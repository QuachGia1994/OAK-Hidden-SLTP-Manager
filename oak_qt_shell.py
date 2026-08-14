# -*- coding: utf-8 -*-
"""Native Qt Widgets/QSS shell for OAK Manager.

This launcher avoids Qt WebEngine/Chromium so the future installer can stay
much smaller than the premium WebView experiment.

Performance optimizations:
- Lazy loading of heavy components
- Cached JSON reads with TTL
- Debounced UI updates
- Efficient style updates via property changes only
- Optimized timer intervals based on activity
"""
from __future__ import annotations

import json
import os
import re
import runpy
import signal
import sys
import threading
import time
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from domain.file_lock import FileLock
from domain.json_io import save_json
from services.debug_bundle_service import build_debug_bundle_bytes
from services.stock_advisor_desktop import (
    StockAdvisorDesktopError,
    StockAdvisorDesktopSettings,
    StockAdvisorLaunchPlan,
    build_stock_advisor_launch_plan,
    requires_d1_backfill_file,
)
from domain.constants import VERSION as APP_VERSION
from utils import UnsupportedFrozenProcessError, build_signal_process_cmd


SOURCE_ROOT = Path(__file__).resolve().parent

# Performance: Cache for JSON reads with TTL
_JSON_CACHE: dict[Path, tuple[Any, float]] = {}
_JSON_CACHE_TTL = 0.5  # seconds


def runtime_root() -> Path:
    """Return the writable app root for source or frozen mode."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return SOURCE_ROOT


ROOT = runtime_root()
PROFILE_FILE = ROOT / "profiles.json"
SETTINGS_FILE = ROOT / "settings.json"
APP_SCRIPT = SOURCE_ROOT / "OAK_Hidden_SLTP_Manager.py"


def app_icon_path() -> Path | None:
    """Resolve the bundled icon in source and frozen PyInstaller modes."""
    for folder in (SOURCE_ROOT, ROOT):
        candidate = folder / "icon.ico"
        if candidate.is_file():
            return candidate
    return None


def apply_window_icon(target: Any) -> None:
    """Apply the bundled app icon when it is available."""
    icon_path = app_icon_path()
    if icon_path is not None:
        target.setWindowIcon(QT.QIcon(str(icon_path)))


BASE_SIGNAL_DEFS = (
    ("signal_bot", "MT5 Account Audit Service", "#2fa572"),
    ("mimo_bot", "MiMo Telegram Bot", "#b33dd4"),
    ("mimo_worker", "MiMo Worker", "#d4a03d"),
    ("factcheck_worker", "Fact Check Worker", "#00bfa5"),
)


def get_visible_signal_defs() -> tuple[tuple[str, str, str], ...]:
    """Signal defs to render, register, and start."""
    return tuple(BASE_SIGNAL_DEFS)
CONSOLE_NOISE = (
    "this is a development server",
    "do not use it in a production deployment",
    " * running on http",
    " * debug mode:",
    "press ctrl+c to quit",
    "werkzeug",
    "debugger is active",
    "debugger pin code",
)
PROFILE_TEXT_FIELDS = (
    ("Profile name", "profile_name"),
    ("Terminal path", "path"),
    ("Magic number", "magic"),
    ("Symbol filter", "symbol"),
    ("Stop loss", "sl"),
    ("Take profit", "tp"),
    ("Gold stop loss", "gold_sl"),
    ("Gold take profit", "gold_tp"),
    ("Balance SL %", "balance_sl_pct"),
    ("Balance TP %", "balance_tp_pct"),
    ("Partial close R", "partial_r"),
    ("Partial close %", "partial_pct"),
    ("Auto BE R", "auto_be"),
    ("Telegram token", "tele_token"),
    ("Telegram chat", "tele_chat"),
    ("Admin chat", "tele_admin"),
    ("Copy role", "copy_role"),
    ("Copy channel", "copy_channel"),
    ("Copy lot mode", "copy_lot_mode"),
    ("Copy lot value", "copy_lot_value"),
    ("Copy ignore list", "copy_ignore_list"),
    ("Copy max daily", "copy_max_daily_trades"),
    ("Copy max lot", "copy_max_lot_per_trade"),
    ("Copy max exposure", "copy_max_exposure"),
)
PROFILE_BOOL_FIELDS = (
    ("Use balance SL/TP", "use_balance_sltp"),
    ("Visible SL/TP", "visible_sltp"),
    ("Copy stealth", "copy_stealth"),
    ("Copy max one", "copy_max_one"),
    ("Copy kill switch", "copy_kill_switch"),
)
PENDING_DONE_STATUSES = {"done", "executed", "closed", "expired", "cancelled", "canceled"}
PENDING_META_KEYS = {"_pending_file", "_pending_shape", "_pending_key", "_pending_index", "_pending_identity"}
LOG_LEVEL_MARKERS = {
    "ERROR": ("ERROR", "[ERR", "Traceback", "Exception", "FAILED", "CRITICAL"),
    "WARN": ("WARN", "WARNING", "CAUTION"),
    "INFO": ("INFO", "[OK]", "START", "CONNECTED", "RUNNING"),
}
NATIVE_LANGUAGE = "EN"
ANALYSIS_KPI_HELP = {
    "Net P&L": {
        "EN": "Realized trading P/L from closed positions. It excludes external deposits/withdrawals and is separate from floating P/L.",
        "VN": "Lãi/lỗ giao dịch đã chốt từ các vị thế đóng. Không tính nộp/rút tiền và tách biệt với lãi/lỗ đang nổi.",
    },
    "Trading return": {
        "EN": "Trading return (%) = (ending balance − starting balance − net external cash flow) / starting balance. It measures trading performance, not cash deposits.",
        "VN": "Trading return (%) = (số dư cuối − số dư đầu − dòng tiền ngoài ròng) / số dư đầu. Đo hiệu quả giao dịch, không tính tiền nộp/rút.",
    },
    "Win rate": {
        "EN": "Win rate = winning closed positions / (winning + losing closed positions). Entry deals and scratch trades are not counted as wins or losses.",
        "VN": "Tỷ lệ thắng = vị thế đóng có lãi / (vị thế đóng có lãi + vị thế đóng có lỗ). Deal vào lệnh và lệnh hòa vốn không được tính thắng/thua.",
    },
    "Profit factor": {
        "EN": "Profit factor = gross profit / gross loss across closed positions. Higher than 1 means gross winning P/L exceeds gross losing P/L.",
        "VN": "Profit factor = tổng lãi gộp / tổng lỗ gộp của các vị thế đóng. Lớn hơn 1 nghĩa là tổng lãi thắng vượt tổng lỗ.",
    },
    "Expectancy": {
        "EN": "Expectancy = (gross profit − gross loss) / decided closed positions. It is the average realized trading outcome per decided position before separate fees.",
        "VN": "Expectancy = (tổng lãi gộp − tổng lỗ gộp) / số vị thế đóng có kết quả. Đây là kết quả giao dịch trung bình mỗi vị thế, trước các loại phí tách riêng.",
    },
    "Current drawdown": {
        "EN": "Current drawdown = latest equity peak − current equity, using the available equity-sample/checkpoint curve.",
        "VN": "Drawdown hiện tại = đỉnh vốn gần nhất − vốn hiện tại, tính trên chuỗi mẫu equity/checkpoint hiện có.",
    },
    "Max drawdown": {
        "EN": "Maximum peak-to-trough equity drawdown observed in the available equity samples. Source is shown in the account audit data.",
        "VN": "Drawdown vốn tối đa từ một đỉnh xuống đáy trong chuỗi equity hiện có. Nguồn dữ liệu được ghi trong kiểm toán tài khoản.",
    },
    "Avg win": {
        "EN": "Average realized profit of winning closed positions only.",
        "VN": "Lãi trung bình chỉ của các vị thế đóng có kết quả dương.",
    },
    "Avg loss": {
        "EN": "Average absolute loss of losing closed positions only.",
        "VN": "Mức lỗ trung bình theo trị tuyệt đối, chỉ của các vị thế đóng có kết quả âm.",
    },
    "Account growth": {
        "EN": "Account growth (%) = (ending balance − starting balance) / starting balance. Unlike trading return, it includes net external cash flow.",
        "VN": "Tăng trưởng tài khoản (%) = (số dư cuối − số dư đầu) / số dư đầu. Khác trading return, chỉ số này bao gồm tác động dòng tiền ngoài ròng.",
    },
}
NATIVE_TEXT = {
    "EN": {"Signals": "Account Tracking"},
    "VN": {
        "Dashboard": "Bảng điều khiển",
        "Signals": "Tín hiệu",
        "VN30 Advisor": "Bộ lọc CP",
        "Profiles": "Hồ sơ",
        "Copy": "Sao chép",
        "Pending": "Lệnh chờ",
        "Diagnostics": "Chẩn đoán",
        "Settings": "Cài đặt",
        "ONE-CLICK STOCK FILTER": "BỘ LỌC CỔ PHIẾU BẰNG LOCAL EOD",
        "LOCAL EOD MARKET DATA": "DỮ LIỆU THỊ TRƯỜNG LOCAL EOD",
        "Hurdle (bps)": "Chi phí + biên an toàn (bps)",
        "Update EOD Data (15:00+)": "Cập nhật dữ liệu EOD (15h00+)",
        "Run advisor": "Chạy bộ lọc Cổ phiếu",
        "Run VN30 Advisor": "Chạy bộ lọc Cổ phiếu",
        "ADVISORY RESULT": "KẾT QUẢ KHUYẾN NGHỊ",
        "LOCAL EOD STOCKS": "CỔ PHIẾU LOCAL EOD",
        "Filter symbols…": "Lọc mã…",
        "Local EOD Database (data/market.db) · Auto-updated after 15:00": "Cơ sở dữ liệu Local EOD (data/market.db) · Tự động cập nhật sau 15h00",
        "Local EOD Mode: No API key or account required.": "Chế độ Local EOD: Không cần API key hay tài khoản.",
        "Updating local EOD data...": "Đang cập nhật dữ liệu EOD...",
        "EOD data updated successfully.": "Đã cập nhật dữ liệu EOD thành công.",
        "Press Run VN30 Advisor to scan 30 constituents using local EOD data.": "Nhấn Chạy bộ lọc Cổ phiếu để quét toàn sàn bằng dữ liệu Local EOD.",
        "Recommendation only": "Chỉ khuyến nghị",
        "Local EOD Mode": "Chế độ Local EOD",
        "NO API KEY": "KHÔNG CẦN API KEY",
        "100% free local SQLite database (market.db).": "Cơ sở dữ liệu SQLite cục bộ 100% miễn phí (market.db).",
        "CONFIRM": "XÁC NHẬN",
        "User confirmation is required before every real trade.": "User phải xác nhận trước mọi giao dịch thật.",
        "Execution": "Thực thi",
        "DISABLED": "ĐÃ TẮT",
        "This module has no order submission capability.": "Module này không có khả năng gửi lệnh.",
        "Advisor settings saved.": "Đã lưu cài đặt bộ lọc.",
        "Running VN30 advisor...": "Đang chạy bộ lọc Cổ phiếu...",
        "Auto backfill: pausing Signal Bot...": "Tự backfill: đang tạm dừng Signal Bot...",
        "Advisor completed and dashboard updated.": "Bộ lọc hoàn tất và cập nhật dashboard thành công.",
        "Advisor completed locally; dashboard push needs configuration.": "Bộ lọc hoàn tất (local). Dashboard cập nhật khi có Redis/VPS.",
        "PROFILE": "HỒ SƠ",
        "Start selected": "Chạy profile đã chọn",
        "Stop selected": "Dừng profile đã chọn",
        "Refresh": "Làm mới",
        "Open classic UI": "Mở giao diện cổ điển",
        "Heartbeat ready": "Heartbeat sẵn sàng",
        "TRADING COMMAND CENTER": "TRUNG TÂM ĐIỀU HÀNH",
        "Native Qt/QSS shell · no WebEngine": "Native Qt/QSS · không WebEngine",
        "Running": "Đang chạy",
        "Stopped": "Đã dừng",
        "Degraded": "Suy giảm",
        "Blocked": "Bị chặn",
        "RUNNING": "ĐANG CHẠY",
        "IDLE": "NHÀN RỖI",
        "ON": "BẬT",
        "OFF": "TẮT",
        "None": "Không",
        "Ready": "Sẵn sàng",
        "Start": "Chạy",
        "Stop": "Dừng",
        "LANGUAGE": "NGÔN NGỮ",
        "THEME": "GIAO DIỆN",
        "Language": "Ngôn ngữ",
        "Theme": "Giao diện",
        "PROFILES": "HỒ SƠ",
        "LIVE CONSOLE": "NHẬT KÝ TRỰC TIẾP",
        "Clear logs": "Xóa nhật ký",
        "Copy log": "Sao chép nhật ký",
        "Start all": "Chạy tất cả",
        "Stop all": "Dừng tất cả",
        "PROFILE MAP": "DANH SÁCH HỒ SƠ",
        "PROFILE EDITOR": "CHỈNH SỬA HỒ SƠ",
        "No profile selected": "Chưa chọn hồ sơ",
        "Changes are saved to profiles.json": "Thay đổi được lưu vào profiles.json",
        "Save": "Lưu",
        "Duplicate": "Nhân bản",
        "Add new": "Thêm mới",
        "Delete": "Xóa",
        "Profile name": "Tên hồ sơ",
        "Terminal path": "Đường dẫn terminal",
        "Magic number": "Magic number",
        "Symbol filter": "Bộ lọc symbol",
        "Stop loss": "Dừng lỗ",
        "Take profit": "Chốt lời",
        "Gold stop loss": "Dừng lỗ Vàng",
        "Gold take profit": "Chốt lời Vàng",
        "Balance SL %": "SL theo số dư %",
        "Balance TP %": "TP theo số dư %",
        "Partial close R": "Chốt một phần R",
        "Partial close %": "Chốt một phần %",
        "Auto BE R": "Tự động BE R",
        "Telegram token": "Token Telegram",
        "Telegram chat": "Chat Telegram",
        "Admin chat": "Chat quản trị",
        "Copy role": "Vai trò copy",
        "Copy channel": "Kênh copy",
        "Copy lot mode": "Chế độ lot copy",
        "Copy lot value": "Giá trị lot copy",
        "Copy ignore list": "Danh sách bỏ qua copy",
        "Copy max daily": "Giới hạn copy mỗi ngày",
        "Copy max lot": "Giới hạn lot copy",
        "Copy max exposure": "Giới hạn exposure copy",
        "Use balance SL/TP": "Dùng SL/TP theo số dư",
        "Visible SL/TP": "Hiện SL/TP",
        "Visible SL/TP {state}": "Hiện SL/TP: {state}",
        "Copy {role}": "Sao chép: {role}",
        "Kill {state}": "Ngắt khẩn: {state}",
        "Copy stealth": "Copy ẩn",
        "Copy max one": "Tối đa một lệnh copy",
        "Copy kill switch": "Ngắt copy khẩn cấp",
        "COPY SETTINGS": "CÀI ĐẶT COPY",
        "Exact profile match": "Khớp hồ sơ chính xác",
        "Telegram commands stay scoped to the selected profile.": "Lệnh Telegram luôn được giới hạn trong hồ sơ đang chọn.",
        "Blocks all new copy entries when ON.": "Chặn mọi lệnh copy mới khi đang BẬT.",
        "Max one trade/symbol": "Tối đa một lệnh/mã",
        "Blocks duplicate symbol stacking when enabled.": "Ngăn chồng lệnh trùng mã khi được bật.",
        "Daily / lot / exposure caps": "Giới hạn ngày / lot / exposure",
        "{daily} trades/day · {lot} lot/order · {exposure} lot/symbol": "{daily} lệnh/ngày · {lot} lot/lệnh · {exposure} lot/mã",
        "Stealth copy": "Copy ẩn",
        "Keeps copy execution quiet unless a response is required.": "Giữ thao tác copy yên lặng, trừ khi cần phản hồi.",
        "Ignore list": "Danh sách bỏ qua",
        "Symbols listed here are skipped by copy trading.": "Các mã trong danh sách này sẽ không được copy.",
        "ARMED": "SẴN SÀNG",
        "KILL SWITCH ON": "NGẮT KHẨN ĐANG BẬT",
        "Lot mode": "Chế độ lot",
        "Lot value": "Giá trị lot",
        "Max daily trades": "Tối đa lệnh mỗi ngày",
        "Max lot/trade": "Tối đa lot/lệnh",
        "Max exposure/symbol": "Tối đa exposure/mã",
        "Stealth": "Ẩn",
        "SAFETY GUARDRAILS": "RÀO CHẮN AN TOÀN",
        "SESSION FILES": "FILE PHIÊN LÀM VIỆC",
        "SCHEDULED TASKS": "TÁC VỤ ĐÃ HẸN",
        "PENDING CONTROL": "ĐIỀU KHIỂN LỆNH CHỜ",
        "Total tasks: {count}": "Tổng tác vụ: {count}",
        "Waiting: {count}": "Đang chờ: {count}",
        "Done/closed: {count}": "Đã xong/đóng: {count}",
        "{name}: {count} item(s)": "{name}: {count} tác vụ",
        "No scheduled tasks": "Không có tác vụ đã hẹn",
        "No waiting orders, scheduled closes, or partial tasks.": "Không có lệnh chờ, tác vụ đóng hẹn giờ hoặc chốt từng phần.",
        "CLEAN": "SẠCH",
        "Clear done": "Xóa tác vụ xong",
        "Pending controls are profile-scoped.": "Điều khiển tác vụ chờ theo từng hồ sơ.",
        "Copy report": "Sao chép báo cáo",
        "Copy visible": "Sao chép phần hiển thị",
        "Export bundle": "Xuất gói chẩn đoán",
        "App folder": "Thư mục ứng dụng",
        "Log folder": "Thư mục log",
        "Clear display": "Xóa hiển thị",
        "Search logs: profile, ERROR, ticket, symbol...": "Tìm log: hồ sơ, ERROR, ticket, symbol...",
        "Diagnostics export is redacted by default.": "Gói chẩn đoán mặc định đã che dữ liệu nhạy cảm.",
        "RUNTIME CHECK": "KIỂM TRA RUNTIME",
        "LATEST LOG": "LOG MỚI NHẤT",
        "Dashboard language preference.": "Ngôn ngữ ưu tiên của dashboard.",
        "NativeQt visual skin. Applies instantly after save.": "Giao diện NativeQt. Áp dụng ngay sau khi lưu.",
        "Save settings": "Lưu cài đặt",
        "Reset theme": "Đặt lại giao diện",
        "Open artifacts": "Mở gói phát hành",
        "Settings are stored in settings.json.": "Cài đặt được lưu trong settings.json.",
        "Settings saved and theme applied.": "Đã lưu cài đặt và áp dụng giao diện.",
        "OAK Manager NativeQt": "OAK Manager NativeQt",
        "Mode: Qt Widgets + QSS, no WebEngine/Chromium": "Chế độ: Qt Widgets + QSS, không WebEngine/Chromium",
        "Root: {root}": "Thư mục gốc: {root}",
        "Profiles: {count}": "Hồ sơ: {count}",
        "Selected profile: {profile}": "Hồ sơ đang chọn: {profile}",
        "Language: {language}": "Ngôn ngữ: {language}",
        "Theme: {theme}": "Giao diện: {theme}",
        "License: MIT © 2026 QKP": "Bản quyền: MIT © 2026 QKP",
        "Third-party notices: THIRD_PARTY_NOTICES.md": "Ghi chú bên thứ ba: THIRD_PARTY_NOTICES.md",
        "Shortcuts:": "Phím tắt:",
        "- Ctrl+1..8: switch tabs.": "- Ctrl+1..8: chuyển tab.",
        "- Ctrl+R / F5: refresh runtime state.": "- Ctrl+R / F5: làm mới trạng thái runtime.",
        "- Ctrl+S: save Profiles or Settings.": "- Ctrl+S: lưu Hồ sơ hoặc Cài đặt.",
        "- Esc: clear delete confirmation guards.": "- Esc: hủy xác nhận xóa.",
        "Cleanup policy:": "Chính sách dọn dẹp:",
        "- Keep source, docs, profiles examples, installers, and scripts.": "- Giữ source, docs, profile mẫu, installer và script.",
        "- Ignore runtime state: trades_*.json, waiting_*.json, locks, logs, caches.": "- Bỏ qua state runtime: trades_*.json, waiting_*.json, lock, log, cache.",
        "- Do not delete real trade/runtime state unless explicitly confirmed.": "- Không xóa state giao dịch/runtime thật nếu chưa được xác nhận.",
        "Artifacts:": "Gói phát hành:",
        "missing": "thiếu",
        "Installer": "Installer",
        "Current NativeQt installer stays around 40 MB.": "Installer NativeQt hiện giữ ở khoảng 40 MB.",
        "ABOUT / BUILD": "THÔNG TIN / BẢN BUILD",
        "No profiles found": "Không tìm thấy hồ sơ",
        "SETUP": "THIẾT LẬP",
        "No terminal path": "Chưa có đường dẫn terminal",
        "Selected": "Đang chọn",
        "Use": "Chọn",
        "Profile": "Hồ sơ",
        "Profile: {profile}": "Hồ sơ: {profile}",
        "Status": "Trạng thái",
        "Terminal": "Terminal",
        "Role": "Vai trò",
        "Channel": "Kênh",
        "Daily cap": "Giới hạn ngày",
        "Lot cap": "Giới hạn lot",
        "Exposure cap": "Giới hạn exposure",
        "Kill switch": "Ngắt khẩn cấp",
        "COPY STATUS": "TRẠNG THÁI COPY",
        "EXECUTION": "THỰC THI",
        "SAFETY LIMITS": "GIỚI HẠN AN TOÀN",
        "PROFILE HEALTH": "TRẠNG THÁI HỒ SƠ",
        "COPY RISK LIMITS": "GIỚI HẠN RỦI RO COPY",
        "MASKED SECRETS": "THÔNG TIN ĐÃ CHE",
        "Manual refresh": "Đã làm mới",
        "Live": "Trực tuyến",
        "No save target": "Không có nội dung để lưu",
        "Delete guard cleared.": "Đã hủy xác nhận xóa.",
        "Unsaved changes": "Thay đổi chưa lưu",
        "No log file found.": "Không tìm thấy file log.",
        "Display cleared. Press Refresh to reload logs.": "Đã xóa hiển thị. Nhấn Làm mới để tải lại log.",
        "Selected profile: {profile} · Native Qt/QSS, no Chromium": "Hồ sơ đang chọn: {profile} · Native Qt/QSS, không Chromium",
        "{running}/{total} running": "{running}/{total} đang chạy",
        "OPERATIONS": "VẬN HÀNH",
        "ANALYSIS": "PHÂN TÍCH",
        "LIVE STATUS": "TRẠNG THÁI TRỰC TUYẾN",
        "running": "đang chạy",
        "Accounts": "Tài khoản",
        "Performance": "Hiệu suất",
        "History": "Lịch sử",
        "News": "Tin tức",
        "Analysis": "Phân tích",
        "Account overview": "Tổng quan tài khoản",
        "Live positions": "Vị thế đang mở",
        "No account audit data": "Chưa có dữ liệu kiểm toán tài khoản",
        "No open positions": "Không có vị thế mở",
        "Performance metrics": "Chỉ số hiệu suất",
        "Equity curve": "Đường vốn",
        "Drawdown": "Drawdown",
        "No performance data": "Chưa có dữ liệu hiệu suất",
        "History ledger": "Sổ giao dịch",
        "Checkpoints": "Checkpoint",
        "No trade history": "Chưa có lịch sử giao dịch",
        "No checkpoints": "Chưa có checkpoint",
        "Economic news": "Tin tức kinh tế",
        "Refresh news": "Làm mới tin tức",
        "No economic news": "Chưa có tin tức kinh tế",
        "News unavailable": "Nguồn tin tức chưa khả dụng",
        "Stale news cache": "Cache tin tức đã cũ",
        "Broker day": "Ngày broker",
        "Cache day": "Ngày cache",
        "Updated": "Cập nhật",
        "Balance": "Số dư",
        "Equity": "Vốn",
        "Margin": "Ký quỹ",
        "Free margin": "Ký quỹ trống",
        "Margin level": "Mức ký quỹ",
        "Floating P/L": "Lãi/lỗ nổi",
        "Open profit": "Lãi/lỗ đang mở",
        "Profile": "Hồ sơ",
        "Symbol": "Symbol",
        "Direction": "Hướng",
        "Volume": "Khối lượng",
        "Open price": "Giá vào",
        "Source": "Nguồn",
        "Time": "Thời gian",
        "Type": "Loại",
        "Reason": "Lý do",
        "Profit": "Lãi/lỗ",
        "Commission": "Phí GD",
        "Swap": "Swap",
        "Date": "Ngày",
        "Hour": "Giờ",
        "Status": "Trạng thái",
        "Mode": "Chế độ",
        "Net profit": "Lợi nhuận ròng",
        "Profit factor": "Profit factor",
        "Win rate": "Tỷ lệ thắng",
        "Average win": "Lãi TB",
        "Average loss": "Lỗ TB",
        "Expectancy": "Expectancy",
        "Max equity drawdown": "Drawdown vốn tối đa",
        "Current drawdown": "Drawdown hiện tại",
        "Account growth": "Tăng trưởng tài khoản",
        "Trading return": "Trading return",
        "Open positions": "Vị thế mở",
        "Closed deals": "Lệnh đã đóng",
        "Realized P/L": "Lãi/lỗ đã chốt",
        "Total commission": "Tổng phí giao dịch",
        "Total swap": "Tổng swap",
        "All symbols": "Tất cả symbol",
        "All types": "Tất cả loại",
        "All currencies": "Tất cả tiền tệ",
        "All impact": "Tất cả mức độ",
        "Search symbol or reason…": "Tìm symbol hoặc lý do…",
        "Audit checkpoint": "Checkpoint kiểm toán",
        "samples": "mẫu",
        "Captured": "Ghi nhận",
        "High": "Cao",
        "Medium": "Trung bình",
        "Low": "Thấp",
        "Total": "Tổng",
    },
}


def set_native_language(value: str) -> None:
    """Select the supported NativeQt display language."""
    global NATIVE_LANGUAGE
    candidate = str(value or "").upper()
    NATIVE_LANGUAGE = candidate if candidate in NATIVE_TEXT else "EN"


def native_text(value: Any) -> str:
    """Translate one fixed NativeQt string while preserving unknown runtime data."""
    text = str(value)
    catalog = NATIVE_TEXT.get(NATIVE_LANGUAGE, {})
    translated = catalog.get(text)
    if translated is not None:
        return translated
    if text.isupper():
        for source, localized in catalog.items():
            if source.upper() == text:
                return localized.upper()
    return text


def native_format(template: str, **values: Any) -> str:
    """Translate and interpolate a NativeQt message safely."""
    localized_values = {
        key: native_text(value) if isinstance(value, str) else value
        for key, value in values.items()
    }
    return native_text(template).format(**localized_values)


def read_json(path: Path, default: Any) -> Any:
    """Read JSON with TTL caching to reduce disk I/O."""
    now = time.time()
    if path in _JSON_CACHE:
        cached_value, cached_time = _JSON_CACHE[path]
        if now - cached_time < _JSON_CACHE_TTL:
            return cached_value
    
    if not path.exists():
        _JSON_CACHE[path] = (default, now)
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        _JSON_CACHE[path] = (value, now)
        return value
    except (OSError, json.JSONDecodeError):
        _JSON_CACHE[path] = (default, now)
        return default


def invalidate_json_cache(path: Path | None = None) -> None:
    """Invalidate JSON cache for a specific path or all paths."""
    if path is not None:
        _JSON_CACHE.pop(path, None)
    else:
        _JSON_CACHE.clear()


def write_json_atomic(path: Path, payload: Any) -> None:
    """Write JSON through the shared unique-temp atomic writer."""
    save_json(path, payload)
    invalidate_json_cache(path)  # Invalidate cache after write


def normalize_profile_name(value: str) -> str:
    """Return a safe non-empty profile name."""
    clean = re.sub(r"\s+", " ", (value or "").strip())
    return clean or "NewProfile"


def unique_profile_name(existing: set[str], base: str) -> str:
    """Return a unique profile name using a compact numeric suffix."""
    root = normalize_profile_name(base)
    if root not in existing:
        return root
    index = 2
    while f"{root} {index}" in existing:
        index += 1
    return f"{root} {index}"


def public_pending_item(item: dict[str, Any]) -> dict[str, Any]:
    """Return a pending item without NativeQt metadata keys."""
    return {key: value for key, value in item.items() if key not in PENDING_META_KEYS}


def pending_identity(item: dict[str, Any]) -> str:
    """Build a stable identity string for cautious row deletion."""
    return json.dumps(public_pending_item(item), ensure_ascii=False, sort_keys=True, default=str)


def pending_file_specs(root: Path, profile_name: str) -> list[tuple[str, Path, str]]:
    """Return pending persistence files for a profile."""
    safe = safe_profile_filename(profile_name)
    return [
        ("entries", root / f"waiting_{safe}.json", "list"),
        ("scheduled closes", root / f"scheduled_close_{safe}.json", "list"),
        ("partials", root / f"pending_partials_{safe}.json", "dict"),
    ]


def pending_rows(kind: str, path: Path, data: Any, shape: str) -> list[dict[str, Any]]:
    """Normalize list/dict pending persistence into UI rows."""
    rows: list[dict[str, Any]] = []
    if shape == "dict" and isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                item = {"kind": kind, "ticket": key, **value}
            else:
                item = {"kind": kind, "ticket": key, "value": value}
            item["_pending_file"] = str(path)
            item["_pending_shape"] = shape
            item["_pending_key"] = str(key)
            item["_pending_identity"] = pending_identity(item)
            rows.append(item)
        return rows
    if isinstance(data, list):
        for index, value in enumerate(data):
            if isinstance(value, dict):
                item = {"kind": kind, **value}
            else:
                item = {"kind": kind, "value": value}
            item["_pending_file"] = str(path)
            item["_pending_shape"] = "list"
            item["_pending_index"] = index
            item["_pending_identity"] = pending_identity(item)
            rows.append(item)
    return rows


def remove_pending_item_from_data(data: Any, item: dict[str, Any]) -> tuple[Any, bool]:
    """Remove one normalized pending item from list/dict data."""
    shape = item.get("_pending_shape")
    if shape == "dict" and isinstance(data, dict):
        key = str(item.get("_pending_key", ""))
        if key in data:
            updated = dict(data)
            updated.pop(key, None)
            return updated, True
        return data, False
    if not isinstance(data, list):
        return data, False
    target_identity = str(item.get("_pending_identity") or "")
    index = item.get("_pending_index")
    if isinstance(index, int) and 0 <= index < len(data):
        candidate = pending_rows(str(item.get("kind") or "task"), Path(item.get("_pending_file", "")), [data[index]], "list")[0]
        if candidate.get("_pending_identity") == target_identity:
            return data[:index] + data[index + 1 :], True
    for pos, row in enumerate(data):
        candidate = pending_rows(str(item.get("kind") or "task"), Path(item.get("_pending_file", "")), [row], "list")[0]
        if candidate.get("_pending_identity") == target_identity:
            return data[:pos] + data[pos + 1 :], True
    return data, False


def clear_done_pending_data(data: Any) -> tuple[Any, int]:
    """Remove completed rows from list-based pending files."""
    if not isinstance(data, list):
        return data, 0
    kept = []
    removed = 0
    for row in data:
        status = str(row.get("status") if isinstance(row, dict) else "").lower()
        if status in PENDING_DONE_STATUSES:
            removed += 1
        else:
            kept.append(row)
    return kept, removed


def mutate_pending_file(
    path: Path,
    default: Any,
    mutator: Callable[[Any], tuple[Any, Any]],
) -> tuple[Any, Any]:
    """Reload, mutate, and persist one pending file without losing updates."""
    if path.name.startswith("scheduled_close_") and path.suffix == ".json":
        with FileLock(f"{path}.lock", timeout=3.0) as lock:
            if lock is None:
                raise TimeoutError(f"Timed out locking {path.name}")
            return _mutate_pending_file_unlocked(path, default, mutator)
    return _mutate_pending_file_unlocked(path, default, mutator)


def _mutate_pending_file_unlocked(
    path: Path,
    default: Any,
    mutator: Callable[[Any], tuple[Any, Any]],
) -> tuple[Any, Any]:
    data = read_json(path, default)
    updated, result = mutator(data)
    if result:
        write_json_atomic(path, updated)
    return updated, result


def log_line_matches_level(line: str, level: str) -> bool:
    """Return whether a log line matches a coarse display level."""
    normalized = (level or "ALL").upper()
    if normalized == "ALL":
        return True
    markers = LOG_LEVEL_MARKERS.get(normalized, ())
    upper_line = line.upper()
    return any(marker.upper() in upper_line for marker in markers)


def filter_log_text(text: str, query: str = "", level: str = "ALL", max_lines: int = 800) -> str:
    """Filter log text by level and whitespace-separated search terms."""
    if not text:
        return ""
    terms = [term.lower() for term in (query or "").split() if term.strip()]
    kept: list[str] = []
    for line in text.splitlines():
        lower_line = line.lower()
        if terms and not all(term in lower_line for term in terms):
            continue
        if not log_line_matches_level(line, level):
            continue
        kept.append(line)
    if max_lines > 0:
        kept = kept[-max_lines:]
    return "\n".join(kept)


def filter_analysis_history_deals(
    deals: list[dict[str, Any]],
    symbol: str = "All symbols",
    deal_type: str = "All types",
    search: str = "",
) -> list[dict[str, Any]]:
    """Filter public trade history without mutating the source list."""
    search_text = str(search or "").strip().lower()
    result = []
    for deal in deals:
        if symbol != "All symbols" and str(deal.get("symbol") or "") != symbol:
            continue
        if deal_type != "All types" and str(deal.get("deal_type") or "").upper() != deal_type.upper():
            continue
        haystack = " ".join(
            str(deal.get(key) or "")
            for key in ("symbol", "reason_category", "entry_type", "deal_type")
        ).lower()
        if search_text and search_text not in haystack:
            continue
        result.append(deal)
    return result


def filter_analysis_news_items(
    items: list[dict[str, Any]],
    currency: str = "All currencies",
    impact: str = "All impact",
) -> list[dict[str, Any]]:
    """Filter cached news items without mutating the source list."""
    result = []
    for item in items:
        item_currency = str(item.get("currency") or "").upper()
        item_impact = str(item.get("impact") or "").upper()
        if currency != "All currencies" and item_currency != currency.upper():
            continue
        if impact != "All impact" and item_impact != impact.upper():
            continue
        result.append(item)
    return result


def write_bytes_atomic(path: Path, payload: bytes) -> None:
    """Write bytes through a same-folder temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_bytes(payload)
    temp_path.replace(path)


