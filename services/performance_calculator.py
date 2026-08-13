# -*- coding: utf-8 -*-
"""Account performance metrics calculator for OAK (§8, §9).

Computes realized / unrealized P&L, drawdown, win rate, profit factor,
exposure, holding time, commissions, and cash-flow-adjusted returns.

All calculations are defensive: an empty store produces a dict with
None/0.0 values and ``drawdown_source="NONE"``; the method never raises.
"""
from collections import defaultdict
from datetime import datetime, timezone

from oak_logger import setup_logger

log = setup_logger("perf_calc")

# Entry types that represent a trading close (§8).
_CLOSE_ENTRY_TYPES = frozenset({"OUT", "INOUT", "OUT_BY", "CLOSEBY"})
# Deal types that represent trading activity (excludes BALANCE, CREDIT, etc.).
_TRADING_DEAL_TYPES = frozenset({"BUY", "SELL"})


def _safe_float(val, default=0.0):
    """Coerce to float, returning *default* on failure."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _parse_iso(ts):
    """Parse an ISO-8601 timestamp to a datetime (UTC-aware)."""
    if ts is None:
        return None
    try:
        return datetime.fromisoformat(str(ts))
    except (ValueError, TypeError):
        return None


class PerformanceCalculator:
    """Compute account performance from the trade audit store."""

    def __init__(self, store):
        self._store = store

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def compute(self, account_uid, initial_balance=None, as_of_utc=None, since_utc=None):
        """Return a dict with exactly the keys specified in §8 / §9.

        Parameters
        ----------
        account_uid : str
        initial_balance : float, optional
            Starting balance for account_growth / trading_return.
            ``None`` → use earliest balance snapshot or 0.0.
        as_of_utc : datetime, optional
            Upper cutoff (inclusive); deals/samples after this are ignored.
        since_utc : datetime, optional
            Lower bound (inclusive); rolling period start. None = all history.

        Returns
        -------
        dict
            Performance metrics — never raises.
        """
        result = self._empty_result()
        try:
            self._fill_metrics(result, account_uid, initial_balance, as_of_utc, since_utc)
        except Exception as exc:
            log.warning("PerformanceCalculator error (returning defaults): %s", exc)
        return result

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    @staticmethod
    def _empty_result():
        return {
            "current_balance": 0.0,
            "current_equity": None,
            "net_deposits": None,
            "net_profit": None,
            "realized_pl": None,
            "unrealized_pl": None,
            "gross_profit": None,
            "gross_loss": None,
            "profit_factor": None,
            "win_rate": None,
            "closed_trade_count": 0,
            "winning_trade_count": 0,
            "losing_trade_count": 0,
            "win_rate_basis": "CLOSED_POSITIONS",
            "average_win": None,
            "average_loss": None,
            "expectancy": None,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
            "max_equity_drawdown": None,
            "max_balance_drawdown": None,
            "current_drawdown": None,
            "recovery_factor": None,
            "average_holding_time": None,
            "exposure_by_symbol": {},
            "exposure_by_direction": {"BUY": 0.0, "SELL": 0.0},
            "total_commission": 0.0,
            "total_swap": 0.0,
            "total_fees": 0.0,
            "account_growth": None,
            "account_growth_pct": None,
            "trading_return": None,
            "trading_return_pct": None,
            "net_cash_flow": None,
            "drawdown_source": "NONE",
        }

    @staticmethod
    def _in_window(ts, since_utc, as_of_utc):
        if ts is None:
            return since_utc is None and as_of_utc is None
        if since_utc is not None and ts < since_utc:
            return False
        if as_of_utc is not None and ts > as_of_utc:
            return False
        return True

    def _fill_metrics(self, r, account_uid, initial_balance, as_of_utc, since_utc=None):
        account = self._store.get_account_by_uid(account_uid)
        if account is None:
            return
        account_id = account["id"]

        # --- Deals (optional rolling window on deal_time_utc) ---
        raw_deals = self._store.list_deals(account_id=account_id)
        all_deals = []
        for d in raw_deals:
            ts = _parse_iso(d.get("deal_time_utc"))
            if since_utc is not None or as_of_utc is not None:
                if not self._in_window(ts, since_utc, as_of_utc):
                    continue
            all_deals.append(d)
        close_deals = [
            d for d in all_deals
            if d.get("entry_type") in _CLOSE_ENTRY_TYPES
            and d.get("deal_type") in _TRADING_DEAL_TYPES
        ]
        trading_deals = [
            d for d in all_deals
            if d.get("deal_type") in _TRADING_DEAL_TYPES
        ]

        # --- Realized P/L ---
        realized_pl = sum(_safe_float(d.get("profit")) for d in close_deals)
        r["realized_pl"] = realized_pl

        # --- Gross profit / loss ---
        profits = [_safe_float(d.get("profit")) for d in close_deals]
        gross_profit = sum(p for p in profits if p > 0)
        gross_loss = abs(sum(p for p in profits if p < 0))
        r["gross_profit"] = gross_profit if gross_profit > 0 else None
        r["gross_loss"] = gross_loss if gross_loss > 0 else None

        # --- Profit factor ---
        if gross_loss > 0:
            r["profit_factor"] = gross_profit / gross_loss
        elif gross_profit > 0 and gross_loss == 0:
            # No losses → profit_factor is infinite in principle; report 0.0 per spec
            # when there are no losses (wins only).
            r["profit_factor"] = 0.0
        else:
            r["profit_factor"] = None

        # --- Win/loss per position ---
        pos_profits = defaultdict(float)
        pos_first_close = {}
        pos_first_in = {}
        for d in close_deals:
            pid = str(d.get("position_id") or "")
            if not pid:
                continue
            pos_profits[pid] += _safe_float(d.get("profit"))
            ts = _parse_iso(d.get("deal_time_utc"))
            if ts is not None:
                if pid not in pos_first_close or ts < pos_first_close[pid]:
                    pos_first_close[pid] = ts
        for d in all_deals:
            if d.get("entry_type") == "IN" and d.get("deal_type") in _TRADING_DEAL_TYPES:
                pid = str(d.get("position_id") or "")
                if not pid:
                    continue
                ts = _parse_iso(d.get("deal_time_utc"))
                if ts is not None:
                    if pid not in pos_first_in or ts < pos_first_in[pid]:
                        pos_first_in[pid] = ts

        wins = sum(1 for v in pos_profits.values() if v > 0)
        losses = sum(1 for v in pos_profits.values() if v < 0)
        decided = wins + losses

        r["closed_trade_count"] = decided
        r["winning_trade_count"] = wins
        r["losing_trade_count"] = losses
        if decided > 0:
            r["win_rate"] = wins / decided
        else:
            r["win_rate"] = None

        r["average_win"] = gross_profit / wins if wins > 0 else None
        r["average_loss"] = gross_loss / losses if losses > 0 else None
        r["expectancy"] = (
            (gross_profit - gross_loss) / decided if decided > 0 else None
        )

        # --- Consecutive wins / losses ---
        ordered_pids = sorted(
            pos_profits.keys(),
            key=lambda p: pos_first_close.get(p, datetime.max.replace(tzinfo=timezone.utc)),
        )
        max_cw, max_cl = 0, 0
        cw, cl = 0, 0
        for pid in ordered_pids:
            if pos_profits[pid] > 0:
                cw += 1
                cl = 0
            elif pos_profits[pid] < 0:
                cl += 1
                cw = 0
            else:
                cw = 0
                cl = 0
            max_cw = max(max_cw, cw)
            max_cl = max(max_cl, cl)
        r["max_consecutive_wins"] = max_cw
        r["max_consecutive_losses"] = max_cl

        # --- Equity samples & drawdown ---
        equity_samples = list(reversed(
            self._store.list_equity_samples(account_id=account_id)
        ))
        if since_utc is not None or as_of_utc is not None:
            equity_samples = [
                s for s in equity_samples
                if self._in_window(_parse_iso(s.get("sampled_at_utc")), since_utc, as_of_utc)
            ]
        snapshots = self._store.list_snapshots(account_id=account_id)

        current_balance = 0.0
        current_equity = None

        if equity_samples:
            latest = equity_samples[-1]
            current_balance = _safe_float(latest.get("balance"), 0.0)
            current_equity = _safe_float(latest.get("equity"), None)
            r["current_balance"] = current_balance
            r["current_equity"] = current_equity
            open_profit = latest.get("open_profit")
            r["unrealized_pl"] = _safe_float(open_profit, None) if open_profit is not None else None

            peak = None
            max_dd = None
            for s in equity_samples:
                eq = _safe_float(s.get("equity"), None)
                if eq is None:
                    continue
                if peak is not None:
                    dd = peak - eq
                    if max_dd is None or dd > max_dd:
                        max_dd = dd
                if peak is None or eq > peak:
                    peak = eq
            r["max_equity_drawdown"] = max_dd
            r["drawdown_source"] = "EQUITY_SAMPLES"

            if peak is not None and current_equity is not None:
                r["current_drawdown"] = peak - current_equity
        elif snapshots:
            latest_snap = snapshots[-1]
            current_balance = _safe_float(latest_snap.get("balance"), 0.0)
            current_equity = _safe_float(latest_snap.get("equity"), None)
            r["current_balance"] = current_balance
            r["current_equity"] = current_equity
            open_profit = latest_snap.get("open_profit")
            r["unrealized_pl"] = _safe_float(open_profit, None) if open_profit is not None else None

            peak = None
            max_dd = None
            for s in snapshots:
                eq = _safe_float(s.get("equity"), None)
                if eq is None:
                    continue
                if peak is not None:
                    dd = peak - eq
                    if max_dd is None or dd > max_dd:
                        max_dd = dd
                if peak is None or eq > peak:
                    peak = eq
            r["max_equity_drawdown"] = max_dd
            r["drawdown_source"] = "CHECKPOINT"

            if peak is not None and current_equity is not None:
                r["current_drawdown"] = peak - current_equity
        else:
            r["current_balance"] = 0.0
            r["current_equity"] = None
            r["drawdown_source"] = "NONE"

        # --- Max balance drawdown ---
        balance_values = []
        if equity_samples:
            balance_values = [_safe_float(s.get("balance"), 0.0) for s in equity_samples]
        elif snapshots:
            balance_values = [_safe_float(s.get("balance"), 0.0) for s in snapshots]
        if balance_values:
            bpeak = None
            bmax_dd = None
            for bv in balance_values:
                if bpeak is not None:
                    bdd = bpeak - bv
                    if bmax_dd is None or bdd > bmax_dd:
                        bmax_dd = bdd
                if bpeak is None or bv > bpeak:
                    bpeak = bv
            r["max_balance_drawdown"] = bmax_dd

        # --- Recovery factor ---
        dd = r["max_equity_drawdown"]
        if dd is not None and dd > 0:
            r["recovery_factor"] = realized_pl / dd
        else:
            r["recovery_factor"] = None

        # --- Average holding time ---
        holding_times = []
        for pid in pos_profits:
            if pos_profits[pid] == 0:
                continue  # scratch — skip
            t_in = pos_first_in.get(pid)
            t_out = pos_first_close.get(pid)
            if t_in is not None and t_out is not None:
                holding_times.append((t_out - t_in).total_seconds())
        if holding_times:
            r["average_holding_time"] = sum(holding_times) / len(holding_times)

        # --- Exposure ---
        positions = self._store.list_positions(account_id=account_id)
        closed_position_ids = set()
        for d in close_deals:
            pid = str(d.get("position_id") or "")
            if pid:
                closed_position_ids.add(pid)
        exposure_sym = defaultdict(float)
        exposure_dir = {"BUY": 0.0, "SELL": 0.0}
        for p in positions:
            pid = str(p.get("position_id") or "")
            if pid in closed_position_ids:
                continue
            vol = _safe_float(p.get("initial_volume"), 0.0)
            sym = p.get("symbol", "")
            if sym:
                exposure_sym[sym] += vol
            direction = (p.get("direction") or "").upper()
            if direction in exposure_dir:
                exposure_dir[direction] += vol
        r["exposure_by_symbol"] = dict(exposure_sym)
        r["exposure_by_direction"] = exposure_dir

        # --- Commissions / swap / fees ---
        r["total_commission"] = sum(_safe_float(d.get("commission")) for d in trading_deals)
        r["total_swap"] = sum(_safe_float(d.get("swap")) for d in trading_deals)
        r["total_fees"] = sum(_safe_float(d.get("fee")) for d in trading_deals)

        # --- Cash flows (§9) ---
        cash_flows = self._store.list_cash_flows(account_id=account_id)
        net_cf = sum(_safe_float(cf.get("amount")) for cf in cash_flows)
        r["net_cash_flow"] = net_cf
        r["net_deposits"] = net_cf

        # --- Account growth & trading return ---
        ib = initial_balance
        if ib is None:
            # Prefer the earliest balance-bearing equity sample; fall back to
            # checkpoint snapshots. This keeps return metrics defined for the
            # normal live ledger path where equity samples exist without snapshots.
            if equity_samples:
                ib = _safe_float(equity_samples[0].get("balance"), 0.0)
            elif snapshots:
                ib = _safe_float(snapshots[0].get("balance"), 0.0)
            else:
                ib = 0.0
        r["account_growth"] = current_balance - ib
        r["trading_return"] = current_balance - ib - net_cf
        if ib:
            r["account_growth_pct"] = (current_balance - ib) / ib
            r["trading_return_pct"] = (current_balance - ib - net_cf) / ib

        # --- Net profit ---
        r["net_profit"] = realized_pl if realized_pl != 0 else None
        if r["net_profit"] is None and r["unrealized_pl"] is not None:
            r["net_profit"] = r["unrealized_pl"]

    # ------------------------------------------------------------------ #
    # Helper (internal)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _position_realized_profit(deal):
        """Return the realized profit from a single deal dict."""
        return _safe_float(deal.get("profit"))
