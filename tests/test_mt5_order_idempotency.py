from types import SimpleNamespace

from domain.mt5_orders import send_mutation_idempotent, send_order_idempotent
from repositories.sqlite_store import SQLiteStore


class FakeMT5:
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_RETURN = 2
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_DONE_PARTIAL = 10010
    TRADE_RETCODE_INVALID_FILL = 10030

    def __init__(self, mode="done"):
        self.mode = mode
        self.calls = 0
        self.positions = []
        self.orders = []

    def positions_get(self, symbol=None):
        return [p for p in self.positions if symbol is None or p.symbol == symbol]

    def orders_get(self, symbol=None):
        return [o for o in self.orders if symbol is None or o.symbol == symbol]

    def order_send(self, request):
        self.calls += 1
        if self.mode == "existing_then_exception":
            self.positions.append(SimpleNamespace(ticket=77, symbol=request["symbol"], comment=request["comment"]))
            raise TimeoutError("broker response lost")
        if self.mode == "unknown":
            raise TimeoutError("broker response lost")
        if self.mode == "invalid_fill_then_done" and self.calls == 1:
            return SimpleNamespace(retcode=self.TRADE_RETCODE_INVALID_FILL, comment="invalid fill")
        self.positions.append(SimpleNamespace(ticket=100 + self.calls, symbol=request["symbol"], comment=request["comment"]))
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, order=100 + self.calls, deal=200 + self.calls)


def request():
    return {
        "action": 1,
        "symbol": "XAUUSD",
        "volume": 0.01,
        "type": 0,
        "type_filling": 1,
    }


def test_existing_order_is_reconciled_without_send(tmp_path):
    mt5 = FakeMT5()
    store = SQLiteStore(str(tmp_path / "state.db"))
    first = send_order_idempotent(request(), "scheduled:demo:42", mt5_module=mt5)
    second = send_order_idempotent(request(), "scheduled:demo:42", mt5_module=mt5)
    store.close()
    assert first["status"] == "DONE"
    assert second["status"] == "EXISTING"
    assert mt5.calls == 1


def test_ambiguous_exception_after_broker_acceptance_is_reconciled(tmp_path):
    mt5 = FakeMT5("existing_then_exception")
    result = send_order_idempotent(request(), "copy:demo:123", mt5_module=mt5)
    assert result["status"] == "EXISTING"
    assert result["ticket"] == 77
    assert mt5.calls == 1


def test_ambiguous_exception_without_existing_order_is_not_retried_blindly(tmp_path):
    mt5 = FakeMT5("unknown")
    result = send_order_idempotent(request(), "copy:demo:123", mt5_module=mt5)
    assert result["status"] == "UNKNOWN"
    assert mt5.calls == 1


def test_invalid_fill_is_the_only_retryable_send_error(tmp_path):
    mt5 = FakeMT5("invalid_fill_then_done")
    result = send_order_idempotent(request(), "scheduled:demo:42", mt5_module=mt5)
    assert result["status"] == "DONE"
    assert mt5.calls == 2


def test_mutation_unknown_is_not_retried_blindly(tmp_path):
    mt5 = FakeMT5("unknown")
    store = SQLiteStore(str(tmp_path / "state.db"))
    result = send_mutation_idempotent(request(), "close:demo:77", mt5_module=mt5, mutation_store=store)
    store.close()
    assert result["status"] == "UNKNOWN"
    assert mt5.calls == 1


def test_mutation_exception_can_be_reconciled(tmp_path):
    mt5 = FakeMT5("unknown")
    store = SQLiteStore(str(tmp_path / "state.db"))
    result = send_mutation_idempotent(
        request(),
        "close:demo:77",
        mt5_module=mt5,
        reconcile=lambda: 77,
        mutation_store=store,
    )
    store.close()
    assert result["status"] == "EXISTING"
    assert result["ticket"] == 77
    assert mt5.calls == 1


