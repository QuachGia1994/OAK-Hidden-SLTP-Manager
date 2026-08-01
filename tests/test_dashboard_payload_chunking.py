"""Test G: split_records_by_encoded_size — batching correctness."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()


class TestDashboardPayloadChunking(unittest.TestCase):
    def _make_record(self, idx, size_kb=5):
        """Create a record approximately size_kb kilobytes."""
        return {
            "date": "2026-07-31",
            "hour": idx % 6 + 3,
            "signal": "SELL",
            "logic_version": 84,
            "pair_dirs": {"XAUUSD": "SELL", "GBPUSD": "SELL"},
            "_padding": "x" * (size_kb * 1024),
        }

    def test_no_batch_exceeds_350kb(self):
        import mt5_signal_bot as bot
        records = [self._make_record(i, size_kb=10) for i in range(50)]
        MAX_BYTES = 350 * 1024
        for batch in bot.split_records_by_encoded_size(records, max_records=20, max_bytes=MAX_BYTES):
            batch_size = len(json.dumps(batch, default=str).encode("utf-8"))
            self.assertLessEqual(
                batch_size, MAX_BYTES,
                f"Batch size {batch_size} exceeds {MAX_BYTES}"
            )

    def test_no_batch_exceeds_max_records(self):
        import mt5_signal_bot as bot
        records = [{"idx": i} for i in range(100)]
        for batch in bot.split_records_by_encoded_size(records, max_records=20, max_bytes=350 * 1024):
            self.assertLessEqual(len(batch), 20)

    def test_all_records_covered(self):
        """All records must appear in exactly one batch."""
        import mt5_signal_bot as bot
        records = [{"idx": i} for i in range(194)]
        all_delivered = []
        for batch in bot.split_records_by_encoded_size(records, max_records=20, max_bytes=350 * 1024):
            all_delivered.extend(batch)
        self.assertEqual(len(all_delivered), len(records))
        self.assertEqual([r["idx"] for r in all_delivered], list(range(194)))

    def test_empty_records_gives_no_batches(self):
        import mt5_signal_bot as bot
        batches = list(bot.split_records_by_encoded_size([], max_records=20, max_bytes=350 * 1024))
        self.assertEqual(batches, [])

    def test_single_oversized_record_is_yielded_alone(self):
        """A record exceeding max_bytes must still be yielded (not silently dropped)."""
        import mt5_signal_bot as bot
        huge = {"data": "x" * (400 * 1024)}
        batches = list(bot.split_records_by_encoded_size([huge], max_records=20, max_bytes=350 * 1024))
        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0]), 1)

    def test_complete_snapshot_clears_only_the_first_history_batch(self):
        import mt5_signal_bot as bot

        records = [
            {
                "date": "2026-07-31",
                "hour": (3, 7, 9, 12, 14, 16)[index % 6],
                "signal": "SELL",
                "logic_version": 87,
                "pair_dirs": {"XAUUSD": "SELL"},
            }
            for index in range(21)
        ]
        payloads = []

        class FakeResponse:
            status = 200

            def read(self):
                return b'{"ok":true}'

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

        def fake_urlopen(request, timeout=15):
            if request.full_url.endswith("/api/signals/history/batch"):
                payloads.append(json.loads(request.data.decode("utf-8")))
            return FakeResponse()

        with tempfile.TemporaryDirectory() as temp_dir:
            signal_log = Path(temp_dir) / "signals_log.json"
            signal_log.write_text(json.dumps(records), encoding="utf-8")
            with (
                patch.object(bot, "_SIGNALS_LOG", str(signal_log)),
                patch.object(bot, "DASHBOARD_URL", "http://fake"),
                patch.object(bot, "push_state_to_dashboard", return_value=False),
                patch.object(bot, "_latest_today_news_cache", return_value=None),
                patch("urllib.request.urlopen", fake_urlopen),
            ):
                bot.push_to_dashboard(snapshot_complete=True)

        self.assertEqual([payload["clear_all"] for payload in payloads], [True, False])


if __name__ == "__main__":
    unittest.main()
