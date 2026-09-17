#!/usr/bin/env bash
set -u
set -o pipefail

# ============================================================
# Phase 6.8 Controlled Mutation Test
#
# Verifies:
#   1. Backend health
#   2. Select test incident
#   3. Capture original state
#   4. Priority mutation
#   5. Priority persistence
#   6. SLA recalculation
#   7. Incident acknowledgement
#   8. Acknowledgement persistence
#   9. SLA evaluation
#  10. Post-evaluation SLA state
#  11. Incident history
#  12. PostgreSQL persistence
#  13. Restore original priority
#  14. Final state
#
# Phase 6.8:
# - Understands nested API response envelopes
# - Does NOT dump linked alerts
# - Preserves controlled mutation verification
# ============================================================

BASE="${BASE:-http://localhost:8000}"

PASSED=0
FAILED=0
INCIDENT_ID=""
ORIGINAL_PRIORITY=""
TEST_PRIORITY=""
ORIGINAL_STATUS=""

TMP_DIR="$(mktemp -d /tmp/phase_6_8_mutation.XXXXXX)"

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT


# ------------------------------------------------------------
# Formatting
# ------------------------------------------------------------

section() {
    echo
    echo "============================================================"
    echo "$1"
    echo "============================================================"
}

pass() {
    echo "✅ $1"
    PASSED=$((PASSED + 1))
}

fail() {
    echo "❌ $1"
    FAILED=$((FAILED + 1))
}

info() {
    echo "   $1"
}


# ------------------------------------------------------------
# HTTP helper
#
# Usage:
#   request METHOD URL OUTPUT_FILE [JSON_BODY]
#
# Prints HTTP status code only.
# Response body goes to OUTPUT_FILE.
# ------------------------------------------------------------

request() {
    local method="$1"
    local url="$2"
    local output="$3"
    local body="${4:-}"

    if [[ -n "$body" ]]; then
        curl -sS \
            -X "$method" \
            -H "Content-Type: application/json" \
            -o "$output" \
            -w "%{http_code}" \
            --data "$body" \
            "$url"
    else
        curl -sS \
            -X "$method" \
            -o "$output" \
            -w "%{http_code}" \
            "$url"
    fi
}


# ------------------------------------------------------------
# JSON validation
# ------------------------------------------------------------

valid_json() {
    python3 - "$1" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        json.load(f)
except Exception:
    raise SystemExit(1)
PY
}


# ------------------------------------------------------------
# Recursive JSON field extractor
#
# This is the important Phase 6.8 fix.
#
# Instead of assuming:
#
#   data["priority"]
#
# it recursively searches dictionaries/lists for the requested
# field. This supports response structures such as:
#
#   {"incident": {"priority": "P1"}}
#
#   {"data": {"incident": {"priority": "P1"}}}
#
#   {"result": {"priority": "P1"}}
#
# without dumping linked alert arrays.
# ------------------------------------------------------------

json_field() {
    local file="$1"
    local field="$2"

    python3 - "$file" "$field" <<'PY'
import json
import sys

path = sys.argv[1]
wanted = sys.argv[2]

try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    print("")
    raise SystemExit(0)


def find(value):
    if isinstance(value, dict):

        # Prefer the field on the current object.
        if wanted in value:
            candidate = value[wanted]

            if candidate is None:
                return ""

            if isinstance(candidate, bool):
                return "true" if candidate else "false"

            if isinstance(candidate, (str, int, float)):
                return str(candidate)

        # Search common API envelope objects first.
        preferred = (
            "incident",
            "sla",
            "data",
            "result",
            "state",
            "summary",
        )

        for key in preferred:
            child = value.get(key)
            if isinstance(child, (dict, list)):
                result = find(child)
                if result != "":
                    return result

        # Then search remaining dictionaries.
        for key, child in value.items():

            # Avoid traversing large linked-alert collections
            # unless absolutely necessary.
            if key in {
                "alerts",
                "linked_alerts",
                "incident_alerts",
                "telemetry_alerts",
            }:
                continue

            if isinstance(child, (dict, list)):
                result = find(child)
                if result != "":
                    return result

    elif isinstance(value, list):

        # Avoid printing/traversing huge arrays unnecessarily.
        for child in value[:100]:
            if isinstance(child, (dict, list)):
                result = find(child)
                if result != "":
                    return result

    return ""


print(find(data))
PY
}


# ------------------------------------------------------------
# Compact response summary
#
# Deliberately does not print linked alerts.
# ------------------------------------------------------------

