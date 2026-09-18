#!/usr/bin/env bash

set -u
set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API="${GEO_API_URL:-http://localhost:8000}"
FRONTEND="${GEO_FRONTEND_URL:-http://localhost:8080}"

PASS=0
FAIL=0
WARN=0

pass() {
    echo "✅ PASS: $1"
    PASS=$((PASS + 1))
}

fail() {
    echo "❌ FAIL: $1"
    FAIL=$((FAIL + 1))
}

warn() {
    echo "⚠️  WARN: $1"
    WARN=$((WARN + 1))
}

section() {
    echo
    echo "========================================================================"
    echo "$1"
    echo "========================================================================"
}

run_check() {
    local label="$1"
    shift

    if "$@"; then
        pass "$label"
        return 0
    else
        fail "$label"
        return 1
    fi
}

http_check() {
    local path="$1"
    local expected="${2:-200}"
    local body
    local code

    body="$(mktemp)"

    code="$(
        curl -sS \
            --connect-timeout 5 \
            --max-time 20 \
            -o "$body" \
            -w '%{http_code}' \
            "$API$path"
    )" || code="000"

    if [[ "$code" == "$expected" ]]; then
        pass "$path returns HTTP $code"
    else
        fail "$path returned HTTP $code; expected $expected"
        cat "$body"
        echo
    fi

    rm -f "$body"
}

section "1. GIT / SAFETY"

echo "Branch: $(git branch --show-current)"
git status --short || true

section "2. SYNTAX"

run_check \
    "backend/main.py compiles" \
    python3 -m py_compile backend/main.py

run_check \
    "anomaly_engine.py compiles" \
    python3 -m py_compile backend/anomaly_engine.py

run_check \
    "prediction_engine.py compiles" \
    python3 -m py_compile backend/prediction_engine.py

run_check \
    "predictive_risk_engine.py compiles" \
    python3 -m py_compile backend/predictive_risk_engine.py

run_check \
    "frontend/app.js syntax is valid" \
    node --check frontend/app.js

run_check \
    "browser verification script compiles" \
    python3 -m py_compile scripts/browser_verify_phase_7_0_e.py

section "3. PHASE 7.0E MARKERS"

if grep -q 'predictiveOperationsSection' frontend/index.html; then
    pass "Predictive Operations DOM marker exists"
else
    fail "predictiveOperationsSection missing from frontend/index.html"
fi

if grep -q 'PHASE 7.0' frontend/index.html; then
    pass "Phase 7 marker exists in index.html"
else
    fail "Phase 7 marker missing from index.html"
fi

if grep -q 'PHASE 7.0' frontend/app.js; then
    pass "Phase 7 marker exists in app.js"
else
    fail "Phase 7 marker missing from app.js"
fi

if grep -q 'PHASE 7.0' frontend/style.css; then
    pass "Phase 7 marker exists in style.css"
else
    fail "Phase 7 marker missing from style.css"
fi

COUNT="$(
    grep -o 'id="predictiveOperationsSection"' frontend/index.html |
    wc -l
)"

if [[ "$COUNT" -eq 1 ]]; then
    pass "Predictive Operations section occurs exactly once"
else
    fail "predictiveOperationsSection occurs $COUNT times"
fi

section "4. DOCKER REBUILD"

if docker compose up -d --build backend frontend; then
    pass "Backend/frontend Docker rebuild completed"
else
    fail "Docker rebuild failed"
fi

echo
docker compose ps

section "5. SERVICE READINESS"

BACKEND_READY=0

for attempt in $(seq 1 30); do
    if curl -fsS \
        --connect-timeout 2 \
        --max-time 5 \
        "$API/health" >/dev/null 2>&1; then
        BACKEND_READY=1
        break
    fi

    sleep 2
done

if [[ "$BACKEND_READY" -eq 1 ]]; then
    pass "Backend became ready"
else
    fail "Backend did not become ready"
fi

FRONTEND_READY=0

for attempt in $(seq 1 30); do
    if curl -fsS \
        --connect-timeout 2 \
        --max-time 5 \
        "$FRONTEND" >/dev/null 2>&1; then
        FRONTEND_READY=1
        break
    fi

    sleep 2
done

if [[ "$FRONTEND_READY" -eq 1 ]]; then
    pass "Frontend became ready"
else
    fail "Frontend did not become ready"
fi

