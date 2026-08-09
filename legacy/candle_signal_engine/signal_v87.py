"""Pure v88 signal rules using only completed market-data bars.

The module deliberately has no MetaTrader import and no wall-clock reads.  The
caller supplies a Broker-date, a data provider, and (for live evaluation) an
``as_of`` cutoff.  This makes history rebuilds deterministic and keeps the
reference/entry/reverse steps in one auditable pipeline.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

PAIRS = ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
SLOTS = (3, 7, 9, 12, 14, 16)

# Canonical slot-level active pair map.  XAUUSD and GBPUSD are evaluated at
# every slot and always share the same Signal.  A pair absent from a slot is
# NOT_APPLICABLE: it is never derived, never read for D, never scheduled, and
# never published.
SLOT_ACTIVE_PAIRS = {
    3: ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY"),
    7: ("XAUUSD", "GBPUSD", "GBPJPY"),
    9: ("XAUUSD", "GBPUSD", "GBPCAD"),
    12: ("XAUUSD", "GBPUSD", "GBPAUD"),
    14: ("XAUUSD", "GBPUSD", "GBPCAD"),
    16: ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD"),
}


def get_evaluated_pairs_for_hour(hour):
    """Return the canonical active pairs evaluated at a given slot hour."""
    return tuple(SLOT_ACTIVE_PAIRS.get(int(hour), ()))


class SignalInvariantError(Exception):
    """Raised when a signal invariant is violated (e.g. XAUUSD != GBPUSD)."""
    pass


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


def _resolve_active_source_id(provider) -> str | None:
    """Return the active feed source_id the engine should read bars from.

    Duck-typed so pure fixtures without a heartbeat return ``None``.
    """
    getter = getattr(provider, "get_active_source_id", None)
    if not callable(getter):
        return None
    try:
        return getter() or None
    except Exception:
        return None


def _bar(provider, symbol: str, timeframe: str, broker_open: datetime, as_of: datetime | None, source_id: str | None = None):
    if as_of is not None and broker_open + _timeframe_delta(timeframe) > as_of:
        return None
    if source_id is None:
        source_id = _resolve_active_source_id(provider)
    try:
        if source_id is not None:
            bar = provider.get_exact_bar(symbol, timeframe, broker_open, source_id=source_id)
        else:
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


def _provider_wait_reason(provider) -> str:
    """Market-data wait reason (MT5 is the only provider)."""
    return "WAIT_MT5_DATA"


def build_entry_plan(slot_dt: datetime, slot_hour: int, provider, as_of: datetime | None = None) -> dict[str, Any]:
    """Resolve the one XAUUSD Entry Plan shared by all five pairs."""
    h = int(slot_hour)
    wait_reason = _provider_wait_reason(provider)
    if h == 16:
        layer2_opens = tuple(slot_dt.replace(hour=x, minute=0, second=0, microsecond=0) for x in (5, 4, 3))
        layer2 = _layer(provider, "XAUUSD", "H1", layer2_opens, as_of, "LAYER_2")
        if layer2["group"] == "BT":
            return _entry_result(h, "16:11", "H_11", ("16:11",), layer2, None, provider_wait_reason=wait_reason)
        if layer2["group"] != "SW":
            return _entry_result(h, None, None, (), layer2, None, provider_wait_reason=wait_reason)
        layer3_opens = tuple(slot_dt.replace(hour=x, minute=0, second=0, microsecond=0) for x in (10, 9, 8))
        layer3 = _layer(provider, "XAUUSD", "H1", layer3_opens, as_of, "LAYER_3")
        entry = "16:49" if layer3["group"] == "BT" else "17:25" if layer3["group"] == "SW" else None
        branch = "H_49" if entry == "16:49" else "H_PLUS_1_25" if entry else None
        return _entry_result(h, entry, branch, ("16:49", "17:25"), layer2, layer3, provider_wait_reason=wait_reason)
    layer2_opens = tuple(slot_dt - timedelta(minutes=x) for x in (30, 60, 90))
    layer2 = _layer(provider, "XAUUSD", "M30", layer2_opens, as_of, "LAYER_2")
    if layer2["group"] == "BT":
        entry = f"{h:02d}:11"
        return _entry_result(h, entry, "H_11", (entry,), layer2, None, provider_wait_reason=wait_reason)
    if layer2["group"] != "SW":
        return _entry_result(h, None, None, (), layer2, None, provider_wait_reason=wait_reason)
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
        provider_wait_reason=wait_reason,
    )


def _entry_result(hour, entry, branch, candidates, layer2, layer3, entry_state=None, provider_wait_reason="WAIT_MT5_DATA"):
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
        "failure_reason": provider_wait_reason if not entry and entry_state != "PENDING_LAYER3" else None,
    }


def classify_d_relation(pair_direction: str | None, reference_direction: str | None) -> str:
    if pair_direction not in ("BUY", "SELL") or reference_direction not in ("BUY", "SELL"):
        return "UNRESOLVED"
    return "SAME_AS_REFERENCE" if pair_direction == reference_direction else "OPPOSITE_TO_REFERENCE"


def derive_gbpjpy_signal(reference_signal: str | None, d_relation: str) -> str:
    """Derive GBPJPY from the Reference Signal and its D relation."""
    if reference_signal not in ("BUY", "SELL"):
        return "WAIT"
    return reverse_signal(reference_signal) if d_relation == "SAME_AS_REFERENCE" else reference_signal if d_relation == "OPPOSITE_TO_REFERENCE" else "WAIT"


def _mode_branch(day_mode):
    if day_mode is None:
        return None
    if isinstance(day_mode, str):
        return "H_11" if day_mode in ("H_11", "DAY_MODE_H11") else "H_PLUS_1_25" if day_mode in ("H_PLUS_1_25", "DAY_MODE_H_PLUS_1_25") else None
    return getattr(day_mode, "source_branch", None)


def _resolve_single_source_bar(provider, symbol: str, timeframe: str, broker_open: datetime) -> dict | None:
    """Read one bar without an active source, resolving to a single offline source.

    Offline rebuilds have no live heartbeat, so the engine may still read the
    one persisted source.  When multiple sources publish conflicting OHLC for
    the same exact bar this raises ``AmbiguousFeedSourceError`` so the caller
    can fail closed with an explicit ``*_AMBIGUOUS`` reason instead of a silent
    ``*_MISSING``.
    """
    try:
        return provider.get_exact_bar(symbol, timeframe, broker_open)
    except Exception as error:
        if type(error).__name__ == "AmbiguousFeedSourceError":
            raise
        return None


def evaluate_h49_reference_signal(slot_dt, provider, *, as_of=None) -> dict[str, Any]:
    """Resolve the exact H1 XAUUSD candle right before the slot and reverse it.

    Pure helper shared by live evaluation, history rebuild, and the evidence
    drawer.  The source candle is the completed H1 that closes exactly at
    ``slot_dt`` (source_open = slot_dt - 1 hour).  It never consults D GBPUSD,
    Day Mode, or the M30 Layer 2/3 direction.
    """
    source_open = slot_dt - timedelta(hours=1)
    source_close = slot_dt
    cutoff = as_of if as_of is not None else slot_dt
    source_id = _resolve_active_source_id(provider)
    if source_id is not None:
        h1 = _bar(provider, "XAUUSD", "H1", source_open, cutoff, source_id=source_id)
    else:
        # No live active source: allow the single persisted offline source,
        # but fail closed with an explicit ambiguous-source reason on conflict.
        if cutoff is not None and source_open + timedelta(hours=1) > cutoff:
            h1 = None
        else:
            try:
                h1 = _resolve_single_source_bar(provider, "XAUUSD", "H1", source_open)
            except Exception:
                return {
                    "state": "WAIT",
                    "source_symbol": "XAUUSD",
                    "timeframe": "H1",
                    "broker_open_at": source_open.isoformat(),
                    "broker_close_at": source_close.isoformat(),
                    "source_id": None,
                    "resolved_symbol": None,
                    "open_exact": None,
                    "high_exact": None,
                    "low_exact": None,
                    "close_exact": None,
                    "candle_direction": None,
                    "reversed_signal": "WAIT",
                    "failure_reason": "H49_H1_AMBIGUOUS",
                }
    if not h1:
        return {
            "state": "WAIT",
            "source_symbol": "XAUUSD",
            "timeframe": "H1",
            "broker_open_at": source_open.isoformat(),
            "broker_close_at": source_close.isoformat(),
            "source_id": (h1 or {}).get("source_id"),
            "resolved_symbol": (h1 or {}).get("resolved_symbol"),
            "open_exact": None,
            "high_exact": None,
            "low_exact": None,
            "close_exact": None,
            "candle_direction": None,
            "reversed_signal": "WAIT",
            "failure_reason": "H49_H1_MISSING",
        }
    direction = candle_direction(h1)
    reversed_signal = {"TANG": "SELL", "GIAM": "BUY"}.get(direction, "WAIT")
    print(
        f"[H49-H1] date={slot_dt.strftime('%Y-%m-%d')} slot=H{slot_dt.hour}"
        f" source=XAUUSD H1 window={source_open.strftime('%H:%M')}->{source_close.strftime('%H:%M')} Broker"
        f" source_id={h1.get('source_id')}"
        f" open={h1.get('open_exact')} close={h1.get('close_exact')}"
        f" direction={direction} reversed_signal={reversed_signal}"
    )
    return {
        "state": "READY" if reversed_signal != "WAIT" else "WAIT",
        "source_symbol": "XAUUSD",
        "timeframe": "H1",
        "broker_open_at": h1.get("broker_open_at") or source_open.isoformat(),
        "broker_close_at": h1.get("broker_close_at") or source_close.isoformat(),
        "source_id": h1.get("source_id"),
        "resolved_symbol": h1.get("resolved_symbol") or h1.get("canonical_symbol"),
        "open_exact": h1.get("open_exact"),
        "high_exact": h1.get("high_exact"),
        "low_exact": h1.get("low_exact"),
        "close_exact": h1.get("close_exact"),
        "candle_direction": direction,
        "reversed_signal": reversed_signal,
        "failure_reason": None if reversed_signal != "WAIT" else ("H49_H1_DOJI" if direction == "DOJI" else "H49_H1_MISSING"),
    }


def _reference_base(entry, slot_dt, provider, reference_d, day_mode):
    branch = entry.get("entry_branch")
    if entry.get("entry_state") != "READY" or branch not in ("H_11", "H_49", "H_PLUS_1_25"):
        return "WAIT", day_mode, "ENTRY_PLAN_UNRESOLVED", None
    if branch == "H_49":
        h49_ref = evaluate_h49_reference_signal(slot_dt, provider)
        return h49_ref["reversed_signal"], day_mode, "PREVIOUS_XAU_H1_REVERSED", h49_ref
    mode_branch = _mode_branch(day_mode)
    if mode_branch is None:
        mode_branch = branch if branch in ("H_11", "H_PLUS_1_25") else None
        day_mode = mode_branch
    base = reference_d if reference_d in ("BUY", "SELL") else direction_to_signal(reference_d)
    if base == "WAIT" or mode_branch is None:
        return "WAIT", day_mode, "REFERENCE_D_UNRESOLVED", None
    return (base if branch == mode_branch else reverse_signal(base)), day_mode, "REFERENCE_D_DAY_MODE", None


def _requires_reference_d(symbol: str, entry: dict[str, Any]) -> bool:
    """Return whether one pair needs GBPUSD D for this resolved branch."""
    return entry.get("entry_branch") != "H_49" or symbol not in ("XAUUSD", "GBPUSD")


def _signal_failure_reason(symbol: str, entry: dict[str, Any], d_snapshot: dict[str, dict], final_signal: str, h49_ref: dict | None = None, provider_wait_reason: str = "WAIT_MT5_DATA") -> str | None:
    """Keep diagnostics aligned with each pair's actual fail-closed state."""
    if entry.get("failure_reason"):
        return entry["failure_reason"]
    if symbol == "XAUUSD" and h49_ref and h49_ref.get("failure_reason"):
        return h49_ref["failure_reason"]
    reference_d = (d_snapshot.get("GBPUSD") or {}).get("d_direction")
    if _requires_reference_d(symbol, entry) and reference_d not in ("BUY", "SELL"):
        return provider_wait_reason
    if final_signal not in ("BUY", "SELL"):
        return provider_wait_reason
    return None


