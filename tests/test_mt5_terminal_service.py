from types import SimpleNamespace

from services.mt5_terminal_service import ensure_mt5_profile_connected


class FakeMT5:
    def __init__(self, terminal_path):
        self.terminal_path = terminal_path
        self.initialized = False
        self.shutdown_calls = 0
        self.initialize_calls = 0

    def shutdown(self):
        self.shutdown_calls += 1
        self.initialized = False

    def initialize(self, **kwargs):
        self.initialize_calls += 1
        assert kwargs["path"] == self.terminal_path
        self.initialized = True
        return True

    def terminal_info(self):
        return SimpleNamespace(path=self.terminal_path)

    def account_info(self):
        return SimpleNamespace(login=123456, server="Broker-Live")

    def last_error(self):
        return (1, "Success")


def test_ensure_connects_and_validates_under_profile_lock(tmp_path):
    terminal = tmp_path / "terminal64.exe"
    terminal.write_text("fake", encoding="utf-8")
    profile = {
        "path": str(terminal),
        "login_id": 123456,
        "server": "Broker-Live",
        "signal_execution_enabled": True,
    }
    fake = FakeMT5(str(terminal))

    result = ensure_mt5_profile_connected(
        profile,
        timeout_seconds=2,
        mt5_module=fake,
        discover_fn=lambda: [],
    )

    assert result.ok is True
    assert result.failure_code is None
    # A healthy/clean attach must not require an unconditional shutdown;
    # avoiding that teardown is part of the multi-profile IPC safety contract.
    assert fake.shutdown_calls == 0
    assert fake.initialize_calls == 1


def test_ensure_accepts_mt5_terminal_info_directory_path(tmp_path):
    terminal = tmp_path / "terminal64.exe"
    terminal.write_text("fake", encoding="utf-8")
    profile = {
        "path": str(terminal),
        "login_id": 123456,
        "server": "Broker-Live",
        "signal_execution_enabled": True,
    }
    fake = FakeMT5(str(terminal))
    fake.terminal_info = lambda: SimpleNamespace(path=str(terminal.parent))

    result = ensure_mt5_profile_connected(
        profile,
        timeout_seconds=2,
        mt5_module=fake,
        discover_fn=lambda: [],
    )

    assert result.ok is True
    assert result.failure_code is None


def test_ensure_fails_closed_when_profile_identity_does_not_match(tmp_path):
    terminal = tmp_path / "terminal64.exe"
    terminal.write_text("fake", encoding="utf-8")
    profile = {
        "path": str(terminal),
        "login_id": 123456,
        "server": "Broker-Live",
        "signal_execution_enabled": True,
    }
    fake = FakeMT5(str(terminal))
    fake.account_info = lambda: SimpleNamespace(login=999999, server="Broker-Wrong")

    result = ensure_mt5_profile_connected(
        profile,
        timeout_seconds=2,
        mt5_module=fake,
        discover_fn=lambda: [],
    )

    assert result.ok is False
    assert result.failure_code == "ACCOUNT_MISMATCH"
