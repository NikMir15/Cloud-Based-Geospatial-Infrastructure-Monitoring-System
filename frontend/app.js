/* =========================================================
   INFRASTRUCTURE SITUATIONAL AWARENESS PLATFORM

   Phase 6.6 Frontend

   - Live USGS earthquake visualization
   - Project-local simulated sensor telemetry
   - PostGIS exposure/risk visualization
   - Phase 6.1 local test earthquake
   - REST + WebSockets
   - Persistent telemetry history + live SVG charts
   - Persistent telemetry alert lifecycle + audit history
========================================================= */


/* =========================================================
   GLOBAL STATE
========================================================= */

let map;

let clusterGroup;

let infrastructureData = [];

let riskData = [];

let earthquakeData = [];

let earthquakeLayers = [];

let activeTestEvent = null;


/*
    Map of asset ID -> local sensor telemetry
*/
const sensorTelemetry = new Map();


/*
    Map of asset ID -> Leaflet marker
*/
const assetMarkers = new Map();


let locationSocket = null;

let eventSocket = null;

let sensorSocket = null;

let alertSocket = null;

let alertData = [];

let alertSummary = {
    total: 0,
    critical: 0,
    high: 0,
    medium: 0,
    low: 0
};

let sensorHealthSummary = {
    total: 0,
    online: 0,
    degraded: 0,
    offline: 0,
    average_health: 0
};


let selectedHistoryAssetId = null;

let telemetryHistoryRecords = [];

let telemetryHistoryTimer = null;

let telemetryHistoryPaused = false;

let telemetryHistoryLastUpdatedAt = null;

const TELEMETRY_HISTORY_REFRESH_MS = 60000;


let telemetryAlertSocket = null;

let telemetryAlertData = [];

let telemetryAlertSummary = {
    total: 0,
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    threshold_alerts: 0,
    trend_alerts: 0,
    affected_assets: 0
};

let telemetryAlertWindowMinutes = 5;


let persistedTelemetryAlerts = [];

let persistedAlertLastUpdatedAt = null;

let selectedPersistedAlertId = null;

let persistedAlertRequestInFlight = false;


/* =========================================================
   API CONFIGURATION
========================================================= */

const API_URL =
    `${window.location.protocol}//${window.location.hostname}:8000`;


/* =========================================================
   WEBSOCKET CONFIGURATION
========================================================= */

function getWebSocketBaseURL() {

    const protocol =
        window.location.protocol === "https:"
            ? "wss"
            : "ws";


    return (
        `${protocol}://${window.location.hostname}:8000`
    );
}


/* =========================================================
   INFRASTRUCTURE COLORS
========================================================= */

function getInfrastructureColor(type) {

    const colors = {

        cloud:
            "#25c7ff",

        education:
            "#43df8c",

        healthcare:
            "#ff5468",

        transport:
            "#ffc845",

        telecom:
            "#c06cff",

        sensor:
            "#20d8ff",

        traffic:
            "#ff9f32",

        environment:
            "#47df88",

        grid:
            "#f3dc4c",

        bridge:
            "#ff5757",

        coastal:
            "#3fbaff",

        tower:
            "#a968ff"
    };


    return (
        colors[
            String(
                type || ""
            ).toLowerCase()
        ]
        ||
        "#cad4dc"
    );
}


/* =========================================================
   RISK COLORS
========================================================= */

function getRiskColor(severity) {

    const value =
        String(
            severity || "low"
        ).toLowerCase();


    if (value === "critical") {

        return "#ff4057";
    }


    if (value === "high") {

        return "#ff843d";
    }


    if (value === "medium") {

        return "#ffc845";
    }


    return "#45df8c";
}


/* =========================================================
   SENSOR STATUS COLORS
========================================================= */

function getSensorStatusColor(status) {

    const value =
        String(
            status || "unknown"
        ).toLowerCase();


    if (value === "online") {

        return "#5effa5";
    }


    if (value === "degraded") {

        return "#ffc845";
    }


    if (value === "offline") {

        return "#ff4057";
    }


    return "#8398a7";
}


/* =========================================================
   SENSOR STATUS OPACITY
========================================================= */

function getSensorOpacity(status) {

    const value =
        String(
            status || "online"
        ).toLowerCase();


    if (value === "offline") {

        return 0.35;
    }


    if (value === "degraded") {

        return 0.70;
    }


    return 0.95;
}


/* =========================================================
   MAP INITIALISATION
========================================================= */

function initMap() {

    map =
        L.map(
            "map",
            {
                zoomControl:
                    false,

                worldCopyJump:
                    true,

                minZoom:
                    2
            }
        )
        .setView(
            [20, 5],
            2
        );


    /*
        Keep controls bottom-right so they do not
        overlap the command panel.
    */

    L.control
        .zoom(
            {
                position:
                    "bottomright"
            }
        )
        .addTo(map);


    /*
        OpenStreetMap standard raster basemap.

        This endpoint does NOT require an API key.
        The dark command-center appearance is applied
        using CSS only, so the map remains stable and
        does not display provider API-key watermarks.
    */

    L.tileLayer(
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            minZoom:
                2,

            maxZoom:
                19,

            noWrap:
                true,

            attribution:
                "&copy; OpenStreetMap contributors"
        }
    )
    .addTo(map);


    /*
        Infrastructure marker cluster group
    */

    clusterGroup =
        L.markerClusterGroup(
            {
                showCoverageOnHover:
                    false,

                spiderfyOnMaxZoom:
                    true,

                /*
                    Phase 6.7 command-center view:
                    show every infrastructure marker individually.

                    The map's minimum zoom is 2, so disabling
                    clustering at zoom 2 removes the numeric
                    cluster bubbles (for example 23, 18, 6)
                    at every usable zoom level while keeping
                    MarkerClusterGroup compatibility for the
                    existing focus/zoom functions.
                */
                disableClusteringAtZoom:
                    2,

                iconCreateFunction:
                    createClusterIcon
            }
        );


    map.addLayer(
        clusterGroup
    );


    /*
        Click anywhere on map to find
        nearest monitored infrastructure.
    */

    map.on(
        "click",
        handleMapClick
    );
}


/* =========================================================
   CLUSTER ICONS
========================================================= */

function createClusterIcon(cluster) {

    const count =
        cluster.getChildCount();


    let className =
        "cluster-low";


    let size =
        40;


    if (count >= 10) {

        className =
            "cluster-medium";

        size =
            46;
    }


    if (count >= 20) {

        className =
            "cluster-high";

        size =
            52;
    }


    return L.divIcon(
        {
            html: `
                <div
                    class="
                        custom-cluster
                        ${className}
                    "
                    style="
                        width:${size}px;
                        height:${size}px;
                    "
                >
                    ${count}
                </div>
            `,

            className:
                "",

            iconSize:
                [
                    size,
                    size
                ]
        }
    );
}


/* =========================================================
   RISK LOOKUP
========================================================= */

function getAssetRisk(assetId) {

    return riskData.find(
        item =>
            Number(item.id)
            ===
            Number(assetId)
    );
}


/* =========================================================
   SENSOR LOOKUP
========================================================= */

function getSensorData(assetId) {

    return (
        sensorTelemetry.get(
            Number(assetId)
        )
        ||
        null
    );
}


/* =========================================================
   SENSOR AGE
========================================================= */

function formatTelemetryAge(timestamp) {

    if (!timestamp) {

        return "unknown";
    }


    const date =
        new Date(
            timestamp
        );


    if (
        Number.isNaN(
            date.getTime()
        )
    ) {

        return "unknown";
    }


    const seconds =
        Math.max(
            0,
            Math.floor(
                (
                    Date.now()
                    -
                    date.getTime()
                )
                /
                1000
            )
        );


    if (seconds < 5) {

        return "just now";
    }


    if (seconds < 60) {

        return `${seconds} sec ago`;
    }


    const minutes =
        Math.floor(
            seconds / 60
        );


    if (minutes < 60) {

        return `${minutes} min ago`;
    }


    return timestamp;
}


/* =========================================================
   SENSOR TELEMETRY POPUP HTML
========================================================= */

function buildSensorTelemetryHTML(assetId) {

    const sensor =
        getSensorData(
            assetId
        );


    if (!sensor) {

        return `
            <div
                style="
                    margin-top:10px;
                    padding-top:8px;
                    border-top:
                    1px solid rgba(255,255,255,0.08);
                "
            >

                <strong>
                    LOCAL LIVE TELEMETRY
                </strong>

                <br>

                <span
                    style="
                        color:#8398a7;
                    "
                >
                    Waiting for local sensor data...
                </span>

            </div>
        `;
    }


    const statusColor =
        getSensorStatusColor(
            sensor.status
        );


    return `
        <div
            style="
                margin-top:10px;
                padding-top:9px;
                border-top:
                1px solid rgba(255,255,255,0.08);
            "
        >

            <strong>
                LOCAL LIVE TELEMETRY
            </strong>

            <br><br>


            <span
                style="
                    color:${statusColor};
                    font-weight:700;
                "
            >
                ● ${escapeHtml(
                    String(
                        sensor.status
                        || "unknown"
                    ).toUpperCase()
                )}
            </span>


            <br><br>


            <strong>
                Health:
            </strong>

            ${Number(
                sensor.health
                ?? 0
            ).toFixed(0)}%


            <br>


            <strong>
                CPU:
            </strong>

            ${Number(
                sensor.cpu_percent
                ?? 0
            ).toFixed(1)}%


            <br>


            <strong>
                Temperature:
            </strong>

            ${Number(
                sensor.temperature_c
                ?? 0
            ).toFixed(1)}°C


            <br>


            <strong>
                Latency:
            </strong>

            ${Number(
                sensor.latency_ms
                ?? 0
            ).toFixed(1)} ms


            <br>


            <strong>
                Packet Loss:
            </strong>

            ${Number(
                sensor.packet_loss_percent
                ?? 0
            ).toFixed(2)}%


            <br>


            <strong>
                Signal:
            </strong>

            ${Number(
                sensor.signal_strength
                ?? 0
            ).toFixed(0)}%


            <br><br>


            <span
                style="
                    color:#6f8799;
                    font-size:10px;
                "
            >

                Source:
                LOCAL PROJECT SIMULATION

                <br>

                Updated:
                ${escapeHtml(
                    formatTelemetryAge(
                        sensor.last_updated
                    )
                )}

            </span>

        </div>
    `;
}


/* =========================================================
   INFRASTRUCTURE POPUP
========================================================= */

function buildInfrastructurePopup(point) {

    const risk =
        getAssetRisk(
            point.id
        );


    let riskHTML = `
        <strong>
            Estimated Exposure:
        </strong>

        Low
    `;


    if (risk) {

        riskHTML = `
            <strong>
                Estimated Exposure:
            </strong>

            ${Number(
                risk.risk_score
                ?? 0
            )}/100

            <br>


            <strong>
                Severity:
            </strong>

            ${escapeHtml(
                risk.severity
                || "low"
            )}

            <br>


            <strong>
                Hazard:
            </strong>

            M${Number(
                risk.magnitude
                ?? 0
            )}

            earthquake

            <br>


            <strong>
                Event Source:
            </strong>

            ${escapeHtml(
                risk.event_source
                || "USGS"
            )}

            <br>


            <strong>
                Hazard Distance:
            </strong>

            ${Number(
                risk.distance_km
                ?? 0
            ).toFixed(2)}
            km
        `;
    }


    return `
        <div>

            <strong
                style="
                    font-size:14px;
                "
            >
                ${escapeHtml(
                    point.name
                )}
            </strong>


            <br><br>


            ${escapeHtml(
                point.description
                || ""
            )}


            <br>


            <strong>
                Infrastructure Type:
            </strong>

            ${escapeHtml(
                point.infra_type
                || "Unknown"
            )}


            <br>


            <strong>
                Asset Status:
            </strong>

            ${escapeHtml(
                point.status
                || "operational"
            )}


            <br><br>


            ${riskHTML}


            ${buildSensorTelemetryHTML(
                point.id
            )}

        </div>
    `;
}


/* =========================================================
   CREATE INFRASTRUCTURE MARKER
========================================================= */

function createInfrastructureMarker(point) {

    const risk =
        getAssetRisk(
            point.id
        );


    const sensor =
        getSensorData(
            point.id
        );


    const severity =
        risk
            ? risk.severity
            : (
                point.severity
                || "low"
            );


    const baseColor =
        getInfrastructureColor(
            point.infra_type
        );


    const markerColor =
        (
            risk
            &&
            Number(
                risk.risk_score
                || 0
            )
            >= 30
        )
            ?
            getRiskColor(
                severity
            )
            :
            baseColor;


    const radius =
        risk
            ? 9
            : 7;


    const marker =
        L.circleMarker(
            [
                point.latitude,
                point.longitude
            ],
            {
                radius:
                    radius,

                color:
                    markerColor,

                fillColor:
                    markerColor,

                fillOpacity:
                    getSensorOpacity(
                        sensor
                            ? sensor.status
                            : "online"
                    ),

                weight:
                    risk
                        ? 3
                        : 2
            }
        );


    marker.bindPopup(
        buildInfrastructurePopup(
            point
        )
    );


    /*
        Store asset ID on marker
    */

    marker.assetId =
        Number(
            point.id
        );


    /*
        Important:
        rebuild popup when clicked so the user
        always sees the latest local telemetry.
    */

    marker.on(
        "click",
        () => {

            marker.setPopupContent(
                buildInfrastructurePopup(
                    point
                )
            );

            selectHistoryAsset(
                point.id,
                true
            );
        }
    );


    assetMarkers.set(
        Number(
            point.id
        ),
        marker
    );


    return marker;
}


/* =========================================================
   RENDER INFRASTRUCTURE
========================================================= */

function renderInfrastructure(data) {

    clusterGroup.clearLayers();

    assetMarkers.clear();


    data.forEach(
        point => {

            if (
                point.latitude == null
                ||
                point.longitude == null
            ) {

                return;
            }


            clusterGroup.addLayer(
                createInfrastructureMarker(
                    point
                )
            );
        }
    );
}


