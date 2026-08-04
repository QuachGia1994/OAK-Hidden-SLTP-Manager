# -*- coding: utf-8 -*-
"""Account-audit queries for the supervisor (Phase 3, Edit prompt.txt §9).

These handlers re-use the existing tested trade-audit stack
(``repositories.trade_audit_store``, ``services.performance_calculator``,
``services.audit_dashboard_publisher``) — the sidecar never re-implements
business logic.  Public-safe payloads only: no raw tickets, no account uid,
no credentials (the publisher builders already strip those).
"""
import sys
from pathlib import Path

from ..ipc.protocol import error_payload

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _ensure_imports():
    """Import the repo-root Python modules (dev layout). Best-effort."""
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))


def _store():
    _ensure_imports()
    from repositories.trade_audit_store import TradeAuditStore
    return TradeAuditStore(read_only=True)


class AccountQueries:
    """Public-safe account / positions / checkpoints / performance queries."""

    def __init__(self, store=None):
        self._store = store

    def _get_store(self):
        if self._store is None:
            self._store = _store()
        return self._store

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _account_id(self, account_uid: str):
        acct = self._get_store().get_account_by_uid(account_uid)
        return acct["id"] if acct else None

    def _uid_for_profile(self, profile_name: str) -> str:
        """Find the audit account whose profile_name matches."""
        store = self._get_store()
        for account in store.list_accounts():
            if account.get("profile_name") == profile_name:
                return account["account_uid"]
        return ""

    # ------------------------------------------------------------------ #
    # Query handlers (return public-safe dicts)
    # ------------------------------------------------------------------ #
    def account_get(self, profile_name: str) -> dict:
        """Latest account overview from the audit ledger (balance/equity/...)."""
        uid = self._uid_for_profile(profile_name)
        if not uid:
            return {"profile": profile_name, "available": False}
        store = self._get_store()
        account_id = self._account_id(uid)
        samples = store.list_equity_samples(account_id=account_id, limit=1)
        if samples:
            s = samples[0]
            return {
                "profile": profile_name,
                "available": True,
                "balance": s.get("balance"),
                "equity": s.get("equity"),
                "margin": s.get("margin"),
                "free_margin": s.get("free_margin"),
                "margin_level": s.get("margin_level"),
                "open_profit": s.get("open_profit"),
                "sampled_at_utc": s.get("sampled_at_utc"),
            }
        return {"profile": profile_name, "available": True, "balance": None}

    def positions_list(self, profile_name: str) -> list:
        """Open positions — public-safe (no raw tickets)."""
        uid = self._uid_for_profile(profile_name)
        account_id = self._account_id(uid) if uid else None
        if not account_id:
            return []
        positions = self._get_store().list_positions(account_id=account_id)
        result = []
        for p in positions:
            result.append({
                "public_trade_id": p.get("public_trade_id") or "",
                "symbol": p.get("symbol", ""),
                "direction": p.get("direction", ""),
                "volume": p.get("initial_volume"),
                "open_price": p.get("open_price"),
                "open_time_utc": p.get("open_time_utc"),
                "source_type": p.get("source_type", ""),
            })
        return result

    def deals_list(self, profile_name: str, limit: int = 200) -> list:
        """Trade ledger — public-safe subset of deals."""
        uid = self._uid_for_profile(profile_name)
        account_id = self._account_id(uid) if uid else None
        if not account_id:
            return []
        deals = self._get_store().list_deals(account_id=account_id)
        result = []
        for d in deals:
            if d.get("deal_type") not in ("BUY", "SELL"):
                continue
            result.append({
                "public_trade_id": d.get("public_trade_id") or "",
                "symbol": d.get("symbol", ""),
                "deal_type": d.get("deal_type", ""),
                "entry_type": d.get("entry_type", ""),
                "reason_category": d.get("reason_category", ""),
                "volume": d.get("volume"),
                "price": d.get("price"),
                "profit": d.get("profit"),
                "commission": d.get("commission"),
                "swap": d.get("swap"),
                "deal_time_utc": d.get("deal_time_utc"),
            })
        return result[:limit]

    def checkpoints_list(self, profile_name: str, limit: int = 30) -> list:
        """Checkpoint timeline — chronological, public-safe."""
        uid = self._uid_for_profile(profile_name)
        account_id = self._account_id(uid) if uid else None
        if not account_id:
            return []
        runs = self._get_store().list_checkpoint_runs(account_id=account_id, limit=limit)
        result = []
        for r in runs:
            result.append({
                "broker_date": r.get("broker_date", ""),
                "checkpoint_hour": r.get("checkpoint_hour"),
                "interval_start": r.get("interval_start"),
                "interval_end": r.get("interval_end"),
                "captured_at_utc": r.get("captured_at_utc"),
                "capture_mode": r.get("capture_mode", ""),
                "status": r.get("status", ""),
            })
        result.reverse()  # chronological ascending
        return result

    def performance_summary(self, profile_name: str) -> dict:
        """Performance metrics from the calculator — public-safe subset."""
        uid = self._uid_for_profile(profile_name)
        if not uid:
            return {"profile": profile_name, "available": False}
        _ensure_imports()
        from services.performance_calculator import PerformanceCalculator
        perf = PerformanceCalculator(self._get_store()).compute(uid)
        keys = (
            "current_balance", "current_equity", "net_profit", "realized_pl",
            "unrealized_pl", "profit_factor", "win_rate", "average_win",
            "average_loss", "expectancy", "max_equity_drawdown",
            "current_drawdown", "drawdown_source", "trading_return",
            "account_growth", "net_cash_flow", "total_commission",
            "total_swap", "total_fees",
        )
        return {
            "profile": profile_name,
            "available": True,
            **{k: perf.get(k) for k in keys},
        }

    def equity_curve(self, profile_name: str, limit: int = 500) -> list:
        """Equity samples as a lightweight curve (time, equity) for charts."""
        uid = self._uid_for_profile(profile_name)
        account_id = self._account_id(uid) if uid else None
        if not account_id:
            return []
        samples = self._get_store().list_equity_samples(account_id=account_id, limit=limit)
        # list_equity_samples returns DESC — reverse to chronological.
        result = []
        for s in reversed(samples):
            result.append({
                "t": s.get("sampled_at_utc"),
                "equity": s.get("equity"),
                "balance": s.get("balance"),
            })
        return result

    def drawdown_curve(self, profile_name: str, limit: int = 500) -> list:
        """Drawdown (peak-to-current) per equity sample, chronological."""
        uid = self._uid_for_profile(profile_name)
        account_id = self._account_id(uid) if uid else None
        if not account_id:
            return []
        samples = self._get_store().list_equity_samples(account_id=account_id, limit=limit)
        peak = None
        result = []
        for s in reversed(samples):
            equity = s.get("equity")
            if equity is None:
                continue
            if peak is None or equity > peak:
                peak = equity
            dd = (peak - equity) if peak else 0.0
            result.append({
                "t": s.get("sampled_at_utc"),
                "drawdown": dd,
                "equity": equity,
                "peak": peak,
            })
        return result

    def risk_summary(self, profile_name: str) -> dict:
        """Risk metrics from the calculator + open positions."""
        uid = self._uid_for_profile(profile_name)
        if not uid:
            return {"profile": profile_name, "available": False}
        _ensure_imports()
        from services.performance_calculator import PerformanceCalculator
        perf = PerformanceCalculator(self._get_store()).compute(uid)
        positions = self.positions_list(profile_name)
        exposure = {}
        for p in positions:
            sym = p.get("symbol", "")
            exposure[sym] = exposure.get(sym, 0.0) + (p.get("volume") or 0.0)
        return {
            "profile": profile_name,
            "available": True,
            "exposure_by_symbol": exposure,
            "exposure_by_direction": perf.get("exposure_by_direction", {"BUY": 0.0, "SELL": 0.0}),
            "max_consecutive_wins": perf.get("max_consecutive_wins", 0),
            "max_consecutive_losses": perf.get("max_consecutive_losses", 0),
            "max_balance_drawdown": perf.get("max_balance_drawdown"),
            "max_equity_drawdown": perf.get("max_equity_drawdown"),
            "recovery_factor": perf.get("recovery_factor"),
            "open_position_count": len(positions),
        }

    # ------------------------------------------------------------------ #
    # Stock screener (§9 Phase 6 — local EOD, mirrors web stock-advisor)
    # ------------------------------------------------------------------ #
    def screener_list(self, limit: int = 10) -> list:
        """Latest local EOD rows per symbol — public-safe, read-only."""
        try:
            import sqlite3
            db_path = _REPO_ROOT / "data" / "market.db"
            if not db_path.is_file():
                return []
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    """SELECT date, symbol, exchange, open, high, low, close,
                              volume, value, foreign_buy_value, foreign_sell_value
                       FROM eod_prices
                       WHERE date = (SELECT MAX(date) FROM eod_prices)
                       ORDER BY symbol
                       LIMIT ?""",
                    (limit,),
                ).fetchall()
            finally:
                conn.close()
            result = []
            for r in rows:
                result.append({
                    "date": r["date"], "symbol": r["symbol"], "exchange": r["exchange"],
                    "open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"],
                    "volume": r["volume"], "value": r["value"],
                    "foreign_buy_value": r["foreign_buy_value"],
                    "foreign_sell_value": r["foreign_sell_value"],
                })
            return result
        except Exception:
            return []
