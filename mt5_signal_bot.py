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
from datetime import datetime, timedelta, timezone
import urllib.request

from utils import send_telegram_raw, send_telegram_with_keyboard
from oak_logger import setup_logger
from repositories.sqlite_store import SQLiteStore
from secret_store import resolve_telegram_token, migrate_plaintext_tokens
from telegram_client import telegram_get_me
from domain.broker_clock import BrokerClock, BrokerClockError
from domain.signal_rules import (
    classify_four_candle_group,
    classify_three_candle_group,
    deferred_gbp_entry_time,
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


SIGNAL_LOGIC_VERSION = 72
GBP_SIGNAL_PAIRS = ("GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
SIGNAL_PAIRS = ("XAUUSD", *GBP_SIGNAL_PAIRS)
DISPLAY_SIGNAL_PAIRS = ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")


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
    """Load restart-safe sent-slot, entry-alert, and auto-close state."""
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
    }


def _save_state(sent_today, broker_dt=None):
    """Persist sent logical slots, entry alerts, and pending auto-close obligations."""
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
    }
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
    """Build versioned two-layer M30 evidence records for the dashboard."""
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
            "entry_rule": evidence.get("entry_rule") or (
                "XAU_TWO_LAYER_M30" if symbol == "XAUUSD" else "NEXT_FULL_HOUR_AFTER_XAU"
            ),
            "signal_state": (result.get("pair_signal_states") or {}).get(symbol),
        })
        if symbol == "XAUUSD":
            evidence["gbp_entry_time"] = deferred_gbp_entry_time(evidence.get("entry_time"))
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


def _serialize_candle_ohlc(candle, symbol):
    """Serialize an MT5 candle array row to a plain dict with proper precision."""
    if candle is None:
        return None
    digits = _symbol_digits(symbol)
    return {
        "open": round(float(candle["open"]), digits),
        "high": round(float(candle["high"]), digits),
        "low": round(float(candle["low"]), digits),
        "close": round(float(candle["close"]), digits),
        "tick_volume": int(candle["tick_volume"]),
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
    "pair_signal_states",
    "pair_labels",
    "pair_entry_at_utc",
    "entry_at_utc",
    "signal_state",
    "pair_groups",
    "pair_evidence",
)

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
        3: "04:49",
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


