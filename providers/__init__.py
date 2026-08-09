"""Market-data provider package for the OAK Signal engine.

The Signal engine consumes bars exclusively through a ``MarketDataProvider``
that implements as ``name`` plus ``get_health``, ``get_bar_now``,
``get_broker_utc_offset``, ``is_broker_utc_offset_verified``, ``get_bars`` and
``get_exact_bar``.

The default and only provider is the MetaTrader 5 Python API
(:class:`providers.mt5_market_data_provider.MT5MarketDataProvider`).
"""
from __future__ import annotations

from providers.health_contract import MarketDataHealth, health_value
from providers.mt5_market_data_provider import MT5MarketDataProvider

MARKET_DATA_PROVIDER_DEFAULT = "MT5"
MARKET_DATA_PROVIDER_VALUES = ("MT5",)
MARKET_DATA_SCHEMA_VERSION = 1


__all__ = [
    "MT5MarketDataProvider",
    "MARKET_DATA_PROVIDER_DEFAULT",
    "MARKET_DATA_PROVIDER_VALUES",
    "MARKET_DATA_SCHEMA_VERSION",
    "MarketDataHealth",
    "health_value",
]