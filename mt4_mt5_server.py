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
from domain.signal_rules import (
    apply_entry_rule,
    classify_four_h1_group,
    classify_three_candle_group,
    derive_signal_base,
    derive_xau_entry_basis,
    select_xau_entry_time,
)

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
GBPUSD_SYMBOL = "GBPUSD"
GBPAUD_SYMBOL = "GBPAUD"
SIGNAL_PAIRS = ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
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
    return "STAGE A ENTRY + H3 THREE-H1 / H7+ FOUR-H1 SIGNALS"


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
# SIGNAL LOGIC AND MT5 DATA FETCHER
# =====================================================================
def _resolved_direction(symbol, timeframe, candle_dt, fallback_delta):
    target_ts = broker_datetime_to_ts(candle_dt)
    direction = candle_dir(get_candle_by_ts(symbol, timeframe, target_ts))
    if direction in ("TANG", "GIAM"):
        return direction
    if direction != "DOJI":
        return None
    fallback_ts = broker_datetime_to_ts(candle_dt - fallback_delta)
    fallback = candle_dir(get_candle_by_ts(symbol, timeframe, fallback_ts))
    if fallback not in ("TANG", "GIAM"):
        return None
    if timeframe == mt5.TIMEFRAME_M15:
        return "GIAM" if fallback == "TANG" else "TANG"
    return fallback


def _fetch_stage_a_entry(broker_dt, slot):
    slot_dt = broker_dt.replace(hour=int(slot), minute=0, second=0, microsecond=0)
    m15 = timedelta(minutes=15)
    base = _resolved_direction(XAUUSD_SYMBOL, mt5.TIMEFRAME_M15, slot_dt - 2 * m15, m15)
    patterns = tuple(
        _resolved_direction(XAUUSD_SYMBOL, mt5.TIMEFRAME_M15, slot_dt - offset * m15, m15)
        for offset in (3, 4, 5)
    )
    xau_offset15 = _resolved_direction(XAUUSD_SYMBOL, mt5.TIMEFRAME_M15, slot_dt - m15, m15)
    basis = derive_xau_entry_basis(base, patterns, xau_offset15)
    gbpaud_initial = _resolved_direction(GBPAUD_SYMBOL, mt5.TIMEFRAME_M15, slot_dt - m15, m15)
    followup = _resolved_direction(GBPAUD_SYMBOL, mt5.TIMEFRAME_M15, slot_dt + 2 * m15, m15)
    return select_xau_entry_time(slot, basis, gbpaud_initial, followup)


def _h3_source_context(broker_dt, symbol):
    for days_back in range(1, 8):
        candidate = broker_dt.date() - timedelta(days=days_back)
        if candidate.weekday() >= 5:
            continue
        day_start = datetime.combine(candidate, datetime.min.time())
        directions = tuple(
            _resolved_direction(
                symbol, mt5.TIMEFRAME_H1, day_start.replace(hour=hour), timedelta(hours=1)
            )
            for hour in (4, 3, 2)
        )
        if directions[0] not in ("TANG", "GIAM"):
            continue
        group = classify_three_candle_group(directions)
        signal = derive_signal_base(directions[0], group) if group else "WAIT"
        return {"signal": signal, "group": group, "directions": directions, "source": day_start}
    return {"signal": "WAIT", "group": None, "directions": (), "source": None}


def _h3_context_for_pair(broker_dt, symbol):
    if broker_dt.weekday() != 3:
        return _h3_source_context(broker_dt, symbol)
    monday_dt = broker_dt - timedelta(days=3)
    context = _h3_source_context(monday_dt, symbol)
    if context.get("group") == "SW":
        return {**context, "signal": "WAIT", "thursday_wait_until_h7": True}
    return {**context, "reused_monday": monday_dt.date().isoformat()}


def _h1_context_for_pair(broker_dt, slot, symbol, entry_time):
    slot_dt = broker_dt.replace(hour=int(slot), minute=0, second=0, microsecond=0)
    if int(slot) == 3:
        return _h3_context_for_pair(broker_dt, symbol)
    plus_1_entry = f"{int(slot) + 1:02d}:25"
    base_dt = slot_dt if entry_time == plus_1_entry else slot_dt - timedelta(hours=1)
    if broker_dt < base_dt + timedelta(hours=1):
        return {"signal": "WAIT", "group": None, "directions": (), "source": base_dt}
    directions = tuple(
        _resolved_direction(symbol, mt5.TIMEFRAME_H1, base_dt - timedelta(hours=index), timedelta(hours=1))
        for index in range(4)
    )
    group = classify_four_h1_group(directions)
    signal_base = derive_signal_base(directions[0], group) if group else "WAIT"
    return {
        "signal": apply_entry_rule(signal_base, entry_time, slot),
        "group": group,
        "directions": directions,
        "source": base_dt,
    }


