# -*- coding: utf-8 -*-
"""ROBOT SLTP Pro trading domain layer (lazy re-exports)."""
from __future__ import annotations

from domain.constants import (  # noqa: F401
    APP_NAME,
    VERSION,
    BUILD,
    CONFIG_FILE,
    SETTINGS_FILE,
    TRADES_FILE,
    SESSION_RECOVERY_FILE,
    _oak_enginecore_token,
    _oak_enginecore_chat_id,
)
from domain.json_io import load_json, save_json, resource_path  # noqa: F401
from domain.i18n import LANG, CURRENT_LANG, T  # noqa: F401
def __getattr__(name: str):
    """Load optional trading helpers only when a caller explicitly uses them."""
    if name in {"get_filling_type", "send_order_with_retry"}:
        from domain import mt5_orders

        return getattr(mt5_orders, name)
    if name == "TicketManager":
        from domain.ticket_manager import TicketManager

        return TicketManager
    if name == "FileLock":
        from domain.file_lock import FileLock

        return FileLock
    if name == "get_start_day_balance":
        from domain.balance import get_start_day_balance

        return get_start_day_balance
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
    "CopyTradeManager",
    "MonitorWorker",
    "_oak_enginecore_token",
    "_oak_enginecore_chat_id",
]
