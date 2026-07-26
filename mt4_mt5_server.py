# -*- coding: utf-8 -*-
"""
MT4-MT5 Dual Signal Server v2.0
================================
Flask API nhan du lieu tu MT4 EA, lay du lieu MT5 tu dong,
so sanh tin hieu va gui bao cao Telegram.
MT5 timestamps la UTC; broker clock duoc suy tu gio mo nen D1.
"""
import os
import sys
import json
import urllib.request
import urllib.parse
import threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from domain.broker_clock import BrokerClock
from domain.json_io import load_json, save_json

try:
    import MetaTrader5 as mt5
except ImportError:
    print("Loi: pip install MetaTrader5")
    sys.exit(1)

# =====================================================================
# CAU HINH - doc tu config.json (gitignored)
# =====================================================================
_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
_delivery_state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mt4_server_state.json")
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
# Kept in sync with the MT5 Signal Bot for diagnostics and startup reporting.
TARGET_HOURS = [3, 4, 5, 6, 9, 12, 14, 16]
BROKER_CLOCK = BrokerClock(mt5)
_delivery_lock = threading.Lock()
_deliveries_in_progress = set()

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
    """Lay broker time tu moc mo nen D1 UTC; khong doan offset."""
    if not mt5_ready:
        raise RuntimeError("MT5 unavailable; broker clock is unknown")
    return BROKER_CLOCK.now()

def broker_time_to_ts(broker_dt, hour, minute=0, second=0):
    """Chuyen broker time + hour/minute thanh UTC timestamp."""
    target_broker = broker_dt.replace(hour=hour, minute=minute, second=second, microsecond=0)
    target_utc = BROKER_CLOCK.utc_from_broker_datetime(target_broker)
    return int(target_utc.timestamp())

def _is_raw_special_date(target_date):
    weekday = target_date.weekday()
    if weekday not in (3, 4):
        return False
    if (target_date + timedelta(days=7)).month != target_date.month:
        return True
    wednesday = target_date - timedelta(days=1 if weekday == 3 else 2)
    return wednesday.day in (30, 1) or (weekday == 4 and target_date.day in (3, 4, 7))


def is_special_day(broker_dt):
    """Use the same Thu/Fri pair calendar as the signal bot."""
    if broker_dt.weekday() not in (3, 4):
        return False
    target_date = broker_dt.date()
    thursday = target_date if target_date.weekday() == 3 else target_date - timedelta(days=1)
    friday = thursday + timedelta(days=1)
    if thursday.year != friday.year:
        return False
    return _is_raw_special_date(thursday) or _is_raw_special_date(friday)


def is_post_special_monday(broker_dt):
    if broker_dt.weekday() != 0:
        return False
    return is_special_day(broker_dt - timedelta(days=4))


def is_slot_suppressed(broker_dt, slot):
    return slot in (12, 14, 16) and (
        is_special_day(broker_dt) or is_post_special_monday(broker_dt)
    )


def is_deactivated_h3(broker_dt, slot):
    return slot == 3 and broker_dt.weekday() == 3 and is_special_day(broker_dt)


def _delivery_key(broker_dt, slot):
    return f"{broker_dt.date().isoformat()}:{slot}"


def _delivered_keys():
    state = load_json(_delivery_state_path, {"delivered": []})
    if not isinstance(state, dict):
        return set()
    return {str(value) for value in state.get("delivered", [])}


def _start_delivery(key):
    with _delivery_lock:
        if key in _deliveries_in_progress or key in _delivered_keys():
            return False
        _deliveries_in_progress.add(key)
        return True


def _release_delivery(key):
    with _delivery_lock:
        _deliveries_in_progress.discard(key)


def _complete_delivery(key):
    with _delivery_lock:
        delivered = sorted((*_delivered_keys(), key))[-128:]
        save_json(_delivery_state_path, {"delivered": delivered})
        _deliveries_in_progress.discard(key)


def get_signal_time_for_slot(broker_dt, slot):
    """Return the publication clock for one active logical slot."""
    clocks = {3: "03:00", 4: "04:45", 5: "05:45", 6: "06:00", 9: "09:00", 12: "12:00", 14: "14:00", 16: "16:00"}
    if slot == 9 and is_special_day(broker_dt):
        return "08:00"
    return clocks[slot]


