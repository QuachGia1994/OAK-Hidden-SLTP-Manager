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

from domain.telegram_backoff import compute_telegram_backoff
from domain.telegram_inbox import append_inbox_update

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "config.json"
PROFILES_FILE = ROOT / "profiles.json"
INBOX_FILE = ROOT / "tele_inbox.json"
LOCK_FILE = ROOT / "mimo_bot.lock"


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return default


def _config() -> tuple[str, int]:
    cfg = _load_json(CONFIG_FILE, {})
    token = str(cfg.get("telegram_token") or "").strip()
    try:
        admin_id = int(cfg.get("telegram_chat_id") or 0)
    except (TypeError, ValueError):
        admin_id = 0
    return token, admin_id


BOT_TOKEN, ADMIN_CHAT_ID = _config()
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
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            old_pid = 0
        if old_pid != os.getpid() and _pid_is_live(old_pid):
            print(f"[EXIT] Telegram receiver already running (PID {old_pid})")
            return False
        try:
            LOCK_FILE.unlink()
        except OSError:
            pass
    try:
        LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except OSError as exc:
        print(f"[WARN] Cannot create receiver lock: {exc}")
        return True


def _release_lock() -> None:
    try:
        if LOCK_FILE.exists() and LOCK_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
            LOCK_FILE.unlink()
    except OSError:
        pass


def _drop_webhook() -> None:
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=false"
        urllib.request.urlopen(url, timeout=10).read()
    except Exception as exc:
        print(f"[WARN] deleteWebhook failed: {exc}")


def main() -> int:
    if not ADMIN_CHAT_ID:
        print("[ERROR] Missing telegram_chat_id in config.json", file=sys.stderr)
        return 2
    if not _acquire_lock():
        return 0
    _drop_webhook()
    print(f"[TG] Receiver ready · PID {os.getpid()}", flush=True)
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
