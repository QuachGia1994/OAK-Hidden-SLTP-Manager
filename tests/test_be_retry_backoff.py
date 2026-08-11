import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from domain.monitor_worker import MonitorWorker


class FakeMT5:
    POSITION_TYPE_BUY = 0
    TRADE_ACTION_SLTP = 6
    TRADE_RETCODE_DONE = 10009

    def __init__(self, retcode, terminal_path=""):
        self.retcode = retcode
        self.orders = 0
        self.login = 1001
        self.server = "Broker-Demo"
        self.terminal_path = terminal_path

    def terminal_info(self):
        return SimpleNamespace(path=self.terminal_path)

    def account_info(self):
        return SimpleNamespace(login=self.login, server=self.server)

    def symbol_info(self, _symbol):
        return SimpleNamespace(digits=2, point=0.01, trade_tick_size=0.01, trade_stops_level=0, trade_freeze_level=0)

    def symbol_info_tick(self, _symbol):
        return SimpleNamespace(bid=120.0, ask=120.1)

    def order_send(self, _request):
        self.orders += 1
        return SimpleNamespace(retcode=self.retcode)

    def positions_get(self, **_kwargs):
        return []


class BERetryTests(unittest.TestCase):
    def test_market_closed_is_deferred_without_spam(self):
        with TemporaryDirectory() as raw_dir:
            terminal = Path(raw_dir) / "terminal64.exe"
            terminal.write_bytes(b"fake")
            fake = FakeMT5(10018, str(terminal))
            logs = []
            worker = MonitorWorker({"visible_sltp": True, "profile_name": "Vantage", "path": str(terminal), "login_id": 1001, "server": "Broker-Demo"}, logs.append, __import__("threading").Event())
            position = SimpleNamespace(ticket=7, symbol="XAUUSD", type=0, sl=0.0, price_open=100.0, tp=0.0, price_current=120.0)
            with patch("domain.monitor_worker.mt5", fake), patch("domain.monitor_worker.time.time", return_value=1000.0):
                self.assertFalse(worker.move_sl_to_entry(position))
                self.assertFalse(worker.move_sl_to_entry(position))
            self.assertEqual(fake.orders, 1)
            self.assertEqual(len(logs), 1)
            self.assertIn("thị trường đóng cửa", logs[0])


if __name__ == "__main__":
    unittest.main()
