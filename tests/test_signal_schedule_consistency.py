"""Keep the MT5 bot and dual-signal server schedule aligned."""
import unittest

import mt4_mt5_server
import mt5_signal_bot


class SignalScheduleConsistencyTests(unittest.TestCase):
    def test_all_signal_processes_share_the_active_slots(self) -> None:
        self.assertEqual(mt4_mt5_server.TARGET_HOURS, mt5_signal_bot.TARGET_HOURS)
        self.assertEqual(mt5_signal_bot.TARGET_HOURS, [2, 4, 5, 6, 9, 12, 13, 14, 15])
        self.assertEqual(mt5_signal_bot.DISABLED_HOURS, {3, 11})


if __name__ == "__main__":
    unittest.main()