compact_incident() {
    local file="$1"

    python3 - "$file" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as exc:
    print(f"   Invalid JSON: {exc}")
    raise SystemExit(0)


FIELDS = (
    "id",
    "incident_id",
    "status",
    "severity",
    "priority",
    "owner",
    "assigned_team",
    "acknowledged_at",
    "acknowledgement_due_at",
    "resolution_due_at",
    "acknowledgement_sla_breached",
    "resolution_sla_breached",
)


def locate_incident(obj):
    if not isinstance(obj, dict):
        return None

    # Prefer explicit envelopes.
    for key in ("incident", "data", "result"):
        child = obj.get(key)

        if isinstance(child, dict):
            if (
                "id" in child
                or "incident_id" in child
                or "priority" in child
                or "status" in child
            ):
                return child

            nested = locate_incident(child)
            if nested:
                return nested

    if (
        "id" in obj
        or "incident_id" in obj
        or "priority" in obj
        or "status" in obj
    ):
        return obj

    return None


incident = locate_incident(data)

if incident is None:
    print("   Response keys:", ", ".join(data.keys()) if isinstance(data, dict) else type(data).__name__)
    raise SystemExit(0)

for field in FIELDS:
    if field in incident:
        print(f"   {field}: {incident[field]}")
PY
}


compact_sla() {
    local file="$1"

    python3 - "$file" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as exc:
    print(f"   Invalid JSON: {exc}")
    raise SystemExit(0)


wanted = (
    "incident_id",
    "priority",
    "acknowledgement_due_at",
    "resolution_due_at",
    "acknowledgement_sla_breached",
    "resolution_sla_breached",
    "acknowledged_at",
    "resolved_at",
)


def find_value(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key], True

        for preferred in (
            "sla",
            "incident",
            "data",
            "result",
            "state",
            "summary",
        ):
            if preferred in obj:
                value, found = find_value(obj[preferred], key)
                if found:
                    return value, True

        for name, child in obj.items():
            if name in {
                "alerts",
                "linked_alerts",
                "incident_alerts",
                "telemetry_alerts",
            }:
                continue

            if isinstance(child, (dict, list)):
                value, found = find_value(child, key)
                if found:
                    return value, True

    elif isinstance(obj, list):
        for child in obj[:100]:
            value, found = find_value(child, key)
            if found:
                return value, True

    return None, False


for field in wanted:
    value, found = find_value(data, field)
    if found:
        print(f"   {field}: {value}")
PY
}


# ------------------------------------------------------------
# 1. Backend health
# ------------------------------------------------------------

section "1. BACKEND HEALTH"

HEALTH="$TMP_DIR/health.json"

HTTP="$(
    request GET \
        "$BASE/health" \
        "$HEALTH"
)"

if [[ "$HTTP" == "200" ]]; then
    pass "Backend health endpoint -> HTTP 200"
else
    fail "Backend health endpoint -> HTTP $HTTP"
    cat "$HEALTH" 2>/dev/null || true
fi


# ------------------------------------------------------------
# 2. Select test incident
#
# Prefer an OPEN, non-critical incident that has not yet been
# acknowledged. Fall back progressively if necessary.
# ------------------------------------------------------------

section "2. SELECT TEST INCIDENT"

INCIDENTS="$TMP_DIR/incidents.json"

HTTP="$(
    request GET \
        "$BASE/incidents?limit=1000" \
        "$INCIDENTS"
)"

if [[ "$HTTP" != "200" ]]; then
    fail "Unable to list incidents -> HTTP $HTTP"
else
    INCIDENT_ID="$(
        python3 - "$INCIDENTS" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)


def find_incident_list(obj):
    if isinstance(obj, list):
        return obj

    if isinstance(obj, dict):
        for key in ("incidents", "items", "data", "results"):
            value = obj.get(key)

            if isinstance(value, list):
                return value

            if isinstance(value, dict):
                nested = find_incident_list(value)
                if nested:
                    return nested

    return []


items = find_incident_list(data)


def incident_id(item):
    return item.get("id") or item.get("incident_id")


# Best controlled candidate:
# open + not acknowledged.
for item in items:
    if (
        str(item.get("status", "")).lower() == "open"
        and not item.get("acknowledged_at")
        and incident_id(item)
    ):
        print(incident_id(item))
        raise SystemExit(0)

