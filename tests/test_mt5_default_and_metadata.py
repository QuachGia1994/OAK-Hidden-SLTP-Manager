import unittest

import mt5_signal_bot
from mt5_signal_bot import D_SOURCE_SYMBOL


class TestMT5DefaultAndMetadata(unittest.TestCase):
    def test_default_market_data_provider_is_mt5(self):
        self.assertEqual(getattr(mt5_signal_bot.MARKET_DATA_PROVIDER, "name", ""), "MT5")

    def test_xauusd_direction_shares_gbpusd_d_source(self):
        self.assertEqual(D_SOURCE_SYMBOL["XAUUSD"], "GBPUSD")

    def test_all_active_pairs_have_explicit_d_source(self):
        for symbol in mt5_signal_bot.ACTIVE_SIGNAL_PAIRS:
            self.assertIn(symbol, D_SOURCE_SYMBOL)
            self.assertTrue(D_SOURCE_SYMBOL[symbol])


if __name__ == "__main__":
    unittest.main()
