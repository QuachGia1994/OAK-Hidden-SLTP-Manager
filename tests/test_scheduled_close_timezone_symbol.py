# -*- coding: utf-8 -*-
"""Scheduled Telegram close — Asia/Ho_Chi_Minh + exact symbol + fail-closed jobs."""
from __future__ import annotations

import tempfile
import time
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from domain import copy_trade_manager
from domain.copy_trade_manager import (
    SCHEDULED_CLOSE_TZ,
    CopyTradeManager,
    _extract_close_symbol,
    _scheduled_close_now,
    _scheduled_close_parse_local,
    _scheduled_close_resolve_target,
)
from domain.json_io import load_json


class ExtractSymbolTests(unittest.TestCase):
    def test_matrix_preserves_broker_tokens(self):
        cases = {
            "Close EURUSD 07:00": "EURUSD",
            "Đóng EURUSDm 07:00": "EURUSDM",
            "Đóng EURUSDM 07:00": "EURUSDM",
            "Close XAUUSD 07:00": "XAUUSD",
            "Đóng XAUUSDm 07:00": "XAUUSDM",
            "Đóng XAUUSDM 07:00": "XAUUSDM",
            "Đóng XAUUSD.a 07:00": "XAUUSD.A",
            "Đóng XAUUSD+ 07:00": "XAUUSD+",
            "Đóng GOLDm 07:00": "GOLDM",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(_extract_close_symbol(text), expected)

    def test_unknown_or_missing_returns_empty(self):
        self.assertEqual(_extract_close_symbol("Đóng tất cả lúc 07:00"), "")
        self.assertEqual(_extract_close_symbol("hello world"), "")


class TimezoneTests(unittest.TestCase):
    def test_zone_is_iana_not_fixed_offset(self):
        self.assertIsInstance(SCHEDULED_CLOSE_TZ, ZoneInfo)
        self.assertEqual(str(SCHEDULED_CLOSE_TZ), "Asia/Ho_Chi_Minh")

    def test_resolve_0700_is_vietnam_civil_time(self):
        now = datetime(2026, 8, 13, 6, 0, 0, tzinfo=SCHEDULED_CLOSE_TZ)
        target = _scheduled_close_resolve_target("07:00", now=now)
        self.assertEqual(target.tzinfo, SCHEDULED_CLOSE_TZ)
        self.assertEqual(target.hour, 7)
        self.assertEqual(target.minute, 0)
        self.assertEqual(target.date().isoformat(), "2026-08-13")

    def test_past_time_rolls_next_day(self):
        now = datetime(2026, 8, 13, 9, 0, 0, tzinfo=SCHEDULED_CLOSE_TZ)
        target = _scheduled_close_resolve_target("07:00", now=now)
        self.assertEqual(target.date().isoformat(), "2026-08-14")

    def test_friday_evening_skips_weekend(self):
        # Friday 2026-08-14 23:00 → next slot Monday if 07:00 Saturday would be used
        now = datetime(2026, 8, 14, 23, 30, 0, tzinfo=SCHEDULED_CLOSE_TZ)
        target = _scheduled_close_resolve_target("07:00", now=now)
        # 15=Sat, 16=Sun skipped → Monday 17
        self.assertEqual(target.weekday(), 0)
        self.assertEqual(target.date().isoformat(), "2026-08-17")

    def test_parse_local_attaches_vn_zone(self):
        dt = _scheduled_close_parse_local("2026-08-13", "23:59:00")
        self.assertEqual(dt.tzinfo, SCHEDULED_CLOSE_TZ)
        self.assertEqual(dt.hour, 23)
        self.assertEqual(dt.minute, 59)

    def test_dst_zoneinfo_structural_not_fixed_offset(self):
        """Prove architecture uses IANA zones (NY observes DST); VN zone is separate."""
        ny = ZoneInfo("America/New_York")
        winter = datetime(2026, 1, 15, 12, 0, tzinfo=ny)
        summer = datetime(2026, 7, 15, 12, 0, tzinfo=ny)
        self.assertNotEqual(winter.utcoffset(), summer.utcoffset())
        vn = datetime(2026, 1, 15, 12, 0, tzinfo=SCHEDULED_CLOSE_TZ)
        vn2 = datetime(2026, 7, 15, 12, 0, tzinfo=SCHEDULED_CLOSE_TZ)
        self.assertEqual(vn.utcoffset(), vn2.utcoffset())


class ExactCloseMatchTests(unittest.TestCase):
    def _manager(self):
        m = object.__new__(CopyTradeManager)
        m.config = {"profile_name": "Vantage", "magic": 0, "symbol": ""}
        m.notify = lambda *_a, **_k: None
        closed = []
        m._direct_close = lambda pos: closed.append(pos.symbol) or True
        m._closed = closed
        return m

    def test_xauusd_does_not_match_xauusdm(self):
        m = self._manager()
        positions = [
            SimpleNamespace(ticket=1, symbol="XAUUSDm", magic=0, profit=1),
            SimpleNamespace(ticket=2, symbol="XAUUSD", magic=0, profit=1),
        ]
        with patch.object(copy_trade_manager.mt5, "positions_get", return_value=positions):
            outcome = CopyTradeManager._execute_close_all(m, "all", "XAUUSD", "")
        self.assertEqual(outcome, "done")
        self.assertEqual(m._closed, ["XAUUSD"])

    def test_xauusdm_does_not_match_xauusd(self):
        m = self._manager()
        positions = [
            SimpleNamespace(ticket=1, symbol="XAUUSD", magic=0, profit=1),
            SimpleNamespace(ticket=2, symbol="XAUUSDm", magic=0, profit=1),
        ]
        with patch.object(copy_trade_manager.mt5, "positions_get", return_value=positions):
            outcome = CopyTradeManager._execute_close_all(m, "all", "XAUUSDm", "")
        self.assertEqual(outcome, "done")
        self.assertEqual(m._closed, ["XAUUSDm"])

    def test_unknown_symbol_closes_zero_not_all(self):
        m = self._manager()
        positions = [
            SimpleNamespace(ticket=1, symbol="EURUSD", magic=0, profit=1),
            SimpleNamespace(ticket=2, symbol="XAUUSD", magic=0, profit=1),
        ]
        with patch.object(copy_trade_manager.mt5, "positions_get", return_value=positions):
            outcome = CopyTradeManager._execute_close_all(m, "all", "NOSUCH", "")
        self.assertEqual(outcome, "empty")
        self.assertEqual(m._closed, [])


class ScheduledCloseReliabilityTests(unittest.TestCase):
    def make_manager(self, path):
        m = object.__new__(CopyTradeManager)
        m.config = {"profile_name": "Vantage", "magic": 0, "symbol": ""}
        m.notify_messages = []
        m.notify = m.notify_messages.append
        m.scheduled_close_file = path
        m._scheduled_close = []
        m.scheduled_trades = []
        m.scheduled_file = ""
        m._with_scheduled_close_file_lock = CopyTradeManager._with_scheduled_close_file_lock.__get__(
            m, CopyTradeManager
        )
        m._remove_scheduled_closes = CopyTradeManager._remove_scheduled_closes.__get__(
            m, CopyTradeManager
        )
        m._next_scheduled_close_id = CopyTradeManager._next_scheduled_close_id.__get__(
            m, CopyTradeManager
        )
        return m

    def test_execution_error_keeps_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/scheduled_close.json"
            m = self.make_manager(path)
            past = _scheduled_close_now() - timedelta(minutes=1)
            job = {
                "id": 42,
                "time": past.strftime("%H:%M:%S"),
                "date": past.strftime("%Y-%m-%d"),
                "tz": "Asia/Ho_Chi_Minh",
                "filter": "all",
                "sym": "XAUUSD+",
                "ticket": "",
                "attempts": 0,
            }
            m._scheduled_close = [job]
            from domain.json_io import save_json

            save_json(path, [job])

            def boom(*_a, **_k):
                return "error"

            m._execute_close_all = boom
            CopyTradeManager._check_scheduled_trades(m)
            remaining = load_json(path, [])
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0]["id"], 42)
            self.assertGreaterEqual(int(remaining[0].get("attempts") or 0), 1)

    def test_empty_outcome_removes_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/scheduled_close.json"
            m = self.make_manager(path)
            past = _scheduled_close_now() - timedelta(minutes=1)
            job = {
                "id": 7,
                "time": past.strftime("%H:%M:%S"),
                "date": past.strftime("%Y-%m-%d"),
                "tz": "Asia/Ho_Chi_Minh",
                "filter": "all",
                "sym": "XAUUSD",
                "ticket": "",
                "attempts": 0,
            }
            from domain.json_io import save_json

            save_json(path, [job])
            m._scheduled_close = [job]
            m._execute_close_all = lambda *a, **k: "empty"
            CopyTradeManager._check_scheduled_trades(m)
            remaining = load_json(path, [])
            self.assertEqual(remaining, [])


if __name__ == "__main__":
    unittest.main()
