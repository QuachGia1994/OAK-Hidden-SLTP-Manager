# -*- coding: utf-8 -*-
"""Dashboard frame, news, status cards, theme, language, docs."""
from __future__ import annotations

class DashboardControllerMixin:
    """Dashboard frame, news, status cards, theme, language, docs."""

    def _project_root(self) -> str:
        """Repo/app root (parent of controllers/), never controllers/ itself."""
        try:
            svc = getattr(self, "services", None)
            if svc is not None and getattr(svc, "project_root", None) is not None:
                return str(svc.project_root)
        except Exception:
            pass
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def create_dashboard_frame(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["dashboard"] = frame
        frame.pack(fill="both", expand=True)
        frame.grid_columnconfigure(0, weight=3)
        frame.grid_columnconfigure(1, weight=7)
        frame.grid_rowconfigure(0, weight=1)

        left_panel = ctk.CTkFrame(frame, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        right_panel = ctk.CTkFrame(frame, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        # pack stack: cards (fixed) + news (fixed) + console (expand) — more reliable than nested grid after lang rebuild
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(0, weight=1)

        # === INFO CARDS ===
        cards_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        cards_frame.pack(fill="x", pady=(0, 8))
        cards_frame.grid_columnconfigure(0, weight=1)
        cards_frame.grid_columnconfigure(1, weight=1)
        cards_frame.grid_columnconfigure(2, weight=1)

        # Account Card (Balance/Equity hidden for privacy)
        self.card_account = ctk.CTkFrame(cards_frame, corner_radius=8)
        self.card_account.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.lbl_card_account_title = ctk.CTkLabel(self.card_account, text=T("ui_card_account"), font=ctk.CTkFont(size=14, weight="bold"), anchor="w")
        self.lbl_card_account_title.pack(fill="x", padx=8, pady=(6, 2))
        self.add_ui_element("ui_card_account", self.lbl_card_account_title)
        self.card_account_server = ctk.CTkLabel(self.card_account, text="—", font=ctk.CTkFont(size=12), anchor="w", text_color="gray")
        self.card_account_server.pack(fill="x", padx=8)
        self.card_account_status = ctk.CTkLabel(self.card_account, text=T("ui_status_dash"), font=ctk.CTkFont(size=13), anchor="w")
        self.card_account_status.pack(fill="x", padx=8, pady=(0, 6))

        # Signal Card — current slot + pair list (same pairs as dashboard cards)
        self.card_signal = ctk.CTkFrame(cards_frame, corner_radius=8)
        self.card_signal.grid(row=0, column=1, sticky="nsew", padx=4)
        self.lbl_card_signal_title = ctk.CTkLabel(self.card_signal, text=T("ui_card_signal"), font=ctk.CTkFont(size=14, weight="bold"), anchor="w")
        self.lbl_card_signal_title.pack(fill="x", padx=8, pady=(6, 2))
        self.add_ui_element("ui_card_signal", self.lbl_card_signal_title)
        self.card_signal_current = ctk.CTkLabel(self.card_signal, text=T("ui_current_dash"), font=ctk.CTkFont(size=13), anchor="w")
        self.card_signal_current.pack(fill="x", padx=8)
        self.card_signal_next = ctk.CTkLabel(self.card_signal, text=f"{T('ui_next')}: —", font=ctk.CTkFont(size=13), anchor="w")
        self.card_signal_next.pack(fill="x", padx=8)
        self.card_signal_countdown = ctk.CTkLabel(self.card_signal, text=f"{T('ui_countdown')}: —", font=ctk.CTkFont(size=12), anchor="w", text_color="gray")
        self.card_signal_countdown.pack(fill="x", padx=8, pady=(2, 4))
        self.card_signal_pairs_frame = ctk.CTkFrame(self.card_signal, fg_color="transparent")
        self.card_signal_pairs_frame.pack(fill="x", padx=6, pady=(0, 6))
        self.card_signal_pair_labels = {}
        for pair in ("XAUUSD",):
            row = ctk.CTkFrame(self.card_signal_pairs_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=pair, font=ctk.CTkFont(size=12, family="Consolas"), anchor="w").pack(side="left")
            val = ctk.CTkLabel(row, text="—", font=ctk.CTkFont(size=12, weight="bold"), anchor="e")
            val.pack(side="right")
            self.card_signal_pair_labels[pair] = val

        # Engine Card
        self.card_engine = ctk.CTkFrame(cards_frame, corner_radius=8)
        self.card_engine.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        self.lbl_card_engine_title = ctk.CTkLabel(self.card_engine, text=T("ui_card_engine"), font=ctk.CTkFont(size=14, weight="bold"), anchor="w")
        self.lbl_card_engine_title.pack(fill="x", padx=8, pady=(6, 2))
        self.add_ui_element("ui_card_engine", self.lbl_card_engine_title)
        self.card_engine_ghost = ctk.CTkLabel(self.card_engine, text=f"{T('ui_ghost')}: —", font=ctk.CTkFont(size=13), anchor="w")
        self.card_engine_ghost.pack(fill="x", padx=8)
        self.card_engine_session = ctk.CTkLabel(self.card_engine, text=T("ui_session_on"), font=ctk.CTkFont(size=13), anchor="w", text_color="#2ecc71")
        self.card_engine_session.pack(fill="x", padx=8)
        self.card_engine_version = ctk.CTkLabel(self.card_engine, text=f"v{VERSION[1:]} {T('ui_stable')}", font=ctk.CTkFont(size=12), anchor="w", text_color="gray")
        self.card_engine_version.pack(fill="x", padx=8, pady=(0, 6))

        self.lbl_select = ctk.CTkLabel(left_panel, text=T("msg_select_profile"), font=ctk.CTkFont(size=14))
        self.lbl_select.pack(pady=(0, 5), anchor="w")
        self.add_ui_element("msg_select_profile", self.lbl_select)

        self.combo_profiles = ctk.CTkOptionMenu(left_panel, values=list(self.profiles.keys()) if self.profiles else ["Empty"], command=self.on_profile_change)
        self.combo_profiles.pack(pady=(0, 8), anchor="w")

        # Explicit Selected vs Running vs Account source (safety)
        self.lbl_profile_selected = ctk.CTkLabel(
            left_panel, text=f"{T('ui_selected')}: —", font=ctk.CTkFont(size=12), anchor="w", text_color="#ffb74d"
        )
        self.lbl_profile_selected.pack(fill="x", pady=(0, 2))
        self.lbl_profile_running = ctk.CTkLabel(
            left_panel, text=f"{T('ui_running_monitor')}: —", font=ctk.CTkFont(size=12), anchor="w", text_color="#66bb6a"
        )
        self.lbl_profile_running.pack(fill="x", pady=(0, 2))
        self.lbl_account_source = ctk.CTkLabel(
            left_panel, text=f"{T('ui_account_source')}: —", font=ctk.CTkFont(size=11), anchor="w", text_color="gray"
        )
        self.lbl_account_source.pack(fill="x", pady=(0, 12))

        self.btn_start = ctk.CTkButton(left_panel, text=T("btn_start"), fg_color="green", height=40, command=self.start_monitor)
        self.btn_start.pack(pady=(0, 10), fill="x")
        self.add_ui_element("btn_start", self.btn_start)

        self.btn_stop = ctk.CTkButton(left_panel, text=T("btn_stop"), fg_color="red", height=40, state="disabled", command=self.stop_monitor)
        self.btn_stop.pack(pady=(0, 8), fill="x")
        self.add_ui_element("btn_stop", self.btn_stop)

        # Multi-monitor list (each row: name + PID + Stop)
        # Taller so 3+ rows stay visible without empty scroll trap
        self.running_monitors_frame = ctk.CTkScrollableFrame(
            left_panel, height=150, label_text=""
        )
        self.running_monitors_frame.pack(fill="x", pady=(0, 12))
        self._running_row_widgets = {}
        self._running_panel_sig = None
        self._stop_dialog_open = False
        self._stop_highlight_profile = None
        try:
            self.refresh_running_monitors_panel(force=True)
        except Exception:
            pass

        self.btn_ghost_toggle = ctk.CTkButton(
            left_panel,
            text=T("ui_btn_ghost_short"),
            height=40,
            corner_radius=10,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._open_ghost_popup,
        )
        self.btn_ghost_toggle.pack(pady=(0, 20), fill="x")
        self.update_ghost_button_ui()

        self.engine_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        self.engine_frame.pack(pady=(10, 0), fill="x")

        self.lbl_engine_title_frame = ctk.CTkFrame(self.engine_frame, fg_color="transparent")
        self.lbl_engine_title_frame.pack()

        self.lbl_engine_title = ctk.CTkLabel(self.lbl_engine_title_frame, text=T("lbl_engine"), font=ctk.CTkFont(size=10))
        self.lbl_engine_title.grid(row=0, column=0)
        self.add_ui_element("lbl_engine", self.lbl_engine_title)
        add_help_icon(self.lbl_engine_title_frame, 0, 1, "tip_engine")

        self.lbl_engine_badge = ctk.CTkLabel(self.engine_frame, text="", font=ctk.CTkFont(size=12, weight="bold"), corner_radius=6)
        self.lbl_engine_badge.pack(pady=2, fill="x")

        self.recovery_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        self.recovery_frame.pack(pady=(10, 0), fill="x")

        self.lbl_recovery_status_frame = ctk.CTkFrame(self.recovery_frame, fg_color="transparent")
        self.lbl_recovery_status_frame.pack()

        self.lbl_recovery_status = ctk.CTkLabel(self.lbl_recovery_status_frame, text="🛡️ Session Auto-Save: ON", font=ctk.CTkFont(size=12, weight="bold", slant="italic"), text_color="#2ecc71")
        self.lbl_recovery_status.grid(row=0, column=0)
        add_help_icon(self.lbl_recovery_status_frame, 0, 1, "tip_session")

        self.update_ghost_button_ui()

        # News (fixed height) + Console (fills remaining) — pack, never grid-collapse
        try:
            news_section = ctk.CTkFrame(right_panel, fg_color="transparent", height=200)
            news_section.pack(fill="x", pady=(0, 6))
            news_section.pack_propagate(False)

            news_header = ctk.CTkFrame(news_section, fg_color="transparent")
            news_header.pack(fill="x", pady=(0, 4))
            self.lbl_news_title = ctk.CTkLabel(news_header, text=T("news_title"), font=ctk.CTkFont(size=13, weight="bold"))
            self.lbl_news_title.pack(side="left")
            self.add_ui_element("news_title", self.lbl_news_title)

            self.news_box = ctk.CTkTextbox(news_section, wrap="word", height=160)
            self.news_box.pack(fill="both", expand=True)
            self.news_box.configure(state="disabled")
        except Exception as e:
            print(f"Dashboard news section failed: {e}")

        try:
            console_section = ctk.CTkFrame(right_panel, fg_color="transparent")
            console_section.pack(fill="both", expand=True, pady=(4, 0))

            self.lbl_console = ctk.CTkLabel(console_section, text=T("console_title"), font=ctk.CTkFont(weight="bold"))
            self.lbl_console.pack(anchor="w")
            self.add_ui_element("console_title", self.lbl_console)

            filter_frame = ctk.CTkFrame(console_section, fg_color="transparent")
            filter_frame.pack(fill="x", pady=(0, 3))
            self._console_filters = {}
            for label, color in [("INFO", "#b0bec5"), ("WARN", "#ffb74d"), ("ERROR", "#ef5350"), ("MT5", "#29b6f6"), ("TG", "#ab47bc"), ("SIG", "#66bb6a")]:
                var = ctk.BooleanVar(value=True)
                cb = ctk.CTkCheckBox(filter_frame, text=label, variable=var, font=ctk.CTkFont(size=10), text_color=color)
                cb.pack(side="left", padx=4)
                self._console_filters[label] = var

            self.console = ctk.CTkTextbox(console_section, wrap="word")
            self.console.pack(fill="both", expand=True)
            self.console.configure(state="disabled")
        except Exception as e:
            print(f"Dashboard console section failed: {e}")

        # News load is deferred on first paint (see _deferred_startup); force only if already shown
        if getattr(self, "_startup_news_ready", False):
            try:
                self.update_news_summary(force=True)
            except Exception as e:
                print(f"Dashboard news load failed: {e}")


    def update_news_summary(self, force=False):
        if getattr(self, "_ui_rebuilding", False):
            return
        if not self._widget_alive(getattr(self, "news_box", None)):
            return

        # Check if already running
        if hasattr(self, "_news_thread") and self._news_thread is not None and self._news_thread.is_alive():
            return

        now = datetime.now()
        if not force and hasattr(self, "_last_news_fetch"):
            if (now - self._last_news_fetch).total_seconds() < 300:
                return
        self._last_news_fetch = now
        
        # Cache only if same day AND format version matches (timezone fix)
        try:
            from oak_trading_reminders import _NEWS_CACHE_VERSION, _get_news_day_str
            cache_file = f"news_cache_{CURRENT_LANG}.json"
            today_str = _get_news_day_str()
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                if (
                    cache.get("date") == today_str
                    and cache.get("v") == _NEWS_CACHE_VERSION
                    and cache.get("news")
                ):
                    self._display_news_result(cache["news"])
                    # Still re-push dashboard so web stays in sync with app
                    threading.Thread(
                        target=self._push_news_to_dashboard,
                        args=(cache["news"],),
                        daemon=True,
                    ).start()
                    return
        except Exception:
            pass
        
        self.news_box.configure(state="normal")
        self.news_box.delete("1.0", "end")
        self.news_box.insert("1.0", T("news_loading"))
        self.news_box.configure(state="disabled")
        
        self._news_thread = threading.Thread(target=self._fetch_news_worker, daemon=True)
        self._news_thread.start()


    def _fetch_news_worker(self):
        token = getattr(self, "_news_gen", 0)
        try:
            news = oak_trading_reminders.get_economic_news(lang=CURRENT_LANG)
        except Exception:
            news = []
        def _done(n=news, t=token):
            if t != getattr(self, "_news_gen", 0):
                return
            self._display_news_result(n, token=t)
        try:
            self.after(0, _done)
        except Exception:
            pass
        try:
            self._push_news_to_dashboard(news)
        except Exception:
            pass


    def _push_news_to_dashboard(self, news_lines):
        """Push the same news list the app shows so Dashboard never drifts."""
        try:
            cfg_path = os.path.join(self._project_root(), "config.json")
            url = ""
            api_key = ""
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                url = (cfg.get("dashboard_url") or "").rstrip("/")
                api_key = cfg.get("dashboard_api_key") or ""
            if not url or not news_lines:
                return
            from mt5_signal_bot import _parse_news_for_dashboard
            parsed = _parse_news_for_dashboard(news_lines)
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["X-API-Key"] = api_key
            payload = json.dumps(parsed).encode("utf-8")
            req = urllib.request.Request(
                f"{url}/api/news", data=payload, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
            log.info("Dashboard news synced (%d items)", len(parsed))
        except Exception as e:
            log.warning("Dashboard news push failed: %s", e)


    def _display_news_result(self, news, token=None):
        if getattr(self, "_ui_rebuilding", False):
            return
        box = getattr(self, "news_box", None)
        if box is None:
            return
        try:
            if not box.winfo_exists():
                return
        except Exception:
            return
        try:
            box.configure(state="normal")
            box.delete("1.0", "end")
            if news:
                # Critical (Federal Funds Rate etc.) first + banner
                critical = [n for n in news if "NỔI BẬT" in n or "Federal Funds Rate" in n]
                normal = [n for n in news if n not in critical]
                ordered = critical + normal
                if critical:
                    banner = (
                        "╔══════════════════════════════════════╗\n"
                        "║  ⚠  TIN NỔI BẬT HÔM NAY (HIGH IMPACT) ║\n"
                        "╚══════════════════════════════════════╝\n"
                    )
                    box.insert("1.0", banner + "\n".join(ordered))
                else:
                    box.insert("1.0", "\n".join(ordered))
                self.apply_markdown(box)
                self._maybe_alert_critical_news(critical)
            else:
                box.insert("1.0", T("news_empty"))
            box.configure(state="disabled")
        except Exception:
            pass


    def _maybe_alert_critical_news(self, critical_lines):
        """Notify once/day when Federal Funds Rate (etc.) is on the calendar."""
        if not critical_lines:
            return
        today = datetime.now().strftime("%Y-%m-%d")
        lock_key = f"critical_news_alert_{today}"
        if getattr(self, "_critical_news_alerted", None) == today:
            return
        # Persist across GUI restarts (simple lock file)
        lock_path = os.path.join("sent_locks", f"{lock_key}.lock")
        try:
            os.makedirs("sent_locks", exist_ok=True)
            if os.path.exists(lock_path):
                self._critical_news_alerted = today
                return
            with open(lock_path, "w", encoding="utf-8") as f:
                f.write("\n".join(critical_lines))
        except Exception:
            pass
        self._critical_news_alerted = today
        body = "\n".join(critical_lines[:6])
        msg = (
            f"🚨 <c=#ef5350>TIN NỔI BẬT HÔM NAY</c>\n"
            f"Phát hiện tin quan trọng (Federal Funds Rate / FOMC / NFP…):\n\n{body}"
        )
        try:
            self.log(msg)
        except Exception:
            pass
        try:
            # Telegram via running worker monitor if available
            if hasattr(self, "notify"):
                self.notify(re.sub(r"<c=#[A-Fa-f0-9]{6}>|</c>", "", msg))
        except Exception:
            pass


    def apply_theme_overrides(self):
        if not hasattr(self, "theme_palette"):
            return
        p = self.theme_palette
        if hasattr(self, "list_frame"):
            try:
                self.list_frame.configure(fg_color=p["panel_bg"], label_text_color=p["text_primary"])
            except:
                self.list_frame.configure(fg_color=p["panel_bg"])
        if hasattr(self, "form_scroll"):
            try:
                self.form_scroll.configure(fg_color=p["panel_bg"], label_text_color=p["text_primary"])
            except:
                self.form_scroll.configure(fg_color=p["panel_bg"])
        if hasattr(self, "res_box"):
            self.res_box.configure(fg_color=p["res_box_bg"])
        if hasattr(self, "lbl_pos_res"):
            self.lbl_pos_res.configure(text_color=p["accent"])
        if hasattr(self, "val_pos_lot"):
            self.val_pos_lot.configure(text_color=p["text_primary"], fg_color=p["res_box_bg"])
        if hasattr(self, "sched_input_frame"):
            self.sched_input_frame.configure(fg_color=p["schedule_bg"])
        if hasattr(self, "lbl_pos_time"):
            self.lbl_pos_time.configure(text_color=p["text_primary"])
        if hasattr(self, "ent_pos_time"):
            self.ent_pos_time.configure(text_color=p["text_primary"], fg_color=p["input_bg"], border_color=p["input_border"])
        if hasattr(self, "seg_pos_type"):
            self.seg_pos_type.configure(text_color=p["text_primary"], fg_color=p["panel_alt_bg"], selected_color=p["accent"], selected_hover_color=p["accent"])
        if hasattr(self, "lbl_schedule_title"):
            self.lbl_schedule_title.configure(text_color=p["text_muted"])
        if hasattr(self, "sep_left_line"):
            self.sep_left_line.configure(fg_color=p["card_border"])
        if hasattr(self, "sep_right_line"):
            self.sep_right_line.configure(fg_color=p["card_border"])
        if hasattr(self, "news_box"):
            self.news_box.configure(text_color=p["text_primary"], fg_color=p["panel_alt_bg"])
        if hasattr(self, "lbl_news_title"):
            self.lbl_news_title.configure(text_color=p["text_primary"])

    def apply_theme(self, theme_key):
        """Premium Trading Terminal palettes — Soft Premium / Minimal Dark / Deep Sea."""
        self.theme_key = theme_key
        if theme_key == "light":
            ctk.set_appearance_mode("Light")
            ctk.set_default_color_theme("blue")
            self.theme_palette = {
                "text_primary": "#0f172a",
                "text_muted": "#64748b",
                "panel_bg": "#f8fafc",
                "panel_alt_bg": "#f1f5f9",
                "card_bg": "#ffffff",
                "card_border": "#e2e8f0",
                "input_bg": "#ffffff",
                "input_border": "#cbd5e1",
                "input_text": "#0f172a",
                "signal_card_bg": "#ffffff",
                "signal_title": "#64748b",
                "signal_value": "#0f172a",
                "res_box_bg": "#f1f5f9",
                "accent": "#0ea5e9",
                "accent_hover": "#0284c7",
                "schedule_bg": "#f8fafc",
                "sidebar_bg": "#0f172a",
                "sidebar_text": "#e2e8f0",
                "success": "#059669",
                "danger": "#dc2626",
            }
        elif theme_key == "deepsea":
            ctk.set_appearance_mode("Dark")
            ctk.set_default_color_theme("dark-blue")
            self.theme_palette = {
                "text_primary": "#e0f2fe",
                "text_muted": "#7dd3fc",
                "panel_bg": "#020617",
                "panel_alt_bg": "#0c1929",
                "card_bg": "#0f2744",
                "card_border": "#164e63",
                "input_bg": "#0c1929",
                "input_border": "#155e75",
                "input_text": "#e0f2fe",
                "signal_card_bg": "#0f2744",
                "signal_title": "#67e8f9",
                "signal_value": "#ecfeff",
                "res_box_bg": "#082f49",
                "accent": "#22d3ee",
                "accent_hover": "#06b6d4",
                "schedule_bg": "#0c1929",
                "sidebar_bg": "#020617",
                "sidebar_text": "#a5f3fc",
                "success": "#34d399",
                "danger": "#f87171",
            }
        else:
            ctk.set_appearance_mode("Dark")
            ctk.set_default_color_theme("blue")
            self.theme_palette = {
                "text_primary": "#fafafa",
                "text_muted": "#a1a1aa",
                "panel_bg": "#09090b",
                "panel_alt_bg": "#18181b",
                "card_bg": "#18181b",
                "card_border": "#27272a",
                "input_bg": "#18181b",
                "input_border": "#3f3f46",
                "input_text": "#fafafa",
                "signal_card_bg": "#18181b",
                "signal_title": "#a1a1aa",
                "signal_value": "#fafafa",
                "res_box_bg": "#09090b",
                "accent": "#3b82f6",
                "accent_hover": "#2563eb",
                "schedule_bg": "#18181b",
                "sidebar_bg": "#09090b",
                "sidebar_text": "#e4e4e7",
                "success": "#22c55e",
                "danger": "#ef4444",
            }


    def refresh_theme_labels(self):
        if not hasattr(self, "combo_theme"):
            return
        values = [T("theme_dark"), T("theme_light"), T("theme_deepsea")]
        self.combo_theme.configure(values=values)
        theme_key = self.settings.get("theme", "dark")
        if theme_key == "light":
            self.combo_theme.set(T("theme_light"))
        elif theme_key == "deepsea":
            self.combo_theme.set(T("theme_deepsea"))
        else:
            self.combo_theme.set(T("theme_dark"))


    def change_theme(self, value):
        if value == T("theme_light"):
            theme_key = "light"
        elif value == T("theme_deepsea"):
            theme_key = "deepsea"
        else:
            theme_key = "dark"
        self.settings["theme"] = theme_key
        save_json(SETTINGS_FILE, self.settings)
        self.apply_theme(theme_key)
        self.refresh_theme_labels()
        self.apply_theme_overrides()
        try:
            self._apply_scheduled_tree_style()
        except Exception:
            pass
        self.refresh_profile_list()
        self.update_news_summary(force=True)
        # Rebuild About theme cards so selection border matches
        try:
            if hasattr(self, "tab_about") and self.tab_about.winfo_exists():
                for child in list(self.tab_about.winfo_children()):
                    child.destroy()
                self.create_about_frame(self.tab_about)
        except Exception:
            pass


    def periodic_ui_refresh(self):
        """Reload scheduled trades from JSON file if it has changed (Multi-process sync)"""
        try:
            if getattr(self, "_ui_rebuilding", False):
                return
            if hasattr(self, 'copy_manager') and hasattr(self.copy_manager, 'scheduled_file') and self.copy_manager.scheduled_file:
                file_path = self.copy_manager.scheduled_file
                if os.path.exists(file_path):
                    mtime = os.path.getmtime(file_path)
                    if not hasattr(self, '_last_json_mtime'): self._last_json_mtime = 0

                    if mtime > self._last_json_mtime:
                        self._last_json_mtime = mtime
                        # Reload
                        trades = load_json(file_path)
                        if isinstance(trades, list):
                            self.copy_manager.scheduled_trades = trades
                            # Update UI
                            self.update_scheduled_list_ui()
            self.update_news_summary()
            self._update_dashboard_cards()
        except Exception as e:
            print(f"Refresh Error: {e}")
        finally:
            self.after(2000, self.periodic_ui_refresh) # Check every 2s


    def _widget_alive(self, w):
        if w is None:
            return False
        try:
            return bool(w.winfo_exists())
        except Exception:
            return False


    def _update_dashboard_cards(self):
        """Update Account/Signal/Engine cards from worker heartbeat (SQLite)."""
        if getattr(self, "_ui_rebuilding", False):
            return
        try:
            # Selected profile (pure state preferred) vs running monitors
            profile = getattr(self, "selected_profile_name", None) or ""
            if not profile:
                combo = getattr(self, "combo_profiles", None)
                if self._widget_alive(combo):
                    try:
                        profile = combo.get() or ""
                    except Exception:
                        profile = ""
            # Multi: prefer selected if live, else primary live, else selected
            try:
                live = self._get_live_running_profiles()
            except Exception:
                live = []
            running = getattr(self, "running_profile_name", None) or ""
            if profile and profile in live:
                hb_profile = profile
            elif live:
                hb_profile = live[0]
            else:
                hb_profile = running if running else profile
            hb = self._store.get_heartbeat(hb_profile) if hasattr(self, "_store") and hb_profile else None
            mt5_state = (
                self._store.compute_mt5_state(hb_profile)
                if hasattr(self, "_store") and hb_profile
                else {"state": "Disconnected", "last_error": ""}
            )
            tg_state = (
                self._store.compute_telegram_state(hb_profile)
                if hasattr(self, "_store") and hb_profile
                else {"configured": False, "api_ok": False}
            )

            # Left-rail Selected / Running / Account source
            try:
                if self._widget_alive(getattr(self, "lbl_profile_selected", None)):
                    self.lbl_profile_selected.configure(text=f"{T('ui_selected')}: {profile or '—'}")
                if self._widget_alive(getattr(self, "lbl_profile_running", None)):
                    self.lbl_profile_running.configure(text=f"{T('ui_running_monitor')}: {running or '—'}")
                if self._widget_alive(getattr(self, "lbl_account_source", None)):
                    if hb and (hb.get("server") or hb.get("login")):
                        src = f"{hb_profile or '—'} / {hb.get('login') or '—'}"
                    else:
                        src = f"{hb_profile or '—'} / —"
                    self.lbl_account_source.configure(text=f"{T('ui_account_source')}: {src}")
            except Exception:
                pass

            # Keep Start/Stop caption in sync every tick
            try:
                self.update_ui_state(profile or running or "")
            except Exception:
                pass

            # Account Card - server/status only (Balance/Equity intentionally hidden)
            # Prefix MUST use hb_profile (source of heartbeat), never a different "running" label
            card_server = getattr(self, "card_account_server", None)
            card_status = getattr(self, "card_account_status", None)
            if self._widget_alive(card_server):
                if hb and hb.get("server"):
                    server_text = f"{hb['server']} | #{hb.get('login', '')}"
                    if hb_profile:
                        server_text = f"[{hb_profile}] {server_text}"
                    if mt5_state["state"] != "Connected" and mt5_state.get("age") is not None:
                        server_text += f" ({int(mt5_state['age'])}s stale)"
                    card_server.configure(text=server_text)
                    if self._widget_alive(card_status):
                        state = mt5_state.get("state") or "—"
                        state_lbl = {
                            "Connected": T("ui_connected"),
                            "Degraded": T("ui_degraded"),
                            "Disconnected": T("ui_disconnected"),
                        }.get(state, state)
                        card_status.configure(
                            text=f"{T('ui_status')}: {state_lbl}",
                            text_color="#66bb6a" if state == "Connected" else "#ffb74d" if state == "Degraded" else "#ef5350",
                        )
                else:
                    card_server.configure(text=T("ui_waiting_worker"))
                    if self._widget_alive(card_status):
                        card_status.configure(text=T("ui_status_dash"), text_color="gray")

            # Signal Card — XAUUSD only.
            card_sig = getattr(self, "card_signal_current", None)
            if self._widget_alive(card_sig):
                pair_dirs = {}
                latest = None
                now = datetime.now()
                is_weekend = now.weekday() >= 5
                try:
                    # Project root (not controllers/) — signals_log lives next to OAK_*.py
                    if is_weekend:
                        card_sig.configure(text=f"{T('ui_current')}: {T('sig_no_trade')}")
                    signals_file = os.path.join(self._project_root(), "signals_log.json")
                    if not is_weekend and not os.path.exists(signals_file):
                        # Fallback: cwd (Documents run path)
                        signals_file = os.path.join(os.getcwd(), "signals_log.json")
                    if not is_weekend and os.path.exists(signals_file):
                        with open(signals_file, "r", encoding="utf-8") as f:
                            signals = json.load(f)
                        if signals:
                            try:
                                from utils import get_latest_display_signal as _glds
                                latest = _glds(signals) or signals[-1]
                            except Exception:
                                try:
                                    latest = get_latest_display_signal(signals) or signals[-1]
                                except Exception:
                                    latest = signals[-1] if isinstance(signals, list) else None
                            if latest:
                                sig = latest.get("signal", "—")
                                icon = "🟢" if sig == "BUY" else "🔴" if sig == "SELL" else "⚪"
                                hour = latest.get("hour")
                                hour_txt = f" H={int(hour):02d}:45" if hour is not None else ""
                                card_sig.configure(text=f"{T('ui_current')}: {icon} {sig}{hour_txt}")
                                pair_dirs = latest.get("pair_dirs") or {}
                            else:
                                card_sig.configure(text=T("ui_current_dash"))
                        else:
                            card_sig.configure(text=T("ui_current_dash"))
                    elif not is_weekend:
                        card_sig.configure(text=T("ui_current_dash"))
                except Exception as _sig_err:
                    try:
                        card_sig.configure(text=T("ui_current_dash"))
                    except Exception:
                        pass
                    try:
                        print(f"Signal card update error: {_sig_err}")
                    except Exception:
                        pass
                    pair_dirs = {}
                    latest = None

                pair_labels = getattr(self, "card_signal_pair_labels", None) or {}
                if pair_labels:
                    p = getattr(self, "theme_palette", {}) or {}
                    muted = p.get("text_muted", "gray")
                    for pair, lbl in pair_labels.items():
                        if not self._widget_alive(lbl):
                            continue
                        if is_weekend:
                            lbl.configure(text="—", text_color=muted)
                            continue
                        if pair == "XAUUSD":
                            d = pair_dirs.get(pair)
                            if d == "BUY":
                                lbl.configure(text=T("sig_buy"), text_color=p.get("success", "#2ecc71"))
                            elif d == "SELL":
                                lbl.configure(text=T("sig_sell"), text_color=p.get("danger", "#e74c3c"))
                            else:
                                lbl.configure(text="—", text_color=muted)
                            continue
                        lbl.configure(text="—", text_color=muted)

                # Next slot countdown (T2-T6=H2-5,7-9,12-15; broker weekday)
                try:
                    from mt5_signal_bot import get_target_hours as _gth
                    target_hours = _gth(weekday=now.weekday())
                except Exception:
                    target_hours = [] if is_weekend else [2, 3, 4, 5, 7, 8, 9, 12, 13, 14, 15]
                if not target_hours:
                    self.card_signal_next.configure(text=f"{T('ui_next')}: —")
                    self.card_signal_countdown.configure(text=f"{T('ui_countdown')}: —")
                else:
                    next_h = None
                    for h in target_hours:
                        if now.hour < h or (now.hour == h and now.minute < 45):
                            next_h = h
                            break
                    if next_h is None:
                        next_h = target_hours[0]
                    self.card_signal_next.configure(text=f"{T('ui_next')}: {next_h:02d}:45")
                    target = now.replace(hour=next_h, minute=45, second=0, microsecond=0)
                    if target < now:
                        from datetime import timedelta
                        target += timedelta(days=1)
                    diff = target - now
                    hrs, rem = divmod(int(diff.total_seconds()), 3600)
                    mins, secs = divmod(rem, 60)
                    self.card_signal_countdown.configure(text=f"{T('ui_countdown')}: {hrs:02d}:{mins:02d}:{secs:02d}")

            # Engine Card
            if hasattr(self, 'card_engine_ghost'):
                is_running = any(
                    data.get("proc") and data["proc"].poll() is None
                    for data in self.workers.values()
                ) if hasattr(self, 'workers') else False
                ghost_active = self.settings.get("ghost_mode_active", False) if hasattr(self, 'settings') else False
                dot = "🟢" if is_running else "⚫"
                gh = T("ui_ghost_active") if ghost_active else T("ui_ghost_off")
                self.card_engine_ghost.configure(text=f"{T('ui_ghost')}: {dot} {gh}")

            # Status Bar - multi: N/M Connected when several monitors are live
            if hasattr(self, 'status_mt5'):
                state = mt5_state["state"]
                age = mt5_state.get("age")
                color = "#66bb6a" if state == "Connected" else "#ffb74d" if state == "Degraded" else "#ef5350"
                multi_label = None
                try:
                    if live and len(live) > 1 and hasattr(self, "_store") and self._store:
                        n_ok = 0
                        for pn in live:
                            st = self._store.compute_mt5_state(pn) or {}
                            if st.get("state") == "Connected":
                                n_ok += 1
                        multi_label = T("ui_n_of_m_connected").format(n=n_ok, m=len(live))
                        color = (
                            "#66bb6a" if n_ok == len(live)
                            else "#ffb74d" if n_ok > 0
                            else "#ef5350"
                        )
                except Exception:
                    multi_label = None
                if multi_label:
                    label = multi_label
                elif state == "Connected":
                    label = f"{T('ui_connected')} ({int(age)}s)" if age is not None else T("ui_connected")
                elif state == "Degraded":
                    if mt5_state.get("last_error"):
                        label = f"{T('ui_degraded')} ({mt5_state['last_error'][:30]})"
                    elif age is not None:
                        label = f"{T('ui_degraded')} ({int(age)}s {T('ui_stale')})"
                    else:
                        label = T("ui_degraded")
                else:
                    label = (
                        f"{T('ui_disconnected')} ({int(age)}s {T('ui_ago')})"
                        if age is not None
                        else T("ui_disconnected")
                    )
                self.status_mt5.configure(text=f"MT5 ● {label}", text_color=color)

                # Telegram: 3 states
                tg_configured = tg_state["configured"]
                tg_api = tg_state["api_ok"]
                if not tg_configured:
                    try:
                        import OAK_Hidden_SLTP_Manager as _oak
                        mimo_chat = getattr(_oak, "_mimo_bot_chat_id", "") or ""
                    except Exception:
                        mimo_chat = ""
                    profile_chat = ""
                    try:
                        pdata = (getattr(self, "profiles", {}) or {}).get(profile, {}) or {}
                        profile_chat = pdata.get("tele_chat", "") or ""
                    except Exception:
                        profile_chat = ""
                    if mimo_chat or profile_chat:
                        tg_label = T("ui_configured")
                        tg_color = "#ffb74d"
                    else:
                        tg_label = T("ui_not_configured")
                        tg_color = "gray"
                elif tg_api:
                    tg_label = f"Online (@{tg_state['bot_name']})" if tg_state["bot_name"] else "Online"
                    tg_color = "#66bb6a"
                else:
                    tg_error = tg_state.get("bot_name", "")
                    if tg_error.startswith("client_error:"):
                        code = tg_error.split(":", 1)[1]
                        friendly = f"Client error ({code})"
                    else:
                        friendly = {
                            "token_invalid": "Token invalid",
                            "chat_not_found": "Chat ID invalid",
                            "rate_limited": "Rate limited",
                            "bad_gateway": "API gateway error",
                            "service_unavailable": "Service unavailable",
                            "server_error": "Server error",
                            "client_error": "Client error",
                            "network_error": "Network error",
                        }.get(tg_error, tg_error.replace("_", " ").capitalize() if tg_error else "API unreachable")
                    tg_label = f"{T('ui_degraded')} ({friendly})"
                    tg_color = "#ffb74d"
                self.status_telegram.configure(text=f"Telegram ● {tg_label}", text_color=tg_color)
                is_running = any(
                    data.get("proc") and data["proc"].poll() is None
                    for data in self.workers.values()
                ) if hasattr(self, 'workers') else False
                gh_state = T("lbl_running") if is_running else T("lbl_stopped")
                self.status_ghost.configure(
                    text=f"{T('ui_ghost')} ● {gh_state}",
                    text_color="#66bb6a" if is_running else "gray",
                )
        except Exception:
            pass


    def create_diagnostics_frame(self, parent):
        """Create the Diagnostics/Logs tab."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["diagnostics"] = frame
        frame.pack(fill="both", expand=True)

        # Header
        self._diag_header = ctk.CTkLabel(frame, text=T("ui_diag_title"), font=ctk.CTkFont(size=16, weight="bold"))
        self._diag_header.pack(pady=(10, 5), anchor="w", padx=10)
        self.add_ui_element("ui_diag_title", self._diag_header)

        # Time scope: Current Session | Last 15 Minutes | All History
        scope_frame = ctk.CTkFrame(frame, fg_color="transparent")
        scope_frame.pack(fill="x", padx=10, pady=(0, 4))
        self._diag_scope_lbl = ctk.CTkLabel(scope_frame, text=T("ui_diag_scope"))
        self._diag_scope_lbl.pack(side="left")
        self.add_ui_element("ui_diag_scope", self._diag_scope_lbl)
        self._log_scope_var = ctk.StringVar(value="session")
        self._diag_scope_radios = []
        for value, key in (
            ("session", "ui_diag_scope_session"),
            ("15m", "ui_diag_scope_15m"),
            ("all", "ui_diag_scope_all"),
        ):
            rb = ctk.CTkRadioButton(
                scope_frame,
                text=T(key),
                variable=self._log_scope_var,
                value=value,
                command=self._filter_logs,
            )
            rb.pack(side="left", padx=5)
            self.add_ui_element(key, rb)
            self._diag_scope_radios.append(rb)

        # Log level filter
        filter_frame = ctk.CTkFrame(frame, fg_color="transparent")
        filter_frame.pack(fill="x", padx=10, pady=5)
        self._diag_level_lbl = ctk.CTkLabel(filter_frame, text=T("ui_diag_level"))
        self._diag_level_lbl.pack(side="left")
        self.add_ui_element("ui_diag_level", self._diag_level_lbl)
        self._log_level_var = ctk.StringVar(value="ALL")
        for level in ["ALL", "INFO", "WARNING", "ERROR"]:
            ctk.CTkRadioButton(filter_frame, text=level, variable=self._log_level_var, value=level,
                               command=self._filter_logs).pack(side="left", padx=5)

        # Auto Refresh + Follow toggle
        self._auto_refresh_var = ctk.BooleanVar(value=False)
        self._follow_var = ctk.BooleanVar(value=True)
        self._diag_auto_cb = ctk.CTkCheckBox(
            filter_frame, text=T("ui_diag_auto_refresh"), variable=self._auto_refresh_var,
            font=ctk.CTkFont(size=10), command=self._toggle_auto_refresh,
        )
        self._diag_auto_cb.pack(side="right", padx=5)
        self.add_ui_element("ui_diag_auto_refresh", self._diag_auto_cb)
        self._diag_follow_cb = ctk.CTkCheckBox(
            filter_frame, text=T("ui_diag_follow"), variable=self._follow_var,
            font=ctk.CTkFont(size=10),
        )
        self._diag_follow_cb.pack(side="right", padx=5)
        self.add_ui_element("ui_diag_follow", self._diag_follow_cb)

        # Log display
        self._log_text = ctk.CTkTextbox(frame, wrap="word", font=ctk.CTkFont(family="Consolas", size=11))
        self._log_text.pack(fill="both", expand=True, padx=10, pady=5)

        # Buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=5)
        self._diag_btn_refresh = ctk.CTkButton(btn_frame, text=T("ui_diag_refresh"), width=80, command=self._refresh_logs)
        self._diag_btn_refresh.pack(side="left", padx=3)
        self.add_ui_element("ui_diag_refresh", self._diag_btn_refresh)
        self._diag_btn_clear = ctk.CTkButton(btn_frame, text=T("ui_diag_clear"), width=100, command=self._clear_log_display)
        self._diag_btn_clear.pack(side="left", padx=3)
        self.add_ui_element("ui_diag_clear", self._diag_btn_clear)
        self._diag_btn_archive = ctk.CTkButton(
            btn_frame,
            text=T("ui_diag_archive"),
            width=160,
            fg_color="#5c6bc0",
            hover_color="#3f51b5",
            command=self._archive_and_start_new_log,
        )
        self._diag_btn_archive.pack(side="left", padx=3)
        self.add_ui_element("ui_diag_archive", self._diag_btn_archive)
        self._diag_btn_copy = ctk.CTkButton(btn_frame, text=T("ui_diag_copy"), width=100, command=self._copy_selected_logs)
        self._diag_btn_copy.pack(side="left", padx=3)
        self.add_ui_element("ui_diag_copy", self._diag_btn_copy)
        self._diag_btn_folder = ctk.CTkButton(btn_frame, text=T("ui_diag_open_folder"), width=110, command=self._open_log_folder)
        self._diag_btn_folder.pack(side="left", padx=3)
        self.add_ui_element("ui_diag_open_folder", self._diag_btn_folder)
        self._diag_btn_export = ctk.CTkButton(btn_frame, text=T("ui_diag_export"), width=150, command=self._export_debug_bundle)
        self._diag_btn_export.pack(side="left", padx=3)
        self.add_ui_element("ui_diag_export", self._diag_btn_export)

        # Status bar
        self._diag_status = ctk.CTkLabel(frame, text=T("ui_diag_ready"), text_color="gray")
        self._diag_status.pack(anchor="w", padx=10, pady=(0, 5))

        # Load initial logs
        self.after(500, self._refresh_logs)


    def _toggle_auto_refresh(self):
        """Toggle auto refresh for diagnostics."""
        if self._auto_refresh_var.get():
            self._auto_refresh_diag()


    def _auto_refresh_diag(self):
        """Auto refresh diagnostics log."""
        if self._auto_refresh_var.get():
            self._refresh_logs()
            self.after(3000, self._auto_refresh_diag)


    def _copy_selected_logs(self):
        """Copy selected text from log display."""
        try:
            selected = self._log_text.get("sel.first", "sel.last")
            self.clipboard_clear()
            self.clipboard_append(selected)
            self._diag_status.configure(text="Copied to clipboard")
        except Exception:
            self._diag_status.configure(text="No text selected")


    def _open_log_folder(self):
        """Open log folder in file explorer."""
        log_dir = os.path.join(self._project_root(), "logs")
        if not os.path.isdir(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception:
                log_dir = self._project_root()
        try:
            if os.name == "nt":
                os.startfile(log_dir)
            else:
                os.system(f'xdg-open "{log_dir}"')
        except Exception as e:
            try:
                self._diag_status.configure(text=f"Open folder error: {e}")
            except Exception:
                pass

    def _resolve_app_log_path(self):
        """Prefer cwd/logs (runtime) then project root."""
        root = self._project_root()
        candidates = [
            os.path.join(os.getcwd(), "logs", "app.log"),
            os.path.join(root, "logs", "app.log"),
            os.path.join(root, "app.log"),
        ]
        return next((p for p in candidates if os.path.exists(p)), candidates[0]), candidates

    @staticmethod
    def _parse_log_line_ts(line):
        """Parse leading 'YYYY-MM-DD HH:MM:SS' from oak_logger lines → epoch or None."""
        if not line or len(line) < 19:
            return None
        try:
            from datetime import datetime
            return datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            return None

    def _log_scope_cutoff(self):
        """Return epoch cutoff for scope filter, or None for All History."""
        scope = "session"
        try:
            scope = (self._log_scope_var.get() or "session").strip()
        except Exception:
            pass
        if scope == "all":
            return None
        if scope == "15m":
            return time.time() - 15 * 60
        started = getattr(self, "_session_started_at", None)
        if started is None:
            started = time.time()
            self._session_started_at = started
        return float(started)

    def _refresh_logs(self):
        """Load logs from app.log into the display (scoped + level filtered)."""
        log_file, candidates = self._resolve_app_log_path()
        self._log_text.delete("1.0", "end")
        if not os.path.exists(log_file):
            self._log_text.insert(
                "1.0",
                "No diagnostics found.\n"
                f"Looked for: {candidates[0]}\n"
                "System is currently quiet. 🌙",
            )
            try:
                self._diag_status.configure(text="No log file")
            except Exception:
                pass
            return
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            level_filter = self._log_level_var.get()
            cutoff = self._log_scope_cutoff()
            scope = "session"
            try:
                scope = self._log_scope_var.get() or "session"
            except Exception:
                pass
            filtered = []
            accepting = False
            for line in lines:
                ts = self._parse_log_line_ts(line)
                if ts is not None:
                    if cutoff is not None and ts < cutoff:
                        accepting = False
                        continue
                    if level_filter != "ALL" and f" - {level_filter} - " not in line:
                        accepting = False
                        continue
                    accepting = True
                    filtered.append(line)
                else:
                    if accepting:
                        filtered.append(line)
            display = filtered[-500:] if len(filtered) > 500 else filtered
            if display:
                self._log_text.insert("1.0", "".join(display))
            else:
                scope_label = {
                    "session": "Current Session",
                    "15m": "Last 15 Minutes",
                    "all": "All History",
                }.get(scope, scope)
                self._log_text.insert(
                    "1.0",
                    f"(no lines for scope: {scope_label}"
                    + (f", level: {level_filter}" if level_filter != "ALL" else "")
                    + ")\n"
                    "Tip: switch to All History, or use Archive & Start New Log.\n",
                )
            if self._follow_var.get():
                self._log_text.see("end")
            self._diag_status.configure(
                text=(
                    f"Scope={scope} · shown {len(display)} / matched {len(filtered)} "
                    f"({len(lines)} file) · {os.path.basename(log_file)}"
                )
            )
        except Exception as e:
            self._log_text.insert("1.0", f"Error reading log: {e}\nPath: {log_file}")

    def _filter_logs(self):
        """Re-filter logs when level or scope changes."""
        self._refresh_logs()

    def _clear_log_display(self):
        """Clear the log display only (file unchanged)."""
        self._log_text.delete("1.0", "end")
        try:
            self._diag_status.configure(text="Display cleared (file unchanged)")
        except Exception:
            pass

    def _archive_and_start_new_log(self):
        """Rotate app.log to archive and open a fresh log for this session."""
        from tkinter import messagebox
        from datetime import datetime

        log_file, _ = self._resolve_app_log_path()
        log_dir = os.path.dirname(log_file) if log_file else os.path.join(self._project_root(), "logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception:
            pass
        target = os.path.join(log_dir, "app.log")
        if not os.path.exists(target) and os.path.exists(log_file):
            target = log_file

        if not os.path.exists(target):
            self._session_started_at = time.time()
            try:
                with open(target, "a", encoding="utf-8") as f:
                    f.write(
                        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [oak] INFO - "
                        f"New log session started (empty archive)\n"
                    )
            except Exception:
                pass
            self._refresh_logs()
            try:
                self._diag_status.configure(text="New session log started")
            except Exception:
                pass
            return

        try:
            if not messagebox.askyesno(
                "Archive & Start New Log",
                "Archive the current app.log and start a fresh log file?\n\n"
                "Historical errors stay in the archive; Current Session will only show new lines.",
            ):
                return
        except Exception:
            pass

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive = os.path.join(log_dir, f"app_{stamp}.log")
        try:
            try:
                import logging
                for name in list(logging.Logger.manager.loggerDict.keys()):
                    lg = logging.getLogger(name)
                    for h in list(lg.handlers):
                        try:
                            base = getattr(h, "baseFilename", "") or ""
                            if base.replace("\\", "/").endswith("/app.log"):
                                h.close()
                                lg.removeHandler(h)
                        except Exception:
                            pass
            except Exception:
                pass

            os.replace(target, archive)
            with open(target, "w", encoding="utf-8") as f:
                f.write(
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [oak] INFO - "
                    f"Log archived to {os.path.basename(archive)}; new session started\n"
                )
            self._session_started_at = time.time()
            try:
                self._log_scope_var.set("session")
            except Exception:
                pass
            self._refresh_logs()
            try:
                self._diag_status.configure(
                    text=f"Archived → {os.path.basename(archive)} · new session"
                )
                self.log(f"Diagnostics: archived log to {os.path.basename(archive)}")
            except Exception:
                pass
        except Exception as e:
            try:
                messagebox.showerror("Archive failed", str(e))
            except Exception:
                pass
            try:
                self._diag_status.configure(text=f"Archive error: {e}")
            except Exception:
                pass

    def _export_debug_bundle(self):
        """Export redacted logs/config/state zip (safe by default; raw is gated)."""
        from tkinter import filedialog, messagebox, simpledialog
        from services.debug_bundle_service import build_debug_bundle_bytes, list_export_candidates

        root = self._project_root()
        candidates = list_export_candidates(root)
        if not candidates:
            self._diag_status.configure(text="No files found to export")
            return

        listing = "\n".join(f"  • {arc}" for arc, _ in candidates)
        # Default path: always redacted (JSON + log PII). No accidental raw via "No".
        try:
            ok = messagebox.askokcancel(
                "Export Debug Bundle (redacted)",
                "Export SAFE diagnostic bundle?\n\n"
                f"Files:\n{listing}\n\n"
                "• Tokens / API keys / chat IDs redacted\n"
                "• Log PII (account, login, user path) redacted\n\n"
                "OK = export redacted ZIP\n"
                "Cancel = abort\n\n"
                "Raw secrets require typing EXPORT RAW in the next step "
                "(developer only).",
            )
            if not ok:
                return
        except Exception:
            pass

        include_raw = False
        try:
            if messagebox.askyesno(
                "Developer raw export?",
                "Do you need RAW unredacted secrets/logs?\n\n"
                "Only for local debugging. Default is NO (recommended).",
                default="no",
            ):
                typed = simpledialog.askstring(
                    "Confirm RAW export",
                    "Type exactly: EXPORT RAW\n\n"
                    "Anything else cancels raw mode (exports redacted).",
                )
                include_raw = (typed or "").strip() == "EXPORT RAW"
                if not include_raw:
                    messagebox.showinfo(
                        "Redacted export",
                        "Phrase mismatch — exporting REDACTED bundle only.",
                    )
        except Exception:
            include_raw = False

        bundle_path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("Zip files", "*.zip")],
            title="Save Debug Bundle",
            initialfile=(
                "oak_debug_bundle_RAW.zip" if include_raw else "oak_debug_bundle.zip"
            ),
        )
        if not bundle_path:
            return
        try:
            data = build_debug_bundle_bytes(
                root,
                include_account_raw=include_raw,
                selected=[arc for arc, _ in candidates],
            )
            with open(bundle_path, "wb") as f:
                f.write(data)
            mode = "RAW SECRETS" if include_raw else "redacted"
            self._diag_status.configure(
                text=f"Exported ({mode}): {os.path.basename(bundle_path)}"
            )
            self.log(f"Debug bundle exported ({mode}): {bundle_path}")
        except Exception as e:
            self._diag_status.configure(text=f"Export error: {e}")


    def create_guide_frame(self, parent):
        # Clear previous content if re-building
        try:
            for child in list(parent.winfo_children()):
                child.destroy()
        except Exception:
            pass
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["guide"] = frame
        frame.pack(fill="both", expand=True)

        self.guide_box = ctk.CTkTextbox(frame, width=600, height=500, font=ctk.CTkFont(size=16), wrap="word")
        self.guide_box.pack(fill="both", expand=True)
        self.guide_box.insert("0.0", self.get_doc_content("guide_info"))
        # Markdown is relatively heavy — run after first paint of this tab
        self.after(10, lambda: self._safe_apply_markdown(self.guide_box))


    def create_readme_frame(self, parent):
        try:
            for child in list(parent.winfo_children()):
                child.destroy()
        except Exception:
            pass
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["readme"] = frame
        frame.pack(fill="both", expand=True)

        self.readme_box = ctk.CTkTextbox(frame, width=600, height=500, font=ctk.CTkFont(size=14), wrap="word")
        self.readme_box.pack(fill="both", expand=True)
        self.readme_box.insert("0.0", self.get_doc_content("readme_info"))
        self.after(10, lambda: self._safe_apply_markdown(self.readme_box))


    def create_release_notes_frame(self, parent):
        try:
            for child in list(parent.winfo_children()):
                child.destroy()
        except Exception:
            pass
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["release_notes"] = frame
        frame.pack(fill="both", expand=True)

        self.release_box = ctk.CTkTextbox(frame, width=600, height=500, font=ctk.CTkFont(size=14), wrap="word")
        self.release_box.pack(fill="both", expand=True)
        self.release_box.insert("0.0", self.get_doc_content("release_notes_info"))
        self.after(10, lambda: self._safe_apply_markdown(self.release_box))


    def _safe_apply_markdown(self, box):
        if not self._widget_alive(box):
            return
        try:
            self.apply_markdown(box)
            box.configure(state="disabled")
        except Exception:
            try:
                box.configure(state="disabled")
            except Exception:
                pass


    def _format_markdown_tables(self, text_widget):
        """Render simple Markdown tables as readable text in the desktop docs."""
        original = text_widget.get("1.0", "end-1c")
        formatted = []
        for line in original.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("|") and stripped.endswith("|")):
                formatted.append(line)
                continue
            cells = [cell.strip() for cell in stripped[1:-1].split("|")]
            is_separator = cells and all(
                cell and set(cell) <= {"-", ":"} for cell in cells
            )
            if not is_separator:
                formatted.append("   ".join(cells))
        rendered = "\n".join(formatted)
        if rendered != original:
            text_widget.delete("1.0", "end")
            text_widget.insert("1.0", rendered)


    def apply_markdown(self, textbox):
        # Access internal tkinter widget to bypass CTkTextbox font restriction
        tf = textbox._textbox
        self._format_markdown_tables(tf)
        
        # Clear existing tags
        for tag in tf.tag_names():
            tf.tag_remove(tag, "1.0", "end")
            
        # Configure Tags
        tf.tag_config("h1", font=ctk.CTkFont(size=24, weight="bold"), foreground="#1565C0")
        tf.tag_config("h2", font=ctk.CTkFont(size=20, weight="bold"), foreground="#1976D2")
        tf.tag_config("h3", font=ctk.CTkFont(size=18, weight="bold"), foreground="#0277bd")
        tf.tag_config("bold", font=ctk.CTkFont(size=16, weight="bold"))
        tf.tag_config("italic", font=ctk.CTkFont(size=16, slant="italic"))
        tf.tag_config("note", foreground="orange", font=ctk.CTkFont(size=16, slant="italic"))
        tf.tag_config("link", foreground="#1E88E5", underline=True)
        
        count = tkinter.IntVar()
        
        # 1. Process Headers (#, ##, ###) and remove markers
        for tag_name, marker, size in [("h1", "# ", 24), ("h2", "## ", 20), ("h3", "### ", 18)]:
            while True:
                pos = tf.search(f"^{marker}", "1.0", stopindex="end", count=count, regexp=True)
                if not pos: break
                
                # Delete marker
                tf.delete(pos, f"{pos}+{len(marker)}c")
                
                # Find end of line
                line_end = tf.index(f"{pos} lineend")
                tf.tag_add(tag_name, pos, line_end)
        
        # 2. Process Numbered Headers (1. Title)
        start = "1.0"
        while True:
            pos = tf.search(r"^\d+\..*", start, stopindex="end", count=count, regexp=True)
            if not pos: break
            end = f"{pos}+{count.get()}c"
            tf.tag_add("h2", pos, end)
            start = end
            
        # 3. Notes (Note: or Lưu ý:)
        start = "1.0"
        while True:
            pos = tf.search(r"^(Lưu ý|Note):.*", start, stopindex="end", count=count, regexp=True)
            if not pos: break
            end = f"{pos}+{count.get()}c"
            tf.tag_add("note", pos, end)
            start = end

        # 4. Bold (**text**) - Process and remove markers
        while True:
            pos = tf.search(r"\*\*.*?\*\*", "1.0", stopindex="end", count=count, regexp=True)
            if not pos: break
            
            match_len = count.get()
            tf.delete(pos, f"{pos}+2c")
            content_len = match_len - 4
            trail_pos = f"{pos}+{content_len}c"
            tf.delete(trail_pos, f"{trail_pos}+2c")
            tf.tag_add("bold", pos, f"{pos}+{content_len}c")

        # 5. Italic (*text*) - Process and remove markers
        while True:
            pos = tf.search(r"\*[^\*]+\*", "1.0", stopindex="end", count=count, regexp=True)
            if not pos: break
            
            match_len = count.get()
            tf.delete(pos, f"{pos}+1c")
            content_len = match_len - 2
            trail_pos = f"{pos}+{content_len}c"
            tf.delete(trail_pos, f"{trail_pos}+1c")
            tf.tag_add("italic", pos, f"{pos}+{content_len}c")

        # 6. Colored Text (<c=#HEX>text</c>) - NEW v3.0.0
        start = "1.0"
        while True:
            # Search for <c=#HEX>content</c>
            pos = tf.search(r"<c=(#[A-Fa-f0-9]{6})>.*?</c>", start, stopindex="end", count=count, regexp=True)
            if not pos: break
            
            match_str = tf.get(pos, f"{pos}+{count.get()}c")
            match = re.search(r"<c=(#[A-Fa-f0-9]{6})>(.*?)</c>", match_str)
            if match:
                color = match.group(1)
                content = match.group(2)
                tag_name = f"color_{color}"
                
                # Configure tag if not exists
                if tag_name not in tf.tag_names():
                    tf.tag_config(tag_name, foreground=color)
                
                # Replace the whole tag with just content
                tf.delete(pos, f"{pos}+{count.get()}c")
                tf.insert(pos, content)
                tf.tag_add(tag_name, pos, f"{pos}+{len(content)}c")
                start = f"{pos}+{len(content)}c"
            else:
                start = f"{pos}+1c"


    def create_about_frame(self, parent):
        """Giới thiệu — layout Trading Terminal (typography + theme cards)."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frames["about"] = frame
        frame.pack(fill="both", expand=True)

        p = getattr(self, "theme_palette", {}) or {}
        accent = p.get("accent", "#3b82f6")
        card_bg = p.get("card_bg", "#18181b")
        border = p.get("card_border", "#27272a")
        muted = p.get("text_muted", "#a1a1aa")
        primary = p.get("text_primary", "#fafafa")

        outer = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=28, pady=24)

        # Hero
        hero = ctk.CTkFrame(outer, fg_color=card_bg, corner_radius=16, border_width=1, border_color=border)
        hero.pack(fill="x", pady=(0, 20))
        hero_in = ctk.CTkFrame(hero, fg_color="transparent")
        hero_in.pack(fill="x", padx=28, pady=28)

        badge = ctk.CTkFrame(hero_in, fg_color=accent, corner_radius=12, width=56, height=56)
        badge.pack(pady=(0, 14))
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text="OAK", font=ctk.CTkFont(size=16, weight="bold"), text_color="#ffffff").place(relx=0.5, rely=0.5, anchor="center")

        self.lbl_about_title = ctk.CTkLabel(
            hero_in, text=f"OAK Manager {VERSION}",
            font=ctk.CTkFont(size=26, weight="bold"), text_color=primary,
        )
        self.lbl_about_title.pack()
        ctk.CTkLabel(
            hero_in, text=T("ui_about_subtitle"),
            font=ctk.CTkFont(size=13), text_color=muted,
        ).pack(pady=(6, 0))
        ctk.CTkLabel(
            hero_in, text=f"Stable · Build {BUILD} · Windows x64",
            font=ctk.CTkFont(size=11), text_color=muted,
        ).pack(pady=(4, 0))

        self.lbl_about = ctk.CTkLabel(
            hero_in, text=T("about_info"), font=ctk.CTkFont(size=13),
            text_color=muted, wraplength=520, justify="center",
        )
        self.lbl_about.pack(pady=(16, 0))
        self.add_ui_element("about_info", self.lbl_about)

        btn_row = ctk.CTkFrame(hero_in, fg_color="transparent")
        btn_row.pack(pady=(20, 0))
        ctk.CTkButton(
            btn_row, text=T("ui_about_docs"), width=160, height=36, corner_radius=10,
            fg_color=accent, hover_color=p.get("accent_hover", accent),
            command=lambda: os.startfile("README.md") if os.path.exists("README.md") else None,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            btn_row, text=T("ui_about_updates"), width=160, height=36, corner_radius=10,
            fg_color="transparent", border_width=1, border_color=border, text_color=primary,
            hover_color=p.get("panel_alt_bg", "#18181b"),
            command=lambda: self.log("Checking for updates..."),
        ).pack(side="left", padx=6)

        # Theme section
        ctk.CTkLabel(
            outer, text=T("about_section_theme"), font=ctk.CTkFont(size=11, weight="bold"),
            text_color=muted, anchor="w",
        ).pack(fill="x", pady=(8, 10))

        themes_row = ctk.CTkFrame(outer, fg_color="transparent")
        themes_row.pack(fill="x")
        themes_row.grid_columnconfigure((0, 1, 2), weight=1, uniform="theme")

        theme_defs = [
            ("dark", T("theme_dark"), "Dark", "#09090b", "#3b82f6", "#27272a"),
            ("light", T("theme_light"), "Light", "#f8fafc", "#0ea5e9", "#e2e8f0"),
            ("deepsea", T("theme_deepsea"), "Deep Sea", "#020617", "#22d3ee", "#164e63"),
        ]
        current = self.settings.get("theme", "dark")
        self._about_theme_cards = {}
        for col, (key, label, short, bg, acc, brd) in enumerate(theme_defs):
            selected = key == current
            card = ctk.CTkFrame(
                themes_row, fg_color=bg, corner_radius=14,
                border_width=2, border_color=acc if selected else brd, height=120,
            )
            card.grid(row=0, column=col, sticky="nsew", padx=6)
            card.grid_propagate(False)
            sw = ctk.CTkFrame(card, fg_color=acc, corner_radius=8, height=8)
            sw.pack(fill="x", padx=14, pady=(16, 10))
            ctk.CTkLabel(card, text=short, font=ctk.CTkFont(size=15, weight="bold"),
                         text_color="#fafafa" if key != "light" else "#0f172a").pack()
            ctk.CTkLabel(
                card, text=T("about_card_active") if selected else T("about_card_select"),
                font=ctk.CTkFont(size=11),
                text_color=acc if selected else ("#a1a1aa" if key != "light" else "#64748b"),
            ).pack(pady=(4, 0))

            def _make_theme_cmd(lbl=label):
                return lambda: self.change_theme(lbl)

            card.bind("<Button-1>", lambda e, c=_make_theme_cmd(): c())
            for child in card.winfo_children():
                child.bind("<Button-1>", lambda e, c=_make_theme_cmd(): c())
            self._about_theme_cards[key] = card

        # Language section (same card language as themes)
        ctk.CTkLabel(
            outer, text=T("about_section_lang"), font=ctk.CTkFont(size=11, weight="bold"),
            text_color=muted, anchor="w",
        ).pack(fill="x", pady=(22, 10))

        lang_row = ctk.CTkFrame(outer, fg_color="transparent")
        lang_row.pack(fill="x")
        lang_row.grid_columnconfigure((0, 1), weight=1, uniform="lang")

        lang_defs = [
            ("VN", "VN", T("about_lang_vn"), "#0f172a", "#3b82f6", "#1e293b"),
            ("EN", "EN", T("about_lang_en"), "#0c4a6e", "#0ea5e9", "#075985"),
        ]
        self._about_lang_cards = {}
        for col, (key, code, label, bg, acc, brd) in enumerate(lang_defs):
            selected = key == CURRENT_LANG
            card = ctk.CTkFrame(
                lang_row, fg_color=bg, corner_radius=14,
                border_width=2, border_color=acc if selected else brd, height=120,
            )
            card.grid(row=0, column=col, sticky="nsew", padx=6)
            card.grid_propagate(False)
            sw = ctk.CTkFrame(card, fg_color=acc, corner_radius=8, height=8)
            sw.pack(fill="x", padx=14, pady=(16, 10))
            ctk.CTkLabel(
                card, text=code, font=ctk.CTkFont(size=18, weight="bold"), text_color="#fafafa",
            ).pack()
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=12), text_color="#cbd5e1").pack(pady=(2, 0))
            ctk.CTkLabel(
                card, text=T("about_card_active") if selected else T("about_card_select"),
                font=ctk.CTkFont(size=11),
                text_color=acc if selected else "#94a3b8",
            ).pack(pady=(4, 0))

            def _make_lang_cmd(k=key):
                return lambda: self.change_lang(k)

            card.bind("<Button-1>", lambda e, c=_make_lang_cmd(): c())
            for child in card.winfo_children():
                child.bind("<Button-1>", lambda e, c=_make_lang_cmd(): c())
            self._about_lang_cards[key] = card


    def get_doc_content(self, key):
        """Load docs by language only — never mix EN with VN file content.

        Source of truth: ``*.en.md``. VN files ``GUIDE.md`` / ``README.md`` /
        ``RELEASE_NOTES.md`` are translations (regenerate via
        ``python scripts/sync_docs_from_en.py``).
        """
        file_map = {
            "VN": {
                "guide_info": "GUIDE.md",
                "readme_info": "README.md",
                "release_notes_info": "RELEASE_NOTES.md",
            },
            "EN": {
                "guide_info": "GUIDE.en.md",
                "readme_info": "README.en.md",
                "release_notes_info": "RELEASE_NOTES.en.md",
            },
        }
        # Controllers receive CURRENT_LANG as an import-time alias. Read the
        # domain value here so an EN preference restored during app startup
        # cannot accidentally load the VN document.
        try:
            from domain import i18n
            lang = i18n.CURRENT_LANG
        except Exception:
            lang = CURRENT_LANG
        if lang not in ("VN", "EN"):
            lang = "VN"
        name = (file_map.get(lang) or {}).get(key)
        if not name:
            return T(key)
        root = self._project_root()
        # Prefer project root (repo / installed package), then cwd
        for path in (
            os.path.join(root, name),
            os.path.join(os.getcwd(), name),
            name,
        ):
            if path and os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        text = f.read()
                    if text.strip():
                        return text
                except Exception:
                    pass
        return T(key)


    def change_lang(self, value):
        """Switch UI language in-place (no full tabview destroy — that blanks news/console)."""
        import OAK_Hidden_SLTP_Manager as oak
        import controllers.dashboard_controller as _selfmod

        if value not in ("VN", "EN"):
            return
        if value == getattr(oak, "CURRENT_LANG", None):
            return

        # Single source of truth for lang
        try:
            import domain.i18n as _i18n

            _i18n.CURRENT_LANG = value
        except Exception:
            pass
        oak.CURRENT_LANG = value
        # Keep free-name CURRENT_LANG in sync across controller modules + app
        try:
            from controllers.runtime import _CONTROLLER_MODULES
            import importlib
            import sys as _sys

            for _mn in _CONTROLLER_MODULES:
                try:
                    setattr(importlib.import_module(_mn), "CURRENT_LANG", value)
                except Exception:
                    pass
            if "app" in _sys.modules:
                setattr(_sys.modules["app"], "CURRENT_LANG", value)
        except Exception:
            try:
                _selfmod.CURRENT_LANG = value
            except Exception:
                pass
        self.settings["lang"] = value
        save_json(SETTINGS_FILE, self.settings)

        if hasattr(self, "ghost_popup") and self.ghost_popup and self.ghost_popup.winfo_exists():
            try:
                self.ghost_popup.destroy()
            except Exception:
                pass
            self.ghost_popup = None

        # Defer past About-card click so the click target is not destroyed mid-handler
        if getattr(self, "_lang_after_id", None):
            try:
                self.after_cancel(self._lang_after_id)
            except Exception:
                pass
        self._lang_after_id = self.after(30, self._apply_language_in_place)


    def _apply_language_in_place(self):
        """Update labels/docs/About + tab headers without destroying Dashboard."""
        self._lang_after_id = None
        try:
            self.title(T("title"))
        except Exception:
            pass

        # 1) Registered text widgets
        for key, widgets in list(getattr(self, "ui_elements", {}).items()):
            text = T(key)
            items = widgets if isinstance(widgets, list) else [widgets]
            for w in items:
                if not self._widget_alive(w):
                    continue
                try:
                    w.configure(text=text)
                except Exception:
                    pass

        # 1b) Runtime labels rebuilt from T() (cards, monitors, start/stop captions)
        try:
            if self._widget_alive(getattr(self, "card_engine_session", None)):
                self.card_engine_session.configure(text=T("ui_session_on"))
            if self._widget_alive(getattr(self, "card_engine_version", None)):
                self.card_engine_version.configure(text=f"v{VERSION[1:]} {T('ui_stable')}")
            if self._widget_alive(getattr(self, "btn_ghost_toggle", None)):
                # keep ghost state text via existing updater if available
                if hasattr(self, "_refresh_ghost_button"):
                    self._refresh_ghost_button()
                else:
                    self.btn_ghost_toggle.configure(text=T("ui_btn_ghost_short"))
        except Exception:
            pass
        try:
            self.refresh_running_monitors_panel(force=True)
        except Exception:
            pass
        try:
            self.update_ui_state(getattr(self, "selected_profile_name", None) or "")
        except Exception:
            pass
        try:
            self._update_dashboard_cards()
        except Exception:
            pass
        try:
            self.refresh_profile_list()
        except Exception:
            pass

        # 2) ScrollableFrame headers (label_text, not text=)
        label_map = dict(getattr(self, "_label_text_widgets", {}) or {})
        # Fallback attrs used by profiles tab
        if "profile_list" not in label_map and getattr(self, "list_frame", None) is not None:
            label_map["profile_list"] = self.list_frame
        if "grp_config" not in label_map and getattr(self, "form_scroll", None) is not None:
            label_map["grp_config"] = self.form_scroll
        for key, w in label_map.items():
            if not self._widget_alive(w):
                continue
            try:
                w.configure(label_text=T(key))
            except Exception:
                try:
                    if getattr(w, "_label", None) is not None:
                        w._label.configure(text=T(key))
                except Exception:
                    pass

        # 3) Theme combo labels if present
        try:
            self.refresh_theme_labels()
        except Exception:
            pass

        # 4) Static doc tabs (only if already loaded)
        for box_attr, doc_key in (
            ("guide_box", "guide_info"),
            ("readme_box", "readme_info"),
            ("release_box", "release_notes_info"),
        ):
            box = getattr(self, box_attr, None)
            if not self._widget_alive(box):
                continue
            try:
                box.configure(state="normal")
                box.delete("1.0", "end")
                box.insert("0.0", self.get_doc_content(doc_key))
                self.apply_markdown(box)
                box.configure(state="disabled")
            except Exception:
                pass

        # 5) Tab header rename (CTkTabview internals — keeps same frames)
        try:
            self._rename_tabs_for_language()
        except Exception as e:
            print(f"Tab rename failed: {e}")

        # 6) Rebuild About only (theme + language cards Active state)
        try:
            about_tab = getattr(self, "tab_about", None)
            if self._widget_alive(about_tab):
                for child in list(about_tab.winfo_children()):
                    try:
                        child.destroy()
                    except Exception:
                        pass
                self.create_about_frame(about_tab)
        except Exception as e:
            print(f"About rebuild failed: {e}")

        try:
            self.update_ghost_button_ui()
        except Exception:
            pass
        try:
            self.update_news_summary(force=True)
        except Exception:
            pass
        try:
            self.log(f"Language changed to {CURRENT_LANG}")
        except Exception:
            pass


    def _build_tab_names(self) -> dict:
        return {
            "dashboard": f"📊 {T('tab_dashboard')}",
            "signals": f"📈 {T('tab_signals')}",
            "profiles": f"👤 {T('tab_profiles')}",
            "copy_trade": f"🔄 {T('tab_copy_trade')}",
            "pos_size": f"⏰ {T('tab_pos_size')}",
            "diagnostics": "🩺 Diagnostics",
            "guide": f"📘 {T('tab_guide')}",
            "readme": f"🚀 {T('tab_readme')}",
            "release_notes": f"📋 {T('tab_release_notes')}",
            "about": f"ℹ️ {T('tab_about')}",
        }


    def _rename_tabs_for_language(self):
        """Rename CTkTabview tabs without destroying tab frames (language switch)."""
        old_names = dict(getattr(self, "tab_names", {}) or {})
        new_names = self._build_tab_names()
        if old_names == new_names:
            return

        # Which logical tab is selected?
        current_key = "dashboard"
        try:
            cur = self.tabview.get()
            for k, v in old_names.items():
                if v == cur:
                    current_key = k
                    break
        except Exception:
            pass

        tv = self.tabview
        new_tab_dict = {}
        new_name_list = []
        order = [
            "dashboard", "signals", "profiles", "copy_trade", "pos_size",
            "diagnostics", "guide", "readme", "release_notes", "about",
        ]
        for key in order:
            old_label = old_names.get(key, new_names[key])
            new_label = new_names[key]
            frame = None
            try:
                frame = tv._tab_dict.get(old_label) or tv._tab_dict.get(new_label)
            except Exception:
                frame = None
            if frame is None:
                continue
            new_tab_dict[new_label] = frame
            new_name_list.append(new_label)

        if not new_tab_dict:
            return

        tv._tab_dict = new_tab_dict
        tv._name_list = new_name_list
        tv._current_name = new_names.get(current_key, new_name_list[0])

        # Rebuild segmented button labels to match new names
        seg = getattr(tv, "_segmented_button", None)
        if seg is not None:
            try:
                seg.configure(values=new_name_list)
                seg.set(tv._current_name)
            except Exception as e:
                print(f"Segmented button rename failed: {e}")

        # Keep selected tab frame gridded
        try:
            tv._grid_forget_all_tabs(exclude_name=tv._current_name)
            tv._set_grid_current_tab()
        except Exception:
            pass

        self.tab_names = new_names
        # Refresh app tab frame refs
        try:
            self.tab_dashboard = new_tab_dict[new_names["dashboard"]]
            self.tab_signals = new_tab_dict[new_names["signals"]]
            self.tab_profiles = new_tab_dict[new_names["profiles"]]
            self.tab_copy_trade = new_tab_dict[new_names["copy_trade"]]
            self.tab_pos_size = new_tab_dict[new_names["pos_size"]]
            self.tab_diagnostics = new_tab_dict[new_names["diagnostics"]]
            self.tab_guide = new_tab_dict[new_names["guide"]]
            self.tab_readme = new_tab_dict[new_names["readme"]]
            self.tab_release = new_tab_dict[new_names["release_notes"]]
            self.tab_about = new_tab_dict[new_names["about"]]
        except Exception:
            pass

        # Lazy builders must target updated frames
        self._lazy_tab_builders = {
            "diagnostics": (lambda: self.create_diagnostics_frame(self.tab_diagnostics)),
            "guide": (lambda: self.create_guide_frame(self.tab_guide)),
            "readme": (lambda: self.create_readme_frame(self.tab_readme)),
            "release_notes": (lambda: self.create_release_notes_frame(self.tab_release)),
        }
