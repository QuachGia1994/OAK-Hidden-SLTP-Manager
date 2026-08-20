# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from domain.file_lock import FileLock
import domain.xau_h1_pattern_scanner as scanner_module
from domain.xau_h1_pattern_scanner import (
    H1PatternMatch,
    MultiSymbolH1PatternScanner,
    classify_symbol_day,
    find_h1_pattern_matches,
    pattern5_block_for_h1_slot,
    resolve_canonical_gbpusd_group,
    resolve_symbol_variant,
    resolve_target_symbols,
    resolve_xauusd_symbol,
    signal_from_gbpusd_day_type,
    signal_from_gbpusd_h1_base,
    signal_from_h1_match,
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
    group_resolver=None,
):
    kwargs = {
        "pattern5_group_resolver": group_resolver or (lambda _mt5, _symbol, _day, _block: "Bt")
    }
    return MultiSymbolH1PatternScanner(
        mt5,
        notify=notify or (lambda message: sent.append(message) or True),
        log=lambda _message: None,
        profile_name=profile,
        state_path=tmp_path / "state.json",
        owner_lock_path=tmp_path / "owner.lock",
        clock_factory=lambda **_kwargs: clock,
        lock_factory=lock_factory,
        **kwargs,
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
    rows = rates_for(day, "TGT")  # H03→H02 = TG
    return {
        "XAUUSDm": rows,
        "EURUSD+": rows,
        "AUDUSD.a": rows,
        "USDCAD.pro": rows,
        "USDJPYraw": rows,
        "GBPUSD+": rows,
    }


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


def test_h1_slot_maps_to_expected_pattern5_block():
    expected = {
        3: 3, 4: 3, 5: 3,
        6: 6, 7: 6, 8: 6,
        9: 9, 10: 9, 11: 9,
        12: 12, 13: 12, 14: 12,
        15: 15, 16: 15, 17: 15,
    }
    assert {hour: pattern5_block_for_h1_slot(hour) for hour in expected} == expected


def test_gbpusd_h1_signal_reverses_sw_sr_and_follows_bt():
    assert signal_from_gbpusd_h1_base("T", "Sw") == "SELL"
    assert signal_from_gbpusd_h1_base("G", "Sw") == "BUY"
    assert signal_from_gbpusd_h1_base("T", "Sr") == "SELL"
    assert signal_from_gbpusd_h1_base("G", "Sr") == "BUY"
    assert signal_from_gbpusd_h1_base("T", "Bt") == "BUY"
    assert signal_from_gbpusd_h1_base("G", "Bt") == "SELL"


def test_first_symbol_h1_signal_maps_newest_pattern_candle_and_classifies_day():
    buy_match = H1PatternMatch(4, ("T", "G"), ())
    sell_match = H1PatternMatch(3, ("G", "T"), ())
    assert signal_from_h1_match(buy_match) == "BUY"
    assert signal_from_h1_match(sell_match) == "SELL"
    assert classify_symbol_day("BUY", "BUY") == "SW"
    assert classify_symbol_day("SELL", "SELL") == "SW"
    assert classify_symbol_day("BUY", "SELL") == "BT"
    assert classify_symbol_day("SELL", "BUY") == "BT"


def test_later_symbol_signal_is_derived_from_gbpusd_and_locked_day_type():
    assert signal_from_gbpusd_day_type("BUY", "SW") == "SELL"
    assert signal_from_gbpusd_day_type("SELL", "SW") == "BUY"
    assert signal_from_gbpusd_day_type("BUY", "BT") == "BUY"
    assert signal_from_gbpusd_day_type("SELL", "BT") == "SELL"


def test_canonical_gbpusd_group_reuses_pattern5_and_h15_is_independent(monkeypatch):
    calls = []

    class FakeProvider:
        def __init__(self, mt5_module):
            self.mt5_module = mt5_module

    def build_signal_cell(_symbol, _day, block, _offset, provider=None):
        calls.append((block, provider))
        if block == 12:
            return {"group": "Bt"}, ""
        return {"group": "Sr"}, ""

    fake_pattern5 = SimpleNamespace(
        broker_day_offset=lambda _symbol, provider=None: 123,
        build_signal_cell=build_signal_cell,
    )
    fake_provider_module = SimpleNamespace(MT5MarketDataProvider=FakeProvider)

    def fake_import(name):
        if name == "pattern5_engine":
            return fake_pattern5
        if name == "market_data_provider":
            return fake_provider_module
        raise AssertionError(name)

    monkeypatch.setattr(scanner_module.importlib, "import_module", fake_import)
    assert resolve_canonical_gbpusd_group(object(), "GBPUSD+", datetime(2026, 8, 20).date(), 6) == "Sr"
    assert resolve_canonical_gbpusd_group(object(), "GBPUSD+", datetime(2026, 8, 20).date(), 15) == "Sr"
    assert [block for block, _provider in calls] == [6, 15]


def test_h4_ignores_h1_and_uses_only_h3_h2_backward():
    clock = FakeClock(datetime(2026, 8, 20, 4, 30))
    rows = [rate(20, 1, "G"), rate(20, 2, "G"), rate(20, 3, "T"), rate(20, 4, "G")]
    matches = find_h1_pattern_matches(rows, clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert [(item.slot_hour, item.pattern_text, item.bar_range_text) for item in matches] == [(4, "T G", "H03→H02")]

    rows[0] = rate(20, 1, "T")  # H1 is noise at H4.
    matches = find_h1_pattern_matches(rows, clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert [(item.slot_hour, item.pattern_text) for item in matches] == [(4, "T G")]


def test_h5_plus_uses_three_most_recent_closed_h1_in_backward_order():
    clock = FakeClock(datetime(2026, 8, 20, 5, 10))
    rows = [rate(20, 1, "T"), rate(20, 2, "G"), rate(20, 3, "G"), rate(20, 4, "T"), rate(20, 5, "G")]
    matches = find_h1_pattern_matches(rows, clock.now(), clock.broker_datetime_from_mt5_timestamp)
    assert [(item.slot_hour, item.pattern_text, item.bar_range_text) for item in matches] == [(5, "T G G", "H04→H03→H02")]


def test_fx_starts_at_h3_with_h2_h1_while_xau_waits_for_h4():
    clock = FakeClock(datetime(2026, 8, 20, 3, 10))
    rows = [rate(20, 1, "G"), rate(20, 2, "T"), rate(20, 3, "G")]
    fx_matches = find_h1_pattern_matches(
        rows,
        clock.now(),
        clock.broker_datetime_from_mt5_timestamp,
        first_scan_hour=3,
    )
    xau_matches = find_h1_pattern_matches(
        rows,
        clock.now(),
        clock.broker_datetime_from_mt5_timestamp,
        first_scan_hour=4,
    )
    assert [(item.slot_hour, item.pattern_text, item.bar_range_text) for item in fx_matches] == [(3, "T G", "H02→H01")]
    assert xau_matches == []


def test_first_alert_compares_symbol_h1_with_gbpusd_and_classifies_bt(tmp_path):
    symbols = [
        SimpleNamespace(name="XAUUSD+", visible=True),
        SimpleNamespace(name="GBPUSD+", visible=True),
    ]
    mt5 = FakeMT5(
        {
            "XAUUSD+": rates_for(20, "TGTTG"),  # XAU matches H04 and H06; first signal BUY.
            "GBPUSD+": rates_for(20, "GGTTG"),  # H03=T; Sw reverses GBPUSD to SELL.
        },
        symbols,
    )
    calls = []

    def group_resolver(_mt5, symbol, broker_day, block_hour):
        calls.append((symbol, broker_day.isoformat(), block_hour))
        return "Sw"

    sent = []
    subject = scanner(
        tmp_path,
        mt5,
        FakeClock(datetime(2026, 8, 20, 7, 5)),
        sent,
        group_resolver=group_resolver,
    )
    try:
        assert subject.scan_once() == 2
        assert subject.gbpusd_symbol == "GBPUSD+"
        assert len(sent) == 2
        assert "XAUUSD H1 FIRST SIGNAL" in sent[0]
        assert "Signal XAUUSD H1: BUY" in sent[0]
        assert "Signal GBPUSD H1: SELL | Base H03=T | Block H03=Sw (đảo)" in sent[0]
        assert "Phân loại ngày: BT (ngược chiều GBPUSD H1)" in sent[0]
        assert "XAUUSD H1 PATTERN" in sent[1]
        assert "Mốc scan: H06" in sent[1]
        assert "Signal GBPUSD H1: BUY | Base H05=G | Block H06=Sw (đảo)" in sent[1]
        assert "Phân loại ngày: BT (đã khóa từ first signal H04)" in sent[1]
        assert "Signal XAUUSD H1: BUY" in sent[1]  # BT follows GBPUSD; raw XAU pattern is GTT/SELL.
        assert all("CẨN THẬN" not in message for message in sent)
        assert all("#2" not in message for message in sent)
        assert calls == [
            ("GBPUSD+", "2026-08-20", 3),
            ("GBPUSD+", "2026-08-20", 6),
        ]
        state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        symbol_state = state["days"]["2026-08-20"]["symbols"]["XAUUSD"]
        alerts = symbol_state["alerts"]
        assert len(alerts) == 2
        assert alerts[0]["symbolH1Signal"] == "BUY"
        assert alerts[0]["gbpusdH1Signal"] == "SELL"
        assert alerts[0]["dayType"] == "BT"
        assert alerts[1]["dayType"] == "BT"
        assert alerts[1]["symbolH1Signal"] == "BUY"
        assert alerts[1]["gbpusdH1Signal"] == "BUY"
        assert symbol_state["dayType"] == "BT"
        assert symbol_state["firstSignalHour"] == 4
        assert subject.scan_once() == 0
    finally:
        subject.close()


def test_missing_gbpusd_reference_keeps_first_match_pending_without_alert(tmp_path):
    symbols = [
        SimpleNamespace(name="XAUUSD+", visible=True),
        SimpleNamespace(name="GBPUSD+", visible=True),
    ]
    mt5 = FakeMT5(
        {
            "XAUUSD+": rates_for(20, "GGT", start_hour=14),  # H17=TGG.
            "GBPUSD+": rates_for(20, "GGT", start_hour=14),
        },
        symbols,
    )
    sent = []
    subject = scanner(
        tmp_path,
        mt5,
        FakeClock(datetime(2026, 8, 20, 17, 30)),
        sent,
        group_resolver=lambda _mt5, _symbol, _day, _block: None,
    )
    try:
        assert subject.scan_once() == 0
        assert sent == []
        assert not (tmp_path / "state.json").exists()
    finally:
        subject.close()


def test_scanner_scans_all_five_target_symbols_with_suffixes_and_classifies_sw(tmp_path):
    mt5 = FakeMT5(target_h4_rates(), target_symbols())
    sent = []
    subject = scanner(tmp_path, mt5, FakeClock(datetime(2026, 8, 20, 4, 5)), sent)
    try:
        assert subject.scan_once() == 5
        assert len(sent) == 5
        assert subject.symbols == {
            "XAUUSD": "XAUUSDm",
            "EURUSD": "EURUSD+",
            "AUDUSD": "AUDUSD.a",
            "USDCAD": "USDCAD.pro",
            "USDJPY": "USDJPYraw",
        }
        for base in ("XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"):
            assert any(f"🔔 {base} H1 FIRST SIGNAL" in message for message in sent)
            assert any(f"Signal {base} H1:" in message and "Phân loại ngày: SW" in message for message in sent)
        assert any("XAUUSD H1 FIRST SIGNAL" in message and "Mốc scan: H04" in message for message in sent)
        for base in ("EURUSD", "AUDUSD", "USDCAD", "USDJPY"):
            assert any(f"{base} H1 FIRST SIGNAL" in message and "Mốc scan: H03" in message for message in sent)
    finally:
        subject.close()


def test_first_match_locks_day_but_all_later_patterns_still_notify_without_numbering(tmp_path):
    # XAU matches at H04, H06, H08, H10, H12, H14. All notify; only H04 classifies the day.
    rows = rates_for(20, "TTGGTTGGTTGGT")
    symbols = [SimpleNamespace(name="XAUUSDm", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    mt5 = FakeMT5({"XAUUSDm": rows, "GBPUSD+": rows}, symbols)
    sent = []
    subject = scanner(tmp_path, mt5, FakeClock(datetime(2026, 8, 20, 15, 5)), sent)
    try:
        assert subject.scan_once() == 6
        assert len(sent) == 6
        assert "H1 FIRST SIGNAL" in sent[0]
        assert "Mốc scan: H04" in sent[0]
        assert all("H1 PATTERN" in message for message in sent[1:])
        assert all("Phân loại ngày: SW (đã khóa từ first signal H04)" in message for message in sent[1:])
        # SW reverses each later GBPUSD H1 signal; the target pattern only triggers the alert.
        for message in sent[1:]:
            gbp_signal = "BUY" if "Signal GBPUSD H1: BUY" in message else "SELL"
            expected_target = "SELL" if gbp_signal == "BUY" else "BUY"
            assert f"Signal XAUUSD H1: {expected_target}" in message
        assert all("CẨN THẬN" not in message for message in sent)
        assert all("PATTERN #" not in message for message in sent)
        assert subject.scan_once() == 0
        state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        symbol_state = state["days"]["2026-08-20"]["symbols"]["XAUUSD"]
        alerts = symbol_state["alerts"]
        assert [alert["slotHour"] for alert in alerts] == [4, 6, 8, 10, 12, 14]
        assert {alert["dayType"] for alert in alerts} == {"SW"}
        assert symbol_state["firstSignalHour"] == 4
    finally:
        subject.close()


def test_first_signal_classification_is_independent_per_symbol(tmp_path):
    symbols = [
        SimpleNamespace(name="XAUUSDm", visible=True),
        SimpleNamespace(name="EURUSD+", visible=True),
        SimpleNamespace(name="GBPUSD+", visible=True),
    ]
    rates = {
        "XAUUSDm": rates_for(20, "TGT"),
        "EURUSD+": rates_for(20, "TGT"),
        "GBPUSD+": rates_for(20, "TGT"),
    }
    sent = []
    subject = scanner(tmp_path, FakeMT5(rates, symbols), FakeClock(datetime(2026, 8, 20, 4, 5)), sent)
    try:
        assert subject.scan_once() == 2
        assert any("XAUUSD H1 FIRST SIGNAL" in message for message in sent)
        assert any("EURUSD H1 FIRST SIGNAL" in message for message in sent)
        assert all("Phân loại ngày: SW" in message for message in sent)
        assert subject.scan_once() == 0
    finally:
        subject.close()


def test_state_survives_restart_and_only_new_later_matches_are_sent(tmp_path):
    symbols = [SimpleNamespace(name="XAUUSDm", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    rows = rates_for(20, "TTGGTTG")  # H04, H06, H08 matches.
    sent = []
    first = scanner(
        tmp_path,
        FakeMT5({"XAUUSDm": rows, "GBPUSD+": rows}, symbols),
        FakeClock(datetime(2026, 8, 20, 7, 0)),
        sent,
    )
    assert first.scan_once() == 2
    assert "Mốc scan: H04" in sent[0]
    assert "Mốc scan: H06" in sent[1]
    first.close()

    restarted = scanner(
        tmp_path,
        FakeMT5({"XAUUSDm": rows, "GBPUSD+": rows}, symbols),
        FakeClock(datetime(2026, 8, 20, 9, 0)),
        sent,
    )
    try:
        assert restarted.scan_once() == 1
        assert len(sent) == 3
        assert "XAUUSD H1 PATTERN" in sent[-1]
        assert "Mốc scan: H08" in sent[-1]
        assert "đã khóa từ first signal H04" in sent[-1]
    finally:
        restarted.close()


def test_first_signal_alert_resets_on_new_broker_day(tmp_path):
    symbols = [SimpleNamespace(name="EURUSD+", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    sent = []
    day20_rates = rates_for(20, "TTGGTTG")
    day20 = scanner(
        tmp_path,
        FakeMT5({"EURUSD+": day20_rates, "GBPUSD+": day20_rates}, symbols),
        FakeClock(datetime(2026, 8, 20, 9, 0)),
        sent,
    )
    assert day20.scan_once() == 3
    day20.close()

    day21_rates = rates_for(21, "TGT")
    day21 = scanner(
        tmp_path,
        FakeMT5({"EURUSD+": day21_rates, "GBPUSD+": day21_rates}, symbols),
        FakeClock(datetime(2026, 8, 21, 4, 5)),
        sent,
    )
    try:
        assert day21.scan_once() == 1
        assert len(sent) == 4
        assert "EURUSD H1 FIRST SIGNAL" in sent[-1]
        assert "Ngày broker: 2026-08-21" in sent[-1]
    finally:
        day21.close()


def test_existing_delivered_first_match_is_classified_without_replay_then_later_match_notifies(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps({
            "version": 2,
            "days": {
                "2026-08-20": {
                    "symbols": {
                        "XAUUSD": {
                            "alerts": [{
                                "slotHour": 4,
                                "pattern": "T G",
                                "bars": [],
                                "symbol": "XAUUSD+",
                                "profile": "Vantage",
                            }]
                        }
                    }
                }
            },
        }),
        encoding="utf-8",
    )
    symbols = [
        SimpleNamespace(name="XAUUSD+", visible=True),
        SimpleNamespace(name="GBPUSD+", visible=True),
    ]
    rows = rates_for(20, "TGTTG")  # XAU H04 + H06 matches; GBP Bt gives H04 BUY.
    sent = []
    subject = scanner(
        tmp_path,
        FakeMT5({"XAUUSD+": rows, "GBPUSD+": rows}, symbols),
        FakeClock(datetime(2026, 8, 20, 7, 5)),
        sent,
    )
    try:
        assert subject.scan_once() == 1
        assert len(sent) == 1
        assert "XAUUSD H1 PATTERN" in sent[0]
        assert "Mốc scan: H06" in sent[0]
        assert "Phân loại ngày: SW (đã khóa từ first signal H04)" in sent[0]
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        symbol_state = saved["days"]["2026-08-20"]["symbols"]["XAUUSD"]
        assert symbol_state["dayType"] == "SW"
        assert symbol_state["firstSignalHour"] == 4
        assert [item["slotHour"] for item in symbol_state["alerts"]] == [4, 6]
        assert symbol_state["alerts"][0]["dayType"] == "SW"
    finally:
        subject.close()


def test_legacy_xau_state_migrates_without_replay_and_new_symbol_starts_at_one(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps({
            "version": 1,
            "days": {
                "2026-08-20": {
                    "alerts": [{"slotHour": 4, "pattern": "T G", "bars": [], "symbol": "XAUUSDm", "profile": "Vantage"}]
                }
            },
        }),
        encoding="utf-8",
    )
    symbols = [
        SimpleNamespace(name="XAUUSDm", visible=True),
        SimpleNamespace(name="EURUSD+", visible=True),
        SimpleNamespace(name="GBPUSD+", visible=True),
    ]
    rows = rates_for(20, "TGT")
    rates = {"XAUUSDm": rows, "EURUSD+": rows, "GBPUSD+": rows}
    sent = []
    subject = scanner(tmp_path, FakeMT5(rates, symbols), FakeClock(datetime(2026, 8, 20, 4, 5)), sent)
    try:
        assert subject.scan_once() == 1
        assert len(sent) == 1
        assert "EURUSD H1 FIRST SIGNAL" in sent[0]
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        assert saved["version"] == 2
        assert len(saved["days"]["2026-08-20"]["symbols"]["XAUUSD"]["alerts"]) == 1
        assert len(saved["days"]["2026-08-20"]["symbols"]["EURUSD"]["alerts"]) == 1
    finally:
        subject.close()


def test_failed_telegram_does_not_advance_persistent_state(tmp_path):
    rows = rates_for(20, "TGT")
    symbols = [SimpleNamespace(name="XAUUSDm", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    mt5 = FakeMT5({"XAUUSDm": rows, "GBPUSD+": rows}, symbols)
    attempts = []
    subject = scanner(
        tmp_path,
        mt5,
        FakeClock(datetime(2026, 8, 20, 4, 5)),
        [],
        notify=lambda message: attempts.append(message) and False,
    )
    try:
        assert subject.scan_once() == 0
        assert not (tmp_path / "state.json").exists()
    finally:
        subject.close()

    sent = []
    retry = scanner(
        tmp_path,
        FakeMT5({"XAUUSDm": rows, "GBPUSD+": rows}, symbols),
        FakeClock(datetime(2026, 8, 20, 4, 5)),
        sent,
    )
    try:
        assert retry.scan_once() == 1
        assert len(sent) == 1
    finally:
        retry.close()


def test_corrupt_state_fails_closed_for_all_symbols_without_telegram(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{broken", encoding="utf-8")
    sent = []
    subject = scanner(
        tmp_path,
        FakeMT5(target_h4_rates(), target_symbols()),
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
    symbols = [SimpleNamespace(name="XAUUSDm", visible=True), SimpleNamespace(name="GBPUSD+", visible=True)]
    rates = {"XAUUSDm": rows, "GBPUSD+": rows}
    clock = FakeClock(datetime(2026, 8, 20, 4, 5))
    sent_a = []
    sent_b = []
    first = scanner(tmp_path, FakeMT5(rates, symbols), clock, sent_a, lock_factory=FileLock, profile="Vantage")
    second = scanner(tmp_path, FakeMT5(rates, symbols), clock, sent_b, lock_factory=FileLock, profile="ICMarkets")
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


def test_scanner_stops_after_h17_even_with_no_prior_alerts(tmp_path):
    mt5 = FakeMT5(target_h4_rates(), target_symbols())
    sent = []
    subject = scanner(tmp_path, mt5, FakeClock(datetime(2026, 8, 20, 18, 1)), sent)
    try:
        assert subject.scan_once() == 0
        assert sent == []
        assert mt5.rate_calls == []
    finally:
        subject.close()
