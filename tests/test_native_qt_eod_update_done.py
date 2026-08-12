# -*- coding: utf-8 -*-
"""Regression: _eod_update_done must not raise on successful auto-EOD
(append_log typo) and must tolerate destroyed widgets during teardown."""
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qt_env():
    import oak_qt_shell as shell_mod

    qt, err = shell_mod.load_qt()
    assert qt is not None, err
    shell_mod.QT = qt
    app = qt.QApplication.instance() or qt.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    yield qt, app, shell_mod


@pytest.fixture()
def shell(qt_env, monkeypatch):
    qt, app, shell_mod = qt_env
    # NativeShell.__init__ -> refresh() -> _refresh_stock_advisor_page() ->
    # _check_auto_eod_update() can spawn a real `python -m eod_collector
    # update` when tests run at/after 15:00 local time. Neutralize the launch
    # at CLASS level BEFORE constructing the shell (non-LIVE-SAFE otherwise).
    monkeypatch.setattr(
        shell_mod.NativeShell, "update_eod_data", lambda self, is_auto=False: None
    )
    shell = shell_mod.NativeShell()
    shell._last_auto_eod_date = time.strftime("%Y-%m-%d")
    shell.window.show()
    app.processEvents()
    for tab in shell.tab_pages:
        shell.switch_tab(tab)
        app.processEvents()
    yield shell
    shell.shutdown()


def test_auto_eod_success_does_not_raise_and_schedules_scanner(qt_env, shell):
    qt, app, shell_mod = qt_env
    shell._reload_stock_rows = lambda: None  # avoid DB/table work in test
    calls = []
    shell.run_stock_advisor = lambda: calls.append("scanner")

    shell._eod_update_done(0, None, True)  # must NOT raise (was AttributeError)

    deadline = time.time() + 3
    while time.time() < deadline and not calls:
        app.processEvents()
        time.sleep(0.02)
    assert calls == ["scanner"], f"auto stock scanner was never scheduled: {calls}"


def test_auto_eod_failure_path_does_not_raise(qt_env, shell):
    qt, app, shell_mod = qt_env
    shell._eod_update_done(1, None, True)  # failure path must not raise


def test_eod_done_tolerates_destroyed_widget_and_still_schedules_scanner(qt_env, shell):
    qt, app, shell_mod = qt_env

    class DeletedButton:
        def setEnabled(self, enabled):
            raise RuntimeError(
                "Internal C++ object (PySide6.QtWidgets.QPushButton) already deleted."
            )

    shell.stock_update_eod_btn = DeletedButton()
    reloaded = []
    calls = []
    shell._reload_stock_rows = lambda: reloaded.append(True)
    shell.run_stock_advisor = lambda: calls.append("scanner")

    shell._eod_update_done(0, None, True)  # must not raise RuntimeError

    deadline = time.time() + 3
    while time.time() < deadline and not calls:
        app.processEvents()
        time.sleep(0.02)

    assert reloaded == [True], "DB rows were not reloaded despite EOD success"
    assert calls == ["scanner"], f"auto stock scanner was not scheduled: {calls}"


def test_check_auto_eod_update_does_not_mark_date_if_update_skipped(qt_env, shell, monkeypatch):
    qt, app, shell_mod = qt_env
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("OAK_DISABLE_AUTO_EOD", raising=False)

    shell._last_auto_eod_date = None
    # Simulate existing running process -> update_eod_data returns False
    shell.eod_update_process = object()

    # Fake time to weekday after 15:00
    class FakeDateTime:
        @classmethod
        def now(cls):
            from datetime import datetime
            return datetime(2026, 8, 12, 16, 0, 0) # Wednesday 16:00

    monkeypatch.setattr(shell_mod, "datetime", FakeDateTime)
    shell._check_auto_eod_update()

    assert shell._last_auto_eod_date is None, "_last_auto_eod_date was prematurely marked despite process skip"


def test_check_auto_eod_update_skipped_in_pytest_env(qt_env, shell, monkeypatch):
    qt, app, shell_mod = qt_env
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_native_qt_eod_update_done.py")
    shell._last_auto_eod_date = None
    launched = []
    monkeypatch.setattr(shell, "update_eod_data", lambda is_auto=False: launched.append(True))

    shell._check_auto_eod_update()
    assert not launched, "_check_auto_eod_update should return early under PYTEST_CURRENT_TEST"


def test_eod_update_done_noop_during_shutdown(qt_env, shell):
    qt, app, shell_mod = qt_env
    shell._is_shut_down = True
    calls = []
    shell.run_stock_advisor = lambda: calls.append("scanner")

    shell._eod_update_done(0, None, True)
    app.processEvents()
    assert not calls, "run_stock_advisor should not be scheduled after shutdown"
    shell._is_shut_down = False