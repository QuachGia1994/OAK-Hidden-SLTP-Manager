import types

from services.mt5_terminal_service import (
    ensure_mt5_profile_connected,
    validate_mt5_mutation_session,
    validate_mt5_profile_session,
)


class FakeMT5:
    def __init__(self, login=1001, server="Broker-Demo", terminal_path=""):
        self.login = login
        self.server = server
        self.terminal_path = terminal_path
        self.initialized = False
        self.shutdown_calls = 0

    def initialize(self, **kwargs):
        self.initialized = True
        return True

    def shutdown(self):
        self.shutdown_calls += 1
        self.initialized = False

    def terminal_info(self):
        return types.SimpleNamespace(path=self.terminal_path) if self.initialized else None

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


def test_execution_profile_rejects_partial_identity(tmp_path):
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"fake")
    mt5 = FakeMT5(login=1001, server="Broker-Live")

    for profile in (
        {"path": str(terminal), "signal_execution_enabled": True, "login_id": 1001},
        {"path": str(terminal), "signal_execution_enabled": True, "server": "Broker-Live"},
    ):
        result = ensure_mt5_profile_connected(profile, mt5_module=mt5, timeout_seconds=0.1)
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


def test_mutation_session_requires_login_server_and_path(tmp_path):
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"fake")
    mt5 = FakeMT5(login=1001, server="Broker-Live", terminal_path=str(terminal))
    mt5.initialized = True

    assert validate_mt5_mutation_session(mt5, {"path": str(terminal)}) == (False, "MUTATION_LOGIN_REQUIRED")
    assert validate_mt5_mutation_session(mt5, {"path": str(terminal), "login_id": 1001}) == (False, "MUTATION_SERVER_REQUIRED")
    assert validate_mt5_mutation_session(mt5, {"login_id": 1001, "server": "Broker-Live"}) == (False, "MUTATION_PATH_REQUIRED")


def test_mutation_session_rejects_partial_identity(tmp_path):
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"fake")
    mt5 = FakeMT5(login=1001, server="Broker-Live", terminal_path=str(terminal))
    mt5.initialized = True

    assert validate_mt5_mutation_session(
        mt5,
        {"path": str(terminal), "login_id": 1001},
    ) == (False, "MUTATION_SERVER_REQUIRED")
    assert validate_mt5_mutation_session(
        mt5,
        {"path": str(terminal), "server": "Broker-Live"},
    ) == (False, "MUTATION_LOGIN_REQUIRED")


def test_mutation_session_accepts_exact_identity(tmp_path):
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"fake")
    mt5 = FakeMT5(login=1001, server="Broker-Live", terminal_path=str(terminal))
    mt5.initialized = True

    assert validate_mt5_mutation_session(
        mt5,
        {"path": str(terminal), "login_id": 1001, "server": "Broker-Live"},
    ) == (True, "MUTATION_SESSION_OK")


def test_mutation_session_rejects_account_switch(tmp_path):
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"fake")
    mt5 = FakeMT5(login=2002, server="Broker-Live", terminal_path=str(terminal))
    mt5.initialized = True

    assert validate_mt5_mutation_session(
        mt5,
        {"path": str(terminal), "login_id": 1001, "server": "Broker-Live"},
    ) == (False, "ACCOUNT_MISMATCH")


def test_mutation_session_rejects_terminal_switch(tmp_path):
    configured = tmp_path / "configured" / "terminal64.exe"
    observed = tmp_path / "observed" / "terminal64.exe"
    configured.parent.mkdir()
    observed.parent.mkdir()
    configured.write_bytes(b"fake")
    observed.write_bytes(b"fake")
    mt5 = FakeMT5(login=1001, server="Broker-Live", terminal_path=str(observed))
    mt5.initialized = True

    assert validate_mt5_mutation_session(
        mt5,
        {"path": str(configured), "login_id": 1001, "server": "Broker-Live"},
    ) == (False, "TERMINAL_PATH_MISMATCH")
