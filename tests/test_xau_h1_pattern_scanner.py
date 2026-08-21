# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from domain.file_lock import FileLock
from domain.xau_h1_pattern_scanner import (
    PATTERN_KIND_SW2,
    PATTERN_KIND_SW3_NORMAL,
    PATTERN_KIND_SW3_PURE,
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


def all_rates(directions="GGT", day=20, start_hour=1):
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


def test_target_mapping_uses_own_source_plus_gbpusd_base_for_cad_jpy():
    assert scanner_base_for_target("XAUUSD") == "AUDUSD"
    assert base_symbol_for_target("XAUUSD") == "GBPUSD"
    for base in ("EURUSD", "AUDUSD"):
        assert scanner_base_for_target(base) == "GBPUSD"
        assert base_symbol_for_target(base) == base
    for base in ("USDCAD", "USDJPY"):
        assert scanner_base_for_target(base) == base
        assert base_symbol_for_target(base) == "GBPUSD"


def test_source_scanner_has_sw2_pure_sw3_and_normal_sw3_only():
    h3 = FakeClock(datetime(2026, 8, 20, 3, 0))
    sw2 = find_h1_pattern_matches(rates_for(20, "GT"), h3.now(), h3.broker_datetime_from_mt5_timestamp)
    assert [(m.slot_hour, m.pattern_text, m.pattern_kind) for m in sw2] == [(3, "T G", PATTERN_KIND_SW2)]

    h4 = FakeClock(datetime(2026, 8, 20, 4, 0))
    tgg = find_h1_pattern_matches(rates_for(20, "GGT"), h4.now(), h4.broker_datetime_from_mt5_timestamp)
    gtt = find_h1_pattern_matches(rates_for(20, "TTG"), h4.now(), h4.broker_datetime_from_mt5_timestamp)
    ttt = find_h1_pattern_matches(rates_for(20, "TTT"), h4.now(), h4.broker_datetime_from_mt5_timestamp)
    tgt = find_h1_pattern_matches(rates_for(20, "TGT"), h4.now(), h4.broker_datetime_from_mt5_timestamp)
    assert [(m.pattern_text, m.pattern_kind) for m in tgg if m.slot_hour == 4] == [("T G G", PATTERN_KIND_SW3_PURE)]
    assert [(m.pattern_text, m.pattern_kind) for m in gtt if m.slot_hour == 4] == [("G T T", PATTERN_KIND_SW3_PURE)]
    assert [(m.pattern_text, m.pattern_kind) for m in ttt if m.slot_hour == 4] == [("T T T", PATTERN_KIND_SW3_NORMAL)]
    assert not [m for m in tgt if m.slot_hour == 4]


def test_sw2_is_h03_only():
    clock = FakeClock(datetime(2026, 8, 20, 4, 0))
    matches = find_h1_pattern_matches(rates_for(20, "GGT"), clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert not any(match.slot_hour == 4 and match.pattern_kind == PATTERN_KIND_SW2 for match in matches)


def test_normal_sw3_guard_skips_current_slot_after_run_reaches_four_or_more():
    clock = FakeClock(datetime(2026, 8, 20, 5, 0))
    t4 = find_h1_pattern_matches(rates_for(20, "TTTT"), clock.now(), clock.broker_datetime_from_mt5_timestamp)
    g4 = find_h1_pattern_matches(rates_for(20, "GGGG"), clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert not [m for m in t4 if m.slot_hour == 5]
    assert not [m for m in g4 if m.slot_hour == 5]


def test_xau_eur_aud_keep_sw2_reverse_sw3_while_cad_jpy_reverse_sw2_follow_sw3():
    assert signal_from_h1_direction("T") == "BUY"
    assert signal_from_h1_direction("G") == "SELL"
    for base in ("XAUUSD", "EURUSD", "AUDUSD"):
        assert signal_from_pattern_base(base, "BUY", PATTERN_KIND_SW2) == "BUY"
        assert signal_from_pattern_base(base, "SELL", PATTERN_KIND_SW2) == "SELL"
        for kind in (PATTERN_KIND_SW3_PURE, PATTERN_KIND_SW3_NORMAL):
            assert signal_from_pattern_base(base, "BUY", kind) == "SELL"
            assert signal_from_pattern_base(base, "SELL", kind) == "BUY"
    for base in ("USDCAD", "USDJPY"):
        assert signal_from_pattern_base(base, "BUY", PATTERN_KIND_SW2) == "SELL"
        assert signal_from_pattern_base(base, "SELL", PATTERN_KIND_SW2) == "BUY"
        for kind in (PATTERN_KIND_SW3_PURE, PATTERN_KIND_SW3_NORMAL):
            assert signal_from_pattern_base(base, "BUY", kind) == "BUY"
            assert signal_from_pattern_base(base, "SELL", kind) == "SELL"


def test_pure_sw3_two_slots_later_is_skipped_and_tracking_resets():
    h6 = FakeClock(datetime(2026, 8, 20, 6, 0))
    matches = [
        match for match in find_h1_pattern_matches(rates_for(20, "GGTTG"), h6.now(), h6.broker_datetime_from_mt5_timestamp)
        if match.pattern_kind == PATTERN_KIND_SW3_PURE
    ]
    assert [(match.slot_hour, match.pattern_text) for match in matches] == [(4, "T G G")]

    h8 = FakeClock(datetime(2026, 8, 20, 8, 0))
    reset_matches = [
        match for match in find_h1_pattern_matches(rates_for(20, "GGTTGGT"), h8.now(), h8.broker_datetime_from_mt5_timestamp)
        if match.pattern_kind == PATTERN_KIND_SW3_PURE
    ]
    assert [(match.slot_hour, match.pattern_text) for match in reset_matches] == [(4, "T G G"), (8, "T G G")]

    shifted = [
        match for match in find_h1_pattern_matches(rates_for(20, "GGTTG", start_hour=3), h8.now(), h8.broker_datetime_from_mt5_timestamp)
        if match.pattern_kind == PATTERN_KIND_SW3_PURE
    ]
    assert [(match.slot_hour, match.pattern_text) for match in shifted] == [(6, "T G G")]


def test_xau_sw2_uses_audusd_source_and_keeps_gbpusd_base(tmp_path):
    sent: list[str] = []
    subject = make_scanner(tmp_path, FakeMT5(all_rates("GT")), FakeClock(datetime(2026, 8, 20, 3, 0)), sent)
    try:
        subject.scan_once()
        xau = next(message for message in sent if message.startswith("🔔 XAUUSD") and "Mốc scan: H03" in message)
        assert "Pattern nguồn: T G" in xau
        assert "Nhóm nguồn: SW 2 cây" in xau
        assert "Base H1: GBPUSD H02=T → BUY" in xau
        assert "Logic nguồn: giữ nguyên GBPUSD H1" in xau
        assert "Signal XAUUSD H1: BUY" in xau
    finally:
        subject.close()


def test_xau_pure_sw3_reverses_gbpusd_base_without_postcheck(tmp_path):
    rates = all_rates("TGT")
    rates["AUDUSD.a"] = rates_for(20, "GGT")
    rates["GBPUSD+"] = rates_for(20, "TTT")
    sent: list[str] = []
    subject = make_scanner(tmp_path, FakeMT5(rates), FakeClock(datetime(2026, 8, 20, 4, 0)), sent)
    try:
        subject.scan_once()
        xau = next(message for message in sent if message.startswith("🔔 XAUUSD") and "Mốc scan: H04" in message)
        assert "Pattern nguồn: T G G" in xau
        assert "Nhóm nguồn: /!\\ SW 3 cây thuần" in xau
        assert "Base H1: GBPUSD H03=T → BUY" in xau
        assert "Logic nguồn: đảo GBPUSD H1" in xau
        assert "Signal XAUUSD H1: SELL" in xau
        assert "Hậu kiểm" not in xau
    finally:
        subject.close()


def test_normal_sw3_reverses_own_base_for_other_symbol(tmp_path):
    rates = all_rates("TGT")
    rates["GBPUSD+"] = rates_for(20, "TTT")
    rates["EURUSD+"] = rates_for(20, "GGG")
    sent: list[str] = []
    subject = make_scanner(tmp_path, FakeMT5(rates), FakeClock(datetime(2026, 8, 20, 4, 0)), sent)
    try:
        subject.scan_once()
        eur = next(message for message in sent if message.startswith("🔔 EURUSD") and "Mốc scan: H04" in message)
        assert "Pattern nguồn: T T T" in eur
        assert "Nhóm nguồn: SW 3 cây thường" in eur
        assert "Base H1: EURUSD H03=G → SELL" in eur
        assert "Logic nguồn: đảo EURUSD H1" in eur
        assert "Signal EURUSD H1: BUY" in eur
    finally:
        subject.close()


def test_usdcad_uses_own_source_gbpusd_base_and_target_specific_direction_rules(tmp_path):
    rates = all_rates("TGT")
    rates["USDCAD.pro"] = rates_for(20, "GGT")
    rates["GBPUSD+"] = rates_for(20, "TTT")
    sent: list[str] = []
    subject = make_scanner(tmp_path, FakeMT5(rates), FakeClock(datetime(2026, 8, 20, 4, 0)), sent)
    try:
        subject.scan_once()
        cad = next(message for message in sent if message.startswith("🔔 USDCAD") and "Mốc scan: H04" in message)
        assert "Scanner pattern: USDCAD (USDCAD.pro)" in cad
        assert "Pattern nguồn: T G G" in cad
        assert "Base H1: GBPUSD H03=T → BUY" in cad
        assert "Logic nguồn: giữ nguyên GBPUSD H1" in cad
        assert "Signal USDCAD H1: BUY" in cad
    finally:
        subject.close()


def test_repeated_pure_sw3_two_slots_later_is_not_sent(tmp_path):
    rates = all_rates("GGTTG")
    rates["AUDUSD.a"] = rates_for(20, "GGTTG")
    sent: list[str] = []
    subject = make_scanner(tmp_path, FakeMT5(rates), FakeClock(datetime(2026, 8, 20, 6, 0)), sent)
    try:
        subject.scan_once()
        assert any(message.startswith("🔔 XAUUSD") and "Mốc scan: H04" in message for message in sent)
        assert not any(message.startswith("🔔 XAUUSD") and "Mốc scan: H06" in message for message in sent)
    finally:
        subject.close()


def test_local_fallback_reads_only_pattern_sources_and_required_base_h1(tmp_path):
    mt5 = FakeMT5(all_rates("GGT"))
    subject = make_scanner(tmp_path, mt5, FakeClock(datetime(2026, 8, 20, 4, 0)), [])
    try:
        subject.scan_once()
        assert {call[0] for call in mt5.rate_calls} == {"GBPUSD+", "AUDUSD.a", "EURUSD+", "USDCAD.pro", "USDJPYraw"}
    finally:
        subject.close()


def test_v6_state_migrates_to_v7_suppression_without_replaying_old_slots(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "version": 6,
        "days": {"2026-08-20": {"symbols": {"XAUUSD": {"alerts": [{"slotHour": 4, "pattern": "T G G"}]}}}},
    }), encoding="utf-8")
    sent: list[str] = []
    subject = make_scanner(tmp_path, FakeMT5(all_rates("GGTTG")), FakeClock(datetime(2026, 8, 20, 6, 0)), sent)
    try:
        subject.scan_once()
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        assert saved["version"] == 7
        assert saved["days"]["2026-08-20"]["suppressedThroughHour"] == 4
        assert all("Mốc scan: H04" not in message for message in sent)
    finally:
        subject.close()


def test_state_survives_restart_and_does_not_replay_delivered_slots(tmp_path):
    rows = all_rates("GGT")
    sent: list[str] = []
    first = make_scanner(tmp_path, FakeMT5(rows), FakeClock(datetime(2026, 8, 20, 4, 0)), sent)
    first.scan_once()
    first.close()
    before = len(sent)
    second = make_scanner(tmp_path, FakeMT5(rows), FakeClock(datetime(2026, 8, 20, 4, 10)), sent)
    try:
        assert second.scan_once() == 0
        assert len(sent) == before
    finally:
        second.close()


def test_public_feed_callback_omits_skipped_pure_and_repeat_metadata(tmp_path):
    published = []
    rows = all_rates("GGTTG")
    subject = make_scanner(
        tmp_path,
        FakeMT5(rows),
        FakeClock(datetime(2026, 8, 20, 6, 0)),
        [],
        publish_state=lambda state, profile: published.append((json.loads(json.dumps(state)), profile)),
    )
    try:
        subject.scan_once()
        xau_alerts = published[-1][0]["days"]["2026-08-20"]["symbols"]["XAUUSD"]["alerts"]
        assert any(row["slotHour"] == 4 and row["patternKind"] == PATTERN_KIND_SW3_PURE for row in xau_alerts)
        assert not any(row["slotHour"] == 6 for row in xau_alerts)
        assert all("previousPureSlot" not in row for row in xau_alerts)
        assert all("postCheckApplied" not in row for row in xau_alerts)
        assert all("sourceSignal" not in row for row in xau_alerts)
    finally:
        subject.close()


def test_failed_telegram_does_not_advance_state(tmp_path):
    attempts = []
    subject = make_scanner(
        tmp_path,
        FakeMT5(all_rates("GGT")),
        FakeClock(datetime(2026, 8, 20, 4, 0)),
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
        "version": 7,
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
    rates = all_rates("GGT")
    clock = FakeClock(datetime(2026, 8, 20, 4, 0))
    first = make_scanner(tmp_path, FakeMT5(rates), clock, [], lock_factory=FileLock, profile="Vantage")
    second = make_scanner(tmp_path, FakeMT5(rates), clock, [], lock_factory=FileLock, profile="VantageDemo")
    try:
        assert first.scan_once() > 0
        assert second.scan_once() == 0
        assert not second.is_owner
    finally:
        first.close()
    try:
        second.scan_once()
        assert second.is_owner
    finally:
        second.close()
