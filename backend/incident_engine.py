"""
Phase 6.7 Incident Management Engine
Infrastructure Situational Awareness Platform

Purpose
-------
Correlates persistent Phase 6.6 telemetry alerts into durable incidents,
tracks ownership and lifecycle events, and exposes SRE metrics including
MTTA and MTTR.

All incident data is project-local:
    source = LOCAL_PROJECT
    external = False
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy import text


SOURCE = "LOCAL_PROJECT"
EXTERNAL = False

SEVERITY_ORDER = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

INCIDENT_STATUSES = {
    "open",
    "investigating",
    "mitigated",
    "resolved",
}

ACTIVE_INCIDENT_STATUSES = {
    "open",
    "investigating",
    "mitigated",
}


def utc_now():
    return datetime.now(timezone.utc)


def iso(value):
    return value.isoformat() if value is not None else None


def severity_rank(value):
    return SEVERITY_ORDER.get(str(value or "low").lower(), 1)


def highest_severity(values):
    candidates = [str(v).lower() for v in values if v]
    if not candidates:
        return "low"
    return max(candidates, key=severity_rank)


def next_severity(current):
    current = str(current or "low").lower()
    order = ["low", "medium", "high", "critical"]
    try:
        index = order.index(current)
    except ValueError:
        return "medium"
    return order[min(index + 1, len(order) - 1)]


def add_incident_history_event(
    conn,
    incident_id,
    action,
    from_status=None,
    to_status=None,
    severity=None,
    owner=None,
    note=None,
    changed_by="SYSTEM",
):
    conn.execute(
        text("""
            INSERT INTO incident_history (
                incident_id,
                action,
                from_status,
                to_status,
                severity,
                owner,
                note,
                changed_by,
                changed_at
            )
            VALUES (
                :incident_id,
                :action,
                :from_status,
                :to_status,
                :severity,
                :owner,
                :note,
                :changed_by,
                NOW()
            );
        """),
        {
            "incident_id": incident_id,
            "action": action,
            "from_status": from_status,
            "to_status": to_status,
            "severity": severity,
            "owner": owner,
            "note": note,
            "changed_by": changed_by,
        },
    )


def _incident_key(asset_id):
    return (
        f"INC-{utc_now().strftime('%Y%m%d')}-"
        f"{asset_id}-{uuid4().hex[:8].upper()}"
    )


def _row_to_incident(row):
    mapping = row._mapping if hasattr(row, "_mapping") else row
    return {
        "id": mapping["id"],
        "incident_key": mapping["incident_key"],
        "title": mapping["title"],
        "summary": mapping["summary"],
        "primary_asset_id": mapping["primary_asset_id"],
        "primary_asset_name": mapping["primary_asset_name"],
        "severity": mapping["severity"],
        "status": mapping["status"],
        "owner": mapping["owner"],
        "source": mapping["source"],
        "external": mapping["external"],
        "alert_count": mapping.get("alert_count", 0),
        "active_alert_count": mapping.get("active_alert_count", 0),
        "impacted_assets_count": mapping.get("impacted_assets_count", 1),
        "created_at": iso(mapping["created_at"]),
        "first_seen_at": iso(mapping["first_seen_at"]),
        "last_seen_at": iso(mapping["last_seen_at"]),
        "acknowledged_at": iso(mapping["acknowledged_at"]),
        "mitigated_at": iso(mapping["mitigated_at"]),
        "resolved_at": iso(mapping["resolved_at"]),
        "updated_at": iso(mapping["updated_at"]),
        "resolution_note": mapping["resolution_note"],
    }


INCIDENT_SELECT = """
    SELECT
        i.id,
        i.incident_key,
        i.title,
        i.summary,
        i.primary_asset_id,
        i.primary_asset_name,
        i.severity,
        i.status,
        i.owner,
        i.source,
        i.external,
        i.created_at,
        i.first_seen_at,
        i.last_seen_at,
        i.acknowledged_at,
        i.mitigated_at,
        i.resolved_at,
        i.updated_at,
        i.resolution_note,
        COUNT(DISTINCT ia.alert_id)::integer AS alert_count,
        COUNT(
            DISTINCT ia.alert_id
        ) FILTER (
            WHERE ta.status IN ('active', 'acknowledged')
        )::integer AS active_alert_count,
        COUNT(DISTINCT ta.asset_id)::integer AS impacted_assets_count
    FROM incidents i
    LEFT JOIN incident_alerts ia
        ON ia.incident_id = i.id
    LEFT JOIN telemetry_alerts ta
        ON ta.id = ia.alert_id
