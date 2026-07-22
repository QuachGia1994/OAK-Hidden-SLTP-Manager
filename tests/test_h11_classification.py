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
        group, detail, *rest = evaluate_h11_classification(dt)
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
        group, detail, *rest = evaluate_h11_classification(dt)
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
        group, detail, *rest = evaluate_h11_classification(dt)
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
        group, detail, *rest = evaluate_h11_classification(dt)
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
        group, detail, *rest = evaluate_h11_classification(dt)
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
        group, detail, *rest = evaluate_h11_classification(dt)
        self.assertEqual(group, "SW")


class TestH11PriorityAndNoGoldRules(unittest.TestCase):
    """evaluate_h11_classification is called twice:
    1st call = yesterday (for priority slot)
    2nd call = today (for no-gold label)
    We use side_effect to control each call independently.
    """

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_tue_priority_from_mon_sw_today_sw_nogold(self, mock_eval):
        tue = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
        # yesterday Mon=SW → priority H=2 (sớm), today Tue=SW → no-gold=True (Tue needs SW)
        mock_eval.side_effect = [("SW", ""), ("SW", "")]
        rules = get_h11_priority_and_nogold_rules(tue)
        self.assertEqual(rules["priority_slot"], 2)
        self.assertIn("đi sớm H=2", rules["priority_label"])
        self.assertTrue(rules["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_tue_priority_from_mon_bt_today_bt_no_nogold(self, mock_eval):
        tue = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
        # yesterday Mon=BT → priority H=3, today Tue=BT → no-gold=False (Tue needs SW)
        mock_eval.side_effect = [("BT", ""), ("BT", "")]
        rules = get_h11_priority_and_nogold_rules(tue)
        self.assertEqual(rules["priority_slot"], 3)
        self.assertIn("đi trễ H=3", rules["priority_label"])
        self.assertFalse(rules["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_tue_bt_priority_today_sw_nogold(self, mock_eval):
        tue = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
        # yesterday Mon=BT → priority H=3, today Tue=SW → no-gold=True (Tue needs SW)
        mock_eval.side_effect = [("BT", ""), ("SW", "")]
        rules = get_h11_priority_and_nogold_rules(tue)
        self.assertEqual(rules["priority_slot"], 3)
        self.assertTrue(rules["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_wed_priority_from_tue_sw_today_sw_nogold(self, mock_eval):
        wed = datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc)
        # yesterday Tue=SW → priority H=2 (sớm), today Wed=SW → no-gold=True
        mock_eval.side_effect = [("SW", ""), ("SW", "")]
        rules = get_h11_priority_and_nogold_rules(wed)
        self.assertEqual(rules["priority_slot"], 2)
        self.assertIn("đi sớm H=2", rules["priority_label"])
        self.assertTrue(rules["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_wed_bt_priority_today_bt_no_nogold(self, mock_eval):
        wed = datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc)
        # yesterday Tue=BT → priority H=3, today Wed=BT → no-gold=False (Wed needs SW)
        mock_eval.side_effect = [("BT", ""), ("BT", "")]
        rules = get_h11_priority_and_nogold_rules(wed)
        self.assertEqual(rules["priority_slot"], 3)
        self.assertIn("đi trễ H=3", rules["priority_label"])
        self.assertFalse(rules["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_thu_priority_from_wed_sw_today_sw_nogold(self, mock_eval):
        thu = datetime(2026, 7, 23, 10, 0, tzinfo=timezone.utc)
        # yesterday Wed=SW → priority H=3, today Thu=SW → no-gold=True
        mock_eval.side_effect = [("SW", ""), ("SW", "")]
        rules = get_h11_priority_and_nogold_rules(thu)
        self.assertEqual(rules["priority_slot"], 3)
        self.assertIn("đi trễ H=3", rules["priority_label"])
        self.assertTrue(rules["has_nogold_label"])

    @patch("mt5_signal_bot.is_h2_special_calendar_weekday")
    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_thu_bt_normal_no_nogold(self, mock_eval, mock_special):
        thu = datetime(2026, 7, 23, 10, 0, tzinfo=timezone.utc)
        # yesterday Wed=BT → priority H=2, normal Thu, today Thu=BT → no-gold=False
        mock_eval.side_effect = [("BT", ""), ("BT", "")]
        mock_special.return_value = False
        rules = get_h11_priority_and_nogold_rules(thu)
        self.assertEqual(rules["priority_slot"], 2)
        self.assertIn("đi trễ H=2", rules["priority_label"])
        self.assertFalse(rules["has_nogold_label"])

    @patch("mt5_signal_bot.is_h2_special_calendar_weekday")
    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_thu_bt_special_nogold(self, mock_eval, mock_special):
        thu = datetime(2026, 7, 23, 10, 0, tzinfo=timezone.utc)
        # yesterday Wed=BT → priority H=2, special Thu, today Thu=BT → no-gold=True
        mock_eval.side_effect = [("BT", ""), ("BT", "")]
        mock_special.return_value = True
        rules = get_h11_priority_and_nogold_rules(thu)
        self.assertEqual(rules["priority_slot"], 2)
        self.assertTrue(rules["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_fri_today_bt_nogold(self, mock_eval):
        fri = datetime(2026, 7, 24, 10, 0, tzinfo=timezone.utc)
        # yesterday Thu=SW → priority H=3, today Fri=BT → no-gold=True
        mock_eval.side_effect = [("SW", ""), ("BT", "")]
        rules = get_h11_priority_and_nogold_rules(fri)
        self.assertEqual(rules["priority_slot"], 3)
        self.assertTrue(rules["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_fri_today_sw_no_nogold(self, mock_eval):
        fri = datetime(2026, 7, 24, 10, 0, tzinfo=timezone.utc)
        # yesterday Thu=BT → priority H=2, today Fri=SW → no-gold=False (Fri needs BT)
        mock_eval.side_effect = [("BT", ""), ("SW", "")]
        rules = get_h11_priority_and_nogold_rules(fri)
        self.assertEqual(rules["priority_slot"], 2)
        self.assertFalse(rules["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_mon_priority_from_fri_sw(self, mock_eval):
        mon = datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)
        # yesterday Fri=SW → priority H=3, today Mon=SW → no-gold=False (Mon needs BT)
        mock_eval.side_effect = [("SW", ""), ("SW", "")]
        rules = get_h11_priority_and_nogold_rules(mon)
        self.assertEqual(rules["priority_slot"], 3)
        self.assertFalse(rules["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_mon_bt_priority_today_bt_nogold(self, mock_eval):
        mon = datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)
        # yesterday Fri=BT → priority H=2, today Mon=BT → no-gold=True
        mock_eval.side_effect = [("BT", ""), ("BT", "")]
        rules = get_h11_priority_and_nogold_rules(mon)
        self.assertEqual(rules["priority_slot"], 2)
        self.assertTrue(rules["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_today_h11_group_in_result(self, mock_eval):
        tue = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
        mock_eval.side_effect = [("SW", ""), ("BT", "")]
        rules = get_h11_priority_and_nogold_rules(tue)
        self.assertEqual(rules["prev_h11_group"], "SW")
        self.assertEqual(rules["today_h11_group"], "BT")



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
