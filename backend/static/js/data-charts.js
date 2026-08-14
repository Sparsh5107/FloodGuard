// FloodGuard Data Charts - Line, Bar, Polar Area with real-time auto-refresh

(function () {
    'use strict';

    var NORMAL_INTERVAL = 5 * 1000;
    var CRITICAL_INTERVAL = 5 * 1000;
    var charts = {};
    var refreshTimer = null;
    var currentType = 'line';

    var LEVEL_COLORS = {
        normal: { line: '#22c55e', bg: 'rgba(34, 197, 94, 0.08)' },
        warning: { line: '#eab308', bg: 'rgba(234, 179, 8, 0.08)' },
        danger: { line: '#f97316', bg: 'rgba(249, 115, 22, 0.08)' },
        critical: { line: '#ef4444', bg: 'rgba(239, 68, 68, 0.08)' },
        offline: { line: '#94a3b8', bg: 'rgba(148, 163, 184, 0.08)' }
    };

    var STATUS_ICONS = {
        offline: '&#9888;', rising: '&#9650;', falling: '&#9660;', stable: '&#9644;', no_data: '&#8212;'
    };
    var STATUS_LABELS = {
        offline: 'Offline', rising: 'Rising', falling: 'Falling', stable: 'Stable', no_data: 'No Data'
    };

    Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
    Chart.defaults.font.size = 11;
    Chart.defaults.color = '#64748b';

    function getLevelType(level) {
        if (level >= 70) return 'critical';
        if (level >= 50) return 'danger';
        if (level >= 30) return 'warning';
        return 'normal';
    }

    function getLevelColors(level) {
        return LEVEL_COLORS[getLevelType(level)];
    }

    function hasCritical(sensors) {
        return sensors.some(function (s) { return s.alert_level === 'critical' || s.alert_level === 'danger'; });
    }

    function formatTime(date) {
        var d = new Date(date);
        return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0');
    }

    function fetchSensorStatus() {
        return fetch('/api/sensor-status/?_=' + Date.now(), { cache: 'no-store' })
            .then(function (r) { return r.json(); })
            .then(function (data) { return data.sensors || []; })
            .catch(function () { return []; });
    }

    function fetchHistory(deviceId) {
        return fetch('/api/sensor-history/' + deviceId + '/?_=' + Date.now(), { cache: 'no-store' })
            .then(function (r) { return r.json(); })
            .then(function (d) { return d.history || []; })
            .catch(function () { return []; });
    }

    function buildOverview() {
        var container = document.getElementById('sensor-overview');
        if (!container || !SENSORS) return;
        var html = '';
        SENSORS.forEach(function (s) {
            var colors = getLevelColors(s.level);
            var pct = Math.min(s.level, 100);
            html = html +
                '<div class="overview-card">' +
                    '<div class="overview-top">' +
                        '<div class="overview-icon" style="background:' + colors.bg + ';"><span style="color:' + colors.line + ';">&#x1F4A7;</span></div>' +
                        '<div class="overview-text"><div class="overview-name">' + s.name + '</div><div class="overview-location">' + s.location + '</div></div>' +
                    '</div>' +
                    '<div class="overview-level" style="color:' + colors.line + ';">' + s.level + '<span class="overview-unit"> cm</span></div>' +
                    '<div class="overview-bar-bg"><div class="overview-bar-fill" style="width:' + pct + '%;background:' + colors.line + ';"></div></div>' +
                    '<div class="overview-bottom"><span class="overview-status" style="color:' + colors.line + ';">' + (STATUS_ICONS[s.status] || '') + ' ' + (STATUS_LABELS[s.status] || s.status) + '</span><span class="overview-threshold">' + getLevelType(s.level) + '</span></div>' +
                '</div>';
        });
        container.innerHTML = html;
    }

    function updateLiveStats() {
        if (!SENSORS) return;
        var total = SENSORS.length;
        var active = SENSORS.filter(function (s) { return s.status !== 'offline'; }).length;
        var alerts = SENSORS.filter(function (s) { return s.alert_level === 'warning' || s.alert_level === 'danger' || s.alert_level === 'critical'; }).length;
        var totalLevel = SENSORS.reduce(function (sum, s) { return sum + s.level; }, 0);
        var avg = total > 0 ? (totalLevel / total).toFixed(1) : '0.0';

        var el;
        el = document.getElementById('stat-total'); if (el) el.textContent = total;
        el = document.getElementById('stat-active'); if (el) el.textContent = active;
        el = document.getElementById('stat-alerts'); if (el) el.textContent = alerts;
        el = document.getElementById('stat-avg'); if (el) el.textContent = avg + ' cm';

        var refreshEl = document.getElementById('stat-refresh');
        if (refreshEl) {
            var isCritical = hasCritical(SENSORS);
            refreshEl.textContent = isCritical ? 'CRITICAL' : 'Live';
            refreshEl.style.color = isCritical ? '#ef4444' : '#22c55e';
        }
    }

    function buildChartCard(sensor) {
        var colors = getLevelColors(sensor.level);
        return '<div class="sensor-chart-card" id="chart-card-' + sensor.device_id + '">' +
            '<div class="chart-card-header"><div class="chart-card-title"><span class="chart-card-dot" style="background:' + colors.line + ';"></span><div><h3>' + sensor.name + '</h3><span class="chart-card-subtitle">Water level over 24 hours</span></div></div><div class="chart-card-level" style="color:' + colors.line + ';">' + sensor.level + ' cm</div></div>' +
            '<div class="chart-card-body"><canvas id="chart-' + sensor.device_id + '"></canvas></div>' +
            '<div class="chart-card-footer"><div class="chart-legend-item"><span class="chart-legend-line" style="background:#22c55e;"></span> Normal (&lt;30cm)</div><div class="chart-legend-item"><span class="chart-legend-line" style="background:#eab308;"></span> Warning (30-50cm)</div><div class="chart-legend-item"><span class="chart-legend-line" style="background:#f97316;"></span> Danger (50-70cm)</div><div class="chart-legend-item"><span class="chart-legend-line" style="background:#ef4444;"></span> Critical (&gt;70cm)</div></div>' +
        '</div>';
    }

    var thresholdPlugin = {
        id: 'thresholdLines',
        beforeDraw: function (chart) {
            if (chart.config.type === 'bar' || chart.config.type === 'polarArea') return;
            var yScale = chart.scales.y;
            var ctx = chart.ctx;
            var area = chart.chartArea;
            [{ v: 30, c: '#eab308', l: 'Warning' }, { v: 50, c: '#f97316', l: 'Danger' }, { v: 70, c: '#ef4444', l: 'Critical' }].forEach(function (t) {
                var y = yScale.getPixelForValue(t.v);
                if (y >= area.top && y <= area.bottom) {
                    ctx.save();
                    ctx.beginPath();
                    ctx.setLineDash([6, 4]);
                    ctx.strokeStyle = t.c + '60';
                    ctx.lineWidth = 1;
                    ctx.moveTo(area.left, y);
                    ctx.lineTo(area.right, y);
                    ctx.stroke();
                    ctx.fillStyle = t.c + '90';
                    ctx.font = '9px Segoe UI';
                    ctx.textAlign = 'right';
                    ctx.fillText(t.l, area.right - 4, y - 3);
                    ctx.restore();
                }
            });
        }
    };

    function createChart(canvasId, history, sensorName, type) {
        var ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        var timeData = history.map(function (h) { return { x: new Date(h.timestamp), y: h.level_cm }; });
        var barLabels = history.map(function (h) { return formatTime(h.timestamp); });
        var barData = history.map(function (h) { return h.level_cm; });
        var barColors = barData.map(function (v) {
            if (v >= 70) return '#ef4444';
            if (v >= 50) return '#f97316';
            if (v >= 30) return '#eab308';
            return '#22c55e';
        });

        var gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 220);
        gradient.addColorStop(0, 'rgba(26, 115, 232, 0.22)');
        gradient.addColorStop(1, 'rgba(26, 115, 232, 0.01)');

        var dataset, options, chartType, chartData;

        if (type === 'bar') {
            chartType = 'bar';
            dataset = {
                label: sensorName, data: barData,
                backgroundColor: barColors.map(function (c) { return c + 'BB'; }),
                borderColor: barColors, borderWidth: 1.5, borderRadius: 4,
                borderSkipped: false, barPercentage: 0.7, categoryPercentage: 0.8
            };
            chartData = { labels: barLabels, datasets: [dataset] };
            options = {
                responsive: true, maintainAspectRatio: false, animation: { duration: 500 },
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.92)', titleColor: '#e2e8f0', bodyColor: '#e2e8f0',
                        padding: { top: 10, bottom: 10, left: 14, right: 14 }, cornerRadius: 8,
                        titleFont: { size: 11, weight: '600' }, bodyFont: { size: 13, weight: '700' }, displayColors: false,
                        callbacks: {
                            title: function (items) { return items[0].label || ''; },
                            label: function (item) { var val = item.parsed.y; return val + ' cm  (' + getLevelType(val).charAt(0).toUpperCase() + getLevelType(val).slice(1) + ')'; }
                        }
                    }
                },
                scales: {
                    x: { title: { display: true, text: 'Time', font: { size: 11, weight: '600' }, color: '#94a3b8' }, grid: { display: false }, ticks: { maxTicksLimit: 8, font: { size: 9 }, color: '#94a3b8', maxRotation: 45 }, border: { display: false } },
                    y: { beginAtZero: true, max: 100, title: { display: true, text: 'Water Level (cm)', font: { size: 11, weight: '600' }, color: '#94a3b8' }, grid: { color: 'rgba(0,0,0,0.04)', drawBorder: false }, ticks: { stepSize: 20, font: { size: 10 }, color: '#94a3b8', callback: function (v) { return v + ' cm'; } }, border: { display: false } }
                }
            };
        } else if (type === 'polarArea') {
            var recentHistory = history.slice(-12);
            var polarLabels = recentHistory.map(function (h) { return formatTime(h.timestamp); });
            var polarData = recentHistory.map(function (h) { return h.level_cm; });
            var polarColors = polarData.map(function (v) {
                if (v >= 70) return 'rgba(239, 68, 68, 0.7)';
                if (v >= 50) return 'rgba(249, 115, 22, 0.7)';
                if (v >= 30) return 'rgba(234, 179, 8, 0.7)';
                return 'rgba(34, 197, 94, 0.7)';
            });
            var polarBorders = polarData.map(function (v) {
                if (v >= 70) return '#ef4444';
                if (v >= 50) return '#f97316';
                if (v >= 30) return '#eab308';
                return '#22c55e';
            });
            chartType = 'polarArea';
            dataset = { data: polarData, backgroundColor: polarColors, borderColor: polarBorders, borderWidth: 2 };
            chartData = { labels: polarLabels, datasets: [dataset] };
            options = {
                responsive: true, maintainAspectRatio: false, animation: { duration: 500 },
                plugins: {
                    legend: { display: true, position: 'right', labels: { font: { size: 9 }, padding: 6, usePointStyle: true, pointStyle: 'circle', color: '#64748b' } },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.92)', titleColor: '#e2e8f0', bodyColor: '#e2e8f0',
                        padding: { top: 10, bottom: 10, left: 14, right: 14 }, cornerRadius: 8,
                        bodyFont: { size: 13, weight: '700' }, displayColors: true,
                        callbacks: {
                            title: function (items) { return polarLabels[items[0].dataIndex] || ''; },
                            label: function (item) { var val = item.parsed.r; return ' ' + val + ' cm  (' + getLevelType(val).charAt(0).toUpperCase() + getLevelType(val).slice(1) + ')'; }
                        }
                    }
                },
                scales: { r: { beginAtZero: true, max: 100, ticks: { stepSize: 20, font: { size: 9 }, color: '#94a3b8', backdropColor: 'transparent' }, grid: { color: 'rgba(0,0,0,0.06)' } } }
            };
        } else {
            chartType = 'line';
            dataset = {
                label: sensorName, data: timeData, borderColor: '#1a73e8', backgroundColor: gradient,
                borderWidth: 2.5, pointRadius: timeData.length > 30 ? 0 : 3, pointHoverRadius: 6,
                pointBackgroundColor: '#1a73e8', pointBorderColor: '#fff', pointBorderWidth: 2, tension: 0.35, fill: true
            };
            chartData = { datasets: [dataset] };
            options = {
                responsive: true, maintainAspectRatio: false, animation: { duration: 600, easing: 'easeOutQuart' },
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.92)', titleColor: '#e2e8f0', bodyColor: '#e2e8f0',
                        padding: { top: 10, bottom: 10, left: 14, right: 14 }, cornerRadius: 8,
                        titleFont: { size: 11, weight: '600' }, bodyFont: { size: 13, weight: '700' }, displayColors: false,
                        callbacks: {
                            title: function (items) { var d = new Date(items[0].parsed.x); return d.toLocaleDateString() + '  ' + formatTime(d); },
                            label: function (item) { var val = item.parsed.y; return val + ' cm  (' + getLevelType(val).charAt(0).toUpperCase() + getLevelType(val).slice(1) + ')'; }
                        }
                    }
                },
                scales: {
                    x: { type: 'time', time: { unit: 'hour', displayFormats: { hour: 'HH:mm' } }, title: { display: true, text: 'Time (last 24 hours)', font: { size: 11, weight: '600' }, color: '#94a3b8' }, grid: { color: 'rgba(0,0,0,0.04)', drawBorder: false }, ticks: { maxTicksLimit: 7, font: { size: 10 }, color: '#94a3b8' }, border: { display: false } },
                    y: { beginAtZero: true, max: 100, title: { display: true, text: 'Water Level (cm)', font: { size: 11, weight: '600' }, color: '#94a3b8' }, grid: { color: 'rgba(0,0,0,0.04)', drawBorder: false }, ticks: { stepSize: 20, font: { size: 10 }, color: '#94a3b8', callback: function (v) { return v + ' cm'; } }, border: { display: false } }
                }
            };
        }

        return new Chart(ctx, { type: chartType, data: chartData, options: options, plugins: type === 'line' ? [thresholdPlugin] : [] });
    }

    function destroyAllCharts() {
        Object.keys(charts).forEach(function (id) {
            if (charts[id]) { charts[id].destroy(); delete charts[id]; }
        });
    }

    function buildAllCharts(type) {
        destroyAllCharts();
        var grid = document.getElementById('sensor-charts-grid');
        if (!grid) return Promise.resolve();
        var html = '';
        SENSORS.forEach(function (s) { html += buildChartCard(s); });
        grid.innerHTML = html;
        var promises = SENSORS.map(function (sensor) {
            return fetchHistory(sensor.device_id).then(function (history) {
                var chart = createChart('chart-' + sensor.device_id, history, sensor.name, type);
                if (chart) charts[sensor.device_id] = chart;
            });
        });
        return Promise.all(promises);
    }

    function refreshAll() {
        if (!SENSORS || SENSORS.length === 0) return;

        fetchSensorStatus().then(function (liveSensors) {
            liveSensors.forEach(function (live) {
                var match = SENSORS.find(function (s) { return s.device_id === live.device_id; });
                if (match) {
                    match.level = live.level_cm;
                    match.status = live.status;
                    if (live.level_cm >= 70) match.alert_level = 'critical';
                    else if (live.level_cm >= 50) match.alert_level = 'danger';
                    else if (live.level_cm >= 30) match.alert_level = 'warning';
                    else match.alert_level = 'normal';
                }
            });
            buildOverview();
            updateLiveStats();

            var promises = SENSORS.map(function (sensor) {
                return fetchHistory(sensor.device_id).then(function (history) {
                    if (!charts[sensor.device_id]) return;
                    var chart = charts[sensor.device_id];
                    if (currentType === 'bar') {
                        chart.data.labels = history.map(function (h) { return formatTime(h.timestamp); });
                        var bData = history.map(function (h) { return h.level_cm; });
                        chart.data.datasets[0].data = bData;
                        chart.data.datasets[0].backgroundColor = bData.map(function (v) { return (v >= 70 ? '#ef4444' : v >= 50 ? '#f97316' : v >= 30 ? '#eab308' : '#22c55e') + 'BB'; });
                        chart.data.datasets[0].borderColor = bData.map(function (v) { return v >= 70 ? '#ef4444' : v >= 50 ? '#f97316' : v >= 30 ? '#eab308' : '#22c55e'; });
                    } else if (currentType === 'polarArea') {
                        var rH = history.slice(-12);
                        chart.data.labels = rH.map(function (h) { return formatTime(h.timestamp); });
                        var pD = rH.map(function (h) { return h.level_cm; });
                        chart.data.datasets[0].data = pD;
                        chart.data.datasets[0].backgroundColor = pD.map(function (v) { return v >= 70 ? 'rgba(239,68,68,0.7)' : v >= 50 ? 'rgba(249,115,22,0.7)' : v >= 30 ? 'rgba(234,179,8,0.7)' : 'rgba(34,197,94,0.7)'; });
                        chart.data.datasets[0].borderColor = pD.map(function (v) { return v >= 70 ? '#ef4444' : v >= 50 ? '#f97316' : v >= 30 ? '#eab308' : '#22c55e'; });
                    } else {
                        var tData = history.map(function (h) { return { x: new Date(h.timestamp), y: h.level_cm }; });
                        chart.data.datasets[0].data = tData;
                        chart.data.datasets[0].pointRadius = tData.length > 30 ? 0 : 3;
                    }
                    chart.update();
                });
            });

            Promise.all(promises).then(scheduleNext).catch(scheduleNext);
        }).catch(scheduleNext);
    }

    function scheduleNext() {
        if (refreshTimer) clearTimeout(refreshTimer);
        var critical = hasCritical(SENSORS);
        var interval = critical ? CRITICAL_INTERVAL : NORMAL_INTERVAL;
        var statusEl = document.getElementById('refresh-interval');
        var dotEl = document.getElementById('refresh-dot');
        if (statusEl) statusEl.textContent = critical ? '5s (Alert Active)' : '5 sec';
        if (dotEl) { dotEl.style.background = critical ? '#ef4444' : '#22c55e'; dotEl.classList.toggle('pulse', critical); }
        refreshTimer = setTimeout(refreshAll, interval);
    }

    function init() {
        if (!SENSORS || SENSORS.length === 0) return;
        buildOverview();
        var selector = document.getElementById('chart-type-selector');
        if (selector) {
            selector.addEventListener('click', function (e) {
                var btn = e.target.closest('.chart-type-btn');
                if (!btn) return;
                var type = btn.getAttribute('data-type');
                if (type === currentType) return;
                currentType = type;
                selector.querySelectorAll('.chart-type-btn').forEach(function (b) { b.classList.remove('active'); });
                btn.classList.add('active');
                buildAllCharts(type).then(scheduleNext).catch(scheduleNext);
            });
        }
        buildAllCharts(currentType).then(scheduleNext).catch(scheduleNext);
    }

    document.addEventListener('DOMContentLoaded', init);
})();