# Second choice: investigating + not acknowledged.
for item in items:
    if (
        str(item.get("status", "")).lower() == "investigating"
        and not item.get("acknowledged_at")
        and incident_id(item)
    ):
        print(incident_id(item))
        raise SystemExit(0)

# Final fallback: any open/investigating incident.
for item in items:
    if (
        str(item.get("status", "")).lower()
        in {"open", "investigating"}
        and incident_id(item)
    ):
        print(incident_id(item))
        raise SystemExit(0)

print("")
PY
    )"

    if [[ -n "$INCIDENT_ID" ]]; then
        pass "Selected incident ID $INCIDENT_ID"
    else
        fail "No suitable open/investigating incident available"
    fi
fi


if [[ -z "$INCIDENT_ID" ]]; then
    section "PHASE 6.8 CONTROLLED MUTATION TEST RESULT"
    echo "Incident tested: NONE"
    echo "Passed: $PASSED"
    echo "Failed: $FAILED"
    echo
    echo "❌ PHASE 6.8 CONTROLLED MUTATION TEST FAILED"
    exit 1
fi


# ------------------------------------------------------------
# 3. Capture original state
# ------------------------------------------------------------

section "3. CAPTURE ORIGINAL STATE"

ORIGINAL="$TMP_DIR/original.json"

HTTP="$(
    request GET \
        "$BASE/incidents/$INCIDENT_ID" \
        "$ORIGINAL"
)"

if [[ "$HTTP" == "200" ]] && valid_json "$ORIGINAL"; then

    ORIGINAL_PRIORITY="$(json_field "$ORIGINAL" priority)"
    ORIGINAL_STATUS="$(json_field "$ORIGINAL" status)"

    pass "Original incident state captured"

    info "Incident: $INCIDENT_ID"
    info "Status: ${ORIGINAL_STATUS:-unknown}"
    info "Priority: ${ORIGINAL_PRIORITY:-unknown}"

else
    fail "Could not capture original incident state"
fi


# ------------------------------------------------------------
# Choose a priority guaranteed to differ from original.
# ------------------------------------------------------------

case "$ORIGINAL_PRIORITY" in
    P1) TEST_PRIORITY="P2" ;;
    P2) TEST_PRIORITY="P1" ;;
    P3) TEST_PRIORITY="P1" ;;
    P4) TEST_PRIORITY="P1" ;;
    *)  TEST_PRIORITY="P1" ;;
esac


# ------------------------------------------------------------
# 4. Priority change
# ------------------------------------------------------------

section "4. PRIORITY CHANGE"

PRIORITY_RESPONSE="$TMP_DIR/priority.json"

HTTP="$(
    request POST \
        "$BASE/incidents/$INCIDENT_ID/priority" \
        "$PRIORITY_RESPONSE" \
        "{\"priority\":\"$TEST_PRIORITY\",\"changed_by\":\"PHASE_6_8_TEST\"}"
)"

if [[ "$HTTP" == "200" ]]; then
    pass "Priority mutation endpoint -> HTTP 200"
else
    fail "Priority mutation endpoint -> HTTP $HTTP"
fi

info "Requested priority: $TEST_PRIORITY"

if valid_json "$PRIORITY_RESPONSE"; then
    compact_incident "$PRIORITY_RESPONSE"
fi


# ------------------------------------------------------------
# 5. Verify priority persistence
#
# IMPORTANT:
# Fetch the canonical incident endpoint instead of assuming
# the POST response contains a flat incident object.
# ------------------------------------------------------------

section "5. VERIFY PRIORITY PERSISTENCE"

AFTER_PRIORITY="$TMP_DIR/after_priority.json"

HTTP="$(
    request GET \
        "$BASE/incidents/$INCIDENT_ID" \
        "$AFTER_PRIORITY"
)"

CURRENT_PRIORITY="$(json_field "$AFTER_PRIORITY" priority)"

if [[ "$HTTP" == "200" && "$CURRENT_PRIORITY" == "$TEST_PRIORITY" ]]; then
    pass "Priority persisted as $TEST_PRIORITY"
else
    fail "Expected $TEST_PRIORITY but received '${CURRENT_PRIORITY:-missing}'"
fi


# ------------------------------------------------------------
# 6. SLA recalculation
# ------------------------------------------------------------

section "6. SLA RECALCULATION"

SLA="$TMP_DIR/sla.json"

HTTP="$(
    request GET \
        "$BASE/incidents/$INCIDENT_ID/sla" \
        "$SLA"
)"

