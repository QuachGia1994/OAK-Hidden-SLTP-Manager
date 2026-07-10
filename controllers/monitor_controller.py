# -*- coding: utf-8 -*-
"""Start/stop monitor workers (multi-monitor), ghost requests, worker log piping."""
from __future__ import annotations

import os
import subprocess
import sys
import threading


class MonitorControllerMixin:
    """Start/stop monitor workers (multi-monitor), ghost requests, worker log piping."""

    def _get_live_running_profiles(self):
        """Return sorted list of all profiles with a live worker process."""
        live = []
        for name, data in list((getattr(self, "workers", None) or {}).items()):
            try:
                proc = (data or {}).get("proc")
                if proc is not None and proc.poll() is None:
                    live.append(name)
            except Exception:
                continue
        return sorted(live)

    def _get_live_running_profile(self):
        """Primary running profile for display (selected if live, else first live)."""
        live = self._get_live_running_profiles()
        if not live:
            return None
        try:
            sel = self.combo_profiles.get() if hasattr(self, "combo_profiles") else None
        except Exception:
            sel = None
        if sel in live:
            return sel
        declared = getattr(self, "running_profile_name", None)
        if declared in live:
            return declared
        return live[0]

    def _is_profile_live(self, profile_name):
        if not profile_name:
            return False
        data = (getattr(self, "workers", None) or {}).get(profile_name)
        if not data:
            return False
        try:
            proc = data.get("proc")
            return proc is not None and proc.poll() is None
        except Exception:
            return False

    def start_monitor(self):
        """Start monitor for the *selected* profile (multi: others may keep running)."""
        profile_name = self.combo_profiles.get()
        if not profile_name or profile_name not in self.profiles:
            self.log(T("msg_select_profile"))
            return

        # Check if this profile already running
        if self._is_profile_live(profile_name):
            self.log(f"Profile '{profile_name}' is already running.")
            try:
                self.update_ui_state(profile_name)
            except Exception:
                pass
            return

        try:
            # Update button text immediately for responsive UI
            self.btn_start.configure(text=T("btn_start") + "...", state="disabled")

            # Clear consoles on UI thread only (Tkinter is not thread-safe)
            def _clear_console():
                try:
                    self.console.configure(state="normal")
                    self.console.delete("1.0", "end")
                    self.console.configure(state="disabled")
                    if hasattr(self, "copy_console") and self.copy_console.winfo_exists():
                        self.copy_console.configure(state="normal")
                        self.copy_console.delete("1.0", "end")
                        self.copy_console.configure(state="disabled")
                except Exception:
                    pass
            self.after(0, _clear_console)

            # Kill orphans only for THIS profile (never other live monitors)
            self._kill_orphan_workers(profile_name)
            
            if getattr(sys, 'frozen', False):
                cmd = [sys.executable, "--worker", "--profile", profile_name]
            else:
                cmd = [sys.executable, sys.argv[0], "--worker", "--profile", profile_name]
            
            # Windows: Hide Console Window
            startupinfo = None
            creationflags = 0
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
            
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            
            # Register for cleanup on exit/crash (shared list from domain module)
            try:
                _running_processes.append(proc)
            except NameError:
                import OAK_Hidden_SLTP_Manager as _oak
                _oak._running_processes.append(proc)
                # keep controller free-name in sync for subsequent starts
                import controllers.monitor_controller as _selfmod
                _selfmod._running_processes = _oak._running_processes
            
            # Reset logs for this run
            self.workers[profile_name] = {
                "proc": proc,
                "logs": []
            }
            # Primary display name = last started (still multi-live via list)
            self.running_profile_name = profile_name
            self.selected_profile_name = profile_name
            self.refresh_profile_list()
            try:
                self._update_active_profile_badge(profile_name)
            except Exception:
                pass

            # Start Reader Thread
            t = threading.Thread(target=self.monitor_worker_output, args=(profile_name, proc))
            t.daemon = True
            t.start()

            self.update_ui_state(profile_name)
            self.refresh_running_monitors_panel()
            self.log(f"Started process for '{profile_name}' (PID: {proc.pid})")

        except Exception as e:
            self.log(f"Start Error: {e}")
            from tkinter import messagebox
            messagebox.showerror("Error", f"Could not start monitor:\n{e}")
            try:
                self.update_ui_state(profile_name)
            except Exception:
                pass

    def stop_monitor(self):
        """Stop the *selected* profile's monitor (if live)."""
        try:
            profile_name = self.combo_profiles.get()
        except Exception:
            profile_name = getattr(self, "selected_profile_name", None)
        if not profile_name:
            profile_name = self._get_live_running_profile()
        if not profile_name or not self._is_profile_live(profile_name):
            # Fall back: if selected not live, stop primary live if only one
            live = self._get_live_running_profiles()
            if len(live) == 1:
                profile_name = live[0]
            else:
                self.log("No live monitor for selected profile. Use Running Monitors list to Stop.")
                try:
                    self.update_ui_state(profile_name or "")
                except Exception:
                    pass
                return
        self.stop_monitor_profile(profile_name, confirm=True)

    def stop_monitor_profile(self, profile_name, *, confirm=False):
        """Stop one monitor by profile name (multi-safe; does not touch others)."""
        if not profile_name:
            return
        if not self._is_profile_live(profile_name):
            self.log(f"Monitor '{profile_name}' is not running.")
            self.refresh_running_monitors_panel()
            try:
                self.update_ui_state(profile_name)
            except Exception:
                pass
            return

        if confirm:
            try:
                from tkinter import messagebox
                if not messagebox.askyesno(
                    "Stop Monitor",
                    f"Stop monitor for '{profile_name}'?\n\n"
                    "Other running monitors are not affected.",
                ):
                    return
            except Exception:
                pass

        proc = self.workers[profile_name]["proc"]
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

        self.log(f"Stopping '{profile_name}'...")
        live_left = [n for n in self._get_live_running_profiles() if n != profile_name]
        # Fix primary name if we just stopped it
        if getattr(self, "running_profile_name", None) == profile_name:
            self.running_profile_name = live_left[0] if live_left else None
        try:
            self.refresh_profile_list()
        except Exception:
            pass
        try:
            self._update_active_profile_badge(self.selected_profile_name)
        except Exception:
            pass
        self._kill_orphan_workers(profile_name)
        self.update_ui_state(profile_name)
        self.refresh_running_monitors_panel()
        self.after(400, lambda: self.update_ui_state(profile_name))
        self.after(400, self.refresh_running_monitors_panel)


    def monitor_worker_output(self, profile_name, proc):
        try:
            for line in iter(proc.stdout.readline, ''):
                if not line: break
                clean_line = line.strip()
                if clean_line:
                    # GHOST MODE REQUEST
                    if "[GHOST_REQUEST]" in clean_line:
                        self.after(0, self._handle_ghost_request)
                        continue

                    if profile_name in self.workers:
                        self.workers[profile_name]["logs"].append(clean_line)
                    
                    if self.combo_profiles.get() == profile_name:
                        self.after(0, self.log_to_console_direct, clean_line)
        except: pass
        finally:
            self.after(0, lambda: self.update_ui_state(profile_name))


    def _handle_ghost_request(self):
        """Show ghost consent popup if not already active."""
        if self.settings.get("ghost_mode_active", False):
            return
            
        def on_accept(accepted):
            if accepted:
                self.settings["ghost_mode_active"] = True
                save_json(SETTINGS_FILE, self.settings)
                self.log("👻 GHOST MODE ACTIVATED (Stealth Operator)")
            else:
                self.log("⚠️ Ghost Mode Declined.")
                
        show_ghost_consent(self, on_accept)


    def log_to_console_direct(self, msg):
        try:
            self.console.configure(state="normal")
            self.console.insert("end", msg + "\n")
            self.console.see("end")
            self.console.configure(state="disabled")
            
            if hasattr(self, 'copy_console') and self.copy_console.winfo_exists():
                self.copy_console.configure(state="normal")
                self.copy_console.insert("end", msg + "\n")
                self.copy_console.see("end")
                self.copy_console.configure(state="disabled")
        except: pass


    def update_ui_state(self, profile_name):
        """Refresh Start/Stop for *selected* profile; multi-live list is separate panel."""
        try:
            current_sel = self.combo_profiles.get() if hasattr(self, "combo_profiles") else ""
        except Exception:
            current_sel = profile_name or ""

        live = self._get_live_running_profiles()
        primary = self._get_live_running_profile()
        self.running_profile_name = primary

        sel = current_sel or profile_name or "—"
        run_summary = ", ".join(live) if live else "—"

        try:
            if hasattr(self, "lbl_profile_selected") and self.lbl_profile_selected.winfo_exists():
                self.lbl_profile_selected.configure(text=f"Selected: {sel}")
            if hasattr(self, "lbl_profile_running") and self.lbl_profile_running.winfo_exists():
                n = len(live)
                self.lbl_profile_running.configure(
                    text=f"Running ({n}): {run_summary}" if n else "Running: —"
                )
        except Exception:
            pass

        sel_live = self._is_profile_live(current_sel)

        try:
            if sel_live:
                self.btn_start.configure(state="disabled", text=f"START {sel}")
                self.btn_stop.configure(state="normal", text=f"STOP {sel}")
            else:
                self.btn_start.configure(state="normal", text=f"START {sel}")
                # Stop selected only if that profile is live; else disabled
                self.btn_stop.configure(state="disabled", text=T("btn_stop"))
        except Exception:
            pass

        try:
            if hasattr(self, "btn_copy_start"):
                if sel_live:
                    self.btn_copy_start.configure(state="disabled", text=f"START {sel}")
                    self.btn_copy_stop.configure(state="normal", text=f"STOP {sel}")
                else:
                    self.btn_copy_start.configure(state="normal", text=f"START {sel}")
                    self.btn_copy_stop.configure(state="disabled", text=T("btn_stop"))
        except Exception:
            pass

        try:
            self.refresh_running_monitors_panel()
        except Exception:
            pass

    def refresh_running_monitors_panel(self):
        """Rebuild multi-monitor list: ● Name   PID   [Stop]."""
        frame = getattr(self, "running_monitors_frame", None)
        if frame is None:
            return
        try:
            if not frame.winfo_exists():
                return
        except Exception:
            return

        for child in list(frame.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

        live = self._get_live_running_profiles()
        hdr = ctk.CTkLabel(
            frame,
            text="Running Monitors" + (f" ({len(live)})" if live else ""),
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        hdr.pack(fill="x", padx=2, pady=(0, 4))

        if not live:
            ctk.CTkLabel(
                frame,
                text="No monitors running",
                font=ctk.CTkFont(size=11),
                text_color="gray",
                anchor="w",
            ).pack(fill="x", padx=4, pady=2)
            return

        for name in live:
            pid = "—"
            try:
                proc = self.workers[name]["proc"]
                pid = str(getattr(proc, "pid", "—") or "—")
            except Exception:
                pass
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row,
                text=f"● {name}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#66bb6a",
                anchor="w",
            ).pack(side="left", padx=(2, 6))
            ctk.CTkLabel(
                row,
                text=f"PID {pid}",
                font=ctk.CTkFont(size=11),
                text_color="gray",
                anchor="w",
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                row,
                text="Stop",
                width=56,
                height=26,
                fg_color="#d9534f",
                hover_color="#c9302c",
                command=lambda n=name: self.stop_monitor_profile(n, confirm=True),
            ).pack(side="right", padx=2)


    def _kill_orphan_workers(self, profile_name):
        """Kill leftover --worker processes for this profile (python + pythonw)."""
        if os.name != "nt" or not profile_name:
            return
        try:
            # WMIC: match worker + profile in command line
            where = (
                f"CommandLine like '%--worker%' and CommandLine like '%{profile_name}%' "
                f"and (Name='python.exe' or Name='pythonw.exe')"
            )
            result = subprocess.run(
                ["wmic", "process", "where", where, "get", "ProcessId"],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in (result.stdout or "").splitlines():
                line = line.strip()
                if line.isdigit():
                    pid = int(line)
                    if pid != os.getpid():
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(pid)],
                            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        self.log(f"Killed orphan worker for '{profile_name}' (PID: {pid})")
        except Exception:
            pass
        # Clear stale lock so new worker can start
        try:
            safe = re.sub(r"[^\w\-]", "_", profile_name)
            lock = f"worker_{safe}.lock"
            if os.path.exists(lock):
                os.remove(lock)
        except Exception:
            pass


    def on_profile_change(self, choice):
        """Dashboard combo callback → atomic select_profile (single source of truth)."""
        if getattr(self, "_selecting_profile", False):
            return
        if choice and choice in getattr(self, "profiles", {}):
            self.select_profile(choice, source="dashboard_combo", clear_console=True)
        else:
            self.selected_profile_name = choice or None


    def _open_ghost_popup(self):
        if hasattr(self, "ghost_popup") and self.ghost_popup and self.ghost_popup.winfo_exists():
            try:
                self.ghost_popup.lift()
                self.ghost_popup.focus_force()
                return
            except Exception:
                pass

        popup = ctk.CTkToplevel(self)
        popup.title(T("ghost_popup_title"))
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        try:
            popup.transient(self)
        except Exception:
            pass
        try:
            popup.wm_attributes("-toolwindow", True)
        except Exception:
            pass

        try:
            x = self.winfo_x() + 70
            y = self.winfo_y() + 80
            popup.geometry(f"320x190+{x}+{y}")
        except Exception:
            popup.geometry("320x190")

        def on_close():
            try:
                popup.destroy()
            finally:
                self.ghost_popup = None
                if hasattr(self, "btn_ghost_popup_toggle"):
                    self.btn_ghost_popup_toggle = None

        popup.protocol("WM_DELETE_WINDOW", on_close)
        self.ghost_popup = popup

        body = ctk.CTkFrame(popup, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=12)
        body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(body, text=T("ghost_popup_header"), font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(body, text=T("ghost_popup_desc"), justify="left", wraplength=290).grid(row=1, column=0, sticky="w", pady=(8, 12))

        self.btn_ghost_popup_toggle = ctk.CTkButton(body, text="", height=38, command=self._toggle_ghost_from_popup, font=ctk.CTkFont(weight="bold"))
        self.btn_ghost_popup_toggle.grid(row=2, column=0, sticky="ew")
        self.update_ghost_button_ui()


    def _toggle_ghost_from_popup(self):
        self.toggle_ghost_mode()
        self.update_ghost_button_ui()
        

    def toggle_ghost_mode(self):
        current = self.settings.get("ghost_mode_active", False)
        new_state = not current
        self.settings["ghost_mode_active"] = new_state
        save_json(SETTINGS_FILE, self.settings)
        
        self.update_ghost_button_ui()
        
        msg = T("ghost_active_msg") if new_state else T("ghost_inactive_msg")
        self.log(msg)
        

    def update_ghost_button_ui(self):
        is_active = self.settings.get("ghost_mode_active", False)
        btn_color = "#e67e22" if is_active else "#27ae60"
        btn_hover = "#d35400" if is_active else "#219150"
        
        engine_text = T("engine_ghost") if is_active else T("engine_api")
        engine_color = "#e67e22" if is_active else "#3498db" # Orange vs Blue
        
        if hasattr(self, "btn_ghost_toggle"):
            label = "👻 Ghost ON" if is_active else "👻 Ghost"
            self.btn_ghost_toggle.configure(text=label, fg_color=btn_color, hover_color=btn_hover)

        if hasattr(self, "btn_ghost_popup_toggle") and self.btn_ghost_popup_toggle:
            try:
                btn_text = T("btn_ghost_off") if is_active else T("btn_ghost_on")
                self.btn_ghost_popup_toggle.configure(text=btn_text, fg_color=btn_color, hover_color=btn_hover)
            except Exception:
                pass
            
        if hasattr(self, "lbl_engine_badge"):
            self.lbl_engine_badge.configure(text=engine_text, text_color=engine_color)