def load_qt() -> tuple[SimpleNamespace | None, str]:
    """Import only QtCore/QtGui/QtWidgets, never QtWebEngine."""
    try:
        from PySide6.QtCore import QEasingCurve, QProcess, QProcessEnvironment, QPropertyAnimation, QSize, Qt, QTimer
        from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QKeySequence, QShortcut
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QDialog,
            QFrame,
            QGraphicsOpacityEffect,
            QGridLayout,
            QHBoxLayout,
            QHeaderView,
            QLabel,
            QLineEdit,
            QMainWindow,
            QProgressBar,
            QPushButton,
            QMessageBox,
            QScrollArea,
            QSizePolicy,
            QStackedWidget,
            QTableWidget,
            QTableWidgetItem,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        return None, str(exc)
    return (
        SimpleNamespace(**locals(), NotRunning=QProcess.ProcessState.NotRunning),
        "",
    )


def app_qss(theme: str = "dark") -> str:
    """Return the native Qt stylesheet matching the Tauri design tokens."""
    base = """
    QMainWindow{background:#0b0f14}
    QWidget{font-family:"Segoe UI";font-size:14px;color:#e6edf3}
    QWidget#StockAdvisorControls{background:#111820}
    #Root{background:qradialgradient(cx:.08,cy:.02,radius:1,fx:.08,fy:.02,stop:0 rgba(47,165,114,0.13),stop:.42 #0b0f14,stop:1 #0b0f14)}
    QFrame[role="panel"]{background:#111820;border:1px solid #1e2937;border-radius:18px}
    QFrame[role="row"]{background:#0b0f14;border:1px solid #1e2937;border-radius:14px}
    QFrame[role="row"][active="true"]{border:1px solid #2fa572;background:rgba(47,165,114,.06)}
    QFrame[role="hint"]{background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.38);border-radius:12px}
    QFrame[role="signal"]{background:#111820;border:1px solid #1e2937;border-radius:14px}
    QFrame[role="signal"][state="running"]{border:1px solid #2fa572;background:rgba(47,165,114,.06)}
    QFrame[role="signal"][state="degraded"]{border:1px solid #f59e0b;background:rgba(245,158,11,.07)}
    QFrame[role="stat"]{background:#0b0f14;border:1px solid #1e2937;border-radius:14px}
    QLabel[role="tiny"]{color:#8b98a5;font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase}
    QLabel[role="muted"]{color:#8b98a5;font-size:12px}
    QLabel[role="stockStatus"]{color:#d6dde4;font-size:12px;font-weight:700;padding:4px 2px}
    QLabel[role="progress"]{color:#2fa572;font-size:12px;font-weight:700;padding:2px 2px}
    QLabel[role="section"]{font-size:20px;font-weight:800}
    QLabel[role="title"]{font-size:40px;font-weight:800}
    QLabel[role="value"]{font-family:Consolas;font-size:22px;font-weight:700}
    QLabel[role="status"]{border-radius:999px;padding:6px 10px;background:rgba(47,165,114,.10);color:#2fa572;font-size:12px;font-weight:700}
    QLabel[role="status"][mode="LIVE"]{background:rgba(47,165,114,.14);color:#2fa572;border:1px solid rgba(47,165,114,.45)}
    QLabel[role="status"][mode="DEMO"]{background:rgba(245,158,11,.12);color:#f59e0b;border:1px solid rgba(245,158,11,.45)}
    QLabel[role="status"][mode="UNKNOWN"]{background:rgba(139,152,165,.12);color:#8b98a5;border:1px solid rgba(139,152,165,.35)}
    QLabel[role="status"][mode="READY"]{background:rgba(47,165,114,.12);color:#2fa572;border:1px solid rgba(47,165,114,.40)}
    QLabel[role="status"][mode="DEGRADED"]{background:rgba(245,158,11,.12);color:#f59e0b;border:1px solid rgba(245,158,11,.45)}
    QLabel[role="status"][mode="UNAVAILABLE"]{background:rgba(239,68,68,.10);color:#ef4444;border:1px solid rgba(239,68,68,.40)}
    QLabel[role="status"][mode="STALE"]{background:rgba(245,158,11,.10);color:#f59e0b;border:1px solid rgba(245,158,11,.35)}
    QToolTip{background:#111820;color:#e6edf3;border:1px solid #1e2937;padding:8px 10px;border-radius:8px;font-size:12px}
    QLabel[accent="green"]{color:#2fa572}QLabel[accent="amber"]{color:#f59e0b}QLabel[accent="red"]{color:#ef4444}QLabel[accent="theme"]{color:#2fa572}
    QPushButton{background:#111820;border:1px solid #1e2937;border-radius:8px;padding:7px 14px;color:#e6edf3;font-weight:600;text-align:center}
    QPushButton:hover{border:1px solid #2fa572}
    QPushButton:disabled{color:#5b6672;border:1px solid #1e2937;background:#0d1219}
    QPushButton[primary="true"]:enabled{background:rgba(47,165,114,.15);border:1px solid #2fa572;color:#2fa572}
    QPushButton[active="true"]{background:rgba(47,165,114,.15);border:1px solid #2fa572;color:#2fa572}
    QPushButton[compact="true"]{padding:4px 10px}
    QPushButton[intent="positive"]{color:#2fa572;border:1px solid rgba(47,165,114,.55);background:rgba(47,165,114,.12)}
    QPushButton[intent="danger"]{color:#ef4444;border:1px solid rgba(239,68,68,.55);background:rgba(239,68,68,.10)}
    QPushButton[stockAction="save"]:enabled{color:#f59e0b;border:1px solid rgba(245,158,11,.5);background:rgba(245,158,11,.12)}
    QPushButton[stockAction="save"]:hover{color:#f59e0b;border:1px solid rgba(245,158,11,.7);background:rgba(245,158,11,.18)}
    QPushButton[role="nav"]{background:transparent;border:1px solid transparent;border-radius:14px;padding:5px 12px;min-height:24px;text-align:left;color:#8b98a5;font-size:14px;font-weight:600}
    QPushButton[role="nav"]:hover{color:#e6edf3;background:#111820}
    QPushButton[role="nav"][active="true"]{color:#e6edf3;background:#111820;border:1px solid #1e2937;border-left:3px solid #2fa572;font-weight:700}
    QPushButton[role="nav"]:disabled{color:#525d6a}
    QPushButton[role="nav"][secondary="true"]{font-size:13px;padding:3px 12px}
    QFrame[role="divider"]{background:#1e2937;border:none}
    QPushButton[role="lang"]{background:transparent;border:1px solid #1e2937;color:#8b98a5;padding:5px 11px;border-radius:0}
    QPushButton[role="lang"]:hover{color:#e6edf3}
    QPushButton[role="lang"][active="true"]{background:rgba(47,165,114,.15);color:#2fa572}
    QPushButton[role="prefs"]{background:#111820;border:1px solid #1e2937;border-radius:8px;color:#e6edf3;padding:5px 12px}
    QPushButton[role="prefs"]:hover{border:1px solid #2fa572}
    QComboBox{background:#111820;border:1px solid #1e2937;border-radius:8px;padding:7px 10px;color:#e6edf3;min-height:22px}
    QComboBox::drop-down{background:transparent;border:0;width:26px}
    QComboBox::down-arrow{width:0;height:0}
    QComboBox QAbstractItemView{background:#0b0f14;border:1px solid #1e2937;border-radius:8px;padding:6px;selection-background-color:rgba(47,165,114,.22);selection-color:#e6edf3;outline:0}
    QComboBox QAbstractItemView::item{min-height:28px;padding:5px 10px;border-radius:6px;background:#0b0f14;color:#e6edf3}
    QComboBox QAbstractItemView::item:selected{background:rgba(47,165,114,.22);color:#e6edf3}
    QLineEdit{background:#111820;border:1px solid #1e2937;border-radius:8px;padding:7px 10px;color:#e6edf3;font-weight:500}
    QLineEdit:focus{border:1px solid #2fa572;background:#0f141b}
    QCheckBox{spacing:8px;color:#d6dde4}
    QCheckBox::indicator{width:18px;height:18px;border-radius:5px;border:1px solid #3a4654;background:#111820}
    QCheckBox::indicator:checked{background:#2fa572;border:1px solid #2fa572}
    QScrollArea,QTextEdit{background:#0b0f14;border:1px solid #1e2937;border-radius:8px;padding:8px}
    QScrollArea > QWidget#qt_scrollarea_viewport{background:#0b0f14}
    QScrollArea#RailScroll{background:transparent;border:none;padding:0;border-radius:0}
    QScrollArea#RailScroll > QWidget#qt_scrollarea_viewport{background:transparent}
    QWidget#RailContent{background:transparent}
    QTextEdit[role="mini"]{font-family:Consolas;font-size:12px;color:#f0f6fc;background:#0a0e13}
    QScrollBar:vertical{background:transparent;width:10px;margin:2px}
    QScrollBar::handle:vertical{background:#3a4654;border-radius:5px;min-height:42px}
    QScrollBar::handle:vertical:hover{background:#2fa572}
    QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;background:transparent}
    QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:transparent}
    QProgressBar{min-height:8px;border:1px solid #1e2937;border-radius:6px;background:#111820;text-align:center;color:#8b98a5;font-size:11px}
    QProgressBar::chunk{background:#2fa572;border-radius:6px}
    QTableWidget,QTableView{background:#0b0f14;border:1px solid #1e2937;border-radius:8px;gridline-color:#1e2937;color:#e6edf3;selection-background-color:rgba(47,165,114,.22);selection-color:#e6edf3;outline:0}
    QTableWidget::item,QTableView::item{padding:4px 8px;color:#e6edf3}
    QHeaderView::section{background:#111820;color:#8b98a5;border:none;border-right:1px solid #1e2937;border-bottom:1px solid #1e2937;padding:6px 10px;font-weight:700;font-size:12px}
    QTableCornerButton::section{background:#111820;border:none}
    """
    normalized = str(theme or "dark").lower().replace("_", "-").strip()
    if normalized == "light":
        return base + """
    QMainWindow{background:#eef1f5}
    QWidget{color:#141b24}
    QWidget#StockAdvisorControls{background:#ffffff}
    #Root{background:rgba(20,122,82,.09)}
    QFrame[role="panel"]{background:#ffffff;border:1px solid #c3ccd6;border-radius:18px}
    QFrame[role="row"]{background:#eef1f5;border:1px solid #c3ccd6}
    QFrame[role="row"][active="true"]{border:1px solid #147a52;background:rgba(20,122,82,.06)}
    QFrame[role="hint"]{background:rgba(146,97,10,.08);border:1px solid rgba(146,97,10,.35);border-radius:12px}
    QFrame[role="signal"]{background:#ffffff;border:1px solid #c3ccd6}
    QFrame[role="signal"][state="running"]{border:1px solid #147a52;background:rgba(20,122,82,.06)}
    QFrame[role="signal"][state="degraded"]{border:1px solid #92610a;background:rgba(146,97,10,.07)}
    QFrame[role="stat"]{background:#eef1f5;border:1px solid #c3ccd6}
    QLabel[role="tiny"]{color:#4b5a6b}
    QLabel[role="muted"]{color:#4b5a6b}
    QLabel[role="stockStatus"]{color:#141b24}
    QLabel[role="progress"]{color:#147a52}
    QLabel[role="section"]{color:#141b24}
    QLabel[role="title"]{color:#141b24}
    QLabel[role="value"]{color:#141b24}
    QLabel[role="status"]{background:rgba(20,122,82,.12);color:#147a52}
    QLabel[role="status"][mode="LIVE"]{background:rgba(20,122,82,.14);color:#147a52;border:1px solid rgba(20,122,82,.45)}
    QLabel[role="status"][mode="DEMO"]{background:rgba(146,97,10,.12);color:#92610a;border:1px solid rgba(146,97,10,.45)}
    QLabel[role="status"][mode="UNKNOWN"]{background:rgba(75,90,107,.12);color:#4b5a6b;border:1px solid rgba(75,90,107,.35)}
    QLabel[role="status"][mode="READY"]{background:rgba(20,122,82,.12);color:#147a52;border:1px solid rgba(20,122,82,.40)}
    QLabel[role="status"][mode="DEGRADED"]{background:rgba(146,97,10,.12);color:#92610a;border:1px solid rgba(146,97,10,.45)}
    QLabel[role="status"][mode="UNAVAILABLE"]{background:rgba(194,47,47,.10);color:#c22f2f;border:1px solid rgba(194,47,47,.40)}
    QLabel[role="status"][mode="STALE"]{background:rgba(146,97,10,.10);color:#92610a;border:1px solid rgba(146,97,10,.35)}
    QToolTip{background:#ffffff;color:#141b24;border:1px solid #c3ccd6;padding:8px 10px;border-radius:8px;font-size:12px}
    QLabel[accent="green"]{color:#147a52}QLabel[accent="amber"]{color:#92610a}QLabel[accent="red"]{color:#c22f2f}QLabel[accent="theme"]{color:#147a52}
    QPushButton{background:#ffffff;border:1px solid #c3ccd6;color:#141b24}
    QPushButton:hover{border:1px solid #147a52}
    QPushButton:disabled{color:#98a2ac;border:1px solid #c3ccd6;background:#f4f6f8}
    QPushButton[primary="true"]:enabled{background:rgba(20,122,82,.12);border:1px solid #147a52;color:#147a52}
    QPushButton[active="true"]{background:rgba(20,122,82,.12);border:1px solid #147a52;color:#147a52}
    QPushButton[intent="positive"]{color:#147a52;border:1px solid rgba(20,122,82,.55);background:rgba(20,122,82,.12)}
    QPushButton[intent="danger"]{color:#c22f2f;border:1px solid rgba(194,47,47,.55);background:rgba(194,47,47,.10)}
    QPushButton[stockAction="save"]:enabled{color:#92610a;border:1px solid rgba(146,97,10,.5);background:rgba(146,97,10,.12)}
    QPushButton[role="nav"]{color:#4b5a6b}
    QPushButton[role="nav"]:hover{color:#141b24;background:#eef1f5}
    QPushButton[role="nav"][active="true"]{color:#141b24;background:#eef1f5;border:1px solid #c3ccd6;border-left:3px solid #147a52}
    QPushButton[role="nav"]:disabled{color:#98a2ac}
    QFrame[role="divider"]{background:#c3ccd6;border:none}
    QPushButton[role="lang"]{border:1px solid #c3ccd6;color:#4b5a6b}
    QPushButton[role="lang"]:hover{color:#141b24}
    QPushButton[role="lang"][active="true"]{background:rgba(20,122,82,.12);color:#147a52}
    QPushButton[role="prefs"]{background:#ffffff;border:1px solid #c3ccd6;color:#141b24}
    QPushButton[role="prefs"]:hover{border:1px solid #147a52}
    QComboBox{background:#ffffff;border:1px solid #c3ccd6;color:#141b24}
    QComboBox::drop-down{background:transparent}
    QComboBox QAbstractItemView{background:#ffffff;border:1px solid #c3ccd6;selection-background-color:rgba(20,122,82,.16);selection-color:#141b24}
    QComboBox QAbstractItemView::item{background:#ffffff;color:#141b24}
    QComboBox QAbstractItemView::item:selected{background:rgba(20,122,82,.16);color:#141b24}
    QLineEdit{background:#ffffff;border:1px solid #c3ccd6;color:#141b24}
    QLineEdit:focus{border:1px solid #147a52;background:#ffffff}
    QCheckBox{color:#141b24}QCheckBox::indicator{border:1px solid #9aa5b0;background:#ffffff}QCheckBox::indicator:checked{background:#147a52;border:1px solid #147a52}
    QScrollArea,QTextEdit{background:#eef1f5;border:1px solid #c3ccd6}
    QScrollArea > QWidget#qt_scrollarea_viewport{background:#eef1f5}
    QScrollBar::handle:vertical{background:#b9c2cc}QScrollBar::handle:vertical:hover{background:#147a52}
    QProgressBar{background:#ffffff;border:1px solid #c3ccd6;border-radius:6px;color:#141b24;font-size:11px}
    QProgressBar::chunk{background:#147a52;border-radius:6px}
    QTableWidget,QTableView{background:#ffffff;border:1px solid #c3ccd6;border-radius:8px;gridline-color:#c3ccd6;color:#141b24;selection-background-color:rgba(20,122,82,.16);selection-color:#141b24;outline:0}
    QTableWidget::item,QTableView::item{padding:4px 8px;color:#141b24}
    QHeaderView::section{background:#eef1f5;color:#4b5a6b;border:none;border-right:1px solid #c3ccd6;border-bottom:1px solid #c3ccd6;padding:6px 10px;font-weight:700;font-size:12px}
    QTableCornerButton::section{background:#eef1f5;border:none}
    """
    if normalized in {"deep-sea", "deep sea", "sea"}:
        return base + """
    QMainWindow{background:#031016}
    QWidget{color:#e8fbff}
    QWidget#StockAdvisorControls{background:#061219}
    #Root{background:qradialgradient(cx:.12,cy:.08,radius:1,fx:.12,fy:.08,stop:0 rgba(24,214,255,.12),stop:.46 #031016,stop:1 #031016)}
    QFrame[role="panel"]{background:#061219;border:1px solid #1b3b45}
    QFrame[role="row"]{background:#031016;border:1px solid #1b3b45}
    QFrame[role="row"][active="true"]{border:1px solid #18d6ff;background:rgba(24,214,255,.07)}
    QFrame[role="hint"]{background:rgba(244,183,64,.08);border:1px solid rgba(244,183,64,.35);border-radius:12px}
    QFrame[role="signal"]{background:#061219;border:1px solid #1b3b45}
    QFrame[role="signal"][state="running"]{border:1px solid #18d6ff;background:rgba(24,214,255,.07)}
    QFrame[role="signal"][state="degraded"]{border:1px solid #f4b740;background:rgba(244,183,64,.08)}
    QFrame[role="stat"]{background:#031016;border:1px solid #1b3b45}
    QLabel[role="tiny"]{color:#8caab2}
    QLabel[role="muted"]{color:#8caab2}
    QLabel[role="stockStatus"]{color:#e8fbff}
    QLabel[role="progress"]{color:#18d6ff}
    QLabel[role="section"]{color:#e8fbff}
    QLabel[role="title"]{color:#e8fbff}
    QLabel[role="value"]{color:#e8fbff}
    QLabel[role="status"]{background:rgba(24,214,255,.12);color:#18d6ff}
    QLabel[accent="green"]{color:#18d6ff}QLabel[accent="amber"]{color:#f4b740}QLabel[accent="red"]{color:#ff6670}QLabel[accent="theme"]{color:#18d6ff}
    QPushButton{background:#061219;border:1px solid #1b3b45;color:#e8fbff}
    QPushButton:hover{border:1px solid #18d6ff}
    QPushButton:disabled{color:#48656e;border:1px solid #1b3b45;background:#0d1219}
    QPushButton[primary="true"]:enabled{background:rgba(24,214,255,.14);border:1px solid #18d6ff;color:#18d6ff}
    QPushButton[active="true"]{background:rgba(24,214,255,.14);border:1px solid #18d6ff;color:#18d6ff}
    QPushButton[intent="positive"]{color:#18d6ff;border:1px solid rgba(24,214,255,.55);background:rgba(24,214,255,.14)}
    QPushButton[intent="danger"]{color:#ff6670;border:1px solid rgba(255,102,112,.55);background:rgba(255,102,112,.12)}
    QPushButton[stockAction="save"]:enabled{color:#f4b740;border:1px solid rgba(244,183,64,.5);background:rgba(244,183,64,.14)}
    QPushButton[role="nav"]{color:#8caab2}
    QPushButton[role="nav"]:hover{color:#e8fbff;background:#09232c}
    QPushButton[role="nav"][active="true"]{color:#e8fbff;background:#09232c;border:1px solid #1b3b45;border-left:3px solid #18d6ff}
    QPushButton[role="nav"]:disabled{color:#45616b}
    QFrame[role="divider"]{background:#1b3b45;border:none}
    QPushButton[role="lang"]{border:1px solid #1b3b45;color:#8caab2}
    QPushButton[role="lang"]:hover{color:#e8fbff}
    QPushButton[role="lang"][active="true"]{background:rgba(24,214,255,.14);color:#18d6ff}
    QPushButton[role="prefs"]{background:#09232c;border:1px solid #1b3b45;color:#e8fbff}
    QPushButton[role="prefs"]:hover{border:1px solid #18d6ff}
    QComboBox{background:#061219;border:1px solid #1b3b45;color:#e8fbff}
    QComboBox::drop-down{background:transparent}
    QComboBox QAbstractItemView{background:#031016;border:1px solid #1b3b45;selection-background-color:rgba(24,214,255,.18);selection-color:#e8fbff}
    QComboBox QAbstractItemView::item{background:#031016;color:#e8fbff}
    QComboBox QAbstractItemView::item:selected{background:rgba(24,214,255,.18);color:#e8fbff}
    QLineEdit{background:#061219;border:1px solid #1b3b45;color:#e8fbff}
    QLineEdit:focus{border:1px solid #18d6ff;background:#061a22}
    QCheckBox{color:#e8fbff}QCheckBox::indicator{border:1px solid #2a5864;background:#061219}QCheckBox::indicator:checked{background:#18d6ff;border:1px solid #18d6ff}
    QScrollArea,QTextEdit{background:#031016;border:1px solid #1b3b45}
    QScrollArea > QWidget#qt_scrollarea_viewport{background:#031016}
    QScrollBar::handle:vertical{background:#1d5d6e}QScrollBar::handle:vertical:hover{background:#18d6ff}
    QProgressBar{border:1px solid #1b3b45;background:#061219;color:#8caab2}
    QProgressBar::chunk{background:#18d6ff}
    QTableWidget,QTableView{background:#031016;border:1px solid #1b3b45;border-radius:8px;gridline-color:#1b3b45;color:#e8fbff;selection-background-color:rgba(24,214,255,.18);selection-color:#e8fbff;outline:0}
    QTableWidget::item,QTableView::item{padding:4px 8px;color:#e8fbff}
    QHeaderView::section{background:#061219;color:#8caab2;border:none;border-right:1px solid #1b3b45;border-bottom:1px solid #1b3b45;padding:6px 10px;font-weight:700;font-size:12px}
    QTableCornerButton::section{background:#061219;border:none}
    """
    if normalized in {"contrast", "high-contrast", "high contrast"}:
        return base + """
    QMainWindow{background:#000000}
    QWidget{color:#ffffff}
    QWidget#StockAdvisorControls{background:#0d0d0d}
    #Root{background:#000000}
    QFrame[role="panel"]{background:#0d0d0d;border:1px solid #4d4d4d}
    QFrame[role="row"]{background:#000000;border:1px solid #4d4d4d}
    QFrame[role="row"][active="true"]{border:1px solid #00e676;background:rgba(0,230,118,.10)}
    QFrame[role="hint"]{background:rgba(255,171,0,.08);border:1px solid rgba(255,171,0,.4);border-radius:12px}
    QFrame[role="signal"]{background:#0d0d0d;border:1px solid #4d4d4d}
    QFrame[role="signal"][state="running"]{border:1px solid #00e676;background:rgba(0,230,118,.10)}
    QFrame[role="signal"][state="degraded"]{border:1px solid #ffab00;background:rgba(255,171,0,.08)}
    QFrame[role="stat"]{background:#000000;border:1px solid #4d4d4d}
    QLabel[role="tiny"]{color:#b3b3b3}
    QLabel[role="muted"]{color:#b3b3b3}
    QLabel[role="stockStatus"]{color:#ffffff}
    QLabel[role="progress"]{color:#00e676}
    QLabel[role="section"]{color:#ffffff}
    QLabel[role="title"]{color:#ffffff}
    QLabel[role="value"]{color:#ffffff}
    QLabel[role="status"]{background:rgba(0,230,118,.14);color:#00e676}
    QLabel[accent="green"]{color:#00e676}QLabel[accent="amber"]{color:#ffab00}QLabel[accent="red"]{color:#ff5252}QLabel[accent="theme"]{color:#00e676}
    QPushButton{background:#0d0d0d;border:1px solid #4d4d4d;color:#ffffff}
    QPushButton:hover{border:1px solid #00e676}
    QPushButton:disabled{color:#6b6b6b;border:1px solid #4d4d4d;background:#080808}
    QPushButton[primary="true"]:enabled{background:rgba(0,230,118,.15);border:1px solid #00e676;color:#00e676}
    QPushButton[active="true"]{background:rgba(0,230,118,.15);border:1px solid #00e676;color:#00e676}
    QPushButton[intent="positive"]{color:#00e676;border:1px solid rgba(0,230,118,.55);background:rgba(0,230,118,.15)}
    QPushButton[intent="danger"]{color:#ff5252;border:1px solid rgba(255,82,82,.55);background:rgba(255,82,82,.12)}
    QPushButton[stockAction="save"]:enabled{color:#ffab00;border:1px solid rgba(255,171,0,.5);background:rgba(255,171,0,.15)}
    QPushButton[role="nav"]{color:#b3b3b3}
    QPushButton[role="nav"]:hover{color:#ffffff;background:#0d0d0d}
    QPushButton[role="nav"][active="true"]{color:#ffffff;background:#0d0d0d;border:1px solid #4d4d4d;border-left:3px solid #00e676}
    QPushButton[role="nav"]:disabled{color:#5c5c5c}
    QFrame[role="divider"]{background:#4d4d4d;border:none}
    QPushButton[role="lang"]{border:1px solid #4d4d4d;color:#b3b3b3}
    QPushButton[role="lang"]:hover{color:#ffffff}
    QPushButton[role="lang"][active="true"]{background:rgba(0,230,118,.15);color:#00e676}
    QPushButton[role="prefs"]{background:#0d0d0d;border:1px solid #4d4d4d;color:#ffffff}
    QPushButton[role="prefs"]:hover{border:1px solid #00e676}
    QComboBox{background:#0d0d0d;border:1px solid #4d4d4d;color:#ffffff}
    QComboBox::drop-down{background:transparent}
    QComboBox QAbstractItemView{background:#000000;border:1px solid #4d4d4d;selection-background-color:rgba(0,230,118,.2);selection-color:#ffffff}
    QComboBox QAbstractItemView::item{background:#000000;color:#ffffff}
    QComboBox QAbstractItemView::item:selected{background:rgba(0,230,118,.2);color:#ffffff}
    QLineEdit{background:#0d0d0d;border:1px solid #4d4d4d;color:#ffffff}
    QLineEdit:focus{border:1px solid #00e676;background:#0d0d0d}
    QCheckBox{color:#ffffff}QCheckBox::indicator{border:1px solid #6e6e6e;background:#0d0d0d}QCheckBox::indicator:checked{background:#00e676;border:1px solid #00e676}
    QScrollArea,QTextEdit{background:#000000;border:1px solid #4d4d4d}
    QScrollArea > QWidget#qt_scrollarea_viewport{background:#000000}
    QScrollBar::handle:vertical{background:#5a5a5a}QScrollBar::handle:vertical:hover{background:#00e676}
    QProgressBar{border:1px solid #4d4d4d;background:#0d0d0d;color:#b3b3b3}
    QProgressBar::chunk{background:#00e676}
    QTableWidget,QTableView{background:#000000;border:1px solid #4d4d4d;border-radius:8px;gridline-color:#4d4d4d;color:#ffffff;selection-background-color:rgba(0,230,118,.2);selection-color:#ffffff;outline:0}
    QTableWidget::item,QTableView::item{padding:4px 8px;color:#ffffff}
    QHeaderView::section{background:#0d0d0d;color:#b3b3b3;border:none;border-right:1px solid #4d4d4d;border-bottom:1px solid #4d4d4d;padding:6px 10px;font-weight:700;font-size:12px}
    QTableCornerButton::section{background:#0d0d0d;border:none}
    """
    return base


