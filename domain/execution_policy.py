"""Fail-closed execution policy for v88 signal intents.

This module decides whether a signal is eligible to reach the execution gateway.
It never talks to MT5 and never places orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ExecutionPolicyConfig:
    enabled: bool = False
    allow_weekends: bool = False
    max_entry_age_seconds: int = 90


@dataclass(frozen=True)
class ExecutionDecision:
    allowed: bool
    reason: str


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def evaluate_execution_policy(result: dict, slot_hour: int, *, now_utc: datetime | None = None,
                               config: ExecutionPolicyConfig | None = None) -> ExecutionDecision:
    """Return ALLOW only for a complete, current, explicitly enabled signal."""
    cfg = config or ExecutionPolicyConfig()
    if not cfg.enabled:
        return ExecutionDecision(False, "EXECUTION_DISABLED")
    if not isinstance(result, dict):
        return ExecutionDecision(False, "INVALID_SIGNAL")
    if now_utc is not None and _utc(now_utc).weekday() >= 5 and not cfg.allow_weekends:
        return ExecutionDecision(False, "WEEKEND_EXECUTION_DISABLED")
    if int(result.get("logic_version", -1)) != 88:
        return ExecutionDecision(False, "LOGIC_VERSION_MISMATCH")
    if int(result.get("hour", slot_hour)) != int(slot_hour):
        return ExecutionDecision(False, "SLOT_MISMATCH")
    if result.get("signal_state") != "READY" or result.get("entry_state") != "READY":
        return ExecutionDecision(False, "SIGNAL_NOT_READY")
    if result.get("signal") not in ("BUY", "SELL"):
        return ExecutionDecision(False, "NO_ACTIONABLE_SIGNAL")
    if not result.get("entry_time"):
        return ExecutionDecision(False, "ENTRY_TIME_MISSING")
    applicable = result.get("applicable_pairs") or ()
    directions = result.get("pair_dirs") or {}
    states = result.get("pair_signal_states") or {}
    entries = result.get("pair_entry_times") or {}
    if not applicable:
        return ExecutionDecision(False, "NO_APPLICABLE_PAIRS")
    if any(directions.get(symbol) not in ("BUY", "SELL") or states.get(symbol) != "READY" for symbol in applicable):
        return ExecutionDecision(False, "PAIR_NOT_READY")
    if len({entries.get(symbol) for symbol in applicable}) != 1:
        return ExecutionDecision(False, "COMMON_ENTRY_MISMATCH")
    current = _utc(now_utc) if now_utc is not None else None
    entry_utc = result.get("entry_at_utc")
    if entry_utc and current is not None:
        try:
            parsed = datetime.fromisoformat(str(entry_utc).replace("Z", "+00:00"))
            parsed = _utc(parsed)
            age = (current - parsed).total_seconds()
            if age < -cfg.max_entry_age_seconds:
                return ExecutionDecision(False, "ENTRY_IN_FUTURE")
            if age > cfg.max_entry_age_seconds:
                return ExecutionDecision(False, "ENTRY_EXPIRED")
        except ValueError:
            return ExecutionDecision(False, "ENTRY_TIMESTAMP_INVALID")
    return ExecutionDecision(True, "ALLOW")


def evaluate_execution_intent(intent: dict, *, now_utc: datetime | None = None,
                              config: ExecutionPolicyConfig | None = None) -> ExecutionDecision:
    """Re-check a persisted intent immediately before MT5 execution."""
    cfg = config or ExecutionPolicyConfig()
    if not cfg.enabled:
        return ExecutionDecision(False, "EXECUTION_DISABLED")
    if not isinstance(intent, dict) or int(intent.get("logic_version", -1)) != 88:
        return ExecutionDecision(False, "LOGIC_VERSION_MISMATCH")
    if now_utc is not None and _utc(now_utc).weekday() >= 5 and not cfg.allow_weekends:
        return ExecutionDecision(False, "WEEKEND_EXECUTION_DISABLED")
    if intent.get("direction") not in ("BUY", "SELL"):
        return ExecutionDecision(False, "NO_ACTIONABLE_INTENT")
    if not intent.get("common_entry_time") or not intent.get("entry_at_utc"):
        return ExecutionDecision(False, "ENTRY_METADATA_MISSING")
    current = _utc(now_utc) if now_utc is not None else None
    if current is not None:
        try:
            parsed = datetime.fromisoformat(str(intent["entry_at_utc"]).replace("Z", "+00:00"))
            age = (current - _utc(parsed)).total_seconds()
        except ValueError:
            return ExecutionDecision(False, "ENTRY_TIMESTAMP_INVALID")
        if age < -cfg.max_entry_age_seconds:
            return ExecutionDecision(False, "ENTRY_IN_FUTURE")
        if age > cfg.max_entry_age_seconds:
            return ExecutionDecision(False, "ENTRY_EXPIRED")
    return ExecutionDecision(True, "ALLOW")
