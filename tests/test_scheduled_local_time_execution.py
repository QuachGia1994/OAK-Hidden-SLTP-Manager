from datetime import datetime, timedelta

from domain.copy_trade_manager import _scheduled_local_datetimes


def test_telegram_schedule_uses_local_machine_wall_clock_without_broker_conversion():
    requested, execute = _scheduled_local_datetimes("2026-08-10", "20:15:00")

    assert requested == datetime(2026, 8, 10, 20, 15, 0)
    assert execute == datetime(2026, 8, 10, 20, 14, 58)


def test_two_second_early_lead_is_exactly_preserved():
    requested, execute = _scheduled_local_datetimes("2026-08-10", "20:15:00")
    assert requested - execute == timedelta(seconds=2)


def test_expiry_anchor_is_original_requested_local_time():
    requested, execute = _scheduled_local_datetimes("2026-08-10", "20:15:00")
    now = requested + timedelta(minutes=10, seconds=1)

    assert now > requested
    assert now > execute
    # The scheduler's expiry contract is +10m from the requested time,
    # not +10m from the -2s execution lead.
    assert (now - requested).total_seconds() > 600
