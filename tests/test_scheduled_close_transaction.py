import inspect
import os
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from domain.copy_trade_manager import CopyTradeManager
from domain.json_io import load_json, save_json


class ScheduledCloseTransactionTests(unittest.TestCase):
    def make_manager(self, path):
        manager = object.__new__(CopyTradeManager)
        manager.config = {"profile_name": "Vantage"}
        manager.scheduled_close_file = path
        manager.scheduled_trades = []
        manager._scheduled_close = []
        manager.notify = lambda _message: None
        return manager

    def test_transaction_reloads_disk_and_updates_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scheduled_close_Vantage.json")
            save_json(path, [{"id": 1}])
            manager = self.make_manager(path)

            result = manager._with_scheduled_close_file_lock(
                lambda closes: [*closes, {"id": 2}]
            )

            self.assertEqual([item["id"] for item in result], [1, 2])
            self.assertEqual(load_json(path, []), result)
            self.assertEqual(manager._scheduled_close, result)

    def test_parallel_transactions_preserve_both_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scheduled_close_Vantage.json")
            save_json(path, [])
            managers = [self.make_manager(path), self.make_manager(path)]

            def append(manager, task_id):
                def mutate(closes):
                    time.sleep(0.03)
                    return [*closes, {"id": task_id}]

                return manager._with_scheduled_close_file_lock(mutate)

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(append, managers[0], 10),
                    executor.submit(append, managers[1], 20),
                ]
                for future in futures:
                    self.assertIsNotNone(future.result())

            self.assertEqual(
                sorted(item["id"] for item in load_json(path, [])),
                [10, 20],
            )

    def test_copy_manager_does_not_create_automatic_daily_closes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scheduled_close_Vantage.json")
            manager = self.make_manager(path)
            save_json(path, [])

            manager._check_scheduled_trades()

            self.assertEqual(load_json(path, []), [])
            self.assertNotIn("_auto_schedule_daily_closes", inspect.getsource(CopyTradeManager))

    def test_manual_scheduled_close_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scheduled_close_Vantage.json")
            manual = {
                "id": 7,
                "time": "12:00:00",
                "date": "2099-01-01",
                "filter": "all",
                "sym": "XAUUSD",
                "ticket": "",
            }
            save_json(path, [manual])
            manager = self.make_manager(path)
            manager._scheduled_close = [manual]

            manager._check_scheduled_trades()

            self.assertEqual(load_json(path, []), [manual])

    def test_legacy_automatic_close_is_removed_without_touching_manual_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scheduled_close_Vantage.json")
            manual = {
                "id": 7,
                "time": "12:00:00",
                "date": "2099-01-01",
                "filter": "all",
                "sym": "XAUUSD",
                "ticket": "",
            }
            legacy_auto = {
                **manual,
                "id": 8,
                "sym": "GBP",
                "is_auto_daily": True,
            }
            save_json(path, [manual, legacy_auto])
            manager = self.make_manager(path)
            manager._scheduled_close = [manual, legacy_auto]

            manager._check_scheduled_trades()

            self.assertEqual(load_json(path, []), [manual])

    def test_lock_timeout_is_propagated(self):
        class BusyLock:
            def __enter__(self):
                return None

            def __exit__(self, *_args):
                return False

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scheduled_close_Vantage.json")
            manager = self.make_manager(path)
            with patch("domain.copy_trade_manager.FileLock", return_value=BusyLock()):
                with self.assertRaisesRegex(TimeoutError, "scheduled close lock timed out"):
                    manager._remove_scheduled_closes(lambda _task: True)

    def test_all_scheduled_close_mutations_use_transaction_helper(self):
        source = inspect.getsource(CopyTradeManager)
        self.assertNotIn("save_json(self.scheduled_close_file", source)


if __name__ == "__main__":
    unittest.main()
