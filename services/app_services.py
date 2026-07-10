# -*- coding: utf-8 -*-
"""Explicit app dependencies (controllers prefer this over free-name globals)."""
from __future__ import annotations

import os
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Optional


class AppServices:
    """Composition-root services shared by controllers."""

    def __init__(self, oak: ModuleType, project_root: Optional[str] = None):
        self.oak = oak
        self.project_root = Path(
            project_root
            or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ).resolve()
        self.log_dir = self.project_root / "logs"
        self.log_file = self.log_dir / "app.log"

    # --- i18n ---
    def T(self, key: str) -> str:
        try:
            import domain.i18n as i18n

            return i18n.T(key)
        except Exception:
            fn = getattr(self.oak, "T", None)
            return fn(key) if callable(fn) else str(key)

    def set_lang(self, lang: str) -> None:
        import domain.i18n as i18n

        i18n.CURRENT_LANG = lang
        try:
            self.oak.CURRENT_LANG = lang
        except Exception:
            pass

    @property
    def CURRENT_LANG(self) -> str:
        try:
            import domain.i18n as i18n

            return i18n.CURRENT_LANG
        except Exception:
            return getattr(self.oak, "CURRENT_LANG", "VN")

    # --- persistence ---
    @property
    def load_json(self) -> Callable:
        from domain.json_io import load_json

        return load_json

    @property
    def save_json(self) -> Callable:
        from domain.json_io import save_json

        return save_json

    @property
    def CONFIG_FILE(self) -> str:
        from domain.constants import CONFIG_FILE

        return CONFIG_FILE

    @property
    def SETTINGS_FILE(self) -> str:
        from domain.constants import SETTINGS_FILE

        return SETTINGS_FILE

    # --- domain classes ---
    def CopyTradeManager(self, *args, **kwargs) -> Any:
        from domain.copy_trade_manager import CopyTradeManager

        return CopyTradeManager(*args, **kwargs)

    def MonitorWorker(self, *args, **kwargs) -> Any:
        from domain.monitor_worker import MonitorWorker

        return MonitorWorker(*args, **kwargs)

    def SQLiteStore(self, *args, **kwargs) -> Any:
        from repositories.sqlite_store import SQLiteStore

        return SQLiteStore(*args, **kwargs)
