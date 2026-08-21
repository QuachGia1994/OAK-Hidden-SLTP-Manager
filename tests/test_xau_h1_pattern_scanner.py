# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from domain.file_lock import FileLock
from domain.xau_h1_pattern_scanner import (
    PATTERN_KIND_SW2,
    PATTERN_KIND_SW3_ALTERNATING,
    PATTERN_KIND_SW3_PURE,
    PATTERN_KIND_SW4_ALTERNATING,
    MultiSymbolH1PatternScanner,
    base_symbol_for_target,
    find_h1_pattern_matches,
    resolve_symbol_variant,
    resolve_target_symbols,
    scanner_base_for_target,
    signal_from_h1_direction,
    signal_from_pattern_base,
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

    def __init__(self, rates_by_symbol=None, symbols=None):
        self.rates_by_symbol = rates_by_symbol or {}
        self.symbol_rows = symbols or target_symbols()
        self.selected = []
        self.rate_calls = []

    def symbols_get(self):
        return self.symbol_rows

    def symbol_select(self, symbol, enabled):
        self.selected.append((symbol, enabled))
        return True

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        self.rate_calls.append((symbol, timeframe, start_pos, count))
        return self.rates_by_symbol.get(symbol, [])


def rate(day: int, hour: int, direction: str):
    opened = datetime(2026, 8, day, hour, tzinfo=timezone.utc)
    return {
        "time": int(opened.timestamp()),
        "open": 100.0,
        "close": 101.0 if direction == "T" else 99.0,
    }


def rates_for(day: int, directions_oldest_to_newest: str, start_hour: int = 1):
    return [rate(day, start_hour + index, direction) for index, direction in enumerate(directions_oldest_to_newest)]


def target_symbols():
    return [
        SimpleNamespace(name="XAUUSDm", visible=True),
        SimpleNamespace(name="EURUSD+", visible=True),
        SimpleNamespace(name="AUDUSD.a", visible=True),
        SimpleNamespace(name="USDCAD.pro", visible=True),
        SimpleNamespace(name="USDJPYraw", visible=True),
        SimpleNamespace(name="GBPUSD+", visible=True),
    ]


def all_rates(directions="GT", day=20, start_hour=1):
    rows = rates_for(day, directions, start_hour=start_hour)
    return {
        "GBPUSD+": rows,
        "AUDUSD.a": rows,
        "EURUSD+": rows,
        "USDCAD.pro": rows,
        "USDJPYraw": rows,
        "XAUUSDm": rows,
    }


def make_scanner(
    tmp_path: Path,
    mt5: FakeMT5,
    clock: FakeClock,
    sent: list[str],
    *,
    notify=None,
    publish_state=None,
    lock_factory=AllowLock,
    profile="Vantage",
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    return MultiSymbolH1PatternScanner(
        mt5,
        notify=notify or (lambda message: sent.append(message) or True),
        log=lambda _message: None,
        profile_name=profile,
        state_path=tmp_path / "state.json",
        owner_lock_path=tmp_path / "owner.lock",
        clock_factory=lambda **_kwargs: clock,
        lock_factory=lock_factory,
        publish_state=publish_state,
    )


def test_resolver_accepts_suffixes_for_all_targets_and_rejects_prefixes():
    symbols = target_symbols() + [SimpleNamespace(name="mXAUUSD", visible=True)]
    assert resolve_symbol_variant("XAUUSD", symbols) == "XAUUSDm"
    assert resolve_target_symbols(symbols) == {
        "XAUUSD": "XAUUSDm",
        "EURUSD": "EURUSD+",
        "AUDUSD": "AUDUSD.a",
        "USDCAD": "USDCAD.pro",
        "USDJPY": "USDJPYraw",
    }
    assert resolve_symbol_variant("GBPUSD", symbols) == "GBPUSD+"


def test_target_mapping_uses_only_audusd_and_gbpusd_as_pattern_scanners():
    assert scanner_base_for_target("XAUUSD") == "AUDUSD"
    assert base_symbol_for_target("XAUUSD") == "GBPUSD"
    for base in ("EURUSD", "AUDUSD", "USDCAD", "USDJPY"):
        assert scanner_base_for_target(base) == "GBPUSD"
        assert base_symbol_for_target(base) == base


def test_scanner_transform_only_pure_sw3_reverses_base():
    assert signal_from_h1_direction("T") == "BUY"
    assert signal_from_h1_direction("G") == "SELL"
    for kind in (PATTERN_KIND_SW2, PATTERN_KIND_SW3_ALTERNATING, PATTERN_KIND_SW4_ALTERNATING):
        assert signal_from_pattern_base("BUY", kind) == "BUY"
        assert signal_from_pattern_base("SELL", kind) == "SELL"
    assert signal_from_pattern_base("BUY", PATTERN_KIND_SW3_PURE) == "SELL"
    assert signal_from_pattern_base("SELL", PATTERN_KIND_SW3_PURE) == "BUY"


def test_sw2_is_available_from_h03():
    clock = FakeClock(datetime(2026, 8, 20, 3, 5))
    matches = find_h1_pattern_matches(rates_for(20, "GT"), clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert [(m.slot_hour, m.pattern_text, m.pattern_kind) for m in matches] == [
        (3, "T G", PATTERN_KIND_SW2),
    ]


def test_pure_sw3_is_only_tgg_or_gtt_and_overrides_embedded_sw2():
    clock = FakeClock(datetime(2026, 8, 20, 4, 5))
    tgg = find_h1_pattern_matches(rates_for(20, "GGT"), clock.now(), clock.broker_datetime_from_mt5_timestamp)
    gtt = find_h1_pattern_matches(rates_for(20, "TTG"), clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert [(m.pattern_text, m.pattern_kind) for m in tgg if m.slot_hour == 4] == [("T G G", PATTERN_KIND_SW3_PURE)]
    assert [(m.pattern_text, m.pattern_kind) for m in gtt if m.slot_hour == 4] == [("G T T", PATTERN_KIND_SW3_PURE)]


def test_alternating_sw4_is_a_real_pattern_and_wins_at_current_slot():
    h4_clock = FakeClock(datetime(2026, 8, 20, 4, 5))
    h4 = find_h1_pattern_matches(rates_for(20, "TGT"), h4_clock.now(), h4_clock.broker_datetime_from_mt5_timestamp)
    assert [(m.pattern_text, m.pattern_kind) for m in h4 if m.slot_hour == 4] == [("T G T", PATTERN_KIND_SW3_ALTERNATING)]

    h5_clock = FakeClock(datetime(2026, 8, 20, 5, 5))
    h5 = find_h1_pattern_matches(rates_for(20, "GTGT"), h5_clock.now(), h5_clock.broker_datetime_from_mt5_timestamp)
    assert [(m.pattern_text, m.pattern_kind) for m in h5 if m.slot_hour == 5] == [("T G T G", PATTERN_KIND_SW4_ALTERNATING)]


def test_sw2_is_never_reused_after_h03():
    clock = FakeClock(datetime(2026, 8, 20, 4, 5))
    matches = find_h1_pattern_matches(rates_for(20, "GGT"), clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert not any(m.slot_hour == 4 and m.pattern_kind == PATTERN_KIND_SW2 for m in matches)


def test_xau_uses_audusd_pattern_plus_gbpusd_base_and_sw2_keeps_base(tmp_path):
    sent: list[str] = []
    subject = make_scanner(
        tmp_path,
        FakeMT5(all_rates("GT")),
        FakeClock(datetime(2026, 8, 20, 3, 5)),
        sent,
    )
    try:
        assert subject.scan_once() == 5
        xau = next(message for message in sent if message.startswith("🔔 XAUUSD"))
        assert "Scanner pattern: AUDUSD (AUDUSD.a)" in xau
        assert "Nhóm scanner: SW 2 cây" in xau
        assert "Base H1: GBPUSD H02=T → BUY" in xau
        assert "Logic: giữ nguyên GBPUSD H1" in xau
        assert "Signal XAUUSD H1: BUY" in xau
    finally:
        subject.close()


def test_xau_alternating_sw3_keeps_gbpusd_base(tmp_path):
    sent: list[str] = []
    subject = make_scanner(
        tmp_path,
        FakeMT5(all_rates("TGT")),
        FakeClock(datetime(2026, 8, 20, 4, 5)),
        sent,
    )
    try:
        subject.scan_once()
        xau_h4 = next(message for message in sent if message.startswith("🔔 XAUUSD") and "Mốc scan: H04" in message)
        assert "Nhóm scanner: SW 3 cây xen kẽ" in xau_h4
        assert "Base H1: GBPUSD H03=T → BUY" in xau_h4
        assert "Logic: giữ nguyên GBPUSD H1" in xau_h4
        assert "Signal XAUUSD H1: BUY" in xau_h4
    finally:
        subject.close()


def test_xau_pure_sw3_reverses_gbpusd_base(tmp_path):
    sent: list[str] = []
    rows = all_rates("GGT")
    subject = make_scanner(
        tmp_path,
        FakeMT5(rows),
        FakeClock(datetime(2026, 8, 20, 4, 5)),
        sent,
    )
    try:
        subject.scan_once()
        xau_h4 = next(message for message in sent if message.startswith("🔔 XAUUSD") and "Mốc scan: H04" in message)
        assert "Scanner pattern: AUDUSD" in xau_h4
        assert "Nhóm scanner: SW 3 cây thuần" in xau_h4
        assert "Base H1: GBPUSD H03=T → BUY" in xau_h4
        assert "Logic: đảo GBPUSD H1" in xau_h4
        assert "Signal XAUUSD H1: SELL" in xau_h4
    finally:
        subject.close()


def test_other_symbol_uses_gbpusd_pattern_plus_its_own_base(tmp_path):
    rates = all_rates("GGT")
    # EURUSD H3=G while GBPUSD scanner H3..H1 = TGG (pure -> reverse).
    rates["EURUSD+"] = rates_for(20, "GGG")
    sent: list[str] = []
    subject = make_scanner(tmp_path, FakeMT5(rates), FakeClock(datetime(2026, 8, 20, 4, 5)), sent)
    try:
        subject.scan_once()
        eur = next(message for message in sent if message.startswith("🔔 EURUSD") and "Mốc scan: H04" in message)
        assert "Scanner pattern: GBPUSD (GBPUSD+)" in eur
        assert "Base H1: EURUSD H03=G → SELL" in eur
        assert "Logic: đảo EURUSD H1" in eur
        assert "Signal EURUSD H1: BUY" in eur
    finally:
        subject.close()


def test_local_fallback_reads_only_pattern_sources_and_required_base_h1(tmp_path):
    mt5 = FakeMT5(all_rates("GT"))
    subject = make_scanner(tmp_path, mt5, FakeClock(datetime(2026, 8, 20, 3, 5)), [])
    try:
        subject.scan_once()
        assert {call[0] for call in mt5.rate_calls} == {"GBPUSD+", "AUDUSD.a", "EURUSD+", "USDCAD.pro", "USDJPYraw"}
    finally:
        subject.close()


def test_v2_state_migrates_to_v6_suppression_without_reinterpreting_old_alerts(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "version": 2,
        "days": {
            "2026-08-20": {
                "symbols": {
                    "XAUUSD": {"alerts": [{"slotHour": 4, "pattern": "T G", "symbol": "XAUUSDm"}]},
                },
            },
        },
    }), encoding="utf-8")
    sent: list[str] = []
    subject = make_scanner(
        tmp_path,
        FakeMT5(all_rates("GTGT")),
        FakeClock(datetime(2026, 8, 20, 5, 5)),
        sent,
    )
    try:
        subject.scan_once()
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        assert saved["version"] == 6
        assert saved["days"]["2026-08-20"]["suppressedThroughHour"] == 4
        assert all("Mốc scan: H03" not in message and "Mốc scan: H04" not in message for message in sent)
    finally:
        subject.close()


def test_missing_target_base_h1_keeps_signal_pending(tmp_path):
    rates = all_rates("GGT", start_hour=14)
    rates["EURUSD+"] = rates_for(20, "GG", start_hour=14)  # H16 missing at slot H17.
    sent: list[str] = []
    subject = make_scanner(
        tmp_path,
        FakeMT5(rates),
        FakeClock(datetime(2026, 8, 20, 17, 30)),
        sent,
    )
    try:
        subject.scan_once()
        assert not any(message.startswith("🔔 EURUSD") and "Mốc scan: H17" in message for message in sent)
    finally:
        subject.close()


def test_state_survives_restart_and_does_not_replay_delivered_slots(tmp_path):
    rows = all_rates("GTGT")
    sent: list[str] = []
    first = make_scanner(tmp_path, FakeMT5(rows), FakeClock(datetime(2026, 8, 20, 5, 5)), sent)
    first.scan_once()
    first.close()
    before = len(sent)

    second = make_scanner(tmp_path, FakeMT5(rows), FakeClock(datetime(2026, 8, 20, 5, 10)), sent)
    try:
        assert second.scan_once() == 0
        assert len(sent) == before
    finally:
        second.close()


def test_public_feed_callback_runs_once_for_unchanged_state(tmp_path):
    published = []
    subject = make_scanner(
        tmp_path,
        FakeMT5(all_rates("GT")),
        FakeClock(datetime(2026, 8, 20, 3, 5)),
        [],
        publish_state=lambda state, profile: published.append((json.loads(json.dumps(state)), profile)),
    )
    try:
        assert subject.scan_once() == 5
        assert len(published) >= 1
        count = len(published)
        assert subject.scan_once() == 0
        assert len(published) == count
        xau = published[-1][0]["days"]["2026-08-20"]["symbols"]["XAUUSD"]["alerts"][0]
        assert xau["scannerBase"] == "AUDUSD"
        assert xau["baseSymbol"] == "GBPUSD"
        assert xau["patternKind"] == PATTERN_KIND_SW2
    finally:
        subject.close()


def test_failed_telegram_does_not_advance_state(tmp_path):
    attempts = []
    subject = make_scanner(
        tmp_path,
        FakeMT5(all_rates("GT")),
        FakeClock(datetime(2026, 8, 20, 3, 5)),
        [],
        notify=lambda message: attempts.append(message) and False,
    )
    try:
        assert subject.scan_once() == 0
        assert attempts
        assert not (tmp_path / "state.json").exists()
    finally:
        subject.close()


def test_after_h17_republishes_state_without_h1_history(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "version": 6,
        "days": {"2026-08-20": {"symbols": {base: {"alerts": []} for base in ("XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY")}}},
    }), encoding="utf-8")
    mt5 = FakeMT5({}, target_symbols())
    published = []
    subject = make_scanner(
        tmp_path,
        mt5,
        FakeClock(datetime(2026, 8, 20, 18, 5)),
        [],
        publish_state=lambda state, profile: published.append((state, profile)),
    )
    try:
        assert subject.scan_once() == 0
        assert published
        assert mt5.rate_calls == []
    finally:
        subject.close()


def test_real_owner_lock_prevents_second_local_scanner(tmp_path):
    rates = all_rates("GT")
    clock = FakeClock(datetime(2026, 8, 20, 3, 5))
    first = make_scanner(tmp_path, FakeMT5(rates), clock, [], lock_factory=FileLock, profile="Vantage")
    second = make_scanner(tmp_path, FakeMT5(rates), clock, [], lock_factory=FileLock, profile="VantageDemo")
    try:
        assert first.scan_once() == 5
        assert second.scan_once() == 0
        assert not second.is_owner
    finally:
        first.close()
    try:
        assert second.scan_once() == 0
        assert second.is_owner
    finally:
        second.close()
