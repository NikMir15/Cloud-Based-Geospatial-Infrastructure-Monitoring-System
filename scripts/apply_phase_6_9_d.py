#!/usr/bin/env python3

from pathlib import Path
import shutil
import sys
from datetime import datetime


MAIN = Path("backend/main.py")

START_MARKER = "# ===== PHASE 6.9D FASTAPI INTEGRATION START ====="
END_MARKER = "# ===== PHASE 6.9D FASTAPI INTEGRATION END ====="


PHASE_69D_CODE = r'''
# ===== PHASE 6.9D FASTAPI INTEGRATION START =====
#
# Phase 6.9D
# FastAPI integration for:
#
# - Runbooks
# - Runbook matching
# - Automation execution lifecycle
# - Approval
# - Execution
# - Cancellation
# - Execution history
# - Automation summary
# - Reliability objectives
# - Reliability evaluation
# - Reliability measurements
# - Reliability summary
#
# Provenance:
#   source   = LOCAL_PROJECT
#   external = false
#
# Automation execution remains simulated/project-local.
# ============================================================


from automation_engine import (
    get_runbooks as automation_get_runbooks,
    get_runbook as automation_get_runbook,
    get_execution as automation_get_execution,
    list_executions as automation_list_executions,
    execution_history as automation_execution_history,
    find_matching_runbooks as automation_find_matching_runbooks,
    request_execution as automation_request_execution,
    approve_execution as automation_approve_execution,
    execute_automation as automation_execute,
    cancel_execution as automation_cancel_execution,
    automation_summary as get_automation_summary,
)

from reliability_engine import (
    list_service_objectives as reliability_list_service_objectives,
    get_service_objective as reliability_get_service_objective,
    evaluate_objective as reliability_evaluate_objective,
    evaluate_all_objectives as reliability_evaluate_all_objectives,
    latest_slo_measurements as reliability_latest_slo_measurements,
    reliability_summary as get_reliability_summary,
)


# ============================================================
# PHASE 6.9D REQUEST MODELS
# ============================================================


class AutomationMatchRequest(BaseModel):
    metric: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    severity: str = Field(
        ...,
        min_length=1,
        max_length=30,
    )


class AutomationRequestExecutionRequest(BaseModel):
    runbook_id: int = Field(
        ...,
        gt=0,
    )

    incident_id: int = Field(
        ...,
        gt=0,
    )

    requested_by: str = Field(
        default="operator",
        min_length=1,
        max_length=150,
    )


class AutomationApprovalRequest(BaseModel):
    approved_by: str = Field(
        default="operator",
        min_length=1,
        max_length=150,
    )


class AutomationExecuteRequest(BaseModel):
    executed_by: str = Field(
        default="automation-engine",
        min_length=1,
        max_length=150,
    )


class AutomationCancelRequest(BaseModel):
    changed_by: str = Field(
        default="operator",
        min_length=1,
        max_length=150,
    )


# ============================================================
# PHASE 6.9D HELPERS
# ============================================================


def _phase_69d_payload(data):
    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "data": data,
    }


def _phase_69d_mutation_payload(data):
    """
    Mutation endpoints expose execution fields at the top level.

    This allows callers and verification scripts to directly read:
        id
        status
        runbook_id
        incident_id
        requested_by
        approved_by
        result
        verification_result

    while still preserving provenance.
    """

    if data is None:
        data = {}

    if not isinstance(data, dict):
        return {
            "source": "LOCAL_PROJECT",
            "external": False,
            "data": data,
        }

    return {
        **data,
        "source": "LOCAL_PROJECT",
        "external": False,
    }


def _phase_69d_not_found(
    entity: str,
    entity_id,
):
    raise HTTPException(
        status_code=404,
        detail=f"{entity} {entity_id} not found",
    )


# ============================================================
# RUNBOOKS
# ============================================================


@app.get(
    "/automation/runbooks",
    tags=["Phase 6.9 Automation"],
)
def phase_69d_runbooks_api(
    enabled_only: bool = True,
):
    runbooks = automation_get_runbooks(
        engine,
        enabled_only=enabled_only,
    )

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "count": len(runbooks),
        "runbooks": runbooks,
    }


@app.get(
    "/automation/runbooks/{runbook_id}",
    tags=["Phase 6.9 Automation"],
)
def phase_69d_runbook_api(
    runbook_id: int,
):
    runbook = automation_get_runbook(
        engine,
        runbook_id,
    )

    if not runbook:
        _phase_69d_not_found(
            "Runbook",
            runbook_id,
        )

    return {
        **runbook,
        "source": "LOCAL_PROJECT",
        "external": False,
    }


# ============================================================
# MATCHING
# ============================================================


@app.post(
    "/automation/matches",
    tags=["Phase 6.9 Automation"],
)
def phase_69d_match_runbooks_api(
    request: AutomationMatchRequest,
):
    matches = automation_find_matching_runbooks(
        engine,
        request.metric,
        request.severity,
    )

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "metric": request.metric,
        "severity": request.severity,
        "count": len(matches),
        "matches": matches,
    }


# Optional GET compatibility endpoint.
# Useful for browser/manual testing.

@app.get(
    "/automation/match",
    tags=["Phase 6.9 Automation"],
)
def phase_69d_match_runbooks_get_api(
    metric: str,
    severity: str,
):
    matches = automation_find_matching_runbooks(
        engine,
        metric,
        severity,
    )

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "metric": metric,
        "severity": severity,
        "count": len(matches),
        "matches": matches,
    }


# ============================================================
# EXECUTION LIST
# ============================================================


@app.get(
    "/automation/executions",
    tags=["Phase 6.9 Automation"],
)
def phase_69d_executions_api(
    limit: int = 100,
):
    limit = max(
        1,
        min(limit, 1000),
    )

    executions = automation_list_executions(
        engine,
        limit=limit,
    )

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "count": len(executions),
        "executions": executions,
    }


# ============================================================
# REQUEST EXECUTION
# IMPORTANT: defined before /{execution_id}
# ============================================================


@app.post(
    "/automation/executions/request",
    tags=["Phase 6.9 Automation"],
)
def phase_69d_request_execution_api(
    request: AutomationRequestExecutionRequest,
):
    runbook = automation_get_runbook(
        engine,
        request.runbook_id,
    )

    if not runbook:
        _phase_69d_not_found(
            "Runbook",
            request.runbook_id,
        )

    try:
        result = automation_request_execution(
            engine,
            request.runbook_id,
            request.incident_id,
            requested_by=request.requested_by,
        )

        return _phase_69d_mutation_payload(
            result
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to request automation "
                f"execution: {exc}"
            ),
        )


# ============================================================
# SINGLE EXECUTION
# ============================================================


@app.get(
    "/automation/executions/{execution_id}",
    tags=["Phase 6.9 Automation"],
)
def phase_69d_execution_api(
    execution_id: int,
):
    execution = automation_get_execution(
        engine,
        execution_id,
    )

    if not execution:
        _phase_69d_not_found(
            "Automation execution",
            execution_id,
        )

    return {
        **execution,
        "source": "LOCAL_PROJECT",
        "external": False,
    }


# ============================================================
# EXECUTION HISTORY
# ============================================================


@app.get(
    "/automation/executions/{execution_id}/history",
    tags=["Phase 6.9 Automation"],
)
def phase_69d_execution_history_api(
    execution_id: int,
):
    execution = automation_get_execution(
        engine,
        execution_id,
    )

    if not execution:
        _phase_69d_not_found(
            "Automation execution",
            execution_id,
        )

    history = automation_execution_history(
        engine,
        execution_id,
    )

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "execution_id": execution_id,
        "count": len(history),
        "history": history,
    }


# ============================================================
# APPROVE EXECUTION
# ============================================================


@app.post(
    "/automation/executions/{execution_id}/approve",
    tags=["Phase 6.9 Automation"],
)
def phase_69d_approve_execution_api(
    execution_id: int,
    request: AutomationApprovalRequest,
):
    execution = automation_get_execution(
        engine,
        execution_id,
    )

    if not execution:
        _phase_69d_not_found(
            "Automation execution",
            execution_id,
        )

    try:
        result = automation_approve_execution(
            engine,
            execution_id,
            approved_by=request.approved_by,
        )

        return _phase_69d_mutation_payload(
            result
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to approve automation "
                f"execution: {exc}"
            ),
        )


# ============================================================
# EXECUTE AUTOMATION
# ============================================================


@app.post(
    "/automation/executions/{execution_id}/execute",
    tags=["Phase 6.9 Automation"],
)
def phase_69d_execute_execution_api(
    execution_id: int,
    request: AutomationExecuteRequest,
):
    execution = automation_get_execution(
        engine,
        execution_id,
    )

    if not execution:
        _phase_69d_not_found(
            "Automation execution",
            execution_id,
        )

    try:
        result = automation_execute(
            engine,
            execution_id,
            executed_by=request.executed_by,
        )

        return _phase_69d_mutation_payload(
            result
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to execute automation: "
                f"{exc}"
            ),
        )


# ============================================================
# CANCEL EXECUTION
# ============================================================


@app.post(
    "/automation/executions/{execution_id}/cancel",
    tags=["Phase 6.9 Automation"],
)
def phase_69d_cancel_execution_api(
    execution_id: int,
    request: AutomationCancelRequest,
):
    execution = automation_get_execution(
        engine,
        execution_id,
    )

    if not execution:
        _phase_69d_not_found(
            "Automation execution",
            execution_id,
        )

    try:
        result = automation_cancel_execution(
            engine,
            execution_id,
            changed_by=request.changed_by,
        )

        return _phase_69d_mutation_payload(
            result
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to cancel automation "
                f"execution: {exc}"
            ),
        )


# ============================================================
# AUTOMATION SUMMARY
# ============================================================


@app.get(
    "/automation/summary",
    tags=["Phase 6.9 Automation"],
)
def phase_69d_automation_summary_api():
    summary = get_automation_summary(
        engine
    )

    if isinstance(summary, dict):
        return {
            **summary,
            "source": "LOCAL_PROJECT",
            "external": False,
        }

    return _phase_69d_payload(summary)


# ============================================================
# RELIABILITY OBJECTIVES
# ============================================================


@app.get(
    "/reliability/objectives",
    tags=["Phase 6.9 Reliability"],
)
def phase_69d_reliability_objectives_api(
    enabled_only: bool = False,
):
    objectives = reliability_list_service_objectives(
        engine,
        enabled_only=enabled_only,
    )

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "count": len(objectives),
        "objectives": objectives,
    }


@app.get(
    "/reliability/objectives/{objective_id}",
    tags=["Phase 6.9 Reliability"],
)
def phase_69d_reliability_objective_api(
    objective_id: int,
):
    objective = reliability_get_service_objective(
        engine,
        objective_id,
    )

    if not objective:
        _phase_69d_not_found(
            "Reliability objective",
            objective_id,
        )

    return {
        **objective,
        "source": "LOCAL_PROJECT",
        "external": False,
    }


# ============================================================
# EVALUATE SINGLE RELIABILITY OBJECTIVE
# ============================================================


@app.post(
    "/reliability/objectives/{objective_id}/evaluate",
    tags=["Phase 6.9 Reliability"],
)
def phase_69d_evaluate_reliability_objective_api(
    objective_id: int,
    persist: bool = True,
):
    objective = reliability_get_service_objective(
        engine,
        objective_id,
    )

    if not objective:
        _phase_69d_not_found(
            "Reliability objective",
            objective_id,
        )

    try:
        result = reliability_evaluate_objective(
            engine,
            objective_id,
            persist=persist,
        )

        if isinstance(result, dict):
            return {
                **result,
                "source": "LOCAL_PROJECT",
                "external": False,
            }

        return _phase_69d_payload(result)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ============================================================
# EVALUATE ALL RELIABILITY OBJECTIVES
# ============================================================


@app.post(
    "/reliability/evaluate",
    tags=["Phase 6.9 Reliability"],
)
def phase_69d_evaluate_all_reliability_api(
    persist: bool = True,
):
    results = reliability_evaluate_all_objectives(
        engine,
        persist=persist,
    )

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "count": len(results),
        "results": results,
    }


# ============================================================
# LATEST SLO MEASUREMENTS
# ============================================================


@app.get(
    "/reliability/measurements",
    tags=["Phase 6.9 Reliability"],
)
def phase_69d_reliability_measurements_api():
    measurements = reliability_latest_slo_measurements(
        engine,
    )

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "count": len(measurements),
        "measurements": measurements,
    }


# ============================================================
# RELIABILITY SUMMARY
# ============================================================


@app.get(
    "/reliability/summary",
    tags=["Phase 6.9 Reliability"],
)
def phase_69d_reliability_summary_api():
    summary = get_reliability_summary(
        engine
    )

    if isinstance(summary, dict):
        return {
            **summary,
            "source": "LOCAL_PROJECT",
            "external": False,
        }

    return _phase_69d_payload(summary)


# ===== PHASE 6.9D FASTAPI INTEGRATION END =====
'''


