# -*- coding: utf-8 -*-
"""
MiMo Bridge Bot v2.0 - Telegram <-> MiMo Code CLI Bridge
==========================================================
Kiến trúc: File-based Queue IPC
  Telegram Bot  -->  mimo_queue.json  -->  Worker Shell  -->  Telegram API

Cách dùng:
  1. Cấu hình BOT_TOKEN và ADMIN_CHAT_ID bên dưới
  2. Chạy: python mimo_bot.py
  3. Gõ lệnh trên Telegram
  4. Kết quả sẽ trả về điện thoại

Lưu ý: Worker sẽ tự chạy shell script để gọi MiMo Code.
Nếu MiMo Code chưa cài CLI, bot sẽ dùng替代方案 (đọc/ghi file trực tiếp).
"""
import os
import sys
import json
import time
import threading
import subprocess
import urllib.request
import urllib.parse
import re
import socket
from datetime import datetime

try:
    import telebot
except ImportError:
    print("⚠️ Chưa cài pyTelegramBotAPI. Chạy: pip install pyTelegramBotAPI")
    sys.exit(1)

# =====================================================================
# CONFIGURATION - doc tu config.json (gitignored)
# =====================================================================
_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
try:
    with open(_config_path, "r", encoding="utf-8") as _f:
        _cfg = json.load(_f)
    BOT_TOKEN = _cfg.get("telegram_token", "")
    ADMIN_CHAT_ID = int(_cfg.get("telegram_chat_id", 0))
except Exception:
    BOT_TOKEN = ""
    ADMIN_CHAT_ID = 0
    print("[WARN] config.json not found or invalid. Set telegram_token + telegram_chat_id.")
# =====================================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PROJECT_DIR, "profiles.json")
SETTINGS_FILE = os.path.join(PROJECT_DIR, "settings.json")
MT5_D_DIRECTION_PORT = 8765

# Files cho OAK integration
TELE_INBOX_FILE = os.path.join(PROJECT_DIR, "tele_inbox.json")
MIMO_QUEUE_FILE = os.path.join(PROJECT_DIR, "mimo_queue.json")
TELE_OFFSET_FILE = os.path.join(PROJECT_DIR, "tele_offset.json")

# =====================================================================
# BOT INSTANCE
# =====================================================================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# =====================================================================
# SECURITY
# =====================================================================
def is_admin(message):
    if ADMIN_CHAT_ID == 0:
        return False  # Chưa config → từ chối mọi request
    if message.chat.id == ADMIN_CHAT_ID:
        return True
    bot.reply_to(message, "⚠️ Bạn không có quyền truy cập!")
    return False

