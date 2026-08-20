"""Regression tests for ownership-safe cross-process file locking."""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from domain.file_lock import FileLock


class FileLockTests(unittest.TestCase):
    def test_old_mtime_does_not_let_second_owner_steal_live_lock(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = os.path.join(temporary_directory, "runtime.lock")
            with FileLock(path, timeout=0.2) as first:
                self.assertIsNotNone(first)
                old = time.time() - 3600
                os.utime(path, (old, old))
                with FileLock(path, timeout=0.05) as second:
                    self.assertIsNone(second)

    def test_lock_excludes_a_second_process(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = os.path.join(temporary_directory, "runtime.lock")
            code = f'''\nimport sys\nimport time\nsys.path.insert(0, {str(ROOT)!r})\nfrom domain.file_lock import FileLock\nwith FileLock({path!r}, timeout=0.2) as lock:\n    if lock is None:\n        raise SystemExit(2)\n    print("locked", flush=True)\n    time.sleep(0.4)\n'''
            child = subprocess.Popen(
                [sys.executable, "-c", code],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                self.assertEqual(child.stdout.readline().strip(), "locked")
                with FileLock(path, timeout=0.05) as second:
                    self.assertIsNone(second)
            finally:
                child.wait(timeout=2)
            self.assertEqual(child.returncode, 0, child.stderr.read())

    def test_lock_can_be_reacquired_after_owner_releases_without_unlinking_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = os.path.join(temporary_directory, "runtime.lock")
            with FileLock(path, timeout=0.2) as first:
                self.assertIsNotNone(first)
            self.assertTrue(os.path.exists(path))
            with FileLock(path, timeout=0.2) as second:
                self.assertIsNotNone(second)

    def test_lock_creation_failure_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_parent = os.path.join(temporary_directory, "missing", "runtime.lock")
            with FileLock(missing_parent, timeout=0.01) as acquired:
                self.assertIsNone(acquired)


if __name__ == "__main__":
    unittest.main()
