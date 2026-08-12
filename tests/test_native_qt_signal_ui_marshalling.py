# -*- coding: utf-8 -*-
"""Regression: signal output from the supervisor's background monitor thread
must reach the Qt signal-card console (oak_qt_shell)."""
import os
import sys
import threading
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


def test_signal_output_from_background_thread_reaches_console(qt_env):
    qt, app, shell_mod = qt_env
    shell = shell_mod.NativeShell()
    shell.window.show()
    app.processEvents()
    for tab in shell.tab_pages:
        shell.switch_tab(tab)
        app.processEvents()
    try:
        key = "factcheck_worker"
        assert key in shell.signal_cards

        # Simulate exactly what SignalProcessSupervisor._monitor_signal_output
        # does: append a line from a background thread.
        def _emit():
            shell.signal_supervisor._append_console_line(key, "BG-LINE-123")

        thread = threading.Thread(target=_emit)
        thread.start()
        thread.join()

        deadline = time.time() + 5
        text = ""
        while time.time() < deadline:
            app.processEvents()
            text = shell.signal_cards[key]["console"].toPlainText()
            if "BG-LINE-123" in text:
                break
            time.sleep(0.02)
        assert "BG-LINE-123" in text, f"console never received background output: {text!r}"
    finally:
        shell.shutdown()