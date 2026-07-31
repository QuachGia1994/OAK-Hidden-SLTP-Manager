"""XAUUSD uses GBPUSD D-Direction source (v82 D_SOURCE_SYMBOL mapping)."""

import unittest
from datetime import datetime
from unittest.mock import patch
import mt5_signal_bot
from mt5_signal_bot import DayMode, _build_rebuild_record, D_SOURCE_SYMBOL


class PerSymbolIndependenceTests(unittest.TestCase):
    def test_xauusd_d_source_is_gbpusd(self) -> None:
        """XAUUSD D-Direction source is GBPUSD, not GBPAUD."""
        self.assertEqual(D_SOURCE_SYMBOL["XAUUSD"], "GBPUSD")

    def test_gbp_pairs_use_own_d_source(self) -> None:
        """GBP pairs use their own symbol as D source."""
        self.assertEqual(D_SOURCE_SYMBOL["GBPUSD"], "GBPUSD")
        self.assertEqual(D_SOURCE_SYMBOL["GBPAUD"], "GBPAUD")
        self.assertEqual(D_SOURCE_SYMBOL["GBPJPY"], "GBPJPY")
        self.assertEqual(D_SOURCE_SYMBOL["GBPCAD"], "GBPCAD")

    def test_per_symbol_d_direction_independence(self) -> None:
        """Each symbol uses its own D-Direction independently via Day Mode."""
        target_date = datetime(2026, 7, 30, 9)
        d_dirs = {
            "XAUUSD": {"d_direction": "SELL", "d_state": "READY", "symbol": "XAUUSD", "source_symbol": "GBPUSD", "timeframe": "H4"},
            "GBPUSD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPUSD", "source_symbol": "GBPUSD", "timeframe": "H4"},
            "GBPAUD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPAUD", "source_symbol": "GBPAUD", "timeframe": "H4"},
            "GBPJPY": {"d_direction": "WAIT", "d_state": "DOJI", "symbol": "GBPJPY", "source_symbol": "GBPJPY", "timeframe": "H4"},
            "GBPCAD": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPCAD", "source_symbol": "GBPCAD", "timeframe": "H4"},
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
            patch.object(mt5_signal_bot, "evaluate_symbol_entry_timing_m30", return_value=timing),
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
