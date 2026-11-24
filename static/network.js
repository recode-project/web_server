/**
 * Eka Dashboard - Network Management Module
 * Handles Interface Monitoring, Open Ports Scanner, Diagnostics Toolkit, and Network Configuration.
 */

let allPortsData = [];
let allInterfacesData = [];
let showAllInterfaces = false;

document.addEventListener('DOMContentLoaded', () => {
    loadNetworkInfo();
    loadPublicIp();
    loadPorts();
    loadRoutes();

    // Port search filter listener
    const portSearch = document.getElementById('port-search-input');
    if (portSearch) {
        portSearch.addEventListener('input', () => filterPorts());
    }
});

function toggleVethFilter() {
    showAllInterfaces = !showAllInterfaces;
    const btnText = document.getElementById('veth-toggle-text');
    if (btnText) {
        btnText.textContent = showAllInterfaces ? 'Sembunyikan Virtual Veth' : 'Tampilkan Semua (Termasuk Veth)';
    }
    renderInterfaces(allInterfacesData);
}

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

function switchTab(tabId, btnElement) {
    document.querySelectorAll('.tab-section').forEach(sec => sec.style.display = 'none');
    document.querySelectorAll('.tab-nav-btn').forEach(btn => btn.classList.remove('active'));

    const targetSection = document.getElementById('tab-' + tabId);
    if (targetSection) targetSection.style.display = 'block';

    if (btnElement) {
        btnElement.classList.add('active');
    } else {
        const activeBtn = document.querySelector(`.tab-nav-btn[data-tab="${tabId}"]`);
        if (activeBtn) activeBtn.classList.add('active');
    }
}

// ==================== TAB 1: OVERVIEW & INTERFACES ====================

function loadNetworkInfo() {
    const ifaceContainer = document.getElementById('interface-list');
    if (ifaceContainer) {
        ifaceContainer.innerHTML = '<div style="text-align:center; padding:2rem; color:var(--text-dim)"><i class="fa-solid fa-spinner fa-spin"></i> Memuat antarmuka jaringan...</div>';
    }

    fetch('/api/network/info')
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                showMsg(data.error, 'error');
                return;
            }

            // Overview summary cards
            setText('info-hostname', data.hostname || '-');
            setText('info-primary-ip', data.primary_ip || '-');
            setText('info-gateway', data.gateway || '-');
            setText('info-dns', (data.dns || []).join(', ') || '-');
            setText('info-mac', data.primary_mac || '-');

            // Pre-fill config forms
            const hostInput = document.getElementById('new-hostname');
            if (hostInput && !hostInput.value) hostInput.value = data.hostname || '';

            if (data.dns && data.dns.length > 0) {
                const dns1 = document.getElementById('dns1');
                const dns2 = document.getElementById('dns2');
                if (dns1 && !dns1.value) dns1.value = data.dns[0] || '';
                if (dns2 && !dns2.value) dns2.value = data.dns[1] || '';
            }

            allInterfacesData = data.interfaces || [];
            renderInterfaces(allInterfacesData);
        })
        .catch(err => {
            console.error('Error loading network info:', err);
            showMsg('Gagal memuat informasi jaringan', 'error');
        });
}

function loadPublicIp() {
    fetch('/api/network/public-ip')
        .then(r => r.json())
        .then(data => {
            setText('info-public-ip', data.public_ip || '-');
        })
        .catch(() => {
            setText('info-public-ip', '-');
        });
}

