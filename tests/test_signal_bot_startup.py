"""Controlled startup smoke test for mt5_signal_bot.main()."""

from datetime import datetime
from unittest.mock import MagicMock, patch
import unittest

import mt5_signal_bot


class SignalBotStartupTests(unittest.TestCase):
    def test_main_startup_sequence_reaches_the_live_loop(self) -> None:
        broker_dt = datetime(2026, 7, 29, 10)
        account = MagicMock(balance=10000.0)
        calls = 0

        def broker_time():
            nonlocal calls
            calls += 1
            if calls > 2:
                raise KeyboardInterrupt("stop controlled smoke test")
            return broker_dt

        with (
            patch.object(mt5_signal_bot, "try_init_mt5", return_value=True),
            patch.object(mt5_signal_bot, "mt5") as terminal,
            patch.object(mt5_signal_bot, "get_broker_time", side_effect=broker_time),
            patch.object(mt5_signal_bot, "_load_state", return_value={"sent_today": set()}),
            patch.object(mt5_signal_bot, "rebuild_signals_on_startup", return_value=0),
            patch.object(mt5_signal_bot, "reconcile_due_xau_entry_alerts"),
            patch.object(mt5_signal_bot, "push_to_dashboard"),
            patch.object(mt5_signal_bot, "push_state_to_dashboard"),
            patch.object(mt5_signal_bot, "push_prices_to_dashboard"),
            patch.object(mt5_signal_bot, "send_telegram", return_value=True) as send,
            patch.object(mt5_signal_bot, "_process_live_slot"),
            patch.object(mt5_signal_bot, "_process_auto_closes"),
            patch.object(mt5_signal_bot, "_save_state"),
        ):
            terminal.account_info.return_value = account
            mt5_signal_bot.main(profile_name="VantageDemo")

        self.assertEqual(mt5_signal_bot._active_profile, "VantageDemo")
        startup_message = send.call_args_list[0].args[0]
        self.assertIn("OAK SIGNAL BOT ONLINE", startup_message)
        self.assertIn("v73", startup_message)


if __name__ == "__main__":
    unittest.main()
