/**
 * Alerting & Notification Engine (Universal Multi-Channel)
 * Eka Dashboard - Modular Frontend Logic
 * Zero Inline JS
 */

document.addEventListener('DOMContentLoaded', () => {
    let currentConfig = null;
    let selectedChannel = 'telegram';

    // DOM Elements - Stat Cards
    const statActiveChannel = document.getElementById('stat-active-channel');
    const statChannelSub = document.getElementById('stat-channel-sub');
    const statTotalAlerts = document.getElementById('stat-total-alerts');
    const statAlertsBreakdown = document.getElementById('stat-alerts-breakdown');
    const statSuccessRate = document.getElementById('stat-success-rate');
    const statLastTime = document.getElementById('stat-last-time');
    const statLastChannel = document.getElementById('stat-last-channel');
    const badgeHistoryCount = document.getElementById('badge-history-count');

    // Channel Selector Options
    const channelOptions = document.querySelectorAll('.channel-option');

    // Form Inputs - Telegram
    const inputTgToken = document.getElementById('input-tg-token');
    const inputTgChatId = document.getElementById('input-tg-chatid');
    const btnToggleToken = document.getElementById('btn-toggle-token');
    const iconEyeToken = document.getElementById('icon-eye-token');
    const btnTestTelegram = document.getElementById('btn-test-telegram');

    // Form Inputs - WhatsApp
    const inputWaUrl = document.getElementById('input-wa-url');
    const inputWaPhone = document.getElementById('input-wa-phone');
    const btnTestWhatsapp = document.getElementById('btn-test-whatsapp');
    const badgeWaStatus = document.getElementById('badge-wa-status');
    const btnCheckWa = document.getElementById('btn-check-wa');

    // Form Inputs - Webhook
    const inputWebhookUrl = document.getElementById('input-webhook-url');
    const btnTestWebhook = document.getElementById('btn-test-webhook');

    // Form Inputs - Rules
    const ruleCpuThreshold = document.getElementById('rule-cpu-threshold');
    const ruleCpuEnabled = document.getElementById('rule-cpu-enabled');
    const ruleRamThreshold = document.getElementById('rule-ram-threshold');
    const ruleRamEnabled = document.getElementById('rule-ram-enabled');
    const ruleDiskThreshold = document.getElementById('rule-disk-threshold');
    const ruleDiskEnabled = document.getElementById('rule-disk-enabled');
    const ruleSmartEnabled = document.getElementById('rule-smart-enabled');
    const ruleRebootEnabled = document.getElementById('rule-reboot-enabled');

    // Buttons
    const btnSaveConfig = document.getElementById('btn-save-config');
    const btnQuickTest = document.getElementById('btn-quick-test');
    const btnCheckSystem = document.getElementById('btn-check-system');
    const btnClearHistory = document.getElementById('btn-clear-history');

    // History Table
    const historyTableBody = document.getElementById('history-table-body');

    // Test Modal Elements
    const testModal = document.getElementById('test-alert-modal');
    const modalTestClose = document.getElementById('modal-test-close');
    const modalTestCancel = document.getElementById('modal-test-cancel');
    const modalTestSend = document.getElementById('modal-test-send');
    const modalTestChannel = document.getElementById('modal-test-channel');
    const modalTestMessage = document.getElementById('modal-test-message');

    // Tab Navigation
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            tabButtons.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            const activePane = document.getElementById(targetTab);
            if (activePane) activePane.classList.add('active');

            if (targetTab === 'tab-history') {
                fetchHistory();
            }
        });
    });

    // Helper: Escape HTML
    function escapeHtml(text) {
        if (!text) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Toast Notification Utility
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `glass`;
        toast.style.position = 'fixed';
        toast.style.bottom = '24px';
        toast.style.right = '24px';
        toast.style.zIndex = '9999';
        toast.style.padding = '14px 20px';
        toast.style.borderRadius = '12px';
        toast.style.display = 'flex';
        toast.style.alignItems = 'center';
        toast.style.gap = '10px';
        toast.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.4)';
        toast.style.border = '1px solid rgba(255, 255, 255, 0.15)';
        toast.style.fontSize = '13px';
        toast.style.fontWeight = '500';
        toast.style.color = '#fff';

        let icon = 'fa-info-circle';
        if (type === 'success') {
            toast.style.background = 'rgba(16, 185, 129, 0.9)';
            icon = 'fa-check-circle';
        } else if (type === 'error') {
            toast.style.background = 'rgba(239, 68, 68, 0.9)';
            icon = 'fa-exclamation-triangle';
        } else {
            toast.style.background = 'rgba(30, 41, 59, 0.95)';
        }

        toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${escapeHtml(message)}</span>`;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // Toggle Token Visibility
    btnToggleToken.addEventListener('click', () => {
        if (inputTgToken.type === 'password') {
            inputTgToken.type = 'text';
            iconEyeToken.className = 'fa-solid fa-eye-slash';
        } else {
            inputTgToken.type = 'password';
            iconEyeToken.className = 'fa-solid fa-eye';
        }
    });

    // Channel Option Selector Handlers
    channelOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            channelOptions.forEach(o => o.classList.remove('selected'));
            opt.classList.add('selected');
            selectedChannel = opt.getAttribute('data-channel');
            updateActiveChannelBadge(selectedChannel);
        });
    });

    function updateActiveChannelBadge(ch) {
        if (ch === 'telegram') {
            statActiveChannel.textContent = 'Telegram Bot';
            statChannelSub.textContent = 'Notifikasi via Telegram API';
        } else if (ch === 'whatsapp') {
            statActiveChannel.textContent = 'WhatsApp Gateway';
            statChannelSub.textContent = 'Notifikasi via WA Bridge API';
        } else if (ch === 'both') {
            statActiveChannel.textContent = 'Telegram & WA';
            statChannelSub.textContent = 'Kirim ganda secara paralel';
        } else if (ch === 'webhook') {
            statActiveChannel.textContent = 'Generic Webhook';
            statChannelSub.textContent = 'HTTP POST Webhook';
        }
    }

    // Fetch Config & Stats
    async function fetchConfig() {
        try {
            const res = await fetch('/api/alerts/config');
            const data = await res.json();
            if (!data.success) return;

            currentConfig = data.config;
            const stats = data.stats || {};

            // Populate Channel Selection
            selectedChannel = currentConfig.channel || 'telegram';
            channelOptions.forEach(opt => {
                if (opt.getAttribute('data-channel') === selectedChannel) {
                    opt.classList.add('selected');
                } else {
                    opt.classList.remove('selected');
                }
            });
            updateActiveChannelBadge(selectedChannel);

            // Populate Form - Telegram
            if (currentConfig.telegram) {
                inputTgToken.value = currentConfig.telegram.bot_token || '';
                inputTgChatId.value = currentConfig.telegram.chat_id || '';
            }

            // Populate Form - WhatsApp
            if (currentConfig.whatsapp) {
                inputWaUrl.value = currentConfig.whatsapp.gateway_url || 'http://127.0.0.1:3000/send';
                inputWaPhone.value = currentConfig.whatsapp.target_phone || '';
            }

            // Populate Form - Webhook
            if (currentConfig.webhook) {
                inputWebhookUrl.value = currentConfig.webhook.url || '';
            }

            // Populate Form - Rules
            if (currentConfig.rules) {
                const r = currentConfig.rules;
                ruleCpuThreshold.value = r.cpu_threshold || 90;
                ruleCpuEnabled.checked = !!r.cpu_enabled;
                ruleRamThreshold.value = r.ram_threshold || 85;
                ruleRamEnabled.checked = !!r.ram_enabled;
                ruleDiskThreshold.value = r.disk_threshold || 90;
                ruleDiskEnabled.checked = !!r.disk_enabled;
                ruleSmartEnabled.checked = !!r.smart_warning_enabled;
                ruleRebootEnabled.checked = !!r.reboot_required_enabled;
            }

            // Populate Stats Cards
            const total = stats.total_sent || 0;
            const succ = stats.success_count || 0;
            const fail = stats.failure_count || 0;
            statTotalAlerts.textContent = total;
            statAlertsBreakdown.textContent = `${succ} Berhasil, ${fail} Gagal`;

            if (total > 0) {
                const rate = Math.round((succ / total) * 100);
                statSuccessRate.textContent = `${rate}%`;
            } else {
                statSuccessRate.textContent = '100%';
            }

            if (stats.last_alert) {
                statLastTime.textContent = stats.last_alert.timestamp || 'Baru saja';
                statLastChannel.textContent = `Kanal: ${stats.last_alert.channel} (${stats.last_alert.success ? 'Sukses' : 'Gagal'})`;
            } else {
                statLastTime.textContent = 'Belum ada';
                statLastChannel.textContent = 'Menunggu trigger pertama';
            }

            // Periksa status gateway WhatsApp secara background
            checkWaStatus(true);

        } catch (err) {
            console.error('Error fetching alert config:', err);
            showToast('Gagal memuat konfigurasi alert', 'error');
        }
    }

    // Save Config
    btnSaveConfig.addEventListener('click', async () => {
        const payload = {
            channel: selectedChannel,
            telegram: {
                enabled: true,
                bot_token: inputTgToken.value.trim(),
                chat_id: inputTgChatId.value.trim()
            },
            whatsapp: {
                enabled: true,
                gateway_url: inputWaUrl.value.trim(),
                target_phone: inputWaPhone.value.trim()
            },
            webhook: {
                enabled: true,
                url: inputWebhookUrl.value.trim()
            },
            rules: {
                cpu_threshold: parseInt(ruleCpuThreshold.value) || 90,
                cpu_enabled: ruleCpuEnabled.checked,
                ram_threshold: parseInt(ruleRamThreshold.value) || 85,
                ram_enabled: ruleRamEnabled.checked,
                disk_threshold: parseInt(ruleDiskThreshold.value) || 90,
                disk_enabled: ruleDiskEnabled.checked,
                smart_warning_enabled: ruleSmartEnabled.checked,
                reboot_required_enabled: ruleRebootEnabled.checked
            }
        };

        btnSaveConfig.disabled = true;
        btnSaveConfig.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Menyimpan...';

        try {
            const res = await fetch('/api/alerts/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                showToast('Konfigurasi notifikasi berhasil disimpan!', 'success');
                fetchConfig();
            } else {
                showToast('Gagal menyimpan konfigurasi notifikasi', 'error');
            }
        } catch (err) {
            showToast(`Kesalahan: ${err.message}`, 'error');
        } finally {
            btnSaveConfig.disabled = false;
            btnSaveConfig.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Simpan Pengaturan';
        }
    });

    // Test Specific Channels
    async function testSingleChannel(channel, customCfg) {
        showToast(`Mengirim pesan tes ke ${channel}...`, 'info');
        try {
            const res = await fetch('/api/alerts/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    channel: channel,
                    custom_config: customCfg
                })
            });
            const data = await res.json();
            if (data.success) {
                showToast(`Tes kirim ke ${channel} BERHASIL!`, 'success');
            } else {
                const detail = data.results && data.results.length ? data.results[0].detail : 'Gagal mengirim pesan';
                showToast(`Tes kirim ${channel} GAGAL: ${detail}`, 'error');
            }
            fetchConfig();
            fetchHistory();
        } catch (err) {
            showToast(`Galat jaringan: ${err.message}`, 'error');
        }
    }

    btnTestTelegram.addEventListener('click', () => {
        const custom = {
            telegram: {
                bot_token: inputTgToken.value.trim(),
                chat_id: inputTgChatId.value.trim()
            }
        };
        testSingleChannel('telegram', custom);
    });

    // WhatsApp Gateway Health Checker
    async function checkWaStatus(silent = false) {
        if (!badgeWaStatus) return;
        badgeWaStatus.style.background = 'rgba(255, 255, 255, 0.08)';
        badgeWaStatus.style.color = '#94a3b8';
        badgeWaStatus.style.border = '1px solid rgba(255, 255, 255, 0.15)';
        badgeWaStatus.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Memeriksa Gateway...';

        try {
            const res = await fetch('/api/alerts/wa_status');
            const data = await res.json();
            if (data.online) {
                badgeWaStatus.style.background = 'rgba(37, 211, 102, 0.15)';
                badgeWaStatus.style.color = '#25D366';
                badgeWaStatus.style.border = '1px solid rgba(37, 211, 102, 0.3)';
                badgeWaStatus.innerHTML = '<i class="fa-solid fa-circle-check"></i> Gateway Terhubung';
                if (!silent) {
                    showToast('WhatsApp Gateway terhubung dan siap menerima pesan!', 'success');
                }
            } else {
                badgeWaStatus.style.background = 'rgba(255, 87, 87, 0.15)';
                badgeWaStatus.style.color = '#ff5757';
                badgeWaStatus.style.border = '1px solid rgba(255, 87, 87, 0.3)';
                badgeWaStatus.innerHTML = '<i class="fa-solid fa-circle-xmark"></i> Gateway Offline';
                if (!silent) {
                    showToast(`WhatsApp Gateway Offline: ${data.error || 'Port tidak aktif'}`, 'error');
                }
            }
        } catch (err) {
            badgeWaStatus.style.background = 'rgba(255, 87, 87, 0.15)';
            badgeWaStatus.style.color = '#ff5757';
            badgeWaStatus.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Gagal Memeriksa';
            if (!silent) {
                showToast(`Gagal memeriksa gateway: ${err.message}`, 'error');
            }
        }
    }

    if (btnCheckWa) {
        btnCheckWa.addEventListener('click', () => {
            checkWaStatus(false);
        });
    }

    btnTestWhatsapp.addEventListener('click', () => {
        const custom = {
            whatsapp: {
                gateway_url: inputWaUrl.value.trim(),
                target_phone: inputWaPhone.value.trim()
            }
        };
        testSingleChannel('whatsapp', custom);
    });

    btnTestWebhook.addEventListener('click', () => {
        const custom = {
            webhook: {
                url: inputWebhookUrl.value.trim()
            }
        };
        testSingleChannel('webhook', custom);
    });

    // Quick Test Modal Handlers
    btnQuickTest.addEventListener('click', () => {
        modalTestChannel.value = selectedChannel;
        testModal.classList.add('active');
    });

    function closeTestModal() {
        testModal.classList.remove('active');
    }

    modalTestClose.addEventListener('click', closeTestModal);
    modalTestCancel.addEventListener('click', closeTestModal);

    modalTestSend.addEventListener('click', async () => {
        const ch = modalTestChannel.value;
        const msg = modalTestMessage.value.trim();
        if (!msg) {
            showToast('Pesan tidak boleh kosong', 'error');
            return;
        }

        modalTestSend.disabled = true;
        modalTestSend.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Mengirim...';

        try {
            const res = await fetch('/api/alerts/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    channel: ch,
                    message: msg
                })
            });
            const data = await res.json();
            if (data.success) {
                showToast(`Pesan tes berhasil dikirim ke kanal [${ch}]!`, 'success');
                closeTestModal();
            } else {
                showToast('Pengiriman pesan tes gagal. Periksa log detail.', 'error');
            }
            fetchConfig();
            fetchHistory();
        } catch (err) {
            showToast(`Galat pengiriman: ${err.message}`, 'error');
        } finally {
            modalTestSend.disabled = false;
            modalTestSend.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Kirim Sekarang';
        }
    });

    // Check System Thresholds Now
    btnCheckSystem.addEventListener('click', async () => {
        btnCheckSystem.disabled = true;
        btnCheckSystem.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Memeriksa...';
        showToast('Memeriksa ambang batas sistem host...', 'info');

        try {
            const res = await fetch('/api/alerts/system_check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ send_alert: true })
            });
            const data = await res.json();
            if (data.triggered) {
                showToast(`Terdeteksi ${data.triggers.length} anomali! Notifikasi peringatan telah dikirim.`, 'error');
            } else {
                showToast('Semua parameter metrik sistem berada dalam batas aman normal.', 'success');
            }
            fetchConfig();
            fetchHistory();
        } catch (err) {
            showToast(`Galat evaluasi: ${err.message}`, 'error');
        } finally {
            btnCheckSystem.disabled = false;
            btnCheckSystem.innerHTML = '<i class="fa-solid fa-heart-pulse"></i> Cek Ambang Batas';
        }
    });

    // Fetch History
    async function fetchHistory() {
        try {
            const res = await fetch('/api/alerts/history');
            const data = await res.json();
            if (!data.success) return;

            const history = data.history || [];
            badgeHistoryCount.textContent = history.length;

            if (history.length === 0) {
                historyTableBody.innerHTML = `
                    <tr>
                        <td colspan="5">
                            <div class="empty-state">
                                <i class="fa-solid fa-bell-slash"></i>
                                <p>Belum ada riwayat notifikasi yang tercatat.</p>
                            </div>
                        </td>
                    </tr>
                `;
                return;
            }

            historyTableBody.innerHTML = history.map(h => {
                let badgeClass = 'badge-telegram';
                if (h.channel === 'whatsapp') badgeClass = 'badge-whatsapp';
                if (h.channel === 'both') badgeClass = 'badge-both';
                if (h.channel === 'webhook') badgeClass = 'badge-webhook';

                const resultsSummary = (h.results || []).map(r => 
                    `<div style="font-size: 11px; margin-top: 2px;"><strong>${escapeHtml(r.channel)}:</strong> ${escapeHtml(r.detail)}</div>`
                ).join('');

                return `
                    <tr>
                        <td style="font-family: 'JetBrains Mono', monospace; font-size: 12px; white-space: nowrap;">
                            ${escapeHtml(h.timestamp)}
                        </td>
                        <td>
                            <span class="badge ${badgeClass}">
                                <i class="fa-solid fa-paper-plane"></i> ${escapeHtml(h.channel.toUpperCase())}
                            </span>
                        </td>
                        <td>
                            <span class="badge ${h.success ? 'badge-success' : 'badge-failed'}">
                                <i class="fa-solid ${h.success ? 'fa-check' : 'fa-xmark'}"></i> ${h.success ? 'Terkirim' : 'Gagal'}
                            </span>
                        </td>
                        <td style="max-width: 320px; font-size: 12px; color: #e2e8f0;">
                            ${escapeHtml(h.message)}
                        </td>
                        <td style="max-width: 280px; color: var(--text-muted); font-size: 11px;">
                            ${resultsSummary || '-'}
                        </td>
                    </tr>
                `;
            }).join('');

        } catch (err) {
            console.error('Error fetching alert history:', err);
        }
    }

    // Clear History
    btnClearHistory.addEventListener('click', async () => {
        if (!confirm('Apakah Anda yakin ingin menghapus seluruh log riwayat pengiriman alert?')) return;

        try {
            const res = await fetch('/api/alerts/history/clear', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                showToast('Riwayat notifikasi berhasil dibersihkan', 'success');
                fetchHistory();
                fetchConfig();
            } else {
                showToast('Gagal membersihkan riwayat', 'error');
            }
        } catch (err) {
            showToast(`Galat: ${err.message}`, 'error');
        }
    });

    // Initial Load
    fetchConfig();
    fetchHistory();
});

