"""Per-symbol D-Direction signal independence tests (v81)."""

import unittest
from datetime import datetime
from unittest.mock import patch
import mt5_signal_bot
from mt5_signal_bot import DayMode, _build_rebuild_record


class PerSymbolIndependenceTests(unittest.TestCase):
    def test_per_symbol_d_direction_independence(self) -> None:
        """Section 10: Each symbol uses its own D-Direction independently."""
        target_date = datetime(2026, 7, 30, 9)
        d_dirs = {
            "XAUUSD": {"d_direction": "SELL", "d_state": "READY", "symbol": "XAUUSD"},
            "GBPUSD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPUSD"},
            "GBPAUD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPAUD"},
            "GBPJPY": {"d_direction": "WAIT", "d_state": "DOJI", "symbol": "GBPJPY"},
            "GBPCAD": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPCAD"},
        }
        timing = {
            "entry_time": "09:11",
            "entry_state": "READY",
            "layer1": {"group": "BT"},
            "layer2": {"group": "BT"},
            "layer3": None,
        }
        day_mode = DayMode(mode="DAY_MODE_H_PLUS_1_25", source_hour=3, source_entry_time="04:25", source_branch="H_PLUS_1_25")

        with (
            patch.object(mt5_signal_bot, "calculate_all_d_directions", return_value=d_dirs),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30", return_value=timing),
            patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
        ):
            record, _next_mode = _build_rebuild_record(target_date, 9, day_mode=day_mode, d_directions=d_dirs)

        # Entry 09:11 is H_11, opposite branch to H_PLUS_1_25 -> REVERSE_D
        # XAUUSD: D SELL -> reverse to BUY
        # GBPUSD: D BUY -> reverse to SELL
        # GBPAUD: D BUY -> reverse to SELL
        self.assertEqual(record["pair_dirs"]["XAUUSD"], "BUY")
        self.assertEqual(record["pair_dirs"]["GBPUSD"], "SELL")
        self.assertEqual(record["pair_dirs"]["GBPAUD"], "SELL")


if __name__ == "__main__":
    unittest.main()
