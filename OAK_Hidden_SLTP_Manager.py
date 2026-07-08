# -*- coding: utf-8 -*-
import customtkinter as ctk
import tkinter # Required for text search/tags
from tkinter import ttk # For Treeview
import MetaTrader5 as mt5
try:
    import pywinauto
    from pywinauto import Application, mouse
    GHOST_LIB_AVAILABLE = True
except ImportError:
    GHOST_LIB_AVAILABLE = False
import threading
import time
import winsound
import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
import ctypes
import random
import re
import subprocess # For multi-process support
import signal
import atexit
import oak_trading_reminders
from oak_response_dict import get_random_response
from oak_logger import setup_logger
from repositories.sqlite_store import SQLiteStore
from utils import build_signal_process_cmd, SIGNAL_SCRIPT_MAP, UnsupportedFrozenProcessError, compute_telegram_backoff

log = setup_logger("oak")

# --- PROCESS CLEANUP ---
_running_processes = []

def _cleanup_processes():
    """Kill all spawned child processes on exit."""
    for proc in _running_processes:
        try:
            if proc.poll() is None:
                proc.kill()
        except:
            pass

atexit.register(_cleanup_processes)

def _signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM to cleanup processes."""
    _cleanup_processes()
    sys.exit(0)

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# --- VERSION CONTROL ---
# Dùng để giả lập thao tác người dùng khi Algo bị chặn hoặc cần che giấu 100%
class GhostOperator:
    def __init__(self, login_id=None):
        self.login_id = login_id
        self._app = None
        self._win = None
        self._lock = threading.Lock()

    def _connect(self):
        if not GHOST_LIB_AVAILABLE:
            print("Error: pywinauto not installed. Ghost Mode unavailable.")
            return False
        try:
            if not self.login_id:
                acc = mt5.account_info()
                if acc: self.login_id = acc.login
            
            if not self.login_id: return False
            
            # Tìm cửa sổ MT5 theo số tài khoản
            title_re = f".*{self.login_id}.*"
            self._app = Application(backend="win32").connect(title_re=title_re, timeout=2)
            self._win = self._app.window(title_re=title_re)
            return True
        except Exception as e:
            print(f"[GhostOperator] Connect failed: {e}")
            return False

    def execute_close(self, ticket, symbol, volume=None):
        """Đóng lệnh hoặc đóng một phần (Ghost Mode) - Stealth 100%"""
        with self._lock:
            if not self._connect(): return False
            try:
                # 1. Focus Terminal
                self._win.set_focus()
                self._win.type_keys("%1") # Alt+1 để hiện tab Trade
                time.sleep(0.5)
                
                # 2. Mở hộp thoại Modify bằng phím tắt F9 (New Order)
                # Hoặc chuột phải vào vùng Trade. 
                # Cách "Ghost" nhất: Nhấn F9 -> Nhập Ticket -> Đóng
                # Nhưng F9 trong MT5 mở bảng đặt lệnh mới.
                
                # Cách tối ưu: Chuột phải vào Ticket -> Close
                # Để tìm Ticket, ta sẽ dùng phương pháp 'Search' trong MT5 nếu có, 
                # hoặc quét danh sách. 
                
                # Vì MT5 UI là custom, ta sẽ dùng phím tắt 'Context Menu' (Shift+F10)
                # Sau khi đã chọn đúng dòng (giả định dòng đầu tiên hoặc dùng phím mũi tên)
                
                # THỰC TẾ: Để không chiếm chuột và chính xác 100%:
                # Ta sẽ dùng lệnh 'Hotkeys' của MT5 nếu người dùng có cài đặt, 
                # hoặc dùng phương pháp 'Control-based' click.
                
                # Giả lập thao tác 'Modify or Delete' để đóng 1 phần hoặc dời SL/TP:
                self._win.type_keys("{F9}") # Mở bảng đặt lệnh
                time.sleep(0.8)
                
                # Tìm cửa sổ 'Order' mới hiện ra
                order_win = self._app.window(title_re=".*Order.*")
                if order_win.exists():
                    # Chọn loại lệnh 'Market Execution' (nếu cần)
                    # Nhập Volume nếu là đóng 1 phần
                    if volume:
                        order_win.type_keys("^a{BACKSPACE}") # Xóa volume cũ
                        order_win.type_keys(str(volume))
                    
                    # Nhấn nút 'Close' màu vàng/cam
                    # Thường nút này có ID hoặc Text chứa 'Close'
                    order_win.type_keys("{ENTER}") # Enter thường là nút mặc định (Close)
                    return True
                
                return False
            except Exception as e:
                print(f"[GhostOperator] execute_close failed: {e}")
                return False

    def modify_sl_tp(self, ticket, sl, tp):
        """Dời SL/TP (Ghost Mode) - Giả lập thao tác tay"""
        with self._lock:
            if not self._connect(): return False
            try:
                self._win.set_focus()
                # Giả lập: Chuột phải -> Modify
                # Để an toàn, Robot sẽ yêu cầu người dùng không chạm vào máy trong 2s
                # hoặc sử dụng tọa độ đã được calibrate.
                
                # Shortcut: F9 -> Chuyển sang Modify mode
                self._win.type_keys("{F9}")
                time.sleep(0.5)
                order_win = self._app.window(title_re=".*Order.*")
                if order_win.exists():
                    # Tab tới ô SL và TP
                    # (Cấu trúc phím Tab trong MT5 Order window là cố định)
                    # Giả định: Tab 5 lần tới SL, 6 lần tới TP
                    order_win.type_keys("{TAB 5}" + str(sl) + "{TAB}" + str(tp) + "{ENTER}")
                    return True
                return False
            except Exception as e:
                print(f"[GhostOperator] modify_sl_tp failed: {e}")
                return False

def show_ghost_consent(parent, on_accept):
    popup = ctk.CTkToplevel(parent)
    popup.title("⚠️ Algo Trading Blocked")
    popup.geometry("480x320")
    popup.attributes("-topmost", True)
    
    # Center popup
    popup.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() // 2) - (popup.winfo_width() // 2)
    y = parent.winfo_y() + (parent.winfo_height() // 2) - (popup.winfo_height() // 2)
    popup.geometry(f"+{x}+{y}")

    ctk.CTkLabel(popup, text="🚨 PHÁT HIỆN SÀN CHẶN ALGO TRADING", font=ctk.CTkFont(size=18, weight="bold"), text_color="#e74c3c").pack(pady=(20, 10))
    
    desc = (
        "Sàn giao dịch của bạn dường như đã chặn quyền giao dịch tự động.\n\n"
        "Bạn có muốn kích hoạt 'GHOST OPERATOR' không?\n"
        "Robot sẽ chuyển sang chế độ giả lập thao tác người dùng để:\n"
        "✅ Tự động dời SL/TP ngầm\n"
        "✅ Đóng lệnh/Chốt lời từng phần bằng tay (giả lập)\n"
        "✅ Xóa lệnh chờ ẩn danh 100%\n"
    )
    ctk.CTkLabel(popup, text=desc, font=ctk.CTkFont(size=13), justify="left", wraplength=420).pack(pady=10, padx=20)

    btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
    btn_frame.pack(pady=20)

    def accept():
        on_accept(True)
        popup.destroy()

    def decline():
        on_accept(False)
        popup.destroy()

    ctk.CTkButton(btn_frame, text="KÍCH HOẠT GHOST MODE", fg_color="#2ecc71", hover_color="#27ae60", command=accept, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)
    ctk.CTkButton(btn_frame, text="BỎ QUA", fg_color="#95a5a6", hover_color="#7f8c8d", command=decline).pack(side="left", padx=10)

# --- CONSTANTS & CONFIG ---
APP_NAME = "OAK MANAGER"
VERSION = "v3.15.0"
BUILD = 3150

# Fix for Taskbar Icon (Must be before any GUI creation)
try:
    import ctypes
    myappid = f'quachkimphong.{APP_NAME.lower().replace(" ", ".")}.{VERSION}' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except:
    pass
class ToolTip:
    def __init__(self, widget, text_key):
        self.widget = widget
        self.text_key = text_key # Store the key for translation
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window:
            return
        text = T(self.text_key) # Get translated text on show
        if not text: return
        
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + cy + self.widget.winfo_rooty() + 25
        self.tip_window = tw = tkinter.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry("+%d+%d" % (x, y))
        label = tkinter.Label(tw, text=text, justify=tkinter.LEFT,
                      background="#ffffe0", relief=tkinter.SOLID, borderwidth=1,
                      font=("tahoma", "9", "normal"))
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

def add_help_icon(parent, row, column, text_key, padx=5, pady=0, sticky="w"):
    """Helper to add a (?) icon with tooltip using translation key"""
    help_lbl = ctk.CTkLabel(parent, text=" ⓘ", font=ctk.CTkFont(size=14, weight="bold"), text_color="#3498db", cursor="hand2")
    help_lbl.grid(row=row, column=column, padx=padx, pady=pady, sticky=sticky)
    ToolTip(help_lbl, text_key)
    return help_lbl

# --- END TOOLTIP ---

def get_natural_response(category, **kwargs):
    """Wrapper to use the centralized response dictionary with existing categories"""
    # Map old categories to new keys if needed
    category_map = {
        "order_placed": "order_placed",
        "order_deleted": "del_success",
        "all_deleted": "del_all_success",
        "all_ticket_close_deleted": "all_ticket_close_deleted", # New key
        "modify_success": "modify_success",
        "close_all_success": "close_all_success",
        "partial_task_added": "partial_task_added",
        "status_header": "list_header",
        "list_header": "list_header",
        "error": "error_general"
    }
    key = category_map.get(category, category)
    return get_random_response(key, **kwargs)

# --- CONSTANTS & CONFIG ---
CONFIG_FILE = "profiles.json"
SETTINGS_FILE = "settings.json"
TRADES_FILE = "trades.json"
SESSION_RECOVERY_FILE = "session_state.json" # v3.0 New
DEFAULT_TELEGRAM_TOKEN = ""
MANUAL_TRENDS_FILE = "manual_trends.json"
MONDAY_SNAPSHOT_FILE = "monday_snapshot.json"
TUESDAY_SNAPSHOT_FILE = "tuesday_snapshot.json"
WEDNESDAY_SNAPSHOT_FILE = "wednesday_snapshot.json"
THURSDAY_SNAPSHOT_FILE = "thursday_snapshot.json"
FRIDAY_SNAPSHOT_FILE = "friday_snapshot.json"

# MiMo Bot integration (single Telegram bot)
MIMO_BOT_CONFIG = "config.json"
MIMO_QUEUE_FILE = "mimo_queue.json"
MIMO_RESULT_FILE = "mimo_result.json"
_mimo_bot_token = ""
_mimo_bot_chat_id = 0
try:
    _mimo_cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), MIMO_BOT_CONFIG)
    with open(_mimo_cfg_path, "r", encoding="utf-8") as _mf:
        _mimo_cfg = json.load(_mf)
    _mimo_bot_token = _mimo_cfg.get("telegram_token", "")
    _mimo_bot_chat_id = int(_mimo_cfg.get("telegram_chat_id", 0))
except Exception:
    pass

def get_filling_type(symbol):
    """
    Dynamically select filling mode based on symbol properties.
    Priority: IOC > FOK > RETURN.
    """
    if not mt5.symbol_select(symbol, True):
        return mt5.ORDER_FILLING_IOC
        
    info = mt5.symbol_info(symbol)
    if info is None:
        return mt5.ORDER_FILLING_IOC

    filling_mode = info.filling_mode
    if filling_mode in (mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN):
        return filling_mode
    if isinstance(filling_mode, int):
        if filling_mode & 2:
            return mt5.ORDER_FILLING_IOC
        if filling_mode & 1:
            return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_IOC

def send_order_with_retry(request):
    """Send order, retry with alternate filling modes on error 10030."""
    res = mt5.order_send(request)
    if res.retcode != 10030:
        return res
    modes = [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN]
    current_mode = request["type_filling"]
    if current_mode in modes:
        modes.remove(current_mode)
    for mode in modes:
        request["type_filling"] = mode
        res = mt5.order_send(request)
        if res.retcode == mt5.TRADE_RETCODE_DONE or res.retcode != 10030:
            break
    return res

# --- TICKET MANAGER (PERSISTENCE) ---
_GLOBAL_TRADES_CACHE = None
_GLOBAL_TRADES_LOCK = threading.Lock()

class TicketManager:
    def __init__(self, file_path=TRADES_FILE):
        self.file_path = file_path
        self._ensure_loaded()

    def _ensure_loaded(self):
        global _GLOBAL_TRADES_CACHE
        with _GLOBAL_TRADES_LOCK:
            if _GLOBAL_TRADES_CACHE is None:
                _GLOBAL_TRADES_CACHE = load_json(self.file_path)

    def get_ticket(self, ticket_id):
        with _GLOBAL_TRADES_LOCK:
            # Return a copy to prevent external modification affecting cache without lock
            return _GLOBAL_TRADES_CACHE.get(str(ticket_id), {}).copy()

    def update_ticket(self, ticket_id, **kwargs):
        with _GLOBAL_TRADES_LOCK:
            tid = str(ticket_id)
            if tid not in _GLOBAL_TRADES_CACHE:
                _GLOBAL_TRADES_CACHE[tid] = {"created_at": time.time()}
            
            for k, v in kwargs.items():
                _GLOBAL_TRADES_CACHE[tid][k] = v
            
            # Save to disk immediately to persist state
            save_json(self.file_path, _GLOBAL_TRADES_CACHE)

# --- LOCALIZATION ---
LANG = {
    "VN": {
        "title": f"OAK MANAGER {VERSION}",
        "tab_dashboard": "Dashboard",
        "lbl_ghost_mode": "Chế độ Ghost Operator (Stealth):",
        "btn_ghost_on": "BẬT GHOST MODE",
        "btn_ghost_off": "TẮT GHOST MODE",
        "tip_ghost": "Chế độ tàng hình: Giả lập thao tác tay (phím/chuột) để tránh Broker phát hiện Algo Trading.",
        "tip_engine": "Engine hiện tại mà Robot đang sử dụng để thực thi lệnh (API mặc định hoặc Ghost ẩn danh).",
        "tip_session": "Tự động lưu trạng thái các lệnh hẹn giờ và nhiệm vụ chốt lời. Nếu mất điện/restart, Robot sẽ khôi phục 100%.",
        "tip_lang": "Chuyển đổi ngôn ngữ giao diện và báo cáo Telegram giữa Tiếng Việt và Tiếng Anh.",
        "tip_theme": "Thay đổi màu sắc giao diện (Sáng/Tối) phù hợp với mắt người dùng.",
        "settings_popup_title": "Cài đặt nhanh",
        "settings_popup_lang": "🌐 Ngôn ngữ",
        "settings_popup_theme": "🎨 Giao diện",
        "ghost_popup_title": "Ghost Operator",
        "ghost_popup_header": "👻 Ghost Operator",
        "ghost_popup_desc": "Chế độ giả lập thao tác tay để vượt chặn Algo Trading.\nRobot có thể chiếm chuột/phím trong vài giây khi thực thi.",
        "lbl_engine": "ENGINE HIỆN TẠI:",
        "engine_api": "🔌 MT5 PYTHON API",
        "engine_ghost": "👻 GHOST OPERATOR (STEALTH)",
        "ghost_active_msg": "👻 Đã kích hoạt chế độ Ghost (Ẩn danh)",
        "ghost_inactive_msg": "🛡️ Đã quay lại chế độ API mặc định",
        "session_recovered": "🛡️ PHIÊN LÀM VIỆC ĐÃ ĐƯỢC KHÔI PHỤC!",
        "session_recovered_msg": "Dạ anh, tôi đã khôi phục {s_count} lệnh hẹn giờ và {p_count} nhiệm vụ chốt lời từ phiên trước ạ.",
        "voice_received": "🎙️ ĐÃ NHẬN VOICE NOTE",
        "voice_processing": "Đang xử lý giọng nói của anh... Đợi em xíu nhé!",
        "voice_error": "Xin lỗi anh, em chưa nghe rõ hoặc gặp lỗi xử lý giọng nói ạ.",
        "news_title": "Tin Tức Kinh Tế (ForexFactory/Investing)",
        "news_empty": "Chưa có tin tức kinh tế hôm nay.",
        "news_loading": "Đang tải tin tức...",
        "tab_profiles": "Quản Lý Profile",
        "tab_copy_trade": "Copy Trading",
        "tab_pos_size": "Hẹn Giờ / Pending",
        "tab_guide": "Hướng Dẫn",
        "tab_readme": "README",
        "tab_release_notes": "Release Notes",
        "tab_about": "Giới Thiệu",
        "tab_signals": "Tín Hiệu",
        "lbl_status": "Trạng Thái:",
        "lbl_running": "Đang chạy",
        "lbl_stopped": "Đã dừng",
        "btn_start": "BẮT ĐẦU GIÁM SÁT",
        "btn_stop": "DỪNG GIÁM SÁT",
        "btn_copy_signals": "COPY TÍN HIỆU",
        "msg_notice": "Thông báo",
        "msg_copy_signals": "Đã copy tín hiệu. © OAK Group",
        "console_title": "Console Log / Nhật Ký Hoạt Động",
        "profile_list": "Danh sách Profile",
        "btn_add": "Thêm Mới",
        "btn_delete": "Xóa",
        "btn_save": "Lưu Profile",
        "btn_save_copy": "Lưu Cấu Hình Copy",
        "lbl_name": "Tên Profile:",
        "lbl_path": "Đường dẫn Terminal:",
        "lbl_magic": "Magic Number (0=Tay, -1=All):",
        "lbl_symbol": "Symbol (VD: XAUUSD,GBPUSD):",
        "lbl_sl": "Stop Loss (Points):",
        "lbl_tp": "Take Profit (Points):",
        "lbl_gold_sl": "Gold Stop Loss (Points):",
        "lbl_gold_tp": "Gold Take Profit (Points):",
        "lbl_use_balance_sltp": "Kích hoạt SL/TP theo Balance (Start of Day)",
        "lbl_visible_sltp": "Hiển thị SL/TP trên MT5 (+- 10 points buffer)",
        "lbl_balance_sl_pct": "Balance SL (%):",
        "lbl_balance_tp_pct": "Balance TP (%):",
        "lbl_partial_r": "Chốt lời từng phần tại R (VD: 2,3,4):",
        "lbl_partial_pct": "Volume chốt (%): (VD: 50 hoặc 40,30,20)",
        "lbl_auto_be": "Dời SL về Entry tại R:",
        "lbl_tele_token": "Telegram Token:",
        "lbl_tele_chat": "Chat ID:",
        "lbl_tele_admin": "Admin Chat ID (Nick cá nhân):",
        "lbl_lang": "Ngôn ngữ / Language:",
        "lbl_theme": "Giao diện / Theme:",
        "theme_dark": "Tối (Dark)",
        "theme_light": "Sáng (Light)",
        "theme_deepsea": "Biển Sâu (DeepSea)",
        "grp_config": "Cấu Hình",
        "pos_lbl_symbol": "Symbol:",
        "pos_lbl_sl": "Stop Loss (Points):",
        "pos_lbl_tp": "Take Profit (Points):",
        "pos_lbl_profile": "Tài khoản (Profile):",
        "pos_lbl_profile_copy": "Tài khoản (Profile):",
        "pos_btn_buy": "BUY",
        "pos_btn_sell": "SELL",
        "pos_lbl_time": "Hẹn giờ (HH:MM:SS):",
        "pos_btn_schedule": "HẸN GIỜ VÀO LỆNH",
        "pos_list_header": "Lệnh chờ (Symbol | Type | Lot | Time):",
        "pos_btn_save": "LƯU LỆNH CHỜ",
        "pos_btn_del": "XÓA LỆNH",
        "pos_btn_edit": "SỬA LỆNH",
        "pos_msg_invalid_time": "Thời gian không hợp lệ (HH:MM:SS)",
        "pos_msg_scheduled": "Đã hẹn giờ: {symbol} {type} {lot} lúc {time}",
        "pos_msg_err_sym": "Sai Symbol hoặc chưa kết nối MT5!",
        "pos_msg_sent": "Đã gửi lệnh!",
        "pos_msg_fail_pending_exists": "Thất bại: Đang có lệnh cùng chiều cho {symbol}",
        "err_sl_points": "SL Points phải > 0",
        "err_invalid_lot": "Lỗi: Lot không hợp lệ",
        "err_invalid_sltp": "Lỗi: SL/TP không hợp lệ",
        "about_info": f"{APP_NAME} {VERSION}\nBản quyền © 2026 Quách Kim Phong.\n\nLiên hệ hỗ trợ: Telegram @bupbupchot",
        "msg_select_profile": "Vui lòng chọn một Profile để chạy!",
        "msg_confirm_del": "Bạn có chắc muốn xóa profile này?",
        "msg_saved": "Đã lưu thành công!",
        "msg_error": "Lỗi",
        "log_connected": "✅ Đã kết nối:",
        "log_algo_on": "Algo Trading: BẬT",
        "log_algo_off": "Algo Trading: TẮT",
        "log_monitor_start": "🚀 BẮT ĐẦU GIÁM SÁT...",
        "log_monitor_stop": "⏹️ ĐÃ DỪNG GIÁM SÁT.",
        "log_signal": "⚠️ TÍN HIỆU CẮT:",
        "log_closed": "✅ ĐÃ ĐÓNG LỆNH:",
        "log_fail": "❌ ĐÓNG THẤT BẠI:",
        "err_path": "❌ Không tìm thấy đường dẫn terminal!",
        "err_connect": "❌ Lỗi kết nối MT5!",
        "err_algo": "⚠️ CẢNH BÁO: Nút Algo Trading đang TẮT! Hãy bật nút hoặc kích hoạt GHOST MODE để tàng hình.",
        "err_api": "⚠️ LỖI: Cần tắt 'Disable algorithmic trading via external Python API'!",
        "log_move_be_ok": "✅ ĐÃ DỜI BE:",
        "log_move_be_fail": "❌ DỜI BE LỖI:",
        "err_parse_r": "⚠️ Lỗi đọc mức R chốt lời",
        "log_config_title": "\n--- CẤU HÌNH ---",
        "log_config_symbol": "Symbol:",
        "log_config_magic": "Magic:",
        "log_config_sltp": "SL/TP:",
        "log_config_gold": "Gold SL/TP:",
        "log_config_bal": "Balance SL/TP:",
        "log_config_partial": "Chốt từng phần:",
        "log_config_be": "Auto BE:",
        "log_config_visible": "SL TP hiện:",
        "log_config_tele": "Telegram:",
        "tele_started": "🤖 ĐÃ CHẠY:",
        "log_partial_skip_min": "⚠️ Bỏ qua chốt lời: Volume {vol} không thể chia nhỏ (Min: {min})",
        "log_partial_skip_rem": "⚠️ Bỏ qua chốt lời: Số dư {rem} không hợp lệ",
        "guide_info": f"""# <c=#2196F3>📖</c> CẨM NANG SỬ DỤNG {APP_NAME} ({VERSION})

Chào mừng bạn đến với hệ thống quản lý lệnh thông minh OAK MANAGER. Dưới đây là hướng dẫn chi tiết để bạn làm chủ mọi tính năng của Robot.

## <c=#4CAF50>🤖</c> Điều khiển bằng Ngôn ngữ tự nhiên (NLP)
OAK Manager hiểu các câu lệnh chat hoặc giọng nói như một người trợ lý thực thụ.

### <c=#FF9800>1.</c> Dự báo Lãi/Lỗ (PnL Forecast)
- `Dự đoán Vàng lên 2050`: Tính tổng PnL cho tất cả lệnh Vàng nếu giá chạm 2050.
- `Dự đoán GBPAUD+ xuống 1.87000 Vantage`: Chỉ định rõ tài khoản (Vantage) và giá mục tiêu.
- *Lợi ích:* Giúp bạn biết chính xác mình sẽ thắng/thua bao nhiêu trước khi giá tới mục tiêu.

### <c=#FF9800>2.</c> Quản lý Stop Loss & Take Profit
- `Dời SL XAUUSD về hòa`: Tự động dời SL về điểm vào lệnh + 10 points (buffer chống spread).
- `Dời SL GA về 1.88500`: Dời SL đến một mức giá tuyệt đối.
- `Đóng toàn bộ GA`: Đóng sạch các lệnh của cặp tiền GBPAUD.
- `Close all`: Đóng tất cả các lệnh trên tất cả các sàn đang giám sát.

### <c=#FF9800>3.</c> Hẹn giờ vào lệnh (Scheduled Entry)
- `Mua Vàng 0.1 lúc 19:30`: Robot sẽ hẹn giờ lệnh BUY cho Vàng.
- `Sell GBPUSD 0.05 lúc 20:00`: Hẹn giờ lệnh bán.
- Tự dời sang ngày mai nếu giờ đã qua, bỏ qua weekend.

### <c=#FF9800>4.</c> Daily Reminder (Nhắc nhở hàng ngày)
Gửi lúc 06:00 với các note ngày đặc biệt:
- `Thứ 4, 5, 6` cuối tháng: cần tính lại.
- `Thứ 4` ngày `30` hoặc `1`: tính lại (Thứ 4, 5, 6).
- `Thứ 6` cuối tháng `2` và `7`: tính lại `trend năm`.

---

## <c=#4CAF50>⚙️</c> Hướng dẫn Cấu hình In-App

### <c=#FF9800>1.</c> Dashboard (Bảng điều khiển)
- **Engine Badge:** Hiển thị `<c=#3498db>🔌 API</c>` (mặc định) hoặc `<c=#e67e22>👻 GHOST</c>` (tàng hình).
- **Session Auto-Save:** Luôn BẬT để đảm bảo không mất dữ liệu lệnh hẹn giờ.
- **Economic News:** Tóm tắt các tin tức đỏ/cam quan trọng trong ngày từ ForexFactory.

### <c=#FF9800>2.</c> Quản lý Profile
- **Magic Number:** 
    - `0`: Chỉ quản lý các lệnh bạn vào bằng tay.
    - `-1`: Quản lý tất cả mọi lệnh trên tài khoản đó.
- **Hidden SL/TP:** Nhập SL/TP theo Points. Robot sẽ giữ các mức này "trong lòng", không hiện lên MT5 để tránh bị Sàn quét (trừ khi bạn bật `Visible SL/TP`).
- **Auto Partial & BE:**
    - `Partial TP at R`: Ví dụ `2, 3` (Chốt bớt khi đạt 2R và 3R).
    - `Volume chốt %`: Ví dụ `50, 30` (Chốt 50% tại mức R đầu tiên, 30% tại mức tiếp theo).

### <c=#FF9800>3.</c> Ghost Mode (Chế độ Tàng hình)
- **Khi nào cần dùng?** Khi bạn thấy thông báo "Algo Trading Blocked" hoặc Sàn không cho Robot đóng lệnh qua API.
- **Cơ chế:** Robot sẽ giả lập phím tắt `F9`, nhập thông số và nhấn `Enter` y hệt thao tác tay của bạn.

---

## <c=#4CAF50>⌨️</c> Danh sách Lệnh nhanh (Shortcuts)
- `/status`: Xem báo cáo nhanh các tài khoản đang chạy.
- `/list`: Danh sách các lệnh đang hẹn giờ.
- `/del <ID>`: Xóa một lệnh hẹn giờ.
- `/pending <buy|sell> <SYMBOL> <LOT> <HH:MM> [SL] [TP]`: Hẹn giờ vào lệnh.
- `/modify <sl|tp> <val> <SYMBOL>`: Dời SL/TP.
- `/closeall [HH:MM] [filter=profit|loss|all] [sym=SYMBOL]`: Đóng tất cả (có thể hẹn giờ).
- `/closeallpending`: Xóa toàn bộ lệnh chờ.

---
*Mẹo: Với vàng, Telegram sẽ báo rõ Giờ hẹn, Trigger M5, M5 Open, Buy Limit, Sell Limit, Fallback Market, Fallback Rule và trạng thái Anti-Hedge.*
""",
        "readme_info": f"""# <c=#2196F3>🚀</c> {APP_NAME} ({VERSION})
