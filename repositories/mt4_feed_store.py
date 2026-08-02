# -*- coding: utf-8 -*-
"""
MT4 Feed Persistent SQLite Store (v87)
=======================================
Provides persistent storage for raw MT4 Feed heartbeats and candle bars.
"""
import sqlite3
import os
import tempfile
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Dict, Any
from oak_logger import setup_logger

log = setup_logger("mt4_feed_store")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mt4_feed.db")


class AmbiguousMT4FeedSourceError(Exception):
    """Raised when an exact bar is published by multiple sources with conflicting OHLC."""
    pass


class MT4FeedStore:
    """SQLite state store for MT4 raw market data & clock heartbeat."""

    def __init__(self, db_path=None):
        self._db_path = db_path or DB_PATH
        self._conn = None
        self._close_after_operation = bool(db_path and os.path.abspath(str(db_path)).startswith(os.path.abspath(tempfile.gettempdir())))
        self._init_db()

    def _ensure_open(self):
        if self._conn is None:
            self._init_db()

    def _finish_ephemeral(self):
        if self._close_after_operation:
            self.close()

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _init_db(self):
        """Create tables and unique indexes if they don't exist."""
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS mt4_feed_heartbeat (
                source_id TEXT PRIMARY KEY,
                account TEXT DEFAULT '',
                server TEXT DEFAULT '',
                broker_time TEXT NOT NULL,
                broker_time_utc TEXT DEFAULT '',
                broker_utc_offset INTEGER,
                observed_at_utc TEXT NOT NULL,
                last_sequence INTEGER DEFAULT 0,
                schema_version INTEGER DEFAULT 2
            );
            CREATE TABLE IF NOT EXISTS mt4_feed_clock_offsets (
                source_id TEXT NOT NULL,
                broker_date TEXT NOT NULL,
                broker_utc_offset INTEGER NOT NULL,
                observed_at_utc TEXT NOT NULL,
                PRIMARY KEY (source_id, broker_date)
            );
            CREATE TABLE IF NOT EXISTS mt4_feed_bars (
                canonical_symbol TEXT NOT NULL,
                resolved_mt4_symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                broker_open_at TEXT NOT NULL,
                broker_close_at TEXT DEFAULT '',
                utc_open_at TEXT DEFAULT '',
                open_exact TEXT NOT NULL,
                high_exact TEXT NOT NULL,
                low_exact TEXT NOT NULL,
                close_exact TEXT NOT NULL,
                tick_volume INTEGER DEFAULT 0,
                is_complete INTEGER DEFAULT 1,
                received_at_utc TEXT NOT NULL,
                source_id TEXT DEFAULT 'mt4_ea',
                schema_version INTEGER DEFAULT 2,
                PRIMARY KEY (source_id, canonical_symbol, timeframe, broker_open_at)
            );
            CREATE INDEX IF NOT EXISTS idx_mt4_feed_bars_lookup
            ON mt4_feed_bars (canonical_symbol, timeframe, broker_open_at);
        """)
        self._migrate_legacy_bar_columns()
        self._migrate_clock_offsets()
        self._conn.commit()

    def _migrate_clock_offsets(self):
        """Backfill the per-date offset cache from existing v2 heartbeats."""
        self._conn.execute("""
            INSERT OR IGNORE INTO mt4_feed_clock_offsets
                (source_id, broker_date, broker_utc_offset, observed_at_utc)
            SELECT source_id, substr(broker_time, 1, 10), broker_utc_offset, observed_at_utc
            FROM mt4_feed_heartbeat
            WHERE schema_version = 2 AND broker_utc_offset IS NOT NULL
        """)

    def _migrate_legacy_bar_columns(self):
        """Migrate the short-lived v87 REAL columns without losing feed data."""
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(mt4_feed_bars)").fetchall()}
        if "open" in columns:
            self._conn.execute("ALTER TABLE mt4_feed_bars RENAME TO mt4_feed_bars_legacy")
            self._conn.executescript("""
                CREATE TABLE mt4_feed_bars (
                    canonical_symbol TEXT NOT NULL,
                    resolved_mt4_symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    broker_open_at TEXT NOT NULL,
                    broker_close_at TEXT DEFAULT '',
                    utc_open_at TEXT DEFAULT '',
                    open_exact TEXT NOT NULL,
                    high_exact TEXT NOT NULL,
                    low_exact TEXT NOT NULL,
                    close_exact TEXT NOT NULL,
                    tick_volume INTEGER DEFAULT 0,
                    is_complete INTEGER DEFAULT 1,
                    received_at_utc TEXT NOT NULL,
                    source_id TEXT DEFAULT 'mt4_ea',
                    schema_version INTEGER DEFAULT 2,
                    PRIMARY KEY (source_id, canonical_symbol, timeframe, broker_open_at)
                );
            """)
            self._conn.execute("""
                INSERT INTO mt4_feed_bars
                (canonical_symbol,resolved_mt4_symbol,timeframe,broker_open_at,broker_close_at,utc_open_at,
                 open_exact,high_exact,low_exact,close_exact,tick_volume,is_complete,
                 received_at_utc,source_id,schema_version)
                SELECT canonical_symbol,resolved_mt4_symbol,timeframe,broker_open_at,'',utc_open_at,
                       CAST(open AS TEXT),CAST(high AS TEXT),CAST(low AS TEXT),CAST(close AS TEXT),
                       tick_volume,is_complete,received_at_utc,source_id,2
                FROM mt4_feed_bars_legacy
            """)
            self._conn.execute("DROP TABLE mt4_feed_bars_legacy")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_mt4_feed_bars_lookup ON mt4_feed_bars (canonical_symbol,timeframe,broker_open_at)")
            return
        if "broker_close_at" not in columns:
            self._conn.execute("ALTER TABLE mt4_feed_bars ADD COLUMN broker_close_at TEXT DEFAULT ''")
        for name in ("open_exact", "high_exact", "low_exact", "close_exact"):
            if name not in columns:
                self._conn.execute(f"ALTER TABLE mt4_feed_bars ADD COLUMN {name} TEXT")
        if "open" in columns:
            self._conn.execute("UPDATE mt4_feed_bars SET open_exact=COALESCE(open_exact, CAST(open AS TEXT))")
            self._conn.execute("UPDATE mt4_feed_bars SET high_exact=COALESCE(high_exact, CAST(high AS TEXT))")
            self._conn.execute("UPDATE mt4_feed_bars SET low_exact=COALESCE(low_exact, CAST(low AS TEXT))")
            self._conn.execute("UPDATE mt4_feed_bars SET close_exact=COALESCE(close_exact, CAST(close AS TEXT))")

    def save_heartbeat(self, data: Dict[str, Any]):
        """Persist or update an MT4 feed publisher heartbeat."""
        self._ensure_open()
        source_id = str(data.get("source_id", "mt4_ea"))
        account = str(data.get("account", ""))
        server = str(data.get("server", ""))
        broker_time = str(data.get("broker_time", ""))
        broker_time_utc = str(data.get("broker_time_utc", ""))
        if "broker_utc_offset" not in data:
            raise ValueError("broker_utc_offset is required")
        broker_utc_offset = self._validate_offset(data.get("broker_utc_offset"))
        observed_at_utc = str(data.get("observed_at_utc", datetime.now(timezone.utc).isoformat()))
        last_sequence = int(data.get("last_sequence", 0))
        schema_version = int(data.get("schema_version", 0))

        if not broker_time or not observed_at_utc:
            raise ValueError("broker_time and observed_at_utc are required")
        if schema_version != 2:
            raise ValueError("unsupported MT4 heartbeat schema")
        broker_dt = self._parse_datetime(broker_time, assume_utc=False)
        observed_dt = self._parse_datetime(observed_at_utc, assume_utc=True)
        broker_time = broker_dt.strftime("%Y-%m-%dT%H:%M:%S")
        observed_at_utc = self._format_utc_datetime(observed_dt)
        broker_time_utc = str(data.get("broker_time_utc", "")).strip()
        if broker_time_utc:
            utc_dt = self._parse_datetime(broker_time_utc, assume_utc=True)
            broker_wall = broker_dt.replace(tzinfo=None)
            utc_wall = utc_dt.astimezone(timezone.utc).replace(tzinfo=None)
            measured_offset = (broker_wall - utc_wall).total_seconds() / 3600
            if abs(measured_offset - broker_utc_offset) > 0.01:
                raise ValueError("broker_time and broker_time_utc disagree with broker_utc_offset")
            broker_time_utc = self._format_utc_datetime(utc_dt)

        previous = self._conn.execute(
            "SELECT broker_utc_offset FROM mt4_feed_heartbeat WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        if previous and previous[0] is not None:
            previous_offset = self._validate_offset(previous[0])
            if abs(previous_offset - broker_utc_offset) > 1:
                raise ValueError("inconsistent Broker UTC offset; only a one-hour DST change is allowed")

        self._conn.execute("""
            INSERT OR REPLACE INTO mt4_feed_heartbeat (
                source_id, account, server, broker_time, broker_time_utc,
                broker_utc_offset, observed_at_utc, last_sequence, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source_id, account, server, broker_time, broker_time_utc,
            broker_utc_offset, observed_at_utc, last_sequence, schema_version
        ))
        self._conn.execute("""
            INSERT OR REPLACE INTO mt4_feed_clock_offsets
                (source_id, broker_date, broker_utc_offset, observed_at_utc)
            VALUES (?, ?, ?, ?)
        """, (source_id, broker_dt.date().isoformat(), broker_utc_offset, observed_at_utc))
        self._conn.commit()
        self._finish_ephemeral()

    def get_latest_heartbeat(self, source_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve the latest stored heartbeat record."""
        self._ensure_open()
        if source_id:
            cursor = self._conn.execute(
                "SELECT * FROM mt4_feed_heartbeat WHERE source_id = ?", (source_id,)
            )
        else:
            cursor = self._conn.execute(
                "SELECT * FROM mt4_feed_heartbeat ORDER BY observed_at_utc DESC LIMIT 1"
            )
        row = cursor.fetchone()
        result = dict(row) if row else None
        self._finish_ephemeral()
        return result

    def get_active_source_id(self, max_age_seconds: int = 60) -> Optional[str]:
        """Return the source_id of the freshest verified heartbeat.

        A source is active only when its heartbeat is fresh, its clock is
        verified (a valid broker_utc_offset exists), and its schema matches the
        current feed contract.  Returns ``None`` when no publisher qualifies.
        """
        hb = self.get_latest_heartbeat()
        if not hb:
            return None
        if int(hb.get("schema_version", 0)) != 2:
            return None
        if hb.get("broker_utc_offset") is None:
            return None
        obs_str = str(hb.get("observed_at_utc") or "")
        try:
            if "T" in obs_str:
                obs_dt = datetime.fromisoformat(obs_str)
            else:
                obs_dt = datetime.strptime(obs_str, "%Y-%m-%d %H:%M:%S")
            if obs_dt.tzinfo is None:
                obs_dt = obs_dt.replace(tzinfo=timezone.utc)
            age_sec = (datetime.now(timezone.utc) - obs_dt).total_seconds()
            if age_sec < 0 or age_sec > max_age_seconds:
                return None
        except (TypeError, ValueError):
            return None
        return str(hb.get("source_id") or "mt4_ea")

    def get_broker_utc_offset(self, broker_date=None, source_id: Optional[str] = None) -> int:
        """Return a verified Broker-date offset from heartbeats or raw bar UTC timestamps."""
        self._ensure_open()
        try:
            if broker_date is None:
                query = "SELECT broker_utc_offset FROM mt4_feed_heartbeat"
                params = ()
                if source_id:
                    query += " WHERE source_id = ?"
                    params = (source_id,)
                query += " ORDER BY observed_at_utc DESC LIMIT 1"
                row = self._conn.execute(query, params).fetchone()
            else:
                date_text = broker_date.isoformat() if hasattr(broker_date, "isoformat") else str(broker_date)
                if source_id:
                    row = self._conn.execute(
                        "SELECT broker_utc_offset FROM mt4_feed_clock_offsets WHERE source_id = ? AND broker_date = ?",
                        (source_id, date_text),
                    ).fetchone()
                else:
                    row = self._conn.execute(
                        "SELECT broker_utc_offset FROM mt4_feed_clock_offsets WHERE broker_date = ? ORDER BY observed_at_utc DESC LIMIT 1",
                        (date_text,),
                    ).fetchone()
                if row is None:
                    return self._derive_and_cache_bar_offset(date_text, source_id)
            if row is None:
                raise ValueError("no verified Broker UTC offset is available")
            raw_offset = row["broker_utc_offset"] if isinstance(row, (sqlite3.Row, dict)) else row[0]
            if raw_offset is None:
                raise ValueError("no verified Broker UTC offset is available")
            return self._validate_offset(raw_offset)
        finally:
            self._finish_ephemeral()

    def is_broker_utc_offset_verified(self, broker_date=None) -> bool:
        """Return whether a single unambiguous Broker UTC offset is verified for a date.

        ``True`` when a unique offset exists for ``broker_date`` (multiple
        sources agreeing on the same offset are fine).  ``False`` when the
        offset is missing or when sources publish conflicting offsets — never
        picks the most recent row when sources disagree.  Without a date, uses
        the latest recorded offset.
        """
        self._ensure_open()
        try:
            if broker_date is None:
                row = self._conn.execute(
                    "SELECT broker_utc_offset FROM mt4_feed_clock_offsets ORDER BY observed_at_utc DESC LIMIT 1"
                ).fetchone()
                if not row or row["broker_utc_offset"] is None:
                    return False
                try:
                    self._validate_offset(row["broker_utc_offset"])
                    return True
                except Exception:
                    return False
            date_text = broker_date.isoformat() if hasattr(broker_date, "isoformat") else str(broker_date)
            rows = self._conn.execute(
                "SELECT broker_utc_offset FROM mt4_feed_clock_offsets WHERE broker_date = ?",
                (date_text,),
            ).fetchall()
            offsets = set()
            for row in rows:
                if row["broker_utc_offset"] is None:
                    continue
                try:
                    offsets.add(self._validate_offset(row["broker_utc_offset"]))
                except Exception:
                    return False
            if not offsets:
                # No cached heartbeat offset for this date: try deriving one
                # single consistent offset from the persisted bars themselves.
                try:
                    self._derive_and_cache_bar_offset(date_text, None)
                    return True
                except Exception:
                    return False
            return len(offsets) == 1
        finally:
            self._finish_ephemeral()

    def _derive_and_cache_bar_offset(self, date_text: str, source_id: Optional[str]) -> int:
        """Derive one historical offset from persisted Broker and UTC bar timestamps."""
        query = """
            SELECT source_id, broker_open_at, utc_open_at, received_at_utc
            FROM mt4_feed_bars
            WHERE substr(broker_open_at, 1, 10) = ?
              AND utc_open_at <> ''
              AND is_complete = 1
        """
        params = [date_text]
        if source_id:
            query += " AND source_id = ?"
            params.append(source_id)
        query += " ORDER BY source_id, broker_open_at"
        rows = self._conn.execute(query, params).fetchall()
        if not rows:
            raise ValueError("no verified Broker UTC offset is available")

        offsets_by_source: Dict[str, list[tuple[datetime, int, str]]] = {}
        for row in rows:
            broker_dt = self._parse_datetime(row["broker_open_at"], assume_utc=False).replace(tzinfo=None)
            utc_dt = self._parse_datetime(row["utc_open_at"], assume_utc=True).astimezone(timezone.utc).replace(tzinfo=None)
            raw_offset = (broker_dt - utc_dt).total_seconds() / 3600
            rounded_offset = round(raw_offset)
            if abs(raw_offset - rounded_offset) > (1 / 3600):
                raise ValueError("historical bar Broker UTC offset is not a whole hour")
            offset = self._validate_offset(rounded_offset)
            offsets_by_source.setdefault(str(row["source_id"]), []).append(
                (broker_dt, offset, str(row["received_at_utc"]))
            )

        derived_by_source: Dict[str, tuple[int, str]] = {}
        for source, values in offsets_by_source.items():
            ordered = sorted(values, key=lambda item: item[0])
            unique_offsets = {offset for _, offset, _ in ordered}
            if len(unique_offsets) > 2 or max(unique_offsets) - min(unique_offsets) > 1:
                raise ValueError("inconsistent historical Broker UTC offsets")
            transitions = sum(
                current[1] != previous[1]
                for previous, current in zip(ordered, ordered[1:])
            )
            if transitions > 1:
                raise ValueError("inconsistent historical Broker UTC offset transition")
            _, offset, observed_at_utc = ordered[-1]
            derived_by_source[source] = (offset, observed_at_utc)

        offsets = {value[0] for value in derived_by_source.values()}
        if len(offsets) != 1:
            raise ValueError("inconsistent Broker UTC offsets across feed sources")
        offset = offsets.pop()
        for source, (source_offset, observed_at_utc) in derived_by_source.items():
            self._conn.execute(
                """
                INSERT OR REPLACE INTO mt4_feed_clock_offsets
                    (source_id, broker_date, broker_utc_offset, observed_at_utc)
                VALUES (?, ?, ?, ?)
                """,
                (source, date_text, source_offset, observed_at_utc),
            )
        self._conn.commit()
        return offset

    def get_latest_completed_broker_datetime(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> Optional[datetime]:
        """Return the latest completed Broker wall time persisted by the MT4 feed."""
        self._ensure_open()
        try:
            clauses = ["is_complete = 1", "broker_close_at <> ''"]
            params = []
            if symbol:
                clauses.append("canonical_symbol = ?")
                params.append(symbol)
            if timeframe:
                clauses.append("timeframe = ?")
                params.append(timeframe)
            where = " AND ".join(clauses)
            row = self._conn.execute(
                f"SELECT broker_close_at FROM mt4_feed_bars WHERE {where} ORDER BY broker_close_at DESC LIMIT 1",
                params,
            ).fetchone()
            if not row:
                return None
            return self._parse_datetime(row["broker_close_at"], assume_utc=False).replace(tzinfo=None)
        finally:
            self._finish_ephemeral()

    def get_latest_bar_received_at(self) -> Optional[datetime]:
        """Return the newest bar arrival time (UTC, aware) across the whole feed.

        The History Rebuild Worker uses this to detect persisted-bar changes
        without any dependency on a live heartbeat or ``feed_connected``.
        """
        self._ensure_open()
        try:
            row = self._conn.execute(
                "SELECT MAX(received_at_utc) AS m FROM mt4_feed_bars"
            ).fetchone()
            if not row or not row["m"]:
                return None
            parsed = self._parse_datetime(row["m"], assume_utc=True)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        finally:
            self._finish_ephemeral()

    def get_bar_availability(self, lookback_days: int = 45) -> Dict[str, Any]:
        """Summarize persisted completed bars for diagnostics and offline rebuild.

        Returns a dict with:
        - ``bars_available``: True when any completed bar exists within the
          lookback window (regardless of heartbeat freshness).
        - ``latest_bar_by_symbol_timeframe``: mapping ``"SYMBOL:TIMEFRAME"`` to
          the latest completed ``broker_close_at`` for that symbol/timeframe.
        - ``summary``: one row per symbol/timeframe with count and oldest/latest
          Broker timestamps.
        """
        self._ensure_open()
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
            rows = self._conn.execute("""
                SELECT canonical_symbol, timeframe, COUNT(*) AS bar_count,
                       MIN(broker_open_at) AS oldest_open,
                       MAX(broker_close_at) AS latest_close
                FROM mt4_feed_bars
                WHERE is_complete = 1 AND broker_close_at >= ?
                GROUP BY canonical_symbol, timeframe
                ORDER BY canonical_symbol, timeframe
            """, (cutoff,)).fetchall()
            summary = [dict(row) for row in rows]
            latest_by_symbol_timeframe = {
                f"{row['canonical_symbol']}:{row['timeframe']}": row["latest_close"]
                for row in summary
            }
            return {
                "bars_available": bool(summary),
                "latest_bar_by_symbol_timeframe": latest_by_symbol_timeframe,
                "summary": summary,
            }
        finally:
            self._finish_ephemeral()

    def get_clock_offset_history(self, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return cached per-date offsets for DST-aware history rebuilds."""
        self._ensure_open()
        if source_id:
            rows = self._conn.execute(
                "SELECT * FROM mt4_feed_clock_offsets WHERE source_id = ? ORDER BY broker_date",
                (source_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM mt4_feed_clock_offsets ORDER BY broker_date, source_id"
            ).fetchall()
        result = [dict(row) for row in rows]
        self._finish_ephemeral()
        return result

    def save_bars(self, source_id: str, symbol: str, resolved_symbol: str, timeframe: str, bars: List[Dict[str, Any]]) -> int:
        """Batch save raw completed bars into mt4_feed_bars table."""
        self._ensure_open()
        now_iso = datetime.now(timezone.utc).isoformat()
        rows = []
        for b in bars:
            broker_open_at = str(b.get("broker_open_at", b.get("open_time", ""))).strip()
            if not broker_open_at:
                continue
            broker_open_at = self._format_broker_datetime(self._parse_datetime(broker_open_at, assume_utc=False))
            values = []
            for field in ("open", "high", "low", "close"):
                raw = b.get(field)
                try:
                    value = Decimal(str(raw))
                except (InvalidOperation, TypeError, ValueError):
                    raise ValueError(f"invalid {field} for {symbol} {broker_open_at}")
                if not value.is_finite():
                    raise ValueError(f"non-finite {field} for {symbol} {broker_open_at}")
                values.append(format(value, "f"))
            utc_open_at = str(b.get("utc_open_at", "")).strip()
            if utc_open_at:
                utc_open_at = self._format_utc_datetime(self._parse_datetime(utc_open_at, assume_utc=True))
            else:
                offset_row = self._conn.execute(
                    "SELECT broker_utc_offset FROM mt4_feed_clock_offsets WHERE source_id=? AND broker_date=?",
                    (source_id, broker_open_at[:10]),
                ).fetchone()
                if offset_row is None:
                    offset_row = self._conn.execute(
                        "SELECT broker_utc_offset FROM mt4_feed_heartbeat WHERE source_id=?",
                        (source_id,),
                    ).fetchone()
                if offset_row and offset_row[0] is not None:
                    broker_open_dt = self._parse_datetime(broker_open_at, assume_utc=False)
                    utc_open_at = self._format_utc_datetime(
                        (broker_open_dt - timedelta(hours=self._validate_offset(offset_row[0]))).replace(tzinfo=timezone.utc)
                    )
            broker_close_at = str(b.get("broker_close_at", "")).strip()
            if not broker_close_at:
                broker_close_at = self._derive_close_at(broker_open_at, timeframe)
            else:
                broker_close_at = self._format_broker_datetime(self._parse_datetime(broker_close_at, assume_utc=False))
            tick_vol = int(b.get("tick_volume", b.get("volume", 0)))
            is_comp = 1 if b.get("is_complete", True) else 0
            rows.append((symbol, resolved_symbol, timeframe, broker_open_at, broker_close_at, utc_open_at,
                         values[0], values[1], values[2], values[3], tick_vol, is_comp,
                         now_iso, source_id, 2))

        with self._conn:
            self._conn.executemany("""
            INSERT OR REPLACE INTO mt4_feed_bars (
                canonical_symbol, resolved_mt4_symbol, timeframe, broker_open_at, broker_close_at,
                utc_open_at, open_exact, high_exact, low_exact, close_exact, tick_volume, is_complete,
                received_at_utc, source_id, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
        result = len(rows)
        self._finish_ephemeral()
        return result

    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start_broker_str: str,
        end_broker_str: str
    ) -> List[Dict[str, Any]]:
        """Query raw candles between Broker timestamps.

        The Signal Engine requires the EA-published timeframe to exist exactly;
        this store intentionally does not synthesize H1/H4 bars from M30.
        """
        self._ensure_open()
        tf_str = str(timeframe)
        norm_tf = self._normalize_tf(tf_str)
        start_broker_str = self._format_broker_datetime(self._parse_datetime(start_broker_str, assume_utc=False))
        end_broker_str = self._format_broker_datetime(self._parse_datetime(end_broker_str, assume_utc=False))
        cursor = self._conn.execute("""
            SELECT * FROM mt4_feed_bars
            WHERE canonical_symbol = ? AND (timeframe = ? OR timeframe = ?)
              AND broker_open_at >= ? AND broker_open_at <= ?
            ORDER BY broker_open_at ASC
        """, (symbol, tf_str, norm_tf, start_broker_str, end_broker_str))
        rows = cursor.fetchall()
        if rows:
            result = [self._format_bar_dict(row) for row in rows]
            self._finish_ephemeral()
            return result

        self._finish_ephemeral()
        return []

    def get_exact_bar(self, symbol: str, timeframe: str, broker_open_str: str, *, source_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Query a single exact bar matching symbol, timeframe, and broker_open_at.

        The Signal Engine must pass the active ``source_id`` so the query never
        selects an arbitrary publisher row.  Without a ``source_id`` the store
        fails closed when multiple sources disagree on OHLC
        (``AmbiguousMT4FeedSourceError``); identical rows are still resolved
        deterministically by ``received_at_utc DESC, source_id ASC``.
        """
        self._ensure_open()
        tf_str = str(timeframe)
        norm_tf = self._normalize_tf(tf_str)
        broker_open_str = self._format_broker_datetime(self._parse_datetime(broker_open_str, assume_utc=False))
        params: List[Any] = [symbol, tf_str, norm_tf, broker_open_str]
        query = """
            SELECT * FROM mt4_feed_bars
            WHERE canonical_symbol = ? AND (timeframe = ? OR timeframe = ?)
              AND broker_open_at = ?
        """
        if source_id:
            query += " AND source_id = ?"
            params.append(str(source_id))
        query += " ORDER BY received_at_utc DESC, source_id ASC"
        rows = self._conn.execute(query, params).fetchall()
        if not rows:
            self._finish_ephemeral()
            return None
        if not source_id and len(rows) > 1:
            distinct_ohlc = {
                (r["open_exact"], r["high_exact"], r["low_exact"], r["close_exact"])
                for r in rows
            }
            if len(distinct_ohlc) > 1:
                self._finish_ephemeral()
                raise AmbiguousMT4FeedSourceError(
                    f"multiple MT4 feed sources publish conflicting OHLC for "
                    f"{symbol} {norm_tf} at {broker_open_str}"
                )
        row = rows[0]
        result = self._format_bar_dict(row)
        self._finish_ephemeral()
        return result

    def clear(self):
        """Clear feed bars for unit testing."""
        self._ensure_open()
        self._conn.execute("DELETE FROM mt4_feed_bars")
        self._conn.execute("DELETE FROM mt4_feed_heartbeat")
        self._conn.commit()
        self._finish_ephemeral()

    @staticmethod
    def _normalize_tf(tf: str) -> str:
        mapping = {"30": "M30", "M30": "30", "60": "H1", "H1": "60", "240": "H4", "H4": "240", "16385": "M30", "16388": "H4"}
        return mapping.get(str(tf), str(tf))

    @staticmethod
    def _format_bar_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        b_str = d["broker_open_at"]
        try:
            if "T" in b_str:
                dt = datetime.fromisoformat(b_str)
            else:
                dt = datetime.strptime(b_str, "%Y-%m-%d %H:%M:%S")
            utc_text = str(d.get("utc_open_at") or "").strip().replace("Z", "+00:00")
            if utc_text:
                utc_dt = datetime.fromisoformat(utc_text)
                if utc_dt.tzinfo is None:
                    utc_dt = utc_dt.replace(tzinfo=timezone.utc)
                ts = int(utc_dt.astimezone(timezone.utc).timestamp())
            else:
                # A Broker wall time without a verified offset is not an
                # absolute timestamp.  Do not silently reinterpret it as UTC.
                ts = 0
        except Exception:
            dt = datetime.now()
            ts = 0

        exact_open = d.get("open_exact") if d.get("open_exact") is not None else str(d.get("open"))
        exact_high = d.get("high_exact") if d.get("high_exact") is not None else str(d.get("high"))
        exact_low = d.get("low_exact") if d.get("low_exact") is not None else str(d.get("low"))
        exact_close = d.get("close_exact") if d.get("close_exact") is not None else str(d.get("close"))
        return {
            "time": ts,
            "open": float(exact_open),
            "high": float(exact_high),
            "low": float(exact_low),
            "close": float(exact_close),
            "open_exact": exact_open,
            "high_exact": exact_high,
            "low_exact": exact_low,
            "close_exact": exact_close,
            "tick_volume": d["tick_volume"],
            "broker_open_at": d["broker_open_at"],
            "broker_close_at": d.get("broker_close_at", ""),
            "utc_open_at": d.get("utc_open_at", ""),
            "broker_dt": dt,
            "is_complete": bool(d["is_complete"]),
            "canonical_symbol": d["canonical_symbol"],
            "resolved_mt4_symbol": d.get("resolved_mt4_symbol", d["canonical_symbol"]),
            "timeframe": d["timeframe"],
            "source_id": d.get("source_id", "mt4_ea"),
            "schema_version": int(d.get("schema_version", 2)),
        }

    @staticmethod
    def _derive_close_at(broker_open_at: str, timeframe: str) -> str:
        """Derive the close boundary only when an EA omits it."""
        try:
            opened = datetime.fromisoformat(str(broker_open_at).replace("Z", "+00:00"))
            minutes = {"M30": 30, "30": 30, "H1": 60, "60": 60, "H4": 240, "240": 240}.get(str(timeframe), 0)
            if not minutes:
                return ""
            return (opened + timedelta(minutes=minutes)).replace(tzinfo=None).isoformat(sep=" ")
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def _validate_offset(value) -> int:
        try:
            offset = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("broker_utc_offset must be an integer") from exc
        if offset < -14 or offset > 14:
            raise ValueError("broker_utc_offset is outside the valid UTC range")
        return offset

    @staticmethod
    def _format_broker_datetime(value: datetime) -> str:
        return value.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _format_utc_datetime(value: datetime) -> str:
        current = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _parse_datetime(value, assume_utc: bool) -> datetime:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            parsed = None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
                try:
                    parsed = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
            if parsed is None:
                raw = text.split(".")[0]
                try:
                    parsed = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    parsed = None
            if parsed is None:
                raise ValueError(f"unsupported datetime: {value}")
        if parsed.tzinfo is None and assume_utc:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
