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
        """)
        self._conn.commit()
        log.info("SQLite initialized: %s", self._db_path)

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

    # --- Settings ---
    def get_setting(self, key, default=None):
        """Get a setting value."""
        row = self._conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key, value):
        """Set a setting value."""
        self._conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?,?)", (key, str(value)))
        self._conn.commit()

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
