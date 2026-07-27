# -*- coding: utf-8 -*-
"""
MT5 Multi-Timeframe Signal Bot v3.18.0
"""
import os
import sys
import json
import time
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
from domain.broker_clock import BrokerClock, BrokerClockError

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
TARGET_HOURS = [3, 4, 5, 6, 12, 16]
ACTIVE_HOURS = frozenset(TARGET_HOURS)
VN_UTC_OFFSET = 7  # Vietnam local timezone (Indochina Time, no DST)


def _broker_time_to_local(broker_time_str, broker_offset, local_offset=VN_UTC_OFFSET):
    """Convert a Broker wall-clock 'HH:MM' string to local (Vietnam) 'HH:MM'."""
    if not broker_time_str or ":" not in broker_time_str:
        return broker_time_str
    try:
        hour, minute = (int(part) for part in broker_time_str.split(":"))
        diff = local_offset - broker_offset
        local_hour = (hour + diff) % 24
        return f"{local_hour:02d}:{minute:02d}"
    except (ValueError, TypeError):
        return broker_time_str


def get_signal_time_for_slot(broker_dt, hour):
    """Return the Broker publication clock for a logical signal slot."""
    h = int(hour)
    if h == 3:
        return "03:00"
    if h == 4:
        return "04:45"
    if h == 5:
        return "05:45"
    if h == 6:
        return "06:00"
    if h == 12:
        return "12:00"
    if h == 16:
        return "16:00"
    raise ValueError(f"Unsupported signal slot H={h}")


def get_signal_datetime_for_slot(broker_dt, hour):
    """Return the Broker datetime at which a logical slot is published."""
    clock = get_signal_time_for_slot(broker_dt, hour)
    signal_hour, signal_minute = (int(part) for part in clock.split(":"))
    return broker_dt.replace(
        hour=signal_hour,
        minute=signal_minute,
        second=0,
        microsecond=0,
    )

def get_target_hours(broker_dt=None, weekday=None):
    """Return the active logical signal slots for a Broker weekday."""
    wd = None
    if weekday is not None:
        wd = int(weekday)
    elif broker_dt is not None:
        if isinstance(broker_dt, int):
            wd = broker_dt
        elif hasattr(broker_dt, "weekday"):
            wd = broker_dt.weekday()

    if wd is not None:
        if wd in (5, 6):
            return []
        if wd in (0, 1, 2, 3, 4):  # Mon (0) to Fri (4)
            return list(TARGET_HOURS)
        return []

    return list(TARGET_HOURS)
# Bump when pair-direction / slot rules change to trace rebuilds in logs.
SIGNAL_LOGIC_VERSION = 42
D_DIRECTION_PAIR = "Stock-DIRECTION"
GBP_DIRECTION_PAIR = "GBP-DIRECTION"


BROKER_CLOCK = BrokerClock(
    mt5,
    cache_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "broker_clock_cache.json"),
)

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


def publish_heartbeat(profile, mt5_connected, mt5_error="", profiles_path=None, broker_dt=None):
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

    state = "connected" if mt5_connected else "degraded" if mt5_error else "disconnected"
    broker_offset = None
    broker_time = ""
    broker_observed_at_utc = ""
    if broker_dt is not None:
        broker_offset = BROKER_CLOCK.utc_offset_for_date(broker_dt.date())
        broker_time = broker_dt.replace(microsecond=0).isoformat()
        broker_observed_at_utc = datetime.now(timezone.utc).isoformat()
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
        broker_time=broker_time,
        broker_utc_offset=broker_offset,
        broker_observed_at_utc=broker_observed_at_utc,
        preserve_broker_clock=False,
    )


# =====================================================================
# STATE PERSISTENCE - survive bot restarts
# =====================================================================
_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_state.json")

def _trading_date():
    """Current trading date in broker time."""
    return get_broker_time().date()

def _load_state():
    """Load persisted state from disk. Returns dict with day_signals, sent_today, etc."""
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

    pending_closes = set()
    for item in data.get("auto_close_pending", []):
        try:
            raw_date, category = item
            pending_closes.add((datetime.strptime(str(raw_date), "%Y-%m-%d").date(), str(category)))
        except (TypeError, ValueError):
            continue

    close_alerts = {}
    for item in data.get("auto_close_last_alert", []):
        try:
            raw_date, category, raw_timestamp = item
            key = (datetime.strptime(str(raw_date), "%Y-%m-%d").date(), str(category))
            close_alerts[key] = datetime.fromisoformat(str(raw_timestamp))
        except (TypeError, ValueError):
            continue

    # Daily signal state expires at the Broker date boundary. Auto-close
    # obligations remain pending across restarts and date/weekend boundaries.
    today_str = _trading_date().isoformat()
    if data.get("date") != today_str:
        return {"auto_close_pending": pending_closes, "auto_close_last_alert": close_alerts}

    # Rebuild day_signals keys as (date, hour) tuples matching main loop format
    day_signals = {}
    for k, v in data.get("day_signals", {}).items():
        day_signals[(datetime.strptime(data["date"], "%Y-%m-%d").date(), int(k))] = v

    restored_sent = set()
    for raw_date, raw_hour in data.get("sent_today", []):
        try:
            restored_date = datetime.strptime(str(raw_date), "%Y-%m-%d").date()
            restored_sent.add((restored_date, int(raw_hour)))
        except (TypeError, ValueError):
            continue

    return {
        "day_signals": day_signals,
        "sent_today": restored_sent,
        "auto_close_completed": set(data.get("auto_close_completed", [])),
        "auto_close_pending": pending_closes,
        "auto_close_last_alert": close_alerts,
        "d_direction": data.get("d_direction"),
        "d_direction_date": data.get("d_direction_date"),
    }

def _save_state(day_signals, sent_today):
    """Persist state to disk."""
    broker_now = get_broker_time()
    today_str = broker_now.date().isoformat()
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
        "auto_close_completed": sorted(
            category
            for close_date, category in _auto_close_completed
            if close_date.isoformat() == today_str
        ),
        "auto_close_pending": sorted(
            [[close_date.isoformat(), category] for close_date, category in _auto_close_pending]
        ),
        "auto_close_last_alert": sorted(
            [
                [close_date.isoformat(), category, alert_time.isoformat()]
                for (close_date, category), alert_time in _auto_close_last_alert.items()
                if (close_date, category) in _auto_close_pending
            ]
        ),
        "broker_time": broker_now.replace(microsecond=0).isoformat(),
        "broker_utc_offset": BROKER_CLOCK.utc_offset_for_date(broker_now.date()),
        "broker_observed_at_utc": datetime.now(timezone.utc).isoformat(),
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
               pattern_signal=None, deactivated=False):
    """Append signal data to signals_log.json for website consumption."""
    deactivated = bool(deactivated or is_deactivated_signal_slot(broker_dt, H))
    current_prices = get_current_prices(pair_dirs) if sig in ("BUY", "SELL") else {}
    if not entry_time:
        entry_time = get_entry_time_for_slot(broker_dt, H)
    signal_time = get_signal_time_for_slot(broker_dt, H)
    is_priority = is_priority_slot(broker_dt, H)
    record = {
        "date": broker_dt.date().isoformat(),
        "hour": H,
        "ts": datetime.now().timestamp(),
        "signal": sig,
        "signal_time": signal_time,
        "entry_time": entry_time,
        "is_priority": is_priority,
        "pair_dirs": pair_dirs,
        "entry_prices": {},
        "current_prices": current_prices,
        "hour_note": hour_note,
        "d_direction": (pair_dirs or {}).get(D_DIRECTION_PAIR),
        "deactivated": deactivated,
        "logic_version": SIGNAL_LOGIC_VERSION,
    }
    signal_hour, signal_minute = (int(part) for part in signal_time.split(":"))
    signal_broker_dt = broker_dt.replace(
        hour=signal_hour,
        minute=signal_minute,
        second=0,
        microsecond=0,
    )
    signal_utc = BROKER_CLOCK.utc_from_broker_datetime(signal_broker_dt)
    record["signal_at_utc"] = signal_utc.isoformat()
    broker_offset = BROKER_CLOCK.utc_offset_for_date(broker_dt.date())
    record["broker_utc_offset"] = broker_offset
    record["broker_clock_verified"] = True
    record["broker_timestamp_mode"] = getattr(BROKER_CLOCK, "timestamp_mode", None)
    # Local (Vietnam) times for dashboard display
    record["signal_time_local"] = _broker_time_to_local(signal_time, broker_offset)
    record["entry_time_local"] = _broker_time_to_local(entry_time, broker_offset) if entry_time else None
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


