from types import SimpleNamespace

from domain.mt5_orders import send_order_idempotent


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


def test_existing_order_is_reconciled_without_send():
    mt5 = FakeMT5()
    first = send_order_idempotent(request(), "scheduled:demo:42", mt5_module=mt5)
    second = send_order_idempotent(request(), "scheduled:demo:42", mt5_module=mt5)
    assert first["status"] == "DONE"
    assert second["status"] == "EXISTING"
    assert mt5.calls == 1


def test_ambiguous_exception_after_broker_acceptance_is_reconciled():
    mt5 = FakeMT5("existing_then_exception")
    result = send_order_idempotent(request(), "copy:demo:123", mt5_module=mt5)
    assert result["status"] == "EXISTING"
    assert result["ticket"] == 77
    assert mt5.calls == 1


def test_ambiguous_exception_without_existing_order_is_not_retried_blindly():
    mt5 = FakeMT5("unknown")
    result = send_order_idempotent(request(), "copy:demo:123", mt5_module=mt5)
    assert result["status"] == "UNKNOWN"
    assert mt5.calls == 1


def test_invalid_fill_is_the_only_retryable_send_error():
    mt5 = FakeMT5("invalid_fill_then_done")
    result = send_order_idempotent(request(), "scheduled:demo:42", mt5_module=mt5)
    assert result["status"] == "DONE"
    assert mt5.calls == 2
