# -*- coding: utf-8 -*-
"""Checkpoint engine for the OAK trade audit ledger.

CHECKPOINT_HOURS = [3, 7, 9, 12, 14, 16] (broker local time).

At each checkpoint:
  1. read mt5.account_info();
  2. read mt5.positions_get();
  3. read deals since the previous checkpoint (via the deal reconciler);
  4. complete the previous interval (finalize its cohort statuses);
  5. capture a new account snapshot;
  6. capture all open positions as a new cohort;
  7. persist atomically;
  8. (hook) push dashboard / send Telegram summary.

Checkpoints are idempotent: unique(account_id, broker_date, checkpoint_hour).
A restart never creates duplicates.

Missed-checkpoint reconstruction: capture_mode=RECONSTRUCTED, floating fields
are NULL (never fake historical floating P/L), status=PARTIAL_RECONSTRUCTED when
no equity snapshot is available for that point in time.
"""
from datetime import datetime, timedelta, timezone

from oak_logger import setup_logger

log = setup_logger("checkpoint_engine")

CHECKPOINT_HOURS = [3, 7, 9, 12, 14, 16]

# Position lifecycle statuses for a cohort (section 6).
STILL_OPEN = "STILL_OPEN"
PARTIALLY_CLOSED = "PARTIALLY_CLOSED"
NO_OPEN_POSITIONS = "NO_OPEN_POSITIONS"

# Closing deal entry types (MT5 DEAL_ENTRY_*).
_CLOSE_ENTRIES = {1, 2, 3, 4}  # OUT, INOUT, OUT_BY, CLOSEBY


def previous_checkpoint(broker_date, checkpoint_hour):
    """Return (prev_date, prev_hour) immediately before the given checkpoint.

    H3 -> H16 of the previous broker day; other hours -> previous hour same day.
    """
    if checkpoint_hour not in CHECKPOINT_HOURS:
        raise ValueError("checkpoint_hour %s not in %s" % (checkpoint_hour, CHECKPOINT_HOURS))
    idx = CHECKPOINT_HOURS.index(checkpoint_hour)
    if idx > 0:
        return broker_date, CHECKPOINT_HOURS[idx - 1]
    return _shift_broker_date(broker_date, -1), 16


def checkpoint_iso(broker_date, checkpoint_hour):
    """Broker-local naive ISO timestamp for a checkpoint boundary."""
    return "%sT%02d:00:00" % (broker_date, checkpoint_hour)


def _shift_broker_date(broker_date, days):
    dt = datetime.strptime(broker_date, "%Y-%m-%d") + timedelta(days=days)
    return dt.strftime("%Y-%m-%d")


def _normalize_manual_category(reason_category):
    """Collapse the manual family into CLOSED_MANUAL for cohort status labels."""
    if reason_category and reason_category.startswith("CLOSED_MANUAL"):
        return "CLOSED_MANUAL"
    return reason_category


def _position_id_of(pos):
    """Extract a stable position id from an MT5 position object or dict."""
    if isinstance(pos, dict):
        return str(pos.get("position_id") or pos.get("ticket") or "")
    return str(getattr(pos, "position_id", None) or getattr(pos, "ticket", None) or "")


