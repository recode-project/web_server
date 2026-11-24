/**
 * ==========================================================================
 * EKA DASHBOARD — APP STORE CONTROLLER (ZERO INLINE JS)
 * Universal Self-Hosted Docker Catalog, Lifecycle Manager & Realtime Logs
 * ==========================================================================
 */

window.userRole = (document.body && document.body.dataset.userRole) || 'readonly';

const FALLBACK_ICON = '/static/icon.svg';
let allApps = [];
let currentApp = null;
let managedAppId = null;
let installedApps = {};
let dockerAvailable = true;
let currentCategory = 'All';
let isMinimized = false;

const socket = typeof io === 'function' ? io() : null;

document.addEventListener('DOMContentLoaded', () => {
    const canManage = (window.userRole === 'owner' || window.userRole === 'admin');
    if (!canManage) {
        const customBtn = document.getElementById('btn-custom-app');
        if (customBtn) customBtn.style.display = 'none';
    }
    document.addEventListener('keydown', (ev) => {
        if (ev.key === 'Escape') {
            closeModal();
            closeManageModal();
        }
    });
    ['install-modal', 'manage-modal'].forEach(id => {
        const overlay = document.getElementById(id);
        if (!overlay) return;
        overlay.addEventListener('click', (ev) => {
            if (ev.target === overlay) {
                if (id === 'install-modal') closeModal();
                if (id === 'manage-modal') closeManageModal();
            }
        });
    });
    bindSocketHandlers();
    refreshStore();
});

