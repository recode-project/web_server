/**
 * Services & System Daemons Manager — Modular JavaScript
 * Eka Dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
    initServicesModule();
});

let allServices = [];
let currentFilter = 'all';
let searchQuery = '';
let activeModalUnit = null;
let searchDebounceTimer = null;

function initServicesModule() {
    setupFilterPills();
    setupSearch();
    setupQuickChips();
    setupActionButtons();

    // Initial fetch
    fetchSummary();
    fetchServices();

    // Auto-refresh summary every 20s
    setInterval(fetchSummary, 20000);
}

/**
 * Toast Notification Utility
 */
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toast-msg');
    const toastIcon = document.getElementById('toast-icon');

    if (!toast || !toastMsg) return;

    toastMsg.textContent = message;

    if (type === 'success') {
        toastIcon.className = 'fa-solid fa-circle-check';
        toastIcon.style.color = '#3fb950';
    } else if (type === 'danger' || type === 'error') {
        toastIcon.className = 'fa-solid fa-triangle-exclamation';
        toastIcon.style.color = '#f85149';
    } else {
        toastIcon.className = 'fa-solid fa-circle-info';
        toastIcon.style.color = '#00b4db';
    }

    toast.classList.add('show');
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => {
        toast.classList.remove('show');
    }, 3800);
}

/**
 * Summary Status Fetcher
 */
async function fetchSummary() {
    try {
        const res = await fetch('/api/services/summary');
        const data = await res.json();

        const statTotal = document.getElementById('stat-total-services');
        const statRunning = document.getElementById('stat-running-services');
        const statFailed = document.getElementById('stat-failed-services');
        const statInactive = document.getElementById('stat-inactive-services');
        const failedPillCount = document.getElementById('failed-pill-count');
        const sysText = document.getElementById('system-status-text');
        const sysDot = document.getElementById('system-status-dot');

        if (statTotal) statTotal.textContent = data.total || 0;
        if (statRunning) statRunning.textContent = data.running || 0;
        if (statFailed) statFailed.textContent = data.failed || 0;
        if (statInactive) statInactive.textContent = data.inactive || 0;
        if (failedPillCount) failedPillCount.textContent = data.failed || 0;

        if (sysText && sysDot) {
            const isDegraded = data.failed > 0 || data.system_state === 'degraded';
            if (isDegraded) {
                sysDot.className = 'pulse-dot offline';
                sysText.textContent = `systemd: Degraded (${data.failed} failed)`;
            } else {
                sysDot.className = 'pulse-dot online';
                sysText.textContent = `systemd: Running (Normal)`;
            }
        }
    } catch (err) {
        console.error('Failed to fetch services summary:', err);
    }
}

/**
 * Services List Fetcher & Renderer
 */
