# -*- coding: utf-8 -*-
"""Legacy MT4 Feed market-data provider (hidden/experimental).

Retained for reference and opt-in use via ``enable_legacy_mt4_feed=true``.  It
is **not** the default and never auto-starts.  In MT5 mode this provider is
never constructed and its SQLite store is never read.
"""
from __future__ import annotations

from providers.health_contract import MarketDataHealth


class MT4LegacyMarketDataProvider:
    """``MarketDataProvider`` backed by the legacy MT4 Feed server store.

    Disabled by default.  Only constructed when a developer explicitly opts into
    ``enable_legacy_mt4_feed=true`` (or provider ``MT4_LEGACY``).
    """

    name = "MT4"

    def __init__(self, feed_store=None):
        self._feed_store = feed_store

    @property
    def enabled(self):
        return False

    @property
    def store(self):
        return self._feed_store

    def get_health(self):
        return MarketDataHealth(
            state="disabled",
            fresh=False,
            degraded=False,
            age_seconds=-1.0,
            observed_at_utc="",
            clock_verified=False,
        )

    def get_broker_now(self):
        raise RuntimeError("MT4_LEGACY is disabled; the MT5 provider owns the market-data clock")

    def get_broker_utc_offset(self, broker_date=None, **kwargs):
        raise RuntimeError("MT4_LEGACY is disabled; use the MT5 provider")

    def is_broker_utc_offset_verified(self, broker_date=None):
        return False

    def get_bars(self, symbol, timeframe, start_broker, end_broker):
        return []

    def get_exact_bar(self, symbol, timeframe, broker_open, *, source_id=None):
        return None

    def get_active_source_id(self, max_age_seconds: int = 60):
        return None

    def clear(self):
        pass