import types

from services.mt5_terminal_service import (
    ensure_mt5_profile_connected,
    validate_mt5_profile_session,
)


class FakeMT5:
    def __init__(self, login=1001, server="Broker-Demo"):
        self.login = login
        self.server = server
        self.initialized = False
        self.shutdown_calls = 0

    def initialize(self, **kwargs):
        self.initialized = True
        return True

    def shutdown(self):
        self.shutdown_calls += 1
        self.initialized = False

    def terminal_info(self):
        return object() if self.initialized else None

    def account_info(self):
        if not self.initialized:
            return None
        return types.SimpleNamespace(login=self.login, server=self.server)

    def last_error(self):
        return (0, "")


def test_execution_profile_requires_explicit_account_identity(tmp_path):
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"fake")
    mt5 = FakeMT5()

    result = ensure_mt5_profile_connected(
        {
            "path": str(terminal),
            "signal_execution_enabled": True,
        },
        mt5_module=mt5,
        timeout_seconds=0.1,
    )

    assert result.ok is False
    assert result.failure_code == "ACCOUNT_MISMATCH"
    assert mt5.shutdown_calls >= 1


def test_execution_profile_rejects_wrong_account(tmp_path):
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"fake")
    mt5 = FakeMT5(login=2002, server="Broker-Live")

    result = ensure_mt5_profile_connected(
        {
            "path": str(terminal),
            "signal_execution_enabled": True,
            "login_id": 1001,
            "server": "Broker-Live",
        },
        mt5_module=mt5,
        timeout_seconds=0.1,
    )

    assert result.ok is False
    assert result.failure_code == "ACCOUNT_MISMATCH"


def test_execution_profile_accepts_exact_account_and_server(tmp_path):
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"fake")
    mt5 = FakeMT5(login=1001, server="Broker-Live")

    result = ensure_mt5_profile_connected(
        {
            "path": str(terminal),
            "signal_execution_enabled": True,
            "login_id": 1001,
            "server": "Broker-Live",
        },
        mt5_module=mt5,
        timeout_seconds=0.1,
    )

    assert result.ok is True


def test_continuous_session_validation_detects_account_switch():
    mt5 = FakeMT5(login=1001, server="Broker-Live")
    mt5.initialized = True
    profile = {
        "signal_execution_enabled": True,
        "login_id": 1001,
        "server": "Broker-Live",
    }

    assert validate_mt5_profile_session(mt5, profile) == (True, "SESSION_OK")

    mt5.login = 2002
    assert validate_mt5_profile_session(mt5, profile) == (False, "ACCOUNT_MISMATCH")


def test_non_execution_profile_can_remain_path_only():
    mt5 = FakeMT5(login=9999, server="Broker-Other")
    mt5.initialized = True

    assert validate_mt5_profile_session(mt5, {"path": "terminal64.exe"}) == (True, "SESSION_OK")