/* =========================================================
   UPDATE EXISTING MARKER TELEMETRY
========================================================= */

function refreshMarkerTelemetry() {

    infrastructureData.forEach(
        point => {

            const marker =
                assetMarkers.get(
                    Number(
                        point.id
                    )
                );


            if (!marker) {

                return;
            }


            const sensor =
                getSensorData(
                    point.id
                );


            /*
                Refresh popup content without rebuilding
                the whole Leaflet map.
            */

            marker.setPopupContent(
                buildInfrastructurePopup(
                    point
                )
            );


            /*
                Visually fade degraded/offline local
                sensors while keeping infrastructure/risk
                coloring intact.
            */

            marker.setStyle(
                {
                    fillOpacity:
                        getSensorOpacity(
                            sensor
                                ? sensor.status
                                : "online"
                        )
                }
            );
        }
    );
}


/* =========================================================
   INFRASTRUCTURE TYPE FILTER
========================================================= */

function populateTypeFilter(data) {

    const select =
        document.getElementById(
            "typeFilter"
        );


    if (!select) {

        return;
    }


    const previous =
        select.value;


    const types =
        [
            ...new Set(
                data
                    .map(
                        item =>
                            item.infra_type
                    )
                    .filter(Boolean)
            )
        ]
        .sort();


    select.innerHTML = `
        <option value="all">
            All Infrastructure
        </option>
    `;


    types.forEach(
        type => {

            const option =
                document.createElement(
                    "option"
                );


            option.value =
                type;


            option.textContent =
                type;


            select.appendChild(
                option
            );
        }
    );


    if (
        types.includes(
            previous
        )
    ) {

        select.value =
            previous;
    }
}


/* =========================================================
   TEST ASSET FILTER
========================================================= */

function populateTestAssetSelect(data) {

    const select =
        document.getElementById(
            "testAsset"
        );


    if (!select) {

        return;
    }


    const previous =
        select.value;


    select.innerHTML = `
        <option value="">
            Select infrastructure...
        </option>
    `;


    [...data]
        .sort(
            (a, b) =>
                String(
                    a.name
                )
                .localeCompare(
                    String(
                        b.name
                    )
                )
        )
        .forEach(
            point => {

                const option =
                    document.createElement(
                        "option"
                    );


                option.value =
                    point.id;


                option.textContent =
                    `${point.name} (${point.infra_type})`;


                select.appendChild(
                    option
                );
            }
        );


    if (
        previous
        &&
        data.some(
            item =>
                String(item.id)
                ===
                String(previous)
        )
    ) {

        select.value =
            previous;
    }
}



/* =========================================================
   PHASE 6.4 HISTORY ASSET SELECTOR
========================================================= */

function populateHistoryAssetSelect(data) {

    const select =
        document.getElementById(
            "historyAsset"
        );

    if (!select) {
        return;
    }

    const previous =
        select.value
        || (
            selectedHistoryAssetId != null
                ? String(selectedHistoryAssetId)
                : ""
        );

    select.innerHTML = `
        <option value="">
            Select infrastructure...
        </option>
    `;

    [...data]
        .sort(
            (a, b) =>
                String(a.name || "")
                    .localeCompare(
                        String(b.name || "")
                    )
        )
        .forEach(
            point => {

                const option =
                    document.createElement(
                        "option"
                    );

                option.value =
                    String(point.id);

                option.textContent =
                    `${point.name} (${point.infra_type || "Unknown"})`;

                select.appendChild(
                    option
                );
            }
        );

    if (
        previous
        &&
        data.some(
            item =>
                String(item.id)
                ===
                String(previous)
        )
    ) {

        select.value =
            String(previous);

        selectedHistoryAssetId =
            Number(previous);

        return;
    }

    if (
        selectedHistoryAssetId == null
        &&
        data.length > 0
    ) {

        selectedHistoryAssetId =
            Number(
                data[0].id
            );

        select.value =
            String(
                selectedHistoryAssetId
            );
    }
}


/* =========================================================
   APPLY FILTERS
========================================================= */

function applyFilters() {

    const searchElement =
        document.getElementById(
            "searchBox"
        );


    const typeElement =
        document.getElementById(
            "typeFilter"
        );


    const riskElement =
        document.getElementById(
            "riskFilter"
        );


    const search =
        searchElement
            ? searchElement.value
                .trim()
                .toLowerCase()
            : "";


    const selectedType =
        typeElement
            ? typeElement.value
            : "all";


    const selectedRisk =
        riskElement
            ? riskElement.value
            : "all";


    const filtered =
        infrastructureData.filter(
            point => {

                const searchableText = `
                    ${point.name || ""}
                    ${point.description || ""}
                    ${point.infra_type || ""}
                `
                .toLowerCase();


                const matchesSearch =
                    searchableText.includes(
                        search
                    );


                const matchesType =
                    (
                        selectedType
                        === "all"
                    )
                    ||
                    (
                        point.infra_type
                        === selectedType
                    );


                const risk =
                    getAssetRisk(
                        point.id
                    );


                const severity =
                    risk
                        ? risk.severity
                        : (
                            point.severity
                            || "low"
                        );


                const matchesRisk =
                    (
                        selectedRisk
                        === "all"
                    )
                    ||
                    (
                        severity
                        === selectedRisk
                    );


                return (
                    matchesSearch
                    &&
                    matchesType
                    &&
                    matchesRisk
                );
            }
        );


    renderInfrastructure(
        filtered
    );
}


/* =========================================================
   LOAD INFRASTRUCTURE
========================================================= */

async function loadLocations() {

    try {

        const response =
            await fetch(
                `${API_URL}/locations`
            );


        if (!response.ok) {

            throw new Error(
                "Locations request failed"
            );
        }


        infrastructureData =
            await response.json();


        populateTypeFilter(
            infrastructureData
        );


        populateTestAssetSelect(
            infrastructureData
        );


        populateHistoryAssetSelect(
            infrastructureData
        );


        applyFilters();

    }

    catch (error) {

        console.error(
            "Locations load error:",
            error
        );
    }
}


/* =========================================================
   LOAD LOCAL SENSOR TELEMETRY
========================================================= */

async function loadSensorTelemetry() {

    try {

        const response =
            await fetch(
                `${API_URL}/sensor-telemetry`
            );


        if (!response.ok) {

            throw new Error(
                "Sensor telemetry request failed"
            );
        }


        const payload =
            await response.json();


        /*
            Only accept telemetry explicitly marked as
            local to this project.
        */

        if (
            payload.source
            !== "LOCAL_PROJECT"
        ) {

            console.warn(
                "Unexpected telemetry source:",
                payload.source
            );

            return;
        }


        if (
            payload.external
            !== false
        ) {

            console.warn(
                "Telemetry was not marked project-local."
            );

            return;
        }


        updateSensorStore(
            payload.sensors
            || []
        );


        refreshMarkerTelemetry();

    }

    catch (error) {

        console.error(
            "Sensor telemetry load error:",
            error
        );
    }
}


/* =========================================================
   UPDATE SENSOR STORE
========================================================= */

function updateSensorStore(data) {

    data.forEach(
        sensor => {

            sensorTelemetry.set(
                Number(
                    sensor.asset_id
                ),
                sensor
            );
        }
    );
}


/* =========================================================
   MAP CLICK → NEAREST ASSET
========================================================= */

async function handleMapClick(event) {

    try {

        const response =
            await fetch(
                `${API_URL}/nearest?lat=${event.latlng.lat}&lon=${event.latlng.lng}`
            );


        if (!response.ok) {

            throw new Error(
                "Nearest infrastructure request failed"
            );
        }


        const data =
            await response.json();


        if (!data.name) {

            return;
        }


        L.popup()
            .setLatLng(
                event.latlng
            )
            .setContent(
                `
                <strong>
                    Nearest Infrastructure
                </strong>

                <br><br>

                ${escapeHtml(
                    data.name
                )}

                <br>

                ${escapeHtml(
                    data.infra_type
                )}

                <br>

                ${Number(
                    data.distance_km
                    || 0
                ).toFixed(2)}
                km
                `
            )
            .openOn(map);

    }

    catch (error) {

        console.error(
            "Nearest lookup error:",
            error
        );
    }
}


/* =========================================================
   LOAD RISK DATA
========================================================= */

async function loadRisk() {

    try {

        const response =
            await fetch(
                `${API_URL}/risk`
            );


        if (!response.ok) {

            throw new Error(
                "Risk request failed"
            );
        }


        const data =
            await response.json();


        riskData =
            data.assets
            || [];


        const affectedElement =
            document.getElementById(
                "affectedAssets"
            );


        if (affectedElement) {

            affectedElement.textContent =
                data.affected_assets
                || 0;
        }


        renderRiskFeed(
            riskData
        );


        applyFilters();

    }

    catch (error) {

        console.error(
            "Risk load error:",
            error
        );
    }
}


/* =========================================================
   RISK FEED
========================================================= */

function renderRiskFeed(data) {

    const container =
        document.getElementById(
            "riskFeed"
        );


    if (!container) {

        return;
    }


    const significant =
        data
            .filter(
                item =>
                    Number(
                        item.risk_score
                        || 0
                    )
                    >= 30
            )
            .slice(
                0,
                10
            );


    if (
        significant.length
        === 0
    ) {

        container.innerHTML = `
            <div class="empty-state">

                No monitored infrastructure
                currently has elevated estimated
                earthquake exposure.

            </div>
        `;

        return;
    }


    container.innerHTML =
        significant
            .map(
                asset => {

                    const source =
                        asset.event_source
                        || "USGS";


                    return `
                        <div
                            class="risk-item"

                            onclick="
                                focusAsset(
                                    ${asset.latitude},
                                    ${asset.longitude}
                                )
                            "
                        >

                            <div class="event-header">

                                <strong>

                                    ${escapeHtml(
                                        asset.name
                                    )}

                                </strong>


                                <span
                                    class="
                                        severity
                                        ${escapeHtml(
                                            asset.severity
                                            || "low"
                                        )}
                                    "
                                >

                                    ${escapeHtml(
                                        asset.severity
                                        || "low"
                                    )}

                                </span>

                            </div>


                            <div class="event-type">

                                ${escapeHtml(
                                    source
                                )}

                                · Exposure

                                ${Number(
                                    asset.risk_score
                                    || 0
                                )}/100

                            </div>


                            <div class="event-description">

                                M${Number(
                                    asset.magnitude
                                    || 0
                                )}

                                ·

                                ${Number(
                                    asset.distance_km
                                    || 0
                                ).toFixed(2)}
                                km away

                            </div>

                        </div>
                    `;
                }
            )
            .join("");
}


/* =========================================================
   EARTHQUAKE RENDERING
========================================================= */

function renderEarthquakes(events) {

    earthquakeLayers.forEach(
        layer =>
            map.removeLayer(
                layer
            )
    );


    earthquakeLayers = [];


    events.forEach(
        event => {

            const isTest =
                event.source === "TEST"
                ||
                event.simulated === true;


            const color =
                isTest
                    ? "#bf5cff"
                    : getRiskColor(
                        event.severity
                    );


            const marker =
                L.circleMarker(
                    [
                        event.latitude,
                        event.longitude
                    ],
                    {
                        radius:
                            isTest
                                ? 13
                                :
                                Math.max(
                                    5,
                                    Math.min(
                                        13,
                                        Number(
                                            event.magnitude
                                            || 0
                                        )
                                        * 1.7
                                    )
                                ),

                        color:
                            "#ffffff",

                        fillColor:
                            color,

                        fillOpacity:
                            0.95,

                        weight:
                            isTest
                                ? 3
                                : 1.5
                    }
                )
                .addTo(map);


            marker.bindPopup(
                `
                <div class="quake-popup">

                    <span
                        class="
                            ${isTest
                                ? "test-source"
                                : "live-source"
                            }
                        "
                    >

                        ${isTest
                            ? "LOCAL SIMULATED TEST"
                            : "LIVE USGS READ-ONLY"
                        }

                    </span>


                    <h3>

                        M${Number(
                            event.magnitude
                            || 0
                        )}

                    </h3>


                    <strong>

                        ${escapeHtml(
                            event.place
                            || "Unknown location"
                        )}

                    </strong>


                    <br><br>


                    Depth:

                    ${
                        event.depth_km
                        ?? "N/A"
                    }
                    km


                    <br>


                    Estimated Exposure Radius:

                    ${Number(
                        event.radius_km
                        || 0
                    )}
                    km


                    <br>


                    ${
                        formatEventAge(
                            event.timestamp
                        )
                    }

                </div>
                `
            );


            earthquakeLayers.push(
                marker
            );


            if (
                isTest
                ||
                Number(
                    event.magnitude
                    || 0
                )
                >= 4.5
            ) {

                const zone =
                    L.circle(
                        [
                            event.latitude,
                            event.longitude
                        ],
                        {
                            radius:
                                Number(
                                    event.radius_km
                                    || 0
                                )
                                * 1000,

                            color:
                                color,

                            fillColor:
                                color,

                            fillOpacity:
                                isTest
                                    ? 0.08
                                    : 0.035,

                            weight:
                                isTest
                                    ? 2
                                    : 1,

                            dashArray:
                                isTest
                                    ? "8 6"
                                    : "5 5"
                        }
                    )
                    .addTo(map);


                earthquakeLayers.push(
                    zone
                );
            }
        }
    );


    renderEventFeed(
        events
    );
}


/* =========================================================
   EARTHQUAKE EVENT FEED
========================================================= */

