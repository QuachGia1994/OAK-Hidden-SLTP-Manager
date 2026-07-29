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

SYMBOL = "XAUUSD"
TARGET_HOURS = [3, 4, 7, 9, 12, 14, 16]
ACTIVE_HOURS = frozenset(TARGET_HOURS)
GBP_SOURCE_PAIRS = ("GBPUSD", "GBPAUD")
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
        return "04:00"
    if h == 7:
        return "07:00"
    if h == 9:
        return "09:00"
    if h == 12:
        return "12:00"
    if h == 14:
        return "14:00"
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
SIGNAL_LOGIC_VERSION = 58
SIGNAL_PAIRS = ("XAUUSD", "GBPUSD", "GBPAUD")


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
    """Load restart-safe sent-slot and auto-close state."""
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
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

    today_str = _trading_date().isoformat()
    if data.get("date") != today_str:
        return {"auto_close_pending": pending_closes, "auto_close_last_alert": close_alerts}

    restored_sent = set()
    for raw_date, raw_hour in data.get("sent_today", []):
        try:
            restored_date = datetime.strptime(str(raw_date), "%Y-%m-%d").date()
            restored_sent.add((restored_date, int(raw_hour)))
        except (TypeError, ValueError):
            continue

    return {
        "sent_today": restored_sent,
        "auto_close_completed": set(data.get("auto_close_completed", [])),
        "auto_close_pending": pending_closes,
        "auto_close_last_alert": close_alerts,
    }

def _save_state(sent_today):
    """Persist sent logical slots and pending auto-close obligations."""
    broker_now = get_broker_time()
    today_str = broker_now.date().isoformat()
    sent_rows = [
        [trading_date.isoformat() if hasattr(trading_date, "isoformat") else trading_date, hour]
        for trading_date, hour in sent_today
    ]
    data = {
        "date": today_str,
        "sent_today": sent_rows,
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
    }
    try:
        temporary = _STATE_FILE + ".tmp"
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False)
        os.replace(temporary, _STATE_FILE)
    except Exception as error:
        print(f"[WARN] Cannot save state: {error}")

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


def get_current_prices(pair_dirs):
    """Return current prices only for final tradeable pair directions."""
    prices = {}
    for pair, direction in pair_dirs.items():
        if direction not in ("BUY", "SELL"):
            continue
        try:
            tick = mt5.symbol_info_tick(pair)
            if tick:
                prices[pair] = round(tick.bid, 5)
        except Exception as error:
            log.warning("MT5 tick fetch error for %s: %s", pair, error)
    return prices


