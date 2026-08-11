from pathlib import Path
from types import SimpleNamespace

from domain.mt5_execution import MT5ExecutionGateway
from domain.json_io import save_json
from services.mt5_terminal_service import (
    MT5LaunchResult,
    ensure_mt5_profile_connected,
    profile_session_validation_enabled,
    recover_mt5_profile_session,
    validate_mt5_profile_session,
)

ROOT = Path(__file__).resolve().parents[1]


class SessionFakeMT5:
    TRADE_RETCODE_DONE = 10009

    def __init__(self, login=1001, server="Broker-Live", terminal_path=""):
        self.login = login
        self.server = server
        self.terminal_path = terminal_path
        self.sent = []
        self.initialized = True
        self.shutdown_calls = 0

    def initialize(self, **_kwargs):
        self.initialized = True
        return True

    def shutdown(self):
        self.shutdown_calls += 1
        self.initialized = False

    def last_error(self):
        return (0, "")

    def terminal_info(self):
        return SimpleNamespace(path=self.terminal_path) if self.terminal_path else SimpleNamespace()

    def account_info(self):
        return SimpleNamespace(login=self.login, server=self.server)

    def order_send(self, request):
        self.sent.append(dict(request))
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, order=len(self.sent), deal=len(self.sent))


def test_profile_session_validation_is_enabled_for_real_profile_contracts():
    assert profile_session_validation_enabled({"path": "terminal64.exe"}) is True
    assert profile_session_validation_enabled({"signal_execution_enabled": True}) is True
    assert profile_session_validation_enabled({"copy_role": "slave"}) is True
    assert profile_session_validation_enabled({}) is False


def test_terminal_path_mismatch_fails_closed(tmp_path):
    configured = tmp_path / "configured" / "terminal64.exe"
    observed = tmp_path / "observed" / "terminal64.exe"
    configured.parent.mkdir()
    observed.parent.mkdir()
    configured.write_bytes(b"fake")
    observed.write_bytes(b"fake")

    mt5 = SessionFakeMT5(terminal_path=str(observed))
    ok, reason = validate_mt5_profile_session(mt5, {"path": str(configured)})

    assert ok is False
    assert reason == "TERMINAL_PATH_MISMATCH"


def test_ensure_profile_connection_rejects_terminal_path_mismatch(tmp_path):
    configured = tmp_path / "configured" / "terminal64.exe"
    observed = tmp_path / "observed" / "terminal64.exe"
    configured.parent.mkdir()
    observed.parent.mkdir()
    configured.write_bytes(b"fake")
    observed.write_bytes(b"fake")

    mt5 = SessionFakeMT5(terminal_path=str(observed))
    result = ensure_mt5_profile_connected(
        {"path": str(configured), "signal_execution_enabled": True, "login_id": 1001, "server": "Broker-Live"},
        mt5_module=mt5,
        timeout_seconds=0.1,
    )

    assert result.ok is False
    assert result.failure_code == "TERMINAL_PATH_MISMATCH"


def test_server_identity_is_exact_not_substring():
    mt5 = SessionFakeMT5(server="Broker-Live-2")
    ok, reason = validate_mt5_profile_session(
        mt5,
        {"login_id": 1001, "server": "Broker-Live"},
    )
    assert ok is False
    assert reason == "ACCOUNT_MISMATCH"


def test_account_switch_is_detected_before_execution():
    mt5 = SessionFakeMT5(login=2002, server="Broker-Live")
    ok, reason = validate_mt5_profile_session(
        mt5,
        {"signal_execution_enabled": True, "login_id": 1001, "server": "Broker-Live"},
    )
    assert ok is False
    assert reason == "ACCOUNT_MISMATCH"


def test_signal_gateway_wiring_carries_profile_config():
    source = (ROOT / "mt5_signal_bot.py").read_text(encoding="utf-8")
    start = source.index("_signal_execution_gateway = MT5ExecutionGateway(")
    end = source.index("    return _signal_execution_gateway", start)
    body = source[start:end]
    assert "profile_config=profile_cfg" in body