def panel() -> Any:
    """Create a styled panel frame."""
    frame = QT.QFrame()
    frame.setProperty("role", "panel")
    return frame


def label(text: str, *, role: str = "", accent: str = "") -> Any:
    """Create a label with optional style role."""
    item = QT.QLabel(native_text(text))
    if role:
        item.setProperty("role", role)
    if accent:
        item.setProperty("accent", accent)
    return item


def divider() -> Any:
    """A 1px horizontal divider line for sidebar section groups."""
    line = QT.QFrame()
    line.setProperty("role", "divider")
    line.setFixedHeight(1)
    return line


def mask_secret(value: Any) -> str:
    """Return a safe display value for token-like fields."""
    text = str(value or "").strip()
    if not text:
        return "—"
    if len(text) <= 8:
        return "••••"
    return f"{text[:4]}••••{text[-4:]}"


def yes_no(value: Any) -> str:
    """Format truthy config values for compact profile cards."""
    return "ON" if bool(value) else "OFF"


def safe_profile_filename(profile_name: str) -> str:
    """Match CopyTradeManager's per-profile JSON file naming."""
    raw = (profile_name or "default").strip() or "default"
    safe = "".join(c for c in raw if c.isalpha() or c.isdigit() or c in (" ", "-", "_"))
    return safe.strip() or "default"


def order_type_name(value: Any) -> str:
    """Return a compact order type label."""
    text = str(value).upper()
    if text in {"0", "BUY"}:
        return "BUY"
    if text in {"1", "SELL"}:
        return "SELL"
    return text or "—"


def button(text: str, *, primary: bool = False) -> Any:
    """Create a shell button."""
    item = QT.QPushButton(native_text(text))
    item.setCursor(QT.Qt.CursorShape.PointingHandCursor)
    item.setProperty("primary", "true" if primary else "false")
    return item


QT: SimpleNamespace


def advisory_rows_from_payload(payload: object) -> list[tuple[str, str, float, object, int]]:
    """Extract (symbol, direction, score, latest_close, rank) tuples from a
    stock_recommendation.json payload, sorted by rank (rank 0 last)."""
    if not isinstance(payload, dict) or not payload:
        return []
    recs = payload.get("recommendations")
    if not isinstance(recs, list):
        return []
    rows: list[tuple[str, str, float, object, int]] = []
    for r in recs:
        if not isinstance(r, dict):
            continue
        symbol = str(r.get("symbol", ""))
        direction = str(r.get("direction", ""))
        if direction not in ("BUY", "SELL") or not symbol:
            continue
        score = float(r.get("score", 0.0))
        latest_close = r.get("latest_close")
        rank = int(r.get("rank", 0))
        rows.append((symbol, direction, score, latest_close, rank))
    rows.sort(key=lambda row: (row[4] if row[4] > 0 else 10**9, row[0]))
    return rows


def load_stock_rows(db_path: Path | None = None, limit: int = 1000) -> list[dict]:
    """Latest EOD row per symbol from data/market.db (read-only).

    Returns [] if the db is missing.
    Columns: date, symbol, exchange, open, high, low, close, volume, value,
    foreign_buy_value, foreign_sell_value.
    """
    try:
        import sqlite3
        if db_path is None:
            db_path = ROOT / "data" / "market.db"
        if not db_path.is_file():
            return []
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT date, symbol, exchange, open, high, low, close,
                          volume, value, foreign_buy_value, foreign_sell_value
                   FROM eod_prices
                   WHERE date = (SELECT MAX(date) FROM eod_prices)
                   ORDER BY symbol
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        finally:
            conn.close()
        return [
            {
                "date": r["date"], "symbol": r["symbol"], "exchange": r["exchange"],
                "open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"],
                "volume": r["volume"], "value": r["value"],
                "foreign_buy_value": r["foreign_buy_value"],
                "foreign_sell_value": r["foreign_sell_value"],
            }
            for r in rows
        ]
    except Exception:
        return []


