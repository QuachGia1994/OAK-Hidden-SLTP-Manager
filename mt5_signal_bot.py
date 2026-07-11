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
# Default full band; use get_target_hours(broker_dt) for weekday-aware slots.
# Mon–Fri: H=3..13,15 (no H=14); T5/T6 same band as T2–T4.
# No-trade gold LABEL (logic still computes XAU for GBP Focus):
#   - T5: H=3-4 (trade gold H=5-15)
#   - T6: H=3-11 (trade gold H=12-15 only; H=14 removed)
# Focus GBP: Monday H=9 GBPUSD+GBPCAD; other days use their own slot rules.
# pair_dirs GBP map only T3-T4 H=3-4 (GA/GJ đều ngược Vàng); H=5+ XAU only + Focus list.
TARGET_HOURS = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15]  # no H=14
# Bump when pair-direction / slot rules change to trace rebuilds in logs.
SIGNAL_LOGIC_VERSION = 11


def get_rhythm_label(hour):
    """Return the five-rhythm label for an active H slot."""
    try:
        h = int(hour)
    except (TypeError, ValueError):
        return None
    if h in (3, 4):
        return "Nhịp 1"
    if 5 <= h <= 8:
        return "Nhịp 2"
    if 9 <= h <= 11:
        return "Nhịp 3"
    if h in (12, 13):
        return "Nhịp 4"
    if h == 15:
        return "Nhịp 5"
    return None


def get_target_hours(broker_dt=None, weekday=None):
    """Return active H slots for the broker weekday.

    Python weekday: Mon=0 .. Sun=6.
    Mon–Fri → H=3..13,15 (H=14 removed); weekend → [].
    """
    if weekday is None:
        if broker_dt is None:
            weekday = datetime.now().weekday()
        else:
            weekday = broker_dt.weekday()
    if weekday >= 5:
        return []
    return list(TARGET_HOURS)
BROKER_GMT = 0

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


# Hysteresis for getMe: single timeout must not flip Online → Degraded
_tg_fail_streak = 0
_tg_last_ok_name = ""
_tg_last_ok_mono = 0.0


def publish_heartbeat(profile, mt5_connected, mt5_error="", profiles_path=None):
    """Publish heartbeat to SQLite. Called every ~2s from main loop."""
    from datetime import datetime, timezone
    global _tg_fail_streak, _tg_last_ok_name, _tg_last_ok_mono
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
    if tg_token:
        tg_api_ok, tg_bot = _check_telegram_api(tg_token)
        if tg_api_ok:
            _tg_fail_streak = 0
            _tg_last_ok_name = str(tg_bot or _tg_last_ok_name or "")
            _tg_last_ok_mono = time.time()
            tg_bot = _tg_last_ok_name
        else:
            _tg_fail_streak += 1
            # Hold last-known-good 90s or until 2 consecutive failures
            hold = _tg_last_ok_mono and (time.time() - _tg_last_ok_mono) < 90.0
            if _tg_fail_streak < 2 or hold:
                if _tg_last_ok_name:
                    tg_api_ok = True
                    tg_bot = _tg_last_ok_name
            # else keep tg_api_ok False / error category in tg_bot
    else:
        tg_api_ok, tg_bot = False, ""
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

def log_signal(H, broker_dt, sig, entry_time, pair_dirs, hour_note):
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
    """Parse news strings like '• 19:30 CAD 🔴 [HIGH] GDP m/m' into structured objects."""
    import re
    from oak_trading_reminders import is_critical_news_title
    items = []
    for line in news_lines:
        raw = line
        line = line.lstrip("•- ").strip()
        line = re.sub(r"^⚠️\s*", "", line)
        # Match: HH:MM CURRENCY [emoji/tags] TITLE
        m = re.match(r"(\d{1,2}:\d{2})\s+(\w+)\s+(.+)", line)
        if m:
            time_str, currency, rest = m.group(1), m.group(2), m.group(3)
            impact = "medium"
            title = rest
            if "\U0001f534" in rest or "🔴" in rest or "[HIGH]" in rest.upper():
                impact = "high"
            if "\U0001f7e0" in rest or "🟠" in rest:
                impact = "medium"
            if "\U0001f7e2" in rest or "🟢" in rest:
                impact = "low"
            title = rest
            for tok in ("\U0001f534", "🔴", "\U0001f7e0", "🟠", "\U0001f7e2", "🟢",
                        "[HIGH]", "[high]", "[NỔI BẬT]", "[NOI BAT]", "⚠️"):
                title = title.replace(tok, "")
            title = re.sub(r"\s+", " ", title).strip()
            critical = (
                is_critical_news_title(title)
                or "NỔI BẬT" in raw
                or "NOI BAT" in raw.upper()
            )
            if critical:
                impact = "high"
            items.append({
                "time": time_str,
                "currency": currency,
                "title": title,
                "impact": impact,
                "critical": critical,
            })
    items.sort(key=lambda x: (0 if x.get("critical") else 1, x.get("time") or "99:99"))
    return items

