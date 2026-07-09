# -*- coding: utf-8 -*-
"""Unit tests for exact profile token resolution (no fuzzy broadcast)."""
import unittest
from unittest.mock import patch

# Import only the pure helpers via a thin fake — CopyTradeManager needs heavy deps.
# Test logic by reimplementing/importing module methods after light stub.


class TestLooksLikeProfileToken(unittest.TestCase):
    def setUp(self):
        # Minimal stand-in using real methods from a stripped object
        from OAK_Hidden_SLTP_Manager import CopyTradeManager

        self.cm = object.__new__(CopyTradeManager)
        self.cm.config = {"profile_name": "VantageDemo"}
        self.cm._profile_cache = {
            "mtime": -1,
            "names": {"vantage", "vantagedemo", "icmarkets", "darwinex", "th5ers", "roboforex"},
        }

    def test_exact_match_pops_profile(self):
        matched, invalid, rest = self.cm._resolve_target_profile(
            ["sell", "gbpaud+", "0.01", "20h00", "vantagedemo"]
        )
        self.assertEqual(matched, "vantagedemo")
        self.assertEqual(invalid, "")
        self.assertEqual(rest, ["sell", "gbpaud+", "0.01", "20h00"])

    def test_typo_vantagedemi_is_invalid_not_broadcast(self):
        matched, invalid, rest = self.cm._resolve_target_profile(
            ["sell", "gbpaud+", "0.01", "20h00", "vantagedemi"]
        )
        self.assertEqual(matched, "")
        self.assertEqual(invalid.lower(), "vantagedemi")
        self.assertEqual(rest, ["sell", "gbpaud+", "0.01", "20h00"])

    def test_no_profile_token_broadcast_ok(self):
        matched, invalid, rest = self.cm._resolve_target_profile(
            ["sell", "gbpaud+", "0.01", "20h00"]
        )
        self.assertEqual(matched, "")
        self.assertEqual(invalid, "")
        self.assertEqual(rest, ["sell", "gbpaud+", "0.01", "20h00"])

    def test_symbol_not_profile(self):
        matched, invalid, rest = self.cm._resolve_target_profile(
            ["buy", "xauusd+", "0.04", "9h09"]
        )
        self.assertEqual(matched, "")
        self.assertEqual(invalid, "")

    def test_other_valid_profile_matched(self):
        matched, invalid, rest = self.cm._resolve_target_profile(
            ["buy", "gbpaud+", "0.01", "10:00", "icmarkets"]
        )
        self.assertEqual(matched, "icmarkets")
        self.assertEqual(invalid, "")

    def test_looks_like_rejects_time_and_lot(self):
        self.assertFalse(self.cm._looks_like_profile_token("20h00"))
        self.assertFalse(self.cm._looks_like_profile_token("0.01"))
        self.assertFalse(self.cm._looks_like_profile_token("20:00"))
        self.assertTrue(self.cm._looks_like_profile_token("VantageDemi"))
        self.assertTrue(self.cm._looks_like_profile_token("FooBar"))


if __name__ == "__main__":
    unittest.main()