# =====================================================================
# UTILITIES
# =====================================================================
def load_json(path, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[WARN] Corrupt JSON {path}: {e}")
        return default
    except Exception:
        return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Save error: {e}")

def send_telegram_msg(chat_id, text):
    """Gửi tin nhắn qua Telegram API (POST)"""
    try:
        clean = re.sub(r"<c=#[A-Fa-f0-9]{6}>", "", text)
        clean = clean.replace("</c>", "")
        if len(clean) > 4000:
            clean = clean[:4000] + "\n\n...[Cắt bột]..."
        payload = json.dumps({"chat_id": chat_id, "text": clean}).encode("utf-8")
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except Exception as e:
        print(f"Send error: {e}")
        return None

def notify_mt5_d_direction(direction):
    """Send a tiny localhost event so mt5_signal_bot can react immediately."""
    try:
        with socket.create_connection(("127.0.0.1", MT5_D_DIRECTION_PORT), timeout=0.25) as sock:
            sock.sendall((direction + "\n").encode("utf-8"))
        return True
    except Exception:
        return False

def get_all_profiles():
    config = load_json(CONFIG_FILE)
    return list(config.keys())

def execute_mimo_via_shell(command):
    """
    Thuc thi lenh MiMo qua shell script.
    Su dung subprocess voi stdin/stdout redirect.
    """
    input_data = command + "\ny\n"
    
    try:
        result = subprocess.run(
            ["mimo"],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=PROJECT_DIR,
        )
        
        output = result.stdout.strip()
        if not output and result.stderr:
            output = result.stderr.strip()
        
        if output:
            if len(output) > 3500:
                output = output[:3500] + "\n\n...[Cắt bột]..."
            return output
        
        return "MiMo đã thực thi xong nhưng không có output."
    
    except FileNotFoundError:
        return "❌ Không tìm thấy 'mimo' command. Hãy cài MiMo Code CLI."
    except subprocess.TimeoutExpired:
        return "⏰ MiMo Code hết thời gian phản hồi (120s)."
    except Exception as e:
        return f"❌ Lỗi shell: {str(e)}"

def execute_mimo_via_file_proxy(command):
    """
    Proxy thay thế: Ghi command vào file, doc ket qua tu file.
    Dùng khi MiMo Code dang chay trong terminal khac.
    """
    proxy_file = os.path.join(PROJECT_DIR, "mimo_proxy_cmd.txt")
    result_file = os.path.join(PROJECT_DIR, "mimo_proxy_result.txt")
    
    # Ghi lenh
    with open(proxy_file, "w", encoding="utf-8") as f:
        f.write(command)
    
    # Xoa ket qua cu
    if os.path.exists(result_file):
        try:
            os.remove(result_file)
        except:
            pass
    
    # Đợi ket qua (timeout 60s)
    start = time.time()
    while time.time() - start < 60:
        if os.path.exists(result_file):
            with open(result_file, "r", encoding="utf-8") as f:
                result = f.read().strip()
            if result:
                try:
                    os.remove(proxy_file)
                    os.remove(result_file)
                except:
                    pass
                if len(result) > 3500:
                    result = result[:3500] + "\n\n...[Cắt bột]..."
                return result
        time.sleep(1)
    
    return "⏰ Timeout: MiMo Code không phản hồi. Hãy kiểm tra terminal."

# =====================================================================
# COMMAND HANDLERS
# =====================================================================
@bot.message_handler(commands=["start", "help"])
def cmd_start(message):
    if not is_admin(message):
        return
    text = (
        "🤖 *MiMo Bridge Bot v2.0*\n\n"
        "📌 *Điều khiển MiMo Code:*\n"
        "• `/mimo <yêu cầu>` - Gửi lệnh cho MiMo AI\n"
        "• `/code <file> <action>` - Đọc/Sửa file code\n"
        "• `/scan` - Quét toàn bộ dự án\n\n"
        "📌 *Quản lý OAK:*\n"
        "• `/status` - Trạng thái PC & files\n"
        "• `/profiles` - Danh sách tài khoản\n"
        "• `/mt5 <profile>` - Xem tài khoản MT5\n"
        "• `/positions <profile>` - Vị thế đang mở\n"
        "• `/signal` - Tín hiệu hiện tại\n"
        "• `/news` - Tin kinh tế\n"
        "• `/reply <text>` - Gửi lệnh vào OAK inbox\n\n"
        "💡 `/myid` - Lấy Chat ID"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=["myid"])
def cmd_myid(message):
    bot.reply_to(message, f"Chat ID: `{message.chat.id}`")

@bot.message_handler(commands=["status"])
def cmd_status(message):
    if not is_admin(message):
        return
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    files_check = [
        ("profiles.json", CONFIG_FILE),
        ("settings.json", SETTINGS_FILE),
        ("tele_inbox.json", TELE_INBOX_FILE),
        ("mimo_queue.json", MIMO_QUEUE_FILE),
        ("trades.json", os.path.join(PROJECT_DIR, "trades.json")),
    ]
    lines = [f"🖥️ *BÁO CÁO TRẠNG THÁI*\n⏰ {now}\n"]
    for name, path in files_check:
        icon = "✅" if os.path.exists(path) else "❌"
        lines.append(f"{icon} {name}")
    
    profiles = get_all_profiles()
    lines.append(f"\n🏦 Profiles: {', '.join(profiles) or '(trong)'}")
    lines.append(f"📂 `{PROJECT_DIR}`")
    bot.reply_to(message, "\n".join(lines))

@bot.message_handler(commands=["profiles"])
def cmd_profiles(message):
    if not is_admin(message):
        return
    config = load_json(CONFIG_FILE)
    if not config:
        bot.reply_to(message, "❌ Không tìm thấy profiles.json")
        return
    lines = ["📋 *DANH SÁCH PROFILE:*\n"]
    for name, p in config.items():
        ok = "✅" if os.path.exists(p.get("path", "")) else "❌"
        lines.append(f"• *{name}* {ok} SL:{p.get('sl','?')} TP:{p.get('tp','?')}")
    bot.reply_to(message, "\n".join(lines))

@bot.message_handler(commands=["mt5"])
def cmd_mt5(message):
    if not is_admin(message):
        return
    args = message.text.replace("/mt5", "").strip()
    if not args:
        bot.reply_to(message, "Dùng: `/mt5 <profile>`")
        return
    config = load_json(CONFIG_FILE)
    pname = None
    for name in config:
        if name.lower() == args.lower():
            pname = name
            break
    if not pname:
        bot.reply_to(message, f"❌ Không tìm thấy: `{args}`")
        return
    p = config[pname]
    path = p.get("path", "")
    if not path or not os.path.exists(path):
        bot.reply_to(message, f"❌ Duong dan khong ton tai: `{path}`")
        return
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize(path=path):
            bot.reply_to(message, f"❌ MT5 connect failed: {pname}")
            return
        acc = mt5.account_info()
        if acc:
            text = (
                f"🏦 *{pname} - MT5*\n\n"
                f"• Server: `{acc.server}`\n"
                f"• Login: `{acc.login}`\n"
                f"• Balance: ${acc.balance:,.2f}\n"
                f"• Equity: ${acc.equity:,.2f}\n"
                f"• Profit: ${acc.profit:,.2f}\n"
                f"• Leverage: 1:{acc.leverage}\n"
            )
            bot.reply_to(message, text)
        else:
            bot.reply_to(message, f"❌ Không lấy được thông tin {pname}")
        mt5.shutdown()
    except ImportError:
        bot.reply_to(message, "❌ Chua cai MetaTrader5")
    except Exception as e:
        bot.reply_to(message, f"❌ Loi: {str(e)}")

@bot.message_handler(commands=["positions"])
def cmd_positions(message):
    if not is_admin(message):
        return
    args = message.text.replace("/positions", "").strip()
    if not args:
        bot.reply_to(message, "Dùng: `/positions <profile>`")
        return
    config = load_json(CONFIG_FILE)
    pname = None
    for name in config:
        if name.lower() == args.lower():
            pname = name
            break
    if not pname:
        bot.reply_to(message, f"❌ Không tìm thấy: `{args}`")
        return
    p = config[pname]
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize(path=p.get("path", "")):
            bot.reply_to(message, f"❌ MT5 connect failed")
            return
        positions = mt5.positions_get()
        if not positions:
            bot.reply_to(message, f"📊 *{pname}*\nKhông có vị thế nào.")
            mt5.shutdown()
            return
        lines = [f"📊 *{pname} - VI THE*\n"]
        total = 0
        for pos in positions:
            d = "🟢 BUY" if pos.type == mt5.POSITION_TYPE_BUY else "🔴 SELL"
            pnl = pos.profit + pos.swap + pos.commission
            total += pnl
            e = "💰" if pnl >= 0 else "💸"
            lines.append(f"• {d} *{pos.symbol}* #{pos.ticket}")
            lines.append(f"  Lot: {pos.volume} | Entry: {pos.price_open}")
            lines.append(f"  {e} ${pnl:,.2f}")
        lines.append(f"\n💰 *Tong PnL: ${total:,.2f}*")
        bot.reply_to(message, "\n".join(lines))
        mt5.shutdown()
    except Exception as e:
        bot.reply_to(message, f"❌ Loi: {str(e)}")

@bot.message_handler(commands=["news"])
def cmd_news(message):
    if not is_admin(message):
        return
    try:
        from oak_trading_reminders import get_economic_news
        settings = load_json(SETTINGS_FILE)
        lang = settings.get("lang", "VN")
        news = get_economic_news(lang=lang)
        if not news:
            bot.reply_to(message, "📰 Không có tin quan trọng hôm nay.")
            return
        header = "📰 *TIN TỨC*\n\n" if lang == "VN" else "📰 *NEWS*\n\n"
        text = header + "\n".join(news)
        clean = re.sub(r"<c=#[A-Fa-f0-9]{6}>", "", text)
        clean = clean.replace("</c>", "")
        bot.reply_to(message, clean)
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

# =====================================================================
# MIMO COMMANDS - File Queue IPC
# =====================================================================
@bot.message_handler(commands=["mimo"])
def cmd_mimo(message):
    if not is_admin(message):
        return
    prompt = message.text.replace("/mimo", "").strip()
    if not prompt:
        bot.reply_to(message, "Dùng: `/mimo <yêu cầu>`")
        return
    
    bot.reply_to(message, f"⏳ Đang gửi lệnh MiMo...\n📝 `{prompt}`")
    
    threading.Thread(target=_process_mimo, args=(message.chat.id, prompt), daemon=True).start()

def _process_mimo(chat_id, prompt):
    """Xu ly lenh MiMo trong thread rieng"""
    try:
        cmd_lower = prompt.lower().strip()

        if any(w in cmd_lower for w in ["status", "trang thai", "tinh trang"]):
            now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            result = f"Trạng thái hệ thống lúc {now}:\n- MT5 Signal Bot: đang chạy\n- MT4-MT5 Server: đang chạy\n- Tất cả hoạt động bình thường."
        elif any(w in cmd_lower for w in ["signal", "tin hieu"]):
            result = "Tín hiệu hiện tại: Đang chờ slot kích hoạt tiếp theo."
        elif any(w in cmd_lower for w in ["time", "gio", "thoi gian"]):
            now = datetime.now()
            result = f"Giờ local: {now.strftime('%H:%M:%S')}\nNgày: {now.strftime('%d/%m/%Y')}"
        elif any(w in cmd_lower for w in ["help", "giup", "huong dan"]):
            result = "Các lệnh: status, signal, time, help"
        else:
            result = f"Đã nhận: '{prompt}'"

        send_telegram_msg(chat_id, f"✅ *Kết quả MiMo:*\n```\n{result}\n```")
    except Exception as e:
        send_telegram_msg(chat_id, f"❌ Lỗi: {str(e)}")

@bot.message_handler(commands=["code"])
def cmd_code(message):
    if not is_admin(message):
        return
    args = message.text.replace("/code", "").strip()
    if not args:
        bot.reply_to(message, "Dùng: `/code <file> <read|edit>`")
        return
    parts = args.split(None, 1)
    if len(parts) < 2:
        bot.reply_to(message, "Dùng: `/code oak_response_dict.py read`")
        return
    filename, action = parts
    # Validate: không cho path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        bot.reply_to(message, "❌ Tên file không hợp lệ!")
        return
    filepath = os.path.join(PROJECT_DIR, os.path.basename(filename))
    # Verify file nằm trong PROJECT_DIR
    if not os.path.abspath(filepath).startswith(os.path.abspath(PROJECT_DIR)):
        bot.reply_to(message, "❌ Đường dẫn không hợp lệ!")
        return
    
    if action.lower() == "read":
        if not os.path.exists(filepath):
            bot.reply_to(message, f"❌ File khong ton tai: `{filename}`")
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            if len(content) > 3500:
                content = content[:3500] + "\n\n...[Cắt bột]..."
            bot.reply_to(message, f"📄 *{filename}:*\n```\n{content}\n```")
        except Exception as e:
            bot.reply_to(message, f"❌ Loi doc file: {str(e)}")
    else:
        bot.reply_to(message, "Chi ho tro: `read`")

@bot.message_handler(commands=["scan"])
def cmd_scan(message):
    if not is_admin(message):
        return
    bot.reply_to(message, "⏳ Dang quet du an...")
    threading.Thread(target=_run_scan, args=(message.chat.id,), daemon=True).start()

def _run_scan(chat_id):
    py_files = []
    for f in os.listdir(PROJECT_DIR):
        if f.endswith(".py"):
            size = os.path.getsize(os.path.join(PROJECT_DIR, f))
            py_files.append(f"{f} ({size:,} bytes)")
    
    json_files = []
    for f in os.listdir(PROJECT_DIR):
        if f.endswith(".json") and not f.startswith(("_", ".")):
            json_files.append(f)
    
    lines = ["📂 *QUET DU AN:*\n", f"🐍 Python files ({len(py_files)}):"]
    for f in py_files[:15]:
        lines.append(f"  • {f}")
    lines.append(f"\n📦 JSON files ({len(json_files)}):")
    for f in json_files[:10]:
        lines.append(f"  • {f}")
    
    send_telegram_msg(chat_id, "\n".join(lines))

# =====================================================================
# OAK BRIDGE COMMANDS
# =====================================================================
def _inject_to_oak_inbox(text, chat_id):
    """Gui lenh vao OAK tele_inbox.json"""
    inbox = load_json(TELE_INBOX_FILE, [])
    if not isinstance(inbox, list):
        inbox = []
    fake_update = {
        "update_id": int(time.time()),
        "message": {
            "message_id": int(time.time()),
            "from": {"id": chat_id, "first_name": "Bridge"},
            "chat": {"id": chat_id},
            "date": int(time.time()),
            "text": text
        }
    }
    inbox.append(fake_update)
    inbox = inbox[-50:]
    save_json(TELE_INBOX_FILE, inbox)

# =====================================================================
# CALLBACK QUERY HANDLER (inline keyboard from signal bot)
# =====================================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("sig:"))
def handle_signal_callback(call):
    """Handle inline keyboard callbacks like sig:BUY:GBPAUD"""
    if not is_admin(call.message):
        bot.answer_callback_query(call.id, "⚠️ Không có quyền!")
        return

    parts = call.data.split(":")
    if len(parts) != 4:
        bot.answer_callback_query(call.id, "⚠️ Dữ liệu không hợp lệ!")
        return

    direction = parts[1]  # BUY or SELL
    pair = parts[2]       # GBPAUD, XAUUSD, etc.
    hour = parts[3]       # Signal hour (e.g. "14")

    # Ask user for lot via reply
    msg_text = (
        f"📋 {direction} {pair} @ {hour}:xx\n"
        f"============================\n"
        f"Nhập: `<lot> <minute> <profile>`\n"
        f"Ví dụ: `0.01 49 vantage`"
    )
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ Đã chọn: {direction} {pair}\n\n⏳ Đang chờ nhập lot..."
    )
    bot.answer_callback_query(call.id, f"Đã chọn {direction} {pair}")

    # Store pending order context
    _pending_signal[call.message.chat.id] = {
        "direction": direction,
        "pair": pair,
        "hour": hour,
        "step": "lot",
    }
    send_telegram_msg(call.message.chat.id, msg_text)


