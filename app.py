# -*- coding: utf-8 -*-
"""OAK Manager App shell — composes controller mixins.

Domain logic (CopyTradeManager, MonitorWorker, i18n) remains in
OAK_Hidden_SLTP_Manager for worker entry compatibility; UI behavior
lives in controllers/*.
"""
from __future__ import annotations

import os
import queue
import sys

import customtkinter as ctk

# Domain module first (must not import app at module level).
# Prefer the already-running __main__ copy when launched via OAK_*.py
# so we never bind controllers to a duplicate domain module.
_main = sys.modules.get("__main__")
if (
    _main is not None
    and getattr(_main, "__file__", None)
    and str(getattr(_main, "__file__", "")).replace("\\", "/").endswith(
        "OAK_Hidden_SLTP_Manager.py"
    )
):
    oak = _main
    sys.modules.setdefault("OAK_Hidden_SLTP_Manager", oak)
else:
    import OAK_Hidden_SLTP_Manager as oak

from controllers.runtime import bind_oak_globals
from services.app_services import AppServices

# Inject free-name globals into this module + all controller mixins
bind_oak_globals(oak, extra_modules=[sys.modules[__name__]])

from controllers import (  # noqa: E402
    AppShellControllerMixin,
    CopyTradeControllerMixin,
    DashboardControllerMixin,
    MonitorControllerMixin,
    PendingControllerMixin,
    ProfileControllerMixin,
    SignalControllerMixin,
)

# Local aliases used by App.__init__ free names (also bound via bind_oak_globals)
AppState = oak.AppState
load_json = oak.load_json
save_json = oak.save_json
SETTINGS_FILE = oak.SETTINGS_FILE
CONFIG_FILE = oak.CONFIG_FILE
T = oak.T
resource_path = oak.resource_path
SQLiteStore = oak.SQLiteStore
ProfileStore = oak.ProfileStore
SignalProcessSupervisor = oak.SignalProcessSupervisor


