# -*- coding: utf-8 -*-
"""Native Qt Widgets/QSS shell for OAK Manager.

This launcher avoids Qt WebEngine/Chromium so the future installer can stay
much smaller than the premium WebView experiment.
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
    StockAdvisorDesktopErrorCode,
    StockAdvisorDesktopSettings,
    StockAdvisorLaunchPlan,
    build_stock_advisor_launch_plan,
    load_ssi_desktop_credentials,
    render_stock_advisory,
    requires_h4_backfill_file,
    save_ssi_desktop_credentials,
)
from domain.constants import VERSION as APP_VERSION
from utils import UnsupportedFrozenProcessError, build_signal_process_cmd


SOURCE_ROOT = Path(__file__).resolve().parent


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


SIGNAL_DEFS = (
    ("signal_bot", "MT5 Signal Bot", "#2fa572"),
    ("mt_server", "MT4-MT5 Server", "#1f538d"),
    ("mimo_bot", "MiMo Telegram Bot", "#b33dd4"),
    ("mimo_worker", "MiMo Worker", "#d4a03d"),
    ("factcheck_worker", "Fact Check Worker", "#00bfa5"),
)
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
NATIVE_TEXT = {
    "EN": {},
    "VN": {
        "Dashboard": "Bảng điều khiển",
        "Signals": "Tín hiệu",
        "VN30 Advisor": "Bộ lọc Cổ phiếu",
        "Profiles": "Hồ sơ",
        "Copy": "Sao chép",
        "Pending": "Chờ xử lý",
        "Diagnostics": "Chẩn đoán",
        "Settings": "Cài đặt",
        "ONE-CLICK STOCK FILTER": "BỘ LỌC CỔ PHIẾU BẰNG LOCAL EOD",
        "LOCAL EOD MARKET DATA": "DỮ LIỆU THỊ TRƯỜNG LOCAL EOD",
        "SSI Client ID": "SSI Client ID",
        "SSI API key": "SSI API key",
        "SSI API secret": "SSI API secret",
        "Deployable capital": "Vốn khả dụng (VND)",
        "Hurdle (bps)": "Chi phí + biên an toàn (bps)",
        "Save SSI credentials": "Lưu thông tin SSI",
        "Update EOD Data (15:00+)": "Cập nhật dữ liệu EOD (15h00+)",
        "Run advisor": "Chạy bộ lọc Cổ phiếu",
        "Run VN30 Advisor": "Chạy bộ lọc Cổ phiếu",
        "ADVISORY RESULT": "KẾT QUẢ KHUYẾN NGHỊ",
        "Credentials are stored in Windows Credential Manager.": "Thông tin SSI được lưu trong Windows Credential Manager.",
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
        "Enter SSI credentials once, then press Run advisor.": "Nhập thông tin SSI một lần, sau đó nhấn Chạy bộ lọc.",
        "SSI credentials saved securely.": "Đã lưu thông tin SSI an toàn.",
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
        "TRADING COMMAND CENTER": "TRUNG TÂM ĐIỀU HÀNH GIAO DỊCH",
        "Native Qt/QSS shell · no WebEngine": "Native Qt/QSS · không WebEngine",
        "Running": "Đang chạy",
        "Stopped": "Đã dừng",
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
        "Live": "Đang theo dõi",
        "No save target": "Không có nội dung để lưu",
        "Delete guard cleared.": "Đã hủy xác nhận xóa.",
        "Unsaved changes": "Thay đổi chưa lưu",
        "No log file found.": "Không tìm thấy file log.",
        "Display cleared. Press Refresh to reload logs.": "Đã xóa hiển thị. Nhấn Làm mới để tải lại log.",
        "Selected profile: {profile} · Native Qt/QSS, no Chromium": "Hồ sơ đang chọn: {profile} · Native Qt/QSS, không Chromium",
        "{running}/{total} running": "{running}/{total} đang chạy",
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
    """Read JSON and fall back safely."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json_atomic(path: Path, payload: Any) -> None:
    """Write JSON through the shared unique-temp atomic writer."""
    save_json(path, payload)


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