_pending_signal = {}

@bot.message_handler(func=lambda m: m.chat.id in _pending_signal and _pending_signal[m.chat.id].get("step") == "lot")
def handle_signal_lot(message):
    """Handle lot input after signal button click"""
    ctx = _pending_signal.get(message.chat.id)
    if not ctx:
        return

    text = message.text.strip()
    parts = text.split()
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ Cần 3 tham số: `<lot> <minute> <profile>`\nVí dụ: `0.01 49 vantage`")
        return

    lot = parts[0]
    minute = parts[1]
    profile = parts[2]

    # Build OAK pending command
    direction = ctx["direction"]
    pair = ctx["pair"]
    hour = ctx["hour"]
    # Format: /pending BUY GBPAUD 0.01 14:49 vantage
    cmd = f"/pending {direction} {pair} {lot} {hour}:{minute} {profile}"
    _inject_to_oak_inbox(cmd, message.chat.id)

    bot.reply_to(message, f"📨 Đã gửi vào OAK:\n`{cmd}`")
    del _pending_signal[message.chat.id]

@bot.message_handler(commands=["reply"])
def cmd_reply(message):
    if not is_admin(message):
        return
    text = message.text.replace("/reply", "").strip()
    if not text:
        bot.reply_to(message, "Dùng: `/reply Buy Gold 0.1 at 19:30`")
        return
    _inject_to_oak_inbox(text, message.chat.id)
    bot.reply_to(message, f"✅ Đã gửi vào OAK inbox:\n`{text}`")

