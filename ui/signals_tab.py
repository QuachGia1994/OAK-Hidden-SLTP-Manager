# -*- coding: utf-8 -*-
"""SignalsTab - manages the Signals tab UI."""
from __future__ import annotations

import customtkinter as ctk
from typing import Any, Callable

from .base_tab import BaseTab


def _resolve_T() -> Callable[[str], str]:
    """Resolve translation helper without relying only on __main__."""
    import sys

    # 1) Domain module (preferred after architecture split)
    try:
        import OAK_Hidden_SLTP_Manager as oak

        if callable(getattr(oak, "T", None)):
            return oak.T
    except Exception:
        pass

    # 2) __main__ when launched as OAK_Hidden_SLTP_Manager.py
    try:
        main = sys.modules.get("__main__")
        if main is not None and callable(getattr(main, "T", None)):
            return main.T
    except Exception:
        pass

    # 3) app module after bind
    try:
        import app as app_mod

        if callable(getattr(app_mod, "T", None)):
            return app_mod.T
    except Exception:
        pass

    return lambda key: str(key)


class SignalsTab(BaseTab):
    """Tab for managing signal processes."""

    def __init__(self, app: Any):
        super().__init__(app)
        self.signal_procs = {}

    def mount(self, parent: Any) -> None:
        """Mount the Signals tab UI."""
        T = _resolve_T()

        # Clear previous content if tab is remounted (language rebuild)
        try:
            for child in list(parent.winfo_children()):
                child.destroy()
        except Exception:
            pass

        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0, 10))

        self.btn_start_all = ctk.CTkButton(
            btn_frame,
            text=T("btn_start_all_signals"),
            fg_color="#2fa572",
            hover_color="#238a5c",
            command=self.start_all_signals,
        )
        self.btn_start_all.pack(side="left", padx=5)
        self.app.add_ui_element("btn_start_all_signals", self.btn_start_all)

        self.btn_stop_all = ctk.CTkButton(
            btn_frame,
            text=T("btn_stop_all_signals"),
            fg_color="#d9534f",
            hover_color="#c9302c",
            command=self.stop_all_signals,
        )
        self.btn_stop_all.pack(side="left", padx=5)
        self.app.add_ui_element("btn_stop_all_signals", self.btn_stop_all)

        panels_frame = ctk.CTkFrame(frame, fg_color="transparent")
        panels_frame.pack(fill="both", expand=True)
        panels_frame.grid_columnconfigure(0, weight=1)
        panels_frame.grid_columnconfigure(1, weight=1)
        panels_frame.grid_rowconfigure(0, weight=1)
        panels_frame.grid_rowconfigure(1, weight=1)
        panels_frame.grid_rowconfigure(2, weight=1)

        signal_defs = [
            ("signal_bot", "MT5 Signal Bot", "#2fa572"),
            ("mt_server", "MT4-MT5 Server", "#1f538d"),
            ("mimo_bot", "MiMo Telegram Bot", "#b33dd4"),
            ("mimo_worker", "MiMo Worker", "#d4a03d"),
            ("factcheck_worker", "Fact Check Worker", "#00bfa5"),
        ]

        positions = [(0, 0, 1), (0, 1, 1), (1, 0, 1), (1, 1, 1), (2, 0, 2)]
        self.signal_procs = {}

        for idx, (key, name, color) in enumerate(signal_defs):
            row, col, columnspan = positions[idx]
            panel = ctk.CTkFrame(panels_frame, corner_radius=8)
            panel.grid(row=row, column=col, columnspan=columnspan, padx=5, pady=5, sticky="nsew")

            header = ctk.CTkFrame(panel, fg_color="transparent")
            header.pack(fill="x", padx=10, pady=(8, 2))

            dot = ctk.CTkLabel(header, text="●", text_color=color, font=("", 14))
            dot.pack(side="left", padx=(0, 5))

            ctk.CTkLabel(header, text=name, font=("", 13, "bold")).pack(side="left")

            lbl_status = ctk.CTkLabel(
                header, text="Stopped", font=("", 10, "bold"), text_color="#9e9e9e"
            )
            lbl_status.pack(side="left", padx=(8, 0))

            lbl_pid = ctk.CTkLabel(header, text="PID: ---", font=("", 11))
            lbl_pid.pack(side="right", padx=5)

            btn_frame_p = ctk.CTkFrame(header, fg_color="transparent")
            btn_frame_p.pack(side="right", padx=5)

            btn_start = ctk.CTkButton(
                btn_frame_p,
                text="▶",
                width=32,
                height=28,
                fg_color="#2fa572",
                hover_color="#238a5c",
                command=lambda k=key: self.start_signal_process(k),
            )
            btn_start.pack(side="left", padx=2)

            btn_stop = ctk.CTkButton(
                btn_frame_p,
                text="■",
                width=32,
                height=28,
                fg_color="#d9534f",
                hover_color="#c9302c",
                state="disabled",
                command=lambda k=key: self.stop_signal_process(k),
            )
            btn_stop.pack(side="left", padx=2)

            console = ctk.CTkTextbox(panel, font=("Consolas", 11), state="disabled", wrap="word")
            console.pack(fill="both", expand=True, padx=10, pady=(2, 8))

            self.signal_procs[key] = {
                "name": name,
                "color": color,
                "proc": None,
                "logs": [],
                "console": console,
                "btn_start": btn_start,
                "btn_stop": btn_stop,
                "lbl_pid": lbl_pid,
                "lbl_status": lbl_status,
            }

    def bind_state(self, app_state: Any) -> None:
        """Bind this tab to app state."""
        pass

    def refresh(self) -> None:
        """Refresh tab UI."""
        pass

    def start_signal_process(self, key: str) -> None:
        """Start a signal process by key, delegating to supervisor."""
        try:
            if hasattr(self.app, "start_signal_process"):
                self.app.start_signal_process(key)
            elif hasattr(self.app, "signal_supervisor"):
                profile = ""
                try:
                    profile = self.app.combo_profiles.get()
                except Exception:
                    profile = ""
                self.app.signal_supervisor.start_signal_process(key, profile)
        except Exception as e:
            try:
                self.app.log(f"Signal start error ({key}): {e}")
            except Exception:
                print(f"Signal start error ({key}): {e}")

    def stop_signal_process(self, key: str) -> None:
        """Stop a signal process by key, delegating to supervisor."""
        try:
            if hasattr(self.app, "stop_signal_process"):
                self.app.stop_signal_process(key)
            elif hasattr(self.app, "signal_supervisor"):
                self.app.signal_supervisor.stop_signal_process(key)
        except Exception as e:
            try:
                self.app.log(f"Signal stop error ({key}): {e}")
            except Exception:
                print(f"Signal stop error ({key}): {e}")

    def start_all_signals(self) -> None:
        """Start all signals (non-blocking — supervisor sleeps between starts)."""
        try:
            if hasattr(self.app, "start_all_signals"):
                self.app.start_all_signals()
            elif hasattr(self.app, "signal_supervisor"):
                import threading

                profile = ""
                try:
                    profile = self.app.combo_profiles.get()
                except Exception:
                    profile = ""
                threading.Thread(
                    target=self.app.signal_supervisor.start_all_signals,
                    args=(profile,),
                    daemon=True,
                ).start()
        except Exception as e:
            try:
                self.app.log(f"Start all signals error: {e}")
            except Exception:
                print(f"Start all signals error: {e}")

    def stop_all_signals(self) -> None:
        """Stop all signals."""
        try:
            if hasattr(self.app, "stop_all_signals"):
                self.app.stop_all_signals()
            elif hasattr(self.app, "signal_supervisor"):
                self.app.signal_supervisor.stop_all_signals()
        except Exception as e:
            try:
                self.app.log(f"Stop all signals error: {e}")
            except Exception:
                print(f"Stop all signals error: {e}")
