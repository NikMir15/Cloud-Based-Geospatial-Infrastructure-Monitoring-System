/* =========================================================
   INFRASTRUCTURE SITUATIONAL AWARENESS PLATFORM

   Phase 6.3 Frontend

   - Live USGS earthquake visualization
   - Project-local simulated sensor telemetry
   - PostGIS exposure/risk visualization
   - Phase 6.1 local test earthquake
   - REST + WebSockets
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
        OpenStreetMap basemap.

        No CARTO API key is required.
    */

    L.tileLayer(
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            minZoom:
                2,

            maxZoom:
                19,

            noWrap:
                false,

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

                disableClusteringAtZoom:
                    12,

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

                            <div class="alert-source-row">
                                LOCAL PROJECT
                            </div>

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
            loadTestEventStatus()
        ]
    );


    refreshMarkerTelemetry();
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


        /*
            Initial REST load
        */

        await refreshDashboard();


        /*
            Start real-time project-local streams
        */

        connectSensorSocket();

        connectAlertSocket();

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
    }
);

/* =========================================================
   PHASE 6.8 — SRE INTELLIGENCE + INCIDENT OPERATIONS
   Additive module: does not recreate the map or modify the
   existing telemetry, sensor-health, alert-lifecycle streams.
========================================================= */

const phase68State = {
    intelligence: null,
    slaStatus: null,
    policy: null,
    incidents: [],
    selectedIncidentId: null,
    refreshTimer: null
};

