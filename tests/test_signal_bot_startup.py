"""Controlled startup smoke test for mt5_signal_bot.main()."""
from datetime import datetime
from unittest.mock import MagicMock, patch
import unittest

import mt5_signal_bot


class SignalBotStartupTests(unittest.TestCase):
    def test_main_startup_sequence_completes_past_telegram_message(self) -> None:
        """Smoke test verifying main() initializes profile, sends Telegram, rebuilds, and enters loop."""
        mock_broker_dt = datetime(2026, 7, 29, 10, 0)
        mock_account_info = MagicMock()
        mock_account_info.balance = 10000.0

        loop_counter = 0

        def mock_get_broker_time():
            nonlocal loop_counter
            loop_counter += 1
            if loop_counter > 2:
                raise KeyboardInterrupt("Stop main loop test")
            return mock_broker_dt

        with (
            patch.object(mt5_signal_bot, "try_init_mt5", return_value=True),
            patch.object(mt5_signal_bot, "mt5") as mock_mt5,
            patch.object(mt5_signal_bot, "get_broker_time", side_effect=mock_get_broker_time),
            patch.object(mt5_signal_bot, "_load_state", return_value={"sent_today": set()}),
            patch.object(mt5_signal_bot, "rebuild_signals_on_startup", return_value=0),
            patch.object(mt5_signal_bot, "reconcile_due_xau_entry_alerts"),
            patch.object(mt5_signal_bot, "push_to_dashboard"),
            patch.object(mt5_signal_bot, "push_state_to_dashboard"),
            patch.object(mt5_signal_bot, "push_prices_to_dashboard"),
            patch.object(mt5_signal_bot, "send_telegram", return_value=True) as mock_send_telegram,
            patch.object(mt5_signal_bot, "_process_live_slot"),
            patch.object(mt5_signal_bot, "_process_auto_closes"),
            patch.object(mt5_signal_bot, "_save_state"),
        ):
            mock_mt5.account_info.return_value = mock_account_info

            mt5_signal_bot.main(profile_name="VantageDemo")

        self.assertEqual(mt5_signal_bot._active_profile, "VantageDemo")
        mock_send_telegram.assert_called()
        # Verify the startup message contained bot online tag
        startup_msg_call = mock_send_telegram.call_args_list[0][0][0]
        self.assertIn("🤖 OAK SIGNAL BOT ONLINE · v68", startup_msg_call)


if __name__ == "__main__":
    unittest.main()
