"""Regression tests for the active logical slot matrix."""
from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


class SlotMatrixTests(unittest.TestCase):
    def test_removed_slots_are_suppressed(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)

        for hour in (2, 11, 13, 15, 1500):
            with self.subTest(hour=hour):
                result = mt5_signal_bot.calculate_slot_signal(broker_dt, hour)
                self.assertEqual(result["signal"], "WAIT")
                self.assertTrue(result["suppressed"])

    def test_h3_uses_monday_history_on_thursday(self) -> None:
        thursday = datetime(2026, 7, 23, 3, 0)

        with patch.object(
            mt5_signal_bot,
            "_lookup_historical_t2_signal",
            return_value="BUY",
        ), patch.object(
            mt5_signal_bot,
            "evaluate_3_m30_classification_for_h3",
            return_value="SW",
        ):
            result = mt5_signal_bot.calculate_slot_signal(thursday, 3)

        self.assertEqual(result["signal"], "BUY")
        self.assertEqual(result["pair_dirs"], {"XAUUSD": "BUY", "GBPAUD": "SELL"})
        self.assertTrue(result["deactivated"])

    def test_special_thursday_h3_is_saved_as_deactivated_direction(self) -> None:
        special_thursday = datetime(2026, 8, 6, 3, 0)

        with patch.object(
            mt5_signal_bot,
            "_lookup_historical_t2_signal",
            return_value="SELL",
        ), patch.object(
            mt5_signal_bot,
            "evaluate_3_m30_classification_for_h3",
            return_value="SW",
        ):
            result = mt5_signal_bot.calculate_slot_signal(special_thursday, 3)

        self.assertEqual(result["signal"], "SELL")
        self.assertEqual(result["pair_dirs"], {"XAUUSD": "SELL", "GBPAUD": "BUY"})
        self.assertTrue(result["deactivated"])

    def test_h16_sw_branch_compares_h6_and_h12(self) -> None:
        thursday = datetime(2026, 7, 23, 16, 0)

        with (
            patch.object(mt5_signal_bot, "evaluate_4_m30_classification_before_hour", return_value="SW"),
            patch.object(
                mt5_signal_bot,
                "_lookup_signal_from_log",
                side_effect=lambda _dt, hour: {6: "BUY", 12: "SELL"}.get(hour),
            ) as lookup,
        ):
            result = mt5_signal_bot.calculate_slot_signal(thursday, 16)

        self.assertEqual(result["signal"], "BUY")
        self.assertEqual([call.args[1] for call in lookup.call_args_list], [6, 12])

    def test_h16_bt_branch_compares_h9_and_h14(self) -> None:
        thursday = datetime(2026, 7, 23, 16, 0)

        with (
            patch.object(mt5_signal_bot, "evaluate_4_m30_classification_before_hour", return_value="BT"),
            patch.object(
                mt5_signal_bot,
                "_lookup_signal_from_log",
                side_effect=lambda _dt, hour: {9: "SELL", 14: "SELL"}.get(hour),
            ) as lookup,
        ):
            result = mt5_signal_bot.calculate_slot_signal(thursday, 16)

        self.assertEqual(result["signal"], "BUY")
        self.assertEqual([call.args[1] for call in lookup.call_args_list], [9, 14])

    def test_h16_waits_when_a_dependency_is_missing(self) -> None:
        thursday = datetime(2026, 7, 23, 16, 0)

        with (
            patch.object(mt5_signal_bot, "evaluate_4_m30_classification_before_hour", return_value="SW"),
            patch.object(
                mt5_signal_bot,
                "_lookup_signal_from_log",
                side_effect=lambda _dt, hour: "BUY" if hour == 6 else None,
            ),
        ):
            result = mt5_signal_bot.calculate_slot_signal(thursday, 16)

        self.assertEqual(result["signal"], "WAIT")
        self.assertEqual(result["pair_dirs"], {})


if __name__ == "__main__":
    unittest.main()
