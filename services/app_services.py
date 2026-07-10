# -*- coding: utf-8 -*-
"""Explicit app dependencies (reduces free-name / bind_oak_globals coupling)."""
from __future__ import annotations

import os
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Optional


class AppServices:
    """Composition-root services shared by controllers.

    Controllers should prefer ``self.services.*`` over free-name globals when available.
    """

    def __init__(self, oak: ModuleType, project_root: Optional[str] = None):
        self.oak = oak
        self.project_root = Path(
            project_root
            or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ).resolve()
        self.log_dir = self.project_root / "logs"
        self.log_file = self.log_dir / "app.log"

    # --- domain helpers ---
    def T(self, key: str) -> str:
        fn = getattr(self.oak, "T", None)
        return fn(key) if callable(fn) else str(key)

    @property
    def load_json(self) -> Callable:
        return self.oak.load_json

    @property
    def save_json(self) -> Callable:
        return self.oak.save_json

    @property
    def CONFIG_FILE(self) -> str:
        return getattr(self.oak, "CONFIG_FILE", "profiles.json")

    @property
    def SETTINGS_FILE(self) -> str:
        return getattr(self.oak, "SETTINGS_FILE", "settings.json")

    def CopyTradeManager(self, *args, **kwargs) -> Any:
        return self.oak.CopyTradeManager(*args, **kwargs)

    def SQLiteStore(self, *args, **kwargs) -> Any:
        return self.oak.SQLiteStore(*args, **kwargs)
