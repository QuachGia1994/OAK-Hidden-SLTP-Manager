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

    def __init__(self, balance=5000.0, equity=5000.0, login=123, mode="done"):
        self.sent = []
        self.balance = balance
        self.equity = equity
        self.login = login
        self.mode = mode

    def account_info(self):
        return SimpleNamespace(balance=self.balance, equity=self.equity, login=self.login)

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
        if self.mode == "unknown":
            raise TimeoutError("broker response lost")
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, order=len(self.sent), deal=len(self.sent))


def ready_result(entry_at_utc="2026-08-03T06:49:00Z"):
    return {
        "logic_version": 88,
        "signal": "BUY",
        "signal_state": "READY",
        "entry_state": "READY",
        "entry_time": "09:49",
        "hour": 9,
        "applicable_pairs": ["XAUUSD", "GBPUSD", "GBPCAD"],
        "pair_dirs": {"XAUUSD": "BUY", "GBPUSD": "BUY", "GBPAUD": None, "GBPJPY": None, "GBPCAD": "BUY"},
        "pair_signal_states": {"XAUUSD": "READY", "GBPUSD": "READY", "GBPAUD": "NOT_APPLICABLE", "GBPJPY": "NOT_APPLICABLE", "GBPCAD": "READY"},
        "pair_entry_times": {"XAUUSD": "09:49", "GBPUSD": "09:49", "GBPAUD": None, "GBPJPY": None, "GBPCAD": "09:49"},
        "pair_entry_at_utc": {"XAUUSD": "2026-08-03T06:49:00Z", "GBPUSD": "2026-08-03T06:49:00Z", "GBPCAD": "2026-08-03T06:49:00Z"},
    }


def test_schedule_is_idempotent_and_disabled_gateway_does_not_send():
    store = IntentStore()
    mt5 = FakeMT5()
    gateway = MT5ExecutionGateway(mt5, store, enabled=False)
    result = ready_result()
    now = datetime(2026, 8, 3, 6, 50, tzinfo=timezone.utc)
    first = gateway.schedule_signal(result, date(2026, 8, 3), 9, now_utc=now)
    second = gateway.schedule_signal(result, date(2026, 8, 3), 9, now_utc=now)
    assert first == second
    # H9 is slot-scoped: only XAUUSD, GBPUSD, GBPCAD get intents.
    assert len(store.rows) == 3
    assert all("GBPAUD" not in key and "GBPJPY" not in key for key in store.rows)
    assert mt5.sent == []


def test_risk_gate_blocks_order_when_drawdown_exceeds_limit(tmp_path):
    store = IntentStore()
    mt5 = FakeMT5(balance=5000.0, equity=4699.0)
    gateway = MT5ExecutionGateway(mt5, store, enabled=True, initial_peak_equity=5000.0, risk_state_dir=str(tmp_path))
    now = datetime(2026, 8, 3, 6, 50, tzinfo=timezone.utc)
    gateway.schedule_signal(ready_result(entry_at_utc="2026-08-03T06:49:00Z"), date(2026, 8, 3), 9, now_utc=now)
    gateway.process_due(now_utc=now)
    assert mt5.sent == []
    assert all(row["status"] == "PENDING" for row in store.rows.values())
    assert all("DRAWDOWN_LIMIT_EXCEEDED" in row["last_error"] for row in store.rows.values())


def test_unknown_broker_outcome_is_terminal_until_reconciled(tmp_path):
    store = IntentStore()
    mt5 = FakeMT5(mode="unknown")
    gateway = MT5ExecutionGateway(mt5, store, enabled=True, initial_peak_equity=5000.0, risk_state_dir=str(tmp_path))
    now = datetime(2026, 8, 3, 6, 50, tzinfo=timezone.utc)
    gateway.schedule_signal(ready_result(entry_at_utc="2026-08-03T06:49:00Z"), date(2026, 8, 3), 9, now_utc=now)
    gateway.process_due(now_utc=now)
    assert len(mt5.sent) == 3
    assert all(row["status"] == "UNKNOWN" for row in store.rows.values())
    assert all("UNKNOWN broker outcome" in row["last_error"] for row in store.rows.values())
    assert gateway.process_due(now_utc=now) == []
    assert len(mt5.sent) == 3