def calculate_slot_signal(broker_dt, hour):
    """Evaluate one active slot with the two-layer independent M30 engine."""
    hour = int(hour)
    if hour not in ACTIVE_HOURS:
        return {
            "signal": "WAIT",
            "report": f"H={hour}: inactive slot.",
            "suppressed": True,
        }
    result = evaluate_all_pairs_for_slot(broker_dt, hour)
    if result is None:
        return {
            "signal": "WAIT",
            "report": f"H={hour}: incomplete two-layer M30 data.",
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
        "Pairs: XAUUSD | GBPUSD | GBPAUD | GBPJPY | GBPCAD\n"
        "Signal engine: GBP M30 signals -> XAU Layer 1 -> XAU Layer 2\n"
        "Entry: XAU from XAU M30; GBP at the next full Broker hour\n"
        "XAUUSD: Reverse GBPAUD; H3/H14/H16 reverse XAU once more\n"
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
    """Build the v72 five-pair private-admin signal message."""
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
    lines = [f"🚨 SIGNAL READY · H{hour} · v{record.get('logic_version', SIGNAL_LOGIC_VERSION)}"]
    for symbol in GBP_SIGNAL_PAIRS:
        lines.append(_telegram_pair_line(symbol, directions.get(symbol, "WAIT"), entries.get(symbol), broker_offset, source_date))
    lines.append(_telegram_pair_line("XAUUSD", directions.get("XAUUSD", "WAIT"), entries.get("XAUUSD"), broker_offset, source_date))
    relation = "SAME AS" if hour in (3, 14, 16) else "OPPOSITE"
    lines.append(
        f"XAU direction: {relation} GBPAUD "
        f"({directions.get('GBPAUD', 'WAIT')})"
    )
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
# REBUILD: tính lại signals_log từ MT5 khi bot khởi động (tránh push data cũ)
# =====================================================================
def rebuild_slot_signal(broker_dt, h):
    """Recalculate one slot with current logic and overwrite signals_log (date, hour).
    Always logs the result -- including WAIT and deactivated slots -- so the dashboard
    shows every scheduled hour.

    The v72 inputs are complete by the logical H:00 slot.
    """
    if broker_dt.weekday() >= 5:
        return False

    result = evaluate_all_pairs_for_slot(broker_dt, h)
    if result is None:
        result = calculate_slot_signal(broker_dt, h)

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
    """Recalculate recent sessions with the active two-layer M30 rules."""
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
    pair_dirs = get_pair_direction(hour, result.get("signal", "WAIT"), broker_dt, full_result=result)
    extra_fields = {
        field: result.get(field)
        for field in ENTRY_PLAN_FIELDS
        if field in result
    }
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
    """Publish one due v72 slot and fail closed until XAUUSD is ready."""
    key = (broker_dt.date(), hour)
    if key in sent_today or broker_dt < get_signal_datetime_for_slot(broker_dt, hour):
        return False
    result = calculate_slot_signal(broker_dt, hour)
    if not result:
        print(f"  [RETRY] H={hour} - no evaluation result")
        return False
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
            print(f"  [MISSED] H={hour} exceeded latest v72 entry deadline")
        else:
            print(f"  [RETRY] H={hour} - incomplete GBPAUD/XAUUSD M30 data")
        return False
    _persist_live_result(broker_dt, hour, result)
    if not _all_pair_entries_ready(result):
        print(f"  [RETRY] H={hour} - one or more GBP pair entries are incomplete")
        return False
    if should_send_xau_entry_alert(result, entry_alerts_sent):
        send_xau_entry_ready_alert(result, broker_dt=broker_dt)
    sent_today.add(key)
    _save_state(sent_today, broker_dt=broker_dt)
    print(f"  [SENT] H={hour} signal={result['signal']} entry={result['entry_time']}")
    return True


def main(profile_name=None):
    global mt5_ready, sent_today, _active_profile, _broker_clock_error, entry_alerts_sent, entry_alerts_pending
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
    reconcile_due_xau_entry_alerts(broker_dt)

    push_to_dashboard(snapshot_complete=True)
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
    """Return the four MT5 M30 open times used for one GBP signal."""
    slot = slot_dt.replace(minute=0, second=0, microsecond=0)
    return tuple(slot - timedelta(minutes=value) for value in (60, 90, 120, 150))


def xau_entry_layer_close_times(slot_dt):
    """Return user-facing close-time windows for both XAU entry layers."""
    slot = slot_dt.replace(minute=0, second=0, microsecond=0)
    if slot.hour == 3:
        layer1_offsets = (30, 60, 90)
        layer2_offsets = (0, 30, 60, 90)
    else:
        layer1_offsets = (60, 90, 120, 150)
        layer2_offsets = (30, 60, 90, 120)
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
    if not _valid_m30_ohlc(candle):
        return None
    open_price, close_price = float(candle["open"]), float(candle["close"])
    if close_price > open_price:
        return "TANG"
    if close_price < open_price:
        return "GIAM"
    return "DOJI"


def read_completed_m30_candle(symbol, open_dt, completed_by=None):
    """Read one exact, valid M30 candle that has closed by ``completed_by``."""
    if symbol not in SIGNAL_PAIRS:
        return None
    cutoff = completed_by or open_dt + timedelta(minutes=30)
    if open_dt + timedelta(minutes=30) > cutoff:
        return None
    target_ts = broker_time_to_ts(open_dt, open_dt.hour, open_dt.minute)
    candle = get_candle_by_ts(symbol, mt5.TIMEFRAME_M30, target_ts)
    if candle is None or not _valid_m30_ohlc(candle):
        return None
    try:
        return candle if int(candle["time"]) == int(target_ts) else None
    except (KeyError, TypeError, ValueError):
        return None


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


def _m30_candle_evidence(symbol, role, close_dt, candle):
    open_dt = close_dt - timedelta(minutes=30)
    evidence = _empty_m30_candle(role, open_dt, close_dt)
    if candle is None:
        return evidence
    evidence.update(_serialize_candle_ohlc(candle, symbol))
    evidence.update({"state": "READY", "direction": _m30_candle_direction(candle)})
    return evidence


def _classify_m30_layer(symbol, close_times, candles_by_close, classifier):
    candles = [
        _m30_candle_evidence(
            symbol,
            f"C{index + 1}{'_BASE' if index == 0 else ''}",
            close_dt,
            candles_by_close.get(close_dt),
        )
        for index, close_dt in enumerate(close_times)
    ]
    directions = [candle.get("direction") for candle in candles]
    classification = classifier(directions)
    return {
        "candles": candles,
        "directions": directions,
        "base_direction": directions[0] if directions else None,
        "group": classification["group"],
        "rule_number": classification["rule_number"],
    }


def _read_m30_close_windows(symbol, close_times, completed_by):
    return {
        close_dt: read_completed_m30_candle(
            symbol,
            close_dt - timedelta(minutes=30),
            completed_by,
        )
        for close_dt in sorted(set(close_times))
    }


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
        "signal_state": "WAIT",
        "entry_state": "WAIT",
        "classification_reason": "INCOMPLETE_GBP_M30_SIGNAL_WAIT",
    }