function escapeStoreHtml(str) {
    return String(str === undefined || str === null ? '' : str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function showToast(msg, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icon = type === 'success' ? 'check-circle' : 'exclamation-circle';
    const color = type === 'success' ? '#34d399' : '#f87171';
    toast.innerHTML = `
        <i class="fa-solid fa-${icon}" style="color:${color}"></i>
        <div style="flex:1">${escapeStoreHtml(msg)}</div>
        <button onclick="this.parentElement.remove()" style="background:none; border:none; color:#94a3b8; cursor:pointer; font-size:1rem">&times;</button>
    `;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

function refreshStore() {
    loadInstalledApps().then(loadApps);
}

function loadInstalledApps() {
    return fetch('/api/store/installed')
        .then(r => r.json())
        .then(data => {
            installedApps = {};
            dockerAvailable = data.docker_available !== false;
            const warnBanner = document.getElementById('docker-warning-banner');
            if (warnBanner) {
                warnBanner.style.display = dockerAvailable ? 'none' : 'flex';
            }
            if (Array.isArray(data.installed)) {
                data.installed.forEach(item => {
                    if (typeof item === 'string') {
                        installedApps[item] = { running: true };
                    } else if (item && item.id) {
                        installedApps[item.id] = item;
                    }
                });
            }
        })
        .catch(err => {
            console.error('Failed loading installed apps:', err);
        });
}

function loadApps() {
    const grid = document.getElementById('apps-grid');
    if (grid) {
        grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:3rem; color:#94a3b8"><i class="fa-solid fa-spinner fa-spin fa-2x"></i></div>';
    }

    fetch('/api/store/catalog')
        .then(r => r.json())
        .then(data => {
            allApps = Array.isArray(data.catalog) ? data.catalog : [];
            updateStoreStats();
            renderCategories();
            applyFilters();
        })
        .catch(() => {
            if (grid) grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:2rem; color:#f87171">Gagal memuat katalog aplikasi</div>';
            showToast('Gagal memuat katalog', 'error');
        });
}

function updateStoreStats() {
    const meta = document.getElementById('store-stats-pill');
    if (!meta) return;
    const installedCount = Object.keys(installedApps).length;
    meta.textContent = `${allApps.length} aplikasi / ${installedCount} terpasang`;
}

function renderCategories() {
    const counts = {};
    allApps.forEach(a => {
        const cat = a.category || 'Other';
        counts[cat] = (counts[cat] || 0) + 1;
    });
    const categories = ['All', ...Object.keys(counts)];
    const container = document.getElementById('categories');
    if (!container) return;

    container.innerHTML = categories.map(cat => {
        const count = cat === 'All' ? allApps.length : counts[cat];
        const safeCat = escapeStoreHtml(cat);
        return `
            <button type="button" class="category-tab ${cat === currentCategory ? 'active' : ''}" onclick="filterCategory('${safeCat}', this)">
                <span>${safeCat}</span>
                <span class="tab-count">${count}</span>
            </button>
        `;
    }).join('');
}

function filterCategory(cat, el) {
    currentCategory = cat;
    document.querySelectorAll('.category-tab').forEach(p => p.classList.remove('active'));
    if (el) el.classList.add('active');
    applyFilters();
}

function applyFilters() {
    const searchEl = document.getElementById('app-search');
    const statusEl = document.getElementById('status-filter');
    const search = (searchEl ? searchEl.value : '').trim().toLowerCase();
    const statusFilter = statusEl ? statusEl.value : 'all';

    const filtered = allApps.filter(app => {
        if (currentCategory !== 'All' && app.category !== currentCategory) return false;
        if (search) {
            const hay = `${app.name || ''} ${app.description || ''} ${app.category || ''} ${app.image || ''}`.toLowerCase();
            if (!hay.includes(search)) return false;
        }
        const isInstalled = !!installedApps[app.id];
        if (statusFilter === 'installed' && !isInstalled) return false;
        if (statusFilter === 'not_installed' && isInstalled) return false;
        return true;
    });

    renderApps(filtered);
}

function renderApps(apps) {
    const container = document.getElementById('apps-grid');
    if (!container) return;
    if (apps.length === 0) {
        container.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:2.5rem; color:#94a3b8">Tidak ada aplikasi sesuai filter.</div>';
        return;
    }

    const canManage = (window.userRole === 'owner' || window.userRole === 'admin');

    container.innerHTML = apps.map(app => {
        const info = installedApps[app.id];
        const isInstalled = !!info;
        const isRunning = !!(info && info.running);
        const isNative = !!(info && info.is_native);
        const openPort = info && info.open_port;
        const safeId = escapeStoreHtml(app.id);
        const safeIcon = escapeStoreHtml(app.icon || FALLBACK_ICON);

        let buttons = '';
        if (isInstalled) {
            if (canManage && !isNative) {
                buttons += `<button class="btn" onclick="openManageModal('${safeId}')"><i class="fa-solid fa-sliders"></i> Manage</button>`;
            } else if (isNative) {
                buttons += '<span class="host-service-label"><i class="fa-solid fa-server"></i> Host Service</span>';
            }
            if (isRunning && openPort) {
                buttons += `<button class="btn btn-install" onclick="openApp('${safeId}')"><i class="fa-solid fa-arrow-up-right-from-square"></i> Open</button>`;
            }
        } else if (canManage) {
            const disabledAttr = dockerAvailable ? '' : 'disabled style="opacity:0.5; cursor:not-allowed" title="Docker Engine unavailable"';
            buttons += `<button class="btn btn-install" onclick="openInstallModal('${safeId}')" ${disabledAttr}><i class="fa-solid fa-download"></i> Install</button>`;
        }

        let metaText = app.image || '';
        let metaClass = '';
        if (isInstalled) {
            const targetName = isNative ? 'host service' : (info.container_name || app.id);
            const portSuffix = openPort ? ` :${openPort}` : '';
            if (isRunning) {
                metaText = `${targetName}${portSuffix}`;
                metaClass = ' is-running';
            } else {
                metaText = `stopped / ${targetName}`;
                metaClass = ' is-stopped';
            }
        }

        return `
            <div class="app-card" id="card-${safeId}">
                <div class="app-header">
                    <img src="${safeIcon}" alt="" class="app-icon" loading="lazy" onerror="this.onerror=null;this.src='${FALLBACK_ICON}'">
                    <div class="app-info">
                        <div class="app-name" title="${escapeStoreHtml(app.name)}">${escapeStoreHtml(app.name)}</div>
                        <div class="app-cat">${escapeStoreHtml(app.category)}</div>
                    </div>
                </div>
                <div class="app-desc">${escapeStoreHtml(app.description)}</div>
                <div class="app-meta-row${metaClass}" title="${escapeStoreHtml(metaText)}">${escapeStoreHtml(metaText)}</div>
                <div class="app-footer">${buttons}</div>
                <div class="loading-overlay" id="loading-${safeId}">
                    <div class="spinner"></div>
                    <div style="color:#fff; font-size:0.85rem">Processing...</div>
                </div>
            </div>
        `;
    }).join('');
}

function openApp(appId) {
    const info = installedApps[appId];
    const port = info && info.open_port;
    const proto = (info && info.open_protocol) || 'http';
    if (port) {
        window.open(`${proto}://${window.location.hostname}:${port}`, '_blank', 'noopener');
    } else {
        showToast('Aplikasi ini tidak memiliki Web UI HTTP.', 'error');
    }
}

// ===== MANAGE APP MODAL (START / STOP / RESTART / LOGS / UNINSTALL) =====
function openManageModal(appId) {
    const app = allApps.find(a => a.id === appId);
    const info = installedApps[appId];
    if (!app || !info) return;

    managedAppId = appId;
    const iconEl = document.getElementById('manage-icon');
    if (iconEl) {
        iconEl.src = app.icon || FALLBACK_ICON;
        iconEl.onerror = () => { iconEl.src = FALLBACK_ICON; };
    }
    document.getElementById('manage-app-name').textContent = app.name;
    const originTag = info.is_external ? 'External / Compose' : 'App Store Managed';
    document.getElementById('manage-app-meta').textContent = `${info.container_name || app.id} • ${info.running ? 'RUNNING' : 'STOPPED'} • ${originTag}`;

    const portsRow = document.getElementById('manage-ports-row');
    if (portsRow) {
        const ports = Array.isArray(info.ports) ? info.ports : [];
        portsRow.innerHTML = ports.length > 0
            ? ports.map(p => `<span class="port-chip"><i class="fa-solid fa-plug"></i> ${escapeStoreHtml(p.host)} -&gt; ${escapeStoreHtml(p.container)}/${escapeStoreHtml(p.protocol)}</span>`).join('')
            : '<span style="font-size:0.78rem; color:#94a3b8">No mapped host ports (host network or internal)</span>';
    }

    const startBtn = document.getElementById('btn-manage-start');
    const stopBtn = document.getElementById('btn-manage-stop');
    const openBtn = document.getElementById('btn-manage-open');
    if (startBtn) startBtn.style.display = info.running ? 'none' : 'inline-flex';
    if (stopBtn) stopBtn.style.display = info.running ? 'inline-flex' : 'none';
    if (openBtn) openBtn.style.display = (info.running && info.open_port) ? 'inline-flex' : 'none';

    document.getElementById('manage-modal').style.display = 'flex';
    loadManageLogs();
}

function closeManageModal() {
    document.getElementById('manage-modal').style.display = 'none';
    managedAppId = null;
}

function openManagedApp() {
    if (managedAppId) openApp(managedAppId);
}

function loadManageLogs() {
    if (!managedAppId) return;
    const box = document.getElementById('manage-logs-box');
    if (!box) return;
    box.textContent = 'Memuat log kontainer...';
    fetch(`/api/store/logs/${encodeURIComponent(managedAppId)}?tail=150`)
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                box.textContent = data.logs && data.logs.trim() ? data.logs : '(Belum ada output log)';
                box.scrollTop = box.scrollHeight;
            } else {
                box.textContent = `Gagal memuat log: ${data.error || 'Unknown error'}`;
            }
        })
        .catch(err => {
            box.textContent = `Network error: ${err.message}`;
        });
}

