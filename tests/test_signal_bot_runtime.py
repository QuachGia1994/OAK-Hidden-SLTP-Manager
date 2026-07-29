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

        self.assertIn("🤖 OAK SIGNAL BOT ONLINE · v64", message)
        self.assertIn("Slots: H3 · H7 · H9 · H12 · H14 · H16", message)
        self.assertIn("Pairs: GBPAUD / GBPUSD → XAUUSD", message)
        self.assertIn("Auto-close: XAU 17:59 · GBP 19:59 Broker", message)
        self.assertNotIn("H1 hôm qua", message)

    def test_live_loop_has_no_per_signal_history_rebuild(self) -> None:
        source = inspect.getsource(mt5_signal_bot.main)

        self.assertEqual(source.count("rebuild_signals_on_startup()"), 1)
        self.assertNotIn("rebuild_recent_history(days=7)", source)

    def test_restart_guard_uses_a_fresh_clock_after_startup_rebuild(self) -> None:
        source = inspect.getsource(mt5_signal_bot.main)
        rebuild_index = source.index("startup_rebuilt = rebuild_signals_on_startup()")
        guard_index = source.index("if not startup_slots_marked:")
        refreshed_clock_index = source.rfind(
            "broker_dt = get_broker_time()",
            rebuild_index,
            guard_index,
        )

        self.assertGreater(refreshed_clock_index, rebuild_index)
        self.assertLess(refreshed_clock_index, guard_index)


if __name__ == "__main__":
    unittest.main()
