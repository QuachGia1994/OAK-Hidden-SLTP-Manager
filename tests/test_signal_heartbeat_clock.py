"""Signal heartbeat exposes Broker clock only when it is trustworthy."""
from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


class SignalHeartbeatClockTests(unittest.TestCase):
    def test_clock_failure_publishes_degraded_without_clock_fields(self) -> None:
        with (
            patch.object(mt5_signal_bot, "load_profile_config", return_value={}),
            patch.object(mt5_signal_bot, "resolve_telegram_token", return_value=""),
            patch.object(mt5_signal_bot._store, "publish_heartbeat") as publish,
        ):
            mt5_signal_bot.publish_heartbeat(
                "Vantage",
                mt5_connected=False,
                mt5_error="Broker clock unavailable",
                broker_dt=None,
            )

        payload = publish.call_args.kwargs
        self.assertEqual(payload["state"], "degraded")
        self.assertEqual(payload["last_error"], "Broker clock unavailable")
        self.assertEqual(payload["broker_time"], "")
        self.assertIsNone(payload["broker_utc_offset"])
        self.assertEqual(payload["broker_observed_at_utc"], "")
        self.assertFalse(payload["preserve_broker_clock"])

    def test_connected_heartbeat_publishes_validated_clock_fields(self) -> None:
        broker_dt = datetime(2026, 7, 20, 4, 0)
        with (
            patch.object(mt5_signal_bot, "load_profile_config", return_value={}),
            patch.object(mt5_signal_bot, "resolve_telegram_token", return_value=""),
            patch.object(mt5_signal_bot.mt5, "account_info", return_value=None),
            patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
            patch.object(mt5_signal_bot._store, "publish_heartbeat") as publish,
        ):
            mt5_signal_bot.publish_heartbeat(
                "Vantage",
                mt5_connected=True,
                broker_dt=broker_dt,
            )

        payload = publish.call_args.kwargs
        self.assertEqual(payload["state"], "connected")
        self.assertEqual(payload["broker_time"], "2026-07-20T04:00:00")
        self.assertEqual(payload["broker_utc_offset"], 3)
        self.assertTrue(payload["broker_observed_at_utc"].endswith("+00:00"))


if __name__ == "__main__":
    unittest.main()
