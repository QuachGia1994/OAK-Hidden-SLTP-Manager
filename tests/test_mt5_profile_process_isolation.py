import unittest
from services.mt5_terminal_service import normalize_terminal_path


class MT5ProfileIsolationTests(unittest.TestCase):
    def test_terminal_path_is_normalized_per_worker(self):
        self.assertIsNone(normalize_terminal_path("C:/not-a-terminal.exe"))


if __name__ == "__main__":
    unittest.main()
