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
import re
import math
from datetime import datetime, timedelta, timezone, time as dtime, date
from zoneinfo import ZoneInfo
import traceback
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from utils import send_telegram_raw, send_telegram_with_keyboard
from oak_logger import setup_logger
from repositories.sqlite_store import SQLiteStore
from secret_store import resolve_telegram_token, migrate_plaintext_tokens
from telegram_client import telegram_get_me
from domain.broker_clock import BrokerClock, BrokerClockError
from domain.signal_rules import (
    classify_three_candle_group,
    derive_gbp_signal_from_layer1,
    select_two_layer_entry,
)

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
    TELEGRAM_ADMIN_CHAT_ID = str(
        _cfg.get("telegram_admin_chat_id")
        or _cfg.get("telegram_chat_id")
        or ""
    ).strip()
    TELEGRAM_CHAT_ID = TELEGRAM_ADMIN_CHAT_ID
    MT5_PATH = _cfg.get("mt5_path", "")
    DASHBOARD_URL = _cfg.get("dashboard_url", "")
except Exception:
    TELEGRAM_TOKEN = ""
    TELEGRAM_ADMIN_CHAT_ID = ""
    TELEGRAM_CHAT_ID = ""
    MT5_PATH = ""
    DASHBOARD_URL = ""
    print("[WARN] config.json not found or invalid.")

SYMBOL = "XAUUSD"
TARGET_HOURS = [3, 7, 9, 12, 14, 16]
ACTIVE_HOURS = frozenset(TARGET_HOURS)
VN_UTC_OFFSET = 7  # Vietnam local timezone (Indochina Time, no DST)


def resolve_signal_admin_chat_id(profile_cfg=None):
    """Return a positive integer admin chat ID for signal notifications.

    Reads from config.json keys (telegram_admin_chat_id or telegram_chat_id).
    Never uses profile_cfg["tele_chat"] — that is a group/channel ID.
    Rejects group/channel IDs (<= 0) and invalid values.
    Returns None if no valid admin chat ID is available.
    """
    raw_id = TELEGRAM_ADMIN_CHAT_ID
    if not raw_id:
        return None
    try:
        chat_id = int(raw_id)
    except (TypeError, ValueError):
        print(f"[WARN] Invalid telegram admin chat ID: {raw_id}")
        return None
    if chat_id <= 0:
        print(f"[WARN] Group/channel chat ID rejected for admin routing: {chat_id}")
        return None
    return chat_id


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


SIGNAL_LOGIC_VERSION = 82
ACTIVE_SIGNAL_LOGIC_VERSION = 82
MINIMUM_SIGNAL_LOGIC_VERSION = 82
SIGNAL_EVIDENCE_SCHEMA_VERSION = 4
LAYER3_CANDLE_GRACE_SECONDS = 90
D_DIRECTION_SCHEMA_VERSION = 4
D_SESSION_POLICY = {
    "normal_close_broker": "23:00",
    "timeframe_minutes": 30,
    "allow_early_close": True,
}
ACTIVE_SIGNAL_PAIRS = ("XAUUSD", "GBPUSD", "GBPAUD")
DISABLED_SIGNAL_PAIRS = ("GBPJPY", "GBPCAD")
GBP_SIGNAL_PAIRS = ("GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
SIGNAL_PAIRS = ("XAUUSD", *GBP_SIGNAL_PAIRS)
DISPLAY_SIGNAL_PAIRS = ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
EVIDENCE_SIGNAL_PAIRS = ("XAUUSD", "GBPUSD", "GBPAUD")
ENTRY_TIMING_SYMBOLS = ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
D_SOURCE_SYMBOL = {
    "XAUUSD": "GBPUSD",
    "GBPUSD": "GBPUSD",
    "GBPAUD": "GBPAUD",
    "GBPJPY": "GBPJPY",
    "GBPCAD": "GBPCAD",
}


def get_evaluated_pairs_for_hour(hour):
    """Return which pairs are evaluated at a given slot hour.

    All active slots (H3, H7, H9, H12, H14, H16) evaluate all five pairs.
    """
    h = int(hour)
    if h in ACTIVE_HOURS:
        return SIGNAL_PAIRS
    return ()


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
    """Load restart-safe sent-slot, entry-alert, auto-close, and D publication state."""
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

    pub_dates = set(data.get("d_published_local_dates", []))
    last_success = data.get("d_last_success_at")

    today_str = _trading_date().isoformat()
    if data.get("date") != today_str:
        res = {"auto_close_pending": pending_closes, "auto_close_last_alert": close_alerts}
        if pub_dates:
            res["d_published_local_dates"] = pub_dates
        if last_success is not None:
            res["d_last_success_at"] = last_success
        return res

    stored_ver = data.get("signal_logic_version")
    if stored_ver != SIGNAL_LOGIC_VERSION:
        print(f"  [STATE] Dropping stale sent_today: stored version={stored_ver or 'legacy'}, current version={SIGNAL_LOGIC_VERSION}")
        return {
            "auto_close_completed": set(data.get("auto_close_completed", [])),
            "auto_close_pending": pending_closes,
            "auto_close_last_alert": close_alerts,
            "sent_today": set(),
            "entry_alerts_sent": set(),
            "entry_alerts_pending": {},
            "d_published_local_dates": pub_dates,
            "d_last_success_at": last_success,
        }

    restored_sent = set()
    for raw_date, raw_hour in data.get("sent_today", []):
        try:
            restored_date = datetime.strptime(str(raw_date), "%Y-%m-%d").date()
            restored_sent.add((restored_date, int(raw_hour)))
        except (TypeError, ValueError):
            continue

    alerts_sent = set(data.get("entry_alerts_sent", []))
    alerts_pending = data.get("entry_alerts_pending", {})
    if not isinstance(alerts_pending, dict):
        alerts_pending = {}

    return {
        "sent_today": restored_sent,
        "auto_close_completed": set(data.get("auto_close_completed", [])),
        "auto_close_pending": pending_closes,
        "auto_close_last_alert": close_alerts,
        "entry_alerts_sent": alerts_sent,
        "entry_alerts_pending": alerts_pending,
        "d_published_local_dates": pub_dates,
        "d_last_success_at": last_success,
    }


def _save_state(sent_today=None, broker_dt=None, d_published_local_dates=None, d_last_success_at=None):
    """Persist sent logical slots, entry alerts, pending auto-close obligations, and D-Direction publication state."""
    if sent_today is None:
        try:
            sent_today = globals().get("sent_today", set())
        except Exception:
            sent_today = set()

    broker_now = broker_dt
    if broker_now is None:
        try:
            broker_now = get_broker_time()
        except Exception as error:
            print(f"[WARN] Cannot save state without a verified Broker clock: {error}")
            return False
    today_str = broker_now.date().isoformat()
    sent_rows = [
        [trading_date.isoformat() if hasattr(trading_date, "isoformat") else trading_date, hour]
        for trading_date, hour in (sent_today or set())
    ]
    try:
        broker_utc_offset = BROKER_CLOCK.utc_offset_for_date(broker_now.date())
    except Exception as error:
        print(f"[WARN] Cannot attach Broker clock metadata to state: {error}")
        broker_utc_offset = None
    has_verified_clock = broker_utc_offset is not None

    existing = _load_state()
    pub_dates = d_published_local_dates if d_published_local_dates is not None else existing.get("d_published_local_dates", set())
    last_success = d_last_success_at if d_last_success_at is not None else existing.get("d_last_success_at")

    data = {
        "date": today_str,
        "signal_logic_version": SIGNAL_LOGIC_VERSION,
        "sent_today": sent_rows,
        "entry_alerts_sent": sorted(list(entry_alerts_sent)),
        "entry_alerts_pending": entry_alerts_pending,
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
        "broker_time": broker_now.replace(microsecond=0).isoformat() if has_verified_clock else "",
        "broker_utc_offset": broker_utc_offset,
        "broker_observed_at_utc": datetime.now(timezone.utc).isoformat() if has_verified_clock else "",
        "d_published_local_dates": sorted(list(pub_dates)),
    }
    if last_success:
        data["d_last_success_at"] = last_success

    try:
        temporary = _STATE_FILE + ".tmp"
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False)
        os.replace(temporary, _STATE_FILE)
        return True
    except Exception as error:
        print(f"[WARN] Cannot save state: {error}")
        return False

_SIGNALS_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signals_log.json")


def _load_signals_log_records():
    """Load all signal records from signals_log.json safely."""
    try:
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
    except Exception:
        pass
    return []


def _get_current_entry_state(date_str, hour):
    """Read the current XAUUSD entry_state from signals_log for one slot."""
    try:
        if not os.path.exists(_SIGNALS_LOG) or os.path.getsize(_SIGNALS_LOG) <= 2:
            return None
        with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        for record in reversed(data):
            if record.get("date") == date_str and int(record.get("hour", -1)) == hour:
                return record.get("entry_state")
    except Exception:
        pass
    return None


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


def send_telegram(text: str) -> bool:
    """Send Telegram messages without allowing Telegram failure to stop the signal bot."""
    if not text:
        return False

    try:
        profile_name = _active_profile or ""
        profile_cfg = load_profile_config(profile_name)

        token = resolve_telegram_token(
            profile_name,
            profile_cfg.get("tele_token"),
            global_fallback=TELEGRAM_TOKEN,
        )
        chat_id = resolve_signal_admin_chat_id(profile_cfg)
    except Exception as error:
        print(f"[TELEGRAM] Cannot resolve profile credentials: {error}")
        return False

    if not token or chat_id is None:
        print(
            "[TELEGRAM] Missing token or chat_id "
            f"for profile={profile_name or '<default>'}"
        )
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                res_body = json.loads(resp.read().decode("utf-8"))
                if isinstance(res_body, dict) and res_body.get("ok") is True:
                    print(
                        f"[TELEGRAM] Sent private admin notification "
                        f"for profile={profile_name or '<default>'}"
                    )
                    return True
                print(f"[TELEGRAM] Response ok=False: {res_body}")
                return False
            print(f"[TELEGRAM] HTTP status {resp.status}")
            return False
    except Exception as e:
        print(f"[TELEGRAM] Send error: {e}")
        return False


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
    record = _format_signal_record(
        H, broker_dt, sig, entry_time, pair_dirs, hour_note,
        pattern_signal=pattern_signal, deactivated=deactivated,
        source_date=source_date, extra_fields=extra_fields,
    )
    try:
        data = []
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        key = (record["date"], record["hour"])
        data = [d for d in data if (d["date"], d["hour"]) != key]
        data.append(record)
        data = data[-2000:]
        _write_signals_log_atomic(data)
    except Exception as e:
        print(f"[WARN] Cannot log signal: {e}")


def _format_signal_record(H, broker_dt, sig, entry_time, pair_dirs, hour_note,
                          pattern_signal=None, deactivated=False, source_date=None, extra_fields=None):
    """Build one signal record dict without persisting."""
    deactivated = bool(deactivated or is_deactivated_signal_slot(broker_dt, H))
    current_prices = get_current_prices(pair_dirs)
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
    if _d_directions_today:
        record["daily_directions"] = _d_directions_today
        record["d_direction_schema_version"] = D_DIRECTION_SCHEMA_VERSION
    return record

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


def push_to_dashboard(snapshot_complete: bool = False):
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
                mode = "FULL_SNAPSHOT" if snapshot_complete else "UPSERT"
                body = {
                    "mode": mode,
                    "snapshot_complete": snapshot_complete,
                    "source": "mt5_signal_bot",
                    "logic_version": SIGNAL_LOGIC_VERSION,
                    "records": signals,
                }
                payload = json.dumps(body).encode("utf-8")
                req = urllib.request.Request(
                    f"{dashboard_url}/api/signals",
                    data=payload,
                    headers=headers
                )
                resp = urllib.request.urlopen(req, timeout=15)
                resp.read()
                print(f"[DASHBOARD] Signals pushed OK ({len(signals)} items, mode={mode})")
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



def _dashboard_signal_evidence(broker_dt, hour, result):
    """Build versioned evidence records for the dashboard (v82 per-symbol)."""
    pair_evidence = result.get("pair_evidence") or {}
    logic_version = result.get("logic_version", SIGNAL_LOGIC_VERSION)
    source_date = broker_dt.date().isoformat()
    records = {}
    for symbol, raw_evidence in pair_evidence.items():
        evidence = dict(raw_evidence or {})
        evidence.update({
            "logic_version": logic_version,
            "date": source_date,
            "hour": int(hour),
            "symbol": symbol,
            "entry_time": (result.get("pair_entry_times") or {}).get(symbol),
            "entry_state": (result.get("pair_entry_states") or {}).get(symbol),
            "entry_rule": evidence.get("entry_rule") or "INDEPENDENT_M30_ENGINE",
            "signal_state": (result.get("pair_signal_states") or {}).get(symbol),
        })
        key = f"{source_date}:{int(hour)}:{symbol}:v{logic_version}"
        records[key] = evidence
    return records


