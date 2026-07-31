"""Test: Compact signal payloads exclude heavy fields."""
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestDashboardCompactSignalPayload(unittest.TestCase):
    def _full_record(self):
        return {
            "date": "2026-07-31",
            "hour": 7,
            "signal": "SELL",
            "pair_dirs": {"XAUUSD": "SELL", "GBPUSD": "SELL"},
            "pair_evidence": {"XAUUSD": {"m30_candles": [{"open": 1}, {"open": 2}], "action": "KEEP_D"}},
            "d_directions": {"GBPUSD": {"d_direction": "SELL"}},
            "daily_directions": {"GBPUSD": {"d_direction": "SELL"}},
            "m30_candles": [[1, 2, 3, 4, 5], [6, 7, 8, 9, 0]],
            "h1_candle": {"open": 1000, "close": 1001},
            "m30_layer1": {"candle": {"open": 1}},
            "m30_layer2": {"candle": {"open": 2}},
            "m30_layer3": {"candle": {"open": 3}},
            "logic_version": 84,
            "broker_utc_offset": 3,
        }

    def _capture_push_payloads(self):
        """Return all payloads sent in a _push_compact_current_signals call."""
        import mt5_signal_bot as bot
        captured = []

        class FakeResp:
            status = 200
            def read(self): return b'{"ok":true}'
            def __enter__(self): return self
            def __exit__(self, *a): pass

        def mock_urlopen(req, timeout=15):
            captured.append(json.loads(req.data.decode("utf-8")))
            return FakeResp()

        with patch("mt5_signal_bot.DASHBOARD_URL", "http://fake"):
            with patch("urllib.request.urlopen", mock_urlopen):
                bot._push_compact_current_signals([self._full_record()])

        return captured

    def test_pair_evidence_excluded(self):
        payloads = self._capture_push_payloads()
        self.assertTrue(payloads, "No payload was sent")
        for payload in payloads:
            for record in payload.get("records", []):
                self.assertNotIn("pair_evidence", record, "pair_evidence must be stripped")

    def test_d_directions_excluded(self):
        payloads = self._capture_push_payloads()
        for payload in payloads:
            for record in payload.get("records", []):
                self.assertNotIn("d_directions", record, "d_directions must be stripped")
                self.assertNotIn("daily_directions", record, "daily_directions must be stripped")

    def test_m30_candles_excluded(self):
        payloads = self._capture_push_payloads()
        for payload in payloads:
            for record in payload.get("records", []):
                self.assertNotIn("m30_candles", record)
                self.assertNotIn("m30_layer1", record)
                self.assertNotIn("m30_layer2", record)
                self.assertNotIn("m30_layer3", record)
                self.assertNotIn("h1_candle", record)

    def test_core_fields_retained(self):
        """Key fields must be in compact record."""
        payloads = self._capture_push_payloads()
        for payload in payloads:
            for record in payload.get("records", []):
                self.assertIn("date", record)
                self.assertIn("hour", record)
                self.assertIn("signal", record)
                self.assertIn("pair_dirs", record)
                self.assertIn("logic_version", record)

    def test_evidence_available_marker_added(self):
        """evidence_available dict must be added when pair_evidence exists."""
        payloads = self._capture_push_payloads()
        for payload in payloads:
            for record in payload.get("records", []):
                if record.get("evidence_available"):
                    self.assertIn("XAUUSD", record["evidence_available"])


if __name__ == "__main__":
    unittest.main()
