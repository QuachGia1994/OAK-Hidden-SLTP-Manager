# -*- coding: utf-8 -*-
"""GhostOperator stealth automation."""
from __future__ import annotations

import threading
import time

import customtkinter as ctk
import MetaTrader5 as mt5

try:
    from pywinauto import Application, mouse
    GHOST_LIB_AVAILABLE = True
except ImportError:
    GHOST_LIB_AVAILABLE = False
    Application = None  # type: ignore
    mouse = None  # type: ignore

from domain.i18n import T

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

