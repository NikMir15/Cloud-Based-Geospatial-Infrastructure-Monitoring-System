#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "frontend" / "index.html"
JS = ROOT / "frontend" / "app.js"
CSS = ROOT / "frontend" / "style.css"

FILES = (HTML, JS, CSS)

PHASE_MARKER = "PHASE 7.0E — PREDICTIVE OPERATIONS"


def fail(message):
    print(f"❌ {message}")
    sys.exit(1)


def replace_once(text, old, new, label):
    count = text.count(old)

    if count != 1:
        fail(
            f"{label}: expected exactly one anchor, "
            f"found {count}"
        )

    return text.replace(old, new, 1)


for path in FILES:
    if not path.exists():
        fail(f"Missing required file: {path}")


html = HTML.read_text(encoding="utf-8")
js = JS.read_text(encoding="utf-8")
css = CSS.read_text(encoding="utf-8")


# ------------------------------------------------------------
# Refuse duplicate integration
# ------------------------------------------------------------

if (
    "predictiveOperationsSection" in html
    or "phase70State" in js
    or ".phase70-section" in css
):
    fail(
        "Phase 7.0E markers already exist. "
        "Integration was not applied again."
    )


# ------------------------------------------------------------
# Validate Phase 6.9 / existing dashboard anchors
# ------------------------------------------------------------

required_html = [
    'data-scroll-target="automationReliabilitySection"',
    'data-scroll-target="analyticsSection"',
    'id="automationReliabilitySection"',
    '<footer class="dashboard-footer">',
]

for marker in required_html:
    if marker not in html:
        fail(f"Required HTML anchor missing: {marker}")


# ------------------------------------------------------------
# Backup
# ------------------------------------------------------------

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

backup_dir = Path(
    f"/tmp/geo-before-phase-7-0e-integration-{stamp}"
)

backup_dir.mkdir(parents=True, exist_ok=False)

for path in FILES:
    shutil.copy2(path, backup_dir / path.name)

print(f"✅ Backup: {backup_dir}")


# ============================================================
# HTML
# ============================================================

# Insert Predictive Ops immediately before Analytics.

analytics_nav_anchor = (
    '        <button class="nav-item" '
    'data-scroll-target="analyticsSection">'
)

predictive_nav = '''        <button class="nav-item" data-scroll-target="predictiveOperationsSection">
            <span class="nav-icon">⌁</span>
            <span>Predictive Ops</span>
        </button>

'''

html = replace_once(
    html,
    analytics_nav_anchor,
    predictive_nav + analytics_nav_anchor,
    "Predictive Ops sidebar insertion",
)


# Insert Phase 7 before existing footer.

footer_anchor = '    <footer class="dashboard-footer">'

