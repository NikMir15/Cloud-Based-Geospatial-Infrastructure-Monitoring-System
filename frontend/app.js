// ========================================
// Infrastructure Monitoring System
// ========================================

// Create map
var map = L.map('map', {
    zoomControl: false
}).setView([54.5, -3], 5);

// Store markers
let markers = [];

// Zoom controls
L.control.zoom({
    position: 'bottomright'
}).addTo(map);

// Dark theme map
L.tileLayer(
    'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    {
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        maxZoom: 19
    }
).addTo(map);

// ========================================
// Load Infrastructure Locations
// ========================================

fetch("http://127.0.0.1:8000/locations")
.then(response => response.json())
.then(data => {

    data.forEach(point => {

        let markerColor = "blue";

        // Assign colors based on infrastructure type
        if (point.infra_type === "Cloud") {
            markerColor = "red";
        }

        if (point.infra_type === "Education") {
            markerColor = "green";
        }

        if (point.infra_type === "Healthcare") {
            markerColor = "blue";
        }

        if (point.infra_type === "Transport") {
            markerColor = "orange";
        }

        const marker = L.circleMarker(
            [point.latitude, point.longitude],
            {
                radius: 10,
                color: markerColor,
                fillColor: markerColor,
                fillOpacity: 0.8,
                weight: 2
            }
        );

        marker.bindPopup(`
            <b>${point.name}</b><br>
            ${point.description}<br>
            <b>Type:</b> ${point.infra_type}
        `);

        marker.infraType = point.infra_type;

        marker.addTo(map);

        markers.push(marker);

    });

})
.catch(error => {
    console.error("Error loading locations:", error);
});

// ========================================
// Infrastructure Filters
// ========================================

function applyFilters() {

    markers.forEach(marker => {

        let visible = false;

        if (
            marker.infraType === "Cloud" &&
            document.getElementById("cloudFilter").checked
        ) {
            visible = true;
        }

        if (
            marker.infraType === "Education" &&
            document.getElementById("educationFilter").checked
        ) {
            visible = true;
        }

        if (
            marker.infraType === "Healthcare" &&
            document.getElementById("healthcareFilter").checked
        ) {
            visible = true;
        }

        if (
            marker.infraType === "Transport" &&
            document.getElementById("transportFilter").checked
        ) {
            visible = true;
        }

        if (visible) {

            if (!map.hasLayer(marker)) {
                marker.addTo(map);
            }

        } else {

            if (map.hasLayer(marker)) {
                map.removeLayer(marker);
            }

        }

    });

}

// Event Listeners
document.getElementById("cloudFilter")
    .addEventListener("change", applyFilters);

document.getElementById("educationFilter")
    .addEventListener("change", applyFilters);

document.getElementById("healthcareFilter")
    .addEventListener("change", applyFilters);

document.getElementById("transportFilter")
    .addEventListener("change", applyFilters);

// ========================================
// Find Nearest Infrastructure
// ========================================

map.on("click", function(e) {

    const lat = e.latlng.lat;
    const lon = e.latlng.lng;

    fetch(
        `http://127.0.0.1:8000/nearest?lat=${lat}&lon=${lon}`
    )
    .then(response => response.json())
    .then(data => {

        L.popup()
            .setLatLng([lat, lon])
            .setContent(`
                <b>Nearest Infrastructure</b>
                <hr>
                <b>Name:</b> ${data.name}<br>
                <b>Type:</b> ${data.infra_type}<br>
                <b>Distance:</b> ${data.distance_km} km
            `)
            .openOn(map);

    })
    .catch(error => {
        console.error("Nearest Infrastructure Error:", error);
    });

});

// ========================================
// Fix Leaflet Rendering
// ========================================

setTimeout(() => {
    map.invalidateSize();
}, 200);