"""


def get_incident(conn, incident_id):
    row = conn.execute(
        text(
            INCIDENT_SELECT
            + """
            WHERE i.id = :incident_id
            GROUP BY i.id;
            """
        ),
        {"incident_id": incident_id},
    ).fetchone()

    if row is None:
        return None

    incident = _row_to_incident(row)

    alerts = conn.execute(
        text("""
            SELECT
                ta.id,
                ta.alert_key,
                ta.asset_id,
                ta.asset_name,
                ta.metric,
                ta.metric_label,
                ta.alert_kind,
                ta.severity,
                ta.status,
                ta.message,
                ta.latest_value,
                ta.reference_value,
                ta.threshold,
                ta.delta,
                ta.unit,
                ta.first_seen_at,
                ta.last_seen_at,
                ta.acknowledged_at,
                ta.resolved_at,
                ia.linked_at,
                ia.link_reason
            FROM incident_alerts ia
            JOIN telemetry_alerts ta
                ON ta.id = ia.alert_id
            WHERE ia.incident_id = :incident_id
            ORDER BY
                CASE ta.severity
                    WHEN 'critical' THEN 4
                    WHEN 'high' THEN 3
                    WHEN 'medium' THEN 2
                    ELSE 1
                END DESC,
                ta.last_seen_at DESC;
        """),
        {"incident_id": incident_id},
    ).fetchall()

    incident["alerts"] = [
        {
            "id": item.id,
            "alert_key": item.alert_key,
            "asset_id": item.asset_id,
            "asset_name": item.asset_name,
            "metric": item.metric,
            "metric_label": item.metric_label,
            "alert_kind": item.alert_kind,
            "severity": item.severity,
            "status": item.status,
            "message": item.message,
            "latest_value": float(item.latest_value)
                if item.latest_value is not None else None,
            "reference_value": float(item.reference_value)
                if item.reference_value is not None else None,
            "threshold": float(item.threshold)
                if item.threshold is not None else None,
            "delta": float(item.delta)
                if item.delta is not None else None,
            "unit": item.unit,
            "first_seen_at": iso(item.first_seen_at),
            "last_seen_at": iso(item.last_seen_at),
            "acknowledged_at": iso(item.acknowledged_at),
            "resolved_at": iso(item.resolved_at),
            "linked_at": iso(item.linked_at),
            "link_reason": item.link_reason,
        }
        for item in alerts
    ]

    return incident


def list_incidents(
    engine,
    status=None,
    severity=None,
    owner=None,
    asset_id=None,
    limit=100,
):
    clauses = []
    params = {"limit": limit}

    if status:
        clauses.append("i.status = :status")
        params["status"] = status

    if severity:
        clauses.append("i.severity = :severity")
        params["severity"] = severity

    if owner:
        clauses.append("LOWER(COALESCE(i.owner, '')) = LOWER(:owner)")
        params["owner"] = owner

    if asset_id:
        clauses.append("""
            EXISTS (
                SELECT 1
                FROM incident_alerts ia2
                JOIN telemetry_alerts ta2
                    ON ta2.id = ia2.alert_id
                WHERE ia2.incident_id = i.id
                  AND ta2.asset_id = :asset_id
            )
        """)
        params["asset_id"] = asset_id

    where_sql = (
        "WHERE " + " AND ".join(clauses)
        if clauses else ""
    )

    query = (
        INCIDENT_SELECT
        + f"""
        {where_sql}
        GROUP BY i.id
        ORDER BY
            CASE i.status
                WHEN 'open' THEN 1
                WHEN 'investigating' THEN 2
                WHEN 'mitigated' THEN 3
                ELSE 4
            END,
            CASE i.severity
                WHEN 'critical' THEN 4
                WHEN 'high' THEN 3
                WHEN 'medium' THEN 2
                ELSE 1
            END DESC,
            i.last_seen_at DESC
        LIMIT :limit;
        """
    )

    with engine.connect() as conn:
        rows = conn.execute(text(query), params).fetchall()

    return [_row_to_incident(row) for row in rows]


def load_incident_history(engine, incident_id):
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT
                    id,
                    incident_id,
                    action,
                    from_status,
                    to_status,
                    severity,
                    owner,
                    note,
                    changed_by,
                    changed_at
                FROM incident_history
                WHERE incident_id = :incident_id
                ORDER BY changed_at ASC, id ASC;
            """),
            {"incident_id": incident_id},
        ).fetchall()

    return [
        {
            "id": row.id,
            "incident_id": row.incident_id,
            "action": row.action,
            "from_status": row.from_status,
            "to_status": row.to_status,
            "severity": row.severity,
            "owner": row.owner,
            "note": row.note,
            "changed_by": row.changed_by,
            "changed_at": iso(row.changed_at),
        }
        for row in rows
    ]


