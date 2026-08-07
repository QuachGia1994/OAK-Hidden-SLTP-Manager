"""The process launcher must not block the Signal Bot on the legacy MT4 feed."""

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

    def test_start_all_launches_signal_bot_and_skips_disabled_mt4_feed(self) -> None:
        supervisor = SignalProcessSupervisor([])
        supervisor.register_signals({
            "mt4_feed_server": {"name": "Feed"},
            "signal_bot": {"name": "Signal Bot"},
            "mimo_worker": {"name": "Worker"},
        })
        supervisor.start_signal_process = MagicMock()
        supervisor._set_running_ui = MagicMock()
        supervisor._log = MagicMock()

        with patch("services.signal_process_supervisor.time.sleep"):
            supervisor.start_all_signals()

        started = [call.args[0] for call in supervisor.start_signal_process.call_args_list]
        self.assertEqual(started, ["signal_bot", "mimo_worker"])
        self.assertNotIn("mt4_feed_server", started)

    def test_start_all_launches_mt4_feed_server_when_legacy_enabled(self) -> None:
        supervisor = SignalProcessSupervisor([])
        supervisor.register_signals({
            "mt4_feed_server": {"name": "Feed"},
            "signal_bot": {"name": "Signal Bot"},
        })
        supervisor.start_signal_process = MagicMock()
        supervisor._set_running_ui = MagicMock()
        supervisor._log = MagicMock()

        with patch("services.signal_process_supervisor.time.sleep"), \
             patch.object(supervisor, "_is_mt4_legacy_enabled", return_value=True):
            supervisor.start_all_signals()

        started = [call.args[0] for call in supervisor.start_signal_process.call_args_list]
        self.assertIn("mt4_feed_server", started)
        self.assertIn("signal_bot", started)

    def test_manual_signal_bot_start_proceeds_without_mt4_feed(self) -> None:
        supervisor = SignalProcessSupervisor([])
        supervisor.register_signals({"signal_bot": {"name": "Signal Bot", "proc": None}})
        supervisor._set_running_ui = MagicMock()
        supervisor._log = MagicMock()
        supervisor._kill_orphan_processes = MagicMock()

        mock_proc = MagicMock()
        mock_proc.pid = 1234
        with patch("services.signal_process_supervisor.subprocess.Popen", return_value=mock_proc) as popen_mock, \
             patch("services.signal_process_supervisor.threading.Thread"):
            supervisor.start_signal_process("signal_bot")

        cmd = popen_mock.call_args.args[0]
        self.assertIn("--audit-service", cmd)  # legacy GUI must start the audit service, never main()
        self.assertNotIn("blocked", (supervisor._log.call_args.args[0] or "").lower())
        supervisor._set_running_ui.assert_called_once()

    def test_mt4_feed_server_is_disabled_by_default_in_native_qt(self) -> None:
        shell = NativeShell.__new__(NativeShell)
        shell.signal_cards = {"mt4_feed_server": {"name": "MT4 Feed"}}
        shell.signal_processes = {}
        shell._append_signal_log = MagicMock()
        shell._set_signal_running = MagicMock()

        NativeShell.start_signal(shell, "mt4_feed_server")

        shell._set_signal_running.assert_called_once_with("mt4_feed_server", False, status="Blocked")
        self.assertIn("disabled", shell._append_signal_log.call_args.args[1].lower())


if __name__ == "__main__":
    unittest.main()
