"""Regression coverage for live signal-loop startup failures."""

import inspect
from datetime import datetime
import unittest

import mt5_signal_bot


class SignalBotRuntimeTests(unittest.TestCase):
    def test_live_loop_does_not_require_an_unbound_d_direction(self) -> None:
        source = inspect.getsource(mt5_signal_bot.main)

        self.assertNotIn("d_direction=d_direction", source)
        self.assertNotIn("d_direction", inspect.signature(mt5_signal_bot.get_pair_direction).parameters)

    def test_startup_message_reuses_the_daily_rule_matrix(self) -> None:
        message = mt5_signal_bot.build_startup_telegram_message(
            datetime(2026, 7, 16, 1, 0),
            mt5_connected=True,
        )

        self.assertIn("Slots: H=2, H=3, H=4, H=5, H=7, H=8, H=9, H=11, H=12, H=13, H=14, H=15", message)
        self.assertIn("Tắt: H=6, H=10, H=17.", message)
        self.assertNotIn("02-15:45", message)


if __name__ == "__main__":
    unittest.main()