phase70_html = r'''
    <!-- ==================================================
         PHASE 7.0E — PREDICTIVE OPERATIONS
         Additive UI only. Existing map and Phase 6.6–6.9
         sections remain unchanged.
         ================================================== -->
    <section
        class="dashboard-section phase70-section"
        id="predictiveOperationsSection"
    >
        <div class="phase70-heading">
            <div>
                <p class="eyebrow">
                    PHASE 7.0 · PREDICTIVE OPERATIONS
                </p>
                <h2>Predictive Infrastructure Intelligence</h2>
                <p>
                    Local telemetry anomaly detection, trend analysis
                    and operational risk prioritisation.
                </p>
            </div>

            <div class="phase70-heading-actions">
                <span
                    id="phase70RefreshStatus"
                    class="phase70-live-pill"
                >LIVE</span>

                <button
                    id="phase70RefreshButton"
                    class="neon-button subtle"
                    type="button"
                >
                    Refresh
                </button>
            </div>
        </div>

        <div class="phase70-kpi-grid">
            <article class="glass-card phase70-kpi-card">
                <span>Anomaly Events</span>
                <strong id="phase70AnomalyCount">—</strong>
                <small>Persisted predictive anomaly events</small>
            </article>

            <article class="glass-card phase70-kpi-card">
                <span>Affected Assets</span>
                <strong id="phase70AffectedAssets">—</strong>
                <small>Assets represented by anomaly events</small>
            </article>

            <article class="glass-card phase70-kpi-card">
                <span>Selected Risk</span>
                <strong id="phase70SelectedRisk">—</strong>
                <small>Operational risk score / 100</small>
            </article>

            <article class="glass-card phase70-kpi-card">
                <span>Risk Level</span>
                <strong id="phase70RiskLevel">—</strong>
                <small>Selected infrastructure risk classification</small>
            </article>
        </div>

        <article class="glass-card phase70-selector-card">
            <div>
                <span class="card-kicker">INFRASTRUCTURE ASSET</span>
                <h3>Predictive Analysis Target</h3>
            </div>

            <label class="phase70-select-wrap">
                <span>Asset</span>
                <select id="phase70AssetSelect">
                    <option value="">
                        Select infrastructure...
                    </option>
                </select>
            </label>
        </article>

        <div class="phase70-grid">
            <article class="glass-card phase70-panel">
                <div class="card-heading">
                    <div>
                        <span class="card-kicker">
                            ANOMALY DETECTION
                        </span>
                        <h2>Telemetry Anomalies</h2>
                    </div>

                    <span
                        id="phase70AnomalyBadge"
                        class="phase70-badge"
                    >WAITING</span>
                </div>

                <div
                    id="phase70AnomalyPanel"
                    class="phase70-content"
                >
                    <div class="empty-state">
                        Select an infrastructure asset.
                    </div>
                </div>
            </article>

            <article class="glass-card phase70-panel">
                <div class="card-heading">
                    <div>
                        <span class="card-kicker">
                            TREND PREDICTION
                        </span>
                        <h2>Telemetry Trends</h2>
                    </div>

                    <span
                        id="phase70TrendBadge"
                        class="phase70-badge"
                    >WAITING</span>
                </div>

                <div
                    id="phase70TrendPanel"
                    class="phase70-content"
                >
                    <div class="empty-state">
                        Select an infrastructure asset.
                    </div>
                </div>
            </article>
        </div>

        <div class="phase70-grid phase70-risk-grid">
            <article class="glass-card phase70-panel">
                <div class="card-heading">
                    <div>
                        <span class="card-kicker">
                            PREDICTIVE RISK
                        </span>
                        <h2>Operational Risk</h2>
                    </div>

                    <span
                        id="phase70RiskBadge"
                        class="phase70-badge"
                    >WAITING</span>
                </div>

                <div
                    id="phase70RiskPanel"
                    class="phase70-content"
                >
                    <div class="empty-state">
                        Select an infrastructure asset.
                    </div>
                </div>
            </article>

            <article class="glass-card phase70-panel">
                <div class="card-heading">
                    <div>
                        <span class="card-kicker">
                            PREDICTIVE EVENT HISTORY
                        </span>
                        <h2>Recent Anomaly Events</h2>
                    </div>

                    <span
                        id="phase70EventCount"
                        class="phase70-count"
                    >0 events</span>
                </div>

                <div
                    id="phase70EventList"
                    class="phase70-list"
                >
                    <div class="empty-state">
                        Loading anomaly events...
                    </div>
                </div>
            </article>
        </div>

        <div class="phase70-provenance">
            Predictive analysis uses project-local telemetry.
            Operational prioritisation heuristic only;
            not a guaranteed future prediction.
        </div>
    </section>

'''

html = replace_once(
    html,
    footer_anchor,
    phase70_html + footer_anchor,
    "Phase 7.0E dashboard section insertion",
)


# ============================================================
# JAVASCRIPT
# ============================================================

