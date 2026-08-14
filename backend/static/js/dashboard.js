// FloodGuard Dashboard JavaScript - Real-time polling with status change detection

(function() {
    var POLL_INTERVAL = 2000;
    var TOAST_DURATION = 5000;
    var previousStatus = {};
    var audioCtx = null;

    function initAudio() {
        if (!audioCtx) {
            try {
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            } catch(e) {}
        }
        if (audioCtx && audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
    }

    function playBeep(freq, duration) {
        if (!audioCtx) return;
        try {
            var osc = audioCtx.createOscillator();
            var gain = audioCtx.createGain();
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.frequency.value = freq;
            osc.type = 'sine';
            gain.gain.value = 0.3;
            osc.start();
            gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
            osc.stop(audioCtx.currentTime + duration);
        } catch(e) {}
    }

    function playOfflineAlert() {
        initAudio();
        playBeep(800, 0.3);
        setTimeout(function() { playBeep(800, 0.3); }, 400);
        setTimeout(function() { playBeep(600, 0.5); }, 800);
    }

    function playReconnectAlert() {
        initAudio();
        playBeep(523, 0.2);
        setTimeout(function() { playBeep(659, 0.2); }, 200);
        setTimeout(function() { playBeep(784, 0.3); }, 400);
    }

    function getToastContainer() {
        var container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    function showToast(type, title, message) {
        var container = getToastContainer();
        var toast = document.createElement('div');
        toast.className = 'toast toast-' + type;

        var icon = type === 'offline' ? '&#9888;' : '&#10003;';

        toast.innerHTML = '<span class="toast-icon">' + icon + '</span>' +
            '<div class="toast-content">' +
            '<div class="toast-title">' + title + '</div>' +
            '<div class="toast-message">' + message + '</div>' +
            '</div>' +
            '<button class="toast-close">&times;</button>';

        var closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', function() {
            removeToast(toast);
        });

        container.appendChild(toast);

        setTimeout(function() {
            removeToast(toast);
        }, TOAST_DURATION);

        return toast;
    }

    function removeToast(toast) {
        if (toast.classList.contains('removing')) return;
        toast.classList.add('removing');
        setTimeout(function() {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }

    function showOfflineModal(sensors) {
        var popup = document.getElementById('offline-popup');
        var popupBody = document.getElementById('offline-popup-body');
        var dismissBtn = document.getElementById('offline-popup-dismiss');

        if (!popup || !popupBody || !dismissBtn) return;

        var html = '<p>The following sensors are no longer sending data:</p><ul>';
        sensors.forEach(function(s) {
            html += '<li><strong>' + s.name + '</strong> (' + s.location + ')</li>';
        });
        html += '</ul>';
        popupBody.innerHTML = html;
        popup.classList.remove('hidden');

        var dismissed = [];
        try { dismissed = JSON.parse(localStorage.getItem('fg_dismissed') || '[]'); } catch(e) {}

        dismissBtn.onclick = function() {
            popup.classList.add('hidden');
            sensors.forEach(function(s) {
                if (dismissed.indexOf(s.name) === -1) {
                    dismissed.push(s.name);
                }
            });
            localStorage.setItem('fg_dismissed', JSON.stringify(dismissed));
        };

        var onlineNames = [];
        Object.keys(previousStatus).forEach(function(id) {
            if (previousStatus[id].status !== 'offline') {
                onlineNames.push(previousStatus[id].name);
            }
        });
        dismissed = dismissed.filter(function(n) { return onlineNames.indexOf(n) < 0; });
        localStorage.setItem('fg_dismissed', JSON.stringify(dismissed));
    }

    function pollSensorStatus() {
        fetch('/api/sensor-status/?_=' + Date.now(), {cache: 'no-store'})
            .then(function(response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(function(data) {
                if (!data.sensors) return;

                var dismissed = [];
                try { dismissed = JSON.parse(localStorage.getItem('fg_dismissed') || '[]'); } catch(e) {}

                var newOfflineSensors = [];

                data.sensors.forEach(function(sensor) {
                    var prev = previousStatus[sensor.device_id];
                    var currentStatus = sensor.status;

                    if (prev) {
                        var prevStatus = prev.status;

                        if (prevStatus !== currentStatus) {
                            var isOffline = (currentStatus === 'offline');
                            var wasOffline = (prevStatus === 'offline');

                            if (isOffline && !wasOffline && dismissed.indexOf(sensor.name) === -1) {
                                playOfflineAlert();
                                showToast('offline', 'Sensor Offline',
                                    sensor.name + ' at ' + sensor.location + ' has stopped sending data');
                                newOfflineSensors.push(sensor);
                            } else if (!isOffline && wasOffline) {
                                playReconnectAlert();
                                showToast('reconnect', 'Sensor Reconnected',
                                    sensor.name + ' at ' + sensor.location + ' is now active');

                                var idx = dismissed.indexOf(sensor.name);
                                if (idx > -1) dismissed.splice(idx, 1);
                                localStorage.setItem('fg_dismissed', JSON.stringify(dismissed));
                            }
                        }
                    }

                    previousStatus[sensor.device_id] = {
                        name: sensor.name,
                        location: sensor.location,
                        status: currentStatus,
                        level_cm: sensor.level_cm
                    };
                });

                if (newOfflineSensors.length > 1) {
                    showOfflineModal(newOfflineSensors);
                }

                updateDashboardDisplay(data.sensors);
            })
            .catch(function(err) {
                console.error('Poll error:', err);
            });
    }

    function updateDashboardDisplay(sensors) {
        sensors.forEach(function(sensor) {
            var readingEl = document.getElementById('reading-' + sensor.device_id);
            if (readingEl) {
                readingEl.textContent = sensor.level_cm + ' cm';
            }

            var cards = document.querySelectorAll('.sensor-card');
            cards.forEach(function(card) {
                var deviceIdEl = card.querySelector('.sensor-id');
                if (deviceIdEl && deviceIdEl.textContent.indexOf(sensor.device_id) > -1) {
                    var statusBadge = card.querySelector('.sensor-status');
                    if (statusBadge) {
                        if (sensor.status === 'offline') {
                            statusBadge.className = 'sensor-status inactive';
                            statusBadge.textContent = 'OFFLINE';
                            card.classList.add('pulse-offline');
                        } else {
                            statusBadge.className = 'sensor-status active';
                            statusBadge.textContent = 'Active';
                            card.classList.remove('pulse-offline');
                        }
                    }

                    var lastSeenEl = card.querySelector('.sensor-last-seen');
                    if (lastSeenEl && sensor.last_seen) {
                        var d = new Date(sensor.last_seen);
                        lastSeenEl.textContent = 'Last seen: ' + d.toLocaleString();
                    }
                }
            });

            var statusCards = document.querySelectorAll('.status-card');
            statusCards.forEach(function(card) {
                var nameEl = card.querySelector('h3');
                if (nameEl && nameEl.textContent === sensor.name) {
                    card.className = 'status-card status-' + sensor.status;

                    var indicator = card.querySelector('.status-indicator');
                    if (indicator) {
                        indicator.className = 'status-indicator ' + sensor.status;
                        indicator.textContent = sensor.status.toUpperCase();
                    }

                    var levelVal = card.querySelector('.level-value');
                    if (levelVal) {
                        levelVal.textContent = sensor.level_cm + ' cm';
                    }
                }
            });
        });

        updateLastUpdateTime();
    }

    function updateLastUpdateTime() {
        var lastUpdate = document.getElementById('last-update');
        if (lastUpdate) {
            lastUpdate.textContent = new Date().toLocaleString();
        }
    }

    function pollDashboardData() {
        fetch('/api/dashboard-data/?_=' + Date.now(), {cache: 'no-store'})
            .then(function(response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(function(data) {
                if (data.readings) {
                    var tbody = document.querySelector('#readings-table tbody');
                    if (tbody) {
                        var html = '';
                        data.readings.forEach(function(r) {
                            var statusHtml = r.is_alert
                                ? '<span class="status-alert">ALERT</span>'
                                : '<span class="status-normal">Normal</span>';
                            html += '<tr>' +
                                '<td>' + r.sensor_name + '</td>' +
                                '<td>' + r.location + '</td>' +
                                '<td>' + r.level_cm + '</td>' +
                                '<td>' + statusHtml + '</td>' +
                                '<td>' + r.timestamp + '</td>' +
                                '</tr>';
                        });
                        if (!html) {
                            html = '<tr><td colspan="5" class="no-data">No readings yet</td></tr>';
                        }
                        tbody.innerHTML = html;
                    }
                }

                if (data.alerts) {
                    var tbody = document.querySelector('#alert-log-table tbody');
                    if (tbody) {
                        var html = '';
                        data.alerts.forEach(function(a) {
                            html += '<tr>' +
                                '<td>' + a.sensor_name + '</td>' +
                                '<td>' + a.location + '</td>' +
                                '<td><span class="alert-badge alert-' + a.alert_type + '">' + a.alert_type.toUpperCase() + '</span></td>' +
                                '<td>' + a.message + '</td>' +
                                '<td>' + a.created_at + '</td>' +
                                '</tr>';
                        });
                        if (!html) {
                            html = '<tr><td colspan="5" class="no-data">No alerts recorded</td></tr>';
                        }
                        tbody.innerHTML = html;
                    }
                }
            })
            .catch(function(err) {
                console.error('Dashboard data poll error:', err);
            });
    }

    document.addEventListener('DOMContentLoaded', function() {
        updateLastUpdateTime();

        var sensorStatusEl = document.getElementById('sensor-status-data');
        if (sensorStatusEl) {
            try {
                var initialData = JSON.parse(sensorStatusEl.textContent);
                initialData.forEach(function(s) {
                    previousStatus[s.device_id] = {
                        name: s.name,
                        location: s.location,
                        status: s.status,
                        level_cm: s.level_cm
                    };
                });
            } catch(e) {}
        }

        setInterval(pollSensorStatus, POLL_INTERVAL);
        setInterval(pollDashboardData, POLL_INTERVAL);
    });
})();
