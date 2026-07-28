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
TARGET_HOURS = [3, 4, 6, 9, 12, 14, 16]
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
    if h == 6:
        return "06:00"
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
# Bump when pair-direction / slot rules change to trace rebuilds in logs.
SIGNAL_LOGIC_VERSION = 52


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
               pattern_signal=None, deactivated=False, source_date=None):
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

def resolve_doji(symbol, timeframe, target_ts, broker_dt):
    """Nến DOJI → lùi 1 nến trước cùng khung, lấy direction nến trước đó."""
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
    """Disabled — month boundary suppression removed. XAUUSD always uses normal signal."""
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


def evaluate_previous_day_gbp_h1_pair(broker_dt, hour, symbol):
    """Derive one XAU direction from the previous session's two completed GBP H1 bars."""
    if broker_dt is None:
        return None
    prev_session = resolve_previous_broker_session(broker_dt, symbol, mt5.TIMEFRAME_H1)
    if prev_session is None:
        return None
    previous_slot_dt = datetime.combine(prev_session, datetime.min.time()).replace(hour=int(hour), minute=0)
    newest_dt = previous_slot_dt - timedelta(hours=1)
    older_dt = previous_slot_dt - timedelta(hours=2)
    newest_direction = _lookback_candle_direction(symbol, mt5.TIMEFRAME_H1, newest_dt)
    older_direction = _lookback_candle_direction(symbol, mt5.TIMEFRAME_H1, older_dt)
    if newest_direction not in ("TANG", "GIAM") or older_direction not in ("TANG", "GIAM"):
        return None
    base_signal = "BUY" if newest_direction == "TANG" else "SELL"
    group = "SW" if newest_direction == older_direction else "BT"
    derived_signal = reverse_signal(base_signal) if group == "SW" else base_signal
    return {
        "newest_direction": newest_direction,
        "older_direction": older_direction,
        "group": group,
        "base_signal": base_signal,
        "derived_signal": derived_signal,
    }


def evaluate_xauusd_m15_group_for_slot(broker_dt, hour):
    """Classify XAUUSD M15 bars two through four immediately before a slot."""
    if broker_dt is None:
        return None
    slot_dt = broker_dt.replace(hour=int(hour), minute=0, second=0, microsecond=0)
    directions = [
        _lookback_candle_direction(SYMBOL, mt5.TIMEFRAME_M15, slot_dt - timedelta(minutes=offset))
        for offset in (30, 45, 60)
    ]
    return _classify_three_candles(directions)


def _m15_pair_for_hour(hour):
    """Return the GBP pair used for M15 4-candle lookback by hour group."""
    h = int(hour)
    if h in (3, 6, 9):
        return "GBPAUD"
    if h in (12, 14, 16):
        return "GBPUSD"
    return None


_previous_session_cache: dict[tuple, object] = {}


