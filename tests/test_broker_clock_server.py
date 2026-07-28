"""MT4/MT5 server integration tests for the shared broker clock."""

import json
import unittest
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import mt4_mt5_server


def _mt4_payload(slot: int, time_value: str) -> dict[str, object]:
    return {
        "broker": "MT4",
        "time": time_value,
        "slot": slot,
        "gbpusd_h1_1": "TANG",
        "gbpusd_h1_2": "GIAM",
        "gbpaud_h1_1": "GIAM",
        "gbpaud_h1_2": "TANG",
        "xau_m15_1": "TANG",
        "xau_m15_2": "TANG",
        "xau_m15_3": "TANG",
    }


def _mt5_context(slot: int) -> dict[str, object]:
    context = dict(_mt4_payload(slot, f"{slot:02d}:00"))
    context.update({"signal": "BUY", "entry_time": f"{slot + 1:02d}:25"})
    return context


def _calculated_context(payload: dict[str, object]) -> dict[str, object]:
    context = mt4_mt5_server.calculate_context(
        payload["slot"],
        payload["gbpusd_h1_1"],
        payload["gbpusd_h1_2"],
        payload["gbpaud_h1_1"],
        payload["gbpaud_h1_2"],
        (payload["xau_m15_1"], payload["xau_m15_2"], payload["xau_m15_3"]),
    )
    return {**payload, **context}


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
        self.assertTrue(mt4_mt5_server.is_deactivated_slot(datetime(2026, 7, 21, 4, 0), 4))
        self.assertNotIn(5, mt4_mt5_server.TARGET_HOURS)
        self.assertFalse(mt4_mt5_server.is_slot_suppressed(special_thursday, 12))
        self.assertFalse(mt4_mt5_server.is_slot_suppressed(post_special_monday, 16))
        self.assertFalse(mt4_mt5_server.is_special_day(datetime(2026, 12, 31, 3, 0)))

    def test_endpoint_accepts_special_h12_without_suppressing(self):
        broker_dt = datetime(2026, 8, 6, 12, 0)
        payload = _mt4_payload(12, "12:00")
        mt5_data = _mt5_context(12)
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
                response = mt4_mt5_server.app.test_client().post("/mt4_data", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")
        send.assert_called_once()

    def test_deactivated_h3_warns_once_and_is_restart_safe(self):
        broker_dt = datetime(2026, 8, 6, 3, 0)
        payload = _mt4_payload(3, "03:00")
        mt5_data = _mt5_context(3)
        mt5_data["entry_time"] = "04:49"
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

    def test_h1_results_drive_signal_and_m15_only_breaks_opposite_entry(self):
        opposite = mt4_mt5_server.calculate_context(
            12,
            "TANG", "GIAM",
            "GIAM", "TANG",
            ("TANG", "TANG", "TANG"),
        )
        self.assertEqual(opposite["signal"], "BUY")
        self.assertEqual(opposite["gbpusd_group"], "BT")
        self.assertEqual(opposite["gbpaud_signal"], "SELL")
        self.assertEqual(opposite["m15_group"], "SW")
        self.assertEqual(opposite["entry_time"], "13:25")

        same = mt4_mt5_server.calculate_context(
            12,
            "TANG", "GIAM",
            "TANG", "GIAM",
            (None, None, None),
        )
        self.assertEqual(same["signal"], "BUY")
        self.assertEqual(same["entry_time"], "12:11")

    def test_h3_uses_0449_as_the_late_opposite_entry(self):
        context = mt4_mt5_server.calculate_context(
            3,
            "TANG", "GIAM",
            "GIAM", "TANG",
            ("TANG", "TANG", "TANG"),
        )
        self.assertEqual(context["entry_time"], "04:49")

    def test_fetch_uses_yesterday_h1_and_skips_the_first_today_m15(self):
        broker_dt = datetime(2026, 8, 6, 9, 0)
        captured = []
        values = iter(("TANG", "GIAM", "GIAM", "TANG", "TANG", "TANG", "TANG"))

        def read_direction(symbol, timeframe, candle_dt, fallback_delta):
            captured.append((symbol, timeframe, candle_dt, fallback_delta))
            return next(values)

        with (
            patch.object(mt4_mt5_server, "mt5_ready", True),
            patch.object(mt4_mt5_server, "_resolved_direction", side_effect=read_direction),
        ):
            result = mt4_mt5_server.fetch_mt5_data(broker_dt, 9)

        self.assertEqual(result["entry_time"], "10:25")
        self.assertEqual(
            [(symbol, candle_dt) for symbol, _, candle_dt, _ in captured],
            [
                ("GBPUSD", datetime(2026, 8, 5, 8, 0)),
                ("GBPUSD", datetime(2026, 8, 5, 7, 0)),
                ("GBPAUD", datetime(2026, 8, 5, 8, 0)),
                ("GBPAUD", datetime(2026, 8, 5, 7, 0)),
                ("XAUUSD", datetime(2026, 8, 6, 8, 30)),
                ("XAUUSD", datetime(2026, 8, 6, 8, 15)),
                ("XAUUSD", datetime(2026, 8, 6, 8, 0)),
            ],
        )

    def test_fetch_does_not_read_m15_when_h1_derivations_match(self):
        broker_dt = datetime(2026, 8, 6, 9, 7)
        captured = []
        values = iter(("TANG", "GIAM", "TANG", "GIAM"))

        def read_direction(symbol, timeframe, candle_dt, fallback_delta):
            captured.append((symbol, timeframe, candle_dt, fallback_delta))
            return next(values)

        with (
            patch.object(mt4_mt5_server, "mt5_ready", True),
            patch.object(mt4_mt5_server, "_resolved_direction", side_effect=read_direction),
        ):
            result = mt4_mt5_server.fetch_mt5_data(broker_dt, 9)

        self.assertEqual(result["signal"], "BUY")
        self.assertEqual(result["entry_time"], "09:11")
        self.assertEqual([item[0] for item in captured], ["GBPUSD", "GBPUSD", "GBPAUD", "GBPAUD"])

    def test_fetch_does_not_read_m15_when_h1_is_incomplete(self):
        broker_dt = datetime(2026, 8, 6, 9, 7)
        captured = []
        values = iter((None, "GIAM", "TANG", "GIAM"))

        def read_direction(symbol, timeframe, candle_dt, fallback_delta):
            captured.append((symbol, timeframe, candle_dt, fallback_delta))
            return next(values)

        with (
            patch.object(mt4_mt5_server, "mt5_ready", True),
            patch.object(mt4_mt5_server, "_resolved_direction", side_effect=read_direction),
        ):
            result = mt4_mt5_server.fetch_mt5_data(broker_dt, 9)

        self.assertEqual(result["signal"], "WAIT")
        self.assertEqual([item[0] for item in captured], ["GBPUSD", "GBPUSD", "GBPAUD", "GBPAUD"])

    def test_wait_is_retryable_and_never_sends_or_completes_delivery(self):
        broker_dt = datetime(2026, 8, 6, 12, 5)
        payload = _mt4_payload(12, "12:00")
        payload["gbpusd_h1_1"] = "MISSING"
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/mt4_server_state.json"
            mt4_mt5_server._deliveries_in_progress.clear()
            with (
                patch.object(mt4_mt5_server, "_delivery_state_path", state_path),
                patch.object(mt4_mt5_server, "get_broker_time", return_value=broker_dt),
                patch.object(mt4_mt5_server.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
                patch.object(mt4_mt5_server, "fetch_mt5_data") as fetch,
                patch.object(mt4_mt5_server, "send_telegram") as send,
            ):
                response = mt4_mt5_server.app.test_client().post("/mt4_data", json=payload)

            self.assertEqual(response.status_code, 425)
            self.assertEqual(response.get_json()["reason"], "MT4_WAIT")
            self.assertFalse(Path(state_path).exists())
        fetch.assert_not_called()
        send.assert_not_called()

    def test_mt5_wait_releases_slot_for_a_later_resolved_retry(self):
        broker_dt = datetime(2026, 8, 6, 12, 5)
        payload = _mt4_payload(12, "12:00")
        resolved = _mt5_context(12)
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/mt4_server_state.json"
            mt4_mt5_server._deliveries_in_progress.clear()
            with (
                patch.object(mt4_mt5_server, "_delivery_state_path", state_path),
                patch.object(mt4_mt5_server, "get_broker_time", return_value=broker_dt),
                patch.object(mt4_mt5_server.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
                patch.object(
                    mt4_mt5_server,
                    "fetch_mt5_data",
                    side_effect=({"signal": "WAIT", "entry_time": None}, resolved),
                ),
                patch.object(mt4_mt5_server, "send_telegram", return_value=b"ok") as send,
            ):
                client = mt4_mt5_server.app.test_client()
                first = client.post("/mt4_data", json=payload)
                second = client.post("/mt4_data", json=payload)

        self.assertEqual(first.status_code, 425)
        self.assertEqual(first.get_json()["reason"], "MT5_WAIT")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json()["status"], "ok")
        send.assert_called_once()

    def test_late_resolved_slot_is_persistently_missed_without_telegram(self):
        broker_dt = datetime(2026, 8, 6, 12, 12)
        payload = _mt4_payload(12, "12:00")
        payload["gbpaud_h1_1"] = "TANG"
        payload["gbpaud_h1_2"] = "GIAM"
        resolved = _calculated_context(payload)
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/mt4_server_state.json"
            mt4_mt5_server._deliveries_in_progress.clear()
            with (
                patch.object(mt4_mt5_server, "_delivery_state_path", state_path),
                patch.object(mt4_mt5_server, "get_broker_time", return_value=broker_dt),
                patch.object(mt4_mt5_server.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
                patch.object(mt4_mt5_server, "fetch_mt5_data", return_value=resolved) as fetch,
                patch.object(mt4_mt5_server, "send_telegram") as send,
            ):
                client = mt4_mt5_server.app.test_client()
                first = client.post("/mt4_data", json=payload)
                mt4_mt5_server._deliveries_in_progress.clear()
                repeated = client.post("/mt4_data", json=payload)
            persisted = json.loads(Path(state_path).read_text(encoding="utf-8"))

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["status"], "missed")
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.get_json()["status"], "missed")
        self.assertIn("2026-08-06:12", persisted["missed"])
        fetch.assert_called_once()
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
