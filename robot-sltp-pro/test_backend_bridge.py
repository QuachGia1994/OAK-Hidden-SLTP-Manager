import json
import tempfile
import unittest
from pathlib import Path

import backend_bridge
from domain.telegram_inbox import append_inbox_update


class BackendBridgeTests(unittest.TestCase):
    def test_profile_match_is_exact(self):
        cmd = 'python OAK_Hidden_SLTP_Manager.py --worker --profile VantageDemo'
        self.assertTrue(backend_bridge._cmdline_profile_exact(cmd, 'VantageDemo'))
        self.assertFalse(backend_bridge._cmdline_profile_exact(cmd, 'Vantage'))

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