def evaluate_gbp_pair_signal_m30(slot_dt, hour, symbol):
    """Derive one GBP signal independently; XAU timing assigns its entry later."""
    result = _empty_gbp_signal_evidence(slot_dt, hour, symbol)
    if symbol not in GBP_SIGNAL_PAIRS or int(hour) not in ACTIVE_HOURS:
        return result
    open_times = gbp_signal_open_times(slot_dt)
    close_times = tuple(value + timedelta(minutes=30) for value in open_times)
    candles = _read_m30_close_windows(symbol, close_times, slot_dt)
    layer1 = _classify_m30_layer(symbol, close_times, candles, classify_four_candle_group)
    signal = derive_gbp_signal_from_layer1(layer1["base_direction"], layer1["group"])
    layer1.update(signal)
    ready = signal["signal"] in ("BUY", "SELL")
    result.update({
        "layer1": layer1,
        "direction": signal["signal"] if ready else "WAIT",
        "signal_state": "READY" if ready else "WAIT",
        "classification_reason": "INDEPENDENT_GBP_M30_SIGNAL" if ready else "INCOMPLETE_GBP_M30_SIGNAL_WAIT",
    })
    return result


def evaluate_xau_entry_timing_m30(slot_dt, hour):
    """Use XAU M30 Layer 1/2 groups to choose the final XAU entry."""
    windows = xau_entry_layer_close_times(slot_dt)
    close_times = (*windows["layer1"], *windows["layer2"])
    candles = _read_m30_close_windows("XAUUSD", close_times, slot_dt)
    layer1_classifier = classify_three_candle_group if int(hour) == 3 else classify_four_candle_group
    layer1 = _classify_m30_layer("XAUUSD", windows["layer1"], candles, layer1_classifier)
    layer2 = _classify_m30_layer("XAUUSD", windows["layer2"], candles, classify_four_candle_group)
    entry = select_two_layer_entry(hour, layer1["group"], layer2["group"])
    layer1["entry_candidates"] = entry["entry_candidates"]
    layer2["entry_selection"] = entry["entry_selection"]
    return {
        "symbol": "XAUUSD",
        "timeframe": "M30",
        "slot_hour": int(hour),
        "layer1": layer1,
        "layer2": layer2,
        "entry_time": entry["entry_time"],
        "entry_state": entry["state"],
        "classification_reason": "XAU_TWO_LAYER_M30_ENTRY" if entry["state"] == "READY" else "INCOMPLETE_XAU_M30_ENTRY_WAIT",
    }


def derive_xau_from_gbpaud(hour, gbpaud_evidence, timing_evidence):
    """Derive XAU direction from GBPAUD and entry from XAU timing layers."""
    source_signal = (gbpaud_evidence or {}).get("direction")
    timing_entry = (timing_evidence or {}).get("entry_time")
    signal_ready = source_signal in ("BUY", "SELL")
    timing_ready = (timing_evidence or {}).get("entry_state") == "READY" and bool(timing_entry)
    matches_gbpaud = int(hour) in (3, 14, 16)
    direction = source_signal if matches_gbpaud else reverse_signal(source_signal)
    ready = signal_ready and timing_ready
    return {
        "symbol": "XAUUSD",
        "logic_version": SIGNAL_LOGIC_VERSION,
        "timeframe": "M30",
        "slot_hour": int(hour),
        "source_symbol": "GBPAUD",
        "source_signal": source_signal if signal_ready else "WAIT",
        "direction_relation_to_gbpaud": "SAME" if matches_gbpaud else "OPPOSITE",
        "direction_rule": "SAME_AS_GBPAUD" if matches_gbpaud else "OPPOSITE_GBPAUD",
        "layer1": (timing_evidence or {}).get("layer1", {}),
        "layer2": (timing_evidence or {}).get("layer2", {}),
        "direction": direction if signal_ready else "WAIT",
        "entry_time": timing_entry if ready else None,
        "signal_state": "READY" if signal_ready else "WAIT",
        "entry_state": "READY" if ready else "WAIT",
        "classification_reason": "XAU_DIRECTION_GBPAUD_ENTRY_XAU_M30" if ready else "XAU_SIGNAL_OR_ENTRY_WAIT",
        "source_evidence": "pair_evidence.GBPAUD",
    }


def _evaluate_all_gbp_pairs(slot_dt, hour):
    evidence = {}
    for symbol in GBP_SIGNAL_PAIRS:
        try:
            evidence[symbol] = evaluate_gbp_pair_signal_m30(slot_dt, hour, symbol)
        except Exception as error:
            log.warning("GBP M30 evaluation failed for %s H=%s: %s", symbol, hour, error)
            evidence[symbol] = _empty_gbp_signal_evidence(slot_dt, hour, symbol)
    return evidence


