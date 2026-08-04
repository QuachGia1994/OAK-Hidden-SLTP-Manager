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
from datetime import datetime, timezone
from pathlib import Path

from oak_logger import setup_logger

log = setup_logger("audit_dashboard_pub")

DEFAULT_PUBLIC_ALIAS = "OAK Trader"

# Relative endpoints for the trade audit dashboard.
_ENDPOINTS = {
    "overview":     "/api/trade-audit/overview",
    "positions":    "/api/trade-audit/positions",
    "checkpoints":  "/api/trade-audit/checkpoints",
    "ledger":       "/api/trade-audit/ledger",
    "performance":  "/api/trade-audit/performance",
    "risk":         "/api/trade-audit/risk",
    "audit":        "/api/trade-audit/audit",
}

# Public-safe subset of performance calculator keys.
_PUBLIC_PERF_KEYS = frozenset({
    "current_balance", "current_equity", "net_profit", "realized_pl",
    "unrealized_pl", "profit_factor", "win_rate", "average_win",
    "average_loss", "expectancy", "max_equity_drawdown", "current_drawdown",
    "drawdown_source", "total_commission", "total_swap", "total_fees",
    "trading_return", "account_growth", "net_cash_flow",
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

        return {
            "alias": public_alias_for(acct),
            "broker": acct.get("broker", ""),
            "currency": acct.get("currency", ""),
            "balance": balance,
            "equity": equity,
            "floating_pl": floating,
            "margin": margin,
            "free_margin": free_margin,
            "margin_level": margin_level,
            "current_drawdown": perf.get("current_drawdown"),
            "drawdown_source": perf.get("drawdown_source", "NONE"),
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def build_positions(self, account_uid):
        """Live positions — public-safe, no raw identity leakage."""
        account_id = self._account_id(account_uid)
        if not account_id:
            return []

        positions = self._store.list_positions(account_id=account_id)
        result = []
        for p in positions:
            result.append({
                "public_trade_id": self._ptid(account_uid, p.get("position_id", "")),
                "symbol": p.get("symbol", ""),
                "direction": p.get("direction", ""),
                "volume": p.get("initial_volume"),
                "open_price": p.get("open_price"),
                "open_time_utc": p.get("open_time_utc"),
                "sl": None,
                "tp": None,
                "floating_profit": None,
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

    def build_performance(self, account_uid):
        """Public-safe performance metrics (subset of calculator output)."""
        perf = self._calc.compute(account_uid)
        return {k: perf.get(k) for k in _PUBLIC_PERF_KEYS if k in perf}

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

    def build_all(self, account_uid):
        """Build all sections into a single dict."""
        return {
            "overview":     self.build_overview(account_uid),
            "positions":    self.build_positions(account_uid),
            "checkpoints":  self.build_checkpoints(account_uid),
            "ledger":       self.build_ledger(account_uid),
            "performance":  self.build_performance(account_uid),
            "risk":         self.build_risk(account_uid),
            "audit":        self.build_audit(account_uid),
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
        results = {}
        all_ok = True

        for section, endpoint in _ENDPOINTS.items():
            data = payloads.get(section)
            payload_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
            url = f"{base}{endpoint}"
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

        return {"pushed": all_ok, "results": results}
