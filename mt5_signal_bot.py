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
from typing import Protocol, Optional

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
from domain.signal_v87 import (
    PAIRS as V87_PAIRS,
    evaluate_slot as evaluate_v87_slot,
    build_entry_plan as build_v87_entry_plan,
    final_reverse as final_reverse_v87,
)
from domain.mt5_execution import MT5ExecutionGateway
from services.mt5_terminal_service import ensure_mt5_profile_connected

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


SIGNAL_LOGIC_VERSION = 87
ACTIVE_SIGNAL_LOGIC_VERSION = 87
MINIMUM_SIGNAL_LOGIC_VERSION = 87
SIGNAL_EVIDENCE_SCHEMA_VERSION = 9
LAYER3_CANDLE_GRACE_SECONDS = 90
D_DIRECTION_SCHEMA_VERSION = 9
D_PUBLICATION_STATE_SCHEMA_VERSION = 2
DASHBOARD_TRANSPORT_SCHEMA_VERSION = 3
SIGNAL_SUMMARY_SCHEMA_VERSION = 3
MARKET_DATA_PROVIDER_SCHEMA_VERSION = 2
HEARTBEAT_SCHEMA_VERSION = 2
D_SESSION_POLICY = {
    "normal_close_broker": "23:00",
    "timeframe_minutes": 30,
    "allow_early_close": True,
}
ACTIVE_SIGNAL_PAIRS = ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
DISABLED_SIGNAL_PAIRS = ()
GBP_SIGNAL_PAIRS = ("GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
SIGNAL_PAIRS = ("XAUUSD", *GBP_SIGNAL_PAIRS)
DISPLAY_SIGNAL_PAIRS = ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
EVIDENCE_SIGNAL_PAIRS = ("XAUUSD",)
ENTRY_TIMING_SYMBOLS = ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
D_SOURCE_SYMBOL = {symbol: symbol for symbol in SIGNAL_PAIRS}


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
# Keep one explicit storage handle for scheduler code and older integrations.
# The signal engine never uses this as a market-data source.
store = _store
_active_profile = ""  # Module-level, set by main() at startup
_signal_execution_gateway = None


def _as_bool(value):
    """Parse an explicit boolean setting without enabling live execution implicitly."""
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _get_signal_execution_gateway():
    """Build the MT5 gateway lazily so importing the signal engine sends no orders."""
    global _signal_execution_gateway
    if _signal_execution_gateway is not None:
        return _signal_execution_gateway
    profile_cfg = load_profile_config(_active_profile)
    enabled = _as_bool(os.environ.get("SIGNAL_BOT_EXECUTION_ENABLED", profile_cfg.get("signal_execution_enabled")))
    try:
        volume = float(profile_cfg.get("signal_lot", profile_cfg.get("copy_lot_value", 0.01)))
    except (TypeError, ValueError):
        volume = 0.01
    try:
        magic = int(profile_cfg.get("signal_magic", 87000))
    except (TypeError, ValueError):
        magic = 87000
    _signal_execution_gateway = MT5ExecutionGateway(
        mt5,
        store,
        enabled=enabled,
        volume=volume,
        magic=magic,
        symbol_resolver=resolve_mt5_symbol,
    )
    return _signal_execution_gateway


def schedule_orders_for_signal(result, broker_dt, hour):
    """Persist common-entry MT5 intents; actual sends require explicit opt-in."""
    if not result or broker_dt is None:
        return []
    try:
        return _get_signal_execution_gateway().schedule_signal(result, broker_dt.date(), hour)
    except Exception as error:
        log.warning("Signal execution intent scheduling failed for H=%s: %s", hour, error)
        return []


def process_pending_execution_orders():
    """Retry due intents only while MT5 is connected; MT4 remains clock authority."""
    if not mt5_ready:
        return []
    try:
        return _get_signal_execution_gateway().process_due()
    except Exception as error:
        log.warning("Signal execution retry failed: %s", error)
        return []

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

    feed_health = MARKET_DATA_PROVIDER.get_health() if hasattr(MARKET_DATA_PROVIDER, "get_health") else None
    data_state = getattr(feed_health, "state", "disconnected") if feed_health else "disconnected"
    state = "connected" if mt5_connected else "degraded" if mt5_error else "disconnected"
    broker_offset = None
    broker_time = ""
    broker_observed_at_utc = ""
    if broker_dt is not None:
        try:
            try:
                broker_offset = MARKET_DATA_PROVIDER.get_broker_utc_offset(broker_dt.date())
            except TypeError:
                broker_offset = MARKET_DATA_PROVIDER.get_broker_utc_offset()
        except Exception:
            broker_offset = None
        broker_time = broker_dt.replace(microsecond=0).isoformat()
        broker_observed_at_utc = feed_health.observed_at_utc if feed_health else ""
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
        data_provider="MT4",
        data_state=data_state,
        data_observed_at_utc=feed_health.observed_at_utc if feed_health else "",
        execution_provider="MT5",
        execution_state="connected" if mt5_connected else "disconnected",
    )


# =====================================================================
# STATE PERSISTENCE - survive bot restarts
# =====================================================================
_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_state.json")

def _trading_date():
    """Current trading date in broker time."""
    return get_broker_time().date()

def _load_state():
    """Load restart-safe sent-slot, signal-alert, and D publication state.

    Supports three legacy formats for d_publication_state:
      A. Legacy list: ["2026-07-31"] -> migrated as UNKNOWN_LEGACY, acknowledged=False
      B. Legacy set from runtime (also iterable non-dict).
      C. New metadata dictionary with snapshot_state, dashboard_acknowledged, etc.

    Legacy dates are intentionally NOT treated as READY/acknowledged — they must
    be re-verified against the actual Dashboard state before being considered complete.
    """
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

    # Support both old key (d_published_local_dates) and new key (d_publication_state).
    raw_pub_state = data.get("d_publication_state") or data.get("d_published_local_dates", {})
    if isinstance(raw_pub_state, (list, set)):
        # Legacy list/set: migrate to UNKNOWN_LEGACY — NOT acknowledged, NOT READY.
        pub_state = {
            str(d): {
                "snapshot_state": "UNKNOWN_LEGACY",
                "dashboard_acknowledged": False,
                "schema_version": D_PUBLICATION_STATE_SCHEMA_VERSION,
            }
            for d in raw_pub_state
        }
    elif isinstance(raw_pub_state, dict):
        pub_state = raw_pub_state
    else:
        pub_state = {}

    last_success = data.get("d_last_success_at")

    today_str = _trading_date().isoformat()
    if data.get("date") != today_str:
        res = {}
        if pub_state:
            res["d_publication_state"] = pub_state
        if last_success is not None:
            res["d_last_success_at"] = last_success
        return res

    stored_ver = data.get("signal_logic_version")
    if stored_ver != SIGNAL_LOGIC_VERSION:
        print(f"  [STATE] Dropping stale sent_today: stored version={stored_ver or 'legacy'}, current version={SIGNAL_LOGIC_VERSION}")
        return {
            "sent_today": set(),
            "signal_alerts_sent": set(),
            "signal_alerts_pending": {},
            "d_publication_state": pub_state,
            "d_last_success_at": last_success,
        }

    restored_sent = set()
    for raw_date, raw_hour in data.get("sent_today", []):
        try:
            restored_date = datetime.strptime(str(raw_date), "%Y-%m-%d").date()
            restored_sent.add((restored_date, int(raw_hour)))
        except (TypeError, ValueError):
            continue

    alerts_sent = set(data.get("signal_alerts_sent", []))
    alerts_pending = data.get("signal_alerts_pending", {})
    if not isinstance(alerts_pending, dict):
        alerts_pending = {}

    return {
        "sent_today": restored_sent,
        "signal_alerts_sent": alerts_sent,
        "signal_alerts_pending": alerts_pending,
        "d_publication_state": pub_state,
        "d_last_success_at": last_success,
    }


def _save_state(sent_today=None, broker_dt=None, d_published_local_dates=None,
                d_publication_state=None, d_last_success_at=None):
    """Persist sent logical slots, signal alerts, and D-Direction publication state.

    Accepts both legacy `d_published_local_dates` kwarg (for backward compat in tests)
    and new `d_publication_state` dict. The new key takes priority.
    The metadata dict is always written as-is — never converted to sorted list.
    """
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
        try:
            broker_utc_offset = MARKET_DATA_PROVIDER.get_broker_utc_offset(broker_now.date())
        except TypeError:
            broker_utc_offset = MARKET_DATA_PROVIDER.get_broker_utc_offset()
    except Exception as error:
        print(f"[WARN] Cannot attach Broker clock metadata to state: {error}")
        broker_utc_offset = None
    has_verified_clock = broker_utc_offset is not None

    existing = _load_state()
    # d_publication_state (new key) takes priority over legacy d_published_local_dates kwarg.
    if d_publication_state is not None:
        pub_state = d_publication_state
    elif d_published_local_dates is not None:
        # Legacy kwarg provided — accept as-is (may be dict from old tests)
        pub_state = d_published_local_dates
    else:
        pub_state = existing.get("d_publication_state", {})
    last_success = d_last_success_at if d_last_success_at is not None else existing.get("d_last_success_at")

    health = MARKET_DATA_PROVIDER.get_health() if hasattr(MARKET_DATA_PROVIDER, "get_health") else None
    data_state = getattr(health, "state", "disconnected") if health else "disconnected"

    data = {
        "date": today_str,
        "signal_logic_version": SIGNAL_LOGIC_VERSION,
        "sent_today": sent_rows,
        "signal_alerts_sent": sorted(list(signal_alerts_sent)),
        "signal_alerts_pending": signal_alerts_pending,
        "broker_time": broker_now.replace(microsecond=0).isoformat() if has_verified_clock else "",
        "broker_utc_offset": broker_utc_offset,
        "broker_observed_at_utc": health.observed_at_utc if has_verified_clock and health else "",
        "d_publication_state": pub_state,
        "data_provider": "MT4",
        "data_state": data_state,
        "data_observed_at_utc": health.observed_at_utc if health else "",
        "execution_provider": "MT5",
        "execution_state": "connected" if mt5_ready else "disconnected",
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
               pattern_signal=None, source_date=None, extra_fields=None):
    """Append signal data to signals_log.json for website consumption."""
    record = _format_signal_record(
        H, broker_dt, sig, entry_time, pair_dirs, hour_note,
        pattern_signal=pattern_signal,
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
                          pattern_signal=None, source_date=None, extra_fields=None):
    """Build one signal record dict without persisting."""
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
        "logic_version": SIGNAL_LOGIC_VERSION,
    }
    signal_hour, signal_minute = (int(part) for part in signal_time.split(":"))
    signal_broker_dt = broker_dt.replace(
        hour=signal_hour,
        minute=signal_minute,
        second=0,
        microsecond=0,
    )
    try:
        try:
            broker_offset = MARKET_DATA_PROVIDER.get_broker_utc_offset(broker_dt.date())
        except TypeError:
            broker_offset = MARKET_DATA_PROVIDER.get_broker_utc_offset()
        signal_utc = (signal_broker_dt - timedelta(hours=broker_offset)).replace(tzinfo=timezone.utc)
        health = MARKET_DATA_PROVIDER.get_health()
        clock_verified = bool(health.fresh and getattr(health, "clock_verified", True))
    except Exception:
        broker_offset = None
        signal_utc = None
        clock_verified = False

    record["signal_at_utc"] = signal_utc.isoformat() if signal_utc else None
    record["broker_utc_offset"] = broker_offset
    record["broker_clock_verified"] = clock_verified
    record["broker_timestamp_mode"] = "MT4_FEED"
    record["signal_time_local"] = (
        _broker_time_to_local(signal_time, broker_offset)
        if broker_offset is not None and clock_verified else None
    )
    record["entry_time_local"] = (
        _broker_time_to_local(entry_time, broker_offset)
        if entry_time and broker_offset is not None and clock_verified else None
    )
    if pattern_signal:
        record["pattern_signal"] = pattern_signal
    if source_date:
        record["source_date"] = source_date
    if extra_fields and isinstance(extra_fields, dict):
        for k, v in extra_fields.items():
            if k not in ("date", "hour", "ts", "signal", "pair_dirs", "signal_time", "deactivated"):
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
    if signal_record.get("broker_clock_verified") is not True:
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
                for batch_index, batch in enumerate(
                    split_records_by_encoded_size(signals, max_records=20, max_bytes=350 * 1024)
                ):
                    clears_snapshot = snapshot_complete and batch_index == 0
                    body = {
                        "clear_all": clears_snapshot,
                        "source": "mt5_signal_bot",
                        "logic_version": SIGNAL_LOGIC_VERSION,
                        "records": batch,
                    }
                    payload = json.dumps(body).encode("utf-8")
                    endpoint = "/api/signals/history/batch"
                    req = urllib.request.Request(
                        f"{dashboard_url}{endpoint}",
                        data=payload,
                        headers=headers
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=15) as resp:
                            status = resp.status
                            resp.read()
                        print(
                            f"[DASHBOARD] POST {endpoint} records={len(batch)} "
                            f"bytes={len(payload)} status={status}"
                        )
                    except urllib.error.HTTPError as http_err:
                        if http_err.code == 413:
                            print(
                                f"[DASHBOARD] POST {endpoint} records={len(batch)} "
                                f"bytes={len(payload)} status=413 action=split"
                            )
                            # Retry with half batch size
                            half = max(1, len(batch) // 2)
                            for sub_index, i in enumerate(range(0, len(batch), half)):
                                sub = batch[i:i+half]
                                sub_body = {
                                    "clear_all": clears_snapshot and sub_index == 0,
                                    "source": "mt5_signal_bot",
                                    "logic_version": SIGNAL_LOGIC_VERSION,
                                    "records": sub,
                                }
                                sub_payload = json.dumps(sub_body).encode("utf-8")
                                try:
                                    req2 = urllib.request.Request(
                                        f"{dashboard_url}{endpoint}",
                                        data=sub_payload,
                                        headers=headers
                                    )
                                    with urllib.request.urlopen(req2, timeout=15) as resp2:
                                        status2 = resp2.status
                                        resp2.read()
                                    print(
                                        f"[DASHBOARD] POST {endpoint} records={len(sub)} "
                                        f"bytes={len(sub_payload)} status={status2} (retry after 413)"
                                    )
                                except Exception as retry_err:
                                    print(f"[DASHBOARD] Retry sub-batch FAILED: {retry_err}")
                        else:
                            raise
                print(f"[DASHBOARD] Signals pushed OK ({len(signals)} items, snapshot={snapshot_complete})")
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
    """Build one versioned XAUUSD entry-evidence record for the dashboard."""
    pair_evidence = result.get("pair_evidence") or {}
    logic_version = result.get("logic_version", SIGNAL_LOGIC_VERSION)
    source_date = broker_dt.date().isoformat()
    records = {}
    for symbol in ("XAUUSD",):
        raw_evidence = pair_evidence.get(symbol)
        if not raw_evidence:
            continue
        evidence = dict(raw_evidence or {})
        timing = result.get("timing") if isinstance(result.get("timing"), dict) else {}
        timeframe = str(timing.get("timeframe") or result.get("entry_timeframe") or "M30").upper()
        default_entry_rule = "XAUUSD_H1_ENTRY_PLAN" if timeframe == "H1" else "XAUUSD_M30_ENTRY_PLAN"
        evidence.update({
            "logic_version": logic_version,
            "date": source_date,
            "hour": int(hour),
            "symbol": symbol,
            "entry_time": result.get("entry_time") or (result.get("pair_entry_times") or {}).get(symbol),
            "entry_state": result.get("entry_state") or (result.get("pair_entry_states") or {}).get(symbol),
            "entry_rule": evidence.get("entry_rule") or default_entry_rule,
            "signal_state": (result.get("pair_signal_states") or {}).get(symbol),
        })
        key = f"{source_date}:{int(hour)}:{symbol}:v{logic_version}"
        records[key] = evidence
    return records


def push_signal_evidence(broker_dt, hour, result):
    """Push the single XAUUSD entry-evidence source to the dashboard."""
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
    """Convert Broker wall time to UTC using the MT4 heartbeat offset."""
    target_broker = broker_dt.replace(hour=hour, minute=minute, second=second, microsecond=0)
    try:
        offset = MARKET_DATA_PROVIDER.get_broker_utc_offset(broker_dt.date())
    except TypeError:
        offset = MARKET_DATA_PROVIDER.get_broker_utc_offset()
    return int((target_broker - timedelta(hours=offset)).replace(tzinfo=timezone.utc).timestamp())

# =====================================================================
# MT4 FEED CANDLE HELPER
# =====================================================================
def get_candle_by_ts(symbol, timeframe, target_ts, use_mt5_fallback=False):
    """Lay nến gan nhat voi UTC timestamp. Tra ve dict hoac None."""
    key = (symbol, timeframe, int(target_ts))
    cached = _cache.get(key)
    if cached is not None and abs(int(cached["time"]) - int(target_ts)) <= 180:
        return cached

    if MARKET_DATA_PROVIDER and getattr(MARKET_DATA_PROVIDER, "name", "") == "MT4":
        try:
            utc_target = datetime.fromtimestamp(target_ts, tz=timezone.utc).replace(tzinfo=None)
            candidate_dates = (utc_target.date(), utc_target.date() - timedelta(days=1), utc_target.date() + timedelta(days=1))
            for broker_date in candidate_dates:
                try:
                    offset = MARKET_DATA_PROVIDER.get_broker_utc_offset(broker_date)
                except TypeError:
                    offset = MARKET_DATA_PROVIDER.get_broker_utc_offset()
                broker_open = utc_target + timedelta(hours=offset)
                exact = MARKET_DATA_PROVIDER.get_exact_bar(symbol, _provider_timeframe(timeframe), broker_open)
                if exact:
                    _cache[key] = exact
                    return exact
        except Exception:
            return None
        return None

    # Query a narrow range around the target open timestamp.
    rates = _provider_bars_near_timestamp(symbol, timeframe, target_ts, use_mt5_fallback=use_mt5_fallback)
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
        norm = normalize_mt5_rate_row(best) if not isinstance(best, dict) or "canonical_symbol" not in best else best
        _cache[key] = norm
        if "time" in norm:
            _cache[(symbol, timeframe, int(norm["time"]))] = norm
        return norm
    return None


def get_candle_by_broker_datetime(symbol, timeframe, broker_open_dt, use_mt5_fallback=False):
    """Fetch one candle by Broker open datetime using canonical timestamp encoding."""
    if MARKET_DATA_PROVIDER and getattr(MARKET_DATA_PROVIDER, "name", "") == "MT4":
        return MARKET_DATA_PROVIDER.get_exact_bar(symbol, _provider_timeframe(timeframe), broker_open_dt)
    return None



def _provider_bars_near_timestamp(symbol, timeframe, target_ts, use_mt5_fallback=False):
    """Load an exact historical window using MARKET_DATA_PROVIDER (MT4 Feed)."""
    if not MARKET_DATA_PROVIDER or getattr(MARKET_DATA_PROVIDER, "name", "") != "MT4":
        return None
    try:
        utc_target = datetime.fromtimestamp(target_ts, tz=timezone.utc).replace(tzinfo=None)
        try:
            offset = MARKET_DATA_PROVIDER.get_broker_utc_offset(utc_target.date())
        except TypeError:
            offset = MARKET_DATA_PROVIDER.get_broker_utc_offset()
        broker_target = utc_target + timedelta(hours=offset)
        return MARKET_DATA_PROVIDER.get_bars(symbol, _provider_timeframe(timeframe), broker_target - timedelta(minutes=3), broker_target + timedelta(minutes=3))
    except Exception:
        return None


def _provider_timeframe(timeframe):
    return {30: "M30", 60: "H1", 240: "H4", 16385: "M30", 16388: "H4", "30": "M30", "60": "H1", "240": "H4", "16385": "M30", "16388": "H4"}.get(timeframe, str(timeframe).upper())


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
    "entry_branch",
    "entry_candidates",
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
    "failure_reason",
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
    "core_signal",
    "core_signals",
    "final_reverse_applied",
    "final_reverse_reason",
    "pair_d_directions",
    "pair_d_relations",
    "pair_relation_rules",
    "reference_d_symbol",
    "reference_d_direction",
    "entry_timeframe",
    "entry_source_symbol",
    "timing",
    "entry_plan",
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
        }
    result = evaluate_all_pairs_for_slot(broker_dt, hour, day_mode=day_mode, d_directions=d_directions)
    if result is None:
        return {
            "signal": "WAIT",
            "report": f"H={hour}: incomplete D-Direction + Day Mode data.",
        }
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
        "GBPUSD is the Reference Signal; XAUUSD provides the shared Entry Plan "
        "and D relations derive the remaining pair directions."
    )


