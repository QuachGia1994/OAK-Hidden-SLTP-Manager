import inspect
import os
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
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
        manager._last_auto_close_date = None
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

    def test_auto_daily_retries_after_first_persistence_failure(self):
        class FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 7, 22, 8, 0, 0)

            @classmethod
            def utcnow(cls):
                return cls(2026, 7, 22, 1, 0, 0)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scheduled_close_Vantage.json")
            manager = self.make_manager(path)
            attempts = {"count": 0}

            def flaky_save(file, payload):
                attempts["count"] += 1
                if attempts["count"] == 1:
                    raise PermissionError("busy")
                return save_json(file, payload)

            with patch("domain.copy_trade_manager.datetime", FixedDatetime):
                with patch("domain.copy_trade_manager.mt5.symbol_info_tick", return_value=None):
                    with patch(
                        "domain.copy_trade_manager.save_json",
                        side_effect=flaky_save,
                    ):
                        with self.assertRaises(PermissionError):
                            manager._auto_schedule_daily_closes()
                        self.assertIsNone(manager._last_auto_close_date)
                        manager._auto_schedule_daily_closes()

            self.assertEqual(manager._last_auto_close_date, "2026-07-22")
            self.assertEqual(len(load_json(path, [])), 2)

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
