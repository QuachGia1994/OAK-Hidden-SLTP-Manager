import unittest
from datetime import datetime
from unittest.mock import patch
from mt5_signal_bot import evaluate_xau_entry_timing_m30

class TestH7ThreeLayerEntry(unittest.TestCase):
    @patch("mt5_signal_bot.read_completed_m30_candle_by_open_time")
    def test_layer2_bt_immediate_h11(self, mock_read):
        # Layer 2: BT (e.g. C1=TANG, C2=TANG, C3=GIAM, C4=GIAM) -> Rule 4 BT
        def fake_candle(symbol, open_dt, as_of_dt=None):
            t_str = open_dt.strftime("%H:%M")
            if t_str == "06:30":
                return {"open": "2300.0", "close": "2305.0", "high": "2306.0", "low": "2299.0"} # TANG
            if t_str == "06:00":
                return {"open": "2295.0", "close": "2300.0", "high": "2301.0", "low": "2294.0"} # TANG
            if t_str == "05:30":
                return {"open": "2295.0", "close": "2290.0", "high": "2296.0", "low": "2289.0"} # GIAM
            if t_str == "05:00":
                return {"open": "2290.0", "close": "2285.0", "high": "2291.0", "low": "2284.0"} # GIAM
            return None

        mock_read.side_effect = fake_candle

        slot_dt = datetime(2026, 7, 30, 7, 0, 0)
        res = evaluate_xau_entry_timing_m30(slot_dt, 7, as_of_dt=slot_dt)
        self.assertEqual(res["entry_state"], "READY")
        self.assertEqual(res["entry_time"], "07:11")

    @patch("mt5_signal_bot.read_completed_m30_candle_by_open_time")
    def test_layer2_sw_pending_layer3(self, mock_read):
        # Layer 2: SW (e.g. C1=TANG, C2=TANG, C3=TANG, C4=TANG) -> Rule 1 SW
        def fake_candle(symbol, open_dt, as_of_dt=None):
            t_str = open_dt.strftime("%H:%M")
            if t_str in ("06:30", "06:00", "05:30", "05:00"):
                return {"open": "2300.0", "close": "2305.0", "high": "2306.0", "low": "2299.0"} # TANG
            return None # 07:00 candle not available yet at 07:00

        mock_read.side_effect = fake_candle

        slot_dt = datetime(2026, 7, 30, 7, 0, 0)
        res = evaluate_xau_entry_timing_m30(slot_dt, 7, as_of_dt=slot_dt)
        self.assertEqual(res["entry_state"], "PENDING_LAYER3")
        self.assertEqual(res["entry_time"], None)
        self.assertEqual(res["entry_candidates"], ["07:49", "08:25"])
        self.assertEqual(res["entry_resolution_time"], "07:30")

    @patch("mt5_signal_bot.read_completed_m30_candle_by_open_time")
    def test_layer3_sw_resolves_h49(self, mock_read):
        # Layer 2 SW; Layer 3 at 07:30: C1(07:00)=TANG, C2(06:30)=TANG, C3(06:00)=TANG, C4(05:30)=TANG -> Rule 1 SW
        def fake_candle(symbol, open_dt, as_of_dt=None):
            return {"open": "2300.0", "close": "2305.0", "high": "2306.0", "low": "2299.0"}

        mock_read.side_effect = fake_candle

        slot_dt = datetime(2026, 7, 30, 7, 0, 0)
        as_of_dt = datetime(2026, 7, 30, 7, 30, 0)
        res = evaluate_xau_entry_timing_m30(slot_dt, 7, as_of_dt=as_of_dt)
        self.assertEqual(res["entry_state"], "READY")
        self.assertEqual(res["entry_time"], "07:49")

    @patch("mt5_signal_bot.read_completed_m30_candle_by_open_time")
    def test_layer3_bt_resolves_hplus1_25(self, mock_read):
        # Layer 2: SW (C1(06:30)=TANG, C2=TANG, C3=TANG, C4=TANG)
        # Layer 3: BT (C1(07:00)=TANG, C2(06:30)=TANG, C3(06:00)=GIAM, C4(05:30)=GIAM) -> Rule 4 BT
        def fake_candle(symbol, open_dt, as_of_dt=None):
            t_str = open_dt.strftime("%H:%M")
            if t_str in ("07:00", "06:30"):
                return {"open": "2300.0", "close": "2305.0", "high": "2306.0", "low": "2299.0"} # TANG
            return {"open": "2305.0", "close": "2300.0", "high": "2306.0", "low": "2299.0"} # GIAM

        mock_read.side_effect = fake_candle

        slot_dt = datetime(2026, 7, 30, 7, 0, 0)
        as_of_dt = datetime(2026, 7, 30, 7, 30, 0)
        res = evaluate_xau_entry_timing_m30(slot_dt, 7, as_of_dt=as_of_dt)
        self.assertEqual(res["entry_state"], "READY")
        self.assertEqual(res["entry_time"], "08:25")

if __name__ == "__main__":
    unittest.main()
