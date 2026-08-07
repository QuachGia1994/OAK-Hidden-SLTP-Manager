# -*- coding: utf-8 -*-
"""Tests for the oak-core JSONL IPC protocol (§3, §11)."""
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_python_root = Path(__file__).resolve().parents[1]
if str(_python_root) not in sys.path:
    sys.path.insert(0, str(_python_root))

from oak_core.ipc.protocol import (  # noqa: E402
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
from oak_core.ipc.server import IpcServer  # noqa: E402
from oak_core.supervisor import SupervisorApp  # noqa: E402
from oak_core.version import APP_NAME, APP_VERSION, PROTOCOL_VERSION  # noqa: E402


class TestProtocolParse(unittest.TestCase):
    def test_parse_valid_request(self):
        req = parse_line('{"v":1,"id":"req-1","method":"app.health","params":{"a":1}}')
        self.assertEqual(req.id, "req-1")
        self.assertEqual(req.method, "app.health")
        self.assertEqual(req.params, {"a": 1})

    def test_parse_rejects_wrong_version(self):
        with self.assertRaises(ProtocolError):
            parse_line('{"v":2,"id":"x","method":"app.health"}')

    def test_parse_rejects_missing_method_or_id(self):
        with self.assertRaises(ProtocolError):
            parse_line('{"v":1,"method":"app.health"}')
        with self.assertRaises(ProtocolError):
            parse_line('{"v":1,"id":"x"}')

    def test_parse_rejects_non_object_payload(self):
        with self.assertRaises(ProtocolError):
            parse_line('"just a string"')
        with self.assertRaises(ProtocolError):
            parse_line("{not json")

    def test_parse_defaults_params_to_empty(self):
        req = parse_line('{"v":1,"id":"x","method":"m"}')
        self.assertEqual(req.params, {})

    def test_parse_params_must_be_object(self):
        with self.assertRaises(ProtocolError):
            parse_line('{"v":1,"id":"x","method":"m","params":[1,2]}')


class TestProtocolSerialize(unittest.TestCase):
    def test_response_ok_shape(self):
        line = response_line(Response(id="r1", ok=True, result={"x": 1}))
        payload = json.loads(line)
        self.assertEqual(payload["v"], 1)
        self.assertEqual(payload["id"], "r1")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["result"], {"x": 1})
        self.assertNotIn("error", payload)

    def test_response_error_shape(self):
        line = response_line(Response(
            id="r1", ok=False, error=error_payload("METHOD_NOT_FOUND", "nope"),
        ))
        payload = json.loads(line)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "METHOD_NOT_FOUND")
        self.assertEqual(payload["error"]["message"], "nope")

    def test_event_shape_with_sequence(self):
        line = event_line(Event(name="position.updated", data={"count": 2}, sequence=7))
        payload = json.loads(line)
        self.assertEqual(payload["event"], "position.updated")
        self.assertEqual(payload["sequence"], 7)
        self.assertEqual(payload["data"], {"count": 2})
        self.assertEqual(payload["v"], 1)

    def test_sequence_counter_monotonic(self):
        counter = SequenceCounter()
        self.assertEqual(counter.next(), 1)
        self.assertEqual(counter.next(), 2)


