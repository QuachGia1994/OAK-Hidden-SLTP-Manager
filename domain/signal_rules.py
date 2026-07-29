"""Pure signal rules shared by MT5 runtime and comparison server."""

ACTIVE_SIGNAL_HOURS = frozenset({3, 7, 9, 12, 14, 16})


def reverse_signal(signal):
    if signal == "BUY":
        return "SELL"
    if signal == "SELL":
        return "BUY"
    return "WAIT"


def direction_to_signal(direction):
    if direction == "TANG":
        return "BUY"
    if direction == "GIAM":
        return "SELL"
    return "WAIT"


def classify_four_h1_group(directions):
    """Classify C1..C4 with the canonical ten-rule SW/BT matrix."""
    if len(directions) != 4 or any(value not in ("TANG", "GIAM") for value in directions):
        return None
    c1, c2, c3, c4 = directions
    if c1 == "TANG":
        if c2 == "TANG" and c3 == "TANG":
            return "SW"
        if c2 == "GIAM" and c3 == "TANG":
            return "SW" if c4 == "GIAM" else "BT"
        return "SW" if c2 == "GIAM" else "BT"
    if c2 == "GIAM" and c3 == "GIAM":
        return "SW"
    if c2 == "TANG" and c3 == "GIAM":
        return "SW" if c4 == "TANG" else "BT"
    return "SW" if c2 == "TANG" else "BT"


def derive_signal_base(first_h1_direction, group):
    """Derive Signal Base from C1, reversing only the SW group."""
    base_signal = direction_to_signal(first_h1_direction)
    if base_signal == "WAIT" or group not in ("SW", "BT"):
        return "WAIT"
    return reverse_signal(base_signal) if group == "SW" else base_signal


def apply_entry_rule(signal_base, entry_time, slot_hour):
    """Apply the entry branch and the exact 15:25/16:49 exceptions."""
    if signal_base not in ("BUY", "SELL"):
        return "WAIT"
    h = int(slot_hour)
    if h not in ACTIVE_SIGNAL_HOURS:
        return "WAIT"
    if entry_time == f"{h + 1:02d}:25":
        final_signal = signal_base
    elif entry_time in (f"{h:02d}:11", f"{h:02d}:49"):
        final_signal = reverse_signal(signal_base)
    else:
        return "WAIT"
    return reverse_signal(final_signal) if entry_time in ("15:25", "16:49") else final_signal


_M15_GROUPS = {
    ("TANG", "TANG", "TANG"): "SW",
    ("GIAM", "TANG", "TANG"): "SW",
    ("GIAM", "TANG", "GIAM"): "BT",
    ("GIAM", "GIAM", "TANG"): "BT",
    ("GIAM", "GIAM", "GIAM"): "SW",
    ("TANG", "GIAM", "GIAM"): "SW",
    ("TANG", "GIAM", "TANG"): "BT",
    ("TANG", "TANG", "GIAM"): "BT",
}


def classify_three_candle_group(directions):
    """Classify three directions with the legacy eight-case M15 matrix."""
    return _M15_GROUPS.get(tuple(directions))


def derive_xau_entry_basis(base_direction, pattern_directions, offset15_direction):
    """Return the Stage-A XAU comparison signal, or WAIT when incomplete."""
    group = classify_three_candle_group(pattern_directions)
    base_signal = direction_to_signal(base_direction)
    offset_signal = direction_to_signal(offset15_direction)
    if group is None or "WAIT" in (base_signal, offset_signal):
        return "WAIT"
    provisional = reverse_signal(base_signal) if group == "SW" else base_signal
    return reverse_signal(provisional) if provisional == offset_signal else provisional


def select_xau_entry_time(slot, xau_signal, gbpaud_initial_direction, followup_direction=None):
    """Resolve the existing Stage-A entry schedule from pure directions."""
    h = int(slot)
    initial = direction_to_signal(gbpaud_initial_direction)
    if h not in ACTIVE_SIGNAL_HOURS or xau_signal not in ("BUY", "SELL") or initial == "WAIT":
        return {"state": "WAIT", "entry_time": None}
    relation = "SAME" if xau_signal == initial else "OPPOSITE"
    if h in (3, 7) and relation == "SAME":
        return {"state": "READY", "entry_time": f"{h:02d}:11"}
    if h >= 9 and relation == "OPPOSITE":
        return {"state": "READY", "entry_time": f"{h:02d}:11"}
    followup = direction_to_signal(followup_direction)
    if followup == "WAIT":
        return {"state": "PENDING_FOLLOWUP", "entry_time": None}
    followup_relation = "SAME" if xau_signal == followup else "OPPOSITE"
    if h == 3:
        entry = "04:25" if followup_relation == "OPPOSITE" else "03:49"
    elif h == 7:
        entry = "08:25" if followup_relation == "OPPOSITE" else "07:49"
    else:
        entry = f"{h + 1:02d}:25" if followup_relation == "SAME" else f"{h:02d}:49"
    return {"state": "READY", "entry_time": entry}
