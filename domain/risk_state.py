"""Persistent account equity high-water mark for the pre-trade risk gate."""
from __future__ import annotations

import os
from dataclasses import dataclass

from domain.file_lock import FileLock
from domain.json_io import load_json, save_json


@dataclass(frozen=True)
class EquityHighWaterMark:
    account_id: str
    peak_equity: float | None


class EquityHighWaterMarkStore:
    """Persist the highest observed equity per MT5 account.

    The store never lowers a high-water mark. A missing state is intentional:
    callers must explicitly initialize it from trusted account evidence before
    live execution can be allowed.
    """

    def __init__(self, root_dir: str, account_id: str):
        self.root_dir = os.path.abspath(root_dir)
        self.account_id = str(account_id).strip()
        if not self.account_id:
            raise ValueError("account_id is required")
        safe_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in self.account_id)
        self.path = os.path.join(self.root_dir, f"risk_equity_hwm_{safe_id}.json")
        self.lock_path = f"{self.path}.lock"

    def read(self) -> EquityHighWaterMark:
        data = load_json(self.path, None)
        if not isinstance(data, dict):
            return EquityHighWaterMark(self.account_id, None)
        try:
            peak = float(data["peak_equity"])
        except (KeyError, TypeError, ValueError):
            peak = None
        return EquityHighWaterMark(self.account_id, peak)

    def initialize(self, peak_equity: float) -> EquityHighWaterMark:
        value = float(peak_equity)
        if value <= 0:
            raise ValueError("peak_equity must be positive")
        with FileLock(self.lock_path, timeout=3.0) as lock:
            if lock is None:
                raise TimeoutError("risk state lock timed out")
            current = self.read().peak_equity
            if current is not None and current != value:
                raise ValueError("risk high-water mark already initialized")
            save_json(self.path, {"account_id": self.account_id, "peak_equity": value})
        return self.read()

    def observe(self, equity: float) -> EquityHighWaterMark:
        value = float(equity)
        if value <= 0:
            raise ValueError("equity must be positive")
        with FileLock(self.lock_path, timeout=3.0) as lock:
            if lock is None:
                raise TimeoutError("risk state lock timed out")
            current = self.read().peak_equity
            if current is None:
                return EquityHighWaterMark(self.account_id, None)
            if value > current:
                save_json(self.path, {"account_id": self.account_id, "peak_equity": value})
                current = value
        return EquityHighWaterMark(self.account_id, current)
