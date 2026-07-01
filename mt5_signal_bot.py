# -*- coding: utf-8 -*-
"""
MT5 Multi-Timeframe Signal Bot v3.6.0
"""
import os
import sys
import json
import time
import calendar
from datetime import datetime, timedelta, timezone
import urllib.request
import urllib.parse

from utils import send_telegram_raw, load_json_file, get_signal_icon, vn_direction
from oak_trading_reminders import get_day_notes

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
TARGET_HOURS = list(range(2, 17))  # 2-16
BROKER_GMT = 0

# =====================================================================
# STATE PERSISTENCE - survive bot restarts
# =====================================================================
_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_state.json")

def _load_state():
    """Load persisted state from disk. Returns dict with day_signals, sent_today, etc."""
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

    # Only accept state from today
    today_str = datetime.now().date().isoformat()
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
    today_str = datetime.now().date().isoformat()
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

def get_entry_prices(pair_dirs, broker_dt, entry_time):
    """Lấy giá gần nhất trước entry time — M1@(entry-1) Close, gần giá thực."""
    prices = {}
    if not entry_time:
        return prices
    try:
        parts = entry_time.split(":")
        eh, em = int(parts[0]), int(parts[1])
        # Lùi 1 phút để lấy Close của nến trước
        prev_ts = broker_time_to_ts(broker_dt, eh, em) - 60
    except Exception:
        return prices
    for pair, direction in pair_dirs.items():
        if direction not in ("BUY", "SELL"):
            continue
        try:
            candle = get_candle_by_ts(pair, mt5.TIMEFRAME_M1, prev_ts)
            if candle:
                prices[pair] = round(candle["close"], 5)
            else:
                tick = mt5.symbol_info_tick(pair)
                if tick:
                    price = tick.ask if direction == "BUY" else tick.bid
                    prices[pair] = round(price, 5)
        except Exception:
            pass
    return prices

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
        except Exception:
            pass
    return prices

