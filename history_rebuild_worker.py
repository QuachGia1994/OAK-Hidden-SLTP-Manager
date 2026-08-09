# -*- coding: utf-8 -*-
"""History Rebuild Worker

Automatically refreshes recent history from persisted MT5 market data whenever
new bars arrive.  The worker is deliberately NOT gated on ``feed_connected``
or a live heartbeat: an EA backfill (e.g. Sunday, MT5 closed) persists bars
with no heartbeat, and history must still be rebuilt from those bars.

Integrity contract (same as the rebuild pipeline):
- every WAIT pair carries an explicit ``wait_reasons`` entry;
- a missing-input WAIT (or a missing D snapshot) marks the rebuild incomplete;
- an incomplete rebuild is pushed with ``snapshot_complete=False`` and never
  clears existing history.

The interval is configurable via ``HISTORY_REBUILD_INTERVAL_SECONDS``
(default 180) and the horizon via ``HISTORY_REBUILD_DAYS`` (default 45).
"""
import os
import threading
import time
from datetime import datetime, timezone

HISTORY_REBUILD_INTERVAL_SECONDS = int(
    os.environ.get("HISTORY_REBUILD_INTERVAL_SECONDS", "180")
)
HISTORY_REBUILD_DAYS = int(os.environ.get("HISTORY_REBUILD_DAYS", "45"))


def get_latest_bar_timestamp(store) -> "datetime | None":
    """Return the newest persisted bar arrival time, or None when no bars exist."""
    if store is None:
        return None
    getter = getattr(store, "get_latest_bar_received_at", None)
    if not callable(getter):
        return None
    try:
        latest = getter()
        if latest is None:
            return None
        if getattr(latest, "tzinfo", None) is None:
            latest = latest.replace(tzinfo=timezone.utc)
        return latest.astimezone(timezone.utc)
    except Exception:
        return None


def bars_changed_since(store, last_seen: "datetime | None") -> bool:
    """Return whether persisted bars arrived after ``last_seen``.

    ``last_seen=None`` (first run) always triggers a rebuild so history is
    fresh on startup even when the feed never reported a heartbeat.
    """
    latest = get_latest_bar_timestamp(store)
    if latest is None:
        return False
    if last_seen is None:
        return True
    return latest > last_seen


class HistoryRebuildWorker:
    """Background worker that rebuilds history from persisted MT5 market data."""

    def __init__(self, store=None, rebuild_fn=None, interval_seconds=None, days=None):
        self._store = store
        self._rebuild_fn = rebuild_fn or self._default_rebuild
        self._interval_seconds = int(interval_seconds or HISTORY_REBUILD_INTERVAL_SECONDS)
        self._days = int(days or HISTORY_REBUILD_DAYS)
        self._last_seen = None
        self._last_rebuild_complete = False
        self._last_run_at = None
        self._last_error = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    @staticmethod
    def _default_rebuild(days):
        import mt5_signal_bot
        return mt5_signal_bot._run_market_data_rebuild(days=days)

    def refresh_bars_seen(self):
        """Re-read the persisted bar watermark so a backfill is not missed."""
        latest = get_latest_bar_timestamp(self._store)
        if latest is not None and (self._last_seen is None or latest > self._last_seen):
            self._last_seen = latest

    def should_run(self) -> bool:
        """Run when bars changed since the last seen watermark.

        Explicitly NOT gated on heartbeat/feed_connected state.
        """
        if self._store is None:
            return False
        return bars_changed_since(self._store, self._last_seen)

    def run_once(self) -> bool:
        """Run one rebuild if persisted bars changed. Returns True when it ran."""
        if not self.should_run():
            return False
        with self._lock:
            try:
                self._rebuild_fn(days=self._days)
                rebuild_complete = self._read_rebuild_complete()
                self._last_rebuild_complete = bool(rebuild_complete)
                self._last_error = None
            except Exception as exc:
                self._last_rebuild_complete = False
                self._last_error = str(exc)
                print(f"[HISTORY-WORKER] rebuild error: {type(exc).__name__}: {exc}")
            finally:
                self._last_run_at = datetime.now()
                self.refresh_bars_seen()
        return True

    def _read_rebuild_complete(self):
        try:
            import mt5_signal_bot
            return bool(getattr(mt5_signal_bot, "_LAST_REBUILD_COMPLETE", False))
        except Exception:
            return False

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="history-rebuild-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception as exc:
                print(f"[HISTORY-WORKER] loop error: {type(exc).__name__}: {exc}")
            self._stop.wait(self._interval_seconds)


def start_history_rebuild_worker(store=None) -> HistoryRebuildWorker:
    """Start the background worker with an optional market-data watermark store."""
    worker = HistoryRebuildWorker(store=store)
    worker.start()
    return worker
