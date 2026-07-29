import unittest
from datetime import datetime
from unittest.mock import patch

import mt5_signal_bot


PAIR_DIRS = {symbol: "BUY" for symbol in mt5_signal_bot.SIGNAL_PAIRS}


class TestSignalApiUpsert(unittest.TestCase):
    def test_ready_record_has_monotonic_revision_metadata(self) -> None:
        dt = datetime(2026, 7, 29, 3)
        evidence = {
            symbol: {"group": "BT", "direction": "BUY", "source_date": "2026-07-28"}
            for symbol in mt5_signal_bot.SIGNAL_PAIRS
        }
        with (
            patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
            patch.object(
                mt5_signal_bot,
                "evaluate_xau_entry_timing_basis_m15",
                return_value={"entry_basis_direction": "BUY", "entry_time": "03:11"},
            ),
            patch.object(
                mt5_signal_bot,
                "evaluate_gbpaud_entry_timing_m15",
                return_value={"offset15_direction": "TANG"},
            ),
            patch.object(
                mt5_signal_bot,
                "_derive_pair_signals_and_evidence",
                return_value=(PAIR_DIRS, evidence),
            ),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(dt, 3)
        self.assertEqual(result["logic_version"], 71)
        self.assertEqual(result["record_revision"], 4)
        self.assertEqual(result["signal_state"], "READY")
        self.assertIn("state_updated_at_utc", result)

    def test_terminal_thursday_wait_outranks_pending_entry(self) -> None:
        dt = datetime(2026, 7, 30, 3)
        directions = {**PAIR_DIRS, "XAUUSD": "WAIT"}
        evidence = {
            symbol: {"group": "BT", "direction": direction, "source_date": "2026-07-24"}
            for symbol, direction in directions.items()
        }
        evidence["XAUUSD"].update({
            "group": "SW",
            "classification_reason": "THURSDAY_MONDAY_SW_WAIT_UNTIL_H7",
        })
        with (
            patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
            patch.object(
                mt5_signal_bot,
                "evaluate_xau_entry_timing_basis_m15",
                return_value={"entry_basis_direction": "BUY", "entry_time": "03:49"},
            ),
            patch.object(
                mt5_signal_bot,
                "evaluate_gbpaud_entry_timing_m15",
                return_value={"offset15_direction": "GIAM"},
            ),
            patch.object(mt5_signal_bot, "can_resolve_entry_followup", return_value=False),
            patch.object(
                mt5_signal_bot,
                "_derive_pair_signals_and_evidence",
                return_value=(directions, evidence),
            ),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(dt, 3)
        self.assertEqual(result["entry_state"], "PENDING_FOLLOWUP")
        self.assertTrue(result["terminal_wait"])
        self.assertEqual(result["record_revision"], 5)


if __name__ == "__main__":
    unittest.main()