function renderEventFeed(events) {

    const container =
        document.getElementById(
            "eventFeed"
        );


    if (!container) {

        return;
    }


    const displayEvents =
        [...events]
            .sort(
                (a, b) => {

                    const aTest =
                        a.source === "TEST"
                        ||
                        a.simulated;


                    const bTest =
                        b.source === "TEST"
                        ||
                        b.simulated;


                    if (
                        aTest
                        &&
                        !bTest
                    ) {

                        return -1;
                    }


                    if (
                        bTest
                        &&
                        !aTest
                    ) {

                        return 1;
                    }


                    return (
                        Number(
                            b.magnitude
                            || 0
                        )
                        -
                        Number(
                            a.magnitude
                            || 0
                        )
                    );
                }
            )
            .slice(
                0,
                12
            );


    if (
        displayEvents.length
        === 0
    ) {

        container.innerHTML = `
            <div class="empty-state">
                No earthquake events available.
            </div>
        `;

        return;
    }


    container.innerHTML =
        displayEvents
            .map(
                event => {

                    const isTest =
                        event.source === "TEST"
                        ||
                        event.simulated;


                    return `
                        <div
                            class="
                                event-card
                                ${isTest
                                    ? "test-event-card"
                                    : ""
                                }
                            "

                            onclick="
                                focusEarthquake(
                                    ${event.latitude},
                                    ${event.longitude}
                                )
                            "
                        >

                            <div class="event-header">

                                <span class="event-title">

                                    M${Number(
                                        event.magnitude
                                        || 0
                                    )}

                                    ${escapeHtml(
                                        event.place
                                        || ""
                                    )}

                                </span>


                                <span
                                    class="
                                        ${isTest
                                            ? "test-source"
                                            : "live-source"
                                        }
                                    "
                                >

                                    ${isTest
                                        ? "LOCAL TEST"
                                        : "USGS"
                                    }

                                </span>

                            </div>


                            <div class="event-type">

                                ${escapeHtml(
                                    event.severity
                                    || "low"
                                )}

                                · Radius

                                ${Number(
                                    event.radius_km
                                    || 0
                                )}
                                km

                            </div>


                            <div class="event-description">

                                ${formatEventAge(
                                    event.timestamp
                                )}

                            </div>

                        </div>
                    `;
                }
            )
            .join("");
}


/* =========================================================
   LOAD EARTHQUAKES
========================================================= */

async function loadEarthquakes() {

    try {

        const response =
            await fetch(
                `${API_URL}/events`
            );


        if (!response.ok) {

            throw new Error(
                "Earthquake request failed"
            );
        }


        const data =
            await response.json();


        earthquakeData =
            data.events
            || [];


        renderEarthquakes(
            earthquakeData
        );


        const sourceStatus =
            document.getElementById(
                "dataSourceStatus"
            );


        if (sourceStatus) {

            sourceStatus.textContent =
                Number(
                    data.test_event_count
                    || 0
                )
                > 0
                    ?
                    "USGS + LOCAL TEST"
                    :
                    (
                        data.live
                            ?
                            "USGS LIVE"
                            :
                            "USGS CACHE"
                    );
        }

    }

    catch (error) {

        console.error(
            "Earthquake load error:",
            error
        );
    }
}


/* =========================================================
   ANALYTICS
========================================================= */

async function loadAnalytics() {

    try {

        const response =
            await fetch(
                `${API_URL}/analytics`
            );


        if (!response.ok) {

            throw new Error(
                "Analytics request failed"
            );
        }


        const data =
            await response.json();


        setTextIfExists(
            "totalInfrastructure",
            data.total_infrastructure
            || 0
        );


        setTextIfExists(
            "liveEarthquakes",
            data.live_earthquakes
            || 0
        );


        setTextIfExists(
            "affectedAssets",
            data.affected_assets
            || 0
        );


        setTextIfExists(
            "highRisk",
            data.high_risk_assets
            || 0
        );


        setTextIfExists(
            "criticalEvents",
            data.critical_events
            || 0
        );


        setTextIfExists(
            "feedStatus",
            Number(
                data.test_events
                || 0
            )
            > 0
                ?
                "TEST"
                :
                (
                    data.live
                        ?
                        "LIVE"
                        :
                        "CACHE"
                )
        );


        renderTypeStats(
            data.by_type
            || {}
        );

    }

    catch (error) {

        console.error(
            "Analytics load error:",
            error
        );
    }
}


/* =========================================================
   TYPE STATISTICS
========================================================= */

function renderTypeStats(stats) {

    const container =
        document.getElementById(
            "typeStats"
        );


    if (!container) {

        return;
    }


    const entries =
        Object.entries(
            stats
        );


    if (
        entries.length
        === 0
    ) {

        container.innerHTML = `
            <div class="empty-state">
                No infrastructure data available.
            </div>
        `;

        return;
    }


    container.innerHTML =
        entries
            .map(
                ([type, count]) => {

                    return `
                        <div class="type-stat">

                            <div class="type-stat-name">

                                <span
                                    class="type-color-dot"

                                    style="
                                        background:
                                        ${getInfrastructureColor(type)}
                                    "
                                ></span>

                                ${escapeHtml(type)}

                            </div>


                            <div class="type-stat-count">

                                ${count}

                            </div>

                        </div>
                    `;
                }
            )
            .join("");
}


/* =========================================================
   TEST EVENT STATUS
========================================================= */

async function loadTestEventStatus() {

    try {

        const response =
            await fetch(
                `${API_URL}/test-event`
            );


        if (!response.ok) {

            throw new Error(
                "Test event status request failed"
            );
        }


        const data =
            await response.json();


        activeTestEvent =
            data.event
            || null;


        updateTestControls();

    }

    catch (error) {

        console.error(
            "Test event status error:",
            error
        );
    }
}


/* =========================================================
   UPDATE TEST CONTROLS
========================================================= */

function updateTestControls() {

    const indicator =
        document.getElementById(
            "testModeIndicator"
        );


    const status =
        document.getElementById(
            "testEventStatus"
        );


    const createButton =
        document.getElementById(
            "createTestEvent"
        );


    const removeButton =
        document.getElementById(
            "removeTestEvent"
        );


    if (
        !indicator
        ||
        !status
        ||
        !createButton
        ||
        !removeButton
    ) {

        return;
    }


    if (activeTestEvent) {

        indicator.textContent =
            "ACTIVE";


        indicator.classList.remove(
            "inactive"
        );


        indicator.classList.add(
            "active"
        );


        createButton.disabled =
            true;


        removeButton.disabled =
            false;


        status.innerHTML = `
            <strong>
                LOCAL TEST EVENT ACTIVE
            </strong>

            <br>

            ${escapeHtml(
                activeTestEvent.title
                || ""
            )}

            <br>

            ${escapeHtml(
                activeTestEvent.target_asset_name
                ||
                activeTestEvent.place
                ||
                ""
            )}

            <br>

            Radius:

            ${Number(
                activeTestEvent.radius_km
                || 0
            )}
            km

            <br>

            <span
                style="
                    color:#748b9c;
                "
            >
                Project-only simulation.
                Nothing is sent externally.
            </span>
        `;

    }

    else {

        indicator.textContent =
            "OFF";


        indicator.classList.remove(
            "active"
        );


        indicator.classList.add(
            "inactive"
        );


        createButton.disabled =
            false;


        removeButton.disabled =
            true;


        status.textContent =
            "No simulated event active.";
    }
}


/* =========================================================
   CREATE TEST EVENT
========================================================= */

async function createTestEvent() {

    const assetElement =
        document.getElementById(
            "testAsset"
        );


    const magnitudeElement =
        document.getElementById(
            "testMagnitude"
        );


    const radiusElement =
        document.getElementById(
            "testRadius"
        );


    if (
        !assetElement
        ||
        !magnitudeElement
        ||
        !radiusElement
    ) {

        return;
    }


    const assetId =
        Number(
            assetElement.value
        );


    const magnitude =
        Number(
            magnitudeElement.value
        );


    const radiusKm =
        Number(
            radiusElement.value
        );


    if (!assetId) {

        showTestMessage(
            "Select an infrastructure asset first.",
            true
        );

        return;
    }


    if (
        !Number.isFinite(
            magnitude
        )
        ||
        magnitude < 2.5
        ||
        magnitude > 9.5
    ) {

        showTestMessage(
            "Magnitude must be between 2.5 and 9.5.",
            true
        );

        return;
    }


    if (
        !Number.isFinite(
            radiusKm
        )
        ||
        radiusKm <= 0
    ) {

        showTestMessage(
            "Enter a valid radius.",
            true
        );

        return;
    }


    const button =
        document.getElementById(
            "createTestEvent"
        );


    if (button) {

        button.disabled =
            true;

        button.textContent =
            "Creating...";
    }


    try {

        const response =
            await fetch(
                `${API_URL}/test-event`,
                {
                    method:
                        "POST",

                    headers:
                        {
                            "Content-Type":
                                "application/json"
                        },

                    body:
                        JSON.stringify(
                            {
                                asset_id:
                                    assetId,

                                magnitude:
                                    magnitude,

                                radius_km:
                                    radiusKm,

                                latitude_offset:
                                    0,

                                longitude_offset:
                                    0
                            }
                        )
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail
                ||
                "Unable to create test event"
            );
        }


        activeTestEvent =
            data.event
            || null;


        updateTestControls();


        showTestMessage(
            "Local test earthquake created. No external system was contacted.",
            false
        );


        await refreshDashboard();


        if (
            activeTestEvent
            &&
            activeTestEvent.latitude != null
            &&
            activeTestEvent.longitude != null
        ) {

            map.flyTo(
                [
                    activeTestEvent.latitude,
                    activeTestEvent.longitude
                ],
                8,
                {
                    duration:
                        1.2
                }
            );
        }

    }

    catch (error) {

        console.error(
            "Create test event error:",
            error
        );


        showTestMessage(
            error.message,
            true
        );

    }

    finally {

        if (button) {

            button.textContent =
                "Create Test Earthquake";
        }


        updateTestControls();
    }
}


/* =========================================================
   REMOVE TEST EVENT
========================================================= */

async function removeTestEvent() {

    const button =
        document.getElementById(
            "removeTestEvent"
        );


    if (button) {

        button.disabled =
            true;

        button.textContent =
            "Removing...";
    }


    try {

        const response =
            await fetch(
                `${API_URL}/test-event`,
                {
                    method:
                        "DELETE"
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail
                ||
                "Unable to remove test event"
            );
        }


        activeTestEvent =
            null;


        showTestMessage(
            "Local test earthquake removed.",
            false
        );


        await refreshDashboard();


        map.setView(
            [20, 5],
            2
        );

    }

    catch (error) {

        console.error(
            "Remove test event error:",
            error
        );


        showTestMessage(
            error.message,
            true
        );

    }

    finally {

        if (button) {

            button.textContent =
                "Remove Test Earthquake";
        }


        updateTestControls();
    }
}


/* =========================================================
   TEST MESSAGE
========================================================= */

function showTestMessage(
    message,
    isError
) {

    const status =
        document.getElementById(
            "testEventStatus"
        );


    if (!status) {

        return;
    }


    status.textContent =
        message;


    status.classList.toggle(
        "error",
        Boolean(
            isError
        )
    );
}





/* =========================================================
   PHASE 6.5 TELEMETRY ALERTING
========================================================= */

function setTelemetryAlertStatus(
    state,
    text
) {

    const element =
        document.getElementById(
            "telemetryAlertStatus"
        );

    if (!element) {
        return;
    }

    element.className =
        `telemetry-alert-status ${state}`;

    element.textContent =
        text;
}


function updateTelemetryAlertSummary(
    summary
) {

    telemetryAlertSummary = {
        ...telemetryAlertSummary,
        ...(summary || {})
    };

    setTextIfExists(
        "telemetryAlertTotal",
        telemetryAlertSummary.total || 0
    );

    setTextIfExists(
        "telemetryAlertCritical",
        telemetryAlertSummary.critical || 0
    );

    setTextIfExists(
        "telemetryAlertHigh",
        telemetryAlertSummary.high || 0
    );

    setTextIfExists(
        "telemetryAlertMedium",
        telemetryAlertSummary.medium || 0
    );

    setTextIfExists(
        "telemetryTrendAlertCount",
        telemetryAlertSummary.trend_alerts || 0
    );

    setTextIfExists(
        "telemetryAlertAssets",
        telemetryAlertSummary.affected_assets || 0
    );

    const meta =
        document.getElementById(
            "telemetryAlertMeta"
        );

    if (meta) {

        meta.textContent =
            `Trend window: ${telemetryAlertWindowMinutes} min · `
            +
            `${telemetryAlertSummary.threshold_alerts || 0} threshold · `
            +
            `${telemetryAlertSummary.trend_alerts || 0} trend`;
    }
}


