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
# Mon–Fri active rhythm slots. H=6/H=10/H=11/H=17 are intentionally inactive.
# XAU-only mode: no GBP focus pairs and no no-gold labels.
DISABLED_HOURS = {6, 10, 17}
TARGET_HOURS = [2, 3, 4, 5, 7, 8, 9, 11, 12, 13, 14, 15]
# Bump when pair-direction / slot rules change to trace rebuilds in logs.
SIGNAL_LOGIC_VERSION = 22
D_DIRECTION_PAIR = "Stock-DIRECTION"
GBP_DIRECTION_PAIR = "GBP-DIRECTION"


def get_rhythm_label(hour):
    """Return the five-rhythm label for an active H slot."""
    try:
        h = int(hour)
    except (TypeError, ValueError):
        return None
    if h in DISABLED_HOURS:
        return None
    if h == 2:
        return "Nhịp 0 · XAU"
    if h in (3, 4):
        return "Nhịp 1 · JPY"
    if h in (5, 7, 8):
        return "Nhịp 2 · AUD"
    if h == 9:
        return "Nhịp 3 · GBP"
    if h in (11, 12, 13):
        return "Nhịp 4 · EUR"
    if h in (14, 15):
        return "Nhịp 5 · USD"
    return None


def get_target_hours(broker_dt=None, weekday=None):
    """Return active H slots for the broker weekday.

    Python weekday: Mon=0 .. Sun=6.
    Mon–Fri → active H=2,3,4,5,7,8,9,12,13,15; weekend → [].
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
    ok, result = telegram_get_me(token, retries=1, timeout=8.0)
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
_tg_last_probe_mono = 0.0
_tg_next_probe_mono = 0.0
_tg_cached_api_ok = False
_tg_cached_bot = ""
_tg_probe_key = None
_tg_last_check_iso = ""
_TG_PROBE_BASE_SECONDS = 45.0
_TG_PROBE_MAX_SECONDS = 300.0


def _reset_telegram_probe_state(probe_key=None):
    """Reset cached Telegram health when the active profile or token changes."""
    global _tg_fail_streak, _tg_last_ok_name, _tg_last_ok_mono
    global _tg_last_probe_mono, _tg_next_probe_mono
    global _tg_cached_api_ok, _tg_cached_bot, _tg_probe_key, _tg_last_check_iso
    _tg_fail_streak = 0
    _tg_last_ok_name = ""
    _tg_last_ok_mono = 0.0
    _tg_last_probe_mono = 0.0
    _tg_next_probe_mono = 0.0
    _tg_cached_api_ok = False
    _tg_cached_bot = ""
    _tg_probe_key = probe_key
    _tg_last_check_iso = ""


def _probe_telegram_health(profile, token):
    """Return cached health, probing only when the backoff window expires."""
    global _tg_fail_streak, _tg_last_ok_name, _tg_last_ok_mono
    global _tg_last_probe_mono, _tg_next_probe_mono
    global _tg_cached_api_ok, _tg_cached_bot, _tg_last_check_iso
    probe_key = (profile, token)
    if probe_key != _tg_probe_key:
        _reset_telegram_probe_state(probe_key)
    now = time.monotonic()
    if now >= _tg_next_probe_mono:
        _tg_last_probe_mono = now
        _tg_cached_api_ok, _tg_cached_bot = _check_telegram_api(token)
        if _tg_cached_api_ok:
            _tg_fail_streak = 0
            _tg_last_ok_name = str(_tg_cached_bot or _tg_last_ok_name or "")
            _tg_last_ok_mono = now
            _tg_last_check_iso = datetime.now(timezone.utc).isoformat()
        else:
            _tg_fail_streak += 1
        exponent = min(3, max(0, _tg_fail_streak - 1))
        delay = min(_TG_PROBE_BASE_SECONDS * (2 ** exponent), _TG_PROBE_MAX_SECONDS)
        _tg_next_probe_mono = now + delay
    if _tg_cached_api_ok:
        return True, _tg_last_ok_name or _tg_cached_bot
    hold = _tg_last_ok_mono and (now - _tg_last_ok_mono) < 90.0
    if _tg_last_ok_name and (_tg_fail_streak < 2 or hold):
        return True, _tg_last_ok_name
    return False, _tg_cached_bot or "network_error"


def publish_heartbeat(profile, mt5_connected, mt5_error="", profiles_path=None):
    """Publish heartbeat to SQLite. Called every ~2s from main loop."""
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
        tg_api_ok, tg_bot = _probe_telegram_health(profile, tg_token)
    else:
        if _tg_probe_key is not None:
            _reset_telegram_probe_state()
        tg_api_ok, tg_bot = False, ""

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
        telegram_last_check=_tg_last_check_iso,
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
        "d_direction": ds_json.get("4", {}).get("d_direction"),
        "d_direction_date": today_str if ds_json.get("4", {}).get("d_direction") else None,
    }
    try:
        tmp_file = _STATE_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp_file, _STATE_FILE)
    except Exception as e:
        print(f"[WARN] Cannot save state: {e}")

_SIGNALS_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signals_log.json")


def _write_signals_log_atomic(data):
    """Replace the signal log atomically so readers never see partial JSON."""
    temporary = f"{_SIGNALS_LOG}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False)
        os.replace(temporary, _SIGNALS_LOG)
    finally:
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
        except OSError:
            pass


def _get_d_direction_from_day(date_value):
    """Find the stored H=4 D-direction for a trading date."""
    h4_data = day_signals.get((date_value, 4), {})
    d_direction = h4_data.get("d_direction") if isinstance(h4_data, dict) else None
    if d_direction in ("BUY", "SELL"):
        return d_direction

    date_str = date_value.isoformat() if hasattr(date_value, "isoformat") else str(date_value)
    try:
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as file:
                data = json.load(file)
            for record in reversed(data):
                if record.get("date") != date_str or int(record.get("hour", -1)) != 4:
                    continue
                d_direction = (record.get("pair_dirs") or {}).get(D_DIRECTION_PAIR)
                if d_direction in ("BUY", "SELL"):
                    return d_direction
    except Exception as error:
        print(f"[WARN] Cannot restore D-direction: {error}")
    return None


def get_current_prices(pair_dirs):
    """Lấy giá market hiện tại (tick)."""
    prices = {}
    for pair, direction in pair_dirs.items():
        if pair == D_DIRECTION_PAIR or pair == GBP_DIRECTION_PAIR:
            continue
        if direction not in ("BUY", "SELL"):
            continue
        try:
            tick = mt5.symbol_info_tick(pair)
            if tick:
                prices[pair] = round(tick.bid, 5)
        except Exception as e:
            log.warning("MT5 tick fetch error for %s: %s", pair, e)
    return prices

def log_signal(H, broker_dt, sig, entry_time, pair_dirs, hour_note,
               pattern_signal=None):
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
        "d_direction": (pair_dirs or {}).get(D_DIRECTION_PAIR),
    }
    if pattern_signal:
        record["pattern_signal"] = pattern_signal
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
        _write_signals_log_atomic(data)
    except Exception as e:
        print(f"[WARN] Cannot log signal: {e}")

def _parse_news_for_dashboard(news_lines, source_date=None):
    """Parse news strings like '• 19:30 CAD 🔴 [HIGH] GDP m/m' into structured objects."""
    import re
    from oak_trading_reminders import _get_news_day_str, _get_display_tz_name, is_critical_news_title
    display_date = _get_news_day_str()
    if source_date and source_date != display_date:
        return []
    news_date = source_date or display_date
    timezone_label = _get_display_tz_name()
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
                "date": news_date,
                "time": time_str,
                "local_time": time_str,
                "time_zone": timezone_label,
                "currency": currency,
                "title": title,
                "impact": impact,
                "critical": critical,
            })
    items.sort(key=lambda x: (0 if x.get("critical") else 1, x.get("time") or "99:99"))
    return items


def _latest_today_news_cache():
    """Return the newest VN/EN news cache for today's display date."""
    from oak_trading_reminders import _NEWS_CACHE_VERSION, _get_news_day_str

    display_date = _get_news_day_str()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    for filename in ("news_cache_VN.json", "news_cache_EN.json"):
        path = os.path.join(base_dir, filename)
        if not os.path.exists(path) or os.path.getsize(path) <= 2:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                cache = json.load(f)
            if cache.get("v") != _NEWS_CACHE_VERSION:
                continue
            if cache.get("date") != display_date or not cache.get("news"):
                continue
            candidates.append((os.path.getmtime(path), cache))
        except Exception:
            continue
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def select_signals_for_dashboard(all_signals):
    """Keep every signal that still has pair data so history can be republished across days."""
    return [
        s for s in all_signals
        if s.get("pair_dirs") and int(s.get("hour", -1)) not in DISABLED_HOURS
    ]

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
        # Push today's newest VN/EN news cache.
        cache = _latest_today_news_cache()
        if cache:
            raw_news = cache.get("news", []) if cache else []
            parsed = _parse_news_for_dashboard(raw_news, source_date=cache.get("date"))
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