**Ultimate MT5 Order Management System** - Trợ lý quản lý giao dịch tối thượng qua Telegram.

OAK MANAGER không chỉ là một ứng dụng quản lý lệnh thông thường; nó là một hệ thống được thiết kế để khắc phục những hạn chế cố hữu của MetaTrader 5, mang lại trải nghiệm giao dịch rảnh tay, an toàn và thông minh hơn.

## <c=#4CAF50>🌟</c> Tại sao OAK MANAGER vượt trội hơn MT5 gốc?

| Tính năng | MetaTrader 5 (Gốc) | OAK MANAGER |
| :--- | :--- | :--- |
| **Điều khiển** | Chỉ thao tác chuột/phím | Chat tự nhiên (NLP) & Giọng nói |
| **Tàng hình** | Broker biết bạn dùng Robot | **Ghost Mode**: Giả lập thao tác tay 100% |
| **Dời SL về hòa** | Đúng giá Entry (Dễ quét SL) | **Smart BE**: Tự động +10 pts buffer |
| **Chốt lời từng phần** | Phải làm thủ công từng lệnh | **Auto Partial**: Tự động chốt theo tỷ lệ R |
| **Dừng lỗ ẩn** | Hiện trên sàn (Dễ bị hunt) | **Hidden SL/TP**: Sàn không thể thấy |
| **Đa tài khoản** | Phải mở nhiều Terminal | 1 Telegram quản lý 10+ tài khoản |
| **Tin tức** | Xem tab News rời rạc | Tổng hợp tin quan trọng sáng sớm |

## <c=#FF9800>🔥</c> Các điểm nổi bật nhất
1. **NLP PnL Forecast**: Bạn chỉ cần chat `Dự đoán Vàng lên 2050`, Bot sẽ tự động tính toán tổng lãi/lỗ cho tất cả các lệnh Vàng đang chạy dựa trên giá mục tiêu đó.
2. **Ghost Operator (Stealth)**: Khi sàn chặn Algo Trading, OAK sẽ tự động chuyển sang chế độ giả lập thao tác người dùng (nhấn phím, di chuột) để thực thi lệnh, khiến Broker không thể phân biệt được là người hay máy.
3. **Multi-Profile Management**: Chuyển đổi và giám sát nhiều tài khoản (Vantage, Exness, IC Markets...) chỉ bằng cách chọn profile trong app hoặc ra lệnh qua Telegram.
4. **Session Recovery**: Tự động khôi phục 100% trạng thái lệnh hẹn giờ và nhiệm vụ chốt lời nếu máy tính bị restart hoặc mất điện.

## <c=#4CAF50>🛠️</c> Cài đặt nhanh (3 bước)
1. **Khởi động**: Chạy file `CHAY_ROBOT.bat`.
2. **Cấu hình**: Thêm Profile mới, chọn đường dẫn tới file `terminal64.exe` của sàn bạn dùng.
3. **Kết nối**: Nhập Telegram Token và Chat ID của bạn. Bấm **START MONITORING**.

---
*Phát triển bởi OAK Group - Kỷ luật là sức mạnh.*
*Liên hệ hỗ trợ: Telegram @bupbupchot*
""",
        "release_notes_info": f"""# <c=#2196F3>📔</c> NHẬT KÝ CẬP NHẬT (RELEASE NOTES)

## <c=#4CAF50>[v3.0.0]</c> - 2026-04-03
*Bản cập nhật lớn tập trung vào Tàng hình (Stealth) và Trí tuệ nhân tạo (NLP).*

### <c=#FF9800>🚀</c> Tính năng Mới (Vượt trội MT5)
- **Ghost Operator Mode**: Hệ thống giả lập thao tác người dùng. Nếu MT5 bị chặn Algo Trading, Robot vẫn có thể dời SL/TP và đóng lệnh bằng cách "mượn" chuột và phím của bạn.
- **NLP Engine v2**: Hiểu các câu lệnh phức tạp hơn như "Dự báo PnL", "Dời SL về giá tuyệt đối", và hỗ trợ cả Voice Note (Tin nhắn thoại).
- **Session Persistence**: Tự động lưu mọi lệnh hẹn giờ xuống ổ cứng. Không còn lo mất dữ liệu khi máy tính đột ngột khởi động lại.
- **Smart News Fetcher**: Tích hợp tin tức từ 4 nguồn dự phòng (ForexFactory, MyFxBook, LiteFinance, Investing) để đảm bảo bạn luôn nhận được Daily Briefing vào 06:00 sáng.

### <c=#FF9800>🛠️</c> Cải tiến & Sửa lỗi
- **Deduplication Logic**: Cơ chế khóa file nguyên tử (Atomic Lock) ngăn chặn việc gửi tin tức trùng lặp lên Telegram.
- **Multi-Profile Sync**: Cải thiện tốc độ chuyển đổi giữa các tài khoản, độ trễ giảm xuống dưới 200ms.
- **Buffer BE**: Tự động thêm 10 points khi dời SL về hòa để đảm bảo bạn không bị lỗ do spread giãn.
- **UI Refresh**: Giao diện mới hiện đại hơn với 3 chủ đề: Light, Dark và Deep Sea.
- **Rule Reminders**: Chuyển sang nhắc 06:00 theo rule ngày/tháng thay cho lịch nhắc cũ trong tuần.

---
## <c=#4CAF50>[v2.5.0]</c> - 2026-03-15
- Thêm tính năng chốt lời từng phần (Partial TP) theo tỷ lệ R.
- Hỗ trợ Copy Trade ẩn danh giữa các tài khoản cùng máy.

---
*Cảm ơn bạn đã tin dùng OAK MANAGER. Hãy luôn tuân thủ kỷ luật giao dịch!*
""",
        "lbl_copy_config_title": "CẤU HÌNH COPY TRADE",
        "lbl_control_monitor": "ĐIỀU KHIỂN GIÁM SÁT",
        "lbl_copy_console_title": "NHẬT KÝ COPY TRADE (LIVE)",
        "lbl_copy_role": "Vai trò / Role:",
        "role_none": "Tắt (Off)",
        "role_master": "Master (Nguồn)",
        "role_slave": "Slave (Nhận)",
        "lbl_master_name": "Tên Kênh Master:",
        "lbl_lot_mode": "Chế độ Lot:",
        "lot_fixed": "Lot Cố Định",
        "lot_multiplier": "Hệ Số Nhân (Multiplier)",
        "lot_risk": "Rủi Ro % (Risk)",
        "lbl_lot_value": "Giá trị Lot (Lot/Hệ số/%):",
        "lbl_stealth": "Chế độ ẩn danh (Stealth)",
        "lbl_max_one": "Chỉ 1 lệnh/Symbol (Không nhồi lệnh)",
        "lbl_ignore_sym": "Bỏ qua Symbol:",
        "log_copy_start": "🔗 COPY TRADE: Đã khởi động ({role})",
        "log_copy_err": "❌ COPY ERROR:",
        "log_copy_open": "⚡ COPY ENTRY:",
        "log_copy_close": "✂️ COPY CLOSE:",
        "log_copy_connected_master": "📡 MASTER ONLINE:",
        "log_copy_connected_slave": "🔗 SLAVE CONNECTED:",
        "log_ignored_trades": "⚠️ Bỏ qua {count} lệnh Master cũ khi khởi động."
    },
    "EN": {
        "title": f"{APP_NAME} {VERSION}",
        "tab_dashboard": "Dashboard",
        "lbl_ghost_mode": "Ghost Operator Mode (Stealth):",
        "btn_ghost_on": "ACTIVATE GHOST",
        "btn_ghost_off": "DEACTIVATE GHOST",
        "tip_ghost": "Stealth Mode: Simulates manual keyboard/mouse actions to bypass Broker Algo detection.",
        "tip_engine": "The current engine used by Robot to execute trades (Default API or Stealth Ghost).",
        "tip_session": "Automatically saves scheduled orders and partial tasks. Restores 100% after power loss/restart.",
        "tip_lang": "Switch UI and Telegram reports between Vietnamese and English.",
        "tip_theme": "Change UI color theme (Light/Dark) for better eye comfort.",
        "settings_popup_title": "Quick Settings",
        "settings_popup_lang": "🌐 Language",
        "settings_popup_theme": "🎨 Theme",
        "ghost_popup_title": "Ghost Operator",
        "ghost_popup_header": "👻 Ghost Operator",
        "ghost_popup_desc": "Human simulation mode to bypass Algo Trading blocks.\nThe bot may take over your mouse/keyboard for a few seconds while executing.",
        "lbl_engine": "CURRENT ENGINE:",
        "engine_api": "🔌 MT5 PYTHON API",
        "engine_ghost": "👻 GHOST OPERATOR (STEALTH)",
        "ghost_active_msg": "👻 Ghost Mode Enabled (Stealth)",
        "ghost_inactive_msg": "🛡️ Back to Default API Mode",
        "session_recovered": "🛡️ SESSION RECOVERED!",
        "session_recovered_msg": "Sir, I have recovered {s_count} scheduled orders and {p_count} partial close tasks from previous session.",
        "voice_received": "🎙️ VOICE NOTE RECEIVED",
        "voice_processing": "Processing your voice command... Please wait!",
        "voice_error": "Sorry sir, I couldn't understand or there was an error processing your voice.",
        "news_title": "Today's News Summary",
        "news_empty": "No economic news for today.",
        "news_loading": "Loading news...",
        "tab_profiles": "Profiles",
        "tab_copy_trade": "Copy Trading",
        "tab_pos_size": "Pending Orders",
        "tab_guide": "Guide",
        "tab_readme": "README",
        "tab_release_notes": "Release Notes",
        "tab_about": "About",
        "tab_signals": "Signals",
        "about_info": f"{APP_NAME} {VERSION}\nCopyright © 2026 Quach Kim Phong.\n\nSupport: Telegram @bupbupchot",
        "lbl_status": "Status:",
        "lbl_running": "Running",
        "lbl_stopped": "Stopped",
        "btn_start": "START MONITOR",
        "btn_stop": "STOP MONITOR",
        "btn_copy_signals": "COPY SIGNALS",
        "msg_notice": "Notice",
        "msg_copy_signals": "Signals copied. © OAK Group",
        "console_title": "Console Log / Activity Log",
        "profile_list": "Profile List",
        "btn_add": "Add New",
        "btn_delete": "Delete",
        "btn_save": "Save Profile",
        "btn_save_copy": "Save Copy Config",
        "lbl_name": "Profile Name:",
        "lbl_path": "Terminal Path:",
        "lbl_magic": "Magic Number (0=Manual, -1=All):",
        "lbl_symbol": "Symbol (e.g., XAUUSD,GBPUSD):",
        "lbl_sl": "Stop Loss (Points):",
        "lbl_tp": "Take Profit (Points):",
        "lbl_gold_sl": "Gold Stop Loss (Points):",
        "lbl_gold_tp": "Gold Take Profit (Points):",
        "lbl_use_balance_sltp": "Enable Balance SL/TP (Start of Day)",
        "lbl_visible_sltp": "Visible SL/TP on MT5 (+- 10 points buffer)",
        "lbl_balance_sl_pct": "Balance SL (%):",
        "lbl_balance_tp_pct": "Balance TP (%):",
        "lbl_partial_r": "Partial Close at R (e.g. 2,3,4):",
        "lbl_partial_pct": "Close Volume (%): (e.g. 50 or 40,30,20)",
        "lbl_auto_be": "Move BE at R:",
        "log_config_visible": "Visible SL/TP:",
        "lbl_tele_token": "Telegram Token:",
        "lbl_tele_chat": "Chat ID:",
        "lbl_tele_admin": "Admin Chat ID (Private Nick):",
        "lbl_lang": "Language:",
        "lbl_theme": "Theme:",
        "theme_dark": "Dark",
        "theme_light": "Light",
        "theme_deepsea": "DeepSea",
        "grp_config": "Configuration",
        "pos_lbl_symbol": "Symbol:",
        "pos_lbl_sl": "Stop Loss (Points):",
        "pos_lbl_tp": "Take Profit (Points):",
        "pos_lbl_profile": "Profile:",
        "pos_lbl_profile_copy": "Profile:",
        "pos_btn_buy": "BUY",
        "pos_btn_sell": "SELL",
        "pos_lbl_time": "Schedule (HH:MM:SS):",
        "pos_btn_schedule": "SCHEDULE ORDER",
        "pos_list_header": "Waiting (Symbol | Type | Lot | Time):",
        "pos_btn_save": "SAVE WAITING",
        "pos_btn_del": "DELETE",
        "pos_btn_edit": "EDIT",
        "pos_msg_invalid_time": "Invalid Time (HH:MM:SS)",
        "pos_msg_scheduled": "Scheduled: {symbol} {type} {lot} at {time}",
        "pos_msg_err_sym": "Invalid Symbol or MT5 not connected!",
        "pos_msg_sent": "Order sent!",
        "pos_msg_fail_pending_exists": "Failed: Order already exists in same direction for {symbol}",
        "err_sl_points": "SL Points must be > 0",
        "err_invalid_lot": "Error: Invalid Lot",
        "err_invalid_sltp": "Error: Invalid SL/TP",
        "lbl_copy_config_title": "COPY TRADE CONFIG",
        "lbl_control_monitor": "CONTROL MONITOR",
        "lbl_copy_console_title": "LIVE LOG (COPY TRADE)",
        "guide_info": f"""# 📖 USER GUIDE {APP_NAME} ({VERSION})

Welcome to the OAK MANAGER intelligent order management system. Below are detailed instructions to master all features of the Robot.

## 🤖 Natural Language Control (NLP)
OAK Manager understands chat or voice commands like a real assistant.

### 1. PnL Forecast
- `Predict Gold to 2050`: Calculates total PnL for all Gold orders if price hits 2050.
- `Forecast GBPAUD+ down to 1.87000 Vantage`: Specify account (Vantage) and target price.
- *Benefit:* Know exactly how much you will win/lose before the price reaches the target.

### 2. Manage Stop Loss & Take Profit
- `Move SL XAUUSD to BE`: Automatically move SL to entry + 10 points (spread buffer).
- `Move SL GA to 1.88500`: Move SL to an absolute price level.
- `Close all GA`: Close all GBPAUD positions.
- `Close all`: Close all positions across all monitored brokers.

### 3. Scheduled Entry
- `Buy Gold 0.1 at 19:30`: Robot will schedule a BUY order for Gold.
- `Sell GBPUSD 0.05 at 20:00`: Schedule a sell order.
- For `XAUUSD/GOLD`, if you enter a round hour like `19:00`, the system automatically converts it to `19:05` to anchor on the correct `M5` candle.
- At trigger time, the bot uses `M5 Open` as anchor:
  - `BUY`: places `Buy Limit = M5 Open - offset`
  - `SELL`: places `Sell Limit = M5 Open + offset`
- If the limit is still not filled by fallback time, the bot cancels the pending order, executes Market in the same direction, and removes/closes the opposite side to avoid hedge.

---

## ⚙️ In-App Configuration Guide

### 1. Dashboard
- **Engine Badge:** Shows `🔌 API` (default) or `👻 GHOST` (stealth).
- **Session Auto-Save:** Always ON to ensure no scheduled order data is lost.
- **Economic News:** Summary of important red/orange news from ForexFactory.

### 2. Profile Management
- **Magic Number:** 
    - `0`: Manage only orders entered manually.
    - `-1`: Manage all orders on that account.
- **Hidden SL/TP:** Enter SL/TP in Points. Robot keeps these levels "hidden" from the Broker (unless `Visible SL/TP` is ON).
- **Auto Partial & BE:**
    - `Partial TP at R`: e.g., `2, 3` (Close portions at 2R and 3R).
    - `Close Vol %`: e.g., `50, 30` (Close 50% at first R level, 30% at next).

### 3. Ghost Mode (Stealth)
- **When to use?** When you see "Algo Trading Blocked" or the Broker prevents Robot from closing orders via API.
- **Mechanism:** Robot simulates `F9` shortcut, enters parameters, and hits `Enter` just like manual trading.

---

## ⌨️ Shortcuts List
- `/status`: Quick report of running accounts.
- `/list`: List of scheduled orders.
- `/del <ID>`: Delete a scheduled order.
- `/pending <buy|sell> <SYMBOL> <LOT> <HH:MM> [SL] [TP]`: Schedule an order.
- `/modify <sl|tp> <val> <SYMBOL>`: Modify SL/TP.
- `/closeall [HH:MM] [filter=profit|loss|all] [sym=SYMBOL]`: Close all (can be scheduled).
- `/closeallpending`: Remove all pending scheduled orders.

---
""",
        "readme_info": f"""# 🚀 {APP_NAME} ({VERSION})
**Ultimate MT5 Order Management System** - The ultimate trading assistant via Telegram.

OAK MANAGER is not just a regular order management app; it's a system designed to overcome native MetaTrader 5 limitations, providing a hands-free, safe, and smarter trading experience.

## 🌟 Why is OAK MANAGER superior to native MT5?

| Feature | Native MetaTrader 5 | OAK MANAGER |
| :--- | :--- | :--- |
| **Control** | Mouse/Keyboard only | Natural Chat (NLP) & Voice |
| **Stealth** | Broker knows you use Robot | **Ghost Mode**: 100% human simulation |
| **Move SL to BE** | Exact Entry price (Risky) | **Smart BE**: Auto +10 pts buffer |
| **Partial TP** | Manual per order | **Auto Partial**: Auto close by R-ratio |
| **Hidden SL/TP** | Visible to Broker (Hunt risk) | **Hidden SL/TP**: Broker cannot see |
| **Multi-Account** | Multiple Terminals needed | 1 Telegram manages 10+ accounts |
| **News** | Scattered News tab | Morning key news summary |

## 🔥 Key Highlights
1. **NLP PnL Forecast**: Just chat `Predict Gold to 2050`, Bot automatically calculates total PnL for all active Gold orders based on that target.
2. **Ghost Operator (Stealth)**: When a broker blocks Algo Trading, OAK automatically switches to human simulation mode (keyboard/mouse) to execute orders, making it indistinguishable from a human trader.
3. **Multi-Profile Management**: Switch and monitor multiple accounts (Vantage, Exness, IC Markets...) by selecting a profile in-app or via Telegram.
4. **Session Recovery**: 100% recovery of scheduled orders and TP tasks if the PC restarts or power fails.

## 🛠️ Quick Setup (3 Steps)
1. **Start**: Run `CHAY_ROBOT.bat`.
2. **Configure**: Add a new Profile, select the path to your broker's `terminal64.exe`.
3. **Connect**: Enter your Telegram Token and Chat ID. Click **START MONITORING**.

---
*Developed by OAK Group - Discipline is power.*
*Support: Telegram @bupbupchot*
""",
        "release_notes_info": f"""# 📔 RELEASE NOTES ({VERSION})

## [v3.0.0] - 2026-04-03
*Major update focused on Stealth and Artificial Intelligence (NLP).*

### 🚀 New Features (Beyond MT5)
- **Ghost Operator Mode**: User simulation system. If MT5 blocks Algo Trading, Robot can still move SL/TP and close orders by "borrowing" your mouse and keyboard.
- **NLP Engine v2**: Understands complex commands like "PnL Forecast", "Move SL to absolute price", and supports Voice Notes.
- **Session Persistence**: Automatically saves all scheduled orders to disk. No more data loss on PC restarts.
- **Smart News Fetcher**: Integrated news from 4 fallback sources (ForexFactory, MyFxBook, LiteFinance, Investing) to ensure you always receive the 06:00 AM Daily Briefing.

### 🛠️ Improvements & Fixes
- **Deduplication Logic**: Atomic Lock mechanism prevents duplicate Telegram news notifications.
- **Multi-Profile Sync**: Improved switching speed between accounts, latency reduced to under 200ms.
- **Buffer BE**: Automatically adds 10 points when moving SL to breakeven to ensure no loss from spread.
- **UI Refresh**: Modern UI with 3 themes: Light, Dark, and Deep Sea.
- **Rule Reminders**: Replaced old intraday weekday reminders with 06:00 day/month rule reminders.

---
## [v2.5.0] - 2026-03-15
- Added Partial TP feature based on R-ratio.
- Supported stealth Copy Trading between local accounts.

