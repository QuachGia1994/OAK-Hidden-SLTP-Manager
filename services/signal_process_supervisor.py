# -*- coding: utf-8 -*-
"""SignalProcessSupervisor - manages background signal processes."""
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

    def __init__(self, signal_defs: list, log_callback: Optional[Callable] = None):
        self.signal_defs = signal_defs
        self.log_callback = log_callback
        self._signal_procs: Dict[str, Dict[str, Any]] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._running_processes: list = []

    def _log(self, msg: str) -> None:
        """Log message using callback if available."""
        if self.log_callback:
            self.log_callback(msg)
        log.info(msg)

    def _kill_orphan_processes(self, key: str) -> None:
        """Kill orphan processes that weren't tracked."""
        if os.name != 'nt':
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
                ["wmic", "process", "where",
                 f"CommandLine like '%{script}%' and Name='python.exe'",
                 "get", "ProcessId"],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line.isdigit():
                    pid = int(line)
                    if pid != os.getpid():
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        self._log(f"Killed orphan process: {script} (PID: {pid})")
        except Exception:
            pass

    def start_signal_process(self, key: str, profile: str = "") -> None:
        """Start a signal process by key."""
        info = self._signal_procs.get(key)
        if not info:
            return
        if info.get("proc") and info["proc"].poll() is None:
            return

        self._kill_orphan_processes(key)
        try:
            from utils import build_signal_process_cmd, UnsupportedFrozenProcessError

            frozen = getattr(sys, 'frozen', False)
            cmd = build_signal_process_cmd(key, profile, frozen, sys.executable)

            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUNBUFFERED"] = "1"
            startupinfo = None
            creationflags = 0
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW

            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding='utf-8', errors='replace',
                startupinfo=startupinfo, creationflags=creationflags,
                cwd=os.path.dirname(os.path.abspath(__file__)),
                env=env,
            )
            info["proc"] = proc
            info["logs"] = []
            info["lbl_pid"].configure(text=f"PID: {proc.pid}")
            info["btn_start"].configure(state="disabled")
            info["btn_stop"].configure(state="normal")

            self._running_processes.append(proc)

            t = threading.Thread(
                target=self._monitor_signal_output, args=(key, proc), daemon=True
            )
            t.start()
            self._threads[key] = t
            self._log(f"Signal started: {info['name']} (PID: {proc.pid})")
        except UnsupportedFrozenProcessError:
            self._log(f"Frozen mode: {info['name']} not supported yet")
        except Exception as e:
            self._log(f"Signal start error ({info['name']}): {e}")

    def stop_signal_process(self, key: str) -> None:
        """Stop a signal process by key."""
        info = self._signal_procs.get(key)
        if not info or not info.get("proc"):
            return

        proc = info["proc"]
        if proc.poll() is None:
            try:
                if os.name == 'nt':
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    proc.terminate()
            except Exception:
                proc.terminate()
            time.sleep(0.5)
            self._log(f"Signal stopped: {info['name']}")
        info["proc"] = None
        info["btn_start"].configure(state="normal")
        info["btn_stop"].configure(state="disabled")
        info["lbl_pid"].configure(text="PID: ---")
        self._kill_orphan_processes(key)

        if key == "mimo_worker":
            lock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mimo_worker.lock")
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
            except Exception:
                pass

    def _monitor_signal_output(self, key: str, proc: subprocess.Popen) -> None:
        """Monitor output of a signal process."""
        info = self._signal_procs.get(key)
        if not info:
            return
        try:
            for line in iter(proc.stdout.readline, ''):
                if not line:
                    break
                clean = line.strip()
                if clean:
                    info["logs"].append(clean)
                    if info.get("console"):
                        console = info["console"]
                        console.configure(state="normal")
                        console.insert("end", clean + "\n")
                        console.see("end")
                        console.configure(state="disabled")
                    if len(info["logs"]) > 500:
                        info["logs"] = info["logs"][-300:]
        except Exception:
            pass
        finally:
            self.stop_signal_process(key)

    def start_all_signals(self, profile: str = "") -> None:
        """Start all registered signals."""
        for key in self._signal_procs:
            self.start_signal_process(key, profile)
            time.sleep(1)

    def stop_all_signals(self) -> None:
        """Stop all registered signals."""
        for key in self._signal_procs:
            self.stop_signal_process(key)

    def register_signals(self, signal_procs: Dict[str, Dict[str, Any]]) -> None:
        """Register signal processes from UI."""
        self._signal_procs = signal_procs

    def cleanup(self) -> None:
        """Stop all signals and clean up."""
        self.stop_all_signals()
        for proc in self._running_processes:
            try:
                proc.kill()
            except Exception:
                pass
        self._running_processes.clear()
