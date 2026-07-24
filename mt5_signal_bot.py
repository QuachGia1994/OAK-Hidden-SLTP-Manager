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

from utils import send_telegram_raw, send_telegram_photo_raw, send_telegram_with_keyboard, get_signal_icon, vn_direction
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
# Mon–Fri active rhythm slots. H=6/H=10/H=17 are intentionally inactive.
# Slot outputs may contain XAUUSD, GBPAUD, or the configured GBP group.
DISABLED_HOURS = set()

def get_target_minute(hour):
    """Return the configured target minute for a specific hour."""
    h = int(hour)
    if h in (7, 9, 14):
        return 15
    if h in (11, 1500):
        return 0
    return 45

TARGET_HOURS = [2, 3, 4, 5, 7, 9, 11, 12, 13, 14, 15]

def get_target_hours(broker_dt=None, weekday=None):
    """Return weekday-aware active rhythm slots."""
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
        if wd in (0, 3, 4):  # Mon (0), Thu (3), Fri (4)
            return [2, 3, 4, 5, 7, 9, 11, 12, 13, 14, 1500, 15]
        return [2, 3, 4, 5, 7, 9, 11, 12, 13, 14, 15]

    return [2, 3, 4, 5, 7, 9, 11, 12, 13, 14, 15]
# Bump when pair-direction / slot rules change to trace rebuilds in logs.
SIGNAL_LOGIC_VERSION = 23
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
               pattern_signal=None, h11_candles=None):
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
    if h11_candles:
        record["h11_candles"] = h11_candles
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
    if hour in DISABLED_HOURS:
        return False
    if signal.get("pair_dirs"):
        return True
    candles = signal.get("h11_candles") or []
    return hour == 11 and signal.get("signal") in ("SW", "BT") and len(candles) == 4


def select_signals_for_dashboard(all_signals):
    """Keep renderable signal and H=11 classification history across days."""
    return [signal for signal in all_signals if _has_dashboard_payload(signal)]


