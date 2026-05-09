document.addEventListener('DOMContentLoaded', () => {
    // Clock
    setInterval(updateClock, 1000);
    updateClock();

    // System Stats
    setInterval(updateStats, 2000);
    updateStats();

    // Host Info
    fetch('/api/system')
        .then(r => r.json())
        .then(data => {
            document.getElementById('hostname').textContent = data.node;
            document.getElementById('os-info').textContent = data.system + " " + data.release;
            document.getElementById('cpu-model').textContent = data.processor;
        });

    // Home Automation
    initHome();
});

function updateClock() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    const dateString = now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });

    document.getElementById('clock-time').textContent = timeString;
    document.getElementById('clock-date').textContent = dateString;
}

function updateGauge(id, percent, textOverride = null) {
    const circle = document.getElementById(`${id}-circle`);
    const text = document.getElementById(`${id}-text`);
    const detail = document.getElementById(`${id}-detail`);

    if (circle) circle.style.setProperty('--p', percent);
    if (text) text.textContent = `${Math.round(percent)}%`;
    if (textOverride && detail) detail.textContent = textOverride;
}

// Detail View Logic
const detailOverlay = document.getElementById('detail-view');
const detailTitle = document.getElementById('detail-title');
const detailContent = document.getElementById('detail-content');

// Attach Click Handlers
document.querySelector('.cpu-color').closest('.widget-card').onclick = () => openDetail('cpu');
document.querySelector('.ram-color').closest('.widget-card').onclick = () => openDetail('ram');
document.querySelector('.disk-color').closest('.widget-card').onclick = () => openDetail('disk');
document.querySelector('.net-color').closest('.widget-card').onclick = () => openDetail('network');

let detailInterval = null;
let lastNet = { sent: 0, recv: 0, time: 0 };

function openDetail(type) {
    detailOverlay.classList.remove('hidden');
    detailOverlay.style.display = 'flex'; // Ensure flex

    if (type === 'cpu') {
        detailTitle.textContent = 'CPU Usage';
        fetchProcesses('cpu');
        detailInterval = setInterval(() => fetchProcesses('cpu'), 3000);
    } else if (type === 'ram') {
        detailTitle.textContent = 'Memory Usage';
        fetchProcesses('mem'); // Re-use process list but sorted by mem
        detailInterval = setInterval(() => fetchProcesses('mem'), 3000);
    } else if (type === 'disk') {
        detailTitle.textContent = 'Storage Analysis';
        fetchDiskAnalysis();
        // No interval for disk as it is heavy
    } else if (type === 'network') {
        detailTitle.textContent = 'Network Interfaces';
        fetchNetworkDetails();
        // Static info mostly, no interval needed or maybe slow poll
    }
}

function refreshDetail() {
    const title = detailTitle.textContent;
    if (title === 'CPU Usage') fetchProcesses('cpu');
    else if (title === 'Memory Usage') fetchProcesses('mem');
    else if (title === 'Storage Analysis') fetchDiskAnalysis();
    else if (title === 'Network Interfaces') {
        if (typeof window.switchNetTab === 'function') {
            loadNetContent(); // Refresh current tab
        } else {
            fetchNetworkDetails();
        }
    }
}

function closeDetail() {
    detailOverlay.classList.add('hidden');
    setTimeout(() => detailOverlay.style.display = 'none', 300);
    if (detailInterval) clearInterval(detailInterval);
    detailContent.innerHTML = '<div style="text-align:center; padding: 2rem;">Loading...</div>';
}

