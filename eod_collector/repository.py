"""Repository pattern for SQLite eod_prices persistence with UPSERT."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import sqlite3
from typing import Sequence

from eod_collector.database import Database
from eod_collector.models import EODRecord


UPSERT_SQL = """
INSERT INTO eod_prices (
    date, symbol, exchange, open, high, low, close,
    reference_price, ceiling_price, floor_price, volume, value,
    source, collected_at, foreign_buy_volume, foreign_sell_volume,
    foreign_buy_value, foreign_sell_value, adjusted_close
) VALUES (
    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
) ON CONFLICT(date, symbol, exchange) DO UPDATE SET
    open = excluded.open,
    high = excluded.high,
    low = excluded.low,
    close = excluded.close,
    reference_price = excluded.reference_price,
    ceiling_price = excluded.ceiling_price,
    floor_price = excluded.floor_price,
    volume = excluded.volume,
    value = excluded.value,
    source = excluded.source,
    collected_at = excluded.collected_at,
    foreign_buy_volume = excluded.foreign_buy_volume,
    foreign_sell_volume = excluded.foreign_sell_volume,
    foreign_buy_value = excluded.foreign_buy_value,
    foreign_sell_value = excluded.foreign_sell_value,
    adjusted_close = excluded.adjusted_close;
"""


class EODRepository:
    """Repository handling atomic UPSERT and queries for EOD records."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert_records(self, records: Sequence[EODRecord]) -> int:
        """Atomically insert or update EOD records. Rollback completely on error."""
        if not records:
            return 0

        rows = [
            (
                r.date, r.symbol, r.exchange, r.open, r.high, r.low, r.close,
                r.reference_price, r.ceiling_price, r.floor_price, r.volume, r.value,
                r.source, r.collected_at, r.foreign_buy_volume, r.foreign_sell_volume,
                r.foreign_buy_value, r.foreign_sell_value, r.adjusted_close
            )
            for r in records
        ]

        with self.database.connection() as conn:
            cursor = conn.executemany(UPSERT_SQL, rows)
            return cursor.rowcount if cursor.rowcount > 0 else len(records)

    def get_records(
        self,
        symbol: str | None = None,
        exchange: str | None = None,
        trading_date: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[EODRecord]:
        """Query EOD records with optional filters."""
        query = "SELECT * FROM eod_prices WHERE 1=1"
        params: list[object] = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.strip().upper())
        if exchange:
            query += " AND exchange = ?"
            params.append(exchange.strip().upper())
        if trading_date:
            query += " AND date = ?"
            params.append(trading_date)
        if from_date:
            query += " AND date >= ?"
            params.append(from_date)
        if to_date:
            query += " AND date <= ?"
            params.append(to_date)

        query += " ORDER BY date ASC, symbol ASC"

        with self.database.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_record(row) for row in rows]

    def get_latest_date(self) -> str | None:
        """Return latest date present in DB."""
        with self.database.connection() as conn:
            row = conn.execute("SELECT MAX(date) as max_date FROM eod_prices").fetchone()
            return row["max_date"] if row and row["max_date"] else None

    def get_symbol_count_by_exchange(self) -> dict[str, int]:
        """Return dict of distinct symbol count per exchange for latest trading date."""
        latest = self.get_latest_date()
        if not latest:
            return {}
        with self.database.connection() as conn:
            rows = conn.execute(
                "SELECT exchange, COUNT(DISTINCT symbol) as count FROM eod_prices WHERE date = ? GROUP BY exchange",
                (latest,)
            ).fetchall()
            return {r["exchange"]: r["count"] for r in rows}

    def get_total_sessions_count(self) -> int:
        """Return total unique dates saved."""
        with self.database.connection() as conn:
            row = conn.execute("SELECT COUNT(DISTINCT date) as cnt FROM eod_prices").fetchone()
            return row["cnt"] if row else 0

    def get_count_for_exchange_date(self, exchange: str, trading_date: str) -> int:

        """Return count of records for an exchange on a given date."""
        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM eod_prices WHERE exchange = ? AND date = ?",
                (exchange.upper(), trading_date)
            ).fetchone()
            return row["cnt"] if row else 0

    def get_missing_dates(self, from_date: str, to_date: str, holidays: list[str] | None = None) -> list[str]:
        """Return weekday dates missing between from_date and to_date."""
        start = datetime.strptime(from_date, "%Y-%m-%d").date()
        end = datetime.strptime(to_date, "%Y-%m-%d").date()
        holiday_set = set(holidays or [])

        with self.database.connection() as conn:
            existing_rows = conn.execute(
                "SELECT DISTINCT date FROM eod_prices WHERE date >= ? AND date <= ?",
                (from_date, to_date)
            ).fetchall()
            existing_dates = {r["date"] for r in existing_rows}

        missing = []
        curr = start
        while curr <= end:
            if curr.weekday() not in (5, 6):
                d_str = curr.strftime("%Y-%m-%d")
                if d_str not in existing_dates and d_str not in holiday_set:
                    missing.append(d_str)
            curr += timedelta(days=1)
        return missing

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> EODRecord:
        return EODRecord(
            date=row["date"],
            symbol=row["symbol"],
            exchange=row["exchange"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            reference_price=float(row["reference_price"]) if row["reference_price"] is not None else None,
            ceiling_price=float(row["ceiling_price"]) if row["ceiling_price"] is not None else None,
            floor_price=float(row["floor_price"]) if row["floor_price"] is not None else None,
            volume=float(row["volume"]),
            value=float(row["value"]),
            source=str(row["source"]),
            collected_at=str(row["collected_at"]),
            foreign_buy_volume=float(row["foreign_buy_volume"]) if row["foreign_buy_volume"] is not None else None,
            foreign_sell_volume=float(row["foreign_sell_volume"]) if row["foreign_sell_volume"] is not None else None,
            foreign_buy_value=float(row["foreign_buy_value"]) if row["foreign_buy_value"] is not None else None,
            foreign_sell_value=float(row["foreign_sell_value"]) if row["foreign_sell_value"] is not None else None,
            adjusted_close=float(row["adjusted_close"]) if row["adjusted_close"] is not None else None,
        )
