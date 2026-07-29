"""Regression test suite verifying complete removal of XAUUSD2 (v55).

Per Section 9 & 20 of the architecture specification:
- XAUUSD2 must no longer exist in signal records, pair maps, or bot functions.
- Every slot evaluates XAUUSD, GBPUSD, and GBPAUD independently on current M15 candles.
"""
from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


class Xauusd2RemovalTests(unittest.TestCase):
    """Verify XAUUSD2 is completely removed and replaced by independent M15 pairs."""

    def test_no_xauusd2_in_signal_pairs(self) -> None:
        self.assertNotIn("XAUUSD2", mt5_signal_bot.SIGNAL_PAIRS)
        self.assertEqual(mt5_signal_bot.SIGNAL_PAIRS, ("XAUUSD", "GBPUSD", "GBPAUD"))

    def test_no_xauusd2_function_attributes(self) -> None:
        self.assertFalse(hasattr(mt5_signal_bot, "evaluate_xauusd2_m15_for_slot"))
        self.assertFalse(hasattr(mt5_signal_bot, "_classify_xauusd2_pattern"))
        self.assertFalse(hasattr(mt5_signal_bot, "_m15_pair_for_hour"))

    def test_evaluator_returns_three_canonical_pairs(self) -> None:
        broker_dt = datetime(2026, 7, 29, 9, 0)
        with patch.object(mt5_signal_bot, "_lookback_candle_direction", return_value="TANG"):
            res = mt5_signal_bot.evaluate_all_pairs_for_slot(broker_dt, 9)

        self.assertIsNotNone(res)
        self.assertNotIn("XAUUSD2", res["pair_dirs"])
        self.assertCountEqual(res["pair_dirs"].keys(), ["XAUUSD", "GBPUSD", "GBPAUD"])
        self.assertCountEqual(res["pair_entry_times"].keys(), ["XAUUSD", "GBPUSD", "GBPAUD"])
        self.assertCountEqual(res["pair_groups"].keys(), ["XAUUSD", "GBPUSD", "GBPAUD"])
        self.assertCountEqual(res["pair_evidence"].keys(), ["XAUUSD", "GBPUSD", "GBPAUD"])


if __name__ == "__main__":
    unittest.main()
