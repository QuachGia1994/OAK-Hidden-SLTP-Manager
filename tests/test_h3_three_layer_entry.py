import unittest
from datetime import datetime
from unittest.mock import patch
from mt5_signal_bot import evaluate_xau_entry_timing_m30

class TestH3ThreeLayerEntry(unittest.TestCase):
    @patch("mt5_signal_bot.read_completed_m30_candle_by_open_time")
    def test_h3_layer2_bt_immediate_0311(self, mock_read):
        # H3 Layer 2 uses 3 candles: C1=02:30, C2=02:00, C3=01:30
        # Case: C1=TANG, C2=GIAM, C3=TANG -> Case 7 BT
        def fake_candle(symbol, open_dt, as_of_dt=None):
            t_str = open_dt.strftime("%H:%M")
            if t_str == "02:30":
                return {"open": "2300.0", "close": "2305.0", "high": "2306.0", "low": "2299.0"} # TANG
            if t_str == "02:00":
                return {"open": "2305.0", "close": "2300.0", "high": "2306.0", "low": "2299.0"} # GIAM
            if t_str == "01:30":
                return {"open": "2300.0", "close": "2305.0", "high": "2306.0", "low": "2299.0"} # TANG
            return None

        mock_read.side_effect = fake_candle

        slot_dt = datetime(2026, 7, 30, 3, 0, 0)
        res = evaluate_xau_entry_timing_m30(slot_dt, 3, as_of_dt=slot_dt)
        self.assertEqual(res["entry_state"], "READY")
        self.assertEqual(res["entry_time"], "03:11")

    @patch("mt5_signal_bot.read_completed_m30_candle_by_open_time")
    def test_h3_layer2_sw_pending(self, mock_read):
        # H3 Layer 2: C1=TANG, C2=TANG, C3=TANG -> Case 1 SW
        def fake_candle(symbol, open_dt, as_of_dt=None):
            t_str = open_dt.strftime("%H:%M")
            if t_str in ("02:30", "02:00", "01:30"):
                return {"open": "2300.0", "close": "2305.0", "high": "2306.0", "low": "2299.0"} # TANG
            return None

        mock_read.side_effect = fake_candle

        slot_dt = datetime(2026, 7, 30, 3, 0, 0)
        res = evaluate_xau_entry_timing_m30(slot_dt, 3, as_of_dt=slot_dt)
        self.assertEqual(res["entry_state"], "PENDING_LAYER3")
        self.assertEqual(res["entry_candidates"], ["03:49", "04:49"])
        self.assertEqual(res["entry_resolution_time"], "03:30")

    @patch("mt5_signal_bot.read_completed_m30_candle_by_open_time")
    def test_h3_layer3_bt_resolves_0449(self, mock_read):
        # H3 Layer 3 at 03:30: C1(03:00)=TANG, C2(02:30)=TANG, C3(02:00)=GIAM, C4(01:30)=GIAM -> Rule 4 BT -> 04:49
        def fake_candle(symbol, open_dt, as_of_dt=None):
            t_str = open_dt.strftime("%H:%M")
            if t_str in ("03:00", "02:30"):
                return {"open": "2300.0", "close": "2305.0", "high": "2306.0", "low": "2299.0"} # TANG
            return {"open": "2305.0", "close": "2300.0", "high": "2306.0", "low": "2299.0"} # GIAM

        mock_read.side_effect = fake_candle

        slot_dt = datetime(2026, 7, 30, 3, 0, 0)
        as_of_dt = datetime(2026, 7, 30, 3, 30, 0)
        res = evaluate_xau_entry_timing_m30(slot_dt, 3, as_of_dt=as_of_dt)
        self.assertEqual(res["entry_state"], "READY")
        self.assertEqual(res["entry_time"], "04:49")

if __name__ == "__main__":
    unittest.main()
