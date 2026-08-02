"""Standardized market-data provider health contract.

Both ``MT5MarketDataProvider`` and ``MT4LegacyMarketDataProvider`` return a
:class:`MarketDataHealth` from ``get_health()`` so consumers never mix ``dict``
and attribute access (the historical ``'dict' object has no attribute 'fresh'``
failure mode).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class MarketDataHealth:
    """Standardized provider health value."""

    state: str
    fresh: bool
    degraded: bool
    age_seconds: float
    observed_at_utc: str
    clock_verified: bool
    error: str = ""


def health_value(health, key, default=None):
    """Read ``key`` from a health object or mapping without coupling to either."""
    if health is None:
        return default
    if isinstance(health, Mapping):
        return health.get(key, default)
    return getattr(health, key, default)


__all__ = ["MarketDataHealth", "health_value"]
