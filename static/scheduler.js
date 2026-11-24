/**
 * Task Scheduler & Cron Jobs Manager
 * Eka Dashboard - Modular Frontend Logic
 * Zero Inline JS
 */

document.addEventListener('DOMContentLoaded', () => {
    let cronJobs = [];
    let systemdTimers = [];
    let systemUsers = ['root'];

    // DOM Elements
    const statTotalJobs = document.getElementById('stat-total-jobs');
    const statActiveJobs = document.getElementById('stat-active-jobs');
    const statTotalTimers = document.getElementById('stat-total-timers');
    const statActiveTimers = document.getElementById('stat-active-timers');
    const statNextUnit = document.getElementById('stat-next-unit');
    const statNextTime = document.getElementById('stat-next-time');
    const statUsersCount = document.getElementById('stat-users-count');

    const badgeCountCron = document.getElementById('badge-count-cron');
    const badgeCountTimers = document.getElementById('badge-count-timers');

    const cronTableBody = document.getElementById('cron-table-body');
    const timersTableBody = document.getElementById('timers-table-body');

    const cronSearch = document.getElementById('cron-search');
    const cronFilterUser = document.getElementById('cron-filter-user');
    const cronFilterStatus = document.getElementById('cron-filter-status');

    const timersSearch = document.getElementById('timers-search');
    const timersFilterStatus = document.getElementById('timers-filter-status');

    const btnRefresh = document.getElementById('btn-refresh');
    const btnAddCron = document.getElementById('btn-add-cron');

    // Modal Elements
    const modalCron = document.getElementById('modal-cron');
    const modalTitle = document.getElementById('modal-title');
    const modalCloseBtn = document.getElementById('modal-close-btn');
    const modalCancelBtn = document.getElementById('modal-cancel-btn');
    const modalSaveBtn = document.getElementById('modal-save-btn');
    const modalOriginalRaw = document.getElementById('modal-original-raw');
    const modalCronUser = document.getElementById('modal-cron-user');
    const modalCronPreset = document.getElementById('modal-cron-preset');
    const modalCronSchedule = document.getElementById('modal-cron-schedule');
    const modalCronCommand = document.getElementById('modal-cron-command');
    const modalCronEnabled = document.getElementById('modal-cron-enabled');
    const previewText = document.getElementById('preview-text');

    // Tester Elements
    const testerUser = document.getElementById('tester-user');
    const testerCommand = document.getElementById('tester-command');
    const btnRunTest = document.getElementById('btn-run-test');
    const btnClearTest = document.getElementById('btn-clear-test');
    const testStatusBadge = document.getElementById('test-status-badge');
    const testDuration = document.getElementById('test-duration');
    const testOutputBox = document.getElementById('test-output-box');
    const btnCopyOutput = document.getElementById('btn-copy-output');

    // Tab Switching
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

            if (targetTab === 'tab-timers' && systemdTimers.length === 0) {
                fetchTimers();
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

    // Helper: Translate Cron Expression into Human Description
    function humanizeCron(expr) {
        const s = (expr || '').trim();
        if (!s) return 'Ekspresi kosong';
        if (s === '@reboot') return 'Saat sistem booting (Startup)';
        if (s === '@daily' || s === '@midnight' || s === '0 0 * * *') return 'Setiap hari pada pukul 00:00';
        if (s === '@hourly' || s === '0 * * * *') return 'Setiap jam (pada menit ke-00)';
        if (s === '* * * * *') return 'Setiap menit';
        if (s === '*/5 * * * *') return 'Setiap 5 menit';
        if (s === '*/10 * * * *') return 'Setiap 10 menit';
        if (s === '*/15 * * * *') return 'Setiap 15 menit';
        if (s === '*/30 * * * *') return 'Setiap 30 menit';

        const parts = s.split(/\s+/);
        if (parts.length === 5) {
            const [m, h, dom, mon, dow] = parts;
            let timeStr = '';
            if (/^\d+$/.test(m) && /^\d+$/.test(h)) {
                timeStr = `pada ${h.padStart(2, '0')}:${m.padStart(2, '0')}`;
            } else if (/^\d+$/.test(m) && h === '*') {
                timeStr = `pada menit ke-${m} setiap jam`;
            } else if (m.startsWith('*/')) {
                timeStr = `setiap ${m.substring(2)} menit`;
            }

            let daysStr = '';
            if (dom === '*' && dow === '*') {
                daysStr = 'Setiap hari';
            } else if (dow !== '*') {
                const dowMap = {'0': 'Minggu', '1': 'Senin', '2': 'Selasa', '3': 'Rabu', '4': 'Kamis', '5': 'Jumat', '6': 'Sabtu', '7': 'Minggu'};
                daysStr = `Setiap ${dowMap[dow] || 'hari ke-' + dow}`;
            } else if (dom !== '*') {
                daysStr = `Tanggal ${dom} setiap bulan`;
            }

            if (timeStr && daysStr) return `${daysStr} ${timeStr}`;
            if (timeStr) return timeStr;
            if (daysStr) return daysStr;
        }
        return s;
    }

    // Fetch Summary & Statistics
    async function fetchSummary() {
        try {
            const res = await fetch('/api/cron/summary');
            const data = await res.json();
            if (!data.success) return;

            statTotalJobs.textContent = data.total_cron_jobs || 0;
            statActiveJobs.textContent = `${data.active_cron_jobs || 0} aktif, ${data.disabled_cron_jobs || 0} dinonaktifkan`;
            statTotalTimers.textContent = data.total_timers || 0;
            statActiveTimers.textContent = `${data.active_timers || 0} timer aktif`;

            if (data.next_timer) {
                statNextUnit.textContent = data.next_timer.unit || '-';
                if (data.next_timer.timestamp) {
                    const dt = new Date(data.next_timer.timestamp * 1000);
                    statNextTime.textContent = dt.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }) + ' (' + dt.toLocaleDateString('id-ID') + ')';
                }
            } else {
                statNextUnit.textContent = 'Tidak Ada';
                statNextTime.textContent = 'Tidak ada timer berikutnya';
            }

            if (data.users && Array.isArray(data.users)) {
                systemUsers = data.users;
                statUsersCount.textContent = `${systemUsers.length} pengguna terdeteksi`;
                populateUserDropdowns();
            }
        } catch (err) {
            console.error('Error fetching summary:', err);
        }
    }

    function populateUserDropdowns() {
        const currentUserFilter = cronFilterUser.value;
        cronFilterUser.innerHTML = '<option value="all">Semua Pengguna</option>';
        modalCronUser.innerHTML = '';
        testerUser.innerHTML = '';

        systemUsers.forEach(u => {
            const opt1 = document.createElement('option');
            opt1.value = u;
            opt1.textContent = u;
            cronFilterUser.appendChild(opt1);

            const opt2 = document.createElement('option');
            opt2.value = u;
            opt2.textContent = u;
            modalCronUser.appendChild(opt2);

            const opt3 = document.createElement('option');
            opt3.value = u;
            opt3.textContent = u;
            testerUser.appendChild(opt3);
        });

        if (currentUserFilter && systemUsers.includes(currentUserFilter)) {
            cronFilterUser.value = currentUserFilter;
        }
    }

    // Fetch Crontab Jobs
    async function fetchCronJobs() {
        cronTableBody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state">
                    <i class="fa-solid fa-spinner fa-spin"></i>
                    <p>Memuat daftar tugas terjadwal...</p>
                </td>
            </tr>
        `;

        try {
            const res = await fetch('/api/cron/list');
            const data = await res.json();
            if (data.success) {
                cronJobs = data.jobs || [];
                badgeCountCron.textContent = cronJobs.length;
                renderCronTable();
            } else {
                cronTableBody.innerHTML = `
                    <tr>
                        <td colspan="6" class="empty-state" style="color: #ef4444;">
                            <i class="fa-solid fa-triangle-exclamation"></i>
                            <p>Gagal memuat crontab: ${escapeHtml(data.error || 'Terjadi kesalahan')}</p>
                        </td>
                    </tr>
                `;
            }
        } catch (err) {
            console.error('Error fetching cron jobs:', err);
            cronTableBody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-state" style="color: #ef4444;">
                        <i class="fa-solid fa-triangle-exclamation"></i>
                        <p>Koneksi ke backend terputus.</p>
                    </td>
                </tr>
            `;
        }
    }

    function renderCronTable() {
        const query = cronSearch.value.trim().toLowerCase();
        const selectedUser = cronFilterUser.value;
        const selectedStatus = cronFilterStatus.value;

        const filtered = cronJobs.filter(job => {
            if (selectedUser !== 'all' && job.user !== selectedUser) return false;
            if (selectedStatus === 'active' && !job.enabled) return false;
            if (selectedStatus === 'disabled' && job.enabled) return false;

            if (query) {
                const matchCmd = (job.command || '').toLowerCase().includes(query);
                const matchSched = (job.schedule || '').toLowerCase().includes(query);
                const matchUser = (job.user || '').toLowerCase().includes(query);
                const matchDesc = (job.schedule_human || '').toLowerCase().includes(query);
                if (!matchCmd && !matchSched && !matchUser && !matchDesc) return false;
            }
            return true;
        });

        if (filtered.length === 0) {
            cronTableBody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-state">
                        <i class="fa-regular fa-clock"></i>
                        <p>Tidak ada tugas cron yang cocok dengan filter.</p>
                    </td>
                </tr>
            `;
            return;
        }

        cronTableBody.innerHTML = filtered.map(job => {
            const isSystem = job.source === 'system';
            return `
                <tr data-id="${job.id}">
                    <td>
                        <label class="switch">
                            <input type="checkbox" class="cron-toggle-check" data-user="${escapeHtml(job.user)}" data-raw="${escapeHtml(job.raw)}" ${job.enabled ? 'checked' : ''} ${isSystem ? 'disabled title="Jadwal sistem hanya dapat disunting di /etc/crontab"' : ''}>
                            <span class="slider"></span>
                        </label>
                    </td>
                    <td>
                        <span class="badge ${isSystem ? 'badge-system' : 'badge-user'}">
                            <i class="${isSystem ? 'fa-solid fa-server' : 'fa-solid fa-user'}"></i> ${escapeHtml(job.user)}
                        </span>
                    </td>
                    <td>
                        <span class="badge badge-cron">${escapeHtml(job.schedule)}</span>
                    </td>
                    <td>
                        <span style="font-size: 12.5px; color: ${job.enabled ? 'var(--text-main)' : 'var(--text-muted)'};">
                            ${escapeHtml(job.schedule_human)}
                        </span>
                    </td>
                    <td>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span class="cmd-snippet" title="${escapeHtml(job.command)}">${escapeHtml(job.command)}</span>
                            <button class="action-icon-btn btn-copy-cmd" data-cmd="${escapeHtml(job.command)}" title="Salin Perintah">
                                <i class="fa-regular fa-copy"></i>
                            </button>
                        </div>
                    </td>
                    <td style="text-align: right;">
                        <div class="row-actions" style="justify-content: flex-end;">
                            <button class="action-icon-btn test btn-test-job" data-user="${escapeHtml(job.user)}" data-cmd="${escapeHtml(job.command)}" title="Uji Coba Script (Dry-Run)">
                                <i class="fa-solid fa-play"></i>
                            </button>
                            ${!isSystem ? `
                                <button class="action-icon-btn btn-edit-job" data-user="${escapeHtml(job.user)}" data-sched="${escapeHtml(job.schedule)}" data-cmd="${escapeHtml(job.command)}" data-enabled="${job.enabled}" data-raw="${escapeHtml(job.raw)}" title="Sunting Jadwal">
                                    <i class="fa-solid fa-pen-to-square"></i>
                                </button>
                                <button class="action-icon-btn delete btn-delete-job" data-user="${escapeHtml(job.user)}" data-raw="${escapeHtml(job.raw)}" title="Hapus Jadwal">
                                    <i class="fa-solid fa-trash"></i>
                                </button>
                            ` : `
                                <span style="font-size: 11px; color: var(--text-muted); font-style: italic;">sistem</span>
                            `}
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        // Attach event listeners for table buttons
        attachTableEvents();
    }

    function attachTableEvents() {
        // Toggle Switch
        cronTableBody.querySelectorAll('.cron-toggle-check').forEach(chk => {
            chk.addEventListener('change', async (e) => {
                const user = chk.getAttribute('data-user');
                const raw = chk.getAttribute('data-raw');
                try {
                    const res = await fetch('/api/cron/toggle', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user, raw })
                    });
                    const d = await res.json();
                    if (!d.success) {
                        alert(d.error || 'Gagal mengubah status cron job');
                        chk.checked = !chk.checked;
                    } else {
                        fetchSummary();
                        fetchCronJobs();
                    }
                } catch (err) {
                    alert('Koneksi terputus');
                    chk.checked = !chk.checked;
                }
            });
        });

        // Copy Command
        cronTableBody.querySelectorAll('.btn-copy-cmd').forEach(btn => {
            btn.addEventListener('click', () => {
                const cmd = btn.getAttribute('data-cmd');
                navigator.clipboard.writeText(cmd).then(() => {
                    const icon = btn.querySelector('i');
                    icon.className = 'fa-solid fa-check';
                    setTimeout(() => icon.className = 'fa-regular fa-copy', 1500);
                });
            });
        });

        // Test Job -> Switch to Tester Tab
        cronTableBody.querySelectorAll('.btn-test-job').forEach(btn => {
            btn.addEventListener('click', () => {
                const user = btn.getAttribute('data-user');
                const cmd = btn.getAttribute('data-cmd');

                testerCommand.value = cmd;
                if (systemUsers.includes(user)) {
                    testerUser.value = user;
                }

                // Switch Tab to tab-test
                const tabTestBtn = document.querySelector('[data-tab="tab-test"]');
                if (tabTestBtn) tabTestBtn.click();
            });
        });

        // Edit Job
        cronTableBody.querySelectorAll('.btn-edit-job').forEach(btn => {
            btn.addEventListener('click', () => {
                const user = btn.getAttribute('data-user');
                const sched = btn.getAttribute('data-sched');
                const cmd = btn.getAttribute('data-cmd');
                const enabled = btn.getAttribute('data-enabled') === 'true';
                const raw = btn.getAttribute('data-raw');

                openModal({
                    isEdit: true,
                    user,
                    schedule: sched,
                    command: cmd,
                    enabled,
                    originalRaw: raw
                });
            });
        });

        // Delete Job
        cronTableBody.querySelectorAll('.btn-delete-job').forEach(btn => {
            btn.addEventListener('click', async () => {
                const user = btn.getAttribute('data-user');
                const raw = btn.getAttribute('data-raw');

                if (!confirm(`Hapus jadwal cron ini dari pengguna ${user}?`)) return;

                try {
                    const res = await fetch('/api/cron/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user, raw })
                    });
                    const d = await res.json();
                    if (d.success) {
                        fetchSummary();
                        fetchCronJobs();
                    } else {
                        alert(d.error || 'Gagal menghapus jadwal');
                    }
                } catch (err) {
                    alert('Gagal menghapus jadwal cron');
                }
            });
        });
    }

    // Fetch Systemd Timers
    async function fetchTimers() {
        timersTableBody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state">
                    <i class="fa-solid fa-spinner fa-spin"></i>
                    <p>Memuat daftar systemd timers host...</p>
                </td>
            </tr>
        `;

        try {
            const query = encodeURIComponent(timersSearch.value.trim());
            const res = await fetch(`/api/cron/timers?search=${query}`);
            const data = await res.json();
            if (data.success) {
                systemdTimers = data.timers || [];
                badgeCountTimers.textContent = systemdTimers.length;
                renderTimersTable();
            } else {
                timersTableBody.innerHTML = `
                    <tr>
                        <td colspan="5" class="empty-state" style="color: #ef4444;">
                            <i class="fa-solid fa-triangle-exclamation"></i>
                            <p>Gagal memuat timers: ${escapeHtml(data.error || 'Terjadi kesalahan')}</p>
                        </td>
                    </tr>
                `;
            }
        } catch (err) {
            console.error('Error fetching timers:', err);
        }
    }

    function renderTimersTable() {
        const query = timersSearch.value.trim().toLowerCase();
        const selectedStatus = timersFilterStatus.value;

        const filtered = systemdTimers.filter(t => {
            if (selectedStatus === 'active' && t.status !== 'active') return false;
            if (selectedStatus === 'waiting' && t.status !== 'waiting') return false;
            if (selectedStatus === 'inactive' && t.status !== 'inactive') return false;

            if (query) {
                const mUnit = (t.unit || '').toLowerCase().includes(query);
                const mAct = (t.activates || '').toLowerCase().includes(query);
                if (!mUnit && !mAct) return false;
            }
            return true;
        });

        if (filtered.length === 0) {
            timersTableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="empty-state">
                        <i class="fa-solid fa-stopwatch"></i>
                        <p>Tidak ada timer yang sesuai.</p>
                    </td>
                </tr>
            `;
            return;
        }

        timersTableBody.innerHTML = filtered.map(t => {
            let statusBadge = '<span class="badge badge-active"><i class="fa-solid fa-circle-check"></i> Aktif</span>';
            if (t.status === 'waiting') {
                statusBadge = '<span class="badge badge-waiting"><i class="fa-solid fa-clock"></i> Menunggu</span>';
            } else if (t.status === 'inactive') {
                statusBadge = '<span class="badge badge-disabled"><i class="fa-solid fa-circle-pause"></i> Nonaktif</span>';
            }

            return `
                <tr>
                    <td>${statusBadge}</td>
                    <td>
                        <span style="font-weight: 600; font-family: 'JetBrains Mono', monospace; font-size: 13px; color: #38ef7d;">
                            ${escapeHtml(t.unit)}
                        </span>
                    </td>
                    <td>
                        <span class="badge badge-user" style="font-family: 'JetBrains Mono', monospace;">
                            <i class="fa-solid fa-gears"></i> ${escapeHtml(t.activates)}
                        </span>
                    </td>
                    <td>
                        <div>
                            <span style="font-weight: 600; color: #6ee7b7;">${escapeHtml(t.next_countdown)}</span>
                            <div style="font-size: 11.5px; color: var(--text-muted);">${escapeHtml(t.next_time)}</div>
                        </div>
                    </td>
                    <td>
                        <div>
                            <span>${escapeHtml(t.last_elapsed)}</span>
                            <div style="font-size: 11.5px; color: var(--text-muted);">${escapeHtml(t.last_time)}</div>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    // Modal Add / Edit Functions
    function openModal({ isEdit, user, schedule, command, enabled, originalRaw }) {
        modalTitle.innerHTML = isEdit
            ? '<i class="fa-solid fa-pen-to-square" style="color: #38ef7d;"></i> Sunting Jadwal Cron'
            : '<i class="fa-solid fa-calendar-plus" style="color: #38ef7d;"></i> Tambah Cron Job Baru';

        modalOriginalRaw.value = isEdit ? (originalRaw || '') : '';
        if (user && systemUsers.includes(user)) {
            modalCronUser.value = user;
        } else if (systemUsers.length > 0) {
            modalCronUser.value = systemUsers[0];
        }

        modalCronSchedule.value = schedule || '* * * * *';
        modalCronCommand.value = command || '';
        modalCronEnabled.checked = enabled !== undefined ? enabled : true;

        updateModalPreview();
        modalCron.classList.add('active');
    }

    function closeModal() {
        modalCron.classList.remove('active');
        modalOriginalRaw.value = '';
        modalCronCommand.value = '';
    }

    function updateModalPreview() {
        const sched = modalCronSchedule.value.trim();
        previewText.textContent = humanizeCron(sched);
    }

    modalCronPreset.addEventListener('change', () => {
        const val = modalCronPreset.value;
        if (val !== 'custom') {
            modalCronSchedule.value = val;
            updateModalPreview();
        }
    });

    modalCronSchedule.addEventListener('input', () => {
        updateModalPreview();
    });

    btnAddCron.addEventListener('click', () => {
        openModal({
            isEdit: false,
            user: systemUsers[0] || 'root',
            schedule: '*/15 * * * *',
            command: '',
            enabled: true
        });
    });

    modalCloseBtn.addEventListener('click', closeModal);
    modalCancelBtn.addEventListener('click', closeModal);
    modalCron.addEventListener('click', (e) => {
        if (e.target === modalCron) closeModal();
    });

    modalSaveBtn.addEventListener('click', async () => {
        const user = modalCronUser.value;
        const schedule = modalCronSchedule.value.trim();
        const command = modalCronCommand.value.trim();
        const enabled = modalCronEnabled.checked;
        const originalRaw = modalOriginalRaw.value;

        if (!schedule) {
            alert('Format schedule cron tidak boleh kosong');
            return;
        }
        if (!command) {
            alert('Perintah bash / skrip tidak boleh kosong');
            return;
        }

        modalSaveBtn.disabled = true;
        modalSaveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Menyimpan...';

        try {
            const res = await fetch('/api/cron/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user,
                    schedule,
                    command,
                    enabled,
                    original_raw: originalRaw
                })
            });
            const data = await res.json();
            if (data.success) {
                closeModal();
                fetchSummary();
                fetchCronJobs();
            } else {
                alert(data.error || 'Gagal menyimpan jadwal cron');
            }
        } catch (err) {
            alert('Gagal menghubungi server');
        } finally {
            modalSaveBtn.disabled = false;
            modalSaveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Simpan Jadwal';
        }
    });

    // Dry-Run Tester Execution
    btnRunTest.addEventListener('click', async () => {
        const command = testerCommand.value.trim();
        const user = testerUser.value;

        if (!command) {
            alert('Masukkan perintah yang ingin diuji coba');
            return;
        }

        btnRunTest.disabled = true;
        btnRunTest.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Mengeksekusi...';
        testStatusBadge.style.display = 'inline-flex';
        testStatusBadge.className = 'badge badge-waiting';
        testStatusBadge.textContent = 'Menjalankan...';
        testOutputBox.textContent = `[EKA DASHBOARD DRY-RUN TESTER]\n> Target Pengguna : ${user}\n> Perintah        : ${command}\n> Waktu Mulai    : ${new Date().toLocaleTimeString()}\n\nMenunggu output kernel host...`;

        try {
            const res = await fetch('/api/cron/test_run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command, user })
            });
            const data = await res.json();

            if (data.success) {
                const passed = data.passed;
                testStatusBadge.className = passed ? 'badge badge-active' : 'badge badge-disabled';
                testStatusBadge.textContent = passed ? 'Exit Code: 0 (Sukses)' : `Exit Code: ${data.returncode} (Error)`;
                testDuration.textContent = `${data.duration_ms} ms`;

                let out = `[HASIL EKSEKUSI DRY-RUN]\nStatus: ${passed ? 'BERHASIL' : 'GAGAL'} (Exit Code: ${data.returncode}) | Durasi: ${data.duration_ms} ms\n\n`;
                if (data.stdout) {
                    out += `--- STDOUT ---\n${data.stdout}\n`;
                }
                if (data.stderr) {
                    out += `--- STDERR ---\n${data.stderr}\n`;
                }
                if (!data.stdout && !data.stderr) {
                    out += `(Perintah selesai tanpa mengeluarkan output)`;
                }
                testOutputBox.textContent = out;
            } else {
                testStatusBadge.className = 'badge badge-disabled';
                testStatusBadge.textContent = 'Gagal';
                testOutputBox.textContent = `Error: ${data.error || 'Gagal mengeksekusi perintah'}`;
            }
        } catch (err) {
            testStatusBadge.className = 'badge badge-disabled';
            testStatusBadge.textContent = 'Error';
            testOutputBox.textContent = 'Koneksi ke backend server gagal.';
        } finally {
            btnRunTest.disabled = false;
            btnRunTest.innerHTML = '<i class="fa-solid fa-play"></i> Eksekusi Dry-Run';
        }
    });

    btnClearTest.addEventListener('click', () => {
        testerCommand.value = '';
        testOutputBox.textContent = 'Siap menguji perintah. Ketikkan perintah di sebelah kiri lalu klik "Eksekusi Dry-Run".';
        testStatusBadge.style.display = 'none';
        testDuration.textContent = '';
    });

    btnCopyOutput.addEventListener('click', () => {
        navigator.clipboard.writeText(testOutputBox.textContent).then(() => {
            const icon = btnCopyOutput.querySelector('i');
            icon.className = 'fa-solid fa-check';
            setTimeout(() => icon.className = 'fa-regular fa-copy', 1500);
        });
    });

    // Search and filter listeners
    cronSearch.addEventListener('input', renderCronTable);
    cronFilterUser.addEventListener('change', renderCronTable);
    cronFilterStatus.addEventListener('change', renderCronTable);

    timersSearch.addEventListener('input', renderTimersTable);
    timersFilterStatus.addEventListener('change', renderTimersTable);

    btnRefresh.addEventListener('click', () => {
        fetchSummary();
        fetchCronJobs();
        fetchTimers();
    });

    // Initial Load
    fetchSummary();
    fetchCronJobs();
});

