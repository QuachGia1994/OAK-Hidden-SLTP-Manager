# -*- coding: utf-8 -*-
"""Unit tests for H=11 XAUUSD H1 4-candle classification rules (SW/BT)."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from mt5_signal_bot import (
    evaluate_h11_classification,
    get_h11_priority_and_nogold_rules,
    get_h7_h8_priority_rule,
)


def _c(o, c):
    """Build a full OHLC candle dict from open and close. high/low have 5pt spread."""
    return {"open": o, "high": max(o, c) + 5.0, "low": min(o, c) - 5.0, "close": c}


class TestH11Classification(unittest.TestCase):
    @patch("mt5_signal_bot.get_candle_by_ts")
    def test_accepts_mt5_structured_rate_records(self, mock_candle):
        class StructuredRate:
            def __init__(self, **values):
                self.values = values

            def __getitem__(self, key):
                return self.values[key]

        mock_candle.side_effect = [
            StructuredRate(open=100, high=102, low=99, close=101),
            StructuredRate(open=101, high=103, low=100, close=102),
            StructuredRate(open=102, high=103, low=100, close=101),
            StructuredRate(open=101, high=102, low=99, close=100),
        ]

        group, _detail, candles = evaluate_h11_classification(
            datetime(2026, 7, 22, 11, 0, tzinfo=timezone.utc)
        )

        self.assertIn(group, ("SW", "BT"))
        self.assertEqual(len(candles), 4)

    @patch("mt5_signal_bot.get_candle_by_ts")
    def test_evaluate_h11_rule_1_sw(self, mock_candle):
        # Rule 1: H10 Tăng, H9 Giảm, H8 Tăng, H7 Giảm => SW
        candles = {
            10: _c(2000.0, 2010.0), # T
            9:  _c(2010.0, 2005.0), # G
            8:  _c(2005.0, 2012.0), # T
            7:  _c(2012.0, 2008.0), # G
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
            10: _c(2000.0, 2010.0), # T
            9:  _c(2010.0, 2005.0), # G
            8:  _c(2005.0, 2012.0), # T
            7:  _c(2008.0, 2012.0), # T
        }
        mock_candle.side_effect = lambda sym, tf, ts: candles.get(int(datetime.fromtimestamp(ts, tz=timezone.utc).hour))

        dt = datetime(2026, 7, 22, 17, 45, tzinfo=timezone.utc)
        group, detail, *rest = evaluate_h11_classification(dt)
        self.assertEqual(group, "BT")

    @patch("mt5_signal_bot.get_candle_by_ts")
    def test_evaluate_h11_rule_3_bt(self, mock_candle):
        # Rule 3: H10 Tăng, H9 Tăng, H8 Giảm => BT
        candles = {
            10: _c(2000.0, 2010.0), # T
            9:  _c(2005.0, 2010.0), # T
            8:  _c(2012.0, 2005.0), # G
            7:  _c(2008.0, 2012.0), # T
        }
        mock_candle.side_effect = lambda sym, tf, ts: candles.get(int(datetime.fromtimestamp(ts, tz=timezone.utc).hour))

        dt = datetime(2026, 7, 22, 17, 45, tzinfo=timezone.utc)
        group, detail, *rest = evaluate_h11_classification(dt)
        self.assertEqual(group, "BT")

    @patch("mt5_signal_bot.get_candle_by_ts")
    def test_evaluate_h11_rule_4_sw(self, mock_candle):
        # Rule 4: H10 Tăng, H9 Tăng, H8 Tăng => SW
        candles = {
            10: _c(2000.0, 2010.0), # T
            9:  _c(2005.0, 2010.0), # T
            8:  _c(2000.0, 2005.0), # T
            7:  _c(2008.0, 2012.0), # T
        }
        mock_candle.side_effect = lambda sym, tf, ts: candles.get(int(datetime.fromtimestamp(ts, tz=timezone.utc).hour))

        dt = datetime(2026, 7, 22, 17, 45, tzinfo=timezone.utc)
        group, detail, *rest = evaluate_h11_classification(dt)
        self.assertEqual(group, "SW")

    @patch("mt5_signal_bot.get_candle_by_ts")
    def test_evaluate_h11_rule_5_sw(self, mock_candle):
        # Rule 5: H10 Tăng, H9 Giảm, H8 Giảm => SW
        candles = {
            10: _c(2000.0, 2010.0), # T
            9:  _c(2010.0, 2005.0), # G
            8:  _c(2008.0, 2002.0), # G
            7:  _c(2008.0, 2012.0), # T
        }
        mock_candle.side_effect = lambda sym, tf, ts: candles.get(int(datetime.fromtimestamp(ts, tz=timezone.utc).hour))

        dt = datetime(2026, 7, 22, 17, 45, tzinfo=timezone.utc)
        group, detail, *rest = evaluate_h11_classification(dt)
        self.assertEqual(group, "SW")

    @patch("mt5_signal_bot.get_candle_by_ts")
    def test_evaluate_h11_inverted_rule_6_sw(self, mock_candle):
        # Inverted Rule 6 (of 1): H10 Giảm, H9 Tăng, H8 Giảm, H7 Tăng => SW
        candles = {
            10: _c(2010.0, 2000.0), # G
            9:  _c(2005.0, 2010.0), # T
            8:  _c(2012.0, 2005.0), # G
            7:  _c(2008.0, 2012.0), # T
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
        self.assertIn("Ưu tiên đi H=2", rules["priority_label"])
        self.assertTrue(rules["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_tue_priority_from_mon_bt_today_bt_no_nogold(self, mock_eval):
        tue = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
        # yesterday Mon=BT → priority H=3, today Tue=BT → no-gold=False (Tue needs SW)
        mock_eval.side_effect = [("BT", ""), ("BT", "")]
        rules = get_h11_priority_and_nogold_rules(tue)
        self.assertEqual(rules["priority_slot"], 3)
        self.assertIn("Ưu tiên đi H=3", rules["priority_label"])
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
        self.assertIn("Ưu tiên đi H=2", rules["priority_label"])
        self.assertTrue(rules["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_wed_bt_priority_today_bt_no_nogold(self, mock_eval):
        wed = datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc)
        # yesterday Tue=BT → priority H=3, today Wed=BT → no-gold=False (Wed needs SW)
        mock_eval.side_effect = [("BT", ""), ("BT", "")]
        rules = get_h11_priority_and_nogold_rules(wed)
        self.assertEqual(rules["priority_slot"], 3)
        self.assertIn("Ưu tiên đi H=3", rules["priority_label"])
        self.assertFalse(rules["has_nogold_label"])

    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_thu_priority_from_wed_sw_today_sw_nogold(self, mock_eval):
        thu = datetime(2026, 7, 23, 10, 0, tzinfo=timezone.utc)
        # yesterday Wed=SW → priority H=3, today Thu=SW → no-gold=True
        mock_eval.side_effect = [("SW", ""), ("SW", ""), ("SW", "")]
        rules = get_h11_priority_and_nogold_rules(thu)
        self.assertEqual(rules["priority_slot"], 3)
        self.assertIn("Ưu tiên đi H=3", rules["priority_label"])
        self.assertTrue(rules["has_nogold_label"])

    @patch("mt5_signal_bot.is_special_day")
    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_thu_bt_normal_no_nogold(self, mock_eval, mock_special):
        thu = datetime(2026, 7, 23, 10, 0, tzinfo=timezone.utc)
        # yesterday Wed=BT, today Thu=BT, last Fri=BT
        mock_eval.side_effect = [("BT", ""), ("BT", ""), ("BT", "")]
        mock_special.return_value = False
        rules = get_h11_priority_and_nogold_rules(thu)
        self.assertEqual(rules["priority_slot"], 2)
        self.assertIn("Ưu tiên đi H=2", rules["priority_label"])
        self.assertFalse(rules["has_nogold_label"])

    @patch("mt5_signal_bot.is_special_day")
    @patch("mt5_signal_bot.evaluate_h11_classification")
    def test_thu_bt_special_nogold(self, mock_eval, mock_special):
        thu = datetime(2026, 7, 23, 10, 0, tzinfo=timezone.utc)
        # yesterday Wed=BT, today Thu=BT, last Fri=BT
        mock_eval.side_effect = [("BT", ""), ("BT", ""), ("BT", "")]
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
    """Priority rule disabled (H=7→H=6 transition). Always returns None."""

    def test_priority_rule_returns_none(self):
        from mt5_signal_bot import get_h7_h8_priority_rule
        dt = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
        rule = get_h7_h8_priority_rule(dt)
        self.assertIsNone(rule)

    def test_priority_rule_none_with_h9_check(self):
        from mt5_signal_bot import get_h7_h9_priority_rule
        dt = datetime(2026, 7, 22, 8, 45, tzinfo=timezone.utc)
        rule = get_h7_h9_priority_rule(dt)
        self.assertIsNone(rule)


if __name__ == "__main__":
    unittest.main()
