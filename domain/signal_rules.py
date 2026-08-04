# -*- coding: utf-8 -*-
"""Compatibility shim — the pre-v87 candle rules live in
``legacy/candle_signal_engine/signal_rules.py`` (Phase 5 archive).

Production runs in account audit mode and never imports this module; the shim
only keeps legacy callers and tests working.  See
``legacy/candle_signal_engine`` for the ``ENABLE_LEGACY_CANDLE_SIGNALS`` flag.
"""
from legacy.candle_signal_engine.signal_rules import (  # noqa: F401
    reverse_signal,
    direction_to_signal,
    classify_four_candle_group,
    classify_three_candle_group,
    derive_gbp_signal_from_layer1,
    entry_candidates,
    select_two_layer_entry,
    deferred_gbp_entry_time,
)
