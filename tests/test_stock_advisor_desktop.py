"""Desktop orchestration contracts for the one-click VN30 advisor."""
from datetime import date
from pathlib import Path
import unittest
from unittest.mock import patch

from oak_qt_shell import run_embedded_worker

from services.stock_advisor_desktop import (
    StockAdvisorDesktopSettings,
    build_stock_advisor_launch_plan,
    render_stock_advisory,
    requires_h4_backfill,
)


class StockAdvisorDesktopTests(unittest.TestCase):
    def test_first_run_requires_backfill_and_current_history_does_not(self) -> None:
        today = date(2026, 7, 17)
        current = [
            {
                "date": f"2026-06-{index:02d}",
                "hour": 4,
                "logic_version": 64,
                "pair_dirs": {"XAUUSD": "BUY"},
            }
            for index in range(1, 27)
        ]
        current.append({
            "date": today.isoformat(),
            "hour": 4,
            "logic_version": 64,
            "pair_dirs": {"XAUUSD": "SELL"},
        })

        self.assertTrue(requires_h4_backfill([], today))
        self.assertFalse(requires_h4_backfill(current, today))

    def test_launch_plan_is_one_click_and_never_contains_credentials(self) -> None:
        settings = StockAdvisorDesktopSettings(capital=90_000_000, hurdle_bps=5)
        plan = build_stock_advisor_launch_plan(
            Path("C:/OAK"),
            executable="python.exe",
            frozen=False,
            settings=settings,
            requires_backfill=True,
        )

        self.assertEqual(plan.program, "python.exe")
        self.assertIn("C:\\OAK\\vn_stock_advisor.py", plan.arguments[0])
        self.assertIn("--backfill-h4", plan.arguments)
        self.assertTrue(plan.requires_signal_pause)
        self.assertNotIn("secret", " ".join(plan.arguments).lower())

    def test_frozen_plan_reuses_the_desktop_executable(self) -> None:
        plan = build_stock_advisor_launch_plan(
            Path("C:/OAK"),
            executable="OAK.exe",
            frozen=True,
            settings=StockAdvisorDesktopSettings(),
            requires_backfill=False,
        )

        self.assertEqual(plan.arguments[0], "--stock-advisor")
        self.assertFalse(plan.requires_signal_pause)

    def test_result_renderer_preserves_confirmation_gate(self) -> None:
        payload = {
            "status": "READY",
            "action": "SELL_OR_AVOID",
            "signal": {"date": "2026-07-17", "direction": "SELL"},
            "candidates": [{"rank": 1, "symbol": "AAA", "weight": 1 / 3, "conditional_hit_rate": 0.76}],
            "requires_user_confirmation": True,
            "orders_submitted": False,
        }

        rendered = render_stock_advisory(payload, locale="EN")
        rendered_vn = render_stock_advisory(payload, locale="VN")

        self.assertIn("AAA", rendered)
        self.assertIn("SELL / AVOID", rendered)
        self.assertIn("USER CONFIRMATION REQUIRED", rendered)
        self.assertIn("NO ORDER SUBMITTED", rendered)

        self.assertIn("AAA", rendered_vn)
        self.assertIn("BÁN / ĐỨNG NGOÀI (SELL / AVOID)", rendered_vn)
        self.assertIn("⚠️ YÊU CẦU USER XÁC NHẬN TRƯỚC KHI GIAO DỊCH THỰC TẾ", rendered_vn)

    def test_frozen_worker_forwards_advisor_arguments_and_exit_code(self) -> None:
        with patch("vn_stock_advisor.main", return_value=2) as advisor_main:
            exit_code = run_embedded_worker(["OAK.exe", "--stock-advisor", "--capital", "1"])

        self.assertEqual(exit_code, 2)
        advisor_main.assert_called_once_with(["--capital", "1"])


if __name__ == "__main__":
    unittest.main()
