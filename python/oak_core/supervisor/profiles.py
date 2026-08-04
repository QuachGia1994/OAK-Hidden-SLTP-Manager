# -*- coding: utf-8 -*-
"""Profile management for the oak-core supervisor (Phase 2, Edit prompt.txt §9).

The supervisor owns the list of configured MT5 profiles and the lifecycle of
one profile-worker subprocess per profile.  Workers run the SAME oak-core
binary in ``profile-worker`` mode, so each worker gets its own MT5 connection
(never share a mutable MT5 connection across profiles — §2).

Profile data comes from ``profiles.json`` at the repo root.  Sensitive fields
(tele tokens, credentials) are never returned to the frontend.
"""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from ..ipc.protocol import error_payload

#: Fields that must never cross the IPC boundary to React (§5).
_SENSITIVE_KEYS = frozenset({
    "tele_token", "tele_chat", "tele_admin", "password", "secret", "token",
})

#: Fields relevant for the profiles UI (excluded: pure execution internals).
_PUBLIC_KEYS = (
    "profile_name", "path", "mt5_portable", "magic", "visible_sltp",
    "partial_r", "partial_pct", "auto_be", "sl", "tp", "gold_sl", "gold_tp",
    "copy_role", "copy_channel", "copy_max_daily_trades", "copy_max_lot_per_trade",
    "copy_max_exposure", "copy_kill_switch", "copy_stale_threshold",
    "signal_execution_enabled", "signal_lot", "signal_magic",
)


def _data_root() -> Path:
    """Directory holding profiles.json / settings.json / data/.

    Priority:
    1. OAK_DATA_DIR env (explicit, used by the Rust shell in prod);
    2. current working directory if it already contains profiles.json
       (dev: repo root when launched with that cwd);
    3. repo root derived from the source layout (dev fallback).
    """
    env_dir = os.environ.get("OAK_DATA_DIR", "")
    if env_dir:
        return Path(env_dir)
    cwd = Path.cwd()
    if (cwd / "profiles.json").is_file():
        return cwd
    here = Path(__file__).resolve()
    return here.parents[3]  # python/oak_core/supervisor -> repo root


def profiles_path() -> Path:
    """profiles.json lives at the data root."""
    return _data_root() / "profiles.json"


