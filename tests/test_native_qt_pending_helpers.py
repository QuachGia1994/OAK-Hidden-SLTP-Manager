# -*- coding: utf-8 -*-
"""Tests for NativeQt pending-control helper logic."""
from pathlib import Path
import unittest

from oak_qt_shell import (
    clear_done_pending_data,
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


if __name__ == "__main__":
    unittest.main()