// Sparkline Data
let cpuHistory = new Array(50).fill(0);
let ramHistory = new Array(50).fill(0);
let netHistory = new Array(60).fill(0);
// Helper to manage colors
function updateGauge(type, percent, subtext = "") {
    const circle = document.getElementById(type + '-circle');
    const text = document.getElementById(type + '-text');
    const detail = document.getElementById(type + '-detail');

    if (!circle) return;

    // Color Logic
    let colorVar = '';
    if (percent > 90) colorVar = '#ff7675'; // Red
    else if (percent > 70) colorVar = '#ffeaa7'; // Yellow
    else {
        // Default colors
        if (type === 'cpu') colorVar = 'var(--cpu-color)';
        if (type === 'ram') colorVar = 'var(--ram-color)';
        if (type === 'disk') colorVar = 'var(--disk-color)';
    }

    circle.style.setProperty('--active-color', colorVar);
    circle.style.setProperty('--p', percent);
    text.textContent = Math.round(percent) + '%';

    if (detail && subtext) detail.textContent = subtext;
}

function updateStats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            // CPU
            if (data.cpu) {
                updateGauge('cpu', data.cpu.percent);
                const elLoad = document.getElementById('cpu-load');
                if (elLoad) {
                    const l1 = Number(data.cpu.load_1).toFixed(2);
                    const l5 = Number(data.cpu.load_5).toFixed(2);
                    elLoad.textContent = `${l1} / ${l5}`;
                }
                const elTemp = document.getElementById('cpu-temp');
                if (elTemp) elTemp.textContent = `${data.cpu.temp}°C`;

                if (data.cpu.cores) {
                    const elCores = document.getElementById('cpu-cores');
                    if (elCores) elCores.textContent = data.cpu.cores;
                }

                cpuHistory.push(data.cpu.percent);
                if (cpuHistory.length > 50) cpuHistory.shift();
                drawSparkline('cpu-chart', cpuHistory);
            }

            // Memory
            if (data.memory) {
                let used = data.memory.used;
                let total = data.memory.total;

                // Handle string "1.2GB" vs number bytes
                if (typeof used === 'string') {
                    used = parseFloat(used).toFixed(1);
                    total = parseFloat(total).toFixed(1);
                } else {
                    used = (used / 1024 / 1024 / 1024).toFixed(1);
                    total = (total / 1024 / 1024 / 1024).toFixed(1);
                }

                updateGauge('ram', data.memory.percent, `${used} / ${total} GB`);

                ramHistory.push(data.memory.percent);
                if (ramHistory.length > 50) ramHistory.shift();
                drawSparkline('ram-chart', ramHistory);
            }

            // Disk
            if (data.disk) {
                updateGauge('disk', data.disk.percent, `Used: ${data.disk.used} GB`);
            }

            // Network Speed
            if (data.network) {
                const now = Date.now();
                if (lastNet.time !== 0 && data.network.sent !== undefined) {
                    const timeDiff = (now - lastNet.time) / 1000;
                    if (timeDiff > 0) {
                        const speedSent = (data.network.sent - lastNet.sent) / timeDiff;
                        const speedRecv = (data.network.recv - lastNet.recv) / timeDiff;

                        let u = speedSent > 0 ? speedSent : 0;
                        let d = speedRecv > 0 ? speedRecv : 0;

                        const elSent = document.getElementById('net-sent');
                        if (elSent) elSent.textContent = formatSpeed(u) + "/s";
                        const elRecv = document.getElementById('net-recv');
                        if (elRecv) elRecv.textContent = formatSpeed(d) + "/s";

                        netHistory.shift();
                        netHistory.push(u + d);
                        drawSparkline('net-chart', netHistory);
                    }
                }
                if (data.network.sent !== undefined) {
                    lastNet = { sent: data.network.sent, recv: data.network.recv, time: now };
                }

                // Total GB
                let totalBytes = 0;
                if (data.network.sent !== undefined) totalBytes = data.network.sent + data.network.recv;
                else if (data.network.interfaces) {
                    data.network.interfaces.forEach(iface => { totalBytes += iface.bytes_sent + iface.bytes_recv; });
                }
                let totalGB = (totalBytes / (1024 * 1024 * 1024)).toFixed(2);
                if (document.getElementById('net-total')) document.getElementById('net-total').textContent = `${totalGB} GB`;
            }

            // Power
            if (data.power) {
                const elKwh = document.getElementById('power-kwh');
                if (elKwh) elKwh.textContent = data.power.kwh;

                const elEst = document.getElementById('power-est');
                if (elEst) elEst.textContent = `Est. based on ${data.power.watts_est}W`;

                const elCost = document.getElementById('power-cost');
                if (elCost) {
                    let kwh = parseFloat(data.power.kwh);
                    let cost = kwh * 1444.70;
                    let costFormatted = cost.toLocaleString('id-ID', { maximumFractionDigits: 0 });
                    if (cost > 0 && cost < 1) costFormatted = "< 1";
                    elCost.textContent = `Rp ${costFormatted}`;
                }
            }

            // Uptime (Header)
            if (data.uptime !== undefined) {
                const sec = data.uptime;
                const d = Math.floor(sec / 86400);
                const h = Math.floor((sec % 86400) / 3600);
                const m = Math.floor((sec % 3600) / 60);
                const s = Math.floor(sec % 60);

                let str = "";
                if (d > 0) str += `${d}d `;
                if (h > 0 || d > 0) str += `${h}h `;
                str += `${m}m ${s}s`;

                const elem = document.getElementById('uptime-text');
                if (elem) elem.textContent = `Up: ${str}`;
            }
        })
        .catch(err => console.error("Stats fetch error:", err));
}

