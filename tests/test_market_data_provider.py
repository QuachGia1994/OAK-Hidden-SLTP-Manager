import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "robot-sltp-pro"
sys.path.insert(0, str(APP))

from market_data_parity import compare_provider_range, require_parity
from market_data_provider import Candle, SnapshotMarketDataProvider
from pattern5_engine import look4


class MarketDataProviderTests(unittest.TestCase):
    def setUp(self):
        self.candles = [
            Candle(100, 1.00, 1.20, 0.90, 1.10),
            Candle(200, 1.10, 1.20, 1.00, 1.00),
            Candle(300, 1.00, 1.30, 0.90, 1.20),
            Candle(400, 1.20, 1.30, 1.00, 1.10),
        ]

    def _provider(self, provider_id="snapshot", candles=None, offset=0):
        return SnapshotMarketDataProvider(
            provider_id,
            {"EURUSD": candles or self.candles},
            {"EURUSD": offset},
        )

    def test_snapshot_round_trip_preserves_candles_and_offset(self):
        original = self._provider("ic-ctrader")
        restored = SnapshotMarketDataProvider.from_payload(original.as_payload())
        self.assertEqual(restored.provider_id, "ic-ctrader")
        self.assertEqual(restored.broker_day_offset("EURUSD"), 0)
        self.assertEqual(list(restored.h4_range("EURUSD", 100, 400)), self.candles)

    def test_pattern5_look4_runs_without_mt5_when_provider_supplied(self):
        directions, evidence = look4("EURUSD", 500, provider=self._provider())
        self.assertEqual(directions, ["G", "T", "G", "T"])
        self.assertEqual([row["time"] for row in evidence], [100, 200, 300, 400])

    def test_parity_passes_for_same_broker_candles(self):
        baseline = self._provider("ic-mt5")
        candidate = self._provider("ic-ctrader")
        report = compare_provider_range(baseline, candidate, "EURUSD", 100, 400)
        self.assertTrue(report.ok)
        self.assertEqual(report.matched, 4)
        require_parity(report)

    def test_parity_fails_closed_on_candle_boundary_shift(self):
        shifted = [
            Candle(row.time + 3600, row.open, row.high, row.low, row.close)
            for row in self.candles
        ]
        report = compare_provider_range(
            self._provider("vantage-mt5"),
            self._provider("generic-cloud", candles=shifted),
            "EURUSD",
            100,
            4000,
        )
        self.assertFalse(report.ok)
        self.assertTrue(any(issue.kind == "missing_candidate" for issue in report.issues))
        with self.assertRaises(RuntimeError):
            require_parity(report)

    def test_parity_fails_closed_on_broker_day_offset_mismatch(self):
        report = compare_provider_range(
            self._provider("ic-mt5", offset=0),
            self._provider("ic-cloud", offset=7200),
            "EURUSD",
            100,
            400,
        )
        self.assertFalse(report.ok)
        self.assertEqual(report.issues[0].kind, "day_offset_mismatch")


if __name__ == "__main__":
    unittest.main()