function renderInterfaces(interfaces) {
    const container = document.getElementById('interface-list');
    if (!container) return;

    if (!interfaces || interfaces.length === 0) {
        container.innerHTML = '<div style="text-align:center; padding:2rem; color:var(--text-dim)">Tidak ada interface ditemukan</div>';
        return;
    }

    const displayed = showAllInterfaces 
        ? interfaces 
        : interfaces.filter(i => !i.name.startsWith('veth') && !i.name.startsWith('tap') && !i.name.startsWith('br-'));

    container.innerHTML = displayed.map(iface => {
        const isUp = iface.status === 'up';
        const statusBadge = isUp 
            ? '<span class="status-pill up"><i class="fa-solid fa-circle-check"></i> UP</span>' 
            : '<span class="status-pill down"><i class="fa-solid fa-circle-xmark"></i> DOWN</span>';

        let iconClass = 'fa-ethernet';
        let typeBadgeClass = 'type-ethernet';
        let typeLabel = 'Ethernet';

        if (iface.type === 'wifi') {
            iconClass = 'fa-wifi';
            typeBadgeClass = 'type-wifi';
            typeLabel = 'Wi-Fi';
        } else if (iface.type === 'vpn') {
            iconClass = 'fa-shield-halved';
            typeBadgeClass = 'type-vpn';
            typeLabel = 'VPN / Tunnel';
        } else if (iface.type === 'bridge') {
            iconClass = 'fa-diagram-project';
            typeBadgeClass = 'type-bridge';
            typeLabel = 'Bridge';
        } else if (iface.type === 'virtual') {
            iconClass = 'fa-network-wired';
            typeBadgeClass = 'type-virtual';
            typeLabel = 'Virtual';
        }

        return `
        <div class="iface-card glass">
            <div class="iface-top">
                <div class="iface-icon-box ${typeBadgeClass}">
                    <i class="fa-solid ${iconClass}"></i>
                </div>
                <div class="iface-title-wrap">
                    <div class="iface-name">${escapeHtml(iface.name)}</div>
                    <span class="type-badge ${typeBadgeClass}">${typeLabel}</span>
                </div>
                <div class="iface-status-wrap">
                    ${statusBadge}
                </div>
            </div>

            <div class="iface-details">
                <div class="iface-field">
                    <span class="lbl">IP Address:</span>
                    <span class="val ip">${escapeHtml(iface.ip || 'Belum Terhubung')}</span>
                </div>
                <div class="iface-field">
                    <span class="lbl">MAC Address:</span>
                    <span class="val mac">${escapeHtml(iface.mac || '-')}</span>
                </div>
                <div class="iface-field">
                    <span class="lbl">MTU:</span>
                    <span class="val">${iface.mtu || 1500} bytes</span>
                </div>
            </div>

            <div class="iface-traffic">
                <div class="traffic-box rx">
                    <span class="traffic-label"><i class="fa-solid fa-arrow-down"></i> Diterima (Rx)</span>
                    <span class="traffic-val">${formatBytes(iface.rx_bytes)}</span>
                </div>
                <div class="traffic-box tx">
                    <span class="traffic-label"><i class="fa-solid fa-arrow-up"></i> Dikirim (Tx)</span>
                    <span class="traffic-val">${formatBytes(iface.tx_bytes)}</span>
                </div>
            </div>
            ${iface.rx_dropped > 0 || iface.tx_dropped > 0 ? `
                <div class="iface-warning-bar">
                    <i class="fa-solid fa-triangle-exclamation"></i> Terdeteksi Packet Dropped: Rx ${iface.rx_dropped} | Tx ${iface.tx_dropped}
                </div>
            ` : ''}
        </div>`;
    }).join('');
}

// ==================== TAB 2: LISTENING PORTS & SERVICES ====================

function loadPorts() {
    const tbody = document.querySelector('#ports-table tbody');
    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:2rem; color:var(--text-dim)"><i class="fa-solid fa-spinner fa-spin"></i> Memindai port host aktif...</td></tr>';
    }

    fetch('/api/network/ports')
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--danger)">${escapeHtml(data.error)}</td></tr>`;
                return;
            }
            allPortsData = data || [];
            setText('total-ports-count', allPortsData.length);
            filterPorts();
        })
        .catch(err => {
            console.error('Error loading ports:', err);
            if (tbody) tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--danger)">Gagal memindai port listening</td></tr>';
        });
}

function filterPorts() {
    const query = (document.getElementById('port-search-input')?.value || '').toLowerCase().trim();
    const protoFilter = document.querySelector('input[name="proto-filter"]:checked')?.value || 'ALL';

    const filtered = allPortsData.filter(p => {
        // Proto filter
        if (protoFilter !== 'ALL' && p.proto !== protoFilter) return false;
        // Search query
        if (!query) return true;
        const portStr = String(p.port);
        const progStr = (p.program || '').toLowerCase();
        const ipStr = (p.ip || '').toLowerCase();
        return portStr.includes(query) || progStr.includes(query) || ipStr.includes(query);
    });

    renderPortsTable(filtered);
}

