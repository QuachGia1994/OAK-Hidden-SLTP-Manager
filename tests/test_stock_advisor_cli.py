"""Safety tests for the recommendation-only stock advisor CLI."""
from datetime import date
from contextlib import redirect_stderr
from io import StringIO
import inspect
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from domain.stock_scanner import (
    AdvisoryBacktest,
    Direction,
    H4Signal,
    StockScannerError,
    StockScannerErrorCode,
    StockScore,
    select_top_stocks,
)
import vn_stock_advisor
import services.ssi_market_data as ssi_market_data
from vn_stock_advisor import build_advisory_payload


class StockAdvisorSafetyTests(unittest.TestCase):
    def test_payload_requires_user_confirmation_and_reports_no_orders(self) -> None:
        score = StockScore("AAA", 25, 12, 0.8, 0.75, 0.01, 0.012, 0.01, 0.5, True)
        selection = select_top_stocks([score], Direction.BUY, capital=30_000_000)
        backtest = AdvisoryBacktest(250, 210, 0.7, 0.004, False)

        payload = build_advisory_payload(
            selection,
            H4Signal(date(2026, 7, 17), Direction.BUY),
            backtest,
            rejected_count=29,
            data_errors=(),
        )

        self.assertTrue(payload["advisory_only"])
        self.assertTrue(payload["requires_user_confirmation"])
        self.assertFalse(payload["orders_submitted"])
        self.assertEqual(payload["candidates"][0]["weight"], 1 / 3)
        self.assertEqual(payload["warnings"], [])

    def test_cli_has_no_order_submission_surface(self) -> None:
        source = inspect.getsource(vn_stock_advisor) + inspect.getsource(ssi_market_data)
        self.assertNotIn("place_order", source)
        self.assertNotIn("Trading(", source)
        self.assertNotIn("otp=", source)

    def test_cli_reports_scanner_validation_without_a_traceback(self) -> None:
        error = StockScannerError(StockScannerErrorCode.INVALID_CAPITAL, "invalid capital")
        with patch.object(vn_stock_advisor, "run_advisor", side_effect=error):
            with patch.object(sys, "argv", ["vn_stock_advisor.py"]):
                with redirect_stderr(StringIO()) as stderr:
                    exit_code = vn_stock_advisor.main()

        self.assertEqual(exit_code, 2)
        self.assertEqual(stderr.getvalue().strip(), "[ERROR] invalid capital")

    def test_cli_publishes_the_same_safe_payload_to_dashboard(self) -> None:
        payload = {"advisory_only": True, "orders_submitted": False}
        push_result = type("Push", (), {"pushed": True, "status": "pushed"})()
        with patch.object(vn_stock_advisor, "run_advisor", return_value=payload):
            with patch.object(vn_stock_advisor, "_write_payload"):
                with patch.object(vn_stock_advisor, "load_dashboard_publisher_config") as config:
                    with patch.object(vn_stock_advisor, "publish_stock_advisory", return_value=push_result) as publish:
                        exit_code = vn_stock_advisor.main([])

        self.assertEqual(exit_code, 0)
        publish.assert_called_once_with(payload, config.return_value)

    def test_backfill_targets_the_requested_signal_log(self) -> None:
        import mt5_signal_bot

        target = Path("C:/OAK/signals_log.json").resolve()
        observed = []

        def rebuild(days: int) -> int:
            observed.append((days, Path(mt5_signal_bot._SIGNALS_LOG)))
            return 1

        with patch.object(mt5_signal_bot, "mt5_ready", True):
            with patch.object(mt5_signal_bot, "_SIGNALS_LOG", "original"):
                with patch.object(mt5_signal_bot, "rebuild_recent_history", side_effect=rebuild):
                    vn_stock_advisor._backfill_h4(1, target)

        self.assertEqual(observed, [(1, target)])


if __name__ == "__main__":
    unittest.main()
