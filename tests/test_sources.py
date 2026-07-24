"""Unit tests for HOSE, HNX, and UPCOM Data Sources."""
from datetime import date
import unittest
from eod_collector.sources.hose import HOSEDataSource
from eod_collector.sources.hnx import HNXDataSource
from eod_collector.sources.upcom import UPCOMDataSource


class TestDataSources(unittest.TestCase):
    def test_hose_source_fetch_and_parse(self) -> None:
        src = HOSEDataSource()
        self.assertEqual(src.exchange_name, "HOSE")
        
        res = src.fetch(date(2026, 7, 24))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(len(res.content) > 0)
        self.assertTrue(len(res.sha256) > 0)

        rows = src.parse(res.content)
        self.assertGreaterEqual(len(rows), 30)
        self.assertEqual(rows[0]["symbol"], "ACB")

    def test_hnx_source_fetch_and_parse(self) -> None:
        src = HNXDataSource()
        self.assertEqual(src.exchange_name, "HNX")

        res = src.fetch(date(2026, 7, 24))
        self.assertEqual(res.status_code, 200)
        rows = src.parse(res.content)
        self.assertGreaterEqual(len(rows), 10)

    def test_upcom_source_fetch_and_parse(self) -> None:
        src = UPCOMDataSource()
        self.assertEqual(src.exchange_name, "UPCOM")

        res = src.fetch(date(2026, 7, 24))
        self.assertEqual(res.status_code, 200)
        rows = src.parse(res.content)
        self.assertGreaterEqual(len(rows), 10)


if __name__ == "__main__":
    unittest.main()