def push_signal_evidence(broker_dt, hour, result):
    """Push evaluated M30 evidence for every signal pair to the dashboard."""
    dashboard_url = os.environ.get("DASHBOARD_API_URL", "") or DASHBOARD_URL
    if not dashboard_url:
        return
    api_key = os.environ.get("DASHBOARD_API_KEY", "") or _cfg.get("dashboard_api_key", "")
    payload_dict = _dashboard_signal_evidence(broker_dt, hour, result)
    if not payload_dict:
        return
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        payload = json.dumps(payload_dict, default=str).encode("utf-8")
        req = urllib.request.Request(
            f"{dashboard_url}/api/signals/evidence",
            data=payload,
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            response.read()
    except Exception as e:
        print(f"  [DASHBOARD] Evidence push error: {e}")

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
    cached = _cache.get((symbol, int(target_ts)))
    if cached is not None and abs(int(cached["time"]) - int(target_ts)) <= 180:
        return cached
    if not mt5.symbol_select(symbol, True):
        print(f"[WARN] Khong the select symbol: {symbol}")
        return None

    # Query a narrow range around the exact M30 open timestamp.
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
        return normalize_mt5_rate_row(best)
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


_MISSING = object()


def _mt5_rate_field(row, field, default=_MISSING):
    """Safely read one field from an MT5 rate row (dict or numpy.void)."""
    if row is None:
        if default is _MISSING:
            raise KeyError(field)
        return default

    if isinstance(row, Mapping):
        value = row.get(field, default)
    else:
        dtype = getattr(row, "dtype", None)
        names = getattr(dtype, "names", None)
        if names and field in names:
            value = row[field]
        else:
            try:
                value = row[field]
            except (KeyError, IndexError, TypeError, ValueError):
                value = getattr(row, field, default)

    if value is _MISSING:
        raise KeyError(field)

    if hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass

    return value


def normalize_mt5_rate_row(row):
    """Convert an MT5 rate row (numpy.void or dict) to a plain Python dict."""
    if row is None:
        return None
    return {
        "time": int(_mt5_rate_field(row, "time")),
        "open": float(_mt5_rate_field(row, "open")),
        "high": float(_mt5_rate_field(row, "high")),
        "low": float(_mt5_rate_field(row, "low")),
        "close": float(_mt5_rate_field(row, "close")),
        "tick_volume": int(_mt5_rate_field(row, "tick_volume", 0)),
        "spread": int(_mt5_rate_field(row, "spread", 0)),
        "real_volume": int(_mt5_rate_field(row, "real_volume", 0)),
    }


def _serialize_candle_ohlc(candle, symbol):
    """Serialize an MT5 candle row to a plain dict with proper precision."""
    if candle is None:
        return None
    digits = _symbol_digits(symbol)
    return {
        "open": round(float(_mt5_rate_field(candle, "open")), digits),
        "high": round(float(_mt5_rate_field(candle, "high")), digits),
        "low": round(float(_mt5_rate_field(candle, "low")), digits),
        "close": round(float(_mt5_rate_field(candle, "close")), digits),
        "tick_volume": int(_mt5_rate_field(candle, "tick_volume", 0)),
    }


def _symbol_digits(symbol):
    """Return the price digits for a symbol from MT5 symbol_info, with fallback."""
    try:
        info = mt5.symbol_info(symbol)
        if info is not None:
            return info.digits
    except Exception:
        pass
    return 2 if symbol == "XAUUSD" else 5
def compute_utc_iso(date_obj, time_str, offset_hours):
    """Convert a Broker date and clock into an ISO-8601 UTC string."""
    if not time_str or ":" not in str(time_str):
        return None
    try:
        parts = str(time_str).split(":")
        h, m = int(parts[0]), int(parts[1])
        dt = datetime.combine(date_obj, datetime.min.time()).replace(hour=h, minute=m)
        utc_dt = dt - timedelta(hours=offset_hours)
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


ENTRY_PLAN_FIELDS = (
    "entry_state",
    "entry_candidate",
    "entry_rule",
    "pair_entry_times",
    "pair_entry_states",
    "pair_entry_branches",
    "pair_signal_states",
    "pair_labels",
    "pair_entry_at_utc",
    "entry_at_utc",
    "signal_state",
    "pair_groups",
    "pair_evidence",
    "record_revision",
    "state_updated_at_utc",
    "day_mode",
    "day_mode_state",
    "day_mode_source_hour",
    "day_mode_source_entry_time",
    "day_mode_source_branch",
    "day_mode_resolved_at",
    "pair_day_modes",
    "pair_day_mode_states",
    "pair_day_mode_source_hours",
    "pair_day_mode_source_entry_times",
    "pair_day_mode_source_branches",
    "d_directions",
    "signal_engine",
    "evidence_schema_version",
)

_VALID_DAY_MODES = {"DAY_MODE_H11", "DAY_MODE_H_PLUS_1_25"}
_VALID_DAY_MODE_BRANCHES = {"H_11", "H_PLUS_1_25"}


def serialize_day_mode(day_mode):
    """Serialize a DayMode dataclass to a plain dict for JSON/Redis/Telegram.

    Returns a dict with all day_mode_* fields set to None when day_mode is None.
    Never serializes the dataclass object itself — only scalar fields.
    """
    if day_mode is None:
        return {
            "day_mode": None,
            "day_mode_state": "UNRESOLVED_WAITING_FOR_ANCHOR",
            "day_mode_source_hour": None,
            "day_mode_source_entry_time": None,
            "day_mode_source_branch": None,
            "day_mode_resolved_at": None,
        }
    return {
        "day_mode": day_mode.mode,
        "day_mode_state": "RESOLVED",
        "day_mode_source_hour": day_mode.source_hour,
        "day_mode_source_entry_time": day_mode.source_entry_time,
        "day_mode_source_branch": day_mode.source_branch,
        "day_mode_resolved_at": datetime.now(timezone.utc).isoformat(),
    }


def deserialize_day_mode(record):
    """Reconstruct a DayMode from a serialized record dict.

    Returns None if the record lacks valid day_mode metadata.
    Validates mode, source_branch, source_hour, and source_entry_time.
    """
    if not isinstance(record, dict):
        return None
    mode = record.get("day_mode")
    if mode not in _VALID_DAY_MODES:
        return None
    source_hour = record.get("day_mode_source_hour")
    source_entry = record.get("day_mode_source_entry_time")
    source_branch = record.get("day_mode_source_branch")
    if source_branch not in _VALID_DAY_MODE_BRANCHES:
        return None
    try:
        source_hour_int = int(source_hour)
    except (TypeError, ValueError):
        return None
    if not source_entry or not isinstance(source_entry, str):
        return None
    return DayMode(
        mode=mode,
        source_hour=source_hour_int,
        source_entry_time=source_entry,
        source_branch=source_branch,
    )


def day_mode_from_result(result):
    """Extract a DayMode from an evaluate_all_pairs_for_slot result dict.

    The result contains 'day_mode' as a DayMode object (transient).
    This helper returns the object or None.
    """
    dm = result.get("day_mode")
    if isinstance(dm, DayMode):
        return dm
    return None


def reconstruct_current_day_mode(records, broker_date, active_logic_version):
    """Reconstruct the current DayMode from persisted records at startup.

    Scans records for the given broker date and logic version, in chronological
    slot order (H3 -> H7 -> H9 -> H12 -> H14 -> H16), and returns the first resolved
    DayMode found. Returns None if no resolved mode is found.
    """
    if not records or not broker_date:
        return None
    date_str = broker_date.isoformat() if hasattr(broker_date, 'isoformat') else str(broker_date)
    try:
        active_ver = int(active_logic_version)
    except (TypeError, ValueError):
        return None
    candidates = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if rec.get("date") != date_str:
            continue
        try:
            rec_ver = int(rec.get("logic_version", 0))
        except (TypeError, ValueError):
            continue
        if rec_ver != active_ver:
            continue
        candidates.append(rec)
    HOUR_ORDER = {3: 0, 7: 1, 9: 2, 12: 3, 14: 4, 16: 5}
    candidates.sort(key=lambda r: HOUR_ORDER.get(int(r.get("hour", 99)), 99))
    for rec in candidates:
        dm = deserialize_day_mode(rec)
        if dm is not None:
            return dm
    return None


def is_deactivated_signal_slot(broker_dt, hour):
    """Return whether a calculated slot is dependency-only and must not be traded.

    Since v65, no active slot has a weekday deactivation rule.
    This function returns False for all active slots.
    It exists for backward compatibility with consumers that check this field.
    """
    return False


def get_entry_time_for_slot(broker_dt, hour):
    """Calculate the Broker entry clock for one logical slot."""
    h = int(hour)
    if broker_dt is None or h not in ACTIVE_HOURS:
        return None
    result = evaluate_all_pairs_for_slot(broker_dt, h)
    return result.get("entry_time") if result else None


def get_slot_retry_deadline(broker_dt, hour, entry_time=None):
    """Return the last Broker datetime at which a live slot may be emitted."""
    h = int(hour)
    fallback_clocks = {
        3: "04:25",
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


def get_layer3_resolution_datetime(slot_dt):
    """Return the Broker datetime at which Layer 3 can first be evaluated."""
    return slot_dt + timedelta(minutes=30)


def calculate_slot_signal(broker_dt, hour, day_mode=None, d_directions=None):
    """Evaluate one active slot with the D-Direction + Day Mode engine."""
    hour = int(hour)
    if hour not in ACTIVE_HOURS:
        return {
            "signal": "WAIT",
            "report": f"H={hour}: inactive slot.",
            "suppressed": True,
        }
    result = evaluate_all_pairs_for_slot(broker_dt, hour, day_mode=day_mode, d_directions=d_directions)
    if result is None:
        return {
            "signal": "WAIT",
            "report": f"H={hour}: incomplete D-Direction + Day Mode data.",
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
        "GBP signals are derived independently first. XAU M30 Layer 1 creates the "
        "entry pair and Layer 2 selects the final XAU entry; GBP enters next hour."
    )


GBP_PAIRS = list(GBP_SIGNAL_PAIRS)
ALL_PAIRS = list(SIGNAL_PAIRS)

sent_today = set()
_d_directions_today = {}
ENTRY_ALERT_GRACE_MINUTES = 5
entry_alerts_sent = set()
entry_alerts_pending = {}


def load_signal_rule_contract():
    """Load canonical signal rule contract from signal_rule_contract.json."""
    contract_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signal_rule_contract.json")
    if os.path.exists(contract_path):
        try:
            with open(contract_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "logic_version": SIGNAL_LOGIC_VERSION,
        "public_slots": [3, 7, 9, 12, 14, 16],
        "internal_slots": [],
        "rules": {"VN": [], "EN": []},
        "startup_summary": "v72: two-layer independent M30 for GBP pairs",
    }





def build_startup_telegram_message(broker_dt, mt5_connected, rule_contract=None):
    """Build compact startup Telegram message per canonical contract."""
    ver = SIGNAL_LOGIC_VERSION
    mt5_status = "✅ OK" if mt5_connected else "⚠️ DISCONNECTED"
    broker_time_str = "--:--"
    if broker_dt is not None:
        try:
            broker_time_str = broker_dt.strftime("%H:%M")
        except Exception:
            pass
    return (
        f"🤖 OAK SIGNAL BOT ONLINE · v{ver}\n"
        f"MT5: {mt5_status} | Broker: {broker_time_str}\n"
        "Slots: H3 - H7 - H9 - H12 - H14 - H16\n"
        "Pairs: XAUUSD | GBPUSD | GBPAUD (GBPJPY/CAD: OFF)\n"
        "Signal engine: Independent M30 per symbol + H4 20:00 D\n"
        "Entry: L2 BT H:11 / L3 SW H:49 / L3 BT (H+1):25\n"
        "Auto-close: XAU 17:59 | GBP 19:59 Broker"
    )


def build_xau_entry_alert_fingerprint(trading_date, hour, logic_version, symbol, entry_time):
    """Build the canonical version/date/hour/symbol/entry de-duplication key."""
    return f"{logic_version}|{trading_date}|{hour}|{symbol}|{entry_time}"


def should_send_xau_entry_alert(current_result, sent_fingerprints):
    """Return True if current_result is a READY XAUUSD entry alert that has not been sent yet."""
    if not current_result or not isinstance(current_result, dict):
        return False
    if current_result.get("entry_state") != "READY":
        return False
    pair_entry_states = current_result.get("pair_entry_states", {})
    if pair_entry_states.get("XAUUSD") != "READY":
        return False
    pair_dirs = current_result.get("pair_dirs", {})
    xau_dir = pair_dirs.get("XAUUSD")
    if xau_dir not in ("BUY", "SELL"):
        return False
    pair_entry_times = current_result.get("pair_entry_times", {})
    xau_entry = pair_entry_times.get("XAUUSD")
    if not xau_entry or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(xau_entry)):
        return False
    fp = build_xau_entry_alert_fingerprint(
        current_result.get("source_date"),
        current_result.get("hour"),
        current_result.get("logic_version", SIGNAL_LOGIC_VERSION),
        "XAUUSD",
        xau_entry,
    )
    return fp not in (sent_fingerprints or set())


def _format_entry_local(entry_time, broker_offset, source_date):
    if (
        not entry_time
        or not source_date
        or isinstance(broker_offset, bool)
        or not isinstance(broker_offset, (int, float))
    ):
        return ""
    try:
        source = datetime.fromisoformat(source_date).date()
        utc_iso = compute_utc_iso(source, entry_time, broker_offset)
        if not utc_iso:
            return ""
        local_dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00")).astimezone()
        offset_hours = int((local_dt.utcoffset() or timedelta()).total_seconds() // 3600)
        zone = f"GMT{'+' if offset_hours >= 0 else ''}{offset_hours}"
        day_delta = (local_dt.date() - source).days
        suffix = " +1d" if day_delta > 0 else " -1d" if day_delta < 0 else ""
        return f" · {local_dt.strftime('%H:%M')} {zone}{suffix}"
    except (AttributeError, TypeError, ValueError):
        return ""


def _telegram_pair_line(symbol, direction, entry_time, broker_offset, source_date):
    icon = "🟢" if direction == "BUY" else "🔴" if direction == "SELL" else "⚪"
    entry = entry_time if entry_time else "WAIT"
    local = _format_entry_local(entry_time, broker_offset, source_date)
    return f"{symbol}: {icon} {direction or 'WAIT'} · Entry {entry} Broker{local}"


def build_entry_ready_telegram_message(record, broker_dt=None):
    """Build the v82 per-pair signal message."""
    del broker_dt
    try:
        hour = int(record.get("hour"))
    except (TypeError, ValueError):
        return None
    if hour not in ACTIVE_HOURS:
        return None
    directions = record.get("pair_dirs") or {}
    entries = record.get("pair_entry_times") or {}
    source_date = record.get("source_date") or record.get("date") or ""
    broker_offset = record.get("broker_utc_offset")
    exec_states = record.get("pair_entry_states") or {}
    lines = [f"🚨 SIGNAL READY · H{hour} · v{record.get('logic_version', SIGNAL_LOGIC_VERSION)}"]
    for symbol in DISPLAY_SIGNAL_PAIRS:
        dir_val = directions.get(symbol, "WAIT")
        entry_val = entries.get(symbol)
        exec_off = exec_states.get(symbol) == "DISABLED"
        icon = "🟢" if dir_val == "BUY" else "🔴" if dir_val == "SELL" else "⚪"
        entry = entry_val if entry_val else "WAIT"
        local = _format_entry_local(entry_val, broker_offset, source_date)
        suffix = " · EXEC OFF" if exec_off else ""
        lines.append(f"{symbol}: {icon} {dir_val} · Entry {entry} Broker{local}{suffix}")
    return "\n".join(lines)


def send_xau_entry_ready_alert(record, broker_dt=None) -> bool:
    """Attempt sending an entry ready alert. Add to entry_alerts_sent if success, else queue in entry_alerts_pending."""
    global entry_alerts_sent, entry_alerts_pending
    h = record.get("hour")
    source_date = record.get("source_date")
    ver = record.get("logic_version", SIGNAL_LOGIC_VERSION)
    xau_dir = (record.get("pair_dirs") or {}).get("XAUUSD")
    xau_entry = (record.get("pair_entry_times") or {}).get("XAUUSD")

    if not source_date or xau_dir not in ("BUY", "SELL") or not xau_entry:
        return False

    fp = build_xau_entry_alert_fingerprint(source_date, h, ver, "XAUUSD", xau_entry)
    if fp in entry_alerts_sent:
        return True

    # Check if entry is expired (> 5 minutes past entry datetime)
    if broker_dt is not None and source_date and xau_entry:
        try:
            s_date = datetime.fromisoformat(source_date).date()
            em_match = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", str(xau_entry))
            if em_match:
                eh, em = int(em_match.group(1)), int(em_match.group(2))
                entry_dt = datetime.combine(s_date, datetime.min.time()).replace(hour=eh, minute=em)
                if broker_dt > entry_dt + timedelta(minutes=ENTRY_ALERT_GRACE_MINUTES):
                    print(f"  [ENTRY ALERT EXPIRED] H={h} entry={xau_entry} past grace limit ({broker_dt})")
                    entry_alerts_pending.pop(fp, None)
                    return False
        except Exception:
            pass

    msg = build_entry_ready_telegram_message(record, broker_dt=broker_dt)
    success = send_telegram(msg)
    if success:
        entry_alerts_sent.add(fp)
        entry_alerts_pending.pop(fp, None)
        _save_state(sent_today, broker_dt=broker_dt)
        print(f"  [ALERT SENT] H={h} XAUUSD={xau_dir} entry={xau_entry} fp={fp}")
        return True
    else:
        entry_alerts_pending[fp] = {
            "record": record,
            "added_at": broker_dt.isoformat() if broker_dt else "",
            "attempts": entry_alerts_pending.get(fp, {}).get("attempts", 0) + 1,
        }
        _save_state(sent_today, broker_dt=broker_dt)
        print(f"  [ALERT QUEUED] H={h} fp={fp} (will retry)")
        return False


def reconcile_due_xau_entry_alerts(broker_dt):
    """Retry alerts already queued before restart; never create catch-up alerts."""
    global entry_alerts_pending, entry_alerts_sent
    if not broker_dt:
        return

    pending_fps = list(entry_alerts_pending.keys())
    for fp in pending_fps:
        item = entry_alerts_pending.get(fp)
        if not item:
            continue
        record = item.get("record") if isinstance(item, dict) else None
        if record:
            send_xau_entry_ready_alert(record, broker_dt=broker_dt)

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
def is_slot_ready(broker_dt, hour):
    """Return whether the mapped publication clock for this slot has passed."""
    h = int(hour)
    if h not in ACTIVE_HOURS:
        return False
    return broker_dt >= get_signal_datetime_for_slot(broker_dt, h)


# =====================================================================
# M30 HISTORY CACHE & WARM-UP
# =====================================================================

HISTORY_REBUILD_SCHEMA_VERSION = 2

_cache = {}


def warm_m30_history(symbols, start_dt, end_dt):
    """Batch-load M30 history for symbols into the in-memory cache."""
    if not mt5_ready:
        return
    for symbol in symbols:
        try:
            mt5.symbol_select(symbol, True)
        except Exception:
            pass
        try:
            rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M30, start_dt, end_dt)
        except Exception as error:
            print(f"  [HISTORY] {symbol} M30 fetch error: {error}")
            continue
        if rates is None or len(rates) == 0:
            print(f"  [HISTORY] {symbol} M30 loaded 0 bars")
            continue
        count = 0
        for row in rates:
            norm = normalize_mt5_rate_row(row)
            ts = norm["time"]
            _cache[(symbol, ts)] = norm
            count += 1
        print(f"  [HISTORY] {symbol} M30 loaded {count} bars")


def get_cached_candle(symbol, open_dt):
    """Look up one normalized candle dict from the M30 history cache."""
    target_ts = broker_time_to_ts(open_dt, open_dt.hour, open_dt.minute)
    cached = _cache.get((symbol, target_ts))
    if cached is None:
        return None
    if abs(int(cached["time"]) - int(target_ts)) > 180:
        return None
    return cached


def clear_history_cache():
    """Clear the in-memory M30 history cache."""
    _cache.clear()


D_DIRECTION_PAIRS = ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
_d_direction_cache = {}


def find_previous_available_broker_session(symbol, target_broker_date):
    """Find the most recent Broker date before target_date that has M30 bars."""
    search_start = datetime.combine(target_broker_date - timedelta(days=10), datetime.min.time())
    search_end = datetime.combine(target_broker_date, datetime.min.time())

    try:
        mt5.symbol_select(symbol, True)
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M30, search_start, search_end)
    except Exception:
        return None

    if rates is None or len(rates) == 0:
        return None

    broker_dates_with_bars = set()
    for row in rates:
        ts = int(row["time"]) if hasattr(row, "dtype") else int(row.get("time", 0))
        utc_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        try:
            broker_offset = BROKER_CLOCK.utc_offset_for_date(utc_dt.date())
            broker_dt = utc_dt - timedelta(hours=broker_offset)
            if broker_dt.date() < target_broker_date:
                broker_dates_with_bars.add(broker_dt.date())
        except Exception:
            continue

    if not broker_dates_with_bars:
        return None
    return max(broker_dates_with_bars)


