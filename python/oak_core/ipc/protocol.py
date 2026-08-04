# -*- coding: utf-8 -*-
"""JSON Lines IPC protocol for oak-core (§3 of the refactor plan).

Wire contract (stdout carries protocol JSON only; stderr carries logs):

Request:
    {"v":1,"id":"req-101","method":"profile.start","params":{...}}

Response:
    {"v":1,"id":"req-101","ok":true,"result":{...}}

Error:
    {"v":1,"id":"req-101","ok":false,"error":{"code":"...","message":"...","details":{}}}

Event:
    {"v":1,"event":"position.updated","sequence":123,"data":{...}}

Events carry a monotonically increasing per-process sequence number so React
can detect dropped events.
"""
import json
import threading
from dataclasses import dataclass, field
from typing import Any

from ..version import PROTOCOL_VERSION


@dataclass
class Request:
    id: str
    method: str
    params: dict = field(default_factory=dict)
    v: int = PROTOCOL_VERSION


@dataclass
class Response:
    id: str
    ok: bool
    result: dict = field(default_factory=dict)
    error: dict | None = None
    v: int = PROTOCOL_VERSION


@dataclass
class Event:
    name: str
    data: dict = field(default_factory=dict)
    sequence: int = 0
    v: int = PROTOCOL_VERSION


class ProtocolError(Exception):
    """Raised for malformed wire messages."""


def parse_line(line: str) -> Request:
    """Parse one JSONL request line. Raises ProtocolError on malformed input."""
    if not line or not line.strip():
        raise ProtocolError("empty line")
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid json: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("payload must be an object")
    if payload.get("v") != PROTOCOL_VERSION:
        raise ProtocolError(
            f"unsupported protocol version {payload.get('v')!r} (expected {PROTOCOL_VERSION})"
        )
    method = payload.get("method")
    req_id = payload.get("id")
    if not isinstance(method, str) or not method:
        raise ProtocolError("missing method")
    if not isinstance(req_id, str) or not req_id:
        raise ProtocolError("missing id")
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        raise ProtocolError("params must be an object")
    return Request(id=req_id, method=method, params=params, v=payload.get("v"))


def response_line(resp: Response) -> str:
    """Serialize a Response to one JSONL line."""
    payload: dict[str, Any] = {"v": resp.v, "id": resp.id, "ok": resp.ok}
    if resp.ok:
        payload["result"] = resp.result
    else:
        payload["error"] = resp.error or {
            "code": "UNKNOWN_ERROR",
            "message": "unknown error",
            "details": {},
        }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def event_line(event: Event) -> str:
    """Serialize an Event to one JSONL line."""
    payload: dict[str, Any] = {
        "v": event.v,
        "event": event.name,
        "sequence": event.sequence,
        "data": event.data,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def error_payload(code: str, message: str, details: dict | None = None) -> dict:
    return {"code": code, "message": message, "details": details or {}}


class SequenceCounter:
    """Thread-safe monotonic event sequence counter (§3)."""

    def __init__(self, start: int = 0):
        self._value = start
        self._lock = threading.Lock()

    def next(self) -> int:
        with self._lock:
            self._value += 1
            return self._value
