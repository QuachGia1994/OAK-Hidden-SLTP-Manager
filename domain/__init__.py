# -*- coding: utf-8 -*-
"""OAK trading domain layer (lazy re-exports)."""
from __future__ import annotations

from domain.constants import (  # noqa: F401
    APP_NAME,
    VERSION,
    BUILD,
    CONFIG_FILE,
    SETTINGS_FILE,
    TRADES_FILE,
    SESSION_RECOVERY_FILE,
    _mimo_bot_token,
    _mimo_bot_chat_id,
)
from domain.json_io import load_json, save_json, resource_path  # noqa: F401
from domain.i18n import LANG, CURRENT_LANG, T  # noqa: F401
from domain.mt5_orders import get_filling_type, send_order_with_retry  # noqa: F401
from domain.ticket_manager import TicketManager  # noqa: F401
from domain.file_lock import FileLock  # noqa: F401
from domain.balance import get_start_day_balance  # noqa: F401
from domain.ghost_operator import GhostOperator, show_ghost_consent, GHOST_LIB_AVAILABLE  # noqa: F401


def __getattr__(name: str):
    # Heavy modules: load on first access
    if name == "CopyTradeManager":
        from domain.copy_trade_manager import CopyTradeManager

        return CopyTradeManager
    if name == "MonitorWorker":
        from domain.monitor_worker import MonitorWorker

        return MonitorWorker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "APP_NAME",
    "VERSION",
    "BUILD",
    "CONFIG_FILE",
    "SETTINGS_FILE",
    "load_json",
    "save_json",
    "resource_path",
    "LANG",
    "CURRENT_LANG",
    "T",
    "get_filling_type",
    "send_order_with_retry",
    "TicketManager",
    "FileLock",
    "get_start_day_balance",
    "GhostOperator",
    "show_ghost_consent",
    "GHOST_LIB_AVAILABLE",
    "CopyTradeManager",
    "MonitorWorker",
    "_mimo_bot_token",
    "_mimo_bot_chat_id",
]
