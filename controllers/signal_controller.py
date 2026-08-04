# -*- coding: utf-8 -*-
"""Signal process UI wrappers around SignalProcessSupervisor."""
from __future__ import annotations

class SignalControllerMixin:
    """Signal process UI wrappers around SignalProcessSupervisor."""

    def create_signals_frame(self, parent):
        # Initialize and mount the SignalsTab
        try:
            from ui.signals_tab import SignalsTab as _SignalsTab
        except Exception:
            _SignalsTab = SignalsTab  # bound via controllers.runtime

        self.signals_tab = _SignalsTab(self)
        self.signals_tab.mount(parent)
        # Copy over UI references for backwards compatibility
        self.signal_procs = self.signals_tab.signal_procs
        # Register the UI with the signal supervisor (same dict object)
        self.signal_supervisor.register_signals(self.signal_procs)
        self.signal_supervisor.signal_defs = [
            ("mt4_feed_server", "MT4 Feed Server", "#1f538d"),
            ("signal_bot", "MT5 Account Audit Service", "#2fa572"),
            ("mimo_bot", "MiMo Telegram Bot", "#b33dd4"),
            ("mimo_worker", "MiMo Worker", "#d4a03d"),
            ("factcheck_worker", "Fact Check Worker", "#00bfa5"),
        ]
        # Ensure UI marshal is bound (re-apply after rebuild)
        try:
            if hasattr(self, "_schedule_ui"):
                self.signal_supervisor.set_ui_after(self._schedule_ui)
            elif hasattr(self, "after"):
                self.signal_supervisor.set_ui_after(lambda cb: self.after(0, cb))
        except Exception:
            pass


    def _kill_orphan_processes(self, key):
        """Kill orphan processes that weren't tracked (e.g. from crashed sessions)"""
        if os.name != 'nt':
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
                ["wmic", "process", "where",
                 f"CommandLine like '%{script}%' and (Name='python.exe' or Name='pythonw.exe')",
                 "get", "ProcessId"],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line.isdigit():
                    pid = int(line)
                    if pid != os.getpid():
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        self.log(f"Killed orphan process: {script} (PID: {pid})")
        except:
            pass


    def start_signal_process(self, key):
        """Delegate to signal supervisor."""
        profile = self.combo_profiles.get() if hasattr(self, 'combo_profiles') else ""
        self.signal_supervisor.start_signal_process(key, profile)


    def stop_signal_process(self, key):
        """Delegate to signal supervisor."""
        self.signal_supervisor.stop_signal_process(key)


    def _monitor_signal_output(self, key, proc):
        info = self.signal_procs.get(key)
        if not info:
            return
        try:
            for line in iter(proc.stdout.readline, ''):
                if not line:
                    break
                clean = line.strip()
                if clean:
                    info["logs"].append(clean)
                    self.after(0, self._append_signal_log, key, clean)
        except:
            pass
        finally:
            self.after(0, lambda: self.stop_signal_process(key))


    def _append_signal_log(self, key, line):
        info = self.signal_procs.get(key)
        if not info:
            return
        # Hide Flask/Werkzeug development-server noise in UI consoles
        low = (line or "").lower()
        if any(
            frag in low
            for frag in (
                "this is a development server",
                "do not use it in a production deployment",
                " * running on http",
                "werkzeug",
                "debugger is active",
                "debugger pin code",
                "press ctrl+c to quit",
            )
        ):
            return
        console = info["console"]
        console.configure(state="normal")
        console.insert("end", line + "\n")
        console.see("end")
        console.configure(state="disabled")
        if len(info["logs"]) > 500:
            info["logs"] = info["logs"][-300:]


    def start_all_signals(self):
        """Delegate to signal supervisor (background so UI stays responsive)."""
        import threading

        profile = self.combo_profiles.get() if hasattr(self, "combo_profiles") else ""
        # Re-bind registry in case UI was remounted
        try:
            if getattr(self, "signal_procs", None):
                self.signal_supervisor.register_signals(self.signal_procs)
        except Exception:
            pass

        def _run():
            try:
                self.signal_supervisor.start_all_signals(profile)
            except Exception as e:
                try:
                    self.log(f"Start all signals error: {e}")
                except Exception:
                    pass

        threading.Thread(target=_run, daemon=True).start()

    def stop_all_signals(self):
        """Delegate to signal supervisor."""
        self.signal_supervisor.stop_all_signals()
