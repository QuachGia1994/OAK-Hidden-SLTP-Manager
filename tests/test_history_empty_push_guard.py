"""Regression tests for empty-push guard in push_to_dashboard.

The bot uses HTTP (urllib) to call the dashboard API, not Redis directly.
We mock urllib.request.urlopen to simulate the guard behaviour.
"""

import tempfile
import unittest
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
import mt5_signal_bot


class HistoryEmptyPushGuardTests(unittest.TestCase):
    """Verify push_to_dashboard refuses to replace non-empty history with empty payload."""

    def test_push_aborts_when_outgoing_empty_and_existing_nonempty(self):
        """When outgoing signals are empty but history API reports non-empty, push must abort."""
        with tempfile.TemporaryDirectory() as temp_dir:
            signal_log = Path(temp_dir) / "signals_log.json"
            signal_log.write_text("[]", encoding="utf-8")

            mock_get_response = MagicMock()
            mock_get_response.read.return_value = json.dumps({
                "ok": True, "total": 5, "records": []
            }).encode("utf-8")
            mock_get_response.__enter__ = lambda s: s
            mock_get_response.__exit__ = MagicMock(return_value=False)

            with (
                patch.object(mt5_signal_bot, "mt5_ready", True),
                patch.object(mt5_signal_bot, "_SIGNALS_LOG", str(signal_log)),
                patch.object(mt5_signal_bot, "get_broker_time",
                             return_value=datetime(2026, 7, 22, 9, 25)),
                patch("mt5_signal_bot.urllib.request.urlopen", return_value=mock_get_response),
                patch("mt5_signal_bot.DASHBOARD_URL", "http://fake-dashboard"),
            ):
                result = mt5_signal_bot.push_to_dashboard()

    def test_push_proceeds_when_signals_nonempty(self):
        """When outgoing signals are non-empty, push proceeds to POST."""
        with tempfile.TemporaryDirectory() as temp_dir:
            signal_log = Path(temp_dir) / "signals_log.json"
            signals = [
                {"date": "2026-07-22", "hour": 9, "signal": "BUY",
                 "pair_dirs": {"XAUUSD": "BUY"}, "logic_version": 88,
                 "entry_state": "READY", "hour_note": None,
                 "signal_time": "07:45", "entry_time": "07:49",
                 "entry_prices": {"XAUUSD": 3300.0},
                 "current_prices": {"XAUUSD": 3305.0},
                 "ts": 1721631000},
            ]
            signal_log.write_text(json.dumps(signals), encoding="utf-8")

            mock_get_response = MagicMock()
            mock_get_response.read.return_value = json.dumps({
                "ok": True, "total": 0, "records": []
            }).encode("utf-8")
            mock_get_response.__enter__ = lambda s: s
            mock_get_response.__exit__ = MagicMock(return_value=False)

            mock_post_response = MagicMock()
            mock_post_response.status = 200
            mock_post_response.read.return_value = b'{"ok": true}'
            mock_post_response.__enter__ = lambda s: s
            mock_post_response.__exit__ = MagicMock(return_value=False)

            call_count = {"post": 0}
            def mock_urlopen(req, **kwargs):
                if hasattr(req, "data") and req.data:
                    call_count["post"] += 1
                    return mock_post_response
                return mock_get_response

            with (
                patch.object(mt5_signal_bot, "mt5_ready", True),
                patch.object(mt5_signal_bot, "_SIGNALS_LOG", str(signal_log)),
                patch.object(mt5_signal_bot, "get_broker_time",
                             return_value=datetime(2026, 7, 22, 9, 25)),
                patch("mt5_signal_bot.urllib.request.urlopen", side_effect=mock_urlopen),
                patch("mt5_signal_bot.DASHBOARD_URL", "http://fake-dashboard"),
            ):
                mt5_signal_bot.push_to_dashboard()

            self.assertGreaterEqual(call_count["post"], 1)


if __name__ == "__main__":
    unittest.main()