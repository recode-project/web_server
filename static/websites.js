/**
 * Web & Reverse Proxy Shield — Modular JavaScript
 * Eka Dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
    initWebsitesModule();
});

let currentSites = [];
let currentThreats = [];

function initWebsitesModule() {
    setupTabs();
    setupNginxControls();
    setupSearchFilter();
    setupBlockForm();

    // Initial data load
    fetchNginxStatus();
    fetchVhosts();
    fetchTraffic();
    fetchThreats();
    fetchBlockedIps();
    fetchSecurity();
    fetchSslStatus();

    // Interval timers
    setInterval(fetchNginxStatus, 30000);
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
        toastIcon.style.color = '#23d5ab';
    }

    toast.classList.add('show');
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => {
        toast.classList.remove('show');
    }, 3800);
}

/**
 * Tab Navigation Setup
 */
function setupTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    // Check initial tab from body or URL query
    const urlParams = new URLSearchParams(window.location.search);
    const initialTab = urlParams.get('tab') || document.body.dataset.initialTab || 'vhosts';

    switchTab(initialTab);

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            switchTab(tabName);
            // Update URL without refresh
            const url = new URL(window.location);
            url.searchParams.set('tab', tabName);
            window.history.replaceState({}, '', url);
        });
    });

    function switchTab(tabName) {
        tabBtns.forEach(b => {
            if (b.dataset.tab === tabName) {
                b.classList.add('active');
            } else {
                b.classList.remove('active');
            }
        });

        tabContents.forEach(content => {
            if (content.id === `tab-${tabName}`) {
                content.classList.add('active');
            } else {
                content.classList.remove('active');
            }
        });

        // Trigger specific data refresh when tab activated
        if (tabName === 'traffic') fetchTraffic();
        if (tabName === 'shield') { fetchThreats(); fetchBlockedIps(); }
        if (tabName === 'ssl') fetchSslStatus();
    }
}

/**
 * Nginx Service Status & Management
 */
function setupNginxControls() {
    const btnReload = document.getElementById('btn-reload-nginx');
    const btnRestart = document.getElementById('btn-restart-nginx');
    const btnRefreshVhosts = document.getElementById('btn-refresh-vhosts');
    const btnRefreshTraffic = document.getElementById('btn-refresh-traffic');
    const btnRefreshBlocked = document.getElementById('btn-refresh-blocked');
    const btnRefreshSsl = document.getElementById('btn-refresh-ssl');

    if (btnReload) {
        btnReload.addEventListener('click', () => controlNginx('reload'));
    }

    if (btnRestart) {
        btnRestart.addEventListener('click', () => {
            if (confirm('Apakah Anda yakin ingin me-restart service Nginx? Koneksi aktif akan tertutup sejenak.')) {
                controlNginx('restart');
            }
        });
    }

    if (btnRefreshVhosts) btnRefreshVhosts.addEventListener('click', fetchVhosts);
    if (btnRefreshTraffic) btnRefreshTraffic.addEventListener('click', fetchTraffic);
    if (btnRefreshBlocked) btnRefreshBlocked.addEventListener('click', fetchBlockedIps);
    if (btnRefreshSsl) btnRefreshSsl.addEventListener('click', fetchSslStatus);
}

async function fetchNginxStatus() {
    const dot = document.getElementById('nginx-status-dot');
    const text = document.getElementById('nginx-status-text');

    try {
        const res = await fetch('/api/websites/nginx_status');
        const data = await res.json();

        if (data.running) {
            dot.className = 'pulse-dot online';
            text.textContent = `${data.version || 'Nginx'} • Aktif`;
        } else {
            dot.className = 'pulse-dot offline';
            text.textContent = `Nginx: ${data.status || 'Nonaktif'}`;
        }
    } catch (err) {
        dot.className = 'pulse-dot offline';
        text.textContent = 'Gagal terhubung ke host';
    }
}