function renderTelemetryAlerts() {

    const container =
        document.getElementById(
            "telemetryAlertFeed"
        );

    if (!container) {
        return;
    }

    const severitySelect =
        document.getElementById(
            "telemetryAlertSeverity"
        );

    const selectedSeverity =
        severitySelect
            ? severitySelect.value
            : "all";

    const alerts =
        telemetryAlertData.filter(
            alert =>
                selectedSeverity === "all"
                ||
                alert.severity
                === selectedSeverity
        );

    if (
        alerts.length === 0
    ) {

        container.innerHTML = `
            <div class="empty-state">
                No active telemetry alerts for the selected severity.
            </div>
        `;

        return;
    }

    container.innerHTML =
        alerts
            .slice(
                0,
                25
            )
            .map(
                alert => {

                    const severity =
                        escapeHtml(
                            alert.severity
                            || "low"
                        );

                    const kind =
                        escapeHtml(
                            alert.alert_kind
                            || "threshold"
                        );

                    const latest =
                        formatTelemetryAlertValue(
                            alert.latest_value,
                            alert.unit
                        );

                    const reference =
                        alert.reference_value
                        == null
                            ? ""
                            : `
                                <span class="telemetry-alert-detail">
                                    Start:
                                    ${formatTelemetryAlertValue(
                                        alert.reference_value,
                                        alert.unit
                                    )}
                                </span>
                            `;

                    const delta =
                        alert.delta
                        == null
                            ? ""
                            : `
                                <span class="telemetry-alert-detail">
                                    Change:
                                    ${Number(alert.delta).toFixed(2)}
                                    ${escapeHtml(alert.unit || "")}
                                </span>
                            `;

                    return `
                        <button
                            type="button"
                            class="
                                telemetry-alert-item
                                severity-${severity}
                            "
                            onclick="focusTelemetryAlertAsset(${Number(alert.asset_id)})"
                        >

                            <div class="telemetry-alert-item-header">

                                <strong>
                                    ${escapeHtml(
                                        String(
                                            alert.asset_name
                                            || `Asset ${alert.asset_id}`
                                        )
                                    )}
                                </strong>

                                <span
                                    class="
                                        telemetry-alert-severity
                                        severity-${severity}
                                    "
                                >
                                    ${severity.toUpperCase()}
                                </span>

                            </div>

                            <div class="telemetry-alert-message">
                                ${escapeHtml(
                                    alert.message
                                    || "Telemetry anomaly detected"
                                )}
                            </div>

                            <div class="telemetry-alert-metric-row">

                                <span>
                                    ${escapeHtml(
                                        alert.metric_label
                                        || alert.metric
                                        || "Metric"
                                    )}
                                </span>

                                <strong>
                                    ${latest}
                                </strong>

                            </div>

                            <div class="telemetry-alert-kind-row">

                                <span class="telemetry-alert-kind">
                                    ${kind.toUpperCase()}
                                </span>

                                ${reference}

                                ${delta}

                            </div>

                        </button>
                    `;
                }
            )
            .join("");
}


function formatTelemetryAlertValue(
    value,
    unit
) {

    const numeric =
        Number(value);

    if (!Number.isFinite(numeric)) {
        return "--";
    }

    const absolute =
        Math.abs(numeric);

    const decimals =
        absolute >= 100
            ? 0
            : absolute >= 10
                ? 1
                : 2;

    return (
        numeric.toFixed(decimals)
        +
        escapeHtml(
            unit || ""
        )
    );
}


function focusTelemetryAlertAsset(
    assetId
) {

    const point =
        infrastructureData.find(
            item =>
                Number(item.id)
                ===
                Number(assetId)
        );

    if (!point) {
        return;
    }

    selectHistoryAsset(
        assetId,
        true
    );

    focusAsset(
        point.latitude,
        point.longitude
    );

    const marker =
        assetMarkers.get(
            Number(assetId)
        );

    if (!marker) {
        return;
    }

    setTimeout(
        () => {

            if (
                clusterGroup
                &&
                typeof clusterGroup.zoomToShowLayer
                === "function"
            ) {

                clusterGroup.zoomToShowLayer(
                    marker,
                    () => {
                        marker.openPopup();
                    }
                );
            }

            else {
                marker.openPopup();
            }
        },
        450
    );
}


async function loadTelemetryAlerts() {

    try {

        const response =
            await fetch(
                `${API_URL}/telemetry-alerts`
            );

        if (!response.ok) {

            throw new Error(
                "Telemetry alerts request failed"
            );
        }

        const payload =
            await response.json();

        if (
            payload.source
            !== "LOCAL_PROJECT"
            ||
            payload.external
            !== false
        ) {

            throw new Error(
                "Unexpected telemetry alert source"
            );
        }

        telemetryAlertData =
            payload.alerts
            || [];

        telemetryAlertWindowMinutes =
            Number(
                payload.window_minutes
                || 5
            );

        updateTelemetryAlertSummary(
            payload.summary
            || {}
        );

        renderTelemetryAlerts();

        setTelemetryAlertStatus(
            "live",
            "LIVE"
        );
    }

    catch (error) {

        console.error(
            "Telemetry alerts load error:",
            error
        );

        setTelemetryAlertStatus(
            "error",
            "ERROR"
        );
    }
}


function connectTelemetryAlertSocket() {

    telemetryAlertSocket =
        new WebSocket(
            `${getWebSocketBaseURL()}/ws/telemetry-alerts`
        );

    telemetryAlertSocket.onopen =
        () => {

            console.log(
                "Telemetry alert WebSocket connected"
            );

            setTelemetryAlertStatus(
                "live",
                "LIVE"
            );
        };

    telemetryAlertSocket.onmessage =
        event => {

            try {

                const message =
                    JSON.parse(
                        event.data
                    );

                if (
                    message.type
                    !== "telemetry_alerts"
                ) {

                    return;
                }

                if (
                    message.source
                    !== "LOCAL_PROJECT"
                    ||
                    message.external
                    !== false
                ) {

                    console.warn(
                        "Rejected unexpected telemetry alert stream."
                    );

                    return;
                }

                telemetryAlertData =
                    message.alerts
                    || [];

                telemetryAlertWindowMinutes =
                    Number(
                        message.window_minutes
                        || 5
                    );

                updateTelemetryAlertSummary(
                    message.summary
                    || {}
                );

                renderTelemetryAlerts();

                loadPersistedTelemetryAlerts();

                setTelemetryAlertStatus(
                    "live",
                    "LIVE"
                );
            }

            catch (error) {

                console.error(
                    "Telemetry alert WebSocket message error:",
                    error
                );
            }
        };

    telemetryAlertSocket.onerror =
        error => {

            console.error(
                "Telemetry alert WebSocket error:",
                error
            );

            setTelemetryAlertStatus(
                "error",
                "ERROR"
            );
        };

    telemetryAlertSocket.onclose =
        () => {

            console.log(
                "Telemetry alert WebSocket disconnected. Reconnecting..."
            );

            setTelemetryAlertStatus(
                "connecting",
                "RECONNECTING"
            );

            setTimeout(
                connectTelemetryAlertSocket,
                5000
            );
        };
}


/* =========================================================
   PHASE 6.6
   PERSISTED TELEMETRY ALERT LIFECYCLE
========================================================= */

function setPersistedAlertStatus(
    state,
    text
) {

    const element =
        document.getElementById(
            "persistedAlertStatus"
        );

    if (!element) {
        return;
    }

    element.className =
        `persisted-alert-status ${state}`;

    element.textContent =
        text;
}


function getPersistedAlertOperator() {

    const input =
        document.getElementById(
            "persistedAlertOperator"
        );

    const value =
        input
            ? input.value.trim()
            : "";

    return value || "operator";
}


function formatAlertTimestamp(
    value
) {

    if (!value) {
        return "—";
    }

    const date =
        new Date(
            value
        );

    if (
        Number.isNaN(
            date.getTime()
        )
    ) {
        return String(value);
    }

    return date.toLocaleString();
}


function calculatePersistedAlertCounts() {

    return persistedTelemetryAlerts.reduce(
        (
            summary,
            alert
        ) => {

            const status =
                String(
                    alert.status
                    || "active"
                );

            if (
                Object.prototype.hasOwnProperty.call(
                    summary,
                    status
                )
            ) {

                summary[
                    status
                ] += 1;
            }

            return summary;
        },
        {
            active: 0,
            acknowledged: 0,
            resolved: 0
        }
    );
}


function updatePersistedAlertSummary() {

    const summary =
        calculatePersistedAlertCounts();

    setTextIfExists(
        "persistedAlertActive",
        summary.active
    );

    setTextIfExists(
        "persistedAlertAcknowledged",
        summary.acknowledged
    );

    setTextIfExists(
        "persistedAlertResolved",
        summary.resolved
    );

    const meta =
        document.getElementById(
            "persistedAlertMeta"
        );

    if (meta) {

        const lastUpdated =
            persistedAlertLastUpdatedAt
                ? persistedAlertLastUpdatedAt.toLocaleTimeString()
                : "—";

        meta.textContent =
            `${persistedTelemetryAlerts.length} persisted · `
            +
            `updated ${lastUpdated}`;
    }
}


function persistedAlertStatusLabel(
    status
) {

    const value =
        String(
            status
            || "active"
        ).toLowerCase();

    if (
        value
        === "acknowledged"
    ) {

        return "ACKNOWLEDGED";
    }

    if (
        value
        === "resolved"
    ) {

        return "RESOLVED";
    }

    return "ACTIVE";
}


function renderPersistedAlerts() {

    const container =
        document.getElementById(
            "persistedAlertFeed"
        );

    if (!container) {
        return;
    }

    const statusSelect =
        document.getElementById(
            "persistedAlertStatusFilter"
        );

    const severitySelect =
        document.getElementById(
            "persistedAlertSeverityFilter"
        );

    const selectedStatus =
        statusSelect
            ? statusSelect.value
            : "all";

    const selectedSeverity =
        severitySelect
            ? severitySelect.value
            : "all";

    const alerts =
        persistedTelemetryAlerts.filter(
            alert => {

                const matchesStatus =
                    selectedStatus === "all"
                    ||
                    alert.status === selectedStatus;

                const matchesSeverity =
                    selectedSeverity === "all"
                    ||
                    alert.severity === selectedSeverity;

                return (
                    matchesStatus
                    &&
                    matchesSeverity
                );
            }
        );

    if (
        alerts.length === 0
    ) {

        container.innerHTML = `
            <div class="empty-state">
                No persisted alerts match the selected filters.
            </div>
        `;

        return;
    }

    container.innerHTML =
        alerts
            .slice(
                0,
                100
            )
            .map(
                alert => {

                    const id =
                        Number(
                            alert.id
                        );

                    const assetId =
                        Number(
                            alert.asset_id
                        );

                    const severity =
                        escapeHtml(
                            alert.severity
                            || "low"
                        );

                    const status =
                        escapeHtml(
                            alert.status
                            || "active"
                        );

                    const canAcknowledge =
                        status === "active";

                    const canResolve =
                        (
                            status === "active"
                            ||
                            status === "acknowledged"
                        );

                    const latestValue =
                        formatTelemetryAlertValue(
                            alert.latest_value,
                            alert.unit
                        );

                    return `
                        <article
                            class="
                                persisted-alert-card
                                severity-${severity}
                                status-${status}
                            "
                            data-alert-id="${id}"
                        >

                            <div class="persisted-alert-card-header">

                                <button
                                    type="button"
                                    class="persisted-alert-asset"
                                    data-focus-asset="${assetId}"
                                >
                                    ${escapeHtml(
                                        String(
                                            alert.asset_name
                                            || `Asset ${assetId}`
                                        )
                                    )}
                                </button>

                                <div class="persisted-alert-badges">

                                    <span
                                        class="
                                            persisted-alert-badge
                                            severity-${severity}
                                        "
                                    >
                                        ${severity.toUpperCase()}
                                    </span>

                                    <span
                                        class="
                                            persisted-alert-badge
                                            state-${status}
                                        "
                                    >
                                        ${persistedAlertStatusLabel(
                                            status
                                        )}
                                    </span>

                                </div>

                            </div>

                            <div class="persisted-alert-message">
                                ${escapeHtml(
                                    alert.message
                                    || "Telemetry alert"
                                )}
                            </div>

                            <div class="persisted-alert-metric">

                                <span>
                                    ${escapeHtml(
                                        alert.metric_label
                                        || alert.metric
                                        || "Metric"
                                    )}
                                </span>

                                <strong>
                                    ${latestValue}
                                </strong>

                            </div>

                            <div class="persisted-alert-times">

                                <span>
                                    First:
                                    ${escapeHtml(
                                        formatAlertTimestamp(
                                            alert.first_seen_at
                                        )
                                    )}
                                </span>

                                <span>
                                    Last:
                                    ${escapeHtml(
                                        formatAlertTimestamp(
                                            alert.last_seen_at
                                        )
                                    )}
                                </span>

                                ${
                                    alert.acknowledged_at
                                        ? `
                                            <span>
                                                Ack:
                                                ${escapeHtml(
                                                    formatAlertTimestamp(
                                                        alert.acknowledged_at
                                                    )
                                                )}
                                                ${
                                                    alert.acknowledged_by
                                                        ? ` · ${escapeHtml(alert.acknowledged_by)}`
                                                        : ""
                                                }
                                            </span>
                                        `
                                        : ""
                                }

                                ${
                                    alert.resolved_at
                                        ? `
                                            <span>
                                                Resolved:
                                                ${escapeHtml(
                                                    formatAlertTimestamp(
                                                        alert.resolved_at
                                                    )
                                                )}
                                                ${
                                                    alert.resolved_by
                                                        ? ` · ${escapeHtml(alert.resolved_by)}`
                                                        : ""
                                                }
                                            </span>
                                        `
                                        : ""
                                }

                            </div>

                            ${
                                alert.resolution_note
                                    ? `
                                        <div class="persisted-alert-note">
                                            ${escapeHtml(
                                                alert.resolution_note
                                            )}
                                        </div>
                                    `
                                    : ""
                            }

                            <div class="persisted-alert-actions">

                                <button
                                    type="button"
                                    class="persisted-alert-action history"
                                    data-alert-action="history"
                                    data-alert-id="${id}"
                                >
                                    History
                                </button>

                                <button
                                    type="button"
                                    class="persisted-alert-action acknowledge"
                                    data-alert-action="acknowledge"
                                    data-alert-id="${id}"
                                    ${canAcknowledge ? "" : "disabled"}
                                >
                                    Acknowledge
                                </button>

                                <button
                                    type="button"
                                    class="persisted-alert-action resolve"
                                    data-alert-action="resolve"
                                    data-alert-id="${id}"
                                    ${canResolve ? "" : "disabled"}
                                >
                                    Resolve
                                </button>

                            </div>

                        </article>
                    `;
                }
            )
            .join("");
}


