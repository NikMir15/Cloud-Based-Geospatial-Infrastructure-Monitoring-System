"""
Phase 6.9C - Incident Automation Engine

Implements controlled, local-project remediation workflows:

    REQUEST
        -> PENDING_APPROVAL
        -> APPROVED
        -> RUNNING
        -> SUCCEEDED / FAILED

No operating-system, cloud-provider, shell, or external remediation
commands are executed. Remediation is simulated inside the project.

Source: LOCAL_PROJECT
External: False
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import text


SOURCE = "LOCAL_PROJECT"
EXTERNAL = False

VALID_EXECUTION_STATUSES = {
    "PENDING_APPROVAL",
    "APPROVED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
}


SEVERITY_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def _utcnow():
    return datetime.now(timezone.utc)


def _row_to_dict(row):
    if row is None:
        return None

    if hasattr(row, "_mapping"):
        return dict(row._mapping)

    return dict(row)


def _severity_meets_minimum(actual, minimum):
    actual_rank = SEVERITY_RANK.get(str(actual or "").lower(), 0)
    minimum_rank = SEVERITY_RANK.get(str(minimum or "").lower(), 0)

    return actual_rank >= minimum_rank


def _history(
    conn,
    execution_id,
    action,
    from_status,
    to_status,
    message,
    changed_by,
):
    conn.execute(
        text(
            """
            INSERT INTO automation_execution_history (
                execution_id,
                action,
                from_status,
                to_status,
                message,
                changed_by
            )
            VALUES (
                :execution_id,
                :action,
                :from_status,
                :to_status,
                :message,
                :changed_by
            )
            """
        ),
        {
            "execution_id": execution_id,
            "action": action,
            "from_status": from_status,
            "to_status": to_status,
            "message": message,
            "changed_by": changed_by,
        },
    )


def get_runbooks(engine, enabled_only=True):
    query = """
        SELECT *
        FROM automation_runbooks
    """

    if enabled_only:
        query += " WHERE enabled = TRUE"

    query += " ORDER BY id"

    with engine.connect() as conn:
        rows = conn.execute(text(query)).fetchall()

    return [_row_to_dict(row) for row in rows]


def get_runbook(engine, runbook_id):
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT *
                FROM automation_runbooks
                WHERE id = :runbook_id
                """
            ),
            {"runbook_id": runbook_id},
        ).fetchone()

    return _row_to_dict(row)


def get_execution(engine, execution_id):
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    ae.*,
                    ar.runbook_key,
                    ar.name AS runbook_name,
                    ar.trigger_metric,
                    ar.minimum_severity,
                    ar.execution_mode
                FROM automation_executions ae
                JOIN automation_runbooks ar
                    ON ar.id = ae.runbook_id
                WHERE ae.id = :execution_id
                """
            ),
            {"execution_id": execution_id},
        ).fetchone()

    return _row_to_dict(row)


def list_executions(engine, limit=100):
    limit = max(1, min(int(limit), 1000))

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    ae.*,
                    ar.runbook_key,
                    ar.name AS runbook_name,
                    ar.trigger_metric,
                    ar.minimum_severity,
                    ar.execution_mode
                FROM automation_executions ae
                JOIN automation_runbooks ar
                    ON ar.id = ae.runbook_id
                ORDER BY ae.created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).fetchall()

    return [_row_to_dict(row) for row in rows]


def execution_history(engine, execution_id):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT *
                FROM automation_execution_history
                WHERE execution_id = :execution_id
                ORDER BY changed_at, id
                """
            ),
            {"execution_id": execution_id},
        ).fetchall()

    return [_row_to_dict(row) for row in rows]


