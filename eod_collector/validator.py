"""Validator module for EOD records and trading sessions."""
from __future__ import annotations

from datetime import date, datetime, timezone
import logging
from typing import Sequence

from eod_collector.models import EODRecord

logger = logging.getLogger("eod_collector")

VALID_EXCHANGES = {"HOSE", "HNX", "UPCOM"}


class ValidationError(ValueError):
    """Validation failure with explicit reason."""
    pass


class EODValidator:
    """Validator for individual records and complete exchange sessions."""

    def __init__(self, holidays: list[str] | None = None) -> None:
        self.holidays = set(holidays or [])

    def validate_record(self, record: EODRecord) -> None:
        """Validate an individual EODRecord row."""
        if not record.symbol:
            raise ValidationError("Symbol cannot be empty")
        
        if record.exchange not in VALID_EXCHANGES:
            raise ValidationError(f"Exchange '{record.exchange}' is not in {VALID_EXCHANGES}")

        # Validate date
        try:
            record_date = datetime.strptime(record.date, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError(f"Invalid date format '{record.date}', expected YYYY-MM-DD")

        local_today = datetime.now(timezone.utc).date()
        if record_date > local_today:
            raise ValidationError(f"Trading date {record.date} is in the future")

        if record_date.weekday() in (5, 6):
            raise ValidationError(f"Trading date {record.date} falls on a weekend (Sat/Sun)")

        if record.date in self.holidays:
            raise ValidationError(f"Trading date {record.date} is a configured holiday")

        # Validate OHLC logic
        if record.low > record.open or record.open > record.high:
            raise ValidationError(f"OHLC violation for {record.symbol}: low ({record.low}) <= open ({record.open}) <= high ({record.high}) failed")

        if record.low > record.close or record.close > record.high:
            raise ValidationError(f"OHLC violation for {record.symbol}: low ({record.low}) <= close ({record.close}) <= high ({record.high}) failed")

        if record.volume < 0:
            raise ValidationError(f"Volume cannot be negative: {record.volume}")

        if record.value < 0:
            raise ValidationError(f"Value cannot be negative: {record.value}")

    def validate_session(
        self,
        records: Sequence[EODRecord],
        exchange: str,
        trading_date: date,
        min_symbols: int = 10,
        previous_count: int | None = None,
    ) -> list[str]:
        """Validate a full trading session for an exchange.

        Returns:
            list[str]: Warning messages (if any). Raises ValidationError on critical failures.
        """
        warnings: list[str] = []

        if trading_date.weekday() in (5, 6):
            raise ValidationError(f"Cannot collect session for weekend date {trading_date.isoformat()}")

        date_str = trading_date.strftime("%Y-%m-%d")
        if date_str in self.holidays:
            raise ValidationError(f"Cannot collect session for holiday date {date_str}")

        if not records:
            raise ValidationError(f"Session records for {exchange} on {date_str} is completely empty")

        if len(records) < min_symbols:
            raise ValidationError(f"Abnormally low symbol count for {exchange} on {date_str}: {len(records)} < {min_symbols}")

        if previous_count is not None and previous_count > 0:
            drop_ratio = (previous_count - len(records)) / previous_count
            if drop_ratio > 0.3:
                msg = f"Symbol count dropped significantly for {exchange}: {previous_count} -> {len(records)} ({drop_ratio*100:.1f}% drop)"
                logger.warning(msg)
                warnings.append(msg)

        total_volume = sum(r.volume for r in records)
        if total_volume == 0:
            msg = f"WARNING: Total volume for {exchange} on {date_str} is zero"
            logger.warning(msg)
            warnings.append(msg)

        # Validate every row in session
        for row in records:
            self.validate_record(row)

        return warnings
