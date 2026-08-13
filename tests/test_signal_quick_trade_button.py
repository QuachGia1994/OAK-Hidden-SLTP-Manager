import unittest
from datetime import datetime
from unittest.mock import patch

import mt5_signal_bot as bot
from quick_trade_flow import QuickTradeManager, QuickTradeState


class SignalQuickTradeButtonTests(unittest.TestCase):
    def _ready_record(self, hour=7):
        return {
            "logic_version": 87,
            "source_date": "2026-08-01",
            "hour": hour,
            "signal": "BUY",
            "signal_state": "READY",
            "entry_state": "READY",
            "record_revision": 2,
            "entry_time": "07:49",
            "pair_dirs": {pair: "BUY" for pair in bot.DISPLAY_SIGNAL_PAIRS},
        }

    def test_keyboard_is_qt_start_only(self):
        kb = bot.signal_quick_trade_keyboard()
        self.assertEqual(len(kb), 1)
        self.assertEqual(len(kb[0]), 1)
        self.assertEqual(kb[0][0]["callback_data"], "qt:start")
        self.assertIn("QUICK TRADE", kb[0][0]["text"])

    def test_send_signal_alert_attaches_keyboard(self):
        bot.signal_alerts_sent.clear()
        bot.signal_alerts_pending.clear()
        record = self._ready_record(hour=3)
        broker_dt = datetime(2026, 8, 1, 3, 0)

        with patch.object(bot, "send_telegram", return_value=True) as mock_send, \
             patch.object(bot, "_save_state"):
            ok = bot.send_signal_alert(record, broker_dt=broker_dt)

        self.assertTrue(ok)
        self.assertTrue(mock_send.called)
        args, kwargs = mock_send.call_args
        if len(args) >= 2:
            keyboard = args[1]
        else:
            keyboard = kwargs.get("inline_keyboard")
        self.assertIsNotNone(keyboard)
        self.assertEqual(keyboard[0][0]["callback_data"], "qt:start")

    def test_non_actionable_does_not_send(self):
        bot.signal_alerts_sent.clear()
        record = self._ready_record()
        record["signal"] = "WAIT"
        with patch.object(bot, "send_telegram", return_value=True) as mock_send:
            bot.send_signal_alert(record, broker_dt=datetime(2026, 8, 1, 7, 0))
        mock_send.assert_not_called()

    def test_qt_start_renders_symbol_selection(self):
        manager = QuickTradeManager()

        class _Msg:
            message_id = 42

            class chat:
                id = 1001

        class _User:
            id = 2002

        class _Call:
            id = "cb1"
            data = "qt:start"
            message = _Msg()
            from_user = _User()

        edits = []
        answers = []

        class _Bot:
            def edit_message_text(self, **kwargs):
                edits.append(kwargs)

            def answer_callback_query(self, *a, **k):
                answers.append((a, k))

            def send_message(self, **kwargs):
                edits.append(kwargs)

        manager.handle_callback(_Call(), _Bot())
        self.assertTrue(edits)
        session = manager.get_session_by_chat(1001)
        self.assertIsNotNone(session)
        self.assertEqual(session.state, QuickTradeState.SYMBOL_SELECTION)
        self.assertIn("reply_markup", edits[0])


if __name__ == "__main__":
    unittest.main()
