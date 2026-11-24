/**
 * ==========================================================================
 * EKA DASHBOARD — PUBLIC MONITORING (WALLBOARD NOC) CONTROLLER
 * Zero Inline JS Architecture • Realtime Fleet Telemetry Engine
 * ==========================================================================
 */

// Color Palette Constants
const COLORS = {
    good: '#3fb950',
    warning: '#d29922',
    danger: '#f85149',
    info: '#58a6ff',
    purple: '#a855f7',
    muted: 'rgba(255, 255, 255, 0.08)'
};

// Data Histories for Line Charts
let cpuHistory = [];
let ramHistory = [];
let netUpHistory = [];
let netDownHistory = [];
const MAX_POINTS = 60;

let lastNetData = null;

// Chart Instances
let donutCPU = null;
let donutRAM = null;
let donutDisk = null;
let donutNetwork = null;
let donutDocker = null;
let cpuRamChart = null;
let networkChart = null;

// Lifecycle Initialization
document.addEventListener('DOMContentLoaded', () => {
    initDonutCharts();
    initLineCharts();
    
    // Core metrics loop (every 2 seconds)
    loadMetrics();
    setInterval(loadMetrics, 2000);

    // Fleet Infrastructure Telemetry loop (every 10 seconds)
    loadFleetTelemetry();
    setInterval(loadFleetTelemetry, 10000);

    // Additional modules
    initHomeMonitor();
    loadMonitoringConfig();
    handleAccessDeniedQuery();
});

/* ==========================================================================
   1. CHART INITIALIZATION (DONUTS & LINE CHARTS)
   ========================================================================== */

function initDonutCharts() {
    const donutOptions = {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '76%',
        plugins: {
            legend: { display: false },
            tooltip: { enabled: false }
        },
        animation: { duration: 300 }
    };

    const cpuEl = document.getElementById('donut-cpu');
    if (cpuEl) {
        donutCPU = new Chart(cpuEl, {
            type: 'doughnut',
            data: {
                datasets: [{
                    data: [0, 100],
                    backgroundColor: [COLORS.good, COLORS.muted],
                    borderWidth: 0
                }]
            },
            options: donutOptions
        });
    }

    const ramEl = document.getElementById('donut-ram');
    if (ramEl) {
        donutRAM = new Chart(ramEl, {
            type: 'doughnut',
            data: {
                datasets: [{
                    data: [0, 100],
                    backgroundColor: [COLORS.good, COLORS.muted],
                    borderWidth: 0
                }]
            },
            options: donutOptions
        });
    }

    const diskEl = document.getElementById('donut-disk');
    if (diskEl) {
        donutDisk = new Chart(diskEl, {
            type: 'doughnut',
            data: {
                datasets: [{
                    data: [0, 100],
                    backgroundColor: [COLORS.good, COLORS.muted],
                    borderWidth: 0
                }]
            },
            options: donutOptions
        });
    }

    const netEl = document.getElementById('donut-network');
    if (netEl) {
        donutNetwork = new Chart(netEl, {
            type: 'doughnut',
            data: {
                datasets: [{
                    data: [50, 50],
                    backgroundColor: [COLORS.danger, COLORS.info],
                    borderWidth: 0
                }]
            },
            options: donutOptions
        });
    }

    const docEl = document.getElementById('donut-docker');
    if (docEl) {
        donutDocker = new Chart(docEl, {
            type: 'doughnut',
            data: {
                datasets: [{
                    data: [0, 0],
                    backgroundColor: [COLORS.good, COLORS.danger],
                    borderWidth: 0
                }]
            },
            options: donutOptions
        });
    }
}

