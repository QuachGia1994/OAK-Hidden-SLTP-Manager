# -*- coding: utf-8 -*-
"""Start/stop monitor workers, ghost requests, worker log piping."""
from __future__ import annotations

class MonitorControllerMixin:
    """Start/stop monitor workers, ghost requests, worker log piping."""

    def start_monitor(self):
        profile_name = self.combo_profiles.get()
        if not profile_name or profile_name not in self.profiles:
            self.log(T("msg_select_profile"))
            return
            
        # Check if already running
        if profile_name in self.workers:
            if self.workers[profile_name]["proc"].poll() is None:
                self.log(f"Profile '{profile_name}' is already running.")
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

            # Prevent multi-worker double fire of scheduled orders
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
            self.log(f"Started process for '{profile_name}' (PID: {proc.pid})")
            
        except Exception as e:
            self.log(f"Start Error: {e}")
            from tkinter import messagebox
            messagebox.showerror("Error", f"Could not start monitor:\n{e}")


    def stop_monitor(self):
        # Confirm stop when a worker is actively running
        try:
            from tkinter import messagebox
            running = any(
                w.get("proc") and w["proc"].poll() is None
                for w in getattr(self, "workers", {}).values()
            )
            if running:
                run_name = getattr(self, "running_profile_name", None) or "worker"
                if not messagebox.askyesno(
                    "Stop Monitor",
                    f"Stop monitor for '{run_name}'?\n\n"
                    "Scheduled orders will no longer auto-fire until you start again.",
                ):
                    return
        except Exception:
            pass
        # Always stop the RUNNING profile, not only the selected combo
        profile_name = getattr(self, "running_profile_name", None) or self.combo_profiles.get()
        if profile_name in self.workers:
            proc = self.workers[profile_name]["proc"]
            if proc.poll() is None:
                try:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW
                        )
                    else:
                        proc.terminate()
                except Exception:
                    proc.terminate()
                self.log(f"Stopping '{profile_name}'...")
                self.btn_stop.configure(state="disabled", text="Stopping...")
                self.running_profile_name = None
                self.refresh_profile_list()
                try:
                    self._update_active_profile_badge(self.selected_profile_name)
                except Exception:
                    pass
                # Immediate update for local UI feedback
                self.update_ui_state(profile_name)
                # Still keep the delayed check just in case
                self.after(500, lambda: self.update_ui_state(profile_name))
        # Always sweep orphans for this profile (pythonw leftovers)
        if profile_name:
            self._kill_orphan_workers(profile_name)


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
        """Refresh Start/Stop labels with explicit Selected vs Running profile names."""
        try:
            current_sel = self.combo_profiles.get() if hasattr(self, "combo_profiles") else ""
        except Exception:
            current_sel = profile_name or ""

        running = getattr(self, "running_profile_name", None)
        # Prefer live worker poll
        if running and running in getattr(self, "workers", {}):
            try:
                if self.workers[running]["proc"].poll() is not None:
                    running = None
            except Exception:
                pass
        else:
            # Fallback: any live worker
            running = None
            for n, data in (getattr(self, "workers", {}) or {}).items():
                try:
                    if data.get("proc") and data["proc"].poll() is None:
                        running = n
                        break
                except Exception:
                    pass
            self.running_profile_name = running

        sel = current_sel or profile_name or "—"
        run = running or "—"

        # Labels (if dashboard created them)
        try:
            if hasattr(self, "lbl_profile_selected") and self.lbl_profile_selected.winfo_exists():
                self.lbl_profile_selected.configure(text=f"Selected: {sel}")
            if hasattr(self, "lbl_profile_running") and self.lbl_profile_running.winfo_exists():
                self.lbl_profile_running.configure(text=f"Running Monitor: {run}")
        except Exception:
            pass

        sel_is_running = bool(running and current_sel and running == current_sel)
        any_running = bool(running)

        try:
            if any_running:
                if sel_is_running:
                    self.btn_start.configure(state="disabled", text=f"START {sel}")
                    self.btn_stop.configure(state="normal", text=f"STOP {running}")
                else:
                    # Selected profile differs from running — Start selected, Stop the runner
                    self.btn_start.configure(state="normal", text=f"START {sel}")
                    self.btn_stop.configure(state="normal", text=f"STOP {running}")
            else:
                self.btn_start.configure(state="normal", text=f"START {sel}")
                self.btn_stop.configure(state="disabled", text=T("btn_stop"))
        except Exception:
            pass

        # Copy Trade Buttons (mirror selected profile)
        try:
            if hasattr(self, "btn_copy_start"):
                if sel_is_running:
                    self.btn_copy_start.configure(state="disabled", text=f"START {sel}")
                    self.btn_copy_stop.configure(state="normal", text=f"STOP {running}")
                elif any_running:
                    self.btn_copy_start.configure(state="normal", text=f"START {sel}")
                    self.btn_copy_stop.configure(state="normal", text=f"STOP {running}")
                else:
                    self.btn_copy_start.configure(state="normal", text=f"START {sel}")
                    self.btn_copy_stop.configure(state="disabled", text=T("btn_stop"))
        except Exception:
            pass


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
