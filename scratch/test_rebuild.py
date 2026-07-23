import sys
import os
from datetime import datetime, timezone, timedelta

# Add current directory to sys.path
sys.path.insert(0, os.path.abspath("."))

import mt5_signal_bot as bot

bot.try_init_mt5()
now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
broker_dt = now_utc + timedelta(hours=bot.BROKER_GMT)
print(f"Current Broker Time: {broker_dt}")

rebuilt = bot.rebuild_recent_history(days=7)
print(f"Rebuilt slots: {rebuilt}")

import json
if os.path.exists("signals_log.json"):
    with open("signals_log.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"\nTotal records in signals_log.json: {len(data)}")
    for r in data[-15:]:
        print(f"Date: {r.get('date')}, Hour: H={r.get('hour')}, Signal: {r.get('signal')}, Note: {r.get('hour_note')}")
