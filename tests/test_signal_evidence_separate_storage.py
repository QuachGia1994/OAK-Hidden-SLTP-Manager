"""Test: Evidence is tracked separately with evidence_available markers."""
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSignalEvidenceSeparateStorage(unittest.TestCase):
    def _make_full_record_with_evidence(self):
        return {
            "date": "2026-07-31",
            "hour": 7,
            "signal": "SELL",
            "pair_dirs": {"XAUUSD": "SELL", "GBPUSD": "SELL"},
            "pair_evidence": {
                "XAUUSD": {"m30_candles": [1, 2, 3], "action": "KEEP_D"},
                "GBPUSD": {"m30_candles": [4, 5, 6], "action": "KEEP_D"},
                "GBPAUD": {"m30_candles": [7, 8, 9], "action": "KEEP_D"},
            },
            "logic_version": 84,
        }

    def _capture_compact_records(self, full_record):
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
                bot._push_compact_current_signals([full_record])

        return captured

    def test_evidence_available_keys_set_when_evidence_present(self):
        """evidence_available must be set for all evidence-bearing pairs."""
        records = self._capture_compact_records(self._make_full_record_with_evidence())
        self.assertTrue(records)
        for payload in records:
            for record in payload.get("records", []):
                ev_avail = record.get("evidence_available", {})
                self.assertIn("XAUUSD", ev_avail)
                self.assertIn("GBPUSD", ev_avail)
                self.assertIn("GBPAUD", ev_avail)
                self.assertTrue(ev_avail["XAUUSD"])
                self.assertTrue(ev_avail["GBPUSD"])
                self.assertTrue(ev_avail["GBPAUD"])

    def test_evidence_keys_contain_version(self):
        """evidence_keys must contain logic_version for idempotent fetching."""
        records = self._capture_compact_records(self._make_full_record_with_evidence())
        for payload in records:
            for record in payload.get("records", []):
                ev_keys = record.get("evidence_keys", {})
                if ev_keys:
                    for sym, key in ev_keys.items():
                        self.assertIn("v84", key, f"Key {key!r} missing version for {sym}")

    def test_pair_evidence_not_in_compact_record(self):
        """pair_evidence raw data must not appear in compact summary."""
        records = self._capture_compact_records(self._make_full_record_with_evidence())
        for payload in records:
            for record in payload.get("records", []):
                self.assertNotIn("pair_evidence", record)

    def test_no_evidence_available_when_no_evidence(self):
        """Records without pair_evidence must not have spurious evidence_available."""
        record = {
            "date": "2026-07-31",
            "hour": 7,
            "signal": "SELL",
            "pair_dirs": {"XAUUSD": "SELL"},
            "logic_version": 84,
        }
        captured = self._capture_compact_records(record)
        for payload in captured:
            for rec in payload.get("records", []):
                ev_avail = rec.get("evidence_available", {})
                self.assertEqual(ev_avail, {})


if __name__ == "__main__":
    unittest.main()
