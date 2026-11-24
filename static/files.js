let currentPath = 'drives://';
let selectedItem = null;
let clipboard = null;
let currentPage = 1;
let hasMore = false;
let isLoading = false;
let viewMode = 'drives'; // 'files' or 'drives'

// Quick folder list for sidebar
const quickFolders = ['/', '/root', '/home', '/var', '/etc', '/tmp', '/opt'];

document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const initialPath = urlParams.get('path');
    
    if (initialPath) {
        loadFiles(initialPath);
    } else {
        loadDrives();
    }
    buildSidebarTree();

    // Close context menu on click outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.context-menu')) {
            hideContextMenu();
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Delete' && selectedItem) deleteItem();
        if (e.key === 'F2' && selectedItem) renameItem();
        if (e.ctrlKey && e.key === 'c' && selectedItem) copyItem('copy');
        if (e.ctrlKey && e.key === 'x' && selectedItem) copyItem('cut');
        if (e.ctrlKey && e.key === 'v' && clipboard) pasteItem();
    });
});

let physicalDisksData = [];

function loadDrives() {
    viewMode = 'drives';
    currentPath = 'drives://';

    const lmBtn = document.getElementById('btn-load-more');
    if (lmBtn) lmBtn.style.display = 'none';
    
    document.getElementById('file-list').innerHTML = '';
    document.getElementById('status-text').textContent = 'Loading physical drives...';
    document.getElementById('status-path').textContent = 'This PC';
    
    renderBreadcrumbs('drives://');
    updateSidebarActive('drives://');

    fetch('/api/files/drives')
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                alert("Error loading drives: " + data.error);
                return;
            }
            physicalDisksData = data.physical_disks || [];
            if (physicalDisksData.length > 0) {
                renderPhysicalDisks(physicalDisksData);
                document.getElementById('status-text').textContent = `${physicalDisksData.length} physical drives detected`;
            } else {
                renderDriveTable(data.drives || []);
                document.getElementById('status-text').textContent = `${(data.drives || []).length} drives found`;
            }
        })
        .catch(err => {
            console.error("Drives fetch error:", err);
            document.getElementById('status-text').textContent = 'Error loading drives';
        });
}

