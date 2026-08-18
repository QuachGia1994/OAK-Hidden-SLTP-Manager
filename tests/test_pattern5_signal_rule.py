import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1] / "robot-sltp-pro"
sys.path.insert(0, str(APP))

import pattern5_engine
import publish_pattern5_site
from pattern5_engine import ANCHOR_HOUR, BLOCKS, PATTERN_GROUP, PUBLIC_FEED_SCHEMA, WATCHLIST, build_h15_reference, build_signal_cell, build_table, classify5, flip_signal, look4, pattern_text, render_profile, render_profile_cached, render_profile_with_provider, should_reverse_signal, signal_from_base


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

    def test_sr_owns_both_four_candle_alternating_patterns(self):
        for directions in (["T", "G", "T", "G"], ["G", "T", "G", "T"]):
            pattern_id, _mirrored = classify5(directions)
            self.assertEqual(pattern_id, 5)
            self.assertEqual(PATTERN_GROUP[pattern_id], "Sr")
            self.assertEqual(pattern_text(pattern_id, directions), " ".join(directions))

    def test_sr_preserves_existing_pattern5_base_signal_behavior(self):
        self.assertEqual(signal_from_base(["T", "G", "T", "G"], "Sr"), "BUY")
        self.assertEqual(signal_from_base(["G", "T", "G", "T"], "Sr"), "SELL")

    def test_signal_cell_publishes_sr_for_alternating_pattern(self):
        directions = ["T", "G", "T", "G"]
        evidence = [
            {"index": index + 1, "time": 100 + index, "open": 1.0, "high": 1.2, "low": 0.8, "close": 1.1, "direction": direction}
            for index, direction in enumerate(reversed(directions))
        ]
        with patch("pattern5_engine.look4", return_value=(directions, evidence)), \
             patch("pattern5_engine.should_reverse_signal", return_value=False):
            cell, detail = build_signal_cell("EURUSD", date(2026, 8, 18), 15, 0)

        self.assertEqual(cell["group"], "Sr")
        self.assertEqual(cell["pattern"], "T G T G")
        self.assertEqual(cell["signal"], "BUY")
        self.assertIn("Sr", detail)

    def test_rendered_feed_carries_public_schema(self):
        provider = SimpleNamespace(provider_id="fixture", symbols=lambda: [], broker_day_offset=lambda _symbol: 0)
        payload = render_profile_with_provider("Fixture", provider, selected=["GBPUSD"])
        self.assertEqual(payload["schemaVersion"], PUBLIC_FEED_SCHEMA)

    def test_publisher_cli_can_explicitly_target_profile_and_force_recompute(self):
        args = publish_pattern5_site.parse_args(["--profile", "Vantage", "--force"])
        self.assertEqual(args.profile, "Vantage")
        self.assertTrue(args.force)

    def test_publisher_script_bootstraps_repo_import_path(self):
        script = APP / "publish_pattern5_site.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = subprocess.run(
                [sys.executable, str(script), "--help"],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--profile", completed.stdout)

    def test_pattern_classifier_still_uses_three_or_four_candles(self):
        self.assertEqual(classify5(["T", "T", "T", "G"])[0], 1)
        self.assertEqual(classify5(["G", "G", "T", "T"])[0], 3)
        self.assertEqual(classify5(["T", "G", "T", "G"])[0], 5)
        self.assertEqual(pattern_text(1, ["T", "T", "T", "G"]), "T T T")
        self.assertEqual(pattern_text(5, ["T", "G", "T", "G"]), "T G T G")

    def test_block_remap_preserves_existing_anchor_slots(self):
        self.assertEqual(BLOCKS, [3, 6, 9, 12, 15])
        self.assertEqual(ANCHOR_HOUR, {3: 4, 6: 8, 9: 12, 12: 16, 15: 20})

    def test_reverse_matrix_for_h6_h9_h12_h15(self):
        week = [date(2026, 8, 10 + offset) for offset in range(5)]
        self.assertEqual([should_reverse_signal(6, day) for day in week], [False, True, False, False, True])
        self.assertEqual([should_reverse_signal(9, day) for day in week], [False, False, False, True, True])
        self.assertEqual([should_reverse_signal(12, day) for day in week], [True, True, False, True, True])
        self.assertEqual([should_reverse_signal(15, day) for day in week], [True, True, True, True, True])

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

    def test_h15_reference_uses_previous_day_h15_cell_not_current_cell(self):
        days = [date(2026, 8, 17 + offset) for offset in range(5)]
        rows = {15: [
            {"group": "Sw", "pattern": "T T T"},
            {"group": "Bt", "pattern": "G G T"},
            "", "", "",
        ]}

        reference = build_h15_reference("EURUSD", days, rows)

        self.assertEqual(reference, {
            "date": "2026-08-17",
            "display": "17/08",
            "group": "Sw",
            "pattern": "T T T",
        })

    def test_pattern5_cache_is_scoped_to_requested_symbol_sequence(self):
        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(pattern5_engine, "CACHE_PATH", Path(temp_dir) / "pattern5_cache.json"), \
             patch("pattern5_engine.render_profile", side_effect=lambda profile, selected=None, week_start=None: {
                 "profile": profile,
                 "weekStart": week_start,
                 "blocks": [15],
                 "tables": [{"base": symbol} for symbol in (selected or WATCHLIST)],
             }) as render:
            gbp = render_profile_cached("Vantage", selected=["GBPUSD"], week_start="2026-08-17")
            eur = render_profile_cached("Vantage", selected=["EURUSD"], week_start="2026-08-17")
            eur_cached = render_profile_cached("Vantage", selected=["EURUSD"], week_start="2026-08-17")

        self.assertEqual([table["base"] for table in gbp["tables"]], ["GBPUSD"])
        self.assertEqual([table["base"] for table in eur["tables"]], ["EURUSD"])
        self.assertTrue(eur_cached["cacheHit"])
        self.assertEqual(render.call_count, 2)

    def test_render_profile_never_launches_closed_terminal(self):
        profiles = {"Vantage": {"path": "C:/Broker/terminal64.exe"}}
        attach_result = SimpleNamespace(
            ok=False,
            failure_code="TERMINAL_NOT_RUNNING",
            message="MT5 terminal is not running",
        )
        with patch.object(Path, "read_text", return_value=json.dumps(profiles)), \
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
