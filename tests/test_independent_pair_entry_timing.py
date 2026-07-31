"""Test independent per-symbol M30 entry timing (v82)."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_candle(open_price, close_price):
    return {"open": open_price, "high": max(open_price, close_price) + 1,
            "low": min(open_price, close_price) - 1, "close": close_price,
            "time": 0, "tick_volume": 100}


class TestIndependentPairEntryTiming(unittest.TestCase):
    """Each symbol runs its own M30 entry engine independently."""

    @patch("mt5_signal_bot._read_m30_open_windows")
    def test_h7_independent_entries(self, mock_read):
        """H7: XAU BT, GBPUSD SW→SW, GBPAUD SW→BT → three different entries."""
        from mt5_signal_bot import evaluate_symbol_entry_timing_m30

        slot_dt = datetime(2026, 7, 29, 7, 0, 0)
        far_future = slot_dt + timedelta(days=1)

        # XAUUSD: Layer 2 BT (G,T,G = BT)
        xau_candles = {
            slot_dt - timedelta(minutes=30): _make_candle(2000, 1999),  # GIAM
            slot_dt - timedelta(minutes=60): _make_candle(1999, 2001),  # TANG
            slot_dt - timedelta(minutes=90): _make_candle(2001, 1998),  # GIAM
        }
        # GBPUSD: Layer 2 SW (T,T,T = SW), Layer 3 SW (T,T,T = SW)
        gbp_candles = {
            slot_dt - timedelta(minutes=30): _make_candle(1.25, 1.26),  # TANG
            slot_dt - timedelta(minutes=60): _make_candle(1.24, 1.25),  # TANG
            slot_dt - timedelta(minutes=90): _make_candle(1.23, 1.24),  # TANG
            slot_dt: _make_candle(1.26, 1.27),  # TANG (L3)
        }
        # GBPAUD: Layer 2 SW (T,T,T = SW), Layer 3 BT (G,G,T = BT)
        aud_candles = {
            slot_dt - timedelta(minutes=30): _make_candle(1.90, 1.91),  # TANG
            slot_dt - timedelta(minutes=60): _make_candle(1.89, 1.90),  # TANG
            slot_dt - timedelta(minutes=90): _make_candle(1.88, 1.89),  # TANG
            slot_dt: _make_candle(1.92, 1.90),  # GIAM (L3 C1)
            slot_dt - timedelta(minutes=30): _make_candle(1.91, 1.90),  # GIAM (L3 C2)
            slot_dt - timedelta(minutes=60): _make_candle(1.89, 1.91),  # TANG (L3 C3)
        }

        def side_effect(symbol, open_times, as_of_dt=None):
            if symbol == "XAUUSD":
                return {ot: xau_candles.get(ot) for ot in open_times}
            elif symbol == "GBPUSD":
                return {ot: gbp_candles.get(ot) for ot in open_times}
            elif symbol == "GBPAUD":
                return {ot: aud_candles.get(ot) for ot in open_times}
            return {ot: None for ot in open_times}

        mock_read.side_effect = side_effect

        xau_result = evaluate_symbol_entry_timing_m30("XAUUSD", slot_dt, 7, as_of_dt=far_future)
        gbp_result = evaluate_symbol_entry_timing_m30("GBPUSD", slot_dt, 7, as_of_dt=far_future)
        aud_result = evaluate_symbol_entry_timing_m30("GBPAUD", slot_dt, 7, as_of_dt=far_future)

        self.assertEqual(xau_result["entry_time"], "07:11")
        self.assertEqual(xau_result["entry_state"], "READY")

        self.assertEqual(gbp_result["entry_time"], "07:49")
        self.assertEqual(gbp_result["entry_state"], "READY")

        self.assertEqual(aud_result["entry_time"], "08:25")
        self.assertEqual(aud_result["entry_state"], "READY")

        # All three must be different
        entries = {xau_result["entry_time"], gbp_result["entry_time"], aud_result["entry_time"]}
        self.assertEqual(len(entries), 3, "All three entries must be distinct")

    @patch("mt5_signal_bot._read_m30_open_windows")
    def test_symbol_field_matches_input(self, mock_read):
        """Each result's symbol field must match the input symbol."""
        from mt5_signal_bot import evaluate_symbol_entry_timing_m30

        slot_dt = datetime(2026, 7, 29, 3, 0, 0)
        mock_read.return_value = {}

        for sym in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD"):
            result = evaluate_symbol_entry_timing_m30(sym, slot_dt, 3)
            self.assertEqual(result["symbol"], sym)


if __name__ == "__main__":
    unittest.main()