function runManageAction(action) {
    if (!managedAppId) return;
    const appId = managedAppId;
    const info = installedApps[appId] || {};
    if (action === 'uninstall') {
        const cname = info.container_name || appId;
        const msg = info.is_external
            ? `PERINGATAN: Kontainer "${cname}" terdeteksi sebagai kontainer eksternal/Docker Compose. Hapus kontainer ini? (Volume data tetap tersimpan)`
            : `Uninstall ${appId} (${cname})? Kontainer akan dihapus (volume data tetap tersimpan).`;
        if (!confirm(msg)) return;
    }

    const loading = document.getElementById(`loading-${appId}`);
    if (loading) loading.style.display = 'flex';

    fetch('/api/store/manage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ app_id: appId, action: action })
    })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'error');
            } else {
                showToast(`Berhasil ${action} ${appId}`, 'success');
                closeManageModal();
                setTimeout(() => {
                    loadInstalledApps().then(() => {
                        updateStoreStats();
                        applyFilters();
                    });
                }, 700);
            }
        })
        .catch(err => {
            showToast(`Error: ${err.message}`, 'error');
        })
        .finally(() => {
            if (loading) loading.style.display = 'none';
        });
}

// ===== INSTALL & CUSTOM APP MODALS =====
function openInstallModal(appId) {
    if (!dockerAvailable) {
        showToast('Docker Engine tidak aktif di server ini.', 'error');
        return;
    }
    currentApp = allApps.find(a => a.id === appId);
    if (!currentApp) return;

    document.getElementById('modal-app-name').textContent = currentApp.name;
    document.getElementById('modal-app-image').textContent = currentApp.image;
    const iconEl = document.getElementById('modal-icon');
    iconEl.src = currentApp.icon || FALLBACK_ICON;
    iconEl.onerror = () => { iconEl.src = FALLBACK_ICON; };

    const portsHtml = (currentApp.ports || []).map((p, i) => `
        <div class="form-row">
            <div class="form-control">
                <label>Host Port (${escapeStoreHtml(p.description || 'Port')})</label>
                <input type="number" id="port-host-${i}" value="${escapeStoreHtml(p.host)}" min="1" max="65535">
                <div class="desc">Port akses di server host</div>
            </div>
            <div class="form-control">
                <label>Container Port (${escapeStoreHtml(p.protocol || 'tcp')})</label>
                <input type="text" value="${escapeStoreHtml(p.container)}" disabled style="opacity:0.55; cursor:not-allowed">
                <input type="hidden" id="port-container-${i}" value="${escapeStoreHtml(p.container)}">
                <input type="hidden" id="port-proto-${i}" value="${escapeStoreHtml(p.protocol || 'tcp')}">
            </div>
        </div>
    `).join('');

    const volHtml = (currentApp.volumes || []).map((v, i) => `
        <div class="form-control" style="margin-bottom:0.85rem">
            <label>Volume / Host Path (${escapeStoreHtml(v.description || 'Storage')})</label>
            <input type="text" id="vol-host-${i}" value="${escapeStoreHtml(v.bind)}">
            <div class="desc">Container: ${escapeStoreHtml(v.container)} (Gunakan nama volume Docker atau path host absolut)</div>
            <input type="hidden" id="vol-container-${i}" value="${escapeStoreHtml(v.container)}">
        </div>
    `).join('');

    const envHtml = (currentApp.env || []).map((e, i) => `
        <div class="form-control" style="margin-bottom:0.85rem">
            <label>${escapeStoreHtml(e.key)}</label>
            <input type="text" id="env-val-${i}" value="${escapeStoreHtml(e.value)}">
            <input type="hidden" id="env-key-${i}" value="${escapeStoreHtml(e.key)}">
        </div>
    `).join('');

    document.getElementById('modal-body').innerHTML = `
        <div class="config-group">
            <h4><i class="fa-solid fa-network-wired" style="color:#38bdf8"></i> Network Ports (${escapeStoreHtml(currentApp.network_mode || 'bridge')})</h4>
            <div id="config-ports">${portsHtml || '<div style="color:#94a3b8; font-style:italic; font-size:0.82rem">Tidak ada port mapping (mode host atau internal)</div>'}</div>
        </div>
        <div class="config-group">
            <h4><i class="fa-solid fa-folder-open" style="color:#fbbf24"></i> Volumes (Persistent Storage)</h4>
            <div id="config-volumes">${volHtml || '<div style="color:#94a3b8; font-style:italic; font-size:0.82rem">Tidak ada volume persistent</div>'}</div>
        </div>
        <div class="config-group">
            <h4><i class="fa-solid fa-list" style="color:#34d399"></i> Environment Variables</h4>
            <div id="config-env">${envHtml || '<div style="color:#94a3b8; font-style:italic; font-size:0.82rem">Tidak ada environment variables</div>'}</div>
        </div>
    `;

    document.getElementById('install-modal').style.display = 'flex';
}

