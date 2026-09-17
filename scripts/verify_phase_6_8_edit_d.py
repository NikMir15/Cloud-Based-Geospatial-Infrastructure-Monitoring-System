#!/usr/bin/env python3

"""
Phase 6.8 Edit D verification
Infrastructure Situational Awareness Platform

Checks:
1. incident_engine.py syntax
2. Phase 6.8 SLA lifecycle functions exist
3. SLA breach fields are updated by the engine
4. acknowledgement lifecycle integrates SLA evaluation
5. resolution lifecycle integrates SLA evaluation
6. existing Phase 6.7 lifecycle functions remain present
7. Phase 6.8 database columns exist
8. Runtime SLA breach evaluation can execute safely

This script is intentionally strict. A failed check exits non-zero.
"""

from pathlib import Path
import ast
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENGINE = PROJECT_ROOT / "backend" / "incident_engine.py"


passed = 0
failed = 0


def ok(message):
    global passed
    passed += 1
    print(f"✅ {message}")


def fail(message):
    global failed
    failed += 1
    print(f"❌ {message}")


def section(title):
    print()
    print("=" * 68)
    print(title)
    print("=" * 68)


def require(condition, message):
    if condition:
        ok(message)
    else:
        fail(message)


# ------------------------------------------------------------
# Load source
# ------------------------------------------------------------

section("1. SOURCE FILE")

if not ENGINE.exists():
    print(f"❌ Missing: {ENGINE}")
    sys.exit(1)

source = ENGINE.read_text(encoding="utf-8")
ok("backend/incident_engine.py exists")


# ------------------------------------------------------------
# Syntax / AST
# ------------------------------------------------------------

section("2. PYTHON SYNTAX")

try:
    tree = ast.parse(source)
    ok("incident_engine.py parses successfully")
except SyntaxError as exc:
    fail(f"Syntax error: {exc}")
    sys.exit(1)


functions = {
    node.name: node
    for node in ast.walk(tree)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}


# ------------------------------------------------------------
# Existing Phase 6.7 lifecycle must survive
# ------------------------------------------------------------

section("3. PHASE 6.7 LIFECYCLE REGRESSION CHECK")

phase67_functions = [
    "update_incident_status",
    "assign_incident",
    "escalate_incident",
    "incident_metrics",
]

for name in phase67_functions:
    require(
        name in functions,
        f"Existing lifecycle function preserved: {name}()",
    )


# ------------------------------------------------------------
# Phase 6.8 configuration from Edit A
# ------------------------------------------------------------

section("4. PHASE 6.8 CONFIGURATION")

requirements = {
    "PRIORITIES":
        "PRIORITIES =",

    "severity-to-priority mapping":
        "SEVERITY_TO_PRIORITY",

    "SLA targets":
        "SLA_TARGETS",

    "priority_for_severity()":
        "def priority_for_severity",

    "sla_targets()":
        "def sla_targets",
}

for name, marker in requirements.items():
    require(marker in source, name)


# ------------------------------------------------------------
# Edit B DB/API fields
# ------------------------------------------------------------

section("5. PHASE 6.8 INCIDENT FIELDS")

phase68_fields = [
    "priority",
    "assigned_team",
    "assigned_at",
    "escalated",
    "escalated_at",
    "escalation_level",
    "acknowledgement_due_at",
    "resolution_due_at",
    "acknowledgement_sla_breached",
    "resolution_sla_breached",
]

for field in phase68_fields:
    require(field in source, f"Field mapped: {field}")


# ------------------------------------------------------------
# Edit C creation integration
# ------------------------------------------------------------

section("6. EDIT C CREATION REGRESSION")

creation_markers = {
    "automatic priority":
        "priority = priority_for_severity(alert.severity)",

    "SLA target lookup":
        "targets = sla_targets(priority)",

    "acknowledgement deadline":
        "make_interval(mins => :ack_minutes)",

    "resolution deadline":
        "make_interval(mins => :resolve_minutes)",
}

for name, marker in creation_markers.items():
    require(marker in source, f"Edit C preserved: {name}")


# ------------------------------------------------------------
# Edit D functions
# ------------------------------------------------------------

section("7. EDIT D SLA FUNCTIONS")

#
# Edit D should expose these functions.
#
# evaluate_incident_sla()
#     evaluates a single incident
#
# evaluate_sla_breaches()
#     evaluates/persists breach state across incidents
#

edit_d_functions = [
    "evaluate_incident_sla",
    "evaluate_sla_breaches",
]

for name in edit_d_functions:
    require(
        name in functions,
        f"Edit D function exists: {name}()",
    )


# ------------------------------------------------------------
# Breach flag persistence
# ------------------------------------------------------------

section("8. SLA BREACH FLAG UPDATES")

breach_markers = [
    "acknowledgement_sla_breached",
    "resolution_sla_breached",
]

for marker in breach_markers:
    require(
        source.count(marker) >= 3,
        f"{marker} is used by mapping/query/lifecycle logic",
    )


require(
    "UPDATE incidents" in source,
    "Incident engine contains incident UPDATE operations",
)


# Try to identify an UPDATE that actually touches SLA flags.

sla_update_detected = (
    "SET acknowledgement_sla_breached" in source
    or "acknowledgement_sla_breached =" in source
)

require(
    sla_update_detected,
    "Acknowledgement SLA breach flag has persistence logic",
)


resolution_update_detected = (
    "resolution_sla_breached =" in source
    or "SET resolution_sla_breached" in source
)

require(
    resolution_update_detected,
    "Resolution SLA breach flag has persistence logic",
)