def find_previous_session_h4_20_candle(source_symbol, target_broker_date):
    """Find the H4 candle with Broker open time exactly 20:00 from the previous available session.

    Returns (candle_norm, session_date, broker_offset) or (None, None, None) if not found.
    Does NOT fallback to H4 16:00 or M30 if 20:00 is missing.
    """
    session_date = find_previous_available_broker_session(source_symbol, target_broker_date)
    if session_date is None:
        return None, None, None

    session_start = datetime.combine(session_date, datetime.min.time())
    session_end = datetime.combine(session_date + timedelta(days=1), datetime.min.time())

    try:
        mt5.symbol_select(source_symbol, True)
        rates = mt5.copy_rates_range(source_symbol, mt5.TIMEFRAME_H4, session_start, session_end)
    except Exception:
        return None, session_date, None

    if rates is None or len(rates) == 0:
        return None, session_date, None

    try:
        broker_offset = BROKER_CLOCK.utc_offset_for_date(session_date)
    except Exception:
        return None, session_date, None

    for row in rates:
        norm = normalize_mt5_rate_row(row)
        utc_dt = datetime.fromtimestamp(norm["time"], tz=timezone.utc)
        broker_open = utc_dt + timedelta(hours=broker_offset)
        if (broker_open.date() == session_date
                and broker_open.hour == 20
                and broker_open.minute == 0):
            return norm, session_date, broker_offset

    return None, session_date, broker_offset


def _parse_broker_time_to_minutes(broker_time_str):
    """Convert 'HH:MM' broker time string to minutes since midnight."""
    if not broker_time_str or ":" not in str(broker_time_str):
        return None
    try:
        parts = str(broker_time_str).split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, TypeError):
        return None


def _session_close_minutes_from_policy(policy):
    """Return normal session close in minutes from D_SESSION_POLICY."""
    return _parse_broker_time_to_minutes(policy.get("normal_close_broker", "23:00"))


def classify_session_state(session_date, session_bars, policy):
    """Classify whether a session is complete, early-close, or incomplete.

    Rules:
    - exact normal D bar at normal_close_minutes - 30: SESSION_COMPLETE_NORMAL
    - no normal bar, but last valid bar >= 18:30 and < normal D bar time: EARLY_CLOSE
    - last valid bar < 18:30: HISTORY_INCOMPLETE, do NOT select early fake D
    """
    if not session_bars:
        return "SESSION_MISSING", None, None

    normal_close_minutes = _session_close_minutes_from_policy(policy)
    earliest_incomplete_minutes = 18 * 60 + 30
    normal_d_bar_minutes = None if normal_close_minutes is None else normal_close_minutes - 30

    for broker_dt, norm in session_bars:
        if not _valid_m30_ohlc(norm):
            continue
        bar_minutes = broker_dt.hour * 60 + broker_dt.minute
        if normal_d_bar_minutes is not None and bar_minutes == normal_d_bar_minutes:
            return "SESSION_COMPLETE_NORMAL", broker_dt, norm
        if normal_d_bar_minutes is None or bar_minutes < normal_d_bar_minutes:
            if bar_minutes < earliest_incomplete_minutes:
                return "SESSION_HISTORY_INCOMPLETE", broker_dt, norm
            return "SESSION_COMPLETE_EARLY_CLOSE", broker_dt, norm
        return "SESSION_HISTORY_INCOMPLETE", broker_dt, norm

    return "SESSION_INVALID", None, None


def find_last_completed_m30_of_session(symbol, session_date):
    """Find the last valid completed M30 candle in a broker session."""
    session_start = datetime.combine(session_date, datetime.min.time())
    session_end = datetime.combine(session_date + timedelta(days=1), datetime.min.time())

    try:
        mt5.symbol_select(symbol, True)
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M30, session_start, session_end)
    except Exception:
        return None, "MT5_FETCH_ERROR"

    if rates is None or len(rates) == 0:
        return None, "MISSING"

    # Convert to broker time and filter to session_date
    session_bars = []
    for row in rates:
        norm = normalize_mt5_rate_row(row)
        utc_dt = datetime.fromtimestamp(norm["time"], tz=timezone.utc)
        try:
            broker_offset = BROKER_CLOCK.utc_offset_for_date(utc_dt.date())
            broker_dt = utc_dt - timedelta(hours=broker_offset)
            if broker_dt.date() == session_date and broker_dt.minute in (0, 30):
                session_bars.append((broker_dt, norm))
        except Exception:
            continue

    if not session_bars:
        return None, "MISSING"

    # Sort by broker time descending, find last valid bar
    session_bars.sort(key=lambda x: x[0], reverse=True)
    session_state, selected_broker_dt, selected_norm = classify_session_state(
        session_date, session_bars, D_SESSION_POLICY
    )
    if selected_norm is None:
        return None, session_state
    return selected_norm, session_state


def _build_d_direction_evidence_h4(target_symbol, source_symbol, target_broker_date, session_date, candle, broker_offset):
    """Build D-Direction evidence payload v4 from H4 20:00 candle."""
    utc_open = datetime.fromtimestamp(candle["time"], tz=timezone.utc)
    utc_close = utc_open + timedelta(hours=4)
    broker_open = utc_open + timedelta(hours=broker_offset)
    broker_close = utc_close + timedelta(hours=broker_offset)
    local_open = broker_open + timedelta(hours=VN_UTC_OFFSET)
    local_close = broker_close + timedelta(hours=VN_UTC_OFFSET)

    direction = exact_candle_direction(candle)
    if direction == "TANG":
        d_dir = "BUY"
        d_state = "READY"
    elif direction == "GIAM":
        d_dir = "SELL"
        d_state = "READY"
    else:
        d_dir = "WAIT"
        d_state = "DOJI"

    return {
        "schema_version": D_DIRECTION_SCHEMA_VERSION,
        "symbol": target_symbol,
        "source_symbol": source_symbol,
        "timeframe": "H4",
        "target_date": target_broker_date.isoformat(),
        "session_date": session_date.isoformat() if session_date else None,
        "source_open_time_broker": "20:00",
        "source_open_at_utc": utc_open.isoformat(),
        "d_candle_open_time_broker": f"{broker_open.hour:02d}:{broker_open.minute:02d}",
        "d_candle_close_time_broker": f"{broker_close.hour:02d}:{broker_close.minute:02d}",
        "d_candle_open_time_local": f"{local_open.hour:02d}:{local_open.minute:02d}",
        "d_candle_close_time_local": f"{local_close.hour:02d}:{local_close.minute:02d}",
        "broker_utc_offset": broker_offset,
        "local_timezone": "Asia/Ho_Chi_Minh",
        "d_candle_open_at_utc": utc_open.isoformat(),
        "d_candle_close_at_utc": utc_close.isoformat(),
        "price_digits": get_symbol_price_digits(source_symbol),
        "candle": {
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "tick_volume": candle.get("tick_volume", 0),
        },
        "raw_direction": direction,
        "d_direction": d_dir,
        "d_state": d_state,
        "failure_reason": None,
        "discovery_rule": "PREVIOUS_AVAILABLE_SESSION_EXACT_H4_OPEN_20_00",
    }


def _build_d_missing_evidence(target_symbol, source_symbol, target_broker_date, session_date, broker_offset, failure_reason):
    """Build D-Direction evidence for missing/incomplete H4 20:00."""
    d_state = "MISSING_H4_20" if failure_reason == "MISSING_H4_20" else "MISSING"
    return {
        "schema_version": D_DIRECTION_SCHEMA_VERSION,
        "symbol": target_symbol,
        "source_symbol": source_symbol,
        "timeframe": "H4",
        "target_date": target_broker_date.isoformat(),
        "session_date": session_date.isoformat() if session_date else None,
        "source_open_time_broker": "20:00",
        "source_open_at_utc": None,
        "d_candle_open_time_broker": None,
        "d_candle_close_time_broker": None,
        "d_candle_open_time_local": None,
        "d_candle_close_time_local": None,
        "broker_utc_offset": broker_offset,
        "local_timezone": "Asia/Ho_Chi_Minh",
        "d_candle_open_at_utc": None,
        "d_candle_close_at_utc": None,
        "price_digits": get_symbol_price_digits(source_symbol),
        "candle": None,
        "raw_direction": None,
        "d_direction": "WAIT",
        "d_state": d_state,
        "failure_reason": failure_reason,
        "discovery_rule": "PREVIOUS_AVAILABLE_SESSION_EXACT_H4_OPEN_20_00",
    }


def _compute_d_from_source(target_symbol, source_symbol, target_broker_date):
    """Compute D-Direction for target_symbol using the source_symbol's H4 20:00 candle."""
    candle, session_date, broker_offset = find_previous_session_h4_20_candle(source_symbol, target_broker_date)

    if session_date is None:
        return _build_d_missing_evidence(target_symbol, source_symbol, target_broker_date, None, None, "MISSING_PREVIOUS_SESSION")

    if candle is None:
        return _build_d_missing_evidence(target_symbol, source_symbol, target_broker_date, session_date, broker_offset, "MISSING_H4_20")

    return _build_d_direction_evidence_h4(target_symbol, source_symbol, target_broker_date, session_date, candle, broker_offset)


