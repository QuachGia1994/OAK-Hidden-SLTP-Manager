"""Canonical ten-rule classifier coverage for signal logic v72."""

import itertools
import unittest

from domain.signal_rules import classify_four_candle_group, classify_three_candle_group


EXPECTED = {
    ("TANG", "TANG", "TANG", "TANG"): ("SW", 1),
    ("TANG", "TANG", "TANG", "GIAM"): ("SW", 1),
    ("TANG", "GIAM", "TANG", "GIAM"): ("SW", 2),
    ("TANG", "GIAM", "GIAM", "TANG"): ("SW", 3),
    ("TANG", "GIAM", "GIAM", "GIAM"): ("SW", 3),
    ("TANG", "TANG", "GIAM", "TANG"): ("BT", 4),
    ("TANG", "TANG", "GIAM", "GIAM"): ("BT", 4),
    ("TANG", "GIAM", "TANG", "TANG"): ("BT", 5),
    ("GIAM", "GIAM", "GIAM", "GIAM"): ("SW", 6),
    ("GIAM", "GIAM", "GIAM", "TANG"): ("SW", 6),
    ("GIAM", "TANG", "GIAM", "TANG"): ("SW", 7),
    ("GIAM", "TANG", "TANG", "TANG"): ("SW", 8),
    ("GIAM", "TANG", "TANG", "GIAM"): ("SW", 8),
    ("GIAM", "GIAM", "TANG", "TANG"): ("BT", 9),
    ("GIAM", "GIAM", "TANG", "GIAM"): ("BT", 9),
    ("GIAM", "TANG", "GIAM", "GIAM"): ("BT", 10),
}


class FourM30ClassifierTests(unittest.TestCase):
    def test_all_sixteen_binary_patterns_match_exactly_one_rule(self) -> None:
        patterns = set(itertools.product(("TANG", "GIAM"), repeat=4))
        self.assertEqual(set(EXPECTED), patterns)

        for directions, (group, rule_number) in EXPECTED.items():
            with self.subTest(directions=directions):
                result = classify_four_candle_group(directions)
                self.assertEqual(result["group"], group)
                self.assertEqual(result["rule_number"], rule_number)
                self.assertEqual(result["directions"], list(directions))

    def test_invalid_or_doji_group_is_unresolved(self) -> None:
        for directions in (
            ("TANG", "GIAM", "DOJI", "TANG"),
            ("TANG", "GIAM", None, "TANG"),
            ("TANG", "GIAM", "TANG"),
        ):
            with self.subTest(directions=directions):
                result = classify_four_candle_group(directions)
                self.assertIsNone(result["group"])
                self.assertIsNone(result["rule_number"])

    def test_h3_three_candle_matrix_matches_the_previous_m15_model(self) -> None:
        expected = {
            ("TANG", "TANG", "TANG"): "SW",
            ("GIAM", "TANG", "TANG"): "SW",
            ("GIAM", "TANG", "GIAM"): "BT",
            ("GIAM", "GIAM", "TANG"): "BT",
            ("GIAM", "GIAM", "GIAM"): "SW",
            ("TANG", "GIAM", "GIAM"): "SW",
            ("TANG", "GIAM", "TANG"): "BT",
            ("TANG", "TANG", "GIAM"): "BT",
        }
        for directions, group in expected.items():
            with self.subTest(directions=directions):
                result = classify_three_candle_group(directions)
                self.assertEqual(result["group"], group)
                self.assertEqual(result["directions"], list(directions))


if __name__ == "__main__":
    unittest.main()
