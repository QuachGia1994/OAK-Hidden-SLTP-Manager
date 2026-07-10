# -*- coding: utf-8 -*-
"""Ticket persistence — one trades file per profile (multi-process safe)."""
from __future__ import annotations

import re
import threading
import time

from domain.constants import TRADES_FILE
from domain.json_io import load_json, save_json

# Per-file caches (never share one cache across profiles / processes).
_TRADES_CACHES: dict[str, dict] = {}
_TRADES_LOCK = threading.Lock()


def trades_file_for_profile(profile_name: str | None) -> str:
    """Return trades_<safe_profile>.json path for isolation across monitors."""
    if not profile_name:
        return TRADES_FILE
    safe = re.sub(r"[^\w\-]", "_", str(profile_name).strip()) or "default"
    return f"trades_{safe}.json"


class TicketManager:
    def __init__(self, file_path=None, profile_name=None):
        if file_path is None:
            file_path = trades_file_for_profile(profile_name)
        self.file_path = file_path
        self._ensure_loaded()

    def _ensure_loaded(self):
        with _TRADES_LOCK:
            if self.file_path not in _TRADES_CACHES:
                data = load_json(self.file_path)
                if not isinstance(data, dict):
                    data = {}
                _TRADES_CACHES[self.file_path] = data

    def get_ticket(self, ticket_id):
        with _TRADES_LOCK:
            cache = _TRADES_CACHES.get(self.file_path) or {}
            return cache.get(str(ticket_id), {}).copy()

    def update_ticket(self, ticket_id, **kwargs):
        with _TRADES_LOCK:
            if self.file_path not in _TRADES_CACHES:
                data = load_json(self.file_path)
                _TRADES_CACHES[self.file_path] = data if isinstance(data, dict) else {}
            cache = _TRADES_CACHES[self.file_path]
            tid = str(ticket_id)
            if tid not in cache:
                cache[tid] = {"created_at": time.time()}
            for k, v in kwargs.items():
                cache[tid][k] = v
            save_json(self.file_path, cache)
