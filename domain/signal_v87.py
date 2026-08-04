# -*- coding: utf-8 -*-
"""Compatibility shim — the candle signal engine lives in
``legacy/candle_signal_engine/signal_v87.py`` (Phase 5 archive).

Production runs in account audit mode and never imports this module; the shim
only keeps legacy callers and tests working.  See
``legacy/candle_signal_engine`` for the ``ENABLE_LEGACY_CANDLE_SIGNALS`` flag.
"""
from legacy.candle_signal_engine.signal_v87 import (  # noqa: F401
    PAIRS,
    SLOTS,
    SLOT_ACTIVE_PAIRS,
    SignalInvariantError,
    reverse_signal,
    candle_direction,
    direction_to_signal,
    classify_three_candle_group,
    get_evaluated_pairs_for_hour,
    evaluate_slot,
    build_entry_plan,
    final_reverse,
    evaluate_h49_reference_signal,
    derive_gbpjpy_signal,
)
