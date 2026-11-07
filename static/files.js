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

function loadDrives() {
    viewMode = 'drives';
    currentPath = 'drives://';

    const lmBtn = document.getElementById('btn-load-more');
    if (lmBtn) lmBtn.style.display = 'none';
    
    document.getElementById('file-list').innerHTML = '';
    document.getElementById('status-text').textContent = 'Loading drives...';
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
            renderDriveTable(data.drives);
            document.getElementById('status-text').textContent = `${data.drives.length} drives found`;
        })
        .catch(err => {
            console.error("Drives fetch error:", err);
            document.getElementById('status-text').textContent = 'Error loading drives';
        });
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
        
        // Progress bar style for disk usage
        let barColor = '#238636'; // Green
        if (percent > 70) barColor = '#d29922'; // Yellow
        if (percent > 90) barColor = '#f85149'; // Red

        tr.innerHTML = `
            <td>
                <div style="display:flex; align-items:center; gap:0.8rem">
                    <span class="fm-icon dir" style="font-size:1.2rem"><i class="fa-solid fa-hard-drive"></i></span>
                    <div>
                        <div style="font-weight:500">${drive.mountpoint}</div>
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
    // Mock a selectedItem for detail panel but minimal
    selectedItem = {
        name: drive.mountpoint,
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
    
    // PC / Home root
    const pcDiv = document.createElement('div');
    pcDiv.className = 'tree-item';
    pcDiv.dataset.path = 'drives://';
    pcDiv.innerHTML = `<i class="fa-solid fa-display"></i> This PC`;
    pcDiv.onclick = () => loadDrives();
    container.appendChild(pcDiv);

    quickFolders.forEach(folder => {
        const name = folder === '/' ? 'System Root (/)' : folder.split('/').pop();
        const div = document.createElement('div');
        div.className = 'tree-item';
        div.dataset.path = folder;
        div.innerHTML = `<i class="fa-solid fa-folder"></i> ${name}`;
        div.onclick = () => loadFiles(folder);
        container.appendChild(div);
    });
    
    // Separate drives section
    const label = document.createElement('div');
    label.style.fontSize = '0.7rem';
    label.style.color = 'var(--text-muted)';
    label.style.textTransform = 'uppercase';
    label.style.padding = '0.8rem 0.6rem 0.4rem';
    label.textContent = 'Drives';
    container.appendChild(label);

    fetch('/api/files/drives')
        .then(r => r.json())
        .then(data => {
            if (data.drives) {
                data.drives.forEach(drive => {
                    const div = document.createElement('div');
                    div.className = 'tree-item';
                    div.dataset.path = drive.mountpoint;
                    div.innerHTML = `<i class="fa-solid fa-hard-drive"></i> ${drive.mountpoint}`;
                    div.onclick = () => loadFiles(drive.mountpoint);
                    container.appendChild(div);
                });
            }
        });
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
    pcEl.innerHTML = 'This PC';
    pcEl.onclick = () => loadDrives();
    container.appendChild(pcEl);

    const pcSep = document.createElement('span');
    pcSep.className = 'fm-crumb-sep';
    pcSep.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
    container.appendChild(pcSep);

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
