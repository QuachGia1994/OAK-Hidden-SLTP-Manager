# -*- coding: utf-8 -*-
"""Debug bundle secret redaction tests."""
import json
import os
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.debug_bundle_service import build_debug_bundle_bytes, redact_json_obj


class TestDebugBundleRedact(unittest.TestCase):
    def test_redact_nested_token(self):
        data = {
            "dashboard_api_key": "super-secret-key-12345",
            "profiles": {"A": {"tele_token": "123:ABC", "tele_chat": "999", "path": "C:/x"}},
        }
        out = redact_json_obj(data)
        self.assertEqual(out["dashboard_api_key"], "***REDACTED***")
        self.assertEqual(out["profiles"]["A"]["tele_token"], "***REDACTED***")
        self.assertEqual(out["profiles"]["A"]["tele_chat"], "***REDACTED***")
        self.assertEqual(out["profiles"]["A"]["path"], "C:/x")

    def test_bundle_writes_redacted_not_raw(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = {"dashboard_api_key": "sekrit", "url": "https://x"}
            with open(os.path.join(td, "config.json"), "w", encoding="utf-8") as f:
                json.dump(cfg, f)
            raw = build_debug_bundle_bytes(td, include_account_raw=False)
            with zipfile.ZipFile(__import__("io").BytesIO(raw)) as zf:
                names = zf.namelist()
                self.assertIn("config.redacted.json", names)
                self.assertNotIn("config.json", names)
                body = zf.read("config.redacted.json").decode("utf-8")
                self.assertIn("***REDACTED***", body)
                self.assertNotIn("sekrit", body)


if __name__ == "__main__":
    unittest.main()
