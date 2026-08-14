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


class NativeQtDashboardFidelityTests(unittest.TestCase):
    """Data-fidelity contracts for Dashboard mode / risk / positions / detail."""

    def test_trade_mode_only_from_explicit_metadata(self) -> None:
        shell = MagicMock(spec=shell_mod.NativeShell)
        fn = lambda cfg: shell_mod.NativeShell._trade_mode_from_cfg(shell, cfg)
        self.assertEqual(fn({"trade_mode": "LIVE"}), "LIVE")
        self.assertEqual(fn({"account_mode": "REAL"}), "LIVE")
        self.assertEqual(fn({"trade_mode": "DEMO"}), "DEMO")
        self.assertEqual(fn({"account_mode": "PRACTICE"}), "DEMO")
        # Missing metadata → UNKNOWN
        self.assertEqual(fn({}), "UNKNOWN")
        self.assertEqual(fn(None), "UNKNOWN")
        # Misleading profile names must NEVER invent mode
        self.assertEqual(fn({"name": "VantageDemo"}), "UNKNOWN")
        self.assertEqual(fn({"profile": "ICMarkets Live"}), "UNKNOWN")
        self.assertEqual(
            fn({"name": "VantageDemo", "trade_mode": "LIVE"}), "LIVE"
        )

    def test_format_analysis_value_none_not_zero(self) -> None:
        shell = MagicMock(spec=shell_mod.NativeShell)
        out = shell_mod.NativeShell._format_analysis_value(shell, None)
        self.assertEqual(out, "—")
        self.assertNotEqual(out, "0")
        self.assertNotEqual(out, "0.00")

    def test_detail_dialog_skips_secrets_and_pending_meta(self) -> None:
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn('"password"', source)
        self.assertIn('"token"', source)
        self.assertIn('"api_key"', source)
        self.assertIn("_pending_file", source)
        # skip set is applied before rendering lines
        self.assertIn("k_lower in skip", source)
        self.assertIn('k.startswith("_")', source)

    def test_dashboard_risk_never_fabricates_current_dd(self) -> None:
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn('_set_risk("cur_dd", None', source)
        self.assertIn("unavailable", source)
        self.assertIn("Never invent 0 for missing risk fields", source)

    def test_dashboard_prefers_live_mt5_positions(self) -> None:
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn("_live_mt5_open_positions", source)
        self.assertIn('source = "LIVE_MT5"', source)
        self.assertIn("positions = live if live is not None else audit_positions", source)

    def test_positions_aggregate_null_profit_is_unavailable(self) -> None:
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn("float_ok = False", source)
        self.assertIn('agg = self._format_analysis_value(total_float) if float_ok', source)

    def test_dashboard_observability_source_and_refresh_labels(self) -> None:
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn("dash_source_badge", source)
        self.assertIn("dash_refresh_label", source)
        self.assertIn('acct_source = "AUDIT"', source)
        self.assertIn('acct_source = "UNAVAILABLE"', source)
        # Mode and freshness remain separate badges from data source.
        self.assertIn("dash_mode_badge", source)
        self.assertIn("dash_fresh_badge", source)

    def test_switch_tab_dashboard_refreshes_observability(self) -> None:
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn('elif tab == "Dashboard":', source)
        self.assertIn("self._refresh_dashboard_page()", source)

    def test_dashboard_query_failure_not_zero_positions(self) -> None:
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn("positions_known", source)
        self.assertIn("positions unavailable · source unknown", source)
        self.assertIn("audit_ok = queries is not None", source)

    def test_dashboard_refresh_exception_is_isolated(self) -> None:
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn("_refresh_dashboard_page_inner", source)
        self.assertIn("Dashboard refresh error", source)
        self.assertIn("Dashboard timer refresh error", source)

    def test_dashboard_profile_switch_clears_snapshot(self) -> None:
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn("_dashboard_clear_live_snapshot", source)
        self.assertIn("switching account", source)
        self.assertIn("_dashboard_bound_profile", source)

    def test_freshness_classification_matrix(self) -> None:
        shell = MagicMock(spec=shell_mod.NativeShell)
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        classify = lambda ts: shell_mod.NativeShell._classify_observation_freshness(shell, ts)

        # 10s age -> LIVE
        live_ts = (now - timedelta(seconds=10)).isoformat()
        self.assertEqual(classify(live_ts)["source_status"], "LIVE")

        # 60s age -> DEGRADED
        deg_ts = (now - timedelta(seconds=60)).isoformat()
        self.assertEqual(classify(deg_ts)["source_status"], "DEGRADED")

        # 300s age -> STALE
        stale_ts = (now - timedelta(seconds=300)).isoformat()
        self.assertEqual(classify(stale_ts)["source_status"], "STALE")

        # None / missing -> UNAVAILABLE
        self.assertEqual(classify(None)["source_status"], "UNAVAILABLE")
        self.assertEqual(classify("")["source_status"], "UNAVAILABLE")

    def test_detail_dialog_sensitive_patterns_filter(self) -> None:
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn("sensitive_patterns", source)
        self.assertIn("password", source)
        self.assertIn("secret", source)
        self.assertIn("token", source)
        self.assertIn("api_key", source)

    def test_account_isolation_clears_on_switch(self) -> None:
        shell = MagicMock(spec=shell_mod.NativeShell)
        shell._dashboard_clear_live_snapshot = MagicMock()
        shell._dashboard_bound_profile = "AccountA"
        shell.selected = "AccountB"
        shell.profiles = {"AccountB": {}}
        shell.dash_mode_badge = MagicMock()
        shell.dash_account_label = MagicMock()
        shell.dash_mt5_label = MagicMock()
        shell.dash_exec_label = MagicMock()
        shell.dash_fresh_badge = MagicMock()
        shell.dash_fresh_label = MagicMock()
        shell.dash_source_badge = MagicMock()
        shell.dash_refresh_label = MagicMock()
        shell.dash_risk_stats = {}
        shell.dash_equity_table = MagicMock()
        shell.dash_equity_status = MagicMock()
        shell.dash_positions_table = MagicMock()
        shell.dash_pos_status = MagicMock()
        shell.dash_pending_table = MagicMock()
        shell.dash_pending_status = MagicMock()
        shell._profile_is_running = MagicMock(return_value=False)
        shell._trade_mode_from_cfg = MagicMock(return_value="UNKNOWN")
        shell._apply_mode_badge = MagicMock()
        shell._classify_observation_freshness = MagicMock(return_value={"source_status": "UNAVAILABLE", "data_age_seconds": None})
        shell._format_freshness_age = MagicMock(return_value="age unavailable")
        shell._analysis_queries = MagicMock(return_value=MagicMock(account_get=lambda p: {}, positions_list=lambda p: [], risk_summary=lambda p: {}, equity_curve=lambda p, limit=8: []))
        shell._live_mt5_open_positions = MagicMock(return_value=None)
        shell._set_analysis_table_rows = MagicMock()
        shell._bind_table_row_details = MagicMock()
        shell._pending_state = MagicMock(return_value=([], []))

        shell_mod.NativeShell._refresh_dashboard_page_inner(shell)
        shell._dashboard_clear_live_snapshot.assert_called_once()
        self.assertEqual(shell._dashboard_bound_profile, "AccountB")

    def test_dashboard_mt5_path_resolves_path_key(self) -> None:
        """Dashboard MT5 status must use the same path keys as LIVE_MT5 / Profiles."""
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn('cfg.get("path") or cfg.get("mt5_path") or cfg.get("terminal_path")', source)

    def test_kpi_help_uses_qt_message_box(self) -> None:
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn("QT.QMessageBox.information", source)

    def test_news_table_binds_row_details(self) -> None:
        source = Path(shell_mod.__file__).read_text(encoding="utf-8")
        self.assertIn('self._bind_table_row_details(\n            self.analysis_news_table', source)


if __name__ == "__main__":
    unittest.main()
