# -*- coding: utf-8 -*-
"""Service lifecycle manager for the oak-core supervisor (Phase 6, §9).

The 5 "services" surfaced in the Settings UI were previously only
configuration-status indicators.  This module gives them a REAL, safe
start/stop/status lifecycle, mirroring ``profiles.ProfileManager`` but for
the side services (telegram / mimo_worker / factcheck_worker / screener /
signal_bot).

Safety rules (see explore report — trading-risk findings):
  * Nothing auto-starts.  The UI triggers every start; the supervisor never
    launches a service on boot.
  * ``signal_bot`` is labelled "MT5 Account Audit Service" and MUST start the
    audit service (``--audit-service``), NEVER the live signal loop
    (``main()``) which can place orders.  This fixes a pre-existing
    mislabelled-entry-point bug.
  * Services flagged ``trading_risk == "critical"`` (telegram, signal_bot)
    require an explicit ``confirm: true`` from the caller and surface an
    ``execution_armed`` flag so the UI can show a red warning.
  * No secrets ever cross the IPC boundary — only booleans/counts.
  * Single-instance lock files (mimo_bot.lock / mimo_worker.lock) are honoured
    on start and removed on stop to avoid Telegram 409 conflicts.
"""
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# utils.py lives at the repo root; ensure it is importable in both dev
# (cwd=python) and frozen layouts.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from utils import build_signal_process_cmd, UnsupportedFrozenProcessError  # noqa: E402

from .profiles import _data_root, load_profiles  # noqa: E402


@dataclass(frozen=True)
class ServiceSpec:
    key: str
    label: str
    kind: str                 # "subprocess" | "on_demand"
    legacy_key: str | None    # key into utils.SIGNAL_SCRIPT_MAP
    needs_profile: bool
    trading_risk: str         # "none" | "low" | "critical"
    lock_file: str | None
    audit_service: bool = False


SERVICE_SPECS: dict[str, ServiceSpec] = {
    "telegram": ServiceSpec(
        "telegram", "MiMo Telegram Bot", "subprocess", "mimo_bot",
        needs_profile=False, trading_risk="critical", lock_file="mimo_bot.lock",
    ),
    "mimo_worker": ServiceSpec(
        "mimo_worker", "MiMo Worker", "subprocess", "mimo_worker",
        needs_profile=False, trading_risk="none", lock_file="mimo_worker.lock",
    ),
    "factcheck_worker": ServiceSpec(
        "factcheck_worker", "Fact Check Worker", "subprocess", "factcheck_worker",
        needs_profile=False, trading_risk="none", lock_file=None,
    ),
    "screener": ServiceSpec(
        "screener", "Stock Screener", "on_demand", None,
        needs_profile=False, trading_risk="none", lock_file=None,
    ),
    "signal_bot": ServiceSpec(
        "signal_bot", "MT5 Account Audit Service", "subprocess", "signal_bot",
        needs_profile=True, trading_risk="critical", lock_file=None,
        audit_service=True,
    ),
}


