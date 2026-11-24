/**
 * Eka Dashboard - File Sharing (SMB / Samba) Module
 * Modular JavaScript separation per project protocol.
 */

let serverLanIP = '';
let serverTsIP = '';
let serverHostname = '';
let allShares = [];
let allSessions = [];

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function showToast(msg, type = 'info') {
    const box = document.getElementById('msg-box');
    if (!box) return;
    box.textContent = msg;
    box.className = `msg-toast ${type} show`;
    setTimeout(() => {
        box.className = 'msg-toast';
    }, 4500);
}

function copyToClipboard(text, btn) {
    if (!navigator.clipboard) {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
    } else {
        navigator.clipboard.writeText(text);
    }

    if (btn) {
        const origHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-check" style="color:var(--ram-color)"></i> Tersalin!';
        btn.classList.add('copied');
        setTimeout(() => {
            btn.innerHTML = origHtml;
            btn.classList.remove('copied');
        }, 1800);
    } else {
        showToast('Path berhasil disalin ke clipboard!', 'success');
    }
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-section').forEach(s => s.style.display = 'none');

    const activeBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
    if (activeBtn) activeBtn.classList.add('active');

    const targetSection = document.getElementById(`section-${tabId}`);
    if (targetSection) targetSection.style.display = 'block';

    if (tabId === 'sessions') {
        loadSessions();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadStatus();
    loadShares();
});

// ==================== STATUS & BANNER ====================

function loadStatus() {
    fetch('/api/smb/status')
        .then(r => r.json())
        .then(data => {
            serverLanIP = data.lan_ip || data.server_ip || '';
            serverTsIP = data.ts_ip || '';
            serverHostname = data.hostname || '';
            updateStatusBanner(data);
        })
        .catch(err => {
            updateStatusBanner({ installed: false, running: false });
        });
}

function updateStatusBanner(data) {
    const banner = document.getElementById('status-banner');
    const title = document.getElementById('status-title');
    const desc = document.getElementById('status-desc');
    const actions = document.getElementById('status-actions');
    const ipPills = document.getElementById('server-ip-pills');
    const canManage = ['owner', 'admin'].includes(window.userRole);

    if (!banner) return;

    if (!data.installed) {
        banner.className = 'status-banner glass not-installed';
        banner.querySelector('.status-icon').innerHTML = '<i class="fa-solid fa-circle-xmark"></i>';
        if (title) title.textContent = 'Samba Belum Terpasang';
        if (desc) {
            desc.innerHTML = `
                <div>Daemon SMB/Samba tidak ditemukan di sistem host. Silakan pasang paket Samba melalui terminal:</div>
                <code style="display:block; background:rgba(0,0,0,0.3); padding:0.5rem; border-radius:6px; margin-top:0.4rem; font-size:0.82rem">
                    sudo apt update &amp;&amp; sudo apt install -y samba
                </code>
            `;
        }
        if (actions) actions.innerHTML = '';
        if (ipPills) ipPills.style.display = 'none';
        return;
    }

    if (data.running) {
        banner.className = 'status-banner glass running';
        banner.querySelector('.status-icon').innerHTML = '<i class="fa-solid fa-circle-check"></i>';
        if (title) title.innerHTML = `Samba Aktif &amp; Siap <span style="font-size:0.75rem; font-weight:500; opacity:0.8">(${escapeHtml(data.version || 'SMB')})</span>`;
        if (desc) desc.textContent = 'Layanan berbagi file SMB berjalan normal di jaringan lokal dan Tailscale.';
        
        if (actions) {
            actions.innerHTML = canManage ? `
                <button class="btn warning" onclick="controlSamba('restart')" title="Restart Samba daemon">
                    <i class="fa-solid fa-rotate"></i> Restart
                </button>
                <button class="btn danger" onclick="controlSamba('stop')" title="Hentikan sementara layanan Samba">
                    <i class="fa-solid fa-stop"></i> Stop
                </button>
            ` : '';
        }
    } else {
        banner.className = 'status-banner glass stopped';
        banner.querySelector('.status-icon').innerHTML = '<i class="fa-solid fa-circle-pause"></i>';
        if (title) title.textContent = 'Samba Tidak Aktif (Stopped)';
        if (desc) desc.textContent = 'Layanan Samba dihentikan di server host.';
        if (actions) {
            actions.innerHTML = canManage ? `
                <button class="btn primary" onclick="controlSamba('start')">
                    <i class="fa-solid fa-play"></i> Start Service
                </button>
            ` : '';
        }
    }

    // IP Pills update
    if (ipPills) {
        ipPills.style.display = 'flex';
        const bestIP = serverLanIP || serverTsIP || '127.0.0.1';
        
        document.getElementById('pill-lan-ip').textContent = serverLanIP ? serverLanIP : 'Tidak terdeteksi';
        document.getElementById('pill-ts-ip').textContent = serverTsIP ? serverTsIP : 'Tidak aktif';
        document.getElementById('pill-hostname').textContent = serverHostname ? serverHostname : '-';
        
        // Update quick access helper
        const winPath = `\\\\${bestIP}`;
        const macPath = `smb://${bestIP}`;
        const winEl = document.getElementById('quick-win-path');
        const macEl = document.getElementById('quick-mac-path');
        if (winEl) winEl.textContent = winPath;
        if (macEl) macEl.textContent = macPath;
    }
}

