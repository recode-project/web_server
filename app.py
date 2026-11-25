import psutil
import platform
import socket
import re
import shlex
from flask import Flask, jsonify, render_template, request, Response, session, redirect, url_for, stream_with_context, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from functools import wraps
import time
import subprocess
import os
import select
import struct
import hashlib
import json
import io
from datetime import datetime
import requests
import threading
import eventlet
import sqlite3
import docker # Ensure docker is imported
# LICENSE IMPORTS
try:
   import docker as docker_sdk # Alias for compatibility if needed
except ImportError:
   docker_sdk = None

try:
    import pty
    import fcntl
    import termios
except ImportError:
    pty = None
    fcntl = None
    termios = None # Import License Manager

# Base Directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============ VERSI APLIKASI ============
APP_VERSION = "1.4"
APP_NAME = "Eka Dashboard"
UPDATE_CHECK_URL = os.environ.get('UPDATE_URL', "https://raw.githubusercontent.com/recode-project/web_server/main/version.json")
# ========================================

# Data Directory (For Persistence across updates)
DATA_DIR = os.path.join(BASE_DIR, 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Energy Monitoring & Universal Hardware Power Engine (RAPL / power_supply / Model)
ENERGY_FILE = os.path.join(DATA_DIR, 'energy_data.json')
TOTAL_KWH = 0.0
CURRENT_WATTS = 0.0
POWER_SOURCE = "model"

DEFAULT_ENERGY_SETTINGS = {
    'currency_symbol': 'Rp',
    'currency_code': 'IDR',
    'locale': 'id-ID',
    'decimals': 0,
    'tariff_per_kwh': 1444.70,
    'base_overhead_watts': 9.5,
    'psu_efficiency': 0.85,
    'idle_watts_fallback': 12.0,
    'power_source_mode': 'auto',  # 'auto' | 'rapl' | 'power_supply' | 'model'
}
_ENERGY_SETTINGS_CACHE = {'ts': 0.0, 'data': None}


def _invalidate_energy_cache():
    _ENERGY_SETTINGS_CACHE['ts'] = 0.0
    _ENERGY_SETTINGS_CACHE['data'] = None


OPTIONAL_MODULES_CATALOG = [
    {
        'id': 'lxd',
        'name': 'LXD / Incus Manager',
        'category': 'Virtualization',
        'icon': 'fa-brands fa-linux',
        'url': '/lxd',
        'app_id': 'lxd',
        'description': 'Manage LXD or Incus system containers across projects.',
        'default_visible': True,
    },
    {
        'id': 'adblocker',
        'name': 'AdGuard Home DNS',
        'category': 'Network',
        'icon': 'fa-solid fa-shield-virus',
        'url': '/adblocker',
        'app_id': 'adblocker',
        'description': 'Network-wide DNS ad-blocking, query logs & client rules.',
        'default_visible': True,
    },
    {
        'id': 'vpn',
        'name': 'VPN Manager',
        'category': 'Network',
        'icon': 'fa-solid fa-shield-halved',
        'url': '/vpn',
        'app_id': 'vpn',
        'description': 'Tailscale Mesh, WireGuard Hub & ZeroTier tunnel manager.',
        'default_visible': True,
    },
    {
        'id': 'sharing',
        'name': 'File Sharing (Samba)',
        'category': 'Storage',
        'icon': 'fa-solid fa-share-nodes',
        'url': '/sharing',
        'app_id': 'sharing',
        'description': 'LAN SMB/CIFS file sharing for Windows, macOS & Linux.',
        'default_visible': True,
    },
    {
        'id': 'websites',
        'name': 'Websites & Reverse Proxy',
        'category': 'Web',
        'icon': 'fa-solid fa-globe',
        'url': '/websites',
        'app_id': 'websites',
        'description': 'Nginx/Apache/Caddy vhosts, traffic analytics & SSL monitor.',
        'default_visible': True,
    },
    {
        'id': 'mobile-backup',
        'name': 'Mobile Sync',
        'category': 'Backup',
        'icon': 'fa-solid fa-mobile-screen',
        'url': '/mobile-backup',
        'app_id': 'mobile-backup',
        'description': 'Automated mobile media and document backup endpoint.',
        'default_visible': True,
    },
    {
        'id': 'store',
        'name': 'App Store (Docker)',
        'category': 'Containers',
        'icon': 'fa-solid fa-store',
        'url': '/store',
        'app_id': 'store',
        'description': 'One-click self-hosted Docker application catalog.',
        'default_visible': True,
    },
    {
        'id': 'mqtt',
        'name': 'Home Automation (MQTT)',
        'category': 'IoT',
        'icon': 'fa-solid fa-house-signal',
        'url': '/settings',
        'app_id': None,
        'description': 'MQTT IoT sensors and smart switches widget on Dashboard/Wallboard.',
        'default_visible': False,
    },
    {
        'id': 'whatsapp_bridge',
        'name': 'WhatsApp Alert Gateway',
        'category': 'Notifications',
        'icon': 'fa-brands fa-whatsapp',
        'url': '/alerts',
        'app_id': None,
        'description': 'Optional WhatsApp HTTP bridge for alert notifications.',
        'default_visible': False,
    },
]

DEFAULT_MODULE_SETTINGS = {
    **{m['id']: m['default_visible'] for m in OPTIONAL_MODULES_CATALOG},
    'auto_hide_uninstalled': False,
}
_MODULES_STATUS_CACHE = {'ts': 0.0, 'data': None}


def _invalidate_modules_cache():
    _MODULES_STATUS_CACHE['ts'] = 0.0
    _MODULES_STATUS_CACHE['data'] = None


def _sanitize_module_settings(raw):
    cfg = dict(DEFAULT_MODULE_SETTINGS)
    if not isinstance(raw, dict):
        return cfg
    for key in DEFAULT_MODULE_SETTINGS:
        if key in raw:
            cfg[key] = bool(raw[key])
    return cfg


def _probe_optional_modules(force_refresh=False):
    """Fast cross-distro probe of optional modules' installation & runtime state (cached 15s)."""
    now = time.time()
    if (not force_refresh) and _MODULES_STATUS_CACHE['data'] is not None and (now - _MODULES_STATUS_CACHE['ts'] < 15.0):
        return [dict(item) for item in _MODULES_STATUS_CACHE['data']]

    # Single lightweight shell probe for host binaries (includes /snap/bin for Snap LXD)
    found_bins = set()
    try:
        probe_cmd = (
            'PATH="$PATH:/snap/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/sbin"; '
            'for b in lxc incus smbd tailscale wg zerotier-cli AdGuardHome; do '
            'command -v "$b" >/dev/null 2>&1 && echo "$b"; done; true'
        )
        res = _run_host_cmd(['sh', '-c', probe_cmd], timeout=4, include_pid=False)
        if res.stdout:
            found_bins = {line.strip() for line in res.stdout.splitlines() if line.strip()}
    except Exception:
        pass

    # Docker availability + check AdGuard container
    docker_ok = False
    adguard_container = False
    try:
        client = docker.from_env()
        ctrs = client.containers.list(all=True)
        docker_ok = True
        for c in ctrs:
            cname = (c.name or '').lower()
            img = ((c.attrs.get('Config') or {}).get('Image') or '').lower()
            if 'adguard' in cname or 'adguard' in img:
                adguard_container = True
                break
    except Exception:
        pass

    # Web servers from Tahap 3 helper
    web_servers = []
    try:
        web_servers = _detect_host_web_servers()
    except Exception:
        pass

    # App settings & alert configs
    app_cfg = load_app_settings()
    mod_vis = _sanitize_module_settings(app_cfg.get('modules'))
    mqtt_cfg = app_cfg.get('mqtt') or {}
    wa_cfg = {}
    try:
        wa_cfg = (_load_alert_config() or {}).get('whatsapp') or {}
    except Exception:
        pass

    lxd_installed = ('lxc' in found_bins) or ('incus' in found_bins)
    adguard_installed = ('AdGuardHome' in found_bins) or adguard_container
    vpn_installed = bool({'tailscale', 'wg', 'zerotier-cli'} & found_bins)
    smb_installed = ('smbd' in found_bins) or os.path.exists('/host/root/etc/samba/smb.conf') or os.path.exists('/etc/samba/smb.conf')
    web_installed = len(web_servers) > 0
    mqtt_configured = bool(mqtt_cfg.get('enabled') and (mqtt_cfg.get('broker') or '').strip())
    wa_configured = bool(wa_cfg.get('enabled') and (wa_cfg.get('gateway_url') or '').strip())

    state_map = {
        'lxd': {'installed': lxd_installed, 'configured': lxd_installed, 'detail': 'incus' if 'incus' in found_bins else ('lxc' if 'lxc' in found_bins else 'Not installed')},
        'adblocker': {'installed': adguard_installed, 'configured': adguard_installed, 'detail': 'AdGuard Home detected' if adguard_installed else 'Not installed'},
        'vpn': {'installed': vpn_installed, 'configured': vpn_installed, 'detail': ', '.join(sorted({'tailscale', 'wg', 'zerotier-cli'} & found_bins)) or 'Not installed'},
        'sharing': {'installed': smb_installed, 'configured': smb_installed, 'detail': 'Samba (smbd)' if smb_installed else 'Not installed'},
        'websites': {'installed': web_installed, 'configured': web_installed, 'detail': ', '.join(s['name'] for s in web_servers) if web_servers else 'No web server detected'},
        'mobile-backup': {'installed': True, 'configured': True, 'detail': 'Built-in sync module'},
        'store': {'installed': docker_ok, 'configured': docker_ok, 'detail': 'Docker Engine ready' if docker_ok else 'Docker unavailable'},
        'mqtt': {'installed': True, 'configured': mqtt_configured, 'detail': f"Broker: {mqtt_cfg.get('broker')}" if mqtt_configured else 'Opt-in (disabled)'},
        'whatsapp_bridge': {'installed': wa_configured, 'configured': wa_configured, 'detail': wa_cfg.get('gateway_url') if wa_configured else 'Opt-in (disabled)'},
    }

    results = []
    for meta in OPTIONAL_MODULES_CATALOG:
        mid = meta['id']
        st = state_map.get(mid, {'installed': False, 'configured': False, 'detail': ''})
        results.append({
            **meta,
            'installed': bool(st['installed']),
            'configured': bool(st['configured']),
            'detail': st['detail'],
            'visible': bool(mod_vis.get(mid, meta['default_visible'])),
        })

    _MODULES_STATUS_CACHE['ts'] = now
    _MODULES_STATUS_CACHE['data'] = results
    return [dict(item) for item in results]


def _sanitize_energy_settings(raw):
    cfg = dict(DEFAULT_ENERGY_SETTINGS)
    if not isinstance(raw, dict):
        return cfg

    sym = str(raw.get('currency_symbol', cfg['currency_symbol'])).strip()
    if sym:
        cfg['currency_symbol'] = sym[:10]

    code = str(raw.get('currency_code', cfg['currency_code'])).strip().upper()
    code_clean = ''.join(ch for ch in code if ch.isalnum())[:8]
    if code_clean:
        cfg['currency_code'] = code_clean

    loc = str(raw.get('locale', cfg['locale'])).strip()
    loc_clean = ''.join(ch for ch in loc if ch.isalnum() or ch in ('-', '_'))[:16]
    if loc_clean:
        cfg['locale'] = loc_clean

    try:
        dec = int(raw.get('decimals', cfg['decimals']))
        cfg['decimals'] = max(0, min(4, dec))
    except (ValueError, TypeError):
        pass

    try:
        tariff = float(raw.get('tariff_per_kwh', cfg['tariff_per_kwh']))
        if tariff >= 0.0:
            cfg['tariff_per_kwh'] = round(tariff, 6)
    except (ValueError, TypeError):
        pass

    try:
        overhead = float(raw.get('base_overhead_watts', cfg['base_overhead_watts']))
        cfg['base_overhead_watts'] = round(max(0.0, min(500.0, overhead)), 2)
    except (ValueError, TypeError):
        pass

    try:
        eff = float(raw.get('psu_efficiency', cfg['psu_efficiency']))
        if eff > 1.0 and eff <= 100.0:
            eff = eff / 100.0
        cfg['psu_efficiency'] = round(max(0.50, min(1.00, eff)), 4)
    except (ValueError, TypeError):
        pass

    try:
        idle_w = float(raw.get('idle_watts_fallback', cfg['idle_watts_fallback']))
        cfg['idle_watts_fallback'] = round(max(1.0, min(500.0, idle_w)), 2)
    except (ValueError, TypeError):
        pass

    mode = str(raw.get('power_source_mode', cfg['power_source_mode'])).strip().lower()
    if mode in ('auto', 'rapl', 'power_supply', 'model'):
        cfg['power_source_mode'] = mode

    return cfg


def _get_energy_settings(force_refresh=False):
    now = time.time()
    if (not force_refresh) and _ENERGY_SETTINGS_CACHE['data'] is not None and (now - _ENERGY_SETTINGS_CACHE['ts'] < 5.0):
        return dict(_ENERGY_SETTINGS_CACHE['data'])

    raw_energy = {}
    try:
        loader = globals().get('load_app_settings')
        if callable(loader):
            raw_energy = (loader() or {}).get('energy', {})
        else:
            settings_path = os.path.join(DATA_DIR, 'app_settings.json')
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    raw_energy = (json.load(f) or {}).get('energy', {})
    except Exception:
        raw_energy = {}

    sanitized = _sanitize_energy_settings(raw_energy)
    _ENERGY_SETTINGS_CACHE['ts'] = now
    _ENERGY_SETTINGS_CACHE['data'] = sanitized
    return dict(sanitized)


class HardwarePowerReader:
    """Universal Hardware Power Reader: Intel/AMD RAPL, Linux power_supply (Battery/UPS), and Calibrated Model."""
    def __init__(self, powercap_dir=None, power_supply_dir=None):
        self.powercap_dir = powercap_dir or (
            '/sys/class/powercap' if os.path.exists('/sys/class/powercap') else '/host/root/sys/class/powercap'
        )
        self.power_supply_dir = power_supply_dir or (
            '/sys/class/power_supply' if os.path.exists('/sys/class/power_supply') else '/host/root/sys/class/power_supply'
        )
        self.rapl_available = False
        self.rapl_path = None
        self.max_energy_range_uj = None
        self.last_energy_uj = None
        self.last_timestamp = None
        self.last_cpu_pkg_watts = None
        self.last_measured_watts = 0.0
        self.power_supply_paths = []
        self._init_rapl()
        self._discover_power_supplies()

    def _init_rapl(self):
        base_dir = self.powercap_dir
        if base_dir and os.path.exists(base_dir):
            try:
                for entry in sorted(os.listdir(base_dir)):
                    if entry.startswith('intel-rapl') or entry.startswith('amd-rapl'):
                        pkg_path = os.path.join(base_dir, entry)
                        uj_file = os.path.join(pkg_path, 'energy_uj')
                        if os.path.exists(uj_file):
                            try:
                                with open(uj_file, 'r') as f:
                                    val = int(f.read().strip())
                                self.rapl_path = uj_file
                                self.rapl_available = True
                                self.last_energy_uj = val
                                self.last_timestamp = time.time()
                                max_f = os.path.join(pkg_path, 'max_energy_range_uj')
                                if os.path.exists(max_f):
                                    with open(max_f, 'r') as mf:
                                        self.max_energy_range_uj = int(mf.read().strip())
                                break
                            except Exception:
                                pass
            except Exception:
                pass

    def _discover_power_supplies(self):
        """Discover Linux system Battery / UPS sensors under /sys/class/power_supply (excluding peripheral HID devices)."""
        found = []
        base_dir = self.power_supply_dir
        if base_dir and os.path.exists(base_dir):
            try:
                for entry in sorted(os.listdir(base_dir)):
                    dev_path = os.path.join(base_dir, entry)
                    if not os.path.isdir(dev_path):
                        continue
                    scope_file = os.path.join(dev_path, 'scope')
                    if os.path.exists(scope_file):
                        try:
                            with open(scope_file, 'r') as sf:
                                if sf.read().strip().lower() == 'device':
                                    continue
                        except Exception:
                            pass
                    type_file = os.path.join(dev_path, 'type')
                    ptype = ''
                    if os.path.exists(type_file):
                        try:
                            with open(type_file, 'r') as tf:
                                ptype = tf.read().strip()
                        except Exception:
                            pass
                    if ptype.lower() in ('battery', 'ups') or entry.upper().startswith(('BAT', 'UPS')):
                        found.append((entry, ptype or 'Battery', dev_path))
            except Exception:
                pass
        self.power_supply_paths = found

    def _read_single_supply_watts(self, dev_path):
        """Read instantaneous power draw in Watts from a sysfs power_supply directory."""
        power_file = os.path.join(dev_path, 'power_now')
        if os.path.exists(power_file):
            try:
                with open(power_file, 'r') as f:
                    uw = abs(int(f.read().strip()))
                if uw > 0:
                    return uw / 1_000_000.0
            except Exception:
                pass

        curr_file = os.path.join(dev_path, 'current_now')
        volt_file = os.path.join(dev_path, 'voltage_now')
        if os.path.exists(curr_file) and os.path.exists(volt_file):
            try:
                with open(curr_file, 'r') as cf:
                    ua = abs(int(cf.read().strip()))
                with open(volt_file, 'r') as vf:
                    uv = abs(int(vf.read().strip()))
                if ua > 0 and uv > 0:
                    return (ua * uv) / 1_000_000_000_000.0
            except Exception:
                pass
        return None

    def _read_power_supply_watts(self):
        if not self.power_supply_paths:
            return None
        total = 0.0
        found_active = False
        for _, _, dev_path in self.power_supply_paths:
            w = self._read_single_supply_watts(dev_path)
            if w is not None and w >= 0.5:
                total += w
                found_active = True
        if found_active:
            return round(total, 2)
        return None

    def get_battery_info(self):
        """Return first detected system Battery/UPS telemetry dict, or None if absent."""
        if not self.power_supply_paths:
            return None
        name, ptype, dev_path = self.power_supply_paths[0]
        status = 'Unknown'
        capacity = None
        status_file = os.path.join(dev_path, 'status')
        if os.path.exists(status_file):
            try:
                with open(status_file, 'r') as sf:
                    status = sf.read().strip() or 'Unknown'
            except Exception:
                pass
        cap_file = os.path.join(dev_path, 'capacity')
        if os.path.exists(cap_file):
            try:
                with open(cap_file, 'r') as cf:
                    capacity = int(cf.read().strip())
            except Exception:
                pass
        watts = self._read_single_supply_watts(dev_path)
        return {
            'device': name,
            'type': ptype,
            'status': status,
            'capacity': capacity,
            'watts': round(watts, 2) if watts is not None else None,
        }

    def _read_rapl_watts(self, now, base_overhead, psu_eff):
        if not (self.rapl_available and self.rapl_path):
            return None
        try:
            with open(self.rapl_path, 'r') as f:
                curr_uj = int(f.read().strip())
            dt = now - self.last_timestamp if self.last_timestamp else 1.0
            if dt >= 0.5:
                diff_uj = curr_uj - self.last_energy_uj
                if diff_uj < 0 and self.max_energy_range_uj:
                    diff_uj = (self.max_energy_range_uj - self.last_energy_uj) + curr_uj

                if diff_uj >= 0:
                    cpu_pkg_watts = diff_uj / (1_000_000.0 * dt)
                    self.last_cpu_pkg_watts = cpu_pkg_watts
                    wall_watts = (cpu_pkg_watts + base_overhead) / psu_eff
                    self.last_measured_watts = round(wall_watts, 2)
                    self.last_energy_uj = curr_uj
                    self.last_timestamp = now
                    return self.last_measured_watts
            elif self.last_cpu_pkg_watts is not None:
                wall_watts = (self.last_cpu_pkg_watts + base_overhead) / psu_eff
                self.last_measured_watts = round(wall_watts, 2)
                return self.last_measured_watts
            elif self.last_measured_watts > 0:
                return self.last_measured_watts
        except Exception:
            pass
        return None

    def _read_model_watts(self, cpu_percent, idle_fallback):
        is_arm = platform.machine().lower().startswith(('arm', 'aarch'))
        cores = psutil.cpu_count(logical=True) or 2
        if is_arm:
            arm_base = min(idle_fallback, 5.0) if idle_fallback == DEFAULT_ENERGY_SETTINGS['idle_watts_fallback'] else idle_fallback
            watts = (3.5 if idle_fallback == DEFAULT_ENERGY_SETTINGS['idle_watts_fallback'] else arm_base) + (cpu_percent * 5.0 / 100.0)
        else:
            scale_watt = max(15.0, cores * 6.0)
            watts = idle_fallback + (cpu_percent * scale_watt / 100.0)
        return round(watts, 2)

    def read_power(self, cpu_percent=None, energy_cfg=None):
        now = time.time()
        if cpu_percent is None:
            cpu_percent = psutil.cpu_percent(interval=None) or 0.0

        cfg = _sanitize_energy_settings(energy_cfg) if energy_cfg is not None else _get_energy_settings()
        base_overhead = cfg['base_overhead_watts']
        psu_eff = cfg['psu_efficiency']
        idle_fallback = cfg['idle_watts_fallback']
        mode = cfg['power_source_mode']

        if mode == 'model':
            self.last_measured_watts = self._read_model_watts(cpu_percent, idle_fallback)
            return self.last_measured_watts, 'model'

        if mode == 'power_supply':
            ps_w = self._read_power_supply_watts()
            if ps_w is not None:
                self.last_measured_watts = ps_w
                return ps_w, 'power_supply'
            rapl_w = self._read_rapl_watts(now, base_overhead, psu_eff)
            if rapl_w is not None:
                return rapl_w, 'rapl'
        elif mode == 'rapl':
            rapl_w = self._read_rapl_watts(now, base_overhead, psu_eff)
            if rapl_w is not None:
                return rapl_w, 'rapl'
        else:  # 'auto'
            rapl_w = self._read_rapl_watts(now, base_overhead, psu_eff)
            if rapl_w is not None:
                return rapl_w, 'rapl'
            ps_w = self._read_power_supply_watts()
            if ps_w is not None:
                self.last_measured_watts = ps_w
                return ps_w, 'power_supply'

        self.last_measured_watts = self._read_model_watts(cpu_percent, idle_fallback)
        return self.last_measured_watts, 'model'


POWER_READER = HardwarePowerReader()


def _build_power_payload(kwh_used, watts_now, source):
    cfg = _get_energy_settings()
    tariff = cfg['tariff_per_kwh']
    est_cost = round(float(kwh_used) * tariff, max(2, cfg['decimals']))
    payload = {
        'kwh': f"{float(kwh_used):.4f}",
        'watts_est': round(float(watts_now), 1),
        'source': source,
        'currency_symbol': cfg['currency_symbol'],
        'currency_code': cfg['currency_code'],
        'locale': cfg['locale'],
        'decimals': cfg['decimals'],
        'tariff_per_kwh': tariff,
        'estimated_cost': est_cost,
        'base_overhead_watts': cfg['base_overhead_watts'],
        'psu_efficiency': cfg['psu_efficiency'],
        'power_source_mode': cfg['power_source_mode'],
    }
    bat = POWER_READER.get_battery_info()
    if bat:
        payload['battery'] = bat
    return payload


# LICENSE FILE
LICENSE_FILE = os.path.join(DATA_DIR, 'license.lic')
IS_ACTIVATED = False  # Cache validation status

# Update Check URL (Administrator configurable via ENV UPDATE_URL)
CURRENT_VERSION = APP_VERSION


def energy_monitor_loop():
    global TOTAL_KWH, CURRENT_WATTS, POWER_SOURCE
    # Load initial
    try:
        if os.path.exists(ENERGY_FILE):
            with open(ENERGY_FILE, 'r') as f:
                data = json.load(f)
                TOTAL_KWH = float(data.get('kwh', 0.0))
    except Exception:
        pass

    last_save_time = time.time()
    last_loop_time = time.time()

    while True:
        try:
            now = time.time()
            dt = now - last_loop_time
            last_loop_time = now

            watts, source = POWER_READER.read_power()
            CURRENT_WATTS = watts
            POWER_SOURCE = source

            if 0 < dt < 10:
                TOTAL_KWH += (watts * dt) / 3600000.0

            if now - last_save_time >= 60:
                last_save_time = now
                try:
                    with open(ENERGY_FILE, 'w') as f:
                        json.dump({
                            'kwh': TOTAL_KWH,
                            'last_watts': CURRENT_WATTS,
                            'source': POWER_SOURCE,
                            'updated_at': int(now)
                        }, f)
                except Exception:
                    pass

            time.sleep(1)
        except Exception:
            time.sleep(1)


# Start Energy Thread
t_energy = threading.Thread(target=energy_monitor_loop, daemon=True)
t_energy.start()
try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

# MQTT Global State
mqtt_client = None
HOME_DEVICES_STATE = {}

def _get_persistent_secret_key():
    """Memuat atau mengenerate SECRET_KEY persisten agar sesi tidak ter-reset tiap restart."""
    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key
    cfg_file = os.path.join(DATA_DIR, 'config.json')
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, 'r') as f:
                saved = json.load(f)
                if isinstance(saved, dict) and saved.get('secret_key'):
                    return saved['secret_key']
        except Exception:
            pass
    key = os.urandom(24).hex()
    try:
        saved = {}
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file, 'r') as f:
                    saved = json.load(f)
            except Exception:
                saved = {}
        if not isinstance(saved, dict):
            saved = {}
        saved['secret_key'] = key
        with open(cfg_file, 'w') as f:
            json.dump(saved, f, indent=2)
    except Exception:
        pass
    return key

app = Flask(__name__)
app.config['SECRET_KEY'] = _get_persistent_secret_key()
app.config['UPLOAD_FOLDER'] = DATA_DIR
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB Limit
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.jinja_env.auto_reload = True

# ==============================================
_raw_cors_origins = [o.strip() for o in (os.environ.get('CORS_ALLOWED_ORIGINS') or '').split(',') if o.strip()]
if _raw_cors_origins:
    CORS(app, resources={r"/*": {"origins": _raw_cors_origins}}, supports_credentials=True)
    socketio = SocketIO(app, cors_allowed_origins=_raw_cors_origins, async_mode='eventlet')
else:
    CORS(app, resources={r"/*": {"origins": []}}, supports_credentials=True)
    socketio = SocketIO(app, cors_allowed_origins=None, async_mode='eventlet')

# Terminal sessions storage
terminal_sessions = {}

# Active user sessions tracking (server-side)
# Format: {session_id: {username, login_time, last_activity, ip, role}}
ACTIVE_SESSIONS = {}

# ============== ROLE-BASED ACCESS CONTROL ==============
# Role hierarchy: owner > admin > operator > readonly
ROLES = ['owner', 'admin', 'operator', 'readonly']

# Permission definitions per role
PERMISSIONS = {
    'owner': {
        'dashboard': True, 'metrics': True, 'monitoring': True,
        'files': 'full',           # full = read/write/delete
        'terminal': True,
        'docker': 'full',          # full = view/start/stop/restart/delete
        'security': 'full',        # full = all settings
        'users': 'full',           # full = add/edit/delete any user
        'audit_logs': 'full',      # full = view/clear
        'active_sessions': True,   # view + force logout others
        'security_policy': True,   # change global policy
        'services': 'full',        # full = view/start/stop/restart
        'settings': 'full',        # full = all app settings
        'adblocker': 'full'
    },
    'admin': {
        'dashboard': True, 'metrics': True, 'monitoring': True,
        'files': 'full',
        'terminal': True,
        'docker': 'full',
        'security': 'view',        # view only
        'users': 'limited',        # can manage operator/readonly, NOT owner/admin
        'audit_logs': 'view',      # view only, cannot clear
        'active_sessions': True,
        'security_policy': False,
        'services': 'full',
        'settings': 'full',
        'adblocker': 'full'
    },
    'operator': {
        'dashboard': True, 'metrics': True, 'monitoring': True,
        'files': 'read',           # read only
        'terminal': False,
        'docker': 'view',          # view + restart only
        'security': False,
        'users': False,
        'audit_logs': False,
        'active_sessions': False,
        'security_policy': False,
        'services': 'limited',     # view + restart whitelisted
        'settings': 'view',
        'adblocker': 'view'
    },
    'readonly': {
        'dashboard': True, 'metrics': True, 'monitoring': True,
        'files': 'read',           # read only
        'terminal': False,
        'docker': 'view',          # view only, no actions
        'security': 'view',        # view only
        'users': False,
        'audit_logs': False,
        'active_sessions': False,
        'security_policy': False,
        'services': 'view',        # view only
        'settings': 'view',
        'adblocker': 'view'
    }
}

def has_permission(role, feature, level='any'):
    """Check if a role has permission for a feature
    level: 'any' (any access), 'full', 'view', 'limited', True
    """
    if role not in PERMISSIONS:
        return False
    perm = PERMISSIONS[role].get(feature, False)
    if level == 'any':
        return bool(perm)
    return perm == level or perm == 'full' or perm == True

def get_role_level(role):
    """Get numeric level of role (lower = more powerful)"""
    try:
        return ROLES.index(role)
    except ValueError:
        return 999  # Unknown role = no power


# Configuration Files
# Configuration Files
SECURITY_CONFIG_FILE = os.path.join(DATA_DIR, 'security_config.json')
AUDIT_LOG_FILE = os.path.join(DATA_DIR, 'audit.log')
LOGIN_ATTEMPTS_FILE = os.path.join(DATA_DIR, 'login_attempts.json')
APP_SETTINGS_FILE = os.path.join(DATA_DIR, 'app_settings.json')

# ============ AUTO-DETECT DEVICE NAME ============
_STALE_SERVER_NAMES = {
    'amlogic server',
    'my server',
    'my dashboard',
}


def _read_host_text(path):
    """Read a sysfs/procfs node, stripping NUL bytes and whitespace."""
    try:
        with open(path, 'rb') as f:
            raw = f.read().strip(b'\x00 \t\r\n')
        val = raw.decode('utf-8', errors='ignore').strip()
        return val or None
    except Exception:
        return None


def _looks_like_sku(s):
    """Heuristic for OEM machine codes like '10MR000XGE' / '82K2001BID'."""
    if not s:
        return False
    if any(ch.islower() or ch.isspace() or ch in '._:/,()' for ch in s):
        return False
    return bool(re.fullmatch(r'[A-Z0-9][A-Z0-9\-]{3,}', s)) and any(ch.isdigit() for ch in s)


def _clean_vendor(v):
    """Tidy a DMI vendor string ('LENOVO' -> 'Lenovo')."""
    if not v:
        return None
    v = v.strip()
    if v.isupper():
        v = v.title()
    v = re.sub(r'\s+(inc|corp|corporation|co|ltd|llc|computer inc|technologies|gmbh)\.?$', '', v, flags=re.I).strip()
    v = v.replace('ASUSTeK', 'ASUS').replace('asustek', 'ASUS').replace('Gigabyte Technology', 'Gigabyte')
    return v or None


def detect_device_name():
    """Auto-detect a human-friendly device/model name.

    Honors the HOST_SYS / HOST_PROC mounts from docker-compose.yml so it
    works inside the container (privileged + /sys and /proc mounted ro).
    """
    host_sys = os.environ.get('HOST_SYS', '/sys')
    host_proc = os.environ.get('HOST_PROC', '/proc')

    # 1) ARM / embedded boards expose their model via device-tree
    dt_paths = [
        os.path.join(host_sys, 'firmware', 'devicetree', 'base', 'model'),
        os.path.join(host_proc, 'device-tree', 'model'),
        '/proc/device-tree/model',
    ]
    for p in dt_paths:
        model = _read_host_text(p)
        if model:
            return model

    # 2) Standard x86 PCs via DMI sysfs
    dmi = os.path.join(host_sys, 'class', 'dmi', 'id')
    vendor = _clean_vendor(_read_host_text(os.path.join(dmi, 'sys_vendor')))
    product_name = _read_host_text(os.path.join(dmi, 'product_name'))
    product_version = _read_host_text(os.path.join(dmi, 'product_version'))
    product_family = _read_host_text(os.path.join(dmi, 'product_family'))
    board_name = _read_host_text(os.path.join(dmi, 'board_name'))

    def _usable(s):
        if not s:
            return None
        s = s.strip()
        if s.lower() in (
            'not specified', 'unknown', 'to be filled by o.e.m.', 'default string',
            'o.e.m.', 'system product name', 'system version', 'none', 'standard',
            'to be filled by oem',
        ):
            return None
        return s

    name = _usable(product_name)
    version = _usable(product_version)
    family = _usable(product_family)
    board = _usable(board_name)

    # Prefer the friendly model string, skip OEM SKU codes like '10MR000XGE'
    model = None
    if name and not _looks_like_sku(name):
        model = name
    elif version:
        model = version
    elif family:
        model = family
    elif name:
        model = name
    elif board:
        model = board

    if model:
        if vendor and vendor.lower() not in model.lower():
            return (vendor + ' ' + model).strip()
        return model

    # 3) Fallback to hostname
    try:
        hn = socket.gethostname() or platform.node()
    except Exception:
        hn = None
    return hn or 'Eka Dashboard Server'


def load_app_settings():
    default_settings = {
        'general': {
            'server_name': detect_device_name(),
            'timezone': 'Asia/Jakarta',
            'time_format': '24h',
            'date_format': 'DD/MM/YYYY'
        },
        'appearance': {
            'accent_color': 'blue',
            'density': 'comfortable',
            'visible_cards': ['cpu', 'ram', 'disk', 'network', 'docker']
        },
        'monitoring': {
            'wallboard_interval': 2000,
            'metrics_interval': 5000,
            'metrics_history_minutes': 60,
            'default_page': 'dashboard'
        },
        'alerts': {
            'enabled': True,
            'cpu_warning': 70,
            'cpu_critical': 90,
            'ram_warning': 70,
            'ram_critical': 90,
            'disk_warning': 80,
            'disk_critical': 95
        },
        'integrations': {
            'telegram_enabled': False,
            'telegram_token': '',
            'telegram_chat_id': '',
            'webhook_enabled': False,
            'webhook_url': ''
        },
        'services': [
            {'id': 'ssh', 'name': 'SSH Server'},
            {'id': 'docker', 'name': 'Docker Engine'},
            {'id': 'cron', 'name': 'Cron Job'},
            {'id': 'gunicorn', 'name': 'Gunicorn Service'},
            {'id': 'python-app', 'name': 'Python App Service'}
        ],
        'mqtt': {
            'enabled': False,
            'broker': '',
            'port': 1883,
            'devices': []
        },
        'energy': dict(DEFAULT_ENERGY_SETTINGS),
        'modules': dict(DEFAULT_MODULE_SETTINGS),
    }
    try:
        if os.path.exists(APP_SETTINGS_FILE):
            with open(APP_SETTINGS_FILE, 'r') as f:
                saved = json.load(f)
                # Deep merge
                for key in default_settings:
                    if key in saved:
                        if isinstance(default_settings[key], dict):
                            default_settings[key] = {**default_settings[key], **saved[key]}
                        else:
                            default_settings[key] = saved[key]
    except Exception as e:
        print(f"!!! CRITICAL: Failed to load settings file: {e}")

    # Auto-detect device name: override empty/stale defaults so every install
    # shows its real device (e.g. 'Linux Bare-Metal Server') automatically.
    general = default_settings.get('general') or {}
    server_name = (general.get('server_name') or '').strip()
    if not server_name or server_name.lower() in _STALE_SERVER_NAMES:
        general['server_name'] = detect_device_name()
        default_settings['general'] = general

    # Normalize energy calibration & optional module visibility settings
    default_settings['energy'] = _sanitize_energy_settings(default_settings.get('energy'))
    default_settings['modules'] = _sanitize_module_settings(default_settings.get('modules'))

    return default_settings

def save_app_settings(settings):
    with open(APP_SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)
    _invalidate_energy_cache()
    _invalidate_modules_cache()

def load_security_config():
    default_config = {
        'username': 'admin',
        'password_hash': hashlib.sha256('admin'.encode()).hexdigest(),
        'role': 'owner',  # Default to owner for main user
        'session_timeout': 3600,
        'require_auth': True,
        'allowed_ips': [],
        'max_login_attempts': 5,
        'lockout_duration': 300,  # 5 minutes
        'users': []
    }
    try:
        if os.path.exists(SECURITY_CONFIG_FILE):
            with open(SECURITY_CONFIG_FILE, 'r') as f:
                config = {**default_config, **json.load(f)}
                
                # Auto-migration: Main user MUST be owner
                if config.get('role') != 'owner':
                    config['role'] = 'owner'
                    # Save back to disk immediately to persist migration
                    try:
                        save_security_config(config)
                    except:
                        pass
                
                return config
    except:
        pass
    return default_config

def save_security_config(config):
    with open(SECURITY_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def load_login_attempts():
    try:
        if os.path.exists(LOGIN_ATTEMPTS_FILE):
            with open(LOGIN_ATTEMPTS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_login_attempts(attempts):
    with open(LOGIN_ATTEMPTS_FILE, 'w') as f:
        json.dump(attempts, f)

def check_login_locked(ip):
    """Check if IP is locked out due to too many failed attempts"""
    config = load_security_config()
    attempts = load_login_attempts()
    
    if ip in attempts:
        data = attempts[ip]
        if data.get('locked_until', 0) > time.time():
            return True, int(data['locked_until'] - time.time())
    return False, 0

def record_login_attempt(ip, success):
    """Record login attempt and lock if too many failures"""
    config = load_security_config()
    attempts = load_login_attempts()
    
    if success:
        # Clear attempts on success
        if ip in attempts:
            del attempts[ip]
    else:
        # Increment failed attempts
        if ip not in attempts:
            attempts[ip] = {'count': 0, 'locked_until': 0}
        attempts[ip]['count'] = attempts[ip].get('count', 0) + 1
        
        # Lock if exceeded max attempts
        max_attempts = config.get('max_login_attempts', 5)
        if attempts[ip]['count'] >= max_attempts:
            lockout = config.get('lockout_duration', 300)
            attempts[ip]['locked_until'] = time.time() + lockout
            audit_log('ACCOUNT_LOCKED', f"IP {ip} locked for {lockout}s after {max_attempts} failed attempts")
    
    save_login_attempts(attempts)

def audit_log(action, details='', user='system'):
    try:
        # Ensure data directory exists
        os.makedirs(os.path.dirname(AUDIT_LOG_FILE), exist_ok=True)
        
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        try:
            ip = request.remote_addr if request else 'N/A'
        except:
            ip = 'N/A'
        log_entry = f"{timestamp} | {user} | {ip} | {action} | {details}\n"
        with open(AUDIT_LOG_FILE, 'a') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"[AUDIT ERROR] Failed to write log: {e}")
        pass

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        config = load_security_config()
        
        # 1. Global Authentication Toggle
        if not config.get('require_auth', True):
            session['logged_in'] = True
            session['role'] = 'admin'
            return f(*args, **kwargs)

        # 2. Check Session
        if session.get('logged_in'):
            # Check timeout
            last_active = session.get('last_active', time.time())
            timeout = config.get('session_timeout', 3600)
            if time.time() - last_active > timeout:
                session.clear()
                audit_log('SESSION_EXPIRED', f"User session expired after {timeout}s")
                if request.is_json:
                    return jsonify({'error': 'Session expired'}), 401
                return redirect(url_for('login_page'))
            
            session['last_active'] = time.time()
            return f(*args, **kwargs)

        # 3. Require Login
        if request.is_json:
            return jsonify({'error': 'Authentication required'}), 401
        return redirect(url_for('login_page'))
    return decorated_function

def owner_required(f):
    """Decorator: Only owner can access"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'owner':
            audit_log('ACCESS_DENIED', f"Non-owner tried to access {request.path}", session.get('username'))
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Owner access required'}), 403
            return redirect(url_for('dashboard', error='access_denied', feature='owner_required'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator: Owner or Admin can access"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        role = session.get('role', 'readonly')
        if role not in ['owner', 'admin']:
            audit_log('ACCESS_DENIED', f"Insufficient role ({role}) for {request.path}", session.get('username'))
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Admin access required'}), 403
            return redirect(url_for('dashboard', error='access_denied', feature='admin_required'))
        return f(*args, **kwargs)
    return decorated_function

def operator_required(f):
    """Decorator: Owner, Admin, or Operator can access"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        role = session.get('role', 'readonly')
        if role not in ['owner', 'admin', 'operator']:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Operator access required'}), 403
            return redirect(url_for('dashboard', error='access_denied', feature='operator_required'))
        return f(*args, **kwargs)
    return decorated_function

def requires_permission(feature, level='any'):
    """Decorator factory: Check if user has permission for a feature"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            role = session.get('role', 'readonly')
            if not has_permission(role, feature, level):
                audit_log('PERMISSION_DENIED', f"Role {role} denied {feature} ({level})", session.get('username'))
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': f'No permission for {feature}'}), 403
                return redirect(url_for('dashboard', error='access_denied', feature=feature))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --------------------------




def get_size(bytes, suffix="B"):
    """Scale bytes to its proper format"""
    factor = 1024
    for unit in ["", "K", "M", "G", "T", "P"]:
        if bytes < factor:
            return f"{bytes:.2f}{unit}{suffix}"
        bytes /= factor

# Auth Routes
@app.route('/login', methods=['GET'])
def login_page():
    # If setup hasn't been completed, force setup wizard
    try:
        config = load_security_config()
        default_hash = hashlib.sha256('admin'.encode()).hexdigest()
        if config['password_hash'] == default_hash:
            return redirect('/setup-admin')
    except Exception:
        return redirect('/setup-admin')

    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/setup-admin')
def setup_admin_page():
    return render_template('setup_admin.html')

@app.route('/api/setup-admin', methods=['POST'])
def setup_admin_api():
    config = load_security_config()
    default_hash = hashlib.sha256('admin'.encode()).hexdigest()
    
    # Allow setup if password is default OR session setup_mode is active
    if config['password_hash'] != default_hash and not session.get('setup_mode'):
        # If already setup, forbid unless valid admin login? No, just forbid.
        return jsonify({'error': 'Setup already completed'}), 403
        
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password or len(password) < 4:
        return jsonify({'error': 'Invalid input (min 4 chars)'}), 400
        
    # Update config - first user is always 'owner'
    config['username'] = username
    config['password_hash'] = hashlib.sha256(password.encode()).hexdigest()
    config['role'] = 'owner'
    save_security_config(config)
    
    # Auto Login
    ip = request.remote_addr
    session['logged_in'] = True
    session['username'] = username
    session['role'] = 'owner'
    session['login_time'] = time.time()
    session['session_id'] = hashlib.md5(f"{username}{time.time()}{ip}".encode()).hexdigest()[:16]
    session.pop('setup_mode', None) # Clear flag
    
    # Register in active sessions
    ACTIVE_SESSIONS[session['session_id']] = {
        'username': username,
        'role': 'owner',
        'login_time': session['login_time'],
        'last_activity': session['login_time'],
        'ip': ip
    }
    
    return jsonify({'success': True})

@app.route('/api/auth/login', methods=['POST'])
def login_api():
    ip = request.remote_addr
    
    # Check if locked out
    locked, remaining = check_login_locked(ip)
    if locked:
        return jsonify({'error': f'Too many failed attempts. Try again in {remaining}s'}), 429
    
    config = load_security_config()
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # Check main user
    if username == config['username'] and password_hash == config['password_hash']:
        session['logged_in'] = True
        session['username'] = username
        session['role'] = config.get('role', 'admin')
        session['login_time'] = time.time()
        session['session_id'] = hashlib.md5(f"{username}{time.time()}{ip}".encode()).hexdigest()[:16]
        
        # Register in active sessions
        ACTIVE_SESSIONS[session['session_id']] = {
            'username': username,
            'role': session['role'],
            'login_time': session['login_time'],
            'last_activity': session['login_time'],
            'ip': ip
        }
        
        record_login_attempt(ip, True)
        audit_log('LOGIN_SUCCESS', f"User {username} logged in (role: {session['role']})", username)
        return jsonify({'success': True, 'role': session['role']})
    
    # Check additional users
    for user in config.get('users', []):
        if username == user.get('username') and password_hash == user.get('password_hash'):
            session['logged_in'] = True
            session['username'] = username
            session['role'] = user.get('role', 'readonly')
            session['login_time'] = time.time()
            session['session_id'] = hashlib.md5(f"{username}{time.time()}{ip}".encode()).hexdigest()[:16]
            
            # Register in active sessions
            ACTIVE_SESSIONS[session['session_id']] = {
                'username': username,
                'role': session['role'],
                'login_time': session['login_time'],
                'last_activity': session['login_time'],
                'ip': ip
            }
            
            record_login_attempt(ip, True)
            audit_log('LOGIN_SUCCESS', f"User {username} logged in (role: {session['role']})", username)
            return jsonify({'success': True, 'role': session['role']})
    
    # Failed login
    record_login_attempt(ip, False)
    audit_log('LOGIN_FAILED', f"Failed login attempt for user {username}")
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def logout_api():
    user = session.get('username', 'unknown')
    session_id = session.get('session_id')
    
    # Remove from active sessions
    if session_id and session_id in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[session_id]
    
    session.clear()
    audit_log('LOGOUT', f"User {user} logged out")
    return jsonify({'success': True})

# Public Monitoring Page - redirects to setup on first install
@app.route('/')
def monitoring_page():
    try:
        config = load_security_config()
        default_hash = hashlib.sha256('admin'.encode()).hexdigest()
        if config['password_hash'] == default_hash:
            return redirect('/setup-admin')
    except Exception:
        return redirect('/setup-admin')
    return render_template('monitoring.html')

# Admin Dashboard (requires login)
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('index.html')


@app.route('/api/stats')
@login_required
def stats():
    # CPU
    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_count = psutil.cpu_count(logical=True)
    try:
        load_avg = psutil.getloadavg() # (1, 5, 15)
    except:
        load_avg = (0, 0, 0)
    
    # Memory
    svmem = psutil.virtual_memory()
    mem_percent = svmem.percent
    mem_used = get_size(svmem.used)
    mem_total = get_size(svmem.total)
    
    # Linux specific memory details
    mem_cached = 0
    mem_buffers = 0
    if hasattr(svmem, 'cached'): mem_cached = get_size(svmem.cached)
    if hasattr(svmem, 'buffers'): mem_buffers = get_size(svmem.buffers)
    
    # Disk
    path = "/"
    if platform.system() == "Windows":
        path = "C:\\"
    
    disk_usage = psutil.disk_usage(path)
    disk_percent = disk_usage.percent
    disk_used = get_size(disk_usage.used)
    disk_free = get_size(disk_usage.free)
    disk_total = get_size(disk_usage.total)
    
    # Network
    net_io = psutil.net_io_counters()
    # Send raw bytes for speed calc on frontend
    sent = net_io.bytes_sent 
    recv = net_io.bytes_recv

    # Power Telemetry (Synced with Hardware RAPL & Energy Engine)
    uptime_seconds = int(time.time() - psutil.boot_time())
    try:
        avg_watts = CURRENT_WATTS if CURRENT_WATTS > 0 else POWER_READER.read_power(cpu_percent)[0]
        kwh_used = TOTAL_KWH
    except Exception as e:
        print(f"Energy calc error: {e}")
        avg_watts = 0.0
        kwh_used = 0.0

    # Temperature
    temps = psutil.sensors_temperatures()
    cpu_temp = 0
    if temps:
        # Common keys for arm/linux
        for name in ['cpu_thermal', 'soc_thermal', 'coretemp', 'thermal_zone0']:
             if name in temps:
                 cpu_temp = temps[name][0].current
                 break
        # Fallback
        if cpu_temp == 0 and len(temps) > 0:
             first_key = list(temps.keys())[0]
             cpu_temp = temps[first_key][0].current

    return jsonify({
        "cpu": {
            "percent": cpu_percent,
            "temp": cpu_temp,
            "cores": cpu_count,
            "load_1": load_avg[0],
            "load_5": load_avg[1],
            "load_15": load_avg[2]
        },
        "memory": {
            "percent": mem_percent,
            "used": mem_used,
            "total": mem_total,
            "cached": mem_cached,
            "buffers": mem_buffers
        },
        "disk": {
            "percent": disk_percent,
            "used": disk_used,
            "free": disk_free,
            "total": disk_total,
            "partition": path
        },
        "network": {
            "sent": sent,
            "recv": recv
        },
        "power": _build_power_payload(kwh_used, avg_watts, POWER_SOURCE),
        "uptime": uptime_seconds
    })

@app.route('/metrics')
def metrics_page():
    return render_template('metrics.html')

@app.route('/api/metrics')
def metrics_api():
    """Comprehensive metrics for the Metrics page"""
    
    # CPU per core
    cpu_percent_total = psutil.cpu_percent(interval=None)
    cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
    cpu_count = psutil.cpu_count(logical=True)
    try:
        load_avg = psutil.getloadavg()
    except:
        load_avg = (0, 0, 0)
    
    # Temperature
    temps = psutil.sensors_temperatures()
    cpu_temp = 0
    if temps:
        for name in ['cpu_thermal', 'soc_thermal', 'coretemp', 'thermal_zone0']:
            if name in temps:
                cpu_temp = temps[name][0].current
                break
        if cpu_temp == 0 and len(temps) > 0:
            first_key = list(temps.keys())[0]
            cpu_temp = temps[first_key][0].current
    
    # Memory
    svmem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    # Disk partitions
    partitions = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            partitions.append({
                'device': part.device,
                'mountpoint': part.mountpoint,
                'fstype': part.fstype,
                'total': usage.total,
                'used': usage.used,
                'free': usage.free,
                'percent': usage.percent
            })
        except:
            pass
    
    # Disk I/O
    disk_io = psutil.disk_io_counters()
    
    # Network
    net_io_total = psutil.net_io_counters()
    net_io_per_if = psutil.net_io_counters(pernic=True)
    net_interfaces = []
    for iface, stats in net_io_per_if.items():
        if iface != 'lo':  # Skip loopback
            net_interfaces.append({
                'name': iface,
                'bytes_sent': stats.bytes_sent,
                'bytes_recv': stats.bytes_recv,
                'packets_sent': stats.packets_sent,
                'packets_recv': stats.packets_recv
            })
    
    # Process count
    process_count = len(list(psutil.process_iter()))
    
    # Docker summary
    docker_summary = {'running': 0, 'stopped': 0, 'total': 0}
    try:
        client = docker_sdk.from_env()
        containers = client.containers.list(all=True)
        docker_summary['total'] = len(containers)
        docker_summary['running'] = len([c for c in containers if c.status == 'running'])
        docker_summary['stopped'] = docker_summary['total'] - docker_summary['running']
    except:
        pass
    
    # Uptime
    uptime_seconds = int(time.time() - psutil.boot_time())
    
    # Power Telemetry (Hardware RAPL / Dynamic Model)
    cpu_inst = psutil.cpu_percent(interval=None) or 0
    watts_now = CURRENT_WATTS if CURRENT_WATTS > 0 else POWER_READER.read_power(cpu_inst)[0]

    return jsonify({
        'power': _build_power_payload(TOTAL_KWH, watts_now, POWER_SOURCE),
        'cpu': {
            'percent': cpu_percent_total,
            'per_core': cpu_per_core,
            'cores': cpu_count,
            'temp': cpu_temp,
            'load_1': load_avg[0],
            'load_5': load_avg[1],
            'load_15': load_avg[2]
        },
        'memory': {
            'total': svmem.total,
            'available': svmem.available,
            'used': svmem.used,
            'percent': svmem.percent,
            'cached': getattr(svmem, 'cached', 0),
            'buffers': getattr(svmem, 'buffers', 0)
        },
        'swap': {
            'total': swap.total,
            'used': swap.used,
            'percent': swap.percent
        },
        'disk': {
            'partitions': partitions,
            'io': {
                'read_bytes': disk_io.read_bytes if disk_io else 0,
                'write_bytes': disk_io.write_bytes if disk_io else 0,
                'read_count': disk_io.read_count if disk_io else 0,
                'write_count': disk_io.write_count if disk_io else 0
            }
        },
        'network': {
            'sent': net_io_total.bytes_sent,
            'recv': net_io_total.bytes_recv,
            'interfaces': net_interfaces
        },

        'processes': process_count,
        'docker': docker_summary,
        'uptime': uptime_seconds,
        'timestamp': int(time.time() * 1000)
    })

@app.route('/api/processes')
@login_required
def processes():
    # Get all running processes
    procs = []
    for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info']):
        try:
            pinfo = proc.info
            # Calculate memory in MB
            mem_mb = pinfo['memory_info'].rss / (1024 * 1024)
            procs.append({
                'pid': pinfo['pid'],
                'name': pinfo['name'],
                'user': pinfo['username'],
                'cpu': pinfo['cpu_percent'],
                'mem_mb': round(mem_mb, 2)
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    # Sort by CPU usage by default
    procs.sort(key=lambda x: x['cpu'], reverse=True)
    return jsonify(procs[:50]) # Return top 50 to avoid overhead

@app.route('/api/disk-analysis')
@login_required
def disk_analysis():
    def get_du(path):
        try:
            # Run du -h --max-depth=1 | sort -hr
            # Added timeout to prevent hanging on large disks
            cmd = f"timeout 5s du -h --max-depth=1 {path} 2>/dev/null | sort -hr | head -n 10"
            result = subprocess.check_output(cmd, shell=True).decode('utf-8')
            items = []
            for line in result.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) == 2:
                    items.append({'size': parts[0], 'path': parts[1]})
            return items
        except subprocess.CalledProcessError:
            return [{'size': 'N/A', 'path': 'Timeout or Access Denied'}]
        except Exception as e:
            return [{'size': 'Error', 'path': str(e)}]

    # Analyze key directories
    # User requested to focus only on logs
    var_logs = get_du('/var/log')
    
    # Try to find zram1 mount point
    zram1_path = None
    try:
        with open('/proc/mounts', 'r') as f:
            for line in f:
                if 'zram1' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        zram1_path = parts[1]
                        break
    except:
        pass

    zram1_data = []
    if zram1_path:
        zram1_data = get_du(zram1_path)
    
    return jsonify({
        'logs': var_logs,
        'zram1': {'path': zram1_path, 'data': zram1_data}
    })

@app.route('/api/network-ports')
@login_required
def network_ports():
    connections = []
    try:
        # Requires root usually for full details
        for conn in psutil.net_connections(kind='inet'):
            if conn.status == 'LISTEN':
                pid = conn.pid
                program = "Unknown"
                path = "N/A"
                if pid:
                    try:
                        proc = psutil.Process(pid)
                        program = proc.name()
                        try:
                            path = proc.exe()
                        except:
                            path = "Access Denied"

                        # Improve details for Python processes
                        try:
                            cmdline = proc.cmdline()
                            if cmdline and len(cmdline) > 1 and 'python' in program:
                                # The script is usually the second argument (index 1)
                                script_path = cmdline[1]
                                path = script_path # Set path to the script, not the python binary
                                
                                # Custom names
                                if 'backend_webserver/app.py' in script_path:
                                    program = 'web_dashboard'
                                else:
                                    # Use filename as program name for other python scripts
                                    program = script_path.split('/')[-1]
                        except:
                            pass
                    except:
                        pass
                
                connections.append({
                    'port': conn.laddr.port,
                    'ip': conn.laddr.ip,
                    'pid': pid,
                    'program': program,
                    'path': path
                })
        
        # Sort by port
        connections.sort(key=lambda x: x['port'])
    except Exception as e:
        return jsonify({'error': str(e)})
        
    return jsonify(connections)

@app.route('/api/network-details')
@login_required
def network_details():
    interfaces = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    
    for name, snics in addrs.items():
        ip = "N/A"
        for snic in snics:
            if snic.family == socket.AF_INET:
                ip = snic.address
                break
        
        is_up = "Down"
        if name in stats and stats[name].isup:
            is_up = "Up"
            
        interfaces.append({
            'name': name,
            'ip': ip,
            'status': is_up
        })
        
    return jsonify(interfaces)

@app.route('/api/system')
@login_required
def system_info():
    uname = platform.uname()
    
    # Try getting better CPU name on Linux
    cpu_name = uname.processor
    try:
        if platform.system() == "Linux":
            command = "cat /proc/cpuinfo"
            output = subprocess.check_output(command, shell=True).decode().strip()
            for line in output.split('\n'):
                if "model name" in line:
                    cpu_name = line.split(':')[1].strip()
                    break
    except:
        pass

    return jsonify({
        "system": uname.system,
        "node": uname.node,
        "release": uname.release,
        "version": uname.version,
        "machine": uname.machine,
        "processor": cpu_name,
    })

# --- FILE MANAGER ROUTES ---
import os
import shutil

@app.route('/files')
@requires_permission('files', 'read')
def files_page():
    return render_template('files.html')

# --- FILE MANAGER PATH HELPERS ---
HOST_ROOT = os.environ.get('HOST_ROOT', '/host/root')

def _fm_to_container(path):
    """Map the user-facing (host) path to the real container path."""
    if not path:
        path = '/'
    if path == '/' or path == HOST_ROOT:
        return HOST_ROOT
    if path.startswith('/host/') or path.startswith(HOST_ROOT + '/'):
        return path
    return HOST_ROOT + path


def _fm_to_ui(path):
    """Map the container path back to the host path shown in the UI."""
    if path == HOST_ROOT:
        return '/'
    if path.startswith(HOST_ROOT + '/'):
        return path[len(HOST_ROOT):]
    return path


@app.route('/api/files/list', methods=['GET'])
@requires_permission('files', 'read')
def list_files():
    path = request.args.get('path', '/')
    page = int(request.args.get('page', 1))
    per_page = 10000

    real_path = _fm_to_container(path)
    if not os.path.isdir(real_path):
        return jsonify({'error': 'Path not found'}), 404

    try:
        # Use compiled C binary for Native Speed
        cmd = ["./file_lister", real_path, str(page), str(per_page)]
        result = subprocess.check_output(cmd, cwd=BASE_DIR).decode('utf-8')
        data = json.loads(result)
        data['current_path'] = _fm_to_ui(data.get('current_path', path))
        for item in data.get('items', []):
            item['path'] = _fm_to_ui(item.get('path', ''))
        return jsonify(data)
    except subprocess.CalledProcessError as e:
        return jsonify({'error': 'C Lister Failed: ' + str(e)}), 500
    except Exception as e:
        # Fallback to Python if binary fails or permission denied
        return jsonify({'error': str(e)}), 500


@app.route('/api/files/drives', methods=['GET'])
@requires_permission('files', 'read')
def get_drives():
    try:
        import psutil
        disks = []
        flat_drives = []

        # 1. Kumpulkan informasi disk fisik host via lsblk
        try:
            out = run_host_command(['lsblk', '-J', '-b', '-o', 'NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,TRAN,ROTA'])
            if out.returncode == 0 and out.stdout.strip():
                data = json.loads(out.stdout)
                for dev in data.get('blockdevices', []):
                    if dev.get('type') != 'disk':
                        continue
                    disk_name = dev.get('name')
                    model = (dev.get('model') or '').strip()
                    tran = (dev.get('tran') or ('nvme' if 'nvme' in disk_name else 'sata')).lower()
                    is_rotational = dev.get('rota', True)
                    is_ssd = (not is_rotational) or ('nvme' in disk_name.lower()) or ('ssd' in model.lower())

                    disk_type = 'SSD' if is_ssd else 'HDD'
                    disk_label = f"{disk_type} ({tran.upper()})" if tran else disk_type
                    size_bytes = dev.get('size') or 0
                    size_gb = round(size_bytes / (1024**3), 1)

                    partitions = []

                    def collect_parts(children):
                        for child in children:
                            mp = child.get('mountpoint')
                            if mp and not mp.startswith('/boot') and not mp.startswith('/snap'):
                                usage = None
                                try:
                                    c_path = _fm_to_container(mp)
                                    u = psutil.disk_usage(c_path)
                                    usage = {
                                        'total': u.total,
                                        'used': u.used,
                                        'free': u.free,
                                        'percent': u.percent
                                    }
                                except Exception:
                                    pass

                                label = 'System Root' if mp == '/' else ('User Home' if mp == '/home' else ('Data Storage' if mp == '/mnt/data' else mp))
                                c_name = child.get('name')
                                p_data = {
                                    'name': c_name,
                                    'device': f'/dev/{c_name}',
                                    'mountpoint': mp,
                                    'label': label,
                                    'fstype': child.get('fstype') or 'ext4',
                                    'size': child.get('size'),
                                    'usage': usage
                                }
                                partitions.append(p_data)

                                flat_drives.append({
                                    'mountpoint': mp,
                                    'device': f'/dev/{c_name}',
                                    'fstype': child.get('fstype') or 'ext4',
                                    'label': f"{disk_type}: {label}",
                                    'disk_id': disk_name,
                                    'disk_name': f"{disk_label} — {model}" if model else disk_label,
                                    'total': usage['total'] if usage else child.get('size'),
                                    'used': usage['used'] if usage else 0,
                                    'free': usage['free'] if usage else 0,
                                    'percent': usage['percent'] if usage else 0
                                })
                            if 'children' in child:
                                collect_parts(child['children'])

                    if 'children' in dev:
                        collect_parts(dev['children'])

                    if partitions:
                        total_used = sum(p['usage']['used'] for p in partitions if p.get('usage'))
                        total_cap = sum(p['usage']['total'] for p in partitions if p.get('usage')) or size_bytes
                        overall_percent = round((total_used / total_cap * 100), 1) if total_cap else 0

                        disks.append({
                            'id': disk_name,
                            'name': f"{disk_label} — {model}" if model else f"{disk_label} ({disk_name})",
                            'disk_type': disk_type,
                            'is_ssd': is_ssd,
                            'model': model,
                            'size': size_bytes,
                            'size_gb': size_gb,
                            'used_bytes': total_used,
                            'percent': overall_percent,
                            'partitions': partitions
                        })
        except Exception:
            pass

        # Urutkan SSD lebih dahulu baru HDD
        disks.sort(key=lambda d: 0 if d.get('is_ssd') else 1)

        # Fallback jika lsblk tidak tersedia
        if not disks:
            seen_devices = set()
            for part in psutil.disk_partitions(all=False):
                if 'loop' in part.device or 'snap' in part.mountpoint or 'overlay' in part.mountpoint:
                    continue
                if part.mountpoint in ('/etc/resolv.conf', '/etc/hostname', '/etc/hosts') or part.mountpoint.startswith('/boot'):
                    continue
                if part.device in seen_devices:
                    continue
                seen_devices.add(part.device)

                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    flat_drives.append({
                        'mountpoint': _fm_to_ui(part.mountpoint),
                        'device': part.device,
                        'fstype': part.fstype,
                        'total': usage.total,
                        'free': usage.free,
                        'used': usage.used,
                        'percent': usage.percent
                    })
                except Exception:
                    flat_drives.append({
                        'mountpoint': _fm_to_ui(part.mountpoint),
                        'device': part.device,
                        'fstype': part.fstype
                    })

        return jsonify({'physical_disks': disks, 'drives': flat_drives})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/action', methods=['POST'])
@requires_permission('files', 'full')
def file_action():
    data = request.json
    action = data.get('action')
    path = _fm_to_container(data.get('path'))
    
    try:
        if action == 'delete':
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        elif action == 'create_folder':
            os.makedirs(path, exist_ok=True)
        elif action == 'create_file':
            with open(path, 'w') as f:
                pass
        elif action == 'rename':
            new_path = data.get('new_path')
            if new_path:
                new_path = _fm_to_container(new_path)
            os.rename(path, new_path)
        elif action == 'paste':
            source = _fm_to_container(data.get('source'))
            dest = path # paste into this folder
            # Simple handling: copy raw
            base_name = os.path.basename(source)
            final_dest = os.path.join(dest, base_name)
            
            if data.get('operation') == 'cut':
                shutil.move(source, final_dest)
            else:
                if os.path.isdir(source):
                    shutil.copytree(source, final_dest)
                else:
                    shutil.copy2(source, final_dest)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/files/content', methods=['GET', 'POST'])
@login_required
def file_content():
    role = session.get('role', 'readonly')
    config = load_security_config()
    if config.get('require_auth', True):
        req_perm = 'full' if request.method == 'POST' else 'read'
        if not has_permission(role, 'files', req_perm):
            return jsonify({'error': 'Access denied'}), 403

    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        raw_path = (data.get('path') or '').strip()
        if not raw_path:
            return jsonify({'error': 'Path is required'}), 400
        path = _fm_to_container(raw_path)
        content = data.get('content')
        if content is None:
            return jsonify({'error': 'Content is required'}), 400
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(str(content))
            audit_log('FILES_WRITE', f"Modified {raw_path}", session.get('username'))
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # GET
    raw_path = (request.args.get('path') or '').strip()
    if not raw_path:
        return jsonify({'error': 'Path is required'}), 400
    path = _fm_to_container(raw_path)
    if not os.path.exists(path) or os.path.isdir(path):
        return jsonify({'error': 'File not found'}), 404

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            return jsonify({'content': content})
    except UnicodeDecodeError:
        return jsonify({'error': 'Binary or unsupported file type'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- TERMINAL ROUTES ---
@app.route('/terminal')
@requires_permission('terminal')
def terminal_page():
    return render_template('terminal.html')

def _terminal_socket_authorized():
    """Terminal lewat WebSocket harus tunduk pada aturan auth yang sama dengan /terminal."""
    try:
        config = load_security_config()
    except Exception:
        config = {}

    if not config.get('require_auth', True):
        return True

    if not session.get('logged_in'):
        return False

    return has_permission(session.get('role', 'readonly'), 'terminal', 'any')


_NSENTER_CAPABILITY = None


def _is_in_container():
    """Deteksi apakah proses berjalan di dalam container (Docker / Podman / OCI)."""
    return (
        os.path.exists('/.dockerenv')
        or os.path.exists('/run/.containerenv')
        or bool(os.environ.get('CONTAINER'))
    )


def _can_use_nsenter():
    """Gunakan nsenter ke PID 1 hanya bila di dalam container DAN memiliki kapabilitas root/privileged."""
    global _NSENTER_CAPABILITY
    if _NSENTER_CAPABILITY is not None:
        return _NSENTER_CAPABILITY
    if not _is_in_container():
        _NSENTER_CAPABILITY = False
        return False
    if os.geteuid() != 0:
        _NSENTER_CAPABILITY = False
        return False
    try:
        ok = subprocess.run(
            ['nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'true'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
        ).returncode == 0
        _NSENTER_CAPABILITY = ok
        return ok
    except Exception:
        _NSENTER_CAPABILITY = False
        return False


def _host_cmd_prefix(include_pid=False):
    """Mengembalikan prefix nsenter pada container privileged, atau [] saat berjalan native di host/VPS."""
    if _can_use_nsenter():
        flags = ['-t', '1', '-m', '-u', '-i', '-n']
        if include_pid:
            flags.append('-p')
        return ['nsenter'] + flags + ['--']
    return []


class _CmdResult:
    """Objek hasil eksekusi seragam untuk fallback timeout/error."""
    __slots__ = ('returncode', 'stdout', 'stderr')

    def __init__(self, returncode=1, stdout='', stderr=''):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _run_host_cmd(args, timeout=15, input_data=None, env=None, include_pid=True):
    """Eksekutor perintah host universal: otomatis nsenter (Docker) atau direct execution (Native/VPS)."""
    if not isinstance(args, list):
        args = [str(args)]
    cmd = _host_cmd_prefix(include_pid=include_pid) + args
    try:
        return subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )
    except subprocess.TimeoutExpired:
        return _CmdResult(124, '', f'Perintah timeout terlampaui ({timeout} detik)')
    except Exception as e:
        return _CmdResult(1, '', str(e))


def _get_target_host_user():
    """Deteksi user reguler utama host secara dinamis (ENV atau UID 1000)."""
    env_user = (os.environ.get('TERMINAL_USER') or os.environ.get('HOST_USER') or '').strip()
    if env_user:
        return env_user
    # Cek user reguler pertama (UID 1000) pada sistem host
    try:
        res = _run_host_cmd(['id', '-nu', '1000'], timeout=2, include_pid=False)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    # Fallback: cari user reguler pertama dari /etc/passwd host (UID >= 1000 & shell login valid)
    try:
        passwd_path = os.path.join(os.environ.get('HOST_ROOT', '/host/root'), 'etc', 'passwd')
        if not os.path.exists(passwd_path):
            passwd_path = '/etc/passwd'
        if os.path.exists(passwd_path):
            with open(passwd_path, 'r') as f:
                for line in f:
                    parts = line.strip().split(':')
                    if len(parts) >= 7 and parts[2].isdigit():
                        uid = int(parts[2])
                        shell = parts[6]
                        if 1000 <= uid < 65000 and not shell.endswith(('nologin', 'false')):
                            return parts[0]
    except Exception:
        pass
    return None


def _build_terminal_command(lxd_target=None, start_path=None, lxd_project=None):
    """Susun perintah shell interaktif bersih (Docker nsenter maupun Native Linux).

    Memakai interactive non-login shell (`bash -i`) agar `~/.bashrc` (alias, prompt warna,
    completion) tetap termuat namun melewati skrip login banner/MOTD di `/etc/profile.d/*`.
    """
    prefix = _host_cmd_prefix(include_pid=False)

    if lxd_target:
        lxc_cmd = ['lxc']
        if lxd_project and lxd_project != 'default':
            lxc_cmd += ['--project', lxd_project]
        lxc_cmd += ['exec', lxd_target, '--', 'bash', '-i']
        return prefix + lxc_cmd

    target_dir = start_path if (start_path and start_path not in ['/root', '/']) else ''
    cd_expr = f'cd {shlex.quote(target_dir)} 2>/dev/null || cd ~' if target_dir else 'cd ~'

    if _can_use_nsenter() or os.geteuid() == 0:
        target_user = _get_target_host_user()
        if target_user:
            q_user = shlex.quote(target_user)
            shell_cmd = (
                f'export HOME="$(getent passwd {q_user} | cut -d: -f6)"; '
                f'[ -z "$HOME" ] && HOME="/home/{target_user}"; '
                f'export USER={q_user} LOGNAME={q_user} '
                f'PATH="$HOME/.local/bin:$HOME/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"; '
                f'{cd_expr}; exec bash -i'
            )
            return prefix + ['runuser', '-u', target_user, '--', 'bash', '-c', shell_cmd]

        if target_dir:
            return prefix + ['bash', '-c', f'{cd_expr}; exec bash -i']
        return prefix + ['bash', '-i']

    # Fallback: shell lokal non-root (native user / dev)
    if target_dir:
        return ['bash', '-c', f'{cd_expr}; exec bash -i']
    return ['bash', '-i']


def _spawn_pty_session(session_id, cmd, output_event='terminal_output', extra_env=None, rows=None, cols=None):
    """Jalankan `cmd` di dalam PTY baru dan daftarkan sesinya.

    Dipakai oleh Web Terminal PTY supaya logika fork/PTY,
    pembersihan fd, dan pembacaan output hanya ada di satu tempat.
    Mengembalikan True bila proses berhasil di-fork.
    """
    master_fd, slave_fd = pty.openpty()

    # Apply initial winsize before fork so shell/ls/htop never start with 0x0 dimensions
    try:
        r = max(5, min(500, int(rows))) if rows else 24
        c = max(20, min(500, int(cols))) if cols else 80
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, struct.pack('HHHH', r, c, 0, 0))
    except Exception:
        pass

    pid = os.fork()
    if pid == 0:
        # Child process
        try:
            os.close(master_fd)
            os.setsid()
            try:
                fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
            except Exception:
                pass
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            if slave_fd > 2:
                os.close(slave_fd)

            os.environ['TERM'] = 'xterm-256color'
            os.environ['SHELL'] = '/bin/bash'
            for key, value in (extra_env or {}).items():
                os.environ[str(key)] = str(value)

            os.execvp(cmd[0], cmd)
        except Exception as e:
            # Tulis alasan gagal ke PTY supaya terlihat di browser, bukan mati senyap.
            try:
                os.write(2, f"\r\nGagal menjalankan proses ({cmd[0]}): {e}\r\n".encode())
            except Exception:
                pass
        os._exit(1)

    # Parent process
    os.close(slave_fd)
    owner_sid = getattr(request, 'sid', None) if request else None
    owner_user = session.get('username') if session else None
    terminal_sessions[session_id] = {
        'fd': master_fd,
        'pid': pid,
        'event': output_event,
        'sid': owner_sid,
        'user': owner_user,
    }
    socketio.start_background_task(read_terminal_output, session_id, master_fd, output_event, owner_sid)
    return True


def _terminal_session_owned(session_id):
    """Pastikan PTY session hanya bisa diakses oleh socket pemiliknya."""
    info = terminal_sessions.get(session_id)
    if not info:
        return False
    owner_sid = info.get('sid')
    cur_sid = getattr(request, 'sid', None)
    if owner_sid and cur_sid and owner_sid != cur_sid:
        return False
    return True


def _terminate_terminal_session(session_id):
    """Tutup PTY dan hentikan child process secara bersih."""
    sess_info = terminal_sessions.pop(session_id, None)
    if not sess_info:
        return
    try:
        os.close(sess_info['fd'])
    except Exception:
        pass
    try:
        os.kill(sess_info['pid'], 9)
    except Exception:
        pass
    try:
        os.waitpid(sess_info['pid'], 0)
    except Exception:
        pass


# WebSocket handlers for terminal
@socketio.on('start_terminal')
def handle_start_terminal(data):
    if pty is None or fcntl is None:
        emit('terminal_error', {'error': 'PTY tidak tersedia di platform ini'})
        return

    if not _terminal_socket_authorized():
        audit_log('ACCESS_DENIED', 'Unauthenticated start_terminal via WebSocket',
                  session.get('username'))
        emit('terminal_error', {'error': 'Authentication required'})
        return

    data = data or {}
    session_id = str(data.get('session_id') or 'default').strip()[:64]
    lxd_target = data.get('lxd_target')
    lxd_project = data.get('lxd_project')
    start_path = data.get('path')

    # Jangan izinkan socket lain membajak / membunuh sesi aktif milik pengguna berbeda
    if session_id in terminal_sessions:
        if not _terminal_session_owned(session_id):
            audit_log('ACCESS_DENIED', f'Cross-socket terminal hijack attempt ({session_id})',
                      session.get('username'))
            emit('terminal_error', {'error': 'Session ID sedang digunakan oleh sesi lain'})
            return
        _terminate_terminal_session(session_id)

    cmd = _build_terminal_command(lxd_target, start_path=start_path, lxd_project=lxd_project)
    _spawn_pty_session(session_id, cmd, rows=data.get('rows'), cols=data.get('cols'))
    emit('terminal_started', {'session_id': session_id})


def read_terminal_output(session_id, fd, output_event='terminal_output', target_sid=None):
    import eventlet
    while session_id in terminal_sessions and terminal_sessions[session_id].get('fd') == fd:
        eventlet.sleep(0.01)
        try:
            if select.select([fd], [], [], 0.1)[0]:
                data = os.read(fd, 4096)
                if not data:
                    break
                payload = {
                    'session_id': session_id,
                    'data': data.decode('utf-8', errors='replace')
                }
                if target_sid:
                    socketio.emit(output_event, payload, to=target_sid)
                else:
                    socketio.emit(output_event, payload)
        except Exception:
            break


@socketio.on('terminal_input')
def handle_terminal_input(data):
    if not _terminal_socket_authorized():
        emit('terminal_error', {'error': 'Authentication required'})
        return
    data = data or {}
    session_id = str(data.get('session_id') or 'default').strip()[:64]
    input_data = data.get('input', '')
    if not isinstance(input_data, str) or len(input_data) > 16384:
        return
    if not _terminal_session_owned(session_id):
        return

    fd = terminal_sessions[session_id]['fd']
    try:
        os.write(fd, input_data.encode('utf-8'))
    except Exception:
        pass


@socketio.on('terminal_resize')
def handle_terminal_resize(data):
    if not _terminal_socket_authorized():
        return
    data = data or {}
    session_id = str(data.get('session_id') or 'default').strip()[:64]
    if not _terminal_session_owned(session_id):
        return
    try:
        rows = max(5, min(500, int(data.get('rows', 24))))
        cols = max(20, min(500, int(data.get('cols', 80))))
    except (TypeError, ValueError):
        return

    fd = terminal_sessions[session_id]['fd']
    try:
        winsize = struct.pack('HHHH', rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
    except Exception:
        pass


@socketio.on('stop_terminal')
def handle_stop_terminal(data):
    if not _terminal_socket_authorized():
        return
    data = data or {}
    session_id = str(data.get('session_id') or 'default').strip()[:64]
    if not _terminal_session_owned(session_id):
        return
    _terminate_terminal_session(session_id)


@socketio.on('disconnect')
def handle_terminal_disconnect():
    """Bersihkan seluruh sesi PTY milik socket saat koneksi browser terputus."""
    cur_sid = getattr(request, 'sid', None)
    if not cur_sid:
        return
    owned_ids = [sid_key for sid_key, info in list(terminal_sessions.items()) if info.get('sid') == cur_sid]
    for sid_key in owned_ids:
        _terminate_terminal_session(sid_key)


# --- DOCKER ROUTES ---
import docker as docker_sdk

@app.route('/docker')
@requires_permission('docker', 'view')
def docker_page():
    return render_template('docker.html')

@app.route('/api/docker/containers')
@requires_permission('docker', 'view')
def docker_containers():
    try:
        client = docker_sdk.from_env()
        containers = client.containers.list(all=True)
        
        result = []
        for c in containers:
            # Extract first public port
            public_port = None
            if c.attrs['NetworkSettings']['Ports']:
                for p_int, p_bind in c.attrs['NetworkSettings']['Ports'].items():
                    if p_bind:
                        public_port = p_bind[0]['HostPort']
                        break
            
            # Handle Host Mode - Lookup from Catalog
            if c.attrs['HostConfig']['NetworkMode'] == 'host':
                 try:
                     # Load catalogs if not loaded (optimization: load once or rely on cached)
                     # For simplicity, load here or use helper if available. 
                     # Given performance, let's just peek at the file or assume we can reuse global if exists.
                     # But `docker_containers` is a standalone route.
                     
                     # Simple logic: Check against known apps in app_catalog
                     # We need to read app_catalog.json
                     catalog_path = os.path.join(DATA_DIR, 'app_catalog.json')
                     if os.path.exists(catalog_path):
                         with open(catalog_path, 'r') as f:
                             catalog = json.load(f)
                             
                         # Find match by image or name
                         for app_def in catalog:
                             # Check Image Match (Strongest signal for standard apps)
                             if app_def.get('image') and c.attrs['Config']['Image'] in app_def.get('image'):
                                 # Found it! Get the first port.
                                 if app_def.get('ports'):
                                     public_port = app_def['ports'][0].get('host')
                                 break
                             
                             # Check ID/Name Match
                             if app_def.get('id') == c.name:
                                 if app_def.get('ports'):
                                     public_port = app_def['ports'][0].get('host')
                                 break
                 except Exception as e:
                     print(f"Error checking catalog for host port: {e}")

            try:
                img_name = c.image.tags[0] if c.image.tags else c.image.short_id
            except Exception:
                img_name = c.attrs.get('Config', {}).get('Image', 'Unknown')

            result.append({
                'id': c.short_id,
                'name': c.name,
                'image': img_name,
                'status': c.status,
                'created': c.attrs['Created'][:19].replace('T', ' '),
                'port': public_port,
                'network_mode': c.attrs['HostConfig']['NetworkMode']
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/docker/<container_id>/stats')
@requires_permission('docker', 'view')
def docker_container_stats(container_id):
    """Fetch stats for a single container - called separately to not block"""
    try:
        client = docker_sdk.from_env()
        container = client.containers.get(container_id)
        
        if container.status != 'running':
            return jsonify({'cpu': 0, 'mem': 0, 'mem_used': '-', 'mem_limit': '-'})
        
        raw_stats = container.stats(stream=False)
        
        # CPU
        cpu_delta = raw_stats['cpu_stats']['cpu_usage']['total_usage'] - raw_stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = raw_stats['cpu_stats']['system_cpu_usage'] - raw_stats['precpu_stats']['system_cpu_usage']
        cpu_percent = 0.0
        if system_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * 100.0
        
        # RAM
        mem_usage = raw_stats['memory_stats'].get('usage', 0)
        mem_limit = raw_stats['memory_stats'].get('limit', 1)
        mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0
        
        return jsonify({
            'cpu': round(cpu_percent, 1),
            'mem': round(mem_percent, 1),
            'mem_used': get_size(mem_usage),
            'mem_limit': get_size(mem_limit)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/docker/<container_id>/action', methods=['POST'])
@requires_permission('docker', 'full')
def docker_action(container_id):
    try:
        data = request.get_json(silent=True) or {}
        action = data.get('action')

        client = docker_sdk.from_env()
        container = client.containers.get(container_id)

        if action == 'start':
            container.start()
        elif action == 'stop':
            container.stop()
        elif action == 'restart':
            container.restart()
        elif action == 'kill':
            container.kill()
        else:
            return jsonify({'error': 'Unknown action'}), 400

        audit_log('DOCKER_ACTION', f"{action} container {container_id}", session.get('username'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/docker/<container_id>/logs')
@requires_permission('docker', 'view')
def docker_logs(container_id):
    try:
        lines = max(1, min(2000, request.args.get('lines', 200, type=int)))
        
        client = docker_sdk.from_env()
        container = client.containers.get(container_id)
        logs = container.logs(tail=lines, timestamps=True).decode('utf-8', errors='replace')
        
        return jsonify({'logs': logs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- SECURITY ROUTES ---
@app.route('/security')
@login_required
def security_page():
    return render_template('security.html')

@app.route('/api/security/config')
@login_required
def get_security_config():
    config = load_security_config()
    # Don't send password hashes to frontend
    safe_config = {
        'username': config['username'],
        'role': config.get('role', 'admin'),
        'session_timeout': config.get('session_timeout', 3600),
        'require_auth': config.get('require_auth', True),
        'allowed_ips': config.get('allowed_ips', []),
        'max_login_attempts': config.get('max_login_attempts', 5),
        'lockout_duration': config.get('lockout_duration', 300),
        'users': [{'username': u['username'], 'role': u.get('role', 'readonly')} for u in config.get('users', [])]
    }
    return jsonify(safe_config)

@app.route('/api/security/config', methods=['POST'])
@login_required
def update_security_config():
    config = load_security_config()
    data = request.json
    
    if 'session_timeout' in data:
        config['session_timeout'] = int(data['session_timeout'])
    if 'require_auth' in data:
        config['require_auth'] = bool(data['require_auth'])
    if 'max_login_attempts' in data:
        config['max_login_attempts'] = int(data['max_login_attempts'])
    if 'lockout_duration' in data:
        config['lockout_duration'] = int(data['lockout_duration'])
    
    save_security_config(config)
    audit_log('CONFIG_CHANGED', f"Security config updated: {data}", session.get('username', 'unknown'))
    return jsonify({'success': True})

@app.route('/api/security/change-password', methods=['POST'])
@login_required
def change_password():
    config = load_security_config()
    data = request.json
    
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    
    current_hash = hashlib.sha256(current_password.encode()).hexdigest()
    if current_hash != config['password_hash']:
        return jsonify({'error': 'Current password is incorrect'}), 400
    
    if len(new_password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters'}), 400
    
    config['password_hash'] = hashlib.sha256(new_password.encode()).hexdigest()
    save_security_config(config)
    audit_log('PASSWORD_CHANGED', 'Password was changed', session.get('username', 'unknown'))
    return jsonify({'success': True})

@app.route('/api/security/users', methods=['POST'])
@admin_required
def add_user():
    """Add a new user"""
    config = load_security_config()
    data = request.json
    current_role = session.get('role', 'readonly')
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'readonly')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if len(password) < 4:
        return jsonify({'error': 'Password min 4 characters'}), 400
    
    # Validate role
    valid_roles = ['admin', 'operator', 'readonly']
    if role not in valid_roles:
        role = 'readonly'
    
    # Role hierarchy enforcement: admin can only create operator/readonly
    if current_role == 'admin' and role == 'admin':
        return jsonify({'error': 'Admin cannot create admin users'}), 403
    
    # Owner can create any except owner
    if role == 'owner':
        return jsonify({'error': 'Cannot create owner users'}), 403
    
    # Check if username exists
    if username == config['username']:
        return jsonify({'error': 'Username already exists'}), 400
    
    for u in config.get('users', []):
        if u['username'] == username:
            return jsonify({'error': 'Username already exists'}), 400
    
    # Add user
    if 'users' not in config:
        config['users'] = []
    
    config['users'].append({
        'username': username,
        'password_hash': hashlib.sha256(password.encode()).hexdigest(),
        'role': role
    })
    
    save_security_config(config)
    audit_log('USER_ADDED', f"Added user {username} with role {role}", session.get('username'))
    return jsonify({'success': True})

@app.route('/api/security/users/<username>', methods=['PUT'])
@admin_required
def update_user(username):
    """Update user role"""
    config = load_security_config()
    data = request.json
    current_role = session.get('role', 'readonly')
    new_role = data.get('role', 'readonly')
    
    # Validate role
    valid_roles = ['admin', 'operator', 'readonly']
    if new_role not in valid_roles:
        new_role = 'readonly'
    
    # Find user first
    target_user = None
    for u in config.get('users', []):
        if u['username'] == username:
            target_user = u
            break
    
    if not target_user:
        return jsonify({'error': 'User not found'}), 404
    
    # Role hierarchy enforcement
    target_current_role = target_user.get('role', 'readonly')
    
    # Admin cannot modify other admins
    if current_role == 'admin':
        if target_current_role == 'admin':
            return jsonify({'error': 'Cannot modify admin users'}), 403
        if new_role == 'admin':
            return jsonify({'error': 'Cannot promote to admin'}), 403
    
    # Cannot set role to owner
    if new_role == 'owner':
        return jsonify({'error': 'Cannot set role to owner'}), 403
    
    # Update role
    target_user['role'] = new_role
    save_security_config(config)
    audit_log('USER_ROLE_CHANGED', f"Changed {username} role to {new_role}", session.get('username'))
    return jsonify({'success': True})

@app.route('/api/security/users/<username>', methods=['DELETE'])
@admin_required
def delete_user(username):
    """Delete a user"""
    config = load_security_config()
    current_role = session.get('role', 'readonly')
    
    # Can't delete owner
    if username == config['username']:
        return jsonify({'error': 'Cannot delete owner'}), 400
    
    # Find target user
    target_user = None
    for u in config.get('users', []):
        if u['username'] == username:
            target_user = u
            break
    
    if not target_user:
        return jsonify({'error': 'User not found'}), 404
    
    # Role hierarchy enforcement: admin can only delete operator/readonly
    target_role = target_user.get('role', 'readonly')
    if current_role == 'admin' and target_role == 'admin':
        return jsonify({'error': 'Cannot delete admin users'}), 403
    
    # Delete user
    config['users'] = [u for u in config.get('users', []) if u['username'] != username]
    save_security_config(config)
    audit_log('USER_DELETED', f"Deleted user {username}", session.get('username'))
    return jsonify({'success': True})

@app.route('/api/security/audit-logs')
@login_required
def get_audit_logs():
    try:
        lines = request.args.get('lines', 100, type=int)
        if os.path.exists(AUDIT_LOG_FILE):
            with open(AUDIT_LOG_FILE, 'r') as f:
                all_lines = f.readlines()
                return jsonify({'logs': all_lines[-lines:]})
        return jsonify({'logs': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/security/session-info')
@login_required
def session_info():
    login_time = session.get('login_time', time.time())
    last_activity = session.get('last_activity', login_time)
    return jsonify({
        'username': session.get('username'),
        'role': session.get('role', 'readonly'),
        'login_time': login_time,
        'elapsed': time.time() - login_time,
        'last_activity': last_activity,
        'ip': request.remote_addr
    })

@app.route('/api/security/heartbeat', methods=['POST'])
@login_required
def session_heartbeat():
    """Heartbeat to keep session alive and track activity"""
    session['last_activity'] = time.time()
    
    # Update in active sessions
    session_id = session.get('session_id')
    if session_id and session_id in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS[session_id]['last_activity'] = time.time()
    
    return jsonify({'success': True, 'timestamp': time.time()})

@app.route('/api/security/logout-beacon', methods=['POST'])
def logout_beacon():
    """Called by browser on tab close/unload to logout"""
    if session.get('logged_in'):
        user = session.get('username', 'unknown')
        session_id = session.get('session_id')
        
        # Remove from active sessions
        if session_id and session_id in ACTIVE_SESSIONS:
            del ACTIVE_SESSIONS[session_id]
        
        audit_log('TAB_CLOSED_LOGOUT', f"User {user} logged out (browser closed)", user)
        session.clear()
    return jsonify({'success': True})

@app.route('/api/security/active-sessions')
@admin_required
def get_active_sessions():
    """Get all currently active sessions (admin only)"""
    now = time.time()
    sessions_list = []
    
    # Clean up stale sessions (no activity for 5 minutes)
    stale_threshold = 300  # 5 minutes
    stale_ids = [sid for sid, data in ACTIVE_SESSIONS.items() 
                 if now - data.get('last_activity', 0) > stale_threshold]
    for sid in stale_ids:
        del ACTIVE_SESSIONS[sid]
    
    for sid, data in ACTIVE_SESSIONS.items():
        sessions_list.append({
            'session_id': sid,
            'username': data.get('username'),
            'role': data.get('role'),
            'login_time': data.get('login_time'),
            'last_activity': data.get('last_activity'),
            'ip': data.get('ip'),
            'duration': int(now - data.get('login_time', now))
        })
    
    # Sort by login time (most recent first)
    sessions_list.sort(key=lambda x: x['login_time'], reverse=True)
    
    return jsonify({'sessions': sessions_list})

# --- SETTINGS ROUTES ---
@app.route('/settings')
@requires_permission('settings', 'view')
def settings_page():
    return render_template('settings.html')

@app.route('/api/monitoring/config')
def get_monitoring_config():
    """Public endpoint for monitoring board configuration"""
    settings = load_app_settings()
    mqtt = settings.get('mqtt', {})
    safe_mqtt = {
        'enabled': mqtt.get('enabled', False),
        'devices': mqtt.get('devices', [])
    }
    general = settings.get('general', {})
    return jsonify({
        'mqtt': safe_mqtt,
        'energy': _sanitize_energy_settings(settings.get('energy')),
        'modules': _sanitize_module_settings(settings.get('modules')),
        'server_name': (general.get('server_name') or '').strip() or detect_device_name(),
        'hostname': socket.gethostname()
    })

_MONITORING_TELEMETRY_CACHE = {
    'timestamp': 0,
    'data': None
}

@app.route('/api/monitoring/telemetry')
def get_monitoring_telemetry():
    """Public read-only telemetry summary for the NOC Wallboard display"""
    now = time.time()
    if _MONITORING_TELEMETRY_CACHE['data'] and (now - _MONITORING_TELEMETRY_CACHE['timestamp'] < 20):
        return jsonify(_MONITORING_TELEMETRY_CACHE['data'])

    # 1. SMART / Disk Health
    smart_status = {'healthy': True, 'text': 'PASSED', 'temp': 0, 'drives': 0, 'detail': 'All drives healthy'}
    try:
        drives = _discover_physical_drives()
        smart_status['drives'] = len(drives)
        if drives:
            temps = []
            all_healthy = True
            for d in drives[:3]:
                p = _parse_drive_smart(d['device'])
                if p.get('temperature'):
                    try:
                        temps.append(int(p['temperature']))
                    except (ValueError, TypeError):
                        pass
                if not p.get('healthy', True):
                    all_healthy = False
            smart_status['healthy'] = all_healthy
            smart_status['text'] = 'PASSED' if all_healthy else 'WARNING'
            smart_status['temp'] = max(temps) if temps else 0
            smart_status['detail'] = f"{len(drives)} drive(s) verified"
    except Exception:
        pass

    # 2. Firewall / Web Shield (Universal: UFW / firewalld / iptables / nftables)
    firewall_status = _get_firewall_telemetry_summary()

    # 3. Systemd Services
    services_status = {'running': 0, 'failed': 0, 'state': 'running', 'status_text': 'HEALTHY'}
    try:
        st_res = _run_systemctl(['is-system-running'], timeout=4)
        sys_state = (st_res.stdout or '').strip()
        services_status['state'] = sys_state if sys_state else 'running'
        failed_res = _run_systemctl(['list-units', '--state=failed', '--type=service', '--no-legend'], timeout=4)
        failed_lines = [l for l in (failed_res.stdout or '').splitlines() if l.strip()]
        services_status['failed'] = len(failed_lines)
        services_status['status_text'] = 'DEGRADED' if len(failed_lines) > 0 else 'HEALTHY'
    except Exception:
        pass

    # 4. OS & Kernel Packages Update
    packages_status = {'upgradable': 0, 'security': 0, 'reboot_required': False, 'kernel': 'Linux'}
    try:
        reboot_req, _ = _get_reboot_status()
        packages_status['reboot_required'] = reboot_req
        pkgs = _parse_upgradable_packages()
        packages_status['upgradable'] = len(pkgs)
        packages_status['security'] = sum(1 for p in pkgs if p.get('is_security'))
        kernel_info = _get_kernel_info()
        packages_status['kernel'] = kernel_info.get('running_kernel', platform.release())
    except Exception:
        packages_status['kernel'] = platform.release()

    # 5. Backup / Disaster Recovery
    backup_status = {'total': 0, 'latest': 'No backup', 'rclone_active': False, 'status_text': 'READY'}
    try:
        if os.path.exists(BACKUP_DIR):
            files = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.tar.gz')]
            backup_status['total'] = len(files)
            if files:
                latest_mtime = 0
                for f in files:
                    try:
                        mt = os.path.getmtime(os.path.join(BACKUP_DIR, f))
                        if mt > latest_mtime:
                            latest_mtime = mt
                    except Exception:
                        pass
                if latest_mtime > 0:
                    backup_status['latest'] = datetime.fromtimestamp(latest_mtime).strftime('%Y-%m-%d %H:%M')
        r_info = _get_rclone_info()
        backup_status['rclone_active'] = r_info.get('installed', False) and len(r_info.get('remotes', [])) > 0
        backup_status['status_text'] = 'CLOUD SYNC' if backup_status['rclone_active'] else ('LOCAL READY' if backup_status['total'] > 0 else 'IDLE')
    except Exception:
        pass

    # 6. Connectivity & Gateway Latency
    conn_status = {'online': True, 'latency_ms': 0, 'status_text': 'CONNECTED'}
    try:
        t0 = time.time()
        s = socket.create_connection(('1.1.1.1', 53), timeout=1.5)
        s.close()
        conn_status['latency_ms'] = max(1, int((time.time() - t0) * 1000))
        conn_status['online'] = True
        conn_status['status_text'] = f"{conn_status['latency_ms']}ms"
    except Exception:
        conn_status['online'] = False
        conn_status['status_text'] = 'OFFLINE'

    telemetry_data = {
        'success': True,
        'smart': smart_status,
        'firewall': firewall_status,
        'services': services_status,
        'packages': packages_status,
        'backup': backup_status,
        'connectivity': conn_status,
        'timestamp': int(now * 1000)
    }

    _MONITORING_TELEMETRY_CACHE['timestamp'] = now
    _MONITORING_TELEMETRY_CACHE['data'] = telemetry_data
    return jsonify(telemetry_data)

@app.route('/api/settings')
@login_required
def get_settings():
    return jsonify(load_app_settings())

@app.route('/api/settings', methods=['POST'])
@requires_permission('settings', 'full')
def update_settings():
    global CURRENT_WATTS, POWER_SOURCE
    settings = load_app_settings()
    data = request.json or {}
    
    # Update each section if provided
    for section in ['general', 'appearance', 'monitoring', 'alerts', 'integrations', 'mqtt', 'services', 'energy', 'modules']:
        if section in data:
            if section == 'energy' and isinstance(data[section], dict):
                merged_energy = {**settings.get('energy', {}), **data[section]}
                settings['energy'] = _sanitize_energy_settings(merged_energy)
            elif section == 'modules' and isinstance(data[section], dict):
                merged_mods = {**settings.get('modules', {}), **data[section]}
                settings['modules'] = _sanitize_module_settings(merged_mods)
            elif section in settings and isinstance(settings[section], dict) and isinstance(data[section], dict):
                settings[section] = {**settings[section], **data[section]}
            else:
                # For lists like 'services', just replace entirely
                settings[section] = data[section]
    
    save_app_settings(settings)
    if 'energy' in data:
        try:
            CURRENT_WATTS, POWER_SOURCE = POWER_READER.read_power(energy_cfg=settings['energy'])
        except Exception:
            pass
    audit_log('SETTINGS_CHANGED', f"App settings updated", session.get('username', 'unknown'))
    return jsonify({'success': True, 'energy': settings.get('energy'), 'modules': settings.get('modules')})


@app.route('/api/modules/status', methods=['GET'])
@login_required
def api_modules_status():
    """Return live availability & visibility config for all optional modules."""
    force = request.args.get('refresh') in ('1', 'true', 'yes')
    modules = _probe_optional_modules(force_refresh=force)
    settings = load_app_settings()
    mod_cfg = _sanitize_module_settings(settings.get('modules'))
    return jsonify({
        'success': True,
        'modules': modules,
        'settings': mod_cfg,
        'auto_hide_uninstalled': mod_cfg.get('auto_hide_uninstalled', False),
    })


@app.route('/api/energy/reset', methods=['POST'])
@requires_permission('settings', 'full')
def reset_energy_counter():
    """Reset accumulated kWh counter cleanly (e.g. start of billing cycle)."""
    global TOTAL_KWH
    TOTAL_KWH = 0.0
    try:
        with open(ENERGY_FILE, 'w') as f:
            json.dump({
                'kwh': 0.0,
                'last_watts': CURRENT_WATTS,
                'source': POWER_SOURCE,
                'updated_at': int(time.time())
            }, f)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    audit_log('ENERGY_RESET', 'Energy kWh counter reset to 0', session.get('username', 'unknown'))
    return jsonify({'success': True, 'kwh': '0.0000'})

@app.route('/api/settings/export')
@requires_permission('settings', 'full')
def export_settings():
    settings = load_app_settings()
    return Response(
        json.dumps(settings, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment;filename=dashboard_settings.json'}
    )

@app.route('/api/settings/import', methods=['POST'])
@requires_permission('settings', 'full')
def import_settings():
    try:
        data = request.json
        save_app_settings(data)
        audit_log('SETTINGS_IMPORTED', 'Settings imported from file', session.get('username', 'unknown'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/settings/reset', methods=['POST'])
@requires_permission('settings', 'full')
def reset_settings():
    # Delete settings file to use defaults
    if os.path.exists(APP_SETTINGS_FILE):
        os.remove(APP_SETTINGS_FILE)
    _invalidate_energy_cache()
    _invalidate_modules_cache()
    audit_log('SETTINGS_RESET', 'Settings reset to defaults', session.get('username', 'unknown'))
    return jsonify({'success': True})

# --- CASAOS ROUTES ---
CASAOS_URL = 'http://host.docker.internal:9999'
CASAOS_ALLOWED_IPS = {}  # {ip: expiry_time}

@app.route('/face')
def face_ui():
    """Eilik-style Robot Face Interface"""
    return render_template('face.html')

@app.route('/api/face-stats')
def face_stats_api():
    """Public API for Face UI (No Login Required)"""
    try:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        return jsonify({
            'cpu': cpu,
            'ram': mem.percent
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/casaos')
@login_required
def casaos_page():
    """Render CasaOS access page"""
    return render_template('casaos.html')

@app.route('/api/casaos/status')
@login_required
def casaos_status():
    """Check if CasaOS is running"""
    try:
        resp = requests.get(CASAOS_URL, timeout=2)
        return jsonify({'online': resp.status_code == 200})
    except:
        return jsonify({'online': False})

@app.route('/api/casaos/access', methods=['POST'])
@login_required
def casaos_access():
    """Grant temporary direct access to CasaOS for authenticated user"""
    ip = request.remote_addr
    # Allow this IP for 1 hour
    CASAOS_ALLOWED_IPS[ip] = time.time() + 3600
    audit_log('CASAOS_ACCESS', f"Granted CasaOS access for IP {ip}", session.get('username'))
    
    # For now, we need to unblock port 80 for this IP via iptables
    try:
        subprocess.run(['iptables', '-I', 'INPUT', '1', '-p', 'tcp', '--dport', '80', '-s', ip, '-j', 'ACCEPT'], check=True)
    except:
        pass
    
    return jsonify({
        'success': True, 
        'url': f'http://{request.host.split(":")[0]}:9999',
        'expires_in': 3600
    })

# --- SERVICE MANAGEMENT ROUTES ---
# --- SERVICE MANAGEMENT ROUTES ---

def run_host_command(cmd_list, timeout=15):
    """Run a command on the HOST system via universal _run_host_cmd (Docker nsenter or Native)."""
    return _run_host_cmd(cmd_list, timeout=timeout, include_pid=False)

@app.route('/api/services/status')
@requires_permission('services', 'view')
def services_status():
    """Get status of managed services (Dynamic from settings)"""
    settings = load_app_settings()
    services_config = settings.get('services', [])
    
    # Backward compatibility if services is dict or missing (from old config)
    if not services_config:
         services_config = [
            {'id': 'ssh', 'name': 'SSH Server'},
            {'id': 'docker', 'name': 'Docker Engine'},
            {'id': 'cron', 'name': 'Cron Job'},
            {'id': 'gunicorn', 'name': 'Gunicorn Service'}, # Umum buat Flask
            {'id': 'python-app', 'name': 'Python App Service'} # Generik
         ]

    status = []
    for srv in services_config:
        # Handle both list of dicts and old format
        service_id = srv.get('id')
        label = srv.get('name', service_id)
        
        try:
            # Check active state
            res = run_host_command(['systemctl', 'is-active', service_id])
            active = res.stdout.strip() == 'active'
            
            # Check uptime/status details (optional)
            # res_status = run_host_command(['systemctl', 'status', service_id, '--no-pager', '-n', '0'])
            
            status.append({
                'id': service_id,
                'name': label,
                'active': active,
                'status_text': 'Running' if active else 'Stopped'
            })
        except Exception as e:
            status.append({'id': service_id, 'name': label, 'active': False, 'status_text': 'Error'})
            
    return jsonify({'services': status})

def _run_systemctl(args, timeout=10):
    """Jalankan systemctl pada host via eksekutor universal (nsenter / native)."""
    return _run_host_cmd(['systemctl'] + list(args), timeout=timeout)

@app.route('/api/services/control', methods=['POST'])
@requires_permission('services', 'limited')
def api_services_control():
    """Mengendalikan siklus hidup service: start, stop, restart, enable, disable, mask, unmask"""
    data = request.json or {}
    unit = (data.get('unit') or data.get('service') or '').strip()
    action = (data.get('action') or '').strip().lower()

    valid_actions = ('start', 'stop', 'restart', 'enable', 'disable', 'mask', 'unmask')
    if action not in valid_actions:
        return jsonify({'success': False, 'error': f'Aksi tidak valid: {action}'}), 400

    if not unit:
        return jsonify({'success': False, 'error': 'Nama service/unit wajib diisi'}), 400

    if not unit.endswith('.service'):
        unit += '.service'

    if not re.match(r'^[a-zA-Z0-9_@.-]+\.service$', unit):
        return jsonify({'success': False, 'error': 'Format nama unit tidak valid'}), 400

    res = _run_systemctl([action, unit], timeout=15)
    success = (res.returncode == 0)
    output = (res.stdout or '') + (res.stderr or '')

    audit_log('SERVICE_CONTROL', f"{action.title()} unit {unit}", session.get('username'))

    return jsonify({
        'success': success,
        'message': f'Service {unit} berhasil di-{action}' if success else f'Gagal {action} {unit}: {output}',
        'output': output
    })

@app.route('/api/services/discover')
@requires_permission('services', 'view')
def discover_services():
    """Discover all systemd services on the host"""
    try:
        # List all unit files (services)
        res = run_host_command(['systemctl', 'list-unit-files', '--type=service', '--no-pager', '--no-legend'])
        
        services = []
        common_important = ['ssh', 'sshd', 'docker', 'nginx', 'apache2', 'mysql', 'mariadb', 
                           'postgresql', 'redis', 'mongodb', 'casaos', 'casaos-gateway',
                           'smbd', 'nmbd', 'vsftpd', 'fail2ban', 'ufw', 'cron', 'containerd',
                           'ollama', 'zerotier-one', 'gunicorn', 'uwsgi', 'flask',
                           'keuangan-web', 'keuangan-bot', 'server_monitor', 'yt_app', 
                           'yt_shorts_api', 'exsa-backend', 'youtube_bot', 'rclone']
        
        for line in res.stdout.strip().split('\n'):
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2:
                unit_name = parts[0].replace('.service', '')
                state = parts[1]  # enabled, disabled, static, masked
                
                # Skip system internal services (start with systemd-, dbus, etc)
                if unit_name.startswith(('systemd-', 'dbus', 'getty', 'serial-getty', 'user@', 'autovt@')):
                    continue
                    
                # Check if currently running
                active_res = run_host_command(['systemctl', 'is-active', unit_name])
                is_active = active_res.stdout.strip() == 'active'
                
                # Prioritize common/important services
                priority = 1 if unit_name in common_important else 0
                
                services.append({
                    'id': unit_name,
                    'name': unit_name.replace('-', ' ').replace('_', ' ').title(),
                    'enabled': state == 'enabled',
                    'active': is_active,
                    'priority': priority
                })
        
        # Sort by priority (important first), then by name  
        services.sort(key=lambda x: (-x['priority'], x['name']))
        
        return jsonify({'services': services[:50]})  # Limit to 50
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- DETAILED METRICS ROUTE ---
@app.route('/api/metrics/detailed')
@login_required
def detailed_metrics():
    import time
    try:
        # CPU Details
        cpu_per_core = psutil.cpu_percent(percpu=True)
        cpu_total = psutil.cpu_percent()
        
        # RAM Details
        mem = psutil.virtual_memory()
        mem_details = {
            'total': mem.total,
            'available': mem.available,
            'used': mem.used,
            'free': mem.free,
            'cached': getattr(mem, 'cached', 0) if hasattr(mem, 'cached') else getattr(mem, 'active', 0), # Windows fallback
            'buffers': getattr(mem, 'buffers', 0),
            'percent': mem.percent
        }
        
        # Storage Details (Mount Points)
        partitions = []
        for part in psutil.disk_partitions(all=False):
            if 'snap' in part.mountpoint or 'docker' in part.mountpoint: # Skip clutter
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append({
                    'device': part.device,
                    'mountpoint': part.mountpoint,
                    'fstype': part.fstype,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': usage.percent
                })
            except (PermissionError, OSError):
                continue

        # Disk I/O (System Wide)
        disk_io = psutil.disk_io_counters()
        io_stats = {
            'read_bytes': disk_io.read_bytes if disk_io else 0,
            'write_bytes': disk_io.write_bytes if disk_io else 0
        }

        # Network I/O
        net_io = psutil.net_io_counters()
        network_stats = {
            'bytes_sent': net_io.bytes_sent if net_io else 0,
            'bytes_recv': net_io.bytes_recv if net_io else 0
        }

        # Load Average & Uptime
        load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0,0,0)
        uptime = int(time.time() - psutil.boot_time())

        # Top Processes (Expensive Operation)
        processes = []
        cpu_count = psutil.cpu_count(logical=True) or 1

        # Mengambil info process. Note: memory_info().rss is standard.
        for p in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info']):
            try:
                p_info = p.info
                # Calculate memory in MB
                p_info['memory_mb'] = p_info['memory_info'].rss / (1024 * 1024)
                
                # Normalize CPU: psutil returns % of ONE core. We want % of TOTAL SYSTEM (to match dashboard).
                raw_cpu = p_info.get('cpu_percent', 0) or 0
                p_info['cpu_percent'] = round(raw_cpu / cpu_count, 1)
                
                processes.append(p_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort Top 5 CPU (skip process 0 or idle)
        top_cpu = sorted(processes, key=lambda p: float(p['cpu_percent'] or 0), reverse=True)[:10]
        # Sort Top 5 Mem
        top_mem = sorted(processes, key=lambda p: float(p['memory_mb'] or 0), reverse=True)[:10]

        return jsonify({
            'cpu': {
                'total': cpu_total,
                'per_core': cpu_per_core,
                'top_processes': top_cpu,
                'load_avg': load_avg
            },
            'memory': {
                'details': mem_details,
                'top_processes': top_mem
            },
            'storage': {
                'partitions': partitions,
                'io': io_stats
            },
            'network': network_stats,
            'system': {
                'uptime': uptime
            }
        })
    except Exception as e:
        print(f"Error metrics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/process/kill', methods=['POST'])
@requires_permission('services', 'limited')
def kill_process_api():
    pid = request.json.get('pid')
    try:
        # Check docker environment
        in_docker = os.path.exists('/.dockerenv')
        if in_docker:
             # Kill on HOST using systemctl kill?? No, 'kill' command via nsenter
             # systemctl kill is for services. For raw PID we use `kill -9 PID`
             run_host_command(['kill', '-9', str(pid)])
             # We rely on run_host_command wrapper
             return jsonify({'success': True})
        else:
             p = psutil.Process(int(pid))
             p.terminate()
             return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- MQTT LOGIC ---
def mqtt_on_connect(client, userdata, flags, rc):
    print(f"MQTT Connected with result code {rc}")
    settings = load_app_settings()
    devices = settings.get('mqtt', {}).get('devices', [])
    
    # Subscribe to status topics
    for dev in devices:
        topic = dev.get('topic') or dev.get('topic_state')
        if topic:
            client.subscribe(topic)
            print(f"MQTT Subscribed: {topic}")

def mqtt_on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode()
        # print(f"MQTT Msg: {topic} -> {payload}")
        
        # Map topic to device ID
        settings = load_app_settings()
        devices = settings.get('mqtt', {}).get('devices', [])
        
        for dev in devices:
            t_stat = dev.get('topic') or dev.get('topic_state')
            if t_stat == topic:
                HOME_DEVICES_STATE[dev['id']] = {
                    'value': payload,
                    'ts': time.time()
                }
                # Emit socket event for realtime update
                socketio.emit('home_update', {'id': dev['id'], 'value': payload})
    except Exception as e:
        print(f"MQTT Error processing message: {e}")

def init_mqtt_client():
    global mqtt_client
    if not mqtt:
        print("MQTT Library not found")
        return

    settings = load_app_settings()
    mqtt_cfg = settings.get('mqtt', {})
    
    if not mqtt_cfg.get('enabled', False):
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
            mqtt_client = None
        return

    broker = mqtt_cfg.get('broker')
    if not broker: return

    # Re-init if config changed or not exists
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    
    try:
        mqtt_client = mqtt.Client()
        if mqtt_cfg.get('user'):
            mqtt_client.username_pw_set(mqtt_cfg['user'], mqtt_cfg.get('password', ''))
            
        mqtt_client.on_connect = mqtt_on_connect
        mqtt_client.on_message = mqtt_on_message
        
        port = int(mqtt_cfg.get('port', 1883))
        mqtt_client.connect(broker, port, 60)
        mqtt_client.loop_start()
        print(f"MQTT Client Started: {broker}:{port}")
    except Exception as e:
        print(f"MQTT Init Error: {e}")

@app.route('/api/home/status')
def home_status():
    """Get current state of home devices"""
    # Force refresh/check timeout logic if needed, but returning dict is fast
    return jsonify(HOME_DEVICES_STATE)

@app.route('/api/home/control', methods=['POST'])
@login_required
def home_control():
    """Control a device via MQTT"""
    if not mqtt_client:
        return jsonify({'error': 'MQTT not connected'}), 503
        
    data = request.json
    dev_id = data.get('id')
    state = data.get('state') # boolean usually
    
    settings = load_app_settings()
    devices = settings.get('mqtt', {}).get('devices', [])
    
    target_dev = next((d for d in devices if d['id'] == dev_id), None)
    if not target_dev:
        return jsonify({'error': 'Device not found'}), 404
        
    topic = target_dev.get('topic_set') or target_dev.get('topic_control')
    if not topic:
        return jsonify({'error': 'No control topic defined'}), 400
        
    payload = target_dev.get('payload_on', 'ON') if state else target_dev.get('payload_off', 'OFF')
    
    mqtt_client.publish(topic, payload)
    return jsonify({'success': True})

# Init MQTT on startup
# We delay it slightly or run it directly
init_mqtt_client()


# --- DATABASE & HISTORY LOGIC ---
HISTORY_DB_FILE = os.path.join(DATA_DIR, 'history.db')

def init_history_db():
    conn = sqlite3.connect(HISTORY_DB_FILE)
    c = conn.cursor()
    # Create metrics table: timestamp, cpu, ram, net_sent, net_recv
    c.execute('''CREATE TABLE IF NOT EXISTS metrics (
                    timestamp INTEGER PRIMARY KEY,
                    cpu REAL,
                    ram REAL,
                    net_sent REAL,
                    net_recv REAL
                 )''')
    # Auto cleanup old data trigger (keep last 3 days approx 4320 mins)
    c.execute('''CREATE TRIGGER IF NOT EXISTS clean_old_metrics 
                 AFTER INSERT ON metrics
                 BEGIN
                    DELETE FROM metrics WHERE timestamp < (NEW.timestamp - 259200);
                 END;''')
    conn.commit()
    conn.close()

def record_metrics_background():
    """Background task to record metrics every 60 seconds"""
    while True:
        try:
            # Stats
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            net = psutil.net_io_counters()
            
            # Save to DB
            conn = sqlite3.connect(HISTORY_DB_FILE)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO metrics (timestamp, cpu, ram, net_sent, net_recv) VALUES (?, ?, ?, ?, ?)",
                           (int(time.time()), cpu, ram, net.bytes_sent, net.bytes_recv))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error recording metrics: {e}")
            
        eventlet.sleep(60)

# Init DB on start
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
init_history_db()

# Start Background Task
eventlet.spawn(record_metrics_background)

@app.route('/api/metrics/history')
@login_required
def get_metrics_history():
    """Get last 24h metrics (resampled/simplified if needed)"""
    try:
        range_hours = request.args.get('hours', 24, type=int)
        cutoff = int(time.time()) - (range_hours * 3600)
        
        conn = sqlite3.connect(HISTORY_DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM metrics WHERE timestamp > ? ORDER BY timestamp ASC", (cutoff,))
        rows = c.fetchall()
        conn.close()
        
        data = {
            'labels': [],
            'cpu': [],
            'ram': [],
            'net_sent': [], 
            'net_recv': []
        }
        
        for r in rows:
            data['labels'].append(r['timestamp'])
            data['cpu'].append(r['cpu'])
            data['ram'].append(r['ram'])
            data['net_sent'].append(r['timestamp']) # Placeholder, handled in UI? wait, previous code had delta logic. Let's keep raw.
            data['net_recv'].append(r['net_recv'])
            
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/storage/analyze')
@login_required
def storage_analyze():
    """Analyze top files (Requires 'scan' param path, default /)"""
    scan_path = request.args.get('path', '/app/data') 
    
    # We want to scan HOST files. We mounted /:/host/root
    prefix = "/host/root"
    target_path = prefix
    
    try:
        # Run du command. It's safe-ish.
        # du -ah --max-depth=2 /host/root | sort -rh | head -n 20
        
        full_cmd = f"du -ah --max-depth=2 {target_path} 2>/dev/null | sort -rh | head -n 20"
        
        res = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=20)
        
        lines = res.stdout.strip().split('\n')
        results = []
        for line in lines:
            parts = line.split('\t')
            if len(parts) == 2:
                display_path = parts[1].replace(prefix, '') or '/'
                results.append({'size': parts[0], 'path': display_path})
                
        return jsonify({'files': results})
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Scan timed out (Disk too large/slow)'}), 408
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ UPDATE CHECKER ============
@app.route('/api/version')
@login_required
def get_version():
    """Menampilkan versi aplikasi saat ini"""
    return jsonify({
        'name': APP_NAME,
        'version': APP_VERSION,
        'build_date': '2026-01-11'
    })

@app.route('/api/check-update')
@login_required
def check_update_layout():
    """Cek apakah ada versi baru tersedia (Standardized)"""
    try:
        # Coba ambil info versi dari GitHub
        headers = {'User-Agent': 'EkaDashboard/1.0'}
        response = requests.get(UPDATE_CHECK_URL, headers=headers, timeout=10)
        
        if response.status_code == 200:
            remote_info = response.json()
            remote_version = remote_info.get('version', '0.0.0')
            
            # Bandingkan versi (Semantic Versioning)
            def parse_version(v):
                return [int(x) for x in v.split('.')] if v else [0,0,0]

            current_parts = parse_version(APP_VERSION)
            remote_parts = parse_version(remote_version)
            
            update_available = remote_parts > current_parts
            
            return jsonify({
                'current_version': APP_VERSION,
                'latest_version': remote_version,
                'update_available': update_available,
                'changelog': remote_info.get('changelog', ''),
                'download_url': remote_info.get('download_url', ''),
                'release_date': remote_info.get('release_date', ''),
                'success': True
            })
        else:
            return jsonify({
                'current_version': APP_VERSION,
                'error': f'Server update merespon dengan kode: {response.status_code}',
                'update_available': False,
                'success': False
            })
    except requests.exceptions.Timeout:
        return jsonify({
            'current_version': APP_VERSION,
            'error': 'Timeout saat menghubungi server update',
            'update_available': False,
            'success': False
        })
    except Exception as e:
        return jsonify({
            'current_version': APP_VERSION,
            'error': f'Gagal cek update: {str(e)}',
            'update_available': False,
            'success': False
        })

@app.route('/api/perform-update', methods=['POST'])
@login_required
def perform_update():
    """Melakukan update otomatis dari GitHub dan rebuild container"""
    if session.get('role') not in ['owner', 'admin']:
        return jsonify({'success': False, 'error': 'Akses ditolak.'}), 403

    try:
        import docker
        client = docker.from_env()
        
        # Cari container dashboard ini
        container = None
        for c in client.containers.list():
            if 'eka_dashboard' in c.name:
                container = c
                break
                
        if not container:
            # Fallback jika tidak ketemu berdasarkan nama
            container = client.containers.get('eka_dashboard')

        working_dir = container.labels.get('com.docker.compose.project.working_dir')
        
        if not working_dir:
            # Fallback manual jika gagal dideteksi
            working_dir = '/root/eka_dashboard'

        # Eksekusi perintah di host untuk pull kode terbaru dan build ulang
        # Perintah ini akan berjalan di background dan otomatis me-restart container
        update_cmd = f"cd '{working_dir}' && git pull origin main && docker compose up --build -d"
        nsenter_cmd = f"nsenter -m -u -i -n -p -t 1 sh -c \"{update_cmd}\""
        
        subprocess.Popen(nsenter_cmd, shell=True)
        
        return jsonify({
            'success': True, 
            'message': 'Sistem sedang memperbarui diri. Harap tunggu sekitar 1-2 menit lalu muat ulang halaman (Refresh).'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'Gagal menjalankan pembaruan: {str(e)}'}), 500

# ========================================


# ============ NETWORK CONFIGURATION ============
@app.route('/network')
@login_required
@admin_required
def network_page():
    """Halaman konfigurasi jaringan"""
    return render_template('network.html')

@app.route('/api/network/info')
@login_required
def get_network_info():
    """Mendapatkan informasi jaringan saat ini (HOST)"""
    try:
        result = {
            'hostname': '',
            'primary_ip': '',
            'primary_mac': '',
            'gateway': '',
            'dns': [],
            'interfaces': [],
            'public_ip': ''
        }
        
        nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
        
        # 1. Get Hostname
        try:
            res = subprocess.run(nsenter + ['hostname'], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                result['hostname'] = res.stdout.strip()
        except:
            result['hostname'] = 'Unknown'

        # Fetch stats from ip -j -s link
        link_stats = {}
        try:
            res_link = subprocess.run(nsenter + ['ip', '-j', '-s', 'link'], capture_output=True, text=True, timeout=5)
            if res_link.returncode == 0:
                for l in json.loads(res_link.stdout):
                    iname = l.get('ifname')
                    s64 = l.get('stats64', {})
                    link_stats[iname] = {
                        'mtu': l.get('mtu', 1500),
                        'rx_bytes': s64.get('rx', {}).get('bytes', 0),
                        'tx_bytes': s64.get('tx', {}).get('bytes', 0),
                        'rx_dropped': s64.get('rx', {}).get('dropped', 0),
                        'tx_dropped': s64.get('tx', {}).get('dropped', 0),
                        'rx_errors': s64.get('rx', {}).get('errors', 0),
                        'tx_errors': s64.get('tx', {}).get('errors', 0),
                    }
        except Exception as e:
            print(f"Error getting link stats: {e}")

        # 2. Get Interfaces & IP (via ip -j addr)
        try:
            res = subprocess.run(nsenter + ['ip', '-j', 'addr'], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                addr_data = json.loads(res.stdout)
                
                for iface in addr_data:
                    name = iface.get('ifname', 'unknown')
                    if name == 'lo': continue
                    
                    flags = iface.get('flags', [])
                    operstate = iface.get('operstate', 'unknown').lower()
                    has_up_flag = ('UP' in flags or 'LOWER_UP' in flags)
                    has_ip = False
                    
                    st = link_stats.get(name, {})
                    iface_info = {
                        'name': name,
                        'ip': '',
                        'mac': iface.get('address', ''),
                        'type': 'ethernet',
                        'status': 'down',
                        'mtu': st.get('mtu', iface.get('mtu', 1500)),
                        'rx_bytes': st.get('rx_bytes', 0),
                        'tx_bytes': st.get('tx_bytes', 0),
                        'rx_dropped': st.get('rx_dropped', 0),
                        'tx_dropped': st.get('tx_dropped', 0),
                        'rx_errors': st.get('rx_errors', 0),
                        'tx_errors': st.get('tx_errors', 0)
                    }
                    
                    # Heuristic Type
                    lower_name = name.lower()
                    if 'wlan' in lower_name or 'wifi' in lower_name or 'wl' in lower_name:
                        iface_info['type'] = 'wifi'
                    elif 'tun' in lower_name or 'wg' in lower_name or 'tailscale' in lower_name or 'zt' in lower_name:
                        iface_info['type'] = 'vpn'
                    elif 'br' in lower_name or 'lxd' in lower_name:
                        iface_info['type'] = 'bridge'
                    elif 'docker' in lower_name or 'veth' in lower_name or 'tap' in lower_name:
                        iface_info['type'] = 'virtual'
                        
                    # Get IPs
                    for addr in iface.get('addr_info', []):
                        if addr.get('family') == 'inet':
                            ip = addr.get('local')
                            prefix = addr.get('prefixlen')
                            iface_info['ip'] = f"{ip}/{prefix}" if prefix else ip
                            has_ip = True
                            # Determine primary IP (heuristic: global scope, not docker/br)
                            if not result['primary_ip'] and iface_info['type'] in ['ethernet', 'wifi']:
                                result['primary_ip'] = ip
                                result['primary_mac'] = iface_info['mac']

                    # Status determination
                    # In Linux, virtual tunnels (like tailscale0, wg0) report operstate: UNKNOWN because they lack physical carrier detection.
                    # An interface is UP if flags have UP/LOWER_UP, operstate is 'up', or has an active IP.
                    if has_up_flag or operstate == 'up' or (has_ip and operstate != 'down'):
                        iface_info['status'] = 'up'
                    else:
                        iface_info['status'] = 'down'
                    
                    result['interfaces'].append(iface_info)
        except Exception as e:
            print(f"Error getting interfaces: {e}")

        # Sort interfaces: physical & VPN first, then bridges, then container veths
        def iface_priority(item):
            n = item.get('name', '').lower()
            t = item.get('type', '')
            if t in ['ethernet', 'wifi']:
                return (0, n)
            if 'tailscale' in n or t == 'vpn':
                return (1, n)
            if 'br' in n or t == 'bridge':
                return (2, n)
            return (3, n)

        result['interfaces'].sort(key=iface_priority)

        # 3. Get Gateway
        try:
            res = subprocess.run(nsenter + ['ip', '-j', 'route', 'show', 'default'], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                routes = json.loads(res.stdout)
                if routes:
                    result['gateway'] = routes[0].get('gateway', '')
        except:
            pass

        # 4. Get DNS (cat /etc/resolv.conf)
        try:
            res = subprocess.run(nsenter + ['cat', '/etc/resolv.conf'], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if line.startswith('nameserver'):
                        parts = line.split()
                        if len(parts) > 1:
                            result['dns'].append(parts[1])
        except:
            pass

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/network/ports')
@app.route('/api/network-ports')
@login_required
def get_network_ports():
    """Mendapatkan daftar port listening di host"""
    ports = []
    nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
    try:
        res = subprocess.run(nsenter + ['ss', '-tulpn', '-H'], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            for line in res.stdout.strip().splitlines():
                parts = line.split()
                if len(parts) < 5:
                    continue
                proto = parts[0].upper()
                local_raw = parts[4]
                if ":" in local_raw:
                    ip_str, port_str = local_raw.rsplit(":", 1)
                    try:
                        port = int(port_str)
                    except ValueError:
                        continue
                else:
                    continue
                
                proc_str = " ".join(parts[6:]) if len(parts) >= 7 else ""
                m = re.search(r'\("([^"]+)",pid=(\d+)', proc_str)
                program = m.group(1) if m else "System"
                pid = int(m.group(2)) if m else None
                
                is_loopback = ip_str in ("127.0.0.1", "::1", "127.0.0.53", "127.0.0.54") or ip_str.startswith("127.0.0.")
                is_public = (ip_str in ("0.0.0.0", "*", "[::]", "::") or not is_loopback)
                
                ports.append({
                    'proto': proto,
                    'ip': ip_str,
                    'port': port,
                    'program': program,
                    'pid': pid,
                    'is_public': is_public
                })
            ports.sort(key=lambda x: (x['port'], x['proto']))
            return jsonify(ports)
    except Exception as e:
        print(f"Error ss ports: {e}")

    # Fallback to psutil
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.status == 'LISTEN':
                pid = conn.pid
                prog = "Unknown"
                if pid:
                    try:
                        prog = psutil.Process(pid).name()
                    except:
                        pass
                ip_str = conn.laddr.ip
                is_loopback = ip_str.startswith("127.") or ip_str == "::1"
                ports.append({
                    'proto': 'TCP',
                    'ip': ip_str,
                    'port': conn.laddr.port,
                    'program': prog,
                    'pid': pid,
                    'is_public': not is_loopback
                })
        ports.sort(key=lambda x: x['port'])
    except Exception as e2:
        return jsonify({'error': str(e2)}), 500

    return jsonify(ports)

@app.route('/api/network/routes')
@login_required
def get_network_routes():
    """Mendapatkan tabel routing host"""
    routes = []
    nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
    try:
        res = subprocess.run(nsenter + ['ip', '-j', 'route'], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            routes = json.loads(res.stdout)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify(routes)

@app.route('/api/network/public-ip')
@login_required
def get_public_ip():
    """Mengambil IP publik server"""
    try:
        res = subprocess.run(['curl', '-s', '-m', '3', 'https://api.ipify.org'], capture_output=True, text=True, timeout=4)
        if res.returncode == 0 and res.stdout.strip():
            return jsonify({'public_ip': res.stdout.strip()})
    except:
        pass
    return jsonify({'public_ip': '-'})

@app.route('/api/network/ping', methods=['POST'])
@login_required
def ping_host():
    """Uji ping ke target host"""
    data = request.json or {}
    target = data.get('target', '').strip()
    count = min(max(int(data.get('count', 3)), 1), 5)
    
    if not target:
        return jsonify({'error': 'Target ping tidak boleh kosong'}), 400
        
    if not re.match(r'^[a-zA-Z0-9.-]+$', target):
        return jsonify({'error': 'Format target ping tidak valid'}), 400
        
    nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
    try:
        cmd = nsenter + ['ping', '-c', str(count), '-W', '2', target]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        
        output = res.stdout or res.stderr
        success = (res.returncode == 0)
        
        loss_match = re.search(r'(\d+)% packet loss', output)
        loss = int(loss_match.group(1)) if loss_match else (0 if success else 100)
        
        rtt_match = re.search(r'rtt min/avg/max/mdev = ([0-9.]+)/([0-9.]+)/([0-9.]+)', output)
        avg_rtt = float(rtt_match.group(2)) if rtt_match else None
        
        return jsonify({
            'success': success,
            'target': target,
            'packet_loss': loss,
            'avg_rtt_ms': avg_rtt,
            'output': output
        })
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Ping timeout setelah 12 detik'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/network/dns-lookup', methods=['POST'])
@login_required
def dns_lookup():
    """Uji resolusi DNS domain"""
    data = request.json or {}
    domain = data.get('domain', '').strip()
    
    if not domain:
        return jsonify({'error': 'Domain tidak boleh kosong'}), 400
        
    if not re.match(r'^[a-zA-Z0-9.-]+$', domain):
        return jsonify({'error': 'Format domain tidak valid'}), 400
        
    start_time = time.time()
    try:
        resolved = []
        info = socket.getaddrinfo(domain, None)
        for item in info:
            ip = item[4][0]
            if ip not in resolved:
                resolved.append(ip)
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return jsonify({
            'success': True,
            'domain': domain,
            'ips': resolved,
            'elapsed_ms': elapsed_ms
        })
    except socket.gaierror as e:
        return jsonify({
            'success': False,
            'domain': domain,
            'error': f'Domain tidak dapat diresolusi ({str(e)})'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/network/hostname', methods=['POST'])
@login_required
@admin_required
def update_hostname():
    """Mengubah hostname server"""
    try:
        data = request.json
        new_hostname = data.get('hostname', '').strip()
        
        if not new_hostname:
            return jsonify({'error': 'Hostname tidak boleh kosong'}), 400
        
        # Validasi hostname
        if not re.match(r'^[a-zA-Z0-9-]+$', new_hostname):
            return jsonify({'error': 'Hostname hanya boleh berisi huruf, angka, dan tanda hubung'}), 400
        
        if len(new_hostname) > 63:
            return jsonify({'error': 'Hostname terlalu panjang (maks 63 karakter)'}), 400
        
        # Update hostname using hostnamectl (systemd)
        result = subprocess.run(
            ['hostnamectl', 'set-hostname', new_hostname],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return jsonify({'error': f'Gagal mengubah hostname: {result.stderr}'}), 500
        
        # Update /etc/hosts juga
        try:
            with open('/etc/hosts', 'r') as f:
                hosts_content = f.read()
            
            old_hostname = socket.gethostname()
            hosts_content = hosts_content.replace(old_hostname, new_hostname)
            
            with open('/etc/hosts', 'w') as f:
                f.write(hosts_content)
        except Exception as e:
            pass
        
        audit_log('NETWORK_CHANGE', f'Hostname diubah menjadi: {new_hostname}', session.get('username'))
        return jsonify({'success': True, 'message': 'Hostname berhasil diubah'})
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout saat mengubah hostname'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/network/dns', methods=['POST'])
@login_required
@admin_required
def update_dns():
    """Mengubah konfigurasi DNS"""
    try:
        data = request.json
        dns_servers = data.get('dns', [])
        
        if not dns_servers or len(dns_servers) == 0:
            return jsonify({'error': 'Minimal satu DNS server diperlukan'}), 400
        
        ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
        for dns in dns_servers:
            if not ip_pattern.match(dns):
                return jsonify({'error': f'Format DNS tidak valid: {dns}'}), 400
        
        resolv_content = "# Generated by Eka Dashboard\n"
        for dns in dns_servers:
            resolv_content += f"nameserver {dns}\n"
        
        with open('/etc/resolv.conf', 'w') as f:
            f.write(resolv_content)
        
        audit_log('NETWORK_CHANGE', f'DNS diubah menjadi: {", ".join(dns_servers)}', session.get('username'))
        return jsonify({'success': True, 'message': 'Konfigurasi DNS berhasil disimpan'})
        
    except PermissionError:
        return jsonify({'error': 'Tidak memiliki izin untuk mengubah konfigurasi DNS'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# ===============================================


# ============ STORAGE MANAGEMENT ============
@app.route('/storage')
@login_required
@admin_required
def storage_page():
    """Halaman manajemen penyimpanan"""
    return render_template('storage.html')

@app.route('/api/storage/disks')
@login_required
def get_storage_disks():
    """Mendapatkan daftar disk dan partisi yang sangat lengkap menggunakan lsblk"""
    try:
        disks = []
        total_size = 0
        total_used = 0
        total_free = 0
        disk_count = 0
        
        # Ambil data dari lsblk
        try:
            lsblk_result = subprocess.run(
                ['lsblk', '-J', '-b', '-o', 'NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL,SERIAL,VENDOR,UUID'],
                capture_output=True, text=True, timeout=10
            )
            if lsblk_result.returncode != 0:
                raise Exception("lsblk failed")
            
            lsblk_data = json.loads(lsblk_result.stdout)
        except Exception as e:
            return jsonify({'error': f"Gagal mengambil data lsblk: {str(e)}"}), 500

        # Map untuk memudahkan pencarian usage dari psutil
        mounted_usage = {}
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                mounted_usage[part.mountpoint] = {
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': usage.percent
                }
            except:
                pass

        for dev in lsblk_data.get('blockdevices', []):
            # Skip loop devices unless they are specifically requested or large
            if dev.get('type') == 'loop':
                continue
            
            # Info fisik disk
            physical_info = {
                'model': dev.get('model', 'Unknown'),
                'serial': dev.get('serial', 'N/A'),
                'vendor': dev.get('vendor', ''),
                'size_raw': int(dev.get('size', 0))
            }
            
            # Jika ini disk fisik, tambahkan ke hitungan disk
            if dev.get('type') == 'disk':
                disk_count += 1

            # Proses device itu sendiri (bisa jadi disk tanpa partisi atau partisi itu sendiri)
            def process_device(item, parent_info=None):
                name = item.get('name')
                device_path = f"/dev/{name}"
                mountpoint = item.get('mountpoint')
                fstype = item.get('fstype', '')
                size_raw = int(item.get('size', 0))
                
                info = {
                    'name': name,
                    'device': device_path,
                    'mountpoint': mountpoint,
                    'fstype': fstype,
                    'size_raw': size_raw,
                    'size': format_bytes(size_raw),
                    'type': 'hdd',
                    'is_partition': item.get('type') == 'part',
                    'mounted': mountpoint is not None,
                    'model': parent_info['model'] if parent_info else item.get('model', 'Unknown'),
                    'serial': parent_info['serial'] if parent_info else item.get('serial', 'N/A'),
                    'uuid': item.get('uuid', '')
                }

                # Deteksi tipe icon
                if 'nvme' in name: info['type'] = 'ssd'
                elif 'mmc' in name: info['type'] = 'sd'
                elif parent_info and 'usb' in (parent_info['model'] or '').lower(): info['type'] = 'usb'
                
                # Tambahkan data penggunaan jika mounted
                if mountpoint and mountpoint in mounted_usage:
                    usage = mounted_usage[mountpoint]
                    info['used'] = format_bytes(usage['used'])
                    info['free'] = format_bytes(usage['free'])
                    info['usage_percent'] = usage['percent']
                    
                    # Hanya tambahkan ke total jika ini mount point unik (bukan bind mount)
                    # Kita anggap / dan /home dsb adalah unik
                    non_unique = ['/etc/resolv.conf', '/etc/hostname', '/etc/hosts']
                    if mountpoint not in non_unique and not mountpoint.startswith('/snap'):
                        nonlocal total_size, total_used, total_free
                        # Hindari double counting jika device yang sama di-mount di tempat berbeda
                        # (Sudah di-filter oleh psutil.disk_partitions(all=False) sebenarnya)
                else:
                    info['used'] = None
                    info['free'] = None
                    info['usage_percent'] = 0

                return info

            # Jika disk memiliki anak (partisi)
            if dev.get('children'):
                for child in dev['children']:
                    disks.append(process_device(child, physical_info))
            else:
                # Disk tanpa partisi (atau disk itu sendiri yang di-mount langsung)
                disks.append(process_device(dev, physical_info))

        # Hitung ringkasan dari mounted_usage untuk akurasi
        for mpoint, usage in mounted_usage.items():
            if mpoint.startswith('/snap') or mpoint in ['/etc/resolv.conf', '/etc/hostname', '/etc/hosts']:
                continue
            total_size += usage['total']
            total_used += usage['used']
            total_free += usage['free']

        return jsonify({
            'disks': disks,
            'summary': {
                'disk_count': disk_count,
                'total_size': format_bytes(total_size),
                'total_used': format_bytes(total_used),
                'total_free': format_bytes(total_free)
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def format_bytes(bytes_val):
    """Format bytes ke human readable (GB, TB, dll)"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"

@app.route('/api/storage/mount', methods=['POST'])
@login_required
@admin_required
def mount_partition():
    """Mount partisi ke mount point tertentu"""
    try:
        data = request.json
        device = data.get('device', '')
        mountpoint = data.get('mountpoint', '')
        
        if not device or not mountpoint:
            return jsonify({'error': 'Device dan mount point diperlukan'}), 400
        
        # Validasi path
        if not mountpoint.startswith('/'):
            return jsonify({'error': 'Mount point harus absolute path (dimulai dengan /)'}), 400
        
        # Buat direktori mount point jika belum ada
        if not os.path.exists(mountpoint):
            os.makedirs(mountpoint, exist_ok=True)
        
        # Jalankan mount command
        result = subprocess.run(
            ['mount', device, mountpoint],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode != 0:
            return jsonify({'error': f'Gagal mount: {result.stderr}'}), 500
        
        audit_log('STORAGE_MOUNT', f'Mounted {device} ke {mountpoint}', session.get('username'))
        return jsonify({'success': True, 'message': f'Berhasil mount {device} ke {mountpoint}'})
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout saat mount'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/storage/unmount', methods=['POST'])
@login_required
@admin_required
def unmount_partition():
    """Unmount partisi"""
    try:
        data = request.json
        device = data.get('device', '')
        
        if not device:
            return jsonify({'error': 'Device diperlukan'}), 400
        
        # Jalankan umount command
        result = subprocess.run(
            ['umount', device],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode != 0:
            # Coba dengan -l (lazy unmount) jika gagal
            result = subprocess.run(
                ['umount', '-l', device],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return jsonify({'error': f'Gagal unmount: {result.stderr}'}), 500
        
        audit_log('STORAGE_UNMOUNT', f'Unmounted {device}', session.get('username'))
        return jsonify({'success': True, 'message': f'Berhasil unmount {device}'})
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout saat unmount'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# ============================================


# ============ DISASTER RECOVERY & OFFSITE BACKUP ENGINE ============
BACKUP_DIR = os.path.join(DATA_DIR, 'backups')
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR, exist_ok=True)

BACKUP_SYNC_META_FILE = os.path.join(DATA_DIR, 'backup_sync_meta.json')
BACKUP_SCHEDULE_FILE = os.path.join(DATA_DIR, 'backup_schedule.json')


def _load_backup_sync_meta():
    """Memuat metadata riwayat sinkronisasi offsite cloud backup"""
    if os.path.exists(BACKUP_SYNC_META_FILE):
        try:
            with open(BACKUP_SYNC_META_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {'synced_files': {}, 'last_sync': None, 'active_remote': None}


def _save_backup_sync_meta(meta):
    """Menyimpan metadata riwayat sinkronisasi offsite"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(BACKUP_SYNC_META_FILE, 'w') as f:
            json.dump(meta, f, indent=2)
        return True
    except Exception:
        return False


def _load_backup_schedule():
    """Memuat konfigurasi jadwal backup otomatis"""
    if os.path.exists(BACKUP_SCHEDULE_FILE):
        try:
            with open(BACKUP_SCHEDULE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        'enabled': False,
        'frequency': 'daily',
        'time': '02:00',
        'remote': None,
        'scope': {'config': True, 'docker': True, 'nginx': True, 'system': False}
    }


def _save_backup_schedule(sched):
    """Menyimpan konfigurasi jadwal backup otomatis"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(BACKUP_SCHEDULE_FILE, 'w') as f:
            json.dump(sched, f, indent=2)
        return True
    except Exception:
        return False


def _run_rclone_cmd(args, timeout=60):
    """Menjalankan binary rclone pada host melalui eksekutor universal (nsenter / native)."""
    res = _run_host_cmd(['rclone'] + list(args), timeout=timeout, include_pid=False)
    return res.returncode, res.stdout, res.stderr


def _get_rclone_info():
    """Mendeteksi apakah rclone terpasang pada host dan mengambil daftar remote aktif"""
    installed = False
    version = ""
    remotes = []

    try:
        res = _run_host_cmd(['which', 'rclone'], timeout=5, include_pid=False)
        if res.returncode == 0 and res.stdout.strip():
            installed = True
            rc, out, _ = _run_rclone_cmd(['version'], timeout=5)
            if rc == 0 and out:
                first_line = out.strip().splitlines()[0]
                version = first_line.replace('rclone', '').strip()
            rc, out_remotes, _ = _run_rclone_cmd(['listremotes'], timeout=8)
            if rc == 0 and out_remotes:
                remotes = [r.strip().rstrip(':') for r in out_remotes.strip().splitlines() if r.strip()]
    except Exception:
        pass

    return {
        'installed': installed,
        'version': version,
        'remotes': remotes
    }


def _inspect_tarball(filepath):
    """Membaca manifest dan daftar anggota file di dalam arsip tar.gz"""
    import tarfile
    manifest = None
    members = []
    try:
        with tarfile.open(filepath, 'r:gz') as tar:
            for m in tar.getmembers():
                if m.name in ['manifest.json', './manifest.json']:
                    f = tar.extractfile(m)
                    if f:
                        try:
                            manifest = json.load(f)
                        except Exception:
                            pass
                members.append({
                    'name': m.name,
                    'size': format_bytes(m.size),
                    'size_bytes': m.size,
                    'is_dir': m.isdir(),
                    'mtime': datetime.fromtimestamp(m.mtime).strftime('%Y-%m-%d %H:%M:%S') if m.mtime else '-'
                })
        return {'success': True, 'manifest': manifest, 'members': members, 'count': len(members)}
    except Exception as e:
        return {'success': False, 'error': str(e), 'members': [], 'count': 0}


@app.route('/backup')
@login_required
@admin_required
def backup_page():
    """Halaman Disaster Recovery & Offsite Backup Engine"""
    return render_template('backup.html')


@app.route('/api/backup/summary')
@login_required
def api_backup_summary():
    """Ringkasan statistik telemetri backup, cloud remotes, dan status scheduler"""
    try:
        total_backups = 0
        total_bytes = 0
        latest_backup = None

        if os.path.exists(BACKUP_DIR):
            files = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.tar.gz')]
            total_backups = len(files)
            for f in files:
                f_path = os.path.join(BACKUP_DIR, f)
                try:
                    st = os.stat(f_path)
                    total_bytes += st.st_size
                    if latest_backup is None or st.st_mtime > latest_backup.get('timestamp', 0):
                        latest_backup = {
                            'filename': f,
                            'timestamp': st.st_mtime,
                            'date': datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M'),
                            'size': format_bytes(st.st_size)
                        }
                except Exception:
                    pass

        rclone_info = _get_rclone_info()
        sync_meta = _load_backup_sync_meta()
        sched = _load_backup_schedule()

        return jsonify({
            'success': True,
            'summary': {
                'total_backups': total_backups,
                'total_bytes': total_bytes,
                'total_size_formatted': format_bytes(total_bytes),
                'latest_backup': latest_backup,
                'rclone': rclone_info,
                'sync_meta': sync_meta,
                'schedule': sched
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/backup/list')
@login_required
def list_backups():
    """Mendapatkan daftar snapshot backup yang tersedia beserta manifest metadata"""
    try:
        backups = []
        sync_meta = _load_backup_sync_meta()
        synced_files = sync_meta.get('synced_files', {})

        if os.path.exists(BACKUP_DIR):
            for filename in os.listdir(BACKUP_DIR):
                if filename.endswith('.tar.gz'):
                    filepath = os.path.join(BACKUP_DIR, filename)
                    stat = os.stat(filepath)

                    # Derivasi nama dan komponen
                    parts = filename.replace('.tar.gz', '').split('_')
                    if len(parts) >= 3:
                        date_str = f"{parts[1]} {parts[2].replace('-', ':')}"
                        name = '_'.join(parts[3:]) if len(parts) > 3 else 'Snapshot'
                    else:
                        date_str = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                        name = filename.replace('.tar.gz', '')

                    # Default components tag
                    components = ['Dashboard']
                    if 'nginx' in filename.lower():
                        components.append('Nginx Host')
                    if 'system' in filename.lower():
                        components.append('System Netplan')
                    if 'docker' in filename.lower() or 'all' in filename.lower():
                        components.append('Docker')

                    # Cek apakah synced ke remote
                    sync_info = synced_files.get(filename)
                    is_synced = bool(sync_info)

                    backups.append({
                        'id': filename,
                        'name': name or 'Snapshot',
                        'filename': filename,
                        'date': date_str,
                        'size': format_bytes(stat.st_size),
                        'size_bytes': stat.st_size,
                        'timestamp': stat.st_mtime,
                        'components': components,
                        'synced': is_synced,
                        'sync_info': sync_info
                    })

        backups.sort(key=lambda x: x['timestamp'], reverse=True)
        return jsonify({'success': True, 'backups': backups})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/backup/create', methods=['POST'])
@login_required
@admin_required
def create_backup():
    """Membuat snapshot sistem disaster recovery baru (Dashboard, Docker, Nginx, System Netplan)"""
    try:
        import tarfile

        data = request.json or {}
        custom_name = data.get('name', '').strip()
        include_config = data.get('include_config', True)
        include_docker = data.get('include_docker', True)
        include_users = data.get('include_users', True)
        include_nginx = data.get('include_nginx', True)
        include_system = data.get('include_system', False)
        custom_paths = data.get('custom_paths', [])
        sync_remote = data.get('sync_remote')

        timestamp_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        safe_name = ''.join(c for c in custom_name if c.isalnum() or c in '-_') if custom_name else 'disaster_recovery'
        filename = f"backup_{timestamp_str}_{safe_name}.tar.gz"
        filepath = os.path.join(BACKUP_DIR, filename)

        components_included = []

        with tarfile.open(filepath, 'w:gz') as tar:
            # 1. Konfigurasi Dashboard & Security
            if include_config:
                components_included.append('Dashboard Config')
                for cfg_name in ['settings.json', 'alert_config.json', 'alert_history.json']:
                    p = os.path.join(DATA_DIR, cfg_name)
                    if os.path.exists(p):
                        tar.add(p, arcname=f"dashboard/{cfg_name}")

                sec_file = os.path.join(BASE_DIR, 'security_config.json')
                if os.path.exists(sec_file):
                    tar.add(sec_file, arcname="dashboard/security_config.json")

            # 2. Docker Compose
            if include_docker:
                components_included.append('Docker Compose')
                compose_file = os.path.join(BASE_DIR, 'docker-compose.yml')
                if os.path.exists(compose_file):
                    tar.add(compose_file, arcname="docker/docker-compose.yml")
                catalog_file = os.path.join(DATA_DIR, 'app_catalog.json')
                if os.path.exists(catalog_file):
                    tar.add(catalog_file, arcname="docker/app_catalog.json")

            # 3. Data Pengguna
            if include_users:
                components_included.append('Users Database')
                users_db = os.path.join(DATA_DIR, 'users.db')
                if os.path.exists(users_db):
                    tar.add(users_db, arcname="users/users.db")

            # 4. Host Nginx Virtual Hosts & Konfigurasi
            if include_nginx:
                components_included.append('Host Nginx')
                host_nginx = '/host/root/etc/nginx'
                if os.path.exists(host_nginx):
                    tar.add(host_nginx, arcname="host_etc/nginx")

            # 5. Host System Network & Mount Configs
            if include_system:
                components_included.append('Host System Config')
                for sys_item in ['netplan', 'hosts', 'fstab', 'systemd/system']:
                    p_sys = f"/host/root/etc/{sys_item}"
                    if os.path.exists(p_sys):
                        tar.add(p_sys, arcname=f"host_etc/{sys_item}")

            # 6. Custom Paths
            if custom_paths and isinstance(custom_paths, list):
                for cp in custom_paths:
                    cp_clean = str(cp).strip()
                    if cp_clean and not ('..' in cp_clean):
                        real_p = f"/host/root{cp_clean}" if os.path.exists(f"/host/root{cp_clean}") else cp_clean
                        if os.path.exists(real_p):
                            arc_name = f"custom{cp_clean}"
                            tar.add(real_p, arcname=arc_name)
                            components_included.append(f"Custom: {cp_clean}")

            # 7. Tanamkan manifest.json
            manifest = {
                'id': filename,
                'name': custom_name or 'Disaster Recovery Snapshot',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'hostname': socket.gethostname(),
                'kernel': platform.release(),
                'components': components_included
            }
            manifest_bytes = json.dumps(manifest, indent=2).encode('utf-8')
            manifest_info = tarfile.TarInfo(name='manifest.json')
            manifest_info.size = len(manifest_bytes)
            manifest_info.mtime = int(time.time())
            tar.addfile(manifest_info, io.BytesIO(manifest_bytes))

        stat_new = os.stat(filepath)
        audit_log('BACKUP_CREATED', f"Disaster Recovery Snapshot dibuat: {filename} ({format_bytes(stat_new.st_size)})", session.get('username'))

        # Sinkronisasi Rclone otomatis jika diminta
        sync_result = None
        if sync_remote:
            r_info = _get_rclone_info()
            if r_info['installed'] and sync_remote in r_info['remotes']:
                rc, out, err = _run_rclone_cmd(['copy', filepath, f"{sync_remote}:eka_backups/"], timeout=90)
                if rc == 0:
                    sync_meta = _load_backup_sync_meta()
                    sync_meta['synced_files'][filename] = {
                        'remote': sync_remote,
                        'synced_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    sync_meta['last_sync'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    _save_backup_sync_meta(sync_meta)
                    sync_result = f"Berhasil diunggah ke remote {sync_remote}"
                else:
                    sync_result = f"Gagal sinkronisasi remote: {err or out}"

        return jsonify({
            'success': True,
            'filename': filename,
            'size': format_bytes(stat_new.st_size),
            'components': components_included,
            'sync_result': sync_result,
            'message': 'Disaster Recovery Snapshot berhasil dibuat'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/backup/inspect/<backup_id>')
@login_required
def inspect_backup(backup_id):
    """Melihat daftar file dan struktur arsip backup sebelum restore"""
    try:
        if '..' in backup_id or '/' in backup_id or '\\' in backup_id:
            return jsonify({'success': False, 'error': 'Invalid backup ID'}), 400

        filepath = os.path.join(BACKUP_DIR, backup_id)
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'Backup tidak ditemukan'}), 404

        res = _inspect_tarball(filepath)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/backup/restore', methods=['POST'])
@login_required
@admin_required
def restore_backup():
    """Memulihkan sistem dari snapshot backup secara granular"""
    try:
        import tarfile

        data = request.json or {}
        backup_id = data.get('id', '')

        if '..' in backup_id or '/' in backup_id or '\\' in backup_id:
            return jsonify({'success': False, 'error': 'Invalid backup ID'}), 400

        filepath = os.path.join(BACKUP_DIR, backup_id)
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'Backup tidak ditemukan'}), 404

        restored_items = []

        with tarfile.open(filepath, 'r:gz') as tar:
            for member in tar.getmembers():
                # 1. Dashboard config
                if member.name == 'dashboard/settings.json':
                    member.name = 'settings.json'
                    tar.extract(member, DATA_DIR)
                    restored_items.append('settings.json')
                elif member.name == 'dashboard/security_config.json':
                    member.name = 'security_config.json'
                    tar.extract(member, BASE_DIR)
                    restored_items.append('security_config.json')
                elif member.name == 'dashboard/alert_config.json':
                    member.name = 'alert_config.json'
                    tar.extract(member, DATA_DIR)
                    restored_items.append('alert_config.json')

                # 2. Docker compose
                elif member.name == 'docker/docker-compose.yml':
                    member.name = 'docker-compose.yml'
                    tar.extract(member, BASE_DIR)
                    restored_items.append('docker-compose.yml')

                # 3. Users database
                elif member.name == 'users/users.db':
                    member.name = 'users.db'
                    tar.extract(member, DATA_DIR)
                    restored_items.append('users.db')

                # Legacy compatibility
                elif member.name == 'settings.json':
                    tar.extract(member, DATA_DIR)
                    restored_items.append('settings.json')
                elif member.name == 'docker-compose.yml':
                    tar.extract(member, BASE_DIR)
                    restored_items.append('docker-compose.yml')
                elif member.name == 'users.db':
                    tar.extract(member, DATA_DIR)
                    restored_items.append('users.db')

        audit_log('BACKUP_RESTORED', f'Backup di-restore: {backup_id} ({len(restored_items)} items)', session.get('username'))
        return jsonify({
            'success': True,
            'restored_items': restored_items,
            'message': 'Pemulihan snapshot berhasil dieksekusi'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/backup/delete/<backup_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_backup(backup_id):
    """Menghapus file snapshot backup"""
    try:
        if '..' in backup_id or '/' in backup_id or '\\' in backup_id:
            return jsonify({'success': False, 'error': 'Invalid backup ID'}), 400

        filepath = os.path.join(BACKUP_DIR, backup_id)
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'Backup tidak ditemukan'}), 404

        os.remove(filepath)

        # Bersihkan metadata sinkronisasi jika ada
        sync_meta = _load_backup_sync_meta()
        if backup_id in sync_meta.get('synced_files', {}):
            del sync_meta['synced_files'][backup_id]
            _save_backup_sync_meta(sync_meta)

        audit_log('BACKUP_DELETED', f'Backup dihapus: {backup_id}', session.get('username'))
        return jsonify({
            'success': True,
            'message': 'Snapshot backup berhasil dihapus'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/backup/download/<backup_id>')
@login_required
def download_backup(backup_id):
    """Download berkas arsip backup tar.gz"""
    try:
        if '..' in backup_id or '/' in backup_id or '\\' in backup_id:
            return jsonify({'error': 'Invalid backup ID'}), 400

        filepath = os.path.join(BACKUP_DIR, backup_id)
        if not os.path.exists(filepath):
            return jsonify({'error': 'Backup tidak ditemukan'}), 404

        from flask import send_file
        return send_file(filepath, as_attachment=True, download_name=backup_id)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/backup/rclone/status')
@login_required
def api_backup_rclone_status():
    """Memeriksa status rclone host dan daftar remotes"""
    info = _get_rclone_info()
    sync_meta = _load_backup_sync_meta()
    return jsonify({
        'success': True,
        'rclone': info,
        'sync_meta': sync_meta
    })


@app.route('/api/backup/rclone/install', methods=['POST'])
@login_required
@admin_required
def api_backup_rclone_install():
    """Menginstal rclone pada host secara lintas distro (apt/dnf/yum/pacman/apk/zypper)"""
    try:
        pm = _detect_package_manager()
        cmd = _build_pkg_install_cmd(pm, 'rclone')
        if not cmd:
            return jsonify({
                'success': False,
                'error': 'Package manager distro tidak terdeteksi. Silakan pasang rclone manual via https://rclone.org/install/'
            }), 400
        res = _run_host_cmd(cmd, timeout=180, include_pid=False)
        if res.returncode == 0:
            audit_log('RCLONE_INSTALLED', f'Rclone berhasil dipasang pada host via {pm}', session.get('username'))
            return jsonify({'success': True, 'message': f'Rclone berhasil dipasang pada host melalui {pm.upper()}!'})
        return jsonify({'success': False, 'error': res.stderr or res.stdout or f'Gagal memasang rclone via {pm}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/backup/rclone/sync', methods=['POST'])
@login_required
@admin_required
def api_backup_rclone_sync():
    """Sinkronisasi snapshot lokal ke remote cloud tujuan via Rclone"""
    data = request.json or {}
    remote_name = data.get('remote')
    backup_id = data.get('backup_id')

    if not remote_name:
        return jsonify({'success': False, 'error': 'Nama remote tidak boleh kosong'}), 400

    r_info = _get_rclone_info()
    if not r_info['installed']:
        return jsonify({'success': False, 'error': 'Rclone belum terpasang pada host'}), 400

    if remote_name not in r_info['remotes']:
        return jsonify({'success': False, 'error': f"Remote '{remote_name}' tidak ditemukan di rclone listremotes"}), 404

    target_dest = f"{remote_name}:eka_backups/"

    if backup_id:
        if '..' in backup_id or '/' in backup_id or '\\' in backup_id:
            return jsonify({'success': False, 'error': 'Invalid backup ID'}), 400
        src_path = os.path.join(BACKUP_DIR, backup_id)
        if not os.path.exists(src_path):
            return jsonify({'success': False, 'error': 'Berkas backup tidak ditemukan'}), 404
        cmd_args = ['copy', src_path, target_dest]
    else:
        cmd_args = ['copy', BACKUP_DIR, target_dest]

    rc, out, err = _run_rclone_cmd(cmd_args, timeout=180)
    if rc == 0:
        sync_meta = _load_backup_sync_meta()
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sync_meta['last_sync'] = now_str
        sync_meta['active_remote'] = remote_name

        if backup_id:
            sync_meta['synced_files'][backup_id] = {'remote': remote_name, 'synced_at': now_str}
        else:
            if os.path.exists(BACKUP_DIR):
                for f in os.listdir(BACKUP_DIR):
                    if f.endswith('.tar.gz'):
                        sync_meta['synced_files'][f] = {'remote': remote_name, 'synced_at': now_str}

        _save_backup_sync_meta(sync_meta)
        audit_log('BACKUP_RCLONE_SYNC', f"Backup disinkronkan ke remote '{remote_name}'", session.get('username'))
        return jsonify({
            'success': True,
            'message': f"Sinkronisasi ke remote '{remote_name}' berhasil diselesaikan!",
            'last_sync': now_str
        })
    return jsonify({
        'success': False,
        'error': f"Rclone error (code {rc}): {err or out}"
    }), 500


@app.route('/api/backup/schedule', methods=['GET', 'POST'])
@login_required
@admin_required
def api_backup_schedule():
    """Mengambil atau menyimpan jadwal backup otomatis"""
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'schedule': _load_backup_schedule()
        })

    data = request.json or {}
    sched = _load_backup_schedule()
    sched['enabled'] = bool(data.get('enabled', False))
    sched['frequency'] = str(data.get('frequency', 'daily'))
    sched['time'] = str(data.get('time', '02:00'))
    sched['remote'] = data.get('remote')
    if 'scope' in data and isinstance(data['scope'], dict):
        sched['scope'] = data['scope']

    _save_backup_schedule(sched)
    audit_log('BACKUP_SCHEDULE_UPDATED', f"Jadwal backup otomatis diubah (Enabled: {sched['enabled']})", session.get('username'))
    return jsonify({
        'success': True,
        'schedule': sched,
        'message': 'Jadwal backup otomatis berhasil diperbarui'
    })


@app.route('/api/backup/cron_trigger', methods=['POST'])
def api_backup_cron_trigger():
    """Endpoint internal untuk memicu backup otomatis terjadwal (hanya loopback atau admin)."""
    is_local = (request.remote_addr in ('127.0.0.1', '::1'))
    is_admin = bool(session.get('logged_in') and session.get('role') in ('owner', 'admin'))
    if not (is_local or is_admin):
        return jsonify({'error': 'Forbidden'}), 403
    sched = _load_backup_schedule()
    if not sched.get('enabled'):
        return jsonify({'success': False, 'message': 'Backup otomatis sedang dinonaktifkan'}), 200

    scope = sched.get('scope', {})
    res_fake = create_backup.__wrapped__() if hasattr(create_backup, '__wrapped__') else None
    return jsonify({'success': True, 'triggered': True})
# ==========================================


# ============ SMB/SAMBA FILE SHARING ============
def _get_smb_conf_path():
    """Mendapatkan path file konfigurasi smb.conf (container vs host)"""
    if os.path.exists('/host/root/etc/samba/smb.conf'):
        return '/host/root/etc/samba/smb.conf'
    return '/etc/samba/smb.conf'

@app.route('/sharing')
@login_required
@admin_required
def sharing_page():
    """Halaman berbagi file SMB"""
    return render_template('sharing.html')

@app.route('/api/smb/status')
@login_required
def get_smb_status():
    """Mendapatkan status Samba host beserta IP akses secara universal (Docker & Native Linux)."""
    try:
        installed = False
        running = False
        version = 'Not Installed'

        # 1. Cek instalasi dan status daemon lintas mode (Docker nsenter / Native Linux)
        res_which = _run_host_cmd(['which', 'smbd'], timeout=4, include_pid=False)
        installed = (res_which.returncode == 0)

        if installed:
            version = 'Samba'
            res_status = _run_systemctl(['is-active', 'smbd'], timeout=4)
            running = (res_status.stdout.strip() == 'active')
            if not running:
                res_alt = _run_systemctl(['is-active', 'smb'], timeout=4)
                running = (res_alt.stdout.strip() == 'active')
            if not running:
                res_pg = _run_host_cmd(['pgrep', '-x', 'smbd'], timeout=3, include_pid=False)
                running = (res_pg.returncode == 0)

            res_ver = _run_host_cmd(['smbd', '-V'], timeout=4, include_pid=False)
            if res_ver.returncode == 0 and res_ver.stdout.strip():
                version = res_ver.stdout.strip()
        else:
            conf_path = _get_smb_conf_path()
            if os.path.exists(conf_path):
                res_pg = _run_host_cmd(['pgrep', '-x', 'smbd'], timeout=3, include_pid=False)
                if res_pg.returncode == 0:
                    installed = True
                    running = True
                    version = 'Samba'

        # 2. Dapatkan IP Host (LAN, Tailscale, Hostname)
        lan_ip = ''
        ts_ip = ''
        hostname = socket.gethostname()
        h_res = _run_host_cmd(['hostname'], timeout=3, include_pid=False)
        if h_res.returncode == 0 and h_res.stdout.strip():
            hostname = h_res.stdout.strip()

        res_ip = _run_host_cmd(['ip', '-j', 'addr', 'show'], timeout=4, include_pid=False)
        if res_ip.returncode == 0 and res_ip.stdout.strip():
            try:
                data_ip = json.loads(res_ip.stdout)
                for iface in data_ip:
                    if iface.get('ifname') == 'lo':
                        continue
                    for addr_info in iface.get('addr_info', []):
                        if addr_info.get('family') == 'inet':
                            ip_addr = addr_info.get('local', '')
                            if (ip_addr.startswith('192.168.') or ip_addr.startswith('10.') or ip_addr.startswith('172.')) \
                               and not ip_addr.startswith('172.17.') and not ip_addr.startswith('172.18.'):
                                if not lan_ip:
                                    lan_ip = ip_addr
                            elif ip_addr.startswith('100.'):
                                if not ts_ip:
                                    ts_ip = ip_addr
            except Exception:
                pass

        server_ip = lan_ip or ts_ip or '127.0.0.1'

        return jsonify({
            'installed': installed,
            'available': installed,
            'running': running,
            'version': version,
            'lan_ip': lan_ip,
            'ts_ip': ts_ip,
            'hostname': hostname,
            'server_ip': server_ip
        })
    except Exception as e:
        return jsonify({
            'installed': False,
            'available': False,
            'running': False,
            'version': 'Not Installed',
            'lan_ip': '',
            'ts_ip': '',
            'hostname': socket.gethostname(),
            'server_ip': '127.0.0.1',
            'error': str(e)
        })

@app.route('/api/smb/shares')
@login_required
def get_smb_shares():
    """Mendapatkan daftar share aktif dari smb.conf"""
    try:
        shares = []
        conf_path = _get_smb_conf_path()
        
        if os.path.exists(conf_path):
            with open(conf_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Match [sharename] sections (exclude global, homes, printers, print$)
            pattern = r'\[([^\]]+)\]\s*\n([^[]*)'
            matches = re.findall(pattern, content)
            
            for name, block in matches:
                clean_name = name.strip()
                if clean_name.lower() in ['global', 'homes', 'printers', 'print$']:
                    continue
                
                path_match = re.search(r'path\s*=\s*(.+)', block)
                if not path_match:
                    continue
                path = path_match.group(1).strip()
                
                comment_match = re.search(r'comment\s*=\s*(.+)', block)
                comment = comment_match.group(1).strip() if comment_match else ''
                
                ro_match = re.search(r'read\s+only\s*=\s*(yes|no|true|false)', block, re.I)
                read_only = (ro_match.group(1).lower() in ['yes', 'true']) if ro_match else False
                
                guest_match = re.search(r'guest\s+ok\s*=\s*(yes|no|true|false)', block, re.I)
                guest_ok = (guest_match.group(1).lower() in ['yes', 'true']) if guest_match else False
                
                shares.append({
                    'name': clean_name,
                    'path': path,
                    'comment': comment,
                    'read_only': read_only,
                    'guest_ok': guest_ok
                })
        
        return jsonify({'shares': shares})
    except Exception as e:
        return jsonify({'error': str(e), 'shares': []}), 500

@app.route('/api/smb/sessions')
@login_required
def get_smb_sessions():
    """Mendapatkan daftar sesi klien SMB yang sedang terhubung secara universal"""
    try:
        res = _run_host_cmd(['smbstatus', '-b'], timeout=5, include_pid=False)
        sessions = []
        installed = (res.returncode == 0)
        if res.returncode == 0:
            lines = res.stdout.strip().split('\n')
            dashed_found = False
            for line in lines:
                if '---' in line:
                    dashed_found = True
                    continue
                if dashed_found and line.strip():
                    parts = line.split()
                    if len(parts) >= 4:
                        sessions.append({
                            'pid': parts[0],
                            'username': parts[1],
                            'group': parts[2],
                            'machine': parts[3],
                            'protocol': parts[4] if len(parts) > 4 else 'SMB',
                            'encryption': parts[5] if len(parts) > 5 else '-',
                            'signing': parts[6] if len(parts) > 6 else '-'
                        })
        return jsonify({'installed': installed, 'sessions': sessions, 'count': len(sessions)})
    except Exception as e:
        return jsonify({'installed': False, 'sessions': [], 'count': 0, 'error': str(e)})

@app.route('/api/smb/share/add', methods=['POST'])
@login_required
@admin_required
def add_smb_share():
    """Menambahkan share baru ke Samba"""
    try:
        data = request.json or {}
        name = data.get('name', '').strip()
        path = data.get('path', '').strip()
        description = data.get('description', '').strip()
        is_public = data.get('public', True)
        writable = data.get('writable', True)
        
        if not name or not path:
            return jsonify({'error': 'Nama dan path harus diisi'}), 400
        
        # Validasi nama (alphanumeric, underscore, dash)
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            return jsonify({'error': 'Nama hanya boleh berupa huruf, angka, underscore, dan dash'}), 400
        
        # Cek dan buat direktori di host jika belum ada
        container_path = '/host/root' + path if os.path.exists('/host/root') else path
        if not os.path.exists(container_path):
            try:
                os.makedirs(container_path, exist_ok=True)
            except Exception as e:
                return jsonify({'error': f'Path tidak ada dan tidak dapat dibuat di host: {str(e)}'}), 400
        
        conf_path = _get_smb_conf_path()
        if not os.path.exists(conf_path):
            return jsonify({'error': 'Berkas konfigurasi Samba (smb.conf) tidak ditemukan'}), 404
            
        # Periksa duplikasi nama share
        with open(conf_path, 'r', encoding='utf-8', errors='ignore') as f:
            existing = f.read()
        if re.search(rf'\[{re.escape(name)}\]', existing, re.I):
            return jsonify({'error': f'Share dengan nama "{name}" sudah ada'}), 400
        
        # Buat blok konfigurasi share
        share_config = f"""
[{name}]
   comment = {description or name}
   path = {path}
   browseable = yes
   read only = {'no' if writable else 'yes'}
   guest ok = {'yes' if is_public else 'no'}
   create mask = 0775
   directory mask = 0775
"""
        
        with open(conf_path, 'a', encoding='utf-8') as f:
            f.write(share_config)
        
        # Reload Samba daemon di host
        nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
        subprocess.run(nsenter + ['systemctl', 'reload', 'smbd'], capture_output=True, text=True, timeout=10)
        
        audit_log('SMB_SHARE_ADDED', f'Share ditambahkan: {name} -> {path}', session.get('username'))
        return jsonify({'success': True, 'message': 'Share berhasil ditambahkan'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/smb/share/remove', methods=['DELETE'])
@login_required
@admin_required
def remove_smb_share():
    """Menghapus share dari Samba"""
    try:
        data = request.json or {}
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'error': 'Nama share diperlukan'}), 400
        
        conf_path = _get_smb_conf_path()
        if not os.path.exists(conf_path):
            return jsonify({'error': 'Berkas konfigurasi Samba tidak ditemukan'}), 404
        
        with open(conf_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Hapus section share target
        pattern = rf'\[{re.escape(name)}\][^\[]*'
        new_content = re.sub(pattern, '', content)
        
        with open(conf_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # Reload Samba daemon di host
        nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
        subprocess.run(nsenter + ['systemctl', 'reload', 'smbd'], capture_output=True, text=True, timeout=10)
        
        audit_log('SMB_SHARE_REMOVED', f'Share dihapus: {name}', session.get('username'))
        return jsonify({'success': True, 'message': 'Share berhasil dihapus'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/smb/control', methods=['POST'])
@login_required
@admin_required
def control_smb():
    """Start/stop/restart Samba service di host"""
    try:
        data = request.json or {}
        action = data.get('action', '').strip().lower()
        
        if action not in ['start', 'stop', 'restart', 'reload']:
            return jsonify({'error': 'Action tidak valid'}), 400
        
        nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
        result = subprocess.run(nsenter + ['systemctl', action, 'smbd'], capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return jsonify({'error': f'Gagal {action} Samba: {result.stderr or result.stdout}'}), 500
        
        audit_log('SMB_CONTROL', f'Samba di-{action}', session.get('username'))
        return jsonify({'success': True, 'message': f'Samba berhasil di-{action}'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# ================================================


# ============ VPN (TAILSCALE, WIREGUARD, ZEROTIER) ============
@app.route('/api/vpn/tailscale/status')
@login_required
def tailscale_status():
    """Mendapatkan status Tailscale node dan daftar peer terhubung secara universal"""
    try:
        check = _run_host_cmd(['which', 'tailscale'], timeout=3, include_pid=False)
        installed = (check.returncode == 0)
        
        if not installed:
            return jsonify({
                'installed': False,
                'available': False,
                'running': False,
                'self': {},
                'peers': [],
                'peer_count': 0,
                'online_count': 0
            })
            
        res = _run_host_cmd(['tailscale', 'status', '--json'], timeout=5, include_pid=False)
        if res.returncode != 0 or not (res.stdout or '').strip():
            return jsonify({
                'installed': True,
                'available': True,
                'running': False,
                'self': {},
                'peers': [],
                'peer_count': 0,
                'online_count': 0
            })
            
        data = json.loads(res.stdout)
        self_node = data.get('Self', {})
        backend_state = data.get('BackendState', 'Stopped')
        running = (backend_state == 'Running' and self_node.get('Online', False))
        
        self_info = {
            'hostname': self_node.get('HostName', 'Unknown'),
            'dns_name': self_node.get('DNSName', '').rstrip('.'),
            'ips': self_node.get('TailscaleIPs', []),
            'primary_ip': self_node.get('TailscaleIPs', ['N/A'])[0] if self_node.get('TailscaleIPs') else 'N/A',
            'online': self_node.get('Online', False),
            'os': self_node.get('OS', 'linux'),
            'relay': self_node.get('Relay', ''),
            'version': data.get('Version', '')
        }
        
        peers_dict = data.get('Peer', {})
        peers_list = []
        online_count = 0
        
        for pid, p in peers_dict.items():
            hostname = p.get('HostName') or 'Unknown'
            ips = p.get('TailscaleIPs') or []
            if not ips:
                continue
                
            is_online = p.get('Online', False)
            is_active = p.get('Active', False)
            if is_online:
                online_count += 1
                
            cur_addr = p.get('CurAddr', '')
            conn_type = 'Direct P2P' if cur_addr else (f"DERP ({p.get('Relay', 'Relay')})" if p.get('Relay') else 'Idle')
            
            os_name = (p.get('OS') or '').lower()
            if 'android' in os_name:
                os_type = 'android'
            elif 'windows' in os_name:
                os_type = 'windows'
            elif 'darwin' in os_name or 'ios' in os_name or 'mac' in os_name:
                os_type = 'apple'
            else:
                os_type = 'linux'
                
            peers_list.append({
                'id': pid,
                'name': hostname,
                'dns_name': p.get('DNSName', '').rstrip('.'),
                'ip': ips[0],
                'ips': ips,
                'os': os_type,
                'online': is_online,
                'active': is_active,
                'conn_type': conn_type,
                'cur_addr': cur_addr,
                'rx_bytes': p.get('RxBytes', 0),
                'tx_bytes': p.get('TxBytes', 0),
                'last_seen': p.get('LastSeen', '')
            })
            
        peers_list.sort(key=lambda x: (not x['active'], not x['online'], x['name'].lower()))
        
        return jsonify({
            'installed': True,
            'available': True,
            'running': running,
            'backend_state': backend_state,
            'self': self_info,
            'peers': peers_list,
            'peer_count': len(peers_list),
            'online_count': online_count
        })
    except Exception as e:
        return jsonify({
            'installed': False,
            'available': False,
            'running': False,
            'self': {},
            'peers': [],
            'peer_count': 0,
            'online_count': 0,
            'error': str(e)
        })

@app.route('/api/vpn/tailscale/ping', methods=['POST'])
@login_required
def tailscale_ping():
    """Uji konektivitas Tailscale Ping ke peer target"""
    data = request.json or {}
    target = data.get('target', '').strip()
    
    if not target:
        return jsonify({'error': 'Target tidak boleh kosong'}), 400
        
    if not re.match(r'^[a-zA-Z0-9.-]+$', target):
        return jsonify({'error': 'Format target tidak valid'}), 400
        
    try:
        res = _run_host_cmd(['tailscale', 'ping', '--timeout', '2s', '-c', '2', target], timeout=8, include_pid=False)
        output = (res.stdout or '') + (res.stderr or '')
        
        latency_match = re.search(r'in (\d+(?:\.\d+)?m?s)', output)
        latency = latency_match.group(1) if latency_match else None
        
        via_match = re.search(r'via ([^\s]+)', output)
        via = via_match.group(1) if via_match else None
        
        reachable = bool(latency and res.returncode == 0)
        
        if reachable:
            return jsonify({
                'success': True,
                'reachable': True,
                'target': target,
                'latency': latency,
                'via': via or 'Direct P2P',
                'output': output
            })
        else:
            return jsonify({
                'success': False,
                'reachable': False,
                'target': target,
                'latency': None,
                'via': None,
                'message': 'Peer tidak merespons (Timeout / Peer offline atau dalam mode tidur)',
                'output': output.strip() or 'no reply'
            })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'reachable': False,
            'target': target,
            'latency': None,
            'via': None,
            'message': 'Uji koneksi timeout setelah 8 detik (Peer tidak merespons)',
            'output': 'timeout'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'reachable': False,
            'target': target,
            'latency': None,
            'via': None,
            'message': f'Gagal mengeksekusi ping: {str(e)}',
            'output': str(e)
        }), 500

WG_CONFIG_DIR = '/etc/wireguard'
WG_INTERFACE = 'wg0'

@app.route('/vpn')
@login_required
@admin_required
def vpn_page():
    """Halaman VPN Manager"""
    return render_template('vpn.html')

@app.route('/api/vpn/status')
@login_required
def get_vpn_status():
    """Mendapatkan status WireGuard secara universal (Docker & Native Linux)"""
    try:
        result = _run_host_cmd(['which', 'wg'], timeout=3, include_pid=False)
        installed = result.returncode == 0
        
        running = False
        server_ip = ''
        port = '51820'
        client_count = 0
        
        if installed:
            status = _run_host_cmd(['wg', 'show', WG_INTERFACE], timeout=4, include_pid=False)
            running = status.returncode == 0
            
            if running:
                for line in status.stdout.split('\n'):
                    if 'listening port' in line:
                        port = line.split(':')[-1].strip()
                    if 'peer:' in line:
                        client_count += 1
        
        # Dapatkan IP server
        try:
            net_info = psutil.net_if_addrs()
            for iface, addrs in net_info.items():
                if iface == 'lo' or iface.startswith('wg'):
                    continue
                for addr in addrs:
                    if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                        server_ip = addr.address
                        break
                if server_ip:
                    break
        except Exception:
            pass
        
        return jsonify({
            'installed': installed,
            'available': installed,
            'running': running,
            'server_ip': server_ip,
            'port': port,
            'client_count': client_count
        })
    except Exception as e:
        return jsonify({'installed': False, 'available': False, 'running': False, 'server_ip': '', 'port': '51820', 'client_count': 0, 'error': str(e)})

@app.route('/api/vpn/clients')
@login_required
def get_vpn_clients():
    """Mendapatkan daftar client VPN"""
    try:
        clients = []
        clients_dir = os.path.join(WG_CONFIG_DIR, 'clients')
        
        if os.path.exists(clients_dir):
            for filename in os.listdir(clients_dir):
                if filename.endswith('.conf'):
                    client_name = filename.replace('.conf', '')
                    
                    # Coba baca IP dari file config
                    client_ip = ''
                    config_path = os.path.join(clients_dir, filename)
                    try:
                        with open(config_path, 'r') as f:
                            for line in f:
                                if line.strip().startswith('Address'):
                                    client_ip = line.split('=')[1].strip()
                                    break
                    except:
                        pass
                    
                    clients.append({
                        'name': client_name,
                        'ip': client_ip
                    })
        
        return jsonify({'clients': clients})
    except Exception as e:
        return jsonify({'error': str(e), 'clients': []}), 500

@app.route('/api/vpn/client/add', methods=['POST'])
@login_required
@admin_required
def add_vpn_client():
    """Membuat client VPN baru"""
    try:
        data = request.json
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'error': 'Nama client harus diisi'}), 400
        
        # Validasi nama
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            return jsonify({'error': 'Nama hanya boleh huruf, angka, underscore, dan dash'}), 400
        
        clients_dir = os.path.join(WG_CONFIG_DIR, 'clients')
        os.makedirs(clients_dir, exist_ok=True)
        
        # Cek apakah client sudah ada
        config_path = os.path.join(clients_dir, f'{name}.conf')
        if os.path.exists(config_path):
            return jsonify({'error': 'Client dengan nama ini sudah ada'}), 400
        
        # Generate keys
        # Generate keys via nsenter (Host)
        nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
        # Gen private key
        private_key = subprocess.run(nsenter + ['wg', 'genkey'], capture_output=True, text=True).stdout.strip()
        # Gen public key (pipe private key)
        public_key = subprocess.run(nsenter + ['wg', 'pubkey'], input=private_key, capture_output=True, text=True).stdout.strip()
        
        # Baca server public key
        server_public_key = ''
        server_config = os.path.join(WG_CONFIG_DIR, f'{WG_INTERFACE}.conf')
        if os.path.exists(server_config):
            with open(server_config, 'r') as f:
                for line in f:
                    if 'PrivateKey' in line:
                        server_private = line.split('=')[1].strip()
                        # Public key via nsenter
                        server_public_key = subprocess.run(nsenter + ['wg', 'pubkey'], input=server_private, capture_output=True, text=True).stdout.strip()
                        break
        
        # Dapatkan IP server (HOST IP) via nsenter
        server_ip = ''
        try:
            # Use hostname -I on host
            res = subprocess.run(nsenter + ['hostname', '-I'], capture_output=True, text=True)
            ips = res.stdout.strip().split()
            if ips:
                server_ip = ips[0]
        except:
            pass
            
        if not server_ip:
            server_ip = 'YOUR_SERVER_IP'
        
        # Hitung IP untuk client baru (simplistik)
        existing_clients = len([f for f in os.listdir(clients_dir) if f.endswith('.conf')]) if os.path.exists(clients_dir) else 0
        client_ip = f'10.66.66.{existing_clients + 2}/32'
        
        # Buat config client
        client_config = f"""[Interface]
PrivateKey = {private_key}
Address = {client_ip}
DNS = 1.1.1.1

[Peer]
PublicKey = {server_public_key}
Endpoint = {server_ip}:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""
        
        # Simpan config
        with open(config_path, 'w') as f:
            f.write(client_config)
        
        # Tambahkan peer ke server config
        with open(server_config, 'a') as f:
            f.write(f"""
[Peer]
# {name}
PublicKey = {public_key}
AllowedIPs = {client_ip.replace('/32', '/32')}
""")
        
        # Reload WireGuard via nsenter
        nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
        subprocess.run(nsenter + ['wg-quick', 'down', WG_INTERFACE], capture_output=True)
        subprocess.run(nsenter + ['wg-quick', 'up', WG_INTERFACE], capture_output=True)
        
        audit_log('VPN_CLIENT_ADDED', f'Client VPN ditambahkan: {name}', session.get('username'))
        
        return jsonify({
            'success': True,
            'config': client_config,
            'message': 'Client berhasil dibuat'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vpn/client/<name>/config')
@login_required
def get_vpn_client_config(name):
    """Mendapatkan konfigurasi client"""
    try:
        config_path = os.path.join(WG_CONFIG_DIR, 'clients', f'{name}.conf')
        
        if not os.path.exists(config_path):
            return jsonify({'error': 'Client tidak ditemukan'}), 404
        
        with open(config_path, 'r') as f:
            config = f.read()
        
        return jsonify({'config': config})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vpn/client/remove', methods=['DELETE'])
@login_required
@admin_required
def remove_vpn_client():
    """Menghapus client VPN"""
    try:
        data = request.json
        name = data.get('name', '')
        
        config_path = os.path.join(WG_CONFIG_DIR, 'clients', f'{name}.conf')
        
        if not os.path.exists(config_path):
            return jsonify({'error': 'Client tidak ditemukan'}), 404
        
        os.remove(config_path)
        
        # TODO: Hapus peer dari server config (lebih kompleks)
        
        audit_log('VPN_CLIENT_REMOVED', f'Client VPN dihapus: {name}', session.get('username'))
        
        return jsonify({'success': True, 'message': 'Client berhasil dihapus'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vpn/control', methods=['POST'])
@login_required
@admin_required
def control_vpn():
    """Start/stop WireGuard"""
    try:
        data = request.json
        action = data.get('action', '')
        
        nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
        if action == 'start':
            result = subprocess.run(nsenter + ['wg-quick', 'up', WG_INTERFACE], capture_output=True, text=True)
        elif action == 'stop':
            result = subprocess.run(nsenter + ['wg-quick', 'down', WG_INTERFACE], capture_output=True, text=True)
        else:
            return jsonify({'error': 'Action tidak valid'}), 400
        
        if result.returncode != 0:
            return jsonify({'error': f'Gagal {action}: {result.stderr}'}), 500
        
        audit_log('VPN_CONTROL', f'VPN di-{action}', session.get('username'))
        
        return jsonify({'success': True, 'message': f'VPN berhasil di-{action}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vpn/install', methods=['POST'])
@login_required
@admin_required
def install_vpn():
    """Install dan setup WireGuard"""
    try:
        # Update package list first
        subprocess.run(
            ['apt-get', 'update'],
            capture_output=True, text=True, timeout=120
        )
        
        # Install wireguard
        result = subprocess.run(
            ['apt-get', 'install', '-y', 'wireguard'],
            capture_output=True, text=True, timeout=300
        )
        
        if result.returncode != 0:
            return jsonify({'error': f'Gagal install: {result.stderr}'}), 500
        
        # Generate server keys
        os.makedirs(WG_CONFIG_DIR, exist_ok=True)
        
        private_key = subprocess.run(['wg', 'genkey'], capture_output=True, text=True).stdout.strip()
        
        # Dapatkan IP server
        server_ip = ''
        try:
            net_info = psutil.net_if_addrs()
            for iface, addrs in net_info.items():
                if iface == 'lo':
                    continue
                for addr in addrs:
                    if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                        server_ip = addr.address
                        break
                if server_ip:
                    break
        except:
            pass
        
        # Buat server config
        server_config = f"""[Interface]
PrivateKey = {private_key}
Address = 10.66.66.1/24
ListenPort = 51820
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
"""
        
        with open(os.path.join(WG_CONFIG_DIR, f'{WG_INTERFACE}.conf'), 'w') as f:
            f.write(server_config)
        
        # Enable IP forwarding
        subprocess.run(['sysctl', '-w', 'net.ipv4.ip_forward=1'], capture_output=True)
        
        # Start WireGuard
        subprocess.run(['wg-quick', 'up', WG_INTERFACE], capture_output=True)
        subprocess.run(['systemctl', 'enable', f'wg-quick@{WG_INTERFACE}'], capture_output=True)
        
        audit_log('VPN_INSTALLED', 'WireGuard berhasil diinstall', session.get('username'))
        
        return jsonify({'success': True, 'message': 'WireGuard berhasil diinstall'})
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout saat install'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# ==========================================


# ============ APP STORE ============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CATALOG_FILE = os.path.join(DATA_DIR, 'app_catalog.json')
USER_CATALOG_FILE = os.path.join(DATA_DIR, 'user_apps.json')

@app.route('/store')
@login_required
@admin_required
def store_page():
    """Halaman App Store"""
    return render_template('store.html')

_NON_HTTP_PORTS = {'53', '22', '3306', '5432', '6379', '27017', '1883', '6881', '51413', '784', '853', '11434', '51820', '22000', '21027'}


def _load_store_catalog(include_user=True):
    """Load default + user custom App Store catalog and resolve dynamic placeholders like {{AUTO_TZ}}."""
    catalog = []
    target = CATALOG_FILE
    if not os.path.exists(target):
        fallback_path = os.path.join(os.getcwd(), 'data', 'app_catalog.json')
        if os.path.exists(fallback_path):
            target = fallback_path

    if os.path.exists(target):
        with open(target, 'r', encoding='utf-8') as f:
            catalog = json.load(f)

    if include_user and os.path.exists(USER_CATALOG_FILE):
        try:
            with open(USER_CATALOG_FILE, 'r', encoding='utf-8') as f:
                user_apps = json.load(f)
                for item in user_apps:
                    item['category'] = item.get('category') or 'Custom'
                    item['is_custom'] = True
                    if not item.get('icon') or item.get('icon') == '/static/icon.png':
                        item['icon'] = '/static/icon.svg'
                catalog.extend(user_apps)
        except Exception:
            pass

    tz = 'UTC'
    try:
        tz = ((load_app_settings().get('general') or {}).get('timezone') or 'UTC').strip() or 'UTC'
    except Exception:
        pass

    resolved = []
    for item in catalog:
        entry = dict(item)
        if isinstance(entry.get('env'), list):
            new_env = []
            for e_item in entry['env']:
                ev = dict(e_item)
                if ev.get('value') == '{{AUTO_TZ}}':
                    ev['value'] = tz
                new_env.append(ev)
            entry['env'] = new_env
        resolved.append(entry)
    return resolved


def _normalize_store_volume_bind(raw_bind):
    """Normalize volume source: keep Docker Named Volumes intact, strip accidental /host/root prefix from host paths."""
    bind = str(raw_bind or '').strip()
    if not bind:
        return ''
    if bind == '/host/root':
        return '/'
    if bind.startswith('/host/root/'):
        cleaned = bind[len('/host/root'):]
        return cleaned if cleaned.startswith('/') else '/' + cleaned
    return bind


def _ensure_host_bind_dir(host_path):
    """Safely create host directory for absolute bind mounts (skipping sockets, /dev devices, and named volumes)."""
    if not host_path or not host_path.startswith('/'):
        return
    if host_path.startswith('/dev/') or host_path.endswith('.sock') or host_path == '/':
        return
    if os.path.exists('/host/root'):
        target = os.path.join('/host/root', host_path.lstrip('/'))
    else:
        target = host_path
    if not os.path.exists(target):
        try:
            os.makedirs(target, exist_ok=True)
        except Exception:
            pass


def _resolve_app_open_port(app_def, live_ports):
    """Determine accurate Web UI host port & protocol for an installed app (None for DB/CLI-only apps)."""
    if app_def.get('has_web_ui') is False:
        return None, 'http'

    ports = live_ports or []
    web_cport = app_def.get('web_port')
    if web_cport is not None:
        web_cport_str = str(web_cport)
        for p_item in ports:
            if str(p_item.get('container')) == web_cport_str and p_item.get('host'):
                proto = 'https' if web_cport_str in ('443', '8443') else 'http'
                return str(p_item['host']), proto

    for p_item in ports:
        h = str(p_item.get('host') or '').strip()
        c = str(p_item.get('container') or '').strip()
        pr = str(p_item.get('protocol') or 'tcp').lower()
        if h and h != '0' and pr != 'udp' and c not in _NON_HTTP_PORTS and h not in _NON_HTTP_PORTS:
            proto = 'https' if c in ('443', '8443') else 'http'
            return h, proto

    # Fallback for host-network Web UI apps (e.g., Home Assistant, Plex, Homebridge)
    if app_def.get('network_mode') == 'host':
        if web_cport is not None:
            proto = 'https' if str(web_cport) in ('443', '8443') else 'http'
            return str(web_cport), proto
        for p_item in (app_def.get('ports') or []):
            if p_item.get('host') and str(p_item.get('protocol', 'tcp')).lower() != 'udp':
                return str(p_item['host']), 'http'

    return None, 'http'


@app.route('/api/store/catalog')
@login_required
def get_app_catalog():
    """Mendapatkan katalog aplikasi universal (Default + Custom)"""
    try:
        catalog = _load_store_catalog(include_user=True)
        return jsonify({'catalog': catalog, 'count': len(catalog)})
    except Exception as e:
        return jsonify({'error': str(e), 'catalog': [], 'count': 0}), 500

_host_snapshot_cache = {'time': 0, 'data': (set(), set())}

def _get_host_active_snapshot():
    """Ambil set service aktif dan proses aktif di host sekaligus dalam 1 batch call (di-cache 8 detik)."""
    now = time.time()
    if now - _host_snapshot_cache['time'] < 8:
        return _host_snapshot_cache['data']

    active_services = set()
    active_procs = set()

    # 1. Batch systemctl active services (1 call)
    try:
        res = run_host_command(['systemctl', 'list-units', '--type=service', '--state=running', '--no-legend', '--no-pager'])
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                parts = line.strip().split()
                if parts:
                    unit_full = parts[0].lower()
                    unit_name = unit_full.replace('.service', '')
                    active_services.add(unit_full)
                    active_services.add(unit_name)
    except Exception:
        pass

    # 2. Batch host processes (1 call)
    try:
        res = run_host_command(['ps', '-eo', 'comm='])
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                proc = line.strip().lower()
                if proc:
                    active_procs.add(proc)
    except Exception:
        pass

    data = (active_services, active_procs)
    _host_snapshot_cache['time'] = now
    _host_snapshot_cache['data'] = data
    return data


def _detect_native_host_app(app_id, catalog_ports=None, host_snapshot=None):
    """Mendeteksi apakah aplikasi katalog berjalan sebagai service/proses native di host via O(1) in-memory lookup."""
    catalog_ports = catalog_ports or []
    if host_snapshot is None:
        host_snapshot = _get_host_active_snapshot()
    active_services, active_procs = host_snapshot
    
    # Pemetaan aplikasi katalog ke unit service / proses host yang valid (universal lintas user & interface)
    native_defs = {
        'tailscale': {
            'services': ['tailscaled', 'tailscale'],
            'service_prefixes': [],
            'procs': ['tailscaled'],
            'ports': []
        },
        'syncthing': {
            'services': ['syncthing'],
            'service_prefixes': ['syncthing@'],
            'procs': ['syncthing'],
            'ports': [{'host': '8384', 'container': '8384', 'protocol': 'tcp'}]
        },
        'wireguard': {
            'services': ['wg-quick@wg0'],
            'service_prefixes': ['wg-quick@'],
            'procs': [],
            'ports': [{'host': '51820', 'container': '51820', 'protocol': 'udp'}]
        }
    }

    cfg = native_defs.get(app_id)
    if not cfg:
        cfg = {
            'services': [app_id, f"{app_id}d"],
            'service_prefixes': [f"{app_id}@"],
            'procs': [app_id],
            'ports': []
        }

    # 1. Cek status active pada systemd service host (O(1) exact + template unit prefix)
    matched_service = False
    for s in cfg.get('services', []):
        s_low = s.lower()
        if s_low in active_services or f"{s_low}.service" in active_services:
            matched_service = True
            break
    if not matched_service:
        for pref in cfg.get('service_prefixes', []):
            p_low = pref.lower()
            if any(u.startswith(p_low) for u in active_services):
                matched_service = True
                break
    if matched_service:
        ports = cfg.get('ports') or [{'host': str(p.get('host')), 'container': str(p.get('container')), 'protocol': p.get('protocol', 'tcp')} for p in catalog_ports if p.get('host')]
        return {'running': True, 'state': 'running', 'ports': ports, 'is_native': True}

    # 2. Cek apakah ada proses aktif di host (O(1) in-memory)
    for p in cfg.get('procs', []):
        if p.lower() in active_procs:
            ports = cfg.get('ports') or [{'host': str(prt.get('host')), 'container': str(prt.get('container')), 'protocol': prt.get('protocol', 'tcp')} for prt in catalog_ports if prt.get('host')]
            return {'running': True, 'state': 'running', 'ports': ports, 'is_native': True}

    return None


_SIDECAR_TOKENS = {
    'runner', 'runners', 'worker', 'workers', 'beat', 'celery',
    'exporter', 'learning', 'scraper', 'backup', 'init', 'migrate',
    'migration', 'hbbr', 'relay'
}

_GENERIC_IMAGE_BASENAMES = {
    'app', 'web', 'server', 'api', 'service', 'latest', 'main', 'core', 'db', 'database'
}

_GENERIC_CONTAINER_SUFFIXES = {
    'container', 'app', 'server', 'web', 'service', 'main', 'instance', 'hub'
}


def _normalize_image_repo(image_str):
    """Normalize Docker image string to canonical lowercase repository path without registry/tag/digest."""
    img = str(image_str or '').strip().lower()
    if not img:
        return ''
    if '@' in img:
        img = img.split('@', 1)[0]
    last_slash = img.rfind('/')
    last_colon = img.rfind(':')
    if last_colon > last_slash:
        img = img[:last_colon]
    parts = [p for p in img.split('/') if p]
    if not parts:
        return ''
    if len(parts) > 1 and ('.' in parts[0] or ':' in parts[0] or parts[0] == 'localhost'):
        parts = parts[1:]
    if len(parts) == 2 and parts[0] == 'library':
        parts = [parts[1]]
    return '/'.join(parts)


def _extract_container_record(c):
    """Extract normalized container metadata (name, image_repo, state, deduplicated ports)."""
    name = c.name
    state = (c.status or '').lower()
    raw_image = ''
    try:
        raw_image = (c.attrs.get('Config') or {}).get('Image') or ''
    except Exception:
        raw_image = ''
    if not raw_image:
        try:
            tags = c.image.tags
            raw_image = tags[0] if tags else ''
        except Exception:
            raw_image = ''

    raw_ports = (c.attrs.get('NetworkSettings') or {}).get('Ports') or {}
    ports_list = []
    seen = set()
    for c_key, bindings in raw_ports.items():
        if not bindings:
            continue
        c_port, proto = (c_key.split('/', 1) + ['tcp'])[:2]
        for b in bindings:
            h_port = str(b.get('HostPort') or '').strip()
            if not h_port:
                continue
            dedup_key = (h_port, c_port, proto)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            ports_list.append({
                'host': h_port,
                'container': c_port,
                'protocol': proto,
            })

    return {
        'obj': c,
        'container_name': name,
        'image': raw_image,
        'image_repo': _normalize_image_repo(raw_image),
        'running': (state == 'running'),
        'state': state,
        'ports': ports_list,
    }


def _match_store_container_record(app_def, records, claimed_names=None, allow_fuzzy=True):
    """
    Universal 3-tier matcher mapping a catalog app to an existing Docker container:
      Tier 1: Exact name (eka_<id>, container_name, or <id>)
      Tier 2: Official/mirror image repository match (excludes sidecars/helpers)
      Tier 3: Container name token prefix + corroborating signal (patched image / matching port / standard suffix)
    """
    claimed = claimed_names or set()
    app_id = str(app_def.get('id') or '').strip().lower()
    if not app_id:
        return None

    exact_targets = [f"eka_{app_id}"]
    custom_cname = str(app_def.get('container_name') or '').strip().lower()
    if custom_cname and custom_cname not in exact_targets:
        exact_targets.append(custom_cname)
    if app_id not in exact_targets:
        exact_targets.append(app_id)

    # Tier 1: Exact container name match
    by_lower_name = {r['container_name'].lower(): r for r in records if r['container_name'] not in claimed}
    for target in exact_targets:
        if target in by_lower_name:
            return by_lower_name[target]

    if not allow_fuzzy:
        return None

    app_repo = _normalize_image_repo(app_def.get('image'))
    app_basename = app_repo.rsplit('/', 1)[-1] if app_repo else ''
    app_tokens = [t for t in re.split(r'[-_.\s]+', app_id) if t]
    catalog_cports = {str(p.get('container')) for p in (app_def.get('ports') or []) if p.get('container')}
    web_cport = str(app_def.get('web_port')) if app_def.get('web_port') is not None else None
    if web_cport:
        catalog_cports.add(web_cport)

    best_rec = None
    best_score = -1

    for rec in records:
        if rec['container_name'] in claimed:
            continue
        cname_low = rec['container_name'].lower()
        name_tokens = [t for t in re.split(r'[-_.\s]+', cname_low) if t]
        c_repo = rec.get('image_repo') or ''
        c_basename = c_repo.rsplit('/', 1)[-1] if c_repo else ''
        img_tokens = [t for t in re.split(r'[-_./\s]+', c_repo) if t]

        # Exclude sidecar/helper containers unless the app itself expects that token
        combined_tokens = set(name_tokens) | set(img_tokens)
        disallowed_sidecars = (_SIDECAR_TOKENS - set(app_tokens))
        if combined_tokens & disallowed_sidecars:
            continue

        c_mapped_cports = {str(p.get('container')) for p in (rec.get('ports') or []) if p.get('container')}
        has_web_port_match = bool(web_cport and web_cport in c_mapped_cports)
        has_any_port_match = bool(catalog_cports and (catalog_cports & c_mapped_cports))

        score = 0

        # Tier 2: Image repository match
        if app_repo and c_repo:
            if c_repo == app_repo:
                score = 700
            elif (
                app_basename
                and c_basename == app_basename
                and len(app_basename) >= 4
                and app_basename not in _GENERIC_IMAGE_BASENAMES
                and (c_repo.startswith('linuxserver/') or app_repo.startswith('linuxserver/') or '/' not in app_repo)
            ):
                # Same upstream app from official vs linuxserver mirror (avoid matching immich-app/postgres as postgres)
                if '/' not in app_repo and '/' in c_repo and not c_repo.startswith('linuxserver/'):
                    pass
                else:
                    score = 620

        # Tier 3: Name token prefix match (covers patched/custom-built images like n8n-container + n8n-patched:latest)
        if score == 0 and app_tokens and len(name_tokens) >= len(app_tokens):
            prefix_match = (name_tokens[:len(app_tokens)] == app_tokens)
            # Also match single-token app_id with numeric suffix like pgadmin4-web for pgadmin
            if not prefix_match and len(app_tokens) == 1 and len(app_tokens[0]) >= 3:
                prefix_match = (
                    name_tokens[0].startswith(app_tokens[0])
                    and name_tokens[0][len(app_tokens[0]):].isdigit()
                )
            if prefix_match:
                img_starts_with_app = bool(c_basename and (c_basename == app_id or c_basename.startswith(f"{app_id}-") or c_basename.startswith(f"{app_id}_")))
                has_generic_suffix = (len(name_tokens) > len(app_tokens) and name_tokens[len(app_tokens)] in _GENERIC_CONTAINER_SUFFIXES)
                if img_starts_with_app or has_web_port_match or has_any_port_match or has_generic_suffix:
                    score = 380
                    if img_starts_with_app:
                        score += 50
                    if has_web_port_match:
                        score += 40

        if score <= 0:
            continue

        # Tie-breakers: prefer running, matching web/service port, exposed host port, cleaner name match
        if rec['running']:
            score += 40
        if has_web_port_match:
            score += 35
        elif has_any_port_match:
            score += 20
        if rec['ports']:
            score += 15
        if name_tokens and name_tokens[0].startswith(app_tokens[0]):
            score += 15

        if score > best_score:
            best_score = score
            best_rec = rec

    return best_rec


@app.route('/api/store/installed')
@login_required
def get_installed_apps():
    """Mendapatkan detail aplikasi yang sudah terinstall (Smart Universal Matcher, Deduplicated Ports & Web UI Port)."""
    try:
        container_records = []
        docker_available = False

        try:
            client = docker.from_env()
            containers = client.containers.list(all=True)
            docker_available = True
            container_records = [_extract_container_record(c) for c in containers]
        except Exception:
            docker_available = False

        full_catalog = _load_store_catalog(include_user=True)
        host_snapshot = _get_host_active_snapshot()

        matched_by_app = {}
        claimed_containers = set()

        # Pass 1: Exact container name matches claim their containers first
        if docker_available:
            for app_def in full_catalog:
                rec = _match_store_container_record(app_def, container_records, claimed_containers, allow_fuzzy=False)
                if rec:
                    matched_by_app[app_def['id']] = rec
                    claimed_containers.add(rec['container_name'])

            # Pass 2: Smart image-repo & token-prefix matching for compose / custom-named containers
            for app_def in full_catalog:
                app_id = app_def['id']
                if app_id in matched_by_app:
                    continue
                rec = _match_store_container_record(app_def, container_records, claimed_containers, allow_fuzzy=True)
                if rec:
                    matched_by_app[app_id] = rec
                    claimed_containers.add(rec['container_name'])

        installed = []
        for app_def in full_catalog:
            app_id = app_def['id']
            info = matched_by_app.get(app_id)
            if not info:
                info = _detect_native_host_app(app_id, app_def.get('ports', []), host_snapshot)

            if info:
                cname = info.get('container_name', '')
                is_native = bool(info.get('is_native', False))
                open_port, open_proto = _resolve_app_open_port(app_def, info.get('ports', []))
                installed.append({
                    'id': app_id,
                    'container_name': cname,
                    'running': bool(info.get('running')),
                    'state': info.get('state', 'running' if info.get('running') else 'stopped'),
                    'ports': info.get('ports', []),
                    'open_port': open_port,
                    'open_protocol': open_proto,
                    'is_native': is_native,
                    'is_external': (not is_native) and bool(cname) and (not cname.startswith('eka_')),
                })

        return jsonify({
            'installed': installed,
            'docker_available': docker_available,
        })
    except Exception as e:
        print(f"Error checking installed apps: {e}")
        return jsonify({'error': str(e), 'installed': [], 'docker_available': False})


@app.route('/api/store/install', methods=['POST'])
@login_required
@admin_required
def install_app_endpoint():
    """Install app from store (Async with Socket.IO Logs)"""
    data = request.json or {}
    app_id = (data.get('app_id') or '').strip()
    config = data.get('config') or {}
    
    if not app_id:
        return jsonify({'error': 'App ID required'}), 400

    username = session.get('username')
    thread = threading.Thread(target=install_worker, args=(app_id, config, username), daemon=True)
    thread.start()

    return jsonify({'success': True, 'message': 'Instalasi dimulai... Cek log untuk progress.'})


def install_worker(app_id, config, username):
    """Background worker for universal Docker App Store installation."""
    try:
        client = docker.from_env()
        socketio.emit('install_log', {'app_id': app_id, 'message': f"Menyiapkan instalasi {app_id}...", 'type': 'info'})

        found = None
        cap_add = None
        devices = None
        command = None
        restart_name = 'unless-stopped'
        custom_slug = None

        if app_id != 'custom':
            catalog = _load_store_catalog(include_user=True)
            found = next((a for a in catalog if a['id'] == app_id), None)
            if not found:
                socketio.emit('install_log', {'app_id': app_id, 'message': 'Definisi aplikasi tidak ditemukan di katalog.', 'type': 'error'})
                socketio.emit('install_complete', {'app_id': app_id, 'status': 'error'})
                return

            image = found['image']
            container_name = f"eka_{app_id}"
            cap_add = found.get('cap_add')
            devices = found.get('devices')
            command = found.get('command')
            restart_name = found.get('restart') or 'unless-stopped'

            if 'ports' not in config and 'ports' in found:
                config['ports'] = found['ports']
            if 'volumes' not in config and 'volumes' in found:
                config['volumes'] = found['volumes']
            if 'env' not in config and 'env' in found:
                config['env'] = found['env']
            if 'network_mode' not in config and 'network_mode' in found:
                config['network_mode'] = found['network_mode']
        else:
            image = (config.get('image') or '').strip()
            raw_name = (config.get('name') or '').strip()
            if not image or not raw_name:
                socketio.emit('install_log', {'app_id': app_id, 'message': 'Nama aplikasi dan Docker image wajib diisi.', 'type': 'error'})
                socketio.emit('install_complete', {'app_id': app_id, 'status': 'error'})
                return
            slug_base = ''.join(ch for ch in raw_name.lower() if ch.isalnum() or ch in ('-', '_')).strip('-_') or 'app'
            custom_slug = f"custom_{slug_base}_{int(time.time())}"
            container_name = f"eka_{custom_slug}"

        # Remove old container if exists (both eka_<id> and legacy <id>)
        for candidate_name in {container_name, app_id if app_id != 'custom' else container_name}:
            try:
                old = client.containers.get(candidate_name)
                if old:
                    socketio.emit('install_log', {'app_id': app_id, 'message': f"Menghapus kontainer lama ({candidate_name})...", 'type': 'warning'})
                    old.remove(force=True)
            except docker.errors.NotFound:
                pass

        # Pull Image with Progress
        socketio.emit('install_log', {'app_id': app_id, 'message': f"Target Image: {image}", 'type': 'info'})
        socketio.emit('install_log', {'app_id': app_id, 'message': f"Mengunduh image {image}...", 'type': 'info'})
        try:
            layers = {}
            for line in client.api.pull(image, stream=True, decode=True):
                status = line.get('status')
                progress_detail = line.get('progressDetail', {})
                id_ = line.get('id')

                if id_ and status in ('Downloading', 'Extracting'):
                    current = progress_detail.get('current', 0)
                    total = progress_detail.get('total', 1)
                    layers[id_] = {'current': current, 'total': total, 'status': status}
                    total_bytes = sum(d['total'] for d in layers.values())
                    current_bytes = sum(d['current'] for d in layers.values())
                    if total_bytes > 0:
                        overall_percent = min(99, (current_bytes / total_bytes) * 100)
                        socketio.emit('install_progress', {'app_id': app_id, 'percent': overall_percent, 'message': f"{status} {id_}..."})

                if 'error' in line:
                    raise Exception(line['error'])

            socketio.emit('install_progress', {'app_id': app_id, 'percent': 100, 'message': 'Image berhasil diunduh'})
        except Exception as e:
            socketio.emit('install_log', {'app_id': app_id, 'message': f"Gagal mengunduh image: {str(e)}", 'type': 'error'})
            socketio.emit('install_complete', {'app_id': app_id, 'status': 'error'})
            return

        socketio.emit('install_log', {'app_id': app_id, 'message': 'Image siap. Menyiapkan konfigurasi kontainer...', 'type': 'info'})

        # Prepare Ports safely
        ports = {}
        for p_item in (config.get('ports') or []):
            h_raw = str(p_item.get('host') or '').strip()
            c_raw = str(p_item.get('container') or '').strip()
            proto = (p_item.get('protocol') or 'tcp').strip().lower()
            if not h_raw or not c_raw:
                continue
            try:
                h_int = int(h_raw)
                if 1 <= h_int <= 65535:
                    ports[f"{c_raw}/{proto}"] = h_int
            except (ValueError, TypeError):
                continue

        # Prepare Volumes (Named Volumes + Normalized Host Bind Paths)
        vols_dict = {}
        for v_item in (config.get('volumes') or []):
            src = _normalize_store_volume_bind(v_item.get('bind'))
            dst = str(v_item.get('container') or '').strip()
            if not src or not dst:
                continue
            if src.startswith('/'):
                _ensure_host_bind_dir(src)
            vols_dict[src] = {'bind': dst, 'mode': 'rw'}

        # Prepare Env (supports both list [{key, value}] and dict)
        env_vars = {}
        if isinstance(config.get('environment'), dict):
            env_vars.update(config['environment'])
        if isinstance(config.get('env'), list):
            for e_item in config['env']:
                k = str(e_item.get('key') or '').strip()
                if k:
                    env_vars[k] = str(e_item.get('value') if e_item.get('value') is not None else '')

        net_mode = (config.get('network_mode') or 'bridge').strip()
        run_kwargs = {
            'name': container_name,
            'volumes': vols_dict or None,
            'environment': env_vars or None,
            'network_mode': net_mode,
            'restart_policy': {'Name': restart_name},
            'detach': True,
        }
        if net_mode != 'host' and ports:
            run_kwargs['ports'] = ports
        if cap_add:
            run_kwargs['cap_add'] = cap_add
        if devices:
            run_kwargs['devices'] = devices
        if command:
            run_kwargs['command'] = command

        client.containers.run(image, **run_kwargs)

        # Save Custom App cleanly with matching ID
        if app_id == 'custom' and custom_slug:
            user_apps = []
            if os.path.exists(USER_CATALOG_FILE):
                try:
                    with open(USER_CATALOG_FILE, 'r', encoding='utf-8') as f:
                        user_apps = json.load(f)
                except Exception:
                    pass

            new_entry = {
                'id': custom_slug,
                'name': config.get('name').strip(),
                'description': config.get('description') or 'Custom Docker Application',
                'category': 'Custom',
                'image': image,
                'icon': '/static/icon.svg',
                'ports': config.get('ports', []),
                'volumes': config.get('volumes', []),
                'env': config.get('env', []),
                'network_mode': net_mode,
                'has_web_ui': bool(ports),
            }
            user_apps.append(new_entry)
            os.makedirs(os.path.dirname(USER_CATALOG_FILE), exist_ok=True)
            with open(USER_CATALOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(user_apps, f, indent=4)

        _invalidate_modules_cache()
        _host_snapshot_cache['time'] = 0
        audit_log('APP_INSTALL', f"Installed {container_name} ({image})", username)
        socketio.emit('install_log', {'app_id': app_id, 'message': f"Kontainer {container_name} berhasil dijalankan.", 'type': 'success'})
        socketio.emit('install_complete', {'app_id': app_id, 'status': 'success'})

    except Exception as e:
        print(f"Async Install Error: {e}")
        socketio.emit('install_log', {'app_id': app_id, 'message': f"CRITICAL ERROR: {str(e)}", 'type': 'error'})
        socketio.emit('install_complete', {'app_id': app_id, 'status': 'error', 'error': str(e)})



# ================= APP MANAGER ROUTES =================
# /apps route removed as requested, features moved to /docker

@app.route('/api/apps/details/<app_id>')
@login_required
@requires_permission('docker', 'view')
def app_details(app_id):
    try:
        client = docker.from_env()
        container = client.containers.get(app_id)
        
        # Parse Ports
        ports = []
        if container.attrs['HostConfig']['PortBindings']:
            for c_port, bindings in container.attrs['HostConfig']['PortBindings'].items():
                if bindings:
                    ports.append({
                        'container': c_port.split('/')[0],
                        'protocol': c_port.split('/')[1],
                        'host': bindings[0]['HostPort']
                    })
        
        # Parse Env
        env = []
        for e in container.attrs['Config']['Env']:
             if '=' in e:
                 k, v = e.split('=', 1)
                 env.append({'key': k, 'value': v})
                 
        # Parse Volumes (Binds)
        volumes = []
        if container.attrs['HostConfig']['Binds']:
             for bind in container.attrs['HostConfig']['Binds']:
                 # Format: /host/path:/container/path:rw
                 parts = bind.split(':')
                 if len(parts) >= 2:
                     volumes.append({'host': parts[0], 'container': parts[1], 'mode': parts[2] if len(parts)>2 else 'rw'})

        try:
            img_name = container.image.tags[0] if container.image.tags else container.attrs['Config']['Image']
        except Exception:
            img_name = container.attrs.get('Config', {}).get('Image', 'Unknown')

        details = {
            'id': container.name,
            'image': img_name,
            'status': container.status,
            'network_mode': container.attrs['HostConfig']['NetworkMode'],
            'ports': ports,
            'env': env,
            'volumes': volumes,
            'created': container.attrs['Created']
        }
        return jsonify(details)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/api/apps/action', methods=['POST'])
@login_required
@requires_permission('docker', 'full') 
def app_action():
    data = request.json
    app_id = data.get('id')
    action = data.get('action')
    
    try:
        client = docker.from_env()
        container = client.containers.get(app_id)
        
        if action == 'start': container.start()
        elif action == 'stop': container.stop()
        elif action == 'restart': container.restart()
        elif action == 'uninstall': 
            container.remove(force=True)
            # Remove from user_catalog if exists
            if os.path.exists(USER_CATALOG_FILE):
                 try:
                     with open(USER_CATALOG_FILE) as f: user_apps = json.load(f)
                     user_apps = [a for a in user_apps if a['id'] != app_id] # Filter out
                     with open(USER_CATALOG_FILE, 'w') as f: json.dump(user_apps, f, indent=4)
                 except: pass

        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/apps/update', methods=['POST'])
@login_required
@requires_permission('docker', 'full')
def update_app_config():
    """
    Re-creates container with new config (Ports/Network).
    Preserves Volumes and Env (unless edited).
    """
    data = request.json
    app_id = data.get('id')
    new_ports = data.get('ports') # List of {container, host, protocol}
    new_network = data.get('network_mode', 'bridge')
    
    try:
        client = docker.from_env()
        old_container = client.containers.get(app_id)
        
        # 1. Capture existing config
        image = old_container.attrs['Config']['Image']
        env_vars = old_container.attrs['Config']['Env']
        # Helper to convert list ["K=V"] to dict {K:V}
        environment = {e.split('=',1)[0]: e.split('=',1)[1] for e in env_vars}
        
        volumes = old_container.attrs['HostConfig']['Binds'] # List of binds
        # Convert binds to dict for run command: {'/host': {'bind': '/cont', 'mode': 'rw'}}
        vols_dict = {}
        if volumes:
            for v in volumes:
                 parts = v.split(':')
                 if len(parts) >= 2:
                     vols_dict[parts[0]] = {'bind': parts[1], 'mode': parts[2] if len(parts)>2 else 'rw'}
        
        # 2. Prepare New Config
        ports_dict = None
        if new_network != 'host':
            ports_dict = {}
            if new_ports:
                for p in new_ports:
                     # p: {container: 80, host: 8080, protocol: tcp}
                     c_port = f"{p['container']}/{p.get('protocol','tcp')}"
                     ports_dict[c_port] = int(p['host'])
        
        # 3. Recreate
        print(f"DEBUG: Recreating {app_id} with Network: {new_network}, Ports: {ports_dict}")
        
        old_container.stop()
        old_container.remove()
        
        client.containers.run(
            image,
            name=app_id,
            ports=ports_dict,
            volumes=vols_dict,
            environment=environment,
            network_mode=new_network,
            restart_policy={"Name": "unless-stopped"},
            detach=True
        )
        
        return jsonify({'success': True})

    except Exception as e:
        print(f"Update failed: {e}")
        return jsonify({'error': str(e)}), 500


def _find_store_container(client, app_id):
    """Locate container for an App Store app (exact eka_<id>/<id> first, then universal smart matcher)."""
    for cname in (f"eka_{app_id}", app_id):
        try:
            return client.containers.get(cname)
        except Exception:
            pass
    try:
        full_catalog = _load_store_catalog(include_user=True)
        app_def = next((a for a in full_catalog if a.get('id') == app_id), None)
        if not app_def:
            return None
        records = [_extract_container_record(c) for c in client.containers.list(all=True)]
        matched = _match_store_container_record(app_def, records, allow_fuzzy=True)
        return matched['obj'] if matched else None
    except Exception:
        return None


@app.route('/api/store/manage', methods=['POST'])
@login_required
@admin_required
def manage_app_endpoint():
    """Manage app lifecycle (start/stop/restart/uninstall) — single authoritative endpoint."""
    try:
        data = request.json or {}
        app_id = (data.get('app_id') or '').strip()
        action = (data.get('action') or '').strip().lower()

        if not app_id or action not in ('start', 'stop', 'restart', 'uninstall'):
            return jsonify({'error': 'Invalid params'}), 400

        client = docker.from_env()
        container = _find_store_container(client, app_id)
        if not container:
            return jsonify({'error': f'Container for {app_id} not found'}), 404

        if action == 'start':
            container.start()
        elif action == 'stop':
            container.stop()
        elif action == 'restart':
            container.restart()
        elif action == 'uninstall':
            container.remove(force=True)
            if os.path.exists(USER_CATALOG_FILE):
                try:
                    with open(USER_CATALOG_FILE, 'r', encoding='utf-8') as f:
                        apps = json.load(f)
                    apps = [a for a in apps if a.get('id') != app_id and a.get('name') != app_id]
                    with open(USER_CATALOG_FILE, 'w', encoding='utf-8') as f:
                        json.dump(apps, f, indent=4)
                except Exception:
                    pass

        _invalidate_modules_cache()
        _host_snapshot_cache['time'] = 0
        audit_log('APP_MANAGE', f"{action.title()} app {app_id}", session.get('username'))
        return jsonify({'success': True, 'action': action, 'app_id': app_id})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/store/logs/<app_id>', methods=['GET'])
@login_required
@admin_required
def store_app_logs(app_id):
    """Fetch recent Docker container logs for an installed App Store app."""
    try:
        tail = max(20, min(500, int(request.args.get('tail', 150))))
    except (ValueError, TypeError):
        tail = 150
    try:
        client = docker.from_env()
        container = _find_store_container(client, app_id)
        if not container:
            return jsonify({'success': False, 'logs': '', 'error': 'Container not found'}), 404
        raw = container.logs(tail=tail, timestamps=False)
        text = raw.decode('utf-8', errors='replace') if isinstance(raw, bytes) else str(raw)
        return jsonify({
            'success': True,
            'container_name': container.name,
            'status': container.status,
            'logs': text,
        })
    except Exception as e:
        return jsonify({'success': False, 'logs': '', 'error': str(e)}), 500

SYSTEM_APPS = [
    {"id": "files", "name": "Files", "icon": "fa-solid fa-folder-open", "color": "linear-gradient(135deg, #FF9966, #FF5E62)", "url": "/files"},
    {"id": "terminal", "name": "Terminal", "icon": "fa-solid fa-terminal", "color": "linear-gradient(135deg, #2d3436, #636e72)", "url": "/terminal"},
    {"id": "docker", "name": "Docker", "icon": "fa-brands fa-docker", "color": "linear-gradient(135deg, #2496ed, #0db7ed)", "url": "/panel_docker"},
    {"id": "metrics", "name": "Metrics", "icon": "fa-solid fa-chart-line", "color": "linear-gradient(135deg, #f7971e, #ffd200)", "url": "/metrics"},
    {"id": "security", "name": "Security", "icon": "fa-solid fa-shield-halved", "color": "linear-gradient(135deg, #833ab4, #fd1d1d)", "url": "/security"},
    {"id": "network", "name": "Network", "icon": "fa-solid fa-network-wired", "color": "linear-gradient(135deg, #11998e, #38ef7d)", "url": "/network"},
    {"id": "storage", "name": "Storage", "icon": "fa-solid fa-hard-drive", "color": "linear-gradient(135deg, #667eea, #764ba2)", "url": "/storage"},
    {"id": "websites", "name": "Websites", "icon": "fa-solid fa-globe", "color": "linear-gradient(135deg, #23a6d5, #23d5ab)", "url": "/websites"},
    {"id": "backup", "name": "Backup", "icon": "fa-solid fa-box-archive", "color": "linear-gradient(135deg, #f093fb, #f5576c)", "url": "/backup"},
    {"id": "sharing", "name": "Sharing", "icon": "fa-solid fa-share-nodes", "color": "linear-gradient(135deg, #a18cd1, #fbc2eb)", "url": "/sharing"},
    {"id": "vpn", "name": "VPN", "icon": "fa-solid fa-shield-halved", "color": "linear-gradient(135deg, #ff9a9e, #fecfef)", "url": "/vpn"},
    {"id": "store", "name": "App Store", "icon": "fa-solid fa-store", "color": "linear-gradient(135deg, #FF6B6B, #556270)", "url": "/store"},
    {"id": "mobile-backup", "name": "Mobile Sync", "icon": "fa-solid fa-mobile-screen", "color": "linear-gradient(135deg, #00c6ff, #0072ff)", "url": "/mobile-backup"},
    {"id": "settings", "name": "Settings", "icon": "fa-solid fa-gear", "color": "linear-gradient(135deg, #36D1DC, #5B86E5)", "url": "/settings"},
    {"id": "lxd", "name": "LXD Manager", "icon": "fa-brands fa-linux", "color": "linear-gradient(135deg, #e66465, #9198e5)", "url": "/lxd"},
    {"id": "adblocker", "name": "AdBlocker", "icon": "fa-solid fa-shield-virus", "color": "linear-gradient(135deg, #10b981, #059669)", "url": "/adblocker"},
    {"id": "services", "name": "Services", "icon": "fa-solid fa-gears", "color": "linear-gradient(135deg, #00b4db, #0083b0)", "url": "/services"},
    {"id": "system_logs", "name": "System Logs", "icon": "fa-solid fa-file-waveform", "color": "linear-gradient(135deg, #f857a6, #ff5858)", "url": "/logs"},
    {"id": "firewall", "name": "Firewall", "icon": "fa-solid fa-shield", "color": "linear-gradient(135deg, #f12711, #f5af19)", "url": "/firewall"},
    {"id": "scheduler", "name": "Task Scheduler", "icon": "fa-solid fa-clock-rotate-left", "color": "linear-gradient(135deg, #11998e, #38ef7d)", "url": "/scheduler"},
    {"id": "drive_health", "name": "Drive Health", "icon": "fa-solid fa-heart-pulse", "color": "linear-gradient(135deg, #ff0844, #ffb199)", "url": "/smart"},
    {"id": "packages", "name": "Package Manager", "icon": "fa-solid fa-box-open", "color": "linear-gradient(135deg, #4facfe, #00f2fe)", "url": "/packages"},
    {"id": "alerts", "name": "Alert Engine", "icon": "fa-solid fa-bell", "color": "linear-gradient(135deg, #fa709a, #fee140)", "url": "/alerts"}
]

LAYOUT_FILE = os.path.join(DATA_DIR, 'dashboard_layout.json')

def get_installed_apps_dashboard():
    # Helper to get installed apps formatted for dashboard
    apps = []
    catalog = get_app_catalog() # Defined later, but accessible globally or via import if split
    
    # We need to call the actual function logic here or cache it.
    # Since get_app_catalog is below, we can assume it works.
    # But installed status check is needed.
    
    # Quick fix: Reuse logic from /api/store/installed logic briefly
    # Or better, just get catalog and filter by what is running/installed?
    # NO, we should rely on 'user_apps.json' + docker checks?
    # Actually, simpler: Use 'get_installed_apps_ids' then map to catalog details
    
    return [] # Placeholder, will be populated in route

@app.route('/api/dashboard/apps', methods=['GET'])
def get_dashboard_apps():
    # 1. Get System Apps
    all_items = SYSTEM_APPS.copy()
    
    # 2. Get Installed Apps (Custom + Standard)
    try:
        # Re-use store logic to get details of installed apps
        # We need their icons, names, and exposed ports to build the URL
        
        # Load user catalog first
        user_catalog = []
        user_apps_file = os.path.join(DATA_DIR, 'user_apps.json')
        if os.path.exists(user_apps_file):
            with open(user_apps_file, 'r') as f:
                user_catalog = json.load(f)
        
        # Load default catalog
        default_catalog = []
        catalog_file = os.path.join(BASE_DIR, 'data', 'app_catalog.json')
        if os.path.exists(catalog_file):
             with open(catalog_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    default_catalog = data
                else:
                    default_catalog = data.get('apps', [])
        
        full_catalog = default_catalog + user_catalog
        
        # Check which are installed (running or stopped)
        client = docker.from_env()
        containers = client.containers.list(all=True)
        
        for app in full_catalog:
            # Check if app container exists
            # We match by container name usually or ID logic.
            # In store logic (lines 3500+), we check availability.
            # Here we just want "Is Installed?"
            # Simple check: Is there a container with name 'app['id']' (if standard) 
            # OR logic used in store installation.
            # Store installation uses 'image' and 'name'.
            # A robust way is to check if we have tracked it in 'installed_apps.json' (if we had one)
            # But we don't. We rely on docker container existence.
            
            # Let's try to find container by likely names
            # Standard apps usually named same as ID or configured name.
            # Custom apps have specific container names.
            
            # FAST WAY: Assume if it's in user_apps.json (custom), it is installed/managed.
            # For standard apps, we need to check if container exists.
            
            exists = False
            target_port = None
            
            for c in containers:
                # This is a heuristic. Ideally we should have robust tracking.
                # Matching by image is safer for standard apps? 
                # Or just matching names.
                # Let's match exact name if known, or fuzzy.
                if c.name == app.get('id') or c.name == app.get('container_name') or (app.get('image') and c.attrs['Config']['Image'] == app.get('image')):
                     exists = True
                     # Find first exposed public port
                     ports = c.attrs['NetworkSettings']['Ports']
                     if ports:
                         for p_internal, p_bindings in ports.items():
                             if p_bindings:
                                 target_port = p_bindings[0]['HostPort']
                                 break
                     break
            
            if exists:
                icon = app.get('icon', '/static/icon.png')
                if not icon.startswith('/') and not icon.startswith('http'):
                    icon = '/static/icons/' + icon # heuristic
                    
                dashboard_item = {
                    "id": app.get('id'),
                    "name": app.get('name'),
                    "icon": icon,
                    "color": "linear-gradient(135deg, #34495e, #2c3e50)", # Default dark
                    "url": f"http://{request.host.split(':')[0]}:{target_port}" if target_port else "#",
                    "type": "app"
                }
                
                # Custom overrides
                if app.get('category') == 'Custom':
                    dashboard_item['color'] = "linear-gradient(135deg, #16a085, #2ecc71)"
                    if app.get('web_ui') and app['web_ui'].get('enabled'):
                        # Use defined web ui port logic if complex
                        pass 
                
                # FILTER: Exclude system/backend/all apps from dashboard per user request
                # To keep dashboard clean, we only show System Apps defined in get_dashboard_apps() start.
                # App management is fully in Docker menu.
                # excluded_apps = ['mariadb', 'phpmyadmin', 'homeassistant', 'redis', 'postgres', 'uptime-kuma']
                # if app.get('id') not in excluded_apps:
                #    all_items.append(dashboard_item)
                pass

    except Exception as e:
        print("Error fetching installed apps for dashboard:", e)
    
    # 3. Filter Optional Modules Visibility (Tahap 5 Opt-In Modularization)
    hidden_modules = []
    auto_hide_uninstalled = False
    try:
        settings = load_app_settings()
        mod_cfg = _sanitize_module_settings(settings.get('modules'))
        auto_hide_uninstalled = bool(mod_cfg.get('auto_hide_uninstalled', False))

        installed_map = {}
        if auto_hide_uninstalled:
            for m in _probe_optional_modules():
                installed_map[m['id']] = m.get('installed', True)

        filtered_items = []
        optional_ids = {m['id'] for m in OPTIONAL_MODULES_CATALOG if m.get('app_id')}
        for item in all_items:
            aid = item.get('id')
            if aid == 'settings':
                filtered_items.append(item)
                continue
            if aid in optional_ids:
                if mod_cfg.get(aid) is False:
                    hidden_modules.append(aid)
                    continue
                if auto_hide_uninstalled and (not installed_map.get(aid, True)):
                    hidden_modules.append(aid)
                    continue
            filtered_items.append(item)
        all_items = filtered_items
    except Exception as e:
        print("Module visibility filter error:", e)

    # 4. Apply Order
    try:
        if os.path.exists(LAYOUT_FILE):
            with open(LAYOUT_FILE, 'r') as f:
                saved_order = json.load(f) # List of IDs
                
            # Sort all_items based on saved_order
            # Create a map for rank
            rank = {id: i for i, id in enumerate(saved_order)}
            
            # Items in rank come first, sorted by rank. Items not in rank come last.
            all_items.sort(key=lambda x: rank.get(x['id'], 9999))
            
    except Exception as e:
        print("Layout load error:", e)

    return jsonify({
        "items": all_items,
        "hidden_modules": hidden_modules,
        "auto_hide_uninstalled": auto_hide_uninstalled
    })

@app.route('/api/dashboard/layout', methods=['POST'])
@login_required 
def save_dashboard_layout():
    if session.get('role') not in ['owner', 'admin']:
         return jsonify({'error': 'Unauthorized'}), 403
         
    try:
        order = request.json.get('order', [])
        with open(LAYOUT_FILE, 'w') as f:
            json.dump(order, f)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# (Legacy duplicate install_app / manage_app removed; consolidated in install_worker & manage_app_endpoint)
# =========================================

# --- SYSTEM UPDATE CHECKER ---


# =========================================

# =========================================
# --- ZEROTIER API (ADDED) ---
# =========================================

@app.route('/api/zerotier/status')
@login_required
def zerotier_status():
    """Get ZeroTier status from HOST universally (Docker & Native Linux)"""
    try:
        check = _run_host_cmd(['which', 'zerotier-cli'], timeout=3, include_pid=False)
        installed = check.returncode == 0
        
        running = False
        networks = []
        node_id = ''
        
        if installed:
            status = _run_host_cmd(['zerotier-cli', 'info'], timeout=4, include_pid=False)
            if status.returncode == 0 and '200 info' in status.stdout:
                running = True
                try:
                    node_id = status.stdout.split()[2]
                except Exception:
                    node_id = 'Unknown'
                
                net_cmd = _run_host_cmd(['zerotier-cli', 'listnetworks'], timeout=4, include_pid=False)
                if net_cmd.returncode == 0:
                    lines = net_cmd.stdout.splitlines()
                    if len(lines) > 1:
                        for line in lines[1:]:
                            parts = line.split()
                            if len(parts) >= 8:
                                ip_address = parts[8] if len(parts) > 8 else 'Pending'
                                networks.append({
                                    'network_id': parts[2],
                                    'name': parts[3],
                                    'mac': parts[4],
                                    'status': parts[5],
                                    'type': parts[6],
                                    'dev': parts[7],
                                    'ip': ip_address
                                })
                            
        return jsonify({
            'installed': installed,
            'available': installed,
            'running': running,
            'node_id': node_id,
            'networks': networks
        })
    except Exception as e:
        return jsonify({'installed': False, 'available': False, 'running': False, 'node_id': '', 'networks': [], 'error': str(e)})

@app.route('/api/zerotier/join', methods=['POST'])
@login_required
@admin_required
def zerotier_join():
    """Join ZeroTier network on HOST"""
    try:
        network_id = (request.json or {}).get('networkId')
        if not network_id:
            return jsonify({'error': 'Network ID required'}), 400
            
        if not re.match(r'^[0-9a-fA-F]{16}$', network_id):
             return jsonify({'error': 'Invalid Network ID format'}), 400
        
        res = _run_host_cmd(['zerotier-cli', 'join', network_id], timeout=10, include_pid=False)
        if res.returncode != 0:
            return jsonify({'error': res.stderr or res.stdout or 'Failed to join ZeroTier network'}), 500
        
        audit_log('VPN', f"Joined ZeroTier network {network_id}", session.get('username'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/zerotier/leave', methods=['POST'])
@login_required
@admin_required
def zerotier_leave():
    """Leave ZeroTier network on HOST"""
    try:
        network_id = (request.json or {}).get('networkId')
        if not network_id:
            return jsonify({'error': 'Network ID required'}), 400
            
        res = _run_host_cmd(['zerotier-cli', 'leave', network_id], timeout=10, include_pid=False)
        if res.returncode != 0:
            return jsonify({'error': res.stderr or res.stdout or 'Failed to leave ZeroTier network'}), 500
        audit_log('VPN', f"Left ZeroTier network {network_id}", session.get('username'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- VPN SMART SCAN ---
@app.route('/api/vpn/scan')
@login_required
def vpn_smart_scan():
    """Otomatis mendeteksi semua layanan VPN/Network di host secara universal"""
    try:
        services = []

        # 1. Check Tailscale
        try:
            ts_check = _run_host_cmd(['tailscale', 'status', '--json'], timeout=4, include_pid=False)
            if ts_check.returncode == 0 and ts_check.stdout.strip():
                ts_data = json.loads(ts_check.stdout)
                services.append({
                    'id': 'tailscale',
                    'name': 'Tailscale',
                    'status': 'Online' if ts_data.get('Self', {}).get('Online') else 'Offline',
                    'ip': (ts_data.get('Self', {}).get('TailscaleIPs') or ['N/A'])[0],
                    'icon': 'fa-solid fa-circle-nodes',
                    'color': '#238636'
                })
        except Exception:
            pass

        # 2. Check ZeroTier
        try:
            zt_check = _run_host_cmd(['zerotier-cli', 'info'], timeout=4, include_pid=False)
            if zt_check.returncode == 0:
                services.append({
                    'id': 'zerotier',
                    'name': 'ZeroTier One',
                    'status': 'Online' if 'ONLINE' in zt_check.stdout else 'Offline',
                    'ip': 'Global',
                    'icon': 'fa-solid fa-globe',
                    'color': '#58a6ff'
                })
        except Exception:
            pass

        # 3. Check WireGuard
        try:
            wg_check = _run_host_cmd(['wg', 'show'], timeout=4, include_pid=False)
            if wg_check.returncode == 0 and wg_check.stdout.strip():
                services.append({
                    'id': 'wireguard',
                    'name': 'WireGuard Server',
                    'status': 'Running',
                    'ip': 'Local',
                    'icon': 'fa-solid fa-shield-halved',
                    'color': '#3fb950'
                })
        except Exception:
            pass

        # 4. Check AdGuard Home (Network Filter)
        try:
            ag_check = _run_host_cmd(['ss', '-tulpn'], timeout=4, include_pid=False)
            if 'AdGuardHome' in (ag_check.stdout or ''):
                services.append({
                    'id': 'adguard',
                    'name': 'AdGuard Home',
                    'status': 'Active',
                    'ip': 'DNS Filter',
                    'icon': 'fa-solid fa-leaf',
                    'color': '#63e6be'
                })
        except Exception:
            pass

        # 5. Generic TUN/TAP interfaces
        try:
            interfaces = psutil.net_if_stats()
            for iface in interfaces:
                if iface.startswith(('tun', 'tap', 'ppp')):
                    services.append({
                        'id': f'raw-{iface}',
                        'name': f'Generic VPN ({iface})',
                        'status': 'Active' if interfaces[iface].isup else 'Down',
                        'ip': 'Interface Only',
                        'icon': 'fa-solid fa-network-wired',
                        'color': '#8b949e'
                    })
        except Exception:
            pass

        return jsonify({'services': services})
    except Exception as e:
        return jsonify({'services': [], 'error': str(e)})

# =========================================
# --- FILE UPLOAD API (ADDED) ---
# =========================================

# Helper for secure_filename if not exists
try:
    from werkzeug.utils import secure_filename
except ImportError:
    def secure_filename(filename):
        import re
        return re.sub(r'[^\w\s.-]', '', filename).strip()

@app.route('/api/files/upload', methods=['POST'])
@login_required
def files_upload_endpoint():
    """Upload file(s)"""
    # Check permission explicitly since decorator might duplicate
    # Assuming role check
    if session.get('role') not in ['owner', 'admin']:
         return jsonify({'error': 'Access denied'}), 403
         
    try:
        dest_path = _fm_to_container(request.form.get('path', '/'))
        if not os.path.exists(dest_path):
             return jsonify({'error': 'Path not found'}), 404
             
        if 'file' not in request.files:
             return jsonify({'error': 'No files'}), 400
             
        uploaded = []
        files = request.files.getlist('file')
        
        for f in files:
            if f.filename:
                fname = secure_filename(f.filename)
                save_path = os.path.join(dest_path, fname)
                
                # Auto rename if exists
                counter = 1
                name, ext = os.path.splitext(fname)
                while os.path.exists(save_path):
                    save_path = os.path.join(dest_path, f"{name}_{counter}{ext}")
                    counter += 1
                    
                f.save(save_path)
                uploaded.append(os.path.basename(save_path))
                
        audit_log('FILES', f"Uploaded {len(uploaded)} files to {dest_path}", session.get('username'))
        return jsonify({'success': True, 'files': uploaded})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/download', methods=['GET'])
@login_required
def files_download_endpoint():
    """Download file"""
    try:
        path = request.args.get('path')
        if not path:
            return jsonify({'error': 'File not found'}), 404
        path = _fm_to_container(path)
        if not os.path.exists(path):
            return jsonify({'error': 'File not found'}), 404
        if os.path.isdir(path):
            return jsonify({'error': 'Cannot download directory'}), 400
            
        from flask import send_file
        return send_file(path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==============================================================================
# MOBILE BACKUP ENDPOINTS
# ==============================================================================

MOBILE_BACKUP_CONFIG_FILE = os.path.join(DATA_DIR, 'mobile_backup_config.json')


def _resolve_mobile_backup_base_dir():
    """Deteksi direktori penyimpanan Mobile Backup secara dinamis & universal."""
    env_dir = (os.environ.get('MOBILE_BACKUP_DIR') or '').strip()
    if env_dir:
        return env_dir
    host_root = os.environ.get('HOST_ROOT', '/host/root')
    mounted_data = os.path.join(host_root, 'mnt', 'data')
    if os.path.isdir(os.path.join(mounted_data, 'MobileBackup')) or os.path.ismount(mounted_data):
        return os.path.join(mounted_data, 'MobileBackup')
    return os.path.join(DATA_DIR, 'mobile_backup')


BACKUP_BASE_DIR = _resolve_mobile_backup_base_dir()

def get_mobile_backup_config():
    """Baca config IP dari file, fallback ke auto-detect dari host network"""
    # Cek config tersimpan
    if os.path.exists(MOBILE_BACKUP_CONFIG_FILE):
        try:
            with open(MOBILE_BACKUP_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass

    # Auto-detect dari host network
    lan_ip = "127.0.0.1"
    ts_ip = ""
    try:
        nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
        result = subprocess.run(nsenter + ['ip', 'addr', 'show'], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                addr_m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', line)
                if addr_m:
                    ip = addr_m.group(1)
                    if (ip.startswith('192.168.') or ip.startswith('10.') or ip.startswith('172.')) and not ip.startswith('172.17.') and not ip.startswith('172.18.'):
                        lan_ip = ip
                    elif ip.startswith('100.'):
                        ts_ip = ip
    except:
        pass

    return {"lan_ip": lan_ip, "ts_ip": ts_ip}

@app.route('/mobile-backup')
@login_required
def mobile_backup_page():
    """Halaman Mobile Backup"""
    config = get_mobile_backup_config()
    return render_template('mobile_backup.html', lan_ip=config['lan_ip'], ts_ip=config['ts_ip'])

@app.route('/api/mobile-backup/config', methods=['GET'])
@login_required
def mobile_backup_get_config():
    """Ambil config IP"""
    return jsonify(get_mobile_backup_config())

@app.route('/api/mobile-backup/config', methods=['POST'])
@login_required
def mobile_backup_save_config():
    """Simpan config IP ke file"""
    data = request.get_json()
    config = {"lan_ip": data.get('lan_ip', ''), "ts_ip": data.get('ts_ip', '')}
    try:
        with open(MOBILE_BACKUP_CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mobile-backup/ping', methods=['GET'])
def mobile_backup_ping():
    """Endpoint untuk deteksi server oleh aplikasi Android"""
    return jsonify({"server": "EkaDashboard", "status": "online", "version": "1.0"})

@app.route('/api/mobile-backup/disk-usage', methods=['GET'])
@login_required
def mobile_backup_disk_usage():
    """Informasi penggunaan disk target penyimpanan Mobile Backup"""
    try:
        import shutil
        os.makedirs(BACKUP_BASE_DIR, exist_ok=True)
        disk_target = BACKUP_BASE_DIR if os.path.exists(BACKUP_BASE_DIR) else DATA_DIR
        total, used, free = shutil.disk_usage(disk_target)
        # Cek ukuran folder MobileBackup saja
        backup_size = 0
        if os.path.exists(BACKUP_BASE_DIR):
            for dirpath, dirnames, filenames in os.walk(BACKUP_BASE_DIR):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try: backup_size += os.path.getsize(fp)
                    except: pass
        return jsonify({
            "total": total,
            "used": used,
            "free": free,
            "backup_size": backup_size,
            "percent_used": round(used / total * 100, 1) if total > 0 else 0
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _is_within_mobile_backup_dir(target_path):
    """Canonical path boundary guard preventing sibling-prefix traversal (e.g. MobileBackup_evil)."""
    if not target_path:
        return False
    try:
        real_base = os.path.realpath(BACKUP_BASE_DIR)
        real_target = os.path.realpath(target_path)
        return os.path.commonpath([real_base, real_target]) == real_base
    except Exception:
        return False


def _mobile_backup_upload_authorized():
    """Authorize Mobile Backup upload via logged-in admin/owner session OR scoped MOBILE_ACCESS_TOKEN."""
    config = load_security_config()
    if not config.get('require_auth', True):
        return True
    if session.get('logged_in') and session.get('role') in ('owner', 'admin'):
        return True
    expected_token = (os.environ.get('MOBILE_ACCESS_TOKEN') or '').strip()
    if expected_token:
        import hmac
        provided = (request.headers.get('X-Mobile-Token') or '').strip()
        if not provided:
            auth_hdr = (request.headers.get('Authorization') or '').strip()
            if auth_hdr.lower().startswith('bearer '):
                provided = auth_hdr[7:].strip()
        if provided and hmac.compare_digest(provided, expected_token):
            return True
    return False


@app.route('/api/mobile-backup/mkdir', methods=['POST'])
@login_required
@admin_required
def mobile_backup_mkdir():
    """Buat folder baru"""
    data = request.get_json(silent=True) or {}
    parent = data.get('parent', BACKUP_BASE_DIR)
    name = (data.get('name') or '').strip()
    if not name or '/' in name or '\\' in name or name.startswith('.'):
        return jsonify({"error": "Nama folder tidak valid"}), 400
    if not _is_within_mobile_backup_dir(parent):
        return jsonify({"error": "Akses ditolak"}), 403
    new_dir = os.path.join(parent, name)
    if not _is_within_mobile_backup_dir(new_dir):
        return jsonify({"error": "Akses ditolak"}), 403
    try:
        os.makedirs(new_dir, exist_ok=True)
        return jsonify({"success": True, "path": new_dir})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mobile-backup/rename', methods=['POST'])
@login_required
@admin_required
def mobile_backup_rename():
    """Rename file atau folder"""
    data = request.get_json(silent=True) or {}
    old_path = data.get('path', '')
    new_name = (data.get('new_name') or '').strip()
    if not new_name or '/' in new_name or '\\' in new_name or new_name.startswith('.'):
        return jsonify({"error": "Nama tidak valid"}), 400
    if not _is_within_mobile_backup_dir(old_path) or os.path.realpath(old_path) == os.path.realpath(BACKUP_BASE_DIR):
        return jsonify({"error": "Akses ditolak"}), 403
    new_path = os.path.join(os.path.dirname(old_path), new_name)
    if not _is_within_mobile_backup_dir(new_path):
        return jsonify({"error": "Akses ditolak"}), 403
    if os.path.exists(new_path):
        return jsonify({"error": "Tujuan sudah ada"}), 409
    try:
        os.rename(old_path, new_path)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mobile-backup/move', methods=['POST'])
@login_required
@admin_required
def mobile_backup_move():
    """Pindah file atau folder (Cut & Paste)"""
    data = request.get_json(silent=True) or {}
    src = data.get('src')
    dest_dir = data.get('dest_dir')
    if not src or not dest_dir:
        return jsonify({"error": "Data tidak lengkap"}), 400
    if not _is_within_mobile_backup_dir(src) or not _is_within_mobile_backup_dir(dest_dir):
        return jsonify({"error": "Akses ditolak"}), 403
    if os.path.realpath(src) == os.path.realpath(BACKUP_BASE_DIR):
        return jsonify({"error": "Akses ditolak"}), 403

    try:
        import shutil
        dest = os.path.join(dest_dir, os.path.basename(src))
        if not _is_within_mobile_backup_dir(dest) or os.path.exists(dest):
            return jsonify({"error": "Tujuan tidak valid atau sudah ada"}), 409
        shutil.move(src, dest)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mobile-backup/copy', methods=['POST'])
@login_required
@admin_required
def mobile_backup_copy():
    """Salin file atau folder (Copy & Paste)"""
    data = request.get_json(silent=True) or {}
    src = data.get('src')
    dest_dir = data.get('dest_dir')
    if not src or not dest_dir:
        return jsonify({"error": "Data tidak lengkap"}), 400
    if not _is_within_mobile_backup_dir(src) or not _is_within_mobile_backup_dir(dest_dir):
        return jsonify({"error": "Akses ditolak"}), 403

    try:
        import shutil
        dest = os.path.join(dest_dir, os.path.basename(src))
        if not _is_within_mobile_backup_dir(dest) or os.path.exists(dest):
            return jsonify({"error": "Tujuan tidak valid atau sudah ada"}), 409
        if os.path.isdir(src):
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mobile-backup/download-file', methods=['GET'])
@login_required
def mobile_backup_download_file():
    """Download file backup"""
    path = request.args.get('path', '')
    if not _is_within_mobile_backup_dir(path):
        return jsonify({"error": "Akses ditolak"}), 403
    real_path = os.path.realpath(path)
    if not os.path.isfile(real_path):
        return jsonify({"error": "File tidak ditemukan"}), 404
    from flask import send_file
    return send_file(real_path, as_attachment=True)

@app.route('/api/mobile-backup/files', methods=['GET'])
@login_required
def mobile_backup_list_files():
    """List semua file dan folder di direktori backup HDD"""
    try:
        path = request.args.get('path')
        if not path:
            path = BACKUP_BASE_DIR
        if not _is_within_mobile_backup_dir(path):
            return jsonify({"error": "Akses ditolak"}), 403

        os.makedirs(path, exist_ok=True)
        items = []
        for entry in sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower())):
            stat = entry.stat()
            items.append({
                "name": entry.name,
                "type": "folder" if entry.is_dir() else "file",
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "path": entry.path
            })
        total_size = sum(i['size'] for i in items if i['type'] == 'file')
        return jsonify({
            "current_path": path,
            "base_path": BACKUP_BASE_DIR,
            "items": items,
            "total_size": total_size
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mobile-backup/delete', methods=['POST'])
@login_required
@admin_required
def mobile_backup_delete():
    """Hapus file backup"""
    data = request.get_json(silent=True) or {}
    path = data.get('path', '')
    if not _is_within_mobile_backup_dir(path) or os.path.realpath(path) == os.path.realpath(BACKUP_BASE_DIR):
        return jsonify({"error": "Akses ditolak"}), 403
    real_path = os.path.realpath(path)
    try:
        if os.path.isdir(real_path):
            import shutil
            shutil.rmtree(real_path)
        else:
            os.remove(real_path)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mobile-backup/upload', methods=['POST'])
def mobile_backup_upload():
    """API endpoint untuk menerima file dari aplikasi Android atau admin web."""
    if not _mobile_backup_upload_authorized():
        return jsonify({'error': 'Authentication required'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    raw_fname = os.path.basename(file.filename or '')
    safe_fname = secure_filename(raw_fname)
    if not safe_fname:
        return jsonify({'error': 'Invalid filename'}), 400

    target_dir = request.form.get('path') or BACKUP_BASE_DIR
    if not _is_within_mobile_backup_dir(target_dir):
        return jsonify({"error": "Akses ditolak"}), 403

    os.makedirs(target_dir, exist_ok=True)
    save_path = os.path.join(target_dir, safe_fname)
    if not _is_within_mobile_backup_dir(save_path):
        return jsonify({"error": "Akses ditolak"}), 403
    try:
        file.save(save_path)
        return jsonify({'success': True, 'message': 'File backed up successfully', 'path': save_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# WEB PANEL INTEGRATION — WEBSITES, STORAGE, DOCKER OVERVIEW
# ==========================================

def _read_host_nginx_file(fpath):
    """Membaca isi file konfigurasi Nginx dari host dengan resolusi symlink transparan di Docker"""
    try:
        if os.path.islink(fpath):
            target = os.readlink(fpath)
            if target.startswith('/'):
                if os.path.exists('/host/root' + target):
                    fpath = '/host/root' + target
                elif os.path.exists(target):
                    fpath = target
        if os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
    except Exception:
        pass
    return ""

def _parse_vhost_file(fname, fpath):
    """Parse konfigurasi Nginx vhost: domain, listen ports, root, proxy_pass, ssl"""
    content = _read_host_nginx_file(fpath)
    if not content:
        return None
    
    server_names = []
    m_names = re.findall(r'server_name\s+([^;]+);', content)
    for m in m_names:
        names = [n.strip() for n in m.split() if n.strip()]
        for n in names:
            if n not in server_names:
                server_names.append(n)
                
    primary_domain = server_names[0] if server_names else fname
    
    listen_ports = []
    has_ssl = False
    m_listens = re.findall(r'listen\s+([^;]+);', content)
    for l in m_listens:
        parts = l.split()
        if 'ssl' in parts or '443' in parts:
            has_ssl = True
        port_num = parts[0].split(':')[-1]
        if port_num.isdigit() and port_num not in listen_ports:
            listen_ports.append(port_num)
            
    if not listen_ports:
        listen_ports = ['80']
        
    m_root = re.search(r'root\s+([^;]+);', content)
    root = m_root.group(1).strip() if m_root else '-'
    
    m_proxy = re.search(r'proxy_pass\s+([^;]+);', content)
    proxy_target = m_proxy.group(1).strip() if m_proxy else None
    
    return {
        'name': fname,
        'domain': primary_domain,
        'domains': server_names if server_names else [fname],
        'port': ', '.join(listen_ports),
        'ports': listen_ports,
        'root': root,
        'is_proxy': bool(proxy_target),
        'proxy_pass': proxy_target,
        'ssl': has_ssl or ('ssl_certificate' in content),
        'enabled': True
    }

def _detect_host_web_servers():
    """Deteksi web server yang terpasang pada host (nginx / apache2 / httpd / caddy)."""
    detected = []
    for name, bin_name, svc_name in (
        ('nginx', 'nginx', 'nginx'),
        ('apache', 'apache2', 'apache2'),
        ('httpd', 'httpd', 'httpd'),
        ('caddy', 'caddy', 'caddy'),
    ):
        chk = _run_host_cmd(['which', bin_name], timeout=3, include_pid=False)
        if chk.returncode == 0 and chk.stdout.strip():
            st = _run_systemctl(['is-active', svc_name], timeout=3)
            detected.append({
                'name': name,
                'binary': bin_name,
                'service': svc_name,
                'running': (st.returncode == 0 and st.stdout.strip() == 'active')
            })
    return detected


def _find_host_access_log():
    """Cari lokasi file access.log web server lintas distro (Nginx/Apache/Httpd/Caddy)."""
    host_root = os.environ.get('HOST_ROOT', '/host/root')
    rel_paths = (
        'var/log/nginx/access.log',
        'var/log/apache2/access.log',
        'var/log/httpd/access_log',
        'var/log/caddy/access.log',
    )
    for rel in rel_paths:
        for base in (host_root, '/'):
            p = os.path.join(base, rel)
            if os.path.exists(p):
                return p
    return None


def _get_all_vhosts():
    """Mengambil dan mem-parsing seluruh virtual host Nginx lintas distro (sites-enabled, conf.d, http.d)."""
    sites = []
    seen_keys = set()
    host_root = os.environ.get('HOST_ROOT', '/host/root')
    rel_dirs = ('etc/nginx/sites-enabled', 'etc/nginx/conf.d', 'etc/nginx/http.d')

    for rel in rel_dirs:
        target_dir = None
        for base in (host_root, '/'):
            cand = os.path.join(base, rel)
            if os.path.isdir(cand):
                target_dir = cand
                break
        if not target_dir:
            continue
        try:
            for fname in sorted(os.listdir(target_dir)):
                fpath = os.path.join(target_dir, fname)
                if os.path.isdir(fpath):
                    continue
                if rel != 'etc/nginx/sites-enabled' and not fname.endswith('.conf'):
                    continue
                vhost = _parse_vhost_file(fname, fpath)
                if vhost:
                    dedup_key = (vhost.get('domain'), vhost.get('port'))
                    if dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        sites.append(vhost)
        except Exception:
            pass
    return sites

def check_ssl_expiry(domain):
    """Mengecek masa berlaku sertifikat SSL domain publik dengan timeout aman"""
    import ssl
    import socket
    from datetime import datetime
    try:
        context = ssl.create_default_context()
        conn = context.wrap_socket(socket.socket(socket.AF_INET), server_hostname=domain)
        conn.settimeout(2.5)
        conn.connect((domain, 443))
        ssl_info = conn.getpeercert()
        conn.close()
        expire_date = datetime.strptime(ssl_info['notAfter'], r'%b %d %H:%M:%S %Y %Z')
        days_left = (expire_date - datetime.utcnow()).days
        issuer_cn = dict(x[0] for x in ssl_info.get('issuer', []))
        issuer = issuer_cn.get('commonName', issuer_cn.get('organizationName', 'Unknown CA'))
        status = 'valid'
        if days_left <= 0:
            status = 'expired'
        elif days_left < 14:
            status = 'expiring'
            
        return {
            "domain": domain,
            "days_left": days_left,
            "issuer": issuer,
            "valid_from": ssl_info.get('notBefore'),
            "valid_to": ssl_info.get('notAfter'),
            "status": status,
            "success": True
        }
    except Exception as e:
        return {
            "domain": domain,
            "days_left": 0,
            "issuer": "N/A",
            "status": "error",
            "error": str(e),
            "success": False
        }

def _run_iptables(args, timeout=5):
    """Jalankan iptables pada host via eksekutor universal (nsenter / native)."""
    return _run_host_cmd(['iptables'] + list(args), timeout=timeout)

@app.route('/websites')
@login_required
def websites_page():
    """List semua Nginx virtual hosts yang aktif dan Shield Control"""
    sites = _get_all_vhosts()
    tab = request.args.get('tab', 'vhosts')
    return render_template('websites.html', sites=sites, initial_tab=tab)

@app.route('/api/websites/vhosts')
@login_required
def api_websites_vhosts():
    """Daftar detail semua virtual host Nginx yang aktif"""
    sites = _get_all_vhosts()
    ssl_count = sum(1 for s in sites if s.get('ssl'))
    proxy_count = sum(1 for s in sites if s.get('is_proxy'))
    return jsonify({
        'sites': sites,
        'total': len(sites),
        'active_count': len(sites),
        'ssl_count': ssl_count,
        'proxy_count': proxy_count
    })

@app.route('/api/websites/nginx_status')
@login_required
def nginx_status():
    """Cek status Nginx & web server host secara universal (Docker nsenter / Native Linux)."""
    status = 'not_installed'
    running = False
    version = 'Not Installed'
    detected_servers = _detect_host_web_servers()
    installed = any(s['name'] == 'nginx' for s in detected_servers)

    if installed:
        status = 'inactive'
        version = 'Nginx'
        try:
            result = _run_systemctl(['is-active', 'nginx'], timeout=5)
            st_out = (result.stdout or '').strip()
            if st_out:
                status = st_out
            running = (status == 'active')
        except Exception:
            pass

    if not running:
        try:
            proc_path = os.environ.get('HOST_PROC', '/proc')
            for pid in os.listdir(proc_path):
                if not pid.isdigit():
                    continue
                try:
                    comm_file = os.path.join(proc_path, pid, 'comm')
                    with open(comm_file, 'r') as f:
                        if f.read().strip() == 'nginx':
                            cmdline_file = os.path.join(proc_path, pid, 'cmdline')
                            with open(cmdline_file, 'r') as cf:
                                cmdline = cf.read()
                            if 'master' in cmdline or 'nginx' in cmdline:
                                status = 'active'
                                running = True
                                installed = True
                                break
                except Exception:
                    continue
        except Exception:
            pass

    if installed:
        try:
            v_res = _run_host_cmd(['nginx', '-v'], timeout=5)
            v_out = (v_res.stdout or '') + (v_res.stderr or '')
            m_ver = re.search(r'nginx/([^\s]+)', v_out)
            if m_ver:
                version = f"Nginx {m_ver.group(1)}"
        except Exception:
            pass

    primary_server = 'nginx' if installed else (detected_servers[0]['name'] if detected_servers else 'none')
    return jsonify({
        'status': status,
        'running': running,
        'installed': installed,
        'version': version,
        'web_server': primary_server,
        'detected_servers': detected_servers
    })

@app.route('/api/websites/control_nginx', methods=['POST'])
@login_required
def control_nginx():
    """Reload, restart, start, stop service Nginx secara universal dengan uji sintaks otomatis"""
    data = request.json or {}
    action = data.get('action', 'reload').strip().lower()
    if action not in ('reload', 'restart', 'start', 'stop'):
        return jsonify({'success': False, 'error': 'Aksi tidak valid'}), 400

    chk = _run_host_cmd(['which', 'nginx'], timeout=4, include_pid=False)
    if chk.returncode != 0 or not chk.stdout.strip():
        return jsonify({'success': False, 'error': 'Nginx tidak terpasang pada host ini'}), 400

    try:
        if action in ('reload', 'restart'):
            t_res = _run_host_cmd(['nginx', '-t'], timeout=8)
            if t_res.returncode != 0:
                err_msg = (t_res.stderr or t_res.stdout or 'Sintaks konfigurasi Nginx salah').strip()
                return jsonify({'success': False, 'error': f'Config test failed: {err_msg}'}), 400

        res = _run_systemctl([action, 'nginx'], timeout=12)
        success = (res.returncode == 0)
        output = (res.stdout or '') + (res.stderr or '')
        audit_log('NGINX_CONTROL', f"Nginx {action} executed", session.get('username'))
        return jsonify({
            'success': success,
            'message': f'Nginx {action} berhasil dieksekusi' if success else f'Gagal {action} Nginx: {output}',
            'output': output
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/websites/reload_nginx', methods=['POST'])
@login_required
def reload_nginx():
    """Reload Nginx config (alias backward compatibility)"""
    return control_nginx()

@app.route('/api/websites/traffic')
@login_required
def api_websites_traffic():
    """Statistik lalu lintas web server real-time lintas distro dari access.log"""
    import collections
    from datetime import datetime
    log_path = _find_host_access_log()

    today_requests = 0
    unique_ips = set()
    ip_times = collections.defaultdict(list)
    top_pages = collections.Counter()
    bad_bots_blocked = 0
    hourly_counter = collections.Counter()
    status_counter = collections.Counter()

    if log_path:
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[-6000:]
                for line in lines:
                    today_requests += 1
                    parts = line.split()
                    if len(parts) > 6:
                        ip = parts[0]
                        unique_ips.add(ip)
                        page = parts[6]
                        status = parts[8] if len(parts) > 8 else ''
                        if status.isdigit():
                            code_cls = f"{status[0]}xx"
                            status_counter[code_cls] += 1

                        try:
                            time_str = parts[3][1:]
                            dt = datetime.strptime(time_str, "%d/%b/%Y:%H:%M:%S")
                            ip_times[ip].append(dt)
                            hour_label = dt.strftime('%H:00')
                            hourly_counter[hour_label] += 1
                        except Exception:
                            pass

                        if not page.endswith(('.png', '.css', '.js', '.ico', '.jpg', '.woff2', '.svg', '.map')):
                            clean_page = page.split('?')[0]
                            top_pages[clean_page] += 1

                        if '403' in parts or 'bot' in line.lower() or 'crawler' in line.lower() or 'spider' in line.lower():
                            bad_bots_blocked += 1
        except Exception:
            pass

    total_duration = 0
    valid_sessions = 0
    for ip, times in ip_times.items():
        if len(times) > 1:
            duration = (max(times) - min(times)).total_seconds()
            total_duration += duration
            valid_sessions += 1

    avg_duration = (total_duration / valid_sessions) if valid_sessions > 0 else 0
    avg_duration_str = f"{int(avg_duration // 60)}m {int(avg_duration % 60)}s"

    hourly_distribution = []
    for h in range(24):
        hl = f"{h:02d}:00"
        hourly_distribution.append({'hour': hl, 'count': hourly_counter.get(hl, 0)})

    return jsonify({
        "today_requests": today_requests,
        "unique_ips_count": len(unique_ips),
        "unique_ips": list(unique_ips)[:20],
        "avg_duration": avg_duration_str,
        "top_pages": [{"page": k, "count": v} for k, v in top_pages.most_common(5)],
        "bad_bots_blocked": bad_bots_blocked,
        "hourly_distribution": hourly_distribution,
        "status_codes": dict(status_counter)
    })

@app.route('/api/websites/ssl_status')
@login_required
def api_websites_ssl_status():
    """Pengecekan sertifikat SSL dinamis untuk semua domain yang ditemukan di vhost"""
    sites = _get_all_vhosts()
    domains_to_check = set()
    for s in sites:
        for d in s.get('domains', []):
            d_clean = d.strip()
            if (d_clean and not d_clean.startswith('_') and not d_clean.startswith('*')
                    and d_clean not in ('localhost', 'default')
                    and not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', d_clean)):
                domains_to_check.add(d_clean)

    if not domains_to_check:
        legacy_domain = get_web_shield_domain()
        if legacy_domain:
            domains_to_check.add(legacy_domain)

    results = []
    for dom in sorted(domains_to_check):
        res = check_ssl_expiry(dom)
        results.append(res)

    valid_count = sum(1 for r in results if r.get('status') == 'valid')
    expiring_count = sum(1 for r in results if r.get('status') == 'expiring')
    expired_count = sum(1 for r in results if r.get('status') in ('expired', 'error'))

    return jsonify({
        'certificates': results,
        'total': len(results),
        'valid_count': valid_count,
        'expiring_count': expiring_count,
        'expired_count': expired_count
    })

@app.route('/api/websites/backup', methods=['POST'])
@login_required
def api_websites_backup():
    """Backup direktori web domain menjadi arsip ZIP"""
    import zipfile
    data = request.json or {}
    domain = data.get('domain', '').strip()
    if not domain:
        domain = get_web_shield_domain()
    if not domain:
        return jsonify({'error': 'Domain harus ditentukan'}), 400

    source_dir = None
    sites = _get_all_vhosts()
    for s in sites:
        if domain in s.get('domains', []) or domain == s.get('name'):
            v_root = s.get('root')
            if v_root and v_root != '-':
                h_path = '/host/root' + v_root if os.path.exists('/host/root' + v_root) else v_root
                if os.path.exists(h_path):
                    source_dir = h_path
                    break

    if not source_dir:
        for cand in [f'/host/root/var/www/{domain}', f'/var/www/{domain}']:
            if os.path.exists(cand):
                source_dir = cand
                break

    if not source_dir or not os.path.exists(source_dir):
        return jsonify({'error': f'Direktori web untuk {domain} tidak ditemukan'}), 404

    zip_filename = f"backup_{domain.replace('.', '_')}_{int(time.time())}.zip"
    zip_path = os.path.join('/tmp', zip_filename)

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, source_dir)
                    zipf.write(file_path, arcname)

        return send_file(zip_path, as_attachment=True, download_name=zip_filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# THREAT DETECTION — Nginx Log Scanner
# ============================================================
import re as _re
from collections import defaultdict

# Known scanner/bot User-Agent patterns
SCANNER_UA_PATTERNS = [
    r'nikto', r'sqlmap', r'nmap', r'masscan', r'zgrab', r'nuclei',
    r'dirbuster', r'gobuster', r'wfuzz', r'hydra', r'metasploit',
    r'python-requests', r'go-http-client', r'curl/', r'wget/',
    r'scrapy', r'ahrefsbot', r'semrushbot', r'mj12bot', r'dotbot',
    r'petalbot', r'bytespider', r'gptbot', r'claudebot', r'ccbot',
    r'dataforseobot', r'yandexbot', r'baiduspider', r'360spider',
    r'acunetix', r'nessus', r'openvas', r'burpsuite', r'zap',
    r'whatweb', r'wpscan', r'joomscan', r'droopescan',
    r'libwww-perl', r'lwp-trivial', r'java/', r'jakarta',
    r'zgrab', r'internet-explorer/[0-6]',  # Old IE often bots
]

# Suspicious URL path patterns (scanning/exploit attempts)
SUSPICIOUS_PATH_PATTERNS = [
    r'\.php$', r'wp-login', r'wp-admin', r'xmlrpc\.php',
    r'\.env', r'\.git/', r'\.htaccess', r'\.htpasswd',
    r'admin/', r'phpmyadmin', r'pma/', r'mysql/',
    r'/etc/passwd', r'/etc/shadow', r'proc/self',
    r'union.*select', r'select.*from', r'drop.*table',
    r'<script', r'javascript:', r'onerror=', r'onload=',
    r'\.\./\.\.',  # Path traversal
    r'cmd=', r'exec=', r'system\(', r'passthru\(',
    r'eval\(', r'base64_decode',
    r'\.bak$', r'\.sql$', r'\.zip$', r'\.tar\.gz$',
    r'config\.', r'backup\.', r'dump\.',
    r'/cgi-bin/', r'/shell', r'/cmd',
    r'jndi:', r'\$\{',  # Log4Shell
    r'actuator/', r'solr/', r'jenkins/',
]

NGINX_LOG_PATHS = [
    '/host/root/var/log/nginx/access.log',
    '/var/log/nginx/access.log',
]

def _parse_nginx_log_line(line):
    """Parse a single Nginx combined log format line"""
    pattern = r'(\S+) - (\S+) \[([^\]]+)\] "(\S+) (\S+) (\S+)" (\d+) (\d+) "([^"]*)" "([^"]*)"'
    m = _re.match(pattern, line)
    if not m:
        return None
    return {
        'ip': m.group(1),
        'user': m.group(2),
        'time': m.group(3),
        'method': m.group(4),
        'path': m.group(5),
        'proto': m.group(6),
        'status': int(m.group(7)),
        'size': int(m.group(8)),
        'referer': m.group(9),
        'ua': m.group(10),
    }

def _classify_threat(entry):
    """Return threat type string or None"""
    ua_lower = entry['ua'].lower()
    path_lower = entry['path'].lower()

    # Check UA
    for pat in SCANNER_UA_PATTERNS:
        if _re.search(pat, ua_lower, _re.IGNORECASE):
            return 'Scanner/Bot UA'

    # Check path
    for pat in SUSPICIOUS_PATH_PATTERNS:
        if _re.search(pat, path_lower, _re.IGNORECASE):
            return 'Suspicious Path'

    # High 4xx rate (checked at aggregation level, not per-line)
    if entry['status'] in (400, 401, 403, 404, 405, 429):
        return '4xx Error'

    return None

@app.route('/api/websites/threats')
@login_required
def get_threats():
    """
    Scan Nginx access log and return:
    - Top threat IPs with request counts, threat types, last seen
    - Recent suspicious requests (last 200 lines)
    - Summary stats
    """
    log_file = None
    for path in NGINX_LOG_PATHS:
        if os.path.exists(path):
            log_file = path
            break

    if not log_file:
        return jsonify({'error': 'Nginx access log not found', 'threats': [], 'recent': [], 'stats': {}})

    # Read last N lines efficiently
    MAX_LINES = 5000
    try:
        result = subprocess.run(['tail', '-n', str(MAX_LINES), log_file],
                                capture_output=True, text=True, timeout=5)
        lines = result.stdout.splitlines()
    except Exception as e:
        return jsonify({'error': str(e), 'threats': [], 'recent': [], 'stats': {}})

    # Aggregate per IP
    ip_data = defaultdict(lambda: {
        'count': 0, 'threat_count': 0, 'threat_types': set(),
        'paths': [], 'statuses': defaultdict(int),
        'last_seen': '', 'ua': '', 'is_threat': False
    })

    recent_threats = []
    total_requests = 0
    total_threats = 0

    for line in lines:
        entry = _parse_nginx_log_line(line)
        if not entry:
            continue
        total_requests += 1
        ip = entry['ip']
        d = ip_data[ip]
        d['count'] += 1
        d['last_seen'] = entry['time']
        d['ua'] = entry['ua'][:120]
        d['statuses'][str(entry['status'])] += 1

        threat_type = _classify_threat(entry)
        if threat_type:
            d['threat_count'] += 1
            d['threat_types'].add(threat_type)
            d['is_threat'] = True
            if len(d['paths']) < 5:
                d['paths'].append(entry['path'][:100])
            total_threats += 1

            if len(recent_threats) < 50:
                recent_threats.append({
                    'ip': ip,
                    'time': entry['time'],
                    'method': entry['method'],
                    'path': entry['path'][:120],
                    'status': entry['status'],
                    'ua': entry['ua'][:100],
                    'threat_type': threat_type,
                })

    # Build threat IP list — IPs with high 4xx rate OR scanner UA
    threat_ips = []
    for ip, d in ip_data.items():
        if not d['is_threat']:
            # Also flag IPs with >10 4xx errors even if no scanner UA
            total_4xx = sum(v for k, v in d['statuses'].items() if k.startswith('4'))
            if total_4xx >= 10:
                d['is_threat'] = True
                d['threat_types'].add('High 4xx Rate')
                d['threat_count'] += total_4xx

        if d['is_threat']:
            threat_ips.append({
                'ip': ip,
                'total_requests': d['count'],
                'threat_requests': d['threat_count'],
                'threat_types': list(d['threat_types']),
                'sample_paths': d['paths'],
                'statuses': dict(d['statuses']),
                'last_seen': d['last_seen'],
                'ua': d['ua'],
            })

    # Sort by threat_requests desc
    threat_ips.sort(key=lambda x: x['threat_requests'], reverse=True)

    return jsonify({
        'log_file': log_file,
        'lines_scanned': len(lines),
        'stats': {
            'total_requests': total_requests,
            'total_threats': total_threats,
            'unique_threat_ips': len(threat_ips),
        },
        'threats': threat_ips[:100],
        'recent': list(reversed(recent_threats)),  # newest first
    })


@app.route('/api/websites/threats/block', methods=['POST'])
@login_required
def block_threat_ip():
    """Block an IP via iptables host (nsenter aware)"""
    data = request.json or {}
    ip = data.get('ip', '').strip()

    import ipaddress
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid IP address'})

    try:
        check = _run_iptables(['-C', 'INPUT', '-s', ip, '-j', 'DROP'])
        if check.returncode == 0:
            return jsonify({'success': True, 'message': f'{ip} already blocked'})

        result = _run_iptables(['-I', 'INPUT', '-s', ip, '-j', 'DROP'])
        if result.returncode == 0:
            audit_log('IP_BLOCKED', f"Blocked IP {ip} via iptables", session.get('username'))
            return jsonify({'success': True, 'message': f'{ip} blocked successfully'})
        else:
            return jsonify({'success': False, 'error': result.stderr})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/websites/threats/unblock', methods=['POST'])
@login_required
def unblock_threat_ip():
    """Unblock an IP via iptables host (nsenter aware)"""
    data = request.json or {}
    ip = data.get('ip', '').strip()

    import ipaddress
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid IP address'})

    try:
        result = _run_iptables(['-D', 'INPUT', '-s', ip, '-j', 'DROP'])
        if result.returncode == 0:
            audit_log('IP_UNBLOCKED', f"Unblocked IP {ip} via iptables", session.get('username'))
            return jsonify({'success': True, 'message': f'{ip} unblocked'})
        else:
            return jsonify({'success': False, 'error': result.stderr or 'IP not in block list'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/websites/threats/blocked_ips')
@login_required
def get_blocked_ips():
    """List currently blocked IPs from host iptables"""
    try:
        result = _run_iptables(['-L', 'INPUT', '-n', '--line-numbers'])
        lines = result.stdout.splitlines()
        blocked = []
        for line in lines:
            if 'DROP' in line:
                parts = line.split()
                for part in parts:
                    try:
                        import ipaddress
                        addr = ipaddress.ip_address(part)
                        blocked.append(str(addr))
                        break
                    except ValueError:
                        continue
        return jsonify({'blocked': blocked})
    except Exception as e:
        return jsonify({'blocked': [], 'error': str(e)})
# ============================================================


@app.route('/api/storage/info')
@login_required
def storage_info():
    """Info lengkap semua mount point disk"""
    partitions = []
    try:

        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append({
                    'device': part.device,
                    'mountpoint': part.mountpoint,
                    'fstype': part.fstype,
                    'total': round(usage.total / (1024**3), 2),
                    'used': round(usage.used / (1024**3), 2),
                    'free': round(usage.free / (1024**3), 2),
                    'percent': usage.percent
                })
            except:
                pass
    except Exception as e:
        pass
    
    # IO counters
    io = psutil.disk_io_counters()
    io_data = {
        'read_mb': round(io.read_bytes / (1024**2), 1) if io else 0,
        'write_mb': round(io.write_bytes / (1024**2), 1) if io else 0,
        'read_count': io.read_count if io else 0,
        'write_count': io.write_count if io else 0,
    }
    
    return jsonify({'partitions': partitions, 'io': io_data})

@app.route('/panel_docker')
@login_required
def panel_docker_page():
    """Halaman Docker Overview (Panel style)"""
    return render_template('panel_docker.html')

@app.route('/api/panel_docker/containers')
@login_required
def panel_docker_containers():
    """Daftar semua Docker containers dengan stats"""
    containers_data = []
    try:
        client = docker.from_env()
        for c in client.containers.list(all=True):
            stats = {}
            if c.status == 'running':
                try:
                    raw = c.stats(stream=False)
                    cpu_delta = raw['cpu_stats']['cpu_usage']['total_usage'] - raw['precpu_stats']['cpu_usage']['total_usage']
                    sys_delta = raw['cpu_stats']['system_cpu_usage'] - raw['precpu_stats']['system_cpu_usage']
                    cpu_pct = round((cpu_delta / sys_delta) * raw['cpu_stats']['online_cpus'] * 100, 1) if sys_delta > 0 else 0
                    mem_used = round(raw['memory_stats']['usage'] / (1024**2), 1)
                    mem_limit = round(raw['memory_stats']['limit'] / (1024**2), 1)
                    stats = {'cpu': cpu_pct, 'mem_used': mem_used, 'mem_limit': mem_limit}
                except:
                    stats = {'cpu': 0, 'mem_used': 0, 'mem_limit': 0}
            
            ports = []
            for k, v in (c.ports or {}).items():
                if v:
                    ports.append(f"{v[0]['HostPort']}→{k}")
            
            containers_data.append({
                'id': c.short_id,
                'name': c.name,
                'image': c.image.tags[0] if c.image.tags else 'none',
                'status': c.status,
                'ports': ', '.join(ports) or '-',
                **stats
            })
    except Exception as e:
        pass
    return jsonify({'containers': containers_data})

@app.route('/api/panel_docker/action', methods=['POST'])
@login_required
def panel_docker_action():
    """Start/Stop/Restart Docker container"""
    data = request.json
    name = data.get('name')
    action = data.get('action')
    
    if not name or action not in ['start', 'stop', 'restart']:
        return jsonify({'success': False, 'error': 'Invalid params'})
    
    try:
        client = docker.from_env()
        c = client.containers.get(name)
        getattr(c, action)()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==========================================
# DATABASE MONITORING API
# ==========================================

@app.route('/api/webpanel/database')
@login_required
def webpanel_database():
    """Cek status MySQL/MariaDB dan list databases"""
    result = {
        'status': 'unknown',
        'version': '-',
        'databases': [],
        'error': None
    }
    try:
        # Cek apakah mysql/mariadb client tersedia
        ver = subprocess.run(['mysql', '--version'], capture_output=True, text=True, timeout=3)
        if ver.returncode == 0:
            result['version'] = ver.stdout.strip().split('\n')[0]
        
        # List databases (tanpa password, pakai unix socket root)
        db_res = subprocess.run(
            ['mysql', '-u', 'root', '-e', 'SHOW DATABASES;', '--batch', '--skip-column-names'],
            capture_output=True, text=True, timeout=5
        )
        if db_res.returncode == 0:
            dbs = [d.strip() for d in db_res.stdout.strip().split('\n') if d.strip()]
            result['databases'] = dbs
            result['status'] = 'running'
        else:
            # Coba via Docker container bernama 'mariadb' atau 'mysql'
            docker_res = subprocess.run(
                ['docker', 'exec', 'mariadb', 'mysql', '-u', 'root', '-e', 'SHOW DATABASES;', '--batch', '--skip-column-names'],
                capture_output=True, text=True, timeout=5
            )
            if docker_res.returncode == 0:
                dbs = [d.strip() for d in docker_res.stdout.strip().split('\n') if d.strip()]
                result['databases'] = dbs
                result['status'] = 'running (docker)'
            else:
                result['status'] = 'not found'
                result['error'] = 'MySQL/MariaDB not accessible'
    except FileNotFoundError:
        result['status'] = 'not installed'
        result['error'] = 'mysql client not found'
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
    
    return jsonify(result)

# ==========================================
# WEB SHIELD & ANALYTICS API
# ==========================================
import requests

@app.route('/web_monitor')
@login_required
def web_monitor_page():
    return redirect(url_for('websites_page', tab='traffic'))

def get_web_shield_domain():
    config_path = os.path.join(DATA_DIR, 'web_shield.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return json.load(f).get('domain', None)
        except: pass
    return None

@app.route('/api/web_monitor/config', methods=['GET', 'POST'])
@login_required
def web_monitor_config():
    config_path = os.path.join(DATA_DIR, 'web_shield.json')
    if request.method == 'POST':
        domain = request.json.get('domain')
        if not domain:
            return jsonify({'error': 'Domain required'}), 400
        domain = domain.replace('https://', '').replace('http://', '').strip('/')
        with open(config_path, 'w') as f:
            json.dump({'domain': domain}, f)
        return jsonify({'success': True, 'domain': domain})
    
    return jsonify({'domain': get_web_shield_domain()})

@app.route('/api/web_monitor/status')
@login_required
def web_monitor_status():
    """Mengambil Hardware, SSL, dan Uptime Status"""
    domain = get_web_shield_domain()
    if not domain:
        # Fallback domain dari vhost aktif
        vhosts = _get_all_vhosts()
        for v in vhosts:
            if v.get('domain') and v.get('domain') != '_':
                domain = v.get('domain')
                break
    if not domain:
        domain = 'localhost'
    
    # 1. Hardware Monitoring
    temp_c = 0
    try:
        with open('/host/root/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp_c = int(f.read().strip()) / 1000.0
    except:
        pass
        
    cpu_usage = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory()
    ram_usage = ram.percent
    
    # Server Uptime
    uptime_seconds = 0
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
    except:
        pass
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    uptime_str = f"{days}d {hours}h"

    # SSL Expiry
    ssl_info = check_ssl_expiry(domain)
    
    # Is Online
    try:
        res = requests.get(f'https://{domain}', timeout=3)
        is_online = (res.status_code == 200)
    except:
        is_online = False

    return jsonify({
        "temp": temp_c,
        "cpu_usage": cpu_usage,
        "ram_usage": ram_usage,
        "uptime": uptime_str,
        "ssl_days": ssl_info.get("days_left", 0),
        "is_online": is_online
    })

@app.route('/api/web_monitor/ssl_details')
@login_required
def web_monitor_ssl_details():
    domain = get_web_shield_domain()
    if not domain:
        return api_websites_ssl_status()
    return jsonify(check_ssl_expiry(domain))

@app.route('/api/web_monitor/traffic')
@login_required
def web_monitor_traffic():
    """Alias backward-compatible untuk traffic access.log"""
    return api_websites_traffic()

def _read_auth_log_lines(max_lines=1500):
    """Baca baris log autentikasi SSH lintas distro (/var/log/auth.log, /var/log/secure, /var/log/messages, atau journalctl)."""
    host_root = os.environ.get('HOST_ROOT', '/host/root')
    rel_paths = ('var/log/auth.log', 'var/log/secure', 'var/log/messages')
    for rel in rel_paths:
        for base in (host_root, '/'):
            p = os.path.join(base, rel)
            if os.path.exists(p):
                try:
                    with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                        return f.readlines()[-max_lines:]
                except Exception:
                    pass
    res = _run_journalctl(['-u', 'ssh', '-u', 'sshd', '-n', str(max_lines), '--no-pager'], timeout=6)
    if res.returncode == 0 and res.stdout:
        return res.stdout.splitlines()
    return []


@app.route('/api/web_monitor/bot_details')
@login_required
def web_monitor_bot_details():
    log_path = _find_host_access_log()
    blocked_list = []
    try:
        if log_path and os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[-5000:]
                for line in reversed(lines):
                    parts = line.split()
                    if len(parts) > 6 and ('403' in parts or 'bot' in line.lower() or 'spider' in line.lower()):
                        ip = parts[0]
                        ua = line.split('"')[5] if len(line.split('"')) > 5 else "Unknown"
                        time_str = parts[3][1:] if len(parts) > 3 else "Unknown"
                        blocked_list.append({"ip": ip, "time": time_str, "ua": ua[:50]})
                        if len(blocked_list) >= 15: break
    except: pass
    return jsonify({"bots": blocked_list})

@app.route('/api/web_monitor/security')
@login_required
def web_monitor_security():
    """Cek Failed SSH Logins lintas distro (auth.log / secure / messages / journalctl)"""
    failed_logins = 0
    try:
        for line in _read_auth_log_lines(max_lines=1500):
            if 'Failed password' in line or 'authentication failure' in line or 'Invalid user' in line:
                failed_logins += 1
    except Exception:
        pass
    return jsonify({"failed_logins": failed_logins})

@app.route('/api/web_monitor/backup')
@login_required
def web_monitor_backup():
    """Alias backward-compatible untuk backup web root"""
    return api_websites_backup()


@app.route('/lxd')
@login_required
def lxd_page():
    """Halaman LXD Container Manager"""
    return render_template('lxd.html')

def _lxc_cmd(args, project='default'):
    """Bungkus perintah lxc dengan nsenter host dan parameter project jika ada."""
    cmd = ['nsenter', '-t', '1', '-m', '-u', '-i', '-n', '-p', '--', 'lxc']
    if project and project != 'default':
        cmd += ['--project', project]
    cmd += args
    return cmd


def _detect_lxc_binary():
    """Detect whether LXD (`lxc`) or Incus (`incus`) CLI is installed on the host (including /snap/bin)."""
    probe = 'PATH="$PATH:/snap/bin:/usr/local/bin:/usr/sbin:/sbin"; command -v lxc || command -v incus'
    res = _run_host_cmd(['sh', '-c', probe], timeout=3, include_pid=False)
    if res.returncode == 0 and (res.stdout or '').strip():
        return res.stdout.strip().splitlines()[0].strip()
    return None


def _run_lxc_cmd(args, project='default', timeout=15, binary=None):
    """Run LXD or Incus command universally (Docker nsenter or Native Linux)."""
    exe = binary or _detect_lxc_binary() or 'lxc'
    cmd = [exe]
    if project and project != 'default':
        cmd += ['--project', project]
    cmd += args
    return _run_host_cmd(cmd, timeout=timeout, include_pid=True)


@app.route('/api/lxd/containers')
@login_required
def api_lxd_containers():
    """Daftar semua LXD/Incus containers secara universal dengan graceful empty state."""
    try:
        lxc_bin = _detect_lxc_binary()
        if not lxc_bin:
            return jsonify({
                'installed': False,
                'available': False,
                'engine': None,
                'containers': [],
                'message': 'LXD/Incus is not installed on this server.'
            })

        res = _run_lxc_cmd(['list', '--all-projects', '--format', 'json'], timeout=12, binary=lxc_bin)
        if res.returncode == 0 and (res.stdout or '').strip():
            data = json.loads(res.stdout)
            return jsonify({
                'installed': True,
                'available': True,
                'engine': lxc_bin,
                'containers': data
            })

        err_msg = (res.stderr or res.stdout or 'LXD daemon is not running or inaccessible').strip()
        return jsonify({
            'installed': True,
            'available': False,
            'engine': lxc_bin,
            'containers': [],
            'error': err_msg
        })
    except Exception as e:
        return jsonify({
            'installed': False,
            'available': False,
            'engine': None,
            'containers': [],
            'error': str(e)
        })

@app.route('/api/lxd/action', methods=['POST'])
@login_required
def api_lxd_action():
    """Start/Stop/Restart/Delete LXD container"""
    data = request.json or {}
    name = data.get('name')
    action = data.get('action')
    project = data.get('project') or 'default'
    
    if not name or action not in ['start', 'stop', 'restart', 'delete']:
        return jsonify({'success': False, 'error': 'Invalid params'})
    
    try:
        args = ['delete', '-f', name] if action == 'delete' else [action, name]
        res = _run_lxc_cmd(args, project=project, timeout=30)
        if res.returncode == 0:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': res.stderr or res.stdout})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/lxd/create', methods=['POST'])
@login_required
def api_lxd_create():
    """Create LXD container"""
    data = request.json or {}
    name = data.get('name')
    image = data.get('image', 'ubuntu:22.04')
    project = data.get('project') or 'default'
    
    if not name:
        return jsonify({'success': False, 'error': 'Name is required'})
        
    try:
        res = _run_lxc_cmd(['launch', image, name], project=project, timeout=120)
        if res.returncode == 0:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': res.stderr or res.stdout})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/lxd/config', methods=['POST'])
@login_required
def api_lxd_config():
    """Set LXD container resource limits (CPU, RAM, Storage)"""
    data = request.json or {}
    name = data.get('name')
    project = data.get('project') or 'default'
    ram = data.get('ram')
    cpu = data.get('cpu')
    storage = data.get('storage')
    
    if not name:
        return jsonify({'success': False, 'error': 'Name is required'})
        
    try:
        if ram:
            _run_lxc_cmd(['config', 'set', name, 'limits.memory', ram], project=project)
        if cpu:
            _run_lxc_cmd(['config', 'set', name, 'limits.cpu', str(cpu)], project=project)
        if storage:
            res = _run_lxc_cmd(['config', 'device', 'set', name, 'root', f'size={storage}'], project=project)
            if res.returncode != 0:
                _run_lxc_cmd(['config', 'device', 'override', name, 'root', f'size={storage}'], project=project)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/lxd/device/add', methods=['POST'])
@login_required
def api_lxd_device_add():
    """Add a proxy device (Port Forwarding) to container"""
    data = request.json or {}
    name = data.get('name')
    project = data.get('project') or 'default'
    device_name = data.get('device_name')
    host_port = data.get('host_port')
    container_port = data.get('container_port')
    protocol = data.get('protocol', 'tcp')
    
    if not name or not device_name or not host_port or not container_port:
        return jsonify({'success': False, 'error': 'All fields are required'})
        
    try:
        listen_str = f"{protocol}:0.0.0.0:{host_port}"
        connect_str = f"{protocol}:127.0.0.1:{container_port}"
        res = _run_lxc_cmd(['config', 'device', 'add', name, device_name, 'proxy', f'listen={listen_str}', f'connect={connect_str}'], project=project)
        if res.returncode == 0:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': res.stderr or res.stdout})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/lxd/device/remove', methods=['POST'])
@login_required
def api_lxd_device_remove():
    """Remove a device from container"""
    data = request.json or {}
    name = data.get('name')
    project = data.get('project') or 'default'
    device_name = data.get('device_name')
    
    if not name or not device_name:
        return jsonify({'success': False, 'error': 'Name and device_name are required'})
        
    try:
        res = _run_lxc_cmd(['config', 'device', 'remove', name, device_name], project=project)
        if res.returncode == 0:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': res.stderr or res.stdout})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/lxd/advanced', methods=['POST'])
@login_required
def api_lxd_advanced():
    """Set advanced container settings (nesting, privileged, autostart)"""
    data = request.json or {}
    name = data.get('name')
    project = data.get('project') or 'default'
    nesting = data.get('nesting')
    privileged = data.get('privileged')
    autostart = data.get('autostart')
    
    if not name:
        return jsonify({'success': False, 'error': 'Name is required'})
        
    try:
        if nesting is not None:
            _run_lxc_cmd(['config', 'set', name, 'security.nesting', nesting], project=project)
        if privileged is not None:
            _run_lxc_cmd(['config', 'set', name, 'security.privileged', privileged], project=project)
        if autostart is not None:
            _run_lxc_cmd(['config', 'set', name, 'boot.autostart', autostart], project=project)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/lxd/tools/status')
@login_required
def api_lxd_tools_status():
    """Check if Tailscale and Wireguard are installed and get their running status inside the container"""
    name = request.args.get('name')
    project = request.args.get('project') or 'default'
    if not name:
        return jsonify({'error': 'Container name is required'}), 400
        
    try:
        # Check if container is running first. If not running, tools status cannot be queried.
        info_res = subprocess.run(_lxc_cmd(['info', name], project=project), capture_output=True, text=True)
        if "Status: RUNNING" not in info_res.stdout:
            return jsonify({
                'success': True,
                'running': False,
                'tailscale': {'installed': False, 'status': 'Container is stopped', 'ip': ''},
                'wireguard': {'installed': False, 'status': 'Container is stopped'}
            })
            
        # 1. Check Tailscale
        ts_installed = False
        ts_status = "Not Installed"
        ts_ip = ""
        
        # Test which tailscale
        ts_check = subprocess.run(_lxc_cmd(['exec', name, '--', 'which', 'tailscale'], project=project), capture_output=True, text=True)
        if ts_check.returncode == 0:
            ts_installed = True
            # Check tailscale status
            ts_status_run = subprocess.run(_lxc_cmd(['exec', name, '--', 'tailscale', 'status'], project=project), capture_output=True, text=True)
            if "Logged out" in ts_status_run.stdout or "No link established" in ts_status_run.stdout:
                ts_status = "Disconnected"
            elif "Authentication required" in ts_status_run.stdout:
                ts_status = "Needs Authentication"
            elif ts_status_run.returncode == 0 and len(ts_status_run.stdout.strip()) > 0:
                ts_status = "Connected"
                # Try getting Tailscale IP
                ts_ip_run = subprocess.run(_lxc_cmd(['exec', name, '--', 'tailscale', 'ip', '-4'], project=project), capture_output=True, text=True)
                if ts_ip_run.returncode == 0:
                    ts_ip = ts_ip_run.stdout.strip()
            else:
                ts_status = "Stopped"
                
        # 2. Check Wireguard
        wg_installed = False
        wg_status = "Not Installed"
        
        wg_check = subprocess.run(_lxc_cmd(['exec', name, '--', 'which', 'wg'], project=project), capture_output=True, text=True)
        if wg_check.returncode == 0:
            wg_installed = True
            # Check if wireguard module or configs exists / runs
            wg_show = subprocess.run(_lxc_cmd(['exec', name, '--', 'wg', 'show'], project=project), capture_output=True, text=True)
            if wg_show.returncode == 0 and len(wg_show.stdout.strip()) > 0:
                wg_status = "Active"
            else:
                wg_status = "Installed (Inactive)"
                
        return jsonify({
            'success': True,
            'running': True,
            'tailscale': {
                'installed': ts_installed,
                'status': ts_status,
                'ip': ts_ip
            },
            'wireguard': {
                'installed': wg_installed,
                'status': wg_status
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/lxd/tools/install', methods=['POST'])
@login_required
def api_lxd_tools_install():
    """Install and configure Tailscale or Wireguard in the container"""
    data = request.json
    name = data.get('name')
    project = data.get('project') or 'default'
    tool = data.get('tool') # 'tailscale' or 'wireguard'
    
    if not name or tool not in ['tailscale', 'wireguard']:
        return jsonify({'success': False, 'error': 'Invalid parameters'})
        
    try:
        # 1. Enable Nesting and TUN device first (essential for VPNs)
        subprocess.run(_lxc_cmd(['config', 'set', name, 'security.nesting', 'true'], project=project))
        subprocess.run(_lxc_cmd(['config', 'device', 'add', name, 'tun', 'unix-char', 'path=/dev/net/tun'], project=project), capture_output=True)
        
        # 2. Check and install dependencies (curl)
        subprocess.run(_lxc_cmd(['exec', name, '--', 'bash', '-c', 'apt-get update && apt-get install -y curl || apk add curl || yum install -y curl'], project=project), capture_output=True)
        
        if tool == 'tailscale':
            install_cmd = _lxc_cmd(['exec', name, '--', 'bash', '-c', 'curl -fsSL https://tailscale.com/install.sh | sh'], project=project)
            res = subprocess.run(install_cmd, capture_output=True, text=True)
            if res.returncode != 0:
                return jsonify({'success': False, 'error': f'Failed to install Tailscale: {res.stderr}'})
                
            subprocess.run(_lxc_cmd(['exec', name, '--', 'systemctl', 'enable', '--now', 'tailscaled'], project=project), capture_output=True)
            subprocess.run(_lxc_cmd(['exec', name, '--', 'service', 'tailscaled', 'start'], project=project), capture_output=True)
            
            # Run tailscale up and capture login URL from stdout/stderr (using 15s timeout to not block)
            up_cmd = _lxc_cmd(['exec', name, '--', 'tailscale', 'up', '--timeout=15s'], project=project)
            try:
                up_res = subprocess.run(up_cmd, capture_output=True, text=True, timeout=20)
                output = up_res.stdout + "\n" + up_res.stderr
            except subprocess.TimeoutExpired as te:
                output = (te.stdout.decode('utf-8', errors='ignore') if te.stdout else "") + "\n" + (te.stderr.decode('utf-8', errors='ignore') if te.stderr else "")
                
            login_url = ""
            for line in output.split('\n'):
                if "https://login.tailscale.com" in line:
                    # Find exact URL
                    words = line.split()
                    for word in words:
                        if word.startswith("https://login.tailscale.com"):
                            login_url = word.strip()
                            break
                    if login_url:
                        break
                    
            return jsonify({
                'success': True,
                'login_url': login_url,
                'output': output
            })
            
        elif tool == 'wireguard':
            install_cmd = _lxc_cmd(['exec', name, '--', 'bash', '-c', 'apt-get update && apt-get install -y wireguard wireguard-tools iptables || apk add wireguard-tools || yum install -y wireguard-tools'], project=project)
            res = subprocess.run(install_cmd, capture_output=True, text=True)
            if res.returncode != 0:
                return jsonify({'success': False, 'error': f'Failed to install Wireguard: {res.stderr}'})
                
            return jsonify({
                'success': True,
                'message': 'Wireguard package and iptables installed successfully! You can configure it via the container terminal.'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# =====================================================================
# ADBLOCKER / ADGUARD HOME INTEGRATION (OPEN SOURCE & PORTABLE)
# =====================================================================
ADBLOCKER_CONFIG_FILE = os.path.join(DATA_DIR, 'adblocker_config.json')

def get_adblocker_config():
    """Mengambil konfigurasi AdGuard Home dari data/adblocker_config.json atau ENV"""
    default_host = "host.docker.internal" if (os.path.exists('/.dockerenv') or os.path.exists('/host/proc')) else "127.0.0.1"
    cfg = {
        "host": os.environ.get("ADGUARD_HOST", default_host),
        "port": int(os.environ.get("ADGUARD_PORT", "8053")),
        "username": os.environ.get("ADGUARD_USER", ""),
        "password": os.environ.get("ADGUARD_PASSWORD", ""),
        "tls": os.environ.get("ADGUARD_TLS", "0") == "1",
        "timeout": int(os.environ.get("ADGUARD_TIMEOUT", "5"))
    }
    if os.path.exists(ADBLOCKER_CONFIG_FILE):
        try:
            with open(ADBLOCKER_CONFIG_FILE, 'r') as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    cfg.update(saved)
        except Exception as e:
            print(f"[AdBlocker] Failed to load config: {e}")
    return cfg

def save_adblocker_config(new_cfg):
    """Menyimpan konfigurasi AdGuard Home ke data/adblocker_config.json"""
    cfg = get_adblocker_config()
    for k in ['host', 'port', 'username', 'tls', 'timeout']:
        if k in new_cfg:
            cfg[k] = new_cfg[k]
    # Hanya perbarui password bila dikirim dan tidak kosong
    if new_cfg.get('password'):
        cfg['password'] = new_cfg['password']
    with open(ADBLOCKER_CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)
    return cfg

def adguard_api_call(endpoint, method='GET', json_body=None, custom_cfg=None):
    """Konektor API generik ke AdGuard Home daemon"""
    cfg = custom_cfg or get_adblocker_config()
    proto = "https" if cfg.get("tls") else "http"
    host = cfg.get("host", "127.0.0.1")
    port = cfg.get("port", 8053)
    base_url = f"{proto}://{host}:{port}"
    url = f"{base_url}{endpoint}"
    
    auth = None
    if cfg.get("username") or cfg.get("password"):
        auth = (cfg.get("username", ""), cfg.get("password", ""))
        
    timeout = cfg.get("timeout", 5)
    
    try:
        if method.upper() == 'GET':
            resp = requests.get(url, auth=auth, timeout=timeout)
        elif method.upper() == 'POST':
            resp = requests.post(url, auth=auth, json=json_body, timeout=timeout)
        else:
            return False, f"Metode HTTP tidak didukung: {method}", 400
            
        if resp.status_code >= 400:
            return False, f"AdGuard API error ({resp.status_code}): {resp.text}", resp.status_code
            
        content_type = resp.headers.get('content-type', '')
        if 'application/json' in content_type:
            return True, resp.json(), 200
        return True, resp.text, 200
    except requests.exceptions.ConnectionError:
        return False, f"Tidak dapat terhubung ke AdGuard Home di {base_url}. Pastikan layanan aktif dan host/port sesuai.", 503
    except requests.exceptions.Timeout:
        return False, f"Koneksi ke AdGuard Home timeout ({timeout} detik).", 504
    except Exception as e:
        return False, str(e), 500

def get_host_network_ips():
    """Mengambil IP LAN fisik dan IP Tailscale host yang valid untuk DNS"""
    lan_ips = []
    tailscale_ips = []
    try:
        res = subprocess.run(['nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'ip', '-j', 'addr'], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            for iface in data:
                name = iface.get('ifname', '')
                if name == 'lo' or name.startswith('br-') or name.startswith('docker') or name.startswith('veth') or name.startswith('lxd'):
                    continue
                for addr in iface.get('addr_info', []):
                    if addr.get('family') == 'inet':
                        ip = addr.get('local')
                        if ip and not ip.startswith('127.'):
                            if name.startswith('tailscale') or name.startswith('wg'):
                                tailscale_ips.append({'name': name, 'ip': ip, 'type': 'Tailscale VPN'})
                            else:
                                lan_ips.append({'name': name, 'ip': ip, 'type': 'LAN / Router'})
    except Exception as e:
        print(f"[AdBlocker] Error detecting host IPs: {e}")
        
    return lan_ips, tailscale_ips

def _get_host_default_gateway():
    """Deteksi IP default gateway jaringan host secara dinamis via kernel routing table."""
    try:
        cmd = (['nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'ip', 'route', 'show', 'default']
               if _can_use_nsenter() else ['ip', 'route', 'show', 'default'])
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if res.returncode == 0 and res.stdout:
            m = re.search(r'\bvia\s+(\d+\.\d+\.\d+\.\d+)\b', res.stdout)
            if m:
                return m.group(1)
    except Exception:
        pass

    for route_path in (os.path.join(os.environ.get('HOST_PROC', '/host/proc'), 'net/route'), '/proc/net/route'):
        if os.path.exists(route_path):
            try:
                with open(route_path, 'r') as f:
                    for line in f.readlines()[1:]:
                        parts = line.strip().split()
                        if len(parts) >= 3 and parts[1] == '00000000':
                            gw_hex = parts[2]
                            octets = [str(int(gw_hex[i:i+2], 16)) for i in (6, 4, 2, 0)]
                            gw_ip = '.'.join(octets)
                            if gw_ip != '0.0.0.0':
                                return gw_ip
            except Exception:
                pass
    return None


@app.route('/adblocker')
@login_required
@requires_permission('adblocker')
def adblocker_page():
    """Halaman AdBlocker DNS Manager"""
    return render_template('adblocker.html')

@app.route('/api/adblocker/status')
@login_required
@requires_permission('adblocker')
def api_adblocker_status():
    """Mengambil status proteksi, statistik query, IP host, dan status fitur keamanan"""
    cfg = get_adblocker_config()
    proto = "https" if cfg.get("tls") else "http"
    base_url = f"{proto}://{cfg.get('host')}:{cfg.get('port')}"

    # Cek status proteksi
    ok_status, res_status, code_status = adguard_api_call('/control/status')
    if not ok_status:
        return jsonify({
            'installed': False,
            'available': False,
            'connected': False,
            'error': res_status,
            'base_url': base_url,
            'host': cfg.get('host'),
            'port': cfg.get('port')
        })

    # Cek statistik query
    ok_stats, res_stats, code_stats = adguard_api_call('/control/stats')
    stats_data = res_stats if ok_stats and isinstance(res_stats, dict) else {}

    # Ambil IP jaringan host yang valid
    lan_ips, tailscale_ips = get_host_network_ips()
    if not lan_ips:
        # Fallback jika nsenter tidak mengembalikan IP
        for ip in res_status.get('dns_addresses', []):
            if ip not in ['127.0.0.1', '::1', '0.0.0.0'] and not ip.startswith('172.') and not ip.startswith('192.168.64.'):
                if ip.startswith('100.'):
                    tailscale_ips.append({'name': 'tailscale', 'ip': ip, 'type': 'Tailscale VPN'})
                else:
                    lan_ips.append({'name': 'lan', 'ip': ip, 'type': 'LAN / Router'})

    # Ambil status fitur keamanan tambahan
    ok_sb, sb_st, _ = adguard_api_call('/control/safebrowsing/status')
    ok_ss, ss_st, _ = adguard_api_call('/control/safesearch/status')
    ok_par, par_st, _ = adguard_api_call('/control/parental/status')

    # Format Klien Teratas dengan Nama Perangkat (Device Name) & Rasio Persentase
    client_names = {}
    ok_c, clients_data, _ = adguard_api_call('/control/clients')
    if ok_c and isinstance(clients_data, dict):
        for c in (clients_data.get('clients') or []):
            c_name = c.get('name', '')
            for cid in (c.get('ids') or []):
                client_names[cid] = c_name
        for ac in (clients_data.get('auto_clients') or []):
            ac_name = ac.get('name', '')
            ac_ip = ac.get('ip', '')
            if ac_ip and ac_name and ac_ip not in client_names:
                client_names[ac_ip] = ac_name

    raw_clients = stats_data.get('top_clients', [])
    total_q = stats_data.get('num_dns_queries', 0)
    formatted_clients = []

    default_gw = _get_host_default_gateway()
    lan_ip_values = [x.get('ip') for x in lan_ips]
    for item in raw_clients:
        if isinstance(item, dict):
            for ip, count in item.items():
                is_gateway = bool(default_gw and ip == default_gw)
                name = client_names.get(ip, '')
                # Heuristik otomatis nama jika belum dinamai
                if not name:
                    if is_gateway:
                        name = 'Router / Gateway'
                    elif ip in lan_ip_values or ip in ('127.0.0.1', '::1'):
                        host_label = socket.gethostname() or 'Local'
                        name = f"Host Server ({host_label})"
                    elif ip.startswith('100.'):
                        name = 'Klien Tailscale'
                    else:
                        try:
                            resolved = socket.gethostbyaddr(ip)[0]
                            if resolved and resolved != ip:
                                name = resolved
                        except Exception:
                            pass

                pct = round((count / total_q * 100), 2) if total_q > 0 else 0
                formatted_clients.append({
                    'ip': ip,
                    'name': name or 'Perangkat Tanpa Nama',
                    'has_custom_name': bool(name and name != 'Perangkat Tanpa Nama'),
                    'is_gateway': is_gateway,
                    'count': count,
                    'percent': pct
                })

    return jsonify({
        'installed': True,
        'available': True,
        'connected': True,
        'base_url': base_url,
        'web_port': cfg.get('port', 8053),
        'status': res_status,
        'stats': stats_data,
        'top_clients_formatted': formatted_clients,
        'protection_enabled': res_status.get('protection_enabled', False),
        'dns_addresses': res_status.get('dns_addresses', []),
        'dns_port': res_status.get('dns_port', 53),
        'version': res_status.get('version', 'Unknown'),
        'lan_ips': lan_ips,
        'tailscale_ips': tailscale_ips,
        'safebrowsing_enabled': sb_st.get('enabled', False) if ok_sb and isinstance(sb_st, dict) else False,
        'safesearch_enabled': ss_st.get('enabled', False) if ok_ss and isinstance(ss_st, dict) else False,
        'parental_enabled': par_st.get('enabled', False) if ok_par and isinstance(par_st, dict) else False
    })

@app.route('/api/adblocker/client/rename', methods=['POST'])
@login_required
@requires_permission('adblocker', 'full')
def api_adblocker_client_rename():
    """Memberi nama atau alias pada perangkat / client IP di AdGuard Home"""
    data = request.json or {}
    ip = str(data.get('ip', '')).strip()
    name = str(data.get('name', '')).strip()

    if not ip or not name:
        return jsonify({'success': False, 'error': 'Alamat IP dan nama perangkat wajib diisi'}), 400

    # Cek apakah client sudah ada di AdGuard
    ok_f, find_res, _ = adguard_api_call(f'/control/clients/find?ip0={ip}')
    client_exists = False
    old_name = None
    if ok_f and isinstance(find_res, list) and len(find_res) > 0:
        c_info = find_res[0].get(ip, {})
        if c_info.get('name'):
            client_exists = True
            old_name = c_info.get('name')

    if client_exists and old_name:
        payload = {
            'name': old_name,
            'data': {
                'name': name,
                'ids': [ip],
                'use_global_settings': True,
                'filtering_enabled': True
            }
        }
        ok, res, code = adguard_api_call('/control/clients/update', method='POST', json_body=payload)
    else:
        payload = {
            'name': name,
            'ids': [ip],
            'use_global_settings': True,
            'filtering_enabled': True
        }
        ok, res, code = adguard_api_call('/control/clients/add', method='POST', json_body=payload)

    if ok:
        audit_log('ADBLOCKER_CLIENT_RENAME', f"Renamed client {ip} to '{name}'", session.get('username'))
        return jsonify({'success': True, 'message': f"Perangkat {ip} berhasil dinamai '{name}'."})
    return jsonify({'success': False, 'error': str(res)}), code

@app.route('/api/adblocker/feature/<feature_name>', methods=['POST'])
@login_required
@requires_permission('adblocker', 'full')
def api_adblocker_feature_toggle(feature_name):
    """Toggle SafeBrowsing, SafeSearch, atau Parental Control"""
    if feature_name not in ['safebrowsing', 'safesearch', 'parental']:
        return jsonify({'success': False, 'error': f'Fitur {feature_name} tidak valid'}), 400

    data = request.json or {}
    enable = bool(data.get('enabled', False))
    action = 'enable' if enable else 'disable'

    ok, res, code = adguard_api_call(f'/control/{feature_name}/{action}', method='POST')
    if ok:
        audit_log('ADBLOCKER_FEATURE', f"{feature_name} set to {enable}", session.get('username'))
        return jsonify({'success': True, 'feature': feature_name, 'enabled': enable})
    return jsonify({'success': False, 'error': str(res)}), code

@app.route('/api/adblocker/querylog', methods=['GET'])
@login_required
@requires_permission('adblocker')
def api_adblocker_querylog():
    """Mengambil riwayat query DNS terakhir"""
    limit = int(request.args.get('limit', 15))
    ok, res, code = adguard_api_call(f'/control/querylog?limit={limit}')
    if ok and isinstance(res, dict):
        return jsonify({'success': True, 'data': res.get('data', [])})
    return jsonify({'success': False, 'error': str(res)}), code

@app.route('/api/adblocker/toggle', methods=['POST'])
@login_required
@requires_permission('adblocker', 'full')
def api_adblocker_toggle():
    """Toggle proteksi AdGuard ON/OFF"""
    data = request.json or {}
    enabled = bool(data.get('enabled', False))
    ok, res, code = adguard_api_call('/control/protection', method='POST', json_body={'enabled': enabled})
    if ok:
        audit_log('ADBLOCKER_TOGGLE', f"Protection set to {enabled}", session.get('username'))
        return jsonify({'success': True, 'protection_enabled': enabled})
    return jsonify({'success': False, 'error': str(res)}), code

@app.route('/api/adblocker/rules', methods=['GET', 'POST'])
@login_required
def api_adblocker_rules():
    """Membaca atau memperbarui custom rules AdGuard Home"""
    if request.method == 'GET':
        role = session.get('role', 'readonly')
        if not has_permission(role, 'adblocker'):
            return jsonify({'error': 'Permission denied'}), 403
        ok, res, code = adguard_api_call('/control/filtering/status')
        if ok and isinstance(res, dict):
            return jsonify({
                'success': True,
                'user_rules': res.get('user_rules', []),
                'filters': res.get('filters', [])
            })
        return jsonify({'success': False, 'error': str(res)}), code

    # POST: Simpan custom rules
    role = session.get('role', 'readonly')
    if not has_permission(role, 'adblocker', 'full'):
        return jsonify({'error': 'Admin/Owner permission required to edit rules'}), 403

    data = request.json or {}
    rules = data.get('rules', [])
    if isinstance(rules, str):
        rules = [line.strip() for line in rules.splitlines() if line.strip()]

    ok, res, code = adguard_api_call('/control/filtering/set_rules', method='POST', json_body={'rules': rules})
    if ok:
        audit_log('ADBLOCKER_RULES', f"Updated custom rules ({len(rules)} rules)", session.get('username'))
        return jsonify({'success': True, 'rules_count': len(rules)})
    return jsonify({'success': False, 'error': str(res)}), code

@app.route('/api/adblocker/config', methods=['GET', 'POST'])
@login_required
def api_adblocker_config():
    """Membaca atau menyimpan konfigurasi koneksi AdGuard Home"""
    if request.method == 'GET':
        role = session.get('role', 'readonly')
        if not has_permission(role, 'adblocker'):
            return jsonify({'error': 'Permission denied'}), 403
        cfg = get_adblocker_config()
        # Jangan kirim password plaintext
        safe_cfg = {
            'host': cfg.get('host', '127.0.0.1'),
            'port': cfg.get('port', 8053),
            'username': cfg.get('username', ''),
            'has_password': bool(cfg.get('password')),
            'tls': cfg.get('tls', False),
            'timeout': cfg.get('timeout', 5)
        }
        return jsonify({'success': True, 'config': safe_cfg})

    # POST: Simpan konfigurasi koneksi baru
    role = session.get('role', 'readonly')
    if not has_permission(role, 'adblocker', 'full'):
        return jsonify({'error': 'Admin/Owner permission required to update config'}), 403

    data = request.json or {}
    test_cfg = {
        'host': str(data.get('host', '127.0.0.1')).strip(),
        'port': int(data.get('port', 8053)),
        'username': str(data.get('username', '')).strip(),
        'password': str(data.get('password', '')),
        'tls': bool(data.get('tls', False)),
        'timeout': int(data.get('timeout', 5))
    }
    
    # Bila password kosong di request tapi sebelumnya sudah ada, pertahankan password lama
    if not test_cfg['password']:
        existing = get_adblocker_config()
        test_cfg['password'] = existing.get('password', '')

    # Tes koneksi terlebih dahulu
    ok, res, code = adguard_api_call('/control/status', custom_cfg=test_cfg)
    if not ok:
        return jsonify({
            'success': False,
            'error': f"Uji koneksi gagal: {res}. Pastikan kredensial dan alamat sudah benar."
        }), 400

    saved = save_adblocker_config(test_cfg)
    audit_log('ADBLOCKER_CONFIG', f"Updated config host={saved.get('host')}:{saved.get('port')}", session.get('username'))
    return jsonify({
        'success': True,
        'message': 'Konfigurasi AdGuard Home berhasil disimpan dan diverifikasi aktif!'
    })

@app.route('/api/adblocker/install', methods=['POST'])
@login_required
def api_adblocker_install():
    """1-Click AdGuard Home Docker installer"""
    role = session.get('role', 'readonly')
    if not has_permission(role, 'adblocker', 'full'):
        return jsonify({'success': False, 'error': 'Hak akses Admin/Owner diperlukan untuk instalasi'}), 403

    data = request.json or {}
    web_port = int(data.get('web_port', 8053))
    dns_port = int(data.get('dns_port', 53))

    try:
        import docker as docker_lib
        client = docker_lib.from_env()
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Tidak dapat terhubung ke Docker Engine: {str(e)}. Pastikan Docker aktif di server.'
        }), 500

    container_name = "adguardhome"
    
    # 1. Cek apakah container sudah ada
    try:
        existing = client.containers.get(container_name)
        if existing.status == 'running':
            return jsonify({
                'success': True,
                'already_running': True,
                'message': f'Kontainer {container_name} sudah terpasang dan berstatus aktif.'
            })
        else:
            existing.start()
            audit_log('ADBLOCKER_INSTALL', f"Started existing container {container_name}", session.get('username'))
            return jsonify({
                'success': True,
                'message': f'Kontainer {container_name} yang ada berhasil diaktifkan kembali.'
            })
    except docker_lib.errors.NotFound:
        pass
    except Exception as e:
        return jsonify({'success': False, 'error': f'Gagal memeriksa status kontainer: {str(e)}'}), 500

    # 2. Pull image dan buat kontainer baru
    try:
        image_name = "adguard/adguardhome:latest"
        try:
            client.images.pull(image_name)
        except Exception as pull_err:
            print(f"[AdBlocker Install] Pull warning: {pull_err}")

        # Port bindings
        ports = {
            '53/tcp': dns_port,
            '53/udp': dns_port,
            '80/tcp': web_port,
            '3000/tcp': 3000
        }

        # Volume mounts (Docker named volumes portabel)
        volumes = {
            'adguard_work': {'bind': '/opt/adguardhome/work', 'mode': 'rw'},
            'adguard_conf': {'bind': '/opt/adguardhome/conf', 'mode': 'rw'}
        }

        container = client.containers.run(
            image=image_name,
            name=container_name,
            ports=ports,
            volumes=volumes,
            restart_policy={"Name": "unless-stopped"},
            detach=True
        )

        # 3. Simpan konfigurasi awal di data/adblocker_config.json
        cfg = get_adblocker_config()
        cfg['host'] = 'host.docker.internal'
        cfg['port'] = web_port
        save_adblocker_config(cfg)

        audit_log('ADBLOCKER_INSTALL', f"Installed new container {container_name} on web_port={web_port}, dns_port={dns_port}", session.get('username'))

        return jsonify({
            'success': True,
            'container_id': container.short_id,
            'message': f'AdGuard Home berhasil dipasang dan dijalankan pada port Web {web_port} dan DNS {dns_port}.',
            'web_port': web_port,
            'dns_port': dns_port
        })
    except docker_lib.errors.APIError as api_err:
        err_msg = str(api_err)
        if "port is already allocated" in err_msg or "address already in use" in err_msg:
            return jsonify({
                'success': False,
                'error': f'Port bentrok: {err_msg}. Jika port 53 digunakan systemd-resolved, gunakan port DNS lain atau matikan stub listener host.'
            }), 409
        return jsonify({'success': False, 'error': f'Docker API error: {err_msg}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': f'Gagal menginstal AdGuard Home: {str(e)}'}), 500


# ============================================================
# SERVICES & SYSTEM DAEMONS MANAGER (systemd)
# ============================================================

@app.route('/services')
@login_required
def services_page():
    """Halaman Manajemen Services & System Daemons (systemd)"""
    return render_template('services.html')

@app.route('/api/services/summary')
@login_required
def api_services_summary():
    """Ringkasan status systemd host: total, running, failed, inactive, system_state"""
    res = _run_systemctl(['list-units', '--type=service', '--all', '--output=json'])
    system_state = 'unknown'
    try:
        st_res = _run_systemctl(['is-system-running'])
        system_state = (st_res.stdout or '').strip()
    except Exception:
        pass

    total = 0
    running = 0
    failed = 0
    inactive = 0

    if res.returncode == 0 and res.stdout:
        try:
            data = json.loads(res.stdout)
            total = len(data)
            for item in data:
                act = item.get('active', '')
                sub = item.get('sub', '')
                if act == 'failed' or sub == 'failed':
                    failed += 1
                elif act == 'active' and sub == 'running':
                    running += 1
                elif act == 'inactive' or sub == 'dead':
                    inactive += 1
                else:
                    if act == 'active':
                        running += 1
        except Exception:
            pass

    return jsonify({
        'total': total,
        'running': running,
        'failed': failed,
        'inactive': inactive,
        'system_state': system_state
    })

@app.route('/api/services/list')
@login_required
def api_services_list():
    """Daftar services host dengan filter: all, running, failed, inactive, search query"""
    filter_type = request.args.get('filter', 'all').strip().lower()
    q = request.args.get('q', '').strip().lower()

    cmd = ['list-units', '--type=service', '--all', '--output=json']
    if filter_type == 'failed':
        cmd = ['list-units', '--type=service', '--state=failed', '--output=json']
    elif filter_type == 'running':
        cmd = ['list-units', '--type=service', '--state=running', '--output=json']

    res = _run_systemctl(cmd)
    services = []

    if res.returncode == 0 and res.stdout:
        try:
            raw_data = json.loads(res.stdout)
            for item in raw_data:
                unit = item.get('unit', '')
                if not unit.endswith('.service'):
                    continue

                act = item.get('active', '')
                sub = item.get('sub', '')
                desc = item.get('description', '')
                name = unit[:-8]

                if filter_type == 'inactive' and act != 'inactive' and sub != 'dead':
                    continue

                if q:
                    if q not in unit.lower() and q not in desc.lower() and q not in name.lower():
                        continue

                services.append({
                    'unit': unit,
                    'name': name,
                    'description': desc or name,
                    'load': item.get('load', 'loaded'),
                    'active': act,
                    'sub': sub
                })
        except Exception:
            pass

    def sort_key(s):
        if s['active'] == 'failed' or s['sub'] == 'failed':
            return (0, s['name'])
        if s['active'] == 'active' and s['sub'] == 'running':
            return (1, s['name'])
        return (2, s['name'])

    services.sort(key=sort_key)

    return jsonify({
        'services': services,
        'count': len(services),
        'filter': filter_type
    })

@app.route('/api/services/detail/<unit>')
@login_required
def api_services_detail(unit):
    """Detail inspeksi properti service dan 40 baris log journald terakhir"""
    unit = unit.strip()
    if not unit.endswith('.service'):
        unit += '.service'

    if not re.match(r'^[a-zA-Z0-9_@.-]+\.service$', unit):
        return jsonify({'error': 'Format nama unit tidak valid'}), 400

    props_cmd = [
        'show', unit,
        '--property=Id,Description,LoadState,ActiveState,SubState,MainPID,'
        'MemoryCurrent,CPUUsageNSec,ExecMainStatus,ExecMainCode,UnitFileState,ActiveEnterTimestamp'
    ]
    p_res = _run_systemctl(props_cmd)
    props = {}
    if p_res.stdout:
        for line in p_res.stdout.splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                props[k] = v

    mem_bytes = props.get('MemoryCurrent', '')
    mem_formatted = '0 MB'
    if mem_bytes and mem_bytes.isdigit():
        mb = int(mem_bytes) / (1024 * 1024)
        if mb >= 1024:
            mem_formatted = f"{mb / 1024:.2f} GB"
        else:
            mem_formatted = f"{mb:.1f} MB"
    props['MemoryFormatted'] = mem_formatted

    cpu_nsec = props.get('CPUUsageNSec', '')
    cpu_formatted = '0 s'
    if cpu_nsec and cpu_nsec.isdigit():
        sec = int(cpu_nsec) / 1_000_000_000
        cpu_formatted = f"{sec:.2f} s"
    props['CPUUsageFormatted'] = cpu_formatted

    logs = []
    log_cmd = ['nsenter', '-t', '1', '-m', '-u', '-i', '-n', '-p', '--',
               'journalctl', '-u', unit, '-n', '40', '--no-pager']
    try:
        l_res = subprocess.run(log_cmd, capture_output=True, text=True, timeout=6)
        if l_res.stdout:
            logs = l_res.stdout.splitlines()
    except Exception:
        pass

    return jsonify({
        'unit': unit,
        'properties': props,
        'logs': logs
    })


# ============================================================
# SYSTEM LOGS & JOURNALD EXPLORER (journalctl & dmesg)
# ============================================================

def _run_journalctl(args, timeout=12):
    """Jalankan journalctl pada host via eksekutor universal (nsenter / native)."""
    return _run_host_cmd(['journalctl'] + list(args), timeout=timeout)

def _run_dmesg(args, timeout=10):
    """Jalankan dmesg pada host via eksekutor universal (nsenter / native)."""
    return _run_host_cmd(['dmesg'] + list(args), timeout=timeout)

@app.route('/logs')
@login_required
def system_logs_page():
    """Halaman Utama System Logs & Journald Explorer"""
    return render_template('system_logs.html')

@app.route('/api/logs/summary')
@login_required
def api_logs_summary():
    """Statistik ringkasan log 24 jam terakhir: error count, ssh failed, oom events, kernel alerts"""
    errors_24h = 0
    ssh_failed_24h = 0
    oom_events = 0
    kernel_alerts = 0

    err_res = _run_journalctl(['-p', 'err', '--since', '24 hours ago', '-q', '--no-pager'], timeout=6)
    if err_res.returncode == 0 and err_res.stdout:
        errors_24h = len(err_res.stdout.splitlines())

    ssh_res = _run_journalctl(['-u', 'ssh', '-u', 'sshd', '--grep=Failed password|Invalid user', '--since', '24 hours ago', '-q', '--no-pager'], timeout=6)
    if ssh_res.returncode == 0 and ssh_res.stdout:
        ssh_failed_24h = len(ssh_res.stdout.splitlines())

    dmesg_res = _run_dmesg(['-T', '--level=emerg,alert,crit,err'], timeout=6)
    if dmesg_res.returncode == 0 and dmesg_res.stdout:
        kernel_alerts = len(dmesg_res.stdout.splitlines())

    oom_res = _run_dmesg([], timeout=6)
    if oom_res.returncode == 0 and oom_res.stdout:
        for line in oom_res.stdout.splitlines():
            low = line.lower()
            if 'oom-killer' in low or 'out of memory' in low or 'killed process' in low:
                oom_events += 1

    return jsonify({
        'errors_24h': errors_24h,
        'ssh_failed_24h': ssh_failed_24h,
        'oom_events': oom_events,
        'kernel_alerts': kernel_alerts
    })

@app.route('/api/logs/journal')
@login_required
def api_logs_journal():
    """Query log journald interaktif dengan filter unit, priority, rentang waktu, limit, dan search"""
    unit = request.args.get('unit', '').strip()
    priority = request.args.get('priority', 'all').strip().lower()
    since = request.args.get('since', '1h').strip()
    limit = request.args.get('limit', '100').strip()
    q = request.args.get('q', '').strip()

    try:
        limit_num = max(10, min(500, int(limit)))
    except ValueError:
        limit_num = 100

    cmd = ['-n', str(limit_num), '-o', 'json', '-r', '--no-pager']

    if unit:
        if not unit.endswith('.service'):
            unit += '.service'
        if not re.match(r'^[a-zA-Z0-9_@.-]+\.service$', unit):
            return jsonify({'success': False, 'error': 'Format nama unit tidak valid'}), 400
        cmd.extend(['-u', unit])

    priority_map = {
        'emerg': '0', 'alert': '1', 'crit': '2', 'err': '3',
        'warning': '4', 'notice': '5', 'info': '6', 'debug': '7',
        'errors_only': '0..3', 'warnings_and_errors': '0..4'
    }
    if priority in priority_map:
        cmd.extend(['-p', priority_map[priority]])

    since_map = {
        '15m': '15 minutes ago',
        '1h': '1 hour ago',
        '6h': '6 hours ago',
        '24h': '24 hours ago',
        '7d': '7 days ago',
        'today': 'today'
    }
    if since in since_map:
        cmd.extend(['--since', since_map[since]])

    if q:
        cmd.extend(['--grep', q])

    res = _run_journalctl(cmd, timeout=12)
    entries = []
    priority_names = {
        0: 'emerg', 1: 'alert', 2: 'crit', 3: 'err',
        4: 'warning', 5: 'notice', 6: 'info', 7: 'debug'
    }

    if res.returncode == 0 and res.stdout:
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                ts_raw = item.get('__REALTIME_TIMESTAMP')
                ts_str = ''
                if ts_raw:
                    try:
                        epoch_sec = int(ts_raw) / 1_000_000
                        ts_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(epoch_sec))
                    except Exception:
                        ts_str = str(ts_raw)

                p_val = int(item.get('PRIORITY', 6))
                p_label = priority_names.get(p_val, 'info')

                msg = item.get('MESSAGE', '')
                if isinstance(msg, list):
                    msg = ''.join(chr(b) if 32 <= b <= 126 else '?' for b in msg)

                entries.append({
                    'timestamp': ts_str,
                    'priority': p_val,
                    'priority_label': p_label,
                    'unit': item.get('_SYSTEMD_UNIT', ''),
                    'ident': item.get('SYSLOG_IDENTIFIER') or item.get('_COMM', ''),
                    'pid': item.get('_PID', ''),
                    'message': str(msg)
                })
            except Exception:
                continue

    return jsonify({
        'success': True,
        'entries': entries,
        'count': len(entries),
        'filter': {
            'unit': unit,
            'priority': priority,
            'since': since,
            'limit': limit_num
        }
    })

@app.route('/api/logs/auth')
@login_required
def api_logs_auth():
    """Audit keamanan SSH, upaya login brute force, session PAM, dan eksekusi sudo"""
    since = request.args.get('since', '24h').strip()
    limit = request.args.get('limit', '150').strip()
    status_filter = request.args.get('status', 'all').strip().lower()

    try:
        limit_num = max(10, min(500, int(limit)))
    except ValueError:
        limit_num = 150

    since_map = {
        '1h': '1 hour ago',
        '6h': '6 hours ago',
        '24h': '24 hours ago',
        '7d': '7 days ago',
        'all': None
    }
    since_arg = since_map.get(since, '24 hours ago')

    ssh_cmd = ['-u', 'ssh', '-u', 'sshd', '-n', str(limit_num), '-r', '--no-pager']
    if since_arg:
        ssh_cmd.extend(['--since', since_arg])
    ssh_res = _run_journalctl(ssh_cmd, timeout=10)

    sudo_cmd = ['--grep=COMMAND=', '-n', '50', '-r', '--no-pager']
    if since_arg:
        sudo_cmd.extend(['--since', since_arg])
    sudo_res = _run_journalctl(sudo_cmd, timeout=10)

    events = []
    attackers = {}
    stats = {'failed': 0, 'accepted': 0, 'sudo': 0}

    re_fail = re.compile(r'Failed password for (?:invalid user )?([^\s]+) from ([0-9a-fA-F.:]+) port (\d+)')
    re_invalid = re.compile(r'Invalid user ([^\s]+) from ([0-9a-fA-F.:]+) port (\d+)')
    re_acc = re.compile(r'Accepted (publickey|password) for ([^\s]+) from ([0-9a-fA-F.:]+) port (\d+)')
    re_sudo = re.compile(r'(\w+)\s*:\s*(?:TTY=[^;]*;\s*)?PWD=([^;]*);\s*USER=([^;]*);\s*COMMAND=(.*)')

    ssh_lines = []
    if ssh_res.returncode == 0 and ssh_res.stdout:
        ssh_lines = ssh_res.stdout.splitlines()
    else:
        # Fallback lintas distro (non-systemd / Alpine / RHEL /var/log/secure / Debian /var/log/auth.log)
        ssh_lines = list(reversed(_read_auth_log_lines(max_lines=limit_num * 3)))

    if ssh_lines:
        for line in ssh_lines:
            line = line.strip()
            if not line:
                continue

            m_acc = re_acc.search(line)
            if m_acc:
                stats['accepted'] += 1
                if status_filter in ('all', 'accepted'):
                    ts = ' '.join(line.split()[:3])
                    events.append({
                        'timestamp': ts,
                        'type': 'accepted',
                        'method': m_acc.group(1),
                        'user': m_acc.group(2),
                        'ip': m_acc.group(3),
                        'port': m_acc.group(4),
                        'raw': line
                    })
                continue

            m_fail = re_fail.search(line) or re_invalid.search(line)
            if m_fail:
                stats['failed'] += 1
                user = m_fail.group(1)
                ip = m_fail.group(2)
                port = m_fail.group(3)

                if ip not in attackers:
                    attackers[ip] = {'ip': ip, 'count': 0, 'users': set(), 'last_seen': ''}
                attackers[ip]['count'] += 1
                attackers[ip]['users'].add(user)

                ts = ' '.join(line.split()[:3])
                if not attackers[ip]['last_seen']:
                    attackers[ip]['last_seen'] = ts

                if status_filter in ('all', 'failed'):
                    events.append({
                        'timestamp': ts,
                        'type': 'failed',
                        'method': 'password',
                        'user': user,
                        'ip': ip,
                        'port': port,
                        'raw': line
                    })

    if sudo_res.returncode == 0 and sudo_res.stdout:
        for line in sudo_res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            m_sudo = re_sudo.search(line)
            if m_sudo:
                stats['sudo'] += 1
                if status_filter in ('all', 'sudo'):
                    ts = ' '.join(line.split()[:3])
                    events.append({
                        'timestamp': ts,
                        'type': 'sudo',
                        'user': m_sudo.group(1),
                        'target_user': m_sudo.group(3).strip(),
                        'pwd': m_sudo.group(2).strip(),
                        'command': m_sudo.group(4).strip(),
                        'ip': '127.0.0.1 (local)',
                        'port': '-',
                        'raw': line
                    })

    top_attackers = []
    for ip, data in attackers.items():
        top_attackers.append({
            'ip': ip,
            'count': data['count'],
            'users': list(data['users'])[:5],
            'last_seen': data['last_seen']
        })
    top_attackers.sort(key=lambda x: x['count'], reverse=True)
    stats['attackers_count'] = len(top_attackers)

    return jsonify({
        'success': True,
        'stats': stats,
        'events': events[:limit_num],
        'top_attackers': top_attackers[:10]
    })

@app.route('/api/logs/dmesg')
@login_required
def api_logs_dmesg():
    """Kernel ring buffer inspector: hardware errors, OOM-Killer, storage I/O alerts"""
    level = request.args.get('level', 'all').strip().lower()
    limit = request.args.get('limit', '150').strip()
    q = request.args.get('q', '').strip().lower()

    try:
        limit_num = max(10, min(500, int(limit)))
    except ValueError:
        limit_num = 150

    cmd = ['-T']
    level_map = {
        'err': '--level=emerg,alert,crit,err',
        'warn': '--level=emerg,alert,crit,err,warn',
        'info': '--level=emerg,alert,crit,err,warn,notice,info'
    }
    if level in level_map:
        cmd.append(level_map[level])

    res = _run_dmesg(cmd, timeout=8)
    entries = []
    oom_events = []
    disk_errors = []

    if res.returncode == 0 and res.stdout:
        lines = res.stdout.splitlines()
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue

            low = line.lower()
            is_oom = ('oom-killer' in low or 'out of memory' in low or 'killed process' in low)
            is_disk = ('i/o error' in low or 'ext4-fs error' in low or 'btrfs error' in low or 'blk_update_request' in low or ('ata' in low and 'error' in low))

            tag = 'info'
            if 'error' in low or 'fail' in low or 'crit' in low:
                tag = 'err'
            elif 'warn' in low or 'block' in low:
                tag = 'warn'
            elif is_oom or is_disk:
                tag = 'crit'

            ts = ''
            msg = line
            if line.startswith('[') and ']' in line:
                parts = line.split(']', 1)
                ts = parts[0][1:]
                msg = parts[1].strip()

            entry = {
                'timestamp': ts,
                'tag': tag,
                'message': msg,
                'is_oom': is_oom,
                'is_disk': is_disk
            }

            if is_oom:
                oom_events.append(entry)
            if is_disk:
                disk_errors.append(entry)

            if q:
                if q not in low and q not in ts.lower():
                    continue

            entries.append(entry)
            if len(entries) >= limit_num:
                break

    return jsonify({
        'success': True,
        'entries': entries,
        'oom_events': oom_events[:10],
        'disk_errors': disk_errors[:10],
        'total': len(entries),
        'filter': {'level': level, 'limit': limit_num}
    })

@app.route('/api/logs/units')
@login_required
def api_logs_units():
    """Daftar unit systemd aktif yang sering diperiksa log-nya untuk kemudahan filter"""
    res = _run_systemctl(['list-units', '--type=service', '--state=running', '--output=json'])
    units = []
    if res.returncode == 0 and res.stdout:
        try:
            data = json.loads(res.stdout)
            for item in data:
                u = item.get('unit', '')
                if u.endswith('.service'):
                    units.append({
                        'unit': u,
                        'name': u[:-8],
                        'description': item.get('description', '')
                    })
        except Exception:
            pass

    units.sort(key=lambda x: x['name'])
    return jsonify({'units': units, 'count': len(units)})


# ============================================================
# CENTRAL FIREWALL MANAGER (UNIVERSAL: UFW / firewalld / nftables / iptables)
# ============================================================

_DETECTED_FIREWALL_BACKEND = None


def _run_ufw(args, timeout=12):
    """Jalankan ufw pada host via eksekutor universal (nsenter / native)."""
    return _run_host_cmd(['ufw'] + list(args), timeout=timeout)


def _run_firewalld(args, timeout=12):
    """Jalankan firewall-cmd pada host via eksekutor universal (nsenter / native)."""
    return _run_host_cmd(['firewall-cmd'] + list(args), timeout=timeout)


def _detect_firewall_backend(force_refresh=False):
    """Auto-deteksi backend firewall host: ufw -> firewalld -> nftables -> iptables -> none."""
    global _DETECTED_FIREWALL_BACKEND
    if _DETECTED_FIREWALL_BACKEND and not force_refresh:
        return _DETECTED_FIREWALL_BACKEND

    for binary, name in (
        ('ufw', 'ufw'),
        ('firewall-cmd', 'firewalld'),
        ('nft', 'nftables'),
        ('iptables', 'iptables'),
    ):
        chk = _run_host_cmd(['which', binary], timeout=3, include_pid=False)
        if chk.returncode == 0 and chk.stdout.strip():
            _DETECTED_FIREWALL_BACKEND = name
            return name

    _DETECTED_FIREWALL_BACKEND = 'none'
    return 'none'


def _parse_firewalld_status(state_out, list_all_out):
    """Parser murni status & daftar rule firewalld (`firewall-cmd --state` + `--list-all`)."""
    active = (state_out or '').strip().lower() == 'running'
    defaults = {'incoming': 'deny', 'outgoing': 'allow', 'routed': 'allow'}
    rules = []
    num = 0
    for line in (list_all_out or '').splitlines():
        s = line.strip()
        if s.startswith('target:'):
            tgt = s.split(':', 1)[1].strip().upper()
            defaults['incoming'] = 'allow' if tgt == 'ACCEPT' else ('reject' if 'REJECT' in tgt else 'deny')
        elif s.startswith('services:'):
            for svc in s.split(':', 1)[1].strip().split():
                if svc:
                    num += 1
                    rules.append({'num': num, 'to': f'service:{svc}', 'action': 'ALLOW IN', 'from': 'Anywhere', 'is_v6': False, 'raw': f'service:{svc}'})
        elif s.startswith('ports:'):
            for prt in s.split(':', 1)[1].strip().split():
                if prt:
                    num += 1
                    rules.append({'num': num, 'to': prt, 'action': 'ALLOW IN', 'from': 'Anywhere', 'is_v6': False, 'raw': f'port:{prt}'})
        elif s.startswith('rule '):
            num += 1
            act = 'DENY IN' if ('drop' in s or 'reject' in s) else 'ALLOW IN'
            m_src = re.search(r'source address="([^"]+)"', s)
            m_prt = re.search(r'port port="([^"]+)" protocol="([^"]+)"', s)
            to_lbl = f"{m_prt.group(1)}/{m_prt.group(2)}" if m_prt else s
            from_lbl = m_src.group(1) if m_src else 'Anywhere'
            rules.append({'num': num, 'to': to_lbl, 'action': act, 'from': from_lbl, 'is_v6': 'ipv6' in s, 'raw': f'rich:{s}'})

    allow_count = sum(1 for r in rules if 'ALLOW' in r['action'])
    deny_count = sum(1 for r in rules if 'DENY' in r['action'] or 'REJECT' in r['action'])
    v6_count = sum(1 for r in rules if r['is_v6'])
    return {
        'active': active,
        'logging': 'firewalld',
        'defaults': defaults,
        'rules': rules,
        'stats': {
            'total_rules': len(rules),
            'allow_count': allow_count,
            'deny_count': deny_count,
            'limit_count': 0,
            'v4_count': len(rules) - v6_count,
            'v6_count': v6_count
        }
    }


def _parse_iptables_input_rules(iptables_out):
    """Parser murni output `iptables -L INPUT -n --line-numbers` ke skema unified firewall."""
    defaults = {'incoming': 'allow', 'outgoing': 'allow', 'routed': 'allow'}
    rules = []
    for line in (iptables_out or '').splitlines():
        s = line.strip()
        if s.startswith('Chain INPUT'):
            m_pol = re.search(r'\(policy\s+(\w+)\)', s)
            if m_pol:
                defaults['incoming'] = 'deny' if m_pol.group(1).upper() in ('DROP', 'REJECT') else 'allow'
            continue
        m = re.match(r'^(\d+)\s+(\S+)\s+(\S+)\s+\S+\s+(\S+)\s+(\S+)\s*(.*)$', s)
        if m:
            num = int(m.group(1))
            target = m.group(2).upper()
            proto = m.group(3).lower()
            src = m.group(4)
            extra = m.group(6) or ''
            m_dpt = re.search(r'dpt:(\S+)', extra)
            to_lbl = f"{m_dpt.group(1)}/{proto}" if m_dpt else (proto if proto != 'all' else 'Any')
            action = 'ALLOW IN' if target == 'ACCEPT' else ('DENY IN' if target == 'DROP' else ('REJECT IN' if target == 'REJECT' else target))
            rules.append({
                'num': num,
                'to': to_lbl,
                'action': action,
                'from': 'Anywhere' if src == '0.0.0.0/0' else src,
                'is_v6': False
            })

    allow_count = sum(1 for r in rules if 'ALLOW' in r['action'])
    deny_count = sum(1 for r in rules if 'DENY' in r['action'] or 'REJECT' in r['action'])
    active = (defaults['incoming'] != 'allow') or (len(rules) > 0)
    return {
        'active': active,
        'logging': 'kernel',
        'defaults': defaults,
        'rules': rules,
        'stats': {
            'total_rules': len(rules),
            'allow_count': allow_count,
            'deny_count': deny_count,
            'limit_count': 0,
            'v4_count': len(rules),
            'v6_count': 0
        }
    }


def _get_firewall_telemetry_summary():
    """Ringkasan status firewall host lintas backend untuk Wallboard NOC."""
    backend = _detect_firewall_backend()
    summary = {'active': False, 'status_text': 'INACTIVE', 'rules_count': 0, 'blocked_count': 0, 'backend': backend}
    try:
        if backend == 'ufw':
            v_res = _run_ufw(['status', 'verbose'], timeout=4)
            if v_res.returncode == 0 and v_res.stdout:
                summary['active'] = 'status: active' in v_res.stdout.lower()
                summary['status_text'] = 'ACTIVE' if summary['active'] else 'INACTIVE'
                n_res = _run_ufw(['status', 'numbered'], timeout=4)
                if n_res.returncode == 0 and n_res.stdout:
                    summary['rules_count'] = sum(1 for l in n_res.stdout.splitlines() if re.match(r'^\s*\[\s*\d+\]', l))
        elif backend == 'firewalld':
            st = _run_firewalld(['--state'], timeout=4)
            la = _run_firewalld(['--list-all'], timeout=4)
            parsed = _parse_firewalld_status(st.stdout, la.stdout)
            summary['active'] = parsed['active']
            summary['status_text'] = 'ACTIVE' if parsed['active'] else 'INACTIVE'
            summary['rules_count'] = parsed['stats']['total_rules']
        elif backend in ('iptables', 'nftables'):
            res_ipt = _run_iptables(['-L', 'INPUT', '-n', '--line-numbers'], timeout=4)
            parsed = _parse_iptables_input_rules(res_ipt.stdout)
            summary['active'] = parsed['active']
            summary['status_text'] = 'ACTIVE' if parsed['active'] else 'INACTIVE'
            summary['rules_count'] = parsed['stats']['total_rules']
    except Exception:
        pass
    return summary


@app.route('/firewall')
@login_required
def firewall_page():
    """Halaman Manajemen Central Firewall (UFW / Firewalld / Nftables / Iptables)"""
    return render_template('firewall.html')

@app.route('/api/firewall/status')
@login_required
def api_firewall_status():
    """Status lengkap firewall host lintas backend (ufw / firewalld / iptables / nftables)"""
    backend = _detect_firewall_backend()

    if backend == 'firewalld':
        st_res = _run_firewalld(['--state'])
        la_res = _run_firewalld(['--list-all'])
        parsed = _parse_firewalld_status(st_res.stdout, la_res.stdout)
        return jsonify({
            'success': True,
            'backend': backend,
            **parsed
        })

    if backend in ('iptables', 'nftables'):
        ipt_res = _run_iptables(['-L', 'INPUT', '-n', '--line-numbers'])
        parsed = _parse_iptables_input_rules(ipt_res.stdout)
        return jsonify({
            'success': True,
            'backend': backend,
            **parsed
        })

    v_res = _run_ufw(['status', 'verbose'])
    n_res = _run_ufw(['status', 'numbered'])

    status_active = False
    logging = 'off'
    defaults = {'incoming': 'deny', 'outgoing': 'allow', 'routed': 'allow'}

    if v_res.returncode == 0 and v_res.stdout:
        for line in v_res.stdout.splitlines():
            line_str = line.strip()
            if line_str.startswith('Status:'):
                status_active = 'active' in line_str.lower()
            elif line_str.startswith('Logging:'):
                logging = line_str.split(':', 1)[1].strip()
            elif line_str.startswith('Default:'):
                parts = line_str.split(':', 1)[1].strip().split(',')
                for p in parts:
                    p = p.strip()
                    if '(incoming)' in p:
                        defaults['incoming'] = p.replace('(incoming)', '').strip()
                    elif '(outgoing)' in p:
                        defaults['outgoing'] = p.replace('(outgoing)', '').strip()
                    elif '(routed)' in p:
                        defaults['routed'] = p.replace('(routed)', '').strip()

    rules = []
    allow_count = 0
    deny_count = 0
    limit_count = 0
    v4_count = 0
    v6_count = 0

    if n_res.returncode == 0 and n_res.stdout:
        for line in n_res.stdout.splitlines():
            m = re.match(r'^\s*\[\s*(\d+)\]\s+(.*?)\s+(ALLOW IN|DENY IN|LIMIT IN|ALLOW FWD|DENY FWD|REJECT IN|ALLOW OUT|DENY OUT)\s+(.*)$', line)
            if m:
                num = int(m.group(1))
                to_target = m.group(2).strip()
                action = m.group(3).strip()
                from_target = m.group(4).strip()
                is_v6 = ('(v6)' in to_target or '(v6)' in from_target)

                if is_v6:
                    v6_count += 1
                else:
                    v4_count += 1

                if 'ALLOW' in action:
                    allow_count += 1
                elif 'DENY' in action or 'REJECT' in action:
                    deny_count += 1
                elif 'LIMIT' in action:
                    limit_count += 1

                rules.append({
                    'num': num,
                    'to': to_target,
                    'action': action,
                    'from': from_target,
                    'is_v6': is_v6
                })

    stats = {
        'total_rules': len(rules),
        'allow_count': allow_count,
        'deny_count': deny_count,
        'limit_count': limit_count,
        'v4_count': v4_count,
        'v6_count': v6_count
    }

    return jsonify({
        'success': True,
        'backend': backend,
        'active': status_active,
        'logging': logging,
        'defaults': defaults,
        'stats': stats,
        'rules': rules
    })

@app.route('/api/firewall/rule/add', methods=['POST'])
@login_required
def api_firewall_rule_add():
    """Menambahkan aturan firewall baru secara aman lintas backend (ufw / firewalld / iptables)"""
    data = request.json or {}
    action = (data.get('action') or 'allow').strip().lower()
    port = str(data.get('port') or '').strip()
    proto = (data.get('proto') or '').strip().lower()
    from_ip = (data.get('from_ip') or '').strip()
    direction = (data.get('direction') or 'in').strip().lower()
    interface = (data.get('interface') or '').strip()

    valid_actions = ('allow', 'deny', 'reject', 'limit')
    if action not in valid_actions:
        return jsonify({'success': False, 'error': f'Aksi tidak valid: {action}'}), 400

    if direction not in ('in', 'out'):
        direction = 'in'

    if interface and not re.match(r'^[a-zA-Z0-9_.-]+$', interface):
        return jsonify({'success': False, 'error': 'Format interface tidak valid'}), 400

    if port:
        if not re.match(r'^[a-zA-Z0-9_:-]+$', port):
            return jsonify({'success': False, 'error': 'Format port tidak valid'}), 400

    if proto and proto not in ('tcp', 'udp', 'any'):
        return jsonify({'success': False, 'error': 'Protokol tidak valid (tcp, udp, any)'}), 400

    if from_ip and from_ip.lower() != 'any':
        import ipaddress
        try:
            if '/' in from_ip:
                ipaddress.ip_network(from_ip, strict=False)
            else:
                ipaddress.ip_address(from_ip)
        except ValueError:
            return jsonify({'success': False, 'error': 'Format IP / CIDR source tidak valid'}), 400

    backend = _detect_firewall_backend()

    if backend == 'firewalld':
        eff_proto = proto if (proto and proto != 'any') else 'tcp'
        fd_port = port.replace(':', '-')
        if (not from_ip or from_ip.lower() == 'any') and action == 'allow' and fd_port:
            res = _run_firewalld(['--permanent', f'--add-port={fd_port}/{eff_proto}'], timeout=15)
        else:
            fd_act = 'accept' if action in ('allow', 'limit') else ('reject' if action == 'reject' else 'drop')
            fam = 'ipv6' if ':' in from_ip else 'ipv4'
            rule_parts = [f'rule family="{fam}"']
            if from_ip and from_ip.lower() != 'any':
                rule_parts.append(f'source address="{from_ip}"')
            if fd_port:
                rule_parts.append(f'port port="{fd_port}" protocol="{eff_proto}"')
            rule_parts.append(fd_act)
            res = _run_firewalld(['--permanent', f'--add-rich-rule={" ".join(rule_parts)}'], timeout=15)
        if res.returncode == 0:
            _run_firewalld(['--reload'], timeout=15)
        success = (res.returncode == 0)
        output = (res.stdout or '') + (res.stderr or '')
        audit_log('FIREWALL_RULE_ADD', f"firewalld {action} {port}/{eff_proto} from={from_ip or 'any'} - success={success}", session.get('username'))
        return jsonify({
            'success': success,
            'backend': backend,
            'message': 'Aturan firewalld berhasil ditambahkan' if success else f'Gagal: {output}',
            'output': output
        }), 200 if success else 400

    if backend in ('iptables', 'nftables'):
        chain = 'INPUT' if direction == 'in' else 'OUTPUT'
        tgt = 'ACCEPT' if action in ('allow', 'limit') else ('REJECT' if action == 'reject' else 'DROP')
        ipt_args = ['-A', chain]
        if interface:
            ipt_args += ['-i' if direction == 'in' else '-o', interface]
        if from_ip and from_ip.lower() != 'any':
            ipt_args += ['-s', from_ip]
        if port:
            eff_proto = proto if (proto and proto != 'any') else 'tcp'
            ipt_args += ['-p', eff_proto, '--dport', port]
        elif proto and proto != 'any':
            ipt_args += ['-p', proto]
        ipt_args += ['-j', tgt]
        res = _run_iptables(ipt_args, timeout=15)
        success = (res.returncode == 0)
        output = (res.stdout or '') + (res.stderr or '')
        audit_log('FIREWALL_RULE_ADD', f"iptables {' '.join(ipt_args)} - success={success}", session.get('username'))
        return jsonify({
            'success': success,
            'backend': backend,
            'message': f'Aturan berhasil ditambahkan: iptables {" ".join(ipt_args)}' if success else f'Gagal: {output}',
            'output': output
        }), 200 if success else 400

    args = []
    if not from_ip or from_ip.lower() == 'any':
        if not port:
            return jsonify({'success': False, 'error': 'Port atau IP source wajib ditentukan'}), 400

        target_port = port
        if proto and proto != 'any':
            target_port = f"{port}/{proto}"

        if interface:
            args = [action, direction, 'on', interface, 'to', 'any', 'port', port]
            if proto and proto != 'any':
                args.extend(['proto', proto])
        else:
            args = [action, target_port]
    else:
        args = [action]
        if direction == 'in':
            args.append('in')
        elif direction == 'out':
            args.append('out')

        if interface:
            args.extend(['on', interface])

        args.extend(['from', from_ip])

        if port:
            args.extend(['to', 'any', 'port', port])
            if proto and proto != 'any':
                args.extend(['proto', proto])

    res = _run_ufw(args, timeout=15)
    success = (res.returncode == 0)
    output = (res.stdout or '') + (res.stderr or '')

    audit_log('FIREWALL_RULE_ADD', f"UFW {' '.join(args)} - success={success}", session.get('username'))

    return jsonify({
        'success': success,
        'backend': backend,
        'message': f'Aturan berhasil ditambahkan: ufw {" ".join(args)}' if success else f'Gagal: {output}',
        'output': output
    }), 200 if success else 400

@app.route('/api/firewall/rule/delete', methods=['POST'])
@login_required
def api_firewall_rule_delete():
    """Menghapus aturan firewall berdasarkan nomor urut lintas backend"""
    data = request.json or {}
    try:
        num = int(data.get('num'))
        if num <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Nomor rule tidak valid'}), 400

    backend = _detect_firewall_backend()
    if backend == 'firewalld':
        st_res = _run_firewalld(['--state'])
        la_res = _run_firewalld(['--list-all'])
        parsed = _parse_firewalld_status(st_res.stdout, la_res.stdout)
        target_rule = next((r for r in parsed['rules'] if r['num'] == num), None)
        if not target_rule:
            return jsonify({'success': False, 'error': f'Rule #{num} tidak ditemukan di firewalld'}), 404
        raw = target_rule.get('raw', '')
        if raw.startswith('port:'):
            res = _run_firewalld(['--permanent', f'--remove-port={raw[5:]}'], timeout=15)
        elif raw.startswith('service:'):
            res = _run_firewalld(['--permanent', f'--remove-service={raw[8:]}'], timeout=15)
        elif raw.startswith('rich:'):
            res = _run_firewalld(['--permanent', f'--remove-rich-rule={raw[5:]}'], timeout=15)
        else:
            return jsonify({'success': False, 'error': 'Tipe rule firewalld tidak didukung'}), 400
        if res.returncode == 0:
            _run_firewalld(['--reload'], timeout=15)
    elif backend in ('iptables', 'nftables'):
        res = _run_iptables(['-D', 'INPUT', str(num)], timeout=15)
    else:
        res = _run_ufw(['--force', 'delete', str(num)], timeout=15)

    success = (res.returncode == 0)
    output = (res.stdout or '') + (res.stderr or '')

    audit_log('FIREWALL_RULE_DELETE', f"{backend} delete rule #{num} - success={success}", session.get('username'))

    return jsonify({
        'success': success,
        'backend': backend,
        'message': f'Rule #{num} berhasil dihapus' if success else f'Gagal menghapus rule #{num}: {output}',
        'output': output
    }), 200 if success else 400

@app.route('/api/firewall/default', methods=['POST'])
@login_required
def api_firewall_set_default():
    """Mengubah kebijakan default traffic (incoming, outgoing, routed) lintas backend"""
    data = request.json or {}
    direction = (data.get('direction') or 'incoming').strip().lower()
    policy = (data.get('policy') or 'deny').strip().lower()

    if direction not in ('incoming', 'outgoing', 'routed'):
        return jsonify({'success': False, 'error': 'Direction tidak valid'}), 400
    if policy not in ('allow', 'deny', 'reject'):
        return jsonify({'success': False, 'error': 'Kebijakan tidak valid (allow, deny, reject)'}), 400

    backend = _detect_firewall_backend()
    if backend == 'firewalld':
        tgt = 'ACCEPT' if policy == 'allow' else ('%%REJECT%%' if policy == 'reject' else 'DROP')
        res = _run_firewalld(['--permanent', f'--set-target={tgt}'], timeout=15)
        if res.returncode == 0:
            _run_firewalld(['--reload'], timeout=15)
    elif backend in ('iptables', 'nftables'):
        chain = {'incoming': 'INPUT', 'outgoing': 'OUTPUT', 'routed': 'FORWARD'}[direction]
        ipt_pol = 'ACCEPT' if policy == 'allow' else 'DROP'
        res = _run_iptables(['-P', chain, ipt_pol], timeout=15)
    else:
        res = _run_ufw(['default', policy, direction], timeout=15)

    success = (res.returncode == 0)
    output = (res.stdout or '') + (res.stderr or '')

    audit_log('FIREWALL_DEFAULT_POLICY', f"{backend} default {policy} {direction}", session.get('username'))

    return jsonify({
        'success': success,
        'backend': backend,
        'message': f'Kebijakan default {direction} diubah menjadi {policy}' if success else f'Gagal: {output}',
        'output': output
    }), 200 if success else 400

@app.route('/api/firewall/toggle', methods=['POST'])
@login_required
def api_firewall_toggle():
    """Mengaktifkan atau menonaktifkan firewall host lintas backend"""
    data = request.json or {}
    action = (data.get('action') or '').strip().lower()

    if action not in ('enable', 'disable'):
        return jsonify({'success': False, 'error': 'Aksi tidak valid (enable/disable)'}), 400

    backend = _detect_firewall_backend()
    if backend == 'firewalld':
        svc_act = 'start' if action == 'enable' else 'stop'
        res = _run_systemctl([svc_act, 'firewalld'], timeout=15)
    elif backend in ('iptables', 'nftables'):
        return jsonify({
            'success': False,
            'backend': backend,
            'error': f'Backend {backend} berjalan di level kernel; kelola proteksi melalui aturan atau default policy.'
        }), 400
    else:
        args = ['--force', 'enable'] if action == 'enable' else ['disable']
        res = _run_ufw(args, timeout=15)

    success = (res.returncode == 0)
    output = (res.stdout or '') + (res.stderr or '')

    audit_log('FIREWALL_TOGGLE', f"{backend} {action}", session.get('username'))

    return jsonify({
        'success': success,
        'backend': backend,
        'message': f'Firewall ({backend}) berhasil di-{action}' if success else f'Gagal {action} firewall: {output}',
        'output': output
    }), 200 if success else 500

@app.route('/api/firewall/reload', methods=['POST'])
@login_required
def api_firewall_reload():
    """Memuat ulang aturan firewall host lintas backend"""
    backend = _detect_firewall_backend()
    if backend == 'firewalld':
        res = _run_firewalld(['--reload'], timeout=15)
    elif backend in ('iptables', 'nftables'):
        res = _run_iptables(['-L', '-n'], timeout=10)
    else:
        res = _run_ufw(['reload'], timeout=15)

    success = (res.returncode == 0)
    output = (res.stdout or '') + (res.stderr or '')

    audit_log('FIREWALL_RELOAD', f"{backend} reload", session.get('username'))

    return jsonify({
        'success': success,
        'backend': backend,
        'message': f'Firewall ({backend}) berhasil dimuat ulang' if success else f'Gagal reload firewall: {output}',
        'output': output
    }), 200 if success else 500

@app.route('/api/firewall/iptables')
@login_required
def api_firewall_iptables():
    """Membaca daftar aturan filter iptables dan nftables untuk inspeksi tingkat lanjut"""
    res_v4 = _run_iptables(['-L', '-n', '-v', '--line-numbers'])
    v4_rules = res_v4.stdout if res_v4.returncode == 0 else ''

    n_res = _run_host_cmd(['nft', 'list', 'ruleset'], timeout=8)
    nft_rules = n_res.stdout if (n_res.returncode == 0 and n_res.stdout) else ''

    return jsonify({
        'success': True,
        'backend': _detect_firewall_backend(),
        'iptables_v4': v4_rules,
        'nftables': nft_rules
    })


# ============================================================
# TASK SCHEDULER & CRON JOBS (crontab & systemd.timer)
# ============================================================

def _run_scheduler_cmd(args, timeout=15, input_data=None):
    """Jalankan perintah host via eksekutor universal (nsenter / native) dengan input data opsional."""
    return _run_host_cmd(list(args), timeout=timeout, input_data=input_data)

def _get_system_cron_users():
    """Deteksi pengguna di host secara dinamis yang memiliki atau dapat memiliki crontab"""
    users = {'root'}
    res = _run_scheduler_cmd(['ls', '-1', '/var/spool/cron/crontabs'])
    if res.returncode == 0 and res.stdout:
        for u in res.stdout.strip().splitlines():
            u = u.strip()
            if u and not u.startswith('.'):
                users.add(u)
    res_pw = _run_scheduler_cmd(['cat', '/etc/passwd'])
    if res_pw.returncode == 0 and res_pw.stdout:
        for line in res_pw.stdout.splitlines():
            parts = line.split(':')
            if len(parts) >= 7:
                uname = parts[0].strip()
                try:
                    uid = int(parts[2])
                    shell = parts[6].strip()
                    if (uid == 0 or uid >= 1000) and not shell.endswith('nologin') and not shell.endswith('false'):
                        users.add(uname)
                except ValueError:
                    pass
    return sorted(list(users))

def _humanize_cron_schedule(schedule):
    """Menerjemahkan ekspresi cron ke penjelasan bahasa manusia yang ramah"""
    s = schedule.strip()
    if s == '@reboot':
        return 'Saat booting / startup sistem'
    if s in ('@daily', '@midnight', '0 0 * * *'):
        return 'Setiap hari pada pukul 00:00'
    if s in ('@hourly', '0 * * * *'):
        return 'Setiap jam (menit 00)'
    if s == '* * * * *':
        return 'Setiap menit'
    if s == '*/5 * * * *':
        return 'Setiap 5 menit'
    if s == '*/10 * * * *':
        return 'Setiap 10 menit'
    if s == '*/15 * * * *':
        return 'Setiap 15 menit'
    if s == '*/30 * * * *':
        return 'Setiap 30 menit'

    parts = s.split()
    if len(parts) == 5:
        m, h, dom, mon, dow = parts
        time_str = ''
        if m.isdigit() and h.isdigit():
            time_str = f"pada {h.zfill(2)}:{m.zfill(2)}"
        elif m.isdigit() and h == '*':
            time_str = f"pada menit ke-{m} setiap jam"
        elif m.startswith('*/'):
            time_str = f"setiap {m[2:]} menit"

        days_str = ''
        if dom == '*' and dow == '*':
            days_str = 'Setiap hari'
        elif dow != '*':
            dow_map = {'0': 'Minggu', '1': 'Senin', '2': 'Selasa', '3': 'Rabu', '4': 'Kamis', '5': 'Jumat', '6': 'Sabtu', '7': 'Minggu'}
            day_name = dow_map.get(dow, f"hari ke-{dow}")
            days_str = f"Setiap {day_name}"
        elif dom != '*':
            days_str = f"Tanggal {dom} setiap bulan"

        if time_str and days_str:
            return f"{days_str} {time_str}"
        elif time_str:
            return time_str
        elif days_str:
            return days_str

    return s

def _parse_crontab_lines(content, default_user='root', source='user'):
    """Parsing baris-baris crontab ke list of dict"""
    jobs = []
    lines = content.splitlines()
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        is_disabled = False
        active_line = line
        if line.startswith('# DISABLED:') or line.startswith('# DISABLED_BY_EKADASH:'):
            is_disabled = True
            active_line = line.split(':', 1)[1].strip()
        elif line.startswith('#'):
            # Komentar biasa, lewati
            continue

        schedule = ''
        command = ''
        job_user = default_user

        if active_line.startswith('@'):
            parts = active_line.split(None, 1)
            schedule = parts[0]
            command = parts[1] if len(parts) > 1 else ''
        else:
            parts = active_line.split(None, 5)
            if len(parts) >= 6:
                schedule = ' '.join(parts[:5])
                command = parts[5]
            elif len(parts) == 5:
                schedule = ' '.join(parts)
                command = ''
            else:
                continue

        # Untuk /etc/crontab atau /etc/cron.d, format baris: min hr dom mon dow username command
        if source == 'system':
            c_parts = command.split(None, 1)
            if len(c_parts) >= 2:
                job_user = c_parts[0]
                command = c_parts[1]

        jobs.append({
            'id': f"{default_user}_{idx}_{abs(hash(raw_line)) & 0xffffffff:x}",
            'user': job_user,
            'source': source,
            'schedule': schedule,
            'schedule_human': _humanize_cron_schedule(schedule),
            'command': command,
            'enabled': not is_disabled,
            'raw': raw_line,
            'line_index': idx
        })
    return jobs

def _get_all_cron_jobs():
    """Mengumpulkan seluruh cron jobs dari seluruh pengguna host dan direktori sistem"""
    all_jobs = []
    users = _get_system_cron_users()

    # 1. User Crontabs
    for u in users:
        res = _run_scheduler_cmd(['crontab', '-u', u, '-l'])
        if res.returncode == 0 and res.stdout:
            parsed = _parse_crontab_lines(res.stdout, default_user=u, source='user')
            all_jobs.extend(parsed)

    # 2. System /etc/crontab
    res_sys = _run_scheduler_cmd(['cat', '/etc/crontab'])
    if res_sys.returncode == 0 and res_sys.stdout:
        parsed_sys = _parse_crontab_lines(res_sys.stdout, default_user='system', source='system')
        all_jobs.extend(parsed_sys)

    # 3. System /etc/cron.d/*
    res_d = _run_scheduler_cmd(['ls', '-1', '/etc/cron.d'])
    if res_d.returncode == 0 and res_d.stdout:
        for fname in res_d.stdout.splitlines():
            fname = fname.strip()
            if not fname or fname.startswith('.'):
                continue
            res_f = _run_scheduler_cmd(['cat', f'/etc/cron.d/{fname}'])
            if res_f.returncode == 0 and res_f.stdout:
                parsed_f = _parse_crontab_lines(res_f.stdout, default_user=f'cron.d/{fname}', source='system')
                all_jobs.extend(parsed_f)

    return all_jobs, users

def _write_user_crontab(user, new_content):
    """Menulis berkas crontab pengguna secara aman"""
    if not new_content.strip():
        res = _run_scheduler_cmd(['crontab', '-u', user, '-r'])
        return res.returncode == 0 or 'no crontab' in res.stderr.lower()
    if not new_content.endswith('\n'):
        new_content += '\n'
    res = _run_scheduler_cmd(['crontab', '-u', user, '-'], input_data=new_content)
    return res.returncode == 0


@app.route('/scheduler')
@login_required
def scheduler_page():
    """Halaman Task Scheduler & Cron Jobs"""
    return render_template('scheduler.html')

@app.route('/api/cron/summary')
@login_required
def api_cron_summary():
    """Ringkasan statistik cron jobs dan systemd timers"""
    jobs, users = _get_all_cron_jobs()
    total_jobs = len(jobs)
    active_jobs = sum(1 for j in jobs if j['enabled'])
    disabled_jobs = total_jobs - active_jobs

    res_timers = _run_scheduler_cmd(['systemctl', 'list-timers', '--all', '--output=json'])
    timers_list = []
    if res_timers.returncode == 0 and res_timers.stdout:
        try:
            timers_list = json.loads(res_timers.stdout)
        except Exception:
            pass

    active_timers = 0
    next_timer_info = None
    min_left = float('inf')

    for t in timers_list:
        next_val = t.get('next')
        if next_val and next_val > 0:
            active_timers += 1
            left_val = t.get('left')
            if left_val is not None and left_val < min_left:
                min_left = left_val
                next_timer_info = {
                    'unit': t.get('unit'),
                    'activates': t.get('activates'),
                    'timestamp': int(next_val / 1e6)
                }

    return jsonify({
        'success': True,
        'total_cron_jobs': total_jobs,
        'active_cron_jobs': active_jobs,
        'disabled_cron_jobs': disabled_jobs,
        'total_timers': len(timers_list),
        'active_timers': active_timers,
        'next_timer': next_timer_info,
        'users': users
    })

@app.route('/api/cron/list')
@login_required
def api_cron_list():
    """Daftar cron jobs dengan filter user dan source"""
    filter_user = request.args.get('user', 'all').strip()
    filter_source = request.args.get('source', 'all').strip()

    jobs, users = _get_all_cron_jobs()

    if filter_user != 'all':
        jobs = [j for j in jobs if j['user'] == filter_user]
    if filter_source != 'all':
        jobs = [j for j in jobs if j['source'] == filter_source]

    return jsonify({
        'success': True,
        'jobs': jobs,
        'count': len(jobs),
        'users': users
    })

@app.route('/api/cron/save', methods=['POST'])
@login_required
def api_cron_save():
    """Menambah atau memperbarui jadwal cron pengguna"""
    data = request.json or {}
    user = (data.get('user') or 'root').strip()
    schedule = (data.get('schedule') or '').strip()
    command = (data.get('command') or '').strip()
    enabled = bool(data.get('enabled', True))
    original_raw = data.get('original_raw')

    if not re.match(r'^[a-zA-Z0-9_.-]+$', user):
        return jsonify({'success': False, 'error': 'Username tidak valid'}), 400

    if not command:
        return jsonify({'success': False, 'error': 'Perintah (command) tidak boleh kosong'}), 400

    command = ' '.join(command.splitlines()).strip()

    valid_special = ('@reboot', '@yearly', '@annually', '@monthly', '@weekly', '@daily', '@midnight', '@hourly')
    if schedule not in valid_special:
        parts = schedule.split()
        if len(parts) != 5:
            return jsonify({'success': False, 'error': 'Format schedule cron harus berupa @preset atau 5 kolom (min hour dom mon dow)'}), 400
        for p in parts:
            if not re.match(r'^[0-9a-zA-Z/*,-]+$', p):
                return jsonify({'success': False, 'error': f'Karakter tidak valid pada kolom schedule: {p}'}), 400

    new_line = f"{schedule} {command}"
    if not enabled:
        new_line = f"# DISABLED: {new_line}"

    res_l = _run_scheduler_cmd(['crontab', '-u', user, '-l'])
    existing_content = res_l.stdout if res_l.returncode == 0 else ''
    lines = [l for l in existing_content.splitlines() if l.strip()]

    updated = False
    if original_raw:
        new_lines = []
        for line in lines:
            if line.strip() == original_raw.strip() and not updated:
                new_lines.append(new_line)
                updated = True
            else:
                new_lines.append(line)
        lines = new_lines

    if not updated:
        lines.append(new_line)

    new_crontab = '\n'.join(lines) + '\n'
    ok = _write_user_crontab(user, new_crontab)
    if not ok:
        return jsonify({'success': False, 'error': 'Gagal menulis crontab pada sistem host'}), 500

    return jsonify({
        'success': True,
        'message': 'Jadwal cron berhasil disimpan'
    })

@app.route('/api/cron/toggle', methods=['POST'])
@login_required
def api_cron_toggle():
    """Mengaktifkan atau menonaktifkan baris cron job"""
    data = request.json or {}
    user = (data.get('user') or 'root').strip()
    raw = (data.get('raw') or '').strip()

    if not re.match(r'^[a-zA-Z0-9_.-]+$', user):
        return jsonify({'success': False, 'error': 'Username tidak valid'}), 400

    if not raw:
        return jsonify({'success': False, 'error': 'Parameter raw tidak boleh kosong'}), 400

    res_l = _run_scheduler_cmd(['crontab', '-u', user, '-l'])
    if res_l.returncode != 0:
        return jsonify({'success': False, 'error': 'Tidak dapat membaca crontab user'}), 400

    lines = res_l.stdout.splitlines()
    new_lines = []
    found = False
    new_state = True

    for line in lines:
        if line.strip() == raw and not found:
            found = True
            if line.strip().startswith('# DISABLED:') or line.strip().startswith('# DISABLED_BY_EKADASH:'):
                active = line.strip().split(':', 1)[1].strip()
                new_lines.append(active)
                new_state = True
            else:
                new_lines.append(f"# DISABLED: {line.strip()}")
                new_state = False
        else:
            new_lines.append(line)

    if not found:
        return jsonify({'success': False, 'error': 'Baris jadwal tidak ditemukan dalam crontab'}), 404

    new_crontab = '\n'.join(new_lines) + '\n'
    ok = _write_user_crontab(user, new_crontab)
    if not ok:
        return jsonify({'success': False, 'error': 'Gagal memperbarui crontab'}), 500

    return jsonify({
        'success': True,
        'enabled': new_state,
        'message': f"Jadwal cron berhasil {'diaktifkan' if new_state else 'dinonaktifkan'}"
    })

@app.route('/api/cron/delete', methods=['POST'])
@login_required
def api_cron_delete():
    """Menghapus entri cron job tertentu"""
    data = request.json or {}
    user = (data.get('user') or 'root').strip()
    raw = (data.get('raw') or '').strip()

    if not re.match(r'^[a-zA-Z0-9_.-]+$', user):
        return jsonify({'success': False, 'error': 'Username tidak valid'}), 400

    if not raw:
        return jsonify({'success': False, 'error': 'Parameter raw tidak boleh kosong'}), 400

    res_l = _run_scheduler_cmd(['crontab', '-u', user, '-l'])
    if res_l.returncode != 0:
        return jsonify({'success': False, 'error': 'Crontab user tidak ditemukan'}), 404

    lines = res_l.stdout.splitlines()
    new_lines = []
    found = False

    for line in lines:
        if line.strip() == raw and not found:
            found = True
            continue
        new_lines.append(line)

    if not found:
        return jsonify({'success': False, 'error': 'Baris jadwal tidak ditemukan'}), 404

    new_crontab = '\n'.join(new_lines) + '\n'
    ok = _write_user_crontab(user, new_crontab)
    if not ok:
        return jsonify({'success': False, 'error': 'Gagal memperbarui crontab setelah penghapusan'}), 500

    return jsonify({
        'success': True,
        'message': 'Jadwal cron berhasil dihapus'
    })

@app.route('/api/cron/timers')
@login_required
def api_cron_timers():
    """Daftar systemd timers aktif dan terjadwal"""
    search = (request.args.get('search') or '').strip().lower()

    res = _run_scheduler_cmd(['systemctl', 'list-timers', '--all', '--output=json'])
    raw_timers = []
    if res.returncode == 0 and res.stdout:
        try:
            raw_timers = json.loads(res.stdout)
        except Exception:
            pass

    formatted_timers = []
    now_ts = time.time()

    for item in raw_timers:
        unit = item.get('unit', '')
        activates = item.get('activates', '')

        if search and search not in unit.lower() and search not in activates.lower():
            continue

        next_us = item.get('next')
        last_us = item.get('last')

        next_dt_str = '-'
        next_countdown = '-'
        status = 'waiting'

        if next_us and next_us > 0:
            next_sec = next_us / 1e6
            try:
                next_dt = datetime.fromtimestamp(next_sec)
                next_dt_str = next_dt.strftime('%Y-%m-%d %H:%M:%S')
                diff = next_sec - now_ts
                if diff > 0:
                    mins = int(diff // 60)
                    hours = int(mins // 60)
                    days = int(hours // 24)
                    if days > 0:
                        next_countdown = f"dalam {days}h {hours % 24}j"
                    elif hours > 0:
                        next_countdown = f"dalam {hours}j {mins % 60}m"
                    elif mins > 0:
                        next_countdown = f"dalam {mins}m"
                    else:
                        next_countdown = f"dalam {int(diff)}s"
                else:
                    next_countdown = 'segera'
                status = 'active'
            except Exception:
                pass
        else:
            status = 'inactive'

        last_dt_str = '-'
        last_elapsed = '-'
        if last_us and last_us > 0:
            last_sec = last_us / 1e6
            try:
                last_dt = datetime.fromtimestamp(last_sec)
                last_dt_str = last_dt.strftime('%Y-%m-%d %H:%M:%S')
                diff = now_ts - last_sec
                if diff > 0:
                    mins = int(diff // 60)
                    hours = int(mins // 60)
                    days = int(hours // 24)
                    if days > 0:
                        last_elapsed = f"{days}h lalu"
                    elif hours > 0:
                        last_elapsed = f"{hours}j lalu"
                    elif mins > 0:
                        last_elapsed = f"{mins}m lalu"
                    else:
                        last_elapsed = f"{int(diff)}s lalu"
            except Exception:
                pass

        formatted_timers.append({
            'unit': unit,
            'activates': activates,
            'next_time': next_dt_str,
            'next_countdown': next_countdown,
            'last_time': last_dt_str,
            'last_elapsed': last_elapsed,
            'status': status
        })

    return jsonify({
        'success': True,
        'timers': formatted_timers,
        'count': len(formatted_timers)
    })

@app.route('/api/cron/test_run', methods=['POST'])
@login_required
def api_cron_test_run():
    """Uji coba eksekusi (dry-run) perintah atau skrip dengan log output real-time"""
    data = request.json or {}
    command = (data.get('command') or '').strip()
    user = (data.get('user') or 'root').strip()

    if not command:
        return jsonify({'success': False, 'error': 'Perintah (command) tidak boleh kosong'}), 400

    if not re.match(r'^[a-zA-Z0-9_.-]+$', user):
        return jsonify({'success': False, 'error': 'Username tidak valid'}), 400

    t0 = time.time()
    exec_cmd = ['su', '-', user, '-c', command]
    res = _run_scheduler_cmd(exec_cmd, timeout=15)
    duration_ms = int((time.time() - t0) * 1000)

    return jsonify({
        'success': True,
        'returncode': res.returncode,
        'stdout': res.stdout,
        'stderr': res.stderr,
        'duration_ms': duration_ms,
        'passed': res.returncode == 0
    })


# ============================================================
# DRIVE HEALTH & S.M.A.R.T. INSPECTOR (smartctl, RAID & ZFS)
# ============================================================

def _run_smartctl_cmd(args, timeout=15):
    """Jalankan smartctl pada host via eksekutor universal (nsenter / native)."""
    return _run_host_cmd(['smartctl'] + list(args), timeout=timeout)

def _discover_physical_drives():
    """Deteksi drive fisik yang terpasang pada host secara dinamis"""
    drives = []
    res = _run_smartctl_cmd(['--scan', '-j'])
    if res.stdout:
        try:
            data = json.loads(res.stdout)
            for d in data.get('devices', []):
                dev_name = d.get('name', '').strip()
                if dev_name and not dev_name.startswith('/dev/loop') and not dev_name.startswith('/dev/ram'):
                    drives.append({
                        'device': dev_name,
                        'name': os.path.basename(dev_name),
                        'type': d.get('type', 'scsi'),
                        'protocol': d.get('protocol', '')
                    })
        except Exception:
            pass

    if not drives:
        res_lsblk = _run_scheduler_cmd(['lsblk', '-d', '-J', '-o', 'NAME,TYPE,ROTA,MODEL,TRAN,SIZE'])
        if res_lsblk.stdout:
            try:
                blk_data = json.loads(res_lsblk.stdout)
                for b in blk_data.get('blockdevices', []):
                    bname = b.get('name', '')
                    btype = b.get('type', '')
                    if btype == 'disk' and not bname.startswith('loop') and not bname.startswith('ram'):
                        drives.append({
                            'device': f"/dev/{bname}",
                            'name': bname,
                            'type': 'nvme' if 'nvme' in bname else 'scsi',
                            'protocol': 'NVMe' if 'nvme' in bname else 'SATA'
                        })
            except Exception:
                pass

    return drives

def _format_smart_json(data, dev_path):
    """Ekstraksi telemetri terstruktur dari output JSON smartctl"""
    bname = os.path.basename(dev_path)
    is_nvme = (data.get('device', {}).get('type') == 'nvme') or ('nvme' in bname.lower())

    model = data.get('model_name') or data.get('device', {}).get('info_name') or bname
    serial = data.get('serial_number') or 'N/A'
    firmware = data.get('firmware_version') or 'N/A'
    cap_bytes = data.get('user_capacity', {}).get('bytes') or data.get('nvme_total_capacity') or 0
    cap_gb = f"{round(cap_bytes / (1024**3), 1)} GB" if cap_bytes else "N/A"

    smart_status_obj = data.get('smart_status', {})
    passed = smart_status_obj.get('passed', True)
    health_status = 'PASSED' if passed else 'WARNING / FAILING'

    temp_val = None
    if 'temperature' in data and isinstance(data['temperature'], dict):
        temp_val = data['temperature'].get('current')
    elif 'nvme_smart_health_information_log' in data:
        temp_val = data['nvme_smart_health_information_log'].get('temperature')

    poh = 0
    error_count = 0
    nvme_stats = None
    ata_attrs = []
    pending_sectors = 0
    reallocated_sectors = 0

    if is_nvme:
        log = data.get('nvme_smart_health_information_log', {})
        poh = log.get('power_on_hours', 0)
        error_count = log.get('media_errors', 0) + log.get('num_err_log_entries', 0)

        units_written = log.get('data_units_written', 0)
        tbw = round((units_written * 512000) / (1024**4), 2) if units_written else 0

        units_read = log.get('data_units_read', 0)
        tbr = round((units_read * 512000) / (1024**4), 2) if units_read else 0

        percentage_used = log.get('percentage_used', 0)
        available_spare = log.get('available_spare', 100)
        spare_threshold = log.get('available_spare_threshold', 10)

        nvme_stats = {
            'percentage_used': percentage_used,
            'tbw': tbw,
            'tbr': tbr,
            'available_spare': available_spare,
            'available_spare_threshold': spare_threshold,
            'critical_warning': log.get('critical_warning', 0),
            'unsafe_shutdowns': log.get('unsafe_shutdowns', 0),
            'media_errors': log.get('media_errors', 0),
            'num_err_log_entries': log.get('num_err_log_entries', 0)
        }
    else:
        table = data.get('ata_smart_attributes', {}).get('table', [])
        for attr in table:
            attr_id = attr.get('id')
            attr_name = attr.get('name')
            raw_val = attr.get('raw', {}).get('string') or str(attr.get('raw', {}).get('value', '0'))
            val = attr.get('value')
            worst = attr.get('worst')
            thresh = attr.get('thresh')
            when_failed = attr.get('when_failed', '-')

            if attr_name == 'Power_On_Hours':
                try:
                    poh = int(raw_val.split()[0])
                except Exception:
                    pass
            elif attr_name == 'Current_Pending_Sector':
                try:
                    pending_sectors = int(raw_val.split()[0])
                    error_count += pending_sectors
                except Exception:
                    pass
            elif attr_name == 'Reallocated_Sector_Ct':
                try:
                    reallocated_sectors = int(raw_val.split()[0])
                    error_count += reallocated_sectors
                except Exception:
                    pass
            elif attr_name in ('Offline_Uncorrectable', 'Reported_Uncorrect'):
                try:
                    error_count += int(raw_val.split()[0])
                except Exception:
                    pass

            ata_attrs.append({
                'id': attr_id,
                'name': attr_name,
                'value': val,
                'worst': worst,
                'thresh': thresh,
                'raw': raw_val,
                'when_failed': when_failed
            })

    selftest_status = 'Tidak ada tes aktif'
    if is_nvme:
        op = data.get('nvme_self_test_log', {}).get('current_self_test_operation', {})
        selftest_status = op.get('string', 'No test in progress')
    else:
        st_obj = data.get('ata_smart_data', {}).get('self_test', {}).get('status', {})
        selftest_status = st_obj.get('string', 'Completed or No test running')

    is_healthy = passed and (error_count == 0 or (nvme_stats and nvme_stats['percentage_used'] < 90))

    return {
        'device': dev_path,
        'name': bname,
        'model': model,
        'serial': serial,
        'firmware': firmware,
        'capacity_bytes': cap_bytes,
        'capacity_gb': cap_gb,
        'protocol': 'NVMe' if is_nvme else 'SATA',
        'is_nvme': is_nvme,
        'healthy': is_healthy,
        'health_status': 'PASSED' if is_healthy else 'WARNING',
        'temperature': temp_val,
        'power_on_hours': poh,
        'nvme_stats': nvme_stats,
        'ata_attributes': ata_attrs,
        'pending_sectors': pending_sectors,
        'reallocated_sectors': reallocated_sectors,
        'selftest_status': selftest_status,
        'error_count': error_count,
        'raw_json': data
    }

def _parse_drive_smart(dev_path):
    """Membaca dan memparsing data telemetri S.M.A.R.T. untuk sebuah drive fisik"""
    res = _run_smartctl_cmd(['-a', '-j', dev_path])
    if res.stdout:
        try:
            data = json.loads(res.stdout)
            return _format_smart_json(data, dev_path)
        except Exception:
            pass

    bname = os.path.basename(dev_path)
    return {
        'device': dev_path,
        'name': bname,
        'model': 'Drive Fisik ' + bname,
        'serial': 'N/A',
        'firmware': 'N/A',
        'capacity_bytes': 0,
        'capacity_gb': 'N/A',
        'protocol': 'NVMe' if 'nvme' in bname else 'SATA',
        'is_nvme': 'nvme' in bname,
        'healthy': True,
        'health_status': 'PASSED',
        'temperature': None,
        'power_on_hours': 0,
        'nvme_stats': None,
        'ata_attributes': [],
        'pending_sectors': 0,
        'reallocated_sectors': 0,
        'selftest_status': 'Tidak ada tes aktif',
        'error_count': 0,
        'raw_json': {}
    }

def _get_raid_and_zfs_status():
    """Inspeksi status Software RAID mdadm dan ZFS pool"""
    raid_arrays = []
    res_md = _run_scheduler_cmd(['cat', '/proc/mdstat'])
    if res_md.returncode == 0 and res_md.stdout:
        lines = res_md.stdout.splitlines()
        for i, l in enumerate(lines):
            l = l.strip()
            if l.startswith('md'):
                parts = l.split()
                md_name = parts[0]
                status = parts[1] if len(parts) > 1 else 'unknown'
                level = parts[2] if len(parts) > 2 else ''
                devices = parts[3:] if len(parts) > 3 else []
                detail_line = lines[i+1].strip() if i+1 < len(lines) else ''
                raid_arrays.append({
                    'name': md_name,
                    'status': status,
                    'level': level,
                    'devices': devices,
                    'detail': detail_line
                })

    zfs_pools = []
    res_zfs = _run_scheduler_cmd(['zpool', 'list', '-H', '-o', 'name,size,alloc,free,frag,cap,health'])
    if res_zfs.returncode == 0 and res_zfs.stdout:
        for line in res_zfs.stdout.strip().splitlines():
            p = line.split()
            if len(p) >= 7:
                zfs_pools.append({
                    'name': p[0],
                    'size': p[1],
                    'alloc': p[2],
                    'free': p[3],
                    'frag': p[4],
                    'capacity': p[5],
                    'health': p[6]
                })

    return {
        'raid_active': len(raid_arrays) > 0,
        'raid_arrays': raid_arrays,
        'zfs_active': len(zfs_pools) > 0,
        'zfs_pools': zfs_pools
    }


@app.route('/smart')
@login_required
def drive_health_page():
    """Halaman Drive Health & S.M.A.R.T. Inspector"""
    return render_template('drive_health.html')

@app.route('/api/smart/summary')
@login_required
def api_smart_summary():
    """Ringkasan status kesehatan seluruh drive fisik host"""
    raw_drives = _discover_physical_drives()
    drives_data = []
    healthy_count = 0
    warning_count = 0
    max_temp = 0

    for d in raw_drives:
        dev_path = d['device']
        parsed = _parse_drive_smart(dev_path)
        drives_data.append(parsed)

        if parsed.get('healthy'):
            healthy_count += 1
        else:
            warning_count += 1

        t = parsed.get('temperature')
        if t and isinstance(t, (int, float)) and t > max_temp:
            max_temp = t

    raid_info = _get_raid_and_zfs_status()

    return jsonify({
        'success': True,
        'total_drives': len(drives_data),
        'healthy_count': healthy_count,
        'warning_count': warning_count,
        'max_temperature': max_temp if max_temp > 0 else None,
        'drives': drives_data,
        'raid': raid_info
    })

@app.route('/api/smart/detail/<disk_name>')
@login_required
def api_smart_detail(disk_name):
    """Mendapatkan rincian telemetri S.M.A.R.T. lengkap untuk sebuah disk"""
    disk_name = (disk_name or '').strip()
    if not re.match(r'^[a-zA-Z0-9_.-]+$', disk_name):
        return jsonify({'success': False, 'error': 'Nama disk tidak valid'}), 400

    dev_path = f"/dev/{disk_name}"
    data = _parse_drive_smart(dev_path)
    return jsonify({
        'success': True,
        'drive': data
    })

@app.route('/api/smart/test/start', methods=['POST'])
@login_required
def api_smart_test_start():
    """Memulai eksekusi S.M.A.R.T. Self-Test (Short / Long)"""
    data = request.json or {}
    device = (data.get('device') or '').strip()
    test_type = (data.get('type') or 'short').strip().lower()

    if not re.match(r'^[a-zA-Z0-9_.-]+$', device):
        return jsonify({'success': False, 'error': 'Nama device tidak valid'}), 400

    if test_type not in ('short', 'long'):
        return jsonify({'success': False, 'error': 'Tipe self-test tidak valid (short atau long)'}), 400

    dev_path = f"/dev/{device}"
    res = _run_smartctl_cmd(['-t', test_type, dev_path])

    if res.returncode == 0 or 'has begun' in res.stdout.lower() or 'routine begun' in res.stdout.lower():
        return jsonify({
            'success': True,
            'message': f"S.M.A.R.T. {test_type.upper()} Self-Test berhasil dimulai pada {device}",
            'output': res.stdout
        })
    else:
        return jsonify({
            'success': False,
            'error': res.stderr or res.stdout or 'Gagal memulai S.M.A.R.T. Self-Test'
        }), 500

@app.route('/api/smart/test/abort', methods=['POST'])
@login_required
def api_smart_test_abort():
    """Membatalkan eksekusi S.M.A.R.T. Self-Test yang sedang berjalan"""
    data = request.json or {}
    device = (data.get('device') or '').strip()

    if not re.match(r'^[a-zA-Z0-9_.-]+$', device):
        return jsonify({'success': False, 'error': 'Nama device tidak valid'}), 400

    dev_path = f"/dev/{device}"
    res = _run_smartctl_cmd(['-X', dev_path])

    if res.returncode == 0 or 'aborted' in res.stdout.lower():
        return jsonify({
            'success': True,
            'message': f"S.M.A.R.T. Self-Test pada {device} berhasil dibatalkan",
            'output': res.stdout
        })
    else:
        return jsonify({
            'success': False,
            'error': res.stderr or res.stdout or 'Gagal membatalkan S.M.A.R.T. Self-Test'
        }), 500

@app.route('/api/smart/raid')
@login_required
def api_smart_raid():
    """Status Software RAID mdadm dan ZFS pool"""
    raid_info = _get_raid_and_zfs_status()
    return jsonify({
        'success': True,
        'raid': raid_info
    })


# ==========================================
# PACKAGE & OS UPDATE MANAGER (UNIVERSAL MULTI-DISTRO)
# Mendukung: APT (Debian/Ubuntu), DNF/YUM (Fedora/RHEL/Rocky),
#            Pacman (Arch/Garuda/Manjaro), APK (Alpine), Zypper (openSUSE)
# ==========================================

_DETECTED_PKG_MANAGER = None
_KERNEL_PKG_PATTERNS = (
    'linux-image', 'linux-generic', 'linux-lts', 'linux-zen', 'linux-hardened',
    'kernel-core', 'kernel-default', 'kernel-modules'
)


def _run_apt_cmd(args, timeout=120):
    """Menjalankan perintah package manager di host via eksekutor universal (nsenter / native)."""
    if not isinstance(args, list):
        args = [args]
    env = os.environ.copy()
    env['DEBIAN_FRONTEND'] = 'noninteractive'
    env['LANG'] = 'C.UTF-8'
    res = _run_host_cmd(args, timeout=timeout, env=env)
    return res.returncode, res.stdout, res.stderr


def _detect_distro_info():
    """Deteksi nama dan ID distribusi Linux host dari /etc/os-release secara dinamis."""
    host_root = os.environ.get('HOST_ROOT', '/host/root')
    candidates = [os.path.join(host_root, 'etc', 'os-release'), '/etc/os-release']
    info = {'id': 'linux', 'pretty_name': f"{platform.system()} {platform.release()}"}
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('PRETTY_NAME='):
                            info['pretty_name'] = line.split('=', 1)[1].strip().strip('"')
                        elif line.startswith('ID='):
                            info['id'] = line.split('=', 1)[1].strip().strip('"').lower()
                return info
            except Exception:
                pass
    return info


def _detect_package_manager(force_refresh=False):
    """Auto-deteksi package manager utama host (apt/dnf/yum/pacman/apk/zypper)."""
    global _DETECTED_PKG_MANAGER
    if _DETECTED_PKG_MANAGER and not force_refresh:
        return _DETECTED_PKG_MANAGER

    checks = [
        ('apt-get', 'apt'),
        ('dnf', 'dnf'),
        ('yum', 'yum'),
        ('pacman', 'pacman'),
        ('apk', 'apk'),
        ('zypper', 'zypper'),
    ]
    for binary, pm_name in checks:
        res = _run_host_cmd(['which', binary], timeout=4, include_pid=False)
        if res.returncode == 0 and res.stdout.strip():
            _DETECTED_PKG_MANAGER = pm_name
            return pm_name

    _DETECTED_PKG_MANAGER = 'unknown'
    return 'unknown'


def _build_pkg_refresh_cmd(pm):
    """Susun perintah refresh repository cache sesuai package manager host."""
    mapping = {
        'apt': ['apt-get', 'update'],
        'dnf': ['dnf', 'makecache', '-q'],
        'yum': ['yum', 'makecache', '-q'],
        'pacman': ['pacman', '-Sy', '--noconfirm'],
        'apk': ['apk', 'update'],
        'zypper': ['zypper', '--non-interactive', 'refresh'],
    }
    return mapping.get(pm)


def _build_pkg_install_cmd(pm, package_name):
    """Susun perintah instalasi satu paket lintas distro Linux."""
    mapping = {
        'apt': ['apt-get', 'install', '-y', package_name],
        'dnf': ['dnf', 'install', '-y', package_name],
        'yum': ['yum', 'install', '-y', package_name],
        'pacman': ['pacman', '-S', '--noconfirm', package_name],
        'apk': ['apk', 'add', '--no-cache', package_name],
        'zypper': ['zypper', '--non-interactive', 'install', package_name],
    }
    return mapping.get(pm)


def _build_pkg_upgrade_cmd(pm, packages=None, dry_run=False):
    """Susun perintah simulasi dry-run atau upgrade paket lintas distro Linux."""
    has_pkgs = bool(packages and len(packages) > 0)
    if pm == 'apt':
        if has_pkgs:
            return ['apt-get', 'install', '--only-upgrade', '-y'] + (['-s'] if dry_run else []) + list(packages)
        return ['apt-get', 'upgrade', '-y'] + (['-s'] if dry_run else [])
    if pm in ('dnf', 'yum'):
        base = [pm, 'upgrade', '--assumeno' if dry_run else '-y']
        return base + list(packages) if has_pkgs else base
    if pm == 'pacman':
        if has_pkgs:
            return ['pacman', '-S', '--noconfirm'] + (['--print'] if dry_run else []) + list(packages)
        return ['pacman', '-Su', '--noconfirm'] + (['--print'] if dry_run else [])
    if pm == 'apk':
        base = ['apk', 'upgrade'] + (['--simulate'] if dry_run else [])
        return base + list(packages) if has_pkgs else base
    if pm == 'zypper':
        base = ['zypper', '--non-interactive', 'update'] + (['--dry-run'] if dry_run else [])
        return base + list(packages) if has_pkgs else base
    return None


def _parse_apt_upgradable(stdout):
    """Parser output `apt list --upgradable`."""
    pkgs = []
    pattern = r'^([^/]+)/(\S+)\s+(\S+)\s+(\S+)\s+\[upgradable from:\s*([^\]]+)\]'
    for line in (stdout or '').splitlines():
        line = line.strip()
        if not line or line.startswith('Listing...') or '[' not in line:
            continue
        m = re.match(pattern, line)
        if m:
            name, repo, new_ver, arch, cur_ver = m.groups()
            pkgs.append({
                'name': name,
                'repo': repo,
                'new_version': new_ver,
                'arch': arch,
                'current_version': cur_ver,
                'is_security': 'security' in repo.lower()
            })
    return pkgs


def _parse_dnf_upgradable(stdout, security_names=None):
    """Parser output `dnf/yum check-update -q`."""
    sec_set = set(security_names or ())
    pkgs = []
    for line in (stdout or '').splitlines():
        line = line.strip()
        if not line or line.startswith(('Last metadata', 'Obsoleting', 'Security:')):
            continue
        parts = line.split()
        if len(parts) < 3 or '.' not in parts[0]:
            continue
        name, arch = parts[0].rsplit('.', 1)
        new_ver = parts[1]
        repo = parts[2]
        pkgs.append({
            'name': name,
            'repo': repo,
            'new_version': new_ver,
            'arch': arch,
            'current_version': 'installed',
            'is_security': ('security' in repo.lower()) or (name in sec_set)
        })
    return pkgs


def _parse_pacman_upgradable(stdout):
    """Parser output `pacman -Qu` atau `checkupdates`."""
    arch_default = platform.machine() or 'x86_64'
    sec_hints = ('openssl', 'openssh', 'linux', 'glibc', 'sudo', 'systemd', 'ca-certificates', 'gnutls', 'curl', 'gnupg')
    pkgs = []
    pattern = r'^(\S+)\s+(\S+)\s+->\s+(\S+)'
    for line in (stdout or '').splitlines():
        m = re.match(pattern, line.strip())
        if m:
            name, cur_ver, new_ver = m.groups()
            pkgs.append({
                'name': name,
                'repo': 'pacman',
                'new_version': new_ver,
                'arch': arch_default,
                'current_version': cur_ver,
                'is_security': any(h in name.lower() for h in sec_hints)
            })
    return pkgs


def _parse_apk_upgradable(stdout):
    """Parser output `apk version -l '<'` (Alpine Linux)."""
    arch_default = platform.machine() or 'x86_64'
    pkgs = []
    for line in (stdout or '').splitlines():
        line = line.strip()
        if '<' not in line or line.startswith('Installed:'):
            continue
        left, right = [x.strip() for x in line.split('<', 1)]
        m = re.match(r'^(.+?)-([0-9][^-]*(?:-r[0-9]+)?)$', left)
        if m:
            name, cur_ver = m.groups()
        else:
            name, cur_ver = left, 'installed'
        new_ver = right.split()[0] if right else ''
        pkgs.append({
            'name': name,
            'repo': 'alpine',
            'new_version': new_ver,
            'arch': arch_default,
            'current_version': cur_ver,
            'is_security': any(h in name.lower() for h in ('openssl', 'musl', 'openssh', 'busybox', 'linux', 'ca-certificates'))
        })
    return pkgs


def _parse_zypper_upgradable(stdout):
    """Parser output `zypper --non-interactive list-updates`."""
    pkgs = []
    for line in (stdout or '').splitlines():
        if '|' not in line:
            continue
        cols = [c.strip() for c in line.split('|')]
        if len(cols) >= 6 and cols[0] == 'v':
            repo, name, cur_ver, new_ver, arch = cols[1], cols[2], cols[3], cols[4], cols[5]
            pkgs.append({
                'name': name,
                'repo': repo,
                'new_version': new_ver,
                'arch': arch,
                'current_version': cur_ver,
                'is_security': 'security' in repo.lower()
            })
    return pkgs


def _parse_upgradable_packages(pm=None):
    """Mengambil dan mem-parsing daftar paket upgradable secara lintas distro."""
    pm = pm or _detect_package_manager()
    if pm == 'apt':
        ret, stdout, _ = _run_apt_cmd(['apt', 'list', '--upgradable'], timeout=30)
        return _parse_apt_upgradable(stdout) if (ret == 0 or stdout) else []
    if pm in ('dnf', 'yum'):
        ret, stdout, _ = _run_apt_cmd([pm, 'check-update', '-q'], timeout=45)
        if ret not in (0, 100) and not stdout:
            return []
        sec_names = set()
        if pm == 'dnf':
            s_ret, s_out, _ = _run_apt_cmd(['dnf', 'updateinfo', 'list', 'security', '-q'], timeout=25)
            if s_ret == 0 and s_out:
                for line in s_out.splitlines():
                    parts = line.split()
                    if len(parts) >= 3:
                        pkg_spec = parts[2]
                        sec_names.add(pkg_spec.rsplit('-', 2)[0] if '-' in pkg_spec else pkg_spec)
        return _parse_dnf_upgradable(stdout, security_names=sec_names)
    if pm == 'pacman':
        ret, stdout, _ = _run_apt_cmd(['pacman', '-Qu'], timeout=30)
        return _parse_pacman_upgradable(stdout) if stdout else []
    if pm == 'apk':
        ret, stdout, _ = _run_apt_cmd(['apk', 'version', '-l', '<'], timeout=30)
        return _parse_apk_upgradable(stdout) if (ret == 0 or stdout) else []
    if pm == 'zypper':
        ret, stdout, _ = _run_apt_cmd(['zypper', '--non-interactive', 'list-updates'], timeout=45)
        return _parse_zypper_upgradable(stdout) if (ret == 0 or stdout) else []
    return []


def _get_reboot_status(pm=None):
    """Memeriksa kebutuhan reboot lintas distro (Debian/Ubuntu, RHEL/Fedora, Arch/Universal)."""
    pm = pm or _detect_package_manager()
    # 1. Debian / Ubuntu standard flag
    ret, _, _ = _run_apt_cmd(['test', '-f', '/var/run/reboot-required'], timeout=5)
    if ret == 0:
        reboot_pkgs = []
        ret_pkgs, stdout_pkgs, _ = _run_apt_cmd(['cat', '/var/run/reboot-required.pkgs'], timeout=5)
        if ret_pkgs == 0 and stdout_pkgs:
            reboot_pkgs = [p.strip() for p in stdout_pkgs.splitlines() if p.strip()]
        return True, reboot_pkgs

    # 2. RHEL / Fedora / Rocky (dnf-utils / yum-utils)
    if pm in ('dnf', 'yum'):
        ret_nr, out_nr, _ = _run_apt_cmd(['needs-restarting', '-r'], timeout=10)
        if ret_nr == 1:
            return True, ['kernel/core-libraries (needs-restarting)']

    # 3. Universal kernel-module mismatch check (Arch / Alpine / openSUSE / generic)
    ret_k, out_k, _ = _run_apt_cmd(['uname', '-r'], timeout=5)
    running_k = out_k.strip() if ret_k == 0 else ''
    if running_k:
        ret_mod, _, _ = _run_apt_cmd(['test', '-d', f'/lib/modules/{running_k}'], timeout=5)
        ret_base, out_base, _ = _run_apt_cmd(['ls', '-1', '/lib/modules'], timeout=5)
        if ret_mod != 0 and ret_base == 0 and out_base.strip():
            return True, [f'kernel-upgrade (running: {running_k})']

    return False, []


def _get_kernel_info(pm=None):
    """Mendapatkan informasi kernel berjalan, daftar kernel terinstal, dan status auto-update lintas distro."""
    pm = pm or _detect_package_manager()
    ret_k, out_k, _ = _run_apt_cmd(['uname', '-r'], timeout=5)
    running_kernel = out_k.strip() if (ret_k == 0 and out_k.strip()) else (platform.release() or 'Unknown')

    installed_kernels = []
    if pm == 'apt':
        ret_dpkg, out_dpkg, _ = _run_apt_cmd(['dpkg', '-l', 'linux-image-[0-9]*'], timeout=10)
        if ret_dpkg == 0 and out_dpkg:
            for line in out_dpkg.splitlines():
                if line.startswith('ii'):
                    parts = line.split()
                    if len(parts) >= 2:
                        installed_kernels.append(parts[1].replace('linux-image-', ''))
    elif pm in ('dnf', 'yum', 'zypper'):
        ret_rpm, out_rpm, _ = _run_apt_cmd(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}.%{ARCH}\n', 'kernel', 'kernel-core', 'kernel-default'], timeout=10)
        if out_rpm:
            for line in out_rpm.splitlines():
                line = line.strip()
                if line and 'is not installed' not in line and line not in installed_kernels:
                    installed_kernels.append(line)

    # Universal fallback (Arch / Alpine / generic): /lib/modules
    if not installed_kernels:
        ret_m, out_m, _ = _run_apt_cmd(['ls', '-1', '/lib/modules'], timeout=5)
        if ret_m == 0 and out_m:
            installed_kernels = [k.strip() for k in out_m.splitlines() if k.strip()]

    # Auto-update service check lintas distro
    auto_svc_map = {
        'apt': 'unattended-upgrades.service',
        'dnf': 'dnf-automatic.timer',
        'yum': 'yum-cron.service',
    }
    auto_svc = auto_svc_map.get(pm, 'manual')
    auto_updates = False
    if auto_svc != 'manual':
        ret_u, out_u, _ = _run_apt_cmd(['systemctl', 'is-active', auto_svc], timeout=5)
        auto_updates = (ret_u == 0 and out_u.strip() == 'active')

    return {
        'running_kernel': running_kernel,
        'installed_kernels': installed_kernels,
        'auto_updates_active': auto_updates,
        'auto_update_service': auto_svc
    }


@app.route('/packages')
@login_required
def packages_page():
    """Halaman Package & OS Update Manager"""
    return render_template('packages.html')


@app.route('/api/packages/summary')
@login_required
def api_packages_summary():
    """Ringkasan status paket, keamanan, distro, dan kernel host secara lintas distro"""
    pm = _detect_package_manager()
    distro = _detect_distro_info()
    pkgs = _parse_upgradable_packages(pm=pm)
    total_upgradable = len(pkgs)
    security_count = sum(1 for p in pkgs if p['is_security'])
    regular_count = total_upgradable - security_count

    reboot_required, reboot_pkgs = _get_reboot_status(pm=pm)
    kernel_info = _get_kernel_info(pm=pm)

    kernel_upgrade_available = any(
        p['name'] in ('linux', 'kernel') or any(pat in p['name'] for pat in _KERNEL_PKG_PATTERNS)
        for p in pkgs
    )

    return jsonify({
        'success': True,
        'package_manager': pm,
        'distro_name': distro.get('pretty_name', 'Linux'),
        'distro_id': distro.get('id', 'linux'),
        'total_upgradable': total_upgradable,
        'security_count': security_count,
        'regular_count': regular_count,
        'reboot_required': reboot_required,
        'reboot_pkgs': reboot_pkgs,
        'kernel_upgrade_available': kernel_upgrade_available,
        'running_kernel': kernel_info.get('running_kernel', 'Unknown'),
        'installed_kernels': kernel_info.get('installed_kernels', []),
        'auto_updates_active': kernel_info.get('auto_updates_active', False),
        'auto_update_service': kernel_info.get('auto_update_service', 'manual')
    })


@app.route('/api/packages/list')
@login_required
def api_packages_list():
    """Daftar paket yang dapat diperbarui (upgradable) secara lintas distro"""
    pm = _detect_package_manager()
    pkgs = _parse_upgradable_packages(pm=pm)
    return jsonify({
        'success': True,
        'package_manager': pm,
        'count': len(pkgs),
        'packages': pkgs
    })


@app.route('/api/packages/refresh', methods=['POST'])
@login_required
def api_packages_refresh():
    """Memperbarui cache repository paket host (lintas distro)"""
    pm = _detect_package_manager()
    cmd = _build_pkg_refresh_cmd(pm)
    if not cmd:
        return jsonify({
            'success': False,
            'package_manager': pm,
            'returncode': 1,
            'output': 'Package manager Linux tidak terdeteksi atau belum didukung pada host ini.'
        }), 400

    ret, stdout, stderr = _run_apt_cmd(cmd, timeout=120)
    output = stdout + ('\n' + stderr if stderr else '')
    return jsonify({
        'success': (ret == 0),
        'package_manager': pm,
        'command': ' '.join(cmd),
        'returncode': ret,
        'output': output
    }), (200 if ret == 0 else 500)


@app.route('/api/packages/upgrade', methods=['POST'])
@login_required
def api_packages_upgrade():
    """Mengeksekusi simulasi dry-run atau upgrade nyata paket host secara lintas distro"""
    data = request.json or {}
    dry_run = bool(data.get('dry_run', False))
    packages = data.get('packages')  # list of package names, or None for all

    clean_pkgs = None
    if packages and isinstance(packages, list) and len(packages) > 0:
        clean_pkgs = []
        for p in packages:
            p_clean = str(p).strip()
            if re.match(r'^[a-zA-Z0-9_\.\+:-]+$', p_clean):
                clean_pkgs.append(p_clean)

        if not clean_pkgs:
            return jsonify({'success': False, 'error': 'Daftar nama paket tidak valid'}), 400

    pm = _detect_package_manager()
    cmd = _build_pkg_upgrade_cmd(pm, packages=clean_pkgs, dry_run=dry_run)
    if not cmd:
        return jsonify({
            'success': False,
            'package_manager': pm,
            'error': 'Package manager Linux tidak terdeteksi pada host ini'
        }), 400

    ret, stdout, stderr = _run_apt_cmd(cmd, timeout=300)
    # Pada dnf/yum dengan --assumeno, exit code 1 adalah hasil normal dry-run setelah menampilkan daftar transaksi
    is_ok = (ret == 0) or (dry_run and pm in ('dnf', 'yum') and ret == 1 and bool(stdout))
    output = stdout + ('\n' + stderr if stderr else '')

    return jsonify({
        'success': is_ok,
        'dry_run': dry_run,
        'package_manager': pm,
        'command': ' '.join(cmd),
        'returncode': ret,
        'output': output
    }), (200 if is_ok else 500)


# ==========================================
# ALERTING & NOTIFICATION ENGINE (UNIVERSAL MULTI-CHANNEL)
# ==========================================

ALERT_CONFIG_FILE = os.path.join(DATA_DIR, 'alert_config.json')
ALERT_HISTORY_FILE = os.path.join(DATA_DIR, 'alert_history.json')

DEFAULT_ALERT_CONFIG = {
    'channel': 'telegram',  # 'telegram', 'whatsapp', 'both', 'webhook'
    'telegram': {
        'enabled': True,
        'bot_token': '',
        'chat_id': ''
    },
    'whatsapp': {
        'enabled': False,
        'gateway_url': 'http://127.0.0.1:3000/send',
        'target_phone': ''
    },
    'webhook': {
        'enabled': False,
        'url': ''
    },
    'rules': {
        'cpu_threshold': 90,
        'cpu_enabled': True,
        'ram_threshold': 85,
        'ram_enabled': True,
        'disk_threshold': 90,
        'disk_enabled': True,
        'smart_warning_enabled': True,
        'service_failure_enabled': True,
        'reboot_required_enabled': True
    }
}


def _load_alert_config():
    """Memuat konfigurasi notifikasi dengan fallback default aman."""
    if os.path.exists(ALERT_CONFIG_FILE):
        try:
            with open(ALERT_CONFIG_FILE, 'r') as f:
                cfg = json.load(f)
                merged = json.loads(json.dumps(DEFAULT_ALERT_CONFIG))
                for k, v in cfg.items():
                    if isinstance(v, dict) and k in merged:
                        merged[k].update(v)
                    else:
                        merged[k] = v
                return merged
        except Exception as e:
            print("Error loading alert config:", e)
    return json.loads(json.dumps(DEFAULT_ALERT_CONFIG))


def _save_alert_config(config):
    """Menyimpan konfigurasi notifikasi ke file JSON."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(ALERT_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print("Error saving alert config:", e)
        return False


def _load_alert_history():
    """Memuat riwayat pengiriman notifikasi."""
    if os.path.exists(ALERT_HISTORY_FILE):
        try:
            with open(ALERT_HISTORY_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print("Error loading alert history:", e)
    return []


def _append_alert_history(entry):
    """Mencatat entri pengiriman notifikasi baru ke riwayat (maks 100)."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        history = _load_alert_history()
        history.insert(0, entry)
        history = history[:100]
        with open(ALERT_HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
        return True
    except Exception as e:
        print("Error appending alert history:", e)
        return False


def _send_telegram_notification(bot_token, chat_id, message):
    """Mengirim pesan notifikasi via Telegram Bot API."""
    if not bot_token or not chat_id:
        return False, "Bot Token atau Chat ID tidak boleh kosong"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": str(chat_id).strip(),
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        res = requests.post(url, json=payload, timeout=12)
        data = res.json()
        if data.get("ok"):
            return True, "Pesan berhasil terkirim ke Telegram"
        return False, data.get("description", f"Telegram error: {res.status_code}")
    except requests.exceptions.Timeout:
        return False, "Koneksi ke Telegram API timeout (12 detik)"
    except Exception as e:
        return False, str(e)


def _send_http_with_host_fallback(url, payload, headers=None, timeout=12):
    """
    Kirim HTTP POST. Jika target mengarah ke loopback (127.0.0.1 / localhost) dan
    berjalan di dalam kontainer Docker, lakukan eksekusi langsung ke host network
    namespace via nsenter + curl agar dapat menjangkau daemon port host (mis. WA bridge port 3000).
    """
    url_clean = url.strip()
    is_loopback = ('127.0.0.1' in url_clean or 'localhost' in url_clean)

    # 1. Jika loopback dan container memiliki kapabilitas nsenter, langsung bypass via host namespace
    if is_loopback and _can_use_nsenter():
        try:
            cmd = [
                'nsenter', '-t', '1', '-m', '-u', '-i', '-n', '--',
                '/usr/bin/curl', '-s', '-S',
                '-w', '\n__HTTP_CODE__:%{http_code}',
                '-X', 'POST',
                '-H', 'Content-Type: application/json',
                '-d', json.dumps(payload),
                url_clean,
                '--connect-timeout', str(min(timeout, 8)),
                '--max-time', str(timeout)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
            stdout = res.stdout
            if '__HTTP_CODE__:' in stdout:
                body, code_str = stdout.rsplit('__HTTP_CODE__:', 1)
                http_code = int(code_str.strip()) if code_str.strip().isdigit() else 0
                if 200 <= http_code < 300:
                    return True, http_code, body
                return False, http_code, body or res.stderr
            if res.returncode != 0:
                if 'Connection refused' in res.stderr or 'Failed to connect' in res.stderr:
                    return False, 502, "Koneksi ditolak oleh host (Connection refused). Gateway lokal tidak aktif atau port belum berjalan."
                return False, 500, res.stderr or "Eksekusi curl host gagal"
            return True, 200, stdout
        except subprocess.TimeoutExpired:
            return False, 408, "Host curl timeout (12 detik)"
        except Exception as e:
            return False, 500, f"Host fallback error: {str(e)}"

    # 2. Direct requests via Python
    try:
        req_headers = headers or {"Content-Type": "application/json"}
        res = requests.post(url_clean, json=payload, headers=req_headers, timeout=timeout)
        if 200 <= res.status_code < 300:
            return True, res.status_code, res.text
        return False, res.status_code, res.text
    except requests.exceptions.Timeout:
        return False, 408, "Koneksi gateway timeout (12 detik)"
    except requests.exceptions.ConnectionError:
        return False, 502, "Koneksi ditolak (Connection refused). Gateway offline atau URL tidak dapat dijangkau."
    except Exception as e:
        return False, 500, str(e)


def _send_whatsapp_notification(gateway_url, target_phone, message):
    """Mengirim pesan notifikasi via WhatsApp Bridge API."""
    if not gateway_url or not target_phone:
        return False, "Gateway URL atau Nomor WhatsApp tidak boleh kosong"

    clean_phone = re.sub(r'\D', '', str(target_phone))
    if not clean_phone:
        return False, "Format nomor telepon tidak valid"

    payload = {
        "chatId": clean_phone,
        "number": clean_phone,
        "message": message
    }
    ok, code, text = _send_http_with_host_fallback(gateway_url, payload, timeout=12)
    if ok:
        return True, f"Pesan terkirim ke WhatsApp ({code})"
    return False, f"WhatsApp Gateway ({code}): {text[:140]}"


def _send_webhook_notification(webhook_url, message):
    """Mengirim notifikasi via Generic Webhook (Discord / Slack / Custom)."""
    if not webhook_url:
        return False, "Webhook URL tidak boleh kosong"

    payload = {
        "content": message,
        "text": message,
        "source": "Eka Dashboard Alert Engine"
    }
    headers = {
        "User-Agent": "EkaDashboard-AlertEngine/1.0"
    }
    ok, code, text = _send_http_with_host_fallback(webhook_url, payload, headers=headers, timeout=12)
    if ok:
        return True, f"Webhook berhasil (HTTP {code})"
    return False, f"Webhook ({code}): {text[:140]}"


def _dispatch_alert(channel, message, config=None):
    """Mengirim notifikasi ke satu atau lebih kanal dan mencatat riwayat."""
    if config is None:
        config = _load_alert_config()

    target_channel = channel or config.get('channel', 'telegram')
    results = []

    # 1. Telegram
    if target_channel in ['telegram', 'both', 'all']:
        tg = config.get('telegram', {})
        ok, msg = _send_telegram_notification(tg.get('bot_token'), tg.get('chat_id'), message)
        results.append({'channel': 'Telegram', 'success': ok, 'detail': msg})

    # 2. WhatsApp
    if target_channel in ['whatsapp', 'both', 'all']:
        wa = config.get('whatsapp', {})
        ok, msg = _send_whatsapp_notification(wa.get('gateway_url'), wa.get('target_phone'), message)
        results.append({'channel': 'WhatsApp', 'success': ok, 'detail': msg})

    # 3. Webhook
    if target_channel in ['webhook', 'all']:
        wh = config.get('webhook', {})
        ok, msg = _send_webhook_notification(wh.get('url'), message)
        results.append({'channel': 'Webhook', 'success': ok, 'detail': msg})

    overall_success = any(r['success'] for r in results) if results else False

    # Log riwayat
    entry = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "channel": target_channel,
        "message": message[:200] + '...' if len(message) > 200 else message,
        "success": overall_success,
        "results": results
    }
    _append_alert_history(entry)

    return overall_success, results


@app.route('/alerts')
@login_required
def alerts_page():
    """Halaman Alerting & Notification Engine"""
    return render_template('alerts.html')


@app.route('/api/alerts/config', methods=['GET', 'POST'])
@login_required
def api_alerts_config():
    """Mengambil atau menyimpan konfigurasi notifikasi"""
    if request.method == 'GET':
        cfg = _load_alert_config()
        history = _load_alert_history()
        total_sent = len(history)
        success_count = sum(1 for h in history if h.get('success'))
        failure_count = total_sent - success_count
        return jsonify({
            'success': True,
            'config': cfg,
            'stats': {
                'total_sent': total_sent,
                'success_count': success_count,
                'failure_count': failure_count,
                'last_alert': history[0] if history else None
            }
        })

    # POST: Simpan konfigurasi
    data = request.json or {}
    current_cfg = _load_alert_config()

    # Update field utama
    if 'channel' in data and data['channel'] in ['telegram', 'whatsapp', 'both', 'webhook', 'all']:
        current_cfg['channel'] = data['channel']

    if 'telegram' in data and isinstance(data['telegram'], dict):
        current_cfg['telegram']['enabled'] = bool(data['telegram'].get('enabled', current_cfg['telegram'].get('enabled')))
        if 'bot_token' in data['telegram']:
            current_cfg['telegram']['bot_token'] = str(data['telegram']['bot_token']).strip()
        if 'chat_id' in data['telegram']:
            current_cfg['telegram']['chat_id'] = str(data['telegram']['chat_id']).strip()

    if 'whatsapp' in data and isinstance(data['whatsapp'], dict):
        current_cfg['whatsapp']['enabled'] = bool(data['whatsapp'].get('enabled', current_cfg['whatsapp'].get('enabled')))
        if 'gateway_url' in data['whatsapp']:
            current_cfg['whatsapp']['gateway_url'] = str(data['whatsapp']['gateway_url']).strip()
        if 'target_phone' in data['whatsapp']:
            current_cfg['whatsapp']['target_phone'] = str(data['whatsapp']['target_phone']).strip()

    if 'webhook' in data and isinstance(data['webhook'], dict):
        current_cfg['webhook']['enabled'] = bool(data['webhook'].get('enabled', current_cfg['webhook'].get('enabled')))
        if 'url' in data['webhook']:
            current_cfg['webhook']['url'] = str(data['webhook']['url']).strip()

    if 'rules' in data and isinstance(data['rules'], dict):
        for r_key, r_val in data['rules'].items():
            if r_key in current_cfg['rules']:
                current_cfg['rules'][r_key] = r_val

    ok = _save_alert_config(current_cfg)
    return jsonify({
        'success': ok,
        'config': current_cfg
    }), (200 if ok else 500)


@app.route('/api/alerts/test', methods=['POST'])
@login_required
def api_alerts_test():
    """Mengirim pesan notifikasi uji coba ke kanal yang dipilih"""
    data = request.json or {}
    channel = data.get('channel')  # 'telegram', 'whatsapp', 'both', 'webhook', atau None untuk config default
    message = data.get('message') or (
        f"<b>🔔 [TEST ALERT] Eka Dashboard</b>\n\n"
        f"Server: <code>{socket.gethostname()}</code>\n"
        f"Waktu: <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
        f"Status: Saluran komunikasi terverifikasi normal.\n"
        f"Pesan ini dikirim melalui Alerting & Notification Engine."
    )

    custom_config = data.get('custom_config')
    overall_success, results = _dispatch_alert(channel, message, config=custom_config)

    return jsonify({
        'success': overall_success,
        'results': results
    })


@app.route('/api/alerts/history', methods=['GET'])
@login_required
def api_alerts_history():
    """Mendapatkan riwayat pengiriman notifikasi"""
    history = _load_alert_history()
    return jsonify({
        'success': True,
        'history': history
    })


@app.route('/api/alerts/history/clear', methods=['POST'])
@login_required
def api_alerts_history_clear():
    """Menghapus seluruh riwayat pengiriman notifikasi"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(ALERT_HISTORY_FILE, 'w') as f:
            json.dump([], f)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/alerts/system_check', methods=['POST'])
@login_required
def api_alerts_system_check():
    """Memeriksa ambang batas sistem (CPU, RAM, Disk, SMART) dan memicu alert jika terlampaui"""
    data = request.json or {}
    send_alert = bool(data.get('send_alert', False))
    cfg = _load_alert_config()
    rules = cfg.get('rules', {})

    triggers = []

    # 1. CPU
    try:
        cpu_usage = psutil.cpu_percent(interval=0.2)
        if rules.get('cpu_enabled') and cpu_usage >= rules.get('cpu_threshold', 90):
            triggers.append(f"⚠️ CPU Usage Tinggi: {cpu_usage}% (Ambang batas: {rules.get('cpu_threshold')}%)")
    except Exception:
        pass

    # 2. RAM
    try:
        ram = psutil.virtual_memory()
        if rules.get('ram_enabled') and ram.percent >= rules.get('ram_threshold', 85):
            triggers.append(f"⚠️ RAM Usage Tinggi: {ram.percent}% (Ambang batas: {rules.get('ram_threshold')}%)")
    except Exception:
        pass

    # 3. Disk
    try:
        disk = psutil.disk_usage('/')
        if rules.get('disk_enabled') and disk.percent >= rules.get('disk_threshold', 90):
            triggers.append(f"⚠️ Root Disk Hampir Penuh: {disk.percent}% (Ambang batas: {rules.get('disk_threshold')}%)")
    except Exception:
        pass

    # 4. Reboot Required
    if rules.get('reboot_required_enabled'):
        reboot_req, reboot_pkgs = _get_reboot_status()
        if reboot_req:
            triggers.append(f"🔄 Host Membutuhkan Reboot ({len(reboot_pkgs)} paket kernel/sistem)")

    # 5. SMART Warning
    if rules.get('smart_warning_enabled'):
        try:
            drives = _discover_physical_drives()
            for d in drives:
                dev = d.get('device')
                smart_data = _parse_drive_smart(dev)
                if smart_data.get('health') == 'WARNING':
                    triggers.append(f"🚨 S.M.A.R.T. Warning pada {dev}: Terdeteksi anomali sektor/wear!")
        except Exception:
            pass

    # Dispatch alert jika diminta dan ada triggers
    dispatch_results = []
    if send_alert and triggers:
        alert_msg = (
            f"<b>🚨 [ALERT INCIDENT] Eka Dashboard</b>\n\n"
            f"Server: <code>{socket.gethostname()}</code>\n"
            f"Waktu: <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n\n"
            + "\n".join(triggers)
        )
        _, dispatch_results = _dispatch_alert(cfg.get('channel'), alert_msg, config=cfg)

    return jsonify({
        'success': True,
        'triggered': len(triggers) > 0,
        'triggers': triggers,
        'dispatch_results': dispatch_results
    })


@app.route('/api/alerts/wa_status', methods=['GET'])
@login_required
def api_alerts_wa_status():
    """Memeriksa apakah WhatsApp Gateway aktif dan siap menerima pesan secara opt-in."""
    cfg = _load_alert_config()
    wa_cfg = cfg.get('whatsapp', {})
    wa_enabled = bool(wa_cfg.get('enabled', False))
    gateway_url = (wa_cfg.get('gateway_url') or '').strip()

    if not gateway_url:
        return jsonify({
            'success': True,
            'installed': False,
            'configured': False,
            'online': False,
            'status': 'not_configured',
            'message': 'WhatsApp Gateway URL is not configured (optional module).'
        })

    # Bentuk endpoint health check
    health_url = gateway_url.replace('/send', '/health') if '/send' in gateway_url else gateway_url.rstrip('/') + '/health'
    is_loopback = ('127.0.0.1' in health_url or 'localhost' in health_url)

    if is_loopback and _can_use_nsenter():
        try:
            res = _run_host_cmd([
                '/usr/bin/curl', '-s', '-S',
                '-w', '\n__HTTP_CODE__:%{http_code}',
                health_url,
                '--connect-timeout', '3',
                '--max-time', '5'
            ], timeout=7, include_pid=False)
            stdout = res.stdout or ''
            if '__HTTP_CODE__:' in stdout:
                body, code_str = stdout.rsplit('__HTTP_CODE__:', 1)
                code = int(code_str.strip()) if code_str.strip().isdigit() else 0
                if 200 <= code < 300:
                    try:
                        parsed = json.loads(body.strip())
                        return jsonify({'success': True, 'installed': True, 'configured': wa_enabled, 'online': True, 'status': parsed.get('status', 'connected'), 'details': parsed})
                    except Exception:
                        return jsonify({'success': True, 'installed': True, 'configured': wa_enabled, 'online': True, 'status': 'online', 'details': body[:100]})
                return jsonify({'success': True, 'installed': False, 'configured': wa_enabled, 'online': False, 'status': 'offline', 'http_code': code, 'error': f'HTTP {code}'})
            return jsonify({'success': True, 'installed': False, 'configured': wa_enabled, 'online': False, 'status': 'offline', 'error': 'Gateway tidak merespons'})
        except Exception as e:
            return jsonify({'success': True, 'installed': False, 'configured': wa_enabled, 'online': False, 'status': 'offline', 'error': str(e)})

    # Fallback direct request
    try:
        res = requests.get(health_url, timeout=4)
        if 200 <= res.status_code < 300:
            try:
                parsed = res.json()
                return jsonify({'success': True, 'installed': True, 'configured': wa_enabled, 'online': True, 'status': parsed.get('status', 'connected'), 'details': parsed})
            except Exception:
                return jsonify({'success': True, 'installed': True, 'configured': wa_enabled, 'online': True, 'status': 'online', 'details': res.text[:100]})
        return jsonify({'success': True, 'installed': False, 'configured': wa_enabled, 'online': False, 'status': 'offline', 'http_code': res.status_code})
    except Exception as e:
        return jsonify({'success': True, 'installed': False, 'configured': wa_enabled, 'online': False, 'status': 'offline', 'error': str(e)})


if __name__ == '__main__':
    # Dev server: bind ke loopback saja secara default agar Werkzeug debugger
    # tidak terekspos ke LAN. Override lewat ENV bila memang perlu diakses
    # dari perangkat lain (mis. DEV_HOST=0.0.0.0 DEV_DEBUG=0).
    dev_host = os.environ.get('DEV_HOST', '127.0.0.1')
    dev_port = int(os.environ.get('DEV_PORT', '5000'))
    dev_debug = os.environ.get('DEV_DEBUG', '1') == '1'

    if dev_host != '127.0.0.1' and dev_debug:
        print("WARNING: debug mode aktif pada host non-loopback. "
              "Werkzeug debugger memungkinkan eksekusi kode arbitrer. "
              "Set DEV_DEBUG=0 untuk akses dari jaringan.")

    print(f"Starting Development Server on http://{dev_host}:{dev_port}")
    socketio.run(app, debug=dev_debug, host=dev_host, port=dev_port)

