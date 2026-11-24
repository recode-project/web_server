/**
 * ==========================================================================
 * EKA DASHBOARD — SETTINGS CONTROLLER (MODULAR ZERO INLINE JS)
 * Handles General, Appearance, Monitoring, Alerts, Energy Calibration,
 * Service Integrations, MQTT, Backup/Restore, and Version Updates.
 * ==========================================================================
 */

window.userRole = (document.body && document.body.dataset.userRole) || 'readonly';

let settings = {};
let selectedColor = 'blue';
let selectedDensity = 'comfortable';
let lastMeasuredKwh = 0;
let modulesState = {};

const ENERGY_CURRENCY_PRESETS = {
    IDR: { symbol: 'Rp', code: 'IDR', locale: 'id-ID', decimals: 0, tariff: 1444.70 },
    USD: { symbol: '$', code: 'USD', locale: 'en-US', decimals: 2, tariff: 0.16 },
    EUR: { symbol: '€', code: 'EUR', locale: 'de-DE', decimals: 2, tariff: 0.30 },
    GBP: { symbol: '£', code: 'GBP', locale: 'en-GB', decimals: 2, tariff: 0.25 },
    SGD: { symbol: 'S$', code: 'SGD', locale: 'en-SG', decimals: 2, tariff: 0.30 },
    MYR: { symbol: 'RM', code: 'MYR', locale: 'ms-MY', decimals: 2, tariff: 0.57 },
    AUD: { symbol: 'A$', code: 'AUD', locale: 'en-AU', decimals: 2, tariff: 0.32 },
    JPY: { symbol: '¥', code: 'JPY', locale: 'ja-JP', decimals: 0, tariff: 31 },
    INR: { symbol: '₹', code: 'INR', locale: 'en-IN', decimals: 2, tariff: 8.0 }
};

document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    loadServices();
    loadVersion();
    loadEnergyLiveStatus();
    loadModulesStatus(false);
    bindEnergyPreviewListeners();
    handleAccessDeniedParams();
});

// ===== VERSION & UPDATE CHECKER =====
function loadVersion() {
    fetch('/api/version')
        .then(r => r.json())
        .then(data => {
            const nameEl = document.getElementById('app-name');
            const verEl = document.getElementById('app-version');
            if (nameEl) nameEl.textContent = data.name || 'Eka Dashboard';
            if (verEl) verEl.textContent = data.version || '?';
        })
        .catch(() => {
            const verEl = document.getElementById('app-version');
            if (verEl) verEl.textContent = 'Error';
        });
}

function checkUpdate() {
    const btn = document.getElementById('btn-check-update');
    const btnTop = document.getElementById('btn-update-top');
    const statusEl = document.getElementById('update-status');
    const statusTopEl = document.getElementById('update-status-top');
    const bannerEl = document.getElementById('update-banner');

    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Memeriksa...'; }
    if (btnTop) { btnTop.disabled = true; btnTop.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Memeriksa...'; }
    if (statusEl) statusEl.innerHTML = '';
    if (statusTopEl) statusTopEl.innerHTML = '';
    if (bannerEl) bannerEl.style.display = 'none';

    fetch('/api/check-update')
        .then(r => r.json())
        .then(data => {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-rotate"></i> Cek Pembaruan'; }
            if (btnTop) { btnTop.disabled = false; btnTop.innerHTML = '<i class="fa-solid fa-rotate"></i> Check for Updates'; }

            if (data.error) {
                const errHtml = `<span style="color:#f85149"><i class="fa-solid fa-exclamation-circle"></i> ${data.error}</span>`;
                if (statusEl) statusEl.innerHTML = errHtml;
                if (statusTopEl) statusTopEl.innerHTML = errHtml;
                return;
            }

            if (data.update_available) {
                if (bannerEl) bannerEl.style.display = 'block';
                const infoEl = document.getElementById('update-info');
                if (infoEl) {
                    infoEl.textContent = `Versi ${data.latest_version} tersedia (Saat ini: ${data.current_version})`;
                }
                const dlLink = document.getElementById('update-download-link');
                if (dlLink) dlLink.href = data.download_url || '#';
                if (statusEl) statusEl.innerHTML = '';
                if (statusTopEl) statusTopEl.innerHTML = '';
            } else {
                const successHtml = '<span style="color:#3fb950"><i class="fa-solid fa-check-circle"></i> Anda sudah menggunakan versi terbaru!</span>';
                if (statusEl) statusEl.innerHTML = successHtml;
                if (statusTopEl) statusTopEl.innerHTML = successHtml;
            }
        })
        .catch(() => {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-rotate"></i> Cek Pembaruan'; }
            if (btnTop) { btnTop.disabled = false; btnTop.innerHTML = '<i class="fa-solid fa-rotate"></i> Check for Updates'; }
            const errHtml = '<span style="color:#f85149"><i class="fa-solid fa-exclamation-circle"></i> Gagal memeriksa update</span>';
            if (statusEl) statusEl.innerHTML = errHtml;
            if (statusTopEl) statusTopEl.innerHTML = errHtml;
        });
}

function performAutoUpdate() {
    if (!confirm('Apakah Anda yakin ingin melakukan update otomatis? Dashboard akan berhenti sejenak selama proses berlangsung.')) {
        return;
    }

    const btn = document.getElementById('btn-auto-update');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Mengunduh & Rebuild...';
    }

    fetch('/api/perform-update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showMsg(data.message, 'success');
                setTimeout(() => window.location.reload(), 45000);
            } else {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> Update Sekarang';
                }
                showMsg(data.error || 'Gagal memulai update', 'error');
            }
        })
        .catch(() => {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> Update Sekarang';
            }
            showMsg('Koneksi terputus. Ini normal jika container sedang di-restart.', 'info');
            setTimeout(() => window.location.reload(), 45000);
        });
}

