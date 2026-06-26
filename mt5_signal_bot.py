# -*- coding: utf-8 -*-
"""
MT5 Multi-Timeframe Signal Bot v3.0
====================================
Tinh gio hoan toan tu tick.time cua MT5 (UTC timestamp).
Khong phu thuoc vao gio local may tinh/VPS.
"""
import os
import sys
import json
import time
import calendar
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

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
except Exception:
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHAT_ID = ""
    print("[WARN] config.json not found or invalid.")

SYMBOL = "GBPUSD"
TARGET_HOURS = list(range(1, 17))
MT5_PATH = r"C:\Program Files\MetaTrader 5 IC Markets Global\terminal64.exe"
BROKER_GMT = 0

# Mo ta chi tiet theo thứ trong tuần (0=Thứ 2 ... 4=Thứ 6)
SCHEDULE_NOTES = {
    0: "Thứ 2: Vàng SW nhẹ",
    1: "Thứ 3: Bình thường",
    2: "Thứ 4: GBP SW rộng theo Vàng + tính lại W1",
    3: "Thứ 5: Theo W1, phiên AU dời 9h broker time",
    4: "Thứ 6: SW/W1, tính lại nếu cuối tháng",
}

def get_schedule_note(broker_dt):
    wd = broker_dt.weekday()
    return SCHEDULE_NOTES.get(wd, "Ngoài giờ giao dịch")

# =====================================================================
# TELEGRAM
# =====================================================================
def send_telegram(text):
    try:
        clean = text.replace("*", "").replace("_", "")
        msg = urllib.parse.quote(clean)
        url = (
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
            f"/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={msg}"
        )
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.read()
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

    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1000)
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

