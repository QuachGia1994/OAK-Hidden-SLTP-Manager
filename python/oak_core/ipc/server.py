# -*- coding: utf-8 -*-
"""JSONL server loop for oak-core.

Reads request lines from stdin, dispatches to registered handlers, writes
response lines to stdout, and lets handlers emit events (also on stdout).

stdout carries ONLY protocol JSONL; human logs go to stderr.
"""
import sys
import threading
import traceback
from typing import Any, Callable

from ..version import PROTOCOL_VERSION
from .protocol import (
    Event,
    ProtocolError,
    Request,
    Response,
    SequenceCounter,
    error_payload,
    event_line,
    parse_line,
    response_line,
)

Handler = Callable[[Request], dict]


class IpcServer:
    """Dispatches JSONL requests. Never raises out of the loop."""

    def __init__(self, *, stdin=None, stdout=None, stderr=None, log=None):
        self._stdin = stdin if stdin is not None else sys.stdin
        self._stdout = stdout if stdout is not None else sys.stdout
        self._stderr = stderr if stderr is not None else sys.stderr
        self._log = log or _default_log(self._stderr)
        self._handlers: dict[str, Handler] = {}
        self._events = SequenceCounter()
        self._write_lock = threading.Lock()
        self._shutdown_requested = False

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #
    def register(self, method: str, handler: Handler) -> None:
        self._handlers[method] = handler

    # ------------------------------------------------------------------ #
    # Output helpers
    # ------------------------------------------------------------------ #
    def emit_event(self, name: str, data: dict | None = None) -> int:
        seq = self._events.next()
        line = event_line(Event(name=name, data=data or {}, sequence=seq))
        self._write_line(line)
        return seq

    def _write_line(self, line: str) -> None:
        with self._write_lock:
            try:
                self._stdout.write(line + "\n")
                self._stdout.flush()
            except (OSError, ValueError) as exc:  # pragma: no cover - broken pipe
                self._log(f"[ipc] stdout write failed: {exc}")

    def _respond(self, resp: Response) -> None:
        self._write_line(response_line(resp))

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #
    def run(self, *, max_lines: int | None = None) -> int:
        """Process request lines until EOF or shutdown. Returns line count."""
        processed = 0
        for raw in self._stdin:
            if max_lines is not None and processed >= max_lines:
                break
            processed += 1
            line = raw.rstrip("\r\n")
            try:
                request = parse_line(line)
            except ProtocolError as exc:
                # Unparseable request — answer best-effort with the raw id if
                # we can, then keep the loop alive (never crash on bad input).
                self._log(f"[ipc] bad request line: {exc}")
                self._respond(Response(id="?", ok=False, error=error_payload(
                    "BAD_REQUEST", str(exc),
                )))
                continue

            try:
                if self._shutdown_requested:
                    self._respond(Response(id=request.id, ok=False, error=error_payload(
                        "SHUTTING_DOWN", "server is shutting down",
                    )))
                    continue
                handler = self._handlers.get(request.method)
                if handler is None:
                    self._respond(Response(id=request.id, ok=False, error=error_payload(
                        "METHOD_NOT_FOUND", f"unknown method {request.method!r}",
                    )))
                    continue
                result = handler(request)
                if result is None:
                    result = {}
                self._respond(Response(id=request.id, ok=True, result=result))
            except Exception as exc:  # noqa: BLE001 - handler isolation
                self._log(f"[ipc] handler {request.method} failed: {exc}")
                traceback.print_exc(file=self._stderr)
                self._respond(Response(id=request.id, ok=False, error=error_payload(
                    "HANDLER_ERROR", str(exc),
                )))
        return processed

    def request_shutdown(self) -> None:
        self._shutdown_requested = True


def _default_log(stderr):
    def log(message: str) -> None:
        try:
            stderr.write(message + "\n")
            stderr.flush()
        except (OSError, ValueError):  # pragma: no cover
            pass

    return log