// ===== SERVICE INTEGRATIONS =====
function loadServices() {
    fetch('/api/services/status')
        .then(r => r.json())
        .then(data => {
            const tbody = document.getElementById('services-list');
            if (!tbody) return;
            if (data.services && data.services.length > 0) {
                tbody.innerHTML = data.services.map(svc => `
                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05)">
                        <td style="padding:1rem 1.2rem">
                            <div style="font-weight:500">${svc.name}</div>
                            <div style="font-size:0.75rem; color:#8b949e; margin-top:0.2rem">${svc.id}</div>
                        </td>
                        <td style="padding:1rem 1.2rem">
                            <span style="display:inline-flex; align-items:center; gap:0.4rem; padding:0.2rem 0.6rem; border-radius:4px; font-size:0.75rem; font-weight:600; background:${svc.active ? 'rgba(63,185,80,0.15)' : 'rgba(248,81,73,0.15)'}; color:${svc.active ? '#3fb950' : '#f85149'}">
                                <span style="width:6px; height:6px; border-radius:50%; background:currentColor"></span>
                                ${svc.status_text.toUpperCase()}
                            </span>
                        </td>
                        <td style="padding:1rem 1.2rem; text-align:right">
                            <div style="display:flex; gap:0.5rem; justify-content:flex-end">
                                ${svc.active
                                    ? `<button class="btn danger" onclick="controlService('${svc.id}', 'stop')" style="padding:0.3rem 0.6rem; font-size:0.75rem"><i class="fa-solid fa-stop"></i> Stop</button>
                                       <button class="btn secondary" onclick="controlService('${svc.id}', 'restart')" style="padding:0.3rem 0.6rem; font-size:0.75rem"><i class="fa-solid fa-refresh"></i> Restart</button>`
                                    : `<button class="btn primary" onclick="controlService('${svc.id}', 'start')" style="padding:0.3rem 0.6rem; font-size:0.75rem"><i class="fa-solid fa-play"></i> Start</button>`
                                }
                            </div>
                        </td>
                    </tr>
                `).join('');
            } else {
                tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; padding:2rem; color:#8b949e">No managed services found</td></tr>';
            }
        })
        .catch(() => {
            const tbody = document.getElementById('services-list');
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; padding:2rem; color:#f85149">Failed to load services</td></tr>';
            }
        });
}

