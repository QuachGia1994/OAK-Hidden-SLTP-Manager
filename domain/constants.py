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
MIMO_BOT_CONFIG = "config.json"

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_mimo_bot_token = ""
_mimo_bot_chat_id = 0
try:
    with open(os.path.join(_ROOT, MIMO_BOT_CONFIG), "r", encoding="utf-8") as _mf:
        _mimo_cfg = json.load(_mf)
    _mimo_bot_token = _mimo_cfg.get("telegram_token", "")
    _mimo_bot_chat_id = int(_mimo_cfg.get("telegram_chat_id", 0))
except Exception:
    pass