def build_startup_telegram_message(broker_dt, mt5_connected):
    """Build the startup Telegram note from the same daily matrix as the dashboard."""
    day_notes = get_day_notes(broker_dt, lang="VN")
    disabled_slots = ", ".join(f"H={hour}" for hour in sorted(DISABLED_HOURS))
    rules = "\n".join(f"⚠️ {note}" for note in day_notes)
    mt5_status = "OK" if mt5_connected else "N/A"
    return (
        "🤖 BOT KHỞI ĐỘNG\n"
        f"Nguồn pattern: {SYMBOL} | MT5: {mt5_status}\n"
        f"Slots: {', '.join(f'H={h}' for h in TARGET_HOURS)}\n"
        f"Tắt: {disabled_slots}.\n"
        "🔒 Auto-close: XAUUSD 14:44 (T2) / 17:44, GBP 19:44 (Broker)\n"
        f"Quy tắc hôm nay:\n{rules}"
    )

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
    rates = _copy_rates_near_timestamp(symbol, timeframe, target_ts)
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


def _copy_rates_near_timestamp(symbol, timeframe, target_ts):
    """Load an exact historical window, with the recent-bar fallback."""
    target = datetime.fromtimestamp(target_ts, tz=timezone.utc)
    start = target - timedelta(minutes=3)
    end = target + timedelta(minutes=3)
    try:
        rates = mt5.copy_rates_range(symbol, timeframe, start, end)
    except Exception as error:
        print(f"[WARN] MT5 range lookup failed for {symbol}: {error}")
        rates = None
    if rates is not None and len(rates) > 0:
        return rates
    return mt5.copy_rates_from_pos(symbol, timeframe, 0, 5000)

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