def log_signal(H, broker_dt, sig, entry_time, pair_dirs, hour_note,
               pattern_signal=None, deactivated=False, source_date=None, extra_fields=None):
    """Append signal data to signals_log.json for website consumption."""
    deactivated = bool(deactivated or is_deactivated_signal_slot(broker_dt, H))
    current_prices = get_current_prices(pair_dirs) if sig in ("BUY", "SELL") else {}
    if not entry_time:
        entry_time = get_entry_time_for_slot(broker_dt, H)
    signal_time = get_signal_time_for_slot(broker_dt, H)
    record = {
        "date": broker_dt.date().isoformat(),
        "hour": H,
        "ts": datetime.now().timestamp(),
        "signal": sig,
        "signal_time": signal_time,
        "entry_time": entry_time,
        "pair_dirs": pair_dirs,
        "entry_prices": {},
        "current_prices": current_prices,
        "hour_note": hour_note,
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
    if source_date:
        record["source_date"] = source_date
    if extra_fields and isinstance(extra_fields, dict):
        for k, v in extra_fields.items():
            if k not in ("date", "hour", "ts", "signal", "pair_dirs", "signal_time"):
                record[k] = v
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
    try:
        logic_version = int(signal.get("logic_version"))
    except (TypeError, ValueError):
        return False
    if logic_version < SIGNAL_LOGIC_VERSION:
        return False
    pair_dirs = signal.get("pair_dirs")
    if not isinstance(pair_dirs, dict):
        return False
    xauusd_direction = pair_dirs.get("XAUUSD")
    if xauusd_direction not in ("BUY", "SELL", "WAIT"):
        return False
    return signal.get("signal") == xauusd_direction


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
        f"Nguồn: GBPUSD/GBPAUD H1 hôm qua + {SYMBOL} M15 hôm nay | MT5: {mt5_status}\n"
        f"Slots: {', '.join(f'H={h}' for h in TARGET_HOURS)}\n"
        "🔒 Auto-close ALL: XAUUSD 17:59; GBPAUD/GBPCAD/GBPJPY/GBPUSD 19:59 (Broker)\n"
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

    # Keep enough history for prior-day H1 and current M15 lookups.
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

def reverse_candle_direction(direction):
    if direction == "TANG":
        return "GIAM"
    if direction == "GIAM":
        return "TANG"
    return None

def resolve_doji(symbol, timeframe, target_ts, broker_dt):
    """Nến DOJI → lùi 1 nến trước cùng khung (900s for M15).
    For M15: reverse the direction of previous candle (TANG -> GIAM, GIAM -> TANG).
    For H1: keep previous direction if TANG/GIAM.
    """
    timeframe_seconds = {
        mt5.TIMEFRAME_M15: 900,
        mt5.TIMEFRAME_H1: 3600,
    }
    prev_offset = timeframe_seconds.get(timeframe)
    if prev_offset is None:
        return None
    prev_ts = target_ts - prev_offset
    prev_candle = get_candle_by_ts(symbol, timeframe, prev_ts)
    d = candle_direction(prev_candle)
    if timeframe == mt5.TIMEFRAME_M15:
        return reverse_candle_direction(d)
    if d and d != "DOJI":
        return d
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
    """Return whether a Broker Thursday or Friday belongs to a special pair."""
    if broker_dt is None or broker_dt.weekday() not in (3, 4):
        return False
    current = broker_dt.date()
    thursday = current if broker_dt.weekday() == 3 else current - timedelta(days=1)
    friday = thursday + timedelta(days=1)
    if thursday.year != friday.year:
        return False
    return _is_raw_special_day(thursday) or _is_raw_special_day(friday)

def is_post_special_day(broker_dt):
    """Check if today is Monday after a special Thursday."""
    if broker_dt is None:
        return False
    wd = broker_dt.weekday()
    dt = broker_dt.date()
    if wd != 0:
        return False
    prev_thu = dt - timedelta(days=4)
    thu_dt = datetime(prev_thu.year, prev_thu.month, prev_thu.day, tzinfo=broker_dt.tzinfo)
    return is_special_day(thu_dt)


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
    - Months with 5 Fridays: 1st, 2nd and 3rd Friday are special day 2
    - Months with 4 Fridays: 1st and 2nd Friday are special day 2
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
    total = _count_fridays_in_month(dt.year, dt.month)
    if total >= 5:
        return nth in (1, 2, 3)
    else:
        return nth in (1, 2)


def is_month_boundary_suppress(broker_dt):
    """Disabled -- month boundary suppression removed."""
    return False


_THREE_CANDLE_GROUPS = {
    ("TANG", "TANG", "TANG"): "SW",
    ("GIAM", "TANG", "TANG"): "SW",
    ("GIAM", "TANG", "GIAM"): "BT",
    ("GIAM", "GIAM", "TANG"): "BT",
    ("GIAM", "GIAM", "GIAM"): "SW",
    ("TANG", "GIAM", "GIAM"): "SW",
    ("TANG", "GIAM", "TANG"): "BT",
    ("TANG", "TANG", "GIAM"): "BT",
}


def _lookback_candle_direction(symbol, timeframe, candle_dt):
    """Read one completed candle, resolving a DOJI with exactly one older bar."""
    target_ts = broker_time_to_ts(candle_dt, candle_dt.hour, candle_dt.minute)
    direction = candle_direction(get_candle_by_ts(symbol, timeframe, target_ts))
    if direction in ("TANG", "GIAM"):
        return direction
    if direction != "DOJI":
        return None
    resolved = resolve_doji(symbol, timeframe, target_ts, candle_dt)
    return resolved if resolved in ("TANG", "GIAM") else None


def _classify_three_candles(directions):
    """Classify newest-to-oldest directions with the existing SW/BT table."""
    return _THREE_CANDLE_GROUPS.get(tuple(directions))


_previous_session_cache: dict[tuple, object] = {}


def resolve_previous_broker_session(broker_dt, symbol, timeframe):
    """Find the most recent Broker trading session before *broker_dt*.

    Scans backwards up to 7 calendar days, skipping weekends and sessions
    with no data for the given symbol/timeframe. Results are cached per
    (broker_date, symbol, timeframe) within a rebuild pass.

    Returns the session date (``datetime.date``) or ``None`` if no session
    is found within the lookback window.
    """
    cache_key = (broker_dt.date(), symbol, timeframe)
    if cache_key in _previous_session_cache:
        return _previous_session_cache[cache_key]

    candidate = broker_dt.date() - timedelta(days=1)
    for _ in range(7):
        if candidate.weekday() >= 5:
            candidate -= timedelta(days=1)
            continue
        try:
            bars = mt5.copy_rates_from(
                symbol,
                timeframe,
                datetime.combine(candidate, datetime.min.time()).replace(hour=12),
                1,
            )
            if bars is not None and len(bars) > 0:
                _previous_session_cache[cache_key] = candidate
                return candidate
        except Exception:
            pass
        candidate -= timedelta(days=1)

    _previous_session_cache[cache_key] = None
    return None


def candle_direction_to_signal(direction):
    """Convert candle direction 'TANG'/'GIAM' to signal 'BUY'/'SELL'."""
    if direction == "TANG":
        return "BUY"
    if direction == "GIAM":
        return "SELL"
    return None


def apply_offset15_filter(provisional_signal, offset15_direction):
    """Post-process provisional signal against offset -15 candle direction.

    Contract:
    - provisional_signal must be BUY or SELL.
    - offset15_direction must be TANG or GIAM.
    - returns None if inputs are invalid/unresolved.
    """
    if provisional_signal not in ("BUY", "SELL"):
        return None
    offset15_signal = candle_direction_to_signal(offset15_direction)
    if offset15_signal is None:
        return None

    same_direction = (provisional_signal == offset15_signal)
    if same_direction:
        final_signal = reverse_signal(provisional_signal)
        relation = "SAME"
        action = "REVERSE"
    else:
        final_signal = provisional_signal
        relation = "OPPOSITE"
        action = "KEEP"

    return {
        "offset15_direction": offset15_direction,
        "offset15_signal": offset15_signal,
        "relation": relation,
        "action": action,
        "final_signal": final_signal,
    }


def evaluate_symbol_m15_for_slot(broker_dt, hour, symbol):
    """Evaluate 5 M15 candles (offsets -15, -30, -45, -60, -75) from current Broker session for a symbol.

    Offsets:
      -15 = Post-filter candle
      -30 = Base
      -45 = Pattern 1
      -60 = Pattern 2
      -75 = Pattern 3
    """
    h = int(hour)
    if broker_dt is None or h not in ACTIVE_HOURS:
        return None
    source_slot = datetime.combine(broker_dt.date(), datetime.min.time()).replace(hour=h, minute=0)

    # Base (-30) and pattern (-45, -60, -75)
    base_dir = _lookback_candle_direction(symbol, mt5.TIMEFRAME_M15, source_slot - timedelta(minutes=30))
    if base_dir not in ("TANG", "GIAM"):
        return None

    pattern_dirs = [
        _lookback_candle_direction(symbol, mt5.TIMEFRAME_M15, source_slot - timedelta(minutes=offset))
        for offset in (45, 60, 75)
    ]
    if any(d is None or d not in ("TANG", "GIAM") for d in pattern_dirs):
        return None

    pullback_group = _classify_three_candles(pattern_dirs)
    if pullback_group not in ("SW", "BT"):
        return None

    base_signal = "BUY" if base_dir == "TANG" else "SELL"
    pattern_direction = reverse_signal(base_signal) if pullback_group == "SW" else base_signal
    slot_adjusted_direction = reverse_signal(pattern_direction) if h == 14 else pattern_direction
    pre_offset15_direction = slot_adjusted_direction

    # Offset -15 post-filter
    offset15_dt = source_slot - timedelta(minutes=15)
    offset15_direction = _lookback_candle_direction(symbol, mt5.TIMEFRAME_M15, offset15_dt)
    filter_res = apply_offset15_filter(pre_offset15_direction, offset15_direction)
    if filter_res is None:
        return None

    post_offset15_direction = filter_res["final_signal"]

    # Final inversion for GBPUSD at H>=9 (H9, H12, H14, H16)
    if symbol == "GBPUSD" and h >= 9:
        final_direction = reverse_signal(post_offset15_direction)
        gbpusd_h9plus_inversion_applied = True
    else:
        final_direction = post_offset15_direction
        gbpusd_h9plus_inversion_applied = False

    entry_time = f"{h + 1:02d}:25" if pullback_group == "SW" else f"{h:02d}:49"

    return {
        "symbol": symbol,
        "source_date": broker_dt.date().isoformat(),
        "base_direction": base_dir,
        "base_signal": base_signal,
        "pattern_directions": pattern_dirs,
        "matched_pattern": tuple(pattern_dirs),
        "pattern_length": 3,
        "pullback_group": pullback_group,
        "pattern_direction": pattern_direction,
        "slot_adjusted_direction": slot_adjusted_direction,
        "pre_offset15_direction": pre_offset15_direction,
        "offset15_datetime": offset15_dt.isoformat(),
        "offset15_direction": offset15_direction,
        "offset15_signal": filter_res["offset15_signal"],
        "offset15_relation": filter_res["relation"],
        "offset15_action": filter_res["action"],
        "post_offset15_direction": post_offset15_direction,
        "gbpusd_h9plus_inversion_applied": gbpusd_h9plus_inversion_applied,
        "classification_reason": "shared_three_candle_pattern_with_offset15_filter",
        "offsets": [15, 30, 45, 60, 75],
        "direction": final_direction,
        "entry_time": entry_time,
    }


def get_completed_m15_direction_by_close_time(symbol, close_dt):
    """Return the candle direction of an M15 bar that closed at close_dt.

    Bar open time is close_dt - 15 minutes.
    """
    bar_open_dt = close_dt - timedelta(minutes=15)
    return _lookback_candle_direction(symbol, mt5.TIMEFRAME_M15, bar_open_dt)


def compare_signal_directions(left_signal, right_signal):
    """Compare two signals ('BUY'/'SELL'). Return 'SAME', 'OPPOSITE', or None."""
    if left_signal not in ("BUY", "SELL"):
        return None
    if right_signal not in ("BUY", "SELL"):
        return None
    return "SAME" if left_signal == right_signal else "OPPOSITE"


def build_xau_entry_plan(
    broker_dt,
    hour,
    xauusd_signal,
    gbpaud_offset15_direction,
    followup_gbpaud_direction=None,
):
    """Build XAUUSD entry plan based on final XAUUSD signal and GBPAUD candle directions.

    Returns dict with entry_state ('READY', 'PENDING_FOLLOWUP', 'WAIT'), entry_time,
    entry_candidate, entry_rule, and detailed evidence fields.
    """
    h = int(hour)
    if broker_dt is None or h not in ACTIVE_HOURS:
        return {
            "entry_state": "WAIT",
            "entry_time": None,
            "entry_candidate": None,
            "entry_rule": "INVALID_SLOT",
            "entry_xauusd_signal": xauusd_signal,
            "entry_gbpaud_offset15_direction": gbpaud_offset15_direction,
            "entry_gbpaud_offset15_signal": None,
            "entry_initial_relation": None,
            "entry_followup_required": False,
            "entry_followup_close_time": None,
            "entry_followup_bar_open_time": None,
            "entry_followup_direction": None,
            "entry_followup_signal": None,
            "entry_followup_relation": None,
            "entry_decided_at": None,
        }

    gbpaud_offset15_signal = candle_direction_to_signal(gbpaud_offset15_direction)
    initial_relation = compare_signal_directions(xauusd_signal, gbpaud_offset15_signal)

    if xauusd_signal not in ("BUY", "SELL") or initial_relation is None:
        return {
            "entry_state": "WAIT",
            "entry_time": None,
            "entry_candidate": None,
            "entry_rule": "MISSING_INITIAL_DATA",
            "entry_xauusd_signal": xauusd_signal,
            "entry_gbpaud_offset15_direction": gbpaud_offset15_direction,
            "entry_gbpaud_offset15_signal": gbpaud_offset15_signal,
            "entry_initial_relation": initial_relation,
            "entry_followup_required": False,
            "entry_followup_close_time": None,
            "entry_followup_bar_open_time": None,
            "entry_followup_direction": None,
            "entry_followup_signal": None,
            "entry_followup_relation": None,
            "entry_decided_at": None,
        }

    source_slot = datetime.combine(broker_dt.date(), datetime.min.time()).replace(hour=h, minute=0)
    followup_close_dt = source_slot.replace(minute=45)
    followup_open_dt = source_slot.replace(minute=30)
    followup_close_iso = followup_close_dt.isoformat()
    followup_open_iso = followup_open_dt.isoformat()

    if h == 3:
        if initial_relation == "SAME":
            return {
                "entry_state": "READY",
                "entry_time": "03:11",
                "entry_candidate": "03:11",
                "entry_rule": "H3_SAME",
                "entry_xauusd_signal": xauusd_signal,
                "entry_gbpaud_offset15_direction": gbpaud_offset15_direction,
                "entry_gbpaud_offset15_signal": gbpaud_offset15_signal,
                "entry_initial_relation": initial_relation,
                "entry_followup_required": False,
                "entry_followup_close_time": None,
                "entry_followup_bar_open_time": None,
                "entry_followup_direction": None,
                "entry_followup_signal": None,
                "entry_followup_relation": None,
                "entry_decided_at": source_slot.isoformat(),
            }
        else:  # OPPOSITE
            if followup_gbpaud_direction is None:
                return {
                    "entry_state": "PENDING_FOLLOWUP",
                    "entry_time": None,
                    "entry_candidate": "03:49",
                    "entry_rule": "H3_PENDING_0345",
                    "entry_xauusd_signal": xauusd_signal,
                    "entry_gbpaud_offset15_direction": gbpaud_offset15_direction,
                    "entry_gbpaud_offset15_signal": gbpaud_offset15_signal,
                    "entry_initial_relation": initial_relation,
                    "entry_followup_required": True,
                    "entry_followup_close_time": followup_close_iso,
                    "entry_followup_bar_open_time": followup_open_iso,
                    "entry_followup_direction": None,
                    "entry_followup_signal": None,
                    "entry_followup_relation": None,
                    "entry_decided_at": None,
                }
            followup_signal = candle_direction_to_signal(followup_gbpaud_direction)
            followup_rel = compare_signal_directions(xauusd_signal, followup_signal)
            if followup_rel is None:
                return {
                    "entry_state": "WAIT",
                    "entry_time": None,
                    "entry_candidate": "03:49",
                    "entry_rule": "H3_FOLLOWUP_UNRESOLVED",
                    "entry_xauusd_signal": xauusd_signal,
                    "entry_gbpaud_offset15_direction": gbpaud_offset15_direction,
                    "entry_gbpaud_offset15_signal": gbpaud_offset15_signal,
                    "entry_initial_relation": initial_relation,
                    "entry_followup_required": True,
                    "entry_followup_close_time": followup_close_iso,
                    "entry_followup_bar_open_time": followup_open_iso,
                    "entry_followup_direction": followup_gbpaud_direction,
                    "entry_followup_signal": followup_signal,
                    "entry_followup_relation": None,
                    "entry_decided_at": None,
                }
            final_entry = "04:49" if followup_rel == "OPPOSITE" else "03:49"
            rule_name = "H3_OPPOSITE_THEN_OPPOSITE" if followup_rel == "OPPOSITE" else "H3_OPPOSITE_THEN_SAME"
            return {
                "entry_state": "READY",
                "entry_time": final_entry,
                "entry_candidate": final_entry,
                "entry_rule": rule_name,
                "entry_xauusd_signal": xauusd_signal,
                "entry_gbpaud_offset15_direction": gbpaud_offset15_direction,
                "entry_gbpaud_offset15_signal": gbpaud_offset15_signal,
                "entry_initial_relation": initial_relation,
                "entry_followup_required": True,
                "entry_followup_close_time": followup_close_iso,
                "entry_followup_bar_open_time": followup_open_iso,
                "entry_followup_direction": followup_gbpaud_direction,
                "entry_followup_signal": followup_signal,
                "entry_followup_relation": followup_rel,
                "entry_decided_at": followup_close_iso,
            }

    elif h == 7:
        if initial_relation == "SAME":
            return {
                "entry_state": "READY",
                "entry_time": "07:11",
                "entry_candidate": "07:11",
                "entry_rule": "H7_SAME",
                "entry_xauusd_signal": xauusd_signal,
                "entry_gbpaud_offset15_direction": gbpaud_offset15_direction,
                "entry_gbpaud_offset15_signal": gbpaud_offset15_signal,
                "entry_initial_relation": initial_relation,
                "entry_followup_required": False,
                "entry_followup_close_time": None,
                "entry_followup_bar_open_time": None,
                "entry_followup_direction": None,
                "entry_followup_signal": None,
                "entry_followup_relation": None,
                "entry_decided_at": source_slot.isoformat(),
            }
        else:  # OPPOSITE
            if followup_gbpaud_direction is None:
                return {
                    "entry_state": "PENDING_FOLLOWUP",
                    "entry_time": None,
                    "entry_candidate": "07:49",
                    "entry_rule": "H7_PENDING_0745",
                    "entry_xauusd_signal": xauusd_signal,
                    "entry_gbpaud_offset15_direction": gbpaud_offset15_direction,
                    "entry_gbpaud_offset15_signal": gbpaud_offset15_signal,
                    "entry_initial_relation": initial_relation,
                    "entry_followup_required": True,
                    "entry_followup_close_time": followup_close_iso,
                    "entry_followup_bar_open_time": followup_open_iso,
                    "entry_followup_direction": None,
                    "entry_followup_signal": None,
                    "entry_followup_relation": None,
                    "entry_decided_at": None,
                }
            followup_signal = candle_direction_to_signal(followup_gbpaud_direction)
            followup_rel = compare_signal_directions(xauusd_signal, followup_signal)
            if followup_rel is None:
                return {
                    "entry_state": "WAIT",
                    "entry_time": None,
                    "entry_candidate": "07:49",
                    "entry_rule": "H7_FOLLOWUP_UNRESOLVED",
                    "entry_xauusd_signal": xauusd_signal,
                    "entry_gbpaud_offset15_direction": gbpaud_offset15_direction,
                    "entry_gbpaud_offset15_signal": gbpaud_offset15_signal,
                    "entry_initial_relation": initial_relation,
                    "entry_followup_required": True,
                    "entry_followup_close_time": followup_close_iso,
                    "entry_followup_bar_open_time": followup_open_iso,
                    "entry_followup_direction": followup_gbpaud_direction,
                    "entry_followup_signal": followup_signal,
                    "entry_followup_relation": None,
                    "entry_decided_at": None,
                }
            final_entry = "08:25" if followup_rel == "OPPOSITE" else "07:49"
            rule_name = "H7_OPPOSITE_THEN_OPPOSITE" if followup_rel == "OPPOSITE" else "H7_OPPOSITE_THEN_SAME"
            return {
                "entry_state": "READY",
                "entry_time": final_entry,
                "entry_candidate": final_entry,
                "entry_rule": rule_name,
                "entry_xauusd_signal": xauusd_signal,
                "entry_gbpaud_offset15_direction": gbpaud_offset15_direction,
                "entry_gbpaud_offset15_signal": gbpaud_offset15_signal,
                "entry_initial_relation": initial_relation,
                "entry_followup_required": True,
                "entry_followup_close_time": followup_close_iso,
                "entry_followup_bar_open_time": followup_open_iso,
                "entry_followup_direction": followup_gbpaud_direction,
                "entry_followup_signal": followup_signal,
                "entry_followup_relation": followup_rel,
                "entry_decided_at": followup_close_iso,
            }

    else:  # H >= 9 (H9, H12, H14, H16)
        h_str = f"{h:02d}"
        if initial_relation == "OPPOSITE":
            entry_t = f"{h_str}:11"
            return {
                "entry_state": "READY",
                "entry_time": entry_t,
                "entry_candidate": entry_t,
                "entry_rule": "H9PLUS_OPPOSITE",
                "entry_xauusd_signal": xauusd_signal,
                "entry_gbpaud_offset15_direction": gbpaud_offset15_direction,
                "entry_gbpaud_offset15_signal": gbpaud_offset15_signal,
                "entry_initial_relation": initial_relation,
                "entry_followup_required": False,
                "entry_followup_close_time": None,
                "entry_followup_bar_open_time": None,
                "entry_followup_direction": None,
                "entry_followup_signal": None,
                "entry_followup_relation": None,
                "entry_decided_at": source_slot.isoformat(),
            }
        else:  # SAME
            cand_t = f"{h_str}:49"
            if followup_gbpaud_direction is None:
                return {
                    "entry_state": "PENDING_FOLLOWUP",
                    "entry_time": None,
                    "entry_candidate": cand_t,
                    "entry_rule": f"H9PLUS_PENDING_{h_str}45",
                    "entry_xauusd_signal": xauusd_signal,
                    "entry_gbpaud_offset15_direction": gbpaud_offset15_direction,
                    "entry_gbpaud_offset15_signal": gbpaud_offset15_signal,
                    "entry_initial_relation": initial_relation,
                    "entry_followup_required": True,
                    "entry_followup_close_time": followup_close_iso,
                    "entry_followup_bar_open_time": followup_open_iso,
                    "entry_followup_direction": None,
                    "entry_followup_signal": None,
                    "entry_followup_relation": None,
                    "entry_decided_at": None,
                }
            followup_signal = candle_direction_to_signal(followup_gbpaud_direction)
            followup_rel = compare_signal_directions(xauusd_signal, followup_signal)
            if followup_rel is None:
                return {
                    "entry_state": "WAIT",
                    "entry_time": None,
                    "entry_candidate": cand_t,
                    "entry_rule": "H9PLUS_FOLLOWUP_UNRESOLVED",
                    "entry_xauusd_signal": xauusd_signal,
                    "entry_gbpaud_offset15_direction": gbpaud_offset15_direction,
                    "entry_gbpaud_offset15_signal": gbpaud_offset15_signal,
                    "entry_initial_relation": initial_relation,
                    "entry_followup_required": True,
                    "entry_followup_close_time": followup_close_iso,
                    "entry_followup_bar_open_time": followup_open_iso,
                    "entry_followup_direction": followup_gbpaud_direction,
                    "entry_followup_signal": followup_signal,
                    "entry_followup_relation": None,
                    "entry_decided_at": None,
                }
            final_entry = f"{h + 1:02d}:25" if followup_rel == "SAME" else f"{h_str}:49"
            rule_name = "H9PLUS_SAME_THEN_SAME" if followup_rel == "SAME" else "H9PLUS_SAME_THEN_OPPOSITE"
            return {
                "entry_state": "READY",
                "entry_time": final_entry,
                "entry_candidate": final_entry,
                "entry_rule": rule_name,
                "entry_xauusd_signal": xauusd_signal,
                "entry_gbpaud_offset15_direction": gbpaud_offset15_direction,
                "entry_gbpaud_offset15_signal": gbpaud_offset15_signal,
                "entry_initial_relation": initial_relation,
                "entry_followup_required": True,
                "entry_followup_close_time": followup_close_iso,
                "entry_followup_bar_open_time": followup_open_iso,
                "entry_followup_direction": followup_gbpaud_direction,
                "entry_followup_signal": followup_signal,
                "entry_followup_relation": followup_rel,
                "entry_decided_at": followup_close_iso,
            }


def can_resolve_entry_followup(slot_dt, as_of_dt=None, historical_complete=False):
    """Return True if the GBPAUD H:45 follow-up candle is available for entry resolution.

    A. Past dates: historical_complete=True → always resolve.
    B. Today before H:45: as_of_dt < H:45 → keep PENDING_FOLLOWUP.
    C. Today from H:45: as_of_dt >= H:45 → resolve READY/WAIT.
    """
    if historical_complete:
        return True
    if as_of_dt is None:
        return False
    followup_close_dt = slot_dt.replace(minute=45, second=0, microsecond=0)
    return as_of_dt >= followup_close_dt


ENTRY_PLAN_FIELDS = (
    "entry_state",
    "entry_candidate",
    "entry_rule",
    "entry_xauusd_signal",
    "entry_gbpaud_offset15_direction",
    "entry_gbpaud_offset15_signal",
    "entry_initial_relation",
    "entry_followup_required",
    "entry_followup_close_time",
    "entry_followup_bar_open_time",
    "entry_followup_direction",
    "entry_followup_signal",
    "entry_followup_relation",
    "entry_decided_at",
    "pair_entry_times",
    "pair_groups",
    "pair_evidence",
)


def evaluate_all_pairs_for_slot(broker_dt, hour, check_followup=False,
                                as_of_dt=None, resolve_historical_followup=False):
    """Evaluate XAUUSD, GBPUSD, and GBPAUD M15 signals independently for current Broker date.

    broker_dt: determines the logical slot date and hour (e.g. 2026-07-28 12:00).
    as_of_dt:  determines the "current time" for follow-up availability.
               Live mode: use BrokerClock current time.
               Rebuild past: leave None (historical_complete handles it).
    resolve_historical_followup: True for past-date rebuilds → always read H:45 candle.
    """
    h = int(hour)
    if broker_dt is None or h not in ACTIVE_HOURS:
        return None

    pair_results = {}
    for symbol in SIGNAL_PAIRS:
        pair_results[symbol] = evaluate_symbol_m15_for_slot(broker_dt, h, symbol)

    pair_dirs = {}
    pair_pre_offset15_dirs = {}
    pair_offset15_dirs = {}
    pair_offset15_relations = {}
    pair_offset15_actions = {}
    pair_entry_times = {}
    pair_groups = {}
    pair_evidence = {}

    for symbol in SIGNAL_PAIRS:
        res = pair_results[symbol]
        if res is None:
            pair_dirs[symbol] = "WAIT"
            pair_pre_offset15_dirs[symbol] = "WAIT"
            pair_offset15_dirs[symbol] = None
            pair_offset15_relations[symbol] = None
            pair_offset15_actions[symbol] = None
            pair_entry_times[symbol] = None
            pair_groups[symbol] = None
            pair_evidence[symbol] = None
        else:
            pair_dirs[symbol] = res["direction"]
            pair_pre_offset15_dirs[symbol] = res["pre_offset15_direction"]
            pair_offset15_dirs[symbol] = res["offset15_direction"]
            pair_offset15_relations[symbol] = res["offset15_relation"]
            pair_offset15_actions[symbol] = res["offset15_action"]
            pair_entry_times[symbol] = None  # XAUUSD entry is assigned below via entry planner
            pair_groups[symbol] = res["pullback_group"]
            pair_evidence[symbol] = res

    gbpaud_off15_dir = pair_offset15_dirs.get("GBPAUD")
    followup_dir = None
    source_slot = datetime.combine(broker_dt.date(), datetime.min.time()).replace(hour=h, minute=0)

    if can_resolve_entry_followup(source_slot, as_of_dt=as_of_dt,
                                  historical_complete=resolve_historical_followup):
        followup_close_dt = source_slot.replace(minute=45)
        followup_dir = get_completed_m15_direction_by_close_time("GBPAUD", followup_close_dt)

    entry_plan = build_xau_entry_plan(
        broker_dt,
        h,
        pair_dirs.get("XAUUSD", "WAIT"),
        gbpaud_off15_dir,
        followup_gbpaud_direction=followup_dir,
    )

    top_signal = pair_dirs.get("XAUUSD", "WAIT")
    if entry_plan["entry_state"] == "WAIT":
        top_signal = "WAIT"
        pair_dirs["XAUUSD"] = "WAIT"

    final_xau_entry = entry_plan["entry_time"]
    pair_entry_times["XAUUSD"] = final_xau_entry

    source_date_str = broker_dt.date().isoformat()

    report_lines = [f"H={h} M15 ({source_date_str}) [v{SIGNAL_LOGIC_VERSION}]:"]
    for symbol in SIGNAL_PAIRS:
        res = pair_results[symbol]
        if res is None:
            report_lines.append(f"  {symbol}: WAIT (missing M15 candle data)")
        else:
            report_lines.append(
                f"  {symbol}: base={res['base_direction']}/{res['base_signal']} "
                f"pattern={','.join(res['pattern_directions'])} group={res['pullback_group']} "
                f"pattern_dir={res['pattern_direction']} slot_adj={res['slot_adjusted_direction']} "
                f"offset15={res['offset15_direction']}/{res['offset15_signal']} "
                f"relation={res['offset15_relation']} action={res['offset15_action']} "
                f"final={res['direction']}"
            )
    report_lines.append(
        f"  XAUUSD Entry Plan: state={entry_plan['entry_state']} time={entry_plan['entry_time']} "
        f"candidate={entry_plan['entry_candidate']} rule={entry_plan['entry_rule']}"
    )

    res_dict = {
        "logic_version": SIGNAL_LOGIC_VERSION,
        "signal": top_signal,
        "entry_time": final_xau_entry,
        "pair_dirs": pair_dirs,
        "pair_pre_offset15_dirs": pair_pre_offset15_dirs,
        "pair_offset15_dirs": pair_offset15_dirs,
        "pair_offset15_relations": pair_offset15_relations,
        "pair_offset15_actions": pair_offset15_actions,
        "pair_entry_times": pair_entry_times,
        "pair_groups": pair_groups,
        "pair_evidence": pair_evidence,
        "source_date": source_date_str,
        "report": "\n".join(report_lines),
    }
    res_dict.update(entry_plan)
    return res_dict


evaluate_multi_pair_m15_slot = evaluate_all_pairs_for_slot
evaluate_gbp_h1_slot = evaluate_all_pairs_for_slot


def is_deactivated_signal_slot(broker_dt, hour):
    """Return whether a calculated slot is dependency-only and must not be traded."""
    if broker_dt is None:
        return False
    h = int(hour)
    if h == 4:
        return True
    if h == 3 and broker_dt.weekday() == 3:
        return True
    return False


def get_entry_time_for_slot(broker_dt, hour):
    """Calculate the Broker entry clock for one logical slot."""
    h = int(hour)
    if broker_dt is None or h not in ACTIVE_HOURS:
        return None
    result = evaluate_gbp_h1_slot(broker_dt, h)
    return result.get("entry_time") if result else None


def get_slot_retry_deadline(broker_dt, hour, entry_time=None):
    """Return the last Broker datetime at which a live slot may be emitted."""
    h = int(hour)
    fallback_clocks = {
        3: "04:49",
        4: "05:25",
        7: "08:25",
        9: "10:25",
        12: "13:25",
        14: "15:25",
        16: "17:25",
    }
    clock = entry_time if (entry_time and ":" in str(entry_time)) else None
    if not clock:
        try:
            clock = get_entry_time_for_slot(broker_dt, h)
        except Exception:
            clock = None
    if not clock or ":" not in str(clock):
        clock = fallback_clocks.get(h, "17:25")

    deadline_hour, deadline_minute = (int(part) for part in str(clock).split(":"))
    deadline = broker_dt.replace(
        hour=deadline_hour,
        minute=deadline_minute,
        second=0,
        microsecond=0,
    )
    return deadline


def calculate_slot_signal(broker_dt, hour, as_of_dt=None):
    """Apply current M15 multi-pair evaluation for live and rebuilt signals.

    as_of_dt: current time for follow-up availability. Defaults to broker_dt.
    """
    hour = int(hour)
    if hour not in ACTIVE_HOURS:
        return {
            "signal": "WAIT",
            "report": f"H={hour}: inactive slot.",
            "suppressed": True,
        }
    result = evaluate_gbp_h1_slot(broker_dt, hour, as_of_dt=as_of_dt or broker_dt)
    if result is None:
        return {
            "signal": "WAIT",
            "report": f"H={hour}: incomplete M15 candle data.",
        }
    if is_deactivated_signal_slot(broker_dt, hour):
        result["deactivated"] = True
    return result


def get_hour_note(H, broker_dt=None):
    """Describe the current slot rule."""
    try:
        h = int(H)
    except (TypeError, ValueError):
        return ""
    if h not in ACTIVE_HOURS:
        return ""
    return (
        "XAUUSD, GBPUSD, GBPAUD M15 (current date): base (-30) + 3 pattern (-45/-60/-75). "
        "SW → reverse base; BT → keep base. "
        "DOJI M15 → step back 1 M15 and reverse previous direction. "
        "Entry: SW → H+1:25, BT → H:49."
    )


def format_telegram_pair_block(pair_dirs, H, broker_dt=None, weekday=None):
    """Render XAUUSD, GBPUSD, and GBPAUD pair directions for Telegram."""
    lines = []
    for pair in SIGNAL_PAIRS:
        direction = (pair_dirs or {}).get(pair)
        if direction in ("BUY", "SELL"):
            icon, _ = get_signal_icon(direction)
            lines.append(f"  {pair}: {icon} {direction}")
        else:
            lines.append(f"  {pair}: WAIT")
    return "\n".join(lines) if lines else "  (no pair)"


GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPJPY", "GBPUSD"]
ALL_PAIRS = ["XAUUSD"] + GBP_PAIRS

sent_today = set()


def reverse_signal(signal):
    """Return the opposite trading direction."""
    if signal == "BUY":
        return "SELL"
    if signal == "SELL":
        return "BUY"
    return None


def get_pair_direction(H, signal, broker_dt, full_result=None):
    """Return the final pair directions for one active slot."""
    result = {}
    h = int(H)
    if h not in ACTIVE_HOURS:
        return result
    if signal not in ("BUY", "SELL", "WAIT"):
        return {}
    pair_dirs = (full_result or {}).get("pair_dirs", {})
    for pair in SIGNAL_PAIRS:
        result[pair] = pair_dirs.get(pair, "WAIT" if signal == "WAIT" else (signal if pair == "XAUUSD" else "WAIT"))
    return result

# =====================================================================
# GUI TELEGRAM BAO CAO
# =====================================================================
def send_report(signal_data, H, broker_dt):
    sig = signal_data["signal"]
    report = signal_data["report"]
    icon, emoji = get_signal_icon(sig)
    hour_note = get_hour_note(H, broker_dt=broker_dt)
    note_line = f"📝 {hour_note}\n" if hour_note else ""
    pair_dirs = get_pair_direction(
        H,
        sig,
        broker_dt,
        full_result=signal_data
    )

    pair_text = format_telegram_pair_block(pair_dirs, H, broker_dt)
    signal_time = get_signal_time_for_slot(broker_dt, H)
    entry_time = signal_data.get("entry_time") or get_entry_time_for_slot(broker_dt, H) or "N/A"
    deactivated = bool(
        signal_data.get("deactivated") or is_deactivated_signal_slot(broker_dt, H)
    )
    if deactivated:
        h = int(H)
        if h == 4:
            reason = "SLOT TRUNG GIAN CHỈ DÙNG ĐỂ TÍNH TOÁN"
        elif h == 3 and broker_dt.weekday() == 3:
            reason = "H=3 THỨ NĂM CHỈ DÙNG ĐỂ ĐỐI CHIẾU"
        else:
            reason = "SLOT DEACTIVATED"
        send_telegram(
            f"H={H} — DEACTIVATED\n"
            "============================\n"
            f"{reason}\n"
            f"Phát: {signal_time} Broker\n"
            f"Mốc entry tham chiếu: {entry_time} Broker\n"
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
        f"Vào lệnh: {entry_time} Broker\n"
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
    return broker_dt >= get_signal_datetime_for_slot(broker_dt, h)


# =====================================================================
# REBUILD: tính lại signals_log từ MT5 khi bot khởi động (tránh push data cũ)
# =====================================================================
def rebuild_slot_signal(broker_dt, h, *, as_of_dt=None, historical_complete=False):
    """Recalculate one slot with current logic and overwrite signals_log (date, hour).
    Always logs the result -- including WAIT and deactivated slots -- so the dashboard
    shows every scheduled hour.

    as_of_dt: current time for follow-up availability. Past dates use historical_complete.
    historical_complete: True for past dates → always resolve H:45 follow-up.
    """
    if broker_dt.weekday() >= 5:
        return False

    result = evaluate_all_pairs_for_slot(
        broker_dt, h,
        as_of_dt=as_of_dt,
        resolve_historical_followup=historical_complete,
    )
    if result is None:
        result = calculate_slot_signal(broker_dt, h, as_of_dt=as_of_dt)

    sig = result.get("signal")
    entry_time = result.get("entry_time")
    source_date = result.get("source_date")
    pair_dirs = result.get("pair_dirs", {})
    if not pair_dirs and sig not in ("WAIT",):
        pair_dirs = get_pair_direction(h, sig, broker_dt, full_result=result)
    if sig == "WAIT" and not pair_dirs:
        pair_dirs = {"XAUUSD": "WAIT", "GBPUSD": "WAIT", "GBPAUD": "WAIT"}
    hour_note = get_hour_note(h, broker_dt=broker_dt)
    deactivated = bool(result.get("deactivated") or is_deactivated_signal_slot(broker_dt, h))

    extra_fields = {
        key: result.get(key)
        for key in ENTRY_PLAN_FIELDS
        if key in result
    }
    log_signal(h, broker_dt, sig or "WAIT", entry_time, pair_dirs or {}, hour_note,
               pattern_signal=result.get("pattern_signal"),
               deactivated=deactivated,
               source_date=source_date,
               extra_fields=extra_fields if extra_fields else None)
    return True


def rebuild_recent_history(days=45):
    """Recalculate recent sessions with the current GBP H1 / XAU M15 logic."""
    if not mt5_ready:
        print("  [REBUILD] MT5 not ready, skip")
        return 0

    # Clear session cache so rebuild sees fresh MT5 data.
    _previous_session_cache.clear()

    broker_dt = get_broker_time()
    today = broker_dt.date()
    dates = [today - timedelta(days=i) for i in range(days)]
    try:
        data = []
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as file:
                data = json.load(file)
        # Replace the recent window entirely so stale/old slot rows do not survive.
        rebuild_dates = {target_date.isoformat() for target_date in dates if target_date.weekday() < 5}
        filtered = []
        for record in data if isinstance(data, list) else []:
            if not isinstance(record, dict):
                continue
            try:
                record_hour = int(record.get("hour", -1))
            except (TypeError, ValueError):
                continue
            if record.get("date") not in rebuild_dates and record_hour in ACTIVE_HOURS:
                filtered.append(record)
        _write_signals_log_atomic(filtered)
    except Exception as error:
        print(f"  [REBUILD] Cannot clear stale history: {error}")

    rebuilt = 0
    for target_date in reversed(dates):
        if target_date.weekday() >= 5:
            continue
        hours = get_target_hours(datetime.combine(target_date, datetime.min.time()))
        for hour in hours:
            # Today's future publication windows are not rebuilt yet.
            if target_date == today and not is_slot_ready(broker_dt, hour):
                continue
            slot_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=hour)
            historical_complete = target_date < today
            try:
                if rebuild_slot_signal(slot_dt, hour,
                                       as_of_dt=broker_dt,
                                       historical_complete=historical_complete):
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
        target_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=4)
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
    if (broker_dt.hour, broker_dt.minute) < (4, 0):
        cursor -= timedelta(days=1)
    dates = []
    while len(dates) < remaining:
        if cursor.weekday() < 5:
            dates.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(dates))