async function loadPersistedTelemetryAlerts() {

    if (
        persistedAlertRequestInFlight
    ) {
        return;
    }

    persistedAlertRequestInFlight =
        true;

    setPersistedAlertStatus(
        "loading",
        "LOADING"
    );

    try {

        const response =
            await fetch(
                `${API_URL}/telemetry-alert-history?limit=1000`
            );

        if (!response.ok) {

            throw new Error(
                `Persisted alert request failed (${response.status})`
            );
        }

        const payload =
            await response.json();

        if (
            payload.source
            !== "LOCAL_PROJECT"
            ||
            payload.external
            !== false
        ) {

            throw new Error(
                "Unexpected persisted alert source"
            );
        }

        persistedTelemetryAlerts =
            Array.isArray(
                payload.alerts
            )
                ? payload.alerts
                : [];

        persistedAlertLastUpdatedAt =
            new Date();

        updatePersistedAlertSummary();

        renderPersistedAlerts();

        setPersistedAlertStatus(
            "ready",
            "READY"
        );
    }

    catch (error) {

        console.error(
            "Persisted telemetry alert load error:",
            error
        );

        setPersistedAlertStatus(
            "error",
            "ERROR"
        );

        const container =
            document.getElementById(
                "persistedAlertFeed"
            );

        if (container) {

            container.innerHTML = `
                <div class="empty-state error-state">
                    Unable to load persisted alerts.
                </div>
            `;
        }
    }

    finally {

        persistedAlertRequestInFlight =
            false;
    }
}


async function postPersistedAlertAction(
    alertId,
    action
) {

    const alert =
        persistedTelemetryAlerts.find(
            item =>
                Number(
                    item.id
                )
                ===
                Number(
                    alertId
                )
        );

    if (!alert) {
        return;
    }

    const operator =
        getPersistedAlertOperator();

    let note =
        null;

    if (
        action === "acknowledge"
    ) {

        note =
            window.prompt(
                "Acknowledgement note (optional):",
                "Investigating telemetry alert"
            );

        if (
            note === null
        ) {
            return;
        }
    }

    else if (
        action === "resolve"
    ) {

        note =
            window.prompt(
                "Resolution note:",
                "Issue investigated and resolved"
            );

        if (
            note === null
        ) {
            return;
        }
    }

    const endpoint =
        action === "acknowledge"
            ? "acknowledge"
            : "resolve";

    setPersistedAlertStatus(
        "loading",
        "UPDATING"
    );

    try {

        const response =
            await fetch(
                `${API_URL}/telemetry-alerts/${Number(alertId)}/${endpoint}`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify(
                        {
                            changed_by:
                                operator,

                            note:
                                note
                                ? note.trim()
                                : null
                        }
                    )
                }
            );

        const payload =
            await response.json()
                .catch(
                    () => ({})
                );

        if (!response.ok) {

            throw new Error(
                payload.detail
                ||
                `Alert ${endpoint} failed (${response.status})`
            );
        }

        await loadPersistedTelemetryAlerts();

        if (
            selectedPersistedAlertId
            ===
            Number(
                alertId
            )
        ) {

            await openAlertHistory(
                alertId
            );
        }
    }

    catch (error) {

        console.error(
            `Persisted alert ${endpoint} error:`,
            error
        );

        setPersistedAlertStatus(
            "error",
            "ERROR"
        );

        window.alert(
            error.message
            ||
            `Unable to ${endpoint} alert.`
        );
    }
}


function closeAlertHistory() {

    const modal =
        document.getElementById(
            "alertHistoryModal"
        );

    if (!modal) {
        return;
    }

    modal.classList.remove(
        "open"
    );

    modal.setAttribute(
        "aria-hidden",
        "true"
    );

    selectedPersistedAlertId =
        null;
}


function renderAlertHistoryTimeline(
    alert,
    history
) {

    const summary =
        document.getElementById(
            "alertHistorySummary"
        );

    const timeline =
        document.getElementById(
            "alertHistoryTimeline"
        );

    if (
        !summary
        ||
        !timeline
    ) {

        return;
    }

    const severity =
        escapeHtml(
            alert.severity
            || "low"
        );

    const status =
        escapeHtml(
            alert.status
            || "active"
        );

    summary.innerHTML = `
        <div class="alert-history-summary-title">

            <strong>
                ${escapeHtml(
                    alert.asset_name
                    || `Asset ${alert.asset_id}`
                )}
            </strong>

            <span
                class="
                    persisted-alert-badge
                    severity-${severity}
                "
            >
                ${severity.toUpperCase()}
            </span>

            <span
                class="
                    persisted-alert-badge
                    state-${status}
                "
            >
                ${persistedAlertStatusLabel(status)}
            </span>

        </div>

        <div class="alert-history-summary-message">
            ${escapeHtml(
                alert.message
                || "Telemetry alert"
            )}
        </div>

        <div class="alert-history-summary-meta">
            Alert #${Number(alert.id)}
            · Asset #${Number(alert.asset_id)}
            · ${escapeHtml(alert.alert_kind || "threshold")}
        </div>
    `;

    if (
        !Array.isArray(history)
        ||
        history.length === 0
    ) {

        timeline.innerHTML = `
            <div class="empty-state">
                No lifecycle events have been recorded for this alert.
            </div>
        `;

        return;
    }

    timeline.innerHTML =
        history
            .map(
                event => {

                    const action =
                        escapeHtml(
                            event.action
                            || "EVENT"
                        );

                    const fromStatus =
                        event.from_status
                            ? escapeHtml(
                                event.from_status
                            )
                            : "—";

                    const toStatus =
                        event.to_status
                            ? escapeHtml(
                                event.to_status
                            )
                            : "—";

                    return `
                        <div class="alert-history-event">

                            <div class="alert-history-event-dot"></div>

                            <div class="alert-history-event-body">

                                <div class="alert-history-event-header">

                                    <strong>
                                        ${action.replaceAll("_", " ")}
                                    </strong>

                                    <span>
                                        ${escapeHtml(
                                            formatAlertTimestamp(
                                                event.changed_at
                                            )
                                        )}
                                    </span>

                                </div>

                                <div class="alert-history-transition">
                                    ${fromStatus}
                                    <span>→</span>
                                    ${toStatus}
                                </div>

                                ${
                                    event.note
                                        ? `
                                            <div class="alert-history-event-note">
                                                ${escapeHtml(event.note)}
                                            </div>
                                        `
                                        : ""
                                }

                                <div class="alert-history-event-meta">
                                    ${escapeHtml(event.changed_by || "SYSTEM")}
                                    ·
                                    ${escapeHtml(event.severity || alert.severity || "low")}
                                </div>

                            </div>

                        </div>
                    `;
                }
            )
            .join("");
}


async function openAlertHistory(
    alertId
) {

    const id =
        Number(
            alertId
        );

    const alert =
        persistedTelemetryAlerts.find(
            item =>
                Number(
                    item.id
                )
                === id
        );

    if (!alert) {
        return;
    }

    selectedPersistedAlertId =
        id;

    const modal =
        document.getElementById(
            "alertHistoryModal"
        );

    const timeline =
        document.getElementById(
            "alertHistoryTimeline"
        );

    if (
        !modal
        ||
        !timeline
    ) {

        return;
    }

    modal.classList.add(
        "open"
    );

    modal.setAttribute(
        "aria-hidden",
        "false"
    );

    timeline.innerHTML = `
        <div class="empty-state">
            Loading alert history...
        </div>
    `;

    try {

        const response =
            await fetch(
                `${API_URL}/telemetry-alert-history/${id}/events`
            );

        if (!response.ok) {

            throw new Error(
                `Alert history request failed (${response.status})`
            );
        }

        const payload =
            await response.json();

        if (
            payload.source
            !== "LOCAL_PROJECT"
            ||
            payload.external
            !== false
        ) {

            throw new Error(
                "Unexpected alert history source"
            );
        }

        renderAlertHistoryTimeline(
            alert,
            payload.history
            || []
        );
    }

    catch (error) {

        console.error(
            "Alert history load error:",
            error
        );

        timeline.innerHTML = `
            <div class="empty-state error-state">
                Unable to load lifecycle history.
            </div>
        `;
    }
}


async function handlePersistedAlertFeedClick(
    event
) {

    const focusButton =
        event.target.closest(
            "[data-focus-asset]"
        );

    if (focusButton) {

        focusTelemetryAlertAsset(
            Number(
                focusButton.dataset.focusAsset
            )
        );

        return;
    }

    const actionButton =
        event.target.closest(
            "[data-alert-action]"
        );

    if (
        !actionButton
        ||
        actionButton.disabled
    ) {

        return;
    }

    const alertId =
        Number(
            actionButton.dataset.alertId
        );

    const action =
        actionButton.dataset.alertAction;

    if (
        action === "history"
    ) {

        await openAlertHistory(
            alertId
        );

        return;
    }

    if (
        action === "acknowledge"
        ||
        action === "resolve"
    ) {

        await postPersistedAlertAction(
            alertId,
            action
        );
    }
}


/* =========================================================
   PHASE 6.4 TELEMETRY HISTORY
========================================================= */

function setTelemetryHistoryStatus(
    state,
    text
) {

    const element =
        document.getElementById(
            "telemetryHistoryStatus"
        );

    if (!element) {
        return;
    }

    element.className =
        `history-status ${state}`;

    element.textContent =
        text;
}



function updateTelemetryRefreshUI() {

    const button =
        document.getElementById(
            "toggleHistoryRefresh"
        );

    const dot =
        document.getElementById(
            "historyRefreshDot"
        );

    const mode =
        document.getElementById(
            "historyRefreshMode"
        );

    if (button) {

        button.textContent =
            telemetryHistoryPaused
                ? "Resume"
                : "Pause";

        button.setAttribute(
            "aria-pressed",
            telemetryHistoryPaused
                ? "true"
                : "false"
        );

        button.title =
            telemetryHistoryPaused
                ? "Resume automatic telemetry history refresh"
                : "Pause automatic telemetry history refresh";

        button.classList.toggle(
            "paused",
            telemetryHistoryPaused
        );
    }

    if (dot) {

        dot.classList.toggle(
            "live",
            !telemetryHistoryPaused
        );

        dot.classList.toggle(
            "paused",
            telemetryHistoryPaused
        );
    }

    if (mode) {

        mode.textContent =
            telemetryHistoryPaused
                ? "Auto-refresh paused"
                : "Auto-refresh active";
    }

    updateTelemetryLastUpdatedLabel();
}


function updateTelemetryLastUpdatedLabel() {

    const element =
        document.getElementById(
            "historyLastUpdated"
        );

    if (!element) {
        return;
    }

    if (!telemetryHistoryLastUpdatedAt) {

        element.textContent =
            "Last updated: Never";

        return;
    }

    const formatted =
        telemetryHistoryLastUpdatedAt
            .toLocaleTimeString(
                [],
                {
                    hour:
                        "2-digit",

                    minute:
                        "2-digit",

                    second:
                        "2-digit"
                }
            );

    element.textContent =
        `Last updated: ${formatted}`;
}


function toggleTelemetryHistoryRefresh() {

    telemetryHistoryPaused =
        !telemetryHistoryPaused;

    if (
        telemetryHistoryPaused
    ) {

        if (
            telemetryHistoryTimer
            != null
        ) {

            clearInterval(
                telemetryHistoryTimer
            );

            telemetryHistoryTimer =
                null;
        }

        setTelemetryHistoryStatus(
            "paused",
            "PAUSED"
        );
    }

    else {

        startTelemetryHistoryRefresh();

        setTelemetryHistoryStatus(
            "ready",
            "LIVE"
        );

        if (
            selectedHistoryAssetId
            != null
        ) {

            loadTelemetryHistory();
        }
    }

    updateTelemetryRefreshUI();
}


function selectHistoryAsset(
    assetId,
    loadNow = true
) {

    const id =
        Number(assetId);

    if (
        !Number.isFinite(id)
        ||
        id <= 0
    ) {

        return;
    }

    selectedHistoryAssetId =
        id;

    const select =
        document.getElementById(
            "historyAsset"
        );

    if (select) {
        select.value =
            String(id);
    }

    if (loadNow) {
        loadTelemetryHistory();
    }
}


async function loadTelemetryHistory() {

    const assetSelect =
        document.getElementById(
            "historyAsset"
        );

    const rangeSelect =
        document.getElementById(
            "historyRange"
        );

    const assetId =
        Number(
            assetSelect?.value
            || selectedHistoryAssetId
            || 0
        );

    const hours =
        Number(
            rangeSelect?.value
            || 24
        );

    if (
        !Number.isFinite(assetId)
        ||
        assetId <= 0
    ) {

        showTelemetryHistoryEmpty(
            "Select an infrastructure asset to load persisted telemetry history."
        );

        return;
    }

    selectedHistoryAssetId =
        assetId;

    setTelemetryHistoryStatus(
        "loading",
        "LOADING"
    );

    try {

        const [
            historyResponse,
            summaryResponse
        ] = await Promise.all(
            [
                fetch(
                    `${API_URL}/telemetry-history/${assetId}?hours=${hours}&limit=5000`
                ),

                fetch(
                    `${API_URL}/telemetry-summary/${assetId}?hours=${hours}`
                )
            ]
        );

        if (!historyResponse.ok) {

            throw new Error(
                "Telemetry history request failed"
            );
        }

        if (!summaryResponse.ok) {

            throw new Error(
                "Telemetry summary request failed"
            );
        }

        const historyPayload =
            await historyResponse.json();

        const summaryPayload =
            await summaryResponse.json();

        if (
            historyPayload.source !== "LOCAL_PROJECT"
            ||
            historyPayload.external !== false
        ) {

            throw new Error(
                "Unexpected telemetry history source"
            );
        }

        if (
            summaryPayload.source !== "LOCAL_PROJECT"
            ||
            summaryPayload.external !== false
        ) {

            throw new Error(
                "Unexpected telemetry summary source"
            );
        }

        telemetryHistoryRecords =
            Array.isArray(
                historyPayload.records
            )
                ? historyPayload.records
                : [];

        renderTelemetryHistory(
            telemetryHistoryRecords,
            summaryPayload.summary || {}
        );

        telemetryHistoryLastUpdatedAt =
            new Date();

        updateTelemetryLastUpdatedLabel();

        if (
            telemetryHistoryPaused
        ) {

            setTelemetryHistoryStatus(
                "paused",
                "PAUSED"
            );
        }

        else {

            setTelemetryHistoryStatus(
                "ready",
                "LIVE"
            );
        }

    }

    catch (error) {

        console.error(
            "Telemetry history load error:",
            error
        );

        setTelemetryHistoryStatus(
            "error",
            "ERROR"
        );

        showTelemetryHistoryEmpty(
            "Unable to load telemetry history. Check the Phase 6.4 backend API."
        );
    }
}


