"""Shared MT5 terminal launcher and profile connection service.

The MetaTrader5 Python package only reports ``-10003`` when its IPC client
cannot create or attach to a terminal.  This service makes the process
lifecycle explicit so each profile worker owns one terminal connection and can
surface a useful status to the desktop UI.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable, Iterable

from domain.file_lock import FileLock


@dataclass(frozen=True, slots=True)
class MT5LaunchResult:
    """Result of starting (when necessary) and connecting one MT5 profile."""

    ok: bool
    terminal_path: str
    process_started: bool
    process_id: int | None
    initialize_attempts: int
    last_error: tuple | None
    failure_code: str | None
    message: str


def normalize_terminal_path(raw_path: object) -> Path | None:
    """Return an absolute ``terminal64.exe`` path, or ``None`` when invalid."""
    if not raw_path:
        return None
    try:
        candidate = Path(os.path.expandvars(os.path.expanduser(str(raw_path))))
        candidate = candidate if candidate.is_absolute() else (Path.cwd() / candidate)
        candidate = candidate.resolve(strict=False)
    except (OSError, ValueError):
        return None
    if candidate.name.lower() != "terminal64.exe":
        return None
    if not candidate.is_file() or not candidate.parent.is_dir():
        return None
    # On Windows X_OK is permissive for executable extensions, while on POSIX
    # it still prevents selecting a readable-but-not-runnable file.
    if not os.access(candidate, os.R_OK | os.X_OK):
        return None
    return candidate


def discover_terminal_candidates() -> list[Path]:
    """Find installed/running MT5 terminals without changing profile config."""
    candidates: set[Path] = set()
    try:
        import psutil  # type: ignore
        for process in psutil.process_iter(["name", "exe", "cmdline"]):
            try:
                name = str(process.info.get("name") or "").lower()
                exe = process.info.get("exe")
                if name == "terminal64.exe" or (exe and str(exe).lower().endswith("terminal64.exe")):
                    path = normalize_terminal_path(exe)
                    if path:
                        candidates.add(path)
            except (psutil.Error, OSError):
                continue
    except ImportError:
        pass

    roots = [
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMFILES(X86)"),
        "D:/Program Files",
        "D:/Program Files (x86)",
        os.path.expandvars(r"%APPDATA%/MetaQuotes/Terminal"),
    ]
    for raw_root in roots:
        if not raw_root:
            continue
        root = Path(os.path.expandvars(os.path.expanduser(raw_root)))
        if not root.exists():
            continue
        try:
            for path in root.rglob("terminal64.exe"):
                normalized = normalize_terminal_path(path)
                if normalized:
                    candidates.add(normalized)
        except OSError:
            continue
    return sorted(candidates, key=lambda item: str(item).lower())


def _profile_matches_candidate(profile: Any, candidate: Path) -> bool:
    """Apply conservative broker hints when a profile provides them."""
    # A profile name (for example ``VantageDemo``) is often an account alias,
    # not part of the terminal installation folder.  Only broker/server are
    # safe folder hints; otherwise discovery must not reject a valid install.
    hints = [profile.get(key) for key in ("broker", "server") if isinstance(profile, dict)]
    hints = [str(value).lower() for value in hints if value]
    if not hints:
        return True
    haystack = str(candidate).lower()
    # Installation folders normally contain the broker name.  If they do not,
    # keep the candidate rather than silently writing a new path to profiles.
    return any(hint in haystack for hint in hints)


def _is_terminal_running(path: Path) -> tuple[bool, int | None]:
    try:
        import psutil  # type: ignore
        wanted = str(path).lower()
        for process in psutil.process_iter(["name", "exe"]):
            try:
                exe = str(process.info.get("exe") or "").lower()
                name = str(process.info.get("name") or "").lower()
                # Without an executable path we cannot prove that this is the
                # requested broker/profile terminal; launch an isolated one.
                if name == "terminal64.exe" and exe == wanted:
                    return True, int(process.pid)
            except (psutil.Error, OSError, ValueError):
                continue
    except ImportError:
        pass
    return False, None


def _popen_terminal(path: Path) -> Any:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    return subprocess.Popen(
        [str(path)],
        cwd=str(path.parent),
        shell=False,
        creationflags=creationflags,
    )


def _call_initialize(mt5_module: Any, path: Path, profile: Any) -> bool:
    portable = bool(profile.get("mt5_portable", False)) if isinstance(profile, dict) else False
    kwargs = {"path": str(path)}
    if portable:
        kwargs["portable"] = True
    try:
        return bool(mt5_module.initialize(**kwargs))
    except TypeError:
        # Small fakes and older package versions may not accept keyword path.
        return bool(mt5_module.initialize(str(path)))


def _initialize_and_validate_locked(
    mt5_module: Any,
    terminal_path: Path,
    profile_config: Any,
    *,
    lock_timeout_seconds: float,
) -> tuple[bool, tuple | None, str | None]:
    """Serialize MT5 IPC attach + identity validation across profile workers.

    MetaTrader5 exposes one current Python IPC connection per host/runtime and
    concurrent initialize calls from separate workers can race which terminal
    instance is attached. The race is especially visible when multiple OAK
    profiles start together. Keep shutdown, initialize, and identity validation
    in one cross-process critical section so a profile cannot validate one
    terminal and then execute against another connection selected by a peer.
    """
    lock_path = Path(__file__).resolve().parents[1] / ".mt5_profile_connection.lock"
    with FileLock(str(lock_path), timeout=max(1.0, float(lock_timeout_seconds))) as lock:
        if lock is None:
            return False, None, "CONNECTION_LOCK_TIMEOUT"

        # Let initialize() select the explicitly requested executable first.
        # Do not preflight terminal_info() here: another profile worker can
        # leave a stale/shared IPC session visible before this worker's first
        # initialize(), which would falsely look like an identity mismatch.
        try:
            initialized = _call_initialize(mt5_module, terminal_path, profile_config)
        except Exception as error:
            return False, (type(error).__name__, str(error)), "INITIALIZE_EXCEPTION"

        try:
            raw_error = mt5_module.last_error()
            last_error = tuple(raw_error) if raw_error else None
        except Exception:
            last_error = None

        if not initialized:
            return False, last_error, None

        try:
            terminal_info = mt5_module.terminal_info()
            account = mt5_module.account_info()
        except Exception as error:
            return False, (type(error).__name__, str(error)), "SESSION_QUERY_ERROR"

        if terminal_info is None or account is None:
            try:
                mt5_module.shutdown()
            except Exception:
                pass
            return False, last_error, "SESSION_UNAVAILABLE"
        if not _terminal_path_matches(terminal_info, profile_config):
            try:
                mt5_module.shutdown()
            except Exception:
                pass
            return False, last_error, "TERMINAL_PATH_MISMATCH"
        if not _account_matches(account, profile_config):
            # Drop the mismatched IPC session so a later worker cannot trade
            # against an account that failed the profile identity contract.
            try:
                mt5_module.shutdown()
            except Exception:
                pass
            return False, last_error, "ACCOUNT_MISMATCH"
        return True, last_error, None


def _profile_requires_account_identity(profile: Any) -> bool:
    """Return True when the profile can create live execution side effects."""
    if not isinstance(profile, dict):
        return False
    if str(profile.get("signal_execution_enabled", "")).strip().lower() in {"1", "true", "yes", "on"}:
        return True
    if str(profile.get("execution_enabled", "")).strip().lower() in {"1", "true", "yes", "on"}:
        return True
    copy_role = str(profile.get("copy_role", "")).strip().lower()
    return copy_role not in {"", "none", "null", "off", "disabled"}


def profile_session_validation_enabled(profile: Any) -> bool:
    """Return True when a caller has a concrete profile/session contract to validate."""
    if not isinstance(profile, dict):
        return False
    keys = (
        "path", "login_id", "login", "server", "broker",
        "signal_execution_enabled", "execution_enabled", "copy_role",
    )
    return any(profile.get(key) not in (None, "") for key in keys)


def _account_matches(account: Any, profile: Any) -> bool:
    if not isinstance(profile, dict) or account is None:
        return True
    expected_login = profile.get("login_id", profile.get("login"))
    expected_server = profile.get("server", profile.get("broker"))
    if expected_login in (None, "") and not expected_server:
        # A profile capable of sending trades must explicitly bind itself to an
        # account/server.  Path-only matching is insufficient because a single
        # MT5 terminal can be logged into a different account after restart.
        return not _profile_requires_account_identity(profile)
    if expected_login not in (None, ""):
        try:
            if int(getattr(account, "login", 0)) != int(expected_login):
                return False
        except (TypeError, ValueError):
            return False
    if expected_server:
        actual = str(getattr(account, "server", getattr(account, "company", ""))).strip().casefold()
        expected = str(expected_server).strip().casefold()
        if actual != expected:
            return False
    return True


def _terminal_path_matches(terminal_info: Any, profile: Any) -> bool:
    """Validate the attached terminal install when MT5 exposes its path.

    MetaTrader5 ``terminal_info().path`` is the terminal *directory* on the
    installed package versions used by OAK, while profile ``path`` stores the
    ``terminal64.exe`` path. Normalize both representations to the executable
    before comparing; comparing the raw strings falsely rejects every healthy
    session as ``TERMINAL_PATH_MISMATCH``.
    """
    if not isinstance(profile, dict):
        return True
    configured = normalize_terminal_path(profile.get("path"))
    if configured is None:
        return True
    observed_raw = getattr(terminal_info, "path", None)
    if not observed_raw:
        return True
    try:
        observed_candidate = Path(
            os.path.expandvars(os.path.expanduser(str(observed_raw)))
        )
        if observed_candidate.is_dir():
            observed_candidate = observed_candidate / "terminal64.exe"
    except (OSError, ValueError):
        return False
    observed = normalize_terminal_path(observed_candidate)
    if observed is None:
        return False
    return observed == configured


def validate_mt5_profile_session(mt5_module: Any, profile_config: Any) -> tuple[bool, str]:
    """Continuously validate the currently attached MT5 session against a profile."""
    if mt5_module is None:
        return False, "MT5_MODULE_MISSING"
    try:
        terminal_info = mt5_module.terminal_info()
        account = mt5_module.account_info()
    except Exception as error:
        return False, f"MT5_SESSION_QUERY_ERROR:{error}"
    if terminal_info is None or account is None:
        return False, "MT5_SESSION_UNAVAILABLE"
    if not _terminal_path_matches(terminal_info, profile_config):
        return False, "TERMINAL_PATH_MISMATCH"
    if not _account_matches(account, profile_config):
        return False, "ACCOUNT_MISMATCH"
    return True, "SESSION_OK"


def recover_mt5_profile_session(
    mt5_module: Any,
    profile_config: Any,
    *,
    timeout_seconds: float = 10.0,
    reconnect_fn: Callable[..., MT5LaunchResult] | None = None,
) -> tuple[bool, str, bool]:
    """Recover a transient MT5 session loss without ever crossing profile identity.

    Return ``(ok, reason, recovered)``. Account/server/path mismatches are
    terminal safety failures and are never converted into a generic reconnect.
    Only an unavailable/query-failed IPC session is eligible for bounded
    reconnection through ``ensure_mt5_profile_connected``.
    """
    valid, reason = validate_mt5_profile_session(mt5_module, profile_config)
    if valid:
        return True, "SESSION_OK", False

    retryable = reason == "MT5_SESSION_UNAVAILABLE" or reason.startswith("MT5_SESSION_QUERY_ERROR:")
    if not retryable:
        return False, reason, False

    launcher = reconnect_fn or ensure_mt5_profile_connected
    result = launcher(
        profile_config,
        mt5_module=mt5_module,
        timeout_seconds=timeout_seconds,
    )
    if not result.ok:
        return False, str(result.failure_code or reason), False

    valid_after, reason_after = validate_mt5_profile_session(mt5_module, profile_config)
    if not valid_after:
        return False, reason_after, True
    return True, "SESSION_RECOVERED", True


def ensure_mt5_profile_connected(
    profile_config: Any,
    *,
    timeout_seconds: float = 60.0,
    mt5_module: Any | None = None,
    process_factory: Callable[[Path], Any] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
    discover_fn: Callable[[], Iterable[Path]] | None = None,
) -> MT5LaunchResult:
    """Ensure one profile's terminal is running and its MT5 IPC is connected."""
    if mt5_module is None:
        import MetaTrader5 as mt5_module  # type: ignore

    configured = str(profile_config.get("path", "")) if isinstance(profile_config, dict) else ""
    terminal_path = normalize_terminal_path(configured)
    if terminal_path is None:
        candidates = list(discover_fn() if discover_fn else discover_terminal_candidates())
        terminal_path = next(
            (normalize_terminal_path(candidate) for candidate in candidates
             if normalize_terminal_path(candidate) and _profile_matches_candidate(profile_config, Path(candidate))),
            None,
        )
    if terminal_path is None:
        return MT5LaunchResult(
            False, str(configured), False, None, 0, None,
            "TERMINAL_PATH_NOT_FOUND",
            f"Configured path is invalid: {configured or '<empty>'}; no terminal64.exe candidate found",
        )

    process_started = False
    process_id: int | None = None
    attempts = 1
    last_error: tuple | None = None

    # A terminal can already be running even when optional process inspection
    # is unavailable. Attach first, but serialize initialize + identity
    # validation across all profile workers to reduce IPC races.
    initialized, last_error, failure_code = _initialize_and_validate_locked(
        mt5_module,
        terminal_path,
        profile_config,
        lock_timeout_seconds=min(max(float(timeout_seconds), 1.0), 15.0),
    )
    if initialized:
        return MT5LaunchResult(
            True, str(terminal_path), False, None,
            attempts, last_error, None, "Connected",
        )
    if failure_code in {"TERMINAL_PATH_MISMATCH", "ACCOUNT_MISMATCH"}:
        return MT5LaunchResult(
            False, str(terminal_path), False, None,
            attempts, last_error, failure_code,
            "Connected terminal/session does not match profile",
        )

    running, process_id = _is_terminal_running(terminal_path)
    if not running:
        try:
            process = (process_factory or _popen_terminal)(terminal_path)
            process_started = True
            process_id = getattr(process, "pid", None)
        except (OSError, subprocess.SubprocessError) as error:
            return MT5LaunchResult(
                False, str(terminal_path), False, None, 0, None,
                "PROCESS_START_FAILED", f"Cannot start terminal: {error}",
            )

    deadline = monotonic_fn() + max(0.1, float(timeout_seconds))
    backoff = (1.0, 2.0, 3.0, 5.0, 8.0)
    while attempts < 10 and monotonic_fn() <= deadline:
        attempts += 1
        initialized, last_error, failure_code = _initialize_and_validate_locked(
            mt5_module,
            terminal_path,
            profile_config,
            lock_timeout_seconds=min(max(float(deadline - monotonic_fn()), 1.0), 15.0),
        )
        if initialized:
            return MT5LaunchResult(
                True, str(terminal_path), process_started, process_id,
                attempts, last_error, None, "Connected",
            )
        if failure_code in {"TERMINAL_PATH_MISMATCH", "ACCOUNT_MISMATCH"}:
            return MT5LaunchResult(
                False, str(terminal_path), process_started, process_id,
                attempts, last_error, failure_code,
                "Connected terminal/session does not match profile",
            )
        delay = min(backoff[min(attempts - 1, len(backoff) - 1)], max(0.0, deadline - monotonic_fn()))
        if delay <= 0:
            break
        sleep_fn(delay)

    return MT5LaunchResult(
        False, str(terminal_path), process_started, process_id,
        attempts, last_error, "IPC_FAILED", "MT5 IPC connection timed out",
    )


__all__ = [
    "MT5LaunchResult",
    "normalize_terminal_path",
    "discover_terminal_candidates",
    "ensure_mt5_profile_connected",
    "validate_mt5_profile_session",
    "recover_mt5_profile_session",
    "profile_session_validation_enabled",
]
