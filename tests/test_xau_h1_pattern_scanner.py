# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from domain.file_lock import FileLock
from domain.xau_h1_pattern_scanner import (
    XauH1PatternScanner,
    find_h1_pattern_matches,
    resolve_xauusd_symbol,
)


class AllowLock:
    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return None


class FakeClock:
    def __init__(self, now_value: datetime):
        self.now_value = now_value

    def now(self):
        return self.now_value

    @staticmethod
    def broker_datetime_from_mt5_timestamp(value: int):
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None)


class FakeMT5:
    TIMEFRAME_H1 = 60

    def __init__(self, rates, symbols=None):
        self.rates = rates
        self.symbol_rows = symbols or [SimpleNamespace(name="XAUUSDm", visible=True)]
        self.selected = []
        self.rate_calls = []

    def symbols_get(self):
        return self.symbol_rows

    def symbol_select(self, symbol, enabled):
        self.selected.append((symbol, enabled))
        return True

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        self.rate_calls.append((symbol, timeframe, start_pos, count))
        return self.rates


def rate(day: int, hour: int, direction: str):
    opened = datetime(2026, 8, day, hour, tzinfo=timezone.utc)
    open_price = 100.0
    close_price = 101.0 if direction == "T" else 99.0
    return {"time": int(opened.timestamp()), "open": open_price, "close": close_price}


def rates_for(day: int, directions: str, start_hour: int = 1):
    return [rate(day, start_hour + index, direction) for index, direction in enumerate(directions)]


def scanner(tmp_path: Path, mt5, clock, sent, lock_factory=AllowLock, profile="Vantage"):
    return XauH1PatternScanner(
        mt5,
        notify=lambda message: sent.append(message) or True,
        log=lambda _message: None,
        profile_name=profile,
        state_path=tmp_path / "state.json",
        owner_lock_path=tmp_path / "owner.lock",
        clock_factory=lambda **_kwargs: clock,
        lock_factory=lock_factory,
    )


def test_resolve_xauusd_symbol_accepts_suffixes_and_prefers_visible_contract():
    symbols = [
        SimpleNamespace(name="EURUSD", visible=True),
        SimpleNamespace(name="XAUUSD.pro", visible=True),
        SimpleNamespace(name="XAUUSDm", visible=True),
        SimpleNamespace(name="XAUUSD", visible=False),
    ]
    assert resolve_xauusd_symbol(symbols) == "XAUUSDm"
    assert resolve_xauusd_symbol([SimpleNamespace(name="XAUUSD+", visible=True)]) == "XAUUSD+"
    assert resolve_xauusd_symbol([SimpleNamespace(name="mXAUUSD", visible=True)]) is None


