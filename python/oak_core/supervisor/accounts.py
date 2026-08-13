# -*- coding: utf-8 -*-
"""Account-audit queries for the supervisor (Phase 3, Edit prompt.txt §9).

These handlers re-use the existing tested trade-audit stack
(``repositories.trade_audit_store``, ``services.performance_calculator``,
``services.audit_dashboard_publisher``) — the sidecar never re-implements
business logic.  Public-safe payloads only: no raw tickets, no account uid,
no credentials (the publisher builders already strip those).
"""
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from ..ipc.protocol import error_payload
from .profiles import _data_root

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: Checkpoint states that still count as an open position.
_OPEN_STATUSES = ("STILL_OPEN", "PARTIALLY_CLOSED")


def _ensure_imports():
    """Import the repo-root Python modules (dev layout). Best-effort."""
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))


def _store():
    _ensure_imports()
    from repositories.trade_audit_store import TradeAuditStore
    return TradeAuditStore(read_only=True)


# ------------------------------------------------------------------ #
# EOD background-thread helpers (pure, testable)
# ------------------------------------------------------------------ #
def _build_eod_cmd(target_date: str = "") -> list:
    """Command for the EOD collector subprocess (dev vs frozen oak-core)."""
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "eod_collector", "update"]
    else:
        cmd = [sys.executable, "-m", "oak_core", "eod_collector", "update"]
    if target_date:
        cmd += ["--date", str(target_date)]
    return cmd


_PROGRESS_RE = re.compile(r"\[VPS EOD\] (\d+)/(\d+) \((\d+)%\)")
_TOTAL_RE = re.compile(r"\[VPS EOD\] Fetching (\d+) symbols")
_SAVED_RE = re.compile(r"(\d+) records", re.IGNORECASE)


def _parse_eod_progress(line: str) -> dict | None:
    """Parse one collector stdout line into {percent,current,total,message} or None."""
    m = _PROGRESS_RE.search(line)
    if m:
        return {"percent": int(m.group(3)), "current": int(m.group(1)),
                "total": int(m.group(2)), "message": line.strip()}
    m = _TOTAL_RE.search(line)
    if m:
        return {"percent": 1, "current": 0, "total": int(m.group(1)), "message": line.strip()}
    m = _SAVED_RE.search(line)
    if m:
        return {"percent": 100, "current": 0, "total": 0, "message": line.strip()}
    return None