def fail(message: str):
    print(f"❌ {message}")
    sys.exit(1)


def main():
    print("=" * 68)
    print("PHASE 6.9D — FASTAPI CONTRACT UPDATE")
    print("=" * 68)

    if not MAIN.exists():
        fail(
            "backend/main.py was not found"
        )

    original = MAIN.read_text(
        encoding="utf-8"
    )

    if "app = FastAPI(" not in original:
        fail(
            "FastAPI application definition "
            "was not found"
        )

    if "engine = create_engine(" not in original:
        fail(
            "SQLAlchemy engine definition "
            "was not found"
        )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup = MAIN.with_name(
        "main.py.before-phase-6-9d-"
        f"contract-{timestamp}"
    )

    shutil.copy2(
        MAIN,
        backup,
    )

    print(
        f"✅ Backup created: {backup}"
    )

    start = original.find(
        START_MARKER
    )

    end = original.find(
        END_MARKER
    )

    if start != -1 and end != -1:
        end += len(END_MARKER)

        print(
            "Existing Phase 6.9D block found."
        )

        print(
            "Replacing existing block..."
        )

        updated = (
            original[:start].rstrip()
            + "\n\n"
            + PHASE_69D_CODE.strip()
            + "\n"
            + original[end:].lstrip("\n")
        )

    elif start == -1 and end == -1:
        print(
            "No existing Phase 6.9D block found."
        )

        print(
            "Appending Phase 6.9D block..."
        )

        updated = (
            original.rstrip()
            + "\n\n"
            + PHASE_69D_CODE.strip()
            + "\n"
        )

    else:
        fail(
            "Only one Phase 6.9D marker was found. "
            "Restore the backup before continuing."
        )

    MAIN.write_text(
        updated,
        encoding="utf-8",
    )

    print(
        "✅ backend/main.py updated"
    )

    print(
        f"Old lines: {len(original.splitlines())}"
    )

    print(
        f"New lines: {len(updated.splitlines())}"
    )

    print()
    print(
        "Phase 6.9D routes installed:"
    )

    routes = [
        "GET  /automation/runbooks",
        "GET  /automation/runbooks/{runbook_id}",
        "POST /automation/matches",
        "GET  /automation/match",
        "GET  /automation/executions",
        "POST /automation/executions/request",
        "GET  /automation/executions/{execution_id}",
        "GET  /automation/executions/{execution_id}/history",
        "POST /automation/executions/{execution_id}/approve",
        "POST /automation/executions/{execution_id}/execute",
        "POST /automation/executions/{execution_id}/cancel",
        "GET  /automation/summary",
        "GET  /reliability/objectives",
        "GET  /reliability/objectives/{objective_id}",
        "POST /reliability/objectives/{objective_id}/evaluate",
        "POST /reliability/evaluate",
        "GET  /reliability/measurements",
        "GET  /reliability/summary",
    ]

    for route in routes:
        print(
            f"  {route}"
        )

    print()
    print(
        "Next:"
    )

    print(
        "  python -m py_compile backend/main.py"
    )

    print(
        "  docker compose up -d --build backend"
    )

    print(
        "  python scripts/verify_phase_6_9_d.py"
    )


if __name__ == "__main__":
    main()
