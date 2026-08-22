# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import date, datetime, timezone
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
    post_signal_decision,
    pure_cooldown_slots,
    resolve_symbol_variant,
    resolve_target_symbols,
    scanner_base_for_target,
    signal_from_base_after_calendar,
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


def test_target_mapping_is_audusd_plus_gbpusd_for_xau_and_gbpusd_plus_own_base_for_others():
    assert scanner_base_for_target("XAUUSD") == "AUDUSD"
    assert base_symbol_for_target("XAUUSD") == "GBPUSD"
    for base in ("EURUSD", "AUDUSD", "USDCAD", "USDJPY"):
        assert scanner_base_for_target(base) == "GBPUSD"
        assert base_symbol_for_target(base) == base


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


def test_every_pattern_keeps_base_before_calendar_post_signal():
    assert signal_from_h1_direction("T") == "BUY"
    assert signal_from_h1_direction("G") == "SELL"
    for kind in (PATTERN_KIND_SW2, PATTERN_KIND_SW3_PURE, PATTERN_KIND_SW3_NORMAL):
        assert signal_from_pattern_base("BUY", kind) == "BUY"
        assert signal_from_pattern_base("SELL", kind) == "SELL"


def test_calendar_post_signal_weekday_blocks_and_monthly_cycles():
    monday = date(2026, 8, 17)
    for slot in (3, 4, 9, 10, 11, 12, 13, 14):
        assert post_signal_decision(monday, slot) == (True, "mon-block")
    assert post_signal_decision(monday, 8) == (False, "none")
    tuesday = date(2026, 8, 18)
    for slot in (3, 4, 9, 10, 11):
        assert post_signal_decision(tuesday, slot) == (True, "tue-block")
    assert post_signal_decision(tuesday, 12) == (False, "none")
    wednesday = date(2026, 8, 19)
    for slot in (3, 4, 12, 13, 14):
        assert post_signal_decision(wednesday, slot) == (True, "wed-block")
    assert post_signal_decision(wednesday, 9) == (False, "none")
    assert post_signal_decision(date(2026, 7, 2), 8) == (True, "thu-cycle")
    assert post_signal_decision(date(2026, 7, 30), 14) == (True, "thu-cycle")
    assert post_signal_decision(date(2026, 8, 6), 8) == (False, "none")
    assert post_signal_decision(date(2026, 10, 1), 8) == (True, "thu-cycle")
    assert post_signal_decision(date(2026, 5, 1), 8) == (False, "none")
    assert post_signal_decision(date(2026, 8, 7), 8) == (True, "fri-cycle")
    assert post_signal_decision(date(2026, 8, 21), 14) == (True, "fri-cycle")
    assert signal_from_base_after_calendar("BUY", date(2026, 8, 21), 14) == "SELL"


def test_pure_cooldown_blocks_only_pure_matches_while_normal_sw_remains_tradable():
    h8 = FakeClock(datetime(2026, 8, 20, 8, 0))
    matches = find_h1_pattern_matches(rates_for(20, "GGTTGGT"), h8.now(), h8.broker_datetime_from_mt5_timestamp)
    pure = [match for match in matches if match.pattern_kind == PATTERN_KIND_SW3_PURE]
    assert [
        (match.slot_hour, match.pattern_text, match.trade_allowed, match.blocked_by_pure_slot)
        for match in pure
    ] == [
        (4, "T G G", True, None),
        (6, "G T T", False, 4),
        (8, "T G G", True, None),
    ]
    assert pure_cooldown_slots(matches, h8.now().hour) == [6]

    h16 = FakeClock(datetime(2026, 8, 20, 16, 0))
    shifted = find_h1_pattern_matches(rates_for(20, "GGTTGGT", start_hour=9), h16.now(), h16.broker_datetime_from_mt5_timestamp)
    assert pure_cooldown_slots(shifted, h16.now().hour) == [14]
    h14_pure = next(match for match in shifted if match.slot_hour == 14 and match.pattern_kind == PATTERN_KIND_SW3_PURE)
    h16_pure = next(match for match in shifted if match.slot_hour == 16 and match.pattern_kind == PATTERN_KIND_SW3_PURE)
    assert (h14_pure.trade_allowed, h14_pure.blocked_by_pure_slot) == (False, 12)
    assert (h16_pure.trade_allowed, h16_pure.blocked_by_pure_slot) == (True, None)

    h15 = FakeClock(datetime(2026, 8, 20, 15, 0))
    normal_window = find_h1_pattern_matches(rates_for(20, "GGTTTG", start_hour=9), h15.now(), h15.broker_datetime_from_mt5_timestamp)
    h14_normal = next(match for match in normal_window if match.slot_hour == 14 and match.pattern_kind == PATTERN_KIND_SW3_NORMAL)
    h15_pure = next(match for match in normal_window if match.slot_hour == 15 and match.pattern_kind == PATTERN_KIND_SW3_PURE)
    assert (h14_normal.trade_allowed, h14_normal.blocked_by_pure_slot) == (True, None)
    assert (h15_pure.trade_allowed, h15_pure.blocked_by_pure_slot) == (False, 12)
    assert pure_cooldown_slots(normal_window, h15.now().hour) == [15]