def calculate_d_direction(symbol, target_broker_date):
    """Calculate D-Direction for one symbol on one target Broker date using H4 20:00."""
    cache_key = (target_broker_date.isoformat(), symbol)
    if cache_key in _d_direction_cache:
        return _d_direction_cache[cache_key]

    source_symbol = D_SOURCE_SYMBOL.get(symbol, symbol)

    source_cache_key = (target_broker_date.isoformat(), source_symbol)
    if source_cache_key in _d_direction_cache and symbol != source_symbol:
        source_evidence = _d_direction_cache[source_cache_key]
        result = dict(source_evidence)
        result["symbol"] = symbol
        _d_direction_cache[cache_key] = result
        return result

    evidence = _compute_d_from_source(symbol, source_symbol, target_broker_date)
    _d_direction_cache[cache_key] = evidence

    if symbol == source_symbol:
        _d_direction_cache[source_cache_key] = evidence

    return evidence


def calculate_all_d_directions(target_broker_date):
    """Calculate D-Direction for all 5 symbols using H4 20:00 source mapping."""
    source_results = {}
    unique_sources = set(D_SOURCE_SYMBOL.values())
    for src in unique_sources:
        source_results[src] = _compute_d_from_source(src, src, target_broker_date)
        cache_key = (target_broker_date.isoformat(), src)
        _d_direction_cache[cache_key] = source_results[src]

    results = {}
    for symbol in D_DIRECTION_PAIRS:
        source_symbol = D_SOURCE_SYMBOL.get(symbol, symbol)
        if symbol == source_symbol:
            results[symbol] = source_results[source_symbol]
        else:
            src_ev = source_results[source_symbol]
            result = dict(src_ev)
            result["symbol"] = symbol
            results[symbol] = result
            cache_key = (target_broker_date.isoformat(), symbol)
            _d_direction_cache[cache_key] = result
    return results


def clear_d_direction_cache():
    """Clear the D-Direction cache."""
    _d_direction_cache.clear()


# =====================================================================
# DAILY D PUBLICATION ENGINE (06:00 GMT+7)
# =====================================================================

try:
    HO_CHI_MINH_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:
    HO_CHI_MINH_TZ = timezone(timedelta(hours=7))
D_PUBLICATION_LOCAL_HOUR = 6
D_PUBLICATION_LOCAL_MINUTE = 0
D_PUBLICATION_TIMEZONE = "Asia/Ho_Chi_Minh"
D_HISTORY_SCHEMA_VERSION = 1
_D_DIRECTION_HISTORY_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "d_direction_history.json")

SYMBOL_PRICE_DIGITS = {
    "XAUUSD": 2,
    "GBPUSD": 5,
    "GBPAUD": 5,
    "GBPJPY": 3,
    "GBPCAD": 5,
}

def get_symbol_price_digits(symbol):
    if mt5_ready:
        try:
            info = mt5.symbol_info(symbol)
            if info and hasattr(info, "digits"):
                return int(info.digits)
        except Exception:
            pass
    return SYMBOL_PRICE_DIGITS.get(symbol, 5)

def get_d_publication_datetime_local(local_date):
    if isinstance(local_date, str):
        local_date = datetime.strptime(local_date, "%Y-%m-%d").date()
    return datetime.combine(local_date, dtime(D_PUBLICATION_LOCAL_HOUR, D_PUBLICATION_LOCAL_MINUTE), tzinfo=HO_CHI_MINH_TZ)

def get_d_publication_datetime_utc(local_date):
    local_dt = get_d_publication_datetime_local(local_date)
    return local_dt.astimezone(timezone.utc)

def is_d_publication_due(now_utc, local_date):
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    pub_utc = get_d_publication_datetime_utc(local_date)
    return now_utc >= pub_utc

def build_d_direction_snapshot_v2(target_local_date, target_broker_date=None):
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(HO_CHI_MINH_TZ)

    if target_broker_date is None:
        target_broker_date = target_local_date

    if isinstance(target_local_date, str):
        target_local_date_str = target_local_date
    else:
        target_local_date_str = target_local_date.isoformat()

    if isinstance(target_broker_date, str):
        target_broker_date_obj = datetime.strptime(target_broker_date, "%Y-%m-%d").date()
    else:
        target_broker_date_obj = target_broker_date

    d_dirs = calculate_all_d_directions(target_broker_date_obj)

    symbols_payload = {}
    states = []

    for symbol in D_DIRECTION_PAIRS:
        item = d_dirs.get(symbol) or {}
        d_state = item.get("d_state", "MISSING")
        d_dir = item.get("d_direction", "WAIT")
        candle = item.get("candle")
        session_date = item.get("session_date")
        source_symbol = item.get("source_symbol", symbol)

        open_time_broker = item.get("d_candle_open_time_broker")
        close_time_broker = item.get("d_candle_close_time_broker")
        open_at_utc = item.get("d_candle_open_at_utc")
        close_at_utc = item.get("d_candle_close_at_utc")
        open_time_local = item.get("d_candle_open_time_local")
        close_time_local = item.get("d_candle_close_time_local")

        digits = get_symbol_price_digits(source_symbol)
        raw_dir = item.get("raw_direction")

        symbols_payload[symbol] = {
            "symbol": symbol,
            "source_symbol": source_symbol,
            "timeframe": "H4",
            "target_date": target_broker_date_obj.isoformat(),
            "session_date": session_date,
            "source_open_time_broker": "20:00",
            "d_candle_open_time_broker": open_time_broker,
            "d_candle_close_time_broker": close_time_broker,
            "d_candle_open_at_utc": open_at_utc,
            "d_candle_close_at_utc": close_at_utc,
            "d_candle_open_time_local": open_time_local,
            "d_candle_close_time_local": close_time_local,
            "price_digits": digits,
            "candle": candle,
            "raw_direction": raw_dir,
            "d_direction": d_dir,
            "d_state": d_state,
            "execution_status": "OFF" if symbol in DISABLED_SIGNAL_PAIRS else "ON",
            "discovery_rule": "PREVIOUS_AVAILABLE_SESSION_EXACT_H4_OPEN_20_00",
        }
        states.append(d_state)

    if all(s in ("READY", "DOJI") for s in states):
        snapshot_state = "READY"
    elif any(s in ("READY", "DOJI") for s in states):
        snapshot_state = "PARTIAL"
    else:
        snapshot_state = "MISSING"

    try:
        broker_offset = BROKER_CLOCK.utc_offset_for_date(now_utc.date())
    except Exception:
        broker_offset = None

    return {
        "schema_version": D_DIRECTION_SCHEMA_VERSION,
        "logic_version": SIGNAL_LOGIC_VERSION,
        "target_local_date": target_local_date_str,
        "target_broker_date": target_broker_date_obj.isoformat(),
        "published_at_utc": now_utc.isoformat(),
        "published_at_local": now_local.isoformat(),
        "publication_timezone": D_PUBLICATION_TIMEZONE,
        "publication_rule": "DAILY_AT_06_00_LOCAL",
        "broker_utc_offset": broker_offset,
        "state": snapshot_state,
        "symbols": symbols_payload,
    }

def _load_d_direction_history_records():
    if not os.path.exists(_D_DIRECTION_HISTORY_LOG):
        return {}
    try:
        with open(_D_DIRECTION_HISTORY_LOG, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            elif isinstance(data, list):
                res = {}
                for row in data:
                    if isinstance(row, dict) and "target_local_date" in row:
                        res[row["target_local_date"]] = row
                return res
    except Exception as e:
        print(f"[DAILY-D] Failed to load local D history: {e}")
    return {}

def save_d_direction_snapshot_local(snapshot):
    records = _load_d_direction_history_records()
    target_date = snapshot.get("target_local_date")
    if target_date:
        records[target_date] = snapshot
        try:
            tmp_path = f"{_D_DIRECTION_HISTORY_LOG}.tmp.{os.getpid()}"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, _D_DIRECTION_HISTORY_LOG)
        except Exception as e:
            print(f"[DAILY-D] Failed to save local D history: {e}")

def push_d_direction_snapshot(snapshot, force=False):
    dashboard_url = os.environ.get("DASHBOARD_API_URL", "") or DASHBOARD_URL
    if not dashboard_url:
        print("[DAILY-D] No dashboard_url configured, skip push.")
        return False
    api_key = os.environ.get("DASHBOARD_API_KEY", "") or _cfg.get("dashboard_api_key", "")
    target_date = snapshot.get("target_local_date", "unknown")
    print(f"[DAILY-D] Pushing D snapshot for {target_date} to {dashboard_url}/api/signals/d-direction ...")
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
            headers["Authorization"] = f"Bearer {api_key}"
        payload = json.dumps(snapshot).encode("utf-8")
        req = urllib.request.Request(
            f"{dashboard_url}/api/signals/d-direction",
            data=payload,
            headers=headers
        )
        resp = urllib.request.urlopen(req, timeout=15)
        resp.read()
        print(f"[DAILY-D] Pushed D snapshot for {target_date} OK")
        return True
    except Exception as e:
        print(f"[DAILY-D] Failed to push D snapshot: {e}")
        return False

def publish_d_direction_daily(target_local_date=None, force=False):
    if target_local_date is None:
        target_local_date = datetime.now(HO_CHI_MINH_TZ).date()
    elif isinstance(target_local_date, str):
        target_local_date = datetime.strptime(target_local_date, "%Y-%m-%d").date()

    target_date_str = target_local_date.isoformat()
    state_data = _load_state()
    published_dates = set(state_data.get("d_published_local_dates", []))

    if target_date_str in published_dates and not force:
        print(f"  [DAILY-D] Date {target_date_str} already published, skip.")
        return _load_d_direction_history_records().get(target_date_str)

    pub_utc = get_d_publication_datetime_utc(target_local_date)
    try:
        broker_offset = BROKER_CLOCK.utc_offset_for_date(pub_utc.date())
        broker_dt = pub_utc - timedelta(hours=broker_offset)
        target_broker_date = broker_dt.date()
    except Exception:
        target_broker_date = target_local_date

    print(f"  [DAILY-D] Calculating D-Direction snapshot for local_date={target_date_str}, broker_date={target_broker_date} ...")

    attempts = 0
    snapshot = None
    deadline_local = datetime.combine(target_local_date, dtime(6, 10), tzinfo=HO_CHI_MINH_TZ)

    while True:
        attempts += 1
        snapshot = build_d_direction_snapshot_v2(target_local_date, target_broker_date)
        if snapshot["state"] in ("READY", "DOJI") or not force:
            break

        current_local = datetime.now(HO_CHI_MINH_TZ)
        if current_local >= deadline_local or attempts >= 6:
            print(f"  [DAILY-D] Reached deadline or max attempts ({attempts}), publishing state={snapshot['state']}")
            break

        print(f"  [DAILY-D] Attempt {attempts}: state={snapshot['state']}, retrying in 10s...")
        time.sleep(10)

    save_d_direction_snapshot_local(snapshot)
    pushed = push_d_direction_snapshot(snapshot, force=force)

    if snapshot["state"] in ("READY", "PARTIAL") or pushed:
        published_dates.add(target_date_str)
        _save_state(
            d_published_local_dates=published_dates,
            d_last_success_at=datetime.now(timezone.utc).isoformat(),
        )

    print(f"  [DAILY-D] Published {target_date_str} state={snapshot['state']} (pushed={pushed})")
    return snapshot

def rebuild_d_direction_history(days=45):
    print(f"[REBUILD-D-HISTORY] Rebuilding past {days} days of D-Direction snapshots...")
    today_local = datetime.now(HO_CHI_MINH_TZ).date()
    for i in range(days, -1, -1):
        target_date = today_local - timedelta(days=i)
        print(f"  --> Processing {target_date} ...")
        publish_d_direction_daily(target_date, force=True)
    print(f"[REBUILD-D-HISTORY] Completed {days} days rebuild.")

def repair_d_direction_date(date_str):
    print(f"[REPAIR-D-DATE] Repairing D-Direction snapshot for date {date_str}...")
    snapshot = publish_d_direction_daily(date_str, force=True)
    print(f"[REPAIR-D-DATE] Done repairing {date_str}: state={snapshot.get('state') if snapshot else 'FAILED'}")


# =====================================================================
# D-DIRECTION + DAY MODE ENGINE (v80)
# =====================================================================

def exact_candle_direction(candle):
    """Return TANG/GIAM/DOJI using exact Decimal comparison. DOJI only when open == close exactly."""
    if candle is None:
        return None
    try:
        open_price = Decimal(str(candle["open"]))
        close_price = Decimal(str(candle["close"]))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None
    if close_price > open_price:
        return "TANG"
    if close_price < open_price:
        return "GIAM"
    return "DOJI"


@dataclass(frozen=True)
class DayMode:
    mode: str  # "DAY_MODE_H11" or "DAY_MODE_H_PLUS_1_25"
    source_hour: int
    source_entry_time: str
    source_branch: str  # "H_11" or "H_PLUS_1_25"


def classify_slot_entry_branch(slot_hour, entry_time):
    """Classify a slot's own entry into H_11, H_49, or H_PLUS_1_25."""
    if not entry_time:
        return None
    h = int(slot_hour)
    if entry_time == f"{h:02d}:11":
        return "H_11"
    if entry_time.endswith(":49"):
        return "H_49"
    if entry_time == f"{h + 1:02d}:25" or (h == 3 and entry_time == "04:25"):
        return "H_PLUS_1_25"
    return None


def resolve_or_anchor_day_mode(current_mode, slot_hour, entry_time):
    """Return (day_mode, was_anchored). H_49 never anchors. First H_11/H+1:25 anchors."""
    branch = classify_slot_entry_branch(slot_hour, entry_time)
    if branch == "H_49" or branch is None:
        return current_mode, False
    if current_mode is not None:
        return current_mode, False
    mode_name = "DAY_MODE_H11" if branch == "H_11" else "DAY_MODE_H_PLUS_1_25"
    return DayMode(
        mode=mode_name,
        source_hour=int(slot_hour),
        source_entry_time=entry_time,
        source_branch=branch,
    ), True


def resolve_primary_signal_action(day_mode, entry_branch):
    """Determine whether to KEEP_D, REVERSE_D, or REVERSE_H1."""
    if entry_branch == "H_49":
        return "REVERSE_H1"
    if entry_branch not in ("H_11", "H_PLUS_1_25"):
        return "WAIT"
    if day_mode is None:
        return "WAIT"
    mode_branch = "H_11" if day_mode.mode == "DAY_MODE_H11" else "H_PLUS_1_25"
    return "KEEP_D" if entry_branch == mode_branch else "REVERSE_D"