def _find_candidate_incident(conn, asset_id, correlation_minutes):
    row = conn.execute(
        text("""
            SELECT id
            FROM incidents
            WHERE primary_asset_id = :asset_id
              AND status IN ('open', 'investigating', 'mitigated')
              AND last_seen_at >= NOW() - make_interval(mins => :minutes)
            ORDER BY last_seen_at DESC
            LIMIT 1
            FOR UPDATE;
        """),
        {
            "asset_id": asset_id,
            "minutes": int(correlation_minutes),
        },
    ).fetchone()

    return row.id if row else None


def _create_incident(conn, alert):
    title = (
        f"{alert.asset_name}: telemetry incident"
    )

    summary = (
        f"Correlated telemetry anomaly affecting {alert.asset_name}. "
        f"Initial signal: {alert.metric_label or alert.metric}."
    )

    row = conn.execute(
        text("""
            INSERT INTO incidents (
                incident_key,
                title,
                summary,
                primary_asset_id,
                primary_asset_name,
                severity,
                status,
                source,
                external,
                created_at,
                first_seen_at,
                last_seen_at,
                updated_at
            )
            VALUES (
                :incident_key,
                :title,
                :summary,
                :asset_id,
                :asset_name,
                :severity,
                'open',
                'LOCAL_PROJECT',
                FALSE,
                NOW(),
                COALESCE(:first_seen_at, NOW()),
                COALESCE(:last_seen_at, NOW()),
                NOW()
            )
            RETURNING id;
        """),
        {
            "incident_key": _incident_key(alert.asset_id),
            "title": title,
            "summary": summary,
            "asset_id": alert.asset_id,
            "asset_name": alert.asset_name,
            "severity": alert.severity,
            "first_seen_at": alert.first_seen_at,
            "last_seen_at": alert.last_seen_at,
        },
    ).fetchone()

    incident_id = row.id

    add_incident_history_event(
        conn,
        incident_id=incident_id,
        action="CREATED",
        from_status=None,
        to_status="open",
        severity=alert.severity,
        owner=None,
        note="Incident created automatically from telemetry alert correlation.",
        changed_by="SYSTEM",
    )

    return incident_id


def _link_alert(conn, incident_id, alert_id, reason):
    conn.execute(
        text("""
            INSERT INTO incident_alerts (
                incident_id,
                alert_id,
                linked_at,
                link_reason
            )
            VALUES (
                :incident_id,
                :alert_id,
                NOW(),
                :reason
            )
            ON CONFLICT (alert_id) DO NOTHING;
        """),
        {
            "incident_id": incident_id,
            "alert_id": alert_id,
            "reason": reason,
        },
    )


