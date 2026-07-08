# -*- coding: utf-8 -*-
"""AppState - manages shared state and events for the desktop application."""
from typing import Any, Callable, Dict, List, Optional
import threading


class AppState:
    """Manages shared state and event subscriptions for cross-tab communication."""

    def __init__(self):
        self._lock = threading.RLock()
        self._subscribers: Dict[str, List[Callable]] = {}
        self._state: Dict[str, Any] = {
            "settings": {},
            "profiles": {},
            "selected_profile": None,
            "running_profile": None,
            "theme": "light",
            "lang": "VN",
            "ghost_mode_active": False,
            "signal_procs": {},
            "workers": {},
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the state."""
        with self._lock:
            return self._state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in the state and notify subscribers."""
        with self._lock:
            old_value = self._state.get(key)
            if old_value == value:
                return
            self._state[key] = value
        self._notify(key, old_value, value)

    def subscribe(self, event_name: str, callback: Callable) -> None:
        """Subscribe a callback to state changes for a specific key."""
        with self._lock:
            if event_name not in self._subscribers:
                self._subscribers[event_name] = []
            self._subscribers[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        """Unsubscribe a callback from state changes."""
        with self._lock:
            if event_name in self._subscribers:
                try:
                    self._subscribers[event_name].remove(callback)
                except ValueError:
                    pass

    def _notify(self, key: str, old_value: Any, new_value: Any) -> None:
        """Notify all subscribers of a state change."""
        callbacks = []
        with self._lock:
            if key in self._subscribers:
                callbacks = list(self._subscribers[key])
        
        for callback in callbacks:
            try:
                callback(key, old_value, new_value)
            except Exception:
                pass