def rebuild_signals_on_startup():
    """Startup hook that refreshes recent history using the active slot logic."""
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
        _save_state(sent_today)
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
        _save_state(sent_today)
        if outcome["attempted"]:
            send_telegram(
                f"🔒 Đã đóng ALL {category.upper()}: "
                f"{outcome['closed']}/{outcome['attempted']} lệnh lúc {cutoff[0]:02d}:{cutoff[1]:02d} Broker"
            )
        return
    last_alert = _auto_close_last_alert.get(key)
    if last_alert is None or (broker_dt - last_alert).total_seconds() >= 900:
        _auto_close_last_alert[key] = broker_dt
        _save_state(sent_today)
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
    """Suppress catch-up Telegram sends for publication minutes already passed.

    Only mark a slot as sent if its entry is already resolved (READY or WAIT).
    PENDING_FOLLOWUP slots must NOT be marked sent — the live loop needs to
    resolve their follow-up candles and update entry_time.
    """
    for hour in get_target_hours(broker_dt):
        signal_dt = get_signal_datetime_for_slot(broker_dt, hour)
        if broker_dt < signal_dt:
            continue
        # Check if this slot's entry is already resolved
        slot_dt = datetime.combine(broker_dt.date(), datetime.min.time()).replace(hour=hour)
        result = evaluate_all_pairs_for_slot(
            slot_dt, hour,
            as_of_dt=broker_dt,
            resolve_historical_followup=False,
        )
        if result is None:
            result = calculate_slot_signal(broker_dt, hour, as_of_dt=broker_dt)
        entry_state = result.get("entry_state") if result else None
        if entry_state == "PENDING_FOLLOWUP":
            print(f"  [STARTUP] H={hour} pending follow-up — not marking sent")
            continue
        if entry_state == "READY" or result.get("signal") == "WAIT":
            sent_today.add((broker_dt.date(), hour))


