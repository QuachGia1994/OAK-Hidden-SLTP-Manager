"""The retired priority badge cannot alter GBP H1 slot calculation."""
from contextlib import ExitStack
from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


DIRECT_SLOTS = (3, 7, 9, 12, 14, 16)


class SignalPriorityTests(unittest.TestCase):
    def test_priority_classifier_is_removed(self) -> None:
        self.assertFalse(hasattr(mt5_signal_bot, "is_priority_slot"))
        self.assertFalse(
            hasattr(mt5_signal_bot, "evaluate_4_m30_classification_before_hour")
        )

    def test_direct_slots_do_not_depend_on_retired_priority_or_signal_lookups(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        context = {
            "signal": "BUY",
            "entry_time": "12:11",
            "pair_dirs": {"XAUUSD": "BUY"},
        }
        legacy = (
            "analyze",
            "evaluate_classification_for_slot",
            "evaluate_3_m30_classification_for_h3",
            "evaluate_4_m30_classification_before_hour",
            "_lookup_h3_signal_today",
            "_lookup_h4_signal_today",
            "_lookup_h5_signal_today",
            "_lookup_h5_signal_yesterday",
            "_lookup_h16_signal_yesterday",
            "_lookup_signal_from_log",
        )

        for hour in DIRECT_SLOTS:
            with self.subTest(hour=hour), ExitStack() as stack:
                stack.enter_context(
                    patch.object(
                        mt5_signal_bot,
                        "evaluate_gbp_h1_slot",
                        return_value=dict(context),
                        create=True,
                    )
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

            self.assertIn(result["signal"], ("BUY", "SELL"))
            self.assertNotIn("m30_dir", result)
            self.assertNotIn("h1_signal", result)


if __name__ == "__main__":
    unittest.main()
