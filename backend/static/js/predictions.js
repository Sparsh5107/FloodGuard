(function() {
    var POLL_INTERVAL = 30000;

    function initTabs() {
        var tabBtns = document.querySelectorAll('.tab-btn');
        var savedTab = localStorage.getItem('fg_predictions_tab') || 'predictions';

        tabBtns.forEach(function(btn) {
            if (btn.getAttribute('data-tab') === savedTab) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }

            btn.addEventListener('click', function() {
                var tab = this.getAttribute('data-tab');
                tabBtns.forEach(function(b) { b.classList.remove('active'); });
                this.classList.add('active');
                document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.remove('active'); });
                document.getElementById('tab-' + tab).classList.add('active');
                localStorage.setItem('fg_predictions_tab', tab);
            });
        });

        document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.remove('active'); });
        document.getElementById('tab-' + savedTab).classList.add('active');
    }

    function pollPredictions() {
        fetch('/api/predictions/?_=' + Date.now(), {cache: 'no-store'})
            .then(function(response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(function(data) {
                var container = document.getElementById('predictions-container');
                if (!container || !data.predictions) return;

                var html = '';
                data.predictions.forEach(function(pred) {
                    var trendIcon = pred.trend_direction === 'rising' ? '&#8593;' :
                                    pred.trend_direction === 'falling' ? '&#8595;' : '&#8594;';
                    var trendClass = pred.trend_direction;

                    html += '<div class="prediction-card">' +
                        '<div class="prediction-header">' +
                            '<h3>' + pred.sensor_name + '</h3>' +
                            '<span class="trend-badge ' + trendClass + '">' + trendIcon + ' ' + pred.trend_direction.toUpperCase() + '</span>' +
                        '</div>' +
                        '<p class="prediction-location">' + pred.location + '</p>' +
                        '<div class="prediction-level">' +
                            '<span class="current-level">' + pred.current_level + ' cm</span>' +
                            '<span class="confidence-badge confidence-' + pred.confidence + '">' + pred.confidence.toUpperCase() + ' confidence</span>' +
                        '</div>' +
                        '<div class="prediction-thresholds">';

                    ['warning', 'danger', 'critical'].forEach(function(threshold) {
                        var p = pred.predictions[threshold];
                        var timeStr = p.time_to_threshold || 'N/A';
                        if (timeStr === 'already_exceeded') timeStr = 'EXCEEDED';
                        var prob = p.probability || 0;
                        var color = threshold === 'critical' ? '#dc3545' : threshold === 'danger' ? '#fd7e14' : '#ffc107';

                        html += '<div class="threshold-row">' +
                            '<span class="threshold-name">' + threshold.toUpperCase() + ' (' + (threshold === 'warning' ? '30' : threshold === 'danger' ? '50' : '70') + 'cm)</span>' +
                            '<div class="threshold-info">' +
                                '<span class="time-to-threshold">' + timeStr + '</span>' +
                                '<div class="probability-bar-container">' +
                                    '<div class="probability-bar" style="width: ' + prob + '%; background: ' + color + ';"></div>' +
                                '</div>' +
                                '<span class="probability-value">' + prob + '%</span>' +
                            '</div>' +
                        '</div>';
                    });

                    html += '</div></div>';
                });

                if (!html) {
                    html = '<p class="no-data">No prediction data available</p>';
                }
                container.innerHTML = html;
            })
            .catch(function(err) {
                console.error('Predictions poll error:', err);
            });
    }

    function pollWeather() {
        fetch('/api/weather/?_=' + Date.now(), {cache: 'no-store'})
            .then(function(response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(function(data) {
                var container = document.getElementById('weather-container');
                if (!container || !data.sensors) return;

                var html = '';
                data.sensors.forEach(function(s) {
                    if (!s.weather) {
                        html += '<div class="weather-card weather-no-data">' +
                            '<h3>' + s.name + '</h3>' +
                            '<p>No weather data available (missing coordinates)</p>' +
                        '</div>';
                        return;
                    }

                    var w = s.weather;
                    var rf = s.rainfall_forecast || {};

                    html += '<div class="weather-card">' +
                        '<div class="weather-header">' +
                            '<h3>' + s.name + '</h3>' +
                            '<span class="weather-icon">' + getWeatherIcon(w.weather_code) + '</span>' +
                        '</div>' +
                        '<p class="weather-location">' + s.location + '</p>' +
                        '<div class="weather-current">' +
                            '<div class="weather-stat">' +
                                '<span class="weather-stat-value">' + (w.temperature || '--') + '&deg;C</span>' +
                                '<span class="weather-stat-label">Temperature</span>' +
                            '</div>' +
                            '<div class="weather-stat">' +
                                '<span class="weather-stat-value">' + (w.humidity || '--') + '%</span>' +
                                '<span class="weather-stat-label">Humidity</span>' +
                            '</div>' +
                            '<div class="weather-stat">' +
                                '<span class="weather-stat-value">' + (w.wind_speed || '--') + ' km/h</span>' +
                                '<span class="weather-stat-label">Wind</span>' +
                            '</div>' +
                            '<div class="weather-stat">' +
                                '<span class="weather-stat-value">' + (w.cloud_cover || '--') + '%</span>' +
                                '<span class="weather-stat-label">Clouds</span>' +
                            '</div>' +
                        '</div>' +
                        '<div class="weather-forecast">' +
                            '<div class="forecast-item">' +
                                '<span class="forecast-label">Rain (now):</span>' +
                                '<span class="forecast-value">' + (w.rain || 0) + ' mm</span>' +
                            '</div>' +
                            '<div class="forecast-item">' +
                                '<span class="forecast-label">Rain (24h):</span>' +
                                '<span class="forecast-value">' + (rf.rain_24h || 0) + ' mm</span>' +
                            '</div>' +
                            '<div class="forecast-item">' +
                                '<span class="forecast-label">Rain (72h):</span>' +
                                '<span class="forecast-value">' + (rf.rain_72h || 0) + ' mm</span>' +
                            '</div>' +
                            '<div class="forecast-item">' +
                                '<span class="forecast-label">Max Prob (24h):</span>' +
                                '<span class="forecast-value">' + (rf.max_precipitation_probability_24h || 0) + '%</span>' +
                            '</div>' +
                            '<div class="forecast-item">' +
                                '<span class="forecast-label">Soil Moisture:</span>' +
                                '<span class="forecast-value">' + (rf.avg_soil_moisture_24h || '--') + ' m&sup3;/m&sup3;</span>' +
                            '</div>' +
                        '</div>' +
                    '</div>';
                });

                if (!html) {
                    html = '<p class="no-data">No weather data available</p>';
                }
                container.innerHTML = html;
            })
            .catch(function(err) {
                console.error('Weather poll error:', err);
            });
    }

    function pollFloodData() {
        fetch('/api/flood-data/?_=' + Date.now(), {cache: 'no-store'})
            .then(function(response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(function(data) {
                var container = document.getElementById('flood-container');
                if (!container || !data.sensors) return;

                var html = '';
                data.sensors.forEach(function(s) {
                    if (!s.flood_data || !s.flood_data.summary) {
                        html += '<div class="flood-card flood-no-data">' +
                            '<h3>' + s.name + '</h3>' +
                            '<p>No river discharge data available</p>' +
                        '</div>';
                        return;
                    }

                    var fd = s.flood_data;
                    var sm = fd.summary;
                    var isAbove = sm.is_above_average;
                    var statusClass = isAbove ? 'flood-warning' : 'flood-normal';

                    html += '<div class="flood-card ' + statusClass + '">' +
                        '<div class="flood-header">' +
                            '<h3>' + s.name + '</h3>' +
                            '<span class="flood-status ' + statusClass + '">' +
                                (isAbove ? '&#9888; ABOVE AVERAGE' : '&#10003; NORMAL') +
                            '</span>' +
                        '</div>' +
                        '<p class="flood-location">' + s.location + '</p>' +
                        '<div class="flood-stats">' +
                            '<div class="flood-stat">' +
                                '<span class="flood-stat-value">' + (sm.current_discharge || '--') + ' m&sup3;/s</span>' +
                                '<span class="flood-stat-label">Current Discharge</span>' +
                            '</div>' +
                            '<div class="flood-stat">' +
                                '<span class="flood-stat-value">' + (sm.avg_discharge_30d || '--') + ' m&sup3;/s</span>' +
                                '<span class="flood-stat-label">30-day Average</span>' +
                            '</div>' +
                            '<div class="flood-stat">' +
                                '<span class="flood-stat-value">' + (sm.peak_discharge_30d || '--') + ' m&sup3;/s</span>' +
                                '<span class="flood-stat-label">30-day Peak</span>' +
                            '</div>' +
                        '</div>' +
                    '</div>';
                });

                if (!html) {
                    html = '<p class="no-data">No flood data available</p>';
                }
                container.innerHTML = html;
            })
            .catch(function(err) {
                console.error('Flood data poll error:', err);
            });
    }

    function getWeatherIcon(code) {
        if (code <= 1) return '&#9728;';
        if (code <= 3) return '&#9925;';
        if (code <= 48) return '&#127787;';
        if (code <= 55) return '&#127782;';
        if (code <= 65) return '&#127783;';
        if (code <= 75) return '&#127784;';
        if (code <= 82) return '&#127783;';
        if (code <= 86) return '&#127784;';
        if (code >= 95) return '&#9889;';
        return '&#127782;';
    }

    document.addEventListener('DOMContentLoaded', function() {
        initTabs();
        pollPredictions();
        pollWeather();
        pollFloodData();
        setInterval(pollPredictions, POLL_INTERVAL);
        setInterval(pollWeather, POLL_INTERVAL);
        setInterval(pollFloodData, POLL_INTERVAL);
    });
})();