def _refresh_incident(conn, incident_id):
    incident = conn.execute(
        text("""
            SELECT
                id,
                status,
                severity,
                owner,
                resolved_at
            FROM incidents
            WHERE id = :incident_id
            FOR UPDATE;
        """),
        {"incident_id": incident_id},
    ).fetchone()

    if incident is None:
        return

    aggregate = conn.execute(
        text("""
            SELECT
                COUNT(*)::integer AS alert_count,
                COUNT(*) FILTER (
                    WHERE ta.status IN ('active', 'acknowledged')
                )::integer AS active_alert_count,
                MAX(ta.last_seen_at) AS max_last_seen,
                MIN(ta.first_seen_at) AS min_first_seen,
                COUNT(DISTINCT ta.asset_id)::integer AS impacted_assets_count
            FROM incident_alerts ia
            JOIN telemetry_alerts ta
                ON ta.id = ia.alert_id
            WHERE ia.incident_id = :incident_id;
        """),
        {"incident_id": incident_id},
    ).fetchone()

    severity_rows = conn.execute(
        text("""
            SELECT ta.severity
            FROM incident_alerts ia
            JOIN telemetry_alerts ta
                ON ta.id = ia.alert_id
            WHERE ia.incident_id = :incident_id
              AND ta.status IN ('active', 'acknowledged');
        """),
        {"incident_id": incident_id},
    ).fetchall()

    active_severity = highest_severity(
        [row.severity for row in severity_rows]
    )

    if aggregate.active_alert_count > 0:
        previous_status = incident.status
        target_status = incident.status

        if incident.status == "resolved":
            target_status = "open"

        previous_severity = incident.severity
        new_severity = active_severity

        conn.execute(
            text("""
                UPDATE incidents
                SET
                    severity = :severity,
                    status = :status,
                    first_seen_at = COALESCE(:first_seen_at, first_seen_at),
                    last_seen_at = COALESCE(:last_seen_at, NOW()),
                    resolved_at = CASE
                        WHEN :status = 'resolved' THEN resolved_at
                        ELSE NULL
                    END,
                    resolution_note = CASE
                        WHEN :status = 'resolved' THEN resolution_note
                        ELSE NULL
                    END,
                    updated_at = NOW()
                WHERE id = :incident_id;
            """),
            {
                "severity": new_severity,
                "status": target_status,
                "first_seen_at": aggregate.min_first_seen,
                "last_seen_at": aggregate.max_last_seen,
                "incident_id": incident_id,
            },
        )

        if previous_status == "resolved" and target_status == "open":
            add_incident_history_event(
                conn,
                incident_id,
                action="REOPENED",
                from_status="resolved",
                to_status="open",
                severity=new_severity,
                owner=incident.owner,
                note="A linked telemetry alert became active again.",
                changed_by="SYSTEM",
            )

        if previous_severity != new_severity:
            add_incident_history_event(
                conn,
                incident_id,
                action="SEVERITY_CHANGED",
                from_status=target_status,
                to_status=target_status,
                severity=new_severity,
                owner=incident.owner,
                note=(
                    f"Incident severity changed from "
                    f"{previous_severity} to {new_severity}."
                ),
                changed_by="SYSTEM",
            )

    else:
        if incident.status != "resolved":
            previous_status = incident.status

            conn.execute(
                text("""
                    UPDATE incidents
                    SET
                        status = 'resolved',
                        resolved_at = NOW(),
                        resolution_note = 'All linked telemetry alerts resolved',
                        updated_at = NOW()
                    WHERE id = :incident_id;
                """),
                {"incident_id": incident_id},
            )

            add_incident_history_event(
                conn,
                incident_id,
                action="AUTO_RESOLVED",
                from_status=previous_status,
                to_status="resolved",
                severity=incident.severity,
                owner=incident.owner,
                note="All linked telemetry alerts returned to a resolved state.",
                changed_by="SYSTEM",
            )


