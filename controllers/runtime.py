# -*- coding: utf-8 -*-
"""Bind domain globals into controller modules (mixin free-name resolution).

Controller methods were extracted from App and still reference names like
``T``, ``ctk``, ``mt5``, ``load_json`` as module-level free variables. Those
names live on ``OAK_Hidden_SLTP_Manager``; this binder injects them after
the domain module is fully loaded — avoiding circular imports at class body time.
"""
from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Iterable, Optional

_CONTROLLER_MODULES = (
    "controllers.monitor_controller",
    "controllers.profile_controller",
    "controllers.signal_controller",
    "controllers.copy_trade_controller",
    "controllers.pending_controller",
    "controllers.dashboard_controller",
    "controllers.app_shell_controller",
)

# Names typically used as free variables in extracted App methods
_OAK_NAMES = (
    "T",
    "CURRENT_LANG",
    "LANG",
    "load_json",
    "save_json",
    "resource_path",
    "SETTINGS_FILE",
    "CONFIG_FILE",
    "VERSION",
    "BUILD",
    "APP_NAME",
    "AppState",
    "SQLiteStore",
    "ProfileStore",
    "SignalProcessSupervisor",
    "SignalsTab",
    "ProfilesTab",
    "BaseTab",
    "CopyTradeManager",
    "MonitorWorker",
    "FileLock",
    "TicketManager",
    "GhostOperator",
    "show_ghost_consent",
    "add_help_icon",
    "ToolTip",
    "get_natural_response",
    "get_filling_type",
    "send_order_with_retry",
    # Process registry (must be same list object as domain atexit cleanup)
    "_running_processes",
    "_cleanup_processes",
    "mt5",
    "ctk",
    "tkinter",
    "ttk",
    "datetime",
    "timedelta",
    "threading",
    "subprocess",
    "os",
    "sys",
    "json",
    "time",
    "re",
    "winsound",
    "oak_trading_reminders",
    "urllib",
    "random",
    "ctypes",
    "get_latest_display_signal",
    "_mimo_bot_chat_id",
    "_mimo_bot_token",
)


def bind_oak_globals(
    oak_module: ModuleType,
    extra_modules: Optional[Iterable[ModuleType]] = None,
) -> None:
    """Copy shared symbols from domain module into controllers (+ optional targets)."""
    payload = {}
    for name in _OAK_NAMES:
        if hasattr(oak_module, name):
            payload[name] = getattr(oak_module, name)

    # Always share process registry list (even if name was missing from explicit set)
    if hasattr(oak_module, "_running_processes"):
        payload["_running_processes"] = oak_module._running_processes
    if hasattr(oak_module, "_cleanup_processes"):
        payload["_cleanup_processes"] = oak_module._cleanup_processes

    # Standard libraries often referenced bare in methods
    import customtkinter as ctk
    import MetaTrader5 as mt5
    import tkinter
    from tkinter import ttk
    from datetime import datetime, timedelta
    import threading
    import subprocess
    import os
    import sys as _sys
    import json
    import time
    import re
    import random
    import urllib.request
    import urllib.parse
    import urllib
    try:
        import winsound
    except Exception:
        winsound = None  # type: ignore
    try:
        import ctypes
    except Exception:
        ctypes = None  # type: ignore

    payload.setdefault("ctk", ctk)
    payload.setdefault("mt5", mt5)
    payload.setdefault("tkinter", tkinter)
    payload.setdefault("ttk", ttk)
    payload.setdefault("datetime", datetime)
    payload.setdefault("timedelta", timedelta)
    payload.setdefault("threading", threading)
    payload.setdefault("subprocess", subprocess)
    payload.setdefault("os", os)
    payload.setdefault("sys", _sys)
    payload.setdefault("json", json)
    payload.setdefault("time", time)
    payload.setdefault("re", re)
    payload.setdefault("random", random)
    payload.setdefault("urllib", urllib)
    if winsound is not None:
        payload.setdefault("winsound", winsound)
    if ctypes is not None:
        payload.setdefault("ctypes", ctypes)

    # utils helpers used by dashboard cards
    try:
        from utils import get_latest_display_signal

        payload.setdefault("get_latest_display_signal", get_latest_display_signal)
    except Exception:
        pass

    targets = []
    for mod_name in _CONTROLLER_MODULES:
        try:
            targets.append(importlib.import_module(mod_name))
        except Exception:
            continue
    if extra_modules:
        targets.extend(list(extra_modules))

    for mod in targets:
        for k, v in payload.items():
            setattr(mod, k, v)

    # Defensive: also patch monitor_controller with a local fallback list
    # if domain somehow lacked the symbol (should not happen).
    mon = importlib.import_module("controllers.monitor_controller")
    if not hasattr(mon, "_running_processes") or mon._running_processes is None:
        mon._running_processes = []