function initLineCharts() {
    const lineOptions = {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 0 },
        interaction: { intersect: false, mode: 'index' },
        scales: {
            x: { display: false },
            y: {
                min: 0,
                max: 100,
                grid: { color: 'rgba(255, 255, 255, 0.04)' },
                ticks: { color: '#94a3b8', font: { size: 10 } }
            }
        },
        plugins: { legend: { display: false } },
        elements: {
            point: { radius: 0 },
            line: { tension: 0.4, borderWidth: 2 }
        }
    };

    const cpuRamEl = document.getElementById('chart-cpu-ram');
    if (cpuRamEl) {
        cpuRamChart = new Chart(cpuRamEl, {
            type: 'line',
            data: {
                labels: Array(MAX_POINTS).fill(''),
                datasets: [
                    { data: [], borderColor: '#58a6ff', backgroundColor: 'rgba(88, 166, 255, 0.12)', fill: true },
                    { data: [], borderColor: '#3fb950', backgroundColor: 'rgba(63, 185, 80, 0.12)', fill: true }
                ]
            },
            options: lineOptions
        });
    }

    const netChartEl = document.getElementById('chart-network');
    if (netChartEl) {
        networkChart = new Chart(netChartEl, {
            type: 'line',
            data: {
                labels: Array(MAX_POINTS).fill(''),
                datasets: [
                    { data: [], borderColor: '#f85149', backgroundColor: 'rgba(248, 81, 73, 0.12)', fill: true },
                    { data: [], borderColor: '#a371f7', backgroundColor: 'rgba(163, 113, 247, 0.12)', fill: true }
                ]
            },
            options: {
                ...lineOptions,
                scales: {
                    ...lineOptions.scales,
                    y: { ...lineOptions.scales.y, max: undefined }
                }
            }
        });
    }
}

/* ==========================================================================
   2. CORE METRICS ENGINE (/api/metrics)
   ========================================================================== */

function loadMetrics() {
    fetch('/api/metrics')
        .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
        })
        .then(data => {
            updateDonutCharts(data);
            updateLineCharts(data);
            updateEnergyMetrics(data);
        })
        .catch(err => {
            console.warn('[Monitoring] Gagal memuat metrik inti:', err);
        });
}

function updateDonutCharts(data) {
    if (!data) return;

    // CPU Telemetry
    if (data.cpu) {
        const cpu = Math.round(data.cpu.percent || 0);
        safeSetText('cpu-value', cpu);
        safeSetText('cpu-load', (data.cpu.load_1 || 0).toFixed(2));
        safeSetText('cpu-cores', data.cpu.cores || 0);
        if (donutCPU) updateDonut(donutCPU, cpu, 'cpu-status');
    }

    // RAM Telemetry
    if (data.memory) {
        const ram = Math.round(data.memory.percent || 0);
        safeSetText('ram-value', ram);
        safeSetText('ram-used', formatBytes(data.memory.used || 0));
        safeSetText('ram-total', formatBytes(data.memory.total || 0));
        if (donutRAM) updateDonut(donutRAM, ram, 'ram-status');
    }

    // Disk Telemetry
    if (data.disk && data.disk.partitions) {
        const disk = data.disk.partitions.find(p => p.mountpoint === '/') || data.disk.partitions[0];
        if (disk) {
            const diskPct = Math.round(disk.percent || 0);
            safeSetText('disk-value', diskPct);
            safeSetText('disk-free', formatBytes(disk.free || 0));
            if (donutDisk) updateDonut(donutDisk, diskPct, 'disk-status');
        }
    }

    // Network Telemetry
    if (data.network && data.network.interfaces) {
        let totalSent = 0, totalRecv = 0;
        data.network.interfaces.forEach(i => {
            totalSent += (i.bytes_sent || 0);
            totalRecv += (i.bytes_recv || 0);
        });

        if (lastNetData) {
            const elapsed = (data.timestamp - lastNetData.timestamp) / 1000;
            if (elapsed > 0) {
                const upSpeed = Math.max(0, (totalSent - lastNetData.sent) / elapsed);
                const downSpeed = Math.max(0, (totalRecv - lastNetData.recv) / elapsed);

                const [val, unit] = formatSpeed(upSpeed + downSpeed);
                safeSetText('net-speed', val);
                safeSetText('net-unit', unit);
                safeSetText('net-up', formatSpeedSimple(upSpeed));
                safeSetText('net-down', formatSpeedSimple(downSpeed));

                // Update Network Ratio Donut
                const total = upSpeed + downSpeed;
                if (donutNetwork) {
                    if (total > 0) {
                        donutNetwork.data.datasets[0].data = [upSpeed, downSpeed];
                    } else {
                        donutNetwork.data.datasets[0].data = [50, 50];
                    }
                    donutNetwork.update('none');
                }

                // Network Status
                const totalKB = total / 1024;
                let netStatus = 'Idle';
                let netClass = 'good';
                if (totalKB > 1000) { netStatus = 'High'; netClass = 'warning'; }
                else if (totalKB > 100) { netStatus = 'Active'; netClass = 'good'; }
                updateStatus('net-status', netStatus, netClass);

                // History push
                netUpHistory.push(upSpeed / 1024);
                netDownHistory.push(downSpeed / 1024);
                if (netUpHistory.length > MAX_POINTS) netUpHistory.shift();
                if (netDownHistory.length > MAX_POINTS) netDownHistory.shift();
            }
        }
        lastNetData = { sent: totalSent, recv: totalRecv, timestamp: data.timestamp };
    }

    // Docker Telemetry
    if (data.docker) {
        const running = data.docker.running || 0;
        const stopped = data.docker.stopped || 0;
        const total = running + stopped;
        safeSetText('docker-total', total);
        safeSetText('docker-running', running);
        safeSetText('docker-stopped', stopped);
        if (donutDocker) {
            donutDocker.data.datasets[0].data = [running, Math.max(0, stopped)];
            donutDocker.update('none');
        }
    }

    // Top Status Bar (Uptime & Temperature)
    if (data.uptime !== undefined) {
        safeSetText('uptime', formatUptime(data.uptime));
    }
    if (data.cpu && data.cpu.temp !== undefined) {
        safeSetText('temp', data.cpu.temp > 0 ? `${data.cpu.temp.toFixed(0)}°C` : '--');
    }

    // Line Chart History Push
    if (data.cpu && data.cpu.percent !== undefined) {
        cpuHistory.push(data.cpu.percent);
        if (cpuHistory.length > MAX_POINTS) cpuHistory.shift();
    }
    if (data.memory && data.memory.percent !== undefined) {
        ramHistory.push(data.memory.percent);
        if (ramHistory.length > MAX_POINTS) ramHistory.shift();
    }
}

