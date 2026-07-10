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
from repositories.profile_store import ProfileStore
from utils import (
    build_signal_process_cmd,
    SIGNAL_SCRIPT_MAP,
    UnsupportedFrozenProcessError,
    compute_telegram_backoff,
    get_latest_display_signal,
)
from models.app_state import AppState
from services.signal_process_supervisor import SignalProcessSupervisor
from ui.base_tab import BaseTab
from ui.signals_tab import SignalsTab
from ui.profiles_tab import ProfilesTab

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
                # 1. Focus Terminal only — do NOT send Alt+1/Alt+2.
                # On MT5 chart window those hotkeys switch chart type:
                #   Alt+1 = Bar chart, Alt+2 = Candlesticks (user complaint).
                # Old comment assumed Alt+1 = Trade tab; that was wrong for chart focus.
                self._win.set_focus()
                time.sleep(0.2)

                # 2. F9 opens Order dialog from main window (no chart-type side effect)
                self._win.type_keys("{F9}")
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
VERSION = "v3.15.2"
BUILD = 3152

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
        "about_section_theme": "GIAO DIỆN",
        "about_section_lang": "NGÔN NGỮ",
        "about_lang_vn": "Tiếng Việt",
        "about_lang_en": "English",
        "about_card_active": "Active",
        "about_card_select": "Select",
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
        "profile_list": "DANH SÁCH PROFILE",
        "btn_start_all_signals": "▶ BẮT ĐẦU TẤT CẢ",
        "btn_stop_all_signals": "■ DỪNG TẤT CẢ",
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
        "grp_config": "CẤU HÌNH PROFILE",
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

### Chốt lời từng phần (Partial)
- `Chốt XAUUSD 0.02 lot khi giá đạt 5000.00` — canh giá, chốt volume khi giá chạm.
- `Chốt vàng 0.01 khi giá 2650` — alias Vàng/Gold.
- `Lệnh 12345 lãi 200 chốt 0.01` — canh **lãi $** theo ticket.
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
- `Thứ 5` có `Thứ 4` hôm qua rơi ngày `30` hoặc `1` tây: cần tính lại W1.
- `Thứ 5` có `Thứ 6` trong tuần rơi ngày `3`, `4` hoặc `7`: cần tính lại W1.

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
        "about_section_theme": "THEME",
        "about_section_lang": "LANGUAGE",
        "about_lang_vn": "Tiếng Việt",
        "about_lang_en": "English",
        "about_card_active": "Active",
        "about_card_select": "Select",
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
        "profile_list": "PROFILE LIST",
        "btn_start_all_signals": "▶ START ALL",
        "btn_stop_all_signals": "■ STOP ALL",
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
        "grp_config": "PROFILE CONFIG",
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
        task_file = "pending_partials.json"
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
                    net_profit = pos.profit + pos.swap + pos.commission
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
                self._send_mimo_response("📋 Không có lệnh nào đang mở.")
                return
            lines = ["📋 *VỊ THẾ ĐANG MỞ:*\n"]
            for pos in positions:
                typ = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                pnl = pos.profit + pos.swap + pos.commission
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
                d_dir = state.get("d_direction") or "—"
                d_matched = state.get("d_matched_hour")
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
                    f"Hướng D: `{d_dir}`" + (f" | match H={d_matched}" if d_matched is not None else ""),
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
                    # Xóa scheduled entry trades
                    count_entries = len(self.scheduled_trades)
                    self.scheduled_trades = []
                    save_json(self.scheduled_file, self.scheduled_trades)
                    # Xóa scheduled close tasks
                    count_closes = 0
                    if hasattr(self, "_scheduled_close"):
                        count_closes = len(self._scheduled_close)
                        self._scheduled_close = []
                        save_json(self.scheduled_close_file, [])
                    # Xóa lệnh canh chốt từng phần (price/profit partials) của profile này
                    count_partials = 0
                    task_file = "pending_partials.json"
                    if os.path.exists(task_file):
                        try:
                            tasks = load_json(task_file)
                            if isinstance(tasks, dict):
                                kept = {}
                                for tid, task in tasks.items():
                                    if task.get("profile") != profile_name:
                                        kept[tid] = task
                                    else:
                                        count_partials += 1
                                save_json(task_file, kept)
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
        }
        if t in skip:
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

    def _check_scheduled_trades(self):
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
            lock_path = f"{self.scheduled_close_file}.lock" if getattr(self, "scheduled_close_file", None) else "scheduled_close.lock"
            due_batch = []
            with FileLock(lock_path, timeout=3.0) as clock:
                if clock is not None:
                    disk_closes = load_json(self.scheduled_close_file, [])
                    if not isinstance(disk_closes, list):
                        disk_closes = []
                    remaining_closes = []
                    for close_info in disk_closes:
                        if isinstance(close_info, dict):
                            c_time = close_info.get("time", "00:00:00")
                            c_date = close_info.get("date", now_date)
                            c_filter = close_info.get("filter", "all")
                            c_sym = close_info.get("sym", "")
                        else:
                            c_time = close_info
                            c_date = now_date
                            c_filter = "all"
                            c_sym = ""
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
                        due_batch.append({"filter": c_filter, "sym": c_sym})
                    self._scheduled_close = remaining_closes
                    save_json(self.scheduled_close_file, self._scheduled_close)
            profile_name = self.config.get("profile_name", "Unknown")
            for item in due_batch:
                self.notify(
                    f"⏰ [{profile_name}] Scheduled Time Reached: "
                    f"Closing Positions ({item['filter']}) {item['sym']}"
                )
                self._execute_close_all(item["filter"], item["sym"])







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
        token = resolve_telegram_token(profile_name, raw_token, global_fallback=_mimo_bot_token)
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
        token = resolve_telegram_token(profile_name, self.config.get("tele_token", ""), global_fallback=_mimo_bot_token)
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
                self.config.get("tele_token", ""),
                global_fallback=_mimo_bot_token
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
            last_heartbeat = 0.0
            try:
                _hb_store = SQLiteStore()
            except Exception:
                _hb_store = None

            # TRACKING: Initialize known tickets for closure detection
            self.known_tickets = set()
            first_run = True
            
            while not self.stop_event.is_set():
                try:
                    # Loop throttling to save CPU
                    time.sleep(0.2)

                    # Heartbeat for Dashboard Account/status bar (every ~2s)
                    if _hb_store is not None and (time.time() - last_heartbeat) >= 2.0:
                        last_heartbeat = time.time()
                        try:
                            term = mt5.terminal_info()
                            acc = mt5.account_info() if term else None
                            profile_name = self.config.get("profile_name", "") or "default"
                            if term and acc:
                                _hb_store.publish_heartbeat(
                                    profile=profile_name,
                                    state="connected",
                                    server=getattr(acc, "server", "") or "",
                                    login=int(getattr(acc, "login", 0) or 0),
                                    balance=float(getattr(acc, "balance", 0) or 0),
                                    equity=float(getattr(acc, "equity", 0) or 0),
                                    last_error="",
                                    telegram_configured=bool(
                                        resolve_telegram_token(
                                            profile_name,
                                            self.config.get("tele_token", ""),
                                            global_fallback=_mimo_bot_token,
                                        )
                                        and self.config.get("tele_chat", "")
                                    ),
                                    telegram_api_ok=False,
                                    telegram_last_check="",
                                    telegram_bot_name="",
                                )
                            else:
                                err = ""
                                try:
                                    err = str(mt5.last_error())
                                except Exception:
                                    err = "MT5 disconnected"
                                _hb_store.publish_heartbeat(
                                    profile=profile_name,
                                    state="disconnected",
                                    last_error=err[:200],
                                )
                        except Exception:
                            pass

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
# App lives in app.py + controllers/. Lazy re-export avoids circular import
# (app.py imports this domain module first, then App).

