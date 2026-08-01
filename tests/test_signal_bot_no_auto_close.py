"""v87 contract: Signal Bot does not own an automatic position-close schedule."""
import inspect
import unittest
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot


class SignalBotNoAutoCloseTests(unittest.TestCase):
    def test_runtime_has_no_auto_close_manager_or_schedule(self):
        source = inspect.getsource(mt5_signal_bot)
        self.assertNotIn("SignalAutoCloseManager", source)
        self.assertNotIn("auto_close_state_", source)
        self.assertNotIn("17:59", source)
        self.assertNotIn("19:59", source)


if __name__ == "__main__":
    unittest.main()