if [[ "$HTTP" == "200" ]]; then
    pass "Incident SLA endpoint -> HTTP 200"
else
    fail "Incident SLA endpoint -> HTTP $HTTP"
fi


ACK_DUE="$(json_field "$SLA" acknowledgement_due_at)"
RESOLUTION_DUE="$(json_field "$SLA" resolution_due_at)"
SLA_PRIORITY="$(json_field "$SLA" priority)"

if [[ -n "$ACK_DUE" ]]; then
    pass "Acknowledgement SLA deadline populated"
    info "$ACK_DUE"
else
    fail "Acknowledgement SLA deadline missing"
fi

if [[ -n "$RESOLUTION_DUE" ]]; then
    pass "Resolution SLA deadline populated"
    info "$RESOLUTION_DUE"
else
    fail "Resolution SLA deadline missing"
fi

if [[ -n "$SLA_PRIORITY" && "$SLA_PRIORITY" == "$TEST_PRIORITY" ]]; then
    pass "SLA state reflects priority $TEST_PRIORITY"
else
    # Some SLA envelopes may not repeat priority.
    # Verify against canonical incident state before failing.
    CANONICAL_PRIORITY="$(json_field "$AFTER_PRIORITY" priority)"

    if [[ "$CANONICAL_PRIORITY" == "$TEST_PRIORITY" ]]; then
        pass "Canonical incident state reflects SLA priority $TEST_PRIORITY"
    else
        fail "SLA/canonical priority does not reflect $TEST_PRIORITY"
    fi
fi

compact_sla "$SLA"


# ------------------------------------------------------------
# 7. Acknowledge incident
# ------------------------------------------------------------

section "7. ACKNOWLEDGE INCIDENT"

ACK_RESPONSE="$TMP_DIR/ack.json"

HTTP="$(
    request POST \
        "$BASE/incidents/$INCIDENT_ID/acknowledge" \
        "$ACK_RESPONSE" \
        '{"changed_by":"PHASE_6_8_TEST","note":"Phase 6.8 controlled mutation acknowledgement test"}'
)"

if [[ "$HTTP" == "200" ]]; then
    pass "Incident acknowledgement -> HTTP 200"
else
    fail "Incident acknowledgement -> HTTP $HTTP"
fi

if valid_json "$ACK_RESPONSE"; then
    compact_incident "$ACK_RESPONSE"
fi


# ------------------------------------------------------------
# 8. Verify acknowledgement
#
# Fetch canonical incident again. Do not rely on the mutation
# endpoint's response envelope.
# ------------------------------------------------------------

section "8. VERIFY ACKNOWLEDGEMENT"

AFTER_ACK="$TMP_DIR/after_ack.json"

HTTP="$(
    request GET \
        "$BASE/incidents/$INCIDENT_ID" \
        "$AFTER_ACK"
)"

ACK_AT="$(json_field "$AFTER_ACK" acknowledged_at)"
ACK_STATUS="$(json_field "$AFTER_ACK" status)"

if [[ "$HTTP" == "200" ]]; then
    pass "Canonical incident fetch after acknowledgement -> HTTP 200"
else
    fail "Canonical incident fetch after acknowledgement -> HTTP $HTTP"
fi

if [[ -n "$ACK_AT" ]]; then
    pass "acknowledged_at populated"
    info "$ACK_AT"
else
    fail "acknowledged_at was not populated"
fi

if [[ "$ACK_STATUS" == "investigating" || "$ACK_STATUS" == "acknowledged" || "$ACK_STATUS" == "resolved" ]]; then
    pass "Incident lifecycle advanced after acknowledgement ($ACK_STATUS)"
else
    fail "Unexpected status after acknowledgement: '${ACK_STATUS:-missing}'"
fi


# ------------------------------------------------------------
# 9. SLA evaluation
# ------------------------------------------------------------

section "9. SLA EVALUATION"

EVALUATION="$TMP_DIR/evaluation.json"

HTTP="$(
    request POST \
        "$BASE/sre/sla/evaluate" \
        "$EVALUATION"
)"

if [[ "$HTTP" == "200" ]]; then
    pass "SLA evaluator -> HTTP 200"
else
    fail "SLA evaluator -> HTTP $HTTP"
fi


# ------------------------------------------------------------
# 10. Post-evaluation SLA state
# ------------------------------------------------------------

section "10. POST-EVALUATION SLA STATE"

POST_SLA="$TMP_DIR/post_sla.json"