function updateDonut(chart, value, statusId) {
    if (!chart) return;
    const color = value > 90 ? COLORS.danger : value > 70 ? COLORS.warning : COLORS.good;
    chart.data.datasets[0].data = [value, Math.max(0, 100 - value)];
    chart.data.datasets[0].backgroundColor = [color, COLORS.muted];
    chart.update('none');

    const status = value > 90 ? 'Critical' : value > 70 ? 'Warning' : 'Normal';
    const statusClass = value > 90 ? 'danger' : value > 70 ? 'warning' : 'good';
    updateStatus(statusId, status, statusClass);
}

function updateStatus(id, text, className) {
    const el = document.getElementById(id);
    if (el) {
        el.textContent = text;
        el.className = 'status-badge ' + className;
    }
}

function updateLineCharts(data) {
    if (cpuRamChart) {
        cpuRamChart.data.datasets[0].data = [...cpuHistory];
        cpuRamChart.data.datasets[1].data = [...ramHistory];
        cpuRamChart.update('none');
    }

    if (networkChart) {
        networkChart.data.datasets[0].data = [...netUpHistory];
        networkChart.data.datasets[1].data = [...netDownHistory];
        networkChart.update('none');
    }
}

function updateEnergyMetrics(data) {
    if (data.power) {
        const p = data.power;
        safeSetText('energy-kwh', p.kwh || '0.0000');
        const kwh = parseFloat(p.kwh || 0) || 0;
        const tariff = p.tariff_per_kwh !== undefined ? parseFloat(p.tariff_per_kwh) : 1444.70;
        const cost = p.estimated_cost !== undefined ? parseFloat(p.estimated_cost) : (kwh * tariff);
        const symbol = (p.currency_symbol !== undefined ? String(p.currency_symbol) : 'Rp').trim();
        const locale = p.locale || 'id-ID';
        const decimals = Math.max(0, Math.min(4, parseInt(p.decimals !== undefined ? p.decimals : 0, 10) || 0));

        let costStr;
        if (decimals === 0 && cost > 0 && cost < 1) {
            costStr = '< 1';
        } else {
            try {
                costStr = cost.toLocaleString(locale, {
                    minimumFractionDigits: decimals,
                    maximumFractionDigits: decimals
                });
            } catch (e) {
                costStr = cost.toFixed(decimals);
            }
        }
        safeSetText('energy-cost', symbol ? `${symbol} ${costStr}` : costStr);

        const watts = p.watts_est !== undefined ? p.watts_est : '--';
        let source = 'Est';
        if (p.source === 'rapl') source = 'Hardware RAPL';
        else if (p.source === 'power_supply') source = 'Battery/UPS';
        let wattText = `${watts}W (${source})`;
        if (p.battery && p.battery.capacity !== null && p.battery.capacity !== undefined) {
            wattText += ` • ${p.battery.capacity}%`;
        }
        safeSetText('energy-watts', wattText);
    }
}