def _dashboard_log_pair_dirs(hour, signal, pair_dirs):
    """Return live-log directions without inventing a tradable H=11 pair."""
    if pair_dirs:
        return pair_dirs
    if int(hour) == 11:
        return {}
    if int(hour) in (9, 14):
        return {pair: signal for pair in GBP_PAIRS}
    return {"XAUUSD": signal}


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
    rules = "\n".join(f"⚠️ {note}" for note in day_notes)
    mt5_status = "OK" if mt5_connected else "N/A"
    return (
        "🤖 BOT KHỞI ĐỘNG\n"
        f"Nguồn pattern: {SYMBOL} | MT5: {mt5_status}\n"
        f"Slots: {', '.join(f'H={h}' for h in TARGET_HOURS)}\n"
        "🔒 Auto-close: XAUUSD 17:49, GBP 19:49 (Broker)\n"
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


def send_telegram_photo(photo_bytes, caption=None):
    try:
        return send_telegram_photo_raw(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, photo_bytes, caption)
    except Exception as e:
        print(f"[ERROR] Telegram photo: {e}")
        return None


def render_h11_chart_png(candles, group, detail, slot_hour=11):
    """Draw a dark-themed candlestick chart image for H11 (4 H1 candles) or H15:00 (4 M30 candles)."""
    try:
        from PIL import Image, ImageDraw
        import io

        width, height = 640, 360
        bg_color = (13, 17, 23)  # #0d1117
        img = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Title
        label = "Sideway" if group == "SW" else "Bình Thường"
        tf_label = "M30" if slot_hour == 1500 else "H1"
        title_text = f"PHÂN NHÓM {tf_label} XAUUSD: {label} ({group})"
        draw.text((20, 15), title_text, fill=(255, 255, 255))
        if detail:
            draw.text((20, 35), str(detail), fill=(156, 163, 175))

        if not candles:
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()

        highs = [float(c.get("high", max(c.get("open", 0), c.get("close", 0)))) for c in candles]
        lows = [float(c.get("low", min(c.get("open", 0), c.get("close", 0)))) for c in candles]
        max_p = max(highs) if highs else 100.0
        min_p = min(lows) if lows else 0.0
        if max_p == min_p:
            max_p += 1.0
            min_p -= 1.0
        margin = (max_p - min_p) * 0.15
        max_p += margin
        min_p -= margin

        chart_top = 70
        chart_bottom = 290
        chart_height = chart_bottom - chart_top

        def price_to_y(p):
            return chart_bottom - int(((p - min_p) / (max_p - min_p)) * chart_height)

        n = len(candles)
        col_width = (width - 60) // max(n, 1)

        for i, c in enumerate(candles):
            x_center = 30 + i * col_width + col_width // 2
            candle_lbl = c.get("label") or f"H={c.get('hour', i)}"
            open_p = float(c.get("open", 0))
            close_p = float(c.get("close", 0))
            high_p = float(c.get("high", max(open_p, close_p)))
            low_p = float(c.get("low", min(open_p, close_p)))

            is_up = close_p >= open_p
            color = (16, 185, 129) if is_up else (239, 68, 68)  # green / red

            # Wick
            y_high = price_to_y(high_p)
            y_low = price_to_y(low_p)
            draw.line([(x_center, y_high), (x_center, y_low)], fill=color, width=2)

            # Body
            y_open = price_to_y(open_p)
            y_close = price_to_y(close_p)
            top_y = min(y_open, y_close)
            bot_y = max(y_open, y_close)
            if bot_y - top_y < 2:
                bot_y = top_y + 2

            body_width = int(col_width * 0.45)
            left_x = x_center - body_width // 2
            right_x = x_center + body_width // 2
            draw.rectangle([(left_x, top_y), (right_x, bot_y)], fill=color, outline=color)

            # Labels
            draw.text((x_center - 18, chart_bottom + 10), candle_lbl, fill=(156, 163, 175))
            price_lbl = f"C: {close_p}"
            draw.text((x_center - 22, chart_bottom + 26), price_lbl, fill=color)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as e:
        print(f"[ERROR] Failed to render H11 chart image: {e}")
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
            d_m30 = "TANG"
        print(f"  [DOJI] M30 XAUUSD@{H-1}:30 DOJI -> fallback: {d_m30}")
    if d_m30 and d_m30 != "DOJI":
        return "BUY" if d_m30 == "TANG" else "SELL"
    return None


def is_special_day(broker_dt):
    """
    - Thứ 5, Thứ 6 mà có Thứ 6 là ngày đầu tháng (ngày <= 7)
    - Thứ 2 mà Thứ 6 tuần trước là ngày đầu tháng (ngày <= 7)
    """
    if broker_dt is None:
        return False
        
    wd = broker_dt.weekday()
    dt = broker_dt.date()
    
    if wd == 4: # Thứ 6
        return dt.day <= 7
    elif wd == 3: # Thứ 5
        friday_dt = dt + timedelta(days=1)
        return friday_dt.day <= 7
    elif wd == 0: # Thứ 2
        last_friday_dt = dt - timedelta(days=3)
        return last_friday_dt.day <= 7
        
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

def _lookup_historical_t2_gbp_signal(broker_dt, target_hour):
    """Look up the previous Monday GBPAUD signal for Thursday history reuse."""
    monday_date = broker_dt.date() - timedelta(days=3)
    date_str = monday_date.isoformat()
    try:
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            for record in reversed(data):
                if record.get("date") == date_str and int(record.get("hour", -1)) == target_hour:
                    pair_dirs = record.get("pair_dirs", {})
                    sig = pair_dirs.get("GBPAUD")
                    if sig in ("BUY", "SELL"):
                        return sig
    except Exception:
        pass
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

    Update the XAUUSD direction after M30 post-processing.
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
    
    if pattern_signal != "WAIT" and not result.get("skip_xau_m30"):
        apply_xauusd_m30_logic(pair_dirs, pattern_signal, broker_dt, hour)
        
    final_signal = pair_dirs.get("XAUUSD", pattern_signal)
    if reverse:
        final_signal = reverse_signal(final_signal) or final_signal
    result["pattern_signal"] = pattern_signal
    result["signal"] = final_signal
    result["skip_xau_m30"] = True
    return result





def evaluate_classification_for_slot(broker_dt, slot_hour, symbol="XAUUSD"):
    """Evaluate 4 H1 candles ending at slot_hour - 1.
    For slot_hour=11, evaluates H=10, 9, 8, 7.
    """
    h1, h2, h3, h4 = slot_hour - 1, slot_hour - 2, slot_hour - 3, slot_hour - 4
    if broker_dt is None:
        return "BT", f"H{h1}:Tăng, H{h2}:Tăng, H{h3}:Giảm, H{h4}:Giảm [Rule 3]", []

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
                d = doji_d if doji_d in ("TANG", "GIAM") else "TANG"
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
            d = "TANG"
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

def evaluate_h11_classification(broker_dt, symbol="XAUUSD"):
    """Backward compatible wrapper for H=11 logic."""
    return evaluate_classification_for_slot(broker_dt, 11, symbol)


def resolve_h1500_signal(group, m1_signal, weekday, is_special):
    """
    Normal days (is_special=False):
      Mon (wd=0): SW -> Follow (cùng chiều m1), BT -> Reverse (đảo ngược m1)
      Thu/Fri (wd in (3, 4)): SW -> Reverse (đảo ngược m1), BT -> Follow (cùng chiều m1)
    Special days (is_special=True):
      Thu/Fri (wd in (3, 4)): SW -> Follow (cùng chiều m1), BT -> Reverse (đảo ngược m1)
      Mon (wd=0): SW -> Reverse (đảo ngược m1), BT -> Follow (cùng chiều m1)
    """
    sw_means_follow = (weekday == 0 and not is_special) or (weekday in (3, 4) and is_special)
    if group == "SW":
        return m1_signal if sw_means_follow else reverse_signal(m1_signal)
    else:  # BT
        return reverse_signal(m1_signal) if sw_means_follow else m1_signal


def evaluate_h15_m30_classification(broker_dt, symbol="XAUUSD"):
    """Evaluate 4 M30 candles before 15:00 Broker time.
    M30 candles: 14:30 (m1), 14:00 (m2), 13:30 (m3), 13:00 (m4).
    """
    if broker_dt is None:
        return "BT", "14:30:Tăng, 14:00:Tăng, 13:30:Giảm, 13:00:Giảm [Rule 3]", "BUY", "BUY", []

    m_times = [(13, 0), (13, 30), (14, 0), (14, 30)]
    dirs = {}
    vn_dirs = {}
    candles = []
    for h, m in m_times:
        ts = broker_time_to_ts(broker_dt, h, m)
        c = get_candle_by_ts(symbol, mt5.TIMEFRAME_M30, ts)
        if c is not None:
            open_p = round(float(_rate_value(c, "open")), 2)
            close_p = round(float(_rate_value(c, "close")), 2)
            high_p = round(float(_rate_value(c, "high", max(open_p, close_p))), 2)
            low_p = round(float(_rate_value(c, "low", min(open_p, close_p))), 2)
            d = candle_direction(c)
            is_doji = (d == "DOJI")
            if is_doji:
                doji_d = resolve_doji(symbol, mt5.TIMEFRAME_M30, ts, broker_dt)
                d = doji_d if doji_d in ("TANG", "GIAM") else "TANG"
                print(f"  [DOJI] M30@{h:02d}:{m:02d} DOJI -> fallback: {d}")
            candles.append({
                "hour": h,
                "label": f"{h:02d}:{m:02d}",
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "dir": d,
                "doji": is_doji,
            })
        else:
            d = "TANG"
        time_key = f"{h:02d}:{m:02d}"
        dirs[time_key] = d
        vn_dirs[time_key] = "Tăng" if d == "TANG" else "Giảm"

    d1 = dirs["14:30"]
    d2 = dirs["14:00"]
    d3 = dirs["13:30"]
    d4 = dirs["13:00"]

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

    m1_signal = "BUY" if d1 == "TANG" else "SELL"
    weekday = broker_dt.weekday()
    is_sp = is_special_day(broker_dt)
    final_signal = resolve_h1500_signal(group, m1_signal, weekday, is_sp)

    detail = f"14:30:{vn_dirs['14:30']}, 14:00:{vn_dirs['14:00']}, 13:30:{vn_dirs['13:30']}, 13:00:{vn_dirs['13:00']} [Rule {rule_num}]"
    return group, detail, final_signal, m1_signal, candles


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
    # H=15:00: XAUUSD M30 4-candle classification (14:30, 14:00, 13:30, 13:00) on Mon (0), Thu (3), Fri (4)
    if hour == 1500:
        if broker_dt.weekday() not in (0, 3, 4):
            return {
                "signal": "WAIT",
                "report": "H=15:00: chỉ hoạt động vào Thứ 2, Thứ 5, Thứ 6.",
                "m30_dir": None,
                "h1_signal": None,
                "skip_xau_m30": True,
                "pair_dirs": {},
            }
        group, detail, final_signal, m1_sig, candles = evaluate_h15_m30_classification(broker_dt)
        sp_tag = " [Special Day]" if is_special_day(broker_dt) else ""
        return {
            "signal": final_signal,
            "pattern_signal": m1_sig,
            "report": f"H=15:00{sp_tag}: M30 Phân nhóm {group} ({detail}) -> XAUUSD {final_signal}",
            "m30_dir": None,
            "h1_signal": None,
            "skip_xau_m30": True,
            "pair_dirs": {"XAUUSD": final_signal},
            "h11_candles": candles,
        }
    # H=2,3: XAUUSD đảo từ H=5 hôm qua (Nếu Thứ 5 thì dùng lại y chang Thứ 2)
    if hour in (2, 3):
        if broker_dt.weekday() == 3:  # Thứ 5
            historical_signal = _lookup_historical_t2_signal(broker_dt, hour)
            if historical_signal not in ("BUY", "SELL"):
                return {"signal": "WAIT", "report": f"H={hour}: thiếu lịch sử Thứ 2.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
            return {"signal": historical_signal, "pattern_signal": historical_signal, "report": f"H={hour}: dùng lịch sử Thứ 2 ({historical_signal}).", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        else:
            h5_yesterday = _lookup_h5_signal_yesterday(broker_dt)
            if h5_yesterday not in ("BUY", "SELL"):
                return {"signal": "WAIT", "report": f"H={hour}: thiếu H=5 hôm qua.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
            final_signal = reverse_signal(h5_yesterday)
            return {"signal": final_signal, "pattern_signal": h5_yesterday, "report": f"H={hour}: đảo H=5 hôm qua ({h5_yesterday} -> {final_signal}).", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
    # H=7: XAUUSD đảo từ H=5 hôm nay
    if hour == 7:
        h5_today = _lookup_h5_signal_today(broker_dt)
        if h5_today not in ("BUY", "SELL"):
            return {"signal": "WAIT", "report": f"H={hour}: thiếu H=5 hôm nay.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        final_signal = reverse_signal(h5_today)
        return {"signal": final_signal, "pattern_signal": h5_today, "report": f"H={hour}: đảo H=5 hôm nay ({h5_today} -> {final_signal}).", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
    # H=9: MIXED (XAUUSD đảo H=5 hôm nay, GBP đảo H=5 hôm qua)
    if hour == 9:
        h5_today = _lookup_h5_signal_today(broker_dt)
        h5_yesterday = _lookup_h5_signal_yesterday(broker_dt)
        
        if h5_today not in ("BUY", "SELL") and h5_yesterday not in ("BUY", "SELL"):
            return {"signal": "WAIT", "report": "H=9: thiếu cả H=5 hôm nay và hôm qua.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        
        final_xau = reverse_signal(h5_today) if h5_today in ("BUY", "SELL") else "WAIT"
        wd = broker_dt.weekday()
        final_gbp = (h5_yesterday if wd == 4 else reverse_signal(h5_yesterday)) if h5_yesterday in ("BUY", "SELL") else "WAIT"
        
        report = (f"H=9 [XAUUSD]: {'đảo H=5 hôm nay (' + h5_today + ' -> ' + final_xau + ')' if final_xau != 'WAIT' else 'chờ H=5 hôm nay'}\n"
                  f"H=9 [GBP]: {('cùng' if wd == 4 else 'đảo') + ' H=5 hôm qua (' + h5_yesterday + ' -> ' + final_gbp + ')' if final_gbp != 'WAIT' else 'chờ H=5 hôm qua'}")
        
        return {
            "signal": "MIXED",
            "xau_signal": final_xau,
            "gbp_signal": final_gbp,
            "report": report,
            "m30_dir": None,
            "h1_signal": None,
            "skip_xau_m30": True
        }
        

    # H=11: Phân nhóm H1 XAUUSD (SW/BT) liên quan H=2,3 ngày mai
    if hour == 11:
        res_h11 = evaluate_h11_classification(broker_dt)
        group = res_h11[0] if isinstance(res_h11, (tuple, list)) else "BT"
        detail = res_h11[1] if isinstance(res_h11, (tuple, list)) and len(res_h11) > 1 else ""
        candles = res_h11[2] if isinstance(res_h11, (tuple, list)) and len(res_h11) > 2 else []
        return {
            "signal": group,
            "pattern_signal": group,
            "report": f"H=11: Nhóm {group} ({detail})",
            "m30_dir": None,
            "h1_signal": None,
            "skip_xau_m30": True,
            "pair_dirs": {},
            "h11_candles": candles,
        }
    # H=14: GBP group cùng chiều H=5 hôm nay (Thứ 6 đảo), không XAUUSD
    if hour == 14:
        h5_today = _lookup_h5_signal_today(broker_dt)
        if h5_today not in ("BUY", "SELL"):
            return {"signal": "WAIT", "report": "H=14: thiếu H=5 hôm nay.", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
        wd = broker_dt.weekday()
        final_signal = reverse_signal(h5_today) if wd == 4 else h5_today
        return {"signal": final_signal, "pattern_signal": h5_today, "report": f"H=14: {'đảo' if wd == 4 else 'cùng'} H=5 hôm nay ({h5_today} -> {final_signal}).", "m30_dir": None, "h1_signal": None, "skip_xau_m30": True}
    # H=15: XAUUSD đảo ngược vào Thứ 4 (weekday == 2) và Thứ 5 (weekday == 3)
    if hour == 15 and broker_dt.weekday() in (2, 3):
        result = analyze(broker_dt, hour)
        final_result = _finalize_pattern_result(result, broker_dt, hour, reverse=True)
        if final_result.get("signal") in ("BUY", "SELL"):
            wd_name = "Thứ 4" if broker_dt.weekday() == 2 else "Thứ 5"
            final_result["report"] += f"\n  -> [{wd_name}] Đảo ngược XAUUSD: {final_result['signal']}"
        return final_result

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
    """Tính signal cho các slot cơ bản (không phải nhóm giờ đặc biệt như 2,3,9...)."""
    actual_broker_time = get_broker_time()
    if broker_dt.date() == actual_broker_time.date():
        target_min = get_target_minute(H)
        if actual_broker_time.hour < H or (actual_broker_time.hour == H and actual_broker_time.minute < target_min):
            return {"signal": "WAIT", "report": f"Chua toi {fmt_hour(H)}:{target_min:02d}", "skip_xau_m30": True}

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
    """Determine today's priority slot and no-gold labels.

    - Priority slot (H=2, H=3): based on YESTERDAY's H=11 classification (SW vs BT).
    - No-gold label (H=12,13,15): based on TODAY's H=11 classification (SW vs BT).
    """
    if broker_dt is None:
        return {
            "prev_h11_group": "BT",
            "today_h11_group": "BT",
            "priority_slot": 2,
            "priority_label": "Ưu tiên H=2",
            "has_nogold_label": False,
        }

    # --- Yesterday's H=11 → priority slot ---
    d = broker_dt.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    prev_dt = datetime.combine(d, datetime.min.time(), tzinfo=broker_dt.tzinfo or timezone.utc)
    res_prev = evaluate_h11_classification(prev_dt)
    prev_group = res_prev[0] if isinstance(res_prev, (tuple, list)) else "BT"

    # --- Today's H=11 → no-gold label ---
    res_today = evaluate_h11_classification(broker_dt)
    today_group = res_today[0] if isinstance(res_today, (tuple, list)) else "BT"

    weekday = broker_dt.weekday()  # 0: Mon, 1: Tue, 2: Wed, 3: Thu, 4: Fri
    is_special = is_special_day(broker_dt)

    # ── Priority slot (from yesterday's H=11) ──
    priority_slot = 2

    if weekday == 0:  # Monday (Yesterday was Friday)
        priority_slot = 3 if prev_group == "SW" else 2
    elif weekday == 1:  # Tuesday (Yesterday was Monday)
        priority_slot = 2 if prev_group == "SW" else 3
    elif weekday == 2:  # Wednesday (Yesterday was Tuesday)
        priority_slot = 2 if prev_group == "SW" else 3
    elif weekday == 3:  # Thursday (Reuse Monday's priority based on last Friday's H11)
        friday_dt = broker_dt - timedelta(days=6)
        res_friday = evaluate_h11_classification(friday_dt)
        friday_group = res_friday[0] if isinstance(res_friday, (tuple, list)) else "BT"
        priority_slot = 3 if friday_group == "SW" else 2
    elif weekday == 4:  # Friday (Yesterday was Thursday)
        priority_slot = 3 if prev_group == "SW" else 2

    priority_label = f"Ưu tiên đi H={priority_slot}"

    # ── No-gold label (from TODAY's H=11) ──
    has_nogold = False

    if weekday == 0:    # Monday: BT → no-gold
        has_nogold = (today_group == "BT")
    elif weekday == 1:  # Tuesday: SW → no-gold
        has_nogold = (today_group == "SW")
    elif weekday == 2:  # Wednesday: SW → no-gold
        has_nogold = (today_group == "SW")
    elif weekday == 3:  # Thursday: SW → no-gold; special day BT → also no-gold
        has_nogold = (today_group == "SW") or (is_special and today_group == "BT")
    elif weekday == 4:  # Friday: BT → no-gold
        has_nogold = (today_group == "BT")

    return {
        "prev_h11_group": prev_group,
        "today_h11_group": today_group,
        "priority_slot": priority_slot,
        "priority_label": priority_label,
        "has_nogold_label": has_nogold,
    }



def get_h7_h9_priority_rule(broker_dt):
    """Prioritize H=9 when H=6 candle dir matches expected reversal dir, else H=7.

    H=8 was merged into H=9 — so priority is either H=7 or H=9.
    Rule: XAUUSD expected direction at H=7/H=9 = reverse of H=5 today.
    - If H=6 candle direction == expected_dir  → H=9 is priority
    - If H=6 candle direction != expected_dir  → H=7 is priority
    """
    if broker_dt is None:
        return None
    if (broker_dt.hour, broker_dt.minute) < (7, 0):
        return None

    h5_today = _lookup_h5_signal_today(broker_dt)
    if h5_today not in ("BUY", "SELL"):
        return None
    # XAUUSD reverses H=5 → expected dir is opposite
    expected_dir = "GIAM" if h5_today == "BUY" else "TANG"

    ts_h6 = broker_time_to_ts(broker_dt, 6, 0)
    c_h6 = get_candle_by_ts("XAUUSD", mt5.TIMEFRAME_H1, ts_h6)
    if c_h6 is None:
        return None
    if c_h6["close"] > c_h6["open"]:
        h6_dir = "TANG"
    elif c_h6["close"] < c_h6["open"]:
        h6_dir = "GIAM"
    else:
        h6_dir = resolve_doji("XAUUSD", mt5.TIMEFRAME_H1, ts_h6, broker_dt)
        if h6_dir not in ("TANG", "GIAM"):
            return None

    # H=6 confirms trend → H=9 (deeper continuation), otherwise H=7 catches the early move
    priority_slot = 9 if h6_dir == expected_dir else 7
    return {"priority_slot": priority_slot, "priority_label": f"Ưu tiên đi H={priority_slot}"}


# Keep old alias for backward compatibility with tests that import the old name
get_h7_h8_priority_rule = get_h7_h9_priority_rule


def is_xau_no_trade_label_slot(H, broker_dt=None, weekday=None):
    """Return True if slot H has a no-gold label attached based on today's H=11 SW/BT logic,
    OR if H=12,13 has its own 4-candle lookback evaluating to SW."""
    try:
        h = int(H)
    except (TypeError, ValueError):
        return False

    if h not in (12, 13, 15):
        return False

    if broker_dt is None:
        return False

    # 1. Inherit from H=11
    rules = get_h11_priority_and_nogold_rules(broker_dt)
    has_label = rules["has_nogold_label"]

    # 2. Evaluate independent 4-candle logic for H=12 and H=13 if the time has come
    if h in (12, 13):
        actual_broker_time = get_broker_time()
        if broker_dt.date() < actual_broker_time.date() or actual_broker_time.hour >= h:
            group, _, _ = evaluate_classification_for_slot(broker_dt, h)
            if group == "SW":
                has_label = True

    return has_label


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
        return ""
    if h in DISABLED_HOURS:
        return ""
    if h == 1500:
        return "XAUUSD theo M30 (13:00-14:30) (Thứ 2 / Thứ 5 / Thứ 6)"
    if h == 11:
        if broker_dt is not None:
            res_h11 = evaluate_h11_classification(broker_dt)
            group = res_h11[0] if isinstance(res_h11, (tuple, list)) else "BT"
            detail = res_h11[1] if isinstance(res_h11, (tuple, list)) and len(res_h11) > 1 else ""
            return f"H=11: Nhóm {group} ({detail})"
        return "H=11: Phân nhóm H1 (SW/BT) từ H=10,9,8,7"

    rules = get_h11_priority_and_nogold_rules(broker_dt) if broker_dt is not None else None
    h79_rules = get_h7_h9_priority_rule(broker_dt) if broker_dt is not None and h in (7, 9) else None

    notes = {
        2: "XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua",
        3: "XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua",
        7: "XAUUSD đảo từ H=5 hôm nay",
        9: "XAUUSD đảo từ H=5 hôm nay; GBP group đảo từ H=5 hôm qua",
        14: "GBP group cùng chiều H=5 hôm nay",
    }
    if broker_dt is not None:
        if broker_dt.weekday() == 2:  # Wednesday (Thứ 4)
            notes[2] = "XAUUSD đảo từ H=5 hôm qua"
            notes[3] = "XAUUSD đảo từ H=5 hôm qua"
            notes[9] = "XAUUSD đảo từ H=5 hôm nay"
            notes[14] = "Tắt nhóm GBP (Thứ 4)"
        elif h in (2, 3) and broker_dt.weekday() == 3:
            notes[2] = "XAUUSD & GBPAUD dùng lại lịch sử của Thứ 2"
            notes[3] = "XAUUSD & GBPAUD dùng lại lịch sử của Thứ 2"
        elif broker_dt.weekday() == 4:
            notes[2] = "XAUUSD đảo từ H=5 hôm qua; GBPAUD ngược chiều H=5 hôm qua"
            notes[3] = "XAUUSD đảo từ H=5 hôm qua; GBPAUD ngược chiều H=5 hôm qua"
            notes[9] = "XAUUSD đảo từ H=5 hôm nay; GBP cùng chiều H=5 hôm qua (Thứ 6)"
            notes[14] = "GBP group đảo từ H=5 hôm nay (Thứ 6)"
    base_note = notes.get(h, "Chỉ Vàng (XAUUSD)")

    if rules is not None:
        if h == rules["priority_slot"]:
            prefix = f"★ {rules['priority_label']}"
            base_note = f"{prefix} · {base_note}" if base_note else prefix
            
    if is_xau_no_trade_label_slot(H, broker_dt=broker_dt):
        base_note = base_note + "; 🚫 no-gold label" if base_note else "🚫 no-gold label"

    if h79_rules is not None:
        if h == h79_rules["priority_slot"]:
            prefix = f"★ {h79_rules['priority_label']}"
            base_note = f"{prefix} · {base_note}" if base_note else prefix

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
    elif xau in ("SW", "BT"):
        icon = "🟡" if xau == "SW" else "⚪"
        lbl = "Sideway" if xau == "SW" else "Bình Thường"
        lines.append(f"  XAUUSD: {icon} {lbl}")
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


def get_pair_direction(H, signal, broker_dt, h1_signal=None, full_result=None):
    """Return the configured XAU or GBP output directions for one slot."""
    result = {}
    h = int(H)
    if h in DISABLED_HOURS:
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
        if h in (12, 13, 15):
            result["XAUUSD"] = "WAIT"
        return result
    if signal not in ("BUY", "SELL"):
        return result
    # H=9,14: GBP group only, no XAUUSD
    if h in (9, 14):
        pairs_to_use = GBP_PAIRS
        if h == 14 and broker_dt is not None and broker_dt.weekday() in (2, 3):
            pairs_to_use = ["GBPAUD", "GBPJPY"]
        for pair in pairs_to_use:
            result[pair] = signal
        return result
    # All active hours: XAUUSD
    result["XAUUSD"] = signal
    apply_d_direction_marker(result, H, broker_dt)
    # H=2,3: add GBPAUD
    if h in (2, 3) and broker_dt is not None:
        if broker_dt.weekday() == 3:  # Thursday
            gbp_historical = _lookup_historical_t2_gbp_signal(broker_dt, h)
            if gbp_historical in ("BUY", "SELL"):
                result["GBPAUD"] = gbp_historical
        elif broker_dt.weekday() == 4:  # Friday: GBPAUD reverse from H=5 yesterday
            h5_yesterday = _lookup_h5_signal_yesterday(broker_dt)
            if h5_yesterday in ("BUY", "SELL"):
                result["GBPAUD"] = "SELL" if h5_yesterday == "BUY" else "BUY"
        else:
            h5_yesterday = _lookup_h5_signal_yesterday(broker_dt)
            if h5_yesterday in ("BUY", "SELL"):
                result["GBPAUD"] = h5_yesterday
    if broker_dt is not None and broker_dt.weekday() == 2:
        for gbp_pair in GBP_PAIRS:
            result.pop(gbp_pair, None)
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
        full_result=signal_data
    )

    # Canonical slot calculation already applies XAU M30 once.
    if not signal_data.get("skip_xau_m30"):
        apply_xauusd_m30_logic(pair_dirs, sig, broker_dt, H)

    # Hiển thị các output pair của slot.
    pair_text = format_telegram_pair_block(pair_dirs, H, broker_dt)

    if sig in ("SW", "BT"):
        label = "Sideway" if sig == "SW" else "Bình Thường"
        conclusion = f"PHÂN NHÓM H1: {icon} {label} ({sig})\n"
        msg = (
            f"📊 Phân nhóm H1 XAUUSD - {icon} {label}\n"
            f"============================\n"
            f"  {fmt_hour(H)}:{get_target_minute(H):02d} (Broker)\n"
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
    elif sig == "MIXED":
        conclusion = f"KẾT LUẬN: ĐA HƯỚNG\n"
        msg = (
            f"⚪ Tín hiệu pattern ĐA HƯỚNG\n"
            f"============================\n"
            f"  {fmt_hour(H)}:{get_target_minute(H):02d} (Broker)\n"
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
    else:
        conclusion = f"KẾT LUẬN (XAUUSD): {icon} {sig}\n"
        msg = (
            f"{emoji} Tín hiệu pattern {SYMBOL} - {icon} {sig}\n"
            f"============================\n"
            f"  {fmt_hour(H)}:{get_target_minute(H):02d} (Broker)\n"
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

    if H in (11, 1500) or sig in ("SW", "BT"):
        candles = signal_data.get("h11_candles") or []
        photo_bytes = render_h11_chart_png(candles, sig, report, slot_hour=H)
        if photo_bytes:
            send_telegram_photo(photo_bytes, caption=msg)
        else:
            send_telegram(msg)
    else:
        send_telegram(msg)



    return pair_dirs

# =====================================================================
def is_slot_ready(broker_dt, hour):
    """Check if slot hour can be calculated based on time or dependency availability.

    - H=2, 3, 9: ready as soon as H=5 yesterday exists.
    - H=7, 8, 14: ready as soon as H=5 today exists.
    - H=11: ready as soon as H=10 candle closes (broker hour >= 11).
    - H=4, 5, 12, 13, 15: ready once hour < broker_dt.hour or (hour == broker_dt.hour and broker_dt.minute >= 45).
    """
    h = int(hour)
    if h in (2, 3, 9):
        return _lookup_h5_signal_yesterday(broker_dt) in ("BUY", "SELL")
    if h in (7, 8, 14):
        return _lookup_h5_signal_today(broker_dt) in ("BUY", "SELL")
    if h == 1500:
        return broker_dt.hour >= 15
    if h in (11, 12, 13, 15):
        return broker_dt.hour >= 11
    target_min = get_target_minute(h)
    return broker_dt.hour > h or (broker_dt.hour == h and broker_dt.minute >= target_min)


# =====================================================================
# REBUILD: tính lại signals_log từ MT5 khi bot khởi động (tránh push data cũ)
# =====================================================================
def rebuild_slot_signal(broker_dt, h):
    """Recalculate one slot with current logic and overwrite signals_log (date, hour)."""
    if broker_dt.weekday() >= 5:
        return False

    result = calculate_slot_signal(broker_dt, h)
    sig = result.get("signal")
    if sig not in ("BUY", "SELL", "SW", "BT", "WAIT", "MIXED"):
        return False

    pair_dirs = get_pair_direction(h, sig, broker_dt, h1_signal=result.get("h1_signal"), full_result=result)
    if h != 11 and not pair_dirs:
        return False

    if not result.get("skip_xau_m30"):
        apply_xauusd_m30_logic(pair_dirs, sig, broker_dt, h)

    hour_note = get_hour_note(h, broker_dt=broker_dt)
    log_signal(h, broker_dt, sig, None, pair_dirs, hour_note,
               pattern_signal=result.get("pattern_signal"),
               h11_candles=result.get("h11_candles"))
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
        filtered = [record for record in data if record.get("date") not in rebuild_dates]
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
            slot_hour_num = 15 if hour == 1500 else hour
            slot_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=slot_hour_num)
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
    print(f"  Auto-close: XAUUSD 17:49, GBP 19:49 (Broker)")
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

    # Mark all passed hours of today as already sent to Telegram to prevent restart spamming
    hours_today = get_target_hours(broker_dt)
    for h in hours_today:
        if h < broker_dt.hour:
            sent_today.add((broker_dt.date(), h))
    _save_state(day_signals, sent_today)

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

            # 1) Quietly pre-calculate & refresh Dashboard for all ready slots (no Telegram push)
            for h in hours_now:
                if is_slot_ready(broker_dt, h):
                    rebuild_slot_signal(broker_dt, h)
            push_to_dashboard()

            # 2) Live Telegram push ONLY at target minute of slot H
            target_min = get_target_minute(now_hour)
            if now_min == target_min and now_hour in hours_now:
                key = (broker_dt.date(), now_hour)
                if key not in sent_today:
                    print(f"\n[{fmt_time(broker_dt)}] Kích hoạt H={fmt_hour(now_hour)}:{target_min:02d} (Gửi Telegram Live)")

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
                    full_result=result
                )

                # Log for website (even WAIT signals)
                hour_note = get_hour_note(now_hour, broker_dt=broker_dt)
                log_pair_dirs = _dashboard_log_pair_dirs(now_hour, sig, pair_dirs)
                log_signal(now_hour, broker_dt, sig, None, log_pair_dirs, hour_note,
                           pattern_signal=result.get("pattern_signal"),
                           h11_candles=result.get("h11_candles"))
                push_to_dashboard()

                if sig not in ("BUY", "SELL", "SW", "BT", "MIXED"):
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

                # Auto-close XAUUSD: 17:49 các ngày trong tuần
                xau_close_hour = 17
                if now_hour == xau_close_hour and now_min == 49:
                    today_key = broker_dt.date()
                    if today_key not in _xauusd_closed_today:
                        closed = _close_positions_by_prefix(["XAUUSD"], f"XAUUSD-17:49")
                        if closed > 0:
                            send_telegram(f"🔒 Đã đóng {closed} lệnh XAUUSD lúc 17:49 (Broker)")
                            print(f"  [AUTO-CLOSE] Closed {closed} XAUUSD positions at 17:49")
                        _xauusd_closed_today.add(today_key)

                # Auto-close GBP at 19:49
                if now_hour == 19 and now_min == 49:
                    today_key = broker_dt.date()
                    if today_key not in _gbp_closed_today:
                        closed = _close_positions_by_prefix(["GBPAUD", "GBPCAD", "GBPJPY", "GBPUSD"], "GBP-19:49")
                        if closed > 0:
                            send_telegram(f"🔒 Đã đóng {closed} lệnh GBP lúc 19:49 (Broker)")
                            print(f"  [AUTO-CLOSE] Closed {closed} GBP positions at 19:49")
                        _gbp_closed_today.add(today_key)

                # Tối ưu sleep: thức tỉnh vào mỗi đầu phút (giây = 0)
                wait = 60.0 - broker_dt.second
                wait = min(max(wait, 1.0), 60.0)
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
