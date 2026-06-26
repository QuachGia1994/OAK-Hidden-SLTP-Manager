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

try:
    import flask
except ImportError:
    print("Loi: pip install Flask")
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
except Exception:
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHAT_ID = ""
    print("[WARN] config.json not found or invalid.")
SYMBOL = "GBPUSD"
MT5_PATH = r"C:\Program Files\MetaTrader 5 IC Markets Global\terminal64.exe"
TARGET_HOURS = [1, 7, 9, 14, 15, 16]
BROKER_GMT = 0

SCHEDULE_NOTES = {
    1: "Thứ 2: Vàng SW nhẹ",
    7: "Thứ 2: Vàng SW nhẹ",
    9: "Thứ 3: Bình thường | Thứ 4: GBP SW rộng theo Vàng + tính lại W1 | Thứ 5: Theo W1, phiên AU dời 9h broker | Thứ 6: SW/W1, tính lại nếu cuối tháng",
    14: "Thứ 3: Bình thường | Thứ 4: GBP SW rộng theo Vàng + tính lại W1 | Thứ 5: Theo W1, phiên AU dời 9h broker | Thứ 6: SW/W1, tính lại nếu cuối tháng",
    15: "XAUUSD - Thứ 4: tính lại W1 | Thứ 5: theo W1",
    16: "Thứ 4: toàn bộ nhóm GBP + tính lại W1 | Thứ 5: Theo W1 | Thứ 6: Vàng + GBP",
}

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
def calculate_signal(m35_dir, m40_dir, h1_dir, m15_dir):
    if m35_dir is None or m40_dir is None:
        return "WAIT"
    if m35_dir == "DOJI" or m40_dir == "DOJI":
        return "WAIT"

    if m35_dir == m40_dir:
        if h1_dir is None or h1_dir == "DOJI":
            return "WAIT"
        return "BUY" if h1_dir == "TANG" else "SELL"
    else:
        if m15_dir is None or m15_dir == "DOJI":
            return "WAIT"
        return "SELL" if m15_dir == "TANG" else "BUY"

# =====================================================================
# MT5 DATA FETCHER
# =====================================================================
def fetch_mt5_data(broker_dt, H):
    """Lay 4 nến MT5 tai H:50 su dung broker time tu tick.time."""
    if not mt5_ready:
        return {"m35":"N/A","m40":"N/A","h1":"N/A","m15":"N/A","signal":"WAIT","h1_hour":H-1}

    ts_m35 = broker_time_to_ts(broker_dt, H, 35)
    ts_m40 = broker_time_to_ts(broker_dt, H, 40)
    ts_m15 = broker_time_to_ts(broker_dt, H, 30)
    h1_h = H - 1 if H > 0 else 23
    ts_h1 = broker_time_to_ts(broker_dt, h1_h, 0)

    c_m35 = get_candle_by_ts(SYMBOL, mt5.TIMEFRAME_M5, ts_m35)
    c_m40 = get_candle_by_ts(SYMBOL, mt5.TIMEFRAME_M5, ts_m40)
    c_m15 = get_candle_by_ts(SYMBOL, mt5.TIMEFRAME_M15, ts_m15)
    c_h1 = get_candle_by_ts(SYMBOL, mt5.TIMEFRAME_H1, ts_h1)

    d_m35 = candle_dir(c_m35)
    d_m40 = candle_dir(c_m40)
    d_m15 = candle_dir(c_m15)
    d_h1 = candle_dir(c_h1)

    sig = calculate_signal(d_m35, d_m40, d_h1, d_m15)

    return {
        "m35": d_m35 or "N/A",
        "m40": d_m40 or "N/A",
        "h1": d_h1 or "N/A",
        "m15": d_m15 or "N/A",
        "signal": sig,
        "h1_hour": h1_h,
    }

# =====================================================================
# FLASK ENDPOINT
# =====================================================================
@app.route("/mt4_data", methods=["POST"])
def receive_mt4_data():
    try:
        data = request.get_json(force=True)
        broker_dt = get_broker_time()
        print(f"\n{'='*55}")
        print(f"[{fmt_time(broker_dt)} GMT+{BROKER_GMT}] Nhan tu MT4:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        broker = data.get("broker", "MT4")
        time_str = data.get("time", "")
        mt4_m35 = data.get("m35", "N/A")
        mt4_m40 = data.get("m40", "N/A")
        mt4_h1 = data.get("h1", "N/A")
        mt4_m15 = data.get("m15", "N/A")

        mt4_signal = calculate_signal(mt4_m35, mt4_m40, mt4_h1, mt4_m15)

        h_parts = time_str.replace(":50", "").strip()
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
            mt4_m35, mt4_m40, mt4_h1, mt4_m15, mt4_signal,
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
        return jsonify({"status": "error", "msg": str(e)}), 500

# =====================================================================
# TELEGRAM REPORT
# =====================================================================
def build_telegram(
    broker, time_str, H,
    mt4_m35, mt4_m40, mt4_h1, mt4_m15, mt4_sig,
    mt5, mt5_sig,
    conclusion, broker_dt
):
    def ico(s):
        return {"BUY": "Mua", "SELL": "Bán"}.get(s, "Chờ")

    now_s = fmt_time(broker_dt)
    h1_label = fmt_hour(H - 1 if H > 0 else 23)
    note = SCHEDULE_NOTES.get(H, "")

    return (
        f"=== BÁO CÁO ĐỐI CHIẾU ===\n"
        f"Thời gian: {now_s}\n"
        f"Kích hoạt: {fmt_hour(H)}:50\n"
        f"Tập trung: {note}\n"
        f"===========================\n\n"
        f"--- {broker} (MT4) ---\n"
        f"  M5@{fmt_hour(H)}:35 = {mt4_m35}\n"
        f"  M5@{fmt_hour(H)}:40 = {mt4_m40}\n"
        f"  H1@{h1_label}:00   = {mt4_h1}\n"
        f"  M15@{fmt_hour(H)}:30 = {mt4_m15}\n"
        f"  => {ico(mt4_sig)}\n\n"
        f"--- {SYMBOL} (MT5) ---\n"
        f"  M5@{fmt_hour(H)}:35 = {mt5['m35']}\n"
        f"  M5@{fmt_hour(H)}:40 = {mt5['m40']}\n"
        f"  H1@{h1_label}:00   = {mt5['h1']}\n"
        f"  M15@{fmt_hour(H)}:30 = {mt5['m15']}\n"
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

def main():
    global mt5_ready
    print("=" * 55)
    print("  MT4-MT5 Dual Signal Server v2.0")
    print(f"  Symbol: {SYMBOL}")
    print(f"  Target Hours: {TARGET_HOURS}")
    print(f"  Broker GMT+{BROKER_GMT} (tu tick.time)")
    print("=" * 55)

    ok = mt5.initialize(path=MT5_PATH) if MT5_PATH else mt5.initialize()
    if ok:
        mt5_ready = True
        info = mt5.account_info()
        if info:
            print(f"  MT5: {info.server} | {info.login}")
    else:
        print(f"[WARN] MT5 init failed: {mt5.last_error()}")
        print("  Server van chay, nhung MT5 data se KHONG co.")

    print("=" * 55)
    print("  API: POST http://localhost:5000/mt4_data")
    print("  Dang chay... Ctrl+C de dung")
    print("=" * 55)

    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n  Dung server.")
    finally:
        if mt5_ready:
            mt5.shutdown()

if __name__ == "__main__":
    main()