function renderPortsTable(ports) {
    const tbody = document.querySelector('#ports-table tbody');
    if (!tbody) return;

    if (!ports || ports.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:2rem; color:var(--text-dim)">Tidak ada port yang sesuai kriteria pencarian</td></tr>';
        return;
    }

    tbody.innerHTML = ports.map(p => {
        const isPublic = p.is_public;
        const scopeBadge = isPublic
            ? '<span class="scope-pill public" title="Dapat diakses dari luar / seluruh antarmuka"><i class="fa-solid fa-globe"></i> Publik (0.0.0.0 / *)</span>'
            : '<span class="scope-pill local" title="Hanya dapat diakses secara lokal di host"><i class="fa-solid fa-lock"></i> Lokal (127.0.0.1)</span>';

        const protoBadge = p.proto === 'TCP'
            ? '<span class="proto-badge tcp">TCP</span>'
            : '<span class="proto-badge udp">UDP</span>';

        return `
        <tr>
            <td><span class="port-num">${p.port}</span></td>
            <td>${protoBadge}</td>
            <td><span class="ip-bind">${escapeHtml(p.ip)}</span></td>
            <td>${scopeBadge}</td>
            <td>
                <div class="prog-cell">
                    <i class="fa-solid fa-cube" style="color:var(--accent-blue)"></i>
                    <strong>${escapeHtml(p.program || 'System')}</strong>
                </div>
            </td>
            <td>
                ${p.pid ? `<span class="pid-badge">#${p.pid}</span>` : '<span style="color:var(--text-dim)">-</span>'}
            </td>
        </tr>`;
    }).join('');
}

// ==================== TAB 3: NETWORK DIAGNOSTICS ====================

function runPing() {
    const target = (document.getElementById('ping-target')?.value || '').trim();
    const count = parseInt(document.getElementById('ping-count')?.value || '3');
    const btn = document.getElementById('btn-run-ping');
    const resultBox = document.getElementById('ping-result-box');

    if (!target) {
        showMsg('Target ping tidak boleh kosong', 'error');
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Melakukan Ping...';
    resultBox.style.display = 'block';
    resultBox.innerHTML = `<div style="color:var(--text-dim)"><i class="fa-solid fa-spinner fa-spin"></i> Mengirim paket ICMP ke <strong>${escapeHtml(target)}</strong>...</div>`;

    fetch('/api/network/ping', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target, count })
    })
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-play"></i> Mulai Ping';

            if (!data.success && data.error) {
                resultBox.innerHTML = `<div style="color:var(--danger)"><i class="fa-solid fa-circle-xmark"></i> ${escapeHtml(data.error)}</div>`;
                return;
            }

            const lossColor = data.packet_loss === 0 ? 'var(--success)' : (data.packet_loss < 50 ? 'var(--warning)' : 'var(--danger)');
            const latencyText = data.avg_rtt_ms !== null ? `${data.avg_rtt_ms} ms` : 'N/A';

            resultBox.innerHTML = `
                <div class="diag-summary">
                    <div class="diag-metric">
                        <span class="lbl">Packet Loss</span>
                        <span class="val" style="color:${lossColor}">${data.packet_loss}%</span>
                    </div>
                    <div class="diag-metric">
                        <span class="lbl">Rata-rata Latensi</span>
                        <span class="val" style="color:var(--accent-blue)">${latencyText}</span>
                    </div>
                    <div class="diag-metric">
                        <span class="lbl">Status</span>
                        <span class="val" style="color:${data.success ? 'var(--success)' : 'var(--danger)'}">
                            ${data.success ? 'Terkoneksi' : 'Koneksi Terputus'}
                        </span>
                    </div>
                </div>
                <div class="terminal-output">${escapeHtml(data.output || '')}</div>
            `;
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-play"></i> Mulai Ping';
            resultBox.innerHTML = '<div style="color:var(--danger)">Gagal menjalankan perintah ping.</div>';
        });
}

function runDnsLookup() {
    const domain = (document.getElementById('dns-domain-input')?.value || '').trim();
    const btn = document.getElementById('btn-run-dns');
    const resultBox = document.getElementById('dns-result-box');

    if (!domain) {
        showMsg('Domain tidak boleh kosong', 'error');
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Resolving...';
    resultBox.style.display = 'block';
    resultBox.innerHTML = `<div style="color:var(--text-dim)"><i class="fa-solid fa-spinner fa-spin"></i> Meminta lookup DNS untuk <strong>${escapeHtml(domain)}</strong>...</div>`;

    fetch('/api/network/dns-lookup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain })
    })
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Uji DNS';

            if (!data.success) {
                resultBox.innerHTML = `<div style="color:var(--danger)"><i class="fa-solid fa-circle-xmark"></i> ${escapeHtml(data.error || 'Resolusi domain gagal')}</div>`;
                return;
            }

            const ipsHtml = data.ips.map(ip => `<div class="resolved-ip-item"><i class="fa-solid fa-arrow-right"></i> <code>${escapeHtml(ip)}</code></div>`).join('');
            resultBox.innerHTML = `
                <div class="diag-summary">
                    <div class="diag-metric">
                        <span class="lbl">Domain</span>
                        <span class="val">${escapeHtml(data.domain)}</span>
                    </div>
                    <div class="diag-metric">
                        <span class="lbl">Waktu Resolusi</span>
                        <span class="val" style="color:var(--accent-blue)">${data.elapsed_ms} ms</span>
                    </div>
                    <div class="diag-metric">
                        <span class="lbl">Jumlah Record</span>
                        <span class="val" style="color:var(--success)">${data.ips.length}</span>
                    </div>
                </div>
                <div class="resolved-ips-list">
                    ${ipsHtml}
                </div>
            `;
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Uji DNS';
            resultBox.innerHTML = '<div style="color:var(--danger)">Gagal melakukan query DNS.</div>';
        });
}

// ==================== TAB 4: CONFIGURATION & ROUTING ====================

function loadRoutes() {
    const tbody = document.querySelector('#routes-table tbody');
    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:1.5rem; color:var(--text-dim)"><i class="fa-solid fa-spinner fa-spin"></i> Memuat tabel rute...</td></tr>';
    }

    fetch('/api/network/routes')
        .then(r => r.json())
        .then(routes => {
            if (!tbody) return;
            if (!routes || routes.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-dim)">Tabel perutean kosong</td></tr>';
                return;
            }

            tbody.innerHTML = routes.map(r => {
                const isDefault = r.dst === 'default';
                return `
                <tr ${isDefault ? 'style="background:rgba(88, 166, 255, 0.08)"' : ''}>
                    <td>
                        <strong style="color:${isDefault ? 'var(--accent-blue)' : '#ffffff'}">${escapeHtml(r.dst)}</strong>
                        ${isDefault ? '<span class="default-badge">DEFAULT</span>' : ''}
                    </td>
                    <td><code>${escapeHtml(r.gateway || '-')}</code></td>
                    <td><span class="iface-pill">${escapeHtml(r.dev || '-')}</span></td>
                    <td>${escapeHtml(r.protocol || 'kernel')}</td>
                    <td>${r.metric !== undefined ? r.metric : '-'}</td>
                </tr>`;
            }).join('');
        })
        .catch(err => {
            console.error('Error loading routes:', err);
            if (tbody) tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--danger)">Gagal memuat tabel routing</td></tr>';
        });
}

function updateHostname() {
    const hostname = document.getElementById('new-hostname').value.trim();
    if (!hostname) {
        showMsg('Hostname tidak boleh kosong', 'error');
        return;
    }

    if (!/^[a-zA-Z0-9-]+$/.test(hostname)) {
        showMsg('Hostname hanya boleh berisi huruf, angka, dan tanda hubung', 'error');
        return;
    }

    const btn = document.getElementById('btn-update-hostname');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Menyimpan...';

    fetch('/api/network/hostname', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hostname: hostname })
    })
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-save"></i> Simpan Hostname';

            if (data.error) {
                showMsg(data.error, 'error');
            } else {
                showMsg('Hostname berhasil diubah! Restart sistem untuk menerapkan sepenuhnya.', 'success');
                loadNetworkInfo();
            }
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-save"></i> Simpan Hostname';
            showMsg('Gagal mengubah hostname', 'error');
        });
}

function updateDns() {
    const dns1 = document.getElementById('dns1').value.trim();
    const dns2 = document.getElementById('dns2').value.trim();

    if (!dns1) {
        showMsg('DNS Server 1 tidak boleh kosong', 'error');
        return;
    }

    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (!ipRegex.test(dns1)) {
        showMsg('Format DNS Server 1 tidak valid', 'error');
        return;
    }
    if (dns2 && !ipRegex.test(dns2)) {
        showMsg('Format DNS Server 2 tidak valid', 'error');
        return;
    }

    const btn = document.getElementById('btn-update-dns');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Menyimpan...';

    const dnsServers = [dns1];
    if (dns2) dnsServers.push(dns2);

    fetch('/api/network/dns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dns: dnsServers })
    })
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-save"></i> Simpan DNS';

            if (data.error) {
                showMsg(data.error, 'error');
            } else {
                showMsg('Konfigurasi DNS berhasil disimpan!', 'success');
                loadNetworkInfo();
            }
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-save"></i> Simpan DNS';
            showMsg('Gagal menyimpan konfigurasi DNS', 'error');
        });
}

// ==================== UTILITY HELPERS ====================

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.innerText = text;
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