def synchronize_incidents(engine, correlation_minutes=30):
    """
    Correlate every active/acknowledged persisted telemetry alert.

    Current Phase 6.7 correlation policy:
      - Same infrastructure asset
      - Existing non-resolved incident
      - Last activity inside correlation_minutes

    This is intentionally deterministic and explainable for a portfolio/SRE
    project. Cross-asset topology correlation can be added in a later phase.
    """

    created = 0
    linked = 0
    refreshed = 0

    with engine.begin() as conn:
        active_alerts = conn.execute(
            text("""
                SELECT
                    ta.id,
                    ta.alert_key,
                    ta.asset_id,
                    ta.asset_name,
                    ta.metric,
                    ta.metric_label,
                    ta.alert_kind,
                    ta.severity,
                    ta.status,
                    ta.first_seen_at,
                    ta.last_seen_at
                FROM telemetry_alerts ta
                LEFT JOIN incident_alerts ia
                    ON ia.alert_id = ta.id
                WHERE ta.status IN ('active', 'acknowledged')
                  AND ia.alert_id IS NULL
                ORDER BY ta.asset_id, ta.first_seen_at ASC;
            """)
        ).fetchall()

        touched = set()

        for alert in active_alerts:
            incident_id = _find_candidate_incident(
                conn,
                alert.asset_id,
                correlation_minutes,
            )

            if incident_id is None:
                incident_id = _create_incident(conn, alert)
                created += 1
                reason = (
                    "New incident created: first unresolved telemetry alert "
                    "for this asset in the correlation window."
                )
            else:
                reason = (
                    "Automatically correlated by matching asset within "
                    f"{correlation_minutes}-minute incident window."
                )

            _link_alert(
                conn,
                incident_id,
                alert.id,
                reason,
            )
            linked += 1
            touched.add(incident_id)

        all_active_incidents = conn.execute(
            text("""
                SELECT id
                FROM incidents
                WHERE status IN (
                    'open',
                    'investigating',
                    'mitigated'
                )
                OR EXISTS (
                    SELECT 1
                    FROM incident_alerts ia
                    JOIN telemetry_alerts ta
                        ON ta.id = ia.alert_id
                    WHERE ia.incident_id = incidents.id
                      AND ta.status IN ('active', 'acknowledged')
                );
            """)
        ).fetchall()

        touched.update(row.id for row in all_active_incidents)

        for incident_id in touched:
            _refresh_incident(conn, incident_id)
            refreshed += 1

    return {
        "source": SOURCE,
        "external": EXTERNAL,
        "created": created,
        "linked": linked,
        "refreshed": refreshed,
        "generated_at": utc_now().isoformat(),
    }


def update_incident_status(
    engine,
    incident_id,
    target_status,
    changed_by="operator",
    note=None,
):
    target_status = str(target_status).lower()

    if target_status not in INCIDENT_STATUSES:
        raise ValueError("Invalid incident status")

    with engine.begin() as conn:
        current = conn.execute(
            text("""
                SELECT
                    id,
                    status,
                    severity,
                    owner
                FROM incidents
                WHERE id = :incident_id
                FOR UPDATE;
            """),
            {"incident_id": incident_id},
        ).fetchone()

        if current is None:
            return None

        if current.status == target_status:
            raise ValueError(
                f"Incident is already {target_status}"
            )

        if current.status == "resolved" and target_status != "open":
            raise ValueError(
                "Resolved incidents must be reopened before another transition"
            )

        acknowledged_sql = (
            "COALESCE(acknowledged_at, NOW())"
            if target_status == "investigating"
            else "acknowledged_at"
        )

        mitigated_sql = (
            "COALESCE(mitigated_at, NOW())"
            if target_status == "mitigated"
            else "mitigated_at"
        )

        resolved_sql = (
            "NOW()"
            if target_status == "resolved"
            else (
                "NULL"
                if target_status == "open"
                else "resolved_at"
            )
        )

        resolution_note_sql = (
            ":note"
            if target_status == "resolved"
            else (
                "NULL"
                if target_status == "open"
                else "resolution_note"
            )
        )

        conn.execute(
            text(f"""
                UPDATE incidents
                SET
                    status = :target_status,
                    acknowledged_at = {acknowledged_sql},
                    mitigated_at = {mitigated_sql},
                    resolved_at = {resolved_sql},
                    resolution_note = {resolution_note_sql},
                    updated_at = NOW()
                WHERE id = :incident_id;
            """),
            {
                "target_status": target_status,
                "note": note,
                "incident_id": incident_id,
            },
        )

        action_map = {
            "open": "REOPENED",
            "investigating": "ACKNOWLEDGED",
            "mitigated": "MITIGATED",
            "resolved": "MANUALLY_RESOLVED",
        }

        add_incident_history_event(
            conn,
            incident_id,
            action=action_map[target_status],
            from_status=current.status,
            to_status=target_status,
            severity=current.severity,
            owner=current.owner,
            note=note,
            changed_by=changed_by,
        )

        return get_incident(conn, incident_id)


def assign_incident(
    engine,
    incident_id,
    owner,
    changed_by="operator",
    note=None,
):
    clean_owner = str(owner or "").strip()

    if not clean_owner:
        raise ValueError("Owner cannot be empty")

    with engine.begin() as conn:
        current = conn.execute(
            text("""
                SELECT
                    id,
                    status,
                    severity,
                    owner
                FROM incidents
                WHERE id = :incident_id
                FOR UPDATE;
            """),
            {"incident_id": incident_id},
        ).fetchone()

        if current is None:
            return None

        conn.execute(
            text("""
                UPDATE incidents
                SET
                    owner = :owner,
                    updated_at = NOW()
                WHERE id = :incident_id;
            """),
            {
                "owner": clean_owner,
                "incident_id": incident_id,
            },
        )

        add_incident_history_event(
            conn,
            incident_id,
            action="ASSIGNED",
            from_status=current.status,
            to_status=current.status,
            severity=current.severity,
            owner=clean_owner,
            note=note,
            changed_by=changed_by,
        )

        return get_incident(conn, incident_id)