function openCustomInstallModal() {
    if (!dockerAvailable) {
        showToast('Docker Engine tidak aktif di server ini.', 'error');
        return;
    }
    currentApp = { id: 'custom' };
    document.getElementById('modal-app-name').textContent = 'Install Custom App';
    document.getElementById('modal-app-image').textContent = 'Custom Docker Container';
    document.getElementById('modal-icon').src = FALLBACK_ICON;

    document.getElementById('modal-body').innerHTML = `
        <div class="form-row" style="margin-bottom:1rem">
            <div class="form-control">
                <label>App Name <span style="color:#f87171">*</span></label>
                <input type="text" id="custom-app-name" placeholder="e.g. My Service">
            </div>
            <div class="form-control">
                <label>Docker Image <span style="color:#f87171">*</span></label>
                <input type="text" id="custom-app-image" placeholder="e.g. nginx:alpine">
            </div>
        </div>
        <div class="form-control" style="margin-bottom:1.25rem">
            <label>Network Mode</label>
            <select id="custom-net-mode">
                <option value="bridge">Bridge (Default - Recommended)</option>
                <option value="host">Host (Direct network stack)</option>
                <option value="none">None</option>
            </select>
        </div>

        <div class="config-section-custom">
            <div class="section-header-custom">
                <div class="title"><i class="fa-solid fa-network-wired"></i> Ports</div>
                <button class="btn-sm-add" onclick="addCustomPort()"><i class="fa-solid fa-plus"></i> Add Port</button>
            </div>
            <div class="section-hint">Petakan port host ke container port.</div>
            <div id="custom-ports-container" class="items-container">
                <div class="empty-state">Tidak ada port ditambahkan</div>
            </div>
        </div>

        <div class="config-section-custom">
            <div class="section-header-custom">
                <div class="title"><i class="fa-solid fa-folder-open"></i> Volumes</div>
                <button class="btn-sm-add" onclick="addCustomVol()"><i class="fa-solid fa-plus"></i> Add Volume</button>
            </div>
            <div class="section-hint">Gunakan nama Docker volume (contoh: myapp_data) atau path host absolut.</div>
            <div id="custom-vols-container" class="items-container">
                <div class="empty-state">Tidak ada volume ditambahkan</div>
            </div>
        </div>

        <div class="config-section-custom">
            <div class="section-header-custom">
                <div class="title"><i class="fa-solid fa-list"></i> Environment Variables</div>
                <button class="btn-sm-add" onclick="addCustomEnv()"><i class="fa-solid fa-plus"></i> Add Variable</button>
            </div>
            <div class="section-hint">Konfigurasi variabel lingkungan (TZ, PUID, dll.).</div>
            <div id="custom-env-container" class="items-container">
                <div class="empty-state">Tidak ada environment var ditambahkan</div>
            </div>
        </div>
    `;

    document.getElementById('install-modal').style.display = 'flex';
}