def find_matching_runbooks(engine, metric, severity):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT *
                FROM automation_runbooks
                WHERE enabled = TRUE
                  AND trigger_metric = :metric
                ORDER BY id
                """
            ),
            {"metric": metric},
        ).fetchall()

    matches = []

    for row in rows:
        runbook = _row_to_dict(row)

        if _severity_meets_minimum(
            severity,
            runbook.get("minimum_severity"),
        ):
            matches.append(runbook)

    return matches


def request_execution(
    engine,
    runbook_id,
    incident_id,
    requested_by="operator",
):
    """
    Request a controlled automation execution.

    Runbooks using manual_approval enter PENDING_APPROVAL.
    """

    execution_key = f"AUTO-{uuid.uuid4().hex[:12].upper()}"

    with engine.begin() as conn:

        runbook = conn.execute(
            text(
                """
                SELECT *
                FROM automation_runbooks
                WHERE id = :runbook_id
                """
            ),
            {"runbook_id": runbook_id},
        ).fetchone()

        if runbook is None:
            raise ValueError(f"Runbook {runbook_id} does not exist.")

        runbook = _row_to_dict(runbook)

        if not runbook["enabled"]:
            raise ValueError("Runbook is disabled.")

        incident = conn.execute(
            text(
                """
                SELECT id, severity, status
                FROM incidents
                WHERE id = :incident_id
                """
            ),
            {"incident_id": incident_id},
        ).fetchone()

        if incident is None:
            raise ValueError(f"Incident {incident_id} does not exist.")

        incident = _row_to_dict(incident)

        if not _severity_meets_minimum(
            incident.get("severity"),
            runbook.get("minimum_severity"),
        ):
            raise ValueError(
                "Incident severity does not satisfy the "
                "runbook minimum severity."
            )

        status = (
            "PENDING_APPROVAL"
            if runbook["execution_mode"] == "manual_approval"
            else "APPROVED"
        )

        row = conn.execute(
            text(
                """
                INSERT INTO automation_executions (
                    execution_key,
                    runbook_id,
                    incident_id,
                    status,
                    requested_by,
                    source,
                    external
                )
                VALUES (
                    :execution_key,
                    :runbook_id,
                    :incident_id,
                    :status,
                    :requested_by,
                    :source,
                    :external
                )
                RETURNING id
                """
            ),
            {
                "execution_key": execution_key,
                "runbook_id": runbook_id,
                "incident_id": incident_id,
                "status": status,
                "requested_by": requested_by,
                "source": SOURCE,
                "external": EXTERNAL,
            },
        ).fetchone()

        execution_id = row[0]

        _history(
            conn,
            execution_id,
            "REQUESTED",
            None,
            status,
            (
                f"Automation requested using runbook "
                f"{runbook['runbook_key']}."
            ),
            requested_by,
        )

    return get_execution(engine, execution_id)


def approve_execution(
    engine,
    execution_id,
    approved_by="operator",
):
    with engine.begin() as conn:

        row = conn.execute(
            text(
                """
                SELECT *
                FROM automation_executions
                WHERE id = :execution_id
                FOR UPDATE
                """
            ),
            {"execution_id": execution_id},
        ).fetchone()

        if row is None:
            raise ValueError("Automation execution does not exist.")

        execution = _row_to_dict(row)

        if execution["status"] != "PENDING_APPROVAL":
            raise ValueError(
                "Only PENDING_APPROVAL executions can be approved."
            )

        conn.execute(
            text(
                """
                UPDATE automation_executions
                SET
                    status = 'APPROVED',
                    approved_by = :approved_by
                WHERE id = :execution_id
                """
            ),
            {
                "approved_by": approved_by,
                "execution_id": execution_id,
            },
        )

        _history(
            conn,
            execution_id,
            "APPROVED",
            "PENDING_APPROVAL",
            "APPROVED",
            "Automation execution approved.",
            approved_by,
        )

    return get_execution(engine, execution_id)


def cancel_execution(
    engine,
    execution_id,
    changed_by="operator",
):
    with engine.begin() as conn:

        row = conn.execute(
            text(
                """
                SELECT status
                FROM automation_executions
                WHERE id = :execution_id
                FOR UPDATE
                """
            ),
            {"execution_id": execution_id},
        ).fetchone()

        if row is None:
            raise ValueError("Automation execution does not exist.")

        old_status = row[0]

        if old_status not in {
            "PENDING_APPROVAL",
            "APPROVED",
        }:
            raise ValueError(
                f"Execution in {old_status} cannot be cancelled."
            )

        conn.execute(
            text(
                """
                UPDATE automation_executions
                SET
                    status = 'CANCELLED',
                    completed_at = NOW(),
                    result = 'Automation cancelled before execution.'
                WHERE id = :execution_id
                """
            ),
            {"execution_id": execution_id},
        )

        _history(
            conn,
            execution_id,
            "CANCELLED",
            old_status,
            "CANCELLED",
            "Automation execution cancelled.",
            changed_by,
        )

    return get_execution(engine, execution_id)


def _simulate_remediation(runbook):
    """
    Local-only remediation simulation.

    This intentionally does not execute shell commands, Docker commands,
    cloud APIs, systemctl, SSH, or any external action.
    """

    metric = runbook["trigger_metric"]

    messages = {
        "cpu_percent":
            "Simulated workload redistribution and service recovery.",

        "temperature_c":
            "Simulated thermal remediation and workload reduction.",

        "latency_ms":
            "Simulated network-path remediation and latency recovery.",

        "packet_loss_percent":
            "Simulated network-path recovery and connectivity validation.",

        "health":
            "Simulated infrastructure service recovery.",
    }

    return messages.get(
        metric,
        "Simulated local infrastructure remediation.",
    )


def execute_automation(
    engine,
    execution_id,
    executed_by="automation-engine",
):
    """
    Execute an approved automation.

    Execution is deliberately simulated for Phase 6.9C.
    """

    with engine.begin() as conn:

        row = conn.execute(
            text(
                """
                SELECT
                    ae.*,
                    ar.runbook_key,
                    ar.name AS runbook_name,
                    ar.trigger_metric
                FROM automation_executions ae
                JOIN automation_runbooks ar
                    ON ar.id = ae.runbook_id
                WHERE ae.id = :execution_id
                FOR UPDATE OF ae
                """
            ),
            {"execution_id": execution_id},
        ).fetchone()

        if row is None:
            raise ValueError("Automation execution does not exist.")

        execution = _row_to_dict(row)

        if execution["status"] != "APPROVED":
            raise ValueError(
                "Execution must be APPROVED before it can run."
            )

        conn.execute(
            text(
                """
                UPDATE automation_executions
                SET
                    status = 'RUNNING',
                    started_at = NOW()
                WHERE id = :execution_id
                """
            ),
            {"execution_id": execution_id},
        )

        _history(
            conn,
            execution_id,
            "STARTED",
            "APPROVED",
            "RUNNING",
            (
                f"Started local simulated remediation using "
                f"{execution['runbook_key']}."
            ),
            executed_by,
        )

    # ----------------------------------------------------------
    # Simulation occurs outside the transaction.
    # ----------------------------------------------------------

    try:

        remediation_result = _simulate_remediation(execution)

        verification_result = (
            "Local remediation simulation completed successfully. "
            "No external or host-level action was executed."
        )

        with engine.begin() as conn:

            conn.execute(
                text(
                    """
                    UPDATE automation_executions
                    SET
                        status = 'SUCCEEDED',
                        completed_at = NOW(),
                        result = :result,
                        verification_result = :verification_result,
                        error_message = NULL
                    WHERE id = :execution_id
                    """
                ),
                {
                    "result": remediation_result,
                    "verification_result": verification_result,
                    "execution_id": execution_id,
                },
            )

            _history(
                conn,
                execution_id,
                "SUCCEEDED",
                "RUNNING",
                "SUCCEEDED",
                verification_result,
                executed_by,
            )

    except Exception as exc:

        with engine.begin() as conn:

            conn.execute(
                text(
                    """
                    UPDATE automation_executions
                    SET
                        status = 'FAILED',
                        completed_at = NOW(),
                        error_message = :error_message
                    WHERE id = :execution_id
                    """
                ),
                {
                    "error_message": str(exc),
                    "execution_id": execution_id,
                },
            )

            _history(
                conn,
                execution_id,
                "FAILED",
                "RUNNING",
                "FAILED",
                str(exc),
                executed_by,
            )

        raise

    return get_execution(engine, execution_id)


def automation_summary(engine):
    with engine.connect() as conn:

        row = conn.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_executions,

                    COUNT(*) FILTER (
                        WHERE status = 'PENDING_APPROVAL'
                    ) AS pending_approval,

                    COUNT(*) FILTER (
                        WHERE status = 'APPROVED'
                    ) AS approved,

                    COUNT(*) FILTER (
                        WHERE status = 'RUNNING'
                    ) AS running,

                    COUNT(*) FILTER (
                        WHERE status = 'SUCCEEDED'
                    ) AS successful,

                    COUNT(*) FILTER (
                        WHERE status = 'FAILED'
                    ) AS failed,

                    COUNT(*) FILTER (
                        WHERE status = 'CANCELLED'
                    ) AS cancelled,

                    CASE
                        WHEN COUNT(*) FILTER (
                            WHERE status IN ('SUCCEEDED', 'FAILED')
                        ) = 0
                        THEN 0
                        ELSE ROUND(
                            (
                                COUNT(*) FILTER (
                                    WHERE status = 'SUCCEEDED'
                                )::numeric
                                /
                                COUNT(*) FILTER (
                                    WHERE status IN (
                                        'SUCCEEDED',
                                        'FAILED'
                                    )
                                )
                            ) * 100,
                            2
                        )
                    END AS success_rate_percentage

                FROM automation_executions
                """
            )
        ).fetchone()

    result = _row_to_dict(row)

    result["source"] = SOURCE
    result["external"] = EXTERNAL

    return result
