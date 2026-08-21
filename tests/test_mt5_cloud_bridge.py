from __future__ import annotations

from types import SimpleNamespace

import domain.mt5_cloud_bridge as bridge


class FakeMT5:
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_SLTP = 6
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2

    def __init__(self, *, login=202):
        self.login = login
        self.position = SimpleNamespace(
            ticket=77,
            symbol="GBPUSD",
            type=self.POSITION_TYPE_BUY,
            volume=0.1,
            profit=12.5,
            price_open=1.1000,
            price_current=1.1010,
            sl=1.0950,
            tp=1.1200,
            magic=42,
        )

    def account_info(self):
        return SimpleNamespace(login=self.login, server="Vantage", company="Vantage")

    def symbol_select(self, _symbol, _enabled):
        return True

    def symbol_info(self, symbol):
        if symbol != "GBPUSD":
            return None
        return SimpleNamespace(point=0.00001, digits=5, volume_min=0.01, volume_max=100.0, volume_step=0.01, filling_mode=self.ORDER_FILLING_IOC)

    def symbol_info_tick(self, symbol):
        if symbol != "GBPUSD":
            return None
        return SimpleNamespace(ask=1.1001, bid=1.1000)

    def symbols_get(self):
        return [SimpleNamespace(name="GBPUSD")]

    def positions_get(self, ticket=None, symbol=None):
        if ticket is not None:
            return [self.position] if ticket == self.position.ticket else []
        if symbol is not None:
            return [self.position] if symbol == self.position.symbol else []
        return [self.position]


PROFILE = {"profile_name": "Vantage", "login_id": 202, "server": "Vantage", "magic": "42"}


def _task(action, **extra):
    return {
        "version": 1,
        "id": f"intent:1:mt5:abcdefgh:{action}",
        "intentId": 1,
        "providerAccountId": "mt5:abcdefgh",
        "bridgeProfile": "Vantage",
        "login": 202,
        "action": action,
        "payload": {},
        "status": "running",
        **extra,
    }


def test_entry_builds_sl_tp_and_uses_existing_idempotent_gateway(monkeypatch):
    fake = FakeMT5()
    calls = []
    monkeypatch.setattr(bridge, "validate_mt5_mutation_session", lambda _module, _profile: (True, "OK"))

    def fake_send(request, key, **kwargs):
        calls.append((request, key, kwargs))
        return {"status": "DONE", "ticket": 99, "response": None}

    monkeypatch.setattr(bridge, "send_order_idempotent", fake_send)
    result = bridge.execute_mt5_bridge_task(
        _task("entry", payload={"symbol": "GBPUSD", "side": "BUY", "lot": 0.1}, protection={"slPoints": 500, "tpPoints": 10000}),
        dict(PROFILE),
        mt5_module=fake,
    )

    assert result == {"ok": True, "action": "entry", "detail": "BUY GBPUSD 0.1 lot", "brokerRef": "99"}
    assert len(calls) == 1
    request, key, kwargs = calls[0]
    assert key.startswith("cloud-entry:intent:1:mt5:abcdefgh:entry")
    assert request["sl"] == 1.0951
    assert request["tp"] == 1.2001
    assert request["magic"] == 42
    assert kwargs["mt5_module"] is fake
    assert kwargs["profile_config"]["login_id"] == 202


def test_unknown_entry_is_uncertain_and_is_not_retried_inside_bridge(monkeypatch):
    fake = FakeMT5()
    calls = []
    monkeypatch.setattr(bridge, "validate_mt5_mutation_session", lambda _module, _profile: (True, "OK"))

    def fake_send(*args, **kwargs):
        calls.append((args, kwargs))
        return {"status": "UNKNOWN", "ticket": None, "response": None, "error": "transport lost after submit"}

    monkeypatch.setattr(bridge, "send_order_idempotent", fake_send)
    result = bridge.execute_mt5_bridge_task(
        _task("entry", payload={"symbol": "GBPUSD", "side": "SELL", "lot": 0.1}, protection={"slPoints": 500, "tpPoints": 10000}),
        dict(PROFILE),
        mt5_module=fake,
    )
    assert len(calls) == 1
    assert result["ok"] is False
    assert result["uncertain"] is True
    assert "transport lost" in result["detail"]


def test_bridge_rejects_wrong_live_login_before_any_mutation(monkeypatch):
    fake = FakeMT5(login=999)
    called = False
    monkeypatch.setattr(bridge, "validate_mt5_mutation_session", lambda _module, _profile: (True, "OK"))

    def fake_send(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("mutation must not be reached")

    monkeypatch.setattr(bridge, "send_order_idempotent", fake_send)
    result = bridge.execute_mt5_bridge_task(
        _task("entry", payload={"symbol": "GBPUSD", "side": "BUY", "lot": 0.1}, protection={"slPoints": 500, "tpPoints": 10000}),
        dict(PROFILE),
        mt5_module=fake,
    )
    assert called is False
    assert result["ok"] is False
    assert "BRIDGE_LOGIN_MISMATCH:999:202" in result["detail"]


def test_close_modify_and_positions_share_the_bound_profile_session(monkeypatch):
    fake = FakeMT5()
    mutations = []
    monkeypatch.setattr(bridge, "validate_mt5_mutation_session", lambda _module, _profile: (True, "OK"))

    def fake_mutation(request, key, **kwargs):
        mutations.append((request, key, kwargs))
        return {"status": "DONE", "ticket": request.get("position"), "response": None}

    monkeypatch.setattr(bridge, "send_mutation_idempotent", fake_mutation)

    positions = bridge.execute_mt5_bridge_task(_task("positions"), dict(PROFILE), mt5_module=fake)
    close = bridge.execute_mt5_bridge_task(_task("close", payload={"scope": "GBPUSD"}), dict(PROFILE), mt5_module=fake, mutation_store=object())
    modify = bridge.execute_mt5_bridge_task(_task("modify", payload={"field": "SL", "symbol": "GBPUSD", "value": 1.0975}), dict(PROFILE), mt5_module=fake, mutation_store=object())

    assert positions["ok"] is True
    assert positions["positions"][0]["ticket"] == 77
    assert positions["positions"][0]["side"] == "BUY"
    assert close["ok"] is True
    assert close["brokerRef"] == "77"
    assert modify["ok"] is True
    assert modify["brokerRef"] == "77"
    assert len(mutations) == 2
    assert mutations[0][0]["action"] == fake.TRADE_ACTION_DEAL
    assert mutations[1][0]["action"] == fake.TRADE_ACTION_SLTP
    assert mutations[1][0]["sl"] == 1.0975
