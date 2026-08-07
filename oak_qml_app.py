# -*- coding: utf-8 -*-
"""Phase 1-2 QML shell scaffold for OAK Manager (Profiles + Dashboard + Shell live).

Widget-hosted QML: QQuickWidget renders a QML sidebar + tab pages.
``create_engine(profile_manager=...)`` injects a ``ProfileManager`` (or
fake) into a ``QmlProfileBridge`` singleton accessible from QML as
``Api`` (``import QmlApi 1.0``).

``create_engine(dashboard_backend=...)`` injects a ``DashboardBackend``
(or fake) into a ``QmlDashboardBridge`` singleton accessible from QML as
``DashApi`` (``import QmlApi 1.0``).

``create_engine(shell_backend=...)`` injects a ``ShellBackend``
(or fake) into a ``QmlShellBridge`` singleton accessible from QML as
``ShellApi`` (``import QmlApi 1.0``).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Environment before any Qt import ──
os.environ.setdefault("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))
os.environ.setdefault("QT_QUICK_BACKEND", "software")

SOURCE_ROOT = Path(__file__).resolve().parent
QML_DIR = SOURCE_ROOT / "qml"

PYTHON_DIR = SOURCE_ROOT / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))


def app_icon_path() -> Path | None:
    """Resolve the bundled app icon in source and frozen PyInstaller modes."""
    folders = [SOURCE_ROOT]
    if getattr(sys, "frozen", False):
        folders.append(Path(sys.executable).resolve().parent)
    for folder in folders:
        candidate = folder / "icon.ico"
        if candidate.is_file():
            return candidate
    return None


# ── Sensitive key set (defense-in-depth redaction) ──
def _sensitive_keys():
    from oak_core.supervisor.profiles import _SENSITIVE_KEYS
    return frozenset(_SENSITIVE_KEYS)


# ── Uptime helpers (patchable in tests for deterministic uptime) ──
def _monotonic_now():
    import time as _time
    return _time.monotonic()


def _format_uptime_local(elapsed_seconds):
    """Format elapsed duration as ``HH:MM:SS`` or ``Nd HH:MM:SS``.

    Mirrors oak_core.supervisor._format_uptime exactly: integer seconds,
    never negative.
    """
    total = max(0, int(elapsed_seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


# ── Bridge: expose ProfileManager to QML via singleton ──

from PySide6.QtCore import QObject, Slot  # noqa: E402


class QmlProfileBridge(QObject):
    """Expose ProfileManager to QML (read + whitelisted mutations).

    Every method catches exceptions and returns a dict with an ``ok`` flag so
    QML never has to handle QML-JS exceptions.  Sensitive keys are stripped
    from every payload (defense in depth on top of the backend redaction).
    """

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._sensitive = _sensitive_keys()

    def _redact(self, payload):
        if isinstance(payload, dict):
            return {k: self._redact(v) for k, v in payload.items() if k not in self._sensitive}
        if isinstance(payload, list):
            return [self._redact(v) for v in payload]
        return payload

    def _call(self, fn, *args, **kwargs):
        try:
            return {"ok": True, "result": self._redact(fn(*args, **kwargs))}
        except Exception as exc:  # noqa: BLE001 — surfaced to QML as error dict
            return {"ok": False, "error": str(exc)}

    @Slot(result=list)
    def list_profiles(self):
        payload = self._manager.list_profiles()
        return self._redact(payload.get("profiles") or [])

    @Slot(str, result=dict)
    def start_profile(self, name):
        return self._call(self._manager.start_profile, str(name))

    @Slot(str, result=dict)
    def stop_profile(self, name):
        return self._call(self._manager.stop_profile, str(name))

    @Slot(str, result=dict)
    def add_profile(self, name):
        return self._call(self._manager.add_profile, str(name), "", -1)

    @Slot(str, str, result=dict)
    def update_profile(self, name, updates_json):
        import json as _json
        updates = _json.loads(updates_json) if updates_json else {}
        return self._call(self._manager.update_profile, str(name), updates)

    @Slot(str, result=dict)
    def duplicate_profile(self, name):
        return self._call(self._manager.duplicate_profile, str(name))

    @Slot(str, result=dict)
    def delete_profile(self, name):
        return self._call(self._manager.delete_profile, str(name))

    @Slot(str, result=dict)
    def secret_status(self, name):
        return self._call(self._manager.secret_status, str(name))

    @Slot(str, str, result=dict)
    def set_tele_token(self, name, token):
        return self._call(self._manager.set_tele_token, str(name), str(token))

    @Slot(str, result=dict)
    def clear_tele_token(self, name):
        return self._call(self._manager.clear_tele_token, str(name))


# ── Dashboard: read-only data sources ──

class DashboardBackend:
    """Read-only data sources for the Dashboard page (injectable in tests)."""

    def __init__(self, manager, services=None):
        self._manager = manager
        self._services = services
        self._started = _monotonic_now()

    def _get_services(self):
        if self._services is None:
            from oak_core.supervisor.services import ServiceManager
            self._services = ServiceManager()
        return self._services

    def handshake(self):
        from oak_core import version as v
        return {"app": v.APP_NAME, "version": v.APP_VERSION, "protocol": v.PROTOCOL_VERSION}

    def health(self):
        workers = list(self._manager.running_workers())
        elapsed = max(0.0, _monotonic_now() - self._started)
        return {"status": "ok", "uptime": _format_uptime_local(elapsed), "workers": workers, "protocol": 1}

    def profiles(self):
        payload = self._manager.list_profiles()
        return payload.get("profiles") or []

    def services(self):
        return self._get_services().list_services().get("services") or []

    def orders(self):
        from oak_core.supervisor import orders as orders_module
        s = orders_module.orders_summary()
        return {
            "scheduled_trades": len(s.get("scheduled_trades") or []),
            "scheduled_closes": len(s.get("scheduled_closes") or []),
            "pending_partials": len(s.get("pending_partials") or []),
            "total": (len(s.get("scheduled_trades") or []) + len(s.get("scheduled_closes") or [])
                      + len(s.get("pending_partials") or [])),
        }

    def logs(self, lines=200):
        from oak_core.supervisor import diagnostics as diagnostics_module
        return diagnostics_module.tail(lines=int(lines))


# ── Shell backend: shared data sources for all shell pages ──

class ShellBackend:
    """Shared backend for all shell pages (injectable in tests).

    Wraps existing supervisor module-level functions / manager constructors.
    Every method returns plain dict/list; never raises.
    """

    def services(self):
        from oak_core.supervisor.services import ServiceManager
        return ServiceManager().list_services().get("services") or []

    def service_start(self, key, profile, confirm):
        from oak_core.supervisor.services import ServiceManager
        return ServiceManager().start_service(key, profile=profile, confirm=bool(confirm))

    def service_stop(self, key):
        from oak_core.supervisor.services import ServiceManager
        return ServiceManager().stop_service(key)

    def screener(self, limit=1000):
        from oak_core.supervisor.accounts import AccountQueries
        return AccountQueries().screener_list(limit=limit)

    def run_filter(self, limit=30):
        from oak_core.supervisor.accounts import AccountQueries
        return AccountQueries().run_filter(limit=limit)

    def copy_get(self, profile):
        from oak_core.supervisor import profiles as _p
        return _p.read_copy(profile)

    def copy_update(self, profile, updates):
        from oak_core.supervisor import profiles as _p
        return _p.update_copy(profile, updates)

    def sltp_get(self, profile):
        from oak_core.supervisor import profiles as _p
        return _p.read_sltp(profile)

    def sltp_update(self, profile, updates):
        from oak_core.supervisor import profiles as _p
        return _p.update_sltp(profile, updates)

    def pending(self, profile):
        from oak_core.supervisor import pending as _pending
        return _pending.summary(profile)

    def pending_delete(self, profile, item_id):
        from oak_core.supervisor import pending as _pending
        return _pending.delete_item(profile, item_id)

    def pending_clear_done(self, profile):
        from oak_core.supervisor import pending as _pending
        return _pending.clear_done(profile)

    def diagnostics(self, selected="", query="", level="ALL"):
        from oak_core.supervisor import diagnostics as _diag
        return _diag.summary(selected=selected, query=query, level=level)

    def logs_tail(self, lines=200, query="", level="ALL"):
        from oak_core.supervisor import diagnostics as _diag
        return _diag.tail(lines=int(lines), query=query, level=level)

    def export_bundle(self):
        from oak_core.supervisor import diagnostics as _diag
        return _diag.export_bundle()

    def settings_get(self):
        from oak_core.supervisor import settings as _settings
        return _settings.public_settings()

    def settings_update(self, updates):
        from oak_core.supervisor import settings as _settings
        return _settings.update_settings(updates)


# ── Dashboard Bridge: expose DashboardBackend to QML via singleton ──

class QmlDashboardBridge(QObject):
    """Expose the read-only Dashboard data to QML (singleton ``DashApi``)."""

    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._sensitive = _sensitive_keys()

    def _redact(self, payload):
        if isinstance(payload, dict):
            return {k: self._redact(v) for k, v in payload.items() if k not in self._sensitive}
        if isinstance(payload, list):
            return [self._redact(v) for v in payload]
        return payload

    @Slot(result=dict)
    def overview(self):
        """Aggregate dashboard payload. Per-field failure tolerance:
        each source is fetched independently; a failing source yields None
        (or []) plus a warning entry; ok=False only when every source failed.
        Never raises to QML."""
        result = {"ok": True, "warnings": [], "handshake": None, "health": None,
                  "profiles": [], "services": [], "orders": None, "logs": None}

        def _field(name, fn):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                result["warnings"].append(f"{name}: {exc}")
                return None

        hs = _field("handshake", self._backend.handshake)
        hth = _field("health", self._backend.health)
        prof = _field("profiles", self._backend.profiles)
        svc = _field("services", self._backend.services)
        ords = _field("orders", self._backend.orders)
        logs = _field("logs", lambda: self._backend.logs(200))

        if hs is not None:
            result["handshake"] = hs
        if hth is not None:
            result["health"] = hth
        if isinstance(prof, list):
            result["profiles"] = self._redact(prof)
        if isinstance(svc, list):
            result["services"] = svc
        if ords is not None:
            result["orders"] = ords
        if logs is not None:
            result["logs"] = logs
        failed = sum(1 for f in (hs, hth, prof, svc, ords, logs) if f is None)
        result["ok"] = failed < 6
        return result


# ── Shell Bridge: expose ShellBackend to QML via singleton ──

class QmlShellBridge(QObject):
    """Expose the shared ShellBackend to QML (singleton ``ShellApi``).

    Every method catches exceptions and returns a dict with an ``ok`` flag so
    QML never has to handle QML-JS exceptions.  Sensitive keys are stripped
    from every payload (defense in depth on top of the backend redaction).
    """

    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._sensitive = _sensitive_keys()

    def _redact(self, payload):
        if isinstance(payload, dict):
            return {k: self._redact(v) for k, v in payload.items() if k not in self._sensitive}
        if isinstance(payload, list):
            return [self._redact(v) for v in payload]
        return payload

    def _call(self, fn, *args, **kwargs):
        try:
            return {"ok": True, "result": self._redact(fn(*args, **kwargs))}
        except Exception as exc:  # noqa: BLE001 — surfaced to QML as error dict
            return {"ok": False, "error": str(exc)}

    @Slot(result=dict)
    def services(self):
        return self._call(self._backend.services)

    @Slot(str, str, bool, result=dict)
    def service_start(self, key, profile, confirm):
        return self._call(self._backend.service_start, str(key), str(profile), bool(confirm))

    @Slot(str, result=dict)
    def service_stop(self, key):
        return self._call(self._backend.service_stop, str(key))

    @Slot(result=dict)
    def screener(self):
        try:
            lst = self._backend.screener()
            return {"ok": True, "stocks": self._redact(lst)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    @Slot(int, result=dict)
    def run_filter(self, limit):
        return self._call(self._backend.run_filter, int(limit))

    @Slot(str, result=dict)
    def copy_get(self, profile):
        return self._call(self._backend.copy_get, str(profile))

    @Slot(str, str, result=dict)
    def copy_update(self, profile, updates_json):
        import json as _json
        try:
            updates = _json.loads(updates_json or "{}")
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        return self._call(self._backend.copy_update, str(profile), updates)

    @Slot(str, result=dict)
    def sltp_get(self, profile):
        return self._call(self._backend.sltp_get, str(profile))

    @Slot(str, str, result=dict)
    def sltp_update(self, profile, updates_json):
        import json as _json
        try:
            updates = _json.loads(updates_json or "{}")
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        return self._call(self._backend.sltp_update, str(profile), updates)

    @Slot(str, result=dict)
    def pending(self, profile):
        return self._call(self._backend.pending, str(profile))

    @Slot(str, str, result=dict)
    def pending_delete(self, profile, item_id):
        return self._call(self._backend.pending_delete, str(profile), str(item_id))

    @Slot(str, result=dict)
    def pending_clear_done(self, profile):
        return self._call(self._backend.pending_clear_done, str(profile))

    @Slot(result=dict)
    def diagnostics(self):
        try:
            result = self._backend.diagnostics()
            return {"ok": True, "result": self._redact(result)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    @Slot(int, str, str, result=dict)
    def logs_tail(self, lines, query, level):
        return self._call(self._backend.logs_tail, int(lines), str(query), str(level))

    @Slot(result=dict)
    def export_bundle(self):
        return self._call(self._backend.export_bundle)

    @Slot(result=dict)
    def settings_get(self):
        return self._call(self._backend.settings_get)

    @Slot(str, result=dict)
    def settings_update(self, updates_json):
        import json as _json
        try:
            updates = _json.loads(updates_json or "{}")
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        return self._call(self._backend.settings_update, updates)


# ── Singleton registration (ONCE, at module level) ──
# qmlRegisterSingletonType is NOT idempotent in PySide6 6.11+; calling it
# a second time for the same module corrupts subsequent QQuickWidget engines.
# We register once and use a mutable ref holder so create_engine() can swap
# the manager underneath.

_bridge_ref: list = [None]  # mutable container captured by the callback


def _bridge_factory(engine):
    """QML engine callback — returns the current bridge singleton."""
    return _bridge_ref[0]


from PySide6.QtQml import qmlRegisterSingletonType as _reg  # noqa: E402

_reg(QmlProfileBridge, "QmlApi", 1, 0, "Api", _bridge_factory)

_dash_ref: list = [None]


def _dash_factory(engine):
    """QML engine callback — returns the current dashboard bridge singleton."""
    return _dash_ref[0]


_reg(QmlDashboardBridge, "QmlApi", 1, 0, "DashApi", _dash_factory)

_shell_ref: list = [None]


def _shell_factory(engine):
    """QML engine callback — returns the current shell bridge singleton."""
    return _shell_ref[0]


_reg(QmlShellBridge, "QmlApi", 1, 0, "ShellApi", _shell_factory)


# ── Engine factory ──

def create_engine(profile_manager=None, dashboard_backend=None, shell_backend=None):
    """Create a QApplication + QQuickWidget loaded with the QML shell.

    Parameters
    ----------
    profile_manager:
        A ``ProfileManager`` instance (or ``FakeManager`` in tests).
        When *None* the real ``ProfileManager`` is imported and created.
    dashboard_backend:
        A ``DashboardBackend`` instance (or ``FakeDashboardBackend`` in tests).
        When *None* a real ``DashboardBackend`` wrapping *profile_manager*
        is created.
    shell_backend:
        A ``ShellBackend`` instance (or fake in tests).
        When *None* a real ``ShellBackend`` is created (module functions,
        no manager needed).

    Returns ``(app, widget)`` where *app* may already exist (singleton
    QApplication) and *widget* is a ``QQuickWidget`` ready for ``show()``
    or offscreen ``grab()``.
    """
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtQuickWidgets import QQuickWidget
    from PySide6.QtWidgets import QApplication

    from oak_core.supervisor.profiles import ProfileManager

    # (a) QApplication — must exist before QObject construction.
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # Pin the application font so QML text metrics are deterministic whether
    # this app is created fresh or reuses a shared QApplication singleton
    # (QML Text defaults its family from the application font).
    app.setFont(QFont("Segoe UI", 9))

    # (b) Manager + bridge — QObject construction (needs QApplication).
    manager = profile_manager if profile_manager is not None else ProfileManager()
    bridge = QmlProfileBridge(manager)
    _bridge_ref[0] = bridge   # swap into the singleton callback's ref

    # (c) Dashboard backend + bridge.
    backend = dashboard_backend if dashboard_backend is not None else DashboardBackend(manager)
    dash = QmlDashboardBridge(backend)
    _dash_ref[0] = dash       # swap into the dashboard singleton callback's ref

    # (d) Shell backend + bridge.
    s_backend = shell_backend if shell_backend is not None else ShellBackend()
    shell = QmlShellBridge(s_backend)
    _shell_ref[0] = shell     # swap into the shell singleton callback's ref

    # (e) QQuickWidget — engine created here inherits the QmlApi singletons
    #     registered at module import time.
    widget = QQuickWidget()
    widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
    widget.profilesApi = bridge   # strong ref + test access
    widget.dashboardApi = dash    # strong ref + test access
    widget.shellApi = shell       # strong ref + test access

    # ── QML import path (for QmlPages module etc.) ──
    engine = widget.engine()
    engine.addImportPath(str(QML_DIR))

    # ── Load main.qml ──
    qml_file = QML_DIR / "main.qml"
    widget.setSource(QUrl.fromLocalFile(str(qml_file)))

    if widget.status() != QQuickWidget.Ready:
        for err in widget.errors():
            print(f"QML Error: {err.toString()}", file=sys.stderr)
        sys.exit(1)

    widget.resize(1240, 780)
    widget.setWindowTitle("OAK Manager — Native Qt")

    # Window/taskbar icon (mirrors oak_qt_shell.apply_window_icon).
    icon_path = app_icon_path()
    if icon_path is not None:
        widget.setWindowIcon(QIcon(str(icon_path)))

    return app, widget


def main() -> None:
    """Launch the QML shell (visible window)."""
    app, widget = create_engine()
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