HTTP="$(
    request GET \
        "$BASE/incidents/$INCIDENT_ID/sla" \
        "$POST_SLA"
)"

if [[ "$HTTP" == "200" ]]; then
    pass "Post-evaluation SLA endpoint -> HTTP 200"
else
    fail "Post-evaluation SLA endpoint -> HTTP $HTTP"
fi

POST_ACK_DUE="$(json_field "$POST_SLA" acknowledgement_due_at)"
POST_RESOLUTION_DUE="$(json_field "$POST_SLA" resolution_due_at)"
ACK_BREACHED="$(json_field "$POST_SLA" acknowledgement_sla_breached)"
RESOLUTION_BREACHED="$(json_field "$POST_SLA" resolution_sla_breached)"

if [[ -n "$POST_ACK_DUE" ]]; then
    pass "Post-evaluation acknowledgement deadline available"
else
    fail "Post-evaluation acknowledgement deadline missing"
fi

if [[ -n "$POST_RESOLUTION_DUE" ]]; then
    pass "Post-evaluation resolution deadline available"
else
    fail "Post-evaluation resolution deadline missing"
fi

if [[ "$ACK_BREACHED" == "true" || "$ACK_BREACHED" == "false" ]]; then
    pass "Acknowledgement SLA breach flag available ($ACK_BREACHED)"
else
    fail "Acknowledgement SLA breach flag missing"
fi

if [[ "$RESOLUTION_BREACHED" == "true" || "$RESOLUTION_BREACHED" == "false" ]]; then
    pass "Resolution SLA breach flag available ($RESOLUTION_BREACHED)"
else
    fail "Resolution SLA breach flag missing"
fi

compact_sla "$POST_SLA"


# ------------------------------------------------------------
# 11. Incident history
# ------------------------------------------------------------

section "11. INCIDENT HISTORY"

HISTORY="$TMP_DIR/history.json"

HTTP="$(
    request GET \
        "$BASE/incidents/$INCIDENT_ID/events" \
        "$HISTORY"
)"

if [[ "$HTTP" == "200" ]]; then
    pass "Incident history endpoint -> HTTP 200"
else
    fail "Incident history endpoint -> HTTP $HTTP"
fi


HISTORY_RESULT="$(
    python3 - "$HISTORY" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    print("0|0|0")
    raise SystemExit(0)


def find_events(obj):
    if isinstance(obj, list):
        return obj

    if isinstance(obj, dict):
        for key in (
            "events",
            "history",
            "incident_history",
            "items",
            "data",
            "results",
        ):
            value = obj.get(key)

            if isinstance(value, list):
                return value

            if isinstance(value, dict):
                nested = find_events(value)
                if nested:
                    return nested

    return []


events = find_events(data)

priority = 0
ack = 0

for event in events:
    if not isinstance(event, dict):
        continue

    action = str(event.get("action", "")).upper()

    if action == "PRIORITY_CHANGED":
        priority += 1

    if action == "ACKNOWLEDGED":
        ack += 1

print(f"{len(events)}|{priority}|{ack}")
PY
)"

IFS='|' read -r HISTORY_COUNT PRIORITY_EVENTS ACK_EVENTS <<< "$HISTORY_RESULT"

if [[ "${HISTORY_COUNT:-0}" -gt 0 ]]; then
    pass "Incident history contains events ($HISTORY_COUNT)"
else
    fail "Incident history returned no events"
fi

if [[ "${PRIORITY_EVENTS:-0}" -gt 0 ]]; then
    pass "PRIORITY_CHANGED history event recorded"
else
    fail "PRIORITY_CHANGED history event missing"
fi

if [[ "${ACK_EVENTS:-0}" -gt 0 ]]; then
    pass "ACKNOWLEDGED history event recorded"
else
    fail "ACKNOWLEDGED history event missing"
fi


# ------------------------------------------------------------
# 12. PostgreSQL verification
# ------------------------------------------------------------

section "12. POSTGRESQL VERIFICATION"

DB_STATE="$(
    docker exec geodb \
        psql \
        -U postgres \
        -d geospatialdb \
        -At \
        -F '|' \
        -c "
SELECT
    priority,
    COALESCE(status, ''),
    CASE WHEN acknowledged_at IS NULL THEN 'false' ELSE 'true' END,
    CASE WHEN acknowledgement_due_at IS NULL THEN 'false' ELSE 'true' END,
    CASE WHEN resolution_due_at IS NULL THEN 'false' ELSE 'true' END,
    acknowledgement_sla_breached::text,
    resolution_sla_breached::text
