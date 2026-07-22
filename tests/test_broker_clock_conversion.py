"""Broker-clock conversion used by Telegram quick orders."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from domain.copy_trade_manager import _broker_clock_to_local_clock, _live_broker_utc_offset


class BrokerClockConversionTests(unittest.TestCase):
    def test_converts_gmt3_broker_to_gmt7_windows_clock(self):
        self.assertEqual(_broker_clock_to_local_clock("09:15", 3, 7), "13:15")

    def test_wraps_across_midnight(self):
        self.assertEqual(_broker_clock_to_local_clock("23:30", 3, 7), "03:30")

    def test_rejects_invalid_clock_or_offset(self):
        for args in (("24:00", 3, 7), ("09:60", 3, 7), ("09:15", 20, 7)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                _broker_clock_to_local_clock(*args)

    @patch("domain.copy_trade_manager.time.time", return_value=1_000)
    @patch("domain.copy_trade_manager.mt5.symbol_info_tick")
    def test_reads_same_server_clock_offset_used_by_signal_slots(self, symbol_tick, _time):
        symbol_tick.return_value = SimpleNamespace(time=1_000 + 3 * 3_600)

        self.assertEqual(_live_broker_utc_offset(), 3)

    @patch("domain.copy_trade_manager.mt5.symbol_info_tick", return_value=None)
    def test_refuses_to_guess_when_live_broker_clock_is_unavailable(self, _symbol_tick):
        with self.assertRaises(ValueError):
            _live_broker_utc_offset()


if __name__ == "__main__":
    unittest.main()
