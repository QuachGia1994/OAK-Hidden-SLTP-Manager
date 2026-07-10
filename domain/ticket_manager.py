# -*- coding: utf-8 -*-
"""Ticket persistence."""
from __future__ import annotations

import threading
import time

from domain.constants import TRADES_FILE
from domain.json_io import load_json, save_json

_GLOBAL_TRADES_CACHE = None
_GLOBAL_TRADES_LOCK = threading.Lock()

class TicketManager:
    def __init__(self, file_path=TRADES_FILE):
        self.file_path = file_path
        self._ensure_loaded()

    def _ensure_loaded(self):
        global _GLOBAL_TRADES_CACHE
        with _GLOBAL_TRADES_LOCK:
            if _GLOBAL_TRADES_CACHE is None:
                _GLOBAL_TRADES_CACHE = load_json(self.file_path)

    def get_ticket(self, ticket_id):
        with _GLOBAL_TRADES_LOCK:
            # Return a copy to prevent external modification affecting cache without lock
            return _GLOBAL_TRADES_CACHE.get(str(ticket_id), {}).copy()

    def update_ticket(self, ticket_id, **kwargs):
        with _GLOBAL_TRADES_LOCK:
            tid = str(ticket_id)
            if tid not in _GLOBAL_TRADES_CACHE:
                _GLOBAL_TRADES_CACHE[tid] = {"created_at": time.time()}
            
            for k, v in kwargs.items():
                _GLOBAL_TRADES_CACHE[tid][k] = v
            
            # Save to disk immediately to persist state
            save_json(self.file_path, _GLOBAL_TRADES_CACHE)

