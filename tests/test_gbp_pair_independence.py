"""GBP pairs use their own D-Direction independently with independent M30 entry (v82)."""

from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot
from mt5_signal_bot import DayMode


def _d_dirs():
    return {
        "XAUUSD": {"d_direction": "BUY", "d_state": "READY", "symbol": "XAUUSD", "source_symbol": "GBPUSD", "timeframe": "H4"},
        "GBPUSD": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPUSD", "source_symbol": "GBPUSD", "timeframe": "H4"},
        "GBPAUD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPAUD", "source_symbol": "GBPAUD", "timeframe": "H4"},
        "GBPJPY": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPJPY", "source_symbol": "GBPJPY", "timeframe": "H4"},
        "GBPCAD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPCAD", "source_symbol": "GBPCAD", "timeframe": "H4"},
    }


def _timing(entry="07:11", symbol="XAUUSD"):
    return {
        "symbol": symbol,
        "entry_time": entry,
        "entry_state": "READY" if entry else "WAIT",
        "layer1": {"group": "BT"},
        "layer2": {"group": "BT"},
        "layer3": None,
    }


class GbpPairIndependenceTests(unittest.TestCase):
    def test_signals_are_independent_with_independent_m30_entries(self) -> None:
        """In v82, each symbol runs its own M30 entry engine independently."""
        mode = DayMode(mode="DAY_MODE_H11", source_hour=3, source_entry_time="03:11", source_branch="H_11")
        with (
            patch.object(mt5_signal_bot, "calculate_all_d_directions", return_value=_d_dirs()),
            patch.object(mt5_signal_bot, "evaluate_symbol_entry_timing_m30",
                         side_effect=lambda sym, *a, **kw: _timing("07:11", symbol=sym)),
            patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(datetime(2026, 7, 30, 7), 7, day_mode=mode)

        # H:11 matches DAY_MODE_H11 → KEEP_D for all pairs
        # XAUUSD D=BUY → BUY
        self.assertEqual(result["pair_dirs"]["XAUUSD"], "BUY")
        # GBPAUD D=BUY → BUY (independent)
        self.assertEqual(result["pair_dirs"]["GBPAUD"], "BUY")
        # GBPUSD D=SELL → SELL (independent)
        self.assertEqual(result["pair_dirs"]["GBPUSD"], "SELL")
        # In v82, all symbols get independent M30 entry (H:11 for BT)
        self.assertEqual(result["pair_entry_times"]["XAUUSD"], "07:11")
        self.assertEqual(result["pair_entry_times"]["GBPUSD"], "07:11")
        self.assertEqual(result["pair_entry_times"]["GBPAUD"], "07:11")
        # Disabled pairs
        self.assertEqual(result["pair_signal_states"]["GBPJPY"], "DISABLED")
        self.assertEqual(result["pair_signal_states"]["GBPCAD"], "DISABLED")


if __name__ == "__main__":
    unittest.main()