def test_xau_sw2_uses_audusd_source_and_keeps_gbpusd_base(tmp_path):
    sent: list[str] = []
    subject = make_scanner(tmp_path, FakeMT5(all_rates("GT")), FakeClock(datetime(2026, 8, 20, 3, 0)), sent)
    try:
        subject.scan_once()
        xau = next(message for message in sent if message.startswith("🔔 XAUUSD") and "Mốc scan: H03" in message)
        assert "Pattern nguồn: T G" in xau
        assert "Nhóm nguồn: SW 2 cây" in xau
        assert "Base H1: GBPUSD H02=T → BUY" in xau
        assert "Logic pattern: giữ nguyên GBPUSD H1" in xau
        assert "Hậu signal: không đảo" in xau
        assert "Signal XAUUSD H1: BUY" in xau
    finally:
        subject.close()


def test_xau_pure_sw3_keeps_gbpusd_base_then_applies_calendar_post_signal(tmp_path):
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
        assert "Logic pattern: giữ nguyên GBPUSD H1" in xau
        assert "Hậu signal: không đảo" in xau
        assert "Signal XAUUSD H1: BUY" in xau
        assert "Hậu kiểm" not in xau
    finally:
        subject.close()


def test_normal_sw3_keeps_own_base_before_calendar_post_signal(tmp_path):
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
        assert "Logic pattern: giữ nguyên EURUSD H1" in eur
        assert "Hậu signal: không đảo" in eur
        assert "Signal EURUSD H1: SELL" in eur
    finally:
        subject.close()


def test_usdcad_uses_gbpusd_source_and_own_h1_base(tmp_path):
    rates = all_rates("TGT")
    rates["GBPUSD+"] = rates_for(20, "GGT")
    rates["USDCAD.pro"] = rates_for(20, "GGG")
    sent: list[str] = []
    subject = make_scanner(tmp_path, FakeMT5(rates), FakeClock(datetime(2026, 8, 20, 4, 0)), sent)
    try:
        subject.scan_once()
        cad = next(message for message in sent if message.startswith("🔔 USDCAD") and "Mốc scan: H04" in message)
        assert "Scanner pattern: GBPUSD (GBPUSD+)" in cad
        assert "Pattern nguồn: T G G" in cad
        assert "Base H1: USDCAD H03=G → SELL" in cad
        assert "Logic pattern: giữ nguyên USDCAD H1" in cad
        assert "Signal USDCAD H1: SELL" in cad
    finally:
        subject.close()


def test_pure_inside_cooldown_is_calculated_and_published_block_but_not_sent_to_telegram(tmp_path):
    rates = all_rates("GGTTG")
    rates["AUDUSD.a"] = rates_for(20, "GGTTG")
    sent: list[str] = []
    subject = make_scanner(tmp_path, FakeMT5(rates), FakeClock(datetime(2026, 8, 20, 6, 0)), sent)
    try:
        subject.scan_once()
        assert any(message.startswith("🔔 XAUUSD") and "Mốc scan: H04" in message for message in sent)
        assert not any(message.startswith("🔔 XAUUSD") and "Mốc scan: H06" in message for message in sent)
        saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        xau = saved["days"]["2026-08-20"]["symbols"]["XAUUSD"]
        h6 = next(row for row in xau["alerts"] if row["slotHour"] == 6)
        assert h6["patternKind"] == PATTERN_KIND_SW3_PURE
        assert h6["tradeAllowed"] is False
        assert h6["blockedByPureSlot"] == 4
        assert xau["blockedSlots"] == [6]
    finally:
        subject.close()


