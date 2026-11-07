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
    let currentLanIp = '192.168.1.4';
    let currentTailscaleIp = '100.87.49.14';

    // DOM Elements
    const elements = {
        protectionBar: document.getElementById('protection-bar'),
        protectionIcon: document.getElementById('protection-icon'),
        badgeStatus: document.getElementById('badge-status'),
        protectionDesc: document.getElementById('protection-desc'),
        toggleProtection: document.getElementById('toggle-protection'),
        // Security Toggles
        toggleSafebrowsing: document.getElementById('toggle-safebrowsing'),
        toggleSafesearch: document.getElementById('toggle-safesearch'),
        toggleParental: document.getElementById('toggle-parental'),
        // Banners & Controls
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
        // IP Chips & Copy
        valLanIp: document.getElementById('val-lan-ip'),
        valTailscaleIp: document.getElementById('val-tailscale-ip'),
        btnCopyLan: document.getElementById('btn-copy-lan'),
        btnCopyTailscale: document.getElementById('btn-copy-tailscale'),
        // Metrics
        valTotalQueries: document.getElementById('val-total-queries'),
        valBlockedQueries: document.getElementById('val-blocked-queries'),
        valBlockedRatio: document.getElementById('val-blocked-ratio'),
        barBlockedRatio: document.getElementById('bar-blocked-ratio'),
        valAvgLatency: document.getElementById('val-avg-latency'),
        // Chart Canvas
        activityChart: document.getElementById('activity-chart'),
        // Tables
        tableBlockedBody: document.getElementById('table-blocked-body'),
        tableQueriedBody: document.getElementById('table-queried-body'),
        tableClientsBody: document.getElementById('table-clients-body'),
        badgeTopBlocked: document.getElementById('badge-top-blocked'),
        badgeTopQueried: document.getElementById('badge-top-queried'),
        badgeTopClients: document.getElementById('badge-top-clients'),
        btnRefreshClients: document.getElementById('btn-refresh-clients'),
        // Rename Client Modal
        modalRenameClient: document.getElementById('modal-rename-client'),
        btnCloseRenameModal: document.getElementById('btn-close-rename-modal'),
        btnCancelRename: document.getElementById('btn-cancel-rename'),
        formRenameClient: document.getElementById('form-rename-client'),
        btnSubmitRename: document.getElementById('btn-submit-rename'),
        renameClientIp: document.getElementById('rename-client-ip'),
        renameClientName: document.getElementById('rename-client-name'),
        // Query Log
        tableQuerylogBody: document.getElementById('table-querylog-body'),
        btnRefreshLog: document.getElementById('btn-refresh-log'),
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
     * Format angka ke format ribuan
     */
    function formatNumber(num) {
        if (typeof num !== 'number') return '0';
        return num.toLocaleString('id-ID');
    }

    /**
     * Menyalin teks ke clipboard
     */
    async function copyToClipboard(text, label) {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
            } else {
                const textarea = document.createElement('textarea');
                textarea.value = text;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
            }
            showToast(`${label} berhasil disalin! (${text})`, 'success');
        } catch (err) {
            showToast(`Gagal menyalin: ${err.message}`, 'error');
        }
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
     * Render antarmuka saat AdGuard Home offline
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

        // Update Quick Security Toggles
        if (elements.toggleSafebrowsing) elements.toggleSafebrowsing.checked = Boolean(data.safebrowsing_enabled);
        if (elements.toggleSafesearch) elements.toggleSafesearch.checked = Boolean(data.safesearch_enabled);
        if (elements.toggleParental) elements.toggleParental.checked = Boolean(data.parental_enabled);

        // Update Web Console Link (Selalu mengarah ke Port 8053 AdGuard Home pada host yang diakses)
        if (elements.linkWebConsole) {
            const clientHost = window.location.hostname;
            const port = data.web_port || 8053;
            elements.linkWebConsole.href = `${window.location.protocol}//${clientHost}:${port}`;
        }

        // Update Accurate DNS IPs (LAN vs Tailscale) - Tampilkan IP murni tanpa port untuk router
        if (data.lan_ips && data.lan_ips.length > 0) {
            currentLanIp = data.lan_ips[0].ip;
            if (elements.valLanIp) elements.valLanIp.textContent = currentLanIp;
        }
        if (data.tailscale_ips && data.tailscale_ips.length > 0) {
            currentTailscaleIp = data.tailscale_ips[0].ip;
            if (elements.valTailscaleIp) elements.valTailscaleIp.textContent = currentTailscaleIp;
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

        // Render 24-Hour Activity Chart
        renderActivityChart(stats.dns_queries || [], stats.blocked_filtering || []);

        // Render Tables
        renderDomainTable(elements.tableBlockedBody, elements.badgeTopBlocked, stats.top_blocked_domains || [], 'Blokir', 'Domain');
        renderDomainTable(elements.tableQueriedBody, elements.badgeTopQueried, stats.top_queried_domains || [], 'Permintaan', 'Domain');
        renderClientsTable(elements.tableClientsBody, elements.badgeTopClients, data.top_clients_formatted || stats.top_clients || [], total);
    }

    /**
     * Render Grafik Time-Series Aktivitas DNS 24 Jam via HTML5 Canvas
     */
    function renderActivityChart(totalQueries, blockedQueries) {
        const canvas = elements.activityChart;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const rect = canvas.parentElement.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;

        // Atur resolusi retina
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const width = rect.width;
        const height = rect.height;

        ctx.clearRect(0, 0, width, height);

        const len = Math.max(totalQueries.length, blockedQueries.length, 24);
        if (len === 0) return;

        // Cari nilai maksimum untuk skala Y
        let maxVal = 10;
        for (let i = 0; i < len; i++) {
            const t = totalQueries[i] || 0;
            if (t > maxVal) maxVal = t;
        }
        maxVal = Math.ceil(maxVal * 1.15); // Padding 15% atas

        const paddingBottom = 26;
        const paddingTop = 15;
        const paddingLeft = 35;
        const paddingRight = 15;
        const chartW = width - paddingLeft - paddingRight;
        const chartH = height - paddingTop - paddingBottom;

        // Gambar Grid Garis Horizontal
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = 1;
        ctx.fillStyle = '#64748b';
        ctx.font = '10px Inter, sans-serif';
        ctx.textAlign = 'right';

        const gridSteps = 4;
        for (let i = 0; i <= gridSteps; i++) {
            const y = paddingTop + (chartH / gridSteps) * i;
            const val = Math.round(maxVal - (maxVal / gridSteps) * i);
            ctx.beginPath();
            ctx.moveTo(paddingLeft, y);
            ctx.lineTo(width - paddingRight, y);
            ctx.stroke();
            ctx.fillText(val > 1000 ? (val / 1000).toFixed(1) + 'k' : val, paddingLeft - 6, y + 3);
        }

        // Gambar Garis Total Queries (Biru Cyan)
        drawChartLine(ctx, totalQueries, len, maxVal, paddingLeft, paddingTop, chartW, chartH, '#38bdf8', 'rgba(56, 189, 248, 0.25)');

        // Gambar Garis Blocked Queries (Merah)
        drawChartLine(ctx, blockedQueries, len, maxVal, paddingLeft, paddingTop, chartW, chartH, '#ef4444', 'rgba(239, 68, 68, 0.3)');

        // Label Sumbu X (Waktu 24h - Tiap 4 jam)
        ctx.fillStyle = '#94a3b8';
        ctx.textAlign = 'center';
        for (let i = 0; i < len; i += 4) {
            const x = paddingLeft + (chartW / (len - 1)) * i;
            const hourOffset = (24 - len + i);
            const hourLabel = `${hourOffset < 0 ? hourOffset + 24 : hourOffset}:00`;
            ctx.fillText(hourLabel, x, height - 6);
        }
    }

    function drawChartLine(ctx, dataArr, len, maxVal, pLeft, pTop, cW, cH, strokeColor, fillColor) {
        if (!dataArr || dataArr.length === 0) return;

        const points = [];
        for (let i = 0; i < len; i++) {
            const val = dataArr[i] || 0;
            const x = pLeft + (cW / (len - 1)) * i;
            const y = pTop + cH - (val / maxVal) * cH;
            points.push({ x, y });
        }

        // Area Fill Gradient
        ctx.beginPath();
        ctx.moveTo(points[0].x, pTop + cH);
        for (let i = 0; i < points.length; i++) {
            ctx.lineTo(points[i].x, points[i].y);
        }
        ctx.lineTo(points[points.length - 1].x, pTop + cH);
        ctx.closePath();

        const grad = ctx.createLinearGradient(0, pTop, 0, pTop + cH);
        grad.addColorStop(0, fillColor);
        grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = grad;
        ctx.fill();

        // Stroke Line
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i].x, points[i].y);
        }
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = 2.5;
        ctx.stroke();

        // Dots on points
        ctx.fillStyle = strokeColor;
        for (let i = 0; i < points.length; i += 3) {
            ctx.beginPath();
            ctx.arc(points[i].x, points[i].y, 3.5, 0, Math.PI * 2);
            ctx.fill();
        }
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

        if (badge) badge.textContent = `${items.length} Domain`;

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
     * Menentukan icon perangkat berdasarkan nama dan IP
     */
    function getDeviceIcon(name, ip) {
        const lowerName = (name || '').toLowerCase();
        if (lowerName.includes('router') || lowerName.includes('gateway') || ip === '192.168.1.1') {
            return 'fa-solid fa-network-wired';
        }
        if (lowerName.includes('phone') || lowerName.includes('hp') || lowerName.includes('android') || lowerName.includes('iphone') || lowerName.includes('ipad') || lowerName.includes('mobile')) {
            return 'fa-solid fa-mobile-screen';
        }
        if (lowerName.includes('server') || lowerName.includes('ekaharefa') || lowerName.includes('host') || lowerName.includes('lenovo')) {
            return 'fa-solid fa-server';
        }
        if (lowerName.includes('laptop') || lowerName.includes('pc') || lowerName.includes('desktop') || lowerName.includes('computer') || lowerName.includes('macbook')) {
            return 'fa-solid fa-laptop';
        }
        if (lowerName.includes('tv') || lowerName.includes('smarttv') || lowerName.includes('stb')) {
            return 'fa-solid fa-tv';
        }
        return 'fa-solid fa-desktop';
    }

    /**
     * Menentukan warna progress bar berdasarkan persentase
     */
    function getProgressClass(percent) {
        if (percent >= 40) return 'green';
        if (percent >= 10) return 'amber';
        return 'blue';
    }

    /**
     * Render daftar klien teratas lengkap dengan Nama Perangkat, Ikon, Persentase, dan Tombol Rename
     */
    function renderClientsTable(tbody, badge, clients, totalQueries = 0) {
        if (!tbody) return;

        if (!clients || clients.length === 0) {
            tbody.innerHTML = '<tr><td colspan="2" class="empty-hint">Belum ada klien aktif terdeteksi.</td></tr>';
            if (badge) badge.textContent = '0 Klien';
            return;
        }

        if (badge) badge.textContent = `${clients.length} Klien`;

        tbody.innerHTML = clients.slice(0, 10).map(item => {
            let ip = '';
            let name = '';
            let count = 0;
            let percent = 0;
            let hasCustomName = false;

            if (item && typeof item === 'object') {
                if ('ip' in item && 'count' in item) {
                    ip = item.ip;
                    name = item.name || 'Perangkat Tanpa Nama';
                    count = item.count;
                    percent = item.percent || 0;
                    hasCustomName = Boolean(item.has_custom_name);
                } else {
                    const keys = Object.keys(item);
                    if (keys.length > 0) {
                        ip = keys[0];
                        count = item[ip];
                        name = ip === '192.168.1.1' ? 'Router / Gateway' : 'Perangkat Tanpa Nama';
                        percent = totalQueries > 0 ? Number(((count / totalQueries) * 100).toFixed(2)) : 0;
                    }
                }
            }

            const deviceIcon = getDeviceIcon(name, ip);
            const progressClass = getProgressClass(percent);
            const displayPercent = percent > 0 ? `${percent}%` : '<1%';

            return `
                <tr>
                    <td>
                        <div class="client-info-cell">
                            <div class="client-avatar" title="${escapeHtml(name)}">
                                <i class="${deviceIcon}"></i>
                            </div>
                            <div class="client-meta">
                                <div class="client-name-row">
                                    <span class="client-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span>
                                    <button type="button" class="btn-edit-client" data-ip="${escapeHtml(ip)}" data-name="${escapeHtml(name)}" title="Ganti Nama Perangkat">
                                        <i class="fa-solid fa-pencil"></i>
                                    </button>
                                </div>
                                <div class="client-ip-row">
                                    <span class="client-ip">${escapeHtml(ip)}</span>
                                    ${hasCustomName ? '<span class="client-tag">Kustom</span>' : ''}
                                </div>
                            </div>
                        </div>
                    </td>
                    <td style="text-align: right; vertical-align: middle;">
                        <div class="client-stat-cell">
                            <div class="client-count-row">
                                <strong class="client-count">${formatNumber(count)}</strong>
                                <span class="client-percent">${displayPercent}</span>
                            </div>
                            <div class="client-progress-bar" title="${displayPercent} dari total query">
                                <div class="client-progress-fill ${progressClass}" style="width: ${Math.min(100, Math.max(3, percent))}%;"></div>
                            </div>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        // Pasang event listener untuk tombol edit / rename klien
        const editButtons = tbody.querySelectorAll('.btn-edit-client');
        editButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const targetIp = btn.getAttribute('data-ip');
                const targetName = btn.getAttribute('data-name');
                openRenameModal(targetIp, targetName);
            });
        });
    }

    /**
     * Modal Rename Client
     */
    function openRenameModal(ip, currentName) {
        if (!elements.modalRenameClient) return;

        if (elements.renameClientIp) elements.renameClientIp.value = ip || '';
        if (elements.renameClientName) {
            elements.renameClientName.value = (currentName && currentName !== 'Perangkat Tanpa Nama') ? currentName : '';
        }

        elements.modalRenameClient.classList.add('open');
        setTimeout(() => {
            if (elements.renameClientName) elements.renameClientName.focus();
        }, 100);
    }

    function closeRenameModal() {
        if (!elements.modalRenameClient) return;
        elements.modalRenameClient.classList.remove('open');
    }

    async function handleSubmitRename(e) {
        e.preventDefault();

        const ip = elements.renameClientIp ? elements.renameClientIp.value.trim() : '';
        const name = elements.renameClientName ? elements.renameClientName.value.trim() : '';

        if (!ip || !name) {
            showToast('Nama perangkat tidak boleh kosong', 'error');
            return;
        }

        const btn = elements.btnSubmitRename;
        const originalText = btn ? btn.innerHTML : '';
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Menyimpan...';
        }

        try {
            const res = await fetch('/api/adblocker/client/rename', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ip, name })
            });
            const data = await res.json();

            if (res.ok && data.success) {
                showToast(data.message || `Perangkat ${ip} berhasil dinamai.`, 'success');
                closeRenameModal();
                await fetchStatus();
            } else {
                showToast(`Gagal: ${data.error || 'Terjadi kesalahan'}`, 'error');
            }
        } catch (err) {
            showToast(`Kesalahan jaringan: ${err.message}`, 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        }
    }

    /**
     * Mengambil riwayat query DNS langsung (Live Query Log)
     */
    async function fetchQueryLog() {
        if (!elements.tableQuerylogBody) return;

        try {
            const res = await fetch('/api/adblocker/querylog?limit=12');
            const data = await res.json();

            if (res.ok && data.success && Array.isArray(data.data)) {
                renderQueryLogTable(data.data);
            }
        } catch (err) {
            console.error('[AdBlocker] Gagal mengambil query log:', err);
        }
    }

    function renderQueryLogTable(logs) {
        const tbody = elements.tableQuerylogBody;
        if (!tbody) return;

        if (logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="empty-hint">Belum ada log query DNS terbaru.</td></tr>';
            return;
        }

        tbody.innerHTML = logs.map(item => {
            const isBlocked = item.reason && item.reason !== 'NotFilteredNotFound' && item.reason !== 'Rewrite';
            const statusClass = isBlocked ? 'pill-blocked' : 'pill-allowed';
            const statusText = isBlocked ? 'Blocked' : 'Processed';

            const timeStr = item.time ? new Date(item.time).toLocaleTimeString('id-ID') : '-';
            const client = item.client || item.client_proto || '-';
            const domain = item.question ? item.question.name : (item.name || '-');

            return `
                <tr>
                    <td style="color: var(--text-muted); font-family: monospace;">${escapeHtml(timeStr)}</td>
                    <td><span class="status-pill ${statusClass}">${statusText}</span></td>
                    <td class="domain-name" title="${domain}"><strong>${escapeHtml(domain)}</strong></td>
                    <td style="font-family: monospace; color: #a855f7;">${escapeHtml(client)}</td>
                </tr>
            `;
        }).join('');
    }

    /**
     * Toggle Proteksi DNS Master
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
                showToast(`Gagal: ${data.error || 'Unknown error'}`, 'error');
            }
        } catch (err) {
            e.target.checked = !targetState;
            showToast(`Kesalahan jaringan: ${err.message}`, 'error');
        } finally {
            e.target.disabled = false;
        }
    }

    /**
     * Toggle Fitur Keamanan Tambahan
     */
    async function handleToggleFeature(featureName, checkboxEl) {
        const targetState = checkboxEl.checked;
        checkboxEl.disabled = true;

        try {
            const res = await fetch(`/api/adblocker/feature/${featureName}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: targetState })
            });
            const data = await res.json();

            if (res.ok && data.success) {
                showToast(`Fitur ${featureName} ${targetState ? 'diaktifkan' : 'dinonaktifkan'}.`, 'success');
            } else {
                checkboxEl.checked = !targetState;
                showToast(`Gagal: ${data.error || 'Akses ditolak'}`, 'error');
            }
        } catch (err) {
            checkboxEl.checked = !targetState;
            showToast(`Kesalahan jaringan: ${err.message}`, 'error');
        } finally {
            checkboxEl.disabled = false;
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
                showToast(`Gagal: ${data.error || 'Akses ditolak'}`, 'error');
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
                fetchQueryLog();
            });
        }

        if (elements.btnRefreshLog) {
            elements.btnRefreshLog.addEventListener('click', () => {
                fetchQueryLog();
                showToast('Log DNS diperbarui', 'success');
            });
        }

        if (elements.toggleProtection) {
            elements.toggleProtection.addEventListener('change', handleToggleProtection);
        }

        // Quick Security Toggles
        if (elements.toggleSafebrowsing) {
            elements.toggleSafebrowsing.addEventListener('change', () => handleToggleFeature('safebrowsing', elements.toggleSafebrowsing));
        }
        if (elements.toggleSafesearch) {
            elements.toggleSafesearch.addEventListener('change', () => handleToggleFeature('safesearch', elements.toggleSafesearch));
        }
        if (elements.toggleParental) {
            elements.toggleParental.addEventListener('change', () => handleToggleFeature('parental', elements.toggleParental));
        }

        // Copy IP Handlers
        if (elements.btnCopyLan) {
            elements.btnCopyLan.addEventListener('click', () => copyToClipboard(currentLanIp, 'IP LAN Router'));
        }
        if (elements.btnCopyTailscale) {
            elements.btnCopyTailscale.addEventListener('click', () => copyToClipboard(currentTailscaleIp, 'IP Tailscale'));
        }

        // Rules
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

        // Rename Client Modal triggers
        if (elements.btnRefreshClients) {
            elements.btnRefreshClients.addEventListener('click', () => {
                showToast('Memperbarui daftar klien...', 'success');
                fetchStatus();
            });
        }
        if (elements.btnCloseRenameModal) elements.btnCloseRenameModal.addEventListener('click', closeRenameModal);
        if (elements.btnCancelRename) elements.btnCancelRename.addEventListener('click', closeRenameModal);
        if (elements.formRenameClient) elements.formRenameClient.addEventListener('submit', handleSubmitRename);

        // Install Modal triggers
        if (elements.btnOpenInstall) elements.btnOpenInstall.addEventListener('click', openInstallModal);
        if (elements.btnCloseInstallModal) elements.btnCloseInstallModal.addEventListener('click', closeInstallModal);
        if (elements.btnCancelInstall) elements.btnCancelInstall.addEventListener('click', closeInstallModal);
        if (elements.formInstall) elements.formInstall.addEventListener('submit', handleSubmitInstall);

        // Backdrop click
        if (elements.modalSettings) {
            elements.modalSettings.addEventListener('click', (e) => {
                if (e.target === elements.modalSettings) closeSettingsModal();
            });
        }
        if (elements.modalRenameClient) {
            elements.modalRenameClient.addEventListener('click', (e) => {
                if (e.target === elements.modalRenameClient) closeRenameModal();
            });
        }
        if (elements.modalInstall) {
            elements.modalInstall.addEventListener('click', (e) => {
                if (e.target === elements.modalInstall) closeInstallModal();
            });
        }

        // Resize window -> redraw chart
        window.addEventListener('resize', () => {
            fetchStatus();
        });

        // Auto polling
        autoRefreshTimer = setInterval(() => {
            if (!document.hidden) {
                fetchStatus();
                fetchQueryLog();
            }
        }, 8000);
    }

    // Inisialisasi saat DOM siap
    document.addEventListener('DOMContentLoaded', () => {
        setupEventListeners();
        fetchStatus();
        fetchRules();
        fetchQueryLog();
    });

})();