function renderPhysicalDisks(disks) {
    const tbody = document.getElementById('file-list');
    tbody.innerHTML = '';
    
    disks.forEach(disk => {
        const tr = document.createElement('tr');
        tr.onclick = (e) => selectDiskRow(tr, disk, e);
        tr.ondblclick = () => openPhysicalDisk(disk.id);
        
        const usedGB = (disk.used_bytes / (1024**3)).toFixed(1);
        const totalGB = disk.size_gb;
        const percent = disk.percent || 0;
        
        let barColor = '#238636';
        if (percent > 70) barColor = '#d29922';
        if (percent > 90) barColor = '#f85149';

        const iconHtml = disk.is_ssd ? 
            `<span class="fm-icon" style="color:#55efc4; font-size:1.3rem"><i class="fa-solid fa-bolt"></i></span>` : 
            `<span class="fm-icon" style="color:#74b9ff; font-size:1.3rem"><i class="fa-solid fa-hard-drive"></i></span>`;

        const badgeHtml = disk.is_ssd ?
            `<span style="background:rgba(85,239,196,0.15); color:#55efc4; border:1px solid rgba(85,239,196,0.3); font-size:0.65rem; padding:2px 6px; border-radius:4px; font-weight:600; text-transform:uppercase;">${disk.disk_type}</span>` :
            `<span style="background:rgba(116,185,255,0.15); color:#74b9ff; border:1px solid rgba(116,185,255,0.3); font-size:0.65rem; padding:2px 6px; border-radius:4px; font-weight:600; text-transform:uppercase;">${disk.disk_type}</span>`;

        const volumeSummary = (disk.partitions || []).map(p => `${p.label} (${p.mountpoint})`).join(', ');

        tr.innerHTML = `
            <td>
                <div style="display:flex; align-items:center; gap:0.8rem">
                    ${iconHtml}
                    <div>
                        <div style="font-weight:600; display:flex; align-items:center; gap:0.5rem">
                            <span>${disk.name}</span>
                            ${badgeHtml}
                        </div>
                        <div style="font-size:0.75rem; color:#888; margin-top:2px;">
                            ${(disk.partitions || []).length} volume: ${volumeSummary}
                        </div>
                    </div>
                </div>
            </td>
            <td>
                <div style="width:140px">
                    <div style="font-size:0.75rem; margin-bottom:4px; display:flex; justify-content:space-between">
                        <span>${usedGB} / ${totalGB} GB</span>
                        <span>${percent}%</span>
                    </div>
                    <div style="height:6px; background:rgba(255,255,255,0.1); border-radius:3px; overflow:hidden">
                        <div style="width:${Math.min(percent, 100)}%; height:100%; background:${barColor}"></div>
                    </div>
                </div>
            </td>
            <td style="color:var(--text-muted); font-size:0.8rem">${disk.disk_type}</td>
            <td>
                <button class="fm-btn" onclick="event.stopPropagation(); openPhysicalDisk('${disk.id}')" style="padding:0.25rem 0.6rem; font-size:0.75rem;">
                    Buka Drive <i class="fa-solid fa-arrow-right" style="margin-left:4px; font-size:0.7rem;"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function openPhysicalDisk(diskId) {
    const disk = physicalDisksData.find(d => d.id === diskId);
    if (!disk) return;
    
    // Jika disk hanya memiliki 1 volume, langsung masuk ke foldernya
    if (disk.partitions && disk.partitions.length === 1) {
        return loadFiles(disk.partitions[0].mountpoint);
    }

    viewMode = 'drives';
    currentPath = 'drives://' + diskId;

    const lmBtn = document.getElementById('btn-load-more');
    if (lmBtn) lmBtn.style.display = 'none';

    renderBreadcrumbs(currentPath);
    updateSidebarActive('drives://' + diskId);
    document.getElementById('status-path').textContent = disk.name;
    document.getElementById('status-text').textContent = `${(disk.partitions || []).length} volume di ${disk.name}`;

    const tbody = document.getElementById('file-list');
    tbody.innerHTML = '';

    (disk.partitions || []).forEach(part => {
        const tr = document.createElement('tr');
        tr.onclick = (e) => selectVolumeRow(tr, part, disk, e);
        tr.ondblclick = () => loadFiles(part.mountpoint);

        const usage = part.usage || {};
        const usedGB = usage.total ? (usage.used / (1024**3)).toFixed(1) : '-';
        const totalGB = usage.total ? (usage.total / (1024**3)).toFixed(1) : (part.size ? (part.size / (1024**3)).toFixed(1) : '-');
        const percent = usage.percent || 0;

        let barColor = '#238636';
        if (percent > 70) barColor = '#d29922';
        if (percent > 90) barColor = '#f85149';

        let volIcon = 'fa-folder';
        if (part.mountpoint === '/') volIcon = 'fa-folder-tree';
        else if (part.mountpoint === '/home') volIcon = 'fa-house-user';
        else if (part.mountpoint === '/mnt/data') volIcon = 'fa-database';

        tr.innerHTML = `
            <td>
                <div style="display:flex; align-items:center; gap:0.8rem">
                    <span class="fm-icon dir" style="font-size:1.3rem"><i class="fa-solid ${volIcon}"></i></span>
                    <div>
                        <div style="font-weight:600; display:flex; align-items:center; gap:0.5rem">
                            <span>${part.label}</span>
                            <span style="font-family:monospace; color:#9198e5; font-size:0.75rem;">(${part.mountpoint})</span>
                        </div>
                        <div style="font-size:0.75rem; color:#888; margin-top:2px;">
                            ${part.device} • ${part.fstype}
                        </div>
                    </div>
                </div>
            </td>
            <td>
                <div style="width:140px">
                    <div style="font-size:0.75rem; margin-bottom:4px; display:flex; justify-content:space-between">
                        <span>${usedGB} / ${totalGB} GB</span>
                        <span>${percent}%</span>
                    </div>
                    <div style="height:6px; background:rgba(255,255,255,0.1); border-radius:3px; overflow:hidden">
                        <div style="width:${Math.min(percent, 100)}%; height:100%; background:${barColor}"></div>
                    </div>
                </div>
            </td>
            <td style="color:var(--text-muted); font-size:0.8rem">${part.fstype}</td>
            <td>
                <button class="fm-btn" onclick="event.stopPropagation(); loadFiles('${part.mountpoint}')" style="padding:0.25rem 0.6rem; font-size:0.75rem;">
                    Buka Folder <i class="fa-solid fa-folder-open" style="margin-left:4px; font-size:0.7rem;"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function selectDiskRow(tr, disk, e) {
    document.querySelectorAll('.fm-table tr').forEach(r => r.classList.remove('selected'));
    tr.classList.add('selected');
    selectedItem = {
        name: disk.name,
        is_dir: true,
        path: 'drives://' + disk.id,
        size: `${disk.size_gb} GB`,
        date: '-',
        perm: disk.disk_type
    };
    updateDetailPanel();
}

function selectVolumeRow(tr, part, disk, e) {
    document.querySelectorAll('.fm-table tr').forEach(r => r.classList.remove('selected'));
    tr.classList.add('selected');
    selectedItem = {
        name: part.label,
        is_dir: true,
        path: part.mountpoint,
        size: part.usage ? formatSize(part.usage.total) : (part.size ? formatSize(part.size) : '-'),
        date: '-',
        perm: `${disk.disk_type} (${part.fstype})`
    };
    updateDetailPanel();
}

function renderDriveTable(drives) {
    const tbody = document.getElementById('file-list');
    tbody.innerHTML = '';
    
    drives.forEach(drive => {
        const tr = document.createElement('tr');
        tr.onclick = (e) => selectDriveRow(tr, drive, e);
        tr.ondblclick = () => loadFiles(drive.mountpoint);
        
        const usedGB = drive.total ? (drive.used / 1024**3).toFixed(1) : '-';
        const totalGB = drive.total ? (drive.total / 1024**3).toFixed(1) : '-';
        const percent = drive.percent || 0;
        
        let barColor = '#238636';
        if (percent > 70) barColor = '#d29922';
        if (percent > 90) barColor = '#f85149';

        tr.innerHTML = `
            <td>
                <div style="display:flex; align-items:center; gap:0.8rem">
                    <span class="fm-icon dir" style="font-size:1.2rem"><i class="fa-solid fa-hard-drive"></i></span>
                    <div>
                        <div style="font-weight:500">${drive.label || drive.mountpoint}</div>
                        <div style="font-size:0.75rem; color:#888">${drive.device} (${drive.fstype})</div>
                    </div>
                </div>
            </td>
            <td>
                <div style="width:120px">
                    <div style="font-size:0.75rem; margin-bottom:4px; display:flex; justify-content:space-between">
                        <span>${usedGB} / ${totalGB} GB</span>
                        <span>${percent}%</span>
                    </div>
                    <div style="height:6px; background:rgba(255,255,255,0.1); border-radius:3px; overflow:hidden">
                        <div style="width:${percent}%; height:100%; background:${barColor}"></div>
                    </div>
                </div>
            </td>
            <td style="color:var(--text-muted)">-</td>
            <td style="color:var(--text-muted)">-</td>
        `;
        tbody.appendChild(tr);
    });
}

function selectDriveRow(tr, drive, e) {
    document.querySelectorAll('.fm-table tr').forEach(r => r.classList.remove('selected'));
    tr.classList.add('selected');
    selectedItem = {
        name: drive.label || drive.mountpoint,
        is_dir: true,
        path: drive.mountpoint,
        size: drive.total ? formatSize(drive.total) : '-',
        date: '-',
        perm: drive.fstype
    };
    updateDetailPanel();
}

function buildSidebarTree() {
    const container = document.getElementById('sidebar-tree');
    container.innerHTML = '';
    
    // 1. Quick Access Header
    const qaHeader = document.createElement('div');
    qaHeader.style.fontSize = '0.7rem';
    qaHeader.style.color = 'var(--text-muted)';
    qaHeader.style.textTransform = 'uppercase';
    qaHeader.style.letterSpacing = '0.5px';
    qaHeader.style.padding = '0.4rem 0.6rem 0.2rem';
    qaHeader.style.fontWeight = '600';
    qaHeader.textContent = 'Quick Access';
    container.appendChild(qaHeader);

    // This PC
    const pcDiv = document.createElement('div');
    pcDiv.className = 'tree-item';
    pcDiv.dataset.path = 'drives://';
    pcDiv.innerHTML = `<i class="fa-solid fa-display" style="color:#74b9ff"></i> This PC`;
    pcDiv.onclick = () => loadDrives();
    container.appendChild(pcDiv);

    // Clean shortcuts
    const shortcuts = [
        { name: 'User Home (/home)', path: '/home', icon: 'fa-house-user', color: '#55efc4' },
        { name: 'Data Storage (/mnt/data)', path: '/mnt/data', icon: 'fa-database', color: '#ffeaa7' },
        { name: 'System Root (/)', path: '/', icon: 'fa-folder-tree', color: '#a29bfe' }
    ];

    shortcuts.forEach(sc => {
        const div = document.createElement('div');
        div.className = 'tree-item';
        div.dataset.path = sc.path;
        div.innerHTML = `<i class="fa-solid ${sc.icon}" style="color:${sc.color}"></i> ${sc.name}`;
        div.onclick = () => loadFiles(sc.path);
        container.appendChild(div);
    });
    
    // 2. Physical Drives Header
    const drivesHeader = document.createElement('div');
    drivesHeader.style.fontSize = '0.7rem';
    drivesHeader.style.color = 'var(--text-muted)';
    drivesHeader.style.textTransform = 'uppercase';
    drivesHeader.style.letterSpacing = '0.5px';
    drivesHeader.style.padding = '0.8rem 0.6rem 0.2rem';
    drivesHeader.style.fontWeight = '600';
    drivesHeader.textContent = 'Physical Drives';
    container.appendChild(drivesHeader);

    fetch('/api/files/drives')
        .then(r => r.json())
        .then(data => {
            physicalDisksData = data.physical_disks || [];
            if (physicalDisksData.length > 0) {
                physicalDisksData.forEach(disk => {
                    const diskIcon = disk.is_ssd ? 'fa-bolt' : 'fa-hard-drive';
                    const diskColor = disk.is_ssd ? '#55efc4' : '#74b9ff';
                    
                    const diskDiv = document.createElement('div');
                    diskDiv.className = 'tree-item';
                    diskDiv.dataset.path = 'drives://' + disk.id;
                    diskDiv.style.fontWeight = '600';
                    diskDiv.innerHTML = `<i class="fa-solid ${diskIcon}" style="color:${diskColor}"></i> ${disk.name}`;
                    diskDiv.onclick = () => openPhysicalDisk(disk.id);
                    container.appendChild(diskDiv);

                    // List volumes indented under this physical drive
                    (disk.partitions || []).forEach(part => {
                        let volIcon = 'fa-folder';
                        if (part.mountpoint === '/') volIcon = 'fa-folder-tree';
                        else if (part.mountpoint === '/home') volIcon = 'fa-house-user';
                        else if (part.mountpoint === '/mnt/data') volIcon = 'fa-database';

                        const partDiv = document.createElement('div');
                        partDiv.className = 'tree-item';
                        partDiv.dataset.path = part.mountpoint;
                        partDiv.style.paddingLeft = '1.4rem';
                        partDiv.style.fontSize = '0.8rem';
                        partDiv.innerHTML = `<i class="fa-solid ${volIcon}" style="opacity:0.8; font-size:0.75rem;"></i> ${part.label} (${part.mountpoint})`;
                        partDiv.onclick = () => loadFiles(part.mountpoint);
                        container.appendChild(partDiv);
                    });
                });
            } else if (data.drives) {
                data.drives.forEach(drive => {
                    const div = document.createElement('div');
                    div.className = 'tree-item';
                    div.dataset.path = drive.mountpoint;
                    div.innerHTML = `<i class="fa-solid fa-hard-drive"></i> ${drive.label || drive.mountpoint}`;
                    div.onclick = () => loadFiles(drive.mountpoint);
                    container.appendChild(div);
                });
            }
        })
        .catch(err => console.error("Sidebar drives fetch error:", err));
}

function loadFiles(path, page = 1) {
    viewMode = 'files';
    if (page === 1) {
        document.getElementById('file-list').innerHTML = '';
        document.getElementById('status-text').textContent = 'Loading...';
        currentPage = 1;
        selectedItem = null;
        updateDetailPanel();
    }

    isLoading = true;

    fetch(`/api/files/list?path=${encodeURIComponent(path)}&page=${page}`)
        .then(r => r.json())
        .then(data => {
            isLoading = false;

            if (data.error) {
                alert("Error: " + data.error);
                return;
            }

            currentPath = data.current_path;

            if (page === 1) {
                renderBreadcrumbs(currentPath);
                updateSidebarActive(currentPath);
            }

            renderTable(data.items, page === 1);

            hasMore = data.has_more;
            currentPage = page;

            const lmBtn = document.getElementById('btn-load-more');
            if (lmBtn) lmBtn.style.display = hasMore ? 'block' : 'none';

            document.getElementById('status-text').textContent = `${data.total || 0} items`;
            document.getElementById('status-path').textContent = currentPath;
        })
        .catch(err => {
            console.error(err);
            isLoading = false;
        });
}

function loadMore() {
    if (hasMore && !isLoading) {
        loadFiles(currentPath, currentPage + 1);
    }
}

function updateSidebarActive(path) {
    document.querySelectorAll('.tree-item').forEach(el => {
        el.classList.toggle('active', el.dataset.path === path);
    });
}

function renderBreadcrumbs(path) {
    const container = document.getElementById('breadcrumbs');
    container.innerHTML = '';

    if (path === 'drives://') {
        const el = document.createElement('span');
        el.className = 'fm-crumb active';
        el.innerHTML = '<i class="fa-solid fa-display"></i> This PC';
        container.appendChild(el);
        return;
    }

    // Always show "This PC" as root of breadcrumbs
    const pcEl = document.createElement('span');
    pcEl.className = 'fm-crumb';
    pcEl.innerHTML = '<i class="fa-solid fa-display"></i> This PC';
    pcEl.onclick = () => loadDrives();
    container.appendChild(pcEl);

    const pcSep = document.createElement('span');
    pcSep.className = 'fm-crumb-sep';
    pcSep.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
    container.appendChild(pcSep);

    if (path.startsWith('drives://')) {
        const diskId = path.replace('drives://', '');
        const disk = physicalDisksData.find(d => d.id === diskId);
        const diskEl = document.createElement('span');
        diskEl.className = 'fm-crumb active';
        const dIcon = (disk && disk.is_ssd) ? 'fa-bolt' : 'fa-hard-drive';
        diskEl.innerHTML = `<i class="fa-solid ${dIcon}"></i> ${disk ? disk.name : diskId}`;
        container.appendChild(diskEl);
        return;
    }

    // Root (/)
    const rootEl = document.createElement('span');
    rootEl.className = 'fm-crumb' + (path === '/' ? ' active' : '');
    rootEl.textContent = '/';
    rootEl.onclick = () => loadFiles('/');
    container.appendChild(rootEl);

    if (path === '/') return;

    const parts = path.split('/').filter(p => p);
    let builtPath = '';
    parts.forEach((part, index) => {
        builtPath += '/' + part;

        const sep = document.createElement('span');
        sep.className = 'fm-crumb-sep';
        sep.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
        container.appendChild(sep);

        const el = document.createElement('span');
        el.className = 'fm-crumb';
        el.textContent = part;
        const p = builtPath;

        if (index === parts.length - 1) {
            el.classList.add('active');
        } else {
            el.onclick = () => loadFiles(p);
        }
        container.appendChild(el);
    });
}

function formatSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function renderTable(items, isNew) {
    const tbody = document.getElementById('file-list');

    if (isNew && items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:2rem; color:var(--text-muted)">Empty folder</td></tr>';
        return;
    }

    items.forEach(item => {
        const tr = document.createElement('tr');
        tr.onclick = (e) => selectRow(tr, item, e);
        tr.ondblclick = () => openItem(item);
        tr.oncontextmenu = (e) => showContextMenu(e, item, tr);

        let iconClass = item.is_dir ? 'fa-folder dir' : 'fa-file file';
        if (!item.is_dir) {
            if (item.name.match(/\.(py|js|html|css|json|xml|sh)$/i)) iconClass = 'fa-file-code file';
            else if (item.name.match(/\.(txt|log|md|conf)$/i)) iconClass = 'fa-file-lines file';
            else if (item.name.match(/\.(png|jpg|jpeg|gif|svg)$/i)) iconClass = 'fa-file-image file';
            else if (item.name.match(/\.(zip|tar|gz|7z)$/i)) iconClass = 'fa-file-zipper file';
        }

        tr.innerHTML = `
            <td><span class="fm-icon ${item.is_dir ? 'dir' : 'file'}"><i class="fa-solid ${iconClass.split(' ')[0]}"></i></span>${item.name}</td>
            <td>${item.size}</td>
            <td style="font-family:monospace; color:#888">${item.perm || '-'}</td>
            <td style="color:var(--text-muted)">${item.date}</td>
        `;
        tbody.appendChild(tr);
    });
}

function selectRow(tr, item, e) {
    document.querySelectorAll('.fm-table tr').forEach(r => r.classList.remove('selected'));
    tr.classList.add('selected');
    selectedItem = item;
    updateDetailPanel();

    // Don't trigger when right-clicking
    if (e && e.button === 2) return;
}

function updateDetailPanel() {
    const panel = document.getElementById('detail-panel');
    if (!selectedItem) {
        panel.classList.add('hidden');
        return;
    }

    panel.classList.remove('hidden');
    document.getElementById('detail-name').textContent = selectedItem.name;
    document.getElementById('detail-type').textContent = selectedItem.is_dir ? 'Folder' : 'File';
    document.getElementById('detail-size').textContent = selectedItem.size;
    document.getElementById('detail-date').textContent = selectedItem.date;
    document.getElementById('detail-perm').textContent = selectedItem.perm || '-';
    document.getElementById('detail-uid').textContent = selectedItem.uid ?? '-';
    document.getElementById('detail-gid').textContent = selectedItem.gid ?? '-';
}

function openItem(item) {
    if (item.is_dir) {
        loadFiles(item.path);
    } else {
        openEditor(item);
    }
}

function openSelected() {
    if (selectedItem) openItem(selectedItem);
    hideContextMenu();
}

// Context Menu
function showContextMenu(e, item, tr) {
    e.preventDefault();
    selectRow(tr, item);

    const menu = document.getElementById('context-menu');
    menu.classList.remove('hidden');
    menu.style.left = e.clientX + 'px';
    menu.style.top = e.clientY + 'px';

    // Adjust if off-screen
    const rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) menu.style.left = (window.innerWidth - rect.width - 10) + 'px';
    if (rect.bottom > window.innerHeight) menu.style.top = (window.innerHeight - rect.height - 10) + 'px';
}

function hideContextMenu() {
    document.getElementById('context-menu').classList.add('hidden');
}

// Actions
function createNew(type) {
    const name = prompt(`Enter name for new ${type}:`);
    if (!name) return;

    const path = currentPath === '/' ? `/${name}` : `${currentPath}/${name}`;

    fetch('/api/files/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: type === 'folder' ? 'create_folder' : 'create_file',
            path: path
        })
    }).then(refreshAfterAction);
}

