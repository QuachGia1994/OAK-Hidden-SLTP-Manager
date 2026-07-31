"""Versioned record/evidence payload regression tests."""

from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


def _d_dirs():
    """Return D-Directions for all 5 symbols."""
    return {
        "XAUUSD": {"d_direction": "BUY", "d_state": "READY", "symbol": "XAUUSD"},
        "GBPUSD": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPUSD"},
        "GBPAUD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPAUD"},
        "GBPJPY": {"d_direction": "WAIT", "d_state": "DOJI", "symbol": "GBPJPY"},
        "GBPCAD": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPCAD"},
    }


def _timing(entry_time):
    return {
        "entry_time": entry_time,
        "entry_state": "READY",
        "layer1": {"group": "BT"},
        "layer2": {"group": "BT"},
        "layer3": None,
    }


def _mock_symbol_timing(symbol, slot_dt, h, as_of_dt=None):
    if symbol == "XAUUSD":
        return _timing(f"{h:02d}:11")
    return _timing("04:00")


class SignalApiUpsertTests(unittest.TestCase):
    def test_persisted_entry_plan_keeps_revision_metadata(self) -> None:
        self.assertIn("record_revision", mt5_signal_bot.ENTRY_PLAN_FIELDS)
        self.assertIn("state_updated_at_utc", mt5_signal_bot.ENTRY_PLAN_FIELDS)

    def test_ready_result_has_versioned_five_pair_maps(self) -> None:
        with (
            patch.object(mt5_signal_bot, "calculate_all_d_directions", return_value=_d_dirs()),
            patch.object(mt5_signal_bot, "evaluate_symbol_entry_timing_m30", side_effect=_mock_symbol_timing),
            patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(datetime(2026, 7, 29, 3), 3)

        self.assertEqual(result["logic_version"], mt5_signal_bot.SIGNAL_LOGIC_VERSION)
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
        self.assertEqual(result["pair_entry_times"]["XAUUSD"], "03:11")

    def test_dashboard_evidence_emits_one_versioned_record_per_symbol(self) -> None:
        ver = mt5_signal_bot.SIGNAL_LOGIC_VERSION
        with (
            patch.object(mt5_signal_bot, "calculate_all_d_directions", return_value=_d_dirs()),
            patch.object(mt5_signal_bot, "evaluate_symbol_entry_timing_m30", side_effect=_mock_symbol_timing),
            patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(datetime(2026, 7, 29, 7), 7)
        records = mt5_signal_bot._dashboard_signal_evidence(datetime(2026, 7, 29, 7), 7, result)
        self.assertEqual(len(records), 5)
        self.assertTrue(all(key.endswith(f":v{ver}") for key in records))


if __name__ == "__main__":
    unittest.main()
