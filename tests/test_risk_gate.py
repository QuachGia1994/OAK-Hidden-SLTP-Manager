from pathlib import Path

import pytest

from domain.risk_gate import RiskGateConfig, evaluate_risk_gate
from domain.risk_state import EquityHighWaterMarkStore


def test_drawdown_is_measured_from_peak_equity():
    decision = evaluate_risk_gate(
        balance=5000,
        equity=5200,
        peak_equity=5500,
        volume=0.01,
    )
    assert decision.allowed is True
    assert decision.drawdown_pct == pytest.approx(5.45454545)


def test_exact_six_percent_is_denied():
    decision = evaluate_risk_gate(
        balance=5000,
        equity=5170,
        peak_equity=5500,
        volume=0.01,
    )
    assert decision.allowed is False
    assert decision.reason == "DRAWDOWN_LIMIT_EXCEEDED"
    assert decision.drawdown_pct == pytest.approx(6.0)


def test_below_six_percent_is_allowed():
    decision = evaluate_risk_gate(
        balance=5000,
        equity=5171,
        peak_equity=5500,
        volume=0.01,
    )
    assert decision.allowed is True
    assert decision.drawdown_pct < 6.0


def test_missing_peak_is_fail_closed():
    decision = evaluate_risk_gate(balance=5000, equity=5000, volume=0.01)
    assert decision.allowed is False
    assert decision.reason == "EQUITY_HIGH_WATER_MARK_MISSING"


def test_peak_must_not_be_below_current_equity():
    decision = evaluate_risk_gate(
        balance=5000,
        equity=5000,
        peak_equity=4999,
        volume=0.01,
    )
    assert decision.allowed is False
    assert decision.reason == "EQUITY_HIGH_WATER_MARK_INVALID"


def test_missing_account_snapshot_is_fail_closed():
    decision = evaluate_risk_gate(
        balance=None,
        equity=None,
        peak_equity=5000,
        volume=0.01,
    )
    assert decision.allowed is False
    assert decision.reason == "ACCOUNT_SNAPSHOT_MISSING"


def test_hwm_initialise_and_observe_never_lowers(tmp_path: Path):
    store = EquityHighWaterMarkStore(str(tmp_path), "123")
    assert store.read().peak_equity is None
    assert store.initialize(5000).peak_equity == 5000
    assert store.observe(4900).peak_equity == 5000
    assert store.observe(5100).peak_equity == 5100
    assert store.observe(5001).peak_equity == 5100
    assert store.read().peak_equity == 5100


def test_hwm_survives_restart(tmp_path: Path):
    first = EquityHighWaterMarkStore(str(tmp_path), "123")
    first.initialize(5000)
    first.observe(5200)
    second = EquityHighWaterMarkStore(str(tmp_path), "123")
    assert second.read().peak_equity == 5200


def test_reinitialising_existing_hwm_with_different_value_is_rejected(tmp_path: Path):
    store = EquityHighWaterMarkStore(str(tmp_path), "123")
    store.initialize(5000)
    with pytest.raises(ValueError, match="already initialized"):
        store.initialize(4900)


def test_custom_limit_remains_supported():
    decision = evaluate_risk_gate(
        balance=5000,
        equity=9500,
        peak_equity=10000,
        volume=0.01,
        config=RiskGateConfig(max_drawdown_pct=5.0),
    )
    assert decision.allowed is False
    assert decision.drawdown_pct == pytest.approx(5.0)
