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

    def test_skip_path_repushes_already_ready_snapshot(self):
        """Fix: when D is already published locally (READY), publish_d_direction_daily
        still re-pushes the snapshot to the dashboard so a cleared Redis is refilled."""
        import mt5_signal_bot as bot

        target_date = "2026-07-31"
        sample = dict(self._sample_snapshot())
        sample["target_local_date"] = target_date
        # state READY + acknowledged metadata so the skip gate matches
        sample["symbols"]["GBPJPY"] = {"d_state": "READY", "d_direction": "SELL"}
        sample["symbols"]["GBPCAD"] = {"d_state": "READY", "d_direction": "SELL"}
        sample["symbols"]["XAUUSD"] = {"d_state": "READY", "d_direction": "BUY"}

        metadata = {
            "schema_version": bot.D_PUBLICATION_STATE_SCHEMA_VERSION,
            "logic_version": bot.SIGNAL_LOGIC_VERSION,
            "d_schema_version": bot.D_DIRECTION_SCHEMA_VERSION,
            "snapshot_state": "READY",
            "dashboard_acknowledged": True,
            "active_source_states": {},
        }

        resp = _make_http_response(200, {"ok": True, "target_local_date": target_date})

        # Mock the local history store to contain the READY snapshot and the
        # state file to mark it as acknowledged.
        with patch("mt5_signal_bot._load_d_direction_history_records", return_value={target_date: sample}):
            with patch("mt5_signal_bot._load_state", return_value={"d_publication_state": {target_date: metadata}}):
                with patch("mt5_signal_bot.validate_local_ready_snapshot", return_value=True):
                    with patch("mt5_signal_bot.is_d_publication_complete", return_value=True):
                        with patch("mt5_signal_bot.DASHBOARD_URL", "http://fake"):
                            with patch("urllib.request.urlopen", return_value=resp) as mock_urlopen:
                                result = bot.publish_d_direction_daily(target_date)

        # The skip path must still have called push_d_direction_snapshot (urlopen)
        self.assertEqual(mock_urlopen.call_count, 1)
        self.assertEqual(result["target_local_date"], target_date)


if __name__ == "__main__":
    unittest.main()
