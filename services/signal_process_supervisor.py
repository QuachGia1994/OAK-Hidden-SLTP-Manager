# -*- coding: utf-8 -*-
"""SignalProcessSupervisor - manages background signal processes.

All Tkinter widget mutations are marshalled onto the UI thread via
``ui_after(callback)`` (typically ``app.after(0, callback)``).
"""
import os
import re
import sys
import time
import threading
import subprocess
from typing import Dict, Any, Callable, Optional
from oak_logger import setup_logger

log = setup_logger("signal_supervisor")

# ---------------------------------------------------------------------------
# Single-instance recovery helpers (module-level so they are unit-testable)
# ---------------------------------------------------------------------------
# Shared message contract emitted by the managed bots when another instance is
# already running: ``mimo_bot`` prints "[EXIT] mimo_bot already running
# (PID N)"; ``mimo_worker`` prints "[WARN] MiMo Worker already running
# (PID N)". The Vietnamese legacy variant is matched for lock-file fallback.
_DUPLICATE_PID_RE = re.compile(r"already running \(PID (\d+)\)")
_DUPLICATE_LINE_RE = re.compile(r"already running|dang chay roi", re.IGNORECASE)

# Lock files are the single-instance source of truth for the managed bots.
_LOCK_FILE_MAP = {
    "mimo_bot": "mimo_bot.lock",
    "mimo_worker": "mimo_worker.lock",
}


def parse_duplicate_instance_pid(line: Optional[str]) -> Optional[int]:
    """Extract the conflicting PID from a managed bot's duplicate line.

    Returns ``None`` when the line carries no PID (or is not a duplicate
    message at all).
    """
    if not line:
        return None
    match = _DUPLICATE_PID_RE.search(line)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def is_duplicate_instance_line(line: Optional[str]) -> bool:
    """True when a managed bot reports another instance already running."""
    return bool(line) and bool(_DUPLICATE_LINE_RE.search(line))


def read_lock_file_pid(key: str, root_dir: Optional[str] = None) -> Optional[int]:
    """Read the managed bot's lock-file PID (source of truth), or None."""
    lock_name = _LOCK_FILE_MAP.get(key)
    if not lock_name:
        return None
    if root_dir is None:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        with open(os.path.join(root_dir, lock_name), "r", encoding="utf-8") as f:
            raw = (f.read() or "").strip()
        pid = int(raw)
        return pid if pid > 0 else None
    except (OSError, ValueError):
        return None


def _expected_process_markers(key, script_map=None, frozen_flags=None):
    """Command-line fragments that identify the managed process for ``key``.

    Dev launchers run ``<script>.py``; frozen builds run the exe with a
    ``--<mode>`` flag. The conflicting instance may have been launched by
    either kind of build, so both markers are checked.
    """
    if script_map is None or frozen_flags is None:
        from utils import SIGNAL_SCRIPT_MAP, FROZEN_MODE_FLAGS

        script_map = script_map or SIGNAL_SCRIPT_MAP
        frozen_flags = frozen_flags or FROZEN_MODE_FLAGS
    markers = []
    script = (script_map or {}).get(key)
    if script:
        markers.append(script.lower())
    flag = (frozen_flags or {}).get(key)
    if flag:
        markers.append(flag.lower())
    return markers


def _psutil_probe(pid):
    """Return (alive, cmdline_lower) via psutil; (None, None) if unavailable."""
    try:
        import psutil  # type: ignore
    except Exception:
        return None, None
    try:
        proc = psutil.Process(pid)
        return True, " ".join(proc.cmdline() or []).lower()
    except psutil.NoSuchProcess:
        return False, None
    except Exception:
        return None, None


def _tasklist_alive(pid):
    """Windows tasklist liveness probe; None when the probe itself fails."""
    if os.name != "nt":
        return None
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        out = (result.stdout or "").strip()
        if not out or out.lower().startswith("info:"):
            return False
        return True
    except Exception:
        return None


def _powershell_cmdline(pid):
    """Command line via Get-CimInstance (safer than wmic); None on failure."""
    if os.name != "nt":
        return None
    script = f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        cmdline = (result.stdout or "").strip()
        return cmdline.lower() if cmdline else None
    except Exception:
        return None


