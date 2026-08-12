"""Regression tests for the NativeQt stock-advisor table rendering and market.db loader."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch
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


class TestStockAdvisorPageDeferral(unittest.TestCase):
    """Tests for Stock Advisor page deferral & signature caching optimization."""

    def test_refresh_stock_advisor_page_skips_render_when_hidden_and_not_forced(self) -> None:
        import oak_qt_shell
        from unittest.mock import MagicMock, patch

        shell = MagicMock()
        shell.stock_result_table = MagicMock()
        shell.current_tab = "Profiles"
        shell._render_advisory_table = MagicMock()
        shell._reload_stock_rows = MagicMock()
        shell._check_auto_eod_update = MagicMock()

        # Call without force when hidden: skips rendering
        oak_qt_shell.NativeShell._refresh_stock_advisor_page(shell, force=False)
        shell._render_advisory_table.assert_not_called()
        shell._reload_stock_rows.assert_not_called()

        # Call with force=True when hidden: executes rendering
        oak_qt_shell.NativeShell._refresh_stock_advisor_page(shell, force=True)
        shell._render_advisory_table.assert_called_once()
        shell._reload_stock_rows.assert_called_once()

    def test_switch_tab_forces_stock_advisor_refresh_when_activating(self) -> None:
        import oak_qt_shell
        from unittest.mock import MagicMock

        shell = MagicMock()
        shell.tab_pages = {"VN30 Advisor": MagicMock(), "Stock Advisor": MagicMock(), "Profiles": MagicMock()}
        shell.stack = MagicMock()
        shell._refresh_nav = MagicMock()
        shell._fade_in_page = MagicMock()
        shell._refresh_stock_advisor_page = MagicMock()

        # Switch to VN30 Advisor forces refresh
        oak_qt_shell.NativeShell.switch_tab(shell, "VN30 Advisor")
        self.assertEqual(shell.current_tab, "VN30 Advisor")
        shell._refresh_stock_advisor_page.assert_called_once_with(force=True)

    def test_signature_caching_skips_repeated_activation_and_invalidates_on_data_change(self) -> None:
        import oak_qt_shell
        from unittest.mock import MagicMock

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "data" / "market.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_path.write_bytes(b"initial db")

            rec_path = tmp_path / "stock_recommendation.json"
            rec_path.write_text('{"recommendations": []}', encoding="utf-8")

            shell = MagicMock()
            shell.selected = "Demo"
            shell.current_tab = "Stock Advisor"
            shell.stock_result_table = MagicMock()
            shell.stock_search = MagicMock()
            shell.stock_search.text.return_value = ""
            shell._last_stock_advisor_signature = None
            shell._render_advisory_table = MagicMock()
            shell._reload_stock_rows = MagicMock()
            shell._check_auto_eod_update = MagicMock()
            shell._stock_advisor_signature = lambda: oak_qt_shell.NativeShell._stock_advisor_signature(shell)

            with patch.object(oak_qt_shell, "ROOT", tmp_path):
                # Call 1: renders and saves signature
                oak_qt_shell.NativeShell._refresh_stock_advisor_page(shell, force=False)
                self.assertIsNotNone(shell._last_stock_advisor_signature)
                self.assertEqual(shell._render_advisory_table.call_count, 1)

                # Call 2: unchanged signature, force=False -> skips render
                oak_qt_shell.NativeShell._refresh_stock_advisor_page(shell, force=False)
                self.assertEqual(shell._render_advisory_table.call_count, 1)

                # Data change: update db file on disk -> invalidates signature -> re-renders
                db_path.write_bytes(b"updated db content")
                oak_qt_shell.NativeShell._refresh_stock_advisor_page(shell, force=False)
                self.assertEqual(shell._render_advisory_table.call_count, 2)

                # Explicit force=True -> re-renders regardless of signature
                oak_qt_shell.NativeShell._refresh_stock_advisor_page(shell, force=True)
                self.assertEqual(shell._render_advisory_table.call_count, 3)


if __name__ == "__main__":
    unittest.main()
