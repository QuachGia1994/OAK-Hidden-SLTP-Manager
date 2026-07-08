# -*- coding: utf-8 -*-
"""BaseTab - base class for all tabs in OAK Hidden SLTP Manager."""
from typing import Any, Callable, Optional


class BaseTab:
    """Base class for all UI tabs."""

    def __init__(self, app: Any):
        self.app = app
        self.ui_elements = {}

    def mount(self, parent: Any) -> None:
        """Mount this tab to a parent widget."""
        raise NotImplementedError("Subclasses must implement mount()")

    def bind_state(self, app_state: Any) -> None:
        """Bind tab to app state and subscribe to events."""
        pass

    def refresh(self) -> None:
        """Refresh the tab's UI."""
        pass

    def add_ui_element(self, key: str, widget: Any) -> None:
        """Register a UI element for language updates."""
        self.ui_elements[key] = widget
        if hasattr(self.app, 'add_ui_element'):
            self.app.add_ui_element(key, widget)
