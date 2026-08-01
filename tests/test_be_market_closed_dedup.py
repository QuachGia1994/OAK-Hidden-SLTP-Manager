import threading
import unittest

from domain.monitor_worker import MonitorWorker


class BEMarketClosedStateTests(unittest.TestCase):
    def test_closed_position_clears_retry_state(self):
        worker = MonitorWorker(
            {"profile_name": "VantageDemo"},
            lambda _message: None,
            threading.Event(),
        )
        worker._be_retry_state[("VantageDemo", 42, "MOVE_BE")] = {"attempt_count": 3}
        worker._be_retry_state[("Other", 42, "MOVE_BE")] = {"attempt_count": 3}

        worker._clear_be_retry_state_for_tickets({42})

        self.assertNotIn(("VantageDemo", 42, "MOVE_BE"), worker._be_retry_state)
        self.assertIn(("Other", 42, "MOVE_BE"), worker._be_retry_state)


if __name__ == "__main__":
    unittest.main()
