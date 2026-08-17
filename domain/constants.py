# -*- coding: utf-8 -*-
"""Shared runtime constants for ROBOT SLTP Pro."""
from __future__ import annotations

import json
import os

APP_NAME = "ROBOT SLTP Pro"
VERSION = "0.1.0"
BUILD = 100

CONFIG_FILE = "profiles.json"
SETTINGS_FILE = "settings.json"
TRADES_FILE = "trades.json"
PENDING_PARTIALS_FILE = "pending_partials.json"
SESSION_RECOVERY_FILE = "session_state.json"
DEFAULT_TELEGRAM_TOKEN = ""
OAK_ENGINECORE_CONFIG = "config.json"

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_oak_enginecore_token = ""
_oak_enginecore_chat_id = 0
try:
    with open(os.path.join(_ROOT, OAK_ENGINECORE_CONFIG), "r", encoding="utf-8") as _enginecore_file:
        _enginecore_cfg = json.load(_enginecore_file)
    _oak_enginecore_token = _enginecore_cfg.get("telegram_token", "")
    _oak_enginecore_chat_id = int(_enginecore_cfg.get("telegram_chat_id", 0))
except Exception:
    pass
