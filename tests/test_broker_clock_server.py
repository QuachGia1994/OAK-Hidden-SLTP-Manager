"""MT4/MT5 comparison server tests for the v71 signal contract."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import mt4_mt5_server


PAIR_DIRS = {symbol: "BUY" for symbol in mt4_mt5_server.SIGNAL_PAIRS}
PAIR_GROUPS = {symbol: "BT" for symbol in mt4_mt5_server.SIGNAL_PAIRS}


def _payload(slot: int, entry_time: str | None = None) -> dict[str, object]:
    entry = entry_time or f"{slot:02d}:11"
    payload: dict[str, object] = {
        "broker": "MT4",
        "time": f"{slot:02d}:00",
        "slot": slot,
        "entry_time": entry,
        "terminal_wait": False,
    }
    for symbol in mt4_mt5_server.SIGNAL_PAIRS:
        payload[f"{symbol.lower()}_signal"] = PAIR_DIRS[symbol]
        payload[f"{symbol.lower()}_group"] = PAIR_GROUPS[symbol]
    return payload


def _context(entry_time: str = "12:11", pair_dirs=None) -> dict[str, object]:
    return mt4_mt5_server.calculate_context(
        12,
        entry_time,
        pair_dirs or PAIR_DIRS,
        PAIR_GROUPS,
    )


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
        broker_value = datetime(2026, 3, 30, 16)
        expected = int(datetime(2026, 3, 30, 16, tzinfo=timezone.utc).timestamp())
        with patch.object(
            mt4_mt5_server.BROKER_CLOCK,
            "mt5_timestamp_from_broker_datetime",
            return_value=expected,
        ) as convert:
            timestamp = mt4_mt5_server.broker_time_to_ts(broker_value, 16)
        convert.assert_called_once_with(broker_value)
        self.assertEqual(timestamp, expected)

    def test_h9_plus_1_entry_reads_h1_0900_0800_0700_0600(self) -> None:
        captured: list[datetime] = []
        directions = iter(("TANG", "TANG", "GIAM", "TANG"))

        def read(_symbol, _timeframe, candle_dt, _fallback):
            captured.append(candle_dt)
            return next(directions)

        with patch.object(mt4_mt5_server, "_resolved_direction", side_effect=read):
            result = mt4_mt5_server._h1_context_for_pair(
                datetime(2026, 7, 29, 10, 1), 9, "XAUUSD", "10:25"
            )
        self.assertEqual(captured, [
            datetime(2026, 7, 29, 9),
            datetime(2026, 7, 29, 8),
            datetime(2026, 7, 29, 7),
            datetime(2026, 7, 29, 6),
        ])
        self.assertEqual(result["group"], "BT")
        self.assertEqual(result["signal"], "BUY")

    def test_h9_h11_entry_reverses_signal_base(self) -> None:
        with patch.object(
            mt4_mt5_server,
            "_resolved_direction",
            side_effect=("TANG", "TANG", "GIAM", "TANG"),
        ):
            result = mt4_mt5_server._h1_context_for_pair(
                datetime(2026, 7, 29, 9, 5), 9, "GBPUSD", "09:11"
            )
        self.assertEqual(result["group"], "BT")
        self.assertEqual(result["signal"], "SELL")

    def test_h3_uses_previous_session_0400_0300_0200(self) -> None:
        captured: list[datetime] = []

        def read(_symbol, _timeframe, candle_dt, _fallback):
            captured.append(candle_dt)
            return {4: "TANG", 3: "TANG", 2: "GIAM"}[candle_dt.hour]

        with patch.object(mt4_mt5_server, "_resolved_direction", side_effect=read):
            result = mt4_mt5_server._h3_source_context(
                datetime(2026, 7, 29, 3), "XAUUSD"
            )
        self.assertEqual(captured, [
            datetime(2026, 7, 28, 4),
            datetime(2026, 7, 28, 3),
            datetime(2026, 7, 28, 2),
        ])
        self.assertEqual(result["group"], "BT")
        self.assertEqual(result["signal"], "BUY")

    def test_thursday_h3_monday_sw_waits_until_h7(self) -> None:
        monday_sw = {"signal": "BUY", "group": "SW", "directions": (), "source": None}
        with patch.object(mt4_mt5_server, "_h3_source_context", return_value=monday_sw) as source:
            result = mt4_mt5_server._h3_context_for_pair(
                datetime(2026, 7, 30, 3), "XAUUSD"
            )
        self.assertEqual(result["signal"], "WAIT")
        self.assertTrue(result["thursday_wait_until_h7"])
        source.assert_called_once_with(datetime(2026, 7, 27, 3), "XAUUSD")

    def test_thursday_h3_sw_bypasses_the_stage_a_entry_wait(self) -> None:
        sw = {"signal": "WAIT", "group": "SW", "directions": (), "source": None}
        bt = {"signal": "BUY", "group": "BT", "directions": (), "source": None}
        with (
            patch.object(mt4_mt5_server, "mt5_ready", True),
            patch.object(
                mt4_mt5_server,
                "_h3_context_for_pair",
                side_effect=lambda _dt, symbol: sw if symbol == "XAUUSD" else bt,
            ),
            patch.object(mt4_mt5_server, "_fetch_stage_a_entry") as stage_a,
        ):
            result = mt4_mt5_server.fetch_mt5_data(datetime(2026, 7, 30, 3, 1), 3)
        self.assertEqual(result["signal"], "WAIT")
        self.assertEqual(result["pair_groups"]["XAUUSD"], "SW")
        self.assertIsNone(result["entry_time"])
        stage_a.assert_not_called()

    def test_endpoint_delivers_matching_five_pair_context_once(self) -> None:
        broker_dt = datetime(2026, 8, 6, 12, 1)
        payload = _payload(12)
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/state.json"
            mt4_mt5_server._deliveries_in_progress.clear()
            with (
                patch.object(mt4_mt5_server, "_delivery_state_path", state_path),
                patch.object(mt4_mt5_server, "get_broker_time", return_value=broker_dt),
                patch.object(mt4_mt5_server.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
                patch.object(mt4_mt5_server, "fetch_mt5_data", return_value=_context()),
                patch.object(mt4_mt5_server, "send_telegram", return_value=b"ok") as send,
            ):
                client = mt4_mt5_server.app.test_client()
                first = client.post("/mt4_data", json=payload)
                duplicate = client.post("/mt4_data", json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["status"], "ok")
        self.assertEqual(duplicate.get_json()["status"], "duplicate")
        send.assert_called_once()

    def test_wait_is_retryable_without_telegram_or_state(self) -> None:
        payload = _payload(12)
        payload["xauusd_signal"] = "WAIT"
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/state.json"
            with (
                patch.object(mt4_mt5_server, "_delivery_state_path", state_path),
                patch.object(mt4_mt5_server, "get_broker_time", return_value=datetime(2026, 8, 6, 12, 5)),
                patch.object(mt4_mt5_server.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
                patch.object(mt4_mt5_server, "send_telegram") as send,
            ):
                response = mt4_mt5_server.app.test_client().post("/mt4_data", json=payload)
        self.assertEqual(response.status_code, 425)
        self.assertEqual(response.get_json()["reason"], "MT4_WAIT")
        self.assertFalse(Path(state_path).exists())
        send.assert_not_called()

    def test_thursday_terminal_wait_completes_without_telegram(self) -> None:
        payload = _payload(3)
        payload.update({
            "terminal_wait": True,
            "entry_time": "",
            "xauusd_signal": "WAIT",
            "xauusd_group": "SW",
        })
        mt5_wait = mt4_mt5_server.calculate_context(
            3,
            "03:11",
            {**PAIR_DIRS, "XAUUSD": "WAIT"},
            {**PAIR_GROUPS, "XAUUSD": "SW"},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(mt4_mt5_server, "_delivery_state_path", f"{temp_dir}/state.json"),
                patch.object(mt4_mt5_server, "get_broker_time", return_value=datetime(2026, 7, 30, 3, 5)),
                patch.object(mt4_mt5_server.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
                patch.object(mt4_mt5_server, "fetch_mt5_data", return_value=mt5_wait),
                patch.object(mt4_mt5_server, "send_telegram") as send,
            ):
                response = mt4_mt5_server.app.test_client().post("/mt4_data", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "wait_until_h7")
        self.assertTrue(response.get_json()["matched"])
        send.assert_not_called()

    def test_terminal_wait_mismatch_remains_retryable(self) -> None:
        payload = _payload(3)
        payload.update({
            "terminal_wait": True,
            "entry_time": "",
            "xauusd_signal": "WAIT",
            "xauusd_group": "SW",
        })
        mt5_incomplete = mt4_mt5_server.calculate_context(
            3,
            "03:11",
            {**PAIR_DIRS, "XAUUSD": "WAIT"},
            {**PAIR_GROUPS, "XAUUSD": None},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/state.json"
            with (
                patch.object(mt4_mt5_server, "_delivery_state_path", state_path),
                patch.object(mt4_mt5_server, "get_broker_time", return_value=datetime(2026, 7, 30, 3, 5)),
                patch.object(mt4_mt5_server.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
                patch.object(mt4_mt5_server, "fetch_mt5_data", return_value=mt5_incomplete),
                patch.object(mt4_mt5_server, "send_telegram") as send,
            ):
                response = mt4_mt5_server.app.test_client().post("/mt4_data", json=payload)
        self.assertEqual(response.status_code, 425)
        self.assertEqual(response.get_json()["reason"], "MT5_H3_CONTEXT_MISMATCH")
        self.assertFalse(Path(state_path).exists())
        send.assert_not_called()

    def test_late_resolved_slot_is_persistently_missed(self) -> None:
        broker_dt = datetime(2026, 8, 6, 12, 12)
        payload = _payload(12, "12:11")
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/state.json"
            mt4_mt5_server._deliveries_in_progress.clear()
            with (
                patch.object(mt4_mt5_server, "_delivery_state_path", state_path),
                patch.object(mt4_mt5_server, "get_broker_time", return_value=broker_dt),
                patch.object(mt4_mt5_server.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
                patch.object(mt4_mt5_server, "fetch_mt5_data", return_value=_context()),
                patch.object(mt4_mt5_server, "send_telegram") as send,
            ):
                response = mt4_mt5_server.app.test_client().post("/mt4_data", json=payload)
                persisted = json.loads(Path(state_path).read_text(encoding="utf-8"))
        self.assertEqual(response.get_json()["status"], "missed")
        self.assertIn("2026-08-06:12", persisted["missed"])
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
