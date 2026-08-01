import unittest

import mt4_mt5_server


class LegacyComparatorRemovedTests(unittest.TestCase):
    def test_stub_does_not_expose_flask_app(self):
        self.assertFalse(hasattr(mt4_mt5_server, "app"))
        self.assertEqual(mt4_mt5_server.main(), 0)


if __name__ == "__main__":
    unittest.main()