function showTelemetryHistoryEmpty(message) {

    const empty =
        document.getElementById(
            "telemetryHistoryEmpty"
        );

    const charts =
        document.getElementById(
            "telemetryCharts"
        );

    if (empty) {

        empty.textContent =
            message;

        empty.classList.remove(
            "hidden"
        );
    }

    if (charts) {

        charts.classList.add(
            "hidden"
        );
    }

    setTextIfExists(
        "historySamples",
        "0"
    );

    setTextIfExists(
        "historyAvgHealth",
        "--"
    );

    setTextIfExists(
        "historyAvgCpu",
        "--"
    );

    setTextIfExists(
        "historyAvgTemp",
        "--"
    );
}


function renderTelemetryHistory(
    records,
    summary
) {

    const chronological =
        [...records]
            .reverse();

    setTextIfExists(
        "historySamples",
        Number(
            summary.samples
            ?? records.length
            ?? 0
        )
    );

    setTextIfExists(
        "historyAvgHealth",
        formatMetricValue(
            summary.avg_health,
            "%",
            1
        )
    );

    setTextIfExists(
        "historyAvgCpu",
        formatMetricValue(
            summary.avg_cpu_percent,
            "%",
            1
        )
    );

    setTextIfExists(
        "historyAvgTemp",
        formatMetricValue(
            summary.avg_temperature_c,
            "°C",
            1
        )
    );

    if (
        chronological.length === 0
    ) {

        showTelemetryHistoryEmpty(
            "No historical telemetry exists for this asset in the selected time range yet."
        );

        return;
    }

    const empty =
        document.getElementById(
            "telemetryHistoryEmpty"
        );

    const charts =
        document.getElementById(
            "telemetryCharts"
        );

    if (empty) {
        empty.classList.add(
            "hidden"
        );
    }

    if (charts) {
        charts.classList.remove(
            "hidden"
        );
    }

    const latest =
        chronological[
            chronological.length - 1
        ];

    setTextIfExists(
        "historyHealthLatest",
        formatMetricValue(
            latest.health,
            "%",
            0
        )
    );

    setTextIfExists(
        "historyCpuLatest",
        formatMetricValue(
            latest.cpu_percent,
            "%",
            1
        )
    );

    setTextIfExists(
        "historyTempLatest",
        formatMetricValue(
            latest.temperature_c,
            "°C",
            1
        )
    );

    setTextIfExists(
        "historyLatencyLatest",
        formatMetricValue(
            latest.latency_ms,
            " ms",
            1
        )
    );

    setTextIfExists(
        "historyPacketLossLatest",
        formatMetricValue(
            latest.packet_loss_percent,
            "%",
            2
        )
    );

    renderTelemetryMultiSeriesChart(
        "healthHistoryChart",
        chronological
    );
}


function renderTelemetryMultiSeriesChart(
    containerId,
    records
) {

    const container =
        document.getElementById(
            containerId
        );

    if (!container) {
        return;
    }

    const source =
        Array.isArray(records)
            ? records.filter(
                item =>
                    item
                    &&
                    item.recorded_at
            )
            : [];

    if (source.length < 2) {

        container.innerHTML = `
            <div class="chart-empty-state">
                Waiting for enough historical samples...
            </div>
        `;

        return;
    }

    const width = 1000;
    const height = 245;

    const padding = {
        left: 48,
        right: 18,
        top: 16,
        bottom: 32
    };

    const plotWidth =
        width
        -
        padding.left
        -
        padding.right;

    const plotHeight =
        height
        -
        padding.top
        -
        padding.bottom;

    const metricDefinitions = [
        {
            key: "cpu_percent",
            label: "CPU",
            color: "#25c8ff",
            min: 0,
            max: 100
        },
        {
            key: "health",
            label: "Health",
            color: "#28e4a3",
            min: 0,
            max: 100
        },
        {
            key: "temperature_c",
            label: "Temperature",
            color: "#ffb547"
        },
        {
            key: "latency_ms",
            label: "Latency",
            color: "#a96cff"
        },
        {
            key: "packet_loss_percent",
            label: "Packet Loss",
            color: "#ff5b78"
        }
    ];

    function finiteValues(metric) {

        return source
            .map(
                row =>
                    Number(
                        row[metric.key]
                    )
            )
            .filter(
                Number.isFinite
            );
    }

    function bounds(metric) {

        const values =
            finiteValues(
                metric
            );

        if (!values.length) {

            return {
                min: 0,
                max: 1
            };
        }

        let min =
            Number.isFinite(
                metric.min
            )
                ? metric.min
                : Math.min(
                    ...values
                );

        let max =
            Number.isFinite(
                metric.max
            )
                ? metric.max
                : Math.max(
                    ...values
                );

        if (max === min) {

            const margin =
                Math.max(
                    Math.abs(max) * 0.08,
                    1
                );

            min -= margin;
            max += margin;
        }

        else if (
            !Number.isFinite(
                metric.min
            )
            ||
            !Number.isFinite(
                metric.max
            )
        ) {

            const margin =
                (
                    max
                    -
                    min
                )
                *
                0.12;

            min -= margin;
            max += margin;
        }

        return {
            min,
            max
        };
    }

    function pointFor(
        row,
        index,
        metric,
        metricBounds
    ) {

        const value =
            Number(
                row[
                    metric.key
                ]
            );

        if (!Number.isFinite(value)) {
            return null;
        }

        const x =
            padding.left
            +
            (
                index
                /
                Math.max(
                    source.length - 1,
                    1
                )
            )
            *
            plotWidth;

        const ratio =
            Math.max(
                0,
                Math.min(
                    1,
                    (
                        value
                        -
                        metricBounds.min
                    )
                    /
                    (
                        metricBounds.max
                        -
                        metricBounds.min
                    )
                )
            );

        const y =
            padding.top
            +
            (
                1
                -
                ratio
            )
            *
            plotHeight;

        return {
            x,
            y
        };
    }

    const seriesMarkup =
        metricDefinitions
            .map(
                metric => {

                    const metricBounds =
                        bounds(
                            metric
                        );

                    const points =
                        source
                            .map(
                                (
                                    row,
                                    index
                                ) =>
                                    pointFor(
                                        row,
                                        index,
                                        metric,
                                        metricBounds
                                    )
                            )
                            .filter(Boolean);

                    if (
                        points.length
                        <
                        2
                    ) {
                        return "";
                    }

                    const pointString =
                        points
                            .map(
                                point =>
                                    `${point.x.toFixed(1)},${point.y.toFixed(1)}`
                            )
                            .join(" ");

                    return `
                        <polyline
                            points="${pointString}"
                            fill="none"
                            stroke="${metric.color}"
                            stroke-width="2.4"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            vector-effect="non-scaling-stroke"
                            opacity="0.96"
                        ></polyline>
                    `;
                }
            )
            .join("");

    const horizontalGrid =
        [0, 0.25, 0.5, 0.75, 1]
            .map(
                ratio => {

                    const y =
                        padding.top
                        +
                        ratio
                        *
                        plotHeight;

                    const label =
                        Math.round(
                            100
                            -
                            ratio * 100
                        );

                    return `
                        <line
                            x1="${padding.left}"
                            y1="${y}"
                            x2="${padding.left + plotWidth}"
                            y2="${y}"
                            stroke="rgba(111,151,183,0.13)"
                            stroke-width="1"
                            vector-effect="non-scaling-stroke"
                        ></line>

                        <text
                            x="8"
                            y="${y + 4}"
                            fill="#6f879b"
                            font-size="11"
                            font-family="Inter,system-ui,sans-serif"
                        >${label}%</text>
                    `;
                }
            )
            .join("");

    const sampleIndexes =
        [
            0,
            Math.floor(
                (source.length - 1)
                *
                0.25
            ),
            Math.floor(
                (source.length - 1)
                *
                0.5
            ),
            Math.floor(
                (source.length - 1)
                *
                0.75
            ),
            source.length - 1
        ];

    const verticalGrid =
        sampleIndexes
            .map(
                index => {

                    const x =
                        padding.left
                        +
                        (
                            index
                            /
                            Math.max(
                                source.length - 1,
                                1
                            )
                        )
                        *
                        plotWidth;

                    const timestamp =
                        new Date(
                            source[
                                index
                            ].recorded_at
                        );

                    const label =
                        Number.isNaN(
                            timestamp.getTime()
                        )
                            ? "--:--"
                            : timestamp.toLocaleTimeString(
                                [],
                                {
                                    hour: "2-digit",
                                    minute: "2-digit"
                                }
                            );

                    return `
                        <line
                            x1="${x}"
                            y1="${padding.top}"
                            x2="${x}"
                            y2="${padding.top + plotHeight}"
                            stroke="rgba(111,151,183,0.07)"
                            stroke-width="1"
                            vector-effect="non-scaling-stroke"
                        ></line>

                        <text
                            x="${x}"
                            y="${height - 8}"
                            text-anchor="${
                                index === 0
                                    ? "start"
                                    : index === source.length - 1
                                        ? "end"
                                        : "middle"
                            }"
                            fill="#6f879b"
                            font-size="11"
                            font-family="Inter,system-ui,sans-serif"
                        >${label}</text>
                    `;
                }
            )
            .join("");

    container.innerHTML = `
        <svg
            viewBox="0 0 ${width} ${height}"
            preserveAspectRatio="none"
            role="img"
            aria-label="Multi-series telemetry history"
            style="
                display:block;
                width:100%;
                height:100%;
                overflow:hidden;
            "
        >
            ${horizontalGrid}
            ${verticalGrid}
            ${seriesMarkup}
        </svg>
    `;
}



function formatMetricValue(
    value,
    suffix = "",
    decimals = 1
) {

    const numeric =
        Number(value);

    if (!Number.isFinite(numeric)) {
        return "--";
    }

    return (
        numeric.toFixed(decimals)
        +
        suffix
    );
}


function renderTelemetryLineChart(
    containerId,
    records,
    metricKey,
    options = {}
) {

    const container =
        document.getElementById(
            containerId
        );

    if (!container) {
        return;
    }

    const points =
        records
            .map(
                record => ({
                    value:
                        Number(
                            record[
                                metricKey
                            ]
                        ),

                    timestamp:
                        record.recorded_at
                })
            )
            .filter(
                point =>
                    Number.isFinite(
                        point.value
                    )
            );

    if (
        points.length === 0
    ) {

        container.innerHTML = `
            <div class="chart-empty-state">
                No samples
            </div>
        `;

        return;
    }

    const width = 300;
    const height = 105;

    const padding = {
        top: 10,
        right: 8,
        bottom: 24,
        left: 34
    };

    const values =
        points.map(
            point =>
                point.value
        );

    let minValue =
        Number.isFinite(
            Number(options.min)
        )
            ? Number(options.min)
            : Math.min(
                ...values
            );

    let maxValue =
        Number.isFinite(
            Number(options.max)
        )
            ? Number(options.max)
            : Math.max(
                ...values
            );

    const extraPadding =
        Number(
            options.padding
            ?? 2
        );

    if (
        options.min == null
    ) {
        minValue -= extraPadding;
    }

    if (
        options.max == null
    ) {
        maxValue += extraPadding;
    }

    if (
        maxValue <= minValue
    ) {
        maxValue =
            minValue + 1;
    }

    const plotWidth =
        width
        -
        padding.left
        -
        padding.right;

    const plotHeight =
        height
        -
        padding.top
        -
        padding.bottom;

    const xForIndex =
        index => {

            if (
                points.length === 1
            ) {
                return (
                    padding.left
                    +
                    plotWidth / 2
                );
            }

            return (
                padding.left
                +
                (
                    index
                    /
                    (
                        points.length
                        - 1
                    )
                )
                *
                plotWidth
            );
        };

    const yForValue =
        value =>
            padding.top
            +
            (
                1
                -
                (
                    value
                    -
                    minValue
                )
                /
                (
                    maxValue
                    -
                    minValue
                )
            )
            *
            plotHeight;

    const polyline =
        points
            .map(
                (point, index) =>
                    `${xForIndex(index).toFixed(1)},${yForValue(point.value).toFixed(1)}`
            )
            .join(" ");

    const area =
        [
            `${padding.left},${padding.top + plotHeight}`,
            ...points.map(
                (point, index) =>
                    `${xForIndex(index).toFixed(1)},${yForValue(point.value).toFixed(1)}`
            ),
            `${padding.left + plotWidth},${padding.top + plotHeight}`
        ]
        .join(" ");

    const firstTime =
        formatChartTime(
            points[0].timestamp
        );

    const lastTime =
        formatChartTime(
            points[
                points.length - 1
            ].timestamp
        );

    const decimals =
        Number(
            options.decimals
            ?? 1
        );

    const suffix =
        options.suffix
        ?? "";

    const yMaxLabel =
        `${maxValue.toFixed(decimals)}${suffix}`;

    const yMinLabel =
        `${minValue.toFixed(decimals)}${suffix}`;

    const latestPoint =
        points[
            points.length - 1
        ];

    const latestX =
        xForIndex(
            points.length - 1
        );

    const latestY =
        yForValue(
            latestPoint.value
        );

    container.innerHTML = `
        <svg
            class="telemetry-svg-chart"
            viewBox="0 0 ${width} ${height}"
            preserveAspectRatio="none"
            role="img"
            aria-label="${escapeHtml(metricKey)} telemetry history"
        >
            <line
                class="chart-grid-line"
                x1="${padding.left}"
                y1="${padding.top}"
                x2="${padding.left + plotWidth}"
                y2="${padding.top}"
            ></line>

            <line
                class="chart-grid-line"
                x1="${padding.left}"
                y1="${padding.top + plotHeight / 2}"
                x2="${padding.left + plotWidth}"
                y2="${padding.top + plotHeight / 2}"
            ></line>

            <line
                class="chart-grid-line"
                x1="${padding.left}"
                y1="${padding.top + plotHeight}"
                x2="${padding.left + plotWidth}"
                y2="${padding.top + plotHeight}"
            ></line>

            <polygon
                class="chart-area"
                points="${area}"
            ></polygon>

            <polyline
                class="chart-line"
                points="${polyline}"
            ></polyline>

            <circle
                class="chart-latest-point"
                cx="${latestX.toFixed(1)}"
                cy="${latestY.toFixed(1)}"
                r="2.8"
            ></circle>

            <text
                class="chart-axis-label chart-y-max"
                x="2"
                y="${padding.top + 4}"
            >
                ${escapeHtml(yMaxLabel)}
            </text>

            <text
                class="chart-axis-label chart-y-min"
                x="2"
                y="${padding.top + plotHeight + 3}"
            >
                ${escapeHtml(yMinLabel)}
            </text>

            <text
                class="chart-axis-label chart-x-first"
                x="${padding.left}"
                y="${height - 4}"
            >
                ${escapeHtml(firstTime)}
            </text>

            <text
                class="chart-axis-label chart-x-last"
                x="${padding.left + plotWidth}"
                y="${height - 4}"
                text-anchor="end"
            >
                ${escapeHtml(lastTime)}
            </text>
        </svg>
    `;
}


