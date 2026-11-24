/**
 * Eka Dashboard - VPN Manager Module
 * Handles Tailscale Mesh Network, WireGuard Server/Client Hub, ZeroTier, and Smart Scanning.
 */

let allTailscalePeers = [];
let currentConfig = '';
let currentClientName = '';
let currentTab = 'tailscale';

document.addEventListener('DOMContentLoaded', () => {
    switchTab('tailscale');
    loadTailscaleStatus();
    loadWireGuardStatus();
    loadZerotierStatus();

    // Tailscale search listener
    const tsSearch = document.getElementById('ts-search-input');
    if (tsSearch) {
        tsSearch.addEventListener('input', () => filterTailscalePeers());
    }
});

function showMsg(msg, type) {
    const el = document.getElementById('msg-box');
    if (!el) return;
    el.textContent = msg;
    el.className = 'msg ' + type;
    el.style.display = 'block';
    setTimeout(() => {
        el.className = 'msg';
        el.style.display = 'none';
    }, 5000);
}

function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab-section').forEach(sec => sec.style.display = 'none');
    document.querySelectorAll('.tab-nav-btn').forEach(btn => btn.classList.remove('active'));

    const targetSection = document.getElementById('section-' + tab);
    if (targetSection) targetSection.style.display = 'block';

    const activeBtn = document.querySelector(`.tab-nav-btn[data-tab="${tab}"]`);
    if (activeBtn) activeBtn.classList.add('active');

    if (tab === 'tailscale') {
        loadTailscaleStatus();
    } else if (tab === 'wireguard') {
        loadWireGuardStatus();
    } else if (tab === 'zerotier') {
        loadZerotierStatus();
    } else if (tab === 'smartscan') {
        runSmartScan();
    }
}

// ==================== TAB 1: TAILSCALE MESH NETWORK ====================

function loadTailscaleStatus() {
    const container = document.getElementById('ts-peer-list');
    if (container) {
        container.innerHTML = '<div style="text-align:center; padding:2.5rem; color:var(--text-dim); grid-column:1/-1"><i class="fa-solid fa-spinner fa-spin"></i> Memuat mesh Tailscale...</div>';
    }

    fetch('/api/vpn/tailscale/status')
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                showMsg(data.error, 'error');
                return;
            }

            updateTailscaleSelfNode(data);
            allTailscalePeers = data.peers || [];
            filterTailscalePeers();
        })
        .catch(err => {
            console.error('Error loading Tailscale status:', err);
            if (container) {
                container.innerHTML = '<div style="text-align:center; padding:2rem; color:var(--danger); grid-column:1/-1">Gagal memuat status Tailscale</div>';
            }
        });
}

function updateTailscaleSelfNode(data) {
    const node = data.self || {};
    const isRunning = data.running;

    const statusBadge = isRunning
        ? '<span class="status-pill up"><i class="fa-solid fa-circle-check"></i> Connected</span>'
        : '<span class="status-pill down"><i class="fa-solid fa-circle-xmark"></i> Stopped</span>';

    setText('ts-self-status-badge', statusBadge, true);
    setText('ts-self-hostname', node.hostname || 'Host Node');
    setText('ts-self-ip', node.primary_ip || '-');
    setText('ts-self-dns', node.dns_name || '-');
    setText('ts-self-derp', node.relay ? `Relay: ${node.relay}` : 'Direct');
    setText('ts-self-version', node.version || 'Tailscale');

    setText('ts-total-peers', data.peer_count || 0);
    setText('ts-online-peers', data.online_count || 0);
    setText('tab-ts-count', `${data.online_count || 0}/${data.peer_count || 0}`);
}

