"""Unit tests for EODValidator."""
from datetime import date
import unittest
from eod_collector.models import EODRecord
from eod_collector.validator import EODValidator, ValidationError


class TestEODValidator(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = EODValidator(holidays=["2026-09-02"])

    def test_valid_record(self) -> None:
        rec = EODRecord(
            date="2026-07-24",
            symbol="FPT",
            exchange="HOSE",
            open=125.0,
            high=127.0,
            low=124.0,
            close=126.0,
            volume=100000.0,
            value=126000000.0,
        )
        self.validator.validate_record(rec)  # Should not raise

    def test_invalid_ohlc(self) -> None:
        rec = EODRecord(
            date="2026-07-24",
            symbol="FPT",
            exchange="HOSE",
            open=130.0,  # open > high (127)
            high=127.0,
            low=124.0,
            close=126.0,
        )
        with self.assertRaises(ValidationError):
            self.validator.validate_record(rec)

    def test_weekend_date_rejection(self) -> None:
        rec = EODRecord(
            date="2026-07-26",  # Sunday
            symbol="FPT",
            exchange="HOSE",
            open=125.0,
            high=127.0,
            low=124.0,
            close=126.0,
        )
        with self.assertRaises(ValidationError):
            self.validator.validate_record(rec)

    def test_session_validation_low_symbol_count(self) -> None:
        recs = [
            EODRecord(date="2026-07-24", symbol="FPT", exchange="HOSE", open=10, high=12, low=9, close=11)
        ]
        with self.assertRaises(ValidationError):
            self.validator.validate_session(recs, "HOSE", date(2026, 7, 24), min_symbols=10)


if __name__ == "__main__":
    unittest.main()