def _process_live_slot(broker_dt, hour):
    """Publish one due logical slot, retrying incomplete data until its deadline.

    Handles three states:
    - PENDING_FOLLOWUP: log signal without entry, keep retrying until follow-up resolves.
    - READY: log signal with entry, send Telegram, mark sent.
    - WAIT: keep retrying until deadline.
    """
    key = (broker_dt.date(), hour)
    if key in sent_today:
        return False
    signal_dt = get_signal_datetime_for_slot(broker_dt, hour)
    if broker_dt < signal_dt:
        return False

    result = calculate_slot_signal(broker_dt, hour)
    if not result:
        print(f"  [RETRY] H={hour} - no evaluation result")
        return False

    entry_state = result.get("entry_state")
    signal = result.get("signal")
    entry_time = result.get("entry_time")

    if entry_state == "PENDING_FOLLOWUP":
        pair_dirs = get_pair_direction(hour, signal, broker_dt, full_result=result)
        hour_note = get_hour_note(hour, broker_dt=broker_dt)
        extra_fields = {
            key_: result.get(key_)
            for key_ in ENTRY_PLAN_FIELDS
            if key_ in result
        }
        log_signal(
            hour, broker_dt, signal, None, pair_dirs, hour_note,
            pattern_signal=result.get("pattern_signal"),
            deactivated=result.get("deactivated", False),
            extra_fields=extra_fields if extra_fields else None,
        )
        push_to_dashboard()
        print(f"  [PENDING] H={hour} signal={signal} candidate={result.get('entry_candidate')} rule={result.get('entry_rule')}")
        return False

    if broker_dt > get_slot_retry_deadline(broker_dt, hour, entry_time=entry_time):
        print(f"  [MISSED] H={hour} exceeded entry deadline")
        sent_today.add(key)
        _save_state(sent_today)
        return False

    if signal not in ("BUY", "SELL") or not entry_time or entry_state != "READY":
        print(f"  [RETRY] H={hour} - {result.get('report', 'incomplete data')}")
        return False

    pair_dirs = get_pair_direction(hour, signal, broker_dt, full_result=result)
    if not pair_dirs:
        print(f"  [RETRY] H={hour} - no pair directions")
        return False
    hour_note = get_hour_note(hour, broker_dt=broker_dt)
    extra_fields = {
        key_: result.get(key_)
        for key_ in ENTRY_PLAN_FIELDS
        if key_ in result
    }
    log_signal(
        hour, broker_dt, signal, entry_time, pair_dirs, hour_note,
        pattern_signal=result.get("pattern_signal"),
        deactivated=result.get("deactivated", False),
        extra_fields=extra_fields if extra_fields else None,
    )
    push_to_dashboard()
    send_report(result, hour, broker_dt)
    sent_today.add(key)
    _save_state(sent_today)
    print(f"  [SENT] H={hour} signal={signal} entry={entry_time}")
    return True


