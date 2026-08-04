# -*- coding: utf-8 -*-
"""Account audit service — wires the trade-audit runtime together (§2, §6, §7).

Runs against a connected MT5 session WITHOUT any candle API:

- every ``tick_interval_seconds`` it reads the broker clock (injected provider,
  typically ``mt5.symbol_info_tick(...).time`` — never ``copy_rates_*``);
- when the broker clock enters a checkpoint hour (H3/H7/H9/H12/H14/H16) it runs
  the checkpoint engine (account_info + positions_get + deal reconciliation +
  snapshot + cohort capture) and then pushes the public dashboard payloads;
- checkpoint hours that were skipped (app was off / late startup) are rebuilt
  from MT5 history with ``capture_mode=RECONSTRUCTED`` per §6;
- the equity sampler records account state every ``sample_interval_seconds``
  when the profile is connected; sampler failures NEVER propagate (§7).

Checkpoint runs are idempotent (unique account/date/hour), so restarts never
create duplicates.
"""
import time
from datetime import datetime, timezone

from oak_logger import setup_logger

from services.checkpoint_engine import CheckpointEngine, CHECKPOINT_HOURS
from services.mt5_deal_reconciler import MT5DealReconciler
from services.equity_sampler import EquitySampler

log = setup_logger("account_audit")

#: Broker hours that define a checkpoint boundary (§2).
CHECKPOINT_HOURS_ORDERED = list(CHECKPOINT_HOURS)

#: Statuses that count as "already captured" for a checkpoint hour.
_DONE_STATUSES = frozenset({"COMPLETED", "NO_OPEN_POSITIONS", "PARTIAL_RECONSTRUCTED"})


def broker_time_from_mt5(mt5_module, symbol="XAUUSD"):
    """Return broker-local naive datetime from an MT5 tick timestamp.

    MT5 tick ``time`` is a unix epoch in the broker/server timezone, which is
    exactly the broker clock the checkpoint schedule is defined against.
    Returns ``None`` when no tick is available (terminal not connected).
    """
    try:
        tick = mt5_module.symbol_info_tick(symbol)
    except Exception:  # defensive: never break the audit loop
        return None
    if tick is None or getattr(tick, "time", None) is None:
        return None
    try:
        return datetime.fromtimestamp(int(tick.time))
    except (TypeError, ValueError, OSError):
        return None


def account_info_dict(account_info, profile_name="", broker=""):
    """Normalize an MT5 account_info object into the engine's expected dict.

    MT5 exposes ``margin_free`` and ``profit``; the engine/sampler expect
    ``free_margin`` and ``open_profit`` — map them here.
    """
    if not account_info:
        return {}
    return {
        "login": getattr(account_info, "login", None),
        "server": getattr(account_info, "server", "") or "",
        "currency": getattr(account_info, "currency", "") or "",
        "account_type": getattr(account_info, "account_type", "") or "",
        "balance": getattr(account_info, "balance", None),
        "equity": getattr(account_info, "equity", None),
        "margin": getattr(account_info, "margin", None),
        "free_margin": getattr(account_info, "margin_free", None),
        "margin_level": getattr(account_info, "margin_level", None),
        "open_profit": getattr(account_info, "profit", None),
        "credit": getattr(account_info, "credit", 0.0),
        "profile_name": profile_name,
        "broker": broker,
    }


