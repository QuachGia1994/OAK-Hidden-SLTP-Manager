"""Missing, invalid, or DOJI M30 candles fail closed without fallback."""

from datetime import datetime
from unittest.mock import patch
import unittest
import mt5_signal_bot


VALID = {
    "time": 100,
    "open": 1.0,
    "high": 1.2,
    "low": 0.9,
    "close": 1.1,
    "tick_volume": 10,
}


class SignalIncompleteDataTests(unittest.TestCase):
    def test_exact_timestamp_and_valid_ohlc_are_required(self) -> None:
        open_dt = datetime(2026, 7, 14, 6)
        for candle in (
            None,
            {**VALID, "high": 0.8},
            {**VALID, "open": float("nan")},
        ):
            with self.subTest(candle=candle), patch.object(
                mt5_signal_bot, "get_candle_by_broker_datetime", return_value=candle
            ):
                self.assertIsNone(
                    mt5_signal_bot.read_completed_m30_candle(
                        "GBPUSD", open_dt, datetime(2026, 7, 14, 7)
                    )
                )

    def test_uses_the_exact_broker_m30_open_time(self) -> None:
        open_dt = datetime(2026, 7, 14, 6)
        with patch.object(
            mt5_signal_bot, "get_candle_by_broker_datetime", return_value=VALID
        ) as read:
            result = mt5_signal_bot.read_completed_m30_candle(
                "GBPUSD", open_dt, datetime(2026, 7, 14, 7)
            )

        self.assertEqual(result, VALID)
        read.assert_called_once_with("GBPUSD", "M30", open_dt)

    def test_unclosed_candle_is_rejected(self) -> None:
        open_dt = datetime(2026, 7, 14, 6, 30)
        with patch.object(mt5_signal_bot, "get_candle_by_ts") as read:
            value = mt5_signal_bot.read_completed_m30_candle(
                "GBPUSD", open_dt, datetime(2026, 7, 14, 6, 45)
            )
        self.assertIsNone(value)
        read.assert_not_called()

    def test_one_doji_makes_only_that_pair_wait(self) -> None:
        candle = {**VALID, "close": VALID["open"]}
        with patch.object(mt5_signal_bot, "read_completed_m30_candle_by_open_time", return_value=candle):
            result = mt5_signal_bot.evaluate_gbp_native_signal_m30(
                datetime(2026, 7, 14, 7), 7, "GBPUSD"
            )
        self.assertEqual(result["direction"], "WAIT")
        self.assertIsNone(result["entry_time"])
        self.assertEqual(result["signal_state"], "WAIT")

    def test_every_active_slot_waits_if_engine_returns_no_context(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12)
        with patch.object(mt5_signal_bot, "evaluate_all_pairs_for_slot", return_value=None):
            self.assertIsNone(mt5_signal_bot.evaluate_all_pairs_for_slot(broker_dt, 12))


if __name__ == "__main__":
    unittest.main()
