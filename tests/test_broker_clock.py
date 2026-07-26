"""Tests for calibrated MT5 timestamp modes and fail-closed Broker time."""

import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from domain.broker_clock import BrokerClock, BrokerClockError


def epoch(year, month, day, hour=0, minute=0, second=0):
    return int(datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc).timestamp())


class AdvancingTick:
    def __init__(self, timestamp):
        self.timestamp = timestamp

    def read(self, read_index):
        return SimpleNamespace(
            time=self.timestamp,
            time_msc=self.timestamp * 1000 + read_index,
        )


def tick(timestamp):
    return AdvancingTick(timestamp)


def static_tick(timestamp):
    return SimpleNamespace(time=timestamp, time_msc=timestamp * 1000)


class FakeMT5:
    TIMEFRAME_D1 = 16408

    def __init__(self, rates_by_symbol, ticks_by_symbol=None):
        self.rates_by_symbol = rates_by_symbol
        self.ticks_by_symbol = ticks_by_symbol or {}
        self.rate_calls = []
        self.tick_calls = []
        self.tick_read_counts = {}
        self.connected = True
        self.identity = ("Demo", 1)

    def terminal_info(self):
        return object() if self.connected else None

    def account_info(self):
        if not self.connected:
            return None
        return SimpleNamespace(server=self.identity[0], login=self.identity[1])

    def symbol_select(self, _symbol, _enabled):
        return True

    def symbol_info_tick(self, symbol):
        self.tick_calls.append(symbol)
        value = self.ticks_by_symbol.get(symbol)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, AdvancingTick):
            read_index = self.tick_read_counts.get(symbol, 0)
            self.tick_read_counts[symbol] = read_index + 1
            return value.read(read_index)
        return value

    def copy_rates_range(self, symbol, timeframe, start_utc, end_utc):
        self.rate_calls.append((symbol, timeframe, start_utc, end_utc))
        value = self.rates_by_symbol.get(symbol)
        if isinstance(value, Exception):
            raise value
        return value