async function fetchServices() {
    const tbody = document.getElementById('services-tbody');
    if (!tbody) return;

    try {
        const url = `/api/services/list?filter=${encodeURIComponent(currentFilter)}&q=${encodeURIComponent(searchQuery)}`;
        const res = await fetch(url);
        const data = await res.json();

        allServices = data.services || [];
        renderServices(allServices);
    } catch (err) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation" style="color: var(--danger);"></i>
                    <p>Gagal memuat daftar services: ${err.message}</p>
                </td>
            </tr>
        `;
    }
}

function renderServices(services) {
    const tbody = document.getElementById('services-tbody');
    if (!tbody) return;

    if (!services || services.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state">
                    <i class="fa-solid fa-folder-open"></i>
                    <p>Tidak ada service yang cocok dengan filter atau pencarian saat ini.</p>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = services.map(s => {
        const isFailed = s.active === 'failed' || s.sub === 'failed';
        const isRunning = s.active === 'active' && s.sub === 'running';

        let badgeHtml = '';
        if (isFailed) {
            badgeHtml = `<span class="badge badge-danger"><i class="fa-solid fa-circle-xmark"></i> Failed</span>`;
        } else if (isRunning) {
            badgeHtml = `<span class="badge badge-success"><i class="fa-solid fa-circle-check"></i> Running</span>`;
        } else if (s.active === 'active') {
            badgeHtml = `<span class="badge badge-info"><i class="fa-solid fa-check"></i> Active</span>`;
        } else {
            badgeHtml = `<span class="badge badge-gray"><i class="fa-solid fa-circle-pause"></i> Inactive</span>`;
        }

        const subBadge = `<span style="font-family: monospace; font-size: 0.8rem; color: var(--text-dim); background: rgba(255,255,255,0.05); padding: 2px 7px; border-radius: 4px;">${s.sub}</span>`;

        return `
            <tr>
                <td style="font-family: monospace; font-weight: 700;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <i class="fa-solid fa-cube" style="color: ${isFailed ? 'var(--danger)' : (isRunning ? 'var(--accent-blue)' : 'var(--text-dim)')};"></i>
                        <span style="color: #fff;">${s.name}</span>
                    </div>
                    <div style="font-size: 0.72rem; color: var(--text-dim); font-weight: 400; margin-top: 2px;">${s.unit}</div>
                </td>
                <td style="font-size: 0.85rem; color: var(--text-dim); max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${s.description}">
                    ${s.description}
                </td>
                <td>${badgeHtml}</td>
                <td>${subBadge}</td>
                <td style="text-align: right;">
                    <div style="display: flex; gap: 0.4rem; justify-content: flex-end; align-items: center;">
                        ${isRunning ? `
                            <button class="btn-mini" onclick="quickControl('${s.unit}', 'restart')" title="Restart service">
                                <i class="fa-solid fa-rotate"></i>
                            </button>
                            <button class="btn-mini danger" onclick="quickControl('${s.unit}', 'stop')" title="Hentikan service">
                                <i class="fa-solid fa-stop"></i>
                            </button>
                        ` : `
                            <button class="btn-mini success" onclick="quickControl('${s.unit}', 'start')" title="Jalankan service">
                                <i class="fa-solid fa-play"></i>
                            </button>
                        `}
                        <button class="btn-mini" onclick="openServiceDetail('${s.unit}')" title="Inspeksi detail dan log">
                            <i class="fa-solid fa-terminal"></i> Log
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

/**
 * Filter Pills, Search & Quick Chips Setup
 */
function setupFilterPills() {
    const pills = document.querySelectorAll('.pill-btn');
    pills.forEach(pill => {
        pill.addEventListener('click', () => {
            pills.forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            currentFilter = pill.dataset.filter;
            fetchServices();
        });
    });

    const cardFailed = document.getElementById('card-failed');
    if (cardFailed) {
        cardFailed.addEventListener('click', () => {
            const pillFailed = document.getElementById('pill-failed');
            if (pillFailed) pillFailed.click();
        });
    }
}

function setupSearch() {
    const searchInput = document.getElementById('service-search');
    if (!searchInput) return;

    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
            searchQuery = e.target.value.trim();
            fetchServices();
        }, 220);
    });
}

function setupQuickChips() {
    const chips = document.querySelectorAll('.chip-btn');
    const searchInput = document.getElementById('service-search');

    chips.forEach(chip => {
        chip.addEventListener('click', () => {
            const term = chip.dataset.search;
            if (searchInput) {
                searchInput.value = term;
                searchQuery = term;
                fetchServices();
            }
        });
    });
}

function setupActionButtons() {
    const btnRefresh = document.getElementById('btn-refresh-all');
    if (btnRefresh) {
        btnRefresh.addEventListener('click', () => {
            showToast('Menyegarkan daftar services...', 'info');
            fetchSummary();
            fetchServices();
        });
    }

    // Modal buttons
    const mRestart = document.getElementById('modal-btn-restart');
    const mStart = document.getElementById('modal-btn-start');
    const mStop = document.getElementById('modal-btn-stop');
    const mToggleEnable = document.getElementById('modal-btn-toggle-enable');

    if (mRestart) mRestart.addEventListener('click', () => activeModalUnit && controlService(activeModalUnit, 'restart'));
    if (mStart) mStart.addEventListener('click', () => activeModalUnit && controlService(activeModalUnit, 'start'));
    if (mStop) mStop.addEventListener('click', () => activeModalUnit && controlService(activeModalUnit, 'stop'));
    if (mToggleEnable) {
        mToggleEnable.addEventListener('click', () => {
            if (!activeModalUnit) return;
            const curState = document.getElementById('modal-unit-state').textContent.toLowerCase();
            const nextAction = curState.includes('enabled') ? 'disable' : 'enable';
            controlService(activeModalUnit, nextAction);
        });
    }
}

