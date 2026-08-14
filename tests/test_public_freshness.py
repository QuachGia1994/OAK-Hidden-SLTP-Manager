# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
import unittest

from services.public_freshness import (
    FRESHNESS_DEGRADED_SECONDS,
    FRESHNESS_LIVE_SECONDS,
    FRESHNESS_STALE_SECONDS,
    STATUS_DEGRADED,
    STATUS_LIVE,
    STATUS_STALE,
    STATUS_UNAVAILABLE,
    build_freshness_envelope,
    classify_freshness,
)


class TestPublicFreshness(unittest.TestCase):
    def test_thresholds_are_constants(self):
        self.assertEqual(FRESHNESS_LIVE_SECONDS, 30)
        self.assertEqual(FRESHNESS_DEGRADED_SECONDS, 120)
        self.assertEqual(FRESHNESS_STALE_SECONDS, 600)

    def test_missing_observation_is_unavailable(self):
        meta = classify_freshness(None)
        self.assertEqual(meta["source_status"], STATUS_UNAVAILABLE)
        self.assertIsNone(meta["data_age_seconds"])

    def test_live_window(self):
        now = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)
        obs = now - timedelta(seconds=10)
        meta = classify_freshness(obs, now_utc=now)
        self.assertEqual(meta["source_status"], STATUS_LIVE)
        self.assertEqual(meta["data_age_seconds"], 10)

    def test_degraded_window(self):
        now = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)
        obs = now - timedelta(seconds=60)
        meta = classify_freshness(obs, now_utc=now)
        self.assertEqual(meta["source_status"], STATUS_DEGRADED)

    def test_stale_window(self):
        now = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)
        obs = now - timedelta(seconds=300)
        meta = classify_freshness(obs, now_utc=now)
        self.assertEqual(meta["source_status"], STATUS_STALE)

    def test_envelope_preserves_observed_not_now(self):
        now = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)
        obs = now - timedelta(seconds=90)
        env = build_freshness_envelope(
            observed_at_utc=obs,
            published_at_utc=now,
            source="MT5_LIVE",
            now_utc=now,
        )
        self.assertEqual(env["source"], "MT5_LIVE")
        self.assertEqual(env["source_status"], STATUS_DEGRADED)
        self.assertIn("2026-08-14T11:58:30", env["observed_at_utc"])
        self.assertNotEqual(env["observed_at_utc"], env["published_at_utc"])


if __name__ == "__main__":
    unittest.main()
