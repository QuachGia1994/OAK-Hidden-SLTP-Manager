import base64
import json
import sys
import threading
import time
import types
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import app

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class FakeContext:
    @classmethod
    def from_dict(cls, settings):
        return settings


class ReaderFactory:
    state = "Trusted"
    manifest = True

    def __init__(self, mime, stream, context=None):
        self.mime = mime
        self.context = context

    def json(self):
        payload = {"active_manifest": None, "manifests": {}}
        if self.manifest:
            payload = {
                "active_manifest": "urn:test",
                "manifests": {
                    "urn:test": {
                        "claim_generator": "fixture-generator",
                        "assertions": [{
                            "label": "c2pa.actions",
                            "data": {"actions": [{"digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture"}]},
                        }],
                    }
                },
            }
        return json.dumps(payload)

    def get_validation_state(self):
        return self.state

    def get_validation_results(self):
        return [{"code": "fixture"}]


class MediaForensicsTests(unittest.TestCase):
    def fake_c2pa_module(self):
        return types.SimpleNamespace(Context=FakeContext, Reader=ReaderFactory)

    def start_server(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_validates_real_png_and_rejects_trailing_polyglot(self):
        self.assertEqual(app._validate_image(PNG_1X1, "image/png"), (1, 1))
        with self.assertRaises(ValueError):
            app._validate_image(PNG_1X1 + b"<script>alert(1)</script>", "image/png")

    def test_no_trust_anchors_never_turns_sdk_invalid_into_invalid_signature(self):
        ReaderFactory.state = "Invalid"
        ReaderFactory.manifest = True
        with patch.dict(sys.modules, {"c2pa": self.fake_c2pa_module()}), patch.object(app, "C2PA_TRUST_ANCHORS_PEM", ""):
            result = app._c2pa(PNG_1X1 + b"c2pa", "image/png")
        self.assertEqual(result["state"], "present_unverified")
        self.assertEqual(result["trust_chain"], "not_configured")

    def test_configured_trust_distinguishes_verified_and_invalid(self):
        ReaderFactory.manifest = True
        with patch.dict(sys.modules, {"c2pa": self.fake_c2pa_module()}), patch.object(app, "C2PA_TRUST_ANCHORS_PEM", "TEST-ANCHOR"):
            ReaderFactory.state = "Trusted"
            verified = app._c2pa(PNG_1X1, "image/png")
            ReaderFactory.state = "Invalid"
            invalid = app._c2pa(PNG_1X1, "image/png")
        self.assertEqual((verified["state"], verified["trust_chain"]), ("verified", "trusted"))
        self.assertEqual((invalid["state"], invalid["trust_chain"]), ("invalid", "failed"))

    def test_absent_manifest_is_not_detected(self):
        ReaderFactory.manifest = False
        ReaderFactory.state = "Trusted"
        with patch.dict(sys.modules, {"c2pa": self.fake_c2pa_module()}), patch.object(app, "C2PA_TRUST_ANCHORS_PEM", "TEST-ANCHOR"):
            result = app._c2pa(PNG_1X1, "image/png")
        self.assertEqual(result["state"], "not_detected")
        self.assertEqual(result["trust_chain"], "not_applicable")

    def test_parser_error_preserves_only_marker_presence(self):
        broken = types.SimpleNamespace(Context=FakeContext, Reader=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
        with patch.dict(sys.modules, {"c2pa": broken}):
            present = app._c2pa(PNG_1X1 + b"content credentials", "image/png")
            absent = app._c2pa(PNG_1X1, "image/png")
        self.assertEqual(present["state"], "present_unverified")
        self.assertEqual(absent["state"], "verification_error")

    def test_detector_runtime_missing_is_explicit_unavailable(self):
        with patch.object(app, "UNIVFD_REPO", ""), patch.object(app, "UNIVFD_CKPT", ""), patch.object(app, "_model", None), patch.object(app, "_transform", None), patch.object(app, "_model_error", None):
            result = app._detect_univfd(PNG_1X1)
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("raw_score", result)

    def test_windows_runtime_defaults_to_loopback_cpu(self):
        self.assertEqual(app.HOST, "127.0.0.1")
        self.assertEqual(app.DEVICE, "cpu")

    def test_version_reports_cpu_when_model_is_loaded_on_cpu(self):
        server, thread = self.start_server()
        try:
            host, port = server.server_address
            with patch.object(app, "_model", (object(), "cpu")):
                with urllib.request.urlopen(f"http://{host}:{port}/version", timeout=2) as response:
                    version = json.load(response)
            self.assertEqual(version["model_device"], "cpu")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_detector_timeout_is_explicit_and_bounded(self):
        def slow_detector(_image):
            time.sleep(0.08)
            return {"detector_id": "slow", "version": "1", "status": "ok", "raw_score": 0.9}

        with patch.object(app, "DETECTOR_REGISTRY", {"slow": slow_detector}), patch.object(app, "ENABLED_DETECTOR_IDS", ("slow",)), patch.object(app, "DETECTOR_TIMEOUT_SECONDS", 0.01), patch.object(app, "_c2pa", lambda *_: {"state": "not_detected", "trust_chain": "not_applicable"}):
            started = time.monotonic()
            result = app.analyze(PNG_1X1, "image/png")
        self.assertLess(time.monotonic() - started, 0.25)
        self.assertEqual(result["detectors"][0]["status"], "failed")
        self.assertEqual(result["detectors"][0]["reason"], "detector_timeout")

    def test_health_and_version_startup_smoke(self):
        server, thread = self.start_server()
        try:
            host, port = server.server_address
            with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2) as response:
                health = json.load(response)
            with urllib.request.urlopen(f"http://{host}:{port}/version", timeout=2) as response:
                version = json.load(response)
            self.assertTrue(health["ok"])
            self.assertIn(health["runtime"], {"ready", "degraded"})
            self.assertEqual(version["service"], "oak-media-forensics")
            self.assertEqual(version["version"], "3")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_http_auth_rejects_missing_token_and_accepts_controlled_request(self):
        server, thread = self.start_server()
        try:
            host, port = server.server_address
            url = f"http://{host}:{port}/v1/detect/image"
            unauthorized = urllib.request.Request(url, data=PNG_1X1, headers={"Content-Type": "image/png"}, method="POST")
            with patch.object(app, "TOKEN", "test-secret"):
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(unauthorized, timeout=2)
                self.assertEqual(denied.exception.code, 401)

                controlled = {
                    "ok": True,
                    "schema_version": 2,
                    "technical": {"width": 1, "height": 1},
                    "c2pa": {"state": "not_detected", "trust_chain": "not_applicable"},
                    "detectors": [{"detector_id": "universalfakedetect", "version": "cvpr2023-clip-vitl14", "status": "unavailable", "reason": "runtime_not_configured"}],
                    "latency_ms": 1,
                }
                authorized = urllib.request.Request(url, data=PNG_1X1, headers={"Content-Type": "image/png", "Authorization": "Bearer test-secret"}, method="POST")
                with patch.object(app, "analyze", lambda *_: controlled):
                    with urllib.request.urlopen(authorized, timeout=2) as response:
                        payload = json.load(response)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["schema_version"], 2)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_request_concurrency_is_fail_fast(self):
        server, thread = self.start_server()
        started = threading.Event()
        release = threading.Event()
        first_done = threading.Event()
        result_holder = []

        def blocking_analyze(*_):
            started.set()
            release.wait(timeout=2)
            return {"ok": True, "schema_version": 2, "technical": {"width": 1, "height": 1}, "c2pa": {}, "detectors": [], "latency_ms": 1}

        try:
            host, port = server.server_address
            url = f"http://{host}:{port}/v1/detect/image"
            headers = {"Content-Type": "image/png", "Authorization": "Bearer test-secret"}

            def first_request():
                try:
                    req = urllib.request.Request(url, data=PNG_1X1, headers=headers, method="POST")
                    with urllib.request.urlopen(req, timeout=3) as response:
                        result_holder.append(response.status)
                finally:
                    first_done.set()

            with patch.object(app, "TOKEN", "test-secret"), patch.object(app, "_capacity", threading.BoundedSemaphore(1)), patch.object(app, "analyze", blocking_analyze):
                worker = threading.Thread(target=first_request, daemon=True)
                worker.start()
                self.assertTrue(started.wait(timeout=1))
                second = urllib.request.Request(url, data=PNG_1X1, headers=headers, method="POST")
                with self.assertRaises(urllib.error.HTTPError) as busy:
                    urllib.request.urlopen(second, timeout=2)
                self.assertEqual(busy.exception.code, 503)
                release.set()
                self.assertTrue(first_done.wait(timeout=2))
                worker.join(timeout=2)
                self.assertEqual(result_holder, [200])
        finally:
            release.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
