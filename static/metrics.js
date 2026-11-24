/**
 * Eka Dashboard - System Metrics Module
 * Handles real-time telemetry, Chart.js graphs, process listing, and storage analysis.
 */

let mainChart, coresChart, netChart;
let lastNetData = null;
let historyData = { labels: [], cpu: [], mem: [], netIn: [], netOut: [] };

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    fetchHistory();
    startLiveLoop();
});

function initCharts() {
    // 1. Main History Chart (CPU & Memory)
    const canvasMain = document.getElementById('main-chart');
    if (canvasMain) {
        const ctxMain = canvasMain.getContext('2d');
        mainChart = new Chart(ctxMain, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'CPU Usage %',
                        data: [],
                        borderColor: '#ff6b6b',
                        backgroundColor: 'rgba(255, 107, 107, 0.15)',
                        fill: true,
                        tension: 0.35,
                        pointRadius: 0,
                        borderWidth: 2
                    },
                    {
                        label: 'Memory Usage %',
                        data: [],
                        borderColor: '#4ecdc4',
                        backgroundColor: 'rgba(78, 205, 196, 0.12)',
                        fill: true,
                        tension: 0.35,
                        pointRadius: 0,
                        borderWidth: 2
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        min: 0,
                        max: 100,
                        grid: { color: 'rgba(255, 255, 255, 0.06)' },
                        ticks: { color: '#a0a0b0', font: { family: 'Inter', size: 11 } }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#a0a0b0', maxRotation: 0, font: { family: 'Inter', size: 11 } }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        align: 'end',
                        labels: {
                            color: '#e1e7ef',
                            usePointStyle: true,
                            boxWidth: 8,
                            boxHeight: 8,
                            font: { family: 'Inter', size: 12, weight: '500' }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(20, 20, 28, 0.92)',
                        titleColor: '#ffffff',
                        bodyColor: '#e1e7ef',
                        borderColor: 'rgba(255, 255, 255, 0.12)',
                        borderWidth: 1,
                        padding: 10,
                        cornerRadius: 8,
                        titleFont: { family: 'Inter', size: 12, weight: '600' },
                        bodyFont: { family: 'Inter', size: 12 }
                    }
                },
                animation: { duration: 0 }
            }
        });
    }

    // 2. CPU Cores Load Chart
    const canvasCores = document.getElementById('cores-chart');
    if (canvasCores) {
        coresChart = new Chart(canvasCores, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    data: [],
                    backgroundColor: 'rgba(35, 166, 213, 0.75)',
                    hoverBackgroundColor: '#23a6d5',
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        grid: { display: false },
                        ticks: { color: '#e1e7ef', font: { family: 'Inter', size: 11, weight: '500' } }
                    },
                    x: {
                        max: 100,
                        grid: { color: 'rgba(255, 255, 255, 0.06)' },
                        ticks: { color: '#a0a0b0', font: { family: 'Inter', size: 11 } }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(20, 20, 28, 0.92)',
                        borderColor: 'rgba(255, 255, 255, 0.12)',
                        borderWidth: 1,
                        cornerRadius: 8,
                        callbacks: {
                            label: (ctx) => ` Load: ${ctx.raw}%`
                        }
                    }
                },
                indexAxis: 'y'
            }
        });
    }

    // 3. Network History Chart
    const canvasNet = document.getElementById('network-history-chart');
    if (canvasNet) {
        netChart = new Chart(canvasNet, {
            type: 'line',
            data: {
                labels: Array(30).fill(''),
                datasets: [
                    {
                        label: 'Download (KB/s)',
                        data: Array(30).fill(0),
                        borderColor: '#4ecdc4',
                        backgroundColor: 'rgba(78, 205, 196, 0.12)',
                        fill: true,
                        tension: 0.35,
                        pointRadius: 0,
                        borderWidth: 2
                    },
                    {
                        label: 'Upload (KB/s)',
                        data: Array(30).fill(0),
                        borderColor: '#ff6b6b',
                        backgroundColor: 'rgba(255, 107, 107, 0.12)',
                        fill: true,
                        tension: 0.35,
                        pointRadius: 0,
                        borderWidth: 2
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.06)' },
                        ticks: { color: '#a0a0b0', font: { family: 'Inter', size: 11 } }
                    },
                    x: { display: false }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: '#e1e7ef',
                            usePointStyle: true,
                            boxWidth: 8,
                            boxHeight: 8,
                            font: { family: 'Inter', size: 12, weight: '500' }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(20, 20, 28, 0.92)',
                        borderColor: 'rgba(255, 255, 255, 0.12)',
                        borderWidth: 1,
                        cornerRadius: 8
                    }
                },
                animation: { duration: 0 }
            }
        });
    }
}