function filterTailscalePeers() {
    const query = (document.getElementById('ts-search-input')?.value || '').toLowerCase().trim();
    const filterMode = document.querySelector('input[name="ts-filter"]:checked')?.value || 'ALL';

    const filtered = allTailscalePeers.filter(p => {
        if (filterMode === 'ONLINE' && !p.online) return false;
        if (filterMode === 'ACTIVE') {
            const isDirect = Boolean(p.cur_addr && p.cur_addr.trim().length > 0);
            if (!isDirect) return false;
        }

        if (!query) return true;
        const name = (p.name || '').toLowerCase();
        const ip = (p.ip || '').toLowerCase();
        const dns = (p.dns_name || '').toLowerCase();
        return name.includes(query) || ip.includes(query) || dns.includes(query);
    });

    renderTailscalePeers(filtered);
}

function renderTailscalePeers(peers) {
    const container = document.getElementById('ts-peer-list');
    if (!container) return;

    if (!peers || peers.length === 0) {
        container.innerHTML = `
            <div style="text-align:center; padding:3rem; color:var(--text-dim); grid-column:1/-1">
                <i class="fa-solid fa-circle-nodes" style="font-size:2.5rem; opacity:0.3; margin-bottom:1rem"></i>
                <div>Tidak ada perangkat peer yang sesuai filter.</div>
            </div>`;
        return;
    }

    container.innerHTML = peers.map(p => {
        let osIcon = 'fa-linux';
        if (p.os === 'android') osIcon = 'fa-android';
        else if (p.os === 'windows') osIcon = 'fa-windows';
        else if (p.os === 'apple') osIcon = 'fa-apple';

        const isDirect = Boolean(p.cur_addr && p.cur_addr.trim().length > 0);
        let statusClass = 'down';
        let statusText = 'Offline';

        if (p.online) {
            if (isDirect) {
                statusClass = 'active';
                statusText = p.active ? 'Active Direct' : 'Direct P2P';
            } else {
                statusClass = 'relay';
                statusText = p.active ? 'Active (DERP)' : 'Online (DERP)';
            }
        }

        const connBadge = isDirect
            ? `<span class="conn-pill direct" title="${escapeHtml(p.cur_addr)}"><i class="fa-solid fa-bolt"></i> Direct (${escapeHtml(p.cur_addr)})</span>`
            : `<span class="conn-pill relay"><i class="fa-solid fa-tower-broadcast"></i> ${escapeHtml(p.conn_type)}</span>`;

        return `
        <div class="peer-card glass ${isDirect ? 'peer-active' : ''}">
            <div class="peer-top">
                <div class="peer-icon-box ${p.os}">
                    <i class="fa-brands ${osIcon}"></i>
                </div>
                <div class="peer-title-wrap">
                    <div class="peer-name" title="${escapeHtml(p.dns_name)}">${escapeHtml(p.name)}</div>
                    <span class="status-pill ${statusClass}">${statusText}</span>
                </div>
            </div>

            <div class="peer-meta-box">
                <div class="peer-field">
                    <span class="lbl">Tailscale IP:</span>
                    <span class="val ip">${escapeHtml(p.ip)}</span>
                </div>
                <div class="peer-field">
                    <span class="lbl">Koneksi:</span>
                    <span class="val">${connBadge}</span>
                </div>
            </div>

            <div class="peer-bottom">
                <div class="peer-traffic">
                    <span><i class="fa-solid fa-arrow-down"></i> ${formatBytes(p.rx_bytes)}</span>
                    <span><i class="fa-solid fa-arrow-up"></i> ${formatBytes(p.tx_bytes)}</span>
                </div>
                <button class="btn-peer-ping" onclick="runTailscalePing('${escapeHtml(p.ip)}', '${escapeHtml(p.name)}')" title="Ping ${escapeHtml(p.name)}">
                    <i class="fa-solid fa-satellite-dish"></i> Ping
                </button>
            </div>
        </div>`;
    }).join('');
}

function closeTailscalePingResult() {
    const resultBox = document.getElementById('ts-ping-result-box');
    if (resultBox) {
        resultBox.style.display = 'none';
        resultBox.innerHTML = '';
    }
}