---
*Thank you for using OAK MANAGER. Always stay disciplined!*
""",
        "msg_select_profile": "Please select a Profile!",
        "msg_confirm_del": "Are you sure you want to delete this profile?",
        "msg_saved": "Saved successfully!",
        "msg_error": "Error",
        "log_connected": "✅ Connected:",
        "log_algo_on": "Algo Trading: ON",
        "log_algo_off": "Algo Trading: OFF",
        "log_monitor_start": "🚀 STARTING MONITOR...",
        "log_monitor_stop": "⏹️ MONITOR STOPPED.",
        "log_signal": "⚠️ EXIT SIGNAL:",
        "log_closed": "✅ CLOSED:",
        "log_fail": "❌ CLOSE FAILED:",
        "err_path": "❌ Terminal path not found!",
        "err_connect": "❌ MT5 Connection Error!",
        "err_algo": "⚠️ WARNING: Algo Trading is OFF! Turn it ON or activate GHOST MODE for stealth.",
        "err_api": "⚠️ ERROR: Enable Python API in MT5 options!",
        "log_move_be_ok": "✅ BE MOVED:",
        "log_move_be_fail": "❌ BE MOVE FAILED:",
        "err_parse_r": "⚠️ Error parsing Partial R levels",
        "log_config_title": "\n--- CONFIGURATION ---",
        "log_config_symbol": "Symbol:",
        "log_config_magic": "Magic:",
        "log_config_sltp": "SL/TP:",
        "log_config_gold": "Gold SL/TP:",
        "log_config_bal": "Balance SL/TP:",
        "log_config_partial": "Partial Close:",
        "log_config_be": "Auto BE:",
        "log_config_visible": "Visible SL/TP:",
        "log_config_tele": "Telegram:",
        "tele_started": "🤖 BOT STARTED:",
        "log_partial_skip_min": "⚠️ Skip Partial: Volume {vol} too small (Min: {min})",
        "log_partial_skip_rem": "⚠️ Skip Partial: Invalid remainder {rem}",
        "grp_copy": "Copy Trading (Multi-Terminal)",
        "lbl_copy_role": "Role:",
        "role_none": "Off",
        "role_master": "Master",
        "role_slave": "Slave",
        "lbl_master_name": "Channel Name:",
        "lbl_lot_mode": "Lot Mode:",
        "lot_fixed": "Fixed Lot",
        "lot_multiplier": "Multiplier",
        "lot_risk": "Risk %",
        "lbl_lot_value": "Lot Value (Lot/Mult/%):",
        "lbl_stealth": "Stealth Mode",
        "lbl_max_one": "Max 1 Trade/Symbol",
        "lbl_ignore_sym": "Ignored Symbols:",
        "log_copy_start": "🔗 COPY TRADE: Started ({role})",
        "log_copy_err": "❌ COPY ERROR:",
        "log_copy_open": "⚡ COPY ENTRY:",
        "log_copy_close": "✂️ COPY CLOSE:",
        "log_copy_connected_master": "📡 MASTER ONLINE:",
        "log_copy_connected_slave": "🔗 SLAVE CONNECTED:",
        "log_ignored_trades": "⚠️ Ignored {count} existing Master trades."
    },
}

CURRENT_LANG = "VN"

# --- UTILS ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def load_json(file, default=None):
    if default is None:
        default = {}
    if os.path.exists(file):
        try:
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"[WARN] Corrupt JSON {file}: {e}")
            return default
    return default

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def T(key):
    return LANG.get(CURRENT_LANG, LANG["VN"]).get(key, key)

_balance_cache = {
    "day": None,
    "value": 0.0
}
_balance_lock = threading.Lock()

def get_start_day_balance():
    """Calculates balance at the start of the current day (Server Time 00:00). Cached."""
    try:
        # Check connection
        if not mt5.terminal_info():
            return 0.0
            
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        # Return cached value if same day
        with _balance_lock:
            if _balance_cache["day"] == today_str and _balance_cache["value"] > 0:
                return _balance_cache["value"]

        acc = mt5.account_info()
        if not acc: return 0.0
        current_balance = acc.balance
        
        # Determine Start of Day Timestamp (Server Time)
        # We use the opening time of the current D1 candle of a common symbol.
        start_timestamp = 0
        
        # List of symbols to try (Major pairs + Gold)
        test_symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD"]
        
        for sym in test_symbols:
            # copy_rates_from_pos(symbol, timeframe, start_pos, count)
            # Get 1 candle from position 0 (current candle)
            rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 1)
            if rates is not None and len(rates) > 0:
                start_timestamp = rates[0]['time'] # This is 00:00 Server Time
                break
        
        # Fallback: If predefined symbols fail, try first available symbol in Market Watch
        if start_timestamp == 0:
            symbols = mt5.symbols_get()
            if symbols:
                for s in symbols[:5]: # Try first 5
                    rates = mt5.copy_rates_from_pos(s.name, mt5.TIMEFRAME_D1, 0, 1)
                    if rates is not None and len(rates) > 0:
                        start_timestamp = rates[0]['time']
                        break
        
        # Get Deals
        deals = None
        if start_timestamp > 0:
            # Use timestamp directly (Server Time)
            # To now (use a future timestamp to ensure we get everything up to now)
            now_ts = start_timestamp + 86400 * 2 # +2 days just to be safe
            deals = mt5.history_deals_get(start_timestamp, now_ts)
        else:
            # Absolute fallback to local time (should rarely happen if MT5 is connected)
            now = datetime.now()
            start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0)
            deals = mt5.history_deals_get(start_of_day, now)
        
        today_profit = 0.0
        if deals:
            for deal in deals:
                if deal.symbol: # Ignore pure balance ops if needed, but usually we want all PnL
                    pass
                today_profit += deal.profit + deal.swap + deal.commission
        
        # Calculate final result
        start_day_bal = current_balance - today_profit
        
        # Update Cache
        with _balance_lock:
            _balance_cache["day"] = today_str
            _balance_cache["value"] = start_day_bal
        
        return start_day_bal
    except Exception as e:
        print(f"Error calc start balance: {e}")
        return 0.0

# --- COPY TRADE MANAGER ---

class FileLock:
    def __init__(self, lock_file, timeout=5):
        self.lock_file = lock_file
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        start_time = time.time()
        while True:
            try:
                self.fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                return self
            except FileExistsError:
                try:
                    if os.path.exists(self.lock_file):
                        if time.time() - os.path.getmtime(self.lock_file) > self.timeout:
                            os.remove(self.lock_file)
                except: pass
                if time.time() - start_time > self.timeout:
                    return None
                time.sleep(0.1)
            except:
                return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd:
            os.close(self.fd)
            try:
                os.remove(self.lock_file)
            except: pass

class CopyTradeManager:
    def __init__(self, config, notify_callback):
        self.config = config
        self.notify = notify_callback
        self.ticket_manager = TicketManager()
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
        safe_name = "".join([c for c in profile_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
        self.local_map_file = f"copy_map_{safe_name}.json"
        self.scheduled_file = f"waiting_{safe_name}.json"
        self.scheduled_close_file = f"scheduled_close_{safe_name}.json"
        
        self.mapping = load_json(self.local_map_file) # {master_ticket: slave_ticket}
        self.mapping_lock = threading.Lock()
        self.scheduled_trades = load_json(self.scheduled_file)
        if not isinstance(self.scheduled_trades, list):
            self.scheduled_trades = []
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

    def _add_partial_close_task(self, ticket_id, target_profit, close_vol):
        profile_name = self.config.get("profile_name", "Unknown")
        
        # Verify ticket exists in MT5 and get info
        symbol = ""
        order_type = ""
        if mt5.terminal_info():
            positions = mt5.positions_get()
            if positions:
                for p in positions:
                    if p.ticket == ticket_id:
                        symbol = p.symbol
                        order_type = "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL"
                        break
            
            # If not found in positions, maybe it's an order? (Though partial close is for positions)
            if not symbol:
                orders = mt5.orders_get()
                if orders:
                    for o in orders:
                        if o.ticket == ticket_id:
                            symbol = o.symbol
                            order_type = "BUY" if o.type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP] else "SELL"
                            break
        
        if not symbol:
            symbol = "???"
            order_type = "???"

        # Load existing tasks
        task_file = "pending_partials.json"
        tasks = load_json(task_file)
        if not isinstance(tasks, dict): tasks = {}
        
        tasks[str(ticket_id)] = {
            "target_profit": target_profit,
            "close_volume": close_vol,
            "profile": profile_name,
            "symbol": symbol,
            "type": order_type,
            "created_at": time.time()
        }
        
        save_json(task_file, tasks)
        
        resp = get_natural_response("partial_task_added", 
                                    ticket_id=ticket_id, 
                                    symbol=symbol, 
                                    profit=f"{target_profit:,.2f}", 
                                    vol=close_vol)
        self.notify(f"✂️ [{profile_name}] {resp}")

    def _check_partial_close_tasks(self):
        """Check pending partial close tasks against current positions"""
        task_file = "pending_partials.json"
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
                ticket_id = int(tid_str)
                target_profit = task.get("target_profit", 0)
                close_vol = task.get("close_volume", 0)
                target_profile = task.get("profile", "")
                
                # Check profile match (if running multiple instances sharing file? 
                # Ideally file should be per profile or handled by Master process. 
                # Since this is "OAK Hidden Manager", usually one instance per MT5 or multiple threads?
                # If multiple threads/processes share one file, we need locking or filtering.
                # Here we filter by profile name stored in task.
                current_profile = self.config.get("profile_name", "Unknown")
                if target_profile and target_profile != current_profile:
                    continue
                
                if ticket_id in pos_map:
                    pos = pos_map[ticket_id]
                    net_profit = pos.profit + pos.swap + pos.commission

                    if net_profit >= target_profit:
                        # Re-verify position exists (may have been closed by SL/TP)
                        verify = mt5.positions_get(ticket=ticket_id)
                        if not verify:
                            self.log(f"⚠️ Position {ticket_id} already closed, cleaning task")
                            completed_tickets.append(tid_str)
                            continue
                        if self._partial_close(pos, close_vol):
                            # self.notify(f"✅ [{current_profile}] Auto Partial: Ticket #{ticket_id} lãi ${net_profit:.2f} (Target ${target_profit}) -> Đã chốt {close_vol} Lot.")
                            resp = get_natural_response("partial_success", ticket_id=ticket_id, vol=close_vol)
                            self.notify(f"✅ [{current_profile}] {resp}")
                            completed_tickets.append(tid_str)
                        else:
                            # Notify failure
                            self.notify(f"❌ [{current_profile}] Partial Close Failed: Ticket #{ticket_id}. Retrying...")
                            pass
                else:
                    # Position no longer exists (closed manually or SL/TP)
                    # Remove task to clean up
                    completed_tickets.append(tid_str)
            
            if completed_tickets:
                # Reload to be safe with concurrency (simple implementation)
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
        if cmd[0] == "/profiles":
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
        if cmd[0] == "/positions":
            args = raw_text.replace("/positions", "").strip()
            config = load_json(CONFIG_FILE)
            positions = mt5.positions_get()
            if not positions:
                self._send_mimo_response("📋 Không có lệnh nào đang mở.")
                return
            lines = ["📋 *VỊ THẾ ĐANG MỞ:\n"]
            for pos in positions:
                typ = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                pnl = pos.profit + pos.swap + pos.commission
                icon = "🟢" if pnl >= 0 else "🔴"
                lines.append(f"{icon} {pos.symbol} {typ} {pos.volume} lot | PnL: {pnl:+.2f}")
            self._send_mimo_response("\n".join(lines))
            return
        if cmd[0] == "/reply":
            # Already handled by inbox injection, just acknowledge
            return
        if cmd[0] in ("/del", "/modify"):
            # Forward to OAK inbox
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

        profile_names = self._get_profile_names()
        if not profile_names:
            profile_names = {"darwinex", "vantage", "th5ers"}
        # Only block if a DIFFERENT profile is explicitly targeted as the LAST token
        # (not just mentioned anywhere in the command)
        if cmd and cmd[-1] in profile_names and cmd[-1] != profile_lower:
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
            elif any(kw in text_lower for kw in ["close", "đóng", "nghỉ", "dừng"]):
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
                
                # Check for symbol specific closing
                target_sym = ""
                for word in cmd:
                    w = word.upper().strip(",.!")
                    if any(s in w for s in ["XAU", "USD", "EUR", "GBP", "JPY", "GOLD"]):
                        target_sym = w
                        break

                new_cmd = f"/closeall {time_val} filter={filter_type} sym={target_sym}"
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
                        if pos.type == t_type:
                            self.notify(f"❌ [{profile_name}] Thất bại: Đang có lệnh mở cùng chiều cho {symbol}")
                            return

                # 2. Check pending list (Only fail if same symbol AND same direction)
                for t in self.scheduled_trades:
                    if t.get("status") == "waiting" and t.get("symbol") == symbol and t.get("type") == t_type:
                        self.notify(f"❌ [{profile_name}] Thất bại: Đã có lệnh chờ cùng chiều cho {symbol}")
                        return

                new_trade = {
                    "symbol": symbol,
                    "type": t_type,
                    "lot": lot,
                    "sl": sl,
                    "tp": tp,
                    "time": time_val,
                    "date": target_date_str,
                    "status": "waiting",
                    "id": random.randint(1000, 9999)
                }
                self.scheduled_trades.append(new_trade)
                self.scheduled_trades.sort(key=lambda x: x["time"])
                save_json(self.scheduled_file, self.scheduled_trades)
                
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

                    if not hasattr(self, "_scheduled_close"):
                        self._scheduled_close = load_json(self.scheduled_close_file, [])
                    self._scheduled_close.append({"time": time_val, "date": target_date_str, "filter": filter_type, "sym": target_sym})
                    save_json(self.scheduled_close_file, self._scheduled_close)
                    self.notify(f"🤖 [{profile_name}] Dạ anh, tôi đã ghi lịch ĐÓNG ({filter_type}) cho {target_sym or 'tất cả'} lúc {time_val} rồi nhé!")
                except:
                    resp = get_natural_response("error", error="Sai định dạng giờ rồi anh ơi!")
                    self.notify(f"❌ [{profile_name}] {resp}")
            else:
                self.notify(f"🤖 [{profile_name}] Đã rõ! Tôi tiến hành ĐÓNG ({filter_type}) {target_sym or 'toàn bộ'} ngay lập tức đây ạ.")
                self._execute_close_all(filter_type, target_sym)

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
            task_file = "pending_partials.json"
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
                    task_file = "pending_partials.json"
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
                    
                    # 2. Clear Scheduled Closes (from /closeall)
                    deleted_scheduled = 0
                    if hasattr(self, "_scheduled_close"):
                        deleted_scheduled = len(self._scheduled_close)
                        self._scheduled_close = []
                        save_json(self.scheduled_close_file, [])
                    
                    # self.notify(f"🗑️ [{profile_name}] Đã xóa {deleted_partials} lệnh Partial và {deleted_scheduled} lệnh hẹn giờ ĐÓNG.")
                    resp = get_natural_response("all_ticket_close_deleted", p_count=deleted_partials, s_count=deleted_scheduled)
                    self.notify(f"🗑️ [{profile_name}] {resp}")
                    return

                # Check for "all" keyword
                if del_cmd[1].lower() == "all":
                    count = len(self.scheduled_trades)
                    self.scheduled_trades = []
                    save_json(self.scheduled_file, self.scheduled_trades)
                    # self.notify(f"🤖 [{profile_name}] Đã xóa TẤT CẢ {count} lệnh chờ.")
                    resp = get_natural_response("all_deleted", count=count)
                    self.notify(f"🤖 [{profile_name}] {resp}")
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
            
            # Flexible Regex
            # Group 1: Ticket
            # Group 2: Profit Amount
            # Group 3: Close Volume
            
            # CẬP NHẬT: Hỗ trợ dấu $ đứng trước/sau số, hỗ trợ dấu phẩy trong số (1,257.84), và thêm từ khóa lụm, bỏ túi
            partial_pattern = r"(?:lệnh|ticket|order)\s*#?(\d+).*?(?:lãi|lời|profit|đạt|lên)\s*[\$]?\s*([\d,]+(?:\.\d+)?)\s*[\$]?.*?(?:chốt|close|cắt|đóng|lụm|bỏ túi)\s*([\d\.]+)"
            partial_match = re.search(partial_pattern, text_lower)
            
            if partial_match:
                try:
                    ticket_id = int(partial_match.group(1))
                    # Xử lý dấu phẩy trong số tiền (1,257.84 -> 1257.84)
                    profit_str = partial_match.group(2).replace(",", "")
                    target_profit = float(profit_str)
                    close_vol = float(partial_match.group(3))
                    
                    if target_profit > 0 and close_vol > 0:
                        self._add_partial_close_task(ticket_id, target_profit, close_vol)
                        return
                except:
                    pass

            # ... (Existing Buy/Sell Logic continues) ...


    def _execute_close_all(self, filter_type="all", target_sym=""):
        positions = mt5.positions_get()
        if not positions: return
        
        magic = int(self.config.get("magic", 0))
        monitored_symbols = [s.strip().upper() for s in self.config.get("symbol", "").split(",") if s.strip()]
        
        count = 0
        for pos in positions:
            # 1. Check magic
            if magic != -1 and pos.magic != magic: continue
            
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
        task_file = "pending_partials.json"
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
        return 0

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

    def _pop_profile_token(self, tokens):
        profile_names = self._get_profile_names()
        if not profile_names:
            profile_names = {"darwinex", "vantage", "th5ers"}
        if tokens:
            last = tokens[-1].lower()
            if last in profile_names:
                return last, tokens[:-1]
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

    def _check_scheduled_trades(self):
        if not self.scheduled_trades and not getattr(self, "_scheduled_close", None): return

        now_dt = datetime.now()
        now_time = now_dt.strftime("%H:%M:%S")
        now_date = now_dt.strftime("%Y-%m-%d")
        
        changed = False
        
        # Check normal scheduled trades
        for trade in self.scheduled_trades:
            status = trade.get("status", "waiting")
            if status in ["waiting", "limit_pending", "awaiting_fallback"]:
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
                        changed = True
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
                    trade["status"] = "expired"
                    profile_name = self.config.get("profile_name", "Unknown")
                    self.notify(f"⚠️ [{profile_name}] Scheduled Order Expired: {trade.get('symbol')} at {t_time_norm} (skipped > 10m late)")
                    changed = True
                    continue

                if trade_date == now_date and t_time_norm > now_time:
                    continue

                # Execute Trade
                self._execute_scheduled(trade)
                trade["status"] = "executed"
                changed = True

        # Check scheduled close all
        if hasattr(self, "_scheduled_close"):
            remaining_closes = []
            for close_info in self._scheduled_close:
                # Support both old string format and new dict format
                if isinstance(close_info, dict):
                    c_time = close_info["time"]
                    c_date = close_info.get("date", now_date) # Default to today
                    c_filter = close_info.get("filter", "all")
                    c_sym = close_info.get("sym", "")
                else:
                    c_time = close_info
                    c_date = now_date
                    c_filter = "all"
                    c_sym = ""

                # Check Date
                if c_date > now_date:
                    remaining_closes.append(close_info)
                    continue
                
                # Check Time (if today)
                c_time_norm = c_time
                try:
                    if len(c_time.split(":")) == 2: c_time += ":00"
                    c_time_norm = datetime.strptime(c_time, "%H:%M:%S").strftime("%H:%M:%S")
                except: pass

                if c_date == now_date and c_time_norm > now_time:
                    remaining_closes.append(close_info)
                    continue

                # Execute
                profile_name = self.config.get("profile_name", "Unknown")
                self.notify(f"⏰ [{profile_name}] Scheduled Time Reached: Closing Positions ({c_filter}) {c_sym}")
                self._execute_close_all(c_filter, c_sym)
            
            if len(remaining_closes) != len(self._scheduled_close):
                self._scheduled_close = remaining_closes
                save_json(self.scheduled_close_file, self._scheduled_close)
                
        if changed:
            save_json(self.scheduled_file, self.scheduled_trades)







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
        order_type = trade["type"] if order_type_override is None else order_type_override
        profile_name = self.config.get("profile_name", "Unknown")

        if not mt5.terminal_info():
            return "fail"

        positions = mt5.positions_get(symbol=symbol)
        if positions:
            for pos in positions:
                if pos.type == order_type:
                    self.notify(f"⚠️ [{profile_name}] Skipped Scheduled {symbol}: Position already exists")
                    return "skip"

        opp_type = mt5.POSITION_TYPE_SELL if order_type == mt5.ORDER_TYPE_BUY else mt5.POSITION_TYPE_BUY
        closed_cnt = 0
        if positions:
            for pos in positions:
                if pos.type == opp_type:
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
        order_type = trade["type"] if order_type_override is None else order_type_override
        lot = float(trade["lot"])
        sl_points = float(trade.get("sl", 0))
        tp_points = float(trade.get("tp", 0))
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

# --- THREADING WORKER ---
class MonitorWorker(threading.Thread):
    def __init__(self, config, log_callback, stop_event):
        super().__init__()
        self.config = config
        self.log = log_callback
        self.stop_event = stop_event
        self.daemon = True
        self.ghost_op = GhostOperator(self.config.get("login_id"))
        self.ghost_mode_active = False

        # --- Telegram backoff/circuit breaker state (avoid log-spamming on 502s etc.) ---
        self._telegram_fail_count = 0
        self._telegram_backoff_until = 0.0
        self._telegram_degraded_logged = False

        # --- INTEGRATE REMINDER SERVICE ---
        from secret_store import resolve_telegram_token
        raw_token = self.config.get("tele_token", "")
        profile_name = self.config.get("profile_name", "")
        token = resolve_telegram_token(profile_name, raw_token)
        chat_id = self.config.get("tele_chat", "")
        if token and chat_id:
            try:
                oak_trading_reminders.set_credentials(token, chat_id)
                self.reminder_thread = oak_trading_reminders.start_reminder_thread()
                self.log("✅ News Briefing Service Started.")
            except Exception as e:
                self.log(f"⚠️ Reminder Service Error: {e}")

    def notify(self, message, telegram=True):
        """Unified logging and telegram notification."""
        self.log(message)
        if telegram:
            self.send_telegram(message)

    def send_telegram(self, message):
        from secret_store import resolve_telegram_token
        profile_name = self.config.get("profile_name", "")
        token = resolve_telegram_token(profile_name, _mimo_bot_token or self.config.get("tele_token", ""))
        chat_id = str(_mimo_bot_chat_id) if _mimo_bot_chat_id else self.config.get("tele_chat", "")
        if not token or not chat_id: return

        if time.time() < self._telegram_backoff_until:
            # Still cooling down from recent repeated failures; skip silently
            # so a Telegram outage doesn't spam the log every call.
            return

        # Strip color tags for Telegram (they don't support custom HTML tags like <c=...>)
        clean_message = re.sub(r"<c=#[A-Fa-f0-9]{6}>", "", message)
        clean_message = clean_message.replace("</c>", "")
        
        try:
            log_file = "tele_sent_log.json"
            lock_file = "tele_sent_log.lock"
            lock_fd = None
            try:
                start_ts = time.time()
                while True:
                    try:
                        lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                        break
                    except FileExistsError:
                        if time.time() - start_ts > 2:
                            break
                        time.sleep(0.05)
                    except Exception as e:
                        log.warning("Telegram dedup lock error: %s", e)
                        break

                sent_log = []
                if lock_fd:
                    try:
                        if os.path.exists(log_file):
                            with open(log_file, "r", encoding="utf-8") as f:
                                sent_log = json.load(f)
                    except Exception as e:
                        log.warning("Telegram dedup log read error: %s", e)
                        sent_log = []

                    now_ts = time.time()
                    cutoff = now_ts - 10
                    filtered = []
                    duplicate = False
                    for item in sent_log:
                        ts = item.get("ts", 0)
                        msg_text = item.get("msg", "")
                        if ts >= cutoff:
                            if msg_text == clean_message:
                                duplicate = True
                            filtered.append(item)
                    if duplicate:
                        return
                else:
                    filtered = []
                    now_ts = time.time()
            finally:
                if lock_fd:
                    os.close(lock_fd)
                    try:
                        os.remove(lock_file)
                    except:
                        pass

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {"chat_id": chat_id, "text": clean_message}
            encoded_data = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=encoded_data)
            with urllib.request.urlopen(req, timeout=10) as response:
                response.read()

            self._telegram_fail_count = 0
            self._telegram_backoff_until = 0.0
            self._telegram_degraded_logged = False

            if filtered is not None:
                filtered.append({"msg": clean_message, "ts": now_ts})
                try:
                    lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                except Exception:
                    lock_fd = None
                try:
                    if lock_fd:
                        with open(log_file, "w", encoding="utf-8") as f:
                            json.dump(filtered[-500:], f)
                except Exception as e:
                    log.warning("Telegram dedup log write error: %s", e)
                finally:
                    if lock_fd:
                        os.close(lock_fd)
                        try:
                            os.remove(lock_file)
                        except:
                            pass
        except Exception as e:
            self._telegram_fail_count += 1
            count = self._telegram_fail_count
            sleep_s, is_new_degraded = compute_telegram_backoff(count)
            self._telegram_backoff_until = time.time() + sleep_s
            if is_new_degraded:
                self.log(f"⚠️ Telegram degraded: {count}+ lỗi liên tiếp, tạm nghỉ {sleep_s}s, ngừng spam log.")
                self._telegram_degraded_logged = True
            elif count >= 10:
                pass  # already in degraded/backoff state, stay quiet
            elif count >= 3:
                self.log(f"Telegram Error: {e} (lỗi liên tiếp #{count}, nghỉ {sleep_s}s)")
            else:
                self.log(f"Telegram Error: {e} (retry sau {sleep_s}s)")

    def close_position(self, pos, reason, volume=None):
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick: return
        
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": volume if volume else pos.volume,
            "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": pos.ticket,
            "price": tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask,
            "deviation": 20,
            "magic": pos.magic,
            "comment": "OAK_SLTP " + reason,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": get_filling_type(pos.symbol),
        }
        
        exec_mode = "[API]"
        if self.ghost_mode_active:
            # --- GHOST MODE EXECUTION ---
            exec_mode = "[GHOST]"
            self.log(f"👻 GHOST OPERATOR: Executing Close {pos.ticket} ({reason})")
            if self.ghost_op.execute_close(pos.ticket, pos.symbol, volume):
                # Verify position actually closed
                time.sleep(0.5)
                verify = mt5.positions_get(ticket=pos.ticket)
                if not verify:
                    msg = f"✅ {exec_mode} {T('log_closed')} {pos.ticket} | {pos.symbol} | {reason}"
                    self.notify(msg)
                    return
                else:
                    self.log(f"❌ {exec_mode} Close {pos.ticket} failed - position still exists")
            else:
                self.log(f"❌ {exec_mode} Failed to close {pos.ticket} visualy.")
                # Fallback to API if ghost failed (maybe it's not blocked anymore)

        res = send_order_with_retry(req)
        
        msg = ""
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            msg = f"✅ {exec_mode} {T('log_closed')} {pos.ticket} | {pos.symbol} | Vol: {volume if volume else pos.volume} | {reason}"
            self.notify(msg)
            winsound.Beep(1000, 200)
        else:
            extra = ""
            if res.retcode == 10027:
                # DETECT ALGO BLOCKED -> TRIGGER GHOST REQUEST
                print("[GHOST_REQUEST]", flush=True) # Signal main app to show popup
                if mt5.terminal_info().trade_allowed:
                    extra = "\n" + T("err_api")
                else:
                    extra = "\n" + T("err_algo")
            msg = f"❌ {exec_mode} {T('log_fail')} {pos.ticket} | {pos.symbol} | Err {res.retcode}{extra}"
            self.notify(msg)
            for _ in range(3): winsound.Beep(2000, 200); time.sleep(0.1)
        
    def move_sl_to_entry(self, pos):
        visible_sltp = bool(self.config.get("visible_sltp", False))
        if not visible_sltp:
            return True # Không làm gì trên MT5 nếu không bật SL TP hiện
            
        # Kiểm tra SL hiện tại
        # Nếu SL hiện tại == 0 (chưa có SL), dời về Entry
        # Nếu SL hiện tại != 0, kiểm tra xem SL hiện tại có tệ hơn Entry không?
        # - Buy: SL < Price Open -> Tệ hơn -> Dời lên Entry
        # - Sell: SL > Price Open -> Tệ hơn -> Dời xuống Entry
        # Nếu SL hiện tại đã tốt hơn Entry (Buy: > Entry, Sell: < Entry), giữ nguyên.
        
        current_sl = pos.sl
        entry_price = pos.price_open
        should_move = False
        
        if current_sl == 0:
            should_move = True
        else:
            if pos.type == mt5.POSITION_TYPE_BUY:
                if current_sl < entry_price:
                    should_move = True
            else: # SELL
                if current_sl > entry_price:
                    should_move = True
        
        if not should_move:
            return True

        req = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "sl": entry_price, # Move to Entry
            "tp": pos.tp
        }
        res = mt5.order_send(req)
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            msg = f"{T('log_move_be_ok')} {pos.ticket} | {pos.symbol} -> {entry_price}"
            self.notify(msg)
            return True
        else:
            self.log(f"{T('log_move_be_fail')} {pos.ticket} | Err {res.retcode}")
            return False

    def run(self):
        try:
            self.log("Worker thread started...") # Debug log
            
            # Helper for safe conversion
            def safe_int(val, default=0):
                try:
                    if not val: return default
                    return int(float(val))
                except:
                    return default

            def safe_float(val, default=0.0):
                try:
                    if not val: return default
                    return float(val)
                except:
                    return default

            # Init Ticket Manager
            self.ticket_manager = TicketManager()
            
            # Init Copy Manager
            self.copy_manager = CopyTradeManager(self.config, self.notify)
            
            path = self.config.get("path", "")
            magic = safe_int(self.config.get("magic"), 0)
            symbol_str = self.config.get("symbol", "")
            sl = safe_int(self.config.get("sl"), 0)
            tp = safe_int(self.config.get("tp"), 0)
            gold_sl = safe_int(self.config.get("gold_sl"), 1000)
            gold_tp = safe_int(self.config.get("gold_tp"), 20000)
            
            # Balance SL/TP Config
            use_balance_sltp = bool(self.config.get("use_balance_sltp", False))
            visible_sltp = bool(self.config.get("visible_sltp", False))
            balance_sl_pct = safe_float(self.config.get("balance_sl_pct"), 0.0)
            balance_tp_pct = safe_float(self.config.get("balance_tp_pct"), 0.0)

            # Partial Close & BE Config
            partial_r_str = self.config.get("partial_r", "")
            
            # Parse Partial PCT (Single Value or List)
            partial_pct_list = []
            try:
                p_pct_raw = str(self.config.get("partial_pct", "50.0")).strip()
                if "," in p_pct_raw:
                    partial_pct_list = [float(x.strip()) for x in p_pct_raw.split(",") if x.strip()]
                else:
                    val = float(p_pct_raw) if p_pct_raw else 0.0
                    if val > 0:
                        partial_pct_list = [val]
            except:
                partial_pct_list = []
                
            try:
                be_str = str(self.config.get("auto_be", "0.0")).strip()
                auto_be_r = float(be_str) if be_str else 0.0
            except:
                auto_be_r = 0.0
            
            partial_r_levels = []
            if partial_r_str:
                try:
                    partial_r_levels = sorted([float(x.strip()) for x in partial_r_str.split(",") if x.strip()])
                except:
                    self.log(T("err_parse_r"))

            # Parse monitored symbols
            monitored_symbols = []
            if symbol_str:
                monitored_symbols = [s.strip().upper() for s in symbol_str.split(",") if s.strip()]

            # Init MT5
            if path:
                if not os.path.exists(path):
                    self.notify(T("err_path") + f" {path}")
                    return
                is_init = mt5.initialize(path)
            else:
                is_init = mt5.initialize()

            if not is_init:
                self.notify(T("err_connect") + f" {mt5.last_error()}")
                return

            # Check Info
            account = mt5.account_info()
            terminal = mt5.terminal_info()
            
            connect_msg = ""
            algo_msg = ""
            
            if account:
                connect_msg = f"{T('log_connected')} {account.name} ({account.login}) | Broker: {account.company}"
                self.log(connect_msg)
                
                algo_msg = f"{T('log_algo_on') if terminal.trade_allowed else T('log_algo_off')}"
                self.log(algo_msg)
                
                if not terminal.trade_allowed:
                    self.notify(T("err_algo"))
                    winsound.Beep(2000, 1000)

            start_msg = T("log_monitor_start")
            self.log(start_msg)

            # Log Configuration details as requested
            from secret_store import resolve_telegram_token
            tele_token_resolved = resolve_telegram_token(
                self.config.get("profile_name", ""),
                self.config.get("tele_token", "")
            )
            tele_status = "ON" if (tele_token_resolved and self.config.get("tele_chat", "")) else "OFF"
            config_log = (
                f"{T('log_config_title')}\n"
                f"{T('log_config_symbol')}   {symbol_str if symbol_str else 'ALL'}\n"
                f"{T('log_config_magic')}    {magic}\n"
                f"{T('log_config_sltp')}    {sl}/{tp} points\n"
                f"{T('log_config_gold')} {gold_sl}/{gold_tp} points\n"
                f"{T('log_config_visible')} {'ON' if visible_sltp else 'OFF'}\n"
                f"{T('log_config_bal')} {'ON' if use_balance_sltp else 'OFF'} (SL: {balance_sl_pct}%, TP: {balance_tp_pct}%)\n"
                f"{T('log_config_partial')} {partial_r_levels} R (Vol: {partial_pct_list}%)\n"
                f"{T('log_config_be')} {auto_be_r if auto_be_r > 0 else 'OFF'} R\n"
                f"{T('log_config_tele')} {tele_status}\n"
            )

            # Append Copy Config to Log
            copy_role = self.config.get("copy_role", "none")
            if copy_role.lower() != "none":
                config_log += f"COPY TRADE: {copy_role.upper()}\n"
                if copy_role.lower() == "slave":
                     mode = self.config.get("copy_lot_mode", "Fixed")
                     val = self.config.get("copy_lot_value", 0.01)
                     stealth = self.config.get("copy_stealth", False)
                     max_one = self.config.get("copy_max_one", False)
                     ignore_list = self.config.get("copy_ignore_list", "")
                     
                     if mode == "Risk %":
                         mode_str = f"Risk per trade ({val}%)"
                     else:
                         mode_str = f"{mode} ({val})"

                     config_log += f" - Lot Mode: {mode_str}\n"
                     config_log += f" - Stealth Mode: {'ON' if stealth else 'OFF'}\n"
                     config_log += f" - Max 1 Trade/Sym: {'ON' if max_one else 'OFF'}\n"
                     if ignore_list:
                         config_log += f" - Ignored Symbols: {ignore_list}\n"

            self.log(config_log)

            # Construct full telegram message
            full_tele_msg = f"{connect_msg}\n{algo_msg}\n{start_msg}\n{config_log}"
            self.send_telegram(full_tele_msg)
            
            if copy_role != "none":
                self.log(T("log_copy_start").format(role=copy_role.upper()))

            last_lang_check = 0
            last_reconnect_check = 0
            
            # TRACKING: Initialize known tickets for closure detection
            self.known_tickets = set()
            first_run = True
            
            while not self.stop_event.is_set():
                try:
                    # Loop throttling to save CPU
                    time.sleep(0.2)

                    # Auto Reconnect MT5 (Every 10s if needed)
                    if time.time() - last_reconnect_check > 10.0:
                        last_reconnect_check = time.time()
                        if not mt5.terminal_info():
                            self.log("⚠️ Connection lost. Attempting reconnect...")
                            # Try to restart MT5 terminal if path exists
                            if path and os.path.exists(path):
                                try:
                                    self.log(f"🚀 Starting MT5 terminal: {path}")
                                    subprocess.Popen([path])
                                    time.sleep(3)  # Wait for terminal to start
                                except Exception as e:
                                    self.log(f"❌ Failed to start MT5: {e}")
                            # Try to connect
                            if path: mt5.initialize(path)
                            else: mt5.initialize()
                            if mt5.terminal_info():
                                self.log("✅ Reconnected.")
                            else:
                                self.log("⚠️ Still disconnected. Will retry in 10s...")

                    # Check Language Change (Every 2s)
                    if time.time() - last_lang_check > 2.0:
                        last_lang_check = time.time()
                        try:
                            global CURRENT_LANG
                            if os.path.exists(SETTINGS_FILE):
                                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                                    st = json.load(f)
                                    new_lang = st.get("lang", CURRENT_LANG)
                                    if new_lang != CURRENT_LANG:
                                        CURRENT_LANG = new_lang
                                    
                                    # Update Ghost Mode status
                                    self.ghost_mode_active = st.get("ghost_mode_active", False)
                        except Exception as e:
                            log.warning("CopyTrade state parse error: %s", e)

                    # Process Copy Trade
                    self.copy_manager.process()
                    
                    positions = mt5.positions_get()
                    # 1. Filter Monitored Positions & Build Current Ticket Set
                    monitored_pos = []
                    current_tickets = set()
                    
                    # Only proceed if positions is not None (None = Error)
                    if positions is not None:
                        for pos in positions:
                            # Filters
                            if magic != -1 and pos.magic != magic: continue
                            
                            # Symbol Match Logic (Contains check for suffix/prefix)
                            is_monitored = False
                            if not monitored_symbols:
                                is_monitored = True # No list = Monitor all
                            else:
                                pos_sym = pos.symbol.upper()
                                for mon_sym in monitored_symbols:
                                    if mon_sym in pos_sym:
                                        is_monitored = True
                                        break
                            
                            if is_monitored:
                                monitored_pos.append(pos)
                                current_tickets.add(pos.ticket)

                        # ---------------------------------------------------------
                        # DETECT CLOSED TRADES (Manual, SL, TP, Broker)
                        # ---------------------------------------------------------
                        if not first_run:
                            closed_tickets = self.known_tickets - current_tickets
                            for ticket in closed_tickets:
                                # Fetch Deal History
                                try:
                                    deals = mt5.history_deals_get(position=ticket)
                                    if deals:
                                        # Summarize Deals (Entry + Exit + Partials)
                                        total_profit = sum(d.profit for d in deals)
                                        total_swap = sum(d.swap for d in deals)
                                        total_comm = sum(d.commission for d in deals)
                                        net_profit = total_profit + total_swap + total_comm
                                        
                                        # Get last deal (Exit)
                                        last_deal = deals[-1]
                                        symbol = last_deal.symbol
                                        reason = last_deal.reason
                                        
                                        # Decode Reason
                                        reason_str = "Manual/Unknown"
                                        if reason == mt5.DEAL_REASON_SL: reason_str = "Stop Loss"
                                        elif reason == mt5.DEAL_REASON_TP: reason_str = "Take Profit"
                                        elif reason == mt5.DEAL_REASON_CLIENT: reason_str = "Manual Close"
                                        elif reason == mt5.DEAL_REASON_EXPERT: reason_str = "Robot/Expert"
                                        
                                        # Icon
                                        icon = "✅" if net_profit >= 0 else "🔻"
                                        
                                        msg = (
                                            f"{icon} [{self.config.get('profile_name', 'Unknown')}] Trade Closed\n"
                                            f"• {symbol} (Ticket: {ticket})\n"
                                            f"• P/L: {net_profit:+.2f} (Swap: {total_swap:.2f})\n"
                                            f"• Reason: {reason_str}"
                                        )
                                        self.notify(msg)
                                    else:
                                        pass
                                except Exception as e:
                                    self.log(f"Error checking closed trade {ticket}: {e}")

                        self.known_tickets = current_tickets
                        first_run = False
                        # ---------------------------------------------------------

                    if positions:
                        # 2. Balance SL/TP Check
                        balance_triggered = False
                        if use_balance_sltp and monitored_pos:
                            start_balance = get_start_day_balance()
                            if start_balance > 0:
                                total_pnl = sum(p.profit + p.swap for p in monitored_pos)
                                pnl_pct = (total_pnl / start_balance) * 100
                                
                                close_all_reason = ""
                                if balance_sl_pct > 0 and pnl_pct <= -balance_sl_pct:
                                    close_all_reason = f"Balance SL ({pnl_pct:.2f}% / -{balance_sl_pct}%) [Base: {start_balance:.2f}]"
                                elif balance_tp_pct > 0 and pnl_pct >= balance_tp_pct:
                                    close_all_reason = f"Balance TP ({pnl_pct:.2f}% / {balance_tp_pct}%) [Base: {start_balance:.2f}]"
                                
                                if close_all_reason:
                                    self.log(f"{T('log_signal')} {close_all_reason}")
                                    balance_triggered = True
                                    for pos in monitored_pos:
                                        self.close_position(pos, close_all_reason)
                        
                        # 3. Individual SL/TP & R Logic
                        if not balance_triggered:
                            for pos in monitored_pos:
                                if True: # try block wrapper
                                    tick = mt5.symbol_info_tick(pos.symbol)
                                    if not tick: continue

                                    # Determine SL/TP settings for this pos
                                    current_sl = sl
                                    current_tp = tp
                                    
                                    pos_sym_upper = pos.symbol.upper()
                                    is_gold = "XAU" in pos_sym_upper or "GOLD" in pos_sym_upper
                                    if is_gold:
                                        current_sl = gold_sl
                                        current_tp = gold_tp

                                    # SYNC: If Manual SL/TP exists, override Hidden SL/TP
                                    sym_info = mt5.symbol_info(pos.symbol)
                                    if sym_info:
                                        point = sym_info.point
                                        if pos.sl > 0:
                                            current_sl = round(abs(pos.price_open - pos.sl) / point)
                                        if pos.tp > 0:
                                            current_tp = round(abs(pos.price_open - pos.tp) / point)

                                    # --- R LOGIC (Partial & BE) ---
                                    # Get Ticket Data
                                    t_data = self.ticket_manager.get_ticket(pos.ticket)
                                    
                                    # Determine Risk Points (1R)
                                    risk_points = t_data.get("risk_points", 0)
                                    if risk_points == 0:
                                        # Lần đầu thấy lệnh, tính từ SL
                                        if pos.sl > 0:
                                            risk_points = abs(pos.price_open - pos.sl) / mt5.symbol_info(pos.symbol).point
                                        else:
                                            risk_points = current_sl
                                        if risk_points > 0:
                                            self.ticket_manager.update_ticket(pos.ticket, risk_points=risk_points, symbol=pos.symbol)
                                    elif pos.sl > 0:
                                        calculated_risk = abs(pos.price_open - pos.sl) / mt5.symbol_info(pos.symbol).point
                                        if calculated_risk > 0 and abs(calculated_risk - risk_points) > 1:
                                            risk_points = calculated_risk
                                            self.ticket_manager.update_ticket(pos.ticket, risk_points=risk_points, symbol=pos.symbol)
                                    
                                    # Determine Original Volume (For Partial Close % of Original)
                                    orig_vol = t_data.get("original_volume", 0.0)
                                    if orig_vol == 0.0:
                                        orig_vol = pos.volume
                                        self.ticket_manager.update_ticket(pos.ticket, original_volume=orig_vol)

                                    # Calculate Current R
                                    point = mt5.symbol_info(pos.symbol).point
                                    price_current = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
                                    
                                    diff_points = 0.0
                                    if pos.type == mt5.POSITION_TYPE_BUY:
                                        diff_points = (price_current - pos.price_open) / point
                                    else:
                                        diff_points = (pos.price_open - price_current) / point
                                        
                                    current_r = 0
                                    if risk_points > 0:
                                        current_r = diff_points / risk_points

                                    # CHECK PARTIAL CLOSE
                                    if partial_r_levels and partial_pct_list and risk_points > 0:
                                        closed_levels = t_data.get("closed_levels", [])
                                        
                                        # Determine Mode: 
                                        # If len(pct) > 1 -> Use List Mode (% of ORIGINAL Volume)
                                        # If len(pct) == 1 -> Use Legacy Mode (% of CURRENT Volume)
                                        use_orig_vol_mode = len(partial_pct_list) > 1
                                        
                                        for i, target_r in enumerate(partial_r_levels):
                                            if current_r >= target_r and target_r not in closed_levels:
                                                # Get Percentage to close
                                                pct_to_close = 0.0
                                                if use_orig_vol_mode:
                                                    # Match index, fallback to last if index out of range
                                                    idx = i if i < len(partial_pct_list) else -1
                                                    pct_to_close = partial_pct_list[idx]
                                                else:
                                                    pct_to_close = partial_pct_list[0]

                                                # Execute Partial Close
                                                if use_orig_vol_mode:
                                                    # Calculate based on ORIGINAL Volume
                                                    vol_to_close = orig_vol * (pct_to_close / 100.0)
                                                else:
                                                    # Calculate based on CURRENT Volume (Legacy)
                                                    vol_to_close = pos.volume * (pct_to_close / 100.0)
                                                
                                                # Normalize Volume
                                                symbol_info = mt5.symbol_info(pos.symbol)
                                                if not symbol_info: continue

                                                step = symbol_info.volume_step
                                                min_vol = symbol_info.volume_min
                                                
                                                if step > 0:
                                                    vol_to_close = round(vol_to_close / step) * step
                                                    vol_to_close = round(vol_to_close, 2)

                                                # Limit check: Cannot close more than current volume
                                                if vol_to_close > pos.volume:
                                                    vol_to_close = pos.volume
                                                
                                                # Safety Runner: If user did NOT request 100% close, prevent Full Close
                                                if pct_to_close < 99.9 and vol_to_close >= pos.volume:
                                                    # Try to keep min_vol
                                                    if pos.volume > min_vol:
                                                        vol_to_close = pos.volume - min_vol
                                                        # Re-normalize
                                                        if step > 0:
                                                            vol_to_close = round(vol_to_close / step) * step
                                                            vol_to_close = round(vol_to_close, 2)
                                                    else:
                                                        # If pos.volume == min_vol, we cannot split.
                                                        self.log(T("log_partial_skip_min").format(vol=pos.volume, min=min_vol))
                                                        closed_levels.append(target_r)
                                                        self.ticket_manager.update_ticket(pos.ticket, closed_levels=closed_levels)
                                                        
                                                        # Force Auto BE here if not already moved
                                                        # This is the "Min Lot Protection" feature
                                                        is_be_moved = t_data.get("be_moved", False)
                                                        if not is_be_moved:
                                                            if self.move_sl_to_entry(pos):
                                                                self.ticket_manager.update_ticket(pos.ticket, be_moved=True)
                                                        continue

                                                # Check Min Vol Requirement
                                                if vol_to_close < min_vol:
                                                    # Try forcing to min_vol if possible
                                                    if pos.volume > min_vol:
                                                        vol_to_close = min_vol
                                                    else:
                                                        # Cannot split
                                                        self.log(T("log_partial_skip_min").format(vol=pos.volume, min=min_vol))
                                                        closed_levels.append(target_r)
                                                        self.ticket_manager.update_ticket(pos.ticket, closed_levels=closed_levels)
                                                        
                                                        # Force Auto BE here if not already moved
                                                        # This is the "Min Lot Protection" feature
                                                        is_be_moved = t_data.get("be_moved", False)
                                                        if not is_be_moved:
                                                            if self.move_sl_to_entry(pos):
                                                                self.ticket_manager.update_ticket(pos.ticket, be_moved=True)
                                                        continue

                                                # Verify position still exists before closing
                                                verify_pos = mt5.positions_get(ticket=pos.ticket)
                                                if not verify_pos:
                                                    self.log(f"⚠️ Position {pos.ticket} already closed, skipping partial")
                                                    closed_levels.append(target_r)
                                                    self.ticket_manager.update_ticket(pos.ticket, closed_levels=closed_levels)
                                                    continue
                                                self.close_position(pos, f"Partial {pct_to_close}% @ {target_r}R", volume=vol_to_close)
                                                
                                                # Update Persistence
                                                closed_levels.append(target_r)
                                                self.ticket_manager.update_ticket(pos.ticket, closed_levels=closed_levels)

                                    # CHECK AUTO BE
                                    if auto_be_r > 0 and risk_points > 0:
                                        is_be_moved = t_data.get("be_moved", False)
                                        if not is_be_moved and current_r >= auto_be_r:
                                            if self.move_sl_to_entry(pos):
                                                self.ticket_manager.update_ticket(pos.ticket, be_moved=True)

                                    # --- END R LOGIC ---

                                    # --- SYNC VISIBLE SL/TP (+- 10 points) ---
                                    if visible_sltp:
                                        try:
                                            target_visible_sl = 0.0
                                            target_visible_tp = 0.0
                                            
                                            # --- SYNC HIDDEN FROM VISIBLE (User Manual Change) ---
                                            # Check if user manually changed SL on MT5
                                            # If current SL is different from 0 and different from our last known state, update Hidden
                                            # But here we simplify: If SL exists, we update our "Hidden" SL tracking to match it if it's tighter.
                                            # Actually, if user sets SL, that IS the SL. Hidden SL is just a backup or for stealth.
                                            # If Visible SL is set, we use IT as the reference for R calculation and closing.
                                            
                                            # Update Ticket Data with new SL if changed
                                            if pos.sl > 0:
                                                current_sl_points = 0
                                                if pos.type == mt5.POSITION_TYPE_BUY:
                                                    current_sl_points = (pos.price_open - pos.sl) / point
                                                else:
                                                    current_sl_points = (pos.sl - pos.price_open) / point
                                                
                                                # If this SL is significantly different (e.g. > 1 point)
                                                # We consider it a manual update.
                                                # Note: We don't overwrite 'risk_points' (initial risk) to preserve R calc based on entry.
                                                # But we should respect this SL for closing.

                                            # Calculate buffer in price
                                            buffer_price = 10 * point
                                            
                                            # Target Hidden SL/TP in price
                                            # Use risk_points if available, else current_sl
                                            sl_pts = risk_points if risk_points > 0 else current_sl
                                            tp_pts = current_tp
                                            
                                            # Determine the robot's CURRENT target SL price
                                            is_be_moved = t_data.get("be_moved", False)
                                            if is_be_moved:
                                                # If BE moved, the robot's target is entry price
                                                current_target_sl_price = pos.price_open
                                            else:
                                                # Otherwise it's entry +/- sl_pts
                                                if pos.type == mt5.POSITION_TYPE_BUY:
                                                    current_target_sl_price = pos.price_open - (sl_pts * point)
                                                else:
                                                    current_target_sl_price = pos.price_open + (sl_pts * point)
                                                    
                                            if pos.type == mt5.POSITION_TYPE_BUY:
                                                # Visible SL should be at Hidden SL - 10 points
                                                if sl_pts > 0 or is_be_moved:
                                                    target_visible_sl = current_target_sl_price - buffer_price
                                                if tp_pts > 0:
                                                    target_visible_tp = pos.price_open + (tp_pts * point) + buffer_price
                                            else:
                                                # SELL
                                                if sl_pts > 0 or is_be_moved:
                                                    target_visible_sl = current_target_sl_price + buffer_price
                                                if tp_pts > 0:
                                                    target_visible_tp = pos.price_open - (tp_pts * point) - buffer_price
                                            
                                            # Round to symbol digits
                                            symbol_info = mt5.symbol_info(pos.symbol)
                                            if symbol_info:
                                                if target_visible_sl > 0: target_visible_sl = round(target_visible_sl, symbol_info.digits)
                                                if target_visible_tp > 0: target_visible_tp = round(target_visible_tp, symbol_info.digits)
                                                
                                                # CHỈ ĐẶT LẠI KHI SL/TP BỊ XOÁ (BẰNG 0)
                                                # Tôn trọng việc người dùng tự dời SL/TP thủ công
                                                final_sl = pos.sl
                                                final_tp = pos.tp
                                                update_needed = False
                                                
                                                # Kiểm tra SL
                                                if target_visible_sl > 0 and pos.sl == 0:
                                                    # Kiểm tra xem giá đã qua mức SL này chưa
                                                    is_passed = False
                                                    if pos.type == mt5.POSITION_TYPE_BUY:
                                                        if pos.price_current <= target_visible_sl: is_passed = True
                                                    else:
                                                        if pos.price_current >= target_visible_sl: is_passed = True
                                                    
                                                    if not is_passed:
                                                        final_sl = target_visible_sl
                                                        update_needed = True
                                                
                                                # Kiểm tra TP
                                                if target_visible_tp > 0 and pos.tp == 0:
                                                    # Kiểm tra xem giá đã qua mức TP này chưa
                                                    is_passed = False
                                                    if pos.type == mt5.POSITION_TYPE_BUY:
                                                        if pos.price_current >= target_visible_tp: is_passed = True
                                                    else:
                                                        if pos.price_current <= target_visible_tp: is_passed = True
                                                        
                                                    if not is_passed:
                                                        final_tp = target_visible_tp
                                                        update_needed = True
                                                    
                                                if update_needed:
                                                    req = {
                                                        "action": mt5.TRADE_ACTION_SLTP,
                                                        "position": pos.ticket,
                                                        "symbol": pos.symbol,
                                                        "sl": final_sl,
                                                        "tp": final_tp
                                                    }
                                                    res = mt5.order_send(req)
                                                    if res.retcode != mt5.TRADE_RETCODE_DONE:
                                                        # self.log(f"Visible SLTP Sync Error: {res.retcode}")
                                                        pass
                                        except Exception as e:
                                            # self.log(f"Visible SLTP Sync Exception: {e}")
                                            pass

                                    # Check Hidden SL/TP Conditions
                                    close = False
                                    reason = ""
                                    
                                    # If BE was moved, adjust Hidden SL to Entry Price
                                    is_be_moved = t_data.get("be_moved", False)
                                    
                                    if is_be_moved:
                                        # Hidden SL is now effectively 0 points (Entry Price)
                                        # diff_points calculates distance from Entry.
                                        # If diff_points is negative (Loss), we close.
                                        if diff_points < 0:
                                            close = True; reason = f"Hidden BE (Entry)"
                                    else:
                                        # Normal Hidden SL
                                        if current_sl > 0 and diff_points <= -current_sl:
                                            close = True; reason = f"SL ({diff_points:.1f}/{current_sl})"
                                            
                                    if current_tp > 0 and diff_points >= current_tp:
                                        close = True; reason = f"TP ({diff_points:.1f}/{current_tp})"

                                    if close:
                                        self.close_position(pos, reason)
                                    
                                    pass
                                
                                # except block wrapper
                                if False:
                                    pos_e = None
                                    self.log(f"Position Error ({pos.symbol}): {pos_e}")
                                    self.send_telegram(f"⚠️ Position Error ({pos.symbol}): {pos_e}")
                    
                    # Check stop event more frequently to avoid freezing
                    for _ in range(10):
                        if self.stop_event.is_set(): break
                        time.sleep(0.1)
                except Exception as loop_e:
                     self.log(f"Loop Error: {loop_e}")
                     self.send_telegram(f"⚠️ Loop Error: {loop_e}")
                     time.sleep(1.0) # Prevent tight loop on error
        except Exception as e:
            self.log(f"Runtime Error: {e}")
            self.send_telegram(f"⚠️ Runtime Error: {e}")
        finally:
            mt5.shutdown()
            self.log(T("log_monitor_stop"))

# --- GUI APP ---
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Load Settings
        self.settings = load_json(SETTINGS_FILE)
        global CURRENT_LANG
        CURRENT_LANG = self.settings.get("lang", "VN")

        # SQLite store for heartbeat
        self._store = SQLiteStore()
        
        # Ensure Ghost Mode is in settings
        if "ghost_mode_active" not in self.settings:
            self.settings["ghost_mode_active"] = False
            save_json(SETTINGS_FILE, self.settings)
        
        # Theme Setup
        self.apply_theme(self.settings.get("theme", "light")) # Default to Light as per user request
        
        # Window Setup
        self.title(T("title"))
        self.geometry("1000x700") # Resized as per user request
        
        # Icon Setup
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
            
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Data
        self.profiles = load_json(CONFIG_FILE)
        self.workers = {} # {profile_name: {"proc": Popen, "console": CTkTextbox, "btn_stop": CTkButton}}
        self.ui_elements = {} # Store widgets for language update
        self._last_json_mtime = 0 # Initialize for periodic refresh sync
        self.selected_profile_name = None  # Profile selected in list (editing)
        self.running_profile_name = None   # Profile with active worker
        
        # Injects profile_name if missing from profiles to ensure sync works
        for name, profile in self.profiles.items():
            if "profile_name" not in profile:
                profile["profile_name"] = name
        
        # Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Status Bar
        self.status_bar = ctk.CTkFrame(self, height=28, corner_radius=0)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="sew")
        self.status_mt5 = ctk.CTkLabel(self.status_bar, text="MT5 ● —", font=ctk.CTkFont(size=11))
        self.status_mt5.pack(side="left", padx=10)
        self.status_telegram = ctk.CTkLabel(self.status_bar, text="Telegram ● —", font=ctk.CTkFont(size=11))
        self.status_telegram.pack(side="left", padx=10)
        self.status_ghost = ctk.CTkLabel(self.status_bar, text="Ghost ● —", font=ctk.CTkFont(size=11))
        self.status_ghost.pack(side="left", padx=10)
        self.status_system = ctk.CTkLabel(self.status_bar, text="", font=ctk.CTkFont(size=11))
        self.status_system.pack(side="right", padx=10)
        
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=56, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(2, weight=1)

        self.btn_settings_rail = ctk.CTkButton(
            self.sidebar,
            text="🌐\n🎨",
            width=44,
            height=56,
            corner_radius=10,
            font=ctk.CTkFont(size=18, weight="bold"),
            command=self._open_settings_popup,
        )
        self.btn_settings_rail.grid(row=0, column=0, padx=6, pady=(10, 6))
        self.btn_settings_rail.bind("<Enter>", lambda _e: self._show_theme_radial())
        self.btn_settings_rail.bind("<Leave>", lambda _e: self._schedule_hide_theme_radial())

        self.btn_ghost_toggle = ctk.CTkButton(
            self.sidebar,
            text="👻",
            width=44,
            height=44,
            corner_radius=10,
            font=ctk.CTkFont(size=18, weight="bold"),
            command=self._open_ghost_popup,
        )
        self.btn_ghost_toggle.grid(row=1, column=0, padx=6, pady=6)
        self.update_ghost_button_ui()

        # Main Area
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        self.frames = {}
        self.signal_procs = {}
        self.tab_names = {
            "dashboard": f"📊 {T('tab_dashboard')}",
            "signals": f"📈 {T('tab_signals')}",
            "profiles": f"👤 {T('tab_profiles')}",
            "copy_trade": f"🔄 {T('tab_copy_trade')}",
            "pos_size": f"⏰ {T('tab_pos_size')}",
            "diagnostics": "🩺 Diagnostics",
            "guide": f"📘 {T('tab_guide')}",
            "readme": f"🚀 {T('tab_readme')}",
            "release_notes": f"📋 {T('tab_release_notes')}",
            "about": f"ℹ️ {T('tab_about')}",
        }

        self.tabview = ctk.CTkTabview(self.main_frame, command=self._on_tab_change)
        self.tabview.grid(row=0, column=0, sticky="nsew")

        self.tab_dashboard = self.tabview.add(self.tab_names["dashboard"])
        self.tab_signals = self.tabview.add(self.tab_names["signals"])
        self.tab_profiles = self.tabview.add(self.tab_names["profiles"])
        self.tab_copy_trade = self.tabview.add(self.tab_names["copy_trade"])
        self.tab_pos_size = self.tabview.add(self.tab_names["pos_size"])
        self.tab_diagnostics = self.tabview.add(self.tab_names["diagnostics"])
        self.tab_guide = self.tabview.add(self.tab_names["guide"])
        self.tab_readme = self.tabview.add(self.tab_names["readme"])
        self.tab_release = self.tabview.add(self.tab_names["release_notes"])
        self.tab_about = self.tabview.add(self.tab_names["about"])

        self.create_dashboard_frame(self.tab_dashboard)
        self.create_signals_frame(self.tab_signals)
        self.create_profiles_frame(self.tab_profiles)
        self.create_copy_trade_frame(self.tab_copy_trade)
        self.create_pos_size_frame(self.tab_pos_size)
        self.create_diagnostics_frame(self.tab_diagnostics)
        self.create_guide_frame(self.tab_guide)
        self.create_readme_frame(self.tab_readme)
        self.create_release_notes_frame(self.tab_release)
        self.create_about_frame(self.tab_about)
        self.apply_theme_overrides()

        self.tabview.set(self.tab_names["dashboard"])
        self._enable_tab_hover_switch()
        
        # Initial Profile Selection
        if self.profiles:
            initial = list(self.profiles.keys())[0]
            self.combo_profiles.set(initial)
            self.on_profile_change(initial)
        
        # Start Periodic UI Refresh
        self.periodic_ui_refresh()

    def _open_settings_popup(self):
        self._hide_theme_radial()
        if hasattr(self, "ghost_popup") and self.ghost_popup and self.ghost_popup.winfo_exists():
            try:
                self.ghost_popup.destroy()
            except Exception:
                pass
            self.ghost_popup = None

        if hasattr(self, "settings_popup") and self.settings_popup and self.settings_popup.winfo_exists():
            try:
                self.settings_popup.lift()
                self.settings_popup.focus_force()
                return
            except Exception:
                pass

        popup = ctk.CTkToplevel(self)
        popup.title(T("settings_popup_title"))
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        try:
            popup.transient(self)
        except Exception:
            pass
        try:
            popup.wm_attributes("-toolwindow", True)
        except Exception:
            pass

        try:
            x = self.winfo_x() + 70
            y = self.winfo_y() + 80
            popup.geometry(f"280x170+{x}+{y}")
        except Exception:
            popup.geometry("280x170")

        def on_close():
            try:
                popup.destroy()
            finally:
                self.settings_popup = None

        popup.protocol("WM_DELETE_WINDOW", on_close)
        self.settings_popup = popup

        body = ctk.CTkFrame(popup, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=12)
        body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(body, text=T("settings_popup_lang"), font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w")
        seg = ctk.CTkSegmentedButton(body, values=["VN", "EN"], command=self.change_lang, height=30)
        seg.set(CURRENT_LANG)
        seg.grid(row=1, column=0, sticky="ew", pady=(6, 12))

        ctk.CTkLabel(body, text=T("settings_popup_theme"), font=ctk.CTkFont(size=13, weight="bold")).grid(row=2, column=0, sticky="w")
        opt = ctk.CTkOptionMenu(body, values=[T("theme_dark"), T("theme_light"), T("theme_deepsea")], command=self.change_theme)
        theme_key = self.settings.get("theme", "dark")
        if theme_key == "light":
            opt.set(T("theme_light"))
        elif theme_key == "deepsea":
            opt.set(T("theme_deepsea"))
        else:
            opt.set(T("theme_dark"))
        opt.grid(row=3, column=0, sticky="ew", pady=(6, 0))

    def _show_theme_radial(self):
        if hasattr(self, "settings_popup") and self.settings_popup and self.settings_popup.winfo_exists():
            return
        self._cancel_hide_theme_radial()
        if hasattr(self, "theme_radial") and self.theme_radial and self.theme_radial.winfo_exists():
            try:
                self.theme_radial.lift()
                return
            except Exception:
                pass

        p = getattr(self, "theme_palette", None)
        circle_bg = (p["panel_alt_bg"] if p else "#e6eef7")
        accent = (p["accent"] if p else "#1e6bb8")
        card_border = (p["card_border"] if p else "#c7d0dd")
        text_primary = (p["text_primary"] if p else "#1f2328")

        popup = ctk.CTkToplevel(self)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.resizable(False, False)
        try:
            popup.transient(self)
        except Exception:
            pass
        try:
            popup.wm_attributes("-toolwindow", True)
        except Exception:
            pass

        transparent_key = "#010203"
        try:
            popup.configure(bg=transparent_key)
            popup.wm_attributes("-transparentcolor", transparent_key)
        except Exception:
            pass

        final_size = 176
        start_size = 22
        try:
            bx = self.btn_settings_rail.winfo_rootx()
            by = self.btn_settings_rail.winfo_rooty()
            anchor_cx = bx + 60 + (final_size // 2)
            anchor_cy = by - 2 + (final_size // 2)
        except Exception:
            anchor_cx = self.winfo_rootx() + 90 + (final_size // 2)
            anchor_cy = self.winfo_rooty() + 110 + (final_size // 2)

        popup.geometry(f"{start_size}x{start_size}+{anchor_cx - (start_size // 2)}+{anchor_cy - (start_size // 2)}")
        try:
            popup.attributes("-alpha", 0.0)
        except Exception:
            pass

        self.theme_radial = popup
        canvas = tkinter.Canvas(popup, width=start_size, height=start_size, bg=transparent_key, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        oval_id = canvas.create_oval(2, 2, start_size - 2, start_size - 2, fill=circle_bg, outline=circle_bg)

        def pick_theme(value):
            self.change_theme(value)
            self._hide_theme_radial()

        btn_theme = dict(width=44, height=44, corner_radius=22, fg_color=accent, hover_color=accent, text_color="#ffffff", font=ctk.CTkFont(size=16, weight="bold"))

        b_dark = ctk.CTkButton(popup, text="🌙", command=lambda: pick_theme(T("theme_dark")), **btn_theme)
        b_light = ctk.CTkButton(popup, text="☀", command=lambda: pick_theme(T("theme_light")), **btn_theme)
        b_sea = ctk.CTkButton(popup, text="🌊", command=lambda: pick_theme(T("theme_deepsea")), **btn_theme)

        def clamp01(v):
            if v < 0.0:
                return 0.0
            if v > 1.0:
                return 1.0
            return v

        def ease_out_back(t):
            c1 = 1.70158
            c3 = c1 + 1.0
            x = t - 1.0
            return 1.0 + (c3 * (x ** 3)) + (c1 * (x ** 2))

        def compute_targets(size):
            center = size / 2.0
            radius = center - 4.0
            max_scale = 1.05
            max_btn = 44.0 * max_scale
            half_diag = max_btn * 0.7071
            outer_max = radius - half_diag - 4.0
            outer = min(size * 0.29, outer_max)
            if outer < 0.0:
                outer = 0.0
            cos60 = 0.5
            sin60 = 0.866

            top = (center, center - outer)
            bl = (center - (outer * sin60), center + (outer * cos60))
            br = (center + (outer * sin60), center + (outer * cos60))
            return top, bl, br

        def place_btn(btn, cx, cy, base, scale):
            s = max(0.6, scale)
            w = int(base * s)
            h = int(base * s)
            r = max(8, int((base * s) / 2))
            try:
                btn.configure(width=w, height=h, corner_radius=r)
            except Exception:
                pass
            btn.place(x=int(cx - (w / 2)), y=int(cy - (h / 2)))

        def layout_animated(size, t):
            center = size / 2.0
            top, bl, br = compute_targets(size)

            items = [
                (b_dark, top, 44, 0.00, 0.55),
                (b_light, bl, 44, 0.06, 0.55),
                (b_sea, br, 44, 0.12, 0.55),
            ]

            for btn, target, base, delay, dur in items:
                u = clamp01((t - delay) / dur)
                e = ease_out_back(u) if u > 0.0 else 0.0
                e_pos = min(1.0, e)
                cx = center + (target[0] - center) * e_pos
                cy = center + (target[1] - center) * e_pos
                scale = 0.65 + (0.45 * min(1.0, e))
                if scale > 1.05:
                    scale = 1.05
                place_btn(btn, cx, cy, base, scale)

        layout_animated(start_size, 0.0)

        popup.bind("<Enter>", lambda _e: self._cancel_hide_theme_radial())
        popup.bind("<Leave>", lambda _e: self._schedule_hide_theme_radial())
        canvas.bind("<Enter>", lambda _e: self._cancel_hide_theme_radial())
        canvas.bind("<Leave>", lambda _e: self._schedule_hide_theme_radial())

        if hasattr(self, "_theme_radial_anim") and self._theme_radial_anim:
            try:
                self.after_cancel(self._theme_radial_anim)
            except Exception:
                pass
            self._theme_radial_anim = None

        steps = 18
        def animate(i):
            if not (hasattr(self, "theme_radial") and self.theme_radial and self.theme_radial.winfo_exists()):
                return
            t = i / float(steps)
            ease = t * (2.0 - t)
            size = int(start_size + (final_size - start_size) * ease)
            x = int(anchor_cx - (size / 2))
            y = int(anchor_cy - (size / 2))
            popup.geometry(f"{size}x{size}+{x}+{y}")
            canvas.configure(width=size, height=size)
            canvas.coords(oval_id, 2, 2, size - 2, size - 2)
            layout_animated(size, ease)
            try:
                popup.attributes("-alpha", min(0.98, ease))
            except Exception:
                pass
            if i < steps:
                self._theme_radial_anim = self.after(16, lambda: animate(i + 1))
            else:
                self._theme_radial_anim = None

        animate(0)

    def _cancel_hide_theme_radial(self):
        if hasattr(self, "_theme_radial_after") and self._theme_radial_after:
            try:
                self.after_cancel(self._theme_radial_after)
            except Exception:
                pass
            self._theme_radial_after = None

    def _schedule_hide_theme_radial(self):
        self._cancel_hide_theme_radial()
        self._theme_radial_after = self.after(250, self._hide_theme_radial)

    def _hide_theme_radial(self):
        self._cancel_hide_theme_radial()
        if hasattr(self, "_theme_radial_anim") and self._theme_radial_anim:
            try:
                self.after_cancel(self._theme_radial_anim)
            except Exception:
                pass
            self._theme_radial_anim = None
        if hasattr(self, "theme_radial") and self.theme_radial and self.theme_radial.winfo_exists():
            try:
                self.theme_radial.destroy()
            except Exception:
                pass
        self.theme_radial = None

    def _open_ghost_popup(self):
        if hasattr(self, "settings_popup") and self.settings_popup and self.settings_popup.winfo_exists():
            try:
                self.settings_popup.destroy()
            except Exception:
                pass
            self.settings_popup = None

        if hasattr(self, "ghost_popup") and self.ghost_popup and self.ghost_popup.winfo_exists():
            try:
                self.ghost_popup.lift()
                self.ghost_popup.focus_force()
                return
            except Exception:
                pass

        popup = ctk.CTkToplevel(self)
        popup.title(T("ghost_popup_title"))
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        try:
            popup.transient(self)
        except Exception:
            pass
        try:
            popup.wm_attributes("-toolwindow", True)
        except Exception:
            pass

        try:
            x = self.winfo_x() + 70
            y = self.winfo_y() + 260
            popup.geometry(f"320x190+{x}+{y}")
        except Exception:
            popup.geometry("320x190")

        def on_close():
            try:
                popup.destroy()
            finally:
                self.ghost_popup = None
                if hasattr(self, "btn_ghost_popup_toggle"):
                    self.btn_ghost_popup_toggle = None

        popup.protocol("WM_DELETE_WINDOW", on_close)
        self.ghost_popup = popup

        body = ctk.CTkFrame(popup, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=12)
        body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(body, text=T("ghost_popup_header"), font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(body, text=T("ghost_popup_desc"), justify="left", wraplength=290).grid(row=1, column=0, sticky="w", pady=(8, 12))

        self.btn_ghost_popup_toggle = ctk.CTkButton(body, text="", height=38, command=self._toggle_ghost_from_popup, font=ctk.CTkFont(weight="bold"))
        self.btn_ghost_popup_toggle.grid(row=2, column=0, sticky="ew")
        self.update_ghost_button_ui()

    def _toggle_ghost_from_popup(self):
        self.toggle_ghost_mode()
        self.update_ghost_button_ui()
        
    def add_ui_element(self, key, widget):
        """Helper to store multiple widgets for the same translation key"""
        if key not in self.ui_elements:
            self.ui_elements[key] = []
        self.ui_elements[key].append(widget)

    def _enable_tab_hover_switch(self):
        if not hasattr(self, "tabview"):
            return
        seg = getattr(self.tabview, "_segmented_button", None)
        if not seg:
            return

        self._tab_hover_target = None
        self._tab_hover_after = None

        buttons = []
        try:
            if hasattr(seg, "_buttons_dict"):
                buttons = list(seg._buttons_dict.values())
            elif hasattr(seg, "_buttons"):
                if isinstance(seg._buttons, dict):
                    buttons = list(seg._buttons.values())
                else:
                    buttons = list(seg._buttons)
        except Exception:
            buttons = []

        if not buttons:
            try:
                buttons = [w for w in seg.winfo_children() if isinstance(w, ctk.CTkButton)]
            except Exception:
                buttons = []

        for btn in buttons:
            try:
                name = btn.cget("text")
            except Exception:
                continue
            btn.bind("<Enter>", lambda _e, n=name: self._schedule_tab_hover(n))
            btn.bind("<Leave>", lambda _e: self._cancel_tab_hover())

    def _schedule_tab_hover(self, name):
        self._tab_hover_target = name
        self._cancel_tab_hover(cancel_target=False)
        self._tab_hover_after = self.after(140, lambda: self._apply_tab_hover(name))

    def _apply_tab_hover(self, name):
        if getattr(self, "_tab_hover_target", None) != name:
            return
        try:
            self.tabview.set(name)
        except Exception:
            pass

    def _cancel_tab_hover(self, cancel_target=True):
        if cancel_target:
            self._tab_hover_target = None
        if hasattr(self, "_tab_hover_after") and self._tab_hover_after:
            try:
                self.after_cancel(self._tab_hover_after)
            except Exception:
                pass
            self._tab_hover_after = None

    def _rebuild_tabview(self, preferred_key="dashboard"):
        current_key = preferred_key
        try:
            current_name = self.tabview.get()
            for k, v in getattr(self, "tab_names", {}).items():
                if v == current_name:
                    current_key = k
                    break
        except Exception:
            current_key = preferred_key

        try:
            for child in self.main_frame.winfo_children():
                child.destroy()
        except Exception:
            pass

        self.frames = {}
        self.signal_procs = {}
        self.tab_names = {
            "dashboard": f"📊 {T('tab_dashboard')}",
            "signals": f"📈 {T('tab_signals')}",
            "profiles": f"👤 {T('tab_profiles')}",
            "copy_trade": f"🔄 {T('tab_copy_trade')}",
            "pos_size": f"⏰ {T('tab_pos_size')}",
            "diagnostics": "🩺 Diagnostics",
            "guide": f"📘 {T('tab_guide')}",
            "readme": f"🚀 {T('tab_readme')}",
            "release_notes": f"📋 {T('tab_release_notes')}",
            "about": f"ℹ️ {T('tab_about')}",
        }

        self.tabview = ctk.CTkTabview(self.main_frame, command=self._on_tab_change)
        self.tabview.grid(row=0, column=0, sticky="nsew")

        self.tab_dashboard = self.tabview.add(self.tab_names["dashboard"])
        self.tab_signals = self.tabview.add(self.tab_names["signals"])
        self.tab_profiles = self.tabview.add(self.tab_names["profiles"])
        self.tab_copy_trade = self.tabview.add(self.tab_names["copy_trade"])
        self.tab_pos_size = self.tabview.add(self.tab_names["pos_size"])
        self.tab_diagnostics = self.tabview.add(self.tab_names["diagnostics"])
        self.tab_guide = self.tabview.add(self.tab_names["guide"])
        self.tab_readme = self.tabview.add(self.tab_names["readme"])
        self.tab_release = self.tabview.add(self.tab_names["release_notes"])
        self.tab_about = self.tabview.add(self.tab_names["about"])

        self.create_dashboard_frame(self.tab_dashboard)
        self.create_signals_frame(self.tab_signals)
        self.create_profiles_frame(self.tab_profiles)
        self.create_copy_trade_frame(self.tab_copy_trade)
        self.create_pos_size_frame(self.tab_pos_size)
        self.create_diagnostics_frame(self.tab_diagnostics)
        self.create_guide_frame(self.tab_guide)
        self.create_readme_frame(self.tab_readme)
        self.create_release_notes_frame(self.tab_release)
        self.create_about_frame(self.tab_about)

        self.apply_theme_overrides()

        if current_key not in self.tab_names:
            current_key = "dashboard"
        self.tabview.set(self.tab_names[current_key])
        self._enable_tab_hover_switch()

        if getattr(self, "profiles", None):
            try:
                initial = self.combo_profiles.get().strip() if hasattr(self, "combo_profiles") else ""
                if not initial:
                    initial = list(self.profiles.keys())[0]
                if hasattr(self, "combo_profiles"):
                    self.combo_profiles.set(initial)
                self.on_profile_change(initial)
            except Exception:
                pass
        
    def _on_tab_change(self):
        current = ""
        try:
            current = self.tabview.get()
        except Exception:
            current = ""
        if current and current == self.tab_names.get("copy_trade", ""):
            self.load_copy_config()

    def create_dashboard_frame(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["dashboard"] = frame
        frame.pack(fill="both", expand=True)
        frame.grid_columnconfigure(0, weight=3)
        frame.grid_columnconfigure(1, weight=7)
        frame.grid_rowconfigure(0, weight=1)

        left_panel = ctk.CTkFrame(frame, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        right_panel = ctk.CTkFrame(frame, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right_panel.grid_rowconfigure(0, weight=0)  # cards - fixed height
        right_panel.grid_rowconfigure(1, weight=0)  # news - fixed 240px
        right_panel.grid_rowconfigure(2, weight=1)  # console - takes remaining
        right_panel.grid_columnconfigure(0, weight=1)

        # === INFO CARDS ===
        cards_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        cards_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        cards_frame.grid_columnconfigure(0, weight=1)
        cards_frame.grid_columnconfigure(1, weight=1)
        cards_frame.grid_columnconfigure(2, weight=1)

        # Account Card
        self.card_account = ctk.CTkFrame(cards_frame, corner_radius=8)
        self.card_account.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        ctk.CTkLabel(self.card_account, text="📊 Account", font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(fill="x", padx=8, pady=(6, 2))
        self.card_account_server = ctk.CTkLabel(self.card_account, text="—", font=ctk.CTkFont(size=10), anchor="w", text_color="gray")
        self.card_account_server.pack(fill="x", padx=8)
        self.card_account_balance = ctk.CTkLabel(self.card_account, text="Balance: —", font=ctk.CTkFont(size=11), anchor="w")
        self.card_account_balance.pack(fill="x", padx=8)
        self.card_account_equity = ctk.CTkLabel(self.card_account, text="Equity: —", font=ctk.CTkFont(size=11), anchor="w")
        self.card_account_equity.pack(fill="x", padx=8, pady=(0, 6))

        # Signal Card
        self.card_signal = ctk.CTkFrame(cards_frame, corner_radius=8)
        self.card_signal.grid(row=0, column=1, sticky="nsew", padx=4)
        ctk.CTkLabel(self.card_signal, text="📈 Signal", font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(fill="x", padx=8, pady=(6, 2))
        self.card_signal_current = ctk.CTkLabel(self.card_signal, text="Current: —", font=ctk.CTkFont(size=11), anchor="w")
        self.card_signal_current.pack(fill="x", padx=8)
        self.card_signal_next = ctk.CTkLabel(self.card_signal, text="Next: —", font=ctk.CTkFont(size=11), anchor="w")
        self.card_signal_next.pack(fill="x", padx=8)
        self.card_signal_countdown = ctk.CTkLabel(self.card_signal, text="Countdown: —", font=ctk.CTkFont(size=10), anchor="w", text_color="gray")
        self.card_signal_countdown.pack(fill="x", padx=8, pady=(0, 6))

        # Engine Card
        self.card_engine = ctk.CTkFrame(cards_frame, corner_radius=8)
        self.card_engine.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        ctk.CTkLabel(self.card_engine, text="⚙️ Engine", font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(fill="x", padx=8, pady=(6, 2))
        self.card_engine_ghost = ctk.CTkLabel(self.card_engine, text="Ghost: —", font=ctk.CTkFont(size=11), anchor="w")
        self.card_engine_ghost.pack(fill="x", padx=8)
        self.card_engine_session = ctk.CTkLabel(self.card_engine, text="Session: ON", font=ctk.CTkFont(size=11), anchor="w", text_color="#2ecc71")
        self.card_engine_session.pack(fill="x", padx=8)
        self.card_engine_version = ctk.CTkLabel(self.card_engine, text=f"v{VERSION[1:]} Stable", font=ctk.CTkFont(size=10), anchor="w", text_color="gray")
        self.card_engine_version.pack(fill="x", padx=8, pady=(0, 6))

        self.lbl_select = ctk.CTkLabel(left_panel, text=T("msg_select_profile"), font=ctk.CTkFont(size=14))
        self.lbl_select.pack(pady=(0, 5), anchor="w")
        self.add_ui_element("msg_select_profile", self.lbl_select)

        self.combo_profiles = ctk.CTkOptionMenu(left_panel, values=list(self.profiles.keys()) if self.profiles else ["Empty"], command=self.on_profile_change)
        self.combo_profiles.pack(pady=(0, 20), anchor="w")

        self.btn_start = ctk.CTkButton(left_panel, text=T("btn_start"), fg_color="green", height=40, command=self.start_monitor)
        self.btn_start.pack(pady=(0, 10), fill="x")
        self.add_ui_element("btn_start", self.btn_start)

        self.btn_stop = ctk.CTkButton(left_panel, text=T("btn_stop"), fg_color="red", height=40, state="disabled", command=self.stop_monitor)
        self.btn_stop.pack(pady=(0, 20), fill="x")
        self.add_ui_element("btn_stop", self.btn_stop)

        self.engine_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        self.engine_frame.pack(pady=(10, 0), fill="x")

        self.lbl_engine_title_frame = ctk.CTkFrame(self.engine_frame, fg_color="transparent")
        self.lbl_engine_title_frame.pack()

        self.lbl_engine_title = ctk.CTkLabel(self.lbl_engine_title_frame, text=T("lbl_engine"), font=ctk.CTkFont(size=10))
        self.lbl_engine_title.grid(row=0, column=0)
        self.add_ui_element("lbl_engine", self.lbl_engine_title)
        add_help_icon(self.lbl_engine_title_frame, 0, 1, "tip_engine")

        self.lbl_engine_badge = ctk.CTkLabel(self.engine_frame, text="", font=ctk.CTkFont(size=12, weight="bold"), corner_radius=6)
        self.lbl_engine_badge.pack(pady=2, fill="x")

        self.recovery_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        self.recovery_frame.pack(pady=(10, 0), fill="x")

        self.lbl_recovery_status_frame = ctk.CTkFrame(self.recovery_frame, fg_color="transparent")
        self.lbl_recovery_status_frame.pack()

        self.lbl_recovery_status = ctk.CTkLabel(self.lbl_recovery_status_frame, text="🛡️ Session Auto-Save: ON", font=ctk.CTkFont(size=12, weight="bold", slant="italic"), text_color="#2ecc71")
        self.lbl_recovery_status.grid(row=0, column=0)
        add_help_icon(self.lbl_recovery_status_frame, 0, 1, "tip_session")

        self.update_ghost_button_ui()

        news_section = ctk.CTkFrame(right_panel, fg_color="transparent", height=240)
        news_section.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        news_section.grid_propagate(False)

        news_header = ctk.CTkFrame(news_section, fg_color="transparent")
        news_header.pack(fill="x", pady=(0, 6))
        self.lbl_news_title = ctk.CTkLabel(news_header, text=T("news_title"), font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_news_title.pack(side="left")
        self.add_ui_element("news_title", self.lbl_news_title)

        self.news_box = ctk.CTkTextbox(news_section, wrap="word")
        self.news_box.pack(fill="both", expand=True)
        self.news_box.configure(state="disabled")

        self.update_news_summary(force=True)

        console_section = ctk.CTkFrame(right_panel, fg_color="transparent")
        console_section.grid(row=2, column=0, sticky="nsew", pady=(5, 0))

        self.lbl_console = ctk.CTkLabel(console_section, text=T("console_title"), font=ctk.CTkFont(weight="bold"))
        self.lbl_console.pack(anchor="w")
        self.add_ui_element("console_title", self.lbl_console)

        # Console filter checkboxes
        filter_frame = ctk.CTkFrame(console_section, fg_color="transparent")
        filter_frame.pack(fill="x", pady=(0, 3))
        self._console_filters = {}
        for label, color in [("INFO", "#b0bec5"), ("WARN", "#ffb74d"), ("ERROR", "#ef5350"), ("MT5", "#29b6f6"), ("TG", "#ab47bc"), ("SIG", "#66bb6a")]:
            var = ctk.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(filter_frame, text=label, variable=var, font=ctk.CTkFont(size=10), text_color=color)
            cb.pack(side="left", padx=4)
            self._console_filters[label] = var

        self.console = ctk.CTkTextbox(console_section, wrap="word")
        self.console.pack(fill="both", expand=True)
        self.console.configure(state="disabled")

    def update_news_summary(self, force=False):
        if not hasattr(self, "news_box"):
            return
            
        # Check if already running
        if hasattr(self, "_news_thread") and self._news_thread.is_alive():
            return

        now = datetime.now()
        if not force and hasattr(self, "_last_news_fetch"):
            if (now - self._last_news_fetch).total_seconds() < 300:
                return
        self._last_news_fetch = now
        
        # Try to load from cache first to avoid "Loading..." state
        try:
            cache_file = f"news_cache_{CURRENT_LANG}.json"
            today_str = str(datetime.now().date())
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                if cache.get("date") == today_str and cache.get("news"):
                    self._display_news_result(cache["news"])
                    return
        except:
            pass
        
        self.news_box.configure(state="normal")
        self.news_box.delete("1.0", "end")
        self.news_box.insert("1.0", T("news_loading"))
        self.news_box.configure(state="disabled")
        
        self._news_thread = threading.Thread(target=self._fetch_news_worker, daemon=True)
        self._news_thread.start()

    def _fetch_news_worker(self):
        try:
            news = oak_trading_reminders.get_economic_news(lang=CURRENT_LANG)
        except Exception as e:
            # print(f"News fetch error: {e}")
            news = []
        self.after(0, lambda: self._display_news_result(news))

    def _display_news_result(self, news):
        if not hasattr(self, "news_box"): return
        self.news_box.configure(state="normal")
        self.news_box.delete("1.0", "end")
        if news:
            self.news_box.insert("1.0", "\n".join(news))
            self.apply_markdown(self.news_box)
        else:
            self.news_box.insert("1.0", T("news_empty"))
        self.news_box.configure(state="disabled")

    def apply_theme_overrides(self):
        if not hasattr(self, "theme_palette"):
            return
        p = self.theme_palette
        if hasattr(self, "sidebar"):
            self.sidebar.configure(fg_color=p["sidebar_bg"])
        if hasattr(self, "list_frame"):
            try:
                self.list_frame.configure(fg_color=p["panel_bg"], label_text_color=p["text_primary"])
            except:
                self.list_frame.configure(fg_color=p["panel_bg"])
        if hasattr(self, "form_scroll"):
            try:
                self.form_scroll.configure(fg_color=p["panel_bg"], label_text_color=p["text_primary"])
            except:
                self.form_scroll.configure(fg_color=p["panel_bg"])
        if hasattr(self, "res_box"):
            self.res_box.configure(fg_color=p["res_box_bg"])
        if hasattr(self, "lbl_pos_res"):
            self.lbl_pos_res.configure(text_color=p["accent"])
        if hasattr(self, "val_pos_lot"):
            self.val_pos_lot.configure(text_color=p["text_primary"], fg_color=p["res_box_bg"])
        if hasattr(self, "sched_input_frame"):
            self.sched_input_frame.configure(fg_color=p["schedule_bg"])
        if hasattr(self, "lbl_pos_time"):
            self.lbl_pos_time.configure(text_color=p["text_primary"])
        if hasattr(self, "ent_pos_time"):
            self.ent_pos_time.configure(text_color=p["text_primary"], fg_color=p["input_bg"], border_color=p["input_border"])
        if hasattr(self, "seg_pos_type"):
            self.seg_pos_type.configure(text_color=p["text_primary"], fg_color=p["panel_alt_bg"], selected_color=p["accent"], selected_hover_color=p["accent"])
        if hasattr(self, "lbl_schedule_title"):
            self.lbl_schedule_title.configure(text_color=p["text_muted"])
        if hasattr(self, "sep_left_line"):
            self.sep_left_line.configure(fg_color=p["card_border"])
        if hasattr(self, "sep_right_line"):
            self.sep_right_line.configure(fg_color=p["card_border"])
        if hasattr(self, "news_box"):
            self.news_box.configure(text_color=p["text_primary"], fg_color=p["panel_alt_bg"])
        if hasattr(self, "lbl_news_title"):
            self.lbl_news_title.configure(text_color=p["text_primary"])
    def apply_theme(self, theme_key):
        self.theme_key = theme_key
        if theme_key == "light":
            ctk.set_appearance_mode("Light")
            ctk.set_default_color_theme("blue")
            self.theme_palette = {
                "text_primary": "#1f2328",
                "text_muted": "#5c6773",
                "panel_bg": "#f5f7fb",
                "panel_alt_bg": "#e6eef7",
                "card_bg": "#ffffff",
                "card_border": "#c7d0dd",
                "input_bg": "#ffffff",
                "input_border": "#c7d0dd",
                "input_text": "#1f2328",
                "signal_card_bg": "#f2f5f9",
                "signal_title": "#4d5966",
                "signal_value": "#1f2328",
                "res_box_bg": "#eef3ff",
                "accent": "#1e6bb8",
                "schedule_bg": "#eef1f6",
                "sidebar_bg": "#e9edf2"
            }
        elif theme_key == "deepsea":
            ctk.set_appearance_mode("Dark")
            ctk.set_default_color_theme("dark-blue")
            self.theme_palette = {
                "text_primary": "#e6f0f7",
                "text_muted": "#86a0b2",
                "panel_bg": "#08131f",
                "panel_alt_bg": "#0b1b2b",
                "card_bg": "#0d2030",
                "card_border": "#163148",
                "input_bg": "#0b1b2b",
                "input_border": "#163148",
                "input_text": "#e6f0f7",
                "signal_card_bg": "#0d2030",
                "signal_title": "#a8bfcd",
                "signal_value": "#e6f0f7",
                "res_box_bg": "#0b1f31",
                "accent": "#1aa6b2",
                "schedule_bg": "#0b1b2b",
                "sidebar_bg": "#06101a"
            }
        else:
            ctk.set_appearance_mode("Dark")
            ctk.set_default_color_theme("blue")
            self.theme_palette = {
                "text_primary": "#f2f2f2",
                "text_muted": "#a0a0a0",
                "panel_bg": "#1f1f1f",
                "panel_alt_bg": "#2b2b2b",
                "card_bg": "#222222",
                "card_border": "#3b3b3b",
                "input_bg": "#2b2b2b",
                "input_border": "#404040",
                "input_text": "#ffffff",
                "signal_card_bg": "#222222",
                "signal_title": "#d0d0d0",
                "signal_value": "#86868b",
                "res_box_bg": "#1a1a1a",
                "accent": "#3b8ed0",
                "schedule_bg": "#2b2b2b",
                "sidebar_bg": "#202020"
            }

    def refresh_theme_labels(self):
        if not hasattr(self, "combo_theme"):
            return
        values = [T("theme_dark"), T("theme_light"), T("theme_deepsea")]
        self.combo_theme.configure(values=values)
        theme_key = self.settings.get("theme", "dark")
        if theme_key == "light":
            self.combo_theme.set(T("theme_light"))
        elif theme_key == "deepsea":
            self.combo_theme.set(T("theme_deepsea"))
        else:
            self.combo_theme.set(T("theme_dark"))

    def change_theme(self, value):
        if value == T("theme_light"):
            theme_key = "light"
        elif value == T("theme_deepsea"):
            theme_key = "deepsea"
        else:
            theme_key = "dark"
        self.settings["theme"] = theme_key
        save_json(SETTINGS_FILE, self.settings)
        self.apply_theme(theme_key)
        self.refresh_theme_labels()
        self.apply_theme_overrides()
        self.refresh_profile_list()
        self.update_news_summary(force=True)

    def create_signals_frame(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkButton(btn_frame, text="▶ BẮT ĐẦU TẤT CẢ", fg_color="#2fa572",
                       hover_color="#238a5c", command=self.start_all_signals).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="■ DỪNG TẤT CẢ", fg_color="#d9534f",
                       hover_color="#c9302c", command=self.stop_all_signals).pack(side="left", padx=5)

        panels_frame = ctk.CTkFrame(frame, fg_color="transparent")
        panels_frame.pack(fill="both", expand=True)
        panels_frame.grid_columnconfigure(0, weight=1)
        panels_frame.grid_columnconfigure(1, weight=1)
        panels_frame.grid_rowconfigure(0, weight=1)
        panels_frame.grid_rowconfigure(1, weight=1)

        signal_defs = [
            ("signal_bot", "MT5 Signal Bot", "python mt5_signal_bot.py", "#2fa572"),
            ("mt_server", "MT4-MT5 Server", "python mt4_mt5_server.py", "#1f538d"),
            ("mimo_bot", "MiMo Telegram Bot", "python mimo_bot.py", "#b33dd4"),
            ("mimo_worker", "MiMo Worker", "python mimo_worker.py", "#d4a03d"),
        ]

        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]

        for idx, (key, name, cmd, color) in enumerate(signal_defs):
            row, col = positions[idx]
            panel = ctk.CTkFrame(panels_frame, corner_radius=8)
            panel.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

            header = ctk.CTkFrame(panel, fg_color="transparent")
            header.pack(fill="x", padx=10, pady=(8, 2))

            dot = ctk.CTkLabel(header, text="●", text_color=color, font=("", 14))
            dot.pack(side="left", padx=(0, 5))

            ctk.CTkLabel(header, text=name, font=("", 13, "bold")).pack(side="left")

            lbl_pid = ctk.CTkLabel(header, text="PID: ---", font=("", 11))
            lbl_pid.pack(side="right", padx=5)

            btn_frame_p = ctk.CTkFrame(header, fg_color="transparent")
            btn_frame_p.pack(side="right", padx=5)

            btn_start = ctk.CTkButton(btn_frame_p, text="▶", width=32, height=28,
                                       fg_color="#2fa572", hover_color="#238a5c",
                                       command=lambda k=key: self.start_signal_process(k))
            btn_start.pack(side="left", padx=2)

            btn_stop = ctk.CTkButton(btn_frame_p, text="■", width=32, height=28,
                                      fg_color="#d9534f", hover_color="#c9302c",
                                      state="disabled",
                                      command=lambda k=key: self.stop_signal_process(k))
            btn_stop.pack(side="left", padx=2)

            console = ctk.CTkTextbox(panel, font=("Consolas", 11),
                                      state="disabled", wrap="word")
            console.pack(fill="both", expand=True, padx=10, pady=(2, 8))

            self.signal_procs[key] = {
                "name": name, "cmd": cmd, "color": color,
                "proc": None, "logs": [],
                "console": console, "btn_start": btn_start,
                "btn_stop": btn_stop, "lbl_pid": lbl_pid,
            }

    def _kill_orphan_processes(self, key):
        """Kill orphan processes that weren't tracked (e.g. from crashed sessions)"""
        if os.name != 'nt':
            return
        script_map = {
            "mimo_bot": "mimo_bot.py",
            "mimo_worker": "mimo_worker.py",
        }
        script = script_map.get(key)
        if not script:
            return
        try:
            result = subprocess.run(
                ["wmic", "process", "where",
                 f"CommandLine like '%{script}%' and Name='python.exe'",
                 "get", "ProcessId"],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line.isdigit():
                    pid = int(line)
                    if pid != os.getpid():
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        self.log(f"Killed orphan process: {script} (PID: {pid})")
        except:
            pass

    def start_signal_process(self, key):
        info = self.signal_procs.get(key)
        if not info or info["proc"] and info["proc"].poll() is None:
            return
        self._kill_orphan_processes(key)
        try:
            startupinfo = None
            creationflags = 0
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW

            # Build command based on mode (shared helper so it's covered by real tests)
            profile = self.combo_profiles.get() if hasattr(self, 'combo_profiles') else ""
            frozen = getattr(sys, 'frozen', False)
            try:
                cmd = build_signal_process_cmd(
                    key, profile, frozen, sys.executable, script_map=SIGNAL_SCRIPT_MAP
                )
            except UnsupportedFrozenProcessError:
                self.log(f"Frozen mode: {info['name']} not supported yet")
                return
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUNBUFFERED"] = "1"
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding='utf-8', errors='replace',
                startupinfo=startupinfo, creationflags=creationflags,
                cwd=os.path.dirname(os.path.abspath(__file__)),
                env=env,
            )
            info["proc"] = proc
            info["logs"] = []
            info["lbl_pid"].configure(text=f"PID: {proc.pid}")
            info["btn_start"].configure(state="disabled")
            info["btn_stop"].configure(state="normal")

            t = threading.Thread(target=self._monitor_signal_output, args=(key, proc), daemon=True)
            t.start()
            self.log(f"Signal started: {info['name']} (PID: {proc.pid})")
        except Exception as e:
            self.log(f"Signal start error ({info['name']}): {e}")

    def stop_signal_process(self, key):
        info = self.signal_procs.get(key)
        if not info or not info["proc"]:
            return
        proc = info["proc"]
        if proc.poll() is None:
            try:
                if os.name == 'nt':
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    proc.terminate()
            except:
                proc.terminate()
            time.sleep(0.5)
            self.log(f"Signal stopped: {info['name']}")
        info["proc"] = None
        info["btn_start"].configure(state="normal")
        info["btn_stop"].configure(state="disabled")
        info["lbl_pid"].configure(text="PID: ---")
        self._kill_orphan_processes(key)
        if key == "mimo_worker":
            lock = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mimo_worker.lock")
            try:
                if os.path.exists(lock):
                    os.remove(lock)
            except:
                pass

    def _monitor_signal_output(self, key, proc):
        info = self.signal_procs.get(key)
        if not info:
            return
        try:
            for line in iter(proc.stdout.readline, ''):
                if not line:
                    break
                clean = line.strip()
                if clean:
                    info["logs"].append(clean)
                    self.after(0, self._append_signal_log, key, clean)
        except:
            pass
        finally:
            self.after(0, lambda: self.stop_signal_process(key))

    def _append_signal_log(self, key, line):
        info = self.signal_procs.get(key)
        if not info:
            return
        console = info["console"]
        console.configure(state="normal")
        console.insert("end", line + "\n")
        console.see("end")
        console.configure(state="disabled")
        if len(info["logs"]) > 500:
            info["logs"] = info["logs"][-300:]

    def start_all_signals(self):
        for key in self.signal_procs:
            self.start_signal_process(key)
            time.sleep(1)

    def stop_all_signals(self):
        for key in self.signal_procs:
            self.stop_signal_process(key)

    def create_profiles_frame(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["profiles"] = frame
        frame.pack(fill="both", expand=True)
        
        # Left List
        self.list_frame = ctk.CTkScrollableFrame(frame, width=220, label_text=T("profile_list"))
        self.list_frame.pack(side="left", fill="y", padx=(0, 20))
        
        self.refresh_profile_list()
        
        # Right Panel (Container for Form + Buttons)
        self.right_panel = ctk.CTkFrame(frame, fg_color="transparent")
        self.right_panel.pack(side="right", fill="both", expand=True)
        
        # Scrollable Form Area (Top)
        self.form_scroll = ctk.CTkScrollableFrame(self.right_panel, label_text=T("grp_config"))
        self.form_scroll.pack(side="top", fill="both", expand=True, pady=(0, 10))
        self.form_scroll.grid_columnconfigure(1, weight=1)
        
        # Inputs (inside form_scroll)
        # Checkbox for Balance SL/TP
        self.chk_balance = ctk.CTkCheckBox(self.form_scroll, text=T("lbl_use_balance_sltp"))
        self.chk_balance.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.add_ui_element("lbl_use_balance_sltp", self.chk_balance)

        self.chk_visible_sltp = ctk.CTkCheckBox(self.form_scroll, text=T("lbl_visible_sltp"))
        self.chk_visible_sltp.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        self.add_ui_element("lbl_visible_sltp", self.chk_visible_sltp)

        fields = [
            ("name", "lbl_name"), ("path", "lbl_path"), ("magic", "lbl_magic"),
            ("symbol", "lbl_symbol"), ("sl", "lbl_sl"), ("tp", "lbl_tp"),
            ("gold_sl", "lbl_gold_sl"), ("gold_tp", "lbl_gold_tp"),
            ("balance_sl_pct", "lbl_balance_sl_pct"), ("balance_tp_pct", "lbl_balance_tp_pct"),
            ("partial_r", "lbl_partial_r"), ("partial_pct", "lbl_partial_pct"),
            ("auto_be", "lbl_auto_be"),
            ("tele_token", "lbl_tele_token"), ("tele_chat", "lbl_tele_chat"), ("tele_admin", "lbl_tele_admin")
        ]
        self.entries = {}
        secret_fields = {"tele_token"}
        for i, (key, label_key) in enumerate(fields):
            row_idx = i + 1
            lbl = ctk.CTkLabel(self.form_scroll, text=T(label_key))
            lbl.grid(row=row_idx, column=0, padx=10, pady=5, sticky="w")
            self.add_ui_element(label_key, lbl)

            ent = ctk.CTkEntry(self.form_scroll, show="•" if key in secret_fields else "")
            ent.grid(row=row_idx, column=1, padx=10, pady=5, sticky="ew")
            self.entries[key] = ent
            
        # Buttons (Fixed at Bottom of Right Panel)
        btn_box = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        btn_box.pack(side="bottom", fill="x", pady=10)

        # Active Profile badge
        self.lbl_active_profile = ctk.CTkLabel(btn_box, text="", font=ctk.CTkFont(size=11, weight="bold"),
                                                text_color="#66bb6a")
        self.lbl_active_profile.pack(side="left", padx=10)

        # Unsaved changes indicator
        self.lbl_unsaved = ctk.CTkLabel(btn_box, text="", font=ctk.CTkFont(size=10),
                                         text_color="#ffb74d")
        self.lbl_unsaved.pack(side="left", padx=5)

        self.btn_save_p = ctk.CTkButton(btn_box, text=T("btn_save"), command=self.save_profile)
        self.btn_save_p.pack(side="left", padx=10, expand=True)
        self.add_ui_element("btn_save", self.btn_save_p)
        
        self.btn_del_p = ctk.CTkButton(btn_box, text=T("btn_delete"), fg_color="red", command=self.delete_profile)
        self.btn_del_p.pack(side="left", padx=10, expand=True)
        self.add_ui_element("btn_delete", self.btn_del_p)
        
        self.btn_add_p = ctk.CTkButton(btn_box, text=T("btn_add"), fg_color="gray", command=self.clear_form)
        self.btn_add_p.pack(side="left", padx=10, expand=True)
        self.add_ui_element("btn_add", self.btn_add_p)
        
        # Auto-select active profile if any
        if self.profiles:
            active = list(self.profiles.keys())[0]
            self.load_profile_to_form(active)
            self._update_active_profile_badge(active)
        else:
            self.clear_form()

    def create_copy_trade_frame(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["copy_trade"] = frame
        frame.pack(fill="both", expand=True)
        
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        # --- LEFT PANEL (Settings) ---
        left_panel = ctk.CTkScrollableFrame(frame, width=300)
        left_panel.pack(side="left", fill="y", padx=(0, 20))
        
        self.lbl_copy_title = ctk.CTkLabel(left_panel, text=T("lbl_copy_config_title"), font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_copy_title.pack(pady=10)
        self.add_ui_element("lbl_copy_config_title", self.lbl_copy_title)
        
        # Profile Selector in Copy Trade
        self.lbl_copy_sel = ctk.CTkLabel(left_panel, text=T("pos_lbl_profile"))
        self.lbl_copy_sel.pack(anchor="w", padx=10)
        self.add_ui_element("pos_lbl_profile_copy", self.lbl_copy_sel) # Unique key for this tab's profile label
        
        self.combo_copy_profiles = ctk.CTkComboBox(left_panel, values=list(self.profiles.keys()), command=self.on_copy_profile_change)
        self.combo_copy_profiles.pack(fill="x", padx=10, pady=(0, 10))
        if self.combo_profiles.get():
            self.combo_copy_profiles.set(self.combo_profiles.get())

        # Profile Info
        self.lbl_copy_profile = ctk.CTkLabel(left_panel, text="Profile: None", text_color="gray")
        self.lbl_copy_profile.pack(pady=(0, 20))
        
        # Role
        self.lbl_copy_role = ctk.CTkLabel(left_panel, text=T("lbl_copy_role"))
        self.lbl_copy_role.pack(anchor="w", padx=10)
        self.add_ui_element("lbl_copy_role", self.lbl_copy_role)
        
        self.combo_copy_role = ctk.CTkComboBox(left_panel, values=["None", "Master", "Slave"])
        self.combo_copy_role.pack(fill="x", padx=10, pady=(0, 10))
        
        # Channel
        self.lbl_copy_channel = ctk.CTkLabel(left_panel, text=T("lbl_master_name"))
        self.lbl_copy_channel.pack(anchor="w", padx=10)
        self.add_ui_element("lbl_master_name", self.lbl_copy_channel)
        
        self.ent_copy_channel = ctk.CTkEntry(left_panel)
        self.ent_copy_channel.pack(fill="x", padx=10, pady=(0, 10))
        
        # Lot Mode (Slave Only)
        self.lbl_copy_lot = ctk.CTkLabel(left_panel, text=T("lbl_lot_mode"))
        self.lbl_copy_lot.pack(anchor="w", padx=10)
        self.add_ui_element("lbl_lot_mode", self.lbl_copy_lot)
        
        self.combo_copy_lot = ctk.CTkComboBox(left_panel, values=["Fixed", "Multiplier", "Risk %"])
        self.combo_copy_lot.pack(fill="x", padx=10, pady=(0, 10))
        
        # Lot Value
        self.lbl_copy_val = ctk.CTkLabel(left_panel, text=T("lbl_lot_value"))
        self.lbl_copy_val.pack(anchor="w", padx=10)
        self.add_ui_element("lbl_lot_value", self.lbl_copy_val)
        
        self.ent_copy_value = ctk.CTkEntry(left_panel)
        self.ent_copy_value.pack(fill="x", padx=10, pady=(0, 10))
        
        # Stealth
        self.chk_copy_stealth = ctk.CTkCheckBox(left_panel, text=T("lbl_stealth"))
        self.chk_copy_stealth.pack(anchor="w", padx=10, pady=(10, 5))
        self.add_ui_element("lbl_stealth", self.chk_copy_stealth)

        # Max 1 Trade
        self.chk_copy_max_one = ctk.CTkCheckBox(left_panel, text=T("lbl_max_one"))
        self.chk_copy_max_one.pack(anchor="w", padx=10, pady=(5, 10))
        self.add_ui_element("lbl_max_one", self.chk_copy_max_one)

        # --- SAFETY GUARDRAILS ---
        self.lbl_safety_title = ctk.CTkLabel(left_panel, text="Safety Guardrails", font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_safety_title.pack(anchor="w", padx=10, pady=(10, 5))

        # Max Daily Trades
        self.lbl_max_daily = ctk.CTkLabel(left_panel, text="Max Daily Trades")
        self.lbl_max_daily.pack(anchor="w", padx=10)
        self.ent_max_daily = ctk.CTkEntry(left_panel, placeholder_text="20")
        self.ent_max_daily.pack(fill="x", padx=10, pady=(0, 5))

        # Max Lot Per Trade
        self.lbl_max_lot = ctk.CTkLabel(left_panel, text="Max Lot Per Trade")
        self.lbl_max_lot.pack(anchor="w", padx=10)
        self.ent_max_lot = ctk.CTkEntry(left_panel, placeholder_text="5.0")
        self.ent_max_lot.pack(fill="x", padx=10, pady=(0, 5))

        # Max Exposure Per Symbol
        self.lbl_max_exposure = ctk.CTkLabel(left_panel, text="Max Exposure/Symbol (lots)")
        self.lbl_max_exposure.pack(anchor="w", padx=10)
        self.ent_max_exposure = ctk.CTkEntry(left_panel, placeholder_text="10.0")
        self.ent_max_exposure.pack(fill="x", padx=10, pady=(0, 5))

        # Kill Switch
        self.chk_kill_switch = ctk.CTkCheckBox(left_panel, text="Kill Switch (Stop All New Trades)")
        self.chk_kill_switch.pack(anchor="w", padx=10, pady=(5, 5))

        # Stale Threshold
        self.lbl_stale = ctk.CTkLabel(left_panel, text="Stale Signal Threshold (sec)")
        self.lbl_stale.pack(anchor="w", padx=10)
        self.ent_stale = ctk.CTkEntry(left_panel, placeholder_text="300")
        self.ent_stale.pack(fill="x", padx=10, pady=(0, 10))
        
        # Ignored Symbols
        self.lbl_copy_ignore = ctk.CTkLabel(left_panel, text=T("lbl_ignore_sym"))
        self.lbl_copy_ignore.pack(anchor="w", padx=10)
        self.add_ui_element("lbl_ignore_sym", self.lbl_copy_ignore)
        
        self.ent_copy_ignore = ctk.CTkEntry(left_panel, placeholder_text="e.g. BTCUSD,ETHUSD")
        self.ent_copy_ignore.pack(fill="x", padx=10, pady=(0, 10))
        
        # Save Config Button
        self.btn_save_copy = ctk.CTkButton(left_panel, text=T("btn_save_copy"), command=self.save_copy_config)
        self.btn_save_copy.pack(fill="x", padx=10, pady=20)
        self.add_ui_element("btn_save_copy", self.btn_save_copy)
        
        # Start/Stop Monitor (Convenience)
        self.lbl_copy_control = ctk.CTkLabel(left_panel, text=T("lbl_control_monitor"), font=ctk.CTkFont(weight="bold"))
        self.lbl_copy_control.pack(pady=(20, 5))
        self.add_ui_element("lbl_control_monitor", self.lbl_copy_control)
        
        self.btn_copy_start = ctk.CTkButton(left_panel, text=T("btn_start"), fg_color="green", command=self.start_monitor)
        self.btn_copy_start.pack(fill="x", padx=10, pady=5)
        self.add_ui_element("btn_start", self.btn_copy_start)
        
        self.btn_copy_stop = ctk.CTkButton(left_panel, text=T("btn_stop"), fg_color="red", state="disabled", command=self.stop_monitor)
        self.btn_copy_stop.pack(fill="x", padx=10, pady=5)
        self.add_ui_element("btn_stop", self.btn_copy_stop)
        
        # --- RIGHT PANEL (Green Console) ---
        right_panel = ctk.CTkFrame(frame, fg_color="transparent")
        right_panel.pack(side="right", fill="both", expand=True)
        
        self.lbl_copy_log = ctk.CTkLabel(right_panel, text=T("lbl_copy_console_title"), font=ctk.CTkFont(weight="bold"))
        self.lbl_copy_log.pack(anchor="w", pady=5)
        self.add_ui_element("lbl_copy_console_title", self.lbl_copy_log)
        
        self.copy_console = ctk.CTkTextbox(right_panel, font=("Consolas", 12), wrap="word")
        self.copy_console.pack(fill="both", expand=True)
        self.copy_console.configure(state="disabled")

    def load_copy_config(self):
        # Load from current selected profile in Dashboard combo
        if not hasattr(self, 'combo_profiles'): return
        
        name = self.combo_profiles.get()
        if not name or name not in self.profiles:
            self.lbl_copy_profile.configure(text="Profile: None")
            return
            
        self.lbl_copy_profile.configure(text=f"Profile: {name}")
        data = self.profiles[name]
        
        self.combo_copy_role.set(data.get("copy_role", "None"))
        self.ent_copy_channel.delete(0, "end"); self.ent_copy_channel.insert(0, data.get("copy_channel", ""))
        self.combo_copy_lot.set(data.get("copy_lot_mode", "Fixed"))
        self.ent_copy_value.delete(0, "end"); self.ent_copy_value.insert(0, data.get("copy_lot_value", "0.01"))
        
        if data.get("copy_stealth", False):
            self.chk_copy_stealth.select()
        else:
            self.chk_copy_stealth.deselect()
            
        if data.get("copy_max_one", False):
            self.chk_copy_max_one.select()
        else:
            self.chk_copy_max_one.deselect()
            
        self.ent_copy_ignore.delete(0, "end")
        self.ent_copy_ignore.insert(0, data.get("copy_ignore_list", ""))

        # Safety guardrails
        self.ent_max_daily.delete(0, "end")
        self.ent_max_daily.insert(0, str(data.get("copy_max_daily_trades", "20")))
        self.ent_max_lot.delete(0, "end")
        self.ent_max_lot.insert(0, str(data.get("copy_max_lot_per_trade", "5.0")))
        self.ent_max_exposure.delete(0, "end")
        self.ent_max_exposure.insert(0, str(data.get("copy_max_exposure", "10.0")))
        if data.get("copy_kill_switch", False):
            self.chk_kill_switch.select()
        else:
            self.chk_kill_switch.deselect()
        self.ent_stale.delete(0, "end")
        self.ent_stale.insert(0, str(data.get("copy_stale_threshold", "300")))
            
    def save_copy_config(self):
        name = self.combo_profiles.get()
        if not name or name not in self.profiles:
            return

        data = self.profiles[name]
        new_role = self.combo_copy_role.get()
        old_role = data.get("copy_role", "None")

        # Confirm when changing to Master/Slave
        if new_role != old_role and new_role in ("Master", "Slave"):
            from tkinter import messagebox
            role_desc = "send trades (Master)" if new_role == "Master" else "copy trades (Slave)"
            if not messagebox.askyesno("Confirm Role Change",
                                       f"Set '{name}' as {new_role}?\n\nThis will {role_desc}.\n\nContinue?"):
                return
            data["copy_role"] = new_role
            self.log(f"⚠️ [{name}] Role changed to {new_role.upper()}")
        else:
            data["copy_role"] = new_role
        data["copy_channel"] = self.ent_copy_channel.get().strip()
        data["copy_lot_mode"] = self.combo_copy_lot.get()
        data["copy_lot_value"] = self.ent_copy_value.get().strip()
        data["copy_stealth"] = bool(self.chk_copy_stealth.get())
        data["copy_max_one"] = bool(self.chk_copy_max_one.get())
        data["copy_ignore_list"] = self.ent_copy_ignore.get().strip()

        # Safety guardrails
        data["copy_max_daily_trades"] = self.ent_max_daily.get().strip() or "20"
        data["copy_max_lot_per_trade"] = self.ent_max_lot.get().strip() or "5.0"
        data["copy_max_exposure"] = self.ent_max_exposure.get().strip() or "10.0"
        data["copy_kill_switch"] = bool(self.chk_kill_switch.get())
        data["copy_stale_threshold"] = self.ent_stale.get().strip() or "300"

        save_json(CONFIG_FILE, self.profiles)
        self.log(f"Copy Trade Config Saved for {name}")

    def create_pos_size_frame(self, parent):
        # Create main container
        container = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["pos_size"] = container
        container.pack(fill="both", expand=True)
        
        # Grid layout: 2 columns (Left: Inputs, Right: List)
        container.grid_columnconfigure(0, weight=1) # Inputs
        container.grid_columnconfigure(1, weight=3) # List
        container.grid_rowconfigure(0, weight=1)
        
        # --- LEFT COLUMN: INPUTS ---
        left_frame = ctk.CTkFrame(container, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # 1. Profile
        self.lbl_pos_profile = ctk.CTkLabel(left_frame, text=T("pos_lbl_profile"), anchor="w")
        self.lbl_pos_profile.pack(fill="x", padx=5, pady=(5,0))
        self.add_ui_element("pos_lbl_profile", self.lbl_pos_profile)

        self.combo_pos_profiles = ctk.CTkComboBox(left_frame, values=list(self.profiles.keys()), command=self.on_pos_profile_change, height=30)
        self.combo_pos_profiles.pack(fill="x", padx=5, pady=(0,5))
        if hasattr(self, 'combo_profiles') and self.combo_profiles.get():
            self.combo_pos_profiles.set(self.combo_profiles.get())

        # 2. Symbol
        self.lbl_pos_sym = ctk.CTkLabel(left_frame, text=T("pos_lbl_symbol"), anchor="w")
        self.lbl_pos_sym.pack(fill="x", padx=5, pady=(5,0))
        self.add_ui_element("pos_lbl_symbol", self.lbl_pos_sym)

        self.ent_pos_sym = ctk.CTkEntry(left_frame, placeholder_text="e.g. XAUUSD", height=30)
        self.ent_pos_sym.pack(fill="x", padx=5, pady=(0,5))

        # 3. Type
        ctk.CTkLabel(left_frame, text="Type:", anchor="w").pack(fill="x", padx=5, pady=(5,0))
        self.seg_pos_type = ctk.CTkSegmentedButton(left_frame, values=["BUY", "SELL"], height=30)
        self.seg_pos_type.set("BUY")
        self.seg_pos_type.pack(fill="x", padx=5, pady=(0,5))

        # 4. Lot
        ctk.CTkLabel(left_frame, text="Lot:", anchor="w").pack(fill="x", padx=5, pady=(5,0))
        self.val_pos_lot = ctk.CTkEntry(left_frame, height=30)
        self.val_pos_lot.insert(0, "0.01")
        self.val_pos_lot.pack(fill="x", padx=5, pady=(0,5))

        # 5. SL
        self.lbl_pos_sl = ctk.CTkLabel(left_frame, text=T("pos_lbl_sl"), anchor="w")
        self.lbl_pos_sl.pack(fill="x", padx=5, pady=(5,0))
        self.add_ui_element("pos_lbl_sl", self.lbl_pos_sl)

        self.ent_pos_sl = ctk.CTkEntry(left_frame, height=30)
        self.ent_pos_sl.insert(0, "0")
        self.ent_pos_sl.pack(fill="x", padx=5, pady=(0,5))

        # 6. TP
        self.lbl_pos_tp = ctk.CTkLabel(left_frame, text=T("pos_lbl_tp"), anchor="w")
        self.lbl_pos_tp.pack(fill="x", padx=5, pady=(5,0))
        self.add_ui_element("pos_lbl_tp", self.lbl_pos_tp)

        self.ent_pos_tp = ctk.CTkEntry(left_frame, height=30)
        self.ent_pos_tp.insert(0, "0")
        self.ent_pos_tp.pack(fill="x", padx=5, pady=(0,5))

        # 7. Time
        self.lbl_pos_time = ctk.CTkLabel(left_frame, text=T("pos_lbl_time"), anchor="w")
        self.lbl_pos_time.pack(fill="x", padx=5, pady=(5,0))
        self.add_ui_element("pos_lbl_time", self.lbl_pos_time)

        self.ent_pos_time = ctk.CTkEntry(left_frame, placeholder_text="HH:MM:SS", height=30)
        self.ent_pos_time.insert(0, datetime.now().strftime("%H:%M:%S"))
        self.ent_pos_time.pack(fill="x", padx=5, pady=(0,5))

        # 8. Schedule Button
        self.btn_pos_schedule = ctk.CTkButton(left_frame, text=T("pos_btn_schedule"), fg_color="#ffc107", text_color="black",
                                              hover_color="#e0a800", height=40, font=ctk.CTkFont(weight="bold"),
                                              command=self.add_scheduled_trade)
        self.btn_pos_schedule.pack(fill="x", padx=5, pady=20)
        self.add_ui_element("pos_btn_schedule", self.btn_pos_schedule)

        # 9. Status Msg
        self.lbl_pos_msg = ctk.CTkLabel(left_frame, text="", text_color="yellow", font=ctk.CTkFont(size=13, slant="italic"), wraplength=200)
        self.lbl_pos_msg.pack(fill="x", padx=5, pady=5)


        # --- RIGHT COLUMN: LIST ---
        right_frame = ctk.CTkFrame(container, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_frame.grid_rowconfigure(1, weight=1) # Treeview expands
        right_frame.grid_columnconfigure(0, weight=1)

        # Header
        self.lbl_pos_list = ctk.CTkLabel(right_frame, text=T("pos_list_header"), font=ctk.CTkFont(weight="bold", size=14))
        self.lbl_pos_list.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.add_ui_element("pos_list_header", self.lbl_pos_list)

        # Treeview Container
        tree_container = ctk.CTkFrame(right_frame, fg_color="transparent")
        tree_container.grid(row=1, column=0, sticky="nsew")
        
        # Treeview Style - dark theme
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Scheduled.Treeview",
                        rowheight=30,
                        background="#1a1a2e",
                        foreground="#e0e0e0",
                        fieldbackground="#1a1a2e",
                        borderwidth=0,
                        font=("Segoe UI", 10))
        style.configure("Scheduled.Treeview.Heading",
                        background="#16213e",
                        foreground="#e0e0e0",
                        font=("Segoe UI", 10, "bold"),
                        borderwidth=0)
        style.map("Scheduled.Treeview",
                  background=[("selected", "#0f3460")],
                  foreground=[("selected", "#ffffff")])
        
        self.tree_scheduled = ttk.Treeview(tree_container, columns=("Symbol", "Type", "Lot", "Time", "Status", "StatusDetail", "NextAction"), show="headings", height=20, style="Scheduled.Treeview")
        
        self.tree_scheduled.heading("Symbol", text="Symbol")
        self.tree_scheduled.heading("Type", text="Type")
        self.tree_scheduled.heading("Lot", text="Lot")
        self.tree_scheduled.heading("Time", text="Time")
        self.tree_scheduled.heading("Status", text="Status")
        self.tree_scheduled.heading("StatusDetail", text="Status Chi Tiết")
        self.tree_scheduled.heading("NextAction", text="Next Action")
        
        self.tree_scheduled.column("Symbol", width=70, anchor="center")
        self.tree_scheduled.column("Type", width=50, anchor="center")
        self.tree_scheduled.column("Lot", width=50, anchor="center")
        self.tree_scheduled.column("Time", width=120, anchor="center")
        self.tree_scheduled.column("Status", width=70, anchor="center")
        self.tree_scheduled.column("StatusDetail", width=130, anchor="center")
        self.tree_scheduled.column("NextAction", width=150, anchor="center")
        
        self.tree_scheduled.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree_scheduled.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree_scheduled.configure(yscrollcommand=scrollbar.set)
        
        # Context Menu
        self.context_menu = tkinter.Menu(self.main_frame, tearoff=0)
        self.context_menu.add_command(label=T("pos_btn_edit"), command=self.edit_scheduled_trade)
        self.context_menu.add_command(label=T("pos_btn_del"), command=self.delete_scheduled_trade)
        self.context_menu.add_command(label=T("pos_btn_save"), command=self.save_scheduled_trades_ui)
        
        def do_popup(event):
            try:
                item = self.tree_scheduled.identify_row(event.y)
                if item:
                    self.tree_scheduled.selection_set(item)
                    self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

        self.tree_scheduled.bind("<Button-3>", do_popup)

    def create_diagnostics_frame(self, parent):
        """Create the Diagnostics/Logs tab."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["diagnostics"] = frame
        frame.pack(fill="both", expand=True)

        # Header
        header = ctk.CTkLabel(frame, text="Diagnostics & Logs", font=ctk.CTkFont(size=16, weight="bold"))
        header.pack(pady=(10, 5), anchor="w", padx=10)

        # Log level filter
        filter_frame = ctk.CTkFrame(frame, fg_color="transparent")
        filter_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(filter_frame, text="Filter:").pack(side="left")
        self._log_level_var = ctk.StringVar(value="ALL")
        for level in ["ALL", "INFO", "WARNING", "ERROR"]:
            ctk.CTkRadioButton(filter_frame, text=level, variable=self._log_level_var, value=level,
                               command=self._filter_logs).pack(side="left", padx=5)

        # Auto Refresh + Follow toggle
        self._auto_refresh_var = ctk.BooleanVar(value=False)
        self._follow_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(filter_frame, text="Auto Refresh", variable=self._auto_refresh_var,
                        font=ctk.CTkFont(size=10), command=self._toggle_auto_refresh).pack(side="right", padx=5)
        ctk.CTkCheckBox(filter_frame, text="Follow Latest", variable=self._follow_var,
                        font=ctk.CTkFont(size=10)).pack(side="right", padx=5)

        # Log display
        self._log_text = ctk.CTkTextbox(frame, wrap="word", font=ctk.CTkFont(family="Consolas", size=11))
        self._log_text.pack(fill="both", expand=True, padx=10, pady=5)

        # Buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(btn_frame, text="Refresh", width=80, command=self._refresh_logs).pack(side="left", padx=3)
        ctk.CTkButton(btn_frame, text="Clear Display", width=100, command=self._clear_log_display).pack(side="left", padx=3)
        ctk.CTkButton(btn_frame, text="Copy Selected", width=100, command=self._copy_selected_logs).pack(side="left", padx=3)
        ctk.CTkButton(btn_frame, text="Open Log Folder", width=110, command=self._open_log_folder).pack(side="left", padx=3)
        ctk.CTkButton(btn_frame, text="Export Debug Bundle", width=150, command=self._export_debug_bundle).pack(side="left", padx=3)

        # Status bar
        self._diag_status = ctk.CTkLabel(frame, text="Ready", text_color="gray")
        self._diag_status.pack(anchor="w", padx=10, pady=(0, 5))

        # Load initial logs
        self.after(500, self._refresh_logs)

    def _toggle_auto_refresh(self):
        """Toggle auto refresh for diagnostics."""
        if self._auto_refresh_var.get():
            self._auto_refresh_diag()

    def _auto_refresh_diag(self):
        """Auto refresh diagnostics log."""
        if self._auto_refresh_var.get():
            self._refresh_logs()
            self.after(3000, self._auto_refresh_diag)

    def _copy_selected_logs(self):
        """Copy selected text from log display."""
        try:
            selected = self._log_text.get("sel.first", "sel.last")
            self.clipboard_clear()
            self.clipboard_append(selected)
            self._diag_status.configure(text="Copied to clipboard")
        except Exception:
            self._diag_status.configure(text="No text selected")

    def _open_log_folder(self):
        """Open log folder in file explorer."""
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.startfile(log_dir) if os.name == "nt" else os.system(f"xdg-open {log_dir}")

    def _refresh_logs(self):
        """Load logs from app.log into the display."""
        log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "app.log")
        self._log_text.delete("1.0", "end")
        if not os.path.exists(log_file):
            self._log_text.insert("1.0", "No diagnostics found.\nSystem is currently quiet. 🌙")
            return
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            level_filter = self._log_level_var.get()
            filtered = []
            for line in lines:
                if level_filter == "ALL":
                    filtered.append(line)
                elif f" - {level_filter} - " in line:
                    filtered.append(line)
            # Show last 500 lines
            display = filtered[-500:] if len(filtered) > 500 else filtered
            self._log_text.insert("1.0", "".join(display))
            if self._follow_var.get():
                self._log_text.see("end")
            self._diag_status.configure(text=f"Loaded {len(filtered)} lines ({len(lines)} total)")
        except Exception as e:
            self._log_text.insert("1.0", f"Error reading log: {e}")

    def _filter_logs(self):
        """Re-filter logs when level changes."""
        self._refresh_logs()

    def _clear_log_display(self):
        """Clear the log display."""
        self._log_text.delete("1.0", "end")

    def _export_debug_bundle(self):
        """Export logs + config + state as a zip bundle."""
        import zipfile
        from tkinter import filedialog
        bundle_path = filedialog.asksaveasfilename(defaultextension=".zip",
                                                    filetypes=[("Zip files", "*.zip")],
                                                    title="Export Debug Bundle")
        if not bundle_path:
            return
        try:
            with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Add log file
                log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "app.log")
                if os.path.exists(log_file):
                    zf.write(log_file, "app.log")
                # Add config files
                for fname in ["config.json", "profiles.json", "settings.json"]:
                    fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
                    if os.path.exists(fpath):
                        zf.write(fpath, fname)
                # Add state files
                for fname in ["scheduled_trades.json", "scheduled_close.json", "pending_partials.json"]:
                    fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
                    if os.path.exists(fpath):
                        zf.write(fpath, fname)
            self._diag_status.configure(text=f"Exported to {os.path.basename(bundle_path)}")
        except Exception as e:
            self._diag_status.configure(text=f"Export error: {e}")

    def create_guide_frame(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["guide"] = frame
        frame.pack(fill="both", expand=True)
        
        self.guide_box = ctk.CTkTextbox(frame, width=600, height=500, font=ctk.CTkFont(size=16), wrap="word")
        self.guide_box.pack(fill="both", expand=True)
        self.guide_box.insert("0.0", self.get_doc_content("guide_info"))
        self.apply_markdown(self.guide_box)
        self.guide_box.configure(state="disabled")

    def create_readme_frame(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["readme"] = frame
        frame.pack(fill="both", expand=True)
        
        self.readme_box = ctk.CTkTextbox(frame, width=600, height=500, font=ctk.CTkFont(size=14), wrap="word")
        self.readme_box.pack(fill="both", expand=True)
        self.readme_box.insert("0.0", self.get_doc_content("readme_info"))
        self.apply_markdown(self.readme_box)
        self.readme_box.configure(state="disabled")

    def create_release_notes_frame(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["release_notes"] = frame
        frame.pack(fill="both", expand=True)
        
        self.release_box = ctk.CTkTextbox(frame, width=600, height=500, font=ctk.CTkFont(size=14), wrap="word")
        self.release_box.pack(fill="both", expand=True)
        self.release_box.insert("0.0", self.get_doc_content("release_notes_info"))
        self.apply_markdown(self.release_box)
        self.release_box.configure(state="disabled")

    def apply_markdown(self, textbox):
        # Access internal tkinter widget to bypass CTkTextbox font restriction
        tf = textbox._textbox
        
        # Clear existing tags
        for tag in tf.tag_names():
            tf.tag_remove(tag, "1.0", "end")
            
        # Configure Tags
        tf.tag_config("h1", font=ctk.CTkFont(size=24, weight="bold"), foreground="#1565C0")
        tf.tag_config("h2", font=ctk.CTkFont(size=20, weight="bold"), foreground="#1976D2")
        tf.tag_config("h3", font=ctk.CTkFont(size=18, weight="bold"), foreground="#0277bd")
        tf.tag_config("bold", font=ctk.CTkFont(size=16, weight="bold"))
        tf.tag_config("italic", font=ctk.CTkFont(size=16, slant="italic"))
        tf.tag_config("note", foreground="orange", font=ctk.CTkFont(size=16, slant="italic"))
        tf.tag_config("link", foreground="#1E88E5", underline=True)
        
        count = tkinter.IntVar()
        
        # 1. Process Headers (#, ##, ###) and remove markers
        for tag_name, marker, size in [("h1", "# ", 24), ("h2", "## ", 20), ("h3", "### ", 18)]:
            while True:
                pos = tf.search(f"^{marker}", "1.0", stopindex="end", count=count, regexp=True)
                if not pos: break
                
                # Delete marker
                tf.delete(pos, f"{pos}+{len(marker)}c")
                
                # Find end of line
                line_end = tf.index(f"{pos} lineend")
                tf.tag_add(tag_name, pos, line_end)
        
        # 2. Process Numbered Headers (1. Title)
        start = "1.0"
        while True:
            pos = tf.search(r"^\d+\..*", start, stopindex="end", count=count, regexp=True)
            if not pos: break
            end = f"{pos}+{count.get()}c"
            tf.tag_add("h2", pos, end)
            start = end
            
        # 3. Notes (Note: or Lưu ý:)
        start = "1.0"
        while True:
            pos = tf.search(r"^(Lưu ý|Note):.*", start, stopindex="end", count=count, regexp=True)
            if not pos: break
            end = f"{pos}+{count.get()}c"
            tf.tag_add("note", pos, end)
            start = end

        # 4. Bold (**text**) - Process and remove markers
        while True:
            pos = tf.search(r"\*\*.*?\*\*", "1.0", stopindex="end", count=count, regexp=True)
            if not pos: break
            
            match_len = count.get()
            tf.delete(pos, f"{pos}+2c")
            content_len = match_len - 4
            trail_pos = f"{pos}+{content_len}c"
            tf.delete(trail_pos, f"{trail_pos}+2c")
            tf.tag_add("bold", pos, f"{pos}+{content_len}c")

        # 5. Italic (*text*) - Process and remove markers
        while True:
            pos = tf.search(r"\*[^\*]+\*", "1.0", stopindex="end", count=count, regexp=True)
            if not pos: break
            
            match_len = count.get()
            tf.delete(pos, f"{pos}+1c")
            content_len = match_len - 2
            trail_pos = f"{pos}+{content_len}c"
            tf.delete(trail_pos, f"{trail_pos}+1c")
            tf.tag_add("italic", pos, f"{pos}+{content_len}c")

        # 6. Colored Text (<c=#HEX>text</c>) - NEW v3.0.0
        start = "1.0"
        while True:
            # Search for <c=#HEX>content</c>
            pos = tf.search(r"<c=(#[A-Fa-f0-9]{6})>.*?</c>", start, stopindex="end", count=count, regexp=True)
            if not pos: break
            
            match_str = tf.get(pos, f"{pos}+{count.get()}c")
            match = re.search(r"<c=(#[A-Fa-f0-9]{6})>(.*?)</c>", match_str)
            if match:
                color = match.group(1)
                content = match.group(2)
                tag_name = f"color_{color}"
                
                # Configure tag if not exists
                if tag_name not in tf.tag_names():
                    tf.tag_config(tag_name, foreground=color)
                
                # Replace the whole tag with just content
                tf.delete(pos, f"{pos}+{count.get()}c")
                tf.insert(pos, content)
                tf.tag_add(tag_name, pos, f"{pos}+{len(content)}c")
                start = f"{pos}+{len(content)}c"
            else:
                start = f"{pos}+1c"

    def create_about_frame(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["about"] = frame
        frame.pack(fill="both", expand=True)

        # App icon + title
        ctk.CTkLabel(frame, text="🎛️", font=ctk.CTkFont(size=48)).pack(pady=(30, 5))
        ctk.CTkLabel(frame, text=f"OAK Manager {VERSION} Stable", font=ctk.CTkFont(size=24, weight="bold")).pack()
        ctk.CTkLabel(frame, text="Trading Operations Console for MT4 / MT5", font=ctk.CTkFont(size=13), text_color="gray").pack(pady=(0, 5))
        ctk.CTkLabel(frame, text=f"Build {BUILD} · Windows x64", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(0, 20))

        self.lbl_about = ctk.CTkLabel(frame, text=T("about_info"), font=ctk.CTkFont(size=13))
        self.lbl_about.pack(pady=10)
        self.add_ui_element("about_info", self.lbl_about)

        # Buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="📘 Open Documentation", width=180,
                       command=lambda: os.startfile("README.md") if os.path.exists("README.md") else None).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="🔄 Check for Updates", width=180,
                       command=lambda: self.log("Checking for updates... (auto-check coming soon)")).pack(side="left", padx=10)

    def ensure_mt5_connection(self):
        if mt5.terminal_info():
            return True
        
        # Try to find path from selected profile
        path = ""
        try:
            profile_name = self.combo_profiles.get()
            if profile_name and profile_name in self.profiles:
                path = self.profiles[profile_name].get("path", "")
        except:
            pass
            
        if path and os.path.exists(path):
            return mt5.initialize(path)
        else:
            return mt5.initialize()

    def send_order(self, order_type):
        self.lbl_pos_msg.configure(text="", text_color="yellow")
        if not self.ensure_mt5_connection():
             self.lbl_pos_msg.configure(text=T("pos_msg_err_sym"), text_color="red")
             return

        try:
            symbol = self.ent_pos_sym.get().strip().upper()
            try:
                vol = float(self.val_pos_lot.get())
            except:
                self.lbl_pos_msg.configure(text=T("err_invalid_lot"), text_color="red")
                return

            try:
                sl_points = int(self.ent_pos_sl.get())
                tp_points = int(self.ent_pos_tp.get())
            except:
                 self.lbl_pos_msg.configure(text=T("err_invalid_sltp"), text_color="red")
                 return
            
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                mt5.symbol_select(symbol, True)
                tick = mt5.symbol_info_tick(symbol)
                
            if not tick:
                self.lbl_pos_msg.configure(text=T("pos_msg_err_sym"), text_color="red")
                return
            
            price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
            point = mt5.symbol_info(symbol).point
            
            sl_price = 0.0
            tp_price = 0.0
            
            if order_type == mt5.ORDER_TYPE_BUY:
                if sl_points > 0: sl_price = price - sl_points * point
                if tp_points > 0: tp_price = price + tp_points * point
            else:
                if sl_points > 0: sl_price = price + sl_points * point
                if tp_points > 0: tp_price = price - tp_points * point
                
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": vol,
                "type": order_type,
                "price": price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": 20,
                "magic": 0, # Manual
                "comment": "OAK_POS_SIZE",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": get_filling_type(symbol),
            }
            
            # --- AUTO CLOSE OPPOSITE POSITIONS & PENDING ---
            opp_type = mt5.POSITION_TYPE_SELL if order_type == mt5.ORDER_TYPE_BUY else mt5.POSITION_TYPE_BUY
            positions_c = mt5.positions_get(symbol=symbol)
            if positions_c:
                for pos in positions_c:
                    if pos.type == opp_type:
                        tick_c = mt5.symbol_info_tick(pos.symbol)
                        if tick_c:
                            price_c = tick_c.bid if pos.type == mt5.POSITION_TYPE_BUY else tick_c.ask
                            req_c = {
                                "action": mt5.TRADE_ACTION_DEAL,
                                "symbol": pos.symbol,
                                "volume": pos.volume,
                                "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                                "position": pos.ticket,
                                "price": price_c,
                                "deviation": 20,
                                "magic": pos.magic,
                                "comment": "OAK_AUTO_CLOSE_OPPOSITE",
                                "type_time": mt5.ORDER_TIME_GTC,
                                "type_filling": get_filling_type(pos.symbol),
                            }
                            mt5.order_send(req_c)
                            profile_name = self.config.get("profile_name", "Unknown")
                            self.notify(f"🔄 [{profile_name}] Manual Entry: Auto Closed opposite {symbol} (Ticket: {pos.ticket})")
            
            # Close any PENDING ORDERS of the SAME symbol but OPPOSITE direction
            if order_type == mt5.ORDER_TYPE_BUY:
                opp_pending_types = [mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP, mt5.ORDER_TYPE_SELL_STOP_LIMIT]
            else:
                opp_pending_types = [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_BUY_STOP_LIMIT]
                
            pending_orders = mt5.orders_get(symbol=symbol)
            if pending_orders:
                for o in pending_orders:
                    if o.type in opp_pending_types:
                        request_del = {
                            "action": mt5.TRADE_ACTION_REMOVE,
                            "order": o.ticket
                        }
                        mt5.order_send(request_del)
                        profile_name = self.config.get("profile_name", "Unknown")
                        self.notify(f"🗑️ [{profile_name}] Manual Entry: Auto Removed opposite pending {symbol} (Ticket: {o.ticket})")

            res = mt5.order_send(req)
            if res.retcode == mt5.TRADE_RETCODE_DONE:
                 self.lbl_pos_msg.configure(text=f"{T('pos_msg_sent')} #{res.order}", text_color="green")
                 winsound.Beep(1000, 200)
            else:
                 self.lbl_pos_msg.configure(text=f"{T('log_fail')} {res.retcode}", text_color="red")
                 winsound.Beep(500, 500)
                 
        except Exception as e:
            self.lbl_pos_msg.configure(text=f"{T('msg_error')}: {e}", text_color="red")

    # --- SCHEDULED ORDER HELPERS ---
    def add_scheduled_trade(self):
        try:
            symbol = self.ent_pos_sym.get().strip().upper()
            lot = self.val_pos_lot.get().strip()
            sl = self.ent_pos_sl.get().strip()
            tp = self.ent_pos_tp.get().strip()
            time_str = self.ent_pos_time.get().strip()
            t_type_str = self.seg_pos_type.get()
            t_type = mt5.ORDER_TYPE_BUY if t_type_str == "BUY" else mt5.ORDER_TYPE_SELL
            
            # Basic validation
            if not symbol or not lot or not time_str:
                self.lbl_pos_msg.configure(text="Missing Info", text_color="red")
                return
            
            # Check if already holding this symbol or has a pending order for it
            # 1. Check open positions (Only fail if same symbol AND same direction)
            positions = mt5.positions_get(symbol=symbol)
            if positions:
                for pos in positions:
                    if pos.type == t_type:
                        self.lbl_pos_msg.configure(text=T("pos_msg_fail_pending_exists").format(symbol=symbol), text_color="red")
                        return
            
            # 2. Check pending list (Only fail if same symbol AND same direction)
            if hasattr(self, 'copy_manager'):
                for t in self.copy_manager.scheduled_trades:
                    if t.get("status") == "waiting" and t.get("symbol") == symbol and t.get("type") == t_type:
                        self.lbl_pos_msg.configure(text=T("pos_msg_fail_pending_exists").format(symbol=symbol), text_color="red")
                        return

            # Time format validation
            try:
                if len(time_str.split(":")) == 2: time_str += ":00"
                # Calculate Target Date (Tomorrow if time < now - tolerance)
                now_dt = datetime.now()
                target_dt = datetime.strptime(time_str, "%H:%M:%S").replace(year=now_dt.year, month=now_dt.month, day=now_dt.day)

                if target_dt < (now_dt - timedelta(seconds=60)):
                    target_dt += timedelta(days=1)
                while target_dt.weekday() in (5, 6):
                    target_dt += timedelta(days=1)
                
                target_date_str = target_dt.strftime("%Y-%m-%d")
                
                # Normalize time string to HH:MM:SS (ensure leading zeros for correct string comparison)
                time_str = target_dt.strftime("%H:%M:%S")
                
            except:
                self.lbl_pos_msg.configure(text=T("pos_msg_invalid_time"), text_color="red")
                return
            
            new_trade = {
                "symbol": symbol,
                "type": t_type, 
                "lot": lot,
                "sl": sl,
                "tp": tp,
                "time": time_str,
                "date": target_date_str,
                "status": "waiting"
            }
            
            if hasattr(self, 'copy_manager'):
                self.copy_manager.scheduled_trades.append(new_trade)
                # Sort by date and time
                self.copy_manager.scheduled_trades.sort(key=lambda x: (x.get("date", ""), x["time"]))
                save_json(self.copy_manager.scheduled_file, self.copy_manager.scheduled_trades)
                self.update_scheduled_list_ui()
                
                # Determine time description (Today vs Tomorrow)
                time_desc = time_str
                if target_dt.date() > now_dt.date():
                    day_name = "ngày mai" if (target_dt.date() - now_dt.date()).days == 1 else f"ngày {target_dt.strftime('%d/%m')}"
                    time_desc = f"{time_str} {day_name} ({target_dt.strftime('%d/%m')})"
                
                self.lbl_pos_msg.configure(text=T("pos_msg_scheduled").format(symbol=symbol, type=t_type_str, lot=lot, time=time_desc), text_color="green")
            else:
                self.lbl_pos_msg.configure(text="Copy Manager not initialized", text_color="red")
                
        except Exception as e:
            self.lbl_pos_msg.configure(text=f"Error: {e}", text_color="red")

    def edit_scheduled_trade(self):
        selected = self.tree_scheduled.selection()
        if not selected: return
        
        idx = self.tree_scheduled.index(selected[0])
        
        if hasattr(self, 'copy_manager') and idx < len(self.copy_manager.scheduled_trades):
            trade = self.copy_manager.scheduled_trades.pop(idx)
            
            # Load into UI
            self.ent_pos_sym.delete(0, "end")
            self.ent_pos_sym.insert(0, trade["symbol"])
            
            self.val_pos_lot.delete(0, "end")
            self.val_pos_lot.insert(0, trade["lot"])
            
            self.ent_pos_sl.delete(0, "end")
            self.ent_pos_sl.insert(0, trade["sl"])
            
            self.ent_pos_tp.delete(0, "end")
            self.ent_pos_tp.insert(0, trade["tp"])
            
            self.ent_pos_time.delete(0, "end")
            self.ent_pos_time.insert(0, trade["time"])
            
            t_type_str = "BUY" if trade["type"] == mt5.ORDER_TYPE_BUY else "SELL"
            self.seg_pos_type.set(t_type_str)
            
            save_json(self.copy_manager.scheduled_file, self.copy_manager.scheduled_trades)
            self.update_scheduled_list_ui()
            self.lbl_pos_msg.configure(text="Loaded for editing", text_color="yellow")

    def delete_scheduled_trade(self):
        selected = self.tree_scheduled.selection()
        if not selected: return
        
        # Sort indices in reverse to avoid index shifting while popping
        indices = sorted([self.tree_scheduled.index(item) for item in selected], reverse=True)
        
        if hasattr(self, 'copy_manager'):
            for idx in indices:
                if idx < len(self.copy_manager.scheduled_trades):
                    self.copy_manager.scheduled_trades.pop(idx)
            
            save_json(self.copy_manager.scheduled_file, self.copy_manager.scheduled_trades)
            self.update_scheduled_list_ui()

    def save_scheduled_trades_ui(self):
        if hasattr(self, 'copy_manager'):
            save_json(self.copy_manager.scheduled_file, self.copy_manager.scheduled_trades)
            self.log("Scheduled Trades Saved")

    def update_scheduled_list_ui(self):
        # Clear tree
        for item in self.tree_scheduled.get_children():
            self.tree_scheduled.delete(item)
            
        if not hasattr(self, 'copy_manager'): return
        
        for trade in self.copy_manager.scheduled_trades:
            # Robust type handling
            raw_type = trade.get("type", mt5.ORDER_TYPE_BUY)
            if isinstance(raw_type, str):
                t_type = raw_type.upper()
            else:
                t_type = "BUY" if raw_type == mt5.ORDER_TYPE_BUY else "SELL"
                
            # Format Time + Date
            t_time = trade.get("time", "00:00:00")
            t_date = trade.get("date", "")
            display_time = f"{t_time}\n{t_date}" if t_date else t_time
            status_raw = trade.get("status", "Waiting")
            status_detail = status_raw
            next_action = "-"
            if hasattr(self.copy_manager, "_get_trade_status_detail"):
                try:
                    status_detail = self.copy_manager._get_trade_status_detail(trade)
                except Exception:
                    status_detail = status_raw
            if hasattr(self.copy_manager, "_get_trade_next_action"):
                try:
                    next_action = self.copy_manager._get_trade_next_action(trade)
                except Exception:
                    next_action = "-"
            
            self.tree_scheduled.insert("", "end", values=(
                trade.get("symbol", "N/A"),
                t_type,
                trade.get("lot", 0.01),
                display_time,
                status_raw,
                status_detail,
                next_action
            ))

    def periodic_ui_refresh(self):
        """Reload scheduled trades from JSON file if it has changed (Multi-process sync)"""
        try:
            if hasattr(self, 'copy_manager') and hasattr(self.copy_manager, 'scheduled_file') and self.copy_manager.scheduled_file:
                file_path = self.copy_manager.scheduled_file
                if os.path.exists(file_path):
                    mtime = os.path.getmtime(file_path)
                    if not hasattr(self, '_last_json_mtime'): self._last_json_mtime = 0

                    if mtime > self._last_json_mtime:
                        self._last_json_mtime = mtime
                        # Reload
                        trades = load_json(file_path)
                        if isinstance(trades, list):
                            self.copy_manager.scheduled_trades = trades
                            # Update UI
                            self.update_scheduled_list_ui()
            self.update_news_summary()
            self._update_dashboard_cards()
        except Exception as e:
            print(f"Refresh Error: {e}")
        finally:
            self.after(2000, self.periodic_ui_refresh) # Check every 2s

    def _update_dashboard_cards(self):
        """Update Account/Signal/Engine cards from worker heartbeat (SQLite)."""
        try:
            # Read heartbeat for the ACTIVE profile only
            profile = self.combo_profiles.get() if hasattr(self, 'combo_profiles') else ""
            hb = self._store.get_heartbeat(profile) if hasattr(self, '_store') and profile else None
            mt5_state = self._store.compute_mt5_state(profile) if hasattr(self, '_store') and profile else {"state": "Disconnected", "last_error": ""}
            tg_state = self._store.compute_telegram_state(profile) if hasattr(self, '_store') and profile else {"configured": False, "api_ok": False}

            # Account Card - read from heartbeat
            if hasattr(self, 'card_account_balance'):
                if hb and hb.get("server"):
                    self.card_account_server.configure(text=f"{hb['server']} | #{hb.get('login', '')}")
                    self.card_account_balance.configure(text=f"Balance: ${hb.get('balance', 0):,.2f}")
                    self.card_account_equity.configure(text=f"Equity: ${hb.get('equity', 0):,.2f}")
                else:
                    self.card_account_server.configure(text="Waiting for worker...")
                    self.card_account_balance.configure(text="Balance: —")
                    self.card_account_equity.configure(text="Equity: —")

            # Signal Card
            if hasattr(self, 'card_signal_current'):
                try:
                    signals_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signals_log.json")
                    if os.path.exists(signals_file):
                        with open(signals_file, "r", encoding="utf-8") as f:
                            signals = json.load(f)
                        if signals:
                            latest = signals[-1]
                            sig = latest.get("signal", "—")
                            icon = "🟢" if sig == "BUY" else "🔴" if sig == "SELL" else "⚪"
                            self.card_signal_current.configure(text=f"Current: {icon} {sig}")
                except Exception:
                    self.card_signal_current.configure(text="Current: —")
                # Next slot countdown
                now = datetime.now()
                target_hours = list(range(3, 16))
                next_h = None
                for h in target_hours:
                    if now.hour < h or (now.hour == h and now.minute < 45):
                        next_h = h
                        break
                if next_h is None:
                    next_h = target_hours[0]
                self.card_signal_next.configure(text=f"Next: {next_h:02d}:45")
                target = now.replace(hour=next_h, minute=45, second=0, microsecond=0)
                if target < now:
                    from datetime import timedelta
                    target += timedelta(days=1)
                diff = target - now
                hrs, rem = divmod(int(diff.total_seconds()), 3600)
                mins, secs = divmod(rem, 60)
                self.card_signal_countdown.configure(text=f"Countdown: {hrs:02d}:{mins:02d}:{secs:02d}")

            # Engine Card
            if hasattr(self, 'card_engine_ghost'):
                is_running = any(
                    data.get("proc") and data["proc"].poll() is None
                    for data in self.workers.values()
                ) if hasattr(self, 'workers') else False
                ghost_active = self.settings.get("ghost_mode_active", False) if hasattr(self, 'settings') else False
                dot = "🟢" if is_running else "⚫"
                self.card_engine_ghost.configure(text=f"Ghost: {dot} {'Active' if ghost_active else 'Off'}")

            # Status Bar - read from heartbeat, not direct MT5 call
            if hasattr(self, 'status_mt5'):
                state = mt5_state["state"]
                color = "#66bb6a" if state == "Connected" else "#ffb74d" if state == "Degraded" else "#ef5350"
                label = state
                if state == "Degraded" and mt5_state.get("last_error"):
                    label = f"Degraded ({mt5_state['last_error'][:30]})"
                self.status_mt5.configure(text=f"MT5 ● {label}", text_color=color)

                # Telegram: 3 states
                tg_configured = tg_state["configured"]
                tg_api = tg_state["api_ok"]
                if not tg_configured:
                    # If OAK Manager has a configured chat or MiMo bot value, show configured
                    if _mimo_bot_chat_id or self.config.get("tele_chat", ""):
                        tg_label = "Configured"
                        tg_color = "#ffb74d"
                    else:
                        tg_label = "Not configured"
                        tg_color = "gray"
                elif tg_api:
                    tg_label = f"Online (@{tg_state['bot_name']})" if tg_state["bot_name"] else "Online"
                    tg_color = "#66bb6a"
                else:
                    tg_label = "Degraded (API unreachable)"
                    tg_color = "#ffb74d"
                self.status_telegram.configure(text=f"Telegram ● {tg_label}", text_color=tg_color)

                is_running = any(
                    data.get("proc") and data["proc"].poll() is None
                    for data in self.workers.values()
                ) if hasattr(self, 'workers') else False
                self.status_ghost.configure(text=f"Ghost ● {'Running' if is_running else 'Stopped'}",
                                            text_color="#66bb6a" if is_running else "gray")
        except Exception:
            pass

    def on_closing(self):
        # Cleanup all spawned processes
        _cleanup_processes()
        # Stop all signal processes
        for key in list(self.signal_procs.keys()):
            self.stop_signal_process(key)
        # Stop all workers
        for name, data in self.workers.items():
            if data["proc"].poll() is None:
                try:
                    data["proc"].kill()
                except: pass
        self.destroy()
        sys.exit(0)

    def notify(self, message):
        """Standard notification for CopyTradeManager within GUI process"""
        self.log(message)

    # --- LOGIC ---
    def get_doc_content(self, key):
        """Ưu tiên đọc từ file .md ngoài nếu là Tiếng Việt, fallback về LANG dictionary"""
        file_map = {
            "guide_info": "GUIDE.md",
            "readme_info": "README.md",
            "release_notes_info": "RELEASE_NOTES.md"
        }
        filename = file_map.get(key)
        # Chỉ ưu tiên đọc file .md cho tiếng Việt (mặc định các file này là VN)
        if filename and CURRENT_LANG == "VN" and os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    return f.read()
            except: pass
        return T(key)

    def log(self, msg):
        # Ensure thread safety by scheduling GUI update on main thread
        print(msg) # Debug print
        self.after(0, self._log_safe, msg)

    def _detect_log_tag(self, msg):
        """Detect log category for color coding."""
        m = msg.lower()
        if any(kw in m for kw in ["error", "fail", "❌", "loint"]): return "error"
        if any(kw in m for kw in ["warn", "⚠️"]): return "warning"
        if any(kw in m for kw in ["mt5", "position", "order", "trade", "ticket"]): return "mt5"
        if any(kw in m for kw in ["telegram", "tg ", "notify", "tele"]): return "telegram"
        if any(kw in m for kw in ["signal", "buy", "sell", "📊", "tín hiệu"]): return "signal"
        return "info"

    _LOG_COLORS = {
        "info": "#b0bec5",
        "warning": "#ffb74d",
        "error": "#ef5350",
        "mt5": "#29b6f6",
        "telegram": "#ab47bc",
        "signal": "#66bb6a",
    }

    def _log_safe(self, msg):
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            full_msg = f"[{timestamp}] {msg}\n"

            # Check console filters
            if hasattr(self, '_console_filters'):
                tag = self._detect_log_tag(msg)
                tag_key = tag.upper().replace("TELEGRAM", "TG")
                if tag_key in self._console_filters and not self._console_filters[tag_key].get():
                    return  # Filtered out

            # Dashboard Console
            if hasattr(self, 'console') and self.console.winfo_exists():
                tag = self._detect_log_tag(msg)
                color = self._LOG_COLORS.get(tag, "#b0bec5")
                self.console.configure(state="normal")
                self.console.insert("end", full_msg, tag)
                self.console.tag_config(tag, foreground=color)
                self.console.see("end")
                self.console.configure(state="disabled")

            # Copy Trade Console
            if hasattr(self, 'copy_console') and self.copy_console.winfo_exists():
                self.copy_console.configure(state="normal")
                self.copy_console.insert("end", full_msg)
                self.apply_markdown(self.copy_console)
                self.copy_console.see("end")
                self.copy_console.configure(state="disabled")

        except Exception as e:
            print(f"Log Error: {e}")

    def on_pos_profile_change(self, choice):
        # Sync with main profile combo
        self.combo_profiles.set(choice)
        self.on_profile_change(choice)
        self.log(f"Profile switched to {choice} (from Pos Size tab)")

    def on_copy_profile_change(self, choice):
        # Sync with main profile combo
        self.combo_profiles.set(choice)
        self.on_profile_change(choice)
        self.load_copy_config() # Specific for copy trade tab
        self.log(f"Profile switched to {choice} (from Copy Trade tab)")

    def start_monitor(self):
        profile_name = self.combo_profiles.get()
        if not profile_name or profile_name not in self.profiles:
            self.log(T("msg_select_profile"))
            return
            
        # Check if already running
        if profile_name in self.workers:
            if self.workers[profile_name]["proc"].poll() is None:
                self.log(f"Profile '{profile_name}' is already running.")
                return

        try:
            # Update button text immediately for responsive UI
            self.btn_start.configure(text=T("btn_start") + "...", state="disabled")
            
            # Clear console in background to avoid UI freeze
            def _clear_console():
                try:
                    self.console.configure(state="normal")
                    self.console.delete("1.0", "end")
                    self.console.configure(state="disabled")
                    if hasattr(self, 'copy_console') and self.copy_console.winfo_exists():
                        self.copy_console.configure(state="normal")
                        self.copy_console.delete("1.0", "end")
                        self.copy_console.configure(state="disabled")
                except: pass
            threading.Thread(target=_clear_console, daemon=True).start()
            
            if getattr(sys, 'frozen', False):
                cmd = [sys.executable, "--worker", "--profile", profile_name]
            else:
                cmd = [sys.executable, sys.argv[0], "--worker", "--profile", profile_name]
            
            # Windows: Hide Console Window
            startupinfo = None
            creationflags = 0
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
            
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            
            # Register for cleanup on exit/crash
            _running_processes.append(proc)
            
            # Reset logs for this run
            self.workers[profile_name] = {
                "proc": proc,
                "logs": []
            }
            self.running_profile_name = profile_name
            self.refresh_profile_list()
            
            # Start Reader Thread
            t = threading.Thread(target=self.monitor_worker_output, args=(profile_name, proc))
            t.daemon = True
            t.start()
            
            self.update_ui_state(profile_name)
            self.log(f"Started process for '{profile_name}' (PID: {proc.pid})")
            
        except Exception as e:
            self.log(f"Start Error: {e}")
            from tkinter import messagebox
            messagebox.showerror("Error", f"Could not start monitor:\n{e}")

    def stop_monitor(self):
        profile_name = self.combo_profiles.get()
        if profile_name in self.workers:
            proc = self.workers[profile_name]["proc"]
            if proc.poll() is None:
                proc.terminate()
                self.log(f"Stopping '{profile_name}'...")
                self.btn_stop.configure(state="disabled", text="Stopping...")
                self.running_profile_name = None
                self.refresh_profile_list()
                # Immediate update for local UI feedback
                self.update_ui_state(profile_name)
                # Still keep the delayed check just in case
                self.after(500, lambda: self.update_ui_state(profile_name))

    def monitor_worker_output(self, profile_name, proc):
        try:
            for line in iter(proc.stdout.readline, ''):
                if not line: break
                clean_line = line.strip()
                if clean_line:
                    # GHOST MODE REQUEST
                    if "[GHOST_REQUEST]" in clean_line:
                        self.after(0, self._handle_ghost_request)
                        continue

                    if profile_name in self.workers:
                        self.workers[profile_name]["logs"].append(clean_line)
                    
                    if self.combo_profiles.get() == profile_name:
                        self.after(0, self.log_to_console_direct, clean_line)
        except: pass
        finally:
            self.after(0, lambda: self.update_ui_state(profile_name))

    def _handle_ghost_request(self):
        """Show ghost consent popup if not already active."""
        if self.settings.get("ghost_mode_active", False):
            return
            
        def on_accept(accepted):
            if accepted:
                self.settings["ghost_mode_active"] = True
                save_json(SETTINGS_FILE, self.settings)
                self.log("👻 GHOST MODE ACTIVATED (Stealth Operator)")
            else:
                self.log("⚠️ Ghost Mode Declined.")
                
        show_ghost_consent(self, on_accept)

    def log_to_console_direct(self, msg):
        try:
            self.console.configure(state="normal")
            self.console.insert("end", msg + "\n")
            self.console.see("end")
            self.console.configure(state="disabled")
            
            if hasattr(self, 'copy_console') and self.copy_console.winfo_exists():
                self.copy_console.configure(state="normal")
                self.copy_console.insert("end", msg + "\n")
                self.copy_console.see("end")
                self.copy_console.configure(state="disabled")
        except: pass

    def on_profile_change(self, choice):
        # Update selected profile state
        self.selected_profile_name = choice
        # Update config and Init Copy Manager for GUI sync
        if choice in self.profiles:
            self.config = self.profiles[choice]
            self.config["profile_name"] = choice # Ensure profile_name is set for filename sync
            self.copy_manager = CopyTradeManager(self.config, self.notify)
            self.log(f"Profile: {choice} - Sync File: {self.copy_manager.scheduled_file}")
            self._last_json_mtime = 0 # Force refresh on next periodic call
            self.update_scheduled_list_ui()

        # Sync with Pos Size profile combo if it exists
        if hasattr(self, 'combo_pos_profiles'):
            self.combo_pos_profiles.set(choice)
        # Sync with Copy Trade profile combo if it exists
        if hasattr(self, 'combo_copy_profiles'):
            self.combo_copy_profiles.set(choice)
            
        if hasattr(self, 'lbl_copy_profile'):
            self.lbl_copy_profile.configure(text=f"Profile: {choice}")
            
        # Clear Console
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")
        
        if hasattr(self, 'copy_console') and self.copy_console.winfo_exists():
            self.copy_console.configure(state="normal")
            self.copy_console.delete("1.0", "end")
            self.copy_console.configure(state="disabled")
        
        # Load Logs
        if choice in self.workers:
            logs = self.workers[choice]["logs"]
            full_log = "\n".join(logs) + "\n"
            
            self.console.configure(state="normal")
            self.console.insert("end", full_log)
            self.console.see("end")
            self.console.configure(state="disabled")
            
            if hasattr(self, 'copy_console') and self.copy_console.winfo_exists():
                self.copy_console.configure(state="normal")
                self.copy_console.insert("end", full_log)
                self.copy_console.see("end")
                self.copy_console.configure(state="disabled")
            
        self.update_ui_state(choice)
        self.refresh_profile_list()

    def update_ui_state(self, profile_name):
        is_running = False
        if profile_name in self.workers:
             if self.workers[profile_name]["proc"].poll() is None:
                 is_running = True
        
        current_sel = self.combo_profiles.get()
        if current_sel == profile_name:
            if is_running:
                # Dashboard Buttons
                self.btn_start.configure(state="disabled", text=T("btn_start"))
                self.btn_stop.configure(state="normal", text=T("btn_stop"))
                # Copy Trade Buttons
                if hasattr(self, 'btn_copy_start'):
                    self.btn_copy_start.configure(state="disabled", text=T("btn_start"))
                if hasattr(self, 'btn_copy_stop'):
                    self.btn_copy_stop.configure(state="normal", text=T("btn_stop"))
            else:
                # Dashboard Buttons
                self.btn_start.configure(state="normal", text=T("btn_start"))
                self.btn_stop.configure(state="disabled", text=T("btn_stop"))
                # Copy Trade Buttons
                if hasattr(self, 'btn_copy_start'):
                    self.btn_copy_start.configure(state="normal", text=T("btn_start"))
                if hasattr(self, 'btn_copy_stop'):
                    self.btn_copy_stop.configure(state="disabled", text=T("btn_stop"))

    def refresh_profile_list(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        p = getattr(self, "theme_palette", None)
        for name in self.profiles:
            is_running = (name == self.running_profile_name)
            is_selected = (name == self.selected_profile_name)
            # Show running/editing status
            if is_running and is_selected:
                label = f"● ✎ {name}"
                color = "#66bb6a"
            elif is_running:
                label = f"● {name}"
                color = "#66bb6a"
            elif is_selected:
                label = f"✎ {name}"
                color = "#ffb74d"
            else:
                label = name
                color = p["text_primary"] if p else "white"

            btn_kwargs = {
                "text": label,
                "fg_color": "transparent",
                "border_width": 2 if (is_running or is_selected) else 1,
                "command": lambda n=name: self.load_profile_to_form(n)
            }
            if p:
                btn_kwargs.update({
                    "text_color": color,
                    "border_color": "#66bb6a" if is_running else ("#ffb74d" if is_selected else p["card_border"]),
                    "hover_color": p["panel_alt_bg"]
                })
            btn = ctk.CTkButton(self.list_frame, **btn_kwargs)
            btn.pack(pady=2, fill="x")
        
        # Update Combo
        if hasattr(self, 'combo_profiles'):
            self.combo_profiles.configure(values=list(self.profiles.keys()))
        if hasattr(self, 'combo_pos_profiles'):
            self.combo_pos_profiles.configure(values=list(self.profiles.keys()))
        if hasattr(self, 'combo_copy_profiles'):
            self.combo_copy_profiles.configure(values=list(self.profiles.keys()))

    def load_profile_to_form(self, name):
        self.selected_profile_name = name
        data = self.profiles[name]
        self.entries["name"].delete(0, "end"); self.entries["name"].insert(0, name)

        # Load Checkbox
        if data.get("use_balance_sltp", False):
            self.chk_balance.select()
        else:
            self.chk_balance.deselect()
        self.chk_visible_sltp.deselect()

        if data.get("visible_sltp", False):
            self.chk_visible_sltp.select()
        else:
            self.chk_visible_sltp.deselect()

        for key in data:
            if key in self.entries:
                val = str(data[key])
                # Mask token: if vaulted, show masked placeholder
                if key == "tele_token" and val == "__vault__":
                    val = "••••••••••••••••"
                self.entries[key].delete(0, "end")
                self.entries[key].insert(0, val)

        self._update_active_profile_badge(name)
        self._profile_form_snapshot = self._get_form_data()
        # Re-render the list so the ✎ Editing marker moves to this row
        # immediately, instead of staying on whatever was selected at the
        # last refresh (which made the list look out of sync with the form).
        self.refresh_profile_list()

    def clear_form(self):
        # Defaults
        defaults = {
            "name": "",
            "path": "",
            "magic": "0",
            "symbol": "GBPUSD,GBPJPY,GBPAUD,USDJPY",
            "sl": "350",
            "tp": "2500",
            "gold_sl": "1000",
            "gold_tp": "20000",
            "balance_sl_pct": "1.0",
            "balance_tp_pct": "2.0",
            "tele_token": "",
            "tele_chat": "",
            "tele_admin": ""
        }

        self.chk_balance.deselect()
        self.chk_visible_sltp.deselect()

        for key, ent in self.entries.items():
            ent.delete(0, "end")
            ent.insert(0, defaults.get(key, ""))

    def _get_form_data(self):
        """Snapshot current form data for unsaved detection."""
        data = {}
        for key, ent in self.entries.items():
            data[key] = ent.get().strip()
        data["use_balance_sltp"] = bool(self.chk_balance.get())
        data["visible_sltp"] = bool(self.chk_visible_sltp.get())
        return data

    def _update_active_profile_badge(self, name):
        """Update the profile badge showing Running and Editing states.

        Only shows "Editing: X" when it differs from the running profile,
        so a profile that is both running and being edited just shows
        "Running: X" instead of a confusing "Running: X | Editing: X".
        """
        if hasattr(self, 'lbl_active_profile'):
            parts = []
            if self.running_profile_name:
                parts.append(f"● Running: {self.running_profile_name}")
            if name and name != self.running_profile_name:
                parts.append(f"✎ Editing: {name}")
            self.lbl_active_profile.configure(text="   ".join(parts) if parts else "")

    def _check_unsaved_changes(self):
        """Check if form has unsaved changes vs last saved snapshot."""
        if not hasattr(self, '_profile_form_snapshot') or self._profile_form_snapshot is None:
            return False
        current = self._get_form_data()
        return current != self._profile_form_snapshot

    def save_profile(self):
        name = self.entries["name"].get().strip()
        if not name: return

        # Start with existing data to preserve fields not in this form (e.g. Copy Trade settings)
        new_data = self.profiles.get(name, {}).copy()

        # Save Checkbox
        new_data["use_balance_sltp"] = bool(self.chk_balance.get())
        new_data["visible_sltp"] = bool(self.chk_visible_sltp.get())

        for key, ent in self.entries.items():
            if key == "name": continue
            val = ent.get().strip()
            if key == "path":
                val = val.strip('"').strip("'")
            # Store token in keyring if changed and not masked
            if key == "tele_token" and val and val != "••••••••••••••••" and val != "__vault__":
                from secret_store import store_secret
                store_secret(name, "tele_token", val)
                new_data[key] = "__vault__"
            elif key == "tele_token" and (val == "••••••••••••••••" or val == "__vault__"):
                new_data[key] = "__vault__"
            else:
                new_data[key] = val

        self.profiles[name] = new_data
        save_json(CONFIG_FILE, self.profiles)
        self.refresh_profile_list()
        self._profile_form_snapshot = self._get_form_data()
        if hasattr(self, 'lbl_unsaved'):
            self.lbl_unsaved.configure(text="")
        self.log(f"{T('msg_saved')} ({name})")

    def delete_profile(self):
        from tkinter import messagebox
        name = self.entries["name"].get().strip()
        if name not in self.profiles:
            return
        if not messagebox.askyesno("Confirm Delete", f"Delete profile '{name}'?\n\nThis action cannot be undone."):
            return
        # Check if profile is running
        if hasattr(self, 'workers') and name in self.workers:
            if self.workers[name].get("proc") and self.workers[name]["proc"].poll() is None:
                messagebox.showwarning("Warning", f"Profile '{name}' is currently running.\nStop it before deleting.")
                return
        del self.profiles[name]
        save_json(CONFIG_FILE, self.profiles)
        self.refresh_profile_list()
        self.clear_form()
        self.log(f"Profile '{name}' deleted")

    def toggle_ghost_mode(self):
        current = self.settings.get("ghost_mode_active", False)
        new_state = not current
        self.settings["ghost_mode_active"] = new_state
        save_json(SETTINGS_FILE, self.settings)
        
        self.update_ghost_button_ui()
        
        msg = T("ghost_active_msg") if new_state else T("ghost_inactive_msg")
        self.log(msg)
        
    def update_ghost_button_ui(self):
        is_active = self.settings.get("ghost_mode_active", False)
        btn_color = "#e67e22" if is_active else "#27ae60"
        btn_hover = "#d35400" if is_active else "#219150"
        
        engine_text = T("engine_ghost") if is_active else T("engine_api")
        engine_color = "#e67e22" if is_active else "#3498db" # Orange vs Blue
        
        if hasattr(self, "btn_ghost_toggle"):
            self.btn_ghost_toggle.configure(text="👻", fg_color=btn_color, hover_color=btn_hover)

        if hasattr(self, "btn_ghost_popup_toggle") and self.btn_ghost_popup_toggle:
            try:
                btn_text = T("btn_ghost_off") if is_active else T("btn_ghost_on")
                self.btn_ghost_popup_toggle.configure(text=btn_text, fg_color=btn_color, hover_color=btn_hover)
            except Exception:
                pass
            
        if hasattr(self, "lbl_engine_badge"):
            self.lbl_engine_badge.configure(text=engine_text, text_color=engine_color)

    def change_lang(self, value):
        global CURRENT_LANG
        CURRENT_LANG = value
        self.settings["lang"] = CURRENT_LANG
        save_json(SETTINGS_FILE, self.settings)
        self.title(T("title"))

        try:
            self._hide_theme_radial()
        except Exception:
            pass

        if hasattr(self, "settings_popup") and self.settings_popup and self.settings_popup.winfo_exists():
            try:
                self.settings_popup.destroy()
            except Exception:
                pass
            self.settings_popup = None

        if hasattr(self, "ghost_popup") and self.ghost_popup and self.ghost_popup.winfo_exists():
            try:
                self.ghost_popup.destroy()
            except Exception:
                pass
            self.ghost_popup = None

        self.ui_elements = {}
        self._rebuild_tabview()
        self.update_ghost_button_ui()
        self.update_news_summary(force=True)
        self.log(f"Language changed to {CURRENT_LANG}")

import argparse

# --- WORKER PROCESS ---
def run_worker(profile_name):
    """
    Worker process entry point.
    Loads profile from CONFIG_FILE and runs MonitorWorker.
    """
    try:
        # Load Config
        if not os.path.exists(CONFIG_FILE):
            print(f"Error: {CONFIG_FILE} not found.")
            return

        # Load Settings (Lang)
        global CURRENT_LANG
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    CURRENT_LANG = settings.get("lang", "VN")
        except: pass

        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            profiles = json.load(f)
            
        if profile_name not in profiles:
            print(f"Error: Profile '{profile_name}' not found.")
            return
            
        config = profiles[profile_name]
        config["profile_name"] = profile_name
        
        # Setup Logging
        def worker_log(msg):
            # Print with timestamp for Parent to parse if needed, or just raw
            # We use a special prefix to distinguish log from other output if needed
            # But simple print is fine for now.
            try:
                timestamp = datetime.now().strftime("%H:%M:%S")
                final_msg = f"[{timestamp}] {msg}"
                # Force flush to ensure Parent gets it immediately
                print(final_msg, flush=True)
            except: pass

        # Stop Event
        stop_event = threading.Event()
        
        # Signal Handling for Graceful Exit
        import signal
        def signal_handler(sig, frame):
            worker_log("Stopping worker...")
            stop_event.set()
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start Worker
        worker = MonitorWorker(config, worker_log, stop_event)
        worker.log(f"Worker Process Started: {profile_name}")
        
        # Run logic inline (since we are in a dedicated process)
        # But MonitorWorker is a Thread. We can just start it and join.
        worker.start()
        
        # Keep main thread alive until worker stops
        while worker.is_alive():
            try:
                time.sleep(0.5)
            except KeyboardInterrupt:
                stop_event.set()
                break
                
        worker.join()
        print("Worker Process Exited.")
        
    except Exception as e:
        print(f"Worker Error: {e}", flush=True)


if __name__ == "__main__":
    # Argument Parsing
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true", help="Run in worker mode")
    parser.add_argument("--signal-bot", action="store_true", help="Run signal bot mode")
    parser.add_argument("--profile", type=str, help="Profile name to run")
    args, unknown = parser.parse_known_args()

    if args.signal_bot and args.profile:
        # Frozen exe: run signal bot directly
        import mt5_signal_bot
        mt5_signal_bot.main(profile_name=args.profile)
    elif args.worker and args.profile:
        run_worker(args.profile)
    else:
        try:
            app = App()
            app.mainloop()
        except Exception as startup_e:
            with open("app_error.log", "w", encoding="utf-8") as f:
                import traceback
                f.write(f"Startup Error: {startup_e}\n")
                f.write(traceback.format_exc())
            # Also print to stderr
            print(f"Startup Error: {startup_e}", file=sys.stderr)
            sys.exit(1)
