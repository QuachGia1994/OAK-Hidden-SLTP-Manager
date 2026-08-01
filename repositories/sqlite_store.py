# -*- coding: utf-8 -*-
"""SQLite state store for OAK Trading system."""
import sqlite3
import json
import os
from oak_logger import setup_logger

log = setup_logger("sqlite")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "oak_state.db")


class SQLiteStore:
    """Persistent state storage using SQLite."""

    def __init__(self, db_path=None):
        self._db_path = db_path or DB_PATH
        self._conn = None
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS scheduled_trades (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                type INTEGER NOT NULL,
                lot TEXT NOT NULL,
                sl TEXT DEFAULT '0',
                tp TEXT DEFAULT '0',
                time TEXT NOT NULL,
                date TEXT NOT NULL,
                status TEXT DEFAULT 'waiting'
            );
            CREATE TABLE IF NOT EXISTS scheduled_close (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                date TEXT NOT NULL,
                filter TEXT DEFAULT 'all',
                sym TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS pending_partials (
                ticket INTEGER PRIMARY KEY,
                symbol TEXT,
                type TEXT,
                target_profit REAL DEFAULT 0,
                close_volume REAL DEFAULT 0,
                profile TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS signal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                hour INTEGER NOT NULL,
                signal TEXT,
                pair_dirs_json TEXT,
                entry_prices_json TEXT,
                current_prices_json TEXT,
                hour_note TEXT,
                missed INTEGER DEFAULT 0,
                d_direction TEXT,
                ts REAL
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS worker_heartbeat (
                profile TEXT PRIMARY KEY,
                state TEXT NOT NULL DEFAULT 'starting',
                last_seen TEXT NOT NULL,
                server TEXT DEFAULT '',
                login INTEGER DEFAULT 0,
                balance REAL DEFAULT 0,
                equity REAL DEFAULT 0,
                last_error TEXT DEFAULT '',
                telegram_configured INTEGER DEFAULT 0,
                telegram_api_ok INTEGER DEFAULT 0,
                telegram_last_check TEXT DEFAULT '',
                telegram_bot_name TEXT DEFAULT '',
                broker_time TEXT DEFAULT '',
                broker_utc_offset INTEGER,
                broker_observed_at_utc TEXT DEFAULT '',
                data_provider TEXT DEFAULT 'MT4',
                data_state TEXT DEFAULT 'disconnected',
                data_observed_at_utc TEXT DEFAULT '',
                execution_provider TEXT DEFAULT 'MT5',
                execution_state TEXT DEFAULT 'disconnected'
            );
            CREATE TABLE IF NOT EXISTS signal_execution_intents (
                idempotency_key TEXT PRIMARY KEY,
                logic_version INTEGER NOT NULL,
                broker_date TEXT NOT NULL,
                slot_hour INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                common_entry_time TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_at_utc TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at_utc TEXT NOT NULL,
                order_ticket INTEGER,
                last_error TEXT DEFAULT '',
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );
        """)
        heartbeat_columns = {
            row[1] for row in self._conn.execute("PRAGMA table_info(worker_heartbeat)").fetchall()
        }
        for column, definition in (
            ("broker_time", "TEXT DEFAULT ''"),
            ("broker_utc_offset", "INTEGER"),
            ("broker_observed_at_utc", "TEXT DEFAULT ''"),
            ("data_provider", "TEXT DEFAULT 'MT4'"),
            ("data_state", "TEXT DEFAULT 'disconnected'"),
            ("data_observed_at_utc", "TEXT DEFAULT ''"),
            ("execution_provider", "TEXT DEFAULT 'MT5'"),
            ("execution_state", "TEXT DEFAULT 'disconnected'"),
        ):
            if column not in heartbeat_columns:
                self._conn.execute(f"ALTER TABLE worker_heartbeat ADD COLUMN {column} {definition}")
        self._conn.commit()
        log.debug("SQLite initialized: %s", self._db_path)

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # --- Scheduled Trades ---
    def get_scheduled_trades(self, status=None):
        """Get scheduled trades, optionally filtered by status."""
        if status:
            rows = self._conn.execute("SELECT * FROM scheduled_trades WHERE status=? ORDER BY time", (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM scheduled_trades ORDER BY time").fetchall()
        return [dict(r) for r in rows]

    def add_scheduled_trade(self, trade):
        """Add a scheduled trade."""
        self._conn.execute(
            "INSERT INTO scheduled_trades (id, symbol, type, lot, sl, tp, time, date, status) VALUES (?,?,?,?,?,?,?,?,?)",
            (trade["id"], trade["symbol"], trade["type"], trade["lot"],
             trade.get("sl", "0"), trade.get("tp", "0"), trade["time"], trade["date"], trade.get("status", "waiting"))
        )
        self._conn.commit()

    def update_trade_status(self, trade_id, status):
        """Update trade status."""
        self._conn.execute("UPDATE scheduled_trades SET status=? WHERE id=?", (status, trade_id))
        self._conn.commit()

    def delete_trade(self, trade_id):
        """Delete a trade by ID."""
        self._conn.execute("DELETE FROM scheduled_trades WHERE id=?", (trade_id,))
        self._conn.commit()

    def delete_all_trades(self):
        """Delete all trades."""
        self._conn.execute("DELETE FROM scheduled_trades")
        self._conn.commit()

    # --- Scheduled Close ---
    def get_scheduled_closes(self):
        """Get all scheduled close tasks."""
        rows = self._conn.execute("SELECT * FROM scheduled_close").fetchall()
        return [dict(r) for r in rows]

    def add_scheduled_close(self, close_info):
        """Add a scheduled close task."""
        self._conn.execute(
            "INSERT INTO scheduled_close (time, date, filter, sym) VALUES (?,?,?,?)",
            (close_info["time"], close_info["date"], close_info.get("filter", "all"), close_info.get("sym", ""))
        )
        self._conn.commit()

    def delete_scheduled_close(self, rowid):
        """Delete a scheduled close by rowid."""
        self._conn.execute("DELETE FROM scheduled_close WHERE id=?", (rowid,))
        self._conn.commit()

    def clear_scheduled_closes(self):
        """Delete all scheduled closes."""
        self._conn.execute("DELETE FROM scheduled_close")
        self._conn.commit()

    # --- Pending Partials ---
    def get_pending_partials(self):
        """Get all pending partial close tasks."""
        rows = self._conn.execute("SELECT * FROM pending_partials").fetchall()
        return {str(r["ticket"]): dict(r) for r in rows}

    def set_pending_partial(self, ticket, data):
        """Set/update a pending partial close task."""
        self._conn.execute(
            "INSERT OR REPLACE INTO pending_partials (ticket, symbol, type, target_profit, close_volume, profile) VALUES (?,?,?,?,?,?)",
            (ticket, data.get("symbol"), data.get("type"), data.get("target_profit", 0),
             data.get("close_volume", 0), data.get("profile", ""))
        )
        self._conn.commit()

    def delete_pending_partial(self, ticket):
        """Delete a pending partial close task."""
        self._conn.execute("DELETE FROM pending_partials WHERE ticket=?", (ticket,))
        self._conn.commit()

    # --- Signal History ---
    def add_signal(self, signal_data):
        """Add a signal record."""
        self._conn.execute(
            "INSERT INTO signal_history (date, hour, signal, pair_dirs_json, entry_prices_json, current_prices_json, hour_note, missed, d_direction, ts) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (signal_data.get("date"), signal_data.get("hour"), signal_data.get("signal"),
             json.dumps(signal_data.get("pair_dirs", {})), json.dumps(signal_data.get("entry_prices", {})),
             json.dumps(signal_data.get("current_prices", {})), signal_data.get("hour_note"),
             1 if signal_data.get("missed") else 0, signal_data.get("d_direction"), signal_data.get("ts"))
        )
        self._conn.commit()

    def get_signals(self, date=None, limit=100):
        """Get signal history, optionally filtered by date."""
        if date:
            rows = self._conn.execute("SELECT * FROM signal_history WHERE date=? ORDER BY hour", (date,)).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM signal_history ORDER BY date DESC, hour DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # --- Signal execution intents ---
    def upsert_signal_execution_intent(self, intent):
        """Insert one v87 intent once; duplicate idempotency keys are ignored."""
        fields = (
            "idempotency_key", "logic_version", "broker_date", "slot_hour",
            "symbol", "common_entry_time", "direction", "entry_at_utc",
            "status", "attempts", "next_attempt_at_utc", "order_ticket",
            "last_error", "created_at_utc", "updated_at_utc",
        )
        values = tuple(intent.get(field) for field in fields)
        self._conn.execute(
            f"INSERT OR IGNORE INTO signal_execution_intents ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
            values,
        )
        self._conn.commit()

    def get_due_signal_execution_intents(self, now_utc, limit=50):
        """Return pending intents whose UTC entry and retry windows are due."""
        rows = self._conn.execute(
            "SELECT * FROM signal_execution_intents WHERE status='PENDING' AND entry_at_utc<=? AND next_attempt_at_utc<=? ORDER BY entry_at_utc LIMIT ?",
            (now_utc, now_utc, int(limit)),
        ).fetchall()
        return [dict(row) for row in rows]

    def update_signal_execution_intent(self, key, **changes):
        """Update a whitelisted execution-intent state atomically."""
        allowed = {"status", "attempts", "next_attempt_at_utc", "order_ticket", "last_error", "updated_at_utc"}
        payload = {name: value for name, value in changes.items() if name in allowed}
        if not payload:
            return
        assignments = ", ".join(f"{name}=?" for name in payload)
        self._conn.execute(
            f"UPDATE signal_execution_intents SET {assignments} WHERE idempotency_key=?",
            (*payload.values(), key),
        )
        self._conn.commit()

    # --- Settings ---
    def get_setting(self, key, default=None):
        """Get a setting value."""
        row = self._conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key, value):
        """Set a setting value."""
        self._conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?,?)", (key, str(value)))
        self._conn.commit()

    # --- Worker Heartbeat ---
    def publish_heartbeat(self, profile, state, server="", login=0, balance=0, equity=0,
                          last_error="", telegram_configured=False, telegram_api_ok=False,
                          telegram_last_check="", telegram_bot_name="",
                          preserve_telegram=False, broker_time=None,
                          broker_utc_offset=None, broker_observed_at_utc=None,
                          preserve_broker_clock=True, data_provider="MT4",
                          data_state="disconnected", data_observed_at_utc="",
                          execution_provider="MT5", execution_state="disconnected"):
        """Publish worker heartbeat. Called by worker every ~2s.

        preserve_telegram=True keeps prior telegram_* fields (MT5-only refresh).
        Use this when the publisher does not re-check Telegram getMe.
        """
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        if preserve_telegram:
            prev = self.get_heartbeat(profile) or {}
            telegram_configured = bool(prev.get("telegram_configured", telegram_configured))
            telegram_api_ok = bool(prev.get("telegram_api_ok", telegram_api_ok))
            telegram_last_check = prev.get("telegram_last_check", telegram_last_check) or ""
            telegram_bot_name = prev.get("telegram_bot_name", telegram_bot_name) or ""
        if preserve_broker_clock:
            prev = self.get_heartbeat(profile) or {}
            broker_time = prev.get("broker_time", "") if broker_time is None else broker_time
            broker_utc_offset = prev.get("broker_utc_offset") if broker_utc_offset is None else broker_utc_offset
            broker_observed_at_utc = (
                prev.get("broker_observed_at_utc", "")
                if broker_observed_at_utc is None
                else broker_observed_at_utc
            )
        self._conn.execute(
            """INSERT OR REPLACE INTO worker_heartbeat
               (profile, state, last_seen, server, login, balance, equity, last_error,
                 telegram_configured, telegram_api_ok, telegram_last_check, telegram_bot_name,
                 broker_time, broker_utc_offset, broker_observed_at_utc,
                 data_provider, data_state, data_observed_at_utc, execution_provider, execution_state)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (profile, state, now, server, login, balance, equity, last_error,
             1 if telegram_configured else 0, 1 if telegram_api_ok else 0,
             telegram_last_check, telegram_bot_name, broker_time or "",
             broker_utc_offset, broker_observed_at_utc or "", data_provider, data_state,
             data_observed_at_utc or "", execution_provider, execution_state)
        )
        self._conn.commit()

    def get_heartbeat(self, profile):
        """Get worker heartbeat for a specific profile. Returns dict or None."""
        if not profile:
            return None
        row = self._conn.execute("SELECT * FROM worker_heartbeat WHERE profile=?", (profile,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["telegram_configured"] = bool(d.get("telegram_configured"))
        d["telegram_api_ok"] = bool(d.get("telegram_api_ok"))
        return d

    def compute_mt5_state(self, profile):
        """Compute MT5 state from heartbeat: Connected/Degraded/Disconnected/Starting."""
        from datetime import datetime, timezone, timedelta
        hb = self.get_heartbeat(profile)
        if hb is None:
            return {"state": "Disconnected", "last_seen": None, "last_error": "No heartbeat yet", "age": None}
        last_seen = datetime.fromisoformat(hb["last_seen"])
        age = (datetime.now(timezone.utc) - last_seen).total_seconds()
        if hb["state"] == "starting" or age > 90:
            return {"state": "Disconnected", "last_seen": hb["last_seen"], "last_error": hb.get("last_error", "Heartbeat stale"), "age": age}
        if age > 15:
            return {"state": "Degraded", "last_seen": hb["last_seen"], "last_error": hb.get("last_error", ""), "age": age}
        return {"state": "Connected", "last_seen": hb["last_seen"], "last_error": "", "age": age}

    def compute_telegram_state(self, profile):
        """Compute Telegram state from heartbeat."""
        hb = self.get_heartbeat(profile)
        if hb is None:
            return {"configured": False, "api_ok": False, "bot_name": "", "last_check": ""}
        return {
            "configured": hb.get("telegram_configured", False),
            "api_ok": hb.get("telegram_api_ok", False),
            "bot_name": hb.get("telegram_bot_name", ""),
            "last_check": hb.get("telegram_last_check", ""),
        }

    # --- Migration from JSON ---
    def migrate_from_json(self, json_dir):
        """Migrate state from JSON files to SQLite."""
        migrated = 0

        # Migrate scheduled_trades.json
        trades_file = os.path.join(json_dir, "scheduled_trades.json")
        if os.path.exists(trades_file):
            try:
                with open(trades_file, "r", encoding="utf-8") as f:
                    trades = json.load(f)
                for t in trades:
                    self.add_scheduled_trade(t)
                migrated += len(trades)
                log.info("Migrated %d scheduled trades from JSON", len(trades))
            except Exception as e:
                log.warning("Failed to migrate scheduled_trades: %s", e)

        # Migrate scheduled_close.json
        close_file = os.path.join(json_dir, "scheduled_close.json")
        if os.path.exists(close_file):
            try:
                with open(close_file, "r", encoding="utf-8") as f:
                    closes = json.load(f)
                for c in closes:
                    self.add_scheduled_close(c)
                migrated += len(closes)
                log.info("Migrated %d scheduled closes from JSON", len(closes))
            except Exception as e:
                log.warning("Failed to migrate scheduled_close: %s", e)

        return migrated