GBP_PAIRS = list(GBP_SIGNAL_PAIRS)
ALL_PAIRS = list(SIGNAL_PAIRS)

sent_today = set()
_d_directions_today = {}
signal_alerts_sent = set()
signal_alerts_pending = {}


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
        "startup_summary": "v87 canonical signal engine",
    }





def build_startup_telegram_message(broker_dt, mt5_connected, rule_contract=None):
    """Build compact startup Telegram message per canonical contract."""
    ver = SIGNAL_LOGIC_VERSION
    mt5_status = "✅ CONNECTED" if mt5_connected else "⚠️ DISCONNECTED"
    feed_health = MARKET_DATA_PROVIDER.get_health() if hasattr(MARKET_DATA_PROVIDER, "get_health") else None
    feed_state = getattr(feed_health, "state", "disconnected") if feed_health else "disconnected"
    broker_time_str = "--:--"
    if broker_dt is not None:
        try:
            broker_time_str = broker_dt.strftime("%H:%M")
        except Exception:
            pass
    return (
        f"🤖 OAK SIGNAL BOT ONLINE · v{ver}\n"
        f"MT4 Feed: {feed_state.upper()} · MT5: {mt5_status}\n"
        f"Broker Clock: {broker_time_str}\n"
        "Slots: H3 · H7 · H9 · H12 · H14 · H16"
    )


def _signal_date(record):
    return str(record.get("source_date") or record.get("date") or "")


def _signal_directions(record):
    directions = record.get("pair_dirs") or {}
    return tuple((symbol, str(directions.get(symbol, "WAIT"))) for symbol in DISPLAY_SIGNAL_PAIRS)


def build_signal_alert_fingerprint(record):
    """Deduplicate by logic/date/slot/revision/directions, never Entry metadata."""
    try:
        hour = int(record.get("hour"))
    except (TypeError, ValueError):
        hour = -1
    directions = ";".join(f"{symbol}={direction}" for symbol, direction in _signal_directions(record))
    return "|".join((
        str(record.get("logic_version", SIGNAL_LOGIC_VERSION)),
        _signal_date(record), str(hour), str(record.get("record_revision", 1)), directions,
    ))


def _signal_base_prefix(record):
    return "|".join((
        str(record.get("logic_version", SIGNAL_LOGIC_VERSION)),
        _signal_date(record), str(int(record.get("hour"))),
    )) + "|"


def _sent_same_signal_directions(record, sent_fingerprints=None):
    prefix = _signal_base_prefix(record)
    directions = ";".join(f"{symbol}={direction}" for symbol, direction in _signal_directions(record))
    sent = signal_alerts_sent if sent_fingerprints is None else sent_fingerprints
    return any(str(item).startswith(prefix) and str(item).split("|", 4)[-1] == directions for item in sent)


def build_signal_telegram_message(record, broker_dt=None, updated=False):
    """Build the compact Signal-only message; Entry stays on the web dashboard."""
    try:
        hour = int(record.get("hour"))
    except (TypeError, ValueError):
        return None
    if hour not in ACTIVE_HOURS:
        return None
    lines = [("SIGNAL UPDATED" if updated else "🚨 SIGNAL") + f" H{hour}"]
    for symbol, direction in _signal_directions(record):
        icon = "🟢" if direction == "BUY" else "🔴" if direction == "SELL" else "⚪"
        lines.append(f"{symbol}: {icon} {direction}")
    if broker_dt is not None:
        lines.append(f"Logic v{record.get('logic_version', SIGNAL_LOGIC_VERSION)} · Broker {broker_dt.strftime('%H:%M')}")
    return "\n".join(lines)


def should_send_signal_alert(record, sent_fingerprints=None):
    if not isinstance(record, dict) or record.get("signal") not in ("BUY", "SELL"):
        return False
    if record.get("signal_state", "READY") != "READY" or record.get("entry_state") != "READY":
        return False
    if any(direction not in ("BUY", "SELL") for _, direction in _signal_directions(record)):
        return False
    return not _sent_same_signal_directions(record, sent_fingerprints)


def send_signal_alert(record, broker_dt=None):
    """Send a decision alert once and queue transient delivery failures."""
    if broker_dt is not None and _signal_date(record) != broker_dt.date().isoformat():
        return False
    if not should_send_signal_alert(record, signal_alerts_sent):
        return True
    updated = any(str(item).startswith(_signal_base_prefix(record)) for item in signal_alerts_sent)
    fingerprint = build_signal_alert_fingerprint(record)
    message = build_signal_telegram_message(record, broker_dt=broker_dt, updated=updated)
    if not message:
        return False
    if send_telegram(message):
        signal_alerts_sent.add(fingerprint)
        signal_alerts_pending.pop(fingerprint, None)
        _save_state(sent_today, broker_dt=broker_dt)
        print(f"  [SIGNAL ALERT SENT] H={record.get('hour')} fp={fingerprint}")
        return True
    signal_alerts_pending[fingerprint] = {
        "record": dict(record), "added_at": broker_dt.isoformat() if broker_dt else "",
        "attempts": signal_alerts_pending.get(fingerprint, {}).get("attempts", 0) + 1,
    }
    _save_state(sent_today, broker_dt=broker_dt)
    return False


def reconcile_pending_signal_alerts(broker_dt):
    if not broker_dt:
        return
    changed = False
    for fingerprint, item in list(signal_alerts_pending.items()):
        record = item.get("record") if isinstance(item, dict) else None
        # Pending alerts are delivery retries for today's live signal only.
        # Never replay an old day's signal after restart.
        if not record or _signal_date(record) != broker_dt.date().isoformat():
            signal_alerts_pending.pop(fingerprint, None)
            changed = True
            continue
        send_signal_alert(record, broker_dt=broker_dt)
        changed = True
    if changed:
        _save_state(sent_today, broker_dt=broker_dt)


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
    if MARKET_DATA_PROVIDER and getattr(MARKET_DATA_PROVIDER, "name", "") == "MT4":
        health = MARKET_DATA_PROVIDER.get_health()
        if health.fresh or health.degraded or getattr(MARKET_DATA_PROVIDER, "_db_store", None) is not None:
            for symbol in symbols:
                bars = MARKET_DATA_PROVIDER.get_bars(symbol, "M30", start_dt, end_dt)
                if bars:
                    count = 0
                    for bar in bars:
                        ts = bar.get("time", 0)
                        if ts > 0:
                            _cache[(symbol, mt5.TIMEFRAME_M30, ts)] = bar
                            count += 1
                    print(f"  [HISTORY] {symbol} M30 loaded {count} bars from MT4 Feed")
            return

    return


def get_cached_candle(symbol, open_dt):
    """Look up one normalized candle dict from the M30 history cache."""
    target_ts = broker_time_to_ts(open_dt, open_dt.hour, open_dt.minute)
    cached = _cache.get((symbol, mt5.TIMEFRAME_M30, target_ts))
    if cached is None:
        return None
    if abs(int(cached["time"]) - int(target_ts)) > 180:
        return None
    return cached


def clear_history_cache():
    """Clear the in-memory M30 history cache, D-direction cache, and market data provider store."""
    _cache.clear()
    _d_direction_cache.clear()
    if hasattr(MARKET_DATA_PROVIDER, "clear"):
        MARKET_DATA_PROVIDER.clear()


D_DIRECTION_PAIRS = ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
D_SOURCE_SYMBOL = {symbol: symbol for symbol in D_DIRECTION_PAIRS}
_d_direction_cache = {}


def _d_cache_key(
    provider,
    canonical_symbol,
    resolved_symbol,
    target_broker_date,
    source_session_date,
    timeframe="H4",
    open_hour=20,
):
    """Build the date-aware identity required for one D source candle."""
    provider_name = getattr(provider, "name", None) or "MT4"

    def date_text(value):
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    return (
        str(provider_name),
        str(canonical_symbol),
        str(resolved_symbol),
        str(timeframe).upper(),
        date_text(target_broker_date),
        date_text(source_session_date) if source_session_date is not None else None,
        int(open_hour),
    )


