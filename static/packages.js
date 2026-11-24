/**
 * Package & OS Update Manager (APT / Distro Packages)
 * Eka Dashboard - Modular Frontend Logic
 * Zero Inline JS
 */

document.addEventListener('DOMContentLoaded', () => {
    let allPackages = [];
    let activeFilter = 'all';
    let searchQuery = '';
    let pendingAction = null;
    let detectedPm = 'pkg';

    // DOM Elements - Dynamic Distro/PM Labels
    const pmSubtitle = document.getElementById('pm-subtitle');
    const pmRefreshLabel = document.getElementById('pm-refresh-label');
    const pmAutoUpdateService = document.getElementById('pm-autoupdate-service');
    const pmConsoleTabLabel = document.getElementById('pm-console-tab-label');
    const pmConsoleSub = document.getElementById('pm-console-sub');

    // DOM Elements - Stat Cards
    const statTotalPkgs = document.getElementById('stat-total-pkgs');
    const statPkgsSub = document.getElementById('stat-pkgs-sub');
    const statSecurityPkgs = document.getElementById('stat-security-pkgs');
    const statSecuritySub = document.getElementById('stat-security-sub');
    const statRebootStatus = document.getElementById('stat-reboot-status');
    const statRebootSub = document.getElementById('stat-reboot-sub');
    const statRebootIcon = document.getElementById('stat-reboot-icon');
    const statAutoUpdate = document.getElementById('stat-autoupdate-status');
    const badgePkgCount = document.getElementById('badge-pkg-count');

    // Filter Chips & Search
    const searchInput = document.getElementById('search-packages');
    const filterChips = document.querySelectorAll('.filter-chip');
    const countChipAll = document.getElementById('count-chip-all');
    const countChipSec = document.getElementById('count-chip-sec');
    const countChipReg = document.getElementById('count-chip-reg');
    const tableBody = document.getElementById('packages-table-body');

    // Tab 2 Elements
    const kernelRunningVal = document.getElementById('kernel-running-val');
    const kernelUpgradeStatus = document.getElementById('kernel-upgrade-status');
    const installedKernelsList = document.getElementById('installed-kernels-list');
    const rebootPkgsList = document.getElementById('reboot-pkgs-list');

    // Tab 3 Terminal Elements
    const terminalOutput = document.getElementById('apt-terminal-output');
    const consoleBadge = document.getElementById('console-status-badge');
    const btnClearConsole = document.getElementById('btn-clear-console');

    // Action Buttons
    const btnRefreshApt = document.getElementById('btn-refresh-apt');
    const btnUpgradeDryRun = document.getElementById('btn-upgrade-dryrun');
    const btnUpgradeAll = document.getElementById('btn-upgrade-all');

    // Modal Elements
    const confirmModal = document.getElementById('confirm-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalMessage = document.getElementById('modal-message');
    const modalWarningBox = document.getElementById('modal-warning-box');
    const modalConfirmBtn = document.getElementById('modal-confirm-btn');
    const modalCancelBtn = document.getElementById('modal-cancel-btn');
    const modalCloseBtn = document.getElementById('modal-close-btn');

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
        });
    });

    function switchToTab(tabId) {
        tabButtons.forEach(b => {
            if (b.getAttribute('data-tab') === tabId) b.classList.add('active');
            else b.classList.remove('active');
        });
        tabPanes.forEach(p => {
            if (p.id === tabId) p.classList.add('active');
            else p.classList.remove('active');
        });
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

    // Append to Terminal Box
    function appendTerminal(text, type = 'normal') {
        const timestamp = new Date().toLocaleTimeString();
        let color = '#10b981';
        if (type === 'error') color = '#ff6b6b';
        if (type === 'warning') color = '#f5af19';
        if (type === 'info') color = '#4facfe';

        const line = `[${timestamp}] ${text}\n`;
        terminalOutput.textContent += line;
        terminalOutput.scrollTop = terminalOutput.scrollHeight;
    }

    // Fetch Summary & Telemetry
    async function fetchSummary() {
        try {
            const res = await fetch('/api/packages/summary');
            const data = await res.json();
            if (!data.success) return;

            // Update dynamic Distro & Package Manager labels
            if (data.package_manager) {
                detectedPm = data.package_manager.toUpperCase();
                const distroName = data.distro_name || 'Linux';
                if (pmSubtitle) pmSubtitle.textContent = `${distroName} • Engine: ${detectedPm}`;
                if (pmRefreshLabel) pmRefreshLabel.textContent = `Perbarui Cache (${detectedPm})`;
                if (pmConsoleTabLabel) pmConsoleTabLabel.textContent = `Terminal Eksekusi (${detectedPm})`;
                if (pmConsoleSub) pmConsoleSub.textContent = `Output live proses ${detectedPm}`;
            }
            if (pmAutoUpdateService) {
                pmAutoUpdateService.textContent = data.auto_update_service && data.auto_update_service !== 'manual'
                    ? data.auto_update_service
                    : 'Pembaruan manual / distro default';
            }

            // Stat Card 1: Total Upgradable
            statTotalPkgs.textContent = data.total_upgradable;
            statPkgsSub.textContent = `${data.security_count} Keamanan, ${data.regular_count} Reguler`;
            badgePkgCount.textContent = data.total_upgradable;

            // Stat Card 2: Security Patches
            statSecurityPkgs.textContent = data.security_count;
            if (data.security_count > 0) {
                statSecuritySub.textContent = 'Pembaruan keamanan mendesak tersedia';
                statSecuritySub.style.color = '#ff6b6b';
            } else {
                statSecuritySub.textContent = 'Semua patch keamanan up-to-date';
                statSecuritySub.style.color = '#38ef7d';
            }

            // Stat Card 3: Reboot Status
            if (data.reboot_required) {
                statRebootStatus.textContent = 'REBOOT DIBUTUHKAN';
                statRebootStatus.style.color = '#ff6b6b';
                statRebootSub.textContent = `${data.reboot_pkgs.length} paket meminta reboot host`;
                statRebootIcon.style.background = 'rgba(255, 87, 87, 0.15)';
                statRebootIcon.style.color = '#ff6b6b';
            } else {
                statRebootStatus.textContent = 'Sistem Siap';
                statRebootStatus.style.color = '#38ef7d';
                statRebootSub.textContent = 'Tidak ada kernel reboot tertunda';
                statRebootIcon.style.background = 'rgba(56, 239, 125, 0.15)';
                statRebootIcon.style.color = '#38ef7d';
            }

            // Stat Card 4: Auto Updates
            if (data.auto_updates_active) {
                statAutoUpdate.textContent = 'Aktif (Running)';
                statAutoUpdate.style.color = '#38ef7d';
            } else {
                statAutoUpdate.textContent = 'Nonaktif / Standby';
                statAutoUpdate.style.color = '#94a3b8';
            }

            // Tab 2: Kernel Telemetry
            kernelRunningVal.textContent = data.running_kernel;
            if (data.kernel_upgrade_available) {
                kernelUpgradeStatus.innerHTML = '<span style="color: #f5af19;"><i class="fa-solid fa-arrow-up"></i> Kernel Baru Tersedia untuk Upgrade</span>';
            } else {
                kernelUpgradeStatus.innerHTML = '<span style="color: #38ef7d;"><i class="fa-solid fa-check"></i> Menggunakan Versi Terbaru</span>';
            }

            // Installed Kernels
            if (data.installed_kernels && data.installed_kernels.length > 0) {
                installedKernelsList.innerHTML = `
                    <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                        ${data.installed_kernels.map(k => `
                            <span class="badge ${k === data.running_kernel ? 'badge-success' : 'badge-regular'}" style="font-family: 'JetBrains Mono', monospace; font-size: 13px; padding: 6px 12px;">
                                <i class="fa-solid ${k === data.running_kernel ? 'fa-play' : 'fa-compact-disc'}"></i> ${escapeHtml(k)} ${k === data.running_kernel ? '(Aktif)' : ''}
                            </span>
                        `).join('')}
                    </div>
                `;
            } else {
                installedKernelsList.innerHTML = `<p style="color: var(--text-muted); font-size: 13px;">Tidak ada metadata kernel tambahan.</p>`;
            }

            // Reboot Pkgs List
            if (data.reboot_pkgs && data.reboot_pkgs.length > 0) {
                rebootPkgsList.innerHTML = `
                    <ul style="padding-left: 20px; color: #f5af19; font-family: 'JetBrains Mono', monospace; font-size: 13px; line-height: 1.8;">
                        ${data.reboot_pkgs.map(p => `<li>${escapeHtml(p)}</li>`).join('')}
                    </ul>
                `;
            } else {
                rebootPkgsList.innerHTML = `<p style="color: #38ef7d; font-size: 13px;"><i class="fa-solid fa-circle-check"></i> Seluruh layanan berjalan tanpa permintaan reboot.</p>`;
            }

        } catch (err) {
            console.error('Error fetching package summary:', err);
        }
    }

    // Fetch Packages List
    async function fetchPackagesList() {
        try {
            const res = await fetch('/api/packages/list');
            const data = await res.json();
            if (!data.success) {
                tableBody.innerHTML = `<tr><td colspan="6"><div class="empty-state" style="color: #ff6b6b;"><p>Gagal memuat daftar paket.</p></div></td></tr>`;
                return;
            }

            allPackages = data.packages || [];
            updateCounts();
            renderTable();
        } catch (err) {
            console.error('Error fetching packages list:', err);
            tableBody.innerHTML = `<tr><td colspan="6"><div class="empty-state" style="color: #ff6b6b;"><p>Terjadi kesalahan jaringan.</p></div></td></tr>`;
        }
    }

    function updateCounts() {
        const secCount = allPackages.filter(p => p.is_security).length;
        const regCount = allPackages.length - secCount;

        countChipAll.textContent = allPackages.length;
        countChipSec.textContent = secCount;
        countChipReg.textContent = regCount;
    }

    // Render Table
    function renderTable() {
        let filtered = allPackages;

        // Apply Category Filter
        if (activeFilter === 'security') {
            filtered = filtered.filter(p => p.is_security);
        } else if (activeFilter === 'regular') {
            filtered = filtered.filter(p => !p.is_security);
        }

        // Apply Search Query
        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            filtered = filtered.filter(p => 
                p.name.toLowerCase().includes(q) ||
                p.repo.toLowerCase().includes(q) ||
                p.new_version.toLowerCase().includes(q) ||
                p.current_version.toLowerCase().includes(q)
            );
        }

        if (filtered.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="6">
                        <div class="empty-state">
                            <i class="fa-solid fa-check-circle" style="color: #38ef7d;"></i>
                            <p>Tidak ada paket yang sesuai dengan kriteria filter.</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        tableBody.innerHTML = filtered.map(pkg => `
            <tr>
                <td>
                    <div style="font-weight: 600; font-family: 'JetBrains Mono', monospace; color: #fff;">
                        ${escapeHtml(pkg.name)}
                    </div>
                </td>
                <td>
                    <span class="badge ${pkg.is_security ? 'badge-security' : 'badge-regular'}">
                        <i class="fa-solid ${pkg.is_security ? 'fa-shield-halved' : 'fa-box'}"></i>
                        ${escapeHtml(pkg.repo)}
                    </span>
                </td>
                <td style="font-family: 'JetBrains Mono', monospace; color: var(--text-muted); font-size: 12px;">
                    ${escapeHtml(pkg.current_version)}
                </td>
                <td style="font-family: 'JetBrains Mono', monospace; color: #38ef7d; font-weight: 600; font-size: 12px;">
                    ${escapeHtml(pkg.new_version)}
                </td>
                <td style="font-size: 12px; color: var(--text-muted);">
                    ${escapeHtml(pkg.arch)}
                </td>
                <td style="text-align: right;">
                    <button class="btn btn-secondary btn-upgrade-single" data-pkg="${escapeHtml(pkg.name)}" style="padding: 6px 12px; font-size: 12px;">
                        <i class="fa-solid fa-arrow-up"></i> Upgrade
                    </button>
                </td>
            </tr>
        `).join('');

        // Attach Single Upgrade Listeners
        document.querySelectorAll('.btn-upgrade-single').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const pkgName = e.currentTarget.getAttribute('data-pkg');
                openConfirmModal({
                    title: `Upgrade Paket: ${pkgName}`,
                    message: `Apakah Anda yakin ingin memperbarui paket <strong>${escapeHtml(pkgName)}</strong> saja ke versi terbaru?`,
                    warning: 'Proses pembaruan akan mengunduh dan menimpa dependensi paket terkait.',
                    onConfirm: () => runUpgrade(false, [pkgName])
                });
            });
        });
    }

    // Filter Chips Event
    filterChips.forEach(chip => {
        chip.addEventListener('click', () => {
            filterChips.forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            activeFilter = chip.getAttribute('data-filter');
            renderTable();
        });
    });

    // Search Input Event
    searchInput.addEventListener('input', (e) => {
        searchQuery = e.target.value.trim();
        renderTable();
    });

    // Modal Handlers
    function openConfirmModal({ title, message, warning, onConfirm }) {
        modalTitle.textContent = title;
        modalMessage.innerHTML = message;
        if (warning) {
            modalWarningBox.textContent = warning;
            modalWarningBox.style.display = 'block';
        } else {
            modalWarningBox.style.display = 'none';
        }
        pendingAction = onConfirm;
        confirmModal.classList.add('active');
    }

    function closeModal() {
        confirmModal.classList.remove('active');
        pendingAction = null;
    }

    modalCloseBtn.addEventListener('click', closeModal);
    modalCancelBtn.addEventListener('click', closeModal);
    modalConfirmBtn.addEventListener('click', () => {
        if (pendingAction) {
            const action = pendingAction;
            closeModal();
            action();
        }
    });

    // Repository Cache Refresh (Universal Distro-Agnostic)
    btnRefreshApt.addEventListener('click', async () => {
        switchToTab('tab-console');
        consoleBadge.className = 'badge badge-warning';
        consoleBadge.textContent = `Memperbarui ${detectedPm}...`;
        appendTerminal(`Menjalankan pembaruan cache repository (${detectedPm}) pada host...`, 'info');

        btnRefreshApt.disabled = true;
        try {
            const res = await fetch('/api/packages/refresh', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                appendTerminal(data.output || `Cache ${detectedPm} berhasil diperbarui.`, 'normal');
                consoleBadge.className = 'badge badge-success';
                consoleBadge.textContent = 'Selesai (OK)';
                fetchSummary();
                fetchPackagesList();
            } else {
                appendTerminal(data.output || `Gagal memperbarui cache ${detectedPm}.`, 'error');
                consoleBadge.className = 'badge badge-security';
                consoleBadge.textContent = 'Gagal';
            }
        } catch (err) {
            appendTerminal(`Galat koneksi: ${err.message}`, 'error');
            consoleBadge.className = 'badge badge-security';
            consoleBadge.textContent = 'Error';
        } finally {
            btnRefreshApt.disabled = false;
        }
    });

    // Dry Run Simulation
    btnUpgradeDryRun.addEventListener('click', () => {
        runUpgrade(true, null);
    });

    // Upgrade All Packages
    btnUpgradeAll.addEventListener('click', () => {
        openConfirmModal({
            title: 'Upgrade Semua Paket Host',
            message: `Apakah Anda yakin ingin memperbarui seluruh <strong>${allPackages.length} paket</strong> yang tersedia di host?`,
            warning: 'Perhatian: Pembaruan massal dapat memerlukan waktu beberapa menit dan memicu penulisan file sistem/kernel.',
            onConfirm: () => runUpgrade(false, null)
        });
    });

    // Unified Upgrade Runner
    async function runUpgrade(dryRun = false, packages = null) {
        switchToTab('tab-console');
        const modeText = dryRun ? 'SIMULASI DRY-RUN' : 'UPGRADE AKTIF';
        const targetText = packages ? `paket [${packages.join(', ')}]` : 'seluruh paket sistem';

        consoleBadge.className = 'badge badge-warning';
        consoleBadge.textContent = dryRun ? 'Simulasi Berjalan...' : 'Sedang Menginstal...';
        appendTerminal(`Memulai ${modeText} untuk ${targetText}...`, 'info');

        btnUpgradeDryRun.disabled = true;
        btnUpgradeAll.disabled = true;

        try {
            const res = await fetch('/api/packages/upgrade', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dry_run: dryRun, packages: packages })
            });
            const data = await res.json();

            if (data.success) {
                appendTerminal(data.output || 'Operasi selesai dengan sukses.', 'normal');
                consoleBadge.className = 'badge badge-success';
                consoleBadge.textContent = dryRun ? 'Simulasi Sukses' : 'Upgrade Selesai (OK)';

                if (!dryRun) {
                    fetchSummary();
                    fetchPackagesList();
                }
            } else {
                appendTerminal(data.output || 'Gagal mengeksekusi operasi upgrade.', 'error');
                consoleBadge.className = 'badge badge-security';
                consoleBadge.textContent = 'Gagal';
            }
        } catch (err) {
            appendTerminal(`Galat koneksi eksekusi: ${err.message}`, 'error');
            consoleBadge.className = 'badge badge-security';
            consoleBadge.textContent = 'Error';
        } finally {
            btnUpgradeDryRun.disabled = false;
            btnUpgradeAll.disabled = false;
        }
    }

    // Clear Console
    btnClearConsole.addEventListener('click', () => {
        terminalOutput.textContent = 'Console dibersihkan.\n';
        consoleBadge.className = 'badge badge-regular';
        consoleBadge.textContent = 'Standby';
    });

    // Initial Load
    fetchSummary();
    fetchPackagesList();
});