def test_mutation_explicit_rejection_is_not_retried_without_invalid_fill(tmp_path):
    mt5 = FakeMT5()
    mt5.order_send = lambda _request: SimpleNamespace(retcode=10013, comment="rejected")
    store = SQLiteStore(str(tmp_path / "state.db"))
    result = send_mutation_idempotent(request(), "modify:demo:77", mt5_module=mt5, mutation_store=store)
    store.close()
    assert result["status"] == "REJECTED"


def test_mutation_unknown_survives_restart_and_blocks_second_send(tmp_path):
    db_path = tmp_path / "state.db"
    first_store = SQLiteStore(str(db_path))
    mt5 = FakeMT5("unknown")
    first = send_mutation_idempotent(
        request(), "close:demo:900", mt5_module=mt5, mutation_store=first_store
    )
    first_store.close()
    second_store = SQLiteStore(str(db_path))
    second = send_mutation_idempotent(
        request(), "close:demo:900", mt5_module=mt5, mutation_store=second_store
    )
    row = second_store.get_mutation_intent("close:demo:900")
    second_store.close()
    assert first["status"] == "UNKNOWN"
    assert second["status"] == "UNKNOWN"
    assert row["status"] == "UNKNOWN"
    assert mt5.calls == 1


def test_mutation_claim_prevents_concurrent_second_sender(tmp_path):
    store = SQLiteStore(str(tmp_path / "state.db"))
    now = "2026-08-10T12:00:00+00:00"
    store.upsert_mutation_intent({
        "idempotency_key": "close:demo:901",
        "operation": "CLOSE",
        "profile": "demo",
        "symbol": "XAUUSD",
        "target_ticket": 901,
        "status": "PENDING",
        "attempts": 0,
        "order_ticket": None,
        "next_attempt_at_utc": now,
        "last_error": "",
        "created_at_utc": now,
        "updated_at_utc": now,
    })
    first, first_claimed = store.claim_mutation_intent("close:demo:901", now)
    second, second_claimed = store.claim_mutation_intent("close:demo:901", now)
    store.close()
    assert first_claimed is True
    assert first["status"] == "EXECUTING"
    assert second_claimed is False
    assert second["status"] == "EXECUTING"


def test_stale_executing_reconciles_without_resend(tmp_path):
    store = SQLiteStore(str(tmp_path / "state.db"))
    now = "2026-08-10T12:00:00+00:00"
    store.upsert_mutation_intent({
        "idempotency_key": "close:demo:902",
        "operation": "CLOSE",
        "profile": "demo",
        "symbol": "XAUUSD",
        "target_ticket": 902,
        "status": "EXECUTING",
        "attempts": 1,
        "order_ticket": None,
        "next_attempt_at_utc": now,
        "last_error": "",
        "created_at_utc": now,
        "updated_at_utc": now,
    })
    mt5 = FakeMT5()
    result = send_mutation_idempotent(
        request(),
        "close:demo:902",
        mt5_module=mt5,
        reconcile=lambda: 902,
        mutation_store=store,
    )
    row = store.get_mutation_intent("close:demo:902")
    store.close()
    assert result["status"] == "EXISTING"
    assert result["ticket"] == 902
    assert mt5.calls == 0
    assert row["status"] == "EXISTING"


def test_stale_executing_without_reconcile_becomes_unknown_and_blocks_resend(tmp_path):
    store = SQLiteStore(str(tmp_path / "state.db"))
    now = "2026-08-10T12:00:00+00:00"
    store.upsert_mutation_intent({
        "idempotency_key": "close:demo:903",
        "operation": "CLOSE",
        "profile": "demo",
        "symbol": "XAUUSD",
        "target_ticket": 903,
        "status": "EXECUTING",
        "attempts": 1,
        "order_ticket": None,
        "next_attempt_at_utc": now,
        "last_error": "",
        "created_at_utc": now,
        "updated_at_utc": now,
    })
    mt5 = FakeMT5()
    result = send_mutation_idempotent(
        request(),
        "close:demo:903",
        mt5_module=mt5,
        reconcile=lambda: None,
        mutation_store=store,
    )
    row = store.get_mutation_intent("close:demo:903")
    store.close()
    assert result["status"] == "UNKNOWN"
    assert mt5.calls == 0
    assert row["status"] == "UNKNOWN"
