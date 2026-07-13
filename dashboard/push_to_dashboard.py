"""
Push data to dashboard Redis via API.
Usage: python push_to_dashboard.py signals|state|news [data_json]
"""
import sys
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

API_BASE = os.environ.get("DASHBOARD_API_URL", "http://localhost:3000")
API_KEY = os.environ.get("DASHBOARD_API_KEY", "")

def push(endpoint: str, data):
    url = f"{API_BASE}/api/{endpoint}"
    payload = json.dumps(data).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    req = urllib.request.Request(url, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            print(f"[OK] {endpoint}: {result}")
            return result
    except Exception as e:
        print(f"[ERROR] {endpoint}: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python push_to_dashboard.py signals|state|news [data_json]")
        sys.exit(1)

    endpoint = sys.argv[1]

    if endpoint == "signals":
        # Read signals_log.json and push
        filepath = os.path.join(os.path.dirname(__file__), "..", "signals_log.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            push("signals", data)
        else:
            print("signals_log.json not found")

    elif endpoint == "state":
        # Read bot_state.json and push
        filepath = os.path.join(os.path.dirname(__file__), "..", "bot_state.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            push("state", data)
        else:
            print("bot_state.json not found")

    elif endpoint == "news":
        # Read news_cache_VN.json and push
        filepath = os.path.join(os.path.dirname(__file__), "..", "news_cache_VN.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            news_date = data.get("date", "")
            today_vn = datetime.now(timezone(timedelta(hours=7))).date().isoformat()
            # Parse news items
            items = []
            source_lines = data.get("news", []) if news_date == today_vn else []
            for line in source_lines:
                clean = line.lstrip("• ").strip()
                import re
                match = re.match(r"^(\d{2}:\d{2})\s+(\w+)\s+(.+)$", clean)
                if match:
                    rest = match.group(3)
                    impact = "high"
                    if "🟡" in rest:
                        impact = "medium"
                    elif "🟢" in rest:
                        impact = "low"
                    title = rest.replace("🔴", "").replace("🟡", "").replace("🟢", "").strip()
                    items.append({"date": news_date, "time": match.group(1), "local_time": match.group(1), "time_zone": "Asia/Bangkok", "currency": match.group(2), "title": title, "impact": impact})
                else:
                    items.append({"date": news_date, "time": "", "local_time": "", "time_zone": "Asia/Bangkok", "currency": "", "title": clean, "impact": "high"})
            push("news", items)
        else:
            print("news_cache_VN.json not found")

    else:
        print(f"Unknown endpoint: {endpoint}")
        sys.exit(1)
