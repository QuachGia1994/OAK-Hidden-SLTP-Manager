"""v88 Final Reverse applies to every applicable pair exactly once; never weekends."""
import unittest
from datetime import datetime, timedelta

from domain.signal_v87 import evaluate_slot, final_reverse
from test_signal_v87_core import FixtureProvider, add_m30_layer


def _h3_wednesday_result():
    """Wednesday 2026-08-05 H3 -> Final Reverse H3_WEDNESDAY must invert all applicable."""
    provider = FixtureProvider()
    slot_dt = datetime(2026, 8, 5, 3)
    add_m30_layer(provider, slot_dt, ("GIAM", "TANG", "GIAM"))
    snapshot = {symbol: {"d_direction": "BUY"} for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")}
    return evaluate_slot(slot_dt, 3, provider, snapshot)


class TestFinalReverseAllActivePairs(unittest.TestCase):

    def test_reverse_matrix_sample(self):
        self.assertEqual(final_reverse(3, datetime(2026, 8, 5).date()), (True, "H3_WEDNESDAY"))
        self.assertEqual(final_reverse(14, datetime(2026, 8, 4).date()), (True, "H14_TUESDAY"))
        self.assertEqual(final_reverse(16, datetime(2026, 8, 14).date()), (True, "H16_FRIDAY"))

    def test_never_reverses_on_weekends(self):
        saturday = datetime(2026, 8, 1).date()
        sunday = datetime(2026, 8, 2).date()
        for hour in (3, 7, 9, 12, 14, 16):
            with self.subTest(hour=hour, day=saturday):
                self.assertEqual(final_reverse(hour, saturday), (False, "WEEKEND_NO_REVERSE"))
            with self.subTest(hour=hour, day=sunday):
                self.assertEqual(final_reverse(hour, sunday), (False, "WEEKEND_NO_REVERSE"))

    def test_h3_wednesday_reverses_every_applicable_pair_once(self):
        result = _h3_wednesday_result()
        self.assertTrue(result["final_reverse_applied"])
        self.assertEqual(result["final_reverse_reason"], "H3_WEDNESDAY")
        # H3 applies to XAUUSD, GBPUSD, GBPAUD, GBPJPY.
        for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY"):
            with self.subTest(symbol=symbol):
                self.assertTrue(result["pair_final_reverse_applied"][symbol])
                self.assertEqual(
                    result["pair_dirs"][symbol],
                    {"BUY": "SELL", "SELL": "BUY"}[result["core_signals"][symbol]],
                )
                self.assertTrue(result["pair_evidence"][symbol]["final_reverse_applied"])
        # GBPCAD is inactive at H3: not reversed.
        self.assertFalse(result["pair_final_reverse_applied"]["GBPCAD"])
        self.assertNotIn("GBPCAD", result["pair_evidence"])

    def test_xauusd_gbpusd_equal_after_reverse(self):
        result = _h3_wednesday_result()
        self.assertEqual(result["pair_dirs"]["XAUUSD"], result["pair_dirs"]["GBPUSD"])

    def test_no_reverse_slot_keeps_pairs(self):
        provider = FixtureProvider()
        slot_dt = datetime(2026, 8, 5, 9)
        add_m30_layer(provider, slot_dt, ("GIAM", "TANG", "GIAM"))
        snapshot = {symbol: {"d_direction": "SELL"} for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")}
        result = evaluate_slot(slot_dt, 9, provider, snapshot)
        self.assertFalse(result["final_reverse_applied"])
        self.assertIsNone(result["final_reverse_reason"])
        self.assertFalse(result["pair_final_reverse_applied"]["XAUUSD"])


if __name__ == "__main__":
    unittest.main()
