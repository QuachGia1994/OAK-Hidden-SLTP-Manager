# -*- coding: utf-8 -*-
"""
MT4-MT5 Dual Signal Server v2.0
================================
Flask API nhan du lieu tu MT4 EA, lay du lieu MT5 tu dong,
so sanh tin hieu va gui bao cao Telegram.
Tinh gio hoan toan tu tick.time (UTC timestamp).
"""
import os
import sys
import json
import calendar
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify

try:
    import MetaTrader5 as mt5
except ImportError:
    print("Loi: pip install MetaTrader5")
    sys.exit(1)

# =====================================================================
# CAU HINH - doc tu config.json (gitignored)
# =====================================================================
_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
try:
    with open(_config_path, "r", encoding="utf-8") as _f:
        _cfg = json.load(_f)
    TELEGRAM_TOKEN = _cfg.get("telegram_token", "")
    TELEGRAM_CHAT_ID = _cfg.get("telegram_chat_id", "")
    MT5_PATH = _cfg.get("mt5_path", "")
except Exception:
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHAT_ID = ""
    MT5_PATH = ""
    print("[WARN] config.json not found or invalid.")
SYMBOL = "GBPUSD"
# Default band; Thursday uses H=5-15 via get_target_hours if imported from signal bot
TARGET_HOURS = list(range(2, 16))
BROKER_GMT = 0

app = Flask(__name__)

# =====================================================================
# TELEGRAM
# =====================================================================
def send_telegram(text):
    try:
        clean = text.replace("*", "").replace("_", "")
        msg = urllib.parse.quote(clean)
        url = (
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
            f"/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={msg}"
        )
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.read()
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")
        return None

# =====================================================================
# TIME HELPERS
# =====================================================================
def fmt_hour(h):
    return f"{h:02d}"

def fmt_time(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def get_broker_time():
    """Lay broker time tu tick.time (UTC). Khong phu thuoc local."""
    if mt5_ready:
        tick = mt5.symbol_info_tick(SYMBOL)
        if tick is not None:
            utc_dt = datetime.fromtimestamp(tick.time, tz=timezone.utc).replace(tzinfo=None)
            return utc_dt + timedelta(hours=BROKER_GMT)
    now_utc = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    return now_utc + timedelta(hours=BROKER_GMT)

def broker_time_to_ts(broker_dt, hour, minute=0, second=0):
    """Chuyen broker time + hour/minute thanh UTC timestamp."""
    target_broker = broker_dt.replace(hour=hour, minute=minute, second=second, microsecond=0)
    target_utc = target_broker - timedelta(hours=BROKER_GMT)
    return calendar.timegm(target_utc.timetuple())

def get_schedule_note(broker_dt):
    """Return a short note about today's schedule focus."""
    today = broker_dt.date()
    year = today.year
    month = today.month
    last_day = calendar.monthrange(year, month)[1]

    last_fri = today.replace(day=last_day)
    while last_fri.weekday() != 4:
        last_fri -= timedelta(days=1)
    if today == last_fri:
        return "THU 6 CUOI THANG"

    last_wed = today.replace(day=last_day)
    while last_wed.weekday() != 2:
        last_wed -= timedelta(days=1)
    if today == last_wed:
        return "THU 4 CUOI THANG"

    if today.weekday() == 2 and today.day in (1, 30):
        return "THU 4 NGAY 30/1 TAY"

    return "Binh thuong"

# =====================================================================
# MT5 CANDLE
# =====================================================================
def get_candle_by_ts(symbol, timeframe, target_ts):
    """Lay nến gan nhat voi UTC timestamp."""
    if not mt5.symbol_select(symbol, True):
        print(f"[WARN] Khong select: {symbol}")
        return None

    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1000)
    if rates is None or len(rates) == 0:
        print(f"[WARN] Khong du lieu {symbol} TF={timeframe}")
        return None

    best = None
    min_diff = float("inf")
    for r in rates:
        d = abs(r["time"] - target_ts)
        if d < min_diff:
            min_diff = d
            best = r

    return best if (best and min_diff <= 180) else None