def _assign_gbp_entries(pair_evidence, xau_timing):
    gbp_entry = deferred_gbp_entry_time((xau_timing or {}).get("entry_time"))
    for symbol in GBP_SIGNAL_PAIRS:
        item = pair_evidence[symbol]
        ready = item.get("direction") in ("BUY", "SELL") and bool(gbp_entry)
        item["entry_time"] = gbp_entry if ready else None
        item["entry_state"] = "READY" if ready else "WAIT"
        item["entry_rule"] = "NEXT_FULL_HOUR_AFTER_XAU" if ready else None


def _pair_payload_from_evidence(pair_evidence):
    return {
        "pair_dirs": {symbol: item.get("direction", "WAIT") for symbol, item in pair_evidence.items()},
        "pair_entry_times": {symbol: item.get("entry_time") for symbol, item in pair_evidence.items()},
        "pair_signal_states": {symbol: item.get("signal_state", "WAIT") for symbol, item in pair_evidence.items()},
        "pair_entry_states": {symbol: item.get("entry_state", "WAIT") for symbol, item in pair_evidence.items()},
    }


def _pair_entry_utc_map(slot_dt, pair_entry_times, broker_offset):
    return {
        symbol: compute_utc_iso(slot_dt.date(), pair_entry_times.get(symbol), broker_offset)
        for symbol in SIGNAL_PAIRS
    }


def _pair_group_labels(pair_groups):
    labels = {
        symbol: (f"L1 {pair_groups[symbol]}" if pair_groups.get(symbol) else None)
        for symbol in SIGNAL_PAIRS
    }
    if pair_groups.get("XAUUSD"):
        labels["XAUUSD"] = f"XAU L1 {pair_groups['XAUUSD']}"
    return labels


def evaluate_all_pairs_for_slot(broker_dt, hour):
    """Evaluate GBP directions first, then XAU Layer 1/2 entry timing."""
    h = int(hour)
    if broker_dt is None or h not in ACTIVE_HOURS:
        return None
    slot_dt = broker_dt.replace(hour=h, minute=0, second=0, microsecond=0)
    pair_evidence = _evaluate_all_gbp_pairs(slot_dt, h)
    timing = evaluate_xau_entry_timing_m30(slot_dt, h)
    _assign_gbp_entries(pair_evidence, timing)
    pair_evidence["XAUUSD"] = derive_xau_from_gbpaud(h, pair_evidence["GBPAUD"], timing)
    pair_evidence = {symbol: pair_evidence[symbol] for symbol in SIGNAL_PAIRS}
    payload = _pair_payload_from_evidence(pair_evidence)
    pair_entries = payload["pair_entry_times"]
    try:
        broker_offset = BROKER_CLOCK.utc_offset_for_date(slot_dt.date())
    except Exception:
        broker_offset = None
    pair_groups = {
        symbol: (item.get("layer1") or {}).get("group")
        for symbol, item in pair_evidence.items()
    }
    top_signal = payload["pair_dirs"]["XAUUSD"]
    top_entry = pair_entries["XAUUSD"]
    return {
        "logic_version": SIGNAL_LOGIC_VERSION,
        "record_revision": 2 if top_signal in ("BUY", "SELL") else 1,
        "state_updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "signal": top_signal,
        "signal_state": payload["pair_signal_states"]["XAUUSD"],
        "entry_state": payload["pair_entry_states"]["XAUUSD"],
        "entry_time": top_entry,
        "entry_candidate": top_entry,
        "entry_rule": "XAU_TWO_LAYER_M30" if top_entry else None,
        "entry_at_utc": compute_utc_iso(slot_dt.date(), top_entry, broker_offset),
        "broker_utc_offset": broker_offset,
        **payload,
        "pair_entry_at_utc": _pair_entry_utc_map(slot_dt, pair_entries, broker_offset),
        "pair_groups": pair_groups,
        "pair_labels": _pair_group_labels(pair_groups),
        "pair_evidence": pair_evidence,
        "source_date": slot_dt.date().isoformat(),
        "report": _two_layer_m30_report(h, slot_dt, pair_evidence),
    }


def _two_layer_m30_report(hour, slot_dt, pair_evidence):
    lines = [f"H={hour} ({slot_dt.date().isoformat()}) [v{SIGNAL_LOGIC_VERSION}] GBP signal -> XAU L1 -> XAU L2:"]
    for symbol in SIGNAL_PAIRS:
        item = pair_evidence[symbol]
        layer1 = (item.get("layer1") or {}).get("group")
        layer2 = (item.get("layer2") or {}).get("group")
        lines.append(
            f"  {symbol}: {item.get('direction', 'WAIT')} entry={item.get('entry_time') or 'WAIT'} "
            f"L1={layer1 or '-'} L2={layer2 or '-'}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=str, help="Profile name for heartbeat")
    args, _ = parser.parse_known_args()
    main(profile_name=args.profile)


