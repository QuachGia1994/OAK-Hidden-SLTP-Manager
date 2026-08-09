import unittest
from datetime import datetime
from unittest.mock import patch
import mt5_signal_bot

class TestStartupDueSlotRecovery(unittest.TestCase):
    @patch("mt5_signal_bot.evaluate_all_pairs_for_slot")
    def test_startup_does_not_skip_due_slot(self, mock_eval):
        # Simulate startup at 08:10 Broker time
        broker_dt = datetime(2026, 7, 30, 8, 10, 0)
        
        # Verify due past slots are H3 and H7
        target_hours = mt5_signal_bot.get_target_hours(broker_dt)
        due_slots = [h for h in target_hours if broker_dt >= mt5_signal_bot.get_signal_datetime_for_slot(broker_dt, h)]
        self.assertEqual(due_slots, [3, 7])

if __name__ == "__main__":
    unittest.main()
