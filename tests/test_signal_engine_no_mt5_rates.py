import unittest
from datetime import datetime
from unittest.mock import Mock

import mt5_signal_bot
from providers.mt5_market_data_provider import MT5MarketDataProvider


class TestSignalEngineNoMT5Rates(unittest.TestCase):
    """Behavioral guard: signal evaluation uses the MT5 provider contract."""

    def test_signal_engine_does_not_call_mt5_copy_rates_directly(self):
        provider = Mock(spec=MT5MarketDataProvider)
        provider.name = "MT5"
        provider.get_health.return_value = Mock(state="connected", fresh=True)
        provider.get_broker_utc_offset.return_value = 3
        provider.get_exact_bar.return_value = {
            "time": 1785002400,
            "open": 1.34,
            "high": 1.35,
            "low": 1.33,
            "close": 1.345,
            "tick_volume": 100,
            "broker_dt": datetime(2026, 7, 25, 20, 0),
            "is_complete": True,
            "source_id": "mt5",
        }

        old_provider = mt5_signal_bot.MARKET_DATA_PROVIDER
        old_mt5 = mt5_signal_bot.mt5
        mock_mt5 = Mock()
        mock_mt5.copy_rates_from.side_effect = AssertionError("signal engine bypassed provider")
        mock_mt5.copy_rates_range.side_effect = AssertionError("signal engine bypassed provider")
        mock_mt5.copy_rates_from_pos.side_effect = AssertionError("signal engine bypassed provider")
        mt5_signal_bot.MARKET_DATA_PROVIDER = provider
        mt5_signal_bot.mt5 = mock_mt5
        try:
            result = mt5_signal_bot.get_candle_by_broker_datetime(
                "XAUUSD", "M30", datetime(2026, 7, 25, 20, 0)
            )
            self.assertIsNotNone(result)
            provider.get_exact_bar.assert_called_once()
            mock_mt5.copy_rates_from.assert_not_called()
            mock_mt5.copy_rates_range.assert_not_called()
            mock_mt5.copy_rates_from_pos.assert_not_called()
        finally:
            mt5_signal_bot.MARKET_DATA_PROVIDER = old_provider
            mt5_signal_bot.mt5 = old_mt5


if __name__ == "__main__":
    unittest.main()