function formatChartTime(timestamp) {

    const date =
        new Date(
            timestamp
        );

    if (
        Number.isNaN(
            date.getTime()
        )
    ) {
        return "--";
    }

    return date.toLocaleTimeString(
        [],
        {
            hour:
                "2-digit",

            minute:
                "2-digit"
        }
    );
}


function startTelemetryHistoryRefresh() {

    if (
        telemetryHistoryTimer
        != null
    ) {

        clearInterval(
            telemetryHistoryTimer
        );

        telemetryHistoryTimer =
            null;
    }

    if (
        telemetryHistoryPaused
    ) {

        updateTelemetryRefreshUI();

        return;
    }

    telemetryHistoryTimer =
        setInterval(
            () => {

                if (
                    telemetryHistoryPaused
                ) {

                    return;
                }

                if (
                    selectedHistoryAssetId
                    != null
                ) {

                    loadTelemetryHistory();
                }
            },
            TELEMETRY_HISTORY_REFRESH_MS
        );

    updateTelemetryRefreshUI();
}


/* =========================================================
   PHASE 6.3 SENSOR HEALTH + ALERTS
========================================================= */

async function loadSensorHealth() {

    try {

        const response =
            await fetch(
                `${API_URL}/sensor-health`
            );


        if (!response.ok) {

            throw new Error(
                "Sensor health request failed"
            );
        }


        const payload =
            await response.json();


        if (
            payload.source !== "LOCAL_PROJECT"
            || payload.external !== false
        ) {

            console.warn(
                "Rejected unexpected sensor health payload."
            );

            return;
        }


        updateSensorHealthSummary(
            payload
        );

    }

    catch (error) {

        console.error(
            "Sensor health load error:",
            error
        );
    }
}


async function loadAlerts() {

    try {

        const response =
            await fetch(
                `${API_URL}/alerts`
            );


        if (!response.ok) {

            throw new Error(
                "Alerts request failed"
            );
        }


        const payload =
            await response.json();


        if (
            payload.source !== "LOCAL_PROJECT"
            || payload.external !== false
        ) {

            console.warn(
                "Rejected unexpected alert payload."
            );

            return;
        }


        updateAlertState(
            payload.alerts || [],
            payload.summary || {}
        );

    }

    catch (error) {

        console.error(
            "Alerts load error:",
            error
        );
    }
}


function updateSensorHealthSummary(data) {

    sensorHealthSummary = {
        total: Number(data.total ?? 0),
        online: Number(data.online ?? 0),
        degraded: Number(data.degraded ?? 0),
        offline: Number(data.offline ?? 0),
        average_health: Number(data.average_health ?? 0)
    };


    setTextIfExists(
        "monitoredSensors",
        sensorHealthSummary.total
    );

    setTextIfExists(
        "onlineSensors",
        sensorHealthSummary.online
    );

    setTextIfExists(
        "degradedSensors",
        sensorHealthSummary.degraded
    );

    setTextIfExists(
        "offlineSensors",
        sensorHealthSummary.offline
    );

    setTextIfExists(
        "averageSensorHealth",
        `${sensorHealthSummary.average_health.toFixed(0)}%`
    );


    if (data.active_alerts != null) {

        setTextIfExists(
            "activeAlertsCount",
            Number(data.active_alerts)
        );
    }
}


function updateAlertState(
    alerts,
    summary
) {

    alertData = Array.isArray(alerts)
        ? alerts
        : [];


    alertSummary = {
        total: Number(summary.total ?? alertData.length),
        critical: Number(summary.critical ?? 0),
        high: Number(summary.high ?? 0),
        medium: Number(summary.medium ?? 0),
        low: Number(summary.low ?? 0)
    };


    setTextIfExists(
        "activeAlertsCount",
        alertSummary.total
    );

    setTextIfExists(
        "criticalAlertCount",
        alertSummary.critical
    );

    setTextIfExists(
        "highAlertCount",
        alertSummary.high
    );

    setTextIfExists(
        "mediumAlertCount",
        alertSummary.medium
    );

    setTextIfExists(
        "lowAlertCount",
        alertSummary.low
    );


    renderAlertFeed(
        alertData
    );
}


function renderAlertFeed(alerts) {

    const container =
        document.getElementById(
            "alertFeed"
        );


    if (!container) {

        return;
    }


    if (
        !Array.isArray(alerts)
        || alerts.length === 0
    ) {

        container.innerHTML = `
            <div class="empty-state alert-clear-state">
                No active local sensor alerts.
            </div>
        `;

        return;
    }


    const severityOrder = {
        critical: 4,
        high: 3,
        medium: 2,
        low: 1
    };


    const sorted =
        [...alerts]
            .sort(
                (a, b) =>
                    (severityOrder[b.severity] || 0)
                    -
                    (severityOrder[a.severity] || 0)
            )
            .slice(
                0,
                12
            );


    container.innerHTML =
        sorted
            .map(
                alert => {

                    const assetId =
                        Number(
                            alert.asset_id
                        );

                    const severity =
                        String(
                            alert.severity || "low"
                        ).toLowerCase();

                    const value =
                        Number.isFinite(
                            Number(alert.value)
                        )
                            ? Number(alert.value)
                            : null;

                    const threshold =
                        Number.isFinite(
                            Number(alert.threshold)
                        )
                            ? Number(alert.threshold)
                            : null;


                    return `
                        <button
                            type="button"
                            class="alert-card ${escapeHtml(severity)}"
                            onclick="focusAlertAsset(${assetId})"
                        >

                            <div class="alert-card-header">

                                <div>
                                    <div class="alert-asset-name">
                                        ${escapeHtml(
                                            alert.asset_name
                                            || `Asset ${assetId}`
                                        )}
                                    </div>

                                    <div class="alert-type-name">
                                        ${escapeHtml(
                                            String(
                                                alert.alert_type
                                                || "sensor_alert"
                                            )
                                            .replaceAll("_", " ")
                                        )}
                                    </div>
                                </div>

                                <span class="severity ${escapeHtml(severity)}">
                                    ${escapeHtml(severity)}
                                </span>

                            </div>

                            <div class="alert-message">
                                ${escapeHtml(
                                    alert.message
                                    || "Sensor threshold exceeded"
                                )}
                            </div>

                            ${
                                value !== null
                                    ? `
                                        <div class="alert-metric">
                                            <span>
                                                ${escapeHtml(
                                                    alert.metric
                                                    || "metric"
                                                )}
                                            </span>

                                            <strong>
                                                ${value}
                                                ${
                                                    threshold !== null
                                                        ? ` / threshold ${threshold}`
                                                        : ""
                                                }
                                            </strong>
                                        </div>
                                    `
                                    : ""
                            }

                        </button>
                    `;
                }
            )
            .join("");
}


function focusAlertAsset(assetId) {

    const point =
        infrastructureData.find(
            item =>
                Number(item.id)
                ===
                Number(assetId)
        );


    if (!point) {

        console.warn(
            "Alert asset was not found on the map:",
            assetId
        );

        return;
    }


    const marker =
        assetMarkers.get(
            Number(assetId)
        );


    if (marker && clusterGroup) {

        clusterGroup.zoomToShowLayer(
            marker,
            () => {

                marker.setPopupContent(
                    buildInfrastructurePopup(
                        point
                    )
                );

                marker.openPopup();
            }
        );

        return;
    }


    focusAsset(
        point.latitude,
        point.longitude
    );
}


function setAlertSocketIndicator(
    state,
    text
) {

    const indicator =
        document.getElementById(
            "alertSocketIndicator"
        );


    if (!indicator) {

        return;
    }


    indicator.className =
        `alert-socket-indicator ${state}`;

    indicator.textContent =
        text;
}


function connectAlertSocket() {

    alertSocket =
        new WebSocket(
            `${getWebSocketBaseURL()}/ws/alerts`
        );


    setAlertSocketIndicator(
        "connecting",
        "CONNECTING"
    );


    alertSocket.onopen =
        () => {

            console.log(
                "Alerts WebSocket connected"
            );

            setAlertSocketIndicator(
                "connected",
                "LIVE"
            );
        };


    alertSocket.onmessage =
        event => {

            try {

                const message =
                    JSON.parse(
                        event.data
                    );


                if (
                    message.type !== "sensor_alerts"
                    || message.source !== "LOCAL_PROJECT"
                    || message.external !== false
                ) {

                    return;
                }


                updateSensorHealthSummary(
                    message.sensor_health || {}
                );

                updateAlertState(
                    message.alerts || [],
                    message.summary || {}
                );

            }

            catch (error) {

                console.error(
                    "Alert WebSocket message error:",
                    error
                );
            }
        };


    alertSocket.onerror =
        error => {

            console.error(
                "Alerts WebSocket error:",
                error
            );

            setAlertSocketIndicator(
                "disconnected",
                "ERROR"
            );
        };


    alertSocket.onclose =
        () => {

            console.log(
                "Alerts WebSocket disconnected. Reconnecting..."
            );

            setAlertSocketIndicator(
                "disconnected",
                "OFFLINE"
            );

            setTimeout(
                connectAlertSocket,
                5000
            );
        };
}


/* =========================================================
   SENSOR WEBSOCKET
========================================================= */

function connectSensorSocket() {

    const url =
        `${getWebSocketBaseURL()}/ws/sensors`;


    sensorSocket =
        new WebSocket(
            url
        );


    sensorSocket.onopen =
        () => {

            console.log(
                "Local sensor WebSocket connected"
            );
        };


    sensorSocket.onmessage =
        event => {

            try {

                const message =
                    JSON.parse(
                        event.data
                    );


                /*
                    Accept only our local project stream.
                */

                if (
                    message.type
                    !== "sensor_telemetry"
                ) {

                    return;
                }


                if (
                    message.source
                    !== "LOCAL_PROJECT"
                ) {

                    console.warn(
                        "Rejected unexpected sensor source:",
                        message.source
                    );

                    return;
                }


                if (
                    message.external
                    !== false
                ) {

                    console.warn(
                        "Rejected sensor message not marked local."
                    );

                    return;
                }


                updateSensorStore(
                    message.data
                    || []
                );


                refreshMarkerTelemetry();

            }

            catch (error) {

                console.error(
                    "Sensor WebSocket message error:",
                    error
                );
            }
        };


    sensorSocket.onerror =
        error => {

            console.error(
                "Sensor WebSocket error:",
                error
            );
        };


    sensorSocket.onclose =
        () => {

            console.log(
                "Local sensor WebSocket disconnected. Reconnecting..."
            );


            setTimeout(
                connectSensorSocket,
                5000
            );
        };
}


/* =========================================================
   LOCATION WEBSOCKET
========================================================= */

function connectLocationSocket() {

    locationSocket =
        new WebSocket(
            `${getWebSocketBaseURL()}/ws/locations`
        );


    locationSocket.onopen =
        () => {

            console.log(
                "Location WebSocket connected"
            );
        };


    locationSocket.onmessage =
        event => {

            try {

                const message =
                    JSON.parse(
                        event.data
                    );


                if (
                    message.type
                    !== "locations"
                ) {

                    return;
                }


                infrastructureData =
                    message.data
                    || [];


                populateTestAssetSelect(
                    infrastructureData
                );


                populateHistoryAssetSelect(
                    infrastructureData
                );


                applyFilters();

            }

            catch (error) {

                console.error(
                    "Location WebSocket error:",
                    error
                );
            }
        };


    locationSocket.onclose =
        () => {

            console.log(
                "Location WebSocket disconnected. Reconnecting..."
            );


            setTimeout(
                connectLocationSocket,
                5000
            );
        };
}


/* =========================================================
   EVENT WEBSOCKET
========================================================= */

function connectEventSocket() {

    eventSocket =
        new WebSocket(
            `${getWebSocketBaseURL()}/ws/events`
        );


    eventSocket.onopen =
        () => {

            console.log(
                "Earthquake WebSocket connected"
            );
        };


    eventSocket.onmessage =
        event => {

            try {

                const message =
                    JSON.parse(
                        event.data
                    );


                if (
                    message.type
                    !== "earthquakes"
                ) {

                    return;
                }


                earthquakeData =
                    message.data
                    || [];


                riskData =
                    message.risk
                    || [];


                renderEarthquakes(
                    earthquakeData
                );


                renderRiskFeed(
                    riskData
                );


                applyFilters();


                loadAnalytics();

                loadTestEventStatus();

            }

            catch (error) {

                console.error(
                    "Earthquake WebSocket error:",
                    error
                );
            }
        };


    eventSocket.onclose =
        () => {

            console.log(
                "Earthquake WebSocket disconnected. Reconnecting..."
            );


            setTimeout(
                connectEventSocket,
                5000
            );
        };
}