function discoverServices() {
    const tbody = document.getElementById('services-list');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; padding:2rem; color:#8b949e"><i class="fa-solid fa-spinner fa-spin"></i> Scanning host services... (may take a moment)</td></tr>';

    fetch('/api/services/discover')
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; padding:2rem; color:#f85149">${data.error}</td></tr>`;
                return;
            }
            if (data.services && data.services.length > 0) {
                tbody.innerHTML = data.services.map(svc => `
                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05)">
                        <td style="padding:0.8rem 1.2rem">
                            <label style="display:flex; align-items:center; gap:0.6rem; cursor:pointer">
                                <input type="checkbox" class="svc-checkbox" data-id="${svc.id}" data-name="${svc.name}">
                                <div>
                                    <div style="font-weight:500">${svc.name}</div>
                                    <div style="font-size:0.75rem; color:#8b949e">${svc.id}</div>
                                </div>
                            </label>
                        </td>
                        <td style="padding:0.8rem 1.2rem">
                            <span style="display:inline-flex; align-items:center; gap:0.4rem; padding:0.2rem 0.6rem; border-radius:4px; font-size:0.7rem; font-weight:600; background:${svc.active ? 'rgba(63,185,80,0.15)' : 'rgba(248,81,73,0.15)'}; color:${svc.active ? '#3fb950' : '#f85149'}">
                                <span style="width:6px; height:6px; border-radius:50%; background:currentColor"></span>
                                ${svc.active ? 'RUNNING' : 'STOPPED'}
                            </span>
                            ${svc.enabled ? '<span style="margin-left:0.5rem; font-size:0.65rem; color:#8b949e">(enabled)</span>' : ''}
                        </td>
                        <td style="padding:0.8rem 1.2rem; text-align:right">
                            <div style="display:flex; gap:0.5rem; justify-content:flex-end">
                                ${svc.active
                                    ? `<button class="btn danger" onclick="controlService('${svc.id}', 'stop')" style="padding:0.2rem 0.5rem; font-size:0.7rem"><i class="fa-solid fa-stop"></i></button>
                                       <button class="btn secondary" onclick="controlService('${svc.id}', 'restart')" style="padding:0.2rem 0.5rem; font-size:0.7rem"><i class="fa-solid fa-refresh"></i></button>`
                                    : `<button class="btn primary" onclick="controlService('${svc.id}', 'start')" style="padding:0.2rem 0.5rem; font-size:0.7rem"><i class="fa-solid fa-play"></i></button>`
                                }
                            </div>
                        </td>
                    </tr>
                `).join('');

                if (window.userRole !== 'readonly' && window.userRole !== 'operator') {
                    tbody.innerHTML += `<tr><td colspan="3" style="padding:1rem 1.2rem; text-align:right; background:rgba(255,255,255,0.02)">
                        <button class="btn primary" onclick="saveSelectedServices()"><i class="fa-solid fa-save"></i> Save Selected to Dashboard</button>
                    </td></tr>`;
                }
            } else {
                tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; padding:2rem; color:#8b949e">No services found</td></tr>';
            }
        })
        .catch(e => {
            tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; padding:2rem; color:#f85149">Scan failed: ${e}</td></tr>`;
        });
}

function saveSelectedServices() {
    const checkboxes = document.querySelectorAll('.svc-checkbox:checked');
    const selected = Array.from(checkboxes).map(cb => ({
        id: cb.dataset.id,
        name: cb.dataset.name
    }));

    if (selected.length === 0) {
        showMsg('Please select at least one service', 'error');
        return;
    }

    settings.services = selected;

    fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ services: selected })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showMsg(`Saved ${selected.length} services to dashboard!`, 'success');
                loadServices();
            } else {
                showMsg('Failed to save', 'error');
            }
        })
        .catch(() => showMsg('Save failed', 'error'));
}

function controlService(serviceId, action) {
    showMsg(`${action.charAt(0).toUpperCase() + action.slice(1)}ing service...`, 'info');

    fetch('/api/services/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: serviceId, action: action })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showMsg(`Service ${action}ed successfully`, 'success');
                setTimeout(loadServices, 1000);
            } else {
                showMsg(`Error: ${data.error}`, 'error');
            }
        })
        .catch(() => showMsg('Command failed', 'error'));
}

// ===== LOAD & POPULATE SETTINGS =====
function loadSettings() {
    fetch('/api/settings?_=' + new Date().getTime())
        .then(r => r.json())
        .then(data => {
            settings = data;
            populateForm(data);
            applyPermissions();
            updateEnergyPreview();
        })
        .catch(() => {
            showMsg('Connection Error', 'error');
        });
}