def final_reverse(slot_hour: int, signal_date) -> tuple[bool, str]:
    weekday = signal_date.weekday()
    # Weekend backtest/rebuild records never invert: there is no weekend rule.
    if weekday >= 5:
        return False, "WEEKEND_NO_REVERSE"
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
    """Run entry, reference, D relation, and final reverse exactly once.

    Only the slot's applicable pairs are derived.  Inactive pairs get
    ``direction=None``, ``pair_signal_state=NOT_APPLICABLE`` and are excluded
    from D reading, evidence, and execution.  XAUUSD == GBPUSD is enforced at
    the final payload with ``SignalInvariantError`` on violation.
    """
    entry = build_entry_plan(slot_dt, slot_hour, provider, as_of)
    provider_wait_reason = _provider_wait_reason(provider)
    reference_d = (d_snapshot.get("GBPUSD") or {}).get("d_direction")
    base_signal, next_mode, base_source, h49_ref = _reference_base(entry, slot_dt, provider, reference_d, day_mode)
    applicable = get_evaluated_pairs_for_hour(int(slot_hour))
    # XAUUSD's D candle is independent evidence even though its Signal is
    # locked to the GBPUSD Reference Signal.  Preserve that relation in the
    # payload so the drawer can explain an opposite XAU D without changing
    # the locked Signal.
    relations: dict[str, Any] = {}
    for symbol in PAIRS:
        if symbol not in applicable:
            relations[symbol] = None
        elif symbol == "XAUUSD":
            relations[symbol] = classify_d_relation(
                (d_snapshot.get("XAUUSD") or {}).get("d_direction"), reference_d
            )
        elif symbol == "GBPUSD":
            relations[symbol] = "REFERENCE"
        else:
            relations[symbol] = classify_d_relation((d_snapshot.get(symbol) or {}).get("d_direction"), reference_d)

    core: dict[str, Any] = {}
    for symbol in PAIRS:
        if symbol not in applicable:
            core[symbol] = None
            continue
        if symbol in ("XAUUSD", "GBPUSD"):
            core[symbol] = base_signal
        elif base_signal in ("BUY", "SELL"):
            relation = relations[symbol]
            if relation == "UNRESOLVED":
                core[symbol] = "WAIT"
            elif symbol == "GBPAUD":
                core[symbol] = base_signal if relation == "SAME_AS_REFERENCE" else reverse_signal(base_signal)
            else:
                core[symbol] = reverse_signal(base_signal) if relation == "SAME_AS_REFERENCE" else base_signal
        else:
            core[symbol] = "WAIT"
    should_reverse, reason = final_reverse(int(slot_hour), slot_dt.date())
    final = dict(core)
    if should_reverse:
        for symbol in applicable:
            if core[symbol] in ("BUY", "SELL"):
                final[symbol] = reverse_signal(core[symbol])
    if final.get("XAUUSD") != final.get("GBPUSD"):
        raise SignalInvariantError(
            f"XAUUSD != GBPUSD invariant violated at H{slot_hour} {slot_dt.date()}: "
            f"{final.get('XAUUSD')} vs {final.get('GBPUSD')}"
        )
    pair_final_reverse_applied = {
        symbol: bool(should_reverse and symbol in applicable and core.get(symbol) in ("BUY", "SELL"))
        for symbol in PAIRS
    }
    pair_times = {symbol: entry.get("entry_time") if symbol in applicable else None for symbol in PAIRS}
    pair_branches = {symbol: entry.get("entry_branch") if symbol in applicable else None for symbol in PAIRS}
    evidence = {
        symbol: _evidence(
            symbol,
            slot_dt,
            entry,
            d_snapshot,
            relations,
            core,
            final,
            pair_final_reverse_applied[symbol],
            reason,
            base_source,
            h49_ref,
            provider_wait_reason,
        )
        for symbol in applicable
    }
    failure_reason = _signal_failure_reason("XAUUSD", entry, d_snapshot, final["XAUUSD"], h49_ref, provider_wait_reason)
    return {
        "logic_version": 88,
        "signal": final["XAUUSD"],
        "signal_state": "READY" if final["XAUUSD"] in ("BUY", "SELL") else "WAIT",
        "entry_time": entry.get("entry_time"),
        "entry_branch": entry.get("entry_branch"),
        "entry_state": entry.get("entry_state"),
        "failure_reason": failure_reason,
        "entry_candidates": entry.get("entry_candidates"),
        "entry_timeframe": entry.get("timeframe"),
        "entry_source_symbol": "XAUUSD",
        "applicable_pairs": list(applicable),
        "pair_dirs": final,
        "core_signal": core["XAUUSD"],
        "core_signals": core,
        "pair_core_signals": core,
        "final_reverse_applied": should_reverse,
        "final_reverse_reason": reason if should_reverse else None,
        "pair_final_reverse_applied": pair_final_reverse_applied,
        "pair_signal_states": {
            symbol: (
                "NOT_APPLICABLE"
                if final[symbol] is None
                else "READY" if final[symbol] in ("BUY", "SELL") else "WAIT"
            )
            for symbol in PAIRS
        },
        "execution_state": {
            symbol: (
                "NOT_APPLICABLE"
                if symbol not in applicable
                else "READY" if final[symbol] in ("BUY", "SELL") and entry.get("entry_state") == "READY" else "WAIT"
            )
            for symbol in PAIRS
        },
        "pair_entry_states": {
            symbol: entry.get("entry_state") if symbol in applicable else "NOT_APPLICABLE"
            for symbol in PAIRS
        },
        "pair_entry_times": pair_times,
        "pair_entry_branches": pair_branches,
        "pair_d_directions": {
            symbol: ((d_snapshot.get(symbol) or {}).get("d_direction") if symbol in applicable else None)
            for symbol in PAIRS
        },
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


def _evidence(symbol, slot_dt, entry, d_snapshot, relations, core, final, reversed_once, reason, base_source, h49_ref=None, provider_wait_reason="WAIT_MT5_DATA"):
    evidence = {
        "evidence_schema_version": 11,
        "logic_version": 88,
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
        "failure_reason": _signal_failure_reason(
            symbol, entry, d_snapshot, final.get(symbol, "WAIT"), h49_ref, provider_wait_reason,
        ),
    }
    if h49_ref and symbol == "XAUUSD":
        evidence["h49_h1_evidence"] = h49_ref
    return evidence
