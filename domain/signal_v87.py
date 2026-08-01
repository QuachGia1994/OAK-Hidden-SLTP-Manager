"""Pure v87 signal rules using only the completed MT4 feed bars.

The module deliberately has no MetaTrader import and no wall-clock reads.  The
caller supplies a Broker-date, a feed provider, and (for live evaluation) an
``as_of`` cutoff.  This makes history rebuilds deterministic and keeps the
reference/entry/reverse steps in one auditable pipeline.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

PAIRS = ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
SLOTS = (3, 7, 9, 12, 14, 16)


def reverse_signal(signal: str | None) -> str:
    return {"BUY": "SELL", "SELL": "BUY"}.get(signal, "WAIT")


def candle_direction(candle: dict | None) -> str | None:
    if not candle:
        return None
    try:
        open_exact = candle.get("open_exact")
        close_exact = candle.get("close_exact")
        opening = Decimal(str(open_exact if open_exact is not None else candle["open"]))
        closing = Decimal(str(close_exact if close_exact is not None else candle["close"]))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None
    if closing > opening:
        return "TANG"
    if closing < opening:
        return "GIAM"
    return "DOJI"


def direction_to_signal(direction: str | None) -> str:
    return {"TANG": "BUY", "GIAM": "SELL"}.get(direction, "WAIT")


def classify_three_candle_group(directions: list[str | None]) -> dict[str, Any]:
    values = list(directions or [])
    if len(values) != 3 or any(value not in ("TANG", "GIAM") for value in values):
        return {"group": None, "rule_number": None, "directions": values}
    table = {
        ("TANG", "TANG", "TANG"): ("SW", 1),
        ("GIAM", "TANG", "TANG"): ("SW", 2),
        ("GIAM", "TANG", "GIAM"): ("BT", 3),
        ("GIAM", "GIAM", "TANG"): ("BT", 4),
        ("GIAM", "GIAM", "GIAM"): ("SW", 5),
        ("TANG", "GIAM", "GIAM"): ("SW", 6),
        ("TANG", "GIAM", "TANG"): ("BT", 7),
        ("TANG", "TANG", "GIAM"): ("BT", 8),
    }
    group, rule = table[tuple(values)]
    return {"group": group, "rule_number": rule, "directions": values}


def _bar(provider, symbol: str, timeframe: str, broker_open: datetime, as_of: datetime | None):
    if as_of is not None and broker_open + _timeframe_delta(timeframe) > as_of:
        return None
    try:
        bar = provider.get_exact_bar(symbol, timeframe, broker_open)
    except Exception:
        return None
    if not bar or not bool(bar.get("is_complete", True)):
        return None
    return bar


def _timeframe_delta(timeframe: str) -> timedelta:
    return {"M30": timedelta(minutes=30), "H1": timedelta(hours=1), "H4": timedelta(hours=4)}[timeframe]


def _layer(provider, symbol: str, timeframe: str, opens: tuple[datetime, ...], as_of: datetime | None, label: str):
    candles = []
    for index, opening in enumerate(opens):
        bar = _bar(provider, symbol, timeframe, opening, as_of)
        candles.append({
            "role": f"C{index + 1}{'_BASE' if index == 0 else ''}",
            "open_time": opening.isoformat(),
            "close_time": (opening + _timeframe_delta(timeframe)).isoformat(),
            "state": "READY" if bar else "MISSING",
            "direction": candle_direction(bar),
            "open": bar.get("open") if bar else None,
            "high": bar.get("high") if bar else None,
            "low": bar.get("low") if bar else None,
            "close": bar.get("close") if bar else None,
            "open_exact": bar.get("open_exact", bar.get("open")) if bar else None,
            "close_exact": bar.get("close_exact", bar.get("close")) if bar else None,
            "tick_volume": bar.get("tick_volume") if bar else None,
        })
    classification = classify_three_candle_group([item["direction"] for item in candles])
    return {
        "name": label,
        "timeframe": timeframe,
        "candles": candles,
        "directions": classification["directions"],
        "base_direction": candles[0]["direction"],
        "group": classification["group"],
        "rule_number": classification["rule_number"],
        "classifier_model": "THREE_CANDLE_SW_BT",
    }


def build_entry_plan(slot_dt: datetime, slot_hour: int, provider, as_of: datetime | None = None) -> dict[str, Any]:
    """Resolve the one XAUUSD Entry Plan shared by all five pairs."""
    h = int(slot_hour)
    if h == 16:
        layer2_opens = tuple(slot_dt.replace(hour=x, minute=0, second=0, microsecond=0) for x in (5, 4, 3))
        layer2 = _layer(provider, "XAUUSD", "H1", layer2_opens, as_of, "LAYER_2")
        if layer2["group"] == "BT":
            return _entry_result(h, "16:11", "H_11", ("16:11",), layer2, None)
        layer3_opens = tuple(slot_dt.replace(hour=x, minute=0, second=0, microsecond=0) for x in (10, 9, 8))
        layer3 = _layer(provider, "XAUUSD", "H1", layer3_opens, as_of, "LAYER_3")
        entry = "16:49" if layer3["group"] == "BT" else "17:25" if layer3["group"] == "SW" else None
        branch = "H_49" if entry == "16:49" else "H_PLUS_1_25" if entry else None
        return _entry_result(h, entry, branch, ("16:49", "17:25"), layer2, layer3)
    layer2_opens = tuple(slot_dt - timedelta(minutes=x) for x in (30, 60, 90))
    layer2 = _layer(provider, "XAUUSD", "M30", layer2_opens, as_of, "LAYER_2")
    if layer2["group"] == "BT":
        entry = f"{h:02d}:11"
        return _entry_result(h, entry, "H_11", (entry,), layer2, None)
    layer3_opens = (slot_dt, slot_dt - timedelta(minutes=30), slot_dt - timedelta(minutes=60))
    layer3 = _layer(provider, "XAUUSD", "M30", layer3_opens, as_of, "LAYER_3")
    entry = f"{h:02d}:49" if layer3["group"] == "SW" else ("04:25" if h == 3 else f"{h + 1:02d}:25") if layer3["group"] == "BT" else None
    branch = "H_49" if entry and entry.endswith(":49") else "H_PLUS_1_25" if entry else None
    pending = (
        entry is None
        and as_of is not None
        and as_of < slot_dt + timedelta(minutes=30)
    )
    return _entry_result(
        h,
        entry,
        branch,
        (f"{h:02d}:49", "04:25" if h == 3 else f"{h + 1:02d}:25"),
        layer2,
        layer3,
        entry_state="PENDING_LAYER3" if pending else None,
    )


def _entry_result(hour, entry, branch, candidates, layer2, layer3, entry_state=None):
    required_layers = (layer2, layer3) if layer3 is not None else (layer2,)
    has_missing_candle = any(
        candle.get("state") == "MISSING"
        for layer in required_layers
        for candle in layer.get("candles", [])
    )
    return {
        "symbol": "XAUUSD",
        "slot_hour": hour,
        "entry_time": entry,
        "entry_branch": branch,
        "entry_state": entry_state or ("READY" if entry else "WAIT"),
        "entry_candidates": list(candidates),
        "layers": {"layer2": layer2, "layer3": layer3},
        "layer2": layer2,
        "layer3": layer3,
        "classification_reason": "XAU_COMMON_ENTRY_PLAN",
        "timeframe": "H1" if hour == 16 else "M30",
        "source_symbol": "XAUUSD",
        "entry_selection": layer2.get("group") if layer3 is None else layer3.get("group"),
        "failure_reason": "WAIT_MT4_DATA" if has_missing_candle and not entry and entry_state != "PENDING_LAYER3" else None,
    }


def classify_d_relation(pair_direction: str | None, reference_direction: str | None) -> str:
    if pair_direction not in ("BUY", "SELL") or reference_direction not in ("BUY", "SELL"):
        return "UNRESOLVED"
    return "SAME_AS_REFERENCE" if pair_direction == reference_direction else "OPPOSITE_TO_REFERENCE"


def _mode_branch(day_mode):
    if day_mode is None:
        return None
    if isinstance(day_mode, str):
        return "H_11" if day_mode in ("H_11", "DAY_MODE_H11") else "H_PLUS_1_25" if day_mode in ("H_PLUS_1_25", "DAY_MODE_H_PLUS_1_25") else None
    return getattr(day_mode, "source_branch", None)


def _reference_base(entry, slot_dt, provider, reference_d, day_mode):
    branch = entry.get("entry_branch")
    if branch == "H_49":
        h1 = _bar(provider, "XAUUSD", "H1", slot_dt - timedelta(hours=1), slot_dt)
        direction = candle_direction(h1)
        return ("SELL" if direction == "TANG" else "BUY" if direction == "GIAM" else "WAIT"), day_mode, "PREVIOUS_XAU_H1_REVERSED"
    mode_branch = _mode_branch(day_mode)
    if mode_branch is None:
        mode_branch = branch if branch in ("H_11", "H_PLUS_1_25") else None
        day_mode = mode_branch
    base = reference_d if reference_d in ("BUY", "SELL") else direction_to_signal(reference_d)
    if base == "WAIT" or mode_branch is None:
        return "WAIT", day_mode, "REFERENCE_D_UNRESOLVED"
    return (base if branch == mode_branch else reverse_signal(base)), day_mode, "REFERENCE_D_DAY_MODE"


def final_reverse(slot_hour: int, signal_date) -> tuple[bool, str]:
    weekday = signal_date.weekday()
    day = signal_date.day
    if slot_hour == 3:
        if weekday == 2:
            return True, "H3_WEDNESDAY"
        if weekday == 3:
            previous_wed = signal_date - timedelta(days=1)
            return (False, "H3_THURSDAY_PREVIOUS_WED_MONTH_BOUNDARY_EXCEPTION") if previous_wed.day in (30, 1) else (True, "H3_THURSDAY")
        return (True, "H3_FRIDAY_SPECIAL_DAY_3_4_7") if weekday == 4 and day in (3, 4, 7) else (False, "H3_NORMAL")
    if slot_hour == 14:
        return (True, "H14_TUESDAY") if weekday == 1 else (True, "H14_WEDNESDAY") if weekday == 2 else (False, "H14_NORMAL")
    if slot_hour == 16:
        if weekday == 1:
            return True, "H16_TUESDAY"
        if weekday == 2:
            return True, "H16_WEDNESDAY"
        if weekday == 3:
            prev = signal_date - timedelta(days=1)
            return (True, "H16_THURSDAY_PREVIOUS_WED_MONTH_BOUNDARY") if prev.day in (30, 1) else (False, "H16_THURSDAY_NORMAL")
        if weekday == 4:
            return (False, "H16_FRIDAY_SPECIAL_DAY_3_4_7_EXCEPTION") if day in (3, 4, 7) else (True, "H16_FRIDAY")
        return False, "H16_NORMAL"
    return False, f"H{slot_hour}_NO_REVERSE"


def evaluate_slot(slot_dt: datetime, slot_hour: int, provider, d_snapshot: dict[str, dict], day_mode=None, as_of: datetime | None = None) -> dict[str, Any]:
    """Run entry, reference, D relation, and final reverse exactly once."""
    entry = build_entry_plan(slot_dt, slot_hour, provider, as_of)
    reference_d = (d_snapshot.get("GBPUSD") or {}).get("d_direction")
    base_signal, next_mode, base_source = _reference_base(entry, slot_dt, provider, reference_d, day_mode)
    # XAUUSD's D candle is independent evidence even though its Signal is
    # locked to the GBPUSD Reference Signal.  Preserve that relation in the
    # payload so the drawer can explain an opposite XAU D without changing
    # the locked Signal.
    relations = {
        "XAUUSD": classify_d_relation(
            (d_snapshot.get("XAUUSD") or {}).get("d_direction"), reference_d
        ),
        "GBPUSD": "REFERENCE",
    }
    for symbol in ("GBPAUD", "GBPJPY", "GBPCAD"):
        relations[symbol] = classify_d_relation((d_snapshot.get(symbol) or {}).get("d_direction"), reference_d)
    core = {"XAUUSD": base_signal, "GBPUSD": base_signal}
    if base_signal in ("BUY", "SELL"):
        for symbol in ("GBPAUD", "GBPJPY", "GBPCAD"):
            relation = relations[symbol]
            if relation == "UNRESOLVED":
                core[symbol] = "WAIT"
            elif symbol == "GBPAUD":
                core[symbol] = base_signal if relation == "SAME_AS_REFERENCE" else reverse_signal(base_signal)
            else:
                core[symbol] = reverse_signal(base_signal) if relation == "SAME_AS_REFERENCE" else base_signal
    else:
        core.update({symbol: "WAIT" for symbol in ("GBPAUD", "GBPJPY", "GBPCAD")})
    should_reverse, reason = final_reverse(int(slot_hour), slot_dt.date())
    final = {symbol: reverse_signal(signal) if should_reverse and signal in ("BUY", "SELL") else signal for symbol, signal in core.items()}
    pair_times = {symbol: entry.get("entry_time") for symbol in PAIRS}
    pair_branches = {symbol: entry.get("entry_branch") for symbol in PAIRS}
    evidence = {symbol: _evidence(symbol, slot_dt, entry, d_snapshot, relations, core, final, should_reverse, reason, base_source) for symbol in PAIRS}
    failure_reason = entry.get("failure_reason")
    if failure_reason is None and reference_d not in ("BUY", "SELL"):
        failure_reason = "WAIT_MT4_DATA"
    return {
        "logic_version": 87,
        "signal": final["XAUUSD"],
        "signal_state": "READY" if final["XAUUSD"] in ("BUY", "SELL") else "WAIT",
        "entry_time": entry.get("entry_time"),
        "entry_branch": entry.get("entry_branch"),
        "entry_state": entry.get("entry_state"),
        "failure_reason": failure_reason,
        "entry_candidates": entry.get("entry_candidates"),
        "entry_timeframe": entry.get("timeframe"),
        "entry_source_symbol": "XAUUSD",
        "pair_dirs": final,
        "core_signal": core["XAUUSD"],
        "core_signals": core,
        "final_reverse_applied": should_reverse,
        "final_reverse_reason": reason if should_reverse else None,
        "pair_signal_states": {symbol: "READY" if final[symbol] in ("BUY", "SELL") else "WAIT" for symbol in PAIRS},
        "pair_entry_states": {symbol: entry.get("entry_state") for symbol in PAIRS},
        "pair_entry_times": pair_times,
        "pair_entry_branches": pair_branches,
        "pair_d_directions": {symbol: (d_snapshot.get(symbol) or {}).get("d_direction", "WAIT") for symbol in PAIRS},
        "pair_d_relations": relations,
        "pair_relation_rules": {"XAUUSD": "FOLLOW_REFERENCE_SIGNAL", "GBPUSD": "REFERENCE_SIGNAL", "GBPAUD": "SAME_FOLLOW_OPPOSITE_REVERSE", "GBPJPY": "SAME_REVERSE_OPPOSITE_FOLLOW", "GBPCAD": "SAME_REVERSE_OPPOSITE_FOLLOW"},
        "reference_d_symbol": "GBPUSD",
        "reference_d_direction": reference_d or "WAIT",
        "d_directions": d_snapshot,
        "pair_evidence": evidence,
        "timing": entry,
        "day_mode": next_mode,
        "day_mode_state": "RESOLVED" if next_mode else "UNRESOLVED_WAITING_FOR_ANCHOR",
        "report": f"H={slot_hour} signal={final['XAUUSD']} entry={entry.get('entry_time') or 'WAIT'}"
        + (f" reason={failure_reason}" if failure_reason else ""),
    }


def _evidence(symbol, slot_dt, entry, d_snapshot, relations, core, final, reversed_once, reason, base_source):
    return {
        "evidence_schema_version": 9,
        "logic_version": 87,
        "date": slot_dt.date().isoformat(),
        "hour": slot_dt.hour,
        "symbol": symbol,
        "entry_source_symbol": "XAUUSD",
        "entry_time": entry.get("entry_time"),
        "entry_branch": entry.get("entry_branch"),
        "entry_state": entry.get("entry_state"),
        "entry_timing": entry,
        "d_evidence": d_snapshot.get(symbol),
        "reference_d_symbol": "GBPUSD",
        "reference_d_direction": (d_snapshot.get("GBPUSD") or {}).get("d_direction", "WAIT"),
        "pair_d_direction": (d_snapshot.get(symbol) or {}).get("d_direction", "WAIT"),
        "d_relation": relations.get(symbol, "UNRESOLVED"),
        "relation_rule": {"XAUUSD": "FOLLOW_REFERENCE_SIGNAL", "GBPUSD": "REFERENCE_SIGNAL", "GBPAUD": "SAME_FOLLOW_OPPOSITE_REVERSE", "GBPJPY": "SAME_REVERSE_OPPOSITE_FOLLOW", "GBPCAD": "SAME_REVERSE_OPPOSITE_FOLLOW"}.get(symbol),
        "core_signal": core.get(symbol, "WAIT"),
        "final_reverse_applied": reversed_once,
        "final_reverse_reason": reason if reversed_once else None,
        "final_signal": final.get(symbol, "WAIT"),
        "base_signal_source": base_source,
        "failure_reason": entry.get("failure_reason") or (
            "WAIT_MT4_DATA" if (d_snapshot.get("GBPUSD") or {}).get("d_direction") not in ("BUY", "SELL") else None
        ),
    }