class AccountAuditService:
    """Drives checkpoints + equity sampling + dashboard push for one account."""

    def __init__(
        self,
        store,
        account_uid,
        *,
        broker_time_provider=None,
        account_info_provider=None,
        positions_provider=None,
        reconciler=None,
        engine=None,
        sampler=None,
        publisher=None,
        profile_name="",
        broker="",
        currency="",
        tick_interval_seconds=30,
        sample_interval_seconds=60,
    ):
        self.store = store
        self.account_uid = account_uid
        self._broker_time_provider = broker_time_provider
        self._account_info_provider = account_info_provider
        self._positions_provider = positions_provider
        self.reconciler = reconciler
        self.engine = engine
        self.sampler = sampler
        self.publisher = publisher
        self.profile_name = profile_name
        self.broker = broker
        self.currency = currency
        self.tick_interval = max(1, int(tick_interval_seconds))
        self.sample_interval = max(1, int(sample_interval_seconds))
        self._last_sample_at = None

    # ------------------------------------------------------------------ #
    # Providers (lazy MT5 defaults, injectable for tests)
    # ------------------------------------------------------------------ #
    def _broker_time(self):
        if self._broker_time_provider is not None:
            return self._broker_time_provider()
        return None

    def _account_info(self):
        if self._account_info_provider is not None:
            return self._account_info_provider()
        return {}

    def _positions(self):
        if self._positions_provider is not None:
            return list(self._positions_provider() or [])
        return []

    # ------------------------------------------------------------------ #
    # Core tick — one scheduling pass
    # ------------------------------------------------------------------ #
    def tick(self, now_utc=None):
        """Run one scheduling pass. Returns a result dict (never raises)."""
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
        broker_dt = self._broker_time()
        if broker_dt is None:
            return {"status": "NO_BROKER_CLOCK", "checkpoints_run": 0, "samples": 0}

        account_info = self._account_info()
        if not account_info:
            return {"status": "NOT_CONNECTED", "checkpoints_run": 0, "samples": 0}

        # Catch-up: reconstruct any earlier checkpoint hours of today that
        # were missed (app off / late start) per §6.
        reconstructed = 0
        for hour in CHECKPOINT_HOURS_ORDERED:
            if hour >= broker_dt.hour:
                break
            if self._hour_captured(broker_dt.date(), hour):
                continue
            self._reconstruct_checkpoint(broker_dt.date(), hour, now_utc)
            reconstructed += 1

        # Current checkpoint window: the latest hour <= broker hour.
        current_hour = max(
            (h for h in CHECKPOINT_HOURS_ORDERED if h <= broker_dt.hour),
            default=None,
        )
        checkpoints_run = 0
        if current_hour is not None and not self._hour_captured(broker_dt.date(), current_hour):
            self._run_current_checkpoint(broker_dt.date(), current_hour, account_info, now_utc)
            checkpoints_run += 1

        # Continuous equity sampling (§7) — never propagates failures.
        samples = 0
        try:
            if self.sampler is not None:
                if self._last_sample_at is None or (now_utc - self._last_sample_at).total_seconds() >= self.sample_interval:
                    self.sampler.sample_once(self.account_uid, account_info, now_utc=now_utc)
                    self._last_sample_at = now_utc
                    samples = 1
        except Exception as exc:  # pragma: no cover - isolation per §7
            log.warning("Equity sampler failure (will continue): %s", exc)

        return {
            "status": "OK",
            "checkpoints_run": checkpoints_run,
            "reconstructed": reconstructed,
            "samples": samples,
        }

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _hour_captured(self, broker_date, hour):
        account = self.store.get_account_by_uid(self.account_uid)
        if account is None:
            return False
        run = self.store.get_checkpoint_run(account["id"], broker_date.isoformat(), hour)
        return run is not None and run.get("status") in _DONE_STATUSES

    def _reconstruct_checkpoint(self, broker_date, hour, now_utc):
        if self.engine is None:
            return
        try:
            self.engine.reconstruct_missed_checkpoint(
                self.account_uid,
                broker_date.isoformat(),
                hour,
                account_info={"server": "", "account_type": ""},
                now_utc=now_utc,
            )
            log.info("Reconstructed missed checkpoint %s H%02d", broker_date.isoformat(), hour)
        except Exception as exc:  # pragma: no cover - never break the audit loop
            log.warning("Checkpoint reconstruction failed %s H%02d: %s", broker_date.isoformat(), hour, exc)

    def _run_current_checkpoint(self, broker_date, hour, account_info, now_utc):
        try:
            result = self.engine.run_checkpoint(
                self.account_uid,
                broker_date.isoformat(),
                hour,
                account_info=account_info,
                open_positions=self._positions(),
                now_utc=now_utc,
                capture_mode="NORMAL",
                on_checkpoint=self._after_checkpoint,
            )
            log.info(
                "Checkpoint %s H%02d done: status=%s positions=%s",
                broker_date.isoformat(), hour, result.get("status"), result.get("open_positions"),
            )
        except Exception as exc:  # pragma: no cover - never break the audit loop
            log.warning("Checkpoint %s H%02d failed: %s", broker_date.isoformat(), hour, exc)

    def _after_checkpoint(self, result):
        """Push public dashboard payloads after a checkpoint (§2 step 8)."""
        if self.publisher is None:
            return
        try:
            outcome = self.publisher.push_all(self.account_uid)
            if not outcome.get("pushed"):
                log.warning("Dashboard push skipped: %s", outcome.get("reason", "unknown"))
        except Exception as exc:  # pragma: no cover - push must never break capture
            log.warning("Dashboard push failed after checkpoint: %s", exc)

    # ------------------------------------------------------------------ #
    # Continuous loop
    # ------------------------------------------------------------------ #
    def run_forever(self, stop_event=None, max_ticks=None):
        """Run the audit loop until stopped. Returns total tick count."""
        ticks = 0
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            if max_ticks is not None and ticks >= max_ticks:
                break
            self.tick()
            ticks += 1
            time.sleep(self.tick_interval)
        return ticks