// ==================== SHARES MANAGEMENT ====================

function loadShares() {
    const list = document.getElementById('share-list');
    if (list) {
        list.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-spinner fa-spin" style="font-size:2rem; opacity:0.5"></i>
                <div style="margin-top:0.6rem">Memuat daftar folder yang di-share...</div>
            </div>`;
    }

    fetch('/api/smb/shares')
        .then(r => r.json())
        .then(data => {
            allShares = data.shares || [];
            document.getElementById('share-count-badge').textContent = allShares.length;
            renderShares(allShares);
        })
        .catch(err => {
            if (list) list.innerHTML = '<div class="empty-state" style="color:var(--danger)">Gagal memuat daftar share SMB.</div>';
        });
}

function filterShares() {
    const q = (document.getElementById('share-search-input')?.value || '').toLowerCase().trim();
    if (!q) {
        renderShares(allShares);
        return;
    }
    const filtered = allShares.filter(s => 
        (s.name || '').toLowerCase().includes(q) || 
        (s.path || '').toLowerCase().includes(q) ||
        (s.comment || '').toLowerCase().includes(q)
    );
    renderShares(filtered);
}

function renderShares(shares) {
    const container = document.getElementById('share-list');
    if (!container) return;
    const canManage = ['owner', 'admin'].includes(window.userRole);
    const targetIP = serverLanIP || serverTsIP || 'server-ip';

    if (!shares || shares.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-folder-open" style="font-size:2.5rem; opacity:0.3; margin-bottom:0.8rem"></i>
                <div style="font-weight:600">Belum Ada Folder yang Di-Share</div>
                <div style="font-size:0.85rem; color:var(--text-dim); margin-top:0.3rem">Gunakan tab "Tambah Share Baru" untuk membagikan direktori.</div>
            </div>`;
        return;
    }

    container.innerHTML = shares.map(s => {
        const winPath = `\\\\${targetIP}\\${s.name}`;
        const macPath = `smb://${targetIP}/${s.name}`;

        const permPill = s.read_only
            ? '<span class="badge ro"><i class="fa-solid fa-eye"></i> Read Only</span>'
            : '<span class="badge rw"><i class="fa-solid fa-pen"></i> Read &amp; Write</span>';

        const accessPill = s.guest_ok
            ? '<span class="badge public"><i class="fa-solid fa-lock-open"></i> Akses Publik</span>'
            : '<span class="badge auth"><i class="fa-solid fa-lock"></i> Autentikasi User</span>';

        return `
        <div class="share-card glass">
            <div class="share-header-row">
                <div class="share-left">
                    <div class="share-icon-box">
                        <i class="fa-solid fa-folder-tree"></i>
                    </div>
                    <div>
                        <div class="share-title">${escapeHtml(s.name)}</div>
                        <div class="share-comment">${escapeHtml(s.comment || 'Folder berbagi bersama')}</div>
                    </div>
                </div>
                <div class="share-badges">
                    ${permPill}
                    ${accessPill}
                    ${canManage ? `
                        <button class="btn-icon danger" onclick="removeShare('${escapeHtml(s.name)}')" title="Hapus Share">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    ` : ''}
                </div>
            </div>

            <div class="share-meta-row">
                <div class="meta-label"><i class="fa-solid fa-hard-drive"></i> Path Fisik:</div>
                <div class="meta-val path-val">${escapeHtml(s.path)}</div>
            </div>

            <div class="share-connect-row">
                <div class="connect-box">
                    <div class="connect-label"><i class="fa-brands fa-windows"></i> Windows UNC:</div>
                    <code class="connect-code">${escapeHtml(winPath)}</code>
                    <button class="btn-copy" onclick="copyToClipboard('${escapeHtml(winPath)}', this)" title="Salin Path Windows">
                        <i class="fa-solid fa-copy"></i> Salin
                    </button>
                </div>
                <div class="connect-box">
                    <div class="connect-label"><i class="fa-brands fa-apple"></i> macOS / Linux:</div>
                    <code class="connect-code">${escapeHtml(macPath)}</code>
                    <button class="btn-copy" onclick="copyToClipboard('${escapeHtml(macPath)}', this)" title="Salin URL SMB">
                        <i class="fa-solid fa-copy"></i> Salin
                    </button>
                </div>
            </div>
        </div>`;
    }).join('');
}