function phase68El(id) { return document.getElementById(id); }
function phase68Text(id, value) { const el = phase68El(id); if (el) el.textContent = value; }
function phase68Number(value, fallback = 0) { const n = Number(value); return Number.isFinite(n) ? n : fallback; }
function phase68Date(value) {
    if (!value) return "--";
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString();
}
function phase68Duration(minutes) {
    const n = Number(minutes);
    if (!Number.isFinite(n)) return "--";
    if (n < 60) return `${n.toFixed(2)} min`;
    return `${(n / 60).toFixed(2)} hr`;
}
function phase68Escape(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;").replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}
async function phase68Fetch(path, options = {}) {
    const response = await fetch(`${API_URL}${path}`, {
        ...options,
        headers: { "Content-Type": "application/json", ...(options.headers || {}) }
    });
    let body = null;
    try { body = await response.json(); } catch (_) { body = null; }
    if (!response.ok) {
        const detail = body?.detail || body?.message || `HTTP ${response.status}`;
        throw new Error(detail);
    }
    return body;
}

function renderPhase68Intelligence(data) {
    const metrics = data?.incident_metrics || {};
    const sla = data?.sla || {};
    const ops = data?.operations || {};
    const priorities = ops?.open_by_priority || {};

    phase68Text("sreMtta", phase68Duration(metrics.mtta_minutes));
    phase68Text("sreMttr", phase68Duration(metrics.mttr_minutes));
    phase68Text("sreSlaBreaches", phase68Number(sla.incidents_with_active_sla_breach));
    phase68Text("sreEscalated", phase68Number(ops.escalated_open_incidents));
    phase68Text("sreUnassigned", phase68Number(ops.unassigned_open_incidents));
    phase68Text("priorityP1", phase68Number(priorities.P1));
    phase68Text("priorityP2", phase68Number(priorities.P2));
    phase68Text("priorityP3", phase68Number(priorities.P3));
    phase68Text("priorityP4", phase68Number(priorities.P4));
    phase68Text("slaAckBreaches", phase68Number(sla.active_acknowledgement_breaches));
    phase68Text("slaResolutionBreaches", phase68Number(sla.active_resolution_breaches));

    const evaluation = sla.last_evaluation || {};
    phase68Text("slaEvaluatedCount", phase68Number(evaluation.evaluated ?? evaluation.checked ?? evaluation.incidents_checked));
    phase68Text("slaLastEvaluation", data?.generated_at ? new Date(data.generated_at).toLocaleTimeString() : "--");
}

function renderPhase68Policy(data) {
    const target = phase68El("slaPolicyList");
    if (!target) return;
    const targets = data?.sla_targets || {};
    const priorities = data?.priorities || ["P1", "P2", "P3", "P4"];
    target.innerHTML = priorities.map(priority => {
        const item = targets[priority] || {};
        const ack = item.acknowledge_minutes ?? item.ack_minutes ?? "--";
        const resolve = item.resolve_minutes ?? item.resolution_minutes ?? "--";
        return `<div class="sla-policy-row"><span class="priority-badge ${priority.toLowerCase()}">${phase68Escape(priority)}</span><span>ACK <strong>${phase68Escape(ack)}m</strong></span><span>RES <strong>${phase68Escape(resolve)}m</strong></span></div>`;
    }).join("");
}

function incidentHasBreach(incident) {
    return Boolean(incident?.acknowledgement_sla_breached || incident?.resolution_sla_breached);
}
function incidentSlaLabel(incident) {
    const ack = Boolean(incident?.acknowledgement_sla_breached);
    const res = Boolean(incident?.resolution_sla_breached);
    if (ack && res) return "ACK + RES BREACH";
    if (ack) return "ACK BREACH";
    if (res) return "RES BREACH";
    return "WITHIN SLA";
}
function filteredPhase68Incidents() {
    const search = (phase68El("incidentSearch")?.value || "").trim().toLowerCase();
    const status = phase68El("incidentStatusFilter")?.value || "all";
    const priority = phase68El("incidentPriorityFilter")?.value || "all";
    const sla = phase68El("incidentSlaFilter")?.value || "all";
    return phase68State.incidents.filter(item => {
        const haystack = [item.id, item.incident_key, item.title, item.asset_name, item.owner, item.assigned_team].join(" ").toLowerCase();
        if (search && !haystack.includes(search)) return false;
        if (status !== "all" && String(item.status || "").toLowerCase() !== status) return false;
        if (priority !== "all" && String(item.priority || "").toUpperCase() !== priority) return false;
        if (sla === "breached" && !incidentHasBreach(item)) return false;
        if (sla === "healthy" && incidentHasBreach(item)) return false;
        return true;
    });
}

function renderPhase68Incidents() {
    const target = phase68El("incidentOperationsList");
    if (!target) return;
    const incidents = filteredPhase68Incidents();
    phase68Text("incidentQueueCount", `${incidents.length} incidents`);
    phase68Text("sidebarIncidentCount", phase68State.incidents.filter(i => i.status !== "resolved").length);
    if (!incidents.length) {
        target.innerHTML = '<div class="empty-state">No incidents match the current filters.</div>';
        return;
    }
    target.innerHTML = incidents.map(item => {
        const id = Number(item.id);
        const priority = String(item.priority || "UNSET").toUpperCase();
        const status = String(item.status || "unknown").toLowerCase();
        const breached = incidentHasBreach(item);
        const title = item.title || item.asset_name || item.incident_key || `Incident ${id}`;
        return `<div class="incident-operation-row" data-incident-id="${id}">
            <button class="incident-title-button" type="button" data-phase68-action="view" data-incident-id="${id}"><strong>#${id} · ${phase68Escape(title)}</strong><small>${phase68Escape(item.severity || "unknown")} severity</small></button>
            <span><span class="priority-badge ${priority.toLowerCase()}">${phase68Escape(priority)}</span></span>
            <span><span class="incident-status-badge ${status}">${phase68Escape(status.toUpperCase())}</span></span>
            <span class="incident-owner">${phase68Escape(item.owner || item.assigned_team || "Unassigned")}</span>
            <span><span class="sla-badge ${breached ? "breached" : "healthy"}">${phase68Escape(incidentSlaLabel(item))}</span></span>
            <span class="incident-row-actions">
                <button type="button" data-phase68-action="view" data-incident-id="${id}">View</button>
                <button type="button" data-phase68-action="priority" data-incident-id="${id}">Priority</button>
                <button type="button" data-phase68-action="assign" data-incident-id="${id}">Assign</button>
                <button type="button" data-phase68-action="more" data-incident-id="${id}">Ops</button>
            </span>
        </div>`;
    }).join("");
}

async function loadPhase68Intelligence() {
    const data = await phase68Fetch("/sre/intelligence?hours=168");
    phase68State.intelligence = data;
    renderPhase68Intelligence(data);
}
async function loadPhase68Policy() {
    const data = await phase68Fetch("/sre/priority-policy");
    phase68State.policy = data;
    renderPhase68Policy(data);
}
async function loadPhase68Incidents() {
    const [slaData, incidentData] = await Promise.all([
        phase68Fetch("/sre/sla-status?limit=250"),
        phase68Fetch("/incidents?limit=250")
    ]);
    phase68State.slaStatus = slaData;
    const full = Array.isArray(incidentData?.incidents) ? incidentData.incidents : [];
    const slaById = new Map((slaData?.incidents || []).map(i => [Number(i.id), i]));
    phase68State.incidents = full.map(i => ({ ...i, ...(slaById.get(Number(i.id)) || {}) }));
    renderPhase68Incidents();
}

async function refreshPhase68() {
    const status = phase68El("sreRefreshStatus");
    if (status) { status.textContent = "REFRESHING"; status.classList.add("refreshing"); }
    const results = await Promise.allSettled([
        loadPhase68Intelligence(), loadPhase68Incidents(), loadPhase68Policy()
    ]);
    const failed = results.filter(r => r.status === "rejected");
    if (status) {
        status.textContent = failed.length ? "DEGRADED" : "LIVE";
        status.classList.toggle("error", Boolean(failed.length));
        status.classList.remove("refreshing");
    }
    if (failed.length) console.error("Phase 6.8 refresh errors:", failed.map(f => f.reason));
}

function openIncidentDrawer() {
    phase68El("incidentDrawer")?.classList.add("open");
    phase68El("incidentDrawer")?.setAttribute("aria-hidden", "false");
    phase68El("incidentDrawerBackdrop")?.classList.add("open");
    phase68El("incidentDrawerBackdrop")?.setAttribute("aria-hidden", "false");
}
function closeIncidentDrawer() {
    phase68El("incidentDrawer")?.classList.remove("open");
    phase68El("incidentDrawer")?.setAttribute("aria-hidden", "true");
    phase68El("incidentDrawerBackdrop")?.classList.remove("open");
    phase68El("incidentDrawerBackdrop")?.setAttribute("aria-hidden", "true");
}
async function showIncidentDetail(id) {
    phase68State.selectedIncidentId = Number(id);
    const body = phase68El("incidentDrawerBody");
    if (body) body.innerHTML = '<div class="empty-state">Loading incident detail...</div>';
    openIncidentDrawer();
    try {
        const [detailData, slaData, eventData] = await Promise.all([
            phase68Fetch(`/incidents/${id}`),
            phase68Fetch(`/incidents/${id}/sla`),
            phase68Fetch(`/incidents/${id}/events`)
        ]);
        const incident = { ...(detailData?.incident || {}), ...(slaData?.incident || {}) };
        const sla = slaData?.sla || {};
        const history = Array.isArray(eventData?.history) ? eventData.history : [];
        phase68Text("incidentDrawerTitle", `Incident #${id}`);
        if (body) body.innerHTML = `
            <div class="incident-detail-title"><strong>${phase68Escape(incident.title || incident.incident_key || `Incident ${id}`)}</strong><span class="priority-badge ${String(incident.priority || "unset").toLowerCase()}">${phase68Escape(incident.priority || "UNSET")}</span></div>
            <div class="incident-detail-grid">
                <div><span>Severity</span><strong>${phase68Escape(incident.severity || "--")}</strong></div>
                <div><span>Status</span><strong>${phase68Escape(incident.status || "--")}</strong></div>
                <div><span>Owner</span><strong>${phase68Escape(incident.owner || "Unassigned")}</strong></div>
                <div><span>Team</span><strong>${phase68Escape(incident.assigned_team || "--")}</strong></div>
                <div><span>Escalation</span><strong>${incident.escalated ? `Level ${phase68Escape(incident.escalation_level || 1)}` : "No"}</strong></div>
                <div><span>Created</span><strong>${phase68Escape(phase68Date(incident.created_at))}</strong></div>
            </div>
            <div class="incident-sla-detail">
                <h3>SLA</h3>
                <div class="incident-detail-grid">
                    <div><span>ACK Due</span><strong>${phase68Escape(phase68Date(incident.acknowledgement_due_at || sla.acknowledgement_due_at))}</strong></div>
                    <div><span>ACK Status</span><strong class="${incident.acknowledgement_sla_breached ? "danger-text" : "success-text"}">${incident.acknowledgement_sla_breached ? "BREACHED" : "WITHIN SLA"}</strong></div>
                    <div><span>Resolution Due</span><strong>${phase68Escape(phase68Date(incident.resolution_due_at || sla.resolution_due_at))}</strong></div>
                    <div><span>Resolution Status</span><strong class="${incident.resolution_sla_breached ? "danger-text" : "success-text"}">${incident.resolution_sla_breached ? "BREACHED" : "WITHIN SLA"}</strong></div>
                </div>
            </div>
            <div class="incident-drawer-actions">
                <button data-phase68-action="acknowledge" data-incident-id="${id}">Acknowledge</button>
                <button data-phase68-action="assign" data-incident-id="${id}">Assign</button>
                <button data-phase68-action="priority" data-incident-id="${id}">Priority</button>
                <button data-phase68-action="escalate" data-incident-id="${id}">Escalate</button>
                <button data-phase68-action="mitigate" data-incident-id="${id}">Mitigate</button>
                <button data-phase68-action="resolve" data-incident-id="${id}">Resolve</button>
                <button data-phase68-action="reopen" data-incident-id="${id}">Reopen</button>
            </div>
            <div class="incident-history"><h3>Incident Timeline</h3>${history.length ? history.map(event => `<div class="incident-history-event"><span class="history-dot"></span><div><strong>${phase68Escape(event.action || "EVENT")}</strong><small>${phase68Escape(phase68Date(event.changed_at))} · ${phase68Escape(event.changed_by || "SYSTEM")}</small><p>${phase68Escape(event.note || "")}</p></div></div>`).join("") : '<div class="empty-state">No incident history events.</div>'}</div>`;
    } catch (error) {
        if (body) body.innerHTML = `<div class="empty-state danger-text">${phase68Escape(error.message)}</div>`;
    }
}

function openIncidentAction(id, action) {
    if (action === "view") return showIncidentDetail(id);
    if (action === "more") return showIncidentDetail(id);
    const modal = phase68El("incidentActionModal");
    const valueWrap = phase68El("incidentActionValueWrap");
    const value = phase68El("incidentActionValue");
    const label = phase68El("incidentActionValueLabel");
    phase68El("incidentActionId").value = id;
    phase68El("incidentActionType").value = action;
    phase68El("incidentActionNote").value = "";
    phase68Text("incidentActionMessage", "");
    phase68Text("incidentActionTitle", `${action.charAt(0).toUpperCase() + action.slice(1)} Incident #${id}`);
    valueWrap?.classList.add("hidden");
    value?.removeAttribute("required");
    if (action === "priority") {
        valueWrap?.classList.remove("hidden"); label.textContent = "Priority (P1-P4)"; value.value = "P2"; value.placeholder = "P1, P2, P3 or P4"; value.required = true;
    } else if (action === "assign") {
        valueWrap?.classList.remove("hidden"); label.textContent = "Owner"; value.value = ""; value.placeholder = "Operator or team owner"; value.required = true;
    }
    modal?.classList.add("open"); modal?.setAttribute("aria-hidden", "false");
}
function closeIncidentActionModal() {
    phase68El("incidentActionModal")?.classList.remove("open");
    phase68El("incidentActionModal")?.setAttribute("aria-hidden", "true");
}
async function submitIncidentAction(event) {
    event.preventDefault();
    const id = Number(phase68El("incidentActionId")?.value);
    const action = phase68El("incidentActionType")?.value;
    const operator = (phase68El("incidentActionOperator")?.value || "dashboard-operator").trim();
    const note = (phase68El("incidentActionNote")?.value || "").trim() || null;
    const value = (phase68El("incidentActionValue")?.value || "").trim();
    const message = phase68El("incidentActionMessage");
    if (message) message.textContent = "Applying operation...";
    try {
        let path = `/incidents/${id}/${action}`;
        let payload = { changed_by: operator, note };
        if (action === "priority") {
            const priority = value.toUpperCase();
            if (!/^P[1-4]$/.test(priority)) throw new Error("Priority must be P1, P2, P3 or P4.");
            payload = { priority, changed_by: operator, note };
        } else if (action === "assign") {
            if (!value) throw new Error("Owner is required.");
            payload = { owner: value, changed_by: operator, note };
        }
        await phase68Fetch(path, { method: "POST", body: JSON.stringify(payload) });
        closeIncidentActionModal();
        await refreshPhase68();
        if (phase68State.selectedIncidentId === id && phase68El("incidentDrawer")?.classList.contains("open")) await showIncidentDetail(id);
    } catch (error) {
        if (message) message.textContent = error.message;
    }
}

async function evaluatePhase68Sla() {
    const button = phase68El("evaluateSlaButton");
    if (button) button.disabled = true;
    try { await phase68Fetch("/sre/sla/evaluate", { method: "POST", body: "{}" }); await refreshPhase68(); }
    catch (error) { console.error("SLA evaluation failed:", error); }
    finally { if (button) button.disabled = false; }
}

function initPhase68() {
    if (!phase68El("sreSection")) return;
    ["incidentSearch", "incidentStatusFilter", "incidentPriorityFilter", "incidentSlaFilter"].forEach(id => {
        phase68El(id)?.addEventListener(id === "incidentSearch" ? "input" : "change", renderPhase68Incidents);
    });
    phase68El("refreshSreButton")?.addEventListener("click", refreshPhase68);
    phase68El("evaluateSlaButton")?.addEventListener("click", evaluatePhase68Sla);
    phase68El("closeIncidentDrawer")?.addEventListener("click", closeIncidentDrawer);
    phase68El("incidentDrawerBackdrop")?.addEventListener("click", closeIncidentDrawer);
    phase68El("closeIncidentActionModal")?.addEventListener("click", closeIncidentActionModal);
    phase68El("cancelIncidentAction")?.addEventListener("click", closeIncidentActionModal);
    phase68El("incidentActionModal")?.addEventListener("click", e => { if (e.target?.dataset?.closeIncidentAction === "true") closeIncidentActionModal(); });
    phase68El("incidentActionForm")?.addEventListener("submit", submitIncidentAction);
    document.addEventListener("click", event => {
        const button = event.target.closest("[data-phase68-action]");
        if (!button) return;
        const id = Number(button.dataset.incidentId);
        const action = button.dataset.phase68Action;
        if (!id || !action) return;
        openIncidentAction(id, action);
    });
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") { closeIncidentDrawer(); closeIncidentActionModal(); }
    });
    refreshPhase68();
    phase68State.refreshTimer = window.setInterval(refreshPhase68, 15000);
}

