"""Database connection and schema management for SQLite market.db."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Generator


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS eod_prices (
    date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    reference_price REAL,
    ceiling_price REAL,
    floor_price REAL,
    volume REAL NOT NULL DEFAULT 0,
    value REAL NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'unknown',
    collected_at TEXT NOT NULL,
    foreign_buy_volume REAL,
    foreign_sell_volume REAL,
    foreign_buy_value REAL,
    foreign_sell_value REAL,
    adjusted_close REAL,
    PRIMARY KEY (date, symbol, exchange)
);

CREATE INDEX IF NOT EXISTS idx_eod_prices_symbol_date ON eod_prices(symbol, date, exchange);
CREATE INDEX IF NOT EXISTS idx_eod_prices_date ON eod_prices(date);
"""


class Database:
    """SQLite Database manager ensuring robust schema setup and connection safety."""

    def __init__(self, db_path: Path | str = Path("data/market.db")) -> None:
        self.db_path = Path(db_path)
        self._ensure_parent_directory()
        self.init_schema()

    def _ensure_parent_directory(self) -> None:
        if self.db_path.parent:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def init_schema(self) -> None:
        """Initialize SQLite schema if it does not exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager yielding a transactional SQLite connection with auto rollback on error."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
