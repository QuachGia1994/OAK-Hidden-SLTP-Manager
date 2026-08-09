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
    ) -> None:
        """Update badges. status override: Running | Stopped | Restarting | Crashed."""
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

    def start_signal_process(self, key: str, profile: str = "") -> None:
        info = self._signal_procs.get(key)
        if not info:
            return
        if info.get("proc") and info["proc"].poll() is None:
            return

        self._kill_orphan_processes(key)
        self._intentional_stop[key] = False
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
                    if self._is_noise_line(clean):
                        continue
                    logs = info.setdefault("logs", [])
                    logs.append(clean)
                    if len(logs) > 500:
                        info["logs"] = logs[-300:]
                    self._append_console_line(key, clean)
        except Exception:
            pass
        finally:
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
