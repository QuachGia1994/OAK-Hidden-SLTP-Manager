# -*- coding: utf-8 -*-
"""Telegram bot communication service."""
import json
import time
import urllib.request
import urllib.parse
import re
from oak_logger import setup_logger

log = setup_logger("telegram")


class TelegramService:
    """Handles Telegram API communication (send + poll)."""

    def __init__(self, token, chat_id):
        self._token = token
        self._chat_id = str(chat_id)
        self._last_update_id = 0

    @property
    def is_configured(self):
        return bool(self._token and self._chat_id)

    def send(self, text, parse_mode="Markdown"):
        """Send a message via Telegram Bot API."""
        if not self.is_configured:
            return None
        try:
            clean = re.sub(r"<c=#[A-Fa-f0-9]{6}>", "", text)
            clean = clean.replace("</c>", "")
            if len(clean) > 4000:
                clean = clean[:4000] + "\n\n...[Cắt bột]..."
            url = f"https://api.telegram.org/bot{self._token}/sendMessage"
            payload = json.dumps({
                "chat_id": self._chat_id,
                "text": clean,
                "parse_mode": parse_mode,
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read()
        except Exception as e:
            log.warning("Telegram send error: %s", e)
            return None

    def send_with_keyboard(self, text, inline_keyboard, parse_mode="Markdown"):
        """Send a message with inline keyboard."""
        if not self.is_configured:
            return None
        try:
            url = f"https://api.telegram.org/bot{self._token}/sendMessage"
            payload = json.dumps({
                "chat_id": self._chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "reply_markup": {"inline_keyboard": inline_keyboard},
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            log.warning("Telegram keyboard send error: %s", e)
            return None

    def poll_updates(self, timeout=0):
        """Poll for new updates from Telegram."""
        if not self.is_configured:
            return []
        try:
            url = f"https://api.telegram.org/bot{self._token}/getUpdates?offset={self._last_update_id}&timeout={timeout}"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                if data.get("ok") and data.get("result"):
                    updates = data["result"]
                    if updates:
                        self._last_update_id = max(u["update_id"] for u in updates) + 1
                    return updates
        except Exception as e:
            log.warning("Telegram poll error: %s", e)
        return []
