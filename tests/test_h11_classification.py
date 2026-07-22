# -*- coding: utf-8 -*-
"""Unit tests for H=11 XAUUSD H1 4-candle classification rules (SW/BT)."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from mt5_signal_bot import evaluate_h11_classification, get_h11_priority_and_nogold_rules


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


class TestH11PriorityAndNoGoldRules(unittest.TestCase):
    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_tue_rules_from_mon_h11(self, mock_eval):
        # Tuesday (weekday = 1). Yesterday = Mon.
        tue = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)

        # Mon SW => Tue Ưu tiên đi sớm H=2, no-gold=False
        mock_eval.return_value = ("SW", "")
        rules_sw = get_h11_priority_and_nogold_rules(tue)
        self.assertEqual(rules_sw["priority_slot"], 2)
        self.assertIn("đi sớm H=2", rules_sw["priority_label"])
        self.assertFalse(rules_sw["has_nogold_label"])

        # Mon BT => Tue Ưu tiên đi trễ H=3, no-gold=True
        mock_eval.return_value = ("BT", "")
        rules_bt = get_h11_priority_and_nogold_rules(tue)
        self.assertEqual(rules_bt["priority_slot"], 3)
        self.assertIn("đi trễ H=3", rules_bt["priority_label"])
        self.assertTrue(rules_bt["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_wed_rules_from_tue_h11(self, mock_eval):
        # Wednesday (weekday = 2). Yesterday = Tue.
        wed = datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc)

        # Tue SW => Wed Ưu tiên đi sớm H=2, no-gold=True
        mock_eval.return_value = ("SW", "")
        rules_sw = get_h11_priority_and_nogold_rules(wed)
        self.assertEqual(rules_sw["priority_slot"], 2)
        self.assertIn("đi sớm H=2", rules_sw["priority_label"])
        self.assertTrue(rules_sw["has_nogold_label"])

        # Tue BT => Wed Ưu tiên đi trễ H=3, no-gold=False
        mock_eval.return_value = ("BT", "")
        rules_bt = get_h11_priority_and_nogold_rules(wed)
        self.assertEqual(rules_bt["priority_slot"], 3)
        self.assertIn("đi trễ H=3", rules_bt["priority_label"])
        self.assertFalse(rules_bt["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_thu_rules_from_wed_h11(self, mock_eval):
        # Thursday (weekday = 3). Yesterday = Wed.
        thu = datetime(2026, 7, 23, 10, 0, tzinfo=timezone.utc)

        # Wed SW => Thu Ưu tiên đi trễ H=3, no-gold=True
        mock_eval.return_value = ("SW", "")
        rules_sw = get_h11_priority_and_nogold_rules(thu)
        self.assertEqual(rules_sw["priority_slot"], 3)
        self.assertIn("đi trễ H=3", rules_sw["priority_label"])
        self.assertTrue(rules_sw["has_nogold_label"])

        # Wed BT => Thu Ưu tiên đi trễ H=2, no-gold=False
        mock_eval.return_value = ("BT", "")
        rules_bt = get_h11_priority_and_nogold_rules(thu)
        self.assertEqual(rules_bt["priority_slot"], 2)
        self.assertIn("đi trễ H=2", rules_bt["priority_label"])
        self.assertFalse(rules_bt["has_nogold_label"])

    @patch("mt5_signal_bot.is_h2_special_calendar_weekday")
    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_fri_rules_from_thu_h11(self, mock_eval, mock_special):
        # Friday (weekday = 4). Yesterday = Thu.
        fri = datetime(2026, 7, 24, 10, 0, tzinfo=timezone.utc)

        # Thu SW + normal Fri => Fri Ưu tiên đi trễ H=3, no-gold=True
        mock_eval.return_value = ("SW", "")
        mock_special.return_value = False
        rules_sw_norm = get_h11_priority_and_nogold_rules(fri)
        self.assertEqual(rules_sw_norm["priority_slot"], 3)
        self.assertTrue(rules_sw_norm["has_nogold_label"])

        # Thu BT + special Fri => Fri Ưu tiên đi trễ H=2, no-gold=True
        mock_eval.return_value = ("BT", "")
        mock_special.return_value = True
        rules_bt_spec = get_h11_priority_and_nogold_rules(fri)
        self.assertEqual(rules_bt_spec["priority_slot"], 2)
        self.assertTrue(rules_bt_spec["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_mon_rules_from_fri_h11(self, mock_eval):
        # Monday (weekday = 0). Yesterday = Fri.
        mon = datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)

        # Fri SW => Mon Ưu tiên đi trễ H=3, no-gold=False
        mock_eval.return_value = ("SW", "")
        rules_sw = get_h11_priority_and_nogold_rules(mon)
        self.assertEqual(rules_sw["priority_slot"], 3)
        self.assertFalse(rules_sw["has_nogold_label"])

        # Fri BT => Mon Ưu tiên đi trễ H=2, no-gold=True
        mock_eval.return_value = ("BT", "")
        rules_bt = get_h11_priority_and_nogold_rules(mon)
        self.assertEqual(rules_bt["priority_slot"], 2)
        self.assertTrue(rules_bt["has_nogold_label"])


class TestH7H8PriorityRules(unittest.TestCase):
    @patch("mt5_signal_bot.get_candle_by_ts")
    @patch("mt5_signal_bot._lookup_h5_signal_today")
    def test_h6_tang_and_h78_tang_prioritizes_h8(self, mock_h5, mock_candle):
        # H=5 today is SELL -> H=7,8 calculated as reverse_signal(SELL) = BUY (Tăng)
        mock_h5.return_value = "SELL"
        # H=6 candle is Tăng (Close > Open)
        mock_candle.return_value = {"open": 2000.0, "close": 2010.0}

        dt = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
        from mt5_signal_bot import get_h7_h8_priority_rule
        rule = get_h7_h8_priority_rule(dt)
        self.assertIsNotNone(rule)
        self.assertEqual(rule["priority_slot"], 8)
        self.assertEqual(rule["priority_label"], "Ưu tiên đi H=8")

    @patch("mt5_signal_bot.get_candle_by_ts")
    @patch("mt5_signal_bot._lookup_h5_signal_today")
    def test_h6_giam_and_h78_tang_prioritizes_h7(self, mock_h5, mock_candle):
        # H=5 today is SELL -> H=7,8 calculated as reverse_signal(SELL) = BUY (Tăng)
        mock_h5.return_value = "SELL"
        # H=6 candle is Giảm (Close < Open)
        mock_candle.return_value = {"open": 2010.0, "close": 2000.0}

        dt = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
        from mt5_signal_bot import get_h7_h8_priority_rule
        rule = get_h7_h8_priority_rule(dt)
        self.assertIsNotNone(rule)
        self.assertEqual(rule["priority_slot"], 7)
        self.assertEqual(rule["priority_label"], "Ưu tiên đi H=7")


if __name__ == "__main__":
    unittest.main()
