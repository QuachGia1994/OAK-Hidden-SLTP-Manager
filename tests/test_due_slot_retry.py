import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

import mt5_signal_bot


class TestDueSlotRetry(unittest.TestCase):
    def test_missing_layer_data_is_not_marked_sent_before_deadline(self):
        broker_now = datetime(2026, 8, 3, 3, 5)
        unresolved = {
            "signal": "WAIT",
            "signal_state": "WAIT",
            "entry_state": "WAIT",
            "entry_time": None,
        }
        with tempfile.NamedTemporaryFile(suffix=".json") as log_file:
            log_file.write(b"[]")
            log_file.flush()
            with patch.object(mt5_signal_bot, "_SIGNALS_LOG", log_file.name), \
                 patch.object(mt5_signal_bot, "evaluate_all_pairs_for_slot", return_value=unresolved), \
                 patch.object(mt5_signal_bot, "_persist_live_result"), \
                 patch.object(mt5_signal_bot, "sent_today", set()):
                mt5_signal_bot.catchup_due_slots(broker_now)
                self.assertNotIn((broker_now.date(), 3), mt5_signal_bot.sent_today)


if __name__ == "__main__":
    unittest.main()