def validate_conflicting_pid(
    key: str,
    pid,
    *,
    current_proc_pid: Optional[int] = None,
    script_map: Optional[dict] = None,
    frozen_flags: Optional[dict] = None,
):
    """Validate a conflicting PID against the expected managed process.

    Returns ``(verdict, detail)`` where verdict is one of:
      "gone"     – no live process with that PID; conflict already resolved
      "matches"  – live process whose command line names the expected bot;
                   safe to terminate that exact PID
      "mismatch" – live process that is NOT the expected bot; never terminate
      "unknown"  – Windows metadata unavailable; safe termination cannot be
                   established, so the caller must stop and show the PID
    """
    if not isinstance(pid, int) or pid <= 0:
        return "mismatch", "invalid PID"
    if pid == os.getpid():
        return "mismatch", "PID is the supervisor itself"
    if current_proc_pid is not None and pid == current_proc_pid:
        return "mismatch", "PID is the current managed process"

    markers = _expected_process_markers(key, script_map, frozen_flags)

    alive, cmdline = _psutil_probe(pid)
    if alive is None:
        alive = _tasklist_alive(pid)
    if alive is False:
        return "gone", "process no longer exists"
    if alive is True:
        if cmdline is None:
            cmdline = _powershell_cmdline(pid)
        if cmdline is None:
            return "unknown", "process metadata unavailable"
        if markers and any(marker in cmdline for marker in markers):
            return "matches", "command line matches the expected managed process"
        return "mismatch", "command line does not match the expected managed process"
    return "unknown", "process metadata unavailable"


def terminate_pid(pid: int) -> None:
    """Force-terminate exactly one PID (Windows taskkill; POSIX SIGKILL)."""
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=10,
            )
        else:
            os.kill(pid, 9)
    except Exception:
        pass


