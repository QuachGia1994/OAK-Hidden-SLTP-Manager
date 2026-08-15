import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "robot-sltp-pro"
sys.path.insert(0, str(APP))

from pattern5_engine import classify5, pattern_text, signal_from_base


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


if __name__ == "__main__":
    unittest.main()
