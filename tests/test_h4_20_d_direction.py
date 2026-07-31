"""Test H4 20:00 D-Direction source (v82)."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_h4_candle(open_price, close_price, open_ts):
    return {"open": open_price, "high": max(open_price, close_price) + 1,
            "low": min(open_price, close_price) - 1, "close": close_price,
            "time": open_ts, "tick_volume": 500}


class TestH420DDirection(unittest.TestCase):
    """D-Direction uses H4 candle opened at exactly 20:00 Broker."""

    @patch("mt5_signal_bot.find_previous_session_h4_20_candle")
    def test_d_source_mapping(self, mock_h4):
        """Each symbol uses correct D source per D_SOURCE_SYMBOL mapping."""
        from mt5_signal_bot import calculate_all_d_directions, clear_d_direction_cache

        clear_d_direction_cache()
        target_date = datetime(2026, 7, 31).date()

        # GBPUSD H4 20:00 = BUY (close > open)
        # GBPAUD H4 20:00 = SELL (close < open)
        # GBPJPY H4 20:00 = BUY
        # GBPCAD H4 20:00 = SELL
        session_date = datetime(2026, 7, 30).date()
        broker_offset = 3

        def side_effect(source_symbol, target_broker_date):
            if source_symbol == "GBPUSD":
                candle = _make_h4_candle(1.25, 1.26, 0)  # TANG → BUY
                return candle, session_date, broker_offset
            elif source_symbol == "GBPAUD":
                candle = _make_h4_candle(1.95, 1.93, 0)  # GIAM → SELL
                return candle, session_date, broker_offset
            elif source_symbol == "GBPJPY":
                candle = _make_h4_candle(190.0, 191.0, 0)  # TANG → BUY
                return candle, session_date, broker_offset
            elif source_symbol == "GBPCAD":
                candle = _make_h4_candle(1.75, 1.73, 0)  # GIAM → SELL
                return candle, session_date, broker_offset
            return None, None, None

        mock_h4.side_effect = side_effect

        results = calculate_all_d_directions(target_date)

        # XAUUSD D = GBPUSD D = BUY
        self.assertEqual(results["XAUUSD"]["d_direction"], "BUY")
        self.assertEqual(results["XAUUSD"]["source_symbol"], "GBPUSD")

        # GBPUSD D = BUY
        self.assertEqual(results["GBPUSD"]["d_direction"], "BUY")
        self.assertEqual(results["GBPUSD"]["source_symbol"], "GBPUSD")

        # GBPAUD D = SELL
        self.assertEqual(results["GBPAUD"]["d_direction"], "SELL")
        self.assertEqual(results["GBPAUD"]["source_symbol"], "GBPAUD")

        # GBPJPY D = BUY
        self.assertEqual(results["GBPJPY"]["d_direction"], "BUY")
        self.assertEqual(results["GBPJPY"]["source_symbol"], "GBPJPY")

        # GBPCAD D = SELL
        self.assertEqual(results["GBPCAD"]["d_direction"], "SELL")
        self.assertEqual(results["GBPCAD"]["source_symbol"], "GBPCAD")

    @patch("mt5_signal_bot.find_previous_session_h4_20_candle")
    def test_missing_h4_20_no_fallback(self, mock_h4):
        """If H4 20:00 is missing, D=WAIT with MISSING_H4_20, no fallback."""
        from mt5_signal_bot import calculate_all_d_directions, clear_d_direction_cache

        clear_d_direction_cache()
        target_date = datetime(2026, 7, 31).date()
        session_date = datetime(2026, 7, 30).date()
        broker_offset = 3

        # GBPUSD: session exists but no H4 20:00
        def side_effect(source_symbol, target_broker_date):
            if source_symbol == "GBPUSD":
                return None, session_date, broker_offset  # No 20:00 candle
            elif source_symbol == "GBPAUD":
                return None, session_date, broker_offset
            elif source_symbol == "GBPJPY":
                return None, session_date, broker_offset
            elif source_symbol == "GBPCAD":
                return None, session_date, broker_offset
            return None, None, None

        mock_h4.side_effect = side_effect

        results = calculate_all_d_directions(target_date)

        # XAUUSD and GBPUSD both WAIT because GBPUSD source is missing
        self.assertEqual(results["XAUUSD"]["d_direction"], "WAIT")
        self.assertEqual(results["XAUUSD"]["d_state"], "MISSING_H4_20")
        self.assertEqual(results["GBPUSD"]["d_direction"], "WAIT")
        self.assertEqual(results["GBPUSD"]["d_state"], "MISSING_H4_20")

        # GBPAUD also WAIT
        self.assertEqual(results["GBPAUD"]["d_direction"], "WAIT")
        self.assertEqual(results["GBPAUD"]["d_state"], "MISSING_H4_20")

    @patch("mt5_signal_bot.find_previous_session_h4_20_candle")
    def test_xau_shares_gbpusd_candle(self, mock_h4):
        """XAUUSD and GBPUSD share the same source candle."""
        from mt5_signal_bot import calculate_all_d_directions, clear_d_direction_cache

        clear_d_direction_cache()
        target_date = datetime(2026, 7, 31).date()
        session_date = datetime(2026, 7, 30).date()
        broker_offset = 3

        def side_effect(source_symbol, target_broker_date):
            if source_symbol == "GBPUSD":
                candle = _make_h4_candle(1.25, 1.26, 0)
                return candle, session_date, broker_offset
            return None, session_date, broker_offset

        mock_h4.side_effect = side_effect

        results = calculate_all_d_directions(target_date)

        xau_candle = results["XAUUSD"]["candle"]
        gbp_candle = results["GBPUSD"]["candle"]
        self.assertEqual(xau_candle, gbp_candle, "XAU and GBP must share same source candle")


class TestXauUsesGbpusdD(unittest.TestCase):
    """XAUUSD must use GBPUSD H4 20:00 for D, not its own."""

    def test_d_source_symbol_mapping(self):
        from mt5_signal_bot import D_SOURCE_SYMBOL
        self.assertEqual(D_SOURCE_SYMBOL["XAUUSD"], "GBPUSD")
        self.assertEqual(D_SOURCE_SYMBOL["GBPUSD"], "GBPUSD")
        self.assertEqual(D_SOURCE_SYMBOL["GBPAUD"], "GBPAUD")
        self.assertEqual(D_SOURCE_SYMBOL["GBPJPY"], "GBPJPY")
        self.assertEqual(D_SOURCE_SYMBOL["GBPCAD"], "GBPCAD")


if __name__ == "__main__":
    unittest.main()
