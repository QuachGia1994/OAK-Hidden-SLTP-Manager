import base64
import json
import sys
import threading
import types
import unittest
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

    def test_health_and_version_startup_smoke(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2) as response:
                health = json.load(response)
            with urllib.request.urlopen(f"http://{host}:{port}/version", timeout=2) as response:
                version = json.load(response)
            self.assertTrue(health["ok"])
            self.assertIn(health["detector"], {"ready", "unavailable"})
            self.assertEqual(version["service"], "oak-media-forensics")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
