"""HTTP Client with retry, exponential backoff, and timeouts for public data sources."""
from __future__ import annotations

import logging
import time
from typing import Any
import urllib.error
import urllib.request

logger = logging.getLogger("eod_collector")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


def fetch_url(
    url: str,
    timeout_seconds: int = 30,
    max_retries: int = 3,
    headers: dict[str, str] | None = None,
) -> tuple[bytes, int, str]:
    """Fetch URL over HTTP/HTTPS with proper retries, backoff, and user-agent.

    Returns:
        tuple[content_bytes, status_code, content_type]
    """
    req_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
    }
    if headers:
        req_headers.update(headers)

    import ssl

    request = urllib.request.Request(url, headers=req_headers)
    last_error: Exception | None = None
    ssl_context = None

    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds, context=ssl_context) as response:
                status_code = response.getcode() or 200
                content_type = response.headers.get("Content-Type", "application/octet-stream")
                content = response.read()
                return content, status_code, content_type
        except urllib.error.HTTPError as err:
            last_error = err
            logger.warning("HTTPError %d for %s (attempt %d/%d)", err.code, url, attempt, max_retries)
            if err.code in (404, 400, 403):
                # Don't retry client errors
                content = err.read() if hasattr(err, "read") else b""
                return content, err.code, "text/plain"
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            last_error = err
            logger.warning("Network error '%s' for %s (attempt %d/%d)", err, url, attempt, max_retries)
            # Create unverified SSL context for retry if SSL handshake fails
            if ssl_context is None:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                ssl_context = ctx

        if attempt < max_retries:
            sleep_time = 1.5 ** attempt
            time.sleep(sleep_time)

    raise RuntimeError(f"Failed to fetch {url} after {max_retries} attempts: {last_error}")