function runTailscalePing(ip, name) {
    if (!ip) return;
    const resultBox = document.getElementById('ts-ping-result-box');
    if (resultBox) {
        resultBox.style.display = 'block';
        resultBox.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div style="color:var(--text-dim); display:flex; align-items:center; gap:8px;">
                    <i class="fa-solid fa-spinner fa-spin"></i> Melakukan Tailscale Ping ke <strong>${escapeHtml(name || ip)} (${escapeHtml(ip)})</strong>...
                </div>
                <button class="btn" style="padding:4px 8px; font-size:0.75rem; background:rgba(255,255,255,0.08);" onclick="closeTailscalePingResult()"><i class="fa-solid fa-xmark"></i></button>
            </div>`;
    }

    fetch('/api/vpn/tailscale/ping', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: ip })
    })
        .then(r => r.json())
        .then(data => {
            if (!resultBox) return;
            if (!data.reachable || !data.success) {
                const errMsg = data.message || data.error || 'Peer tidak merespons (Timeout / Peer offline atau dalam mode tidur)';
                resultBox.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                        <strong style="color:var(--warning); display:flex; align-items:center; gap:8px;">
                            <i class="fa-solid fa-triangle-exclamation"></i> Uji Ping: ${escapeHtml(name || ip)}
                        </strong>
                        <button class="btn" style="padding:4px 8px; font-size:0.75rem; background:rgba(255,255,255,0.08);" onclick="closeTailscalePingResult()"><i class="fa-solid fa-xmark"></i></button>
                    </div>
                    <div style="color:var(--text-dim); font-size:0.88rem; margin-bottom:0.5rem;">
                        ${escapeHtml(errMsg)}
                    </div>
                    <pre class="terminal-mini" style="margin-top:0.4rem; max-height:100px; font-size:0.75rem;">${escapeHtml(data.output || 'no reply')}</pre>
                `;
                return;
            }

            const latencyText = data.latency ? `${data.latency}` : 'N/A';
            const viaText = data.via || 'Direct P2P';

            resultBox.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                    <strong style="color:#ffffff; display:flex; align-items:center; gap:8px;">
                        <i class="fa-solid fa-circle-check" style="color:var(--ram-color)"></i> Hasil Ping: ${escapeHtml(name || ip)}
                    </strong>
                    <div style="display:flex; align-items:center; gap:10px;">
                        <span style="color:var(--accent-blue); font-weight:700"><i class="fa-solid fa-bolt"></i> ${escapeHtml(latencyText)} via ${escapeHtml(viaText)}</span>
                        <button class="btn" style="padding:4px 8px; font-size:0.75rem; background:rgba(255,255,255,0.08);" onclick="closeTailscalePingResult()"><i class="fa-solid fa-xmark"></i></button>
                    </div>
                </div>
                <pre class="terminal-mini">${escapeHtml(data.output || '')}</pre>
            `;
        })
        .catch(err => {
            if (resultBox) {
                resultBox.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="color:var(--danger); display:flex; align-items:center; gap:8px;"><i class="fa-solid fa-circle-xmark"></i> Gagal menghubungi endpoint ping: ${escapeHtml(err.message)}</div>
                        <button class="btn" style="padding:4px 8px; font-size:0.75rem; background:rgba(255,255,255,0.08);" onclick="closeTailscalePingResult()"><i class="fa-solid fa-xmark"></i></button>
                    </div>`;
            }
        });
}

// ==================== TAB 2: WIREGUARD HUB ====================

function loadWireGuardStatus() {
    fetch('/api/vpn/status')
        .then(r => r.json())
        .then(data => {
            updateWireGuardStatus(data);
            loadClients();
        })
        .catch(err => {
            updateWireGuardStatus({ installed: false });
        });
}