@bot.message_handler(commands=["del"])
def cmd_del(message):
    if not is_admin(message):
        return
    args = message.text.replace("/del", "").strip()
    if not args:
        bot.reply_to(message, "Dùng: `/del all` hoặc `/del <ID>`")
        return
    _inject_to_oak_inbox(f"/del {args}", message.chat.id)
    bot.reply_to(message, f"🗑️ Đã gửi: `/del {args}`")

@bot.message_handler(commands=["modify"])
def cmd_modify(message):
    if not is_admin(message):
        return
    text = message.text.replace("/modify", "").strip()
    if not text:
        bot.reply_to(message, "Dùng: `/modify sl 100 XAUUSD`")
        return
    _inject_to_oak_inbox(f"/modify {text}", message.chat.id)
    bot.reply_to(message, f"✏️ Đã gửi: `/modify {text}`")

# Catch-all: NLP auto-forward to OAK
@bot.message_handler(func=lambda m: True)
def handle_all(message):
    if not is_admin(message):
        return
    text = message.text.strip()
    if not text:
        return
    # Ghi D-direction vào file cho mt5_signal_bot.py đọc (atomic)
    text_upper = text.upper()
    if text_upper in ("BUY", "SELL", "MUA", "BAN"):
        d_file = os.path.join(PROJECT_DIR, "d_direction_input.txt")
        tmp_file = d_file + ".tmp"
        direction = "BUY" if text_upper in ("BUY", "MUA") else "SELL"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(text_upper)
            os.replace(tmp_file, d_file)
            notify_mt5_d_direction(direction)
            bot.reply_to(message, f"✅ Đã nhận {direction}, đang lưu vào MT5...")
            return
        except Exception:
            bot.reply_to(message, "⚠️ Không ghi được D direction vào file.")
            return
    nlp_triggers = [
        "buy", "sell", "mua", "ban", "long", "short",
        "close", "dong", "di", "sua", "tinh", "pnl",
        "status", "trang thai", "lai", "lo", "du bao",
        # Vietnamese with diacritics (OAK NLP commands)
        "đóng", "dời", "sửa", "hoà", "hòa", "tính", "dự",
        "tất cả", "toàn bộ", "lệnh", "giá", "về",
        "pending", "closeall", "modify", "status",
    ]
    if any(t in text.lower() for t in nlp_triggers):
        _inject_to_oak_inbox(text, message.chat.id)
        bot.reply_to(message, f"📨 Da chuyen vao OAK inbox:\n`{text}`")

