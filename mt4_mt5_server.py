# -*- coding: utf-8 -*-
"""
MT4-MT5 Dual Signal Server v2.0
================================
Flask API nhan du lieu tu MT4 EA, lay du lieu MT5 tu dong,
so sanh tin hieu va gui bao cao Telegram.
MT5 timestamp encoding duoc hieu chuan bang tick song; loi clock thi fail-closed.
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
import mt5_signal_bot as signal_engine

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
XAUUSD_SYMBOL = "XAUUSD"
SIGNAL_LOGIC_VERSION = 76
GBP_SIGNAL_PAIRS = ("GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
SIGNAL_PAIRS = ("XAUUSD", *GBP_SIGNAL_PAIRS)
# Kept in sync with the MT5 Signal Bot for diagnostics and startup reporting.
TARGET_HOURS = [3, 7, 9, 12, 14, 16]
BROKER_CLOCK = BrokerClock(
    mt5,
    cache_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "broker_clock_cache.json"),
)
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
    """Convert Broker wall time to the timestamp encoding used by this terminal."""
    target_broker = broker_dt.replace(hour=hour, minute=minute, second=second, microsecond=0)
    return BROKER_CLOCK.mt5_timestamp_from_broker_datetime(target_broker)


def broker_datetime_to_ts(broker_dt):
    """Convert one explicit Broker wall datetime to the terminal timestamp mode."""
    return BROKER_CLOCK.mt5_timestamp_from_broker_datetime(broker_dt)

def _is_raw_special_date(target_date):
    weekday = target_date.weekday()
    if weekday not in (3, 4):
        return False
    if (target_date + timedelta(days=7)).month != target_date.month:
        return True
    wednesday = target_date - timedelta(days=1 if weekday == 3 else 2)
    return wednesday.day in (30, 1) or (weekday == 4 and target_date.day in (3, 4, 7))


def is_special_day(broker_dt):
    """Use the signal bot's special Thursday/Friday pair calendar."""
    if broker_dt.weekday() not in (3, 4):
        return False
    current = broker_dt.date()
    thursday = current if broker_dt.weekday() == 3 else current - timedelta(days=1)
    friday = thursday + timedelta(days=1)
    if thursday.year != friday.year:
        return False
    return _is_raw_special_date(thursday) or _is_raw_special_date(friday)


def is_post_special_monday(broker_dt):
    if broker_dt.weekday() != 0:
        return False
    return is_special_day(broker_dt - timedelta(days=4))


def _first_friday_of_month(year, month):
    """Return the day number of the first Friday in a given month."""
    for day in range(1, 8):
        if datetime(year, month, day).weekday() == 4:
            return day
    return None


def _last_friday_of_month(year, month):
    """Return the day number of the last Friday in a given month."""
    first = _first_friday_of_month(year, month)
    if first is None:
        return None
    d = first
    while True:
        next_d = d + 7
        try:
            datetime(year, month, next_d)
            d = next_d
        except ValueError:
            return d


def _is_in_restricted_calendar_period(dt):
    """Check whether *dt* falls in the month-end restricted period.

    The restricted period spans from the Tuesday of the week containing
    the last Friday of month M (= last_friday - 3) through the Monday
    immediately after the first Friday of month M+1 (= first_friday + 3).
    Both endpoints are inclusive.
    """
    if dt is None:
        return False
    d = dt.date() if hasattr(dt, "date") and callable(dt.date) else dt

    for src_year, src_month in ((d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1), (d.year, d.month)):
        last_fri_day = _last_friday_of_month(src_year, src_month)
        if last_fri_day is None:
            continue
        start_day = last_fri_day - 3  # Tue of the week containing last Fri
        if start_day < 1:
            continue
        tgt_year, tgt_month = (src_year + 1, 1) if src_month == 12 else (src_year, src_month + 1)
        first_fri_day = _first_friday_of_month(tgt_year, tgt_month)
        if first_fri_day is None:
            continue
        start = datetime(src_year, src_month, start_day).date()
        end = datetime(tgt_year, tgt_month, first_fri_day + 3).date()  # Mon after Fri
        if start <= d <= end:
            return True
    return False


