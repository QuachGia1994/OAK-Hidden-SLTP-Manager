"""Fail-closed pre-trade risk gate for v88 execution intents.

The gate is pure: it consumes an account snapshot and execution intent facts.
It never queries MT5 and never sends an order.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskGateConfig:
    max_drawdown_pct: float = 6.0
    max_volume: float = 0.01
    require_account_snapshot: bool = True


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str
    drawdown_pct: float | None = None


def evaluate_risk_gate(*, balance: float | None, equity: float | None, volume: float,
                       config: RiskGateConfig | None = None) -> RiskDecision:
    """Allow only when account evidence exists and current drawdown/volume fit limits."""
    cfg = config or RiskGateConfig()
    if cfg.require_account_snapshot and (balance is None or equity is None):
        return RiskDecision(False, "ACCOUNT_SNAPSHOT_MISSING")
    try:
        balance_value = float(balance)
        equity_value = float(equity)
        requested_volume = float(volume)
    except (TypeError, ValueError):
        return RiskDecision(False, "ACCOUNT_SNAPSHOT_INVALID")
    if balance_value <= 0 or equity_value < 0:
        return RiskDecision(False, "ACCOUNT_VALUES_INVALID")
    if requested_volume <= 0 or requested_volume > cfg.max_volume:
        return RiskDecision(False, "VOLUME_LIMIT_EXCEEDED")
    drawdown_pct = max(0.0, (balance_value - equity_value) / balance_value * 100.0)
    if drawdown_pct > cfg.max_drawdown_pct:
        return RiskDecision(False, "DRAWDOWN_LIMIT_EXCEEDED", drawdown_pct)
    return RiskDecision(True, "ALLOW", drawdown_pct)
