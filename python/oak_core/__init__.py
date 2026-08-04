# -*- coding: utf-8 -*-
"""oak-core — Python sidecar for the OAK Tauri desktop app.

Runs as a child process managed by the Rust shell.  Speaks JSON Lines
protocol over stdin/stdout (never localhost HTTP — see Edit prompt.txt §3).

Modes:
    oak-core.exe supervisor
    oak-core.exe profile-worker --profile <name>
"""
from .version import APP_NAME, APP_VERSION, PROTOCOL_VERSION

__all__ = ["APP_NAME", "APP_VERSION", "PROTOCOL_VERSION"]
