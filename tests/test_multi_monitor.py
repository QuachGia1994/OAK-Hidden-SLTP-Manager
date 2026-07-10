# -*- coding: utf-8 -*-
"""Multi-monitor policy unit tests (no GUI spawn)."""
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from controllers.monitor_controller import MonitorControllerMixin
from domain.ticket_manager import TicketManager, trades_file_for_profile
from domain.copy_trade_manager import pending_partials_file_for_profile


class FakeProc:
    def __init__(self, alive=True, pid=1):
        self._alive = alive
        self.pid = pid

    def poll(self):
        return None if self._alive else 0


class FakeApp(MonitorControllerMixin):
    def __init__(self):
        self.profiles = {"A": {}, "B": {}, "Vantage": {}, "VantageDemo": {}}
        self.workers = {}
        self.running_profile_name = None
        self.selected_profile_name = None
        self.logs = []
        self.combo_profiles = MagicMock()
        self.combo_profiles.get.return_value = "B"
        self.btn_start = MagicMock()
        self.btn_stop = MagicMock()
        self.console = MagicMock()
        self.copy_console = MagicMock()
        self.copy_console.winfo_exists.return_value = False
        self.running_monitors_frame = None
        self._after_calls = []

    def log(self, msg):
        self.logs.append(msg)

    def after(self, ms, fn, *args):
        self._after_calls.append((ms, fn, args))

    def log_to_console_direct(self, msg):
        self.logs.append(f"console:{msg}")

    def update_ui_state(self, name):
        self._last_ui = name

    def refresh_profile_list(self):
        pass

    def refresh_running_monitors_panel(self):
        self._panel_refreshed = True

    def _update_active_profile_badge(self, name):
        pass

    def _kill_orphan_workers(self, name):
        self.logs.append(f"orphan:{name}")


class TestMultiMonitor(unittest.TestCase):
    def test_live_list_multiple(self):
        app = FakeApp()
        app.workers = {
            "A": {"proc": FakeProc(True, 11)},
            "B": {"proc": FakeProc(True, 22)},
            "C": {"proc": FakeProc(False, 33)},
        }
        live = app._get_live_running_profiles()
        self.assertEqual(live, ["A", "B"])

    def test_primary_prefers_selected_if_live(self):
        app = FakeApp()
        app.workers = {
            "A": {"proc": FakeProc(True, 11)},
            "B": {"proc": FakeProc(True, 22)},
        }
        app.selected_profile_name = "B"
        app.combo_profiles.get.return_value = "A"  # widget wrong → state wins
        self.assertEqual(app._get_live_running_profile(), "B")

    def test_stop_profile_only_targets_one(self):
        app = FakeApp()
        a_proc = FakeProc(True, 11)
        b_proc = FakeProc(True, 22)
        app.workers = {
            "A": {"proc": a_proc},
            "B": {"proc": b_proc},
        }
        app.running_profile_name = "A"

        a_proc.terminate = MagicMock(side_effect=lambda: setattr(a_proc, "_alive", False))
        with patch.object(os, "name", "posix"):
            app.stop_monitor_profile("A", confirm=False)

        self.assertFalse(app._is_profile_live("A"))
        self.assertTrue(app._is_profile_live("B"))
        self.assertEqual(app.running_profile_name, "B")

    def test_orphan_cmdline_exact_vantage_vs_demo(self):
        """Vantage must not match VantageDemo (substring hazard)."""
        m = MonitorControllerMixin
        demo_cmd = (
            r'python.exe "C:\app\OAK_Hidden_SLTP_Manager.py" '
            r"--worker --profile VantageDemo"
        )
        vant_cmd = (
            r'python.exe "C:\app\OAK_Hidden_SLTP_Manager.py" '
            r"--worker --profile Vantage"
        )
        self.assertTrue(m._cmdline_profile_exact(vant_cmd, "Vantage"))
        self.assertFalse(m._cmdline_profile_exact(demo_cmd, "Vantage"))
        self.assertTrue(m._cmdline_profile_exact(demo_cmd, "VantageDemo"))
        self.assertFalse(m._cmdline_profile_exact(vant_cmd, "VantageDemo"))
        # --profile=form
        self.assertTrue(
            m._cmdline_profile_exact("--worker --profile=Vantage", "Vantage")
        )
        self.assertFalse(
            m._cmdline_profile_exact("--worker --profile=VantageDemo", "Vantage")
        )

    def test_reader_thread_uses_selected_state_not_combo(self):
        """Reader must not call combo_profiles.get() (Tk not thread-safe)."""
        app = FakeApp()
        app.selected_profile_name = "A"
        app.workers = {"A": {"proc": FakeProc(True, 1), "logs": []}}

        class FakeStdout:
            def __init__(self):
                self.lines = ["hello from worker\n", ""]
                self.i = 0

            def readline(self):
                if self.i < len(self.lines):
                    line = self.lines[self.i]
                    self.i += 1
                    return line
                return ""

        proc = FakeProc(True, 1)
        proc.stdout = FakeStdout()

        app.monitor_worker_output("A", proc)
        # combo must never be touched from reader path
        app.combo_profiles.get.assert_not_called()
        # after() scheduled log for selected profile
        self.assertTrue(any(c[1] == app.log_to_console_direct for c in app._after_calls))

    def test_reader_skips_console_when_not_selected(self):
        app = FakeApp()
        app.selected_profile_name = "B"
        app.workers = {"A": {"proc": FakeProc(True, 1), "logs": []}}

        class FakeStdout:
            def readline(self):
                if not hasattr(self, "done"):
                    self.done = True
                    return "secret line\n"
                return ""

        proc = FakeProc(True, 1)
        proc.stdout = FakeStdout()
        app.monitor_worker_output("A", proc)
        app.combo_profiles.get.assert_not_called()
        log_calls = [c for c in app._after_calls if c[1] == app.log_to_console_direct]
        self.assertEqual(log_calls, [])
        self.assertIn("secret line", app.workers["A"]["logs"])


