let map;
let markers = [];
let socket;

// -----------------------------
// INIT MAP
// -----------------------------
function initMap() {
    map = L.map('map').setView([20, 0], 2);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    // Click event → NEAREST SENSOR
    map.on("click", function (e) {
        const lat = e.latlng.lat;
        const lng = e.latlng.lng;

        fetch(`http://localhost:8000/nearest?lat=${lat}&lon=${lng}`)
            .then(res => res.json())
            .then(data => {
                console.log("Nearest:", data);

                if (data && data.distance_meters !== undefined) {

                    L.popup()
                        .setLatLng([lat, lng])
                        .setContent(
                            `
                            <b>Nearest Sensor</b><br/>
                            Name: ${data.name}<br/>
                            Type: ${data.infra_type}<br/>
                            Distance: ${data.distance_meters.toFixed(2)} meters
                            `
                        )
                        .openOn(map);
                }
            })
            .catch(err => console.error("Nearest API error:", err));
    });
}


// -----------------------------
// UPDATE MARKERS
// -----------------------------
function updateMarkers(data) {
    // remove old markers
    markers.forEach(m => map.removeLayer(m));
    markers = [];

    data.forEach(point => {
        const marker = L.marker([point.latitude, point.longitude])
            .addTo(map)
            .bindPopup(`
                <b>${point.name}</b><br/>
                Type: ${point.infra_type || "N/A"}<br/>
                ${point.description || ""}
            `);

        markers.push(marker);
    });
}


// -----------------------------
// LOAD INITIAL DATA
// -----------------------------
function loadInitialData() {
    fetch("http://localhost:8000/locations")
        .then(res => res.json())
        .then(data => {
            updateMarkers(data);
        })
        .catch(err => console.error("Locations error:", err));
}


// -----------------------------
// WEBSOCKET LIVE UPDATES
// -----------------------------
function connectWebSocket() {
    socket = new WebSocket("ws://localhost:8000/ws/locations");

    socket.onopen = () => {
        console.log("WebSocket connected");
    };

    socket.onmessage = function (event) {
        const data = JSON.parse(event.data);
        updateMarkers(data);
    };

    socket.onerror = function (err) {
        console.error("WebSocket error:", err);
    };
}


// -----------------------------
// INIT APP
// -----------------------------
window.onload = function () {
    initMap();
    loadInitialData();
    connectWebSocket();
};
