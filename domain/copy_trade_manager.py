# -*- coding: utf-8 -*-
"""CopyTradeManager — master/slave copy + scheduled trades engine."""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import time
import threading
import unicodedata
import winsound
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, date

import MetaTrader5 as mt5

import oak_trading_reminders
from oak_response_dict import get_random_response
from oak_logger import setup_logger

from domain.constants import (
    CONFIG_FILE,
    SESSION_RECOVERY_FILE,
    PENDING_PARTIALS_FILE,
    _mimo_bot_token,
    _mimo_bot_chat_id,
)
from domain.json_io import load_json, save_json
from domain.i18n import T, CURRENT_LANG, LANG
from domain.mt5_orders import get_filling_type, send_order_with_retry
from domain.ticket_manager import TicketManager, trades_file_for_profile
from domain.file_lock import FileLock
from domain.balance import get_start_day_balance

log = setup_logger("copy_trade")

def get_natural_response(category, **kwargs):
    try:
        return get_random_response(category, **kwargs)
    except Exception:
        return ""


def _safe_profile_filename(profile_name: str) -> str:
    raw = (profile_name or "default").strip() or "default"
    return "".join(c for c in raw if c.isalpha() or c.isdigit() or c in (" ", "-", "_")).strip() or "default"


def pending_partials_file_for_profile(profile_name: str) -> str:
    """Per-profile partial-close tasks (avoids ticket_id collisions across brokers)."""
    return f"pending_partials_{_safe_profile_filename(profile_name)}.json"


def _plain_command_text(value: str) -> str:
    """Lowercase Vietnamese command text without accents for safer intent parsing."""
    normalized = unicodedata.normalize("NFD", value or "")
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "d").lower()


def _extract_close_symbol(raw_text: str) -> str:
    """Extract a close target symbol without treating generic words as symbols."""
    plain = _plain_command_text(raw_text)
    if re.search(r"\b(xauusd|xau|gold|vang)\b", plain):
        return "XAUUSD"
    upper = raw_text.upper()
    match = re.search(r"\b(XAUUSD|[A-Z]{3}(?:USD|JPY|EUR|GBP|AUD|CAD|CHF|NZD)[A-Z+.]*)\b", upper)
    return match.group(1).rstrip(",.!;:") if match else ""


def _extract_close_ticket(raw_text: str) -> str:
    """Extract an explicit ticket id; ignore HHMM clock fragments."""
    plain = _plain_command_text(raw_text)
    match = re.search(r"\b(?:ticket|id|order|lenh)\s*#?\s*(\d{5,})\b", plain)
    return match.group(1) if match else ""


def _broker_clock_to_local_clock(broker_clock: str, broker_utc_offset: float, local_utc_offset: float) -> str:
    """Convert a broker HH:MM clock into the worker's local HH:MM clock."""
    match = re.fullmatch(r"(\d{1,2}):([0-5]\d)", broker_clock or "")
    if not match or not -12 <= broker_utc_offset <= 14 or not -12 <= local_utc_offset <= 14:
        raise ValueError("giờ broker không hợp lệ")
    hour, minute = map(int, match.groups())
    if hour > 23:
        raise ValueError("giờ broker không hợp lệ")
    shifted = hour * 60 + minute + round((local_utc_offset - broker_utc_offset) * 60)
    shifted %= 24 * 60
    return f"{shifted // 60:02d}:{shifted % 60:02d}"


def _live_broker_utc_offset() -> int:
    """Read the active MT5 server offset without guessing when ticks are unavailable."""
    now_epoch = time.time()
    for symbol in ("XAUUSD", "GBPUSD"):
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            continue
        offset = round((float(tick.time) - now_epoch) / 3600)
        if -12 <= offset <= 14:
            return offset
    raise ValueError("không xác định được múi giờ broker")


def _local_utc_offset() -> float:
    """Return the Windows local UTC offset in hours."""
    offset = datetime.now().astimezone().utcoffset()
    if offset is None:
        raise ValueError("không xác định được múi giờ Windows")
    return offset.total_seconds() / 3600