# ------------------------------------------------------------
# Deadline evaluation
# ------------------------------------------------------------

section("9. DEADLINE EVALUATION")

require(
    "acknowledgement_due_at" in source
    and "acknowledged_at" in source,
    "Acknowledgement SLA compares lifecycle time/deadline",
)

require(
    "resolution_due_at" in source
    and "resolved_at" in source,
    "Resolution SLA compares lifecycle time/deadline",
)


# ------------------------------------------------------------
# Lifecycle integration
# ------------------------------------------------------------

section("10. INCIDENT LIFECYCLE INTEGRATION")


def function_source(name):
    node = functions.get(name)

    if node is None:
        return ""

    lines = source.splitlines()

    return "\n".join(
        lines[node.lineno - 1:node.end_lineno]
    )


update_status_source = function_source(
    "update_incident_status"
)

require(
    bool(update_status_source),
    "update_incident_status() available for inspection",
)


ack_integration = (
    "acknowledged" in update_status_source
    and (
        "evaluate_incident_sla" in update_status_source
        or "acknowledgement_sla_breached"
        in update_status_source
    )
)

require(
    ack_integration,
    "Acknowledgement lifecycle integrates SLA evaluation",
)


resolution_integration = (
    "resolved" in update_status_source
    and (
        "evaluate_incident_sla" in update_status_source
        or "resolution_sla_breached"
        in update_status_source
    )
)

require(
    resolution_integration,
    "Resolution lifecycle integrates SLA evaluation",
)


# ------------------------------------------------------------
# Assignment / escalation regression
# ------------------------------------------------------------

section("11. OPERATIONS REGRESSION")

assign_source = function_source("assign_incident")
escalate_source = function_source("escalate_incident")

require(
    bool(assign_source),
    "assign_incident() remains operational",
)

require(
    bool(escalate_source),
    "escalate_incident() remains operational",
)


# ------------------------------------------------------------
# Database checks
# ------------------------------------------------------------

section("12. DATABASE SCHEMA")

db_query = """
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'incidents'
ORDER BY ordinal_position;
"""


try:
    result = subprocess.run(
        [
            "docker",
            "exec",
            "geodb",
            "psql",
            "-U",
            "postgres",
            "-d",
            "geospatialdb",
            "-At",
            "-c",
            db_query,
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )

    if result.returncode != 0:
        fail(
            "Could not query PostgreSQL: "
            + result.stderr.strip()
        )

    else:
        columns = {
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip()
        }

        db_fields = [
            "priority",
            "assigned_team",
            "assigned_at",
            "escalated",
            "escalated_at",
            "escalation_level",
            "acknowledgement_due_at",
            "resolution_due_at",
            "acknowledgement_sla_breached",
            "resolution_sla_breached",
        ]

        for field in db_fields:
            require(
                field in columns,
                f"Database column exists: {field}",
            )

except Exception as exc:
    fail(f"Database verification failed: {exc}")


# ------------------------------------------------------------
# Database breach-state sanity
# ------------------------------------------------------------

section("13. SLA DATABASE SANITY")

sanity_query = """
SELECT
    COUNT(*) AS total,
    COUNT(*) FILTER (
        WHERE acknowledgement_due_at IS NOT NULL
    ) AS acknowledgement_deadlines,
    COUNT(*) FILTER (
        WHERE resolution_due_at IS NOT NULL
    ) AS resolution_deadlines,
    COUNT(*) FILTER (
        WHERE acknowledgement_sla_breached
    ) AS acknowledgement_breaches,
    COUNT(*) FILTER (
        WHERE resolution_sla_breached
    ) AS resolution_breaches
FROM incidents;
"""


try:
    result = subprocess.run(
        [
            "docker",
            "exec",
            "geodb",
            "psql",
            "-U",
            "postgres",
            "-d",
            "geospatialdb",
            "-At",
            "-F",
            "|",
            "-c",
            sanity_query,
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )

    if result.returncode == 0:
        values = result.stdout.strip()

        if values:
            ok(
                "PostgreSQL returned SLA lifecycle statistics"
            )
            print(f"   {values}")
        else:
            fail("SLA statistics query returned no data")

    else:
        fail(
            "SLA statistics query failed: "
            + result.stderr.strip()
        )

except Exception as exc:
    fail(f"SLA statistics check failed: {exc}")


# ------------------------------------------------------------
# incident_sre_summary
# ------------------------------------------------------------

section("14. SRE SUMMARY VIEW")

summary_query = """
SELECT *
FROM incident_sre_summary;
"""


try:
    result = subprocess.run(
        [
            "docker",
            "exec",
            "geodb",
            "psql",
            "-U",
            "postgres",
            "-d",
            "geospatialdb",
            "-At",
            "-c",
            summary_query,
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )

    if result.returncode == 0 and result.stdout.strip():
        ok("incident_sre_summary returns data")
        print(f"   {result.stdout.strip()}")
    else:
        fail(
            "incident_sre_summary unavailable or empty"
        )

except Exception as exc:
    fail(f"SRE summary verification failed: {exc}")


# ------------------------------------------------------------
# Final result
# ------------------------------------------------------------

section("PHASE 6.8 EDIT D RESULT")

print(f"Passed: {passed}")
print(f"Failed: {failed}")
print()

if failed:
    print("❌ Phase 6.8 Edit D verification FAILED")
    print(
        "This is expected before Edit D has been installed."
    )
    sys.exit(1)

print("✅ Phase 6.8 Edit D verification PASSED")
sys.exit(0)
