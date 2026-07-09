# -*- coding: utf-8 -*-
"""
MT5 Multi-Timeframe Signal Bot v3.11.0
"""
import os
import sys
import json
import time
import calendar
import threading
import socket
from datetime import datetime, timedelta, timezone
import urllib.request

from utils import send_telegram_raw, send_telegram_with_keyboard, get_signal_icon, vn_direction
from oak_trading_reminders import get_day_notes
from oak_logger import setup_logger
from repositories.sqlite_store import SQLiteStore
from secret_store import resolve_telegram_token, migrate_plaintext_tokens
from telegram_client import telegram_get_me

log = setup_logger("signal")

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
    DASHBOARD_URL = _cfg.get("dashboard_url", "")
except Exception:
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHAT_ID = ""
    MT5_PATH = ""
    DASHBOARD_URL = ""
    print("[WARN] config.json not found or invalid.")

SYMBOL = "GBPUSD"
TARGET_HOURS = list(range(3, 16))
# Bump when pair-direction / slot rules change to trace rebuilds in logs.
SIGNAL_LOGIC_VERSION = 3
BROKER_GMT = 0
DIRECTION_POLL_INTERVAL = 1
DIRECTION_EVENT_PORT = 8765

# =====================================================================
# HEARTBEAT - publish to SQLite for GUI to read
# =====================================================================
_store = SQLiteStore()
_active_profile = ""  # Module-level, set by main() at startup

def _check_telegram_api(token):
    """Check Telegram API reachability via getMe.

    Returns (ok, bot_name_or_error_category).
    """
    if not token:
        return False, "no_token"
    ok, result = telegram_get_me(token)
    if ok:
        return True, result
    return False, result

def load_profile_config(profile_name, profiles_path=None):
    """Load a single profile's config dict from profiles.json.

    Returns {} if profile_name is empty, profiles.json is missing/invalid,
    or the profile isn't found. Never raises.
    """
    if not profile_name:
        return {}
    if profiles_path is None:
        profiles_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles.json")
    try:
        with open(profiles_path, "r", encoding="utf-8") as f:
            profiles_data = json.load(f)
        return profiles_data.get(profile_name, {})
    except Exception:
        return {}


def publish_heartbeat(profile, mt5_connected, mt5_error="", profiles_path=None):
    """Publish heartbeat to SQLite. Called every ~2s from main loop."""
    from datetime import datetime, timezone
    acc = None
    if mt5_connected:
        try:
            acc = mt5.account_info()
        except Exception:
            pass

    # Telegram config is per-profile: tele_token/tele_chat live in profiles.json
    # under the running profile, not just the global config.json. Falling back
    # to the global values keeps config.json-only setups working.
    profile_cfg = load_profile_config(profile, profiles_path=profiles_path)
    tg_token = resolve_telegram_token(profile, profile_cfg.get("tele_token"), global_fallback=TELEGRAM_TOKEN)
    tg_chat = profile_cfg.get("tele_chat") or TELEGRAM_CHAT_ID
    tg_configured = bool(tg_token and tg_chat)
    tg_api_ok, tg_bot = _check_telegram_api(tg_token) if tg_token else (False, "")
    tg_last = datetime.now(timezone.utc).isoformat() if tg_api_ok else ""

    state = "connected" if mt5_connected else "disconnected"
    _store.publish_heartbeat(
        profile=profile,
        state=state,
        server=acc.server if acc else "",
        login=acc.login if acc else 0,
        balance=acc.balance if acc else 0,
        equity=acc.equity if acc else 0,
        last_error=mt5_error,
        telegram_configured=tg_configured,
        telegram_api_ok=tg_api_ok,
        telegram_last_check=tg_last,
        telegram_bot_name=tg_bot,
    )


# =====================================================================
# STATE PERSISTENCE - survive bot restarts
# =====================================================================
_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_state.json")

def _trading_date():
    """Current trading date in broker time."""
    try:
        if "get_broker_time" in globals():
            return get_broker_time().date()
    except Exception:
        pass
    return (datetime.now(tz=timezone.utc).replace(tzinfo=None) + timedelta(hours=BROKER_GMT)).date()

def _load_state():
    """Load persisted state from disk. Returns dict with day_signals, sent_today, etc."""
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

    # Only accept state from the current trading day, not raw UTC date.
    today_str = _trading_date().isoformat()
    if data.get("date") != today_str:
        return {}

    # Rebuild day_signals keys as (date, hour) tuples matching main loop format
    day_signals = {}
    for k, v in data.get("day_signals", {}).items():
        day_signals[(datetime.strptime(data["date"], "%Y-%m-%d").date(), int(k))] = v

    return {
        "day_signals": day_signals,
        "sent_today": set(tuple(x) for x in data.get("sent_today", [])),
        "d_direction": data.get("d_direction"),
        "d_direction_date": data.get("d_direction_date"),
        "d_matched_hour": data.get("d_matched_hour"),
    }

def _save_state(day_signals, sent_today):
    """Persist state to disk."""
    today_str = _trading_date().isoformat()
    # Convert day_signals keys to string for JSON
    ds_json = {}
    for (d, h), v in day_signals.items():
        ds_str = d if isinstance(d, str) else d.isoformat()
        if ds_str == today_str:
            ds_json[str(h)] = v
    st_json = [[d.isoformat() if hasattr(d, 'isoformat') else d, h] for d, h in sent_today]
    data = {
        "date": today_str,
        "day_signals": ds_json,
        "sent_today": st_json,
        "d_direction": d_direction,
        "d_direction_date": d_direction_date.isoformat() if d_direction_date else None,
        "d_matched_hour": d_matched_hour,
    }
    try:
        tmp_file = _STATE_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp_file, _STATE_FILE)
    except Exception as e:
        print(f"[WARN] Cannot save state: {e}")

_SIGNALS_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signals_log.json")


def get_current_prices(pair_dirs):
    """Lấy giá market hiện tại (tick)."""
    prices = {}
    for pair, direction in pair_dirs.items():
        if direction not in ("BUY", "SELL"):
            continue
        try:
            tick = mt5.symbol_info_tick(pair)
            if tick:
                prices[pair] = round(tick.bid, 5)
        except Exception as e:
            log.warning("MT5 tick fetch error for %s: %s", pair, e)
    return prices

