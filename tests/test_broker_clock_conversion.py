"""Absolute Broker-to-local datetime conversion for scheduled entries."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch
import unittest

from domain.copy_trade_manager import CopyTradeManager, _broker_clock_to_local_datetime
import domain.copy_trade_manager as copy_trade_manager


def _resolver(broker_now, offsets):
    resolver = Mock()
    resolver.broker_from_utc_datetime.return_value = broker_now

    def to_utc(target_broker):
        offset = offsets[target_broker.date()]
        return (target_broker - timedelta(hours=offset)).replace(tzinfo=timezone.utc)

    resolver.utc_from_broker_datetime.side_effect = to_utc
    return resolver


class BrokerClockConversionTests(unittest.TestCase):
    def test_preserves_local_date_when_clock_conversion_crosses_midnight(self):
        utc_now = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)
        broker_now = datetime(2026, 7, 20, 13, 0)
        resolver = _resolver(broker_now, {broker_now.date(): 3})

        result = _broker_clock_to_local_datetime(
            "23:30",
            now_utc=utc_now,
            broker_clock_resolver=resolver,
            local_timezone=timezone(timedelta(hours=7)),
        )

        self.assertEqual(result, datetime(2026, 7, 21, 3, 30))
        resolver.utc_from_broker_datetime.assert_called_once_with(datetime(2026, 7, 20, 23, 30))

    def test_passed_friday_clock_rolls_to_monday_broker_date(self):
        utc_now = datetime(2026, 3, 27, 18, 0, tzinfo=timezone.utc)
        broker_now = datetime(2026, 3, 27, 20, 0)
        monday = datetime(2026, 3, 30, 9, 15)
        resolver = _resolver(broker_now, {monday.date(): 3})

        result = _broker_clock_to_local_datetime(
            "09:15",
            now_utc=utc_now,
            broker_clock_resolver=resolver,
            local_timezone=timezone(timedelta(hours=7)),
        )

        self.assertEqual(result, datetime(2026, 3, 30, 13, 15))
        resolver.utc_from_broker_datetime.assert_called_once_with(monday)

    def test_target_broker_date_controls_dst_offset(self):
        utc_now = datetime(2026, 3, 27, 18, 0, tzinfo=timezone.utc)
        broker_now = datetime(2026, 3, 27, 20, 0)
        target = datetime(2026, 3, 30, 9, 15)
        resolver = _resolver(
            broker_now,
            {
                broker_now.date(): 2,
                target.date(): 3,
            },
        )

        result = _broker_clock_to_local_datetime(
            "09:15",
            now_utc=utc_now,
            broker_clock_resolver=resolver,
            local_timezone=timezone.utc,
        )

        self.assertEqual(result, datetime(2026, 3, 30, 6, 15))
        resolver.utc_from_broker_datetime.assert_called_once_with(target)

    def test_future_clock_stays_on_current_broker_date(self):
        utc_now = datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc)
        broker_now = datetime(2026, 7, 20, 9, 0)
        resolver = _resolver(broker_now, {broker_now.date(): 3})

        result = _broker_clock_to_local_datetime(
            "09:15",
            now_utc=utc_now,
            broker_clock_resolver=resolver,
            local_timezone=timezone(timedelta(hours=-5)),
        )

        self.assertEqual(result, datetime(2026, 7, 20, 1, 15))

    def test_rejects_invalid_clock_and_naive_utc(self):
        resolver = Mock()
        for invalid in ("24:00", "09:60", "noon"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                _broker_clock_to_local_datetime(invalid, broker_clock_resolver=resolver)
        with self.assertRaises(ValueError):
            _broker_clock_to_local_datetime(
                "09:15",
                now_utc=datetime(2026, 7, 20, 6, 0),
                broker_clock_resolver=resolver,
            )

    def test_pending_command_persists_the_absolute_local_date_and_time(self):
        manager = CopyTradeManager.__new__(CopyTradeManager)
        manager.config = {"profile_name": "Vantage"}
        manager.notify = Mock()
        manager.scheduled_trades = []

        with tempfile.TemporaryDirectory() as temp_dir:
            scheduled_file = Path(temp_dir) / "waiting.json"
            manager.scheduled_file = str(scheduled_file)
            with (
                patch.object(manager, "_get_profile_names", return_value={"vantage"}),
                patch.object(
                    copy_trade_manager,
                    "_broker_clock_to_local_datetime",
                    return_value=datetime(2026, 7, 21, 3, 30),
                ) as convert,
                patch.object(copy_trade_manager.mt5, "positions_get", return_value=[]),
                patch.object(copy_trade_manager, "get_natural_response", return_value="scheduled"),
            ):
                manager._handle_telegram_text("/pending BUY XAUUSD 0.01 @23:30")

            records = json.loads(scheduled_file.read_text(encoding="utf-8"))

        convert.assert_called_once_with("23:30")
        self.assertEqual(records[0]["date"], "2026-07-21")
        self.assertEqual(records[0]["time"], "03:30:00")


if __name__ == "__main__":
    unittest.main()