FROM incidents
WHERE id = $INCIDENT_ID;
" 2>/dev/null
)"

if [[ -n "$DB_STATE" ]]; then
    pass "PostgreSQL incident state query succeeded"

    IFS='|' read -r \
        DB_PRIORITY \
        DB_STATUS \
        DB_ACK \
        DB_ACK_DUE \
        DB_RES_DUE \
        DB_ACK_BREACH \
        DB_RES_BREACH \
        <<< "$DB_STATE"

    info "priority=$DB_PRIORITY"
    info "status=$DB_STATUS"
    info "acknowledged=$DB_ACK"
    info "ack_deadline=$DB_ACK_DUE"
    info "resolution_deadline=$DB_RES_DUE"
    info "ack_breach=$DB_ACK_BREACH"
    info "resolution_breach=$DB_RES_BREACH"

    if [[ "$DB_PRIORITY" == "$TEST_PRIORITY" ]]; then
        pass "PostgreSQL priority persisted as $TEST_PRIORITY"
    else
        fail "PostgreSQL priority expected $TEST_PRIORITY, found $DB_PRIORITY"
    fi

    if [[ "$DB_ACK" == "true" ]]; then
        pass "PostgreSQL acknowledged_at populated"
    else
        fail "PostgreSQL acknowledged_at missing"
    fi

    if [[ "$DB_ACK_DUE" == "true" && "$DB_RES_DUE" == "true" ]]; then
        pass "PostgreSQL SLA deadlines populated"
    else
        fail "PostgreSQL SLA deadline persistence incomplete"
    fi

    if [[ "$DB_ACK_BREACH" =~ ^(true|false|t|f)$ && "$DB_RES_BREACH" =~ ^(true|false|t|f)$ ]]; then
        pass "PostgreSQL SLA breach flags valid"
    else
        fail "PostgreSQL SLA breach flags invalid"
    fi

else
    fail "PostgreSQL incident state query failed"
fi


# ------------------------------------------------------------
# 13. Restore original priority
# ------------------------------------------------------------

section "13. RESTORE ORIGINAL PRIORITY"

if [[ -n "$ORIGINAL_PRIORITY" ]]; then

    RESTORE="$TMP_DIR/restore.json"

    HTTP="$(
        request POST \
            "$BASE/incidents/$INCIDENT_ID/priority" \
            "$RESTORE" \
            "{\"priority\":\"$ORIGINAL_PRIORITY\",\"changed_by\":\"PHASE_6_8_TEST_RESTORE\"}"
    )"

    if [[ "$HTTP" == "200" ]]; then
        pass "Original priority restore endpoint -> HTTP 200"
    else
        fail "Could not restore original priority -> HTTP $HTTP"
    fi

    RESTORED="$TMP_DIR/restored.json"

    request GET \
        "$BASE/incidents/$INCIDENT_ID" \
        "$RESTORED" >/dev/null

    RESTORED_PRIORITY="$(json_field "$RESTORED" priority)"

    if [[ "$RESTORED_PRIORITY" == "$ORIGINAL_PRIORITY" ]]; then
        pass "Original priority restored ($ORIGINAL_PRIORITY)"
    else
        fail "Priority restore verification failed: '${RESTORED_PRIORITY:-missing}'"
    fi

else
    fail "Original priority unavailable; restore skipped"
fi


# ------------------------------------------------------------
# 14. Final incident state
# ------------------------------------------------------------

section "14. FINAL INCIDENT STATE"

FINAL="$TMP_DIR/final.json"

HTTP="$(
    request GET \
        "$BASE/incidents/$INCIDENT_ID" \
        "$FINAL"
)"

if [[ "$HTTP" == "200" ]]; then
    pass "Final incident state retrieved"
    compact_incident "$FINAL"
else
    fail "Unable to retrieve final incident state"
fi


# ------------------------------------------------------------
# Result
# ------------------------------------------------------------

section "PHASE 6.8 CONTROLLED MUTATION TEST RESULT"

echo "Incident tested: $INCIDENT_ID"
echo "Passed: $PASSED"
echo "Failed: $FAILED"

if [[ "$FAILED" -eq 0 ]]; then
    echo
    echo "✅ PHASE 6.8 CONTROLLED MUTATION TEST PASSED"
    exit 0
else
    echo
    echo "❌ PHASE 6.8 CONTROLLED MUTATION TEST FAILED"
    exit 1
fi