def apply_new_final_signal_inversion(direction, broker_date, slot_hour, primary_source, symbol=None):
    """Apply the three new final inversion rules (v82).

    Rule A: H3 Wed/Thu → invert if primary_source is D_DIRECTION.
    Rule B: H16 Tue/Wed/Fri → invert if primary_source is D_DIRECTION.
    Rule C: H14 Tue/Wed → invert always (regardless of source).
    """
    if direction not in ("BUY", "SELL"):
        return direction, None
    wd = broker_date.weekday()
    h = int(slot_hour)

    # Rule A: H3 Wednesday(2) / Thursday(3), D-based only
    if h == 3 and wd in (2, 3) and primary_source == "D_DIRECTION":
        reversed_dir = "SELL" if direction == "BUY" else "BUY"
        return reversed_dir, "H3_WED_THU_D_EXTRA_REVERSE"

    # Rule C: H14 Tuesday(1) / Wednesday(2), always invert
    if h == 14 and wd in (1, 2):
        reversed_dir = "SELL" if direction == "BUY" else "BUY"
        return reversed_dir, "H14_TUE_WED_EXTRA_REVERSE"

    # Rule B: H16 Tuesday(1) / Wednesday(2) / Friday(4), D-based only
    if h == 16 and wd in (1, 2, 4) and primary_source == "D_DIRECTION":
        reversed_dir = "SELL" if direction == "BUY" else "BUY"
        return reversed_dir, "H16_TUE_WED_FRI_D_EXTRA_REVERSE"

    return direction, None


def apply_weekday_slot_inversion(direction, broker_date, slot_hour):
    """Legacy wrapper — delegates to apply_new_final_signal_inversion with D source."""
    return apply_new_final_signal_inversion(direction, broker_date, slot_hour, "D_DIRECTION")


def read_previous_h1_candle(symbol, slot_dt, as_of_dt=None):
    """Read the completed H1 candle that closes at the slot's H:00."""
    h1_close = slot_dt.replace(minute=0, second=0, microsecond=0)
    h1_open = h1_close - timedelta(hours=1)
    target_ts = broker_time_to_ts(h1_open, h1_open.hour, h1_open.minute)
    try:
        candle = get_candle_by_ts(symbol, mt5.TIMEFRAME_H1, target_ts)
    except Exception:
        return None, None
    if candle is None:
        return None, None
    direction = exact_candle_direction(candle)
    return candle, direction


def _build_h1_evidence(symbol, h1_candle, h1_dir, slot_dt):
    """Build H1 evidence payload for signal evidence records."""
    if h1_candle is None:
        return None
    h1_close_dt = slot_dt.replace(minute=0, second=0, microsecond=0)
    h1_open_dt = h1_close_dt - timedelta(hours=1)
    return {
        "symbol": symbol,
        "timeframe": "H1",
        "open_time": h1_open_dt.strftime("%H:%M"),
        "close_time": h1_close_dt.strftime("%H:%M"),
        "open": float(h1_candle["open"]) if h1_candle.get("open") is not None else None,
        "high": float(h1_candle["high"]) if h1_candle.get("high") is not None else None,
        "low": float(h1_candle["low"]) if h1_candle.get("low") is not None else None,
        "close": float(h1_candle["close"]) if h1_candle.get("close") is not None else None,
        "open_exact": f"{h1_candle['open']:.5f}" if isinstance(h1_candle.get("open"), (int, float)) else str(h1_candle.get("open")),
        "close_exact": f"{h1_candle['close']:.5f}" if isinstance(h1_candle.get("close"), (int, float)) else str(h1_candle.get("close")),
        "direction": h1_dir or "DOJI",
    }


# =====================================================================
# REBUILD: tính lại signals_log từ MT5 khi bot khởi động (tránh push data cũ)
# =====================================================================
def _build_rebuild_record(broker_dt, h, *, as_of_dt=None, prior_slot_results=None, day_mode=None, d_directions=None):
    """Evaluate one slot and return (record_dict, next_day_modes) without persisting.

    Returns a tuple so the caller can propagate per-symbol DayModes across slots.
    next_day_modes is a dict {symbol: DayMode|None} for per-symbol propagation.
    """
    result = evaluate_all_pairs_for_slot(broker_dt, h, as_of_dt=as_of_dt, prior_slot_results=prior_slot_results,
                                          day_mode=day_mode, d_directions=d_directions)
    if result is None:
        result = calculate_slot_signal(broker_dt, h)

    next_day_modes = result.get("_pair_day_modes_objects", {})
    if not next_day_modes:
        next_dm = day_mode_from_result(result)
        next_day_modes = {sym: next_dm for sym in SIGNAL_PAIRS}

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

    extra_fields = {}
    for key in ENTRY_PLAN_FIELDS:
        if key in result:
            val = result[key]
            if key == "day_mode" and isinstance(val, DayMode):
                extra_fields.update(serialize_day_mode(val))
            elif key == "day_mode" and val is None:
                extra_fields.update(serialize_day_mode(None))
            else:
                extra_fields[key] = val

    for pkey in ("pair_day_modes", "pair_day_mode_states", "pair_day_mode_source_hours",
                 "pair_day_mode_source_entry_times", "pair_day_mode_source_branches",
                 "pair_entry_branches"):
        if pkey in result:
            extra_fields[pkey] = result[pkey]

    extra_fields.setdefault("evidence_schema_version", SIGNAL_EVIDENCE_SCHEMA_VERSION)

    record = _format_signal_record(
        h, broker_dt, sig or "WAIT", entry_time, pair_dirs or {}, hour_note,
        pattern_signal=result.get("pattern_signal"),
        deactivated=deactivated,
        source_date=source_date,
        extra_fields=extra_fields if extra_fields else None,
    )

    record.pop("_day_mode_object", None)
    record.pop("_pair_day_modes_objects", None)

    return record, next_day_modes


def rebuild_slot_signal(broker_dt, h, *, as_of_dt=None):
    """Recalculate one slot with current logic and overwrite signals_log (date, hour).

    ``as_of_dt`` controls how much market data the evaluator may read:
    - current-day rebuild: pass ``broker_now`` so Layer 3 resolves when past H:30;
    - historical rebuild: pass a far-future timestamp so all layers resolve.
    """
    if broker_dt.weekday() >= 5:
        return False

    try:
        record, _next_dm = _build_rebuild_record(broker_dt, h, as_of_dt=as_of_dt)
    except Exception as error:
        print(f"  [REBUILD] ERROR date={broker_dt.date().isoformat()} H={h}"
              f" error_type={type(error).__name__}: {error}")
        traceback.print_exc()
        return False

    date_str = record["date"]
    hour_val = int(record["hour"])
    try:
        if not os.path.exists(_SIGNALS_LOG) or os.path.getsize(_SIGNALS_LOG) <= 2:
            _write_signals_log_atomic([record])
        else:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            data = [rec for rec in data
                    if not (rec.get("date") == date_str and int(rec.get("hour", -1)) == hour_val)]
            data.append(record)
            _write_signals_log_atomic(data)
    except Exception as error:
        print(f"  [REBUILD] WRITE ERROR date={date_str} H={hour_val}: {error}")
        return False
    return True


def rebuild_recent_history(days=45):
    """Recalculate recent sessions with warm-up, two-phase publish, and validation."""
    if not mt5_ready:
        print("  [REBUILD] MT5 not ready, skip")
        return 0

    broker_dt = get_broker_time()
    today = broker_dt.date()
    dates = [today - timedelta(days=i) for i in range(days)]

    # Phase 0: warm M30 history cache
    oldest = min(d for d in dates if d.weekday() < 5)
    warm_start = datetime.combine(oldest - timedelta(days=2), datetime.min.time())
    warm_m30_history(["XAUUSD", "GBPUSD", "GBPAUD"], warm_start, broker_dt)

    # Phase A: evaluate all slots in memory
    rebuild_dates = {target_date.isoformat() for target_date in dates if target_date.weekday() < 5}
    candidate_records = {}
    attempted = 0
    failed = 0
    for target_date in reversed(dates):
        if target_date.weekday() >= 5:
            continue
        hours = get_target_hours(datetime.combine(target_date, datetime.min.time()))
        day_results = {}
        current_pair_day_modes = {sym: None for sym in SIGNAL_PAIRS}
        # Compute D-Directions once per date
        try:
            day_d_directions = calculate_all_d_directions(target_date)
        except Exception:
            day_d_directions = None
        for hour in hours:
            if target_date == today and not is_slot_ready(broker_dt, hour):
                continue
            attempted += 1
            slot_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=hour)
            rebuild_as_of = broker_dt if target_date == today else slot_dt + timedelta(days=1)
            try:
                record, next_day_modes = _build_rebuild_record(slot_dt, hour, as_of_dt=rebuild_as_of,
                                               prior_slot_results=day_results if hour == 16 else None,
                                               day_mode=current_pair_day_modes,
                                               d_directions=day_d_directions)
                if record is None:
                    continue
                # Propagate per-symbol DayModes across slots
                if isinstance(next_day_modes, dict):
                    for sym, dm in next_day_modes.items():
                        if dm is not None:
                            current_pair_day_modes[sym] = dm
                # Store D-Directions in record
                if day_d_directions:
                    record["daily_directions"] = day_d_directions
                    record["d_direction_schema_version"] = D_DIRECTION_SCHEMA_VERSION
                day_results[hour] = record
                key = (record["date"], int(record["hour"]))
                candidate_records[key] = record
            except Exception as error:
                failed += 1
                print(f"  [REBUILD] ERROR date={target_date.isoformat()} H={hour}"
                      f" error_type={type(error).__name__}: {error}")
                traceback.print_exc()

    if attempted == 0:
        print(f"  [REBUILD] No slots to rebuild")
        clear_history_cache()
        return 0

    # Phase B: atomic publish
    try:
        existing_data = []
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                existing_data = json.load(f)
        kept = []
        for rec in (existing_data if isinstance(existing_data, list) else []):
            if not isinstance(rec, dict):
                continue
            try:
                rec_hour = int(rec.get("hour", -1))
            except (TypeError, ValueError):
                continue
            if rec.get("date") in rebuild_dates and rec_hour in ACTIVE_HOURS:
                continue
            kept.append(rec)
        kept.extend(candidate_records.values())
        kept = kept[-2000:]
        _write_signals_log_atomic(kept)
    except Exception as error:
        print(f"  [REBUILD] PUBLISH ERROR: {error}")
        traceback.print_exc()
        clear_history_cache()
        return 0

    refreshed = len(candidate_records)
    print(f"  [REBUILD] Attempted: {attempted}")
    print(f"  [REBUILD] Refreshed: {refreshed}")
    print(f"  [REBUILD] Failed: {failed}")
    print(f"  [REBUILD] Logic v{SIGNAL_LOGIC_VERSION}, schema v{HISTORY_REBUILD_SCHEMA_VERSION}")
    clear_history_cache()
    return refreshed


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
_current_day_mode = None  # DayMode or None — tracked across live slots


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
        _save_state(sent_today, broker_dt=broker_dt)
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
        _save_state(sent_today, broker_dt=broker_dt)
        if outcome["attempted"]:
            send_telegram(
                f"🔒 Đã đóng ALL {category.upper()}: "
                f"{outcome['closed']}/{outcome['attempted']} lệnh lúc {cutoff[0]:02d}:{cutoff[1]:02d} Broker"
            )
        return
    last_alert = _auto_close_last_alert.get(key)
    if last_alert is None or (broker_dt - last_alert).total_seconds() >= 900:
        _auto_close_last_alert[key] = broker_dt
        _save_state(sent_today, broker_dt=broker_dt)
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
    """Prevent restart catch-up sends for publication clocks already passed."""
    for hour in get_target_hours(broker_dt):
        if broker_dt >= get_signal_datetime_for_slot(broker_dt, hour):
            sent_today.add((broker_dt.date(), hour))


def _persist_live_result(broker_dt, hour, result):
    """Persist a live slot result with serialized DayMode (scalar fields only)."""
    pair_dirs = get_pair_direction(hour, result.get("signal", "WAIT"), broker_dt, full_result=result)
    extra_fields = {}
    for field in ENTRY_PLAN_FIELDS:
        if field in result:
            val = result[field]
            if field == "day_mode" and isinstance(val, DayMode):
                extra_fields.update(serialize_day_mode(val))
            elif field == "day_mode" and val is None:
                extra_fields.update(serialize_day_mode(None))
            else:
                extra_fields[field] = val
    extra_fields.setdefault("evidence_schema_version", SIGNAL_EVIDENCE_SCHEMA_VERSION)
    log_signal(
        hour,
        broker_dt,
        result.get("signal", "WAIT"),
        result.get("entry_time"),
        pair_dirs,
        get_hour_note(hour, broker_dt=broker_dt),
        extra_fields=extra_fields,
    )
    push_to_dashboard()
    push_signal_evidence(broker_dt, hour, result)
    return pair_dirs


def _all_pair_entries_ready(result):
    """Return whether every canonical pair has an actionable validated entry."""
    directions = result.get("pair_dirs") or {}
    signal_states = result.get("pair_signal_states") or {}
    entry_states = result.get("pair_entry_states") or {}
    entry_times = result.get("pair_entry_times") or {}
    return all(
        directions.get(symbol) in ("BUY", "SELL")
        and signal_states.get(symbol) == "READY"
        and entry_states.get(symbol) == "READY"
        and bool(re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(entry_times.get(symbol) or "")))
        for symbol in SIGNAL_PAIRS
    )


