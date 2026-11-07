"""Unit test fitur Recode Agent (app.py).

Dijalankan tanpa dependensi tambahan:
    .venv/bin/python -m unittest discover -s tests -v

Fokus pengujian:
  1. Validasi konfigurasi menolak nilai yang bisa dipakai command injection.
  2. Susunan argv benar untuk mode local maupun ssh.
  3. Task yang berisi metakarakter shell tetap jadi satu argumen.
  4. Route /recode dan API-nya menolak akses tanpa login.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as dashboard  # noqa: E402


def base_cfg(**overrides):
    cfg = {
        'mode': 'local',
        'binary': 'recode',
        'local_user': '',
        'default_cwd': '/root',
        'default_model': '',
        'max_iterations': 0,
        'ssh': {'host': '', 'user': '', 'port': 22, 'identity_file': ''}
    }
    ssh = overrides.pop('ssh', None)
    cfg.update(overrides)
    if ssh:
        cfg['ssh'] = {**cfg['ssh'], **ssh}
    return cfg


class TestRecodeValidation(unittest.TestCase):
    def test_default_config_valid(self):
        ok, msg = dashboard._recode_validate_config(base_cfg())
        self.assertTrue(ok, msg)

    def test_reject_binary_with_shell_metachars(self):
        for bad in ['recode; rm -rf /', 'recode && curl evil', 'recode$(id)', 're code', '']:
            ok, _ = dashboard._recode_validate_config(base_cfg(binary=bad))
            self.assertFalse(ok, f"binary {bad!r} seharusnya ditolak")

    def test_reject_relative_cwd(self):
        ok, _ = dashboard._recode_validate_config(base_cfg(default_cwd='var/www'))
        self.assertFalse(ok)

    def test_reject_bad_local_user(self):
        ok, _ = dashboard._recode_validate_config(base_cfg(local_user='root; id'))
        self.assertFalse(ok)

    def test_reject_bad_ssh_host_and_port(self):
        ok, _ = dashboard._recode_validate_config(base_cfg(ssh={'host': 'a b;c'}))
        self.assertFalse(ok)
        ok, _ = dashboard._recode_validate_config(base_cfg(ssh={'host': '10.0.0.1', 'port': 0}))
        self.assertFalse(ok)

    def test_reject_relative_identity_file(self):
        ok, _ = dashboard._recode_validate_config(
            base_cfg(ssh={'host': '10.0.0.1', 'identity_file': '.ssh/id_ed25519'}))
        self.assertFalse(ok)

    def test_ssh_mode_requires_host(self):
        ok, _ = dashboard._recode_validate_config(base_cfg(mode='ssh'))
        self.assertFalse(ok)

    def test_max_iterations_range(self):
        self.assertFalse(dashboard._recode_validate_config(base_cfg(max_iterations=-1))[0])
        self.assertFalse(dashboard._recode_validate_config(base_cfg(max_iterations=9999))[0])
        self.assertTrue(dashboard._recode_validate_config(base_cfg(max_iterations=50))[0])


class TestRecodeEffectiveMode(unittest.TestCase):
    def test_auto_falls_back_to_local_without_host(self):
        self.assertEqual(dashboard._recode_effective_mode(base_cfg(mode='auto')), 'local')

    def test_auto_uses_ssh_when_host_set(self):
        cfg = base_cfg(mode='auto', ssh={'host': '100.87.49.14'})
        self.assertEqual(dashboard._recode_effective_mode(cfg), 'ssh')

    def test_explicit_mode_wins(self):
        cfg = base_cfg(mode='local', ssh={'host': '100.87.49.14'})
        self.assertEqual(dashboard._recode_effective_mode(cfg), 'local')


class TestRecodeInnerCommand(unittest.TestCase):
    def test_repl_command_has_no_task_flags(self):
        cmd = dashboard._recode_inner_command(base_cfg())
        self.assertIn('recode', cmd)
        self.assertNotIn('--task', cmd)
        self.assertNotIn('--no-interactive', cmd)
        # shlex.quote hanya menambah kutip bila perlu, jadi path aman tetap polos.
        self.assertTrue(cmd.startswith('cd /root &&'), cmd)

    def test_task_is_single_quoted_argument(self):
        # Task berisi metakarakter shell: harus tetap satu argumen, tidak jadi
        # perintah kedua. Ini pertahanan utama terhadap command injection.
        cmd = dashboard._recode_inner_command(
            base_cfg(), task="cek log; rm -rf / && echo $(whoami)")
        self.assertIn('--task', cmd)
        self.assertNotIn('&& echo', cmd.split('--task')[0])
        # Setelah shlex.quote, seluruh task terkurung kutip tunggal.
        self.assertIn("'cek log; rm -rf / && echo $(whoami)'", cmd)

    def test_task_mode_is_non_interactive(self):
        cmd = dashboard._recode_inner_command(base_cfg(), task='ringkas server')
        self.assertIn('--no-interactive', cmd)

    def test_model_and_iterations_forwarded(self):
        cmd = dashboard._recode_inner_command(
            base_cfg(default_model='gpt-x', max_iterations=12), task='cek')
        self.assertIn('--model gpt-x', cmd)
        self.assertIn('--max-iterations 12', cmd)

    def test_model_with_spaces_is_quoted(self):
        cmd = dashboard._recode_inner_command(
            base_cfg(default_model='model; id'), task='cek')
        self.assertIn("--model 'model; id'", cmd)

    def test_version_probe_skips_cd_and_task(self):
        cmd = dashboard._recode_inner_command(base_cfg(), version_only=True)
        self.assertEqual(cmd, "recode --version")

    def test_cwd_override_quoted(self):
        cmd = dashboard._recode_inner_command(base_cfg(), cwd="/var/www/my project")
        self.assertIn("cd '/var/www/my project'", cmd)


class TestRecodeArgv(unittest.TestCase):
    def test_local_argv_uses_login_shell(self):
        argv = dashboard._recode_argv(base_cfg(mode='local'), task='cek')
        # nsenter hanya dipakai saat root di container privileged; di test
        # runner biasa hasilnya bash -lc.
        self.assertIn('bash', argv)
        self.assertIn('-lc', argv)
        self.assertTrue(any('--task' in part for part in argv))

    def test_ssh_argv_uses_batchmode_and_no_password(self):
        cfg = base_cfg(mode='ssh', ssh={'host': '100.87.49.14', 'user': 'ekaharefa'})
        argv = dashboard._recode_argv(cfg, task='cek')
        self.assertEqual(argv[0], 'ssh')
        self.assertIn('-tt', argv)
        self.assertIn('BatchMode=yes', argv)
        self.assertIn('ekaharefa@100.87.49.14', argv)
        self.assertTrue(argv[-1].startswith('bash -lc '))

    def test_version_probe_skips_tty_allocation(self):
        # `ssh -tt` pada probe non-interaktif mengotori stderr dengan
        # "Connection to host closed." dan bisa mengacaukan parsing versi.
        cfg = base_cfg(mode='ssh', ssh={'host': '100.87.49.14'})
        argv = dashboard._recode_argv(cfg, version_only=True)
        self.assertNotIn('-tt', argv)

    def test_ssh_argv_includes_port_and_identity(self):
        cfg = base_cfg(mode='ssh', ssh={
            'host': 'lenovo.local', 'user': 'eka',
            'port': 2222, 'identity_file': '/root/.ssh/id_ed25519'
        })
        argv = dashboard._recode_argv(cfg)
        self.assertIn('-p', argv)
        self.assertIn('2222', argv)
        self.assertIn('-i', argv)
        self.assertIn('/root/.ssh/id_ed25519', argv)

    def test_ssh_argv_omits_default_port(self):
        cfg = base_cfg(mode='ssh', ssh={'host': 'lenovo.local'})
        argv = dashboard._recode_argv(cfg)
        self.assertNotIn('-p', argv)
        # Tanpa user, target hanya host.
        self.assertIn('lenovo.local', argv)


class TestRecodePermissions(unittest.TestCase):
    def test_recode_permission_matrix(self):
        self.assertTrue(dashboard.has_permission('owner', 'recode'))
        self.assertTrue(dashboard.has_permission('admin', 'recode'))
        self.assertFalse(dashboard.has_permission('operator', 'recode'))
        self.assertFalse(dashboard.has_permission('readonly', 'recode'))

    def test_recode_app_registered_in_dashboard(self):
        ids = [a['id'] for a in dashboard.SYSTEM_APPS]
        self.assertIn('recode', ids)
        entry = next(a for a in dashboard.SYSTEM_APPS if a['id'] == 'recode')
        self.assertEqual(entry['url'], '/recode')


class TestRecodeRoutesAuth(unittest.TestCase):
    """Route Recode mengeksekusi shell — tanpa sesi harus ditolak/di-redirect."""

    @classmethod
    def setUpClass(cls):
        dashboard.app.config['TESTING'] = True
        cls.client = dashboard.app.test_client()

    def _require_auth(self):
        cfg = dashboard.load_security_config()
        return cfg.get('require_auth', True)

    def test_page_requires_login(self):
        if not self._require_auth():
            self.skipTest('require_auth dimatikan di konfigurasi lokal')
        res = self.client.get('/recode')
        self.assertIn(res.status_code, (302, 401, 403))

    def test_config_get_requires_login(self):
        if not self._require_auth():
            self.skipTest('require_auth dimatikan di konfigurasi lokal')
        res = self.client.get('/api/recode/config')
        self.assertIn(res.status_code, (302, 401, 403))

    def test_config_post_requires_admin(self):
        if not self._require_auth():
            self.skipTest('require_auth dimatikan di konfigurasi lokal')
        res = self.client.post('/api/recode/config', json={'mode': 'local'})
        self.assertIn(res.status_code, (302, 401, 403))

    def test_status_requires_login(self):
        if not self._require_auth():
            self.skipTest('require_auth dimatikan di konfigurasi lokal')
        res = self.client.get('/api/recode/status')
        self.assertIn(res.status_code, (302, 401, 403))


class TestRecodeConfigPersistence(unittest.TestCase):
    def setUp(self):
        self.original = dashboard.RECODE_CONFIG_FILE
        dashboard.RECODE_CONFIG_FILE = os.path.join('/tmp', 'recode_config_test.json')

    def tearDown(self):
        try:
            os.remove(dashboard.RECODE_CONFIG_FILE)
        except OSError:
            pass
        dashboard.RECODE_CONFIG_FILE = self.original

    def test_defaults_when_file_absent(self):
        cfg = dashboard.load_recode_config()
        self.assertEqual(cfg['mode'], 'auto')
        self.assertEqual(cfg['binary'], 'recode')
        self.assertEqual(cfg['ssh']['port'], 22)

    def test_save_then_load_roundtrip(self):
        cfg = dashboard.load_recode_config()
        cfg['mode'] = 'ssh'
        cfg['ssh']['host'] = '100.87.49.14'
        cfg['ssh']['user'] = 'ekaharefa'
        dashboard.save_recode_config(cfg)

        loaded = dashboard.load_recode_config()
        self.assertEqual(loaded['mode'], 'ssh')
        self.assertEqual(loaded['ssh']['host'], '100.87.49.14')
        self.assertEqual(loaded['ssh']['user'], 'ekaharefa')
        # Kunci yang tidak disimpan tetap memakai default.
        self.assertEqual(loaded['ssh']['port'], 22)

    def test_unknown_keys_are_ignored(self):
        with open(dashboard.RECODE_CONFIG_FILE, 'w') as f:
            f.write('{"mode": "local", "evil": "rm -rf /"}')
        loaded = dashboard.load_recode_config()
        self.assertEqual(loaded['mode'], 'local')
        self.assertNotIn('evil', loaded)


if __name__ == '__main__':
    unittest.main(verbosity=2)
