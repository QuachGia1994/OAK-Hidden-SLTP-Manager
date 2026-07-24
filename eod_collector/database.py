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
    PRIMARY KEY (date, symbol)
);

CREATE INDEX IF NOT EXISTS idx_eod_prices_symbol_date ON eod_prices(symbol, date);
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
        """Initialize SQLite schema and migrate/deduplicate records."""
        with sqlite3.connect(self.db_path) as conn:
            # Check existing table schema
            table_info = conn.execute("PRAGMA table_info(eod_prices)").fetchall()
            pk_cols = [col[1] for col in table_info if col[5] > 0]
            if "exchange" in pk_cols:
                # Migrate schema: recreate table with PRIMARY KEY (date, symbol)
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS eod_prices_new (
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
                        PRIMARY KEY (date, symbol)
                    );
                    INSERT OR REPLACE INTO eod_prices_new
                    SELECT * FROM eod_prices
                    ORDER BY date ASC, symbol ASC, CASE WHEN source = 'VPS_PUBLIC' THEN 2 ELSE 1 END ASC;
                    DROP TABLE eod_prices;
                    ALTER TABLE eod_prices_new RENAME TO eod_prices;
                    CREATE INDEX IF NOT EXISTS idx_eod_prices_symbol_date ON eod_prices(symbol, date);
                    CREATE INDEX IF NOT EXISTS idx_eod_prices_date ON eod_prices(date);
                """)
            else:
                conn.executescript(SCHEMA_SQL)

            # Cleanup any remaining duplicates prioritizing VPS_PUBLIC source
            conn.execute("""
                DELETE FROM eod_prices
                WHERE rowid NOT IN (
                    SELECT rowid FROM (
                        SELECT rowid, ROW_NUMBER() OVER (
                            PARTITION BY date, symbol
                            ORDER BY CASE WHEN source = 'VPS_PUBLIC' THEN 2 ELSE 1 END DESC, rowid DESC
                        ) as rn
                        FROM eod_prices
                    ) WHERE rn = 1
                );
            """)
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