def is_h2_special_calendar_weekday(broker_dt):
    """Check whether Thursday H=2 is in a special-calendar week.

    Friday never uses a special H=2 reversal.
    """
    if broker_dt.weekday() != 3:
        return False
    week_wednesday = broker_dt.date() + timedelta(days=(2 - broker_dt.weekday()))
    week_friday = broker_dt.date() + timedelta(days=(4 - broker_dt.weekday()))
    return week_wednesday.day in (30, 1) or week_friday.day in (3, 4, 7)


def should_reverse_h2_xau(broker_dt):
    """Whether H=2 should reverse the pattern XAU signal.

    - Thursday (T5): reverse only on special-calendar weeks after T2 history.
    - Friday (T6): always use the normal H=2 flow; never reverse by calendar.
    - Other weekdays: never reverse
    """
    if broker_dt is None:
        return False
    if broker_dt.weekday() != 3:
        return False
    return is_h2_special_calendar_weekday(broker_dt)

def _lookup_h2_t2_signal(broker_dt):
    """Look up the previous Monday H=2 signal for Thursday history reuse."""
    monday_date = broker_dt.date() - timedelta(days=3)
    date_str = monday_date.isoformat()
    try:
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            for record in reversed(data):
                if record.get("date") == date_str and int(record.get("hour", -1)) == 2:
                    sig = record.get("signal")
                    if sig in ("BUY", "SELL"):
                        return sig
    except Exception as e:
        print(f"[WARN] Cannot look up Monday H=2 signal: {e}")
    return None


def _lookup_h2_signal_today(broker_dt):
    """Look up today's H=2 signal from signals_log history."""
    date_str = broker_dt.date().isoformat()
    try:
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            for record in reversed(data):
                if record.get("date") == date_str and int(record.get("hour", -1)) == 2:
                    sig = record.get("signal")
                    if sig in ("BUY", "SELL"):
                        return sig
    except Exception as e:
        print(f"[WARN] Cannot lookup today H=2 signal: {e}")
    return None


def _lookup_h5_signal_for_date(broker_dt, target_date):
    """Look up H=5 signal from signals_log for a specific date."""
    date_str = target_date.isoformat() if hasattr(target_date, 'isoformat') else str(target_date)
    try:
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            for record in reversed(data):
                if record.get("date") == date_str and int(record.get("hour", -1)) == 5:
                    sig = record.get("signal")
                    if sig in ("BUY", "SELL"):
                        return sig
    except Exception as e:
        print(f"[WARN] Cannot lookup H=5 for {date_str}: {e}")
    return None


def _lookup_h5_signal_today(broker_dt):
    return _lookup_h5_signal_for_date(broker_dt, broker_dt.date())


def _lookup_h5_signal_yesterday(broker_dt):
    """Look up H=5 from the most recent previous weekday."""
    d = broker_dt.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return _lookup_h5_signal_for_date(broker_dt, d)


def apply_xauusd_m30_logic(pair_dirs, sig, broker_dt, H):
    """Cùng chiều XAUUSD M30 -> đảo XAUUSD, ngược chiều -> theo XAUUSD M30.

    XAU-only mode: update the XAUUSD direction after M30 post-processing.
    """
    xau_m30 = get_xauusd_m30_signal(broker_dt, H)
    if xau_m30 is None or "XAUUSD" not in pair_dirs:
        return pair_dirs
    if sig == xau_m30:
        final_xau = "SELL" if xau_m30 == "BUY" else "BUY"
    else:
        final_xau = xau_m30

    pair_dirs["XAUUSD"] = final_xau
    apply_d_direction_marker(pair_dirs, H, broker_dt)
    return pair_dirs


def _reversed_h2_result(broker_dt, hour):
    """Build H=3/H=7 from the already-final XAUUSD H=2 direction."""
    h2_signal = _lookup_h2_signal_today(broker_dt)
    final_signal = reverse_signal(h2_signal)
    if final_signal is None:
        return {"signal": "WAIT", "report": f"H={hour}: thiếu H=2 để đảo chiều."}
    return {
        "signal": final_signal,
        "pattern_signal": h2_signal,
        "report": f"H={hour}: đảo ngược H=2 ({h2_signal} -> {final_signal}).",
        "m30_dir": None,
        "h1_signal": None,
        "skip_xau_m30": True,
    }


def _finalize_pattern_result(result, broker_dt, hour, reverse=False):
    """Apply the XAU M30 post-process exactly once to an analysed slot."""
    pattern_signal = result.get("signal")
    pair_dirs = get_pair_direction(hour, pattern_signal, broker_dt)
    if not pair_dirs:
        return result
    apply_xauusd_m30_logic(pair_dirs, pattern_signal, broker_dt, hour)
    final_signal = pair_dirs.get("XAUUSD", pattern_signal)
    if reverse:
        final_signal = reverse_signal(final_signal) or final_signal
    result["pattern_signal"] = pattern_signal
    result["signal"] = final_signal
    result["skip_xau_m30"] = True
    return result


