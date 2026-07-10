# -*- coding: utf-8 -*-
"""Debug bundle secret redaction tests."""
import json
import os
import sys
import tempfile
import unittest
import zipfile
import io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.debug_bundle_service import (
    build_debug_bundle_bytes,
    redact_json_obj,
    redact_log_text,
)


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

    def test_redact_log_pii(self):
        raw = (
            "Connected: Phong Quach Kim (7398029) | Broker: Raw Trading Ltd\n"
            r"path=C:\Users\PHONGQK\Documents\trae_projects\ROBOT SLTP\app.py" + "\n"
            "token=123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxx\n"
            "server | #7398029\n"
        )
        out = redact_log_text(raw)
        self.assertNotIn("PHONGQK", out)
        self.assertNotIn("7398029", out)
        self.assertNotIn("Phong Quach", out)
        self.assertNotIn("123456789:AAH", out)
        self.assertIn("***USER***", out)
        self.assertTrue(
            "***REDACTED***" in out or "***REDACTED_TOKEN***" in out,
            out,
        )

    def test_bundle_writes_redacted_not_raw(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = {"dashboard_api_key": "sekrit", "url": "https://x"}
            with open(os.path.join(td, "config.json"), "w", encoding="utf-8") as f:
                json.dump(cfg, f)
            os.makedirs(os.path.join(td, "logs"), exist_ok=True)
            with open(os.path.join(td, "logs", "app.log"), "w", encoding="utf-8") as f:
                f.write("Connected: Alice (12345) | Broker: Test\n")
                f.write(r"C:\Users\Alice\secret\path" + "\n")

            raw = build_debug_bundle_bytes(td, include_account_raw=False)
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                names = zf.namelist()
                self.assertIn("config.redacted.json", names)
                self.assertNotIn("config.json", names)
                body = zf.read("config.redacted.json").decode("utf-8")
                self.assertIn("***REDACTED***", body)
                self.assertNotIn("sekrit", body)

                log_name = "logs/app.redacted.log"
                self.assertIn(log_name, names)
                log_body = zf.read(log_name).decode("utf-8")
                self.assertNotIn("Alice", log_body)
                self.assertNotIn("12345", log_body)


if __name__ == "__main__":
    unittest.main()