def _read_config_json() -> dict:
    """Best-effort read of config.json from repo root or data root."""
    out: dict = {}
    for base in (_REPO_ROOT, _data_root()):
        p = base / "config.json"
        if p.is_file():
            try:
                out.update(__import__("json").loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
    return out


def _is_lock_held(lock_file: str) -> bool:
    """Return True if a live process holds the given PID lock file."""
    p = Path(lock_file)
    if not p.is_file():
        return False
    try:
        pid = int(p.read_text(encoding="utf-8").strip())
    except Exception:
        return False
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
            if handle:
                kernel32.CloseHandle(handle)
                return True
        except Exception:
            return False
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class ServiceManager:
    """Owns the lifecycle of the side services (mirrors ProfileManager)."""

    def __init__(self, *, python_executable: str | None = None, log=None, emit_event=None):
        self._python = python_executable or sys.executable
        self._log = log or (lambda msg: print(msg, file=sys.stderr))
        self._emit = emit_event
        self._procs: dict[str, subprocess.Popen] = {}
        self._intentional_stop: dict[str, bool] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Spec / config queries
    # ------------------------------------------------------------------ #
    def _spec(self, key: str) -> ServiceSpec | None:
        return SERVICE_SPECS.get(key)

    def _configured(self, spec: ServiceSpec) -> tuple[bool, str]:
        if spec.key == "telegram":
            tok = _read_config_json().get("telegram_token")
            return (bool(tok), "thiếu telegram_token trong config.json")
        if spec.key == "mimo_worker":
            return (True, "")
        if spec.key == "factcheck_worker":
            return (bool(os.environ.get("UPSTASH_REDIS_REST_URL")),
                    "thiếu UPSTASH_REDIS_REST_URL")
        if spec.key == "screener":
            db = _data_root() / "data" / "market.db"
            return (db.is_file(), "thiếu data/market.db")
        if spec.key == "signal_bot":
            return (bool(load_profiles()), "chưa có profile nào được cấu hình")
        return (False, "unknown service")

    def _execution_armed(self, spec: ServiceSpec) -> bool:
        if spec.key != "signal_bot":
            return False
        if os.environ.get("SIGNAL_BOT_EXECUTION_ENABLED", "").lower() in ("1", "true", "yes", "on"):
            return True
        for cfg in load_profiles().values():
            if cfg.get("signal_execution_enabled"):
                return True
        return False

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #
    def _status(self, key: str) -> dict:
        spec = self._spec(key)
        if spec is None:
            return {"key": key, "label": key, "kind": "unknown", "configured": False,
                    "status": "not_supported", "pid": None, "exit_code": None,
                    "trading_risk": "none", "execution_armed": False, "note": "",
                    "scope": "global"}
        configured, reason = self._configured(spec)
        with self._lock:
            proc = self._procs.get(key)
        status = "stopped"
        pid = None
        exit_code = None
        if proc is not None:
            poll = proc.poll()
            if poll is None:
                status = "running"
                pid = proc.pid
            else:
                exit_code = poll
                # A clean self-termination (for example, a second instance
                # finding its lock already held) is not a crash.  Only a
                # non-zero exit without an intentional stop is degraded.
                status = "exited" if poll == 0 or self._intentional_stop.get(key) else "crashed"
        note = ""
        if spec.kind == "on_demand":
            note = ("Chạy theo yêu cầu (không phải daemon) — dùng nút 'Tải EOD' / "
                    "'Chạy bộ lọc' trên tab Bộ lọc CP.")
        return {
            "key": key, "label": spec.label, "kind": spec.kind,
            "configured": configured, "status": status, "pid": pid,
            "exit_code": exit_code, "trading_risk": spec.trading_risk,
            "execution_armed": self._execution_armed(spec), "note": note,
            "config_note": reason if not configured else "",
            # Lifecycle scope so the UI can distinguish per-profile services
            # (one instance per MT5 profile) from global singletons.
            "scope": "profile" if spec.needs_profile else "global",
        }

    def list_services(self) -> dict:
        return {"services": [self._status(k) for k in SERVICE_SPECS]}

    def service_status(self, key: str) -> dict:
        return self._status(key)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start_service(self, key: str, profile: str = "", confirm: bool = False) -> dict:
        spec = self._spec(key)
        if spec is None:
            return {"started": False, "reason": "unknown_service"}
        if spec.kind == "on_demand":
            return {"started": False, "reason": "on_demand_service",
                    "note": "Use the Screener tab controls."}
        if spec.trading_risk == "critical" and not confirm:
            return {"started": False, "reason": "confirmation_required",
                    "error": "CONFIRMATION_REQUIRED"}
        configured, reason = self._configured(spec)
        if not configured:
            return {"started": False, "reason": "not_configured", "detail": reason}

        # Resolve profile for services that need one.
        if spec.needs_profile and not profile:
            profiles = load_profiles()
            if profiles:
                profile = next(iter(profiles))

        # Single-instance lock guard. A lock held by a *live* process means it
        # is already running; a lock left behind by a crashed/killed process is
        # stale and must be removed so we can start a fresh instance.
        if spec.lock_file:
            lf = Path(spec.lock_file)
            if lf.is_file():
                if _is_lock_held(spec.lock_file):
                    return {"started": False, "reason": "already_running_lock",
                            "detail": f"{spec.lock_file} đang được giữ bởi một tiến trình khác"}
                try:
                    lf.unlink()
                except OSError:
                    pass

        with self._lock:
            existing = self._procs.get(key)
            if existing is not None and existing.poll() is None:
                return {"started": False, "reason": "already_running", "pid": existing.pid}

        try:
            cmd = build_signal_process_cmd(
                spec.legacy_key, profile, getattr(sys, "frozen", False), self._python
            )
        except UnsupportedFrozenProcessError as e:
            return {"started": False, "reason": "not_supported_in_frozen", "detail": str(e)}

        cwd = str(_REPO_ROOT) if not getattr(sys, "frozen", False) else None
        # Force UTF-8 I/O so services that print localized text don't crash on
        # the Windows console codepage (mirrors legacy SignalProcessSupervisor).
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        try:
            proc = subprocess.Popen(
                cmd, cwd=cwd, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return {"started": False, "reason": "spawn_failed", "detail": str(exc)}

        with self._lock:
            self._procs[key] = proc
            self._intentional_stop[key] = False

        for stream_name in ("stdout", "stderr"):
            stream = getattr(proc, stream_name, None)
            if stream is None:
                continue
            threading.Thread(
                target=self._drain,
                args=(key, stream),
                daemon=True,
                name=f"svclog-{key}-{stream_name}",
            ).start()
        threading.Thread(
            target=self._watch, args=(key, proc), daemon=True, name=f"svcwatch-{key}"
        ).start()
        self._log(f"[services] started {key} (pid={proc.pid})")
        self._emit_state(key)
        return {"started": True, "pid": proc.pid, "status": "running"}

    def stop_service(self, key: str, timeout_seconds: float = 8.0) -> dict:
        spec = self._spec(key)
        if spec is None:
            return {"stopped": False, "reason": "unknown_service"}
        with self._lock:
            proc = self._procs.get(key)
        if proc is None:
            return {"stopped": False, "reason": "not_running"}
        self._intentional_stop[key] = True
        try:
            proc.terminate()
            proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
        with self._lock:
            self._procs.pop(key, None)
        if spec.lock_file:
            try:
                os.remove(spec.lock_file)
            except OSError:
                pass
        self._log(f"[services] stopped {key}")
        self._emit_state(key)
        return {"stopped": True}

    def stop_all(self, timeout_seconds: float = 5.0) -> dict:
        stopped = []
        for key in list(self._procs.keys()):
            stopped.append(self.stop_service(key, timeout_seconds=timeout_seconds))
        return {"stopped": stopped}

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _drain(self, key: str, stream) -> None:
        try:
            for line in stream:
                self._log(f"[svc:{key}] {line.rstrip()}")
        except Exception:
            pass

    def _watch(self, key: str, proc: subprocess.Popen) -> None:
        """Publish an exit state so the desktop reflects crashes live."""
        try:
            proc.wait()
        except Exception:
            return
        with self._lock:
            current = self._procs.get(key)
        if current is proc:
            self._emit_state(key)

    def _emit_state(self, key: str) -> None:
        if self._emit:
            try:
                self._emit("service.state", self._status(key))
            except Exception:
                pass
