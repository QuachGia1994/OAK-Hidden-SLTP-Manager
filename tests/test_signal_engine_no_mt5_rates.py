import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from mt5_signal_bot import (
    evaluate_all_pairs_for_slot,
    MT4FeedProvider,
    set_market_data_provider,
    calculate_all_d_directions,
)


class TestSignalEngineNoMT5Rates(unittest.TestCase):

    @patch("mt5_signal_bot.BROKER_CLOCK")
    def test_signal_and_d_evaluation_never_call_mt5_copy_rates(self, mock_clock):
        mock_clock.utc_offset_for_date.return_value = 3
        mock_clock.mt5_timestamp_from_broker_datetime.side_effect = lambda dt: int(dt.replace(tzinfo=timezone.utc).timestamp())

        provider = MT4FeedProvider()
        b_dt = datetime(2026, 7, 30, 20, 0, tzinfo=timezone.utc)

        # Register sample bars on provider
        for sym in ("GBPUSD", "XAUUSD", "GBPAUD", "GBPJPY", "GBPCAD"):
            provider.register_bars(sym, "16388", [{"broker_dt": datetime(2026, 7, 30, 20, 0), "time": int(b_dt.timestamp()), "open": 1.34, "high": 1.35, "low": 1.33, "close": 1.345}])
            provider.register_bars(sym, "16385", [{"broker_dt": datetime(2026, 7, 31, 14, 0), "time": int(b_dt.timestamp()), "open": 1.34, "high": 1.35, "low": 1.33, "close": 1.345}])

        set_market_data_provider(provider)

        with patch("mt5_signal_bot.mt5") as mock_mt5:
            mock_mt5.copy_rates_from.side_effect = AssertionError("MT5 copy_rates_from must NOT be called!")
            mock_mt5.copy_rates_range.side_effect = AssertionError("MT5 copy_rates_range must NOT be called!")
            mock_mt5.copy_rates_from_pos.side_effect = AssertionError("MT5 copy_rates_from_pos must NOT be called!")

            d_res = calculate_all_d_directions(datetime(2026, 7, 31).date())
            self.assertIsNotNone(d_res)

            slot_dt = datetime(2026, 7, 31, 14, 0)
            res = evaluate_all_pairs_for_slot(slot_dt, 14)
            self.assertIsNotNone(res)


if __name__ == "__main__":
    unittest.main()