phase70_js = r'''

// ============================================================
// PHASE 7.0E — PREDICTIVE OPERATIONS
// Additive integration. Existing map / Phase 6.6–6.9 logic
// is intentionally left unchanged.
// ============================================================

const phase70State = {
    loading: false,
    selectedAssetId: null,
    refreshTimer: null,
    summary: null,
    events: null
};

function phase70El(id) {
    return document.getElementById(id);
}

function phase70Esc(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function phase70Num(value, fallback = 0) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
}

function phase70Array(body, keys = []) {
    if (Array.isArray(body)) return body;

    if (!body || typeof body !== "object") return [];

    for (const key of keys) {
        if (Array.isArray(body[key])) return body[key];
    }

    if (body.results && typeof body.results === "object") {
        for (const key of keys) {
            if (Array.isArray(body.results[key])) {
                return body.results[key];
            }
        }
    }

    return [];
}

function phase70Object(body, keys = []) {
    if (!body || typeof body !== "object") return {};

    for (const key of keys) {
        if (
            body[key] &&
            typeof body[key] === "object" &&
            !Array.isArray(body[key])
        ) {
            return body[key];
        }
    }

    return body;
}

async function phase70Fetch(path) {
    const response = await fetch(`${API_URL}${path}`, {
        cache: "no-store"
    });

    let body = {};

    try {
        body = await response.json();
    } catch (_) {
        body = {};
    }

    if (!response.ok) {
        throw new Error(
            `${path} returned HTTP ${response.status}`
        );
    }

    if (
        body &&
        typeof body === "object" &&
        "source" in body &&
        body.source !== "LOCAL_PROJECT"
    ) {
        console.warn(
            "[Phase 7.0E] Unexpected source:",
            path,
            body.source
        );
    }

    if (
        body &&
        typeof body === "object" &&
        "external" in body &&
        body.external !== false
    ) {
        console.warn(
            "[Phase 7.0E] Unexpected external flag:",
            path,
            body.external
        );
    }

    return body;
}

function phase70SetStatus(text, mode = "") {
    const el = phase70El("phase70RefreshStatus");
    if (!el) return;

    el.textContent = text;
    el.classList.remove("loading", "error");

    if (mode) el.classList.add(mode);
}

function phase70SetBadge(id, text, className = "") {
    const el = phase70El(id);
    if (!el) return;

    el.textContent = text || "UNKNOWN";
    el.className = "phase70-badge";

    if (className) {
        el.classList.add(className);
    }
}

function phase70SeverityClass(value) {
    const v = String(value || "").toUpperCase();

    if (
        v.includes("CRITICAL") ||
        v.includes("HIGH") ||
        v.includes("BREACH")
    ) {
        return "danger";
    }

    if (
        v.includes("WATCH") ||
        v.includes("MEDIUM") ||
        v.includes("WARN") ||
        v.includes("RISING")
    ) {
        return "warning";
    }

    if (
        v.includes("LOW") ||
        v.includes("NORMAL") ||
        v.includes("HEALTHY") ||
        v.includes("STABLE")
    ) {
        return "healthy";
    }

    return "";
}

function phase70PopulateAssets() {
    const select = phase70El("phase70AssetSelect");
    if (!select) return;

    const previous = String(
        phase70State.selectedAssetId ?? select.value ?? ""
    );

    let assets = [];

    if (
        typeof infrastructureData !== "undefined" &&
        Array.isArray(infrastructureData)
    ) {
        assets = infrastructureData;
    }

    select.innerHTML =
        '<option value="">Select infrastructure...</option>';

    assets.forEach((asset) => {
        if (asset?.id == null) return;

        const option = document.createElement("option");
        option.value = String(asset.id);
        option.textContent =
            asset.name || `Infrastructure ${asset.id}`;

        select.appendChild(option);
    });

    if (
        previous &&
        [...select.options].some(
            (option) => option.value === previous
        )
    ) {
        select.value = previous;
    }
}

function phase70RenderSummary(body) {
    phase70State.summary = body;

    const anomaly =
        body?.anomaly_events ??
        body?.summary?.anomaly_events ??
        {};

    const total =
        anomaly.total_events ??
        anomaly.count ??
        body?.total_events ??
        0;

    const affected =
        anomaly.affected_assets ??
        body?.affected_assets ??
        0;

    const totalEl = phase70El("phase70AnomalyCount");
    const affectedEl = phase70El("phase70AffectedAssets");

    if (totalEl) totalEl.textContent = phase70Num(total);
    if (affectedEl) {
        affectedEl.textContent = phase70Num(affected);
    }
}

function phase70RenderEvents(body) {
    phase70State.events = body;

    const events = phase70Array(
        body,
        ["events", "anomaly_events", "results"]
    );

    const count =
        body?.count ??
        body?.total_events ??
        events.length;

    const countEl = phase70El("phase70EventCount");

    if (countEl) {
        countEl.textContent =
            `${phase70Num(count)} event` +
            `${phase70Num(count) === 1 ? "" : "s"}`;
    }

    const target = phase70El("phase70EventList");
    if (!target) return;

    if (!events.length) {
        target.innerHTML =
            '<div class="empty-state">' +
            'No predictive anomaly events returned.' +
            '</div>';
        return;
    }

    target.innerHTML = events.slice(0, 12).map((event) => {
        const severity =
            event.severity ??
            event.level ??
            event.status ??
            "UNKNOWN";

        const metric =
            event.metric ??
            event.metric_name ??
            "telemetry";

        const asset =
            event.asset_name ??
            event.name ??
            (
                event.asset_id != null
                    ? `Asset ${event.asset_id}`
                    : "Infrastructure"
            );

        const when =
            event.detected_at ??
            event.created_at ??
            event.evaluated_at ??
            event.timestamp ??
            "";

        return `
            <div class="phase70-row">
                <div class="phase70-row-main">
                    <div class="phase70-row-title">
                        ${phase70Esc(asset)}
                    </div>

                    <div class="phase70-row-meta">
                        ${phase70Esc(metric)}
                        ${when ? ` · ${phase70Esc(when)}` : ""}
                    </div>
                </div>

                <span class="phase70-badge ${phase70SeverityClass(severity)}">
                    ${phase70Esc(severity)}
                </span>
            </div>
        `;
    }).join("");
}

function phase70RenderAnomaly(body) {
    const target = phase70El("phase70AnomalyPanel");
    if (!target) return;

    const data = phase70Object(
        body,
        ["anomaly", "result", "analysis"]
    );

    const severity =
        data.severity ??
        body?.severity ??
        data.status ??
        body?.status ??
        "NONE";

    phase70SetBadge(
        "phase70AnomalyBadge",
        String(severity).toUpperCase(),
        phase70SeverityClass(severity)
    );

    const metric =
        data.metric ??
        body?.metric ??
        "Telemetry";

    const score =
        data.score ??
        data.anomaly_score ??
        body?.score ??
        body?.anomaly_score;

    const explanation =
        data.explanation ??
        data.reason ??
        body?.explanation ??
        body?.reason ??
        "No anomaly explanation returned.";

    target.innerHTML = `
        <div class="phase70-metric">
            <span>Metric</span>
            <strong>${phase70Esc(metric)}</strong>
        </div>

        <div class="phase70-metric">
            <span>Anomaly Score</span>
            <strong>
                ${score == null ? "—" : phase70Esc(score)}
            </strong>
        </div>

        <div class="phase70-explanation">
            ${phase70Esc(explanation)}
        </div>
    `;
}

function phase70RenderTrend(body) {
    const target = phase70El("phase70TrendPanel");
    if (!target) return;

    const data = phase70Object(
        body,
        ["trend", "prediction", "result", "analysis"]
    );

    const trend =
        data.trend ??
        data.direction ??
        body?.trend ??
        body?.direction ??
        "UNKNOWN";

    phase70SetBadge(
        "phase70TrendBadge",
        String(trend).toUpperCase(),
        phase70SeverityClass(trend)
    );

    const metric =
        data.metric ??
        body?.metric ??
        "Telemetry";

    const direction =
        data.direction ??
        data.trend ??
        body?.direction ??
        body?.trend ??
        "UNKNOWN";

    const forecast =
        data.forecast ??
        data.predicted_value ??
        data.prediction ??
        body?.forecast ??
        body?.predicted_value;

    const explanation =
        data.explanation ??
        data.reason ??
        body?.explanation ??
        body?.reason ??
        "No trend explanation returned.";

    target.innerHTML = `
        <div class="phase70-metric">
            <span>Metric</span>
            <strong>${phase70Esc(metric)}</strong>
        </div>

        <div class="phase70-metric">
            <span>Direction</span>
            <strong>${phase70Esc(direction)}</strong>
        </div>

        <div class="phase70-metric">
            <span>Forecast</span>
            <strong>
                ${forecast == null ? "—" : phase70Esc(forecast)}
            </strong>
        </div>

        <div class="phase70-explanation">
            ${phase70Esc(explanation)}
        </div>
    `;
}

function phase70RenderRisk(body) {
    const target = phase70El("phase70RiskPanel");
    if (!target) return;

    const data = phase70Object(
        body,
        ["risk", "result", "analysis"]
    );

    const score =
        data.score ??
        data.risk_score ??
        body?.score ??
        body?.risk_score ??
        0;

    const level =
        data.risk_level ??
        data.level ??
        body?.risk_level ??
        body?.level ??
        "UNKNOWN";

    const explanation =
        data.explanation ??
        data.reason ??
        body?.explanation ??
        body?.reason ??
        "No risk explanation returned.";

    const scoreEl = phase70El("phase70SelectedRisk");
    const levelEl = phase70El("phase70RiskLevel");

    if (scoreEl) {
        scoreEl.textContent =
            `${phase70Num(score).toFixed(1)}`;
    }

    if (levelEl) {
        levelEl.textContent =
            String(level).toUpperCase();
    }

    phase70SetBadge(
        "phase70RiskBadge",
        String(level).toUpperCase(),
        phase70SeverityClass(level)
    );

    target.innerHTML = `
        <div class="phase70-risk-score">
            <strong>${phase70Num(score).toFixed(1)}</strong>
            <span>/ 100</span>
        </div>

        <div class="phase70-risk-level">
            ${phase70Esc(String(level).toUpperCase())}
        </div>

        <div class="phase70-explanation">
            ${phase70Esc(explanation)}
        </div>
    `;
}

function phase70ResetAssetPanels() {
    phase70State.selectedAssetId = null;

    const riskScore = phase70El("phase70SelectedRisk");
    const riskLevel = phase70El("phase70RiskLevel");

    if (riskScore) riskScore.textContent = "—";
    if (riskLevel) riskLevel.textContent = "—";

    [
        ["phase70AnomalyPanel", "phase70AnomalyBadge"],
        ["phase70TrendPanel", "phase70TrendBadge"],
        ["phase70RiskPanel", "phase70RiskBadge"]
    ].forEach(([panelId, badgeId]) => {
        const panel = phase70El(panelId);

        if (panel) {
            panel.innerHTML =
                '<div class="empty-state">' +
                'Select an infrastructure asset.' +
                '</div>';
        }

        phase70SetBadge(badgeId, "WAITING");
    });
}

async function phase70RefreshGlobal() {
    const [summary, events] = await Promise.all([
        phase70Fetch("/predictive/summary"),
        phase70Fetch("/anomaly-events")
    ]);

    phase70RenderSummary(summary);
    phase70RenderEvents(events);
}

async function phase70RefreshAsset(assetId) {
    if (!assetId) {
        phase70ResetAssetPanels();
        return;
    }

    phase70State.selectedAssetId = String(assetId);

    const encoded = encodeURIComponent(assetId);

    const [anomaly, trend, risk] = await Promise.all([
        phase70Fetch(
            `/predictive/anomalies/${encoded}`
        ),
        phase70Fetch(
            `/predictive/trends/${encoded}`
        ),
        phase70Fetch(
            `/predictive/risk/${encoded}`
        )
    ]);

    phase70RenderAnomaly(anomaly);
    phase70RenderTrend(trend);
    phase70RenderRisk(risk);
}

async function refreshPhase70() {
    if (
        phase70State.loading ||
        !phase70El("predictiveOperationsSection")
    ) {
        return;
    }

    phase70State.loading = true;
    phase70SetStatus("REFRESHING", "loading");

    try {
        phase70PopulateAssets();

        await phase70RefreshGlobal();

        const select = phase70El("phase70AssetSelect");

        if (select?.value) {
            await phase70RefreshAsset(select.value);
        }

        phase70SetStatus("LIVE");
    } catch (error) {
        console.error(
            "Phase 7.0E dashboard refresh failed:",
            error
        );

        phase70SetStatus("API ERROR", "error");
    } finally {
        phase70State.loading = false;
    }
}

function initPhase70() {
    if (!phase70El("predictiveOperationsSection")) {
        return;
    }

    phase70El("phase70RefreshButton")
        ?.addEventListener(
            "click",
            refreshPhase70
        );

    phase70El("phase70AssetSelect")
        ?.addEventListener(
            "change",
            async (event) => {
                const value = event.target.value;

                if (!value) {
                    phase70ResetAssetPanels();
                    return;
                }

                phase70SetStatus(
                    "REFRESHING",
                    "loading"
                );

                try {
                    await phase70RefreshAsset(value);
                    phase70SetStatus("LIVE");
                } catch (error) {
                    console.error(
                        "Phase 7.0E asset analysis failed:",
                        error
                    );

                    phase70SetStatus(
                        "API ERROR",
                        "error"
                    );
                }
            }
        );

    phase70PopulateAssets();
    refreshPhase70();

    if (phase70State.refreshTimer) {
        clearInterval(
            phase70State.refreshTimer
        );
    }

    phase70State.refreshTimer =
        window.setInterval(
            refreshPhase70,
            30000
        );
}

if (document.readyState === "loading") {
    document.addEventListener(
        "DOMContentLoaded",
        initPhase70
    );
} else {
    initPhase70();
}
'''

