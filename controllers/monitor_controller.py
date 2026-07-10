# -*- coding: utf-8 -*-
"""Start/stop monitor workers (multi-monitor), ghost requests, worker log piping."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time


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
        # Prefer pure Python state (safe from any thread); widget only as fallback on main thread
        sel = getattr(self, "selected_profile_name", None)
        if not sel:
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
            self.refresh_running_monitors_panel(force=True)
            try:
                self.update_ui_state(profile_name)
            except Exception:
                pass
            return

        if confirm:
            if not self._confirm_stop_monitor(profile_name):
                return

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
        self.refresh_running_monitors_panel(force=True)
        self.after(400, lambda: self.update_ui_state(profile_name))
        self.after(400, lambda: self.refresh_running_monitors_panel(force=True))

    def _stop_dialog_account_line(self, profile_name):
        """Best-effort account line for stop confirm dialog."""
        try:
            if hasattr(self, "_store") and self._store and profile_name:
                hb = self._store.get_heartbeat(profile_name) or {}
                server = hb.get("server") or ""
                login = hb.get("login") or ""
                if server or login:
                    return f"{server or '—'} | #{login or '—'}"
        except Exception:
            pass
        try:
            cfg = (getattr(self, "profiles", {}) or {}).get(profile_name) or {}
            login = cfg.get("login_id") or cfg.get("login") or ""
            path = cfg.get("path") or ""
            if login or path:
                return f"{path or '—'} | #{login or '—'}"
        except Exception:
            pass
        return "—"

    def _confirm_stop_monitor(self, profile_name):
        """Clear stop target dialog (profile / PID / account). Returns True if confirmed."""
        pid = "—"
        try:
            proc = (self.workers.get(profile_name) or {}).get("proc")
            if proc is not None:
                pid = str(getattr(proc, "pid", "—") or "—")
        except Exception:
            pass
        account = self._stop_dialog_account_line(profile_name)
        others = [n for n in self._get_live_running_profiles() if n != profile_name]

        # Prefer custom modal so target is unambiguous vs selected combo
        try:
            return self._confirm_stop_monitor_modal(profile_name, pid, account, others)
        except Exception:
            try:
                from tkinter import messagebox
                return bool(
                    messagebox.askyesno(
                        "Stop running monitor",
                        f"Stop running monitor\n\n"
                        f"Profile: {profile_name}\n"
                        f"PID: {pid}\n"
                        f"Account: {account}\n\n"
                        f"Other monitors will remain active"
                        + (f" ({', '.join(others)})." if others else "."),
                    )
                )
            except Exception:
                return True

    def _confirm_stop_monitor_modal(self, profile_name, pid, account, others):
        """CTk modal: highlight stop target; pause panel thrash while open."""
        self._stop_dialog_open = True
        self._stop_highlight_profile = profile_name
        try:
            self.refresh_running_monitors_panel(force=True)
        except Exception:
            pass

        result = {"ok": False}
        popup = ctk.CTkToplevel(self)
        popup.title(T("ui_stop_monitor_title"))
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        try:
            popup.transient(self)
        except Exception:
            pass
        popup.grab_set()

        body = ctk.CTkFrame(popup, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=16)

        ctk.CTkLabel(
            body,
            text=T("ui_stop_monitor_title"),
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 10))

        detail = ctk.CTkFrame(body, fg_color=("#3d2020", "#3d2020"), corner_radius=8)
        detail.pack(fill="x", pady=(0, 10))
        for label, val in (
            (T("ui_profile"), profile_name),
            (T("ui_pid"), pid),
            (T("ui_account"), account),
        ):
            row = ctk.CTkFrame(detail, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(
                row, text=f"{label}:", width=70, anchor="w", text_color="gray"
            ).pack(side="left")
            ctk.CTkLabel(
                row,
                text=str(val),
                anchor="w",
                font=ctk.CTkFont(weight="bold" if label == T("ui_profile") else "normal"),
                text_color="#ef5350" if label == T("ui_profile") else None,
            ).pack(side="left", fill="x", expand=True)

        note = T("ui_other_monitors")
        if others:
            note = T("ui_other_monitors_list").format(names=", ".join(others))
        ctk.CTkLabel(
            body, text=note, anchor="w", justify="left", wraplength=320, text_color="gray"
        ).pack(fill="x", pady=(0, 14))

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x")

        def _close(ok):
            result["ok"] = bool(ok)
            try:
                popup.grab_release()
            except Exception:
                pass
            try:
                popup.destroy()
            except Exception:
                pass

        ctk.CTkButton(
            btns,
            text=T("ui_cancel"),
            width=100,
            fg_color="gray40",
            command=lambda: _close(False),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btns,
            text=T("ui_stop_named").format(name=profile_name),
            width=140,
            fg_color="#d9534f",
            hover_color="#c9302c",
            command=lambda: _close(True),
        ).pack(side="right")

        popup.protocol("WM_DELETE_WINDOW", lambda: _close(False))
        try:
            popup.update_idletasks()
            popup.geometry(f"360x280+{self.winfo_rootx() + 80}+{self.winfo_rooty() + 80}")
        except Exception:
            popup.geometry("360x280")

        try:
            self.wait_window(popup)
        except Exception:
            pass
        finally:
            self._stop_dialog_open = False
            self._stop_highlight_profile = None
            try:
                self.refresh_running_monitors_panel(force=True)
            except Exception:
                pass
        return result["ok"]

    def monitor_worker_output(self, profile_name, proc):
        """Reader thread: never touch Tk widgets; only pure Python state + after()."""
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

                    # Tk is not thread-safe — do not call combo_profiles.get() here
                    selected = getattr(self, "selected_profile_name", None)
                    if selected == profile_name:
                        self.after(0, self.log_to_console_direct, clean_line)
        except Exception:
            pass
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
        current_sel = getattr(self, "selected_profile_name", None) or ""
        if not current_sel:
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
                self.lbl_profile_selected.configure(text=f"{T('ui_selected')}: {sel}")
            if hasattr(self, "lbl_profile_running") and self.lbl_profile_running.winfo_exists():
                n = len(live)
                self.lbl_profile_running.configure(
                    text=f"{T('ui_running')} ({n}): {run_summary}" if n else f"{T('ui_running')}: —"
                )
        except Exception:
            pass

        sel_live = self._is_profile_live(current_sel)

        try:
            if sel_live:
                self.btn_start.configure(state="disabled", text=T("ui_start_named").format(name=sel))
                self.btn_stop.configure(state="normal", text=T("ui_stop_named_btn").format(name=sel))
            else:
                self.btn_start.configure(state="normal", text=T("ui_start_named").format(name=sel))
                self.btn_stop.configure(
                    state="disabled",
                    text=T("ui_stop_named_btn").format(name=sel) if sel and sel != "—" else T("btn_stop"),
                )
        except Exception:
            pass

        try:
            if hasattr(self, "btn_copy_start"):
                if sel_live:
                    self.btn_copy_start.configure(state="disabled", text=T("ui_start_named").format(name=sel))
                    self.btn_copy_stop.configure(state="normal", text=T("ui_stop_named_btn").format(name=sel))
                else:
                    self.btn_copy_start.configure(state="normal", text=T("ui_start_named").format(name=sel))
                    self.btn_copy_stop.configure(
                        state="disabled",
                        text=T("ui_stop_named_btn").format(name=sel) if sel and sel != "—" else T("btn_stop"),
                    )
        except Exception:
            pass

        try:
            self.refresh_running_monitors_panel()
        except Exception:
            pass

    def _running_monitors_signature(self, live=None):
        """Stable signature for live monitors (name, pid) — skip no-op rebuilds."""
        if live is None:
            live = self._get_live_running_profiles()
        parts = []
        for name in live:
            pid = "—"
            try:
                proc = (self.workers.get(name) or {}).get("proc")
                pid = str(getattr(proc, "pid", "—") or "—")
            except Exception:
                pass
            parts.append((name, pid))
        return tuple(parts)

    def refresh_running_monitors_panel(self, force=False):
        """Diff-update multi-monitor list (avoid empty flash from destroy-all thrash)."""
        # While stop modal is open, only recolor rows — never tear down the list
        if getattr(self, "_stop_dialog_open", False) and not force:
            try:
                self._apply_running_row_highlights()
            except Exception:
                pass
            return

        frame = getattr(self, "running_monitors_frame", None)
        if frame is None:
            return
        try:
            if not frame.winfo_exists():
                return
        except Exception:
            return

        live = self._get_live_running_profiles()
        sig = self._running_monitors_signature(live)
        hl = getattr(self, "_stop_highlight_profile", None)
        last_sig = getattr(self, "_running_panel_sig", None)
        last_hl = getattr(self, "_running_panel_hl", None)

        # Ensure stable structure once (header + body), not full destroy every tick
        body = getattr(self, "_running_body", None)
        hdr = getattr(self, "_running_hdr", None)
        empty_lbl = getattr(self, "_running_empty_lbl", None)
        rows = getattr(self, "_running_row_widgets", None)
        if rows is None:
            rows = {}
            self._running_row_widgets = rows

        structure_ok = False
        try:
            structure_ok = (
                hdr is not None
                and hdr.winfo_exists()
                and body is not None
                and body.winfo_exists()
            )
        except Exception:
            structure_ok = False

        if not structure_ok or force:
            for child in list(frame.winfo_children()):
                try:
                    child.destroy()
                except Exception:
                    pass
            rows.clear()
            self._running_hdr = ctk.CTkLabel(
                frame,
                text=T("ui_running_monitors"),
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
            )
            self._running_hdr.pack(fill="x", padx=2, pady=(0, 4))
            self._running_body = ctk.CTkFrame(frame, fg_color="transparent")
            self._running_body.pack(fill="both", expand=True)
            self._running_empty_lbl = ctk.CTkLabel(
                self._running_body,
                text=T("ui_no_monitors"),
                font=ctk.CTkFont(size=11),
                text_color="gray",
                anchor="w",
            )
            hdr = self._running_hdr
            body = self._running_body
            empty_lbl = self._running_empty_lbl
            last_sig = None  # force row rebuild

        # Header count always tracks live set
        try:
            n = len(live)
            base = T("ui_running_monitors")
            hdr.configure(text=f"{base} ({n})" if n else base)
        except Exception:
            pass

        if not force and sig == last_sig and hl == last_hl:
            return

        self._running_panel_sig = sig
        self._running_panel_hl = hl

        # Empty state
        if not live:
            for name in list(rows.keys()):
                self._destroy_running_row(name)
            try:
                if empty_lbl is not None and empty_lbl.winfo_exists():
                    if not empty_lbl.winfo_ismapped():
                        empty_lbl.pack(fill="x", padx=4, pady=2)
            except Exception:
                try:
                    empty_lbl.pack(fill="x", padx=4, pady=2)
                except Exception:
                    pass
            return

        try:
            if empty_lbl is not None and empty_lbl.winfo_exists() and empty_lbl.winfo_ismapped():
                empty_lbl.pack_forget()
        except Exception:
            pass

        live_set = set(live)
        for name in list(rows.keys()):
            if name not in live_set:
                self._destroy_running_row(name)

        for name in live:
            pid = "—"
            try:
                proc = (self.workers.get(name) or {}).get("proc")
                pid = str(getattr(proc, "pid", "—") or "—")
            except Exception:
                pass
            if name not in rows:
                self._create_running_row(name, pid)
            else:
                self._update_running_row(name, pid)

        self._apply_running_row_highlights()

    def _create_running_row(self, name, pid):
        body = getattr(self, "_running_body", None)
        if body is None:
            return
        rows = self._running_row_widgets
        highlight = getattr(self, "_stop_highlight_profile", None) == name
        bg = ("#4a2020", "#4a2020") if highlight else "transparent"
        row = ctk.CTkFrame(body, fg_color=bg, corner_radius=6)
        row.pack(fill="x", pady=2)
        name_lbl = ctk.CTkLabel(
            row,
            text=f"● {name}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ef5350" if highlight else "#66bb6a",
            anchor="w",
            cursor="hand2",
        )
        name_lbl.pack(side="left", padx=(6, 6))
        name_lbl.bind("<Button-1>", lambda _e, n=name: self._on_running_monitor_click(n))
        pid_lbl = ctk.CTkLabel(
            row,
            text=f"PID {pid}",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
            cursor="hand2",
        )
        pid_lbl.pack(side="left", padx=(0, 8))
        pid_lbl.bind("<Button-1>", lambda _e, n=name: self._on_running_monitor_click(n))
        stop_btn = ctk.CTkButton(
            row,
            text=T("ui_stop"),
            width=56,
            height=26,
            fg_color="#d9534f",
            hover_color="#c9302c",
            command=lambda n=name: self.stop_monitor_profile(n, confirm=True),
        )
        stop_btn.pack(side="right", padx=4, pady=2)
        rows[name] = {
            "frame": row,
            "name_lbl": name_lbl,
            "pid_lbl": pid_lbl,
            "stop_btn": stop_btn,
            "pid": pid,
        }

    def _update_running_row(self, name, pid):
        rows = getattr(self, "_running_row_widgets", {}) or {}
        info = rows.get(name)
        if not info:
            return
        if info.get("pid") != pid:
            info["pid"] = pid
            try:
                info["pid_lbl"].configure(text=f"PID {pid}")
            except Exception:
                pass

    def _destroy_running_row(self, name):
        rows = getattr(self, "_running_row_widgets", {}) or {}
        info = rows.pop(name, None)
        if not info:
            return
        try:
            info["frame"].destroy()
        except Exception:
            pass

    def _apply_running_row_highlights(self):
        rows = getattr(self, "_running_row_widgets", {}) or {}
        hl = getattr(self, "_stop_highlight_profile", None)
        for name, info in rows.items():
            highlight = hl == name
            try:
                info["frame"].configure(
                    fg_color=("#4a2020", "#4a2020") if highlight else "transparent"
                )
                info["name_lbl"].configure(
                    text_color="#ef5350" if highlight else "#66bb6a"
                )
            except Exception:
                pass

    def _on_running_monitor_click(self, profile_name):
        """Switch Account Source / selected profile when clicking a live monitor row."""
        if not profile_name or profile_name not in getattr(self, "profiles", {}):
            return
        try:
            self.select_profile(profile_name, source="running_panel", clear_console=False)
        except Exception:
            self.selected_profile_name = profile_name
            try:
                if hasattr(self, "combo_profiles"):
                    self.combo_profiles.set(profile_name)
            except Exception:
                pass
        try:
            self.update_ui_state(profile_name)
        except Exception:
            pass

    @staticmethod
    def _cmdline_profile_exact(cmdline, profile_name):
        """True only when argv has --profile <name> with exact equality (not substring)."""
        if not cmdline or not profile_name:
            return False
        # Tokenize: support quoted args and --profile=Name form
        try:
            import shlex
            parts = shlex.split(cmdline, posix=False)
        except Exception:
            parts = cmdline.replace('"', "").split()
        target = str(profile_name)
        for i, part in enumerate(parts):
            p = part.strip().strip('"').strip("'")
            if p == "--profile":
                if i + 1 < len(parts):
                    val = parts[i + 1].strip().strip('"').strip("'")
                    return val == target
                return False
            if p.startswith("--profile="):
                return p.split("=", 1)[1].strip().strip('"').strip("'") == target
        return False

    def _kill_orphan_workers(self, profile_name):
        """Kill leftover --worker processes for THIS profile only (exact --profile match).

        Never use CommandLine like '%Vantage%' — that also kills VantageDemo.
        """
        if os.name != "nt" or not profile_name:
            return
        my_pid = os.getpid()
        # Prefer known worker PID from registry (if still listed but dead/orphan)
        try:
            data = (getattr(self, "workers", None) or {}).get(profile_name) or {}
            proc = data.get("proc")
            known_pid = getattr(proc, "pid", None) if proc is not None else None
            if known_pid and known_pid != my_pid:
                try:
                    # Only if process no longer tracked as live (orphan cleanup after stop)
                    if proc is None or proc.poll() is not None:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(known_pid)],
                            capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                except Exception:
                    pass
        except Exception:
            pass

        try:
            # List all --worker python processes; filter by exact --profile arg
            where = (
                "CommandLine like '%--worker%' "
                "and (Name='python.exe' or Name='pythonw.exe')"
            )
            result = subprocess.run(
                ["wmic", "process", "where", where, "get", "ProcessId,CommandLine", "/FORMAT:LIST"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            cmdline = None
            pid = None
            for raw in (result.stdout or "").splitlines():
                line = raw.strip()
                if not line:
                    if pid is not None and cmdline is not None:
                        if pid != my_pid and self._cmdline_profile_exact(cmdline, profile_name):
                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", str(pid)],
                                capture_output=True,
                                creationflags=subprocess.CREATE_NO_WINDOW,
                            )
                            self.log(f"Killed orphan worker for '{profile_name}' (PID: {pid})")
                    cmdline = None
                    pid = None
                    continue
                if line.lower().startswith("commandline="):
                    cmdline = line.split("=", 1)[1].strip()
                elif line.lower().startswith("processid="):
                    try:
                        pid = int(line.split("=", 1)[1].strip())
                    except ValueError:
                        pid = None
            # Flush last block
            if pid is not None and cmdline is not None:
                if pid != my_pid and self._cmdline_profile_exact(cmdline, profile_name):
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
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