def is_slot_suppressed(broker_dt, slot):
    return False


def is_deactivated_slot(broker_dt, slot):
    return False


def _delivery_key(broker_dt, slot):
    return f"{broker_dt.date().isoformat()}:{slot}"


def _delivery_state():
    state = load_json(_delivery_state_path, {"delivered": [], "missed": []})
    if not isinstance(state, dict):
        return {"delivered": set(), "missed": set()}
    return {
        "delivered": {str(value) for value in state.get("delivered", [])},
        "missed": {str(value) for value in state.get("missed", [])},
    }


def _terminal_delivery_status(key):
    state = _delivery_state()
    if key in state["missed"]:
        return "missed"
    if key in state["delivered"]:
        return "delivered"
    return None


def _start_delivery(key):
    with _delivery_lock:
        if key in _deliveries_in_progress or _terminal_delivery_status(key):
            return False
        _deliveries_in_progress.add(key)
        return True


def _release_delivery(key):
    with _delivery_lock:
        _deliveries_in_progress.discard(key)


def _complete_delivery(key):
    with _delivery_lock:
        state = _delivery_state()
        delivered = sorted((*state["delivered"], key))[-128:]
        save_json(
            _delivery_state_path,
            {"delivered": delivered, "missed": sorted(state["missed"])[-128:]},
        )
        _deliveries_in_progress.discard(key)


def _mark_delivery_missed(key):
    with _delivery_lock:
        state = _delivery_state()
        missed = sorted((*state["missed"], key))[-128:]
        save_json(
            _delivery_state_path,
            {"delivered": sorted(state["delivered"])[-128:], "missed": missed},
        )
        _deliveries_in_progress.discard(key)


def get_signal_time_for_slot(broker_dt, slot):
    """Return the publication clock for one active logical slot."""
    clocks = {hour: f"{hour:02d}:00" for hour in TARGET_HOURS}
    return clocks[slot]


def get_schedule_note(broker_dt):
    return "TWO-LAYER INDEPENDENT M30 FOR GBP PAIRS; XAU FOLLOWS GBPAUD"


def _entry_datetime(broker_dt, entry_time):
    try:
        hour, minute = (int(value) for value in entry_time.split(":"))
    except (AttributeError, TypeError, ValueError):
        return None
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    return broker_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _is_past_earliest_entry(broker_dt, *entry_times):
    entries = [_entry_datetime(broker_dt, value) for value in entry_times]
    if any(value is None for value in entries):
        return False
    current_minute = broker_dt.replace(second=0, microsecond=0)
    return current_minute > min(entries)

# =====================================================================
# MT5 CANDLE
# =====================================================================
def calculate_context(slot, pair_dirs, pair_entry_times, pair_groups=None):
    """Normalize one terminal's final v72 five-pair context."""
    directions = {
        symbol: pair_dirs.get(symbol) if pair_dirs.get(symbol) in ("BUY", "SELL", "WAIT") else "WAIT"
        for symbol in SIGNAL_PAIRS
    }
    entries = {
        symbol: pair_entry_times.get(symbol) if _entry_datetime(datetime.now(), pair_entry_times.get(symbol)) else None
        for symbol in SIGNAL_PAIRS
    }
    groups = {
        symbol: value if value in ("SW", "BT", None) else None
        for symbol, value in dict(pair_groups or {}).items()
        if symbol in SIGNAL_PAIRS
    }
    return {
        "logic_version": SIGNAL_LOGIC_VERSION,
        "signal": directions["XAUUSD"],
        "entry_time": entries["XAUUSD"],
        "pair_dirs": directions,
        "pair_entry_times": entries,
        "pair_groups": groups,
    }


def fetch_mt5_data(broker_dt, slot):
    """Evaluate MT5 with the canonical v72 engine shared by the signal bot."""
    if not mt5_ready:
        return calculate_context(slot, {}, {}, {})
    result = signal_engine.evaluate_all_pairs_for_slot(broker_dt, slot)
    if not result:
        return calculate_context(slot, {}, {}, {})
    return calculate_context(
        slot,
        result.get("pair_dirs") or {},
        result.get("pair_entry_times") or {},
        result.get("pair_groups") or {},
    )


