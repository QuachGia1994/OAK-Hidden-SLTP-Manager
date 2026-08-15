import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "robot-sltp-pro"
sys.path.insert(0, str(APP))

from pattern5_engine import pattern_text, signal_from_two


class Pattern5SignalRuleTests(unittest.TestCase):
    def test_same_direction_follows_first_candle(self):
        self.assertEqual(signal_from_two(["T", "T"]), "BUY")
        self.assertEqual(signal_from_two(["G", "G"]), "SELL")

    def test_opposite_direction_reverses_first_candle(self):
        self.assertEqual(signal_from_two(["T", "G"]), "SELL")
        self.assertEqual(signal_from_two(["G", "T"]), "BUY")

    def test_pattern_text_uses_three_or_four_candles(self):
        self.assertEqual(pattern_text(1, ["T", "T", "T", "G"]), "T T T")
        self.assertEqual(pattern_text(5, ["T", "G", "T", "G"]), "T G T G")


if __name__ == "__main__":
    unittest.main()
