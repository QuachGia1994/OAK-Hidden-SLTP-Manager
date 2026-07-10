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
        
        # Auto-select active profile if any
        if self.profiles:
            active = list(self.profiles.keys())[0]
            self.load_profile_to_form(active)
            self._update_active_profile_badge(active)
        else:
            self.clear_form()


    def refresh_profile_list(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        p = getattr(self, "theme_palette", None)
        # Header badges: never merge RUNNING + EDITING into one ambiguous line
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
            # List rows: plain name; status is only in RUNNING/EDITING badges above
            color = p["text_primary"] if p else "white"
            if is_running:
                color = "#66bb6a"
            elif is_selected:
                color = "#ffb74d"

            btn_kwargs = {
                "text": name,
                "fg_color": "transparent",
                "border_width": 2 if (is_running or is_selected) else 1,
                "command": lambda n=name: self.load_profile_to_form(n),
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

        # Update Combo
        if hasattr(self, "combo_profiles"):
            self.combo_profiles.configure(values=list(self.profiles.keys()))
        if hasattr(self, "combo_pos_profiles"):
            self.combo_pos_profiles.configure(values=list(self.profiles.keys()))
        if hasattr(self, "combo_copy_profiles"):
            self.combo_copy_profiles.configure(values=list(self.profiles.keys()))


    def load_profile_to_form(self, name):
        self.selected_profile_name = name
        data = self.profiles[name]
        self.entries["name"].delete(0, "end"); self.entries["name"].insert(0, name)

        # Load Checkbox
        if data.get("use_balance_sltp", False):
            self.chk_balance.select()
        else:
            self.chk_balance.deselect()
        self.chk_visible_sltp.deselect()

        if data.get("visible_sltp", False):
            self.chk_visible_sltp.select()
        else:
            self.chk_visible_sltp.deselect()

        for key in data:
            if key in self.entries:
                val = str(data[key])
                # Mask token: if vaulted, show masked placeholder
                if key == "tele_token" and val == "__vault__":
                    val = "••••••••••••••••"
                self.entries[key].delete(0, "end")
                self.entries[key].insert(0, val)

        self._update_active_profile_badge(name)
        self._profile_form_snapshot = self._get_form_data()
        # Re-render the list so the ✎ Editing marker moves to this row
        # immediately, instead of staying on whatever was selected at the
        # last refresh (which made the list look out of sync with the form).
        self.refresh_profile_list()


    def clear_form(self):
        # Defaults
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
            "tele_token": "",
            "tele_chat": "",
            "tele_admin": ""
        }

        self.chk_balance.deselect()
        self.chk_visible_sltp.deselect()

        for key, ent in self.entries.items():
            ent.delete(0, "end")
            ent.insert(0, defaults.get(key, ""))


    def _get_form_data(self):
        """Snapshot current form data for unsaved detection."""
        data = {}
        for key, ent in self.entries.items():
            data[key] = ent.get().strip()
        data["use_balance_sltp"] = bool(self.chk_balance.get())
        data["visible_sltp"] = bool(self.chk_visible_sltp.get())
        return data


    def _update_active_profile_badge(self, name):
        """Always show both RUNNING and EDITING badges (never merge into one glyph)."""
        if hasattr(self, "lbl_active_profile"):
            run = self.running_profile_name or "—"
            edit = name or self.selected_profile_name or "—"
            self.lbl_active_profile.configure(
                text=f"RUNNING: {run}    EDITING: {edit}"
            )


    def _check_unsaved_changes(self):
        """Check if form has unsaved changes vs last saved snapshot."""
        if not hasattr(self, '_profile_form_snapshot') or self._profile_form_snapshot is None:
            return False
        current = self._get_form_data()
        return current != self._profile_form_snapshot


    def save_profile(self):
        name = self.entries["name"].get().strip()
        if not name: return

        # Start with existing data to preserve fields not in this form (e.g. Copy Trade settings)
        new_data = self.profiles.get(name, {}).copy()

        # Save Checkbox
        new_data["use_balance_sltp"] = bool(self.chk_balance.get())
        new_data["visible_sltp"] = bool(self.chk_visible_sltp.get())

        for key, ent in self.entries.items():
            if key == "name": continue
            val = ent.get().strip()
            if key == "path":
                val = val.strip('"').strip("'")
            # Store token in keyring if changed and not masked
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
        self.refresh_profile_list()
        self._profile_form_snapshot = self._get_form_data()
        if hasattr(self, 'lbl_unsaved'):
            self.lbl_unsaved.configure(text="")
        self.log(f"{T('msg_saved')} ({name})")


    def delete_profile(self):
        from tkinter import messagebox
        name = self.entries["name"].get().strip()
        if name not in self.profiles:
            return
        if not messagebox.askyesno("Confirm Delete", f"Delete profile '{name}'?\n\nThis action cannot be undone."):
            return
        # Check if profile is running
        if hasattr(self, 'workers') and name in self.workers:
            if self.workers[name].get("proc") and self.workers[name]["proc"].poll() is None:
                messagebox.showwarning("Warning", f"Profile '{name}' is currently running.\nStop it before deleting.")
                return
        del self.profiles[name]
        save_json(CONFIG_FILE, self.profiles)
        self.refresh_profile_list()
        self.clear_form()
        self.log(f"Profile '{name}' deleted")
