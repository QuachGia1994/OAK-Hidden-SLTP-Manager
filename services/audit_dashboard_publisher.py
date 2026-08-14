# -*- coding: utf-8 -*-
"""Public-safe dashboard publisher for the trade audit ledger (§10, §11).

Builds JSON payloads from TradeAuditStore that never expose raw MT5 login,
server credentials, account numbers, tokens, or local file paths.
Generates stable, non-reversible public trade IDs via HMAC-SHA256.
Pushes payloads to configurable dashboard endpoints over HTTP.
"""
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from oak_logger import setup_logger
from services.public_freshness import (
    SOURCE_CHECKPOINT,
    SOURCE_EQUITY_SAMPLE,
    SOURCE_MT5_LIVE,
    SOURCE_NONE,
    SOURCE_STORE,
    build_freshness_envelope,
    parse_utc,
)

log = setup_logger("audit_dashboard_pub")

DEFAULT_PUBLIC_ALIAS = "OAK Trader"

# Public portal period windows (calendar days, UTC lower bound).
PUBLIC_PERIOD_DAYS = {
    "all": None,
    "1w": 7,
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
}

# Relative endpoints for the trade audit dashboard.
_ENDPOINTS = {
    "overview":     "/api/trade-audit/overview",
    "positions":    "/api/trade-audit/positions",
    "checkpoints":  "/api/trade-audit/checkpoints",
    "ledger":       "/api/trade-audit/ledger",
    "performance":  "/api/trade-audit/performance",
    "risk":         "/api/trade-audit/risk",
    "audit":        "/api/trade-audit/audit",
    "equity":       "/api/trade-audit/equity",
    "live":         "/api/trade-audit/live",
}

# Public-safe subset of performance calculator keys.
_PUBLIC_PERF_KEYS = frozenset({
    "current_balance", "current_equity", "net_profit", "realized_pl",
    "unrealized_pl", "profit_factor", "win_rate", "closed_trade_count",
    "winning_trade_count", "losing_trade_count", "win_rate_basis", "average_win",
    "average_loss", "expectancy", "max_equity_drawdown", "current_drawdown",
    "drawdown_source", "total_commission", "total_swap", "total_fees",
    "trading_return", "trading_return_pct", "account_growth", "account_growth_pct", "net_cash_flow",
})

# Trading deal types for filtering.
_TRADING_DEAL_TYPES = frozenset({"BUY", "SELL"})


# ---------------------------------------------------------------------- #
# Config helper
# ---------------------------------------------------------------------- #
def _read_config():
    """Read config.json from project root (best-effort, returns {})."""
    config_path = Path(__file__).resolve().parent.parent / "config.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------- #
# Public identity functions
# ---------------------------------------------------------------------- #
def public_trade_id(account_uid, position_id, secret):
    """HMAC-SHA256 hex digest: stable, non-reversible public trade ID.

    Canonical string: ``account_uid::position_id``.
    If *secret* is empty/None, falls back to plain SHA-256 (still one-way)
    and logs a warning.
    """
    if not position_id:
        return ""
    canonical = f"{account_uid}::{position_id}"
    if not secret:
        log.warning(
            "public_trade_id: no secret provided; falling back to SHA-256 "
            "(non-reversible but not HMAC-protected)"
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def public_alias_for(account):
    """Return the public alias for an account dict, or the default."""
    return account.get("public_alias") or DEFAULT_PUBLIC_ALIAS


def public_account_id(account_uid, secret=""):
    """Stable public-safe account identifier (non-reversible).

    Safe to expose in URLs/Redis namespaces. Never equals the raw internal uid.
    """
    canonical = f"account::{account_uid}"
    if secret:
        digest = hmac.new(
            secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
        ).hexdigest()
    else:
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:16]


def period_since_utc(period_key, now=None):
    """UTC lower bound for a public period key; None = all history."""
    days = PUBLIC_PERIOD_DAYS.get(period_key)
    if days is None:
        return None
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now - timedelta(days=int(days))


