# -*- coding: utf-8 -*-
"""Tests for worker heartbeat and health state computation."""
import unittest
import os
import tempfile
from datetime import datetime, timezone, timedelta

from repositories.sqlite_store import SQLiteStore


class TestHeartbeat(unittest.TestCase):
    """Test heartbeat publish and health state computation."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = SQLiteStore(db_path=self.db_path)

    def tearDown(self):
        self.store.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_publish_and_read_heartbeat(self):
        """Worker publishes heartbeat, GUI reads it back."""
        self.store.publish_heartbeat(
            profile="Vantage",
            state="connected",
            server="Vantage Markets",
            login=12345,
            balance=1000.0,
            equity=1018.24,
        )
        hb = self.store.get_heartbeat("Vantage")
        self.assertIsNotNone(hb)
        self.assertEqual(hb["profile"], "Vantage")
        self.assertEqual(hb["state"], "connected")
        self.assertEqual(hb["server"], "Vantage Markets")
        self.assertEqual(hb["login"], 12345)
        self.assertAlmostEqual(hb["balance"], 1000.0)
        self.assertAlmostEqual(hb["equity"], 1018.24)

    def test_mt5_connected_state(self):
        """Fresh heartbeat (< 5s) => Connected."""
        self.store.publish_heartbeat("Vantage", "connected")
        state = self.store.compute_mt5_state("Vantage")
        self.assertEqual(state["state"], "Connected")

    def test_mt5_degraded_state(self):
        """Stale heartbeat (5-30s) => Degraded."""
        self.store.publish_heartbeat("Vantage", "connected")
        # Backdate last_seen by 10 seconds
        self.store._conn.execute(
            "UPDATE worker_heartbeat SET last_seen=? WHERE profile=?",
            ((datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(), "Vantage")
        )
        self.store._conn.commit()
        state = self.store.compute_mt5_state("Vantage")
        self.assertEqual(state["state"], "Degraded")

    def test_mt5_disconnected_state(self):
        """Very stale heartbeat (> 30s) => Disconnected."""
        self.store.publish_heartbeat("Vantage", "connected")
        self.store._conn.execute(
            "UPDATE worker_heartbeat SET last_seen=? WHERE profile=?",
            ((datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat(), "Vantage")
        )
        self.store._conn.commit()
        state = self.store.compute_mt5_state("Vantage")
        self.assertEqual(state["state"], "Disconnected")

    def test_mt5_no_heartbeat(self):
        """No heartbeat at all => Disconnected."""
        state = self.store.compute_mt5_state("Vantage")
        self.assertEqual(state["state"], "Disconnected")
        self.assertIn("No heartbeat", state["last_error"])

    def test_telegram_configured_and_api_ok(self):
        """Telegram configured + API reachable => configured=True, api_ok=True."""
        self.store.publish_heartbeat(
            "Vantage", "connected",
            telegram_configured=True, telegram_api_ok=True,
            telegram_bot_name="oak_manager_bot"
        )
        tg = self.store.compute_telegram_state("Vantage")
        self.assertTrue(tg["configured"])
        self.assertTrue(tg["api_ok"])
        self.assertEqual(tg["bot_name"], "oak_manager_bot")

    def test_telegram_configured_api_fail(self):
        """Telegram configured but API unreachable => configured=True, api_ok=False."""
        self.store.publish_heartbeat(
            "Vantage", "connected",
            telegram_configured=True, telegram_api_ok=False
        )
        tg = self.store.compute_telegram_state("Vantage")
        self.assertTrue(tg["configured"])
        self.assertFalse(tg["api_ok"])

    def test_telegram_not_configured(self):
        """No Telegram config => configured=False."""
        self.store.publish_heartbeat("Vantage", "connected")
        tg = self.store.compute_telegram_state("Vantage")
        self.assertFalse(tg["configured"])
        self.assertFalse(tg["api_ok"])

    def test_worker_connected_gui_not_init(self):
        """Worker connected but GUI hasn't read yet => still returns Connected from heartbeat."""
        self.store.publish_heartbeat("Vantage", "connected", server="Test", login=999)
        state = self.store.compute_mt5_state("Vantage")
        self.assertEqual(state["state"], "Connected")
        hb = self.store.get_heartbeat("Vantage")
        self.assertEqual(hb["server"], "Test")

    def test_profile_not_found(self):
        """Unknown profile returns Disconnected."""
        state = self.store.compute_mt5_state("NonExistent")
        self.assertEqual(state["state"], "Disconnected")

    def test_heartbeat_overwrites(self):
        """Second publish overwrites first (upsert on profile PK)."""
        self.store.publish_heartbeat("Vantage", "connected", balance=1000)
        self.store.publish_heartbeat("Vantage", "connected", balance=2000)
        hb = self.store.get_heartbeat("Vantage")
        self.assertAlmostEqual(hb["balance"], 2000)


if __name__ == "__main__":
    unittest.main()