def test_normal_sw_inside_pure_window_is_sent_while_later_pure_is_blocked(tmp_path):
    rates = all_rates("GGTTTG", start_hour=9)
    rates["AUDUSD.a"] = rates_for(20, "GGTTTG", start_hour=9)
    sent: list[str] = []
    subject = make_scanner(tmp_path, FakeMT5(rates), FakeClock(datetime(2026, 8, 20, 15, 0)), sent)
    try:
        subject.scan_once()
        assert any(message.startswith("🔔 XAUUSD") and "Mốc scan: H12" in message for message in sent)
        assert any(message.startswith("🔔 XAUUSD") and "Mốc scan: H14" in message for message in sent)
        assert not any(message.startswith("🔔 XAUUSD") and "Mốc scan: H15" in message for message in sent)
        saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        xau = saved["days"]["2026-08-20"]["symbols"]["XAUUSD"]
        h14 = next(row for row in xau["alerts"] if row["slotHour"] == 14)
        h15 = next(row for row in xau["alerts"] if row["slotHour"] == 15)
        assert h14["patternKind"] == PATTERN_KIND_SW3_NORMAL
        assert (h14["tradeAllowed"], h14["blockedByPureSlot"]) == (True, None)
        assert h15["patternKind"] == PATTERN_KIND_SW3_PURE
        assert (h15["tradeAllowed"], h15["blockedByPureSlot"]) == (False, 12)
        assert xau["blockedSlots"] == [15]
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


def test_v7_state_migrates_to_v10_suppression_without_replaying_old_slots(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "version": 7,
        "days": {"2026-08-20": {"symbols": {"XAUUSD": {"alerts": [{"slotHour": 4, "pattern": "T G G"}]}}}},
    }), encoding="utf-8")
    sent: list[str] = []
    subject = make_scanner(tmp_path, FakeMT5(all_rates("GGTTG")), FakeClock(datetime(2026, 8, 20, 6, 0)), sent)
    try:
        subject.scan_once()
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        assert saved["version"] == 10
        assert saved["days"]["2026-08-20"]["suppressedThroughHour"] == 4
        assert all("Mốc scan: H04" not in message for message in sent)
    finally:
        subject.close()


def test_v9_state_migrates_to_v10_and_unblocks_normal_sw_rows(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "version": 9,
        "days": {
            "2026-08-20": {
                "symbols": {
                    "XAUUSD": {
                        "alerts": [
                            {"slotHour": 12, "patternKind": PATTERN_KIND_SW3_PURE, "tradeAllowed": True, "blockedByPureSlot": None},
                            {"slotHour": 14, "patternKind": PATTERN_KIND_SW3_NORMAL, "tradeAllowed": False, "blockedByPureSlot": 12},
                            {"slotHour": 15, "patternKind": PATTERN_KIND_SW3_PURE, "tradeAllowed": False, "blockedByPureSlot": 12},
                        ],
                        "blockedSlots": [13, 14, 15],
                    },
                },
            },
        },
    }), encoding="utf-8")
    subject = make_scanner(tmp_path, FakeMT5(all_rates("GGTTTG", start_hour=9)), FakeClock(datetime(2026, 8, 20, 18, 0)), [])
    try:
        subject.scan_once()
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        xau = saved["days"]["2026-08-20"]["symbols"]["XAUUSD"]
        h14 = next(row for row in xau["alerts"] if row["slotHour"] == 14)
        h15 = next(row for row in xau["alerts"] if row["slotHour"] == 15)
        assert saved["version"] == 10
        assert (h14["tradeAllowed"], h14["blockedByPureSlot"]) == (True, None)
        assert (h15["tradeAllowed"], h15["blockedByPureSlot"]) == (False, 12)
        assert xau["blockedSlots"] == [15]
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


def test_public_feed_callback_keeps_blocked_pure_and_three_slot_cooldown_metadata(tmp_path):
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
        xau = published[-1][0]["days"]["2026-08-20"]["symbols"]["XAUUSD"]
        xau_alerts = xau["alerts"]
        h4 = next(row for row in xau_alerts if row["slotHour"] == 4)
        h6 = next(row for row in xau_alerts if row["slotHour"] == 6)
        assert h4["patternKind"] == PATTERN_KIND_SW3_PURE and h4["tradeAllowed"] is True
        assert h6["patternKind"] == PATTERN_KIND_SW3_PURE and h6["tradeAllowed"] is False
        assert h6["blockedByPureSlot"] == 4
        assert xau["blockedSlots"] == [6]
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
