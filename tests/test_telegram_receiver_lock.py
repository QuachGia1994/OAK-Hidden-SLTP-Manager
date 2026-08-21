"""Contract guard for Telegram receiver singleton ownership."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "oak_enginecore.py").read_text(encoding="utf-8")


class TelegramReceiverLockTests(unittest.TestCase):
    def test_pid_marker_is_separate_from_os_singleton_lock(self):
        self.assertIn('PID_FILE = ROOT / "oak_enginecore.lock"', SOURCE)
        self.assertIn('LOCK_FILE = ROOT / "oak_enginecore.singleton.lock"', SOURCE)
        self.assertIn("guard = FileLock(str(LOCK_FILE), timeout=0.0)", SOURCE)

    def test_lock_failure_is_fail_closed(self):
        acquire = SOURCE.split("def _acquire_lock() -> bool:", 1)[1].split("def _release_lock()", 1)[0]
        self.assertIn("if acquired is None:", acquire)
        self.assertIn("return False", acquire)
        self.assertNotIn("Cannot create receiver lock", acquire)

    def test_legacy_live_pid_guard_remains_during_lock_migration(self):
        acquire = SOURCE.split("def _acquire_lock() -> bool:", 1)[1].split("def _release_lock()", 1)[0]
        self.assertIn("_pid_is_live(old_pid)", acquire)
        self.assertIn("Telegram receiver already running", acquire)

    def test_cloud_webhook_ownership_is_not_stolen_by_desktop_fallback(self):
        self.assertIn("def _active_webhook_url() -> str:", SOURCE)
        self.assertIn("getWebhookInfo", SOURCE)
        self.assertNotIn("deleteWebhook", SOURCE)
        main = SOURCE.split("def main() -> int:", 1)[1].split('if __name__ == "__main__":', 1)[0]
        self.assertIn("webhook_url = _active_webhook_url()", main)
        self.assertIn("Telegram cloud webhook active", main)
        self.assertLess(main.index("_active_webhook_url()"), main.index("_acquire_lock()"))


if __name__ == "__main__":
    unittest.main()