function clearEmptyState(containerId) {
    const container = document.getElementById(containerId);
    const empty = container && container.querySelector('.empty-state');
    if (empty) empty.remove();
}

function addCustomPort() {
    clearEmptyState('custom-ports-container');
    const div = document.createElement('div');
    div.className = 'custom-row-item';
    div.innerHTML = `
        <div class="form-control" style="flex:1">
            <label>Host Port</label>
            <input type="number" placeholder="8080" class="custom-port-host">
        </div>
        <div class="form-control" style="flex:1">
            <label>Container Port</label>
            <input type="number" placeholder="80" class="custom-port-container">
        </div>
        <button onclick="this.closest('.custom-row-item').remove()" class="btn-remove" title="Hapus"><i class="fa-solid fa-trash"></i></button>
    `;
    document.getElementById('custom-ports-container').appendChild(div);
}

function addCustomVol() {
    clearEmptyState('custom-vols-container');
    const div = document.createElement('div');
    div.className = 'custom-row-item';
    div.innerHTML = `
        <div class="form-control" style="flex:1">
            <label>Volume / Host Path</label>
            <input type="text" placeholder="myapp_data or /srv/myapp" class="custom-vol-host">
        </div>
        <div class="form-control" style="flex:1">
            <label>Container Path</label>
            <input type="text" placeholder="/config" class="custom-vol-container">
        </div>
        <button onclick="this.closest('.custom-row-item').remove()" class="btn-remove" title="Hapus"><i class="fa-solid fa-trash"></i></button>
    `;
    document.getElementById('custom-vols-container').appendChild(div);
}