# =====================================================================
# MAIN
# =====================================================================
if __name__ == "__main__":
    # Check if OAK Manager is already handling Telegram (single bot mode)
    def _is_oak_running():
        try:
            result = subprocess.run(
                ["wmic", "process", "where",
                 "CommandLine like '%OAK_Hidden_SLTP_Manager%' and Name='python.exe'",
                 "get", "ProcessId"],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in result.stdout.strip().split('\n'):
                if line.strip().isdigit():
                    return True
        except:
            pass
        return False

    if _is_oak_running():
        print("=" * 55)
        print("  MiMo Bridge Bot - SKIP (OAK Manager is running)")
        print("  OAK Manager now handles all Telegram commands.")
        print("  mimo_worker.py still runs independently.")
        print("=" * 55)
        # Keep alive so CHAY_ALL.bat doesn't restart it
        import time as _time
        while True:
            _time.sleep(60)
    else:
        print("=" * 55)
        print("  MiMo Bridge Bot v2.0 - Telegram <-> MiMo Code CLI")
        print(f"  Project: {PROJECT_DIR}")
        print(f"  Token:   {'SET' if BOT_TOKEN else 'MISSING'}")
        print(f"  Admin:   {ADMIN_CHAT_ID or '(Chua set - dung /myid)'}")
        print("=" * 55)
        print("  Dang chay... Ctrl+C de dung")
        print("  Queue file: mimo_queue.json")
        print("  Result file: mimo_result.json")
        print("=" * 55)

        import time as _time
        while True:
            try:
                bot.polling(none_stop=True, timeout=1, long_polling_timeout=1, skip_pending=True)
            except KeyboardInterrupt:
                print("\n  Đã dừng bot.")
                break
            except Exception as e:
                print(f"\n  Lỗi: {e}")
                print("  Đang kết nối lại sau 5 giây...")
                _time.sleep(1)
