"""Fail-closed pre-trade risk gate for v88 execution intents.

The gate is pure: it consumes an account snapshot and an explicit high-water
mark. It never queries MT5 and never sends an order.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from domain.risk_state import EquityHighWaterMarkStore


@dataclass(frozen=True)
class RiskGateConfig:
    max_drawdown_pct: float = 6.0
    max_volume: float = 0.01
    require_account_snapshot: bool = True
    require_high_water_mark: bool = True


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str
    drawdown_pct: float | None = None


def evaluate_risk_gate(
    *,
    balance: float | None,
    equity: float | None,
    volume: float,
    peak_equity: float | None = None,
    config: RiskGateConfig | None = None,
) -> RiskDecision:
    """Allow only with valid account evidence and a verified equity high-water mark.

    FDD is measured from the highest observed equity, not today's balance.  A
    missing high-water mark is a hard deny because the gate cannot prove the
    account is within the configured maximum drawdown.
    """
    cfg = config or RiskGateConfig()
    if cfg.require_account_snapshot and (balance is None or equity is None):
        return RiskDecision(False, "ACCOUNT_SNAPSHOT_MISSING")
    if cfg.require_high_water_mark and peak_equity is None:
        return RiskDecision(False, "EQUITY_HIGH_WATER_MARK_MISSING")
    try:
        balance_value = float(balance)
        equity_value = float(equity)
        requested_volume = float(volume)
        peak_value = float(peak_equity) if peak_equity is not None else equity_value
    except (TypeError, ValueError):
        return RiskDecision(False, "ACCOUNT_SNAPSHOT_INVALID")
    if balance_value <= 0 or equity_value < 0:
        return RiskDecision(False, "ACCOUNT_VALUES_INVALID")
    if peak_value <= 0 or peak_value < equity_value:
        return RiskDecision(False, "EQUITY_HIGH_WATER_MARK_INVALID")
    if requested_volume <= 0 or requested_volume > cfg.max_volume:
        return RiskDecision(False, "VOLUME_LIMIT_EXCEEDED")
    drawdown_pct = max(0.0, (peak_value - equity_value) / peak_value * 100.0)
    if drawdown_pct >= cfg.max_drawdown_pct:
        return RiskDecision(False, "DRAWDOWN_LIMIT_EXCEEDED", drawdown_pct)
    return RiskDecision(True, "ALLOW", drawdown_pct)


def evaluate_mt5_account_risk(
    mt5_module,
    *,
    volume: float,
    risk_state_dir: str | None = None,
    account_id: str | int | None = None,
    initial_peak_equity: float | None = None,
    config: RiskGateConfig | None = None,
) -> RiskDecision:
    """Evaluate a live MT5 account and persist its equity high-water mark.

    A live account without an account snapshot, stable account id, or trusted
    high-water mark is denied. The first high-water mark must be explicitly
    provisioned via ``initial_peak_equity``; current equity is never silently
    promoted to a trusted peak.
    """
    account = mt5_module.account_info()
    balance = getattr(account, "balance", None) if account is not None else None
    equity = getattr(account, "equity", None) if account is not None else None
    login = account_id if account_id is not None else (
        getattr(account, "login", None) if account is not None else None
    )
    if login is None:
        return RiskDecision(False, "ACCOUNT_ID_MISSING")
    root = Path(risk_state_dir or Path(__file__).resolve().parents[1])
    store = EquityHighWaterMarkStore(str(root), str(login))
    state = store.read()
    if state.peak_equity is None and initial_peak_equity is not None:
        try:
            store.initialize(float(initial_peak_equity))
        except (TypeError, ValueError, TimeoutError) as error:
            return RiskDecision(False, f"EQUITY_HIGH_WATER_MARK_INIT_FAILED:{error}")
        state = store.read()
    if state.peak_equity is not None and equity is not None:
        try:
            state = store.observe(float(equity))
        except (TypeError, ValueError, TimeoutError) as error:
            return RiskDecision(False, f"EQUITY_HIGH_WATER_MARK_UPDATE_FAILED:{error}")
    return evaluate_risk_gate(
        balance=balance,
        equity=equity,
        volume=volume,
        peak_equity=state.peak_equity,
        config=config,
    )
