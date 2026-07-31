"""D-Direction + Day Mode signal engine: each pair uses its own D independently (v82)."""

import unittest
from datetime import datetime
from unittest.mock import patch

from mt5_signal_bot import (
    evaluate_all_pairs_for_slot,
    next_full_hour_after_signal_slot,
    DayMode,
    SIGNAL_PAIRS,
)


def _d_dirs(xau="BUY", gbpusd="SELL", gbpaud="BUY", gbpjpy="SELL", gbpcad="BUY"):
    return {
        "XAUUSD": {"d_direction": xau, "d_state": "READY", "symbol": "XAUUSD", "source_symbol": "GBPUSD", "timeframe": "H4"},
        "GBPUSD": {"d_direction": gbpusd, "d_state": "READY", "symbol": "GBPUSD", "source_symbol": "GBPUSD", "timeframe": "H4"},
        "GBPAUD": {"d_direction": gbpaud, "d_state": "READY", "symbol": "GBPAUD", "source_symbol": "GBPAUD", "timeframe": "H4"},
        "GBPJPY": {"d_direction": gbpjpy, "d_state": "READY", "symbol": "GBPJPY", "source_symbol": "GBPJPY", "timeframe": "H4"},
        "GBPCAD": {"d_direction": gbpcad, "d_state": "READY", "symbol": "GBPCAD", "source_symbol": "GBPCAD", "timeframe": "H4"},
    }


def _timing(entry_time, symbol="XAUUSD"):
    return {
        "symbol": symbol,
        "entry_time": entry_time,
        "entry_state": "READY",
        "layer1": {"group": "BT"},
        "layer2": {"group": "BT"},
        "layer3": None,
    }


def _symbol_timing(symbol, entry_time):
    """Return timing dict for any symbol."""
    return _timing(entry_time, symbol=symbol)


# Use Monday July 27 to avoid final inversion rules (Wed/Thu at H3, Tue/Wed/Fri at H16, Tue/Wed at H14)
_MONDAY = datetime(2026, 7, 27)


class CrossPairSignalMappingTests(unittest.TestCase):
    """In v82, each pair uses its own D-Direction independently via Day Mode + independent M30 entry."""

    @patch("mt5_signal_bot.BROKER_CLOCK")
    def test_h3_all_pairs_use_own_d_with_day_mode_h11(self, mock_clock):
        mock_clock.utc_offset_for_date.return_value = 3
        mode = DayMode(mode="DAY_MODE_H11", source_hour=3, source_entry_time="03:11", source_branch="H_11")
        with (
            patch("mt5_signal_bot.calculate_all_d_directions", return_value=_d_dirs()),
            patch("mt5_signal_bot.evaluate_symbol_entry_timing_m30", side_effect=lambda sym, *a, **kw: _symbol_timing(sym, "03:11")),
        ):
            result = evaluate_all_pairs_for_slot(_MONDAY.replace(hour=3), 3, day_mode=mode)

        # H_11 matches DAY_MODE_H11 → KEEP_D for all pairs
        self.assertEqual(result["pair_dirs"]["XAUUSD"], "BUY")
        self.assertEqual(result["pair_dirs"]["GBPUSD"], "SELL")
        self.assertEqual(result["pair_dirs"]["GBPAUD"], "BUY")

    @patch("mt5_signal_bot.BROKER_CLOCK")
    def test_h7_gbpusd_independent_of_xauusd(self, mock_clock):
        """GBPUSD uses its own D, not XAUUSD's D."""
        mock_clock.utc_offset_for_date.return_value = 3
        mode = DayMode(mode="DAY_MODE_H11", source_hour=3, source_entry_time="03:11", source_branch="H_11")
        with (
            patch("mt5_signal_bot.calculate_all_d_directions", return_value=_d_dirs(xau="BUY", gbpusd="SELL")),
            patch("mt5_signal_bot.evaluate_symbol_entry_timing_m30", side_effect=lambda sym, *a, **kw: _symbol_timing(sym, "07:11")),
        ):
            result = evaluate_all_pairs_for_slot(_MONDAY.replace(hour=7), 7, day_mode=mode)

        # XAUUSD D=BUY, KEEP_D → BUY
        self.assertEqual(result["pair_dirs"]["XAUUSD"], "BUY")
        # GBPUSD D=SELL, KEEP_D → SELL (independent of XAUUSD)
        self.assertEqual(result["pair_dirs"]["GBPUSD"], "SELL")

    @patch("mt5_signal_bot.BROKER_CLOCK")
    def test_h12_each_pair_independent(self, mock_clock):
        mock_clock.utc_offset_for_date.return_value = 3
        mode = DayMode(mode="DAY_MODE_H11", source_hour=3, source_entry_time="03:11", source_branch="H_11")
        with (
            patch("mt5_signal_bot.calculate_all_d_directions", return_value=_d_dirs()),
            patch("mt5_signal_bot.evaluate_symbol_entry_timing_m30", side_effect=lambda sym, *a, **kw: _symbol_timing(sym, "12:11")),
        ):
            result = evaluate_all_pairs_for_slot(_MONDAY.replace(hour=12), 12, day_mode=mode)

        # Each pair uses its own D independently
        self.assertEqual(result["pair_dirs"]["XAUUSD"], "BUY")
        self.assertEqual(result["pair_dirs"]["GBPUSD"], "SELL")
        self.assertEqual(result["pair_dirs"]["GBPAUD"], "BUY")

    def test_gbp_entry_schedule_is_next_full_hour(self):
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 3, 0)), "04:00")
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 7, 0)), "08:00")
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 9, 0)), "10:00")
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 12, 0)), "13:00")
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 14, 0)), "15:00")
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 16, 0)), "17:00")


if __name__ == "__main__":
    unittest.main()