class AccountQueries:
    """Public-safe account / positions / checkpoints / performance queries."""

    def __init__(self, store=None, emit_event=None):
        self._store = store
        self._emit_event = emit_event

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
        """Open positions at the latest checkpoint — public-safe (no raw tickets).

        The ``positions`` table is append-only and retains historical /
        reconstructed rows, so the newest checkpoint's position states decide
        what is still open.  No checkpoint run (or no open state) means nothing
        is verified as open — never fall back to historical rows.
        """
        uid = self._uid_for_profile(profile_name)
        account_id = self._account_id(uid) if uid else None
        if not account_id:
            return []
        store = self._get_store()
        runs = store.list_checkpoint_runs(account_id=account_id, limit=1)
        if not runs:
            return []
        open_volumes = {}
        for state in store.list_checkpoint_position_states(runs[0].get("id")):
            if state.get("status_at_checkpoint") not in _OPEN_STATUSES:
                continue
            open_volumes[str(state.get("position_id") or "")] = state.get("volume")
        if not open_volumes:
            return []
        result = []
        for p in store.list_positions(account_id=account_id):
            position_id = str(p.get("position_id") or "")
            if position_id not in open_volumes:
                continue
            volume = open_volumes[position_id]
            result.append({
                "public_trade_id": p.get("public_trade_id") or "",
                "symbol": p.get("symbol", ""),
                "direction": p.get("direction", ""),
                "volume": volume if volume is not None else p.get("initial_volume"),
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

    def performance_summary(self, profile_name: str, since_utc=None) -> dict:
        """Performance metrics from the calculator — public-safe subset."""
        uid = self._uid_for_profile(profile_name)
        if not uid:
            return {"profile": profile_name, "available": False}
        _ensure_imports()
        from services.performance_calculator import PerformanceCalculator
        perf = PerformanceCalculator(self._get_store()).compute(
            uid, since_utc=since_utc
        )
        keys = (
            "current_balance", "current_equity", "net_profit", "realized_pl",
            "unrealized_pl", "profit_factor", "win_rate", "closed_trade_count",
            "winning_trade_count", "losing_trade_count", "win_rate_basis", "average_win",
            "average_loss", "expectancy", "max_equity_drawdown",
            "current_drawdown", "drawdown_source", "trading_return", "trading_return_pct",
            "account_growth", "account_growth_pct", "net_cash_flow", "total_commission",
            "total_swap", "total_fees",
        )
        return {
            "profile": profile_name,
            "available": True,
            **{k: perf.get(k) for k in keys},
        }

    def equity_curve(self, profile_name: str, limit: int = 500, since_utc=None) -> list:
        """Equity samples as a lightweight curve (time, equity) for charts."""
        uid = self._uid_for_profile(profile_name)
        account_id = self._account_id(uid) if uid else None
        if not account_id:
            return []
        samples = self._get_store().list_equity_samples(account_id=account_id, limit=limit)
        # list_equity_samples returns DESC — reverse to chronological.
        result = []
        for s in reversed(samples):
            t = s.get("sampled_at_utc")
            if since_utc is not None and t:
                try:
                    from datetime import datetime
                    ts = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
                    bound = since_utc if since_utc.tzinfo else since_utc.replace(tzinfo=ts.tzinfo)
                    if ts.tzinfo is None and bound.tzinfo is not None:
                        ts = ts.replace(tzinfo=bound.tzinfo)
                    if ts < bound:
                        continue
                except (TypeError, ValueError):
                    pass
            result.append({
                "t": t,
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
            db_path = _data_root() / "data" / "market.db"
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

    def update_eod(self, target_date: str = "") -> dict:
        """Start the EOD collector in a background thread; stream progress events.

        Returns immediately with {started: True}.  The thread spawns the collector
        subprocess, parses its stdout progress markers, emits ``eod.progress``
        events, and finishes with an ``eod.done`` event (ok + stdout tail).
        """
        cmd = _build_eod_cmd(target_date)
        emit = self._emit_event
        root = str(_data_root())

        def _worker() -> None:
            proc = None
            out_lines: list[str] = []
            try:
                proc = subprocess.Popen(
                    cmd, cwd=root, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, bufsize=1,
                )
                deadline = time.time() + 180
                for line in proc.stdout:
                    out_lines.append(line)
                    parsed = _parse_eod_progress(line)
                    if parsed and emit:
                        emit("eod.progress", parsed)
                    if time.time() > deadline:
                        proc.kill()
                        break
                proc.wait(timeout=5)
            except Exception as exc:  # noqa: BLE001 - report via event
                if emit:
                    emit("eod.done", {"ok": False, "returncode": None,
                                      "stdout": "".join(out_lines)[-2000:],
                                      "stderr": str(exc)})
                return
            if emit:
                emit("eod.done", {"ok": proc.returncode == 0,
                                  "returncode": proc.returncode,
                                  "stdout": "".join(out_lines)[-2000:],
                                  "stderr": ""})

        threading.Thread(target=_worker, daemon=True, name="eod-update").start()
        return {"started": True}

    def run_filter(self, limit: int = 10) -> dict:
        """Run the local-EOD D1 advisory scan (read-only, no orders).

        Mirrors vn_stock_advisor.run_advisor using the tested D1 scanner.
        """
        try:
            _ensure_imports()
            import sqlite3
            from datetime import datetime, timezone
            from domain.stock_scanner import ScannerPolicy, scan_d1_linear
            db_path = _data_root() / "data" / "market.db"
            if not db_path.is_file():
                return {"ok": True, "status": "NO_DATA", "as_of_date": "",
                        "scanned": 0, "buy": 0, "sell": 0, "recommendations": []}
            as_of = datetime.now(timezone.utc).date()
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT DISTINCT symbol FROM eod_prices ORDER BY symbol"
                ).fetchall()
                symbols = [r["symbol"] for r in rows]
                bars_by_symbol = {}
                for symbol in symbols:
                    bars = conn.execute(
                        "SELECT date, open, high, low, close, volume FROM eod_prices "
                        "WHERE symbol = ? AND date <= ? ORDER BY date ASC",
                        (symbol, as_of.isoformat()),
                    ).fetchall()
                    bars_by_symbol[symbol] = [dict(b) for b in bars]
            finally:
                conn.close()
            if not bars_by_symbol:
                return {"ok": True, "status": "NO_DATA", "as_of_date": as_of.isoformat(),
                        "scanned": 0, "buy": 0, "sell": 0, "recommendations": []}
            payload = scan_d1_linear(bars_by_symbol, as_of,
                                     policy=ScannerPolicy(history_window=20), capital=0.0)
            results = payload.get("results") or []
            recs = [r for r in results if r.get("rank") and r.get("rank") > 0]
            buy = sum(1 for r in results
                      if r.get("direction") == "BUY" and r.get("data_quality") == "OK")
            sell = sum(1 for r in results
                       if r.get("direction") == "SELL" and r.get("data_quality") == "OK")
            return {
                "ok": True,
                "status": payload.get("status", "NO_TRADE"),
                "as_of_date": payload.get("as_of_date", as_of.isoformat()),
                "scanned": len(results),
                "buy": buy,
                "sell": sell,
                "recommendations": [
                    {"symbol": r.get("symbol"), "direction": r.get("direction"),
                     "score": r.get("score"), "latest_close": r.get("latest_close"),
                     "rank": r.get("rank")}
                    for r in recs
                ][:limit],
            }
        except Exception as exc:
            return {"ok": False, "status": "ERROR", "as_of_date": "",
                    "scanned": 0, "buy": 0, "sell": 0, "recommendations": [],
                    "error": str(exc)}
