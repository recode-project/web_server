"""Unit tests for Store performance optimization and LXD multi-project support.

Ran via:
    .venv/bin/python -m unittest tests/test_store_and_lxd.py -v
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as dashboard  # noqa: E402


class TestLxdMultiProject(unittest.TestCase):
    def test_lxc_cmd_default_project(self):
        cmd = dashboard._lxc_cmd(['list', '--format', 'json'], project='default')
        expected_base = ['nsenter', '-t', '1', '-m', '-u', '-i', '-n', '-p', '--', 'lxc']
        self.assertEqual(cmd[:len(expected_base)], expected_base)
        self.assertNotIn('--project', cmd)
        self.assertEqual(cmd[len(expected_base):], ['list', '--format', 'json'])

    def test_lxc_cmd_custom_project(self):
        cmd = dashboard._lxc_cmd(['list', '--format', 'json'], project='demo-project')
        expected_base = ['nsenter', '-t', '1', '-m', '-u', '-i', '-n', '-p', '--', 'lxc', '--project', 'demo-project']
        self.assertEqual(cmd[:len(expected_base)], expected_base)
        self.assertEqual(cmd[len(expected_base):], ['list', '--format', 'json'])

    def test_lxc_cmd_exec_with_project(self):
        cmd = dashboard._lxc_cmd(['exec', 'demo-project', '--', 'tailscale', 'status'], project='demo-project')
        self.assertIn('--project', cmd)
        idx = cmd.index('--project')
        self.assertEqual(cmd[idx + 1], 'demo-project')

    def test_build_terminal_command_lxd_project(self):
        cmd = dashboard._build_terminal_command(
            lxd_target='demo-project',
            start_path=None,
            lxd_project='demo-project'
        )
        self.assertIn('--project', cmd)
        idx = cmd.index('--project')
        self.assertEqual(cmd[idx + 1], 'demo-project')
        self.assertIn('demo-project', cmd)


class TestStoreSnapshotDetection(unittest.TestCase):
    def test_detect_native_host_app_from_snapshot(self):
        snapshot = (
            {'tailscaled.service', 'tailscaled', 'syncthing.service', 'syncthing', 'nginx.service'},
            {'tailscaled', 'syncthing', 'nginx'}
        )
        res = dashboard._detect_native_host_app('tailscale', host_snapshot=snapshot)
        self.assertIsNotNone(res)
        self.assertTrue(res['running'])
        self.assertTrue(res['is_native'])

    def test_detect_native_host_app_not_installed(self):
        snapshot = (
            {'nginx.service'},
            {'nginx'}
        )
        res = dashboard._detect_native_host_app('nonexistent_dummy_app', host_snapshot=snapshot)
        self.assertIsNone(res)


class TestPhysicalDrives(unittest.TestCase):
    def test_get_drives_response_structure(self):
        client = dashboard.app.test_client()
        with client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['role'] = 'owner'
            sess['username'] = 'admin'
        
        res = client.get('/api/files/drives')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('physical_disks', data)
        self.assertIn('drives', data)
        
        # Ensure /boot/efi is excluded from drives
        for d in data['drives']:
            self.assertFalse(d['mountpoint'].startswith('/boot'))


class TestMetricsTheme(unittest.TestCase):
    def test_metrics_page_renders_theme_elements(self):
        client = dashboard.app.test_client()
        with client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['role'] = 'owner'
            sess['username'] = 'admin'
        
        res = client.get('/metrics')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('class="wallpaper"', html)
        self.assertIn('metrics.js', html)
        self.assertIn('chart.js', html)
        self.assertIn('Inter', html)


class TestNetworkModule(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.app.test_client()
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['role'] = 'owner'
            sess['username'] = 'admin'

    def test_network_page_renders_clean_template(self):
        res = self.client.get('/network')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('class="wallpaper"', html)
        self.assertIn('network.js', html)
        self.assertIn('Network Manager', html)

    def test_network_info_endpoint(self):
        res = self.client.get('/api/network/info')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('interfaces', data)
        self.assertIn('hostname', data)

    def test_network_ports_endpoint(self):
        res = self.client.get('/api/network/ports')
        self.assertEqual(res.status_code, 200)
        ports = res.get_json()
        self.assertIsInstance(ports, list)

    def test_ping_endpoint_validation(self):
        res = self.client.post('/api/network/ping', json={'target': 'invalid;rm -rf'})
        self.assertEqual(res.status_code, 400)

    def test_dns_lookup_validation(self):
        res = self.client.post('/api/network/dns-lookup', json={'domain': 'invalid$(whoami)'})
        self.assertEqual(res.status_code, 400)


class TestVpnModule(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.app.test_client()
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['role'] = 'owner'
            sess['username'] = 'admin'

    def test_vpn_page_renders_clean_template(self):
        res = self.client.get('/vpn')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('class="wallpaper"', html)
        self.assertIn('vpn.js', html)
        self.assertIn('Tailscale Mesh Network', html)
        self.assertIn('WireGuard Hub', html)
        self.assertIn('ZeroTier', html)

    def test_tailscale_status_endpoint(self):
        res = self.client.get('/api/vpn/tailscale/status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('installed', data)
        self.assertIn('running', data)
        self.assertIn('peers', data)

    def test_tailscale_ping_endpoint_validation(self):
        res = self.client.post('/api/vpn/tailscale/ping', json={'target': 'invalid;rm -rf'})
        self.assertEqual(res.status_code, 400)
        err = res.get_json()
        self.assertIn('Format target tidak valid', err.get('error', ''))

    def test_tailscale_ping_empty_target(self):
        res = self.client.post('/api/vpn/tailscale/ping', json={'target': ''})
        self.assertEqual(res.status_code, 400)
        err = res.get_json()
        self.assertIn('Target tidak boleh kosong', err.get('error', ''))


class TestSharingModule(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.app.test_client()
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['role'] = 'owner'
            sess['username'] = 'admin'

    def test_sharing_page_renders_clean_template(self):
        res = self.client.get('/sharing')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('class="wallpaper"', html)
        self.assertIn('sharing.js', html)
        self.assertIn('Berbagi File (SMB / Samba)', html)
        self.assertIn('Daftar Share Aktif', html)
        self.assertIn('Sesi Klien Aktif', html)

    def test_smb_status_endpoint(self):
        res = self.client.get('/api/smb/status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('installed', data)
        self.assertIn('running', data)
        self.assertIn('server_ip', data)

    def test_smb_shares_endpoint(self):
        res = self.client.get('/api/smb/shares')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('shares', data)
        self.assertIsInstance(data['shares'], list)

    def test_smb_sessions_endpoint(self):
        res = self.client.get('/api/smb/sessions')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('sessions', data)
        self.assertIn('count', data)


class TestWebsitesModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dashboard.app.config['TESTING'] = True
        cls.client = dashboard.app.test_client()

    def setUp(self):
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['username'] = 'admin'
            sess['role'] = 'admin'

    def test_websites_page_render(self):
        res = self.client.get('/websites')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('websites.js', html)
        self.assertIn('Web & Reverse Proxy Shield', html)
        self.assertIn('Virtual Hosts', html)
        self.assertIn('Keamanan & Bot Shield', html)

    def test_web_monitor_redirect(self):
        res = self.client.get('/web_monitor')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/websites?tab=traffic', res.headers.get('Location', ''))

    def test_websites_vhosts_api(self):
        res = self.client.get('/api/websites/vhosts')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('sites', data)
        self.assertIn('total', data)
        self.assertIn('ssl_count', data)

    def test_websites_nginx_status_api(self):
        res = self.client.get('/api/websites/nginx_status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('status', data)
        self.assertIn('running', data)
        self.assertIn('version', data)

    def test_websites_traffic_api(self):
        res = self.client.get('/api/websites/traffic')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('today_requests', data)
        self.assertIn('unique_ips_count', data)
        self.assertIn('hourly_distribution', data)
        self.assertEqual(len(data['hourly_distribution']), 24)

    def test_websites_ssl_status_api(self):
        res = self.client.get('/api/websites/ssl_status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('certificates', data)
        self.assertIn('total', data)

    def test_websites_threats_blocked_ips_api(self):
        res = self.client.get('/api/websites/threats/blocked_ips')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('blocked', data)

    def test_websites_control_nginx_invalid_action(self):
        res = self.client.post('/api/websites/control_nginx', json={'action': 'invalid_xyz'})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))


class TestServicesModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dashboard.app.config['TESTING'] = True
        cls.client = dashboard.app.test_client()

    def setUp(self):
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['username'] = 'admin'
            sess['role'] = 'owner'
            sess['last_active'] = time.time()

    def test_services_page_render(self):
        res = self.client.get('/services')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('services.js', html)
        self.assertIn('Services & System Daemons', html)
        self.assertIn('Total Services', html)

    def test_system_apps_includes_services(self):
        res = self.client.get('/api/dashboard/apps')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        ids = [a['id'] for a in data.get('items', [])]
        self.assertIn('services', ids)

    def test_services_summary_api(self):
        res = self.client.get('/api/services/summary')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('total', data)
        self.assertIn('running', data)
        self.assertIn('failed', data)
        self.assertIn('system_state', data)

    def test_services_list_api(self):
        res = self.client.get('/api/services/list')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('services', data)
        self.assertIn('count', data)

    def test_services_detail_invalid_unit(self):
        res = self.client.get('/api/services/detail/invalid;command.service')
        self.assertEqual(res.status_code, 400)

    def test_services_control_invalid_action(self):
        res = self.client.post('/api/services/control', json={'unit': 'cron.service', 'action': 'destroy'})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))


class TestSystemLogsModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dashboard.app.config['TESTING'] = True
        cls.client = dashboard.app.test_client()

    def setUp(self):
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['username'] = 'admin'
            sess['role'] = 'owner'
            sess['last_active'] = time.time()

    def test_logs_page_render(self):
        res = self.client.get('/logs')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('system_logs.js', html)
        self.assertIn('System Logs & Journald Explorer', html)
        self.assertIn('Journald Explorer', html)
        self.assertIn('SSH & Auth Security', html)

    def test_system_apps_includes_system_logs(self):
        res = self.client.get('/api/dashboard/apps')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        ids = [a['id'] for a in data.get('items', [])]
        self.assertIn('system_logs', ids)

    def test_logs_summary_api(self):
        res = self.client.get('/api/logs/summary')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('errors_24h', data)
        self.assertIn('ssh_failed_24h', data)
        self.assertIn('oom_events', data)
        self.assertIn('kernel_alerts', data)

    def test_logs_journal_api(self):
        res = self.client.get('/api/logs/journal?limit=20&since=1h')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('entries', data)
        self.assertIn('count', data)

    def test_logs_journal_invalid_unit_validation(self):
        res = self.client.get('/api/logs/journal?unit=invalid;rm.service')
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))

    def test_logs_auth_api(self):
        res = self.client.get('/api/logs/auth?limit=30')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('stats', data)
        self.assertIn('events', data)
        self.assertIn('top_attackers', data)

    def test_logs_dmesg_api(self):
        res = self.client.get('/api/logs/dmesg?limit=30')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('entries', data)
        self.assertIn('oom_events', data)
        self.assertIn('disk_errors', data)

    def test_logs_units_api(self):
        res = self.client.get('/api/logs/units')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('units', data)
        self.assertIn('count', data)


class TestFirewallModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dashboard.app.config['TESTING'] = True
        cls.client = dashboard.app.test_client()

    def setUp(self):
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['username'] = 'admin'
            sess['role'] = 'owner'
            sess['last_active'] = time.time()

    def test_firewall_page_render(self):
        res = self.client.get('/firewall')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('firewall.js', html)
        self.assertIn('Central Firewall Manager', html)
        self.assertIn('Rules Manager', html)
        self.assertIn('Quick Presets & Rate-Limit', html)

    def test_system_apps_includes_firewall(self):
        res = self.client.get('/api/dashboard/apps')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        ids = [a['id'] for a in data.get('items', [])]
        self.assertIn('firewall', ids)

    def test_firewall_status_api(self):
        res = self.client.get('/api/firewall/status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('active', data)
        self.assertIn('defaults', data)
        self.assertIn('stats', data)
        self.assertIn('rules', data)

    def test_firewall_rule_add_validation_invalid_action(self):
        res = self.client.post('/api/firewall/rule/add', json={'action': 'destroy_all', 'port': '80'})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))

    def test_firewall_rule_add_validation_invalid_port(self):
        res = self.client.post('/api/firewall/rule/add', json={'action': 'allow', 'port': '80;rm -rf'})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))

    def test_firewall_rule_add_validation_invalid_ip(self):
        res = self.client.post('/api/firewall/rule/add', json={'action': 'allow', 'port': '80', 'from_ip': '999.999.999.999'})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))

    def test_firewall_rule_delete_invalid_num(self):
        res = self.client.post('/api/firewall/rule/delete', json={'num': -5})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))

    def test_firewall_default_invalid_direction(self):
        res = self.client.post('/api/firewall/default', json={'direction': 'invalid_dir', 'policy': 'allow'})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))

    def test_firewall_toggle_invalid_action(self):
        res = self.client.post('/api/firewall/toggle', json={'action': 'restart'})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))

    def test_firewall_iptables_api(self):
        res = self.client.get('/api/firewall/iptables')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('iptables_v4', data)


class TestSchedulerModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dashboard.app.config['TESTING'] = True
        cls.client = dashboard.app.test_client()

    def setUp(self):
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['username'] = 'admin'
            sess['role'] = 'owner'
            sess['last_active'] = time.time()

    def test_scheduler_page_render(self):
        res = self.client.get('/scheduler')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('scheduler.js', html)
        self.assertIn('Task Scheduler & Cron Jobs', html)
        self.assertIn('Crontab Jobs', html)
        self.assertIn('Systemd Timers', html)
        self.assertIn('Script Dry-Run & Tester', html)

    def test_system_apps_includes_scheduler(self):
        res = self.client.get('/api/dashboard/apps')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        ids = [a['id'] for a in data.get('items', [])]
        self.assertIn('scheduler', ids)

    def test_cron_summary_api(self):
        res = self.client.get('/api/cron/summary')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('total_cron_jobs', data)
        self.assertIn('active_cron_jobs', data)
        self.assertIn('total_timers', data)
        self.assertIn('active_timers', data)
        self.assertIn('users', data)

    def test_cron_list_api(self):
        res = self.client.get('/api/cron/list')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('jobs', data)
        self.assertIn('users', data)

    def test_cron_timers_api(self):
        res = self.client.get('/api/cron/timers')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('timers', data)

    def test_cron_save_validation_empty_command(self):
        res = self.client.post('/api/cron/save', json={'schedule': '* * * * *', 'command': ''})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))

    def test_cron_save_validation_invalid_schedule(self):
        res = self.client.post('/api/cron/save', json={'schedule': 'invalid_sched', 'command': 'echo 1'})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))

    def test_cron_toggle_validation_empty_raw(self):
        res = self.client.post('/api/cron/toggle', json={'user': 'root', 'raw': ''})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))

    def test_cron_delete_validation_empty_raw(self):
        res = self.client.post('/api/cron/delete', json={'user': 'root', 'raw': ''})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))

    def test_cron_test_run_validation_empty_command(self):
        res = self.client.post('/api/cron/test_run', json={'command': ''})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))


class TestDriveHealthModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dashboard.app.config['TESTING'] = True
        cls.client = dashboard.app.test_client()

    def setUp(self):
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['username'] = 'admin'
            sess['role'] = 'owner'
            sess['last_active'] = time.time()

    def test_drive_health_page_render(self):
        res = self.client.get('/smart')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('drive_health.js', html)
        self.assertIn('Drive Health & S.M.A.R.T. Inspector', html)
        self.assertIn('Total Drive Fisik', html)
        self.assertIn('style.css', html)

    def test_system_apps_includes_drive_health(self):
        res = self.client.get('/api/dashboard/apps')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        ids = [a['id'] for a in data.get('items', [])]
        self.assertIn('drive_health', ids)

    def test_smart_summary_api(self):
        res = self.client.get('/api/smart/summary')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('total_drives', data)
        self.assertIn('healthy_count', data)
        self.assertIn('drives', data)
        self.assertIn('raid', data)

    def test_smart_detail_api(self):
        res = self.client.get('/api/smart/detail/sda')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('drive', data)
        drive = data.get('drive', {})
        self.assertIn('device', drive)
        self.assertIn('protocol', drive)

    def test_smart_detail_invalid_device(self):
        res = self.client.get('/api/smart/detail/bad;device')
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))

    def test_smart_raid_api(self):
        res = self.client.get('/api/smart/raid')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('raid', data)

    def test_smart_test_start_validation_invalid_device(self):
        res = self.client.post('/api/smart/test/start', json={'device': 'bad;dev', 'type': 'short'})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))

    def test_smart_test_start_validation_invalid_type(self):
        res = self.client.post('/api/smart/test/start', json={'device': 'sda', 'type': 'invalid_test'})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))

    def test_smart_test_abort_validation_invalid_device(self):
        res = self.client.post('/api/smart/test/abort', json={'device': 'bad;dev'})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))


class TestPackagesModule(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.app.test_client()
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['role'] = 'owner'
            sess['username'] = 'admin'

    def test_packages_registered_in_system_apps(self):
        app_ids = [a['id'] for a in dashboard.SYSTEM_APPS]
        self.assertIn('packages', app_ids)
        pkg_app = next(a for a in dashboard.SYSTEM_APPS if a['id'] == 'packages')
        self.assertEqual(pkg_app['url'], '/packages')
        self.assertEqual(pkg_app['name'], 'Package Manager')

    def test_packages_page_render(self):
        res = self.client.get('/packages')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('Package & OS Update Manager', html)
        self.assertIn('packages.js', html)
        self.assertIn('style.css', html)

    def test_parse_upgradable_packages_regex(self):
        from unittest.mock import patch
        mock_output = (
            "Listing... Done\n"
            "alsa-ucm-conf/noble-updates,noble-updates 1.2.10-1ubuntu5.15 all [upgradable from: 1.2.10-1ubuntu5.10]\n"
            "libssl3/noble-security 3.0.13-0ubuntu3.4 amd64 [upgradable from: 3.0.13-0ubuntu3.1]\n"
            "invalid line without bracket\n"
        )
        with patch.object(dashboard, '_run_apt_cmd', return_value=(0, mock_output, '')):
            pkgs = dashboard._parse_upgradable_packages()
            self.assertEqual(len(pkgs), 2)
            self.assertEqual(pkgs[0]['name'], 'alsa-ucm-conf')
            self.assertFalse(pkgs[0]['is_security'])
            self.assertEqual(pkgs[1]['name'], 'libssl3')
            self.assertTrue(pkgs[1]['is_security'])

    def test_api_packages_summary_structure(self):
        res = self.client.get('/api/packages/summary')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('total_upgradable', data)
        self.assertIn('security_count', data)
        self.assertIn('regular_count', data)
        self.assertIn('reboot_required', data)
        self.assertIn('running_kernel', data)
        self.assertIn('installed_kernels', data)
        self.assertIn('auto_updates_active', data)

    def test_api_packages_list(self):
        res = self.client.get('/api/packages/list')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('packages', data)
        self.assertIn('count', data)

    def test_api_packages_upgrade_validation_invalid_package_names(self):
        res = self.client.post('/api/packages/upgrade', json={'packages': ['bad;pkg;injection', 'rm -rf']})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success', True))

    def test_api_packages_upgrade_dry_run_mock(self):
        from unittest.mock import patch
        with patch.object(dashboard, '_run_apt_cmd', return_value=(0, 'Inst libssl3 (upgrade)\nConf libssl3', '')):
            res = self.client.post('/api/packages/upgrade', json={'dry_run': True, 'packages': ['libssl3']})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get('success', False))
            self.assertTrue(data.get('dry_run', False))
            self.assertIn('Inst libssl3', data.get('output', ''))

    def test_api_packages_refresh_mock(self):
        from unittest.mock import patch
        with patch.object(dashboard, '_run_apt_cmd', return_value=(0, 'Hit:1 http://archive.ubuntu.com/ubuntu noble InRelease\nReading package lists... Done', '')):
            res = self.client.post('/api/packages/refresh')
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get('success', False))
            self.assertIn('Hit:1', data.get('output', ''))


class TestAlertsModule(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.app.test_client()
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['role'] = 'owner'
            sess['username'] = 'admin'

    def test_alerts_registered_in_system_apps(self):
        app_ids = [a['id'] for a in dashboard.SYSTEM_APPS]
        self.assertIn('alerts', app_ids)
        alert_app = next(a for a in dashboard.SYSTEM_APPS if a['id'] == 'alerts')
        self.assertEqual(alert_app['url'], '/alerts')
        self.assertEqual(alert_app['name'], 'Alert Engine')

    def test_alerts_page_render(self):
        res = self.client.get('/alerts')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('Alerting & Notification Engine', html)
        self.assertIn('alerts.js', html)
        self.assertIn('style.css', html)

    def test_api_alerts_config_lifecycle(self):
        # 1. Get initial config
        res_get = self.client.get('/api/alerts/config')
        self.assertEqual(res_get.status_code, 200)
        data_get = res_get.get_json()
        self.assertTrue(data_get.get('success', False))
        self.assertIn('config', data_get)
        self.assertIn('stats', data_get)

        # 2. Update config
        new_payload = {
            'channel': 'both',
            'telegram': {'bot_token': 'test_token_123', 'chat_id': '987654321'},
            'whatsapp': {'gateway_url': 'http://127.0.0.1:3000/send', 'target_phone': '628123456789'},
            'rules': {'cpu_threshold': 95}
        }
        res_post = self.client.post('/api/alerts/config', json=new_payload)
        self.assertEqual(res_post.status_code, 200)
        data_post = res_post.get_json()
        self.assertTrue(data_post.get('success', False))
        self.assertEqual(data_post['config']['channel'], 'both')
        self.assertEqual(data_post['config']['telegram']['chat_id'], '987654321')
        self.assertEqual(data_post['config']['rules']['cpu_threshold'], 95)

    def test_api_alerts_test_telegram_mock(self):
        from unittest.mock import patch
        with patch.object(dashboard, '_send_telegram_notification', return_value=(True, 'Pesan terkirim ke Telegram')):
            res = self.client.post('/api/alerts/test', json={'channel': 'telegram', 'message': 'Test mock alert'})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get('success', False))
            self.assertTrue(any(r['channel'] == 'Telegram' and r['success'] for r in data.get('results', [])))

    def test_api_alerts_test_whatsapp_mock(self):
        from unittest.mock import patch
        with patch.object(dashboard, '_send_whatsapp_notification', return_value=(True, 'Pesan terkirim ke WA (200)')):
            res = self.client.post('/api/alerts/test', json={'channel': 'whatsapp', 'message': 'Test WA alert'})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get('success', False))
            self.assertTrue(any(r['channel'] == 'WhatsApp' and r['success'] for r in data.get('results', [])))

    def test_api_alerts_history_and_clear(self):
        # 1. Fetch history
        res_hist = self.client.get('/api/alerts/history')
        self.assertEqual(res_hist.status_code, 200)
        data_hist = res_hist.get_json()
        self.assertTrue(data_hist.get('success', False))
        self.assertIsInstance(data_hist.get('history'), list)

        # 2. Clear history
        res_clear = self.client.post('/api/alerts/history/clear')
        self.assertEqual(res_clear.status_code, 200)
        data_clear = res_clear.get_json()
        self.assertTrue(data_clear.get('success', False))

        # 3. Verify history empty
        res_verify = self.client.get('/api/alerts/history')
        self.assertEqual(len(res_verify.get_json().get('history', [])), 0)

    def test_api_alerts_system_check(self):
        res = self.client.post('/api/alerts/system_check', json={'send_alert': False})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('triggers', data)
        self.assertIn('triggered', data)

    def test_api_alerts_wa_status(self):
        res = self.client.get('/api/alerts/wa_status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('online', data)
        self.assertIn('status', data)


class TestBackupModule(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.app.test_client()
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['role'] = 'owner'
            sess['username'] = 'admin'

    def test_backup_page_render(self):
        res = self.client.get('/backup')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('Disaster Recovery & Offsite Backup', html)
        self.assertIn('backup.js', html)
        self.assertIn('style.css', html)

    def test_api_backup_summary(self):
        res = self.client.get('/api/backup/summary')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('summary', data)
        self.assertIn('total_backups', data['summary'])
        self.assertIn('rclone', data['summary'])
        self.assertIn('schedule', data['summary'])

    def test_api_backup_list(self):
        res = self.client.get('/api/backup/list')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('backups', data)
        self.assertIsInstance(data['backups'], list)

    def test_api_backup_create_inspect_delete_lifecycle(self):
        # 1. Create snapshot
        res_create = self.client.post('/api/backup/create', json={
            'name': 'test_dr_lifecycle',
            'include_config': True,
            'include_docker': False,
            'include_users': False,
            'include_nginx': False,
            'include_system': False
        })
        self.assertEqual(res_create.status_code, 200)
        data_create = res_create.get_json()
        self.assertTrue(data_create.get('success', False))
        filename = data_create.get('filename')
        self.assertIsNotNone(filename)

        # 2. Inspect snapshot
        res_inspect = self.client.get(f'/api/backup/inspect/{filename}')
        self.assertEqual(res_inspect.status_code, 200)
        data_inspect = res_inspect.get_json()
        self.assertTrue(data_inspect.get('success', False))
        self.assertIn('manifest', data_inspect)
        self.assertIn('members', data_inspect)

        # 3. Delete snapshot
        res_del = self.client.delete(f'/api/backup/delete/{filename}')
        self.assertEqual(res_del.status_code, 200)
        data_del = res_del.get_json()
        self.assertTrue(data_del.get('success', False))

    def test_api_backup_schedule_lifecycle(self):
        res_get = self.client.get('/api/backup/schedule')
        self.assertEqual(res_get.status_code, 200)
        data_get = res_get.get_json()
        self.assertTrue(data_get.get('success', False))
        self.assertIn('schedule', data_get)

        res_post = self.client.post('/api/backup/schedule', json={
            'enabled': True,
            'frequency': 'weekly',
            'time': '03:30',
            'remote': None
        })
        self.assertEqual(res_post.status_code, 200)
        data_post = res_post.get_json()
        self.assertTrue(data_post.get('success', False))
        self.assertEqual(data_post['schedule']['frequency'], 'weekly')
        self.assertEqual(data_post['schedule']['time'], '03:30')

    def test_api_backup_rclone_status(self):
        res = self.client.get('/api/backup/rclone/status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('rclone', data)
        self.assertIn('installed', data['rclone'])


class TestMonitoringWallboard(unittest.TestCase):
    def setUp(self):
        dashboard.app.config['TESTING'] = True
        self.client = dashboard.app.test_client()

    def test_monitoring_page_renders_wallpaper_and_fleet(self):
        res = self.client.get('/')
        self.assertIn(res.status_code, (200, 302))
        if res.status_code == 200:
            html = res.get_data(as_text=True)
            self.assertIn('class="wallpaper"', html)
            self.assertIn('href="/static/monitoring.css"', html)
            self.assertIn('src="/static/monitoring.js"', html)
            self.assertIn('class="fleet-grid"', html)
            self.assertIn('Drive Health (S.M.A.R.T.)', html)
            self.assertIn('System Services', html)
            self.assertIn('2026', html)

    def test_api_monitoring_telemetry_structure(self):
        res = self.client.get('/api/monitoring/telemetry')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success', False))
        self.assertIn('smart', data)
        self.assertIn('firewall', data)
        self.assertIn('services', data)
        self.assertIn('packages', data)
        self.assertIn('backup', data)
        self.assertIn('connectivity', data)
        self.assertIn('timestamp', data)
        self.assertIsInstance(data['smart']['healthy'], bool)
        self.assertIsInstance(data['firewall']['active'], bool)
        self.assertIsInstance(data['services']['failed'], int)


class TestHardwarePowerEngine(unittest.TestCase):
    def setUp(self):
        dashboard.app.config['TESTING'] = True
        self.client = dashboard.app.test_client()

    def test_power_reader_instantiation_and_read(self):
        reader = dashboard.HardwarePowerReader()
        watts, source = reader.read_power(cpu_percent=10.0)
        self.assertIsInstance(watts, (int, float))
        self.assertGreater(watts, 0)
        self.assertIn(source, ('rapl', 'power_supply', 'model'))

    def test_api_metrics_power_format(self):
        res = self.client.get('/api/metrics')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('power', data)
        self.assertIn('kwh', data['power'])
        self.assertIn('watts_est', data['power'])
        self.assertIn('source', data['power'])
        self.assertGreater(data['power']['watts_est'], 0)

    def test_api_stats_power_format(self):
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['username'] = 'admin'
        res = self.client.get('/api/stats')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('power', data)
        self.assertIn('kwh', data['power'])
        self.assertIn('watts_est', data['power'])
        self.assertIn('source', data['power'])


class TestUniversalAntiHardcode(unittest.TestCase):
    def test_syncthing_dynamic_user_service_prefix(self):
        snapshot = ({'syncthing@anyuser.service'}, set())
        res = dashboard._detect_native_host_app('syncthing', host_snapshot=snapshot)
        self.assertIsNotNone(res)
        self.assertTrue(res['running'])
        self.assertTrue(res['is_native'])

    def test_wireguard_dynamic_interface_prefix(self):
        snapshot = ({'wg-quick@wg1.service'}, set())
        res = dashboard._detect_native_host_app('wireguard', host_snapshot=snapshot)
        self.assertIsNotNone(res)
        self.assertTrue(res['running'])

    def test_mobile_backup_dir_env_override(self):
        orig = os.environ.get('MOBILE_BACKUP_DIR')
        try:
            os.environ['MOBILE_BACKUP_DIR'] = '/tmp/custom_mobile_backup'
            self.assertEqual(dashboard._resolve_mobile_backup_base_dir(), '/tmp/custom_mobile_backup')
        finally:
            if orig is None:
                os.environ.pop('MOBILE_BACKUP_DIR', None)
            else:
                os.environ['MOBILE_BACKUP_DIR'] = orig

    def test_update_check_url_points_to_official_repo(self):
        self.assertIn('recode-project/web_server', dashboard.UPDATE_CHECK_URL)

    def test_default_gateway_detection_returns_valid_or_none(self):
        gw = dashboard._get_host_default_gateway()
        if gw is not None:
            parts = gw.split('.')
            self.assertEqual(len(parts), 4)

    def test_dockerfile_has_no_personal_cli_wrappers(self):
        df_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Dockerfile')
        with open(df_path, 'r') as f:
            content = f.read()
        self.assertNotIn('kiro-cli', content)

    def test_terminal_command_skips_login_banner_shell(self):
        cmd = dashboard._build_terminal_command()
        self.assertNotIn('--login', cmd)
        self.assertNotIn('-l', cmd)
        cmd_str = ' '.join(cmd)
        self.assertIn('bash', cmd_str)
        self.assertIn('-i', cmd_str)

    def test_universal_host_runner_echo_works(self):
        res = dashboard._run_host_cmd(['echo', 'universal_ok'], timeout=5)
        self.assertEqual(res.returncode, 0)
        self.assertIn('universal_ok', res.stdout)

    def test_host_cmd_prefix_adapts_to_nsenter_capability(self):
        orig = dashboard._NSENTER_CAPABILITY
        try:
            dashboard._NSENTER_CAPABILITY = False
            self.assertEqual(dashboard._host_cmd_prefix(include_pid=True), [])
            dashboard._NSENTER_CAPABILITY = True
            self.assertEqual(
                dashboard._host_cmd_prefix(include_pid=True),
                ['nsenter', '-t', '1', '-m', '-u', '-i', '-n', '-p', '--']
            )
            self.assertEqual(
                dashboard._host_cmd_prefix(include_pid=False),
                ['nsenter', '-t', '1', '-m', '-u', '-i', '-n', '--']
            )
        finally:
            dashboard._NSENTER_CAPABILITY = orig


class TestDistroAgnosticPackages(unittest.TestCase):
    def test_parse_dnf_upgradable_with_security_set(self):
        out = (
            "Last metadata expiration check: 0:10:00 ago.\n"
            "openssl-libs.x86_64        1:3.0.7-27.el9     baseos\n"
            "vim-enhanced.x86_64        2:8.2.2637-20.el9  appstream\n"
        )
        pkgs = dashboard._parse_dnf_upgradable(out, security_names={'openssl-libs'})
        self.assertEqual(len(pkgs), 2)
        self.assertEqual(pkgs[0]['name'], 'openssl-libs')
        self.assertEqual(pkgs[0]['arch'], 'x86_64')
        self.assertTrue(pkgs[0]['is_security'])
        self.assertEqual(pkgs[1]['name'], 'vim-enhanced')
        self.assertFalse(pkgs[1]['is_security'])

    def test_parse_pacman_upgradable(self):
        out = (
            "openssl 3.3.1-1 -> 3.3.2-1\n"
            "ripgrep 14.1.0-1 -> 14.1.1-1\n"
        )
        pkgs = dashboard._parse_pacman_upgradable(out)
        self.assertEqual(len(pkgs), 2)
        self.assertEqual(pkgs[0]['name'], 'openssl')
        self.assertEqual(pkgs[0]['current_version'], '3.3.1-1')
        self.assertEqual(pkgs[0]['new_version'], '3.3.2-1')
        self.assertTrue(pkgs[0]['is_security'])
        self.assertFalse(pkgs[1]['is_security'])

    def test_parse_apk_upgradable(self):
        out = (
            "Installed:                                Available:\n"
            "musl-1.2.4-r2                           < 1.2.4-r3\n"
            "tzdata-2024a-r0                         < 2024b-r0\n"
        )
        pkgs = dashboard._parse_apk_upgradable(out)
        self.assertEqual(len(pkgs), 2)
        self.assertEqual(pkgs[0]['name'], 'musl')
        self.assertEqual(pkgs[0]['current_version'], '1.2.4-r2')
        self.assertEqual(pkgs[0]['new_version'], '1.2.4-r3')
        self.assertTrue(pkgs[0]['is_security'])
        self.assertEqual(pkgs[1]['name'], 'tzdata')

    def test_parse_zypper_upgradable(self):
        out = (
            "S | Repository               | Name    | Current Version | Available Version | Arch\n"
            "--+--------------------------+---------+-----------------+-------------------+-------\n"
            "v | openSUSE-Security-Update | openssl | 3.1.4-1         | 3.1.4-2           | x86_64\n"
            "v | openSUSE-OSS             | git     | 2.43.0-1        | 2.44.0-1          | x86_64\n"
        )
        pkgs = dashboard._parse_zypper_upgradable(out)
        self.assertEqual(len(pkgs), 2)
        self.assertTrue(pkgs[0]['is_security'])
        self.assertEqual(pkgs[1]['name'], 'git')
        self.assertFalse(pkgs[1]['is_security'])

    def test_cross_distro_command_builders(self):
        for pm in ('apt', 'dnf', 'yum', 'pacman', 'apk', 'zypper'):
            self.assertIsNotNone(dashboard._build_pkg_refresh_cmd(pm))
            self.assertIsNotNone(dashboard._build_pkg_install_cmd(pm, 'rclone'))
            self.assertIsNotNone(dashboard._build_pkg_upgrade_cmd(pm, packages=['curl'], dry_run=True))
            self.assertIsNotNone(dashboard._build_pkg_upgrade_cmd(pm, packages=None, dry_run=False))
        self.assertIsNone(dashboard._build_pkg_refresh_cmd('unknown'))
        self.assertIsNone(dashboard._build_pkg_install_cmd('unknown', 'rclone'))
        self.assertIsNone(dashboard._build_pkg_upgrade_cmd('unknown'))

    def test_api_packages_summary_includes_distro_metadata(self):
        client = dashboard.app.test_client()
        with client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['role'] = 'owner'
            sess['username'] = 'admin'
        res = client.get('/api/packages/summary')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('package_manager', data)
        self.assertIn('distro_name', data)
        self.assertIn('auto_update_service', data)


class TestTahap3FirewallLogsWebServer(unittest.TestCase):
    def test_parse_firewalld_status(self):
        list_all = (
            "public (active)\n"
            "  target: default\n"
            "  services: ssh http https\n"
            "  ports: 8080/tcp 51820/udp\n"
            "  rich rules:\n"
            "    rule family=\"ipv4\" source address=\"192.0.2.5\" port port=\"22\" protocol=\"tcp\" drop\n"
        )
        parsed = dashboard._parse_firewalld_status("running\n", list_all)
        self.assertTrue(parsed['active'])
        self.assertEqual(parsed['stats']['total_rules'], 6)
        self.assertEqual(parsed['stats']['allow_count'], 5)
        self.assertEqual(parsed['stats']['deny_count'], 1)

    def test_parse_iptables_input_rules(self):
        ipt_out = (
            "Chain INPUT (policy DROP)\n"
            "num  target     prot opt source               destination\n"
            "1    ACCEPT     tcp  --  0.0.0.0/0            0.0.0.0/0            tcp dpt:22\n"
            "2    DROP       all  --  192.0.2.99           0.0.0.0/0\n"
        )
        parsed = dashboard._parse_iptables_input_rules(ipt_out)
        self.assertTrue(parsed['active'])
        self.assertEqual(parsed['defaults']['incoming'], 'deny')
        self.assertEqual(parsed['stats']['total_rules'], 2)
        self.assertEqual(parsed['rules'][0]['to'], '22/tcp')
        self.assertEqual(parsed['rules'][1]['from'], '192.0.2.99')

    def test_api_firewall_status_reports_backend(self):
        client = dashboard.app.test_client()
        with client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['role'] = 'owner'
            sess['username'] = 'admin'
        res = client.get('/api/firewall/status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('backend', data)
        self.assertIn(data['backend'], ('ufw', 'firewalld', 'nftables', 'iptables', 'none'))

    def test_api_websites_nginx_status_graceful_metadata(self):
        client = dashboard.app.test_client()
        with client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['role'] = 'owner'
            sess['username'] = 'admin'
        res = client.get('/api/websites/nginx_status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('installed', data)
        self.assertIn('web_server', data)
        self.assertIn('detected_servers', data)

    def test_read_auth_log_lines_returns_list(self):
        lines = dashboard._read_auth_log_lines(max_lines=20)
        self.assertIsInstance(lines, list)


class TestTahap4EnergyCalibration(unittest.TestCase):
    def test_sanitize_energy_settings_clamps_bounds(self):
        cfg = dashboard._sanitize_energy_settings({
            'currency_symbol': '  $  ',
            'currency_code': 'usd',
            'locale': 'en-US',
            'decimals': 99,
            'tariff_per_kwh': -5.0,
            'base_overhead_watts': 9999,
            'psu_efficiency': 90,  # percentage form -> 0.90
            'idle_watts_fallback': 0.1,
            'power_source_mode': 'invalid_mode',
        })
        self.assertEqual(cfg['currency_symbol'], '$')
        self.assertEqual(cfg['currency_code'], 'USD')
        self.assertEqual(cfg['locale'], 'en-US')
        self.assertEqual(cfg['decimals'], 4)
        self.assertEqual(cfg['tariff_per_kwh'], dashboard.DEFAULT_ENERGY_SETTINGS['tariff_per_kwh'])
        self.assertEqual(cfg['base_overhead_watts'], 500.0)
        self.assertAlmostEqual(cfg['psu_efficiency'], 0.90, places=2)
        self.assertEqual(cfg['idle_watts_fallback'], 1.0)
        self.assertEqual(cfg['power_source_mode'], 'auto')

    def test_power_supply_battery_power_now_and_ignores_hid_device(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_pcap = os.path.join(tmpdir, 'powercap')
            ps_dir = os.path.join(tmpdir, 'power_supply')
            os.makedirs(empty_pcap)
            os.makedirs(os.path.join(ps_dir, 'BAT0'))
            os.makedirs(os.path.join(ps_dir, 'hidpp_battery_0'))

            with open(os.path.join(ps_dir, 'BAT0', 'type'), 'w') as f:
                f.write('Battery\n')
            with open(os.path.join(ps_dir, 'BAT0', 'status'), 'w') as f:
                f.write('Discharging\n')
            with open(os.path.join(ps_dir, 'BAT0', 'capacity'), 'w') as f:
                f.write('78\n')
            with open(os.path.join(ps_dir, 'BAT0', 'power_now'), 'w') as f:
                f.write('18500000\n')  # 18.5W

            # Peripheral wireless mouse battery must be ignored
            with open(os.path.join(ps_dir, 'hidpp_battery_0', 'type'), 'w') as f:
                f.write('Battery\n')
            with open(os.path.join(ps_dir, 'hidpp_battery_0', 'scope'), 'w') as f:
                f.write('Device\n')
            with open(os.path.join(ps_dir, 'hidpp_battery_0', 'power_now'), 'w') as f:
                f.write('99000000\n')

            reader = dashboard.HardwarePowerReader(powercap_dir=empty_pcap, power_supply_dir=ps_dir)
            watts, src = reader.read_power(cpu_percent=20.0, energy_cfg={'power_source_mode': 'auto'})
            self.assertEqual(src, 'power_supply')
            self.assertAlmostEqual(watts, 18.5, places=1)
            bat = reader.get_battery_info()
            self.assertIsNotNone(bat)
            self.assertEqual(bat['device'], 'BAT0')
            self.assertEqual(bat['capacity'], 78)
            self.assertEqual(bat['status'], 'Discharging')

    def test_power_supply_current_voltage_fallback(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_pcap = os.path.join(tmpdir, 'powercap')
            ps_dir = os.path.join(tmpdir, 'power_supply')
            os.makedirs(empty_pcap)
            os.makedirs(os.path.join(ps_dir, 'BAT1'))

            with open(os.path.join(ps_dir, 'BAT1', 'type'), 'w') as f:
                f.write('Battery\n')
            with open(os.path.join(ps_dir, 'BAT1', 'current_now'), 'w') as f:
                f.write('1500000\n')  # 1.5 A
            with open(os.path.join(ps_dir, 'BAT1', 'voltage_now'), 'w') as f:
                f.write('12000000\n')  # 12.0 V -> 18.0 W

            reader = dashboard.HardwarePowerReader(powercap_dir=empty_pcap, power_supply_dir=ps_dir)
            watts, src = reader.read_power(cpu_percent=10.0, energy_cfg={'power_source_mode': 'auto'})
            self.assertEqual(src, 'power_supply')
            self.assertAlmostEqual(watts, 18.0, places=1)

    def test_rapl_and_model_respect_custom_calibration(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            pcap = os.path.join(tmpdir, 'powercap')
            ps_dir = os.path.join(tmpdir, 'power_supply')
            rapl_pkg = os.path.join(pcap, 'intel-rapl:0')
            os.makedirs(rapl_pkg)
            os.makedirs(ps_dir)

            uj_path = os.path.join(rapl_pkg, 'energy_uj')
            with open(uj_path, 'w') as f:
                f.write('10000000\n')  # 10 J
            with open(os.path.join(rapl_pkg, 'max_energy_range_uj'), 'w') as f:
                f.write('100000000000\n')

            reader = dashboard.HardwarePowerReader(powercap_dir=pcap, power_supply_dir=ps_dir)
            reader.last_timestamp -= 1.0  # simulate 1 second elapsed
            with open(uj_path, 'w') as f:
                f.write('20000000\n')  # +10 J over 1s => ~10 W CPU package

            watts, src = reader.read_power(
                cpu_percent=25.0,
                energy_cfg={'base_overhead_watts': 20.0, 'psu_efficiency': 0.90, 'power_source_mode': 'rapl'}
            )
            self.assertEqual(src, 'rapl')
            # (10 + 20) / 0.90 = 33.33 W (allow slight wall-clock jitter)
            self.assertGreater(watts, 30.0)
            self.assertLess(watts, 36.0)

            model_w, model_src = reader.read_power(
                cpu_percent=0.0,
                energy_cfg={'idle_watts_fallback': 25.0, 'power_source_mode': 'model'}
            )
            self.assertEqual(model_src, 'model')
            self.assertAlmostEqual(model_w, 25.0, places=1)

    def test_api_settings_energy_update_and_telemetry_reflection(self):
        import tempfile
        orig_settings_file = dashboard.APP_SETTINGS_FILE
        orig_kwh = dashboard.TOTAL_KWH
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                dashboard.APP_SETTINGS_FILE = os.path.join(tmpdir, 'app_settings.json')
                dashboard._invalidate_energy_cache()
                dashboard.TOTAL_KWH = 10.0

                client = dashboard.app.test_client()
                with client.session_transaction() as sess:
                    sess['logged_in'] = True
                    sess['role'] = 'owner'
                    sess['username'] = 'admin'

                post_res = client.post('/api/settings', json={
                    'energy': {
                        'currency_symbol': '$',
                        'currency_code': 'USD',
                        'locale': 'en-US',
                        'decimals': 2,
                        'tariff_per_kwh': 0.20,
                        'base_overhead_watts': 11.0,
                        'psu_efficiency': 0.90,
                        'idle_watts_fallback': 15.0,
                        'power_source_mode': 'auto',
                    }
                })
                self.assertEqual(post_res.status_code, 200)
                self.assertTrue(post_res.get_json().get('success'))

                cfg_res = client.get('/api/monitoring/config').get_json()
                self.assertEqual(cfg_res['energy']['currency_symbol'], '$')
                self.assertAlmostEqual(cfg_res['energy']['tariff_per_kwh'], 0.20, places=4)

                met_res = client.get('/api/metrics').get_json()
                self.assertEqual(met_res['power']['currency_symbol'], '$')
                self.assertEqual(met_res['power']['decimals'], 2)
                self.assertAlmostEqual(met_res['power']['estimated_cost'], 2.0, places=2)
            finally:
                dashboard.APP_SETTINGS_FILE = orig_settings_file
                dashboard.TOTAL_KWH = orig_kwh
                dashboard._invalidate_energy_cache()

    def test_settings_template_zero_inline_script_and_energy_ui(self):
        tpl_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates', 'settings.html')
        with open(tpl_path, 'r', encoding='utf-8') as f:
            html = f.read()
        self.assertNotIn('<script>', html)
        self.assertIn('/static/settings.js', html)
        self.assertIn('energy-currency-preset', html)
        self.assertIn('energy-psu-efficiency', html)
        self.assertIn('energy-base-overhead', html)


class TestTahap5OptionalModules(unittest.TestCase):
    def _authed_client(self):
        dashboard.app.config['TESTING'] = True
        client = dashboard.app.test_client()
        with client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['role'] = 'owner'
            sess['username'] = 'admin'
        return client

    def test_api_modules_status_returns_catalog_and_flags(self):
        client = self._authed_client()
        res = client.get('/api/modules/status?refresh=1')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertIsInstance(data.get('modules'), list)
        ids = {m['id'] for m in data['modules']}
        for expected in ('lxd', 'adblocker', 'vpn', 'sharing', 'websites', 'mqtt', 'whatsapp_bridge'):
            self.assertIn(expected, ids)
        for m in data['modules']:
            self.assertIn('installed', m)
            self.assertIn('visible', m)
            self.assertIn('category', m)

    def test_dashboard_apps_filters_hidden_and_auto_hide_modules(self):
        import tempfile
        from unittest.mock import patch

        orig_settings_file = dashboard.APP_SETTINGS_FILE
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                dashboard.APP_SETTINGS_FILE = os.path.join(tmpdir, 'app_settings.json')
                dashboard._invalidate_modules_cache()
                client = self._authed_client()

                post_res = client.post('/api/settings', json={
                    'modules': {'lxd': False, 'adblocker': False, 'auto_hide_uninstalled': False}
                })
                self.assertEqual(post_res.status_code, 200)

                apps_res = client.get('/api/dashboard/apps').get_json()
                ids = [a['id'] for a in apps_res.get('items', [])]
                self.assertNotIn('lxd', ids)
                self.assertNotIn('adblocker', ids)
                self.assertIn('settings', ids)
                self.assertIn('lxd', apps_res.get('hidden_modules', []))

                # Now enable auto_hide_uninstalled and simulate sharing & vpn uninstalled
                client.post('/api/settings', json={
                    'modules': {'lxd': True, 'adblocker': True, 'sharing': True, 'vpn': True, 'auto_hide_uninstalled': True}
                })
                fake_probe = [
                    {'id': 'lxd', 'installed': True},
                    {'id': 'adblocker', 'installed': True},
                    {'id': 'sharing', 'installed': False},
                    {'id': 'vpn', 'installed': False},
                    {'id': 'websites', 'installed': True},
                    {'id': 'mobile-backup', 'installed': True},
                    {'id': 'store', 'installed': True},
                ]
                with patch.object(dashboard, '_probe_optional_modules', return_value=fake_probe):
                    auto_res = client.get('/api/dashboard/apps').get_json()
                auto_ids = [a['id'] for a in auto_res.get('items', [])]
                self.assertIn('lxd', auto_ids)
                self.assertNotIn('sharing', auto_ids)
                self.assertNotIn('vpn', auto_ids)
                self.assertTrue(auto_res.get('auto_hide_uninstalled'))
            finally:
                dashboard.APP_SETTINGS_FILE = orig_settings_file
                dashboard._invalidate_modules_cache()

    def test_lxd_containers_graceful_when_not_installed(self):
        from unittest.mock import patch
        client = self._authed_client()
        with patch.object(dashboard, '_detect_lxc_binary', return_value=None):
            res = client.get('/api/lxd/containers')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data['installed'])
        self.assertFalse(data['available'])
        self.assertEqual(data['containers'], [])

    def test_vpn_and_smb_graceful_when_binaries_missing(self):
        from unittest.mock import patch
        client = self._authed_client()
        missing = dashboard._CmdResult(returncode=1, stdout='', stderr='not found')
        with patch.object(dashboard, '_run_host_cmd', return_value=missing), \
             patch.object(dashboard, '_run_systemctl', return_value=missing):
            for endpoint in ('/api/smb/status', '/api/vpn/tailscale/status', '/api/vpn/status', '/api/zerotier/status'):
                res = client.get(endpoint)
                self.assertEqual(res.status_code, 200, f"{endpoint} returned {res.status_code}")
                data = res.get_json()
                self.assertFalse(data.get('installed'), f"{endpoint} should report installed=False")
                self.assertFalse(data.get('running'), f"{endpoint} should report running=False")

    def test_wa_status_graceful_when_unconfigured(self):
        from unittest.mock import patch
        client = self._authed_client()
        with patch.object(dashboard, '_load_alert_config', return_value={'whatsapp': {'enabled': False, 'gateway_url': ''}}):
            res = client.get('/api/alerts/wa_status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertFalse(data['installed'])
        self.assertFalse(data['configured'])
        self.assertEqual(data['status'], 'not_configured')

    def test_modular_zero_inline_script_across_updated_templates(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        checks = [
            ('templates/settings.html', '/static/settings.js'),
            ('templates/lxd.html', '/static/lxd.js'),
            ('templates/index.html', "filename='script.js'"),
        ]
        for rel_path, expected_src in checks:
            with open(os.path.join(root, rel_path), 'r', encoding='utf-8') as f:
                html = f.read()
            self.assertNotIn('<script>', html, f"Inline <script> found in {rel_path}")
            self.assertIn(expected_src, html, f"Missing modular script in {rel_path}")

    def test_terminal_layout_prevents_bottom_clipping_and_no_esp32_hardcode(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, 'templates', 'terminal.html'), 'r', encoding='utf-8') as f:
            html = f.read()
        with open(os.path.join(root, 'static', 'terminal.js'), 'r', encoding='utf-8') as f:
            js = f.read()
        self.assertIn('.terminal-screen', html)
        self.assertNotIn('/dev/ttyACM1', html)
        self.assertIn("termScreen.className = 'terminal-screen'", js)
        self.assertIn('rows: term.rows', js)
        self.assertIn('cols: term.cols', js)


class TestAppStoreUniversalOverhaul(unittest.TestCase):
    def _authed_client(self):
        dashboard.app.config['TESTING'] = True
        client = dashboard.app.test_client()
        with client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['role'] = 'owner'
            sess['username'] = 'admin'
        return client

    def test_catalog_has_70_plus_universal_apps_and_zero_host_root_binds(self):
        catalog = dashboard._load_store_catalog(include_user=False)
        self.assertGreaterEqual(len(catalog), 70)
        ids = [a['id'] for a in catalog]
        self.assertEqual(len(ids), len(set(ids)))
        for app_item in catalog:
            self.assertNotIn('homebook.png', app_item.get('icon', ''))
            for vol in app_item.get('volumes', []):
                self.assertFalse(
                    vol.get('bind', '').startswith('/host/root'),
                    f"{app_item['id']} still has forbidden /host/root volume bind"
                )
            for env_item in app_item.get('env', []):
                self.assertNotEqual(env_item.get('value'), '{{AUTO_TZ}}')

    def test_normalize_store_volume_bind(self):
        self.assertEqual(dashboard._normalize_store_volume_bind('mariadb_data'), 'mariadb_data')
        self.assertEqual(dashboard._normalize_store_volume_bind('/host/root/srv/media'), '/srv/media')
        self.assertEqual(dashboard._normalize_store_volume_bind('/srv/media'), '/srv/media')

    def test_resolve_app_open_port_prioritizes_web_ui_and_blocks_db(self):
        adguard_def = {'id': 'adguardhome', 'web_port': 80, 'has_web_ui': True}
        adguard_ports = [
            {'host': '53', 'container': '53', 'protocol': 'tcp'},
            {'host': '53', 'container': '53', 'protocol': 'udp'},
            {'host': '8053', 'container': '80', 'protocol': 'tcp'},
        ]
        port, proto = dashboard._resolve_app_open_port(adguard_def, adguard_ports)
        self.assertEqual(port, '8053')
        self.assertEqual(proto, 'http')

        db_def = {'id': 'mariadb', 'has_web_ui': False}
        db_port, _ = dashboard._resolve_app_open_port(db_def, [{'host': '3306', 'container': '3306', 'protocol': 'tcp'}])
        self.assertIsNone(db_port)

    def test_single_manage_route_and_zero_inline_script_in_store_html(self):
        manage_rules = [r for r in dashboard.app.url_map.iter_rules() if str(r) == '/api/store/manage']
        self.assertEqual(len(manage_rules), 1)
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, 'templates', 'store.html'), 'r', encoding='utf-8') as f:
            html = f.read()
        with open(os.path.join(root, 'static', 'store.js'), 'r', encoding='utf-8') as f:
            js = f.read()
        self.assertNotIn('<script>', html)
        self.assertIn('/static/store.js', html)
        self.assertNotIn('.status-badge', html)
        self.assertNotIn('999px', html)
        self.assertNotIn('status-badge', js)
        self.assertIn('position: fixed !important;', html)
        self.assertIn('var(--glass-bg', html)
        self.assertTrue(os.path.exists(os.path.join(root, 'static', 'icon.svg')))

    def test_energy_widget_click_opens_power_detail_view(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, 'templates', 'index.html'), 'r', encoding='utf-8') as f:
            index_html = f.read()
        with open(os.path.join(root, 'static', 'script.js'), 'r', encoding='utf-8') as f:
            script_js = f.read()
        with open(os.path.join(root, 'templates', 'settings.html'), 'r', encoding='utf-8') as f:
            settings_html = f.read()
        self.assertIn('id="energy-widget-card"', index_html)
        self.assertNotIn('<script>', index_html)
        self.assertIn("openDetail('power')", script_js)
        self.assertIn('function fetchPowerDetails()', script_js)
        self.assertIn('function resetEnergyFromDetail()', script_js)
        self.assertIn('id="energy-calibration-section"', settings_html)

    def test_recode_ai_menu_and_route_removed(self):
        client = self._authed_client()
        sys_ids = [a['id'] for a in dashboard.SYSTEM_APPS]
        self.assertNotIn('recode', sys_ids)
        opt_ids = [m['id'] for m in dashboard.OPTIONAL_MODULES_CATALOG]
        self.assertNotIn('recode', opt_ids)
        res = client.get('/recode')
        self.assertEqual(res.status_code, 404)

    def test_api_store_installed_graceful_when_docker_unavailable(self):
        from unittest.mock import patch
        client = self._authed_client()
        with patch.object(dashboard.docker, 'from_env', side_effect=RuntimeError('Docker down')):
            res = client.get('/api/store/installed')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data['docker_available'])
        self.assertIsInstance(data['installed'], list)

    def test_smart_container_matcher_detects_custom_names_and_excludes_sidecars(self):
        catalog = {a['id']: a for a in dashboard._load_store_catalog(include_user=False)}
        self.assertGreaterEqual(len(catalog), 78)
        for expected_id in ('n8n', 'immich', 'pocketbase', 'onlyoffice', 'obsidian', 'rustdesk-server', 'couchdb'):
            self.assertIn(expected_id, catalog)

        fake_records = [
            {
                'obj': 'n8n_runner_obj',
                'container_name': 'n8n-runner-container',
                'image': 'n8nio/runners:latest',
                'image_repo': dashboard._normalize_image_repo('n8nio/runners:latest'),
                'running': True,
                'state': 'running',
                'ports': [{'host': '5680', 'container': '5680', 'protocol': 'tcp'}],
            },
            {
                'obj': 'n8n_main_obj',
                'container_name': 'n8n-container',
                'image': 'n8n-patched:latest',
                'image_repo': dashboard._normalize_image_repo('n8n-patched:latest'),
                'running': True,
                'state': 'running',
                'ports': [{'host': '5678', 'container': '5678', 'protocol': 'tcp'}],
            },
            {
                'obj': 'pgadmin_obj',
                'container_name': 'pgadmin4-web',
                'image': 'dpage/pgadmin4',
                'image_repo': dashboard._normalize_image_repo('dpage/pgadmin4'),
                'running': True,
                'state': 'running',
                'ports': [{'host': '5050', 'container': '80', 'protocol': 'tcp'}],
            },
            {
                'obj': 'rustdesk_relay',
                'container_name': 'rustdesk_hbbr',
                'image': 'rustdesk/rustdesk-server:latest',
                'image_repo': dashboard._normalize_image_repo('rustdesk/rustdesk-server:latest'),
                'running': True,
                'state': 'running',
                'ports': [],
            },
            {
                'obj': 'rustdesk_main',
                'container_name': 'rustdesk_hbbs',
                'image': 'rustdesk/rustdesk-server:latest',
                'image_repo': dashboard._normalize_image_repo('rustdesk/rustdesk-server:latest'),
                'running': True,
                'state': 'running',
                'ports': [],
            },
            {
                'obj': 'immich_obj',
                'container_name': 'immich_server',
                'image': 'ghcr.io/immich-app/immich-server:release',
                'image_repo': dashboard._normalize_image_repo('ghcr.io/immich-app/immich-server:release'),
                'running': True,
                'state': 'running',
                'ports': [{'host': '2283', 'container': '2283', 'protocol': 'tcp'}],
            },
        ]

        n8n_match = dashboard._match_store_container_record(catalog['n8n'], fake_records)
        self.assertIsNotNone(n8n_match)
        self.assertEqual(n8n_match['container_name'], 'n8n-container')

        pgadmin_match = dashboard._match_store_container_record(catalog['pgadmin'], fake_records)
        self.assertIsNotNone(pgadmin_match)
        self.assertEqual(pgadmin_match['container_name'], 'pgadmin4-web')
        pg_port, _ = dashboard._resolve_app_open_port(catalog['pgadmin'], pgadmin_match['ports'])
        self.assertEqual(pg_port, '5050')

        rustdesk_match = dashboard._match_store_container_record(catalog['rustdesk-server'], fake_records)
        self.assertIsNotNone(rustdesk_match)
        self.assertEqual(rustdesk_match['container_name'], 'rustdesk_hbbs')

        immich_match = dashboard._match_store_container_record(catalog['immich'], fake_records)
        self.assertIsNotNone(immich_match)
        self.assertEqual(immich_match['container_name'], 'immich_server')


class TestSecurityHardening(unittest.TestCase):
    def _unauth_client(self):
        dashboard.app.config['TESTING'] = True
        return dashboard.app.test_client()

    def _role_client(self, role='readonly'):
        dashboard.app.config['TESTING'] = True
        client = dashboard.app.test_client()
        with client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['role'] = role
            sess['username'] = f'user_{role}'
        return client

    def test_file_content_requires_auth_and_write_rbac(self):
        unauth = self._unauth_client()
        res_get = unauth.get('/api/files/content?path=/etc/hostname')
        self.assertIn(res_get.status_code, (401, 302))
        res_post = unauth.post('/api/files/content', json={'path': '/tmp/x', 'content': 'pwn'})
        self.assertIn(res_post.status_code, (401, 302))

        readonly = self._role_client('readonly')
        res_ro_post = readonly.post('/api/files/content', json={'path': '/tmp/x', 'content': 'pwn'})
        self.assertEqual(res_ro_post.status_code, 403)

    def test_docker_and_system_apis_require_auth(self):
        unauth = self._unauth_client()
        for ep in (
            '/api/docker/containers',
            '/api/docker/abc/logs',
            '/api/processes',
            '/api/disk-analysis',
            '/api/network-ports',
            '/api/network-details',
            '/api/system',
        ):
            res = unauth.get(ep)
            self.assertIn(res.status_code, (401, 302), f"{ep} leaked without auth ({res.status_code})")

        res_act = unauth.post('/api/docker/abc/action', json={'action': 'stop'})
        self.assertIn(res_act.status_code, (401, 302))

        readonly = self._role_client('readonly')
        res_ro_act = readonly.post('/api/docker/abc/action', json={'action': 'stop'})
        self.assertEqual(res_ro_act.status_code, 403)

    def test_mobile_backup_mutations_and_canonical_boundary(self):
        unauth = self._unauth_client()
        for ep, payload in (
            ('/api/mobile-backup/move', {'src': '/tmp/a', 'dest_dir': '/tmp/b'}),
            ('/api/mobile-backup/copy', {'src': '/tmp/a', 'dest_dir': '/tmp/b'}),
            ('/api/mobile-backup/upload', {}),
        ):
            res = unauth.post(ep, json=payload)
            self.assertIn(res.status_code, (401, 302), f"{ep} allowed unauth POST ({res.status_code})")

        # Canonical boundary must reject sibling prefix bypass (e.g., MobileBackup_evil)
        base = os.path.realpath(dashboard.BACKUP_BASE_DIR)
        self.assertTrue(dashboard._is_within_mobile_backup_dir(base))
        self.assertFalse(dashboard._is_within_mobile_backup_dir(base + '_evil/secret.txt'))

    def test_terminal_socket_auth_and_session_ownership(self):
        from unittest.mock import patch
        # Unauthenticated terminal_input must never write to an active PTY fd
        dashboard.terminal_sessions['sess_owned'] = {'fd': 99999, 'pid': 99999, 'sid': 'sid_owner', 'user': 'admin'}
        try:
            with patch.object(dashboard, '_terminal_socket_authorized', return_value=False), \
                 patch('os.write') as mock_write, \
                 patch.object(dashboard, 'emit') as mock_emit:
                dashboard.handle_terminal_input({'session_id': 'sess_owned', 'input': 'id\n'})
                mock_write.assert_not_called()
                mock_emit.assert_called()

            # Authenticated socket with different sid cannot access or stop another socket's PTY
            with dashboard.app.test_request_context('/'):
                dashboard.request.sid = 'sid_attacker'
                self.assertFalse(dashboard._terminal_session_owned('sess_owned'))
                with patch.object(dashboard, '_terminal_socket_authorized', return_value=True), \
                     patch('os.write') as mock_write:
                    dashboard.handle_terminal_input({'session_id': 'sess_owned', 'input': 'id\n'})
                    mock_write.assert_not_called()
                dashboard.request.sid = 'sid_owner'
                self.assertTrue(dashboard._terminal_session_owned('sess_owned'))
        finally:
            dashboard.terminal_sessions.pop('sess_owned', None)


if __name__ == '__main__':
    unittest.main()
