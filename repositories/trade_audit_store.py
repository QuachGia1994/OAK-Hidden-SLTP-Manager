# -*- coding: utf-8 -*-
"""Append-only MT5 trade audit ledger for OAK Trading system.

New database: data/trade_audit.db
- WAL mode, foreign_keys ON, busy_timeout.
- Numbered migrations via schema_version table.
- Ledger tables (positions, deals, account_snapshots, checkpoint_*, equity_samples,
  cash_flows, audit_events) are append-only: production mode forbids DELETE.
- audit_events keeps an append-only SHA-256 hash chain per account.
"""
import hashlib
import json
import os
import sqlite3

from oak_logger import setup_logger

log = setup_logger("trade_audit")

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "trade_audit.db"
)

# Optional env override for tests / portability.
_DB_PATH_OVERRIDE = os.environ.get("TRADE_AUDIT_DB_PATH")
if _DB_PATH_OVERRIDE:
    DB_PATH = _DB_PATH_OVERRIDE

# Tables created by the initial migration (version 1).
_INITIAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    account_uid   TEXT NOT NULL UNIQUE,
    profile_name  TEXT NOT NULL DEFAULT '',
    broker        TEXT NOT NULL DEFAULT '',
    server        TEXT NOT NULL DEFAULT '',
    currency      TEXT NOT NULL DEFAULT '',
    account_type  TEXT NOT NULL DEFAULT '',
    public_alias  TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS checkpoint_runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id       INTEGER NOT NULL REFERENCES accounts(id),
    broker_date      TEXT NOT NULL,
    checkpoint_hour  INTEGER NOT NULL,
    interval_start   TEXT,
    interval_end     TEXT,
    captured_at_utc  TEXT NOT NULL DEFAULT (datetime('now')),
    capture_mode     TEXT NOT NULL DEFAULT 'NORMAL',
    status           TEXT NOT NULL DEFAULT 'PENDING',
    error            TEXT,
    UNIQUE(account_id, broker_date, checkpoint_hour)
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    checkpoint_run_id INTEGER NOT NULL REFERENCES checkpoint_runs(id),
    balance           REAL,
    equity            REAL,
    margin            REAL,
    free_margin       REAL,
    margin_level      REAL,
    open_profit       REAL,
    credit            REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS positions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id       INTEGER NOT NULL REFERENCES accounts(id),
    position_id      TEXT NOT NULL,
    position_ticket  TEXT NOT NULL DEFAULT '',
    symbol           TEXT NOT NULL DEFAULT '',
    direction        TEXT NOT NULL DEFAULT '',
    magic            TEXT NOT NULL DEFAULT '',
    comment          TEXT NOT NULL DEFAULT '',
    open_time_utc    TEXT,
    open_time_broker TEXT,
    open_price       REAL,
    initial_volume   REAL,
    source_type      TEXT NOT NULL DEFAULT 'LIVE',
    public_trade_id  TEXT NOT NULL DEFAULT '',
    UNIQUE(account_id, position_id)
);

CREATE TABLE IF NOT EXISTS deals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id      INTEGER NOT NULL REFERENCES accounts(id),
    deal_ticket     TEXT NOT NULL,
    position_id     TEXT NOT NULL DEFAULT '',
    order_ticket    TEXT NOT NULL DEFAULT '',
    symbol          TEXT NOT NULL DEFAULT '',
    deal_type       TEXT NOT NULL DEFAULT '',
    entry_type      TEXT NOT NULL DEFAULT '',
    reason_raw      TEXT NOT NULL DEFAULT '',
    reason_category TEXT NOT NULL DEFAULT '',
    volume          REAL,
    price           REAL,
    profit          REAL,
    commission      REAL DEFAULT 0,
    swap            REAL DEFAULT 0,
    fee             REAL DEFAULT 0,
    deal_time_utc   TEXT,
    deal_time_broker TEXT,
    magic           TEXT NOT NULL DEFAULT '',
    comment         TEXT NOT NULL DEFAULT '',
    UNIQUE(account_id, deal_ticket)
);

