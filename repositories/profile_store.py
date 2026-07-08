# -*- coding: utf-8 -*-
"""ProfileStore - manages loading and saving profiles to JSON."""
import json
from typing import Dict, Any


class ProfileStore:
    """Manages profile persistence to and from JSON file."""

    def __init__(self, config_file: str):
        self.config_file = config_file
        self._profiles: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        """Load profiles from JSON file."""
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                self._profiles = json.load(f)
        except FileNotFoundError:
            self._profiles = {}
        except json.JSONDecodeError:
            self._profiles = {}
        return self._profiles

    def save(self, profiles: Dict[str, Any]) -> None:
        """Save profiles to JSON file."""
        self._profiles = profiles
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=2, ensure_ascii=False)

    def get(self, name: str) -> Dict[str, Any]:
        """Get a single profile by name."""
        return self._profiles.get(name, {})

    @property
    def profiles(self) -> Dict[str, Any]:
        """Get all loaded profiles."""
        return self._profiles
