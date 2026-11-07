/**
 * Eka Dashboard — AdBlocker DNS Manager Suite
 * Logika modular antarmuka manajemen AdGuard Home
 * 
 * Standar: Strict External Script (Tanpa Inline JS pada HTML)
 */

(function () {
    'use strict';

    // State Variables
    let currentConfig = null;
    let isFetchingStatus = false;
    let autoRefreshTimer = null;

    // DOM Elements
    const elements = {
        protectionBar: document.getElementById('protection-bar'),
        protectionIcon: document.getElementById('protection-icon'),
        badgeStatus: document.getElementById('badge-status'),
        protectionDesc: document.getElementById('protection-desc'),
        toggleProtection: document.getElementById('toggle-protection'),
        offlineBanner: document.getElementById('offline-banner'),
        offlineDesc: document.getElementById('offline-desc'),
        btnOfflineConfig: document.getElementById('btn-offline-config'),
        btnOpenInstall: document.getElementById('btn-open-install'),
        modalInstall: document.getElementById('modal-install'),
        btnCloseInstallModal: document.getElementById('btn-close-install-modal'),
        btnCancelInstall: document.getElementById('btn-cancel-install'),
        formInstall: document.getElementById('form-install'),
        btnSubmitInstall: document.getElementById('btn-submit-install'),
        instWebPort: document.getElementById('inst-web-port'),
        instDnsPort: document.getElementById('inst-dns-port'),
        installLogBox: document.getElementById('install-log-box'),
        installLogText: document.getElementById('install-log-text'),
        linkWebConsole: document.getElementById('link-web-console'),
        btnRefresh: document.getElementById('btn-refresh'),
        btnOpenSettings: document.getElementById('btn-open-settings'),
        btnCloseModal: document.getElementById('btn-close-modal'),
        btnCancelSettings: document.getElementById('btn-cancel-settings'),
        modalSettings: document.getElementById('modal-settings'),
        formSettings: document.getElementById('form-settings'),
        btnSaveSettings: document.getElementById('btn-save-settings'),
        // Metrics
        valTotalQueries: document.getElementById('val-total-queries'),
        valBlockedQueries: document.getElementById('val-blocked-queries'),
        valBlockedRatio: document.getElementById('val-blocked-ratio'),
        barBlockedRatio: document.getElementById('bar-blocked-ratio'),
        valAvgLatency: document.getElementById('val-avg-latency'),
        dnsChipsList: document.getElementById('dns-chips-list'),
        // Tables
        tableBlockedBody: document.getElementById('table-blocked-body'),
        tableQueriedBody: document.getElementById('table-queried-body'),
        tableClientsBody: document.getElementById('table-clients-body'),
        badgeTopBlocked: document.getElementById('badge-top-blocked'),
        badgeTopQueried: document.getElementById('badge-top-queried'),
        badgeTopClients: document.getElementById('badge-top-clients'),
        // Rules
        rulesTextarea: document.getElementById('rules-textarea'),
        btnSaveRules: document.getElementById('btn-save-rules'),
        rulesCountBadge: document.getElementById('rules-count-badge'),
        // Config inputs
        cfgHost: document.getElementById('cfg-host'),
        cfgPort: document.getElementById('cfg-port'),
        cfgUser: document.getElementById('cfg-user'),
        cfgPass: document.getElementById('cfg-pass'),
        cfgTls: document.getElementById('cfg-tls'),
        // Toast
        toastNotify: document.getElementById('toast-notify'),
        toastIcon: document.getElementById('toast-icon'),
        toastMsg: document.getElementById('toast-msg')
    };

    /**
     * Menampilkan notifikasi Toast
     */
    function showToast(message, type = 'success') {
        if (!elements.toastNotify) return;

        elements.toastNotify.className = `toast ${type} show`;
        elements.toastMsg.textContent = message;

        if (elements.toastIcon) {
            elements.toastIcon.className = type === 'success' 
                ? 'fa-solid fa-circle-check' 
                : 'fa-solid fa-circle-exclamation';
        }

        setTimeout(() => {
            elements.toastNotify.classList.remove('show');
        }, 3500);
    }

    /**
     * Format angka ke format ribuan (locale)
     */
    function formatNumber(num) {
        if (typeof num !== 'number') return '0';
        return num.toLocaleString('id-ID');
    }

    /**
     * Mengambil status operasional dan statistik DNS dari backend
     */
    async function fetchStatus() {
        if (isFetchingStatus) return;
        isFetchingStatus = true;

        try {
            const res = await fetch('/api/adblocker/status');
            const data = await res.json();

            if (!res.ok || !data.connected) {
                renderDisconnected(data.error || 'Gagal menghubungi server AdGuard.');
                return;
            }

            renderConnected(data);
        } catch (err) {
            renderDisconnected(err.message || 'Kesalahan jaringan saat memuat status AdBlocker.');
        } finally {
            isFetchingStatus = false;
        }
    }

    /**
     * Render antarmuka saat AdGuard Home offline / gagal terhubung
     */
    function renderDisconnected(errorMsg) {
        if (elements.offlineBanner) {
            elements.offlineBanner.classList.add('visible');
            if (elements.offlineDesc) {
                elements.offlineDesc.textContent = errorMsg;
            }
        }

        if (elements.protectionBar) {
            elements.protectionBar.classList.add('disabled');
        }
        if (elements.badgeStatus) {
            elements.badgeStatus.className = 'status-badge badge-disabled';
            elements.badgeStatus.textContent = 'DISCONNECTED';
        }
        if (elements.protectionDesc) {
            elements.protectionDesc.textContent = 'Layanan AdGuard Home tidak merespons pada host/port yang dikonfigurasi.';
        }
        if (elements.toggleProtection) {
            elements.toggleProtection.checked = false;
            elements.toggleProtection.disabled = true;
        }

        // Tampilkan placeholder di kartu metrik
        elements.valTotalQueries.textContent = '-';
        elements.valBlockedQueries.textContent = '-';
        elements.valBlockedRatio.textContent = '-';
        elements.barBlockedRatio.style.width = '0%';
        elements.valAvgLatency.textContent = '-';
    }

    /**
     * Render antarmuka saat AdGuard Home online & merespons
     */
    function renderConnected(data) {
        if (elements.offlineBanner) {
            elements.offlineBanner.classList.remove('visible');
        }

        const isProtected = Boolean(data.protection_enabled);

        // Update Toggle & Master Bar
        if (elements.toggleProtection) {
            elements.toggleProtection.disabled = false;
            elements.toggleProtection.checked = isProtected;
        }

        if (elements.protectionBar) {
            if (isProtected) {
                elements.protectionBar.classList.remove('disabled');
            } else {
                elements.protectionBar.classList.add('disabled');
            }
        }

        if (elements.badgeStatus) {
            elements.badgeStatus.className = isProtected ? 'status-badge badge-active' : 'status-badge badge-disabled';
            elements.badgeStatus.textContent = isProtected ? 'PROTECTED' : 'DISABLED';
        }

        if (elements.protectionDesc) {
            elements.protectionDesc.textContent = isProtected
                ? 'Memblokir iklan, pelacak, dan domain berbahaya di seluruh perangkat jaringan.'
                : 'Proteksi DNS sedang DINONAKTIFKAN. Seluruh permintaan DNS diteruskan tanpa filtering.';
        }

        // Update Web Console Link
        if (elements.linkWebConsole && data.base_url) {
            // Gunakan hostname dari window.location agar link console dapat dibuka dari klien eksternal
            const clientHost = window.location.hostname;
            const port = (data.status && data.status.http_port) ? data.status.http_port : 8053;
            elements.linkWebConsole.href = `http://${clientHost}:${port}`;
        }

        // Update DNS Listen Chips
        if (elements.dnsChipsList && Array.isArray(data.dns_addresses)) {
            const port = data.dns_port || 53;
            const validIps = data.dns_addresses.filter(ip => ip !== '0.0.0.0' && ip !== '::');
            const clientHost = window.location.hostname;
            if (clientHost && !validIps.includes(clientHost)) {
                validIps.unshift(clientHost);
            }

            elements.dnsChipsList.innerHTML = validIps.slice(0, 4).map(ip => 
                `<span class="dns-chip"><i class="fa-solid fa-server"></i> ${ip}:${port}</span>`
            ).join('');
        }

        // Render KPI Metrics
        const stats = data.stats || {};
        const total = stats.num_dns_queries || 0;
        const blocked = stats.num_blocked_filtering || 0;
        const latencyMs = stats.avg_processing_time ? (stats.avg_processing_time * 1000).toFixed(1) : '0';
        
        let ratio = 0;
        if (total > 0) {
            ratio = ((blocked / total) * 100).toFixed(1);
        }

        elements.valTotalQueries.textContent = formatNumber(total);
        elements.valBlockedQueries.textContent = formatNumber(blocked);
        elements.valBlockedRatio.textContent = `${ratio}%`;
        elements.barBlockedRatio.style.width = `${Math.min(100, Math.max(0, ratio))}%`;
        elements.valAvgLatency.textContent = `${latencyMs} ms`;

        // Render Tables
        renderDomainTable(elements.tableBlockedBody, elements.badgeTopBlocked, stats.top_blocked_domains || [], 'Blokir', 'Domain');
        renderDomainTable(elements.tableQueriedBody, elements.badgeTopQueried, stats.top_queried_domains || [], 'Permintaan', 'Domain');
        renderClientsTable(elements.tableClientsBody, elements.badgeTopClients, stats.top_clients || []);
    }

    /**
     * Render daftar domain ke tabel analitik
     */
    function renderDomainTable(tbody, badge, items, countHeader, itemLabel) {
        if (!tbody) return;

        if (!items || items.length === 0) {
            tbody.innerHTML = `<tr><td colspan="2" class="empty-hint">Belum ada aktivitas ${itemLabel.toLowerCase()} tercatat.</td></tr>`;
            if (badge) badge.textContent = '0 Domain';
            return;
        }

        if (badge) {
            badge.textContent = `${items.length} Domain`;
        }

        tbody.innerHTML = items.slice(0, 10).map(item => {
            let name = '';
            let count = 0;

            if (typeof item === 'object') {
                const keys = Object.keys(item);
                if (keys.length > 0) {
                    name = keys[0];
                    count = item[name];
                }
            }

            return `
                <tr>
                    <td class="domain-name" title="${name}">
                        <i class="fa-solid fa-globe" style="color: #64748b; margin-right: 6px;"></i>${escapeHtml(name)}
                    </td>
                    <td style="text-align: right;">
                        <span class="count-badge">${formatNumber(count)}</span>
                    </td>
                </tr>
            `;
        }).join('');
    }

    /**
     * Render daftar klien teraktif
     */
    function renderClientsTable(tbody, badge, clients) {
        if (!tbody) return;

        if (!clients || clients.length === 0) {
            tbody.innerHTML = '<tr><td colspan="2" class="empty-hint">Belum ada klien aktif terdeteksi.</td></tr>';
            if (badge) badge.textContent = '0 Klien';
            return;
        }

        if (badge) {
            badge.textContent = `${clients.length} Klien`;
        }

        tbody.innerHTML = clients.slice(0, 10).map(item => {
            let clientIp = '';
            let count = 0;

            if (typeof item === 'object') {
                const keys = Object.keys(item);
                if (keys.length > 0) {
                    clientIp = keys[0];
                    count = item[clientIp];
                }
            }

            return `
                <tr>
                    <td>
                        <i class="fa-solid fa-desktop" style="color: #a855f7; margin-right: 6px;"></i>
                        <span class="domain-name">${escapeHtml(clientIp)}</span>
                    </td>
                    <td style="text-align: right;">
                        <span class="count-badge">${formatNumber(count)} req</span>
                    </td>
                </tr>
            `;
        }).join('');
    }

    /**
     * Toggle Proteksi DNS AdGuard
     */
    async function handleToggleProtection(e) {
        const targetState = e.target.checked;
        e.target.disabled = true;

        try {
            const res = await fetch('/api/adblocker/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: targetState })
            });
            const data = await res.json();

            if (res.ok && data.success) {
                showToast(`Proteksi DNS ${targetState ? 'diaktifkan' : 'dinonaktifkan'}.`, 'success');
                await fetchStatus();
            } else {
                e.target.checked = !targetState;
                showToast(`Gagal mengubah status: ${data.error || 'Unknown error'}`, 'error');
            }
        } catch (err) {
            e.target.checked = !targetState;
            showToast(`Kesalahan jaringan: ${err.message}`, 'error');
        } finally {
            e.target.disabled = false;
        }
    }

    /**
     * Mengambil daftar aturan custom filtering
     */
    async function fetchRules() {
        if (!elements.rulesTextarea) return;

        try {
            const res = await fetch('/api/adblocker/rules');
            const data = await res.json();

            if (res.ok && data.success) {
                const rules = data.user_rules || [];
                elements.rulesTextarea.value = rules.join('\n');
                updateRulesCount(rules.length);
            }
        } catch (err) {
            console.error('[AdBlocker] Gagal mengambil filtering rules:', err);
        }
    }

    /**
     * Simpan aturan custom filtering ke AdGuard
     */
    async function handleSaveRules() {
        if (!elements.rulesTextarea || !elements.btnSaveRules) return;

        const originalBtnText = elements.btnSaveRules.innerHTML;
        elements.btnSaveRules.disabled = true;
        elements.btnSaveRules.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Menyimpan...';

        const lines = elements.rulesTextarea.value.split('\n');

        try {
            const res = await fetch('/api/adblocker/rules', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ rules: lines })
            });
            const data = await res.json();

            if (res.ok && data.success) {
                showToast(`Aturan berhasil disimpan (${data.rules_count} rules aktif).`, 'success');
                updateRulesCount(data.rules_count);
            } else {
                showToast(`Gagal menyimpan aturan: ${data.error || 'Akses ditolak'}`, 'error');
            }
        } catch (err) {
            showToast(`Kesalahan jaringan: ${err.message}`, 'error');
        } finally {
            elements.btnSaveRules.disabled = false;
            elements.btnSaveRules.innerHTML = originalBtnText;
        }
    }

    function updateRulesCount(count) {
        if (elements.rulesCountBadge) {
            elements.rulesCountBadge.textContent = `${count} Aturan`;
        }
    }

    /**
     * Modal Pengaturan Koneksi
     */
    async function openSettingsModal() {
        try {
            const res = await fetch('/api/adblocker/config');
            const data = await res.json();

            if (res.ok && data.success && data.config) {
                currentConfig = data.config;
                elements.cfgHost.value = currentConfig.host || '127.0.0.1';
                elements.cfgPort.value = currentConfig.port || 8053;
                elements.cfgUser.value = currentConfig.username || '';
                elements.cfgPass.value = '';
                elements.cfgPass.placeholder = currentConfig.has_password ? 'Password tersimpan (kosongkan jika tidak diubah)' : 'Masukkan password';
                elements.cfgTls.checked = Boolean(currentConfig.tls);
            }
        } catch (err) {
            console.error('[AdBlocker] Gagal memuat config:', err);
        }

        elements.modalSettings.classList.add('open');
    }

    function closeSettingsModal() {
        elements.modalSettings.classList.remove('open');
    }

    async function handleSaveSettings(e) {
        e.preventDefault();

        const btn = elements.btnSaveSettings;
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Menguji koneksi...';

        const payload = {
            host: elements.cfgHost.value.trim(),
            port: parseInt(elements.cfgPort.value, 10),
            username: elements.cfgUser.value.trim(),
            password: elements.cfgPass.value,
            tls: elements.cfgTls.checked,
            timeout: 5
        };

        try {
            const res = await fetch('/api/adblocker/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();

            if (res.ok && data.success) {
                showToast(data.message || 'Pengaturan berhasil disimpan!', 'success');
                closeSettingsModal();
                await fetchStatus();
                await fetchRules();
            } else {
                showToast(`Gagal: ${data.error || 'Koneksi gagal'}`, 'error');
            }
        } catch (err) {
            showToast(`Kesalahan jaringan: ${err.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }

    /**
     * Modal Instalasi AdGuard Home via Docker
     */
    function openInstallModal() {
        if (!elements.modalInstall) return;
        if (elements.installLogBox) elements.installLogBox.style.display = 'none';
        if (elements.btnSubmitInstall) {
            elements.btnSubmitInstall.disabled = false;
            elements.btnSubmitInstall.innerHTML = '<i class="fa-solid fa-rocket"></i> Pasang Sekarang';
        }
        elements.modalInstall.classList.add('open');
    }

    function closeInstallModal() {
        if (!elements.modalInstall) return;
        elements.modalInstall.classList.remove('open');
    }

    async function handleSubmitInstall(e) {
        e.preventDefault();

        const btn = elements.btnSubmitInstall;
        const btnCancel = elements.btnCancelInstall;
        const logBox = elements.installLogBox;
        const logText = elements.installLogText;

        const webPort = parseInt(elements.instWebPort.value, 10) || 8053;
        const dnsPort = parseInt(elements.instDnsPort.value, 10) || 53;

        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Memasang...';
        if (btnCancel) btnCancel.disabled = true;

        if (logBox && logText) {
            logBox.style.display = 'block';
            logText.innerHTML = `
                <div><i class="fa-solid fa-circle-notch fa-spin"></i> Menghubungi Docker daemon...</div>
                <div><i class="fa-solid fa-cloud-arrow-down"></i> Mengunduh image adguard/adguardhome:latest...</div>
                <div><i class="fa-solid fa-gears"></i> Menyiapkan volume persistensi dan port binding...</div>
            `;
        }

        try {
            const res = await fetch('/api/adblocker/install', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ web_port: webPort, dns_port: dnsPort })
            });
            const data = await res.json();

            if (res.ok && data.success) {
                if (logText) {
                    logText.innerHTML += `<div style="color: #34d399;"><i class="fa-solid fa-circle-check"></i> ${escapeHtml(data.message)}</div>`;
                }
                showToast('AdGuard Home berhasil dipasang!', 'success');

                setTimeout(() => {
                    closeInstallModal();
                    fetchStatus();
                    fetchRules();
                }, 2000);
            } else {
                if (logText) {
                    logText.innerHTML += `<div style="color: #f87171;"><i class="fa-solid fa-circle-xmark"></i> ${escapeHtml(data.error || 'Gagal memasang')}</div>`;
                }
                showToast(`Gagal memasang: ${data.error || 'Terjadi kesalahan'}`, 'error');
            }
        } catch (err) {
            if (logText) {
                logText.innerHTML += `<div style="color: #f87171;"><i class="fa-solid fa-circle-xmark"></i> Kesalahan jaringan: ${escapeHtml(err.message)}</div>`;
            }
            showToast(`Kesalahan jaringan: ${err.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-rocket"></i> Pasang Sekarang';
            if (btnCancel) btnCancel.disabled = false;
        }
    }

    /**
     * Escape HTML untuk keamanan DOM
     */
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    /**
     * Event Listeners Registration
     */
    function setupEventListeners() {
        if (elements.btnRefresh) {
            elements.btnRefresh.addEventListener('click', () => {
                showToast('Memperbarui data AdBlocker...', 'success');
                fetchStatus();
                fetchRules();
            });
        }

        if (elements.toggleProtection) {
            elements.toggleProtection.addEventListener('change', handleToggleProtection);
        }

        if (elements.btnSaveRules) {
            elements.btnSaveRules.addEventListener('click', handleSaveRules);
        }

        if (elements.rulesTextarea) {
            elements.rulesTextarea.addEventListener('input', () => {
                const count = elements.rulesTextarea.value.split('\n').filter(l => l.trim().length > 0).length;
                updateRulesCount(count);
            });
        }

        // Modal triggers
        if (elements.btnOpenSettings) elements.btnOpenSettings.addEventListener('click', openSettingsModal);
        if (elements.btnOfflineConfig) elements.btnOfflineConfig.addEventListener('click', openSettingsModal);
        if (elements.btnCloseModal) elements.btnCloseModal.addEventListener('click', closeSettingsModal);
        if (elements.btnCancelSettings) elements.btnCancelSettings.addEventListener('click', closeSettingsModal);
        if (elements.formSettings) elements.formSettings.addEventListener('submit', handleSaveSettings);

        // Install Modal triggers
        if (elements.btnOpenInstall) elements.btnOpenInstall.addEventListener('click', openInstallModal);
        if (elements.btnCloseInstallModal) elements.btnCloseInstallModal.addEventListener('click', closeInstallModal);
        if (elements.btnCancelInstall) elements.btnCancelInstall.addEventListener('click', closeInstallModal);
        if (elements.formInstall) elements.formInstall.addEventListener('submit', handleSubmitInstall);

        // Tutup modal jika klik di backdrop
        if (elements.modalSettings) {
            elements.modalSettings.addEventListener('click', (e) => {
                if (e.target === elements.modalSettings) {
                    closeSettingsModal();
                }
            });
        }
        if (elements.modalInstall) {
            elements.modalInstall.addEventListener('click', (e) => {
                if (e.target === elements.modalInstall) {
                    closeInstallModal();
                }
            });
        }

        // Auto polling saat dokumen aktif
        autoRefreshTimer = setInterval(() => {
            if (!document.hidden) {
                fetchStatus();
            }
        }, 8000);
    }

    // Inisialisasi saat DOM siap
    document.addEventListener('DOMContentLoaded', () => {
        setupEventListeners();
        fetchStatus();
        fetchRules();
    });

})();