class SignalProcessSupervisor:
    """Supervises Signal/worker processes launched by the NativeQt/Classic UI."""

    def __init__(
        self,
        signal_defs: list,
        log_callback: Optional[Callable] = None,
        ui_after: Optional[Callable] = None,
    ):
        self.signal_defs = signal_defs
        self.log_callback = log_callback
        # ui_after(fn, *args) must schedule fn on the Tk main thread
        self.ui_after = ui_after
        self._signal_procs: Dict[str, Dict[str, Any]] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._running_processes: list = []
        self._intentional_stop: Dict[str, bool] = {}
        # Single-instance recovery: one auto-restart budget per user start.
        self._auto_restart_attempted: Dict[str, bool] = {}
        self._last_profile: Dict[str, str] = {}

    def set_ui_after(self, ui_after: Callable) -> None:
        """Bind UI scheduler after App is constructed."""
        self.ui_after = ui_after

    def _log(self, msg: str) -> None:
        if self.log_callback:
            self.log_callback(msg)
        log.info(msg)

    def _ui(self, fn: Callable, *args) -> None:
        """Run fn on UI thread if scheduler available; else best-effort direct call."""
        def wrapper(f=fn, a=args):
            try:
                f(*a)
            except Exception:
                pass

        try:
            if self.ui_after is not None:
                self.ui_after(wrapper)
                return
        except Exception:
            pass
        wrapper()

    def _safe_configure(self, widget, **kwargs) -> None:
        if widget is None:
            return

        def _do():
            try:
                if hasattr(widget, "winfo_exists") and not widget.winfo_exists():
                    return
                widget.configure(**kwargs)
            except Exception:
                pass

        self._ui(_do)

    # Flask/Werkzeug noise — hide from signal consoles (packaged product feel)
    _CONSOLE_NOISE = (
        "this is a development server",
        "do not use it in a production deployment",
        " * running on http",
        " * debug mode:",
        "press ctrl+c to quit",
        "werkzeug",
        "debugger is active",
        "debugger pin code",
        "warning: this is a development server",
    )

    def _is_noise_line(self, line: str) -> bool:
        low = (line or "").lower()
        return any(frag in low for frag in self._CONSOLE_NOISE)

    def _append_console_line(self, key: str, line: str) -> None:
        if self._is_noise_line(line):
            return
        info = self._signal_procs.get(key)
        if not info:
            return
        console = info.get("console")
        if console is None:
            return

        def _do():
            try:
                if hasattr(console, "winfo_exists") and not console.winfo_exists():
                    return
                console.configure(state="normal")
                console.insert("end", line + "\n")
                console.see("end")
                console.configure(state="disabled")
            except Exception:
                pass

        self._ui(_do)

    def _set_running_ui(
        self,
        key: str,
        running: bool,
        pid: Optional[int] = None,
        status: Optional[str] = None,
        conflict_pid: Optional[int] = None,
    ) -> None:
        """Update badges. status override: Running | Stopped | Restarting | Crashed.

        ``conflict_pid`` surfaces a conflicting instance's PID while stopped
        (single-instance recovery) instead of the usual ``PID: ---`` so the
        user can terminate that PID manually.
        """
        info = self._signal_procs.get(key)
        if not info:
            return
        if running:
            label = status or "Running"
            color = "#66bb6a" if label == "Running" else "#ffb74d"
            self._safe_configure(info.get("lbl_pid"), text=f"PID: {pid}")
            self._safe_configure(info.get("btn_start"), state="disabled")
            self._safe_configure(info.get("btn_stop"), state="normal")
            self._safe_configure(info.get("lbl_status"), text=label, text_color=color)
        else:
            if conflict_pid is not None:
                self._safe_configure(info.get("lbl_pid"), text=f"PID: {conflict_pid} (conflict)")
                self._safe_configure(info.get("btn_start"), state="normal")
                self._safe_configure(info.get("btn_stop"), state="disabled")
                self._safe_configure(info.get("lbl_status"), text="Conflict", text_color="#ff7043")
                return
            label = status or "Stopped"
            color = "#ef5350" if label == "Crashed" else "#9e9e9e"
            self._safe_configure(info.get("lbl_pid"), text="PID: ---")
            self._safe_configure(info.get("btn_start"), state="normal")
            self._safe_configure(info.get("btn_stop"), state="disabled")
            self._safe_configure(info.get("lbl_status"), text=label, text_color=color)

    def _kill_orphan_processes(self, key: str) -> None:
        if os.name != "nt":
            return
        script_map = {
            "mimo_bot": "mimo_bot.py",
            "mimo_worker": "mimo_worker.py",
            "factcheck_worker": "factcheck_worker.py",
        }
        script = script_map.get(key)
        if not script:
            return
        try:
            result = subprocess.run(
                [
                    "wmic",
                    "process",
                    "where",
                    f"CommandLine like '%{script}%' and (Name='python.exe' or Name='pythonw.exe')",
                    "get",
                    "ProcessId",
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line.isdigit():
                    pid = int(line)
                    if pid != os.getpid():
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(pid)],
                            capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                        self._log(f"Killed orphan process: {script} (PID: {pid})")
        except Exception:
            pass

    def start_signal_process(self, key: str, profile: str = "", *, _recovery: bool = False) -> None:
        info = self._signal_procs.get(key)
        if not info:
            return
        if info.get("proc") and info["proc"].poll() is None:
            return

        self._kill_orphan_processes(key)
        self._intentional_stop[key] = False
        # User-initiated starts get a fresh one-shot recovery budget.
        # Recovery-triggered restarts must NOT reset the budget (loop guard).
        if not _recovery:
            self._auto_restart_attempted[key] = False
        if profile:
            self._last_profile[key] = profile
        try:
            from utils import build_signal_process_cmd, UnsupportedFrozenProcessError

            frozen = getattr(sys, "frozen", False)
            cmd = build_signal_process_cmd(key, profile, frozen, sys.executable)

            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUNBUFFERED"] = "1"
            startupinfo = None
            creationflags = 0
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW

            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo,
                creationflags=creationflags,
                cwd=root_dir,
                env=env,
            )
            info["proc"] = proc
            info["logs"] = []
            self._set_running_ui(key, True, pid=proc.pid)
            self._running_processes.append(proc)

            t = threading.Thread(target=self._monitor_signal_output, args=(key, proc), daemon=True)
            t.start()
            self._threads[key] = t
            self._log(f"Signal started: {info['name']} (PID: {proc.pid})")
        except UnsupportedFrozenProcessError:
            self._log(f"Frozen mode: {info['name']} not supported yet")
        except Exception as e:
            self._log(f"Signal start error ({info['name']}): {e}")

    def stop_signal_process(self, key: str, *, wait: bool = True) -> None:
        self._intentional_stop[key] = True
        # Explicit Stop must never auto-restart via recovery.
        self._auto_restart_attempted[key] = True
        info = self._signal_procs.get(key)
        if not info or not info.get("proc"):
            # Still reset UI in case of race
            self._set_running_ui(key, False, status="Stopped")
            return

        proc = info["proc"]
        if key in ("signal_bot", "mimo_bot"):
            try:
                root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                cfg_path = os.path.join(root_dir, "config.json")
                if os.path.exists(cfg_path):
                    import json
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    token = cfg.get("telegram_token", "")
                    chat_id = cfg.get("telegram_chat_id", "")
                    if token and chat_id:
                        sys.path.append(root_dir)
                        from telegram_client import telegram_send_message
                        bot_name = "MT5 Account Audit Service" if key == "signal_bot" else "MiMo Telegram Bot"
                        telegram_send_message(token, chat_id, f"🔴 {bot_name} đã DỪNG (Stopped)")
            except Exception as e:
                self._log(f"Failed to send stop telegram alert: {e}")

        if proc.poll() is None:
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        timeout=5,
                    )
                else:
                    proc.terminate()
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
            if wait:
                time.sleep(0.5)
            self._log(f"Signal stopped: {info['name']}")
        info["proc"] = None
        self._set_running_ui(key, False, status="Stopped")
        self._kill_orphan_processes(key)

        if key == "mimo_worker":
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            lock_file = os.path.join(root_dir, "mimo_worker.lock")
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
            except Exception:
                pass

    def _try_duplicate_recovery(self, key: str, proc: subprocess.Popen, line: str) -> bool:
        """Handle a single-instance conflict reported by a managed bot.

        Returns True when this path owns the UI/lifecycle outcome (recovery
        or manual intervention), so the normal monitor finally-block must
        not overwrite status.
        """
        if self._intentional_stop.get(key):
            return False
        if not is_duplicate_instance_line(line):
            return False

        conflict_pid = parse_duplicate_instance_pid(line)
        if conflict_pid is None:
            conflict_pid = read_lock_file_pid(key)

        current_pid = getattr(proc, "pid", None)
        if conflict_pid is None:
            self._log(
                f"Duplicate instance for {key}: no PID in stdout or lock file; "
                f"manual intervention required"
            )

            def _manual_no_pid(k=key, p=proc):
                info2 = self._signal_procs.get(k)
                if info2 and info2.get("proc") is p:
                    info2["proc"] = None
                self._set_running_ui(k, False, status="Conflict")

            self._ui(_manual_no_pid)
            return True

        verdict, detail = validate_conflicting_pid(
            key, conflict_pid, current_proc_pid=current_pid
        )
        budget_used = bool(self._auto_restart_attempted.get(key))

        if verdict in ("matches", "gone") and not budget_used:
            self._auto_restart_attempted[key] = True
            if verdict == "matches":
                self._log(
                    f"Duplicate instance for {key}: terminating conflicting "
                    f"PID {conflict_pid} ({detail}); restarting once"
                )
                terminate_pid(conflict_pid)
                time.sleep(0.3)
            else:
                self._log(
                    f"Duplicate instance for {key}: conflicting PID {conflict_pid} "
                    f"already gone ({detail}); restarting once"
                )

            def _recover(k=key, p=proc):
                info2 = self._signal_procs.get(k)
                if info2 and info2.get("proc") is p:
                    info2["proc"] = None
                self._set_running_ui(k, False, status="Restarting")
                profile = self._last_profile.get(k, "")
                self.start_signal_process(k, profile, _recovery=True)

            self._ui(_recover)
            return True

        self._log(
            f"Duplicate instance for {key}: PID {conflict_pid} requires "
            f"manual intervention ({verdict}: {detail})"
        )

        def _manual(k=key, p=proc, cpid=conflict_pid):
            info2 = self._signal_procs.get(k)
            if info2 and info2.get("proc") is p:
                info2["proc"] = None
            self._set_running_ui(k, False, conflict_pid=cpid)

        self._ui(_manual)
        return True

    def _monitor_signal_output(self, key: str, proc: subprocess.Popen) -> None:
        """Background reader — never mutates Tk widgets directly."""
        info = self._signal_procs.get(key)
        if not info:
            return
        recovered = False
        try:
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                clean = line.strip()
                if clean:
                    if self._is_noise_line(clean):
                        continue
                    logs = info.setdefault("logs", [])
                    logs.append(clean)
                    if len(logs) > 500:
                        info["logs"] = logs[-300:]
                    self._append_console_line(key, clean)
                    if not recovered and is_duplicate_instance_line(clean):
                        recovered = self._try_duplicate_recovery(key, proc, clean)
        except Exception:
            pass
        finally:
            if not recovered:
                intentional = bool(self._intentional_stop.get(key))
                code = None
                try:
                    code = proc.poll()
                except Exception:
                    code = None
                # User Stop / taskkill → Stopped; unexpected non-zero exit → Crashed
                crashed = (not intentional) and (code not in (None, 0))

                def _finish(k=key, crash=crashed, was_intentional=intentional):
                    info2 = self._signal_procs.get(k)
                    if info2 and info2.get("proc") is proc:
                        info2["proc"] = None
                    # If stop_signal_process already updated UI, keep Stopped
                    if was_intentional:
                        self._set_running_ui(k, False, status="Stopped")
                    else:
                        self._set_running_ui(k, False, status="Crashed" if crash else "Stopped")
                    self._kill_orphan_processes(k)

                self._ui(_finish)

    def start_all_signals(self, profile: str = "") -> None:
        keys = list(self._signal_procs)
        for key in keys:
            self.start_signal_process(key, profile)
            time.sleep(1)

    def stop_all_signals(self, *, wait: bool = True) -> None:
        for key in list(self._signal_procs.keys()):
            self.stop_signal_process(key, wait=wait)

    def register_signals(self, signal_procs: Dict[str, Dict[str, Any]]) -> None:
        self._signal_procs = signal_procs

    def cleanup(self) -> None:
        # Fast close path: no per-process sleeps (app X / shutdown)
        self.stop_all_signals(wait=False)
        for proc in list(self._running_processes):
            try:
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass
        self._running_processes.clear()
