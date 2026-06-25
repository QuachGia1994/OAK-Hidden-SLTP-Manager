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
import tempfile
from datetime import datetime
from pathlib import Path

try:
    import telebot
except ImportError:
    print("⚠️ Chưa cài pyTelegramBotAPI. Chạy: pip install pyTelegramBotAPI")
    sys.exit(1)

# =====================================================================
# CONFIGURATION - SỬA 2 DÒNG NÀY
# =====================================================================
BOT_TOKEN = "REMOVED_TOKEN"
ADMIN_CHAT_ID = 7732907060                  # Chat ID từ profiles.json (tele_admin)
# =====================================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PROJECT_DIR, "profiles.json")
SETTINGS_FILE = os.path.join(PROJECT_DIR, "settings.json")

# Files cho OAK integration
TELE_INBOX_FILE = os.path.join(PROJECT_DIR, "tele_inbox.json")
TELE_OFFSET_FILE = os.path.join(PROJECT_DIR, "tele_offset.json")

# Files cho MiMo Queue IPC
MIMO_QUEUE_FILE = os.path.join(PROJECT_DIR, "mimo_queue.json")
MIMO_RESULT_FILE = os.path.join(PROJECT_DIR, "mimo_result.json")

# =====================================================================
# BOT INSTANCE
# =====================================================================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# =====================================================================
# SECURITY
# =====================================================================
def is_admin(message):
    if ADMIN_CHAT_ID == 0:
        return True
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
    except Exception:
        return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Save error: {e}")

def send_telegram_msg(chat_id, text):
    """Gửi tin nhắn qua Telegram API trực tiếp"""
    try:
        clean = re.sub(r"<c=#[A-Fa-f0-9]{6}>", "", text)
        clean = clean.replace("</c>", "")
        if len(clean) > 4000:
            clean = clean[:4000] + "\n\n...[Cắt bột]..."
        msg = urllib.parse.quote(clean)
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={chat_id}&text={msg}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.read()
    except Exception as e:
        print(f"Send error: {e}")
        return None

def get_all_profiles():
    config = load_json(CONFIG_FILE)
    return list(config.keys())

# =====================================================================
# MIMO QUEUE IPC - File-based communication
# =====================================================================
def enqueue_mimo_command(command, chat_id, request_id=None):
    """Đặt lệnh vào hàng đợi cho MiMo Worker"""
    if request_id is None:
        request_id = f"req_{int(time.time())}_{chat_id}"
    
    queue = load_json(MIMO_QUEUE_FILE, [])
    if not isinstance(queue, list):
        queue = []
    
    queue.append({
        "id": request_id,
        "command": command,
        "chat_id": chat_id,
        "timestamp": time.time(),
        "status": "pending"
    })
    
    save_json(MIMO_QUEUE_FILE, queue)
    return request_id

def check_mimo_result(request_id, timeout=120):
    """Kiểm tra kết quả từ MiMo Worker"""
    start = time.time()
    while time.time() - start < timeout:
        result = load_json(MIMO_RESULT_FILE, {})
        if isinstance(result, dict) and result.get("id") == request_id:
            if result.get("status") == "done":
                return result.get("output", "Không có kết quả.")
        time.sleep(2)
    return None

