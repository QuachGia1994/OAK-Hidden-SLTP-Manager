"""Test G: split_records_by_encoded_size — batching correctness."""
import json
import os
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