class FakeHealthProvider:
    def __init__(self, *, fresh=True, degraded=False, clock_verified=True, error=None):
        self.health = SimpleNamespace(
            fresh=fresh,
            degraded=degraded,
            clock_verified=clock_verified,
        )
        self.error = error

    def get_health(self):
        if self.error:
            raise self.error
        return self.health


def _gateway_with_health(tmp_path, health):
    store = IntentStore()
    mt5 = FakeMT5()
    gateway = MT5ExecutionGateway(
        mt5,
        store,
        enabled=True,
        initial_peak_equity=5000.0,
        risk_state_dir=str(tmp_path),
        health_provider=health,
    )
    now = datetime(2026, 8, 3, 6, 50, tzinfo=timezone.utc)
    gateway.schedule_signal(ready_result(entry_at_utc="2026-08-03T06:49:00Z"), date(2026, 8, 3), 9, now_utc=now)
    return gateway, store, mt5, now


def test_stale_market_data_fails_closed_before_order_send(tmp_path):
    gateway, store, mt5, now = _gateway_with_health(
        tmp_path, FakeHealthProvider(fresh=False)
    )
    gateway.process_due(now_utc=now)
    assert mt5.sent == []
    assert all(row["status"] == "PENDING" for row in store.rows.values())
    assert all("MARKET_DATA_STALE" in row["last_error"] for row in store.rows.values())


def test_degraded_market_data_fails_closed_before_order_send(tmp_path):
    gateway, store, mt5, now = _gateway_with_health(
        tmp_path, FakeHealthProvider(fresh=True, degraded=True)
    )
    gateway.process_due(now_utc=now)
    assert mt5.sent == []
    assert all("MARKET_DATA_DEGRADED" in row["last_error"] for row in store.rows.values())


def test_unverified_broker_clock_fails_closed_before_order_send(tmp_path):
    gateway, store, mt5, now = _gateway_with_health(
        tmp_path, FakeHealthProvider(fresh=True, clock_verified=False)
    )
    gateway.process_due(now_utc=now)
    assert mt5.sent == []
    assert all("BROKER_CLOCK_UNVERIFIED" in row["last_error"] for row in store.rows.values())


def test_health_provider_error_fails_closed_before_order_send(tmp_path):
    gateway, store, mt5, now = _gateway_with_health(
        tmp_path, FakeHealthProvider(error=RuntimeError("health unavailable"))
    )
    gateway.process_due(now_utc=now)
    assert mt5.sent == []
    assert all("MARKET_DATA_HEALTH_ERROR" in row["last_error"] for row in store.rows.values())


def test_healthy_market_data_allows_entry(tmp_path):
    gateway, store, mt5, now = _gateway_with_health(
        tmp_path, FakeHealthProvider()
    )
    gateway.process_due(now_utc=now)
    assert len(mt5.sent) == 3
    assert {row["status"] for row in store.rows.values()} == {"EXECUTED"}


def test_enabled_gateway_sends_each_common_entry_once(tmp_path):
    store = IntentStore()
    mt5 = FakeMT5()
    gateway = MT5ExecutionGateway(mt5, store, enabled=True, initial_peak_equity=5000.0, risk_state_dir=str(tmp_path))
    now = datetime(2026, 8, 3, 6, 50, tzinfo=timezone.utc)
    gateway.schedule_signal(ready_result(entry_at_utc="2026-08-03T06:49:00Z"), date(2026, 8, 3), 9, now_utc=now)
    gateway.process_due(now_utc=now)
    assert len(mt5.sent) == 3
    assert {request["comment"] for request in mt5.sent}.__len__() == 3
    assert {row["status"] for row in store.rows.values()} == {"EXECUTED"}
