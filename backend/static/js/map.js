// FloodGuard Map - Droplet markers, satellite, connection lines, timeline

(function () {
    'use strict';

    var POLL_INTERVAL = 2000;
    var map = null;
    var markers = {};
    var sensorData = [];
    var bounds = null;
    var historyCache = {};
    var historyPending = {};
    var firstLoad = true;

    // Layer references
    var streetLayer = null;
    var satelliteLayer = null;
    var connectionLines = [];
    var isSatellite = false;
    var isLines = false;

    // Current timeline position (100 = live)
    var timelineValue = 100;

    // --- Color helpers ---
    function getMarkerColor(levelCm, status) {
        if (status === 'offline') return '#6c757d';
        if (levelCm >= 70) return '#dc3545';
        if (levelCm >= 50) return '#fd7e14';
        if (levelCm >= 30) return '#ffc107';
        return '#28a745';
    }

    function getMarkerSize(levelCm) {
        if (levelCm >= 70) return 38;
        if (levelCm >= 50) return 34;
        if (levelCm >= 30) return 30;
        return 26;
    }

    function getStatusLabel(status) {
        return status.charAt(0).toUpperCase() + status.slice(1);
    }

    // --- SVG Water Droplet Marker ---
    var dropletIdCounter = 0;
    function createDropletIcon(color, levelCm, isPulse) {
        var size = getMarkerSize(levelCm);
        var uid = 'ds-' + (++dropletIdCounter);
        var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + size + '" height="' + (size + 8) + '" viewBox="0 0 40 48">' +
            '<defs>' +
            '<filter id="' + uid + '" x="-20%" y="-20%" width="140%" height="140%">' +
            '<feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#000" flood-opacity="0.3"/>' +
            '</filter>' +
            '</defs>' +
            '<path d="M20 2 C20 2 4 20 4 30 C4 38.8 11.2 46 20 46 C28.8 46 36 38.8 36 30 C36 20 20 2 20 2Z" ' +
            'fill="' + color + '" stroke="white" stroke-width="2.5" filter="url(#' + uid + ')"/>' +
            '<ellipse cx="14" cy="28" rx="4" ry="5" fill="rgba(255,255,255,0.3)"/>' +
            '</svg>';

        var pulseHtml = '';
        if (isPulse) {
            pulseHtml = '<div class="droplet-pulse" style="width:' + (size + 20) + 'px;height:' + (size + 20) + 'px;border-color:' + color + ';"></div>';
        }

        return L.divIcon({
            className: 'droplet-marker-wrap',
            html: pulseHtml +
                '<div class="droplet-marker" style="width:' + size + 'px;">' + svg +
                '<div class="droplet-level">' + levelCm + 'cm</div></div>',
            iconSize: [size, size + 8],
            iconAnchor: [size / 2, size + 8],
            popupAnchor: [0, -(size + 4)]
        });
    }

    // --- Popup ---
    function buildPopup(sensor) {
        var color = getMarkerColor(sensor.level_cm, sensor.status);
        var pct = Math.min((sensor.level_cm / 100) * 100, 100);
        return '<div class="map-popup">' +
            '<div class="popup-header" style="border-left:4px solid ' + color + ';">' +
            '<h3>' + sensor.name + '</h3>' +
            '<span class="popup-badge" style="background:' + color + ';">' + getStatusLabel(sensor.status) + '</span>' +
            '</div>' +
            '<div class="popup-body">' +
            '<p><strong>Location:</strong> ' + sensor.location + '</p>' +
            '<div class="popup-level-bar"><div class="popup-level-fill" style="width:' + pct + '%;background:' + color + ';"></div></div>' +
            '<p><strong>Water Level:</strong> <span style="color:' + color + ';font-weight:700;">' + sensor.level_cm + ' cm</span></p>' +
            '<p><strong>Device:</strong> ' + sensor.device_id + '</p>' +
            (sensor.last_seen ? '<p><strong>Last Seen:</strong> ' + new Date(sensor.last_seen).toLocaleString() + '</p>' : '') +
            '</div>' +
            '</div>';
    }

    // --- Map init ---
    function initMap() {
        map = L.map('sensor-map', { zoomControl: false }).setView([21.12, 79.10], 13);

        L.control.zoom({ position: 'topright' }).addTo(map);

        streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 19
        });

        satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: '&copy; Esri',
            maxZoom: 19
        });

        streetLayer.addTo(map);

        // Event listeners
        var recenterBtn = document.getElementById('recenter-btn');
        var sidebarToggle = document.getElementById('sidebar-toggle');
        var satelliteToggle = document.getElementById('satellite-toggle');
        var linesToggle = document.getElementById('lines-toggle');
        var timelineSlider = document.getElementById('timeline-slider');
        if (recenterBtn) recenterBtn.addEventListener('click', recenterMap);
        if (sidebarToggle) sidebarToggle.addEventListener('click', toggleSidebar);
        if (satelliteToggle) satelliteToggle.addEventListener('click', toggleSatellite);
        if (linesToggle) linesToggle.addEventListener('click', toggleLines);
        if (timelineSlider) timelineSlider.addEventListener('input', onTimelineChange);

        pollSensorStatus();
        setInterval(pollSensorStatus, POLL_INTERVAL);
    }

    // --- Controls ---
    function recenterMap() {
        if (bounds && bounds.isValid()) {
            map.fitBounds(bounds, { padding: [60, 60], maxZoom: 15 });
        }
    }

    function toggleSidebar() {
        var sidebar = document.getElementById('map-sidebar');
        if (sidebar) sidebar.classList.toggle('collapsed');
        setTimeout(function () { map.invalidateSize(); }, 350);
    }

    function toggleSatellite() {
        isSatellite = !isSatellite;
        var btn = document.getElementById('satellite-toggle');
        if (isSatellite) {
            map.removeLayer(streetLayer);
            satelliteLayer.addTo(map);
            btn.classList.add('active');
        } else {
            map.removeLayer(satelliteLayer);
            streetLayer.addTo(map);
            btn.classList.remove('active');
        }
    }

    function toggleLines() {
        isLines = !isLines;
        var btn = document.getElementById('lines-toggle');
        if (isLines) {
            drawConnectionLines();
            btn.classList.add('active');
        } else {
            clearConnectionLines();
            btn.classList.remove('active');
        }
    }

    // --- Connection Lines ---
    function drawConnectionLines() {
        clearConnectionLines();
        var coords = [];
        sensorData.forEach(function (s) {
            if (s.latitude && s.longitude) {
                coords.push({ lat: s.latitude, lng: s.longitude, level: s.level_cm });
            }
        });
        if (coords.length < 2) return;

        for (var i = 0; i < coords.length - 1; i++) {
            var avgLevel = (coords[i].level + coords[i + 1].level) / 2;
            var lineColor = getMarkerColor(avgLevel, 'active');
            var line = L.polyline(
                [[coords[i].lat, coords[i].lng], [coords[i + 1].lat, coords[i + 1].lng]],
                { color: lineColor, weight: 3, opacity: 0.7, dashArray: '8, 8', className: 'connection-line' }
            ).addTo(map);
            connectionLines.push(line);
        }
    }

    function clearConnectionLines() {
        connectionLines.forEach(function (line) { map.removeLayer(line); });
        connectionLines = [];
    }

    // --- Timeline ---
    function onTimelineChange() {
        var val = parseInt(document.getElementById('timeline-slider').value);
        timelineValue = val;
        var label = document.getElementById('timeline-label');

        if (val >= 100) {
            label.textContent = 'Live';
            applyLiveValues();
            return;
        }

        var hoursAgo = 24 - (val / 100) * 24;
        var targetTime = new Date(Date.now() - hoursAgo * 3600000);
        label.textContent = formatTimeAgo(targetTime);

        sensorData.forEach(function (sensor) {
            var history = historyCache[sensor.device_id];
            if (!history || history.length === 0) return;

            var closest = history[0];
            var minDiff = Math.abs(new Date(closest.timestamp) - targetTime);
            for (var i = 1; i < history.length; i++) {
                var diff = Math.abs(new Date(history[i].timestamp) - targetTime);
                if (diff < minDiff) { minDiff = diff; closest = history[i]; }
            }

            if (markers[sensor.device_id]) {
                var color = getMarkerColor(closest.level_cm, sensor.status);
                var icon = createDropletIcon(color, closest.level_cm, false);
                markers[sensor.device_id].setIcon(icon);
            }
        });
    }

    function applyLiveValues() {
        sensorData.forEach(function (sensor) {
            if (markers[sensor.device_id]) {
                var color = getMarkerColor(sensor.level_cm, sensor.status);
                var isPulse = sensor.status === 'rising' && sensor.level_cm >= 70;
                var icon = createDropletIcon(color, sensor.level_cm, isPulse);
                markers[sensor.device_id].setIcon(icon);
            }
        });
    }

    function formatTimeAgo(date) {
        var diff = Date.now() - date.getTime();
        var mins = Math.floor(diff / 60000);
        if (mins < 60) return mins + 'm ago';
        var hrs = Math.floor(mins / 60);
        var remMins = mins % 60;
        return hrs + 'h ' + remMins + 'm ago';
    }

    function fetchHistory(deviceId) {
        if (historyCache[deviceId] || historyPending[deviceId]) return Promise.resolve();
        historyPending[deviceId] = true;
        return fetch('/api/sensor-history/' + deviceId + '/?_=' + Date.now(), { cache: 'no-store' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                historyCache[deviceId] = data.history || [];
                historyPending[deviceId] = false;
            })
            .catch(function () {
                historyPending[deviceId] = false;
            });
    }

    function fetchAllHistory() {
        var promises = sensorData.map(function (s) { return fetchHistory(s.device_id); });
        Promise.all(promises).then(function () {
            if (timelineValue < 100) onTimelineChange();
        });
    }

    // --- Polling ---
    function pollSensorStatus() {
        fetch('/api/sensor-status/?_=' + Date.now(), { cache: 'no-store' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.sensors) return;
                sensorData = data.sensors;
                updateMarkers(data.sensors);
                updateSidebar(data.sensors);
                if (isLines) drawConnectionLines();
                if (timelineValue >= 100) applyLiveValues();
                fetchAllHistory();
            })
            .catch(function (err) { console.error('Map poll error:', err); });
    }

    // --- Markers ---
    function updateMarkers(sensors) {
        var validIds = [];

        sensors.forEach(function (sensor) {
            if (sensor.latitude == null || sensor.longitude == null) return;
            validIds.push(sensor.device_id);

            var color = getMarkerColor(sensor.level_cm, sensor.status);
            var isPulse = sensor.status === 'rising' && sensor.level_cm >= 70;
            var icon = createDropletIcon(color, sensor.level_cm, isPulse);
            var popupHtml = buildPopup(sensor);

            if (markers[sensor.device_id]) {
                markers[sensor.device_id].setIcon(icon);
                markers[sensor.device_id].setPopupContent(popupHtml);
            } else {
                var marker = L.marker([sensor.latitude, sensor.longitude], { icon: icon })
                    .addTo(map)
                    .bindPopup(popupHtml, { maxWidth: 300, className: 'flood-popup' });

                marker.on('click', function () {
                    map.setView([sensor.latitude, sensor.longitude], Math.max(map.getZoom(), 15));
                });

                markers[sensor.device_id] = marker;
            }
        });

        Object.keys(markers).forEach(function (id) {
            if (validIds.indexOf(id) === -1) {
                map.removeLayer(markers[id]);
                delete markers[id];
            }
        });

        // Only fit bounds on first load
        if (firstLoad && validIds.length > 0) {
            bounds = L.latLngBounds();
            sensors.forEach(function (s) {
                if (s.latitude && s.longitude) bounds.extend([s.latitude, s.longitude]);
            });
            if (bounds.isValid()) {
                map.fitBounds(bounds, { padding: [60, 60], maxZoom: 15 });
            }
            firstLoad = false;
        }
    }

    // --- Sidebar ---
    function updateSidebar(sensors) {
        var container = document.getElementById('sidebar-sensors');
        if (!container) return;

        var html = '';
        sensors.forEach(function (sensor) {
            var color = getMarkerColor(sensor.level_cm, sensor.status);
            var isActive = sensor.status !== 'offline';
            var pct = Math.min((sensor.level_cm / 100) * 100, 100);

            html += '<div class="sidebar-sensor" data-device="' + sensor.device_id + '">' +
                '<div class="sidebar-sensor-top">' +
                '<div class="sidebar-droplet-mini" style="background:' + color + ';"></div>' +
                '<div class="sidebar-sensor-info">' +
                '<div class="sidebar-sensor-name">' + sensor.name + '</div>' +
                '<div class="sidebar-sensor-location">' + sensor.location + '</div>' +
                '</div>' +
                '<span class="sidebar-sensor-status ' + (isActive ? 'active' : 'inactive') + '">' + getStatusLabel(sensor.status) + '</span>' +
                '</div>' +
                '<div class="sidebar-level-bar"><div class="sidebar-level-fill" style="width:' + pct + '%;background:' + color + ';"></div></div>' +
                '<div class="sidebar-sensor-level">' + sensor.level_cm + ' cm</div>' +
                '</div>';
        });

        if (!html) html = '<p class="no-data">No sensors found</p>';
        container.innerHTML = html;

        container.querySelectorAll('.sidebar-sensor').forEach(function (el) {
            el.addEventListener('click', function () {
                var deviceId = this.getAttribute('data-device');
                var sensor = sensors.find(function (s) { return s.device_id === deviceId; });
                if (sensor && sensor.latitude && sensor.longitude) {
                    map.setView([sensor.latitude, sensor.longitude], 16);
                    if (markers[deviceId]) markers[deviceId].openPopup();
                    container.querySelectorAll('.sidebar-sensor').forEach(function (s) { s.classList.remove('selected'); });
                    this.classList.add('selected');
                }
            });
        });
    }

    // --- Init ---
    document.addEventListener('DOMContentLoaded', function () {
        initMap();
    });
})();
