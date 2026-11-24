/**
 * Central Firewall Manager
 * Pure external JavaScript module for Eka Dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
    // State
    let activeTab = 'tabRules';
    let currentFilter = 'all';
    let allRules = [];
    let searchDebounce = null;

    // Header & Toggle elements
    const firewallToggleCheckbox = document.getElementById('firewallToggleCheckbox');
    const firewallStatusLabel = document.getElementById('firewallStatusLabel');
    const btnReloadFirewall = document.getElementById('btnReloadFirewall');
    const btnRefreshAll = document.getElementById('btnRefreshAll');

    // Stat card elements
    const statFirewallState = document.getElementById('statFirewallState');
    const statLoggingState = document.getElementById('statLoggingState');
    const statTotalRules = document.getElementById('statTotalRules');
    const statRulesSub = document.getElementById('statRulesSub');
    const statDefaultPolicy = document.getElementById('statDefaultPolicy');
    const statPolicySub = document.getElementById('statPolicySub');
    const statRateLimits = document.getElementById('statRateLimits');

    // Tabs
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    // Rules Tab Elements
    const pillButtons = document.querySelectorAll('.pill-btn');
    const countAll = document.getElementById('countAll');
    const countAllow = document.getElementById('countAllow');
    const countDeny = document.getElementById('countDeny');
    const countLimit = document.getElementById('countLimit');
    const rulesSearchInput = document.getElementById('rulesSearchInput');
    const rulesTableBody = document.getElementById('rulesTableBody');
    const btnOpenAddRule = document.getElementById('btnOpenAddRule');

    // Presets Buttons
    const btnApplySshLimit = document.getElementById('btnApplySshLimit');
    const btnApplyWebPorts = document.getElementById('btnApplyWebPorts');
    const btnApplyTailscaleMesh = document.getElementById('btnApplyTailscaleMesh');

    // Policy Tab Elements
    const selectPolicyIncoming = document.getElementById('selectPolicyIncoming');
    const selectPolicyOutgoing = document.getElementById('selectPolicyOutgoing');
    const selectPolicyRouted = document.getElementById('selectPolicyRouted');
    const btnSavePolicies = document.getElementById('btnSavePolicies');

    // Raw Tab Elements
    const rawIptablesViewport = document.getElementById('rawIptablesViewport');
    const btnCopyRawIptables = document.getElementById('btnCopyRawIptables');
    const btnRefreshRawIptables = document.getElementById('btnRefreshRawIptables');

    // Modal Add Rule Elements
    const modalAddRule = document.getElementById('modalAddRule');
    const btnCloseModal = document.getElementById('btnCloseModal');
    const btnCancelModal = document.getElementById('btnCancelModal');
    const btnSubmitAddRule = document.getElementById('btnSubmitAddRule');
    const modalAction = document.getElementById('modalAction');
    const modalPort = document.getElementById('modalPort');
    const modalProto = document.getElementById('modalProto');
    const modalFromIp = document.getElementById('modalFromIp');
    const modalInterface = document.getElementById('modalInterface');

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

            if (activeTab === 'tabRaw') {
                fetchRawIptables();
            }
        });
    });

    // 1. Fetch Firewall Status & Rules
    async function fetchFirewallStatus() {
        try {
            const res = await fetch('/api/firewall/status');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            const isActive = !!data.active;
            const backendName = (data.backend || 'ufw').toUpperCase();
            const stats = data.stats || {};
            const defaults = data.defaults || {};
            allRules = data.rules || [];

            // Update Master Toggle
            if (firewallToggleCheckbox) firewallToggleCheckbox.checked = isActive;
            if (firewallStatusLabel) {
                firewallStatusLabel.textContent = `Firewall (${backendName}): ${isActive ? 'Active' : 'Inactive'}`;
                firewallStatusLabel.style.color = isActive ? '#34d399' : '#f87171';
            }

            // Update Stat Cards
            if (statFirewallState) {
                statFirewallState.textContent = isActive ? 'ACTIVE' : 'INACTIVE';
                statFirewallState.style.color = isActive ? '#34d399' : '#f87171';
            }
            if (statLoggingState) statLoggingState.textContent = `Engine: ${backendName} | Log: ${data.logging || 'off'}`;

            if (statTotalRules) statTotalRules.textContent = stats.total_rules || 0;
            if (statRulesSub) statRulesSub.textContent = `${stats.v4_count || 0} IPv4 | ${stats.v6_count || 0} IPv6`;

            if (statDefaultPolicy) {
                statDefaultPolicy.textContent = (defaults.incoming || 'DENY').toUpperCase();
            }
            if (statPolicySub) {
                statPolicySub.textContent = `Out: ${defaults.outgoing || 'allow'} | Fwd: ${defaults.routed || 'allow'}`;
            }

            if (statRateLimits) statRateLimits.textContent = stats.limit_count || 0;

            // Update Pill Counts
            if (countAll) countAll.textContent = stats.total_rules || 0;
            if (countAllow) countAllow.textContent = stats.allow_count || 0;
            if (countDeny) countDeny.textContent = stats.deny_count || 0;
            if (countLimit) countLimit.textContent = stats.limit_count || 0;

            // Update Default Policies Form
            if (selectPolicyIncoming && defaults.incoming) selectPolicyIncoming.value = defaults.incoming.toLowerCase();
            if (selectPolicyOutgoing && defaults.outgoing) selectPolicyOutgoing.value = defaults.outgoing.toLowerCase();
            if (selectPolicyRouted && defaults.routed) selectPolicyRouted.value = defaults.routed.toLowerCase();

            renderRulesTable();
        } catch (e) {
            console.error('Error fetching firewall status:', e);
            if (rulesTableBody) {
                rulesTableBody.innerHTML = `
                    <tr>
                        <td colspan="6">
                            <div class="empty-state">
                                <i class="fa-solid fa-triangle-exclamation" style="color: var(--danger);"></i>
                                <span>Gagal memuat aturan firewall: ${escapeHtml(e.message)}</span>
                            </div>
                        </td>
                    </tr>
                `;
            }
        }
    }

    // 2. Render Rules Table
    function renderRulesTable() {
        if (!rulesTableBody) return;

        const query = rulesSearchInput ? rulesSearchInput.value.trim().toLowerCase() : '';

        const filtered = allRules.filter(r => {
            const action = (r.action || '').toUpperCase();
            const to = (r.to || '').toLowerCase();
            const from = (r.from || '').toLowerCase();

            // Filter by pill category
            if (currentFilter === 'allow' && !action.includes('ALLOW')) return false;
            if (currentFilter === 'deny' && (!action.includes('DENY') && !action.includes('REJECT'))) return false;
            if (currentFilter === 'limit' && !action.includes('LIMIT')) return false;

            // Search query filter
            if (query) {
                const matchTo = to.includes(query);
                const matchFrom = from.includes(query);
                const matchAction = action.toLowerCase().includes(query);
                const matchNum = String(r.num).includes(query);
                if (!matchTo && !matchFrom && !matchAction && !matchNum) return false;
            }

            return true;
        });

        if (filtered.length === 0) {
            rulesTableBody.innerHTML = `
                <tr>
                    <td colspan="6">
                        <div class="empty-state">
                            <i class="fa-solid fa-circle-info"></i>
                            <span>Tidak ada aturan firewall yang cocok dengan kriteria filter.</span>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        let html = '';
        filtered.forEach(r => {
            let actionClass = 'allow';
            let actionIcon = 'fa-check';

            if (r.action.includes('DENY') || r.action.includes('REJECT')) {
                actionClass = 'deny';
                actionIcon = 'fa-ban';
            } else if (r.action.includes('LIMIT')) {
                actionClass = 'limit';
                actionIcon = 'fa-gauge-high';
            }

            const ipBadge = r.is_v6
                ? '<span class="badge-v6">IPv6</span>'
                : '<span class="badge-v4">IPv4</span>';

            html += `
                <tr>
                    <td class="rule-num">#${r.num}</td>
                    <td>
                        <span class="rule-target">${escapeHtml(r.to)}</span>
                    </td>
                    <td>
                        <span class="rule-action-badge ${actionClass}">
                            <i class="fa-solid ${actionIcon}"></i>
                            ${escapeHtml(r.action)}
                        </span>
                    </td>
                    <td>
                        <span class="rule-source">${escapeHtml(r.from)}</span>
                    </td>
                    <td>${ipBadge}</td>
                    <td style="text-align: right;">
                        <button class="btn-del" data-num="${r.num}" title="Hapus Aturan #${r.num}">
                            <i class="fa-solid fa-trash-can"></i> Hapus
                        </button>
                    </td>
                </tr>
            `;
        });

        rulesTableBody.innerHTML = html;

        // Attach delete listeners
        rulesTableBody.querySelectorAll('.btn-del').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const num = e.currentTarget.getAttribute('data-num');
                if (!confirm(`Hapus aturan firewall urutan #${num}? Tindakan ini langsung diterapkan pada kernel host.`)) return;

                try {
                    const res = await fetch('/api/firewall/rule/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ num: parseInt(num) })
                    });
                    const resData = await res.json();
                    if (resData.success) {
                        showToast(`Aturan #${num} berhasil dihapus.`);
                        fetchFirewallStatus();
                    } else {
                        showToast(`Gagal menghapus: ${resData.error || 'Error'}`, true);
                    }
                } catch (err) {
                    showToast(`Error request: ${err.message}`, true);
                }
            });
        });
    }

    // 3. Filter Pills
    pillButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            pillButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.getAttribute('data-filter') || 'all';
            renderRulesTable();
        });
    });

    // Search Input with Debounce
    if (rulesSearchInput) {
        rulesSearchInput.addEventListener('input', () => {
            clearTimeout(searchDebounce);
            searchDebounce = setTimeout(() => {
                renderRulesTable();
            }, 250);
        });
    }

    // 4. Modal Add Rule
    if (btnOpenAddRule && modalAddRule) {
        btnOpenAddRule.addEventListener('click', () => {
            modalAddRule.style.display = 'flex';
            if (modalPort) modalPort.focus();
        });
    }

    function closeModal() {
        if (modalAddRule) modalAddRule.style.display = 'none';
        if (modalPort) modalPort.value = '';
        if (modalFromIp) modalFromIp.value = '';
        if (modalInterface) modalInterface.value = '';
    }

    if (btnCloseModal) btnCloseModal.addEventListener('click', closeModal);
    if (btnCancelModal) btnCancelModal.addEventListener('click', closeModal);

    if (btnSubmitAddRule) {
        btnSubmitAddRule.addEventListener('click', async () => {
            const action = modalAction ? modalAction.value : 'allow';
            const port = modalPort ? modalPort.value.trim() : '';
            const proto = modalProto ? modalProto.value : 'tcp';
            const from_ip = modalFromIp ? modalFromIp.value.trim() : '';
            const interface_name = modalInterface ? modalInterface.value.trim() : '';

            if (!port && !from_ip) {
                showToast('Harap tentukan Port atau IP Source.', true);
                return;
            }

            try {
                const res = await fetch('/api/firewall/rule/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        action,
                        port,
                        proto,
                        from_ip,
                        interface: interface_name,
                        direction: 'in'
                    })
                });
                const data = await res.json();
                if (data.success) {
                    showToast('Aturan firewall berhasil ditambahkan.');
                    closeModal();
                    fetchFirewallStatus();
                } else {
                    showToast(`Gagal: ${data.error || 'Unknown error'}`, true);
                }
            } catch (err) {
                showToast(`Error request: ${err.message}`, true);
            }
        });
    }

    // 5. Presets Handlers
    if (btnApplySshLimit) {
        btnApplySshLimit.addEventListener('click', async () => {
            if (!confirm('Terapkan rate-limiting pada Port 22/tcp SSH (maksimal 6 koneksi per 30 detik)?')) return;
            try {
                const res = await fetch('/api/firewall/rule/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        action: 'limit',
                        port: '22',
                        proto: 'tcp',
                        from_ip: 'any',
                        direction: 'in'
                    })
                });
                const data = await res.json();
                if (data.success) {
                    showToast('SSH Rate-Limiting berhasil diterapkan!');
                    fetchFirewallStatus();
                } else {
                    showToast(`Gagal: ${data.error || 'Error'}`, true);
                }
            } catch (err) {
                showToast(`Error: ${err.message}`, true);
            }
        });
    }

    if (btnApplyWebPorts) {
        btnApplyWebPorts.addEventListener('click', async () => {
            if (!confirm('Buka Port 80 (HTTP) dan Port 443 (HTTPS) untuk seluruh traffic publik?')) return;
            try {
                // Allow 80
                await fetch('/api/firewall/rule/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'allow', port: '80', proto: 'tcp', direction: 'in' })
                });
                // Allow 443
                const res = await fetch('/api/firewall/rule/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'allow', port: '443', proto: 'tcp', direction: 'in' })
                });
                const data = await res.json();
                if (data.success) {
                    showToast('Port 80 & 443 berhasil dibuka.');
                    fetchFirewallStatus();
                } else {
                    showToast(`Gagal: ${data.error || 'Error'}`, true);
                }
            } catch (err) {
                showToast(`Error: ${err.message}`, true);
            }
        });
    }

    if (btnApplyTailscaleMesh) {
        btnApplyTailscaleMesh.addEventListener('click', async () => {
            if (!confirm('Izinkan seluruh lalu lintas masuk dari antarmuka virtual tailscale0?')) return;
            try {
                const res = await fetch('/api/firewall/rule/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        action: 'allow',
                        interface: 'tailscale0',
                        direction: 'in'
                    })
                });
                const data = await res.json();
                if (data.success) {
                    showToast('Akses tailscale0 berhasil diizinkan.');
                    fetchFirewallStatus();
                } else {
                    showToast(`Gagal: ${data.error || 'Error'}`, true);
                }
            } catch (err) {
                showToast(`Error: ${err.message}`, true);
            }
        });
    }

    // 6. Default Policies Save
    if (btnSavePolicies) {
        btnSavePolicies.addEventListener('click', async () => {
            const incoming = selectPolicyIncoming ? selectPolicyIncoming.value : 'deny';
            const outgoing = selectPolicyOutgoing ? selectPolicyOutgoing.value : 'allow';
            const routed = selectPolicyRouted ? selectPolicyRouted.value : 'allow';

            if (!confirm(`Terapkan kebijakan default: Incoming=${incoming}, Outgoing=${outgoing}, Routed=${routed}?`)) return;

            try {
                await fetch('/api/firewall/default', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ direction: 'incoming', policy: incoming })
                });
                await fetch('/api/firewall/default', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ direction: 'outgoing', policy: outgoing })
                });
                const res = await fetch('/api/firewall/default', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ direction: 'routed', policy: routed })
                });
                const data = await res.json();
                if (data.success) {
                    showToast('Kebijakan default berhasil diperbarui.');
                    fetchFirewallStatus();
                } else {
                    showToast(`Gagal: ${data.error || 'Error'}`, true);
                }
            } catch (err) {
                showToast(`Error: ${err.message}`, true);
            }
        });
    }

    // 7. Master Toggle (Enable / Disable)
    if (firewallToggleCheckbox) {
        firewallToggleCheckbox.addEventListener('change', async (e) => {
            const enable = e.target.checked;
            const action = enable ? 'enable' : 'disable';

            if (!enable) {
                if (!confirm('PERINGATAN: Menonaktifkan firewall UFW akan membuka seluruh port sistem ke jaringan! Lanjutkan?')) {
                    e.target.checked = true;
                    return;
                }
            }

            try {
                const res = await fetch('/api/firewall/toggle', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action })
                });
                const data = await res.json();
                if (data.success) {
                    showToast(`Firewall berhasil di-${action}.`);
                    fetchFirewallStatus();
                } else {
                    showToast(`Gagal: ${data.error || 'Error'}`, true);
                    e.target.checked = !enable;
                }
            } catch (err) {
                showToast(`Error: ${err.message}`, true);
                e.target.checked = !enable;
            }
        });
    }

    // 8. Reload Firewall
    if (btnReloadFirewall) {
        btnReloadFirewall.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/firewall/reload', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    showToast('Aturan firewall berhasil dimuat ulang (reloaded).');
                    fetchFirewallStatus();
                } else {
                    showToast(`Gagal reload: ${data.error || 'Error'}`, true);
                }
            } catch (err) {
                showToast(`Error: ${err.message}`, true);
            }
        });
    }

    // 9. Fetch Raw Iptables / Nftables
    async function fetchRawIptables() {
        if (!rawIptablesViewport) return;
        rawIptablesViewport.textContent = 'Memuat aturan raw kernel filter...';

        try {
            const res = await fetch('/api/firewall/iptables');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            let out = '=== IPTABLES (FILTER TABLE) ===\n\n';
            out += data.iptables_v4 || 'Tidak ada data iptables tersedia.\n';

            if (data.nftables) {
                out += '\n\n=== NFTABLES (RULESET) ===\n\n';
                out += data.nftables;
            }

            rawIptablesViewport.textContent = out;
        } catch (e) {
            rawIptablesViewport.textContent = `Gagal memuat raw iptables: ${e.message}`;
        }
    }

    if (btnCopyRawIptables) {
        btnCopyRawIptables.addEventListener('click', () => {
            if (!rawIptablesViewport) return;
            navigator.clipboard.writeText(rawIptablesViewport.textContent).then(() => {
                showToast('Raw output disalin ke clipboard.');
            }).catch(() => {
                showToast('Gagal menyalin.', true);
            });
        });
    }

    if (btnRefreshRawIptables) {
        btnRefreshRawIptables.addEventListener('click', () => fetchRawIptables());
    }

    // Global Refresh
    if (btnRefreshAll) {
        btnRefreshAll.addEventListener('click', () => {
            fetchFirewallStatus();
            if (activeTab === 'tabRaw') fetchRawIptables();
            showToast('Data firewall disegarkan.');
        });
    }

    // Initial Load
    fetchFirewallStatus();
});

