from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative):
    return (ROOT / relative).read_text(encoding="utf-8", errors="replace")


def test_signal_gateway_uses_live_market_health_gate_before_risk_and_order_send():
    source = _source("domain/mt5_execution.py")
    assert "health_provider" in source
    assert "_evaluate_execution_health()" in source
    assert source.index("_evaluate_execution_health()") < source.index("evaluate_mt5_account_risk(")
    assert source.index("evaluate_mt5_account_risk(") < source.index("self.mt5.order_send(")


def test_production_signal_gateway_wires_market_data_health_provider():
    source = _source("mt5_signal_bot.py")
    start = source.index("_signal_execution_gateway = MT5ExecutionGateway(")
    end = source.index("    return _signal_execution_gateway", start)
    body = source[start:end]
    assert "health_provider=MARKET_DATA_PROVIDER" in body


def test_signal_gateway_uses_live_risk_gate_before_order_send():
    source = _source("domain/mt5_execution.py")
    assert "evaluate_mt5_account_risk(" in source
    assert source.index("evaluate_mt5_account_risk(") < source.index("self.mt5.order_send(")


def test_scheduled_entry_risk_gate_is_opt_in_and_never_blocks_legacy_profiles():
    source = _source("domain/copy_trade_manager.py")
    start = source.index("def _send_scheduled_market_order")
    end = source.index("def _execute_scheduled", start)
    body = source[start:end]
    assert "risk_gate_enabled" in body
    assert "use_balance_sltp" in body
    assert "evaluate_mt5_account_risk(" in body
    assert body.index("risk_enabled =") < body.index("evaluate_mt5_account_risk(")
    assert body.index("risk_enabled =") < body.index("self._prepare_scheduled_trade(")
    assert body.index("self._prepare_scheduled_trade(") < body.index("send_order_idempotent(")


def test_default_profile_does_not_enable_equity_fdd_gate():
    profile = __import__("json").loads(_source("profiles.json"))["VantageDemo"]
    assert profile.get("use_balance_sltp") is False
    assert profile.get("risk_gate_enabled", False) is False
    assert profile.get("risk_initial_peak_equity") in (None, "")
    assert profile.get("risk_max_drawdown_pct") in (None, "")
    assert profile.get("risk_max_volume") in (None, "")


def test_copy_entry_uses_live_risk_gate_before_send():
    source = _source("domain/copy_trade_manager.py")
    start = source.index("def _open_copy_trade")
    end = source.index("def _close_copy_trade", start)
    body = source[start:end]
    assert "evaluate_mt5_account_risk(" in body
    assert body.index("evaluate_mt5_account_risk(") < body.index("send_order_idempotent(")


def test_copy_entry_has_stable_idempotency_key():
    source = _source("domain/copy_trade_manager.py")
    start = source.index("def _open_copy_trade")
    end = source.index("def _close_copy_trade", start)
    body = source[start:end]
    assert 'f"copy:{profile_name}:{m_ticket}"' in body


def test_scheduled_entry_retries_only_after_safe_reconciliation():
    source = _source("domain/copy_trade_manager.py")
    start = source.index("def _send_scheduled_market_order")
    end = source.index("def _execute_scheduled", start)
    body = source[start:end]
    assert "send_order_idempotent(" in body
    assert 'f"scheduled:{profile_name}:{trade.get(\'id\')}"' in body


def test_scheduled_failure_does_not_get_marked_executed():
    source = _source("domain/copy_trade_manager.py")
    start = source.index("claimed = self._claim_scheduled_trade")
    end = source.index("# Check scheduled close all", start)
    body = source[start:end]
    assert 'result == "done"' in body
    assert 'result == "skip"' in body
    assert "_schedule_scheduled_retry(" in body
    assert '"executed")' in body

    prep_start = source.index("def _prepare_scheduled_trade")
    prep_end = source.index("def _remove_pending_order", prep_start)
    prep_body = source[prep_start:prep_end]
    assert 'failed to close opposite' in prep_body
    assert 'failed to remove opposite pending' in prep_body


def test_idempotent_helper_is_used_for_entry_paths():
    source = _source("domain/mt5_orders.py")
    assert "def send_order_idempotent(" in source
    source_copy = _source("domain/copy_trade_manager.py")
    assert "send_order_idempotent(" in source_copy


def test_manual_entry_uses_live_risk_gate_before_any_order_send():
    source = _source("controllers/pending_controller.py")
    start = source.index("def send_order")
    end = source.index("# --- SCHEDULED ORDER HELPERS ---", start)
    body = source[start:end]
    assert "evaluate_mt5_account_risk(" in body
    assert body.index("evaluate_mt5_account_risk(") < body.index("mt5.order_send(req_c)")
    assert body.index("evaluate_mt5_account_risk(") < body.index("send_order_idempotent(req,")
    assert "mt5.order_send(req)" not in body
    assert "_manual_idempotency_keys" in body
    assert 'result["status"] == "UNKNOWN"' in body
    assert "could not be closed" in body
    assert "could not be removed" in body
