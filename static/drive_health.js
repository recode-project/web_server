/**
 * Drive Health & S.M.A.R.T. Inspector
 * Eka Dashboard - Modular Frontend Logic
 * Zero Inline JS
 */

document.addEventListener('DOMContentLoaded', () => {
    let drivesData = [];
    let raidData = null;

    // DOM Elements - Stat Cards
    const statTotalDrives = document.getElementById('stat-total-drives');
    const statDrivesBreakdown = document.getElementById('stat-drives-breakdown');
    const statHealthStatus = document.getElementById('stat-health-status');
    const statHealthSub = document.getElementById('stat-health-sub');
    const statPeakTemp = document.getElementById('stat-peak-temp');
    const statRaidVal = document.getElementById('stat-raid-val');
    const badgeDrivesCount = document.getElementById('badge-drives-count');

    // DOM Elements - Containers
    const drivesContainer = document.getElementById('drives-container');
    const selftestDriveSelect = document.getElementById('selftest-drive-select');
    const selftestTypeSelect = document.getElementById('selftest-type-select');
    const btnStartSelftest = document.getElementById('btn-start-selftest');
    const btnAbortSelftest = document.getElementById('btn-abort-selftest');
    const selftestOutputBox = document.getElementById('selftest-output-box');

    const raidStatusBadge = document.getElementById('raid-status-badge');
    const raidContentBox = document.getElementById('raid-content-box');

    const btnRefresh = document.getElementById('btn-refresh');

    // Modal Elements
    const modalSmartDetail = document.getElementById('modal-smart-detail');
    const modalDriveTitle = document.getElementById('modal-drive-title');
    const modalDetailBody = document.getElementById('modal-detail-body');
    const modalDetailClose = document.getElementById('modal-detail-close');

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

            if (targetTab === 'tab-raid') {
                fetchRaidStatus();
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

    // Fetch Summary & Drives
    async function fetchSummary() {
        try {
            const res = await fetch('/api/smart/summary');
            const data = await res.json();
            if (!data.success) return;

            drivesData = data.drives || [];
            badgeDrivesCount.textContent = drivesData.length;
            statTotalDrives.textContent = drivesData.length;

            let nvmeCount = 0;
            let sataCount = 0;
            drivesData.forEach(d => {
                if (d.is_nvme) nvmeCount++;
                else sataCount++;
            });
            statDrivesBreakdown.textContent = `${nvmeCount} NVMe SSD, ${sataCount} SATA Drive`;

            if (data.warning_count > 0) {
                statHealthStatus.textContent = 'PERHATIAN';
                statHealthStatus.style.color = '#ff6b6b';
                statHealthSub.textContent = `${data.healthy_count} Sehat, ${data.warning_count} Warning`;
            } else {
                statHealthStatus.textContent = 'SEHAT (PASSED)';
                statHealthStatus.style.color = '#4ecdc4';
                statHealthSub.textContent = `Seluruh ${drivesData.length} drive dalam kondisi baik`;
            }

            if (data.max_temperature) {
                statPeakTemp.textContent = `${data.max_temperature} °C`;
            } else {
                statPeakTemp.textContent = 'Normal';
            }

            // RAID / ZFS quick stat
            if (data.raid) {
                raidData = data.raid;
                if (data.raid.raid_active) {
                    statRaidVal.textContent = 'RAID Aktif';
                    statRaidVal.style.color = '#38ef7d';
                } else if (data.raid.zfs_active) {
                    statRaidVal.textContent = 'ZFS Pool Aktif';
                    statRaidVal.style.color = '#38ef7d';
                } else {
                    statRaidVal.textContent = 'Standalone';
                    statRaidVal.style.color = '#94a3b8';
                }
            }

            renderDriveCards();
            populateSelftestDrives();
        } catch (err) {
            console.error('Error fetching SMART summary:', err);
        }
    }

    function populateSelftestDrives() {
        const currentSel = selftestDriveSelect.value;
        selftestDriveSelect.innerHTML = '';

        if (drivesData.length === 0) {
            selftestDriveSelect.innerHTML = '<option value="">Tidak ada drive terdeteksi</option>';
            return;
        }

        drivesData.forEach(d => {
            const opt = document.createElement('option');
            opt.value = d.name;
            opt.textContent = `${d.name} — ${d.model} (${d.capacity_gb}, ${d.protocol})`;
            selftestDriveSelect.appendChild(opt);
        });

        if (currentSel) selftestDriveSelect.value = currentSel;
    }

    // Render Drive Cards
    function renderDriveCards() {
        if (drivesData.length === 0) {
            drivesContainer.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1;">
                    <i class="fa-solid fa-hard-drive"></i>
                    <p>Tidak ada drive fisik yang terdeteksi pada host.</p>
                </div>
            `;
            return;
        }

        drivesContainer.innerHTML = drivesData.map(d => {
            const isNvme = d.is_nvme;
            const healthBadge = d.healthy
                ? '<span class="badge badge-passed"><i class="fa-solid fa-circle-check"></i> PASSED</span>'
                : '<span class="badge badge-warning"><i class="fa-solid fa-triangle-exclamation"></i> WARNING</span>';

            const temp = d.temperature;
            let tempColor = '#4ecdc4';
            if (temp && temp >= 60) tempColor = '#ff6b6b';
            else if (temp && temp >= 48) tempColor = '#ffe66d';

            // NVMe Specific metrics
            let nvmeBlock = '';
            if (isNvme && d.nvme_stats) {
                const used = d.nvme_stats.percentage_used || 0;
                let usedFillClass = 'fill-green';
                if (used >= 80) usedFillClass = 'fill-red';
                else if (used >= 50) usedFillClass = 'fill-yellow';

                nvmeBlock = `
                    <div class="progress-bar-wrap">
                        <div class="progress-bar-label">
                            <span>Tingkat Keausan SSD (Wear Level / Percentage Used)</span>
                            <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: ${used >= 80 ? '#ff6b6b' : '#38ef7d'};">${used}%</span>
                        </div>
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill ${usedFillClass}" style="width: ${Math.min(used, 100)}%;"></div>
                        </div>
                    </div>

                    <div class="telemetry-row">
                        <div class="telemetry-item">
                            <span class="telemetry-label">Total Terbaca (TBR)</span>
                            <span class="telemetry-val">${d.nvme_stats.tbr} TB</span>
                        </div>
                        <div class="telemetry-item">
                            <span class="telemetry-label">Total Tertulis (TBW)</span>
                            <span class="telemetry-val">${d.nvme_stats.tbw} TB</span>
                        </div>
                        <div class="telemetry-item">
                            <span class="telemetry-label">Cadangan Spare</span>
                            <span class="telemetry-val" style="color: #4ecdc4;">${d.nvme_stats.available_spare}%</span>
                        </div>
                        <div class="telemetry-item">
                            <span class="telemetry-label">Media Errors</span>
                            <span class="telemetry-val" style="color: ${d.nvme_stats.media_errors > 0 ? '#ff6b6b' : 'var(--text-main)'};">${d.nvme_stats.media_errors}</span>
                        </div>
                    </div>
                `;
            }

            // SATA Specific metrics
            let sataBlock = '';
            if (!isNvme) {
                const pending = d.pending_sectors || 0;
                const reallocated = d.reallocated_sectors || 0;

                sataBlock = `
                    <div class="telemetry-row">
                        <div class="telemetry-item">
                            <span class="telemetry-label">Pending Sectors</span>
                            <span class="telemetry-val" style="color: ${pending > 0 ? '#ff6b6b' : '#4ecdc4'}; font-size: 15px;">
                                ${pending > 0 ? `<i class="fa-solid fa-triangle-exclamation"></i> ${pending}` : '0 (Bersih)'}
                            </span>
                        </div>
                        <div class="telemetry-item">
                            <span class="telemetry-label">Reallocated Sectors</span>
                            <span class="telemetry-val" style="color: ${reallocated > 0 ? '#ff6b6b' : '#4ecdc4'}; font-size: 15px;">
                                ${reallocated}
                            </span>
                        </div>
                        <div class="telemetry-item">
                            <span class="telemetry-label">Jam Operasi (POH)</span>
                            <span class="telemetry-val">${d.power_on_hours.toLocaleString()} jam</span>
                        </div>
                        <div class="telemetry-item">
                            <span class="telemetry-label">Status Self-Test</span>
                            <span class="telemetry-val" style="font-size: 11.5px; color: var(--text-muted);">${escapeHtml(d.selftest_status)}</span>
                        </div>
                    </div>
                `;
            }

            return `
                <div class="drive-card">
                    <div class="drive-header">
                        <div class="drive-main-info">
                            <div class="drive-avatar ${isNvme ? 'nvme' : ''}">
                                <i class="${isNvme ? 'fa-solid fa-microchip' : 'fa-solid fa-compact-disc'}"></i>
                            </div>
                            <div>
                                <div class="drive-name">${escapeHtml(d.name)} &bull; ${escapeHtml(d.capacity_gb)}</div>
                                <div class="drive-model">${escapeHtml(d.model)}</div>
                            </div>
                        </div>
                        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 6px;">
                            ${healthBadge}
                            <span class="badge badge-protocol">${escapeHtml(d.protocol)}</span>
                        </div>
                    </div>

                    <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.25); padding: 10px 14px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05);">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <i class="fa-solid fa-temperature-half" style="color: ${tempColor};"></i>
                            <span style="font-size: 13px; font-weight: 600;">Suhu Drive:</span>
                            <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: ${tempColor};">${temp ? temp + ' °C' : 'N/A'}</span>
                        </div>
                        <div style="font-size: 12px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace;">
                            SN: ${escapeHtml(d.serial)}
                        </div>
                    </div>

                    ${isNvme ? nvmeBlock : sataBlock}

                    <div class="drive-footer">
                        <span style="font-size: 12px; color: var(--text-muted);">
                            <i class="fa-solid fa-clock-rotate-left"></i> POH: ${d.power_on_hours.toLocaleString()} jam
                        </span>
                        <div style="display: flex; gap: 8px;">
                            <button class="btn btn-quick-test" data-drive="${escapeHtml(d.name)}" title="Jalankan Diagnostik">
                                <i class="fa-solid fa-stethoscope"></i> Uji Drive
                            </button>
                            <button class="btn btn-primary btn-inspect-smart" data-drive="${escapeHtml(d.name)}" title="Buka Seluruh Atribut S.M.A.R.T.">
                                <i class="fa-solid fa-eye"></i> Inspeksi Detail
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        attachDriveCardEvents();
    }

    function attachDriveCardEvents() {
        // Quick Test -> Switch to Tab 2
        drivesContainer.querySelectorAll('.btn-quick-test').forEach(btn => {
            btn.addEventListener('click', () => {
                const drive = btn.getAttribute('data-drive');
                selftestDriveSelect.value = drive;

                const tabTestBtn = document.querySelector('[data-tab="tab-selftest"]');
                if (tabTestBtn) tabTestBtn.click();
            });
        });

        // Inspect Detail -> Open Modal
        drivesContainer.querySelectorAll('.btn-inspect-smart').forEach(btn => {
            btn.addEventListener('click', () => {
                const drive = btn.getAttribute('data-drive');
                openSmartDetailModal(drive);
            });
        });
    }

    // Modal: SMART Detail
    async function openSmartDetailModal(diskName) {
        modalDriveTitle.textContent = `Inspeksi Detail S.M.A.R.T. — /dev/${diskName}`;
        modalDetailBody.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-spinner fa-spin"></i>
                <p>Membaca telemetri low-level dari kontroler disk...</p>
            </div>
        `;
        modalSmartDetail.classList.add('active');

        try {
            const res = await fetch(`/api/smart/detail/${encodeURIComponent(diskName)}`);
            const data = await res.json();
            if (!data.success || !data.drive) {
                modalDetailBody.innerHTML = `<div class="empty-state" style="color: #ff6b6b;"><p>Gagal membaca detail disk.</p></div>`;
                return;
            }

            const d = data.drive;
            let contentHtml = `
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; background: rgba(0,0,0,0.3); padding: 14px; border-radius: 12px; border: 1px solid var(--glass-border);">
                    <div><span style="font-size: 11px; color: var(--text-muted);">MODEL:</span><div style="font-weight: 600;">${escapeHtml(d.model)}</div></div>
                    <div><span style="font-size: 11px; color: var(--text-muted);">SERIAL NUMBER:</span><div style="font-family: 'JetBrains Mono', monospace;">${escapeHtml(d.serial)}</div></div>
                    <div><span style="font-size: 11px; color: var(--text-muted);">FIRMWARE:</span><div style="font-family: 'JetBrains Mono', monospace;">${escapeHtml(d.firmware)}</div></div>
                    <div><span style="font-size: 11px; color: var(--text-muted);">KAPASITAS:</span><div>${escapeHtml(d.capacity_gb)}</div></div>
                </div>
            `;

            if (d.is_nvme && d.nvme_stats) {
                contentHtml += `
                    <h3 style="font-size: 14px; font-weight: 700; margin-top: 8px;">NVMe Health Information Log</h3>
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th>Parameter Telemetri</th>
                                    <th>Nilai</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr><td>Critical Warning Flags</td><td>${d.nvme_stats.critical_warning}</td></tr>
                                <tr><td>Percentage Used (Keausan)</td><td><strong>${d.nvme_stats.percentage_used}%</strong></td></tr>
                                <tr><td>Available Spare</td><td>${d.nvme_stats.available_spare}% (Batas Ambang: ${d.nvme_stats.available_spare_threshold}%)</td></tr>
                                <tr><td>Total Bytes Written (TBW)</td><td>${d.nvme_stats.tbw} TB</td></tr>
                                <tr><td>Total Bytes Read (TBR)</td><td>${d.nvme_stats.tbr} TB</td></tr>
                                <tr><td>Unsafe Shutdowns</td><td>${d.nvme_stats.unsafe_shutdowns}</td></tr>
                                <tr><td>Media & Data Integrity Errors</td><td><strong>${d.nvme_stats.media_errors}</strong></td></tr>
                                <tr><td>Number of Error Info Log Entries</td><td>${d.nvme_stats.num_err_log_entries}</td></tr>
                            </tbody>
                        </table>
                    </div>
                `;
            } else if (d.ata_attributes && d.ata_attributes.length > 0) {
                contentHtml += `
                    <h3 style="font-size: 14px; font-weight: 700; margin-top: 8px;">Atribut ATA S.M.A.R.T.</h3>
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th style="width: 50px;">ID</th>
                                    <th>Nama Atribut</th>
                                    <th>Nilai Saat Ini</th>
                                    <th>Terburuk</th>
                                    <th>Threshold</th>
                                    <th>Nilai Raw</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${d.ata_attributes.map(attr => {
                                    const isCritical = ['Reallocated_Sector_Ct', 'Current_Pending_Sector', 'Offline_Uncorrectable'].includes(attr.name);
                                    const hasError = isCritical && parseInt(attr.raw) > 0;
                                    return `
                                        <tr style="${hasError ? 'background: rgba(255, 107, 107, 0.15);' : ''}">
                                            <td style="font-family: 'JetBrains Mono', monospace;">${attr.id}</td>
                                            <td><strong>${escapeHtml(attr.name)}</strong></td>
                                            <td style="font-family: 'JetBrains Mono', monospace;">${attr.value}</td>
                                            <td style="font-family: 'JetBrains Mono', monospace;">${attr.worst}</td>
                                            <td style="font-family: 'JetBrains Mono', monospace;">${attr.thresh}</td>
                                            <td style="font-family: 'JetBrains Mono', monospace; font-weight: 600; color: ${hasError ? '#ff6b6b' : '#38ef7d'};">${escapeHtml(attr.raw)}</td>
                                            <td><span class="badge ${hasError ? 'badge-warning' : 'badge-passed'}">${hasError ? 'FAIL / WARN' : 'OK'}</span></td>
                                        </tr>
                                    `;
                                }).join('')}
                            </tbody>
                        </table>
                    </div>
                `;
            }

            modalDetailBody.innerHTML = contentHtml;
        } catch (err) {
            modalDetailBody.innerHTML = `<div class="empty-state" style="color: #ff6b6b;"><p>Koneksi gagal saat membaca detail.</p></div>`;
        }
    }

    modalDetailClose.addEventListener('click', () => {
        modalSmartDetail.classList.remove('active');
    });

    modalSmartDetail.addEventListener('click', (e) => {
        if (e.target === modalSmartDetail) {
            modalSmartDetail.classList.remove('active');
        }
    });

    // Self-Test Execution
    btnStartSelftest.addEventListener('click', async () => {
        const device = selftestDriveSelect.value;
        const type = selftestTypeSelect.value;

        if (!device) {
            alert('Pilih drive sasaran terlebih dahulu');
            return;
        }

        btnStartSelftest.disabled = true;
        btnStartSelftest.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Memulai...';
        selftestOutputBox.textContent = `[S.M.A.R.T. SELF-TEST RUNNER]\n> Target Device : /dev/${device}\n> Tipe Uji      : ${type.toUpperCase()}\n> Waktu Mulai   : ${new Date().toLocaleTimeString()}\n\nMengirim perintah self-test ke kernel host...`;

        try {
            const res = await fetch('/api/smart/test/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ device, type })
            });
            const data = await res.json();
            if (data.success) {
                selftestOutputBox.textContent = `[BERHASIL DIMULAI]\n${data.message}\n\nKeluaran kernel:\n${data.output || '(Perintah diterima oleh kontroler disk)'}`;
                fetchSummary();
            } else {
                selftestOutputBox.textContent = `[GAGAL]: ${data.error || 'Kontroler menolak pengujian'}`;
            }
        } catch (err) {
            selftestOutputBox.textContent = `[ERROR]: Koneksi backend gagal.`;
        } finally {
            btnStartSelftest.disabled = false;
            btnStartSelftest.innerHTML = '<i class="fa-solid fa-play"></i> Mulai Self-Test';
        }
    });

    btnAbortSelftest.addEventListener('click', async () => {
        const device = selftestDriveSelect.value;
        if (!device) return;

        btnAbortSelftest.disabled = true;
        try {
            const res = await fetch('/api/smart/test/abort', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ device })
            });
            const data = await res.json();
            if (data.success) {
                selftestOutputBox.textContent = `[PENGUJIAN DIBATALKAN]\n${data.message}`;
                fetchSummary();
            } else {
                alert(data.error || 'Gagal membatalkan pengujian');
            }
        } catch (err) {
            alert('Koneksi terputus');
        } finally {
            btnAbortSelftest.disabled = false;
        }
    });

    // RAID & ZFS Status Fetcher
    async function fetchRaidStatus() {
        try {
            const res = await fetch('/api/smart/raid');
            const data = await res.json();
            if (!data.success || !data.raid) {
                raidContentBox.innerHTML = `<div class="empty-state" style="color: #ff6b6b;"><p>Gagal memuat status RAID / ZFS.</p></div>`;
                return;
            }

            raidData = data.raid;
            const isRaid = raidData.raid_active;
            const isZfs = raidData.zfs_active;

            raidStatusBadge.textContent = isRaid ? 'Software RAID Aktif' : (isZfs ? 'ZFS Active' : 'Standalone Drive');
            raidStatusBadge.className = (isRaid || isZfs) ? 'badge badge-passed' : 'badge badge-protocol';

            let html = '';
            if (isRaid) {
                html += `
                    <h3 style="font-size: 14px; font-weight: 700; margin-bottom: 12px;">Array RAID Linux (mdadm) Terdeteksi:</h3>
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th>Array</th>
                                    <th>Level</th>
                                    <th>Status</th>
                                    <th>Device Anggota</th>
                                    <th>Detail Sinkronisasi</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${raidData.raid_arrays.map(arr => `
                                    <tr>
                                        <td><strong>${escapeHtml(arr.name)}</strong></td>
                                        <td><span class="badge badge-protocol">${escapeHtml(arr.level)}</span></td>
                                        <td><span class="badge ${arr.status === 'active' ? 'badge-passed' : 'badge-warning'}">${escapeHtml(arr.status)}</span></td>
                                        <td style="font-family: 'JetBrains Mono', monospace;">${escapeHtml(arr.devices.join(', '))}</td>
                                        <td style="font-size: 12px; color: var(--text-muted);">${escapeHtml(arr.detail)}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `;
            }

            if (isZfs) {
                html += `
                    <h3 style="font-size: 14px; font-weight: 700; margin-top: 16px; margin-bottom: 12px;">ZFS Storage Pools:</h3>
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th>Pool Name</th>
                                    <th>Size</th>
                                    <th>Allocated</th>
                                    <th>Free</th>
                                    <th>Frag</th>
                                    <th>Cap</th>
                                    <th>Health</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${raidData.zfs_pools.map(p => `
                                    <tr>
                                        <td><strong>${escapeHtml(p.name)}</strong></td>
                                        <td>${escapeHtml(p.size)}</td>
                                        <td>${escapeHtml(p.alloc)}</td>
                                        <td>${escapeHtml(p.free)}</td>
                                        <td>${escapeHtml(p.frag)}</td>
                                        <td>${escapeHtml(p.capacity)}</td>
                                        <td><span class="badge ${p.health === 'ONLINE' ? 'badge-passed' : 'badge-warning'}">${escapeHtml(p.health)}</span></td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `;
            }

            if (!isRaid && !isZfs) {
                html = `
                    <div style="text-align: center; padding: 32px 16px; color: var(--text-muted);">
                        <i class="fa-solid fa-server" style="font-size: 36px; margin-bottom: 12px; opacity: 0.4;"></i>
                        <p style="font-size: 14px; font-weight: 500;">Tidak ada array Software RAID (mdadm) atau ZFS pool yang aktif pada server ini.</p>
                        <p style="font-size: 12px; margin-top: 4px;">Seluruh penyimpanan beroperasi sebagai drive fisik mandiri (Standalone Disks).</p>
                    </div>
                `;
            }

            raidContentBox.innerHTML = html;
        } catch (err) {
            raidContentBox.innerHTML = `<div class="empty-state" style="color: #ff6b6b;"><p>Gagal memuat status RAID / ZFS.</p></div>`;
        }
    }

    btnRefresh.addEventListener('click', () => {
        fetchSummary();
        fetchRaidStatus();
    });

    // Initial Load
    fetchSummary();
    fetchRaidStatus();
});

