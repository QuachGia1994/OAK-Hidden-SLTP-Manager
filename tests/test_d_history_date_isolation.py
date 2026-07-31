import unittest
from datetime import date
from unittest.mock import patch, MagicMock
from mt5_signal_bot import build_d_direction_snapshot_for_date, MT4FeedProvider

class TestDHistoryDateIsolation(unittest.TestCase):
    @patch("mt5_signal_bot.calculate_all_d_directions")
    def test_history_snapshots_have_isolated_dates_and_objects(self, mock_calc):
        def fake_calc(target_broker_date):
            session = f"2026-07-{target_broker_date.day - 1:02d}"
            return {
                "GBPUSD": {
                    "d_state": "READY",
                    "d_direction": "SELL" if target_broker_date.day % 2 == 0 else "BUY",
                    "candle": {"open": "1.3400", "high": "1.3500", "low": "1.3300", "close": "1.3450"},
                    "session_date": session,
                    "source_symbol": "GBPUSD",
                }
            }

        mock_calc.side_effect = fake_calc
        provider = MT4FeedProvider()
        mock_clock = MagicMock()
        mock_clock.utc_offset_for_date.return_value = 3
        mock_clock.broker_from_utc_datetime.side_effect = lambda dt: dt + timedelta(hours=3)

        snap_31 = build_d_direction_snapshot_for_date(date(2026, 7, 31), provider, mock_clock)
        snap_30 = build_d_direction_snapshot_for_date(date(2026, 7, 30), provider, mock_clock)

        self.assertIsNot(snap_31, snap_30)
        self.assertNotEqual(snap_31["target_local_date"], snap_30["target_local_date"])

        # Mutate snap_31 and assert snap_30 is untouched
        snap_31["symbols"]["GBPUSD"]["candle"]["open"] = "0.0000"
        self.assertEqual(snap_30["symbols"]["GBPUSD"]["candle"]["open"], "1.3400")

if __name__ == "__main__":
    unittest.main()