def log_signal(H, broker_dt, sig, entry_time, pair_dirs, hour_note, is_missed=False):
    """Append signal data to signals_log.json for website consumption."""
    current_prices = get_current_prices(pair_dirs) if sig in ("BUY", "SELL") else {}
    record = {
        "date": broker_dt.date().isoformat(),
        "hour": H,
        "ts": datetime.now().timestamp(),
        "signal": sig,
        "entry_time": None,
        "pair_dirs": pair_dirs,
        "entry_prices": {},
        "current_prices": current_prices,
        "hour_note": hour_note,
        "missed": is_missed,
        "d_direction": d_direction,
    }
    try:
        data = []
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        # Deduplicate: replace existing entry for same (date, hour)
        key = (record["date"], record["hour"])
        data = [d for d in data if (d["date"], d["hour"]) != key]
        data.append(record)
        data = data[-2000:]
        with open(_SIGNALS_LOG, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Cannot log signal: {e}")

def _parse_news_for_dashboard(news_lines):
    """Parse news strings like '• 19:30 CAD 🔴 GDP m/m' into structured objects."""
    import re
    from oak_trading_reminders import is_critical_news_title
    items = []
    for line in news_lines:
        raw = line
        line = line.lstrip("•- ").strip()
        line = re.sub(r"^⚠️\s*", "", line)
        # Match: HH:MM CURRENCY [emoji] TITLE
        m = re.match(r"(\d{1,2}:\d{2})\s+(\w+)\s+(.+)", line)
        if m:
            time_str, currency, rest = m.group(1), m.group(2), m.group(3)
            impact = "medium"
            title = rest
            if "\U0001f534" in rest or "🔴" in rest:
                impact = "high"
                title = rest.replace("\U0001f534", "").replace("🔴", "").strip()
            elif "\U0001f7e0" in rest or "🟠" in rest:
                impact = "medium"
                title = rest.replace("\U0001f7e0", "").replace("🟠", "").strip()
            elif "\U0001f7e2" in rest or "🟢" in rest:
                impact = "low"
                title = rest.replace("\U0001f7e2", "").replace("🟢", "").strip()
            title = re.sub(r"\s*\[TIN NỔI BẬT\]\s*", "", title).strip()
            critical = is_critical_news_title(title) or "TIN NỔI BẬT" in raw
            if critical:
                impact = "high"
            items.append({
                "time": time_str,
                "currency": currency,
                "title": title,
                "impact": impact,
                "critical": critical,
            })
    # Critical first
    items.sort(key=lambda x: (0 if x.get("critical") else 1, x.get("time") or "99:99"))
    return items

def select_signals_for_dashboard(all_signals):
    """Keep every signal that still has pair data so history can be republished across days."""
    return [s for s in all_signals if s.get("pair_dirs")]

def d1_match_note(direction):
    if direction == "BUY":
        return "XAUUSD: Mua BUY (tick match D1)"
    if direction == "SELL":
        return "XAUUSD: Bán SELL (tick match D1)"
    return "XAUUSD: tick match D1"

def push_to_dashboard():
    """Push data to dashboard API (best effort, non-blocking)."""
    dashboard_url = os.environ.get("DASHBOARD_API_URL", "") or DASHBOARD_URL
    if not dashboard_url:
        print("[DASHBOARD] No dashboard_url configured, skip push.")
        return
    api_key = os.environ.get("DASHBOARD_API_KEY", "") or _cfg.get("dashboard_api_key", "")
    print(f"[DASHBOARD] Pushing to {dashboard_url} ...")
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        # Push signals log backlog for history pages; dashboard filters today's
        # view on the frontend, so the bot must not drop prior-day records here.
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                all_signals = json.load(f)
            signals = select_signals_for_dashboard(all_signals)
            if signals:
                payload = json.dumps(signals).encode("utf-8")
                req = urllib.request.Request(
                    f"{dashboard_url}/api/signals",
                    data=payload,
                    headers=headers
                )
                resp = urllib.request.urlopen(req, timeout=15)
                resp.read()
                print(f"[DASHBOARD] Signals pushed OK ({len(signals)} items)")
        # Push state
        if os.path.exists(_STATE_FILE) and os.path.getsize(_STATE_FILE) > 2:
            with open(_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            if state:
                print(f"[DASHBOARD] Pushing state: d_direction={state.get('d_direction')}, date={state.get('date')}")
                payload = json.dumps(state).encode("utf-8")
                req = urllib.request.Request(
                    f"{dashboard_url}/api/state",
                    data=payload,
                    headers=headers
                )
                resp = urllib.request.urlopen(req, timeout=15)
                resp.read()
                print(f"[DASHBOARD] State pushed OK")
        # Push news
        news_cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news_cache_VN.json")
        if os.path.exists(news_cache) and os.path.getsize(news_cache) > 2:
            with open(news_cache, "r", encoding="utf-8") as f:
                cache = json.load(f)
            raw_news = cache.get("news", []) if cache else []
            parsed = _parse_news_for_dashboard(raw_news)
            if parsed:
                payload = json.dumps(parsed).encode("utf-8")
                req = urllib.request.Request(
                    f"{dashboard_url}/api/news",
                    data=payload,
                    headers=headers
                )
                resp = urllib.request.urlopen(req, timeout=15)
                resp.read()
                print(f"[DASHBOARD] News pushed OK ({len(parsed)} items)")
        # Push heartbeat (profile-specific)
        try:
            hb = _store.get_heartbeat(_active_profile)
            if hb:
                payload = json.dumps(hb).encode("utf-8")
                req = urllib.request.Request(
                    f"{dashboard_url}/api/heartbeat?profile={_active_profile}",
                    data=payload,
                    headers=headers
                )
                resp = urllib.request.urlopen(req, timeout=10)
                resp.read()
                print(f"[DASHBOARD] Heartbeat pushed OK ({_active_profile})")
        except Exception as e:
            print(f"[DASHBOARD] Heartbeat push error: {e}")
    except Exception as e:
        print(f"[DASHBOARD] Push error: {e}")

def push_prices_to_dashboard():
    """Push giá realtime lên Redis."""
    dashboard_url = os.environ.get("DASHBOARD_API_URL", "") or DASHBOARD_URL
    if not dashboard_url:
        return
    api_key = os.environ.get("DASHBOARD_API_KEY", "") or _cfg.get("dashboard_api_key", "")
    try:
        prices = {}
        for pair in ALL_PAIRS:
            try:
                tick = mt5.symbol_info_tick(pair)
                if tick:
                    prices[pair] = round(tick.bid, 5)
            except Exception as e:
                log.warning("Dashboard price fetch error for %s: %s", pair, e)
        if prices:
            payload = json.dumps(prices).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["X-API-Key"] = api_key
            req = urllib.request.Request(
                f"{dashboard_url}/api/prices",
                data=payload,
                headers=headers
            )
            resp = urllib.request.urlopen(req, timeout=10)
            resp.read()
            print(f"[DASHBOARD] Prices pushed OK ({len(prices)} pairs)")
    except Exception as e:
        print(f"[DASHBOARD] Prices push error: {e}")

def get_schedule_reminders(broker_dt):
    """Kiểm tra các ngày đặc biệt trong tháng - dùng chung get_day_notes."""
    notes = get_day_notes(broker_dt, lang="VN")
    return [n.upper() for n in notes]

# =====================================================================
# TELEGRAM
# =====================================================================
def send_telegram(text):
    try:
        return send_telegram_raw(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, text)
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")
        return None

d_reminder_sent_date = None

def send_d_direction_reminder():
    global d_reminder_sent_date
    broker_dt = get_broker_time()
    today = broker_dt.date()
    if d_reminder_sent_date == today:
        return
    weekday_label = "THỨ 5/THỨ 6" if broker_dt.weekday() in (3, 4) else "THỨ 6"
    msg = (
        f"📝 NHẬP DIRECTION CHO {weekday_label}\n"
        "============================\n"
        "Gõ BUY hoặc SELL qua Telegram\n"
        "để lưu D direction cho ngày hiện tại.\n"
        "Khung nhắc hiện tại: 4:00 VN.\n\n"
        "Ví dụ: gõ 'BUY' hoặc 'SELL'\n"
        "============================\n"
        "Nếu lưu vào thứ 6, thứ 2 bot sẽ tự đảo lại D\n"
        "để dùng cho nhóm GBP + XAUUSD."
    )
    send_telegram(msg)
    d_reminder_sent_date = today
    print("  [D-REMINDER] Sent daily reminder")

def check_d_direction_input():
    """Đọc D-direction từ file (mimo_bot.py ghi vào), không poll Telegram trực tiếp."""
    global d_direction, d_direction_date
    d_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "d_direction_input.txt")
    if not d_direction_lock.acquire(blocking=False):
        return
    try:
        if not os.path.exists(d_file):
            return
        # Validate file size (max 10 bytes)
        if os.path.getsize(d_file) > 10:
            os.remove(d_file)
            return
        with open(d_file, "r", encoding="utf-8") as f:
            text = f.read().strip().upper()
        os.remove(d_file)
        if text in ("BUY", "SELL", "MUA", "BAN"):
            direction = "BUY" if text in ("BUY", "MUA") else "SELL"
            set_d_direction(direction)
            broker_weekday = get_broker_time().weekday()
            day_label = "thứ 6" if broker_weekday == 4 else "thứ 5" if broker_weekday == 3 else "ngày hiện tại"
            print(f"  [D-DIRECTION] Saved {day_label} D to {direction}")
            # Save state to disk (read existing, update d_direction fields)
            state = {}
            if os.path.exists(_STATE_FILE) and os.path.getsize(_STATE_FILE) > 2:
                with open(_STATE_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)
            # Ensure date field exists
            if "date" not in state:
                state["date"] = _trading_date().isoformat()
            state["d_direction"] = d_direction
            state["d_direction_date"] = d_direction_date.isoformat() if d_direction_date else None
            state["d_matched_hour"] = d_matched_hour
            tmp = _STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
            os.replace(tmp, _STATE_FILE)
            print(f"  [D-DIRECTION] State saved: d_direction={state.get('d_direction')}")
            restore_d1_match_from_today_signals()
            push_to_dashboard()
    except Exception as e:
        log.warning("State save error: %s", e)
    finally:
        d_direction_lock.release()

def restore_d1_match_from_today_signals():
    """Khôi phục mốc match D1 từ tín hiệu hôm nay đã có sẵn trên disk."""
    global d_matched_hour
    if d_direction is None or d_matched_hour is not None:
        return False
    today = _trading_date()
    for hour in TARGET_HOURS:
        payload = day_signals.get((today, hour))
        if payload and payload.get("signal") == d_direction:
            d_matched_hour = hour
            print(f"  [D-MATCH] Restored from existing H={hour} signal")
            _save_state(day_signals, sent_today)
            return True
    return False


def d_direction_watcher():
    """ponytail: 1s file watcher để nhận D nhanh hơn; upgrade path là webhook/queue IPC nếu bỏ file trung gian."""
    while True:
        try:
            check_d_direction_input()
        except Exception as e:
            log.warning("D-direction watcher error: %s", e)
        time.sleep(DIRECTION_POLL_INTERVAL)

def d_direction_event_server():
    """ponytail: localhost ping để MT5 nhặt D gần như tức thì; file watcher vẫn là fallback nếu ping fail."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", DIRECTION_EVENT_PORT))
        server.listen(5)
        server.settimeout(1.0)
    except OSError as exc:
        log.warning("D-direction event server unavailable: %s", exc)
        try:
            server.close()
        except Exception:
            pass  # Best effort cleanup
        return

    print(f"  [D-DIRECTION] Listening on 127.0.0.1:{DIRECTION_EVENT_PORT}")
    while True:
        try:
            conn, _addr = server.accept()
        except socket.timeout:
            continue
        except Exception:
            continue
        try:
            with conn:
                try:
                    conn.recv(64)
                except Exception:
                    pass  # Expected on client disconnect
            check_d_direction_input()
        except Exception as e:
            log.warning("D-direction event handler error: %s", e)
# =====================================================================
# TIME HELPERS
# =====================================================================
def fmt_time(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def fmt_hour(h):
    return f"{h:02d}"

def broker_time_to_ts(broker_dt, hour, minute=0, second=0):
    """Chuyen broker datetime + hour/minute thanh UTC timestamp de so sanh voi rate."""
    target_broker = broker_dt.replace(hour=hour, minute=minute, second=second, microsecond=0)
    target_utc = target_broker - timedelta(hours=BROKER_GMT)
    return calendar.timegm(target_utc.timetuple())

# =====================================================================
# MT5 CANDLE HELPER
# =====================================================================
def get_candle_by_ts(symbol, timeframe, target_ts):
    """Lay nến gan nhat voi UTC timestamp. Tra ve dict hoac None."""
    if not mt5.symbol_select(symbol, True):
        print(f"[WARN] Khong the select symbol: {symbol}")
        return None

    # Tăng số nến để覆盖 sâu hơn (M5: 5000 ≈ 17 ngày, M30/H1 đủ lớn)
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 5000)
    if rates is None or len(rates) == 0:
        print(f"[WARN] Khong lay duoc du lieu {symbol} TF={timeframe}")
        return None

    best = None
    min_diff = float("inf")

    for r in rates:
        diff = abs(r["time"] - target_ts)
        if diff < min_diff:
            min_diff = diff
            best = r

    max_diff = 180
    if best and min_diff <= max_diff:
        return best
    return None

def candle_direction(candle):
    if candle is None:
        return None
    o = candle["open"]
    c = candle["close"]
    body = abs(c - o)
    full_range = candle["high"] - candle["low"]
    if full_range == 0:
        return "DOJI"
    if body / full_range < 0.02:
        return "DOJI"
    if c > o:
        return "TANG"
    elif c < o:
        return "GIAM"
    return "DOJI"

def resolve_doji(symbol, timeframe, target_ts, broker_dt):
    """Nến DOJI → lùi 1 nến trước cùng khung, lấy direction nến trước đó."""
    prev_offset = 300 if timeframe == mt5.TIMEFRAME_M5 else 1800  # M5=5ph, M30=30ph
    prev_ts = target_ts - prev_offset
    prev_candle = get_candle_by_ts(symbol, timeframe, prev_ts)
    d = candle_direction(prev_candle)
    if d and d != "DOJI":
        return d
    return None

def get_h1_candle_for_slot(broker_dt, H):
    """Lấy nến H1 của GBPUSD tại (H-1):00 — nến trước slot hiện tại."""
    if H < 1:
        return None
    ts_h1 = broker_time_to_ts(broker_dt, H - 1, 0, 0)
    c_h1 = get_candle_by_ts(SYMBOL, mt5.TIMEFRAME_H1, ts_h1)
    if c_h1 is None:
        print(f"  [H1] Không có dữ liệu H1 GBPUSD tại {H-1}:00")
        return None
    return c_h1

def get_xauusd_m30_signal(broker_dt, H):
    """Lấy signal từ nến M30 của XAUUSD tại (H-1):30."""
    if H < 1:
        return None
    ts_m30 = broker_time_to_ts(broker_dt, H - 1, 30, 0)
    c_m30 = get_candle_by_ts("XAUUSD", mt5.TIMEFRAME_M30, ts_m30)
    if c_m30 is None:
        print(f"  [M30 XAUUSD] Không có dữ liệu tại {H-1}:30")
        return None
    d_m30 = candle_direction(c_m30)
    if d_m30 == "DOJI":
        d_m30 = resolve_doji("XAUUSD", mt5.TIMEFRAME_M30, ts_m30, broker_dt)
        if d_m30 is None:
            d_m30 = "TANG"
        print(f"  [DOJI] M30 XAUUSD@{H-1}:30 DOJI -> fallback: {d_m30}")
    if d_m30 and d_m30 != "DOJI":
        return "BUY" if d_m30 == "TANG" else "SELL"
    return None

def apply_xauusd_m30_logic(pair_dirs, sig, broker_dt, H):
    """Cùng chiều XAUUSD M30 -> đảo XAUUSD, ngược chiều -> theo XAUUSD M30.

    Baseline cho GBP:
    - H=2..8: rule ghi 'XAUUSD' → rebuild GBP theo final XAU sau flip
      (GBPAUD ngược XAU, GBPJPY cùng XAU).
    - H=9,11,12,15: rule ghi 'Signal' → GBP bám pattern Signal (sig),
      CHỈ cập nhật dòng XAUUSD (có thể lệch Signal sau M30).
    """
    xau_m30 = get_xauusd_m30_signal(broker_dt, H)
    if xau_m30 is None or "XAUUSD" not in pair_dirs:
        return pair_dirs
    if sig == xau_m30:
        final_xau = "SELL" if xau_m30 == "BUY" else "BUY"
    else:
        final_xau = xau_m30

    # H=2..8: pairs relative to XAUUSD → rebuild from final gold
    if H in (2, 3, 4, 5, 6, 7, 8):
        rebuilt = get_pair_direction(H, final_xau, broker_dt)
        if not rebuilt:
            pair_dirs["XAUUSD"] = final_xau
            return pair_dirs
        pair_dirs.clear()
        pair_dirs.update(rebuilt)
        return pair_dirs

    # H=9,11,12,15,...: pairs relative to pattern Signal — keep GBP, flip XAU only
    pair_dirs["XAUUSD"] = final_xau
    return pair_dirs

def candle_info_line(candle, label):
    if candle is None:
        return f"  {label}: Khong co du lieu"
    d = candle_direction(candle)
    arrow = {"TANG": "\u2191", "GIAM": "\u2193", "DOJI": "\u2194"}.get(d, "")
    vn = vn_direction(d)
    return (
        f"  *{label}: {vn} {arrow}*\n"
        f"    *O={candle['open']:.5f} C={candle['close']:.5f}* "
        f"H={candle['high']:.5f} L={candle['low']:.5f}"
    )

# =====================================================================
# PHAN TICH TIN HIEU
# =====================================================================
def analyze(broker_dt, H):
    ts_m35 = broker_time_to_ts(broker_dt, H, 35)
    ts_m40 = broker_time_to_ts(broker_dt, H, 40)

    c_m35 = get_candle_by_ts(SYMBOL, mt5.TIMEFRAME_M5, ts_m35)
    c_m40 = get_candle_by_ts(SYMBOL, mt5.TIMEFRAME_M5, ts_m40)

    d_m35 = candle_direction(c_m35)
    d_m40 = candle_direction(c_m40)

    if d_m35 is None or d_m40 is None:
        print(f"  [SKIP] Khong du du lieu M5 tai {fmt_hour(H)}:35 / {fmt_hour(H)}:40")
        return {"signal": "WAIT", "report": "Không đủ dữ liệu M5"}
    # DOJI fallback: lùi 1 nến trước cùng khung
    if d_m35 == "DOJI":
        d_m35 = resolve_doji(SYMBOL, mt5.TIMEFRAME_M5, ts_m35, broker_dt)
        if d_m35 is None:
            d_m35 = "TANG"  # fallback cuối: TANG
        print(f"  [DOJI] M5@{fmt_hour(H)}:35 DOJI -> fallback: {d_m35}")
    if d_m40 == "DOJI":
        d_m40 = resolve_doji(SYMBOL, mt5.TIMEFRAME_M5, ts_m40, broker_dt)
        if d_m40 is None:
            d_m40 = "GIAM"  # fallback cuối: GIAM
        print(f"  [DOJI] M5@{fmt_hour(H)}:40 DOJI -> fallback: {d_m40}")

    ts_m30 = broker_time_to_ts(broker_dt, H, 0)
    c_m30 = get_candle_by_ts(SYMBOL, mt5.TIMEFRAME_M30, ts_m30)
    d_m30 = candle_direction(c_m30)

    if d_m30 is None:
        return {"signal": "WAIT", "report": "Không đủ dữ liệu M30"}
    # DOJI fallback: lùi 1 nến trước cùng khung
    if d_m30 == "DOJI":
        d_m30 = resolve_doji(SYMBOL, mt5.TIMEFRAME_M30, ts_m30, broker_dt)
        if d_m30 is None:
            d_m30 = "TANG"  # fallback cuối: TANG
        print(f"  [DOJI] M30@{fmt_hour(H)}:00 DOJI -> fallback: {d_m30}")

    vn_m35 = vn_direction(d_m35)
    vn_m40 = vn_direction(d_m40)
    vn_m30 = vn_direction(d_m30)

    if d_m35 == d_m40:
        signal = "BUY" if d_m30 == "TANG" else "SELL"
        report = (
            f"PATTERN: Cùng chiều ({vn_m35})\n"
            f"{candle_info_line(c_m35, f'M5@{fmt_hour(H)}:35')}\n"
            f"{candle_info_line(c_m40, f'M5@{fmt_hour(H)}:40')}\n"
            f"  -> Lấy M30@{fmt_hour(H)}:00 (Cùng chiều)\n"
            f"{candle_info_line(c_m30, f'M30@{fmt_hour(H)}:00')}"
        )
    else:
        signal = "SELL" if d_m30 == "TANG" else "BUY"
        report = (
            f"PATTERN: Ngược chiều ({vn_m35} + {vn_m40})\n"
            f"{candle_info_line(c_m35, f'M5@{fmt_hour(H)}:35')}\n"
            f"{candle_info_line(c_m40, f'M5@{fmt_hour(H)}:40')}\n"
            f"  -> Lấy M30@{fmt_hour(H)}:00 (Ngược chiều)\n"
            f"{candle_info_line(c_m30, f'M30@{fmt_hour(H)}:00')}"
        )

    return {"signal": signal, "orig_signal": signal, "h1_signal": None, "report": report, "m30_dir": d_m30, "h1_flipped": False}

def get_hour_note(H, weekday=None):
    """Trả note theo H (weekday giữ để tương thích call-site)."""
    notes = {
        2: "GBPJPY cùng XAUUSD, GBPAUD ngược, GBPUSD/GBPCAD --",
        3: "GBPJPY cùng XAUUSD, GBPAUD ngược, GBPUSD/GBPCAD --",
        4: "GBPJPY cùng XAUUSD, GBPAUD ngược, GBPUSD/GBPCAD --",
        5: "GBPJPY cùng XAUUSD, GBPAUD ngược, GBPUSD/GBPCAD --",
        6: "GBPJPY cùng XAUUSD, GBPAUD ngược, GBPUSD/GBPCAD --",
        7: "GBPJPY cùng XAUUSD, GBPAUD ngược, GBPUSD/GBPCAD --",
        8: "GBPJPY cùng XAUUSD, GBPAUD ngược, GBPUSD/GBPCAD --",
        9: "GBPAUD ngược Signal; GBPUSD/GBPJPY/GBPCAD cùng Signal",
        11: "GBPAUD/GBPUSD/GBPJPY ngược Signal; GBPCAD cùng Signal",
        12: "GBPAUD/GBPUSD ngược Signal; GBPJPY/GBPCAD cùng Signal",
        15: "GBPAUD/GBPUSD/GBPCAD/GBPJPY cùng Signal",
    }
    return notes.get(H, "Chỉ Vàng")

GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"]
ALL_PAIRS = GBP_PAIRS + ["XAUUSD"]

# Daily direction for XAUUSD (set via Telegram input)
d_direction = None  # 'BUY' or 'SELL'
d_direction_date = None  # date when set
d_matched_hour = None  # H where signal matched D (stops reporting after)
d_direction_lock = threading.Lock()
day_signals = {}
sent_today = set()

def clear_d_direction_state():
    global d_direction, d_direction_date, d_matched_hour
    d_direction = None
    d_direction_date = None
    d_matched_hour = None

def set_d_direction(direction):
    global d_direction, d_direction_date, d_matched_hour
    d_direction = direction.upper() if direction else None
    d_direction_date = _trading_date() if d_direction else None
    d_matched_hour = None

def clear_expired_d_direction(broker_dt):
    """D-direction only applies to Mon/Thu/Fri broker days."""
    if broker_dt.weekday() not in (1, 2):
        return False
    if d_direction is None and d_direction_date is None and d_matched_hour is None:
        return False
    clear_d_direction_state()
    _save_state(day_signals, sent_today)
    print("  [D-DIRECTION] Cleared expired D-direction state for Tue/Wed")
    return True

def get_effective_d_direction(broker_dt):
    """Thứ 5/6 có thể lưu D direction, nhưng chỉ giá trị thứ 6 mới được đảo để dùng cho thứ 2."""
    if d_direction is None:
        return None
    if d_direction_date is None:
        return d_direction
    if broker_dt.weekday() == 0 and d_direction_date.weekday() == 4:
        return "SELL" if d_direction == "BUY" else "BUY"
    return d_direction

def get_pair_direction(H, signal, broker_dt, h1_signal=None):
    """Tính chiều các cặp theo slot. Signal = hướng pattern (XAUUSD baseline)."""
    global d_direction, d_direction_date
    weekday = broker_dt.weekday()
    today = broker_dt.date()
    result = {}

    if d_direction_date != today and weekday not in (0, 3, 4):
        clear_d_direction_state()
    if signal not in ("BUY", "SELL"):
        return result

    gold = signal
    opposite = "SELL" if gold == "BUY" else "BUY"

    # Mọi slot đều có XAUUSD
    result["XAUUSD"] = gold

    # H=2..8: GBPJPY cùng XAUUSD, GBPAUD ngược XAUUSD, GBPUSD/GBPCAD --
    if H in (2, 3, 4, 5, 6, 7, 8):
        result["GBPJPY"] = gold
        result["GBPAUD"] = opposite
        result["GBPUSD"] = "--"
        result["GBPCAD"] = "--"
    # H=9: GBPAUD ngược Signal; GBPUSD/GBPJPY/GBPCAD cùng Signal
    elif H == 9:
        result["GBPAUD"] = opposite
        result["GBPUSD"] = gold
        result["GBPJPY"] = gold
        result["GBPCAD"] = gold
    # H=11: GBPAUD/GBPUSD/GBPJPY ngược Signal; GBPCAD cùng Signal
    elif H == 11:
        result["GBPAUD"] = opposite
        result["GBPUSD"] = opposite
        result["GBPJPY"] = opposite
        result["GBPCAD"] = gold
    # H=12: GBPAUD/GBPUSD ngược Signal; GBPJPY/GBPCAD cùng Signal
    elif H == 12:
        result["GBPAUD"] = opposite
        result["GBPUSD"] = opposite
        result["GBPJPY"] = gold
        result["GBPCAD"] = gold
    # H=15: tất cả GBP cùng Signal
    elif H == 15:
        for p in GBP_PAIRS:
            result[p] = gold
    # Các slot khác (H=10,13,14,...): chỉ Vàng

    return result

def should_skip_xauusd(H, signal, broker_dt):
    """Kiểm tra có nên ẩn XAUUSD không. Không mutated state.
    Skip từ H=4 sau match D1 tới H=11. H=12+ hiển thị lại."""
    if d_direction is None or broker_dt.weekday() not in (0, 3, 4):
        return False
    if H < 1 or H in (12, 14, 15):
        return False
    if d_matched_hour is not None:
        return True
    if signal == d_direction:
        return False  # First match: hiển thị, caller mark matched
    return False

def mark_xauusd_matched(H):
    """Ghi nhận slot đầu tiên XAUUSD khớp D1 direction."""
    global d_matched_hour
    if d_matched_hour is None:
        d_matched_hour = H
        effective_d = get_effective_d_direction(get_broker_time())
        msg = (
            f"⚠️ XAUUSD ĐÃ MATCH D1 ({effective_d or d_direction})\n"
            f"============================\n"
            f"Slot H={fmt_hour(H)}:45 khớp D direction.\n"
            f"Các slot kế XAUUSD bị ẩn đến H=11.\n"
            f"Hiển thị lại từ H=12."
        )
        send_telegram(msg)
        print(f"  [D-MATCH] XAUUSD matched D1 at H={H}, skipping subsequent slots")

# =====================================================================
# GUI TELEGRAM BAO CAO
# =====================================================================
def send_report(signal_data, H, broker_dt, h1_signal=None):
    sig = signal_data["signal"]
    report = signal_data["report"]
    m30_dir = signal_data.get("m30_dir")
    icon, emoji = get_signal_icon(sig)

    hour_note = get_hour_note(H, broker_dt.weekday())
    note_line = f"📝 {hour_note}\n" if hour_note else ""

    pair_dirs = get_pair_direction(H, sig, broker_dt, h1_signal=signal_data.get("h1_signal"))

    # XAUUSD H1 check: cùng chiều H1 XAUUSD -> đảo, ngược -> giữ nguyên signal
    apply_xauusd_m30_logic(pair_dirs, sig, broker_dt, H)

    if should_skip_xauusd(H, sig, broker_dt):
        pair_dirs.pop("XAUUSD", None)
    elif sig == get_effective_d_direction(broker_dt) and get_effective_d_direction(broker_dt) is not None:
        mark_xauusd_matched(H)  # Ghi nhận lần đầu signal match D1

    pair_lines = []
    for p in ALL_PAIRS:
        d = pair_dirs.get(p)
        if d is None:
            pair_lines.append(f"  {p}: -")
        elif d == "--":
            pair_lines.append(f"  {p}: --")
        else:
            p_icon, _ = get_signal_icon(d)
            p_text = "BUY" if d == "BUY" else "SELL"
            pair_lines.append(f"  {p}: {p_icon} {p_text}")
    pair_text = "\n".join(pair_lines)

    # KẾT LUẬN = pattern Signal (baseline GBP cho H=9+; XAU có thể lệch sau M30)
    conclusion = f"KẾT LUẬN: {icon} {sig}\n"

    msg = (
        f"{emoji} Tín hiệu {SYMBOL} - {icon}\n"
        f"============================\n"
        f"  {fmt_hour(H)}:45 (Broker)\n"
        f"============================\n\n"
        f"{report}\n\n"
        f"============================\n"
        f"{conclusion}"
        f"-------------------\n"
        f"{pair_text}\n"
        f"-------------------\n"
        f"{note_line}"
        f"============================\n"
        f"Chỉ tham khảo. Kỷ luật là sức mạnh!"
    )
    send_telegram(msg)

    # Send inline keyboard for quick order placement
    active_pairs = [(p, d) for p, d in pair_dirs.items() if d in ("BUY", "SELL")]
    if active_pairs:
        keyboard = []
        row = []
        for pair, direction in active_pairs:
            label = f"{'🟢' if direction == 'BUY' else '🔴'} {direction} {pair}"
            callback_data = f"sig:{direction}:{pair}:{H}"
            row.append({"text": label, "callback_data": callback_data})
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        try:
            send_telegram_with_keyboard(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
                                        "⚡ Chọn lệnh nhanh (chỉ cần nhập Lot):",
                                        keyboard, parse_mode=None)
        except Exception as e:
            print(f"[WARN] Inline keyboard error: {e}")

    return pair_dirs

# =====================================================================
# REBUILD: tính lại signals_log từ MT5 khi bot khởi động (tránh push data cũ)
# =====================================================================
def rebuild_slot_signal(broker_dt, h, *, is_missed=True):
    """Recalculate one slot with current logic and overwrite signals_log (date, hour)."""
    if broker_dt.weekday() >= 5:
        return False

    result = analyze(broker_dt, h)
    sig = result.get("signal")
    if sig not in ("BUY", "SELL"):
        return False

    pair_dirs = get_pair_direction(h, sig, broker_dt, h1_signal=result.get("h1_signal"))
    if not pair_dirs:
        return False

    apply_xauusd_m30_logic(pair_dirs, sig, broker_dt, h)

    skip_xau = should_skip_xauusd(h, sig, broker_dt)
    if skip_xau:
        pair_dirs.pop("XAUUSD", None)

    base_note = get_hour_note(h, broker_dt.weekday())
    effective_d = get_effective_d_direction(broker_dt)
    matched_d1 = (sig == effective_d and effective_d is not None)
    if skip_xau or matched_d1:
        hour_note = d1_match_note(effective_d)
    else:
        hour_note = base_note

    log_signal(h, broker_dt, sig, None, pair_dirs, hour_note, is_missed=is_missed)
    return True


def rebuild_signals_on_startup():
    """Refresh signals_log from MT5 on every restart so APP/Dashboard get current rules."""
    if not mt5_ready:
        print("  [REBUILD] MT5 not ready, skip")
        return 0

    broker_dt = get_broker_time()
    today = broker_dt.date()
    now_h = broker_dt.hour
    now_m = broker_dt.minute
    rebuilt = 0

    passed_today = [
        h for h in TARGET_HOURS
        if h < now_h or (h == now_h and now_m > 45)
    ]
    if passed_today:
        print(f"  [REBUILD] Today {today.isoformat()} slots: {[fmt_hour(h) for h in passed_today]}")
        for h in passed_today:
            try:
                if rebuild_slot_signal(broker_dt, h, is_missed=True):
                    rebuilt += 1
                    print(f"  [REBUILD] {today.isoformat()} H={fmt_hour(h)}:45 refreshed")
            except Exception as e:
                print(f"  [REBUILD] Error today H={h}: {e}")

    past_dates = []
    for i in range(1, 8):
        d = today - timedelta(days=i)
        if d.weekday() < 5:
            past_dates.append(d)

    if past_dates:
        print(f"  [REBUILD] Past weekdays: {[d.isoformat() for d in past_dates]}")
        for target_date in past_dates:
            fake_broker_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=12)
            for h in TARGET_HOURS:
                try:
                    if rebuild_slot_signal(fake_broker_dt, h, is_missed=True):
                        rebuilt += 1
                except Exception as e:
                    print(f"  [REBUILD] Error {target_date.isoformat()} H={h}: {e}")

    print(f"  [REBUILD] Done: {rebuilt} slots refreshed (logic v{SIGNAL_LOGIC_VERSION})")
    return rebuilt


def backfill_missing_days():
    """Backward-compatible alias; rebuild now covers startup refresh."""
    return rebuild_signals_on_startup()

# =====================================================================
# MAIN LOOP
# =====================================================================
mt5_ready = False

def try_init_mt5():
    global mt5_ready
    if mt5_ready:
        return True
    ok = mt5.initialize(path=MT5_PATH) if MT5_PATH else mt5.initialize()
    if ok:
        mt5_ready = True
        info = mt5.account_info()
        if info:
            print(f"  [OK] MT5: {info.server} | {info.login}")
        return True
    return False

def get_broker_time():
    """Lay broker time hoan toan tu tick.time (UTC). Khong phu thuoc local."""
    if mt5_ready:
        tick = mt5.symbol_info_tick(SYMBOL)
        if tick is not None:
            utc_dt = datetime.fromtimestamp(tick.time, tz=timezone.utc).replace(tzinfo=None)
            return utc_dt + timedelta(hours=BROKER_GMT)
    now_utc = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    return now_utc + timedelta(hours=BROKER_GMT)

def resolve_active_profile(profile_name, profiles_path=None):
    """Resolve which profile the signal bot should run as.

    Always loads profiles.json and runs the one-time plaintext-token
    migration, regardless of whether a CLI profile was supplied, so
    migration is never skipped when --profile is passed.

    Resolution order: CLI arg (if it exists in profiles.json) > first
    profile in profiles.json > "" (no profiles configured).
    If profile_name is given but not found in profiles.json, warns and
    falls back to the first available profile.
    """
    if profiles_path is None:
        profiles_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles.json")

    profiles_data = {}
    try:
        with open(profiles_path, "r", encoding="utf-8") as pf:
            profiles_data = json.load(pf)
        if profiles_data:
            # One-time migration of plaintext tokens to keyring
            migrate_plaintext_tokens(profiles_data)
    except Exception:
        profiles_data = {}

    if profile_name:
        if profiles_data and profile_name not in profiles_data:
            print(
                f"[WARN] Profile '{profile_name}' not found in profiles.json. "
                f"Falling back to first available profile."
            )
            return list(profiles_data.keys())[0] if profiles_data else ""
        return profile_name

    if profiles_data:
        return list(profiles_data.keys())[0]

    return ""


def main(profile_name=None):
    global mt5_ready, d_direction, d_direction_date, d_matched_hour, day_signals, sent_today, _active_profile
    print("=" * 55)
    print("  MT5 Multi-Timeframe Signal Bot v3.12.0")
    print(f"  Symbol: {SYMBOL}")
    print(f"  Target Hours: {TARGET_HOURS}")
    print(f"  Broker GMT+{BROKER_GMT} (tu tick.time)")
    print("=" * 55)

    if try_init_mt5():
        info = mt5.account_info()
        if info:
            print(f"  Balance: ${info.balance:,.2f}")
    else:
        print("[WARN] MT5 init failed - dung UTC time")

    print("=" * 55)
    print("  Dang chay... Ctrl+C de dung")
    print("=" * 55)

    # Restore state from previous run (same day only)
    saved = _load_state()
    sent_today = saved.get("sent_today", set())
    day_signals = saved.get("day_signals", {})
    if saved.get("d_direction"):
        d_direction = saved["d_direction"]
        d_direction_date = datetime.fromisoformat(saved["d_direction_date"]).date() if saved.get("d_direction_date") else None
        d_matched_hour = saved.get("d_matched_hour")
        if d_matched_hour is not None:
            print(f"  [RESTORE] D1 matched at H={d_matched_hour}, XAUUSD hidden for remaining slots")

    # Clear old signals for today (tránh hiển thị data sai rule)
    # _clear_today_signals removed: dedup in log_signal handles (date, hour) collisions
    if day_signals:
        print(f"  [RESTORE] day_signals: {list(day_signals.keys())}")
    if sent_today:
        print(f"  [RESTORE] sent_today: {sent_today}")

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    broker_dt = now_utc + timedelta(hours=BROKER_GMT)
    reminders = get_schedule_reminders(broker_dt)
    reminder_text = "\n".join([f"⚠️ {r}" for r in reminders]) if reminders else ""
    send_telegram(
        f"BOT KHỞI ĐỘNG\n"
        f"Symbol: {SYMBOL} | MT5: {'OK' if mt5_ready else 'N/A'}\n"
        f"Kích hoạt: {fmt_hour(TARGET_HOURS[0])}-{fmt_hour(TARGET_HOURS[-1])}:45"
        + (f"\n{reminder_text}" if reminder_text else "")
    )
    # Nếu D1 đã match trước đó (bot restart), thông báo lại
    if d_matched_hour is not None:
        effective_d = get_effective_d_direction(broker_dt)
        send_telegram(
            f"⚠️ XAUUSD ĐÃ MATCH D1 ({effective_d or d_direction})\n"
            f"============================\n"
            f"Slot H={fmt_hour(d_matched_hour)}:45 đã khớp D direction.\n"
            f"Các slot kế XAUUSD bị ẩn đến H=11.\n"
            f"Hiển thị lại từ H=12."
        )
    check_d_direction_input()
    watcher = threading.Thread(target=d_direction_watcher, daemon=True)
    watcher.start()
    event_server = threading.Thread(target=d_direction_event_server, daemon=True)
    event_server.start()

    # Rebuild signals_log from MT5 before pushing (avoid stale pair_dirs after rule changes)
    startup_rebuilt = rebuild_signals_on_startup()

    if mt5_ready:
        broker_dt = get_broker_time()
        clear_expired_d_direction(broker_dt)
        now_h = broker_dt.hour
        now_m = broker_dt.minute

        passed = [h for h in TARGET_HOURS if h < now_h or (h == now_h and now_m > 45)]
        passed.sort(reverse=True)

        next_slots = [h for h in TARGET_HOURS if h > now_h or (h == now_h and now_m <= 45)]
        next_slots.sort()
        if next_slots:
            next_h = next_slots[0]
            if next_h == now_h:
                mins_left = 45 - now_m
            else:
                mins_left = (next_h - now_h) * 60 + (45 - now_m)
            if mins_left <= 0:
                mins_left += 24 * 60
            hours_left = mins_left // 60
            mins_remain = mins_left % 60
            countdown = f"{hours_left}h{mins_remain:02d}m" if hours_left > 0 else f"{mins_remain}m"
        else:
            countdown = "ngay mai"

        # Check D direction input TRƯỚC missed slots để d_direction đúng khi push
        check_d_direction_input()

        missed_count = 0
        latest_missed = None
        # Xử lý H=1 trước để có h1_sig cho các slot khác
        if 1 in passed:
            key_h1 = (broker_dt.date(), 1)
            if key_h1 not in sent_today:
                r1 = analyze(broker_dt, 1)
                s1 = r1["signal"]
                if s1 in ("BUY", "SELL"):
                    day_signals[(broker_dt.date(), 1)] = {"signal": s1, "m30_dir": r1.get("m30_dir")}
                    _save_state(day_signals, sent_today)
        for h in passed:
            key = (broker_dt.date(), h)
            if key in sent_today:
                continue

            wd = broker_dt.weekday()
            if wd >= 5:
                sent_today.add(key)
                _save_state(day_signals, sent_today)
                continue

            print(f"\n[KIEM TRA BO LO] {fmt_hour(h)}:45")
            result = analyze(broker_dt, h)
            sig = result["signal"]
            icon, emoji = get_signal_icon(sig)

            h1_data = day_signals.get((broker_dt.date(), 1))
            h1_sig = h1_data["signal"] if h1_data else None

            pair_dirs = get_pair_direction(h, sig, broker_dt, h1_signal=result.get("h1_signal"))
            if not pair_dirs:
                sent_today.add(key)
                _save_state(day_signals, sent_today)
                print(f"  [SKIP] H={h} - bỏ trống theo rule")
                continue
            # XAUUSD H1 check
            apply_xauusd_m30_logic(pair_dirs, sig, broker_dt, h)
            skip_xau = should_skip_xauusd(h, sig, broker_dt)
            if skip_xau:
                pair_dirs.pop("XAUUSD", None)
            base_note = get_hour_note(h, broker_dt.weekday())
            effective_d = get_effective_d_direction(broker_dt)
            matched_d1 = (sig == effective_d and effective_d is not None)
            if matched_d1:
                mark_xauusd_matched(h)
            if skip_xau or matched_d1:
                hour_note = d1_match_note(effective_d)
            else:
                hour_note = base_note

            log_signal(h, broker_dt, sig, None, pair_dirs, hour_note, is_missed=True)
            sent_today.add(key)
            _save_state(day_signals, sent_today)
            missed_count += 1

            # Chi lay slot gan nhat (dau tien vi passed sort reverse)
            if latest_missed is None:
                latest_missed = {"h": h, "sig": sig, "icon": icon, "result": result,
                                 "pair_dirs": pair_dirs, "hour_note": hour_note,
                                 "h1_sig": h1_sig}

        # Chi gui Telegram slot gan nhat
        if latest_missed:
            h = latest_missed["h"]
            sig = latest_missed["sig"]
            icon = latest_missed["icon"]
            result = latest_missed["result"]
            pair_dirs = latest_missed["pair_dirs"]
            hour_note = latest_missed["hour_note"]
            h1_sig = latest_missed["h1_sig"]

            slot_line = f"Slot tiếp theo: {fmt_hour(next_slots[0])}:45 (còn {countdown})\n" if next_slots else f"Hết slot hôm nay.\n"
            pair_lines = []
            for p in ALL_PAIRS:
                d = pair_dirs.get(p)
                if d is None:
                    pair_lines.append(f"  {p}: -")
                elif d == "--":
                    pair_lines.append(f"  {p}: --")
                else:
                    p_icon, _ = get_signal_icon(d)
                    p_text = "BUY" if d == "BUY" else "SELL"
                    pair_lines.append(f"  {p}: {p_icon} {p_text}")
            pair_text = "\n".join(pair_lines)
            note_line = f"📝 {hour_note}\n" if hour_note else ""

            conclusion = f"KẾT LUẬN: {icon} {sig}\n"

            msg = (
                f"*KIỂM TRA BỎ LỠ {fmt_hour(h)}:45*\n"
                f"============================\n\n"
                f"{result['report']}\n\n"
                f"============================\n"
                f"{conclusion}"
                        f"-------------------\n"
                f"{pair_text}\n"
                f"-------------------\n"
                f"{note_line}"
                f"============================\n"
                f"{slot_line}"
                f"Bỏ lỡ do bot khởi động sau. Chỉ tham khảo!"
            )
            # Không gửi thông báo Telegram cho slot bỏ lỡ nữa
            print(f"[SKIP TELEGRAM] Missed slot notification suppressed for H={h}")

        if missed_count > 0:
            print(f"\n[STARTUP] Logged {missed_count} missed slots")

    push_to_dashboard()
    if startup_rebuilt > 0:
        print(f"\n[DASHBOARD] Pushed after rebuild ({startup_rebuilt} slots refreshed)")

    try:
        _active_profile = resolve_active_profile(profile_name)
        
        # Heartbeat thread - runs independently every 2s
        def heartbeat_thread():
            while True:
                try:
                    publish_heartbeat(_active_profile, mt5_ready)
                except Exception:
                    pass
                time.sleep(2)
        
        threading.Thread(target=heartbeat_thread, daemon=True).start()

        while True:
            if not mt5_ready:
                try_init_mt5()

            broker_dt = get_broker_time()
            clear_expired_d_direction(broker_dt)
            now_min = broker_dt.minute
            now_hour = broker_dt.hour

            check_d_direction_input()

            if broker_dt.hour == 0 and broker_dt.minute == 0 and broker_dt.weekday() in (3, 4):
                send_d_direction_reminder()

            if now_min == 45 and now_hour in TARGET_HOURS:
                key = (broker_dt.date(), now_hour)
                if key in sent_today:
                    time.sleep(10)
                    continue

                print(f"\n[{fmt_time(broker_dt)}] Kích hoạt {fmt_hour(now_hour)}:45")

                # Tat ca 5 nhom hoat dong T2-6, chi skip T7/CN
                wd = broker_dt.weekday()
                if wd >= 5:
                    print(f"  [SKIP] T{wd+1} - weekend")
                    sent_today.add(key)
                    _save_state(day_signals, sent_today)
                    time.sleep(60)
                    continue

                result = analyze(broker_dt, now_hour)
                sig = result["signal"]

                # Track H=1 signal for downstream day logic
                if now_hour == 1 and sig in ("BUY", "SELL"):
                    day_signals[(broker_dt.date(), 1)] = {"signal": sig, "m30_dir": result.get("m30_dir")}
                    _save_state(day_signals, sent_today)

                h1_data = day_signals.get((broker_dt.date(), 1))
                h1_sig = h1_data["signal"] if h1_data else None

                # Tính pair_dirs trước khi gửi
                pair_dirs = get_pair_direction(now_hour, sig, broker_dt, h1_signal=result.get("h1_signal"))
                if not pair_dirs:
                    # Slot bỏ trống theo rule ngày - đánh dấu đã xử lý
                    sent_today.add(key)
                    _save_state(day_signals, sent_today)
                    print(f"  [SKIP] H={now_hour} - không có pair active theo rule ngày")
                    time.sleep(10)
                    continue

                pair_dirs = send_report(result, now_hour, broker_dt, h1_signal=h1_sig)

                # Log for website
                # Nếu pair_dirs rỗng → XAUUSD bị ẩn do match D1, vẫn log với note
                effective_d = get_effective_d_direction(broker_dt)
                if not pair_dirs:
                    pair_dirs = {"XAUUSD": sig}
                    hour_note = d1_match_note(effective_d)
                else:
                    if should_skip_xauusd(now_hour, sig, broker_dt) or (sig == effective_d and effective_d is not None):
                        hour_note = d1_match_note(effective_d)
                    else:
                        hour_note = get_hour_note(now_hour, broker_dt.weekday())
                log_signal(now_hour, broker_dt, sig, None, pair_dirs, hour_note)
                push_to_dashboard()


                print(f"  Signal: {sig}")
                print(f"  Sent: OK")

                sent_today.add(key)
                _save_state(day_signals, sent_today)

                time.sleep(60)
            else:
                # Push giá realtime mỗi lần loop
                push_prices_to_dashboard()
                if now_min < 45:
                    wait = (45 - now_min) * 60 - broker_dt.second
                else:
                    wait = (60 - now_min + 45) * 60 - broker_dt.second
                wait = min(wait, 300)
                if wait > 0:
                    time.sleep(wait)

    except KeyboardInterrupt:
        print("\n  Dừng bot.")
    except Exception as e:
        print(f"\n  Loi: {e}")
    finally:
        if mt5_ready:
            mt5.shutdown()
        print("  Bot stopped.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=str, help="Profile name for heartbeat")
    args, _ = parser.parse_known_args()
    main(profile_name=args.profile)