def _has_dashboard_payload(signal):
    """Return whether a record has renderable dashboard history data."""
    try:
        hour = int(signal.get("hour", -1))
    except (TypeError, ValueError):
        return False
    if hour not in ACTIVE_HOURS:
        return False
    if signal.get("pair_dirs"):
        return True
    return False


def _enrich_local_times(signal_record):
    """Add signal_time_local / entry_time_local to older records that lack them."""
    if "signal_time_local" in signal_record:
        return signal_record
    broker_offset = signal_record.get("broker_utc_offset")
    if broker_offset is None:
        return signal_record
    signal_time = signal_record.get("signal_time") or ""
    entry_time = signal_record.get("entry_time") or ""
    if signal_time:
        signal_record["signal_time_local"] = _broker_time_to_local(signal_time, broker_offset)
    if entry_time:
        signal_record["entry_time_local"] = _broker_time_to_local(entry_time, broker_offset)
    return signal_record


def select_signals_for_dashboard(all_signals):
    """Keep renderable signal history for active logical slots."""
    return [
        _enrich_local_times(signal)
        for signal in all_signals
        if _has_dashboard_payload(signal)
    ]


def _dashboard_log_pair_dirs(hour, signal, pair_dirs):
    """Return live-log directions for an active logical slot."""
    if pair_dirs:
        return pair_dirs
    if int(hour) in (9, 14):
        return {pair: signal for pair in GBP_PAIRS}
    return {"XAUUSD": signal}


