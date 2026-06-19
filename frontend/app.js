let map;
let markers = [];
let riskLayers = [];
let socket;

// -----------------------------
// INIT MAP
// -----------------------------
function initMap() {

    map = L.map('map').setView([20, 0], 2);

    L.tileLayer(
        'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        {
            attribution: '&copy; OpenStreetMap & CARTO'
        }
    ).addTo(map);

    // CLICK → NEAREST INFRASTRUCTURE
    map.on("click", function (e) {

        const lat = e.latlng.lat;
        const lon = e.latlng.lng;

        fetch(`http://localhost:8000/nearest?lat=${lat}&lon=${lon}`)
            .then(res => res.json())
            .then(data => {

                const distanceKm =
                    ((data.distance_meters || 0) / 1000)
                    .toFixed(2);

                L.popup()
                    .setLatLng([lat, lon])
                    .setContent(`
                        <b>Nearest Infrastructure</b><br/>
                        Name: ${data.name}<br/>
                        Type: ${data.infra_type}<br/>
                        Distance: ${distanceKm} km
                    `)
                    .openOn(map);
            })
            .catch(err => console.error(err));
    });
}

// -----------------------------
// DRAW RISK ZONES
// -----------------------------
function drawRiskZones(data) {

    riskLayers.forEach(layer => {
        map.removeLayer(layer);
    });

    riskLayers = [];

    const cities = {};

    data.forEach(point => {

        let city = "Other";

        if (point.name.includes("London")) city = "London";
        else if (point.name.includes("Mumbai")) city = "Mumbai";
        else if (point.name.includes("Delhi")) city = "Delhi";
        else if (point.name.includes("Bangalore")) city = "Bangalore";
        else if (point.name.includes("Manchester")) city = "Manchester";
        else if (point.name.includes("Tokyo")) city = "Tokyo";
        else if (point.name.includes("New York")) city = "New York";

        if (!cities[city]) {
            cities[city] = [];
        }

        cities[city].push(point);
    });

    Object.keys(cities).forEach(city => {

        const points = cities[city];

        if (points.length === 0) return;

        const avgLat =
            points.reduce((s, p) => s + p.latitude, 0)
            / points.length;

        const avgLon =
            points.reduce((s, p) => s + p.longitude, 0)
            / points.length;

        let color = "green";
        let radius = 25000;

        if (points.length >= 4) {
            color = "orange";
            radius = 50000;
        }

        if (points.length >= 8) {
            color = "red";
            radius = 80000;
        }

        const zone = L.circle(
            [avgLat, avgLon],
            {
                radius: radius,
                color: color,
                fillColor: color,
                fillOpacity: 0.25,
                weight: 2
            }
        )
        .addTo(map)
        .bindPopup(`
            <b>${city} Risk Zone</b><br/>
            Infrastructure Count: ${points.length}
        `);

        riskLayers.push(zone);
    });
}

// -----------------------------
// UPDATE VISUALS
// -----------------------------
function updateVisuals(data) {

    markers.forEach(marker => {
        map.removeLayer(marker);
    });

    markers = [];

    data.forEach(point => {

        const marker = L.marker([
            point.latitude,
            point.longitude
        ])
        .addTo(map)
        .bindPopup(`
            <b>${point.name}</b><br/>
            Type: ${point.infra_type}
        `);

        markers.push(marker);
    });

    drawRiskZones(data);

    const stats = document.getElementById("stats");

    if (stats) {

        const traffic =
            data.filter(x => x.infra_type === "traffic").length;

        const sensor =
            data.filter(x => x.infra_type === "sensor").length;

        const environment =
            data.filter(x => x.infra_type === "environment").length;

        stats.innerHTML = `
            <strong>Total Infrastructure:</strong> ${data.length}<br/>
            <strong>Traffic Nodes:</strong> ${traffic}<br/>
            <strong>Sensors:</strong> ${sensor}<br/>
            <strong>Environment:</strong> ${environment}
        `;
    }
}

// -----------------------------
// LOAD DATA
// -----------------------------
function loadLocations() {

    fetch("http://localhost:8000/locations")
        .then(res => res.json())
        .then(data => {
            updateVisuals(data);
        })
        .catch(err => console.error(err));
}

// -----------------------------
// WEBSOCKET
// -----------------------------
function connectWebSocket() {

    socket = new WebSocket(
        "ws://localhost:8000/ws/locations"
    );

    socket.onopen = () => {
        console.log("WebSocket Connected");
    };

    socket.onmessage = (event) => {

        const data =
            JSON.parse(event.data);

        updateVisuals(data);
    };

    socket.onerror = (error) => {
        console.error(error);
    };
}

// -----------------------------
// START APP
// -----------------------------
window.onload = () => {

    initMap();

    loadLocations();

    connectWebSocket();
};