js = js.rstrip() + "\n" + phase70_js + "\n"


# ============================================================
# CSS
# ============================================================

phase70_css = r'''

/* ==========================================================
   PHASE 7.0E — PREDICTIVE OPERATIONS
   Additive styles only. Existing map and Phase 6.6–6.9
   styles are intentionally unchanged.
   ========================================================== */

.phase70-section {
    display: grid;
    gap: 18px;
}

.phase70-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 20px;
}

.phase70-heading h2 {
    margin: 4px 0 6px;
}

.phase70-heading p:last-child {
    margin: 0;
    opacity: .72;
    max-width: 760px;
}

.phase70-heading-actions {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

.phase70-live-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-height: 34px;
    padding: 0 12px;
    border: 1px solid rgba(63,230,255,.25);
    border-radius: 999px;
    background: rgba(21,195,225,.08);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: .12em;
}

.phase70-live-pill::before {
    content: "";
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #55f3c2;
    box-shadow: 0 0 12px rgba(85,243,194,.8);
}

.phase70-live-pill.loading::before {
    background: #ffd166;
    box-shadow: 0 0 12px rgba(255,209,102,.75);
}

.phase70-live-pill.error::before {
    background: #ff5f7d;
    box-shadow: 0 0 12px rgba(255,95,125,.75);
}

.phase70-kpi-grid {
    display: grid;
    grid-template-columns:
        repeat(4, minmax(0, 1fr));
    gap: 12px;
}

.phase70-kpi-card {
    min-height: 116px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 5px;
}

.phase70-kpi-card span {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: .1em;
    opacity: .68;
}

.phase70-kpi-card strong {
    font-size: 27px;
    line-height: 1;
}

.phase70-kpi-card small {
    opacity: .58;
}

.phase70-selector-card {
    display: flex;
    justify-content: space-between;
    align-items: end;
    gap: 20px;
}

.phase70-selector-card h3 {
    margin: 5px 0 0;
}

.phase70-select-wrap {
    min-width: min(420px, 100%);
    display: grid;
    gap: 6px;
}

.phase70-select-wrap > span {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: .1em;
    opacity: .62;
}

.phase70-select-wrap select {
    width: 100%;
    min-height: 42px;
    padding: 0 12px;
    border: 1px solid rgba(130,190,255,.18);
    border-radius: 10px;
    background: rgba(8,17,31,.82);
    color: inherit;
    outline: none;
}

.phase70-grid {
    display: grid;
    grid-template-columns:
        minmax(0, 1fr)
        minmax(0, 1fr);
    gap: 16px;
}

.phase70-panel {
    min-width: 0;
}

.phase70-content {
    display: grid;
    gap: 10px;
    margin-top: 14px;
}

.phase70-metric {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border: 1px solid rgba(130,190,255,.11);
    border-radius: 10px;
    background: rgba(8,17,31,.30);
}

.phase70-metric span {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: .08em;
    opacity: .62;
}

.phase70-metric strong {
    text-align: right;
}

.phase70-explanation {
    padding: 12px;
    border: 1px solid rgba(130,190,255,.11);
    border-radius: 10px;
    background: rgba(8,17,31,.30);
    font-size: 12px;
    line-height: 1.6;
    opacity: .78;
}

.phase70-list {
    display: grid;
    gap: 8px;
    margin-top: 14px;
}

.phase70-row {
    display: grid;
    grid-template-columns:
        minmax(0, 1fr) auto;
    align-items: center;
    gap: 12px;
    padding: 11px 12px;
    border: 1px solid rgba(130,190,255,.11);
    border-radius: 12px;
    background: rgba(8,17,31,.38);
}

.phase70-row-main {
    min-width: 0;
}

.phase70-row-title {
    font-weight: 700;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.phase70-row-meta {
    margin-top: 4px;
    font-size: 11px;
    opacity: .62;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.phase70-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 72px;
    padding: 5px 8px;
    border-radius: 999px;
    border: 1px solid rgba(130,190,255,.18);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: .06em;
    text-transform: uppercase;
}

.phase70-badge.healthy {
    color: #55f3c2;
    border-color: rgba(85,243,194,.28);
    background: rgba(85,243,194,.07);
}

.phase70-badge.warning {
    color: #ffd166;
    border-color: rgba(255,209,102,.30);
    background: rgba(255,209,102,.07);
}

.phase70-badge.danger {
    color: #ff6b86;
    border-color: rgba(255,107,134,.30);
    background: rgba(255,107,134,.07);
}

.phase70-risk-score {
    display: flex;
    align-items: baseline;
    gap: 7px;
}

.phase70-risk-score strong {
    font-size: 38px;
    line-height: 1;
}

.phase70-risk-score span {
    opacity: .52;
}

.phase70-risk-level {
    font-size: 12px;
    font-weight: 800;
    letter-spacing: .12em;
    text-transform: uppercase;
}

.phase70-count {
    font-size: 11px;
    opacity: .70;
}

.phase70-provenance {
    font-size: 10px;
    opacity: .45;
    text-align: right;
    letter-spacing: .04em;
}

@media (max-width: 1200px) {
    .phase70-kpi-grid {
        grid-template-columns:
            repeat(2, minmax(0, 1fr));
    }

    .phase70-grid {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 760px) {
    .phase70-heading {
        flex-direction: column;
    }

    .phase70-kpi-grid {
        grid-template-columns:
            repeat(2, minmax(0, 1fr));
    }

    .phase70-selector-card {
        align-items: stretch;
        flex-direction: column;
    }

    .phase70-select-wrap {
        min-width: 0;
        width: 100%;
    }
}
'''

css = css.rstrip() + "\n" + phase70_css + "\n"


# ------------------------------------------------------------
# Write only after every validation/transformation succeeded
# ------------------------------------------------------------

HTML.write_text(html, encoding="utf-8")
JS.write_text(js, encoding="utf-8")
CSS.write_text(css, encoding="utf-8")

print("✅ Phase 7.0E frontend integration applied.")
print("   Added: Predictive Ops navigation")
print("   Added: Predictive Operations dashboard section")
print("   Added: /predictive/summary request")
print("   Added: /anomaly-events request")
print("   Added: asset anomaly/trend/risk requests")
print("   Existing map and Phase 6.6–6.9 source retained.")