# FLASK ENDPOINT
# =====================================================================
def _pair_maps_from_payload(data):
    directions = {
        symbol: data.get(f"{symbol.lower()}_signal")
        for symbol in SIGNAL_PAIRS
    }
    entries = {
        symbol: data.get(f"{symbol.lower()}_entry") or None
        for symbol in SIGNAL_PAIRS
    }
    groups = {
        symbol: data.get(f"{symbol.lower()}_group") or None
        for symbol in SIGNAL_PAIRS
    }
    return directions, entries, groups


def _payload_contract_error(slot, directions, entries):
    for symbol in SIGNAL_PAIRS:
        if directions.get(symbol) not in ("BUY", "SELL", "WAIT"):
            return f"invalid {symbol} signal"
        entry = entries.get(symbol)
        if directions[symbol] in ("BUY", "SELL") and _entry_datetime(datetime.now(), entry) is None:
            return f"invalid {symbol} entry"
        if directions[symbol] == "WAIT" and entry is not None:
            return f"WAIT {symbol} must not have entry"
    expected_xau = (
        _reverse_direction(directions["GBPAUD"])
        if slot in (3, 14, 16)
        else directions["GBPAUD"]
    )
    if directions["XAUUSD"] != expected_xau:
        return "XAUUSD signal does not follow slot GBPAUD mapping"
    if directions["XAUUSD"] in ("BUY", "SELL"):
        expected_gbp_entry = signal_engine.deferred_gbp_entry_time(entries["XAUUSD"])
        for symbol in GBP_SIGNAL_PAIRS:
            if directions[symbol] in ("BUY", "SELL") and entries[symbol] != expected_gbp_entry:
                return f"{symbol} entry must be the next full hour after XAUUSD"
    return None


def _reverse_direction(direction):
    if direction == "BUY":
        return "SELL"
    if direction == "SELL":
        return "BUY"
    return "WAIT"


def _actionable_entries(context):
    return [
        entry
        for symbol, entry in (context.get("pair_entry_times") or {}).items()
        if (context.get("pair_dirs") or {}).get(symbol) in ("BUY", "SELL") and entry
    ]


def _all_pairs_ready(context):
    directions = context.get("pair_dirs") or {}
    entries = context.get("pair_entry_times") or {}
    return all(
        directions.get(symbol) in ("BUY", "SELL")
        and _entry_datetime(datetime.now(), entries.get(symbol)) is not None
        for symbol in SIGNAL_PAIRS
    )


