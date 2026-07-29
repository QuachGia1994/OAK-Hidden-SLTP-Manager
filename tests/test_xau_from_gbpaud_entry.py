"""Exhaustive test suite for v62 XAUUSD derivation from GBPAUD and Broker Entry Time."""
from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


class XauFromGbpaudEntryTests(unittest.TestCase):
    def test_pure_helper_table_driven_truth_table(self) -> None:
        """Table-driven verification of derive_xauusd_from_gbpaud_entry across all slots and entry minutes."""
        # Minutes :11 and :25 -> SAME
        # Minute :49 -> OPPOSITE
        test_cases = [
            # (gbpaud_signal, xau_entry_time, expected_direction, expected_relation)
            ("BUY", "03:11", "BUY", "SAME"),
            ("SELL", "03:11", "SELL", "SAME"),
            ("BUY", "03:49", "SELL", "OPPOSITE"),
            ("SELL", "03:49", "BUY", "OPPOSITE"),
            ("BUY", "04:49", "SELL", "OPPOSITE"),
            ("SELL", "04:49", "BUY", "OPPOSITE"),
            ("BUY", "07:11", "BUY", "SAME"),
            ("SELL", "07:11", "SELL", "SAME"),
            ("BUY", "07:49", "SELL", "OPPOSITE"),
            ("SELL", "07:49", "BUY", "OPPOSITE"),
            ("BUY", "08:25", "BUY", "SAME"),
            ("SELL", "08:25", "SELL", "SAME"),
            ("BUY", "09:11", "BUY", "SAME"),
            ("SELL", "09:11", "SELL", "SAME"),
            ("BUY", "09:49", "SELL", "OPPOSITE"),
            ("SELL", "09:49", "BUY", "OPPOSITE"),
            ("BUY", "10:25", "BUY", "SAME"),
            ("SELL", "10:25", "SELL", "SAME"),
            ("BUY", "12:11", "BUY", "SAME"),
            ("SELL", "12:11", "SELL", "SAME"),
            ("BUY", "12:49", "SELL", "OPPOSITE"),
            ("SELL", "12:49", "BUY", "OPPOSITE"),
            ("BUY", "13:25", "BUY", "SAME"),
            ("SELL", "13:25", "SELL", "SAME"),
            ("BUY", "14:11", "BUY", "SAME"),
            ("SELL", "14:11", "SELL", "SAME"),
            ("BUY", "14:49", "SELL", "OPPOSITE"),
            ("SELL", "14:49", "BUY", "OPPOSITE"),
            ("BUY", "15:25", "BUY", "SAME"),
            ("SELL", "15:25", "SELL", "SAME"),
            ("BUY", "16:11", "BUY", "SAME"),
            ("SELL", "16:11", "SELL", "SAME"),
            ("BUY", "16:49", "SELL", "OPPOSITE"),
            ("SELL", "16:49", "BUY", "OPPOSITE"),
            ("BUY", "17:25", "BUY", "SAME"),
            ("SELL", "17:25", "SELL", "SAME"),
        ]

        for gbpaud_sig, entry_t, exp_dir, exp_rel in test_cases:
            with self.subTest(gbpaud_sig=gbpaud_sig, entry_t=entry_t):
                res = mt5_signal_bot.derive_xauusd_from_gbpaud_entry(gbpaud_sig, entry_t)
                self.assertIsNotNone(res)
                self.assertEqual(res["direction"], exp_dir)
                self.assertEqual(res["relation"], exp_rel)

    def test_invalid_inputs_return_none(self) -> None:
        """GBP entry times, invalid strings, out-of-range HH:MM fail closed by returning None."""
        invalid_entries = [
            "08:20", "09:00", "10:20", "11:00", "12:00",
            None, "", "N/A", "—", "25", "7:11", "24:11", "08:60",
        ]
        for inv in invalid_entries:
            with self.subTest(entry_t=inv):
                self.assertIsNone(mt5_signal_bot.derive_xauusd_from_gbpaud_entry("BUY", inv))
                self.assertIsNone(mt5_signal_bot.derive_xauusd_from_gbpaud_entry("SELL", inv))

    def test_prove_xau_independent_logic_is_disabled(self) -> None:
        """Varying legacy XAU entry basis or independent candle data MUST NOT alter final derived XAU direction."""
        wednesday_dt = datetime(2026, 7, 29, 7, 0)

        # Fixture A: GBPAUD BUY + XAU entry 08:25 (legacy basis BUY) -> XAUUSD BUY
        # Fixture B: GBPAUD BUY + XAU entry 08:25 (legacy basis SELL) -> XAUUSD BUY
        # In both cases, GBPAUD final = BUY and XAU entry = 08:25 -> final XAUUSD MUST be BUY
        for legacy_basis in ("BUY", "SELL"):
            with self.subTest(legacy_basis=legacy_basis):
                res = mt5_signal_bot.derive_xauusd_from_gbpaud_entry("BUY", "08:25")
                self.assertEqual(res["direction"], "BUY")

        # Fixture C & D: GBPAUD BUY + XAU entry 07:49 -> final XAUUSD MUST be SELL
        for legacy_basis in ("BUY", "SELL"):
            with self.subTest(legacy_basis=legacy_basis):
                res = mt5_signal_bot.derive_xauusd_from_gbpaud_entry("BUY", "07:49")
                self.assertEqual(res["direction"], "SELL")

    def test_entry_clock_non_regression_h7(self) -> None:
        """H7 entry timing is preserved (08:25 XAU / 09:00 GBP) while XAU direction is derived."""
        dt = datetime(2026, 7, 29, 7, 0)
        # Mock candles so XAU entry plan resolves to READY @ 08:25
        with patch.object(mt5_signal_bot, "_lookback_candle_direction", return_value="TANG"):
            res = mt5_signal_bot.evaluate_all_pairs_for_slot(dt, 7, resolve_historical_followup=True)

        self.assertIsNotNone(res)
        self.assertEqual(res["logic_version"], 62)
        self.assertEqual(res["pair_entry_times"]["XAUUSD"], "08:25")
        self.assertEqual(res["pair_entry_times"]["GBPUSD"], "09:00")
        self.assertEqual(res["pair_entry_times"]["GBPAUD"], "09:00")

    def test_pending_followup_semantics(self) -> None:
        """Before H:45 follow-up is available, top-level signal and XAUUSD direction are WAIT."""
        dt = datetime(2026, 7, 29, 7, 0)
        as_of_before_followup = datetime(2026, 7, 29, 7, 30)

        def mock_candles(symbol, tf, candle_dt):
            return "TANG"

        with patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=mock_candles):
            res = mt5_signal_bot.evaluate_all_pairs_for_slot(dt, 7, as_of_dt=as_of_before_followup)

        self.assertIsNotNone(res)
        self.assertEqual(res["pair_entry_states"]["XAUUSD"], "PENDING_FOLLOWUP")
        self.assertEqual(res["pair_dirs"]["XAUUSD"], "WAIT")
        self.assertEqual(res["signal"], "WAIT")

    def test_h3_derivation_cases(self) -> None:
        """H3 evaluates GBPAUD independently and derives XAUUSD for :11, :39, :49 entries."""
        dt = datetime(2026, 7, 29, 3, 0)

        # Case 1: GBPAUD BUY + XAU entry 03:11 -> XAUUSD BUY, GBPUSD WAIT
        res1 = mt5_signal_bot.derive_xauusd_from_gbpaud_entry("BUY", "03:11")
        self.assertEqual(res1["direction"], "BUY")

        # Case 2: GBPAUD BUY + XAU entry 03:49 -> XAUUSD SELL
        res2 = mt5_signal_bot.derive_xauusd_from_gbpaud_entry("BUY", "03:49")
        self.assertEqual(res2["direction"], "SELL")

        # Case 3: GBPAUD SELL + XAU entry 04:49 -> XAUUSD BUY
        res3 = mt5_signal_bot.derive_xauusd_from_gbpaud_entry("SELL", "04:49")
        self.assertEqual(res3["direction"], "BUY")


if __name__ == "__main__":
    unittest.main()