def get_schedule_note(broker_dt):
    return "SPECIAL THU-FRI" if is_special_day(broker_dt) else "NORMAL"

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
    """Lay nến MT5 tai H:45 bang broker clock da xac minh."""
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
    delivery_key = None
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
        broker_offset = BROKER_CLOCK.utc_offset_for_date(broker_dt.date())
        print(f"[{fmt_time(broker_dt)} GMT{broker_offset:+d}] Nhan tu MT4:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        broker = data.get("broker", "MT4")
        time_str = data.get("time", "")
        mt4_m35 = data.get("m35", "N/A")
        mt4_m40 = data.get("m40", "N/A")
        mt4_m30 = data.get("m30", "N/A")

        mt4_signal = calculate_signal(mt4_m35, mt4_m40, mt4_m30)

        try:
            H = int(data.get("slot"))
            pattern_hour = int(data.get("pattern_hour"))
        except (TypeError, ValueError):
            return jsonify({"error": "slot and pattern_hour must be integers"}), 400
        if H not in TARGET_HOURS or not 0 <= pattern_hour <= 23:
            return jsonify({"error": "inactive slot or invalid pattern_hour"}), 400
        if time_str != get_signal_time_for_slot(broker_dt, H):
            return jsonify({"error": "request does not match the Broker publication clock"}), 409
        if is_slot_suppressed(broker_dt, H):
            return jsonify({"status": "suppressed", "slot": H}), 200

        deactivated = is_deactivated_h3(broker_dt, H)
        delivery_key = _delivery_key(broker_dt, H)
        if not _start_delivery(delivery_key):
            return jsonify({"status": "duplicate", "slot": H}), 200

        mt5_data = fetch_mt5_data(broker_dt, pattern_hour)
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

        if deactivated:
            msg = build_deactivated_warning(broker, time_str, H, broker_dt)
        else:
            msg = build_telegram(
                broker, time_str, H, pattern_hour,
                mt4_m35, mt4_m40, mt4_m30, mt4_signal,
                mt5_data, mt5_signal,
                conclusion, broker_dt
            )
        if send_telegram(msg) is None:
            _release_delivery(delivery_key)
            delivery_key = None
            return jsonify({"status": "retry", "msg": "Telegram delivery failed"}), 503
        _complete_delivery(delivery_key)
        delivery_key = None

        print(f"  MT4: {mt4_signal} | MT5: {mt5_signal}")
        print(f"  => {conclusion}")
        print(f"{'='*55}")

        return jsonify({
            "status": "ok",
            "mt4": mt4_signal,
            "mt5": mt5_signal,
            "conclusion": conclusion,
            "deactivated": deactivated,
        })

    except Exception as e:
        if delivery_key:
            _release_delivery(delivery_key)
        print(f"[ERROR] {e}")
        return jsonify({"status": "error", "msg": "Internal server error"}), 500

# =====================================================================
# TELEGRAM REPORT
# =====================================================================
def build_deactivated_warning(broker, time_str, H, broker_dt):
    return (
        "=== CANH BAO SIGNAL DEACTIVATED ===\n"
        f"Thoi gian: {fmt_time(broker_dt)}\n"
        f"Nguon: {broker} | Logical slot: H={H} | Phat: {time_str} Broker\n"
        "Trang thai: deactivated=true\n"
        "KHONG VAO LENH - chi ghi nhan doi chieu ky thuat."
    )


def build_telegram(
    broker, time_str, H, pattern_hour,
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
        f"Logical slot: H={H} | Phat: {time_str} Broker\n"
        f"Tap trung: {note}\n"
        f"===========================\n\n"
        f"--- {broker} (MT4) ---\n"
        f"  M5@{fmt_hour(pattern_hour)}:35 = {mt4_m35}\n"
        f"  M5@{fmt_hour(pattern_hour)}:40 = {mt4_m40}\n"
        f"  M30@{fmt_hour(pattern_hour)}:00 = {mt4_m30}\n"
        f"  => {ico(mt4_sig)}\n\n"
        f"--- {SYMBOL} (MT5) ---\n"
        f"  M5@{fmt_hour(pattern_hour)}:35 = {mt5['m35']}\n"
        f"  M5@{fmt_hour(pattern_hour)}:40 = {mt5['m40']}\n"
        f"  M30@{fmt_hour(pattern_hour)}:00 = {mt5['m30']}\n"
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
    print("  Broker clock: derived from MT5 D1 UTC bar opens")
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
