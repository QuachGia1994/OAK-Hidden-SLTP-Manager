# -*- coding: utf-8 -*-
"""Supervisor mode of oak-core — Phase 1 (Edit prompt.txt §9).

Phase 1 scope: Tauri shell + sidecar handshake + health + log streaming +
clean shutdown.  No business logic is moved here yet (acceptance #16:
"Không thay đổi business logic trong Phase 1"); profile workers, MT5
integration and the trade-audit stack arrive in later phases.
"""
from ..ipc.protocol import error_payload
from ..ipc.server import IpcServer
from ..version import APP_NAME, APP_VERSION, PROTOCOL_VERSION


class SupervisorApp:
    """Handles the Phase-1 control surface of the supervisor sidecar."""

    def __init__(self, *, server: IpcServer | None = None, started_at=None):
        self._server = server if server is not None else IpcServer()
        from datetime import datetime, timezone
        self._started_at = started_at or datetime.now(timezone.utc).isoformat()
        self._healthy = True
        self._register()

    def _register(self) -> None:
        self._server.register("app.handshake", self._on_handshake)
        self._server.register("app.health", self._on_health)
        self._server.register("app.shutdown", self._on_shutdown)
        self._server.register("logs.tail", self._on_logs_tail)

    # ------------------------------------------------------------------ #
    # Handlers (return dict -> ok response; raise -> error response)
    # ------------------------------------------------------------------ #
    def _on_handshake(self, request) -> dict:
        return {
            "app": APP_NAME,
            "version": APP_VERSION,
            "protocol": PROTOCOL_VERSION,
            "role": "supervisor",
            "started_at": self._started_at,
        }

    def _on_health(self, request) -> dict:
        return {
            "status": "ok" if self._healthy else "degraded",
            "uptime": self._started_at,
            "workers": [],
            "protocol": PROTOCOL_VERSION,
        }

    def _on_shutdown(self, request) -> dict:
        self._healthy = False
        # Ask the loop to stop after this response is flushed.
        self._server.request_shutdown()
        return {"ack": True}

    def _on_logs_tail(self, request) -> dict:
        # Phase 1: no persisted log ring yet — return empty tail.  The Rust
        # shell streams stderr directly; this command is a placeholder for the
        # future in-app log viewer.
        lines = request.params.get("lines", 100)
        return {"lines": [], "truncated": False, "requested": int(lines)}

    # ------------------------------------------------------------------ #
    # Run
    # ------------------------------------------------------------------ #
    def run(self, *, max_lines: int | None = None) -> int:
        return self._server.run(max_lines=max_lines)