class CheckpointEngine:
    """Runs broker-time checkpoint captures against the trade audit ledger."""

    def __init__(self, store, reconciler):
        self.store = store
        self.reconciler = reconciler

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def run_checkpoint(self, account_uid, broker_date, checkpoint_hour,
                       account_info, open_positions, now_utc=None,
                       capture_mode="NORMAL", on_checkpoint=None):
        """Execute one checkpoint capture.

        account_info: dict-like with balance/equity/margin/free_margin/margin_level.
        open_positions: iterable of MT5 position objects or dicts with
            ticket/position_id, symbol, type, volume, price_open, price_current,
            sl, tp, profit, magic, comment, time.
        on_checkpoint: optional callback(result) after persistence (dashboard/Telegram hook).
        Returns a result dict.
        """
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
        if checkpoint_hour not in CHECKPOINT_HOURS:
            raise ValueError("checkpoint_hour %s not in %s" % (checkpoint_hour, CHECKPOINT_HOURS))

        # 1+3. Reconcile deals up to now (reads MT5 history via reconciler).
        recon = self.reconciler.reconcile(
            account_uid=account_uid,
            account_info=account_info,
            now_utc=now_utc,
            profile_name=account_info.get("profile_name", ""),
            broker=account_info.get("broker", ""),
            currency=account_info.get("currency", ""),
        )
        account_id = recon["account_id"]

        # 4. Complete the previous interval and finalize its cohort statuses.
        prev_date, prev_hour = previous_checkpoint(broker_date, checkpoint_hour)
        prev_run = self.store.get_checkpoint_run(account_id, prev_date, prev_hour)
        interval_start = checkpoint_iso(prev_date, prev_hour)
        interval_end = checkpoint_iso(broker_date, checkpoint_hour)
        if prev_run:
            self._finalize_previous_interval(
                account_id, prev_run, prev_date, prev_hour,
                interval_start, interval_end, open_positions,
            )

        # 5. Idempotent checkpoint run row.
        run_id = self.store.upsert_checkpoint_run(
            account_id=account_id,
            broker_date=broker_date,
            checkpoint_hour=checkpoint_hour,
            interval_start=interval_start,
            interval_end=interval_end,
            captured_at_utc=now_utc.isoformat(),
            capture_mode=capture_mode,
            status="COMPLETED",
        )

        # 6. Account snapshot.
        snapshot_id = self.store.upsert_snapshot(run_id, {
            "balance": account_info.get("balance"),
            "equity": account_info.get("equity"),
            "margin": account_info.get("margin"),
            "free_margin": account_info.get("free_margin"),
            "margin_level": account_info.get("margin_level"),
            "open_profit": account_info.get("open_profit") or account_info.get("profit"),
            "credit": account_info.get("credit"),
        })

        # 7. Cohort of open positions at this checkpoint.
        positions = list(open_positions or [])
        for pos in positions:
            normalized = self._normalize_position(pos)
            self.store.upsert_position(account_id, normalized)
            self.store.upsert_checkpoint_position_state(run_id, {
                "position_id": normalized["position_id"],
                "status_at_checkpoint": STILL_OPEN,
                "volume": normalized.get("initial_volume") or normalized.get("volume"),
                "current_price": normalized.get("price_current"),
                "floating_profit": normalized.get("profit"),
                "sl": normalized.get("sl"),
                "tp": normalized.get("tp"),
                "capture_mode": capture_mode,
            })

        # No open positions -> explicit empty checkpoint, never a blank card.
        run_status = "COMPLETED"
        if not positions:
            run_status = NO_OPEN_POSITIONS
            self.store.upsert_checkpoint_run(
                account_id=account_id,
                broker_date=broker_date,
                checkpoint_hour=checkpoint_hour,
                interval_start=interval_start,
                interval_end=interval_end,
                captured_at_utc=now_utc.isoformat(),
                capture_mode=capture_mode,
                status=NO_OPEN_POSITIONS,
            )

        result = {
            "account_id": account_id,
            "run_id": run_id,
            "snapshot_id": snapshot_id,
            "broker_date": broker_date,
            "checkpoint_hour": checkpoint_hour,
            "interval_start": interval_start,
            "interval_end": interval_end,
            "capture_mode": capture_mode,
            "status": run_status,
            "open_positions": len(positions),
            "deals_reconciled": recon.get("deals_upserted", 0),
            "previous_run": prev_run.get("id") if prev_run else None,
        }
        if on_checkpoint:
            try:
                on_checkpoint(dict(result))
            except Exception as exc:  # pragma: no cover - never break the capture
                log.warning("checkpoint on_checkpoint hook failed: %s", exc)
        log.info("Checkpoint %s %02d: %s (%s)", broker_date, checkpoint_hour, run_status, capture_mode)
        return result

    def reconstruct_missed_checkpoint(self, account_uid, broker_date, checkpoint_hour,
                                      account_info=None, now_utc=None):
        """Reconstruct a checkpoint missed while the app was off.

        - Rebuilds deal/status rows from MT5 history (reconciler);
        - capture_mode = RECONSTRUCTED;
        - floating fields are NULL (never fake historical floating P/L);
        - status = PARTIAL_RECONSTRUCTED when no equity snapshot is available.
        """
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
        account_id = self.reconciler.reconcile(
            account_uid=account_uid,
            account_info=account_info or {},
            now_utc=now_utc,
            profile_name=(account_info or {}).get("profile_name", ""),
            broker=(account_info or {}).get("broker", ""),
            currency=(account_info or {}).get("currency", ""),
        )["account_id"]

        prev_date, prev_hour = previous_checkpoint(broker_date, checkpoint_hour)
        interval_start = checkpoint_iso(prev_date, prev_hour)
        interval_end = checkpoint_iso(broker_date, checkpoint_hour)

        run_id = self.store.upsert_checkpoint_run(
            account_id=account_id,
            broker_date=broker_date,
            checkpoint_hour=checkpoint_hour,
            interval_start=interval_start,
            interval_end=interval_end,
            captured_at_utc=now_utc.isoformat(),
            capture_mode="RECONSTRUCTED",
            status="PARTIAL_RECONSTRUCTED",
        )
        # No fake historical snapshot: balance/equity stay NULL.
        self.store.upsert_snapshot(run_id, {
            "balance": None, "equity": None, "margin": None, "free_margin": None,
            "margin_level": None, "open_profit": None, "credit": None,
        })

        # Reconstruct positions open at that point in time from the deal ledger:
        # opened before the checkpoint and (not closed, or closed at/after it).
        self._reconstruct_positions_from_deals(account_id, run_id, interval_start, interval_end)

        result = {
            "account_id": account_id,
            "run_id": run_id,
            "broker_date": broker_date,
            "checkpoint_hour": checkpoint_hour,
            "capture_mode": "RECONSTRUCTED",
            "status": "PARTIAL_RECONSTRUCTED",
        }
        log.info("Reconstructed missed checkpoint %s %02d (RECONSTRUCTED)", broker_date, checkpoint_hour)
        return result

    # ------------------------------------------------------------------ #
    # Interval finalization
    # ------------------------------------------------------------------ #
    def _finalize_previous_interval(self, account_id, prev_run, prev_date, prev_hour,
                                    interval_start, interval_end, open_positions):
        """Update the previous cohort: STILL_OPEN / CLOSED_* / PARTIALLY_CLOSED."""
        prev_run_id = prev_run["id"]
        cohort = self.store.list_checkpoint_position_states(prev_run_id)
        if not cohort:
            return
        open_tickets = {_position_id_of(pos) for pos in (open_positions or [])}
        deals = self.store.list_deals(account_id=account_id)
        for state in cohort:
            position_id = state["position_id"]
            close = self._find_closing_deal(deals, position_id, interval_start, interval_end)
            still_open = position_id in open_tickets
            if still_open and close:
                self._mark_partially_closed(prev_run, state, position_id, close)
            elif close:
                self._mark_closed(prev_run, state, position_id, close)
            elif still_open:
                self._mark_still_open(state, position_id)
            else:
                # Position is neither open nor closed by a deal in this interval.
                self.store.upsert_checkpoint_position_state(prev_run_id, {
                    "position_id": position_id,
                    "status_at_checkpoint": "CLOSED_UNKNOWN",
                    "volume": state.get("volume"),
                    "current_price": state.get("current_price"),
                    "floating_profit": None,
                    "sl": state.get("sl"),
                    "tp": state.get("tp"),
                    "capture_mode": state.get("capture_mode", "NORMAL"),
                })

    def _mark_closed(self, prev_run, state, position_id, close):
        category = _normalize_manual_category(close.get("reason_category") or "")
        status = category or "CLOSED_UNKNOWN"
        prev_run_id = prev_run["id"]
        mode = "RECONSTRUCTED" if prev_run.get("capture_mode") == "RECONSTRUCTED" else "NORMAL"
        self.store.upsert_checkpoint_position_state(prev_run_id, {
            "position_id": position_id,
            "status_at_checkpoint": status,
            "volume": state.get("volume"),
            "current_price": close.get("price"),
            "floating_profit": None,
            "sl": state.get("sl"),
            "tp": state.get("tp"),
            "close_price": close.get("price"),
            "close_time_utc": close.get("deal_time_utc"),
            "close_reason": close.get("reason_category") or "",
            "realized_profit_to_date": close.get("profit"),
            "capture_mode": mode,
        })

    def _mark_partially_closed(self, prev_run, state, position_id, close):
        """Position still open at this checkpoint but had a closing deal in the interval."""
        prev_run_id = prev_run["id"]
        mode = "RECONSTRUCTED" if prev_run.get("capture_mode") == "RECONSTRUCTED" else "NORMAL"
        self.store.upsert_checkpoint_position_state(prev_run_id, {
            "position_id": position_id,
            "status_at_checkpoint": PARTIALLY_CLOSED,
            "volume": state.get("volume"),
            "current_price": state.get("current_price"),
            "floating_profit": state.get("floating_profit"),
            "sl": state.get("sl"),
            "tp": state.get("tp"),
            "close_price": close.get("price"),
            "close_time_utc": close.get("deal_time_utc"),
            "close_reason": close.get("reason_category") or "",
            "realized_profit_to_date": close.get("profit"),
            "capture_mode": mode,
        })

    def _mark_still_open(self, state, position_id):
        prev_run_id = state.get("checkpoint_run_id") or 0
        self.store.upsert_checkpoint_position_state(prev_run_id, {
            "position_id": position_id,
            "status_at_checkpoint": STILL_OPEN,
            "volume": state.get("volume"),
            "current_price": state.get("current_price"),
            "floating_profit": state.get("floating_profit"),
            "sl": state.get("sl"),
            "tp": state.get("tp"),
            "capture_mode": state.get("capture_mode", "NORMAL"),
        })

    def _find_closing_deal(self, deals, position_id, interval_start, interval_end):
        """Find the last OUT-type deal for a position within the interval."""
        best = None
        for deal in deals:
            if str(deal.get("position_id")) != str(position_id):
                continue
            entry = deal.get("entry_type", "")
            if entry not in ("OUT", "INOUT", "OUT_BY", "CLOSEBY"):
                continue
            ts = deal.get("deal_time_utc") or ""
            if ts < interval_start or ts > interval_end:
                continue
            if best is None or ts >= best.get("deal_time_utc", ""):
                best = deal
        return best

    # ------------------------------------------------------------------ #
    # Reconstruction helpers
    # ------------------------------------------------------------------ #
    def _reconstruct_positions_from_deals(self, account_id, run_id, interval_start, interval_end):
        """Insert position states inferred from the deal ledger for a missed checkpoint.

        Floating P/L is unknown for the past: floating_profit stays NULL.
        """
        deals = self.store.list_deals(account_id=account_id)
        by_position = {}
        for deal in deals:
            pos_id = deal.get("position_id") or ""
            if not pos_id:
                continue
            by_position.setdefault(pos_id, []).append(deal)
        for pos_id, pos_deals in by_position.items():
            if not pos_deals:
                continue
            first_in = self._first_entry_deal(pos_deals)
            if not first_in:
                continue
            close = self._last_close_deal(pos_deals)
            if close:
                status = _normalize_manual_category(close.get("reason_category") or "") or "CLOSED_UNKNOWN"
            else:
                status = STILL_OPEN
            self.store.upsert_position(account_id, {
                "position_id": pos_id,
                "position_ticket": pos_id,
                "symbol": first_in.get("symbol", ""),
                "direction": "BUY" if first_in.get("deal_type") == "BUY" else "SELL",
                "magic": first_in.get("magic", ""),
                "comment": first_in.get("comment", ""),
                "open_time_utc": first_in.get("deal_time_utc"),
                "open_time_broker": first_in.get("deal_time_broker"),
                "open_price": first_in.get("price"),
                "initial_volume": first_in.get("volume"),
                "source_type": "RECONSTRUCTED",
            })
            self.store.upsert_checkpoint_position_state(run_id, {
                "position_id": pos_id,
                "status_at_checkpoint": status,
                "volume": first_in.get("volume"),
                "current_price": None,
                "floating_profit": None,
                "sl": None,
                "tp": None,
                "close_price": close.get("price") if close else None,
                "close_time_utc": close.get("deal_time_utc") if close else None,
                "close_reason": close.get("reason_category") if close else None,
                "realized_profit_to_date": close.get("profit") if close else None,
                "capture_mode": "RECONSTRUCTED",
            })

    @staticmethod
    def _first_entry_deal(pos_deals):
        for deal in pos_deals:
            if deal.get("entry_type") == "IN":
                return deal
        return pos_deals[0]

    @staticmethod
    def _last_close_deal(pos_deals):
        best = None
        for deal in pos_deals:
            if deal.get("entry_type") not in ("OUT", "INOUT", "OUT_BY", "CLOSEBY"):
                continue
            if best is None or (deal.get("deal_time_utc") or "") >= (best.get("deal_time_utc") or ""):
                best = deal
        return best

    # ------------------------------------------------------------------ #
    # Position normalization
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize_position(pos):
        if isinstance(pos, dict):
            return {
                "position_id": str(pos.get("position_id") or pos.get("ticket") or ""),
                "position_ticket": str(pos.get("ticket") or pos.get("position_id") or ""),
                "symbol": pos.get("symbol", ""),
                "direction": _direction_name(pos.get("type")),
                "magic": str(pos.get("magic", "") or ""),
                "comment": pos.get("comment", ""),
                "open_time_utc": pos.get("open_time_utc"),
                "open_time_broker": pos.get("open_time_broker"),
                "open_price": pos.get("price_open"),
                "initial_volume": pos.get("volume"),
                "source_type": "LIVE",
                "price_current": pos.get("price_current"),
                "profit": pos.get("profit"),
                "sl": pos.get("sl"),
                "tp": pos.get("tp"),
            }
        return {
            "position_id": str(getattr(pos, "position_id", None) or getattr(pos, "ticket", None) or ""),
            "position_ticket": str(getattr(pos, "ticket", None) or ""),
            "symbol": getattr(pos, "symbol", ""),
            "direction": _direction_name(getattr(pos, "type", None)),
            "magic": str(getattr(pos, "magic", "") or ""),
            "comment": getattr(pos, "comment", ""),
            "open_time_utc": getattr(pos, "time", None),
            "open_time_broker": getattr(pos, "time", None),
            "open_price": getattr(pos, "price_open", None),
            "initial_volume": getattr(pos, "volume", None),
            "source_type": "LIVE",
            "price_current": getattr(pos, "price_current", None),
            "profit": getattr(pos, "profit", None),
            "sl": getattr(pos, "sl", None),
            "tp": getattr(pos, "tp", None),
        }


def _direction_name(pos_type):
    """MT5 POSITION_TYPE_BUY=0 / SELL=1."""
    if pos_type in (0, "BUY"):
        return "BUY"
    if pos_type in (1, "SELL"):
        return "SELL"
    return str(pos_type or "")