/* ==========================================================================
   3. FLEET INFRASTRUCTURE TELEMETRY (/api/monitoring/telemetry)
   ========================================================================== */

function loadFleetTelemetry() {
    fetch('/api/monitoring/telemetry')
        .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
        })
        .then(data => {
            if (!data) return;

            // 1. SMART Drive Health
            if (data.smart) {
                const s = data.smart;
                const isHealthy = s.healthy;
                updateStatus('telemetry-smart-badge', s.text || (isHealthy ? 'PASSED' : 'WARNING'), isHealthy ? 'good' : 'warning');
                safeSetText('telemetry-smart-status', isHealthy ? 'All Drives Healthy' : 'Degraded Health');
                safeSetText('telemetry-smart-temp', s.temp > 0 ? s.temp : '--');
                const subEl = document.getElementById('telemetry-smart-sub');
                if (subEl) {
                    const tempText = s.temp > 0 ? `${s.temp}°C` : '--';
                    subEl.innerHTML = `${s.drives} Drive(s) • Max: <strong>${tempText}</strong>`;
                }
            }

            // 2. Web Shield & Host Firewall (UFW)
            if (data.firewall) {
                const fw = data.firewall;
                const isActive = fw.active;
                updateStatus('telemetry-firewall-badge', fw.status_text || (isActive ? 'ACTIVE' : 'INACTIVE'), isActive ? 'good' : 'danger');
                safeSetText('telemetry-firewall-status', isActive ? 'Firewall Active' : 'Unprotected');
                safeSetText('telemetry-firewall-rules', fw.rules_count || 0);
                const subEl = document.getElementById('telemetry-firewall-sub');
                if (subEl) {
                    subEl.innerHTML = `<strong>${fw.rules_count || 0}</strong> Rules Active • SSH Guard`;
                }
            }

            // 3. Systemd Services
            if (data.services) {
                const svc = data.services;
                const isDegraded = (svc.failed || 0) > 0;
                updateStatus('telemetry-services-badge', isDegraded ? 'DEGRADED' : 'HEALTHY', isDegraded ? 'warning' : 'good');
                safeSetText('telemetry-services-status', isDegraded ? `${svc.failed} Failed` : 'Running Normal');
                safeSetText('telemetry-services-failed', svc.failed || 0);
                const subEl = document.getElementById('telemetry-services-sub');
                if (subEl) {
                    subEl.innerHTML = `State: <strong>${svc.state || 'running'}</strong> • Failed: <strong>${svc.failed || 0}</strong>`;
                }
            }

            // 4. OS & Kernel Updates
            if (data.packages) {
                const pkg = data.packages;
                const needReboot = pkg.reboot_required;
                const secCount = pkg.security || 0;
                let badgeText = 'UP TO DATE';
                let badgeClass = 'good';

                if (needReboot) {
                    badgeText = 'REBOOT REQ';
                    badgeClass = 'danger';
                } else if (secCount > 0) {
                    badgeText = `${secCount} SEC PATCH`;
                    badgeClass = 'warning';
                } else if ((pkg.upgradable || 0) > 0) {
                    badgeText = `${pkg.upgradable} UPDATES`;
                    badgeClass = 'info';
                }

                updateStatus('telemetry-packages-badge', badgeText, badgeClass);
                safeSetText('telemetry-packages-status', needReboot ? 'Reboot Required' : `${pkg.upgradable || 0} Upgradable`);
                safeSetText('telemetry-packages-kernel', pkg.kernel || '--');
                const subEl = document.getElementById('telemetry-packages-sub');
                if (subEl) {
                    subEl.innerHTML = `Kernel: <strong>${pkg.kernel || '--'}</strong>`;
                }
            }

            // 5. Disaster Recovery & Backup
            if (data.backup) {
                const bk = data.backup;
                const isCloud = bk.rclone_active;
                const badgeClass = isCloud ? 'purple' : (bk.total > 0 ? 'good' : 'warning');
                updateStatus('telemetry-backup-badge', bk.status_text || 'READY', badgeClass);
                safeSetText('telemetry-backup-status', bk.total > 0 ? `${bk.total} Snapshots` : 'No Backup');
                safeSetText('telemetry-backup-latest', bk.latest || '--');
                const subEl = document.getElementById('telemetry-backup-sub');
                if (subEl) {
                    subEl.innerHTML = `Latest: <strong>${bk.latest || '--'}</strong>`;
                }
            }

            // 6. WAN Connectivity & Ping
            if (data.connectivity) {
                const conn = data.connectivity;
                const isOnline = conn.online;
                updateStatus('telemetry-conn-badge', isOnline ? 'ONLINE' : 'OFFLINE', isOnline ? 'good' : 'danger');
                safeSetText('telemetry-conn-status', isOnline ? `${conn.latency_ms || 0} ms` : 'Disconnected');
                safeSetText('telemetry-conn-ping', conn.latency_ms || 0);
                const subEl = document.getElementById('telemetry-conn-sub');
                if (subEl) {
                    subEl.innerHTML = isOnline ? `Gateway Latency: <strong>${conn.latency_ms}ms</strong>` : `WAN Down`;
                }
            }
        })
        .catch(err => {
            console.warn('[Monitoring] Gagal memuat telemetri fleet:', err);
        });
}

