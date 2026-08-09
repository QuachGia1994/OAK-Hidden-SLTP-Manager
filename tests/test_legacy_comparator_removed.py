"""MT4 comparator/runtime modules are intentionally absent after MT5 migration."""
import importlib.util
import unittest


class LegacyComparatorRemovalTests(unittest.TestCase):
    def test_mt4_runtime_module_is_removed(self):
        self.assertIsNone(importlib.util.find_spec("mt4_mt5_server"))

    def test_mt4_feed_store_module_is_removed(self):
        self.assertIsNone(importlib.util.find_spec("repositories.mt4_feed_store"))


if __name__ == "__main__":
    unittest.main()