def log_signal(H, broker_dt, sig, entry_time, pair_dirs, hour_note, is_missed=False):
    """Append signal data to signals_log.json for website consumption."""
    entry_prices = get_entry_prices(pair_dirs, broker_dt, entry_time) if sig in ("BUY", "SELL") else {}
    current_prices = get_current_prices(pair_dirs) if sig in ("BUY", "SELL") else {}
    record = {
        "date": broker_dt.date().isoformat(),
        "hour": H,
        "ts": datetime.now().timestamp(),
        "signal": sig,
        "entry_time": entry_time,
        "pair_dirs": pair_dirs,
        "entry_prices": entry_prices,
        "current_prices": current_prices,
        "hour_note": hour_note,
        "missed": is_missed,
    }
    try:
        data = []
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8") as f:
                data = json.load(f)
        # Deduplicate: replace existing entry for same (date, hour)
        key = (record["date"], record["hour"])
        data = [d for d in data if (d["date"], d["hour"]) != key]
        data.append(record)
        data = data[-500:]
        with open(_SIGNALS_LOG, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Cannot log signal: {e}")

def _parse_news_for_dashboard(news_lines):
    """Parse news strings like '• 19:30 CAD 🔴 GDP m/m' into structured objects."""
    import re
    items = []
    for line in news_lines:
        line = line.lstrip("•- ").strip()
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
            items.append({"time": time_str, "currency": currency, "title": title.strip(), "impact": impact})
    return items

def push_to_dashboard():
    """Push data to dashboard API (best effort, non-blocking)."""
    dashboard_url = os.environ.get("DASHBOARD_API_URL", "") or DASHBOARD_URL
    if not dashboard_url:
        print("[DASHBOARD] No dashboard_url configured, skip push.")
        return
    print(f"[DASHBOARD] Pushing to {dashboard_url} ...")
    try:
        # Push signals
        if os.path.exists(_SIGNALS_LOG) and os.path.getsize(_SIGNALS_LOG) > 2:
            with open(_SIGNALS_LOG, "r", encoding="utf-8") as f:
                signals = json.load(f)
            if signals:
                payload = json.dumps(signals).encode("utf-8")
                req = urllib.request.Request(
                    f"{dashboard_url}/api/signals",
                    data=payload,
                    headers={"Content-Type": "application/json"}
                )
                resp = urllib.request.urlopen(req, timeout=15)
                resp.read()
                print(f"[DASHBOARD] Signals pushed OK ({len(signals)} items)")
        # Push state
        if os.path.exists(_STATE_FILE) and os.path.getsize(_STATE_FILE) > 2:
            with open(_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            if state:
                payload = json.dumps(state).encode("utf-8")
                req = urllib.request.Request(
                    f"{dashboard_url}/api/state",
                    data=payload,
                    headers={"Content-Type": "application/json"}
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
                    headers={"Content-Type": "application/json"}
                )
                resp = urllib.request.urlopen(req, timeout=15)
                resp.read()
                print(f"[DASHBOARD] News pushed OK ({len(parsed)} items)")
    except Exception as e:
        print(f"[DASHBOARD] Push error: {e}")

def push_prices_to_dashboard():
    """Push giá realtime cho các cặp đang có tín hiệu."""
    dashboard_url = os.environ.get("DASHBOARD_API_URL", "") or DASHBOARD_URL
    if not dashboard_url:
        return
    try:
        prices = {}
        for pair in ALL_PAIRS:
            try:
                tick = mt5.symbol_info_tick(pair)
                if tick:
                    prices[pair] = round(tick.bid, 5)
            except Exception:
                pass
        if prices:
            payload = json.dumps(prices).encode("utf-8")
            req = urllib.request.Request(
                f"{dashboard_url}/api/prices",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            resp = urllib.request.urlopen(req, timeout=10)
            resp.read()  # Đọc response để tránh leak
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
    today = datetime.now().date()
    if d_reminder_sent_date == today:
        return
    msg = (
        "📝 NHẬP DIRECTION CHO NGÀY HÔM NAY\n"
        "============================\n"
        "Gõ BUY hoặc SELL qua Telegram\n"
        "để set hướng Daily (D).\n\n"
        "Ví dụ: gõ 'BUY' hoặc 'SELL'\n"
        "============================\n"
        "D direction dùng để dừng báo\n"
        "XAUUSD khi H cùng chiều D."
    )
    send_telegram(msg)
    d_reminder_sent_date = today
    print("  [D-REMINDER] Sent daily reminder")

def check_d_direction_input():
    global d_direction, d_direction_date
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    id_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "d_dir_last_id.txt")
    last_id = 0
    try:
        if os.path.exists(id_file):
            with open(id_file, "r") as f:
                last_id = int(f.read().strip())
    except:
        pass
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id + 1}&timeout=1"
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.load(response)
            if not data.get("ok"):
                return
            for update in data.get("result", []):
                new_last_id = update["update_id"]
                msg_obj = update.get("message") or update.get("channel_post")
                if not msg_obj:
                    continue
                text = (msg_obj.get("text") or "").strip().upper()
                if text in ("BUY", "SELL", "MUA", "BAN"):
                    direction = "BUY" if text in ("BUY", "MUA") else "SELL"
                    set_d_direction(direction)
                    send_telegram(f"✅ Daily direction đã set: {direction}")
                    print(f"  [D-DIRECTION] Set to {direction}")
                last_id = new_last_id
            if last_id > 0:
                with open(id_file, "w") as f:
                    f.write(str(last_id))
    except Exception as e:
        pass

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

    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 200)
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
    if H < 2:
        return None
    ts_h1 = broker_time_to_ts(broker_dt, H - 1, 0, 0)
    c_h1 = get_candle_by_ts(SYMBOL, mt5.TIMEFRAME_H1, ts_h1)
    if c_h1 is None:
        print(f"  [H1] Không có dữ liệu H1 GBPUSD tại {H-1}:00")
        return None
    return c_h1

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