def candle_dir(c):
    if c is None:
        return None
    body = abs(c["close"] - c["open"])
    rng = c["high"] - c["low"]
    if rng == 0 or body / rng < 0.02:
        return "DOJI"
    return "TANG" if c["close"] > c["open"] else "GIAM"

# =====================================================================
# SIGNAL LOGIC
# =====================================================================
def calculate_signal(m35_dir, m40_dir, m30_dir):
    if m35_dir is None or m40_dir is None:
        return "WAIT"
    if m35_dir == "DOJI" or m40_dir == "DOJI":
        return "WAIT"
    if m30_dir is None or m30_dir == "DOJI":
        return "WAIT"

    if m35_dir == m40_dir:
        return "BUY" if m30_dir == "TANG" else "SELL"
    else:
        return "SELL" if m30_dir == "TANG" else "BUY"

# =====================================================================
# MT5 DATA FETCHER
# =====================================================================
def fetch_mt5_data(broker_dt, H):
    """Lay nến MT5 tai H:45 su dung broker time tu tick.time."""
    if not mt5_ready:
        return {"m35":"N/A","m40":"N/A","m30":"N/A","signal":"WAIT"}

    ts_m35 = broker_time_to_ts(broker_dt, H, 35)
    ts_m40 = broker_time_to_ts(broker_dt, H, 40)
    ts_m30 = broker_time_to_ts(broker_dt, H, 0)

    c_m35 = get_candle_by_ts(SYMBOL, mt5.TIMEFRAME_M5, ts_m35)
    c_m40 = get_candle_by_ts(SYMBOL, mt5.TIMEFRAME_M5, ts_m40)
    c_m30 = get_candle_by_ts(SYMBOL, mt5.TIMEFRAME_M30, ts_m30)

    d_m35 = candle_dir(c_m35)
    d_m40 = candle_dir(c_m40)
    d_m30 = candle_dir(c_m30)

    sig = calculate_signal(d_m35, d_m40, d_m30)

    return {
        "m35": d_m35 or "N/A",
        "m40": d_m40 or "N/A",
        "m30": d_m30 or "N/A",
        "signal": sig,
    }

# =====================================================================
# FLASK ENDPOINT
# =====================================================================
@app.route("/mt4_data", methods=["POST"])
def receive_mt4_data():
    try:
        data = request.get_json(force=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid data format"}), 400

        # Validate required fields
        time_str = data.get("time", "")
        if not isinstance(time_str, str) or len(time_str) > 20:
            return jsonify({"error": "Invalid time field"}), 400

        # Sanitize string fields
        for key in ["broker", "m35", "m40", "m30"]:
            val = data.get(key, "")
            if not isinstance(val, str):
                data[key] = str(val)
            data[key] = data[key][:50]  # Limit length

        broker_dt = get_broker_time()
        print(f"\n{'='*55}")
        print(f"[{fmt_time(broker_dt)} GMT+{BROKER_GMT}] Nhan tu MT4:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        broker = data.get("broker", "MT4")
        time_str = data.get("time", "")
        mt4_m35 = data.get("m35", "N/A")
        mt4_m40 = data.get("m40", "N/A")
        mt4_m30 = data.get("m30", "N/A")

        mt4_signal = calculate_signal(mt4_m35, mt4_m40, mt4_m30)

        h_parts = time_str.replace(":45", "").strip()
        try:
            H = int(h_parts)
        except ValueError:
            H = broker_dt.hour

        mt5_data = fetch_mt5_data(broker_dt, H)
        mt5_signal = mt5_data["signal"]

        if mt4_signal == "WAIT" or mt5_signal == "WAIT":
            if mt4_signal == "WAIT" and mt5_signal == "WAIT":
                conclusion = "KHONG XAC DINH - Ca 2 khong du dieu kien"
            elif mt4_signal == "WAIT":
                conclusion = f"KHONG XAC DINH - MT4 WAIT, MT5={mt5_signal}"
            else:
                conclusion = f"KHONG XAC DINH - MT5 WAIT, MT4={mt4_signal}"
        elif mt4_signal == mt5_signal:
            conclusion = f"HOP LUU: {mt4_signal}"
        else:
            conclusion = f"XUNG DOT: MT4={mt4_signal} vs MT5={mt5_signal} - KHONG VAO"

        msg = build_telegram(
            broker, time_str, H,
            mt4_m35, mt4_m40, mt4_m30, mt4_signal,
            mt5_data, mt5_signal,
            conclusion, broker_dt
        )
        send_telegram(msg)

        print(f"  MT4: {mt4_signal} | MT5: {mt5_signal}")
        print(f"  => {conclusion}")
        print(f"{'='*55}")

        return jsonify({
            "status": "ok",
            "mt4": mt4_signal,
            "mt5": mt5_signal,
            "conclusion": conclusion,
        })

    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"status": "error", "msg": "Internal server error"}), 500

