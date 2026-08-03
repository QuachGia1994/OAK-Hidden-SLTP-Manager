# -*- coding: utf-8 -*-
"""Continuous account-state sampler for the OAK trade audit ledger (§7).

Samples balance / equity / margin every *interval_seconds* and persists
them via ``TradeAuditStore.upsert_equity_sample``.

Design constraints (§7):
- Sampler failures must NEVER propagate to or stop Hidden SL/TP management.
- Raw 60-second samples are retained 180 days; rollup is derived, never deletes raw rows.
- No MT5 import; no candle API.
"""
import time
from datetime import datetime, timezone
from itertools import groupby

from oak_logger import setup_logger

log = setup_logger("equity_sampler")

# Raw equity samples retained for 180 days (§7 retention policy).
RETENTION_RAW_DAYS = 180


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


class EquitySampler:
    """Append-only equity sampler backed by TradeAuditStore."""

    def __init__(self, store, interval_seconds=60):
        self._store = store
        self._interval = max(1, int(interval_seconds))

    # ------------------------------------------------------------------ #
    # Single-shot sample
    # ------------------------------------------------------------------ #
    def sample_once(self, account_uid, account_info, now_utc=None):
        """Record one equity sample and return a result dict.

        Parameters
        ----------
        account_uid : str
            Unique account identifier (e.g. ``"12345@Vantage-Server"``).
        account_info : dict
            Must contain at least: login, server, currency, account_type,
            profile_name, broker, balance, equity, margin, free_margin,
            margin_level, and either open_profit or profit, credit.
        now_utc : datetime, optional
            Override timestamp (used in tests).

        Returns
        -------
        dict
            ``{"account_id": int, "sample_count": int, "sampled_at_utc": str}``
        """
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
        sampled_at = now_utc.isoformat()

        account_id = self._store.upsert_account(
            account_uid=account_uid,
            profile_name=account_info.get("profile_name", ""),
            broker=account_info.get("broker", ""),
            server=account_info.get("server", ""),
            currency=account_info.get("currency", ""),
            account_type=account_info.get("account_type", ""),
        )

        sample = {
            "sampled_at_utc": sampled_at,
            "sampled_at_broker": sampled_at,
            "balance": account_info.get("balance", 0.0),
            "equity": account_info.get("equity", 0.0),
            "margin": account_info.get("margin", 0.0),
            "free_margin": account_info.get("free_margin", 0.0),
            "margin_level": account_info.get("margin_level", 0.0),
            "open_profit": account_info.get("open_profit", account_info.get("profit", 0.0)),
        }
        self._store.upsert_equity_sample(account_id, sample)

        existing = self._store.list_equity_samples(account_id=account_id)
        return {
            "account_id": account_id,
            "sample_count": len(existing),
            "sampled_at_utc": sampled_at,
        }

    # ------------------------------------------------------------------ #
    # Continuous loop (§7 sampler must never propagate failures)
    # ------------------------------------------------------------------ #
    def sample_loop(self, account_uid, account_info_provider,
                    stop_event=None, max_iterations=None):
        """Sample continuously until *stop_event* is set or *max_iterations* hit.

        Parameters
        ----------
        account_uid : str
        account_info_provider : callable
            Called with no args; must return an account_info dict or
            ``None``/``False`` when MT5 is not connected.
        stop_event : threading.Event, optional
            When set the loop exits gracefully.
        max_iterations : int, optional
            Hard cap on iterations (useful in tests).

        Returns
        -------
        int
            Number of samples actually written.
        """
        count = 0
        iterations = 0
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            if max_iterations is not None and iterations >= max_iterations:
                break
            iterations += 1
            try:
                info = account_info_provider()
                if not info:
                    time.sleep(self._interval)
                    continue
                result = self.sample_once(account_uid, info)
                count += 1
            except Exception as exc:
                log.warning("Equity sampler failure (will continue): %s", exc)
            time.sleep(self._interval)
        return count

    # ------------------------------------------------------------------ #
    # Retention / aggregation helpers (§7)
    # ------------------------------------------------------------------ #
    def list_samples(self, account_uid, since_utc=None):
        """Return samples for *account_uid* ascending by time.

        Parameters
        ----------
        account_uid : str
        since_utc : str, optional
            ISO-8601 lower bound (inclusive). When ``None`` all samples are returned.
        """
        account = self._store.get_account_by_uid(account_uid)
        if account is None:
            return []
        rows = self._store.list_equity_samples(account_id=account["id"])
        ascending = list(reversed(rows))
        if since_utc is not None:
            ascending = [r for r in ascending if (r.get("sampled_at_utc") or "") >= since_utc]
        return ascending

    def aggregate_samples(self, account_uid, bucket_minutes=5):
        """OHLC rollup of equity values bucketed by *bucket_minutes*.

        Returns a list of dicts with keys:
            bucket_start_utc, count, open, high, low, close, avg_balance

        Raw rows are never deleted (ledger is append-only).
        """
        samples = self.list_samples(account_uid)
        if not samples:
            return []

        def _bucket_key(s):
            ts = s.get("sampled_at_utc") or ""
            dt = datetime.fromisoformat(ts)
            minute_floor = (dt.minute // bucket_minutes) * bucket_minutes
            return dt.replace(minute=minute_floor, second=0, microsecond=0).isoformat()

        buckets = []
        for bucket_start, group in groupby(samples, key=_bucket_key):
            rows = list(group)
            equities = [r["equity"] for r in rows if r.get("equity") is not None]
            balances = [r["balance"] for r in rows if r.get("balance") is not None]
            if not equities:
                continue
            buckets.append({
                "bucket_start_utc": bucket_start,
                "count": len(rows),
                "open": equities[0],
                "high": max(equities),
                "low": min(equities),
                "close": equities[-1],
                "avg_balance": sum(balances) / len(balances) if balances else 0.0,
            })
        return buckets
