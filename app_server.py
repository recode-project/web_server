import psutil
import platform
import socket
from flask import Flask, jsonify, render_template, request, Response, session, redirect, url_for, stream_with_context
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
from datetime import datetime
import requests
import threading
import eventlet
import sqlite3
import docker # Ensure docker is imported
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
APP_VERSION = "1.1"
APP_NAME = "Eka Dashboard"
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/ekahr11/web_server/main/version.json"
# ========================================

# Data Directory (For Persistence across updates)
DATA_DIR = os.path.join(BASE_DIR, 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Energy Monitoring
ENERGY_FILE = os.path.join(DATA_DIR, 'energy_data.json')
TOTAL_KWH = 0.0

# Update Check URL (Administrator configurable via Code or ENV)
UPDATE_CHECK_URL = os.environ.get('UPDATE_URL', "https://raw.githubusercontent.com/ekahr11/web_server/main/version.json")
CURRENT_VERSION = "1.1"

def energy_monitor_loop():
    global TOTAL_KWH
    # Load initial
    try:
        if os.path.exists(ENERGY_FILE):
            with open(ENERGY_FILE, 'r') as f:
                data = json.load(f)
                TOTAL_KWH = data.get('kwh', 0.0)
    except:
        pass
        
    while True:
        try:
            # Estimate: Base 6W (Idle) + (CPU% * 6W / 100) -> Range 6W - 12W (Max 12V 1A)
            cpu = psutil.cpu_percent(interval=None) or 0
            watts = 6.0 + (cpu * 6.0 / 100.0)
            
            # Add to kWh
            TOTAL_KWH += watts / 3600000.0
            
            # Save occasionally
            if int(time.time()) % 60 == 0:
                with open(ENERGY_FILE, 'w') as f:
                    json.dump({'kwh': TOTAL_KWH}, f)
                    
            time.sleep(1)
        except:
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

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

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
        'settings': 'full'         # full = all app settings
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
        'settings': 'full'
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
        'settings': 'view'
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
        'settings': 'view'
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



def load_app_settings():
    default_settings = {
        'general': {
            'server_name': 'Amlogic Server',
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
        }
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
                return default_settings
    except Exception as e:
        print(f"!!! CRITICAL: Failed to load settings file: {e}")
        pass
    return default_settings

def save_app_settings(settings):
    with open(APP_SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

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

# Public Monitoring Page (no auth required)
@app.route('/')
def monitoring_page():
    return render_template('monitoring.html')

# Admin Dashboard (requires login)
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('index.html')


@app.route('/api/stats')
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

    # Power Estimation (Synced with energy_monitor_loop)
    uptime_seconds = int(time.time() - psutil.boot_time())
    try:
        avg_watts = 6.0 + (cpu_percent * 6.0 / 100.0) 
        kwh_used = TOTAL_KWH
    except Exception as e:
        print(f"Energy calc error: {e}")
        avg_watts = 0
        kwh_used = 0

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
        "power": {
            "kwh": f"{kwh_used:.4f}",
            "watts_est": avg_watts
        },
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
    
    # Power Snapshot
    cpu_inst = psutil.cpu_percent(interval=None) or 0
    watts_now = 6.0 + (cpu_inst * 6.0 / 100.0)

    return jsonify({
        'power': {
            'kwh': f"{TOTAL_KWH:.4f}",
            'watts_est': int(watts_now)
        },
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
import datetime

@app.route('/files')
@requires_permission('files', 'read')
def files_page():
    return render_template('files.html')

@app.route('/api/files/list', methods=['GET'])
@requires_permission('files', 'read')
def list_files():
    path = request.args.get('path', '/')
    page = int(request.args.get('page', 1))
    # We can load more items per page now because C is fast!
    per_page = 50 

    if not os.path.exists(path):
        return jsonify({'error': 'Path not found'}), 404
    
    try:
        # Use compiled C binary for Native Speed
        cmd = ["./file_lister", path, str(page), str(per_page)]
        result = subprocess.check_output(cmd, cwd=BASE_DIR).decode('utf-8')
        return Response(result, mimetype='application/json')
    except subprocess.CalledProcessError as e:
        return jsonify({'error': 'C Lister Failed: ' + str(e)}), 500
    except Exception as e:
        # Fallback to Python if binary fails or permission denied
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/drives', methods=['GET'])
@requires_permission('files', 'read')
def get_drives():
    drives = []
    try:
        import psutil
        seen_devices = set()
        for part in psutil.disk_partitions(all=False):
            # Skip loop, snap, overlay, docker internals, and config file mounts
            if 'loop' in part.device:
                continue
            if 'snap' in part.mountpoint:
                continue
            if 'overlay' in part.mountpoint:
                continue
            if part.mountpoint in ('/etc/resolv.conf', '/etc/hostname', '/etc/hosts'):
                continue
            if part.device in seen_devices:
                continue
            seen_devices.add(part.device)
            
            try:
                usage = psutil.disk_usage(part.mountpoint)
                drives.append({
                    'mountpoint': part.mountpoint,
                    'device': part.device,
                    'fstype': part.fstype,
                    'total': usage.total,
                    'free': usage.free,
                    'used': usage.used,
                    'percent': usage.percent
                })
            except:
                drives.append({
                    'mountpoint': part.mountpoint,
                    'device': part.device,
                    'fstype': part.fstype,
                })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
    return jsonify({'drives': drives})
@app.route('/api/files/action', methods=['POST'])
@requires_permission('files', 'full')
def file_action():
    data = request.json
    action = data.get('action')
    path = data.get('path')
    
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
            os.rename(path, new_path)
        elif action == 'paste':
            source = data.get('source')
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
def file_content():
    path = request.args.get('path')
    if request.method == 'POST':
        data = request.json
        path = data.get('path')
        content = data.get('content')
        try:
            with open(path, 'w') as f:
                f.write(content)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    # GET
    if not os.path.exists(path):
        return jsonify({'error': 'File not found'}), 404
        
    try:
        with open(path, 'r', encoding='utf-8') as f: # Simple text reading
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

# WebSocket handlers for terminal
@socketio.on('start_terminal')
def handle_start_terminal(data):
    session_id = data.get('session_id', 'default')
    start_path = data.get('path', '/root')
    
    # Create PTY
    master_fd, slave_fd = pty.openpty()
    
    # Fork shell
    pid = os.fork()
    if pid == 0:
        # Child process
        os.close(master_fd)
        os.setsid()
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        
        # Set controlling terminal to avoid "Inappropriate ioctl for device"
        try:
            import fcntl, termios
            fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
        except:
            pass
            
        os.close(slave_fd)
        
        # Use nsenter to enter host PID 1 namespace (root shell on host)
        # Assuming container is privileged and shares PID namespace
        # Use nsenter with -l (login shell) to load host environment/PATH
        cmd = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'bash', '-l']
        
        # Optional: Try to respect path if mapped, but safest is default host root
        # If we wanted to preserve path, we'd need to map container path to host path
        # For now, just spawn host shell
        os.execvp('nsenter', cmd)
    else:
        # Parent process
        os.close(slave_fd)
        terminal_sessions[session_id] = {
            'fd': master_fd,
            'pid': pid
        }
        
        # Start reading thread
        socketio.start_background_task(read_terminal_output, session_id, master_fd)
        emit('terminal_started', {'session_id': session_id})

def read_terminal_output(session_id, fd):
    import eventlet
    while session_id in terminal_sessions:
        eventlet.sleep(0.01)
        try:
            if select.select([fd], [], [], 0.1)[0]:
                data = os.read(fd, 1024)
                if data:
                    socketio.emit('terminal_output', {
                        'session_id': session_id,
                        'data': data.decode('utf-8', errors='replace')
                    })
        except:
            break

@socketio.on('terminal_input')
def handle_terminal_input(data):
    session_id = data.get('session_id', 'default')
    input_data = data.get('input', '')
    
    if session_id in terminal_sessions:
        fd = terminal_sessions[session_id]['fd']
        try:
            os.write(fd, input_data.encode())
        except:
            pass

@socketio.on('terminal_resize')
def handle_terminal_resize(data):
    session_id = data.get('session_id', 'default')
    rows = data.get('rows', 24)
    cols = data.get('cols', 80)
    
    if session_id in terminal_sessions:
        fd = terminal_sessions[session_id]['fd']
        try:
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        except:
            pass

@socketio.on('stop_terminal')
def handle_stop_terminal(data):
    session_id = data.get('session_id', 'default')
    
    if session_id in terminal_sessions:
        session = terminal_sessions.pop(session_id)
        try:
            os.close(session['fd'])
            os.kill(session['pid'], 9)
            os.waitpid(session['pid'], 0)
        except:
            pass

# --- DOCKER ROUTES ---
import docker as docker_sdk

@app.route('/docker')
@requires_permission('docker', 'view')
def docker_page():
    return render_template('docker.html')

@app.route('/api/docker/containers')
def docker_containers():
    try:
        client = docker_sdk.from_env()
        containers = client.containers.list(all=True)
        
        result = []
        for c in containers:
            result.append({
                'id': c.short_id,
                'name': c.name,
                'image': c.image.tags[0] if c.image.tags else c.image.short_id,
                'status': c.status,
                'created': c.attrs['Created'][:19].replace('T', ' ')
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/docker/<container_id>/stats')
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
def docker_action(container_id):
    try:
        data = request.json
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
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/docker/<container_id>/logs')
def docker_logs(container_id):
    try:
        lines = request.args.get('lines', 200, type=int)
        
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
    return jsonify({'mqtt': safe_mqtt})

@app.route('/api/settings')
@login_required
def get_settings():
    return jsonify(load_app_settings())

@app.route('/api/settings', methods=['POST'])
@requires_permission('settings', 'full')
def update_settings():
    settings = load_app_settings()
    data = request.json
    
    # Update each section if provided
    for section in ['general', 'appearance', 'monitoring', 'alerts', 'integrations', 'mqtt', 'services']:
        if section in data:
            if section in settings and isinstance(settings[section], dict) and isinstance(data[section], dict):
                settings[section] = {**settings[section], **data[section]}
            else:
                # For lists like 'services', just replace entirely
                settings[section] = data[section]
    
    save_app_settings(settings)
    audit_log('SETTINGS_CHANGED', f"App settings updated", session.get('username', 'unknown'))
    return jsonify({'success': True})

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
    audit_log('SETTINGS_RESET', 'Settings reset to defaults', session.get('username', 'unknown'))
    return jsonify({'success': True})

# --- CASAOS ROUTES ---
CASAOS_URL = 'http://host.docker.internal:9999'
CASAOS_ALLOWED_IPS = {}  # {ip: expiry_time}

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

def run_host_command(cmd_list):
    """
    Run a command on the HOST system.
    If running in Docker (detected by existence of /.dockerenv), use nsenter.
    Otherwise run directly.
    """
    # Check if inside Docker
    in_docker = os.path.exists('/.dockerenv')
    
    if in_docker:
        # Wrap command with nsenter to run on host (PID 1 namespace)
        # Requires privileged: true in docker-compose
        full_cmd = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i'] + cmd_list
    else:
        full_cmd = cmd_list
        
    return subprocess.run(full_cmd, capture_output=True, text=True)

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

@app.route('/api/services/control', methods=['POST'])
@requires_permission('services', 'limited')
def service_control():
    """Start/Stop/Restart a service"""
    data = request.json
    service_id = data.get('service')
    action = data.get('action') # start, stop, restart
    
    settings = load_app_settings()
    services_config = settings.get('services', [])
    
    # Validate if legitimate service
    valid_ids = [s.get('id') for s in services_config]
    
    if service_id not in valid_ids:
        # Allow admin to control any service technically, but safest to restrict
        # For flexibility, let's allow it but log it warningly if not in list
        pass 

    if action not in ['start', 'stop', 'restart']:
        return jsonify({'error': 'Invalid action'}), 400
        
    try:
        run_host_command(['systemctl', action, service_id])
        audit_log('SERVICE_CONTROL', f"{action.title()} service {service_id}", session.get('username'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
                'top_processes': top_cpu
            },
            'memory': {
                'details': mem_details,
                'top_processes': top_mem
            },
            'storage': {
                'partitions': partitions,
                'io': io_stats
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
            'interfaces': []
        }
        
        nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
        
        # 1. Get Hostname
        try:
            res = subprocess.run(nsenter + ['hostname'], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                result['hostname'] = res.stdout.strip()
        except:
            result['hostname'] = 'Unknown'

        # 2. Get Interfaces & IP (via ip -j addr)
        try:
            # Try JSON format first (modern iproute2)
            res = subprocess.run(nsenter + ['ip', '-j', 'addr'], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                addr_data = json.loads(res.stdout)
                
                for iface in addr_data:
                    name = iface.get('ifname', 'unknown')
                    if name == 'lo': continue
                    
                    iface_info = {
                        'name': name,
                        'ip': '',
                        'mac': iface.get('address', ''),
                        'type': 'ethernet',
                        'status': iface.get('operstate', 'unknown').lower()
                    }
                    
                    # Heuristic Type
                    lower_name = name.lower()
                    if 'wlan' in lower_name or 'wifi' in lower_name or 'wl' in lower_name:
                        iface_info['type'] = 'wifi'
                    elif 'tun' in lower_name or 'wg' in lower_name or 'zt' in lower_name:
                        iface_info['type'] = 'vpn'
                    elif 'br' in lower_name or 'docker' in lower_name or 'veth' in lower_name:
                        iface_info['type'] = 'virtual'
                        
                    # Get IPs
                    for addr in iface.get('addr_info', []):
                        if addr.get('family') == 'inet':
                            ip = addr.get('local')
                            iface_info['ip'] = ip
                            # Determine primary IP (heuristic: global scope, not docker/br)
                            if not result['primary_ip'] and iface_info['type'] in ['ethernet', 'wifi']:
                                result['primary_ip'] = ip
                                result['primary_mac'] = iface_info['mac']
                    
                    result['interfaces'].append(iface_info)
            else:
                # Fallback implementation if needed (omitted for brevity, expecting modern host)
                pass
        except Exception as e:
            print(f"Error getting interfaces: {e}")

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
        import re
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
            
            # Replace old hostname references
            old_hostname = socket.gethostname()
            hosts_content = hosts_content.replace(old_hostname, new_hostname)
            
            with open('/etc/hosts', 'w') as f:
                f.write(hosts_content)
        except Exception as e:
            # Not critical, continue
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
        
        # Validasi IP
        import re
        ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
        for dns in dns_servers:
            if not ip_pattern.match(dns):
                return jsonify({'error': f'Format DNS tidak valid: {dns}'}), 400
        
        # Write to resolv.conf
        # Note: This might be overwritten by DHCP or networkmanager
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
    """Mendapatkan daftar disk dan partisi"""
    try:
        disks = []
        total_size = 0
        total_used = 0
        total_free = 0
        disk_count = 0
        
        # Track devices we've already counted (to avoid duplicates from bind mounts)
        counted_devices = set()
        
        # Get disk partitions
        partitions = psutil.disk_partitions(all=False)
        
        for part in partitions:
            try:
                # Skip if we already counted this device
                if part.device in counted_devices:
                    continue
                
                # Skip special mounts that are bind mounts of the same partition
                # These typically have paths like /host/root/xxx or /app/xxx
                if '/host/root/' in part.mountpoint and part.mountpoint != '/host/root':
                    continue
                if part.mountpoint.startswith('/etc/') or part.mountpoint.startswith('/app/'):
                    # Check if this is a bind mount (same device as root)
                    root_device = None
                    for p in partitions:
                        if p.mountpoint in ['/', '/host/root']:
                            root_device = p.device
                            break
                    if root_device and part.device == root_device:
                        continue
                
                usage = psutil.disk_usage(part.mountpoint)
                
                # Detect disk type
                disk_type = 'hdd'
                device_name = part.device.split('/')[-1] if '/' in part.device else part.device
                
                # Detect media type
                if 'mmc' in part.device.lower():
                    disk_type = 'sd'  # SD Card / eMMC
                elif 'usb' in part.device.lower() or 'removable' in part.opts.lower():
                    disk_type = 'usb'
                elif 'nvme' in part.device.lower():
                    disk_type = 'ssd'
                
                disk_info = {
                    'name': device_name,
                    'device': part.device,
                    'mountpoint': part.mountpoint,
                    'fstype': part.fstype,
                    'type': disk_type,
                    'is_partition': True,
                    'mounted': True,
                    'size': format_bytes(usage.total),
                    'used': format_bytes(usage.used),
                    'free': format_bytes(usage.free),
                    'usage_percent': usage.percent
                }
                
                disks.append(disk_info)
                counted_devices.add(part.device)
                total_size += usage.total
                total_used += usage.used
                total_free += usage.free
                disk_count += 1
                
            except (PermissionError, OSError):
                # Skip partitions we can't access
                continue
        
        # Try to get unmounted partitions from lsblk
        try:
            lsblk_result = subprocess.run(
                ['lsblk', '-J', '-o', 'NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE'],
                capture_output=True, text=True, timeout=10
            )
            if lsblk_result.returncode == 0:
                lsblk_data = json.loads(lsblk_result.stdout)
                for device in lsblk_data.get('blockdevices', []):
                    # Check children (partitions)
                    for child in device.get('children', []):
                        if child.get('type') == 'part' and not child.get('mountpoint'):
                            # Unmounted partition
                            existing = [d for d in disks if child['name'] in d['device']]
                            if not existing:
                                disks.append({
                                    'name': child['name'],
                                    'device': f"/dev/{child['name']}",
                                    'mountpoint': None,
                                    'fstype': child.get('fstype', ''),
                                    'type': 'hdd',
                                    'is_partition': True,
                                    'mounted': False,
                                    'size': child.get('size', ''),
                                    'used': None,
                                    'free': None,
                                    'usage_percent': 0
                                })
        except Exception:
            pass
        
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


# ============ BACKUP & RESTORE ============
BACKUP_DIR = os.path.join(DATA_DIR, 'backups')
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

@app.route('/backup')
@login_required
@admin_required
def backup_page():
    """Halaman backup & restore"""
    return render_template('backup.html')

@app.route('/api/backup/list')
@login_required
def list_backups():
    """Mendapatkan daftar backup yang tersedia"""
    try:
        backups = []
        
        if os.path.exists(BACKUP_DIR):
            for filename in os.listdir(BACKUP_DIR):
                if filename.endswith('.tar.gz'):
                    filepath = os.path.join(BACKUP_DIR, filename)
                    stat = os.stat(filepath)
                    
                    # Parse nama dan tanggal dari filename
                    # Format: backup_YYYY-MM-DD_HH-MM-SS_nama.tar.gz
                    parts = filename.replace('.tar.gz', '').split('_')
                    if len(parts) >= 3:
                        date_str = f"{parts[1]} {parts[2].replace('-', ':')}"
                        name = '_'.join(parts[3:]) if len(parts) > 3 else 'Backup'
                    else:
                        date_str = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                        name = filename.replace('.tar.gz', '')
                    
                    backups.append({
                        'id': filename,
                        'name': name or 'Backup',
                        'filename': filename,
                        'date': date_str,
                        'size': format_bytes(stat.st_size),
                        'timestamp': stat.st_mtime
                    })
        
        # Urutkan dari terbaru
        backups.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({'backups': backups})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup/create', methods=['POST'])
@login_required
@admin_required
def create_backup():
    """Membuat backup baru"""
    try:
        import tarfile
        
        data = request.json
        custom_name = data.get('name', '').strip()
        include_config = data.get('include_config', True)
        include_docker = data.get('include_docker', True)
        include_users = data.get('include_users', False)
        
        # Generate nama file
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        safe_name = ''.join(c for c in custom_name if c.isalnum() or c in '-_') if custom_name else ''
        filename = f"backup_{timestamp}_{safe_name}.tar.gz" if safe_name else f"backup_{timestamp}.tar.gz"
        filepath = os.path.join(BACKUP_DIR, filename)
        
        # Buat tarball
        with tarfile.open(filepath, 'w:gz') as tar:
            # Backup konfigurasi
            if include_config:
                settings_file = os.path.join(DATA_DIR, 'settings.json')
                if os.path.exists(settings_file):
                    tar.add(settings_file, arcname='settings.json')
                
                security_file = os.path.join(BASE_DIR, 'security_config.json')
                if os.path.exists(security_file):
                    tar.add(security_file, arcname='security_config.json')
            
            # Backup docker compose
            if include_docker:
                compose_file = os.path.join(BASE_DIR, 'docker-compose.yml')
                if os.path.exists(compose_file):
                    tar.add(compose_file, arcname='docker-compose.yml')
            
            # Backup data pengguna
            if include_users:
                users_db = os.path.join(DATA_DIR, 'users.db')
                if os.path.exists(users_db):
                    tar.add(users_db, arcname='users.db')
        
        audit_log('BACKUP_CREATED', f'Backup dibuat: {filename}', session.get('username'))
        
        return jsonify({
            'success': True,
            'filename': filename,
            'message': 'Backup berhasil dibuat'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup/download/<backup_id>')
@login_required
def download_backup(backup_id):
    """Download file backup"""
    try:
        # Sanitasi nama file
        if '..' in backup_id or '/' in backup_id or '\\' in backup_id:
            return jsonify({'error': 'Invalid backup ID'}), 400
        
        filepath = os.path.join(BACKUP_DIR, backup_id)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Backup tidak ditemukan'}), 404
        
        from flask import send_file
        return send_file(filepath, as_attachment=True, download_name=backup_id)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup/restore', methods=['POST'])
@login_required
@admin_required
def restore_backup():
    """Restore dari backup"""
    try:
        import tarfile
        
        data = request.json
        backup_id = data.get('id', '')
        
        # Sanitasi nama file
        if '..' in backup_id or '/' in backup_id or '\\' in backup_id:
            return jsonify({'error': 'Invalid backup ID'}), 400
        
        filepath = os.path.join(BACKUP_DIR, backup_id)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Backup tidak ditemukan'}), 404
        
        # Ekstrak backup
        with tarfile.open(filepath, 'r:gz') as tar:
            for member in tar.getmembers():
                # Restore ke lokasi yang sesuai
                if member.name == 'settings.json':
                    tar.extract(member, DATA_DIR)
                elif member.name == 'security_config.json':
                    tar.extract(member, BASE_DIR)
                elif member.name == 'docker-compose.yml':
                    tar.extract(member, BASE_DIR)
                elif member.name == 'users.db':
                    tar.extract(member, DATA_DIR)
        
        audit_log('BACKUP_RESTORED', f'Backup di-restore: {backup_id}', session.get('username'))
        
        return jsonify({
            'success': True,
            'message': 'Backup berhasil di-restore'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup/delete/<backup_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_backup(backup_id):
    """Menghapus backup"""
    try:
        # Sanitasi nama file
        if '..' in backup_id or '/' in backup_id or '\\' in backup_id:
            return jsonify({'error': 'Invalid backup ID'}), 400
        
        filepath = os.path.join(BACKUP_DIR, backup_id)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Backup tidak ditemukan'}), 404
        
        os.remove(filepath)
        
        audit_log('BACKUP_DELETED', f'Backup dihapus: {backup_id}', session.get('username'))
        
        return jsonify({
            'success': True,
            'message': 'Backup berhasil dihapus'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# ==========================================


# ============ SMB/SAMBA FILE SHARING ============
# Path ke config Samba di host (mounted via docker-compose)
SMB_CONFIG_FILE = '/host/root/etc/samba/smb.conf'

@app.route('/sharing')
@login_required
@admin_required
def sharing_page():
    """Halaman berbagi file SMB"""
    return render_template('sharing.html')

@app.route('/api/smb/status')
@login_required
def get_smb_status():
    """Mendapatkan status Samba"""
    try:
        installed = False
        running = False
        
        # Method 1: Cek via nsenter ke host (jika container privileged)
        try:
            result = subprocess.run(
                ['nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'which', 'smbd'],
                capture_output=True, text=True, timeout=5
            )
            installed = result.returncode == 0
            
            if installed:
                status = subprocess.run(
                    ['nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'systemctl', 'is-active', 'smbd'],
                    capture_output=True, text=True, timeout=5
                )
                running = status.stdout.strip() == 'active'
        except:
            pass
        
        # Method 2: Fallback - cek file config di host (jika di-mount)
        if not installed:
            host_smb_conf = '/host/root/etc/samba/smb.conf'
            if os.path.exists(host_smb_conf):
                installed = True
                # Cek apakah smbd proses berjalan
                try:
                    result = subprocess.run(['pgrep', '-x', 'smbd'], capture_output=True, text=True)
                    running = result.returncode == 0
                except:
                    pass
        
        # Method 3: Cek di dalam container (untuk testing lokal)
        if not installed:
            result = subprocess.run(['which', 'smbd'], capture_output=True, text=True)
            installed = result.returncode == 0
            if installed:
                status = subprocess.run(['systemctl', 'is-active', 'smbd'], capture_output=True, text=True)
                running = status.stdout.strip() == 'active'
        
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
        
        return jsonify({
            'installed': installed,
            'running': running,
            'server_ip': server_ip
        })
    except Exception as e:
        return jsonify({'error': str(e), 'installed': False, 'running': False}), 500

@app.route('/api/smb/shares')
@login_required
def get_smb_shares():
    """Mendapatkan daftar share aktif"""
    try:
        shares = []
        
        if os.path.exists(SMB_CONFIG_FILE):
            with open(SMB_CONFIG_FILE, 'r') as f:
                content = f.read()
            
            # Parse smb.conf untuk mencari shares
            import re
            # Match [sharename] sections (exclude global, homes, printers)
            pattern = r'\[([^\]]+)\]\s*\n([^[]*)'
            matches = re.findall(pattern, content)
            
            for name, config in matches:
                if name.lower() in ['global', 'homes', 'printers', 'print$']:
                    continue
                
                # Parse path dari config
                path_match = re.search(r'path\s*=\s*(.+)', config)
                path = path_match.group(1).strip() if path_match else ''
                
                shares.append({
                    'name': name,
                    'path': path
                })
        
        return jsonify({'shares': shares})
    except Exception as e:
        return jsonify({'error': str(e), 'shares': []}), 500

@app.route('/api/smb/share/add', methods=['POST'])
@login_required
@admin_required
def add_smb_share():
    """Menambahkan share baru"""
    try:
        data = request.json
        name = data.get('name', '').strip()
        path = data.get('path', '').strip()
        description = data.get('description', '').strip()
        is_public = data.get('public', True)
        writable = data.get('writable', True)
        
        if not name or not path:
            return jsonify({'error': 'Nama dan path harus diisi'}), 400
        
        # Validasi nama (alphanumeric only)
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            return jsonify({'error': 'Nama hanya boleh huruf, angka, underscore, dan dash'}), 400
        
        # Cek path exists
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except:
                return jsonify({'error': f'Path tidak ada dan tidak bisa dibuat: {path}'}), 400
        
        # Buat konfigurasi share
        share_config = f"""
[{name}]
   comment = {description or name}
   path = {path}
   browseable = yes
   read only = {'no' if writable else 'yes'}
   guest ok = {'yes' if is_public else 'no'}
   create mask = 0755
   directory mask = 0755
"""
        
        # Append ke smb.conf
        with open(SMB_CONFIG_FILE, 'a') as f:
            f.write(share_config)
        
        # Reload Samba
        subprocess.run(['systemctl', 'reload', 'smbd'], capture_output=True)
        
        audit_log('SMB_SHARE_ADDED', f'Share ditambahkan: {name} -> {path}', session.get('username'))
        
        return jsonify({'success': True, 'message': 'Share berhasil ditambahkan'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/smb/share/remove', methods=['DELETE'])
@login_required
@admin_required
def remove_smb_share():
    """Menghapus share"""
    try:
        data = request.json
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'error': 'Nama share diperlukan'}), 400
        
        if not os.path.exists(SMB_CONFIG_FILE):
            return jsonify({'error': 'File konfigurasi Samba tidak ditemukan'}), 404
        
        with open(SMB_CONFIG_FILE, 'r') as f:
            content = f.read()
        
        # Hapus section share
        import re
        pattern = rf'\[{re.escape(name)}\][^\[]*'
        new_content = re.sub(pattern, '', content)
        
        with open(SMB_CONFIG_FILE, 'w') as f:
            f.write(new_content)
        
        # Reload Samba
        subprocess.run(['systemctl', 'reload', 'smbd'], capture_output=True)
        
        audit_log('SMB_SHARE_REMOVED', f'Share dihapus: {name}', session.get('username'))
        
        return jsonify({'success': True, 'message': 'Share berhasil dihapus'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/smb/control', methods=['POST'])
@login_required
@admin_required
def control_smb():
    """Start/stop Samba service"""
    try:
        data = request.json
        action = data.get('action', '')
        
        if action not in ['start', 'stop', 'restart']:
            return jsonify({'error': 'Action tidak valid'}), 400
        
        result = subprocess.run(['systemctl', action, 'smbd'], capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return jsonify({'error': f'Gagal {action} Samba: {result.stderr}'}), 500
        
        audit_log('SMB_CONTROL', f'Samba di-{action}', session.get('username'))
        
        return jsonify({'success': True, 'message': f'Samba berhasil di-{action}'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/smb/install', methods=['POST'])
@login_required
@admin_required
def install_smb():
    """Install Samba"""
    try:
        # Update package list first
        update_result = subprocess.run(
            ['apt-get', 'update'],
            capture_output=True, text=True, timeout=120
        )
        
        # Install samba
        result = subprocess.run(
            ['apt-get', 'install', '-y', 'samba'],
            capture_output=True, text=True, timeout=300
        )
        
        if result.returncode != 0:
            return jsonify({'error': f'Gagal install Samba: {result.stderr}'}), 500
        
        # Enable dan start service
        subprocess.run(['systemctl', 'enable', 'smbd'], capture_output=True)
        subprocess.run(['systemctl', 'start', 'smbd'], capture_output=True)
        
        audit_log('SMB_INSTALLED', 'Samba berhasil diinstall', session.get('username'))
        
        return jsonify({'success': True, 'message': 'Samba berhasil diinstall'})
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout saat install (> 5 menit)'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# ================================================


# ============ VPN (WIREGUARD) ============
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
    """Mendapatkan status WireGuard"""
    try:
        # Cek apakah WireGuard terinstall di HOST (via nsenter)
        nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
        result = subprocess.run(nsenter + ['which', 'wg'], capture_output=True, text=True)
        installed = result.returncode == 0
        
        running = False
        server_ip = ''
        port = '51820'
        client_count = 0
        
        if installed:
            # Cek apakah interface aktif di HOST
            status = subprocess.run(nsenter + ['wg', 'show', WG_INTERFACE], capture_output=True, text=True)
            running = status.returncode == 0
            
            if running:
                # Parse port dari output
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
        except:
            pass
        
        return jsonify({
            'installed': installed,
            'running': running,
            'server_ip': server_ip,
            'port': port,
            'client_count': client_count
        })
    except Exception as e:
        return jsonify({'error': str(e), 'installed': False}), 500

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

@app.route('/api/store/catalog')
@login_required
def get_app_catalog():
    """Mendapatkan katalog aplikasi (Default + Custom)"""
    try:
        catalog = []
        
        # 1. Load Default Catalog
        target = CATALOG_FILE
        if not os.path.exists(CATALOG_FILE):
             fallback_path = os.path.join(os.getcwd(), 'data', 'app_catalog.json')
             if os.path.exists(fallback_path):
                 target = fallback_path
        
        if os.path.exists(target):
            with open(target, 'r') as f:
                catalog = json.load(f)
                
        # 2. Load User Custom Catalog
        if os.path.exists(USER_CATALOG_FILE):
            try:
                with open(USER_CATALOG_FILE, 'r') as f:
                    user_apps = json.load(f)
                    # Mark aliases as custom for UI distinction if needed
                    for app in user_apps:
                        app['category'] = 'Custom' # Force category or keep user defined
                        app['is_custom'] = True
                    catalog.extend(user_apps)
            except:
                pass # Ignore corrupt user file
            
        return jsonify({'catalog': catalog})
    except Exception as e:
        return jsonify({'error': str(e), 'catalog': []}), 500

@app.route('/api/store/installed')
@login_required
def get_installed_apps():
    """Mendapatkan detail aplikasi yang sudah terinstall (Status & Ports)"""
    try:
        # Get detailed container info: Name, State, Ports
        # Format: Name|State|Ports
        result = subprocess.run(['docker', 'ps', '-a', '--format', '{{.Names}}|{{.State}}|{{.Ports}}'], capture_output=True, text=True)
        if result.returncode != 0:
             return jsonify({'error': 'Docker command failed', 'installed': []}), 500
             
        lines = result.stdout.strip().split('\n')
        
        container_map = {}
        for line in lines:
            if not line.strip(): continue
            parts = line.split('|')
            if len(parts) >= 3:
                name = parts[0].strip()
                state = parts[1].strip() # running, exited, created
                ports_str = parts[2].strip()
                
                # Parse Ports
                # Example: 0.0.0.0:8096->8096/tcp, :::8096->8096/tcp
                ports_list = []
                if ports_str:
                    for p in ports_str.split(','):
                        p = p.strip()
                        # Match '0.0.0.0:HOST_PORT->CONTAINER_PORT/PROTO'
                        # Broad regex or simple split
                        if '->' in p:
                            host_part, container_part = p.split('->')
                            # clean host part '0.0.0.0:8096' -> 8096
                            if ':' in host_part:
                                host_port = host_part.split(':')[-1]
                            else:
                                host_port = host_part
                            
                            # clean container part '8096/tcp'
                            if '/' in container_part:
                                container_port, proto = container_part.split('/')
                            else:
                                container_port = container_part
                                proto = 'tcp'
                                
                            ports_list.append({
                                'host': host_port,
                                'container': container_port,
                                'protocol': proto
                            })
                            
                container_map[name] = {
                    'running': (state.lower() == 'running'),
                    'state': state,
                    'ports': ports_list
                }

        installed = []
        
        # Load Catalogs to find potential App IDs
        full_catalog = []
        if os.path.exists(CATALOG_FILE):
             with open(CATALOG_FILE, 'r') as f: full_catalog.extend(json.load(f))
        if os.path.exists(USER_CATALOG_FILE):
             with open(USER_CATALOG_FILE, 'r') as f: full_catalog.extend(json.load(f))
             
        for app in full_catalog:
            app_id = app['id']
            # Check eka_ prefixed first (standard), then raw id (custom legacy?)
            container_name = f"eka_{app_id}"
            info = container_map.get(container_name) or container_map.get(app_id)
            
            if info:
                installed.append({
                    'id': app_id,
                    'running': info['running'],
                    'ports': info['ports']
                })
                
        return jsonify({'installed': installed})
    except Exception as e:
        print(f"Error checking installed apps: {e}")
        return jsonify({'error': str(e), 'installed': []}), 500


@app.route('/api/store/install', methods=['POST'])
@login_required
@admin_required
def install_app_endpoint():
    """Install app from store (Async with Logs)"""
    data = request.json
    app_id = data.get('app_id')
    config = data.get('config', {})
    
    if not app_id:
        return jsonify({'error': 'App ID required'}), 400

    # Start Background Thread
    username = session.get('username')
    thread = threading.Thread(target=install_worker, args=(app_id, config, username))
    thread.start()

    return jsonify({'success': True, 'message': 'Instalasi dimulai... Cek log untuk progress.'})

def install_worker(app_id, config, username):
    """Background worker for installation"""
    room = f"install_{app_id}"
    try:
        print(f"DEBUG: install_worker started for {app_id}")
        socketio.emit('install_log', {'app_id': app_id, 'message': f"Menyiapkan instalasi {app_id}...", 'type': 'info'})
        
        # Prepare params
        if app_id != 'custom':
            # Always force lookup from server catalog to ensure latest image/config is used
            found = None
            try:
                if os.path.exists(CATALOG_FILE):
                    with open(CATALOG_FILE) as f:
                        for a in json.load(f):
                             if a['id'] == app_id: found = a; break
            except: pass
            
            if not found:
                 socketio.emit('install_log', {'app_id': app_id, 'message': "App definition not found in catalog!", 'type': 'error'})
                 socketio.emit('install_complete', {'app_id': app_id, 'status': 'error'})
                 return
            
            image = found['image']
            name = app_id
            
            # HOTFIX: Force linuxserver for phpmyadmin on ARM
            if app_id == 'phpmyadmin':
                image = 'linuxserver/phpmyadmin:latest'
        else:
            # Custom App
            image = config.get('image')
            name = config.get('name')
            
            if not image or not name:
                 socketio.emit('install_log', {'app_id': app_id, 'message': "Custom app missing config", 'type': 'error'})
                 socketio.emit('install_complete', {'app_id': app_id, 'status': 'error'})
                 return
        
        # Docker Client
        try:
            client = docker.from_env()
            old = client.containers.get(name)
            if old:
                socketio.emit('install_log', {'app_id': app_id, 'message': "Menghapus container lama...", 'type': 'warning'})
                old.remove(force=True)
        except docker.errors.NotFound:
            pass
        
        # Pull Image
        print(f"DEBUG: Resolved image for {app_id} is {image}")
        socketio.emit('install_log', {'app_id': app_id, 'message': f"Target Image: {image}", 'type': 'info'})
        socketio.emit('install_log', {'app_id': app_id, 'message': "Downloading image from Docker Hub... (This may take a while)", 'type': 'info'})

        # Pull Image with Progress
        socketio.emit('install_log', {'app_id': app_id, 'message': f"Pulling image {image}...", 'type': 'info'})
        
        try:
            # Use low-level API for progress stream
            layers = {}
            for line in client.api.pull(image, stream=True, decode=True):
                status = line.get('status')
                progress_detail = line.get('progressDetail', {})
                id_ = line.get('id')
                
                # Emit Logs for non-progress status updates
                if status and 'Downloading' not in status and 'Extracting' not in status and 'Pulling fs' not in status:
                     # Throttling status logs to avoid spam
                     pass

                if id_ and (status == 'Downloading' or status == 'Extracting'):
                    current = progress_detail.get('current', 0)
                    total = progress_detail.get('total', 1)
                    layers[id_] = {'current': current, 'total': total, 'status': status}
                    
                    # Calculate Total Progress
                    total_bytes = 0
                    current_bytes = 0
                    for lid, data in layers.items():
                        total_bytes += data['total']
                        current_bytes += data['current']
                    
                    if total_bytes > 0:
                        overall_percent = (current_bytes / total_bytes) * 100
                        # Clamp to 99% until actually done
                        if overall_percent > 99: overall_percent = 99
                        socketio.emit('install_progress', {'app_id': app_id, 'percent': overall_percent, 'message': f"{status} {id_}..."})
                
                if 'error' in line:
                    raise Exception(line['error'])
            
            socketio.emit('install_progress', {'app_id': app_id, 'percent': 100, 'message': "Image pulled successfully"})
                    
        except Exception as e:
            socketio.emit('install_log', {'app_id': app_id, 'message': f"Gagal download image: {str(e)}", 'type': 'error'})
            socketio.emit('install_complete', {'app_id': app_id, 'status': 'error'})
            return

        socketio.emit('install_log', {'app_id': app_id, 'message': "Image ready. Configuring container...", 'type': 'info'})

        # Prepare Config (Ports, Volumes, Env) - reused logic
        ports = {}
        if config.get('ports'):
            for p in config.get('ports'):
                c_port = f"{p['container']}/{p.get('protocol', 'tcp')}"
                ports[c_port] = int(p['host'])
        
        vols_dict = {}
        if config.get('volumes'):
            for v in config.get('volumes'):
                host_path = v['bind']
                if host_path.startswith('/'):
                     internal_path = os.path.join('/host/root', host_path.lstrip('/'))
                     if not os.path.exists(internal_path):
                         try: os.makedirs(internal_path, exist_ok=True)
                         except: pass
                vols_dict[host_path] = {'bind': v['container'], 'mode': 'rw'}

        env_vars = {}
        if config.get('env'):
            for e in config.get('env'):
                env_vars[e['key']] = e['value']
        
        # Run
        container = client.containers.run(
            image,
            name=name,
            ports=ports,
            volumes=vols_dict,
            environment=env_vars,
            network_mode=config.get('network_mode', 'bridge'),
            restart_policy={"Name": "unless-stopped"},
            detach=True
        )
        
        # Save Custom
        if app_id == 'custom':
            user_apps = []
            if os.path.exists(USER_CATALOG_FILE):
                try:
                    with open(USER_CATALOG_FILE) as f:
                        user_apps = json.load(f)
                except:
                    pass
            
            new_entry = {
                "id": f"custom_{int(time.time())}",
                "name": name,
                "description": "Custom Application",
                "category": "Custom",
                "image": image,
                "icon": "/static/icon.png",
                "ports": config.get('ports', []),
                "volumes": config.get('volumes', []),
                "env": config.get('env', []),
                "network_mode": config.get('network_mode', 'bridge')
            }
            user_apps.append(new_entry)
            with open(USER_CATALOG_FILE, 'w') as f:
                json.dump(user_apps, f, indent=4)

        audit_log('APP_INSTALL', f"Installed {name}", username)
        socketio.emit('install_log', {'app_id': app_id, 'message': "Container berhasil dijalankan!", 'type': 'success'})
        socketio.emit('install_complete', {'app_id': app_id, 'status': 'success'})
            
    except Exception as e:
        print(f"Async Install Error: {e}")
        socketio.emit('install_log', {'app_id': app_id, 'message': f"CRITICAL ERROR: {str(e)}", 'type': 'error'})
        socketio.emit('install_complete', {'app_id': app_id, 'status': 'error', 'error': str(e)})



@app.route('/api/store/manage', methods=['POST'])
@login_required
@admin_required
def manage_app_endpoint():
    """Manage app (start/stop/uninstall)"""
    try:
        data = request.json
        app_id = data.get('app_id')
        action = data.get('action') # start, stop, restart, uninstall
        
        if not app_id or not action:
            return jsonify({'error': 'Invalid params'}), 400
            
        client = docker.from_env()
        
        # Determine container name
        # Try finding by name "eka_{id}" or just id if custom
        container = None
        try:
             container = client.containers.get(f"eka_{app_id}")
        except:
             try:
                 container = client.containers.get(app_id) # maybe custom name
             except:
                 pass
        
        # If still not found, try searching by image or loosely?
        if not container:
             # Try catalog lookup to be sure of container name?
             # For now assume 'eka_{app_id}' is standard
             return jsonify({'error': 'Container not found'}), 404
             
        if action == 'start':
            container.start()
        elif action == 'stop':
            container.stop()
        elif action == 'restart':
            container.restart()
        elif action == 'uninstall':
            container.stop()
            container.remove()
            # Remove from user_apps.json if there
            if os.path.exists(USER_CATALOG_FILE):
                try:
                    with open(USER_CATALOG_FILE, 'r') as f: apps = json.load(f)
                    apps = [a for a in apps if a['id'] != app_id and a['name'] != app_id] # simplistic filter
                    with open(USER_CATALOG_FILE, 'w') as f: json.dump(apps, f, indent=4)
                except: pass
                
        audit_log('APP_MANAGE', f"{action.title()} app {app_id}", session.get('username'))
        return jsonify({'success': True})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

SYSTEM_APPS = [
    {"id": "files", "name": "Files", "icon": "fa-solid fa-folder-open", "color": "linear-gradient(135deg, #FF9966, #FF5E62)", "url": "/files"},
    {"id": "terminal", "name": "Terminal", "icon": "fa-solid fa-terminal", "color": "linear-gradient(135deg, #2d3436, #636e72)", "url": "/terminal"},
    {"id": "docker", "name": "Docker", "icon": "fa-brands fa-docker", "color": "linear-gradient(135deg, #2496ed, #0db7ed)", "url": "/docker"},
    {"id": "metrics", "name": "Metrics", "icon": "fa-solid fa-chart-line", "color": "linear-gradient(135deg, #f7971e, #ffd200)", "url": "/metrics"},
    {"id": "security", "name": "Security", "icon": "fa-solid fa-shield-halved", "color": "linear-gradient(135deg, #833ab4, #fd1d1d)", "url": "/security"},
    {"id": "network", "name": "Network", "icon": "fa-solid fa-network-wired", "color": "linear-gradient(135deg, #11998e, #38ef7d)", "url": "/network"},
    {"id": "storage", "name": "Storage", "icon": "fa-solid fa-hard-drive", "color": "linear-gradient(135deg, #667eea, #764ba2)", "url": "/storage"},
    {"id": "backup", "name": "Backup", "icon": "fa-solid fa-box-archive", "color": "linear-gradient(135deg, #f093fb, #f5576c)", "url": "/backup"},
    {"id": "sharing", "name": "Sharing", "icon": "fa-solid fa-share-nodes", "color": "linear-gradient(135deg, #a18cd1, #fbc2eb)", "url": "/sharing"},
    {"id": "vpn", "name": "VPN", "icon": "fa-solid fa-shield-halved", "color": "linear-gradient(135deg, #ff9a9e, #fecfef)", "url": "/vpn"},
    {"id": "store", "name": "App Store", "icon": "fa-solid fa-store", "color": "linear-gradient(135deg, #FF6B6B, #556270)", "url": "/store"},
    {"id": "settings", "name": "Settings", "icon": "fa-solid fa-gear", "color": "linear-gradient(135deg, #36D1DC, #5B86E5)", "url": "/settings"}
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
                default_catalog = json.load(f).get('apps', [])
        
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
                
                all_items.append(dashboard_item)

    except Exception as e:
        print("Error fetching installed apps for dashboard:", e)
    
    # 3. Apply Order
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

    return jsonify({"items": all_items})

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

@login_required
@admin_required
def install_app():
    """Install aplikasi dari store dengan konfigurasi custom atau 'custom install' murni"""
    try:
        data = request.json
        app_id = data.get('app_id')
        custom_config = data.get('config')
        
        is_custom_install = (app_id == 'custom')
        
        if is_custom_install:
            # Generate ID and use config as source of truth
            if not custom_config or not custom_config.get('name') or not custom_config.get('image'):
                return jsonify({'error': 'Name and Image required for custom install'}), 400
                
            # Create a slug-like ID
            raw_name = custom_config['name']
            safe_id = "".join(x for x in raw_name if x.isalnum()).lower()
            app_id = f"custom_{safe_id}_{int(time.time())}" # Ensure unique
            
            # Construct app definition to save
            app_def = {
                "id": app_id,
                "name": raw_name,
                "image": custom_config['image'],
                "category": "Custom",
                "description": custom_config.get('description', 'Custom Application'),
                "icon": "/static/icon.png", # Default icon
                "network_mode": custom_config.get('network_mode', 'bridge'),
                "restart": "unless-stopped",
                "ports": custom_config.get('ports', []),
                "volumes": custom_config.get('volumes', []),
                "env": custom_config.get('env', [])
            }
            
            # Use this as our "app_default"
            app_default = app_def
            image = app_default['image']
            
        else:
            if not app_id:
                return jsonify({'error': 'App ID required'}), 400
                
            # Load catalog (Default + User)
            catalog = []
            if os.path.exists(CATALOG_FILE):
                with open(CATALOG_FILE, 'r') as f: catalog.extend(json.load(f))
            if os.path.exists(USER_CATALOG_FILE):
                with open(USER_CATALOG_FILE, 'r') as f: catalog.extend(json.load(f))
            
            app_default = next((a for a in catalog if a['id'] == app_id), None)
            if not app_default:
                return jsonify({'error': 'App not found in catalog'}), 404
            
            image = app_default['image']

        container_name = f"eka_{app_id}"
        
        # 1. Pull Image
        pull_cmd = ['docker', 'pull', image]
        subprocess.run(pull_cmd, check=True, timeout=600)
        
        # 2. Prepare Docker Run Command
        run_cmd = ['docker', 'run', '-d', '--name', container_name]
        
        if app_default.get('restart'):
            run_cmd.extend(['--restart', app_default['restart']])
        
        # Handling Network Mode (Priority to config if present)
        # Note: If network_mode is 'host', we shouldn't publish ports.
        net_mode = app_default.get('network_mode', 'bridge')
        if is_custom_install and custom_config.get('network_mode'):
             net_mode = custom_config.get('network_mode')
             
        if net_mode:
             run_cmd.extend(['--network', net_mode])

        # --- CONFIGURATION PRIORITY ---
        # For custom install, app_default IS the config.
        # For catalog install, merge custom_config with app_default.
        
        deploy_ports = custom_config.get('ports') if (custom_config and not is_custom_install) else app_default.get('ports', [])
        deploy_vols = custom_config.get('volumes') if (custom_config and not is_custom_install) else app_default.get('volumes', [])
        deploy_env = custom_config.get('env') if (custom_config and not is_custom_install) else app_default.get('env', [])
        
        # Ports
        for p in deploy_ports:
            if net_mode != 'host':
                host = p['host']
                container = p['container']
                proto = p.get('protocol', 'tcp')
                if host and container:
                    run_cmd.extend(['-p', f"{host}:{container}/{proto}"])
        
        # Volumes
        for v in deploy_vols:
            host_pd = v['bind']
            container_pd = v['container']
            
            real_host_path = host_pd
            if host_pd.startswith('/host/root'):
                real_host_path = host_pd.replace('/host/root', '')
                if not real_host_path.startswith('/'): real_host_path = '/' + real_host_path
            
            run_cmd.extend(['-v', f"{real_host_path}:{container_pd}"])
            
        # Env
        for e in deploy_env:
            run_cmd.extend(['-e', f"{e['key']}={e['value']}"])
            
        # Image
        run_cmd.append(image)
        
        # 3. Remove existing if any
        subprocess.run(['docker', 'rm', '-f', container_name], capture_output=True)
        
        # 4. Run
        result = subprocess.run(run_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({'error': f"Failed to start: {result.stderr}"}), 500
            
        # 5. Persist Custom App to user_apps.json
        if is_custom_install:
            user_apps = []
            if os.path.exists(USER_CATALOG_FILE):
                try:
                    with open(USER_CATALOG_FILE, 'r') as f: user_apps = json.load(f)
                except: pass
            
            # Add or Update
            # Remove validation duplicates if any (though ID is unique timestamped)
            user_apps = [a for a in user_apps if a['id'] != app_id]
            user_apps.append(app_default)
            
            os.makedirs(os.path.dirname(USER_CATALOG_FILE), exist_ok=True)
            with open(USER_CATALOG_FILE, 'w') as f:
                json.dump(user_apps, f, indent=2)
            
        audit_log('APP_INSTALL', f"Installed app {app_id} as {container_name}", session.get('username'))
        return jsonify({'success': True, 'message': f'{app_default["name"]} installed successfully'})
        
    except subprocess.CalledProcessError as e:
         return jsonify({'error': 'Failed to pull image'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/store/manage', methods=['POST'])
@login_required
@admin_required
def manage_app():
    """Manage app lifecycle (start/stop/restart/uninstall)"""
    try:
        data = request.json
        app_id = data.get('app_id')
        action = data.get('action')
        
        if not app_id or not action:
            return jsonify({'error': 'Invalid request'}), 400
            
        container_name = f"eka_{app_id}"
        
        if action == 'uninstall':
            subprocess.run(['docker', 'rm', '-f', container_name], capture_output=True)
            # Optional: Remove volumes? No, keep data safe by default.
            msg = f"{app_id} uninstalled"
            
        elif action == 'start':
            subprocess.run(['docker', 'start', container_name], capture_output=True)
            msg = f"{app_id} started"
            
        elif action == 'stop':
            subprocess.run(['docker', 'stop', container_name], capture_output=True)
            msg = f"{app_id} stopped"
            
        elif action == 'restart':
            subprocess.run(['docker', 'restart', container_name], capture_output=True)
            msg = f"{app_id} restarted"
            
        else:
            return jsonify({'error': 'Unknown action'}), 400
            
        audit_log('APP_MANAGE', f"Action {action} on {app_id}", session.get('username'))
        return jsonify({'success': True, 'message': msg})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# =========================================

# --- SYSTEM UPDATE CHECKER ---


# =========================================

# =========================================
# --- ZEROTIER API (ADDED) ---
# =========================================

@app.route('/api/zerotier/status')
@login_required
def zerotier_status():
    """Get ZeroTier status from HOST"""
    try:
        nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
        
        # Check installed on HOST
        check = subprocess.run(nsenter + ['which', 'zerotier-cli'], capture_output=True, text=True)
        installed = check.returncode == 0
        
        running = False
        networks = []
        node_id = ''
        
        if installed:
            # Check status
            status = subprocess.run(nsenter + ['zerotier-cli', 'info'], capture_output=True, text=True)
            if status.returncode == 0 and '200 info' in status.stdout:
                running = True
                try:
                    node_id = status.stdout.split()[2]
                except:
                    node_id = 'Unknown'
                
                # Get networks
                net_cmd = subprocess.run(nsenter + ['zerotier-cli', 'listnetworks'], capture_output=True, text=True)
                if net_cmd.returncode == 0:
                    lines = net_cmd.stdout.splitlines()
                    if len(lines) > 1:
                        # Skip header
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
            'running': running,
            'node_id': node_id,
            'networks': networks
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/zerotier/join', methods=['POST'])
@login_required
@admin_required
def zerotier_join():
    """Join ZeroTier network on HOST"""
    try:
        network_id = request.json.get('networkId')
        if not network_id:
            return jsonify({'error': 'Network ID required'}), 400
            
        # Validate ID (16 hex chars)
        import re
        if not re.match(r'^[0-9a-fA-F]{16}$', network_id):
             return jsonify({'error': 'Invalid Network ID format'}), 400
        
        nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
        subprocess.run(nsenter + ['zerotier-cli', 'join', network_id], check=True)
        
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
        network_id = request.json.get('networkId')
        if not network_id:
            return jsonify({'error': 'Network ID required'}), 400
            
        nsenter = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i']
        subprocess.run(nsenter + ['zerotier-cli', 'leave', network_id], check=True)
        
        audit_log('VPN', f"Left ZeroTier network {network_id}", session.get('username'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        dest_path = request.form.get('path', '/')
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
        if not path or not os.path.exists(path):
            return jsonify({'error': 'File not found'}), 404
        if os.path.isdir(path):
            return jsonify({'error': 'Cannot download directory'}), 400
            
        from flask import send_file
        return send_file(path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("Starting Development Server on http://localhost:5000")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
