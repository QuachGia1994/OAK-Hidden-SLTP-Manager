# -*- coding: utf-8 -*-
"""Legacy candle-based signal engine archive (Phase 5 of the OAK refactor).

The candle signal engine (M30/H1/H4 BUY/SELL generation, D-Direction, D-H4,
Layer 1/2/3, H49-H1, history signal rebuild, candle evidence) is no longer part
of the production runtime.  Per the refactor plan:

- Production runs in ACCOUNT AUDIT mode: account_info, positions_get,
  history_deals_get and orders_get only — no candle preload, no signal
  history rebuild, no D-Direction computation.
- The engine source is archived here (plus re-export shims at the original
  import paths so existing callers and tests keep working) for rollback and
  reference.  It is NEVER started automatically.
- ``ENABLE_LEGACY_CANDLE_SIGNALS`` (default ``"false"``) re-enables the
  candle paths explicitly for backtesting / reference runs.
"""
import os

#: Env flag that re-enables the legacy candle signal engine.
_LEGACY_FLAG = "ENABLE_LEGACY_CANDLE_SIGNALS"


def legacy_candle_signals_enabled() -> bool:
    """Return True only when the legacy candle engine is explicitly enabled.

    Default is ``False`` (account audit mode).  Accepts ``1/true/yes/on``
    (case-insensitive) as truthy values.
    """
    raw = os.environ.get(_LEGACY_FLAG, "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


__all__ = ["legacy_candle_signals_enabled", "LEGACY_CANDLE_SIGNALS_FLAG"]
LEGACY_CANDLE_SIGNALS_FLAG = _LEGACY_FLAG
