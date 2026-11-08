"""Unit tests for Store performance optimization and LXD multi-project support.

Ran via:
    .venv/bin/python -m unittest tests/test_store_and_lxd.py -v
"""

import os
import sys
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
        cmd = dashboard._lxc_cmd(['list', '--format', 'json'], project='projek-kp')
        expected_base = ['nsenter', '-t', '1', '-m', '-u', '-i', '-n', '-p', '--', 'lxc', '--project', 'projek-kp']
        self.assertEqual(cmd[:len(expected_base)], expected_base)
        self.assertEqual(cmd[len(expected_base):], ['list', '--format', 'json'])

    def test_lxc_cmd_exec_with_project(self):
        cmd = dashboard._lxc_cmd(['exec', 'projek-kp', '--', 'tailscale', 'status'], project='projek-kp')
        self.assertIn('--project', cmd)
        idx = cmd.index('--project')
        self.assertEqual(cmd[idx + 1], 'projek-kp')

    def test_build_terminal_command_lxd_project(self):
        cmd = dashboard._build_terminal_command(
            lxd_target='projek-kp',
            start_path=None,
            lxd_project='projek-kp'
        )
        self.assertIn('--project', cmd)
        idx = cmd.index('--project')
        self.assertEqual(cmd[idx + 1], 'projek-kp')
        self.assertIn('projek-kp', cmd)


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


if __name__ == '__main__':
    unittest.main()