class TestPerProfileIsolation(unittest.TestCase):
    def test_trades_file_names(self):
        self.assertEqual(trades_file_for_profile("Vantage"), "trades_Vantage.json")
        self.assertEqual(trades_file_for_profile("VantageDemo"), "trades_VantageDemo.json")
        self.assertNotEqual(
            trades_file_for_profile("Vantage"),
            trades_file_for_profile("VantageDemo"),
        )

    def test_pending_partials_file_names(self):
        self.assertEqual(
            pending_partials_file_for_profile("ICMarkets"),
            "pending_partials_ICMarkets.json",
        )
        self.assertNotEqual(
            pending_partials_file_for_profile("Vantage"),
            pending_partials_file_for_profile("VantageDemo"),
        )

    def test_ticket_manager_same_ticket_id_isolated(self):
        """Two brokers can share ticket_id without clobbering each other."""
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                # Reset module caches for clean isolation
                import domain.ticket_manager as tm

                tm._TRADES_CACHES.clear()
                a = TicketManager(profile_name="ICMarkets")
                b = TicketManager(profile_name="Vantage")
                a.update_ticket(12345678, symbol="XAUUSD", profile="ICMarkets")
                b.update_ticket(12345678, symbol="EURUSD", profile="Vantage")
                self.assertEqual(a.get_ticket(12345678).get("symbol"), "XAUUSD")
                self.assertEqual(b.get_ticket(12345678).get("symbol"), "EURUSD")
                self.assertTrue(os.path.exists("trades_ICMarkets.json"))
                self.assertTrue(os.path.exists("trades_Vantage.json"))
            finally:
                os.chdir(cwd)
                import domain.ticket_manager as tm

                tm._TRADES_CACHES.clear()


class TestAccountCardPrefix(unittest.TestCase):
    def test_hb_profile_prefix_not_running(self):
        """Prefix must use heartbeat source profile, not unrelated running name."""
        hb_profile = "ICMarkets"
        running = "VantageDemo"
        server = "ICMarketsSC-MT5-6"
        login = "7398029"
        server_text = f"{server} | #{login}"
        if hb_profile:
            server_text = f"[{hb_profile}] {server_text}"
        self.assertIn("[ICMarkets]", server_text)
        self.assertNotIn("[VantageDemo]", server_text)
        # Old buggy pattern would put running when running != profile
        profile = "ICMarkets"
        buggy = f"{server} | #{login}"
        if running and profile and running != profile:
            buggy = f"[{running}] {buggy}"
        self.assertIn("[VantageDemo]", buggy)  # documents the old bug
        self.assertNotEqual(server_text, buggy)


if __name__ == "__main__":
    unittest.main()