function drawSparkline(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.parentElement.clientWidth;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);
    ctx.beginPath();
    ctx.strokeStyle = '#55efc4';
    ctx.lineWidth = 2;

    const max = Math.max(...data, 1024 * 100); // 100KB min scale
    const step = width / (data.length - 1);

    data.forEach((val, i) => {
        const x = i * step;
        const y = height - (val / max * height);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();

    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.fillStyle = 'rgba(85, 239, 196, 0.1)';
    ctx.fill();
}

function formatSpeed(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// Network state
let currentNetTab = 'ip'; // 'ip' or 'ports'

function fetchNetworkDetails() {
    // Render tabs first
    const tabsHtml = `
        <div class="tab-container">
            <button class="tab-btn ${currentNetTab === 'ip' ? 'active' : ''}" onclick="switchNetTab('ip')">IP Addresses</button>
            <button class="tab-btn ${currentNetTab === 'ports' ? 'active' : ''}" onclick="switchNetTab('ports')">Open Ports</button>
        </div>
        <div id="net-content">Loading...</div>
    `;
    detailContent.innerHTML = tabsHtml;

    loadNetContent();
}

// Make globally accessible for onclick
window.switchNetTab = function (tab) {
    currentNetTab = tab;
    // Update buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    // Simple re-render for active class logic (a bit lazy but works)
    fetchNetworkDetails();
}

function loadNetContent() {
    const container = document.getElementById('net-content');
    container.innerHTML = '<div style="text-align:center; padding: 2rem;">Loading data...</div>';

    if (currentNetTab === 'ip') {
        fetch('/api/network-details')
            .then(r => r.json())
            .then(ifaces => {
                let html = `
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Interface</th>
                                <th>IP Address</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                ifaces.forEach(i => {
                    const statusColor = i.status === 'Up' ? '#a8ff78' : '#ff6b6b';
                    html += `
                        <tr>
                            <td style="font-weight:bold">${i.name}</td>
                            <td>${i.ip}</td>
                            <td><span style="color:${statusColor}">${i.status}</span></td>
                        </tr>
                    `;
                });
                html += '</tbody></table>';
                container.innerHTML = html;
            });
    } else {
        fetch('/api/network-ports')
            .then(r => r.json())
            .then(ports => {
                if (ports.error) {
                    container.innerHTML = `<p style="color:red">Error: ${ports.error}</p>`;
                    return;
                }
                let html = `
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Port</th>
                                <th>IP</th>
                                <th>Program</th>
                                <th>Path</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                ports.forEach(p => {
                    html += `
                        <tr>
                            <td style="color:var(--net-color); font-weight:bold">${p.port}</td>
                            <td>${p.ip}</td>
                            <td>${p.program || 'Unknown'}</td>
                            <td style="font-size:0.9rem; color: #888">${p.path || 'N/A'}</td>
                        </tr>
                    `;
                });
                html += '</tbody></table>';
                container.innerHTML = html;
            });
    }
}

function fetchProcesses(sortBy) {
    fetch('/api/processes')
        .then(r => r.json())
        .then(procs => {
            // Sort client side if needed
            if (sortBy === 'mem') {
                procs.sort((a, b) => b.mem_mb - a.mem_mb);
            }

            let html = `
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>PID</th>
                            <th>Name</th>
                            <th>User</th>
                            <th>CPU %</th>
                            <th>Memory (MB)</th>
                             ${['owner', 'admin'].includes(window.userRole) ? '<th>Action</th>' : ''}
                        </tr>
                    </thead>
                    <tbody>
            `;

            procs.forEach(p => {
                const cpuColor = p.cpu > 50 ? '#ff6b6b' : '#4ecdc4';
                html += `
                    <tr>
                        <td>${p.pid}</td>
                        <td>${p.name}</td>
                        <td>${p.user}</td>
                        <td>
                            <div style="display:flex; align-items:center; gap:0.5rem">
                                <span style="width:40px">${p.cpu.toFixed(1)}%</span>
                                <div class="usage-bar-bg"><div class="usage-bar-fill" style="width:${Math.min(p.cpu, 100)}%; background:${cpuColor}"></div></div>
                            </div>
                        </td>
                        <td>${p.mem_mb.toFixed(1)} MB</td>
                         ${['owner', 'admin'].includes(window.userRole) ? `<td><button onclick="killProc(${p.pid})" style="background:#ff4757; border:none; color:white; padding:2px 8px; border-radius:4px; cursor:pointer; font-size:0.8rem">Kill</button></td>` : ''}
                    </tr>
                `;
            });
            html += '</tbody></table>';
            detailContent.innerHTML = html;
        });
}

function killProc(pid) {
    if (!confirm('Force kill process ' + pid + '?')) return;
    fetch('/api/process/kill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid: pid })
    }).then(r => {
        if (r.ok) refreshDetail();
        else r.json().then(e => alert(e.error || 'Failed'));
    }).catch(e => alert('Failed to request kill'));
}

function fetchDiskAnalysis() {
    detailContent.innerHTML = '<div style="text-align:center; padding: 2rem;">Scanning disk... this may take a moment.</div>';
    fetch('/api/disk-analysis')
        .then(r => r.json())
        .then(data => {
            let html = `<div class="storage-section">`;

            html += `<h3>Log Directory (/var/log) Largest Items</h3>`;
            html += renderFileTable(data.logs);

            if (data.zram1 && data.zram1.path) {
                html += `<h3>ZRAM1 (${data.zram1.path}) Largest Items</h3>`;
                html += renderFileTable(data.zram1.data);
            } else {
                html += `<h3>ZRAM1</h3><p style="color:#aaa; font-style:italic">zram1 is not mounted as a folder.</p>`;
            }

            html += `</div>`;
            detailContent.innerHTML = html;
        });
}

function renderFileTable(items) {
    let html = `
        <table class="data-table">
            <thead>
                <tr>
                    <th>Size</th>
                    <th>Path</th>
                </tr>
            </thead>
            <tbody>
    `;
    items.forEach(item => {
        html += `
            <tr>
                <td style="color:var(--disk-color); font-weight:bold">${item.size}</td>
                <td>${item.path}</td>
            </tr>
        `;
    });
    html += '</tbody></table>';
    return html;
}

// --- HOME AUTOMATION LOGIC ---
let homeDevices = [];
let homeWidgetRendered = false;

function initHome() {
    fetch('/api/monitoring/config')
        .then(r => r.json())
        .then(settings => {
            if (settings.mqtt && settings.mqtt.enabled && settings.mqtt.devices) {
                homeDevices = settings.mqtt.devices;
                const widget = document.getElementById('home-widget-card');
                if (widget) {
                    widget.style.display = 'block';
                    renderHomeWidget();
                    updateHomeStatus();
                    setInterval(updateHomeStatus, 3000);
                }
            }
        });
}

function renderHomeWidget() {
    const container = document.getElementById('home-widget-content');
    if (!container) return;

    container.innerHTML = homeDevices.map(dev => {
        if (dev.type === 'sensor') {
            return `
            <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.05); padding:0.5rem; border-radius:6px">
                <div style="display:flex; align-items:center; gap:0.5rem">
                    <i class="fa-solid ${dev.icon || 'fa-thermometer-half'}" style="color:#58a6ff"></i>
                    <span style="font-size:0.85rem">${dev.name}</span>
                </div>
                <div style="font-weight:bold; font-size:0.9rem">
                    <span id="dev-val-${dev.id}">--</span> <span style="font-size:0.7rem; color:#aaa">${dev.unit || ''}</span>
                </div>
            </div>`;
        } else if (dev.type === 'switch') {
            return `
            <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.05); padding:0.5rem; border-radius:6px">
                <div style="display:flex; align-items:center; gap:0.5rem">
                    <i class="fa-solid ${dev.icon || 'fa-lightbulb'}" id="dev-icon-${dev.id}" style="color:#aaa"></i>
                    <span style="font-size:0.85rem">${dev.name}</span>
                </div>
                <div class="toggle" id="dev-toggle-${dev.id}" onclick="toggleDevice('${dev.id}')" style="transform:scale(0.8)"></div>
            </div>`;
        }
    }).join('');
    homeWidgetRendered = true;
}

function updateHomeStatus() {
    if (!homeWidgetRendered) return;

    fetch('/api/home/status')
        .then(r => r.json())
        .then(data => {
            homeDevices.forEach(dev => {
                const state = data[dev.id];
                if (!state) return;

                const val = state.value;
                if (dev.type === 'sensor') {
                    const el = document.getElementById(`dev-val-${dev.id}`);
                    if (el) el.textContent = val;
                } else if (dev.type === 'switch') {
                    const isOn = val === (dev.payload_on || 'ON');
                    const toggle = document.getElementById(`dev-toggle-${dev.id}`);
                    const icon = document.getElementById(`dev-icon-${dev.id}`);
                    if (toggle) toggle.classList.toggle('on', isOn);
                    if (icon) icon.style.color = isOn ? '#f1c40f' : '#aaa';
                }
            });
        });
}

function toggleDevice(id) {
    const dev = homeDevices.find(d => d.id === id);
    if (!dev) return;

    const toggle = document.getElementById(`dev-toggle-${id}`);
    const newState = !toggle.classList.contains('on');

    fetch('/api/home/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: id, state: newState })
    });
}