class App(
    ctk.CTk,
    AppShellControllerMixin,
    MonitorControllerMixin,
    ProfileControllerMixin,
    SignalControllerMixin,
    CopyTradeControllerMixin,
    PendingControllerMixin,
    DashboardControllerMixin,
):
    """Main desktop application window."""

    def __init__(self):
        super().__init__()

        # Never shadow Tk/CTk wm_state method with our AppState bag
        self._tk_state_method = type(self).state if callable(getattr(type(self), "state", None)) else None

        # Explicit services bag (preferred over free-name globals)
        self.services = AppServices(oak)

        # Initialize AppState (MUST be app_state, not state — CTk uses self.state())
        self.app_state = AppState()

        # Load Settings
        self.settings = load_json(SETTINGS_FILE)
        self.app_state.set("settings", self.settings)

        # Mutate domain CURRENT_LANG (shared with worker/i18n)
        try:
            import domain.i18n as _i18n

            _i18n.CURRENT_LANG = self.settings.get("lang", "VN")
            oak.CURRENT_LANG = _i18n.CURRENT_LANG
        except Exception:
            oak.CURRENT_LANG = self.settings.get("lang", "VN")
        self.app_state.set("lang", getattr(oak, "CURRENT_LANG", "VN"))
        self.app_state.set("theme", self.settings.get("theme", "light"))

        # SQLite store for heartbeat
        self._store = SQLiteStore()

        # Ensure Ghost Mode is in settings
        if "ghost_mode_active" not in self.settings:
            self.settings["ghost_mode_active"] = False
            save_json(SETTINGS_FILE, self.settings)
        self.app_state.set("ghost_mode_active", self.settings["ghost_mode_active"])

        # Initialize ProfileStore
        self.profile_store = ProfileStore(CONFIG_FILE)

        # Initialize SignalProcessSupervisor (we'll register the UI later)
        self.signal_supervisor = SignalProcessSupervisor([], log_callback=self.log)

        # Theme Setup
        self.apply_theme(self.settings.get("theme", "light"))  # Default to Light as per user request

        # Window Setup
        self.title(T("title"))
        self.geometry("1000x700")  # Resized as per user request

        # Icon Setup
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        # Thread-safe UI marshal: background threads only enqueue; main loop pumps.
        self._ui_queue = queue.Queue()
        self.signal_supervisor.set_ui_after(self._schedule_ui)
        self.after(40, self._pump_ui_queue)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Data
        self.profiles = self.profile_store.load()
        self.app_state.set("profiles", self.profiles)
        self.workers = {}  # {profile_name: {"proc": Popen, "console": CTkTextbox, "btn_stop": CTkButton}}
        self.ui_elements = {}  # Store widgets for language update
        self._last_json_mtime = 0  # Initialize for periodic refresh sync
        self.selected_profile_name = None  # Profile selected in list (editing)
        self.running_profile_name = None  # Profile with active worker

        # Injects profile_name if missing from profiles to ensure sync works
        for name, profile in self.profiles.items():
            if "profile_name" not in profile:
                profile["profile_name"] = name

        # Layout (no left sidebar — Ghost lives under Start/Stop on Dashboard)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Status Bar
        self.status_bar = ctk.CTkFrame(self, height=28, corner_radius=0)
        self.status_bar.grid(row=1, column=0, sticky="sew")
        self.status_mt5 = ctk.CTkLabel(
            self.status_bar, text="MT5 ● —", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.status_mt5.pack(side="left", padx=10)
        self.status_telegram = ctk.CTkLabel(
            self.status_bar, text="Telegram ● —", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.status_telegram.pack(side="left", padx=10)
        self.status_ghost = ctk.CTkLabel(
            self.status_bar, text="Ghost ● —", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.status_ghost.pack(side="left", padx=10)
        self.status_system = ctk.CTkLabel(
            self.status_bar, text="", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.status_system.pack(side="right", padx=10)

        # Main Area
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

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

        # Eager: core trading tabs only (fast startup)
        self._tab_loaded = set()
        self._lazy_tab_builders = {
            "diagnostics": (lambda: self.create_diagnostics_frame(self.tab_diagnostics)),
            "guide": (lambda: self.create_guide_frame(self.tab_guide)),
            "readme": (lambda: self.create_readme_frame(self.tab_readme)),
            "release_notes": (lambda: self.create_release_notes_frame(self.tab_release)),
        }
        self.create_dashboard_frame(self.tab_dashboard)
        self.create_signals_frame(self.tab_signals)
        self.create_profiles_frame(self.tab_profiles)
        self.create_copy_trade_frame(self.tab_copy_trade)
        self.create_pos_size_frame(self.tab_pos_size)
        self.create_about_frame(self.tab_about)
        for k in ("dashboard", "signals", "profiles", "copy_trade", "pos_size", "about"):
            self._tab_loaded.add(k)
        self.apply_theme_overrides()

        self.tabview.set(self.tab_names["dashboard"])
        # No hover-to-switch: it feels laggy and switches tabs accidentally

        # Initial Profile Selection
        if self.profiles:
            initial = list(self.profiles.keys())[0]
            self.combo_profiles.set(initial)
            self.on_profile_change(initial)

        # Defer non-critical work so window appears first
        self.after(150, self._deferred_startup)

    def state(self, newstate=None):
        """Preserve Tk window state API even if something assigns over instance attr."""
        # Prefer real Tk method (never our AppState instance)
        try:
            import tkinter

            return tkinter.Wm.wm_state(self, newstate)
        except Exception:
            if newstate is None:
                return "normal"
            return None

    def _schedule_ui(self, callback):
        """Enqueue a zero-arg callback for the Tk main thread (thread-safe)."""
        try:
            self._ui_queue.put(callback)
        except Exception:
            pass

    def _pump_ui_queue(self):
        """Drain UI callbacks scheduled from worker/reader threads."""
        try:
            while True:
                try:
                    cb = self._ui_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    if callable(cb):
                        cb()
                except Exception:
                    pass
        finally:
            try:
                if self.winfo_exists():
                    self.after(40, self._pump_ui_queue)
            except Exception:
                pass


def main() -> None:
    """GUI entrypoint."""
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
