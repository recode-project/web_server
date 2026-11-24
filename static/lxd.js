/**
 * ==========================================================================
 * EKA DASHBOARD — LXD / INCUS MANAGER CONTROLLER (ZERO INLINE JS)
 * Supports multi-project containers & graceful empty state when uninstalled.
 * ==========================================================================
 */

let containersData = {};
const COLORS = {
    Running: { bg: 'rgba(35,213,171,0.12)', icon: '#23d5ab' },
    Stopped: { bg: 'rgba(255,107,107,0.12)', icon: '#ff6b6b' },
    default: { bg: 'rgba(255,255,255,0.06)', icon: '#a0a0b0' }
};

function escapeLxdHtml(str) {
    return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function showToast(msg, type = 'info') {
    const colors = { success: '#4ecdc4', error: '#ff6b6b', info: '#9198e5' };
    const icons = { success: 'fa-circle-check', error: 'fa-circle-xmark', info: 'fa-circle-info' };
    const t = document.getElementById('toast');
    if (!t) return;
    t.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}" style="color:${colors[type] || colors.info}"></i> ${escapeLxdHtml(msg)}`;
    t.style.display = 'flex';
    setTimeout(() => { t.style.display = 'none'; }, 3500);
}

function openCreateModal() {
    const m = document.getElementById('create-modal');
    if (m) m.style.display = 'flex';
}

function closeCreateModal() {
    const m = document.getElementById('create-modal');
    if (m) m.style.display = 'none';
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

    document.querySelectorAll('.tab-btn').forEach(btn => {
        const handler = btn.getAttribute('onclick') || '';
        if (handler.includes(tabId)) {
            btn.classList.add('active');
        }
    });

    const target = document.getElementById(tabId);
    if (target) target.classList.add('active');

    if (tabId === 'tab-tools') {
        fetchToolsStatus();
    }
}

function openConfigModal(name, project = 'default') {
    const key = `${project || 'default'}/${name}`;
    const c = containersData[key] || containersData[name];
    if (!c) return;
    const actualProject = c.project || project || 'default';
    document.getElementById('cfg-name').value = name;
    document.getElementById('cfg-project').value = actualProject;
    document.getElementById('cfg-title-name').textContent = `[ ${actualProject} / ${name} ]`;
    document.getElementById('cfg-cpu').value = (c.expanded_config && c.expanded_config['limits.cpu']) || '';
    document.getElementById('cfg-ram').value = (c.expanded_config && c.expanded_config['limits.memory']) || '';
    document.getElementById('cfg-storage').value = (c.expanded_devices && c.expanded_devices.root && c.expanded_devices.root.size) || '';

    document.getElementById('adv-autostart').value = (c.expanded_config && c.expanded_config['boot.autostart']) || 'false';
    document.getElementById('adv-nesting').value = (c.expanded_config && c.expanded_config['security.nesting']) || 'false';
    document.getElementById('adv-privileged').value = (c.expanded_config && c.expanded_config['security.privileged']) || 'false';

    renderProxyList(c);

    document.getElementById('tailscale-status').style.display = 'none';
    document.getElementById('wireguard-status').style.display = 'none';

    switchTab('tab-resources');
    document.getElementById('config-modal').style.display = 'flex';
}

function closeConfigModal() {
    const m = document.getElementById('config-modal');
    if (m) m.style.display = 'none';
}

function renderProxyList(container) {
    const wrap = document.getElementById('proxy-list');
    if (!wrap) return;
    let html = '';
    const devices = container.expanded_devices || {};
    let count = 0;

    for (const devName in devices) {
        const d = devices[devName];
        if (d.type === 'proxy') {
            count++;
            html += `
            <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); padding: 0.5rem 0.8rem; border-radius: 8px; margin-bottom: 0.4rem; font-size: 0.75rem;">
                <div>
                    <span style="font-weight: 600; color: #a29bfe; font-family: monospace;">${escapeLxdHtml(devName)}</span>
                    <span style="color: var(--text-muted);"> (${escapeLxdHtml(d.listen)} -&gt; ${escapeLxdHtml(d.connect)})</span>
                </div>
                <button class="ctrl-btn delete" onclick="removeProxyDevice('${escapeLxdHtml(devName)}')" title="Delete Proxy Device" style="width:24px; height:24px; font-size:0.65rem;">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </div>`;
        }
    }

    if (count === 0) {
        wrap.innerHTML = '<div style="font-size: 0.75rem; color: var(--text-muted); text-align: center; padding: 0.5rem 0; opacity:0.6;">No port forwarding rules defined.</div>';
    } else {
        wrap.innerHTML = html;
    }
}

