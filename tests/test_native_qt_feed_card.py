"""Regression tests for compact, truthful NativeQt MT4 Feed cards."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import unittest

import oak_qt_shell
from oak_qt_shell import NativeShell, format_feed_card_details
from services.mt4_feed_health import MT4FeedHealth


class NativeQtFeedCardTests(unittest.TestCase):
    def test_summary_stays_at_two_lines_while_tooltip_keeps_full_coverage(self) -> None:
        coverage = {
            "XAUUSD": {"M30": 2300, "H1": 1150, "H4": 300},
            "GBPUSD": {"M30": 2300, "H1": 1150, "H4": 300},
            "GBPAUD": {"M30": 2300, "H1": 1150, "H4": 300},
        }

        summary, tooltip = format_feed_card_details("CONNECTED", 7, coverage)

        self.assertEqual(len(summary.splitlines()), 2)
        self.assertIn("3 symbols", summary)
        self.assertNotIn("GBPUSD", summary)
        self.assertIn("GBPUSD M30:2300 H1:1150 H4:300", tooltip)

    def test_live_listener_overrides_dead_parent_process_display_only(self) -> None:
        shell = NativeShell.__new__(NativeShell)
        feed_info = MagicMock()
        shell.signal_cards = {"mt4_feed_server": {"feed_info": feed_info}}
        shell._last_feed_card_refresh = 0.0
        shell._set_signal_running = MagicMock()
        store = MagicMock()
        store.get_latest_heartbeat.return_value = {
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        bar_counts = {"M30": 2300, "H1": 1150, "H4": 300}
        store.get_bars.side_effect = lambda _symbol, timeframe, *_args: [None] * bar_counts[timeframe]

        with (
            patch("repositories.mt4_feed_store.MT4FeedStore", return_value=store),
            patch("oak_qt_shell.read_mt4_feed_health", return_value=MT4FeedHealth(True, "connected")),
            patch("oak_qt_shell.time.monotonic", return_value=10.0),
        ):
            NativeShell._refresh_feed_card(shell)

        shell._set_signal_running.assert_called_once_with(
            "mt4_feed_server",
            True,
            status="Running",
            preserve_controls=True,
        )
        summary = feed_info.setText.call_args.args[0]
        self.assertEqual(len(summary.splitlines()), 2)
        self.assertIn("5 symbols", summary)
        self.assertTrue(store.close.called)

    def test_listener_without_heartbeat_is_shown_as_degraded_not_stopped(self) -> None:
        shell = NativeShell.__new__(NativeShell)
        feed_info = MagicMock()
        shell.signal_cards = {"mt4_feed_server": {"feed_info": feed_info}}
        shell._last_feed_card_refresh = 0.0
        shell._set_signal_running = MagicMock()
        store = MagicMock()
        store.get_latest_heartbeat.return_value = None

        with (
            patch("repositories.mt4_feed_store.MT4FeedStore", return_value=store),
            patch("oak_qt_shell.read_mt4_feed_health", return_value=MT4FeedHealth(True, "disconnected")),
            patch("oak_qt_shell.time.monotonic", return_value=10.0),
        ):
            NativeShell._refresh_feed_card(shell)

        shell._set_signal_running.assert_called_once_with(
            "mt4_feed_server",
            False,
            status="Degraded",
            preserve_controls=True,
        )
        self.assertIn("DISCONNECTED", feed_info.setText.call_args.args[0])

    def test_periodic_refresh_does_not_overwrite_external_feed_status(self) -> None:
        shell = NativeShell.__new__(NativeShell)
        shell.signal_processes = {}
        shell._set_signal_running = MagicMock()
        shell._refresh_feed_card = MagicMock()
        shell._refresh_signal_summary = MagicMock()

        NativeShell._refresh_signal_states(shell)

        refreshed_keys = [call.args[0] for call in shell._set_signal_running.call_args_list]
        self.assertNotIn("mt4_feed_server", refreshed_keys)
        shell._refresh_feed_card.assert_called_once_with()

    def test_external_listener_not_counted_when_feed_hidden(self) -> None:
        shell = NativeShell.__new__(NativeShell)
        shell.signal_processes = {}
        shell.signal_summary = MagicMock()
        shell._feed_listener_available = True

        with patch.object(oak_qt_shell, "_legacy_mt4_feed_enabled", return_value=False):
            NativeShell._refresh_signal_summary(shell)

        self.assertIn("0/4 running", shell.signal_summary.setText.call_args.args[0])

    def test_external_listener_counts_once_when_legacy_feed_visible(self) -> None:
        shell = NativeShell.__new__(NativeShell)
        shell.signal_processes = {}
        shell.signal_summary = MagicMock()
        shell._feed_listener_available = True

        with patch.object(oak_qt_shell, "_legacy_mt4_feed_enabled", return_value=True):
            NativeShell._refresh_signal_summary(shell)

        self.assertIn("1/5 running", shell.signal_summary.setText.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