def write_bytes_atomic(path: Path, payload: bytes) -> None:
    """Write bytes through a same-folder temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_bytes(payload)
    temp_path.replace(path)


def load_qt() -> tuple[SimpleNamespace | None, str]:
    """Import only QtCore/QtGui/QtWidgets, never QtWebEngine."""
    try:
        from PySide6.QtCore import QProcess, QProcessEnvironment, QSize, Qt, QTimer
        from PySide6.QtGui import QFont, QIcon, QKeySequence, QShortcut
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QFrame,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QProgressBar,
            QPushButton,
            QScrollArea,
            QStackedWidget,
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
    """Return the native Qt stylesheet."""
    base = """
    QMainWindow{background:#060908}
    QWidget{font-family:"Segoe UI";font-size:14px;color:#f4f7f5}
    QWidget#StockAdvisorControls{background:#090d0c}
    #Root{background:qradialgradient(cx:.08,cy:.02,radius:1,fx:.08,fy:.02,stop:0 rgba(0,201,145,32),stop:.42 #060908,stop:1 #060908)}
    QFrame[role="panel"]{background:rgba(13,18,16,224);border:1px solid #25312c;border-radius:22px}
    QFrame[role="row"]{background:#111816;border:1px solid #26322d;border-radius:14px}
    QFrame[role="row"][active="true"]{background:#0d241e;border:1px solid #22b98f}
    QFrame[role="hint"]{background:#0c211b;border:1px solid #1b735d;border-radius:16px}
    QFrame[role="signal"]{background:#0c1110;border:1px solid #25312c;border-radius:18px}
    QFrame[role="signal"][state="running"]{border:1px solid #1bb58b;background:#0b211a}
    QLabel[role="tiny"]{color:#87958f;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase}
    QLabel[role="muted"]{color:#9aa9a3;font-size:12px}
    QLabel[role="stockStatus"]{color:#dbe7e1;font-size:12px;font-weight:700;padding:4px 2px}
    QLabel[role="section"]{font-size:22px;font-weight:900}
    QLabel[role="title"]{font-size:52px;font-weight:900;letter-spacing:-2px}
    QLabel[role="value"]{font-family:Consolas;font-size:28px;font-weight:900}
    QLabel[accent="green"]{color:#20d4a4}QLabel[accent="amber"]{color:#f3b743}QLabel[accent="red"]{color:#ff6670}QLabel[accent="theme"]{color:#20d4a4}
    QPushButton{background:#151e1a;border:1px solid #2a3932;border-radius:12px;padding:10px 12px;min-width:0;font-weight:800;text-align:left}
    QPushButton[compact="true"]{padding:9px 10px;text-align:center}
    QPushButton:hover{background:#1b2823;border:1px solid #3b5147}
    QPushButton:disabled{background:#0d1210;border:1px solid #1b2722;color:#52615d}
    QPushButton[primary="true"]:enabled{background:#00c991;color:#04130f;border:0}
    QPushButton[stockAction="save"]:enabled{background:#2f2610;color:#f8c95d;border:1px solid #c8952f}
    QPushButton[stockAction="save"]:hover{background:#473814;border:1px solid #f1c45a}
    QPushButton[active="true"]{background:#00c991;color:#04130f;border:0}
    QPushButton[intent="positive"]{color:#20d4a4;border:1px solid rgba(32,212,164,110);background:rgba(32,212,164,18)}
    QPushButton[intent="danger"]{color:#ff6670;border:1px solid rgba(255,102,112,110);background:rgba(255,102,112,18)}
    QComboBox{background:#101714;color:#f4f7f5;border:1px solid #2a3932;border-radius:12px;padding:10px 12px;font-weight:800;min-height:22px}
    QComboBox::drop-down{background:#18221e;border:0;border-top-right-radius:12px;border-bottom-right-radius:12px;width:34px}
    QComboBox::down-arrow{width:0;height:0}
    QComboBox QAbstractItemView{background:#09100e;color:#f6fff9;border:1px solid rgba(0,209,154,80);border-radius:12px;padding:6px;selection-background-color:#00c991;selection-color:#04130f;outline:0}
    QComboBox QAbstractItemView::item{min-height:30px;padding:6px 10px;border-radius:8px;background:#09100e;color:#f6fff9}
    QComboBox QAbstractItemView::item:selected{background:#00c991;color:#04130f}
    QLineEdit{background:#101714;border:1px solid #2a3932;border-radius:12px;padding:10px 12px;color:#f4f7f5;font-weight:700}
    QLineEdit:focus{border:1px solid #20c69b;background:#0d211a}
    QCheckBox{spacing:10px;font-weight:800;color:#d9e7e1}
    QCheckBox::indicator{width:20px;height:20px;border-radius:6px;border:1px solid #4a5a53;background:#101714}
    QCheckBox::indicator:checked{background:#00c991;border:1px solid #00c991}
    QScrollArea,QTextEdit{background:#090d0c;border:1px solid #23302a;border-radius:16px;padding:8px}
    QScrollArea > QWidget#qt_scrollarea_viewport{background:#090d0c}
    QTextEdit[role="mini"]{font-family:Consolas;font-size:12px}
    QScrollBar:vertical{background:#101714;width:10px;border-radius:5px;margin:4px}
    QScrollBar::handle:vertical{background:#1b8064;border-radius:5px;min-height:42px}
    QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;background:transparent}
    QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:transparent}
    """
    normalized = str(theme or "dark").lower().replace("_", "-").strip()
    if normalized in {"deep-sea", "deep sea", "sea"}:
        return base + """
        QMainWindow{background:#031016}
        #Root{background:qradialgradient(cx:.12,cy:.08,radius:1,fx:.12,fy:.08,stop:0 rgba(0,194,255,46),stop:.46 #031016,stop:1 #05070b)}
        QFrame[role="panel"]{background:rgba(6,18,25,220);border:1px solid rgba(104,232,255,38)}
        QFrame[role="row"][active="true"]{background:#061a22;border:1px solid #18d6ff}
        QFrame[role="signal"][state="running"]{background:#061a22;border:1px solid #18d6ff}
        QFrame[role="hint"]{background:#061c25;border:1px solid #177f99}
        QPushButton[primary="true"]:enabled,QPushButton[active="true"]{background:#18d6ff;color:#021014}
        QPushButton[intent="positive"]{color:#18d6ff;border:1px solid rgba(24,214,255,110);background:rgba(24,214,255,18)}
        QLabel[accent="green"],QLabel[accent="theme"]{color:#18d6ff}
        QComboBox QAbstractItemView{border-color:rgba(24,214,255,100);selection-background-color:#18d6ff;selection-color:#021014}
        QComboBox QAbstractItemView::item:selected{background:#18d6ff;color:#021014}
        QScrollBar::handle:vertical{background:rgba(24,214,255,105)}
        """
    if normalized in {"contrast", "high-contrast", "high contrast"}:
        return base + """
        QMainWindow{background:#020202}
        #Root{background:#020202}
        QWidget{color:#fffaf0}
        QWidget#StockAdvisorControls{background:#050504}
        QFrame[role="panel"]{background:#090907;border:1px solid #564c36;border-radius:12px}
        QFrame[role="row"]{background:#10100d;border:1px solid #463f30;border-radius:10px}
        QFrame[role="signal"]{background:#070706;border:1px solid #5d5137;border-radius:12px}
        QFrame[role="row"][active="true"]{background:#1c1507;border:1px solid #d69f27}
        QFrame[role="signal"][state="running"]{background:#13130e;border:1px solid #e9e4ce}
        QFrame[role="hint"]{background:#1b1408;border:1px solid #8c6720;border-radius:10px}
        QLabel[role="tiny"]{color:#ceb98b}
        QLabel[role="muted"]{color:#e5dcc8}
        QLabel[role="stockStatus"]{color:#fff0c7}
        QLabel[accent="green"]{color:#eff5e7}QLabel[accent="amber"]{color:#f1c45a}QLabel[accent="red"]{color:#ff7a6d}QLabel[accent="theme"]{color:#f1c45a}
        QPushButton{background:#11110e;border:1px solid #66583a;border-radius:8px;color:#fffaf0}
        QPushButton:hover{background:#211b0f;border:1px solid #efc861}
        QPushButton:disabled{background:#090907;border:1px solid #2d2a20;color:#777163}
        QPushButton[intent="positive"]{color:#fffaf0;border:1px solid #a79e80;background:#171711}
        QPushButton[intent="danger"]{color:#fffaf0;border:1px solid #ff7467;background:#3a1714}
        QComboBox,QLineEdit{background:#090907;border:1px solid #66583a;border-radius:8px;color:#fffaf0}
        QComboBox::drop-down{background:#17140d}
        QComboBox QAbstractItemView,QComboBox QAbstractItemView::item{background:#090907;color:#fffaf0;border-color:#8f7439}
        QComboBox QAbstractItemView::item:selected{background:#d69f27;color:#120e05}
        QLineEdit:focus{border:1px solid #e4b64e;background:#141109}
        QCheckBox{color:#f0eadc}QCheckBox::indicator{background:#090907;border-color:#8c7b57}QCheckBox::indicator:checked{background:#d69f27;border-color:#d69f27}
        QScrollArea,QTextEdit{background:#050504;border:1px solid #514734;border-radius:10px}
        QScrollArea > QWidget#qt_scrollarea_viewport{background:#050504}
        QScrollBar:vertical{background:#11110e}QScrollBar::handle:vertical{background:#9a772f}
        QPushButton[primary="true"]:enabled{background:#c64339;color:#fffaf6;border:1px solid #ff796e}
        QPushButton[stockAction="save"]:enabled{background:#d69f27;color:#120e05;border:1px solid #f0c65b}
        QPushButton[stockAction="save"]:hover{background:#f1c45a;border:1px solid #fff0b0}
        QPushButton[active="true"]{background:#d69f27;color:#120e05;border:1px solid #f0c65b}
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


class NativeShell:
    """Small wrapper around the Qt main window."""

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
        self.stock_process = None
        self.stock_pending_launch = None
        self.stock_restart_signal_bot = False
        self.stock_process_log: list[str] = []
        self.stock_fields: dict[str, Any] = {}
        self.stock_run_btn = None
        self.stock_status = None
        self.stock_result = None
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
        self.live_timer = None
        self.last_running_signature: tuple[str, ...] = ()
        self.last_diagnostics_report = ""
        self.ready_callback = ready_callback
        self.window = QT.QMainWindow()
        apply_window_icon(self.window)
        self.window.setWindowTitle("OAK Manager · Native Qt")
        self.window.setMinimumSize(1040, 680)
        self.window.resize(1240, 780)
        self._build()
        self._install_shortcuts()
        self.apply_theme()
        self.refresh()
        self._start_live_timer()
        QT.QTimer.singleShot(0, self._ready)

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
        frame.setFixedWidth(260)
        layout = QT.QVBoxLayout(frame)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        logo = label("⚡  SLTP.", role="value", accent="green")
        logo.setContentsMargins(0, 0, 0, 6)
        layout.addWidget(logo)
        for name in ("Dashboard", "Signals", "VN30 Advisor", "Profiles", "Copy", "Pending", "Diagnostics", "Settings"):
            nav = button(name)
            nav.clicked.connect(lambda _checked=False, tab=name: self.switch_tab(tab))
            self.nav_buttons[name] = nav
            layout.addWidget(nav)
        self.profile_combo = QT.QComboBox()
        self.profile_combo.setMinimumHeight(42)
        self.profile_combo.currentTextChanged.connect(self._select_profile)
        layout.addWidget(label("PROFILE", role="tiny"))
        layout.addWidget(self.profile_combo)
        self.start_btn = button("Start selected", primary=True)
        self.stop_btn = button("Stop selected")
        self.refresh_btn = button("Refresh")
        self.classic_btn = button("Open classic UI")
        self.start_btn.clicked.connect(self.start_selected)
        self.stop_btn.clicked.connect(self.stop_selected)
        self.refresh_btn.clicked.connect(self.refresh)
        self.classic_btn.clicked.connect(self.open_classic)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.refresh_btn)
        layout.addWidget(self.classic_btn)
        self.live_status = label("Heartbeat ready", role="muted")
        layout.addWidget(self.live_status)
        layout.addStretch(1)
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
        left_layout.addWidget(label("TRADING COMMAND CENTER", role="tiny"))
        left_layout.addWidget(self.title)
        left_layout.addWidget(self.subtitle)
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
        frame = panel()
        layout = QT.QVBoxLayout(frame)
        value_label = label(value, role="value", accent=accent)
        layout.addWidget(label(title.upper(), role="tiny"))
        layout.addWidget(value_label)
        return {"frame": frame, "value": value_label}

    def _dashboard_page(self) -> Any:
        layout = QT.QHBoxLayout()
        layout.setSpacing(18)
        self.profile_rows = QT.QWidget()
        self.profile_rows.setObjectName("ProfileRows")
        self.profile_rows.setStyleSheet("background: transparent;")
        self.profile_rows_layout = QT.QVBoxLayout(self.profile_rows)
        self.profile_rows_layout.setSpacing(10)
        self.profile_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.profile_scroll = QT.QScrollArea()
        self.profile_scroll.setWidgetResizable(True)
        self.profile_scroll.viewport().setStyleSheet("background: transparent;")
        self.profile_scroll.setWidget(self.profile_rows)
        self.console = QT.QTextEdit()
        self.console.setReadOnly(True)
        self.console.document().setMaximumBlockCount(1200)
        layout.addWidget(self._section("PROFILES", self.profile_scroll), 1)
        layout.addWidget(self._section("LIVE CONSOLE", self.console), 1)
        page = QT.QWidget()
        page.setLayout(layout)
        return page

    def _signals_page(self) -> Any:
        frame = panel()
        layout = QT.QVBoxLayout(frame)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        header = QT.QHBoxLayout()
        header.addWidget(label("Signals", role="section"))
        self.signal_summary = label("0/5 running", role="muted")
        header.addWidget(self.signal_summary)
        header.addStretch(1)
        clear_logs = button("Clear logs")
        start_all = button("Start all", primary=True)
        stop_all = button("Stop all")
        clear_logs.clicked.connect(self.clear_signal_logs)
        start_all.clicked.connect(self.start_all_signals)
        stop_all.clicked.connect(self.stop_all_signals)
        header.addWidget(clear_logs)
        header.addWidget(start_all)
        header.addWidget(stop_all)
        layout.addLayout(header)

        grid = QT.QGridLayout()
        grid.setSpacing(12)
        positions = [(0, 0, 1), (0, 1, 1), (1, 0, 1), (1, 1, 1), (2, 0, 2)]
        for index, (key, name, color) in enumerate(SIGNAL_DEFS):
            row, col, span = positions[index]
            grid.addWidget(self._signal_card(key, name, color), row, col, 1, span)
        layout.addLayout(grid, 1)
        return frame

    def _stock_advisor_page(self) -> Any:
        page = QT.QWidget()
        layout = QT.QHBoxLayout(page)
        layout.setSpacing(18)
        controls = self._stock_advisor_controls()
        controls.setObjectName("StockAdvisorControls")
        controls_scroll = QT.QScrollArea()
        controls_scroll.setFrameShape(QT.QFrame.Shape.NoFrame)
        controls_scroll.setHorizontalScrollBarPolicy(QT.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setWidget(controls)
        self.stock_result = QT.QTextEdit()
        self.stock_result.setReadOnly(True)
        self.stock_result.setProperty("role", "mini")
        self.stock_result.setPlainText(native_text("Press Run VN30 Advisor to scan 30 constituents using local EOD data."))
        layout.addWidget(self._section("LOCAL EOD MARKET DATA", controls_scroll), 1)
        layout.addWidget(self._section("ADVISORY RESULT", self.stock_result), 2)
        return page

    def _stock_advisor_controls(self) -> Any:
        frame = QT.QWidget()
        layout = QT.QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addLayout(self._stock_advisor_actions())
        self.stock_status = label("Local EOD Database (data/market.db) · Auto-updated after 15:00", role="stockStatus")
        self.stock_status.setWordWrap(True)
        layout.addWidget(self.stock_status)

        self.stock_progress_bar = QT.QProgressBar()
        self.stock_progress_bar.setRange(0, 100)
        self.stock_progress_bar.setValue(0)
        self.stock_progress_bar.setTextVisible(True)
        self.stock_progress_bar.setFormat("Sẵn sàng (0%)")
        self.stock_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3f3f46;
                border-radius: 6px;
                background-color: #18181b;
                text-align: center;
                color: #f4f4f5;
                font-weight: bold;
                font-size: 11px;
                min-height: 24px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #10b981);
                border-radius: 5px;
            }
        """)
        self.stock_progress_bar.setVisible(False)
        layout.addWidget(self.stock_progress_bar)

        layout.addStretch(1)
        return frame

    def _build_stock_fields(self, layout: Any) -> None:
        for title, key in (
            ("Deployable capital", "capital"),
            ("Hurdle (bps)", "hurdle_bps"),
        ):
            field = self._stock_advisor_field(secret=False)
            self.stock_fields[key] = field
            layout.addWidget(self._stock_advisor_field_row(title, field))

    def _stock_advisor_field_row(self, title: str, field: Any) -> Any:
        row = QT.QFrame()
        row.setProperty("role", "row")
        row_layout = QT.QVBoxLayout(row)
        row_layout.setContentsMargins(12, 8, 12, 8)
        row_layout.setSpacing(4)
        row_layout.addWidget(label(title, role="tiny"))
        row_layout.addWidget(field)
        return row

    def _stock_advisor_actions(self) -> Any:
        actions = QT.QVBoxLayout()
        self.stock_update_eod_btn = button("Update EOD Data (15:00+)")
        self.stock_update_eod_btn.setProperty("stockAction", "update_eod")
        self.stock_run_btn = button("Run VN30 Advisor", primary=True)
        self.stock_update_eod_btn.clicked.connect(self.update_eod_data)
        self.stock_run_btn.clicked.connect(self.run_stock_advisor)
        actions.addWidget(self.stock_update_eod_btn)
        actions.addWidget(self.stock_run_btn)
        return actions

    def _stock_advisor_field(self, secret: bool) -> Any:
        field = QT.QLineEdit()
        field.setMinimumHeight(40)
        if secret:
            field.setEchoMode(QT.QLineEdit.EchoMode.PasswordEchoOnEdit)
        return field

    def _profiles_page(self) -> Any:
        page = QT.QWidget()
        layout = QT.QHBoxLayout(page)
        layout.setSpacing(18)

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

        layout.addWidget(self._section("PROFILE MAP", scroll), 1)
        layout.addWidget(self._section("PROFILE EDITOR", self._profile_editor()), 1)
        return page

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
        page = QT.QWidget()
        layout = QT.QHBoxLayout(page)
        layout.setSpacing(18)

        self.copy_detail = QT.QTextEdit()
        self.copy_detail.setReadOnly(True)
        self.copy_detail.setProperty("role", "mini")

        guardrails = QT.QWidget()
        guardrails.setStyleSheet("background: transparent;")
        self.copy_guardrails_layout = QT.QVBoxLayout(guardrails)
        self.copy_guardrails_layout.setContentsMargins(0, 0, 0, 0)
        self.copy_guardrails_layout.setSpacing(10)

        layout.addWidget(self._section("COPY SETTINGS", self.copy_detail), 1)
        layout.addWidget(self._section("SAFETY GUARDRAILS", guardrails), 1)
        return page

    def _pending_page(self) -> Any:
        page = QT.QWidget()
        layout = QT.QHBoxLayout(page)
        layout.setSpacing(18)

        left = QT.QWidget()
        left_layout = QT.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        actions = QT.QHBoxLayout()
        refresh = button("Refresh")
        clear_done = button("Clear done")
        refresh.clicked.connect(self.refresh)
        clear_done.clicked.connect(self.clear_done_pending)
        actions.addWidget(refresh)
        actions.addWidget(clear_done)
        left_layout.addLayout(actions)
        self.pending_action_status = label("Pending controls are profile-scoped.", role="muted")
        left_layout.addWidget(self.pending_action_status)
        self.pending_summary = QT.QTextEdit()
        self.pending_summary.setReadOnly(True)
        self.pending_summary.setProperty("role", "mini")
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

        layout.addWidget(self._section("SESSION FILES", left), 1)
        layout.addWidget(self._section("SCHEDULED TASKS", scroll), 1)
        return page

    def _diagnostics_page(self) -> Any:
        page = QT.QWidget()
        layout = QT.QHBoxLayout(page)
        layout.setSpacing(18)
        left = QT.QWidget()
        left_layout = QT.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        actions = QT.QGridLayout()
        actions.setHorizontalSpacing(8)
        actions.setVerticalSpacing(8)
        for index, (text, handler) in enumerate(
            (
                ("Refresh", self.refresh),
                ("Copy report", self.copy_diagnostics_report),
                ("Copy visible", self.copy_visible_log),
                ("Export bundle", self.export_debug_bundle),
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
        clear_display.clicked.connect(self.clear_diagnostics_display)
        filters.addWidget(self.diag_filter, 1)
        filters.addWidget(self.diag_level)
        filters.addWidget(clear_display)
        left_layout.addLayout(filters)
        self.diag_status = label("Diagnostics export is redacted by default.", role="muted")
        left_layout.addWidget(self.diag_status)
        self.diag_summary = QT.QTextEdit()
        self.diag_summary.setReadOnly(True)
        self.diag_summary.setProperty("role", "mini")
        left_layout.addWidget(self.diag_summary, 1)
        self.diag_log = QT.QTextEdit()
        self.diag_log.setReadOnly(True)
        self.diag_log.setProperty("role", "mini")
        layout.addWidget(self._section("RUNTIME CHECK", left), 1)
        layout.addWidget(self._section("LATEST LOG", self.diag_log), 1)
        return page

    def _settings_page(self) -> Any:
        page = QT.QWidget()
        layout = QT.QHBoxLayout(page)
        layout.setSpacing(18)

        controls = QT.QWidget()
        controls_layout = QT.QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(12)

        self.settings_lang_combo = QT.QComboBox()
        self.settings_lang_combo.addItems(["EN", "VN"])
        self.settings_lang_combo.setMinimumHeight(42)
        self.settings_theme_combo = QT.QComboBox()
        self.settings_theme_combo.addItems(["dark", "deep-sea", "contrast"])
        self.settings_theme_combo.setMinimumHeight(42)
        controls_layout.addWidget(self._settings_row("Language", "Dashboard language preference.", self.settings_lang_combo))
        controls_layout.addWidget(self._settings_row("Theme", "NativeQt visual skin. Applies instantly after save.", self.settings_theme_combo))

        actions = QT.QHBoxLayout()
        save = button("Save settings", primary=True)
        reset = button("Reset theme")
        artifacts = button("Open artifacts")
        save.clicked.connect(self.save_native_settings)
        reset.clicked.connect(self.reset_native_theme)
        artifacts.clicked.connect(lambda: self._open_folder(ROOT / "dist"))
        actions.addWidget(save)
        actions.addWidget(reset)
        actions.addWidget(artifacts)
        controls_layout.addLayout(actions)
        self.settings_status = label("Settings are stored in settings.json.", role="muted")
        controls_layout.addWidget(self.settings_status)
        controls_layout.addWidget(self._guardrail_row("NativeQt", "LEAN", "Qt Widgets + QSS only; no Chromium/WebEngine payload.", "green"))
        controls_layout.addWidget(self._guardrail_row("Installer", "SMALL", "Current NativeQt installer stays around 40 MB.", "amber"))
        controls_layout.addStretch(1)

        self.settings_about = QT.QTextEdit()
        self.settings_about.setReadOnly(True)
        self.settings_about.setProperty("role", "mini")
        layout.addWidget(self._section("SETTINGS", controls), 1)
        layout.addWidget(self._section("ABOUT / BUILD", self.settings_about), 1)
        return page

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
        self.live_timer = QT.QTimer(self.window)
        self.live_timer.timeout.connect(self._refresh_live_state)
        self.live_timer.start(1500)

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
        stock_text = self.stock_result.toPlainText() if self.stock_result is not None else ""
        signal_logs = {key: card["console"].toPlainText() for key, card in self.signal_cards.items()}
        old_root = self.window.takeCentralWidget()
        if old_root is not None:
            old_root.deleteLater()
        self.nav_buttons = {}
        self.signal_cards = {}
        self._build()
        self.selected = selected
        self.console.setPlainText(console_text)
        for key, text in signal_logs.items():
            if key in self.signal_cards:
                self.signal_cards[key]["console"].setPlainText(text)
        if stock_text and self.stock_result is not None:
            self.stock_result.setPlainText(stock_text)
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
        self._refresh_pending_page()
        self._refresh_diagnostics_page()
        self._refresh_settings_page()
        self._refresh_stock_advisor_page()
        self._refresh_signal_states()
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

    def _reload_state_files(self) -> None:
        self.profiles = read_json(PROFILE_FILE, {})
        self.settings = read_json(SETTINGS_FILE, {})
        if self.selected in self.profiles:
            return
        self.selected = next(iter(self.profiles), "")

    def _refresh_live_state(self) -> None:
        running = tuple(sorted(self._running_profiles()))
        self.stat_running["value"].setText(str(len(running)))
        self._refresh_profile_controls()
        self._refresh_signal_states()
        if self.current_tab == "Pending":
            self._refresh_pending_page()
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

    def _refresh_profile_controls(self) -> None:
        running = self._profile_is_running(self.selected)
        has_profile = bool(self.selected and self.selected in self.profiles)
        self.start_btn.setEnabled(has_profile and not running)
        self.stop_btn.setEnabled(has_profile and running)
        self.start_btn.setText(native_text("Start selected" if not running else "Running"))
        self.stop_btn.setText(native_text("Stop selected"))

    def switch_tab(self, tab: str) -> None:
        if tab not in self.tab_pages:
            return
        self.current_tab = tab
        self.stack.setCurrentWidget(self.tab_pages[tab])
        self._refresh_nav()

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
        self._clear_profile_rows()
        running = set(self._running_profiles())
        if not self.profiles:
            self.profile_rows_layout.addWidget(
                self._guardrail_row("No profiles found", "SETUP", "Copy profiles.example.json to profiles.json, then add MT5 profile settings.", "amber")
            )
            self.profile_rows_layout.addStretch(1)
            return
        for name, cfg in self.profiles.items():
            status = "RUNNING" if name in running else "IDLE"
            self.profile_rows_layout.addWidget(self._profile_row(name, cfg, status))
        self.profile_rows_layout.addStretch(1)

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
        status_label = label(status, accent="green" if status == "RUNNING" else "")
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

    def _refresh_profile_page(self) -> None:
        if self.profile_cards_layout is None or self.profile_detail is None:
            return
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
            return
        running = set(self._running_profiles())
        for name, cfg in self.profiles.items():
            status = "RUNNING" if name in running else "IDLE"
            self.profile_cards_layout.addWidget(self._profile_card(name, cfg, status))
        self.profile_cards_layout.addStretch(1)
        cfg = self.profiles.get(self.selected, {})
        status = "RUNNING" if self.selected in running else "IDLE"
        self.profile_detail.setPlainText(self._profile_detail_text(self.selected, cfg, status))
        self._load_profile_editor(self.selected, cfg, status)

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
        header.addStretch(1)
        select = button("Selected" if name == self.selected else "Use", primary=name == self.selected)
        select.setFixedWidth(96)
        select.clicked.connect(lambda _checked=False, n=name: self.select_profile(n))
        header.addWidget(label(status, accent="green" if status == "RUNNING" else ""))
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

    def _refresh_copy_page(self) -> None:
        if self.copy_detail is None or self.copy_guardrails_layout is None:
            return
        cfg = self.profiles.get(self.selected, {})
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

    def _refresh_pending_page(self) -> None:
        if self.pending_summary is None or self.pending_items_layout is None:
            return
        files, items = self._pending_state(self.selected)
        waiting = sum(1 for item in items if self._is_waiting_status(item))
        done = sum(1 for item in items if str(item.get("status") or "").lower() in PENDING_DONE_STATUSES)
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
        delete_btn.setStyleSheet("QPushButton{color:#ff6b6b;border-color:rgba(255,107,107,90)}")
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
            self.refresh()
            self._set_pending_status("Pending item was not found on disk.", "amber")
            return
        self.pending_delete_key = ""
        self.log(f"Deleted pending item from {path.name}.")
        self.refresh()
        self.switch_tab("Pending")
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
        self.refresh()
        self.switch_tab("Pending")
        accent = "green" if removed_total else "amber"
        self._set_pending_status(f"Cleared {removed_total} completed item(s).", accent)

    def _set_pending_status(self, message: str, accent: str = "muted") -> None:
        if self.pending_action_status is None:
            return
        self.pending_action_status.setText(native_text(message))
        self.pending_action_status.setProperty("accent", accent)
        self.pending_action_status.style().unpolish(self.pending_action_status)
        self.pending_action_status.style().polish(self.pending_action_status)

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

    def _refresh_diagnostics_page(self) -> None:
        if self.diag_summary is None or self.diag_log is None:
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
        self._set_diag_status("Diagnostics export is redacted by default.", "muted")

    def copy_diagnostics_report(self) -> None:
        """Copy a safe runtime report without secrets."""
        self._refresh_diagnostics_page()
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

    def _refresh_stock_advisor_page(self) -> None:
        if not self.stock_fields:
            return
        values = {
            "capital": self.settings.get("stock_capital", 90_000_000),
            "hurdle_bps": self.settings.get("stock_hurdle_bps", 0),
        }
        for key, value in values.items():
            if key in self.stock_fields:
                self.stock_fields[key].setText(str(value))
        output = ROOT / "stock_recommendation.json"
        if self.stock_process is None and output.exists() and self.stock_result is not None:
            payload = read_json(output, {})
            if isinstance(payload, dict) and payload:
                locale = "VN" if NATIVE_LANGUAGE == "VN" else "EN"
                self.stock_result.setPlainText(render_stock_advisory(payload, locale=locale))
        self._check_auto_eod_update()

    def _check_auto_eod_update(self) -> None:
        """Auto-trigger EOD update after 15:00 local market close on weekdays."""
        now = datetime.now()
        if now.weekday() in (5, 6):  # Weekend
            return
        if now.time() < dt_time(15, 0):  # Before market close
            return
        today_str = now.strftime("%Y-%m-%d")
        if getattr(self, "_last_auto_eod_date", None) == today_str:
            return
        self._last_auto_eod_date = today_str
        self.update_eod_data(is_auto=True)

    def update_eod_data(self, is_auto: bool = False) -> None:
        """Run python -m eod_collector update in background to fetch latest EOD prices."""
        if getattr(self, "eod_update_process", None) is not None:
            return
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
            self.stock_update_eod_btn.setEnabled(False)

        if hasattr(self, "stock_progress_bar") and self.stock_progress_bar is not None:
            self.stock_progress_bar.setRange(0, 100)
            self.stock_progress_bar.setValue(0)
            self.stock_progress_bar.setFormat("Đang cập nhật dữ liệu EOD (0%)...")
            self.stock_progress_bar.setVisible(True)

        process.readyReadStandardOutput.connect(lambda p=process: self._read_eod_update_output(p))
        process.finished.connect(lambda code, _status, p=process: self._eod_update_done(code, p, is_auto))
        self.eod_update_process = process
        process.start()

    def _read_eod_update_output(self, process: Any) -> None:
        data = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            clean = line.strip()
            if not clean or not hasattr(self, "stock_progress_bar") or self.stock_progress_bar is None:
                continue
            # New format: [VPS EOD] N/TOTAL (PCT%) — emitted every 10 symbols
            match_prog = re.search(r"\[VPS EOD\] (\d+)/(\d+) \((\d+)%\)", clean)
            if match_prog:
                cur = int(match_prog.group(1))
                tot = int(match_prog.group(2))
                pct = int(match_prog.group(3))
                self.stock_progress_bar.setValue(pct)
                self.stock_progress_bar.setFormat(f"Đang tải EOD VPS: {cur}/{tot} mã ({pct}%)...")
                continue
            # Announce: [VPS EOD] Fetching N symbols for DATE...
            match_total = re.search(r"\[VPS EOD\] Fetching (\d+) symbols", clean)
            if match_total:
                tot = match_total.group(1)
                self.stock_progress_bar.setValue(1)
                self.stock_progress_bar.setFormat(f"Đang kết nối VPS API (0/{tot} mã)...")
                continue
            # Final save confirmation from logger
            if ("Saved" in clean or "saved" in clean) and "records" in clean:
                match = re.search(r"(\d+) records", clean)
                if match:
                    cnt = match.group(1)
                    self.stock_progress_bar.setValue(100)
                    self.stock_progress_bar.setFormat(f"Đã cập nhật xong {cnt} bản ghi EOD ✓")

    def _eod_update_done(self, code: int, process: Any, is_auto: bool) -> None:
        if getattr(self, "eod_update_process", None) is process:
            self.eod_update_process = None
        if hasattr(self, "stock_update_eod_btn"):
            self.stock_update_eod_btn.setEnabled(True)
        if code == 0:
            msg = native_text("EOD data updated successfully.")
            self._set_stock_status(msg, "green")
            if hasattr(self, "stock_progress_bar") and self.stock_progress_bar is not None:
                self.stock_progress_bar.setValue(100)
                self.stock_progress_bar.setFormat("Cập nhật EOD hoàn tất ✓ 100%")
            if is_auto:
                auto_msg = "Cập nhật EOD tự động hoàn tất. Đang tự động chạy bộ lọc cổ phiếu..." if NATIVE_LANGUAGE == "VN" else "Auto EOD completed. Running stock scanner..."
                self._set_stock_status(auto_msg, "amber")
                self.append_log(f"[AUTO 15:00+] {auto_msg}")
                QT.QTimer.singleShot(500, self.run_stock_advisor)
        else:
            err_msg = f"Cập nhật EOD thất bại (mã lỗi {code})" if NATIVE_LANGUAGE == "VN" else f"EOD update failed (code {code})"
            self._set_stock_status(err_msg, "red")
            if hasattr(self, "stock_progress_bar") and self.stock_progress_bar is not None:
                self.stock_progress_bar.setFormat("Lỗi cập nhật EOD ✗")

    def _stock_settings_from_form(self) -> StockAdvisorDesktopSettings:
        capital_str = self.stock_fields.get("capital", QT.QLineEdit()).text().strip() or "90000000"
        hurdle_str = self.stock_fields.get("hurdle_bps", QT.QLineEdit()).text().strip() or "0"
        return StockAdvisorDesktopSettings(
            client_id="oak-stock-scanner",
            capital=float(capital_str),
            hurdle_bps=float(hurdle_str),
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

    def _save_stock_credentials_if_entered(self) -> bool:
        return False

    def _persist_stock_settings(self, settings: StockAdvisorDesktopSettings) -> None:
        next_settings = dict(self.settings)
        next_settings["stock_client_id"] = settings.client_id
        next_settings["stock_capital"] = settings.capital
        next_settings["stock_hurdle_bps"] = settings.hurdle_bps
        write_json_atomic(SETTINGS_FILE, next_settings)
        self.settings = next_settings

    def run_stock_advisor(self) -> None:
        """Validate and run the local EOD read-only advisor."""
        if self.stock_process is not None or self.stock_pending_launch is not None:
            return
        try:
            settings = self._stock_settings_from_form()
            credentials = self._stock_credentials_for_run()
            self._persist_stock_settings(settings)
        except (StockAdvisorDesktopError, OSError, ValueError, RuntimeError) as error:
            self._set_stock_status(f"Cannot run advisor: {error}", "red")
            return
        today = datetime.now(timezone(timedelta(hours=7))).date()
        needs_backfill = requires_h4_backfill_file(ROOT / "signals_log.json", today)
        plan = build_stock_advisor_launch_plan(ROOT, sys.executable, getattr(sys, "frozen", False), settings, needs_backfill)
        self.stock_pending_launch = (plan, settings.client_id, *credentials)
        self.stock_restart_signal_bot = needs_backfill and self._signal_is_running("signal_bot")
        self.stock_run_btn.setEnabled(False)
        if self.stock_restart_signal_bot:
            self._set_stock_status("Auto backfill: pausing Signal Bot...", "amber")
            self.stop_signal("signal_bot")
            return
        self._launch_pending_stock_advisor()

    def _stock_credentials_for_run(self) -> tuple[str, str]:
        return ("local-eod-key", "local-eod-secret")

    def _signal_is_running(self, key: str) -> bool:
        process = self.signal_processes.get(key)
        return bool(process and process.state() != QT.NotRunning)

    def _launch_pending_stock_advisor(self) -> None:
        if self.stock_pending_launch is None:
            return
        plan, client_id, api_key, api_secret = self.stock_pending_launch
        self.stock_pending_launch = None
        process = QT.QProcess(self.window)
        process.setProgram(plan.program)
        process.setArguments(list(plan.arguments))
        process.setWorkingDirectory(str(ROOT))
        process.setProcessEnvironment(self._stock_process_environment(client_id, api_key, api_secret))
        process.setProcessChannelMode(QT.QProcess.ProcessChannelMode.MergedChannels)
        if hasattr(self, "stock_progress_bar") and self.stock_progress_bar is not None:
            self.stock_progress_bar.setRange(0, 100)
            self.stock_progress_bar.setValue(0)
            self.stock_progress_bar.setFormat("Đang khởi tạo bộ lọc D1 (0%)...")
            self.stock_progress_bar.setVisible(True)
        process.readyReadStandardOutput.connect(lambda p=process: self._read_stock_advisor_output(p))
        process.finished.connect(lambda code, _status, p=process: self._stock_advisor_done(code, p))
        process.errorOccurred.connect(lambda error, p=process: self._stock_advisor_error(error, p))
        self.stock_process = process
        self.stock_process_log = []
        self.stock_result.clear()
        self._set_stock_status(native_text("Running VN30 advisor..."), "amber")
        process.start()

    def _stock_process_environment(self, client_id: str, api_key: str, api_secret: str) -> Any:
        environment = self._process_environment()
        environment.insert("SSI_CLIENT_ID", client_id)
        environment.insert("SSI_API_KEY", api_key)
        environment.insert("SSI_API_SECRET", api_secret)
        return environment

    def _read_stock_advisor_output(self, process: Any) -> None:
        data = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            clean = line.strip()
            if clean:
                self.stock_process_log.append(clean)
                self.stock_result.append(clean)
                match = re.search(r"\[Local EOD\] (\d+)/(\d+)\s+(\w+)", clean)
                if match and hasattr(self, "stock_progress_bar") and self.stock_progress_bar is not None:
                    cur = int(match.group(1))
                    tot = int(match.group(2))
                    sym = match.group(3)
                    pct = int((cur / tot) * 100)
                    self.stock_progress_bar.setValue(pct)
                    self.stock_progress_bar.setFormat(f"Đang quét [{cur}/{tot} mã] {sym}... {pct}%")
                    self.stock_progress_bar.setVisible(True)

    def _stock_advisor_done(self, code: int, process: Any) -> None:
        if self.stock_process is process:
            self.stock_process = None
        self.stock_run_btn.setEnabled(True)
        if code == 0:
            if hasattr(self, "stock_progress_bar") and self.stock_progress_bar is not None:
                self.stock_progress_bar.setValue(100)
                self.stock_progress_bar.setFormat("Hoàn tất quét toàn bộ 3 sàn 100%")
            payload = read_json(ROOT / "stock_recommendation.json", {})
            locale = "VN" if NATIVE_LANGUAGE == "VN" else "EN"
            self.stock_result.setPlainText(render_stock_advisory(payload, locale=locale) if isinstance(payload, dict) else "Invalid result")
            pushed = any(line.endswith("Stock advisor: pushed") for line in self.stock_process_log)
            message = "Advisor completed and dashboard updated." if pushed else "Advisor completed locally; dashboard push needs configuration."
            self._set_stock_status(native_text(message), "green" if pushed else "amber")
        else:
            if hasattr(self, "stock_progress_bar") and self.stock_progress_bar is not None:
                self.stock_progress_bar.setFormat("Lỗi chạy bộ lọc ✗")
            fail_msg = f"Bộ lọc thất bại (mã lỗi {code})" if NATIVE_LANGUAGE == "VN" else f"Advisor failed with code {code}"
            self._set_stock_status(fail_msg, "red")
        self._restart_signal_bot_after_stock()

    def _stock_advisor_error(self, error: Any, process: Any) -> None:
        if self.stock_process is process:
            self._set_stock_status(f"Advisor process error: {error}", "red")

    def _restart_signal_bot_after_stock(self) -> None:
        if not self.stock_restart_signal_bot:
            return
        self.stock_restart_signal_bot = False
        self.start_signal("signal_bot")

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

    def apply_theme(self) -> None:
        """Apply the current NativeQt QSS theme to the application."""
        app = QT.QApplication.instance()
        if app is None:
            return
        app.setStyleSheet(app_qss(str(self.settings.get("theme", "dark"))))

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

    def _profile_is_running(self, profile: str) -> bool:
        proc = self.monitor_processes.get(profile)
        return bool(proc and proc.state() != QT.NotRunning)

    def log(self, message: str) -> None:
        self._append_console_line(message)
        self._refresh_live_state()

    def start_selected(self) -> None:
        self.start_profile(self.selected)

    def start_profile(self, profile: str) -> None:
        if not profile or profile not in self.profiles:
            self.log("Select a valid profile first.")
            return
        if self._profile_is_running(profile):
            self.log(f"{profile} is already running.")
            return
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
        self.log(f"Starting monitor: {profile}")

    def _read_output(self, profile: str, proc: Any) -> None:
        data = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.strip():
                self._append_console_line(f"[{profile}] {line.strip()}")

    def _worker_started(self, profile: str, proc: Any) -> None:
        self.log(f"Monitor live: {profile} (PID {proc.processId()})")

    def _worker_done(self, profile: str, code: int, proc: Any) -> None:
        if self.monitor_processes.get(profile) is proc:
            self.monitor_processes.pop(profile, None)
        self.log(f"Monitor stopped: {profile} (code {code})")

    def _worker_error(self, profile: str, error: Any) -> None:
        self.log(f"Monitor error on {profile}: {error}")

    def stop_selected(self) -> None:
        self.stop_profile(self.selected)

    def stop_profile(self, profile: str) -> None:
        proc = self.monitor_processes.get(profile)
        if not proc or proc.state() == QT.NotRunning:
            self.log(f"No live monitor for {profile or 'selected profile'}.")
            return
        proc.terminate()
        QT.QTimer.singleShot(2500, lambda p=proc: p.kill() if p.state() != QT.NotRunning else None)
        self.log(f"Stopping monitor: {profile}")

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
        for index, (key, _name, _color) in enumerate(SIGNAL_DEFS):
            QT.QTimer.singleShot(index * 250, lambda k=key: self.start_signal(k))

    def stop_all_signals(self) -> None:
        for key, _name, _color in SIGNAL_DEFS:
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
        for key, _name, _color in SIGNAL_DEFS:
            proc = self.signal_processes.get(key)
            running = bool(proc and proc.state() != QT.NotRunning)
            pid = proc.processId() if running else None
            self._set_signal_running(key, running, pid)
        self._refresh_signal_summary()

    def _refresh_signal_summary(self) -> None:
        if self.signal_summary is None:
            return
        running = sum(
            1
            for proc in self.signal_processes.values()
            if proc and proc.state() != QT.NotRunning
        )
        self.signal_summary.setText(native_format("{running}/{total} running", running=running, total=len(SIGNAL_DEFS)))

    def start_signal(self, key: str) -> None:
        card = self.signal_cards.get(key)
        if not card:
            return
        proc = self.signal_processes.get(key)
        if proc and proc.state() != QT.NotRunning:
            self._append_signal_log(key, f"{card['name']} is already running.")
            return
        profile = self.selected if key == "signal_bot" else ""
        try:
            cmd = build_signal_process_cmd(
                key,
                profile,
                getattr(sys, "frozen", False),
                sys.executable,
            )
        except UnsupportedFrozenProcessError:
            self._append_signal_log(key, "Not supported in frozen mode yet.")
            return
        proc = QT.QProcess(self.window)
        proc.setProgram(cmd[0])
        proc.setArguments(cmd[1:])
        proc.setWorkingDirectory(str(ROOT))
        proc.setProcessEnvironment(self._process_environment())
        proc.setProcessChannelMode(QT.QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(lambda p=proc, k=key: self._read_signal_output(k, p))
        proc.finished.connect(lambda code, _status, p=proc, k=key: self._signal_done(k, code, p))
        proc.errorOccurred.connect(lambda error, p=proc, k=key: self._signal_error(k, error, p))
        self.signal_processes[key] = proc
        proc.start()
        card["console"].clear()
        self._set_signal_running(key, True, proc.processId())
        self._append_signal_log(key, f"Started {card['name']} with command: {' '.join(cmd)}")

    def _process_environment(self) -> Any:
        env = QT.QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUNBUFFERED", "1")
        return env

    def stop_signal(self, key: str) -> None:
        proc = self.signal_processes.get(key)
        if not proc or proc.state() == QT.NotRunning:
            self._set_signal_running(key, False)
            return
        proc.terminate()
        QT.QTimer.singleShot(2500, lambda p=proc: p.kill() if p.state() != QT.NotRunning else None)
        self._append_signal_log(key, "Stopping...")

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
        self._resume_stock_after_signal_stop(key)

    def _signal_error(self, key: str, error: Any, proc: Any) -> None:
        if self.signal_processes.get(key) is proc:
            self.signal_processes.pop(key, None)
        self._append_signal_log(key, f"Process error: {error}")
        self._set_signal_running(key, False)
        self._resume_stock_after_signal_stop(key)

    def _resume_stock_after_signal_stop(self, key: str) -> None:
        if key != "signal_bot" or self.stock_pending_launch is None:
            return
        QT.QTimer.singleShot(0, self._launch_pending_stock_advisor)

    def _set_signal_running(self, key: str, running: bool, pid: int | None = None) -> None:
        card = self.signal_cards.get(key)
        if not card:
            return
        card["status"].setText(native_text("Running" if running else "Stopped"))
        card["status"].setProperty("accent", "green" if running else "")
        card["dot"].setProperty("accent", "green" if running else "red")
        card["frame"].setProperty("state", "running" if running else "stopped")
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


def _worker_lock(profile_name: str) -> Path | None:
    """Create a best-effort single-instance worker lock."""
    safe = re.sub(r"[^\w\-]", "_", profile_name or "unknown")
    lock_path = ROOT / f"worker_{safe}.lock"
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

        mt5_signal_bot.main(profile_name=profile_arg(argv))
        return 0
    if "--mt-server" in argv:
        import mt4_mt5_server

        mt4_mt5_server.main()
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
