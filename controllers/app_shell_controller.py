# -*- coding: utf-8 -*-
"""Tab lifecycle, logging helpers, close handlers."""
from __future__ import annotations

class AppShellControllerMixin:
    """Tab lifecycle, logging helpers, close handlers."""

    def add_ui_element(self, key, widget):
        """Helper to store multiple widgets for the same translation key"""
        if key not in self.ui_elements:
            self.ui_elements[key] = []
        self.ui_elements[key].append(widget)


    def _deferred_startup(self):
        """Non-blocking post-show work: news + periodic refresh."""
        self._startup_news_ready = True
        try:
            self.update_news_summary(force=True)
        except Exception as e:
            print(f"Deferred news load: {e}")
        try:
            self.periodic_ui_refresh()
        except Exception as e:
            print(f"Deferred refresh start: {e}")


    def _tab_key_from_name(self, name: str) -> str:
        for k, v in getattr(self, "tab_names", {}).items():
            if v == name:
                return k
        return ""


    def _ensure_tab_loaded(self, key: str):
        """Lazy-build heavy tabs on first visit (guide/readme/etc.)."""
        if not key or key in getattr(self, "_tab_loaded", set()):
            return
        builder = getattr(self, "_lazy_tab_builders", {}).get(key)
        if not builder:
            self._tab_loaded.add(key)
            return
        try:
            builder()
        except Exception as e:
            print(f"Lazy tab '{key}' failed: {e}")
        self._tab_loaded.add(key)


    def _rebuild_tabview(self, preferred_key="dashboard"):
        current_key = preferred_key
        try:
            current_name = self.tabview.get()
            for k, v in getattr(self, "tab_names", {}).items():
                if v == current_name:
                    current_key = k
                    break
        except Exception:
            current_key = preferred_key

        # Remember running profile before widgets are destroyed
        saved_profile = ""
        try:
            combo = getattr(self, "combo_profiles", None)
            if combo is not None:
                saved_profile = (combo.get() or "").strip()
        except Exception:
            saved_profile = ""
        if not saved_profile:
            saved_profile = getattr(self, "selected_profile_name", None) or getattr(self, "running_profile_name", None) or ""

        # Invalidate async UI targets BEFORE destroy (prevents bad window path errors)
        self._news_gen = getattr(self, "_news_gen", 0) + 1
        for attr in (
            "news_box", "console", "copy_console", "combo_profiles",
            "btn_ghost_toggle", "btn_start", "btn_stop", "lbl_engine_badge",
            "card_account_server", "card_account_status", "card_signal_current",
            "card_signal_next", "card_signal_countdown", "card_engine_ghost",
        ):
            try:
                setattr(self, attr, None)
            except Exception:
                pass

        try:
            self.update_idletasks()
        except Exception:
            pass

        try:
            for child in list(self.main_frame.winfo_children()):
                try:
                    child.destroy()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            self.update_idletasks()
        except Exception:
            pass

        # Ensure main area still expands after full rebuild
        try:
            self.main_frame.grid_columnconfigure(0, weight=1)
            self.main_frame.grid_rowconfigure(0, weight=1)
        except Exception:
            pass

        self.frames = {}
        self.signal_procs = {}
        self.tab_names = {
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

        self.tabview = ctk.CTkTabview(self.main_frame, command=self._on_tab_change)
        self.tabview.grid(row=0, column=0, sticky="nsew")

        self.tab_dashboard = self.tabview.add(self.tab_names["dashboard"])
        self.tab_signals = self.tabview.add(self.tab_names["signals"])
        self.tab_profiles = self.tabview.add(self.tab_names["profiles"])
        self.tab_copy_trade = self.tabview.add(self.tab_names["copy_trade"])
        self.tab_pos_size = self.tabview.add(self.tab_names["pos_size"])
        self.tab_diagnostics = self.tabview.add(self.tab_names["diagnostics"])
        self.tab_guide = self.tabview.add(self.tab_names["guide"])
        self.tab_readme = self.tabview.add(self.tab_names["readme"])
        self.tab_release = self.tabview.add(self.tab_names["release_notes"])
        self.tab_about = self.tabview.add(self.tab_names["about"])

        creators = [
            ("dashboard", self.create_dashboard_frame, self.tab_dashboard),
            ("signals", self.create_signals_frame, self.tab_signals),
            ("profiles", self.create_profiles_frame, self.tab_profiles),
            ("copy_trade", self.create_copy_trade_frame, self.tab_copy_trade),
            ("pos_size", self.create_pos_size_frame, self.tab_pos_size),
            ("diagnostics", self.create_diagnostics_frame, self.tab_diagnostics),
            ("guide", self.create_guide_frame, self.tab_guide),
            ("readme", self.create_readme_frame, self.tab_readme),
            ("release_notes", self.create_release_notes_frame, self.tab_release),
            ("about", self.create_about_frame, self.tab_about),
        ]
        for name, fn, tab in creators:
            try:
                fn(tab)
            except Exception as e:
                # Do not call self.log here — console may be mid-rebuild
                print(f"⚠️ Rebuild tab '{name}' failed: {e}")

        try:
            self.apply_theme_overrides()
        except Exception as e:
            print(f"Theme overrides after rebuild failed: {e}")

        if current_key not in self.tab_names:
            current_key = "dashboard"
        try:
            self.tabview.set(self.tab_names[current_key])
        except Exception:
            try:
                self.tabview.set(self.tab_names["dashboard"])
            except Exception:
                pass

        try:
            self.update_idletasks()
        except Exception:
            pass

        if getattr(self, "profiles", None):
            try:
                initial = saved_profile if saved_profile in self.profiles else ""
                if not initial:
                    initial = list(self.profiles.keys())[0]
                if getattr(self, "combo_profiles", None) is not None:
                    self.combo_profiles.configure(values=list(self.profiles.keys()))
                    self.combo_profiles.set(initial)
                self.on_profile_change(initial)
            except Exception as e:
                print(f"Profile restore after rebuild failed: {e}")


    def _on_tab_change(self):
        current = ""
        try:
            current = self.tabview.get()
        except Exception:
            current = ""
        key = self._tab_key_from_name(current) if current else ""
        if key:
            self._ensure_tab_loaded(key)
        if current and current == self.tab_names.get("copy_trade", ""):
            try:
                self.load_copy_config()
            except Exception:
                pass


    def on_closing(self):
        # Cleanup all spawned processes
        _cleanup_processes()
        # Stop all signal processes via supervisor
        self.signal_supervisor.cleanup()
        # Stop all workers
        for name, data in self.workers.items():
            if data["proc"].poll() is None:
                try:
                    data["proc"].kill()
                except: pass
        self.destroy()
        sys.exit(0)


    def notify(self, message):
        """Standard notification for CopyTradeManager within GUI process"""
        self.log(message)

    # --- LOGIC ---

    def log(self, msg):
        # Ensure thread safety by scheduling GUI update on main thread
        print(msg) # Debug print
        self.after(0, self._log_safe, msg)


    def _detect_log_tag(self, msg):
        """Detect log category for color coding."""
        m = msg.lower()
        if any(kw in m for kw in ["error", "fail", "❌", "loint"]): return "error"
        if any(kw in m for kw in ["warn", "⚠️"]): return "warning"
        if any(kw in m for kw in ["mt5", "position", "order", "trade", "ticket"]): return "mt5"
        if any(kw in m for kw in ["telegram", "tg ", "notify", "tele"]): return "telegram"
        if any(kw in m for kw in ["signal", "buy", "sell", "📊", "tín hiệu"]): return "signal"
        return "info"

    _LOG_COLORS = {
        "info": "#b0bec5",
        "warning": "#ffb74d",
        "error": "#ef5350",
        "mt5": "#29b6f6",
        "telegram": "#ab47bc",
        "signal": "#66bb6a",
    }


    def _log_safe(self, msg):
        if getattr(self, "_ui_rebuilding", False):
            print(msg)
            return
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            full_msg = f"[{timestamp}] {msg}\n"

            # Check console filters
            if hasattr(self, '_console_filters') and self._console_filters:
                tag = self._detect_log_tag(msg)
                tag_key = tag.upper().replace("TELEGRAM", "TG")
                if tag_key in self._console_filters and not self._console_filters[tag_key].get():
                    return  # Filtered out

            # Dashboard Console
            console = getattr(self, "console", None)
            if console is not None:
                try:
                    if console.winfo_exists():
                        tag = self._detect_log_tag(msg)
                        color = self._LOG_COLORS.get(tag, "#b0bec5")
                        console.configure(state="normal")
                        console.insert("end", full_msg, tag)
                        console.tag_config(tag, foreground=color)
                        console.see("end")
                        console.configure(state="disabled")
                except Exception:
                    pass

            # Copy Trade Console
            copy_console = getattr(self, "copy_console", None)
            if copy_console is not None:
                try:
                    if copy_console.winfo_exists():
                        copy_console.configure(state="normal")
                        copy_console.insert("end", full_msg)
                        self.apply_markdown(copy_console)
                        copy_console.see("end")
                        copy_console.configure(state="disabled")
                except Exception:
                    pass

        except Exception as e:
            print(f"Log Error: {e}")
