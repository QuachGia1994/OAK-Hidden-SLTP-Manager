"""MT4/MT5 comparison server tests for the v72 timing contract."""

import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import mt4_mt5_server


PAIR_DIRS = {
    "XAUUSD": "BUY",
    "GBPUSD": "SELL",
    "GBPAUD": "BUY",
    "GBPJPY": "BUY",
    "GBPCAD": "SELL",
}
PAIR_ENTRIES = {
    "XAUUSD": "12:49",
    "GBPUSD": "13:00",
    "GBPAUD": "13:00",
    "GBPJPY": "13:00",
    "GBPCAD": "13:00",
}
PAIR_GROUPS = {symbol: "BT" for symbol in mt4_mt5_server.SIGNAL_PAIRS}


def _payload():
    payload = {"broker": "MT4", "time": "12:00", "slot": 12, "logic_version": 73}
    for symbol in mt4_mt5_server.SIGNAL_PAIRS:
        key = symbol.lower()
        payload[f"{key}_signal"] = PAIR_DIRS[symbol]
        payload[f"{key}_entry"] = PAIR_ENTRIES[symbol]
        payload[f"{key}_group"] = PAIR_GROUPS[symbol]
    return payload


def _context():
    return mt4_mt5_server.calculate_context(12, PAIR_DIRS, PAIR_ENTRIES, PAIR_GROUPS)


class BrokerClockServerTests(unittest.TestCase):
    def test_server_clock_fails_closed_before_mt5_is_ready(self) -> None:
        with patch.object(mt4_mt5_server, "mt5_ready", False):
            with self.assertRaisesRegex(RuntimeError, "broker clock is unknown"):
                mt4_mt5_server.get_broker_time()

    def test_server_uses_shared_broker_clock(self) -> None:
        expected = datetime(2026, 7, 22, 15)
        with patch.object(mt4_mt5_server, "mt5_ready", True), patch.object(
            mt4_mt5_server.BROKER_CLOCK, "now", return_value=expected
        ):
            self.assertEqual(mt4_mt5_server.get_broker_time(), expected)

    def test_broker_clock_conversion_uses_terminal_timestamp_mode(self) -> None:
        value = datetime(2026, 3, 30, 16)
        expected = int(datetime(2026, 3, 30, 16, tzinfo=timezone.utc).timestamp())
        with patch.object(
            mt4_mt5_server.BROKER_CLOCK,
            "mt5_timestamp_from_broker_datetime",
            return_value=expected,
        ) as convert:
            self.assertEqual(mt4_mt5_server.broker_time_to_ts(value, 16), expected)
        convert.assert_called_once_with(value)

    def test_endpoint_delivers_matching_context_once(self) -> None:
        broker_dt = datetime(2026, 8, 6, 12, 1)
        with tempfile.TemporaryDirectory() as temp_dir:
            mt4_mt5_server._deliveries_in_progress.clear()
            with (
                patch.object(mt4_mt5_server, "_delivery_state_path", f"{temp_dir}/state.json"),
                patch.object(mt4_mt5_server, "get_broker_time", return_value=broker_dt),
                patch.object(mt4_mt5_server, "fetch_mt5_data", return_value=_context()),
                patch.object(mt4_mt5_server, "send_telegram", return_value=b"ok") as send,
            ):
                client = mt4_mt5_server.app.test_client()
                first = client.post("/mt4_data", json=_payload())
                duplicate = client.post("/mt4_data", json=_payload())
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["status"], "ok")
        self.assertEqual(duplicate.get_json()["status"], "duplicate")
        send.assert_called_once()

    def test_payload_rejects_gbp_entry_not_deferred_from_xau(self) -> None:
        payload = _payload()
        payload["gbpusd_entry"] = "12:49"
        response = mt4_mt5_server.app.test_client().post("/mt4_data", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("next full hour", response.get_json()["error"])

    def test_server_enforces_the_slot_specific_gbpaud_mapping(self) -> None:
        for slot in mt4_mt5_server.TARGET_HOURS:
            with self.subTest(slot=slot):
                xau_direction = "SELL" if slot in (3, 14, 16) else "BUY"
                directions = {symbol: "BUY" for symbol in mt4_mt5_server.SIGNAL_PAIRS}
                directions["XAUUSD"] = xau_direction
                xau_entry = f"{slot:02d}:49"
                gbp_entry = f"{slot + 1:02d}:00"
                entries = {symbol: gbp_entry for symbol in mt4_mt5_server.SIGNAL_PAIRS}
                entries["XAUUSD"] = xau_entry
                self.assertIsNone(mt4_mt5_server._payload_contract_error(slot, directions, entries))
                directions["XAUUSD"] = "SELL" if xau_direction == "BUY" else "BUY"
                self.assertEqual(
                    mt4_mt5_server._payload_contract_error(slot, directions, entries),
                    "XAUUSD signal does not follow slot GBPAUD mapping",
                )

    def test_wait_is_retryable_without_telegram(self) -> None:
        payload = _payload()
        payload["gbpaud_signal"] = "WAIT"
        payload["gbpaud_entry"] = ""
        payload["xauusd_signal"] = "WAIT"
        payload["xauusd_entry"] = ""
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            mt4_mt5_server, "_delivery_state_path", f"{temp_dir}/state.json"
        ), patch.object(
            mt4_mt5_server, "get_broker_time", return_value=datetime(2026, 8, 6, 12, 5)
        ), patch.object(mt4_mt5_server, "send_telegram") as send:
            response = mt4_mt5_server.app.test_client().post("/mt4_data", json=payload)
        self.assertEqual(response.status_code, 425)
        self.assertEqual(response.get_json()["reason"], "MT4_WAIT")
        send.assert_not_called()

    def test_non_xau_mt4_wait_is_also_retryable(self) -> None:
        payload = _payload()
        payload["gbpjpy_signal"] = "WAIT"
        payload["gbpjpy_entry"] = ""
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            mt4_mt5_server, "_delivery_state_path", f"{temp_dir}/state.json"
        ), patch.object(
            mt4_mt5_server, "get_broker_time", return_value=datetime(2026, 8, 6, 12, 5)
        ), patch.object(mt4_mt5_server, "send_telegram") as send:
            response = mt4_mt5_server.app.test_client().post("/mt4_data", json=payload)
        self.assertEqual(response.status_code, 425)
        self.assertEqual(response.get_json()["reason"], "MT4_WAIT")
        send.assert_not_called()

    def test_non_xau_mt5_wait_releases_delivery_for_retry(self) -> None:
        mt5_dirs = {**PAIR_DIRS, "GBPJPY": "WAIT"}
        mt5_entries = {**PAIR_ENTRIES, "GBPJPY": None}
        mt5_context = mt4_mt5_server.calculate_context(12, mt5_dirs, mt5_entries, PAIR_GROUPS)
        with tempfile.TemporaryDirectory() as temp_dir:
            mt4_mt5_server._deliveries_in_progress.clear()
            with (
                patch.object(mt4_mt5_server, "_delivery_state_path", f"{temp_dir}/state.json"),
                patch.object(mt4_mt5_server, "get_broker_time", return_value=datetime(2026, 8, 6, 12, 5)),
                patch.object(mt4_mt5_server, "fetch_mt5_data", return_value=mt5_context),
                patch.object(mt4_mt5_server, "send_telegram") as send,
            ):
                response = mt4_mt5_server.app.test_client().post("/mt4_data", json=_payload())
        self.assertEqual(response.status_code, 425)
        self.assertEqual(response.get_json()["reason"], "MT5_WAIT")
        self.assertFalse(mt4_mt5_server._deliveries_in_progress)
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
