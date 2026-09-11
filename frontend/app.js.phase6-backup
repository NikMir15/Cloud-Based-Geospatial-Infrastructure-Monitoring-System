let map;

let clusterGroup;

let infrastructureData = [];

let riskData = [];

let earthquakeData = [];

let earthquakeLayers = [];

let locationSocket;

let eventSocket;


/* =========================================================
   API
========================================================= */

const API_URL =
    `${window.location.protocol}//${window.location.hostname}:8000`;



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
            (type || "")
            .toLowerCase()
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
        (severity || "low")
        .toLowerCase();


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
   MAP
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


    L.control
        .zoom(
            {
                position:
                    "bottomright"
            }
        )
        .addTo(map);


    /* Free OpenStreetMap tiles */

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
   INFRASTRUCTURE MARKER
========================================================= */

function createInfrastructureMarker(point) {

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


    const baseColor =
        getInfrastructureColor(
            point.infra_type
        );


    const markerColor =
        (
            risk
            &&
            risk.risk_score
            >= 30
        )
        ?
        getRiskColor(
            severity
        )
        :
        baseColor;


    const marker =
        L.circleMarker(
            [
                point.latitude,
                point.longitude
            ],
            {
                radius:
                    risk
                    ? 9
                    : 7,

                color:
                    markerColor,

                fillColor:
                    markerColor,

                fillOpacity:
                    0.95,

                weight:
                    risk
                    ? 3
                    : 2
            }
        );


    let riskHtml =
        `
        <strong>
            Estimated Risk:
        </strong>

        Low
        `;


    if (risk) {

        riskHtml =
            `
            <strong>
                Estimated Exposure:
            </strong>

            ${risk.risk_score}/100

            <br>

            <strong>
                Severity:
            </strong>

            ${escapeHtml(
                risk.severity
            )}

            <br>

            <strong>
                Hazard:
            </strong>

            M${risk.magnitude}
            earthquake

            <br>

            <strong>
                Distance:
            </strong>

            ${risk.distance_km}
            km
            `;
    }


    marker.bindPopup(
        `
        <strong>
            ${escapeHtml(point.name)}
        </strong>

        <br><br>

        ${escapeHtml(
            point.description
            || ""
        )}

        <br>

        <strong>
            Type:
        </strong>

        ${escapeHtml(
            point.infra_type
            || "Unknown"
        )}

        <br>

        <strong>
            Operational Status:
        </strong>

        ${escapeHtml(
            point.status
            || "operational"
        )}

        <br><br>

        ${riskHtml}
        `
    );


    return marker;
}



/* =========================================================
   DRAW INFRASTRUCTURE
========================================================= */

function renderInfrastructure(
    data
) {

    clusterGroup
        .clearLayers();


    data.forEach(
        point => {

            if (
                point.latitude
                == null

                ||

                point.longitude
                == null
            ) {

                return;
            }


            clusterGroup
                .addLayer(
                    createInfrastructureMarker(
                        point
                    )
                );
        }
    );
}



/* =========================================================
   FILTER TYPES
========================================================= */