def test_scheduled_manual_and_copy_paths_wire_session_validation():
    scheduled = (ROOT / "domain/copy_trade_manager.py").read_text(encoding="utf-8")
    manual = (ROOT / "controllers/pending_controller.py").read_text(encoding="utf-8")
    assert "profile_session_validation_enabled(self.config)" in scheduled
    assert scheduled.count("recover_mt5_profile_session(") >= 2
    assert "profile_session_validation_enabled(self.config)" in manual
    assert "validate_mt5_profile_session(mt5, self.config)" in manual


def test_transient_session_loss_reconnects_and_revalidates_exact_identity():
    mt5 = SessionFakeMT5(login=1001, server="Broker-Live")
    mt5.initialized = False

    original_terminal_info = mt5.terminal_info
    original_account_info = mt5.account_info
    mt5.terminal_info = lambda: original_terminal_info() if mt5.initialized else None
    mt5.account_info = lambda: original_account_info() if mt5.initialized else None
    calls = {"n": 0}

    def reconnect(profile_config, **_kwargs):
        calls["n"] += 1
        mt5.initialized = True
        return MT5LaunchResult(True, "", True, 123, 1, None, None, "Connected")

    ok, reason, recovered = recover_mt5_profile_session(
        mt5,
        {"login_id": 1001, "server": "Broker-Live", "signal_execution_enabled": True},
        reconnect_fn=reconnect,
    )

    assert (ok, reason, recovered) == (True, "SESSION_RECOVERED", True)
    assert calls["n"] == 1


def test_reconnect_to_wrong_account_fails_closed():
    mt5 = SessionFakeMT5(login=1001, server="Broker-Live")
    mt5.initialized = False

    original_terminal_info = mt5.terminal_info
    original_account_info = mt5.account_info
    mt5.terminal_info = lambda: original_terminal_info() if mt5.initialized else None
    mt5.account_info = lambda: original_account_info() if mt5.initialized else None

    def reconnect(profile_config, **_kwargs):
        mt5.initialized = True
        mt5.login = 2002
        return MT5LaunchResult(True, "", True, 123, 1, None, None, "Connected")

    ok, reason, recovered = recover_mt5_profile_session(
        mt5,
        {"login_id": 1001, "server": "Broker-Live", "signal_execution_enabled": True},
        reconnect_fn=reconnect,
    )

    assert (ok, reason, recovered) == (False, "ACCOUNT_MISMATCH", True)


def test_identity_mismatch_is_not_reconnectable():
    mt5 = SessionFakeMT5(login=2002, server="Broker-Live")
    calls = {"n": 0}

    def reconnect(*_args, **_kwargs):
        calls["n"] += 1
        return MT5LaunchResult(True, "", False, None, 1, None, None, "Connected")

    ok, reason, recovered = recover_mt5_profile_session(
        mt5,
        {"login_id": 1001, "server": "Broker-Live", "signal_execution_enabled": True},
        reconnect_fn=reconnect,
    )

    assert (ok, reason, recovered) == (False, "ACCOUNT_MISMATCH", False)
    assert calls["n"] == 0


def test_execution_gateway_with_bound_profile_stops_before_order_send(tmp_path):
    store = type("Store", (), {
        "upsert_signal_execution_intent": lambda self, intent: None,
        "get_due_signal_execution_intents": lambda self, now_utc, limit=50: [],
        "update_signal_execution_intent": lambda self, key, **changes: None,
    })()
    mt5 = SessionFakeMT5(login=9999, server="Wrong-Server")
    gateway = MT5ExecutionGateway(
        mt5,
        store,
        enabled=True,
        profile_config={"signal_execution_enabled": True, "login_id": 1001, "server": "Broker-Live"},
        risk_state_dir=str(tmp_path),
    )

    intent = {
        "idempotency_key": "signal:profile-test:1",
        "symbol": "XAUUSD",
        "volume": 0.01,
        "side": "BUY",
        "entry_at_utc": "2026-08-11T00:00:00+00:00",
    }
    result = gateway._execute_intent(intent)

    assert mt5.sent == []
    assert result is not None
