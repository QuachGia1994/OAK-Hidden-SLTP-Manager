from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative):
    return (ROOT / relative).read_text(encoding="utf-8", errors="replace")


def test_signal_gateway_uses_live_risk_gate_before_order_send():
    source = _source("domain/mt5_execution.py")
    assert "evaluate_mt5_account_risk(" in source
    assert source.index("evaluate_mt5_account_risk(") < source.index("self.mt5.order_send(")


def test_scheduled_entry_uses_live_risk_gate_before_preparation():
    source = _source("domain/copy_trade_manager.py")
    start = source.index("def _send_scheduled_market_order")
    end = source.index("def _execute_scheduled", start)
    body = source[start:end]
    assert "evaluate_mt5_account_risk(" in body
    assert body.index("evaluate_mt5_account_risk(") < body.index("self._prepare_scheduled_trade(")
    assert body.index("evaluate_mt5_account_risk(") < body.index("send_order_with_retry(")


def test_copy_entry_uses_live_risk_gate_before_send():
    source = _source("domain/copy_trade_manager.py")
    start = source.index("def _open_copy_trade")
    end = source.index("def _close_copy_trade", start)
    body = source[start:end]
    assert "evaluate_mt5_account_risk(" in body
    assert body.index("evaluate_mt5_account_risk(") < body.index("send_order_with_retry(")


def test_manual_entry_uses_live_risk_gate_before_any_order_send():
    source = _source("controllers/pending_controller.py")
    start = source.index("def send_order")
    end = source.index("# --- SCHEDULED ORDER HELPERS ---", start)
    body = source[start:end]
    assert "evaluate_mt5_account_risk(" in body
    assert body.index("evaluate_mt5_account_risk(") < body.index("mt5.order_send(req_c)")
    assert body.index("evaluate_mt5_account_risk(") < body.index("res = mt5.order_send(req)")