function populateTypeFilter(data) {

    const select =
        document.getElementById(
            "typeFilter"
        );


    const existing =
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


    select.innerHTML =
        `
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
            existing
        )
    ) {

        select.value =
            existing;
    }
}



/* =========================================================
   SEARCH + FILTER
========================================================= */

function applyFilters() {

    const search =
        document
        .getElementById(
            "searchBox"
        )
        .value
        .trim()
        .toLowerCase();


    const selectedType =
        document
        .getElementById(
            "typeFilter"
        )
        .value;


    const selectedRisk =
        document
        .getElementById(
            "riskFilter"
        )
        .value;


    const filtered =
        infrastructureData
        .filter(
            point => {

                const text =
                    `
                    ${point.name || ""}
                    ${point.description || ""}
                    ${point.infra_type || ""}
                    `
                    .toLowerCase();


                const matchesSearch =
                    text.includes(
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
   NEAREST INFRASTRUCTURE
========================================================= */

async function handleMapClick(event) {

    try {

        const response =
            await fetch(
                `${API_URL}/nearest?lat=${event.latlng.lat}&lon=${event.latlng.lng}`
            );


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
   LOAD LOCATIONS
========================================================= */

async function loadLocations() {

    const response =
        await fetch(
            `${API_URL}/locations`
        );


    infrastructureData =
        await response.json();


    populateTypeFilter(
        infrastructureData
    );


    applyFilters();
}



/* =========================================================
   LOAD RISK
========================================================= */

async function loadRisk() {

    try {

        const response =
            await fetch(
                `${API_URL}/risk`
            );


        const data =
            await response.json();


        riskData =
            data.assets
            || [];


        document
            .getElementById(
                "affectedAssets"
            )
            .textContent =
            data.affected_assets
            || 0;


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


    const significant =
        data
        .filter(
            item =>
                item.risk_score
                >= 30
        )
        .slice(
            0,
            8
        );


    if (
        significant.length
        === 0
    ) {

        container.innerHTML =
            `
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
                                    )}
                                "
                            >
                                ${escapeHtml(
                                    asset.severity
                                )}
                            </span>

                        </div>

                        <div class="event-type">

                            Exposure:
                            ${asset.risk_score}/100

                        </div>

                        <div class="event-description">

                            M${asset.magnitude}
                            earthquake

                            ·

                            ${asset.distance_km}
                            km away

                        </div>

                    </div>
                `;
            }
        )
        .join("");
}



/* =========================================================
   LIVE EARTHQUAKES
========================================================= */

function renderEarthquakes(events) {

    earthquakeLayers
        .forEach(
            layer =>
                map.removeLayer(
                    layer
                )
        );


    earthquakeLayers =
        [];


    events.forEach(
        event => {

            const color =
                getRiskColor(
                    event.severity
                );


            /* Earthquake centre */

            const marker =
                L.circleMarker(
                    [
                        event.latitude,
                        event.longitude
                    ],
                    {
                        radius:
                            Math.max(
                                5,
                                Math.min(
                                    13,
                                    event.magnitude
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
                            1.5
                    }
                )
                .addTo(map);


            marker.bindPopup(
                `
                <div class="quake-popup">

                    <span class="live-source">
                        LIVE USGS
                    </span>

                    <h3>
                        M${event.magnitude}
                    </h3>

                    <strong>
                        ${escapeHtml(
                            event.place
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

                    Estimated exposure radius:
                    ${event.radius_km}
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


            /*
               Only draw exposure circles for stronger
               earthquakes so the world map stays readable.
            */

            if (
                event.magnitude >= 4.5
            ) {

                const zone =
                    L.circle(
                        [
                            event.latitude,
                            event.longitude
                        ],
                        {
                            radius:
                                event.radius_km
                                * 1000,

                            color:
                                color,

                            fillColor:
                                color,

                            fillOpacity:
                                0.035,

                            weight:
                                1,

                            dashArray:
                                "5 5"
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
   EVENT FEED
========================================================= */

function renderEventFeed(events) {

    const container =
        document.getElementById(
            "eventFeed"
        );


    const displayEvents =
        [...events]
        .sort(
            (a, b) =>
                b.magnitude
                -
                a.magnitude
        )
        .slice(
            0,
            12
        );


    if (
        displayEvents.length
        === 0
    ) {

        container.innerHTML =
            `
            <div class="empty-state">

                No USGS M2.5+ earthquakes
                currently available.

            </div>
            `;

        return;
    }


    container.innerHTML =
        displayEvents
        .map(
            event => {

                return `
                    <div
                        class="event-card"
                        onclick="
                            focusEarthquake(
                                ${event.latitude},
                                ${event.longitude}
                            )
                        "
                    >

                        <div class="event-header">

                            <span class="event-title">

                                M${event.magnitude}

                                ${escapeHtml(
                                    event.place
                                )}

                            </span>

                            <span
                                class="
                                    severity
                                    ${escapeHtml(
                                        event.severity
                                    )}
                                "
                            >

                                ${escapeHtml(
                                    event.severity
                                )}

                            </span>

                        </div>


                        <div class="event-type">

                            LIVE USGS

                            ·

                            Depth
                            ${
                                event.depth_km
                                ?? "?"
                            }
                            km

                        </div>


                        <div class="event-description">

                            ${
                                formatEventAge(
                                    event.timestamp
                                )
                            }

                        </div>

                    </div>
                `;
            }
        )
        .join("");
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


        const data =
            await response.json();


        document
            .getElementById(
                "totalInfrastructure"
            )
            .textContent =
            data.total_infrastructure
            || 0;


        document
            .getElementById(
                "liveEarthquakes"
            )
            .textContent =
            data.live_earthquakes
            || 0;


        document
            .getElementById(
                "affectedAssets"
            )
            .textContent =
            data.affected_assets
            || 0;


        document
            .getElementById(
                "highRisk"
            )
            .textContent =
            data.high_risk_assets
            || 0;


        document
            .getElementById(
                "criticalEvents"
            )
            .textContent =
            data.critical_events
            || 0;


        document
            .getElementById(
                "feedStatus"
            )
            .textContent =
            data.live
            ?
            "LIVE"
            :
            "CACHE";


        const source =
            document.getElementById(
                "dataSourceStatus"
            );


        source.textContent =
            data.live
            ?
            "USGS LIVE"
            :
            "USGS CACHE";


        source.classList.toggle(
            "stale",
            !data.live
        );


        renderTypeStats(
            data.by_type
            || {}
        );

    }

    catch (error) {

        console.error(
            "Analytics error:",
            error
        );
    }
}



/* =========================================================
   TYPE STATS
========================================================= */

function renderTypeStats(stats) {

    const container =
        document.getElementById(
            "typeStats"
        );


    container.innerHTML =
        Object
        .entries(stats)
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
   LOAD EVENTS
========================================================= */

async function loadEarthquakes() {

    try {

        const response =
            await fetch(
                `${API_URL}/events`
            );


        const data =
            await response.json();


        earthquakeData =
            data.events
            || [];


        renderEarthquakes(
            earthquakeData
        );


        document
            .getElementById(
                "dataSourceStatus"
            )
            .textContent =
            data.live
            ?
            "USGS LIVE"
            :
            "USGS CACHE";

    }

    catch (error) {

        console.error(
            "Earthquake load error:",
            error
        );


        document
            .getElementById(
                "dataSourceStatus"
            )
            .textContent =
            "USGS OFFLINE";
    }
}



/* =========================================================
   WEBSOCKET EVENTS
========================================================= */

function connectEventSocket() {

    const protocol =
        window.location.protocol
        === "https:"
        ?
        "wss"
        :
        "ws";


    eventSocket =
        new WebSocket(
            `${protocol}://${window.location.hostname}:8000/ws/events`
        );


    eventSocket.onopen =
        () => {

            console.log(
                "USGS live WebSocket connected"
            );
        };


    eventSocket.onmessage =
        async event => {

            const message =
                JSON.parse(
                    event.data
                );


            if (
                message.type
                === "earthquakes"
            ) {

                earthquakeData =
                    message.data
                    || [];


                renderEarthquakes(
                    earthquakeData
                );


                await Promise.all(
                    [
                        loadRisk(),
                        loadAnalytics(),
                        loadLocations()
                    ]
                );
            }
        };


    eventSocket.onclose =
        () => {

            setTimeout(
                connectEventSocket,
                5000
            );
        };
}



/* =========================================================
   LOCATION WEBSOCKET
========================================================= */

function connectLocationSocket() {

    const protocol =
        window.location.protocol
        === "https:"
        ?
        "wss"
        :
        "ws";


    locationSocket =
        new WebSocket(
            `${protocol}://${window.location.hostname}:8000/ws/locations`
        );


    locationSocket.onmessage =
        event => {

            const message =
                JSON.parse(
                    event.data
                );


            if (
                message.type
                === "locations"
            ) {

                infrastructureData =
                    message.data;

                applyFilters();
            }
        };


    locationSocket.onclose =
        () => {

            setTimeout(
                connectLocationSocket,
                5000
            );
        };
}



/* =========================================================
   MAP FOCUS
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


    const seconds =
        Math.max(
            0,
            Math.floor(
                (
                    Date.now()
                    -
                    eventTime.getTime()
                )
                / 1000
            )
        );


    if (seconds < 60) {

        return (
            `${seconds} sec ago`
        );
    }


    const minutes =
        Math.floor(
            seconds / 60
        );


    if (minutes < 60) {

        return (
            `${minutes} min ago`
        );
    }


    const hours =
        Math.floor(
            minutes / 60
        );


    if (hours < 24) {

        return (
            `${hours} hr ago`
        );
    }


    return (
        `${Math.floor(
            hours / 24
        )} day ago`
    );
}



/* =========================================================
   ESCAPE HTML
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
   START
========================================================= */

window.addEventListener(
    "load",
    async () => {

        initMap();


        document
            .getElementById(
                "searchBox"
            )
            .addEventListener(
                "input",
                applyFilters
            );


        document
            .getElementById(
                "typeFilter"
            )
            .addEventListener(
                "change",
                applyFilters
            );


        document
            .getElementById(
                "riskFilter"
            )
            .addEventListener(
                "change",
                applyFilters
            );


        await Promise.all(
            [
                loadLocations(),
                loadRisk(),
                loadAnalytics(),
                loadEarthquakes()
            ]
        );


        connectLocationSocket();

        connectEventSocket();
    }
);
