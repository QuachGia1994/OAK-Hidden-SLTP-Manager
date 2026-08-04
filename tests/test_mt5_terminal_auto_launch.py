import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from services.mt5_terminal_service import ensure_mt5_profile_connected


class FakeMT5:
    def __init__(self):
        self.initializes = []
        self.shutdowns = 0
        self.calls = 0

    def shutdown(self):
        self.shutdowns += 1

    def initialize(self, **kwargs):
        self.initializes.append(kwargs)
        self.calls += 1
        return self.calls >= 2

    def terminal_info(self):
        return object() if self.calls >= 2 else None

    def account_info(self):
        return SimpleNamespace(login=123, server="Vantage") if self.calls >= 2 else None

    def last_error(self):
        return (-10003, "IPC")


class MT5TerminalAutoLaunchTests(unittest.TestCase):
    def test_explicit_terminal_is_started_and_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "terminal64.exe"
            path.write_bytes(b"fake")
            mt5 = FakeMT5()
            processes = []

            def start(candidate):
                processes.append(candidate)
                return SimpleNamespace(pid=42)

            now = [0.0]
            result = ensure_mt5_profile_connected(
                {"path": str(path), "login_id": 123, "server": "Vantage"},
                mt5_module=mt5,
                process_factory=start,
                monotonic_fn=lambda: now[0],
                sleep_fn=lambda seconds: now.__setitem__(0, now[0] + seconds),
                timeout_seconds=20,
            )
            self.assertTrue(result.ok)
            self.assertEqual(result.process_id, 42)
            self.assertEqual(result.initialize_attempts, 2)
            # Windows 8.3 short-name aliases (RUNNER~1 vs runneradmin) differ
            # between CI runners and dev machines — compare resolved forms so
            # the assertion is invariant to short/long path presentation.
            self.assertEqual([p.resolve() for p in processes], [path.resolve()])
            self.assertEqual(Path(mt5.initializes[0]["path"]).resolve(), path.resolve())
            self.assertNotIn("portable", mt5.initializes[0])

    def test_invalid_path_does_not_initialize(self):
        mt5 = FakeMT5()
        result = ensure_mt5_profile_connected(
            {"path": "Z:/missing/terminal64.exe", "profile_name": "Vantage"},
            mt5_module=mt5,
            discover_fn=lambda: [],
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, "TERMINAL_PATH_NOT_FOUND")
        self.assertEqual(mt5.initializes, [])

    def test_attaches_before_launching_when_process_inspection_is_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "terminal64.exe"
            path.write_bytes(b"fake")

            class AlreadyConnectedMT5(FakeMT5):
                def initialize(self, **kwargs):
                    self.initializes.append(kwargs)
                    self.calls += 1
                    return True

                def terminal_info(self):
                    return object()

                def account_info(self):
                    return SimpleNamespace(login=123, server="Vantage")

            mt5 = AlreadyConnectedMT5()
            launches = []
            result = ensure_mt5_profile_connected(
                {"path": str(path), "login_id": 123, "server": "Vantage"},
                mt5_module=mt5,
                process_factory=lambda candidate: launches.append(candidate),
            )

            self.assertTrue(result.ok)
            self.assertFalse(result.process_started)
            self.assertEqual(result.initialize_attempts, 1)
            self.assertEqual(launches, [])


if __name__ == "__main__":
    unittest.main()
