# -*- coding: utf-8 -*-
"""
Tests for Telegram Quick Trade Flow (quick_trade_flow.py & mimo_bot.py integration).
Covers all 24 mandated scenarios including multi-profile per-symbol/per-lot config,
mandatory netting behavior, precheck reporting, idempotency, partial failure, and session isolation.
"""

import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from quick_trade_flow import (
    QuickTradeManager,
    QuickTradeSession,
    QuickTradeState,
    validate_entry_time,
    validate_lot,
    validate_symbol,
)


class MockBot:
    def __init__(self):
        self.sent_messages = []
        self.edited_messages = []
        self.replied_messages = []
        self.callback_answers = []

    def send_message(self, chat_id, text, reply_markup=None, **kwargs):
        self.sent_messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})

    def edit_message_text(self, chat_id, message_id, text, reply_markup=None, **kwargs):
        self.edited_messages.append({"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": reply_markup})

    def reply_to(self, message, text, reply_markup=None, **kwargs):
        self.replied_messages.append({"chat_id": message.chat.id, "text": text, "reply_markup": reply_markup})

    def answer_callback_query(self, callback_query_id, text=None, show_alert=False):
        self.callback_answers.append({"id": callback_query_id, "text": text})


def make_call(callback_data, chat_id=100, user_id=1, message_id=50):
    return SimpleNamespace(
        id=f"cb_{int(time.time()*1000)}",
        data=callback_data,
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=chat_id),
            message_id=message_id,
        ),
    )


def make_msg(text, chat_id=100, user_id=1, message_id=50):
    return SimpleNamespace(
        text=text,
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=user_id),
        message_id=message_id,
    )