document.addEventListener("DOMContentLoaded", initPhase68);


/* =========================================================
   GEOINFRA SIDEBAR NAVIGATION
   Uses the existing HTML data-scroll-target attributes.
   ========================================================= */

function initGeoInfraSidebarNavigation() {
    const main = document.getElementById("dashboardMain");
    const sidebar = document.querySelector(".sidebar");

    if (!main || !sidebar) {
        console.error("[Navigation] dashboardMain/sidebar missing");
        return;
    }

    const buttons = Array.from(
        sidebar.querySelectorAll(".nav-item[data-scroll-target]")
    );

    console.log(
        `[Navigation] ${buttons.length} sidebar controls initialized`
    );

    function activate(button) {
        buttons.forEach(btn => btn.classList.remove("active"));
        button.classList.add("active");
    }

    function goTo(button) {
        const targetId = button.dataset.scrollTarget;
        const target = document.getElementById(targetId);

        if (!target) {
            console.error(
                `[Navigation] Target #${targetId} not found`
            );
            return;
        }

        /*
         * Calculate target position relative to dashboardMain,
         * NOT relative to the browser window.
         */
        const mainRect = main.getBoundingClientRect();
        const targetRect = target.getBoundingClientRect();

        const destination =
            main.scrollTop +
            targetRect.top -
            mainRect.top -
            12;

        console.log(
            `[Navigation] ${button.innerText.trim()} -> #${targetId}`,
            {
                current: main.scrollTop,
                destination
            }
        );

        activate(button);

        main.scrollTo({
            top: Math.max(0, destination),
            behavior: "smooth"
        });

        /*
         * Leaflet resize protection.
         */
        if (targetId === "mapSection") {
            setTimeout(() => {
                try {
                    if (
                        typeof map !== "undefined" &&
                        map &&
                        typeof map.invalidateSize === "function"
                    ) {
                        map.invalidateSize();
                    }
                } catch (_) {}
            }, 400);
        }
    }

    /*
     * Capture-phase delegation.
     *
     * This fires before another dashboard handler can swallow
     * the click.
     */
    sidebar.addEventListener(
        "click",
        event => {
            const button = event.target.closest(
                ".nav-item[data-scroll-target]"
            );

            if (!button || !sidebar.contains(button)) {
                return;
            }

            event.preventDefault();
            event.stopPropagation();

            goTo(button);
        },
        true
    );
}

