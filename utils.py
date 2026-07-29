# -*- coding: utf-8 -*-
"""Shared utilities for OAK SLTP system."""
import json
import os
import urllib.error
import urllib.request
import urllib.parse
from datetime import date, datetime


# --- Telegram ---
def send_telegram_raw(token, chat_id, text, parse_mode="Markdown"):
    """Send message via Telegram Bot API (POST)."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def send_telegram_with_keyboard(token, chat_id, text, inline_keyboard, parse_mode=None):
    """Send message with inline keyboard via Telegram Bot API.

    reply_markup must be an object in the JSON body (not a double-encoded string).
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = {
        "chat_id": str(chat_id),
        "text": text,
        "reply_markup": {"inline_keyboard": inline_keyboard},
    }
    if parse_mode:
        body["parse_mode"] = parse_mode
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        raise urllib.error.HTTPError(
            e.url, e.code, f"{e.reason} | {body[:300]}", e.hdrs, e.fp
        ) from e


def answer_callback_query(token, callback_query_id, text=None):
    """Answer a callback query to dismiss the loading spinner."""
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload = json.dumps({
        "callback_query_id": callback_query_id,
        **({"text": text} if text else {}),
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
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


# --- Process command construction ---
SIGNAL_SCRIPT_MAP = {
    "signal_bot": "mt5_signal_bot.py",
    "mt_server": "mt4_mt5_server.py",
    "mimo_bot": "mimo_bot.py",
    "mimo_worker": "mimo_worker.py",
    "factcheck_worker": "factcheck_worker.py",
}

FROZEN_MODE_FLAGS = {
    "signal_bot": "--signal-bot",
    "mt_server": "--mt-server",
    "mimo_bot": "--mimo-bot",
    "mimo_worker": "--mimo-worker",
    "factcheck_worker": "--factcheck-worker",
}
FROZEN_SUPPORTED_KEYS = tuple(FROZEN_MODE_FLAGS)


class UnsupportedFrozenProcessError(Exception):
    """Raised when a frozen build is asked to start a process it can't run standalone."""


def build_signal_process_cmd(key, profile, frozen, executable, script_map=None):
    """Build the subprocess command list for a signal process.

    Mirrors the exact command construction used by
    OAK_Hidden_SLTP_Manager.start_signal_process, so it can be unit tested
    without importing the GUI (customtkinter/MetaTrader5) module.

    - frozen + supported key: [executable, "--worker-flag", ("--profile", profile)?]
    - dev + signal_bot: [executable, "-u", script, ("--profile", profile)?]
    - dev + other key: [executable, "-u", script]
    """
    script_map = script_map or SIGNAL_SCRIPT_MAP
    script = script_map.get(key, "")

    if frozen:
        if key not in FROZEN_SUPPORTED_KEYS:
            raise UnsupportedFrozenProcessError(key)
        cmd = [executable, FROZEN_MODE_FLAGS[key]]
        if key == "signal_bot" and profile:
            cmd.extend(["--profile", profile])
        return cmd

    cmd = [executable, "-u", script]
    if key == "signal_bot" and profile:
        cmd.extend(["--profile", profile])
    return cmd


# --- Telegram backoff/circuit breaker ---
def compute_telegram_backoff(consecutive_fails):
    """Return (sleep_seconds, should_log_degraded).

    Backoff schedule:
    1-2 fails: 10s
    3-9 fails: 60s
    10+ fails: 300s
    """
    try:
        n = int(consecutive_fails)
    except Exception:
        n = 1

    if n < 3:
        return 10, False
    if n < 10:
        return 60, False
    return 300, n == 10


# --- Signal helpers ---
SIGNAL_ICONS = {
    "BUY": ("Mua", "\U0001f7e2"),
    "SELL": ("Bán", "\U0001f534"),
    "SW": ("Sideway", "\U0001f7e1"),
    "BT": ("Bình Thường", "\u26aa"),
    "WAIT": ("Chờ", "\u23f3"),
}
VN_DIR = {"TANG": "Tăng", "GIAM": "Giảm", "DOJI": "Doji"}


def get_signal_icon(sig):
    """Return (icon_text, emoji) for a signal."""
    return SIGNAL_ICONS.get(sig, ("Chờ", "\u26aa"))


def vn_direction(d):
    """Convert TANG/GIAM/DOJI to Vietnamese label."""
    return VN_DIR.get(d, d)


ACTIVE_SIGNAL_HOURS = frozenset({3, 7, 9, 12, 14, 16})
ACTIVE_SIGNAL_LOGIC_VERSION = 63


def get_latest_display_signal(signals, today=None, allow_fallback=True):
    """Pick the newest actionable active-slot signal for the desktop dashboard."""
    if not signals:
        return None
    if today is None:
        today = datetime.now().date().isoformat()

    def _hour_key(row):
        try:
            return int(row.get("hour") or 0)
        except (TypeError, ValueError):
            return 0

    def _is_actionable(row):
        if not isinstance(row, dict) or row.get("deactivated") is True:
            return False
        try:
            hour = int(row.get("hour"))
            logic_version = int(row.get("logic_version"))
            trading_date = date.fromisoformat(str(row.get("date")))
        except (TypeError, ValueError):
            return False
        if hour not in ACTIVE_SIGNAL_HOURS:
            return False
        if logic_version < ACTIVE_SIGNAL_LOGIC_VERSION:
            return False
        if hour == 3 and trading_date.weekday() == 3:
            return False
        pair_dirs = row.get("pair_dirs")
        if not isinstance(pair_dirs, dict):
            return False
        return pair_dirs.get("XAUUSD") in ("BUY", "SELL")

    today_rows = [s for s in signals if s.get("date") == today and _is_actionable(s)]
    if today_rows:
        return max(today_rows, key=_hour_key)

    if not allow_fallback:
        return None

    dated = [s for s in signals if _is_actionable(s)]
    if not dated:
        return None
    return max(dated, key=lambda s: (s.get("date") or "", _hour_key(s)))
