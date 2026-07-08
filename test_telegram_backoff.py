# -*- coding: utf-8 -*-
"""Tests for compute_telegram_backoff(), the shared circuit-breaker tiering
used by mimo_bot.py's polling loop and MonitorWorker.send_telegram() to stop
spamming the log on repeated Telegram failures (e.g. HTTP 502)."""
import unittest

from utils import compute_telegram_backoff


class TestComputeTelegramBackoff(unittest.TestCase):

    def test_first_failure_is_10s_not_degraded(self):
        sleep_s, is_new_degraded = compute_telegram_backoff(1)
        self.assertEqual(sleep_s, 10)
        self.assertFalse(is_new_degraded)

    def test_second_failure_is_still_10s(self):
        sleep_s, is_new_degraded = compute_telegram_backoff(2)
        self.assertEqual(sleep_s, 10)
        self.assertFalse(is_new_degraded)

    def test_third_failure_escalates_to_60s(self):
        sleep_s, is_new_degraded = compute_telegram_backoff(3)
        self.assertEqual(sleep_s, 60)
        self.assertFalse(is_new_degraded)

    def test_ninth_failure_still_60s(self):
        sleep_s, is_new_degraded = compute_telegram_backoff(9)
        self.assertEqual(sleep_s, 60)
        self.assertFalse(is_new_degraded)

    def test_tenth_failure_enters_degraded_state_once(self):
        sleep_s, is_new_degraded = compute_telegram_backoff(10)
        self.assertEqual(sleep_s, 300)
        self.assertTrue(is_new_degraded, "10th failure must be flagged so callers log it exactly once")

    def test_eleventh_failure_stays_300s_but_not_flagged_again(self):
        """Regression: once degraded, further failures must not re-trigger the
        'entering degraded' flag, or callers would spam the log again."""
        sleep_s, is_new_degraded = compute_telegram_backoff(11)
        self.assertEqual(sleep_s, 300)
        self.assertFalse(is_new_degraded)

    def test_hundredth_failure_stays_300s_not_flagged(self):
        sleep_s, is_new_degraded = compute_telegram_backoff(100)
        self.assertEqual(sleep_s, 300)
        self.assertFalse(is_new_degraded)


if __name__ == "__main__":
    unittest.main()