def push_state_to_dashboard():
    """Push the current Broker-clock state without rebuilding signal history."""
    dashboard_url = os.environ.get("DASHBOARD_API_URL", "") or DASHBOARD_URL
    if not dashboard_url or not os.path.exists(_STATE_FILE) or os.path.getsize(_STATE_FILE) <= 2:
        return False
    api_key = os.environ.get("DASHBOARD_API_KEY", "") or _cfg.get("dashboard_api_key", "")
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)
        if not state:
            return False
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        request = urllib.request.Request(
            f"{dashboard_url}/api/state",
            data=json.dumps(state).encode("utf-8"),
            headers=headers,
        )
        urllib.request.urlopen(request, timeout=10).read()
        return True
    except Exception as error:
        print(f"[DASHBOARD] State push error: {error}")
        return False


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
        if push_state_to_dashboard():
            print("[DASHBOARD] State pushed OK")
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
    rules = "\n".join(f"⚠️ {note}" for note in day_notes)
    mt5_status = "OK" if mt5_connected else "N/A"
    return (
        "🤖 BOT KHỞI ĐỘNG\n"
        f"Nguồn pattern: {SYMBOL} | MT5: {mt5_status}\n"
        f"Slots: {', '.join(f'H={h}' for h in TARGET_HOURS)}\n"
        "🔒 Auto-close: XAUUSD 17:59 (Broker)\n"
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
    """Convert Broker wall time to the timestamp encoding used by this terminal."""
    target_broker = broker_dt.replace(hour=hour, minute=minute, second=second, microsecond=0)
    return BROKER_CLOCK.mt5_timestamp_from_broker_datetime(target_broker)

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


def _rate_value(rate, field, default=0):
    """Read a field from either an MT5 structured row or a test dictionary."""
    try:
        return rate[field]
    except (KeyError, IndexError, TypeError, ValueError):
        return default

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
    timeframe_seconds = {
        mt5.TIMEFRAME_M5: 300,
        mt5.TIMEFRAME_M30: 1800,
        mt5.TIMEFRAME_H1: 3600,
    }
    prev_offset = timeframe_seconds.get(timeframe)
    if prev_offset is None:
        return None
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
        print(f"  [M30 XAUUSD] Khong co du lieu tai {H-1}:30")
        return None
    d_m30 = candle_direction(c_m30)
    if d_m30 == "DOJI":
        d_m30 = resolve_doji("XAUUSD", mt5.TIMEFRAME_M30, ts_m30, broker_dt)
        if d_m30 is None:
            return None
        print(f"  [DOJI] M30 XAUUSD@{H-1}:30 DOJI -> fallback: {d_m30}")
    if d_m30 and d_m30 != "DOJI":
        return "BUY" if d_m30 == "TANG" else "SELL"
    return None


def _is_raw_special_day(target_date):
    """Evaluate the original calendar triggers for one Thu/Fri date."""
    weekday = target_date.weekday()
    if weekday not in (3, 4):
        return False
    if (target_date + timedelta(days=7)).month != target_date.month:
        return True
    wednesday = target_date - timedelta(days=1 if weekday == 3 else 2)
    if wednesday.day in (30, 1):
        return True
    return weekday == 4 and target_date.day in (3, 4, 7)


def is_special_day(broker_dt):
    """Return whether this Broker Thursday/Friday belongs to a special pair."""
    if broker_dt is None or broker_dt.weekday() not in (3, 4):
        return False
    target_date = broker_dt.date()
    thursday = target_date if target_date.weekday() == 3 else target_date - timedelta(days=1)
    friday = thursday + timedelta(days=1)
    if thursday.year != friday.year:
        return False
    return _is_raw_special_day(thursday) or _is_raw_special_day(friday)

def is_post_special_day(broker_dt):
    """Check if today is Monday after a special Thu/Fri."""
    if broker_dt is None:
        return False
    wd = broker_dt.weekday()
    dt = broker_dt.date()
    if wd != 0:
        return False
    prev_thu = dt - timedelta(days=3)
    prev_fri = dt - timedelta(days=2)
    thu_dt = datetime(prev_thu.year, prev_thu.month, prev_thu.day, tzinfo=broker_dt.tzinfo)
    fri_dt = datetime(prev_fri.year, prev_fri.month, prev_fri.day, tzinfo=broker_dt.tzinfo)
    return is_special_day(thu_dt) or is_special_day(fri_dt)


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
    Both endpoints are inclusive. A date can fall in up to two overlapping
    restricted windows (prev→cur and cur→next), so we check both.
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


def _count_fridays_in_month(year, month):
    """Count how many Fridays fall in a given month."""
    first = _first_friday_of_month(year, month)
    if first is None:
        return 0
    count = 0
    d = first
    while d <= 31:
        try:
            datetime(year, month, d)
            count += 1
            d += 7
        except ValueError:
            break
    return count


def is_special_day_2(broker_dt):
    """Check if today is a 'ngày đặc biệt 2' Friday or the Wednesday before it.

    Rule:
    - Months with 5 Fridays: 2nd and 3rd Friday (excluding 1st) are special day 2
    - Months with 4 Fridays: only 2nd Friday (excluding 1st) is special day 2
    - 1st Friday is NEVER a special day 2
    - Wednesday (wd=2) immediately before a special_day_2 Friday is also special_day_2
    """
    if broker_dt is None:
        return False
    wd = broker_dt.weekday()
    # Wednesday before a special_day_2 Friday
    if wd == 2:
        friday = broker_dt + timedelta(days=2)
        return _is_friday_special_day_2(friday)
    # Direct Friday check
    if wd == 4:
        return _is_friday_special_day_2(broker_dt)
    return False


def _is_friday_special_day_2(friday_dt):
    """Check whether a given date (must be a Friday) qualifies as special day 2."""
    if friday_dt is None or friday_dt.weekday() != 4:
        return False
    dt = friday_dt.date()
    first = _first_friday_of_month(dt.year, dt.month)
    if first is None:
        return False
    nth = (dt.day - first) // 7 + 1
    if nth == 1:
        return False
    total = _count_fridays_in_month(dt.year, dt.month)
    if total >= 5:
        return nth in (2, 3)
    else:
        return nth == 2


def is_month_boundary_suppress(broker_dt):
    """Disabled — month boundary suppression removed. XAUUSD always uses normal signal."""
    return False


def _lookup_historical_t2_signal(broker_dt, target_hour):
    """Look up the previous Monday signal for Thursday history reuse."""
    monday_date = broker_dt.date() - timedelta(days=3)
    date_str = monday_date.isoformat()
    try:
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            for record in reversed(data):
                if record.get("date") == date_str and int(record.get("hour", -1)) == target_hour:
                    sig = record.get("signal")
                    if sig in ("BUY", "SELL"):
                        return sig
    except Exception as e:
        print(f"[WARN] Cannot look up Monday H={target_hour} signal: {e}")
    return None

def _lookup_h3_signal_today(broker_dt):
    """Look up today's H=3 signal from signals_log history."""
    date_str = broker_dt.date().isoformat()
    try:
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            for record in reversed(data):
                if record.get("date") == date_str and int(record.get("hour", -1)) == 3:
                    sig = record.get("signal")
                    if sig in ("BUY", "SELL"):
                        return sig
    except Exception as e:
        print(f"[WARN] Cannot lookup today H=3 signal: {e}")
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


def _lookup_h4_signal_for_date(broker_dt, target_date):
    """Look up H=4 signal from signals_log for a specific date."""
    date_str = target_date.isoformat() if hasattr(target_date, 'isoformat') else str(target_date)
    try:
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            for record in reversed(data):
                if record.get("date") == date_str and int(record.get("hour", -1)) == 4:
                    sig = record.get("signal")
                    if sig in ("BUY", "SELL"):
                        return sig
    except Exception as e:
        print(f"[WARN] Cannot lookup H=4 for {date_str}: {e}")
    return None


def _lookup_h4_signal_today(broker_dt):
    return _lookup_h4_signal_for_date(broker_dt, broker_dt.date())


def _lookup_signal_from_log(broker_dt, hour):
    """Generic lookup: read signal for a given hour from signals_log.json."""
    target_date = broker_dt.date() if hasattr(broker_dt, 'date') and callable(getattr(broker_dt, 'date')) else broker_dt
    date_str = target_date.isoformat() if hasattr(target_date, 'isoformat') else str(target_date)
    try:
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            for record in reversed(data):
                if record.get("date") == date_str and int(record.get("hour", -1)) == hour:
                    sig = record.get("signal")
                    if sig in ("BUY", "SELL"):
                        return sig
    except Exception as e:
        print(f"[WARN] Cannot lookup H={hour} for {date_str}: {e}")
    return None


def _lookup_h5_signal_yesterday(broker_dt):
    """Look up H=5 from the most recent previous weekday."""
    d = broker_dt.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return _lookup_h5_signal_for_date(broker_dt, d)


def _lookup_h16_signal_yesterday(broker_dt):
    """Look up H=16 from the most recent previous weekday."""
    d = broker_dt.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return _lookup_signal_from_log(broker_dt, 16)


def apply_xauusd_m30_logic(pair_dirs, sig, broker_dt, H):
    """Cùng chiều XAUUSD M30 -> đảo XAUUSD, ngược chiều -> theo XAUUSD M30.

    Update the XAUUSD direction after M30 post-processing.
    """
    xau_m30 = get_xauusd_m30_signal(broker_dt, H)
    if xau_m30 is None:
        return None
    if "XAUUSD" not in pair_dirs:
        return pair_dirs
    if sig == xau_m30:
        final_xau = "SELL" if xau_m30 == "BUY" else "BUY"
    else:
        final_xau = xau_m30

    pair_dirs["XAUUSD"] = final_xau
    apply_d_direction_marker(pair_dirs, H, broker_dt)
    return pair_dirs


def _reversed_h3_result(broker_dt, hour):
    """Build a dependent slot from the final XAUUSD H=3 direction."""
    h3_signal = _lookup_h3_signal_today(broker_dt)
    final_signal = reverse_signal(h3_signal)
    if final_signal is None:
        return {"signal": "WAIT", "report": f"H={hour}: thiếu H=3 để đảo chiều."}
    return {
        "signal": final_signal,
        "pattern_signal": h3_signal,
        "report": f"H={hour}: đảo ngược H=3 ({h3_signal} -> {final_signal}).",
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
    
    if pattern_signal != "WAIT" and not result.get("skip_xau_m30"):
        if apply_xauusd_m30_logic(pair_dirs, pattern_signal, broker_dt, hour) is None:
            return {
                "signal": "WAIT",
                "report": f"H={hour}: missing or unresolved XAUUSD M30.",
                "skip_xau_m30": True,
            }
        
    final_signal = pair_dirs.get("XAUUSD", pattern_signal)
    if reverse:
        final_signal = reverse_signal(final_signal) or final_signal
    result["pattern_signal"] = pattern_signal
    result["signal"] = final_signal
    result["skip_xau_m30"] = True
    return result





def evaluate_classification_for_slot(broker_dt, slot_hour, symbol="XAUUSD"):
    """Evaluate the four completed H1 candles immediately before a slot."""
    h1, h2, h3, h4 = slot_hour - 1, slot_hour - 2, slot_hour - 3, slot_hour - 4
    if broker_dt is None:
        return None, "missing broker time", []

    dirs = {}
    vn_dirs = {}
    candles = []
    for h in (h4, h3, h2, h1):
        ts_h1 = broker_time_to_ts(broker_dt, h, 0)
        c = get_candle_by_ts(symbol, mt5.TIMEFRAME_H1, ts_h1)
        if c is not None:
            open_p = round(float(_rate_value(c, "open")), 2)
            close_p = round(float(_rate_value(c, "close")), 2)
            high_p = round(float(_rate_value(c, "high", max(open_p, close_p))), 2)
            low_p = round(float(_rate_value(c, "low", min(open_p, close_p))), 2)
            d = candle_direction(c)
            is_doji = (d == "DOJI")
            if is_doji:
                doji_d = resolve_doji(symbol, mt5.TIMEFRAME_H1, ts_h1, broker_dt)
                if doji_d not in ("TANG", "GIAM"):
                    return None, f"unresolved DOJI H1@{h:02d}:00", candles
                d = doji_d
                print(f"  [DOJI] H1@{h:02d}:00 DOJI -> fallback: {d}")
            candles.append({
                "hour": h,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "dir": d,
                "doji": is_doji,
            })
        else:
            return None, f"missing H1@{h:02d}:00", candles
        dirs[h] = d
        vn_dirs[h] = "Tăng" if d == "TANG" else "Giảm"

    d1, d2, d3, d4 = dirs[h1], dirs[h2], dirs[h3], dirs[h4]

    if d1 == "TANG":
        if d2 == "GIAM" and d3 == "TANG" and d4 == "GIAM":
            group, rule_num = "SW", 1
        elif d2 == "GIAM" and d3 == "TANG" and d4 == "TANG":
            group, rule_num = "BT", 2
        elif d2 == "TANG" and d3 == "GIAM":
            group, rule_num = "BT", 3
        elif d2 == "TANG" and d3 == "TANG":
            group, rule_num = "SW", 4
        else:
            group, rule_num = "SW", 5
    else:
        if d2 == "TANG" and d3 == "GIAM" and d4 == "TANG":
            group, rule_num = "SW", 6
        elif d2 == "TANG" and d3 == "GIAM" and d4 == "GIAM":
            group, rule_num = "BT", 7
        elif d2 == "GIAM" and d3 == "TANG":
            group, rule_num = "BT", 8
        elif d2 == "GIAM" and d3 == "GIAM":
            group, rule_num = "SW", 9
        else:
            group, rule_num = "SW", 10

    detail = f"H{h1}:{vn_dirs[h1]}, H{h2}:{vn_dirs[h2]}, H{h3}:{vn_dirs[h3]}, H{h4}:{vn_dirs[h4]}"
    return group, detail, candles

def evaluate_4_m30_classification_before_hour(broker_dt, target_hour, symbol="XAUUSD"):
    """Evaluate 4 M30 candles before target_hour Broker time."""
    if broker_dt is None:
        return None

    h_m1, m_m1 = target_hour - 1, 30
    h_m2, m_m2 = target_hour - 1, 0
    h_m3, m_m3 = target_hour - 2, 30
    h_m4, m_m4 = target_hour - 2, 0

    m_times = [(h_m4, m_m4), (h_m3, m_m3), (h_m2, m_m2), (h_m1, m_m1)]
    dirs = {}
    for h, m in m_times:
        ts = broker_time_to_ts(broker_dt, h, m)
        c = get_candle_by_ts(symbol, mt5.TIMEFRAME_M30, ts)
        if c is not None:
            d = candle_direction(c)
            if d == "DOJI":
                doji_d = resolve_doji(symbol, mt5.TIMEFRAME_M30, ts, broker_dt)
                if doji_d not in ("TANG", "GIAM"):
                    return None
                d = doji_d
        else:
            return None
        time_key = f"{h:02d}:{m:02d}"
        dirs[time_key] = d

    d1 = dirs[f"{h_m1:02d}:{m_m1:02d}"]
    d2 = dirs[f"{h_m2:02d}:{m_m2:02d}"]
    d3 = dirs[f"{h_m3:02d}:{m_m3:02d}"]
    d4 = dirs[f"{h_m4:02d}:{m_m4:02d}"]

    if d1 == "TANG":
        if d2 == "GIAM" and d3 == "TANG" and d4 == "GIAM":
            group = "SW"
        elif d2 == "GIAM" and d3 == "TANG" and d4 == "TANG":
            group = "BT"
        elif d2 == "TANG" and d3 == "GIAM":
            group = "BT"
        elif d2 == "TANG" and d3 == "TANG":
            group = "SW"
        else:
            group = "SW"
    else:
        if d2 == "TANG" and d3 == "GIAM" and d4 == "TANG":
            group = "SW"
        elif d2 == "TANG" and d3 == "GIAM" and d4 == "GIAM":
            group = "BT"
        elif d2 == "GIAM" and d3 == "TANG":
            group = "BT"
        elif d2 == "GIAM" and d3 == "GIAM":
            group = "SW"
        else:
            group = "SW"

    return group


def evaluate_3_m30_classification_for_h3(broker_dt, symbol="XAUUSD"):
    """Evaluate H=3 from M30 candles at 01:30, 02:00, and 02:30 Broker."""
    if broker_dt is None:
        return None

    m_times = [(1, 30), (2, 0), (2, 30)]
    dirs = {}
    for h, m in m_times:
        ts = broker_time_to_ts(broker_dt, h, m)
        c = get_candle_by_ts(symbol, mt5.TIMEFRAME_M30, ts)
        if c is not None:
            d = candle_direction(c)
            if d == "DOJI":
                doji_d = resolve_doji(symbol, mt5.TIMEFRAME_M30, ts, broker_dt)
                if doji_d not in ("TANG", "GIAM"):
                    return None
                d = doji_d
        else:
            return None
        dirs[f"{h:02d}:{m:02d}"] = d

    d1 = dirs["02:30"]
    d2 = dirs["02:00"]
    d3 = dirs["01:30"]

    if d1 == "TANG" and d2 == "TANG" and d3 == "TANG":
        return "SW"
    if d1 == "GIAM" and d2 == "TANG" and d3 == "TANG":
        return "SW"
    if d1 == "GIAM" and d2 == "TANG" and d3 == "GIAM":
        return "BT"
    if d1 == "GIAM" and d2 == "GIAM" and d3 == "TANG":
        return "BT"

    if d1 == "GIAM" and d2 == "GIAM" and d3 == "GIAM":
        return "SW"
    if d1 == "TANG" and d2 == "GIAM" and d3 == "GIAM":
        return "SW"
    if d1 == "TANG" and d2 == "GIAM" and d3 == "TANG":
        return "BT"
    if d1 == "TANG" and d2 == "TANG" and d3 == "GIAM":
        return "BT"

    return "SW"


def is_priority_slot(broker_dt, hour):
    """Return True if slot has priority badge according to 4-M30 selection rules."""
    if broker_dt is None:
        return False
    h = int(hour)
    wd = broker_dt.weekday()
    if h == 6:
        return evaluate_4_m30_classification_before_hour(broker_dt, 6) == "SW"
    if h == 12:
        group = evaluate_4_m30_classification_before_hour(broker_dt, 12)
        if wd in (0, 4):
            return group == "BT"
        return group == "SW"
    return False


def is_deactivated_signal_slot(broker_dt, hour):
    """Return whether a calculated slot is dependency-only and must not be traded."""
    if broker_dt is None:
        return False
    h = int(hour)
    if h in (4, 5):
        return True
    if h == 3 and broker_dt.weekday() == 3:
        return True
    # H=16 on Thursday (Thứ 5): always deactivated (DO NOT ENTER)
    if h == 16 and broker_dt.weekday() == 3:
        return True
    # Restricted calendar period: H=12 and H=16 are DO NOT ENTER
    if h in (12, 16) and _is_in_restricted_calendar_period(broker_dt):
        return True
    return False


def get_entry_time_for_slot(broker_dt, hour):
    """Calculate entry_time (Broker HH:MM) based on 4-M30 candle classification rules."""
    h = int(hour)
    if broker_dt is None:
        return f"{h:02d}:45"
    wd = broker_dt.weekday()
    if h == 3:
        group = evaluate_3_m30_classification_for_h3(broker_dt)
        if group is None:
            return None
        return "03:49" if group == "SW" else "03:11"
    if h == 6:
        return "06:11"
    if h == 12:
        return "12:11"
    if h == 16:
        group_h6 = evaluate_4_m30_classification_before_hour(broker_dt, 6)
        if group_h6 is None:
            return None
        return "16:11" if group_h6 == "SW" else "16:49"

    if h == 4:
        return "04:45"
    if h == 5:
        return "05:45"
    return f"{h:02d}:45"


def get_slot_retry_deadline(broker_dt, hour, entry_time=None):
    """Return the last Broker datetime at which a live slot may be emitted."""
    h = int(hour)
    fallback_clocks = {
        3: "03:49",
        4: "04:45",
        5: "05:45",
        6: "06:11",
        12: "12:11",
        16: "16:49",
    }
    clock = entry_time or get_entry_time_for_slot(broker_dt, h) or fallback_clocks[h]
    deadline_hour, deadline_minute = (int(part) for part in clock.split(":"))
    deadline = broker_dt.replace(
        hour=deadline_hour,
        minute=deadline_minute,
        second=59 if h in (4, 5) else 0,
        microsecond=999999 if h in (4, 5) else 0,
    )
    return deadline


def _apply_weekday_extra_inversion(hour, signal, broker_dt):
    """Apply extra XAUUSD signal inversion according to weekday rules:
    - Monday (wd=0): H=16
    - Tuesday (wd=1): H=6, 9, 12, 14
    - Wednesday (wd=2): H=6, 9, 12, 14, 16
    - Friday (wd=4): H=6, 9
    """
    if broker_dt is None or signal not in ("BUY", "SELL"):
        return signal
    wd = broker_dt.weekday()
    h = int(hour)
    if wd == 0 and h == 16:
        return reverse_signal(signal) or signal
    if wd == 1 and h in (6, 12):
        return reverse_signal(signal) or signal
    if wd == 2 and h in (6, 12, 16):
        return reverse_signal(signal) or signal
    if wd == 4 and h == 6:
        return reverse_signal(signal) or signal
    return signal


def calculate_slot_signal(broker_dt, hour):
    """Apply the canonical H-slot matrix for live and rebuilt signals."""
    hour = int(hour)
    if hour not in ACTIVE_HOURS:
        return {
            "signal": "WAIT",
            "report": f"H={hour}: inactive slot.",
            "m30_dir": None,
            "h1_signal": None,
            "skip_xau_m30": True,
            "suppressed": True,
        }
    # H=3: XAUUSD reverses yesterday H=5; Thursday reuses Monday H=3.
    if hour == 3:
        entry_group = evaluate_3_m30_classification_for_h3(broker_dt)
        if entry_group is None:
            return {"signal": "WAIT", "report": "H=3: incomplete 3M30.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        if broker_dt.weekday() == 3:  # Thứ 5
            historical_signal = _lookup_historical_t2_signal(broker_dt, hour)
            if historical_signal not in ("BUY", "SELL"):
                return {"signal": "WAIT", "report": f"H={hour}: thiếu lịch sử Thứ 2.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
            final_signal = historical_signal
        else:
            h5_yesterday = _lookup_h5_signal_yesterday(broker_dt)
            if h5_yesterday not in ("BUY", "SELL"):
                return {"signal": "WAIT", "report": f"H={hour}: thiếu H=5 hôm qua.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
            final_signal = reverse_signal(h5_yesterday)
        gbp_aud = reverse_signal(final_signal) or final_signal
        result = {
            "signal": final_signal,
            "pattern_signal": final_signal,
            "report": f"H={hour}: XAUUSD={final_signal}, GBPAUD={gbp_aud}.",
            "m30_dir": None,
            "h1_signal": None,
            "skip_xau_m30": True,
            "pair_dirs": {"XAUUSD": final_signal, "GBPAUD": gbp_aud},
        }
        if is_deactivated_signal_slot(broker_dt, hour):
            result["deactivated"] = True
        return result
    # H=6: reverse H=3, then apply the four-H1 classification.
    if hour == 6:
        priority_group = evaluate_4_m30_classification_before_hour(broker_dt, 6)
        if priority_group is None:
            return {"signal": "WAIT", "report": "H=6: incomplete priority 4M30.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        h3_signal = _lookup_h3_signal_today(broker_dt)
        if h3_signal not in ("BUY", "SELL"):
            return {"signal": "WAIT", "report": f"H={hour}: thiếu H=3.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        final_signal = reverse_signal(h3_signal)
        final_signal = _apply_weekday_extra_inversion(hour, final_signal, broker_dt)
        # 4 H1 lookback: BT -> đảo lại, SW -> giữ nguyên
        group, detail, _ = evaluate_classification_for_slot(broker_dt, 6)
        if group is None:
            return {"signal": "WAIT", "report": f"H=6: incomplete 4H1 ({detail}).", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        if group == "BT":
            final_signal = reverse_signal(final_signal)
            report = f"H=6: đảo H=3 ({h3_signal} -> {reverse_signal(h3_signal)}), BT({detail}) -> đảo lại ({final_signal})."
        else:
            report = f"H=6: đảo H=3 ({h3_signal} -> {final_signal}), SW({detail}) -> giữ nguyên."
        # Special day: H=6 đảo thêm khi Thứ 5/6 là special day
        if broker_dt is not None and broker_dt.weekday() in (3, 4) and is_special_day(broker_dt):
            final_signal = reverse_signal(final_signal)
            report += f" [Special day -> đảo lại ({final_signal})]"
        # Special day 2: H=6 đảo thêm khi Thứ 4/6 là special day 2
        if broker_dt is not None and is_special_day_2(broker_dt):
            final_signal = reverse_signal(final_signal)
            report += f" [Special day 2 -> đảo lại ({final_signal})]"
        result = {"signal": final_signal, "pattern_signal": h3_signal, "report": report, "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        return result
    # H=12: XAUUSD đảo ngược H=4, sau đó áp dụng 4 H1 lookback
    if hour == 12:
        # Thursday (Thứ 5): H=12 = reverse of yesterday H=16 (always, not just special_day_2)
        if broker_dt is not None and broker_dt.weekday() == 3:
            h16_yesterday = _lookup_h16_signal_yesterday(broker_dt)
            if h16_yesterday not in ("BUY", "SELL"):
                return {"signal": "WAIT", "report": "H=12: thiếu H=16 Thứ 4.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
            final_signal = reverse_signal(h16_yesterday)
            final_signal = _apply_weekday_extra_inversion(hour, final_signal, broker_dt)
            report = f"H=12: đảo H=16 Thứ 4 ({h16_yesterday} -> {final_signal})."
            return {"signal": final_signal, "pattern_signal": h16_yesterday, "report": report, "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        priority_group = evaluate_4_m30_classification_before_hour(broker_dt, 12)
        if priority_group is None:
            return {"signal": "WAIT", "report": "H=12: incomplete priority 4M30.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        h4_signal = _lookup_h4_signal_today(broker_dt)
        if h4_signal not in ("BUY", "SELL"):
            return {"signal": "WAIT", "report": f"H={hour}: thiếu H=4 hôm nay.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        final_signal = reverse_signal(h4_signal)
        final_signal = _apply_weekday_extra_inversion(hour, final_signal, broker_dt)
        # 4 H1 lookback: BT -> đảo lại, SW -> giữ nguyên
        group, detail, _ = evaluate_classification_for_slot(broker_dt, 12)
        if group is None:
            return {"signal": "WAIT", "report": f"H=12: incomplete 4H1 ({detail}).", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        if group == "BT":
            final_signal = reverse_signal(final_signal)
            report = f"H={hour}: đảo H=4 ({h4_signal} -> {reverse_signal(h4_signal)}), BT({detail}) -> đảo lại ({final_signal})."
        else:
            report = f"H={hour}: đảo H=4 ({h4_signal} -> {final_signal}), SW({detail}) -> giữ nguyên."
        return {"signal": final_signal, "pattern_signal": h4_signal, "report": report, "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
    # H=16: always pairs H6↔H12 (H=9 and H=14 removed).
    if hour == 16:
        left_signal = _lookup_signal_from_log(broker_dt, 6)
        right_signal = _lookup_signal_from_log(broker_dt, 12)
        if left_signal not in ("BUY", "SELL") or right_signal not in ("BUY", "SELL"):
            return {"signal": "WAIT", "report": "H=16: missing H=6 or H=12.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True, "pair_dirs": {}}

        if left_signal != right_signal:
            final_signal = left_signal
            relation = "opposite -> follow H=6"
        else:
            final_signal = reverse_signal(left_signal)
            relation = "same -> reverse H=6"

        final_signal = _apply_weekday_extra_inversion(16, final_signal, broker_dt)
        report = f"H=16: H6={left_signal}, H12={right_signal} ({relation}) -> {final_signal}"
        return {
            "signal": final_signal,
            "pattern_signal": left_signal,
            "report": report,
            "m30_dir": None,
            "h1_signal": None,
            "skip_xau_m30": True,
            "pair_dirs": {"XAUUSD": final_signal},
        }

    result = _finalize_pattern_result(analyze(broker_dt, hour), broker_dt, hour)
    if is_deactivated_signal_slot(broker_dt, hour):
        result["deactivated"] = True
    return result

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
    """Tính signal pattern M5/M30 cho các slot cơ bản."""
    actual_broker_time = get_broker_time()
    if broker_dt.date() == actual_broker_time.date():
        signal_dt = get_signal_datetime_for_slot(broker_dt, H)
        if actual_broker_time < signal_dt:
            return {"signal": "WAIT", "report": f"Chua toi {get_signal_time_for_slot(broker_dt, H)}", "skip_xau_m30": True}

    ts_m35 = broker_time_to_ts(broker_dt, H, 35)
    ts_m40 = broker_time_to_ts(broker_dt, H, 40)

    c_m35 = get_candle_by_ts(SYMBOL, mt5.TIMEFRAME_M5, ts_m35)
    c_m40 = get_candle_by_ts(SYMBOL, mt5.TIMEFRAME_M5, ts_m40)

    d_m35 = candle_direction(c_m35)
    d_m40 = candle_direction(c_m40)

    if d_m35 is None or d_m40 is None:
        print(f"  [SKIP] Khong du du lieu M5 tai {fmt_hour(H)}:35 / {fmt_hour(H)}:40")
        return {"signal": "WAIT", "report": "Khong du du lieu M5", "skip_xau_m30": True}
    # DOJI fallback: lùi 1 nến trước cùng khung
    if d_m35 == "DOJI":
        d_m35 = resolve_doji(SYMBOL, mt5.TIMEFRAME_M5, ts_m35, broker_dt)
        if d_m35 is None:
            return {"signal": "WAIT", "report": "Unresolved DOJI M5@35", "skip_xau_m30": True}
        print(f"  [DOJI] M5@{fmt_hour(H)}:35 DOJI -> fallback: {d_m35}")
    if d_m40 == "DOJI":
        d_m40 = resolve_doji(SYMBOL, mt5.TIMEFRAME_M5, ts_m40, broker_dt)
        if d_m40 is None:
            return {"signal": "WAIT", "report": "Unresolved DOJI M5@40", "skip_xau_m30": True}
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
            return {"signal": "WAIT", "report": "Unresolved DOJI M30", "skip_xau_m30": True}
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


def get_hour_note(H, weekday=None, broker_dt=None):
    """Return the note for a slot."""
    try:
        h = int(H)
    except (TypeError, ValueError):
        return ""
    if h not in ACTIVE_HOURS:
        return ""
    notes = {
        3: "XAUUSD đảo H=5 hôm qua; GBPAUD ngược XAUUSD",
        4: "XAUUSD theo pattern M5/M30; tạo Stock-DIRECTION",
        5: "XAUUSD theo pattern M5/M30; tạo GBP-DIRECTION",
        6: "XAUUSD đảo H=3, sau đó áp dụng nhóm 4H1",
        12: "XAUUSD đảo H=4, sau đó áp dụng nhóm 4H1",
        16: "So sánh H6↔H12: opposite → follow H6, same → reverse H6",
    }
    if broker_dt is not None and h == 3 and broker_dt.weekday() == 3:
        notes[3] = "XAUUSD & GBPAUD dùng lại lịch sử H=3 của Thứ 2"
    return notes.get(h, "")


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
    elif xau in ("SW", "BT"):
        icon = "🟡" if xau == "SW" else "⚪"
        lbl = "Sideway" if xau == "SW" else "Bình Thường"
        lines.append(f"  XAUUSD: {icon} {lbl}")
    elif xau == "WAIT":
        lines.append("  XAUUSD: ⏳ WAIT")
    elif xau is None:
        pass

    # GBP pairs hidden from Telegram display (user decision: only track XAUUSD)
    # for gbp_pair in GBP_PAIRS:
    #     gbp_dir = (pair_dirs or {}).get(gbp_pair)
    #     if gbp_dir in ("BUY", "SELL"):
    #         g_icon, _ = get_signal_icon(gbp_dir)
    #         lines.append(f"  {gbp_pair}: {g_icon} {gbp_dir}")
    #     elif gbp_dir == "WAIT":
    #         lines.append(f"  {gbp_pair}: ⏳ WAIT")

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


def get_pair_direction(H, signal, broker_dt, h1_signal=None, full_result=None):
    """Return the configured XAU or GBP output directions for one slot."""
    result = {}
    h = int(H)
    if h not in ACTIVE_HOURS:
        return result
    if signal in ("SW", "BT"):
        return {}
    if signal == "MIXED" and h == 9 and full_result:
        xau = full_result.get("xau_signal")
        gbp = full_result.get("gbp_signal")
        if xau in ("BUY", "SELL"):
            result["XAUUSD"] = xau
        if gbp in ("BUY", "SELL"):
            for pair in GBP_PAIRS:
                result[pair] = gbp
        return result
    if signal == "WAIT":
        if full_result and "pair_dirs" in full_result:
            for pair, direction in full_result["pair_dirs"].items():
                result[pair] = direction
        if not result:
            result["XAUUSD"] = "WAIT"
        return result
    if signal not in ("BUY", "SELL"):
        return result
    # All active hours: XAUUSD
    result["XAUUSD"] = signal
    apply_d_direction_marker(result, H, broker_dt)
    # H=3: add GBPAUD opposite XAUUSD.
    if h == 3 and broker_dt is not None:
        result["GBPAUD"] = reverse_signal(signal) or signal
    return result

# =====================================================================
# GUI TELEGRAM BAO CAO
# =====================================================================
def send_report(signal_data, H, broker_dt, h1_signal=None):
    sig = signal_data["signal"]
    report = signal_data["report"]
    icon, emoji = get_signal_icon(sig)
    hour_note = get_hour_note(H, broker_dt=broker_dt)
    note_line = f"📝 {hour_note}\n" if hour_note else ""
    pair_dirs = get_pair_direction(
        H,
        sig,
        broker_dt,
        h1_signal=signal_data.get("h1_signal"),
        full_result=signal_data
    )

    # Canonical slot calculation already applies XAU M30 once.
    if not signal_data.get("skip_xau_m30"):
        if apply_xauusd_m30_logic(pair_dirs, sig, broker_dt, H) is None:
            return {}

    pair_text = format_telegram_pair_block(pair_dirs, H, broker_dt)
    signal_time = get_signal_time_for_slot(broker_dt, H)
    entry_time = get_entry_time_for_slot(broker_dt, H) or "N/A"
    deactivated = bool(
        signal_data.get("deactivated") or is_deactivated_signal_slot(broker_dt, H)
    )
    if deactivated:
        h = int(H)
        if h in (4, 5):
            reason = "SLOT TRUNG GIAN CHỈ DÙNG ĐỂ TÍNH TOÁN"
        elif h == 3 and broker_dt.weekday() == 3:
            reason = "H=3 THỨ NĂM CHỈ DÙNG ĐỂ ĐỐI CHIẾU"
        elif h == 16 and broker_dt.weekday() == 3:
            reason = "H=16 THỨ NĂM: DEACTIVATED (DO NOT ENTER)"
        elif h in (12, 16) and _is_in_restricted_calendar_period(broker_dt):
            reason = f"H={h} GIAI HẠN CUỘI THÁNG: DEACTIVATED (DO NOT ENTER)"
        else:
            reason = "SLOT DEACTIVATED"
        send_telegram(
            f"⛔ H={H} — KHÔNG VÀO LỆNH\n"
            "============================\n"
            f"{reason}\n"
            f"Phát: {signal_time} Broker\n"
            "Signal đã được lưu ở trạng thái deactivated chỉ để đối chiếu.\n"
            "Không dùng bản ghi này để giao dịch."
        )
        return pair_dirs
    title = f"{emoji} Tín hiệu H={H} — {icon} {sig}"
    footer = "Chỉ tham khảo. Kỷ luật là sức mạnh!"
    msg = (
        f"{title}\n"
        f"============================\n"
        f"Phát: {signal_time} Broker\n"
        f"============================\n\n"
        f"{report}\n\n"
        f"KẾT LUẬN (XAUUSD): {icon} {sig}\n"
        f"-------------------\n{pair_text}\n-------------------\n"
        f"{note_line}"
        f"============================\n{footer}"
    )
    send_telegram(msg)
    return pair_dirs

# =====================================================================
def is_slot_ready(broker_dt, hour):
    """Return whether the mapped publication clock for this slot has passed."""
    h = int(hour)
    if h not in ACTIVE_HOURS:
        return False
    # H=16: ready immediately when H=6 and H=12 are logged (pure dependency, no live candles).
    if h == 16:
        h6 = _lookup_signal_from_log(broker_dt, 6)
        h12 = _lookup_signal_from_log(broker_dt, 12)
        return h6 in ("BUY", "SELL") and h12 in ("BUY", "SELL")
    return broker_dt >= get_signal_datetime_for_slot(broker_dt, h)


# =====================================================================
# REBUILD: tính lại signals_log từ MT5 khi bot khởi động (tránh push data cũ)
# =====================================================================
def rebuild_slot_signal(broker_dt, h):
    """Recalculate one slot with current logic and overwrite signals_log (date, hour)."""
    if broker_dt.weekday() >= 5:
        return False

    result = calculate_slot_signal(broker_dt, h)
    sig = result.get("signal")
    if sig == "WAIT":
        return False
    if sig not in ("BUY", "SELL", "SW", "BT", "MIXED"):
        return False
    entry_time = get_entry_time_for_slot(broker_dt, h)
    if not entry_time:
        return False

    pair_dirs = get_pair_direction(h, sig, broker_dt, h1_signal=result.get("h1_signal"), full_result=result)
    if not pair_dirs:
        return False

    if not result.get("skip_xau_m30"):
        apply_xauusd_m30_logic(pair_dirs, sig, broker_dt, h)

    hour_note = get_hour_note(h, broker_dt=broker_dt)
    log_signal(h, broker_dt, sig, entry_time, pair_dirs, hour_note,
               pattern_signal=result.get("pattern_signal"),
               deactivated=result.get("deactivated", False))
    return True


def rebuild_recent_history(days=45):
    """Recalculate and replace the latest 30 trading sessions (45 calendar days) using current logic v23."""
    if not mt5_ready:
        print("  [REBUILD] MT5 not ready, skip")
        return 0

    broker_dt = get_broker_time()
    today = broker_dt.date()
    dates = [today - timedelta(days=i) for i in range(days)]
    try:
        data = []
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as file:
                data = json.load(file)
        # Replace each recent weekday completely. Filtering only active slots left
        # Replace the recent window entirely so stale/old slot rows do not survive.
        rebuild_dates = {target_date.isoformat() for target_date in dates if target_date.weekday() < 5}
        filtered = [
            record
            for record in data
            if record.get("date") not in rebuild_dates
            and int(record.get("hour", -1)) in ACTIVE_HOURS
        ]
        _write_signals_log_atomic(filtered)
    except Exception as error:
        print(f"  [REBUILD] Cannot clear stale history: {error}")

    rebuilt = 0
    for target_date in reversed(dates):
        if target_date.weekday() >= 5:
            continue
        hours = get_target_hours(datetime.combine(target_date, datetime.min.time()))
        for hour in hours:
            if target_date == today and not is_slot_ready(broker_dt, hour):
                continue
            slot_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=hour)
            try:
                if rebuild_slot_signal(slot_dt, hour):
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
    """Backward-compatible startup hook; refreshes 30 trading sessions of recent history using logic v23."""
    return rebuild_recent_history(days=45)


def backfill_missing_days():
    """Backward-compatible alias; rebuild now covers startup refresh."""
    return rebuild_signals_on_startup()

# =====================================================================
# MAIN LOOP
# =====================================================================
mt5_ready = False
_broker_clock_error = ""

def try_init_mt5():
    global mt5_ready
    if mt5_ready:
        return True
    ok = mt5.initialize(path=MT5_PATH) if MT5_PATH else mt5.initialize()
    if ok:
        mt5_ready = True
        BROKER_CLOCK.clear_cache()
        info = mt5.account_info()
        if info:
            print(f"  [OK] MT5: {info.server} | {info.login}")
        return True
    return False

def get_broker_time():
    """Return Broker wall time from the calibrated MT5 timestamp mode."""
    if not mt5_ready:
        raise BrokerClockError("MT5 is not connected")
    return BROKER_CLOCK.now()

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


_auto_close_completed = set()
_auto_close_pending = set()
_auto_close_last_attempt = {}
_auto_close_last_alert = {}


def _close_positions_by_prefix(prefixes, label):
    """Close every matching position and report attempted/closed/remaining counts."""
    if not mt5_ready:
        return {"attempted": 0, "closed": 0, "remaining": None}
    positions = mt5.positions_get()
    if positions is None:
        return {"attempted": 0, "closed": 0, "remaining": None}
    matching = [
        position
        for position in positions
        if any(position.symbol.upper().startswith(prefix.upper()) for prefix in prefixes)
    ]
    closed = 0
    for pos in matching:
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
        }
        filling_mode = _get_order_filling_mode(pos.symbol)
        if filling_mode is None:
            print(f"[AUTO-CLOSE] Cannot determine filling mode for {pos.symbol}")
            continue
        request["type_filling"] = filling_mode
        try:
            res = mt5.order_send(request)
            success_codes = {mt5.TRADE_RETCODE_DONE}
            if hasattr(mt5, "TRADE_RETCODE_DONE_PARTIAL"):
                success_codes.add(mt5.TRADE_RETCODE_DONE_PARTIAL)
            if res and res.retcode in success_codes:
                closed += 1
        except Exception as e:
            print(f"[AUTO-CLOSE] Error closing {pos.symbol}: {e}")
    remaining_positions = mt5.positions_get()
    if remaining_positions is None:
        remaining = None
    else:
        remaining = sum(
            any(position.symbol.upper().startswith(prefix.upper()) for prefix in prefixes)
            for position in remaining_positions
        )
    return {"attempted": len(matching), "closed": closed, "remaining": remaining}


def _get_order_filling_mode(symbol):
    """Choose a filling mode allowed by the symbol and execution mode."""
    try:
        if not mt5.symbol_select(symbol, True):
            return None
    except Exception:
        return None
    info = mt5.symbol_info(symbol)
    if info is None:
        return None
    allowed = int(getattr(info, "filling_mode", 0) or 0)
    if allowed & 2:
        return getattr(mt5, "ORDER_FILLING_IOC", None)
    if allowed & 1:
        return getattr(mt5, "ORDER_FILLING_FOK", None)
    execution_mode = getattr(info, "trade_exemode", None)
    market_execution = getattr(mt5, "SYMBOL_TRADE_EXECUTION_MARKET", 2)
    if execution_mode is not None and execution_mode != market_execution:
        return getattr(mt5, "ORDER_FILLING_RETURN", None)
    return None


def _process_auto_close_group(broker_dt, category, cutoff, prefixes, obligation_date=None):
    """Retry one daily ALL-position close group once per Broker minute."""
    close_date = obligation_date or broker_dt.date()
    key = (close_date, category)
    is_pending = key in _auto_close_pending
    if key in _auto_close_completed:
        return
    if not is_pending and (close_date != broker_dt.date() or (broker_dt.hour, broker_dt.minute) < cutoff):
        return
    if not is_pending:
        _auto_close_pending.add(key)
        _save_state(day_signals, sent_today)
    minute_key = (broker_dt.date(), broker_dt.hour, broker_dt.minute)
    if _auto_close_last_attempt.get(key) == minute_key:
        return
    _auto_close_last_attempt[key] = minute_key
    label = f"{category.upper()}-{cutoff[0]:02d}:{cutoff[1]:02d}"
    outcome = _close_positions_by_prefix(prefixes, label)
    if outcome["remaining"] == 0:
        _auto_close_pending.discard(key)
        _auto_close_completed.add(key)
        _auto_close_last_alert.pop(key, None)
        _save_state(day_signals, sent_today)
        if outcome["attempted"]:
            send_telegram(
                f"🔒 Đã đóng ALL {category.upper()}: "
                f"{outcome['closed']}/{outcome['attempted']} lệnh lúc {cutoff[0]:02d}:{cutoff[1]:02d} Broker"
            )
        return
    last_alert = _auto_close_last_alert.get(key)
    if last_alert is None or (broker_dt - last_alert).total_seconds() >= 900:
        _auto_close_last_alert[key] = broker_dt
        _save_state(day_signals, sent_today)
        send_telegram(
            f"⚠️ Auto-close {category.upper()} chưa hoàn tất; "
            f"còn {outcome['remaining'] if outcome['remaining'] is not None else 'N/A'} lệnh. Bot sẽ retry mỗi phút."
        )


def _process_auto_closes(broker_dt):
    """Run weekday intraday ALL-position closes on the Broker clock."""
    if broker_dt.weekday() >= 5:
        return
    groups = {
        "xau": ((17, 59), ["XAUUSD"]),
        "gbp": ((19, 59), ["GBPAUD", "GBPCAD", "GBPJPY", "GBPUSD"]),
    }
    for close_date, category in sorted(_auto_close_pending):
        if category in groups:
            cutoff, prefixes = groups[category]
            _process_auto_close_group(broker_dt, category, cutoff, prefixes, close_date)
    pending_categories = {category for _, category in _auto_close_pending}
    for category, (cutoff, prefixes) in groups.items():
        if category not in pending_categories:
            _process_auto_close_group(broker_dt, category, cutoff, prefixes)


def _mark_passed_slots_on_startup(broker_dt):
    """Suppress catch-up Telegram sends for publication minutes already passed."""
    for hour in get_target_hours(broker_dt):
        signal_dt = get_signal_datetime_for_slot(broker_dt, hour)
        if broker_dt >= signal_dt:
            sent_today.add((broker_dt.date(), hour))


def _remember_daily_direction(hour, broker_dt, signal, result, pair_dirs):
    """Persist the two daily direction markers used by downstream features."""
    marker = D_DIRECTION_PAIR if hour == 4 else GBP_DIRECTION_PAIR if hour == 5 else None
    if marker is None:
        return
    direction = (pair_dirs or {}).get(marker)
    if direction not in ("BUY", "SELL"):
        return
    day_signals[(broker_dt.date(), hour)] = {
        "signal": signal,
        "m30_dir": result.get("m30_dir"),
        "d_direction": direction,
    }


def _process_live_slot(broker_dt, hour):
    """Publish one due logical slot, retrying incomplete data until its deadline."""
    key = (broker_dt.date(), hour)
    if key in sent_today:
        return False
    # H=16: pure dependency slot — emit as soon as H=6 and H=12 are logged, no signal_dt/entry check.
    if hour == 16 and not is_slot_ready(broker_dt, 16):
        return False
    if hour != 16:
        signal_dt = get_signal_datetime_for_slot(broker_dt, hour)
        if broker_dt < signal_dt:
            return False
        entry_time = get_entry_time_for_slot(broker_dt, hour)
        if broker_dt > get_slot_retry_deadline(broker_dt, hour, entry_time=entry_time):
            print(f"  [MISSED] H={hour} exceeded entry deadline")
            sent_today.add(key)
            _save_state(day_signals, sent_today)
            return False

    entry_time = get_entry_time_for_slot(broker_dt, hour)
    result = calculate_slot_signal(broker_dt, hour)
    signal = result.get("signal")
    if signal not in ("BUY", "SELL") or not entry_time:
        print(f"  [RETRY] H={hour} - {result.get('report', 'incomplete data')}")
        return False

    pair_dirs = get_pair_direction(hour, signal, broker_dt, full_result=result)
    if not pair_dirs:
        print(f"  [RETRY] H={hour} - no pair directions")
        return False
    hour_note = get_hour_note(hour, broker_dt=broker_dt)
    log_signal(
        hour,
        broker_dt,
        signal,
        entry_time,
        pair_dirs,
        hour_note,
        pattern_signal=result.get("pattern_signal"),
        deactivated=result.get("deactivated", False),
    )
    push_to_dashboard()
    reported_pairs = send_report(result, hour, broker_dt)
    _remember_daily_direction(hour, broker_dt, signal, result, reported_pairs)
    sent_today.add(key)
    _save_state(day_signals, sent_today)
    print(f"  [SENT] H={hour} signal={signal} entry={entry_time}")
    return True


def main(profile_name=None):
    global mt5_ready, day_signals, sent_today, _active_profile, _broker_clock_error
    print("=" * 55)
    print("  MT5 Multi-Timeframe Signal Bot v3.18.0")
    print(f"  Symbol: {SYMBOL}")
    print(f"  Target Hours: {', '.join(f'H={h}' for h in TARGET_HOURS)}")
    print(f"  Auto-close: XAUUSD 17:59, GBP 19:59 (Broker)")
    print("  Broker clock: live-tick calibrated, fail-closed")
    print("=" * 55)

    if try_init_mt5():
        info = mt5.account_info()
        if info:
            print(f"  Balance: ${info.balance:,.2f}")
    else:
        print("[WARN] MT5 init failed - signal and auto-close are fail-closed")

    print("=" * 55)
    print("  Dang chay... Ctrl+C de dung")
    print("=" * 55)

    _active_profile = resolve_active_profile(profile_name)

    def heartbeat_thread():
        global _broker_clock_error
        while True:
            heartbeat_broker_dt = None
            if not mt5_ready:
                _broker_clock_error = "MT5 is not connected"
            else:
                try:
                    heartbeat_broker_dt = get_broker_time()
                    _broker_clock_error = ""
                except BrokerClockError as error:
                    _broker_clock_error = str(error)
            try:
                publish_heartbeat(
                    _active_profile,
                    mt5_ready and heartbeat_broker_dt is not None,
                    _broker_clock_error,
                    broker_dt=heartbeat_broker_dt,
                )
            except Exception:
                pass
            time.sleep(2)

    threading.Thread(target=heartbeat_thread, daemon=True).start()

    broker_dt = None
    while broker_dt is None:
        if not mt5_ready:
            try_init_mt5()
        try:
            broker_dt = get_broker_time()
            _broker_clock_error = ""
        except BrokerClockError as error:
            _broker_clock_error = str(error)
            print(f"[BROKER CLOCK] Fail-closed: {error}")
            time.sleep(5)

    # Restore state from previous run (same day only)
    saved = _load_state()
    sent_today = saved.get("sent_today", set())
    day_signals = saved.get("day_signals", {})
    _auto_close_completed.update(
        (broker_dt.date(), category)
        for category in saved.get("auto_close_completed", set())
    )
    _auto_close_pending.clear()
    _auto_close_pending.update(saved.get("auto_close_pending", set()))
    _auto_close_last_alert.clear()
    _auto_close_last_alert.update(saved.get("auto_close_last_alert", {}))

    if day_signals:
        print(f"  [RESTORE] day_signals: {list(day_signals.keys())}")
    if sent_today:
        print(f"  [RESTORE] sent_today: {sent_today}")

    send_telegram(build_startup_telegram_message(broker_dt, mt5_ready))

    # Rebuild signals_log from MT5 before pushing (avoid stale pair_dirs after rule changes)
    startup_rebuilt = rebuild_signals_on_startup()

    # Do not replay live Telegram slots whose publication minute already passed.
    _mark_passed_slots_on_startup(broker_dt)
    _save_state(day_signals, sent_today)

    push_to_dashboard()
    if startup_rebuilt > 0:
        print(f"\n[DASHBOARD] Pushed after rebuild ({startup_rebuilt} slots refreshed)")

    try:
        last_price_push_minute = None
        while True:
            if not mt5_ready:
                try_init_mt5()

            try:
                broker_dt = get_broker_time()
                _broker_clock_error = ""
            except BrokerClockError as error:
                _broker_clock_error = str(error)
                print(f"[BROKER CLOCK] Fail-closed: {error}")
                time.sleep(5)
                continue
            for hour in get_target_hours(broker_dt):
                _process_live_slot(broker_dt, hour)

            price_push_minute = (broker_dt.date(), broker_dt.hour, broker_dt.minute)
            if price_push_minute != last_price_push_minute:
                _save_state(day_signals, sent_today)
                push_state_to_dashboard()
                push_prices_to_dashboard()
                last_price_push_minute = price_push_minute

            _process_auto_closes(broker_dt)
            time.sleep(5)

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
