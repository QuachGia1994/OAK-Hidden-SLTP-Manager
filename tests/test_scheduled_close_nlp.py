import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from domain import copy_trade_manager
from domain.copy_trade_manager import CopyTradeManager
from domain.json_io import load_json


class ScheduledCloseNlpTests(unittest.TestCase):
    def make_manager(self, scheduled_close_file, close_calls=None):
        manager = object.__new__(CopyTradeManager)
        manager.config = {"profile_name": "Vantage", "magic": 0, "symbol": "XAUUSD,GBPUSD,EURUSD"}
        manager.notify_messages = []
        manager.notify = manager.notify_messages.append
        manager.scheduled_close_file = scheduled_close_file
        manager._scheduled_close = []
        manager._get_profile_names = lambda: {"vantage"}
        if close_calls is None:
            manager._execute_close_all = lambda *args, **kwargs: self.fail(f"closed immediately: {args}")
        else:
            manager._execute_close_all = lambda *args, **kwargs: close_calls.append(args)
        return manager

    def test_close_all_with_time_is_scheduled_not_immediate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/scheduled_close.json"
            manager = self.make_manager(path)

            manager._handle_telegram_text("Đóng tất cả lúc 21h49")

            scheduled = load_json(path, [])
            self.assertEqual(len(scheduled), 1)
            self.assertEqual(scheduled[0]["time"], "21:49:00")
            self.assertEqual(scheduled[0]["filter"], "all")
            self.assertEqual(scheduled[0]["sym"], "")
            self.assertEqual(scheduled[0]["ticket"], "")

    def test_close_gold_with_time_targets_xauusd_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/scheduled_close.json"
            manager = self.make_manager(path)

            manager._handle_telegram_text("Đóng lệnh Xauusd (Vàng) lúc 21h49")

            scheduled = load_json(path, [])
            self.assertEqual(len(scheduled), 1)
            self.assertEqual(scheduled[0]["time"], "21:49:00")
            self.assertEqual(scheduled[0]["sym"], "XAUUSD")
            self.assertEqual(scheduled[0]["ticket"], "")
            self.assertEqual(scheduled[0].get("tz"), "Asia/Ho_Chi_Minh")

    def test_close_broker_suffix_symbols_preserved(self):
        cases = [
            ("Đóng lệnh XAUUSD+ lúc 21h49", "XAUUSD+"),
            ("Đóng lệnh XAUUSDm lúc 21h49", "XAUUSDM"),
            ("Đóng lệnh XAUUSD.a lúc 21h49", "XAUUSD.A"),
            ("Đóng lệnh EURUSDm lúc 21h49", "EURUSDM"),
            ("Đóng lệnh GOLDm lúc 21h49", "GOLDM"),
        ]
        for text, expected_sym in cases:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                path = f"{tmp}/scheduled_close.json"
                manager = self.make_manager(path)

                manager._handle_telegram_text(text)

                scheduled = load_json(path, [])
                self.assertEqual(len(scheduled), 1)
                self.assertEqual(scheduled[0]["sym"], expected_sym)
                self.assertEqual(scheduled[0]["ticket"], "")

    def test_close_gold_without_time_closes_xauusd_plus_immediately(self):
        close_calls = []
        manager = self.make_manager("unused.json", close_calls)

        manager._handle_telegram_text("Đóng lệnh XAUUSD+ ngay bây giờ")

        self.assertEqual(close_calls, [("all", "XAUUSD+", "")])

    def test_close_ticket_with_time_targets_ticket_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/scheduled_close.json"
            manager = self.make_manager(path)

            manager._handle_telegram_text("Đóng lệnh 123456789 lúc 21h49")

            scheduled = load_json(path, [])
            self.assertEqual(len(scheduled), 1)
            self.assertEqual(scheduled[0]["time"], "21:49:00")
            self.assertEqual(scheduled[0]["sym"], "")
            self.assertEqual(scheduled[0]["ticket"], "123456789")

    def test_close_all_without_time_closes_immediately(self):
        close_calls = []
        manager = self.make_manager("unused.json", close_calls)

        manager._handle_telegram_text("Đóng tất cả ngay bây giờ")

        self.assertEqual(close_calls, [("all", "", "")])

    def test_close_bare_xauusd_without_time_closes_immediately(self):
        close_calls = []
        manager = self.make_manager("unused.json", close_calls)

        manager._handle_telegram_text("Đóng lệnh XAUUSD ngay bây giờ")

        self.assertEqual(close_calls, [("all", "XAUUSD", "")])

    def test_close_ticket_without_time_closes_ticket_immediately(self):
        close_calls = []
        manager = self.make_manager("unused.json", close_calls)

        manager._handle_telegram_text("Đóng ticket 123456789 ngay bây giờ")

        self.assertEqual(close_calls, [("all", "", "123456789")])

    def test_ticket_close_executor_only_closes_matching_ticket(self):
        manager = self.make_manager("unused.json")
        closed_tickets = []
        positions = [
            SimpleNamespace(ticket=111, symbol="XAUUSD", magic=0, profit=10),
            SimpleNamespace(ticket=222, symbol="GBPUSD", magic=0, profit=-5),
        ]
        manager._execute_close_all = CopyTradeManager._execute_close_all.__get__(manager, CopyTradeManager)
        manager._direct_close = lambda pos: closed_tickets.append(pos.ticket) or True

        with patch.object(copy_trade_manager.mt5, "positions_get", return_value=positions):
            manager._execute_close_all("all", "", "222")

        self.assertEqual(closed_tickets, [222])


if __name__ == "__main__":
    unittest.main()