function renameItem() {
    hideContextMenu();
    if (!selectedItem) return;
    const newName = prompt("Rename to:", selectedItem.name);
    if (!newName || newName === selectedItem.name) return;

    const dir = currentPath === '/' ? '' : currentPath;
    const newPath = `${dir}/${newName}`;

    fetch('/api/files/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'rename',
            path: selectedItem.path,
            new_path: newPath
        })
    }).then(refreshAfterAction);
}

function deleteItem() {
    hideContextMenu();
    if (!selectedItem) return;
    if (!confirm(`Delete "${selectedItem.name}"? This cannot be undone.`)) return;

    fetch('/api/files/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'delete',
            path: selectedItem.path
        })
    }).then(refreshAfterAction);
}

function copyItem(op) {
    hideContextMenu();
    if (!selectedItem) return;
    clipboard = { path: selectedItem.path, op: op };
}

function pasteItem() {
    hideContextMenu();
    if (!clipboard) return;

    fetch('/api/files/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'paste',
            path: currentPath,
            source: clipboard.path,
            operation: clipboard.op
        })
    }).then(r => r.json()).then(data => {
        if (data.success) {
            clipboard = null;
            loadFiles(currentPath);
        } else {
            alert("Paste failed: " + (data.error || 'Unknown'));
        }
    });
}