def _thursday_h2_history_result(broker_dt):
    """Reuse Monday's final H=2 XAUUSD direction for Thursday."""
    historical_signal = _lookup_h2_t2_signal(broker_dt)
    if historical_signal not in ("BUY", "SELL"):
        return None
    final_signal = reverse_signal(historical_signal) if should_reverse_h2_xau(broker_dt) else historical_signal
    suffix = " đảo tuần đặc biệt" if final_signal != historical_signal else ""
    return {
        "signal": final_signal,
        "pattern_signal": historical_signal,
        "report": f"T5 H=2: dùng lịch sử Thứ 2 {historical_signal}{suffix} -> {final_signal}.",
        "m30_dir": None,
        "h1_signal": None,
        "skip_xau_m30": True,
    }


def evaluate_h11_classification(broker_dt, symbol="XAUUSD"):
    """Evaluate 4 H1 candles (H=10, H=9, H=8, H=7) at slot H=11.
    
    Returns (group, detail_str) where group is "SW" (Sideway) or "BT" (Bình thường).
    """
    if broker_dt is None:
        return "BT", "H10:Tăng, H9:Tăng, H8:Giảm, H7:Giảm [Rule 3]"

    dirs = {}
    vn_dirs = {}
    for h in (10, 9, 8, 7):
        ts_h1 = broker_time_to_ts(broker_dt, h, 0)
        c = get_candle_by_ts(symbol, mt5.TIMEFRAME_H1, ts_h1)
        if c is not None:
            if c["close"] > c["open"]:
                d = "TANG"
            elif c["close"] < c["open"]:
                d = "GIAM"
            else:
                doji_d = resolve_doji(symbol, mt5.TIMEFRAME_H1, ts_h1, broker_dt)
                d = "TANG" if doji_d == "TANG" else "GIAM"
        else:
            d = "TANG"
        dirs[h] = d
        vn_dirs[h] = "Tăng" if d == "TANG" else "Giảm"

    d10, d9, d8, d7 = dirs[10], dirs[9], dirs[8], dirs[7]

    if d10 == "TANG":
        if d9 == "GIAM" and d8 == "TANG" and d7 == "GIAM":
            group, rule_num = "SW", 1
        elif d9 == "GIAM" and d8 == "TANG" and d7 == "TANG":
            group, rule_num = "BT", 2
        elif d9 == "TANG" and d8 == "GIAM":
            group, rule_num = "BT", 3
        elif d9 == "TANG" and d8 == "TANG":
            group, rule_num = "SW", 4
        else:
            group, rule_num = "SW", 5
    else:
        if d9 == "TANG" and d8 == "GIAM" and d7 == "TANG":
            group, rule_num = "SW", 6
        elif d9 == "TANG" and d8 == "GIAM" and d7 == "GIAM":
            group, rule_num = "BT", 7
        elif d9 == "GIAM" and d8 == "TANG":
            group, rule_num = "BT", 8
        elif d9 == "GIAM" and d8 == "GIAM":
            group, rule_num = "SW", 9
        else:
            group, rule_num = "SW", 10

    detail = f"H10:{vn_dirs[10]}, H9:{vn_dirs[9]}, H8:{vn_dirs[8]}, H7:{vn_dirs[7]}"
    return group, detail


