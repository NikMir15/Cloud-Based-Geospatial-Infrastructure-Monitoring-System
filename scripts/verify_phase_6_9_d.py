#!/usr/bin/env python3
"""
Phase 6.9D — FastAPI Integration Verification

Tests the public Phase 6.9D API lifecycle:

    match -> request -> approve -> execute -> history -> summary

and the Reliability Engineering endpoints:

    objectives -> objective -> evaluate one -> evaluate all
    -> measurements -> reliability summary

The verifier uses only the local FastAPI API. It does not execute external
commands or call external services.

Usage:
    python scripts/verify_phase_6_9_d.py

Optional:
    API_BASE_URL=http://localhost:8000 python scripts/verify_phase_6_9_d.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
SOURCE = "LOCAL_PROJECT"

passed = 0
failed = 0


def check(condition: bool, message: str) -> bool:
    global passed, failed
    if condition:
        passed += 1
        print(f"✅ {message}")
        return True
    failed += 1
    print(f"❌ {message}")
    return False


def pretty(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)


def api(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    expected: tuple[int, ...] = (200,),
) -> tuple[int, Any]:
    url = f"{BASE_URL}{path}"
    data = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status = response.status
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8")
    except Exception as exc:
        print(f"\n❌ {method} {path} failed: {exc}")
        return 0, {"error": str(exc)}

    try:
        body = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        body = {"raw": raw}

    if status not in expected:
        print(f"\n❌ Unexpected HTTP {status}: {method} {path}")
        print(pretty(body))

    return status, body


def provenance(body: Any) -> bool:
    return (
        isinstance(body, dict)
        and body.get("source") == SOURCE
        and body.get("external") is False
    )


def unwrap(body: Any, key: str) -> Any:
    if isinstance(body, dict) and key in body:
        return body[key]
    return body


def execution_status(execution: Any) -> str:
    if not isinstance(execution, dict):
        return ""
    return str(execution.get("status") or "").upper()


def first_id(items: Any) -> int | None:
    if not isinstance(items, list) or not items:
        return None
    value = items[0].get("id") if isinstance(items[0], dict) else None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


print("=" * 68)
print("PHASE 6.9D — FASTAPI INTEGRATION VERIFICATION")
print("=" * 68)
print(f"API: {BASE_URL}\n")


# ---------------------------------------------------------------------------
# 1. Health
# ---------------------------------------------------------------------------

status, health = api("GET", "/health")
check(status == 200, "Backend health endpoint reachable")
if status != 200:
    print("\nBackend is unavailable. Start/rebuild it before running this verifier.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 2. Runbooks
# ---------------------------------------------------------------------------

print("\n=== RUNBOOKS ===")

status, body = api("GET", "/automation/runbooks")
check(status == 200, "GET /automation/runbooks")
check(provenance(body), "Runbooks provenance LOCAL_PROJECT / external false")

runbooks = unwrap(body, "runbooks")
check(isinstance(runbooks, list), "Runbooks response contains a list")
check(bool(runbooks), "At least one enabled runbook available")

if not runbooks:
    print("\nNo runbooks are available; lifecycle verification cannot continue.")
    sys.exit(1)

runbook_id = first_id(runbooks)
check(runbook_id is not None, "Runbook ID available")

runbook = runbooks[0]
metric = str(runbook.get("trigger_metric") or "")
severity = str(runbook.get("minimum_severity") or "high")

print(
    f"Selected runbook: id={runbook_id} "
    f"key={runbook.get('runbook_key')} metric={metric} severity={severity}"
)

status, one_runbook = api("GET", f"/automation/runbooks/{runbook_id}")
check(status == 200, "GET /automation/runbooks/{runbook_id}")
check(provenance(one_runbook), "Single runbook provenance correct")


# ---------------------------------------------------------------------------
# 3. Matching
# ---------------------------------------------------------------------------

print("\n=== MATCHING ===")

status, match_body = api(
    "POST",
    "/automation/matches",
    {
        "metric": metric,
        "severity": severity,
    },
)

check(status == 200, "POST /automation/matches")
check(provenance(match_body), "Matching provenance correct")

matches = unwrap(match_body, "matches")
check(isinstance(matches, list), "Matching response contains matches")
check(
    any(
        isinstance(item, dict) and item.get("id") == runbook_id
        for item in (matches or [])
    ),
    "Selected runbook appears in matching results",
)


# ---------------------------------------------------------------------------
# 4. Find an incident for controlled API lifecycle
# ---------------------------------------------------------------------------

print("\n=== INCIDENT SELECTION ===")

status, incidents_body = api("GET", "/incidents")
check(status == 200, "Existing Phase 6.8 GET /incidents still works")

incidents = (
    incidents_body.get("incidents", [])
    if isinstance(incidents_body, dict)
    else incidents_body
)

incident_id = first_id(incidents)

if incident_id is None:
    print("\n❌ No incident ID available for automation execution request.")
    failed += 1
    print(f"\nPassed: {passed}\nFailed: {failed}")
    sys.exit(1)

print(f"Selected incident: {incident_id}")


# ---------------------------------------------------------------------------
# 5. Request
# ---------------------------------------------------------------------------

print("\n=== REQUEST ===")

status, request_body = api(
    "POST",
    "/automation/executions/request",
    {
        "runbook_id": runbook_id,
        "incident_id": incident_id,
        "requested_by": "PHASE_6_9D_TEST",
    },
)

check(status == 200, "POST /automation/executions/request")
check(provenance(request_body), "Requested execution provenance correct")

execution = unwrap(request_body, "execution")
execution_id = (
    execution.get("id")
    if isinstance(execution, dict)
    else None
)

try:
    execution_id = int(execution_id)
except (TypeError, ValueError):
    execution_id = None

check(execution_id is not None, "Execution ID returned")
check(
    execution_status(execution) == "PENDING_APPROVAL",
    "Requested execution status PENDING_APPROVAL",
)

if execution_id is None:
    print("\nCannot continue without an execution ID.")
    sys.exit(1)

print(f"Execution ID: {execution_id}")


# ---------------------------------------------------------------------------
# 6. Read execution
# ---------------------------------------------------------------------------

status, execution_body = api(
    "GET",
    f"/automation/executions/{execution_id}",
)

check(status == 200, "GET requested execution")
check(provenance(execution_body), "Execution provenance correct")

persisted_execution = unwrap(execution_body, "execution")
check(
    execution_status(persisted_execution) == "PENDING_APPROVAL",
    "PENDING_APPROVAL persisted",
)


# ---------------------------------------------------------------------------
# 7. Approve
# ---------------------------------------------------------------------------

print("\n=== APPROVE ===")

status, approve_body = api(
    "POST",
    f"/automation/executions/{execution_id}/approve",
    {
        "approved_by": "PHASE_6_9D_APPROVER",
    },
)

check(status == 200, "POST execution approval")
check(provenance(approve_body), "Approval provenance correct")

approved_execution = unwrap(approve_body, "execution")
check(
    execution_status(approved_execution) == "APPROVED",
    "Execution status APPROVED",
)


# ---------------------------------------------------------------------------
# 8. Execute
# ---------------------------------------------------------------------------

print("\n=== EXECUTE ===")

status, execute_body = api(
    "POST",
    f"/automation/executions/{execution_id}/execute",
    {
        "executed_by": "PHASE_6_9D_ENGINE",
    },
)

check(status == 200, "POST automation execution")
check(provenance(execute_body), "Execution result provenance correct")

executed = unwrap(execute_body, "execution")
check(
    execution_status(executed) == "SUCCEEDED",
    "Automation execution status SUCCEEDED",
)

if isinstance(executed, dict):
    check(bool(executed.get("started_at")), "Execution start timestamp recorded")
    check(bool(executed.get("completed_at")), "Execution completion timestamp recorded")
    check(bool(executed.get("result")), "Execution result recorded")
    check(bool(executed.get("verification_result")), "Verification result recorded")


# ---------------------------------------------------------------------------
# 9. History
# ---------------------------------------------------------------------------

print("\n=== HISTORY ===")

status, history_body = api(
    "GET",
    f"/automation/executions/{execution_id}/history",
)

check(status == 200, "GET execution history")
check(provenance(history_body), "Execution history provenance correct")

history = unwrap(history_body, "history")
check(isinstance(history, list), "Execution history returned")

actions = [
    str(item.get("action") or "").upper()
    for item in (history or [])
    if isinstance(item, dict)
]

print("Lifecycle:", " -> ".join(actions) if actions else "(empty)")

for expected_action in ("REQUESTED", "APPROVED", "STARTED", "SUCCEEDED"):
    check(
        expected_action in actions,
        f"{expected_action} history event present",
    )

positions = [
    actions.index(action)
    for action in ("REQUESTED", "APPROVED", "STARTED", "SUCCEEDED")
    if action in actions
]

check(
    len(positions) == 4 and positions == sorted(positions),
    "Automation lifecycle event order correct",
)


# ---------------------------------------------------------------------------
# 10. Execution listing + summary
# ---------------------------------------------------------------------------

print("\n=== AUTOMATION SUMMARY ===")

status, executions_body = api("GET", "/automation/executions?limit=100")
check(status == 200, "GET /automation/executions")

execution_list = unwrap(executions_body, "executions")
check(
    any(
        isinstance(item, dict) and item.get("id") == execution_id
        for item in (execution_list or [])
    ),
    "New execution appears in execution queue",
)

status, summary_body = api("GET", "/automation/summary")
check(status == 200, "GET /automation/summary")
check(provenance(summary_body), "Automation summary provenance correct")

automation_stats = unwrap(summary_body, "summary")
check(isinstance(automation_stats, dict), "Automation summary generated")

if isinstance(automation_stats, dict):
    print(
        "Automation summary:",
        pretty(automation_stats),
    )


# ---------------------------------------------------------------------------
# 11. Reliability objectives
# ---------------------------------------------------------------------------

print("\n=== RELIABILITY OBJECTIVES ===")

status, objectives_body = api("GET", "/reliability/objectives")
check(status == 200, "GET /reliability/objectives")
check(provenance(objectives_body), "Reliability objectives provenance correct")

objectives = unwrap(objectives_body, "objectives")
check(isinstance(objectives, list), "Reliability objectives returned")
check(bool(objectives), "At least one SLO available")

objective_id = first_id(objectives)

if objective_id is not None:
    status, objective_body = api(
        "GET",
        f"/reliability/objectives/{objective_id}",
    )
    check(status == 200, "GET single reliability objective")
    check(provenance(objective_body), "Single objective provenance correct")

    print(f"Selected objective: {objective_id}")

    status, evaluate_one_body = api(
        "POST",
        f"/reliability/objectives/{objective_id}/evaluate",
        {},
    )
    check(status == 200, "POST single SLO evaluation")
    check(provenance(evaluate_one_body), "Single SLO evaluation provenance correct")

    result = unwrap(evaluate_one_body, "result")
    check(isinstance(result, dict), "Single SLO evaluation result returned")

else:
    check(False, "Objective ID available")


# ---------------------------------------------------------------------------
# 12. Evaluate all reliability objectives
# ---------------------------------------------------------------------------

print("\n=== RELIABILITY EVALUATION ===")

status, evaluate_all_body = api(
    "POST",
    "/reliability/evaluate",
    {},
)

check(status == 200, "POST /reliability/evaluate")
check(provenance(evaluate_all_body), "All-SLO evaluation provenance correct")

evaluation_summary = unwrap(evaluate_all_body, "results")

results = (
    evaluation_summary.get("results", [])
    if isinstance(evaluation_summary, dict)
    else evaluation_summary
)

check(
    isinstance(results, list),
    "All-SLO evaluation results returned"
)
check(
    isinstance(results, list) and bool(results),
    "At least one reliability objective evaluated"
)


# ---------------------------------------------------------------------------
# 13. Measurements
# ---------------------------------------------------------------------------

print("\n=== RELIABILITY MEASUREMENTS ===")

status, measurements_body = api(
    "GET",
    "/reliability/measurements",
)

check(status == 200, "GET /reliability/measurements")
check(provenance(measurements_body), "Measurements provenance correct")

measurements = unwrap(measurements_body, "measurements")
check(isinstance(measurements, list), "SLO measurements returned")
check(bool(measurements), "Latest SLO measurements available")

if measurements:
    sample = measurements[0]
    if isinstance(sample, dict):
        check("sli_percentage" in sample, "Measurement includes SLI percentage")
        check("status" in sample, "Measurement includes reliability status")
        check(
            sample.get("source") == SOURCE,
            "Persisted measurement source LOCAL_PROJECT",
        )
        check(
            sample.get("external") is False,
            "Persisted measurement external flag false",
        )


# ---------------------------------------------------------------------------
# 14. Reliability summary
# ---------------------------------------------------------------------------

print("\n=== RELIABILITY SUMMARY ===")

status, reliability_body = api(
    "GET",
    "/reliability/summary",
)

check(status == 200, "GET /reliability/summary")
check(provenance(reliability_body), "Reliability summary provenance correct")

reliability_stats = unwrap(reliability_body, "summary")
check(isinstance(reliability_stats, dict), "Reliability summary generated")

if isinstance(reliability_stats, dict):
    print("Reliability summary:", pretty(reliability_stats))


# ---------------------------------------------------------------------------
# Final result
# ---------------------------------------------------------------------------

print("\n" + "=" * 68)
print("PHASE 6.9D RESULT")
print("=" * 68)
print(f"Passed: {passed}")
print(f"Failed: {failed}")

if failed == 0:
    print("✅ Phase 6.9D FastAPI integration verification PASSED")
    sys.exit(0)

print("❌ Phase 6.9D FastAPI integration verification FAILED")
sys.exit(1)