def main(profile_name=None):
    global mt5_ready, sent_today, _active_profile, _broker_clock_error
    print("=" * 55)
    print("  MT5 Multi-Timeframe Signal Bot v3.18.2")
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
    _auto_close_completed.update(
        (broker_dt.date(), category)
        for category in saved.get("auto_close_completed", set())
    )
    _auto_close_pending.clear()
    _auto_close_pending.update(saved.get("auto_close_pending", set()))
    _auto_close_last_alert.clear()
    _auto_close_last_alert.update(saved.get("auto_close_last_alert", {}))

    if sent_today:
        print(f"  [RESTORE] sent_today: {sent_today}")

    send_telegram(build_startup_telegram_message(broker_dt, mt5_ready))

    # Rebuild signals_log from MT5 before pushing (avoid stale pair_dirs after rule changes)
    startup_rebuilt = rebuild_signals_on_startup()

    push_to_dashboard()
    if startup_rebuilt > 0:
        print(f"\n[DASHBOARD] Pushed after rebuild ({startup_rebuilt} slots refreshed)")

    try:
        last_price_push_minute = None
        startup_slots_marked = False
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
            if not startup_slots_marked:
                # Rebuild can cross a publication boundary; guard from a fresh
                # Broker clock so restart never replays a slot that just passed.
                _mark_passed_slots_on_startup(broker_dt)
                _save_state(sent_today)
                startup_slots_marked = True
            for hour in get_target_hours(broker_dt):
                _process_live_slot(broker_dt, hour)

            price_push_minute = (broker_dt.date(), broker_dt.hour, broker_dt.minute)
            if price_push_minute != last_price_push_minute:
                _save_state(sent_today)
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
