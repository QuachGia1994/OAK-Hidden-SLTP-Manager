"""Versioned v72 record/evidence payload regression tests."""

from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


def _gbp_evidence(symbol, direction="BUY", group="BT"):
    return {
        "symbol": symbol,
        "direction": direction,
        "entry_time": None,
        "signal_state": "READY",
        "entry_state": "WAIT",
        "layer1": {"group": group, "base_signal": direction},
    }


def _timing(entry_time):
    return {
        "entry_time": entry_time,
        "entry_state": "READY",
        "layer1": {"group": "BT"},
        "layer2": {"group": "BT"},
    }


class SignalApiUpsertTests(unittest.TestCase):
    def test_persisted_entry_plan_keeps_revision_metadata(self) -> None:
        self.assertIn("record_revision", mt5_signal_bot.ENTRY_PLAN_FIELDS)
        self.assertIn("state_updated_at_utc", mt5_signal_bot.ENTRY_PLAN_FIELDS)

    def test_ready_result_has_versioned_five_pair_maps(self) -> None:
        rows = {symbol: _gbp_evidence(symbol) for symbol in mt5_signal_bot.GBP_SIGNAL_PAIRS}
        with (
            patch.object(mt5_signal_bot, "_evaluate_all_gbp_pairs", return_value=rows),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30", return_value=_timing("03:49")),
            patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(datetime(2026, 7, 29, 3), 3)

        self.assertEqual(result["logic_version"], 72)
        self.assertEqual(result["record_revision"], 2)
        for field in (
            "pair_dirs",
            "pair_entry_times",
            "pair_signal_states",
            "pair_entry_states",
            "pair_evidence",
            "pair_entry_at_utc",
        ):
            self.assertEqual(set(result[field]), set(mt5_signal_bot.SIGNAL_PAIRS))
        self.assertNotEqual(result["pair_dirs"]["XAUUSD"], result["pair_dirs"]["GBPAUD"])
        self.assertNotEqual(result["pair_entry_times"]["XAUUSD"], result["pair_entry_times"]["GBPAUD"])

    def test_xau_evidence_references_instead_of_duplicating_gbpaud(self) -> None:
        rows = {symbol: _gbp_evidence(symbol) for symbol in mt5_signal_bot.GBP_SIGNAL_PAIRS}
        with (
            patch.object(mt5_signal_bot, "_evaluate_all_gbp_pairs", return_value=rows),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30", return_value=_timing("07:49")),
            patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(datetime(2026, 7, 29, 7), 7)
        xau = result["pair_evidence"]["XAUUSD"]
        self.assertEqual(xau["source_evidence"], "pair_evidence.GBPAUD")
        self.assertEqual(xau["layer1"]["group"], "BT")
        self.assertEqual(xau["layer2"]["group"], "BT")

    def test_dashboard_evidence_emits_one_versioned_record_per_symbol(self) -> None:
        rows = {symbol: _gbp_evidence(symbol) for symbol in mt5_signal_bot.GBP_SIGNAL_PAIRS}
        with (
            patch.object(mt5_signal_bot, "_evaluate_all_gbp_pairs", return_value=rows),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30", return_value=_timing("07:49")),
            patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(datetime(2026, 7, 29, 7), 7)
        records = mt5_signal_bot._dashboard_signal_evidence(datetime(2026, 7, 29, 7), 7, result)
        self.assertEqual(len(records), 5)
        self.assertTrue(all(key.endswith(":v72") for key in records))
        xau = records["2026-07-29:7:XAUUSD:v72"]
        gbpusd = records["2026-07-29:7:GBPUSD:v72"]
        self.assertEqual(xau["entry_rule"], "XAU_TWO_LAYER_M30")
        self.assertEqual(xau["gbp_entry_time"], "08:00")
        self.assertEqual(gbpusd["entry_rule"], "NEXT_FULL_HOUR_AFTER_XAU")


if __name__ == "__main__":
    unittest.main()