def escalate_incident(
    engine,
    incident_id,
    changed_by="operator",
    note=None,
):
    with engine.begin() as conn:
        current = conn.execute(
            text("""
                SELECT
                    id,
                    status,
                    severity,
                    owner
                FROM incidents
                WHERE id = :incident_id
                FOR UPDATE;
            """),
            {"incident_id": incident_id},
        ).fetchone()

        if current is None:
            return None

        new_severity = next_severity(current.severity)

        if new_severity == current.severity:
            raise ValueError("Incident is already critical")

        conn.execute(
            text("""
                UPDATE incidents
                SET
                    severity = :severity,
                    updated_at = NOW()
                WHERE id = :incident_id;
            """),
            {
                "severity": new_severity,
                "incident_id": incident_id,
            },
        )

        add_incident_history_event(
            conn,
            incident_id,
            action="ESCALATED",
            from_status=current.status,
            to_status=current.status,
            severity=new_severity,
            owner=current.owner,
            note=(
                note
                or f"Severity escalated from {current.severity} to {new_severity}."
            ),
            changed_by=changed_by,
        )

        return get_incident(conn, incident_id)


def incident_metrics(engine, hours=168):
    hours = max(1, min(int(hours), 24 * 365))

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT
                    COUNT(*) FILTER (
                        WHERE created_at >= NOW() - make_interval(hours => :hours)
                    )::integer AS incidents_created,
                    COUNT(*) FILTER (
                        WHERE status != 'resolved'
                    )::integer AS open_incidents,
                    COUNT(*) FILTER (
                        WHERE status != 'resolved'
                          AND severity = 'critical'
                    )::integer AS critical_open_incidents,
                    COUNT(*) FILTER (
                        WHERE status = 'resolved'
                          AND resolved_at >= NOW() - make_interval(hours => :hours)
                    )::integer AS incidents_resolved,
                    AVG(
                        EXTRACT(
                            EPOCH FROM (
                                acknowledged_at - created_at
                            )
                        ) / 60.0
                    ) FILTER (
                        WHERE acknowledged_at IS NOT NULL
                          AND created_at >= NOW() - make_interval(hours => :hours)
                    ) AS mtta_minutes,
                    AVG(
                        EXTRACT(
                            EPOCH FROM (
                                resolved_at - created_at
                            )
                        ) / 60.0
                    ) FILTER (
                        WHERE resolved_at IS NOT NULL
                          AND resolved_at >= NOW() - make_interval(hours => :hours)
                    ) AS mttr_minutes
                FROM incidents;
            """),
            {"hours": hours},
        ).fetchone()

        severity_rows = conn.execute(
            text("""
                SELECT
                    severity,
                    COUNT(*)::integer AS count
                FROM incidents
                WHERE status != 'resolved'
                GROUP BY severity;
            """)
        ).fetchall()

        status_rows = conn.execute(
            text("""
                SELECT
                    status,
                    COUNT(*)::integer AS count
                FROM incidents
                GROUP BY status;
            """)
        ).fetchall()

    return {
        "source": SOURCE,
        "external": EXTERNAL,
        "window_hours": hours,
        "incidents_created": row.incidents_created or 0,
        "open_incidents": row.open_incidents or 0,
        "critical_open_incidents": row.critical_open_incidents or 0,
        "incidents_resolved": row.incidents_resolved or 0,
        "mtta_minutes": round(float(row.mtta_minutes), 2)
            if row.mtta_minutes is not None else None,
        "mttr_minutes": round(float(row.mttr_minutes), 2)
            if row.mttr_minutes is not None else None,
        "by_severity": {
            item.severity: item.count
            for item in severity_rows
        },
        "by_status": {
            item.status: item.count
            for item in status_rows
        },
        "generated_at": utc_now().isoformat(),
    }