def _process_live_slot(broker_dt, hour):
    """Publish one due slot, re-evaluating PENDING_LAYER3 until entry resolves."""
    global _current_day_mode
    key = (broker_dt.date(), hour)

    if broker_dt < get_signal_datetime_for_slot(broker_dt, hour):
        return False

    is_recheck = False
    if key in sent_today:
        prev_entry_state = _get_current_entry_state(broker_dt.date().isoformat(), hour)
        if prev_entry_state == "PENDING_LAYER3":
            h30 = broker_dt.replace(hour=hour, minute=30, second=0, microsecond=0)
            if broker_dt >= h30:
                is_recheck = True
        if not is_recheck:
            return False

    result = calculate_slot_signal(broker_dt, hour, day_mode=_current_day_mode)
    if not result:
        print(f"  [RETRY] H={hour} - no evaluation result")
        return False

    # Update day mode from result with invariant: do not overwrite existing mode
    # unless new mode is from the same source hour or current mode is None.
    dm = result.get("day_mode")
    if isinstance(dm, DayMode):
        if _current_day_mode is None:
            _current_day_mode = dm
        elif dm.source_hour == _current_day_mode.source_hour and dm.mode == _current_day_mode.mode:
            pass  # Same mode, no change needed

    deadline = get_slot_retry_deadline(broker_dt, hour, result.get("entry_time"))
    xau_actionable = (
        result.get("signal") in ("BUY", "SELL")
        and result.get("entry_state") == "READY"
        and result.get("signal_state") == "READY"
        and result.get("entry_time")
    )

    if xau_actionable and broker_dt > deadline:
        sent_today.add(key)
        _save_state(sent_today, broker_dt=broker_dt)
        print(f"  [MISSED] H={hour} resolved after XAUUSD entry {result.get('entry_time')}")
        return False

    if not xau_actionable:
        _persist_live_result(broker_dt, hour, result)
        if broker_dt > deadline:
            sent_today.add(key)
            _save_state(sent_today, broker_dt=broker_dt)
            print(f"  [MISSED] H={hour} exceeded latest entry deadline")
        else:
            print(f"  [RETRY] H={hour} - {result.get('entry_state', 'WAIT')}")
        return False

    _persist_live_result(broker_dt, hour, result)
    if not _all_pair_entries_ready(result):
        print(f"  [RETRY] H={hour} - one or more GBP pair entries are incomplete")
        return False
    if should_send_xau_entry_alert(result, entry_alerts_sent):
        send_xau_entry_ready_alert(result, broker_dt=broker_dt)
    sent_today.add(key)
    _save_state(sent_today, broker_dt=broker_dt)
    tag = "RESOLVED" if is_recheck else "SENT"
    print(f"  [{tag}] H={hour} signal={result['signal']} entry={result['entry_time']}")
    return True


def main(profile_name=None):
    global mt5_ready, sent_today, _d_directions_today, _active_profile, _broker_clock_error, entry_alerts_sent, entry_alerts_pending, _current_day_mode
    print("=" * 55)
    print(f"  MT5 Multi-Timeframe Signal Bot v{SIGNAL_LOGIC_VERSION}")
    print(f"  Symbol: {SYMBOL}")
    print(f"  Target Hours: {', '.join(f'H={h}' for h in TARGET_HOURS)}")
    print(f"  Auto-close: XAUUSD 17:59, GBP 19:59 (Broker)")
    print("  Broker clock: live-tick calibrated, fail-closed")
    admin_ok = bool(TELEGRAM_ADMIN_CHAT_ID and resolve_signal_admin_chat_id())
    print(f"  Telegram admin destination: {'yes' if admin_ok else 'no'}")
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
    entry_alerts_sent.update(saved.get("entry_alerts_sent", set()))
    entry_alerts_pending.update(saved.get("entry_alerts_pending", {}))

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
    # Calculate D-Direction for current Broker date
    try:
        _d_directions_today = calculate_all_d_directions(broker_dt.date())
        print(f"  [D-DIR] Calculated for {broker_dt.date().isoformat()}")
        for sym, dd in _d_directions_today.items():
            print(f"    {sym}: {dd.get('d_direction', 'WAIT')} (session={dd.get('session_date', 'N/A')})")
    except Exception as error:
        _d_directions_today = {}
        print(f"  [D-DIR] Error: {error}")

    # Independent Daily 06:00 GMT+7 D-Direction publication check
    today_local = datetime.now(HO_CHI_MINH_TZ).date()
    now_utc = datetime.now(timezone.utc)
    if is_d_publication_due(now_utc, today_local):
        print(f"  [DAILY-D] Publication is due for local date {today_local.isoformat()}")
        publish_d_direction_daily(today_local)
    else:
        print(f"  [DAILY-D] Before 06:00 GMT+7, today's publication scheduled for 06:00 GMT+7.")

    reconcile_due_xau_entry_alerts(broker_dt)

    push_to_dashboard(snapshot_complete=True)
    if startup_rebuilt > 0:
        print(f"\n[DASHBOARD] Pushed after rebuild ({startup_rebuilt} slots refreshed)")

    # Reconstruct day mode from saved records (do not reset to None)
    _current_day_mode = None
    try:
        records = _load_signals_log_records()
        _current_day_mode = reconstruct_current_day_mode(
            records,
            broker_dt.date(),
            SIGNAL_LOGIC_VERSION,
        )
    except Exception as error:
        print(f"  [DAY MODE] Reconstruction error: {error}")
    if _current_day_mode:
        print(f"  [DAY MODE] Reconstructed: {_current_day_mode.mode} (source H{_current_day_mode.source_hour} {_current_day_mode.source_entry_time})")
    else:
        print(f"  [DAY MODE] No resolved mode found, will anchor at next eligible entry")

    try:
        last_price_push_minute = None
        last_broker_date = broker_dt.date()
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
            # Reset day mode when broker date changes
            if broker_dt.date() != last_broker_date:
                _current_day_mode = None
                last_broker_date = broker_dt.date()
            if not startup_slots_marked:
                # Rebuild can cross a publication boundary; guard from a fresh
                # Broker clock so restart never replays a slot that just passed.
                _mark_passed_slots_on_startup(broker_dt)
                _save_state(sent_today, broker_dt=broker_dt)
                startup_slots_marked = True
            for hour in get_target_hours(broker_dt):
                _process_live_slot(broker_dt, hour)

            price_push_minute = (broker_dt.date(), broker_dt.hour, broker_dt.minute)
            if price_push_minute != last_price_push_minute:
                _save_state(sent_today, broker_dt=broker_dt)
                push_state_to_dashboard()
                push_prices_to_dashboard()
                last_price_push_minute = price_push_minute

            _process_auto_closes(broker_dt)
            time.sleep(5)

    except KeyboardInterrupt:
        print("\n  Bot stopped.")
    except Exception as e:
        print(f"\n  Loi: {e}")
    finally:
        if mt5_ready:
            mt5.shutdown()
        print("  Bot stopped.")

def gbp_signal_open_times(slot_dt):
    """Return the three MT5 M30 open times used for one GBP signal."""
    slot = slot_dt.replace(minute=0, second=0, microsecond=0)
    return tuple(slot - timedelta(minutes=value) for value in (60, 90, 120))


def xau_entry_layer_close_times(slot_dt):
    """Return user-facing close-time windows for both XAU entry layers."""
    slot = slot_dt.replace(minute=0, second=0, microsecond=0)
    if slot.hour == 3:
        layer1_offsets = (30, 60, 90)
        layer2_offsets = (0, 30, 60)
    else:
        layer1_offsets = (60, 90, 120)
        layer2_offsets = (30, 60, 90)
    return {
        "layer1": tuple(slot - timedelta(minutes=value) for value in layer1_offsets),
        "layer2": tuple(slot - timedelta(minutes=value) for value in layer2_offsets),
    }


def _valid_m30_ohlc(candle):
    if candle is None:
        return False
    try:
        values = tuple(float(candle[key]) for key in ("open", "high", "low", "close"))
    except (KeyError, TypeError, ValueError):
        return False
    open_price, high_price, low_price, close_price = values
    if not all(math.isfinite(value) for value in values):
        return False
    return high_price >= max(open_price, close_price) and low_price <= min(open_price, close_price) and high_price >= low_price


def _m30_candle_direction(candle):
    if candle is None:
        return None
    if not _valid_m30_ohlc(candle):
        return None
    return exact_candle_direction(candle)


def read_completed_m30_candle_by_open_time(symbol, open_dt, as_of_dt=None):
    """Read one M30 candle by its exact OPEN time that has completed by ``as_of_dt``."""
    if symbol not in SIGNAL_PAIRS:
        return None
    close_dt = open_dt + timedelta(minutes=30)
    cutoff = as_of_dt or close_dt
    if close_dt > cutoff:
        return None
    target_ts = broker_time_to_ts(open_dt, open_dt.hour, open_dt.minute)
    candle = get_candle_by_ts(symbol, mt5.TIMEFRAME_M30, target_ts)
    if candle is None or not _valid_m30_ohlc(candle):
        return None
    try:
        return candle if int(candle["time"]) == int(target_ts) else None
    except (KeyError, TypeError, ValueError):
        return None


def read_completed_m30_candle(symbol, open_dt, completed_by=None):
    """Alias for backwards compatibility."""
    return read_completed_m30_candle_by_open_time(symbol, open_dt, as_of_dt=completed_by)


def read_m30_candle_status(symbol, open_dt, as_of_dt=None):
    """Return (candle_or_none, status_string) with diagnostic detail.

    Delegates to ``read_completed_m30_candle_by_open_time`` for the actual fetch
    so that existing test mocks remain effective.
    """
    if symbol not in SIGNAL_PAIRS:
        return None, "DISABLED"
    close_dt = open_dt + timedelta(minutes=30)
    cutoff = as_of_dt or close_dt
    if close_dt > cutoff:
        return None, "NOT_YET_CLOSED"
    try:
        candle = read_completed_m30_candle_by_open_time(symbol, open_dt, as_of_dt)
    except Exception as error:
        print(f"  [CANDLE] ERROR symbol={symbol} open={open_dt.strftime('%H:%M')} {error}")
        return None, "MT5_FETCH_ERROR"
    if candle is None:
        return None, "MISSING_CANDLE"
    direction = _m30_candle_direction(candle)
    if direction == "DOJI":
        return candle, "DOJI"
    return candle, "READY"


def _empty_m30_candle(role, open_dt, close_dt):
    return {
        "role": role,
        "state": "MISSING",
        "open_time": open_dt.isoformat(),
        "close_time": close_dt.isoformat(),
        "open": None,
        "high": None,
        "low": None,
        "close": None,
        "tick_volume": None,
        "direction": None,
    }


def _m30_candle_evidence_by_open(symbol, role, open_dt, candle):
    close_dt = open_dt + timedelta(minutes=30)
    evidence = _empty_m30_candle(role, open_dt, close_dt)
    if candle is None:
        return evidence
    evidence.update(_serialize_candle_ohlc(candle, symbol))
    evidence.update({"state": "READY", "direction": _m30_candle_direction(candle)})
    return evidence


def _classify_m30_layer_by_open_times(symbol, open_times, candles_by_open, classifier):
    candles = [
        _m30_candle_evidence_by_open(
            symbol,
            f"C{index + 1}{'_BASE' if index == 0 else ''}",
            open_dt,
            candles_by_open.get(open_dt),
        )
        for index, open_dt in enumerate(open_times)
    ]
    directions = [candle.get("direction") for candle in candles]
    classification = classifier(directions)
    return {
        "candles": candles,
        "directions": directions,
        "base_direction": directions[0] if directions else None,
        "group": classification["group"],
        "rule_number": classification["rule_number"],
        "classifier_model": "M30_3_CANDLE_8_CASE",
    }


def _read_m30_open_windows(symbol, open_times, as_of_dt=None):
    return {
        open_dt: read_completed_m30_candle_by_open_time(
            symbol,
            open_dt,
            as_of_dt,
        )
        for open_dt in sorted(set(open_times))
    }


def _read_m30_open_windows_with_status(symbol, open_times, as_of_dt=None):
    """Return {open_dt: (candle_or_none, status_string)}."""
    return {
        open_dt: read_m30_candle_status(symbol, open_dt, as_of_dt)
        for open_dt in sorted(set(open_times))
    }


def get_m30_layer_open_times(slot_dt):
    """Return exact M30 candle OPEN times for Layer 1, 2, and 3. All layers use 3 candles."""
    l1_open = (
        slot_dt - timedelta(minutes=60),
        slot_dt - timedelta(minutes=90),
        slot_dt - timedelta(minutes=120),
    )
    l2_open = (
        slot_dt - timedelta(minutes=30),
        slot_dt - timedelta(minutes=60),
        slot_dt - timedelta(minutes=90),
    )
    l3_open = (
        slot_dt,
        slot_dt - timedelta(minutes=30),
        slot_dt - timedelta(minutes=60),
    )
    return {"layer1": l1_open, "layer2": l2_open, "layer3": l3_open}


def _empty_gbp_signal_evidence(slot_dt, hour, symbol):
    return {
        "symbol": symbol,
        "logic_version": SIGNAL_LOGIC_VERSION,
        "timeframe": "M30",
        "slot_hour": int(hour),
        "source_date": slot_dt.date().isoformat(),
        "layer1": {},
        "direction": "WAIT",
        "entry_time": None,
        "signal_state": "DISABLED" if symbol in DISABLED_SIGNAL_PAIRS else "WAIT",
        "entry_state": "DISABLED" if symbol in DISABLED_SIGNAL_PAIRS else "WAIT",
        "classification_reason": "DISABLED_PAIR" if symbol in DISABLED_SIGNAL_PAIRS else "INCOMPLETE_GBP_M30_SIGNAL_WAIT",
    }


def evaluate_gbp_native_signal_m30(slot_dt, hour, symbol, as_of_dt=None):
    """Evaluate Layer 1 native GBP M30 signal using M30 candle OPEN times."""
    result = _empty_gbp_signal_evidence(slot_dt, hour, symbol)
    if symbol in DISABLED_SIGNAL_PAIRS:
        return result
    if symbol not in GBP_SIGNAL_PAIRS or int(hour) not in ACTIVE_HOURS:
        return result

    windows = get_m30_layer_open_times(slot_dt)
    l1_open_times = windows["layer1"]
    cutoff = as_of_dt or slot_dt
    candles_with_status = _read_m30_open_windows_with_status(symbol, l1_open_times, as_of_dt=cutoff)
    candles = {open_dt: status_pair[0] for open_dt, status_pair in candles_with_status.items()}
    layer1 = _classify_m30_layer_by_open_times(symbol, l1_open_times, candles, classify_three_candle_group)
    signal = derive_gbp_signal_from_layer1(layer1["base_direction"], layer1["group"])
    layer1.update(signal)
    ready = signal["signal"] in ("BUY", "SELL")

    failure_reason = None
    missing_open_times = []
    doji_open_times = []
    invalid_open_times = []
    if not ready:
        for open_dt, (_candle, status) in candles_with_status.items():
            if status == "MISSING_CANDLE":
                missing_open_times.append(open_dt.strftime("%Y-%m-%dT%H:%M:%S"))
            elif status == "DOJI":
                doji_open_times.append(open_dt.strftime("%Y-%m-%dT%H:%M:%S"))
            elif status == "INVALID_CANDLE":
                invalid_open_times.append(open_dt.strftime("%Y-%m-%dT%H:%M:%S"))
        if missing_open_times:
            failure_reason = "MISSING_CANDLE"
        elif invalid_open_times:
            failure_reason = "INVALID_CANDLE"
        elif doji_open_times:
            failure_reason = "DOJI"
        else:
            failure_reason = "CLASSIFIER_UNRESOLVED"

    result.update({
        "layer1": layer1,
        "native_signal": signal["signal"] if ready else "WAIT",
        "direction": signal["signal"] if ready else "WAIT",
        "signal_state": "READY" if ready else "WAIT",
        "classification_reason": "INDEPENDENT_GBP_M30_SIGNAL" if ready else "INCOMPLETE_GBP_M30_SIGNAL_WAIT",
        "failure_reason": failure_reason,
        "missing_open_times": missing_open_times,
        "doji_open_times": doji_open_times,
        "invalid_open_times": invalid_open_times,
    })
    return result


