# -*- coding: utf-8 -*-
"""Tests for NativeQt pending-control helper logic."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import oak_qt_shell
from oak_qt_shell import (
    clear_done_pending_data,
    mutate_pending_file,
    pending_rows,
    public_pending_item,
    remove_pending_item_from_data,
)


class TestNativeQtPendingHelpers(unittest.TestCase):
    def test_pending_rows_normalizes_dict_without_leaking_metadata(self):
        rows = pending_rows("partials", Path("pending_partials_Demo.json"), {"42": {"symbol": "XAUUSD+"}}, "dict")
        self.assertEqual(rows[0]["ticket"], "42")
        self.assertEqual(public_pending_item(rows[0]), {"kind": "partials", "ticket": "42", "symbol": "XAUUSD+"})

    def test_remove_pending_item_removes_matching_list_row(self):
        data = [
            {"symbol": "XAUUSD", "time": "07:00", "status": "waiting"},
            {"symbol": "GBPUSD", "time": "08:00", "status": "waiting"},
        ]
        item = pending_rows("entries", Path("waiting_Demo.json"), data, "list")[1]
        updated, removed = remove_pending_item_from_data(data, item)
        self.assertTrue(removed)
        self.assertEqual(updated, [data[0]])

    def test_clear_done_pending_data_keeps_waiting_rows(self):
        data = [
            {"symbol": "XAUUSD", "status": "executed"},
            {"symbol": "GBPUSD", "status": "waiting"},
            {"symbol": "GBPAUD", "status": "done"},
        ]
        updated, removed = clear_done_pending_data(data)
        self.assertEqual(removed, 2)
        self.assertEqual(updated, [{"symbol": "GBPUSD", "status": "waiting"}])

    def test_scheduled_close_mutation_reloads_and_writes_inside_shared_lock(self):
        events = []

        class RecordingLock:
            def __init__(self, path, timeout):
                events.append(("lock", path, timeout))

            def __enter__(self):
                events.append("enter")
                return self

            def __exit__(self, *_args):
                events.append("exit")

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "scheduled_close_Demo.json"

            def read_inside_lock(_path, _default):
                events.append("read")
                return [{"status": "done"}, {"status": "waiting"}]

            def write_inside_lock(_path, _payload):
                events.append("write")

            with (
                patch.object(oak_qt_shell, "FileLock", RecordingLock),
                patch.object(oak_qt_shell, "read_json", side_effect=read_inside_lock),
                patch.object(oak_qt_shell, "write_json_atomic", side_effect=write_inside_lock),
            ):
                _updated, removed = mutate_pending_file(path, [], clear_done_pending_data)

        self.assertEqual(removed, 1)
        self.assertEqual(events[0], ("lock", f"{path}.lock", 3.0))
        self.assertEqual(events[1:], ["enter", "read", "write", "exit"])

    def test_scheduled_close_mutation_refuses_to_write_without_lock(self):
        class UnavailableLock:
            def __init__(self, _path, timeout):
                self.timeout = timeout

            def __enter__(self):
                return None

            def __exit__(self, *_args):
                return None

        path = Path("scheduled_close_Demo.json")
        with (
            patch.object(oak_qt_shell, "FileLock", UnavailableLock),
            patch.object(oak_qt_shell, "read_json") as read_mock,
            patch.object(oak_qt_shell, "write_json_atomic") as write_mock,
        ):
            with self.assertRaises(TimeoutError):
                mutate_pending_file(path, [], clear_done_pending_data)

        read_mock.assert_not_called()
        write_mock.assert_not_called()

    def test_scheduled_close_delete_preserves_row_added_after_ui_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "scheduled_close_Demo.json"
            target = {"id": 1, "status": "waiting"}
            added_later = {"id": 2, "status": "waiting"}
            stale_item = pending_rows("scheduled closes", path, [target], "list")[0]
            oak_qt_shell.write_json_atomic(path, [target, added_later])

            _updated, removed = mutate_pending_file(
                path,
                [],
                lambda data: remove_pending_item_from_data(data, stale_item),
            )

            self.assertTrue(removed)
            self.assertEqual(oak_qt_shell.read_json(path, []), [added_later])


if __name__ == "__main__":
    unittest.main()