section "6. CORE REGRESSION ENDPOINTS"

http_check "/health"
http_check "/locations"
http_check "/sensor-telemetry"
http_check "/sensor-health"
http_check "/alerts"
http_check "/analytics"

section "7. PHASE 6.8 / SRE REGRESSION"

http_check "/incidents?limit=250"
http_check "/sre/intelligence?hours=168"
http_check "/sre/sla-status?limit=250"
http_check "/sre/priority-policy"

section "8. PHASE 6.9 REGRESSION"

http_check "/automation/runbooks"
http_check "/automation/executions"
http_check "/automation/summary"
http_check "/reliability/objectives"
http_check "/reliability/measurements"
http_check "/reliability/summary"

section "9. PHASE 7 PREDICTIVE ENDPOINTS"

http_check "/predictive/summary"
http_check "/anomaly-events"

# Discover an actual infrastructure asset instead of hard-coding one.
ASSET_ID="$(
python3 - <<PY
import json
import urllib.request

try:
    with urllib.request.urlopen("$API/locations", timeout=10) as response:
        body = json.load(response)

    if isinstance(body, list) and body:
        print(body[0].get("id", ""))

    elif isinstance(body, dict):
        for key in ("locations", "items", "results", "data"):
            value = body.get(key)
            if isinstance(value, list) and value:
                print(value[0].get("id", ""))
                break
except Exception:
    pass
PY
)"

if [[ -n "$ASSET_ID" ]]; then
    echo "Using infrastructure asset: $ASSET_ID"

    http_check "/predictive/anomalies/$ASSET_ID"
    http_check "/predictive/trends/$ASSET_ID"
    http_check "/predictive/risk/$ASSET_ID"
else
    fail "Could not discover infrastructure asset ID from /locations"
fi

section "10. PHASE 7.0D BACKEND REGRESSION"

if [[ -f scripts/verify_phase_7_0_d.py ]]; then
    if python3 scripts/verify_phase_7_0_d.py; then
        pass "Phase 7.0D backend regression suite passed"
    else
        fail "Phase 7.0D backend regression suite failed"
    fi
else
    warn "scripts/verify_phase_7_0_d.py not found"
fi

section "11. PHASE 6.9 BACKEND REGRESSION"

if [[ -f scripts/verify_phase_6_9_d.py ]]; then
    if python3 scripts/verify_phase_6_9_d.py; then
        pass "Phase 6.9 backend regression suite passed"
    else
        fail "Phase 6.9 backend regression suite failed"
    fi
else
    warn "scripts/verify_phase_6_9_d.py not found"
fi

section "12. AUTOMATED BROWSER REGRESSION"

if python3 -c 'import playwright' >/dev/null 2>&1; then
    if GEO_FRONTEND_URL="$FRONTEND" \
        python3 scripts/browser_verify_phase_7_0_e.py; then
        pass "Phase 7.0E automated browser regression passed"
    else
        fail "Phase 7.0E automated browser regression failed"
    fi
else
    fail "Python Playwright package is not installed"
fi

section "13. CONTAINER HEALTH"

BAD_CONTAINERS="$(
    docker compose ps --format json 2>/dev/null |
    python3 -c '
import json
import sys

bad = []

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue

    try:
        item = json.loads(line)
    except Exception:
        continue

    state = str(item.get("State", "")).lower()
    name = item.get("Name") or item.get("Service") or "unknown"

    if state not in ("running", ""):
        bad.append(f"{name}:{state}")

print(",".join(bad))
'
)"

if [[ -z "$BAD_CONTAINERS" ]]; then
    pass "Compose containers report running state"
else
    fail "Non-running containers detected: $BAD_CONTAINERS"
fi

section "PHASE 7.0E COMPLETE RESULT"

echo "Passed   : $PASS"
echo "Failed   : $FAIL"
echo "Warnings : $WARN"
echo
echo "Browser evidence:"
echo "  /tmp/phase_7_0_e_browser/dashboard-full.png"
echo "  /tmp/phase_7_0_e_browser/phase-7-0-e.png"
echo

if [[ "$FAIL" -eq 0 ]]; then
    echo "✅ PHASE 7.0E COMPLETE VALIDATION PASSED"
    exit 0
else
    echo "❌ PHASE 7.0E COMPLETE VALIDATION FAILED"
    echo
    echo "Do not commit/push Phase 7.0E yet."
    exit 1
fi
