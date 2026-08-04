"""Pure rules for GBP signals and the two-layer XAU M30 entry engine."""

ACTIVE_SIGNAL_HOURS = frozenset({3, 7, 9, 12, 14, 16})


def reverse_signal(signal):
    """Return the opposite actionable direction, otherwise ``WAIT``."""
    if signal == "BUY":
        return "SELL"
    if signal == "SELL":
        return "BUY"
    return "WAIT"


def direction_to_signal(direction):
    """Map one resolved candle direction to an actionable signal."""
    if direction == "TANG":
        return "BUY"
    if direction == "GIAM":
        return "SELL"
    return "WAIT"


def classify_four_candle_group(directions):
    """Classify C1..C4 with the exhaustive canonical ten-rule matrix."""
    values = list(directions or ())
    unresolved = {"group": None, "rule_number": None, "directions": values}
    if len(values) != 4 or any(value not in ("TANG", "GIAM") for value in values):
        return unresolved

    c1, c2, c3, c4 = values
    if (c1, c2, c3) == ("TANG", "TANG", "TANG"):
        result = ("SW", 1)
    elif (c1, c2, c3, c4) == ("TANG", "GIAM", "TANG", "GIAM"):
        result = ("SW", 2)
    elif (c1, c2, c3) == ("TANG", "GIAM", "GIAM"):
        result = ("SW", 3)
    elif (c1, c2, c3) == ("TANG", "TANG", "GIAM"):
        result = ("BT", 4)
    elif (c1, c2, c3, c4) == ("TANG", "GIAM", "TANG", "TANG"):
        result = ("BT", 5)
    elif (c1, c2, c3) == ("GIAM", "GIAM", "GIAM"):
        result = ("SW", 6)
    elif (c1, c2, c3, c4) == ("GIAM", "TANG", "GIAM", "TANG"):
        result = ("SW", 7)
    elif (c1, c2, c3) == ("GIAM", "TANG", "TANG"):
        result = ("SW", 8)
    elif (c1, c2, c3) == ("GIAM", "GIAM", "TANG"):
        result = ("BT", 9)
    else:
        result = ("BT", 10)
    return {"group": result[0], "rule_number": result[1], "directions": values}


def classify_three_candle_group(directions):
    """Classify the H3 XAU layer-one window with the canonical 3-candle model."""
    values = list(directions or ())
    unresolved = {"group": None, "rule_number": None, "directions": values}
    if len(values) != 3 or any(value not in ("TANG", "GIAM") for value in values):
        return unresolved
    rules = {
        ("TANG", "TANG", "TANG"): ("SW", 1),
        ("GIAM", "TANG", "TANG"): ("SW", 2),
        ("GIAM", "TANG", "GIAM"): ("BT", 3),
        ("GIAM", "GIAM", "TANG"): ("BT", 4),
        ("GIAM", "GIAM", "GIAM"): ("SW", 5),
        ("TANG", "GIAM", "GIAM"): ("SW", 6),
        ("TANG", "GIAM", "TANG"): ("BT", 7),
        ("TANG", "TANG", "GIAM"): ("BT", 8),
    }
    group, rule_number = rules[tuple(values)]
    return {"group": group, "rule_number": rule_number, "directions": values}


def derive_gbp_signal_from_layer1(layer1_base_direction, layer1_group):
    """Derive one GBP signal from layer-one Base and SW/BT classification."""
    base_signal = direction_to_signal(layer1_base_direction)
    if base_signal == "WAIT" or layer1_group not in ("SW", "BT"):
        return {
            "base_signal": base_signal,
            "signal_action": None,
            "signal": "WAIT",
        }
    reverse_base = layer1_group == "SW"
    return {
        "base_signal": base_signal,
        "signal_action": "REVERSE_BASE" if reverse_base else "KEEP_BASE",
        "signal": reverse_signal(base_signal) if reverse_base else base_signal,
    }


def entry_candidates(slot_hour, layer1_group):
    """Return the XAU entry pair selected by layer one."""
    try:
        hour = int(slot_hour)
    except (TypeError, ValueError):
        return None
    if hour not in ACTIVE_SIGNAL_HOURS or layer1_group not in ("SW", "BT"):
        return None
    if layer1_group == "SW":
        late = "04:25" if hour == 3 else f"{hour + 1:02d}:25"
        return (f"{hour:02d}:49", late)
    return (f"{hour:02d}:11", f"{hour:02d}:49")


def select_two_layer_entry(slot_hour, layer1_group, layer2_group):
    """Use XAU layer two: SW selects early and BT selects late."""
    candidates = entry_candidates(slot_hour, layer1_group)
    if candidates is None or layer2_group not in ("SW", "BT"):
        return {
            "state": "WAIT",
            "entry_time": None,
            "entry_candidates": list(candidates) if candidates else [],
            "entry_selection": None,
        }
    selection = "EARLY" if layer2_group == "SW" else "LATE"
    entry_time = candidates[0] if selection == "EARLY" else candidates[1]
    return {
        "state": "READY",
        "entry_time": entry_time,
        "entry_candidates": list(candidates),
        "entry_selection": selection,
    }


def deferred_gbp_entry_time(xau_entry_time):
    """Return the next whole Broker hour strictly after the XAU entry."""
    try:
        hour_text, minute_text = str(xau_entry_time).split(":", 1)
        hour, minute = int(hour_text), int(minute_text)
    except (TypeError, ValueError):
        return None
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    return f"{(hour + 1) % 24:02d}:00"