function logout() {
    const modal = document.getElementById('logout-modal');
    if (modal) modal.classList.add('active');
    // Fallback if modal html missing
    else if (confirm('Are you sure you want to logout?')) confirmLogout();
}

function closeLogoutModal() {
    const modal = document.getElementById('logout-modal');
    if (modal) modal.classList.remove('active');
}

function confirmLogout() {
    fetch('/api/auth/logout', { method: 'POST' })
        .then(() => window.location.href = '/')
        .catch(() => window.location.href = '/');
}

// --- DASHBOARD APPS & DND ---
function loadDashboardApps() {
    const grid = document.getElementById('apps-grid');
    if (!grid) return; // Not on dashboard page or grid missing

    fetch('/api/dashboard/apps')
        .then(r => r.json())
        .then(data => {
            if (data.items) {
                renderDashboardApps(data.items);
            }
        })
        .catch(console.error);
}

function renderDashboardApps(apps) {
    const grid = document.getElementById('apps-grid');
    grid.innerHTML = apps.map(app => `
        <div class="app-item glass" draggable="true" data-id="${app.id}" onclick="handleAppClick(event, '${app.url}')">
            <div class="app-icon" style="background: ${app.color};">
                ${app.icon.startsWith('/') ? `<img src="${app.icon}" style="width:32px;height:32px;filter:brightness(0) invert(1)">` : `<i class="${app.icon.startsWith('fa') ? app.icon : 'fa-solid fa-' + app.icon}"></i>`}
            </div>
            <span class="app-name">${app.name}</span>
        </div>
    `).join('');

    // Attach DnD Handlers
    const items = grid.querySelectorAll('.app-item');
    items.forEach(item => {
        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragenter', handleDragEnter);
        item.addEventListener('dragover', handleDragOver);
        item.addEventListener('dragleave', handleDragLeave);
        item.addEventListener('drop', handleDrop);
        item.addEventListener('dragend', handleDragEnd);
    });
}

