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


def test_eod_done_tolerates_destroyed_widget(qt_env, shell):
    qt, app, shell_mod = qt_env

    class DeletedButton:
        def setEnabled(self, enabled):
            raise RuntimeError(
                "Internal C++ object (PySide6.QtWidgets.QPushButton) already deleted."
            )

    shell.stock_update_eod_btn = DeletedButton()
    shell._reload_stock_rows = lambda: None
    shell.run_stock_advisor = lambda: None
    shell._eod_update_done(0, None, True)  # must not raise RuntimeError