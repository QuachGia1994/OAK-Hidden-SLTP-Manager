"""Telegram outage backoff shared by the worker and receiver."""


def compute_telegram_backoff(consecutive_fails: int) -> tuple[int, bool]:
    """Return ``(sleep_seconds, should_log_degraded)`` for a fail count."""
    try:
        fails = int(consecutive_fails)
    except (TypeError, ValueError):
        fails = 1
    if fails < 3:
        return 10, False
    if fails < 10:
        return 60, False
    return 300, fails == 10