function applyPermissions() {
    if (['readonly', 'operator'].includes(window.userRole)) {
        document.querySelectorAll('input, select, textarea').forEach(el => {
            el.disabled = true;
        });

        document.querySelectorAll('.btn.primary').forEach(btn => {
            btn.style.display = 'none';
        });

        const interactiveSelectors = [
            '.toggle',
            '.radio-card',
            '.color-option',
            '.svc-checkbox',
            '.btn.danger'
        ];

        document.querySelectorAll(interactiveSelectors.join(', ')).forEach(el => {
            el.style.pointerEvents = 'none';
            el.style.opacity = '0.5';
            el.style.filter = 'grayscale(100%)';
            el.style.cursor = 'not-allowed';
        });
    }
}

function populateForm(s) {
    const runSafe = (label, fn) => {
        try { fn(); }
        catch (e) { console.error('Error loading ' + label + ':', e); }
    };

    runSafe('General', () => {
        if (!s.general) return;
        const elName = document.getElementById('server-name');
        if (elName) elName.value = s.general.server_name || '';

        const elTz = document.getElementById('timezone');
        if (elTz) {
            const tz = s.general.timezone || 'UTC';
            if (!Array.from(elTz.options).some(opt => opt.value === tz)) {
                const opt = document.createElement('option');
                opt.value = tz;
                opt.textContent = tz;
                elTz.appendChild(opt);
            }
            elTz.value = tz;
        }

        const elTime = document.getElementById('time-format');
        if (elTime) elTime.value = s.general.time_format || '24h';

        const elDate = document.getElementById('date-format');
        if (elDate) elDate.value = s.general.date_format || 'DD/MM/YYYY';
    });

    runSafe('Appearance', () => {
        if (!s.appearance) return;
        if (s.appearance.accent_color) selectColor(s.appearance.accent_color);
        if (s.appearance.density) selectDensity(s.appearance.density);
    });

    runSafe('Monitoring', () => {
        if (!s.monitoring) return;
        const elWall = document.getElementById('wallboard-interval');
        if (elWall) elWall.value = s.monitoring.wallboard_interval || 2000;

        const elMet = document.getElementById('metrics-interval');
        if (elMet) elMet.value = s.monitoring.metrics_interval || 2000;

        const elHist = document.getElementById('metrics-history');
        if (elHist) elHist.value = s.monitoring.metrics_history_minutes || 60;

        const elPage = document.getElementById('default-page');
        if (elPage) elPage.value = s.monitoring.default_page || 'dashboard';
    });

    runSafe('Alerts', () => {
        if (!s.alerts) return;
        const elTog = document.getElementById('toggle-alerts');
        if (elTog) elTog.classList.toggle('on', s.alerts.enabled === true);

        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.value = val !== undefined ? val : 80;
        };
        setVal('cpu-warning', s.alerts.cpu_warning);
        setVal('cpu-critical', s.alerts.cpu_critical);
        setVal('ram-warning', s.alerts.ram_warning);
        setVal('ram-critical', s.alerts.ram_critical);
        setVal('disk-warning', s.alerts.disk_warning);
        setVal('disk-critical', s.alerts.disk_critical);
    });

    runSafe('Energy', () => {
        const e = s.energy || {};
        const code = (e.currency_code || 'IDR').toUpperCase();
        const presetEl = document.getElementById('energy-currency-preset');
        if (presetEl) {
            presetEl.value = ENERGY_CURRENCY_PRESETS[code] ? code : 'CUSTOM';
        }
        const setInput = (id, val) => {
            const el = document.getElementById(id);
            if (el && val !== undefined && val !== null) el.value = val;
        };
        setInput('energy-currency-symbol', e.currency_symbol || 'Rp');
        setInput('energy-currency-code', code);
        setInput('energy-locale', e.locale || 'id-ID');
        setInput('energy-decimals', e.decimals !== undefined ? e.decimals : 0);
        setInput('energy-tariff', e.tariff_per_kwh !== undefined ? e.tariff_per_kwh : 1444.70);
        setInput('energy-base-overhead', e.base_overhead_watts !== undefined ? e.base_overhead_watts : 9.5);
        const effVal = e.psu_efficiency !== undefined ? e.psu_efficiency : 0.85;
        setInput('energy-psu-efficiency', Math.round(effVal * 100));
        setInput('energy-idle-fallback', e.idle_watts_fallback !== undefined ? e.idle_watts_fallback : 12.0);
        setInput('energy-source-mode', e.power_source_mode || 'auto');
    });

    runSafe('Modules', () => {
        if (!s.modules) return;
        modulesState = { ...s.modules };
        const elAuto = document.getElementById('toggle-auto-hide-modules');
        if (elAuto) elAuto.classList.toggle('on', s.modules.auto_hide_uninstalled === true);
    });

    runSafe('MQTT', () => {
        if (!s.mqtt) return;
        const enabled = s.mqtt.enabled === true;
        const elTog = document.getElementById('toggle-mqtt');
        if (elTog) elTog.classList.toggle('on', enabled);

        const elArea = document.getElementById('mqtt-config-area');
        if (elArea) elArea.style.display = enabled ? 'block' : 'none';

        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.value = val || '';
        };

        setVal('mqtt-broker', s.mqtt.broker);
        setVal('mqtt-port', s.mqtt.port || 1883);
        setVal('mqtt-user', s.mqtt.user);
        setVal('mqtt-pass', s.mqtt.password);

        const elDev = document.getElementById('mqtt-devices');
        if (elDev) elDev.value = JSON.stringify(s.mqtt.devices || [], null, 2);
    });
}