async function controlNginx(action) {
    showToast(`Mengeksekusi Nginx ${action}...`, 'info');
    try {
        const res = await fetch('/api/websites/control_nginx', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });
        const data = await res.json();

        if (data.success) {
            showToast(data.message || `Nginx ${action} berhasil`, 'success');
            fetchNginxStatus();
        } else {
            showToast(data.error || `Gagal ${action} Nginx`, 'danger');
        }
    } catch (err) {
        showToast(`Kesalahan jaringan: ${err.message}`, 'danger');
    }
}

/**
 * Virtual Hosts List & Search
 */
async function fetchVhosts() {
    const tbody = document.getElementById('vhosts-tbody');
    const statTotal = document.getElementById('stat-total-vhosts');
    const statSsl = document.getElementById('stat-ssl-count');

    try {
        const res = await fetch('/api/websites/vhosts');
        const data = await res.json();

        currentSites = data.sites || [];
        if (statTotal) statTotal.textContent = data.total || currentSites.length;
        if (statSsl) statSsl.textContent = data.ssl_count || 0;

        renderVhosts(currentSites);
    } catch (err) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation" style="color: var(--danger);"></i>
                    <p>Gagal memuat virtual host: ${err.message}</p>
                </td>
            </tr>
        `;
    }
}

function renderVhosts(sites) {
    const tbody = document.getElementById('vhosts-tbody');
    if (!tbody) return;

    if (!sites || sites.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state">
                    <i class="fa-solid fa-folder-open"></i>
                    <p>Tidak ada virtual host yang ditemukan di sites-enabled.</p>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = sites.map(s => {
        const domain = s.domain || s.name;
        const isProxy = s.is_proxy;
        const target = isProxy ? s.proxy_pass : s.root;
        const targetLabel = isProxy ? 'Reverse Proxy' : 'Static / Web Root';
        const typeBadge = isProxy
            ? `<span class="badge badge-purple"><i class="fa-solid fa-arrow-right-arrow-left"></i> Proxy</span>`
            : `<span class="badge badge-info"><i class="fa-solid fa-folder"></i> Web Root</span>`;

        const sslBadge = s.ssl
            ? `<span class="badge badge-success"><i class="fa-solid fa-lock"></i> SSL Aktif</span>`
            : `<span class="badge badge-warning"><i class="fa-solid fa-lock-open"></i> HTTP</span>`;

        const isLocalOrWildcard = domain.includes('_') || domain.includes('*') || domain === 'localhost';
        const openLink = isLocalOrWildcard ? '#' : (s.ssl ? `https://${domain}` : `http://${domain}`);

        return `
            <tr>
                <td style="font-family: monospace; font-weight: 600;">
                    <i class="fa-solid fa-globe" style="color: var(--accent-cyan); margin-right: 8px;"></i>
                    <span>${domain}</span>
                </td>
                <td>
                    <span style="background: rgba(35, 166, 213, 0.12); color: var(--accent-blue); border: 1px solid rgba(35, 166, 213, 0.25); padding: 2px 8px; border-radius: 6px; font-family: monospace; font-size: 0.8rem;">
                        :${s.port}
                    </span>
                </td>
                <td style="max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${target}">
                    <span style="font-family: monospace; font-size: 0.82rem; color: var(--text-dim);">${target}</span>
                </td>
                <td>${typeBadge}</td>
                <td>${sslBadge}</td>
                <td>
                    <div style="display: flex; gap: 0.4rem; align-items: center;">
                        ${!isLocalOrWildcard ? `
                            <a href="${openLink}" target="_blank" class="btn-mini" title="Buka website di tab baru">
                                <i class="fa-solid fa-arrow-up-right-from-square"></i> Buka
                            </a>
                        ` : ''}
                        ${!isProxy && s.root !== '-' ? `
                            <button class="btn-mini" onclick="backupWebDomain('${domain}')" title="Unduh backup ZIP file web">
                                <i class="fa-solid fa-download"></i> Backup
                            </button>
                        ` : ''}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function setupSearchFilter() {
    const searchInput = document.getElementById('vhost-search');
    if (!searchInput) return;

    searchInput.addEventListener('input', (e) => {
        const q = e.target.value.toLowerCase().trim();
        if (!q) {
            renderVhosts(currentSites);
            return;
        }

        const filtered = currentSites.filter(s => {
            const dom = (s.domain || '').toLowerCase();
            const name = (s.name || '').toLowerCase();
            const root = (s.root || '').toLowerCase();
            const proxy = (s.proxy_pass || '').toLowerCase();
            return dom.includes(q) || name.includes(q) || root.includes(q) || proxy.includes(q);
        });

        renderVhosts(filtered);
    });
}

/**
 * Traffic & Analisis Real-Time
 */
async function fetchTraffic() {
    const statToday = document.getElementById('stat-today-req');
    const statBlocked = document.getElementById('stat-blocked-count');
    const uniqueIpsEl = document.getElementById('traffic-unique-ips');
    const avgDurationEl = document.getElementById('traffic-avg-duration');
    const statusCodesEl = document.getElementById('traffic-status-codes');
    const chartContainer = document.getElementById('traffic-chart');
    const topPagesTbody = document.getElementById('top-pages-tbody');

    try {
        const res = await fetch('/api/websites/traffic');
        const data = await res.json();

        if (statToday) statToday.textContent = data.today_requests.toLocaleString();
        if (statBlocked) statBlocked.textContent = data.bad_bots_blocked.toLocaleString();
        if (uniqueIpsEl) uniqueIpsEl.textContent = data.unique_ips_count.toLocaleString();
        if (avgDurationEl) avgDurationEl.textContent = data.avg_duration || '0m 0s';

        // Format Status codes
        if (statusCodesEl && data.status_codes) {
            const sc = data.status_codes;
            statusCodesEl.innerHTML = `
                <span style="color:#3fb950">${sc['2xx'] || 0}</span> /
                <span style="color:#58a6ff">${sc['3xx'] || 0}</span> /
                <span style="color:#d29922">${sc['4xx'] || 0}</span> /
                <span style="color:#f85149">${sc['5xx'] || 0}</span>
            `;
        }

        // Render 24H Flex Chart
        if (chartContainer && data.hourly_distribution) {
            const maxVal = Math.max(...data.hourly_distribution.map(d => d.count), 1);
            chartContainer.innerHTML = data.hourly_distribution.map(item => {
                const heightPercent = Math.max(Math.round((item.count / maxVal) * 100), 5);
                return `
                    <div class="chart-col" title="${item.hour}: ${item.count} permintaan">
                        <div class="chart-bar" style="height: ${heightPercent}%;"></div>
                        <div class="chart-label">${item.hour.split(':')[0]}</div>
                    </div>
                `;
            }).join('');
        }

        // Render Top Pages
        if (topPagesTbody && data.top_pages) {
            if (data.top_pages.length === 0) {
                topPagesTbody.innerHTML = `
                    <tr><td colspan="3" class="empty-state"><p>Belum ada data riwayat kunjungan.</p></td></tr>
                `;
            } else {
                const maxPageCount = Math.max(...data.top_pages.map(p => p.count), 1);
                topPagesTbody.innerHTML = data.top_pages.map(p => {
                    const widthPct = Math.round((p.count / maxPageCount) * 100);
                    return `
                        <tr>
                            <td style="font-family: monospace; font-size: 0.85rem; font-weight: 600;">
                                <i class="fa-solid fa-link" style="color: var(--accent-blue); margin-right: 6px;"></i>
                                ${p.page}
                            </td>
                            <td>
                                <div style="background: rgba(255,255,255,0.06); height: 8px; border-radius: 4px; overflow: hidden;">
                                    <div style="background: linear-gradient(90deg, var(--accent-cyan), var(--accent-blue)); width: ${widthPct}%; height: 100%; border-radius: 4px;"></div>
                                </div>
                            </td>
                            <td style="font-family: monospace; font-weight: 700; color: var(--accent-cyan); text-align: right;">
                                ${p.count.toLocaleString()}
                            </td>
                        </tr>
                    `;
                }).join('');
            }
        }
    } catch (err) {
        console.error('Traffic fetch error:', err);
    }
}

/**
 * Security & Threats Shield
 */
async function fetchThreats() {
    const tbody = document.getElementById('threats-tbody');
    try {
        const res = await fetch('/api/websites/threats');
        const data = await res.json();
        currentThreats = data.threats || [];

        if (!tbody) return;

        if (!data.recent || data.recent.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-state">
                        <i class="fa-solid fa-shield-check" style="color: var(--success); opacity: 0.8;"></i>
                        <p>Tidak ada aktivitas scanner atau bot mencurigakan terdeteksi dalam log.</p>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = data.recent.slice(0, 25).map(t => {
            return `
                <tr>
                    <td style="font-family: monospace; font-weight: 600; color: #ff6b6b;">
                        ${t.ip}
                    </td>
                    <td style="font-size: 0.8rem; color: var(--text-dim);">${t.time}</td>
                    <td style="font-family: monospace; font-size: 0.8rem;">
                        <span style="color: var(--warning);">${t.method}</span> ${t.path}
                    </td>
                    <td>
                        <span class="badge badge-danger">${t.threat_type}</span>
                    </td>
                    <td style="max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.78rem; color: var(--text-dim);" title="${t.ua}">
                        ${t.ua}
                    </td>
                    <td>
                        <button class="btn-mini" onclick="blockIp('${t.ip}')" style="color: var(--danger); border-color: rgba(248,81,73,0.3);">
                            <i class="fa-solid fa-ban"></i> Blokir
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (err) {
        if (tbody) {
            tbody.innerHTML = `
                <tr><td colspan="6" class="empty-state"><p>Gagal memuat log ancaman: ${err.message}</p></td></tr>
            `;
        }
    }
}

