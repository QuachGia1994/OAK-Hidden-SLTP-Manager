"""Test BrokerClock symbol resolution and suffix support (v84)."""
import unittest
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.broker_clock import BrokerClock


class TestBrokerClockSymbolResolution(unittest.TestCase):
    """Verify BrokerClock handles resolved symbol suffixes properly."""

    def test_configure_symbols_updates_internal_tuples_and_clears_calibration(self):
        mock_mt5 = MagicMock()
        clock = BrokerClock(mt5_module=mock_mt5, symbols=("XAUUSD", "GBPUSD"))
        self.assertEqual(clock._symbols, ("XAUUSD", "GBPUSD"))

        clock.configure_symbols(["XAUUSD+", "GBPUSD+", "GBPAUD+"])
        self.assertEqual(clock._symbols, ("XAUUSD+", "GBPUSD+", "GBPAUD+"))
        self.assertEqual(clock._daily_symbols, ("XAUUSD+", "GBPUSD+", "GBPAUD+"))
        self.assertIsNone(clock.timestamp_mode)

    def test_configure_symbols_ignores_empty_strings(self):
        mock_mt5 = MagicMock()
        clock = BrokerClock(mt5_module=mock_mt5, symbols=("XAUUSD",))
        clock.configure_symbols(["", "GBPUSD+", "  "])
        self.assertEqual(clock._symbols, ("GBPUSD+",))


if __name__ == "__main__":
    unittest.main()