// ===== ENERGY CALIBRATION & LIVE PREVIEW =====
function applyCurrencyPreset() {
    const presetEl = document.getElementById('energy-currency-preset');
    if (!presetEl) return;
    const preset = ENERGY_CURRENCY_PRESETS[presetEl.value];
    if (!preset) {
        updateEnergyPreview();
        return;
    }
    const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.value = val;
    };
    setVal('energy-currency-symbol', preset.symbol);
    setVal('energy-currency-code', preset.code);
    setVal('energy-locale', preset.locale);
    setVal('energy-decimals', preset.decimals);
    setVal('energy-tariff', preset.tariff);
    updateEnergyPreview();
}

function bindEnergyPreviewListeners() {
    const ids = ['energy-currency-symbol', 'energy-locale', 'energy-decimals', 'energy-tariff'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', updateEnergyPreview);
            el.addEventListener('change', updateEnergyPreview);
        }
    });
}

function formatPreviewCost(kwh, symbol, locale, decimals, tariff) {
    const cost = (parseFloat(kwh) || 0) * (parseFloat(tariff) || 0);
    const dec = Math.max(0, Math.min(4, parseInt(decimals, 10) || 0));
    let formatted;
    if (dec === 0 && cost > 0 && cost < 1) {
        formatted = '< 1';
    } else {
        try {
            formatted = cost.toLocaleString(locale || 'en-US', {
                minimumFractionDigits: dec,
                maximumFractionDigits: dec
            });
        } catch (e) {
            formatted = cost.toFixed(dec);
        }
    }
    const sym = (symbol || '').trim();
    return sym ? `${sym} ${formatted}` : formatted;
}

function updateEnergyPreview() {
    const elPreview = document.getElementById('energy-cost-preview');
    if (!elPreview) return;
    const sym = (document.getElementById('energy-currency-symbol') || {}).value || 'Rp';
    const loc = (document.getElementById('energy-locale') || {}).value || 'id-ID';
    const dec = (document.getElementById('energy-decimals') || {}).value || 0;
    const tariff = (document.getElementById('energy-tariff') || {}).value || 0;
    const kwhSample = lastMeasuredKwh > 0 ? lastMeasuredKwh : 1.0;
    const label = lastMeasuredKwh > 0 ? `${lastMeasuredKwh.toFixed(4)} kWh` : '1.0000 kWh sample';
    elPreview.textContent = `${formatPreviewCost(kwhSample, sym, loc, dec, tariff)} (${label})`;
}

