"""Regression tests for Telegram quick-order time parsing."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import mimo_bot


class QuickOrderTimeTests(unittest.TestCase):
    def tearDown(self):
        mimo_bot._pending_signal.clear()

    @patch("mimo_bot.telebot.TeleBot")
    def test_empty_token_only_disables_constructor_validation(self, telebot_class):
        mimo_bot._create_telegram_bot("")

        telebot_class.assert_called_once_with(
            "",
            parse_mode="Markdown",
            validate_token=False,
        )

    def test_accepts_free_hour_and_minute(self):
        self.assertEqual(
            mimo_bot._parse_quick_order_input("0.01 09:15 vantage", signal_hour="8"),
            ("0.01", "09:15", "vantage"),
        )

    def test_normalizes_single_digit_hour(self):
        self.assertEqual(
            mimo_bot._parse_quick_order_input("0.01 9:05 vantage", signal_hour="8"),
            ("0.01", "09:05", "vantage"),
        )

    def test_keeps_legacy_minute_input(self):
        self.assertEqual(
            mimo_bot._parse_quick_order_input("0.01 49 vantage", signal_hour="8"),
            ("0.01", "08:49", "vantage"),
        )

    def test_accepts_clock_boundaries(self):
        for clock in ("00:00", "23:59"):
            with self.subTest(clock=clock):
                self.assertEqual(
                    mimo_bot._parse_quick_order_input(f"0.01 {clock} demo", signal_hour="8")[1],
                    clock,
                )

    def test_rejects_invalid_or_ambiguous_input(self):
        for text in ("0.01 24:00 demo", "0.01 09:60 demo", "0.01 now demo", "0.01 09:15"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                mimo_bot._parse_quick_order_input(text, signal_hour="8")

    @patch("mimo_bot._ack_then_inject")
    @patch("mimo_bot.is_admin", return_value=True)
    def test_valid_reply_injects_broker_clock_only_after_user_input(self, _is_admin, inject):
        message = self._message("0.01 09:15 vantage")
        mimo_bot._pending_signal[42] = self._context()

        mimo_bot.handle_signal_lot(message)

        self.assertEqual(inject.call_args.args[1], "/pending SELL XAUUSD 0.01 @09:15 vantage")
        self.assertNotIn(42, mimo_bot._pending_signal)

    @patch("mimo_bot._ack_then_inject")
    @patch("mimo_bot.bot.reply_to")
    @patch("mimo_bot.is_admin", return_value=True)
    def test_invalid_reply_never_injects_and_keeps_confirmation_context(self, _is_admin, reply, inject):
        message = self._message("0.01 24:00 vantage")
        mimo_bot._pending_signal[42] = self._context()

        mimo_bot.handle_signal_lot(message)

        inject.assert_not_called()
        reply.assert_called_once()
        self.assertIn(42, mimo_bot._pending_signal)

    @staticmethod
    def _message(text):
        return SimpleNamespace(
            text=text,
            chat=SimpleNamespace(id=42),
            from_user=SimpleNamespace(id=7),
        )

    @staticmethod
    def _context():
        return {
            "direction": "SELL",
            "pair": "XAUUSD",
            "hour": "8",
            "step": "lot",
            "admin_user_id": 7,
        }


if __name__ == "__main__":
    unittest.main()