def calculate_slot_signal(broker_dt, hour):
    """Apply the canonical H-slot matrix for live and rebuilt signals."""
    hour = int(hour)
    if hour in DISABLED_HOURS:
        return {
            "signal": "WAIT",
            "report": f"H={hour}: disabled by core rules.",
            "m30_dir": None,
            "h1_signal": None,
            "skip_xau_m30": True,
        }
    # H=2,3: XAUUSD đảo từ H=5 hôm qua
    if hour in (2, 3):
        h5_yesterday = _lookup_h5_signal_yesterday(broker_dt)
        if h5_yesterday not in ("BUY", "SELL"):
            return {"signal": "WAIT", "report": f"H={hour}: thiếu H=5 hôm qua.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        final_signal = reverse_signal(h5_yesterday)
        return {"signal": final_signal, "pattern_signal": h5_yesterday, "report": f"H={hour}: đảo H=5 hôm qua ({h5_yesterday} -> {final_signal}).", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
    # H=7,8: XAUUSD đảo từ H=5 hôm nay
    if hour in (7, 8):
        h5_today = _lookup_h5_signal_today(broker_dt)
        if h5_today not in ("BUY", "SELL"):
            return {"signal": "WAIT", "report": f"H={hour}: thiếu H=5 hôm nay.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        final_signal = reverse_signal(h5_today)
        return {"signal": final_signal, "pattern_signal": h5_today, "report": f"H={hour}: đảo H=5 hôm nay ({h5_today} -> {final_signal}).", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
    # H=9: GBP group đảo từ H=5 hôm qua (Thứ 6 cùng chiều), không XAUUSD
    if hour == 9:
        h5_yesterday = _lookup_h5_signal_yesterday(broker_dt)
        if h5_yesterday not in ("BUY", "SELL"):
            return {"signal": "WAIT", "report": "H=9: thiếu H=5 hôm qua.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        wd = broker_dt.weekday()
        final_signal = h5_yesterday if wd == 4 else reverse_signal(h5_yesterday)
        return {"signal": final_signal, "pattern_signal": h5_yesterday, "report": f"H=9: {'cùng' if wd == 4 else 'đảo'} H=5 hôm qua ({h5_yesterday} -> {final_signal}).", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
    # H=11: Phân nhóm H1 XAUUSD (SW/BT) liên quan H=2,3 ngày mai
    if hour == 11:
        group, detail = evaluate_h11_classification(broker_dt)
        result = analyze(broker_dt, 11)
        res = _finalize_pattern_result(result, broker_dt, 11)
        res["report"] = f"H=11: Nhóm {group} ({detail})\n" + res.get("report", "")
        return res
    # H=14: GBP group cùng chiều H=5 hôm nay (Thứ 6 đảo), không XAUUSD
    if hour == 14:
        h5_today = _lookup_h5_signal_today(broker_dt)
        if h5_today not in ("BUY", "SELL"):
            return {"signal": "WAIT", "report": "H=14: thiếu H=5 hôm nay.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        wd = broker_dt.weekday()
        final_signal = reverse_signal(h5_today) if wd == 4 else h5_today
        return {"signal": final_signal, "pattern_signal": h5_today, "report": f"H=14: {'đảo' if wd == 4 else 'cùng'} H=5 hôm nay ({h5_today} -> {final_signal}).", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
    result = analyze(broker_dt, hour)
    return _finalize_pattern_result(result, broker_dt, hour)

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

    return {"signal": signal, "h1_signal": None, "report": report, "m30_dir": d_m30, "h1_flipped": False}

def _resolve_weekday(broker_dt=None, weekday=None):
    if weekday is not None:
        return weekday
    if broker_dt is not None:
        return broker_dt.weekday()
    return None


def get_h11_priority_and_nogold_rules(broker_dt):
    """Determine today's priority slot (H=2, H=3, or H=4) and whether H=12,13,15 have no-gold labels,
    based on yesterday's H=11 classification (SW vs BT).
    """
    if broker_dt is None:
        return {
            "prev_h11_group": "BT",
            "priority_slot": 2,
            "priority_label": "Ưu tiên H=2",
            "has_nogold_label": False,
        }

    # Find previous trading weekday
    d = broker_dt.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    prev_dt = datetime.combine(d, datetime.min.time(), tzinfo=broker_dt.tzinfo or timezone.utc)

    prev_group, _ = evaluate_h11_classification(prev_dt)
    weekday = broker_dt.weekday() # 0: Mon, 1: Tue, 2: Wed, 3: Thu, 4: Fri
    is_special = is_h2_special_calendar_weekday(broker_dt)

    priority_slot = 2
    priority_label = "Ưu tiên H=2"
    has_nogold = False

    if weekday == 0:  # Monday (Yesterday was Friday)
        if prev_group == "SW":
            priority_slot = 3
            priority_label = "Ưu tiên đi trễ H=3"
            has_nogold = False
        else:  # BT
            priority_slot = 2
            priority_label = "Ưu tiên đi trễ H=2"
            has_nogold = True

    elif weekday == 1:  # Tuesday (Yesterday was Monday)
        if prev_group == "SW":
            priority_slot = 2
            priority_label = "Ưu tiên đi sớm H=2"
            has_nogold = False
        else:  # BT
            priority_slot = 3
            priority_label = "Ưu tiên đi trễ H=3"
            has_nogold = True

    elif weekday == 2:  # Wednesday (Yesterday was Tuesday)
        if prev_group == "SW":
            priority_slot = 2
            priority_label = "Ưu tiên đi sớm H=2"
            has_nogold = True
        else:  # BT
            priority_slot = 3
            priority_label = "Ưu tiên đi trễ H=3"
            has_nogold = False

    elif weekday == 3:  # Thursday (Yesterday was Wednesday)
        if prev_group == "SW":
            priority_slot = 3
            priority_label = "Ưu tiên đi trễ H=3"
            has_nogold = True
        else:  # BT
            priority_slot = 2
            priority_label = "Ưu tiên đi trễ H=2"
            has_nogold = False

    elif weekday == 4:  # Friday (Yesterday was Thursday)
        if prev_group == "SW":
            priority_slot = 3
            priority_label = "Ưu tiên đi trễ H=3"
            has_nogold = not is_special
        else:  # BT
            priority_slot = 2
            priority_label = "Ưu tiên đi trễ H=2"
            has_nogold = is_special

    return {
        "prev_h11_group": prev_group,
        "priority_slot": priority_slot,
        "priority_label": priority_label,
        "has_nogold_label": has_nogold,
    }


def get_h7_h8_priority_rule(broker_dt):
    """Priority between H=7 and H=8 based on H=6 candle direction and calculated H=7/8 direction (from H=5).
    
    1. Nếu H=6 tăng, và H=7 H=8 cũng tăng sau tính toán theo H=5, thì Ưu tiên đi H=8
    2. Nếu H=6 giảm, và H=7 8 tăng, sau tính toán theo H=5, thì Ưu tiên đi H=7
    """
    if broker_dt is None:
        return None

    h5_today = _lookup_h5_signal_today(broker_dt)
    if h5_today != "SELL":  # H=7,8 calculated direction = reverse_signal(H=5). Must be BUY (Tăng).
        return None

    ts_h6 = broker_time_to_ts(broker_dt, 6, 0)
    c_h6 = get_candle_by_ts("XAUUSD", mt5.TIMEFRAME_H1, ts_h6)

    if c_h6 is not None:
        if c_h6["close"] > c_h6["open"]:
            h6_dir = "TANG"
        elif c_h6["close"] < c_h6["open"]:
            h6_dir = "GIAM"
        else:
            doji_d = resolve_doji("XAUUSD", mt5.TIMEFRAME_H1, ts_h6, broker_dt)
            h6_dir = "TANG" if doji_d == "TANG" else "GIAM"
    else:
        h6_dir = "TANG"

    if h6_dir == "TANG":
        return {"priority_slot": 8, "priority_label": "Ưu tiên đi H=8"}
    else:
        return {"priority_slot": 7, "priority_label": "Ưu tiên đi H=7"}


def is_xau_no_trade_label_slot(H, broker_dt=None, weekday=None):
    """Return True if slot H has a no-gold label attached based on yesterday's H=11 SW/BT."""
    try:
        h = int(H)
    except (TypeError, ValueError):
        return False
    if h in (12, 13, 15):
        if broker_dt is not None:
            rules = get_h11_priority_and_nogold_rules(broker_dt)
            return rules["has_nogold_label"]
    return False


# Back-compat alias
def is_thursday_no_gold_slot(H, broker_dt=None, weekday=None):
    return is_xau_no_trade_label_slot(H, broker_dt=broker_dt, weekday=weekday)


def xau_no_trade_label_tag(H, broker_dt=None, weekday=None):
    """Return no-gold badge tag if slot has no-gold label."""
    if is_xau_no_trade_label_slot(H, broker_dt=broker_dt, weekday=weekday):
        return "[Không Vàng]"
    return ""


def thursday_no_gold_label(lang="VN"):
    """Legacy long label. Prefer xau_no_trade_label_tag for badges."""
    return ""


def get_hour_note(H, weekday=None, broker_dt=None):
    """Return the note for a slot."""
    try:
        h = int(H)
    except (TypeError, ValueError):
        return "Chỉ Vàng (XAUUSD)"
    if h in DISABLED_HOURS:
        return "Chỉ Vàng (XAUUSD)"
    if h == 11:
        if broker_dt is not None:
            group, detail = evaluate_h11_classification(broker_dt)
            return f"H=11: Nhóm {group} ({detail})"
        return "H=11: Phân nhóm H1 (SW/BT) từ H=10,9,8,7"

    rules = get_h11_priority_and_nogold_rules(broker_dt) if broker_dt is not None else None
    h78_rules = get_h7_h8_priority_rule(broker_dt) if broker_dt is not None and h in (7, 8) else None

    notes = {
        2: "XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua",
        3: "XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua",
        7: "XAUUSD đảo từ H=5 hôm nay",
        8: "XAUUSD đảo từ H=5 hôm nay",
        9: "GBP group đảo từ H=5 hôm qua (Thứ 6 cùng chiều)",
        14: "GBP group cùng chiều H=5 hôm nay (Thứ 6 đảo)",
    }
    base_note = notes.get(h, "Chỉ Vàng (XAUUSD)")

    if rules is not None:
        if h == rules["priority_slot"]:
            base_note = f"★ {rules['priority_label']} · " + base_note
        if h in (12, 13, 15) and rules["has_nogold_label"]:
            base_note = base_note + "; 🚫 no-gold label"

    if h78_rules is not None:
        if h == h78_rules["priority_slot"]:
            base_note = f"★ {h78_rules['priority_label']} · " + base_note

    return base_note


def get_focus_gbp_pairs(H, broker_dt=None, weekday=None):
    """XAU-only mode: no GBP focus pairs."""
    return []


def format_telegram_pair_block(pair_dirs, H, broker_dt=None, weekday=None):
    """Telegram pair block for XAU-only mode."""
    lines = []
    xau = (pair_dirs or {}).get("XAUUSD")
    if xau in ("BUY", "SELL"):
        p_icon, _ = get_signal_icon(xau)
        lines.append(f"  XAUUSD: {p_icon} {xau}")
    elif xau is None:
        pass

    d_direction = (pair_dirs or {}).get(D_DIRECTION_PAIR)
    # D-direction calculated but hidden from display (v3.16.5)

    if not lines:
        lines.append("  (không có cặp)")
    return "\n".join(lines)


GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPJPY", "GBPUSD"]
ALL_PAIRS = ["XAUUSD"] + GBP_PAIRS

day_signals = {}
sent_today = set()

def reverse_signal(signal):
    """Return the opposite trading direction."""
    if signal == "BUY":
        return "SELL"
    if signal == "SELL":
        return "BUY"
    return None


def get_d_direction_from_xau(xau_signal, broker_dt=None, weekday=None):
    """Calculate D-direction from the H=4 XAUUSD direction."""
    if xau_signal not in ("BUY", "SELL"):
        return None
    wd = _resolve_weekday(broker_dt, weekday)
    if wd in (0, 1, 2, 3, 4):
        return xau_signal
    return None


def apply_d_direction_marker(pair_dirs, H, broker_dt):
    """Attach direction pseudo pairs for UI/Telegram display.

    H=4 → Stock-DIRECTION (direction of day derived from XAUUSD)
    H=5 → GBP-DIRECTION (direction of day derived from XAUUSD)
    """
    h = int(H)
    if h not in (4, 5):
        return None
    d_direction = get_d_direction_from_xau(pair_dirs.get("XAUUSD"), broker_dt)
    if not d_direction:
        return None
    if h == 4:
        pair_dirs[D_DIRECTION_PAIR] = d_direction
    elif h == 5:
        pair_dirs[GBP_DIRECTION_PAIR] = d_direction
    return d_direction


def get_pair_direction(H, signal, broker_dt, h1_signal=None):
    """Return pair directions for XAU-only mode."""
    result = {}
    h = int(H)
    if h in DISABLED_HOURS:
        return result
    if signal not in ("BUY", "SELL"):
        return result
    # H=9,14: GBP group only, no XAUUSD
    if h in (9, 14):
        for pair in GBP_PAIRS:
            result[pair] = signal
        return result
    # All active hours: XAUUSD
    result["XAUUSD"] = signal
    apply_d_direction_marker(result, H, broker_dt)
    # H=2,3: add GBPAUD same direction as H=5 yesterday (not reversed)
    if h in (2, 3) and broker_dt is not None:
        h5_yesterday = _lookup_h5_signal_yesterday(broker_dt)
        if h5_yesterday in ("BUY", "SELL"):
            result["GBPAUD"] = h5_yesterday
    return result

# =====================================================================
# GUI TELEGRAM BAO CAO
# =====================================================================
def send_report(signal_data, H, broker_dt, h1_signal=None):
    sig = signal_data["signal"]
    report = signal_data["report"]
    m30_dir = signal_data.get("m30_dir")
    icon, emoji = get_signal_icon(sig)

    hour_note = get_hour_note(H, broker_dt=broker_dt)
    note_line = f"📝 {hour_note}\n" if hour_note else ""

    pair_dirs = get_pair_direction(
        H,
        sig,
        broker_dt,
        h1_signal=signal_data.get("h1_signal"),
    )

    # Canonical slot calculation already applies XAU M30 once.
    if not signal_data.get("skip_xau_m30"):
        apply_xauusd_m30_logic(pair_dirs, sig, broker_dt, H)

    # Hiển thị XAUUSD only.
    pair_text = format_telegram_pair_block(pair_dirs, H, broker_dt)

    conclusion = f"KẾT LUẬN (XAUUSD): {icon} {sig}\n"

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

    # Quick-order: chỉ XAUUSD.
    active_pairs = []
    xau_d = pair_dirs.get("XAUUSD")
    if xau_d in ("BUY", "SELL"):
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

    result = calculate_slot_signal(broker_dt, h)
    sig = result.get("signal")
    if sig not in ("BUY", "SELL"):
        return False

    pair_dirs = get_pair_direction(h, sig, broker_dt, h1_signal=result.get("h1_signal"))
    if not pair_dirs:
        return False

    if not result.get("skip_xau_m30"):
        apply_xauusd_m30_logic(pair_dirs, sig, broker_dt, h)

    hour_note = get_hour_note(h, broker_dt=broker_dt)
    log_signal(h, broker_dt, sig, None, pair_dirs, hour_note,
               pattern_signal=result.get("pattern_signal"))
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
        # Replace the recent window entirely so stale/old slot rows do not survive.
        rebuild_dates = {target_date.isoformat() for target_date in dates if target_date.weekday() < 5}
        filtered = [record for record in data if record.get("date") not in rebuild_dates]
        _write_signals_log_atomic(filtered)
    except Exception as error:
        print(f"  [REBUILD] Cannot clear stale history: {error}")

    rebuilt = 0
    for target_date in reversed(dates):
        if target_date.weekday() >= 5:
            continue
        fake_broker_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=12)
        hours = sorted(passed_today) if target_date == today else get_target_hours(fake_broker_dt)
        for hour in hours:
            try:
                if rebuild_slot_signal(fake_broker_dt, hour):
                    rebuilt += 1
            except Exception as error:
                print(f"  [REBUILD] Error {target_date.isoformat()} H={hour}: {error}")

    print(f"  [REBUILD] Done: {rebuilt} slots refreshed across {days} days (logic v{SIGNAL_LOGIC_VERSION})")
    return rebuilt


def rebuild_h4_history(session_count=35):
    """Backfill only H=4 weekday signals without clearing unrelated history."""
    if not mt5_ready:
        print("  [H4 BACKFILL] MT5 not ready, skip")
        return 0
    target_dates = _recent_h4_dates(get_broker_time(), session_count)
    rebuilt = 0
    for target_date in target_dates:
        target_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=12)
        try:
            rebuilt += int(rebuild_slot_signal(target_dt, 4))
        except Exception as error:
            print(f"  [H4 BACKFILL] Error {target_date.isoformat()}: {error}")
    print(f"  [H4 BACKFILL] Done: {rebuilt}/{len(target_dates)} sessions")
    return rebuilt


def _recent_h4_dates(broker_dt, session_count):
    """Return chronological weekdays whose H=4 cutoff has passed."""
    try:
        remaining = max(0, int(session_count))
    except (TypeError, ValueError):
        return []
    cursor = broker_dt.date()
    if (broker_dt.hour, broker_dt.minute) < (4, 45):
        cursor -= timedelta(days=1)
    dates = []
    while len(dates) < remaining:
        if cursor.weekday() < 5:
            dates.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(dates))


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


_xauusd_closed_today = set()
_gbp_closed_today = set()


def _close_positions_by_prefix(prefixes, label):
    """Close all open positions whose symbol starts with any of the given prefixes."""
    if not mt5_ready:
        return 0
    positions = mt5.positions_get()
    if not positions:
        return 0
    count = 0
    for pos in positions:
        sym_upper = pos.symbol.upper()
        if not any(sym_upper.startswith(p.upper()) for p in prefixes):
            continue
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            continue
        price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": pos.ticket,
            "price": price,
            "deviation": 20,
            "magic": 0,
            "comment": f"Auto-Close {label}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_TIME_GTC,
        }
        try:
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                count += 1
        except Exception as e:
            print(f"[AUTO-CLOSE] Error closing {pos.symbol}: {e}")
    return count


def main(profile_name=None):
    global mt5_ready, day_signals, sent_today, _active_profile
    print("=" * 55)
    print("  MT5 Multi-Timeframe Signal Bot v3.12.0")
    print(f"  Symbol: {SYMBOL}")
    print(f"  Target Hours: {', '.join(f'H={h}' for h in TARGET_HOURS)}")
    print(f"  Auto-close: XAUUSD 17:44, GBP 19:44 (Broker)")
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
    send_telegram(build_startup_telegram_message(broker_dt, mt5_ready))

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
                result = calculate_slot_signal(broker_dt, now_hour)
                sig = result["signal"]

                # Track H=1 signal for downstream day logic
                if now_hour == 1 and sig in ("BUY", "SELL"):
                    day_signals[(broker_dt.date(), 1)] = {"signal": sig, "m30_dir": result.get("m30_dir")}
                    _save_state(day_signals, sent_today)

                h1_data = day_signals.get((broker_dt.date(), 1))
                h1_sig = h1_data["signal"] if h1_data else None

                # Tính pair_dirs trước khi gửi
                pair_dirs = get_pair_direction(
                    now_hour,
                    sig,
                    broker_dt,
                    h1_signal=result.get("h1_signal"),
                )

                # Log for website (even WAIT signals)
                hour_note = get_hour_note(now_hour, broker_dt=broker_dt)
                log_pair_dirs = pair_dirs
                if not log_pair_dirs:
                    if now_hour in (9, 14):
                        log_pair_dirs = {p: sig for p in GBP_PAIRS}
                    else:
                        log_pair_dirs = {"XAUUSD": sig}
                log_signal(now_hour, broker_dt, sig, None, log_pair_dirs, hour_note,
                           pattern_signal=result.get("pattern_signal"))
                push_to_dashboard()

                if sig not in ("BUY", "SELL"):
                    sent_today.add(key)
                    _save_state(day_signals, sent_today)
                    print(f"  [SKIP] H={now_hour} - {result.get('report', 'không có signal')}")
                    time.sleep(10)
                    continue

                pair_dirs = send_report(result, now_hour, broker_dt, h1_signal=h1_sig)
                if now_hour == 4:
                    h4_d_direction = (pair_dirs or {}).get(D_DIRECTION_PAIR)
                    if h4_d_direction in ("BUY", "SELL"):
                        day_signals[(broker_dt.date(), 4)] = {
                            "signal": sig,
                            "m30_dir": result.get("m30_dir"),
                            "d_direction": h4_d_direction,
                        }
                        _save_state(day_signals, sent_today)
                if now_hour == 5:
                    h5_gbp_direction = (pair_dirs or {}).get(GBP_DIRECTION_PAIR)
                    if h5_gbp_direction in ("BUY", "SELL"):
                        day_signals[(broker_dt.date(), 5)] = {
                            "signal": sig,
                            "m30_dir": result.get("m30_dir"),
                            "d_direction": h5_gbp_direction,
                        }
                        _save_state(day_signals, sent_today)

                print(f"  Signal: {sig}")
                print(f"  Sent: OK")

                sent_today.add(key)
                _save_state(day_signals, sent_today)

                time.sleep(60)
            else:
                # Push giá realtime mỗi lần loop
                push_prices_to_dashboard()

                # Auto-close XAUUSD: 14:44 Thứ 2, 17:44 các ngày còn lại
                xau_close_hour = 14 if broker_dt.weekday() == 0 else 17
                if now_hour == xau_close_hour and now_min == 44:
                    today_key = broker_dt.date()
                    if today_key not in _xauusd_closed_today:
                        closed = _close_positions_by_prefix(["XAUUSD"], f"XAUUSD-{xau_close_hour}:44")
                        if closed > 0:
                            send_telegram(f"🔒 Đã đóng {closed} lệnh XAUUSD lúc {xau_close_hour}:44 (Broker)")
                            print(f"  [AUTO-CLOSE] Closed {closed} XAUUSD positions at {xau_close_hour}:44")
                        _xauusd_closed_today.add(today_key)

                # Auto-close GBP at 19:44
                if now_hour == 19 and now_min == 44:
                    today_key = broker_dt.date()
                    if today_key not in _gbp_closed_today:
                        closed = _close_positions_by_prefix(["GBPAUD", "GBPCAD", "GBPJPY", "GBPUSD"], "GBP-19:44")
                        if closed > 0:
                            send_telegram(f"🔒 Đã đóng {closed} lệnh GBP lúc 19:44 (Broker)")
                            print(f"  [AUTO-CLOSE] Closed {closed} GBP positions at 19:44")
                        _gbp_closed_today.add(today_key)

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
