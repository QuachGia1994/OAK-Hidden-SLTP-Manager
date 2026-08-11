from datetime import datetime, timedelta
from types import SimpleNamespace

from domain.copy_trade_manager import CopyTradeManager, _scheduled_local_datetimes
from domain.json_io import load_json, save_json


class FakeMT5:
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TYPE_BUY_STOP = 4
    ORDER_TYPE_SELL_STOP = 5
    ORDER_TYPE_BUY_STOP_LIMIT = 6
    ORDER_TYPE_SELL_STOP_LIMIT = 7
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    TRADE_RETCODE_DONE = 10009

    def __init__(self):
        self.sent = 0
        self.positions = []

    def terminal_info(self):
        return SimpleNamespace()

    def positions_get(self, symbol=None):
        return [p for p in self.positions if symbol is None or p.symbol == symbol]

    def symbol_info(self, symbol):
        return SimpleNamespace(point=0.01, digits=2)

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(ask=2500.0, bid=2499.9)

    def orders_get(self, symbol=None):
        return []

    def order_send(self, request):
        self.sent += 1
        ticket = 9000 + self.sent
        self.positions.append(SimpleNamespace(ticket=ticket, symbol=request["symbol"], type=request["type"]))
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, order=ticket, deal=ticket + 100)


def _manager(path):
    manager = object.__new__(CopyTradeManager)
    manager.scheduled_file = str(path)
    manager.scheduled_trades = load_json(str(path), [])
    manager.config = {"profile_name": "VantageDemo", "risk_gate_enabled": False, "use_balance_sltp": False}
    manager.max_lot_per_trade = 5.0
    manager._risk_denial_notifications = set()
    manager.notify = lambda *_args, **_kwargs: None
    return manager


def test_full_scheduled_entry_state_machine_executes_once_and_finalizes(tmp_path, monkeypatch):
    path = tmp_path / "waiting.json"
    save_json(str(path), [{
        "id": 4242,
        "symbol": "XAUUSD",
        "type": 0,
        "lot": "0.01",
        "sl": "0",
        "tp": "0",
        "time": "20:15:00",
        "date": "2026-08-10",
        "status": "waiting",
    }])
    manager = _manager(path)
    fake = FakeMT5()

    # Freeze the scheduler at T-1s: inside the intentional T-2s execution window.
    now = datetime(2026, 8, 10, 20, 14, 59)
    monkeypatch.setattr("domain.copy_trade_manager.datetime", type("FrozenDateTime", (), {
        "now": staticmethod(lambda: now),
        "strptime": staticmethod(datetime.strptime),
    }))
    monkeypatch.setattr("domain.copy_trade_manager.mt5", fake)

    def fake_send(request, key):
        result = fake.order_send(request)
        return {"status": "DONE", "ticket": result.order}

    monkeypatch.setattr("domain.copy_trade_manager.send_order_idempotent", fake_send)
    monkeypatch.setattr("domain.copy_trade_manager.get_filling_type", lambda _symbol: 1)

    manager._check_scheduled_trades()
    first = load_json(str(path), [])[0]
    assert first["status"] == "executed"
    assert fake.sent == 1

    # A second scheduler pass must not send the same intent again.
    manager.scheduled_trades = load_json(str(path), [])
    manager._check_scheduled_trades()
    second = load_json(str(path), [])[0]
    assert second["status"] == "executed"
    assert fake.sent == 1