function updateWireGuardStatus(data) {
    const icon = document.getElementById('wg-status-icon');
    const title = document.getElementById('wg-status-title');
    const desc = document.getElementById('wg-status-desc');
    const actions = document.getElementById('wg-status-actions');
    const canManage = ['owner', 'admin'].includes(window.userRole);

    if (!data.installed) {
        if (icon) icon.className = 'status-icon not-installed';
        if (title) title.textContent = 'WireGuard Belum Terpasang';
        if (desc) {
            desc.innerHTML = `
                <div>WireGuard belum terpasang di host server. Perintah pemasangan host:</div>
                <code class="code-box">sudo apt-get update && sudo apt-get install -y wireguard</code>
            `;
        }
        if (actions) actions.innerHTML = '';
    } else if (data.running) {
        if (icon) icon.className = 'status-icon active';
        if (title) title.textContent = 'WireGuard Server Aktif';
        if (desc) {
            desc.innerHTML = `Server IP: <strong>${data.server_ip || 'N/A'}</strong> | Port: <strong>${data.port || '51820'}</strong> | Client: <strong>${data.client_count || 0}</strong>`;
        }
        if (actions) {
            actions.innerHTML = canManage ? '<button class="btn danger" onclick="controlVPN(\'stop\')"><i class="fa-solid fa-stop"></i> Stop Server</button>' : '';
        }
    } else {
        if (icon) icon.className = 'status-icon inactive';
        if (title) title.textContent = 'WireGuard Tidak Aktif';
        if (desc) desc.textContent = 'Layanan WireGuard terpasang di host namun daemon sedang berhenti.';
        if (actions) {
            actions.innerHTML = canManage ? '<button class="btn primary" onclick="controlVPN(\'start\')"><i class="fa-solid fa-play"></i> Start Server</button>' : '';
        }
    }
}

function loadClients() {
    fetch('/api/vpn/clients')
        .then(r => r.json())
        .then(data => {
            renderClients(data.clients || []);
        })
        .catch(() => {
            const container = document.getElementById('client-list');
            if (container) container.innerHTML = '<div class="empty-state">Gagal memuat daftar client WireGuard</div>';
        });
}

function renderClients(clients) {
    const container = document.getElementById('client-list');
    if (!container) return;
    const canManage = ['owner', 'admin'].includes(window.userRole);

    if (clients.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-user-slash" style="font-size:2rem; opacity:0.3; margin-bottom:0.5rem"></i>
                <div>Belum ada client WireGuard yang terdaftar.</div>
            </div>`;
        return;
    }

    container.innerHTML = clients.map(c => `
        <div class="client-item glass">
            <div class="client-icon">
                <i class="fa-solid fa-user-shield"></i>
            </div>
            <div class="client-info">
                <div class="client-name">${escapeHtml(c.name)}</div>
                <div class="client-meta">IP: <code>${escapeHtml(c.ip || 'N/A')}</code></div>
            </div>
            <div style="display:flex; gap:6px;">
                <button class="btn" onclick="showConfig('${escapeHtml(c.name)}')" title="Tampilkan QR Code & Config">
                    <i class="fa-solid fa-qrcode"></i>
                </button>
                ${canManage ? `
                    <button class="btn danger" onclick="removeClient('${escapeHtml(c.name)}')" title="Hapus Client">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                ` : ''}
            </div>
        </div>
    `).join('');
}

function addClient() {
    const name = (document.getElementById('client-name')?.value || '').trim();
    if (!name) {
        showMsg('Nama client harus diisi', 'error');
        return;
    }

    const btn = document.getElementById('btn-add');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Membuat...';

    fetch('/api/vpn/client/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    })
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-plus"></i> Buat Client';

            if (data.error) {
                showMsg(data.error, 'error');
            } else {
                showMsg('Client WireGuard berhasil dibuat!', 'success');
                const nameInput = document.getElementById('client-name');
                if (nameInput) nameInput.value = '';
                loadClients();
                if (data.config) {
                    showConfigModal(name, data.config);
                }
            }
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-plus"></i> Buat Client';
            showMsg('Gagal membuat client', 'error');
        });
}

function showConfig(name) {
    fetch(`/api/vpn/client/${name}/config`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                showMsg(data.error, 'error');
            } else {
                showConfigModal(name, data.config);
            }
        })
        .catch(() => showMsg('Gagal mengambil konfigurasi', 'error'));
}

function showConfigModal(name, config) {
    currentConfig = config;
    currentClientName = name;
    setText('modal-client-name', name);
    setText('config-text', config);

    // Generate QR Code if library available
    if (typeof qrcode !== 'undefined') {
        const qr = qrcode(0, 'M');
        qr.addData(config);
        qr.make();
        const qrBox = document.getElementById('qr-code');
        if (qrBox) qrBox.innerHTML = '<div class="qr-container">' + qr.createImgTag(4) + '</div>';
    }

    const modal = document.getElementById('config-modal');
    if (modal) modal.style.display = 'flex';
}

function closeModal() {
    const modal = document.getElementById('config-modal');
    if (modal) modal.style.display = 'none';
}

function copyConfig() {
    navigator.clipboard.writeText(currentConfig);
    showMsg('Konfigurasi berhasil disalin ke clipboard!', 'success');
}

function downloadConfig() {
    const blob = new Blob([currentConfig], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentClientName}.conf`;
    a.click();
    URL.revokeObjectURL(url);
}

function removeClient(name) {
    if (!confirm(`Hapus client WireGuard "${name}"?`)) return;

    fetch('/api/vpn/client/remove', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                showMsg(data.error, 'error');
            } else {
                showMsg('Client berhasil dihapus', 'success');
                loadClients();
            }
        })
        .catch(() => showMsg('Gagal menghapus client', 'error'));
}

