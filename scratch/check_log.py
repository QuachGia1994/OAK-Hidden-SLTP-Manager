import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')

with open("signals_log.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total records: {len(data)}")

h11_records = [r for r in data if r.get("hour") == 11]
print(f"\nH=11 records count: {len(h11_records)}")
for r in h11_records[-5:]:
    print(f"  Date: {r.get('date')}, Signal: {r.get('signal')}, Candles Count: {len(r.get('h11_candles', []))}, Note: {r.get('hour_note')}")

priority_records = [r for r in data if "★" in (r.get("hour_note") or "")]
print(f"\nPriority badge records count: {len(priority_records)}")
for r in priority_records[-10:]:
    print(f"  Date: {r.get('date')}, Hour: H={r.get('hour')}, Note: {r.get('hour_note')}")
