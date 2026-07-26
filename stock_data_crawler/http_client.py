"""HTTP client with hostname allowlist, retry, and timeout for stock data crawling."""
from __future__ import annotations

import logging
import re
import ssl
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse
from typing import Any

logger = logging.getLogger("stock_data_crawler")

ALLOWED_HOSTS = {
    "congcu.cafef.vn",
    "s.cafef.vn",
    "www.vsd.vn",
    "www.hnx.vn",
    "hnx.vn",
}

SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,12}$")
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB
TIMEOUT = 15
MAX_RETRIES = 2
RETRY_DELAY = 2

_NO_VERIFY_SSL = ssl.create_default_context()
_NO_VERIFY_SSL.check_hostname = False
_NO_VERIFY_SSL.verify_mode = ssl.CERT_NONE


def validate_symbol(symbol: str) -> bool:
    return bool(SYMBOL_RE.match(symbol))


def _is_allowed(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host in ALLOWED_HOSTS


def fetch_html(url: str) -> str | None:
    """Fetch HTML from an allowed URL with retry and timeout.

    Returns HTML string on success, None on failure.
    """
    if not _is_allowed(url):
        logger.warning("Blocked non-allowed host: %s", url)
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    }

    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=TIMEOUT, context=_NO_VERIFY_SSL)
            data = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                logger.warning("Response too large from %s: %d bytes", url, len(data))
                return None
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                logger.warning("Non-HTML response from %s: %s", url, content_type)
                return None
            return data.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            logger.warning("HTTP %d from %s (attempt %d)", exc.code, url, attempt + 1)
            if exc.code == 404:
                return None
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            logger.warning("Fetch error %s (attempt %d): %s", url, attempt + 1, exc)
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY * (attempt + 1))
    return None


def fetch_json(url: str) -> Any | None:
    """Fetch JSON from an allowed URL."""
    if not _is_allowed(url):
        logger.warning("Blocked non-allowed host: %s", url)
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json,*/*",
    }

    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=TIMEOUT, context=_NO_VERIFY_SSL)
            data = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                return None
            import json
            return json.loads(data.decode("utf-8", errors="replace"))
        except Exception as exc:
            logger.warning("JSON fetch error %s (attempt %d): %s", url, attempt + 1, exc)
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY * (attempt + 1))
    return None