function controlVPN(action) {
    fetch('/api/vpn/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
    })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                showMsg(data.error, 'error');
            } else {
                showMsg(`WireGuard berhasil di-${action}`, 'success');
                loadWireGuardStatus();
            }
        })
        .catch(() => showMsg('Gagal mengontrol WireGuard', 'error'));
}

// ==================== TAB 3: ZEROTIER & SMART SCAN ====================

function loadZerotierStatus() {
    fetch('/api/zerotier/status')
        .then(r => r.json())
        .then(data => {
            updateZerotierStatus(data);
        })
        .catch(() => {
            updateZerotierStatus({ installed: false });
        });
}

function updateZerotierStatus(data) {
    const icon = document.getElementById('zt-status-icon');
    const title = document.getElementById('zt-status-title');
    const desc = document.getElementById('zt-status-desc');

    if (!data.installed) {
        if (icon) icon.className = 'status-icon not-installed';
        if (title) title.textContent = 'ZeroTier Belum Terpasang';
        if (desc) {
            desc.innerHTML = `
                <div>Perintah pemasangan ZeroTier One di host:</div>
                <code class="code-box">curl -s https://install.zerotier.com | sudo bash</code>
            `;
        }
    } else if (data.running) {
        if (icon) icon.className = 'status-icon active';
        if (title) title.textContent = 'ZeroTier Online';
        if (desc) desc.innerHTML = `Node ID: <strong>${data.node_id || 'N/A'}</strong> | Networks: <strong>${(data.networks || []).length}</strong>`;
        renderZerotierNetworks(data.networks || []);
    } else {
        if (icon) icon.className = 'status-icon inactive';
        if (title) title.textContent = 'ZeroTier Offline';
        if (desc) desc.textContent = 'Service ZeroTier tidak berjalan. Gunakan: sudo systemctl start zerotier-one';
    }
}

