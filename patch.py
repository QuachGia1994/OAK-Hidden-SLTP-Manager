import re

with open("mt5_signal_bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Replace evaluate_h11_classification logic
old_evaluate = '''def evaluate_h11_classification(broker_dt, symbol="XAUUSD"):
    """Evaluate 4 H1 candles (H=10, H=9, H=8, H=7) at slot H=11.
    
    Returns (group, detail_str, candles_list) where group is "SW" (Sideway) or "BT" (Bình thường).
    """
    if broker_dt is None:
        return "BT", "H10:Tăng, H9:Tăng, H8:Giảm, H7:Giảm [Rule 3]", []

    dirs = {}
    vn_dirs = {}
    candles = []
    for h in (7, 8, 9, 10):'''

new_evaluate = '''def evaluate_classification_for_slot(broker_dt, slot_hour, symbol="XAUUSD"):
    """Evaluate 4 H1 candles ending at slot_hour - 1.
    For slot_hour=11, evaluates H=10, 9, 8, 7.
    """
    h1, h2, h3, h4 = slot_hour - 1, slot_hour - 2, slot_hour - 3, slot_hour - 4
    if broker_dt is None:
        return "BT", f"H{h1}:Tăng, H{h2}:Tăng, H{h3}:Giảm, H{h4}:Giảm [Rule 3]", []

    dirs = {}
    vn_dirs = {}
    candles = []
    for h in (h4, h3, h2, h1):'''
content = content.replace(old_evaluate, new_evaluate)

old_d10 = '''    d10, d9, d8, d7 = dirs[10], dirs[9], dirs[8], dirs[7]

    if d10 == "TANG":
        if d9 == "GIAM" and d8 == "TANG" and d7 == "GIAM":
            group, rule_num = "SW", 1
        elif d9 == "GIAM" and d8 == "TANG" and d7 == "TANG":
            group, rule_num = "BT", 2
        elif d9 == "TANG" and d8 == "GIAM":
            group, rule_num = "BT", 3
        elif d9 == "TANG" and d8 == "TANG":
            group, rule_num = "SW", 4
        else:
            group, rule_num = "SW", 5
    else:
        if d9 == "TANG" and d8 == "GIAM" and d7 == "TANG":
            group, rule_num = "SW", 6
        elif d9 == "TANG" and d8 == "GIAM" and d7 == "GIAM":
            group, rule_num = "BT", 7
        elif d9 == "GIAM" and d8 == "TANG":
            group, rule_num = "BT", 8
        elif d9 == "GIAM" and d8 == "GIAM":
            group, rule_num = "SW", 9
        else:
            group, rule_num = "SW", 10

    detail = f"H10:{vn_dirs[10]}, H9:{vn_dirs[9]}, H8:{vn_dirs[8]}, H7:{vn_dirs[7]}"
    return group, detail, candles'''

new_d10 = '''    d1, d2, d3, d4 = dirs[h1], dirs[h2], dirs[h3], dirs[h4]

    if d1 == "TANG":
        if d2 == "GIAM" and d3 == "TANG" and d4 == "GIAM":
            group, rule_num = "SW", 1
        elif d2 == "GIAM" and d3 == "TANG" and d4 == "TANG":
            group, rule_num = "BT", 2
        elif d2 == "TANG" and d3 == "GIAM":
            group, rule_num = "BT", 3
        elif d2 == "TANG" and d3 == "TANG":
            group, rule_num = "SW", 4
        else:
            group, rule_num = "SW", 5
    else:
        if d2 == "TANG" and d3 == "GIAM" and d4 == "TANG":
            group, rule_num = "SW", 6
        elif d2 == "TANG" and d3 == "GIAM" and d4 == "GIAM":
            group, rule_num = "BT", 7
        elif d2 == "GIAM" and d3 == "TANG":
            group, rule_num = "BT", 8
        elif d2 == "GIAM" and d3 == "GIAM":
            group, rule_num = "SW", 9
        else:
            group, rule_num = "SW", 10

    detail = f"H{h1}:{vn_dirs[h1]}, H{h2}:{vn_dirs[h2]}, H{h3}:{vn_dirs[h3]}, H{h4}:{vn_dirs[h4]}"
    return group, detail, candles

def evaluate_h11_classification(broker_dt, symbol="XAUUSD"):
    """Backward compatible wrapper for H=11 logic."""
    return evaluate_classification_for_slot(broker_dt, 11, symbol)'''

content = content.replace(old_d10, new_d10)

# 2. Replace is_xau_no_trade_label_slot
old_is_xau = '''def is_xau_no_trade_label_slot(H, broker_dt=None, weekday=None):
    """Return True if slot H has a no-gold label attached based on yesterday's H=11 SW/BT."""
    try:
        h = int(H)
    except (TypeError, ValueError):
        return False
    if h in (12, 13, 15):
        if broker_dt is not None:
            rules = get_h11_priority_and_nogold_rules(broker_dt)
            return rules["has_nogold_label"]
    return False'''

new_is_xau = '''def is_xau_no_trade_label_slot(H, broker_dt=None, weekday=None):
    """Return True if slot H has a no-gold label attached based on yesterday's H=11 SW/BT or dynamic SW logic."""
    try:
        h = int(H)
    except (TypeError, ValueError):
        return False
    if h in (12, 13, 15):
        if broker_dt is not None:
            if h in (12, 13):
                group, _, _ = evaluate_classification_for_slot(broker_dt, h)
                return group == "SW"
            else:
                rules = get_h11_priority_and_nogold_rules(broker_dt)
                return rules["has_nogold_label"]
    return False'''

content = content.replace(old_is_xau, new_is_xau)

with open("mt5_signal_bot.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Patched successfully")
