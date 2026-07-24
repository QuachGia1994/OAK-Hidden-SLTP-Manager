"""Unit tests for Database & EODRepository."""
from pathlib import Path
import tempfile
import unittest

from eod_collector.database import Database
from eod_collector.models import EODRecord
from eod_collector.repository import EODRepository


class TestEODRepository(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_market.db"
        self.db = Database(self.db_path)
        self.repo = EODRepository(self.db)

    def tearDown(self) -> None:
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_upsert_and_query(self) -> None:
        recs = [
            EODRecord(date="2026-07-24", symbol="FPT", exchange="HOSE", open=125.0, high=127.0, low=124.0, close=126.0),
            EODRecord(date="2026-07-24", symbol="HPG", exchange="HOSE", open=28.0, high=29.0, low=27.5, close=28.5),
        ]
        count = self.repo.upsert_records(recs)
        self.assertGreaterEqual(count, 2)

        fetched = self.repo.get_records(exchange="HOSE", trading_date="2026-07-24")
        self.assertEqual(len(fetched), 2)
        self.assertEqual(fetched[0].symbol, "FPT")
        self.assertEqual(fetched[1].symbol, "HPG")

    def test_upsert_idempotency(self) -> None:
        rec1 = EODRecord(date="2026-07-24", symbol="FPT", exchange="HOSE", open=125.0, high=127.0, low=124.0, close=126.0)
        self.repo.upsert_records([rec1])

        # Re-run same date/symbol/exchange with updated close price
        rec2 = EODRecord(date="2026-07-24", symbol="FPT", exchange="HOSE", open=125.0, high=127.0, low=124.0, close=128.0)
        self.repo.upsert_records([rec2])

        fetched = self.repo.get_records(symbol="FPT", trading_date="2026-07-24")
        self.assertEqual(len(fetched), 1)
        self.assertEqual(fetched[0].close, 128.0)

    def test_latest_date_and_counts(self) -> None:
        recs = [
            EODRecord(date="2026-07-23", symbol="FPT", exchange="HOSE", open=120, high=125, low=119, close=124),
            EODRecord(date="2026-07-24", symbol="FPT", exchange="HOSE", open=125, high=127, low=124, close=126),
            EODRecord(date="2026-07-24", symbol="SHS", exchange="HNX", open=18, high=19, low=17.5, close=18.5),
        ]
        self.repo.upsert_records(recs)

        self.assertEqual(self.repo.get_latest_date(), "2026-07-24")
        self.assertEqual(self.repo.get_total_sessions_count(), 2)
        counts = self.repo.get_symbol_count_by_exchange()
        self.assertEqual(counts.get("HOSE"), 1)
        self.assertEqual(counts.get("HNX"), 1)


if __name__ == "__main__":
    unittest.main()