def resolve_previous_broker_session(broker_dt, symbol, timeframe):
    """Find the most recent Broker trading session before *broker_dt*.

    Scans backwards up to 7 calendar days, skipping weekends and sessions
    with no data for the given symbol/timeframe.  Results are cached per
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
        # Verify the candidate session has at least one bar for the symbol.
        # Use copy_rates_from_by_date which takes date range directly.
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


def evaluate_m15_4candle_for_slot(broker_dt, hour):
    """Evaluate 4 M15 candles (base + 3 pullback) from the previous trading session.

    H=3,6,9 → GBPAUD M15 previous session at offsets from slot hour.
    H=12,14,16 → GBPUSD M15 previous session at offsets from slot hour.
    Offset-30 candle = base direction → BUY(TANG)/SELL(GIAM).
    Offsets 45,60,75 = 3 pullback candles → classify SW or BT.

    Canonical matrix (two invariants):
      1. Every slot: SW → XAUUSD reverses Base; BT → XAUUSD keeps Base.
      2. H=3/6/9:  GBPAUD always opposite of Base.
         H=12/14/16: GBPUSD always same as Base.
    """
    h = int(hour)
    pair = _m15_pair_for_hour(h)
    if broker_dt is None or pair is None:
        return None
    prev_session = resolve_previous_broker_session(broker_dt, pair, mt5.TIMEFRAME_M15)
    if prev_session is None:
        return None
    source_slot = datetime.combine(prev_session, datetime.min.time()).replace(hour=h, minute=0)
    all_dirs = [
        _lookback_candle_direction(pair, mt5.TIMEFRAME_M15, source_slot - timedelta(minutes=offset))
        for offset in (30, 45, 60, 75)
    ]
    if any(d is None for d in all_dirs):
        return None
    base_dir = all_dirs[0]
    if base_dir not in ("TANG", "GIAM"):
        return None
    pullback_dirs = all_dirs[1:]
    pullback_group = _classify_three_candles(pullback_dirs)
    if pullback_group not in ("SW", "BT"):
        return None
    base_signal = "BUY" if base_dir == "TANG" else "SELL"

    # Invariant 1: SW → reverse Base, BT → keep Base (for XAUUSD)
    xau_signal = reverse_signal(base_signal) if pullback_group == "SW" else base_signal

    # Invariant 2: GBP pair depends on hour group
    if h in (3, 6, 9):
        # GBPAUD always opposite of Base
        gbp_signal = reverse_signal(base_signal)
    else:
        # GBPUSD always same as Base
        gbp_signal = base_signal

    return {
        "base_direction": base_dir,
        "base_signal": base_signal,
        "pullback_group": pullback_group,
        "xau_signal": xau_signal,
        "gbp_signal": gbp_signal,
        "pair": pair,
        "source_date": prev_session.isoformat(),
    }


def _entry_time_from_gbp_derivations(hour, directions_match, m15_group=None):
    """Map the two GBP-derived XAU directions to the Broker entry clock."""
    h = int(hour)
    if directions_match:
        return f"{h:02d}:11"
    if m15_group not in ("SW", "BT"):
        return None
    if h == 3:
        return "04:49" if m15_group == "SW" else "03:49"
    return f"{h + 1:02d}:25" if m15_group == "SW" else f"{h:02d}:49"


def _entry_time_from_m15_4candle(hour, pullback_group):
    """Map M15 4-candle pullback group to Broker entry clock."""
    h = int(hour)
    if pullback_group == "SW":
        return f"{h + 1:02d}:25"
    if pullback_group == "BT":
        return f"{h:02d}:49"
    return None


def evaluate_gbp_h1_slot(broker_dt, hour):
    """Build an XAUUSD slot signal.

    H=4 → legacy GBP H1 pair logic (GBPUSD + GBPAUD yesterday H1).
    H=3,6,9,12,14,16 → M15 4-candle lookback (GBPAUD or GBPUSD).
    """
    h = int(hour)
    if h not in ACTIVE_HOURS:
        return None

    # ── H=4: legacy GBP H1 pair logic ──
    if h == 4:
        gbpusd = evaluate_previous_day_gbp_h1_pair(broker_dt, h, "GBPUSD")
        gbpaud = evaluate_previous_day_gbp_h1_pair(broker_dt, h, "GBPAUD")
        if gbpusd is None or gbpaud is None:
            return None
        directions_match = gbpusd["derived_signal"] == gbpaud["derived_signal"]
        m15_group = None if directions_match else evaluate_xauusd_m15_group_for_slot(broker_dt, h)
        entry_time = _entry_time_from_gbp_derivations(h, directions_match, m15_group)
        if entry_time is None:
            return None
        final_signal = gbpusd["derived_signal"]
        pair_dirs = {"XAUUSD": final_signal}
        source_date = resolve_previous_broker_session(broker_dt, "GBPUSD", mt5.TIMEFRAME_H1)
        source_date_str = source_date.isoformat() if source_date else "unknown"
        comparison = "same" if directions_match else f"opposite, XAU M15={m15_group}"
        return {
            "signal": final_signal,
            "pattern_signal": gbpusd["base_signal"],
            "entry_time": entry_time,
            "report": (
                f"H={h}: GBPUSD {source_date_str}={gbpusd['group']} -> {final_signal}; "
                f"GBPAUD={gbpaud['group']} -> {gbpaud['derived_signal']}; {comparison}."
            ),
            "pair_dirs": pair_dirs,
            "source_date": source_date_str,
            "gbpusd_group": gbpusd["group"],
            "gbpaud_group": gbpaud["group"],
            "gbpusd_derived_signal": gbpusd["derived_signal"],
            "gbpaud_derived_signal": gbpaud["derived_signal"],
            "xau_m15_group": m15_group,
        }

    # ── H=3,6,9,12,14,16: M15 4-candle lookback ──
    m15 = evaluate_m15_4candle_for_slot(broker_dt, h)
    if m15 is None:
        return None
    entry_time = _entry_time_from_m15_4candle(h, m15["pullback_group"])
    if entry_time is None:
        return None
    xau_signal = m15["xau_signal"]
    gbp_signal = m15["gbp_signal"]
    gbp_pair = m15["pair"]
    pair_dirs = {"XAUUSD": xau_signal, gbp_pair: gbp_signal}
    source_date_str = m15.get("source_date", "unknown")
    return {
        "signal": xau_signal,
        "pattern_signal": m15["base_signal"],
        "entry_time": entry_time,
        "report": (
            f"H={h}: {gbp_pair} M15 ({source_date_str}) — "
            f"base={m15['base_direction']}/{m15['base_signal']}, "
            f"group={m15['pullback_group']}, "
            f"XAUUSD={xau_signal}, "
            f"{gbp_pair}={gbp_signal}."
        ),
        "pair_dirs": pair_dirs,
        "source_date": source_date_str,
        "m15_pair": gbp_pair,
        "m15_base_direction": m15["base_direction"],
        "m15_base_signal": m15["base_signal"],
        "m15_pullback_group": m15["pullback_group"],
        "m15_gbp_signal": gbp_signal,
        "m15_xau_signal": xau_signal,
    }


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
        6: "07:25",
        9: "10:25",
        12: "13:25",
        14: "15:25",
        16: "17:25",
    }
    clock = entry_time or get_entry_time_for_slot(broker_dt, h) or fallback_clocks[h]
    deadline_hour, deadline_minute = (int(part) for part in clock.split(":"))
    deadline = broker_dt.replace(
        hour=deadline_hour,
        minute=deadline_minute,
        second=0,
        microsecond=0,
    )
    return deadline


def calculate_slot_signal(broker_dt, hour):
    """Apply the canonical H-slot matrix for live and rebuilt signals."""
    hour = int(hour)
    if hour not in ACTIVE_HOURS:
        return {
            "signal": "WAIT",
            "report": f"H={hour}: inactive slot.",
            "suppressed": True,
        }
    result = evaluate_gbp_h1_slot(broker_dt, hour)
    if result is None:
        return {
            "signal": "WAIT",
            "report": f"H={hour}: incomplete GBP M15 4-candle or GBP H1 pair data.",
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
    if h == 4:
        return (
            "Yesterday's GBPUSD/GBPAUD H1 derives XAUUSD; matching directions "
            "enter H:11, otherwise XAUUSD M15 #2-#4 sets the late entry."
        )
    pair = _m15_pair_for_hour(h)
    if pair is None:
        return ""
    note = (
        f"{pair} M15 (previous session): base + 3 pullback. "
        f"SW → XAUUSD đảo Base; BT → XAUUSD giữ Base. "
        f"{'GBPAUD ngược Base.' if h in (3,6,9) else 'GBPUSD cùng Base.'} "
        f"Entry: SW → H+1:25, BT → H:49."
    )
    return note


def format_telegram_pair_block(pair_dirs, H, broker_dt=None, weekday=None):
    """Render XAUUSD and GBP pair directions for Telegram."""
    lines = []
    xau = (pair_dirs or {}).get("XAUUSD")
    if xau in ("BUY", "SELL"):
        icon, _ = get_signal_icon(xau)
        lines.append(f"  XAUUSD: {icon} {xau}")
    elif xau == "WAIT":
        lines.append("  XAUUSD: WAIT")
    for gbp_pair in ("GBPUSD", "GBPAUD"):
        gbp_dir = (pair_dirs or {}).get(gbp_pair)
        if gbp_dir in ("BUY", "SELL"):
            icon, _ = get_signal_icon(gbp_dir)
            lines.append(f"  {gbp_pair}: {icon} {gbp_dir}")
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
    """Return the final XAUUSD direction for one active slot."""
    result = {}
    h = int(H)
    if h not in ACTIVE_HOURS:
        return result
    if signal in ("SW", "BT"):
        return {}
    if signal == "WAIT":
        pair_dirs = (full_result or {}).get("pair_dirs", {})
        result["XAUUSD"] = pair_dirs.get("XAUUSD", "WAIT")
        # Include GBP pair if present
        for k, v in pair_dirs.items():
            if k != "XAUUSD" and k in ("GBPAUD", "GBPUSD"):
                result[k] = v if v in ("BUY", "SELL") else "WAIT"
        return result
    if signal not in ("BUY", "SELL"):
        return result
    result["XAUUSD"] = signal
    # Include GBP pair signal from full_result
    pair_dirs = (full_result or {}).get("pair_dirs", {})
    for k, v in pair_dirs.items():
        if k != "XAUUSD" and k in ("GBPAUD", "GBPUSD"):
            result[k] = v
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
def rebuild_slot_signal(broker_dt, h):
    """Recalculate one slot with current logic and overwrite signals_log (date, hour).
    Always logs the result — including WAIT and deactivated slots — so the dashboard
    shows every scheduled hour."""
    if broker_dt.weekday() >= 5:
        return False

    result = calculate_slot_signal(broker_dt, h)
    sig = result.get("signal")
    entry_time = get_entry_time_for_slot(broker_dt, h)
    source_date = result.get("source_date")
    pair_dirs = result.get("pair_dirs", {})
    if not pair_dirs and sig not in ("WAIT",):
        pair_dirs = get_pair_direction(h, sig, broker_dt, full_result=result)
    # WAIT records must carry a valid pair_dirs contract for dashboard display.
    if sig == "WAIT" and not pair_dirs:
        gbp_pair = _m15_pair_for_hour(h)
        pair_dirs = {"XAUUSD": "WAIT"}
        if gbp_pair:
            pair_dirs[gbp_pair] = "WAIT"
    hour_note = get_hour_note(h, broker_dt=broker_dt)
    deactivated = bool(result.get("deactivated") or is_deactivated_signal_slot(broker_dt, h))

    log_signal(h, broker_dt, sig or "WAIT", entry_time or "N/A", pair_dirs or {}, hour_note,
               pattern_signal=result.get("pattern_signal"),
               deactivated=deactivated,
               source_date=source_date)
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
    """Suppress catch-up Telegram sends for publication minutes already passed."""
    for hour in get_target_hours(broker_dt):
        signal_dt = get_signal_datetime_for_slot(broker_dt, hour)
        if broker_dt >= signal_dt:
            sent_today.add((broker_dt.date(), hour))


def _process_live_slot(broker_dt, hour):
    """Publish one due logical slot, retrying incomplete data until its deadline."""
    key = (broker_dt.date(), hour)
    if key in sent_today:
        return False
    signal_dt = get_signal_datetime_for_slot(broker_dt, hour)
    if broker_dt < signal_dt:
        return False
    entry_time = get_entry_time_for_slot(broker_dt, hour)
    if broker_dt > get_slot_retry_deadline(broker_dt, hour, entry_time=entry_time):
        print(f"  [MISSED] H={hour} exceeded entry deadline")
        sent_today.add(key)
        _save_state(sent_today)
        return False

    result = calculate_slot_signal(broker_dt, hour)
    signal = result.get("signal")
    entry_time = result.get("entry_time") or entry_time
    if entry_time and broker_dt > get_slot_retry_deadline(broker_dt, hour, entry_time=entry_time):
        print(f"  [MISSED] H={hour} entry window closed")
        sent_today.add(key)
        _save_state(sent_today)
        return False
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