/* =========================================================
   FULL DASHBOARD REFRESH
========================================================= */

async function refreshDashboard() {

    await Promise.all(
        [
            loadLocations(),
            loadSensorTelemetry(),
            loadSensorHealth(),
            loadAlerts(),
            loadRisk(),
            loadAnalytics(),
            loadEarthquakes(),
            loadTestEventStatus(),
            loadTelemetryAlerts(),
            loadPersistedTelemetryAlerts()
        ]
    );


    refreshMarkerTelemetry();

    if (
        selectedHistoryAssetId != null
    ) {

        await loadTelemetryHistory();
    }
}


/* =========================================================
   MAP FOCUS HELPERS
========================================================= */

function focusEarthquake(
    latitude,
    longitude
) {

    map.flyTo(
        [
            latitude,
            longitude
        ],
        6,
        {
            duration:
                1.2
        }
    );
}


function focusAsset(
    latitude,
    longitude
) {

    map.flyTo(
        [
            latitude,
            longitude
        ],
        9,
        {
            duration:
                1.2
        }
    );
}


/* =========================================================
   EVENT AGE
========================================================= */

function formatEventAge(timestamp) {

    if (!timestamp) {

        return "Time unavailable";
    }


    const eventTime =
        new Date(
            timestamp
        );


    if (
        Number.isNaN(
            eventTime.getTime()
        )
    ) {

        return "Time unavailable";
    }


    const seconds =
        Math.max(
            0,
            Math.floor(
                (
                    Date.now()
                    -
                    eventTime.getTime()
                )
                /
                1000
            )
        );


    if (seconds < 60) {

        return `${seconds} sec ago`;
    }


    const minutes =
        Math.floor(
            seconds / 60
        );


    if (minutes < 60) {

        return `${minutes} min ago`;
    }


    const hours =
        Math.floor(
            minutes / 60
        );


    if (hours < 24) {

        return `${hours} hr ago`;
    }


    const days =
        Math.floor(
            hours / 24
        );


    return `${days} day${days === 1 ? "" : "s"} ago`;
}


/* =========================================================
   SAFE TEXT SETTER
========================================================= */

function setTextIfExists(
    id,
    value
) {

    const element =
        document.getElementById(
            id
        );


    if (element) {

        element.textContent =
            value;
    }
}


/* =========================================================
   HTML ESCAPING
========================================================= */

function escapeHtml(value) {

    return String(
        value ?? ""
    )
    .replaceAll(
        "&",
        "&amp;"
    )
    .replaceAll(
        "<",
        "&lt;"
    )
    .replaceAll(
        ">",
        "&gt;"
    )
    .replaceAll(
        '"',
        "&quot;"
    )
    .replaceAll(
        "'",
        "&#039;"
    );
}


/* =========================================================
   START APPLICATION
========================================================= */

window.addEventListener(
    "load",
    async () => {

        initMap();


        const searchBox =
            document.getElementById(
                "searchBox"
            );


        const typeFilter =
            document.getElementById(
                "typeFilter"
            );


        const riskFilter =
            document.getElementById(
                "riskFilter"
            );


        const createButton =
            document.getElementById(
                "createTestEvent"
            );


        const removeButton =
            document.getElementById(
                "removeTestEvent"
            );


        const historyAsset =
            document.getElementById(
                "historyAsset"
            );


        const historyRange =
            document.getElementById(
                "historyRange"
            );


        const refreshHistoryButton =
            document.getElementById(
                "refreshHistory"
            );


        const toggleHistoryRefreshButton =
            document.getElementById(
                "toggleHistoryRefresh"
            );


        const telemetryAlertSeverity =
            document.getElementById(
                "telemetryAlertSeverity"
            );


        const persistedAlertStatusFilter =
            document.getElementById(
                "persistedAlertStatusFilter"
            );


        const persistedAlertSeverityFilter =
            document.getElementById(
                "persistedAlertSeverityFilter"
            );


        const refreshPersistedAlerts =
            document.getElementById(
                "refreshPersistedAlerts"
            );


        const persistedAlertFeed =
            document.getElementById(
                "persistedAlertFeed"
            );


        const closeAlertHistoryButton =
            document.getElementById(
                "closeAlertHistory"
            );


        const alertHistoryModal =
            document.getElementById(
                "alertHistoryModal"
            );


        if (searchBox) {

            searchBox.addEventListener(
                "input",
                applyFilters
            );
        }


        if (typeFilter) {

            typeFilter.addEventListener(
                "change",
                applyFilters
            );
        }


        if (riskFilter) {

            riskFilter.addEventListener(
                "change",
                applyFilters
            );
        }


        if (createButton) {

            createButton.addEventListener(
                "click",
                createTestEvent
            );
        }


        if (removeButton) {

            removeButton.addEventListener(
                "click",
                removeTestEvent
            );
        }


        if (historyAsset) {

            historyAsset.addEventListener(
                "change",
                () => {

                    const value =
                        Number(
                            historyAsset.value
                        );

                    if (
                        Number.isFinite(value)
                        &&
                        value > 0
                    ) {

                        selectedHistoryAssetId =
                            value;

                        loadTelemetryHistory();
                    }

                    else {

                        selectedHistoryAssetId =
                            null;

                        showTelemetryHistoryEmpty(
                            "Select an infrastructure asset to load persisted telemetry history."
                        );
                    }
                }
            );
        }


        if (historyRange) {

            historyRange.addEventListener(
                "change",
                () => {

                    if (
                        selectedHistoryAssetId
                        != null
                    ) {

                        loadTelemetryHistory();
                    }
                }
            );
        }


        if (refreshHistoryButton) {

            refreshHistoryButton.addEventListener(
                "click",
                loadTelemetryHistory
            );
        }


        if (toggleHistoryRefreshButton) {

            toggleHistoryRefreshButton.addEventListener(
                "click",
                toggleTelemetryHistoryRefresh
            );
        }


        if (telemetryAlertSeverity) {

            telemetryAlertSeverity.addEventListener(
                "change",
                renderTelemetryAlerts
            );
        }


        if (persistedAlertStatusFilter) {

            persistedAlertStatusFilter.addEventListener(
                "change",
                renderPersistedAlerts
            );
        }


        if (persistedAlertSeverityFilter) {

            persistedAlertSeverityFilter.addEventListener(
                "change",
                renderPersistedAlerts
            );
        }


        if (refreshPersistedAlerts) {

            refreshPersistedAlerts.addEventListener(
                "click",
                loadPersistedTelemetryAlerts
            );
        }


        if (persistedAlertFeed) {

            persistedAlertFeed.addEventListener(
                "click",
                handlePersistedAlertFeedClick
            );
        }


        if (closeAlertHistoryButton) {

            closeAlertHistoryButton.addEventListener(
                "click",
                closeAlertHistory
            );
        }


        if (alertHistoryModal) {

            alertHistoryModal.addEventListener(
                "click",
                event => {

                    if (
                        event.target.dataset
                        &&
                        event.target.dataset.closeAlertHistory
                        === "true"
                    ) {

                        closeAlertHistory();
                    }
                }
            );
        }


        document.addEventListener(
            "keydown",
            event => {

                if (
                    event.key === "Escape"
                ) {

                    closeAlertHistory();
                }
            }
        );


        /*
            Initial REST load
        */

        await refreshDashboard();


        updateTelemetryRefreshUI();

        startTelemetryHistoryRefresh();


        /*
            Start real-time project-local streams
        */

        connectSensorSocket();

        connectAlertSocket();

        connectTelemetryAlertSocket();

        connectLocationSocket();

        connectEventSocket();


        console.log(
            "Infrastructure Monitor started."
        );


        console.log(
            "Sensor telemetry source: LOCAL_PROJECT"
        );


        console.log(
            "External sensor transmission: DISABLED"
        );


        console.log(
            "USGS earthquake integration: READ ONLY"
        );


        console.log(
            "Telemetry history: PostgreSQL persisted, 60-second refresh"
        );


        console.log(
            "Phase 6.5 telemetry alerting: threshold + trend detection"
        );
    }
);


/* =========================================================
   PHASE 6.6 NEON DASHBOARD SHELL
   Visual-only helpers. Existing monitoring logic remains intact.
========================================================= */

function updateDashboardClock() {

    const now =
        new Date();

    const dateElement =
        document.getElementById(
            "dashboardDate"
        );

    const clockElement =
        document.getElementById(
            "dashboardClock"
        );

    if (dateElement) {

        dateElement.textContent =
            now.toLocaleDateString(
                undefined,
                {
                    weekday: "short",
                    day: "2-digit",
                    month: "short",
                    year: "numeric"
                }
            );
    }

    if (clockElement) {

        clockElement.textContent =
            now.toLocaleTimeString(
                undefined,
                {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit"
                }
            );
    }
}


function updateDashboardMirrors() {

    const healthSource =
        document.getElementById(
            "averageSensorHealth"
        );

    const healthRing =
        document.getElementById(
            "healthRing"
        );

    const healthRingValue =
        document.getElementById(
            "healthRingValue"
        );

    if (
        healthSource
        &&
        healthRing
        &&
        healthRingValue
    ) {

        const match =
            String(
                healthSource.textContent
                || "0"
            ).match(
                /-?\d+(?:\.\d+)?/
            );

        const health =
            Math.max(
                0,
                Math.min(
                    100,
                    match
                        ? Number(match[0])
                        : 0
                )
            );

        healthRingValue.textContent =
            `${Math.round(health)}%`;

        healthRing.style.setProperty(
            "--health-angle",
            `${health * 3.6}deg`
        );
    }


    const alertSource =
        document.getElementById(
            "activeAlertsCount"
        );

    const sidebarAlertCount =
        document.getElementById(
            "sidebarAlertCount"
        );

    if (
        alertSource
        &&
        sidebarAlertCount
    ) {

        sidebarAlertCount.textContent =
            String(
                alertSource.textContent
                || "0"
            );
    }


    const riskSource =
        document.getElementById(
            "highRisk"
        );

    const riskTarget =
        document.getElementById(
            "opsRiskValue"
        );

    if (
        riskSource
        &&
        riskTarget
    ) {

        riskTarget.textContent =
            String(
                riskSource.textContent
                || "0"
            );
    }


    const alertAssetSource =
        document.getElementById(
            "telemetryAlertAssets"
        );

    const alertAssetTarget =
        document.getElementById(
            "opsAlertAssetValue"
        );

    if (
        alertAssetSource
        &&
        alertAssetTarget
    ) {

        alertAssetTarget.textContent =
            String(
                alertAssetSource.textContent
                || "0"
            );
    }


    const trendSource =
        document.getElementById(
            "telemetryTrendAlertCount"
        );

    const trendTarget =
        document.getElementById(
            "opsTrendValue"
        );

    if (
        trendSource
        &&
        trendTarget
    ) {

        trendTarget.textContent =
            String(
                trendSource.textContent
                || "0"
            );
    }
}


function activateDashboardNavigation() {

    const main =
        document.getElementById(
            "dashboardMain"
        );

    const buttons =
        [
            ...document.querySelectorAll(
                "[data-scroll-target]"
            )
        ];

    buttons.forEach(
        button => {

            button.addEventListener(
                "click",
                () => {

                    const targetId =
                        button.dataset.scrollTarget;

                    const target =
                        document.getElementById(
                            targetId
                        );

                    if (!target) {
                        return;
                    }

                    target.scrollIntoView(
                        {
                            behavior: "smooth",
                            block: "start"
                        }
                    );

                    document
                        .querySelectorAll(
                            ".nav-item"
                        )
                        .forEach(
                            item =>
                                item.classList.remove(
                                    "active"
                                )
                        );

                    if (
                        button.classList.contains(
                            "nav-item"
                        )
                    ) {

                        button.classList.add(
                            "active"
                        );
                    }
                }
            );
        }
    );


    if (
        main
        &&
        "IntersectionObserver"
        in window
    ) {

        const navButtons =
            [
                ...document.querySelectorAll(
                    ".nav-item[data-scroll-target]"
                )
            ];

        const observer =
            new IntersectionObserver(
                entries => {

                    const visible =
                        entries
                            .filter(
                                entry =>
                                    entry.isIntersecting
                            )
                            .sort(
                                (
                                    first,
                                    second
                                ) =>
                                    second.intersectionRatio
                                    -
                                    first.intersectionRatio
                            )[0];

                    if (!visible) {
                        return;
                    }

                    navButtons.forEach(
                        button => {

                            button.classList.toggle(
                                "active",
                                button.dataset.scrollTarget
                                ===
                                visible.target.id
                            );
                        }
                    );
                },
                {
                    root: main,
                    threshold: [
                        0.16,
                        0.35,
                        0.55
                    ]
                }
            );

        navButtons.forEach(
            button => {

                const section =
                    document.getElementById(
                        button.dataset.scrollTarget
                    );

                if (section) {
                    observer.observe(section);
                }
            }
        );
    }
}


function initialiseNeonDashboardShell() {

    updateDashboardClock();

    setInterval(
        updateDashboardClock,
        1000
    );

    updateDashboardMirrors();

    setInterval(
        updateDashboardMirrors,
        1500
    );

    activateDashboardNavigation();


    setTimeout(
        () => {

            if (
                typeof map !== "undefined"
                &&
                map
            ) {

                map.invalidateSize();
            }
        },
        600
    );
}


if (
    document.readyState
    === "loading"
) {

    document.addEventListener(
        "DOMContentLoaded",
        initialiseNeonDashboardShell
    );
}

else {

    initialiseNeonDashboardShell();
}