/**
 * Service Actions & Modal Logic
 */
window.quickControl = async function (unit, action) {
    if (action === 'stop' && !confirm(`Hentikan service ${unit}?`)) return;
    await controlService(unit, action);
};

async function controlService(unit, action) {
    showToast(`Mengeksekusi ${action} pada ${unit}...`, 'info');
    try {
        const res = await fetch('/api/services/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ unit, action })
        });
        const data = await res.json();

        if (data.success) {
            showToast(data.message || `Service ${unit} berhasil di-${action}`, 'success');
            fetchSummary();
            fetchServices();
            if (activeModalUnit === unit) {
                openServiceDetail(unit);
            }
        } else {
            showToast(data.error || `Gagal ${action} ${unit}`, 'danger');
        }
    } catch (err) {
        showToast(`Kesalahan jaringan: ${err.message}`, 'danger');
    }
}

window.openServiceDetail = async function (unit) {
    activeModalUnit = unit;
    const modal = document.getElementById('service-modal');
    const nameEl = document.getElementById('modal-unit-name');
    const badgeEl = document.getElementById('modal-unit-badge');
    const descEl = document.getElementById('modal-unit-desc');
    const pidEl = document.getElementById('modal-pid');
    const memEl = document.getElementById('modal-mem');
    const cpuEl = document.getElementById('modal-cpu');
    const stateEl = document.getElementById('modal-unit-state');
    const logsEl = document.getElementById('modal-logs');

    nameEl.textContent = unit;
    descEl.textContent = 'Memuat properti unit...';
    logsEl.textContent = 'Memuat log journald...';
    modal.classList.add('active');

    try {
        const res = await fetch(`/api/services/detail/${encodeURIComponent(unit)}`);
        const data = await res.json();

        if (data.error) {
            showToast(data.error, 'danger');
            closeServiceModal();
            return;
        }

        const p = data.properties || {};
        descEl.textContent = p.Description || unit;
        pidEl.textContent = p.MainPID && p.MainPID !== '0' ? p.MainPID : 'N/A';
        memEl.textContent = p.MemoryFormatted || '0 MB';
        cpuEl.textContent = p.CPUUsageFormatted || '0 s';
        stateEl.textContent = p.UnitFileState || p.ActiveState || 'N/A';

        // Set badge
        const isFailed = p.ActiveState === 'failed' || p.SubState === 'failed';
        const isRunning = p.ActiveState === 'active' && p.SubState === 'running';

        if (isFailed) {
            badgeEl.className = 'badge badge-danger';
            badgeEl.textContent = 'Failed';
        } else if (isRunning) {
            badgeEl.className = 'badge badge-success';
            badgeEl.textContent = 'Running';
        } else {
            badgeEl.className = 'badge badge-gray';
            badgeEl.textContent = p.ActiveState || 'Inactive';
        }

        // Render logs
        const logs = data.logs || [];
        if (logs.length === 0) {
            logsEl.textContent = '(Tidak ada log journald terbaru untuk unit ini)';
        } else {
            logsEl.textContent = logs.join('\n');
            logsEl.scrollTop = logsEl.scrollHeight;
        }
    } catch (err) {
        logsEl.textContent = `Gagal memuat detail unit: ${err.message}`;
    }
};

window.closeServiceModal = function () {
    const modal = document.getElementById('service-modal');
    if (modal) modal.classList.remove('active');
    activeModalUnit = null;
};

window.refreshModalLogs = function () {
    if (activeModalUnit) {
        showToast('Memperbarui log...', 'info');
        openServiceDetail(activeModalUnit);
    }
};

window.copyModalLogs = function () {
    const logsEl = document.getElementById('modal-logs');
    if (!logsEl) return;
    navigator.clipboard.writeText(logsEl.textContent).then(() => {
        showToast('Log berhasil disalin ke clipboard!', 'success');
    }).catch(() => {
        showToast('Gagal menyalin log', 'danger');
    });
};

