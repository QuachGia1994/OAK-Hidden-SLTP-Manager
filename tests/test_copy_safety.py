# -*- coding: utf-8 -*-
"""Real CopyTradeManager safety guardrail tests (production methods)."""
import os
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

# Ensure project root on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _make_manager(**overrides):
    from domain.copy_trade_manager import CopyTradeManager

    config = {
        "profile_name": "TestProfile",
        "copy_role": "slave",
        "copy_channel": "default",
        "copy_lot_mode": "fixed",
        "copy_lot_value": "0.01",
        "copy_max_one": False,
        "copy_max_daily_trades": 5,
        "copy_max_lot_per_trade": 2.0,
        "copy_max_exposure": 10.0,
        "copy_kill_switch": False,
        "copy_stale_threshold": 60,
        "path": "",
    }
    config.update(overrides)
    notify = MagicMock()
    mgr = CopyTradeManager(config, notify)
    return mgr, notify


class TestCopySafetyReal(unittest.TestCase):
    def test_kill_switch_blocks_via_test_safety_rules(self):
        mgr, _ = _make_manager(copy_kill_switch=True)
        result = mgr.test_safety_rules(symbol="EURUSD", lot=0.1, type="BUY")
        self.assertFalse(result["allowed"])
        self.assertIn("Kill switch", result["reason"])

    def test_kill_switch_off_allows_when_limits_ok(self):
        mgr, _ = _make_manager(copy_kill_switch=False)
        with patch("domain.copy_trade_manager.mt5") as mock_mt5:
            mock_mt5.terminal_info.return_value = None
            result = mgr.test_safety_rules(symbol="EURUSD", lot=0.1, type="BUY")
        self.assertTrue(result["allowed"], result)

    def test_max_daily_trades_blocks(self):
        mgr, _ = _make_manager(copy_max_daily_trades=3, copy_kill_switch=False)
        mgr._daily_trade_date = date.today()
        mgr._daily_trade_count = 3
        with patch("domain.copy_trade_manager.mt5") as mock_mt5:
            mock_mt5.terminal_info.return_value = None
            result = mgr.test_safety_rules(symbol="XAUUSD", lot=0.01, type="BUY")
        self.assertFalse(result["allowed"])
        self.assertIn("Daily limit", result["reason"])

    def test_max_lot_flagged_in_test_safety_rules(self):
        mgr, _ = _make_manager(copy_max_lot_per_trade=1.0, copy_kill_switch=False)
        with patch("domain.copy_trade_manager.mt5") as mock_mt5:
            mock_mt5.terminal_info.return_value = None
            result = mgr.test_safety_rules(symbol="EURUSD", lot=5.0, type="BUY")
        self.assertFalse(result["allowed"])
        self.assertIn("exceeds max per trade", result["reason"])

    def test_open_copy_trade_respects_kill_switch(self):
        mgr, notify = _make_manager(copy_kill_switch=True)
        m_pos = {"symbol": "EURUSD", "type": 0, "volume": 0.1, "price_open": 1.1}
        with patch.object(mgr, "_find_matching_symbol", return_value="EURUSD"):
            with patch("domain.copy_trade_manager.profile_session_validation_enabled", return_value=False):
                mgr._open_copy_trade(12345, m_pos)
        notify.assert_called()
        self.assertTrue(any("Kill switch" in str(c) for c in notify.call_args_list))

    def test_open_copy_trade_caps_lot(self):
        mgr, notify = _make_manager(
            copy_kill_switch=False,
            copy_max_lot_per_trade=0.5,
            copy_max_daily_trades=20,
            copy_max_exposure=100.0,
        )
        m_pos = {"symbol": "EURUSD", "type": 0, "volume": 2.0, "price_open": 1.1, "sl": 0, "tp": 0}
        with patch.object(mgr, "_find_matching_symbol", return_value="EURUSD"), \
             patch.object(mgr, "_calculate_lot", return_value=2.0), \
             patch("domain.copy_trade_manager.profile_session_validation_enabled", return_value=False), \
             patch("domain.copy_trade_manager.mt5") as mock_mt5, \
             patch("domain.copy_trade_manager.os.path.exists", return_value=False):
            mock_mt5.positions_get.return_value = []
            mock_info = MagicMock()
            mock_info.volume_min = 0.01
            mock_info.volume_max = 100.0
            mock_info.volume_step = 0.01
            mock_mt5.symbol_info.return_value = mock_info
            mock_mt5.symbol_info_tick.return_value = MagicMock(ask=1.1, bid=1.1)
            # Force early exit after lot cap by failing order send
            mock_mt5.order_send.return_value = MagicMock(retcode=10009, order=1, comment="ok")
            mock_mt5.TRADE_ACTION_DEAL = 1
            mock_mt5.ORDER_TYPE_BUY = 0
            mock_mt5.ORDER_TYPE_SELL = 1
            mock_mt5.ORDER_TIME_GTC = 0
            mock_mt5.ORDER_FILLING_IOC = 1
            try:
                mgr._open_copy_trade(99, m_pos)
            except Exception:
                pass
        # Cap notify should have fired
        joined = " ".join(str(c) for c in notify.call_args_list)
        self.assertIn("capped", joined.lower() + joined)

    def test_profile_name_isolated_in_notify(self):
        mgr, notify = _make_manager(profile_name="VantageDemo", copy_kill_switch=True)
        with patch.object(mgr, "_find_matching_symbol", return_value="EURUSD"), \
             patch("domain.copy_trade_manager.profile_session_validation_enabled", return_value=False):
            mgr._open_copy_trade(1, {"symbol": "EURUSD", "type": 0, "volume": 0.1})
        msg = str(notify.call_args)
        self.assertIn("VantageDemo", msg)


if __name__ == "__main__":
    unittest.main()