def _find_cached_d_evidence(provider, canonical_symbol, target_broker_date):
    """Find a ready cache entry without collapsing sessions or symbols."""
    provider_name = getattr(provider, "name", None) or "MT4"
    target_text = target_broker_date.isoformat()
    prefix = (str(provider_name), str(canonical_symbol), "H4", target_text)
    for key, value in list(_d_direction_cache.items()):
        if not isinstance(key, tuple) or len(key) != 7:
            continue
        if key[0] != prefix[0] or key[1] != prefix[1] or key[3] != prefix[2] or key[4] != prefix[3]:
            continue
        if isinstance(value, dict) and value.get("d_state") not in (
            "MISSING", "MISSING_H4_20", "MISSING_PREVIOUS_SESSION", "WAITING_BROKER_CLOCK"
        ):
            return value
    return None


def find_previous_available_broker_session(symbol, target_broker_date, use_mt5_fallback=False):
    """Find the most recent Broker date before target_date that has market data."""
    search_start_broker = datetime.combine(target_broker_date - timedelta(days=10), datetime.min.time())
    search_end_broker = datetime.combine(target_broker_date, datetime.min.time())

    if MARKET_DATA_PROVIDER and getattr(MARKET_DATA_PROVIDER, "name", "") == "MT4":
        bars = MARKET_DATA_PROVIDER.get_bars(symbol, "M30", search_start_broker, search_end_broker)
        if bars:
            broker_dates_with_bars = set()
            for bar in bars:
                b_dt = bar.get("broker_dt")
                if b_dt and b_dt.date() < target_broker_date:
                    broker_dates_with_bars.add(b_dt.date())
            if broker_dates_with_bars:
                return max(broker_dates_with_bars)
        return None
    return None


def load_h4_history_for_d(source_symbol, target_broker_date, broker_offset, use_mt5_fallback=False, market_data_provider=None):
    """Load H4 bars from MT4 for diagnostics/history; MT5 candle APIs are forbidden."""
    provider = market_data_provider or MARKET_DATA_PROVIDER
    broker_start = datetime.combine(target_broker_date - timedelta(days=10), dtime.min)
    broker_end = datetime.combine(target_broker_date, dtime(4, 0))
    if not provider or getattr(provider, "name", "") != "MT4":
        return []
    try:
        raw_bars = provider.get_bars(source_symbol, "H4", broker_start, broker_end)
    except Exception as exc:
        print(f"[D-H4] MT4 fetch error for {source_symbol}: {exc}")
        return []
    result = []
    for bar in raw_bars or []:
        opening = bar.get("broker_dt")
        if opening is None and bar.get("broker_open_at"):
            text = str(bar["broker_open_at"]).replace("Z", "+00:00")
            opening = datetime.fromisoformat(text).replace(tzinfo=None)
        if opening is not None:
            result.append((opening, bar))
    return result



def resolve_mt5_symbol(symbol):
    """Resolve a canonical symbol name to the broker's actual symbol.

    Tries the raw symbol first, then common suffixes/prefixes.
    Returns the raw symbol unchanged if MT5 is not available.
    """
    if not hasattr(mt5, 'symbol_info'):
        return symbol
    try:
        info = mt5.symbol_info(symbol)
        if info is not None:
            return symbol
    except Exception:
        pass

    for suffix in ("+", ".a", ".i", "m", ".m", "c", ".c", "#", "."):
        candidate = symbol + suffix
        try:
            info = mt5.symbol_info(candidate)
            if info is not None:
                print(f"[D-H4] Resolved {symbol} → {candidate}")
                return candidate
        except Exception:
            continue

    for prefix in (".",):
        candidate = prefix + symbol
        try:
            info = mt5.symbol_info(candidate)
            if info is not None:
                print(f"[D-H4] Resolved {symbol} → {candidate}")
                return candidate
        except Exception:
            continue

    return symbol


def find_previous_session_h4_20_candle(source_symbol, target_broker_date, market_data_provider=None):
    """Find the H4 candle with Broker open time exactly 20:00 from the previous available session.

    Returns (candle_norm, session_date, broker_offset) or (None, None, None) if not found.
    Does NOT fallback to H4 16:00 or M30 if 20:00 is missing.
    Searches back up to 10 days for the most recent H4 20:00.
    """
    if hasattr(target_broker_date, "date") and callable(getattr(target_broker_date, "date")):
        try:
            target_broker_date = target_broker_date.date()
        except Exception:
            pass

    provider = market_data_provider or MARKET_DATA_PROVIDER
    resolved_symbol = source_symbol
    latest_session_date = None
    broker_offset = None

    # Step 1: Try exact H4 20:00 lookup per day
    for lookback_days in range(1, 11):
        try:
            session_date = target_broker_date - timedelta(days=lookback_days)
        except Exception:
            session_date = date.today() - timedelta(days=lookback_days)
        broker_open = datetime.combine(session_date, dtime(20, 0))
        try:
            # The H4 candle belongs to the source session, so its UTC
            # conversion must use that session's verified historical offset,
            # not the offset currently observed for the target date.
            if getattr(provider, "name", "") == "MT4":
                try:
                    session_offset = provider.get_broker_utc_offset(session_date)
                except TypeError:
                    session_offset = provider.get_broker_utc_offset()
            else:
                session_offset = BROKER_CLOCK.utc_offset_for_date(session_date)
            if getattr(provider, "name", "") != "MT4":
                candle = None
            elif hasattr(provider, "get_exact_bar"):
                candle = provider.get_exact_bar(source_symbol, "H4", broker_open)
            else:
                candle = next(
                    (
                        item for item in provider.get_bars(
                            source_symbol, "H4", broker_open, broker_open
                        )
                        if item.get("broker_dt") == broker_open
                        or str(item.get("broker_open_at", "")).startswith(broker_open.strftime("%Y-%m-%d %H:%M"))
                    ),
                    None,
                )
        except Exception:
            candle = None

        if candle is not None and bool(candle.get("is_complete", True)):
            if getattr(provider, "name", "") == "MT4" or candle.get("broker_dt") == broker_open:
                print(f"[D-H4] {source_symbol} (resolved {resolved_symbol}): session={session_date}, open={broker_open.strftime('%H:%M')} Broker")
                return candle, session_date, session_offset

        if latest_session_date is None:
            latest_session_date = session_date

    # Step 2: Fallback range query with canonical encoding
    bars = load_h4_history_for_d(source_symbol, target_broker_date, None, market_data_provider=provider)
    if not bars:
        return None, latest_session_date, broker_offset

    candidates = []
    for broker_open, norm in bars:
        try:
            is_before_target = broker_open.date() < target_broker_date
        except Exception:
            is_before_target = True

        if (broker_open.hour == 20
                and broker_open.minute == 0
                and bool(norm.get("is_complete", True))
                and is_before_target):
            try:
                if getattr(provider, "name", "") == "MT4":
                    try:
                        candidate_offset = provider.get_broker_utc_offset(broker_open.date())
                    except TypeError:
                        candidate_offset = provider.get_broker_utc_offset()
                else:
                    candidate_offset = BROKER_CLOCK.utc_offset_for_date(broker_open.date())
            except Exception:
                continue
            candidates.append((broker_open.date(), broker_open, norm, candidate_offset))

    if not candidates:
        found_opens = [f"{bo.strftime('%Y-%m-%d %H:%M')}" for bo, _ in bars[-12:]]
        print(f"[D-H4] No H4 20:00 found for {source_symbol}. Broker opens: {found_opens}")
        past_dates = []
        for bo, _ in bars:
            try:
                if bo.date() < target_broker_date:
                    past_dates.append(bo.date())
            except Exception:
                past_dates.append(bo.date())
        if past_dates:
            latest_session_date = max(past_dates)
        return None, latest_session_date, broker_offset

    candidates.sort(key=lambda x: x[0], reverse=True)
    session_date, broker_open, norm, broker_offset = candidates[0]
    print(f"[D-H4] {source_symbol}: session={session_date}, open={broker_open.strftime('%H:%M')} Broker")
    return norm, session_date, broker_offset


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
    if not MARKET_DATA_PROVIDER or getattr(MARKET_DATA_PROVIDER, "name", "") != "MT4":
        return None, "MT4_FEED_UNAVAILABLE"
    raw = MARKET_DATA_PROVIDER.get_bars(symbol, "M30", session_start, session_end)
    session_bars = [(bar.get("broker_dt"), bar) for bar in raw if bar.get("broker_dt") and bar["broker_dt"].date() == session_date]
    if not session_bars:
        return None, "MISSING"

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
    """Build D-Direction evidence payload v7 from H4 20:00 candle."""
    def exact_price(name):
        value = candle.get(f"{name}_exact")
        return value if value is not None else candle.get(name)

    broker_open_source = datetime.combine(session_date, dtime(20, 0))
    utc_open = (broker_open_source - timedelta(hours=broker_offset)).replace(tzinfo=timezone.utc)
    utc_close = utc_open + timedelta(hours=4)
    try:
        broker_open = broker_open_source
    except Exception:
        broker_open = (utc_open + timedelta(hours=broker_offset)).replace(tzinfo=None)
    broker_close = broker_open + timedelta(hours=4)
    local_open = utc_open.astimezone(HO_CHI_MINH_TZ)
    local_close = utc_close.astimezone(HO_CHI_MINH_TZ)

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

    broker_offset_str = f"+{broker_offset:02d}:00" if broker_offset and broker_offset >= 0 else f"{broker_offset:03d}:00"

    source_candle_identity = {
        "canonical_symbol": target_symbol,
        "resolved_symbol": candle.get("resolved_mt4_symbol", source_symbol),
        "resolved_mt4_symbol": candle.get("resolved_mt4_symbol", source_symbol),
        "timeframe": "H4",
        "epoch": int(candle.get("time", utc_open.timestamp())),
        "broker_open_at": f"{session_date.isoformat()}T20:00:00{broker_offset_str}",
        "broker_close_at": f"{(session_date + timedelta(days=1)).isoformat()}T00:00:00{broker_offset_str}",
        "utc_open_at": utc_open.isoformat(),
        "utc_close_at": utc_close.isoformat(),
        "local_open_at": local_open.isoformat(),
        "local_close_at": local_close.isoformat(),
        "open_exact": str(exact_price("open")),
        "high_exact": str(exact_price("high")),
        "low_exact": str(exact_price("low")),
        "close_exact": str(exact_price("close")),
    }

    return {
        "schema_version": D_DIRECTION_SCHEMA_VERSION,
        "symbol": target_symbol,
        "source_symbol": source_symbol,
        "provider": "MT4",
        "timeframe": "H4",
        "target_date": target_broker_date.isoformat(),
        "session_date": session_date.isoformat() if session_date else None,
        "source_open_time_broker": "20:00",
        "source_open_at_utc": utc_open.isoformat(),
        "d_candle_open_time_broker": f"{broker_open.hour:02d}:{broker_open.minute:02d}",
        "d_candle_close_time_broker": f"{broker_close.hour:02d}:{broker_close.minute:02d}",
        "d_candle_open_time_local": local_open.strftime("%H:%M"),
        "d_candle_close_time_local": local_close.strftime("%H:%M"),
        "d_candle_open_at_local": local_open.isoformat(),
        "d_candle_close_at_local": local_close.isoformat(),
        "broker_utc_offset": broker_offset,
        "local_timezone": "Asia/Ho_Chi_Minh",
        "d_candle_open_at_utc": utc_open.isoformat(),
        "d_candle_close_at_utc": utc_close.isoformat(),
        "source_candle_identity": source_candle_identity,
        "price_digits": get_symbol_price_digits(source_symbol),
        "candle": {
            "open": exact_price("open"),
            "high": exact_price("high"),
            "low": exact_price("low"),
            "close": exact_price("close"),
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
        "provider": "MT4",
        "timeframe": "H4",
        "target_date": target_broker_date.isoformat(),
        "session_date": session_date.isoformat() if session_date else None,
        "source_open_time_broker": "20:00",
        "source_open_at_utc": None,
        "d_candle_open_time_broker": None,
        "d_candle_close_time_broker": None,
        "d_candle_open_time_local": None,
        "d_candle_close_time_local": None,
        "d_candle_open_at_local": None,
        "d_candle_close_at_local": None,
        "broker_utc_offset": broker_offset,
        "local_timezone": "Asia/Ho_Chi_Minh",
        "d_candle_open_at_utc": None,
        "d_candle_close_at_utc": None,
        "source_candle_identity": None,
        "price_digits": get_symbol_price_digits(source_symbol),
        "candle": None,
        "raw_direction": None,
        "d_direction": "WAIT",
        "d_state": d_state,
        "failure_reason": failure_reason,
        "discovery_rule": "PREVIOUS_AVAILABLE_SESSION_EXACT_H4_OPEN_20_00",
    }


def _compute_d_from_source(target_symbol, source_symbol, target_broker_date, market_data_provider=None):
    """Compute D-Direction for target_symbol using the source_symbol's H4 20:00 candle."""
    candle, session_date, broker_offset = find_previous_session_h4_20_candle(
        source_symbol, target_broker_date, market_data_provider=market_data_provider
    )

    if session_date is None:
        return _build_d_missing_evidence(target_symbol, source_symbol, target_broker_date, None, None, "MISSING_PREVIOUS_SESSION")

    if candle is None:
        return _build_d_missing_evidence(target_symbol, source_symbol, target_broker_date, session_date, broker_offset, "MISSING_H4_20")

    ev = _build_d_direction_evidence_h4(target_symbol, source_symbol, target_broker_date, session_date, candle, broker_offset)
    print(f"[D-H4] {source_symbol} candidate: {session_date.isoformat()} 20:00 Broker")
    print(f"[D-H4] Selected session: {session_date.isoformat()}")
    print(f"[D-H4] O={candle['open']} H={candle['high']} L={candle['low']} C={candle['close']}")
    print(f"[D-H4] Direction: {ev['d_direction']}")
    return ev



def calculate_d_direction(symbol, target_broker_date, market_data_provider=None):
    """Calculate D-Direction for one symbol on one target Broker date using H4 20:00."""
    if hasattr(target_broker_date, "date") and callable(getattr(target_broker_date, "date")):
        target_broker_date = target_broker_date.date()
    provider = market_data_provider or MARKET_DATA_PROVIDER
    source_symbol = D_SOURCE_SYMBOL.get(symbol, symbol)

    if market_data_provider is None:
        cached = _find_cached_d_evidence(provider, symbol, target_broker_date)
        if cached is not None:
            return cached

        # Compatibility lookup for pre-v87 persisted test fixtures.  The
        # target date is still part of this alias, so it cannot leak a
        # snapshot across history dates.
        legacy_keys = (
            (target_broker_date.isoformat(), symbol),
            (getattr(provider, "name", "MT4"), target_broker_date.isoformat(), symbol),
        )
        for legacy_key in legacy_keys:
            cached = _d_direction_cache.get(legacy_key)
            if isinstance(cached, dict):
                if cached.get("d_state") in ("MISSING", "MISSING_H4_20", "MISSING_PREVIOUS_SESSION", "WAITING_BROKER_CLOCK"):
                    _d_direction_cache.pop(legacy_key, None)
                else:
                    return cached

    evidence = _compute_d_from_source(
        symbol, source_symbol, target_broker_date, market_data_provider=provider
    )
    d_state = evidence.get("d_state", "")
    if d_state not in ("MISSING", "MISSING_H4_20", "MISSING_PREVIOUS_SESSION",
                        "WAITING_BROKER_CLOCK"):
        if market_data_provider is None:
            identity = evidence.get("source_candle_identity") or {}
            resolved = identity.get("resolved_symbol") or identity.get("resolved_mt4_symbol") or source_symbol
            full_key = _d_cache_key(
                provider,
                symbol,
                resolved,
                target_broker_date,
                evidence.get("session_date"),
            )
            _d_direction_cache[full_key] = evidence
            # Keep a bounded date-scoped alias for old callers; all new reads
            # prefer the full source-candle identity above.
            _d_direction_cache[(getattr(provider, "name", "MT4"), target_broker_date.isoformat(), symbol)] = evidence
            _d_direction_cache[(target_broker_date.isoformat(), symbol)] = evidence
    return evidence


def calculate_all_d_directions(target_broker_date, market_data_provider=None):
    """Calculate D-Direction for all 5 symbols using H4 20:00 source mapping."""
    if hasattr(target_broker_date, "date") and callable(getattr(target_broker_date, "date")):
        target_broker_date = target_broker_date.date()
    provider = market_data_provider or MARKET_DATA_PROVIDER
    source_results = {}
    unique_sources = sorted(set(D_SOURCE_SYMBOL.values()))
    for src in unique_sources:
        source_results[src] = _compute_d_from_source(
            src, src, target_broker_date, market_data_provider=provider
        )
        d_state = source_results[src].get("d_state", "")
        if d_state not in ("MISSING", "MISSING_H4_20", "MISSING_PREVIOUS_SESSION",
                           "WAITING_BROKER_CLOCK"):
            if market_data_provider is None:
                evidence = source_results[src]
                identity = evidence.get("source_candle_identity") or {}
                resolved = identity.get("resolved_symbol") or identity.get("resolved_mt4_symbol") or src
                full_key = _d_cache_key(
                    provider,
                    src,
                    resolved,
                    target_broker_date,
                    evidence.get("session_date"),
                )
                _d_direction_cache[full_key] = evidence
                _d_direction_cache[(getattr(provider, "name", "MT4"), target_broker_date.isoformat(), src)] = evidence
                _d_direction_cache[(target_broker_date.isoformat(), src)] = evidence

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
            if market_data_provider is None:
                identity = result.get("source_candle_identity") or {}
                resolved = identity.get("resolved_symbol") or identity.get("resolved_mt4_symbol") or source_symbol
                full_key = _d_cache_key(
                    provider,
                    symbol,
                    resolved,
                    target_broker_date,
                    result.get("session_date"),
                )
                _d_direction_cache[full_key] = result
                _d_direction_cache[(getattr(provider, "name", "MT4"), target_broker_date.isoformat(), symbol)] = result
                _d_direction_cache[(target_broker_date.isoformat(), symbol)] = result
    return results


def clear_d_direction_cache():
    """Clear the D-Direction cache."""
    _d_direction_cache.clear()


def ensure_d_direction_ready(target_broker_date):
    """Return the date-scoped D snapshot readiness without mutating another date."""
    snapshot = build_d_direction_snapshot_for_date(target_broker_date, MARKET_DATA_PROVIDER)
    return snapshot_is_publishable(snapshot)


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
    # Signal evidence is sourced from MT4 exact-price strings; MT5 is not a
    # market-data dependency for D-Direction or entry classification.
    return SYMBOL_PRICE_DIGITS.get(symbol, 5)

def get_d_publication_datetime_local(local_date):
    if isinstance(local_date, str):
        local_date = datetime.strptime(local_date, "%Y-%m-%d").date()
    return datetime.combine(local_date, dtime(D_PUBLICATION_LOCAL_HOUR, D_PUBLICATION_LOCAL_MINUTE), tzinfo=HO_CHI_MINH_TZ)

def get_d_publication_datetime_utc(local_date):
    local_dt = get_d_publication_datetime_local(local_date)
    return local_dt.astimezone(timezone.utc)

def resolve_target_broker_date_for_d(target_local_date, broker_clock=None):
    """Resolve canonical Target Broker Date for D publication.

    Given a target_local_date (e.g. 2026-07-31), publication happens at 06:00 GMT+7.
    Publication local: 2026-07-31 06:00 +07:00
    Publication UTC:   2026-07-30 23:00 UTC
    With Broker UTC+3:
    Broker datetime:   2026-07-30 23:00 UTC + 3h = 2026-07-31 02:00 Broker
    Target Broker Date: 2026-07-31 (date portion of Broker datetime at publication).
    """
    if broker_clock is None:
        broker_clock = BROKER_CLOCK

    if isinstance(target_local_date, str):
        target_local_date = datetime.strptime(target_local_date, "%Y-%m-%d").date()
    elif hasattr(target_local_date, "date") and callable(getattr(target_local_date, "date")):
        try:
            target_local_date = target_local_date.date()
        except Exception:
            pass

    publication_local = datetime.combine(
        target_local_date,
        dtime(D_PUBLICATION_LOCAL_HOUR, D_PUBLICATION_LOCAL_MINUTE),
        tzinfo=HO_CHI_MINH_TZ,
    )
    publication_utc = publication_local.astimezone(timezone.utc)

    if hasattr(broker_clock, "get_broker_utc_offset"):
        try:
            broker_offset = int(broker_clock.get_broker_utc_offset(target_local_date))
        except TypeError:
            broker_offset = int(broker_clock.get_broker_utc_offset())
        except Exception as exc:
            raise MarketDataClockError(f"Broker offset unavailable for {target_local_date}: {exc}") from exc
        if broker_offset < -14 or broker_offset > 14:
            raise MarketDataClockError("Broker offset is outside the valid UTC range")
        broker_tz = timezone(timedelta(hours=broker_offset))
        return publication_utc.astimezone(broker_tz).date()

    if hasattr(broker_clock, "broker_from_utc_datetime") and callable(getattr(broker_clock, "broker_from_utc_datetime")):
        try:
            broker_dt = broker_clock.broker_from_utc_datetime(publication_utc)
            return broker_dt.date()
        except Exception as exc:
            raise MarketDataClockError(f"Broker clock unavailable: {exc}") from exc

    if hasattr(broker_clock, "utc_offset_for_date"):
        try:
            broker_offset = int(broker_clock.utc_offset_for_date(target_local_date))
        except Exception as exc:
            raise MarketDataClockError(f"Broker offset unavailable for {target_local_date}: {exc}") from exc
        if broker_offset < -14 or broker_offset > 14:
            raise MarketDataClockError("Broker offset is outside the valid UTC range")
        return publication_utc.astimezone(timezone(timedelta(hours=broker_offset))).date()

    raise MarketDataClockError("No verified Broker clock/offset provider is available")

def is_d_publication_due(now_utc, local_date):
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    pub_utc = get_d_publication_datetime_utc(local_date)
    return now_utc >= pub_utc

class MarketDataClockError(BrokerClockError):
    """Raised when MT4 market data clock is unavailable or stale."""
    pass


@dataclass
class FeedHealth:
    state: str           # "connected" | "degraded" | "stale" | "disconnected"
    fresh: bool          # True only while the MT4 heartbeat is live enough to schedule signals
    degraded: bool
    age_seconds: float
    observed_at_utc: str
    clock_verified: bool = False


class MarketDataProvider(Protocol):
    name: str

    def get_health(self) -> FeedHealth:
        ...

    def get_broker_now(self) -> datetime:
        ...

    def get_broker_utc_offset(self, broker_date=None) -> int:
        ...

    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start_broker: datetime,
        end_broker: datetime,
    ) -> list[dict]:
        ...

    def get_exact_bar(
        self,
        symbol: str,
        timeframe: str,
        broker_open: datetime,
    ) -> Optional[dict]:
        ...


