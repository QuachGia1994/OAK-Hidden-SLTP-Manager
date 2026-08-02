"""Native Qt must hide the legacy MT4 Feed Server unless explicitly enabled.

Mirrors the acceptance tests required by the edit prompt:
- test_qt_default_signal_defs_exclude_mt4
- test_qt_running_count_excludes_hidden_legacy_services
- test_qt_legacy_mode_can_show_mt4_card
- test_run_all_starts_only_visible_services
"""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import oak_qt_shell


class _FakeProc:
    def __init__(self, running):
        self._running = running

    def state(self):
        return 1 if self._running else 0


class _FakeSummary:
    def __init__(self):
        self.value = None

    def setText(self, text):
        self.value = text


def _no_legacy():
    return False


class NativeQtVisibleSignalDefsTests(unittest.TestCase):
    def test_qt_default_signal_defs_exclude_mt4(self):
        with patch.object(oak_qt_shell, "_legacy_mt4_feed_enabled", side_effect=_no_legacy):
            defs = oak_qt_shell.get_visible_signal_defs()

        keys = [key for key, _name, _color in defs]
        self.assertEqual(keys, ["signal_bot", "mimo_bot", "mimo_worker", "factcheck_worker"])
        self.assertNotIn("mt4_feed_server", keys)

    def test_qt_legacy_mode_can_show_mt4_card(self):
        with patch.object(oak_qt_shell, "_legacy_mt4_feed_enabled", return_value=True):
            defs = oak_qt_shell.get_visible_signal_defs()

        keys = [key for key, _name, _color in defs]
        self.assertEqual(keys[0], "mt4_feed_server")
        self.assertEqual(len(keys), 5)

    def test_qt_running_count_excludes_hidden_legacy_services(self):
        shell = oak_qt_shell.NativeShell.__new__(oak_qt_shell.NativeShell)
        shell.signal_summary = _FakeSummary()
        shell.signal_processes = {
            "signal_bot": _FakeProc(running=True),
            "mt4_feed_server": _FakeProc(running=True),
        }
        shell._feed_listener_available = False
        fake_qt = SimpleNamespace(NotRunning=0)

        with patch.object(oak_qt_shell, "_legacy_mt4_feed_enabled", side_effect=_no_legacy), \
             patch.object(oak_qt_shell, "QT", fake_qt, create=True), \
             patch.object(oak_qt_shell, "native_format", lambda template, **kw: template.format(**kw)):
            shell._refresh_signal_summary()

        self.assertEqual(shell.signal_summary.value, "1/4 running")

    def test_qt_legacy_mode_count_includes_mt4_feed(self):
        shell = oak_qt_shell.NativeShell.__new__(oak_qt_shell.NativeShell)
        shell.signal_summary = _FakeSummary()
        shell.signal_processes = {
            "signal_bot": _FakeProc(running=True),
            "mt4_feed_server": _FakeProc(running=True),
        }
        shell._feed_listener_available = False
        fake_qt = SimpleNamespace(NotRunning=0)

        with patch.object(oak_qt_shell, "_legacy_mt4_feed_enabled", return_value=True), \
             patch.object(oak_qt_shell, "QT", fake_qt, create=True), \
             patch.object(oak_qt_shell, "native_format", lambda template, **kw: template.format(**kw)):
            shell._refresh_signal_summary()

        self.assertEqual(shell.signal_summary.value, "2/5 running")

    def test_run_all_starts_only_visible_services(self):
        shell = oak_qt_shell.NativeShell.__new__(oak_qt_shell.NativeShell)
        shell.start_signal = MagicMock()
        single_shot = MagicMock()

        fake_qt = SimpleNamespace(
            NotRunning=0,
            QTimer=SimpleNamespace(singleShot=single_shot),
        )

        with patch.object(oak_qt_shell, "_legacy_mt4_feed_enabled", side_effect=_no_legacy), \
             patch.object(oak_qt_shell, "QT", fake_qt, create=True):
            shell.start_all_signals()

        scheduled = [call.args[1].__defaults__[0] for call in single_shot.call_args_list]
        self.assertEqual(
            scheduled,
            ["signal_bot", "mimo_bot", "mimo_worker", "factcheck_worker"],
        )
        self.assertNotIn("mt4_feed_server", scheduled)


if __name__ == "__main__":
    unittest.main()