/* ==========================================================================
   4. HOME MONITORING & CONFIGURATION
   ========================================================================== */

function loadMonitoringConfig() {
    fetch('/api/monitoring/config')
        .then(r => r.json())
        .then(s => {
            const el = document.getElementById('server-name-text');
            if (el && s.server_name) {
                el.textContent = s.server_name;
            }
        })
        .catch(() => {});
}

function initHomeMonitor() {
    fetch('/api/monitoring/config')
        .then(r => r.json())
        .then(s => {
            if (s.mqtt && s.mqtt.enabled && s.mqtt.devices) {
                const devices = s.mqtt.devices;
                const card = document.getElementById('card-home');
                if (card) {
                    card.style.display = 'flex';
                    fetchHomeStatus(devices);
                    setInterval(() => fetchHomeStatus(devices), 3000);
                }
            }
        })
        .catch(() => {});
}

function fetchHomeStatus(devices) {
    fetch('/api/home/status')
        .then(r => r.json())
        .then(data => {
            const list = document.getElementById('home-stats-list');
            if (!list) return;
            list.innerHTML = devices.map(d => {
                const val = data[d.id] ? data[d.id].value : '--';
                if (d.type === 'sensor') {
                    return `<span style="display:flex; justify-content:space-between; width:100%"><span style="color:#94a3b8">${d.name}</span> <strong style="color:#f0f6fc">${val} ${d.unit || ''}</strong></span>`;
                }
                const isOn = val === (d.payload_on || 'ON');
                const color = isOn ? '#3fb950' : '#94a3b8';
                return `<span style="display:flex; justify-content:space-between; width:100%"><span style="color:#94a3b8">${d.name}</span> <strong style="color:${color}">${val}</strong></span>`;
            }).join('');
        })
        .catch(() => {});
}

/* ==========================================================================
   5. ACCESS DENIED MODAL & QUERY PARAMS
   ========================================================================== */

function handleAccessDeniedQuery() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('error') === 'access_denied') {
        const feature = urlParams.get('feature') || 'Restricted Area';
        setTimeout(() => {
            showAdModal(feature);
        }, 120);
    }
}

function showAdModal(feature) {
    const m = document.getElementById('ad-modal');
    const msg = document.getElementById('ad-message');
    if (msg) {
        msg.textContent = "Akses terbatas: Anda tidak memiliki otorisasi untuk mengakses fitur '" + feature + "'. Silakan hubungi Administrator.";
    }
    if (m) m.classList.add('active');
}

function closeAdModal() {
    const m = document.getElementById('ad-modal');
    if (m) m.classList.remove('active');
    window.history.replaceState({}, document.title, window.location.pathname);
}

// Global modal close attachment
window.closeAdModal = closeAdModal;

/* ==========================================================================
   6. UTILITY FORMATTERS
   ========================================================================== */

function safeSetText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatSpeed(bytes) {
    if (!bytes || bytes < 1024) return [(bytes || 0).toFixed(0), 'B/s'];
    if (bytes < 1024 * 1024) return [(bytes / 1024).toFixed(1), 'KB/s'];
    return [(bytes / 1024 / 1024).toFixed(1), 'MB/s'];
}

function formatSpeedSimple(bytes) {
    if (!bytes || bytes < 1024) return (bytes || 0).toFixed(0) + ' B/s';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB/s';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB/s';
}

function formatUptime(seconds) {
    if (!seconds) return '--';
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (d > 0) return `${d}d ${h}h ${m}m ${s}s`;
    if (h > 0) return `${h}h ${m}m ${s}s`;
    return `${m}m ${s}s`;
}

