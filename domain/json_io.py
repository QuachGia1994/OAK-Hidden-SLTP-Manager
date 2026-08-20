# -*- coding: utf-8 -*-
"""JSON persistence helpers."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time


class JsonStateError(ValueError):
    """Existing JSON state is present but malformed and must not be replaced."""

    def __init__(self, file, error):
        self.file = os.fspath(file)
        self.error = error
        super().__init__(f"Corrupt JSON state {self.file}: {error}")


def resource_path(relative_path):
    """Absolute path to resource (dev + PyInstaller)."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def load_json(file, default=None):
    if default is None:
        default = {}
    if os.path.exists(file):
        try:
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as error:
            raise JsonStateError(file, error) from error
    return default


def _replace_with_retry(temporary_file, target_file, attempts=5):
    """Replace a JSON file after brief Windows sharing violations."""
    for attempt in range(attempts):
        try:
            os.replace(temporary_file, target_file)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.05 * (attempt + 1))


def save_json(file, data):
    target_file = os.path.abspath(file)
    target_directory = os.path.dirname(target_file)
    prefix = f".{os.path.basename(target_file)}."
    descriptor, temporary_file = tempfile.mkstemp(
        dir=target_directory,
        prefix=prefix,
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output_file:
            json.dump(data, output_file, indent=4, ensure_ascii=False)
        _replace_with_retry(temporary_file, target_file)
    finally:
        try:
            os.remove(temporary_file)
        except FileNotFoundError:
            pass