def load_profiles() -> dict:
    """Return {profile_name: config} from profiles.json. Never raises."""
    try:
        data = json.loads(profiles_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def public_profile(profile_name: str, config: dict) -> dict:
    """Project one profile for the UI: name + non-sensitive fields only."""
    out = {"profile_name": profile_name}
    for key in _PUBLIC_KEYS:
        if key in config:
            out[key] = config[key]
    out["exists"] = bool(config)
    return out


#: Hidden SL/TP fields editable from the UI (§9 Phase 5).
_SLTP_KEYS = (
    "visible_sltp", "sl", "tp", "gold_sl", "gold_tp",
    "use_balance_sltp", "balance_sl_pct", "balance_tp_pct",
    "partial_r", "partial_pct", "auto_be", "magic",
)

#: Copy-trading fields editable from the UI (§9 Phase 5).
_COPY_KEYS = (
    "copy_role", "copy_channel", "copy_max_daily_trades",
    "copy_max_lot_per_trade", "copy_max_exposure", "copy_kill_switch",
    "copy_stale_threshold", "copy_ignore_list", "copy_stealth",
    "copy_max_one",
)


def _atomic_write_profiles(profiles: dict) -> None:
    """Write profiles.json atomically (temp file + replace)."""
    path = profiles_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def read_sltp(profile_name: str) -> dict:
    config = load_profiles().get(profile_name, {})
    return {"profile": profile_name, "exists": bool(config),
            "sltp": {k: config.get(k) for k in _SLTP_KEYS}}


def read_copy(profile_name: str) -> dict:
    config = load_profiles().get(profile_name, {})
    return {"profile": profile_name, "exists": bool(config),
            "copy": {k: config.get(k) for k in _COPY_KEYS}}


def update_sltp(profile_name: str, updates: dict) -> dict:
    """Merge SL/TP updates into profiles.json (only whitelisted keys)."""
    profiles = load_profiles()
    if profile_name not in profiles:
        raise KeyError(profile_name)
    config = profiles[profile_name]
    allowed = set(_SLTP_KEYS)
    for key, value in (updates or {}).items():
        if key in allowed:
            config[key] = value
    _atomic_write_profiles(profiles)
    return read_sltp(profile_name)


def update_copy(profile_name: str, updates: dict) -> dict:
    """Merge copy-trading updates into profiles.json (whitelisted keys only)."""
    profiles = load_profiles()
    if profile_name not in profiles:
        raise KeyError(profile_name)
    config = profiles[profile_name]
    allowed = set(_COPY_KEYS)
    for key, value in (updates or {}).items():
        if key in allowed:
            config[key] = value
    _atomic_write_profiles(profiles)
    return read_copy(profile_name)


class ProfileManager:
    """Owns profile-worker subprocesses started by the supervisor."""

    def __init__(self, *, python_executable: str | None = None, log=None):
        self._python = python_executable or sys.executable
        self._log = log or (lambda msg: print(msg, file=sys.stderr))
        self._workers: dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def list_profiles(self) -> dict:
        profiles = load_profiles()
        result = []
        for name, config in profiles.items():
            item = public_profile(name, config)
            item["status"] = "running" if name in self._workers else "stopped"
            result.append(item)
        return {"profiles": result}

    def profile_status(self, profile_name: str) -> dict:
        with self._lock:
            proc = self._workers.get(profile_name)
        if proc is None:
            return public_profile(profile_name, load_profiles().get(profile_name, {})) | {
                "status": "stopped",
                "pid": None,
            }
        poll = proc.poll()
        return public_profile(profile_name, load_profiles().get(profile_name, {})) | {
            "status": "running" if poll is None else "exited",
            "pid": proc.pid,
            "exit_code": poll,
        }

    # ------------------------------------------------------------------ #
    # Phase 5 — hidden SL/TP + copy config (read/update, whitelisted)
    # ------------------------------------------------------------------ #
    def read_sltp(self, profile_name: str) -> dict:
        return read_sltp(profile_name)

    def read_copy(self, profile_name: str) -> dict:
        return read_copy(profile_name)

    def update_sltp(self, profile_name: str, updates: dict) -> dict:
        return update_sltp(profile_name, updates)

    def update_copy(self, profile_name: str, updates: dict) -> dict:
        return update_copy(profile_name, updates)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start_profile(self, profile_name: str) -> dict:
        profiles = load_profiles()
        if profile_name not in profiles:
            raise KeyError(profile_name)
        with self._lock:
            existing = self._workers.get(profile_name)
            if existing is not None and existing.poll() is None:
                return {"profile": profile_name, "pid": existing.pid, "started": False, "reason": "already running"}

        cmd = [self._python, "-m", "oak_core", "profile-worker", "--profile", profile_name]
        proc = subprocess.Popen(
            cmd,
            cwd=str(Path(__file__).resolve().parents[3] / "python"),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        with self._lock:
            self._workers[profile_name] = proc
        self._log(f"[profiles] started worker for {profile_name} (pid={proc.pid})")
        return {"profile": profile_name, "pid": proc.pid, "started": True}

    def stop_profile(self, profile_name: str, timeout_seconds: float = 8.0) -> dict:
        with self._lock:
            proc = self._workers.get(profile_name)
        if proc is None:
            return {"profile": profile_name, "stopped": False, "reason": "not running"}
        try:
            proc.terminate()
            proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        with self._lock:
            self._workers.pop(profile_name, None)
        return {"profile": profile_name, "stopped": True}

    def stop_all(self, timeout_seconds: float = 5.0) -> dict:
        stopped = []
        for name in list(self._workers.keys()):
            stopped.append(self.stop_profile(name, timeout_seconds=timeout_seconds))
        return {"stopped": stopped}
