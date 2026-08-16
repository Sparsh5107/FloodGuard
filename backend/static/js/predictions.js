// predictions.js — Real-time sensor updates, client-side flood probability, what-if simulator
document.addEventListener('DOMContentLoaded', function() {
    const SENSOR_POLL_INTERVAL = 3000;  // 3 seconds for real-time sensor data
    const PREDICTION_POLL_INTERVAL = 300000;  // 5 minutes for full prediction refresh
    let sensorPollTimer = null;
    let predictionPollTimer = null;
    let riskChart = null;
    let currentPredictions = [];
    let ws = null;
    let useWebSocket = false;
    let wsReconnectTimer = null;
    const WS_RECONNECT_DELAY = 3000;
    let _chartRetryAttached = false;

    // ===================== CONNECTION STATUS =====================

    function createWsStatus() {
        const el = document.createElement('div');
        el.id = 'ws-status';
        el.className = 'ws-status connected';
        el.innerHTML = '<span class="ws-status-dot"></span><span class="ws-status-text">Connected</span>';
        document.body.appendChild(el);
    }

    function updateWsStatus(state) {
        const el = document.getElementById('ws-status');
        if (!el) return;
        el.className = 'ws-status ' + state;
        const text = el.querySelector('.ws-status-text');
        if (state === 'connected') text.textContent = 'Connected';
        else if (state === 'reconnecting') text.textContent = 'Reconnecting...';
        else text.textContent = 'Disconnected';
    }

    // ===================== LOADING SPINNER =====================

    function showLoading() {
        const loader = document.getElementById('predictions-loading');
        const statsBar = document.getElementById('pred-stats-bar');
        const grid = document.getElementById('predictions-grid');
        if (loader) {
            loader.style.display = '';
            const hint = loader.querySelector('.loading-hint');
            if (hint) hint.textContent = 'Fetching sensor data and weather forecasts...';
        }
        if (statsBar) statsBar.style.display = 'none';
        if (grid) grid.innerHTML = '';
    }

    function hideLoading() {
        const loader = document.getElementById('predictions-loading');
        if (loader) loader.style.display = 'none';
    }

    // ===================== CLIENT-SIDE FLOOD PROBABILITY =====================

    // Same formula as server: prediction_service.py lines 284-311
    function formatRiseRate(riseRate) {
        if (riseRate > 0.1) {
            return '+' + riseRate.toFixed(2) + ' cm/min';
        } else if (riseRate < -0.1) {
            return riseRate.toFixed(2) + ' cm/min';
        } else {
            return 'Stable';
        }
    }

    function getRiseRateClass(riseRate) {
        if (riseRate > 3) return 'rise-fast';
        if (riseRate > 1.5) return 'rise-medium';
        if (riseRate > 0.5) return 'rise-slow';
        if (riseRate < -0.5) return 'rise-falling';
        return 'rise-stable';
    }

    function getRiskClass(probability) {
        if (probability >= 85) return 'critical';
        if (probability >= 65) return 'high';
        if (probability >= 40) return 'elevated';
        if (probability >= 20) return 'moderate';
        return 'low';
    }

    function calculateSensorRisk(currentLevel, riseRate) {
        // Base risk from water level
        let baseRisk;
        if (currentLevel >= 70) {
            baseRisk = 90;
        } else if (currentLevel >= 50) {
            baseRisk = 60 + (currentLevel - 50) * 1.5;
        } else if (currentLevel >= 30) {
            baseRisk = 20 + (currentLevel - 30) * 2;
        } else {
            baseRisk = currentLevel * 0.67;
        }

        // Rise rate multiplier
        let rateMultiplier = 1.0;
        if (riseRate > 3) rateMultiplier = 1.5;
        else if (riseRate > 1.5) rateMultiplier = 1.3;
        else if (riseRate > 0.5) rateMultiplier = 1.1;
        else if (riseRate < -0.5) rateMultiplier = 0.8;

        return Math.min(baseRisk * rateMultiplier, 100);
    }

    // Final fusion: 30% weather + 40% sensor + 30% (anomaly + history)
    function calculateFloodProbability(currentLevel, riseRate, weatherRisk) {
        const sensorRisk = calculateSensorRisk(currentLevel, riseRate);

        // Estimate anomaly and history from cached prediction data
        const anomalyRisk = 15;  // default moderate
        const historyRisk = 15;  // default moderate

        const floodProbability = weatherRisk * 0.30 + sensorRisk * 0.40 + anomalyRisk * 0.15 + historyRisk * 0.15;
        return Math.min(Math.max(floodProbability, 0), 100);
    }

    // Calculate time-to-flood from rise rate
    function calculateTimeToFlood(currentLevel, riseRate, threshold) {
        if (riseRate <= 0 || currentLevel >= threshold) return null;
        const distance = threshold - currentLevel;
        const minutes = (distance / riseRate) * 1.2;  // 20% safety margin
        if (minutes <= 60) return '~' + Math.round(minutes) + ' min';
        if (minutes <= 360) {
            const h = Math.floor(minutes / 60);
            const m = Math.round(minutes % 60);
            return '~' + h + 'h ' + m + 'm';
        }
        return null;
    }

    // Get risk level from probability
    function getRiskLevel(probability) {
        if (probability >= 85) return 'CRITICAL';
        if (probability >= 65) return 'HIGH';
        if (probability >= 40) return 'ELEVATED';
        if (probability >= 20) return 'MODERATE';
        return 'LOW';
    }

    // ===================== RENDER PREDICTION CARDS =====================

    function renderPredictionCard(pred) {
        const iconMap = {
            "rain": "&#127783;", "cloud": "&#9729;", "rising": "&#8593;",
            "falling": "&#8595;", "warning": "&#9888;", "target": "&#9679;", "droplet": "&#128167;"
        };

        let anomalyHtml = '';
        if (pred.is_anomaly) {
            anomalyHtml = `<div class="anomaly-banner anomaly-${(pred.anomaly_classification || '').toLowerCase()}">
                <span class="anomaly-icon">&#9888;</span>
                <span class="anomaly-text">${pred.anomaly_description || ''}</span>
            </div>`;
        }

        let explanationHtml = '';
        if (pred.explanation && pred.explanation.factors) {
            let factorsHtml = pred.explanation.factors.map(f => {
                const icon = iconMap[f.icon] || '&#8226;';
                return `<div class="factor-row">
                    <span class="factor-icon">${icon}</span>
                    <span class="factor-text">${f.text}</span>
                    <span class="factor-pct">${f.contribution_pct}%</span>
                </div>`;
            }).join('');
            explanationHtml = `<div class="pred-explanation">
                <div class="explanation-summary">${pred.explanation.summary}</div>
                <div class="explanation-factors">${factorsHtml}</div>
            </div>`;
        } else if (pred.weather_factors) {
            let factorsHtml = pred.weather_factors.map(f =>
                `<li><span class="factor-name">${f.label}</span><span class="factor-value">${f.value}</span></li>`
            ).join('');
            explanationHtml = `<div class="pred-factors"><span class="factors-title">Weather Factors:</span><ul>${factorsHtml}</ul></div>`;
        }

        let warningHtml = '';
        if (pred.data_quality === 'unavailable') {
            warningHtml = '<div class="pred-warning">Weather data unavailable - sensor coordinates missing</div>';
        }

        const modelBadge = pred.ml_used
            ? '<span class="model-badge-ml">ML Model</span>'
            : '<span class="model-badge-rules">Rule-Based</span>';

        const isOffline = pred.status === 'offline' || !pred.latitude || !pred.longitude;
        const cardClass = isOffline ? 'offline' : '';

        return `<div class="prediction-card ${cardClass}" data-device-id="${pred.device_id}" data-weather-risk="${pred.weather_risk}">
            <div class="pred-card-header">
                <div class="pred-card-title">
                    <h3>${pred.name}</h3>
                    <span class="location-tag">${pred.location}</span>
                </div>
                <span class="confidence-badge confidence-${pred.confidence}">${pred.confidence.toUpperCase()}</span>
            </div>
            <div class="pred-card-body">
                <div class="pred-level-row">
                    <div class="pred-level-section">
                        <span class="pred-level-label">Current Level</span>
                        <span class="pred-level-value" id="level-${pred.device_id}">${pred.current_level.toFixed(1)} cm</span>
                        <span class="sensor-status-badge" id="status-${pred.device_id}"></span>
                    </div>
                    <div class="pred-rise-section">
                        <span class="pred-level-label">Rise Rate</span>
                        <span class="pred-rise-value ${getRiseRateClass(pred.rise_rate)}" id="rise-${pred.device_id}">${formatRiseRate(pred.rise_rate)}</span>
                    </div>
                </div>
                ${anomalyHtml}
                <div class="pred-risks">
                    <div class="risk-gauge">
                        <div class="risk-header">
                            <span class="risk-label">Weather Risk</span>
                            <span class="risk-value risk-level-${pred.weather_risk_level.toLowerCase()}">${Math.round(pred.weather_risk)}%</span>
                        </div>
                        <div class="risk-bar-container">
                            <div class="risk-bar weather-bar ${pred.weather_risk >= 30 ? 'risk-pulse' : ''}" style="width: ${pred.weather_risk}%"></div>
                        </div>
                    </div>
                    <div class="risk-gauge">
                        <div class="risk-header">
                            <span class="risk-label">Flood Risk</span>
                            <span class="risk-value risk-level-${getRiskClass(pred.flood_probability)}" id="risk-value-${pred.device_id}">${Math.round(pred.flood_probability)}%</span>
                        </div>
                        <div class="risk-bar-container">
                            <div class="risk-bar flood-bar risk-bg-${getRiskClass(pred.flood_probability)}" id="flood-bar-${pred.device_id}" style="width: ${pred.flood_probability}%"></div>
                        </div>
                    </div>
                </div>
                <div class="pred-time-section">
                    <div class="time-item">
                        <span class="time-label">Time to Warning (30cm)</span>
                        <span class="time-value ${pred.time_to_warning ? 'active' : ''}" id="time-warning-${pred.device_id}">${pred.time_to_warning || '--'}</span>
                    </div>
                    <div class="time-item">
                        <span class="time-label">Time to Critical (70cm)</span>
                        <span class="time-value critical ${pred.time_to_critical ? 'active' : ''}" id="time-critical-${pred.device_id}">${pred.time_to_critical || '--'}</span>
                    </div>
                </div>
                ${explanationHtml}
                ${warningHtml}
                <div class="model-badge">${modelBadge}<span class="model-version">${pred.model_version}</span></div>
            </div>
        </div>`;
    }

    function renderAllPredictions(predictions) {
        const grid = document.getElementById('predictions-grid');
        const noPredictions = document.getElementById('no-predictions');
        const statsBar = document.getElementById('pred-stats-bar');

        if (!predictions.length) {
            grid.innerHTML = '';
            if (noPredictions) { noPredictions.style.display = ''; grid.appendChild(noPredictions); }
            return;
        }

        if (noPredictions) noPredictions.style.display = 'none';
        grid.innerHTML = predictions.map(renderPredictionCard).join('');

        // Show stats bar
        if (statsBar) statsBar.style.display = '';

        // Populate whatif sensor dropdown
        const whatifSelect = document.getElementById('whatif-sensor');
        if (whatifSelect) {
            whatifSelect.innerHTML = predictions.map(p =>
                `<option value="${p.device_id}">${p.name} — ${p.location}</option>`
            ).join('');
        }
    }

    // ===================== REAL-TIME SENSOR UPDATES =====================

    async function pollSensorData() {
        try {
            const resp = await fetch('/api/sensor-status/?_=' + Date.now(), {cache: 'no-store'});
            if (!resp.ok) return;
            const data = await resp.json();
            const sensors = data.sensors || data;  // Handle both formats

            sensors.forEach(sensor => {
                const pred = currentPredictions.find(p => p.device_id === sensor.device_id);
                if (!pred) return;

                const newLevel = sensor.level_cm;

                // Update water level display
                const levelEl = document.getElementById('level-' + sensor.device_id);
                if (levelEl) {
                    const oldLevel = parseFloat(levelEl.textContent);
                    levelEl.textContent = newLevel.toFixed(1) + ' cm';

                    // Flash animation on level change
                    if (Math.abs(newLevel - oldLevel) > 0.1) {
                        levelEl.classList.add('level-flash');
                        setTimeout(() => levelEl.classList.remove('level-flash'), 500);
                    }
                }

                // Update sensor status badge
                const statusEl = document.getElementById('status-' + sensor.device_id);
                if (statusEl) {
                    const statusText = sensor.status || 'stable';
                    statusEl.textContent = statusText;
                    if (statusText === 'offline') {
                        statusEl.className = 'sensor-status-badge status-offline';
                        statusEl.title = 'Sensor is offline - no data received';
                    } else {
                        statusEl.className = 'sensor-status-badge status-' + statusText;
                    }
                }

                // Calculate rise rate from API if available, else derive from status
                let riseRate = pred.rise_rate || 0;
                if (riseRate === 0 && sensor.status === 'rising') riseRate = 1.0;
                else if (riseRate === 0 && sensor.status === 'falling') riseRate = -1.0;

                // Client-side flood probability calculation
                const weatherRisk = pred.weather_risk || 0;
                const floodProbability = calculateFloodProbability(newLevel, riseRate, weatherRisk);
                const riskLevel = getRiskLevel(floodProbability);

                // Update flood probability display
                const riskValueEl = document.getElementById('risk-value-' + sensor.device_id);
                if (riskValueEl) {
                    riskValueEl.textContent = Math.round(floodProbability) + '%';
                    riskValueEl.className = 'risk-value risk-level-' + riskLevel.toLowerCase();
                }

                // Update flood risk bar
                const floodBarEl = document.getElementById('flood-bar-' + sensor.device_id);
                if (floodBarEl) {
                    floodBarEl.style.width = floodProbability + '%';
                    floodBarEl.className = 'risk-bar flood-bar risk-bg-' + riskLevel.toLowerCase();

                    // Add pulse animation for high risk
                    if (floodProbability >= 65) {
                        floodBarEl.classList.add('risk-pulse');
                    } else {
                        floodBarEl.classList.remove('risk-pulse');
                    }
                }

                // Pulse weather risk bar when weather risk is high
                const cardEl2 = document.querySelector('.prediction-card[data-device-id="' + sensor.device_id + '"]');
                if (cardEl2) {
                    const weatherBarEl = cardEl2.querySelector('.risk-bar.weather-bar');
                    if (weatherBarEl) {
                        if (weatherRisk >= 30) {
                            weatherBarEl.classList.add('risk-pulse');
                        } else {
                            weatherBarEl.classList.remove('risk-pulse');
                        }
                    }
                }

                // Pulse rise rate when rising fast
                const riseEl = document.getElementById('rise-' + sensor.device_id);
                if (riseEl) {
                    riseEl.classList.remove('rise-fast', 'rise-medium', 'rise-slow', 'rise-falling', 'rise-stable');
                    if (sensor.status === 'rising') {
                        if (riseRate > 3) riseEl.classList.add('rise-fast');
                        else if (riseRate > 1.5) riseEl.classList.add('rise-medium');
                        else riseEl.classList.add('rise-slow');
                    } else if (sensor.status === 'falling') {
                        riseEl.classList.add('rise-falling');
                    } else {
                        riseEl.classList.add('rise-stable');
                    }
                }

                // Update time-to-flood estimates
                const timeWarningEl = document.getElementById('time-warning-' + sensor.device_id);
                if (timeWarningEl) {
                    const timeToWarning = calculateTimeToFlood(newLevel, riseRate, 30);
                    timeWarningEl.textContent = timeToWarning || '--';
                    timeWarningEl.className = 'time-value' + (timeToWarning ? ' active' : '');
                }

                const timeCriticalEl = document.getElementById('time-critical-' + sensor.device_id);
                if (timeCriticalEl) {
                    const timeToCritical = calculateTimeToFlood(newLevel, riseRate, 70);
                    timeCriticalEl.textContent = timeToCritical || '--';
                    timeCriticalEl.className = 'time-value critical' + (timeToCritical ? ' active' : '');
                }

                // Update currentPredictions with real-time values
                pred.current_level = newLevel;
                pred.flood_probability = floodProbability;
                pred.flood_risk_level = riskLevel;
                pred.rise_rate = riseRate;

                // Toggle offline class on prediction card
                const cardEl = document.querySelector('.prediction-card[data-device-id="' + sensor.device_id + '"]');
                if (cardEl) {
                    if (sensor.status === 'offline') {
                        cardEl.classList.add('offline');
                    } else {
                        cardEl.classList.remove('offline');
                    }
                }

            });

            // Update the risk chart with real-time data
            updateRiskChart();

            // Update stats with current predictions
            updateStats(currentPredictions);

            // Update timestamp
            updateTimestamp();

        } catch (e) {
            console.warn('Sensor poll failed:', e);
        }
    }

    // ===================== STATS & CARDS =====================

    function updateTimestamp() {
        const el = document.getElementById('last-updated');
        if (el) el.textContent = new Date().toLocaleTimeString();
    }

    function updateStats(predictions) {
        if (!predictions.length) return;
        const avgWeather = predictions.reduce((s, p) => s + p.weather_risk, 0) / predictions.length;
        const avgFlood = predictions.reduce((s, p) => s + p.flood_probability, 0) / predictions.length;

        const weatherEl = document.getElementById('avg-weather-risk');
        const floodEl = document.getElementById('avg-flood-risk');
        const countEl = document.getElementById('sensor-count');

        if (weatherEl) weatherEl.textContent = Math.round(avgWeather) + '%';
        if (floodEl) floodEl.textContent = Math.round(avgFlood) + '%';
        if (countEl) countEl.textContent = predictions.length;
    }

    // ===================== RISK HISTORY CHART =====================

    let _chartPendingPredictions = null;

    function initRiskChart(predictions) {
        const ctx = document.getElementById('riskHistoryChart');
        if (!ctx || typeof Chart === 'undefined') {
            _chartPendingPredictions = predictions;
            if (!_chartRetryAttached) {
                _chartRetryAttached = true;
                document.addEventListener('DOMContentLoaded', function() {
                    function tryRetry() {
                        if (typeof Chart !== 'undefined' && _chartPendingPredictions) {
                            initRiskChart(_chartPendingPredictions);
                            _chartPendingPredictions = null;
                        } else if (typeof Chart === 'undefined') {
                            setTimeout(tryRetry, 500);
                        }
                    }
                    tryRetry();
                });
            }
            return;
        }

        const labels = predictions.map(p => p.name);
        const weatherData = predictions.map(p => p.weather_risk);
        const floodData = predictions.map(p => p.flood_probability);
        const levelData = predictions.map(p => p.current_level);

        if (riskChart) {
            riskChart.data.labels = labels;
            riskChart.data.datasets[0].data = weatherData;
            riskChart.data.datasets[1].data = floodData;
            riskChart.data.datasets[2].data = levelData;
            riskChart.update();
            return;
        }

        riskChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Weather Risk %',
                        data: weatherData,
                        backgroundColor: 'rgba(54, 162, 235, 0.7)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1,
                        yAxisID: 'y',
                    },
                    {
                        label: 'Flood Risk %',
                        data: floodData,
                        backgroundColor: 'rgba(255, 99, 132, 0.7)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1,
                        yAxisID: 'y',
                    },
                    {
                        label: 'Water Level (cm)',
                        data: levelData,
                        backgroundColor: 'rgba(75, 192, 192, 0.7)',
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 1,
                        yAxisID: 'y1',
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { position: 'top' },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.dataset.label + ': ' + context.parsed.y;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        type: 'linear', display: true, position: 'left',
                        title: { display: true, text: 'Risk %' },
                        min: 0, max: 100,
                    },
                    y1: {
                        type: 'linear', display: true, position: 'right',
                        title: { display: true, text: 'Water Level (cm)' },
                        min: 0, max: 100,
                        grid: { drawOnChartArea: false },
                    }
                }
            }
        });
    }

    function updateRiskChart() {
        if (!riskChart || !currentPredictions.length) return;

        // Update chart datasets with real-time data
        riskChart.data.labels = currentPredictions.map(p => p.name);
        riskChart.data.datasets[0].data = currentPredictions.map(p => p.weather_risk);
        riskChart.data.datasets[1].data = currentPredictions.map(p => p.flood_probability);
        riskChart.data.datasets[2].data = currentPredictions.map(p => p.current_level);

        // Use 'none' animation for fast updates
        riskChart.update('none');
    }

    // ===================== WHAT-IF SIMULATOR =====================

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function initWhatIf() {
        const rainfallSlider = document.getElementById('whatif-rainfall');
        const durationSlider = document.getElementById('whatif-duration');
        const rainfallValue = document.getElementById('rainfall-value');
        const durationValue = document.getElementById('duration-value');
        const runBtn = document.getElementById('whatif-run');

        if (!rainfallSlider || !durationSlider || !runBtn) return;

        rainfallSlider.addEventListener('input', function() {
            rainfallValue.textContent = this.value;
        });

        durationSlider.addEventListener('input', function() {
            durationValue.textContent = this.value;
        });

        runBtn.addEventListener('click', runWhatIf);
    }

    async function runWhatIf() {
        const deviceId = document.getElementById('whatif-sensor').value;
        const rainfall = document.getElementById('whatif-rainfall').value;
        const duration = document.getElementById('whatif-duration').value;
        const soilType = document.getElementById('whatif-soil').value;
        const landUse = document.getElementById('whatif-land').value;
        const runBtn = document.getElementById('whatif-run');
        const resultsDiv = document.getElementById('whatif-results');

        if (!deviceId) {
            const resultsDiv = document.getElementById('whatif-results');
            resultsDiv.style.display = '';
            document.getElementById('whatif-analysis').innerHTML = '<div class="whatif-analysis-desc" style="color:#f44336;">&#9888; No sensor selected. Load predictions first, then select a sensor from the dropdown.</div>';
            return;
        }

        const csrfToken = getCookie('csrftoken');
        if (!csrfToken) {
            console.error('CSRF token not found — refresh the page to load it.');
            alert('Security token missing. Please refresh the page and try again.');
            return;
        }

        runBtn.textContent = 'Simulating...';
        runBtn.disabled = true;

        try {
            const resp = await fetch('/api/predictions/whatif/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({
                    device_id: deviceId,
                    rainfall_mm: parseFloat(rainfall),
                    duration_hours: parseFloat(duration),
                    soil_type: soilType,
                    land_use: landUse,
                })
            });

            if (!resp.ok) throw new Error('Simulation failed: ' + resp.status);
            const data = await resp.json();

            resultsDiv.style.display = '';

            const analysisEl = document.getElementById('whatif-analysis');
            const cnColor = data.cn >= 85 ? '#f44336' : data.cn >= 70 ? '#FF9800' : data.cn >= 50 ? '#FFC107' : '#4CAF50';
            analysisEl.innerHTML = `
                <div class="whatif-analysis-row">
                    <span class="whatif-analysis-label">Method:</span>
                    <span class="whatif-analysis-value">SCS Curve Number (FEMA/USDA standard)</span>
                </div>
                <div class="whatif-analysis-row">
                    <span class="whatif-analysis-label">Curve Number (CN):</span>
                    <span class="whatif-analysis-value" style="color:${cnColor}">${data.cn} — ${data.soil_desc} / ${data.land_desc}</span>
                </div>
                <div class="whatif-analysis-row">
                    <span class="whatif-analysis-label">Rainfall Intensity:</span>
                    <span class="whatif-analysis-value">${data.intensity} mm/hr — ${data.intensity_class}</span>
                </div>
                <div class="whatif-analysis-row">
                    <span class="whatif-analysis-label">Initial Abstraction:</span>
                    <span class="whatif-analysis-value">${data.initial_abstraction} mm (water absorbed before runoff starts)</span>
                </div>
                <div class="whatif-analysis-desc">CN = ${data.cn}: ${data.rainfall_mm}mm rainfall → ${data.runoff_mm}mm runoff (${data.runoff_pct}%)</div>
            `;

            document.getElementById('whatif-current').textContent = data.current_level + ' cm';
            document.getElementById('whatif-projected').textContent = data.projected_level + ' cm';
            document.getElementById('whatif-rise').textContent = '+' + data.rise_cm + ' cm';
            document.getElementById('whatif-runoff').textContent = data.runoff_mm + ' mm (' + data.runoff_pct + '%)';

            const riskEl = document.getElementById('whatif-risk');
            riskEl.textContent = data.flood_risk + '% - ' + data.risk_level;
            riskEl.className = 'whatif-result-value risk-level-' + data.risk_level.toLowerCase();

            document.getElementById('whatif-time').textContent = data.time_to_critical || 'N/A';

            const warningsDiv = document.getElementById('whatif-warnings');
            warningsDiv.innerHTML = '';
            if (data.would_exceed_critical) {
                warningsDiv.innerHTML += '<div class="whatif-warning critical">&#9888; Would exceed CRITICAL threshold (70cm) — flooding likely!</div>';
            } else if (data.would_exceed_warning) {
                warningsDiv.innerHTML += '<div class="whatif-warning warning">&#9888; Would exceed WARNING threshold (30cm) — monitor closely</div>';
            } else if (data.runoff_pct === 0) {
                warningsDiv.innerHTML += '<div class="whatif-warning safe">&#10003; All rainfall absorbed by soil — no runoff expected</div>';
            } else if (data.runoff_pct < 30) {
                warningsDiv.innerHTML += '<div class="whatif-warning safe">&#10003; Low runoff — soil absorbs most rainfall</div>';
            } else if (data.runoff_pct < 60) {
                warningsDiv.innerHTML += '<div class="whatif-warning warning">&#9888; Moderate runoff — minor ponding possible</div>';
            } else {
                warningsDiv.innerHTML += `<div class="whatif-warning critical">&#9888; High runoff — ${data.runoff_pct}% of rainfall becomes surface water</div>`;
            }

        } catch (e) {
            console.error('What-if error:', e);
            resultsDiv.style.display = 'none';
            alert('Simulation failed: ' + e.message);
        } finally {
            runBtn.textContent = 'Run Simulation';
            runBtn.disabled = false;
        }
    }

    // ===================== FETCH PREDICTIONS (ASYNC) =====================

    async function fetchPredictions() {
        try {
            const resp = await fetch('/api/predictions/');
            if (!resp.ok) throw new Error('Failed to fetch predictions');
            const data = await resp.json();

            currentPredictions = data.predictions;
            hideLoading();
            renderAllPredictions(data.predictions);
            updateStats(data.predictions);
            initRiskChart(data.predictions);
            updateTimestamp();

            // Start real-time sensor polling after predictions load
            startSensorPolling();

        } catch (e) {
            console.error('Failed to load predictions:', e);
            hideLoading();
            const grid = document.getElementById('predictions-grid');
            if (grid) {
                grid.innerHTML = '<div class="no-predictions" style="padding:40px;text-align:center;"><p style="color:#f44336;font-size:1.1rem;">&#9888; Failed to load predictions</p><p style="color:#666;">' + e.message + '</p><button onclick="location.reload()" style="margin-top:12px;padding:8px 20px;border:none;border-radius:6px;background:#667eea;color:#fff;cursor:pointer;font-size:0.95rem;">Retry</button></div>';
            }
            const whatifSelect = document.getElementById('whatif-sensor');
            if (whatifSelect) {
                whatifSelect.innerHTML = '<option value="">No sensors available — predictions failed to load</option>';
            }
        }
    }

    async function pollPredictions() {
        try {
            const resp = await fetch('/api/predictions/');
            if (!resp.ok) return;
            const data = await resp.json();
            currentPredictions = data.predictions;
            renderAllPredictions(data.predictions);
            updateStats(data.predictions);
            initRiskChart(data.predictions);
            updateTimestamp();
        } catch (e) {
            console.warn('Prediction poll failed:', e);
        }
    }

    // ===================== REAL-TIME SENSOR POLLING =====================

    function startSensorPolling() {
        // Try WebSocket first for real-time sensor updates
        connectWebSocket();

        // Always poll full predictions every 5 minutes for weather/ML updates
        predictionPollTimer = setInterval(pollPredictions, PREDICTION_POLL_INTERVAL);

        // Initial sensor poll
        pollSensorData();

        // Fallback to HTTP polling if WebSocket doesn't connect in 5 seconds
        setTimeout(function() {
            if (!useWebSocket) {
                console.log('WebSocket not available, falling back to polling');
                sensorPollTimer = setInterval(pollSensorData, SENSOR_POLL_INTERVAL);
            }
        }, 5000);
    }

    // ===================== WEBSOCKET =====================

    function connectWebSocket() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = protocol + '//' + location.host + '/ws/sensors/';

        try {
            ws = new WebSocket(wsUrl);
        } catch(e) {
            console.error('WebSocket construction failed:', e);
            useWebSocket = false;
            if (!sensorPollTimer) {
                sensorPollTimer = setInterval(pollSensorData, SENSOR_POLL_INTERVAL);
            }
            return;
        }

        ws.onopen = function() {
            useWebSocket = true;
            if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
            updateWsStatus('connected');
            console.log('WebSocket connected (predictions)');
        };

        ws.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'sensor_update') {
                    handleWsSensorUpdate(data);
                }
            } catch(e) {
                console.error('WS parse error:', e);
            }
        };

        ws.onclose = function() {
            useWebSocket = false;
            updateWsStatus('reconnecting');
            console.log('WebSocket closed (predictions), retrying...');
            // Start polling as fallback
            if (!sensorPollTimer) {
                sensorPollTimer = setInterval(pollSensorData, SENSOR_POLL_INTERVAL);
            }
            wsReconnectTimer = setTimeout(connectWebSocket, WS_RECONNECT_DELAY);
        };

        ws.onerror = function() {
            useWebSocket = false;
            updateWsStatus('disconnected');
            if (!sensorPollTimer) {
                sensorPollTimer = setInterval(pollSensorData, SENSOR_POLL_INTERVAL);
            }
            ws.close();
        };
    }

    function handleWsSensorUpdate(data) {
        const pred = currentPredictions.find(p => p.device_id === data.device_id);
        if (!pred) return;

        // Update currentPredictions with real-time values
        pred.current_level = data.level_cm;

        // Update water level display
        const levelEl = document.getElementById('level-' + data.device_id);
        if (levelEl) {
            const oldLevel = parseFloat(levelEl.textContent);
            levelEl.textContent = data.level_cm.toFixed(1) + ' cm';
            if (Math.abs(data.level_cm - oldLevel) > 0.1) {
                levelEl.classList.add('level-flash');
                setTimeout(() => levelEl.classList.remove('level-flash'), 500);
            }
        }

        // Update sensor status badge
        const statusEl = document.getElementById('status-' + data.device_id);
        if (statusEl) {
            const statusText = data.status || 'stable';
            statusEl.textContent = statusText;
            if (statusText === 'offline') {
                statusEl.className = 'sensor-status-badge status-offline';
                statusEl.title = 'Sensor is offline - no data received';
            } else {
                statusEl.className = 'sensor-status-badge status-' + statusText;
            }
        }

        // Toggle offline class on prediction card
        const cardEl = document.querySelector('.prediction-card[data-device-id="' + data.device_id + '"]');
        if (cardEl) {
            if (data.status === 'offline') {
                cardEl.classList.add('offline');
            } else {
                cardEl.classList.remove('offline');
            }
        }

        // Calculate rise rate from API if available, else derive from status
        let riseRate = pred.rise_rate || 0;
        if (riseRate === 0 && data.status === 'rising') riseRate = 1.0;
        else if (riseRate === 0 && data.status === 'falling') riseRate = -1.0;

        // Client-side flood probability
        const weatherRisk = pred.weather_risk || 0;
        const floodProbability = calculateFloodProbability(data.level_cm, riseRate, weatherRisk);
        const riskLevel = getRiskLevel(floodProbability);

        pred.flood_probability = floodProbability;
        pred.flood_risk_level = riskLevel;
        pred.rise_rate = riseRate;

        // Update flood probability display
        const riskValueEl = document.getElementById('risk-value-' + data.device_id);
        if (riskValueEl) {
            riskValueEl.textContent = Math.round(floodProbability) + '%';
            riskValueEl.className = 'risk-value risk-level-' + riskLevel.toLowerCase();
        }

        // Update flood risk bar
        const floodBarEl = document.getElementById('flood-bar-' + data.device_id);
        if (floodBarEl) {
            floodBarEl.style.width = floodProbability + '%';
            floodBarEl.className = 'risk-bar flood-bar risk-bg-' + riskLevel.toLowerCase();
            if (floodProbability >= 65) {
                floodBarEl.classList.add('risk-pulse');
            } else {
                floodBarEl.classList.remove('risk-pulse');
            }
        }

        // Pulse weather risk bar when weather risk is high
        const cardEl3 = document.querySelector('.prediction-card[data-device-id="' + data.device_id + '"]');
        if (cardEl3) {
            const weatherBarEl = cardEl3.querySelector('.risk-bar.weather-bar');
            if (weatherBarEl) {
                if (weatherRisk >= 30) {
                    weatherBarEl.classList.add('risk-pulse');
                } else {
                    weatherBarEl.classList.remove('risk-pulse');
                }
            }
        }

        // Pulse rise rate when rising fast
        const riseEl = document.getElementById('rise-' + data.device_id);
        if (riseEl) {
            riseEl.textContent = formatRiseRate(riseRate);
            riseEl.classList.remove('rise-fast', 'rise-medium', 'rise-slow', 'rise-falling', 'rise-stable');
            if (data.status === 'rising') {
                if (riseRate > 3) riseEl.classList.add('rise-fast');
                else if (riseRate > 1.5) riseEl.classList.add('rise-medium');
                else riseEl.classList.add('rise-slow');
            } else if (data.status === 'falling') {
                riseEl.classList.add('rise-falling');
            } else {
                riseEl.classList.add('rise-stable');
            }
        }

        // Update time-to-flood estimates
        const timeWarningEl = document.getElementById('time-warning-' + data.device_id);
        if (timeWarningEl) {
            const timeToWarning = calculateTimeToFlood(data.level_cm, riseRate, 30);
            timeWarningEl.textContent = timeToWarning || '--';
            timeWarningEl.className = 'time-value' + (timeToWarning ? ' active' : '');
        }

        const timeCriticalEl = document.getElementById('time-critical-' + data.device_id);
        if (timeCriticalEl) {
            const timeToCritical = calculateTimeToFlood(data.level_cm, riseRate, 70);
            timeCriticalEl.textContent = timeToCritical || '--';
            timeCriticalEl.className = 'time-value critical' + (timeToCritical ? ' active' : '');
        }

        // Update risk chart
        updateRiskChart();

        // Update stats
        updateStats(currentPredictions);
        updateTimestamp();
    }

    // ===================== INIT =====================

    createWsStatus();
    showLoading();
    initWhatIf();
    fetchPredictions();
});
