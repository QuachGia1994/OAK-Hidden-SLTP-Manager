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
#: Telegram chat/admin IDs are routing targets, not credentials — the bot token
#: is the only Telegram secret and it lives in the Windows keyring.
_SENSITIVE_KEYS = frozenset({
    "tele_token", "password", "secret", "token",
})

#: Marker persisted in profiles.json when the real token lives in the keyring.
_VAULT_MARKER = "__vault__"

#: Characters a UI may use to render a masked secret; never a real token.
_MASK_CHARS = frozenset("•*·.… ")

#: Fields relevant for the profiles UI (excluded: pure execution internals).
_PUBLIC_KEYS = (
    "profile_name", "path", "mt5_portable", "magic", "visible_sltp",
    "symbol", "tele_chat", "tele_admin",
    "use_balance_sltp", "balance_sl_pct", "balance_tp_pct",
    "partial_r", "partial_pct", "auto_be", "sl", "tp", "gold_sl", "gold_tp",
    "copy_role", "copy_channel", "copy_max_daily_trades", "copy_max_lot_per_trade",
    "copy_max_exposure", "copy_kill_switch", "copy_stale_threshold",
    "copy_lot_mode", "copy_lot_value", "copy_ignore_list", "copy_stealth", "copy_max_one",
    "signal_execution_enabled", "signal_lot", "signal_magic",
)

# Full profile editing is intentionally limited to non-secret configuration.
# Telegram tokens, account credentials, and arbitrary execution internals never
# cross the IPC boundary, even when a caller sends them in an update payload.
_EDITABLE_KEYS = frozenset(
    key for key in _PUBLIC_KEYS
    if key not in {"profile_name", "signal_execution_enabled", "signal_lot", "signal_magic"}
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
    "copy_max_one", "copy_lot_mode", "copy_lot_value",
)

#: Read-side defaults matching domain/copy_trade_manager.py for legacy profiles
#: that never stored the copy lot fields.
_COPY_LOT_DEFAULTS = {"copy_lot_mode": "Fixed", "copy_lot_value": "0.01"}


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
    copy = {k: config.get(k) for k in _COPY_KEYS}
    # Legacy profiles predate the lot fields; surface the domain defaults so the
    # UI never round-trips a null into a mode the copy worker treats as a string.
    for key, default in _COPY_LOT_DEFAULTS.items():
        if copy.get(key) is None:
            copy[key] = default
    return {"profile": profile_name, "exists": bool(config), "copy": copy}


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


def add_profile(profile_name: str, path: str = "", magic: int = -1) -> dict:
    """Create a NEW profile in profiles.json (whitelisted fields only)."""
    magic = _coerce_magic(magic)
    name = str(profile_name or "").strip()
    if not name:
        raise ValueError("profile_name required")
    profiles = load_profiles()
    if name in profiles:
        raise ValueError(f"profile {name} already exists")
    profiles[name] = {
        "path": str(path or ""),
        "mt5_portable": False,
        "magic": int(magic) if magic not in (None, "") else -1,
        "visible_sltp": False,
        "sl": 0,
        "tp": 0,
        "copy_role": "None",
    }
    _atomic_write_profiles(profiles)
    return public_profile(name, profiles[name]) | {"status": "stopped", "pid": None}


