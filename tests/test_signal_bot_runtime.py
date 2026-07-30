"""Regression coverage for the v79 live signal-loop startup."""

import inspect
import re
from datetime import datetime
import unittest

import mt5_signal_bot


class SignalBotRuntimeTests(unittest.TestCase):
    def test_live_loop_does_not_require_an_unbound_direction(self) -> None:
        source = inspect.getsource(mt5_signal_bot.main)
        self.assertNotIn("d_direction=d_direction", source)
        self.assertNotIn("d_direction", inspect.signature(mt5_signal_bot.get_pair_direction).parameters)

    def test_startup_message_describes_only_the_v79_engine(self) -> None:
        message = mt5_signal_bot.build_startup_telegram_message(
            datetime(2026, 7, 16, 1), mt5_connected=True
        )
        self.assertIn("OAK SIGNAL BOT ONLINE", message)
        self.assertIn("v79", message)
        self.assertIn("Three-layer M30", message)
        self.assertIn("Slots: H3 - H7 - H9 - H12 - H14 - H16", message)

    def test_live_loop_has_no_per_signal_history_rebuild(self) -> None:
        source = inspect.getsource(mt5_signal_bot.main)
        self.assertEqual(source.count("rebuild_signals_on_startup()"), 1)
        self.assertNotIn("rebuild_recent_history(days=7)", source)


if __name__ == "__main__":
    unittest.main()
