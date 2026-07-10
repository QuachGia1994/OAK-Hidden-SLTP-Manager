# -*- coding: utf-8 -*-
"""Profile list, form load/save, RUNNING/EDITING badges."""
from __future__ import annotations


class ProfileControllerMixin:
    """Profile list, form load/save, RUNNING/EDITING badges."""

    def create_profiles_frame(self, parent):
        self.profiles_tab = ProfilesTab(self)
        self.profiles_tab.mount(parent)

        # Map tab's attributes to app for backwards compatibility
        self.list_frame = self.profiles_tab.list_frame
        self.right_panel = self.profiles_tab.right_panel
        self.form_scroll = self.profiles_tab.form_scroll
        self.chk_balance = self.profiles_tab.chk_balance
        self.chk_visible_sltp = self.profiles_tab.chk_visible_sltp
        self.entries = self.profiles_tab.entries
        self.lbl_active_profile = self.profiles_tab.lbl_active_profile
        self.lbl_unsaved = self.profiles_tab.lbl_unsaved
        self.btn_save_p = self.profiles_tab.btn_save
        self.btn_del_p = self.profiles_tab.btn_delete
        self.btn_add_p = self.profiles_tab.btn_add

        self.refresh_profile_list()

        # Prefer RUNNING / combo selection / previously selected
        if self.profiles:
            active = (
                getattr(self, "selected_profile_name", None)
                or getattr(self, "running_profile_name", None)
                or ""
            )
            try:
                if hasattr(self, "combo_profiles") and self.combo_profiles.winfo_exists():
                    cur = (self.combo_profiles.get() or "").strip()
                    if cur in self.profiles:
                        active = cur
            except Exception:
                pass
            if not active or active not in self.profiles:
                active = list(self.profiles.keys())[0]
            self.select_profile(active, source="profiles_mount", clear_console=False)
        else:
            self.selected_profile_name = None
            self.clear_form()
            self._update_active_profile_badge(None)

    def select_profile(self, name, *, source="api", load_form=True, clear_console=None):
        """Atomic profile switch — single source of truth for editing state.

        Updates: selected_profile_name, config, CopyTradeManager, all combos,
        pending list, Profiles form, badges, UI start/stop state.
        """
        if getattr(self, "_selecting_profile", False):
            return False
        if not name or name not in getattr(self, "profiles", {}):
            return False

        self._selecting_profile = True
        try:
            self.selected_profile_name = name

            # Domain runtime config used by pending / copy / monitor
            self.config = self.profiles[name]
            self.config["profile_name"] = name

            CTM = None
            try:
                if hasattr(self, "services") and self.services is not None:
                    CTM = self.services.CopyTradeManager
                else:
                    CTM = CopyTradeManager  # free-name via runtime bind
            except Exception:
                try:
                    import OAK_Hidden_SLTP_Manager as oak

                    CTM = oak.CopyTradeManager
                except Exception:
                    CTM = None
            if CTM is not None:
                try:
                    self.copy_manager = CTM(self.config, self.notify)
                except Exception as e:
                    try:
                        self.log(f"CopyTradeManager init: {e}")
                    except Exception:
                        pass

            self._last_json_mtime = 0

            # Combos (callback re-entry blocked by _selecting_profile)
            for attr in ("combo_profiles", "combo_pos_profiles", "combo_copy_profiles"):
                w = getattr(self, attr, None)
                if w is None:
                    continue
                try:
                    if w.winfo_exists():
                        vals = list(self.profiles.keys())
                        try:
                            w.configure(values=vals)
                        except Exception:
                            pass
                        w.set(name)
                except Exception:
                    pass
            try:
                if hasattr(self, "lbl_copy_profile") and self.lbl_copy_profile.winfo_exists():
                    self.lbl_copy_profile.configure(text=f"Profile: {name}")
            except Exception:
                pass

            # Form fields
            if load_form and getattr(self, "entries", None):
                self._fill_profile_form_fields(name)

            # Pending list from this profile's scheduled file
            try:
                # Ensure pending combo text matches before refresh (widget may lag)
                if hasattr(self, "combo_pos_profiles") and self.combo_pos_profiles is not None:
                    try:
                        if self.combo_pos_profiles.winfo_exists():
                            if (self.combo_pos_profiles.get() or "") != name:
                                self.combo_pos_profiles.set(name)
                    except Exception:
                        pass
                self.update_scheduled_list_ui()
            except Exception:
                pass

            # Worker logs on dashboard/copy consoles
            if clear_console is None:
                clear_console = source in ("dashboard_combo", "startup")
            if clear_console:
                self._reload_worker_console_for_profile(name)

            self._update_active_profile_badge(name)
            self.refresh_profile_list()
            try:
                self.update_ui_state(name)
            except Exception:
                pass

            if source not in ("silent", "profiles_mount"):
                try:
                    sf = getattr(getattr(self, "copy_manager", None), "scheduled_file", "")
                    self.log(f"Profile: {name} - Sync File: {sf}")
                except Exception:
                    pass
            return True
        finally:
            self._selecting_profile = False

    def _fill_profile_form_fields(self, name):
        """Write profile data into the Profiles form widgets only."""
        if not name or name not in self.profiles or not getattr(self, "entries", None):
            return
        data = self.profiles[name]
        for key, ent in self.entries.items():
            try:
                ent.delete(0, "end")
            except Exception:
                pass
        try:
            self.entries["name"].insert(0, name)
        except Exception:
            pass
        try:
            if data.get("use_balance_sltp", False):
                self.chk_balance.select()
            else:
                self.chk_balance.deselect()
        except Exception:
            pass
        try:
            if data.get("visible_sltp", False):
                self.chk_visible_sltp.select()
            else:
                self.chk_visible_sltp.deselect()
        except Exception:
            pass
        for key, ent in self.entries.items():
            if key == "name" or key not in data:
                continue
            val = str(data[key])
            if key == "tele_token" and val == "__vault__":
                val = "••••••••••••••••"
            try:
                ent.insert(0, val)
            except Exception:
                pass
        try:
            self._profile_form_snapshot = self._get_form_data()
        except Exception:
            self._profile_form_snapshot = None

    def _reload_worker_console_for_profile(self, name):
        """Clear dashboard/copy consoles and replay logs for profile if any."""
        try:
            self.console.configure(state="normal")
            self.console.delete("1.0", "end")
            self.console.configure(state="disabled")
        except Exception:
            pass
        try:
            if hasattr(self, "copy_console") and self.copy_console.winfo_exists():
                self.copy_console.configure(state="normal")
                self.copy_console.delete("1.0", "end")
                self.copy_console.configure(state="disabled")
        except Exception:
            pass
        if name not in getattr(self, "workers", {}):
            return
        logs = self.workers[name].get("logs") or []
        if not logs:
            return
        full_log = "\n".join(logs) + "\n"
        try:
            self.console.configure(state="normal")
            self.console.insert("end", full_log)
            self.console.see("end")
            self.console.configure(state="disabled")
        except Exception:
            pass
        try:
            if hasattr(self, "copy_console") and self.copy_console.winfo_exists():
                self.copy_console.configure(state="normal")
                self.copy_console.insert("end", full_log)
                self.copy_console.see("end")
                self.copy_console.configure(state="disabled")
        except Exception:
            pass

    def refresh_profile_list(self):
        if not getattr(self, "list_frame", None):
            return
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        p = getattr(self, "theme_palette", None)
        hdr = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 6))
        run_txt = self.running_profile_name or "—"
        edit_txt = self.selected_profile_name or "—"
        ctk.CTkLabel(
            hdr,
            text=f"RUNNING: {run_txt}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#66bb6a",
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            hdr,
            text=f"EDITING: {edit_txt}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ffb74d",
            anchor="w",
        ).pack(fill="x")

        for name in self.profiles:
            is_running = name == self.running_profile_name
            is_selected = name == self.selected_profile_name
            color = p["text_primary"] if p else "white"
            if is_running:
                color = "#66bb6a"
            elif is_selected:
                color = "#ffb74d"

            btn_kwargs = {
                "text": name,
                "fg_color": "transparent",
                "border_width": 2 if (is_running or is_selected) else 1,
                "command": lambda n=name: self.select_profile(
                    n, source="profiles_list", clear_console=False
                ),
            }
            if p:
                btn_kwargs.update({
                    "text_color": color,
                    "border_color": (
                        "#66bb6a" if is_running else ("#ffb74d" if is_selected else p["card_border"])
                    ),
                    "hover_color": p["panel_alt_bg"],
                })
            btn = ctk.CTkButton(self.list_frame, **btn_kwargs)
            btn.pack(pady=2, fill="x")

        if hasattr(self, "combo_profiles"):
            try:
                self.combo_profiles.configure(values=list(self.profiles.keys()))
            except Exception:
                pass
        if hasattr(self, "combo_pos_profiles"):
            try:
                self.combo_pos_profiles.configure(values=list(self.profiles.keys()))
            except Exception:
                pass
        if hasattr(self, "combo_copy_profiles"):
            try:
                self.combo_copy_profiles.configure(values=list(self.profiles.keys()))
            except Exception:
                pass

    def load_profile_to_form(self, name, *, sync_combo=True):
        """Back-compat wrapper → atomic select_profile."""
        self.select_profile(
            name,
            source="profiles_list",
            load_form=True,
            clear_console=False,
        )

    def clear_form(self):
        defaults = {
            "name": "",
            "path": "",
            "magic": "0",
            "symbol": "GBPUSD,GBPJPY,GBPAUD,USDJPY",
            "sl": "350",
            "tp": "2500",
            "gold_sl": "1000",
            "gold_tp": "20000",
            "balance_sl_pct": "1.0",
            "balance_tp_pct": "2.0",
            "partial_r": "2",
            "partial_pct": "50",
            "auto_be": "2",
            "tele_token": "",
            "tele_chat": "",
            "tele_admin": "",
        }
        self.selected_profile_name = None
        try:
            self.chk_balance.deselect()
            self.chk_visible_sltp.deselect()
        except Exception:
            pass
        for key, ent in (getattr(self, "entries", None) or {}).items():
            try:
                ent.delete(0, "end")
                ent.insert(0, defaults.get(key, ""))
            except Exception:
                pass
        self._update_active_profile_badge(None)
        self.refresh_profile_list()

    def _get_form_data(self):
        data = {}
        for key, ent in self.entries.items():
            data[key] = ent.get().strip()
        data["use_balance_sltp"] = bool(self.chk_balance.get())
        data["visible_sltp"] = bool(self.chk_visible_sltp.get())
        return data

    def _update_active_profile_badge(self, name):
        if hasattr(self, "lbl_active_profile"):
            run = self.running_profile_name or "—"
            edit = name or self.selected_profile_name or "—"
            try:
                self.lbl_active_profile.configure(
                    text=f"RUNNING: {run}    EDITING: {edit}"
                )
            except Exception:
                pass

    def _check_unsaved_changes(self):
        if not hasattr(self, "_profile_form_snapshot") or self._profile_form_snapshot is None:
            return False
        return self._get_form_data() != self._profile_form_snapshot

    def save_profile(self):
        name = self.entries["name"].get().strip()
        if not name:
            return

        new_data = self.profiles.get(name, {}).copy()
        new_data["use_balance_sltp"] = bool(self.chk_balance.get())
        new_data["visible_sltp"] = bool(self.chk_visible_sltp.get())

        for key, ent in self.entries.items():
            if key == "name":
                continue
            val = ent.get().strip()
            if key == "path":
                val = val.strip('"').strip("'")
            if key == "tele_token" and val and val != "••••••••••••••••" and val != "__vault__":
                from secret_store import store_secret

                store_secret(name, "tele_token", val)
                new_data[key] = "__vault__"
            elif key == "tele_token" and (val == "••••••••••••••••" or val == "__vault__"):
                new_data[key] = "__vault__"
            else:
                new_data[key] = val

        self.profiles[name] = new_data
        save_json(CONFIG_FILE, self.profiles)
        self.select_profile(name, source="save", clear_console=False)
        self._profile_form_snapshot = self._get_form_data()
        if hasattr(self, "lbl_unsaved"):
            try:
                self.lbl_unsaved.configure(text="")
            except Exception:
                pass
        self.log(f"{T('msg_saved')} ({name})")

    def delete_profile(self):
        from tkinter import messagebox

        name = self.entries["name"].get().strip()
        if name not in self.profiles:
            return
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete profile '{name}'?\n\nThis action cannot be undone.",
        ):
            return
        if hasattr(self, "workers") and name in self.workers:
            if self.workers[name].get("proc") and self.workers[name]["proc"].poll() is None:
                messagebox.showwarning(
                    "Warning",
                    f"Profile '{name}' is currently running.\nStop it before deleting.",
                )
                return
        del self.profiles[name]
        save_json(CONFIG_FILE, self.profiles)
        self.refresh_profile_list()
        self.clear_form()
        self.log(f"Profile '{name}' deleted")
