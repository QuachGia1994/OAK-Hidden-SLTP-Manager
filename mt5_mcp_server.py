# -*- coding: utf-8 -*-
"""Read-only MCP server exposing MT5 audit-ledger reports (Phase 1 prototype).

Scope guarantees
----------------
* The server never opens a terminal connection and never imports the broker
  trading API — every answer comes from the local append-only audit ledger
  (``data/trade_audit.db``).
* SQLite is opened through an immutable / ``mode=ro`` URI with
  ``PRAGMA query_only=ON``: the ledger file is never written, and no ``-wal`` /
  ``-shm`` sidecar is produced by this adapter.
* Only report tools are registered. There is no trading, control or mutation
  surface, not even as a stub.
* Profiles must be allow-listed through ``OAK_MCP_PROFILES``; the database
  location comes from ``OAK_MCP_AUDIT_DB`` (or the repo default) and can never
  be supplied by a tool argument.

Transport: stdio. JSON-RPC owns stdout, so all diagnostics go to stderr.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

_REPO_ROOT = Path(__file__).resolve().parent
for _path in (str(_REPO_ROOT), str(_REPO_ROOT / "python")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from mcp.server.fastmcp import FastMCP  # noqa: E402
from oak_core.supervisor.accounts import AccountQueries  # noqa: E402

SOURCE = "audit_ledger"
LEDGER_NOTE = "Derived from the append-only audit ledger; not a live position snapshot."

_DB_ENV = "OAK_MCP_AUDIT_DB"
_PROFILES_ENV = "OAK_MCP_PROFILES"
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9._#\-]{1,32}$")
_TRADING_DEAL_TYPES = ("BUY", "SELL")

log = logging.getLogger("mt5_mcp_audit")
if not log.handlers:  # stderr only — stdout belongs to the MCP transport.
    _stderr_handler = logging.StreamHandler(sys.stderr)
    _stderr_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s - %(message)s")
    )
    log.addHandler(_stderr_handler)
    log.setLevel(logging.INFO)


# --------------------------------------------------------------------------- #
# Query-only ledger adapter
# --------------------------------------------------------------------------- #
class ReadOnlyAuditStore:
    """Query-only SQLite view over the trade-audit ledger.

    Exposes the SELECT-backed subset consumed by ``AccountQueries`` and
    ``PerformanceCalculator``. It has no insert/update/delete/migration path
    and holds no reference to the writable ledger store.
    """

    def __init__(self, db_path: str | Path):
        path = Path(db_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"audit database not found: {path}")
        self._db_path = path
        self._conn = sqlite3.connect(self.read_only_uri(path), uri=True)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA query_only=ON")

    @staticmethod
    def read_only_uri(path: Path) -> str:
        """Absolute ``file://`` URI that forbids any write to the ledger.

        ``immutable=1`` keeps SQLite from materialising ``-wal`` / ``-shm``
        sidecars next to a WAL-mode ledger; ``mode=ro`` blocks writes.
        """
        posix = path.as_posix()
        if not posix.startswith("/"):
            posix = "/" + posix
        return "file://" + quote(posix, safe="/:") + "?immutable=1&mode=ro"

    @property
    def db_path(self) -> Path:
        return self._db_path

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # -- internals ---------------------------------------------------------- #
    def _rows(self, sql: str, params: tuple = ()) -> list[dict]:
        return [dict(row) for row in self._conn.execute(sql, params).fetchall()]

    # -- accounts ----------------------------------------------------------- #
    def get_account_by_uid(self, account_uid) -> dict | None:
        rows = self._rows("SELECT * FROM accounts WHERE account_uid=?", (account_uid,))
        return rows[0] if rows else None

    def list_accounts(self) -> list[dict]:
        return self._rows("SELECT * FROM accounts ORDER BY id")

    # -- ledger reads ------------------------------------------------------- #
    def list_positions(self, account_id=None) -> list[dict]:
        if account_id is None:
            return self._rows("SELECT * FROM positions ORDER BY id")
        return self._rows(
            "SELECT * FROM positions WHERE account_id=? ORDER BY id", (account_id,)
        )

    def list_deals(self, account_id=None, position_id=None) -> list[dict]:
        sql = "SELECT * FROM deals"
        conds, params = [], []
        if account_id is not None:
            conds.append("account_id=?")
            params.append(account_id)
        if position_id is not None:
            conds.append("position_id=?")
            params.append(str(position_id))
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        return self._rows(sql + " ORDER BY id", tuple(params))

    def list_snapshots(self, account_id=None) -> list[dict]:
        if account_id is None:
            return self._rows("SELECT * FROM account_snapshots ORDER BY id")
        return self._rows(
            """SELECT s.* FROM account_snapshots s
               JOIN checkpoint_runs c ON s.checkpoint_run_id = c.id
               WHERE c.account_id=? ORDER BY s.id""",
            (account_id,),
        )

    def list_checkpoint_runs(self, account_id=None, limit=200) -> list[dict]:
        if account_id is None:
            return self._rows(
                "SELECT * FROM checkpoint_runs "
                "ORDER BY broker_date DESC, checkpoint_hour DESC LIMIT ?",
                (limit,),
            )
        return self._rows(
            "SELECT * FROM checkpoint_runs WHERE account_id=? "
            "ORDER BY broker_date DESC, checkpoint_hour DESC LIMIT ?",
            (account_id, limit),
        )

    def list_checkpoint_position_states(self, checkpoint_run_id) -> list[dict]:
        return self._rows(
            "SELECT * FROM checkpoint_position_states "
            "WHERE checkpoint_run_id=? ORDER BY id",
            (checkpoint_run_id,),
        )

    def list_equity_samples(self, account_id=None, limit=100000) -> list[dict]:
        if account_id is None:
            return self._rows(
                "SELECT * FROM equity_samples ORDER BY sampled_at_utc DESC LIMIT ?",
                (limit,),
            )
        return self._rows(
            "SELECT * FROM equity_samples WHERE account_id=? "
            "ORDER BY sampled_at_utc DESC LIMIT ?",
            (account_id, limit),
        )

    def list_cash_flows(self, account_id=None) -> list[dict]:
        if account_id is None:
            return self._rows("SELECT * FROM cash_flows ORDER BY time_utc")
        return self._rows(
            "SELECT * FROM cash_flows WHERE account_id=? ORDER BY time_utc", (account_id,)
        )

    # -- audit chain -------------------------------------------------------- #
    @staticmethod
    def _canonical_payload(payload) -> str:
        if isinstance(payload, str):
            payload = {"message": payload}
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def verify_audit_chain(self, account_id) -> dict:
        """Re-hash the per-account event chain without touching the file."""
        rows = self._rows(
            "SELECT * FROM audit_events WHERE account_id=? ORDER BY id", (account_id,)
        )
        previous_hash = ""
        for index, row in enumerate(rows):
            if row["previous_hash"] != previous_hash:
                return {"ok": False, "events": len(rows), "first_broken": index}
            payload = self._canonical_payload(json.loads(row["payload_json"] or "{}"))
            chain_source = (
                f"{row['previous_hash']}|{row['event_time_utc']}|{row['event_type']}"
                f"|{row['entity_type']}|{row['entity_id']}|{payload}"
            )
            expected = hashlib.sha256(chain_source.encode("utf-8")).hexdigest()
            if row["record_hash"] != expected:
                return {"ok": False, "events": len(rows), "first_broken": index}
            previous_hash = row["record_hash"]
        return {"ok": True, "events": len(rows), "first_broken": None}


# --------------------------------------------------------------------------- #
# Configuration / validation
# --------------------------------------------------------------------------- #
def resolve_db_path() -> Path:
    """Ledger location from the environment only — never from tool arguments."""
    configured = (os.environ.get(_DB_ENV) or "").strip()
    path = Path(configured) if configured else _REPO_ROOT / "data" / "trade_audit.db"
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"audit database not found: {path} (set {_DB_ENV} to an existing file)"
        )
    return path


def allowed_profiles() -> tuple[str, ...]:
    """Allow-listed profile names, read fresh on every request."""
    raw = os.environ.get(_PROFILES_ENV) or ""
    return tuple(name.strip() for name in raw.split(",") if name.strip())


def _require_profile(profile: str) -> str:
    """Fail closed unless *profile* is explicitly allow-listed."""
    allowed = allowed_profiles()
    if not allowed:
        raise ValueError(
            f"{_PROFILES_ENV} is not configured: no profile may be reported"
        )
    name = (profile or "").strip()
    if name not in allowed:
        raise ValueError(f"profile is not allow-listed: {profile!r}")
    return name


def _bounded_int(name: str, value: Any, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer between {low} and {high}") from None
    if number < low or number > high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return number


def _parse_utc(value) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _required_utc(name: str, value: str | None) -> datetime | None:
    if value in (None, ""):
        return None
    parsed = _parse_utc(value)
    if parsed is None:
        raise ValueError(f"{name} must be an ISO-8601 UTC timestamp")
    return parsed


def _validated_symbol(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    symbol = str(value).strip()
    if not _SYMBOL_RE.match(symbol):
        raise ValueError("symbol must be 1-32 characters of [A-Za-z0-9._#-]")
    return symbol.upper()


def _age_seconds(observed_at_utc) -> float | None:
    parsed = _parse_utc(observed_at_utc)
    if parsed is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())


def _meta(observed_at_utc) -> dict[str, Any]:
    """Uniform provenance + staleness labelling for every report."""
    return {
        "source": SOURCE,
        "observed_at_utc": observed_at_utc or None,
        "data_age_seconds": _age_seconds(observed_at_utc),
    }


# --------------------------------------------------------------------------- #
# Session helpers
# --------------------------------------------------------------------------- #
@contextmanager
def _session():
    """Open the query-only ledger for one request and close it deterministically."""
    store = ReadOnlyAuditStore(resolve_db_path())
    try:
        yield store, AccountQueries(store=store)
    finally:
        store.close()


def _account_row(store: ReadOnlyAuditStore, profile: str) -> dict | None:
    for account in store.list_accounts():
        if account.get("profile_name") == profile:
            return account
    return None


def _latest_sample_ts(store: ReadOnlyAuditStore, account_id) -> str | None:
    samples = store.list_equity_samples(account_id=account_id, limit=1)
    return samples[0].get("sampled_at_utc") if samples else None


def _unavailable(profile: str, **extra) -> dict[str, Any]:
    payload = {"profile": profile, "available": False, **_meta(None)}
    payload.update(extra)
    return payload


# --------------------------------------------------------------------------- #
# MCP server (report tools only)
# --------------------------------------------------------------------------- #
mcp = FastMCP(
    "oak-mt5-audit",
    instructions=(
        "Read-only reports over the local OAK trade-audit ledger. No live "
        "terminal connection, no trading and no control operations are "
        "available. Every result carries source='audit_ledger' plus its "
        "observation time so staleness stays visible."
    ),
)


@mcp.tool()
def list_accounts() -> dict[str, Any]:
    """List allow-listed audited accounts (safe metadata only).

    Returns ``configured=false`` with an empty list when no allow-list is set.
    Top-level freshness refers to the newest sample across the listed accounts.
    """
    allowed = allowed_profiles()
    if not allowed:
        return {"configured": False, "accounts": [], **_meta(None)}
    accounts = []
    with _session() as (store, _queries):
        for name in allowed:
            account = _account_row(store, name)
            if account is None:
                accounts.append({
                    "profile": name,
                    "broker": "",
                    "currency": "",
                    "account_type": "",
                    "available": False,
                    "latest_sampled_at_utc": None,
                })
                continue
            accounts.append({
                "profile": name,
                "broker": account.get("broker", ""),
                "currency": account.get("currency", ""),
                "account_type": account.get("account_type", ""),
                "available": True,
                "latest_sampled_at_utc": _latest_sample_ts(store, account.get("id")),
            })
    stamps = [item["latest_sampled_at_utc"] for item in accounts
              if item["latest_sampled_at_utc"]]
    newest = max(
        stamps,
        key=lambda ts: _parse_utc(ts) or datetime.min.replace(tzinfo=timezone.utc),
    ) if stamps else None
    return {"configured": True, "accounts": accounts, **_meta(newest)}


@mcp.tool()
def account_overview(profile: str) -> dict[str, Any]:
    """Latest balance/equity/margin snapshot for one allow-listed profile."""
    name = _require_profile(profile)
    with _session() as (_store, queries):
        result = dict(queries.account_get(name))
        result.update(_meta(result.get("sampled_at_utc")))
        return result


@mcp.tool()
def performance_summary(profile: str) -> dict[str, Any]:
    """Performance metrics (P/L, win rate, drawdown, fees) from the ledger.

    Metrics with no ledger evidence stay ``null``; nothing is estimated.
    """
    name = _require_profile(profile)
    with _session() as (store, queries):
        result = dict(queries.performance_summary(name))
        account = _account_row(store, name)
        observed = _latest_sample_ts(store, account.get("id")) if account else None
        result.update(_meta(observed))
        return result


@mcp.tool()
def trade_history(
    profile: str,
    limit: int = 100,
    from_utc: str | None = None,
    to_utc: str | None = None,
    symbol: str | None = None,
) -> dict[str, Any]:
    """Closed/open trading deals, newest first (1-200 rows, no ticket ids).

    ``from_utc`` / ``to_utc`` are inclusive ISO-8601 bounds on the deal time.
    """
    name = _require_profile(profile)
    count = _bounded_int("limit", limit, 1, 200)
    start = _required_utc("from_utc", from_utc)
    end = _required_utc("to_utc", to_utc)
    if start is not None and end is not None and start > end:
        raise ValueError("from_utc must not be later than to_utc")
    wanted_symbol = _validated_symbol(symbol)

    with _session() as (store, _queries):
        account = _account_row(store, name)
        if account is None:
            return _unavailable(name, count=0, deals=[])
        selected = []
        for deal in store.list_deals(account_id=account.get("id")):
            if deal.get("deal_type") not in _TRADING_DEAL_TYPES:
                continue
            if wanted_symbol and (deal.get("symbol") or "").upper() != wanted_symbol:
                continue
            deal_time = _parse_utc(deal.get("deal_time_utc"))
            if start is not None and (deal_time is None or deal_time < start):
                continue
            if end is not None and (deal_time is None or deal_time > end):
                continue
            selected.append((deal_time, deal))
        selected.sort(
            key=lambda item: item[0] or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        deals = [{
            "symbol": deal.get("symbol", ""),
            "deal_type": deal.get("deal_type", ""),
            "entry_type": deal.get("entry_type", ""),
            "reason_category": deal.get("reason_category", ""),
            "volume": deal.get("volume"),
            "price": deal.get("price"),
            "profit": deal.get("profit"),
            "commission": deal.get("commission"),
            "swap": deal.get("swap"),
            "fee": deal.get("fee"),
            "deal_time_utc": deal.get("deal_time_utc"),
        } for _ts, deal in selected[:count]]
        observed = deals[0]["deal_time_utc"] if deals else None
        return {
            "profile": name,
            "available": True,
            "count": len(deals),
            "deals": deals,
            **_meta(observed),
        }


@mcp.tool()
def equity_curve(profile: str, limit: int = 500) -> dict[str, Any]:
    """Chronological equity/balance samples for charting (1-1000 points)."""
    name = _require_profile(profile)
    count = _bounded_int("limit", limit, 1, 1000)
    with _session() as (store, queries):
        if _account_row(store, name) is None:
            return _unavailable(name, count=0, samples=[])
        samples = queries.equity_curve(name, limit=count)
        observed = samples[-1].get("t") if samples else None
        return {
            "profile": name,
            "available": True,
            "count": len(samples),
            "samples": samples,
            **_meta(observed),
        }


@mcp.tool()
def checkpoint_history(profile: str, limit: int = 30) -> dict[str, Any]:
    """Recent audit checkpoint runs, oldest first (1-100 rows)."""
    name = _require_profile(profile)
    count = _bounded_int("limit", limit, 1, 100)
    with _session() as (store, queries):
        if _account_row(store, name) is None:
            return _unavailable(name, count=0, checkpoints=[])
        checkpoints = queries.checkpoints_list(name, limit=count)
        observed = checkpoints[-1].get("captured_at_utc") if checkpoints else None
        return {
            "profile": name,
            "available": True,
            "count": len(checkpoints),
            "checkpoints": checkpoints,
            **_meta(observed),
        }


@mcp.tool()
def risk_summary(profile: str) -> dict[str, Any]:
    """Ledger-derived exposure, streaks and drawdown for one profile.

    Exposure reflects the last audited positions, not a live position feed.
    """
    name = _require_profile(profile)
    with _session() as (store, queries):
        result = dict(queries.risk_summary(name))
        account = _account_row(store, name)
        observed = _latest_sample_ts(store, account.get("id")) if account else None
        result.update(_meta(observed))
        result["basis"] = LEDGER_NOTE
        return result


@mcp.tool()
def audit_integrity(profile: str) -> dict[str, Any]:
    """Verify the append-only hash chain of the profile's audit events.

    ``ok`` is ``null`` when the profile has no account in the ledger.
    """
    name = _require_profile(profile)
    with _session() as (store, _queries):
        account = _account_row(store, name)
        if account is None:
            return {
                "profile": name,
                "source": SOURCE,
                "ok": None,
                "events": 0,
                "first_broken": None,
            }
        chain = store.verify_audit_chain(account.get("id"))
        return {
            "profile": name,
            "source": SOURCE,
            "ok": chain.get("ok"),
            "events": chain.get("events"),
            "first_broken": chain.get("first_broken"),
        }


def main() -> None:
    log.info("Starting read-only audit MCP server (stdio, no live broker access)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