class CopyTradeManager:
    def __init__(self, config, notify_callback):
        self.config = config
        self.notify = notify_callback
        self.scheduled_trades = [] # List of dicts: {symbol, type, lot, time, sl, tp, status}
        self.scheduled_file = ""

        role_raw = self.config.get("copy_role", "None")
        self.role = role_raw.lower() # none, master, slave

        self.channel = self.config.get("copy_channel", "default")

        mode_raw = self.config.get("copy_lot_mode", "Fixed")
        if "Risk" in mode_raw: self.lot_mode = "risk"
        elif "Multiplier" in mode_raw: self.lot_mode = "multiplier"
        else: self.lot_mode = "fixed"

        self.lot_value = self._safe_float(self.config.get("copy_lot_value", 0.01))
        self.stealth = bool(self.config.get("copy_stealth", False))
        self.max_one = bool(self.config.get("copy_max_one", False))

        # Safety guardrails
        self.max_daily_trades = int(self.config.get("copy_max_daily_trades", 20))
        self.max_lot_per_trade = self._safe_float(self.config.get("copy_max_lot_per_trade", 5.0))
        self.kill_switch = bool(self.config.get("copy_kill_switch", False))
        self.max_exposure_per_symbol = self._safe_float(self.config.get("copy_max_exposure", 10.0))
        self.stale_threshold_sec = int(self.config.get("copy_stale_threshold", 300))

        # Daily trade counter (resets at midnight)
        self._daily_trade_count = 0
        self._daily_trade_date = None
        
        # Shared Directory
        self.shared_dir = os.path.join(os.path.expanduser("~"), ".oak_copy_trade")
        if not os.path.exists(self.shared_dir):
            try:
                os.makedirs(self.shared_dir)
            except: pass
            
        self.signal_file = os.path.join(self.shared_dir, f"{self.channel}.json")
        
        # Unique Map File for this Profile
        profile_name = self.config.get("profile_name", "default")
        # Sanitize filename
        safe_name = _safe_profile_filename(profile_name)
        self.local_map_file = f"copy_map_{safe_name}.json"
        self.scheduled_file = f"waiting_{safe_name}.json"
        self.scheduled_close_file = f"scheduled_close_{safe_name}.json"
        self.pending_partials_file = pending_partials_file_for_profile(profile_name)
        # Ticket state isolated per profile (multi-process safe)
        self.ticket_manager = TicketManager(profile_name=profile_name)
        self._migrate_legacy_pending_partials(profile_name)
        
        self.mapping = load_json(self.local_map_file) # {master_ticket: slave_ticket}
        self.mapping_lock = threading.Lock()
        self.scheduled_trades = load_json(self.scheduled_file)
        if not isinstance(self.scheduled_trades, list):
            self.scheduled_trades = []
        self._scheduled_close = load_json(self.scheduled_close_file, [])
        if not isinstance(self._scheduled_close, list):
            self._scheduled_close = []
        self._last_auto_close_date = None
        self.connected_logged = False

        # --- IGNORE EXISTING MASTER TRADES ON STARTUP ---
        self.ignored_file = f"ignored_{safe_name}.json"
        self.ignored_tickets = set(load_json(self.ignored_file, []))
        if self.role == "slave" and os.path.exists(self.signal_file):
            try:
                with open(self.signal_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    new_ignored = set()
                    for p in data.get("positions", []):
                        ticket = int(p["ticket"])
                        if ticket not in self.ignored_tickets:
                            new_ignored.add(ticket)
                    if new_ignored:
                        self.ignored_tickets.update(new_ignored)
                        save_json(self.ignored_file, list(self.ignored_tickets))
                if self.ignored_tickets:
                    self.notify(T("log_ignored_trades").format(count=len(self.ignored_tickets)))
            except:
                pass

    def _migrate_legacy_pending_partials(self, profile_name: str) -> None:
        """One-shot: move this profile's tasks out of shared pending_partials.json."""
        try:
            dest = self.pending_partials_file
            if os.path.exists(dest):
                return
            if not os.path.exists(PENDING_PARTIALS_FILE):
                return
            legacy = load_json(PENDING_PARTIALS_FILE)
            if not isinstance(legacy, dict) or not legacy:
                return
            mine, rest = {}, {}
            for tid, task in legacy.items():
                if isinstance(task, dict) and task.get("profile") == profile_name:
                    mine[tid] = task
                else:
                    rest[tid] = task
            if not mine:
                return
            save_json(dest, mine)
            save_json(PENDING_PARTIALS_FILE, rest)
            log.info(
                "Migrated %d pending_partials for profile '%s' → %s",
                len(mine),
                profile_name,
                dest,
            )
        except Exception as e:
            log.warning("pending_partials migrate skipped: %s", e)

    def _add_partial_close_task(self, ticket_id, target_profit, close_vol, target_price=None, symbol_hint=""):
        profile_name = self.config.get("profile_name", "Unknown")
        
        # Verify ticket exists in MT5 and get info
        symbol = ""
        order_type = ""
        if mt5.terminal_info():
            positions = mt5.positions_get()
            if positions:
                for p in positions:
                    if ticket_id and p.ticket == ticket_id:
                        symbol = p.symbol
                        order_type = "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL"
                        break
                    # Symbol-only task: match first open position of symbol
                    if (not ticket_id) and symbol_hint:
                        if symbol_hint.upper().replace("+", "") in p.symbol.upper().replace("+", ""):
                            symbol = p.symbol
                            order_type = "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL"
                            ticket_id = p.ticket
                            break
            
            # If not found in positions, maybe it's an order? (Though partial close is for positions)
            if not symbol and ticket_id:
                orders = mt5.orders_get()
                if orders:
                    for o in orders:
                        if o.ticket == ticket_id:
                            symbol = o.symbol
                            order_type = "BUY" if o.type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP] else "SELL"
                            break
        
        if not symbol:
            symbol = symbol_hint or "???"
            order_type = order_type or "???"

        if not ticket_id:
            self.notify(f"❌ [{profile_name}] Không tìm thấy lệnh mở cho {symbol_hint or 'symbol'}")
            return False

        # Load existing tasks
        task_file = self.pending_partials_file
        tasks = load_json(task_file)
        if not isinstance(tasks, dict): tasks = {}
        
        mode = "price" if target_price is not None else "profit"
        tasks[str(ticket_id)] = {
            "target_profit": float(target_profit or 0),
            "target_price": float(target_price) if target_price is not None else None,
            "mode": mode,
            "close_volume": close_vol,
            "profile": profile_name,
            "symbol": symbol,
            "type": order_type,
            "created_at": time.time()
        }
        
        save_json(task_file, tasks)
        
        if mode == "price":
            self.notify(
                f"✂️ [{profile_name}] Đã canh chốt {close_vol} lot {symbol} "
                f"(#{ticket_id}) khi giá đạt {float(target_price):,.2f}"
            )
        else:
            resp = get_natural_response("partial_task_added", 
                                        ticket_id=ticket_id, 
                                        symbol=symbol, 
                                        profit=f"{float(target_profit):,.2f}", 
                                        vol=close_vol)
            self.notify(f"✂️ [{profile_name}] {resp}")
        return True

    def _check_partial_close_tasks(self):
        """Check pending partial close tasks against current positions"""
        task_file = self.pending_partials_file
        if not os.path.exists(task_file): return
        
        try:
            tasks = load_json(task_file)
            if not tasks: return
            
            positions = mt5.positions_get()
            if not positions: return
            
            # Map positions by ticket for fast lookup
            pos_map = {p.ticket: p for p in positions}
            
            completed_tickets = []
            
            for tid_str, task in tasks.items():
                try:
                    ticket_id = int(tid_str)
                except (TypeError, ValueError):
                    completed_tickets.append(tid_str)
                    continue
                target_profit = float(task.get("target_profit") or 0)
                target_price = task.get("target_price")
                mode = task.get("mode") or ("price" if target_price is not None else "profit")
                close_vol = float(task.get("close_volume") or 0)
                target_profile = task.get("profile", "")
                
                current_profile = self.config.get("profile_name", "Unknown")
                if target_profile and target_profile != current_profile:
                    continue
                
                if ticket_id in pos_map:
                    pos = pos_map[ticket_id]
                    net_profit = pos.profit + pos.swap + getattr(pos, "commission", 0)
                    hit = False
                    if mode == "price" and target_price is not None:
                        try:
                            tp = float(target_price)
                        except (TypeError, ValueError):
                            tp = None
                        if tp is not None:
                            # BUY: price rises to target; SELL: price falls to target
                            if pos.type == mt5.POSITION_TYPE_BUY and pos.price_current >= tp:
                                hit = True
                            elif pos.type == mt5.POSITION_TYPE_SELL and pos.price_current <= tp:
                                hit = True
                    else:
                        hit = net_profit >= target_profit

                    if hit:
                        # Re-verify position exists (may have been closed by SL/TP)
                        verify = mt5.positions_get(ticket=ticket_id)
                        if not verify:
                            self.log(f"⚠️ Position {ticket_id} already closed, cleaning task")
                            completed_tickets.append(tid_str)
                            continue
                        if self._partial_close(pos, close_vol):
                            resp = get_natural_response("partial_success", ticket_id=ticket_id, vol=close_vol)
                            self.notify(f"✅ [{current_profile}] {resp}")
                            completed_tickets.append(tid_str)
                        else:
                            self.notify(f"❌ [{current_profile}] Partial Close Failed: Ticket #{ticket_id}. Retrying...")
                else:
                    # Position no longer exists (closed manually or SL/TP)
                    completed_tickets.append(tid_str)
            
            if completed_tickets:
                current_tasks = load_json(task_file)
                for t in completed_tickets:
                    if t in current_tasks:
                        del current_tasks[t]
                save_json(task_file, current_tasks)
                
        except Exception as e:
            print(f"Partial check error: {e}")

    def _partial_close(self, pos, volume):
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick: return False
        
        price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
        
        # Check volume validity
        if volume > pos.volume: volume = pos.volume # Close all if req > current
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": pos.ticket,
            "price": price,
            "deviation": 20,
            "magic": pos.magic,
            "comment": "Auto Partial Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": get_filling_type(pos.symbol),
        }
        
        res = send_order_with_retry(request)
        return res.retcode == mt5.TRADE_RETCODE_DONE

    def process(self):
        # Sync scheduled trades from file if changed by GUI
        if self.scheduled_file and os.path.exists(self.scheduled_file):
            try:
                mtime = os.path.getmtime(self.scheduled_file)
                if not hasattr(self, "_last_scheduled_mtime"):
                    self._last_scheduled_mtime = mtime
                elif mtime > self._last_scheduled_mtime:
                    self.scheduled_trades = load_json(self.scheduled_file)
                    if not isinstance(self.scheduled_trades, list): self.scheduled_trades = []
                    self._last_scheduled_mtime = mtime
                    # self.notify(f"Synced scheduled trades from file.")
            except: pass

        self._check_scheduled_trades()
        self._check_telegram_commands()
        self._check_partial_close_tasks() # NEW CHECK
        if self.role == "master":
            self._process_master()
        elif self.role == "slave":
            self._process_slave()


    def _is_mimo_bot_running(self):
        """Check if mimo_bot.py process is running to avoid Telegram polling conflict"""
        try:
            result = subprocess.run(
                ["wmic", "process", "where",
                 "CommandLine like '%mimo_bot.py%' and Name='python.exe'",
                 "get", "ProcessId"],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in result.stdout.strip().split('\n'):
                if line.strip().isdigit():
                    return True
        except:
            pass
        return False

    def _check_telegram_commands(self):
        """Check for remote commands via shared inbox (mimo_bot.py is the sole Telegram poller)."""
        chat_id = str(_mimo_bot_chat_id) if _mimo_bot_chat_id else self.config.get("tele_chat", "")
        if not chat_id: return

        if not hasattr(self, "_last_tele_check"): self._last_tele_check = 0
        if time.time() - self._last_tele_check < 4.0: return
        self._last_tele_check = time.time()
        if not hasattr(self, "_startup_ts"):
            self._startup_ts = time.time()

        inbox_file = "tele_inbox.json"
        if not os.path.exists(inbox_file): return

        try:
            if not hasattr(self, "_last_processed_id"):
                self._last_processed_id = 0

            with open(inbox_file, "r", encoding="utf-8") as f:
                inbox = json.load(f)

            now_ts = time.time()
            min_ts = self._startup_ts - 60

            for update in inbox:
                u_id = update["update_id"]
                if u_id > self._last_processed_id:
                    msg = update.get("message") or update.get("channel_post")
                    if not msg:
                        continue

                    msg_date = msg.get("date", 0)
                    if msg_date and msg_date < min_ts:
                        self._last_processed_id = u_id
                        continue
                    if msg_date and now_ts - msg_date > 86400:
                        self._last_processed_id = u_id
                        continue

                    text = msg.get("text", "").strip()
                    sender_id = str(msg.get("chat", {}).get("id", ""))
                    admin_id = str(self.config.get("tele_admin", "")).strip()

                    is_valid_sender = (sender_id == str(chat_id)) or (admin_id and sender_id == admin_id)

                    if is_valid_sender and text:
                        lines = text.split('\n')
                        for line in lines:
                            if line.strip():
                                self._handle_telegram_text(line.strip())

                    self._last_processed_id = u_id
        except Exception as e:
            log.warning("Telegram inbox processing error: %s", e)

    def _send_mimo_response(self, text):
        """Send response via MiMo bot token (single Telegram bot)"""
        token = _mimo_bot_token
        chat_id = _mimo_bot_chat_id
        if not token or not chat_id: return
        try:
            clean = re.sub(r"<c=#[A-Fa-f0-9]{6}>", "", text)
            clean = clean.replace("</c>", "")
            if len(clean) > 4000:
                clean = clean[:4000] + "\n\n...[Cắt bớt]..."
            payload = json.dumps({"chat_id": chat_id, "text": clean}).encode("utf-8")
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=15)
        except Exception as e:
            print(f"[MiMo] Send error: {e}")

    def _process_mimo_cmd(self, prompt):
        """Process /mimo command in background thread"""
        try:
            cmd_lower = prompt.lower().strip()
            if any(w in cmd_lower for w in ["status", "trang thai", "tinh trang"]):
                now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                result = f"Trạng thái hệ thống lúc {now}:\n- OAK Manager: đang chạy\n- MT5 Signal Bot: đang chạy\n- Tất cả hoạt động bình thường."
            elif any(w in cmd_lower for w in ["signal", "tin hieu"]):
                result = "Tín hiệu hiện tại: Đang chờ slot kích hoạt tiếp theo."
            elif any(w in cmd_lower for w in ["time", "gio", "thoi gian"]):
                now = datetime.now()
                result = f"Giờ local: {now.strftime('%H:%M:%S')}\nNgày: {now.strftime('%d/%m/%Y')}"
            elif any(w in cmd_lower for w in ["help", "giup", "huong dan"]):
                result = "Các lệnh: status, signal, time, help"
            else:
                result = f"Đã nhận: '{prompt}'"
            self._send_mimo_response(f"✅ *Kết quả MiMo:*\n```\n{result}\n```")
        except Exception as e:
            self._send_mimo_response(f"❌ Lỗi: {str(e)}")

    def _run_scan_cmd(self):
        """Scan project files in background thread"""
        try:
            project_dir = os.path.dirname(os.path.abspath(__file__))
            py_files = []
            for f in os.listdir(project_dir):
                if f.endswith(".py"):
                    size = os.path.getsize(os.path.join(project_dir, f))
                    py_files.append(f"{f} ({size:,} bytes)")
            json_files = [f for f in os.listdir(project_dir) if f.endswith(".json") and not f.startswith(("_", "."))]
            lines = ["📂 *QUÉT DỰ ÁN:*\n", f"🐍 Python files ({len(py_files)}):"]
            for f in py_files[:15]:
                lines.append(f"  • {f}")
            lines.append(f"\n📦 JSON files ({len(json_files)}):")
            for f in json_files[:10]:
                lines.append(f"  • {f}")
            self._send_mimo_response("\n".join(lines))
        except Exception as e:
            self._send_mimo_response(f"❌ Lỗi quét: {str(e)}")

    def _handle_telegram_text(self, text):
        """Parse and execute Enhanced Telegram commands (Support both Syntax and Natural Language)"""
        raw_text = text.strip()
        text_lower = raw_text.lower()
        plain_text = _plain_command_text(raw_text)
        cmd = text_lower.split()
        if not cmd: return
        cmd_set = set(cmd)
        
        profile_name = self.config.get("profile_name", "Unknown")
        profile_lower = profile_name.lower()

        # --- MiMo Bot Commands (merged from mimo_bot.py) ---
        if cmd[0] == "/myid":
            self._send_mimo_response(f"Chat ID: `{_mimo_bot_chat_id}`")
            return
        if cmd[0] == "/mimo":
            prompt = raw_text.replace("/mimo", "").strip()
            if not prompt:
                self._send_mimo_response("Dùng: `/mimo <yêu cầu>`")
                return
            self._send_mimo_response(f"⏳ Đang gửi lệnh MiMo...\n📝 `{prompt}`")
            threading.Thread(target=self._process_mimo_cmd, args=(prompt,), daemon=True).start()
            return
        if cmd[0] == "/code":
            args = raw_text.replace("/code", "").strip()
            if not args:
                self._send_mimo_response("Dùng: `/code <file> <read|edit>`")
                return
            parts = args.split(None, 1)
            if len(parts) < 2:
                self._send_mimo_response("Dùng: `/code oak_response_dict.py read`")
                return
            filename, action = parts
            if ".." in filename or "/" in filename or "\\" in filename:
                self._send_mimo_response("❌ Tên file không hợp lệ!")
                return
            filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.basename(filename))
            if action.lower() == "read":
                if not os.path.exists(filepath):
                    self._send_mimo_response(f"❌ File không tồn tại: `{filename}`")
                    return
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                    if len(content) > 3500:
                        content = content[:3500] + "\n\n...[Cắt bớt]..."
                    self._send_mimo_response(f"📄 *{filename}:*\n```\n{content}\n```")
                except Exception as e:
                    self._send_mimo_response(f"❌ Lỗi đọc file: {str(e)}")
            else:
                self._send_mimo_response("Chỉ hỗ trợ: `read`")
            return
        if cmd[0] == "/scan":
            self._send_mimo_response("⏳ Đang quét dự án...")
            threading.Thread(target=self._run_scan_cmd, daemon=True).start()
            return
        if cmd[0] in ("/profiles", "/profile"):
            config = load_json(CONFIG_FILE)
            if not config:
                self._send_mimo_response("❌ Không tìm thấy profiles.json")
                return
            lines = ["📋 *DANH SÁCH PROFILE:*\n"]
            for name, p in config.items():
                ok = "✅" if os.path.exists(p.get("path", "")) else "❌"
                lines.append(f"• *{name}* {ok} SL:{p.get('sl','?')} TP:{p.get('tp','?')}")
            self._send_mimo_response("\n".join(lines))
            return
        if cmd[0] == "/mt5":
            args = raw_text.replace("/mt5", "").strip()
            if not args:
                self._send_mimo_response("Dùng: `/mt5 <profile>`")
                return
            config = load_json(CONFIG_FILE)
            pname = None
            for name in config:
                if name.lower() == args.lower():
                    pname = name
                    break
            if not pname:
                self._send_mimo_response(f"❌ Không tìm thấy: `{args}`")
                return
            p = config[pname]
            path = p.get("path", "")
            if not path or not os.path.exists(path):
                self._send_mimo_response(f"❌ Đường dẫn không tồn tại: `{path}`")
                return
            try:
                if not mt5.initialize(path=path):
                    self._send_mimo_response(f"❌ MT5 connect failed: {pname}")
                    return
                acc = mt5.account_info()
                if acc:
                    msg = (
                        f"🏦 *{pname} - MT5*\n\n"
                        f"• Server: `{acc.server}`\n"
                        f"• Login: `{acc.login}`\n"
                        f"• Balance: {acc.balance:,.2f} {acc.currency}\n"
                        f"• Equity: {acc.equity:,.2f}\n"
                        f"• Margin: {acc.margin:,.2f}"
                    )
                    self._send_mimo_response(msg)
                else:
                    self._send_mimo_response(f"❌ Không lấy được info: {pname}")
                mt5.shutdown()
            except Exception as e:
                self._send_mimo_response(f"❌ Lỗi MT5: {str(e)}")
            return
        if cmd[0] in ("/positions", "/position"):
            positions = mt5.positions_get()
            if not positions:
                self._send_mimo_response(f"📋 [{profile_name}] Không có lệnh nào đang mở.")
                return
            lines = [f"📋 [{profile_name}] *VỊ THẾ ĐANG MỞ:*\n"]
            for pos in positions:
                typ = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                pnl = pos.profit + pos.swap + getattr(pos, "commission", 0)
                icon = "🟢" if pnl >= 0 else "🔴"
                lines.append(f"{icon} {pos.symbol} {typ} {pos.volume} lot | PnL: {pnl:+.2f}")
            self._send_mimo_response("\n".join(lines))
            return
        if cmd[0] in ("/signal", "/tinhieu", "/tin_hieu"):
            try:
                base = os.path.dirname(os.path.abspath(__file__))
                state = load_json(os.path.join(base, "bot_state.json"), {})
                log_rows = load_json(os.path.join(base, "signals_log.json"), [])
                today = state.get("date")
                if not today and isinstance(log_rows, list) and log_rows:
                    today = max((r.get("date") for r in log_rows if r.get("date")), default=None)
                if not today:
                    self._send_mimo_response("📡 Chưa có tín hiệu hôm nay (`bot_state` / `signals_log`).")
                    return
                today_rows = [r for r in (log_rows or []) if r.get("date") == today]
                by_hour = {}
                for row in today_rows:
                    try:
                        h = int(row.get("hour"))
                    except (TypeError, ValueError):
                        continue
                    by_hour[h] = row
                lines = [
                    f"📡 *TÍN HIỆU HÔM NAY* ({today})",
                    "",
                ]
                if not by_hour:
                    lines.append("(Chưa có slot nào được ghi nhận trong signals_log)")
                else:
                    for h in sorted(by_hour.keys()):
                        payload = by_hour[h] or {}
                        sig = payload.get("signal", "?")
                        icon = "🟢" if sig == "BUY" else "🔴" if sig == "SELL" else "⚪"
                        pair_dirs = payload.get("pair_dirs") or {}
                        pair_bits = []
                        for pair in ("XAUUSD", "GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"):
                            direction = pair_dirs.get(pair)
                            if direction in ("BUY", "SELL", "--"):
                                pair_bits.append(f"{pair}:{direction}")
                        extra = f"\n   {', '.join(pair_bits)}" if pair_bits else ""
                        note = payload.get("hour_note")
                        note_line = f"\n   📝 {note}" if note else ""
                        lines.append(f"{icon} H={h:02d}:45 → *{sig}*{extra}{note_line}")
                self._send_mimo_response("\n".join(lines))
            except Exception as e:
                self._send_mimo_response(f"❌ Lỗi /signal: {e}")
            return
        if cmd[0] == "/reply":
            # Already handled by inbox injection, just acknowledge
            return

        # --- NLP PnL Logic ---
        symbol_match = re.search(r"([A-Z]{2,12}(?:\+)?(?:\.[a-zA-Z0-9]+)?)", text.upper())
        price_match = re.search(r"(\d+(?:\.\d+)?)", text)
        
        is_pnl_trigger = any(t in text_lower for t in ["tính", "pnl", "lãi", "lỗ", "dự báo", "chạm", "mức", "dự đoán"])
        
        if is_pnl_trigger and symbol_match and price_match:
            symbol = symbol_match.group(1)
            try:
                target_price = float(price_match.group(1))
                if not symbol.isdigit():
                    # Identify profile if mentioned
                    requested_profile = None
                    potential_profiles = ["vantage", "th5ers", "exness", "icmarkets", "fbs", "xm", "pepperstone"]
                    for p in potential_profiles:
                        if p in text_lower:
                            requested_profile = p
                            break
                    if not requested_profile:
                        requested_profile = profile_name
                    
                    import oak_trading_reminders
                    reminder = oak_trading_reminders.OakTradingReminder(
                        token=self.config.get("tele_token", ""),
                        chat_id=self.config.get("tele_chat", "")
                    )
                    result_msg = reminder.get_projected_pnl(symbol, target_price, requested_profile)
                    self.notify(result_msg)
                    return # Exit early after handling PnL
            except Exception as e:
                print(f"PnL NLP Error: {e}")

        # Define symbol_map globally for NLP
        symbol_map = {"vàng": "XAUUSD", "gold": "XAUUSD", "gu": "GBPUSD", "eu": "EURUSD", "uj": "USDJPY"}

        # Profile gate (exact match only — typos like VantageDemi must NOT broadcast)
        target_profile, invalid_profile, _ = self._resolve_target_profile(cmd)
        if invalid_profile:
            self._notify_invalid_profile(invalid_profile)
            return
        if target_profile and target_profile != profile_lower:
            return
        
        # --- NLP Parsing Logic ---
        # If not starting with "/", try to convert natural language to /pending or /closeall syntax
        if not text_lower.startswith("/"):
            # 1. Check for Buy/Sell intent
            is_buy = any(kw in text_lower for kw in ["buy", "mua", "long"])
            is_sell = any(kw in text_lower for kw in ["sell", "bán", "short"])
            # 2. Check for Set/Modify Intent (Global Check)
            if cmd_set & {"set", "cài", "đặt", "sửa", "modify", "change", "chỉnh", "dời"}:
                try:
                    mod_type = ""
                    if "sl" in cmd_set or "stoploss" in cmd_set: mod_type = "sl"
                    elif "tp" in cmd_set or "takeprofit" in cmd_set: mod_type = "tp"
                    
                    if mod_type:
                        val = 0.0
                        target_sym = ""
                        
                        for w in cmd:
                            w_clean = w.replace(",", ".")
                            if any(kw in text_lower for kw in ["hòa", "hoà", "hoa", "breakeven", "break even", "be"]):
                                mod_type = "sl"
                                val = -1.0
                            else:
                                try:
                                    val = float(w_clean)
                                    continue
                                except: pass
                            
                            w_parsed = w
                            if "/" in w: w_parsed = w.split("/")[0]
                            
                            if w_parsed in symbol_map: target_sym = symbol_map[w_parsed]
                            else:
                                w_upper = w_parsed.upper()
                                if len(w_upper) >= 3 and any(c in w_upper for c in ["USD", "JPY", "EUR", "GBP", "AUD", "CAD", "CHF", "NZD", "XAU", "GOLD"]):
                                    target_sym = w_upper
                        
                        if val != 0.0 and target_sym:
                            self._modify_positions(mod_type, val, target_sym)
                            return
                except Exception as e:
                    profile_name = self.config.get("profile_name", "Unknown")
                    self.notify(f"❌ [{profile_name}] NLP Error: {e}")

            # 3. Check for Buy/Sell Intent (Open Order)
            if is_buy or is_sell:
                t_type = "buy" if is_buy else "sell"
                
                symbol = ""
                sl = "0"
                tp = "0"
                symbol_map = {"vàng": "XAUUSD", "gold": "XAUUSD", "gu": "GBPUSD", "eu": "EURUSD", "uj": "USDJPY"}
                for word in cmd:
                    raw_w = word.strip(",.!")
                    w = raw_w.lower()
                    if w in symbol_map:
                        symbol = symbol_map[w]
                        break
                    if len(raw_w) >= 6 and ("usd" in w or "jpy" in w or "eur" in w or "gbp" in w or "xau" in w):
                        symbol = raw_w.upper()
                        break
                
                # Extract Lot (float)
                lot = "0.01"
                lots = re.findall(r"\b\d+\.\d+\b", text_lower) or re.findall(r"\b0\.\d+\b", text_lower)
                if lots: lot = lots[0]
                
                risk_match = re.search(r"(?:risk|rủi ro|với)\s*(\d+(?:\.\d+)?)%?", text_lower)
                sl_pips_match = re.search(r"(?:sl|stop|stoploss)\s*(\d+)\s*(?:pip|pips)?", text_lower)
                
                if risk_match and sl_pips_match:
                    try:
                        risk_pct = float(risk_match.group(1))
                        sl_val = int(sl_pips_match.group(1))
                        
                        # Only calc if we have a valid symbol and MT5 connection
                        if symbol and mt5.terminal_info():
                            acc = mt5.account_info()
                            sym_info = mt5.symbol_info(symbol)
                            
                            if acc and sym_info and sym_info.trade_tick_value > 0 and sym_info.trade_tick_size > 0:
                                balance = acc.balance
                                risk_amount = balance * (risk_pct / 100.0)
                                
                                # Convert Pips to Points (1 pip = 10 points usually)
                                # If user says "100 pips", that's 1000 points.
                                # If user just says "sl 100", we assume points if no "pips" keyword?
                                # But in this Risk context, users usually talk in Pips.
                                # Let's assume Pips if "pips" keyword exists, otherwise check magnitude.
                                is_pips_explicit = "pip" in text_lower
                                
                                # Heuristic: If < 200, assume Pips. If > 200, assume Points? 
                                # Gold 100 pips = 1000 points. Gold SL 50 points is very tight (5 pips).
                                # Let's default to: If explicit 'pips', x10. If not, treat as Points unless small (<500).
                                # User prompt: "stoploss 100 pips".
                                
                                sl_points = sl_val
                                is_gold = "XAU" in symbol.upper() or "GOLD" in symbol.upper()
                                if is_pips_explicit:
                                    sl_points = sl_val * 10
                                elif is_gold and sl_val < 500:
                                    sl_points = sl_val * 10
                                    
                                # Formula: Lot = Risk / (SL_Points * TickValue)
                                # TickValue is value of 1 point for 1 lot (usually)
                                value_per_point = (sym_info.trade_tick_value / sym_info.trade_tick_size) * sym_info.point
                                if value_per_point <= 0:
                                    raise Exception("Invalid tick value")
                                calc_lot = risk_amount / (sl_points * value_per_point)
                                
                                # Rounding to step
                                step = sym_info.volume_step
                                if step > 0:
                                    calc_lot = round(calc_lot / step) * step
                                    decimals = self._get_step_decimals(step)
                                    calc_lot = round(calc_lot, decimals)
                                
                                # Min/Max
                                calc_lot = max(sym_info.volume_min, min(sym_info.volume_max, calc_lot))
                                
                                decimals = self._get_step_decimals(sym_info.volume_step)
                                lot = f"{calc_lot:.{decimals}f}"
                                
                                # Update SL to Points for the command
                                sl = str(sl_points)
                                
                                self.notify(f"🧮 [{profile_name}] Auto Lot: {risk_pct}% Bal (${risk_amount:.2f}) / {sl_points} pts -> {lot} Lot")
                    except Exception as e:
                        profile_name = self.config.get("profile_name", "Unknown")
                        self.notify(f"⚠️ [{profile_name}] Risk Calc Error: {e}")

                money_match = re.search(r"(?:lỗ|risk|rủi ro|mất)\s*\$?\s*(\d+(?:\.\d+)?)", text_lower)
                if not money_match:
                    money_match = re.search(r"\$\s*(\d+(?:\.\d+)?)", text_lower)
                
                if money_match and sl_pips_match:
                    try:
                        risk_amount = float(money_match.group(1))
                        sl_val = int(sl_pips_match.group(1))
                        
                        if symbol and mt5.terminal_info():
                            acc = mt5.account_info()
                            sym_info = mt5.symbol_info(symbol)
                            
                            if acc and sym_info and sym_info.trade_tick_value > 0 and sym_info.trade_tick_size > 0:
                                is_pips_explicit = "pip" in text_lower
                                
                                sl_points = sl_val
                                is_gold = "XAU" in symbol.upper() or "GOLD" in symbol.upper()
                                if is_pips_explicit:
                                    sl_points = sl_val * 10
                                elif is_gold and sl_val < 500:
                                    sl_points = sl_val * 10
                                
                                value_per_point = (sym_info.trade_tick_value / sym_info.trade_tick_size) * sym_info.point
                                if value_per_point <= 0:
                                    raise Exception("Invalid tick value")
                                calc_lot = risk_amount / (sl_points * value_per_point)
                                
                                step = sym_info.volume_step
                                if step > 0:
                                    calc_lot = round(calc_lot / step) * step
                                    decimals = self._get_step_decimals(step)
                                    calc_lot = round(calc_lot, decimals)
                                
                                calc_lot = max(sym_info.volume_min, min(sym_info.volume_max, calc_lot))
                                
                                decimals = self._get_step_decimals(sym_info.volume_step)
                                lot = f"{calc_lot:.{decimals}f}"
                                sl = str(sl_points)
                                
                                self.notify(f"🧮 [{profile_name}] Auto Lot: ${risk_amount:.2f} Risk / {sl_points} pts -> {lot} Lot")
                    except Exception as e:
                        profile_name = self.config.get("profile_name", "Unknown")
                        self.notify(f"⚠️ [{profile_name}] Risk Calc Error: {e}")

                # Extract Time (HH:MM)
                time_val = ""
                times = re.findall(r"\b\d{1,2}:\d{2}\b", text_lower)
                if times: 
                    time_val = times[0]
                else:
                    hm = re.search(r"\b(\d{1,2})h(\d{2})?\b", text_lower)
                    if hm:
                        h = int(hm.group(1))
                        m = int(hm.group(2)) if hm.group(2) else 0
                        time_val = f"{h:02d}:{m:02d}"
                    else:
                        now = datetime.now()
                        time_val = now.strftime("%H:%M")
                
                # Extract SL/TP (usually integers > 10)
                if sl == "0":
                    numbers = re.findall(r"\b\d{2,}\b", text_lower)
                    filtered_nums = []
                    for n in numbers:
                        if n not in time_val and n not in lot:
                            filtered_nums.append(n)
                    
                    if len(filtered_nums) >= 2:
                        sl, tp = filtered_nums[0], filtered_nums[1]
                    elif len(filtered_nums) == 1:
                        # If only one number, assume it's SL if "sl" in text, else TP
                        if "sl" in text_lower or "stop" in text_lower: sl = filtered_nums[0]
                        else: tp = filtered_nums[0]

                if symbol:
                    # Reconstruct into /pending command
                    new_cmd = f"/pending {t_type} {symbol} {lot} {time_val} {sl} {tp}"
                    # Check for profile name at the end
                    for p_name in cmd:
                        if p_name.lower() == profile_name.lower():
                            new_cmd += f" {profile_name}"
                            break
                    cmd = new_cmd.split()
                
            # 2. Check for Close intent
            elif any(kw in plain_text for kw in ["close", "dong", "nghi", "dung"]):
                time_val = ""
                times = re.findall(r"\b\d{1,2}:\d{2}\b", text_lower)
                if not times:
                    # Also match "HHhMM" format (e.g. "23h00")
                    times_h = re.findall(r"\b(\d{1,2})h(\d{2})\b", text_lower)
                    if times_h:
                        times = [f"{times_h[0][0]}:{times_h[0][1]}"]
                if times: time_val = times[0]
                
                # Check for profit/loss specific closing
                filter_type = "all"
                if any(kw in text_lower for kw in ["lời", "lãi", "profit"]): filter_type = "profit"
                elif any(kw in text_lower for kw in ["lỗ", "âm", "loss"]): filter_type = "loss"
                
                target_ticket = _extract_close_ticket(raw_text)
                target_sym = "" if target_ticket else _extract_close_symbol(raw_text)

                new_cmd = f"/closeall {time_val} filter={filter_type} sym={target_sym}"
                if target_ticket:
                    new_cmd += f" ticket={target_ticket}"
                if any(kw in text_lower for kw in ["mai", "ngày mai", "sáng mai", "tối mai"]):
                    tomorrow_dt = datetime.now() + timedelta(days=1)
                    new_cmd += f" date={tomorrow_dt.strftime('%Y-%m-%d')}"
                for p_name in cmd:
                    if p_name.lower() == profile_name.lower():
                        new_cmd += f" {profile_name}"
                        break
                cmd = new_cmd.split()
            
            # 3. Check for Status intent
            elif any(kw in text_lower for kw in ["trạng thái", "tài khoản", "status", "xem lệnh", "đang có", "check", "kiểm tra"]):
                new_cmd = "/status"
                for p_name in cmd:
                    if p_name.lower() == profile_name.lower():
                        new_cmd += f" {profile_name}"
                        break
                cmd = new_cmd.split()

            # 4. Check for Modification intent (SL/TP)
            elif any(kw in text_lower for kw in ["dời", "sửa", "đổi", "set", "modify"]):
                # Detect numbers (SL/TP points or price)
                nums = re.findall(r"\d+\.?\d*", text_lower)
                # Detect SL/TP keyword more precisely
                if any(kw in text_lower for kw in ["set sl", "cài sl", "đặt sl", "dời sl", "sl", "stop"]):
                    mod_type = "sl"
                else:
                    mod_type = "tp"
                
                val = nums[0] if nums else "0"
                
                # Detect Symbol
                symbol = ""
                for word in cmd:
                    w = word.upper().strip(",.!")
                    if any(s in w for s in ["XAU", "USD", "EUR", "GBP", "JPY", "GOLD"]):
                        symbol = w
                        break

                new_cmd = f"/modify {mod_type} {val} {symbol}"
                for p_name in cmd:
                    if p_name.lower() == profile_name.lower():
                        new_cmd += f" {profile_name}"
                        break
                cmd = new_cmd.split()

            # 5. Check for List/Help intent
            elif any(kw in text_lower for kw in ["list", "danh sách", "lệnh chờ", "đang chờ"]):
                cmd = ["/list"]
            elif any(kw in text_lower for kw in ["del", "xóa", "hủy", "remove"]):
                if "allticketclose" in text_lower or "all ticket close" in text_lower:
                    cmd = ["/del", "allticketclose"]
                elif "all" in text_lower:
                    cmd = ["/del", "all"]
                else:
                    # Try to find ID (4 digits)
                    ids = re.findall(r"\b\d{4}\b", text_lower)
                    if ids:
                        cmd = ["/del", ids[0]]
                    else:
                        cmd = ["/list"]
            elif any(kw in text_lower for kw in ["help", "giúp", "hướng dẫn"]):
                cmd = ["/help"]

        # 1. /pending <TYPE> <SYMBOL> <LOT> <TIME> [SL] [TP] [PROFILE]
        if cmd[0] == "/pending" and len(cmd) >= 5:
            try:
                pending_cmd = cmd[:]
                target_profile, pending_cmd = self._pop_profile_token(pending_cmd)
                if target_profile and target_profile != profile_lower:
                    return
                
                t_type_str = pending_cmd[1].upper()
                t_type = mt5.ORDER_TYPE_BUY if t_type_str == "BUY" else mt5.ORDER_TYPE_SELL
                symbol = pending_cmd[2].upper()
                lot = pending_cmd[3]
                time_val = pending_cmd[4]
                if time_val.startswith("@"):
                    time_val = _broker_clock_to_local_clock(
                        time_val[1:],
                        _live_broker_utc_offset(),
                        _local_utc_offset(),
                    )
                if len(time_val.split(":")) == 2: time_val += ":00"
                
                now_dt = datetime.now()
                target_dt = datetime.strptime(time_val, "%H:%M:%S").replace(year=now_dt.year, month=now_dt.month, day=now_dt.day)
                if target_dt < now_dt:
                    target_dt += timedelta(days=1)
                    while target_dt.weekday() in (5, 6):
                        target_dt += timedelta(days=1)
                time_val = target_dt.strftime("%H:%M:%S")
                target_date_str = target_dt.strftime("%Y-%m-%d")

                sl = pending_cmd[5] if len(pending_cmd) > 5 else "0"
                tp = pending_cmd[6] if len(pending_cmd) > 6 else "0"
                
                # Check if already holding this symbol or has a pending order for it
                # 1. Check open positions (Only fail if same symbol AND same direction)
                positions = mt5.positions_get(symbol=symbol)
                if positions:
                    for pos in positions:
                        if int(pos.type) == int(t_type):
                            self.notify(f"❌ [{profile_name}] Thất bại: Đang có lệnh mở cùng chiều cho {symbol}")
                            return

                # 2. Atomic append under file lock (multi-worker safe)
                created = {"trade": None, "dup": False}

                def _append_pending(trades):
                    active_pending = ("waiting", "executing", "limit_pending", "awaiting_fallback")
                    for t in trades:
                        if (
                            t.get("status") in active_pending
                            and t.get("symbol") == symbol
                            and int(t.get("type", -1)) == int(t_type)
                        ):
                            created["dup"] = True
                            return trades
                    # Unique id (avoid 4-digit collision across long-lived logs)
                    existing_ids = {t.get("id") for t in trades}
                    new_id = None
                    for _ in range(20):
                        cand = random.randint(10000, 99999)
                        if cand not in existing_ids:
                            new_id = cand
                            break
                    if new_id is None:
                        new_id = int(time.time() * 1000) % 100000000
                    new_trade = {
                        "symbol": symbol,
                        "type": int(t_type),
                        "lot": lot,
                        "sl": sl,
                        "tp": tp,
                        "time": time_val,
                        "date": target_date_str,
                        "status": "waiting",
                        "id": new_id,
                    }
                    trades.append(new_trade)
                    trades.sort(key=lambda x: x.get("time") or "")
                    created["trade"] = new_trade
                    return trades

                result = self._with_scheduled_file_lock(_append_pending)
                if result is None:
                    self.notify(f"❌ [{profile_name}] Thất bại: không khoá được file lệnh chờ (thử lại)")
                    return
                if created["dup"] or not created["trade"]:
                    self.notify(f"❌ [{profile_name}] Thất bại: Đã có lệnh chờ cùng chiều cho {symbol}")
                    return
                new_trade = created["trade"]
                
                # self.notify(f"🤖 [{profile_name}] Đã đặt lệnh ID:{new_trade['id']}: {t_type_str} {symbol} {lot} lúc {time_val}")
                
                # Determine time description (Today vs Tomorrow)
                time_desc = time_val
                if target_dt.date() > now_dt.date():
                    day_name = "ngày mai" if (target_dt.date() - now_dt.date()).days == 1 else f"ngày {target_dt.strftime('%d/%m')}"
                    time_desc = f"{time_val} {day_name} ({target_dt.strftime('%d/%m')})"

                resp = get_natural_response("order_placed", 
                                            type=t_type_str, 
                                            symbol=symbol, 
                                            lot=lot, 
                                            time=time_desc, 
                                            ticket_id=new_trade['id'])
                self.notify(f"🤖 [{profile_name}] {resp}")
                
                # Feedback if NLP was used
                if not text_lower.startswith("/"):
                    # self.notify(f"💡 [{profile_name}] Tôi đã hiểu ý bạn: {t_type_str} {symbol} {lot} @ {time_val}")
                    pass
            except Exception as e:
                self.notify(f"❌ [{profile_name}] Lệnh /pending lỗi: {e}")

        # 2. /closeall [TIME] [PROFILE] [filter=profit/loss] [sym=SYMBOL]
        elif cmd[0] == "/closeall":
            time_val = ""
            target_date = ""
            target_profile = ""
            filter_type = "all"
            target_sym = ""
            target_ticket = ""
            profile_names = self._get_profile_names()
            if not profile_names:
                profile_names = {"darwinex", "vantage", "th5ers"}
            for arg in cmd[1:]:
                if arg.startswith("date="):
                    target_date = arg.split("=", 1)[1]
                elif ":" in arg:
                    time_val = arg
                elif "filter=" in arg:
                    filter_type = arg.split("=")[1]
                elif "sym=" in arg:
                    target_sym = arg.split("=")[1]
                elif "ticket=" in arg:
                    target_ticket = arg.split("=")[1]
                elif arg in profile_names:
                    target_profile = arg.lower()
                else:
                    target_profile = arg.lower()
            
            if target_profile and target_profile != profile_lower:
                return

            if time_val:
                try:
                    if len(time_val.split(":")) == 2: time_val += ":00"
                    
                    if target_date:
                        target_dt = datetime.strptime(f"{target_date} {time_val}", "%Y-%m-%d %H:%M:%S")
                    else:
                        now_dt = datetime.now()
                        target_dt = datetime.strptime(time_val, "%H:%M:%S").replace(year=now_dt.year, month=now_dt.month, day=now_dt.day)
                        if target_dt < now_dt:
                            target_dt += timedelta(days=1)
                        while target_dt.weekday() in (5, 6):
                            target_dt += timedelta(days=1)
                    target_date_str = target_dt.strftime("%Y-%m-%d")

                    created = self._append_scheduled_close({
                        "time": time_val,
                        "date": target_date_str,
                        "filter": filter_type,
                        "sym": target_sym,
                        "ticket": target_ticket,
                    })
                    if created is None:
                        raise TimeoutError("scheduled close file is busy")
                    new_id = created["id"]
                    self.notify(f"🤖 [{profile_name}] Dạ anh, tôi đã ghi lịch ĐÓNG (ID: {new_id}, {filter_type}) cho {target_sym or 'tất cả'} lúc {time_val} rồi nhé!")
                except:
                    resp = get_natural_response("error", error="Sai định dạng giờ rồi anh ơi!")
                    self.notify(f"❌ [{profile_name}] {resp}")
            else:
                # Safety: if original text has a time pattern, never close immediately
                _time_in_text = re.findall(r"\b\d{1,2}:\d{2}\b", raw_text)
                if not _time_in_text:
                    _hm = re.findall(r"\b(\d{1,2})h(\d{2})\b", raw_text.lower())
                    if _hm:
                        _time_in_text = [f"{_hm[0][0]}:{_hm[0][1]}"]
                if _time_in_text:
                    recovered_time = _time_in_text[0]
                    try:
                        if len(recovered_time.split(":")) == 2:
                            recovered_time += ":00"
                        now_dt = datetime.now()
                        target_dt = datetime.strptime(recovered_time, "%H:%M:%S").replace(
                            year=now_dt.year, month=now_dt.month, day=now_dt.day
                        )
                        if target_dt < now_dt:
                            target_dt += timedelta(days=1)
                        while target_dt.weekday() in (5, 6):
                            target_dt += timedelta(days=1)
                        target_date_str = target_dt.strftime("%Y-%m-%d")
                        created = self._append_scheduled_close({
                            "time": recovered_time,
                            "date": target_date_str,
                            "filter": filter_type,
                            "sym": target_sym,
                            "ticket": target_ticket,
                        })
                        if created is None:
                            raise TimeoutError("scheduled close file is busy")
                        new_id = created["id"]
                        self.notify(
                            f"🤖 [{profile_name}] Dạ anh, tôi đã ghi lịch ĐÓNG (ID: {new_id}, {filter_type}) "
                            f"cho {target_sym or 'tất cả'} lúc {recovered_time} rồi nhé!"
                        )
                    except Exception:
                        self.notify(f"❌ [{profile_name}] Không parse được giờ từ tin nhắn, anh thử lại với định dạng HH:MM nhé!")
                else:
                    self.notify(f"🤖 [{profile_name}] Đã rõ! Tôi tiến hành ĐÓNG ({filter_type}) {target_sym or 'toàn bộ'} ngay lập tức đây ạ.")
                    self._execute_close_all(filter_type, target_sym, target_ticket)

        # 6. /list [PROFILE]
        elif cmd[0] in ["/list", "/danhsach"]:
            target_profile, _ = self._pop_profile_token(cmd[:])
            if target_profile and target_profile != profile_lower:
                return
            
            # 1. Scheduled Entry Trades
            header = get_natural_response("list_header")
            msg = f"📋 [{profile_name}] {header}\n"
            waiting_trades = [t for t in self.scheduled_trades if t.get("status") == "waiting"]
            
            if not waiting_trades:
                msg += "• (Trống)\n"
            else:
                for t in waiting_trades:
                    t_type = "BUY" if t["type"] == 0 else "SELL"
                    msg += f"• ID:{t.get('id','?')} | {t['symbol']} {t_type} {t['lot']} | {t['time']}\n"
            
            # 2. Partial Close Tasks
            msg += "\n✂️ LỆNH CHỐT LỜI TỪNG PHẦN (PARTIAL):\n"
            task_file = self.pending_partials_file
            partials_found = False
            if os.path.exists(task_file):
                try:
                    tasks = load_json(task_file)
                    for tid, task in tasks.items():
                        if task.get("profile") == profile_name:
                            partials_found = True
                            target_p = task.get("target_profit", 0)
                            vol = task.get("close_volume", 0)
                            
                            # Attempt to repair missing info
                            sym = task.get("symbol")
                            t_type = task.get("type")
                            if not sym or sym == "???":
                                positions = mt5.positions_get(ticket=int(tid))
                                if positions:
                                    sym = positions[0].symbol
                                    t_type = "BUY" if positions[0].type == mt5.POSITION_TYPE_BUY else "SELL"
                                    # Update task in file
                                    task["symbol"] = sym
                                    task["type"] = t_type
                                    tasks[tid] = task
                                    save_json(task_file, tasks)
                            
                            msg += f"• #{tid} ({sym or '???'} {t_type or '???'}): Lãi ${target_p:,.2f} chốt {vol} lot\n"
                except: pass
            
            if not partials_found:
                msg += "• (Trống)\n"
            
            # 3. Scheduled Close Tasks (from /closeall)
            msg += "\n⏰ LỆNH HẸN GIỜ ĐÓNG (CLOSEALL):\n"
            closes_found = False
            if hasattr(self, "_scheduled_close") and self._scheduled_close:
                for t in self._scheduled_close:
                    if isinstance(t, dict):
                        closes_found = True
                        t_id = t.get("id", "?")
                        t_time = t.get("time", "")
                        t_date = t.get("date", "")
                        t_filter = t.get("filter", "all")
                        t_sym = t.get("sym", "tất cả")
                        msg += f"• ID:{t_id} | Đóng ({t_filter}) {t_sym} | {t_time} ({t_date})\n"
            if not closes_found:
                msg += "• (Trống)\n"

            self.notify(msg)

        # 3. /status [PROFILE]
        elif cmd[0] in ["/status", "/check", "/kiemtra"]:
            target_profile, _ = self._pop_profile_token(cmd[:])
            if target_profile and target_profile != profile_lower:
                return
            
            status_msg = self._get_account_status()
            self.notify(status_msg)

        # 4. /modify <sl/tp> <val> <symbol> [PROFILE]
        elif cmd[0] == "/modify" and len(cmd) >= 3:
            try:
                mod_cmd = cmd[:]
                target_profile, mod_cmd = self._pop_profile_token(mod_cmd)
                if target_profile and target_profile != profile_lower:
                    return
                mod_type = mod_cmd[1]
                val = float(mod_cmd[2])
                target_sym = mod_cmd[3].upper() if len(mod_cmd) > 3 else ""
                self._modify_positions(mod_type, val, target_sym)
            except Exception as e:
                self.notify(f"❌ [{profile_name}] Lệnh /modify lỗi: {e}")

        # 5. /set <sl/tp> <val> [sym] (Global Modify)
        elif cmd[0] == "/set" and len(cmd) >= 3:
            try:
                mod_cmd = cmd[:]
                target_profile, mod_cmd = self._pop_profile_token(mod_cmd)
                if target_profile and target_profile != profile_lower:
                    return
                mod_type = mod_cmd[1] # sl or tp
                val = float(mod_cmd[2])
                target_sym = mod_cmd[3].upper() if len(mod_cmd) > 3 else ""
                self._modify_positions(mod_type, val, target_sym)
            except Exception as e:
                self.notify(f"❌ [{profile_name}] Lệnh /set lỗi: {e}")

        # 4. /del <ID1> [ID2] ... [IDn] [PROFILE] or /del all [PROFILE]
        elif cmd[0] == "/del" and len(cmd) >= 2:
            try:
                del_cmd = cmd[:]
                target_profile, del_cmd = self._pop_profile_token(del_cmd)
                if target_profile and target_profile != profile_lower:
                    return
                
                # Check for "allticketclose" keyword
                if del_cmd[1].lower() == "allticketclose":
                    # 1. Clear Partial Close tasks
                    task_file = self.pending_partials_file
                    deleted_partials = 0
                    if os.path.exists(task_file):
                        try:
                            tasks = load_json(task_file)
                            new_tasks = {}
                            for tid, task in tasks.items():
                                if task.get("profile") != profile_name:
                                    new_tasks[tid] = task
                                else:
                                    deleted_partials += 1
                            save_json(task_file, new_tasks)
                        except: pass
                    
                    # 2. Clear Scheduled Closes (keep fixed daily closes)
                    deleted_scheduled = self._remove_scheduled_closes(
                        lambda task: not (
                            isinstance(task, dict)
                            and (task.get("is_auto_daily") or task.get("sym") in ("XAUUSD", "GBP"))
                        )
                    ) or 0
                    
                    resp = get_natural_response("all_ticket_close_deleted", p_count=deleted_partials, s_count=deleted_scheduled)
                    self.notify(f"🗑️ [{profile_name}] {resp}")
                    return

                # Check for "all" keyword
                if del_cmd[1].lower() == "all":
                    # Xóa scheduled entry trades
                    count_entries = len(self.scheduled_trades)
                    self.scheduled_trades = []
                    save_json(self.scheduled_file, self.scheduled_trades)
                    # Xóa scheduled close tasks (trừ daily fixed schedule close)
                    count_closes = self._remove_scheduled_closes(
                        lambda task: not (
                            isinstance(task, dict)
                            and (task.get("is_auto_daily") or task.get("sym") in ("XAUUSD", "GBP"))
                        )
                    ) or 0
                    # Xóa lệnh canh chốt từng phần (price/profit partials) của profile này
                    count_partials = 0
                    task_file = self.pending_partials_file
                    if os.path.exists(task_file):
                        try:
                            tasks = load_json(task_file)
                            if isinstance(tasks, dict):
                                kept_partials = {}
                                for tid, task in tasks.items():
                                    if task.get("profile") != profile_name:
                                        kept_partials[tid] = task
                                    else:
                                        count_partials += 1
                                save_json(task_file, kept_partials)
                        except Exception:
                            pass
                    self.notify(
                        f"🤖 [{profile_name}] Đã xóa TẤT CẢ: "
                        f"{count_entries} hẹn giờ vào, {count_closes} hẹn giờ đóng, "
                        f"{count_partials} canh chốt từng phần!"
                    )
                    return

                # Collect all IDs to delete
                target_ids = []
                for arg in del_cmd[1:]:
                    try:
                        target_ids.append(int(arg))
                    except: pass
                
                if not target_ids:
                    return

                initial_count = len(self.scheduled_trades)
                self.scheduled_trades = [t for t in self.scheduled_trades if t.get("id") not in target_ids]
                deleted_count = initial_count - len(self.scheduled_trades)
                
                deleted_close_count = self._remove_scheduled_closes(
                    lambda task: isinstance(task, dict) and task.get("id") in target_ids
                ) or 0
                
                if deleted_count > 0 or deleted_close_count > 0:
                    if deleted_count > 0:
                        save_json(self.scheduled_file, self.scheduled_trades)
                    id_str = ", ".join(str(i) for i in target_ids)
                    # self.notify(f"🤖 [{profile_name}] Đã xóa lệnh ID: {id_str}")
                    resp = get_natural_response("order_deleted", ticket_id=id_str)
                    self.notify(f"🤖 [{profile_name}] {resp}")
                else:
                    # self.notify(f"❌ [{profile_name}] Không tìm thấy lệnh ID:{target_id}")
                    pass
            except Exception as e:
                self.notify(f"❌ [{profile_name}] Lệnh /del lỗi: {e}")

        # 5. /closeallpending [PROFILE]
        elif cmd[0] == "/closeallpending":
            target_profile, _ = self._pop_profile_token(cmd[:])
            if target_profile and target_profile != profile_lower:
                return
            
            count = len(self.scheduled_trades)
            self.scheduled_trades = []
            save_json(self.scheduled_file, self.scheduled_trades)
            self.notify(f"🤖 [{profile_name}] Đã xóa TẤT CẢ {count} lệnh chờ.")

        # 7. Partial Close Monitor: /partial <ticket> <profit> <volume>
        # NLP: "khi lệnh 12345 lãi 200 chốt 0.01"
        # Logic is handled in NLP block below, but we can have explicit command too.
        
        # --- NLP Parsing Logic ---
        if not text_lower.startswith("/"):
            # ... (Existing Buy/Sell Logic) ...
            
            # Check for Partial Close Intent
            # Keywords: "lệnh", "ticket", "lãi", "profit", "chốt", "close"
            # Regex: (lệnh|ticket)\s+(\d+).*?(lãi|lời|profit)\s+(\$?[\d\.]+).*?(chốt|close)\s+([\d\.]+)
            
            # Pattern 1: "lệnh 12345 lãi 200 chốt 0.01"
            # Pattern 2: "ticket 12345 profit 200 close 0.01"
            # Pattern 3: "khi lệnh 12345 đạt lợi nhuận $200, hãy chốt 0.01 lot"
            
            # --- Price-based partial (preferred for gold):
            # "Chốt XAUUSD 0.02 lot khi giá đạt 5000.00 (5000)"
            # "chốt vàng 0.01 khi giá 2650"
            price_partial = re.search(
                r"(?:chốt|close|cắt|lụm)\s+"
                r"([a-zA-Z]{3,12}\+?|vàng|gold)\s+"
                r"([\d.]+)\s*(?:lot)?"
                r".*?(?:khi\s+)?(?:giá|price|đạt|chạm)\s*(?:đạt|chạm|tới|tại)?\s*"
                r"([\d]+(?:[.,]\d+)?)",
                text_lower,
                re.I,
            )
            if price_partial:
                try:
                    raw_sym = price_partial.group(1)
                    sym_map = {"vàng": "XAUUSD", "vang": "XAUUSD", "gold": "XAUUSD"}
                    symbol_hint = sym_map.get(raw_sym.lower(), raw_sym.upper())
                    close_vol = float(price_partial.group(2))
                    price_str = price_partial.group(3).replace(",", ".")
                    target_price = float(price_str)
                    # Optional ($profit) in parens — ignored for trigger, price is source of truth
                    if target_price > 0 and close_vol > 0:
                        self._add_partial_close_task(
                            ticket_id=None,
                            target_profit=0,
                            close_vol=close_vol,
                            target_price=target_price,
                            symbol_hint=symbol_hint,
                        )
                        return
                except Exception as e:
                    print(f"Price partial NLP error: {e}")

            # Profit-based: "lệnh 12345 lãi 200 chốt 0.01"
            partial_pattern = (
                r"(?:lệnh|ticket|order)\s*#?(\d+).*?"
                r"(?:lãi|lời|profit|đạt|lên)\s*[\$]?\s*([\d,]+(?:\.\d+)?)\s*[\$]?.*?"
                r"(?:chốt|close|cắt|đóng|lụm|bỏ túi)\s*([\d\.]+)"
            )
            partial_match = re.search(partial_pattern, text_lower)
            
            if partial_match:
                try:
                    ticket_id = int(partial_match.group(1))
                    profit_str = partial_match.group(2).replace(",", "")
                    target_profit = float(profit_str)
                    close_vol = float(partial_match.group(3))
                    
                    if target_profit > 0 and close_vol > 0:
                        self._add_partial_close_task(ticket_id, target_profit, close_vol)
                        return
                except Exception:
                    pass

            # ... (Existing Buy/Sell Logic continues) ...


    def _execute_close_all(self, filter_type="all", target_sym="", target_ticket=""):
        positions = mt5.positions_get()
        if not positions: return
        
        magic = int(self.config.get("magic", 0))
        monitored_symbols = [s.strip().upper() for s in self.config.get("symbol", "").split(",") if s.strip()]
        
        count = 0
        target_ticket = str(target_ticket or "").strip()
        for pos in positions:
            # 1. Check magic
            if magic != -1 and pos.magic != magic: continue

            if target_ticket and str(pos.ticket) != target_ticket:
                continue
            
            # 2. Check symbol (monitored)
            is_monitored = False
            if not monitored_symbols:
                is_monitored = True
            else:
                pos_sym = pos.symbol.upper()
                for mon_sym in monitored_symbols:
                    if mon_sym in pos_sym:
                        is_monitored = True
                        break
            if not is_monitored: continue

            # 3. Check target symbol (filter)
            if target_sym:
                target_sym_upper = target_sym.upper()
                pos_sym_upper = pos.symbol.upper()
                if target_sym_upper not in pos_sym_upper: continue
                # Exact match for symbols with suffixes (like + or .)
                if ("+" in target_sym_upper or "." in target_sym_upper) and target_sym_upper != pos_sym_upper:
                    continue

            # 4. Check profit/loss filter
            if filter_type == "profit" and pos.profit <= 0: continue
            if filter_type == "loss" and pos.profit >= 0: continue
            
            self._direct_close(pos)
            count += 1
        
        if count > 0:
            # self.notify(f"✅ Closed {count} positions ({filter_type}) {target_sym} via Telegram.")
            resp = get_natural_response("close_all_success", count=count, filter=filter_type, symbol=target_sym or "tất cả")
            self.notify(f"✅ [{self.config.get('profile_name', 'Unknown')}] {resp}")

    def _get_account_status(self):
        profile_name = self.config.get("profile_name", "Unknown")
        acc = mt5.account_info()
        if not acc: return f"❌ [{profile_name}] Không thể kết nối MT5."
        
        positions = mt5.positions_get()
        pos_count = len(positions) if positions else 0
        total_profit = sum(p.profit for p in positions) if positions else 0.0
        
        header = get_natural_response("status_header")
        msg = (
            f"📊 [{profile_name}] {header}\n"
            f"• Số dư (Balance): {acc.balance:,.2f} {acc.currency}\n"
            f"• Tài sản (Equity): {acc.equity:,.2f}\n"
            f"• Lệnh đang mở: {pos_count}\n"
            f"• Tổng Profit: {total_profit:+.2f}\n"
        )
        
        if pos_count > 0:
            msg += "\nChi tiết:\n"
            # Group by symbol
            sym_stats = {}
            for p in positions:
                sym = p.symbol
                if sym not in sym_stats: sym_stats[sym] = {"count": 0, "profit": 0.0}
                sym_stats[sym]["count"] += 1
                sym_stats[sym]["profit"] += p.profit
            
            for sym, stat in sym_stats.items():
                msg += f"• {sym}: {stat['count']} lệnh ({stat['profit']:+.2f})\n"
        
        # 2. Scheduled Entry Trades (Waiting only)
        msg += "\n📋 DANH SÁCH LỆNH CHỜ:\n"
        waiting_trades = [t for t in self.scheduled_trades if t.get("status") == "waiting"]
        if not waiting_trades:
            msg += "• (Trống)\n"
        else:
            for t in waiting_trades:
                t_type = "BUY" if t["type"] == 0 else "SELL"
                msg += f"• ID:{t.get('id','?')} | {t['symbol']} {t_type} {t['lot']} | {t['time']}\n"

        # 3. Partial Close Tasks
        msg += "\n✂️ CHỐT LỜI TỪNG PHẦN (PARTIAL):\n"
        task_file = self.pending_partials_file
        partials_found = False
        if os.path.exists(task_file):
            try:
                tasks = load_json(task_file)
                for tid, task in tasks.items():
                    if task.get("profile") == profile_name:
                        partials_found = True
                        target_p = task.get("target_profit", 0)
                        vol = task.get("close_volume", 0)
                        # Attempt to repair missing info
                        sym = task.get("symbol")
                        t_type = task.get("type")
                        if not sym or sym == "???":
                            positions = mt5.positions_get()
                            if positions:
                                for p in positions:
                                    if p.ticket == int(tid):
                                        sym = p.symbol
                                        t_type = "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL"
                                        # Update task in file
                                        task["symbol"] = sym
                                        task["type"] = t_type
                                        tasks[tid] = task
                                        save_json(task_file, tasks)
                                        break
                        
                        msg += f"• #{tid} ({sym or '???'} {t_type or '???'}): Lãi ${target_p:,.2f} chốt {vol}\n"
            except Exception as e:
                log.warning("pending_partials read error: %s", e)
        if not partials_found: msg += "• (Không có)\n"

        return msg

    def _modify_positions(self, mod_type, val, target_sym=""):
        profile_name = self.config.get("profile_name", "Unknown")
        magic = int(self.config.get("magic", 0))
        sync_real = self.config.get("sync_real_sltp", True) # Get sync setting
        
        # 1. HANDLE POSITIONS (Open Trades)
        positions = mt5.positions_get()
        pos_list = list(positions) if positions else []
        
        # 2. HANDLE PENDING ORDERS (Limit/Stop Orders)
        orders = mt5.orders_get()
        ord_list = list(orders) if orders else []
        
        if not pos_list and not ord_list:
            self.notify(f"📋 [{profile_name}] Không có lệnh hay lệnh chờ nào để sửa.")
            return
            
        count = 0
        updated_details = []
        errors = []

        # --- PROCESS POSITIONS ---
        for pos in pos_list:
            # Filter Logic
            if target_sym:
                pos_sym_upper = pos.symbol.upper()
                target_sym_upper = target_sym.upper()
                if target_sym_upper not in pos_sym_upper: continue
                if ("+" in target_sym_upper or "." in target_sym_upper) and target_sym_upper != pos_sym_upper: continue
            
            if magic != -1 and pos.magic != magic: continue

            # --- VALUE INTERPRETATION (ALWAYS PRICE LEVEL) ---
            is_price_mode = True
            open_price = pos.price_open
            symbol_info = mt5.symbol_info(pos.symbol)
            if not symbol_info: continue
            
            point = symbol_info.point
            if val == -1.0 and mod_type == "sl":
                # Calculate Break Even Price with +10 points buffer
                be_offset_points = 10
                if pos.type == mt5.POSITION_TYPE_BUY:
                    current_val = open_price + (be_offset_points * point)
                else:
                    current_val = open_price - (be_offset_points * point)
                val_str = f"Hòa (BE +{be_offset_points}pts)"
                dist = abs(open_price - current_val)
                final_points = dist / point
            else:
                current_val = val
                val_str = str(val)
                dist = abs(open_price - val)
                final_points = dist / point
            
            # --- SYNC REAL SL/TP ---
            real_sl = pos.sl
            real_tp = pos.tp
            should_modify_real = False
            
            if mod_type == "sl":
                if abs(real_sl - current_val) > point:
                    real_sl = current_val
                    should_modify_real = True
            elif mod_type == "tp":
                if abs(real_tp - current_val) > point:
                    real_tp = current_val
                    should_modify_real = True
            
            success_this_pos = False
            if sync_real and should_modify_real:
                req = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": pos.ticket,
                    "symbol": pos.symbol,
                    "sl": round(real_sl, symbol_info.digits),
                    "tp": round(real_tp, symbol_info.digits)
                }
                # Fix for error 10030 or similar: Add missing fields if needed, though SLTP action usually doesn't need them.
                res = mt5.order_send(req)
                if res.retcode == mt5.TRADE_RETCODE_DONE:
                    success_this_pos = True
                else:
                    errors.append(f"#{pos.ticket}: {res.comment}")
            else:
                # Real SL/TP already at target, no sync requested, OR sync_real is OFF
                success_this_pos = True

            # --- UPDATE HIDDEN ONLY IF REAL SYNCED OR NO SYNC NEEDED/REQUESTED ---
            if success_this_pos:
                t_data = self.ticket_manager.get_ticket(pos.ticket)
                if mod_type == "sl": t_data["sl"] = final_points
                elif mod_type == "tp": t_data["tp"] = final_points
                self.ticket_manager.update_ticket(pos.ticket, **t_data)
                
                count += 1
                updated_details.append(f"#{pos.ticket}: {val_str}")

        # --- PROCESS PENDING ORDERS ---
        for ord in ord_list:
            # Filter Logic
            if target_sym:
                ord_sym_upper = ord.symbol.upper()
                target_sym_upper = target_sym.upper()
                if target_sym_upper not in ord_sym_upper: continue
                if ("+" in target_sym_upper or "." in target_sym_upper) and target_sym_upper != ord_sym_upper: continue
            
            if magic != -1 and ord.magic != magic: continue

            symbol_info = mt5.symbol_info(ord.symbol)
            if not symbol_info: continue
            
            point = symbol_info.point
            
            # For Pending Orders
            if val == -1.0: continue # Break even doesn't apply to pending orders
            real_sl = ord.sl
            real_tp = ord.tp
            if mod_type == "sl": real_sl = val
            elif mod_type == "tp": real_tp = val
            
            if sync_real:
                req = {
                    "action": mt5.TRADE_ACTION_MODIFY,
                    "order": ord.ticket,
                    "price": ord.price_open, # Price stays same
                    "sl": round(real_sl, symbol_info.digits),
                    "tp": round(real_tp, symbol_info.digits),
                    "type_time": ord.type_time,
                    "type_filling": ord.type_filling
                }
                res = mt5.order_send(req)
                if res.retcode == mt5.TRADE_RETCODE_DONE:
                    count += 1
                    updated_details.append(f"#{ord.ticket}: {val}")
                else:
                    errors.append(f"#{ord.ticket}: {res.comment}")
            else:
                # If sync_real is OFF, we don't modify pending orders on server
                # (Pending orders don't have a 'hidden' mode in this bot yet, 
                # they are always real on server)
                # But for consistency with user request:
                count += 1
                updated_details.append(f"#{ord.ticket}: {val} (Hidden only)")

        if count > 0:
            resp = get_natural_response("modify_success", 
                                        type=mod_type.upper(), 
                                        count=count, 
                                        symbol=target_sym or "tất cả", 
                                        val=val if val != -1.0 else "Hòa (BE)")
            msg = f"✅ [{profile_name}] {resp}\n📋 Chi tiết: {', '.join(updated_details)}"
            
            if errors:
                msg += f"\n⚠️ Cảnh báo: {len(errors)} lệnh lỗi MT5: {', '.join(errors)}"
            self.notify(msg)
        else:
            resp = get_natural_response("error", error=f"Không tìm thấy lệnh {target_sym or 'nào'} để sửa ạ.")
            msg = f"❌ [{profile_name}] {resp}"
            if errors:
                msg += f"\nLỗi MT5: {', '.join(errors)}"
            self.notify(msg)

    def _direct_close(self, pos):
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick: return False
        
        price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": pos.ticket,
            "price": price,
            "deviation": 20,
            "magic": pos.magic,
            "comment": "Telegram Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": get_filling_type(pos.symbol),
        }
        
        res = send_order_with_retry(request)
        
        # Update ticket manager for closed position
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            self.ticket_manager.update_ticket(pos.ticket, status="closed")
            return True
        return False

    def _process_master(self):
        # Get all open positions
        positions = mt5.positions_get()
        if positions is None: return

        data = {
            "updated": time.time(),
            "positions": []
        }
        
        for pos in positions:
            # We broadcast essential info
            # We use Ticket as unique ID. 
            data["positions"].append({
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "type": pos.type,
                "volume": pos.volume,
                "price_open": pos.price_open,
                "sl": pos.sl,
                "tp": pos.tp,
                "magic": pos.magic,
                "time": pos.time
            })
            
        # Write to shared file (atomic write preferred)
        temp_file = self.signal_file + ".tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(temp_file, self.signal_file)
            
            if not self.connected_logged:
                profile_name = self.config.get("profile_name", "Unknown")
                self.notify(f"[{profile_name}] {T('log_copy_connected_master')} {self.channel}")
                self.connected_logged = True
        except Exception as e:
            pass # Ignore write collisions

    def _process_slave(self):
        # Read signal file
        if not os.path.exists(self.signal_file): 
            self.connected_logged = False
            return
        
        # Check freshness - warn if master file is stale
        try:
            file_age = time.time() - os.path.getmtime(self.signal_file)
            if file_age > 60:
                if not hasattr(self, "_stale_warned") or time.time() - self._stale_warned > 300:
                    profile_name = self.config.get("profile_name", "Unknown")
                    self.notify(f"⚠️ [{profile_name}] Master signal file is {int(file_age)}s old. Master may be disconnected.")
                    self._stale_warned = time.time()
        except:
            pass
        
        try:
            with open(self.signal_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if not self.connected_logged:
                profile_name = self.config.get("profile_name", "Unknown")
                self.notify(f"[{profile_name}] {T('log_copy_connected_slave')} {self.channel}")
                self.connected_logged = True
        except:
            return # Read error

        # Check freshness (e.g. within 10 seconds? No, state-based is better)
        # If master stops updating, we shouldn't close everything immediately?
        # But if master closes a trade, it disappears from list.
        # So we trust the list.
        # Safety: Check timestamp. If > 30s old, Master might be dead. 
        # WARNING: If Master crashes, file remains with positions. Slave keeps them.
        # If Master closes trade and crashes before writing? Slave keeps them.
        # Risk: Master connection lost.
        # Let's just follow the file.
        
        positions = data.get("positions", [])
        if not isinstance(positions, list):
            positions = []
        master_positions = {p["ticket"]: p for p in positions if isinstance(p, dict) and "ticket" in p}
        
        # Parse ignore list
        ignore_str = self.config.get("copy_ignore_list", "")
        ignore_list = [s.strip().upper() for s in ignore_str.split(",") if s.strip()]
        
        # Pre-fetch Slave Positions for Max 1 Check
        slave_symbols_open = set()
        if self.max_one:
            slave_positions_list = mt5.positions_get()
            if slave_positions_list:
                 slave_symbols_open = set(p.symbol for p in slave_positions_list)
        
        # 1. Check for New Trades
        for ticket, m_pos in master_positions.items():
            s_ticket = str(ticket)
            if s_ticket not in self.mapping:
                # CHECK IGNORED
                if int(ticket) in self.ignored_tickets:
                    continue
                
                # Check Ignore Symbol List
                if m_pos["symbol"].upper() in ignore_list:
                    continue
                
                # Check Max 1 Trade Per Symbol
                if self.max_one:
                     target_sym = self._find_matching_symbol(m_pos["symbol"])
                     if target_sym and target_sym in slave_symbols_open:
                         continue
                    
                # NEW TRADE
                self._open_copy_trade(ticket, m_pos)
            else:
                # UPDATE SL/TP if needed?
                # User didn't explicitly ask for SL/TP sync, but it's good.
                # Let's skip for now to keep it simple and hidden.
                pass

        # 2. Check for Closed Trades
        # We iterate over OUR mapping. If mapped master ticket is NOT in master_positions, we close.
        # BUT we must ensure the master file is valid/recent? 
        # If master has 0 positions, list is empty.
        
        # Need a way to cleanup mapping if we manually closed the slave trade?
        # Check if slave trade still exists.
        
        # Snapshot of slave keys to avoid modification during iteration
        with self.mapping_lock:
            mapped_master_tickets = list(self.mapping.keys())
        
        for m_ticket in mapped_master_tickets:
            try:
                m_ticket_int = int(m_ticket)
            except:
                with self.mapping_lock:
                    del self.mapping[m_ticket]
                    save_json(self.local_map_file, self.mapping)
                continue
            # If Master Trade is GONE
            if m_ticket_int not in master_positions:
                # Close Slave Trade
                with self.mapping_lock:
                    slave_ticket = self.mapping[m_ticket]
                self._close_copy_trade(m_ticket, slave_ticket)

    def _safe_float(self, val, default=0.01):
        try:
            if not val: return default
            if isinstance(val, str):
                val = val.replace(",", ".")
            return float(val)
        except:
            return default

    def _get_step_decimals(self, step):
        try:
            step_str = f"{float(step):.10f}".rstrip("0").rstrip(".")
            if "." in step_str:
                return len(step_str.split(".")[1])
        except:
            return 2

    def test_safety_rules(self, symbol="EURUSD", lot=0.1, type="BUY"):
        """
        Test safety guardrails for a hypothetical trade
        Returns dict: {"allowed": bool, "reason": str}
        """
        profile_name = self.config.get("profile_name", "Test")
        reasons = []

        # 1. Check kill switch
        if self.kill_switch:
            reasons.append("Kill switch is ON")
            return {"allowed": False, "reason": "\n".join(reasons)}

        # 2. Check daily trade limit
        from datetime import date
        today = date.today()
        if self._daily_trade_date != today:
            self._daily_trade_date = today
            self._daily_trade_count = 0
        if self._daily_trade_count >= self.max_daily_trades:
            reasons.append(f"Daily limit reached: {self._daily_trade_count}/{self.max_daily_trades}")

        # 3. Check max lot per trade
        if lot > self.max_lot_per_trade:
            reasons.append(f"Lot {lot} exceeds max per trade: {self.max_lot_per_trade}")

        # 4. Check max exposure per symbol
        if self.max_exposure_per_symbol > 0:
            try:
                if mt5.terminal_info():
                    slave_positions_list = mt5.positions_get()
                    current_exposure = 0.0
                    if slave_positions_list:
                        current_exposure = sum(p.volume for p in slave_positions_list if p.symbol == symbol)
                    if current_exposure + lot > self.max_exposure_per_symbol:
                        reasons.append(f"Exposure would exceed max {self.max_exposure_per_symbol}: current {current_exposure} + {lot} = {current_exposure + lot}")
            except Exception as e:
                reasons.append(f"Could not check exposure (MT5 not connected?): {str(e)}")

        if reasons:
            return {"allowed": False, "reason": "\n".join(reasons)}
        else:
            return {"allowed": True, "reason": f"Trade would be allowed (symbol: {symbol}, lot: {lot}, type: {type})"}

    def _get_profile_names(self):
        try:
            if not hasattr(self, "_profile_cache"):
                self._profile_cache = {"mtime": 0, "names": set()}
            if os.path.exists(CONFIG_FILE):
                mtime = os.path.getmtime(CONFIG_FILE)
                if mtime != self._profile_cache.get("mtime"):
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    names = {str(k).lower() for k in data.keys()}
                    self._profile_cache = {"mtime": mtime, "names": names}
            return self._profile_cache.get("names", set())
        except:
            return set()

    def _looks_like_profile_token(self, token):
        """True if token is likely an intentional profile name (not symbol/lot/time/cmd)."""
        if not token:
            return False
        t = str(token).strip().lower()
        plain_t = _plain_command_text(t)
        if len(t) < 2:
            return False
        if re.fullmatch(r"\d+(\.\d+)?", t):
            return False
        if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", t):
            return False
        if re.fullmatch(r"\d{1,2}h\d{0,2}", t):
            return False
        if "=" in t or t.startswith("/"):
            return False
        skip = {
            "buy", "sell", "mua", "bán", "ban", "long", "short",
            "pending", "close", "closeall", "modify", "status", "list",
            "del", "help", "sl", "tp", "all", "profit", "loss", "lời", "lãi", "lỗ",
            "mai", "today", "tomorrow", "risk", "lot", "filter",
            "ngay", "b?y", "bay", "gi?", "gio", "t?t", "tat", "c?", "ca",
            "now",
        }
        if t in skip or plain_t in skip:
            return False
        u = t.upper()
        if any(s in u for s in ("USD", "JPY", "EUR", "GBP", "AUD", "CAD", "CHF", "NZD", "XAU", "GOLD")):
            return False
        if not re.search(r"[a-zA-Z]", t):
            return False
        return True

    def _resolve_target_profile(self, tokens):
        """Parse trailing profile token.

        Returns (matched_profile_lower, invalid_token, remaining_tokens).
        - matched: exact name in profiles.json (lowercase)
        - invalid: looks like a profile but NOT in the monitored list
        - remaining: tokens without the profile token (if any)
        """
        profile_names = self._get_profile_names()
        if not profile_names:
            profile_names = {"darwinex", "vantage", "th5ers"}
        if not tokens:
            return "", "", tokens
        last = str(tokens[-1]).strip()
        last_l = last.lower()
        if last_l in profile_names:
            return last_l, "", tokens[:-1]
        if self._looks_like_profile_token(last):
            return "", last, tokens[:-1]
        return "", "", tokens

    def _notify_invalid_profile(self, invalid_token):
        names = sorted(self._get_profile_names() or [])
        names_txt = ", ".join(names) if names else "(trống)"
        self.notify(
            f"❌ Profile không đúng: `{invalid_token}`.\n"
            f"Không có trong danh sách đang giám sát.\n"
            f"Profiles: {names_txt}"
        )

    def _pop_profile_token(self, tokens):
        """Pop exact profile match only. Invalid-looking names are NOT popped here
        (handled by gate so we can reject the whole command)."""
        matched, invalid, rest = self._resolve_target_profile(tokens)
        if invalid:
            # Keep token so gate can detect; do not treat as "no profile"
            return "", tokens
        if matched:
            return matched, rest
        return "", tokens

    def _calculate_lot(self, m_pos):
        # m_pos: master position dict
        try:
            # Get Slave Symbol for info
            raw_symbol = m_pos["symbol"]
            is_gold = "XAU" in raw_symbol.upper() or "GOLD" in raw_symbol.upper()
            symbol = self._find_matching_symbol(raw_symbol)
            if not symbol:
                return 0.01

            if self.lot_mode == "fixed":
                return self.lot_value
                
            elif self.lot_mode == "multiplier":
                try:
                    m_vol = float(m_pos["volume"])
                    val = m_vol * self.lot_value
                    return val # Will be rounded by volume_step later
                except:
                    return 0.01
                    
            elif self.lot_mode == "risk":
                # Risk % of Balance.
                # UPDATED v2.8.0: Use SL Points from SLAVE PROFILE CONFIG, not Master.
                
                # Get SL from Profile Config
                try:
                    sl_key = "gold_sl" if is_gold else "sl"
                    profile_sl = int(self.config.get(sl_key, 0))
                except:
                    profile_sl = 0
                    
                if profile_sl <= 0:
                    # If SL is not set in Profile, we cannot calculate risk lot. 
                    # Return 0.01 but maybe we should log this.
                    # self.notify(f"Risk mode error: SL points not set in Profile!")
                    return 0.01

                sl_points = float(profile_sl)
                
                # Get Account Balance
                acc = mt5.account_info()
                if not acc: return 0.01
                
                # Check Tick Value on SLAVE symbol
                symbol_info = mt5.symbol_info(symbol)
                if not symbol_info: return 0.01
                
                risk_amt = acc.balance * (self.lot_value / 100.0)
                
                tick_value = symbol_info.trade_tick_value
                tick_size = symbol_info.trade_tick_size
                if tick_size == 0 or tick_value == 0: return 0.01
                value_per_point = (tick_value / tick_size) * symbol_info.point
                if value_per_point <= 0: return 0.01
                
                val = risk_amt / (sl_points * value_per_point)
                return val
        except Exception as e:
            # print(f"Error calculating lot: {e}")
            return 0.01
        return 0.01

    def _with_scheduled_file_lock(self, fn, timeout=3.0):
        """Run fn(trades_list) under exclusive lock; persist if fn returns a list."""
        lock_path = f"{self.scheduled_file}.lock" if self.scheduled_file else "scheduled_trades.lock"
        with FileLock(lock_path, timeout=timeout) as lock:
            if lock is None:
                return None
            trades = load_json(self.scheduled_file, [])
            if not isinstance(trades, list):
                trades = []
            result = fn(trades)
            if isinstance(result, list):
                save_json(self.scheduled_file, result)
                self.scheduled_trades = result
                try:
                    self._last_scheduled_mtime = os.path.getmtime(self.scheduled_file)
                except Exception:
                    pass
                return result
            return result

    def _with_scheduled_close_file_lock(self, fn, timeout=3.0):
        """Reload, mutate, and persist scheduled closes under one profile lock."""
        close_file = getattr(self, "scheduled_close_file", "")
        lock_path = f"{close_file}.lock" if close_file else "scheduled_close.lock"
        with FileLock(lock_path, timeout=timeout) as lock:
            if lock is None:
                raise TimeoutError(f"scheduled close lock timed out: {lock_path}")
            closes = load_json(close_file, [])
            if not isinstance(closes, list):
                closes = []
            result = fn(closes)
            if isinstance(result, list):
                save_json(close_file, result)
                self._scheduled_close = result
            return result

    def _next_scheduled_close_id(self, closes):
        """Return an ID absent from entry and close schedules."""
        existing_ids = {task.get("id") for task in getattr(self, "scheduled_trades", [])}
        existing_ids.update(
            task.get("id") for task in closes if isinstance(task, dict) and task.get("id")
        )
        for _ in range(20):
            candidate = random.randint(10000, 99999)
            if candidate not in existing_ids:
                return candidate
        return int(time.time() * 1000) % 100000000

    def _append_scheduled_close(self, payload):
        """Append one close task transactionally and return its persisted record."""
        created = {"task": None}

        def append(closes):
            task = {"id": self._next_scheduled_close_id(closes), **payload}
            closes.append(task)
            created["task"] = task
            return closes

        result = self._with_scheduled_close_file_lock(append)
        return created["task"] if result is not None else None

    def _remove_scheduled_closes(self, should_remove):
        """Remove matching close tasks transactionally and return their count."""
        removed = {"count": 0}

        def remove(closes):
            kept = [task for task in closes if not should_remove(task)]
            removed["count"] = len(closes) - len(kept)
            return kept

        result = self._with_scheduled_close_file_lock(remove)
        return removed["count"] if result is not None else None

    def _ensure_scheduled_closes(self, planned_tasks):
        """Persist missing planned close tasks in one transaction."""
        added = []

        def ensure(closes):
            keys = {
                (task.get("sym"), task.get("date"), task.get("time"))
                for task in closes if isinstance(task, dict)
            }
            for planned in planned_tasks:
                key = (planned.get("sym"), planned.get("date"), planned.get("time"))
                if planned.get("_skip") or key in keys:
                    continue
                task = {key: value for key, value in planned.items() if key != "_skip"}
                task["id"] = self._next_scheduled_close_id(closes)
                closes.append(task)
                added.append(task)
                keys.add(key)
            return closes

        result = self._with_scheduled_close_file_lock(ensure)
        return added if result is not None else None

    def _claim_scheduled_trade(self, trade_id, stale_executing_sec=45):
        """Atomically claim one scheduled trade so only one worker executes it.

        Returns claimed trade dict, or None if another worker already claimed it.
        Stale 'executing' claims older than stale_executing_sec are reclaimed
        (crash recovery).
        """
        if trade_id is None:
            return None
        claimed_holder = {"trade": None}
        now_ts = time.time()

        def _claim(trades):
            for t in trades:
                if t.get("id") != trade_id:
                    continue
                st = t.get("status", "waiting")
                if st == "executing":
                    claimed_at = float(t.get("claimed_at") or 0)
                    if claimed_at and (now_ts - claimed_at) < stale_executing_sec:
                        return trades  # still in progress elsewhere
                    # stale → reclaim
                elif st not in ("waiting", "limit_pending", "awaiting_fallback"):
                    return trades
                t["status"] = "executing"
                t["claimed_by"] = os.getpid()
                t["claimed_at"] = now_ts
                claimed_holder["trade"] = dict(t)
                return trades
            return trades

        self._with_scheduled_file_lock(_claim)
        return claimed_holder["trade"]

    def _finalize_scheduled_trade(self, trade_id, status="executed"):
        """Persist final status after claim/execute."""
        if trade_id is None:
            return

        def _fin(trades):
            for t in trades:
                if t.get("id") == trade_id:
                    t["status"] = status
                    t.pop("claimed_by", None)
                    t.pop("claimed_at", None)
                    break
            return trades

        self._with_scheduled_file_lock(_fin)

    def _auto_schedule_daily_closes(self):
        """Auto-schedule daily closes for XAUUSD and GBP if they are not already scheduled for today."""
        now_dt = datetime.now()
        now_date = now_dt.strftime("%Y-%m-%d")
        
        # Guard to only attempt scheduling once per calendar day
        if getattr(self, "_last_auto_close_date", None) == now_date:
            return
        
        # We need to get the broker's current date to know if it's a weekday for the broker
        try:
            tick = mt5.symbol_info_tick("XAUUSD")
            if tick is not None:
                # tick.time is broker time timestamp; time.time() is UTC timestamp
                broker_gmt = round((tick.time - time.time()) / 3600.0)
                # If calculated offset is unrealistic (e.g. stale tick on weekends), fallback to GMT+3
                if not (-12 <= broker_gmt <= 14):
                    broker_gmt = 3
            else:
                broker_gmt = 3
        except Exception:
            broker_gmt = 3

        broker_now = datetime.utcnow() + timedelta(hours=broker_gmt)
        broker_date = broker_now.date()
        
        if broker_now.weekday() >= 5:
            self._last_auto_close_date = now_date
            return

        xau_broker_time_str = "14:44:00" if broker_now.weekday() == 0 else "17:44:00"
        gbp_broker_time_str = "19:44:00"
        
        try:
            local_dt = datetime.now()
            utc_dt = datetime.utcnow()
            local_gmt = round((local_dt - utc_dt).total_seconds() / 3600.0)
        except Exception:
            local_gmt = 7
            
        offset_hours = broker_gmt - local_gmt
        
        xau_broker_dt = datetime.combine(broker_date, datetime.strptime(xau_broker_time_str, "%H:%M:%S").time())
        xau_local_dt = xau_broker_dt - timedelta(hours=offset_hours)
        
        gbp_broker_dt = datetime.combine(broker_date, datetime.strptime(gbp_broker_time_str, "%H:%M:%S").time())
        gbp_local_dt = gbp_broker_dt - timedelta(hours=offset_hours)
        
        xau_local_date_str = xau_local_dt.strftime("%Y-%m-%d")
        xau_local_time_str = xau_local_dt.strftime("%H:%M:%S")
        
        gbp_local_date_str = gbp_local_dt.strftime("%Y-%m-%d")
        gbp_local_time_str = gbp_local_dt.strftime("%H:%M:%S")

        planned = [
            {
                "time": xau_local_time_str,
                "date": xau_local_date_str,
                "filter": "all",
                "sym": "XAUUSD",
                "ticket": "",
                "is_auto_daily": True,
                "_skip": xau_local_dt < now_dt,
            },
            {
                "time": gbp_local_time_str,
                "date": gbp_local_date_str,
                "filter": "all",
                "sym": "GBP",
                "ticket": "",
                "is_auto_daily": True,
                "_skip": gbp_local_dt < now_dt,
            },
        ]
        added = self._ensure_scheduled_closes(planned)
        if added is None:
            return

        self._last_auto_close_date = now_date
        added_by_symbol = {task["sym"]: task for task in added}
        xau_scheduled = "XAUUSD" not in added_by_symbol
        gbp_scheduled = "GBP" not in added_by_symbol
        profile_name = self.config.get("profile_name", "Unknown")
        if not xau_scheduled:
            new_id = added_by_symbol["XAUUSD"]["id"]
            self.notify(
                f"🤖 [{profile_name}] Tự động hẹn giờ ĐÓNG XAUUSD (ID: {new_id}) "
                f"lúc {xau_local_time_str} ({xau_local_date_str}) [Broker: {xau_broker_time_str}]."
            )

        if not gbp_scheduled:
            new_id = added_by_symbol["GBP"]["id"]
            self.notify(
                f"🤖 [{profile_name}] Tự động hẹn giờ ĐÓNG GBP (ID: {new_id}) "
                f"lúc {gbp_local_time_str} ({gbp_local_date_str}) [Broker: {gbp_broker_time_str}]."
            )
            
    def _check_scheduled_trades(self):
        self._auto_schedule_daily_closes()
        if not self.scheduled_trades and not getattr(self, "_scheduled_close", None): return

        now_dt = datetime.now()
        now_time = now_dt.strftime("%H:%M:%S")
        now_date = now_dt.strftime("%Y-%m-%d")
        
        # Snapshot list — claim/finalize mutate disk; avoid double-fire mid-loop
        trades_snapshot = list(self.scheduled_trades)
        
        # Check normal scheduled trades
        for trade in trades_snapshot:
            status = trade.get("status", "waiting")
            if status in ["waiting", "limit_pending", "awaiting_fallback", "executing"]:
                # executing only considered if stale (handled inside claim)
                if status == "executing":
                    claimed_at = float(trade.get("claimed_at") or 0)
                    if claimed_at and (time.time() - claimed_at) < 45:
                        continue
                # Check Date
                trade_date = trade.get("date", now_date) # Default to today if missing
                
                # If future date, skip
                if trade_date > now_date:
                    continue
                    
                # If today, check time
                t_time = trade.get("time", "00:00:00")
                # Normalize t_time for comparison (handle 6:00:00 vs 06:00:00)
                try:
                    if len(t_time.split(":")) == 2: t_time += ":00"
                    t_dt = datetime.strptime(t_time, "%H:%M:%S")
                    t_time_norm = t_dt.strftime("%H:%M:%S")
                    # Update normalized time back to trade to fix legacy data
                    if t_time != t_time_norm:
                        trade["time"] = t_time_norm
                except:
                    t_time_norm = t_time # Fallback

                try:
                    trade_full_dt = datetime.strptime(f"{trade_date} {t_time_norm}", "%Y-%m-%d %H:%M:%S")
                    # Execute 2s early for better entry price
                    trade_full_dt -= timedelta(seconds=2)
                    t_time_norm = trade_full_dt.strftime("%H:%M:%S")
                except:
                    trade_full_dt = None

                # Check if EXPIRED (More than 10 mins late)
                is_expired = False
                try:
                    # Construct full datetime for trade
                    trade_dt_str = f"{trade_date} {t_time_norm}"
                    trade_full_dt = datetime.strptime(trade_dt_str, "%Y-%m-%d %H:%M:%S")
                    
                    # If trade is in the past by > 10 mins, mark as expired
                    if (now_dt - trade_full_dt).total_seconds() > 600: # 10 mins
                        is_expired = True
                except: pass

                if is_expired:
                    self._finalize_scheduled_trade(trade.get("id"), "expired")
                    profile_name = self.config.get("profile_name", "Unknown")
                    self.notify(f"⚠️ [{profile_name}] Scheduled Order Expired: {trade.get('symbol')} at {t_time_norm} (skipped > 10m late)")
                    continue

                if trade_date == now_date and t_time_norm > now_time:
                    continue

                # Atomic claim BEFORE execute — only one worker may win
                claimed = self._claim_scheduled_trade(trade.get("id"))
                if not claimed:
                    continue

                try:
                    self._execute_scheduled(claimed)
                finally:
                    # Always finalize so other workers never re-fire
                    self._finalize_scheduled_trade(claimed.get("id"), "executed")

        # Check scheduled close all (atomic pop under lock to avoid multi-worker double close)
        if hasattr(self, "_scheduled_close") and self._scheduled_close:
            due_batch = []

            def pop_due(closes):
                remaining_closes = []
                for close_info in closes:
                    if isinstance(close_info, dict):
                        c_time = close_info.get("time", "00:00:00")
                        c_date = close_info.get("date", now_date)
                        c_filter = close_info.get("filter", "all")
                        c_sym = close_info.get("sym", "")
                        c_ticket = close_info.get("ticket", "")
                    else:
                        c_time, c_date = close_info, now_date
                        c_filter, c_sym, c_ticket = "all", "", ""
                    if c_date > now_date:
                        remaining_closes.append(close_info)
                        continue
                    c_time_norm = c_time
                    try:
                        if len(str(c_time).split(":")) == 2:
                            c_time = f"{c_time}:00"
                        c_time_norm = datetime.strptime(c_time, "%H:%M:%S").strftime("%H:%M:%S")
                    except Exception:
                        pass
                    if c_date == now_date and c_time_norm > now_time:
                        remaining_closes.append(close_info)
                        continue
                    due_batch.append({"filter": c_filter, "sym": c_sym, "ticket": c_ticket})
                return remaining_closes

            self._with_scheduled_close_file_lock(pop_due)
            profile_name = self.config.get("profile_name", "Unknown")
            for item in due_batch:
                self.notify(
                    f"⏰ [{profile_name}] Scheduled Time Reached: "
                    f"Closing Positions ({item['filter']}) {item['sym'] or item.get('ticket', '')}"
                )
                self._execute_close_all(item["filter"], item["sym"], item.get("ticket", ""))







    def _get_m5_open_price(self, symbol, ref_dt):
        try:
            mt5.symbol_select(symbol, True)
        except:
            pass

        rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M5, ref_dt, 1)
        if rates is None or len(rates) == 0:
            return None
        try:
            return float(rates[0]["open"])
        except Exception:
            try:
                return float(rates[0].open)
            except Exception:
                return None

    def _get_trade_status_detail(self, trade):
        override = trade.get("_status_detail_override")
        if override:
            return override

        status = str(trade.get("status", "waiting") or "waiting").lower()
        return status

    def _get_trade_next_action(self, trade):
        override = trade.get("_next_action_override")
        if override:
            return override

        status = str(trade.get("status", "waiting") or "waiting").lower()
        trigger_time = trade.get("trigger_time") or trade.get("time") or ""
        next_stage_time = trade.get("next_stage_time") or ""
        cancel_limit_time = trade.get("cancel_limit_time") or ""
        fallback_time = trade.get("fallback_time") or ""

        if status == "waiting":
            return f"Execute {trade.get('time', '')}".strip()
        if status == "executed":
            return "Done"
        return "-"

    def _calc_scheduled_sl_tp(self, symbol, order_type, entry_price, sl_points, tp_points):
        info = mt5.symbol_info(symbol)
        if not info:
            return 0.0, 0.0

        point = info.point
        sl = 0.0
        tp = 0.0
        if sl_points > 0:
            sl = entry_price - (sl_points * point) if order_type == mt5.ORDER_TYPE_BUY else entry_price + (sl_points * point)
        if tp_points > 0:
            tp = entry_price + (tp_points * point) if order_type == mt5.ORDER_TYPE_BUY else entry_price - (tp_points * point)
        return sl, tp

    def _prepare_scheduled_trade(self, trade, order_type_override=None):
        symbol = trade["symbol"]
        # Coerce type: JSON may load int; never compare str vs pos.type
        raw_type = trade["type"] if order_type_override is None else order_type_override
        try:
            order_type = int(raw_type)
        except (TypeError, ValueError):
            return "fail"
        profile_name = self.config.get("profile_name", "Unknown")

        if not mt5.terminal_info():
            return "fail"

        positions = mt5.positions_get(symbol=symbol)
        if positions:
            for pos in positions:
                if int(pos.type) == order_type:
                    self.notify(f"⚠️ [{profile_name}] Skipped Scheduled {symbol}: Position already exists")
                    return "skip"

        opp_type = mt5.POSITION_TYPE_SELL if order_type == mt5.ORDER_TYPE_BUY else mt5.POSITION_TYPE_BUY
        closed_cnt = 0
        if positions:
            for pos in positions:
                if int(pos.type) == int(opp_type):
                    if self._direct_close(pos):
                        self.notify(f"🔄 [{profile_name}] Auto Closed opposite {symbol} (Ticket: {pos.ticket}) for scheduled {trade.get('id')}")
                        closed_cnt += 1
                    else:
                        self.notify(f"⚠️ [{profile_name}] Failed to close opposite {symbol} (Ticket: {pos.ticket})")

        if order_type == mt5.ORDER_TYPE_BUY:
            opp_pending_types = [mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP, mt5.ORDER_TYPE_SELL_STOP_LIMIT]
        else:
            opp_pending_types = [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_BUY_STOP_LIMIT]

        pending_orders = mt5.orders_get(symbol=symbol)
        if pending_orders:
            for o in pending_orders:
                if o.type in opp_pending_types:
                    request_del = {"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket}
                    res_del = mt5.order_send(request_del)
                    if res_del.retcode == mt5.TRADE_RETCODE_DONE:
                        self.notify(f"🗑️ [{profile_name}] Auto Removed opposite pending {symbol} (Ticket: {o.ticket}) for scheduled {trade.get('id')}")
                    else:
                        self.notify(f"⚠️ [{profile_name}] Failed to remove pending {o.ticket}: {res_del.comment}")

        if closed_cnt > 0:
            for _ in range(20):
                time.sleep(0.1)
                pos_check = mt5.positions_get(symbol=symbol)
                still_exists = False
                if pos_check:
                    for p in pos_check:
                        if p.type == opp_type:
                            still_exists = True
                            break
                if not still_exists:
                    break

        return "ok"

    def _remove_pending_order(self, ticket):
        if not ticket:
            return True
        try:
            res = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": int(ticket)})
            return res.retcode == mt5.TRADE_RETCODE_DONE
        except Exception:
            return False

    def _send_scheduled_market_order(self, trade, comment="Scheduled Order", order_type_override=None):
        symbol = trade["symbol"]
        raw_type = trade["type"] if order_type_override is None else order_type_override
        try:
            order_type = int(raw_type)
        except (TypeError, ValueError):
            return "fail"
        try:
            lot = float(trade["lot"])
            if lot <= 0:
                return "fail"
        except (TypeError, ValueError):
            return "fail"
        sl_points = float(trade.get("sl", 0) or 0)
        tp_points = float(trade.get("tp", 0) or 0)
        profile_name = self.config.get("profile_name", "Unknown")

        prep = self._prepare_scheduled_trade(trade, order_type_override=order_type)
        if prep == "skip":
            return "skip"
        if prep != "ok":
            return "fail"

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            mt5.symbol_select(symbol, True)
            tick = mt5.symbol_info_tick(symbol)
        if not tick:
            self.notify(f"❌ [{profile_name}] Failed Scheduled {symbol}: Symbol not found or Market closed")
            return "fail"

        # Final same-direction guard right before send (close/fill race window)
        positions = mt5.positions_get(symbol=symbol)
        if positions:
            for pos in positions:
                if int(pos.type) == order_type:
                    self.notify(f"⚠️ [{profile_name}] Skipped Scheduled {symbol}: Position already exists (pre-send)")
                    return "skip"

        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        sl, tp = self._calc_scheduled_sl_tp(symbol, order_type, price, sl_points, tp_points)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "magic": int(self.config.get("magic", 0)),
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": get_filling_type(symbol),
        }

        res = send_order_with_retry(request)

        if res.retcode == mt5.TRADE_RETCODE_DONE:
            direction_str = "BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL"
            self.notify(f"✅ [{profile_name}] Executed Scheduled {direction_str} {symbol} {lot} lot")
            return "done"

        self.notify(f"❌ [{profile_name}] Failed Scheduled {symbol}: {res.comment}")
        return "fail"

    def _execute_scheduled(self, trade):
        self._send_scheduled_market_order(trade, comment="Scheduled Order")

    def _find_matching_symbol(self, m_symbol):
        """Find corresponding symbol on Slave (handles prefix/suffix)."""
        # 1. Exact Match
        if mt5.symbol_info(m_symbol):
            return m_symbol

        # 2. Specific Mappings (Gold)
        if "XAU" in m_symbol or "GOLD" in m_symbol:
            # Priority list for Gold
            gold_variants = ["XAUUSD", "GOLD", "XAUUSD.m", "GOLD.m", "XAUUSD+", "GOLD+", "XAUUSD.pro", "GOLD.pro"]
            for v in gold_variants:
                if mt5.symbol_info(v): return v
        
        # 3. Fuzzy Match (Containment)
        # Get all symbols (Warning: Can be slow if thousands, but done only on entry)
        all_syms = mt5.symbols_get()
        if not all_syms: return None
        
        candidates = []
        for s in all_syms:
            s_name = s.name
            # Check mutual containment
            if m_symbol in s_name or s_name in m_symbol:
                candidates.append(s_name)
        
        if candidates:
            # Sort by: 1. Selected in Market Watch, 2. Length difference
            def sort_key(name):
                info = mt5.symbol_info(name)
                is_selected = info.select if info else False
                len_diff = abs(len(name) - len(m_symbol))
                return (not is_selected, len_diff) # Selected first
            
            candidates.sort(key=sort_key)
            return candidates[0]
            
        return None

    def _open_copy_trade(self, m_ticket, m_pos):
        raw_symbol = m_pos["symbol"]
        symbol = self._find_matching_symbol(raw_symbol)
        profile_name = self.config.get("profile_name", "Unknown")

        if not symbol:
            self.notify(f"[{profile_name}] Symbol mismatch! Master: {raw_symbol} -> Slave: ???")
            return

        # SAFETY: Kill switch
        if self.kill_switch:
            self.notify(f"[{profile_name}] Kill switch ON - trade skipped: {symbol}")
            return

        # SAFETY: Daily trade limit
        from datetime import date
        today = date.today()
        if self._daily_trade_date != today:
            self._daily_trade_date = today
            self._daily_trade_count = 0
        if self._daily_trade_count >= self.max_daily_trades:
            self.notify(f"[{profile_name}] Daily limit ({self.max_daily_trades}) reached - trade skipped: {symbol}")
            return

        # SAFETY: Stale signal check
        if os.path.exists(self.signal_file):
            try:
                mtime = os.path.getmtime(self.signal_file)
                age = time.time() - mtime
                if age > self.stale_threshold_sec:
                    self.notify(f"[{profile_name}] Signal stale ({int(age)}s) - trade skipped: {symbol}")
                    return
            except Exception:
                pass
            
        # STEALTH: Delay (reduced to minimize process blocking)
        if self.stealth:
            delay = random.uniform(0.3, 1.5)
            time.sleep(delay)
            
        # Calc Lot
        lot = self._calculate_lot(m_pos)

        # SAFETY: Max lot per trade
        if lot > self.max_lot_per_trade:
            self.notify(f"[{profile_name}] Lot {lot} exceeds max {self.max_lot_per_trade} - capped: {symbol}")
            lot = self.max_lot_per_trade

        # SAFETY: Max exposure per symbol
        if self.max_exposure_per_symbol > 0:
            slave_positions_list = mt5.positions_get()
            if slave_positions_list:
                current_exposure = sum(p.volume for p in slave_positions_list if p.symbol == symbol)
                if current_exposure + lot > self.max_exposure_per_symbol:
                    self.notify(f"[{profile_name}] Exposure {current_exposure + lot} exceeds max {self.max_exposure_per_symbol} - skipped: {symbol}")
                    return

        # Check Min/Max Lot
        sym_info = mt5.symbol_info(symbol)
        if not sym_info:
            self.notify(f"[{profile_name}] {T('log_copy_err')} Symbol info not found for {symbol}")
            return
            
        if lot < sym_info.volume_min: 
            # If calculated lot is too small, use min lot
            lot = sym_info.volume_min
            
        if lot > sym_info.volume_max: 
            lot = sym_info.volume_max
            
        # Step rounding
        if sym_info.volume_step > 0:
            lot = round(lot / sym_info.volume_step) * sym_info.volume_step
            decimals = self._get_step_decimals(sym_info.volume_step)
            lot = round(lot, decimals)
            if lot < sym_info.volume_min: lot = sym_info.volume_min
            
        # Send Order
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return
        
        price = tick.ask if m_pos["type"] == 0 else tick.bid
        cmd = mt5.ORDER_TYPE_BUY if m_pos["type"] == 0 else mt5.ORDER_TYPE_SELL
        
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": cmd,
            "price": price,
            "deviation": 20,
            "magic": int(self.config.get("magic", 0)), # Use Profile Magic so it gets managed
            "comment": "", # STEALTH: No comment
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": get_filling_type(symbol),
        }
        
        try:
            is_gold = "XAU" in symbol.upper() or "GOLD" in symbol.upper()
            sl_key = "gold_sl" if is_gold else "sl"
            tp_key = "gold_tp" if is_gold else "tp"
            sl_points = int(self.config.get(sl_key, 0))
            tp_points = int(self.config.get(tp_key, 0))
            
            sl_price = 0.0
            tp_price = 0.0
            point = sym_info.point
            
            if sl_points > 0:
                if cmd == mt5.ORDER_TYPE_BUY:
                    sl_price = price - sl_points * point
                else:
                    sl_price = price + sl_points * point
                    
            if tp_points > 0:
                if cmd == mt5.ORDER_TYPE_BUY:
                    tp_price = price + tp_points * point
                else:
                    tp_price = price - tp_points * point

            req["sl"] = sl_price
            req["tp"] = tp_price
            
            if sl_points > 0:
                self.notify(f"🛡️ [{profile_name}] Safety SL applied: {sl_points} pts")
        except:
            pass
        
        res = send_order_with_retry(req)
        
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            # Save Mapping
            with self.mapping_lock:
                self.mapping[str(m_ticket)] = res.order # res.order is the ticket
                save_json(self.local_map_file, self.mapping)

            self._daily_trade_count += 1
            msg = f"[{profile_name}] Copied {symbol} | Vol {lot} | Origin {m_ticket}"
            self.notify(msg)
            winsound.Beep(1000, 100)
        else:
            self.notify(f"[{profile_name}] Copy failed {symbol} | {res.comment}")

    def _close_copy_trade(self, m_ticket, s_ticket):
        # Check if slave position exists
        positions = mt5.positions_get(ticket=s_ticket)
        profile_name = self.config.get("profile_name", "Unknown")
        
        if not positions:
            # Already closed manually?
            with self.mapping_lock:
                del self.mapping[str(m_ticket)]
                save_json(self.local_map_file, self.mapping)
            return
            
        pos = positions[0]
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick: return
        
        # STEALTH: Delay (reduced to minimize process blocking)
        if self.stealth:
            time.sleep(random.uniform(0.2, 1.0))
            
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume, # Close all
            "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": pos.ticket,
            "price": tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask,
            "deviation": 20,
            "magic": pos.magic,
            "comment": "",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": get_filling_type(pos.symbol),
        }
        
        res = send_order_with_retry(req)
        
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            with self.mapping_lock:
                del self.mapping[str(m_ticket)]
                save_json(self.local_map_file, self.mapping)
            msg = f"[{profile_name}] {T('log_copy_close')} {pos.symbol} | {pos.volume}"
            self.notify(msg)
        else:
            self.notify(f"[{profile_name}] {T('log_copy_err')} Close {s_ticket} | {res.comment}")
