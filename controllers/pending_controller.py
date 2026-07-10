# -*- coding: utf-8 -*-
"""Pending/scheduled orders UI and CRUD."""
from __future__ import annotations

class PendingControllerMixin:
    """Pending/scheduled orders UI and CRUD."""

    def create_pos_size_frame(self, parent):
        # Create main container
        container = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["pos_size"] = container
        container.pack(fill="both", expand=True)
        
        # Grid layout: 2 columns (Left: Inputs, Right: List)
        container.grid_columnconfigure(0, weight=1) # Inputs
        container.grid_columnconfigure(1, weight=3) # List
        container.grid_rowconfigure(0, weight=1)
        
        # --- LEFT COLUMN: INPUTS ---
        left_frame = ctk.CTkFrame(container, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # 1. Profile
        self.lbl_pos_profile = ctk.CTkLabel(left_frame, text=T("pos_lbl_profile"), anchor="w")
        self.lbl_pos_profile.pack(fill="x", padx=5, pady=(5,0))
        self.add_ui_element("pos_lbl_profile", self.lbl_pos_profile)

        self.combo_pos_profiles = ctk.CTkComboBox(left_frame, values=list(self.profiles.keys()), command=self.on_pos_profile_change, height=30)
        self.combo_pos_profiles.pack(fill="x", padx=5, pady=(0,5))
        if hasattr(self, 'combo_profiles') and self.combo_profiles.get():
            self.combo_pos_profiles.set(self.combo_profiles.get())

        # 2. Symbol
        self.lbl_pos_sym = ctk.CTkLabel(left_frame, text=T("pos_lbl_symbol"), anchor="w")
        self.lbl_pos_sym.pack(fill="x", padx=5, pady=(5,0))
        self.add_ui_element("pos_lbl_symbol", self.lbl_pos_sym)

        self.ent_pos_sym = ctk.CTkEntry(left_frame, placeholder_text="e.g. XAUUSD", height=30)
        self.ent_pos_sym.pack(fill="x", padx=5, pady=(0,5))

        # 3. Type
        ctk.CTkLabel(left_frame, text="Type:", anchor="w").pack(fill="x", padx=5, pady=(5,0))
        self.seg_pos_type = ctk.CTkSegmentedButton(left_frame, values=["BUY", "SELL"], height=30)
        self.seg_pos_type.set("BUY")
        self.seg_pos_type.pack(fill="x", padx=5, pady=(0,5))

        # 4. Lot
        ctk.CTkLabel(left_frame, text="Lot:", anchor="w").pack(fill="x", padx=5, pady=(5,0))
        self.val_pos_lot = ctk.CTkEntry(left_frame, height=30)
        self.val_pos_lot.insert(0, "0.01")
        self.val_pos_lot.pack(fill="x", padx=5, pady=(0,5))

        # 5. SL
        self.lbl_pos_sl = ctk.CTkLabel(left_frame, text=T("pos_lbl_sl"), anchor="w")
        self.lbl_pos_sl.pack(fill="x", padx=5, pady=(5,0))
        self.add_ui_element("pos_lbl_sl", self.lbl_pos_sl)

        self.ent_pos_sl = ctk.CTkEntry(left_frame, height=30)
        self.ent_pos_sl.insert(0, "0")
        self.ent_pos_sl.pack(fill="x", padx=5, pady=(0,5))

        # 6. TP
        self.lbl_pos_tp = ctk.CTkLabel(left_frame, text=T("pos_lbl_tp"), anchor="w")
        self.lbl_pos_tp.pack(fill="x", padx=5, pady=(5,0))
        self.add_ui_element("pos_lbl_tp", self.lbl_pos_tp)

        self.ent_pos_tp = ctk.CTkEntry(left_frame, height=30)
        self.ent_pos_tp.insert(0, "0")
        self.ent_pos_tp.pack(fill="x", padx=5, pady=(0,5))

        # 7. Time
        self.lbl_pos_time = ctk.CTkLabel(left_frame, text=T("pos_lbl_time"), anchor="w")
        self.lbl_pos_time.pack(fill="x", padx=5, pady=(5,0))
        self.add_ui_element("pos_lbl_time", self.lbl_pos_time)

        self.ent_pos_time = ctk.CTkEntry(left_frame, placeholder_text="HH:MM:SS", height=30)
        self.ent_pos_time.insert(0, datetime.now().strftime("%H:%M:%S"))
        self.ent_pos_time.pack(fill="x", padx=5, pady=(0,5))

        # 8. Schedule Button
        self.btn_pos_schedule = ctk.CTkButton(left_frame, text=T("pos_btn_schedule"), fg_color="#ffc107", text_color="black",
                                              hover_color="#e0a800", height=40, font=ctk.CTkFont(weight="bold"),
                                              command=self.add_scheduled_trade)
        self.btn_pos_schedule.pack(fill="x", padx=5, pady=20)
        self.add_ui_element("pos_btn_schedule", self.btn_pos_schedule)

        # 9. Status Msg
        self.lbl_pos_msg = ctk.CTkLabel(left_frame, text="", text_color="yellow", font=ctk.CTkFont(size=13, slant="italic"), wraplength=200)
        self.lbl_pos_msg.pack(fill="x", padx=5, pady=5)


        # --- RIGHT COLUMN: LIST ---
        right_frame = ctk.CTkFrame(container, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_frame.grid_rowconfigure(1, weight=1) # Treeview expands
        right_frame.grid_columnconfigure(0, weight=1)

        # Header + show-history toggle (executed orders collapsed by default)
        hdr_row = ctk.CTkFrame(right_frame, fg_color="transparent")
        hdr_row.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.lbl_pos_list = ctk.CTkLabel(hdr_row, text=T("pos_list_header"), font=ctk.CTkFont(weight="bold", size=14))
        self.lbl_pos_list.pack(side="left")
        self.add_ui_element("pos_list_header", self.lbl_pos_list)
        self._show_executed_pending = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            hdr_row,
            text="Show executed / history",
            variable=self._show_executed_pending,
            font=ctk.CTkFont(size=11),
            command=self.update_scheduled_list_ui,
        ).pack(side="right", padx=4)

        # Treeview Container
        tree_container = ctk.CTkFrame(right_frame, fg_color="transparent")
        tree_container.grid(row=1, column=0, sticky="nsew")

        self._apply_scheduled_tree_style()

        self.tree_scheduled = ttk.Treeview(
            tree_container,
            columns=("Symbol", "Type", "Lot", "Time", "Status", "NextAction"),
            show="headings",
            height=20,
            style="Scheduled.Treeview",
        )

        self.tree_scheduled.heading("Symbol", text="Symbol")
        self.tree_scheduled.heading("Type", text="Type")
        self.tree_scheduled.heading("Lot", text="Lot")
        self.tree_scheduled.heading("Time", text="Time")
        self.tree_scheduled.heading("Status", text="Status")
        self.tree_scheduled.heading("NextAction", text="Next Action")

        # Time is single-line — give it width so date+time never wrap
        self.tree_scheduled.column("Symbol", width=90, minwidth=70, anchor="center", stretch=False)
        self.tree_scheduled.column("Type", width=55, minwidth=50, anchor="center", stretch=False)
        self.tree_scheduled.column("Lot", width=55, minwidth=45, anchor="center", stretch=False)
        self.tree_scheduled.column("Time", width=175, minwidth=160, anchor="w", stretch=True)
        self.tree_scheduled.column("Status", width=100, minwidth=80, anchor="center", stretch=False)
        self.tree_scheduled.column("NextAction", width=160, minwidth=100, anchor="w", stretch=True)

        self.tree_scheduled.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree_scheduled.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree_scheduled.configure(yscrollcommand=scrollbar.set)

        # Context Menu — clear actions: edit / cancel / save
        self.context_menu = tkinter.Menu(self.main_frame, tearoff=0)
        self.context_menu.add_command(label=T("pos_btn_edit"), command=self.edit_scheduled_trade)
        self.context_menu.add_command(label=T("pos_btn_del"), command=self.delete_scheduled_trade)
        self.context_menu.add_command(label=T("pos_btn_save"), command=self.save_scheduled_trades_ui)

        def do_popup(event):
            try:
                item = self.tree_scheduled.identify_row(event.y)
                if item:
                    self.tree_scheduled.selection_set(item)
                    self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

        self.tree_scheduled.bind("<Button-3>", do_popup)


    def _apply_scheduled_tree_style(self):
        """Match Pending tree colors to active app theme (Light vs Dark)."""
        style = ttk.Style()
        try:
            style.theme_use("default")
        except Exception:
            pass
        theme = (self.settings.get("theme") if hasattr(self, "settings") else None) or "light"
        if str(theme).lower() in ("light", "soft", "white"):
            bg, fg, head_bg, sel = "#f8fafc", "#0f172a", "#e2e8f0", "#bae6fd"
        else:
            bg, fg, head_bg, sel = "#1a1a2e", "#e0e0e0", "#16213e", "#0f3460"
        style.configure(
            "Scheduled.Treeview",
            rowheight=28,
            background=bg,
            foreground=fg,
            fieldbackground=bg,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Scheduled.Treeview.Heading",
            background=head_bg,
            foreground=fg,
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        style.map(
            "Scheduled.Treeview",
            background=[("selected", sel)],
            foreground=[("selected", fg if theme == "light" else "#ffffff")],
        )


    def add_scheduled_trade(self):
        try:
            symbol = self.ent_pos_sym.get().strip().upper()
            lot = self.val_pos_lot.get().strip()
            sl = self.ent_pos_sl.get().strip()
            tp = self.ent_pos_tp.get().strip()
            time_str = self.ent_pos_time.get().strip()
            t_type_str = self.seg_pos_type.get()
            t_type = mt5.ORDER_TYPE_BUY if t_type_str == "BUY" else mt5.ORDER_TYPE_SELL
            
            # Basic validation
            if not symbol or not lot or not time_str:
                self.lbl_pos_msg.configure(text="Missing Info", text_color="red")
                return
            
            # Check if already holding this symbol or has a pending order for it
            # 1. Check open positions (Only fail if same symbol AND same direction)
            positions = mt5.positions_get(symbol=symbol)
            if positions:
                for pos in positions:
                    if pos.type == t_type:
                        self.lbl_pos_msg.configure(text=T("pos_msg_fail_pending_exists").format(symbol=symbol), text_color="red")
                        return
            
            # 2. Check pending list (Only fail if same symbol AND same direction)
            if hasattr(self, 'copy_manager'):
                for t in self.copy_manager.scheduled_trades:
                    if t.get("status") == "waiting" and t.get("symbol") == symbol and t.get("type") == t_type:
                        self.lbl_pos_msg.configure(text=T("pos_msg_fail_pending_exists").format(symbol=symbol), text_color="red")
                        return

            # Time format validation
            try:
                if len(time_str.split(":")) == 2: time_str += ":00"
                # Calculate Target Date (Tomorrow if time < now - tolerance)
                now_dt = datetime.now()
                target_dt = datetime.strptime(time_str, "%H:%M:%S").replace(year=now_dt.year, month=now_dt.month, day=now_dt.day)

                if target_dt < (now_dt - timedelta(seconds=60)):
                    target_dt += timedelta(days=1)
                while target_dt.weekday() in (5, 6):
                    target_dt += timedelta(days=1)
                
                target_date_str = target_dt.strftime("%Y-%m-%d")
                
                # Normalize time string to HH:MM:SS (ensure leading zeros for correct string comparison)
                time_str = target_dt.strftime("%H:%M:%S")
                
            except:
                self.lbl_pos_msg.configure(text=T("pos_msg_invalid_time"), text_color="red")
                return
            
            new_trade = {
                "symbol": symbol,
                "type": t_type, 
                "lot": lot,
                "sl": sl,
                "tp": tp,
                "time": time_str,
                "date": target_date_str,
                "status": "waiting"
            }
            
            if hasattr(self, 'copy_manager'):
                self.copy_manager.scheduled_trades.append(new_trade)
                # Sort by date and time
                self.copy_manager.scheduled_trades.sort(key=lambda x: (x.get("date", ""), x["time"]))
                save_json(self.copy_manager.scheduled_file, self.copy_manager.scheduled_trades)
                self.update_scheduled_list_ui()
                
                # Determine time description (Today vs Tomorrow)
                time_desc = time_str
                if target_dt.date() > now_dt.date():
                    day_name = "ngày mai" if (target_dt.date() - now_dt.date()).days == 1 else f"ngày {target_dt.strftime('%d/%m')}"
                    time_desc = f"{time_str} {day_name} ({target_dt.strftime('%d/%m')})"
                
                self.lbl_pos_msg.configure(text=T("pos_msg_scheduled").format(symbol=symbol, type=t_type_str, lot=lot, time=time_desc), text_color="green")
            else:
                self.lbl_pos_msg.configure(text="Copy Manager not initialized", text_color="red")
                
        except Exception as e:
            self.lbl_pos_msg.configure(text=f"Error: {e}", text_color="red")


    def edit_scheduled_trade(self):
        selected = self.tree_scheduled.selection()
        if not selected: return
        
        idx = self.tree_scheduled.index(selected[0])
        
        if hasattr(self, 'copy_manager') and idx < len(self.copy_manager.scheduled_trades):
            trade = self.copy_manager.scheduled_trades.pop(idx)
            
            # Load into UI
            self.ent_pos_sym.delete(0, "end")
            self.ent_pos_sym.insert(0, trade["symbol"])
            
            self.val_pos_lot.delete(0, "end")
            self.val_pos_lot.insert(0, trade["lot"])
            
            self.ent_pos_sl.delete(0, "end")
            self.ent_pos_sl.insert(0, trade["sl"])
            
            self.ent_pos_tp.delete(0, "end")
            self.ent_pos_tp.insert(0, trade["tp"])
            
            self.ent_pos_time.delete(0, "end")
            self.ent_pos_time.insert(0, trade["time"])
            
            t_type_str = "BUY" if trade["type"] == mt5.ORDER_TYPE_BUY else "SELL"
            self.seg_pos_type.set(t_type_str)
            
            save_json(self.copy_manager.scheduled_file, self.copy_manager.scheduled_trades)
            self.update_scheduled_list_ui()
            self.lbl_pos_msg.configure(text="Loaded for editing", text_color="yellow")


    def delete_scheduled_trade(self):
        selected = self.tree_scheduled.selection()
        if not selected: return
        
        # Sort indices in reverse to avoid index shifting while popping
        indices = sorted([self.tree_scheduled.index(item) for item in selected], reverse=True)
        
        if hasattr(self, 'copy_manager'):
            for idx in indices:
                if idx < len(self.copy_manager.scheduled_trades):
                    self.copy_manager.scheduled_trades.pop(idx)
            
            save_json(self.copy_manager.scheduled_file, self.copy_manager.scheduled_trades)
            self.update_scheduled_list_ui()


    def save_scheduled_trades_ui(self):
        if hasattr(self, 'copy_manager'):
            save_json(self.copy_manager.scheduled_file, self.copy_manager.scheduled_trades)
            self.log("Scheduled Trades Saved")


    def update_scheduled_list_ui(self):
        if not hasattr(self, "tree_scheduled"):
            return
        # Clear tree
        for item in self.tree_scheduled.get_children():
            self.tree_scheduled.delete(item)

        if not hasattr(self, "copy_manager"):
            return

        show_history = True
        try:
            show_history = bool(self._show_executed_pending.get())
        except Exception:
            show_history = True

        # Terminal statuses collapsed unless "Show executed / history" is on
        history_statuses = {
            "done", "executed", "completed", "cancelled", "canceled",
            "failed", "error", "closed", "expired", "removed",
        }

        for trade in self.copy_manager.scheduled_trades:
            status_raw = str(trade.get("status", "Waiting") or "Waiting")
            if (not show_history) and status_raw.strip().lower() in history_statuses:
                continue

            # Robust type handling
            raw_type = trade.get("type", mt5.ORDER_TYPE_BUY)
            if isinstance(raw_type, str):
                t_type = raw_type.upper()
            else:
                t_type = "BUY" if raw_type == mt5.ORDER_TYPE_BUY else "SELL"

            # Single-line Time: "YYYY-MM-DD · HH:MM:SS" (no wrap)
            t_time = str(trade.get("time", "00:00:00") or "00:00:00").strip()
            t_date = str(trade.get("date", "") or "").strip()
            if t_date and t_time:
                display_time = f"{t_date} · {t_time}"
            else:
                display_time = t_date or t_time
            next_action = "-"
            if hasattr(self.copy_manager, "_get_trade_next_action"):
                try:
                    next_action = self.copy_manager._get_trade_next_action(trade)
                except Exception:
                    next_action = "-"

            self.tree_scheduled.insert("", "end", values=(
                trade.get("symbol", "N/A"),
                t_type,
                trade.get("lot", 0.01),
                display_time,
                status_raw,
                next_action,
            ))


    def on_pos_profile_change(self, choice):
        # Sync with main profile combo
        self.combo_profiles.set(choice)
        self.on_profile_change(choice)
        self.log(f"Profile switched to {choice} (from Pos Size tab)")


    def ensure_mt5_connection(self):
        if mt5.terminal_info():
            return True
        
        # Try to find path from selected profile
        path = ""
        try:
            profile_name = self.combo_profiles.get()
            if profile_name and profile_name in self.profiles:
                path = self.profiles[profile_name].get("path", "")
        except:
            pass
            
        if path and os.path.exists(path):
            return mt5.initialize(path)
        else:
            return mt5.initialize()


    def send_order(self, order_type):
        self.lbl_pos_msg.configure(text="", text_color="yellow")
        if not self.ensure_mt5_connection():
             self.lbl_pos_msg.configure(text=T("pos_msg_err_sym"), text_color="red")
             return

        try:
            symbol = self.ent_pos_sym.get().strip().upper()
            try:
                vol = float(self.val_pos_lot.get())
            except:
                self.lbl_pos_msg.configure(text=T("err_invalid_lot"), text_color="red")
                return

            try:
                sl_points = int(self.ent_pos_sl.get())
                tp_points = int(self.ent_pos_tp.get())
            except:
                 self.lbl_pos_msg.configure(text=T("err_invalid_sltp"), text_color="red")
                 return
            
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                mt5.symbol_select(symbol, True)
                tick = mt5.symbol_info_tick(symbol)
                
            if not tick:
                self.lbl_pos_msg.configure(text=T("pos_msg_err_sym"), text_color="red")
                return
            
            price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
            point = mt5.symbol_info(symbol).point
            
            sl_price = 0.0
            tp_price = 0.0
            
            if order_type == mt5.ORDER_TYPE_BUY:
                if sl_points > 0: sl_price = price - sl_points * point
                if tp_points > 0: tp_price = price + tp_points * point
            else:
                if sl_points > 0: sl_price = price + sl_points * point
                if tp_points > 0: tp_price = price - tp_points * point
                
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": vol,
                "type": order_type,
                "price": price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": 20,
                "magic": 0, # Manual
                "comment": "OAK_POS_SIZE",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": get_filling_type(symbol),
            }
            
            # --- AUTO CLOSE OPPOSITE POSITIONS & PENDING ---
            opp_type = mt5.POSITION_TYPE_SELL if order_type == mt5.ORDER_TYPE_BUY else mt5.POSITION_TYPE_BUY
            positions_c = mt5.positions_get(symbol=symbol)
            if positions_c:
                for pos in positions_c:
                    if pos.type == opp_type:
                        tick_c = mt5.symbol_info_tick(pos.symbol)
                        if tick_c:
                            price_c = tick_c.bid if pos.type == mt5.POSITION_TYPE_BUY else tick_c.ask
                            req_c = {
                                "action": mt5.TRADE_ACTION_DEAL,
                                "symbol": pos.symbol,
                                "volume": pos.volume,
                                "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                                "position": pos.ticket,
                                "price": price_c,
                                "deviation": 20,
                                "magic": pos.magic,
                                "comment": "OAK_AUTO_CLOSE_OPPOSITE",
                                "type_time": mt5.ORDER_TIME_GTC,
                                "type_filling": get_filling_type(pos.symbol),
                            }
                            mt5.order_send(req_c)
                            profile_name = self.config.get("profile_name", "Unknown")
                            self.notify(f"🔄 [{profile_name}] Manual Entry: Auto Closed opposite {symbol} (Ticket: {pos.ticket})")
            
            # Close any PENDING ORDERS of the SAME symbol but OPPOSITE direction
            if order_type == mt5.ORDER_TYPE_BUY:
                opp_pending_types = [mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP, mt5.ORDER_TYPE_SELL_STOP_LIMIT]
            else:
                opp_pending_types = [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_BUY_STOP_LIMIT]
                
            pending_orders = mt5.orders_get(symbol=symbol)
            if pending_orders:
                for o in pending_orders:
                    if o.type in opp_pending_types:
                        request_del = {
                            "action": mt5.TRADE_ACTION_REMOVE,
                            "order": o.ticket
                        }
                        mt5.order_send(request_del)
                        profile_name = self.config.get("profile_name", "Unknown")
                        self.notify(f"🗑️ [{profile_name}] Manual Entry: Auto Removed opposite pending {symbol} (Ticket: {o.ticket})")

            res = mt5.order_send(req)
            if res.retcode == mt5.TRADE_RETCODE_DONE:
                 self.lbl_pos_msg.configure(text=f"{T('pos_msg_sent')} #{res.order}", text_color="green")
                 winsound.Beep(1000, 200)
            else:
                 self.lbl_pos_msg.configure(text=f"{T('log_fail')} {res.retcode}", text_color="red")
                 winsound.Beep(500, 500)
                 
        except Exception as e:
            self.lbl_pos_msg.configure(text=f"{T('msg_error')}: {e}", text_color="red")

    # --- SCHEDULED ORDER HELPERS ---