def calc_entry_time(signal, m30_dir, H=None, h2_signal=None, orig_signal=None):
    """Calculate entry time based on signal + M30 direction + whether signal matches H=2.
    orig_signal: signal từ M5+M30 TRƯỚC khi H1 check đảo chiều."""
    if signal not in ("BUY", "SELL") or m30_dir not in ("TANG", "GIAM"):
        return None
    # same_m30 dùng orig_signal (trước H1) để xác định entry time
    base = orig_signal if orig_signal else signal
    same_m30 = (base == "BUY" and m30_dir == "TANG") or (base == "SELL" and m30_dir == "GIAM")

    matches_h2 = (h2_signal is not None and signal == h2_signal)

    if matches_h2:
        return f"{H+1}:10" if same_m30 else f"{H}:49"
    else:
        return f"{H+1}:19" if same_m30 else f"{H+1}:24"

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

    # === H1 CHECK — tất cả slot ===
    orig_signal = signal  # giữ signal gốc trước H1
    h1_flipped = False
    h1_result = None  # chiều H1 GBPUSD = chiều XAUUSD
    c_h1 = get_h1_candle_for_slot(broker_dt, H)
    if c_h1 is not None:
        d_h1 = candle_direction(c_h1)
        # DOJI fallback: lùi 1 nến H1 trước
        if d_h1 == "DOJI":
            ts_h1 = broker_time_to_ts(broker_dt, H - 1, 0, 0)
            d_h1 = resolve_doji(SYMBOL, mt5.TIMEFRAME_H1, ts_h1, broker_dt)
            if d_h1 is None:
                d_h1 = "TANG"  # fallback cuối
            print(f"  [DOJI] H1@{H-1}:00 DOJI -> fallback: {d_h1}")
        if d_h1 and d_h1 != "DOJI":
            h1_signal = "BUY" if d_h1 == "TANG" else "SELL"
            h1_result = h1_signal
            vn_h1 = vn_direction(d_h1)
            if h1_signal == signal:
                signal = "SELL" if signal == "BUY" else "BUY"
                h1_flipped = True
                report += f"\n\n  *H1@{H-1}:00: {vn_h1}* (Cùng chiều M5+M30)\n  -> ĐẢO NGƯỢC: {signal}"
            else:
                report += f"\n\n  *H1@{H-1}:00: {vn_h1}* (Ngược chiều M5+M30)\n  -> GIỮ NGUYÊN: {signal}"

    return {"signal": signal, "orig_signal": orig_signal, "h1_signal": h1_result, "report": report, "m30_dir": d_m30, "h1_flipped": h1_flipped}

def get_hour_note(H):
    notes = {
        2: "GBPAUD, GBPJPY ngược Vàng. GBPUSD, GBPCAD nghỉ",
        3: "GBPAUD, GBPJPY ngược Vàng. GBPUSD, GBPCAD nghỉ",
        4: "Chỉ GBPAUD + Vàng",
        5: "Chỉ GBPAUD + Vàng",
        6: "Chỉ GBPAUD + Vàng",
        7: "Chỉ GBPAUD + Vàng",
        8: "Chỉ GBPAUD + Vàng",
        9: "Nhóm GBP ngược Vàng",
        10: "Chỉ Vàng",
        11: "Nhóm GBP ngược Vàng",
        12: "Chỉ Vàng",
        13: "Chỉ Vàng",
        14: "Chỉ Vàng",
        15: "GBPUSD, GBPJPY cùng Vàng",
        16: "GBPUSD, GBPJPY cùng Vàng",
    }
    return notes.get(H)

GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"]
ALL_PAIRS = GBP_PAIRS + ["XAUUSD"]

# Daily direction for XAUUSD (set via Telegram input)
d_direction = None  # 'BUY' or 'SELL'
d_direction_date = None  # date when set
d_matched_hour = None  # H where signal matched D (stops reporting after)

def set_d_direction(direction):
    global d_direction, d_direction_date, d_matched_hour
    d_direction = direction.upper() if direction else None
    d_direction_date = datetime.now().date() if d_direction else None
    d_matched_hour = None