def calculate_context(slot, entry_time, pair_dirs, pair_groups=None):
    """Normalize one terminal's final v71 context."""
    normalized = {
        symbol: pair_dirs.get(symbol) if pair_dirs.get(symbol) in ("BUY", "SELL", "WAIT") else "WAIT"
        for symbol in SIGNAL_PAIRS
    }
    groups = {
        symbol: value if value in ("SW", "BT", "WAIT", None) else None
        for symbol, value in dict(pair_groups or {}).items()
        if symbol in SIGNAL_PAIRS
    }
    return {
        "signal": normalized["XAUUSD"],
        "entry_time": entry_time,
        "pair_dirs": normalized,
        "pair_groups": groups,
    }


def fetch_mt5_data(broker_dt, slot):
    """Read Stage-A entry and independent H1 pair signals from MT5."""
    if not mt5_ready:
        return calculate_context(slot, None, {})
    if int(slot) == 3 and broker_dt.weekday() == 3:
        h3_evidence = {
            symbol: _h3_context_for_pair(broker_dt, symbol)
            for symbol in SIGNAL_PAIRS
        }
        if h3_evidence["XAUUSD"].get("group") == "SW":
            return calculate_context(
                slot,
                None,
                {symbol: value["signal"] for symbol, value in h3_evidence.items()},
                {symbol: value["group"] for symbol, value in h3_evidence.items()},
            )
    entry = _fetch_stage_a_entry(broker_dt, slot)
    entry_time = entry.get("entry_time")
    if entry.get("state") != "READY" or not entry_time:
        return calculate_context(slot, None, {})
    evidence = {
        symbol: _h1_context_for_pair(broker_dt, slot, symbol, entry_time)
        for symbol in SIGNAL_PAIRS
    }
    return calculate_context(
        slot,
        entry_time,
        {symbol: value["signal"] for symbol, value in evidence.items()},
        {symbol: value["group"] for symbol, value in evidence.items()},
    )

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

        direction_fields = tuple(f"{symbol.lower()}_signal" for symbol in SIGNAL_PAIRS)
        group_fields = tuple(f"{symbol.lower()}_group" for symbol in SIGNAL_PAIRS)
        # Sanitize string fields
        for key in ("broker", *direction_fields, *group_fields):
            val = data.get(key, "")
            if not isinstance(val, str):
                data[key] = str(val)
            data[key] = data[key][:50]  # Limit length
        terminal_wait = data.get("terminal_wait") is True
        entry_value = data.get("entry_time")
        valid_entry = isinstance(entry_value, str) and (
            terminal_wait and entry_value == ""
            or _entry_datetime(datetime.now(), entry_value) is not None
        )
        if not valid_entry:
            return jsonify({"error": "invalid entry_time"}), 400

        broker_dt = get_broker_time()
        print(f"\n{'='*55}")
        broker_offset = BROKER_CLOCK.utc_offset_for_date(broker_dt.date())
        print(f"[{fmt_time(broker_dt)} GMT{broker_offset:+d}] Nhan tu MT4:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        broker = data.get("broker", "MT4")
        time_str = data.get("time", "")

        try:
            H = int(data.get("slot"))
        except (TypeError, ValueError):
            return jsonify({"error": "slot must be an integer"}), 400
        if H not in TARGET_HOURS:
            return jsonify({"error": "inactive slot"}), 400
        mt4_context = calculate_context(
            H,
            data.get("entry_time"),
            {symbol: data.get(f"{symbol.lower()}_signal") for symbol in SIGNAL_PAIRS},
            {symbol: data.get(f"{symbol.lower()}_group") for symbol in SIGNAL_PAIRS},
        )
        mt4_signal = mt4_context["signal"]
        if time_str != get_signal_time_for_slot(broker_dt, H):
            return jsonify({"error": "request does not match the Broker publication clock"}), 409
        if is_slot_suppressed(broker_dt, H):
            return jsonify({"status": "suppressed", "slot": H}), 200

        deactivated = is_deactivated_slot(broker_dt, H)
        delivery_key = _delivery_key(broker_dt, H)
        terminal_status = _terminal_delivery_status(delivery_key)
        if terminal_status == "missed":
            return jsonify({"status": "missed", "slot": H}), 200
        if terminal_status == "delivered":
            return jsonify({"status": "duplicate", "slot": H}), 200
        if terminal_wait:
            valid_terminal_wait = (
                H == 3
                and broker_dt.weekday() == 3
                and mt4_signal == "WAIT"
                and mt4_context.get("pair_groups", {}).get("XAUUSD") == "SW"
            )
            if not valid_terminal_wait:
                return jsonify({"error": "invalid terminal_wait context"}), 409
            if not _start_delivery(delivery_key):
                return jsonify({"status": "retry", "slot": H, "reason": "IN_PROGRESS"}), 503
            mt5_data = fetch_mt5_data(broker_dt, H)
            matched = (
                mt5_data.get("signal") == "WAIT"
                and mt5_data.get("pair_groups", {}).get("XAUUSD") == "SW"
            )
            if not matched:
                _release_delivery(delivery_key)
                delivery_key = None
                return jsonify({
                    "status": "retry",
                    "slot": H,
                    "reason": "MT5_H3_CONTEXT_MISMATCH",
                }), 425
            _complete_delivery(delivery_key)
            delivery_key = None
            return jsonify({
                "status": "wait_until_h7",
                "slot": H,
                "matched": matched,
            }), 200
        if mt4_signal == "WAIT" or _entry_datetime(
            broker_dt, mt4_context.get("entry_time")
        ) is None:
            return jsonify({"status": "retry", "slot": H, "reason": "MT4_WAIT"}), 425
        if not _start_delivery(delivery_key):
            terminal_status = _terminal_delivery_status(delivery_key)
            if terminal_status == "missed":
                return jsonify({"status": "missed", "slot": H}), 200
            if terminal_status == "delivered":
                return jsonify({"status": "duplicate", "slot": H}), 200
            return jsonify({"status": "retry", "slot": H, "reason": "IN_PROGRESS"}), 503

        mt5_data = fetch_mt5_data(broker_dt, H)
        mt5_signal = mt5_data["signal"]
        mt4_entry = mt4_context.get("entry_time")
        mt5_entry = mt5_data.get("entry_time")

        if mt5_signal == "WAIT" or _entry_datetime(broker_dt, mt5_entry) is None:
            _release_delivery(delivery_key)
            delivery_key = None
            return jsonify({"status": "retry", "slot": H, "reason": "MT5_WAIT"}), 425
        delivery_dt = get_broker_time()
        if _is_past_earliest_entry(delivery_dt, mt4_entry, mt5_entry):
            _mark_delivery_missed(delivery_key)
            delivery_key = None
            return jsonify({
                "status": "missed",
                "slot": H,
                "mt4_entry_time": mt4_entry,
                "mt5_entry_time": mt5_entry,
            }), 200

        pair_matches = mt4_context.get("pair_dirs") == mt5_data.get("pair_dirs")
        if pair_matches and mt4_entry == mt5_entry:
            conclusion = f"HOP LUU 5 PAIRS @ {mt4_entry}"
        else:
            conclusion = (
                f"XUNG DOT: MT4={mt4_context.get('pair_dirs')}@{mt4_entry} "
                f"vs MT5={mt5_data.get('pair_dirs')}@{mt5_entry} - KHONG VAO"
            )

        if deactivated:
            msg = build_deactivated_warning(broker, time_str, H, delivery_dt)
        else:
            msg = build_telegram(
                broker, time_str, H, mt4_context, mt5_data, conclusion, delivery_dt
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
            "mt4_entry_time": mt4_entry,
            "mt5_entry_time": mt5_entry,
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
    broker, time_str, H, mt4_context, mt5_context, conclusion, broker_dt
):
    def ico(s):
        return {"BUY": "Mua", "SELL": "Bán"}.get(s, "Chờ")

    now_s = fmt_time(broker_dt)
    note = get_schedule_note(broker_dt)

    mt4_pairs = " | ".join(
        f"{symbol}:{mt4_context.get('pair_dirs', {}).get(symbol, 'WAIT')}"
        for symbol in SIGNAL_PAIRS
    )
    mt5_pairs = " | ".join(
        f"{symbol}:{mt5_context.get('pair_dirs', {}).get(symbol, 'WAIT')}"
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
    print("  MT4-MT5 Dual Signal Server v2.10 / signal v71")
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