@app.route("/mt4_data", methods=["POST"])
def receive_mt4_data():
    delivery_key = None
    try:
        data = request.get_json(force=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid data format"}), 400
        try:
            slot = int(data.get("slot"))
            logic_version = int(data.get("logic_version"))
        except (TypeError, ValueError):
            return jsonify({"error": "slot and logic_version must be integers"}), 400
        if slot not in TARGET_HOURS or logic_version != SIGNAL_LOGIC_VERSION:
            return jsonify({"error": "inactive slot or stale logic version"}), 409
        time_str = data.get("time")
        if not isinstance(time_str, str) or len(time_str) > 20:
            return jsonify({"error": "invalid time field"}), 400
        directions, entries, groups = _pair_maps_from_payload(data)
        contract_error = _payload_contract_error(slot, directions, entries)
        if contract_error:
            return jsonify({"error": contract_error}), 400

        broker_dt = get_broker_time()
        if time_str != get_signal_time_for_slot(broker_dt, slot):
            return jsonify({"error": "request does not match Broker publication clock"}), 409
        delivery_key = _delivery_key(broker_dt, slot)
        terminal_status = _terminal_delivery_status(delivery_key)
        if terminal_status in ("missed", "delivered"):
            status = "duplicate" if terminal_status == "delivered" else "missed"
            return jsonify({"status": status, "slot": slot}), 200
        mt4_context = calculate_context(slot, directions, entries, groups)
        if not _all_pairs_ready(mt4_context):
            return jsonify({"status": "retry", "slot": slot, "reason": "MT4_WAIT"}), 425
        if not _start_delivery(delivery_key):
            return jsonify({"status": "retry", "slot": slot, "reason": "IN_PROGRESS"}), 503

        mt5_context = fetch_mt5_data(broker_dt, slot)
        if not _all_pairs_ready(mt5_context):
            _release_delivery(delivery_key)
            delivery_key = None
            return jsonify({"status": "retry", "slot": slot, "reason": "MT5_WAIT"}), 425
        delivery_dt = get_broker_time()
        entries_to_check = _actionable_entries(mt4_context) + _actionable_entries(mt5_context)
        if entries_to_check and _is_past_earliest_entry(delivery_dt, *entries_to_check):
            _mark_delivery_missed(delivery_key)
            delivery_key = None
            return jsonify({"status": "missed", "slot": slot}), 200

        matched = (
            mt4_context["pair_dirs"] == mt5_context["pair_dirs"]
            and mt4_context["pair_entry_times"] == mt5_context["pair_entry_times"]
        )
        conclusion = "HOP LUU 5 PAIRS" if matched else "XUNG DOT MT4/MT5 - KHONG VAO"
        message = build_telegram(data.get("broker", "MT4"), time_str, slot, mt4_context, mt5_context, conclusion, delivery_dt)
        if send_telegram(message) is None:
            _release_delivery(delivery_key)
            delivery_key = None
            return jsonify({"status": "retry", "msg": "Telegram delivery failed"}), 503
        _complete_delivery(delivery_key)
        delivery_key = None
        return jsonify({
            "status": "ok",
            "matched": matched,
            "mt4": mt4_context["signal"],
            "mt5": mt5_context["signal"],
            "mt4_pair_entry_times": mt4_context["pair_entry_times"],
            "mt5_pair_entry_times": mt5_context["pair_entry_times"],
            "conclusion": conclusion,
        })
    except Exception as error:
        if delivery_key:
            _release_delivery(delivery_key)
        print(f"[ERROR] {error}")
        return jsonify({"status": "error", "msg": "Internal server error"}), 500


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
    broker, time_str, H, mt4_context, mt5_context, conclusion, broker_dt
):
    def ico(s):
        return {"BUY": "Mua", "SELL": "Bán"}.get(s, "Chờ")

    now_s = fmt_time(broker_dt)
    note = get_schedule_note(broker_dt)

    mt4_pairs = " | ".join(
        f"{symbol}:{mt4_context.get('pair_dirs', {}).get(symbol, 'WAIT')}@{mt4_context.get('pair_entry_times', {}).get(symbol) or 'WAIT'}"
        for symbol in SIGNAL_PAIRS
    )
    mt5_pairs = " | ".join(
        f"{symbol}:{mt5_context.get('pair_dirs', {}).get(symbol, 'WAIT')}@{mt5_context.get('pair_entry_times', {}).get(symbol) or 'WAIT'}"
        for symbol in SIGNAL_PAIRS
    )
    return (
        f"=== BAO CAO DOI CHIEU ===\n"
        f"Thoi gian: {now_s}\n"
        f"Logical slot: H={H} | Phat: {time_str} Broker\n"
        f"Tap trung: {note}\n"
        f"===========================\n\n"
        f"--- {broker} (MT4) ---\n"
        f"  {mt4_pairs}\n"
        f"  => XAU {ico(mt4_context.get('signal'))} @ {mt4_context.get('entry_time')}\n\n"
        f"--- MT5 ---\n"
        f"  {mt5_pairs}\n"
        f"  => XAU {ico(mt5_context.get('signal'))} @ {mt5_context.get('entry_time')}\n\n"
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
    print("  MT4-MT5 Dual Signal Server v2.12 / signal v72")
    print(f"  Symbols: {', '.join(SIGNAL_PAIRS)}")
    print(f"  Target Hours: {TARGET_HOURS}")
    print("  Broker clock: live-tick calibrated, fail-closed")
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