function loadEnergyLiveStatus() {
    fetch('/api/metrics')
        .then(r => r.json())
        .then(data => {
            if (!data || !data.power) return;
            const p = data.power;
            lastMeasuredKwh = parseFloat(p.kwh || 0) || 0;
            const sensorEl = document.getElementById('energy-live-sensor');
            if (sensorEl) {
                const srcMap = {
                    rapl: 'Hardware RAPL (Intel/AMD)',
                    power_supply: 'Linux power_supply (Battery/UPS)',
                    model: 'Calibrated CPU Model'
                };
                let txt = `${p.watts_est}W via ${srcMap[p.source] || p.source}`;
                if (p.battery && p.battery.capacity !== null && p.battery.capacity !== undefined) {
                    txt += ` | ${p.battery.type} ${p.battery.capacity}% (${p.battery.status})`;
                }
                sensorEl.textContent = txt;
            }
            updateEnergyPreview();
        })
        .catch(() => {});
}

function saveEnergy() {
    const effPct = parseFloat(document.getElementById('energy-psu-efficiency').value);
    const effRatio = isNaN(effPct) ? 0.85 : Math.max(50, Math.min(100, effPct)) / 100.0;

    saveSection('energy', {
        currency_symbol: (document.getElementById('energy-currency-symbol').value || 'Rp').trim(),
        currency_code: (document.getElementById('energy-currency-code').value || 'IDR').trim().toUpperCase(),
        locale: (document.getElementById('energy-locale').value || 'id-ID').trim(),
        decimals: parseInt(document.getElementById('energy-decimals').value, 10) || 0,
        tariff_per_kwh: parseFloat(document.getElementById('energy-tariff').value) || 0,
        base_overhead_watts: parseFloat(document.getElementById('energy-base-overhead').value) || 0,
        psu_efficiency: effRatio,
        idle_watts_fallback: parseFloat(document.getElementById('energy-idle-fallback').value) || 12.0,
        power_source_mode: document.getElementById('energy-source-mode').value || 'auto'
    });
}

function resetEnergyCounter() {
    if (!confirm('Reset accumulated energy counter (kWh) back to 0.0000?')) return;
    fetch('/api/energy/reset', { method: 'POST' })
        .then(r => {
            if (r.status === 403) {
                showAdModal('energy counter reset (Write Access)');
                throw new Error('ACCESS_DENIED_HANDLED');
            }
            return r.json();
        })
        .then(data => {
            if (data.success) {
                lastMeasuredKwh = 0;
                showMsg('Energy kWh counter reset to 0.0000', 'success');
                loadEnergyLiveStatus();
            } else {
                showMsg(data.error || 'Failed to reset energy counter', 'error');
            }
        })
        .catch(err => {
            if (err.message === 'ACCESS_DENIED_HANDLED') return;
            showMsg('Failed to reset energy counter', 'error');
        });
}