def test_h4_ignores_h1_and_uses_only_h3_h2_backward():
    clock = FakeClock(datetime(2026, 8, 20, 4, 30))
    rows = [rate(20, 1, "G"), rate(20, 2, "G"), rate(20, 3, "T"), rate(20, 4, "G")]
    matches = find_h1_pattern_matches(rows, clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert [(item.slot_hour, item.pattern_text, item.bar_range_text) for item in matches] == [(4, "T G", "H03→H02")]

    # H1 is explicitly noise at H4; changing it must not affect the result.
    rows[0] = rate(20, 1, "T")
    matches = find_h1_pattern_matches(rows, clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert [(item.slot_hour, item.pattern_text) for item in matches] == [(4, "T G")]


def test_h5_plus_uses_three_most_recent_closed_h1_in_backward_order():
    clock = FakeClock(datetime(2026, 8, 20, 5, 10))
    rows = [rate(20, 1, "T"), rate(20, 2, "G"), rate(20, 3, "G"), rate(20, 4, "T"), rate(20, 5, "G")]
    matches = find_h1_pattern_matches(rows, clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert [(item.slot_hour, item.pattern_text, item.bar_range_text) for item in matches] == [(5, "T G G", "H04→H03→H02")]


def test_scanner_sends_first_and_second_later_match_only(tmp_path):
    rows = rates_for(20, "TGTTG")  # H04=TG, H06=GTT in newest→oldest order
    mt5 = FakeMT5(rows)
    clock = FakeClock(datetime(2026, 8, 20, 7, 15))
    sent = []
    subject = scanner(tmp_path, mt5, clock, sent)
    try:
        assert subject.scan_once() == 2
        assert len(sent) == 2
        assert "PATTERN 1/2" in sent[0] and "Mốc scan: H04" in sent[0] and "Pattern: T G" in sent[0]
        assert "PATTERN 2/2" in sent[1] and "Mốc scan: H06" in sent[1] and "Pattern: G T T" in sent[1]
        assert subject.scan_once() == 0
        assert len(sent) == 2
    finally:
        subject.close()


def test_state_survives_restart_and_daily_quota_resets(tmp_path):
    day20 = rates_for(20, "TGTTG")
    sent = []
    first = scanner(tmp_path, FakeMT5(day20), FakeClock(datetime(2026, 8, 20, 7, 0)), sent)
    assert first.scan_once() == 2
    first.close()

    restarted = scanner(tmp_path, FakeMT5(day20), FakeClock(datetime(2026, 8, 20, 8, 0)), sent)
    assert restarted.scan_once() == 0
    restarted.close()

    day21 = rates_for(21, "TGT")
    next_day = scanner(tmp_path, FakeMT5(day21), FakeClock(datetime(2026, 8, 21, 4, 5)), sent)
    try:
        assert next_day.scan_once() == 1
        assert "Ngày broker: 2026-08-21" in sent[-1]
        assert "PATTERN 1/2" in sent[-1]
    finally:
        next_day.close()


def test_failed_telegram_does_not_advance_persistent_state(tmp_path):
    rows = rates_for(20, "TGT")
    mt5 = FakeMT5(rows)
    clock = FakeClock(datetime(2026, 8, 20, 4, 5))
    attempts = []
    subject = XauH1PatternScanner(
        mt5,
        notify=lambda message: attempts.append(message) and False,
        log=lambda _message: None,
        profile_name="Vantage",
        state_path=tmp_path / "state.json",
        owner_lock_path=tmp_path / "owner.lock",
        clock_factory=lambda **_kwargs: clock,
        lock_factory=AllowLock,
    )
    try:
        assert subject.scan_once() == 0
        assert not (tmp_path / "state.json").exists()
    finally:
        subject.close()

    sent = []
    retry = scanner(tmp_path, FakeMT5(rows), clock, sent)
    try:
        assert retry.scan_once() == 1
        assert len(sent) == 1
    finally:
        retry.close()


def test_corrupt_state_fails_closed_without_telegram(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{broken", encoding="utf-8")
    sent = []
    subject = scanner(
        tmp_path,
        FakeMT5(rates_for(20, "TGT")),
        FakeClock(datetime(2026, 8, 20, 4, 5)),
        sent,
    )
    try:
        assert subject.scan_once() == 0
        assert sent == []
        assert state_path.read_text(encoding="utf-8") == "{broken"
    finally:
        subject.close()


def test_real_owner_lock_prevents_second_worker_and_state_prevents_replay_after_failover(tmp_path):
    rows = rates_for(20, "TGT")
    clock = FakeClock(datetime(2026, 8, 20, 4, 5))
    sent_a = []
    sent_b = []
    first = scanner(tmp_path, FakeMT5(rows), clock, sent_a, lock_factory=FileLock, profile="Vantage")
    second = scanner(tmp_path, FakeMT5(rows), clock, sent_b, lock_factory=FileLock, profile="ICMarkets")
    try:
        assert first.scan_once() == 1
        assert first.is_owner
        assert second.scan_once() == 0
        assert not second.is_owner
        assert sent_b == []
    finally:
        first.close()
    try:
        assert second.scan_once() == 0
        assert second.is_owner
        assert sent_b == []
    finally:
        second.close()


def test_h17_is_last_eligible_scan_slot():
    clock = FakeClock(datetime(2026, 8, 20, 17, 30))
    rows = rates_for(20, "GGT", start_hour=14)  # H17 sees H16→H15→H14 = TGG
    matches = find_h1_pattern_matches(rows, clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert [(item.slot_hour, item.pattern_text, item.bar_range_text) for item in matches] == [(17, "T G G", "H16→H15→H14")]


def test_scanner_stops_after_h17_even_when_daily_alerts_are_missing(tmp_path):
    mt5 = FakeMT5(rates_for(20, "TGT"))
    sent = []
    subject = scanner(tmp_path, mt5, FakeClock(datetime(2026, 8, 20, 18, 1)), sent)
    try:
        assert subject.scan_once() == 0
        assert sent == []
        assert mt5.rate_calls == []
    finally:
        subject.close()
