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
    PATTERN_KIND_SW6_COMBINED,
    MultiSymbolH1PatternScanner,
    find_h1_pattern_matches,
    resolve_symbol_variant,
    resolve_target_symbols,
    resolve_xauusd_symbol,
    signal_from_gbpusd_pattern,
    signal_from_h1_direction,
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
        return self.rates_by_symbol.get(symbol, [])


def rate(day: int, hour: int, direction: str):
    opened = datetime(2026, 8, day, hour, tzinfo=timezone.utc)
    open_price = 100.0
    close_price = 101.0 if direction == "T" else 99.0
    return {"time": int(opened.timestamp()), "open": open_price, "close": close_price}


def rates_for(day: int, directions: str, start_hour: int = 1):
    return [rate(day, start_hour + index, direction) for index, direction in enumerate(directions)]


def scanner(
    tmp_path: Path,
    mt5,
    clock,
    sent,
    lock_factory=AllowLock,
    profile="Vantage",
    notify=None,
    publish_state=None,
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


def target_symbols():
    return [
        SimpleNamespace(name="XAUUSDm", visible=True),
        SimpleNamespace(name="EURUSD+", visible=True),
        SimpleNamespace(name="AUDUSD.a", visible=True),
        SimpleNamespace(name="USDCAD.pro", visible=True),
        SimpleNamespace(name="USDJPYraw", visible=True),
        SimpleNamespace(name="GBPUSD+", visible=True),
    ]


def target_h4_rates(day=20):
    rows = rates_for(day, "TGT")
    return {symbol.name: rows for symbol in target_symbols()}


def test_resolver_accepts_suffixes_for_all_targets_and_rejects_prefixes():
    symbols = target_symbols() + [
        SimpleNamespace(name="mXAUUSD", visible=True),
        SimpleNamespace(name="EURUSD", visible=False),
    ]
    assert resolve_symbol_variant("XAUUSD", symbols) == "XAUUSDm"
    assert resolve_xauusd_symbol(symbols) == "XAUUSDm"
    assert resolve_target_symbols(symbols) == {
        "XAUUSD": "XAUUSDm",
        "EURUSD": "EURUSD+",
        "AUDUSD": "AUDUSD.a",
        "USDCAD": "USDCAD.pro",
        "USDJPY": "USDJPYraw",
    }
    assert resolve_symbol_variant("GBPUSD", symbols) == "GBPUSD+"


def test_gbpusd_signal_is_directly_the_first_backward_h1_candle():
    assert signal_from_h1_direction("T") == "BUY"
    assert signal_from_h1_direction("G") == "SELL"


def test_target_signal_rule_is_pattern_local_only():
    for reverse_kind in (PATTERN_KIND_SW2, PATTERN_KIND_SW3_ALTERNATING, PATTERN_KIND_SW6_COMBINED):
        assert signal_from_gbpusd_pattern("BUY", reverse_kind) == "SELL"
        assert signal_from_gbpusd_pattern("SELL", reverse_kind) == "BUY"
    assert signal_from_gbpusd_pattern("BUY", PATTERN_KIND_SW3_PURE) == "BUY"
    assert signal_from_gbpusd_pattern("SELL", PATTERN_KIND_SW3_PURE) == "SELL"


def test_xau_first_slot_h4_is_two_candle_sw():
    clock = FakeClock(datetime(2026, 8, 20, 4, 30))
    rows = rates_for(20, "TGT")
    matches = find_h1_pattern_matches(rows, clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert [(m.slot_hour, m.pattern_text, m.pattern_kind, m.bar_range_text) for m in matches] == [
        (4, "T G", PATTERN_KIND_SW2, "H03→H02")
    ]


def test_fx_first_slot_h3_is_two_candle_sw_while_xau_waits_h4():
    clock = FakeClock(datetime(2026, 8, 20, 3, 10))
    rows = [rate(20, 1, "G"), rate(20, 2, "T")]
    fx = find_h1_pattern_matches(rows, clock.now(), clock.broker_datetime_from_mt5_timestamp, first_scan_hour=3)
    xau = find_h1_pattern_matches(rows, clock.now(), clock.broker_datetime_from_mt5_timestamp, first_scan_hour=4)
    assert [(m.slot_hour, m.pattern_text, m.pattern_kind) for m in fx] == [(3, "T G", PATTERN_KIND_SW2)]
    assert xau == []


def test_three_candle_pure_sw_matches_tgg_and_gtt():
    clock = FakeClock(datetime(2026, 8, 20, 5, 10))
    tgg = find_h1_pattern_matches(rates_for(20, "TGGT"), clock.now(), clock.broker_datetime_from_mt5_timestamp)
    gtt = find_h1_pattern_matches(rates_for(20, "GTTG"), clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert any((m.slot_hour, m.pattern_text, m.pattern_kind) == (5, "T G G", PATTERN_KIND_SW3_PURE) for m in tgg)
    assert any((m.slot_hour, m.pattern_text, m.pattern_kind) == (5, "G T T", PATTERN_KIND_SW3_PURE) for m in gtt)


def test_exact_three_candle_alternating_matches_when_fourth_does_not_continue_alternation():
    clock = FakeClock(datetime(2026, 8, 20, 5, 10))
    rows = rates_for(20, "TTGT")  # H04→H03→H02 = TGT; H01=T, so four = TGTT.
    matches = find_h1_pattern_matches(rows, clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert any((m.slot_hour, m.pattern_text, m.pattern_kind) == (5, "T G T", PATTERN_KIND_SW3_ALTERNATING) for m in matches)


def test_four_candle_tgtg_or_gtgt_is_not_counted_as_three_candle_alternating():
    clock = FakeClock(datetime(2026, 8, 20, 5, 10))
    rows = rates_for(20, "GTGT")  # newest→oldest H04..H01 = TGTG.
    matches = find_h1_pattern_matches(rows, clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert not any(m.slot_hour == 5 and m.pattern_kind == PATTERN_KIND_SW3_ALTERNATING for m in matches)


def test_xau_h8_combines_two_pure_three_candle_groups_and_overrides_embedded_pure_match():
    clock = FakeClock(datetime(2026, 8, 20, 8, 10))
    rows = rates_for(20, "TTTGGGT")  # H07..H02 = TGG | GTT.
    matches = find_h1_pattern_matches(rows, clock.now(), clock.broker_datetime_from_mt5_timestamp)
    h8 = [m for m in matches if m.slot_hour == 8]
    assert len(h8) == 1
    assert h8[0].pattern_text == "T G G G T T"
    assert h8[0].pattern_kind == PATTERN_KIND_SW6_COMBINED
    assert h8[0].bar_range_text == "H07→H06→H05→H04→H03→H02"


def test_fx_h7_is_earliest_combined_two_pure_three_candle_groups():
    clock = FakeClock(datetime(2026, 8, 20, 7, 10))
    rows = rates_for(20, "TTGGGT")  # H06..H01 = TGG | GTT.
    matches = find_h1_pattern_matches(rows, clock.now(), clock.broker_datetime_from_mt5_timestamp, first_scan_hour=3)
    h7 = [m for m in matches if m.slot_hour == 7]
    assert len(h7) == 1
    assert h7[0].pattern_kind == PATTERN_KIND_SW6_COMBINED


def test_two_candle_alert_reverses_gbpusd_and_has_no_day_classification(tmp_path):
    symbols = [SimpleNamespace(name="XAUUSD+", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    mt5 = FakeMT5({"XAUUSD+": rates_for(20, "TGT"), "GBPUSD+": rates_for(20, "TGT")}, symbols)
    sent = []
    subject = scanner(tmp_path, mt5, FakeClock(datetime(2026, 8, 20, 4, 5)), sent)
    try:
        assert subject.scan_once() == 1
        assert "Nhóm pattern: SW 2 cây" in sent[0]
        assert "Signal GBPUSD H1: BUY | Base H03=T" in sent[0]
        assert "Logic Signal XAUUSD: đảo GBPUSD H1" in sent[0]
        assert "Signal XAUUSD H1: SELL" in sent[0]
        assert "Phân loại ngày" not in sent[0]
        state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        symbol_state = state["days"]["2026-08-20"]["symbols"]["XAUUSD"]
        assert "dayType" not in symbol_state
        assert symbol_state["alerts"][0]["patternKind"] == PATTERN_KIND_SW2
        assert symbol_state["alerts"][0]["symbolH1Signal"] == "SELL"
    finally:
        subject.close()


def test_three_pure_follows_gbpusd_but_alternating_reverses(tmp_path):
    symbols = [SimpleNamespace(name="XAUUSD+", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]

    pure_sent = []
    pure = scanner(
        tmp_path / "pure",
        FakeMT5({"XAUUSD+": rates_for(20, "TGGT"), "GBPUSD+": rates_for(20, "TGGT")}, symbols),
        FakeClock(datetime(2026, 8, 20, 5, 5)),
        pure_sent,
    )
    try:
        assert pure.scan_once() == 1
        assert "Nhóm pattern: SW 3 cây thuần" in pure_sent[0]
        assert "Signal GBPUSD H1: BUY" in pure_sent[0]
        assert "Signal XAUUSD H1: BUY" in pure_sent[0]
    finally:
        pure.close()

    alt_sent = []
    alt = scanner(
        tmp_path / "alt",
        FakeMT5({"XAUUSD+": rates_for(20, "TTGT"), "GBPUSD+": rates_for(20, "TTGT")}, symbols),
        FakeClock(datetime(2026, 8, 20, 5, 5)),
        alt_sent,
    )
    try:
        assert alt.scan_once() == 2  # H04 SW2 + H05 exact alternating.
        h5 = next(message for message in alt_sent if "Mốc scan: H05" in message)
        assert "Nhóm pattern: SW 3 cây xen kẽ" in h5
        assert "Signal GBPUSD H1: BUY | Base H04=T" in h5
        assert "Signal XAUUSD H1: SELL" in h5
    finally:
        alt.close()


def test_combined_six_reverses_gbpusd(tmp_path):
    symbols = [SimpleNamespace(name="XAUUSD+", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    rows = rates_for(20, "TTTGGGT")
    sent = []
    subject = scanner(tmp_path, FakeMT5({"XAUUSD+": rows, "GBPUSD+": rows}, symbols), FakeClock(datetime(2026, 8, 20, 8, 5)), sent)
    try:
        assert subject.scan_once() >= 1
        h8 = next(message for message in sent if "Mốc scan: H08" in message)
        assert "Nhóm pattern: SW ghép 2×3 cây thuần" in h8
        assert "Logic Signal XAUUSD: đảo GBPUSD H1" in h8
    finally:
        subject.close()


def test_scanner_scans_all_five_target_symbols_with_suffixes(tmp_path):
    mt5 = FakeMT5(target_h4_rates(), target_symbols())
    sent = []
    subject = scanner(tmp_path, mt5, FakeClock(datetime(2026, 8, 20, 4, 5)), sent)
    try:
        assert subject.scan_once() == 9
        assert subject.symbols == {
            "XAUUSD": "XAUUSDm",
            "EURUSD": "EURUSD+",
            "AUDUSD": "AUDUSD.a",
            "USDCAD": "USDCAD.pro",
            "USDJPY": "USDJPYraw",
        }
        assert any("XAUUSD H1 PATTERN" in message and "Mốc scan: H04" in message for message in sent)
        for base in ("EURUSD", "AUDUSD", "USDCAD", "USDJPY"):
            assert any(f"{base} H1 PATTERN" in message and "Mốc scan: H03" in message for message in sent)
            assert any(f"{base} H1 PATTERN" in message and "Mốc scan: H04" in message and "SW 3 cây xen kẽ" in message for message in sent)
        assert all("Phân loại ngày" not in message for message in sent)
    finally:
        subject.close()


def test_new_pattern_catches_up_earlier_undelivered_slot_even_when_later_slot_is_already_stored(tmp_path):
    state_path = tmp_path / "state.json"
    existing = {
        "version": 2,
        "days": {
            "2026-08-20": {
                "symbols": {
                    "XAUUSD": {
                        "alerts": [
                            {
                                "slotHour": 4,
                                "pattern": "G T",
                                "patternKind": PATTERN_KIND_SW2,
                                "bars": [],
                                "symbol": "XAUUSD+",
                                "profile": "Vantage",
                                "symbolH1Signal": "SELL",
                                "gbpusdH1Signal": "BUY",
                            },
                            {
                                "slotHour": 7,
                                "pattern": "G T T",
                                "patternKind": PATTERN_KIND_SW3_PURE,
                                "bars": [],
                                "symbol": "XAUUSD+",
                                "profile": "Vantage",
                                "symbolH1Signal": "BUY",
                                "gbpusdH1Signal": "BUY",
                            },
                        ],
                    },
                },
            },
        },
    }
    state_path.write_text(json.dumps(existing), encoding="utf-8")
    symbols = [SimpleNamespace(name="XAUUSD+", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    rows = rates_for(20, "TTGTTG")  # H05=TGT new alternating; H07=GTT old delivered.
    sent = []
    subject = scanner(tmp_path, FakeMT5({"XAUUSD+": rows, "GBPUSD+": rows}, symbols), FakeClock(datetime(2026, 8, 20, 7, 5)), sent)
    try:
        assert subject.scan_once() == 1
        assert len(sent) == 1
        assert "Mốc scan: H05" in sent[0]
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        alerts = saved["days"]["2026-08-20"]["symbols"]["XAUUSD"]["alerts"]
        assert [item["slotHour"] for item in alerts] == [4, 5, 7]
    finally:
        subject.close()


def test_legacy_day_classification_is_removed_without_replaying_old_alert(tmp_path):
    state_path = tmp_path / "state.json"
    existing = {
        "version": 2,
        "days": {
            "2026-08-20": {
                "symbols": {
                    "XAUUSD": {
                        "dayType": "SW",
                        "firstSignalHour": 4,
                        "symbolH1Signal": "BUY",
                        "gbpusdH1Signal": "BUY",
                        "alerts": [{
                            "slotHour": 4,
                            "pattern": "T G",
                            "bars": [],
                            "symbol": "XAUUSD+",
                            "profile": "Vantage",
                            "symbolH1Signal": "BUY",
                            "dayType": "SW",
                            "gbpusdH1Signal": "BUY",
                        }],
                    },
                },
            },
        },
    }
    state_path.write_text(json.dumps(existing), encoding="utf-8")
    symbols = [SimpleNamespace(name="XAUUSD+", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    rows = rates_for(20, "TGT")
    sent = []
    subject = scanner(tmp_path, FakeMT5({"XAUUSD+": rows, "GBPUSD+": rows}, symbols), FakeClock(datetime(2026, 8, 20, 4, 5)), sent)
    try:
        assert subject.scan_once() == 0
        assert sent == []
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        symbol_state = saved["days"]["2026-08-20"]["symbols"]["XAUUSD"]
        assert "dayType" not in symbol_state
        assert "firstSignalHour" not in symbol_state
        alert = symbol_state["alerts"][0]
        assert "dayType" not in alert
        assert alert["patternKind"] == PATTERN_KIND_SW2
        assert alert["symbolH1Signal"] == "SELL"  # SW2 now reverses stored GBPUSD BUY.
    finally:
        subject.close()


def test_missing_gbpusd_base_h1_keeps_match_pending_without_alert(tmp_path):
    symbols = [SimpleNamespace(name="XAUUSD+", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    target_rows = rates_for(20, "GGT", start_hour=14)  # H17 target sees H16→H15→H14 = TGG.
    gbp_rows = rates_for(20, "GG", start_hour=14)  # H16 is missing; no fallback is allowed.
    sent = []
    subject = scanner(
        tmp_path,
        FakeMT5({"XAUUSD+": target_rows, "GBPUSD+": gbp_rows}, symbols),
        FakeClock(datetime(2026, 8, 20, 17, 30)),
        sent,
    )
    try:
        assert subject.scan_once() == 0
        assert sent == []
    finally:
        subject.close()


def test_gbpusd_base_never_falls_back_to_previous_broker_day(tmp_path):
    symbols = [SimpleNamespace(name="XAUUSD+", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    target_rows = rates_for(20, "GGT", start_hour=14)
    gbp_rows = [rate(19, 16, "T"), rate(20, 14, "G"), rate(20, 15, "G")]
    sent = []
    subject = scanner(
        tmp_path,
        FakeMT5({"XAUUSD+": target_rows, "GBPUSD+": gbp_rows}, symbols),
        FakeClock(datetime(2026, 8, 20, 17, 30)),
        sent,
    )
    try:
        assert subject.scan_once() == 0
        assert sent == []
    finally:
        subject.close()


def test_state_survives_restart_and_only_new_slots_are_sent(tmp_path):
    symbols = [SimpleNamespace(name="XAUUSDm", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    rows = rates_for(20, "TTGGTTG")
    sent = []
    first = scanner(tmp_path, FakeMT5({"XAUUSDm": rows, "GBPUSD+": rows}, symbols), FakeClock(datetime(2026, 8, 20, 7, 0)), sent)
    first_count = first.scan_once()
    assert first_count >= 1
    first.close()

    restarted = scanner(tmp_path, FakeMT5({"XAUUSDm": rows, "GBPUSD+": rows}, symbols), FakeClock(datetime(2026, 8, 20, 9, 0)), sent)
    try:
        before = len(sent)
        restarted.scan_once()
        state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        slots = [item["slotHour"] for item in state["days"]["2026-08-20"]["symbols"]["XAUUSD"]["alerts"]]
        assert len(slots) == len(set(slots))
        assert len(sent) >= before
    finally:
        restarted.close()


def test_legacy_xau_state_migrates_without_replaying_existing_slot(tmp_path):
    state_path = tmp_path / "state.json"
    existing = {
        "version": 1,
        "days": {
            "2026-08-20": {
                "alerts": [{
                    "slotHour": 4,
                    "pattern": "T G",
                    "bars": [],
                    "symbol": "XAUUSDm",
                    "profile": "Vantage",
                }],
            },
        },
    }
    state_path.write_text(json.dumps(existing), encoding="utf-8")
    symbols = [SimpleNamespace(name="XAUUSDm", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    rows = rates_for(20, "TGT")
    sent = []
    subject = scanner(tmp_path, FakeMT5({"XAUUSDm": rows, "GBPUSD+": rows}, symbols), FakeClock(datetime(2026, 8, 20, 4, 5)), sent)
    try:
        assert subject.scan_once() == 0
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        assert saved["version"] == 2
        assert saved["days"]["2026-08-20"]["symbols"]["XAUUSD"]["alerts"][0]["patternKind"] == PATTERN_KIND_SW2
    finally:
        subject.close()


def test_public_feed_callback_runs_on_state_change_but_not_unchanged_rescan(tmp_path):
    rows = rates_for(20, "TGT")
    symbols = [SimpleNamespace(name="XAUUSDm", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    published = []
    subject = scanner(
        tmp_path,
        FakeMT5({"XAUUSDm": rows, "GBPUSD+": rows}, symbols),
        FakeClock(datetime(2026, 8, 20, 4, 5)),
        [],
        publish_state=lambda state, profile: published.append((json.loads(json.dumps(state)), profile)),
    )
    try:
        assert subject.scan_once() == 1
        assert len(published) == 1
        alert = published[0][0]["days"]["2026-08-20"]["symbols"]["XAUUSD"]["alerts"][0]
        assert alert["patternKind"] == PATTERN_KIND_SW2
        assert "dayType" not in alert
        assert subject.scan_once() == 0
        assert len(published) == 1
    finally:
        subject.close()


def test_public_feed_failure_does_not_rollback_telegram_or_state(tmp_path):
    rows = rates_for(20, "TGT")
    symbols = [SimpleNamespace(name="XAUUSDm", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    sent = []
    attempts = []

    def fail_publish(_state, _profile):
        attempts.append(1)
        raise RuntimeError("offline")

    subject = scanner(
        tmp_path,
        FakeMT5({"XAUUSDm": rows, "GBPUSD+": rows}, symbols),
        FakeClock(datetime(2026, 8, 20, 4, 5)),
        sent,
        publish_state=fail_publish,
    )
    try:
        assert subject.scan_once() == 1
        assert len(sent) == 1
        assert len(attempts) == 1
        assert (tmp_path / "state.json").exists()
    finally:
        subject.close()


def test_scanner_after_h17_republishes_persisted_state_without_h1_history(tmp_path):
    state_path = tmp_path / "state.json"
    existing = {
        "version": 2,
        "days": {
            "2026-08-20": {
                "symbols": {
                    "XAUUSD": {
                        "alerts": [{
                            "slotHour": 4,
                            "pattern": "T G",
                            "patternKind": PATTERN_KIND_SW2,
                            "bars": ["2026-08-20T03:00", "2026-08-20T02:00"],
                            "symbol": "XAUUSDm",
                            "profile": "Vantage",
                            "symbolH1Signal": "SELL",
                            "gbpusdH1Signal": "BUY",
                        }],
                    },
                },
            },
        },
    }
    state_path.write_text(json.dumps(existing), encoding="utf-8")
    symbols = [SimpleNamespace(name="XAUUSDm", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    mt5 = FakeMT5({}, symbols)
    published = []
    subject = scanner(
        tmp_path,
        mt5,
        FakeClock(datetime(2026, 8, 20, 18, 5)),
        [],
        publish_state=lambda state, profile: published.append((json.loads(json.dumps(state)), profile)),
    )
    try:
        assert subject.scan_once() == 0
        assert len(published) == 1
        assert mt5.rate_calls == []
    finally:
        subject.close()


def test_failed_telegram_does_not_advance_persistent_state(tmp_path):
    rows = rates_for(20, "TGT")
    symbols = [SimpleNamespace(name="XAUUSDm", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    attempts = []
    subject = scanner(
        tmp_path,
        FakeMT5({"XAUUSDm": rows, "GBPUSD+": rows}, symbols),
        FakeClock(datetime(2026, 8, 20, 4, 5)),
        [],
        notify=lambda message: attempts.append(message) and False,
    )
    try:
        assert subject.scan_once() == 0
        assert not (tmp_path / "state.json").exists()
    finally:
        subject.close()


def test_corrupt_state_fails_closed_without_telegram(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{broken", encoding="utf-8")
    sent = []
    subject = scanner(tmp_path, FakeMT5(target_h4_rates(), target_symbols()), FakeClock(datetime(2026, 8, 20, 4, 5)), sent)
    try:
        assert subject.scan_once() == 0
        assert sent == []
        assert state_path.read_text(encoding="utf-8") == "{broken"
    finally:
        subject.close()


def test_real_owner_lock_prevents_second_worker_and_state_prevents_replay(tmp_path):
    rows = rates_for(20, "TGT")
    symbols = [SimpleNamespace(name="XAUUSDm", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    rates = {"XAUUSDm": rows, "GBPUSD+": rows}
    clock = FakeClock(datetime(2026, 8, 20, 4, 5))
    sent_a, sent_b = [], []
    first = scanner(tmp_path, FakeMT5(rates, symbols), clock, sent_a, lock_factory=FileLock, profile="Vantage")
    second = scanner(tmp_path, FakeMT5(rates, symbols), clock, sent_b, lock_factory=FileLock, profile="ICMarkets")
    try:
        assert first.scan_once() == 1
        assert second.scan_once() == 0
        assert not second.is_owner
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
    rows = rates_for(20, "GGT", start_hour=14)
    matches = find_h1_pattern_matches(rows, clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert [(m.slot_hour, m.pattern_text, m.pattern_kind) for m in matches] == [
        (17, "T G G", PATTERN_KIND_SW3_PURE)
    ]


def test_scanner_stops_after_h17_without_reading_h1(tmp_path):
    mt5 = FakeMT5(target_h4_rates(), target_symbols())
    sent = []
    subject = scanner(tmp_path, mt5, FakeClock(datetime(2026, 8, 20, 18, 1)), sent)
    try:
        assert subject.scan_once() == 0
        assert sent == []
        assert mt5.rate_calls == []
    finally:
        subject.close()