function handleAppClick(e, url) {
    if (isDragging) return;
    if (url && url !== '#') {
        if (url.startsWith('/')) window.location.href = url;
        else window.open(url, '_blank');
    }
}

let dragSrcEl = null;
let isDragging = false;

function handleDragStart(e) {
    dragSrcEl = this;
    // Delay setting isDragging slightly to allow click detection
    setTimeout(() => isDragging = true, 100);

    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', this.innerHTML);
    this.classList.add('dragging');
}

function handleDragOver(e) {
    if (e.preventDefault) e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDragEnter(e) {
    this.classList.add('over');
}

function handleDragLeave(e) {
    this.classList.remove('over');
}

function handleDrop(e) {
    if (e.stopPropagation) e.stopPropagation();

    if (dragSrcEl !== this) {
        const grid = document.getElementById('apps-grid');
        const children = Array.from(grid.children);
        const srcIndex = children.indexOf(dragSrcEl);
        const dstIndex = children.indexOf(this);

        if (srcIndex < dstIndex) {
            this.after(dragSrcEl);
        } else {
            this.before(dragSrcEl);
        }
        saveDashboardLayout();
    }
    return false;
}

function handleDragEnd(e) {
    // Reset dragging state after a small delay to prevent click trigger
    setTimeout(() => isDragging = false, 100);
    this.classList.remove('dragging');
    document.querySelectorAll('.app-item').forEach(item => item.classList.remove('over'));
}

function saveDashboardLayout() {
    const grid = document.getElementById('apps-grid');
    const ids = Array.from(grid.children).map(el => el.getAttribute('data-id'));

    fetch('/api/dashboard/layout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order: ids })
    }).catch(console.error);
}

