"""Tests D & E: push_d_direction_snapshot() push acknowledgement logic.

D: HTTP 500 → acknowledged=False, not marked as published
E: HTTP 200 + ok=true → acknowledged=True, DashboardPushResult.ok=True
"""
import json
import os
import sys
import unittest
from io import BytesIO
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()


def _make_http_response(status, body_dict):
    """Mock urllib response with .status and .read()."""
    class FakeResp:
        def __init__(self, status, body):
            self.status = status
            self._body = json.dumps(body).encode("utf-8")

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass
    return FakeResp(status, body_dict)


class TestDPushAcknowledgement(unittest.TestCase):
    def _sample_snapshot(self):
        return {
            "schema_version": 6,
            "logic_version": 84,
            "target_local_date": "2026-07-31",
            "target_broker_date": "2026-07-30",
            "published_at_utc": "2026-07-31T06:00:00+00:00",
            "published_at_local": "2026-07-31T13:00:00+07:00",
            "publication_timezone": "Asia/Ho_Chi_Minh",
            "publication_rule": "DAILY_AT_06_00_LOCAL",
            "broker_utc_offset": 3,
            "state": "READY",
            "symbols": {
                "GBPUSD": {"d_state": "READY", "d_direction": "SELL"},
                "GBPAUD": {"d_state": "READY", "d_direction": "SELL"},
            },
        }

    def test_http_500_gives_not_acknowledged(self):
        """Test D: HTTP 500 → ok=False, acknowledged=False."""
        import mt5_signal_bot as bot
        import urllib.error

        def mock_urlopen(req, timeout=15):
            raise urllib.error.HTTPError(
                url="http://fake/api/signals/d-direction",
                code=500,
                msg="Internal Server Error",
                hdrs=None,
                fp=BytesIO(b"error"),
            )

        with patch("mt5_signal_bot.DASHBOARD_URL", "http://fake"):
            with patch("urllib.request.urlopen", mock_urlopen):
                result = bot.push_d_direction_snapshot(self._sample_snapshot())

        self.assertIsInstance(result, bot.DashboardPushResult)
        self.assertFalse(result.ok)
        self.assertFalse(result.acknowledged)
        self.assertIsNone(result.status_code)

    def test_http_200_ok_true_gives_acknowledged(self):
        """Test E: HTTP 200 + ok=true → acknowledged=True, status_code=200."""
        import mt5_signal_bot as bot

        resp = _make_http_response(200, {"ok": True, "target_local_date": "2026-07-31"})
        with patch("mt5_signal_bot.DASHBOARD_URL", "http://fake"):
            with patch("urllib.request.urlopen", return_value=resp):
                result = bot.push_d_direction_snapshot(self._sample_snapshot())

        self.assertIsInstance(result, bot.DashboardPushResult)
        self.assertTrue(result.ok)
        self.assertTrue(result.acknowledged)
        self.assertEqual(result.status_code, 200)
        self.assertGreater(result.bytes_sent, 0)

    def test_http_200_ok_false_gives_not_acknowledged(self):
        """HTTP 200 but ok=false → acknowledged=False."""
        import mt5_signal_bot as bot

        resp = _make_http_response(200, {"ok": False, "error": "some_error"})
        with patch("mt5_signal_bot.DASHBOARD_URL", "http://fake"):
            with patch("urllib.request.urlopen", return_value=resp):
                result = bot.push_d_direction_snapshot(self._sample_snapshot())

        self.assertTrue(result.ok)  # HTTP level OK
        self.assertFalse(result.acknowledged)  # Business level not OK

    def test_no_dashboard_url_returns_not_acknowledged(self):
        """Empty DASHBOARD_URL returns DashboardPushResult with ok=False."""
        import mt5_signal_bot as bot
        with patch("mt5_signal_bot.DASHBOARD_URL", ""):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("DASHBOARD_API_URL", None)
                result = bot.push_d_direction_snapshot(self._sample_snapshot())

        self.assertIsInstance(result, bot.DashboardPushResult)
        self.assertFalse(result.ok)
        self.assertFalse(result.acknowledged)


if __name__ == "__main__":
    unittest.main()
