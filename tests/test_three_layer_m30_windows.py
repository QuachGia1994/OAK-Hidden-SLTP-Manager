import unittest
from datetime import datetime
from mt5_signal_bot import get_m30_layer_open_times

class TestThreeLayerM30Windows(unittest.TestCase):
    def test_h7_m30_open_times(self):
        slot_dt = datetime(2026, 7, 30, 7, 0, 0)
        windows = get_m30_layer_open_times(slot_dt)

        # Layer 1 (GBP): C1=06:00, C2=05:30, C3=05:00
        l1_times = [t.strftime("%H:%M") for t in windows["layer1"]]
        self.assertEqual(l1_times, ["06:00", "05:30", "05:00"])

        # Layer 2 (XAU): C1=06:30, C2=06:00, C3=05:30
        l2_times = [t.strftime("%H:%M") for t in windows["layer2"]]
        self.assertEqual(l2_times, ["06:30", "06:00", "05:30"])

        # Layer 3 (XAU): C1=07:00, C2=06:30, C3=06:00
        l3_times = [t.strftime("%H:%M") for t in windows["layer3"]]
        self.assertEqual(l3_times, ["07:00", "06:30", "06:00"])

    def test_h3_m30_open_times(self):
        slot_dt = datetime(2026, 7, 30, 3, 0, 0)
        windows = get_m30_layer_open_times(slot_dt)

        # Layer 1 (GBP): C1=02:00, C2=01:30, C3=01:00
        l1_times = [t.strftime("%H:%M") for t in windows["layer1"]]
        self.assertEqual(l1_times, ["02:00", "01:30", "01:00"])

        # Layer 2 (XAU H3 - 3 candles): C1=02:30, C2=02:00, C3=01:30
        l2_times = [t.strftime("%H:%M") for t in windows["layer2"]]
        self.assertEqual(l2_times, ["02:30", "02:00", "01:30"])

        # Layer 3 (XAU H3 - 3 candles): C1=03:00, C2=02:30, C3=02:00
        l3_times = [t.strftime("%H:%M") for t in windows["layer3"]]
        self.assertEqual(l3_times, ["03:00", "02:30", "02:00"])

if __name__ == "__main__":
    unittest.main()