function refreshAfterAction(res) {
    res.json().then(data => {
        if (data.success) loadFiles(currentPath);
        else alert("Action failed: " + (data.error || 'Unknown'));
    });
}

// Toggle Functions
function toggleCompact() {
    document.body.classList.toggle('compact');
    document.getElementById('btn-compact').classList.toggle('active');
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('collapsed');
    document.getElementById('btn-sidebar').classList.toggle('active');
}

// Editor
const editorOverlay = document.getElementById('editor-overlay');
const editorText = document.getElementById('editor-textarea');
const editorTitle = document.getElementById('editor-filename');
let currentEditingPath = null;

function openEditor(item) {
    if (!item || item.is_dir) return;
    hideContextMenu();

    editorOverlay.style.display = 'flex';
    editorTitle.textContent = item.name;
    currentEditingPath = item.path;
    editorText.value = "Loading...";

    fetch(`/api/files/content?path=${encodeURIComponent(item.path)}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                editorText.value = "Error: " + data.error;
            } else {
                editorText.value = data.content;
            }
        });
}

function saveFile() {
    if (!currentEditingPath) return;

    fetch('/api/files/content', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            path: currentEditingPath,
            content: editorText.value
        })
    }).then(r => r.json()).then(data => {
        if (data.success) {
            alert("Saved!");
            closeEditor();
        } else {
            alert("Error: " + data.error);
        }
    });
}

function closeEditor() {
    editorOverlay.style.display = 'none';
    currentEditingPath = null;
    editorText.value = '';
}

// Search / Filter
let allItems = [];

function filterFiles(query) {
    if (!query) {
        // Reload to show all
        loadFiles(currentPath);
        return;
    }

    const lowerQuery = query.toLowerCase();
    const tbody = document.getElementById('file-list');
    const rows = tbody.querySelectorAll('tr');

    rows.forEach(row => {
        const name = row.querySelector('td')?.textContent?.toLowerCase() || '';
        row.style.display = name.includes(lowerQuery) ? '' : 'none';
    });
}

function clearSearch() {
    document.getElementById('search-input').value = '';
    loadFiles(currentPath);
}

// Close detail panel
function closeDetailPanel() {
    selectedItem = null;
    document.querySelectorAll('.fm-table tr').forEach(r => r.classList.remove('selected'));
    document.getElementById('detail-panel').classList.add('hidden');
}

// Open in Terminal - Integration
function openInTerminal() {
    hideContextMenu();
    let path = currentPath;
    if (selectedItem && selectedItem.is_dir) {
        path = selectedItem.path;
    }
    window.location.href = '/terminal?path=' + encodeURIComponent(path);
}

// Upload Files
function uploadFiles(files) {
    if (!files || files.length === 0) return;

    const formData = new FormData();
    formData.append('path', currentPath);

    for (let i = 0; i < files.length; i++) {
        formData.append('file', files[i]);
    }

    // Show uploading status
    document.getElementById('status-text').textContent = `Uploading ${files.length} file(s)...`;

    fetch('/api/files/upload', {
        method: 'POST',
        body: formData
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                alert(`Uploaded: ${data.files.join(', ')}`);
                loadFiles(currentPath);
            } else {
                alert('Upload failed: ' + (data.error || 'Unknown'));
            }
        })
        .catch(err => {
            alert('Upload error: ' + err);
        })
        .finally(() => {
            // Reset input
            document.getElementById('upload-input').value = '';
        });
}

// Download Selected File
function downloadSelected() {
    if (!selectedItem) {
        alert('Pilih file untuk di-download');
        return;
    }
    if (selectedItem.is_dir) {
        alert('Tidak bisa download folder');
        return;
    }

    // Open download in new tab
    window.open('/api/files/download?path=' + encodeURIComponent(selectedItem.path), '_blank');
}
