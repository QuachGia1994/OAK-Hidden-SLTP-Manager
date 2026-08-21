# -*- coding: utf-8 -*-
"""Telegram receiver for ROBOT SLTP Tauri.

The bot does one job: authenticated Telegram text -> tele_inbox.json.
Trading, scheduling, profile scoping and MT5 mutations remain inside the worker.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

try:
    import telebot
except ImportError:
    print("[ERROR] pyTelegramBotAPI is required", file=sys.stderr)
    raise SystemExit(2)

from domain.file_lock import FileLock
from domain.json_io import load_json
from domain.telegram_backoff import compute_telegram_backoff
from domain.telegram_inbox import append_inbox_update

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "config.json"
PROFILES_FILE = ROOT / "profiles.json"
INBOX_FILE = ROOT / "tele_inbox.json"
PID_FILE = ROOT / "oak_enginecore.lock"
LOCK_FILE = ROOT / "oak_enginecore.singleton.lock"
_RECEIVER_LOCK: FileLock | None = None


def _load_json(path: Path, default):
    return load_json(path, default)


def _config() -> tuple[str, int]:
    cfg = _load_json(CONFIG_FILE, {})
    token = str(cfg.get("telegram_token") or "").strip()
    try:
        admin_id = int(cfg.get("telegram_chat_id") or 0)
    except (TypeError, ValueError):
        admin_id = 0
    return token, admin_id


try:
    BOT_TOKEN, ADMIN_CHAT_ID = _config()
except (OSError, ValueError) as exc:
    print(f"[ERROR] Cannot read config.json: {type(exc).__name__}", file=sys.stderr)
    raise SystemExit(2) from exc
if not BOT_TOKEN:
    print("[ERROR] Missing telegram_token in config.json", file=sys.stderr)
    raise SystemExit(2)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown", validate_token=True)


def _authorized(message) -> bool:
    return bool(ADMIN_CHAT_ID and int(message.chat.id) == ADMIN_CHAT_ID)


def _deny(message) -> None:
    try:
        bot.reply_to(message, "⚠️ Không có quyền truy cập.")
    except Exception:
        pass


def _forward(message) -> None:
    if not _authorized(message):
        _deny(message)
        return
    text = str(message.text or "").strip()
    if not text:
        return
    try:
        update = append_inbox_update(INBOX_FILE, text, message.chat.id, source="Telegram")
        bot.reply_to(message, f"✅ Đã nhận lệnh `#{update['update_id']}`")
    except Exception as exc:
        bot.reply_to(message, f"❌ Không ghi được lệnh: `{exc}`")


@bot.message_handler(commands=["start", "help"])
def cmd_start(message):
    if not _authorized(message):
        _deny(message)
        return
    bot.reply_to(
        message,
        "🤖 *ROBOT SLTP Remote*\n"
        "Gửi trực tiếp lệnh Buy/Sell, /pending, /closeall, /modify hoặc /del.\n"
        "Dùng `/profiles` để xem profile và `/myid` để xem Chat ID.",
    )


@bot.message_handler(commands=["myid"])
def cmd_myid(message):
    bot.reply_to(message, f"Chat ID: `{message.chat.id}`")


@bot.message_handler(commands=["profiles"])
def cmd_profiles(message):
    if not _authorized(message):
        _deny(message)
        return
    profiles = _load_json(PROFILES_FILE, {})
    if not isinstance(profiles, dict) or not profiles:
        bot.reply_to(message, "Không có profile.")
        return
    lines = ["📋 *Profiles*"]
    for name, cfg in profiles.items():
        if not isinstance(cfg, dict):
            continue
        lines.append(
            f"• *{name}* · SL {cfg.get('sl', '?')} · TP {cfg.get('tp', '?')}"
        )
    bot.reply_to(message, "\n".join(lines))


@bot.message_handler(func=lambda message: True, content_types=["text"])
def handle_text(message):
    _forward(message)


def _pid_is_live(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    output = (result.stdout or "").lower()
    return str(pid) in output and "python" in output


def _acquire_lock() -> bool:
    global _RECEIVER_LOCK
    # Migration guard for a receiver started before the OS-lock implementation.
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            old_pid = 0
        if old_pid != os.getpid() and _pid_is_live(old_pid):
            print(f"[EXIT] Telegram receiver already running (PID {old_pid})")
            return False

    guard = FileLock(str(LOCK_FILE), timeout=0.0)
    acquired = guard.__enter__()
    if acquired is None:
        print("[EXIT] Telegram receiver already running or lock unavailable")
        return False
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except OSError as exc:
        acquired.__exit__(None, None, None)
        print(f"[ERROR] Cannot write receiver PID file: {exc}", file=sys.stderr)
        return False
    _RECEIVER_LOCK = acquired
    return True


def _release_lock() -> None:
    global _RECEIVER_LOCK
    guard = _RECEIVER_LOCK
    _RECEIVER_LOCK = None
    try:
        if PID_FILE.exists() and PID_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
            PID_FILE.unlink()
    except OSError:
        pass
    if guard is not None:
        guard.__exit__(None, None, None)


def _active_webhook_url() -> str:
    """Return the configured Telegram webhook URL, if any.

    Cloud webhook ownership is authoritative. The desktop fallback receiver must
    never delete or steal an active webhook merely because the app was opened.
    """
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
        payload = json.loads(urllib.request.urlopen(url, timeout=10).read().decode("utf-8"))
        if payload.get("ok") and isinstance(payload.get("result"), dict):
            return str(payload["result"].get("url") or "").strip()
    except Exception as exc:
        print(f"[WARN] getWebhookInfo failed: {exc}")
    return ""


def main() -> int:
    if not ADMIN_CHAT_ID:
        print("[ERROR] Missing telegram_chat_id in config.json", file=sys.stderr)
        return 2
    webhook_url = _active_webhook_url()
    if webhook_url:
        print(f"[EXIT] Telegram cloud webhook active: {webhook_url}", flush=True)
        return 0
    if not _acquire_lock():
        return 0
    print(f"[OAK EngineCore] Telegram receiver ready · PID {os.getpid()}", flush=True)
    failures = 0
    try:
        while True:
            try:
                # Do not discard messages sent while the receiver was offline.
                bot.polling(
                    none_stop=True,
                    timeout=20,
                    long_polling_timeout=20,
                    skip_pending=False,
                )
                failures = 0
            except KeyboardInterrupt:
                return 0
            except Exception as exc:
                failures += 1
                sleep_seconds, degraded = compute_telegram_backoff(failures)
                if failures < 10 or degraded:
                    print(
                        f"[TG] polling error #{failures}: {exc}; retry {sleep_seconds}s",
                        flush=True,
                    )
                time.sleep(sleep_seconds)
    finally:
        _release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