def test_scheduled_state_machine_keeps_retryable_failure_and_then_executes(tmp_path, monkeypatch):
    path = tmp_path / "waiting.json"
    save_json(str(path), [{
        "id": 4343,
        "symbol": "XAUUSD",
        "type": 0,
        "lot": "0.01",
        "sl": "0",
        "tp": "0",
        "time": "20:15:00",
        "date": "2026-08-10",
        "status": "waiting",
    }])
    manager = _manager(path)
    fake = FakeMT5()
    now = datetime(2026, 8, 10, 20, 14, 59)
    monkeypatch.setattr("domain.copy_trade_manager.datetime", type("FrozenDateTime", (), {
        "now": staticmethod(lambda: now),
        "strptime": staticmethod(datetime.strptime),
    }))
    monkeypatch.setattr("domain.copy_trade_manager.mt5", fake)
    monkeypatch.setattr("domain.copy_trade_manager.get_filling_type", lambda _symbol: 1)
    clock = {"epoch": now.timestamp()}
    monkeypatch.setattr("domain.copy_trade_manager.time.time", lambda: clock["epoch"])

    calls = {"n": 0}

    def flaky_send(request, key):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"status": "UNKNOWN", "error": "broker response lost"}
        result = fake.order_send(request)
        return {"status": "DONE", "ticket": result.order}

    monkeypatch.setattr("domain.copy_trade_manager.send_order_idempotent", flaky_send)
    manager._check_scheduled_trades()
    failed = load_json(str(path), [])[0]
    assert failed["status"] == "waiting"
    assert failed["last_execution_failure"].startswith("order_send:UNKNOWN")
    assert failed["next_retry_at"] > now.timestamp()
    assert fake.sent == 0

    # Move past the persisted retry deadline without changing the requested schedule.
    retry_epoch = failed["next_retry_at"] + 0.1
    retry_now = datetime.fromtimestamp(retry_epoch)
    clock["epoch"] = retry_epoch
    monkeypatch.setattr("domain.copy_trade_manager.datetime", type("RetryDateTime", (), {
        "now": staticmethod(lambda: retry_now),
        "strptime": staticmethod(datetime.strptime),
    }))
    manager.scheduled_trades = load_json(str(path), [])
    manager._check_scheduled_trades()
    final = load_json(str(path), [])[0]
    assert final["status"] == "executed"
    assert calls["n"] == 2
    assert fake.sent == 1


def test_t_minus_two_session_recovery_retries_without_shifting_requested_schedule(tmp_path, monkeypatch):
    path = tmp_path / "waiting.json"
    save_json(str(path), [{
        "id": 4545,
        "symbol": "XAUUSD",
        "type": 0,
        "lot": "0.01",
        "sl": "0",
        "tp": "0",
        "time": "20:15:00",
        "date": "2026-08-10",
        "status": "waiting",
    }])
    manager = _manager(path)
    manager.config["signal_execution_enabled"] = True
    fake = FakeMT5()
    now = datetime(2026, 8, 10, 20, 14, 59)
    monkeypatch.setattr("domain.copy_trade_manager.datetime", type("FrozenDateTime", (), {
        "now": staticmethod(lambda: now),
        "strptime": staticmethod(datetime.strptime),
    }))
    monkeypatch.setattr("domain.copy_trade_manager.mt5", fake)
    monkeypatch.setattr("domain.copy_trade_manager.get_filling_type", lambda _symbol: 1)
    clock = {"epoch": now.timestamp()}
    monkeypatch.setattr("domain.copy_trade_manager.time.time", lambda: clock["epoch"])

    recovery_calls = {"n": 0}

    def recover_then_fail(*_args, **_kwargs):
        recovery_calls["n"] += 1
        return False, "MT5_SESSION_UNAVAILABLE", False

    monkeypatch.setattr("domain.copy_trade_manager.recover_mt5_profile_session", recover_then_fail)
    monkeypatch.setattr(
        "domain.copy_trade_manager.send_order_idempotent",
        lambda _request, _key: {"status": "DONE", "ticket": 9901},
    )

    manager._check_scheduled_trades()
    retrying = load_json(str(path), [])[0]
    assert retrying["status"] == "waiting"
    assert retrying["last_execution_failure"] == "profile_session:MT5_SESSION_UNAVAILABLE"
    assert retrying["next_retry_at"] > clock["epoch"]
    assert recovery_calls["n"] == 1
    assert fake.sent == 0
    assert retrying["time"] == "20:15:00"
    assert retrying["date"] == "2026-08-10"

    retry_epoch = retrying["next_retry_at"] + 0.1
    retry_now = datetime.fromtimestamp(retry_epoch)
    clock["epoch"] = retry_epoch
    monkeypatch.setattr("domain.copy_trade_manager.datetime", type("RetryDateTime", (), {
        "now": staticmethod(lambda: retry_now),
        "strptime": staticmethod(datetime.strptime),
    }))

    def recover_success(*_args, **_kwargs):
        recovery_calls["n"] += 1
        return True, "SESSION_RECOVERED", True

    monkeypatch.setattr("domain.copy_trade_manager.recover_mt5_profile_session", recover_success)
    manager.scheduled_trades = load_json(str(path), [])
    manager._check_scheduled_trades()

    completed = load_json(str(path), [])[0]
    assert completed["status"] == "executed"
    # One recovery attempt on the first pass, then the pre-send session fence
    # revalidates the recovered session immediately before the broker call.
    assert recovery_calls["n"] == 3
    assert completed["time"] == "20:15:00"
    assert completed["date"] == "2026-08-10"


