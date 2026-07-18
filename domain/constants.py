# -*- coding: utf-8 -*-
"""Shared path / version constants."""
from __future__ import annotations

import json
import os

APP_NAME = "OAK MANAGER"
VERSION = "v3.17.0"
BUILD = 3170

CONFIG_FILE = "profiles.json"
SETTINGS_FILE = "settings.json"
TRADES_FILE = "trades.json"
PENDING_PARTIALS_FILE = "pending_partials.json"
SESSION_RECOVERY_FILE = "session_state.json"
DEFAULT_TELEGRAM_TOKEN = ""
MANUAL_TRENDS_FILE = "manual_trends.json"
MONDAY_SNAPSHOT_FILE = "monday_snapshot.json"
TUESDAY_SNAPSHOT_FILE = "tuesday_snapshot.json"
WEDNESDAY_SNAPSHOT_FILE = "wednesday_snapshot.json"
THURSDAY_SNAPSHOT_FILE = "thursday_snapshot.json"
FRIDAY_SNAPSHOT_FILE = "friday_snapshot.json"
MIMO_BOT_CONFIG = "config.json"
MIMO_QUEUE_FILE = "mimo_queue.json"
MIMO_RESULT_FILE = "mimo_result.json"

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