def get_pair_direction(H, signal, broker_dt, h1_signal=None):
    """Tính chiều các cặp theo slot.
    signal: signal cuối cùng (sau H1 check) = chiều XAUUSD."""
    global d_direction, d_direction_date
    weekday = broker_dt.weekday()
    today = broker_dt.date()
    result = {}

    if d_direction_date != today:
        d_direction = None

    # WAIT = không có tín hiệu, trả về rỗng
    if signal not in ("BUY", "SELL"):
        return result

    # XAUUSD = signal cuối cùng (sau H1 check)
    gold = signal
    opposite = "SELL" if gold == "BUY" else "BUY"

    if H in (2, 3):
        result["XAUUSD"] = gold
        result["GBPAUD"] = opposite
        result["GBPJPY"] = opposite
        result["GBPUSD"] = "--"
        result["GBPCAD"] = "--"

    elif H in (4, 5, 6, 7, 8):
        result["XAUUSD"] = gold
        result["GBPAUD"] = opposite
        result["GBPUSD"] = "--"
        result["GBPJPY"] = "--"
        result["GBPCAD"] = "--"

    elif H in (9, 11):
        result["XAUUSD"] = gold
        for p in GBP_PAIRS:
            result[p] = opposite

    elif H in (10, 12, 13, 14):
        result["XAUUSD"] = gold
        for p in GBP_PAIRS:
            result[p] = "--"

    elif H in (15, 16):
        result["XAUUSD"] = gold
        result["GBPUSD"] = gold
        result["GBPJPY"] = gold
        result["GBPAUD"] = "--"
        result["GBPCAD"] = "--"

    return result

def should_skip_xauusd(H, signal, broker_dt):
    """Kiểm tra có nên ẩn XAUUSD không. Không mutated state."""
    if d_direction is None or broker_dt.weekday() not in (0, 3, 4):
        return False
    if H == 16:
        return False
    if d_matched_hour is not None:
        return True
    if signal == d_direction:
        return False  # First match: hiển thị, caller chịu trách nhiệm set d_matched_hour
    return False

def mark_xauusd_matched(H):
    """Ghi nhận slot đầu tiên XAUUSD khớp D1 direction."""
    global d_matched_hour
    if d_matched_hour is None:
        d_matched_hour = H

# =====================================================================
# GUI TELEGRAM BAO CAO
# =====================================================================
def send_report(signal_data, H, broker_dt, h2_signal=None):
    sig = signal_data["signal"]
    report = signal_data["report"]
    m30_dir = signal_data.get("m30_dir")
    icon, emoji = get_signal_icon(sig)

    entry_time = calc_entry_time(sig, m30_dir, H, h2_signal=h2_signal, orig_signal=signal_data.get("orig_signal"))

    hour_note = get_hour_note(H)
    note_line = f"📝 {hour_note}\n" if hour_note else ""

    pair_dirs = get_pair_direction(H, sig, broker_dt, h1_signal=signal_data.get("h1_signal"))

    if should_skip_xauusd(H, sig, broker_dt):
        pair_dirs.pop("XAUUSD", None)
    elif sig == d_direction and d_direction is not None:
        mark_xauusd_matched(H)  # Ghi nhận lần đầu khớp D1

    pair_lines = []
    for p in ALL_PAIRS:
        if p == "XAUUSD":
            continue  # XAUUSD đã hiển thị ở KẾT LUẬN
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

    entry_line = f"Vào lệnh: *{entry_time}*\n" if entry_time else ""

    # KẾT LUẬN: hiển thị signal cuối cùng (sau H1 check) = chiều XAUUSD
    conclusion = f"KẾT LUẬN: XAUUSD:{icon} {sig}\n"

    msg = (
        f"{emoji} Tín hiệu {SYMBOL} - {icon}\n"
        f"============================\n"
        f"  {fmt_hour(H)}:45 (Broker)\n"
        f"============================\n\n"
        f"{report}\n\n"
        f"============================\n"
        f"{conclusion}"
        f"{entry_line}"
        f"-------------------\n"
        f"{pair_text}\n"
        f"-------------------\n"
        f"{note_line}"
        f"============================\n"
        f"Chỉ tham khảo. Kỷ luật là sức mạnh!"
    )
    send_telegram(msg)

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

