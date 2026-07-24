"""Unit tests for EODNormalizer."""
import unittest
from eod_collector.normalizer import EODNormalizer


class TestEODNormalizer(unittest.TestCase):
    def setUp(self) -> None:
        self.normalizer = EODNormalizer(default_exchange="HOSE", default_source="test")

    def test_column_name_mapping_and_number_parsing(self) -> None:
        raw = {
            "Ticker": "fpt",
            "Ngay": "2026-07-24",
            "GiaMua": "125,000",
            "GiaCao": "127,500.5",
            "GiaThap": "124,000",
            "GiaDongCua": "126,000",
            "KLGD": "1,500,000",
            "GTGD": "189,000,000,000",
        }
        rec = self.normalizer.normalize(raw)
        self.assertEqual(rec.symbol, "FPT")
        self.assertEqual(rec.date, "2026-07-24")
        self.assertEqual(rec.exchange, "HOSE")
        self.assertEqual(rec.open, 125.0)
        self.assertEqual(rec.high, 127.5)
        self.assertEqual(rec.low, 124.0)
        self.assertEqual(rec.close, 126.0)
        self.assertEqual(rec.volume, 1500000.0)

    def test_european_number_format(self) -> None:
        raw = {
            "symbol": "HPG",
            "date": "24/07/2026",
            "open": "28.500,0",
            "high": "29.000,0",
            "low": "28.000,0",
            "close": "28.800,0",
            "volume": "10.000.000",
        }
        rec = self.normalizer.normalize(raw)
        self.assertEqual(rec.symbol, "HPG")
        self.assertEqual(rec.date, "2026-07-24")
        self.assertEqual(rec.open, 28.5)
        self.assertEqual(rec.high, 29.0)
        self.assertEqual(rec.close, 28.8)


if __name__ == "__main__":
    unittest.main()
