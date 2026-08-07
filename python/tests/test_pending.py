# -*- coding: utf-8 -*-
"""Regression tests for the Tauri-safe legacy pending-file surface."""
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from oak_core.supervisor import pending  # noqa: E402


class TestPendingSurface(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(prefix="oak-pending-")
        self.root = Path(self.tmpdir.name)
        (self.root / "profiles.json").write_text(json.dumps({"Vantage": {}}), encoding="utf-8")
        (self.root / "waiting_Vantage.json").write_text(json.dumps([
            {"symbol": "XAUUSD", "status": "waiting", "lot": "0.04"},
            {"symbol": "GBPUSD", "status": "done", "lot": "0.01"},
        ]), encoding="utf-8")
        (self.root / "pending_partials_Vantage.json").write_text(json.dumps({
            "123": {"symbol": "XAUUSD", "target_profit": 20, "close_volume": 0.01},
        }), encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _patch_root(self):
        @contextmanager
        def patched():
            with patch("oak_core.supervisor.pending._data_root", return_value=self.root), \
                 patch("oak_core.supervisor.profiles._data_root", return_value=self.root):
                yield
        return patched()

    def test_summary_returns_opaque_rows_without_absolute_paths(self):
        with self._patch_root():
            result = pending.summary("Vantage")
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["waiting"], 2)
        self.assertEqual(result["done"], 1)
        self.assertTrue(all("\\" not in item["file_name"] for item in result["items"]))
        self.assertTrue(all(len(item["id"]) == 24 for item in result["items"]))

    def test_delete_and_clear_done_reload_disk(self):
        with self._patch_root():
            rows = pending.summary("Vantage")["items"]
            target = next(item for item in rows if item["symbol"] == "XAUUSD")
            deleted = pending.delete_item("Vantage", target["id"])
            cleared = pending.clear_done("Vantage")
            remaining = pending.summary("Vantage")
        self.assertTrue(deleted["deleted"])
        self.assertEqual(cleared["cleared"], 1)
        self.assertEqual(remaining["total"], 1)
        self.assertEqual(remaining["items"][0]["kind"], "partials")

    def test_unknown_id_does_not_mutate_files(self):
        with self._patch_root():
            result = pending.delete_item("Vantage", "not-a-real-row")
            rows = pending.summary("Vantage")["items"]
        self.assertFalse(result["deleted"])
        self.assertEqual(len(rows), 3)


if __name__ == "__main__":
    unittest.main()