def test_t_minus_two_wrong_account_is_terminal_and_not_retryable(tmp_path, monkeypatch):
    path = tmp_path / "waiting.json"
    save_json(str(path), [{
        "id": 4646,
        "symbol": "XAUUSD",
        "type": 0,
        "lot": "0.01",
        "sl": "0",
        "tp": "0",
        "time": "20:15:00",
        "date": "2026-08-10",
        "status": "waiting",
    }])
    manager = _manager(path)
    manager.config["signal_execution_enabled"] = True
    fake = FakeMT5()
    now = datetime(2026, 8, 10, 20, 14, 59)
    monkeypatch.setattr("domain.copy_trade_manager.datetime", type("FrozenDateTime", (), {
        "now": staticmethod(lambda: now),
        "strptime": staticmethod(datetime.strptime),
    }))
    monkeypatch.setattr("domain.copy_trade_manager.mt5", fake)
    monkeypatch.setattr("domain.copy_trade_manager.get_filling_type", lambda _symbol: 1)
    monkeypatch.setattr(
        "domain.copy_trade_manager.recover_mt5_profile_session",
        lambda *_args, **_kwargs: (False, "ACCOUNT_MISMATCH", False),
    )
    monkeypatch.setattr(
        "domain.copy_trade_manager.send_order_idempotent",
        lambda _request, _key: {"status": "DONE", "ticket": 9902},
    )

    manager._check_scheduled_trades()
    blocked = load_json(str(path), [])[0]
    assert blocked["status"] == "skipped"
    assert "next_retry_at" not in blocked
    assert fake.sent == 0


def test_final_session_fence_blocks_account_switch_after_trade_preparation(tmp_path, monkeypatch):
    path = tmp_path / "waiting.json"
    save_json(str(path), [{
        "id": 4747,
        "symbol": "XAUUSD",
        "type": 0,
        "lot": "0.01",
        "sl": "0",
        "tp": "0",
        "time": "20:15:00",
        "date": "2026-08-10",
        "status": "waiting",
    }])
    manager = _manager(path)
    manager.config.update({
        "signal_execution_enabled": True,
        "login_id": 1001,
        "server": "Broker-Live",
    })
    fake = FakeMT5()
    monkeypatch.setattr("domain.copy_trade_manager.mt5", fake)
    monkeypatch.setattr("domain.copy_trade_manager.get_filling_type", lambda _symbol: 1)
    monkeypatch.setattr(
        "domain.copy_trade_manager.recover_mt5_profile_session",
        lambda *_args, **_kwargs: (
            False,
            "ACCOUNT_MISMATCH",
            False,
        ) if fake.account_switched else (True, "SESSION_OK", False),
    )

    original_prepare = manager._prepare_scheduled_trade

    def prepare_then_switch(trade, order_type_override=None):
        result = original_prepare(trade, order_type_override=order_type_override)
        if result == "ok":
            fake.account_switched = True
            fake.login = 2002
        return result

    fake.account_switched = False
    manager._prepare_scheduled_trade = prepare_then_switch
    monkeypatch.setattr(
        "domain.copy_trade_manager.send_order_idempotent",
        lambda _request, _key: {"status": "DONE", "ticket": 9903},
    )

    result = manager._send_scheduled_market_order(
        load_json(str(path), [])[0],
        idempotency_key="scheduled:VantageDemo:4747",
    )

    assert result == "skip"
    assert fake.sent == 0


def test_local_schedule_contract_remains_machine_local_with_two_second_lead():
    requested, execute = _scheduled_local_datetimes("2026-08-10", "20:15:00")
    assert requested == datetime(2026, 8, 10, 20, 15, 0)
    assert execute == requested - timedelta(seconds=2)
