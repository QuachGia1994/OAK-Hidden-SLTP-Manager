"""Missing candles and unresolved DOJI must fail closed."""
from contextlib import ExitStack
from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


DOJI = {"open": 1.0, "high": 2.0, "low": 0.0, "close": 1.0}
ACTIVE_SLOTS = (3, 4, 6, 9, 12, 14, 16)
LEGACY_SEAMS = (
    "analyze",
    "apply_xauusd_m30_logic",
    "evaluate_3_m30_classification_for_h3",
    "evaluate_4_m30_classification_before_hour",
    "evaluate_classification_for_slot",
    "evaluate_h3_m30_slot",
    "evaluate_m30_m15_slot",
    "evaluate_slot_candle_groups",
)


class SignalIncompleteDataTests(unittest.TestCase):
    def test_previous_day_gbp_h1_missing_or_unresolved_doji_is_incomplete(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        with (
            patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1),
            patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=None),
        ):
            self.assertIsNone(mt5_signal_bot.evaluate_previous_day_gbp_h1_pair(broker_dt, 12, "GBPUSD"))
        with (
            patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1),
            patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=DOJI),
            patch.object(mt5_signal_bot, "resolve_doji", return_value=None),
        ):
            self.assertIsNone(mt5_signal_bot.evaluate_previous_day_gbp_h1_pair(broker_dt, 12, "GBPUSD"))

    def test_xau_m15_missing_or_unresolved_doji_is_incomplete(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        with patch.object(mt5_signal_bot, "_lookback_candle_direction", return_value=None):
            self.assertIsNone(mt5_signal_bot.evaluate_xauusd_m15_group_for_slot(broker_dt, 12))
        with (
            patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1),
            patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=DOJI),
            patch.object(mt5_signal_bot, "resolve_doji", return_value=None),
        ):
            self.assertIsNone(mt5_signal_bot.evaluate_xauusd_m15_group_for_slot(broker_dt, 12))

    def test_every_active_slot_waits_when_new_context_is_incomplete(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        for hour in ACTIVE_SLOTS:
            with self.subTest(hour=hour), ExitStack() as stack:
                stack.enter_context(patch.object(mt5_signal_bot, "evaluate_gbp_h1_slot", return_value=None))
                for name in LEGACY_SEAMS:
                    stack.enter_context(
                        patch.object(
                            mt5_signal_bot,
                            name,
                            side_effect=AssertionError(f"legacy fallback used: {name}"),
                            create=True,
                        )
                    )
                result = mt5_signal_bot.calculate_slot_signal(broker_dt, hour)
            self.assertEqual(result["signal"], "WAIT")


if __name__ == "__main__":
    unittest.main()