def __getattr__(name):
    if name == "App":
        from app import App as _App
        return _App
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


import argparse

# --- WORKER PROCESS ---
def run_worker(profile_name):
    """
    Worker process entry point.
    Loads profile from CONFIG_FILE and runs MonitorWorker.
    """
    lock_fd = None
    safe = re.sub(r"[^\w\-]", "_", profile_name or "unknown")
    lock_path = f"worker_{safe}.lock"

    def _acquire_worker_lock():
        """Only one worker process per profile may run (prevents double schedule fire)."""
        nonlocal lock_fd
        try:
            if os.path.exists(lock_path):
                try:
                    with open(lock_path, "r", encoding="utf-8") as f:
                        old_pid = int((f.read() or "0").strip() or "0")
                except Exception:
                    old_pid = 0
                if old_pid and old_pid != os.getpid():
                    try:
                        r = subprocess.run(
                            ["tasklist", "/FI", f"PID eq {old_pid}", "/NH"],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                        )
                        out = (r.stdout or "").lower()
                        if str(old_pid) in out and "python" in out:
                            print(
                                f"[{datetime.now().strftime('%H:%M:%S')}] "
                                f"EXIT: worker for '{profile_name}' already running (PID {old_pid}). "
                                f"Avoid multi-worker schedule double-fire.",
                                flush=True,
                            )
                            return False
                    except Exception:
                        pass
            # Exclusive create when possible; always write our pid
            try:
                lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(lock_fd, str(os.getpid()).encode("utf-8"))
            except FileExistsError:
                # Stale or race — overwrite if process dead
                with open(lock_path, "w", encoding="utf-8") as f:
                    f.write(str(os.getpid()))
            return True
        except Exception as e:
            print(f"Worker lock warning: {e}", flush=True)
            return True

    def _release_worker_lock():
        nonlocal lock_fd
        try:
            if lock_fd is not None:
                try:
                    os.close(lock_fd)
                except Exception:
                    pass
                lock_fd = None
            if os.path.exists(lock_path):
                try:
                    with open(lock_path, "r", encoding="utf-8") as f:
                        pid = (f.read() or "").strip()
                    if pid == str(os.getpid()):
                        os.remove(lock_path)
                except Exception:
                    pass
        except Exception:
            pass

    try:
        if not _acquire_worker_lock():
            return

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
        worker.log(f"Worker Process Started: {profile_name} (PID {os.getpid()}, single-instance)")
        
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
    finally:
        _release_worker_lock()


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
            # Critical: when this file is run as __main__, a later
            # `import OAK_Hidden_SLTP_Manager` would load a *second* copy of
            # the module (split state, broken Signals tab, etc.). Alias first.
            sys.modules["OAK_Hidden_SLTP_Manager"] = sys.modules[__name__]
            from app import App, main as app_main
            app_main()
        except Exception as startup_e:
            with open("app_error.log", "w", encoding="utf-8") as f:
                import traceback
                f.write(f"Startup Error: {startup_e}\n")
                f.write(traceback.format_exc())
            # Also print to stderr
            print(f"Startup Error: {startup_e}", file=sys.stderr)
            sys.exit(1)