function addCustomEnv() {
    clearEmptyState('custom-env-container');
    const div = document.createElement('div');
    div.className = 'custom-row-item';
    div.innerHTML = `
        <div class="form-control" style="flex:1">
            <label>Key</label>
            <input type="text" placeholder="TZ" class="custom-env-key">
        </div>
        <div class="form-control" style="flex:1">
            <label>Value</label>
            <input type="text" placeholder="UTC" class="custom-env-val">
        </div>
        <button onclick="this.closest('.custom-row-item').remove()" class="btn-remove" title="Hapus"><i class="fa-solid fa-trash"></i></button>
    `;
    document.getElementById('custom-env-container').appendChild(div);
}

function closeModal() {
    document.getElementById('install-modal').style.display = 'none';
    currentApp = null;
}

function confirmInstall() {
    if (!currentApp) return;
    const appId = currentApp.id;
    const payload = { app_id: appId };

    if (appId === 'custom') {
        const name = (document.getElementById('custom-app-name').value || '').trim();
        const image = (document.getElementById('custom-app-image').value || '').trim();
        const net = document.getElementById('custom-net-mode').value || 'bridge';

        if (!name || !image) {
            showToast('Nama aplikasi dan Docker image wajib diisi.', 'error');
            return;
        }

        const ports = Array.from(document.querySelectorAll('#custom-ports-container .custom-row-item')).map(row => {
            const h = row.querySelector('.custom-port-host');
            const c = row.querySelector('.custom-port-container');
            return (h && c && h.value && c.value) ? { host: h.value, container: c.value, protocol: 'tcp' } : null;
        }).filter(Boolean);

        const vols = Array.from(document.querySelectorAll('#custom-vols-container .custom-row-item')).map(row => {
            const h = row.querySelector('.custom-vol-host');
            const c = row.querySelector('.custom-vol-container');
            return (h && c && h.value && c.value) ? { bind: h.value, container: c.value } : null;
        }).filter(Boolean);

        const envs = Array.from(document.querySelectorAll('#custom-env-container .custom-row-item')).map(row => {
            const k = row.querySelector('.custom-env-key');
            const v = row.querySelector('.custom-env-val');
            return (k && v && k.value) ? { key: k.value, value: v.value } : null;
        }).filter(Boolean);

        payload.config = { name, image, network_mode: net, ports, volumes: vols, env: envs };
    } else {
        const customPorts = (currentApp.ports || []).map((p, i) => ({
            host: document.getElementById(`port-host-${i}`).value,
            container: document.getElementById(`port-container-${i}`).value,
            protocol: document.getElementById(`port-proto-${i}`).value
        }));

        const customVols = (currentApp.volumes || []).map((v, i) => ({
            bind: document.getElementById(`vol-host-${i}`).value,
            container: document.getElementById(`vol-container-${i}`).value
        }));

        const customEnv = (currentApp.env || []).map((e, i) => ({
            key: document.getElementById(`env-key-${i}`).value,
            value: document.getElementById(`env-val-${i}`).value
        }));

        payload.config = {
            ports: customPorts,
            volumes: customVols,
            env: customEnv,
            network_mode: currentApp.network_mode || 'bridge'
        };
    }

    closeModal();
    resetLogModal();
    document.getElementById('log-modal').style.display = 'flex';

    fetch('/api/store/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                appendLog('Request Error: ' + data.error, 'error');
            } else {
                appendLog('Request diterima. Memulai proses instalasi...', 'success');
            }
        })
        .catch(err => {
            appendLog('Network Error: ' + err.message, 'error');
        });
}

