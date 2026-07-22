# -*- coding: utf-8 -*-
"""Unit tests for H=11 XAUUSD H1 4-candle classification rules (SW/BT)."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from mt5_signal_bot import evaluate_h11_classification


class TestH11Classification(unittest.TestCase):
    @patch("mt5_signal_bot.get_candle_by_ts")
    def test_evaluate_h11_rule_1_sw(self, mock_candle):
        # Rule 1: H10 Tăng, H9 Giảm, H8 Tăng, H7 Giảm => SW
        candles = {
            10: {"open": 2000.0, "close": 2010.0}, # T
            9:  {"open": 2010.0, "close": 2005.0}, # G
            8:  {"open": 2005.0, "close": 2012.0}, # T
            7:  {"open": 2012.0, "close": 2008.0}, # G
        }
        mock_candle.side_effect = lambda sym, tf, ts: candles.get(int(datetime.fromtimestamp(ts, tz=timezone.utc).hour))

        dt = datetime(2026, 7, 22, 17, 45, tzinfo=timezone.utc)
        group, detail = evaluate_h11_classification(dt)
        self.assertEqual(group, "SW")
        self.assertIn("H10:Tăng", detail)
        self.assertIn("H9:Giảm", detail)
        self.assertIn("H8:Tăng", detail)
        self.assertIn("H7:Giảm", detail)

    @patch("mt5_signal_bot.get_candle_by_ts")
    def test_evaluate_h11_rule_2_bt(self, mock_candle):
        # Rule 2: H10 Tăng, H9 Giảm, H8 Tăng, H7 Tăng => BT
        candles = {
            10: {"open": 2000.0, "close": 2010.0}, # T
            9:  {"open": 2010.0, "close": 2005.0}, # G
            8:  {"open": 2005.0, "close": 2012.0}, # T
            7:  {"open": 2008.0, "close": 2012.0}, # T
        }
        mock_candle.side_effect = lambda sym, tf, ts: candles.get(int(datetime.fromtimestamp(ts, tz=timezone.utc).hour))

        dt = datetime(2026, 7, 22, 17, 45, tzinfo=timezone.utc)
        group, detail = evaluate_h11_classification(dt)
        self.assertEqual(group, "BT")

    @patch("mt5_signal_bot.get_candle_by_ts")
    def test_evaluate_h11_rule_3_bt(self, mock_candle):
        # Rule 3: H10 Tăng, H9 Tăng, H8 Giảm => BT
        candles = {
            10: {"open": 2000.0, "close": 2010.0}, # T
            9:  {"open": 2005.0, "close": 2010.0}, # T
            8:  {"open": 2012.0, "close": 2005.0}, # G
            7:  {"open": 2008.0, "close": 2012.0}, # T
        }
        mock_candle.side_effect = lambda sym, tf, ts: candles.get(int(datetime.fromtimestamp(ts, tz=timezone.utc).hour))

        dt = datetime(2026, 7, 22, 17, 45, tzinfo=timezone.utc)
        group, detail = evaluate_h11_classification(dt)
        self.assertEqual(group, "BT")

    @patch("mt5_signal_bot.get_candle_by_ts")
    def test_evaluate_h11_rule_4_sw(self, mock_candle):
        # Rule 4: H10 Tăng, H9 Tăng, H8 Tăng => SW
        candles = {
            10: {"open": 2000.0, "close": 2010.0}, # T
            9:  {"open": 2005.0, "close": 2010.0}, # T
            8:  {"open": 2000.0, "close": 2005.0}, # T
            7:  {"open": 2008.0, "close": 2012.0}, # T
        }
        mock_candle.side_effect = lambda sym, tf, ts: candles.get(int(datetime.fromtimestamp(ts, tz=timezone.utc).hour))

        dt = datetime(2026, 7, 22, 17, 45, tzinfo=timezone.utc)
        group, detail = evaluate_h11_classification(dt)
        self.assertEqual(group, "SW")

    @patch("mt5_signal_bot.get_candle_by_ts")
    def test_evaluate_h11_rule_5_sw(self, mock_candle):
        # Rule 5: H10 Tăng, H9 Giảm, H8 Giảm => SW
        candles = {
            10: {"open": 2000.0, "close": 2010.0}, # T
            9:  {"open": 2010.0, "close": 2005.0}, # G
            8:  {"open": 2008.0, "close": 2002.0}, # G
            7:  {"open": 2008.0, "close": 2012.0}, # T
        }
        mock_candle.side_effect = lambda sym, tf, ts: candles.get(int(datetime.fromtimestamp(ts, tz=timezone.utc).hour))

        dt = datetime(2026, 7, 22, 17, 45, tzinfo=timezone.utc)
        group, detail = evaluate_h11_classification(dt)
        self.assertEqual(group, "SW")

    @patch("mt5_signal_bot.get_candle_by_ts")
    def test_evaluate_h11_inverted_rule_6_sw(self, mock_candle):
        # Inverted Rule 6 (of 1): H10 Giảm, H9 Tăng, H8 Giảm, H7 Tăng => SW
        candles = {
            10: {"open": 2010.0, "close": 2000.0}, # G
            9:  {"open": 2005.0, "close": 2010.0}, # T
            8:  {"open": 2012.0, "close": 2005.0}, # G
            7:  {"open": 2008.0, "close": 2012.0}, # T
        }
        mock_candle.side_effect = lambda sym, tf, ts: candles.get(int(datetime.fromtimestamp(ts, tz=timezone.utc).hour))

        dt = datetime(2026, 7, 22, 17, 45, tzinfo=timezone.utc)
        group, detail = evaluate_h11_classification(dt)
        self.assertEqual(group, "SW")


if __name__ == "__main__":
    unittest.main()
