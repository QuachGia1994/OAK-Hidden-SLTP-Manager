"""The process launcher must require a current MT4 heartbeat, not HTTP 200 alone."""

import io
import json
import unittest
from unittest.mock import MagicMock, patch

from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

from oak_qt_shell import NativeShell
from services.mt4_feed_health import MT4FeedHealth, read_mt4_feed_health
from services.signal_process_supervisor import SignalProcessSupervisor


class _Response(io.BytesIO):
    def __init__(self, payload: dict, status: int = 200) -> None:
        super().__init__(json.dumps(payload).encode("utf-8"))
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class MT4FeedReadinessTests(unittest.TestCase):
    def test_listener_health_is_not_treated_as_live_feed_when_stale(self) -> None:
        with patch("services.mt4_feed_health.urllib.request.urlopen", return_value=_Response({"data_state": "stale"})):
            health = read_mt4_feed_health()

        self.assertTrue(health.listener_available)
        self.assertEqual(health.data_state, "stale")
        self.assertFalse(health.feed_connected)

    def test_connected_heartbeat_unblocks_feed(self) -> None:
        with patch("services.mt4_feed_health.urllib.request.urlopen", return_value=_Response({"data_state": "connected"})):
            health = read_mt4_feed_health()

        self.assertTrue(health.feed_connected)

    def test_start_all_never_launches_signal_bot_when_feed_is_not_connected(self) -> None:
        supervisor = SignalProcessSupervisor([])
        supervisor.register_signals({
            "mt4_feed_server": {"name": "Feed"},
            "signal_bot": {"name": "Signal Bot"},
            "mimo_worker": {"name": "Worker"},
        })
        supervisor.start_signal_process = MagicMock()
        supervisor._wait_for_feed_health = MagicMock(return_value=False)
        supervisor._set_running_ui = MagicMock()
        supervisor._log = MagicMock()

        with patch("services.signal_process_supervisor.time.sleep"):
            supervisor.start_all_signals()

        started = [call.args[0] for call in supervisor.start_signal_process.call_args_list]
        self.assertEqual(started, ["mt4_feed_server", "mimo_worker"])
        supervisor._set_running_ui.assert_called_once_with("signal_bot", False, status="Blocked")

    def test_manual_signal_bot_start_is_blocked_when_feed_is_stale(self) -> None:
        supervisor = SignalProcessSupervisor([])
        supervisor.register_signals({"signal_bot": {"name": "Signal Bot", "proc": None}})
        supervisor._set_running_ui = MagicMock()
        supervisor._log = MagicMock()

        with patch(
            "services.signal_process_supervisor.read_mt4_feed_health",
            return_value=MT4FeedHealth(True, "stale"),
        ):
            supervisor.start_signal_process("signal_bot")

        supervisor._set_running_ui.assert_called_once_with("signal_bot", False, status="Blocked")
        self.assertIn("blocked", supervisor._log.call_args.args[0].lower())

    def test_native_qt_manual_signal_bot_start_is_blocked_when_feed_is_stale(self) -> None:
        shell = NativeShell.__new__(NativeShell)
        shell.signal_cards = {"signal_bot": {"name": "Signal Bot"}}
        shell.signal_processes = {}
        shell._append_signal_log = MagicMock()
        shell._set_signal_running = MagicMock()

        with patch(
            "oak_qt_shell.read_mt4_feed_health",
            return_value=MT4FeedHealth(True, "stale"),
        ):
            NativeShell.start_signal(shell, "signal_bot")

        shell._set_signal_running.assert_called_once_with("signal_bot", False, status="Blocked")
        self.assertIn("blocked", shell._append_signal_log.call_args.args[1].lower())


if __name__ == "__main__":
    unittest.main()
