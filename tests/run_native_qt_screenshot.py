"""Run the NativeQt screenshot regression in a dedicated process."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import oak_qt_shell as shell_mod  # noqa: E402

THEMES = ("dark", "light", "deep-sea", "contrast")


def main() -> int:
    qt, error = shell_mod.load_qt()
    if qt is None:
        print(f"PySide6 not installed: {error}")
        return 0
    shell_mod.QT = qt
    app = qt.QApplication.instance() or qt.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    shell = shell_mod.NativeShell()
    out = ROOT / "scratch" / "redesign"
    out.mkdir(parents=True, exist_ok=True)
    try:
        for theme in THEMES:
            shell.settings = {**shell.settings, "theme": theme}
            shell.apply_theme()
            app.processEvents()
            for tab in shell.tab_pages:
                shell.switch_tab(tab)
                app.processEvents()
                page = shell.tab_pages[tab]
                for _ in range(100):
                    app.processEvents()
                    if page.graphicsEffect() is None:
                        break
                    time.sleep(0.02)
                app.processEvents()
                png = out / f"{theme}_{tab.replace(' ', '_')}.png"
                if not page.grab().save(str(png)):
                    raise RuntimeError(f"grab failed for {theme}/{tab}")
                if png.stat().st_size <= 1000:
                    raise RuntimeError(f"tiny PNG for {theme}/{tab}")
    finally:
        shell.shutdown()
        shell.window.close()
    print("NativeQt screenshot capture: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
