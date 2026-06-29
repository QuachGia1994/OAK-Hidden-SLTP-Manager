# -*- coding: utf-8 -*-
"""Shared utilities for OAK SLTP system."""
import json
import os
import urllib.request
import urllib.parse


# --- Telegram ---
def send_telegram_raw(token, chat_id, text, parse_mode="Markdown"):
    """Send message via Telegram Bot API (POST)."""
    msg = urllib.parse.quote(text, safe="*")
    url = (
        f"https://api.telegram.org/bot{token}/sendMessage"
        f"?chat_id={chat_id}&text={msg}&parse_mode={parse_mode}"
    )
    with urllib.request.urlopen(url, timeout=15) as resp:
        return resp.read()


# --- JSON ---
def load_json_file(path, default=None):
    """Read JSON file safely, return default on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def save_json_file(path, data):
    """Write JSON file safely."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# --- Signal helpers ---
SIGNAL_ICONS = {"BUY": ("Mua", "\U0001f7e2"), "SELL": ("Bán", "\U0001f534")}
VN_DIR = {"TANG": "Tăng", "GIAM": "Giảm", "DOJI": "Doji"}


def get_signal_icon(sig):
    """Return (icon_text, emoji) for a signal."""
    return SIGNAL_ICONS.get(sig, ("Chờ", "\u26aa"))


def vn_direction(d):
    """Convert TANG/GIAM/DOJI to Vietnamese label."""
    return VN_DIR.get(d, d)
