"""Missing candles and unresolved DOJI must fail closed."""
from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


DOJI = {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}


class SignalIncompleteDataTests(unittest.TestCase):
    def test_four_h1_missing_candle_returns_incomplete(self) -> None:
        with (
            patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1),
            patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=None),
        ):
            group, detail, candles = mt5_signal_bot.evaluate_classification_for_slot(
                datetime(2026, 7, 14, 12, 0),
                12,
            )

        self.assertIsNone(group)
        self.assertIn("missing H1", detail)
        self.assertEqual(candles, [])

    def test_four_h1_unresolved_doji_returns_incomplete(self) -> None:
        with (
            patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1),
            patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=DOJI),
            patch.object(mt5_signal_bot, "resolve_doji", return_value=None),
        ):
            group, detail, _candles = mt5_signal_bot.evaluate_classification_for_slot(
                datetime(2026, 7, 14, 12, 0),
                12,
            )

        self.assertIsNone(group)
        self.assertIn("unresolved DOJI", detail)

    def test_four_m30_missing_or_unresolved_returns_incomplete(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        with (
            patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1),
            patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=None),
        ):
            self.assertIsNone(
                mt5_signal_bot.evaluate_4_m30_classification_before_hour(broker_dt, 12)
            )
        with (
            patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1),
            patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=DOJI),
            patch.object(mt5_signal_bot, "resolve_doji", return_value=None),
        ):
            self.assertIsNone(
                mt5_signal_bot.evaluate_4_m30_classification_before_hour(broker_dt, 12)
            )

    def test_h3_three_m30_missing_or_unresolved_returns_incomplete(self) -> None:
        broker_dt = datetime(2026, 7, 14, 3, 0)
        with (
            patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1),
            patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=None),
        ):
            self.assertIsNone(mt5_signal_bot.evaluate_3_m30_classification_for_h3(broker_dt))
        with (
            patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1),
            patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=DOJI),
            patch.object(mt5_signal_bot, "resolve_doji", return_value=None),
        ):
            self.assertIsNone(mt5_signal_bot.evaluate_3_m30_classification_for_h3(broker_dt))

    def test_xau_m30_missing_or_unresolved_returns_none(self) -> None:
        broker_dt = datetime(2026, 7, 14, 9, 0)
        with (
            patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1),
            patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=None),
        ):
            self.assertIsNone(mt5_signal_bot.get_xauusd_m30_signal(broker_dt, 9))
        with (
            patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1),
            patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=DOJI),
            patch.object(mt5_signal_bot, "resolve_doji", return_value=None),
        ):
            self.assertIsNone(mt5_signal_bot.get_xauusd_m30_signal(broker_dt, 9))

    def test_slot_calculation_waits_on_incomplete_four_h1(self) -> None:
        broker_dt = datetime(2026, 7, 14, 6, 0)
        with (
            patch.object(
                mt5_signal_bot,
                "evaluate_4_m30_classification_before_hour",
                return_value="SW",
            ),
            patch.object(mt5_signal_bot, "_lookup_h3_signal_today", return_value="BUY"),
            patch.object(
                mt5_signal_bot,
                "evaluate_classification_for_slot",
                return_value=(None, "missing H1@05:00", []),
            ),
        ):
            result = mt5_signal_bot.calculate_slot_signal(broker_dt, 6)

        self.assertEqual(result["signal"], "WAIT")
        self.assertIn("incomplete", result["report"])


if __name__ == "__main__":
    unittest.main()