async function addProxyDevice() {
    const name = document.getElementById('cfg-name').value;
    const project = document.getElementById('cfg-project').value || 'default';
    const device_name = document.getElementById('net-device-name').value.trim();
    const protocol = document.getElementById('net-protocol').value;
    const host_port = document.getElementById('net-host-port').value.trim();
    const container_port = document.getElementById('net-container-port').value.trim();

    if (!device_name || !host_port || !container_port) {
        return showToast('Please fill all forwarding fields', 'error');
    }

    const btn = document.getElementById('btn-add-proxy');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Adding...';

    try {
        const res = await fetch('/api/lxd/device/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, project, device_name, protocol, host_port, container_port })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Proxy ${device_name} added successfully!`, 'success');
            document.getElementById('net-device-name').value = '';
            document.getElementById('net-host-port').value = '';
            document.getElementById('net-container-port').value = '';

            await fetchContainers();
            openConfigModal(name, project);
            switchTab('tab-network');
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (e) {
        showToast('Request failed', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Add Proxy Device';
    }
}

async function removeProxyDevice(device_name) {
    const name = document.getElementById('cfg-name').value;
    const project = document.getElementById('cfg-project').value || 'default';
    if (!confirm(`Are you sure you want to remove proxy device "${device_name}"?`)) return;

    showToast(`Removing proxy ${device_name}...`, 'info');
    try {
        const res = await fetch('/api/lxd/device/remove', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, project, device_name })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Proxy ${device_name} removed`, 'success');
            await fetchContainers();
            openConfigModal(name, project);
            switchTab('tab-network');
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (e) {
        showToast('Request failed', 'error');
    }
}

async function saveAdvancedConfig() {
    const name = document.getElementById('cfg-name').value;
    const project = document.getElementById('cfg-project').value || 'default';
    const autostart = document.getElementById('adv-autostart').value;
    const nesting = document.getElementById('adv-nesting').value;
    const privileged = document.getElementById('adv-privileged').value;

    const btn = document.getElementById('btn-save-advanced');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

    try {
        const res = await fetch('/api/lxd/advanced', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, project, autostart, nesting, privileged })
        });
        const data = await res.json();
        if (data.success) {
            showToast('Advanced configurations updated successfully!', 'success');
            await fetchContainers();
            closeConfigModal();
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (e) {
        showToast('Request failed', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Save Advanced Settings';
    }
}

async function installTool(tool) {
    const name = document.getElementById('cfg-name').value;
    const project = document.getElementById('cfg-project').value || 'default';
    const btn = document.getElementById(`btn-install-${tool}`);
    const statusBox = document.getElementById(`${tool}-status`);

    if (!confirm(`Are you sure you want to install ${tool} inside "${name}" (${project})? This requires downloading packages and may take up to a minute.`)) return;

    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Installing...';
    statusBox.style.display = 'block';
    statusBox.innerHTML = `[System] Starting ${escapeLxdHtml(tool)} installation workflow for ${escapeLxdHtml(name)} (${escapeLxdHtml(project)})...\n`;

    try {
        const res = await fetch('/api/lxd/tools/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, project, tool })
        });
        const data = await res.json();
        if (data.success) {
            statusBox.innerHTML += 'Installation completed successfully!\n';
            if (tool === 'tailscale') {
                if (data.login_url) {
                    statusBox.innerHTML += `\nTAILSCALE LOGIN URL:\n<a href="${escapeLxdHtml(data.login_url)}" target="_blank" style="color: #4ecdc4; text-decoration: underline; word-break: break-all;">${escapeLxdHtml(data.login_url)}</a>\n`;
                } else {
                    statusBox.innerHTML += `\nOutput Logs:\n${escapeLxdHtml(data.output || 'Complete.')}`;
                }
            } else {
                statusBox.innerHTML += `\n${escapeLxdHtml(data.message)}`;
            }
            showToast(`${tool} installed!`, 'success');
            fetchContainers();
            fetchToolsStatus();
        } else {
            statusBox.innerHTML += `Error: ${escapeLxdHtml(data.error)}\n`;
            showToast('Installation failed', 'error');
        }
    } catch (e) {
        statusBox.innerHTML += 'Request failed.\n';
        showToast('Request failed', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `Install ${tool.charAt(0).toUpperCase() + tool.slice(1)}`;
    }
}

async function fetchToolsStatus() {
    const name = document.getElementById('cfg-name').value;
    const project = document.getElementById('cfg-project').value || 'default';
    const tsBadge = document.getElementById('ts-status-badge');
    const wgBadge = document.getElementById('wg-status-badge');
    const tsBtn = document.getElementById('btn-install-tailscale');
    const wgBtn = document.getElementById('btn-install-wireguard');

    if (!name) return;

    tsBadge.style.display = 'inline-block';
    tsBadge.style.background = 'rgba(255,255,255,0.1)';
    tsBadge.style.color = '#fff';
    tsBadge.textContent = 'Checking...';

    wgBadge.style.display = 'inline-block';
    wgBadge.style.background = 'rgba(255,255,255,0.1)';
    wgBadge.style.color = '#fff';
    wgBadge.textContent = 'Checking...';

    try {
        const res = await fetch(`/api/lxd/tools/status?name=${encodeURIComponent(name)}&project=${encodeURIComponent(project)}`);
        const data = await res.json();

        if (data.success) {
            if (!data.running) {
                tsBadge.style.background = 'rgba(255,107,107,0.15)';
                tsBadge.style.color = '#ff6b6b';
                tsBadge.textContent = 'Stopped';

                wgBadge.style.background = 'rgba(255,107,107,0.15)';
                wgBadge.style.color = '#ff6b6b';
                wgBadge.textContent = 'Stopped';
                return;
            }

            if (data.tailscale.installed) {
                if (data.tailscale.status === 'Connected') {
                    tsBadge.style.background = 'rgba(35,213,171,0.15)';
                    tsBadge.style.color = '#23d5ab';
                    tsBadge.textContent = data.tailscale.ip ? `Connected (${data.tailscale.ip})` : 'Connected';
                    tsBtn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Connected';
                    tsBtn.style.borderColor = 'rgba(35,213,171,0.3)';
                    tsBtn.style.color = '#23d5ab';
                } else if (data.tailscale.status === 'Needs Authentication' || data.tailscale.status === 'Disconnected') {
                    tsBadge.style.background = 'rgba(255,159,67,0.15)';
                    tsBadge.style.color = '#ff9f43';
                    tsBadge.textContent = data.tailscale.status;
                    tsBtn.innerHTML = '<i class="fa-solid fa-key"></i> Authenticate';
                    tsBtn.style.borderColor = 'rgba(255,159,67,0.4)';
                    tsBtn.style.color = '#ff9f43';
                } else {
                    tsBadge.style.background = 'rgba(255,255,255,0.1)';
                    tsBadge.style.color = '#a0a0b0';
                    tsBadge.textContent = 'Stopped';
                    tsBtn.innerHTML = '<i class="fa-solid fa-play"></i> Start';
                    tsBtn.style.borderColor = 'rgba(255,255,255,0.2)';
                    tsBtn.style.color = '#fff';
                }
            } else {
                tsBadge.style.background = 'rgba(255,107,107,0.15)';
                tsBadge.style.color = '#ff6b6b';
                tsBadge.textContent = 'Not Installed';
                tsBtn.innerHTML = 'Install Tailscale';
                tsBtn.style.borderColor = 'rgba(255,107,107,0.3)';
                tsBtn.style.color = '#ff6b6b';
            }

            if (data.wireguard.installed) {
                if (data.wireguard.status === 'Active') {
                    wgBadge.style.background = 'rgba(35,213,171,0.15)';
                    wgBadge.style.color = '#23d5ab';
                    wgBadge.textContent = 'Active';
                    wgBtn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Active';
                    wgBtn.style.borderColor = 'rgba(35,213,171,0.3)';
                    wgBtn.style.color = '#23d5ab';
                } else {
                    wgBadge.style.background = 'rgba(255,159,67,0.15)';
                    wgBadge.style.color = '#ff9f43';
                    wgBadge.textContent = 'Installed';
                    wgBtn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Installed';
                    wgBtn.style.borderColor = 'rgba(78,205,196,0.3)';
                    wgBtn.style.color = '#4ecdc4';
                }
            } else {
                wgBadge.style.background = 'rgba(255,107,107,0.15)';
                wgBadge.style.color = '#ff6b6b';
                wgBadge.textContent = 'Not Installed';
                wgBtn.innerHTML = 'Install Wireguard';
                wgBtn.style.borderColor = 'rgba(78,205,196,0.3)';
                wgBtn.style.color = '#4ecdc4';
            }
        } else {
            tsBadge.textContent = 'Error';
            wgBadge.textContent = 'Error';
        }
    } catch (e) {
        tsBadge.textContent = 'Error';
        wgBadge.textContent = 'Error';
    }
}

async function saveConfig() {
    const name = document.getElementById('cfg-name').value;
    const project = document.getElementById('cfg-project').value || 'default';
    const cpu = document.getElementById('cfg-cpu').value.trim();
    const ram = document.getElementById('cfg-ram').value.trim();
    const storage = document.getElementById('cfg-storage').value.trim();

    const btn = document.getElementById('btn-config');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

    try {
        const res = await fetch('/api/lxd/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, project, cpu, ram, storage })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Config for ${name} saved successfully`, 'success');
            closeConfigModal();
            fetchContainers();
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (e) {
        showToast('Request failed', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Save Config';
    }
}

async function createContainer() {
    const name = document.getElementById('ctr-name').value.trim();
    const image = document.getElementById('ctr-image').value.trim();
    if (!name || !image) return showToast('Name and image required', 'error');

    const btn = document.getElementById('btn-create');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Launching...';

    try {
        const res = await fetch('/api/lxd/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, image })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Container ${name} created successfully`, 'success');
            closeCreateModal();
            document.getElementById('ctr-name').value = '';
            fetchContainers();
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (e) {
        showToast('Request failed', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Launch';
    }
}

async function containerAction(name, action, project = 'default') {
    if (action === 'delete') {
        if (!confirm(`Are you sure you want to delete container ${name} (${project})? This action cannot be undone.`)) return;
    }
    showToast(`${action}ing ${name}...`, 'info');
    try {
        const res = await fetch('/api/lxd/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, action, project: project || 'default' })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`${name}: ${action} successful`, 'success');
            setTimeout(fetchContainers, 1200);
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (e) {
        showToast('Request failed', 'error');
    }
}

function openTerminal(name, project = 'default') {
    const p = encodeURIComponent(project || 'default');
    const n = encodeURIComponent(name);
    const url = `/terminal?lxd=${n}&lxd_project=${p}`;
    const win = window.open(url, '_blank');
    if (!win) {
        window.location.href = url;
    }
}

function renderNotInstalledState(data) {
    const isInstalled = data && data.installed === true;
    const title = isInstalled ? 'LXD / Incus Daemon Inactive' : 'LXD / Incus Not Installed (Optional Module)';
    const desc = isInstalled
        ? escapeLxdHtml(data.error || 'The LXD/Incus CLI was found, but the daemon is not running or inaccessible.')
        : 'This server does not have LXD or Incus installed. Install LXD/Incus to manage Linux system containers, or hide this optional module in Settings.';

    return `
        <div style="text-align:center; padding:2.5rem 1.5rem; max-width:560px; margin:0 auto;">
            <div style="width:64px; height:64px; margin:0 auto 1rem; border-radius:16px; background:rgba(245,158,11,0.14); border:1px solid rgba(245,158,11,0.3); display:flex; align-items:center; justify-content:center; color:#fbbf24; font-size:1.75rem;">
                <i class="fa-brands fa-linux"></i>
            </div>
            <h3 style="font-size:1.15rem; font-weight:600; margin-bottom:0.5rem; color:#fff;">${title}</h3>
            <p style="font-size:0.85rem; color:var(--text-muted); line-height:1.55; margin-bottom:1.2rem;">${desc}</p>
            ${!isInstalled ? `
            <div style="background:rgba(0,0,0,0.3); border:1px solid rgba(255,255,255,0.08); border-radius:10px; padding:0.75rem 1rem; font-family:monospace; font-size:0.78rem; color:#93c5fd; margin-bottom:1.2rem; text-align:left;">
                # Ubuntu/Debian: sudo apt install incus  (or: sudo snap install lxd)<br>
                # Fedora/RHEL:   sudo dnf install incus<br>
                # Arch Linux:    sudo pacman -S incus
            </div>` : ''}
            <div style="display:flex; justify-content:center; gap:0.7rem; flex-wrap:wrap;">
                <a href="/settings" class="action-btn" style="text-decoration:none;">
                    <i class="fa-solid fa-sliders"></i> Manage Module Visibility
                </a>
                <button class="action-btn" onclick="fetchContainers()">
                    <i class="fa-solid fa-rotate"></i> Retry Detection
                </button>
            </div>
        </div>
    `;
}

async function fetchContainers() {
    const wrap = document.getElementById('containers-wrap');
    if (!wrap) return;

    try {
        const res = await fetch('/api/lxd/containers');
        const data = await res.json();

        if (data.installed === false || data.available === false) {
            document.getElementById('total-ct').textContent = '0';
            document.getElementById('running-ct').textContent = '0';
            document.getElementById('stopped-ct').textContent = '0';
            wrap.innerHTML = renderNotInstalledState(data);
            return;
        }

        const ctrs = Array.isArray(data.containers) ? data.containers : [];
        const total = ctrs.length;
        const running = ctrs.filter(c => c.status === 'Running').length;
        const stopped = ctrs.filter(c => c.status === 'Stopped').length;

        document.getElementById('total-ct').textContent = total;
        document.getElementById('running-ct').textContent = running;
        document.getElementById('stopped-ct').textContent = stopped;

        if (ctrs.length === 0) {
            wrap.innerHTML = '<div class="loading">No LXD/Incus containers found. Click "Launch Container" to create one.</div>';
            return;
        }

        let html = '';
        containersData = {};
        ctrs.forEach(c => {
            const project = c.project || 'default';
            const key = `${project}/${c.name}`;
            containersData[key] = c;
            containersData[c.name] = c;
            const color = COLORS[c.status] || COLORS.default;
            const isRunning = c.status === 'Running';
            let statusBadge = '';
            if (c.status === 'Running') statusBadge = '<span class="badge badge-running"><span class="pulse"></span> Running</span>';
            else if (c.status === 'Stopped') statusBadge = '<span class="badge badge-stopped">Stopped</span>';
            else statusBadge = `<span class="badge badge-other">${escapeLxdHtml(c.status)}</span>`;

            const projectBadge = `<span class="badge" style="background:rgba(168,85,247,0.18); color:#c084fc; border:1px solid rgba(168,85,247,0.35); font-size:0.68rem;"><i class="fa-solid fa-folder-tree"></i> ${escapeLxdHtml(project)}</span>`;

            const ips = [];
            if (c.state && c.state.network) {
                for (const iface in c.state.network) {
                    if (c.state.network[iface].addresses) {
                        c.state.network[iface].addresses.forEach(addr => {
                            if (addr.family === 'inet' && addr.address !== '127.0.0.1') {
                                ips.push(addr.address);
                            }
                        });
                    }
                }
            }
            const ipTags = ips.length > 0
                ? ips.map(ip => `<span class="ip-tag">${escapeLxdHtml(ip)}</span>`).join(' ')
                : (isRunning ? '<span class="ip-tag" style="opacity:0.5">-</span>' : '');

            const safeName = escapeLxdHtml(c.name);
            const safeProj = escapeLxdHtml(project);

            html += `
            <div class="container-card">
                <div class="container-icon" style="background:${color.bg}; color:${color.icon};">
                    <i class="fa-solid fa-server"></i>
                </div>
                <div class="container-info">
                    <div style="display:flex; align-items:center; gap:0.6rem; flex-wrap:wrap; margin-bottom:4px;">
                        <div class="container-name">${safeName}</div>
                        ${projectBadge}
                        ${statusBadge}
                        ${ipTags}
                    </div>
                    <div class="container-image">Architecture: ${escapeLxdHtml(c.architecture)} &nbsp;&bull;&nbsp; Type: ${escapeLxdHtml(c.type)}</div>
                </div>
                <div class="container-actions">
                    <button class="ctrl-btn start" onclick="containerAction('${safeName}','start','${safeProj}')" title="Start" ${isRunning ? 'disabled' : ''}>
                        <i class="fa-solid fa-play"></i>
                    </button>
                    <button class="ctrl-btn stop" onclick="containerAction('${safeName}','stop','${safeProj}')" title="Stop" ${!isRunning ? 'disabled' : ''}>
                        <i class="fa-solid fa-stop"></i>
                    </button>
                    <button class="ctrl-btn restart" onclick="containerAction('${safeName}','restart','${safeProj}')" title="Restart">
                        <i class="fa-solid fa-rotate-right"></i>
                    </button>
                    <button class="ctrl-btn terminal" onclick="openTerminal('${safeName}','${safeProj}')" title="Terminal" ${!isRunning ? 'disabled' : ''}>
                        <i class="fa-solid fa-terminal"></i>
                    </button>
                    <button class="ctrl-btn config" onclick="openConfigModal('${safeName}','${safeProj}')" title="Configure Resource Limits">
                        <i class="fa-solid fa-gear"></i>
                    </button>
                    <button class="ctrl-btn delete" onclick="containerAction('${safeName}','delete','${safeProj}')" title="Delete">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </div>`;
        });

        wrap.innerHTML = html;
    } catch (e) {
        wrap.innerHTML = '<div class="loading" style="color:#ff6b6b;"><i class="fa-solid fa-circle-exclamation" style="margin-right:0.5rem;"></i>Failed to load containers</div>';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    fetchContainers();
    setInterval(fetchContainers, 8000);
});

