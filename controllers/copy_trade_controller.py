# -*- coding: utf-8 -*-
"""Copy Trading tab UI, role gating, safety test."""
from __future__ import annotations

class CopyTradeControllerMixin:
    """Copy Trading tab UI, role gating, safety test."""

    def create_copy_trade_frame(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["copy_trade"] = frame
        frame.pack(fill="both", expand=True)
        
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        # --- LEFT PANEL (Settings) ---
        left_panel = ctk.CTkScrollableFrame(frame, width=300)
        left_panel.pack(side="left", fill="y", padx=(0, 20))
        
        self.lbl_copy_title = ctk.CTkLabel(left_panel, text=T("lbl_copy_config_title"), font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_copy_title.pack(pady=10)
        self.add_ui_element("lbl_copy_config_title", self.lbl_copy_title)
        
        # Profile Selector in Copy Trade
        self.lbl_copy_sel = ctk.CTkLabel(left_panel, text=T("pos_lbl_profile"))
        self.lbl_copy_sel.pack(anchor="w", padx=10)
        self.add_ui_element("pos_lbl_profile_copy", self.lbl_copy_sel) # Unique key for this tab's profile label
        
        self.combo_copy_profiles = ctk.CTkComboBox(left_panel, values=list(self.profiles.keys()), command=self.on_copy_profile_change)
        self.combo_copy_profiles.pack(fill="x", padx=10, pady=(0, 10))
        if self.combo_profiles.get():
            self.combo_copy_profiles.set(self.combo_profiles.get())

        # Profile Info
        self.lbl_copy_profile = ctk.CTkLabel(left_panel, text="Profile: None", text_color="gray")
        self.lbl_copy_profile.pack(pady=(0, 20))
        
        # Role
        self.lbl_copy_role = ctk.CTkLabel(left_panel, text=T("lbl_copy_role"))
        self.lbl_copy_role.pack(anchor="w", padx=10)
        self.add_ui_element("lbl_copy_role", self.lbl_copy_role)
        
        self.combo_copy_role = ctk.CTkComboBox(
            left_panel, values=["None", "Master", "Slave"], command=self._on_copy_role_change
        )
        self.combo_copy_role.pack(fill="x", padx=10, pady=(0, 10))

        # Widgets disabled when Role=None
        self._copy_role_widgets = []

        # Channel
        self.lbl_copy_channel = ctk.CTkLabel(left_panel, text=T("lbl_master_name"))
        self.lbl_copy_channel.pack(anchor="w", padx=10)
        self.add_ui_element("lbl_master_name", self.lbl_copy_channel)

        self.ent_copy_channel = ctk.CTkEntry(left_panel)
        self.ent_copy_channel.pack(fill="x", padx=10, pady=(0, 10))
        self._copy_role_widgets.append(self.ent_copy_channel)

        # Lot Mode (Slave Only)
        self.lbl_copy_lot = ctk.CTkLabel(left_panel, text=T("lbl_lot_mode"))
        self.lbl_copy_lot.pack(anchor="w", padx=10)
        self.add_ui_element("lbl_lot_mode", self.lbl_copy_lot)

        self.combo_copy_lot = ctk.CTkComboBox(left_panel, values=["Fixed", "Multiplier", "Risk %"])
        self.combo_copy_lot.pack(fill="x", padx=10, pady=(0, 10))
        self._copy_role_widgets.append(self.combo_copy_lot)

        # Lot Value
        self.lbl_copy_val = ctk.CTkLabel(left_panel, text=T("lbl_lot_value"))
        self.lbl_copy_val.pack(anchor="w", padx=10)
        self.add_ui_element("lbl_lot_value", self.lbl_copy_val)

        self.ent_copy_value = ctk.CTkEntry(left_panel)
        self.ent_copy_value.pack(fill="x", padx=10, pady=(0, 10))
        self._copy_role_widgets.append(self.ent_copy_value)

        # Stealth
        self.chk_copy_stealth = ctk.CTkCheckBox(left_panel, text=T("lbl_stealth"))
        self.chk_copy_stealth.pack(anchor="w", padx=10, pady=(10, 5))
        self.add_ui_element("lbl_stealth", self.chk_copy_stealth)
        self._copy_role_widgets.append(self.chk_copy_stealth)

        # Max 1 Trade
        self.chk_copy_max_one = ctk.CTkCheckBox(left_panel, text=T("lbl_max_one"))
        self.chk_copy_max_one.pack(anchor="w", padx=10, pady=(5, 10))
        self.add_ui_element("lbl_max_one", self.chk_copy_max_one)
        self._copy_role_widgets.append(self.chk_copy_max_one)

        # --- SAFETY GUARDRAILS ---
        self.lbl_safety_title = ctk.CTkLabel(left_panel, text="Safety Guardrails", font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_safety_title.pack(anchor="w", padx=10, pady=(10, 5))

        # Max Daily Trades
        self.lbl_max_daily = ctk.CTkLabel(left_panel, text="Max Daily Trades")
        self.lbl_max_daily.pack(anchor="w", padx=10)
        self.ent_max_daily = ctk.CTkEntry(left_panel, placeholder_text="20")
        self.ent_max_daily.pack(fill="x", padx=10, pady=(0, 5))
        self._copy_role_widgets.append(self.ent_max_daily)

        # Max Lot Per Trade (+ equity-relative guidance)
        self.lbl_max_lot = ctk.CTkLabel(left_panel, text="Max Lot Per Trade")
        self.lbl_max_lot.pack(anchor="w", padx=10)
        self.ent_max_lot = ctk.CTkEntry(left_panel, placeholder_text="5.0")
        self.ent_max_lot.pack(fill="x", padx=10, pady=(0, 2))
        self._copy_role_widgets.append(self.ent_max_lot)
        self.lbl_max_lot_hint = ctk.CTkLabel(
            left_panel,
            text="Hint: size vs equity — e.g. 0.01 lot ≈ $1 risk/point on gold; keep max under ~2% equity",
            font=ctk.CTkFont(size=10),
            text_color="gray",
            wraplength=220,
            justify="left",
        )
        self.lbl_max_lot_hint.pack(anchor="w", padx=10, pady=(0, 5))

        # Max Exposure Per Symbol
        self.lbl_max_exposure = ctk.CTkLabel(left_panel, text="Max Exposure/Symbol (lots)")
        self.lbl_max_exposure.pack(anchor="w", padx=10)
        self.ent_max_exposure = ctk.CTkEntry(left_panel, placeholder_text="10.0")
        self.ent_max_exposure.pack(fill="x", padx=10, pady=(0, 5))
        self._copy_role_widgets.append(self.ent_max_exposure)

        # Kill Switch — dedicated danger card
        self.kill_card = ctk.CTkFrame(left_panel, fg_color="#3b1111", corner_radius=10, border_width=1, border_color="#ef4444")
        self.kill_card.pack(fill="x", padx=10, pady=(10, 8))
        ctk.CTkLabel(
            self.kill_card,
            text="KILL SWITCH",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#fecaca",
        ).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            self.kill_card,
            text="Blocks all new copy entries when ON",
            font=ctk.CTkFont(size=10),
            text_color="#fca5a5",
        ).pack(anchor="w", padx=12, pady=(0, 4))
        self.chk_kill_switch = ctk.CTkCheckBox(
            self.kill_card,
            text="Stop All New Trades",
            text_color="#fecaca",
            fg_color="#dc2626",
            hover_color="#b91c1c",
        )
        self.chk_kill_switch.pack(anchor="w", padx=12, pady=(0, 10))
        self._copy_role_widgets.append(self.chk_kill_switch)

        # Stale Threshold
        self.lbl_stale = ctk.CTkLabel(left_panel, text="Stale Signal Threshold (sec)")
        self.lbl_stale.pack(anchor="w", padx=10)
        self.ent_stale = ctk.CTkEntry(left_panel, placeholder_text="300")
        self.ent_stale.pack(fill="x", padx=10, pady=(0, 10))
        self._copy_role_widgets.append(self.ent_stale)

        # Ignored Symbols
        self.lbl_copy_ignore = ctk.CTkLabel(left_panel, text=T("lbl_ignore_sym"))
        self.lbl_copy_ignore.pack(anchor="w", padx=10)
        self.add_ui_element("lbl_ignore_sym", self.lbl_copy_ignore)

        self.ent_copy_ignore = ctk.CTkEntry(left_panel, placeholder_text="e.g. BTCUSD,ETHUSD")
        self.ent_copy_ignore.pack(fill="x", padx=10, pady=(0, 10))
        self._copy_role_widgets.append(self.ent_copy_ignore)

        # Save Config Button
        self.btn_save_copy = ctk.CTkButton(left_panel, text=T("btn_save_copy"), command=self.save_copy_config)
        self.btn_save_copy.pack(fill="x", padx=10, pady=20)
        self.add_ui_element("btn_save_copy", self.btn_save_copy)
        self._copy_role_widgets.append(self.btn_save_copy)

        self._on_copy_role_change(self.combo_copy_role.get())
        
        # --- Test Safety Rules Section ---
        self.lbl_test_safety = ctk.CTkLabel(left_panel, text="Test Safety Rules", font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_test_safety.pack(anchor="w", padx=10, pady=(10, 5))
        
        # Test Symbol
        self.lbl_test_symbol = ctk.CTkLabel(left_panel, text="Test Symbol")
        self.lbl_test_symbol.pack(anchor="w", padx=10)
        self.ent_test_symbol = ctk.CTkEntry(left_panel, placeholder_text="EURUSD")
        self.ent_test_symbol.pack(fill="x", padx=10, pady=(0, 5))
        
        # Test Lot
        self.lbl_test_lot = ctk.CTkLabel(left_panel, text="Test Lot")
        self.lbl_test_lot.pack(anchor="w", padx=10)
        self.ent_test_lot = ctk.CTkEntry(left_panel, placeholder_text="0.1")
        self.ent_test_lot.pack(fill="x", padx=10, pady=(0, 5))
        
        # Test Type
        self.lbl_test_type = ctk.CTkLabel(left_panel, text="Test Type")
        self.lbl_test_type.pack(anchor="w", padx=10)
        self.combo_test_type = ctk.CTkComboBox(left_panel, values=["BUY", "SELL"])
        self.combo_test_type.set("BUY")
        self.combo_test_type.pack(fill="x", padx=10, pady=(0, 10))
        
        # Test Button
        self.btn_test_safety = ctk.CTkButton(left_panel, text="Test Safety Rules", fg_color="#3b8ed0", command=self._on_test_safety_rules)
        self.btn_test_safety.pack(fill="x", padx=10, pady=5)
        
        # Start/Stop Monitor (Convenience)
        self.lbl_copy_control = ctk.CTkLabel(left_panel, text=T("lbl_control_monitor"), font=ctk.CTkFont(weight="bold"))
        self.lbl_copy_control.pack(pady=(20, 5))
        self.add_ui_element("lbl_control_monitor", self.lbl_copy_control)
        
        self.btn_copy_start = ctk.CTkButton(left_panel, text=T("btn_start"), fg_color="green", command=self.start_monitor)
        self.btn_copy_start.pack(fill="x", padx=10, pady=5)
        self.add_ui_element("btn_start", self.btn_copy_start)
        
        self.btn_copy_stop = ctk.CTkButton(left_panel, text=T("btn_stop"), fg_color="red", state="disabled", command=self.stop_monitor)
        self.btn_copy_stop.pack(fill="x", padx=10, pady=5)
        self.add_ui_element("btn_stop", self.btn_copy_stop)
        
        # --- RIGHT PANEL (Green Console) ---
        right_panel = ctk.CTkFrame(frame, fg_color="transparent")
        right_panel.pack(side="right", fill="both", expand=True)
        
        self.lbl_copy_log = ctk.CTkLabel(right_panel, text=T("lbl_copy_console_title"), font=ctk.CTkFont(weight="bold"))
        self.lbl_copy_log.pack(anchor="w", pady=5)
        self.add_ui_element("lbl_copy_console_title", self.lbl_copy_log)
        
        self.copy_console = ctk.CTkTextbox(right_panel, font=("Consolas", 12), wrap="word")
        self.copy_console.pack(fill="both", expand=True)
        self.copy_console.configure(state="disabled")


    def _on_copy_role_change(self, role=None):
        """Disable copy configuration until Role is Master or Slave."""
        if role is None and hasattr(self, "combo_copy_role"):
            try:
                role = self.combo_copy_role.get()
            except Exception:
                role = "None"
        enabled = str(role or "None").strip().lower() in ("master", "slave")
        state = "normal" if enabled else "disabled"
        for w in getattr(self, "_copy_role_widgets", []) or []:
            try:
                w.configure(state=state)
            except Exception:
                pass
        # Kill card stays visible but checkbox follows state
        try:
            if hasattr(self, "kill_card"):
                self.kill_card.configure(border_color="#ef4444" if enabled else "#7f1d1d")
        except Exception:
            pass


    def load_copy_config(self):
        # Load from current selected profile in Dashboard combo
        if not hasattr(self, 'combo_profiles'): return
        
        name = self.combo_profiles.get()
        if not name or name not in self.profiles:
            self.lbl_copy_profile.configure(text="Profile: None")
            return
            
        self.lbl_copy_profile.configure(text=f"Profile: {name}")
        data = self.profiles[name]
        
        self.combo_copy_role.set(data.get("copy_role", "None"))
        self.ent_copy_channel.delete(0, "end"); self.ent_copy_channel.insert(0, data.get("copy_channel", ""))
        self.combo_copy_lot.set(data.get("copy_lot_mode", "Fixed"))
        self.ent_copy_value.delete(0, "end"); self.ent_copy_value.insert(0, data.get("copy_lot_value", "0.01"))
        
        if data.get("copy_stealth", False):
            self.chk_copy_stealth.select()
        else:
            self.chk_copy_stealth.deselect()
            
        if data.get("copy_max_one", False):
            self.chk_copy_max_one.select()
        else:
            self.chk_copy_max_one.deselect()
            
        self.ent_copy_ignore.delete(0, "end")
        self.ent_copy_ignore.insert(0, data.get("copy_ignore_list", ""))

        # Safety guardrails
        self.ent_max_daily.delete(0, "end")
        self.ent_max_daily.insert(0, str(data.get("copy_max_daily_trades", "20")))
        self.ent_max_lot.delete(0, "end")
        self.ent_max_lot.insert(0, str(data.get("copy_max_lot_per_trade", "5.0")))
        self.ent_max_exposure.delete(0, "end")
        self.ent_max_exposure.insert(0, str(data.get("copy_max_exposure", "10.0")))
        if data.get("copy_kill_switch", False):
            self.chk_kill_switch.select()
        else:
            self.chk_kill_switch.deselect()
        self.ent_stale.delete(0, "end")
        self.ent_stale.insert(0, str(data.get("copy_stale_threshold", "300")))
        self._on_copy_role_change(self.combo_copy_role.get())


    def save_copy_config(self):
        name = self.combo_profiles.get()
        if not name or name not in self.profiles:
            return

        data = self.profiles[name]
        new_role = self.combo_copy_role.get()
        old_role = data.get("copy_role", "None")

        # Confirm when changing to Master/Slave
        if new_role != old_role and new_role in ("Master", "Slave"):
            from tkinter import messagebox
            role_desc = "send trades (Master)" if new_role == "Master" else "copy trades (Slave)"
            if not messagebox.askyesno("Confirm Role Change",
                                       f"Set '{name}' as {new_role}?\n\nThis will {role_desc}.\n\nContinue?"):
                return
            data["copy_role"] = new_role
            self.log(f"⚠️ [{name}] Role changed to {new_role.upper()}")
        else:
            data["copy_role"] = new_role
        data["copy_channel"] = self.ent_copy_channel.get().strip()
        data["copy_lot_mode"] = self.combo_copy_lot.get()
        data["copy_lot_value"] = self.ent_copy_value.get().strip()
        data["copy_stealth"] = bool(self.chk_copy_stealth.get())
        data["copy_max_one"] = bool(self.chk_copy_max_one.get())
        data["copy_ignore_list"] = self.ent_copy_ignore.get().strip()

        # Safety guardrails
        data["copy_max_daily_trades"] = self.ent_max_daily.get().strip() or "20"
        data["copy_max_lot_per_trade"] = self.ent_max_lot.get().strip() or "5.0"
        data["copy_max_exposure"] = self.ent_max_exposure.get().strip() or "10.0"
        data["copy_kill_switch"] = bool(self.chk_kill_switch.get())
        data["copy_stale_threshold"] = self.ent_stale.get().strip() or "300"

        save_json(CONFIG_FILE, self.profiles)
        self.log(f"Copy Trade Config Saved for {name}")


    def _on_test_safety_rules(self):
        """
        Test safety rules using the selected profile's config and user input
        Displays result in the Copy Console and as a log message
        """
        name = self.combo_profiles.get()
        if not name or name not in self.profiles:
            self.log("❌ Select a profile first to test safety rules!")
            return

        # First make sure the current config is saved
        self.save_copy_config()

        # Read user inputs
        test_symbol = self.ent_test_symbol.get().strip()
        if not test_symbol:
            test_symbol = "EURUSD"

        test_lot_str = self.ent_test_lot.get().strip()
        try:
            test_lot = float(test_lot_str.replace(",", "."))
        except:
            test_lot = 0.1

        test_type = self.combo_test_type.get()

        # Create a temporary CopyTradeManager with current config to test
        profile_config = self.profiles[name].copy()
        profile_config["profile_name"] = name

        # Update with any changes from the UI (in case not saved yet)
        profile_config["copy_role"] = self.combo_copy_role.get()
        profile_config["copy_max_daily_trades"] = self.ent_max_daily.get().strip() or "20"
        profile_config["copy_max_lot_per_trade"] = self.ent_max_lot.get().strip() or "5.0"
        profile_config["copy_max_exposure"] = self.ent_max_exposure.get().strip() or "10.0"
        profile_config["copy_kill_switch"] = bool(self.chk_kill_switch.get())

        # Create test manager instance
        test_manager = CopyTradeManager(profile_config, lambda msg: None)

        # Run the test
        result = test_manager.test_safety_rules(test_symbol, test_lot, test_type)

        # Format and display result
        timestamp = datetime.now().strftime("%H:%M:%S")
        if result["allowed"]:
            status_icon = "✅"
            status_color = "#66bb6a"
        else:
            status_icon = "❌"
            status_color = "#ef5350"

        result_text = f"[{timestamp}] {status_icon} Safety Test Result:\n"
        result_text += f"  Symbol: {test_symbol}\n"
        result_text += f"  Lot: {test_lot}\n"
        result_text += f"  Type: {test_type}\n"
        result_text += f"\n{result['reason']}\n"

        # Update the copy console
        self.copy_console.configure(state="normal")
        self.copy_console.insert("end", "\n" + "="*60 + "\n")
        self.copy_console.insert("end", result_text)
        self.copy_console.insert("end", "="*60 + "\n")
        self.copy_console.see("end")
        self.copy_console.configure(state="disabled")

        # Also log the result
        log_msg = f"[{name}] Safety Test: {'ALLOWED' if result['allowed'] else 'BLOCKED'} for {test_symbol} x {test_lot}"
        self.log(log_msg)


    def on_copy_profile_change(self, choice):
        # Sync with main profile combo
        self.combo_profiles.set(choice)
        self.on_profile_change(choice)
        self.load_copy_config() # Specific for copy trade tab
        self.log(f"Profile switched to {choice} (from Copy Trade tab)")
