"""Regression tests for atomic JSON persistence on Windows."""

import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

from domain import json_io


class AtomicJsonPersistenceTests(unittest.TestCase):
    def test_retries_transient_windows_access_denied(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = os.path.join(temporary_directory, "scheduled_close_demo.json")
            real_replace = os.replace
            attempts = []

            def transient_access_denied(source, destination):
                attempts.append(source)
                if len(attempts) < 3:
                    raise PermissionError(5, "Access is denied")
                return real_replace(source, destination)

            with patch("domain.json_io.os.replace", side_effect=transient_access_denied), patch(
                "domain.json_io.time.sleep"
            ):
                json_io.save_json(target, [{"id": 42}])

            self.assertEqual(len(attempts), 3)
            with open(target, "r", encoding="utf-8") as saved_file:
                self.assertEqual(json.load(saved_file), [{"id": 42}])

    def test_concurrent_writers_use_distinct_temporary_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = os.path.join(temporary_directory, "scheduled_close_demo.json")
            real_replace = os.replace
            replace_barrier = threading.Barrier(2)
            sources = []
            source_lock = threading.Lock()
            synchronized_sources = set()
            errors = []

            def synchronized_replace(source, destination):
                with source_lock:
                    sources.append(source)
                    first_attempt = source not in synchronized_sources
                    synchronized_sources.add(source)
                if first_attempt:
                    replace_barrier.wait(timeout=2)
                return real_replace(source, destination)

            def save(payload):
                try:
                    json_io.save_json(target, payload)
                except Exception as error:
                    errors.append(error)

            with patch("domain.json_io.os.replace", side_effect=synchronized_replace):
                writers = [
                    threading.Thread(target=save, args=([{"id": identifier}],))
                    for identifier in (1, 2)
                ]
                for writer in writers:
                    writer.start()
                for writer in writers:
                    writer.join(timeout=3)

            self.assertFalse(errors)
            self.assertEqual(len(set(sources)), 2)
            with open(target, "r", encoding="utf-8") as saved_file:
                self.assertIn(json.load(saved_file), ([{"id": 1}], [{"id": 2}]))


if __name__ == "__main__":
    unittest.main()
