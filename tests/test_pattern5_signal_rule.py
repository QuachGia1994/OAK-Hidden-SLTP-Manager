import json
import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import mock_open, patch

APP = Path(__file__).resolve().parents[1] / "robot-sltp-pro"
sys.path.insert(0, str(APP))

from pattern5_engine import WATCHLIST, build_h14_reference, build_table, classify5, flip_signal, look4, pattern_text, render_profile, should_reverse_signal, signal_from_base


class Pattern5SignalRuleTests(unittest.TestCase):
    def test_watchlist_keeps_only_gbpusd_and_eurusd(self):
        self.assertEqual(WATCHLIST, ["GBPUSD", "EURUSD"])

    def test_look4_warms_history_and_retries_once(self):
        rates = [
            {"time": 100, "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1},
            {"time": 200, "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.0},
            {"time": 300, "open": 1.0, "high": 1.3, "low": 0.9, "close": 1.2},
            {"time": 400, "open": 1.2, "high": 1.3, "low": 1.0, "close": 1.1},
        ]
        with patch("pattern5_engine.mt5.copy_rates_range", side_effect=[None, rates]), \
             patch("pattern5_engine.mt5.symbol_select") as select_symbol, \
             patch("pattern5_engine.mt5.copy_rates_from_pos") as warm_history, \
             patch("pattern5_engine.time.sleep"):
            directions, evidence = look4("EURUSD", 500)
        self.assertEqual(directions, ["G", "T", "G", "T"])
        self.assertEqual(len(evidence), 4)
        select_symbol.assert_called_once_with("EURUSD", True)
        warm_history.assert_called_once()

    def test_sw_reverses_base_candle_four(self):
        self.assertEqual(signal_from_base(["T", "T", "T", "T"], "Sw"), "SELL")
        self.assertEqual(signal_from_base(["T", "T", "T", "G"], "Sw"), "BUY")

    def test_bt_follows_base_candle_four(self):
        self.assertEqual(signal_from_base(["G", "G", "T", "T"], "Bt"), "BUY")
        self.assertEqual(signal_from_base(["G", "G", "T", "G"], "Bt"), "SELL")

    def test_pattern_classifier_still_uses_three_or_four_candles(self):
        self.assertEqual(classify5(["T", "T", "T", "G"])[0], 1)
        self.assertEqual(classify5(["G", "G", "T", "T"])[0], 3)
        self.assertEqual(classify5(["T", "G", "T", "G"])[0], 5)
        self.assertEqual(pattern_text(1, ["T", "T", "T", "G"]), "T T T")
        self.assertEqual(pattern_text(5, ["T", "G", "T", "G"]), "T G T G")

    def test_reverse_matrix_for_h7_h9_h12_h14(self):
        week = [date(2026, 8, 10 + offset) for offset in range(5)]
        self.assertEqual([should_reverse_signal(7, day) for day in week], [False, True, False, False, True])
        self.assertEqual([should_reverse_signal(9, day) for day in week], [False, False, False, True, True])
        self.assertEqual([should_reverse_signal(12, day) for day in week], [True, True, False, True, True])
        self.assertEqual([should_reverse_signal(14, day) for day in week], [True, True, True, True, True])

    def test_h3_monday_and_thursday_month_exception(self):
        self.assertTrue(should_reverse_signal(3, date(2026, 8, 10)))
        self.assertTrue(should_reverse_signal(3, date(2026, 9, 3)))
        self.assertFalse(should_reverse_signal(3, date(2026, 7, 2)))
        self.assertFalse(should_reverse_signal(3, date(2026, 7, 9)))
        self.assertFalse(should_reverse_signal(3, date(2026, 10, 1)))
        self.assertFalse(should_reverse_signal(3, date(2026, 10, 8)))

    def test_h3_friday_recalculates_from_first_friday_each_month(self):
        self.assertTrue(should_reverse_signal(3, date(2026, 7, 3)))
        self.assertTrue(should_reverse_signal(3, date(2026, 7, 24)))
        self.assertTrue(should_reverse_signal(3, date(2026, 8, 28)))
        self.assertFalse(should_reverse_signal(3, date(2026, 5, 1)))
        self.assertFalse(should_reverse_signal(3, date(2026, 5, 29)))

    def test_current_week_does_not_calculate_future_days(self):
        evidence = [
            {"index": 1, "time": 100, "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1, "direction": "T"},
            {"index": 2, "time": 200, "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.0, "direction": "G"},
            {"index": 3, "time": 300, "open": 1.0, "high": 1.3, "low": 0.9, "close": 1.2, "direction": "T"},
            {"index": 4, "time": 400, "open": 1.2, "high": 1.3, "low": 1.0, "close": 1.1, "direction": "G"},
        ]
        lookback = (["G", "T", "G", "T"], evidence)
        with patch("pattern5_engine.broker_day_offset", return_value=0), \
             patch("pattern5_engine.look4", return_value=lookback) as mocked_look4:
            _days, rows, detail = build_table("GBPUSD", date(2026, 8, 17), as_of=date(2026, 8, 17))

        self.assertEqual(mocked_look4.call_count, 5)
        for block in rows:
            self.assertNotEqual(rows[block][0], "")
            self.assertEqual(rows[block][1:], ["", "", "", ""])
            self.assertEqual(detail[block][1:], ["", "", "", ""])

    def test_h14_reference_uses_previous_day_h14_cell_not_current_cell(self):
        days = [date(2026, 8, 17 + offset) for offset in range(5)]
        rows = {14: [
            {"group": "Sw", "pattern": "T T T"},
            {"group": "Bt", "pattern": "G G T"},
            "", "", "",
        ]}

        reference = build_h14_reference("EURUSD", days, rows)

        self.assertEqual(reference, {
            "date": "2026-08-17",
            "display": "17/08",
            "group": "Sw",
            "pattern": "T T T",
        })

    def test_render_profile_never_launches_closed_terminal(self):
        profiles = {"Vantage": {"path": "C:/Broker/terminal64.exe"}}
        attach_result = SimpleNamespace(
            ok=False,
            failure_code="TERMINAL_NOT_RUNNING",
            message="MT5 terminal is not running",
        )
        with patch("builtins.open", mock_open(read_data=json.dumps(profiles))), \
             patch("pattern5_engine.ensure_mt5_profile_connected", return_value=attach_result) as ensure_connected, \
             patch("pattern5_engine.render_profile_with_provider") as render_with_provider, \
             patch("pattern5_engine.mt5.shutdown") as shutdown:
            with self.assertRaisesRegex(RuntimeError, "TERMINAL_NOT_RUNNING"):
                render_profile("Vantage")

        self.assertFalse(ensure_connected.call_args.kwargs["allow_process_start"])
        render_with_provider.assert_not_called()
        shutdown.assert_not_called()

    def test_reverse_flips_final_signal_only_once(self):
        self.assertEqual(flip_signal("BUY"), "SELL")
        self.assertEqual(flip_signal("SELL"), "BUY")


if __name__ == "__main__":
    unittest.main()
