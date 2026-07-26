"""HTTP client with hostname allowlist, redirect guard, retry, and timeout for stock data crawling."""
from __future__ import annotations

import html
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
    "cafef.vn",
    "www.cafef.vn",
    "www.vsd.vn",
    "www.hnx.vn",
    "hnx.vn",
    "congbo.ssc.gov.vn",
    # IR websites (with and without www, redirect targets)
    "www.hoaphat.com.vn",
    "www.vinamilk.com.vn",
    "www.fpt.com.vn",
    "fpt.com",
    "www.vietcombank.com.vn",
    "www.techcombank.com.vn",
    "www.thegioididong.com",
    "www.thegioididong.com.vn",
    "www.msn.com.vn",
    "www.ssi.com.vn",
    "www.bidv.com.vn",
    "bidv.com.vn",
    "www.vietinbank.vn",
    "www.transimex.com.vn",
    "www.vingroup.vn",
    "www.pvgas.com.vn",
    "www.petrolimex.com.vn",
    "www.sabeco.com.vn",
    "www.baoviet.com.vn",
    "www.vietjetair.com",
    "www.vincomretail.com",
    "www.pnj.com.vn",
    "www.hdbank.com.vn",
}

SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,12}$")
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB
TIMEOUT = 15
MAX_RETRIES = 2
RETRY_DELAY = 2


def validate_symbol(symbol: str) -> bool:
    return bool(SYMBOL_RE.match(symbol))


def _is_allowed(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host in ALLOWED_HOSTS


class _RedirectGuard(urllib.request.HTTPRedirectHandler):
    """Block redirects to hosts outside the allowlist."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _is_allowed(newurl):
            logger.warning("Blocked redirect to non-allowed host: %s -> %s", req.get_full_url(), newurl)
            raise urllib.error.HTTPError(
                newurl, code, "Redirect blocked: non-allowed host", headers, fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# Vietnamese hosts that may have SSL certificate issues on some machines
_VN_SSL_BYPASS_HOSTS = {
    "www.hnx.vn",
    "hnx.vn",
    "www.vsd.vn",
    "congbo.ssc.gov.vn",
    "www.transimex.com.vn",
    "www.techcombank.com.vn",
}


def _build_opener(url: str) -> urllib.request.OpenerDirector:
    """Build a URL opener with SSL verification and redirect guard.

    Disables SSL verification for known Vietnamese hosts that have
    certificate issues on some machines.
    """
    host = urlparse(url).hostname or ""
    if host in _VN_SSL_BYPASS_HOSTS:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
    else:
        ssl_ctx = ssl.create_default_context()
    handlers = [
        urllib.request.HTTPSHandler(context=ssl_ctx),
        _RedirectGuard(),
    ]
    return urllib.request.build_opener(*handlers)


def escape_html_text(text: str) -> str:
    """Escape HTML entities in parsed text content."""
    return html.escape(text, quote=False)


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

    opener = _build_opener(url)
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = opener.open(req, timeout=TIMEOUT)
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

    opener = _build_opener(url)
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = opener.open(req, timeout=TIMEOUT)
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
