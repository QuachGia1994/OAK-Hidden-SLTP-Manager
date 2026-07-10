# -*- coding: utf-8 -*-
"""Centralized Telegram API client with error classification and retry."""
import json
import random
import time
import urllib.error
import urllib.request
import urllib.parse
from oak_logger import setup_logger

log = setup_logger("telegram_client")

# Error classification — 400 is NOT always chat_not_found
ERROR_CLASSES = {
    401: "token_invalid",
    429: "rate_limited",
    502: "bad_gateway",
    503: "service_unavailable",
}


def classify_error(status_code, body: str = ""):
    """Classify HTTP status + response body into error category."""
    text = (body or "").lower()
    if status_code == 400:
        if "inline keyboard" in text or "reply_markup" in text or "button" in text:
            return "bad_keyboard"
        if "can't parse entities" in text or "parse entities" in text or "markdown" in text:
            return "bad_entities"
        if "chat not found" in text or "chat_id" in text:
            return "chat_not_found"
        if "message is not modified" in text:
            return "message_not_modified"
        return "bad_request"
    if status_code in ERROR_CLASSES:
        return ERROR_CLASSES[status_code]
    if 500 <= status_code < 600:
        return "server_error"
    if 400 <= status_code < 500:
        return f"client_error:{status_code}"
    return "unknown"


def telegram_get_me(token, *, retries: int = 2, timeout: float = 8.0):
    """Test Telegram Bot API connection via getMe.

    Retries once/twice with short jitter on network failures.
    Returns (ok, bot_name_or_error).
    """
    if not token:
        return False, "no_token"
    last_err = "network_error"
    attempts = max(1, int(retries) + 1)
    for i in range(attempts):
        try:
            url = f"https://api.telegram.org/bot{token}/getMe"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
                if data.get("ok"):
                    bot_name = data.get("result", {}).get("username", "")
                    return True, bot_name
                last_err = "api_error"
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()
                log.warning(f"Telegram getMe error {e.code}: {body[:300]}")
            except Exception:
                pass
            last_err = classify_error(e.code, body)
            # No retry on auth/client errors
            if e.code in (400, 401, 403, 404):
                return False, last_err
        except Exception as e:
            log.warning(f"Telegram getMe network error: {e}")
            last_err = "network_error"
        if i + 1 < attempts:
            time.sleep(0.35 + random.random() * 0.4)
    return False, last_err


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
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
            log.warning("Telegram sendMessage HTTP %s: %s", e.code, body[:300])
        except Exception:
            pass
        return False, classify_error(e.code, body)
    except Exception as e:
        return False, "network_error"