CREATE TABLE IF NOT EXISTS checkpoint_position_states (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    checkpoint_run_id       INTEGER NOT NULL REFERENCES checkpoint_runs(id),
    position_id             TEXT NOT NULL,
    status_at_checkpoint    TEXT NOT NULL DEFAULT '',
    volume                  REAL,
    current_price           REAL,
    floating_profit         REAL,
    sl                      REAL,
    tp                      REAL,
    close_price             REAL,
    close_time_utc          TEXT,
    close_reason            TEXT,
    realized_profit_to_date REAL,
    capture_mode            TEXT NOT NULL DEFAULT 'NORMAL'
);

CREATE TABLE IF NOT EXISTS equity_samples (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id       INTEGER NOT NULL REFERENCES accounts(id),
    sampled_at_utc   TEXT NOT NULL,
    sampled_at_broker TEXT,
    balance          REAL,
    equity           REAL,
    margin           REAL,
    free_margin      REAL,
    margin_level     REAL,
    open_profit      REAL,
    UNIQUE(account_id, sampled_at_utc)
);

CREATE TABLE IF NOT EXISTS cash_flows (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id         INTEGER NOT NULL REFERENCES accounts(id),
    time_utc           TEXT NOT NULL,
    flow_type          TEXT NOT NULL,
    amount             REAL NOT NULL,
    comment            TEXT NOT NULL DEFAULT '',
    external_reference TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS audit_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id    INTEGER NOT NULL REFERENCES accounts(id),
    event_time_utc TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    entity_type   TEXT NOT NULL DEFAULT '',
    entity_id     TEXT NOT NULL DEFAULT '',
    payload_json  TEXT NOT NULL DEFAULT '{}',
    previous_hash TEXT NOT NULL DEFAULT '',
    record_hash   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

# Investor-prep tables (schema only, no feature code) — section 15.
_INVESTOR_SCHEMA = """
CREATE TABLE IF NOT EXISTS investors (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    investor_uid TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS investment_accounts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    investor_id  INTEGER NOT NULL REFERENCES investors(id),
    account_id   INTEGER NOT NULL REFERENCES accounts(id),
    UNIQUE(investor_id, account_id)
);

CREATE TABLE IF NOT EXISTS capital_contributions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    investment_account_id INTEGER NOT NULL REFERENCES investment_accounts(id),
    time_utc     TEXT NOT NULL,
    amount       REAL NOT NULL,
    comment      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS withdrawals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    investment_account_id INTEGER NOT NULL REFERENCES investment_accounts(id),
    time_utc     TEXT NOT NULL,
    amount       REAL NOT NULL,
    comment      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS unit_balances (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    investment_account_id INTEGER NOT NULL REFERENCES investment_accounts(id),
    time_utc     TEXT NOT NULL,
    units        REAL NOT NULL,
    nav          REAL
);

CREATE TABLE IF NOT EXISTS high_water_marks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    investment_account_id INTEGER NOT NULL REFERENCES investment_accounts(id),
    time_utc     TEXT NOT NULL,
    equity       REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS performance_fee_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    investment_account_id INTEGER NOT NULL REFERENCES investment_accounts(id),
    time_utc     TEXT NOT NULL,
    amount       REAL NOT NULL,
    comment      TEXT NOT NULL DEFAULT ''
);
"""

# Migration v3: unique constraint on checkpoint_position_states(run_id, position).
_CHECKPOINT_POSITION_UNIQUE_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_checkpoint_position_states_run_pos
  ON checkpoint_position_states(checkpoint_run_id, position_id);
"""

# Ordered migrations: list of (version, sql_script).
MIGRATIONS = [
    (1, _INITIAL_SCHEMA),
    (2, _INVESTOR_SCHEMA),
    (3, _CHECKPOINT_POSITION_UNIQUE_INDEX),
]

# Tables that are append-only in production mode.
_LEDGER_TABLES = {
    "checkpoint_runs",
    "account_snapshots",
    "positions",
    "deals",
    "checkpoint_position_states",
    "equity_samples",
    "cash_flows",
    "audit_events",
}


def position_identity(account_uid, position_id):
    """Canonical identity key for a position: account_uid + position_id."""
    return f"{account_uid}::{position_id}"


def is_same_position(a, b):
    """True only when two position descriptors share ticket-level identity.

    Never compares by symbol/direction/volume. Handles hedging, netting,
    partial close (same ticket), add volume, reverse, reopened and
    copy-trade positions: two same-symbol positions with different
    position_id tickets are always distinct.
    """
    if not a or not b:
        return False
    a_uid = a.get("account_uid") or a.get("account_id")
    b_uid = b.get("account_uid") or b.get("account_id")
    if a_uid is None or b_uid is None or str(a_uid) != str(b_uid):
        return False
    return str(a.get("position_id")) == str(b.get("position_id"))


class TradeAuditStore:
    """Append-only trade ledger on data/trade_audit.db."""

    def __init__(self, db_path=None, read_only=True):
        self._db_path = db_path or DB_PATH
        self._read_only = read_only
        # Ensure parent directory exists.
        parent = os.path.dirname(os.path.abspath(self._db_path))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._migrate()
        log.debug("TradeAuditStore initialized: %s (read_only=%s)", self._db_path, self._read_only)

    # ------------------------------------------------------------------ #
    # Migrations
    # ------------------------------------------------------------------ #
    def _migrate(self):
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        row = self._conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
        current = row["v"] or 0
        for version, script in sorted(MIGRATIONS, key=lambda item: item[0]):
            if version <= current:
                continue
            self._conn.executescript(script)
            self._conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
            self._conn.commit()
            log.info("Applied trade_audit migration v%d", version)

    @property
    def schema_version(self):
        row = self._conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
        return row["v"] or 0

    # ------------------------------------------------------------------ #
    # Append-only guard
    # ------------------------------------------------------------------ #
    def _guarded_execute(self, sql, params=()):
        """Raise if production mode attempts a DELETE on a ledger table."""
        stripped = sql.lstrip().upper()
        if self._read_only and stripped.startswith("DELETE"):
            for table in _LEDGER_TABLES:
                if table in sql.lower():
                    raise PermissionError(
                        f"trade_audit ledger is append-only: DELETE on {table} blocked"
                    )
        return self._conn.execute(sql, params)

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------ #
    # Accounts
    # ------------------------------------------------------------------ #
    def upsert_account(self, account_uid, profile_name="", broker="", server="",
                       currency="", account_type="", public_alias=""):
        """Upsert an account keyed by account_uid. Returns account row id."""
        self._conn.execute(
            """INSERT INTO accounts (account_uid, profile_name, broker, server, currency, account_type, public_alias)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(account_uid) DO UPDATE SET
                 profile_name=excluded.profile_name,
                 broker=excluded.broker,
                 server=excluded.server,
                 currency=excluded.currency,
                 account_type=excluded.account_type,
                 public_alias=CASE WHEN excluded.public_alias <> '' THEN excluded.public_alias ELSE accounts.public_alias END""",
            (account_uid, profile_name, broker, server, currency, account_type, public_alias),
        )
        self._conn.commit()
        row = self._conn.execute("SELECT id FROM accounts WHERE account_uid=?", (account_uid,)).fetchone()
        return row["id"]

    def get_account_by_uid(self, account_uid):
        row = self._conn.execute("SELECT * FROM accounts WHERE account_uid=?", (account_uid,)).fetchone()
        return dict(row) if row else None

    def list_accounts(self):
        rows = self._conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Positions (append-only, idempotent upsert)
    # ------------------------------------------------------------------ #
    def upsert_position(self, account_id, position):
        """Upsert one position by unique(account_id, position_id)."""
        fields = (
            "account_id", "position_id", "position_ticket", "symbol", "direction",
            "magic", "comment", "open_time_utc", "open_time_broker", "open_price",
            "initial_volume", "source_type", "public_trade_id",
        )
        values = (
            account_id,
            str(position.get("position_id") or position.get("position_ticket") or ""),
            str(position.get("position_ticket") or ""),
            position.get("symbol", ""),
            position.get("direction", ""),
            str(position.get("magic", "") or ""),
            position.get("comment", ""),
            position.get("open_time_utc"),
            position.get("open_time_broker"),
            position.get("open_price"),
            position.get("initial_volume"),
            position.get("source_type", "LIVE"),
            position.get("public_trade_id", ""),
        )
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        updates = ", ".join(f"{f}=excluded.{f}" for f in ("position_ticket", "symbol", "direction", "magic", "comment", "open_time_utc", "open_time_broker", "open_price", "initial_volume", "source_type", "public_trade_id"))
        self._conn.execute(
            f"INSERT INTO positions ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(account_id, position_id) DO UPDATE SET {updates}",
            values,
        )
        self._conn.commit()

    def get_position(self, account_id, position_id):
        row = self._conn.execute(
            "SELECT * FROM positions WHERE account_id=? AND position_id=?",
            (account_id, str(position_id)),
        ).fetchone()
        return dict(row) if row else None

    def list_positions(self, account_id=None):
        if account_id is None:
            rows = self._conn.execute("SELECT * FROM positions ORDER BY id").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM positions WHERE account_id=? ORDER BY id", (account_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Deals (append-only, idempotent upsert)
    # ------------------------------------------------------------------ #
    def upsert_deal(self, account_id, deal):
        """Upsert one deal by unique(account_id, deal_ticket). Idempotent."""
        fields = (
            "account_id", "deal_ticket", "position_id", "order_ticket", "symbol",
            "deal_type", "entry_type", "reason_raw", "reason_category", "volume",
            "price", "profit", "commission", "swap", "fee", "deal_time_utc",
            "deal_time_broker", "magic", "comment",
        )
        values = (
            account_id,
            str(deal.get("deal_ticket")),
            str(deal.get("position_id") or ""),
            str(deal.get("order_ticket") or ""),
            deal.get("symbol", ""),
            deal.get("deal_type", ""),
            deal.get("entry_type", ""),
            deal.get("reason_raw", ""),
            deal.get("reason_category", ""),
            deal.get("volume"),
            deal.get("price"),
            deal.get("profit"),
            deal.get("commission", 0),
            deal.get("swap", 0),
            deal.get("fee", 0),
            deal.get("deal_time_utc"),
            deal.get("deal_time_broker"),
            str(deal.get("magic", "") or ""),
            deal.get("comment", ""),
        )
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        updates = ", ".join(
            f"{f}=excluded.{f}"
            for f in ("position_id", "order_ticket", "symbol", "deal_type", "entry_type",
                      "reason_raw", "reason_category", "volume", "price", "profit",
                      "commission", "swap", "fee", "deal_time_utc", "deal_time_broker",
                      "magic", "comment")
        )
        self._conn.execute(
            f"INSERT INTO deals ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(account_id, deal_ticket) DO UPDATE SET {updates}",
            values,
        )
        self._conn.commit()

    def get_deal(self, account_id, deal_ticket):
        row = self._conn.execute(
            "SELECT * FROM deals WHERE account_id=? AND deal_ticket=?",
            (account_id, str(deal_ticket)),
        ).fetchone()
        return dict(row) if row else None

    def list_deals(self, account_id=None, position_id=None):
        sql = "SELECT * FROM deals"
        params = []
        conds = []
        if account_id is not None:
            conds.append("account_id=?")
            params.append(account_id)
        if position_id is not None:
            conds.append("position_id=?")
            params.append(str(position_id))
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY id"
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Account snapshots
    # ------------------------------------------------------------------ #
    def upsert_snapshot(self, checkpoint_run_id, snapshot):
        """Insert one account snapshot row."""
        fields = (
            "checkpoint_run_id", "balance", "equity", "margin", "free_margin",
            "margin_level", "open_profit", "credit",
        )
        values = (
            checkpoint_run_id,
            snapshot.get("balance"),
            snapshot.get("equity"),
            snapshot.get("margin"),
            snapshot.get("free_margin"),
            snapshot.get("margin_level"),
            snapshot.get("open_profit"),
            snapshot.get("credit", 0),
        )
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        self._conn.execute(
            f"INSERT INTO account_snapshots ({columns}) VALUES ({placeholders})", values
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT id FROM account_snapshots WHERE checkpoint_run_id=? ORDER BY id DESC LIMIT 1",
            (checkpoint_run_id,),
        ).fetchone()
        return row["id"] if row else None

    def list_snapshots(self, account_id=None):
        if account_id is None:
            rows = self._conn.execute("SELECT * FROM account_snapshots ORDER BY id").fetchall()
        else:
            rows = self._conn.execute(
                """SELECT s.* FROM account_snapshots s
                   JOIN checkpoint_runs c ON s.checkpoint_run_id = c.id
                   WHERE c.account_id=? ORDER BY s.id""",
                (account_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Checkpoint runs
    # ------------------------------------------------------------------ #
    def upsert_checkpoint_run(self, account_id, broker_date, checkpoint_hour,
                              interval_start=None, interval_end=None,
                              captured_at_utc=None, capture_mode="NORMAL",
                              status="PENDING", error=None):
        """Idempotent checkpoint run keyed by unique(account_id, broker_date, checkpoint_hour)."""
        if captured_at_utc is None:
            from datetime import datetime, timezone
            captured_at_utc = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT INTO checkpoint_runs
                 (account_id, broker_date, checkpoint_hour, interval_start, interval_end,
                  captured_at_utc, capture_mode, status, error)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(account_id, broker_date, checkpoint_hour) DO UPDATE SET
                 interval_start=COALESCE(excluded.interval_start, checkpoint_runs.interval_start),
                 interval_end=excluded.interval_end,
                 captured_at_utc=excluded.captured_at_utc,
                 capture_mode=excluded.capture_mode,
                 status=excluded.status,
                 error=excluded.error""",
            (account_id, broker_date, checkpoint_hour, interval_start, interval_end,
             captured_at_utc, capture_mode, status, error),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT id FROM checkpoint_runs WHERE account_id=? AND broker_date=? AND checkpoint_hour=?",
            (account_id, broker_date, checkpoint_hour),
        ).fetchone()
        return row["id"] if row else None

    def get_checkpoint_run(self, account_id, broker_date, checkpoint_hour):
        row = self._conn.execute(
            "SELECT * FROM checkpoint_runs WHERE account_id=? AND broker_date=? AND checkpoint_hour=?",
            (account_id, broker_date, checkpoint_hour),
        ).fetchone()
        return dict(row) if row else None

    def list_checkpoint_runs(self, account_id=None, limit=200):
        if account_id is None:
            rows = self._conn.execute(
                "SELECT * FROM checkpoint_runs ORDER BY broker_date DESC, checkpoint_hour DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM checkpoint_runs WHERE account_id=? ORDER BY broker_date DESC, checkpoint_hour DESC LIMIT ?",
                (account_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Checkpoint position states
    # ------------------------------------------------------------------ #
    def upsert_checkpoint_position_state(self, checkpoint_run_id, state):
        fields = (
            "checkpoint_run_id", "position_id", "status_at_checkpoint", "volume",
            "current_price", "floating_profit", "sl", "tp", "close_price",
            "close_time_utc", "close_reason", "realized_profit_to_date", "capture_mode",
        )
        values = (
            checkpoint_run_id,
            str(state.get("position_id") or ""),
            state.get("status_at_checkpoint", ""),
            state.get("volume"),
            state.get("current_price"),
            state.get("floating_profit"),
            state.get("sl"),
            state.get("tp"),
            state.get("close_price"),
            state.get("close_time_utc"),
            state.get("close_reason"),
            state.get("realized_profit_to_date"),
            state.get("capture_mode", "NORMAL"),
        )
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        updates = ", ".join(
            f"{f}=excluded.{f}"
            for f in ("status_at_checkpoint", "volume", "current_price", "floating_profit",
                       "sl", "tp", "close_price", "close_time_utc", "close_reason",
                       "realized_profit_to_date", "capture_mode")
        )
        self._conn.execute(
            f"INSERT INTO checkpoint_position_states ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(checkpoint_run_id, position_id) DO UPDATE SET {updates}",
            values,
        )
        self._conn.commit()

    def list_checkpoint_position_states(self, checkpoint_run_id):
        rows = self._conn.execute(
            "SELECT * FROM checkpoint_position_states WHERE checkpoint_run_id=? ORDER BY id",
            (checkpoint_run_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Equity samples
    # ------------------------------------------------------------------ #
    def upsert_equity_sample(self, account_id, sample):
        """Insert one 60-second equity sample; unique(account_id, sampled_at_utc)."""
        self._conn.execute(
            """INSERT INTO equity_samples
                 (account_id, sampled_at_utc, sampled_at_broker, balance, equity, margin,
                  free_margin, margin_level, open_profit)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(account_id, sampled_at_utc) DO NOTHING""",
            (
                account_id,
                sample.get("sampled_at_utc"),
                sample.get("sampled_at_broker"),
                sample.get("balance"),
                sample.get("equity"),
                sample.get("margin"),
                sample.get("free_margin"),
                sample.get("margin_level"),
                sample.get("open_profit"),
            ),
        )
        self._conn.commit()

    def list_equity_samples(self, account_id=None, limit=100000):
        if account_id is None:
            rows = self._conn.execute(
                "SELECT * FROM equity_samples ORDER BY sampled_at_utc DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM equity_samples WHERE account_id=? ORDER BY sampled_at_utc DESC LIMIT ?",
                (account_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Cash flows
    # ------------------------------------------------------------------ #
    def add_cash_flow(self, account_id, time_utc, flow_type, amount,
                      comment="", external_reference=""):
        self._conn.execute(
            "INSERT INTO cash_flows (account_id, time_utc, flow_type, amount, comment, external_reference) VALUES (?,?,?,?,?,?)",
            (account_id, time_utc, flow_type, amount, comment, external_reference),
        )
        self._conn.commit()

    def list_cash_flows(self, account_id=None):
        if account_id is None:
            rows = self._conn.execute("SELECT * FROM cash_flows ORDER BY time_utc").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM cash_flows WHERE account_id=? ORDER BY time_utc", (account_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Audit event hash chain
    # ------------------------------------------------------------------ #
    @staticmethod
    def _canonical_payload(payload):
        if isinstance(payload, str):
            payload = {"message": payload}
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def append_audit_event(self, account_id, event_type, entity_type="", entity_id="",
                           payload=None, event_time_utc=None):
        """Append an event to the per-account hash chain. Returns record hash."""
        if event_time_utc is None:
            from datetime import datetime, timezone
            event_time_utc = datetime.now(timezone.utc).isoformat()
        payload_json = self._canonical_payload(payload or {})
        previous = self._conn.execute(
            "SELECT record_hash FROM audit_events WHERE account_id=? ORDER BY id DESC LIMIT 1",
            (account_id,),
        ).fetchone()
        previous_hash = previous["record_hash"] if previous else ""
        chain_source = f"{previous_hash}|{event_time_utc}|{event_type}|{entity_type}|{entity_id}|{payload_json}"
        record_hash = hashlib.sha256(chain_source.encode("utf-8")).hexdigest()
        self._conn.execute(
            """INSERT INTO audit_events
                 (account_id, event_time_utc, event_type, entity_type, entity_id, payload_json, previous_hash, record_hash)
               VALUES (?,?,?,?,?,?,?,?)""",
            (account_id, event_time_utc, event_type, entity_type, entity_id,
             payload_json, previous_hash, record_hash),
        )
        self._conn.commit()
        return record_hash

    def verify_audit_chain(self, account_id):
        """Walk the per-account event chain and verify hash integrity.

        Returns {"ok": bool, "events": n, "first_broken": index or None, "details": str}.
        """
        rows = self._conn.execute(
            "SELECT * FROM audit_events WHERE account_id=? ORDER BY id", (account_id,)
        ).fetchall()
        previous_hash = ""
        for index, row in enumerate(rows):
            if row["previous_hash"] != previous_hash:
                return {
                    "ok": False,
                    "events": len(rows),
                    "first_broken": index,
                    "details": f"previous_hash mismatch at event {index} (id={row['id']})",
                }
            expected = self._canonical_payload(json.loads(row["payload_json"] or "{}"))
            chain_source = f"{row['previous_hash']}|{row['event_time_utc']}|{row['event_type']}|{row['entity_type']}|{row['entity_id']}|{expected}"
            expected_hash = hashlib.sha256(chain_source.encode("utf-8")).hexdigest()
            if row["record_hash"] != expected_hash:
                return {
                    "ok": False,
                    "events": len(rows),
                    "first_broken": index,
                    "details": f"record_hash mismatch at event {index} (id={row['id']})",
                }
            previous_hash = row["record_hash"]
        return {"ok": True, "events": len(rows), "first_broken": None, "details": "chain intact"}

    # ------------------------------------------------------------------ #
    # Key-value settings (reconciler cursor etc.)
    # ------------------------------------------------------------------ #
    def get_setting(self, key, default=None):
        row = self._conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key, value):
        self._conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?,?)", (key, str(value))
        )
        self._conn.commit()
