# -*- coding: utf-8 -*-
"""History Backfill Watch Worker

Polls ``/mt4-feed/coverage``-equivalent persisted-feed coverage and, whenever
coverage improves or becomes complete, automatically rebuilds the previously
missing dates so no operator button press is required.

The worker complements (does not replace) ``history_rebuild_worker``: the
rebuild worker refreshes on any new bar arrival; this worker reacts to the
coverage matrix specifically so a multi-symbol EA backfill that finally fills
the H4/M30/H1 gaps triggers the D-Direction + signal history rebuild for the
dates that were blocked on those inputs.

Policy:
- first run: rebuild only when coverage is already complete;
- later runs: rebuild when coverage became complete or the set of missing
  dates shrank;
- the rebuilt dates are the previously-missing dates (the newly covered ones);
- a full ``_run_feed_only_rebuild`` runs when coverage completes without any
  explicit missing date.

The interval is configurable via ``BACKFILL_WATCH_INTERVAL_SECONDS`` (default
30) and the horizon via ``BACKFILL_WATCH_DAYS`` (default 45).
"""
import os
import threading
from datetime import datetime, timedelta

BACKFILL_WATCH_INTERVAL_SECONDS = int(
    os.environ.get("BACKFILL_WATCH_INTERVAL_SECONDS", "30")
)
BACKFILL_WATCH_DAYS = int(os.environ.get("BACKFILL_WATCH_DAYS", "45"))


class HistoryBackfillWatchWorker:
    """Background worker that rebuilds missing dates once feed coverage improves."""

    def __init__(self, store=None, *, coverage_fn=None, rebuild_fn=None,
                 slot_count_fn=None, interval_seconds=None, days=None):
        self._store = store
        self._coverage_fn = coverage_fn or self._default_coverage
        self._rebuild_fn = rebuild_fn or self._default_rebuild
        self._slot_count_fn = slot_count_fn or self._default_slot_count
        self._interval_seconds = int(interval_seconds or BACKFILL_WATCH_INTERVAL_SECONDS)
        self._days = int(days or BACKFILL_WATCH_DAYS)
        self._last_missing_dates = None
        self._last_complete = False
        self._last_rebuilt = 0
        self._last_error = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    # ------------------------------------------------------------------
    # Defaults (override via constructor for tests)
    # ------------------------------------------------------------------
    def _default_coverage(self, days):
        if self._store is None:
            return None
        return self._store.get_feed_coverage(days=days)

    @staticmethod
    def _default_rebuild(dates, days):
        import mt5_signal_bot
        if dates:
            return mt5_signal_bot.rebuild_target_dates(dates, include_weekends=True)
        return mt5_signal_bot._run_feed_only_rebuild(days=days)

    @staticmethod
    def _default_slot_count(date_str):
        import mt5_signal_bot
        try:
            target = datetime.strptime(date_str, "%Y-%m-%d")
        except (TypeError, ValueError):
            return 0
        return len(mt5_signal_bot.get_rebuild_target_hours(
            target, include_weekends=True
        ))

    # ------------------------------------------------------------------
    # Coverage decision logic
    # ------------------------------------------------------------------
    def _read_coverage(self):
        try:
            coverage = self._coverage_fn(self._days)
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            return None
        if not isinstance(coverage, dict):
            self._last_error = "coverage_fn returned a non-dict result"
            return None
        return coverage

    def _missing_set(self, coverage):
        return {str(d) for d in (coverage.get("missing_dates") or [])}

    def _target_dates(self, coverage):
        """Return the previously-missing dates that are now covered."""
        current_missing = self._missing_set(coverage)
        if self._last_missing_dates is None:
            return []
        newly_covered = self._last_missing_dates - current_missing
        if bool(coverage.get("coverage_complete")):
            newly_covered |= current_missing
        return sorted(newly_covered)

    def _should_rebuild(self, coverage) -> bool:
        complete = bool(coverage.get("coverage_complete"))
        if self._last_missing_dates is None:
            return complete
        return complete or bool(self._last_missing_dates - self._missing_set(coverage))

    def run_once(self) -> bool:
        """Poll coverage and rebuild when it improved. Returns True when it ran."""
        coverage = self._read_coverage()
        if coverage is None:
            return False
        with self._lock:
            complete = bool(coverage.get("coverage_complete"))
            try:
                if self._should_rebuild(coverage):
                    dates = self._target_dates(coverage)
                    if complete:
                        print("[HISTORY] Coverage complete, rebuilding missing dates...")
                    else:
                        print(
                            f"[HISTORY] Coverage improved, rebuilding {len(dates)} "
                            "missing date(s)..."
                        )
                    rebuilt = self._rebuild_fn(list(dates), self._days)
                    self._last_rebuilt = int(rebuilt or 0)
                    if dates:
                        self._log_rebuilt_dates(dates)
                    self._last_error = None
                self._last_complete = complete
                self._last_missing_dates = self._missing_set(coverage)
                return True
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                self._last_rebuilt = 0
                print(f"[BACKFILL-WATCH] rebuild error: {self._last_error}")
                self._last_complete = complete
                self._last_missing_dates = self._missing_set(coverage)
                return False

    def _log_rebuilt_dates(self, dates):
        for date_str in dates:
            try:
                slots = int(self._slot_count_fn(date_str))
            except Exception:
                slots = 0
            print(f"[HISTORY] Rebuilt date={date_str} slots={slots} complete=true")

    # ------------------------------------------------------------------
    # Threading
    # ------------------------------------------------------------------
    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="history-backfill-watch-worker", daemon=True
        )
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
                print(f"[BACKFILL-WATCH] loop error: {type(exc).__name__}: {exc}")
            self._stop.wait(self._interval_seconds)


def start_history_backfill_watch_worker(store=None) -> HistoryBackfillWatchWorker:
    """Start the background worker with the given feed store (default MT4FeedStore)."""
    if store is None:
        try:
            from repositories.mt4_feed_store import MT4FeedStore
            store = MT4FeedStore()
        except Exception:
            store = None
    worker = HistoryBackfillWatchWorker(store=store)
    worker.start()
    return worker


if __name__ == "__main__":
    worker = start_history_backfill_watch_worker()
    try:
        while True:
            import time
            time.sleep(3600)
    except KeyboardInterrupt:
        worker.stop()
