import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend_bridge
from domain.telegram_inbox import append_inbox_update


class BackendBridgeTests(unittest.TestCase):
    def test_profile_match_is_exact(self):
        cmd = 'python OAK_Hidden_SLTP_Manager.py --worker --profile VantageDemo'
        self.assertTrue(backend_bridge._cmdline_profile_exact(cmd, 'VantageDemo'))
        self.assertFalse(backend_bridge._cmdline_profile_exact(cmd, 'Vantage'))

    def test_runtime_health_is_observation_only(self):
        health = {
            'profile': 'Vantage',
            'telegram': {'configured': False, 'running': False, 'pid': 0},
            'worker': {'running': False, 'pid': 0},
            'remoteReady': False,
            'issues': [],
        }
        with patch.object(backend_bridge, 'load_profiles', return_value={'Vantage': {}}), \
             patch.object(backend_bridge, '_runtime_health', return_value=health), \
             patch.object(backend_bridge, '_spawn_detached') as spawn:
            result = backend_bridge.cmd_runtime_health({'profile': 'Vantage'})

        self.assertEqual(result, health)
        spawn.assert_not_called()

    def test_runtime_ensure_is_explicit_process_start_boundary(self):
        before = {
            'profile': 'Vantage',
            'telegram': {'configured': False, 'running': False, 'pid': 0},
            'worker': {'running': False, 'pid': 0},
            'remoteReady': False,
            'issues': [],
        }
        after = {
            'profile': 'Vantage',
            'telegram': {'configured': False, 'running': False, 'pid': 0},
            'worker': {'running': True, 'pid': 101},
            'remoteReady': False,
            'issues': [],
        }
        with patch.object(backend_bridge, 'load_profiles', return_value={'Vantage': {}}), \
             patch.object(backend_bridge, '_runtime_health', side_effect=[before, after]), \
             patch.object(backend_bridge, '_spawn_detached') as spawn:
            result = backend_bridge.cmd_runtime_ensure({'profile': 'Vantage'})

        spawn.assert_called_once()
        args = spawn.call_args.args[0]
        self.assertIn('worker_runtime.py', str(args[1]))
        self.assertEqual(args[-1], 'Vantage')
        self.assertEqual(result['started'], ['worker'])

    def test_profile_create_defaults_are_owned_by_backend(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / 'profiles.json').write_text('{}', encoding='utf-8')
            original_root = backend_bridge.BACKEND_ROOT
            backend_bridge.BACKEND_ROOT = root
            try:
                listing = backend_bridge.cmd_profiles({})
                created = backend_bridge.cmd_profile_add({'name': 'Demo', 'path': r'C:\Broker\terminal64.exe'})
                saved = json.loads((root / 'profiles.json').read_text(encoding='utf-8'))['Demo']
            finally:
                backend_bridge.BACKEND_ROOT = original_root

        self.assertEqual(listing['profileDefaults'], backend_bridge.PROFILE_CREATE_DEFAULTS)
        self.assertEqual(saved['sl'], backend_bridge.PROFILE_CREATE_DEFAULTS['sl'])
        self.assertEqual(saved['tp'], backend_bridge.PROFILE_CREATE_DEFAULTS['tp'])
        self.assertEqual(saved['auto_be'], backend_bridge.PROFILE_CREATE_DEFAULTS['autoBeR'])
        self.assertTrue(created['saved'])

    def test_malformed_global_config_is_not_reported_as_unconfigured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / 'config.json').write_text('{broken', encoding='utf-8')
            original_root = backend_bridge.BACKEND_ROOT
            backend_bridge.BACKEND_ROOT = root
            try:
                with self.assertRaisesRegex(RuntimeError, 'Cannot read config.json'):
                    backend_bridge._load_global_config()
            finally:
                backend_bridge.BACKEND_ROOT = original_root

    def test_invalid_runtime_lock_is_not_reported_as_offline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock = Path(temp_dir) / 'worker.lock'
            lock.write_text('not-a-pid', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'Invalid runtime lock file'):
                backend_bridge._lock_pid(lock)

    def test_inbox_ids_are_monotonic(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / 'tele_inbox.json'
            first = append_inbox_update(path, 'one', 123)
            second = append_inbox_update(path, 'two', 123)
            self.assertGreater(second['update_id'], first['update_id'])

    def test_telegram_send_queues_selected_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / 'profiles.json').write_text(json.dumps({'Vantage': {'tele_admin': '123'}}), encoding='utf-8')
            (root / 'config.json').write_text(json.dumps({'telegram_token': 'token', 'telegram_chat_id': 123}), encoding='utf-8')
            original_root = backend_bridge.BACKEND_ROOT
            backend_bridge.BACKEND_ROOT = root
            try:
                result = backend_bridge.cmd_telegram_send({'profile': 'Vantage', 'text': '/buy EURUSD 0.10'})
            finally:
                backend_bridge.BACKEND_ROOT = original_root
            self.assertEqual(result['text'], 'buy EURUSD 0.10 Vantage')
            rows = json.loads((root / 'tele_inbox.json').read_text(encoding='utf-8'))
            self.assertEqual(rows[-1]['message']['text'], 'buy EURUSD 0.10 Vantage')


if __name__ == '__main__':
    unittest.main()