class QuickTradeFlowTests(unittest.TestCase):
    def setUp(self):
        self.mgr = QuickTradeManager()
        self.mgr.get_all_profiles_fn = lambda: ["Profile A", "Profile B", "Profile C"]
        self.bot = MockBot()

    def test_01_symbol_selection(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        self.assertEqual(session.state, QuickTradeState.SYMBOL_SELECTION)

        call = make_call("qt:sym:XAUUSD")
        self.mgr.handle_callback(call, self.bot)
        self.assertEqual(session.symbol, "XAUUSD")
        self.assertEqual(session.state, QuickTradeState.DIRECTION_SELECTION)

    def test_02_buy_selection(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.symbol = "XAUUSD"
        session.state = QuickTradeState.DIRECTION_SELECTION

        call = make_call("qt:dir:BUY")
        self.mgr.handle_callback(call, self.bot)
        self.assertEqual(session.direction, "BUY")
        self.assertEqual(session.state, QuickTradeState.ENTRY_TIME_SELECTION)

    def test_03_sell_selection(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.symbol = "EURUSD"
        session.state = QuickTradeState.DIRECTION_SELECTION

        call = make_call("qt:dir:SELL")
        self.mgr.handle_callback(call, self.bot)
        self.assertEqual(session.direction, "SELL")
        self.assertEqual(session.state, QuickTradeState.ENTRY_TIME_SELECTION)

    def test_04_entry_time_selection(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.direction = "BUY"
        session.state = QuickTradeState.ENTRY_TIME_SELECTION

        call = make_call("qt:time:09:15")
        self.mgr.handle_callback(call, self.bot)
        self.assertEqual(session.entry_time, "09:15")
        self.assertEqual(session.state, QuickTradeState.PROFILE_SELECTION)

    def test_05_multi_profile_selection(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.direction = "BUY"
        session.entry_time = "09:15"
        session.state = QuickTradeState.PROFILE_SELECTION

        self.mgr.handle_callback(make_call("qt:prof_toggle:Profile A"), self.bot)
        self.mgr.handle_callback(make_call("qt:prof_toggle:Profile C"), self.bot)
        self.assertEqual(session.selected_profiles, ["Profile A", "Profile C"])

        self.mgr.handle_callback(make_call("qt:prof_next"), self.bot)
        self.assertEqual(session.state, QuickTradeState.PROFILE_SYMBOL_CONFIGURATION)
        self.assertIn("Profile A", session.profile_configs)
        self.assertIn("Profile C", session.profile_configs)

    def test_06_per_profile_symbol(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.selected_profiles = ["Profile A", "Profile C"]
        session.profile_configs = {
            "Profile A": {"symbol": "XAUUSD", "lot": 0.01},
            "Profile C": {"symbol": "XAUUSD", "lot": 0.05},
        }
        session.state = QuickTradeState.PROFILE_SYMBOL_CONFIGURATION

        msg = make_msg("EURUSD")
        session.editing_profile = "Profile C"
        session.state = QuickTradeState.PROFILE_SYMBOL_CUSTOM_INPUT

        handled = self.mgr.handle_text_input(msg, self.bot)
        self.assertTrue(handled)
        self.assertEqual(session.profile_configs["Profile C"]["symbol"], "EURUSD")
        self.assertEqual(session.profile_configs["Profile A"]["symbol"], "XAUUSD")

    def test_07_per_profile_lot(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.selected_profiles = ["Profile A", "Profile C"]
        session.profile_configs = {
            "Profile A": {"symbol": "XAUUSD", "lot": None},
            "Profile C": {"symbol": "EURUSD", "lot": None},
        }
        session.state = QuickTradeState.PROFILE_LOT_CONFIGURATION

        session.editing_profile = "Profile A"
        session.state = QuickTradeState.PROFILE_LOT_CUSTOM_INPUT
        self.mgr.handle_text_input(make_msg("0.01"), self.bot)

        session.editing_profile = "Profile C"
        session.state = QuickTradeState.PROFILE_LOT_CUSTOM_INPUT
        self.mgr.handle_text_input(make_msg("0.05"), self.bot)

        self.assertEqual(session.profile_configs["Profile A"]["lot"], 0.01)
        self.assertEqual(session.profile_configs["Profile C"]["lot"], 0.05)

    def test_08_invalid_lot(self):
        ok, val, err = validate_lot("-0.05")
        self.assertFalse(ok)
        self.assertIn("lớn hơn 0", err)

        ok, val, err = validate_lot("abc")
        self.assertFalse(ok)
        self.assertIn("số thực", err)

        ok, val, err = validate_lot("0.01")
        self.assertTrue(ok)
        self.assertEqual(val, 0.01)

    def test_09_missing_symbol(self):
        ok, val, err = validate_symbol("?")
        self.assertFalse(ok)

        ok, val, err = validate_symbol("BTCUSD")
        self.assertTrue(ok)
        self.assertEqual(val, "BTCUSD")

    def test_10_confirm_summary(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.direction = "BUY"
        session.entry_time = "03:49"
        session.selected_profiles = ["Profile A", "Profile C"]
        session.profile_configs = {
            "Profile A": {"symbol": "XAUUSD", "lot": 0.01},
            "Profile C": {"symbol": "EURUSD", "lot": 0.05},
        }
        text, kb = self.mgr.render_step_review(session)
        self.assertIn("TRADE REVIEW", text)
        self.assertIn("BUY", text)
        self.assertIn("03:49", text)
        self.assertIn("Profile A", text)
        self.assertIn("XAUUSD", text)
        self.assertIn("0.01", text)
        self.assertIn("Profile C", text)
        self.assertIn("EURUSD", text)
        self.assertIn("0.05", text)

    def test_11_existing_buy_requested_buy(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.direction = "BUY"
        session.selected_profiles = ["Profile A"]
        session.profile_configs = {"Profile A": {"symbol": "XAUUSD", "lot": 0.01}}

        self.mgr.position_provider_fn = lambda prof, sym: [{"ticket": 1, "symbol": "XAUUSD", "type": "BUY", "volume": 0.01}]
        report = self.mgr.run_precheck(session)
        self.assertEqual(len(report), 1)
        self.assertIn("EXISTING BUY", report[0]["action_desc"])
        self.assertFalse(report[0]["netting_needed"])

    def test_12_existing_sell_requested_sell(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.direction = "SELL"
        session.selected_profiles = ["Profile A"]
        session.profile_configs = {"Profile A": {"symbol": "XAUUSD", "lot": 0.05}}

        self.mgr.position_provider_fn = lambda prof, sym: [{"ticket": 2, "symbol": "XAUUSD", "type": "SELL", "volume": 0.05}]
        report = self.mgr.run_precheck(session)
        self.assertIn("EXISTING SELL", report[0]["action_desc"])
        self.assertFalse(report[0]["netting_needed"])

    def test_13_existing_sell_requested_buy(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.direction = "BUY"
        session.selected_profiles = ["Profile A"]
        session.profile_configs = {"Profile A": {"symbol": "XAUUSD", "lot": 0.01}}

        self.mgr.position_provider_fn = lambda prof, sym: [{"ticket": 3, "symbol": "XAUUSD", "type": "SELL", "volume": 0.05}]
        report = self.mgr.run_precheck(session)
        self.assertTrue(report[0]["netting_needed"])
        self.assertEqual(report[0]["opp_type"], "SELL")
        self.assertIn("NETTING: CLOSE SELL (0.05) → OPEN BUY (0.01)", report[0]["action_desc"])

    def test_14_existing_buy_requested_sell(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.direction = "SELL"
        session.selected_profiles = ["Profile A"]
        session.profile_configs = {"Profile A": {"symbol": "XAUUSD", "lot": 0.01}}

        self.mgr.position_provider_fn = lambda prof, sym: [{"ticket": 4, "symbol": "XAUUSD", "type": "BUY", "volume": 0.02}]
        report = self.mgr.run_precheck(session)
        self.assertTrue(report[0]["netting_needed"])
        self.assertEqual(report[0]["opp_type"], "BUY")
        self.assertIn("NETTING: CLOSE BUY (0.02) → OPEN SELL (0.01)", report[0]["action_desc"])

    def test_15_netting_close_succeeds(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.direction = "BUY"
        session.entry_time = "03:49"
        session.selected_profiles = ["Profile A"]
        session.profile_configs = {"Profile A": {"symbol": "XAUUSD", "lot": 0.01}}

        self.mgr.position_provider_fn = lambda prof, sym: [{"ticket": 5, "symbol": "XAUUSD", "type": "SELL", "volume": 0.05}]
        self.mgr.position_closer_fn = lambda prof, sym, opp: (True, "Closed SELL 0.05")
        self.mgr.order_executor_fn = lambda prof, sym, dir, lot, t: (True, "OK", 9991)

        self.mgr.run_precheck(session)
        results = self.mgr.execute_trade(session)

        self.assertTrue(results[0]["close_success"])
        self.assertTrue(results[0]["open_success"])
        self.assertEqual(results[0]["ticket"], 9991)

    def test_16_netting_close_fails_does_not_open_opposite_trade(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.direction = "BUY"
        session.entry_time = "03:49"
        session.selected_profiles = ["Profile A"]
        session.profile_configs = {"Profile A": {"symbol": "XAUUSD", "lot": 0.01}}

        open_called = []
        self.mgr.position_provider_fn = lambda prof, sym: [{"ticket": 6, "symbol": "XAUUSD", "type": "SELL", "volume": 0.05}]
        self.mgr.position_closer_fn = lambda prof, sym, opp: (False, "Broker timeout on close")
        self.mgr.order_executor_fn = lambda prof, sym, dir, lot, t: (open_called.append(True) or True, "OK", 9992)

        self.mgr.run_precheck(session)
        results = self.mgr.execute_trade(session)

        self.assertFalse(results[0]["close_success"])
        self.assertFalse(results[0]["open_success"])
        self.assertIn("SKIPPED", results[0]["open_message"])
        self.assertEqual(open_called, [], "Order executor MUST NOT be called if netting close failed!")

    def test_17_open_order_fails_after_successful_close(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.direction = "BUY"
        session.entry_time = "03:49"
        session.selected_profiles = ["Profile A"]
        session.profile_configs = {"Profile A": {"symbol": "XAUUSD", "lot": 0.01}}

        self.mgr.position_provider_fn = lambda prof, sym: [{"ticket": 7, "symbol": "XAUUSD", "type": "SELL", "volume": 0.05}]
        self.mgr.position_closer_fn = lambda prof, sym, opp: (True, "Closed SELL 0.05")
        self.mgr.order_executor_fn = lambda prof, sym, dir, lot, t: (False, "Margin insufficient", None)

        self.mgr.run_precheck(session)
        results = self.mgr.execute_trade(session)

        self.assertTrue(results[0]["close_success"])
        self.assertFalse(results[0]["open_success"])
        self.assertIn("Margin insufficient", results[0]["open_message"])

    def test_18_multi_profile_partial_success(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.direction = "BUY"
        session.entry_time = "03:49"
        session.selected_profiles = ["Profile A", "Profile B", "Profile C"]
        session.profile_configs = {
            "Profile A": {"symbol": "XAUUSD", "lot": 0.01},
            "Profile B": {"symbol": "XAUUSD", "lot": 0.01},
            "Profile C": {"symbol": "EURUSD", "lot": 0.05},
        }

        def mock_closer(prof, sym, opp):
            if prof == "Profile B":
                return False, "Profile B close error"
            return True, "Close OK"

        def mock_executor(prof, sym, dir, lot, t):
            return True, "Open OK", 8800

        self.mgr.position_provider_fn = lambda prof, sym: [{"ticket": 8, "symbol": sym, "type": "SELL", "volume": 0.01}] if prof in ("Profile A", "Profile B") else []
        self.mgr.position_closer_fn = mock_closer
        self.mgr.order_executor_fn = mock_executor

        self.mgr.run_precheck(session)
        results = self.mgr.execute_trade(session)

        self.assertEqual(len(results), 3)
        self.assertTrue(results[0]["open_success"])  # Profile A
        self.assertFalse(results[1]["open_success"]) # Profile B FAILED
        self.assertTrue(results[2]["open_success"])  # Profile C

        res_text = self.mgr.render_execution_results(session)
        self.assertIn("2/3 profiles thực thi thành công", res_text)

    def test_19_duplicate_confirm_does_not_duplicate_execution(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.selected_profiles = ["Profile A"]
        session.profile_configs = {"Profile A": {"symbol": "XAUUSD", "lot": 0.01}}
        session.state = QuickTradeState.REVIEW
        session.confirm_lock = True  # Already locked during execution

        exec_count = [0]

        def count_exec(prof, sym, dir, lot, t):
            exec_count[0] += 1
            return True, "OK", 777

        self.mgr.order_executor_fn = count_exec

        # Second confirm while locked
        self.mgr.handle_callback(make_call("qt:confirm", chat_id=100, user_id=1), self.bot)
        self.assertEqual(exec_count[0], 0, "Duplicate confirm MUST NOT execute trade twice!")
        self.assertIn("không nhấn lặp lại", self.bot.callback_answers[-1]["text"])

    def test_20_cancel_clears_session(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        self.assertIsNotNone(self.mgr.get_session(100, 1))

        self.mgr.handle_callback(make_call("qt:cancel", chat_id=100, user_id=1), self.bot)
        self.assertIsNone(self.mgr.get_session(100, 1))

    def test_21_session_timeout_clears_state(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)
        session.last_activity_at = time.time() - 301.0  # 301 seconds ago

        # Querying expired session clears it
        retrieved = self.mgr.get_session(100, 1)
        self.assertIsNone(retrieved)

    def test_22_cross_user_callback_session_isolation(self):
        session = self.mgr.start_session(chat_id=100, user_id=1)  # User 1 session

        # User 2 clicks User 1's callback in same chat
        call_user2 = make_call("qt:sym:XAUUSD", chat_id=100, user_id=2)
        self.mgr.handle_callback(call_user2, self.bot)

        # Should answer alert and NOT alter user 1 session
        self.assertIn("thuộc về người dùng khác", self.bot.callback_answers[-1]["text"])
        self.assertEqual(session.state, QuickTradeState.SYMBOL_SELECTION)

    def test_23_existing_command_buy_sell_regression(self):
        import mimo_bot

        with patch.object(mimo_bot, "ADMIN_CHAT_ID", 100), patch("mimo_bot._ack_then_inject") as mock_inject:
            msg = SimpleNamespace(
                text="/pending BUY XAUUSD 0.01 @09:15 vantage",
                chat=SimpleNamespace(id=100),
                from_user=SimpleNamespace(id=1),
                message_id=50,
            )
            mimo_bot.cmd_pending(msg)
            mock_inject.assert_called_once()

    def test_24_existing_mt5_execution_regression(self):
        from quick_trade_flow import _default_position_provider, _default_position_closer, _default_order_executor
        self.assertTrue(callable(_default_position_provider))
        self.assertTrue(callable(_default_position_closer))
        self.assertTrue(callable(_default_order_executor))


if __name__ == "__main__":
    unittest.main()