class NativeShell:
    """Small wrapper around the Qt main window.
    
    Performance optimizations:
    - Debounced live updates to reduce CPU usage
    - Conditional UI refreshes only when data changes
    - Efficient style updates via Qt properties
    - Cached QSS stylesheet loading
    """

    def __init__(self, ready_callback=None):
        self.profiles = read_json(PROFILE_FILE, {})
        self.settings = read_json(SETTINGS_FILE, {})
        set_native_language(str(self.settings.get("lang", "EN")))
        self.selected = next(iter(self.profiles), "")
        self.current_tab = "Dashboard"
        self.nav_buttons: dict[str, Any] = {}
        self.monitor_processes: dict[str, Any] = {}
        self.signal_processes: dict[str, Any] = {}
        self.signal_cards: dict[str, dict[str, Any]] = {}
        self.signal_summary = None
        self.signal_supervisor = None
        self._signal_supervisor_logs: dict[str, int] = {}
        self.stock_process = None
        self.stock_pending_launch = None
        self.stock_process_log: list[str] = []
        self._last_auto_eod_date: str | None = None
        self.stock_result_table = None
        self.stock_table = None
        self.stock_count = None
        self.stock_search = None
        self._stock_search_timer = None
        self.stock_run_btn = None
        self.stock_status = None
        self._stock_rows: list[dict] = []
        self.profile_cards_layout = None
        self.profile_detail = None
        self.profile_editor_title = None
        self.profile_editor_status = None
        self.profile_editor_fields: dict[str, Any] = {}
        self.profile_editor_checks: dict[str, Any] = {}
        self.profile_editor_dirty = False
        self.profile_editor_profile = ""
        self.pending_delete_profile = ""
        self.copy_detail = None
        self.copy_guardrails_layout = None
        self.pending_summary = None
        self.pending_items_layout = None
        self.pending_action_status = None
        self.pending_delete_key = ""
        self._last_pending_signature = None
        self._last_stock_advisor_signature = None
        self._table_detail_payloads: dict[int, list[dict[str, Any]]] = {}
        self._table_detail_titles: dict[int, str] = {}
        self.diag_summary = None
        self.diag_log = None
        self.diag_filter = None
        self.diag_level = None
        self.diag_status = None
        self.last_visible_log_text = ""
        self.settings_lang_combo = None
        self.settings_theme_combo = None
        self.settings_status = None
        self.settings_about = None
        self.shortcuts: list[Any] = []
        self.live_status = None
        self.hero_status = None
        self.rail_fleet = None
        self.rail_lang_en = None
        self.rail_lang_vn = None
        self.rail_theme_btn = None
        self.rail_profile_status = None
        self.rail_profile_toggle = None
        self.rail_scroll = None
        self.live_timer = None
        self.last_running_signature: tuple[str, ...] = ()
        self.last_diagnostics_report = ""
        self.ready_callback = ready_callback
        self.starting_profiles: set[str] = set()
        self.startup_phase: dict[str, str] = {}
        self.startup_error: dict[str, str] = {}
        # Per-Start operation identity: stale bg callbacks must not mutate state / launch workers.
        self._startup_ops: dict[str, int] = {}
        self._startup_op_seq: int = 0
        self._is_shut_down: bool = False
        self.analysis_account_summary = None
        self.analysis_account_stats_host = None
        self.analysis_account_stats_layout = None
        self.analysis_account_stats: dict[str, Any] = {}
        self.analysis_positions_status = None
        self.analysis_positions_table = None
        self.analysis_performance_summary = None
        self.analysis_equity_table = None
        self.analysis_equity_chart = None
        self.analysis_equity_chart_view = None
        self.analysis_equity_status = None
        self.analysis_kpi_primary_host = None
        self.analysis_kpi_primary_layout = None
        self.analysis_kpi_secondary_host = None
        self.analysis_kpi_secondary_layout = None
        self.analysis_kpi_cards: dict[str, Any] = {}
        self._analysis_chart_types: dict[str, Any] = {}
        self.analysis_history_summary_host = None
        self.analysis_history_summary_layout = None
        self.analysis_history_summary: dict[str, Any] = {}
        self.analysis_history_symbol_filter = None
        self.analysis_history_type_filter = None
        self.analysis_history_search = None
        self.analysis_history_deals: list[dict] = []
        self.analysis_checkpoint_table = None
        self.analysis_news_summary_host = None
        self.analysis_news_summary_layout = None
        self.analysis_news_summary: dict[str, Any] = {}
        self.analysis_news_currency_filter = None
        self.analysis_news_impact_filter = None
        self.analysis_news_items: list[dict] = []
        self.analysis_news_table = None
        self.analysis_news_status = None

        # Performance: Debouncing and throttling state
        self._ui_update_pending = False
        self._last_refresh_time = 0.0
        self._refresh_cooldown = 0.1  # Minimum seconds between full UI refreshes
        
        self.window = QT.QMainWindow()
        apply_window_icon(self.window)
        self.window.setWindowTitle("OAK Manager · Native Qt")
        self.window.setMinimumSize(1040, 680)
        self.window.resize(1240, 780)
        self._build()
        self._init_signal_supervisor()
        self._install_shortcuts()
        self.apply_theme()
        self.refresh()
        self._start_live_timer()
        QT.QTimer.singleShot(0, self._ready)

    def _init_signal_supervisor(self) -> None:
        """Use the shared supervisor lifecycle/recovery engine for NativeQt."""
        from services.signal_process_supervisor import SignalProcessSupervisor

        defs = list(get_visible_signal_defs())
        self._signal_supervisor_infos = {
            key: {"name": name, "proc": None, "logs": []}
            for key, name, _color in defs
        }
        self.signal_supervisor = SignalProcessSupervisor(
            defs,
            log_callback=self._on_signal_supervisor_log,
            # Context-aware singleShot: plain singleShot(0, cb) from a worker thread never fires
            # because the timer is created in the caller's (non-GUI) thread. Use a QObject that
            # lives on the GUI thread (self.window) as receiver context to marshal the callback.
            ui_after=lambda callback: QT.QTimer.singleShot(0, self.window, callback),
            state_callback=self._on_signal_supervisor_state,
            output_callback=self._on_signal_supervisor_output,
        )
        self.signal_supervisor.register_signals(self._signal_supervisor_infos)

    def _on_signal_supervisor_log(self, message: str) -> None:
        # Context-aware singleShot: plain singleShot(0, cb) from a worker thread never fires
        # because the timer is created in the caller's (non-GUI) thread. Use a QObject that
        # lives on the GUI thread (self.window) as receiver context to marshal the callback.
        QT.QTimer.singleShot(0, self.window, lambda m=message: self._append_console_line(m))

    def _on_signal_supervisor_output(self, key: str, line: str) -> None:
        # Context-aware singleShot: plain singleShot(0, cb) from a worker thread never fires
        # because the timer is created in the caller's (non-GUI) thread. Use a QObject that
        # lives on the GUI thread (self.window) as receiver context to marshal the callback.
        QT.QTimer.singleShot(0, self.window, lambda k=key, text=line: self._append_signal_log(k, text))

    def _on_signal_supervisor_state(
        self, key: str, running: bool, pid: int | None, status: str | None, conflict_pid: int | None
    ) -> None:
        # Context-aware singleShot: plain singleShot(0, cb) from a worker thread never fires
        # because the timer is created in the caller's (non-GUI) thread. Use a QObject that
        # lives on the GUI thread (self.window) as receiver context to marshal the callback.
        QT.QTimer.singleShot(
            0,
            self.window,
            lambda: self._apply_signal_supervisor_state(key, running, pid, status, conflict_pid),
        )

    def _apply_signal_supervisor_state(
        self, key: str, running: bool, pid: int | None, status: str | None, conflict_pid: int | None
    ) -> None:
        card = self.signal_cards.get(key)
        if not card:
            return
        card["status"].setText(native_text(status or ("Running" if running else "Stopped")))
        card["pid"].setText(
            f"PID: {pid}" if running and pid else
            f"PID: {conflict_pid} (conflict)" if conflict_pid else "PID: ---"
        )
        card["start"].setEnabled(not running)
        card["stop"].setEnabled(running)
        degraded = status in {"Conflict", "Restarting", "Degraded", "Blocked"}
        card["frame"].setProperty("state", "running" if running else "degraded" if degraded else "stopped")
        card["status"].setProperty("accent", "green" if running else "amber" if degraded else "")
        card["dot"].setProperty("accent", "green" if running else "amber" if degraded else "red")
        for widget_name in ("frame", "dot", "status", "start", "stop", "pid"):
            widget = card[widget_name]
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self._refresh_signal_summary()

    def _bind_signal_supervisor_ui(self) -> None:
        """Rebind the supervisor registry after a NativeQt UI rebuild."""
        if self.signal_supervisor is not None:
            self.signal_supervisor.register_signals(self._signal_supervisor_infos)

    def _build(self) -> None:
        root = QT.QWidget()
        root.setObjectName("Root")
        layout = QT.QHBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(18)
        layout.addWidget(self._rail(), 0)
        layout.addWidget(self._main(), 1)
        self.window.setCentralWidget(root)

    def _rail(self) -> Any:
        frame = panel()
        frame.setFixedWidth(330)
        self.rail_scroll = QT.QScrollArea()
        self.rail_scroll.setObjectName("RailScroll")
        self.rail_scroll.setWidgetResizable(True)
        self.rail_scroll.setFrameShape(QT.QFrame.Shape.NoFrame)
        content = QT.QWidget()
        content.setObjectName("RailContent")
        layout = QT.QVBoxLayout(content)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)
        # Brand row
        brand_row = QT.QHBoxLayout()
        brand_icon = label("⚡", accent="green")
        brand_icon.setContentsMargins(0, 0, 0, 0)
        brand_row.addWidget(brand_icon)
        brand_oak = label("OAK", role="section")
        brand_oak.setContentsMargins(0, 0, 0, 0)
        brand_row.addWidget(brand_oak)
        brand_mgr = label("Manager", role="section")
        brand_mgr.setContentsMargins(0, 0, 0, 0)
        brand_row.addWidget(brand_mgr)
        brand_row.addStretch(1)
        layout.addLayout(brand_row)
        # Operations section header
        layout.addWidget(label("OPERATIONS", role="tiny"))
        # Nav icons from App.tsx
        nav_icons = {
            "Dashboard": "▦",
            "Signals": "⌁",
            "VN30 Advisor": "◌",
            "Profiles": "▣",
            "Copy": "♧",
            "Pending": "◷",
            "Diagnostics": "⌁",
            "Settings": "⚙",
        }
        for name in ("Dashboard", "Signals", "VN30 Advisor", "Profiles", "Copy", "Pending", "Diagnostics", "Settings"):
            nav = button(f"{nav_icons.get(name, '')}   {native_text(name)}")
            nav.setProperty("role", "nav")
            nav.clicked.connect(lambda _checked=False, tab=name: self.switch_tab(tab))
            self.nav_buttons[name] = nav
            layout.addWidget(nav)
        # Analysis section header
        layout.addSpacing(5)
        layout.addWidget(divider())
        layout.addSpacing(5)
        layout.addWidget(label("ANALYSIS", role="tiny"))
        analysis_nav = [
            ("◎", "Accounts"),
            ("↗", "Performance"),
            ("⧗", "History"),
            ("◈", "News"),
        ]
        for icon, name in analysis_nav:
            nav = button(f"{icon}   {native_text(name)}")
            nav.setProperty("role", "nav")
            nav.setProperty("secondary", "true")
            nav.clicked.connect(lambda _checked=False, tab=name: self.switch_tab(tab))
            self.nav_buttons[name] = nav
            layout.addWidget(nav)
        # Footer
        layout.addStretch(1)
        # Profile block
        layout.addSpacing(5)
        layout.addWidget(divider())
        layout.addSpacing(5)
        layout.addWidget(label("PROFILE", role="tiny"))
        self.profile_combo = QT.QComboBox()
        self.profile_combo.setMinimumHeight(36)
        self.profile_combo.currentTextChanged.connect(self._select_profile)
        layout.addWidget(self.profile_combo)
        # Profile control row: live status + start/stop toggle (Tauri parity)
        profile_ctl = QT.QHBoxLayout()
        profile_ctl.setSpacing(8)
        self.rail_profile_status = label("Stopped", role="muted")
        self.rail_profile_status.setProperty("accent", "muted")
        profile_ctl.addWidget(self.rail_profile_status)
        profile_ctl.addStretch(1)
        self.rail_profile_toggle = button("Start selected")
        self.rail_profile_toggle.setProperty("intent", "positive")
        self.rail_profile_toggle.clicked.connect(self._toggle_selected_profile)
        profile_ctl.addWidget(self.rail_profile_toggle)
        layout.addLayout(profile_ctl)
        # Live status block
        layout.addSpacing(5)
        layout.addWidget(divider())
        layout.addSpacing(5)
        layout.addWidget(label("LIVE STATUS", role="tiny"))
        self.live_status = label("Heartbeat ready", role="muted")
        layout.addWidget(self.live_status)
        # Prefs row: lang switch + theme toggle
        prefs_row = QT.QHBoxLayout()
        self.rail_lang_en = button("EN")
        self.rail_lang_en.setProperty("role", "lang")
        self.rail_lang_en.clicked.connect(lambda: self.set_rail_lang("EN"))
        self.rail_lang_vn = button("VN")
        self.rail_lang_vn.setProperty("role", "lang")
        self.rail_lang_vn.clicked.connect(lambda: self.set_rail_lang("VN"))
        current_lang = NATIVE_LANGUAGE
        self.rail_lang_en.setProperty("active", "true" if current_lang == "EN" else "false")
        self.rail_lang_vn.setProperty("active", "true" if current_lang == "VN" else "false")
        prefs_row.addWidget(self.rail_lang_en)
        prefs_row.addWidget(self.rail_lang_vn)
        self.rail_theme_btn = button("◐")
        self.rail_theme_btn.setProperty("role", "prefs")
        self.rail_theme_btn.setToolTip(f"Theme: {self.settings.get('theme', 'dark')}")
        self.rail_theme_btn.clicked.connect(self.cycle_rail_theme)
        prefs_row.addWidget(self.rail_theme_btn)
        self.classic_btn = button("Classic")
        self.classic_btn.setProperty("role", "prefs")
        self.classic_btn.setToolTip(native_text("Open classic UI"))
        self.classic_btn.clicked.connect(self.open_classic)
        prefs_row.addWidget(self.classic_btn)
        layout.addLayout(prefs_row)
        frame_layout = QT.QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.addWidget(self.rail_scroll)
        self.rail_scroll.setWidget(content)
        return frame

    def _main(self) -> Any:
        frame = QT.QWidget()
        layout = QT.QVBoxLayout(frame)
        layout.setSpacing(18)
        layout.addWidget(self._hero())
        self.stack = QT.QStackedWidget()
        self.tab_pages = {
            "Dashboard": self._dashboard_page(),
            "Signals": self._signals_page(),
            "VN30 Advisor": self._stock_advisor_page(),
            "Profiles": self._profiles_page(),
            "Copy": self._copy_page(),
            "Pending": self._pending_page(),
            "Diagnostics": self._diagnostics_page(),
            "Settings": self._settings_page(),
            "Accounts": self._accounts_page(),
            "Performance": self._performance_page(),
            "History": self._history_page(),
            "News": self._news_page(),
        }
        for page in self.tab_pages.values():
            self.stack.addWidget(page)
        layout.addWidget(self.stack, 1)
        return frame

    def _hero(self) -> Any:
        frame = panel()
        layout = QT.QGridLayout(frame)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(8)
        left = QT.QWidget()
        left_layout = QT.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        self.title = label("OAK Manager", role="title")
        self.subtitle = label("Native Qt/QSS shell · no WebEngine")
        left_layout.addWidget(label("TRADING WORKSTATION", role="tiny"))
        left_layout.addWidget(self.title)
        left_layout.addWidget(self.subtitle)
        self.hero_status = label("● Live", role="status")
        left_layout.addWidget(self.hero_status)
        left_layout.addStretch(1)
        layout.addWidget(left, 0, 0, 2, 1, QT.Qt.AlignmentFlag.AlignTop)
        self.stat_profiles = self._stat("Profiles", "0")
        self.stat_running = self._stat("Running", "0", "green")
        self.stat_lang = self._stat("Language", "VN")
        self.stat_theme = self._stat("Theme", "dark", "theme")
        for index, stat in enumerate((self.stat_profiles, self.stat_running, self.stat_lang, self.stat_theme)):
            layout.addWidget(stat["frame"], index // 2, 1 + index % 2)
        return frame

    def _stat(self, title: str, value: str, accent: str = "") -> dict[str, Any]:
        frame = QT.QFrame()
        frame.setProperty("role", "stat")
        layout = QT.QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        value_label = label(value, role="value", accent=accent)
        layout.addWidget(label(title.upper(), role="tiny"))
        layout.addWidget(value_label)
        return {"frame": frame, "value": value_label}

    def _dashboard_page(self) -> Any:
        """Trading workstation dashboard — account health, risk, equity, positions, pending, activity."""
        content = QT.QWidget()
        root = QT.QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # --- Account / System Health (shared status-strip density) ---
        self.dash_mode_badge = label("UNKNOWN", role="status")
        self.dash_mode_badge.setProperty("mode", "UNKNOWN")
        self.dash_account_label = label("—", role="section")
        self.dash_mt5_label = label("MT5 —", role="muted")
        self.dash_fresh_label = label("Updated —", role="muted")
        self.dash_exec_label = label("Execution —", role="muted")
        root.addWidget(
            self._status_strip(
                self.dash_mode_badge,
                self.dash_account_label,
                "|",
                self.dash_mt5_label,
                self.dash_exec_label,
                self.dash_fresh_label,
            )
        )

        # --- Risk metrics (higher visual weight) ---
        risk_host = QT.QWidget()
        risk_grid = QT.QGridLayout(risk_host)
        risk_grid.setContentsMargins(0, 0, 0, 0)
        risk_grid.setHorizontalSpacing(10)
        risk_grid.setVerticalSpacing(10)
        self.dash_risk_stats: dict[str, Any] = {}
        risk_keys = [
            ("equity", "Equity", "green"),
            ("balance", "Balance", ""),
            ("floating", "Floating P/L", ""),
            ("cur_dd", "Current DD", "amber"),
            ("max_dd", "Max DD", "red"),
            ("margin", "Margin level", ""),
        ]
        for idx, (key, title, accent) in enumerate(risk_keys):
            frame, value_lbl = self._analysis_stat_card(title, "—", accent)
            self.dash_risk_stats[key] = {"frame": frame, "value": value_lbl}
            risk_grid.addWidget(frame, 0, idx)
        root.addWidget(self._section("RISK", risk_host))

        # --- Center: equity summary + positions / pending ---
        mid = QT.QHBoxLayout()
        mid.setSpacing(12)

        # Equity / chart summary panel
        equity_wrap = QT.QWidget()
        equity_lay = QT.QVBoxLayout(equity_wrap)
        equity_lay.setContentsMargins(0, 0, 0, 0)
        equity_lay.setSpacing(8)
        self.dash_equity_status = label("Equity curve uses closed-history samples. Live equity shown in Risk.", role="muted")
        self.dash_equity_status.setWordWrap(True)
        equity_lay.addWidget(self.dash_equity_status)
        self.dash_equity_table = self._analysis_table(
            ["Time", "Equity", "Balance", "Drawdown"], stretch=0
        )
        self.dash_equity_table.setMinimumHeight(160)
        self.dash_equity_table.setMaximumHeight(220)
        equity_lay.addWidget(self.dash_equity_table, 1)
        mid.addWidget(self._section("EQUITY / DRAWDOWN", equity_wrap), 2)

        # Open positions preview (compact, max ~6 rows visual)
        pos_wrap = QT.QWidget()
        pos_lay = QT.QVBoxLayout(pos_wrap)
        pos_lay.setContentsMargins(0, 0, 0, 0)
        pos_lay.setSpacing(6)
        pos_hdr = QT.QHBoxLayout()
        self.dash_pos_status = label("— open · —", role="muted")
        pos_hdr.addWidget(self.dash_pos_status)
        pos_hdr.addStretch(1)
        pos_more = button("Accounts")
        pos_more.setProperty("compact", "true")
        pos_more.clicked.connect(lambda: self.switch_tab("Accounts"))
        pos_hdr.addWidget(pos_more)
        pos_lay.addLayout(pos_hdr)
        self.dash_positions_table = self._analysis_table(
            ["Symbol", "Dir", "Vol", "P/L"], stretch=0
        )
        self.dash_positions_table.setMinimumHeight(160)
        self.dash_positions_table.setMaximumHeight(220)
        pos_lay.addWidget(self.dash_positions_table, 1)
        mid.addWidget(self._section("OPEN POSITIONS", pos_wrap), 1)

        root.addLayout(mid)

        # --- Bottom: pending + profiles + live console ---
        bottom = QT.QHBoxLayout()
        bottom.setSpacing(12)

        pending_wrap = QT.QWidget()
        pending_lay = QT.QVBoxLayout(pending_wrap)
        pending_lay.setContentsMargins(0, 0, 0, 0)
        pending_lay.setSpacing(6)
        pend_hdr = QT.QHBoxLayout()
        self.dash_pending_status = label("— pending", role="muted")
        pend_hdr.addWidget(self.dash_pending_status)
        pend_hdr.addStretch(1)
        pend_more = button("Pending")
        pend_more.setProperty("compact", "true")
        pend_more.clicked.connect(lambda: self.switch_tab("Pending"))
        pend_hdr.addWidget(pend_more)
        pending_lay.addLayout(pend_hdr)
        self.dash_pending_table = self._analysis_table(
            ["Symbol", "Type", "Status"], stretch=0
        )
        self.dash_pending_table.setMinimumHeight(120)
        self.dash_pending_table.setMaximumHeight(160)
        pending_lay.addWidget(self.dash_pending_table, 1)
        bottom.addWidget(self._section("PENDING ORDERS", pending_wrap), 1)

        # Profiles list (kept for existing _refresh_profiles consumers)
        self.profile_rows = QT.QWidget()
        self.profile_rows.setObjectName("ProfileRows")
        self.profile_rows.setStyleSheet("background: transparent;")
        self.profile_rows_layout = QT.QVBoxLayout(self.profile_rows)
        self.profile_rows_layout.setSpacing(8)
        self.profile_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.profile_scroll = QT.QScrollArea()
        self.profile_scroll.setWidgetResizable(True)
        self.profile_scroll.setMaximumHeight(160)
        self.profile_scroll.viewport().setStyleSheet("background: transparent;")
        self.profile_scroll.setWidget(self.profile_rows)
        bottom.addWidget(self._section("PROFILES", self.profile_scroll), 1)

        self.console = QT.QTextEdit()
        self.console.setReadOnly(True)
        self.console.document().setMaximumBlockCount(1200)
        self.console.setMaximumHeight(160)
        self.console.setProperty("role", "mini")
        bottom.addWidget(self._section("RECENT ACTIVITY", self.console), 1)

        root.addLayout(bottom)
        root.addStretch(0)
        return self._workstation_scroll(content)

    def _signals_page(self) -> Any:
        content = QT.QWidget()
        layout = QT.QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        visible_defs = get_visible_signal_defs()
        self.signal_summary = label(f"0/{len(visible_defs)} running", role="status")
        self.signal_fresh_label = label("Supervisor idle", role="muted")
        clear_logs = button("Clear logs")
        start_all = button("Start all", primary=True)
        stop_all = button("Stop all")
        clear_logs.setProperty("compact", "true")
        start_all.setProperty("compact", "true")
        stop_all.setProperty("compact", "true")
        clear_logs.clicked.connect(self.clear_signal_logs)
        start_all.clicked.connect(self.start_all_signals)
        stop_all.clicked.connect(self.stop_all_signals)
        layout.addWidget(
            self._status_strip(
                label("SIGNALS", role="section"),
                self.signal_summary,
                "|",
                self.signal_fresh_label,
                clear_logs,
                start_all,
                stop_all,
            )
        )

        grid_host = QT.QWidget()
        grid = QT.QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        positions = [(0, 0, 1), (0, 1, 1), (1, 0, 1), (1, 1, 1), (2, 0, 2)]
        for index, (key, name, color) in enumerate(visible_defs):
            row, col, span = positions[index] if index < len(positions) else (2 + index // 2, index % 2, 1)
            grid.addWidget(self._signal_card(key, name, color), row, col, 1, span)
        layout.addWidget(self._section("SIGNAL FEEDS", grid_host), 1)
        layout.addStretch(0)
        return self._workstation_scroll(content)

    def _stock_advisor_page(self) -> Any:
        content = QT.QWidget()
        root = QT.QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self.stock_mode_badge = label("LOCAL", role="status")
        self.stock_status = label("Local EOD Database · informational scanner", role="muted")
        self.stock_update_eod_btn = button("Update EOD Data (15:00+)")
        self.stock_update_eod_btn.setProperty("stockAction", "update_eod")
        self.stock_update_eod_btn.setProperty("compact", "true")
        self.stock_run_btn = button("Run Local EOD D1 Scanner", primary=True)
        self.stock_run_btn.setProperty("compact", "true")
        self.stock_update_eod_btn.clicked.connect(self.update_eod_data)
        self.stock_run_btn.clicked.connect(self.run_stock_advisor)
        root.addWidget(
            self._status_strip(
                label("VN30 ADVISOR", role="section"),
                self.stock_mode_badge,
                "|",
                self.stock_status,
                self.stock_update_eod_btn,
                self.stock_run_btn,
            )
        )

        body = QT.QHBoxLayout()
        body.setSpacing(12)

        # --- LEFT pane: Advisory Result ---
        left_widget = QT.QWidget()
        left_layout = QT.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # Advisory result table (5 columns)
        self.stock_result_table = QT.QTableWidget(0, 5)
        self.stock_result_table.setEditTriggers(QT.QTableWidget.EditTrigger.NoEditTriggers)
        self.stock_result_table.setSelectionMode(QT.QTableWidget.SelectionMode.NoSelection)
        self.stock_result_table.verticalHeader().setVisible(False)
        self.stock_result_table.setHorizontalHeaderLabels(
            [native_text("SYMBOL"), native_text("DIRECTION"), native_text("SCORE"),
             native_text("CLOSE"), native_text("RANK")]
        )
        left_layout.addWidget(self.stock_result_table, 1)

        # Progress bar
        self.stock_progress_bar = QT.QProgressBar()
        self.stock_progress_bar.setRange(0, 100)
        self.stock_progress_bar.setValue(0)
        self.stock_progress_bar.setTextVisible(False)
        self.stock_progress_bar.setFormat("Sẵn sàng (0%)")
        self.stock_progress_bar.setVisible(False)
        left_layout.addWidget(self.stock_progress_bar)
        self.stock_progress_label = label("Sẵn sàng (0%)", role="progress")
        self.stock_progress_label.setWordWrap(True)
        left_layout.addWidget(self.stock_progress_label)

        body.addWidget(self._section("ADVISORY RESULT", left_widget), 1)

        # --- RIGHT pane: Local EOD Stocks ---
        right_widget = QT.QWidget()
        right_layout = QT.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Search row
        search_row = QT.QHBoxLayout()
        self.stock_search = QT.QLineEdit()
        self.stock_search.setPlaceholderText(native_text("Filter symbols…"))
        self.stock_search.textChanged.connect(self._on_stock_search_changed)
        search_row.addWidget(self.stock_search, 1)
        self.stock_count = label("", role="muted")
        search_row.addWidget(self.stock_count)
        right_layout.addLayout(search_row)

        # Stocks table (7 columns)
        self.stock_table = QT.QTableWidget(0, 7)
        self.stock_table.setEditTriggers(QT.QTableWidget.EditTrigger.NoEditTriggers)
        self.stock_table.setSelectionMode(QT.QTableWidget.SelectionMode.NoSelection)
        self.stock_table.verticalHeader().setVisible(False)
        self.stock_table.setHorizontalHeaderLabels(
            [native_text("SYMBOL"), native_text("EXCHANGE"), native_text("OPEN"),
             native_text("HIGH"), native_text("LOW"), native_text("CLOSE"),
             native_text("VOLUME")]
        )
        self.stock_table.setMinimumHeight(220)
        right_layout.addWidget(self.stock_table, 1)

        body.addWidget(self._section("LOCAL EOD STOCKS", right_widget), 2)
        root.addLayout(body, 1)
        root.addStretch(0)

        # Load initial stock rows
        self._reload_stock_rows()
        return self._workstation_scroll(content)

    def _profiles_page(self) -> Any:
        content = QT.QWidget()
        root = QT.QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self.profiles_mode_badge = label("UNKNOWN", role="status")
        self.profiles_worker_label = label("Worker —", role="muted")
        self.profiles_mt5_label = label("MT5 —", role="muted")
        self.profiles_count_label = label("0 profiles", role="muted")
        root.addWidget(
            self._status_strip(
                label("PROFILES", role="section"),
                self.profiles_mode_badge,
                self.profiles_count_label,
                "|",
                self.profiles_worker_label,
                self.profiles_mt5_label,
            )
        )

        body = QT.QHBoxLayout()
        body.setSpacing(12)

        cards = QT.QWidget()
        cards.setStyleSheet("background: transparent;")
        self.profile_cards_layout = QT.QVBoxLayout(cards)
        self.profile_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.profile_cards_layout.setSpacing(10)

        scroll = QT.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QT.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setStyleSheet("background: transparent;")
        scroll.setWidget(cards)

        body.addWidget(self._section("PROFILE MAP", scroll), 1)
        body.addWidget(self._section("PROFILE EDITOR", self._profile_editor()), 1)
        root.addLayout(body, 1)
        root.addStretch(0)
        return self._workstation_scroll(content)

    def _profile_editor(self) -> Any:
        frame = QT.QWidget()
        layout = QT.QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.profile_editor_title = label("No profile selected", role="section")
        self.profile_editor_status = label("Changes are saved to profiles.json", role="muted")
        layout.addWidget(self.profile_editor_title)
        layout.addWidget(self.profile_editor_status)

        actions = QT.QHBoxLayout()
        for text, handler, primary in (
            ("Save", self.save_profile, True),
            ("Duplicate", self.duplicate_profile, False),
            ("Add new", self.add_profile, False),
            ("Delete", self.delete_profile, False),
        ):
            item = button(text, primary=primary)
            item.clicked.connect(handler)
            actions.addWidget(item)
        layout.addLayout(actions)

        form = QT.QWidget()
        form.setStyleSheet("background: transparent;")
        grid = QT.QGridLayout(form)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        for row, (title, key) in enumerate(PROFILE_TEXT_FIELDS):
            grid.addWidget(label(title.upper(), role="tiny"), row, 0)
            field = QT.QLineEdit()
            if "token" in key:
                field.setEchoMode(QT.QLineEdit.EchoMode.PasswordEchoOnEdit)
            field.textEdited.connect(self._mark_profile_dirty)
            self.profile_editor_fields[key] = field
            grid.addWidget(field, row, 1)
        offset = len(PROFILE_TEXT_FIELDS)
        for index, (title, key) in enumerate(PROFILE_BOOL_FIELDS):
            check = QT.QCheckBox(native_text(title))
            check.stateChanged.connect(self._mark_profile_dirty)
            self.profile_editor_checks[key] = check
            grid.addWidget(check, offset + index, 1)

        scroll = QT.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QT.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setStyleSheet("background: transparent;")
        scroll.setWidget(form)
        layout.addWidget(scroll, 1)

        self.profile_detail = QT.QTextEdit()
        self.profile_detail.setReadOnly(True)
        self.profile_detail.setProperty("role", "mini")
        self.profile_detail.setFixedHeight(150)
        layout.addWidget(self.profile_detail)
        return frame

    def _copy_page(self) -> Any:
        content = QT.QWidget()
        root = QT.QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self.copy_mode_badge = label("UNKNOWN", role="status")
        self.copy_mode_badge.setProperty("mode", "UNKNOWN")
        self.copy_role_label = label("Role —", role="muted")
        self.copy_worker_label = label("Worker —", role="muted")
        self.copy_status_label = label("Copy controls are profile-scoped.", role="muted")
        root.addWidget(
            self._status_strip(
                label("COPY", role="section"),
                self.copy_mode_badge,
                self.copy_role_label,
                "|",
                self.copy_worker_label,
                self.copy_status_label,
            )
        )

        body = QT.QHBoxLayout()
        body.setSpacing(12)

        self.copy_detail = QT.QTextEdit()
        self.copy_detail.setReadOnly(True)
        self.copy_detail.setProperty("role", "mini")
        self.copy_detail.setMinimumHeight(180)

        guardrails = QT.QWidget()
        guardrails.setStyleSheet("background: transparent;")
        self.copy_guardrails_layout = QT.QVBoxLayout(guardrails)
        self.copy_guardrails_layout.setContentsMargins(0, 0, 0, 0)
        self.copy_guardrails_layout.setSpacing(10)

        body.addWidget(self._section("COPY SETTINGS", self.copy_detail), 1)
        body.addWidget(self._section("SAFETY GUARDRAILS", guardrails), 1)
        root.addLayout(body, 1)
        root.addStretch(0)
        return self._workstation_scroll(content)

    def _pending_page(self) -> Any:
        content = QT.QWidget()
        root = QT.QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self.pending_mode_badge = label("UNKNOWN", role="status")
        self.pending_mode_badge.setProperty("mode", "UNKNOWN")
        self.pending_count_badge = label("— pending", role="status")
        self.pending_action_status = label("Pending controls are profile-scoped.", role="muted")
        refresh = button("Refresh")
        clear_done = button("Clear done")
        refresh.setProperty("compact", "true")
        clear_done.setProperty("compact", "true")
        refresh.clicked.connect(self.refresh)
        clear_done.clicked.connect(self.clear_done_pending)
        root.addWidget(
            self._status_strip(
                label("PENDING", role="section"),
                self.pending_mode_badge,
                self.pending_count_badge,
                "|",
                self.pending_action_status,
                refresh,
                clear_done,
            )
        )

        body = QT.QHBoxLayout()
        body.setSpacing(12)

        left = QT.QWidget()
        left_layout = QT.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        self.pending_summary = QT.QTextEdit()
        self.pending_summary.setReadOnly(True)
        self.pending_summary.setProperty("role", "mini")
        self.pending_summary.setMinimumHeight(160)
        left_layout.addWidget(self.pending_summary, 1)

        items = QT.QWidget()
        items.setStyleSheet("background: transparent;")
        self.pending_items_layout = QT.QVBoxLayout(items)
        self.pending_items_layout.setContentsMargins(0, 0, 0, 0)
        self.pending_items_layout.setSpacing(10)

        scroll = QT.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QT.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setStyleSheet("background: transparent;")
        scroll.setWidget(items)

        body.addWidget(self._section("SESSION FILES", left), 1)
        body.addWidget(self._section("SCHEDULED TASKS", scroll), 1)
        root.addLayout(body, 1)
        root.addStretch(0)
        return self._workstation_scroll(content)

    def _analysis_table(self, columns: list[str], *, stretch: int | None = None) -> Any:
        table = QT.QTableWidget(0, len(columns))
        table.setEditTriggers(QT.QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QT.QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QT.QTableWidget.SelectionMode.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.setHorizontalHeaderLabels([native_text(column) for column in columns])
        header = table.horizontalHeader()
        if stretch is not None and 0 <= stretch < len(columns):
            header.setSectionResizeMode(stretch, QT.QHeaderView.ResizeMode.Stretch)
        return table

    def _analysis_queries(self) -> Any:
        """Return the tested read-only account audit query surface."""
        python_root = SOURCE_ROOT / "python"
        if str(python_root) not in sys.path:
            sys.path.insert(0, str(python_root))
        from oak_core.supervisor.accounts import AccountQueries
        return AccountQueries()

    def _analysis_locale(self) -> str:
        return str(self.settings.get("lang", NATIVE_LANGUAGE)).upper()

    def _accounts_page(self) -> Any:
        content = QT.QWidget()
        layout = QT.QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.accounts_mode_badge = label("UNKNOWN", role="status")
        self.accounts_mode_badge.setProperty("mode", "UNKNOWN")
        self.analysis_account_summary = label("—", role="muted")
        self.analysis_account_summary.setWordWrap(True)
        layout.addWidget(
            self._status_strip(
                label("ACCOUNTS", role="section"),
                self.accounts_mode_badge,
                "|",
                self.analysis_account_summary,
            )
        )

        self.analysis_account_stats_host = QT.QWidget()
        self.analysis_account_stats_layout = QT.QGridLayout(self.analysis_account_stats_host)
        self.analysis_account_stats_layout.setContentsMargins(0, 0, 0, 0)
        self.analysis_account_stats_layout.setHorizontalSpacing(10)
        self.analysis_account_stats_layout.setVerticalSpacing(10)
        layout.addWidget(self._section("ACCOUNT RISK", self.analysis_account_stats_host), 0)

        positions = QT.QWidget()
        positions_layout = QT.QVBoxLayout(positions)
        positions_layout.setContentsMargins(0, 0, 0, 0)
        positions_layout.setSpacing(6)
        header = QT.QHBoxLayout()
        self.analysis_positions_status = label("—", role="muted")
        header.addWidget(self.analysis_positions_status)
        header.addStretch(1)
        positions_layout.addLayout(header)
        self.analysis_positions_table = self._analysis_table(
            ["Symbol", "Direction", "Volume", "Entry", "Current", "P/L"],
            stretch=0,
        )
        self.analysis_positions_table.setMinimumHeight(180)
        positions_layout.addWidget(self.analysis_positions_table, 1)
        layout.addWidget(self._section("OPEN POSITIONS", positions), 1)
        layout.addStretch(0)
        return self._workstation_scroll(content)

    def _performance_page(self) -> Any:
        content = QT.QWidget()
        layout = QT.QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.analysis_period_combo = QT.QComboBox()
        self._analysis_period_keys = [
            ("all", "Toàn bộ lịch sử" if NATIVE_LANGUAGE == "VN" else "All history"),
            ("1m", "1 tháng gần nhất" if NATIVE_LANGUAGE == "VN" else "Last month"),
            ("3m", "3 tháng gần nhất" if NATIVE_LANGUAGE == "VN" else "Last 3 months"),
            ("6m", "6 tháng gần nhất" if NATIVE_LANGUAGE == "VN" else "Last 6 months"),
            ("1y", "1 năm gần nhất" if NATIVE_LANGUAGE == "VN" else "Last year"),
        ]
        for _key, label_text in self._analysis_period_keys:
            self.analysis_period_combo.addItem(label_text, _key)
        self.analysis_period_combo.setCurrentIndex(0)
        self.analysis_period_combo.currentIndexChanged.connect(
            lambda _i: self._refresh_performance_page()
        )
        self.performance_mode_badge = label("UNKNOWN", role="status")
        self.performance_mode_badge.setProperty("mode", "UNKNOWN")
        self.analysis_performance_summary = label("—", role="muted")
        self.analysis_performance_summary.setWordWrap(True)
        layout.addWidget(
            self._status_strip(
                label("PERFORMANCE", role="section"),
                self.performance_mode_badge,
                self.analysis_period_combo,
                "|",
                self.analysis_performance_summary,
            )
        )

        primary = QT.QWidget()
        self.analysis_kpi_primary_host = primary
        self.analysis_kpi_primary_layout = QT.QGridLayout(primary)
        self.analysis_kpi_primary_layout.setContentsMargins(0, 0, 0, 0)
        self.analysis_kpi_primary_layout.setHorizontalSpacing(10)
        self.analysis_kpi_primary_layout.setVerticalSpacing(10)
        secondary = QT.QWidget()
        self.analysis_kpi_secondary_host = secondary
        self.analysis_kpi_secondary_layout = QT.QGridLayout(secondary)
        self.analysis_kpi_secondary_layout.setContentsMargins(0, 0, 0, 0)
        self.analysis_kpi_secondary_layout.setHorizontalSpacing(10)
        self.analysis_kpi_secondary_layout.setVerticalSpacing(10)
        metrics = QT.QWidget()
        metrics_layout = QT.QVBoxLayout(metrics)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(8)
        metrics_layout.addWidget(primary)
        metrics_layout.addWidget(secondary)
        layout.addWidget(self._section("PERFORMANCE METRICS", metrics), 0)

        chart_wrap = QT.QWidget()
        chart_layout = QT.QVBoxLayout(chart_wrap)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(6)
        self.analysis_equity_status = label("—", role="muted")
        chart_layout.addWidget(self.analysis_equity_status)
        self.analysis_equity_chart_view = None
        self.analysis_equity_chart = None
        try:
            from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QDateTimeAxis
            from PySide6.QtCore import QDateTime

            self.analysis_equity_chart = QChart()
            self.analysis_equity_chart.legend().setVisible(True)
            self.analysis_equity_chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
            self.analysis_equity_chart_view = QChartView(self.analysis_equity_chart)
            self.analysis_equity_chart_view.setMinimumHeight(260)
            chart_layout.addWidget(self.analysis_equity_chart_view, 1)
            self._analysis_chart_types = {
                "QChart": QChart,
                "QLineSeries": QLineSeries,
                "QValueAxis": QValueAxis,
                "QDateTimeAxis": QDateTimeAxis,
                "QDateTime": QDateTime,
            }
        except Exception:
            self._analysis_chart_types = {}
            self.analysis_equity_table = self._analysis_table(
                ["Time", "Equity", "Balance", "Drawdown"], stretch=0
            )
            chart_layout.addWidget(self.analysis_equity_table, 1)

        # Hidden/fallback table always available for tests / no-chart builds.
        if self.analysis_equity_chart_view is not None:
            self.analysis_equity_table = self._analysis_table(
                ["Time", "Equity", "Balance", "Drawdown"], stretch=0
            )
            self.analysis_equity_table.setMaximumHeight(0)
            self.analysis_equity_table.hide()

        layout.addWidget(self._section("EQUITY CURVE", chart_wrap), 1)
        layout.addStretch(0)
        return self._workstation_scroll(content)

    def _history_page(self) -> Any:
        content = QT.QWidget()
        layout = QT.QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.history_mode_badge = label("UNKNOWN", role="status")
        self.history_mode_badge.setProperty("mode", "UNKNOWN")
        self.history_status_label = label("Closed-trade ledger · profile-scoped", role="muted")
        layout.addWidget(
            self._status_strip(
                label("HISTORY", role="section"),
                self.history_mode_badge,
                "|",
                self.history_status_label,
            )
        )

        self.analysis_history_summary_host = QT.QWidget()
        self.analysis_history_summary_layout = QT.QGridLayout(self.analysis_history_summary_host)
        self.analysis_history_summary_layout.setContentsMargins(0, 0, 0, 0)
        self.analysis_history_summary_layout.setHorizontalSpacing(10)
        self.analysis_history_summary_layout.setVerticalSpacing(10)
        layout.addWidget(self._section("HISTORY SUMMARY", self.analysis_history_summary_host), 0)

        ledger = QT.QWidget()
        ledger_layout = QT.QVBoxLayout(ledger)
        ledger_layout.setContentsMargins(0, 0, 0, 0)
        ledger_layout.setSpacing(8)
        filters = QT.QHBoxLayout()
        self.analysis_history_search = QT.QLineEdit()
        self.analysis_history_search.setPlaceholderText(native_text("Search symbol or reason…"))
        self.analysis_history_symbol_filter = QT.QComboBox()
        self.analysis_history_type_filter = QT.QComboBox()
        self.analysis_history_type_filter.addItems([native_text("All types"), "BUY", "SELL"])
        self.analysis_history_search.textChanged.connect(self._apply_history_filters)
        self.analysis_history_symbol_filter.currentTextChanged.connect(self._apply_history_filters)
        self.analysis_history_type_filter.currentTextChanged.connect(self._apply_history_filters)
        filters.addWidget(self.analysis_history_search, 1)
        filters.addWidget(self.analysis_history_symbol_filter)
        filters.addWidget(self.analysis_history_type_filter)
        ledger_layout.addLayout(filters)
        self.analysis_history_table = self._analysis_table(
            ["Time", "Symbol", "Type", "Reason", "Volume", "Profit", "Commission", "Swap"], stretch=1
        )
        self.analysis_history_table.setMinimumHeight(180)
        ledger_layout.addWidget(self.analysis_history_table, 1)

        checkpoints = QT.QWidget()
        checkpoints_layout = QT.QVBoxLayout(checkpoints)
        checkpoints_layout.setContentsMargins(0, 0, 0, 0)
        self.analysis_checkpoint_table = self._analysis_table(
            ["Date", "Hour", "Status", "Mode", "Captured"], stretch=0
        )
        self.analysis_checkpoint_table.setMinimumHeight(180)
        checkpoints_layout.addWidget(self.analysis_checkpoint_table, 1)

        split = QT.QHBoxLayout()
        split.setSpacing(12)
        split.addWidget(self._section("HISTORY LEDGER", ledger), 2)
        split.addWidget(self._section("CHECKPOINTS", checkpoints), 1)
        layout.addLayout(split, 1)
        layout.addStretch(0)
        return self._workstation_scroll(content)

    def _news_page(self) -> Any:
        content = QT.QWidget()
        layout = QT.QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.analysis_news_status = label("Informational only · no trade signal", role="muted")
        self.analysis_news_currency_filter = QT.QComboBox()
        self.analysis_news_impact_filter = QT.QComboBox()
        self.analysis_news_impact_filter.addItems([native_text("All impact"), "HIGH", "MEDIUM", "LOW"])
        self.analysis_news_currency_filter.currentTextChanged.connect(self._apply_news_filters)
        self.analysis_news_impact_filter.currentTextChanged.connect(self._apply_news_filters)
        refresh = button("Refresh news", primary=True)
        refresh.setProperty("compact", "true")
        refresh.clicked.connect(self._refresh_news_page)
        layout.addWidget(
            self._status_strip(
                label("NEWS", role="section"),
                self.analysis_news_currency_filter,
                self.analysis_news_impact_filter,
                "|",
                self.analysis_news_status,
                refresh,
            )
        )

        self.analysis_news_summary_host = QT.QWidget()
        self.analysis_news_summary_layout = QT.QGridLayout(self.analysis_news_summary_host)
        self.analysis_news_summary_layout.setContentsMargins(0, 0, 0, 0)
        self.analysis_news_summary_layout.setHorizontalSpacing(10)
        self.analysis_news_summary_layout.setVerticalSpacing(10)
        layout.addWidget(self._section("NEWS OVERVIEW", self.analysis_news_summary_host), 0)

        self.analysis_news_table = self._analysis_table(
            ["Time", "Currency", "Impact", "Headline"], stretch=3
        )
        self.analysis_news_table.setMinimumHeight(220)
        layout.addWidget(self._section("HEADLINES", self.analysis_news_table), 1)
        layout.addStretch(0)
        return self._workstation_scroll(content)

    def _set_analysis_table_rows(self, table: Any, rows: list[list[str]]) -> None:
        table.setUpdatesEnabled(False)
        try:
            table.setRowCount(len(rows))
            for r_index, row in enumerate(rows):
                for c_index, value in enumerate(row):
                    table.setItem(r_index, c_index, QT.QTableWidgetItem(str(value)))
            table.resizeColumnsToContents()
        finally:
            table.setUpdatesEnabled(True)

    def _bind_table_row_details(
        self,
        table: Any,
        payloads: list[dict[str, Any]],
        *,
        title: str,
    ) -> None:
        """Attach row payloads for double-click detail without inventing fields."""
        if table is None:
            return
        key = id(table)
        self._table_detail_payloads[key] = list(payloads)
        self._table_detail_titles[key] = title
        if not getattr(table, "_oak_detail_bound", False):
            table.cellDoubleClicked.connect(
                lambda row, _col, t=table: self._on_table_row_detail(t, row)
            )
            table.setToolTip(native_text("Double-click a row for details"))
            table._oak_detail_bound = True

    def _on_table_row_detail(self, table: Any, row: int) -> None:
        key = id(table)
        payloads = self._table_detail_payloads.get(key) or []
        if row < 0 or row >= len(payloads):
            return
        payload = payloads[row]
        if not isinstance(payload, dict):
            return
        title = self._table_detail_titles.get(key) or native_text("Detail")
        self._show_row_detail_dialog(title, payload)

    def _show_row_detail_dialog(self, title: str, payload: dict[str, Any]) -> None:
        """Compact read-only detail dialog — close/back explicit, no navigation break."""
        # Public-safe fields only; skip internal keys and credentials.
        skip = {
            "ticket", "deal", "order", "comment", "magic", "login", "password",
            "token", "secret", "api_key", "_pending_file", "_pending_key",
            "_pending_identity", "_pending_shape", "_pending_index",
        }
        lines: list[str] = []
        for key, value in payload.items():
            k = str(key)
            if k.startswith("_") or k.lower() in skip:
                continue
            if value is None or value == "":
                text = "unavailable"
            else:
                text = str(value)
            lines.append(f"{k}: {text}")
        if not lines:
            lines = [native_text("No detail fields available")]
        dialog = QT.QDialog(self.window)
        dialog.setWindowTitle(native_text(title))
        dialog.setModal(True)
        dialog.resize(420, 360)
        lay = QT.QVBoxLayout(dialog)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        body = QT.QTextEdit()
        body.setReadOnly(True)
        body.setProperty("role", "mini")
        body.setPlainText("\n".join(lines))
        lay.addWidget(body, 1)
        close_btn = button(native_text("Close"), primary=True)
        close_btn.clicked.connect(dialog.accept)
        row = QT.QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close_btn)
        lay.addLayout(row)
        dialog.exec()

    def _format_analysis_value(self, value: Any, digits: int = 2) -> str:
        if value is None:
            return "—"
        try:
            return f"{float(value):,.{digits}f}"
        except (TypeError, ValueError):
            return str(value)

    def _format_analysis_percent(self, value: Any, digits: int = 2) -> str:
        if value is None:
            return "—"
        try:
            return f"{float(value) * 100:.{digits}f}%"
        except (TypeError, ValueError):
            return str(value)

    def _refresh_analysis_page(self, force: bool = False) -> None:
        if self.current_tab == "Accounts" and (force or self.analysis_account_summary is not None):
            self._refresh_accounts_page()
        elif self.current_tab == "Performance" and (force or self.analysis_performance_summary is not None):
            self._refresh_performance_page()
        elif self.current_tab == "History" and (force or self.analysis_history_table is not None):
            self._refresh_history_page()
        elif self.current_tab == "News" and (force or self.analysis_news_table is not None):
            self._refresh_news_page()

    def _live_mt5_open_positions(self, profile: str) -> list[dict] | None:
        """Best-effort live open positions from the profile terminal (read-only).

        Returns ``None`` when the terminal cannot be queried. Broker symbols are
        preserved exactly (including suffixes such as ``+``).
        """
        profiles = read_json(PROFILE_FILE, {})
        path = str((profiles.get(profile) or {}).get("path") or "").strip()
        if not path:
            return None
        try:
            import MetaTrader5 as mt5
        except Exception:
            return None
        attached = False
        try:
            attached = bool(mt5.initialize(path=path))
            if not attached:
                return None
            positions = mt5.positions_get()
            if positions is None:
                return []
            rows: list[dict] = []
            for pos in positions:
                direction = "BUY" if int(getattr(pos, "type", -1)) == 0 else "SELL"
                rows.append({
                    "symbol": str(getattr(pos, "symbol", "") or ""),
                    "direction": direction,
                    "volume": float(getattr(pos, "volume", 0) or 0),
                    "open_price": float(getattr(pos, "price_open", 0) or 0),
                    "current_price": float(getattr(pos, "price_current", 0) or 0),
                    "profit": float(getattr(pos, "profit", 0) or 0),
                    "source_type": "LIVE_MT5",
                })
            return rows
        except Exception:
            return None
        finally:
            if attached:
                try:
                    mt5.shutdown()
                except Exception:
                    pass

    def _refresh_dashboard_page(self) -> None:
        """Populate trading-workstation dashboard from existing audit/live contracts."""
        if not getattr(self, "dash_mode_badge", None):
            return

        profile = self.selected or "—"
        running = self._profile_is_running(profile) if self.selected else False
        cfg = self.profiles.get(self.selected, {}) if self.selected else {}

        # Mode: only trust explicit trade_mode / account_mode fields — never invent from name.
        mode = self._trade_mode_from_cfg(cfg)
        self._apply_mode_badge(self.dash_mode_badge, mode)
        self.dash_account_label.setText(str(profile))

        mt5_path = str(cfg.get("mt5_path") or cfg.get("terminal_path") or "").strip()
        self.dash_mt5_label.setText(
            "MT5 path set" if mt5_path else "MT5 path unset"
        )
        self.dash_exec_label.setText(
            "Worker RUNNING" if running else "Worker STOPPED"
        )

        account: dict[str, Any] = {}
        audit_positions: list = []
        queries = None
        try:
            queries = self._analysis_queries()
            account = queries.account_get(self.selected) if self.selected else {}
            audit_positions = queries.positions_list(self.selected) if self.selected else []
        except Exception:
            account = {}
            audit_positions = []
            queries = None

        available = bool(account.get("available"))
        updated = account.get("sampled_at_utc") or "—"
        self.dash_fresh_label.setText(f"Updated {updated}")

        def _set_risk(key: str, value: Any, accent: str = "") -> None:
            slot = self.dash_risk_stats.get(key)
            if not slot:
                return
            # Never invent 0 for missing risk fields.
            text = self._format_analysis_value(value) if value is not None else "unavailable"
            slot["value"].setText(text)
            if accent:
                slot["value"].setProperty("accent", accent)
                slot["value"].style().unpolish(slot["value"])
                slot["value"].style().polish(slot["value"])

        open_profit = account.get("open_profit") if available else None
        float_accent = ""
        if open_profit is not None:
            try:
                float_accent = "green" if float(open_profit) >= 0 else "red"
            except (TypeError, ValueError):
                float_accent = ""

        risk: dict[str, Any] = {}
        try:
            if queries is not None and self.selected:
                risk = queries.risk_summary(self.selected)
        except Exception:
            risk = {}
        risk_ok = bool(risk.get("available"))

        _set_risk("equity", account.get("equity") if available else None, "green")
        _set_risk("balance", account.get("balance") if available else None, "")
        _set_risk("floating", open_profit, float_accent)
        # Current DD not always in contract — show unavailable rather than inventing 0.
        _set_risk("cur_dd", None, "amber")
        _set_risk(
            "max_dd",
            risk.get("max_equity_drawdown") if risk_ok else None,
            "red",
        )
        _set_risk("margin", account.get("margin_level") if available else None, "")

        # Equity curve preview (historical only — no fabricated live points)
        try:
            if queries is None:
                queries = self._analysis_queries()
            curve = queries.equity_curve(self.selected, limit=8) if self.selected else []
        except Exception:
            curve = []
        if not isinstance(curve, list):
            curve = []
        eq_rows = []
        for point in curve[-8:]:
            if not isinstance(point, dict):
                continue
            eq_rows.append([
                str(point.get("t") or point.get("time_utc") or point.get("sampled_at_utc") or "—"),
                self._format_analysis_value(point.get("equity")),
                self._format_analysis_value(point.get("balance")),
                self._format_analysis_value(point.get("drawdown")),
            ])
        self._set_analysis_table_rows(self.dash_equity_table, eq_rows)
        self.dash_equity_status.setText(
            native_text("Equity curve uses closed-history samples. Live equity shown in Risk.")
            + (f" · {len(eq_rows)} points" if eq_rows else " · no samples")
        )

        # Open positions preview
        live = self._live_mt5_open_positions(self.selected) if self.selected else None
        positions = live if live is not None else audit_positions
        source = "LIVE_MT5" if live is not None else native_text("Audit checkpoint")
        total_float = 0.0
        float_ok = True
        preview = positions[:6] if isinstance(positions, list) else []
        pos_rows = []
        pos_payloads: list[dict[str, Any]] = []
        for p in preview:
            if not isinstance(p, dict):
                continue
            profit = p.get("profit")
            if profit is not None:
                try:
                    total_float += float(profit)
                except (TypeError, ValueError):
                    float_ok = False
            else:
                float_ok = False
            pos_rows.append([
                str(p.get("symbol") or "—"),
                str(p.get("direction") or "—"),
                self._format_analysis_value(p.get("volume"), 2),
                self._format_analysis_value(profit) if profit is not None else "—",
            ])
            detail = dict(p)
            detail.setdefault("source", source)
            pos_payloads.append(detail)
        self._set_analysis_table_rows(self.dash_positions_table, pos_rows)
        self._bind_table_row_details(self.dash_positions_table, pos_payloads, title="Open position")
        open_count = len(positions) if isinstance(positions, list) else None
        if open_count is None:
            self.dash_pos_status.setText(f"positions unavailable · {source}")
        elif open_count == 0:
            self.dash_pos_status.setText(f"0 open · no positions · {source}")
        else:
            agg = self._format_analysis_value(total_float) if float_ok and preview else "unavailable"
            more = f" · +{open_count - len(preview)} more" if open_count > len(preview) else ""
            self.dash_pos_status.setText(f"{open_count} open · float {agg} · {source}{more}")

        # Pending preview
        try:
            counts, items = self._pending_state(self.selected) if self.selected else ([], [])
        except Exception:
            counts, items = [], []
        pend_rows = []
        pend_payloads: list[dict[str, Any]] = []
        for item in (items or [])[:5]:
            if not isinstance(item, dict):
                continue
            pend_rows.append([
                str(item.get("symbol") or "—"),
                order_type_name(item.get("type") or item.get("order_type")),
                str(item.get("status") or "—"),
            ])
            pend_payloads.append(dict(item))
        self._set_analysis_table_rows(self.dash_pending_table, pend_rows)
        self._bind_table_row_details(self.dash_pending_table, pend_payloads, title="Pending task")
        total_pending = sum(c for _k, c in counts) if counts else len(items or [])
        if total_pending == 0:
            self.dash_pending_status.setText("0 pending · none scheduled")
        else:
            more = f" · +{total_pending - len(pend_rows)} more" if total_pending > len(pend_rows) else ""
            self.dash_pending_status.setText(f"{total_pending} pending{more}")

    def _refresh_accounts_page(self) -> None:
        if self.analysis_positions_table is None:
            return
        if not self.selected:
            self._set_analysis_stat_grid(
                getattr(self, "analysis_account_stats_layout", None),
                getattr(self, "analysis_account_stats", {}),
                [],
            )
            self.analysis_account_summary.setText(native_text("No account audit data"))
            self._set_analysis_table_rows(self.analysis_positions_table, [])
            return
        try:
            queries = self._analysis_queries()
            account = queries.account_get(self.selected)
            audit_positions = queries.positions_list(self.selected)
        except Exception as exc:
            self._set_analysis_stat_grid(
                getattr(self, "analysis_account_stats_layout", None),
                getattr(self, "analysis_account_stats", {}),
                [],
            )
            self.analysis_account_summary.setText(f"{native_text('No account audit data')} · {exc}")
            self._set_analysis_table_rows(self.analysis_positions_table, [])
            return

        cfg = self.profiles.get(self.selected, {}) if self.selected else {}
        mode = self._trade_mode_from_cfg(cfg)
        self._apply_mode_badge(getattr(self, "accounts_mode_badge", None), mode)

        if not account.get("available"):
            self._set_analysis_stat_grid(
                getattr(self, "analysis_account_stats_layout", None),
                getattr(self, "analysis_account_stats", {}),
                [],
            )
            self.analysis_account_summary.setText(native_text("No account audit data"))
        else:
            open_profit = account.get("open_profit")
            float_accent = ""
            if open_profit is not None:
                try:
                    float_accent = "green" if float(open_profit) >= 0 else "red"
                except (TypeError, ValueError):
                    float_accent = ""
            metrics = [
                ("Balance", self._format_analysis_value(account.get("balance")), ""),
                ("Equity", self._format_analysis_value(account.get("equity")), "green"),
                (
                    "Floating P/L",
                    self._format_analysis_value(open_profit) if open_profit is not None else "unavailable",
                    float_accent,
                ),
                (
                    "Margin level",
                    self._format_analysis_value(account.get("margin_level"))
                    if account.get("margin_level") is not None
                    else "unavailable",
                    "",
                ),
            ]
            self._set_analysis_stat_grid(
                getattr(self, "analysis_account_stats_layout", None),
                getattr(self, "analysis_account_stats", {}),
                metrics,
                columns=4,
            )
            updated = account.get("sampled_at_utc") or "—"
            self.analysis_account_summary.setText(
                f"{native_text('Profile')}: {account.get('profile') or self.selected} · "
                f"{native_text('Updated')}: {updated} UTC"
            )

        # Prefer the live MT5 book. Audit checkpoints remain the read-only fallback.
        live = self._live_mt5_open_positions(self.selected)
        positions = live if live is not None else audit_positions
        source = "LIVE_MT5" if live is not None else native_text("Audit checkpoint")
        positions_status = getattr(self, "analysis_positions_status", None)
        if positions_status is not None:
            if not isinstance(positions, list):
                positions_status.setText(f"positions unavailable · {source}")
            elif not positions:
                positions_status.setText(f"0 {native_text('Open positions').lower()} · none · {source}")
            else:
                positions_status.setText(
                    f"{len(positions)} {native_text('Open positions').lower()} · {source} · "
                    f"{native_text('Double-click a row for details')}"
                )
        safe_positions = positions if isinstance(positions, list) else []
        rows = [
            [
                str(p.get("symbol") or "—"),
                str(p.get("direction") or "—"),
                self._format_analysis_value(p.get("volume"), 2),
                self._format_analysis_value(p.get("open_price"), 5),
                self._format_analysis_value(p.get("current_price"), 5) if p.get("current_price") is not None else "—",
                self._format_analysis_value(p.get("profit")) if p.get("profit") is not None else "—",
            ]
            for p in safe_positions
            if isinstance(p, dict)
        ]
        pos_payloads = [
            {**dict(p), "source": source}
            for p in safe_positions
            if isinstance(p, dict)
        ]
        self._set_analysis_table_rows(self.analysis_positions_table, rows)
        self._bind_table_row_details(self.analysis_positions_table, pos_payloads, title="Open position")
        for row_index, position in enumerate(pos_payloads):
            direction = str(position.get("direction") or "").upper()
            profit = position.get("profit")
            item_dir = self.analysis_positions_table.item(row_index, 1)
            item_pl = self.analysis_positions_table.item(row_index, 5)
            if item_dir is not None and direction in {"BUY", "SELL"}:
                item_dir.setForeground(
                    QT.QColor("#2fa572" if direction == "BUY" else "#e05260")
                )
            if item_pl is not None and profit is not None:
                try:
                    item_pl.setForeground(
                        QT.QColor("#2fa572" if float(profit) >= 0 else "#e05260")
                    )
                except (TypeError, ValueError):
                    pass

    def _analysis_stat_card(self, title: str, value: str = "—", accent: str = "") -> tuple[Any, Any]:
        frame = QT.QFrame()
        frame.setProperty("role", "stat")
        lay = QT.QVBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(3)
        title_row = QT.QHBoxLayout()
        title_lbl = label(title, role="tiny")
        title_lbl.setWordWrap(True)
        title_lbl.setMinimumHeight(18)
        title_row.addWidget(title_lbl, 1)
        if title in ANALYSIS_KPI_HELP:
            info = QT.QPushButton("?")
            info.setFixedSize(22, 22)
            info.setCursor(QT.Qt.CursorShape.PointingHandCursor)
            info.setStyleSheet("QPushButton{color:#2fa572;background:transparent;border:1px solid #3a4654;border-radius:11px;font-weight:900;font-size:13px;padding:0} QPushButton:hover{color:#00C991;border-color:#2fa572}")
            info.setToolTip("Explain metric")
            info.clicked.connect(lambda _checked=False, metric=title: self._show_analysis_kpi_help(metric))
            title_row.addWidget(info)
        lay.addLayout(title_row)
        value_lbl = label(value, role="value", accent=accent)
        value_lbl.setTextInteractionFlags(QT.Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(value_lbl)
        return frame, value_lbl

    def _show_analysis_kpi_help(self, title: str) -> None:
        """Show a concise, bilingual definition for one performance KPI."""
        copy = ANALYSIS_KPI_HELP.get(title)
        if not copy:
            return
        message = copy.get(NATIVE_LANGUAGE, copy.get("EN", ""))
        QMessageBox.information(self.window, native_text(title), message)


    def _set_analysis_stat_grid(
        self,
        grid: Any,
        target: dict[str, Any],
        metrics: list[tuple[str, str, str]],
        columns: int = 4,
    ) -> None:
        if grid is None:
            return
        while grid.count():
            item = grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        target.clear()
        for index, (title, value, accent) in enumerate(metrics):
            frame, value_lbl = self._analysis_stat_card(title, value, accent)
            target[title] = value_lbl
            grid.addWidget(frame, index // columns, index % columns)

    def _kpi_card(self, title: str) -> tuple[Any, Any]:
        return self._analysis_stat_card(title)

    def _set_kpi_values(self, metrics: list[tuple[str, str, str] | tuple[str, str]]) -> None:
        def normalize(items: list[tuple[str, str, str] | tuple[str, str]]) -> list[tuple[str, str, str]]:
            return [
                (item[0], item[1], item[2] if len(item) > 2 else "")
                for item in items
            ]

        primary = normalize(metrics[:6])
        secondary = normalize(metrics[6:])
        self._set_analysis_stat_grid(
            getattr(self, "analysis_kpi_primary_layout", None),
            self.analysis_kpi_cards,
            primary,
            columns=3,
        )
        secondary_target: dict[str, Any] = {}
        self._set_analysis_stat_grid(
            getattr(self, "analysis_kpi_secondary_layout", None),
            secondary_target,
            secondary,
            columns=4,
        )
        self.analysis_kpi_cards.update(secondary_target)

    def _render_equity_chart(self, curve: list[dict], drawdown: list[dict]) -> None:
        status = getattr(self, "analysis_equity_status", None)
        chart = getattr(self, "analysis_equity_chart", None)
        types = getattr(self, "_analysis_chart_types", {}) or {}
        dd_map = {str(item.get("t")): item.get("drawdown") for item in drawdown}
        rows = [
            [
                str(item.get("t") or "—"),
                self._format_analysis_value(item.get("equity")),
                self._format_analysis_value(item.get("balance")),
                self._format_analysis_value(dd_map.get(str(item.get("t")))),
            ]
            for item in curve
        ]
        if self.analysis_equity_table is not None:
            self._set_analysis_table_rows(self.analysis_equity_table, rows)

        if chart is None or not types:
            if status is not None:
                status.setText(native_text("Equity curve") if curve else native_text("No performance data"))
            return

        chart.removeAllSeries()
        for axis in list(chart.axes()):
            chart.removeAxis(axis)

        if len(curve) < 1:
            if status is not None:
                status.setText(native_text("No performance data"))
            return

        QLineSeries = types["QLineSeries"]
        QValueAxis = types["QValueAxis"]
        QDateTimeAxis = types["QDateTimeAxis"]
        QDateTime = types["QDateTime"]

        equity_series = QLineSeries()
        equity_series.setName("Equity")
        balance_series = QLineSeries()
        balance_series.setName("Balance")
        dd_series = QLineSeries()
        dd_series.setName("Drawdown")

        has_balance = False
        has_dd = False
        ymin, ymax = None, None
        for item in curve:
            t_raw = item.get("t")
            if not t_raw:
                continue
            try:
                dt = QDateTime.fromString(str(t_raw)[:19].replace("T", " "), "yyyy-MM-dd HH:mm:ss")
                if not dt.isValid():
                    dt = QDateTime.fromString(str(t_raw), QT.Qt.DateFormat.ISODate)
                if not dt.isValid():
                    continue
                ms = dt.toMSecsSinceEpoch()
            except Exception:
                continue
            eq = item.get("equity")
            bal = item.get("balance")
            dd = dd_map.get(str(t_raw))
            if eq is not None:
                equity_series.append(ms, float(eq))
                ymin = float(eq) if ymin is None else min(ymin, float(eq))
                ymax = float(eq) if ymax is None else max(ymax, float(eq))
            if bal is not None:
                has_balance = True
                balance_series.append(ms, float(bal))
                ymin = float(bal) if ymin is None else min(ymin, float(bal))
                ymax = float(bal) if ymax is None else max(ymax, float(bal))
            if dd is not None:
                has_dd = True
                dd_series.append(ms, float(dd))

        chart.addSeries(equity_series)
        if has_balance:
            chart.addSeries(balance_series)
        if has_dd:
            chart.addSeries(dd_series)

        axis_x = QDateTimeAxis()
        axis_x.setFormat("MM-dd HH:mm")
        axis_x.setTitleText("Time (UTC)")
        chart.addAxis(axis_x, QT.Qt.AlignmentFlag.AlignBottom)
        equity_series.attachAxis(axis_x)
        if has_balance:
            balance_series.attachAxis(axis_x)
        if has_dd:
            dd_series.attachAxis(axis_x)

        axis_y = QValueAxis()
        if ymin is not None and ymax is not None and ymin != ymax:
            pad = max(abs(ymax - ymin) * 0.08, 0.01)
            axis_y.setRange(ymin - pad, ymax + pad)
        axis_y.setTitleText("Value")
        chart.addAxis(axis_y, QT.Qt.AlignmentFlag.AlignLeft)
        equity_series.attachAxis(axis_y)
        if has_balance:
            balance_series.attachAxis(axis_y)

        if has_dd:
            axis_dd = QValueAxis()
            axis_dd.setTitleText("Drawdown")
            chart.addAxis(axis_dd, QT.Qt.AlignmentFlag.AlignRight)
            dd_series.attachAxis(axis_dd)

        latest_eq = curve[-1].get("equity") if curve else None
        if status is not None:
            status.setText(
                f"{native_text('Equity curve')} · n={len(curve)} · "
                f"latest={self._format_analysis_value(latest_eq)}"
            )

    def _analysis_period_since_utc(self):
        """Rolling period start from the period combo; None = all history."""
        combo = getattr(self, "analysis_period_combo", None)
        if combo is None:
            return None, "all"
        key = combo.currentData()
        if key in (None, "all"):
            return None, "all"
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        days = {"1m": 30, "3m": 90, "6m": 180, "1y": 365}.get(str(key))
        if days is None:
            return None, "all"
        return now - timedelta(days=days), str(key)

    def _refresh_performance_page(self) -> None:
        if self.analysis_performance_summary is None:
            return
        cfg = self.profiles.get(self.selected, {}) if self.selected else {}
        self._apply_mode_badge(getattr(self, "performance_mode_badge", None), self._trade_mode_from_cfg(cfg))
        if not self.selected:
            self.analysis_performance_summary.setText(native_text("No performance data"))
            self._set_kpi_values([])
            self._render_equity_chart([], [])
            return
        since_utc, period_key = self._analysis_period_since_utc()
        period_label = ""
        combo = getattr(self, "analysis_period_combo", None)
        if combo is not None:
            period_label = combo.currentText()
        try:
            queries = self._analysis_queries()
            perf = queries.performance_summary(self.selected, since_utc=since_utc)
            curve = queries.equity_curve(self.selected, limit=5000 if since_utc else 200, since_utc=since_utc)
            drawdown = queries.drawdown_curve(self.selected, limit=5000 if since_utc else 200)
            if since_utc is not None and drawdown:
                drawdown = [d for d in drawdown if d.get("t") and str(d.get("t")) >= since_utc.isoformat()[:19]]
        except Exception as exc:
            self.analysis_performance_summary.setText(f"{native_text('No performance data')} · {exc}")
            self._set_kpi_values([])
            self._render_equity_chart([], [])
            return

        def _pct(value: Any) -> str:
            if value is None:
                return "—"
            try:
                return f"{float(value) * 100:.2f}%"
            except (TypeError, ValueError):
                return "—"

        if not perf.get("available"):
            self.analysis_performance_summary.setText(native_text("No performance data"))
            self._set_kpi_values([])
        else:
            latest = curve[-1].get("t") if curve else "—"
            n_closed = perf.get("closed_trade_count")
            self.analysis_performance_summary.setText(
                f"Hồ sơ: {perf.get('profile') or self.selected} · "
                f"Khoảng thời gian: {period_label or period_key} · "
                f"n={len(curve)} samples · closed={n_closed} · latest {latest} UTC"
            )
            net_profit = perf.get("net_profit")
            current_dd = perf.get("current_drawdown")
            def _signed_accent(value: Any, *, positive_is_green: bool = True) -> str:
                if value is None:
                    return ""
                try:
                    num = float(value)
                except (TypeError, ValueError):
                    return ""
                if positive_is_green:
                    return "green" if num >= 0 else "red"
                return "red" if num > 0 else "green"

            kpis = [
                ("Net P&L", self._format_analysis_value(net_profit) if net_profit is not None else "unavailable", _signed_accent(net_profit)),
                ("Trading return", self._format_analysis_percent(perf.get("trading_return_pct")), ""),
                ("Win rate", _pct(perf.get("win_rate")), ""),
                ("Profit factor", self._format_analysis_value(perf.get("profit_factor")), ""),
                (
                    "Expectancy",
                    self._format_analysis_value(perf.get("expectancy")) if perf.get("expectancy") is not None else "unavailable",
                    _signed_accent(perf.get("expectancy")),
                ),
                (
                    "Current drawdown",
                    self._format_analysis_value(current_dd) if current_dd is not None else "unavailable",
                    _signed_accent(current_dd, positive_is_green=False),
                ),
                ("Max drawdown", self._format_analysis_value(perf.get("max_equity_drawdown")), ""),
                ("Avg win", self._format_analysis_value(perf.get("average_win")), "green"),
                ("Avg loss", self._format_analysis_value(perf.get("average_loss")), "red"),
                ("Account growth", self._format_analysis_percent(perf.get("account_growth_pct")), ""),
            ]
            self._set_kpi_values(kpis)

        self._render_equity_chart(curve, drawdown)

    def _refresh_history_page(self) -> None:
        if self.analysis_history_table is None or self.analysis_checkpoint_table is None:
            return
        cfg = self.profiles.get(self.selected, {}) if self.selected else {}
        self._apply_mode_badge(getattr(self, "history_mode_badge", None), self._trade_mode_from_cfg(cfg))
        if not self.selected:
            self._set_analysis_stat_grid(self.analysis_history_summary_layout, self.analysis_history_summary, [])
            self.analysis_history_deals = []
            self._set_analysis_table_rows(self.analysis_history_table, [])
            self._set_analysis_table_rows(self.analysis_checkpoint_table, [])
            return
        try:
            queries = self._analysis_queries()
            deals = queries.deals_list(self.selected, limit=300)
            checkpoints = queries.checkpoints_list(self.selected, limit=60)
            performance = queries.performance_summary(self.selected)
        except Exception:
            deals, checkpoints, performance = [], [], {"available": False}
        self.analysis_history_deals = list(deals)
        if performance.get("available"):
            closed_count = int(performance.get("closed_trade_count") or 0)
            realized = performance.get("realized_pl")
            commission = performance.get("total_commission")
            swap = performance.get("total_swap")
            win_rate = performance.get("win_rate")
        else:
            closed_count = None
            realized = None
            commission = None
            swap = None
            win_rate = None
        realized_accent = ""
        if realized is not None:
            try:
                realized_accent = "green" if float(realized) >= 0 else "red"
            except (TypeError, ValueError):
                realized_accent = ""
        summary = [
            (
                "Closed trades",
                self._format_analysis_value(closed_count, 0) if closed_count is not None else "unavailable",
                "",
            ),
            (
                "Realized P/L",
                self._format_analysis_value(realized) if realized is not None else "unavailable",
                realized_accent,
            ),
            (
                "Total commission",
                self._format_analysis_value(commission) if commission is not None else "unavailable",
                "",
            ),
            (
                "Total swap",
                self._format_analysis_value(swap) if swap is not None else "unavailable",
                "",
            ),
            (
                "Win rate",
                f"{float(win_rate) * 100:.2f}%" if win_rate is not None else "unavailable",
                "",
            ),
        ]
        self._set_analysis_stat_grid(self.analysis_history_summary_layout, self.analysis_history_summary, summary, columns=5)
        self._refresh_history_filter_options()
        self._apply_history_filters()
        checkpoint_rows = [
            [
                str(c.get("broker_date") or "—"),
                str(c.get("checkpoint_hour") or "—"),
                str(c.get("status") or "—"),
                str(c.get("capture_mode") or "—"),
                str(c.get("captured_at_utc") or "—"),
            ]
            for c in checkpoints
        ]
        self._set_analysis_table_rows(self.analysis_checkpoint_table, checkpoint_rows)

    def _refresh_history_filter_options(self) -> None:
        combo = self.analysis_history_symbol_filter
        if combo is None:
            return
        current = combo.currentText()
        symbols = sorted({str(d.get("symbol") or "") for d in self.analysis_history_deals if d.get("symbol")})
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(native_text("All symbols"))
        combo.addItems(symbols)
        if current in symbols or current == native_text("All symbols"):
            combo.setCurrentText(current)
        else:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _apply_history_filters(self, *_args: Any) -> None:
        if self.analysis_history_table is None:
            return
        symbol_text = self.analysis_history_symbol_filter.currentText() if self.analysis_history_symbol_filter else native_text("All symbols")
        type_text = self.analysis_history_type_filter.currentText() if self.analysis_history_type_filter else native_text("All types")
        symbol = "All symbols" if symbol_text == native_text("All symbols") else symbol_text
        deal_type = "All types" if type_text == native_text("All types") else type_text
        search = (self.analysis_history_search.text() if self.analysis_history_search else "").strip().lower()
        filtered = filter_analysis_history_deals(
            self.analysis_history_deals,
            symbol=symbol,
            deal_type=deal_type,
            search=search,
        )
        rows = [
            [
                str(d.get("deal_time_utc") or "—"),
                str(d.get("symbol") or "—"),
                str(d.get("deal_type") or "—"),
                str(d.get("reason_category") or d.get("entry_type") or "—"),
                self._format_analysis_value(d.get("volume"), 2),
                self._format_analysis_value(d.get("profit")),
                self._format_analysis_value(d.get("commission")),
                self._format_analysis_value(d.get("swap")),
            ]
            for d in filtered
        ]
        self._set_analysis_table_rows(self.analysis_history_table, rows)
        self._bind_table_row_details(
            self.analysis_history_table,
            [dict(d) for d in filtered if isinstance(d, dict)],
            title="Closed deal",
        )
        if getattr(self, "history_status_label", None) is not None:
            if not filtered:
                self.history_status_label.setText(
                    native_text("No closed deals for current filters · profile-scoped")
                )
            else:
                self.history_status_label.setText(
                    f"{len(filtered)} deals · {native_text('Double-click a row for details')}"
                )
        for row_index, deal in enumerate(filtered):
            deal_type = str(deal.get("deal_type") or "").upper()
            item_type = self.analysis_history_table.item(row_index, 2)
            item_pl = self.analysis_history_table.item(row_index, 5)
            if item_type is not None and deal_type in {"BUY", "SELL"}:
                item_type.setForeground(
                    QT.QColor("#2fa572" if deal_type == "BUY" else "#e05260")
                )
            if item_pl is None or deal.get("profit") is None:
                continue
            try:
                profit = float(deal.get("profit"))
                item_pl.setForeground(
                    QT.QColor("#2fa572" if profit >= 0 else "#e05260")
                )
            except (TypeError, ValueError):
                pass

    def _refresh_news_page(self) -> None:
        if self.analysis_news_table is None:
            return
        try:
            python_root = SOURCE_ROOT / "python"
            if str(python_root) not in sys.path:
                sys.path.insert(0, str(python_root))
            from oak_core.supervisor.news import local_news
            payload = local_news(self._analysis_locale())
        except Exception as exc:
            self.analysis_news_items = []
            self._set_analysis_stat_grid(self.analysis_news_summary_layout, self.analysis_news_summary, [])
            self._set_analysis_table_rows(self.analysis_news_table, [])
            if self.analysis_news_status is not None:
                self.analysis_news_status.setText(str(exc))
            return
        items = [dict(item) for item in (payload.get("items") or []) if isinstance(item, dict)]
        self.analysis_news_items = items
        counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for item in items:
            impact = str(item.get("impact") or "").upper()
            if impact in counts:
                counts[impact] += 1
        summary = [
            ("High", str(counts["HIGH"]), "red"),
            ("Medium", str(counts["MEDIUM"]), "amber"),
            ("Low", str(counts["LOW"]), "green"),
            ("Total", str(len(items)), ""),
        ]
        self._set_analysis_stat_grid(self.analysis_news_summary_layout, self.analysis_news_summary, summary, columns=4)
        self._refresh_news_filter_options()
        self._apply_news_filters()
        if self.analysis_news_status is not None:
            cache_date = payload.get("cache_date") or "—"
            broker_date = payload.get("broker_date") or "—"
            stale = payload.get("stale")
            state = "stale" if stale is True else "ready" if payload.get("available") else "unavailable"
            self.analysis_news_status.setText(
                f"{native_text('Cache day')}: {cache_date} · {native_text('Broker day')}: {broker_date} · {state} · {len(items)}"
            )

    def _refresh_news_filter_options(self) -> None:
        combo = self.analysis_news_currency_filter
        if combo is None:
            return
        current = combo.currentText()
        currencies = sorted({str(item.get("currency") or "").upper() for item in self.analysis_news_items if item.get("currency")})
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(native_text("All currencies"))
        combo.addItems(currencies)
        if current in currencies or current == native_text("All currencies"):
            combo.setCurrentText(current)
        else:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _apply_news_filters(self, *_args: Any) -> None:
        if self.analysis_news_table is None:
            return
        currency_text = self.analysis_news_currency_filter.currentText() if self.analysis_news_currency_filter else native_text("All currencies")
        impact_text = self.analysis_news_impact_filter.currentText() if self.analysis_news_impact_filter else native_text("All impact")
        currency = "All currencies" if currency_text == native_text("All currencies") else currency_text
        impact = "All impact" if impact_text == native_text("All impact") else impact_text
        filtered = filter_analysis_news_items(
            self.analysis_news_items,
            currency=currency,
            impact=impact,
        )
        rows = [
            [
                str(item.get("time") or "—"),
                str(item.get("currency") or "—"),
                str(item.get("impact") or "—").upper(),
                str(item.get("title") or "—"),
            ]
            for item in filtered
        ]
        self._set_analysis_table_rows(self.analysis_news_table, rows)
        for row_index, item in enumerate(filtered):
            impact = str(item.get("impact") or "").upper()
            accent = {"HIGH": "#e05260", "MEDIUM": "#d4a03d", "LOW": "#2fa572"}.get(impact)
            if accent:
                self.analysis_news_table.item(row_index, 2).setForeground(QT.QColor(accent))

    def _diagnostics_page(self) -> Any:
        content = QT.QWidget()
        root = QT.QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self.diag_health_badge = label("READY", role="status")
        self.diag_status = label("Diagnostics export is redacted by default.", role="muted")
        refresh = button("Refresh")
        export_btn = button("Export bundle")
        refresh.setProperty("compact", "true")
        export_btn.setProperty("compact", "true")
        refresh.clicked.connect(self.refresh)
        export_btn.clicked.connect(self.export_debug_bundle)
        root.addWidget(
            self._status_strip(
                label("DIAGNOSTICS", role="section"),
                self.diag_health_badge,
                "|",
                self.diag_status,
                refresh,
                export_btn,
            )
        )

        body = QT.QHBoxLayout()
        body.setSpacing(12)

        left = QT.QWidget()
        left_layout = QT.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        actions = QT.QGridLayout()
        actions.setHorizontalSpacing(8)
        actions.setVerticalSpacing(8)
        for index, (text, handler) in enumerate(
            (
                ("Copy report", self.copy_diagnostics_report),
                ("Copy visible", self.copy_visible_log),
                ("App folder", self.open_app_folder),
                ("Log folder", self.open_log_folder),
            )
        ):
            item = button(text)
            item.setProperty("compact", "true")
            item.clicked.connect(handler)
            actions.addWidget(item, index // 2, index % 2)
        left_layout.addLayout(actions)
        filters = QT.QHBoxLayout()
        self.diag_filter = QT.QLineEdit()
        self.diag_filter.setPlaceholderText(native_text("Search logs: profile, ERROR, ticket, symbol..."))
        self.diag_filter.textChanged.connect(lambda _text: self._refresh_diagnostics_page())
        self.diag_level = QT.QComboBox()
        self.diag_level.addItems(["ALL", "INFO", "WARN", "ERROR"])
        self.diag_level.currentTextChanged.connect(lambda _text: self._refresh_diagnostics_page())
        clear_display = button("Clear display")
        clear_display.setProperty("compact", "true")
        clear_display.clicked.connect(self.clear_diagnostics_display)
        filters.addWidget(self.diag_filter, 1)
        filters.addWidget(self.diag_level)
        filters.addWidget(clear_display)
        left_layout.addLayout(filters)
        self.diag_summary = QT.QTextEdit()
        self.diag_summary.setReadOnly(True)
        self.diag_summary.setProperty("role", "mini")
        self.diag_summary.setMinimumHeight(160)
        left_layout.addWidget(self.diag_summary, 1)

        self.diag_log = QT.QTextEdit()
        self.diag_log.setReadOnly(True)
        self.diag_log.setProperty("role", "mini")
        self.diag_log.setMinimumHeight(220)

        body.addWidget(self._section("RUNTIME CHECK", left), 1)
        body.addWidget(self._section("LATEST LOG", self.diag_log), 1)
        root.addLayout(body, 1)
        root.addStretch(0)
        return self._workstation_scroll(content)

    def _settings_page(self) -> Any:
        content = QT.QWidget()
        root = QT.QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self.settings_status = label("Settings are stored in settings.json.", role="muted")
        save = button("Save settings", primary=True)
        reset = button("Reset theme")
        artifacts = button("Open artifacts")
        save.setProperty("compact", "true")
        reset.setProperty("compact", "true")
        artifacts.setProperty("compact", "true")
        save.clicked.connect(self.save_native_settings)
        reset.clicked.connect(self.reset_native_theme)
        artifacts.clicked.connect(lambda: self._open_folder(ROOT / "dist"))
        root.addWidget(
            self._status_strip(
                label("SETTINGS", role="section"),
                "|",
                self.settings_status,
                save,
                reset,
                artifacts,
            )
        )

        body = QT.QHBoxLayout()
        body.setSpacing(12)

        controls = QT.QWidget()
        controls_layout = QT.QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(12)

        self.settings_lang_combo = QT.QComboBox()
        self.settings_lang_combo.addItems(["EN", "VN"])
        self.settings_lang_combo.setMinimumHeight(42)
        self.settings_theme_combo = QT.QComboBox()
        self.settings_theme_combo.addItems(["dark", "light", "deep-sea", "contrast"])
        self.settings_theme_combo.setMinimumHeight(42)
        controls_layout.addWidget(self._settings_row("Language", "Dashboard language preference.", self.settings_lang_combo))
        controls_layout.addWidget(self._settings_row("Theme", "NativeQt visual skin. Applies instantly after save.", self.settings_theme_combo))
        controls_layout.addWidget(self._guardrail_row("NativeQt", "LEAN", "Qt Widgets + QSS only; no Chromium/WebEngine payload.", "green"))
        controls_layout.addWidget(self._guardrail_row("Installer", "SMALL", "Current NativeQt installer stays around 40 MB.", "amber"))
        controls_layout.addStretch(1)

        self.settings_about = QT.QTextEdit()
        self.settings_about.setReadOnly(True)
        self.settings_about.setProperty("role", "mini")
        self.settings_about.setMinimumHeight(180)

        body.addWidget(self._section("PREFERENCES", controls), 1)
        body.addWidget(self._section("ABOUT / BUILD", self.settings_about), 1)
        root.addLayout(body, 1)
        root.addStretch(0)
        return self._workstation_scroll(content)

    def _settings_row(self, title: str, hint: str, field: Any) -> Any:
        row = QT.QFrame()
        row.setProperty("role", "row")
        layout = QT.QVBoxLayout(row)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(label(title, role="section"))
        hint_label = label(hint, role="muted")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
        layout.addWidget(field)
        return row

    def _signal_card(self, key: str, name: str, color: str) -> Any:
        frame = QT.QFrame()
        frame.setProperty("role", "signal")
        frame.setProperty("state", "stopped")
        layout = QT.QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        header = QT.QHBoxLayout()
        dot = label("●", accent="red")
        title = label(name)
        status = label("Stopped", role="muted")
        pid = label("PID: ---", role="muted")
        copy_log = button("⧉")
        copy_log.setToolTip(native_text("Copy log"))
        start = button("▶")
        stop = button("■")
        copy_log.setFixedWidth(44)
        start.setFixedWidth(44)
        stop.setFixedWidth(44)
        stop.setEnabled(False)
        copy_log.clicked.connect(lambda _checked=False, k=key: self.copy_signal_log(k))
        start.clicked.connect(lambda _checked=False, k=key: self.start_signal(k))
        stop.clicked.connect(lambda _checked=False, k=key: self.stop_signal(k))
        header.addWidget(dot)
        header.addWidget(title)
        header.addWidget(status)
        header.addStretch(1)
        header.addWidget(copy_log)
        header.addWidget(start)
        header.addWidget(stop)
        header.addWidget(pid)
        console = QT.QTextEdit()
        console.setReadOnly(True)
        console.setProperty("role", "mini")
        console.document().setMaximumBlockCount(700)
        layout.addLayout(header)
        layout.addWidget(console, 1)
        self.signal_cards[key] = {
            "frame": frame,
            "name": name,
            "color": color,
            "dot": dot,
            "console": console,
            "status": status,
            "pid": pid,
            "copy": copy_log,
            "start": start,
            "stop": stop,
        }
        return frame

    def _placeholder_page(self, title: str, message: str) -> Any:
        frame = panel()
        layout = QT.QVBoxLayout(frame)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(14)
        layout.addWidget(label(title, role="section"))
        hint = QT.QFrame()
        hint.setProperty("role", "hint")
        hint_layout = QT.QVBoxLayout(hint)
        hint_layout.addWidget(label(message))
        hint_layout.addWidget(label("Native Qt shell is active; classic UI remains one click away.", role="muted"))
        layout.addWidget(hint)
        layout.addStretch(1)
        return frame

    def _section(self, title: str, content: Any) -> Any:
        frame = panel()
        layout = QT.QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(label(title, role="tiny"))
        layout.addWidget(content, 1)
        return frame

    def _trade_mode_from_cfg(self, cfg: dict[str, Any] | None) -> str:
        """LIVE/DEMO/UNKNOWN from explicit config only — never invent from profile name."""
        cfg = cfg or {}
        mode_raw = str(cfg.get("trade_mode") or cfg.get("account_mode") or "").strip().upper()
        if mode_raw in {"LIVE", "REAL"}:
            return "LIVE"
        if mode_raw in {"DEMO", "PRACTICE"}:
            return "DEMO"
        return "UNKNOWN"

    def _apply_mode_badge(self, widget: Any, mode: str) -> None:
        """Set badge text + QSS mode property for LIVE/DEMO/UNKNOWN/READY/DEGRADED/UNAVAILABLE/STALE."""
        if widget is None:
            return
        text = str(mode or "UNKNOWN").strip().upper() or "UNKNOWN"
        widget.setText(text)
        widget.setProperty("mode", text)
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)

    def _workstation_scroll(self, content: Any) -> Any:
        """Wrap tab body in scroll + min-width so narrow resize never collapses."""
        if isinstance(content, QT.QWidget):
            content.setMinimumWidth(720)
            content.setSizePolicy(
                QT.QSizePolicy.Policy.Expanding,
                QT.QSizePolicy.Policy.MinimumExpanding,
            )
        page = QT.QWidget()
        page_layout = QT.QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        scroll = QT.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QT.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QT.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(QT.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.viewport().setStyleSheet("background: transparent;")
        scroll.setWidget(content)
        page_layout.addWidget(scroll, 1)
        return page

    def _status_strip(self, *widgets: Any) -> Any:
        """Horizontal health/status strip matching dashboard workstation density."""
        host = panel()
        lay = QT.QHBoxLayout(host)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(14)
        for i, w in enumerate(widgets):
            if w is None:
                continue
            if isinstance(w, str) and w == "|":
                lay.addStretch(1)
                continue
            lay.addWidget(w)
        return host

    def _ready(self) -> None:
        if callable(self.ready_callback):
            self.ready_callback(True)

    def _install_shortcuts(self) -> None:
        """Install lightweight keyboard shortcuts for operator flow."""
        for index, tab in enumerate(self.tab_pages, 1):
            self._add_shortcut(f"Ctrl+{index}", lambda tab=tab: self.switch_tab(tab))
        for sequence in ("Ctrl+R", "F5"):
            self._add_shortcut(sequence, self.refresh)
        self._add_shortcut("Ctrl+S", self._save_current_context)
        self._add_shortcut("Esc", self._clear_transient_guards)

    def _add_shortcut(self, sequence: str, handler: Any) -> None:
        shortcut = QT.QShortcut(QT.QKeySequence(sequence), self.window)
        shortcut.activated.connect(handler)
        self.shortcuts.append(shortcut)

    def _save_current_context(self) -> None:
        if self.current_tab == "Profiles":
            self.save_profile()
            return
        if self.current_tab == "Settings":
            self.save_native_settings()
            return
        if self.current_tab == "VN30 Advisor":
            self.save_stock_advisor_settings()
            return
        self._set_live_status("No save target")

    def _clear_transient_guards(self) -> None:
        self.pending_delete_key = ""
        self.pending_delete_profile = ""
        self._set_pending_status("Delete guard cleared.", "amber")
        self._set_profile_editor_status("Delete guard cleared.", "amber")

    def _start_live_timer(self) -> None:
        """Start the live update timer with adaptive interval.
        
        Performance: Use 1-second interval for responsiveness but implement
        throttling inside _refresh_live_state to reduce unnecessary updates.
        """
        self.live_timer = QT.QTimer(self.window)
        self.live_timer.timeout.connect(self._refresh_live_state)
        self.live_timer.start(1000)

    def _select_profile(self, name: str) -> None:
        if not name:
            return
        self.selected = name
        self.pending_delete_key = ""
        self.refresh()

    def _rebuild_translated_ui(self) -> None:
        """Recreate visible widgets without losing selected profile or console text."""
        current_tab = self.current_tab
        selected = self.selected
        console_text = self.console.toPlainText() if hasattr(self, "console") else ""
        signal_logs = {key: card["console"].toPlainText() for key, card in self.signal_cards.items()}
        old_root = self.window.takeCentralWidget()
        if old_root is not None:
            old_root.deleteLater()
        self.nav_buttons = {}
        self.signal_cards = {}
        self._build()
        self._bind_signal_supervisor_ui()
        self.selected = selected
        self.console.setPlainText(console_text)
        for key, text in signal_logs.items():
            if key in self.signal_cards:
                self.signal_cards[key]["console"].setPlainText(text)
        self.refresh()
        self.switch_tab(current_tab)

    def refresh(self) -> None:
        self._reload_state_files()
        target_language = str(self.settings.get("lang", "EN")).upper()
        if target_language != NATIVE_LANGUAGE:
            set_native_language(target_language)
            self._rebuild_translated_ui()
            return
        self._refresh_combo()
        self._refresh_profiles()
        self._refresh_profile_page()
        self._refresh_copy_page()
        self._refresh_pending_page(force=True)
        self._refresh_diagnostics_page()
        self._refresh_settings_page()
        self._refresh_stock_advisor_page()
        self._refresh_signal_states()
        self._refresh_analysis_page()
        self._refresh_dashboard_page()
        self._refresh_nav()
        running = self._running_profiles()
        self.stat_profiles["value"].setText(str(len(self.profiles)))
        self.stat_running["value"].setText(str(len(running)))
        self.stat_lang["value"].setText(str(self.settings.get("lang", "VN")))
        self.stat_theme["value"].setText(str(self.settings.get("theme", "dark")))
        self._refresh_profile_controls()
        self._set_live_status("Manual refresh")
        self.subtitle.setText(
            native_format(
                "Selected profile: {profile} · Native Qt/QSS, no Chromium",
                profile=self.selected or "—",
            )
        )
        # Update rail lang buttons
        if hasattr(self, "rail_lang_en") and self.rail_lang_en is not None:
            cur = NATIVE_LANGUAGE
            self.rail_lang_en.setProperty("active", "true" if cur == "EN" else "false")
            self.rail_lang_en.style().unpolish(self.rail_lang_en)
            self.rail_lang_en.style().polish(self.rail_lang_en)
        if hasattr(self, "rail_lang_vn") and self.rail_lang_vn is not None:
            cur = NATIVE_LANGUAGE
            self.rail_lang_vn.setProperty("active", "true" if cur == "VN" else "false")
            self.rail_lang_vn.style().unpolish(self.rail_lang_vn)
            self.rail_lang_vn.style().polish(self.rail_lang_vn)
        # Update theme toggle title
        if hasattr(self, "rail_theme_btn") and self.rail_theme_btn is not None:
            self.rail_theme_btn.setToolTip(f"Theme: {self.settings.get('theme', 'dark')}")

    def _reload_state_files(self) -> None:
        self.profiles = read_json(PROFILE_FILE, {})
        self.settings = read_json(SETTINGS_FILE, {})
        if self.selected in self.profiles:
            return
        self.selected = next(iter(self.profiles), "")

    def _refresh_live_state(self) -> None:
        """Refresh live state with throttling to reduce CPU usage.
        
        Performance: Skip updates if called too frequently or if no meaningful
        changes occurred since last update. This reduces UI thrashing and CPU usage.
        """
        now = time.time()
        if now - self._last_refresh_time < self._refresh_cooldown:
            return  # Throttle rapid updates
        
        self._last_refresh_time = now
        self._check_auto_eod_update()
        running = tuple(sorted(self._running_profiles()))
        
        # Only update if running count changed
        if self.stat_running and str(len(running)) != self.stat_running["value"].text():
            self.stat_running["value"].setText(str(len(running)))
        
        self._refresh_profile_controls()
        self._refresh_signal_states()
        
        # Only refresh pending page if currently visible
        if self.current_tab == "Pending":
            self._refresh_pending_page()
        if self.current_tab == "Dashboard":
            self._refresh_dashboard_page()
        
        # Only do expensive refreshes when signature changes
        if running != self.last_running_signature:
            self.last_running_signature = running
            self._refresh_profiles()
            self._refresh_profile_page()
        
        self._set_live_status("Live")

    def _set_live_status(self, prefix: str) -> None:
        if self.live_status is None:
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        self.live_status.setText(f"{native_text(prefix)} | {stamp}")
        if hasattr(self, "hero_status") and self.hero_status is not None:
            self.hero_status.setText(f"● {native_text(prefix)}")
            self.hero_status.style().unpolish(self.hero_status)
            self.hero_status.style().polish(self.hero_status)

    def _refresh_profile_controls(self) -> None:
        """Update the rail profile status + start/stop toggle for the selected profile."""
        if self.rail_profile_toggle is None or self.rail_profile_status is None:
            return
        selected = self.selected or ""
        running = bool(selected and selected in self._running_profiles())
        starting = bool(selected and selected in self.starting_profiles)

        if running:
            self.rail_profile_toggle.setText(native_text("Stop selected"))
            self.rail_profile_toggle.setProperty("intent", "danger")
            self.rail_profile_toggle.setEnabled(True)
            self.rail_profile_status.setText(native_text("Running"))
            self.rail_profile_status.setProperty("accent", "green")
        elif starting:
            phase = self.startup_phase.get(selected) or native_text("Starting...")
            self.rail_profile_toggle.setText(native_text("Starting..."))
            self.rail_profile_toggle.setProperty("intent", "positive")
            self.rail_profile_toggle.setEnabled(False)
            self.rail_profile_status.setText(phase)
            self.rail_profile_status.setProperty("accent", "amber")
        else:
            err = self.startup_error.get(selected)
            self.rail_profile_toggle.setText(native_text("Start selected"))
            self.rail_profile_toggle.setProperty("intent", "positive")
            self.rail_profile_toggle.setEnabled(True)
            if err:
                self.rail_profile_status.setText(f"Failed: {err}")
                self.rail_profile_status.setProperty("accent", "muted")
            else:
                self.rail_profile_status.setText(native_text("Stopped"))
                self.rail_profile_status.setProperty("accent", "muted")

        self.rail_profile_toggle.style().unpolish(self.rail_profile_toggle)
        self.rail_profile_toggle.style().polish(self.rail_profile_toggle)
        self.rail_profile_status.style().unpolish(self.rail_profile_status)
        self.rail_profile_status.style().polish(self.rail_profile_status)

    def _ui_after(self, callback: Callable[[], None]) -> None:
        """Run ``callback`` on the Qt GUI thread (or immediately when Qt is unavailable)."""
        if getattr(self, "_is_shut_down", False):
            return
        qt_mod = globals().get("QT")
        window = getattr(self, "window", None)
        if qt_mod is not None and window is not None and hasattr(qt_mod, "QTimer"):
            qt_mod.QTimer.singleShot(0, window, callback)
            return
        callback()

    def _next_startup_op(self, profile: str) -> int:
        """Allocate a unique operation id for this Start and bind it to ``profile``."""
        self._startup_op_seq += 1
        op_id = self._startup_op_seq
        self._startup_ops[profile] = op_id
        return op_id

    def _is_startup_op_current(self, profile: str, op_id: int) -> bool:
        """True only while this op still owns the profile and the shell is alive."""
        if getattr(self, "_is_shut_down", False):
            return False
        return self._startup_ops.get(profile) == op_id

    def _invalidate_startup_op(self, profile: str) -> bool:
        """Drop any in-flight startup ownership for ``profile``. Returns True if one existed."""
        had = profile in self._startup_ops or profile in self.starting_profiles
        self._startup_ops.pop(profile, None)
        self.starting_profiles.discard(profile)
        self.startup_phase.pop(profile, None)
        return had

    def _publish_startup_phase(
        self, profile: str, phase: str, op_id: int | None = None
    ) -> None:
        """Surface one terminal-startup phase in console + rail without wiping STARTING.

        Must only be called on the Qt GUI thread (or from tests without Qt).
        When ``op_id`` is provided, stale operations become no-ops.
        """
        if op_id is not None and not self._is_startup_op_current(profile, op_id):
            return
        if getattr(self, "_is_shut_down", False):
            return
        self.startup_phase[profile] = phase
        self.startup_error.pop(profile, None)
        self._append_console_line(f"[{profile}] {phase}")
        if profile == self.selected:
            self._refresh_profile_controls()

    def _fade_in_page(self, page: Any) -> None:
        """Apply a subtle 150ms opacity fade-in on the newly shown page."""
        if page is None:
            return
        try:
            effect = QT.QGraphicsOpacityEffect(page)
            page.setGraphicsEffect(effect)
            anim = QT.QPropertyAnimation(effect, b"opacity", self.window)
            anim.setDuration(150)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QT.QEasingCurve.Type.OutCubic)
            anim.finished.connect(lambda: page.setGraphicsEffect(None))
            anim.start(QT.QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        except Exception:
            page.setGraphicsEffect(None)

    def switch_tab(self, tab: str) -> None:
        if tab not in self.tab_pages:
            return
        self.current_tab = tab
        if tab in ("VN30 Advisor", "Stock Advisor"):
            self._refresh_stock_advisor_page(force=True)
        elif tab in ("Copy Trading", "Copy"):
            self._refresh_copy_page(force=True)
        elif tab == "Diagnostics":
            self._refresh_diagnostics_page(force=True)
        elif tab == "Profiles":
            self._refresh_profile_page(force=True)
        elif tab in ("Accounts", "Performance", "History", "News"):
            self._refresh_analysis_page(force=True)
        self.stack.setCurrentWidget(self.tab_pages[tab])
        self._refresh_nav()
        self._fade_in_page(self.tab_pages[tab])

    def _refresh_nav(self) -> None:
        for name, nav in self.nav_buttons.items():
            nav.setProperty("active", "true" if name == self.current_tab else "false")
            nav.style().unpolish(nav)
            nav.style().polish(nav)

    def _refresh_combo(self) -> None:
        values = list(self.profiles) or [""]
        current = [self.profile_combo.itemText(i) for i in range(self.profile_combo.count())]
        if current == values and self.profile_combo.currentText() == self.selected:
            return
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(values)
        self.profile_combo.setCurrentText(self.selected)
        self.profile_combo.blockSignals(False)

    def _refresh_profiles(self) -> None:
        container = self.profile_rows_layout.parentWidget()
        if container is not None:
            container.setUpdatesEnabled(False)
        try:
            profiles_sig = tuple(sorted((k, repr(v)) for k, v in self.profiles.items()))
            running_sig = tuple(sorted(self._running_profiles()))
            sig = (profiles_sig, self.selected, running_sig, NATIVE_LANGUAGE)
            if getattr(self, "_last_profiles_sig", None) == sig:
                return
            self._last_profiles_sig = sig

            self._clear_profile_rows()
            running = set(running_sig)
            if not self.profiles:
                self.profile_rows_layout.addWidget(
                    self._guardrail_row("No profiles found", "SETUP", "Copy profiles.example.json to profiles.json, then add MT5 profile settings.", "amber")
                )
                self.profile_rows_layout.addStretch(1)
                return
            for name, cfg in self.profiles.items():
                status = self._profile_status(name, name in running)
                self.profile_rows_layout.addWidget(self._profile_row(name, cfg, status))
            self.profile_rows_layout.addStretch(1)
        finally:
            if container is not None:
                container.setUpdatesEnabled(True)

    def _clear_profile_rows(self) -> None:
        while self.profile_rows_layout.count():
            item = self.profile_rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _profile_row(self, name: str, cfg: dict[str, Any], status: str) -> Any:
        row = QT.QFrame()
        row.setProperty("role", "row")
        row.setProperty("active", "true" if name == self.selected else "false")
        row.setCursor(QT.Qt.CursorShape.PointingHandCursor)
        row.mousePressEvent = lambda _event, n=name: self.select_profile(n)
        layout = QT.QHBoxLayout(row)
        left = QT.QVBoxLayout()
        left.addWidget(label(name))
        left.addWidget(label(str(cfg.get("server") or cfg.get("broker") or "MT5"), role="muted"))
        status_label = label(status, accent="green" if status == "RUNNING" else "red" if status == "ERROR" else "")
        action = button("Stop" if status == "RUNNING" else "Start")
        action.setFixedWidth(88)
        if status == "RUNNING":
            action.setProperty("intent", "danger")
            action.clicked.connect(lambda _checked=False, n=name: self.stop_profile(n))
        else:
            action.setProperty("intent", "positive")
            action.clicked.connect(lambda _checked=False, n=name: self.start_profile(n))
        layout.addLayout(left, 1)
        layout.addWidget(status_label)
        layout.addWidget(action)
        return row

    def _refresh_profile_page(self, force: bool = False) -> None:
        if self.profile_cards_layout is None or self.profile_detail is None:
            return
        if not force and self.current_tab != "Profiles":
            return
        container = self.profile_cards_layout.parentWidget()
        if container is not None:
            container.setUpdatesEnabled(False)
        try:
            while self.profile_cards_layout.count():
                item = self.profile_cards_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            if not self.profiles:
                self.profile_cards_layout.addWidget(
                    self._guardrail_row("No profiles found", "SETUP", "NativeQt keeps real credentials out of the installer. Add profiles.json beside the exe.", "amber")
                )
                self.profile_cards_layout.addStretch(1)
                self.profile_detail.setPlainText(self._profile_detail_text("", {}))
                self._load_profile_editor("", {}, "IDLE")
                if getattr(self, "profiles_count_label", None) is not None:
                    self.profiles_count_label.setText("0 profiles")
                    self._apply_mode_badge(self.profiles_mode_badge, "UNKNOWN")
                    self.profiles_worker_label.setText("Worker —")
                    self.profiles_mt5_label.setText("MT5 —")
                return
            running = set(self._running_profiles())
            for name, cfg in self.profiles.items():
                status = self._profile_status(name, name in running)
                self.profile_cards_layout.addWidget(self._profile_card(name, cfg, status))
            self.profile_cards_layout.addStretch(1)
            cfg = self.profiles.get(self.selected, {})
            status = self._profile_status(self.selected, self.selected in running)
            self.profile_detail.setPlainText(self._profile_detail_text(self.selected, cfg, status))
            self._load_profile_editor(self.selected, cfg, status)
            if getattr(self, "profiles_count_label", None) is not None:
                self.profiles_count_label.setText(f"{len(self.profiles)} profiles")
                self._apply_mode_badge(self.profiles_mode_badge, self._trade_mode_from_cfg(cfg))
                self.profiles_worker_label.setText(
                    f"Worker {status}" if self.selected else "Worker —"
                )
                mt5_path = str(cfg.get("path") or cfg.get("mt5_path") or cfg.get("terminal_path") or "").strip()
                self.profiles_mt5_label.setText("MT5 path set" if mt5_path else "MT5 path unset")
        finally:
            if container is not None:
                container.setUpdatesEnabled(True)

    def _profile_card(self, name: str, cfg: dict[str, Any], status: str) -> Any:
        row = QT.QFrame()
        row.setProperty("role", "row")
        row.setProperty("active", "true" if name == self.selected else "false")
        row.setCursor(QT.Qt.CursorShape.PointingHandCursor)
        row.mousePressEvent = lambda _event, n=name: self.select_profile(n)
        layout = QT.QVBoxLayout(row)
        layout.setContentsMargins(14, 12, 14, 12)
        header = QT.QHBoxLayout()
        header.addWidget(label(name, role="section" if name == self.selected else ""))
        mode = self._trade_mode_from_cfg(cfg)
        mode_lbl = label(mode, role="status")
        mode_lbl.setProperty("mode", mode)
        header.addWidget(mode_lbl)
        header.addStretch(1)
        select = button("Selected" if name == self.selected else "Use", primary=name == self.selected)
        select.setFixedWidth(96)
        select.clicked.connect(lambda _checked=False, n=name: self.select_profile(n))
        header.addWidget(label(status, accent="green" if status == "RUNNING" else "red" if status == "ERROR" else ""))
        header.addWidget(select)
        layout.addLayout(header)
        path_label = label(str(cfg.get("path") or "No terminal path"), role="muted")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)
        badges = QT.QHBoxLayout()
        badges.setSpacing(8)
        for text in (
            native_format("Visible SL/TP {state}", state=yes_no(cfg.get("visible_sltp"))),
            native_format("Copy {role}", role=str(cfg.get("copy_role") or "None")),
            native_format("Kill {state}", state=yes_no(cfg.get("copy_kill_switch"))),
        ):
            badges.addWidget(label(text, role="muted"))
        badges.addStretch(1)
        layout.addLayout(badges)
        return row

    def _profile_detail_text(self, name: str, cfg: dict[str, Any], status: str = "IDLE") -> str:
        if not name or not cfg:
            return native_text("No profile selected")
        profile_fields = [
            ("Profile", name),
            ("Status", status),
            ("Mode", self._trade_mode_from_cfg(cfg)),
            ("Terminal", cfg.get("path") or "—"),
            ("Magic", cfg.get("magic", "—")),
            ("Visible SL/TP", yes_no(cfg.get("visible_sltp"))),
            ("SL / TP", f"{cfg.get('sl', '—')} / {cfg.get('tp', '—')}"),
            ("Gold SL / TP", f"{cfg.get('gold_sl', '—')} / {cfg.get('gold_tp', '—')}"),
        ]
        copy_fields = [
            ("Role", cfg.get("copy_role") or "None"),
            ("Channel", cfg.get("copy_channel") or "—"),
            ("Daily cap", cfg.get("copy_max_daily_trades") or "—"),
            ("Lot cap", cfg.get("copy_max_lot_per_trade") or "—"),
            ("Exposure cap", cfg.get("copy_max_exposure") or "—"),
            ("Kill switch", yes_no(cfg.get("copy_kill_switch"))),
        ]
        secret_fields = [
            ("Telegram token", mask_secret(cfg.get("tele_token"))),
            ("Telegram chat", mask_secret(cfg.get("tele_chat"))),
            ("Admin chat", mask_secret(cfg.get("tele_admin"))),
        ]
        return "\n\n".join(
            (
                self._format_detail_block("PROFILE HEALTH", profile_fields),
                self._format_detail_block("COPY RISK LIMITS", copy_fields),
                self._format_detail_block("MASKED SECRETS", secret_fields),
            )
        )

    def _format_detail_block(self, title: str, fields: list[tuple[str, Any]]) -> str:
        lines = [native_text(title)]
        lines.extend(f"  {native_text(key)}: {native_text(value)}" for key, value in fields)
        return "\n".join(lines)

    def _load_profile_editor(self, name: str, cfg: dict[str, Any], status: str) -> None:
        if self.profile_editor_dirty and self.profile_editor_profile == name:
            return
        title = self.profile_editor_title
        state = self.profile_editor_status
        if title is not None:
            title.setText(name or native_text("No profile selected"))
        if state is not None:
            state.setText(f"{native_text(status)} | profiles.json")
            state.setProperty("accent", "")
            state.style().unpolish(state)
            state.style().polish(state)
        for key, field in self.profile_editor_fields.items():
            field.blockSignals(True)
            value = name if key == "profile_name" else cfg.get(key, "")
            field.setText(str(value or ""))
            field.setCursorPosition(0)
            field.blockSignals(False)
        for key, check in self.profile_editor_checks.items():
            check.blockSignals(True)
            check.setChecked(bool(cfg.get(key)))
            check.blockSignals(False)
        self.profile_editor_profile = name
        self.profile_editor_dirty = False
        self.pending_delete_profile = ""

    def _mark_profile_dirty(self, *_args: Any) -> None:
        self.profile_editor_dirty = True
        self.pending_delete_profile = ""
        if self.profile_editor_status is not None:
            self.profile_editor_status.setText(native_text("Unsaved changes"))

    def _set_profile_editor_status(self, message: str, accent: str = "") -> None:
        if self.profile_editor_status is None:
            return
        self.profile_editor_status.setText(native_text(message))
        self.profile_editor_status.setProperty("accent", accent)
        self.profile_editor_status.style().unpolish(self.profile_editor_status)
        self.profile_editor_status.style().polish(self.profile_editor_status)

    def _collect_profile_editor(self) -> tuple[str, dict[str, Any]]:
        old_name = self.profile_editor_profile or self.selected
        cfg = dict(self.profiles.get(old_name, {}))
        raw_name = self.profile_editor_fields["profile_name"].text()
        new_name = normalize_profile_name(raw_name)
        for _title, key in PROFILE_TEXT_FIELDS:
            if key == "profile_name":
                continue
            cfg[key] = self.profile_editor_fields[key].text()
        for _title, key in PROFILE_BOOL_FIELDS:
            cfg[key] = self.profile_editor_checks[key].isChecked()
        cfg["profile_name"] = new_name
        return new_name, cfg

    def save_profile(self) -> None:
        old_name = self.profile_editor_profile or self.selected
        if not old_name or old_name not in self.profiles:
            self._set_profile_editor_status("Select a profile before saving.", "amber")
            return
        new_name, cfg = self._collect_profile_editor()
        if new_name != old_name and new_name in self.profiles:
            self._set_profile_editor_status(f"Profile '{new_name}' already exists.", "red")
            return
        if self._profile_is_running(old_name) and new_name != old_name:
            self._set_profile_editor_status("Stop this profile before renaming it.", "amber")
            return
        updated = dict(self.profiles)
        if new_name != old_name:
            updated.pop(old_name, None)
        updated[new_name] = cfg
        self._save_profiles(updated, new_name, f"Saved profile: {new_name}")

    def duplicate_profile(self) -> None:
        if not self.selected or self.selected not in self.profiles:
            self._set_profile_editor_status("Select a profile to duplicate.", "amber")
            return
        new_name = unique_profile_name(set(self.profiles), f"{self.selected} Copy")
        cfg = dict(self.profiles[self.selected])
        cfg["profile_name"] = new_name
        updated = dict(self.profiles)
        updated[new_name] = cfg
        self._save_profiles(updated, new_name, f"Duplicated profile: {new_name}")

    def add_profile(self) -> None:
        source = dict(self.profiles.get(self.selected, {}))
        new_name = unique_profile_name(set(self.profiles), "NewProfile")
        source.update(
            {
                "profile_name": new_name,
                "path": source.get("path", ""),
                "magic": source.get("magic", "0"),
                "visible_sltp": bool(source.get("visible_sltp", True)),
            }
        )
        updated = dict(self.profiles)
        updated[new_name] = source
        self._save_profiles(updated, new_name, f"Added profile: {new_name}")

    def delete_profile(self) -> None:
        target = self.selected
        if not target or target not in self.profiles:
            self._set_profile_editor_status("Select a profile to delete.", "amber")
            return
        if self._profile_is_running(target):
            self._set_profile_editor_status("Stop this profile before deleting it.", "amber")
            return
        if self.pending_delete_profile != target:
            self.pending_delete_profile = target
            self._set_profile_editor_status(f"Click Delete again to remove '{target}'.", "red")
            return
        updated = dict(self.profiles)
        updated.pop(target, None)
        next_name = next(iter(updated), "")
        self._save_profiles(updated, next_name, f"Deleted profile: {target}")

    def _save_profiles(self, profiles: dict[str, Any], selected: str, message: str) -> None:
        try:
            write_json_atomic(PROFILE_FILE, profiles)
        except OSError as exc:
            self._set_profile_editor_status(f"Save failed: {exc}", "red")
            return
        self.profiles = profiles
        self.selected = selected
        self.profile_editor_dirty = False
        self.profile_editor_profile = selected
        self.pending_delete_profile = ""
        self.log(message)
        self.refresh()
        self.switch_tab("Profiles")
        self._set_profile_editor_status(message, "green")

    def select_profile(self, name: str) -> None:
        if name not in self.profiles:
            return
        self.selected = name
        self.profile_editor_dirty = False
        self.pending_delete_profile = ""
        self.pending_delete_key = ""
        self.profile_combo.setCurrentText(name)
        self.refresh()

    def _refresh_copy_page(self, force: bool = False) -> None:
        if self.copy_detail is None or self.copy_guardrails_layout is None:
            return
        if not force and self.current_tab not in ("Copy", "Copy Trading"):
            return
        cfg = self.profiles.get(self.selected, {})
        mode = self._trade_mode_from_cfg(cfg)
        running = self._profile_is_running(self.selected) if self.selected else False
        if getattr(self, "copy_mode_badge", None) is not None:
            self._apply_mode_badge(self.copy_mode_badge, mode)
            self.copy_role_label.setText(f"Role {cfg.get('copy_role') or 'None'}")
            self.copy_worker_label.setText("Worker RUNNING" if running else "Worker STOPPED")
            kill_on = bool(cfg.get("copy_kill_switch"))
            self.copy_status_label.setText(
                "Kill switch ON · new entries blocked" if kill_on else "Copy ready · profile-scoped"
            )
        self.copy_detail.setPlainText(self._copy_detail_text(self.selected, cfg))
        while self.copy_guardrails_layout.count():
            item = self.copy_guardrails_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not cfg:
            self.copy_guardrails_layout.addWidget(self._guardrail_row("Profile", "Missing", "Select a profile first.", "red"))
            self.copy_guardrails_layout.addStretch(1)
            return
        self.copy_guardrails_layout.addWidget(
            self._guardrail_row("Exact profile match", "ON", "Telegram commands stay scoped to the selected profile.", "green")
        )
        kill_on = bool(cfg.get("copy_kill_switch"))
        self.copy_guardrails_layout.addWidget(
            self._guardrail_row(
                "Kill switch",
                "ON" if kill_on else "OFF",
                "Blocks all new copy entries when ON.",
                "red" if kill_on else "green",
            )
        )
        self.copy_guardrails_layout.addWidget(
            self._guardrail_row("Max one trade/symbol", yes_no(cfg.get("copy_max_one")), "Blocks duplicate symbol stacking when enabled.", "green")
        )
        self.copy_guardrails_layout.addWidget(
            self._guardrail_row(
                "Daily / lot / exposure caps",
                "ARMED",
                native_format(
                    "{daily} trades/day · {lot} lot/order · {exposure} lot/symbol",
                    daily=cfg.get("copy_max_daily_trades", 20),
                    lot=cfg.get("copy_max_lot_per_trade", 5.0),
                    exposure=cfg.get("copy_max_exposure", 10.0),
                ),
                "green",
            )
        )
        self.copy_guardrails_layout.addWidget(
            self._guardrail_row("Stealth copy", yes_no(cfg.get("copy_stealth")), "Keeps copy execution quiet unless a response is required.", "amber")
        )
        ignored = cfg.get("copy_ignore_list") or "—"
        self.copy_guardrails_layout.addWidget(
            self._guardrail_row("Ignore list", str(ignored), "Symbols listed here are skipped by copy trading.", "")
        )
        self.copy_guardrails_layout.addStretch(1)

    def _copy_detail_text(self, name: str, cfg: dict[str, Any]) -> str:
        if not name or not cfg:
            return native_text("No profile selected")
        status_fields = [
            ("Profile", name),
            ("Status", "KILL SWITCH ON" if cfg.get("copy_kill_switch") else "Ready"),
        ]
        execution_fields = [
            ("Role", cfg.get("copy_role") or "None"),
            ("Channel", cfg.get("copy_channel") or "—"),
            ("Lot mode", cfg.get("copy_lot_mode") or "Fixed"),
            ("Lot value", cfg.get("copy_lot_value") or "—"),
        ]
        safety_fields = [
            ("Max daily trades", cfg.get("copy_max_daily_trades") or "20"),
            ("Max lot/trade", cfg.get("copy_max_lot_per_trade") or "5.0"),
            ("Max exposure/symbol", cfg.get("copy_max_exposure") or "10.0"),
            ("Max one trade/symbol", yes_no(cfg.get("copy_max_one"))),
            ("Stealth", yes_no(cfg.get("copy_stealth"))),
            ("Kill switch", yes_no(cfg.get("copy_kill_switch"))),
            ("Ignore list", cfg.get("copy_ignore_list") or "—"),
        ]
        return "\n\n".join(
            (
                self._format_detail_block("COPY STATUS", status_fields),
                self._format_detail_block("EXECUTION", execution_fields),
                self._format_detail_block("SAFETY LIMITS", safety_fields),
            )
        )

    def _guardrail_row(self, title: str, state: str, description: str, accent: str) -> Any:
        row = QT.QFrame()
        row.setProperty("role", "row")
        layout = QT.QVBoxLayout(row)
        layout.setContentsMargins(14, 12, 14, 12)
        header = QT.QHBoxLayout()
        header.addWidget(label(title))
        header.addStretch(1)
        header.addWidget(label(state, accent=accent))
        layout.addLayout(header)
        desc = label(description, role="muted")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        return row

    def _refresh_pending_page(self, force: bool = False) -> None:
        if self.pending_summary is None or self.pending_items_layout is None:
            return
        files, items = self._pending_state(self.selected)
        sig = (self.selected, tuple(files), tuple(item.get("_pending_identity") for item in items))
        if not force and getattr(self, "_last_pending_signature", None) == sig:
            return
        self._last_pending_signature = sig
        cfg = self.profiles.get(self.selected, {}) if self.selected else {}
        self._apply_mode_badge(getattr(self, "pending_mode_badge", None), self._trade_mode_from_cfg(cfg))
        waiting = sum(1 for item in items if self._is_waiting_status(item))
        done = sum(1 for item in items if str(item.get("status") or "").lower() in PENDING_DONE_STATUSES)
        if getattr(self, "pending_count_badge", None) is not None:
            self.pending_count_badge.setText(f"{len(items)} pending · {waiting} waiting")
        summary = [
            native_text("PENDING CONTROL"),
            native_format("Profile: {profile}", profile=self.selected or "—"),
            native_format("Total tasks: {count}", count=len(items)),
            native_format("Waiting: {count}", count=waiting),
            native_format("Done/closed: {count}", count=done),
            "",
            native_text("SESSION FILES"),
            *[native_format("{name}: {count} item(s)", name=name, count=count) for name, count in files],
        ]
        self.pending_summary.setPlainText("\n".join(summary))
        while self.pending_items_layout.count():
            item = self.pending_items_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not items:
            self.pending_items_layout.addWidget(self._guardrail_row("No scheduled tasks", "CLEAN", "No waiting orders, scheduled closes, or partial tasks.", "green"))
            self.pending_items_layout.addStretch(1)
            return
        for item in items[:30]:
            self.pending_items_layout.addWidget(self._pending_row(item))
        self.pending_items_layout.addStretch(1)

    def _pending_state(self, profile_name: str) -> tuple[list[tuple[str, int]], list[dict[str, Any]]]:
        if not profile_name:
            return [("profile", 0)], []
        files: list[tuple[str, int]] = []
        items: list[dict[str, Any]] = []
        for kind, path, shape in pending_file_specs(ROOT, profile_name):
            default = {} if shape == "dict" else []
            data = read_json(path, default)
            rows = pending_rows(kind, path, data, shape)
            files.append((path.name, len(rows)))
            items.extend(rows)
        return files, items

    def _pending_row(self, item: dict[str, Any]) -> Any:
        row = QT.QFrame()
        row.setProperty("role", "row")
        row.setProperty("active", "true" if self._is_waiting_status(item) else "false")
        layout = QT.QVBoxLayout(row)
        layout.setContentsMargins(14, 12, 14, 12)
        header = QT.QHBoxLayout()
        symbol = item.get("symbol") or item.get("sym") or item.get("ticket") or item.get("id") or "TASK"
        status = str(item.get("status") or "waiting").upper()
        kind = str(item.get("kind") or "task").upper()
        header.addWidget(label(f"{kind} | {symbol}"))
        header.addStretch(1)
        header.addWidget(label(status, accent=self._status_accent(status)))
        copy_btn = button("Copy")
        copy_btn.setMaximumWidth(88)
        copy_btn.clicked.connect(lambda _checked=False, payload=dict(item): self.copy_pending_item(payload))
        delete_btn = button("Delete")
        delete_btn.setMaximumWidth(96)
        delete_btn.setProperty("intent", "danger")
        delete_btn.clicked.connect(lambda _checked=False, payload=dict(item): self.delete_pending_item(payload))
        header.addWidget(copy_btn)
        header.addWidget(delete_btn)
        layout.addLayout(header)
        file_name = Path(str(item.get("_pending_file") or "")).name
        when = " ".join(str(item.get(k) or "") for k in ("date", "time")).strip() or str(item.get("execute_at") or "-")
        if "filter" in item:
            close_filter = item.get("filter") or "all"
            close_ticket = item.get("ticket") or ""
            desc = f"filter={close_filter} | sym {symbol} | {close_ticket or '-'} | {when} | {file_name}"
        else:
            desc = f"{order_type_name(item.get('type'))} | lot {item.get('lot', '-')} | {when} | {file_name}"
        layout.addWidget(label(desc, role="muted"))
        return row

    def copy_pending_item(self, item: dict[str, Any]) -> None:
        """Copy one pending row without UI metadata."""
        text = json.dumps(public_pending_item(item), ensure_ascii=False, indent=2)
        QT.QApplication.clipboard().setText(text)
        self._set_pending_status("Copied pending item.", "green")

    def delete_pending_item(self, item: dict[str, Any]) -> None:
        """Delete one pending row with a two-click guard."""
        delete_key = f"{item.get('_pending_file')}|{item.get('_pending_key', item.get('_pending_index'))}|{item.get('_pending_identity')}"
        if self.pending_delete_key != delete_key:
            self.pending_delete_key = delete_key
            self._set_pending_status("Click Delete again to remove this pending item.", "red")
            return
        path = Path(str(item.get("_pending_file") or ""))
        if not path.name:
            self.pending_delete_key = ""
            self._set_pending_status("Cannot resolve pending file.", "red")
            return
        default = {} if item.get("_pending_shape") == "dict" else []
        try:
            _updated, removed = mutate_pending_file(
                path,
                default,
                lambda data: remove_pending_item_from_data(data, item),
            )
        except OSError as exc:
            self._set_pending_status(f"Delete failed: {exc}", "red")
            return
        if not removed:
            self.pending_delete_key = ""
            self._refresh_pending_page(force=True)
            self._set_pending_status("Pending item was not found on disk.", "amber")
            return
        self.pending_delete_key = ""
        self.log(f"Deleted pending item from {path.name}.")
        self._refresh_pending_page(force=True)
        self._set_pending_status("Pending item deleted.", "green")

    def clear_done_pending(self) -> None:
        """Clear completed list-based pending rows for the selected profile."""
        if not self.selected:
            self._set_pending_status("Select a profile before clearing done tasks.", "amber")
            return
        removed_total = 0
        try:
            for _kind, path, shape in pending_file_specs(ROOT, self.selected):
                if shape != "list":
                    continue
                _updated, removed = mutate_pending_file(path, [], clear_done_pending_data)
                removed_total += removed
        except OSError as exc:
            self._set_pending_status(f"Clear failed: {exc}", "red")
            return
        self.pending_delete_key = ""
        self.log(f"Cleared {removed_total} completed pending item(s).")
        self._refresh_pending_page(force=True)
        accent = "green" if removed_total else "amber"
        self._set_pending_status(f"Cleared {removed_total} completed item(s).", accent)

    def _set_pending_status(self, message: str, accent: str = "muted") -> None:
        if getattr(self, "_is_shut_down", False) or self.pending_action_status is None:
            return
        try:
            self.pending_action_status.setText(native_text(message))
            self.pending_action_status.setProperty("accent", accent)
            self.pending_action_status.style().unpolish(self.pending_action_status)
            self.pending_action_status.style().polish(self.pending_action_status)
        except RuntimeError:
            pass

    def _is_waiting_status(self, item: dict[str, Any]) -> bool:
        status = str(item.get("status") or "waiting").lower()
        return status in {"waiting", "pending", "ready", ""}

    def _status_accent(self, status: str) -> str:
        lower = status.lower()
        if lower in {"waiting", "pending", "ready"}:
            return "green"
        if lower in {"error", "failed", "blocked"}:
            return "red"
        return "amber"

    def _refresh_diagnostics_page(self, force: bool = False) -> None:
        if self.diag_summary is None or self.diag_log is None:
            return
        if not force and self.current_tab != "Diagnostics":
            return
        latest_log = self._latest_log_path()
        raw_log = self._tail_text(latest_log, limit=40000)
        query = self.diag_filter.text() if self.diag_filter is not None else ""
        level = self.diag_level.currentText() if self.diag_level is not None else "ALL"
        visible_log = filter_log_text(raw_log, query, level)
        if raw_log and not visible_log:
            visible_log = "No matching log lines."
        self.last_visible_log_text = visible_log
        visible_line_count = len(visible_log.splitlines()) if visible_log else 0
        artifacts = self._artifact_summary()
        summary = [
            f"Mode: {'frozen exe' if getattr(sys, 'frozen', False) else 'source'}",
            f"Python: {sys.version.split()[0]}",
            f"Root: {ROOT}",
            f"Profiles: {PROFILE_FILE.exists()} ({len(self.profiles)})",
            f"Settings: {SETTINGS_FILE.exists()}",
            f"Selected: {self.selected or '—'}",
            f"Latest log: {latest_log.name if latest_log else '—'}",
            f"Filter: level={level}, query={query or '-'}",
            f"Visible lines: {visible_line_count}",
            "",
            *artifacts,
        ]
        self.last_diagnostics_report = "\n".join(summary)
        self.diag_summary.setPlainText(self.last_diagnostics_report)
        self.diag_log.setPlainText(visible_log if latest_log else native_text("No log file found."))
        if getattr(self, "diag_health_badge", None) is not None:
            if not latest_log:
                self._apply_mode_badge(self.diag_health_badge, "UNAVAILABLE")
            elif level == "ERROR" and visible_line_count:
                self._apply_mode_badge(self.diag_health_badge, "DEGRADED")
            else:
                self._apply_mode_badge(self.diag_health_badge, "READY")
        self._set_diag_status("Diagnostics export is redacted by default.", "muted")

    def copy_diagnostics_report(self) -> None:
        """Copy a safe runtime report without secrets."""
        self._refresh_diagnostics_page(force=True)
        text = self.last_diagnostics_report or "No diagnostics report."
        QT.QApplication.clipboard().setText(text)
        self._set_diag_status("Runtime report copied.", "green")
        self.log("Diagnostics report copied.")

    def copy_visible_log(self) -> None:
        """Copy the currently visible diagnostics log text."""
        text = self.last_visible_log_text or ""
        if not text.strip():
            self._set_diag_status("No visible log lines to copy.", "amber")
            return
        QT.QApplication.clipboard().setText(text)
        self._set_diag_status("Visible log copied.", "green")
        self.log("Visible diagnostics log copied.")

    def clear_diagnostics_display(self) -> None:
        """Clear the log pane without deleting files."""
        self.last_visible_log_text = ""
        if self.diag_log is not None:
            self.diag_log.setPlainText(native_text("Display cleared. Press Refresh to reload logs."))
        self._set_diag_status("Display cleared; log files were not modified.", "amber")

    def export_debug_bundle(self) -> None:
        """Export a redacted debug bundle for support handoff."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = ROOT / "dist" / "debug-bundles" / f"oak_debug_bundle_{timestamp}.zip"
        try:
            payload = build_debug_bundle_bytes(str(ROOT), include_account_raw=False)
            write_bytes_atomic(target, payload)
        except OSError as exc:
            self._set_diag_status(f"Debug bundle export failed: {exc}", "red")
            return
        QT.QApplication.clipboard().setText(str(target))
        self.log(f"Debug bundle exported: {target.name}")
        self.refresh()
        self._set_diag_status(f"Exported redacted bundle: {target.name}", "green")

    def _set_diag_status(self, message: str, accent: str = "muted") -> None:
        if self.diag_status is None:
            return
        self.diag_status.setText(native_text(message))
        self.diag_status.setProperty("accent", accent)
        self.diag_status.style().unpolish(self.diag_status)
        self.diag_status.style().polish(self.diag_status)

    def _stock_advisor_signature(self) -> tuple[Any, ...]:
        db_path = ROOT / "data" / "market.db"
        rec_path = ROOT / "stock_recommendation.json"
        db_stat = (db_path.stat().st_mtime_ns, db_path.stat().st_size) if db_path.is_file() else (0, 0)
        rec_stat = (rec_path.stat().st_mtime_ns, rec_path.stat().st_size) if rec_path.is_file() else (0, 0)
        search_txt = self.stock_search.text().strip() if hasattr(self, "stock_search") and self.stock_search is not None else ""
        return (self.selected, db_stat, rec_stat, search_txt)

    def _refresh_stock_advisor_page(self, force: bool = False) -> None:
        if getattr(self, "stock_result_table", None) is None:
            return
        if not force and self.current_tab not in ("VN30 Advisor", "Stock Advisor"):
            return
        sig = self._stock_advisor_signature()
        if not force and getattr(self, "_last_stock_advisor_signature", None) == sig:
            return
        self._last_stock_advisor_signature = sig
        self._render_advisory_table()
        self._reload_stock_rows()
        self._check_auto_eod_update()

    def _check_auto_eod_update(self) -> None:
        """Auto-trigger EOD update after 15:00 local market close on weekdays."""
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("OAK_DISABLE_AUTO_EOD"):
            return
        now = datetime.now()
        if now.weekday() in (5, 6):  # Weekend
            return
        if now.time() < dt_time(15, 0):  # Before market close
            return
        today_str = now.strftime("%Y-%m-%d")
        if getattr(self, "_last_auto_eod_date", None) == today_str:
            return
        if self.update_eod_data(is_auto=True):
            self._last_auto_eod_date = today_str

    def update_eod_data(self, is_auto: bool = False) -> bool:
        """Run python -m eod_collector update in background to fetch latest EOD prices.

        Returns True if process started successfully, False if already running or failed.
        """
        if getattr(self, "eod_update_process", None) is not None:
            return False
        try:
            process = QT.QProcess(self.window)
            process.setProgram(sys.executable)
            process.setArguments(["-m", "eod_collector", "update"])
            process.setWorkingDirectory(str(ROOT))
            process.setProcessChannelMode(QT.QProcess.ProcessChannelMode.MergedChannels)

            status_msg = native_text("Updating local EOD data...")
            if is_auto:
                status_msg = f"[Auto 15:00+] {status_msg}"
            self._set_stock_status(status_msg, "amber")
            if hasattr(self, "stock_update_eod_btn"):
                try:
                    self.stock_update_eod_btn.setEnabled(False)
                except RuntimeError:
                    pass

            if hasattr(self, "stock_progress_bar") and self.stock_progress_bar is not None:
                try:
                    self.stock_progress_bar.setRange(0, 100)
                    self.stock_progress_bar.setValue(0)
                    self.stock_progress_bar.setFormat("Đang cập nhật dữ liệu EOD (0%)...")
                    self.stock_progress_label.setText("Đang cập nhật dữ liệu EOD (0%)...")
                    self.stock_progress_bar.setVisible(True)
                except RuntimeError:
                    pass

            process.readyReadStandardOutput.connect(lambda p=process: self._read_eod_update_output(p))
            process.finished.connect(lambda code, _status, p=process: self._eod_update_done(code, p, is_auto))
            self.eod_update_process = process
            process.start()
            return True
        except Exception as e:
            self.log(f"[EOD] Failed to launch update process: {e}")
            return False

    def _read_eod_update_output(self, process: Any) -> None:
        if getattr(self, "_is_shut_down", False):
            return
        try:
            data = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        except (RuntimeError, AttributeError):
            return
        for line in data.splitlines():
            clean = line.strip()
            if not clean or not hasattr(self, "stock_progress_bar") or self.stock_progress_bar is None:
                continue
            try:
                # New format: [VPS EOD] N/TOTAL (PCT%) — emitted every 10 symbols
                match_prog = re.search(r"\[VPS EOD\] (\d+)/(\d+) \((\d+)%\)", clean)
                if match_prog:
                    cur = int(match_prog.group(1))
                    tot = int(match_prog.group(2))
                    pct = int(match_prog.group(3))
                    self.stock_progress_bar.setValue(pct)
                    self.stock_progress_bar.setFormat(f"Đang tải EOD VPS: {cur}/{tot} mã ({pct}%)...")
                    self.stock_progress_label.setText(f"Đang tải EOD VPS: {cur}/{tot} mã ({pct}%)...")
                    continue
                # Announce: [VPS EOD] Fetching N symbols for DATE...
                match_total = re.search(r"\[VPS EOD\] Fetching (\d+) symbols", clean)
                if match_total:
                    tot = match_total.group(1)
                    self.stock_progress_bar.setValue(1)
                    self.stock_progress_bar.setFormat(f"Đang kết nối VPS API (0/{tot} mã)...")
                    self.stock_progress_label.setText(f"Đang kết nối VPS API (0/{tot} mã)...")
                    continue
                # Final save confirmation from logger
                if ("Saved" in clean or "saved" in clean) and "records" in clean:
                    match = re.search(r"(\d+) records", clean)
                    if match:
                        cnt = match.group(1)
                        self.stock_progress_bar.setValue(100)
                        self.stock_progress_bar.setFormat(f"Đã cập nhật xong {cnt} bản ghi EOD ✓")
                        self.stock_progress_label.setText(f"Đã cập nhật xong {cnt} bản ghi EOD ✓")
            except RuntimeError:
                # QProcess / progress bar C++ object deleted during shutdown/teardown.
                pass

    def _eod_update_done(self, code: int, process: Any, is_auto: bool) -> None:
        if getattr(self, "eod_update_process", None) is process:
            self.eod_update_process = None
        if getattr(self, "_is_shut_down", False):
            return

        if hasattr(self, "stock_update_eod_btn"):
            try:
                self.stock_update_eod_btn.setEnabled(True)
            except RuntimeError:
                pass

        if code == 0:
            msg = native_text("EOD data updated successfully.")
            try:
                self._set_stock_status(msg, "green")
                if hasattr(self, "stock_progress_bar") and self.stock_progress_bar is not None:
                    self.stock_progress_bar.setValue(100)
                    self.stock_progress_bar.setFormat("Cập nhật EOD hoàn tất ✓ 100%")
                    self.stock_progress_label.setText("Cập nhật EOD hoàn tất ✓ 100%")
            except RuntimeError:
                pass

            try:
                self._reload_stock_rows()
            except Exception as e:
                self.log(f"[EOD] Error reloading stock rows: {e}")

            if is_auto:
                auto_msg = "Cập nhật EOD tự động hoàn tất. Đang tự động chạy bộ lọc cổ phiếu..." if NATIVE_LANGUAGE == "VN" else "Auto EOD completed. Running stock scanner..."
                try:
                    self._set_stock_status(auto_msg, "amber")
                except RuntimeError:
                    pass
                self.log(f"[AUTO 15:00+] {auto_msg}")
                QT.QTimer.singleShot(500, self.run_stock_advisor)
        else:
            err_msg = f"Cập nhật EOD thất bại (mã lỗi {code})" if NATIVE_LANGUAGE == "VN" else f"EOD update failed (code {code})"
            try:
                self._set_stock_status(err_msg, "red")
                if hasattr(self, "stock_progress_bar") and self.stock_progress_bar is not None:
                    self.stock_progress_bar.setFormat("Lỗi cập nhật EOD ✗")
                    self.stock_progress_label.setText("Lỗi cập nhật EOD ✗")
            except RuntimeError:
                pass

    def _stock_settings_from_form(self) -> StockAdvisorDesktopSettings:
        return StockAdvisorDesktopSettings(
            client_id="oak-stock-scanner",
            capital=float(self.settings.get("stock_capital", 90_000_000)),
        )

    def save_stock_advisor_settings(self) -> None:
        """Persist settings to settings.json."""
        try:
            settings = self._stock_settings_from_form()
            self._persist_stock_settings(settings)
        except (StockAdvisorDesktopError, OSError, ValueError, RuntimeError) as error:
            self._set_stock_status(f"Save failed: {error}", "red")
            return
        self._set_stock_status("Advisor settings saved.", "green")

    def _persist_stock_settings(self, settings: StockAdvisorDesktopSettings) -> None:
        next_settings = dict(self.settings)
        next_settings["stock_client_id"] = settings.client_id
        next_settings["stock_capital"] = settings.capital
        write_json_atomic(SETTINGS_FILE, next_settings)
        self.settings = next_settings

    def run_stock_advisor(self) -> None:
        """Validate and run the local EOD read-only advisor."""
        if self.stock_process is not None or self.stock_pending_launch is not None:
            return
        try:
            settings = self._stock_settings_from_form()
            self._persist_stock_settings(settings)
        except (StockAdvisorDesktopError, OSError, ValueError, RuntimeError) as error:
            self._set_stock_status(f"Cannot run advisor: {error}", "red")
            return
        today = datetime.now(timezone(timedelta(hours=7))).date()
        needs_backfill = requires_d1_backfill_file(ROOT / "data" / "market.db", today)
        plan = build_stock_advisor_launch_plan(ROOT, sys.executable, getattr(sys, "frozen", False), settings, needs_backfill)
        self.stock_pending_launch = plan
        self.stock_run_btn.setEnabled(False)
        self._launch_pending_stock_advisor()

    def _launch_pending_stock_advisor(self) -> None:
        if self.stock_pending_launch is None:
            return
        plan = self.stock_pending_launch
        self.stock_pending_launch = None
        process = QT.QProcess(self.window)
        process.setProgram(plan.program)
        process.setArguments(list(plan.arguments))
        process.setWorkingDirectory(str(ROOT))
        process.setProcessEnvironment(self._process_environment())
        process.setProcessChannelMode(QT.QProcess.ProcessChannelMode.MergedChannels)
        if hasattr(self, "stock_progress_bar") and self.stock_progress_bar is not None:
            self.stock_progress_bar.setRange(0, 100)
            self.stock_progress_bar.setValue(0)
            self.stock_progress_bar.setFormat("Đang khởi tạo bộ lọc D1 (0%)...")
            self.stock_progress_label.setText("Đang khởi tạo bộ lọc D1 (0%)...")
            self.stock_progress_bar.setVisible(True)
        process.readyReadStandardOutput.connect(lambda p=process: self._read_stock_advisor_output(p))
        process.finished.connect(lambda code, _status, p=process: self._stock_advisor_done(code, p))
        process.errorOccurred.connect(lambda error, p=process: self._stock_advisor_error(error, p))
        self.stock_process = process
        self.stock_process_log = []
        self._set_stock_status(native_text("Running Local EOD D1 scanner..."), "amber")
        process.start()

    def _read_stock_advisor_output(self, process: Any) -> None:
        data = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            clean = line.strip()
            if clean:
                self.stock_process_log.append(clean)
                match = re.search(r"\[Local EOD(?: D1)?\] (\w+) \((\d+) bars\)", clean)
                if match and hasattr(self, "stock_progress_bar") and self.stock_progress_bar is not None:
                    sym = match.group(1)
                    cur = int(match.group(2))
                    pct = min(99, max(1, cur))
                    self.stock_progress_bar.setValue(pct)
                    self.stock_progress_bar.setFormat(f"Đang đọc D1 {sym} ({cur} bars)...")
                    self.stock_progress_label.setText(f"Đang đọc D1 {sym} ({cur} bars)...")
                    self.stock_progress_bar.setVisible(True)

    def _stock_advisor_done(self, code: int, process: Any) -> None:
        if self.stock_process is process:
            self.stock_process = None
        self.stock_run_btn.setEnabled(True)
        if code == 0:
            if hasattr(self, "stock_progress_bar") and self.stock_progress_bar is not None:
                self.stock_progress_bar.setValue(100)
                self.stock_progress_bar.setFormat("Hoàn tất quét toàn bộ 3 sàn 100%")
                self.stock_progress_label.setText("Hoàn tất quét toàn bộ 3 sàn 100%")
            self._render_advisory_table()
            self._reload_stock_rows()
            pushed = any(line.endswith("Stock advisor: pushed") for line in self.stock_process_log)
            message = "Advisor completed and dashboard updated." if pushed else "Advisor completed locally; dashboard push needs configuration."
            self._set_stock_status(native_text(message), "green" if pushed else "amber")
        else:
            if hasattr(self, "stock_progress_bar") and self.stock_progress_bar is not None:
                self.stock_progress_bar.setFormat("Lỗi chạy bộ lọc ✗")
                self.stock_progress_label.setText("Lỗi chạy bộ lọc ✗")
            fail_msg = f"Bộ lọc thất bại (mã lỗi {code})" if NATIVE_LANGUAGE == "VN" else f"Advisor failed with code {code}"
            self._set_stock_status(fail_msg, "red")
    def _stock_advisor_error(self, error: Any, process: Any) -> None:
        if self.stock_process is process:
            self._set_stock_status(f"Advisor process error: {error}", "red")

    def _render_advisory_table(self) -> None:
        """Populate self.stock_result_table from stock_recommendation.json."""
        if getattr(self, "stock_result_table", None) is None:
            return
        tbl = self.stock_result_table
        if self.stock_process is None:
            payload = read_json(ROOT / "stock_recommendation.json", {})
            rows = advisory_rows_from_payload(payload)
        else:
            rows = []
        tbl.setUpdatesEnabled(False)
        try:
            tbl.setRowCount(len(rows))
            for i, (symbol, direction, score, close, rank) in enumerate(rows):
                tbl.setItem(i, 0, QT.QTableWidgetItem(symbol))
                d_item = QT.QTableWidgetItem(direction)
                if direction == "BUY":
                    d_item.setForeground(QT.QBrush(QT.QColor("#2fa572")))
                else:
                    d_item.setForeground(QT.QBrush(QT.QColor("#ef4444")))
                f = d_item.font()
                f.setBold(True)
                d_item.setFont(f)
                tbl.setItem(i, 1, d_item)
                tbl.setItem(i, 2, QT.QTableWidgetItem(f"{score:.2f}"))
                close_txt = f"{float(close):.2f}" if close is not None else "—"
                tbl.setItem(i, 3, QT.QTableWidgetItem(close_txt))
                rank_txt = f"#{rank}" if rank > 0 else "—"
                tbl.setItem(i, 4, QT.QTableWidgetItem(rank_txt))
            tbl.resizeColumnsToContents()
            # Stretch last column
            header = tbl.horizontalHeader()
            if header is not None and tbl.columnCount() > 4:
                header.setSectionResizeMode(4, QT.QHeaderView.ResizeMode.Stretch)
        finally:
            tbl.setUpdatesEnabled(True)

    def _reload_stock_rows(self) -> None:
        """Full reload from market.db, then render (tab open / after EOD update).

        Performance: DB query only happens here, not on every search keystroke
        (see ``_render_stock_table`` / ``_on_stock_search_changed``).
        """
        if getattr(self, "stock_table", None) is None:
            return
        self._stock_rows = load_stock_rows()
        self._render_stock_table()

    def _render_stock_table(self) -> None:
        """Render self.stock_table from the cached self._stock_rows + search text.

        Performance: filters the in-memory cache (no DB round trip) and batches
        the QTableWidgetItem rebuild behind setUpdatesEnabled to avoid a
        repaint/layout pass per row.
        """
        if getattr(self, "stock_table", None) is None:
            return
        all_rows = self._stock_rows
        text = ""
        if getattr(self, "stock_search", None) is not None:
            text = self.stock_search.text().strip().lower()
        if text:
            shown = [r for r in all_rows if text in str(r.get("symbol", "")).lower()]
        else:
            shown = all_rows
        tbl = self.stock_table
        tbl.setUpdatesEnabled(False)
        try:
            tbl.setRowCount(len(shown))
            for i, r in enumerate(shown):
                tbl.setItem(i, 0, QT.QTableWidgetItem(str(r.get("symbol", ""))))
                tbl.setItem(i, 1, QT.QTableWidgetItem(str(r.get("exchange", ""))))
                for col, key in enumerate(("open", "high", "low", "close"), start=2):
                    val = r.get(key)
                    txt = f"{float(val):.2f}" if val is not None else "—"
                    tbl.setItem(i, col, QT.QTableWidgetItem(txt))
                vol = r.get("volume")
                vol_txt = f"{float(vol) / 1e6:.1f}" if vol is not None else "—"
                tbl.setItem(i, 6, QT.QTableWidgetItem(vol_txt))
            tbl.resizeColumnsToContents()
            header = tbl.horizontalHeader()
            if header is not None and tbl.columnCount() > 6:
                header.setSectionResizeMode(6, QT.QHeaderView.ResizeMode.Stretch)
        finally:
            tbl.setUpdatesEnabled(True)
        if getattr(self, "stock_count", None) is not None:
            self.stock_count.setText(f"{len(shown)} / {len(all_rows)}")

    def _on_stock_search_changed(self, text: str) -> None:
        """Debounce live filtering so fast typing doesn't rebuild the table per keystroke."""
        if self._stock_search_timer is None:
            self._stock_search_timer = QT.QTimer(self.window)
            self._stock_search_timer.setSingleShot(True)
            self._stock_search_timer.timeout.connect(self._render_stock_table)
        self._stock_search_timer.start(200)

    def _set_stock_status(self, message: str, accent: str = "muted") -> None:
        if self.stock_status is None:
            return
        self.stock_status.setText(native_text(message))
        self.stock_status.setProperty("accent", accent)
        self.stock_status.style().unpolish(self.stock_status)
        self.stock_status.style().polish(self.stock_status)

    def _refresh_settings_page(self) -> None:
        if self.settings_about is None:
            return
        self._select_combo_value(self.settings_lang_combo, str(self.settings.get("lang", "EN")).upper())
        self._select_combo_value(self.settings_theme_combo, str(self.settings.get("theme", "dark")).lower())
        self.settings_about.setPlainText(self._settings_about_text())

    def _select_combo_value(self, combo: Any, value: str) -> None:
        if combo is None:
            return
        index = combo.findText(value)
        if index < 0:
            index = 0
        combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def save_native_settings(self) -> None:
        """Persist NativeQt settings and apply the selected theme."""
        lang = self.settings_lang_combo.currentText() if self.settings_lang_combo is not None else "EN"
        theme = self.settings_theme_combo.currentText() if self.settings_theme_combo is not None else "dark"
        language_changed = lang.upper() != NATIVE_LANGUAGE
        next_settings = dict(self.settings)
        next_settings["lang"] = lang
        next_settings["theme"] = theme
        try:
            write_json_atomic(SETTINGS_FILE, next_settings)
        except OSError as exc:
            self._set_settings_status(f"Save failed: {exc}", "red")
            return
        self.settings = next_settings
        set_native_language(lang)
        self.apply_theme()
        if language_changed:
            self._rebuild_translated_ui()
        else:
            self.refresh()
        self.switch_tab("Settings")
        self._set_settings_status("Settings saved and theme applied.", "green")

    def reset_native_theme(self) -> None:
        """Reset only the NativeQt theme to the default dark skin."""
        if self.settings_theme_combo is not None:
            self._select_combo_value(self.settings_theme_combo, "dark")
        self.save_native_settings()

    def set_rail_lang(self, lang: str) -> None:
        """Switch the UI language from the rail segmented switch."""
        lang = str(lang).upper()
        if lang not in ("EN", "VN") or lang == NATIVE_LANGUAGE:
            return
        next_settings = dict(self.settings)
        next_settings["lang"] = lang
        write_json_atomic(SETTINGS_FILE, next_settings)
        self.settings = next_settings
        set_native_language(lang)
        self._rebuild_translated_ui()

    def cycle_rail_theme(self) -> None:
        """Cycle through available themes from the rail theme toggle."""
        order = ("dark", "light", "deep-sea", "contrast")
        current = str(self.settings.get("theme", "dark"))
        next_theme = order[(order.index(current) + 1) % len(order)] if current in order else "dark"
        next_settings = dict(self.settings)
        next_settings["theme"] = next_theme
        write_json_atomic(SETTINGS_FILE, next_settings)
        self.settings = next_settings
        self.apply_theme()
        if self.rail_theme_btn is not None:
            self.rail_theme_btn.setToolTip(f"Theme: {next_theme}")
        if getattr(self, "stat_theme", None) is not None:
            self.stat_theme["value"].setText(str(next_theme))

    # Performance: Cache for compiled QSS to avoid repeated string concatenation
    _QSS_CACHE: dict[str, str] = {}
    
    def apply_theme(self) -> None:
        """Apply the current NativeQt QSS theme to the main window subtree.

        Performance optimization: Cache compiled QSS strings to avoid expensive
        string concatenation on every theme application. Scoped to the window
        instead of the whole QApplication: Qt re-polishes every widget when the
        stylesheet changes, and app-wide re-polish measured ~870ms vs ~150ms
        for the window subtree (offscreen). All shell widgets live inside
        self.window, so styling is identical.
        """
        theme = str(self.settings.get("theme", "dark"))
        
        # Check cache first
        if theme not in self._QSS_CACHE:
            self._QSS_CACHE[theme] = app_qss(theme)
        
        qss = self._QSS_CACHE[theme]
        self.window.setStyleSheet(qss)

    def shutdown(self) -> None:
        """Stop background subprocesses and detach handlers before teardown.

        Prevents RuntimeError("Internal C++ object already deleted") when the
        window is destroyed while an EOD/stock/monitor subprocess still emits
        signals (e.g. the user closes the window during an auto EOD update, or
        a test closes the window). Idempotent; safe to call more than once.
        """
        self._is_shut_down = True
        # Invalidate every in-flight startup so late _ui_after callbacks are no-ops.
        self._startup_ops.clear()
        self.starting_profiles.clear()
        self.startup_phase.clear()
        if self.signal_supervisor is not None:
            try:
                self.signal_supervisor.cleanup()
            except Exception:
                pass

        # Stop profile workers this shell owns before teardown (prevents orphan interpreters).
        owned_profiles = list((getattr(self, "monitor_processes", None) or {}).keys())
        for profile in owned_profiles:
            try:
                self._stop_owned_monitor(profile, wait_ms=2000)
            except Exception:
                pass

        processes: list[Any] = []
        for attr in ("eod_update_process", "stock_process"):
            proc = getattr(self, attr, None)
            if proc is not None:
                processes.append(proc)
                setattr(self, attr, None)
        signal_map = getattr(self, "signal_processes", None) or {}
        for proc in list(signal_map.values()):
            processes.append(proc)
        signal_map.clear()
        for proc in processes:
            try:
                proc.disconnect()
            except (RuntimeError, TypeError, AttributeError):
                pass
            try:
                if proc.state() != QT.QProcess.ProcessState.NotRunning:
                    proc.terminate()
                    if not proc.waitForFinished(2000):
                        proc.kill()
                        proc.waitForFinished(500)
            except (RuntimeError, TypeError, AttributeError):
                pass

    def _set_settings_status(self, message: str, accent: str = "muted") -> None:
        if self.settings_status is None:
            return
        self.settings_status.setText(native_text(message))
        self.settings_status.setProperty("accent", accent)
        self.settings_status.style().unpolish(self.settings_status)
        self.settings_status.style().polish(self.settings_status)

    def _settings_about_text(self) -> str:
        artifacts = "\n".join(self._artifact_summary())
        return "\n".join(
            [
                native_text("OAK Manager NativeQt"),
                native_text("Mode: Qt Widgets + QSS, no WebEngine/Chromium"),
                native_format("Root: {root}", root=ROOT),
                native_format("Profiles: {count}", count=len(self.profiles)),
                native_format("Selected profile: {profile}", profile=self.selected or "-"),
                native_format("Language: {language}", language=self.settings.get("lang", "EN")),
                native_format("Theme: {theme}", theme=self.settings.get("theme", "dark")),
                native_text("License: MIT © 2026 QKP"),
                native_text("Third-party notices: THIRD_PARTY_NOTICES.md"),
                "",
                artifacts,
                "",
                native_text("Shortcuts:"),
                native_text("- Ctrl+1..8: switch tabs."),
                native_text("- Ctrl+R / F5: refresh runtime state."),
                native_text("- Ctrl+S: save Profiles or Settings."),
                native_text("- Esc: clear delete confirmation guards."),
                "",
                native_text("Cleanup policy:"),
                native_text("- Keep source, docs, profiles examples, installers, and scripts."),
                native_text("- Ignore runtime state: trades_*.json, waiting_*.json, locks, logs, caches."),
                native_text("- Do not delete real trade/runtime state unless explicitly confirmed."),
            ]
        )

    def open_app_folder(self) -> None:
        """Open the current runtime folder."""
        self._open_folder(ROOT)

    def open_log_folder(self) -> None:
        """Open the log folder, or the app folder when no log folder exists."""
        folder = ROOT / "logs"
        self._open_folder(folder if folder.exists() else ROOT)

    def _open_folder(self, folder: Path) -> None:
        try:
            os.startfile(str(folder))  # type: ignore[attr-defined]
        except OSError as exc:
            self.log(f"Cannot open folder: {exc}")

    def _artifact_summary(self) -> list[str]:
        dist = ROOT / "dist"
        installer = dist / f"OAK MANAGER NativeQt_{APP_VERSION}_Installer.exe"
        archive = dist / "native-qt" / f"OAK MANAGER NativeQt_{APP_VERSION}_window-unpack.zip"
        items = [native_text("Artifacts:")]
        for path in (installer, archive):
            status = self._format_size(path) if path.exists() else native_text("missing")
            items.append(f"- {path.name}: {status}")
        return items

    def _format_size(self, path: Path) -> str:
        return f"{path.stat().st_size / (1024 * 1024):.1f} MB"

    def _latest_log_path(self) -> Path | None:
        candidates: list[Path] = []
        for folder in (ROOT, ROOT / "logs"):
            if folder.exists():
                candidates.extend(folder.glob("*.log"))
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)

    def _tail_text(self, path: Path | None, limit: int = 6000) -> str:
        if path is None or not path.exists():
            return ""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"Cannot read log: {exc}"
        return text[-limit:]

    def _running_profiles(self) -> list[str]:
        return [name for name, proc in self.monitor_processes.items() if proc.state() != QT.NotRunning]

    def _profile_status(self, name: str, running: bool | None = None) -> str:
        """Show a recent launcher error instead of collapsing it into IDLE."""
        active = self._profile_is_running(name) if running is None else running
        if active:
            return "RUNNING"
        if name in self.starting_profiles:
            return "STARTING"
        try:
            from repositories.sqlite_store import SQLiteStore
            store = SQLiteStore()
            heartbeat = store.get_heartbeat(name)
            store.close()
            if heartbeat and heartbeat.get("state") == "error" and heartbeat.get("last_error"):
                last_seen = datetime.fromisoformat(str(heartbeat.get("last_seen", "")).replace("Z", "+00:00"))
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - last_seen).total_seconds() <= 300:
                    return "ERROR"
        except Exception:
            pass
        return "IDLE"

    def _profile_is_running(self, profile: str) -> bool:
        proc = self.monitor_processes.get(profile)
        return bool(proc and proc.state() != QT.NotRunning)

    def log(self, message: str) -> None:
        self._append_console_line(message)
        self._refresh_live_state()

    def _toggle_selected_profile(self) -> None:
        """Start or stop the selected profile from the rail (single toggle button)."""
        if not self.selected or self.selected not in self.profiles:
            self.log("Select a valid profile first.")
            return
        if self.selected in self._running_profiles():
            self.stop_selected()
        else:
            self.start_selected()

    def start_selected(self) -> None:
        self.start_profile(self.selected)

    def start_profile(self, profile: str) -> None:
        if not profile or profile not in self.profiles:
            self.log("Select a valid profile first.")
            return
        if self._profile_is_running(profile):
            self.log(f"{profile} is already running.")
            return
        if profile in self.starting_profiles:
            self.log(f"Startup already in progress for {profile}.")
            return

        # Claim the slot + allocate operation identity on the GUI thread first.
        op_id = self._next_startup_op(profile)
        self.starting_profiles.add(profile)
        self.startup_error.pop(profile, None)
        self._publish_startup_phase(profile, "Starting profile...", op_id)

        # Snapshot config for the worker thread (no shared mutable profile dict writes).
        prof_config = dict(self.profiles.get(profile, {}) or {})

        def _status_from_worker(msg: str) -> None:
            # status_callback may fire off the GUI thread — marshal UI updates.
            self._ui_after(
                lambda p=profile, m=msg, oid=op_id: self._publish_startup_phase(p, m, oid)
            )

        def _terminal_work() -> None:
            from services.mt5_terminal_service import ensure_mt5_profile_connected

            try:
                launch = ensure_mt5_profile_connected(
                    prof_config, status_callback=_status_from_worker
                )
            except Exception as error:
                self._ui_after(
                    lambda p=profile, e=error, oid=op_id: self._finish_terminal_startup(
                        p, None, e, oid
                    )
                )
                return
            self._ui_after(
                lambda p=profile, result=launch, oid=op_id: self._finish_terminal_startup(
                    p, result, None, oid
                )
            )

        threading.Thread(
            target=_terminal_work,
            name=f"mt5-start-{profile}",
            daemon=True,
        ).start()

    def _finish_terminal_startup(
        self,
        profile: str,
        launch: Any,
        error: BaseException | None,
        op_id: int | None = None,
    ) -> None:
        """Apply terminal-ensure outcome on the GUI thread; launch worker only on success.

        When ``op_id`` is set, a mismatch means this startup was superseded (Stop / new Start
        / teardown). Stale completions must not mutate state or launch a worker.
        """
        if op_id is not None and not self._is_startup_op_current(profile, op_id):
            return
        if getattr(self, "_is_shut_down", False):
            self._startup_ops.pop(profile, None)
            self.starting_profiles.discard(profile)
            self.startup_phase.pop(profile, None)
            return

        # Claim completion: drop token so any later status from this op is ignored.
        self._startup_ops.pop(profile, None)

        if error is not None:
            self.starting_profiles.discard(profile)
            self.startup_phase.pop(profile, None)
            self.startup_error[profile] = str(error)
            self.log(f"❌ Failed to start {profile}: {error}")
            self._refresh_profile_controls()
            return

        if launch is None or not getattr(launch, "ok", False):
            self.starting_profiles.discard(profile)
            self.startup_phase.pop(profile, None)
            reason = (
                getattr(launch, "failure_code", None)
                or getattr(launch, "message", None)
                or "Unknown error"
            )
            detail = (
                getattr(launch, "message", None)
                or getattr(launch, "failure_code", None)
                or "Unknown error"
            )
            self.startup_error[profile] = str(reason)
            self.log(f"❌ Failed to start {profile}: {detail}")
            self._refresh_profile_controls()
            return

        self._publish_startup_phase(profile, "MT5 terminal ready")
        self._launch_worker(profile)

    def _launch_worker(self, profile: str) -> None:
        proc = QT.QProcess(self.window)
        proc.setProgram(sys.executable)
        if getattr(sys, "frozen", False):
            proc.setArguments(["--worker", "--profile", profile])
        else:
            proc.setArguments([str(APP_SCRIPT), "--worker", "--profile", profile])
        proc.setWorkingDirectory(str(ROOT))
        proc.setProcessEnvironment(self._process_environment())
        proc.setProcessChannelMode(QT.QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(lambda p=proc, n=profile: self._read_output(n, p))
        proc.started.connect(lambda p=proc, n=profile: self._worker_started(n, p))
        proc.finished.connect(lambda code, _status, p=proc, n=profile: self._worker_done(n, code, p))
        proc.errorOccurred.connect(lambda error, n=profile: self._worker_error(n, error))
        self.monitor_processes[profile] = proc
        proc.start()

    def _read_output(self, profile: str, proc: Any) -> None:
        data = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.strip():
                self._append_console_line(f"[{profile}] {line.strip()}")

    def _worker_started(self, profile: str, proc: Any) -> None:
        self.starting_profiles.discard(profile)
        self.startup_phase.pop(profile, None)
        self.startup_error.pop(profile, None)
        self.log(f"Profile {profile} running (PID {proc.processId()})")
        self._refresh_profile_controls()

    def _worker_done(self, profile: str, code: int, proc: Any) -> None:
        self.starting_profiles.discard(profile)
        self.startup_phase.pop(profile, None)
        if self.monitor_processes.get(profile) is proc:
            self.monitor_processes.pop(profile, None)
        # QProcess.kill()/TerminateProcess skips worker ``finally``; reconcile lock here.
        if reconcile_worker_lock_file(profile):
            self.log(f"Cleared stale worker lock for {profile}")
        if code:
            self.startup_error[profile] = f"exit {code}"
            self.log(f"Monitor error: {profile} (code {code}); press Start to retry")
        else:
            self.log(f"Monitor stopped: {profile} (code {code})")
        self._refresh_profile_controls()

    def _worker_error(self, profile: str, error: Any) -> None:
        self.starting_profiles.discard(profile)
        self.startup_phase.pop(profile, None)
        self.startup_error[profile] = str(error)
        self.log(f"Monitor error on {profile}: {error}")
        self._refresh_profile_controls()

    def stop_selected(self) -> None:
        self.stop_profile(self.selected)

    def _stop_owned_monitor(self, profile: str, *, wait_ms: int = 2500) -> None:
        """Stop a worker QProcess this shell owns and any matching lock-holder interpreter.

        Ownership gate: only profiles present in ``monitor_processes`` are stopped here.
        Never kills unrelated MT5 terminals or foreign-shell workers.
        """
        proc = (getattr(self, "monitor_processes", None) or {}).get(profile)
        if proc is not None:
            try:
                proc.disconnect()
            except (RuntimeError, TypeError, AttributeError):
                pass
            try:
                if proc.state() != QT.NotRunning:
                    proc.terminate()
                    finished = False
                    try:
                        finished = bool(proc.waitForFinished(int(wait_ms)))
                    except (RuntimeError, TypeError, AttributeError):
                        finished = False
                    if not finished:
                        try:
                            if proc.state() != QT.NotRunning:
                                proc.kill()
                                proc.waitForFinished(500)
                        except (RuntimeError, TypeError, AttributeError):
                            pass
            except (RuntimeError, TypeError, AttributeError):
                pass
            mapping = getattr(self, "monitor_processes", None) or {}
            if mapping.get(profile) is proc:
                mapping.pop(profile, None)

        # QProcess often tracks only the pythonw launcher; the interpreter may still hold the lock.
        holder = worker_lock_holder_pid(profile)
        if holder and is_project_profile_worker_pid(holder, profile):
            force_kill_pid(holder)
            # Brief settle so tasklist / lock checks see the death.
            try:
                time.sleep(0.15)
            except Exception:
                pass

        if reconcile_worker_lock_file(profile):
            self.log(f"Cleared stale worker lock for {profile}")

    def stop_profile(self, profile: str) -> None:
        # Invalidate any in-flight startup first so a late ensure cannot launch a worker.
        cancelled_startup = self._invalidate_startup_op(profile)
        if cancelled_startup:
            self.startup_error.pop(profile, None)
            self.log(f"Cancelled startup for {profile}")
            self._refresh_profile_controls()

        proc = self.monitor_processes.get(profile)
        if not proc or proc.state() == QT.NotRunning:
            # Recover orphan locks left by a prior force-kill (no QProcess handle).
            if reconcile_worker_lock_file(profile):
                self.log(f"Cleared stale worker lock for {profile}")
            elif not cancelled_startup:
                self.log(f"No live monitor for {profile or 'selected profile'}.")
            return

        self._stop_owned_monitor(profile, wait_ms=2500)
        self.log(f"Stopping monitor: {profile}")
        self._refresh_profile_controls()

    def _append_console_line(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.console.append(f"[{stamp}] {message}")
        cursor = self.console.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.console.setTextCursor(cursor)

    def open_classic(self) -> None:
        QT.QProcess.startDetached(sys.executable, [str(APP_SCRIPT)], str(ROOT))
        self.log("Classic CTk UI launched.")

    def start_all_signals(self) -> None:
        keys = [key for key, _name, _color in get_visible_signal_defs()]
        for index, key in enumerate(keys):
            QT.QTimer.singleShot(index * 250, lambda k=key: self.start_signal(k))

    def stop_all_signals(self) -> None:
        for key, _name, _color in get_visible_signal_defs():
            self.stop_signal(key)

    def clear_signal_logs(self) -> None:
        for card in self.signal_cards.values():
            card["console"].clear()

    def copy_signal_log(self, key: str) -> None:
        card = self.signal_cards.get(key)
        if not card:
            return
        text = card["console"].toPlainText() or "No signal log."
        QT.QApplication.clipboard().setText(text)
        self._append_signal_log(key, "Console copied.")

    def _refresh_signal_states(self) -> None:
        infos = getattr(self, "_signal_supervisor_infos", {})
        for key, _name, _color in get_visible_signal_defs():
            proc = infos.get(key, {}).get("proc")
            running = bool(proc and proc.poll() is None)
            pid = proc.pid if running else None
            self._set_signal_running(key, running, pid)
        self._refresh_signal_summary()

    def _refresh_signal_summary(self) -> None:
        if self.signal_summary is None:
            return
        visible_defs = get_visible_signal_defs()
        visible_keys = {key for key, _name, _color in visible_defs}
        infos = getattr(self, "_signal_supervisor_infos", {})
        running = sum(
            1
            for key in visible_keys
            if (proc := infos.get(key, {}).get("proc")) is not None and proc.poll() is None
        )
        self.signal_summary.setText(native_format("{running}/{total} running", running=running, total=len(visible_defs)))
        if getattr(self, "signal_fresh_label", None) is not None:
            self.signal_fresh_label.setText(
                native_format("{running} active · {total} feeds", running=running, total=len(visible_defs))
            )

    def start_signal(self, key: str) -> None:
        card = self.signal_cards.get(key)
        if not card or self.signal_supervisor is None:
            return
        card["console"].clear()
        profile = self.selected if key == "signal_bot" else ""
        self.signal_supervisor.start_signal_process(key, profile)

    def _process_environment(self) -> Any:
        env = QT.QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUNBUFFERED", "1")
        return env

    def stop_signal(self, key: str) -> None:
        if self.signal_supervisor is None:
            return
        self.signal_supervisor.stop_signal_process(key)

    def _read_signal_output(self, key: str, proc: Any) -> None:
        data = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            clean = line.strip()
            if clean and not self._is_noise_line(clean):
                self._append_signal_log(key, clean)

    def _signal_done(self, key: str, code: int, proc: Any) -> None:
        if self.signal_processes.get(key) is proc:
            self.signal_processes.pop(key, None)
        self._append_signal_log(key, f"Exited with code {code}.")
        self._set_signal_running(key, False)

    def _signal_error(self, key: str, error: Any, proc: Any) -> None:
        if self.signal_processes.get(key) is proc:
            self.signal_processes.pop(key, None)
        self._append_signal_log(key, f"Process error: {error}")
        self._set_signal_running(key, False)
    def _set_signal_running(
        self,
        key: str,
        running: bool,
        pid: int | None = None,
        status: str | None = None,
        preserve_controls: bool = False,
    ) -> None:
        card = self.signal_cards.get(key)
        if not card:
            return
        label = native_text(status) if status else native_text("Running" if running else "Stopped")
        card["status"].setText(label)
        card["status"].setProperty("accent", "green" if running else "")
        degraded = status in {"Blocked", "Degraded"}
        card["dot"].setProperty("accent", "green" if running else "amber" if degraded else "red")
        card["frame"].setProperty("state", "running" if running else "degraded" if degraded else "stopped")
        if not preserve_controls:
            card["pid"].setText(f"PID: {pid}" if running and pid else "PID: ---")
            card["start"].setEnabled(not running)
            card["stop"].setEnabled(running)
        for widget_name in ("frame", "dot", "status", "start", "stop", "pid"):
            widget = card[widget_name]
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self._refresh_signal_summary()

    def _append_signal_log(self, key: str, line: str) -> None:
        card = self.signal_cards.get(key)
        if not card:
            return
        console = card["console"]
        console.append(line)
        cursor = console.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        console.setTextCursor(cursor)

    def _is_noise_line(self, line: str) -> bool:
        lower = line.lower()
        return any(fragment in lower for fragment in CONSOLE_NOISE)


def screenshot_arg(argv: list[str]) -> str:
    """Return optional screenshot path from CLI args."""
    if "--screenshot" not in argv:
        return ""
    index = argv.index("--screenshot")
    if index + 1 >= len(argv):
        return ""
    return argv[index + 1]


def tab_arg(argv: list[str]) -> str:
    """Return optional initial tab from CLI args."""
    if "--tab" not in argv:
        return ""
    index = argv.index("--tab")
    if index + 1 >= len(argv):
        return ""
    return argv[index + 1]


def profile_arg(argv: list[str]) -> str | None:
    """Return optional profile value from CLI args."""
    if "--profile" not in argv:
        return None
    index = argv.index("--profile")
    if index + 1 >= len(argv):
        return None
    return argv[index + 1]


def _pid_is_running(pid: int) -> bool:
    """Return whether a Windows process id is still alive."""
    try:
        result = os.popen(f'tasklist /FI "PID eq {pid}" /NH').read().lower()
    except OSError:
        return False
    return str(pid) in result


def worker_lock_path(profile_name: str) -> Path:
    """Filesystem path for the single-instance worker lock of ``profile_name``."""
    safe = re.sub(r"[^\w\-]", "_", profile_name or "unknown")
    return ROOT / f"worker_{safe}.lock"


def reconcile_worker_lock_file(profile_name: str) -> bool:
    """Remove ``worker_{profile}.lock`` only when it does not protect a live process.

    Used after NativeQt QProcess stop/kill: forced TerminateProcess skips the
    worker's Python ``finally`` / ``_release_worker_lock``. Idempotent.
    Never deletes a lock whose recorded PID is still a running process.
    """
    lock_path = worker_lock_path(profile_name)
    if not lock_path.exists():
        return False
    try:
        raw = (lock_path.read_text(encoding="utf-8") or "").strip()
        old_pid = int(raw or "0")
    except (OSError, ValueError):
        old_pid = 0
    if old_pid and _pid_is_running(old_pid):
        return False
    try:
        lock_path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def worker_lock_holder_pid(profile_name: str) -> int | None:
    """Return the PID recorded in ``worker_{profile}.lock``, if any."""
    lock_path = worker_lock_path(profile_name)
    if not lock_path.exists():
        return None
    try:
        raw = (lock_path.read_text(encoding="utf-8") or "").strip()
        pid = int(raw or "0")
        return pid or None
    except (OSError, ValueError):
        return None


def is_project_profile_worker_pid(pid: int, profile_name: str) -> bool:
    """True when *pid* is a live project worker for *profile_name* (command-line match)."""
    if not pid or not _pid_is_running(pid):
        return False
    try:
        if os.name == "nt":
            import subprocess as _sp

            r = _sp.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-CimInstance Win32_Process -Filter \"ProcessId={int(pid)}\").CommandLine",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=_sp.CREATE_NO_WINDOW if hasattr(_sp, "CREATE_NO_WINDOW") else 0,
            )
            cmd = (r.stdout or "").strip()
        else:
            cmd = Path(f"/proc/{pid}/cmdline").read_text(errors="replace").replace("\x00", " ")
    except Exception:
        return False
    if not cmd:
        return False
    if "OAK_Hidden_SLTP_Manager" not in cmd and "--worker" not in cmd:
        return False
    # Require exact profile token to avoid Vantage matching VantageDemo.
    return bool(re.search(rf"--profile\s+{re.escape(profile_name)}(?:\s|$)", cmd))


def force_kill_pid(pid: int) -> bool:
    """Best-effort terminate a single PID (Windows taskkill /F)."""
    if not pid:
        return False
    try:
        if os.name == "nt":
            import subprocess as _sp

            r = _sp.run(
                ["taskkill", "/F", "/PID", str(int(pid))],
                capture_output=True,
                text=True,
                timeout=8,
                creationflags=_sp.CREATE_NO_WINDOW if hasattr(_sp, "CREATE_NO_WINDOW") else 0,
            )
            return r.returncode == 0 or not _pid_is_running(pid)
        os.kill(int(pid), 9)
        return True
    except Exception:
        return False


def _worker_lock(profile_name: str) -> Path | None:
    """Create a best-effort single-instance worker lock."""
    lock_path = worker_lock_path(profile_name)
    if lock_path.exists():
        try:
            old_pid = int((lock_path.read_text(encoding="utf-8") or "0").strip())
        except (OSError, ValueError):
            old_pid = 0
        if old_pid and _pid_is_running(old_pid):
            print(f"EXIT: worker '{profile_name}' already running (PID {old_pid}).", flush=True)
            return None
    lock_path.write_text(str(os.getpid()), encoding="utf-8")
    return lock_path


def _release_worker_lock(lock_path: Path | None) -> None:
    """Release a NativeQt worker lock if owned by this process."""
    if not lock_path or not lock_path.exists():
        return
    try:
        if lock_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
            lock_path.unlink()
    except OSError:
        return


def run_monitor_worker(profile_name: str | None) -> None:
    """Run a profile monitor without importing the classic CTk app."""
    if not profile_name:
        print("Error: --profile is required for worker mode.", flush=True)
        return
    profiles = read_json(PROFILE_FILE, {})
    config = dict(profiles.get(profile_name) or {})
    if not config:
        print(f"Error: Profile '{profile_name}' not found.", flush=True)
        return
    lock_path = _worker_lock(profile_name)
    if lock_path is None:
        return
    try:
        from domain.monitor_worker import MonitorWorker

        config["profile_name"] = profile_name
        stop_event = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
        signal.signal(signal.SIGINT, lambda *_: stop_event.set())
        log = lambda msg: print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)
        worker = MonitorWorker(config, log, stop_event)
        worker.start()
        while worker.is_alive() and not stop_event.is_set():
            time.sleep(0.5)
    finally:
        _release_worker_lock(lock_path)


def run_embedded_worker(argv: list[str]) -> int | None:
    """Run an embedded worker mode when a frozen exe launches itself."""
    if "--worker" in argv:
        run_monitor_worker(profile_arg(argv))
        return 0
    if "--signal-bot" in argv:
        import mt5_signal_bot

        if "--audit-service" in argv:
            mt5_signal_bot.run_audit_service(profile_name=profile_arg(argv))
        else:
            mt5_signal_bot.main(profile_name=profile_arg(argv))
        return 0
    if "--mimo-bot" in argv:
        runpy.run_module("mimo_bot", run_name="__main__")
        return 0
    if "--mimo-worker" in argv:
        import mimo_worker

        mimo_worker.main()
        return 0
    if "--factcheck-worker" in argv:
        import factcheck_worker

        factcheck_worker.main()
        return 0
    if "--stock-advisor" in argv:
        from vn_stock_advisor import main as advisor_main

        index = argv.index("--stock-advisor")
        return advisor_main(argv[index + 1 :])
    return None


def main() -> int:
    """Run the native Qt shell."""
    embedded_result = run_embedded_worker(sys.argv)
    if embedded_result is not None:
        return embedded_result
    started_at = time.perf_counter()
    global QT
    qt, error = load_qt()
    if qt is None:
        print("PySide6 is not installed. Run: pip install -r requirements_qt.txt", file=sys.stderr)
        print(error, file=sys.stderr)
        return 1
    QT = qt
    qt_loaded_at = time.perf_counter()
    app = QT.QApplication(sys.argv)
    apply_window_icon(app)
    app.setStyleSheet(app_qss())
    app_ready_at = time.perf_counter()

    def ready_callback(ok: bool) -> None:
        if "--benchmark" not in sys.argv:
            return
        first_paint_at = time.perf_counter()
        payload = {
            "qt_import_ms": round((qt_loaded_at - started_at) * 1000),
            "app_create_ms": round((app_ready_at - qt_loaded_at) * 1000),
            "first_paint_ms": round((first_paint_at - started_at) * 1000),
            "ok": ok,
        }
        print(json.dumps(payload, ensure_ascii=False), flush=True)
        QT.QTimer.singleShot(80, app.quit)

    shell = NativeShell(ready_callback)
    app.aboutToQuit.connect(shell.shutdown)
    initial_tab = tab_arg(sys.argv)
    if initial_tab:
        shell.switch_tab(initial_tab)
    shell.window.show()
    screenshot_path = screenshot_arg(sys.argv)
    if screenshot_path:
        QT.QTimer.singleShot(700, lambda: shell.window.grab().save(screenshot_path))
        QT.QTimer.singleShot(900, app.quit)
    if "--smoke" in sys.argv:
        QT.QTimer.singleShot(800, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
