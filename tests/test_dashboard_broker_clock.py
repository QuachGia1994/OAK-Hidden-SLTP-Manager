"""Dashboard consumes only fresh and consistent Broker-clock heartbeats."""
from datetime import datetime, timedelta, timezone
import unittest

from controllers.dashboard_controller import _broker_now_from_heartbeat


class DashboardBrokerClockTests(unittest.TestCase):
    def test_fresh_heartbeat_advances_broker_time_from_observation(self) -> None:
        observed = datetime(2026, 7, 20, 1, 0, tzinfo=timezone.utc)
        heartbeat = {
            "broker_time": "2026-07-20T04:00:00",
            "broker_utc_offset": 3,
            "broker_observed_at_utc": observed.isoformat(),
        }

        broker_now = _broker_now_from_heartbeat(
            heartbeat,
            now_utc=observed + timedelta(seconds=10),
        )

        self.assertEqual(broker_now, datetime(2026, 7, 20, 4, 0, 10))

    def test_internally_inconsistent_heartbeat_is_rejected(self) -> None:
        observed = datetime(2026, 7, 20, 1, 0, tzinfo=timezone.utc)
        heartbeat = {
            "broker_time": "2026-07-20T05:00:00",
            "broker_utc_offset": 3,
            "broker_observed_at_utc": observed.isoformat(),
        }

        self.assertIsNone(
            _broker_now_from_heartbeat(
                heartbeat,
                now_utc=observed + timedelta(seconds=1),
            )
        )

    def test_stale_heartbeat_is_rejected(self) -> None:
        observed = datetime(2026, 7, 20, 1, 0, tzinfo=timezone.utc)
        heartbeat = {
            "broker_time": "2026-07-20T04:00:00",
            "broker_utc_offset": 3,
            "broker_observed_at_utc": observed.isoformat(),
        }

        self.assertIsNone(
            _broker_now_from_heartbeat(
                heartbeat,
                now_utc=observed + timedelta(seconds=16),
            )
        )


if __name__ == "__main__":
    unittest.main()