def candle_info_line(candle, label):
    if candle is None:
        return f"  {label}: Khong co du lieu"
    d = candle_direction(candle)
    arrow = {"TANG": "\u2191", "GIAM": "\u2193", "DOJI": "\u2194"}.get(d, "")
    vn = {"TANG": "Tăng", "GIAM": "Giảm", "DOJI": "Doji"}.get(d, "?")
    return (
        f"  {label}: {vn} {arrow}\n"
        f"    O={candle['open']:.5f} C={candle['close']:.5f} "
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
        return {"signal": "WAIT", "report": "Khong du du lieu M5"}
    if d_m35 == "DOJI":
        print(f"  [SKIP] M5@{fmt_hour(H)}:35 la DOJI")
        return {"signal": "WAIT", "report": "M5@35 la DOJI - Khong du dieu kien"}
    if d_m40 == "DOJI":
        print(f"  [SKIP] M5@{fmt_hour(H)}:40 la DOJI")
        return {"signal": "WAIT", "report": "M5@40 la DOJI - Khong du dieu kien"}

    ts_m30 = broker_time_to_ts(broker_dt, H, 30)
    c_m30 = get_candle_by_ts(SYMBOL, mt5.TIMEFRAME_M30, ts_m30)
    d_m30 = candle_direction(c_m30)

    if d_m30 is None:
        return {"signal": "WAIT", "report": "Khong du du lieu M30"}
    if d_m30 == "DOJI":
        return {"signal": "WAIT", "report": "M30@30 la DOJI - Khong du dieu kien"}

    vn_m35 = {"TANG": "Tăng", "GIAM": "Giảm"}.get(d_m35, d_m35)
    vn_m40 = {"TANG": "Tăng", "GIAM": "Giảm"}.get(d_m40, d_m40)
    vn_m30 = {"TANG": "Tăng", "GIAM": "Giảm"}.get(d_m30, d_m30)

    if d_m35 == d_m40:
        signal = "BUY" if d_m30 == "TANG" else "SELL"
        report = (
            f"PATTERN: Cung chieu ({vn_m35})\n"
            f"{candle_info_line(c_m35, f'M5@{fmt_hour(H)}:35')}\n"
            f"{candle_info_line(c_m40, f'M5@{fmt_hour(H)}:40')}\n"
            f"  -> Lay M30@{fmt_hour(H)}:30 (Cung chieu)\n"
            f"{candle_info_line(c_m30, f'M30@{fmt_hour(H)}:30')}"
        )
    else:
        signal = "SELL" if d_m30 == "TANG" else "BUY"
        report = (
            f"PATTERN: Nguoc chieu ({vn_m35} + {vn_m40})\n"
            f"{candle_info_line(c_m35, f'M5@{fmt_hour(H)}:35')}\n"
            f"{candle_info_line(c_m40, f'M5@{fmt_hour(H)}:40')}\n"
            f"  -> Lay M30@{fmt_hour(H)}:30 (Nguoc chieu)\n"
            f"{candle_info_line(c_m30, f'M30@{fmt_hour(H)}:30')}"
        )

    return {"signal": signal, "report": report}

# =====================================================================
# GUI TELEGRAM BAO CAO
# =====================================================================
def send_report(signal_data, H, broker_dt):
    sig = signal_data["signal"]
    report = signal_data["report"]

    if sig == "BUY":
        icon = "Mua"
        emoji = "\U0001f7e2"
    elif sig == "SELL":
        icon = "Bán"
        emoji = "\U0001f534"
    else:
        icon = "Chờ"
        emoji = "\u26aa"

    note = get_schedule_note(broker_dt)
    msg = (
        f"{emoji} Tín hiệu {SYMBOL} - {icon}\n"
        f"============================\n"
        f"  {fmt_time(broker_dt)} (Broker)\n"
        f"  Kích hoạt: {fmt_hour(H)}:45\n"
        f"  Tập trung: {note}\n"
        f"============================\n\n"
        f"{report}\n\n"
        f"============================\n"
        f"KẾT LUẬN: {icon}\n"
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
    global mt5_ready
    print("=" * 55)
    print("  MT5 Multi-Timeframe Signal Bot v3.1")
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

    sent_today = set()

    from datetime import datetime as _dt
    today_note = get_schedule_note(_dt.now(timezone.utc))
    send_telegram(
        f"BOT KHOI DONG\n"
        f"Symbol: {SYMBOL} | MT5: {'OK' if mt5_ready else 'N/A'}\n"
        f"Kich hoat: {fmt_hour(TARGET_HOURS[0])}-{fmt_hour(TARGET_HOURS[-1])}:45\n"
        f"Hom nay: {today_note}"
    )

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
                mins_left = (next_h - now_h) * 60 + (50 - now_m)
            if mins_left <= 0:
                mins_left += 24 * 60
            hours_left = mins_left // 60
            mins_remain = mins_left % 60
            countdown = f"{hours_left}h{mins_remain:02d}m" if hours_left > 0 else f"{mins_remain}m"
        else:
            countdown = "ngay mai"

        if passed:
            latest = passed[0]
            key = (broker_dt.date(), latest)
            print(f"\n[KIEM TRA BO LO] {fmt_hour(latest)}:45")
            result = analyze(broker_dt, latest)
            sig = result["signal"]

            if sig == "BUY":
                icon, emoji = "Mua", "\U0001f7e2"
            elif sig == "SELL":
                icon, emoji = "Bán", "\U0001f534"
            else:
                icon, emoji = "Chờ", "\u26aa"

            note = get_schedule_note(broker_dt)
            slot_line = f"Slot tiep theo: {fmt_hour(next_slots[0])}:45 (con {countdown})\n" if next_slots else f"Het slot hom nay.\n"
            msg = (
                f"{emoji} [Bo lo] {fmt_hour(latest)}:45 - {icon}\n"
                f"============================\n"
                f"  {fmt_time(broker_dt)} (Broker)\n"
                f"  Tập trung: {note}\n"
                f"============================\n\n"
                f"{result['report']}\n\n"
                f"============================\n"
                f"KẾT LUẬN: {icon}\n"
                f"============================\n"
                f"{slot_line}"
                f"Bỏ lỡ do bot khởi động sau. Chỉ tham khảo!"
            )
            send_telegram(msg)
            sent_today.add(key)
            print(f"  Signal: {sig} - Sent: OK")

    try:
        while True:
            if not mt5_ready:
                try_init_mt5()

            broker_dt = get_broker_time()
            now_min = broker_dt.minute
            now_hour = broker_dt.hour

            # --- TIN HIEU CHINH: x:45 ---
            if now_min == 45 and now_hour in TARGET_HOURS:
                key = (broker_dt.date(), now_hour)
                if key in sent_today:
                    time.sleep(10)
                    continue

                print(f"\n[{fmt_time(broker_dt)}] Kich hoat {fmt_hour(now_hour)}:45")

                result = analyze(broker_dt, now_hour)
                sig = result["signal"]

                send_report(result, now_hour, broker_dt)

                print(f"  Signal: {sig}")
                print(f"  Sent: OK")

                sent_today.add(key)
                old = [k for k in sent_today if k[0] == broker_dt.date() and k[1] != now_hour]
                for k in old:
                    sent_today.discard(k)

                time.sleep(60)
            else:
                if now_min < 45:
                    wait = (45 - now_min) * 60 - broker_dt.second
                else:
                    wait = (60 - now_min + 45) * 60 - broker_dt.second
                wait = min(wait, 300)
                if wait > 0:
                    time.sleep(wait)

    except KeyboardInterrupt:
        print("\n  Dung bot.")
    except Exception as e:
        print(f"\n  Loi: {e}")
    finally:
        if mt5_ready:
            mt5.shutdown()
        print("  Bot stopped.")

if __name__ == "__main__":
    main()
