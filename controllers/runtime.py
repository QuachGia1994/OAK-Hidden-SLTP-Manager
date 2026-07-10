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
    try:
        import winsound
    except Exception:
        winsound = None  # type: ignore

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
    if winsound is not None:
        payload.setdefault("winsound", winsound)

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