# =====================================================================
# TELEGRAM REPORT
# =====================================================================
def build_telegram(
    broker, time_str, H,
    mt4_m35, mt4_m40, mt4_m30, mt4_sig,
    mt5, mt5_sig,
    conclusion, broker_dt
):
    def ico(s):
        return {"BUY": "Mua", "SELL": "Bán"}.get(s, "Chờ")

    now_s = fmt_time(broker_dt)
    note = get_schedule_note(broker_dt)

    return (
        f"=== BAO CAO DOI CHIEU ===\n"
        f"Thoi gian: {now_s}\n"
        f"Kich hoat: {fmt_hour(H)}:45\n"
        f"Tap trung: {note}\n"
        f"===========================\n\n"
        f"--- {broker} (MT4) ---\n"
        f"  M5@{fmt_hour(H)}:35 = {mt4_m35}\n"
        f"  M5@{fmt_hour(H)}:40 = {mt4_m40}\n"
        f"  M30@{fmt_hour(H)}:00 = {mt4_m30}\n"
        f"  => {ico(mt4_sig)}\n\n"
        f"--- {SYMBOL} (MT5) ---\n"
        f"  M5@{fmt_hour(H)}:35 = {mt5['m35']}\n"
        f"  M5@{fmt_hour(H)}:40 = {mt5['m40']}\n"
        f"  M30@{fmt_hour(H)}:00 = {mt5['m30']}\n"
        f"  => {ico(mt5_sig)}\n\n"
        f"===========================\n"
        f"KET LUAN: {conclusion}\n"
        f"===========================\n"
        f"Ref only. Discipline is power!"
    )

# =====================================================================
# MAIN
# =====================================================================
mt5_ready = False
import subprocess
import time as _time

def ensure_mt5_running():
    """Try to start MT5 terminal if not running."""
    global mt5_ready
    if mt5.terminal_info():
        return True
    # Try to start MT5 terminal
    if MT5_PATH and os.path.exists(MT5_PATH):
        try:
            print(f"[INFO] Starting MT5 terminal: {MT5_PATH}")
            subprocess.Popen([MT5_PATH])
            _time.sleep(3)  # Wait for terminal to start
        except Exception as e:
            print(f"[ERROR] Failed to start MT5: {e}")
    # Try to connect
    ok = mt5.initialize(path=MT5_PATH) if MT5_PATH else mt5.initialize()
    if ok:
        mt5_ready = True
        info = mt5.account_info()
        if info:
            print(f"[OK] MT5 connected: {info.server} | {info.login}")
        return True
    return False

def main():
    global mt5_ready
    print("=" * 55)
    print("  MT4-MT5 Dual Signal Server v2.0")
    print(f"  Symbol: {SYMBOL}")
    print(f"  Target Hours: {TARGET_HOURS}")
    print(f"  Broker GMT+{BROKER_GMT} (tu tick.time)")
    print("=" * 55)

    if not ensure_mt5_running():
        print(f"[WARN] MT5 init failed: {mt5.last_error()}")
        print("  Server van chay, nhung MT5 data se KHONG co.")

    print("=" * 55)
    print("  API: POST http://localhost:5000/mt4_data")
    print("  Dang chay... Ctrl+C de dung")
    print("=" * 55)

    last_reconnect = _time.time()
    try:
        while True:
            app.run(host="127.0.0.1", port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n  Dung server.")
    finally:
        if mt5_ready:
            mt5.shutdown()

if __name__ == "__main__":
    main()