evaluate_gbp_pair_signal_m30 = evaluate_gbp_native_signal_m30


H16_PRIOR_SLOT_PRIORITY = (14, 12, 9, 7, 3)


def classify_entry_branch(source_hour, entry_time):
    """Classify a prior slot's entry into H_11, H_49, or H_PLUS_1_25."""
    if not entry_time:
        return None
    h = int(source_hour)
    if entry_time == f"{h:02d}:11":
        return "H_11"
    if entry_time.endswith(":49"):
        return "H_49"
    if entry_time == f"{h + 1:02d}:25" or (h == 3 and entry_time == "04:25"):
        return "H_PLUS_1_25"
    return None


def resolve_h16_inherited_entry(prior_slot_results):
    """Scan prior slots H14→H12→H9→H7→H3 for nearest eligible entry (XAUUSD backward-compat)."""
    return resolve_h16_inherited_entry_for_symbol("XAUUSD", prior_slot_results)


def resolve_h16_inherited_entry_for_symbol(symbol, prior_slot_results):
    """Scan prior slots for nearest eligible entry for a specific symbol."""
    for source_hour in H16_PRIOR_SLOT_PRIORITY:
        result = prior_slot_results.get(source_hour)
        if not result:
            continue
        pair_entry_states = result.get("pair_entry_states", {})
        pair_entry_times = result.get("pair_entry_times", {})
        if pair_entry_states.get(symbol) != "READY":
            entry_time = result.get("entry_time")
            if result.get("entry_state") != "READY":
                continue
            entry_time = result.get("entry_time")
        else:
            entry_time = pair_entry_times.get(symbol)
        if not entry_time:
            continue
        branch = classify_entry_branch(source_hour, entry_time)
        if branch == "H_11":
            return {
                "symbol": symbol,
                "entry_time": "16:11",
                "entry_state": "READY",
                "entry_rule": "H16_INHERITS_NEAREST_ELIGIBLE_PRIOR_ENTRY",
                "entry_source_hour": source_hour,
                "entry_source_time": entry_time,
                "entry_source_branch": "H_11",
                "entry_candidates": ["16:11", "17:25"],
            }
        if branch == "H_PLUS_1_25":
            return {
                "symbol": symbol,
                "entry_time": "17:25",
                "entry_state": "READY",
                "entry_rule": "H16_INHERITS_NEAREST_ELIGIBLE_PRIOR_ENTRY",
                "entry_source_hour": source_hour,
                "entry_source_time": entry_time,
                "entry_source_branch": "H_PLUS_1_25",
                "entry_candidates": ["16:11", "17:25"],
            }
    return {
        "symbol": symbol,
        "entry_time": None,
        "entry_state": "WAIT",
        "entry_rule": "H16_INHERITS_NEAREST_ELIGIBLE_PRIOR_ENTRY",
        "entry_source_hour": None,
        "entry_source_time": None,
        "entry_source_branch": None,
        "entry_candidates": ["16:11", "17:25"],
        "failure_reason": "NO_ELIGIBLE_PRIOR_ENTRY",
    }


def evaluate_symbol_entry_timing_m30(symbol, slot_dt, hour, as_of_dt=None):
    """Evaluate entry timing for any symbol across Layer 2 and Layer 3 M30 open windows."""
    h = int(hour)
    windows = get_m30_layer_open_times(slot_dt)
    cutoff = as_of_dt or slot_dt

    # Layer 2 evaluation at slot_dt (H:00)
    l2_open_times = windows["layer2"]
    l2_candles = _read_m30_open_windows(symbol, l2_open_times, cutoff)
    l2_classifier = classify_three_candle_group
    layer2 = _classify_m30_layer_by_open_times(symbol, l2_open_times, l2_candles, l2_classifier)

    # Layer 2 BT -> immediate entry at H:11 (03:11 at H3)
    if layer2["group"] == "BT":
        entry_t = "03:11" if h == 3 else f"{h:02d}:11"
        return {
            "symbol": symbol,
            "timeframe": "M30",
            "slot_hour": h,
            "layer2": layer2,
            "layer3": None,
            "entry_time": entry_t,
            "entry_state": "READY",
            "entry_candidates": [entry_t],
            "classification_reason": f"{symbol}_LAYER2_BT_ENTRY",
        }

    # Layer 2 SW -> check Layer 3 if cutoff >= H:30
    h30_dt = slot_dt + timedelta(minutes=30)
    l3_open_times = windows["layer3"]
    if cutoff >= h30_dt:
        l3_candles = _read_m30_open_windows(symbol, l3_open_times, cutoff)
        # Check if the H:00 candle (first in layer3) is available
        h00_candle = l3_candles.get(l3_open_times[0])
        grace_deadline = h30_dt + timedelta(seconds=LAYER3_CANDLE_GRACE_SECONDS)
        if h00_candle is None and cutoff < grace_deadline:
            cand_sw = "03:49" if h == 3 else f"{h:02d}:49"
            cand_bt = "04:25" if h == 3 else f"{h + 1:02d}:25"
            return {
                "symbol": symbol,
                "timeframe": "M30",
                "slot_hour": h,
                "layer2": layer2,
                "layer3": None,
                "entry_time": None,
                "entry_state": "PENDING_LAYER3",
                "entry_candidates": [cand_sw, cand_bt],
                "entry_resolution_time": f"{h:02d}:30",
                "classification_reason": f"{symbol}_LAYER3_CANDLE_PENDING_GRACE",
            }
        layer3 = _classify_m30_layer_by_open_times(symbol, l3_open_times, l3_candles, classify_three_candle_group)
        if layer3["group"] == "SW":
            entry_t = "03:49" if h == 3 else f"{h:02d}:49"
        elif layer3["group"] == "BT":
            entry_t = "04:25" if h == 3 else f"{h + 1:02d}:25"
        else:
            return {
                "symbol": symbol,
                "timeframe": "M30",
                "slot_hour": h,
                "layer2": layer2,
                "layer3": layer3,
                "entry_time": None,
                "entry_state": "WAIT",
                "entry_candidates": [],
                "classification_reason": f"{symbol}_LAYER3_UNRESOLVED",
            }
        return {
            "symbol": symbol,
            "timeframe": "M30",
            "slot_hour": h,
            "layer2": layer2,
            "layer3": layer3,
            "entry_time": entry_t,
            "entry_state": "READY",
            "entry_candidates": [entry_t],
            "classification_reason": f"{symbol}_LAYER3_{layer3['group']}_ENTRY",
        }

    # Still pending Layer 3 (H:00 to H:30)
    cand_sw = "03:49" if h == 3 else f"{h:02d}:49"
    cand_bt = "04:25" if h == 3 else f"{h + 1:02d}:25"
    return {
        "symbol": symbol,
        "timeframe": "M30",
        "slot_hour": h,
        "layer2": layer2,
        "layer3": None,
        "entry_time": None,
        "entry_state": "PENDING_LAYER3",
        "entry_candidates": [cand_sw, cand_bt],
        "entry_resolution_time": f"{h:02d}:30",
        "classification_reason": f"{symbol}_LAYER2_SW_PENDING_LAYER3",
    }


def evaluate_xau_entry_timing_m30(slot_dt, hour, as_of_dt=None):
    """Backward-compatible wrapper — delegates to generic engine with XAUUSD."""
    return evaluate_symbol_entry_timing_m30("XAUUSD", slot_dt, hour, as_of_dt=as_of_dt)


def next_full_hour_after_signal_slot(slot_dt):
    """GBP entry is always the next full Broker hour after the signal slot."""
    return (slot_dt + timedelta(hours=1)).strftime("%H:00")


def _pair_entry_utc_map(slot_dt, pair_entry_times, broker_offset):
    return {
        symbol: compute_utc_iso(slot_dt.date(), pair_entry_times.get(symbol), broker_offset)
        for symbol in SIGNAL_PAIRS
    }