class MT4FeedProvider:
    """Exclusive market-data provider for Signal engine backed by SQLite MT4FeedStore (v87)."""
    name: str = "MT4"

    def __init__(self, feed_store=None):
        try:
            from repositories.mt4_feed_store import MT4FeedStore
            self._db_store = feed_store or MT4FeedStore()
        except Exception:
            self._db_store = feed_store
        self._memory_store = {}

    def clear(self):
        self._memory_store.clear()
        if hasattr(self._db_store, "clear"):
            self._db_store.clear()

    def register_bars(self, symbol: str, timeframe: str, bars: list[dict]):
        key = (symbol, self._normalize_timeframe(timeframe))
        if key not in self._memory_store:
            self._memory_store[key] = []
        for raw in bars:
            bar = dict(raw)
            bar.setdefault("canonical_symbol", symbol)
            bar.setdefault("timeframe", self._normalize_timeframe(timeframe))
            if "broker_dt" not in bar and bar.get("broker_open_at"):
                bar["broker_dt"] = self._parse_broker_datetime(bar["broker_open_at"])
            bar.setdefault("is_complete", True)
            self._memory_store[key].append(bar)

    def get_health(self) -> FeedHealth:
        if self._memory_store:
            return FeedHealth("connected", True, False, 0.0, "", False)
        if self._db_store is None:
            return FeedHealth("disconnected", False, False, 999.0, "", False)

        hb = self._db_store.get_latest_heartbeat()
        if not hb:
            return FeedHealth("disconnected", False, False, 999.0, "", False)

        obs_str = hb.get("observed_at_utc", "")
        try:
            if int(hb.get("schema_version", 0)) != MARKET_DATA_PROVIDER_SCHEMA_VERSION:
                raise ValueError("unsupported heartbeat schema")
            self._db_store.get_broker_utc_offset()
            if "T" in obs_str:
                obs_dt = datetime.fromisoformat(obs_str)
            else:
                obs_dt = datetime.strptime(obs_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if obs_dt.tzinfo is None:
                obs_dt = obs_dt.replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            age_sec = (now_utc - obs_dt).total_seconds()
            if age_sec < 0:
                raise ValueError("heartbeat observed_at_utc is in the future")
        except Exception:
            return FeedHealth("degraded", False, True, 999.0, obs_str, False)

        if age_sec <= 15:
            return FeedHealth("connected", True, False, age_sec, obs_str, True)
        elif age_sec <= 60:
            # Historical bars remain readable while the feed is degraded, but
            # its extrapolated clock is no longer authoritative for a live
            # signal.  Fail closed instead of scheduling into a stopped MT4.
            return FeedHealth("degraded", False, True, age_sec, obs_str, True)
        else:
            return FeedHealth("stale", False, False, age_sec, obs_str, True)

    def get_broker_now(self) -> datetime:
        if self._memory_store:
            # Test helpers do not carry a publisher clock; they are data-only.
            raise MarketDataClockError("MT4 test bars have no heartbeat clock")
        if self._db_store is None:
            raise MarketDataClockError("No MT4 heartbeat recorded in persistent feed store")

        health = self.get_health()
        if not health.fresh or not health.clock_verified:
            raise MarketDataClockError(f"MT4 feed clock unavailable (state={health.state})")

        hb = self._db_store.get_latest_heartbeat()
        if not hb:
            if self._memory_store:
                return datetime.now(timezone.utc).replace(tzinfo=None)
            raise MarketDataClockError("No MT4 heartbeat recorded in persistent feed store")

        b_str = hb.get("broker_time", "")
        obs_str = hb.get("observed_at_utc", "")
        try:
            if "T" in b_str:
                b_dt = datetime.fromisoformat(b_str)
            else:
                b_dt = datetime.strptime(b_str, "%Y-%m-%d %H:%M:%S")

            if "T" in obs_str:
                obs_dt = datetime.fromisoformat(obs_str)
            else:
                obs_dt = datetime.strptime(obs_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if obs_dt.tzinfo is None:
                obs_dt = obs_dt.replace(tzinfo=timezone.utc)

            now_utc = datetime.now(timezone.utc)
            elapsed = (now_utc - obs_dt).total_seconds()
            if elapsed < 0:
                elapsed = 0.0
            return b_dt + timedelta(seconds=elapsed)
        except Exception as e:
            raise MarketDataClockError(f"Failed to parse MT4 broker clock: {e}")

    def get_broker_utc_offset(self, broker_date=None) -> int:
        if self._db_store is None:
            raise MarketDataClockError("No MT4 feed store is available")
        try:
            return self._db_store.get_broker_utc_offset(broker_date=broker_date)
        except Exception as exc:
            raise MarketDataClockError(f"No verified MT4 Broker offset is available: {exc}") from exc

    def get_latest_completed_broker_datetime(self, symbol=None, timeframe=None):
        """Return a persisted completed-bar boundary for offline history maintenance."""
        if self._db_store is None:
            return None
        getter = getattr(self._db_store, "get_latest_completed_broker_datetime", None)
        if not callable(getter):
            return None
        try:
            return getter(symbol=symbol, timeframe=timeframe)
        except Exception:
            return None

    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start_broker: datetime,
        end_broker: datetime,
    ) -> list[dict]:
        key = (symbol, self._normalize_timeframe(timeframe))
        if key in self._memory_store:
            store = self._memory_store.get(key, [])
            res = []
            for bar in store:
                b_dt = bar.get("broker_dt")
                if b_dt and self._naive(b_dt) >= self._naive(start_broker) and self._naive(b_dt) <= self._naive(end_broker):
                    res.append(bar)
            if res:
                return res

        if self._db_store is None:
            return []

        fmt = "%Y-%m-%d %H:%M:%S"
        s_str = start_broker.strftime(fmt) if isinstance(start_broker, datetime) else str(start_broker)
        e_str = end_broker.strftime(fmt) if isinstance(end_broker, datetime) else str(end_broker)
        return self._db_store.get_bars(symbol, self._normalize_timeframe(timeframe), s_str, e_str)

    def get_exact_bar(
        self,
        symbol: str,
        timeframe: str,
        broker_open: datetime,
    ) -> Optional[dict]:
        key = (symbol, self._normalize_timeframe(timeframe))
        if key in self._memory_store:
            store = self._memory_store.get(key, [])
            for bar in store:
                b_dt = bar.get("broker_dt")
                if b_dt and self._naive(b_dt) == self._naive(broker_open):
                    return bar

        if self._db_store is None:
            return None

        fmt = "%Y-%m-%d %H:%M:%S"
        b_str = broker_open.strftime(fmt) if isinstance(broker_open, datetime) else str(broker_open)
        return self._db_store.get_exact_bar(symbol, self._normalize_timeframe(timeframe), b_str)

    @staticmethod
    def _normalize_timeframe(timeframe):
        return {30: "M30", 60: "H1", 240: "H4", 16385: "M30", 16388: "H4", "30": "M30", "60": "H1", "240": "H4", "16385": "M30", "16388": "H4"}.get(timeframe, str(timeframe).upper())

    @staticmethod
    def _parse_broker_datetime(value):
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed

    @staticmethod
    def _naive(value):
        return value.replace(tzinfo=None) if getattr(value, "tzinfo", None) else value


MARKET_DATA_PROVIDER = MT4FeedProvider()


def set_market_data_provider(provider):
    global MARKET_DATA_PROVIDER
    MARKET_DATA_PROVIDER = provider


def build_d_direction_snapshot_for_date(
    target_local_date,
    market_data_provider=None,
    broker_clock=None,
) -> dict:
    """Pure, date-isolated builder for D-Direction snapshot of a specific target_local_date (v86).

    Does NOT read global CURRENT_DATE or datetime.now(), does NOT read Redis current snapshot,
    does NOT mutate snapshot of any other date.
    Returns a brand new independent snapshot dictionary object.
    """
    if market_data_provider is None:
        market_data_provider = MARKET_DATA_PROVIDER
    if broker_clock is None:
        broker_clock = BROKER_CLOCK

    if isinstance(target_local_date, str):
        target_local_date_str = target_local_date
        target_local_date_obj = datetime.strptime(target_local_date, "%Y-%m-%d").date()
    elif hasattr(target_local_date, "date") and callable(getattr(target_local_date, "date")):
        try:
            target_local_date_obj = target_local_date.date()
        except Exception:
            target_local_date_obj = target_local_date
        target_local_date_str = target_local_date_obj.isoformat()
    else:
        target_local_date_obj = target_local_date
        target_local_date_str = target_local_date.isoformat()

    try:
        try:
            feed_offset = market_data_provider.get_broker_utc_offset(target_local_date_obj)
        except TypeError:
            feed_offset = market_data_provider.get_broker_utc_offset()
        target_broker_date = (get_d_publication_datetime_utc(target_local_date_obj) + timedelta(hours=feed_offset)).date()
    except Exception as exc:
        return _build_d_clock_unavailable_snapshot(
            target_local_date_str,
            getattr(market_data_provider, "name", "MT4"),
            str(exc),
        )

    if isinstance(target_broker_date, str):
        target_broker_date_obj = datetime.strptime(target_broker_date, "%Y-%m-%d").date()
    else:
        target_broker_date_obj = target_broker_date

    d_dirs = calculate_all_d_directions(target_broker_date_obj, market_data_provider=market_data_provider)

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
            "data_provider": getattr(market_data_provider, "name", "MT4"),
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
            "candle": dict(candle) if candle else None,
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
        try:
            broker_offset = market_data_provider.get_broker_utc_offset(target_broker_date_obj)
        except TypeError:
            broker_offset = market_data_provider.get_broker_utc_offset()
    except Exception:
        broker_offset = None

    return {
        "schema_version": D_DIRECTION_SCHEMA_VERSION,
        "logic_version": SIGNAL_LOGIC_VERSION,
        "target_local_date": target_local_date_str,
        "target_broker_date": target_broker_date_obj.isoformat(),
        "broker_utc_offset": broker_offset,
        "clock_verified": broker_offset is not None,
        "publication_timezone": "Asia/Ho_Chi_Minh",
        "publication_rule": "DAILY_AT_06_00_LOCAL",
        "state": snapshot_state,
        "snapshot_state": snapshot_state,
        "data_provider": getattr(market_data_provider, "name", "MT4"),
        "symbols": symbols_payload,
    }


def _build_d_clock_unavailable_snapshot(target_local_date, provider_name, reason):
    """Return a non-publishable D snapshot when Broker offset/clock is unverified."""
    symbols = {}
    for symbol in D_DIRECTION_PAIRS:
        symbols[symbol] = {
            "symbol": symbol,
            "source_symbol": symbol,
            "data_provider": provider_name,
            "timeframe": "H4",
            "target_date": None,
            "session_date": None,
            "source_open_time_broker": "20:00",
            "broker_utc_offset": None,
            "candle": None,
            "raw_direction": None,
            "d_direction": "WAIT",
            "d_state": "MISSING",
            "failure_reason": "BROKER_CLOCK_UNAVAILABLE",
            "execution_status": "ON",
        }
    return {
        "schema_version": D_DIRECTION_SCHEMA_VERSION,
        "logic_version": SIGNAL_LOGIC_VERSION,
        "target_local_date": target_local_date,
        "target_broker_date": None,
        "broker_utc_offset": None,
        "clock_verified": False,
        "clock_state": "DEGRADED",
        "clock_error": reason,
        "publication_timezone": "Asia/Ho_Chi_Minh",
        "publication_rule": "DAILY_AT_06_00_LOCAL",
        "state": "MISSING",
        "snapshot_state": "MISSING",
        "data_provider": provider_name,
        "symbols": symbols,
    }


def build_d_direction_snapshot_v2(target_local_date, target_broker_date=None):
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(HO_CHI_MINH_TZ)
    snapshot = build_d_direction_snapshot_for_date(target_local_date)
    snapshot["published_at_utc"] = now_utc.isoformat()
    snapshot["published_at_local"] = now_local.isoformat()
    return snapshot

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


# =====================================================================
# DASHBOARD PUSH INFRASTRUCTURE
# =====================================================================

@dataclass
class DashboardPushResult:
    """Structured result from a dashboard push operation."""
    ok: bool
    status_code: int | None
    endpoint: str
    bytes_sent: int
    error: str | None
    acknowledged: bool  # True only for 2xx + ok=true in JSON response


def is_d_publication_complete(
    metadata,
    *,
    logic_version: int,
    d_schema_version: int,
) -> bool:
    """Return True only when the D publication is fully verified complete.

    A publication is ONLY complete when ALL of the following hold:
    - metadata is a dict
    - logic_version matches current SIGNAL_LOGIC_VERSION
    - d_schema_version matches current D_DIRECTION_SCHEMA_VERSION
    - snapshot_state is READY (or PARTIAL but active sources are READY)
    - dashboard_acknowledged is True (2xx HTTP confirmed)
    - digest key exists (non-empty)
    - last_http_status is in 200..299

    MISSING, UNKNOWN_LEGACY, and push-failed states always return False.
    """
    if not isinstance(metadata, dict):
        return False
    if metadata.get("logic_version") != logic_version:
        return False
    if metadata.get("d_schema_version") != d_schema_version:
        return False
    snap_state = metadata.get("snapshot_state", "")
    if snap_state not in ("READY", "PARTIAL"):
        return False
    if snap_state == "PARTIAL":
        # For PARTIAL: active sources (GBPUSD, GBPAUD) must be individually READY
        active_source_states = metadata.get("active_source_states", {})
        if any(active_source_states.get(symbol) not in ("READY", "DOJI") for symbol in D_DIRECTION_PAIRS):
            return False
    if not metadata.get("dashboard_acknowledged", False):
        return False
    if not metadata.get("digest"):
        return False
    http_status = metadata.get("last_http_status")
    if not (isinstance(http_status, int) and 200 <= http_status <= 299):
        return False
    return True


def snapshot_is_publishable(snapshot: dict) -> bool:
    """Return True when D snapshot has enough data to publish.

    v87 publishes independent D evidence for all five enabled symbols.
    """
    syms = snapshot.get("symbols", {})
    return all(syms.get(symbol, {}).get("d_state") in ("READY", "DOJI") for symbol in D_DIRECTION_PAIRS)


def validate_local_ready_snapshot(target_date_str: str) -> bool:
    """Return True if local d_direction_history.json has a READY/PARTIAL record for that date."""
    try:
        records = _load_d_direction_history_records()
        snap = records.get(target_date_str, {})
        return snap.get("state") in ("READY", "PARTIAL")
    except Exception:
        return False


def split_records_by_encoded_size(records, max_records=20, max_bytes=350 * 1024):
    """Split signal records into batches ensuring no batch exceeds size limits.

    Args:
        records: list of signal record dicts
        max_records: maximum records per batch (default 20)
        max_bytes: maximum JSON byte size per batch (default 350 KiB)

    Yields individual batches as lists.
    """
    current_batch = []
    current_size = 0
    for record in records:
        encoded = json.dumps(record, default=str).encode("utf-8")
        rec_size = len(encoded)
        # If a single record exceeds the limit, yield it alone to avoid infinite loop
        if rec_size >= max_bytes:
            if current_batch:
                yield current_batch
                current_batch = []
                current_size = 0
            yield [record]
            continue
        if (current_batch and (len(current_batch) >= max_records or current_size + rec_size > max_bytes)):
            yield current_batch
            current_batch = []
            current_size = 0
        current_batch.append(record)
        current_size += rec_size
    if current_batch:
        yield current_batch


def push_d_direction_snapshot(snapshot, force=False) -> DashboardPushResult:
    """Push a D-Direction snapshot to the dashboard API.

    Returns a DashboardPushResult. Reads response body to verify ok=true.
    Only sets acknowledged=True when HTTP 2xx AND response contains ok=true.
    """
    endpoint = "/api/signals/d-direction"
    dashboard_url = os.environ.get("DASHBOARD_API_URL", "") or DASHBOARD_URL
    if not dashboard_url:
        print("[D-PUBLISH] No dashboard_url configured, skip push.")
        return DashboardPushResult(ok=False, status_code=None, endpoint=endpoint,
                                   bytes_sent=0, error="No dashboard_url", acknowledged=False)
    api_key = os.environ.get("DASHBOARD_API_KEY", "") or _cfg.get("dashboard_api_key", "")
    target_date = snapshot.get("target_local_date", "unknown")
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
            headers["Authorization"] = f"Bearer {api_key}"
        payload = json.dumps(snapshot).encode("utf-8")
        bytes_sent = len(payload)
        req = urllib.request.Request(
            f"{dashboard_url}{endpoint}",
            data=payload,
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            status_code = resp.status
            body_raw = resp.read()
        print(
            f"[D-PUBLISH] POST {endpoint} "
            f"date={target_date} bytes={bytes_sent} status={status_code}"
        )
        acknowledged = False
        if 200 <= status_code <= 299:
            try:
                body = json.loads(body_raw.decode("utf-8"))
                acknowledged = bool(body.get("ok") is True)
            except Exception:
                acknowledged = True  # 2xx with non-JSON body: accept
        if acknowledged:
            print(f"[D-PUBLISH] D snapshot for {target_date} acknowledged OK")
        else:
            print(f"[D-PUBLISH] D snapshot for {target_date}: HTTP {status_code} but not acknowledged")
        return DashboardPushResult(
            ok=200 <= status_code <= 299,
            status_code=status_code,
            endpoint=endpoint,
            bytes_sent=bytes_sent,
            error=None,
            acknowledged=acknowledged,
        )
    except Exception as e:
        err = str(e)
        print(f"[D-PUBLISH] Failed to push D snapshot for {target_date}: {err}")
        return DashboardPushResult(ok=False, status_code=None, endpoint=endpoint,
                                   bytes_sent=0, error=err, acknowledged=False)


def publish_d_direction_daily(target_local_date=None, force=False):
    """Publish the D-Direction snapshot for a given local date.

    Bug fixes vs previous version:
    - Skip gate: uses is_d_publication_complete() — UNKNOWN_LEGACY and push-failed never skip.
    - Retry condition: uses snapshot_is_publishable() — `force` does NOT affect retry.
    - Mark published: only sets acknowledged=True when push HTTP 2xx + ok=true.
    - Saves structured metadata with digest, version fields, HTTP status.
    """
    if target_local_date is None:
        target_local_date = datetime.now(HO_CHI_MINH_TZ).date()
    elif isinstance(target_local_date, str):
        target_local_date = datetime.strptime(target_local_date, "%Y-%m-%d").date()

    target_date_str = target_local_date.isoformat()
    state_data = _load_state()
    publication_state = state_data.get("d_publication_state", {})
    metadata = publication_state.get(target_date_str)

    # FIX #1: Skip gate uses is_d_publication_complete() — not mere membership.
    # MISSING, UNKNOWN_LEGACY, or push-failed metadata NEVER skips.
    if (
        not force
        and is_d_publication_complete(
            metadata,
            logic_version=SIGNAL_LOGIC_VERSION,
            d_schema_version=D_DIRECTION_SCHEMA_VERSION,
        )
        and validate_local_ready_snapshot(target_date_str)
    ):
        prev_state = metadata.get("snapshot_state", "")
        print(f"  [D-PUBLISH] Date {target_date_str} already published and acknowledged (state={prev_state}), skip.")
        return _load_d_direction_history_records().get(target_date_str)
    elif metadata:
        prev_state = metadata.get("snapshot_state", "NONE")
        if prev_state not in ("READY", "PARTIAL"):
            print(f"  [D-PUBLISH] Previous metadata incomplete (state={prev_state}), will overwrite.")

    pub_local = get_d_publication_datetime_local(target_local_date)
    pub_utc = get_d_publication_datetime_utc(target_local_date)
    target_broker_date = resolve_target_broker_date_for_d(target_local_date, MARKET_DATA_PROVIDER)
    try:
        try:
            broker_offset = MARKET_DATA_PROVIDER.get_broker_utc_offset(target_broker_date)
        except TypeError:
            broker_offset = MARKET_DATA_PROVIDER.get_broker_utc_offset()
    except Exception as exc:
        print(f"  [D-PUBLISH] MT4 Broker offset unavailable; fail closed: {exc}")
        return None
    broker_tz = timezone(timedelta(hours=broker_offset))
    broker_dt = pub_utc.astimezone(broker_tz)

    print(f"[D-DATE] Local target: {target_date_str}")
    print(f"[D-DATE] Publication local: {pub_local.isoformat()}")
    print(f"[D-DATE] Publication UTC: {pub_utc.isoformat()}")
    print(f"[D-DATE] Broker offset: +{broker_offset:02d}:00")
    print(f"[D-DATE] Broker datetime: {broker_dt.strftime('%Y-%m-%d %H:%M')}")
    print(f"[D-DATE] Target Broker date: {target_broker_date.isoformat()}")

    attempts = 0
    snapshot = None
    deadline_utc = pub_utc + timedelta(minutes=10)

    while True:
        attempts += 1
        if attempts > 1:
            clear_d_direction_cache()

        snapshot = build_d_direction_snapshot_v2(target_local_date, target_broker_date)

        # FIX #2: Retry condition uses snapshot_is_publishable() — `force` does NOT affect this.
        # Normal startup with force=False must also retry MISSING snapshots.
        if snapshot_is_publishable(snapshot):
            break

        try:
            current_broker = MARKET_DATA_PROVIDER.get_broker_now()
            try:
                current_offset = MARKET_DATA_PROVIDER.get_broker_utc_offset(current_broker.date())
            except TypeError:
                current_offset = MARKET_DATA_PROVIDER.get_broker_utc_offset()
            current_utc = (current_broker - timedelta(hours=current_offset)).replace(tzinfo=timezone.utc)
        except Exception as exc:
            print(f"  [DAILY-D] MT4 clock degraded during retry: {exc}")
            break
        if current_utc >= deadline_utc or attempts >= 10:
            print(f"  [DAILY-D] Reached deadline or max attempts ({attempts}), publishing state={snapshot['state']}")
            break

        sleep_sec = 5 if attempts <= 6 else (15 if attempts <= 14 else 60)
        print(f"  [DAILY-D] Attempt {attempts}: state={snapshot['state']}, retrying in {sleep_sec}s...")
        time.sleep(sleep_sec)

    save_d_direction_snapshot_local(snapshot)
    push_result = push_d_direction_snapshot(snapshot, force=force)

    # Compute digest for tracking
    import hashlib
    digest = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]

    # Build active_source_states for PARTIAL validation
    syms = snapshot.get("symbols", {})
    active_source_states = {symbol: syms.get(symbol, {}).get("d_state", "MISSING") for symbol in D_DIRECTION_PAIRS}

    # FIX #3: Only mark acknowledged when push_result.acknowledged is True.
    new_metadata = {
        "schema_version": D_PUBLICATION_STATE_SCHEMA_VERSION,
        "logic_version": SIGNAL_LOGIC_VERSION,
        "d_schema_version": D_DIRECTION_SCHEMA_VERSION,
        "snapshot_state": snapshot["state"],
        "dashboard_acknowledged": push_result.acknowledged,
        "digest": digest if push_result.acknowledged else None,
        "last_http_status": push_result.status_code,
        "last_error": push_result.error,
        "published_at_utc": datetime.now(timezone.utc).isoformat(),
        "last_attempt_at_utc": datetime.now(timezone.utc).isoformat(),
        "active_source_states": active_source_states,
    }
    publication_state[target_date_str] = new_metadata

    if push_result.acknowledged:
        _save_state(
            d_publication_state=publication_state,
            d_last_success_at=datetime.now(timezone.utc).isoformat(),
        )
        print(f"  [D-PUBLISH] Published {target_date_str} state={snapshot['state']} HTTP {push_result.status_code} acknowledged")
    else:
        _save_state(d_publication_state=publication_state)
        print(
            f"  [D-PUBLISH] Published {target_date_str} state={snapshot['state']} "
            f"push_ok={push_result.ok} acknowledged=False "
            f"(will retry)"
        )
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
        opening = candle.get("open_exact")
        closing = candle.get("close_exact")
        open_price = Decimal(str(opening if opening is not None else candle["open"]))
        close_price = Decimal(str(closing if closing is not None else candle["close"]))
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


def should_reverse_final_signal(slot_hour: int, signal_date: date) -> tuple[bool, str]:
    """Return the one canonical v87 Final Reverse decision."""
    if isinstance(signal_date, str):
        signal_date = datetime.strptime(signal_date, "%Y-%m-%d").date()
    elif hasattr(signal_date, "date") and callable(getattr(signal_date, "date")):
        try:
            signal_date = signal_date.date()
        except Exception:
            pass

    return final_reverse_v87(int(slot_hour), signal_date)


def apply_special_adjustment(direction, *, broker_date, slot_hour, primary_source=None, symbol=None):
    """Apply the canonical v87 Final Reverse once."""
    if direction not in ("BUY", "SELL"):
        return direction, None

    should_rev, reason = should_reverse_final_signal(slot_hour, broker_date)
    if should_rev:
        return reverse_signal(direction), reason
    return direction, None


def apply_new_final_signal_inversion(direction, broker_date, slot_hour, primary_source=None, symbol=None):
    """Backward-compatible wrapper — delegates to apply_special_adjustment."""
    return apply_special_adjustment(direction, broker_date=broker_date,
                                     slot_hour=slot_hour, primary_source=primary_source,
                                     symbol=symbol)


def apply_weekday_slot_inversion(direction, broker_date, slot_hour):
    """Legacy wrapper — delegates to apply_special_adjustment with D source."""
    return apply_special_adjustment(direction, broker_date=broker_date,
                                     slot_hour=slot_hour, primary_source="D_DIRECTION")


def read_previous_h1_candle(symbol, slot_dt, as_of_dt=None):
    """Read the completed H1 candle that closes at the slot's H:00."""
    h1_close = slot_dt.replace(minute=0, second=0, microsecond=0)
    h1_open = h1_close - timedelta(hours=1)
    try:
        candle = get_candle_by_broker_datetime(symbol, "H1", h1_open)
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
    """Recalculate recent sessions from the persistent MT4 feed."""
    try:
        broker_dt = get_broker_time()
    except MarketDataClockError as exc:
        anchor_getter = getattr(MARKET_DATA_PROVIDER, "get_latest_completed_broker_datetime", None)
        broker_dt = anchor_getter(symbol="XAUUSD", timeframe="M30") if callable(anchor_getter) else None
        if broker_dt is None:
            print(f"  [REBUILD] MT4 clock unavailable, skip: {exc}")
            return 0
        print(
            "  [REBUILD] MT4 live clock unavailable; rebuilding only completed persisted history "
            f"through {broker_dt.strftime('%Y-%m-%d %H:%M')} Broker."
        )
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


def rebuild_current_day_slots_after_d_ready(broker_dt):
    """Rebuild all passed signal slots for today when D transitions MISSING → READY.

    Called once immediately after a READY D snapshot is obtained during the live
    loop so that slots that fired while D was MISSING are corrected without a
    full restart.  Entry times already computed are preserved — only Signal
    direction is recalculated using the newly available D-Direction.

    Slot order: H3 → H7 → H9 → H12 → H14 → H16.
    Only slots whose publication datetime ≤ broker_now are rebuilt.

    FIX: push_to_dashboard() is NOT called inside the per-hour loop.
    Instead compact signal records are collected and pushed ONCE after the loop.
    """
    global _current_day_mode
    target_date = broker_dt.date()
    hours = [h for h in get_target_hours(broker_dt)
             if broker_dt >= get_signal_datetime_for_slot(broker_dt, h)]
    if not hours:
        print("[D-READY] No completed slots to rebuild today")
        return 0

    print(f"[D-READY] Rebuilding current-day slots: {hours} after D READY")
    try:
        day_d_directions = calculate_all_d_directions(target_date)
    except Exception as exc:
        print(f"[D-READY] Could not fetch D-directions for rebuild: {exc}")
        return 0

    rebuilt = 0
    rebuilt_hours = []
    current_pair_day_modes = {sym: None for sym in SIGNAL_PAIRS}
    day_results = {}
    for hour in hours:
        slot_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=hour)
        try:
            record, next_day_modes = _build_rebuild_record(
                slot_dt,
                hour,
                as_of_dt=broker_dt,
                prior_slot_results=day_results if hour == 16 else None,
                day_mode=current_pair_day_modes,
                d_directions=day_d_directions,
            )
            if record is None:
                continue
            if isinstance(next_day_modes, dict):
                for sym, dm in next_day_modes.items():
                    if dm is not None:
                        current_pair_day_modes[sym] = dm
            record["daily_directions"] = day_d_directions
            record["d_direction_schema_version"] = D_DIRECTION_SCHEMA_VERSION
            day_results[hour] = record

            # Upsert into signals_log
            try:
                existing_data = []
                if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
                    with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                        existing_data = json.load(f)
                key_date = record["date"]
                key_hour = int(record["hour"])
                filtered = [r for r in (existing_data if isinstance(existing_data, list) else [])
                            if not (r.get("date") == key_date and int(r.get("hour", -1)) == key_hour)]
                filtered.append(record)
                filtered = filtered[-2000:]
                _write_signals_log_atomic(filtered)
            except Exception as write_exc:
                print(f"[D-READY] Upsert error H={hour}: {write_exc}")
                continue

            pair_dirs = record.get("pair_dirs", {})
            rebuilt += 1
            rebuilt_hours.append(hour)
            print(f"[D-READY] Local rebuild H={hour}: {pair_dirs}")
        except Exception as exc:
            print(f"[D-READY] Rebuild error H={hour}: {exc}")

    if rebuilt:
        hours_str = ", ".join(f"H{h}" for h in rebuilt_hours)
        print(f"[D-READY] Local rebuild OK: {rebuilt} slots ({hours_str})")
        # Push compact current signal summaries ONCE after all slots rebuilt
        try:
            _push_compact_current_signals([day_results[h] for h in rebuilt_hours if h in day_results])
        except Exception as push_exc:
            print(f"[D-READY] Dashboard push FAILED: {push_exc}")
    return rebuilt


