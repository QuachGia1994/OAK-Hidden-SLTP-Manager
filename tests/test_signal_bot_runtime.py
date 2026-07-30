"""Regression coverage for the v72 live signal-loop startup."""

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

    def test_startup_message_describes_only_the_v72_engine(self) -> None:
        message = mt5_signal_bot.build_startup_telegram_message(
            datetime(2026, 7, 16, 1), mt5_connected=True
        )
        self.assertIn("OAK SIGNAL BOT ONLINE", message)
        self.assertIn("v72", message)
        self.assertIn("GBP M30 signals -> XAU Layer 1 -> XAU Layer 2", message)
        self.assertIn("GBP at the next full Broker hour", message)
        self.assertIn("H3/H14/H16 reverse XAU once more", message)
        self.assertIn("Slots: H3 - H7 - H9 - H12 - H14 - H16", message)
        self.assertIn("Pairs: XAUUSD | GBPUSD | GBPAUD | GBPJPY | GBPCAD", message)
        self.assertIsNone(re.search(r"\bH1\b", message))
        self.assertIsNone(re.search(r"\bM15\b", message))
        self.assertNotIn("SW", message)
        self.assertNotIn("BT", message)

    def test_live_loop_has_no_per_signal_history_rebuild(self) -> None:
        source = inspect.getsource(mt5_signal_bot.main)
        self.assertEqual(source.count("rebuild_signals_on_startup()"), 1)
        self.assertNotIn("rebuild_recent_history(days=7)", source)

    def test_restart_guard_uses_a_fresh_clock_after_startup_rebuild(self) -> None:
        source = inspect.getsource(mt5_signal_bot.main)
        rebuild_index = source.index("startup_rebuilt = rebuild_signals_on_startup()")
        guard_index = source.index("if not startup_slots_marked:")
        refreshed_clock_index = source.rfind("broker_dt = get_broker_time()", rebuild_index, guard_index)
        self.assertGreater(refreshed_clock_index, rebuild_index)
        self.assertLess(refreshed_clock_index, guard_index)


if __name__ == "__main__":
    unittest.main()