function addShare() {
    const name = document.getElementById('share-name').value.trim();
    const path = document.getElementById('share-path').value.trim();
    const desc = document.getElementById('share-desc').value.trim();
    const isPublic = document.getElementById('share-public').checked;
    const writable = document.getElementById('share-writable').checked;

    if (!name || !path) {
        showToast('Nama share dan path folder wajib diisi!', 'error');
        return;
    }

    if (!/^[a-zA-Z0-9_-]+$/.test(name)) {
        showToast('Nama share hanya boleh berisi huruf, angka, dash, dan underscore!', 'error');
        return;
    }

    const btn = document.getElementById('btn-add-share');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Menerapkan...';
    }

    fetch('/api/smb/share/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, path, description: desc, public: isPublic, writable })
    })
        .then(r => r.json())
        .then(data => {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-plus"></i> Tambah Share';
            }

            if (data.error) {
                showToast(data.error, 'error');
            } else {
                showToast('Share folder berhasil ditambahkan &amp; service di-reload!', 'success');
                document.getElementById('share-name').value = '';
                document.getElementById('share-path').value = '';
                document.getElementById('share-desc').value = '';
                loadShares();
                switchTab('shares');
            }
        })
        .catch(err => {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-plus"></i> Tambah Share';
            }
            showToast('Gagal menghubungi server saat menambah share', 'error');
        });
}

function removeShare(name) {
    if (!confirm(`Hapus konfigurasi berbagi folder "${name}" dari Samba?\n(Catatan: Berkas fisik di dalam folder tidak akan terhapus).`)) return;

    fetch('/api/smb/share/remove', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'error');
            } else {
                showToast(`Share "${name}" berhasil dihapus`, 'success');
                loadShares();
            }
        })
        .catch(err => showToast('Gagal menghapus share', 'error'));
}

function controlSamba(action) {
    const actionNames = {
        'start': 'menjalankan',
        'stop': 'menghentikan',
        'restart': 'merestart',
        'reload': 'memuat ulang'
    };

    if (action === 'stop' && !confirm('Yakin ingin menghentikan Samba? Klien tidak akan dapat mengakses file bersama saat service mati.')) {
        return;
    }

    showToast(`Sedang ${actionNames[action] || action} Samba...`, 'info');

    fetch('/api/smb/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
    })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'error');
            } else {
                showToast(`Samba berhasil di-${action}!`, 'success');
                loadStatus();
            }
        })
        .catch(err => showToast(`Gagal mengontrol service Samba: ${err.message}`, 'error'));
}

// ==================== SESSIONS MONITOR ====================

function loadSessions() {
    const list = document.getElementById('session-list');
    if (list) {
        list.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-spinner fa-spin" style="font-size:2rem; opacity:0.5"></i>
                <div style="margin-top:0.6rem">Memindai koneksi SMB aktif...</div>
            </div>`;
    }

    fetch('/api/smb/sessions')
        .then(r => r.json())
        .then(data => {
            allSessions = data.sessions || [];
            document.getElementById('session-count-badge').textContent = data.count || 0;
            renderSessions(allSessions);
        })
        .catch(err => {
            if (list) list.innerHTML = '<div class="empty-state" style="color:var(--danger)">Gagal memindai sesi SMB.</div>';
        });
}

function renderSessions(sessions) {
    const container = document.getElementById('session-list');
    if (!container) return;

    if (!sessions || sessions.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-users-slash" style="font-size:2.5rem; opacity:0.3; margin-bottom:0.8rem"></i>
                <div style="font-weight:600">Tidak Ada Klien SMB yang Terhubung</div>
                <div style="font-size:0.85rem; color:var(--text-dim); margin-top:0.3rem">Koneksi aktif dari Windows, macOS, atau Linux akan terpantau di sini secara real-time.</div>
            </div>`;
        return;
    }

    container.innerHTML = `
        <div style="overflow-x:auto;">
            <table class="session-table">
                <thead>
                    <tr>
                        <th>PID</th>
                        <th>User</th>
                        <th>Grup</th>
                        <th>Mesin / Alamat Klien</th>
                        <th>Protokol</th>
                        <th>Enkripsi</th>
                        <th>Signing</th>
                    </tr>
                </thead>
                <tbody>
                    ${sessions.map(s => `
                        <tr>
                            <td><code>${escapeHtml(s.pid)}</code></td>
                            <td><strong style="color:var(--ram-color)">${escapeHtml(s.username)}</strong></td>
                            <td>${escapeHtml(s.group)}</td>
                            <td><i class="fa-solid fa-laptop" style="color:var(--net-color); margin-right:5px;"></i> ${escapeHtml(s.machine)}</td>
                            <td><span class="badge ro">${escapeHtml(s.protocol)}</span></td>
                            <td>${escapeHtml(s.encryption)}</td>
                            <td>${escapeHtml(s.signing)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