# =====================================================================
# MAIN LOOP
# =====================================================================
mt5_ready = False
_broker_clock_error = ""
_mt5_connection_error = ""

# Track last known D snapshot state per broker date to detect MISSING → READY transitions
_d_state_per_date: dict = {}  # {date: snapshot_state_str}


def _push_compact_current_signals(records):
    """Push compact current-day signal summaries to the dashboard.

    Strips heavy fields (pair_evidence, d_directions, M30 arrays) before sending.
    Uses split_records_by_encoded_size to avoid 413.
    """
    dashboard_url = os.environ.get("DASHBOARD_API_URL", "") or DASHBOARD_URL
    if not dashboard_url or not records:
        return
    api_key = os.environ.get("DASHBOARD_API_KEY", "") or _cfg.get("dashboard_api_key", "")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    _HEAVY_FIELDS = {
        "pair_evidence", "d_directions", "daily_directions",
        "m30_candles", "h1_candle", "m30_layer1", "m30_layer2", "m30_layer3",
    }

    compact_records = []
    for rec in records:
        compact = {k: v for k, v in rec.items() if k not in _HEAVY_FIELDS}
        # Track which pairs have evidence available
        pair_ev = {"XAUUSD": (rec.get("pair_evidence") or {}).get("XAUUSD")}
        pair_ev = {key: value for key, value in pair_ev.items() if value}
        if pair_ev:
            compact["evidence_available"] = {sym: True for sym in pair_ev if pair_ev[sym]}
            compact["evidence_keys"] = {
                sym: f"{rec.get('date', '')}:{rec.get('hour', '')}:{sym}:v{SIGNAL_LOGIC_VERSION}"
                for sym in pair_ev if pair_ev[sym]
            }
        compact_records.append(compact)

    pushed = 0
    for batch in split_records_by_encoded_size(compact_records, max_records=20, max_bytes=350 * 1024):
        payload = json.dumps({"records": batch, "source": "mt5_signal_bot_compact",
                              "logic_version": SIGNAL_LOGIC_VERSION}).encode("utf-8")
        endpoint = "/api/signals/current"
        try:
            req = urllib.request.Request(
                f"{dashboard_url}{endpoint}",
                data=payload,
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
                resp.read()
            print(
                f"[DASHBOARD] POST {endpoint} records={len(batch)} "
                f"bytes={len(payload)} status={status}"
            )
            if 200 <= status <= 299:
                pushed += len(batch)
        except urllib.error.HTTPError as http_err:
            if http_err.code == 413:
                print(
                    f"[DASHBOARD] POST {endpoint} records={len(batch)} "
                    f"bytes={len(payload)} status=413 action=split_needed"
                )
                # Re-split to half and retry once
                half = max(1, len(batch) // 2)
                for i in range(0, len(batch), half):
                    sub = batch[i:i+half]
                    sub_payload = json.dumps({"records": sub, "source": "mt5_signal_bot_compact",
                                             "logic_version": SIGNAL_LOGIC_VERSION}).encode("utf-8")
                    try:
                        req2 = urllib.request.Request(
                            f"{dashboard_url}{endpoint}",
                            data=sub_payload,
                            headers=headers,
                        )
                        with urllib.request.urlopen(req2, timeout=15) as resp2:
                            status2 = resp2.status
                            resp2.read()
                        print(
                            f"[DASHBOARD] POST {endpoint} records={len(sub)} "
                            f"bytes={len(sub_payload)} status={status2} (retry after 413)"
                        )
                        if 200 <= status2 <= 299:
                            pushed += len(sub)
                    except Exception as retry_exc:
                        print(f"[DASHBOARD] Retry sub-batch FAILED: {retry_exc}")
            else:
                print(f"[DASHBOARD] POST {endpoint} FAILED: HTTP {http_err.code}")
        except Exception as exc:
            print(f"[DASHBOARD] POST {endpoint} FAILED: {exc}")

    if pushed > 0:
        print(f"[DASHBOARD] Current signal summaries pushed OK ({pushed} records)")
    else:
        print("[DASHBOARD] Current signal summaries push FAILED (0 records delivered)")


def _check_and_rebuild_after_d_ready(broker_dt):
    """Check if D just became READY and, if so, rebuild today's passed slots once.

    Runs each live-loop tick, but the rebuild is triggered at most once per
    (date, state-transition) event, so it is effectively O(1) extra work on
    steady-state loops where D is already READY.
    """
    global _d_directions_today
    today = broker_dt.date()
    prev_state = _d_state_per_date.get(today, "")

    # Only compute a fresh snapshot check once per minute to avoid spam
    try:
        now_key = (today, broker_dt.hour, broker_dt.minute)
        if not hasattr(_check_and_rebuild_after_d_ready, "_last_check_key"):
            _check_and_rebuild_after_d_ready._last_check_key = None
        if _check_and_rebuild_after_d_ready._last_check_key == now_key:
            return
        _check_and_rebuild_after_d_ready._last_check_key = now_key
    except Exception:
        pass

    try:
        fresh_directions = calculate_all_d_directions(today)
    except Exception as exc:
        print(f"[D-READY] Error fetching D directions: {exc}")
        return

    states = [v.get("d_state", "MISSING") for v in fresh_directions.values()
              if isinstance(v, dict)]
    if all(s in ("READY", "DOJI") for s in states):
        current_state = "READY"
    elif any(s in ("READY", "DOJI") for s in states):
        current_state = "PARTIAL"
    else:
        current_state = "MISSING"

    _d_state_per_date[today] = current_state

    # Transition from non-READY to READY/PARTIAL → rebuild
    if current_state in ("READY", "PARTIAL") and prev_state not in ("READY", "PARTIAL"):
        print(f"[D-READY] D transitioned {prev_state!r} → {current_state!r} for {today} — running catch-up rebuild")
        _d_directions_today = fresh_directions
        rebuild_current_day_slots_after_d_ready(broker_dt)
        # FIX: Use dict metadata instead of legacy set membership to decide if D push is needed
        try:
            today_local = datetime.now(HO_CHI_MINH_TZ).date()
            target_date_str = today_local.isoformat()
            state_data = _load_state()
            pub_state = state_data.get("d_publication_state", {})
            metadata = pub_state.get(target_date_str)
            if not is_d_publication_complete(
                metadata,
                logic_version=SIGNAL_LOGIC_VERSION,
                d_schema_version=D_DIRECTION_SCHEMA_VERSION,
            ):
                print(f"[D-READY] D publication incomplete for {target_date_str}, force-pushing snapshot")
                publish_d_direction_daily(today_local, force=True)
        except Exception as exc:
            print(f"[D-READY] Error publishing D snapshot after catch-up: {exc}")

    elif current_state in ("READY", "PARTIAL") and prev_state in ("READY", "PARTIAL"):
        # Already READY — keep _d_directions_today fresh
        _d_directions_today = fresh_directions


def _mt5_profile_config(profile_name=None):
    """Return one explicit profile config for every MT5 entry point."""
    resolved = profile_name or _active_profile
    profile = {"path": MT5_PATH}
    if resolved:
        loaded = load_profile_config(resolved)
        if loaded:
            profile.update(loaded)
        profile["profile_name"] = resolved
    return profile


def try_init_mt5():
    global mt5_ready, _mt5_connection_error
    if mt5_ready:
        return True
    profile = _mt5_profile_config()
    launch = ensure_mt5_profile_connected(profile, mt5_module=mt5, timeout_seconds=60)
    ok = launch.ok
    if ok:
        mt5_ready = True
        BROKER_CLOCK.clear_cache()
        info = mt5.account_info()
        if info:
            print(f"  [OK] MT5: {info.server} | {info.login}")
        _mt5_connection_error = ""
        return True
    details = [str(launch.failure_code or "MT5_INIT_FAILED"), str(launch.message or "")]
    if launch.last_error:
        details.append(f"MT5 last_error={launch.last_error}")
    _mt5_connection_error = " | ".join(part for part in details if part)
    print(f"  [WARN] MT5 execution unavailable: {_mt5_connection_error}")
    return False

def get_broker_time():
    """Return Broker wall time from MT4 Feed clock authority (v87). Fail-closed if MT4 Feed clock is stale or unavailable."""
    if not hasattr(MARKET_DATA_PROVIDER, "get_health"):
        raise MarketDataClockError("MT4 Feed provider is not configured")
    health = MARKET_DATA_PROVIDER.get_health()
    if not health.fresh or not getattr(health, "clock_verified", True):
        raise MarketDataClockError(f"MT4 feed clock is unavailable/stale (state={getattr(health, 'state', 'stale')})")
    return MARKET_DATA_PROVIDER.get_broker_now()


_last_broker_clock_log = ("", 0.0)


def _log_broker_clock_failure(error):
    """Emit one clock failure line per state, then at most once per minute."""
    global _last_broker_clock_log
    message = str(error)
    now = time.time()
    previous, previous_at = _last_broker_clock_log
    if message != previous or now - previous_at >= 60.0:
        print(f"[BROKER CLOCK] Fail-closed: {message}")
        _last_broker_clock_log = (message, now)


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


_current_day_mode = None  # DayMode or None — tracked across live slots


def _stored_signals_for_date(broker_date):
    """Read real persisted slot records from the signal log and SQLite mirror."""
    date_text = str(broker_date)
    merged = {}
    for record in _load_signals_log_records():
        if isinstance(record, dict) and record.get("date") == date_text:
            try:
                key = (date_text, int(record.get("hour")))
            except (TypeError, ValueError):
                continue
            merged[key] = record
    getter = getattr(store, "get_signals_by_date", None)
    if callable(getter):
        stored = getter(date_text) or []
    else:
        getter = getattr(store, "get_signals", None)
        stored = (getter(date=date_text) or []) if callable(getter) else []
    for record in stored:
        if isinstance(record, dict):
            try:
                key = (date_text, int(record.get("hour")))
            except (TypeError, ValueError):
                continue
            current = merged.get(key)
            try:
                newer_version = int(record.get("logic_version", -1)) > int(current.get("logic_version", -1)) if current else False
            except (TypeError, ValueError):
                newer_version = False
            richer_record = current is None or (
                record.get("record_revision") is not None
                and current.get("record_revision") is None
            )
            retry_resolved = bool(current and current.get("entry_state") == "PENDING_LAYER3"
                                  and record.get("entry_state") != "PENDING_LAYER3")
            if current is None or newer_version or richer_record or retry_resolved:
                merged[key] = record
    return list(merged.values())


def reconstruct_sent_slots(broker_date, logic_version=None, records=None):
    """Reconstruct sent_today set from real persisted SQLite records for today (v87)."""
    if logic_version is None:
        logic_version = SIGNAL_LOGIC_VERSION
    if records is None:
        try:
            records = _stored_signals_for_date(broker_date)
        except Exception:
            records = []

    valid_sent = set()
    b_date = broker_date if isinstance(broker_date, date) else datetime.strptime(str(broker_date), "%Y-%m-%d").date()
    for rec in records:
        h = rec.get("hour")
        d = rec.get("date")
        try:
            record_version = int(rec.get("logic_version", -1))
            slot_hour = int(h)
        except (TypeError, ValueError):
            continue
        if h is not None and slot_hour in ACTIVE_HOURS and d == str(b_date) and record_version == int(logic_version):
            sig = rec.get("signal")
            revision = rec.get("record_revision")
            if (
                sig in ("BUY", "SELL", "WAIT")
                and revision in (1, 2)
                and rec.get("entry_state") != "PENDING_LAYER3"
            ):
                valid_sent.add((b_date, slot_hour))
    return valid_sent


def catchup_due_slots(broker_dt):
    """Sequentially catch up and evaluate all passed/due slots for today that have not been persisted (v87)."""
    if broker_dt is None:
        return
    today = broker_dt.date()
    target_hours = get_target_hours(broker_dt)

    try:
        current_records = _stored_signals_for_date(today)
        existing_hours = {slot_hour for _, slot_hour in reconstruct_sent_slots(today, records=current_records)}
    except Exception:
        existing_hours = set()

    for hour in target_hours:
        slot_dt = get_signal_datetime_for_slot(broker_dt, hour)
        if broker_dt >= slot_dt:
            if hour not in existing_hours:
                print(f"[CATCHUP] Evaluating due slot H={hour} for {today} at {broker_dt.strftime('%H:%M')} Broker")
                res = evaluate_all_pairs_for_slot(slot_dt, hour, as_of_dt=broker_dt)
                if res and res.get("signal") in ("BUY", "SELL", "WAIT"):
                    entry_time_str = res.get("entry_time")
                    deadline = get_slot_retry_deadline(broker_dt, hour, entry_time_str)
                    actionable = (
                        res.get("signal") in ("BUY", "SELL")
                        and res.get("signal_state") == "READY"
                        and res.get("entry_state") == "READY"
                        and bool(entry_time_str)
                    )
                    is_missed = bool(not actionable and broker_dt > deadline)
                    if actionable and broker_dt > deadline:
                        is_missed = True
                    if is_missed:
                        res["missed"] = 1
                        current_note = res.get("hour_note") or ""
                        if "[MISSED_ENTRY_WINDOW]" not in current_note:
                            res["hour_note"] = (current_note + " [MISSED_ENTRY_WINDOW]").strip()

                    _persist_live_result(broker_dt, hour, res)
                    # Keep an unresolved slot retryable until its latest allowed entry.
                    if actionable or is_missed:
                        sent_today.add((today, hour))
                        existing_hours.add(hour)

                    if actionable and not is_missed:
                        schedule_orders_for_signal(res, broker_dt, hour)


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
            elif field == "pair_evidence" and isinstance(val, dict):
                # Entry evidence has one source of truth: XAUUSD.  Pair
                # directions still remain in pair_dirs/pair relations.
                xau_evidence = val.get("XAUUSD")
                extra_fields[field] = {"XAUUSD": xau_evidence} if xau_evidence else {}
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
    schedule_orders_for_signal(result, broker_dt, hour)
    alert_record = dict(result)
    alert_record.update({
        "hour": hour,
        "source_date": broker_dt.date().isoformat(),
        "record_revision": 2,
        "pair_dirs": result.get("pair_dirs") or get_pair_direction(hour, result.get("signal"), broker_dt, full_result=result),
    })
    if should_send_signal_alert(alert_record, signal_alerts_sent):
        send_signal_alert(alert_record, broker_dt=broker_dt)
    sent_today.add(key)
    _save_state(sent_today, broker_dt=broker_dt)
    tag = "RESOLVED" if is_recheck else "SENT"
    print(f"  [{tag}] H={hour} signal={result['signal']} entry={result['entry_time']}")
    return True


def main(profile_name=None):
    global mt5_ready, sent_today, _d_directions_today, _active_profile, _broker_clock_error, _mt5_connection_error, signal_alerts_sent, signal_alerts_pending, _current_day_mode
    print("=" * 55)
    print(f"  MT5 Multi-Timeframe Signal Bot v{SIGNAL_LOGIC_VERSION}")
    print(f"  Symbol: {SYMBOL}")
    print(f"  Target Hours: {', '.join(f'H={h}' for h in TARGET_HOURS)}")
    print("  Broker clock: MT4 Feed heartbeat authority, fail-closed")
    admin_ok = bool(TELEGRAM_ADMIN_CHAT_ID and resolve_signal_admin_chat_id())
    print(f"  Telegram admin destination: {'yes' if admin_ok else 'no'}")
    print("=" * 55)

    _active_profile = resolve_active_profile(profile_name)

    if try_init_mt5():
        info = mt5.account_info()
        if info:
            print(f"  Balance: ${info.balance:,.2f}")
    else:
        print("[WARN] MT5 execution is disabled; Signal calculation awaits MT4 Feed.")

    print("=" * 55)
    print("  Dang chay... Ctrl+C de dung")
    print("=" * 55)

    resolved_clock_symbols = tuple(
        dict.fromkeys(
            resolve_mt5_symbol(symbol)
            for symbol in (
                "XAUUSD",
                "GBPUSD",
                "GBPAUD",
                "GBPJPY",
                "GBPCAD",
            )
        )
    )
    BROKER_CLOCK.configure_symbols(resolved_clock_symbols)

    def heartbeat_thread():
        global _broker_clock_error
        while True:
            heartbeat_broker_dt = None
            # MT4 owns both market-data time and the schedule.  MT5 being
            # offline must not hide a valid Broker clock or stop signal
            # calculation; it only disables the execution gateway.
            try:
                heartbeat_broker_dt = get_broker_time()
                _broker_clock_error = ""
            except BrokerClockError as error:
                _broker_clock_error = str(error)
            try:
                errors = [error for error in (_broker_clock_error, _mt5_connection_error) if error]
                publish_heartbeat(
                    _active_profile,
                    mt5_ready,
                    " | ".join(errors),
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
            _log_broker_clock_failure(error)
            time.sleep(5)

    # Restore state from previous run (same day only)
    saved = _load_state()
    sent_today = saved.get("sent_today", set())
    signal_alerts_sent.update(saved.get("signal_alerts_sent", set()))
    signal_alerts_pending.update(saved.get("signal_alerts_pending", {}))

    if sent_today:
        print(f"  [RESTORE] sent_today: {sent_today}")

    send_telegram(build_startup_telegram_message(broker_dt, mt5_ready))

    # Rebuild signals_log from the persistent MT4 Feed before pushing.
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
    try:
        broker_offset = MARKET_DATA_PROVIDER.get_broker_utc_offset(broker_dt.date())
    except TypeError:
        broker_offset = MARKET_DATA_PROVIDER.get_broker_utc_offset()
    now_utc = (broker_dt - timedelta(hours=broker_offset)).replace(tzinfo=timezone.utc)
    today_local = now_utc.astimezone(HO_CHI_MINH_TZ).date()
    if is_d_publication_due(now_utc, today_local):
        print(f"  [DAILY-D] Publication is due for local date {today_local.isoformat()}")
        publish_d_direction_daily(today_local)
    else:
        print(f"  [DAILY-D] Before 06:00 GMT+7, today's publication scheduled for 06:00 GMT+7.")

    reconcile_pending_signal_alerts(broker_dt)

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
                _log_broker_clock_failure(error)
                time.sleep(5)
                continue
            # Reset day mode when broker date changes
            if broker_dt.date() != last_broker_date:
                _current_day_mode = None
                last_broker_date = broker_dt.date()
            if not startup_slots_marked:
                sent_today.update(reconstruct_sent_slots(broker_dt.date()))
                _save_state(sent_today, broker_dt=broker_dt)
                catchup_due_slots(broker_dt)
                startup_slots_marked = True
            for hour in get_target_hours(broker_dt):
                _process_live_slot(broker_dt, hour)
            process_pending_execution_orders()

            price_push_minute = (broker_dt.date(), broker_dt.hour, broker_dt.minute)
            if price_push_minute != last_price_push_minute:
                _save_state(sent_today, broker_dt=broker_dt)
                push_state_to_dashboard()
                push_prices_to_dashboard()
                last_price_push_minute = price_push_minute

            # D-MISSING → READY catch-up: rebuild passed slots when D becomes available
            _check_and_rebuild_after_d_ready(broker_dt)

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
    """Return v87 XAUUSD M30 layer open windows for evidence compatibility."""
    slot = slot_dt.replace(minute=0, second=0, microsecond=0)
    if slot.hour == 16:
        return {
            "layer2": tuple(slot.replace(hour=value) for value in (5, 4, 3)),
            "layer3": tuple(slot.replace(hour=value) for value in (10, 9, 8)),
        }
    return {
        "layer2": tuple(slot - timedelta(minutes=value) for value in (30, 60, 90)),
        "layer3": (slot, slot - timedelta(minutes=30), slot - timedelta(minutes=60)),
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
    candle = get_candle_by_broker_datetime(symbol, "M30", open_dt)
    if candle is None or not _valid_m30_ohlc(candle):
        return None
    return candle


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


def resolve_h16_entry_plan_compatibility(prior_slot_results=None):
    """Legacy call-site guard; H16 is always resolved from XAUUSD H1 data."""
    return {
        "symbol": "XAUUSD",
        "entry_time": None,
        "entry_state": "WAIT",
        "entry_rule": "H16_INDEPENDENT_XAU_H1",
        "entry_candidates": ["16:11", "16:49", "17:25"],
        "failure_reason": "H16_REQUIRES_XAU_H1_LAYERS",
    }


def next_full_hour_after_signal_slot(slot_dt):
    """GBP entry is always the next full Broker hour after the signal slot."""
    return (slot_dt + timedelta(hours=1)).strftime("%H:00")


def _pair_entry_utc_map(slot_dt, pair_entry_times, broker_offset):
    return {
        symbol: compute_utc_iso(slot_dt.date(), pair_entry_times.get(symbol), broker_offset)
        for symbol in SIGNAL_PAIRS
    }


def evaluate_symbol_entry_timing_m30(symbol, slot_dt, hour, as_of_dt=None):
    """Compatibility wrapper; v87 calculates Entry from XAUUSD only."""
    if symbol != "XAUUSD":
        return {"symbol": symbol, "entry_state": "WAIT", "entry_time": None, "classification_reason": "COMMON_XAU_ENTRY_ONLY"}
    return build_v87_entry_plan(slot_dt, int(hour), MARKET_DATA_PROVIDER, as_of_dt or slot_dt)


def evaluate_xau_entry_timing_m30(slot_dt, hour, as_of_dt=None):
    return build_v87_entry_plan(slot_dt, int(hour), MARKET_DATA_PROVIDER, as_of_dt or slot_dt)


def resolve_h16_entry_plan(prior_slot_results=None, slot_dt=None, provider=None, as_of_dt=None):
    """Return the independent H16 XAUUSD H1 plan without reading a prior slot."""
    if slot_dt is None:
        return resolve_h16_entry_plan_compatibility(prior_slot_results)
    active_provider = provider or MARKET_DATA_PROVIDER
    return build_v87_entry_plan(slot_dt, 16, active_provider, as_of_dt or slot_dt)


def evaluate_all_pairs_for_slot(broker_dt, hour, as_of_dt=None, prior_slot_results=None, day_mode=None, d_directions=None):
    """v87 pipeline: one XAU entry, GBPUSD reference, D relation, one final reverse."""
    h = int(hour)
    if broker_dt is None or h not in ACTIVE_HOURS:
        return None
    slot_dt = broker_dt.replace(hour=h, minute=0, second=0, microsecond=0)
    cutoff = as_of_dt or broker_dt
    if d_directions is None:
        d_directions = calculate_all_d_directions(slot_dt.date(), market_data_provider=MARKET_DATA_PROVIDER)
    selected_mode = day_mode.get("XAUUSD") if isinstance(day_mode, dict) else day_mode
    result = evaluate_v87_slot(slot_dt, h, MARKET_DATA_PROVIDER, d_directions, selected_mode, cutoff)
    branch = result.get("entry_branch")
    next_mode = result.get("day_mode")
    if next_mode in ("H_11", "H_PLUS_1_25"):
        mode_name = "DAY_MODE_H11" if next_mode == "H_11" else "DAY_MODE_H_PLUS_1_25"
        next_mode_obj = DayMode(mode_name, h, result.get("entry_time") or "", next_mode)
    elif isinstance(selected_mode, DayMode):
        next_mode_obj = selected_mode
    else:
        next_mode_obj = None
    try:
        try:
            broker_offset = MARKET_DATA_PROVIDER.get_broker_utc_offset(slot_dt.date())
        except TypeError:
            broker_offset = MARKET_DATA_PROVIDER.get_broker_utc_offset()
    except Exception:
        broker_offset = None
    result.update({
        "record_revision": 2 if result.get("signal") in ("BUY", "SELL") and result.get("entry_state") == "READY" else 1,
        "state_updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "entry_at_utc": compute_utc_iso(slot_dt.date(), result.get("entry_time"), broker_offset),
        "broker_utc_offset": broker_offset,
        "pair_labels": {symbol: "REFERENCE" if symbol in ("XAUUSD", "GBPUSD") else "D_RELATION" for symbol in SIGNAL_PAIRS},
        "pair_groups": {symbol: ((result.get("timing") or {}).get("layers") or {}).get("layer2", {}).get("group") for symbol in SIGNAL_PAIRS},
        "pair_day_modes": {symbol: next_mode_obj.mode if next_mode_obj else None for symbol in SIGNAL_PAIRS},
        "pair_day_mode_states": {symbol: "RESOLVED" if next_mode_obj else "UNRESOLVED_WAITING_FOR_ANCHOR" for symbol in SIGNAL_PAIRS},
        "day_mode_source_hour": next_mode_obj.source_hour if next_mode_obj else None,
        "day_mode_source_entry_time": next_mode_obj.source_entry_time if next_mode_obj else None,
        "day_mode_source_branch": next_mode_obj.source_branch if next_mode_obj else None,
        "_pair_day_modes_objects": {symbol: next_mode_obj for symbol in SIGNAL_PAIRS},
        "entry_rule": "XAUUSD_COMMON_ENTRY_PLAN",
        "source_date": slot_dt.date().isoformat(),
    })
    result["pair_entry_at_utc"] = _pair_entry_utc_map(slot_dt, result.get("pair_entry_times", {}), broker_offset)
    result["day_mode"] = next_mode_obj
    result["day_mode_state"] = "RESOLVED" if next_mode_obj else "UNRESOLVED_WAITING_FOR_ANCHOR"
    return result


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
    try:
        broker_dt = get_broker_time()
    except MarketDataClockError as exc:
        print(f"  [REPAIR] MT4 clock unavailable: {exc}")
        return 0
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


def diagnose_h4_d(target_date_str=None, profile_name=None):
    """Diagnostic CLI for H4 D-Direction calculation."""
    active_profile = resolve_active_profile(profile_name)
    launch = ensure_mt5_profile_connected(
        _mt5_profile_config(active_profile), mt5_module=mt5, timeout_seconds=10
    )
    if not launch.ok:
        print(f"[DIAGNOSE-H4-D] MT5 initialization failed: {launch.failure_code} {launch.message}")
        return

    global mt5_ready
    mt5_ready = True

    resolved_clock_symbols = tuple(
        dict.fromkeys(
            resolve_mt5_symbol(symbol)
            for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
        )
    )
    BROKER_CLOCK.configure_symbols(resolved_clock_symbols)
    BROKER_CLOCK.clear_cache()

    try:
        broker_offset = BROKER_CLOCK.current_utc_offset()
        broker_dt = BROKER_CLOCK.now()
        ts_mode = BROKER_CLOCK.timestamp_mode
    except Exception as exc:
        print(f"[DIAGNOSE-H4-D] BrokerClock calibration failed: {exc}")
        return

    print("=" * 60)
    print("  H4 D-DIRECTION DIAGNOSTIC REPORT")
    print("=" * 60)
    print(f"Profile: {active_profile}")
    print(f"BrokerClock symbols: {list(BROKER_CLOCK._symbols)}")
    print(f"Timestamp mode: {ts_mode}")
    print(f"Broker UTC offset: {broker_offset:+03d}:00")
    print(f"Broker now: {broker_dt.strftime('%Y-%m-%d %H:%M:%S')}")

    if target_date_str:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    else:
        target_date = broker_dt.date()

    print(f"Target Broker Date: {target_date.isoformat()}")

    for canonical_symbol in D_DIRECTION_PAIRS:
        source_symbol = D_SOURCE_SYMBOL.get(canonical_symbol, canonical_symbol)
        print("-" * 60)
        print(f"Canonical Symbol: {canonical_symbol}")
        print(f"Canonical Source: {source_symbol}")
        resolved_source = resolve_mt5_symbol(source_symbol)
        print(f"Resolved Source: {resolved_source}")

        sel_res = mt5.symbol_select(resolved_source, True)
        print(f"symbol_select result ({resolved_source}): {sel_res}")

        candidate_broker_dt = None
        encoded_ts = None
        api_start = None
        api_end = None
        found_candle = None
        failure_reason = None
        decoded_opens = []

        for lookback_days in range(1, 11):
            session_date = target_date - timedelta(days=lookback_days)
            broker_open_dt = datetime.combine(session_date, dtime(20, 0))
            if candidate_broker_dt is None:
                candidate_broker_dt = broker_open_dt
                try:
                    encoded_ts = BROKER_CLOCK.mt5_timestamp_from_broker_datetime(broker_open_dt)
                    utc_target = datetime.fromtimestamp(encoded_ts, tz=timezone.utc)
                    api_start = utc_target - timedelta(minutes=3)
                    api_end = utc_target + timedelta(minutes=3)
                except Exception:
                    pass

            try:
                candle = get_candle_by_broker_datetime(source_symbol, mt5.TIMEFRAME_H4, broker_open_dt)
                if candle is not None:
                    decoded = BROKER_CLOCK.broker_datetime_from_mt5_timestamp(candle["time"])
                    decoded_opens.append(decoded.strftime("%Y-%m-%d %H:%M"))
                    if decoded == broker_open_dt:
                        found_candle = candle
                        break
            except Exception as err:
                failure_reason = str(err)

        bars = load_h4_history_for_d(source_symbol, target_date, broker_offset)
        bars_count = len(bars)
        if not decoded_opens:
            decoded_opens = [b[0].strftime("%Y-%m-%d %H:%M") for b in bars[-6:]]

        if found_candle is None:
            failure_reason = failure_reason or "MISSING_H4_20"

        print(f"Candidate Broker datetime: {candidate_broker_dt}")
        print(f"Encoded MT5 timestamp: {encoded_ts}")
        print(f"API UTC start/end: {api_start} -> {api_end}")
        print(f"Bars returned: {bars_count}")
        print(f"Decoded Broker opens: {decoded_opens}")

        if found_candle:
            raw_dir = exact_candle_direction(found_candle)
            d_dir = "BUY" if raw_dir == "TANG" else ("SELL" if raw_dir == "GIAM" else "WAIT")
            print(f"Selected H4 candle time (epoch): {found_candle['time']}")
            print(f"OHLC: O={found_candle['open']} H={found_candle['high']} L={found_candle['low']} C={found_candle['close']}")
            print(f"D Direction: {d_dir} (raw: {raw_dir})")
            print(f"Failure reason: None")
        else:
            print("Selected H4 candle: None")
            print("OHLC: N/A")
            print("D Direction: WAIT")
            print(f"Failure reason: {failure_reason}")

    print("=" * 60)


def _init_mt5_for_cli(profile_name, label):
    """Connect maintenance commands through the same profile launcher."""
    launch = ensure_mt5_profile_connected(
        _mt5_profile_config(profile_name), mt5_module=mt5, timeout_seconds=10
    )
    if not launch.ok:
        print(f"[{label}] MT5 init failed: {launch.failure_code} {launch.message}")
    return launch.ok


def _run_feed_only_rebuild(days):
    """Rebuild v87 records from the MT4 Feed without requiring MT5 execution."""
    print("[REBUILD] MT4 Feed is the only rebuild dependency; MT5 execution is optional.")
    rebuilt = rebuild_recent_history(days=days)
    if rebuilt > 0:
        push_to_dashboard(snapshot_complete=True)
    return rebuilt


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=str, help="Profile name for heartbeat")
    parser.add_argument("--diagnose-h4-d", action="store_true",
                        help="Diagnose H4 D-Direction calculation and symbol resolution")
    parser.add_argument("--date", type=str, help="Target date YYYY-MM-DD for diagnosis")
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

    if args.diagnose_h4_d:
        diagnose_h4_d(target_date_str=args.date, profile_name=args.profile)
    elif args.repair_history or args.repair_date:
        if _init_mt5_for_cli(args.profile, "REPAIR"):
            mt5_ready = True
            BROKER_CLOCK.clear_cache()
            try:
                result = repair_history(target_dates=args.repair_date)
                if result["updated"] > 0:
                    push_to_dashboard(snapshot_complete=False)
            finally:
                mt5.shutdown()
    elif args.rebuild_all:
        _run_feed_only_rebuild(args.days)
    elif args.rebuild_d_history:
        if _init_mt5_for_cli(args.profile, "REBUILD-D"):
            mt5_ready = True
            BROKER_CLOCK.clear_cache()
            try:
                rebuild_d_direction_history(days=args.days)
            finally:
                mt5.shutdown()
    elif args.repair_d_date:
        if _init_mt5_for_cli(args.profile, "REPAIR-D"):
            mt5_ready = True
            BROKER_CLOCK.clear_cache()
            try:
                repair_d_direction_date(args.repair_d_date)
            finally:
                mt5.shutdown()
    else:
        main(profile_name=args.profile)