function fetchHistory() {
    fetch('/api/metrics/history?hours=24')
        .then(r => r.json())
        .then(data => {
            if (data.labels && mainChart) {
                const labels = data.labels.map(ts => new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
                mainChart.data.labels = labels;
                mainChart.data.datasets[0].data = data.cpu;
                mainChart.data.datasets[1].data = data.ram;
                mainChart.update();
            }
        })
        .catch(err => console.error('Error fetching metrics history:', err));
}

function startLiveLoop() {
    updateMetrics();
    setInterval(updateMetrics, 3000);
}

function updateMetrics() {
    fetch('/api/metrics/detailed')
        .then(r => r.json())
        .then(data => {
            if (data.error) return;

            // 1. Top Stats Cards
            const cpuVal = document.getElementById('stat-cpu-val');
            if (cpuVal) cpuVal.innerText = data.cpu.total.toFixed(1) + '%';

            const loadVal = document.getElementById('stat-load-val');
            if (loadVal) loadVal.innerText = `Load: ${data.cpu.load_avg.map(v => v.toFixed(2)).join(', ')}`;

            const m = data.memory.details;
            const ramVal = document.getElementById('stat-ram-val');
            if (ramVal) ramVal.innerText = m.percent.toFixed(1) + '%';

            const ramSub = document.getElementById('stat-ram-sub');
            if (ramSub) ramSub.innerText = `${formatBytes(m.used)} / ${formatBytes(m.total)}`;

            const root = data.storage.partitions.find(p => p.mountpoint === '/') || data.storage.partitions[0];
            const diskVal = document.getElementById('stat-disk-val');
            if (diskVal) diskVal.innerText = root.percent + '%';

            const diskSub = document.getElementById('stat-disk-sub');
            if (diskSub) diskSub.innerText = `${formatBytes(root.free)} Free`;

            // Uptime
            const upt = data.system.uptime;
            const h = Math.floor(upt / 3600);
            const min = Math.floor((upt % 3600) / 60);
            const uptVal = document.getElementById('uptime-val');
            if (uptVal) uptVal.innerText = `${h}h ${min}m`;

            // Network Calculation
            if (lastNetData) {
                const diffIn = (data.network.bytes_recv - lastNetData.bytes_recv) / 3; // 3s interval
                const diffOut = (data.network.bytes_sent - lastNetData.bytes_sent) / 3;

                const netVal = document.getElementById('stat-net-val');
                if (netVal) netVal.innerText = formatBytes(diffIn + diffOut) + '/s';

                const netSub = document.getElementById('stat-net-sub');
                if (netSub) netSub.innerText = `↓ ${formatBytes(diffIn)}/s | ↑ ${formatBytes(diffOut)}/s`;

                // Update net chart
                if (netChart) {
                    netChart.data.datasets[0].data.push(diffIn / 1024); // KB
                    netChart.data.datasets[0].data.shift();
                    netChart.data.datasets[1].data.push(diffOut / 1024);
                    netChart.data.datasets[1].data.shift();
                    netChart.update('none');
                }
            }
            lastNetData = data.network;

            // 2. Charts
            if (mainChart) {
                const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                mainChart.data.labels.push(now);
                mainChart.data.datasets[0].data.push(data.cpu.total);
                mainChart.data.datasets[1].data.push(data.memory.details.percent);

                if (mainChart.data.labels.length > 100) {
                    mainChart.data.labels.shift();
                    mainChart.data.datasets[0].data.shift();
                    mainChart.data.datasets[1].data.shift();
                }
                mainChart.update('none');
            }

            if (coresChart) {
                coresChart.data.labels = data.cpu.per_core.map((_, i) => 'Core ' + i);
                coresChart.data.datasets[0].data = data.cpu.per_core;
                coresChart.update('none');
            }

            // 3. Tables & Mounts
            renderProcesses(data.cpu.top_processes);
            renderMounts(data.storage.partitions);
        })
        .catch(err => console.error('Error updating metrics:', err));
}

function renderProcesses(procs) {
    const tbody = document.querySelector('#proc-table tbody');
    if (!tbody || !procs) return;

    tbody.innerHTML = procs.map(p => {
        const cpuColor = p.cpu_percent > 20 ? 'var(--cpu-color)' : (p.cpu_percent > 10 ? 'var(--disk-color)' : 'var(--ram-color)');
        return `
        <tr>
            <td><span class="pid-badge">#${p.pid}</span></td>
            <td>
                <div class="proc-name-cell">
                    <div class="proc-icon-box">
                        <i class="fa-solid fa-gear"></i>
                    </div>
                    <span class="proc-name-text">${escapeHtml(p.name)}</span>
                </div>
            </td>
            <td><span class="user-badge">${escapeHtml(p.username || 'root')}</span></td>
            <td>
                <div class="progress-mini">
                    <div class="progress-fill" style="width:${Math.min(100, p.cpu_percent * 4)}%; background:${cpuColor}"></div>
                </div>
                <span style="font-weight:600; color:#fff">${p.cpu_percent.toFixed(1)}%</span>
            </td>
            <td><span style="color:#e1e7ef; font-weight:500">${p.memory_mb.toFixed(1)} MB</span></td>
            <td>
                ${['owner', 'admin'].includes(window.userRole) ? `
                    <button class="btn-kill" onclick="killProc(${p.pid})" title="Terminate Process">
                        <i class="fa-solid fa-xmark"></i> Kill
                    </button>
                ` : '<span style="color:var(--text-dim)">-</span>'}
            </td>
        </tr>`;
    }).join('');
}

function renderMounts(parts) {
    const container = document.getElementById('mount-container');
    if (!container || !parts) return;

    container.innerHTML = parts.map(p => {
        const color = p.percent > 90 ? 'var(--cpu-color)' : (p.percent > 70 ? 'var(--disk-color)' : 'var(--ram-color)');
        return `
        <div class="mount-card glass">
            <div class="mount-info">
                <div class="mount-name">
                    <i class="fa-solid fa-hard-drive" style="color:${color}; margin-right:8px"></i>
                    ${escapeHtml(p.mountpoint)}
                </div>
                <div class="mount-usage" style="color:${color}; font-weight:700">${p.percent}%</div>
            </div>
            <div class="mount-progress-track">
                <div class="mount-progress-fill" style="width:${p.percent}%; background:${color}; box-shadow:0 0 12px ${color}55"></div>
            </div>
            <div class="mount-meta">
                <span>${formatBytes(p.used)} Terpakai</span>
                <span>${formatBytes(p.total)} Total</span>
            </div>
        </div>`;
    }).join('');
}

function switchTab(tab, btnElement) {
    document.querySelectorAll('.metric-section').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));

    const targetSection = document.getElementById('tab-' + tab);
    if (targetSection) targetSection.style.display = 'block';

    if (btnElement) {
        btnElement.classList.add('active');
    } else {
        const activeBtn = document.querySelector(`.tab-btn[data-tab="${tab}"]`);
        if (activeBtn) activeBtn.classList.add('active');
    }
}

