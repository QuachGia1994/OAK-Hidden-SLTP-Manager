import unittest
from datetime import datetime, timezone
from mt5_signal_bot import MT4FeedProvider

class TestMT4MarketDataProvider(unittest.TestCase):
    def test_provider_name_is_mt4(self):
        provider = MT4FeedProvider()
        self.assertEqual(provider.name, "MT4")

    def test_register_and_get_bars(self):
        provider = MT4FeedProvider()
        b_dt = datetime(2026, 7, 30, 20, 0, tzinfo=timezone.utc)
        bar = {"broker_dt": b_dt, "open": 1.34646, "high": 1.34766, "low": 1.34545, "close": 1.34639}
        provider.register_bars("GBPUSD", "H4", [bar])

        res_exact = provider.get_exact_bar("GBPUSD", "H4", b_dt)
        self.assertIsNotNone(res_exact)
        self.assertEqual(res_exact["open"], 1.34646)

        res_bars = provider.get_bars("GBPUSD", "H4", b_dt, b_dt)
        self.assertEqual(len(res_bars), 1)

        res_empty = provider.get_bars("XAUUSD", "H4", b_dt, b_dt)
        self.assertEqual(len(res_empty), 0)

if __name__ == "__main__":
    unittest.main()
