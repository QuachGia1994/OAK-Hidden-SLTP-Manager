import sys
import unittest
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "robot-sltp-pro"
sys.path.insert(0, str(APP))

from pattern5_engine import classify5, flip_signal, pattern_text, should_reverse_signal, signal_from_base


class Pattern5SignalRuleTests(unittest.TestCase):
    def test_sw_reverses_base_candle_four(self):
        self.assertEqual(signal_from_base(["T", "T", "T", "T"], "Sw"), "SELL")
        self.assertEqual(signal_from_base(["T", "T", "T", "G"], "Sw"), "BUY")

    def test_bt_follows_base_candle_four(self):
        self.assertEqual(signal_from_base(["G", "G", "T", "T"], "Bt"), "BUY")
        self.assertEqual(signal_from_base(["G", "G", "T", "G"], "Bt"), "SELL")

    def test_pattern_classifier_still_uses_three_or_four_candles(self):
        self.assertEqual(classify5(["T", "T", "T", "G"])[0], 1)
        self.assertEqual(classify5(["G", "G", "T", "T"])[0], 3)
        self.assertEqual(classify5(["T", "G", "T", "G"])[0], 5)
        self.assertEqual(pattern_text(1, ["T", "T", "T", "G"]), "T T T")
        self.assertEqual(pattern_text(5, ["T", "G", "T", "G"]), "T G T G")

    def test_reverse_matrix_for_h7_h9_h12_h14(self):
        week = [date(2026, 8, 10 + offset) for offset in range(5)]
        self.assertEqual([should_reverse_signal(7, day) for day in week], [True, True, False, False, True])
        self.assertEqual([should_reverse_signal(9, day) for day in week], [False, False, False, True, True])
        self.assertEqual([should_reverse_signal(12, day) for day in week], [True, True, False, True, True])
        self.assertEqual([should_reverse_signal(14, day) for day in week], [True, True, True, True, True])

    def test_h3_monday_and_thursday_month_exception(self):
        self.assertTrue(should_reverse_signal(3, date(2026, 8, 10)))
        self.assertTrue(should_reverse_signal(3, date(2026, 9, 3)))
        self.assertFalse(should_reverse_signal(3, date(2026, 7, 2)))
        self.assertFalse(should_reverse_signal(3, date(2026, 7, 9)))
        self.assertFalse(should_reverse_signal(3, date(2026, 10, 1)))
        self.assertFalse(should_reverse_signal(3, date(2026, 10, 8)))

    def test_h3_friday_recalculates_from_first_friday_each_month(self):
        self.assertTrue(should_reverse_signal(3, date(2026, 7, 3)))
        self.assertTrue(should_reverse_signal(3, date(2026, 7, 24)))
        self.assertTrue(should_reverse_signal(3, date(2026, 8, 28)))
        self.assertFalse(should_reverse_signal(3, date(2026, 5, 1)))
        self.assertFalse(should_reverse_signal(3, date(2026, 5, 29)))

    def test_reverse_flips_final_signal_only_once(self):
        self.assertEqual(flip_signal("BUY"), "SELL")
        self.assertEqual(flip_signal("SELL"), "BUY")


if __name__ == "__main__":
    unittest.main()