// ===== REALTIME SOCKET.IO LOG MODAL =====
function bindSocketHandlers() {
    if (!socket) return;
    socket.on('install_log', data => {
        appendLog(data.message, data.type);
    });
    socket.on('install_progress', data => {
        updateProgress(Math.round(data.percent || 0), data.message);
    });
    socket.on('install_complete', data => {
        const footer = document.getElementById('log-footer');
        const btnOpen = document.getElementById('btn-open-app');
        if (footer) footer.style.display = 'flex';

        if (data.status === 'success') {
            updateProgress(100, 'Installation Complete');
            appendLog('[OK] INSTALLATION COMPLETE', 'success');
            if (btnOpen) btnOpen.style.display = 'inline-flex';
            updateMiniWidget('Installed', 'Click to refresh', false);
            document.getElementById('minimized-install-widget').style.borderColor = 'rgba(16, 185, 129, 0.5)';
        } else {
            updateProgress(100, 'Installation Failed');
            document.getElementById('install-progress-bar').style.backgroundColor = '#ef4444';
            appendLog('[FAILED] INSTALLATION FAILED', 'error');
            updateMiniWidget('Failed', 'Check logs', false);
            document.getElementById('minimized-install-widget').style.borderColor = 'rgba(239, 68, 68, 0.5)';
        }
    });
}

function resetLogModal() {
    document.getElementById('log-container').innerHTML = '';
    document.getElementById('install-progress-bar').style.width = '0%';
    document.getElementById('install-progress-bar').style.backgroundColor = '#10b981';
    document.getElementById('progress-text').innerText = 'Starting...';
    document.getElementById('progress-percent').innerText = '0%';
    document.getElementById('log-footer').style.display = 'none';
    document.getElementById('btn-open-app').style.display = 'none';
}

function appendLog(msg, type = 'info') {
    const container = document.getElementById('log-container');
    if (!container) return;
    const div = document.createElement('div');
    div.style.marginBottom = '5px';
    div.style.lineHeight = '1.45';

    if (type === 'error') div.style.color = '#f87171';
    else if (type === 'success') div.style.color = '#34d399';
    else if (type === 'warning') div.style.color = '#fbbf24';
    else if (type === 'dim') div.style.color = '#64748b';

    const time = new Date().toLocaleTimeString();
    div.innerHTML = `<span style="color:#64748b; margin-right:8px">[${time}]</span> ${escapeStoreHtml(msg)}`;
    container.appendChild(div);
    if (!isMinimized) container.scrollTop = container.scrollHeight;
}

function updateProgress(percent, msg) {
    document.getElementById('install-progress-bar').style.width = percent + '%';
    document.getElementById('progress-percent').innerText = percent + '%';
    if (msg) document.getElementById('progress-text').innerText = msg;
    updateMiniWidget(`Installing... ${percent}%`, msg || '', true);
}

function updateMiniWidget(title, status, spinning) {
    document.getElementById('mini-title').innerText = title;
    document.getElementById('mini-status').innerText = status;
    document.getElementById('mini-spinner').style.display = spinning ? 'block' : 'none';
}

function minimizeLogModal() {
    isMinimized = true;
    document.getElementById('log-modal').style.display = 'none';
    document.getElementById('minimized-install-widget').style.display = 'flex';
}

function restoreLogModal() {
    isMinimized = false;
    document.getElementById('minimized-install-widget').style.display = 'none';
    document.getElementById('log-modal').style.display = 'flex';
    const container = document.getElementById('log-container');
    container.scrollTop = container.scrollHeight;
}

function closeLogModal() {
    document.getElementById('log-modal').style.display = 'none';
    document.getElementById('minimized-install-widget').style.display = 'none';
}

function refreshStoreAfterInstall() {
    closeLogModal();
    refreshStore();
}