class BrokerClockTests(unittest.TestCase):
    def setUp(self):
        sample_seconds = BrokerClock._CALIBRATION_SAMPLE_SECONDS
        BrokerClock._CALIBRATION_SAMPLE_SECONDS = 0
        self.addCleanup(
            setattr,
            BrokerClock,
            "_CALIBRATION_SAMPLE_SECONDS",
            sample_seconds,
        )

    def test_wall_epoch_mode_calibrates_plus_three_without_using_d1_midnight_as_zero(self):
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {"XAUUSD": [{"time": epoch(2026, 7, 22)}]},
            {"XAUUSD": tick(epoch(2026, 7, 22, 15))},
        )
        clock = BrokerClock(mt5)

        self.assertEqual(clock.current_utc_offset(now_utc), 3)
        self.assertEqual(clock.now(now_utc), datetime(2026, 7, 22, 15))
        broker_value = datetime(2026, 7, 22, 16)
        self.assertEqual(
            clock.utc_from_broker_datetime(broker_value),
            datetime(2026, 7, 22, 13, tzinfo=timezone.utc),
        )
        self.assertEqual(
            clock.mt5_timestamp_from_broker_datetime(broker_value),
            epoch(2026, 7, 22, 16),
        )

    def test_true_utc_mode_keeps_d1_utc_offset_and_utc_mt5_timestamp(self):
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {"XAUUSD": [{"time": epoch(2026, 7, 21, 21)}]},
            {"XAUUSD": tick(epoch(2026, 7, 22, 12))},
        )
        clock = BrokerClock(mt5)

        self.assertEqual(clock.current_utc_offset(now_utc), 3)
        broker_value = datetime(2026, 7, 22, 16)
        self.assertEqual(
            clock.mt5_timestamp_from_broker_datetime(broker_value),
            epoch(2026, 7, 22, 13),
        )
        self.assertEqual(
            clock.utc_from_broker_datetime(broker_value),
            datetime(2026, 7, 22, 13, tzinfo=timezone.utc),
        )

    def test_true_utc_mode_never_uses_crypto_daily_open_as_broker_midnight(self):
        now_utc = datetime(2026, 7, 26, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {
                "XAUUSD": None,
                "GBPUSD": None,
                "BTCUSD": [{"time": epoch(2026, 7, 26)}],
            },
            {"BTCUSD": tick(epoch(2026, 7, 26, 12))},
        )

        with self.assertRaises(BrokerClockError):
            BrokerClock(mt5).current_utc_offset(now_utc)

        self.assertFalse(any(call[0] == "BTCUSD" for call in mt5.rate_calls))

    def test_wall_epoch_falls_back_from_xau_to_gbpusd(self):
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {
                "XAUUSD": None,
                "GBPUSD": [{"time": epoch(2026, 7, 22)}],
            },
            {
                "XAUUSD": None,
                "GBPUSD": tick(epoch(2026, 7, 22, 15)),
            },
        )

        self.assertEqual(BrokerClock(mt5).current_utc_offset(now_utc), 3)
        self.assertIn("GBPUSD", mt5.tick_calls)
        self.assertEqual(mt5.rate_calls, [])

    def test_wall_epoch_falls_back_to_btc_when_forex_symbols_are_closed(self):
        now_utc = datetime(2026, 7, 26, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {
                "XAUUSD": None,
                "GBPUSD": None,
                "BTCUSD": [{"time": epoch(2026, 7, 26)}],
            },
            {
                "XAUUSD": None,
                "GBPUSD": None,
                "BTCUSD": tick(epoch(2026, 7, 26, 15)),
            },
        )

        self.assertEqual(BrokerClock(mt5).current_utc_offset(now_utc), 3)
        self.assertIn("BTCUSD", mt5.tick_calls)
        self.assertEqual(mt5.rate_calls, [])

    def test_stale_tick_cannot_calibrate_wall_epoch_mode(self):
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {"XAUUSD": [{"time": epoch(2026, 7, 22)}]},
            {"XAUUSD": tick(epoch(2026, 7, 22, 14, 40))},
        )

        with self.assertRaises(BrokerClockError):
            BrokerClock(mt5).current_utc_offset(now_utc)

    def test_exact_whole_hour_stale_tick_cannot_pose_as_fresh_utc(self):
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {"XAUUSD": [{"time": epoch(2026, 7, 22)}]},
            {"XAUUSD": static_tick(epoch(2026, 7, 22, 12))},
        )

        with self.assertRaises(BrokerClockError):
            BrokerClock(mt5).current_utc_offset(now_utc)

    def test_advancing_symbols_must_agree_on_broker_offset(self):
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {"XAUUSD": [{"time": epoch(2026, 7, 22)}]},
            {
                "XAUUSD": tick(epoch(2026, 7, 22, 15)),
                "GBPUSD": tick(epoch(2026, 7, 23, 2)),
            },
        )

        with self.assertRaises(BrokerClockError):
            BrokerClock(mt5).current_utc_offset(now_utc)

    def test_fails_closed_when_every_calibration_symbol_is_unavailable(self):
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {"XAUUSD": None, "GBPUSD": None, "BTCUSD": None},
            {"XAUUSD": None, "GBPUSD": None, "BTCUSD": None},
        )

        with self.assertRaises(BrokerClockError):
            BrokerClock(mt5).current_utc_offset(now_utc)

    def test_current_offset_and_mode_are_cached_for_same_account_and_utc_day(self):
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {"XAUUSD": [{"time": epoch(2026, 7, 22)}]},
            {"XAUUSD": tick(epoch(2026, 7, 22, 15))},
        )
        clock = BrokerClock(mt5)

        self.assertEqual(clock.current_utc_offset(now_utc), 3)
        first_rate_count = len(mt5.rate_calls)
        first_tick_count = len(mt5.tick_calls)
        self.assertEqual(clock.current_utc_offset(now_utc), 3)
        self.assertEqual(len(mt5.rate_calls), first_rate_count)
        self.assertEqual(len(mt5.tick_calls), first_tick_count)

    def test_verified_offset_survives_restart_when_market_ticks_are_unavailable(self):
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = f"{temp_dir}/broker-clock.json"
            source = FakeMT5(
                {"XAUUSD": [{"time": epoch(2026, 7, 22)}]},
                {"XAUUSD": tick(epoch(2026, 7, 22, 15))},
            )
            self.assertEqual(BrokerClock(source, cache_path=cache_path).current_utc_offset(now_utc), 3)

            restarted = FakeMT5(
                {"XAUUSD": None, "GBPUSD": None, "BTCUSD": None},
                {"XAUUSD": None, "GBPUSD": None, "BTCUSD": None},
            )
            clock = BrokerClock(restarted, cache_path=cache_path)

            self.assertEqual(clock.current_utc_offset(now_utc), 3)
            self.assertEqual(clock.timestamp_mode, "broker_wall")

    def test_exact_day_restart_cache_is_valid_inside_dst_transition_window(self):
        now_utc = datetime(2026, 3, 30, 12, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = f"{temp_dir}/broker-clock.json"
            source = FakeMT5(
                {"XAUUSD": [{"time": epoch(2026, 3, 30)}]},
                {"XAUUSD": tick(epoch(2026, 3, 30, 15))},
            )
            self.assertEqual(BrokerClock(source, cache_path=cache_path).current_utc_offset(now_utc), 3)

            restarted = FakeMT5(
                {"XAUUSD": None, "GBPUSD": None, "BTCUSD": None},
                {"XAUUSD": None, "GBPUSD": None, "BTCUSD": None},
            )
            self.assertEqual(
                BrokerClock(restarted, cache_path=cache_path).current_utc_offset(now_utc),
                3,
            )

    def test_switching_account_invalidates_calibrated_mode_and_offset(self):
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {"XAUUSD": [{"time": epoch(2026, 7, 22)}]},
            {"XAUUSD": tick(epoch(2026, 7, 22, 15))},
        )
        clock = BrokerClock(mt5)
        self.assertEqual(clock.current_utc_offset(now_utc), 3)

        mt5.identity = ("Other", 2)
        mt5.ticks_by_symbol["XAUUSD"] = tick(epoch(2026, 7, 22, 14))
        self.assertEqual(clock.current_utc_offset(now_utc), 2)

    def test_terminal_disconnect_never_uses_current_cache_as_live_clock(self):
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {"XAUUSD": [{"time": epoch(2026, 7, 22)}]},
            {"XAUUSD": tick(epoch(2026, 7, 22, 15))},
        )
        clock = BrokerClock(mt5)
        self.assertEqual(clock.current_utc_offset(now_utc), 3)
        mt5.connected = False

        with self.assertRaises(BrokerClockError):
            clock.current_utc_offset(now_utc)

    def test_true_utc_mode_keeps_date_specific_dst_offsets(self):
        now_utc = datetime(2026, 3, 30, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {
                "XAUUSD": [
                    {"time": epoch(2026, 3, 26, 22)},
                    {"time": epoch(2026, 3, 29, 21)},
                ]
            },
            {"XAUUSD": tick(epoch(2026, 3, 30, 12))},
        )
        clock = BrokerClock(mt5)

        self.assertEqual(clock.current_utc_offset(now_utc), 3)
        self.assertEqual(clock.utc_offset_for_date(date(2026, 3, 27)), 2)
        self.assertEqual(clock.utc_offset_for_date(date(2026, 3, 30)), 3)

    def test_wall_epoch_extrapolates_stable_offset_within_45_days(self):
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        wall_rates = [
            {"time": int(datetime.combine(date(2026, 6, 10) + timedelta(days=index), datetime.min.time(), timezone.utc).timestamp())}
            for index in range(43)
        ]
        mt5 = FakeMT5(
            {"XAUUSD": wall_rates},
            {"XAUUSD": tick(epoch(2026, 7, 22, 15))},
        )
        clock = BrokerClock(mt5)

        self.assertEqual(clock.current_utc_offset(now_utc), 3)
        self.assertEqual(clock.utc_offset_for_date(date(2026, 6, 10)), 3)
        self.assertEqual(
            clock.utc_from_broker_datetime(datetime(2026, 6, 10, 16)),
            datetime(2026, 6, 10, 13, tzinfo=timezone.utc),
        )

    def test_inferred_offsets_cannot_leapfrog_past_verified_45_day_anchor(self):
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {"XAUUSD": [{"time": epoch(2026, 7, 22)}]},
            {"XAUUSD": tick(epoch(2026, 7, 22, 15))},
        )
        clock = BrokerClock(mt5)

        self.assertEqual(clock.current_utc_offset(now_utc), 3)
        self.assertEqual(clock.utc_offset_for_date(date(2026, 6, 10)), 3)
        with self.assertRaises(BrokerClockError):
            clock.utc_offset_for_date(date(2026, 4, 27))

    def test_cache_read_modify_write_preserves_other_writer_dates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = f"{temp_dir}/broker-clock.json"
            first_mt5 = FakeMT5(
                {"XAUUSD": [{"time": epoch(2026, 7, 21)}]},
                {"XAUUSD": tick(epoch(2026, 7, 21, 15))},
            )
            second_mt5 = FakeMT5(
                {"XAUUSD": [{"time": epoch(2026, 7, 22)}]},
                {"XAUUSD": tick(epoch(2026, 7, 22, 15))},
            )
            first_clock = BrokerClock(first_mt5, cache_path=cache_path)
            second_clock = BrokerClock(second_mt5, cache_path=cache_path)
            second_clock._ensure_terminal_connection()

            self.assertEqual(
                first_clock.current_utc_offset(datetime(2026, 7, 21, 12, tzinfo=timezone.utc)),
                3,
            )
            self.assertEqual(
                second_clock.current_utc_offset(datetime(2026, 7, 22, 12, tzinfo=timezone.utc)),
                3,
            )

            with open(cache_path, "r", encoding="utf-8") as cache_file:
                profile = next(iter(json.load(cache_file)["profiles"].values()))
            self.assertEqual(
                set(profile["verified_dates"]),
                {"2026-07-21", "2026-07-22"},
            )

    def test_wall_epoch_does_not_extrapolate_across_dst_uncertainty(self):
        now_utc = datetime(2026, 3, 30, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {
                "XAUUSD": [
                    {"time": epoch(2026, 3, 27)},
                    {"time": epoch(2026, 3, 30)},
                ]
            },
            {"XAUUSD": tick(epoch(2026, 3, 30, 15))},
        )
        clock = BrokerClock(mt5)
        self.assertEqual(clock.current_utc_offset(now_utc), 3)

        with self.assertRaises(BrokerClockError):
            clock.utc_offset_for_date(date(2026, 3, 27))

    def test_rejects_true_utc_multi_hour_offset_change(self):
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        mt5 = FakeMT5(
            {
                "XAUUSD": [
                    {"time": epoch(2026, 7, 20, 22)},
                    {"time": epoch(2026, 7, 21, 20)},
                ],
            },
            {"XAUUSD": tick(epoch(2026, 7, 22, 12))},
        )

        with self.assertRaises(BrokerClockError):
            BrokerClock(mt5).current_utc_offset(now_utc)


if __name__ == "__main__":
    unittest.main()