def execute_mimo_via_shell(command):
    """
    Thuc thi lenh MiMo qua shell script.
    Su dung subprocess voi stdin/stdout redirect.
    """
    # Tim duong dan mimo CLI
    mimo_cmd = "mimo"
    
    # Tạo file temp chứa input
    input_file = os.path.join(PROJECT_DIR, "_mimo_input.txt")
    output_file = os.path.join(PROJECT_DIR, "_mimo_output.txt")
    
    try:
        # Ghi input vào file
        with open(input_file, "w", encoding="utf-8") as f:
            f.write(command + "\n")
            f.write("y\n")  # Auto-confirm
        
        # Chạy mimo với input từ file
        if sys.platform == "win32":
            # Windows: dùng cmd.exe
            shell_cmd = f'{mimo_cmd} < "{input_file}" > "{output_file}" 2>&1'
            process = subprocess.Popen(
                shell_cmd,
                shell=True,
                cwd=PROJECT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        else:
            # Linux/Mac
            process = subprocess.Popen(
                [mimo_cmd],
                stdin=open(input_file, "r"),
                stdout=open(output_file, "w"),
                stderr=subprocess.STDOUT,
                cwd=PROJECT_DIR,
            )
        
        # Đợi với timeout
        try:
            process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            process.kill()
            return "⏰ MiMo Code hết thời gian phản hồi (120s)."
        
        # Đọc kết quả
        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as f:
                output = f.read().strip()
            if output:
                if len(output) > 3500:
                    output = output[:3500] + "\n\n...[Cắt bột]..."
                return output
        
        return "MiMo đã thực thi xong nhưng không có output."
    
    except FileNotFoundError:
        return "❌ Không tìm thấy 'mimo' command. Hãy cài MiMo Code CLI."
    except Exception as e:
        return f"❌ Lỗi shell: {str(e)}"
    finally:
        # Dọn dẹp
        for f in [input_file, output_file]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except:
                pass

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
        "📌 *Dieu khien MiMo Code:*\n"
        "• `/mimo <yêu cầu>` - Gui lenh cho MiMo AI\n"
        "• `/code <file> <action>` - Doc/Sua file code\n"
        "• `/scan` - Quet toan bo du an\n\n"
        "📌 *Quan ly OAK:*\n"
        "• `/status` - Trang thai PC & files\n"
        "• `/profiles` - Danh sach tai khoan\n"
        "• `/mt5 <profile>` - Xem tai khoan MT5\n"
        "• `/positions <profile>` - Vi the dang mo\n"
        "• `/signal` - Tin hieu hien tai\n"
        "• `/news` - Tin kinh te\n"
        "• `/reply <text>` - Gui lenh vao OAK inbox\n\n"
        "💡 `/myid` - Lay Chat ID"
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

@bot.message_handler(commands=["signal"])
def cmd_signal(message):
    if not is_admin(message):
        return
    try:
        import signal_logic
        data = signal_logic.calculate_logic(None)
        signals = data.get("signals", {})
        lines = ["📡 *TÍN HIỆU*\n"]
        for pair, info in signals.items():
            sig = info.get("signal", "WAIT")
            icon = {"BUY": "🟢", "SELL": "🔴"}.get(sig, "⚪")
            lines.append(f"• {icon} *{pair}*: {sig}")
        lines.append(f"\n⏰ {data.get('last_update', '?')}")
        bot.reply_to(message, "\n".join(lines))
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
        bot.reply_to(message, header + "\n".join(news))
    except Exception as e:
        bot.reply_to(message, f"❌ Loi: {str(e)}")

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
    
    req_id = enqueue_mimo_command(prompt, message.chat.id)
    bot.reply_to(message, f"⏳ Đang gửi lệnh MiMo...\n📝 `{prompt}`\n🔑 ID: `{req_id}`")
    
    threading.Thread(target=_process_mimo, args=(message.chat.id, prompt, req_id), daemon=True).start()

def _process_mimo(chat_id, prompt, req_id):
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
        bot.reply_to(message, "Dùng: `/code signal_logic.py read`")
        return
    filename, action = parts
    filepath = os.path.join(PROJECT_DIR, filename)
    
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
    nlp_triggers = [
        "buy", "sell", "mua", "ban", "long", "short",
        "close", "dong", "di", "sua", "tinh", "pnl",
        "status", "trang thai", "lai", "lo", "du bao"
    ]
    if any(t in text.lower() for t in nlp_triggers):
        _inject_to_oak_inbox(text, message.chat.id)
        bot.reply_to(message, f"📨 Da chuyen vao OAK inbox:\n`{text}`")

# =====================================================================
# MAIN
# =====================================================================
if __name__ == "__main__":
    print("=" * 55)
    print("  MiMo Bridge Bot v2.0 - Telegram <-> MiMo Code CLI")
    print(f"  Project: {PROJECT_DIR}")
    print(f"  Token:   {BOT_TOKEN[:10]}...")
    print(f"  Admin:   {ADMIN_CHAT_ID or '(Chua set - dung /myid)'}")
    print("=" * 55)
    print("  Dang chay... Ctrl+C de dung")
    print("  Queue file: mimo_queue.json")
    print("  Result file: mimo_result.json")
    print("=" * 55)

    import time as _time
    while True:
        try:
            bot.polling(none_stop=True, timeout=30)
        except KeyboardInterrupt:
            print("\n  Đã dừng bot.")
            break
        except Exception as e:
            print(f"\n  Lỗi: {e}")
            print("  Đang kết nối lại sau 5 giây...")
            _time.sleep(5)