# ---------------------------------------------------------------------- #
# Publisher class
# ---------------------------------------------------------------------- #
class AuditDashboardPublisher:
    """Build public-safe payloads and push them to the dashboard."""

    def __init__(self, store, calculator=None, secret=None,
                 dashboard_url=None, api_key=None):
        self._store = store
        self._calculator = calculator
        self._secret = secret or os.environ.get("PUBLIC_TRADE_ID_SECRET", "")
        cfg = _read_config()
        # None sentinel → fall back to env / config.json; explicit "" means disabled.
        self._dashboard_url = (
            dashboard_url
            if dashboard_url is not None
            else (os.environ.get("DASHBOARD_API_URL", "")
                  or cfg.get("dashboard_url", ""))
        )
        self._api_key = (
            api_key
            if api_key is not None
            else (os.environ.get("DASHBOARD_API_KEY", "")
                  or cfg.get("dashboard_api_key", ""))
        )

    @property
    def _calc(self):
        """Lazy-create PerformanceCalculator."""
        if self._calculator is None:
            from services.performance_calculator import PerformanceCalculator
            self._calculator = PerformanceCalculator(self._store)
        return self._calculator

    def _account_id(self, account_uid):
        """Resolve account row id or None."""
        acct = self._store.get_account_by_uid(account_uid)
        return acct["id"] if acct else None

    def _account_dict(self, account_uid):
        """Return full account row as dict or empty dict."""
        acct = self._store.get_account_by_uid(account_uid)
        return dict(acct) if acct else {}

    def _ptid(self, account_uid, position_id):
        """Public trade id shorthand."""
        return public_trade_id(account_uid, position_id, self._secret)

    # ------------------------------------------------------------------ #
    # Builder methods
    # ------------------------------------------------------------------ #
    def build_overview(self, account_uid):
        """Account overview: balance/equity/floating/margin/drawdown."""
        acct = self._account_dict(account_uid)
        account_id = acct.get("id")

        # Latest equity sample (most recent by sampled_at_utc).
        samples = self._store.list_equity_samples(account_id=account_id, limit=1) if account_id else []
        snapshots = self._store.list_snapshots(account_id=account_id) if account_id else []

        if samples:
            s = samples[0]
            balance = s.get("balance")
            equity = s.get("equity")
            floating = s.get("open_profit")
            margin = s.get("margin")
            free_margin = s.get("free_margin")
            margin_level = s.get("margin_level")
        elif snapshots:
            s = snapshots[-1]
            balance = s.get("balance")
            equity = s.get("equity")
            floating = s.get("open_profit")
            margin = s.get("margin")
            free_margin = s.get("free_margin")
            margin_level = s.get("margin_level")
        else:
            balance = None
            equity = None
            floating = None
            margin = None
            free_margin = None
            margin_level = None

        perf = self._calc.compute(account_uid)

        configured_at = acct.get("created_at_utc") or acct.get("created_at") or None
        trading_started = None
        if account_id:
            deals = self._store.list_deals(account_id=account_id) or []
            times = [
                d.get("deal_time_utc") for d in deals
                if d.get("deal_type") in _TRADING_DEAL_TYPES and d.get("deal_time_utc")
            ]
            if times:
                trading_started = min(times)

        observed = None
        source = SOURCE_NONE
        if samples:
            observed = samples[0].get("sampled_at_utc")
            source = SOURCE_EQUITY_SAMPLE
        elif snapshots:
            observed = snapshots[-1].get("captured_at_utc") or snapshots[-1].get("snapshot_at_utc")
            source = SOURCE_STORE
        published = datetime.now(timezone.utc)
        freshness = build_freshness_envelope(
            observed_at_utc=observed,
            published_at_utc=published,
            source=source,
            now_utc=published,
        )
        return {
            "alias": public_alias_for(acct),
            "broker": acct.get("broker", ""),
            "platform": acct.get("platform") or "MetaTrader 5",
            "account_type": acct.get("account_type") or acct.get("type") or "",
            "currency": acct.get("currency", ""),
            "balance": balance,
            "equity": equity,
            "floating_pl": floating,
            "margin": margin,
            "free_margin": free_margin,
            "margin_level": margin_level,
            "current_drawdown": perf.get("current_drawdown"),
            "drawdown_source": perf.get("drawdown_source", "NONE"),
            "configured_at_utc": configured_at,
            "trading_started_at_utc": trading_started,
            "closed_trade_count": perf.get("closed_trade_count"),
            "updated_at_utc": published.isoformat(),
            **freshness,
        }

    def _latest_checkpoint_mark(self, account_id, position_id):
        """Best-effort live mark from newest checkpoint state for a position."""
        if not account_id or not position_id:
            return None
        runs = self._store.list_checkpoint_runs(account_id=account_id, limit=5) or []
        for run in runs:  # newest first (DESC)
            run_id = run.get("id")
            if run_id is None:
                continue
            states = self._store.list_checkpoint_position_states(run_id) if hasattr(
                self._store, "list_checkpoint_position_states"
            ) else []
            if not states and hasattr(self._store, "list_checkpoint_states"):
                states = self._store.list_checkpoint_states(run_id) or []
            for st in states or []:
                if str(st.get("position_id") or "") != str(position_id):
                    continue
                fp = st.get("floating_profit")
                cp = st.get("current_price")
                if fp is not None or cp is not None:
                    return {
                        "floating_profit": fp,
                        "current_price": cp,
                        "mark_source": "CHECKPOINT",
                        "mark_time_utc": run.get("captured_at_utc"),
                    }
        return None

    def build_positions(self, account_uid):
        """Live positions — public-safe, no raw identity leakage.

        Floating P&L contract:
        - If a trustworthy mark exists → publish floating_profit + current_price.
        - If unavailable → floating_available=False and nulls (never invent 0).
        """
        account_id = self._account_id(account_uid)
        if not account_id:
            return []

        positions = self._store.list_positions(account_id=account_id)
        result = []
        for p in positions:
            mark = self._latest_checkpoint_mark(account_id, p.get("position_id", ""))
            if mark and (mark.get("floating_profit") is not None or mark.get("current_price") is not None):
                floating = mark.get("floating_profit")
                current = mark.get("current_price")
                available = True
                mark_source = mark.get("mark_source")
                mark_time = mark.get("mark_time_utc")
            else:
                floating = None
                current = None
                available = False
                mark_source = None
                mark_time = None
            result.append({
                "public_trade_id": self._ptid(account_uid, p.get("position_id", "")),
                "symbol": p.get("symbol", ""),
                "direction": p.get("direction", ""),
                "volume": p.get("initial_volume"),
                "open_price": p.get("open_price"),
                "current_price": current,
                "open_time_utc": p.get("open_time_utc"),
                "sl": None,
                "tp": None,
                "floating_profit": floating,
                "floating_available": available,
                "mark_source": mark_source,
                "mark_time_utc": mark_time,
                "source_type": p.get("source_type", ""),
            })
        return result

    def build_checkpoints(self, account_uid, limit=30):
        """Checkpoint timeline — chronological ascending."""
        account_id = self._account_id(account_uid)
        if not account_id:
            return []

        runs = self._store.list_checkpoint_runs(account_id=account_id, limit=limit)
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
                "error": r.get("error"),
            })
        # list_checkpoint_runs returns DESC; reverse to chronological ASC.
        result.reverse()
        return result

    def build_ledger(self, account_uid, limit=200):
        """Trade ledger entries — filtered to BUY/SELL only."""
        account_id = self._account_id(account_uid)
        if not account_id:
            return []

        deals = self._store.list_deals(account_id=account_id)
        result = []
        for d in deals:
            if d.get("deal_type") not in _TRADING_DEAL_TYPES:
                continue
            result.append({
                "public_trade_id": self._ptid(account_uid, d.get("position_id", "")),
                "symbol": d.get("symbol", ""),
                "deal_type": d.get("deal_type", ""),
                "entry_type": d.get("entry_type", ""),
                "reason_category": d.get("reason_category", ""),
                "volume": d.get("volume"),
                "price": d.get("price"),
                "profit": d.get("profit"),
                "commission": d.get("commission"),
                "swap": d.get("swap"),
                "fee": d.get("fee"),
                "deal_time_utc": d.get("deal_time_utc"),
            })
        return result[:limit]

    def _public_perf_slice(self, account_uid, period_key, now=None):
        """Canonical performance for one period window (backend-computed).

        Public Net P&L is *realized* closed-trade profit only. Floating/unrealized
        must never substitute into net_profit on the investor portal.
        """
        since = period_since_utc(period_key, now=now)
        perf = self._calc.compute(account_uid, since_utc=since)
        out = {k: perf.get(k) for k in _PUBLIC_PERF_KEYS if k in perf}
        realized = perf.get("realized_pl")
        closed_n = int(perf.get("closed_trade_count") or 0)
        if closed_n > 0:
            # Realized closed-trade profit only (0 is a valid result).
            out["net_profit"] = realized if realized is not None else perf.get("net_profit")
        else:
            # No closed trades → explicit null (never substitute floating/unrealized).
            out["net_profit"] = None
        out["realized_pl"] = realized
        out["unrealized_pl"] = perf.get("unrealized_pl")
        out["period_key"] = period_key
        out["period_label"] = "all_history" if period_key == "all" else period_key
        out["since_utc"] = since.isoformat() if since is not None else None
        out["available"] = bool(out.get("closed_trade_count") or out.get("current_equity") is not None)
        return out

    def build_performance(self, account_uid):
        """Public-safe performance: all-history plus by_period canonical slices."""
        now = datetime.now(timezone.utc)
        by_period = {
            key: self._public_perf_slice(account_uid, key, now=now)
            for key in PUBLIC_PERIOD_DAYS
        }
        # Top-level remains all-history for backward-compatible consumers.
        out = dict(by_period["all"])
        out["by_period"] = by_period
        return out

    def build_equity(self, account_uid, limit=2000):
        """Public equity/balance series for charts (no account secrets)."""
        account_id = self._account_id(account_uid)
        if not account_id:
            return []
        samples = self._store.list_equity_samples(account_id=account_id, limit=limit) or []
        series = []
        for s in reversed(samples):  # chronological ascending
            series.append({
                "t": s.get("sampled_at_utc"),
                "equity": s.get("equity"),
                "balance": s.get("balance"),
                "floating_pl": s.get("open_profit"),
            })
        return series

    def build_risk(self, account_uid):
        """Risk metrics from calculator + store."""
        perf = self._calc.compute(account_uid)
        account_id = self._account_id(account_uid)

        # Largest single loss: min profit among close deals.
        largest_single_loss = None
        if account_id:
            deals = self._store.list_deals(account_id=account_id)
            close_profits = []
            _close_entry = frozenset({"OUT", "INOUT", "OUT_BY", "CLOSEBY"})
            for d in deals:
                if (d.get("entry_type") in _close_entry
                        and d.get("deal_type") in _TRADING_DEAL_TYPES):
                    val = d.get("profit")
                    if val is not None:
                        close_profits.append(val)
            if close_profits:
                largest_single_loss = min(close_profits)

        # Margin usage: guard div/0.
        margin_level = None
        samples = self._store.list_equity_samples(account_id=account_id, limit=1) if account_id else []
        if samples:
            margin_level = samples[0].get("margin_level")
        margin_usage_pct = None
        if margin_level and margin_level != 0:
            margin_usage_pct = 10000.0 / margin_level

        # Open position count.
        open_count = 0
        if account_id:
            positions = self._store.list_positions(account_id=account_id)
            open_count = len(positions)

        return {
            "exposure_by_symbol": perf.get("exposure_by_symbol", {}),
            "exposure_by_direction": perf.get("exposure_by_direction", {"BUY": 0.0, "SELL": 0.0}),
            "max_consecutive_wins": perf.get("max_consecutive_wins", 0),
            "max_consecutive_losses": perf.get("max_consecutive_losses", 0),
            "max_balance_drawdown": perf.get("max_balance_drawdown"),
            "recovery_factor": perf.get("recovery_factor"),
            "margin_usage_pct": margin_usage_pct,
            "largest_single_loss": largest_single_loss,
            "open_position_count": open_count,
        }

    def build_audit(self, account_uid):
        """Audit info: capture modes, last sync, reconciliation status."""
        acct = self._account_dict(account_uid)
        account_id = acct.get("id")

        # Capture mode counts.
        capture_modes = {}
        last_checkpoint = None
        if account_id:
            runs = self._store.list_checkpoint_runs(account_id=account_id, limit=500)
            for r in runs:
                mode = r.get("capture_mode", "NORMAL")
                capture_modes[mode] = capture_modes.get(mode, 0) + 1
                cat = r.get("captured_at_utc")
                if cat and (last_checkpoint is None or cat > last_checkpoint):
                    last_checkpoint = cat

        # Reconciler cursor.
        reconciled_utc = None
        if account_uid:
            reconciled_utc = self._store.get_setting(
                f"reconciler.last_reconciled_utc.{account_uid}"
            )

        return {
            "alias": public_alias_for(acct),
            "capture_modes": capture_modes,
            "last_checkpoint_at_utc": last_checkpoint,
            "missing_intervals": [],
            "reconciliation_status": "OK" if reconciled_utc else "NOT_RECONCILED",
        }

    def build_positions_from_observation(self, account_uid, positions, observed_at_utc=None):
        """Public positions from a live MT5 observation (not store lag).

        Each raw position dict may include: symbol, direction/type, volume,
        price_open/open_price, price_current/current_price, profit, ticket/position_id.
        Never invents floating 0 when profit is missing.
        """
        observed = parse_utc(observed_at_utc) or datetime.now(timezone.utc)
        result = []
        for p in positions or []:
            if not isinstance(p, dict):
                # MT5 namedtuple / object
                p = {
                    "symbol": getattr(p, "symbol", ""),
                    "direction": getattr(p, "type", None),
                    "volume": getattr(p, "volume", None),
                    "open_price": getattr(p, "price_open", None),
                    "current_price": getattr(p, "price_current", None),
                    "profit": getattr(p, "profit", None),
                    "position_id": getattr(p, "ticket", getattr(p, "identifier", "")),
                    "time": getattr(p, "time", None),
                }
            pid = str(p.get("position_id") or p.get("ticket") or p.get("identifier") or "")
            direction = p.get("direction") or p.get("type") or ""
            if direction in (0, "0"):
                direction = "BUY"
            elif direction in (1, "1"):
                direction = "SELL"
            else:
                direction = str(direction).upper()
            cur = p.get("current_price", p.get("price_current"))
            fp = p.get("floating_profit", p.get("profit"))
            available = fp is not None or cur is not None
            result.append({
                "public_trade_id": self._ptid(account_uid, pid),
                "symbol": p.get("symbol", ""),
                "direction": direction,
                "volume": p.get("volume", p.get("initial_volume")),
                "open_price": p.get("open_price", p.get("price_open")),
                "current_price": cur,
                "open_time_utc": p.get("open_time_utc"),
                "sl": p.get("sl"),
                "tp": p.get("tp"),
                "floating_profit": fp if available else None,
                "floating_available": bool(available and fp is not None),
                "mark_source": SOURCE_MT5_LIVE if available else None,
                "mark_time_utc": observed.isoformat() if available else None,
                "observed_at_utc": observed.isoformat(),
                "source_type": "LIVE",
            })
        return result

    def build_live(self, account_uid, account_info=None, positions=None, observed_at_utc=None):
        """Realtime transparency envelope for the public portal.

        When *account_info* is provided, metrics are taken from the live
        observation; otherwise falls back to store equity samples (may be STALE).
        Closed-trade performance is intentionally NOT included here.
        """
        published = datetime.now(timezone.utc)
        observed = parse_utc(observed_at_utc) or published
        acct = self._account_dict(account_uid)

        if account_info:
            balance = account_info.get("balance")
            equity = account_info.get("equity")
            floating = account_info.get("open_profit", account_info.get("profit"))
            source = SOURCE_MT5_LIVE
            pos_list = self.build_positions_from_observation(
                account_uid, positions or [], observed_at_utc=observed,
            )
        else:
            overview = self.build_overview(account_uid)
            balance = overview.get("balance")
            equity = overview.get("equity")
            floating = overview.get("floating_pl")
            source = overview.get("source") or SOURCE_STORE
            observed = parse_utc(overview.get("observed_at_utc")) or observed
            pos_list = self.build_positions(account_uid)

        freshness = build_freshness_envelope(
            observed_at_utc=observed,
            published_at_utc=published,
            source=source,
            now_utc=published,
        )
        return {
            "public_account_id": public_account_id(account_uid, self._secret),
            "alias": public_alias_for(acct),
            "balance": balance,
            "equity": equity,
            "floating_profit": floating,
            "positions_count": len(pos_list),
            "open_positions": pos_list,
            "realized_performance_note": (
                "Closed-trade KPIs are period-scoped historical metrics; "
                "floating P&L is separate and does not alter win-rate."
            ),
            **freshness,
        }

    def build_all(self, account_uid):
        """Build all sections into a single dict (namespaced by public account id)."""
        acct = self._account_dict(account_uid)
        pub_id = public_account_id(account_uid, self._secret)
        live = self.build_live(account_uid)
        return {
            "public_account_id": pub_id,
            "alias": public_alias_for(acct),
            "overview":     self.build_overview(account_uid),
            "positions":    self.build_positions(account_uid),
            "checkpoints":  self.build_checkpoints(account_uid),
            "ledger":       self.build_ledger(account_uid),
            "performance":  self.build_performance(account_uid),
            "risk":         self.build_risk(account_uid),
            "audit":        self.build_audit(account_uid),
            "equity":       self.build_equity(account_uid),
            "live":         live,
        }

    def push_live(self, account_uid, account_info=None, positions=None, observed_at_utc=None):
        """Lightweight push of live overview+positions+live envelope.

        On HTTP failure: does not clear prior Redis values (server retains last good).
        """
        if not self._dashboard_url:
            return {"pushed": False, "reason": "no dashboard url", "results": {}}

        published = datetime.now(timezone.utc)
        observed = parse_utc(observed_at_utc) or published
        live = self.build_live(
            account_uid,
            account_info=account_info,
            positions=positions,
            observed_at_utc=observed,
        )
        # Align overview metrics with live observation when available.
        overview = self.build_overview(account_uid)
        if account_info:
            overview["balance"] = account_info.get("balance")
            overview["equity"] = account_info.get("equity")
            overview["floating_pl"] = account_info.get("open_profit", account_info.get("profit"))
            overview["margin"] = account_info.get("margin")
            overview["free_margin"] = account_info.get("free_margin")
            overview["margin_level"] = account_info.get("margin_level")
            overview.update(build_freshness_envelope(
                observed_at_utc=observed,
                published_at_utc=published,
                source=SOURCE_MT5_LIVE,
                now_utc=published,
            ))
            overview["updated_at_utc"] = published.isoformat()
        positions_payload = live.get("open_positions") or []

        pub_id = live.get("public_account_id") or public_account_id(account_uid, self._secret)
        base = self._dashboard_url.rstrip("/")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key

        results = {}
        all_ok = True
        for section, data in (
            ("live", live),
            ("overview", overview),
            ("positions", positions_payload),
        ):
            endpoint = _ENDPOINTS[section]
            url = f"{base}{endpoint}?account={pub_id}"
            try:
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=15) as resp:
                    results[section] = {"ok": True, "status": resp.status, "error": None}
            except Exception as exc:
                results[section] = {"ok": False, "status": None, "error": str(exc)}
                all_ok = False
        return {
            "pushed": all_ok,
            "results": results,
            "public_account_id": pub_id,
            "observed_at_utc": live.get("observed_at_utc"),
            "published_at_utc": live.get("published_at_utc"),
            "source_status": live.get("source_status"),
        }

    # ------------------------------------------------------------------ #
    # Push
    # ------------------------------------------------------------------ #
    def push_all(self, account_uid):
        """Push all built payloads to dashboard endpoints.

        Returns ``{"pushed": bool, "results": {...}}``.
        Never raises; fail-closed on any HTTP error.
        """
        if not self._dashboard_url:
            return {
                "pushed": False,
                "reason": "no dashboard url",
                "results": {},
            }

        base = self._dashboard_url.rstrip("/")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key

        payloads = self.build_all(account_uid)
        pub_id = payloads.get("public_account_id") or public_account_id(account_uid, self._secret)
        results = {}
        all_ok = True

        # Register public account metadata (alias only — no secrets).
        try:
            reg_body = json.dumps({
                "public_account_id": pub_id,
                "alias": payloads.get("alias") or DEFAULT_PUBLIC_ALIAS,
            }, ensure_ascii=False).encode("utf-8")
            reg_url = f"{base}/api/trade-audit/accounts?account={pub_id}"
            reg_req = urllib.request.Request(
                reg_url, data=reg_body, headers=headers, method="POST",
            )
            with urllib.request.urlopen(reg_req, timeout=15) as resp:
                results["accounts"] = {"ok": True, "status": resp.status, "error": None}
        except Exception as exc:
            results["accounts"] = {"ok": False, "status": None, "error": str(exc)}
            all_ok = False

        for section, endpoint in _ENDPOINTS.items():
            data = payloads.get(section)
            payload_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
            # Namespace every section by public account id (multi-profile isolation).
            url = f"{base}{endpoint}?account={pub_id}"
            try:
                req = urllib.request.Request(
                    url, data=payload_bytes, headers=headers, method="POST",
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    results[section] = {"ok": True, "status": resp.status, "error": None}
            except urllib.error.HTTPError as exc:
                results[section] = {"ok": False, "status": exc.code, "error": str(exc)}
                all_ok = False
            except urllib.error.URLError as exc:
                results[section] = {"ok": False, "status": None, "error": str(exc)}
                all_ok = False
            except Exception as exc:
                results[section] = {"ok": False, "status": None, "error": str(exc)}
                all_ok = False

        return {"pushed": all_ok, "results": results, "public_account_id": pub_id}