def select_signals_for_dashboard(all_signals):
    """Keep every signal that still has pair data so history can be republished across days."""
    return [s for s in all_signals if s.get("pair_dirs")]

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
                print(f"[DASHBOARD] Pushing state: date={state.get('date')}")
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
    - T3-T4 H=3-4: rebuild GBP theo final XAU sau flip (GA/GJ đều ngược).
    - H=5+: chỉ XAUUSD (Focus GBP không gán chiều pair_dirs).
    """
    xau_m30 = get_xauusd_m30_signal(broker_dt, H)
    if xau_m30 is None or "XAUUSD" not in pair_dirs:
        return pair_dirs
    if sig == xau_m30:
        final_xau = "SELL" if xau_m30 == "BUY" else "BUY"
    else:
        final_xau = xau_m30

    # T3-T4 H=3-4: both GBP pairs are opposite final XAUUSD.
    if H in (3, 4) and broker_dt.weekday() in (1, 2):
        rebuilt = get_pair_direction(H, final_xau, broker_dt)
        if not rebuilt:
            pair_dirs["XAUUSD"] = final_xau
            return pair_dirs
        pair_dirs.clear()
        pair_dirs.update(rebuilt)
        return pair_dirs

    # H=5+: Focus-only GBP — flip/update XAU only
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

def _resolve_weekday(broker_dt=None, weekday=None):
    if weekday is not None:
        return weekday
    if broker_dt is not None:
        return broker_dt.weekday()
    return None


def is_xau_no_trade_label_slot(H, broker_dt=None, weekday=None):
    """Slots where XAU is labeled KHÔNG ĐÁNH (logic still computed for GBP Focus).

    - Thứ 5 (Thu): H=3-4 → trade gold H=5-15
    - Thứ 6 (Fri): H=3-11 → trade gold H=12-15 only
    - Thứ 2 (Mon): H=5-11
    - T3–T4: never (gold normal H=3-13,15)
    """
    wd = _resolve_weekday(broker_dt, weekday)
    if wd is None:
        return False
    try:
        h = int(H)
    except (TypeError, ValueError):
        return False
    if wd == 3 and h in (3, 4):  # T5 early
        return True
    if wd == 0 and 5 <= h <= 11:  # T2 no-gold band
        return True
    if wd == 4 and 3 <= h <= 11:  # T6 H=3-11 no-gold; H=12-15 gold OK
        return True
    return False


# Back-compat alias
def is_thursday_no_gold_slot(H, broker_dt=None, weekday=None):
    return is_xau_no_trade_label_slot(H, broker_dt=broker_dt, weekday=weekday)


def xau_no_trade_label_tag(H, broker_dt=None, weekday=None):
    """Short badge tag: 'H=3-4' | 'T6 H=3-11' | ''."""
    wd = _resolve_weekday(broker_dt, weekday)
    try:
        h = int(H)
    except (TypeError, ValueError):
        return ""
    if wd == 3 and h in (3, 4):
        return "H=3-4"
    if wd == 0 and 5 <= h <= 11:
        return "T2 H=5-11"
    if wd == 4 and 3 <= h <= 11:
        return "T6 H=3-11"
    return ""


def thursday_no_gold_label(lang="VN"):
    """Legacy long label. Prefer xau_no_trade_label_tag for badges."""
    if lang == "EN":
        return "⚠ NO Gold entry (logic still computed for GBP Focus)"
    return "⚠ KHÔNG đánh Vàng (logic vẫn tính cho Focus GBP)"


def get_hour_note(H, weekday=None):
    """Trả note theo H; T5 H=3-4 và T6 chỉ hiển thị XAUUSD.

    Không gắn prose no-gold vào đây — nhãn Vàng tách riêng (Telegram/App badge).
    T3-T4 H=3 và H=4: GBPAUD và GBPJPY đều ngược Vàng.
    H=15: chỉ Focus nhóm GBP (không gán chiều pair_dirs). H=14 removed.
    """
    try:
        h = int(H)
    except (TypeError, ValueError):
        return "Chỉ Vàng (XAUUSD)"
    if weekday == 4:
        return "Chỉ Vàng (XAUUSD)"
    if weekday == 3:
        if h in (3, 4):
            return "Chỉ Vàng (XAUUSD)"
        if 5 <= h <= 8:
            return "Chỉ Focus GBPAUD"
    if weekday == 0 and h == 9:
        return "Chỉ Focus GBPUSD · GBPCAD"
    if h == 14:
        return "Slot H=14 đã tắt (không tính)"
    if weekday in (1, 2) and h in (3, 4):
        return "GBPAUD · GBPJPY ngược Vàng (GBPUSD/GBPCAD --)"
    if 5 <= h <= 8:
        return "Chỉ Focus GBPAUD"
    if h in (9, 11, 12, 15):
        return "Chỉ Focus nhóm GBP (không gán chiều Mua/Bán)"
    return "Chỉ Vàng (XAUUSD)"


def get_focus_gbp_pairs(H, broker_dt=None, weekday=None):
    """Cặp GBP tập trung theo slot — hiển thị Focus, không Mua/Bán trên Telegram/UI.

    - T2 H=9: GBPUSD + GBPCAD
    - T2 các H khác: không Focus GBP
    - T3-T4 H=3-4: GBPAUD + GBPJPY
    - T3-T5 H=5-8: chỉ GBPAUD
    - T5 H=3-4: không Focus
    - H=9,11,12,15 T2–T5: đủ nhóm GBP
    - T6: không Focus GBP
    - H=14: disabled (no focus)
    """
    try:
        h = int(H)
    except (TypeError, ValueError):
        return []
    if h == 14:
        return []
    resolved_weekday = _resolve_weekday(broker_dt, weekday)
    if resolved_weekday == 4:
        return []
    if resolved_weekday == 0:
        return ["GBPUSD", "GBPCAD"] if h == 9 else []
    if resolved_weekday == 3:
        if h in (3, 4):
            return []
        if 5 <= h <= 8:
            return ["GBPAUD"]
    if h in (3, 4):
        return ["GBPAUD", "GBPJPY"] if resolved_weekday in (1, 2) else []
    if 5 <= h <= 8:
        return ["GBPAUD"]
    if h in (9, 11, 12, 15):
        return ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"]
    return []


def _focus_gbp_relation_note(pair, H):
    """Mô tả quan hệ Focus vs Vàng — chỉ H=3 và H=4."""
    try:
        h = int(H)
    except (TypeError, ValueError):
        return "Focus"
    if h in (3, 4):
        if pair == "GBPAUD":
            return "Focus · ngược Vàng"
        if pair == "GBPJPY":
            return "Focus · ngược Vàng"
    return "Focus"


def format_telegram_pair_block(pair_dirs, H, broker_dt=None, weekday=None):
    """Block cặp cho Telegram: XAU Mua/Bán hoặc KHÔNG ĐÁNH; GBP Focus (+ quan hệ chỉ H=3–4)."""
    lines = []
    no_trade = is_xau_no_trade_label_slot(H, broker_dt=broker_dt, weekday=weekday)
    tag = xau_no_trade_label_tag(H, broker_dt=broker_dt, weekday=weekday) or "no-trade"
    xau = (pair_dirs or {}).get("XAUUSD")
    if xau in ("BUY", "SELL"):
        p_icon, _ = get_signal_icon(xau)
        if no_trade:
            lines.append(f"  XAUUSD: {p_icon} {xau}  ·  ⚠ KHÔNG ĐÁNH ({tag})")
        else:
            lines.append(f"  XAUUSD: {p_icon} {xau}")
    elif xau is None and not no_trade:
        pass
    elif no_trade:
        lines.append(f"  XAUUSD: ⚠ KHÔNG ĐÁNH ({tag})")

    focus = get_focus_gbp_pairs(H, broker_dt=broker_dt, weekday=weekday)
    if focus:
        lines.append("  Cặp GBP tập trung:")
        for p in focus:
            lines.append(f"  {p}: {_focus_gbp_relation_note(p, H)}")
    elif not lines:
        lines.append("  (không có cặp)")
    return "\n".join(lines)


GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"]
ALL_PAIRS = GBP_PAIRS + ["XAUUSD"]

day_signals = {}
sent_today = set()

def get_pair_direction(H, signal, broker_dt, h1_signal=None):
    """Tính chiều các cặp theo slot. Signal = hướng pattern (XAUUSD baseline).

    - T3-T4 H=3-4: GBPJPY và GBPAUD đều ngược Vàng; GBPUSD/GBPCAD --
    - H=5+: chỉ XAUUSD (GBP = Focus list, không gán Mua/Bán)
    """
    result = {}
    if signal not in ("BUY", "SELL"):
        return result

    gold = signal
    opposite = "SELL" if gold == "BUY" else "BUY"
    result["XAUUSD"] = gold

    if H in (3, 4) and broker_dt.weekday() in (1, 2):
        result["GBPJPY"] = opposite
        result["GBPAUD"] = opposite
        result["GBPUSD"] = "--"
        result["GBPCAD"] = "--"
    # else: XAU only — Focus GBP via get_focus_gbp_pairs

    return result

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

    # XAUUSD M30: cùng chiều M30 -> đảo, ngược -> giữ M30
    apply_xauusd_m30_logic(pair_dirs, sig, broker_dt, H)

    # No-trade gold label slots: keep XAU in pair_dirs; no quick-order Vàng
    no_gold_entry = is_xau_no_trade_label_slot(H, broker_dt)

    # Hiển thị: XAU Mua/Bán (hoặc KHÔNG ĐÁNH); GBP chỉ Focus — không in BUY/SELL GBP
    pair_text = format_telegram_pair_block(pair_dirs, H, broker_dt)

    # KẾT LUẬN = pattern Signal (baseline; XAU có thể lệch sau M30)
    conclusion = f"KẾT LUẬN (pattern): {icon} {sig}\n"

    msg = (
        f"{emoji} Tín hiệu pattern {SYMBOL} - {icon} {sig}\n"
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

    # Quick-order: chỉ XAUUSD (GBP là Focus; skip no-trade gold slots)
    active_pairs = []
    xau_d = pair_dirs.get("XAUUSD")
    if xau_d in ("BUY", "SELL") and not no_gold_entry:
        active_pairs = [("XAUUSD", xau_d)]
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
                                        "⚡ Chọn lệnh nhanh Vàng (chỉ cần nhập Lot):",
                                        keyboard, parse_mode=None)
        except Exception as e:
            print(f"[WARN] Inline keyboard error: {e}")

    return pair_dirs

# =====================================================================
# REBUILD: tính lại signals_log từ MT5 khi bot khởi động (tránh push data cũ)
# =====================================================================
def rebuild_slot_signal(broker_dt, h):
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

    hour_note = get_hour_note(h, broker_dt.weekday())
    log_signal(h, broker_dt, sig, None, pair_dirs, hour_note)
    return True


def rebuild_recent_history(days=7):
    """Recalculate and replace the latest weekday history using current rules."""
    if not mt5_ready:
        print("  [REBUILD] MT5 not ready, skip")
        return 0

    broker_dt = get_broker_time()
    today = broker_dt.date()
    dates = [today - timedelta(days=i) for i in range(days)]
    passed_today = {
        hour for hour in get_target_hours(broker_dt)
        if hour < broker_dt.hour or (hour == broker_dt.hour and broker_dt.minute > 45)
    }
    try:
        data = []
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as file:
                data = json.load(file)
        # Replace each recent weekday completely. Filtering only active slots left
        # obsolete H=2/H=14 records in the log and therefore in Redis history.
        rebuild_dates = {target_date.isoformat() for target_date in dates if target_date.weekday() < 5}
        filtered = [record for record in data if record.get("date") not in rebuild_dates]
        with open(_SIGNALS_LOG, "w", encoding="utf-8") as file:
            json.dump(filtered, file, ensure_ascii=False)
    except Exception as error:
        print(f"  [REBUILD] Cannot clear stale history: {error}")

    rebuilt = 0
    for target_date in dates:
        if target_date.weekday() >= 5:
            continue
        fake_broker_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=12)
        hours = passed_today if target_date == today else get_target_hours(fake_broker_dt)
        for hour in hours:
            try:
                if rebuild_slot_signal(fake_broker_dt, hour):
                    rebuilt += 1
            except Exception as error:
                print(f"  [REBUILD] Error {target_date.isoformat()} H={hour}: {error}")

    print(f"  [REBUILD] Done: {rebuilt} slots refreshed across {days} days (logic v{SIGNAL_LOGIC_VERSION})")
    return rebuilt


def rebuild_signals_on_startup():
    """Backward-compatible startup hook; refreshes the full recent history."""
    return rebuild_recent_history(days=7)


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
    global mt5_ready, day_signals, sent_today, _active_profile
    print("=" * 55)
    print("  MT5 Multi-Timeframe Signal Bot v3.12.0")
    print(f"  Symbol: {SYMBOL}")
    print(f"  Target Hours T2-6: H=3-13,15 (no H=14) | no-gold: T5 H=3-4 | T6 H=3-11 (gold T6 H=12,15; no GBP Focus)")
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

    if day_signals:
        print(f"  [RESTORE] day_signals: {list(day_signals.keys())}")
    if sent_today:
        print(f"  [RESTORE] sent_today: {sent_today}")

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    broker_dt = now_utc + timedelta(hours=BROKER_GMT)
    hours_boot = get_target_hours(broker_dt)
    h0, h1 = (hours_boot[0], hours_boot[-1]) if hours_boot else (3, 15)
    reminders = get_schedule_reminders(broker_dt)
    reminder_text = "\n".join([f"⚠️ {r}" for r in reminders]) if reminders else ""
    send_telegram(
        f"BOT KHỞI ĐỘNG\n"
        f"Symbol: {SYMBOL} | MT5: {'OK' if mt5_ready else 'N/A'}\n"
        f"Kích hoạt hôm nay: {fmt_hour(h0)}-{fmt_hour(h1)}:45 "
        f"(T2-T6=H3-13,15 no H=14 | T5 H=3-4 no Gold | T6 H=3-11 no Gold; gold T6 H=12,15; no GBP Focus)"
        + (f"\n{reminder_text}" if reminder_text else "")
    )

    # Rebuild signals_log from MT5 before pushing (avoid stale pair_dirs after rule changes)
    startup_rebuilt = rebuild_signals_on_startup()

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
            now_min = broker_dt.minute
            now_hour = broker_dt.hour

            hours_now = get_target_hours(broker_dt)
            if now_min == 45 and now_hour in hours_now:
                key = (broker_dt.date(), now_hour)
                if key in sent_today:
                    time.sleep(10)
                    continue

                print(f"\n[{fmt_time(broker_dt)}] Kích hoạt {fmt_hour(now_hour)}:45")

                # T2-6 active (weekday hours via get_target_hours); skip T7/CN
                wd = broker_dt.weekday()
                if wd >= 5:
                    print(f"  [SKIP] T{wd+1} - weekend")
                    sent_today.add(key)
                    _save_state(day_signals, sent_today)
                    time.sleep(60)
                    continue

                # Rebuild seven-day history before every live calculation so backtests
                # always use the current pair and note rules.
                rebuild_recent_history(days=7)
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
                if not pair_dirs:
                    pair_dirs = {"XAUUSD": sig}
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
