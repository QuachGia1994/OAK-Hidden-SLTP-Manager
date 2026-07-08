# -*- coding: utf-8 -*-
"""Centralized Telegram API client with error classification and retry."""
import json
import time
import urllib.request
import urllib.parse
from oak_logger import setup_logger

log = setup_logger("telegram_client")

# Error classification
ERROR_CLASSES = {
    401: "token_invalid",
    400: "chat_not_found",
    429: "rate_limited",
    502: "bad_gateway",
    503: "service_unavailable",
}


def classify_error(status_code):
    """Classify HTTP status code into error category."""
    if status_code in ERROR_CLASSES:
        return ERROR_CLASSES[status_code]
    if 500 <= status_code < 600:
        return "server_error"
    if 400 <= status_code < 500:
        return "client_error"
    return "unknown"


def telegram_get_me(token):
    """Test Telegram Bot API connection via getMe.

    Returns (ok, bot_name_or_error).
    """
    if not token:
        return False, "no_token"
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("ok"):
                bot_name = data.get("result", {}).get("username", "")
                return True, bot_name
            return False, "api_error"
    except urllib.error.HTTPError as e:
        return False, classify_error(e.code)
    except Exception as e:
        return False, "network_error"


def telegram_send_message(token, chat_id, text, parse_mode="Markdown"):
    """Send message via Telegram Bot API with error classification.

    Returns (ok, error_category_or_None).
    """
    if not token or not chat_id:
        return False, "not_configured"
    try:
        clean = text.replace("*", "").replace("_", "")
        if len(clean) > 4000:
            clean = clean[:4000] + "\n\n...[Cut]..."
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({
            "chat_id": str(chat_id),
            "text": clean,
            "parse_mode": parse_mode,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, None
    except urllib.error.HTTPError as e:
        return False, classify_error(e.code)
    except Exception as e:
        return False, "network_error"