def _coerce_magic(value) -> int:
    """Coerce a UI-supplied magic number to int.

    Empty/missing becomes -1 (the add-form default). bool is rejected
    explicitly because bool is an int subclass in Python.
    """
    if isinstance(value, bool):
        raise ValueError("magic must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = str(value or "").strip()
    if not text:
        return -1
    try:
        return int(text)
    except (TypeError, ValueError) as exc:
        raise ValueError("magic must be an integer") from exc


def _normalise_name(value: str) -> str:
    name = " ".join(str(value or "").split())
    if not name:
        raise ValueError("profile_name required")
    return name


def _unique_name(existing: set[str], base: str) -> str:
    root = _normalise_name(base)
    if root not in existing:
        return root
    index = 2
    while f"{root} {index}" in existing:
        index += 1
    return f"{root} {index}"


def update_profile(profile_name: str, updates: dict) -> dict:
    """Update whitelisted non-secret profile fields, including a rename."""
    current_name = _normalise_name(profile_name)
    profiles = load_profiles()
    if current_name not in profiles:
        raise ValueError(f"profile '{current_name}' not found")
    updates = dict(updates) if isinstance(updates, dict) else {}
    forbidden = sorted(set(updates) & _SENSITIVE_KEYS)
    if forbidden:
        raise ValueError("sensitive profile fields cannot be updated through IPC")
    if "magic" in updates:
        updates["magic"] = _coerce_magic(updates["magic"])
    next_name = _normalise_name(updates.get("profile_name", current_name))
    if next_name != current_name and next_name in profiles:
        raise ValueError(f"profile {next_name} already exists")
    config = dict(profiles[current_name])
    for key, value in updates.items():
        if key in _EDITABLE_KEYS:
            config[key] = value
    config.pop("profile_name", None)
    if next_name != current_name:
        profiles.pop(current_name, None)
    profiles[next_name] = config
    _atomic_write_profiles(profiles)
    return public_profile(next_name, config) | {"status": "stopped", "pid": None}


def duplicate_profile(profile_name: str, new_name: str = "") -> dict:
    """Duplicate a profile entirely inside the sidecar without leaking secrets."""
    source_name = _normalise_name(profile_name)
    profiles = load_profiles()
    if source_name not in profiles:
        raise ValueError(f"profile '{source_name}' not found")
    target = _unique_name(set(profiles), new_name or f"{source_name} Copy")
    config = dict(profiles[source_name])
    profiles[target] = config
    _atomic_write_profiles(profiles)
    return public_profile(target, config) | {"status": "stopped", "pid": None}


def delete_profile(profile_name: str) -> dict:
    """Delete a stopped profile; running-state protection is manager-owned."""
    name = _normalise_name(profile_name)
    profiles = load_profiles()
    if name not in profiles:
        raise ValueError(f"profile '{name}' not found")
    profiles.pop(name)
    _atomic_write_profiles(profiles)
    return {"profile": name, "deleted": True}


# ---------------------------------------------------------------------- #
# Telegram bot token — keyring-backed, write-only across IPC
# ---------------------------------------------------------------------- #
def _secret_store():
    """Import the repo-root ``secret_store`` lazily; None when unavailable.

    Imported on demand so merely listing profiles never pulls in the keyring
    stack (or its logger side effects).
    """
    repo_root = str(Path(__file__).resolve().parents[3])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        import secret_store
    except Exception:
        return None
    return secret_store


def _keyring_available(store) -> bool:
    if store is None:
        return False
    try:
        return bool(store.is_keyring_available())
    except Exception:
        return False


def _has_vault_token(store, profile_name: str) -> bool:
    """True when the keyring holds a token for this profile (value discarded)."""
    try:
        return bool(store.get_token_for_profile(profile_name))
    except Exception:
        return False


def secret_status(profile_name: str) -> dict:
    """Presence flags only — the token value never leaves the supervisor."""
    name = _normalise_name(profile_name)
    profiles = load_profiles()
    if name not in profiles:
        raise ValueError(f"profile '{name}' not found")
    raw = str(profiles[name].get("tele_token") or "").strip()
    store = _secret_store()
    available = _keyring_available(store)
    if raw and raw != _VAULT_MARKER:
        configured = True          # legacy plaintext token still in profiles.json
    elif available:
        configured = _has_vault_token(store, name)
    else:
        configured = raw == _VAULT_MARKER
    return {"profile": name, "tele_token_configured": configured,
            "keyring_available": available}


def set_tele_token(profile_name: str, token: str) -> dict:
    """Store a Telegram bot token in the keyring; profiles.json keeps a marker."""
    name = _normalise_name(profile_name)
    value = str(token or "").strip()
    if not value or value == _VAULT_MARKER or set(value) <= _MASK_CHARS:
        raise ValueError("a real Telegram bot token is required")
    profiles = load_profiles()
    if name not in profiles:
        raise ValueError(f"profile '{name}' not found")
    store = _secret_store()
    if not _keyring_available(store):
        raise RuntimeError("Windows keyring unavailable; token was not stored")
    store.store_secret(name, "tele_token", value)
    profiles[name]["tele_token"] = _VAULT_MARKER
    _atomic_write_profiles(profiles)
    return secret_status(name)


def clear_tele_token(profile_name: str) -> dict:
    """Delete the keyring token; only then drop the profiles.json marker."""
    name = _normalise_name(profile_name)
    profiles = load_profiles()
    if name not in profiles:
        raise ValueError(f"profile '{name}' not found")
    raw = str(profiles[name].get("tele_token") or "").strip()
    store = _secret_store()
    available = _keyring_available(store)
    had_vault_token = available and _has_vault_token(store, name)
    deleted = False
    if store is not None:
        try:
            deleted = bool(store.delete_secret(name, "tele_token"))
        except Exception:
            deleted = False
    # A vault token still exists unless the keyring says otherwise; when the
    # keyring is unreadable, a marker must be treated as still stored.
    vault_pending = had_vault_token if available else raw == _VAULT_MARKER
    cleared = deleted or not vault_pending
    if cleared and raw:
        profiles[name]["tele_token"] = ""
        _atomic_write_profiles(profiles)
    status = secret_status(name)
    return {"profile": name, "cleared": cleared,
            "tele_token_configured": status["tele_token_configured"],
            "keyring_available": status["keyring_available"]}


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
    def _worker_states(self) -> dict[str, tuple[int, int | None]]:
        """Snapshot {profile: (pid, exit_code)} for every tracked worker.

        ``poll()`` is non-blocking; a process that already exited reports its
        real exit code so the UI never shows a dead worker as running.
        """
        with self._lock:
            return {name: (proc.pid, proc.poll()) for name, proc in self._workers.items()}

    def running_workers(self) -> list[str]:
        """Names of tracked workers whose process is still alive."""
        return [name for name, (_pid, code) in self._worker_states().items() if code is None]

    def list_profiles(self) -> dict:
        profiles = load_profiles()
        states = self._worker_states()
        result = []
        for name, config in profiles.items():
            item = public_profile(name, config)
            state = states.get(name)
            if state is None:
                item["status"] = "stopped"
                item["pid"] = None
            else:
                pid, exit_code = state
                item["status"] = "running" if exit_code is None else "exited"
                item["pid"] = pid
                item["exit_code"] = exit_code
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

    def add_profile(self, profile_name: str, path: str = "", magic: int = -1) -> dict:
        return add_profile(profile_name, path=path, magic=magic)

    def update_profile(self, profile_name: str, updates: dict) -> dict:
        next_name = str((updates or {}).get("profile_name") or profile_name).strip()
        if next_name != profile_name:
            with self._lock:
                proc = self._workers.get(profile_name)
            if proc is not None and proc.poll() is None:
                raise RuntimeError("stop this profile before renaming it")
        return update_profile(profile_name, updates)

    def duplicate_profile(self, profile_name: str, new_name: str = "") -> dict:
        return duplicate_profile(profile_name, new_name)

    # -- Telegram token (write-only; never returned over IPC) ----------- #
    def secret_status(self, profile_name: str) -> dict:
        return secret_status(profile_name)

    def set_tele_token(self, profile_name: str, token: str) -> dict:
        return set_tele_token(profile_name, token)

    def clear_tele_token(self, profile_name: str) -> dict:
        return clear_tele_token(profile_name)

    def delete_profile(self, profile_name: str) -> dict:
        with self._lock:
            proc = self._workers.get(profile_name)
        if proc is not None and proc.poll() is None:
            raise RuntimeError("stop this profile before deleting it")
        return delete_profile(profile_name)

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

        if getattr(sys, "frozen", False):
            cmd = [self._python, "profile-worker", "--profile", profile_name]
            cwd = None
        else:
            cmd = [self._python, "-m", "oak_core", "profile-worker", "--profile", profile_name]
            cwd = str(Path(__file__).resolve().parents[3] / "python")

        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        with self._lock:
            self._workers[profile_name] = proc

        def _drain(stream):
            for line in stream:
                self._log(f"[worker:{profile_name}] {line.rstrip()}")

        threading.Thread(target=_drain, args=(proc.stderr,), daemon=True, name=f"wlog-{profile_name}").start()
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
