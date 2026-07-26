"""MT4/MT5 server integration tests for the shared broker clock."""

import unittest
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch

import mt4_mt5_server


class BrokerClockServerTests(unittest.TestCase):
    def test_server_clock_fails_closed_before_mt5_is_ready(self):
        with patch.object(mt4_mt5_server, "mt5_ready", False):
            with self.assertRaisesRegex(RuntimeError, "broker clock is unknown"):
                mt4_mt5_server.get_broker_time()

    def test_server_uses_shared_broker_clock(self):
        expected = datetime(2026, 7, 22, 15, 0)
        with patch.object(mt4_mt5_server, "mt5_ready", True):
            with patch.object(mt4_mt5_server.BROKER_CLOCK, "now", return_value=expected):
                self.assertEqual(mt4_mt5_server.get_broker_time(), expected)

    def test_broker_clock_conversion_uses_mt5_timestamp_encoding_mode(self):
        broker_value = datetime(2026, 3, 30, 16, 0)
        expected_timestamp = int(datetime(2026, 3, 30, 16, 0, tzinfo=timezone.utc).timestamp())
        with patch.object(
            mt4_mt5_server.BROKER_CLOCK,
            "mt5_timestamp_from_broker_datetime",
            return_value=expected_timestamp,
        ) as convert:
            timestamp = mt4_mt5_server.broker_time_to_ts(broker_value, 16)

        convert.assert_called_once_with(broker_value)
        self.assertEqual(timestamp, expected_timestamp)

    def test_special_and_post_special_slots_match_signal_bot_contract(self):
        special_thursday = datetime(2026, 8, 6, 3, 0)
        post_special_monday = datetime(2026, 8, 10, 12, 0)
        self.assertTrue(mt4_mt5_server.is_deactivated_slot(special_thursday, 3))
        self.assertTrue(mt4_mt5_server.is_deactivated_slot(datetime(2026, 7, 21, 4, 45), 4))
        self.assertTrue(mt4_mt5_server.is_deactivated_slot(datetime(2026, 7, 21, 5, 45), 5))
        self.assertTrue(mt4_mt5_server.is_slot_suppressed(special_thursday, 12))
        self.assertTrue(mt4_mt5_server.is_slot_suppressed(post_special_monday, 16))
        self.assertFalse(mt4_mt5_server.is_special_day(datetime(2026, 12, 31, 3, 0)))

    def test_endpoint_suppresses_special_h12_without_telegram(self):
        broker_dt = datetime(2026, 8, 6, 12, 0)
        payload = {
            "broker": "MT4",
            "time": "12:00",
            "slot": 12,
            "pattern_hour": 11,
            "m35": "TANG",
            "m40": "TANG",
            "m30": "TANG",
        }
        with (
            patch.object(mt4_mt5_server, "get_broker_time", return_value=broker_dt),
            patch.object(mt4_mt5_server.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
            patch.object(mt4_mt5_server, "send_telegram") as send,
        ):
            response = mt4_mt5_server.app.test_client().post("/mt4_data", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "suppressed")
        send.assert_not_called()

    def test_deactivated_h3_warns_once_and_is_restart_safe(self):
        broker_dt = datetime(2026, 8, 6, 3, 0)
        payload = {
            "broker": "MT4",
            "time": "03:00",
            "slot": 3,
            "pattern_hour": 2,
            "m35": "TANG",
            "m40": "TANG",
            "m30": "TANG",
        }
        mt5_data = {"m35": "TANG", "m40": "TANG", "m30": "TANG", "signal": "BUY"}
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/mt4_server_state.json"
            mt4_mt5_server._deliveries_in_progress.clear()
            with (
                patch.object(mt4_mt5_server, "_delivery_state_path", state_path),
                patch.object(mt4_mt5_server, "get_broker_time", return_value=broker_dt),
                patch.object(mt4_mt5_server.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
                patch.object(mt4_mt5_server, "fetch_mt5_data", return_value=mt5_data),
                patch.object(mt4_mt5_server, "send_telegram", return_value=b"ok") as send,
            ):
                client = mt4_mt5_server.app.test_client()
                first = client.post("/mt4_data", json=payload)
                mt4_mt5_server._deliveries_in_progress.clear()  # simulate process restart
                duplicate = client.post("/mt4_data", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.get_json()["deactivated"])
        self.assertEqual(duplicate.get_json()["status"], "duplicate")
        self.assertIn("KHONG VAO LENH", send.call_args.args[0])
        self.assertNotIn("=> Mua", send.call_args.args[0])
        send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
