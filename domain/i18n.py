# -*- coding: utf-8 -*-
"""Minimal runtime localization for ROBOT SLTP Pro workers."""
from __future__ import annotations

LANG = {
    "VN": {
        "err_algo": "⚠️ CẢNH BÁO: Algo Trading đang TẮT. Hãy bật Algo Trading trước khi giao dịch.",
        "err_parse_r": "⚠️ Lỗi đọc mức R chốt lời",
        "log_algo_off": "Algo Trading: TẮT",
        "log_algo_on": "Algo Trading: BẬT",
        "log_closed": "✅ ĐÃ ĐÓNG LỆNH:",
        "log_config_bal": "Balance SL/TP:",
        "log_config_be": "Auto BE:",
        "log_config_gold": "Gold SL/TP:",
        "log_config_magic": "Magic:",
        "log_config_partial": "Chốt từng phần:",
        "log_config_sltp": "SL/TP:",
        "log_config_symbol": "Symbol:",
        "log_config_tele": "Telegram:",
        "log_config_title": "\n--- CẤU HÌNH ---",
        "log_config_visible": "SL TP hiện:",
        "log_connected": "✅ Đã kết nối:",
        "log_copy_close": "✂️ COPY CLOSE:",
        "log_copy_connected_master": "📡 MASTER ONLINE:",
        "log_copy_connected_slave": "🔗 SLAVE CONNECTED:",
        "log_copy_err": "❌ COPY ERROR:",
        "log_copy_start": "🔗 COPY TRADE: Đã khởi động ({role})",
        "log_fail": "❌ ĐÓNG THẤT BẠI:",
        "log_ignored_trades": "⚠️ Bỏ qua {count} lệnh Master cũ khi khởi động.",
        "log_monitor_start": "🚀 BẮT ĐẦU GIÁM SÁT...",
        "log_monitor_stop": "⏹️ ĐÃ DỪNG GIÁM SÁT.",
        "log_move_be_ok": "✅ ĐÃ DỜI BE:",
        "log_partial_skip_min": "⚠️ Bỏ qua chốt lời: Volume {vol} không thể chia nhỏ (Min: {min})",
        "log_signal": "⚠️ TÍN HIỆU CẮT:",
    },
    "EN": {
        "err_algo": "⚠️ WARNING: Algo Trading is OFF. Enable Algo Trading before trading.",
        "err_parse_r": "⚠️ Error parsing Partial R levels",
        "log_algo_off": "Algo Trading: OFF",
        "log_algo_on": "Algo Trading: ON",
        "log_closed": "✅ CLOSED:",
        "log_config_bal": "Balance SL/TP:",
        "log_config_be": "Auto BE:",
        "log_config_gold": "Gold SL/TP:",
        "log_config_magic": "Magic:",
        "log_config_partial": "Partial Close:",
        "log_config_sltp": "SL/TP:",
        "log_config_symbol": "Symbol:",
        "log_config_tele": "Telegram:",
        "log_config_title": "\n--- CONFIGURATION ---",
        "log_config_visible": "Visible SL/TP:",
        "log_connected": "✅ Connected:",
        "log_copy_close": "✂️ COPY CLOSE:",
        "log_copy_connected_master": "📡 MASTER ONLINE:",
        "log_copy_connected_slave": "🔗 SLAVE CONNECTED:",
        "log_copy_err": "❌ COPY ERROR:",
        "log_copy_start": "🔗 COPY TRADE: Started ({role})",
        "log_fail": "❌ CLOSE FAILED:",
        "log_ignored_trades": "⚠️ Ignored {count} existing Master trades.",
        "log_monitor_start": "🚀 STARTING MONITOR...",
        "log_monitor_stop": "⏹️ MONITOR STOPPED.",
        "log_move_be_ok": "✅ BE MOVED:",
        "log_partial_skip_min": "⚠️ Skip Partial: Volume {vol} too small (Min: {min})",
        "log_signal": "⚠️ EXIT SIGNAL:",
    },
}

CURRENT_LANG = "VN"


def T(key: str) -> str:
    return LANG.get(CURRENT_LANG, LANG["VN"]).get(key, key)