def main():
    global mt5_ready, d_direction, d_direction_date, d_matched_hour
    print("=" * 55)
    print("  MT5 Multi-Timeframe Signal Bot v3.6.0")
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
    push_to_dashboard()

    if mt5_ready:
        broker_dt = get_broker_time()
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

        missed_count = 0
        latest_missed = None
        # Xử lý H=2 trước để có h2_sig cho các slot khác
        if 2 in passed:
            key_h2 = (broker_dt.date(), 2)
            if key_h2 not in sent_today:
                r2 = analyze(broker_dt, 2)
                s2 = r2["signal"]
                if s2 in ("BUY", "SELL"):
                    day_signals[(broker_dt.date(), 2)] = {"signal": s2, "m30_dir": r2.get("m30_dir")}
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

            h2_data = day_signals.get((broker_dt.date(), 2))
            h2_sig = h2_data["signal"] if h2_data else None

            entry_time = calc_entry_time(sig, result.get("m30_dir"), h, h2_signal=h2_sig, orig_signal=result.get("orig_signal"))
            pair_dirs = get_pair_direction(h, sig, broker_dt, h1_signal=result.get("h1_signal"))
            if should_skip_xauusd(h, sig, broker_dt):
                pair_dirs.pop("XAUUSD", None)
            elif sig == d_direction and d_direction is not None:
                mark_xauusd_matched(h)
            hour_note = get_hour_note(h)

            log_signal(h, broker_dt, sig, entry_time, pair_dirs, hour_note, is_missed=True)
            sent_today.add(key)
            _save_state(day_signals, sent_today)
            missed_count += 1

            # Chi lay slot gan nhat (dau tien vi passed sort reverse)
            if latest_missed is None:
                latest_missed = {"h": h, "sig": sig, "icon": icon, "result": result,
                                 "entry_time": entry_time, "pair_dirs": pair_dirs, "hour_note": hour_note,
                                 "h2_sig": h2_sig}

        # Chi gui Telegram slot gan nhat
        if latest_missed:
            h = latest_missed["h"]
            sig = latest_missed["sig"]
            icon = latest_missed["icon"]
            result = latest_missed["result"]
            entry_time = latest_missed["entry_time"]
            pair_dirs = latest_missed["pair_dirs"]
            hour_note = latest_missed["hour_note"]
            h2_sig = latest_missed["h2_sig"]

            slot_line = f"Slot tiếp theo: {fmt_hour(next_slots[0])}:45 (còn {countdown})\n" if next_slots else f"Hết slot hôm nay.\n"
            entry_line = f"Vào lệnh: *{entry_time}*\n" if entry_time else ""

            pair_lines = []
            for p in ALL_PAIRS:
                if p == "XAUUSD":
                    continue  # XAUUSD đã hiển thị ở KẾT LUẬN
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

            conclusion = f"KẾT LUẬN: XAUUSD:{icon} {sig}\n"

            msg = (
                f"*KIỂM TRA BỎ LỠ {fmt_hour(h)}:45*\n"
                f"============================\n\n"
                f"{result['report']}\n\n"
                f"============================\n"
                f"{conclusion}"
                f"{entry_line}"
                f"-------------------\n"
                f"{pair_text}\n"
                f"-------------------\n"
                f"{note_line}"
                f"============================\n"
                f"{slot_line}"
                f"Bỏ lỡ do bot khởi động sau. Chỉ tham khảo!"
            )
            send_telegram(msg)

        if missed_count > 0:
            push_to_dashboard()
            print(f"\n[DASHBOARD] Pushed {missed_count} missed slots")

    try:
        while True:
            if not mt5_ready:
                try_init_mt5()

            broker_dt = get_broker_time()
            now_min = broker_dt.minute
            now_hour = broker_dt.hour

            check_d_direction_input()

            if broker_dt.hour == 6 and broker_dt.minute == 0 and broker_dt.weekday() in (0, 3, 4):
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

                # Track H=2 signal for entry time calculation
                if now_hour == 2 and sig in ("BUY", "SELL"):
                    day_signals[(broker_dt.date(), 2)] = {"signal": sig, "m30_dir": result.get("m30_dir")}
                    _save_state(day_signals, sent_today)

                h2_data = day_signals.get((broker_dt.date(), 2))
                h2_sig = h2_data["signal"] if h2_data else None

                pair_dirs = send_report(result, now_hour, broker_dt, h2_signal=h2_sig)

                # Log for website
                entry_time = calc_entry_time(sig, result.get("m30_dir"), now_hour, h2_signal=h2_sig, orig_signal=result.get("orig_signal"))
                log_signal(now_hour, broker_dt, sig, entry_time, pair_dirs, get_hour_note(now_hour))
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
    main()
