# -*- coding: utf-8 -*-
"""ProfilesTab - manages the Profiles tab UI."""
import customtkinter as ctk
from typing import Any
from .base_tab import BaseTab


class ProfilesTab(BaseTab):
    """Tab for managing profiles."""

    def __init__(self, app: Any):
        super().__init__(app)
        self.entries = {}
        self.lbl_active_profile = None
        self.lbl_unsaved = None

    def mount(self, parent: Any) -> None:
        """Mount the Profiles tab UI."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True)

        # Left list
        self.list_frame = ctk.CTkScrollableFrame(frame, width=220, label_text="Danh sách")
        self.list_frame.pack(side="left", fill="y", padx=(0, 20))

        # Right panel
        self.right_panel = ctk.CTkFrame(frame, fg_color="transparent")
        self.right_panel.pack(side="right", fill="both", expand=True)

        # Scrollable form
        self.form_scroll = ctk.CTkScrollableFrame(self.right_panel, label_text="Cấu hình")
        self.form_scroll.pack(side="top", fill="both", expand=True, pady=(0, 10))
        self.form_scroll.grid_columnconfigure(1, weight=1)

        # Checkboxes for Balance SL/TP
        self.chk_balance = ctk.CTkCheckBox(self.form_scroll, text="Sử dụng Balance SL/TP")
        self.chk_balance.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.chk_visible_sltp = ctk.CTkCheckBox(self.form_scroll, text="SL/TP Hiển thị")
        self.chk_visible_sltp.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # Input fields
        fields = [
            ("name", "Tên"), ("path", "Đường dẫn MT5"), ("magic", "Magic Number"),
            ("symbol", "Cặp tiền"), ("sl", "SL"), ("tp", "TP"),
            ("gold_sl", "Gold SL"), ("gold_tp", "Gold TP"),
            ("balance_sl_pct", "Balance SL %"), ("balance_tp_pct", "Balance TP %"),
            ("partial_r", "Partial R"), ("partial_pct", "Partial %"),
            ("auto_be", "Auto BE"),
            ("tele_token", "Telegram Token"), ("tele_chat", "Telegram Chat ID"),
            ("tele_admin", "Telegram Admin")
        ]

        self.entries = {}
        for i, (key, label) in enumerate(fields):
            row_idx = i + 1
            lbl = ctk.CTkLabel(self.form_scroll, text=label)
            lbl.grid(row=row_idx, column=0, padx=10, pady=5, sticky="w")

            ent = ctk.CTkEntry(self.form_scroll, show="•" if key == "tele_token" else "")
            ent.grid(row=row_idx, column=1, padx=10, pady=5, sticky="ew")
            self.entries[key] = ent

        # Buttons at bottom
        btn_box = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        btn_box.pack(side="bottom", fill="x", pady=10)

        self.lbl_active_profile = ctk.CTkLabel(btn_box, text="", font=ctk.CTkFont(size=11, weight="bold"), text_color="#66bb6a")
        self.lbl_active_profile.pack(side="left", padx=10)

        self.lbl_unsaved = ctk.CTkLabel(btn_box, text="", font=ctk.CTkFont(size=10), text_color="#ffb74d")
        self.lbl_unsaved.pack(side="left", padx=5)

        self.btn_save = ctk.CTkButton(btn_box, text="Lưu", command=self.save_profile)
        self.btn_save.pack(side="left", padx=10, expand=True)

        self.btn_delete = ctk.CTkButton(btn_box, text="Xóa", fg_color="red", command=self.delete_profile)
        self.btn_delete.pack(side="left", padx=10, expand=True)

        self.btn_add = ctk.CTkButton(btn_box, text="Thêm mới", fg_color="gray", command=self.clear_form)
        self.btn_add.pack(side="left", padx=10, expand=True)

    def bind_state(self, app_state: Any) -> None:
        """Bind to app state."""
        pass

    def refresh(self) -> None:
        """Refresh profile list."""
        if hasattr(self.app, 'refresh_profile_list'):
            self.app.refresh_profile_list()

    def save_profile(self) -> None:
        """Save profile, delegating to app."""
        if hasattr(self.app, 'save_profile'):
            self.app.save_profile()

    def delete_profile(self) -> None:
        """Delete profile, delegating to app."""
        if hasattr(self.app, 'delete_profile'):
            self.app.delete_profile()

    def clear_form(self) -> None:
        """Clear form, delegating to app."""
        if hasattr(self.app, 'clear_form'):
            self.app.clear_form()
        else:
            # Default behavior if app doesn't have clear_form yet
            for ent in self.entries.values():
                ent.delete(0, "end")
            self.chk_balance.deselect()
            self.chk_visible_sltp.deselect()
