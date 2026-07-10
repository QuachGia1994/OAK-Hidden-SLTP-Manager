# -*- coding: utf-8 -*-
"""Start-of-day balance helper."""
from __future__ import annotations

import threading
from datetime import datetime

import MetaTrader5 as mt5

_balance_cache = {"day": None, "value": 0.0}
_balance_lock = threading.Lock()

def get_start_day_balance():
    """Calculates balance at the start of the current day (Server Time 00:00). Cached."""
    try:
        # Check connection
        if not mt5.terminal_info():
            return 0.0
            
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        # Return cached value if same day
        with _balance_lock:
            if _balance_cache["day"] == today_str and _balance_cache["value"] > 0:
                return _balance_cache["value"]

        acc = mt5.account_info()
        if not acc: return 0.0
        current_balance = acc.balance
        
        # Determine Start of Day Timestamp (Server Time)
        # We use the opening time of the current D1 candle of a common symbol.
        start_timestamp = 0
        
        # List of symbols to try (Major pairs + Gold)
        test_symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD"]
        
        for sym in test_symbols:
            # copy_rates_from_pos(symbol, timeframe, start_pos, count)
            # Get 1 candle from position 0 (current candle)
            rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 1)
            if rates is not None and len(rates) > 0:
                start_timestamp = rates[0]['time'] # This is 00:00 Server Time
                break
        
        # Fallback: If predefined symbols fail, try first available symbol in Market Watch
        if start_timestamp == 0:
            symbols = mt5.symbols_get()
            if symbols:
                for s in symbols[:5]: # Try first 5
                    rates = mt5.copy_rates_from_pos(s.name, mt5.TIMEFRAME_D1, 0, 1)
                    if rates is not None and len(rates) > 0:
                        start_timestamp = rates[0]['time']
                        break
        
        # Get Deals
        deals = None
        if start_timestamp > 0:
            # Use timestamp directly (Server Time)
            # To now (use a future timestamp to ensure we get everything up to now)
            now_ts = start_timestamp + 86400 * 2 # +2 days just to be safe
            deals = mt5.history_deals_get(start_timestamp, now_ts)
        else:
            # Absolute fallback to local time (should rarely happen if MT5 is connected)
            now = datetime.now()
            start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0)
            deals = mt5.history_deals_get(start_of_day, now)
        
        today_profit = 0.0
        if deals:
            for deal in deals:
                if deal.symbol: # Ignore pure balance ops if needed, but usually we want all PnL
                    pass
                today_profit += deal.profit + deal.swap + deal.commission
        
        # Calculate final result
        start_day_bal = current_balance - today_profit
        
        # Update Cache
        with _balance_lock:
            _balance_cache["day"] = today_str
            _balance_cache["value"] = start_day_bal
        
        return start_day_bal
    except Exception as e:
        print(f"Error calc start balance: {e}")
        return 0.0

# --- COPY TRADE MANAGER ---


