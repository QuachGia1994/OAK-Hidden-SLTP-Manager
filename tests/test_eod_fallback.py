"""Regression tests for the EOD collector fallback-to-latest-session feature."""
from __future__ import annotations

import unittest
from datetime import date
from unittest import mock

from eod_collector.services.collector import CollectorService
from eod_collector.validator import ValidationError


def _make_service() -> CollectorService:
    """Build a CollectorService with a fake config that avoids disk/network."""
    config = mock.MagicMock()
    config.collector.holidays = ["2026-01-01"]
    config.database.path = "data/market.db"
    svc = CollectorService.__new__(CollectorService)
    svc.config = config
    svc.repository = mock.MagicMock()
    return svc


class TestEODFallback(unittest.TestCase):
    """Test that update() walks back to the most recent session with data."""

    def test_fallback_to_previous_weekday(self) -> None:
        """When target_date has no data but the previous weekday does,
        update() returns that previous weekday's counts."""
        svc = _make_service()
        target = date(2026, 8, 7)  # Friday

        with mock.patch.object(
            svc,
            "_collect_via_vps",
            side_effect=[
                ValidationError("VPS returned no data for 2026-08-07"),
                {"HOSE": 614},
            ],
        ) as mock_vps:
            result = svc.update(trading_date=target)

        self.assertEqual(result, {"HOSE": 614})
        # Verify _collect_via_vps was called with the previous weekday (2026-08-06)
        self.assertEqual(mock_vps.call_count, 2)
        second_call_date = mock_vps.call_args_list[1][0][0]
        self.assertEqual(second_call_date, date(2026, 8, 6))

    def test_weekend_returns_empty(self) -> None:
        """Weekend target_date is skipped by update() and returns {}."""
        svc = _make_service()
        saturday = date(2026, 8, 8)  # Saturday
        result = svc.update(trading_date=saturday)
        self.assertEqual(result, {})

    def test_no_data_in_7_days_raises(self) -> None:
        """When no candidate in 7 days yields data, update() raises
        ValidationError whose message mentions the walk-back range."""
        svc = _make_service()
        # Friday 2026-08-07 — all 8 candidates (Fri→Fri) raise
        target = date(2026, 8, 7)
        with mock.patch.object(
            svc,
            "_collect_via_vps",
            side_effect=ValidationError("VPS returned no data for any session"),
        ):
            with self.assertRaises(ValidationError) as ctx:
                svc.update(trading_date=target)
            self.assertIn("back 7 days", str(ctx.exception))

    def test_cli_update_success_returns_zero(self) -> None:
        """CLI 'update' command returns exit code 0 on success."""
        from eod_collector import cli

        with mock.patch("eod_collector.cli.CollectorService") as MockSvc:
            instance = MockSvc.return_value
            instance.update.return_value = {"HOSE": 1}
            result = cli.main(["update"])
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
