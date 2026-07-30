"""Three-candle M30 classifier: exhaustive 8-case matrix (v79)."""

import unittest
from domain.signal_rules import classify_three_candle_group


class ThreeCandleClassifierTests(unittest.TestCase):
    def test_case_1_TTT_SW(self):
        r = classify_three_candle_group(["TANG", "TANG", "TANG"])
        self.assertEqual(r["group"], "SW")
        self.assertEqual(r["rule_number"], 1)

    def test_case_2_GTT_SW(self):
        r = classify_three_candle_group(["GIAM", "TANG", "TANG"])
        self.assertEqual(r["group"], "SW")
        self.assertEqual(r["rule_number"], 2)

    def test_case_3_GTG_BT(self):
        r = classify_three_candle_group(["GIAM", "TANG", "GIAM"])
        self.assertEqual(r["group"], "BT")
        self.assertEqual(r["rule_number"], 3)

    def test_case_4_GGT_BT(self):
        r = classify_three_candle_group(["GIAM", "GIAM", "TANG"])
        self.assertEqual(r["group"], "BT")
        self.assertEqual(r["rule_number"], 4)

    def test_case_5_GGG_SW(self):
        r = classify_three_candle_group(["GIAM", "GIAM", "GIAM"])
        self.assertEqual(r["group"], "SW")
        self.assertEqual(r["rule_number"], 5)

    def test_case_6_TGG_SW(self):
        r = classify_three_candle_group(["TANG", "GIAM", "GIAM"])
        self.assertEqual(r["group"], "SW")
        self.assertEqual(r["rule_number"], 6)

    def test_case_7_TGT_BT(self):
        r = classify_three_candle_group(["TANG", "GIAM", "TANG"])
        self.assertEqual(r["group"], "BT")
        self.assertEqual(r["rule_number"], 7)

    def test_case_8_TTG_BT(self):
        r = classify_three_candle_group(["TANG", "TANG", "GIAM"])
        self.assertEqual(r["group"], "BT")
        self.assertEqual(r["rule_number"], 8)

    def test_doji_returns_unresolved(self):
        r = classify_three_candle_group(["TANG", "TANG", "DOJI"])
        self.assertIsNone(r["group"])
        self.assertIsNone(r["rule_number"])

    def test_none_candle_returns_unresolved(self):
        r = classify_three_candle_group(["TANG", None, "GIAM"])
        self.assertIsNone(r["group"])

    def test_two_candles_returns_unresolved(self):
        r = classify_three_candle_group(["TANG", "GIAM"])
        self.assertIsNone(r["group"])

    def test_four_candles_returns_unresolved(self):
        r = classify_three_candle_group(["TANG", "GIAM", "TANG", "GIAM"])
        self.assertIsNone(r["group"])

    def test_empty_returns_unresolved(self):
        r = classify_three_candle_group([])
        self.assertIsNone(r["group"])

    def test_all_eight_cases_are_exhaustive(self):
        """Every T/G combo of length 3 must resolve to SW or BT."""
        for c1 in ("TANG", "GIAM"):
            for c2 in ("TANG", "GIAM"):
                for c3 in ("TANG", "GIAM"):
                    r = classify_three_candle_group([c1, c2, c3])
                    self.assertIn(r["group"], ("SW", "BT"),
                                  f"Unresolved: {c1} {c2} {c3}")


if __name__ == "__main__":
    unittest.main()
