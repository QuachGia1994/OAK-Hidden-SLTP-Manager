import datetime

# Constants
SYMBOLS = ["AUDUSD", "USDCAD", "GBPAUD", "GBPJPY", "GBPNZD", "GBPCHF", "GBPUSD", "GBPCAD", "XAUUSD", "USDJPY"]
SHORT_NAMES = ["AU", "UC", "GA", "GJ", "GN", "GF", "GU", "GC", "Gold", "UJ"]
# Note: GC refers to GBPCAD. Gold refers to XAUUSD.

def get_monday_h1_open_close(h1_candles, current_date_obj):
    """
    Find H1 Open at 00:00 and H1 Close at 23:00 (or last available) for the most recent Monday.
    Returns (open_price, close_price) or (None, None).
    """
    days_since_mon = current_date_obj.weekday() # Mon=0
    monday_date = (current_date_obj - datetime.timedelta(days=days_since_mon)).date()
    
    open_p = None
    close_p = None
    
    # Sort candles by time to be sure? Usually they are sorted.
    # Let's just iterate.
    mon_candles = [c for c in h1_candles if c['time'].date() == monday_date]
    
    if not mon_candles:
        # Fallback: Check previous 7 days if not found (e.g. if running on Sunday?)
        # But for Tuesday logic, we expect yesterday (Monday).
        return None, None
        
    # Sort by time
    mon_candles.sort(key=lambda x: x['time'])
    
    # Get 00:00 candle for Open
    for c in mon_candles:
        if c['time'].hour == 0:
            open_p = c['open']
            break
    
    # If no 00:00 candle, use the first one available?
    if open_p is None and mon_candles:
         open_p = mon_candles[0]['open']
         
    # Get 23:00 candle (or last one) for Close
    # Ideally 23:00 candle close is the daily close.
    # If 23:00 exists, use its close. Else use last candle's close.
    last_c = mon_candles[-1]
    close_p = last_c['close']
    
    # Try to find specific 23:00 candle if strictly required
    for c in reversed(mon_candles):
        if c['time'].hour == 23:
            close_p = c['close']
            break
            
    return open_p, close_p

def is_winter_time(now):
    """
    Check if it's Winter Time (Standard Time).
    Rule: Winter (+2 UTC): From Mon after 1st Fri Nov -> To 1st Fri March.
    Summer (+3 UTC): From Mon after 1st Fri March -> To 1st Fri Nov.
    
    Simplified US DST Rule (approx):
    - DST Starts: 2nd Sunday in March
    - DST Ends: 1st Sunday in November
    
    If we stick to the memory rule:
    - Winter Starts: Mon after 1st Fri Nov
    - Winter Ends: 1st Fri March (Transition to Summer on following Mon?)
    
    Let's use the memory rule precisely.
    """
    year = now.year
    
    # Calculate 1st Fri in Nov
    nov_1 = datetime.datetime(year, 11, 1)
    days_to_fri_nov = (4 - nov_1.weekday() + 7) % 7
    first_fri_nov = nov_1 + datetime.timedelta(days=days_to_fri_nov)
    winter_start_date = first_fri_nov + datetime.timedelta(days=3) # Mon after 1st Fri
    
    # Calculate 1st Fri in March
    mar_1 = datetime.datetime(year, 3, 1)
    days_to_fri_mar = (4 - mar_1.weekday() + 7) % 7
    first_fri_mar = mar_1 + datetime.timedelta(days=days_to_fri_mar)
    summer_start_date = first_fri_mar + datetime.timedelta(days=3) # Mon after 1st Fri (Assumption based on pattern)
    
    # Current date comparison
    # If date is in Jan, Feb -> Winter
    if now.month < 3:
        return True
    # If date is in Dec -> Winter
    if now.month > 11:
        return True
    # If March: Winter until summer_start_date
    if now.month == 3:
        if now.date() < summer_start_date.date():
            return True
        return False
    # If November: Summer until winter_start_date
    if now.month == 11:
        if now.date() >= winter_start_date.date():
            return True
        return False
        
    # Apr-Oct -> Summer
    return False

def calculate_logic(data_feed, manual_trends=None, monday_snapshot=None, wednesday_snapshot=None, friday_snapshot=None):
    if manual_trends is None:
        manual_trends = {}
    now = datetime.datetime.now()
    json_output = {}
    json_output['last_update'] = now.strftime("%Y.%m.%d %H:%M:%S")
    if now.weekday() == 6:
        mql_dow = 0
    else:
        mql_dow = now.weekday() + 1
    json_output['day_of_week'] = mql_dow
    s = {k: "WAIT" for k in SHORT_NAMES}
    manual_gold = manual_trends.get('Gold')
    manual_au = manual_trends.get('AU')
    manual_uj = manual_trends.get('UJ')
    manual_uc = manual_trends.get('UC')
    manual_gu = manual_trends.get('GU')
    weekday = now.weekday()
    if weekday in [5, 6]:
        weekday = 4
    if weekday == 0:
        if isinstance(friday_snapshot, dict):
            for k in ["GA", "UC", "GU", "UJ"]:
                if k in friday_snapshot:
                    s[k] = friday_snapshot[k]
        if manual_gold in ["BUY", "SELL"]:
            s["Gold"] = manual_gold
    elif weekday == 1:
        if manual_au == "BUY":
            s['GA'] = "BUY"
            s['Gold'] = "SELL"
        elif manual_au == "SELL":
            s['GA'] = "SELL"
            s['Gold'] = "BUY"
        if isinstance(monday_snapshot, dict):
            for k in ["GU", "UC", "UJ"]:
                if k in monday_snapshot:
                    s[k] = monday_snapshot[k]
    elif weekday == 2:
        if manual_au == "BUY":
            s['Gold'] = "BUY"
            s['GA'] = "SELL"
        elif manual_au == "SELL":
            s['Gold'] = "SELL"
            s['GA'] = "BUY"
        if manual_uj == "BUY":
            s['UJ'] = "BUY"
            s['UC'] = "BUY"
        elif manual_uj == "SELL":
            s['UJ'] = "SELL"
            s['UC'] = "SELL"
    elif weekday == 3:
        if manual_gold == "BUY":
            s['Gold'] = "BUY"
            s['GA'] = "SELL"
        elif manual_gold == "SELL":
            s['Gold'] = "SELL"
            s['GA'] = "BUY"
        if manual_gu == "BUY":
            s['GU'] = "BUY"
        elif manual_gu == "SELL":
            s['GU'] = "SELL"
        if isinstance(wednesday_snapshot, dict):
            for k in ["UC", "UJ"]:
                if k in wednesday_snapshot:
                    s[k] = wednesday_snapshot[k]
    elif weekday == 4:
        if manual_gold == "BUY":
            s['Gold'] = "BUY"
            s['GA'] = "SELL"
        elif manual_gold == "SELL":
            s['Gold'] = "SELL"
            s['GA'] = "BUY"
        if manual_uj == "BUY":
            s['UJ'] = "BUY"
            s['UC'] = "BUY"
        elif manual_uj == "SELL":
            s['UJ'] = "SELL"
            s['UC'] = "SELL"
        if isinstance(friday_snapshot, dict) and "GU" in friday_snapshot:
            s['GU'] = friday_snapshot["GU"]
    
    json_output['signals'] = {}
    for k in SHORT_NAMES:
        json_output['signals'][k] = {"signal": s[k], "time": ""}
    json_output['notes'] = ""
    json_output['notes_vn'] = ""
    return json_output