function killProc(pid) {
    if (!confirm(`Hentikan paksa proses PID ${pid}?`)) return;
    fetch('/api/process/kill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid })
    }).then(r => r.json()).then(res => {
        if (res.success) {
            updateMetrics();
        } else {
            alert(res.error || 'Gagal menghentikan proses.');
        }
    }).catch(err => {
        console.error('Error killing process:', err);
        alert('Terjadi kesalahan saat mematikan proses.');
    });
}

function scanStorage() {
    const btn = document.getElementById('scan-btn');
    const resDiv = document.getElementById('scan-results');
    if (!btn || !resDiv) return;

    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Memindai...';
    btn.disabled = true;

    fetch('/api/storage/analyze').then(r => r.json()).then(data => {
        btn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Pindai Ulang';
        btn.disabled = false;
        resDiv.style.display = 'block';
        const tbody = document.querySelector('#scan-table tbody');
        if (tbody && data.files) {
            tbody.innerHTML = data.files.map(f => `
                <tr>
                    <td style="color:var(--disk-color); font-weight:600">${escapeHtml(f.size)}</td>
                    <td style="font-family:monospace; font-size:0.85rem; color:#e1e7ef">${escapeHtml(f.path)}</td>
                </tr>
            `).join('');
        }
    }).catch(err => {
        console.error('Error scanning storage:', err);
        btn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Pindai Ulang';
        btn.disabled = false;
        alert('Gagal melakukan analisa penyimpanan.');
    });
}

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