async function fetchSecurity() {
    const sshEl = document.getElementById('shield-failed-ssh');
    try {
        const res = await fetch('/api/web_monitor/security');
        const data = await res.json();
        if (sshEl) sshEl.textContent = `${data.failed_logins || 0} percobaan`;
    } catch (e) { }
}

async function fetchBlockedIps() {
    const tbody = document.getElementById('blocked-ips-tbody');
    const badgeEl = document.getElementById('shield-blocked-count');

    try {
        const res = await fetch('/api/websites/threats/blocked_ips');
        const data = await res.json();
        const blocked = data.blocked || [];

        if (badgeEl) badgeEl.textContent = `${blocked.length} IP`;

        if (!tbody) return;

        if (blocked.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="3" class="empty-state">
                        <i class="fa-solid fa-circle-check" style="color: var(--success); opacity: 0.8;"></i>
                        <p>Tidak ada IP yang sedang terblokir di host iptables.</p>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = blocked.map(ip => `
            <tr>
                <td style="font-family: monospace; font-weight: 600; font-size: 0.95rem;">${ip}</td>
                <td><span class="badge badge-danger">INPUT DROP</span></td>
                <td>
                    <button class="btn-mini" onclick="unblockIp('${ip}')" style="color: var(--success); border-color: rgba(63,185,80,0.3);">
                        <i class="fa-solid fa-lock-open"></i> Buka Blokir
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        if (tbody) {
            tbody.innerHTML = `
                <tr><td colspan="3" class="empty-state"><p>Gagal memuat daftar IP terblokir: ${err.message}</p></td></tr>
            `;
        }
    }
}

function setupBlockForm() {
    const form = document.getElementById('form-block-ip');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const input = document.getElementById('input-block-ip');
        const ip = input.value.trim();
        if (!ip) return;

        await blockIp(ip);
        input.value = '';
    });
}

window.blockIp = async function (ip) {
    if (!confirm(`Blokir alamat IP ${ip} dari seluruh akses server via iptables DROP?`)) return;

    showToast(`Memblokir IP ${ip}...`, 'info');
    try {
        const res = await fetch('/api/websites/threats/block', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip })
        });
        const data = await res.json();

        if (data.success) {
            showToast(data.message || `IP ${ip} berhasil diblokir`, 'success');
            fetchBlockedIps();
        } else {
            showToast(data.error || `Gagal memblokir IP ${ip}`, 'danger');
        }
    } catch (err) {
        showToast(`Kesalahan: ${err.message}`, 'danger');
    }
};

window.unblockIp = async function (ip) {
    showToast(`Membuka blokir IP ${ip}...`, 'info');
    try {
        const res = await fetch('/api/websites/threats/unblock', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip })
        });
        const data = await res.json();

        if (data.success) {
            showToast(data.message || `IP ${ip} berhasil dibuka`, 'success');
            fetchBlockedIps();
        } else {
            showToast(data.error || `Gagal membuka blokir IP ${ip}`, 'danger');
        }
    } catch (err) {
        showToast(`Kesalahan: ${err.message}`, 'danger');
    }
};

/**
 * SSL Certificates Dynamic Tracker & Web Backup
 */
async function fetchSslStatus() {
    const tbody = document.getElementById('ssl-tbody');
    try {
        const res = await fetch('/api/websites/ssl_status');
        const data = await res.json();

        if (!tbody) return;

        const certs = data.certificates || [];
        if (certs.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-state">
                        <i class="fa-solid fa-certificate"></i>
                        <p>Tidak ada domain publik yang ditemukan untuk diperiksa sertifikat SSL-nya.</p>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = certs.map(c => {
            let statusBadge = '';
            if (c.status === 'valid') {
                statusBadge = `<span class="badge badge-success"><i class="fa-solid fa-check"></i> Aktif Valid</span>`;
            } else if (c.status === 'expiring') {
                statusBadge = `<span class="badge badge-warning"><i class="fa-solid fa-clock"></i> Segera Berakhir</span>`;
            } else {
                statusBadge = `<span class="badge badge-danger"><i class="fa-solid fa-circle-exclamation"></i> Berakhir / Error</span>`;
            }

            const daysLeft = c.days_left;
            let daysHtml = `${daysLeft} Hari`;
            if (daysLeft < 0) {
                daysHtml = `<span style="color: var(--danger); font-weight: 700;">Sudah Kedaluwarsa</span>`;
            } else if (daysLeft < 14) {
                daysHtml = `<span style="color: var(--warning); font-weight: 700;">${daysLeft} Hari Lagi</span>`;
            } else {
                daysHtml = `<span style="color: var(--accent-cyan); font-weight: 700;">${daysLeft} Hari</span>`;
            }

            return `
                <tr>
                    <td style="font-family: monospace; font-weight: 700;">
                        <a href="https://${c.domain}" target="_blank" style="color: #fff; text-decoration: none;">
                            <i class="fa-solid fa-globe" style="color: var(--accent-cyan); margin-right: 6px;"></i>
                            ${c.domain}
                        </a>
                    </td>
                    <td>${statusBadge}</td>
                    <td>${daysHtml}</td>
                    <td style="font-size: 0.85rem; color: var(--text-dim);">${c.issuer || 'N/A'}</td>
                    <td style="font-size: 0.82rem; color: var(--text-dim);">${c.valid_to || 'N/A'}</td>
                    <td>
                        <button class="btn-mini" onclick="backupWebDomain('${c.domain}')">
                            <i class="fa-solid fa-file-zipper"></i> Unduh Cadangan
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (err) {
        if (tbody) {
            tbody.innerHTML = `
                <tr><td colspan="6" class="empty-state"><p>Gagal memuat status sertifikat SSL: ${err.message}</p></td></tr>
            `;
        }
    }
}

window.backupWebDomain = async function (domain) {
    showToast(`Membuat arsip ZIP untuk ${domain}...`, 'info');
    try {
        const res = await fetch('/api/websites/backup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ domain })
        });

        if (!res.ok) {
            const errData = await res.json();
            showToast(errData.error || 'Gagal membuat backup direktori web', 'danger');
            return;
        }

        // Trigger file download
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `backup_${domain.replace(/[^a-zA-Z0-9.-]/g, '_')}.zip`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();

        showToast(`Cadangan ${domain} berhasil diunduh!`, 'success');
    } catch (err) {
        showToast(`Gagal mengunduh cadangan: ${err.message}`, 'danger');
    }
};

