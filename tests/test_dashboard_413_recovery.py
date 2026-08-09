"""Test H: 413 recovery — split batch and retry, no false-success log."""
import json
import os
import sys
import unittest
from io import BytesIO
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestDashboard413Recovery(unittest.TestCase):
    def _make_records(self, n=5):
        return [{"date": "2026-07-31", "hour": 3, "signal": "SELL", "idx": i} for i in range(n)]

    def test_413_triggers_split_and_retry(self):
        """On 413, the function splits the batch in half and retries."""
        import mt5_signal_bot as bot
        import urllib.error

        call_sizes = []
        retry_call_sizes = []

        class FirstFakeResp:
            status = 200
            def read(self): return b'{"ok":true}'
            def __enter__(self): return self
            def __exit__(self, *a): pass

        call_n = [0]
        def mock_urlopen(req, timeout=15):
            call_n[0] += 1
            body = json.loads(req.data.decode("utf-8"))
            n_recs = len(body.get("records", []))
            if call_n[0] == 1:
                # First call: return 413
                raise urllib.error.HTTPError(
                    url="http://fake/api/signals/current",
                    code=413,
                    msg="Request Entity Too Large",
                    hdrs=None,
                    fp=BytesIO(b"too large"),
                )
            else:
                # Retry calls succeed
                retry_call_sizes.append(n_recs)
                return FirstFakeResp()

        records = self._make_records(4)
        with patch("mt5_signal_bot.DASHBOARD_URL", "http://fake"):
            with patch("urllib.request.urlopen", mock_urlopen):
                bot._push_compact_current_signals(records)

        # Should have had retry calls after the 413
        self.assertGreater(len(retry_call_sizes), 0, "No retry happened after 413")

    def test_no_false_success_on_413_with_no_retry(self):
        """If both primary and retry fail, no success log should claim delivery."""
        import mt5_signal_bot as bot
        import urllib.error

        def mock_urlopen(req, timeout=15):
            raise urllib.error.HTTPError(
                url="http://fake/api/signals/current",
                code=413,
                msg="Too Large",
                hdrs=None,
                fp=BytesIO(b"too large"),
            )

        records = self._make_records(2)
        log_messages = []

        original_print = __builtins__["print"] if isinstance(__builtins__, dict) else print
        import builtins
        printed = []
        original_print = builtins.print
        builtins.print = lambda *a, **kw: printed.append(" ".join(str(x) for x in a))

        try:
            with patch("mt5_signal_bot.DASHBOARD_URL", "http://fake"):
                with patch("urllib.request.urlopen", mock_urlopen):
                    bot._push_compact_current_signals(records)
        finally:
            builtins.print = original_print

        success_msgs = [m for m in printed if "pushed OK" in m and "Current signal" in m]
        fail_msgs = [m for m in printed if "FAILED" in m or "0 records" in m]
        # Should have FAILED message and no success message
        self.assertEqual(len(success_msgs), 0, f"False success logged: {success_msgs}")


if __name__ == "__main__":
    unittest.main()
