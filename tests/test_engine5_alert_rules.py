import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "robot-sltp-pro"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(APP))

import pattern5_engine as e


def cell(group: str):
    return {"group": group, "pattern": "T G T G", "signal": "BUY", "baseSignal": "SELL", "reversed": False, "evidence": []}


def rows(groups):
    result = {block: [""] * 5 for block in e.BLOCKS}
    for block, group in groups.items():
        result[block][0] = cell(group)
    return result


class Engine5AlertRuleTests(unittest.TestCase):
    def test_h3_asset_policy_is_explicit_and_unknown_is_unconfigured(self):
        self.assertEqual(e.h3_asset_policy("GBPUSD"), "reverse")
        self.assertEqual(e.h3_asset_policy("AUDUSD"), "reverse")
        self.assertEqual(e.h3_asset_policy("USDCAD"), "reverse")
        self.assertEqual(e.h3_asset_policy("USDJPY"), "normal")
        self.assertEqual(e.h3_asset_policy("XAUUSD"), "normal")
        self.assertIsNone(e.h3_asset_policy("EURUSD"))
        for symbol, code in (("GBPUSD", "h3_reverse_signal"), ("AUDUSD", "h3_reverse_signal"), ("USDCAD", "h3_reverse_signal"), ("USDJPY", "h3_normal_signal"), ("XAUUSD", "h3_normal_signal")):
            alerts = e.evaluate_alert_state(symbol, date(2026, 8, 19), rows({3: "Bt"}), 0, False, eligible_blocks={3})
            self.assertEqual([a["code"] for a in alerts], [code])

    def test_sr_entry_reminder_derives_block_hour_plus_minute_11(self):
        expected = {3: "03:11", 6: "06:11", 9: "09:11", 12: "12:11", 15: "15:11"}
        for block, entry_time in expected.items():
            groups = {candidate: "Bt" for candidate in e.BLOCKS}
            groups[block] = "Sr"
            alerts = e.evaluate_alert_state("GBPUSD", date(2026, 8, 19), rows(groups), 0, True)
            entry = [a for a in alerts if a["code"] == "sr_entry_at_11" and a["block"] == block]
            self.assertEqual([a["entryTime"] for a in entry], [entry_time])

    def test_h3_h6_consecutive_sr_stops_h9_and_later_not_second_sr(self):
        data = rows({3: "Sr", 6: "Sr", 9: "Bt", 12: "Sw", 15: "Bt"})
        alerts = e.evaluate_alert_state("GBPUSD", date(2026, 8, 19), data, 0, True)
        stop_blocks = [a["block"] for a in alerts if a["code"] == "consecutive_sr_stop"]
        entry_blocks = [a["block"] for a in alerts if a["code"] == "sr_entry_at_11"]
        self.assertEqual(entry_blocks, [3, 6])
        self.assertEqual(stop_blocks, [9, 12, 15])

    def test_non_consecutive_sr_does_not_latch_stop(self):
        data = rows({3: "Sr", 6: "Bt", 9: "Sr", 12: "Sw", 15: "Bt"})
        alerts = e.evaluate_alert_state("GBPUSD", date(2026, 8, 19), data, 0, True)
        self.assertFalse(any(a["code"] == "consecutive_sr_stop" for a in alerts))

    def test_missing_block_breaks_consecutive_sr_chain(self):
        data = rows({3: "Sr", 9: "Sr", 12: "Sw", 15: "Bt"})
        alerts = e.evaluate_alert_state("GBPUSD", date(2026, 8, 19), data, 0, True)
        self.assertEqual([a["block"] for a in alerts if a["code"] == "sr_entry_at_11"], [3, 9])
        self.assertFalse(any(a["code"] == "consecutive_sr_stop" for a in alerts))

    def test_h6_h9_consecutive_sr_stops_h12_onward(self):
        data = rows({3: "Bt", 6: "Sr", 9: "Sr", 12: "Bt", 15: "Bt"})
        alerts = e.evaluate_alert_state("GBPUSD", date(2026, 8, 19), data, 0, True)
        self.assertEqual([a["block"] for a in alerts if a["code"] == "consecutive_sr_stop"], [12, 15])

    def test_h9_h12_consecutive_sr_stops_independent_h15_operationally(self):
        data = rows({3: "Bt", 6: "Sw", 9: "Sr", 12: "Sr", 15: "Sr"})
        alerts = e.evaluate_alert_state("GBPUSD", date(2026, 8, 19), data, 0, True)
        h12 = [a for a in alerts if a["block"] == 12]
        h15 = [a for a in alerts if a["block"] == 15]
        self.assertTrue(any(a["code"] == "sr_entry_at_11" for a in h12))
        self.assertEqual(h15[0]["code"], "consecutive_sr_stop")
        self.assertFalse(any(a["code"] == "sr_entry_at_11" for a in h15))

    def test_daily_replay_resets_stop_latch(self):
        stopped = e.evaluate_alert_state("GBPUSD", date(2026, 8, 18), rows({3: "Sr", 6: "Sr", 9: "Bt"}), 0, False)
        fresh = e.evaluate_alert_state("GBPUSD", date(2026, 8, 19), rows({3: "Bt", 6: "Sw"}), 0, False)
        self.assertTrue(any(a["code"] == "consecutive_sr_stop" for a in stopped))
        self.assertFalse(any(a["code"] == "consecutive_sr_stop" for a in fresh))

    def test_h15_is_independent_and_has_no_inactive_alert(self):
        data = rows({3: "Bt", 6: "Sw", 9: "Bt", 12: "Bt", 15: "Bt"})
        alerts = e.evaluate_alert_state("GBPUSD", date(2026, 8, 19), data, 0, False)
        h15 = [a for a in alerts if a["block"] == 15]
        self.assertEqual(h15, [])
        self.assertNotEqual(data[15][0], "")

    def test_stop_precedence_still_overrides_independent_h15(self):
        data = rows({3: "Sr", 6: "Sr", 9: "Bt", 12: "Bt", 15: "Bt"})
        alerts = e.evaluate_alert_state("GBPUSD", date(2026, 8, 19), data, 0, False)
        h15 = [a for a in alerts if a["block"] == 15]
        self.assertEqual([a["code"] for a in h15], ["consecutive_sr_stop"])

    def test_h15_always_calculates_independently_of_h12_group(self):
        for h12_group in ("Sw", "Sr", "Bt"):
            calls = []
            def fake_cell(_symbol, _day, hour, _offset, provider=None):
                calls.append(hour)
                group = h12_group if hour == 12 else "Bt"
                return cell(group), group
            with patch("pattern5_engine.broker_day_offset", return_value=0), patch("pattern5_engine.build_signal_cell", side_effect=fake_cell):
                _days, out_rows, _detail = e.build_table("GBPUSD", date(2026, 8, 17), as_of=date(2026, 8, 17))
            self.assertIn(15, calls)
            self.assertTrue(bool(out_rows[15][0]))

    def test_future_eligible_blocks_emit_no_alerts(self):
        data = rows({3: "Sr", 6: "Sr", 9: "Bt", 12: "Bt"})
        alerts = e.evaluate_alert_state("GBPUSD", date(2026, 8, 19), data, 0, False, eligible_blocks={3, 6})
        self.assertFalse(any(a["block"] in {9, 12, 15} for a in alerts))

    def test_operational_state_marks_h15_independent_before_h15_hour(self):
        days = [date(2026, 8, 17) + e.timedelta(days=index) for index in range(5)]
        data = {block: [""] * 5 for block in e.BLOCKS}
        data[3][3] = cell("Bt")
        now = datetime(2026, 8, 20, 5, 22, tzinfo=e.VIETNAM_TZ)
        with patch("pattern5_engine.vietnam_now", return_value=now):
            h15_states, alerts = e.build_operational_state("GBPUSD", days, data)
        today_alerts = alerts.get("2026-08-20", [])
        self.assertEqual([item["code"] for item in today_alerts], ["h3_reverse_signal"])
        self.assertEqual(h15_states["2026-08-20"], {"active": True, "calculated": False, "activationReason": "independent"})
        self.assertFalse(any(item["block"] in {6, 9, 12, 15} for item in today_alerts))

    def test_current_day_precomputes_full_matrix_but_alerts_remain_time_gated(self):
        calls = []
        def fake_cell(_symbol, day_value, hour, _offset, provider=None):
            calls.append((day_value, hour))
            return cell("Sw"), "Sw"
        now = datetime(2026, 8, 19, 5, 43, tzinfo=e.VIETNAM_TZ)
        with patch("pattern5_engine.vietnam_now", return_value=now), patch("pattern5_engine.broker_day_offset", return_value=0), patch("pattern5_engine.build_signal_cell", side_effect=fake_cell):
            days, out_rows, _detail = e.build_table("GBPUSD", date(2026, 8, 17))
            h15_states, alerts = e.build_operational_state("GBPUSD", days, out_rows)
        for block in e.BLOCKS:
            self.assertIn((date(2026, 8, 19), block), calls)
            self.assertNotEqual(out_rows[block][2], "")
        self.assertTrue(h15_states["2026-08-19"]["active"])
        self.assertEqual([item["code"] for item in alerts["2026-08-19"]], ["h3_reverse_signal"])
        self.assertFalse(any(item["block"] in {6, 9, 12, 15} for item in alerts["2026-08-19"]))


if __name__ == "__main__":
    unittest.main()
