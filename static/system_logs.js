/**
 * System Logs & Journald Explorer
 * Pure external JavaScript module for Eka Dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
    // State management
    let activeTab = 'tabJournal';
    let journalAutoRefreshTimer = null;
    let journalUnitsLoaded = false;
    let searchDebounce = null;

    // Elements
    const statErrors24h = document.getElementById('statErrors24h');
    const statSshFailed24h = document.getElementById('statSshFailed24h');
    const statOomEvents = document.getElementById('statOomEvents');
    const statKernelAlerts = document.getElementById('statKernelAlerts');
    const btnRefreshAll = document.getElementById('btnRefreshAll');

    // Tab buttons & panes
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    // Journald Tab Elements
    const journalUnitSelect = document.getElementById('journalUnitSelect');
    const journalPrioritySelect = document.getElementById('journalPrioritySelect');
    const journalSinceSelect = document.getElementById('journalSinceSelect');
    const journalLimitSelect = document.getElementById('journalLimitSelect');
    const journalSearchInput = document.getElementById('journalSearchInput');
    const btnJournalAutoRefresh = document.getElementById('btnJournalAutoRefresh');
    const btnJournalCopy = document.getElementById('btnJournalCopy');
    const journalLogViewport = document.getElementById('journalLogViewport');

    // Auth Tab Elements
    const authSinceSelect = document.getElementById('authSinceSelect');
    const authStatusSelect = document.getElementById('authStatusSelect');
    const authStatsBadge = document.getElementById('authStatsBadge');
    const btnAuthRefresh = document.getElementById('btnAuthRefresh');
    const attackersList = document.getElementById('attackersList');
    const authEventsFeed = document.getElementById('authEventsFeed');

    // Kernel dmesg Tab Elements
    const oomHealthPill = document.getElementById('oomHealthPill');
    const diskHealthPill = document.getElementById('diskHealthPill');
    const dmesgLevelSelect = document.getElementById('dmesgLevelSelect');
    const dmesgLimitSelect = document.getElementById('dmesgLimitSelect');
    const dmesgSearchInput = document.getElementById('dmesgSearchInput');
    const btnDmesgCopy = document.getElementById('btnDmesgCopy');
    const btnDmesgRefresh = document.getElementById('btnDmesgRefresh');
    const dmesgLogViewport = document.getElementById('dmesgLogViewport');

    // Toast
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toastMsg');

    // Helper: Toast
    function showToast(message, isError = false) {
        if (!toast || !toastMsg) return;
        toastMsg.textContent = message;
        toast.style.borderColor = isError ? 'var(--danger)' : 'var(--glass-border)';
        toast.style.display = 'flex';
        setTimeout(() => {
            toast.style.display = 'none';
        }, 3200);
    }

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

    // Tab Navigation
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-tab');
            if (targetId === activeTab) return;

            tabButtons.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const targetPane = document.getElementById(targetId);
            if (targetPane) targetPane.classList.add('active');
            activeTab = targetId;

            // Load data for newly active tab
            if (activeTab === 'tabJournal') {
                fetchJournalLogs();
            } else if (activeTab === 'tabAuth') {
                fetchAuthAudit();
            } else if (activeTab === 'tabDmesg') {
                fetchDmesg();
            }
        });
    });

    // 1. Fetch Summary Stats (24h)
    async function fetchSummary() {
        try {
            const res = await fetch('/api/logs/summary');
            if (!res.ok) return;
            const data = await res.json();

            if (statErrors24h) statErrors24h.textContent = data.errors_24h ?? 0;
            if (statSshFailed24h) statSshFailed24h.textContent = data.ssh_failed_24h ?? 0;
            if (statOomEvents) statOomEvents.textContent = data.oom_events ?? 0;
            if (statKernelAlerts) statKernelAlerts.textContent = data.kernel_alerts ?? 0;
        } catch (e) {
            console.error('Error fetching logs summary:', e);
        }
    }

    // 2. Fetch Active Units for Dropdown
    async function fetchUnits() {
        if (journalUnitsLoaded) return;
        try {
            const res = await fetch('/api/logs/units');
            if (!res.ok) return;
            const data = await res.json();
            const units = data.units || [];

            // Populate unit select
            if (journalUnitSelect) {
                // Keep the first default option
                journalUnitSelect.innerHTML = '<option value="">Semua Service Host</option>';
                units.forEach(u => {
                    const opt = document.createElement('option');
                    opt.value = u.unit;
                    opt.textContent = `${u.name} (${u.unit})`;
                    journalUnitSelect.appendChild(opt);
                });
                journalUnitsLoaded = true;
            }
        } catch (e) {
            console.error('Error fetching units:', e);
        }
    }

    // 3. Fetch Journald Logs
    async function fetchJournalLogs() {
        if (!journalLogViewport) return;

        const unit = journalUnitSelect ? journalUnitSelect.value : '';
        const priority = journalPrioritySelect ? journalPrioritySelect.value : 'all';
        const since = journalSinceSelect ? journalSinceSelect.value : '1h';
        const limit = journalLimitSelect ? journalLimitSelect.value : '100';
        const q = journalSearchInput ? journalSearchInput.value.trim() : '';

        const params = new URLSearchParams({
            unit,
            priority,
            since,
            limit,
            q
        });

        try {
            const res = await fetch(`/api/logs/journal?${params.toString()}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const entries = data.entries || [];

            if (entries.length === 0) {
                journalLogViewport.innerHTML = `
                    <div class="empty-state">
                        <i class="fa-solid fa-circle-info"></i>
                        <span>Tidak ada log journald ditemukan untuk kriteria filter ini.</span>
                    </div>
                `;
                return;
            }

            let html = '';
            entries.forEach(e => {
                const pLabel = e.priority_label || 'info';
                const unitHtml = e.unit ? `<span class="log-unit">${escapeHtml(e.unit)}</span>` : '';
                const pidHtml = e.pid ? `<span class="log-pid">[${escapeHtml(e.pid)}]</span>` : '';

                html += `
                    <div class="log-entry">
                        <span class="log-ts">${escapeHtml(e.timestamp)}</span>
                        <span class="priority-badge ${pLabel}">${escapeHtml(pLabel)}</span>
                        ${unitHtml}
                        ${pidHtml}
                        <span class="log-msg">${escapeHtml(e.message)}</span>
                    </div>
                `;
            });

            journalLogViewport.innerHTML = html;
        } catch (e) {
            journalLogViewport.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation" style="color: var(--danger);"></i>
                    <span>Gagal memuat log journald: ${escapeHtml(e.message)}</span>
                </div>
            `;
        }
    }

    // 4. Fetch SSH & Auth Audit
    async function fetchAuthAudit() {
        if (!authEventsFeed) return;

        const since = authSinceSelect ? authSinceSelect.value : '24h';
        const status = authStatusSelect ? authStatusSelect.value : 'all';

        const params = new URLSearchParams({ since, status });

        try {
            const res = await fetch(`/api/logs/auth?${params.toString()}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const stats = data.stats || {};
            const events = data.events || [];
            const attackers = data.top_attackers || [];

            // Update stats badge
            if (authStatsBadge) {
                authStatsBadge.innerHTML = `
                    <span style="color:#f87171;"><i class="fa-solid fa-xmark"></i> Failed: ${stats.failed || 0}</span> | 
                    <span style="color:#34d399;"><i class="fa-solid fa-check"></i> Accepted: ${stats.accepted || 0}</span> | 
                    <span style="color:#c084fc;"><i class="fa-solid fa-terminal"></i> Sudo: ${stats.sudo || 0}</span>
                `;
            }

            // Render Top Attackers
            if (attackersList) {
                if (attackers.length === 0) {
                    attackersList.innerHTML = `
                        <div class="empty-state" style="padding: 24px 0;">
                            <i class="fa-solid fa-shield-check" style="color: var(--success); font-size: 1.8rem;"></i>
                            <span>Tidak ada aktivitas penyerang mencurigakan.</span>
                        </div>
                    `;
                } else {
                    let aHtml = '';
                    attackers.forEach(att => {
                        const usersTargeted = (att.users || []).join(', ') || 'unknown';
                        aHtml += `
                            <div class="attacker-item">
                                <div style="display:flex; flex-direction:column; gap:2px;">
                                    <div class="attacker-ip">${escapeHtml(att.ip)}</div>
                                    <div class="attacker-meta">Target: <b>${escapeHtml(usersTargeted)}</b> • ${att.count}x percobaan</div>
                                    <div class="attacker-meta" style="color:#64748b;">Terakhir: ${escapeHtml(att.last_seen)}</div>
                                </div>
                                <button class="btn-ban" data-ip="${escapeHtml(att.ip)}" title="Blokir IP via iptables">
                                    <i class="fa-solid fa-ban"></i> Ban IP
                                </button>
                            </div>
                        `;
                    });
                    attackersList.innerHTML = aHtml;

                    // Attach Ban IP listeners
                    attackersList.querySelectorAll('.btn-ban').forEach(btn => {
                        btn.addEventListener('click', async (evt) => {
                            const ip = evt.currentTarget.getAttribute('data-ip');
                            if (!confirm(`Blokir alamat IP ${ip} dari firewall server host?`)) return;

                            try {
                                const bRes = await fetch('/api/websites/threats/block', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ ip })
                                });
                                const bData = await bRes.json();
                                if (bData.success) {
                                    showToast(`IP ${ip} berhasil diblokir via iptables.`);
                                    fetchAuthAudit();
                                } else {
                                    showToast(`Gagal blokir: ${bData.error || 'Unknown'}`, true);
                                }
                            } catch (err) {
                                showToast(`Gagal request blokir: ${err.message}`, true);
                            }
                        });
                    });
                }
            }

            // Render Auth Events Feed
            if (events.length === 0) {
                authEventsFeed.innerHTML = `
                    <div class="empty-state">
                        <i class="fa-solid fa-circle-info"></i>
                        <span>Tidak ada event autentikasi ditemukan pada rentang waktu ini.</span>
                    </div>
                `;
                return;
            }

            let eHtml = '';
            events.forEach(ev => {
                const type = ev.type || 'info';
                let typeBadge = '';
                let detailText = '';

                if (type === 'failed') {
                    typeBadge = '<span class="priority-badge err"><i class="fa-solid fa-xmark"></i> FAILED LOGIN</span>';
                    detailText = `Upaya login SSH gagal untuk user <b>${escapeHtml(ev.user)}</b> dari IP <code>${escapeHtml(ev.ip)}:${escapeHtml(ev.port)}</code>`;
                } else if (type === 'accepted') {
                    typeBadge = '<span class="priority-badge info" style="background:var(--success-bg); color:#34d399; border-color:rgba(16,185,129,0.3);"><i class="fa-solid fa-check"></i> ACCEPTED</span>';
                    detailText = `Login SSH berhasil via <b>${escapeHtml(ev.method || 'publickey')}</b> untuk user <b>${escapeHtml(ev.user)}</b> dari IP <code>${escapeHtml(ev.ip)}:${escapeHtml(ev.port)}</code>`;
                } else if (type === 'sudo') {
                    typeBadge = '<span class="priority-badge" style="background:var(--purple-bg); color:#c084fc; border:1px solid rgba(168,85,247,0.3);"><i class="fa-solid fa-terminal"></i> SUDO</span>';
                    detailText = `User <b>${escapeHtml(ev.user)}</b> menjalankan: <code>${escapeHtml(ev.command)}</code> sebagai <b>${escapeHtml(ev.target_user || 'root')}</b>`;
                }

                eHtml += `
                    <div class="event-card ${type}">
                        <div class="event-content">
                            <div class="event-top">
                                <div style="display:flex; align-items:center; gap:8px;">
                                    ${typeBadge}
                                    <span class="event-user">${escapeHtml(ev.user)}</span>
                                </div>
                                <span class="event-time">${escapeHtml(ev.timestamp)}</span>
                            </div>
                            <div class="event-detail">${detailText}</div>
                        </div>
                    </div>
                `;
            });

            authEventsFeed.innerHTML = eHtml;
        } catch (e) {
            authEventsFeed.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation" style="color: var(--danger);"></i>
                    <span>Gagal memuat audit log autentikasi: ${escapeHtml(e.message)}</span>
                </div>
            `;
        }
    }

    // 5. Fetch Kernel dmesg
    async function fetchDmesg() {
        if (!dmesgLogViewport) return;

        const level = dmesgLevelSelect ? dmesgLevelSelect.value : 'all';
        const limit = dmesgLimitSelect ? dmesgLimitSelect.value : '150';
        const q = dmesgSearchInput ? dmesgSearchInput.value.trim() : '';

        const params = new URLSearchParams({ level, limit, q });

        try {
            const res = await fetch(`/api/logs/dmesg?${params.toString()}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const entries = data.entries || [];
            const oomEvents = data.oom_events || [];
            const diskErrors = data.disk_errors || [];

            // Update health pills
            if (oomHealthPill) {
                if (oomEvents.length > 0) {
                    oomHealthPill.className = 'health-pill alert';
                    oomHealthPill.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> <span>OOM-Killer: ${oomEvents.length} Peristiwa Out of Memory Terdeteksi!</span>`;
                } else {
                    oomHealthPill.className = 'health-pill healthy';
                    oomHealthPill.innerHTML = `<i class="fa-solid fa-circle-check"></i> <span>OOM-Killer: Bebas Insiden Out of Memory</span>`;
                }
            }

            if (diskHealthPill) {
                if (diskErrors.length > 0) {
                    diskHealthPill.className = 'health-pill alert';
                    diskHealthPill.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> <span>Storage I/O: ${diskErrors.length} Disk/Hardware Error Terdeteksi!</span>`;
                } else {
                    diskHealthPill.className = 'health-pill healthy';
                    diskHealthPill.innerHTML = `<i class="fa-solid fa-hard-drive"></i> <span>Storage I/O: Bebas Hardware / Disk Error</span>`;
                }
            }

            if (entries.length === 0) {
                dmesgLogViewport.innerHTML = `
                    <div class="empty-state">
                        <i class="fa-solid fa-circle-info"></i>
                        <span>Tidak ada log kernel ring buffer ditemukan.</span>
                    </div>
                `;
                return;
            }

            let html = '';
            entries.forEach(e => {
                const tagClass = e.tag === 'err' ? 'err' : (e.tag === 'warn' ? 'warning' : (e.tag === 'crit' ? 'crit' : 'info'));
                const tagLabel = e.is_oom ? 'OOM' : (e.is_disk ? 'DISK-ERR' : e.tag.toUpperCase());

                html += `
                    <div class="log-entry">
                        <span class="log-ts">${escapeHtml(e.timestamp)}</span>
                        <span class="priority-badge ${tagClass}">${escapeHtml(tagLabel)}</span>
                        <span class="log-msg">${escapeHtml(e.message)}</span>
                    </div>
                `;
            });

            dmesgLogViewport.innerHTML = html;
        } catch (e) {
            dmesgLogViewport.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation" style="color: var(--danger);"></i>
                    <span>Gagal memuat dmesg: ${escapeHtml(e.message)}</span>
                </div>
            `;
        }
    }

    // Event Listeners: Journald Controls
    [journalUnitSelect, journalPrioritySelect, journalSinceSelect, journalLimitSelect].forEach(sel => {
        if (sel) sel.addEventListener('change', () => fetchJournalLogs());
    });

    if (journalSearchInput) {
        journalSearchInput.addEventListener('input', () => {
            clearTimeout(searchDebounce);
            searchDebounce = setTimeout(() => {
                fetchJournalLogs();
            }, 350);
        });
    }

    // Event Listeners: Auth Controls
    if (authSinceSelect) authSinceSelect.addEventListener('change', () => fetchAuthAudit());
    if (authStatusSelect) authStatusSelect.addEventListener('change', () => fetchAuthAudit());
    if (btnAuthRefresh) btnAuthRefresh.addEventListener('click', () => fetchAuthAudit());

    // Event Listeners: dmesg Controls
    if (dmesgLevelSelect) dmesgLevelSelect.addEventListener('change', () => fetchDmesg());
    if (dmesgLimitSelect) dmesgLimitSelect.addEventListener('change', () => fetchDmesg());
    if (btnDmesgRefresh) btnDmesgRefresh.addEventListener('click', () => fetchDmesg());

    if (dmesgSearchInput) {
        dmesgSearchInput.addEventListener('input', () => {
            clearTimeout(searchDebounce);
            searchDebounce = setTimeout(() => {
                fetchDmesg();
            }, 350);
        });
    }

    // Copy Handlers
    if (btnJournalCopy) {
        btnJournalCopy.addEventListener('click', () => {
            if (!journalLogViewport) return;
            const text = journalLogViewport.innerText;
            navigator.clipboard.writeText(text).then(() => {
                showToast('Log journald disalin ke clipboard.');
            }).catch(() => {
                showToast('Gagal menyalin log.', true);
            });
        });
    }

    if (btnDmesgCopy) {
        btnDmesgCopy.addEventListener('click', () => {
            if (!dmesgLogViewport) return;
            const text = dmesgLogViewport.innerText;
            navigator.clipboard.writeText(text).then(() => {
                showToast('Log dmesg disalin ke clipboard.');
            }).catch(() => {
                showToast('Gagal menyalin log.', true);
            });
        });
    }

    // Auto Refresh Toggle
    if (btnJournalAutoRefresh) {
        btnJournalAutoRefresh.addEventListener('click', () => {
            if (journalAutoRefreshTimer) {
                clearInterval(journalAutoRefreshTimer);
                journalAutoRefreshTimer = null;
                btnJournalAutoRefresh.classList.remove('active-glow');
                btnJournalAutoRefresh.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i> <span>Auto Refresh: OFF</span>';
                showToast('Auto refresh dinonaktifkan.');
            } else {
                journalAutoRefreshTimer = setInterval(() => {
                    fetchJournalLogs();
                    fetchSummary();
                }, 5000);
                btnJournalAutoRefresh.classList.add('active-glow');
                btnJournalAutoRefresh.innerHTML = '<i class="fa-solid fa-arrows-rotate fa-spin"></i> <span>Auto Refresh: 5s</span>';
                showToast('Auto refresh aktif tiap 5 detik.');
            }
        });
    }

    // Global Refresh Button
    if (btnRefreshAll) {
        btnRefreshAll.addEventListener('click', () => {
            fetchSummary();
            if (activeTab === 'tabJournal') fetchJournalLogs();
            else if (activeTab === 'tabAuth') fetchAuthAudit();
            else if (activeTab === 'tabDmesg') fetchDmesg();
            showToast('Seluruh data log disegarkan.');
        });
    }

    // Initial Load
    fetchSummary();
    fetchUnits();
    fetchJournalLogs();
});