// ===== OPTIONAL MODULES & VISIBILITY =====
function escapeSettingsHtml(str) {
    return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function loadModulesStatus(forceRefresh = false) {
    const container = document.getElementById('modules-visibility-list');
    if (!container) return;
    if (forceRefresh) {
        container.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem; padding:1rem 0;"><i class="fa-solid fa-spinner fa-spin"></i> Probing host modules...</div>';
    }
    const url = forceRefresh ? '/api/modules/status?refresh=1' : '/api/modules/status';
    fetch(url)
        .then(r => r.json())
        .then(data => {
            if (!data || !data.success || !Array.isArray(data.modules)) {
                container.innerHTML = '<div style="color:#f87171; font-size:0.85rem;">Failed to load optional modules status.</div>';
                return;
            }
            modulesState = { ...(data.settings || {}) };
            const elAuto = document.getElementById('toggle-auto-hide-modules');
            if (elAuto) elAuto.classList.toggle('on', Boolean(data.auto_hide_uninstalled));
            renderModulesList(data.modules);
            applyPermissions();
        })
        .catch(() => {
            container.innerHTML = '<div style="color:#f87171; font-size:0.85rem;">Connection error while probing modules.</div>';
        });
}

function renderModulesList(modules) {
    const container = document.getElementById('modules-visibility-list');
    if (!container) return;
    container.innerHTML = modules.map(mod => {
        const isVisible = modulesState[mod.id] !== undefined ? Boolean(modulesState[mod.id]) : Boolean(mod.visible);
        let badgeBg = 'rgba(245, 158, 11, 0.16)';
        let badgeColor = '#fbbf24';
        let badgeText = 'Not Installed';
        if (mod.installed && mod.configured) {
            badgeBg = 'rgba(16, 185, 129, 0.16)';
            badgeColor = '#34d399';
            badgeText = 'Installed';
        } else if (mod.installed) {
            badgeBg = 'rgba(56, 189, 248, 0.16)';
            badgeColor = '#38bdf8';
            badgeText = 'Opt-In';
        }
        return `
            <div style="background:rgba(10,12,22,0.55); border:1px solid var(--glass-border); border-radius:12px; padding:0.9rem 1rem; display:flex; justify-content:space-between; align-items:center; gap:0.8rem;">
                <div style="min-width:0;">
                    <div style="display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap; margin-bottom:0.25rem;">
                        <i class="${escapeSettingsHtml(mod.icon)}" style="color:var(--accent-blue); font-size:0.9rem;"></i>
                        <span style="font-weight:600; font-size:0.9rem;">${escapeSettingsHtml(mod.name)}</span>
                        <span style="font-size:0.68rem; font-weight:600; padding:0.15rem 0.45rem; border-radius:999px; background:${badgeBg}; color:${badgeColor};">${badgeText}</span>
                    </div>
                    <div style="font-size:0.75rem; color:var(--text-muted); line-height:1.35;">${escapeSettingsHtml(mod.description)}</div>
                    <div style="font-size:0.7rem; color:#8b949e; margin-top:0.25rem;">${escapeSettingsHtml(mod.category)} &bull; ${escapeSettingsHtml(mod.detail)}</div>
                </div>
                <div class="toggle ${isVisible ? 'on' : ''}" id="toggle-mod-${escapeSettingsHtml(mod.id)}" data-module-id="${escapeSettingsHtml(mod.id)}" onclick="toggleModuleVisibility('${escapeSettingsHtml(mod.id)}')" title="Show or hide on Dashboard"></div>
            </div>
        `;
    }).join('');
}

function toggleAutoHideModules() {
    const el = document.getElementById('toggle-auto-hide-modules');
    if (!el) return;
    el.classList.toggle('on');
    modulesState.auto_hide_uninstalled = el.classList.contains('on');
}

function toggleModuleVisibility(modId) {
    const el = document.getElementById('toggle-mod-' + modId);
    if (!el) return;
    el.classList.toggle('on');
    modulesState[modId] = el.classList.contains('on');
}

function saveModules() {
    const payload = { ...modulesState };
    const elAuto = document.getElementById('toggle-auto-hide-modules');
    if (elAuto) payload.auto_hide_uninstalled = elAuto.classList.contains('on');
    document.querySelectorAll('[data-module-id]').forEach(el => {
        const mid = el.getAttribute('data-module-id');
        if (mid) payload[mid] = el.classList.contains('on');
    });
    saveSection('modules', payload);
}

// ===== APPEARANCE / ALERTS / MQTT / GENERAL ACTIONS =====
function selectColor(color) {
    selectedColor = color;
    document.querySelectorAll('.color-option').forEach(c => c.classList.remove('active'));
    const target = document.querySelector(`.color-option.${color}`);
    if (target) target.classList.add('active');
}

function selectDensity(density) {
    selectedDensity = density;
    document.querySelectorAll('.radio-card').forEach(c => c.classList.remove('active'));
    const target = document.getElementById('density-' + density);
    if (target) target.classList.add('active');
}

function toggleAlerts() {
    const el = document.getElementById('toggle-alerts');
    if (el) el.classList.toggle('on');
}

function toggleMqtt() {
    const t = document.getElementById('toggle-mqtt');
    if (!t) return;
    t.classList.toggle('on');
    const area = document.getElementById('mqtt-config-area');
    if (area) area.style.display = t.classList.contains('on') ? 'block' : 'none';
}

function saveMqtt() {
    let devices = [];
    const rawJson = document.getElementById('mqtt-devices').value;

    try {
        devices = JSON.parse(rawJson);
    } catch (e) {
        alert('Invalid JSON in Devices Map:\n' + e.message);
        return;
    }

    const payload = {
        enabled: document.getElementById('toggle-mqtt').classList.contains('on'),
        broker: document.getElementById('mqtt-broker').value,
        port: parseInt(document.getElementById('mqtt-port').value, 10) || 1883,
        user: document.getElementById('mqtt-user').value,
        password: document.getElementById('mqtt-pass').value,
        devices: devices
    };

    saveSection('mqtt', payload);
}

function testMqtt() {
    alert('Test connection feature is coming in the next update. Please save the config first.');
}

function saveGeneral() {
    saveSection('general', {
        server_name: document.getElementById('server-name').value,
        timezone: document.getElementById('timezone').value,
        time_format: document.getElementById('time-format').value,
        date_format: document.getElementById('date-format').value
    });
}

function saveAppearance() {
    saveSection('appearance', {
        accent_color: selectedColor,
        density: selectedDensity
    });
}

function saveMonitoring() {
    saveSection('monitoring', {
        wallboard_interval: parseInt(document.getElementById('wallboard-interval').value, 10),
        metrics_interval: parseInt(document.getElementById('metrics-interval').value, 10),
        metrics_history_minutes: parseInt(document.getElementById('metrics-history').value, 10),
        default_page: document.getElementById('default-page').value
    });
}

function saveAlerts() {
    saveSection('alerts', {
        enabled: document.getElementById('toggle-alerts').classList.contains('on'),
        cpu_warning: parseInt(document.getElementById('cpu-warning').value, 10),
        cpu_critical: parseInt(document.getElementById('cpu-critical').value, 10),
        ram_warning: parseInt(document.getElementById('ram-warning').value, 10),
        ram_critical: parseInt(document.getElementById('ram-critical').value, 10),
        disk_warning: parseInt(document.getElementById('disk-warning').value, 10),
        disk_critical: parseInt(document.getElementById('disk-critical').value, 10)
    });
}

function saveSection(section, data) {
    fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [section]: data })
    })
        .then(r => {
            if (r.status === 403) {
                showAdModal(section + ' settings (Write Access)');
                throw new Error('ACCESS_DENIED_HANDLED');
            }
            if (!r.ok) {
                return r.text().then(text => { throw new Error('Server Error ' + r.status + ': ' + text.substring(0, 50)); });
            }
            return r.json();
        })
        .then(result => {
            if (result.success) {
                showMsg('Settings saved successfully!', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                showMsg(result.error || 'Failed to save', 'error');
            }
        })
        .catch(err => {
            if (err.message === 'ACCESS_DENIED_HANDLED') return;
            console.error(err);
            showMsg(err.message || 'Connection Error', 'error');
        });
}

