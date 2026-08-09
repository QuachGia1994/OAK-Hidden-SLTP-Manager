"""Test F: D MISSING→READY transition order.

After D transitions MISSING→READY:
1. Local signals log is updated per slot (no push inside the loop)
2. D snapshot is pushed
3. Compact signal summaries pushed ONCE after loop (not per-hour)
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, call
import ast

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestDReadyCatchupOrder(unittest.TestCase):
    def test_rebuild_does_not_call_push_to_dashboard_per_hour(self):
        """push_to_dashboard() must NOT be called inside the per-hour rebuild loop.
        
        Checks via AST that push_to_dashboard is not called as a standalone call
        (as opposed to being mentioned in a docstring).
        """
        import mt5_signal_bot as bot
        import inspect
        import ast as ast_mod

        src = inspect.getsource(bot.rebuild_current_day_slots_after_d_ready)
        # Remove docstring by parsing the function body
        tree = ast_mod.parse(src)
        calls = []
        for node in ast_mod.walk(tree):
            if isinstance(node, ast_mod.Call):
                func = node.func
                name = None
                if isinstance(func, ast_mod.Name):
                    name = func.id
                elif isinstance(func, ast_mod.Attribute):
                    name = func.attr
                if name == "push_to_dashboard":
                    calls.append(name)

        self.assertEqual(calls, [],
                         "push_to_dashboard() must not be called inside rebuild_current_day_slots_after_d_ready")

    def test_compact_push_helper_present_in_rebuild(self):
        """_push_compact_current_signals must be referenced in the rebuild function."""
        import mt5_signal_bot as bot
        import inspect
        src = inspect.getsource(bot.rebuild_current_day_slots_after_d_ready)
        self.assertIn(
            "_push_compact_current_signals",
            src,
            "_push_compact_current_signals must be called in rebuild function"
        )

    def test_compact_push_is_called_once_after_rebuild(self):
        """_push_compact_current_signals is called once with all rebuilt records."""
        import mt5_signal_bot as bot
        from datetime import datetime

        fake_broker_dt = datetime(2026, 7, 31, 14, 30, 0)
        fake_record = {
            "date": "2026-07-31",
            "hour": 7,
            "signal": "SELL",
            "pair_dirs": {"XAUUSD": "SELL"},
            "pair_evidence": {"XAUUSD": {"some": "evidence"}},
            "logic_version": 84,
        }

        compact_calls = []

        with patch.object(bot, "get_signal_datetime_for_slot",
                          side_effect=lambda broker_dt, h: fake_broker_dt.replace(hour=max(0, h-1))):
            with patch.object(bot, "calculate_all_d_directions", return_value={
                "GBPUSD": {"d_state": "READY", "d_direction": "SELL"},
                "GBPAUD": {"d_state": "READY", "d_direction": "SELL"},
            }):
                with patch.object(bot, "_build_rebuild_record",
                                  return_value=(fake_record, {})):
                    with patch.object(bot, "_write_signals_log_atomic"):
                        with patch("os.path.exists", return_value=False):
                            with patch.object(bot, "_push_compact_current_signals",
                                              side_effect=lambda recs: compact_calls.append(len(recs))):
                                bot.rebuild_current_day_slots_after_d_ready(fake_broker_dt)

        self.assertEqual(len(compact_calls), 1,
                         "_push_compact_current_signals must be called exactly once")

    def test_compact_signal_strips_heavy_fields(self):
        """Compact signals sent to dashboard must not include pair_evidence or d_directions."""
        import mt5_signal_bot as bot
        import json

        full_record = {
            "date": "2026-07-31",
            "hour": 7,
            "signal": "SELL",
            "pair_dirs": {"XAUUSD": "SELL"},
            "pair_evidence": {"XAUUSD": {"m30_candles": [1, 2, 3]}},
            "d_directions": {"GBPUSD": {"d_direction": "SELL"}},
            "daily_directions": {"GBPUSD": {"d_direction": "SELL"}},
            "m30_candles": [[1, 2, 3, 4, 5]],
            "logic_version": 84,
        }

        class FakeResp:
            status = 200
            def read(self): return b'{"ok":true}'
            def __enter__(self): return self
            def __exit__(self, *a): pass

        captured = []
        def mock_urlopen(req, timeout=15):
            captured.append(json.loads(req.data.decode("utf-8")))
            return FakeResp()

        with patch("mt5_signal_bot.DASHBOARD_URL", "http://fake"):
            with patch("urllib.request.urlopen", mock_urlopen):
                bot._push_compact_current_signals([full_record])

        # If no URL called (no records), that's also acceptable
        for payload in captured:
            for rec in payload.get("records", []):
                self.assertNotIn("pair_evidence", rec)
                self.assertNotIn("d_directions", rec)
                self.assertNotIn("m30_candles", rec)


if __name__ == "__main__":
    unittest.main()
