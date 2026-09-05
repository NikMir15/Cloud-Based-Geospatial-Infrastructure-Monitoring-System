let map;

let clusterGroup;

let infrastructureData = [];

let eventLayers = [];

let eventData = [];

let locationSocket;

let eventSocket;


const API_URL =
    `${window.location.protocol}//${window.location.hostname}:8000`;


// =========================================================
// INFRASTRUCTURE COLORS
// =========================================================

function getMarkerColor(type) {

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


// =========================================================
// INITIALISE MAP
// =========================================================

function initMap() {

    map =
        L.map(
            "map",
            {
                zoomControl:
                    false,

                worldCopyJump:
                    true
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


    L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        {
            maxZoom:
                19,

            attribution:
                "&copy; OpenStreetMap & CARTO"
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


// =========================================================
// CUSTOM CLUSTER ICON
// =========================================================

function createClusterIcon(cluster) {

    const count =
        cluster.getChildCount();


    let clusterClass =
        "cluster-low";


    let size =
        40;


    if (count >= 10) {

        clusterClass =
            "cluster-medium";

        size =
            46;
    }


    if (count >= 20) {

        clusterClass =
            "cluster-high";

        size =
            52;
    }


    return L.divIcon(
        {
            html:
                `
                <div
                    class="
                        custom-cluster
                        ${clusterClass}
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


// =========================================================
// NEAREST INFRASTRUCTURE
// =========================================================

async function handleMapClick(event) {

    try {

        const lat =
            event.latlng.lat;

        const lon =
            event.latlng.lng;


        const response =
            await fetch(
                `${API_URL}/nearest?lat=${lat}&lon=${lon}`
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

                <strong>Name:</strong>
                ${escapeHtml(data.name)}

                <br>

                <strong>Type:</strong>
                ${escapeHtml(data.infra_type)}

                <br>

                <strong>Distance:</strong>
                ${Number(
                    data.distance_km || 0
                ).toFixed(2)}
                km
                `
            )
            .openOn(map);

    }

    catch (error) {

        console.error(
            "Nearest infrastructure error:",
            error
        );
    }
}


// =========================================================
// INFRASTRUCTURE MARKER
// =========================================================

function createInfrastructureMarker(point) {

    const color =
        getMarkerColor(
            point.infra_type
        );


    const marker =
        L.circleMarker(
            [
                point.latitude,
                point.longitude
            ],
            {
                radius:
                    7,

                color:
                    color,

                fillColor:
                    color,

                fillOpacity:
                    0.95,

                weight:
                    2
            }
        );


    marker.bindPopup(
        `
        <strong>
            ${escapeHtml(point.name)}
        </strong>

        <br><br>

        ${escapeHtml(
            point.description || ""
        )}

        <br>

        <strong>Type:</strong>

        ${escapeHtml(
            point.infra_type
        )}
        `
    );


    return marker;
}


// =========================================================
// RENDER INFRASTRUCTURE
// =========================================================

function renderInfrastructure(data) {

    clusterGroup
        .clearLayers();


    data.forEach(
        point => {

            if (
                point.latitude == null
                ||
                point.longitude == null
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


// =========================================================
// TYPE FILTER
// =========================================================

function populateTypeFilter(data) {

    const select =
        document.getElementById(
            "typeFilter"
        );


    const selectedValue =
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
            selectedValue
        )
    ) {

        select.value =
            selectedValue;
    }
}


// =========================================================
// SEARCH + FILTER
// =========================================================

function applyFilters() {

    const search =
        document
        .getElementById(
            "searchBox"
        )
        .value
        .toLowerCase()
        .trim();


    const selectedType =
        document
        .getElementById(
            "typeFilter"
        )
        .value;


    const filtered =
        infrastructureData
        .filter(
            item => {

                const text =
                    `
                    ${item.name || ""}
                    ${item.description || ""}
                    ${item.infra_type || ""}
                    `
                    .toLowerCase();


                return (

                    text.includes(
                        search
                    )

                    &&

                    (
                        selectedType
                        === "all"

                        ||

                        item.infra_type
                        === selectedType
                    )
                );
            }
        );


    renderInfrastructure(
        filtered
    );
}


// =========================================================
// ANALYTICS
// =========================================================

async function loadAnalytics() {

    try {

        const response =
            await fetch(
                `${API_URL}/analytics`
            );


        const analytics =
            await response.json();


        document
            .getElementById(
                "totalInfrastructure"
            )
            .textContent =
            analytics.total_infrastructure
            ?? 0;


        document
            .getElementById(
                "activeAlerts"
            )
            .textContent =
            analytics.active_alerts
            ?? 0;


        document
            .getElementById(
                "highRisk"
            )
            .textContent =
            analytics.high_risk_assets
            ?? 0;


        document
            .getElementById(
                "criticalEvents"
            )
            .textContent =
            analytics.critical_events
            ?? 0;


        renderTypeStats(
            analytics.by_type
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


// =========================================================
// TYPE STATISTICS
// =========================================================

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

                const color =
                    getMarkerColor(
                        type
                    );


                return `
                    <div class="type-stat">

                        <div class="type-stat-name">

                            <span
                                class="type-color-dot"
                                style="
                                    background:${color}
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


// =========================================================
// LOAD INFRASTRUCTURE
// =========================================================

async function loadLocations() {

    try {

        const response =
            await fetch(
                `${API_URL}/locations`
            );


        infrastructureData =
            await response.json();


        populateTypeFilter(
            infrastructureData
        );


        renderInfrastructure(
            infrastructureData
        );

    }

    catch (error) {

        console.error(
            "Infrastructure load error:",
            error
        );
    }
}


// =========================================================
// EVENT COLOR
// =========================================================

function getEventColor(event) {

    const severity =
        event.severity
        ?.toLowerCase();


    if (severity === "critical") {
        return "#ff4b5c";
    }


    if (severity === "high") {
        return "#ff853d";
    }


    return "#ffc845";
}


// =========================================================
// RENDER HAZARDS
// =========================================================

function renderEvents(events) {

    eventLayers
        .forEach(
            layer =>
                map.removeLayer(layer)
        );


    eventLayers =
        [];


    events.forEach(
        event => {

            const color =
                getEventColor(
                    event
                );


            const radius =
                Number(
                    event.radius_km
                    || 50
                )
                * 1000;


            const zone =
                L.circle(
                    [
                        event.latitude,
                        event.longitude
                    ],
                    {
                        radius:
                            radius,

                        color:
                            color,

                        fillColor:
                            color,

                        fillOpacity:
                            0.09,

                        weight:
                            1.5,

                        dashArray:
                            "6 5"
                    }
                )
                .addTo(map);


            const marker =
                L.circleMarker(
                    [
                        event.latitude,
                        event.longitude
                    ],
                    {
                        radius:
                            9,

                        color:
                            "#ffffff",

                        fillColor:
                            color,

                        fillOpacity:
                            1,

                        weight:
                            2
                    }
                )
                .addTo(map);


            marker.bindPopup(
                `
                <strong>
                    ${escapeHtml(event.title)}
                </strong>

                <br><br>

                <strong>Event:</strong>
                ${escapeHtml(event.event_type)}

                <br>

                <strong>Severity:</strong>
                ${escapeHtml(event.severity)}

                <br>

                <strong>Radius:</strong>
                ${event.radius_km} km

                <br><br>

                ${escapeHtml(
                    event.description
                )}
                `
            );


            eventLayers.push(
                zone,
                marker
            );
        }
    );


    renderEventFeed(
        events
    );
}


// =========================================================
// EVENT FEED
// =========================================================

function renderEventFeed(events) {

    const container =
        document.getElementById(
            "eventFeed"
        );


    if (
        events.length === 0
    ) {

        container.innerHTML =
            `
            <div class="event-card">
                No active hazard events.
            </div>
            `;

        return;
    }


    container.innerHTML =
        events
        .map(
            (event, index) => {

                return `
                    <div
                        class="event-card"
                        onclick="
                            focusEvent(${index})
                        "
                    >

                        <div class="event-header">

                            <span class="event-title">
                                ${escapeHtml(
                                    event.title
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

                            ${escapeHtml(
                                event.event_type
                            )}

                            ·

                            ${event.radius_km} km radius

                        </div>


                        <div class="event-description">

                            ${escapeHtml(
                                event.description
                            )}

                        </div>

                    </div>
                `;
            }
        )
        .join("");
}


// =========================================================
// FOCUS EVENT
// =========================================================

function focusEvent(index) {

    const event =
        eventData[index];


    if (!event) {
        return;
    }


    map.flyTo(
        [
            event.latitude,
            event.longitude
        ],
        6,
        {
            duration:
                1.3
        }
    );
}


// =========================================================
// LOAD EVENTS
// =========================================================

async function loadEvents() {

    try {

        const response =
            await fetch(
                `${API_URL}/events`
            );


        eventData =
            await response.json();


        renderEvents(
            eventData
        );

    }

    catch (error) {

        console.error(
            "Event load error:",
            error
        );
    }
}


// =========================================================
// LOCATION WEBSOCKET
// =========================================================

function connectLocationSocket() {

    const protocol =
        window.location.protocol
        === "https:"
        ? "wss"
        : "ws";


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


// =========================================================
// EVENT WEBSOCKET
// =========================================================

function connectEventSocket() {

    const protocol =
        window.location.protocol
        === "https:"
        ? "wss"
        : "ws";


    eventSocket =
        new WebSocket(
            `${protocol}://${window.location.hostname}:8000/ws/events`
        );


    eventSocket.onmessage =
        event => {

            const message =
                JSON.parse(
                    event.data
                );


            if (
                message.type
                === "events"
            ) {

                eventData =
                    message.data;


                renderEvents(
                    eventData
                );


                loadAnalytics();
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


// =========================================================
// ESCAPE HTML
// =========================================================

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


// =========================================================
// START
// =========================================================

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


        await Promise.all(
            [
                loadLocations(),
                loadAnalytics(),
                loadEvents()
            ]
        );


        connectLocationSocket();

        connectEventSocket();
    }
);
