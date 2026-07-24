"""Collector service orchestrating sources, raw archive, normalization, validation, and storage."""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, timezone
import json
import logging
from pathlib import Path
from typing import Any, Sequence

from eod_collector.config import Config
from eod_collector.database import Database
from eod_collector.models import EODRecord, RawFetchMetadata
from eod_collector.normalizer import EODNormalizer
from eod_collector.repository import EODRepository
from eod_collector.sources.base import EODDataSource, RawFetchResult
from eod_collector.sources.hose import HOSEDataSource
from eod_collector.sources.hnx import HNXDataSource
from eod_collector.sources.upcom import UPCOMDataSource
from eod_collector.sources.vps_market import VPSMarketDataSource
from eod_collector.validator import EODValidator, ValidationError

logger = logging.getLogger("eod_collector")


class CollectorService:
    """Main orchestrator for Local EOD Market Data Collector."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config.load()
        self.database = Database(self.config.database.path)
        self.repository = EODRepository(self.database)
        self.validator = EODValidator(holidays=self.config.collector.holidays)

        self.sources: dict[str, EODDataSource] = {}
        # VPS unified source covers all exchanges with real data
        self.sources["VN_ALL"] = VPSMarketDataSource()
        # Legacy per-exchange sources (kept for backward compatibility but VPS takes priority)
        if self.config.sources.hose_enabled:
            self.sources["HOSE"] = HOSEDataSource()
        if self.config.sources.hnx_enabled:
            self.sources["HNX"] = HNXDataSource()
        if self.config.sources.upcom_enabled:
            self.sources["UPCOM"] = UPCOMDataSource()

    def update(self, trading_date: date | None = None) -> dict[str, int]:
        """Update market data for a single trading date across all enabled exchanges."""
        target_date = trading_date or self._default_trading_date()
        if target_date.weekday() in (5, 6):
            logger.info("Date %s is a weekend. Skipping update.", target_date.isoformat())
            return {}

        results: dict[str, int] = {}
        for exchange_name, source in self.sources.items():
            try:
                count = self._collect_exchange_date(source, target_date)
                results[exchange_name] = count
            except Exception as err:
                logger.error("Failed to collect %s for %s: %s", exchange_name, target_date.isoformat(), err)
                raise
        return results

    def backfill(
        self,
        days: int | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict[str, int]:
        """Backfill historical data for a range of dates."""
        today = self._default_trading_date()
        if from_date and to_date:
            start_date, end_date = from_date, to_date
        elif days and days > 0:
            end_date = today
            start_date = today - timedelta(days=days)
        else:
            end_date = today
            start_date = today - timedelta(days=30)

        total_collected: dict[str, int] = {ex: 0 for ex in self.sources}
        curr = start_date
        while curr <= end_date:
            if curr.weekday() not in (5, 6) and curr.strftime("%Y-%m-%d") not in self.config.collector.holidays:
                for exchange_name, source in self.sources.items():
                    try:
                        count = self._collect_exchange_date(source, curr)
                        total_collected[exchange_name] = total_collected.get(exchange_name, 0) + count
                    except Exception as err:
                        logger.warning("Backfill error for %s on %s: %s", exchange_name, curr.isoformat(), err)
            curr += timedelta(days=1)
        return total_collected

    def validate(self, trading_date: date | None = None) -> dict[str, list[str]]:
        """Validate saved records in DB against business rules."""
        target_date = trading_date or self._default_trading_date()
        date_str = target_date.strftime("%Y-%m-%d")
        all_warnings: dict[str, list[str]] = {}

        for exchange_name in self.sources:
            records = self.repository.get_records(exchange=exchange_name, trading_date=date_str)
            min_symbols = getattr(self.config.collector, f"minimum_symbols_{exchange_name.lower()}", 10)
            try:
                warnings = self.validator.validate_session(records, exchange_name, target_date, min_symbols=min_symbols)
                all_warnings[exchange_name] = warnings
            except ValidationError as err:
                logger.error("Validation error for %s on %s: %s", exchange_name, date_str, err)
                all_warnings[exchange_name] = [f"CRITICAL: {err}"]
        return all_warnings

    def status(self) -> dict[str, Any]:
        """Return diagnostic status information for CLI."""
        latest_date = self.repository.get_latest_date()
        symbol_counts = self.repository.get_symbol_count_by_exchange()
        total_sessions = self.repository.get_total_sessions_count()

        active_sources = [ex for ex, src in self.sources.items()]

        missing_dates = []
        if latest_date:
            thirty_days_ago = (datetime.strptime(latest_date, "%Y-%m-%d").date() - timedelta(days=30)).strftime("%Y-%m-%d")
            missing_dates = self.repository.get_missing_dates(thirty_days_ago, latest_date, self.config.collector.holidays)

        return {
            "latest_date": latest_date or "N/A",
            "symbol_counts_by_exchange": symbol_counts,
            "saved_sessions_count": total_sessions,
            "active_sources": active_sources,
            "missing_dates": missing_dates,
        }

    def export(
        self,
        symbol: str | None = None,
        exchange: str | None = None,
        output_path: str | Path | None = None,
    ) -> Path:
        """Export EOD records to CSV file."""
        records = self.repository.get_records(symbol=symbol, exchange=exchange)
        out = Path(output_path) if output_path else Path("data/export.csv")
        out.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "date", "symbol", "exchange", "open", "high", "low", "close",
            "reference_price", "ceiling_price", "floor_price", "volume", "value",
            "source", "collected_at"
        ]
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in records:
                d = r.to_dict()
                row = {k: d.get(k, "") for k in fieldnames}
                writer.writerow(row)

        logger.info("Exported %d records to %s", len(records), out)
        return out

    def import_file(
        self,
        file_path: str | Path,
        exchange: str,
        trading_date: date | None = None,
    ) -> int:
        """Manual file fallback importer (CSV or XLSX). Must pass normalizer and validator."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Import file not found: {path}")

        raw_content = path.read_bytes()
        source = self.sources.get(exchange.upper()) or HOSEDataSource()
        raw_rows = source.parse(raw_content)

        date_str = trading_date.strftime("%Y-%m-%d") if trading_date else None
        normalizer = EODNormalizer(default_exchange=exchange, default_source="manual_import")
        records = [normalizer.normalize(row, trading_date_override=date_str) for row in raw_rows]

        # Validate whole imported session
        target_date = trading_date or (datetime.strptime(records[0].date, "%Y-%m-%d").date() if records else self._default_trading_date())
        min_symbols = 1  # Manual imports can be targeted subset
        self.validator.validate_session(records, exchange.upper(), target_date, min_symbols=min_symbols)

        # Upsert to database
        saved_count = self.repository.upsert_records(records)
        logger.info("Successfully imported %d records from %s for %s", saved_count, path.name, exchange)
        return saved_count

    def _collect_exchange_date(self, source: EODDataSource, trading_date: date) -> int:
        """Fetch, archive, normalize, validate, and store raw data for one exchange session."""
        date_str = trading_date.strftime("%Y-%m-%d")
        exchange = source.exchange_name

        # 1. Fetch raw data
        raw_fetch = source.fetch(trading_date)

        # 2. Archive raw data to data/raw/<exchange>/<yyyy-mm-dd>/
        self._archive_raw_data(exchange, date_str, raw_fetch)

        # 3. Parse raw data
        raw_rows = source.parse(raw_fetch.content)

        # 4. Normalize
        normalizer = EODNormalizer(default_exchange=exchange, default_source=raw_fetch.source_url)
        records = [normalizer.normalize(row, trading_date_override=date_str) for row in raw_rows]

        # 5. Validate whole session
        min_symbols = getattr(self.config.collector, f"minimum_symbols_{exchange.lower()}", 10)
        prev_count = self.repository.get_count_for_exchange_date(exchange, date_str)
        self.validator.validate_session(records, exchange, trading_date, min_symbols=min_symbols, previous_count=prev_count if prev_count > 0 else None)

        # 6. Upsert to DB
        return self.repository.upsert_records(records)

    def _archive_raw_data(self, exchange: str, date_str: str, raw_fetch: RawFetchResult) -> None:
        """Save raw payload and metadata JSON to disk."""
        raw_dir = self.config.collector.raw_data_dir / exchange.lower() / date_str
        raw_dir.mkdir(parents=True, exist_ok=True)

        ext = ".json" if "json" in raw_fetch.content_type else (".html" if "html" in raw_fetch.content_type else ".raw")
        raw_file = raw_dir / f"source{ext}"
        raw_file.write_bytes(raw_fetch.content)

        meta = RawFetchMetadata(
            source_url=raw_fetch.source_url,
            downloaded_at=raw_fetch.downloaded_at,
            status_code=raw_fetch.status_code,
            content_type=raw_fetch.content_type,
            sha256=raw_fetch.sha256,
            exchange=exchange,
            trading_date=date_str,
        )
        meta_file = raw_dir / "metadata.json"
        meta_file.write_text(json.dumps(meta.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _default_trading_date() -> date:
        now = datetime.now(timezone(timedelta(hours=7)))
        d = now.date()
        if d.weekday() == 5:
            return d - timedelta(days=1)
        if d.weekday() == 6:
            return d - timedelta(days=2)
        return d
