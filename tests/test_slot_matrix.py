"""Regression tests for the active logical GBP H1 slot matrix."""
from contextlib import ExitStack
from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


ACTIVE_SLOTS = (3, 4, 7, 9, 12, 14, 16)


def _result(hour: int) -> dict[str, object]:
    return {
        "signal": "BUY",
        "entry_time": f"{hour:02d}:11",
        "pair_dirs": {"XAUUSD": "BUY"},
    }


class SlotMatrixTests(unittest.TestCase):
    def test_removed_slots_are_suppressed(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        for hour in (2, 5, 11, 13, 15, 1500):
            with self.subTest(hour=hour):
                result = mt5_signal_bot.calculate_slot_signal(broker_dt, hour)
                self.assertEqual(result["signal"], "WAIT")
                self.assertTrue(result["suppressed"])

    def test_every_active_slot_uses_the_gbp_h1_context(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        legacy = (
            "analyze",
            "apply_xauusd_m30_logic",
            "evaluate_3_m30_classification_for_h3",
            "evaluate_4_m30_classification_before_hour",
            "evaluate_classification_for_slot",
            "evaluate_h3_m30_slot",
            "evaluate_m30_m15_slot",
            "evaluate_slot_candle_groups",
            "_lookup_h3_signal_today",
            "_lookup_h4_signal_today",
            "_lookup_h16_signal_yesterday",
            "_lookup_signal_from_log",
        )
        for hour in ACTIVE_SLOTS:
            with self.subTest(hour=hour), ExitStack() as stack:
                evaluate = stack.enter_context(
                    patch.object(mt5_signal_bot, "evaluate_gbp_h1_slot", return_value=_result(hour))
                )
                for name in legacy:
                    stack.enter_context(
                        patch.object(
                            mt5_signal_bot,
                            name,
                            side_effect=AssertionError(f"legacy path used: {name}"),
                            create=True,
                        )
                    )
                result = mt5_signal_bot.calculate_slot_signal(broker_dt, hour)
            evaluate.assert_called_once_with(broker_dt, hour, as_of_dt=broker_dt)
            self.assertEqual(result["signal"], "BUY")
            self.assertFalse(result.get("suppressed", False))

    def test_h4_and_thursday_h3_are_deactivated(self) -> None:
        with patch.object(
            mt5_signal_bot,
            "evaluate_gbp_h1_slot",
            side_effect=lambda _dt, hour, **kwargs: _result(hour),
        ):
            h4 = mt5_signal_bot.calculate_slot_signal(datetime(2026, 7, 14, 4), 4)
            thursday_h3 = mt5_signal_bot.calculate_slot_signal(datetime(2026, 7, 23, 3), 3)
            friday_h3 = mt5_signal_bot.calculate_slot_signal(datetime(2026, 7, 24, 3), 3)
        self.assertTrue(h4["deactivated"])
        self.assertTrue(thursday_h3["deactivated"])
        self.assertFalse(friday_h3.get("deactivated", False))

    def test_every_active_slot_waits_when_gbp_h1_context_is_missing(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        for hour in ACTIVE_SLOTS:
            with self.subTest(hour=hour), patch.object(
                mt5_signal_bot,
                "evaluate_gbp_h1_slot",
                return_value=None,
            ):
                result = mt5_signal_bot.calculate_slot_signal(broker_dt, hour)
            self.assertEqual(result["signal"], "WAIT")


if __name__ == "__main__":
    unittest.main()