if (document.readyState === "loading") {
    document.addEventListener(
        "DOMContentLoaded",
        initGeoInfraSidebarNavigation
    );
} else {
    initGeoInfraSidebarNavigation();
}


/* =========================================================
   PHASE 6.9E — AUTOMATION + RELIABILITY ENGINEERING
   Read-only frontend integration. Existing phases unchanged.
========================================================= */
const phase69State = { refreshTimer: null, loading: false };
function phase69El(id){ return document.getElementById(id); }
function phase69Text(id,value){ const el=phase69El(id); if(el) el.textContent=value ?? "--"; }
function phase69Esc(value){ return String(value ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;"); }
function phase69Num(value,fallback=0){ const n=Number(value); return Number.isFinite(n)?n:fallback; }
function phase69Pct(value){ const n=Number(value); return Number.isFinite(n)?`${n.toFixed(n%1?1:0)}%`:"--"; }
function phase69Class(value){ return String(value ?? "unknown").toLowerCase().replaceAll("_","-").replace(/[^a-z0-9-]/g,""); }
function phase69Array(body, keys=[]){
    if(Array.isArray(body)) return body;
    if(!body || typeof body!=="object") return [];
    for(const key of keys) if(Array.isArray(body[key])) return body[key];
    if(body.results && typeof body.results==="object") {
        for(const key of keys) if(Array.isArray(body.results[key])) return body.results[key];
        if(Array.isArray(body.results.results)) return body.results.results;
    }
    return [];
}
function phase69Object(body, keys=[]){
    if(!body || typeof body!=="object" || Array.isArray(body)) return {};
    for(const key of keys) if(body[key] && typeof body[key]==="object" && !Array.isArray(body[key])) return body[key];
    if(body.results && typeof body.results==="object" && !Array.isArray(body.results)) return body.results;
    return body;
}
async function phase69Fetch(path){
    const response=await fetch(`${API_URL}${path}`,{headers:{Accept:"application/json"}});
    let body=null; try{body=await response.json();}catch(_){body=null;}
    if(!response.ok) throw new Error(`${path}: ${body?.detail || body?.message || `HTTP ${response.status}`}`);
    return body;
}
function phase69Validate(body,label){
    if(body && typeof body==="object" && "source" in body && body.source!=="LOCAL_PROJECT") console.warn(`[Phase 6.9E] ${label} unexpected source`,body.source);
    if(body && typeof body==="object" && body.external===true) console.warn(`[Phase 6.9E] ${label} unexpectedly marked external`);
}
function phase69RenderRunbooks(body){
    const all=phase69Array(body,["runbooks","items","results"]);
    const enabled=all.filter(x=>x?.enabled!==false);
    phase69Text("phase69Runbooks", enabled.length);
    const target=phase69El("phase69RunbookList"); if(!target) return;
    target.innerHTML=(enabled.slice(0,5).map(r=>{
        const name=r.name || r.runbook_name || r.runbook_key || r.key || `Runbook ${r.id ?? r.runbook_id ?? ""}`;
        const metric=r.metric || r.match_metric || "automation";
        const severity=r.severity || r.minimum_severity || r.min_severity || "enabled";
        return `<div class="phase69-row"><div class="phase69-row-main"><div class="phase69-row-title">${phase69Esc(name)}</div><div class="phase69-row-meta">${phase69Esc(metric)} · ${phase69Esc(severity)}</div></div><span class="phase69-badge enabled">Enabled</span></div>`;
    }).join("")) || '<div class="empty-state">No enabled runbooks returned.</div>';
}
function phase69RenderExecutions(body){
    const rows=phase69Array(body,["executions","items","results"]);
    phase69Text("phase69ExecutionCount",`${rows.length} execution${rows.length===1?"":"s"}`);
    const pending=rows.filter(x=>String(x?.status||"").toUpperCase()==="PENDING_APPROVAL").length;
    phase69Text("phase69Pending",pending);
    const target=phase69El("phase69ExecutionList"); if(!target) return;
    target.innerHTML=(rows.slice(0,7).map(x=>{
        const id=x.execution_id ?? x.id ?? "--";
        const title=x.runbook_name || x.runbook_key || x.runbook_id || `Execution ${id}`;
        const status=String(x.status || "UNKNOWN").toUpperCase();
        const when=x.completed_at || x.started_at || x.requested_at || x.created_at || "";
        return `<div class="phase69-row"><div class="phase69-row-main"><div class="phase69-row-title">${phase69Esc(title)}</div><div class="phase69-row-meta">#${phase69Esc(id)}${when?` · ${phase69Esc(new Date(when).toLocaleString())}`:""}</div></div><span class="phase69-badge ${phase69Class(status)}">${phase69Esc(status.replaceAll("_"," "))}</span></div>`;
    }).join("")) || '<div class="empty-state">No automation executions returned.</div>';
}
function phase69RenderAutomationSummary(body){
    const s=phase69Object(body,["summary","automation_summary"]);
    const total=phase69Num(s.total ?? s.total_executions ?? s.executions_total);
    const successful=phase69Num(s.successful ?? s.succeeded ?? s.successful_executions);
    const pending=phase69Num(s.pending ?? s.pending_approval ?? s.pending_approvals);
    let rate=s.success_percentage ?? s.success_rate ?? s.success_percent;
    if(rate==null && total>0) rate=successful/total*100;
    phase69Text("phase69SuccessRate",phase69Pct(rate));
    if(pending || phase69El("phase69Pending")?.textContent==="--") phase69Text("phase69Pending",pending);
}
function phase69RenderObjectives(body){
    const rows=phase69Array(body,["objectives","items","results"]);
    phase69Text("phase69ObjectiveCount",`${rows.length} objective${rows.length===1?"":"s"}`);
    const target=phase69El("phase69ObjectiveList"); if(!target) return;
    target.innerHTML=(rows.slice(0,8).map(o=>{
        const name=o.objective_name || o.name || o.objective_key || `SLO ${o.objective_id ?? o.id ?? ""}`;
        const metric=o.metric || "metric";
        const targetPct=o.target_percentage ?? o.target_percent ?? o.target;
        const status=String(o.status || o.latest_status || "CONFIGURED").toUpperCase();
        return `<div class="phase69-row"><div class="phase69-row-main"><div class="phase69-row-title">${phase69Esc(name)}</div><div class="phase69-row-meta">${phase69Esc(metric)}${targetPct!=null?` · target ${phase69Esc(targetPct)}%`:""}</div></div><span class="phase69-badge ${phase69Class(status)}">${phase69Esc(status.replaceAll("_"," "))}</span></div>`;
    }).join("")) || '<div class="empty-state">No reliability objectives returned.</div>';
}
function phase69RenderReliabilitySummary(body){
    const s=phase69Object(body,["summary","reliability_summary"]);
    const healthy=phase69Num(s.healthy ?? s.healthy_objectives);
    const atRisk=phase69Num(s.at_risk ?? s.at_risk_objectives);
    const breached=phase69Num(s.breached ?? s.breached_objectives);
    const unknown=phase69Num(s.unknown ?? s.unknown_objectives);
    phase69Text("phase69Healthy",healthy); phase69Text("phase69Breached",breached);
    const target=phase69El("phase69ReliabilitySummary"); if(!target) return;
    target.innerHTML=`<div class="phase69-summary-cell"><span>Healthy</span><strong>${healthy}</strong></div><div class="phase69-summary-cell"><span>At Risk</span><strong>${atRisk}</strong></div><div class="phase69-summary-cell"><span>Breached</span><strong>${breached}</strong></div><div class="phase69-summary-cell"><span>Unknown</span><strong>${unknown}</strong></div>`;
}
async function refreshPhase69(){
    if(phase69State.loading || !phase69El("automationReliabilitySection")) return;
    phase69State.loading=true;
    const status=phase69El("phase69RefreshStatus"); if(status){status.textContent="REFRESHING";status.classList.add("loading");status.classList.remove("error");}
    try{
        const [runbooks,executions,automationSummary,objectives,measurements,reliabilitySummary]=await Promise.all([
            phase69Fetch("/automation/runbooks"), phase69Fetch("/automation/executions"), phase69Fetch("/automation/summary"),
            phase69Fetch("/reliability/objectives"), phase69Fetch("/reliability/measurements"), phase69Fetch("/reliability/summary")
        ]);
        [[runbooks,"runbooks"],[executions,"executions"],[automationSummary,"automation summary"],[objectives,"objectives"],[measurements,"measurements"],[reliabilitySummary,"reliability summary"]].forEach(([b,l])=>phase69Validate(b,l));
        phase69RenderRunbooks(runbooks); phase69RenderExecutions(executions); phase69RenderAutomationSummary(automationSummary); phase69RenderObjectives(objectives); phase69RenderReliabilitySummary(reliabilitySummary);
        if(status){status.textContent="LIVE";status.classList.remove("loading","error");}
    }catch(error){
        console.error("Phase 6.9E dashboard refresh failed:",error);
        if(status){status.textContent="API ERROR";status.classList.remove("loading");status.classList.add("error");}
    }finally{phase69State.loading=false;}
}
function initPhase69(){
    if(!phase69El("automationReliabilitySection")) return;
    phase69El("refreshPhase69Button")?.addEventListener("click",refreshPhase69);
    refreshPhase69();
    if(phase69State.refreshTimer) clearInterval(phase69State.refreshTimer);
    phase69State.refreshTimer=window.setInterval(refreshPhase69,30000);
}
if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",initPhase69); else initPhase69();


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

