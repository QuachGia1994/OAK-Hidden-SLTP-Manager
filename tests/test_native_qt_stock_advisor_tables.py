"""Regression tests for the NativeQt stock-advisor table rendering and market.db loader."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from oak_qt_shell import (
    advisory_rows_from_payload,
    load_stock_rows,
)


class StockRowsTests(unittest.TestCase):
    """Tests for load_stock_rows (market.db reader)."""

    def test_load_stock_rows_returns_expected_shape(self) -> None:
        db_path = ROOT / "data" / "market.db"
        if not db_path.is_file():
            self.skipTest("data/market.db not present")
        rows = load_stock_rows(db_path=db_path, limit=50)
        self.assertIsInstance(rows, list)
        if not rows:
            self.skipTest("market.db has no eod_prices rows")
        expected_keys = {
            "date", "symbol", "exchange", "open", "high", "low", "close",
            "volume", "value", "foreign_buy_value", "foreign_sell_value",
        }
        for row in rows[:5]:
            self.assertIsInstance(row, dict)
            self.assertEqual(set(row.keys()), expected_keys)
            self.assertIsInstance(row["date"], str)
            self.assertIsInstance(row["symbol"], str)

    def test_load_stock_rows_empty_when_missing_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nonexistent" / "market.db"
            rows = load_stock_rows(db_path=missing)
            self.assertEqual(rows, [])


class AdvisoryRowsTests(unittest.TestCase):
    """Tests for advisory_rows_from_payload (JSON parser)."""

    def test_advisory_rows_from_payload_ranks(self) -> None:
        payload = {
            "schema_version": 2,
            "recommendations": [
                {"symbol": "HCT", "direction": "BUY", "score": 19.0, "latest_close": 10.5, "rank": 1},
                {"symbol": "HFX", "direction": "SELL", "score": 12.5, "latest_close": 8.2, "rank": 2},
                {"symbol": "ZZZ", "direction": "BUY", "score": 5.0, "latest_close": 1.0, "rank": 0},
            ],
        }
        rows = advisory_rows_from_payload(payload)
        self.assertEqual(len(rows), 3)
        # HCT rank 1 first, HFX rank 2 second, rank-0 last
        self.assertEqual(rows[0][0], "HCT")
        self.assertEqual(rows[0][4], 1)
        self.assertEqual(rows[1][0], "HFX")
        self.assertEqual(rows[1][4], 2)
        self.assertEqual(rows[2][0], "ZZZ")
        self.assertEqual(rows[2][4], 0)
        # Verify tuple contents
        self.assertEqual(rows[0][1], "BUY")
        self.assertAlmostEqual(rows[0][2], 19.0)
        self.assertEqual(rows[0][3], 10.5)

    def test_advisory_rows_from_payload_invalid_returns_empty(self) -> None:
        for bad in (None, {}, {"recommendations": "x"}, {"recommendations": [None, 1]}):
            result = advisory_rows_from_payload(bad)
            self.assertEqual(result, [], f"Expected empty for {bad!r}")

    def test_advisory_rows_from_payload_real_file(self) -> None:
        rec_file = ROOT / "stock_recommendation.json"
        if not rec_file.is_file():
            self.skipTest("stock_recommendation.json not present")
        import json
        payload = json.loads(rec_file.read_text(encoding="utf-8"))
        rows = advisory_rows_from_payload(payload)
        if not rows:
            self.skipTest("stock_recommendation.json has no valid recommendations")
        # Verify first row has valid tuple structure
        self.assertEqual(len(rows[0]), 5)
        self.assertIsInstance(rows[0][0], str)  # symbol
        self.assertIn(rows[0][1], ("BUY", "SELL"))  # direction
        self.assertIsInstance(rows[0][2], float)  # score
        self.assertIsInstance(rows[0][4], int)  # rank
        # If any rows have rank > 0, the lowest rank should come first
        positive_ranks = [r for r in rows if r[4] > 0]
        if positive_ranks:
            self.assertEqual(positive_ranks[0][4], min(r[4] for r in positive_ranks))

    def test_advisory_rows_sorts_by_symbol_within_same_rank(self) -> None:
        payload = {
            "recommendations": [
                {"symbol": "ZOO", "direction": "BUY", "score": 10.0, "latest_close": 5.0, "rank": 3},
                {"symbol": "AAA", "direction": "SELL", "score": 8.0, "latest_close": 3.0, "rank": 3},
            ],
        }
        rows = advisory_rows_from_payload(payload)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "AAA")
        self.assertEqual(rows[1][0], "ZOO")


if __name__ == "__main__":
    unittest.main()
