/**
 * Disaster Recovery & Offsite Backup Engine
 * Eka Dashboard - Modular Frontend Logic
 * Zero Inline JS
 */

document.addEventListener('DOMContentLoaded', () => {
    let summaryData = null;
    let selectedRestoreId = null;

    // Stat Elements
    const statTotalSnapshots = document.getElementById('stat-total-snapshots');
    const statTotalSize = document.getElementById('stat-total-size');
    const statRemoteName = document.getElementById('stat-remote-name');
    const statRcloneStatus = document.getElementById('stat-rclone-status');
    const statLatestDate = document.getElementById('stat-latest-date');
    const statLatestSize = document.getElementById('stat-latest-size');
    const statScheduleStatus = document.getElementById('stat-schedule-status');
    const statScheduleSub = document.getElementById('stat-schedule-sub');

    // Table Body
    const snapshotsTableBody = document.getElementById('snapshots-table-body');
    const btnRefreshList = document.getElementById('btn-refresh-list');

    // Top Bar Actions
    const btnTopQuick = document.getElementById('btn-top-quick');
    const btnTopSync = document.getElementById('btn-top-sync');

    // Create Form
    const inputBackupName = document.getElementById('input-backup-name');
    const checkConfig = document.getElementById('check-config');
    const checkDocker = document.getElementById('check-docker');
    const checkUsers = document.getElementById('check-users');
    const checkNginx = document.getElementById('check-nginx');
    const checkSystem = document.getElementById('check-system');
    const selectUploadRemote = document.getElementById('select-upload-remote');
    const btnSubmitCreate = document.getElementById('btn-submit-create');

    // Cloud / Rclone Elements
    const rcloneActionBox = document.getElementById('rclone-action-box');
    const rcloneRemotesContainer = document.getElementById('rclone-remotes-container');

    // Schedule Elements
    const checkScheduleEnabled = document.getElementById('check-schedule-enabled');
    const selectScheduleFreq = document.getElementById('select-schedule-freq');
    const inputScheduleTime = document.getElementById('input-schedule-time');
    const selectScheduleRemote = document.getElementById('select-schedule-remote');
    const btnSaveSchedule = document.getElementById('btn-save-schedule');

    // Modals
    const modalInspect = document.getElementById('modal-inspect');
    const inspectModalBody = document.getElementById('inspect-modal-body');
    const btnCloseInspect = document.getElementById('btn-close-inspect');
    const btnInspectCloseFooter = document.getElementById('btn-inspect-close-footer');

    const modalRestore = document.getElementById('modal-restore');
    const restoreTargetName = document.getElementById('restore-target-name');
    const btnCancelRestore = document.getElementById('btn-cancel-restore');
    const btnExecuteRestore = document.getElementById('btn-execute-restore');

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

            if (targetTab === 'tab-snapshots') fetchSnapshots();
            if (targetTab === 'tab-cloud') fetchSummary();
        });
    });

    // Toast Notification Utility
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.style.position = 'fixed';
        toast.style.bottom = '24px';
        toast.style.right = '24px';
        toast.style.padding = '12px 20px';
        toast.style.borderRadius = '12px';
        toast.style.color = '#fff';
        toast.style.fontSize = '13px';
        toast.style.fontWeight = '600';
        toast.style.zIndex = '9999';
        toast.style.backdropFilter = 'blur(16px)';
        toast.style.boxShadow = '0 8px 32px rgba(0,0,0,0.4)';
        toast.style.display = 'flex';
        toast.style.alignItems = 'center';
        toast.style.gap = '10px';
        toast.style.transition = 'all 0.3s ease';

        if (type === 'success') {
            toast.style.background = 'rgba(16, 185, 129, 0.85)';
            toast.style.border = '1px solid rgba(16, 185, 129, 0.3)';
            toast.innerHTML = `<i class="fa-solid fa-circle-check"></i> <span>${escapeHtml(message)}</span>`;
        } else if (type === 'error') {
            toast.style.background = 'rgba(239, 68, 68, 0.85)';
            toast.style.border = '1px solid rgba(239, 68, 68, 0.3)';
            toast.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> <span>${escapeHtml(message)}</span>`;
        } else {
            toast.style.background = 'rgba(15, 23, 42, 0.85)';
            toast.style.border = '1px solid rgba(255, 255, 255, 0.15)';
            toast.innerHTML = `<i class="fa-solid fa-circle-info"></i> <span>${escapeHtml(message)}</span>`;
        }

        document.body.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    function escapeHtml(text) {
        if (!text) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Fetch Summary & Telemetry
    async function fetchSummary() {
        try {
            const res = await fetch('/api/backup/summary');
            const data = await res.json();
            if (!data.success) return;

            summaryData = data.summary;
            renderSummaryCards();
            renderRcloneSection();
            renderScheduleSection();
        } catch (err) {
            console.error('Error fetching backup summary:', err);
        }
    }

    function renderSummaryCards() {
        if (!summaryData) return;

        statTotalSnapshots.textContent = summaryData.total_backups || 0;
        statTotalSize.textContent = `Ukuran Total: ${summaryData.total_size_formatted || '0 B'}`;

        const rclone = summaryData.rclone || {};
        if (rclone.installed) {
            const remotes = rclone.remotes || [];
            if (remotes.length > 0) {
                statRemoteName.textContent = remotes[0];
                statRcloneStatus.innerHTML = `<span style="color: #10b981;"><i class="fa-solid fa-circle-check"></i> ${remotes.length} Remote Siap</span>`;
            } else {
                statRemoteName.textContent = 'Tanpa Remote';
                statRcloneStatus.textContent = 'Rclone terpasang, remote belum diset';
            }
        } else {
            statRemoteName.textContent = 'Lokal Saja';
            statRcloneStatus.innerHTML = `<span style="color: #f59e0b;"><i class="fa-solid fa-triangle-exclamation"></i> Rclone belum terpasang</span>`;
        }

        const latest = summaryData.latest_backup;
        if (latest) {
            statLatestDate.textContent = latest.date;
            statLatestSize.textContent = `${latest.filename} (${latest.size})`;
        } else {
            statLatestDate.textContent = 'Belum Ada';
            statLatestSize.textContent = 'Menunggu snapshot pertama';
        }

        const sched = summaryData.schedule || {};
        if (sched.enabled) {
            statScheduleStatus.textContent = sched.frequency === 'daily' ? 'Harian' : 'Mingguan';
            statScheduleSub.innerHTML = `<span style="color: #10b981;"><i class="fa-solid fa-clock"></i> Pukul ${sched.time || '02:00'} WIB</span>`;
        } else {
            statScheduleStatus.textContent = 'Nonaktif';
            statScheduleSub.textContent = 'Jadwal otomatis dimatikan';
        }

        // Update Remote Dropdowns
        populateRemoteDropdowns(rclone.remotes || []);
    }

    function populateRemoteDropdowns(remotes) {
        const updateSelect = (el) => {
            if (!el) return;
            const currentVal = el.value;
            el.innerHTML = '<option value="">Simpan Lokal Saja (Tanpa Cloud Sync)</option>';
            remotes.forEach(r => {
                const opt = document.createElement('option');
                opt.value = r;
                opt.textContent = `Remote Cloud: ${r}`;
                if (r === currentVal) opt.selected = true;
                el.appendChild(opt);
            });
        };
        updateSelect(selectUploadRemote);
        updateSelect(selectScheduleRemote);
    }

    function renderRcloneSection() {
        if (!summaryData) return;
        const rclone = summaryData.rclone || {};

        if (!rclone.installed) {
            rcloneActionBox.innerHTML = `
                <button id="btn-install-rclone" class="btn btn-primary" style="background: linear-gradient(135deg, #38bdf8, #2563eb);">
                    <i class="fa-solid fa-download"></i> Pasang Rclone via APT
                </button>
            `;
            rcloneRemotesContainer.innerHTML = `
                <div style="background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.25); border-radius: 12px; padding: 20px; text-align: center;">
                    <i class="fa-solid fa-cloud-arrow-up" style="font-size: 32px; color: #f59e0b; margin-bottom: 10px;"></i>
                    <h4 style="margin: 0 0 6px 0; color: #fff; font-size: 15px;">Rclone Belum Terpasang pada Host</h4>
                    <p style="margin: 0; font-size: 12px; color: #94a3b8; max-width: 500px; margin: 0 auto;">
                        Pasang Rclone untuk mengaktifkan fitur sinkronisasi otomatis ke Google Drive, AWS S3, Cloudflare R2, atau storage cloud lainnya.
                    </p>
                </div>
            `;
            const btnInst = document.getElementById('btn-install-rclone');
            if (btnInst) btnInst.addEventListener('click', installRclone);
        } else {
            rcloneActionBox.innerHTML = `
                <button id="btn-sync-all-action" class="btn btn-primary" style="background: linear-gradient(135deg, #38bdf8, #2563eb);">
                    <i class="fa-solid fa-cloud-arrow-up"></i> Sinkronkan Semua ke Cloud
                </button>
            `;
            const btnSync = document.getElementById('btn-sync-all-action');
            if (btnSync) btnSync.addEventListener('click', syncAllSnapshots);

            const remotes = rclone.remotes || [];
            if (remotes.length === 0) {
                rcloneRemotesContainer.innerHTML = `
                    <div style="background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 12px; padding: 20px; text-align: center;">
                        <i class="fa-solid fa-circle-info" style="font-size: 28px; color: #38bdf8; margin-bottom: 8px;"></i>
                        <h4 style="margin: 0 0 6px 0; color: #fff; font-size: 15px;">Rclone Aktif (${escapeHtml(rclone.version || '')})</h4>
                        <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                            Belum ada remote cloud yang dikonfigurasi. Ikuti panduan di bawah untuk membuat remote pertama Anda via <code>rclone config</code>.
                        </p>
                    </div>
                `;
            } else {
                let html = '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px;">';
                remotes.forEach(r => {
                    html += `
                        <div style="background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 16px; display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <div style="font-weight: 700; font-size: 14px; color: #fff; display: flex; align-items: center; gap: 8px;">
                                    <i class="fa-solid fa-hard-drive" style="color: #38bdf8;"></i> ${escapeHtml(r)}
                                </div>
                                <div style="font-size: 11px; color: #10b981; margin-top: 4px;">
                                    <i class="fa-solid fa-circle-check"></i> Siap Menampung Backup
                                </div>
                            </div>
                            <button class="btn btn-secondary btn-sync-single" data-remote="${escapeHtml(r)}" style="padding: 6px 12px; font-size: 12px;">
                                <i class="fa-solid fa-arrow-up-from-bracket"></i> Sync
                            </button>
                        </div>
                    `;
                });
                html += '</div>';
                rcloneRemotesContainer.innerHTML = html;

                document.querySelectorAll('.btn-sync-single').forEach(b => {
                    b.addEventListener('click', () => {
                        const rName = b.getAttribute('data-remote');
                        syncAllSnapshots(rName);
                    });
                });
            }
        }
    }

    function renderScheduleSection() {
        if (!summaryData) return;
        const sched = summaryData.schedule || {};
        checkScheduleEnabled.checked = !!sched.enabled;
        selectScheduleFreq.value = sched.frequency || 'daily';
        inputScheduleTime.value = sched.time || '02:00';
        if (sched.remote) selectScheduleRemote.value = sched.remote;
    }

    // Fetch Snapshots List
    async function fetchSnapshots() {
        snapshotsTableBody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state">
                    <i class="fa-solid fa-spinner fa-spin"></i>
                    <div>Memuat daftar snapshot...</div>
                </td>
            </tr>
        `;

        try {
            const res = await fetch('/api/backup/list');
            const data = await res.json();
            if (!data.success) {
                snapshotsTableBody.innerHTML = `<tr><td colspan="6" class="empty-state"><i class="fa-solid fa-circle-xmark" style="color:#ff6b6b"></i><div>Gagal memuat snapshot: ${escapeHtml(data.error)}</div></td></tr>`;
                return;
            }

            const backups = data.backups || [];
            if (backups.length === 0) {
                snapshotsTableBody.innerHTML = `
                    <tr>
                        <td colspan="6" class="empty-state">
                            <i class="fa-solid fa-box-open"></i>
                            <div>Belum ada snapshot disaster recovery. Klik "Buat Snapshot Baru" untuk mengamankan server.</div>
                        </td>
                    </tr>
                `;
                return;
            }

            let html = '';
            backups.forEach(b => {
                const comps = b.components || ['Dashboard'];
                const badgesHtml = comps.map(c => `<span class="badge badge-info" style="font-size: 10px; margin-right: 4px;">${escapeHtml(c)}</span>`).join('');
                const statusHtml = b.synced
                    ? `<span class="badge badge-success"><i class="fa-solid fa-cloud-check"></i> Synced</span>`
                    : `<span class="badge badge-warning"><i class="fa-solid fa-hard-drive"></i> Lokal</span>`;

                html += `
                    <tr>
                        <td>
                            <div style="font-weight: 700; color: #fff;">${escapeHtml(b.name)}</div>
                            <div style="font-size: 11px; color: #94a3b8; font-family: monospace;">${escapeHtml(b.filename)}</div>
                        </td>
                        <td>${escapeHtml(b.date)}</td>
                        <td><strong style="color: #f093fb;">${escapeHtml(b.size)}</strong></td>
                        <td>${badgesHtml}</td>
                        <td>${statusHtml}</td>
                        <td style="text-align: right; white-space: nowrap;">
                            <button class="btn btn-secondary btn-inspect" data-id="${escapeHtml(b.id)}" title="Inspeksi Berkas" style="padding: 6px 10px;">
                                <i class="fa-solid fa-magnifying-glass"></i>
                            </button>
                            <a href="/api/backup/download/${encodeURIComponent(b.id)}" class="btn btn-secondary" title="Download Snapshot" style="padding: 6px 10px;">
                                <i class="fa-solid fa-download"></i>
                            </a>
                            <button class="btn btn-secondary btn-restore" data-id="${escapeHtml(b.id)}" title="Restore Snapshot" style="padding: 6px 10px; color: #f59e0b;">
                                <i class="fa-solid fa-rotate-left"></i>
                            </button>
                            <button class="btn btn-secondary btn-delete" data-id="${escapeHtml(b.id)}" title="Hapus Snapshot" style="padding: 6px 10px; color: #ff6b6b;">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
            });

            snapshotsTableBody.innerHTML = html;

            // Attach event listeners
            document.querySelectorAll('.btn-inspect').forEach(btn => {
                btn.addEventListener('click', () => inspectSnapshot(btn.getAttribute('data-id')));
            });

            document.querySelectorAll('.btn-restore').forEach(btn => {
                btn.addEventListener('click', () => openRestoreModal(btn.getAttribute('data-id')));
            });

            document.querySelectorAll('.btn-delete').forEach(btn => {
                btn.addEventListener('click', () => deleteSnapshot(btn.getAttribute('data-id')));
            });

        } catch (err) {
            snapshotsTableBody.innerHTML = `<tr><td colspan="6" class="empty-state"><i class="fa-solid fa-triangle-exclamation" style="color:#ff6b6b"></i><div>Galat jaringan: ${escapeHtml(err.message)}</div></td></tr>`;
        }
    }

    // Create Snapshot
    btnSubmitCreate.addEventListener('click', async () => {
        const payload = {
            name: inputBackupName.value.trim(),
            include_config: checkConfig.checked,
            include_docker: checkDocker.checked,
            include_users: checkUsers.checked,
            include_nginx: checkNginx.checked,
            include_system: checkSystem.checked,
            sync_remote: selectUploadRemote.value || null
        };

        btnSubmitCreate.disabled = true;
        btnSubmitCreate.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Membuat Snapshot...';
        showToast('Sedang membuat arsip snapshot sistem...', 'info');

        try {
            const res = await fetch('/api/backup/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                showToast(`Snapshot ${data.filename} berhasil dibuat!`, 'success');
                if (data.sync_result) {
                    showToast(data.sync_result, 'info');
                }
                inputBackupName.value = '';
                fetchSummary();
                fetchSnapshots();
                // Switch to snapshots tab
                document.querySelector('[data-tab="tab-snapshots"]').click();
            } else {
                showToast(`Gagal membuat snapshot: ${data.error}`, 'error');
            }
        } catch (err) {
            showToast(`Kesalahan: ${err.message}`, 'error');
        } finally {
            btnSubmitCreate.disabled = false;
            btnSubmitCreate.innerHTML = '<i class="fa-solid fa-download"></i> Buat Snapshot Sekarang';
        }
    });

    // Inspect Snapshot Modal
    async function inspectSnapshot(backupId) {
        inspectModalBody.innerHTML = '<div class="empty-state"><i class="fa-solid fa-spinner fa-spin"></i><div>Membaca struktur file...</div></div>';
        modalInspect.classList.add('active');

        try {
            const res = await fetch(`/api/backup/inspect/${encodeURIComponent(backupId)}`);
            const data = await res.json();
            if (!data.success) {
                inspectModalBody.innerHTML = `<div class="empty-state"><i class="fa-solid fa-circle-xmark" style="color:#ff6b6b"></i><div>Gagal inspeksi: ${escapeHtml(data.error)}</div></div>`;
                return;
            }

            let html = '';
            if (data.manifest) {
                const m = data.manifest;
                html += `
                    <div style="background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 14px; margin-bottom: 16px;">
                        <div style="font-weight: 700; color: #fff; font-size: 14px;">${escapeHtml(m.name)}</div>
                        <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">Host: ${escapeHtml(m.hostname)} | Kernel: ${escapeHtml(m.kernel)}</div>
                        <div style="margin-top: 8px;">
                            ${(m.components || []).map(c => `<span class="badge badge-info" style="font-size: 10px; margin-right: 4px;">${escapeHtml(c)}</span>`).join('')}
                        </div>
                    </div>
                `;
            }

            html += `
                <div style="font-weight: 700; font-size: 12px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px;">
                    Daftar Berkas (${data.count || 0} entri)
                </div>
                <div style="background: #090d16; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; max-height: 380px; overflow-y: auto; font-family: 'JetBrains Mono', monospace; font-size: 12px;">
            `;

            (data.members || []).forEach(m => {
                const icon = m.is_dir ? 'fa-folder' : 'fa-file-code';
                const color = m.is_dir ? '#f59e0b' : '#38bdf8';
                html += `
                    <div style="padding: 6px 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.04); display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: #e2e8f0;"><i class="fa-solid ${icon}" style="color: ${color}; margin-right: 8px;"></i>${escapeHtml(m.name)}</span>
                        <span style="color: #64748b; font-size: 11px;">${escapeHtml(m.size)}</span>
                    </div>
                `;
            });

            html += '</div>';
            inspectModalBody.innerHTML = html;

        } catch (err) {
            inspectModalBody.innerHTML = `<div class="empty-state"><i class="fa-solid fa-triangle-exclamation" style="color:#ff6b6b"></i><div>Galat jaringan: ${escapeHtml(err.message)}</div></div>`;
        }
    }

    btnCloseInspect.addEventListener('click', () => modalInspect.classList.remove('active'));
    btnInspectCloseFooter.addEventListener('click', () => modalInspect.classList.remove('active'));

    // Restore Modal
    function openRestoreModal(backupId) {
        selectedRestoreId = backupId;
        restoreTargetName.textContent = backupId;
        modalRestore.classList.add('active');
    }

    btnCancelRestore.addEventListener('click', () => modalRestore.classList.remove('active'));

    btnExecuteRestore.addEventListener('click', async () => {
        if (!selectedRestoreId) return;
        btnExecuteRestore.disabled = true;
        btnExecuteRestore.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Memulihkan...';

        try {
            const res = await fetch('/api/backup/restore', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: selectedRestoreId })
            });
            const data = await res.json();
            if (data.success) {
                showToast('Snapshot berhasil dipulihkan ke sistem!', 'success');
                modalRestore.classList.remove('active');
            } else {
                showToast(`Gagal restore: ${data.error}`, 'error');
            }
        } catch (err) {
            showToast(`Kesalahan restore: ${err.message}`, 'error');
        } finally {
            btnExecuteRestore.disabled = false;
            btnExecuteRestore.innerHTML = '<i class="fa-solid fa-rotate-left"></i> Ya, Pulihkan Sekarang';
        }
    });

    // Delete Snapshot
    async function deleteSnapshot(backupId) {
        if (!confirm(`Hapus snapshot ${backupId}? Tindakan ini tidak dapat dibatalkan.`)) return;

        try {
            const res = await fetch(`/api/backup/delete/${encodeURIComponent(backupId)}`, {
                method: 'DELETE'
            });
            const data = await res.json();
            if (data.success) {
                showToast('Snapshot berhasil dihapus', 'success');
                fetchSummary();
                fetchSnapshots();
            } else {
                showToast(`Gagal menghapus: ${data.error}`, 'error');
            }
        } catch (err) {
            showToast(`Galat: ${err.message}`, 'error');
        }
    }

    // Install Rclone via APT
    async function installRclone() {
        const btn = document.getElementById('btn-install-rclone');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Memasang Rclone...';
        }
        showToast('Memasang binary rclone pada host via APT...', 'info');

        try {
            const res = await fetch('/api/backup/rclone/install', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                showToast('Rclone berhasil terpasang pada host!', 'success');
                fetchSummary();
            } else {
                showToast(`Gagal memasang rclone: ${data.error}`, 'error');
            }
        } catch (err) {
            showToast(`Kesalahan pemasangan: ${err.message}`, 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-download"></i> Pasang Rclone via APT';
            }
        }
    }

    // Sync All Snapshots
    async function syncAllSnapshots(targetRemote = null) {
        const rem = targetRemote || (summaryData?.rclone?.remotes?.[0] || null);
        if (!rem) {
            showToast('Tidak ada remote cloud yang terkonfigurasi. Tambahkan remote via rclone config terlebih dahulu.', 'error');
            return;
        }

        showToast(`Memulai sinkronisasi backup ke remote ${rem}...`, 'info');
        try {
            const res = await fetch('/api/backup/rclone/sync', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ remote: rem })
            });
            const data = await res.json();
            if (data.success) {
                showToast(data.message, 'success');
                fetchSummary();
                fetchSnapshots();
            } else {
                showToast(`Gagal sinkronisasi: ${data.error}`, 'error');
            }
        } catch (err) {
            showToast(`Galat sinkronisasi: ${err.message}`, 'error');
        }
    }

    // Save Schedule
    btnSaveSchedule.addEventListener('click', async () => {
        const payload = {
            enabled: checkScheduleEnabled.checked,
            frequency: selectScheduleFreq.value,
            time: inputScheduleTime.value,
            remote: selectScheduleRemote.value || null
        };

        btnSaveSchedule.disabled = true;
        btnSaveSchedule.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Menyimpan...';

        try {
            const res = await fetch('/api/backup/schedule', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                showToast('Jadwal backup otomatis berhasil diperbarui!', 'success');
                fetchSummary();
            } else {
                showToast('Gagal menyimpan jadwal backup', 'error');
            }
        } catch (err) {
            showToast(`Kesalahan: ${err.message}`, 'error');
        } finally {
            btnSaveSchedule.disabled = false;
            btnSaveSchedule.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Simpan Jadwal Backup';
        }
    });

    // Top Bar Quick Actions
    btnTopQuick.addEventListener('click', () => {
        document.querySelector('[data-tab="tab-create"]').click();
    });

    btnTopSync.addEventListener('click', () => {
        syncAllSnapshots();
    });

    btnRefreshList.addEventListener('click', () => {
        fetchSnapshots();
        fetchSummary();
    });

    // Initial Load
    fetchSummary();
    fetchSnapshots();
});