class TestIpcServer(unittest.TestCase):
    def _make_server(self, input_text):
        stdin = io.StringIO(input_text)
        stdout = io.StringIO()
        stderr = io.StringIO()
        server = IpcServer(stdin=stdin, stdout=stdout, stderr=stderr)
        return server, stdout

    def _responses(self, stdout):
        return [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]

    def test_handshake_returns_identity(self):
        server, stdout = self._make_server('{"v":1,"id":"h1","method":"app.handshake"}\n')
        SupervisorApp(server=server).run()
        responses = self._responses(stdout)
        self.assertEqual(len(responses), 1)
        self.assertTrue(responses[0]["ok"])
        self.assertEqual(responses[0]["id"], "h1")
        result = responses[0]["result"]
        self.assertEqual(result["app"], APP_NAME)
        self.assertEqual(result["version"], APP_VERSION)
        self.assertEqual(result["protocol"], PROTOCOL_VERSION)
        self.assertEqual(result["role"], "supervisor")

    def test_health_ok(self):
        server, stdout = self._make_server('{"v":1,"id":"h","method":"app.health"}\n')
        SupervisorApp(server=server).run()
        responses = self._responses(stdout)
        self.assertEqual(responses[0]["result"]["status"], "ok")

    def test_shutdown_acks_and_stops_loop(self):
        # Two requests: shutdown, then one more — the second must be refused.
        text = (
            '{"v":1,"id":"s1","method":"app.shutdown"}\n'
            '{"v":1,"id":"s2","method":"app.health"}\n'
        )
        server, stdout = self._make_server(text)
        SupervisorApp(server=server).run()
        responses = self._responses(stdout)
        self.assertEqual(len(responses), 2)
        self.assertTrue(responses[0]["ok"])
        self.assertTrue(responses[0]["result"]["ack"])
        self.assertFalse(responses[1]["ok"])
        self.assertEqual(responses[1]["error"]["code"], "SHUTTING_DOWN")

    def test_unknown_method_returns_error(self):
        server, stdout = self._make_server('{"v":1,"id":"u","method":"nope.what"}\n')
        SupervisorApp(server=server).run()
        responses = self._responses(stdout)
        self.assertFalse(responses[0]["ok"])
        self.assertEqual(responses[0]["error"]["code"], "METHOD_NOT_FOUND")

    def test_bad_line_keeps_loop_alive(self):
        text = (
            "this is not json\n"
            '{"v":1,"id":"ok","method":"app.health"}\n'
        )
        server, stdout = self._make_server(text)
        SupervisorApp(server=server).run()
        responses = self._responses(stdout)
        self.assertEqual(len(responses), 2)
        self.assertEqual(responses[0]["error"]["code"], "BAD_REQUEST")
        self.assertTrue(responses[1]["ok"])

    def test_emit_event_writes_sequence(self):
        server, stdout = self._make_server("")
        server.emit_event("worker.started", {"pid": 42})
        events = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "worker.started")
        self.assertEqual(events[0]["sequence"], 1)

    def test_logs_tail_is_bounded(self):
        server, stdout = self._make_server(
            '{"v":1,"id":"l","method":"logs.tail","params":{"lines":50}}\n'
        )
        SupervisorApp(server=server).run()
        responses = self._responses(stdout)
        self.assertTrue(responses[0]["ok"])
        result = responses[0]["result"]
        self.assertLessEqual(len(result["lines"]), 50)
        self.assertEqual(result["requested"], 50)


class TestHealthUptime(unittest.TestCase):
    def test_uptime_is_dynamic_and_formatted(self):
        from oak_core import supervisor as sup

        app = SupervisorApp()
        # Patch the module's monotonic clock so elapsed time is deterministic
        # and no real sleeping is required.
        with mock.patch.object(sup, "_monotonic_now",
                               return_value=app._monotonic_start + 0):
            first = app._on_health(None)["uptime"]
        with mock.patch.object(sup, "_monotonic_now",
                               return_value=app._monotonic_start + 83):
            second = app._on_health(None)["uptime"]
        with mock.patch.object(sup, "_monotonic_now",
                               return_value=app._monotonic_start + 93784):
            third = app._on_health(None)["uptime"]

        self.assertEqual(first, "00:00:00")
        self.assertEqual(second, "00:01:23")
        self.assertEqual(third, "1d 02:03:04")
        # The value must change over time, not stay static.
        self.assertNotEqual(first, second)
        self.assertNotEqual(second, third)

    def test_handshake_started_at_unchanged_and_valid(self):
        from datetime import datetime

        app = SupervisorApp()
        handshake = app._on_handshake(None)
        # The handshake timestamp stays the original ISO value.
        self.assertEqual(handshake["started_at"], app._started_at)
        # It must remain a parseable ISO timestamp (not the uptime string).
        parsed = datetime.fromisoformat(
            handshake["started_at"].replace("Z", "+00:00")
        )
        self.assertIsNotNone(parsed)
        self.assertNotEqual(app._on_health(None)["uptime"], handshake["started_at"])


if __name__ == "__main__":
    unittest.main()
