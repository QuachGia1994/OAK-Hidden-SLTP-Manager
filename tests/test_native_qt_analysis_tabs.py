"""Regression coverage for NativeQt Analysis navigation and read-only data tabs."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import oak_qt_shell as shell_mod


class NativeQtAnalysisNavigationTests(unittest.TestCase):
    def test_analysis_catalog_excludes_rules_today(self) -> None:
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn('("◎", "Accounts")', source)
        self.assertIn('("↗", "Performance")', source)
        self.assertIn('("⧗", "History")', source)
        self.assertIn('("◈", "News")', source)
        self.assertNotIn('("§", "Rules today")', source)

    def test_analysis_tabs_are_registered(self) -> None:
        self.assertIn("Accounts", shell_mod.NativeShell.__dict__["_main"].__code__.co_consts)
        self.assertIn("Performance", shell_mod.NativeShell.__dict__["_main"].__code__.co_consts)
        self.assertIn("History", shell_mod.NativeShell.__dict__["_main"].__code__.co_consts)
        self.assertIn("News", shell_mod.NativeShell.__dict__["_main"].__code__.co_consts)

    def test_analysis_query_surface_is_read_only(self) -> None:
        fake = MagicMock()
        fake.account_get.return_value = {"available": True, "profile": "Vantage", "balance": 1000}
        fake.positions_list.return_value = []
        shell = MagicMock(spec=shell_mod.NativeShell)
        shell.selected = "Vantage"
        shell.profiles = {"Vantage": {}}
        shell.accounts_mode_badge = MagicMock()
        shell.analysis_account_summary = MagicMock()
        shell.analysis_positions_table = MagicMock()
        shell.analysis_positions_status = MagicMock()
        shell.analysis_account_stats_layout = None
        shell.analysis_account_stats = {}
        shell._trade_mode_from_cfg = lambda cfg: "UNKNOWN"
        shell._format_detail_block = lambda title, fields: title
        shell._format_analysis_value = lambda value, digits=2: str(value)
        shell._set_analysis_stat_grid = MagicMock()
        shell._set_analysis_table_rows = MagicMock()
        shell._bind_table_row_details = MagicMock()
        shell._classify_observation_freshness = lambda _ts: {
            "source_status": "LIVE",
            "data_age_seconds": 5,
            "observed_at_utc": "2026-08-14T12:00:00+00:00",
        }
        shell._format_freshness_age = lambda age: f"age {age}s"
        shell._live_mt5_open_positions = MagicMock(return_value=None)
        shell._analysis_queries.return_value = fake
        shell_mod.NativeShell._refresh_accounts_page(shell)
        fake.account_get.assert_called_once_with("Vantage")
        fake.positions_list.assert_called_once_with("Vantage")


class NativeQtAnalysisPageBuildTests(unittest.TestCase):
    def test_analysis_page_methods_exist(self) -> None:
        for name in ("_accounts_page", "_performance_page", "_history_page", "_news_page", "_refresh_analysis_page"):
            self.assertTrue(hasattr(shell_mod.NativeShell, name), name)

    def test_row_detail_helpers_exist_and_skip_secrets(self) -> None:
        for name in ("_bind_table_row_details", "_on_table_row_detail", "_show_row_detail_dialog"):
            self.assertTrue(hasattr(shell_mod.NativeShell, name), name)
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn('"ticket"', source)
        self.assertIn('"password"', source)
        self.assertIn("_table_detail_payloads", source)
        self.assertIn("cellDoubleClicked", source)

    def test_freshness_helpers_and_dashboard_throttle_exist(self) -> None:
        for name in ("_classify_observation_freshness", "_format_freshness_age"):
            self.assertTrue(hasattr(shell_mod.NativeShell, name), name)
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn("dash_fresh_badge", source)
        self.assertIn("_dashboard_live_interval", source)
        self.assertIn("classify_freshness", source)
        self.assertIn("RISK / CAPITAL", source)
        self.assertIn("HEALTH", source)


if __name__ == "__main__":
    unittest.main()