function exportSettings() {
    window.location.href = '/api/settings/export';
}

function importSettings(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function (e) {
        try {
            const data = JSON.parse(e.target.result);
            fetch('/api/settings/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
                .then(r => r.json())
                .then(result => {
                    if (result.success) {
                        showMsg('Settings imported!', 'success');
                        loadSettings();
                    } else {
                        showMsg(result.error || 'Import failed', 'error');
                    }
                });
        } catch (err) {
            showMsg('Invalid JSON file', 'error');
        }
    };
    reader.readAsText(file);
}

function resetSettings() {
    if (!confirm('This will reset ALL settings to defaults. Are you sure?')) return;

    fetch('/api/settings/reset', { method: 'POST' })
        .then(r => r.json())
        .then(result => {
            if (result.success) {
                showMsg('Settings reset to defaults', 'success');
                loadSettings();
            }
        });
}

function showMsg(text, type) {
    const msg = document.getElementById('global-msg');
    if (!msg) return;
    msg.innerHTML = `<i class="fa-solid fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i> ${text}`;
    msg.className = 'msg ' + type;
    setTimeout(() => msg.classList.add('hidden'), 3000);
}

function showAdModal(feature) {
    const m = document.getElementById('ad-modal');
    const msg = document.getElementById('ad-message');
    if (msg) msg.textContent = 'Anda tidak memiliki akses untuk menu: ' + feature + '. Silakan hubungi Administrator.';
    if (m) m.classList.add('active');
}

function closeAdModal() {
    const m = document.getElementById('ad-modal');
    if (m) m.classList.remove('active');
    window.history.replaceState({}, document.title, window.location.pathname);
}

function handleAccessDeniedParams() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('error') === 'access_denied') {
        const feature = urlParams.get('feature') || 'Restricted Area';
        setTimeout(() => showAdModal(feature), 100);
    }
}

