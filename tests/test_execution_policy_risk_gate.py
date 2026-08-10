from datetime import datetime, timezone, timedelta

from domain.execution_policy import (
    ExecutionPolicyConfig,
    evaluate_execution_intent,
    evaluate_execution_policy,
)
from domain.risk_gate import RiskGateConfig, evaluate_risk_gate


def ready_result(entry_at_utc=None):
    return {
        "logic_version": 88,
        "hour": 12,
        "signal": "BUY",
        "signal_state": "READY",
        "entry_state": "READY",
        "entry_time": "13:00",
        "entry_at_utc": entry_at_utc,
        "applicable_pairs": ["XAUUSD", "GBPUSD"],
        "pair_dirs": {"XAUUSD": "BUY", "GBPUSD": "BUY"},
        "pair_signal_states": {"XAUUSD": "READY", "GBPUSD": "READY"},
        "pair_entry_times": {"XAUUSD": "13:00", "GBPUSD": "13:00"},
    }


def test_execution_policy_is_fail_closed_by_default():
    decision = evaluate_execution_policy(ready_result(), 12)
    assert not decision.allowed
    assert decision.reason == "EXECUTION_DISABLED"


def test_execution_policy_allows_complete_enabled_signal():
    now = datetime(2026, 8, 10, 6, 0, tzinfo=timezone.utc)
    result = ready_result((now - timedelta(seconds=10)).isoformat())
    decision = evaluate_execution_policy(
        result, 12, now_utc=now, config=ExecutionPolicyConfig(enabled=True)
    )
    assert decision.allowed
    assert decision.reason == "ALLOW"


def test_execution_policy_rejects_expired_entry():
    now = datetime(2026, 8, 10, 6, 0, tzinfo=timezone.utc)
    result = ready_result((now - timedelta(seconds=91)).isoformat())
    decision = evaluate_execution_policy(
        result, 12, now_utc=now, config=ExecutionPolicyConfig(enabled=True)
    )
    assert not decision.allowed
    assert decision.reason == "ENTRY_EXPIRED"


def test_execution_policy_rejects_incomplete_pair():
    result = ready_result()
    result["pair_signal_states"]["GBPUSD"] = "WAIT"
    decision = evaluate_execution_policy(
        result, 12, config=ExecutionPolicyConfig(enabled=True)
    )
    assert not decision.allowed
    assert decision.reason == "PAIR_NOT_READY"


def test_execution_intent_rejects_expired_persisted_intent():
    now = datetime(2026, 8, 10, 6, 0, tzinfo=timezone.utc)
    intent = {
        "logic_version": 88,
        "direction": "BUY",
        "common_entry_time": "12:00",
        "entry_at_utc": (now - timedelta(seconds=91)).isoformat(),
    }
    decision = evaluate_execution_intent(
        intent,
        now_utc=now,
        config=ExecutionPolicyConfig(enabled=True),
    )
    assert not decision.allowed
    assert decision.reason == "ENTRY_EXPIRED"


def test_risk_gate_rejects_missing_account_snapshot():
    decision = evaluate_risk_gate(balance=None, equity=None, volume=0.01)
    assert not decision.allowed
    assert decision.reason == "ACCOUNT_SNAPSHOT_MISSING"


def test_risk_gate_rejects_more_than_six_percent_drawdown():
    decision = evaluate_risk_gate(
        balance=5000, equity=4699, volume=0.01,
        config=RiskGateConfig(max_drawdown_pct=6.0, max_volume=0.05),
    )
    assert not decision.allowed
    assert decision.reason == "DRAWDOWN_LIMIT_EXCEEDED"
    assert decision.drawdown_pct > 6.0


def test_risk_gate_allows_within_limits():
    decision = evaluate_risk_gate(
        balance=5000, equity=4800, volume=0.05,
        config=RiskGateConfig(max_drawdown_pct=6.0, max_volume=0.05),
    )
    assert decision.allowed
    assert decision.reason == "ALLOW"


def test_risk_gate_rejects_volume_limit():
    decision = evaluate_risk_gate(
        balance=5000, equity=5000, volume=0.06,
        config=RiskGateConfig(max_drawdown_pct=6.0, max_volume=0.05),
    )
    assert not decision.allowed
    assert decision.reason == "VOLUME_LIMIT_EXCEEDED"
