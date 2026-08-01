"""The v87 record schema has no reference-only or do-not-enter state."""
from datetime import datetime
from unittest.mock import patch
import unittest
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot


class SignalRecordSchemaTests(unittest.TestCase):
    def test_new_record_never_serializes_deactivated(self):
        broker_dt = datetime(2026, 8, 3, 9, 0)
        with patch.object(mt5_signal_bot, "get_current_prices", return_value={}):
            record = mt5_signal_bot._format_signal_record(
                9,
                broker_dt,
                "BUY",
                "09:49",
                {"XAUUSD": "BUY"},
                "v87",
                extra_fields={"deactivated": True},
            )

        self.assertNotIn("deactivated", record)


if __name__ == "__main__":
    unittest.main()