// Web Monitor Update Function
async function updateWebMonitor() {
    try {
        const res = await fetch('/api/web_monitor/status');
        const reqsEl = document.getElementById('web-reqs');
        const ipsEl = document.getElementById('web-ips');
        const iconEl = document.getElementById('web-status-icon');
        const domainEl = document.getElementById('web-domain');

        if (res.status === 400) {
            const data = await res.json();
            if (data.error === "not_configured") {
                if (domainEl) domainEl.textContent = 'Not Configured';
                if (reqsEl) reqsEl.textContent = '-';
                if (ipsEl) ipsEl.textContent = '-';
                if (iconEl) {
                    iconEl.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i>';
                    iconEl.style.color = '#f59e0b';
                }
                return;
            }
        }

        const data = await res.json();
        
        if (reqsEl && ipsEl) {
            reqsEl.textContent = data.today_requests || 0;
            ipsEl.textContent = data.unique_ips || 0;
            
            if (data.is_online) {
                iconEl.innerHTML = '<i class="fa-solid fa-circle-check"></i>';
                iconEl.style.color = '#14b8a6'; // Greenish
            } else {
                iconEl.innerHTML = '<i class="fa-solid fa-circle-xmark"></i>';
                iconEl.style.color = '#ff6b6b'; // Red
            }
        }
    } catch (err) {
        console.error("Failed to update Web Monitor:", err);
    }
}

// Add init logic
document.addEventListener('DOMContentLoaded', () => {
    loadDashboardApps();
    updateWebMonitor();
    setInterval(updateWebMonitor, 10000); // Polling every 10s
});

