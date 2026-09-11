/* =========================================================
   INFRASTRUCTURE SITUATIONAL AWARENESS PLATFORM

   Phase 6.2 Frontend

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
