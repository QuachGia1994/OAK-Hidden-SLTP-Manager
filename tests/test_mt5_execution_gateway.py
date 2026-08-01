from datetime import date, datetime, timezone
from types import SimpleNamespace

from domain.mt5_execution import MT5ExecutionGateway, SIGNAL_PAIRS


class IntentStore:
    def __init__(self):
        self.rows = {}

    def upsert_signal_execution_intent(self, intent):
        self.rows.setdefault(intent["idempotency_key"], dict(intent))

    def get_due_signal_execution_intents(self, now_utc, limit=50):
        return [row for row in self.rows.values() if row["status"] == "PENDING" and row["entry_at_utc"] <= now_utc and row["next_attempt_at_utc"] <= now_utc][:limit]

    def update_signal_execution_intent(self, key, **changes):
        self.rows[key].update(changes)


class FakeMT5:
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_RETURN = 2
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_INVALID_FILL = 10030

    def __init__(self):
        self.sent = []

    def symbol_select(self, symbol, selected):
        return True

    def symbol_info(self, symbol):
        return SimpleNamespace(volume_min=0.01, volume_max=5.0, volume_step=0.01, filling_mode=1)

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(ask=1.2, bid=1.1)

    def positions_get(self, symbol=None):
        return []

    def orders_get(self, symbol=None):
        return []

    def order_send(self, request):
        self.sent.append(request.copy())
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, order=len(self.sent), deal=len(self.sent))


def ready_result():
    return {
        "logic_version": 87,
        "signal_state": "READY",
        "entry_state": "READY",
        "entry_time": "09:49",
        "pair_dirs": {symbol: "BUY" for symbol in SIGNAL_PAIRS},
        "pair_signal_states": {symbol: "READY" for symbol in SIGNAL_PAIRS},
        "pair_entry_times": {symbol: "09:49" for symbol in SIGNAL_PAIRS},
        "pair_entry_at_utc": {symbol: "2026-08-03T06:49:00Z" for symbol in SIGNAL_PAIRS},
    }


def test_schedule_is_idempotent_and_disabled_gateway_does_not_send():
    store = IntentStore()
    mt5 = FakeMT5()
    gateway = MT5ExecutionGateway(mt5, store, enabled=False)
    result = ready_result()
    first = gateway.schedule_signal(result, date(2026, 8, 3), 9)
    second = gateway.schedule_signal(result, date(2026, 8, 3), 9)
    assert first == second
    assert len(store.rows) == 5
    assert mt5.sent == []


def test_enabled_gateway_sends_each_common_entry_once():
    store = IntentStore()
    mt5 = FakeMT5()
    gateway = MT5ExecutionGateway(mt5, store, enabled=True)
    now = datetime(2026, 8, 3, 6, 50, tzinfo=timezone.utc)
    gateway.schedule_signal(ready_result(), date(2026, 8, 3), 9, now_utc=now)
    gateway.process_due(now_utc=now)
    assert len(mt5.sent) == 5
    assert {request["comment"] for request in mt5.sent}.__len__() == 5
    assert {row["status"] for row in store.rows.values()} == {"EXECUTED"}