def evaluate_all_pairs_for_slot(broker_dt, hour, as_of_dt=None, prior_slot_results=None, day_mode=None, d_directions=None):
    """Evaluate independent Entry + D-Direction + per-symbol Day Mode for all 5 pairs (v82)."""
    h = int(hour)
    if broker_dt is None or h not in ACTIVE_HOURS:
        return None
    slot_dt = broker_dt.replace(hour=h, minute=0, second=0, microsecond=0)
    eval_dt = as_of_dt or broker_dt
    target_date = broker_dt.date()

    if d_directions is None:
        d_directions = calculate_all_d_directions(target_date)

    # Normalize day_mode input: support both legacy single DayMode and new dict
    if isinstance(day_mode, dict):
        pair_day_modes = dict(day_mode)
    elif isinstance(day_mode, DayMode):
        pair_day_modes = {sym: day_mode for sym in SIGNAL_PAIRS}
    else:
        pair_day_modes = {sym: None for sym in SIGNAL_PAIRS}

    # === PER-SYMBOL ENTRY ENGINE ===
    pair_timings = {}
    for symbol in ENTRY_TIMING_SYMBOLS:
        if h == 16:
            pair_timings[symbol] = resolve_h16_inherited_entry_for_symbol(symbol, prior_slot_results or {})
        else:
            pair_timings[symbol] = evaluate_symbol_entry_timing_m30(symbol, slot_dt, h, as_of_dt=eval_dt)

    pair_dirs = {}
    pair_signal_states = {}
    pair_entry_states = {}
    pair_entry_times = {}
    pair_entry_branches = {}
    pair_labels = {}
    pair_evidence = {}
    pair_groups = {}

    for symbol in SIGNAL_PAIRS:
        if symbol in DISABLED_SIGNAL_PAIRS:
            timing = pair_timings.get(symbol, {})
            sym_entry_time = timing.get("entry_time")
            pair_dirs[symbol] = "WAIT"
            pair_signal_states[symbol] = "DISABLED"
            pair_entry_states[symbol] = "DISABLED"
            pair_entry_times[symbol] = sym_entry_time
            pair_entry_branches[symbol] = None
            pair_labels[symbol] = "OFF"
            pair_groups[symbol] = None
            pair_evidence[symbol] = _empty_gbp_signal_evidence(slot_dt, h, symbol)
            pair_evidence[symbol]["entry_time"] = sym_entry_time
            pair_evidence[symbol]["entry_timing"] = timing
            continue

        timing = pair_timings.get(symbol, {})
        d_info = d_directions.get(symbol, {})
        d_dir = d_info.get("d_direction", "WAIT")
        sym_entry_time = timing.get("entry_time")
        sym_entry_state = timing.get("entry_state", "WAIT")

        pair_entry_times[symbol] = sym_entry_time
        pair_entry_states[symbol] = sym_entry_state

        if h == 16:
            entry_branch = classify_slot_entry_branch(h, sym_entry_time)
            pair_entry_branches[symbol] = entry_branch
            sym_day_mode = pair_day_modes.get(symbol)

            if entry_branch is not None:
                action = resolve_primary_signal_action(sym_day_mode, entry_branch)
                source = "D_DIRECTION"
                h1_ev = None
                if action == "REVERSE_H1":
                    h1_candle, h1_dir = read_previous_h1_candle(symbol, slot_dt, as_of_dt=eval_dt)
                    if h1_dir == "TANG":
                        primary_dir = "SELL"
                    elif h1_dir == "GIAM":
                        primary_dir = "BUY"
                    else:
                        primary_dir = "WAIT"
                    source = "PREVIOUS_COMPLETED_H1"
                    label = "Đảo H1"
                    h1_ev = _build_h1_evidence(symbol, h1_candle, h1_dir, slot_dt)
                elif action == "KEEP_D":
                    primary_dir = d_dir
                    label = "Theo D"
                elif action == "REVERSE_D":
                    primary_dir = ("SELL" if d_dir == "BUY" else "BUY") if d_dir in ("BUY", "SELL") else "WAIT"
                    label = "Đảo D"
                else:
                    primary_dir = "WAIT"
                    source = "NONE"
                    label = "WAIT"
            else:
                if d_dir in ("BUY", "SELL"):
                    action = "KEEP_D"
                    primary_dir = d_dir
                    source = "D_DIRECTION"
                    label = "H16 Theo D"
                else:
                    action = "WAIT"
                    primary_dir = "WAIT"
                    source = "NONE"
                    label = "WAIT"

            final_dir, inversion_rule = apply_new_final_signal_inversion(
                primary_dir, broker_dt, h, source, symbol
            )

            pair_dirs[symbol] = final_dir
            pair_signal_states[symbol] = "READY" if final_dir in ("BUY", "SELL") else "WAIT"
            pair_labels[symbol] = label
            pair_groups[symbol] = None
            pair_evidence[symbol] = {
                "evidence_schema_version": SIGNAL_EVIDENCE_SCHEMA_VERSION,
                "logic_version": SIGNAL_LOGIC_VERSION,
                "date": slot_dt.date().isoformat(),
                "hour": h,
                "symbol": symbol,
                "entry_engine": "INDEPENDENT_THREE_CANDLE_M30_V1",
                "signal_engine": "D_DIRECTION_H16_INDEPENDENT_V2",
                "direction": final_dir,
                "signal_state": pair_signal_states[symbol],
                "current_entry_time": sym_entry_time,
                "current_entry_branch": entry_branch,
                "entry_time": sym_entry_time,
                "entry_branch": entry_branch,
                "day_mode": sym_day_mode.mode if sym_day_mode else None,
                "day_mode_source_hour": sym_day_mode.source_hour if sym_day_mode else None,
                "day_mode_source_entry_time": sym_day_mode.source_entry_time if sym_day_mode else None,
                "day_mode_source_branch": sym_day_mode.source_branch if sym_day_mode else None,
                "primary_source": source,
                "primary_action": action,
                "primary_direction": primary_dir,
                "final_inversion_applied": inversion_rule is not None,
                "final_inversion_rule": inversion_rule,
                "weekday_adjustment_applied": inversion_rule is not None,
                "weekday_adjustment_rule": inversion_rule,
                "d_source_symbol": d_info.get("source_symbol"),
                "d_timeframe": d_info.get("timeframe", "H4"),
                "d_source_open_broker": d_info.get("source_open_time_broker", "20:00"),
                "d_evidence": d_info,
                "h1_evidence": h1_ev,
                "entry_timing": timing,
            }
            continue

        # === H3-H14 signal path ===
        entry_branch = classify_slot_entry_branch(h, sym_entry_time)
        pair_entry_branches[symbol] = entry_branch

        sym_day_mode = pair_day_modes.get(symbol)
        was_anchored = False
        if entry_branch is not None:
            sym_day_mode, was_anchored = resolve_or_anchor_day_mode(sym_day_mode, h, sym_entry_time)
            pair_day_modes[symbol] = sym_day_mode

        if entry_branch is None:
            pair_dirs[symbol] = "WAIT"
            pair_signal_states[symbol] = "WAIT"
            pair_labels[symbol] = "No Entry"
            pair_groups[symbol] = None
            pair_evidence[symbol] = {
                "evidence_schema_version": SIGNAL_EVIDENCE_SCHEMA_VERSION,
                "logic_version": SIGNAL_LOGIC_VERSION,
                "date": slot_dt.date().isoformat(),
                "hour": h,
                "symbol": symbol,
                "entry_engine": "INDEPENDENT_THREE_CANDLE_M30_V1",
                "signal_engine": "D_DIRECTION_DYNAMIC_DAY_MODE_V2",
                "direction": "WAIT",
                "signal_state": "WAIT",
                "current_entry_time": sym_entry_time,
                "current_entry_branch": None,
                "entry_time": sym_entry_time,
                "entry_branch": None,
                "day_mode": sym_day_mode.mode if sym_day_mode else None,
                "day_mode_source_hour": sym_day_mode.source_hour if sym_day_mode else None,
                "day_mode_source_entry_time": sym_day_mode.source_entry_time if sym_day_mode else None,
                "day_mode_source_branch": sym_day_mode.source_branch if sym_day_mode else None,
                "primary_source": None,
                "primary_action": "WAIT",
                "primary_direction": "WAIT",
                "final_inversion_applied": False,
                "final_inversion_rule": None,
                "weekday_adjustment_applied": False,
                "weekday_adjustment_rule": None,
                "d_source_symbol": d_info.get("source_symbol"),
                "d_timeframe": d_info.get("timeframe", "H4"),
                "d_source_open_broker": d_info.get("source_open_time_broker", "20:00"),
                "d_evidence": d_info,
                "h1_evidence": None,
                "entry_timing": timing,
            }
            continue

        action = resolve_primary_signal_action(sym_day_mode, entry_branch)
        h1_ev = None

        if action == "REVERSE_H1":
            h1_candle, h1_dir = read_previous_h1_candle(symbol, slot_dt, as_of_dt=eval_dt)
            if h1_dir == "TANG":
                primary_dir = "SELL"
            elif h1_dir == "GIAM":
                primary_dir = "BUY"
            else:
                primary_dir = "WAIT"
            source = "PREVIOUS_COMPLETED_H1"
            label = "Đảo H1"
            h1_ev = _build_h1_evidence(symbol, h1_candle, h1_dir, slot_dt)
        elif action == "KEEP_D":
            primary_dir = d_dir
            source = "D_DIRECTION"
            label = "Theo D"
        elif action == "REVERSE_D":
            primary_dir = ("SELL" if d_dir == "BUY" else "BUY") if d_dir in ("BUY", "SELL") else "WAIT"
            source = "D_DIRECTION"
            label = "Đảo D"
        else:
            primary_dir = "WAIT"
            source = "NONE"
            label = "WAIT"

        final_dir, inversion_rule = apply_new_final_signal_inversion(
            primary_dir, broker_dt, h, source, symbol
        )

        pair_dirs[symbol] = final_dir
        pair_signal_states[symbol] = "READY" if final_dir in ("BUY", "SELL") else "WAIT"
        pair_labels[symbol] = label
        pair_groups[symbol] = None
        pair_evidence[symbol] = {
            "evidence_schema_version": SIGNAL_EVIDENCE_SCHEMA_VERSION,
            "logic_version": SIGNAL_LOGIC_VERSION,
            "date": slot_dt.date().isoformat(),
            "hour": h,
            "symbol": symbol,
            "entry_engine": "INDEPENDENT_THREE_CANDLE_M30_V1",
            "signal_engine": "D_DIRECTION_DYNAMIC_DAY_MODE_V2",
            "direction": final_dir,
            "signal_state": pair_signal_states[symbol],
            "current_entry_time": sym_entry_time,
            "current_entry_branch": entry_branch,
            "entry_time": sym_entry_time,
            "entry_branch": entry_branch,
            "day_mode": sym_day_mode.mode if sym_day_mode else None,
            "day_mode_source_hour": sym_day_mode.source_hour if sym_day_mode else None,
            "day_mode_source_entry_time": sym_day_mode.source_entry_time if sym_day_mode else None,
            "day_mode_source_branch": sym_day_mode.source_branch if sym_day_mode else None,
            "primary_source": source,
            "primary_action": action,
            "primary_direction": primary_dir,
            "final_inversion_applied": inversion_rule is not None,
            "final_inversion_rule": inversion_rule,
            "weekday_adjustment_applied": inversion_rule is not None,
            "weekday_adjustment_rule": inversion_rule,
            "d_source_symbol": d_info.get("source_symbol"),
            "d_timeframe": d_info.get("timeframe", "H4"),
            "d_source_open_broker": d_info.get("source_open_time_broker", "20:00"),
            "d_evidence": d_info,
            "h1_evidence": h1_ev,
            "entry_timing": timing,
        }

    top_signal = pair_dirs.get("XAUUSD", "WAIT")
    top_entry = pair_entry_times.get("XAUUSD")
    top_signal_state = pair_signal_states.get("XAUUSD", "WAIT")
    top_entry_state = pair_entry_states.get("XAUUSD", "WAIT")
    xau_timing = pair_timings.get("XAUUSD", {})

    try:
        broker_offset = BROKER_CLOCK.utc_offset_for_date(slot_dt.date())
    except Exception:
        broker_offset = None

    xau_dm = pair_day_modes.get("XAUUSD")
    day_mode_state = "RESOLVED" if any(pair_day_modes.values()) else "UNRESOLVED_WAITING_FOR_ANCHOR"

    return {
        "logic_version": SIGNAL_LOGIC_VERSION,
        "record_revision": 2 if top_signal in ("BUY", "SELL") else 1,
        "state_updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "signal": top_signal,
        "entry_time": top_entry,
        "signal_state": top_signal_state,
        "entry_state": top_entry_state,
        "entry_candidate": top_entry,
        "entry_candidates": xau_timing.get("entry_candidates"),
        "entry_resolution_time": xau_timing.get("entry_resolution_time"),
        "entry_rule": "D_DIRECTION_DAY_MODE" if top_entry else None,
        "entry_at_utc": compute_utc_iso(slot_dt.date(), top_entry, broker_offset),
        "broker_utc_offset": broker_offset,
        "pair_dirs": pair_dirs,
        "pair_signal_states": pair_signal_states,
        "pair_entry_states": pair_entry_states,
        "pair_entry_times": pair_entry_times,
        "pair_entry_branches": pair_entry_branches,
        "pair_entry_at_utc": _pair_entry_utc_map(slot_dt, pair_entry_times, broker_offset),
        "pair_labels": pair_labels,
        "pair_groups": pair_groups,
        "pair_evidence": pair_evidence,
        "source_date": target_date.isoformat(),
        "day_mode": xau_dm,
        "pair_day_modes": {s: dm.mode if dm else None for s, dm in pair_day_modes.items()},
        "pair_day_mode_states": {s: "RESOLVED" if dm else "UNRESOLVED_WAITING_FOR_ANCHOR" for s, dm in pair_day_modes.items()},
        "pair_day_mode_source_hours": {s: dm.source_hour if dm else None for s, dm in pair_day_modes.items()},
        "pair_day_mode_source_entry_times": {s: dm.source_entry_time if dm else None for s, dm in pair_day_modes.items()},
        "pair_day_mode_source_branches": {s: dm.source_branch if dm else None for s, dm in pair_day_modes.items()},
        "day_mode_state": day_mode_state,
        "day_mode_source_hour": xau_dm.source_hour if xau_dm else None,
        "day_mode_source_entry_time": xau_dm.source_entry_time if xau_dm else None,
        "day_mode_source_branch": xau_dm.source_branch if xau_dm else None,
        "d_directions": d_directions,
        "report": f"H={h} signal={top_signal} entry={top_entry}",
        "timing": xau_timing,
        "_pair_day_modes_objects": pair_day_modes,
    }


def _three_layer_m30_report(hour, slot_dt, pair_evidence):
    lines = [f"H={hour} ({slot_dt.date().isoformat()}) [v{SIGNAL_LOGIC_VERSION}] D-Direction + Day Mode:"]
    for symbol in DISPLAY_SIGNAL_PAIRS:
        item = pair_evidence.get(symbol, {})
        lines.append(
            f"  {symbol}: {item.get('direction', 'WAIT')} entry={item.get('entry_time') or 'OFF'}"
        )
    return "\n".join(lines)


def repair_history(target_dates=None, days=45):
    """Targeted repair of historical records with unresolved native signals."""
    if not mt5_ready:
        print("  [REPAIR] MT5 not ready")
        return 0

    broker_dt = get_broker_time()
    today = broker_dt.date()

    if target_dates:
        dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in target_dates]
    else:
        dates = [today - timedelta(days=i) for i in range(days)]

    oldest = min(dates)
    warm_start = datetime.combine(oldest - timedelta(days=2), datetime.min.time())
    warm_m30_history(["XAUUSD", "GBPUSD", "GBPAUD"], warm_start, broker_dt)

    attempted = 0
    ready_count = 0
    doji_count = 0
    missing_count = 0
    updated = 0
    updated_records_list = []
    for target_date in sorted(dates):
        if target_date.weekday() >= 5:
            continue
        hours = get_target_hours(datetime.combine(target_date, datetime.min.time()))
        day_results = {}
        current_pair_day_modes = {sym: None for sym in SIGNAL_PAIRS}
        for hour in hours:
            slot_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=hour)
            rebuild_as_of = broker_dt if target_date == today else slot_dt + timedelta(days=1)
            try:
                record, next_day_modes = _build_rebuild_record(
                    slot_dt, hour, as_of_dt=rebuild_as_of,
                    prior_slot_results=day_results if hour == 16 else None,
                    day_mode=current_pair_day_modes,
                )
                if isinstance(next_day_modes, dict):
                    for sym, dm in next_day_modes.items():
                        if dm is not None:
                            current_pair_day_modes[sym] = dm
                attempted += 1
                day_results[hour] = record
                sig = record.get("signal", "WAIT")
                entry_state = record.get("entry_state", "WAIT")

                if sig in ("BUY", "SELL") and entry_state == "READY":
                    ready_count += 1
                else:
                    ready_count += 1

                date_str = record["date"]
                hour_val = int(record["hour"])
                if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
                    with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                        data = json.load(f)
                    existing = [r for r in data
                                if r.get("date") == date_str and int(r.get("hour", -1)) == hour_val]
                    if existing:
                        old = existing[0]
                        if (old.get("signal") == record.get("signal")
                                and old.get("pair_dirs") == record.get("pair_dirs")
                                and old.get("entry_state") == record.get("entry_state")):
                            continue
                    data = [r for r in data
                            if not (r.get("date") == date_str and int(r.get("hour", -1)) == hour_val)]
                    data.append(record)
                    _write_signals_log_atomic(data)
                    updated += 1
                    updated_records_list.append(record)
            except Exception as error:
                print(f"  [REPAIR] ERROR date={target_date.isoformat()} H={hour}"
                      f" error_type={type(error).__name__}: {error}")

    print(f"  [REPAIR] Attempted: {attempted}")
    print(f"  [REPAIR] READY: {ready_count}")
    print(f"  [REPAIR] DOJI: {doji_count}")
    print(f"  [REPAIR] DATA_MISSING: {missing_count}")
    print(f"  [REPAIR] Updated: {updated}")
    clear_history_cache()
    return {"updated": updated, "attempted": attempted, "ready": ready_count, "doji": doji_count, "data_missing": missing_count, "records": updated_records_list}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=str, help="Profile name for heartbeat")
    parser.add_argument("--repair-history", action="store_true",
                        help="Repair historical records with unresolved native signals")
    parser.add_argument("--repair-date", type=str, action="append",
                        help="Repair specific date (YYYY-MM-DD), repeatable")
    parser.add_argument("--rebuild-all", action="store_true",
                        help="Full deterministic rebuild of recent history")
    parser.add_argument("--rebuild-d-history", action="store_true",
                        help="Rebuild D-Direction history snapshots")
    parser.add_argument("--repair-d-date", type=str,
                        help="Repair D-Direction snapshot for specific date YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=45,
                        help="Number of days for rebuild (default: 45)")
    args, _ = parser.parse_known_args()

    if args.repair_history or args.repair_date:
        if not (mt5.initialize(path=MT5_PATH) if MT5_PATH else mt5.initialize()):
            print("[REPAIR] MT5 init failed")
        else:
            mt5_ready = True
            BROKER_CLOCK.clear_cache()
            try:
                result = repair_history(target_dates=args.repair_date)
                if result["updated"] > 0:
                    push_to_dashboard(snapshot_complete=False)
            finally:
                mt5.shutdown()
    elif args.rebuild_all:
        if not (mt5.initialize(path=MT5_PATH) if MT5_PATH else mt5.initialize()):
            print("[REBUILD] MT5 init failed")
        else:
            mt5_ready = True
            BROKER_CLOCK.clear_cache()
            try:
                rebuild_recent_history(days=args.days)
                push_to_dashboard(snapshot_complete=True)
            finally:
                mt5.shutdown()
    elif args.rebuild_d_history:
        if not (mt5.initialize(path=MT5_PATH) if MT5_PATH else mt5.initialize()):
            print("[REBUILD-D] MT5 init failed")
        else:
            mt5_ready = True
            BROKER_CLOCK.clear_cache()
            try:
                rebuild_d_direction_history(days=args.days)
            finally:
                mt5.shutdown()
    elif args.repair_d_date:
        if not (mt5.initialize(path=MT5_PATH) if MT5_PATH else mt5.initialize()):
            print("[REPAIR-D] MT5 init failed")
        else:
            mt5_ready = True
            BROKER_CLOCK.clear_cache()
            try:
                repair_d_direction_date(args.repair_d_date)
            finally:
                mt5.shutdown()
    else:
        main(profile_name=args.profile)