function renderZerotierNetworks(networks) {
    const container = document.getElementById('zt-network-list');
    if (!container) return;
    const canManage = ['owner', 'admin'].includes(window.userRole);

    if (networks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-globe" style="font-size:2rem; opacity:0.3; margin-bottom:0.5rem"></i>
                <div>Belum terhubung ke network ZeroTier manapun.</div>
            </div>`;
        return;
    }

    container.innerHTML = networks.map(n => `
        <div class="client-item glass">
            <div class="client-icon">
                <i class="fa-solid fa-globe"></i>
            </div>
            <div class="client-info">
                <div class="client-name">${escapeHtml(n.network_id)}</div>
                <div class="client-meta">IP: <code>${escapeHtml(n.ip || 'Pending')}</code> | Status: ${escapeHtml(n.status || 'N/A')}</div>
            </div>
            ${canManage ? `
                <button class="btn danger" onclick="leaveZerotier('${escapeHtml(n.network_id)}')" title="Tinggalkan Network">
                    <i class="fa-solid fa-unlink"></i>
                </button>
            ` : ''}
        </div>
    `).join('');
}

function joinZerotier() {
    const networkId = (document.getElementById('zt-network-id')?.value || '').trim();
    if (!networkId) {
        showMsg('Network ID harus diisi', 'error');
        return;
    }

    const btn = document.getElementById('btn-join');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Menghubungkan...';

    fetch('/api/zerotier/join', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ networkId })
    })
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-link"></i> Gabung Network';

            if (data.error) {
                showMsg(data.error, 'error');
            } else {
                showMsg('Berhasil terhubung ke network ZeroTier!', 'success');
                const input = document.getElementById('zt-network-id');
                if (input) input.value = '';
                loadZerotierStatus();
            }
        })
        .catch(() => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-link"></i> Gabung Network';
            showMsg('Gagal menghubungkan ke network', 'error');
        });
}

function leaveZerotier(networkId) {
    if (!confirm(`Tinggalkan network ZeroTier "${networkId}"?`)) return;

    fetch('/api/zerotier/leave', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ networkId })
    })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                showMsg(data.error, 'error');
            } else {
                showMsg('Berhasil keluar dari network ZeroTier', 'success');
                loadZerotierStatus();
            }
        })
        .catch(() => showMsg('Gagal keluar dari network', 'error'));
}

function runSmartScan() {
    const container = document.getElementById('smart-scan-results');
    if (!container) return;
    container.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1;">
            <i class="fa-solid fa-spinner fa-spin" style="font-size:2rem; margin-bottom:1rem"></i>
            <div>Sedang memindai sistem host...</div>
        </div>
    `;

    fetch('/api/vpn/scan')
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                container.innerHTML = `<div class="msg error" style="display:block">${escapeHtml(data.error)}</div>`;
                return;
            }
            renderScanResults(data.services || []);
        })
        .catch(() => {
            container.innerHTML = '<div class="msg error" style="display:block">Gagal memindai sistem host</div>';
        });
}

function renderScanResults(services) {
    const container = document.getElementById('smart-scan-results');
    if (!container) return;

    if (services.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <i class="fa-solid fa-face-frown" style="font-size:3rem; opacity:0.3; margin-bottom:1rem"></i>
                <div>Tidak ada layanan VPN lain yang terdeteksi aktif di host</div>
            </div>`;
        return;
    }

    container.innerHTML = services.map(s => `
        <div class="card glass">
            <div class="card-body" style="display:flex; align-items:center; gap:1rem; padding:1.5rem">
                <div style="width:50px; height:50px; background:rgba(255,255,255,0.06); border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:1.5rem; color:${s.color}">
                    <i class="${s.icon}"></i>
                </div>
                <div style="flex:1">
                    <div style="font-weight:600; font-size:1.1rem; color:#fff">${escapeHtml(s.name)}</div>
                    <div style="color:var(--text-dim); font-size:0.85rem">Status: <span style="color:${s.status === 'Online' || s.status === 'Running' || s.status === 'Active' ? 'var(--success)' : 'var(--danger)'}; font-weight:600">${escapeHtml(s.status)}</span></div>
                </div>
                <div style="text-align:right">
                    <div style="font-family:monospace; font-size:0.9rem; color:var(--accent-blue)">${escapeHtml(s.ip)}</div>
                </div>
            </div>
        </div>
    `).join('');
}

// ==================== UTILITY HELPERS ====================

function setText(id, text, isHtml = false) {
    const el = document.getElementById(id);
    if (el) {
        if (isHtml) el.innerHTML = text;
        else el.innerText = text;
    }
}

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
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

