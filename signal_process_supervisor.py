# -*- coding: utf-8 -*-
"""SignalProcessSupervisor - manages background signal processes.

All Tkinter widget mutations are marshalled onto the UI thread via
``ui_after(callback)`` (typically ``app.after(0, callback)``).
"""
import os
import sys
import time
import threading
import subprocess
from typing import Dict, Any, Callable, Optional
from oak_logger import setup_logger

log = setup_logger("signal_supervisor")


class SignalProcessSupervisor:
    """Supervises signal processes (mt5_signal_bot, mt4_mt5_server, etc.)."""

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

    def _append_console_line(self, key: str, line: str) -> None:
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

    def _set_running_ui(self, key: str, running: bool, pid: Optional[int] = None) -> None:
        info = self._signal_procs.get(key)
        if not info:
            return
        if running:
            self._safe_configure(info.get("lbl_pid"), text=f"PID: {pid}")
            self._safe_configure(info.get("btn_start"), state="disabled")
            self._safe_configure(info.get("btn_stop"), state="normal")
            self._safe_configure(info.get("lbl_status"), text="Running", text_color="#66bb6a")
        else:
            self._safe_configure(info.get("lbl_pid"), text="PID: ---")
            self._safe_configure(info.get("btn_start"), state="normal")
            self._safe_configure(info.get("btn_stop"), state="disabled")
            self._safe_configure(info.get("lbl_status"), text="Stopped", text_color="#9e9e9e")

    def _kill_orphan_processes(self, key: str) -> None:
        if os.name != "nt":
            return
        script_map = {
            "mimo_bot": "mimo_bot.py",
            "mimo_worker": "mimo_worker.py",
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

    def start_signal_process(self, key: str, profile: str = "") -> None:
        info = self._signal_procs.get(key)
        if not info:
            return
        if info.get("proc") and info["proc"].poll() is None:
            return

        self._kill_orphan_processes(key)
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

    def stop_signal_process(self, key: str) -> None:
        info = self._signal_procs.get(key)
        if not info or not info.get("proc"):
            # Still reset UI in case of race
            self._set_running_ui(key, False)
            return

        proc = info["proc"]
        if proc.poll() is None:
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                else:
                    proc.terminate()
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
            time.sleep(0.5)
            self._log(f"Signal stopped: {info['name']}")
        info["proc"] = None
        self._set_running_ui(key, False)
        self._kill_orphan_processes(key)

        if key == "mimo_worker":
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            lock_file = os.path.join(root_dir, "mimo_worker.lock")
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
            except Exception:
                pass

    def _monitor_signal_output(self, key: str, proc: subprocess.Popen) -> None:
        """Background reader — never mutates Tk widgets directly."""
        info = self._signal_procs.get(key)
        if not info:
            return
        try:
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                clean = line.strip()
                if clean:
                    logs = info.setdefault("logs", [])
                    logs.append(clean)
                    if len(logs) > 500:
                        info["logs"] = logs[-300:]
                    self._append_console_line(key, clean)
        except Exception:
            pass
        finally:
            # Marshal stop (UI button state) onto main thread
            self._ui(self.stop_signal_process, key)

    def start_all_signals(self, profile: str = "") -> None:
        for key in self._signal_procs:
            self.start_signal_process(key, profile)
            time.sleep(1)

    def stop_all_signals(self) -> None:
        for key in self._signal_procs:
            self.stop_signal_process(key)

    def register_signals(self, signal_procs: Dict[str, Dict[str, Any]]) -> None:
        self._signal_procs = signal_procs

    def cleanup(self) -> None:
        self.stop_all_signals()
        for proc in self._running_processes:
            try:
                proc.kill()
            except Exception:
                pass
        self._running_processes.clear()
