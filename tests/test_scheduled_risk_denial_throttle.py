from domain.copy_trade_manager import CopyTradeManager
from domain.json_io import save_json, load_json


def _manager(scheduled_file, messages):
    manager = object.__new__(CopyTradeManager)
    manager.scheduled_file = str(scheduled_file)
    manager.notify = messages.append
    manager._risk_denial_notifications = set()
    return manager


def test_scheduled_risk_denial_notifies_once_per_persisted_intent_and_reason(tmp_path):
    scheduled_file = tmp_path / "waiting_VantageDemo.json"
    save_json(str(scheduled_file), [{"id": 12345, "status": "executing"}])

    messages_a = []
    messages_b = []
    manager_a = _manager(scheduled_file, messages_a)
    manager_b = _manager(scheduled_file, messages_b)
    trade = {"id": 12345}

    assert manager_a._notify_scheduled_risk_denial_once(
        "VantageDemo", trade, "EQUITY_HIGH_WATER_MARK_MISSING"
    ) is True
    assert manager_b._notify_scheduled_risk_denial_once(
        "VantageDemo", trade, "EQUITY_HIGH_WATER_MARK_MISSING"
    ) is False
    assert manager_b._notify_scheduled_risk_denial_once(
        "VantageDemo", trade, "ACCOUNT_SNAPSHOT_MISSING"
    ) is True

    assert len(messages_a) == 1
    assert len(messages_b) == 1
    assert "EQUITY_HIGH_WATER_MARK_MISSING" in messages_a[0]
    assert "ACCOUNT_SNAPSHOT_MISSING" in messages_b[0]


def test_scheduled_risk_denial_is_reset_after_risk_recovers(tmp_path):
    scheduled_file = tmp_path / "waiting_VantageDemo.json"
    save_json(str(scheduled_file), [{"id": 12345, "status": "executing"}])

    messages = []
    manager = _manager(scheduled_file, messages)
    trade = {"id": 12345}
    reason = "EQUITY_HIGH_WATER_MARK_MISSING"

    assert manager._notify_scheduled_risk_denial_once("VantageDemo", trade, reason) is True
    assert manager._notify_scheduled_risk_denial_once("VantageDemo", trade, reason) is False

    manager._clear_scheduled_risk_denial(trade)
    assert manager._notify_scheduled_risk_denial_once("VantageDemo", trade, reason) is True

    assert len(messages) == 2
    persisted = load_json(str(scheduled_file), [])
    assert "last_risk_denial_reason" in persisted[0]


def test_scheduled_risk_denial_deduplication_is_per_intent(tmp_path):
    manager = object.__new__(CopyTradeManager)
    messages = []
    manager.notify = messages.append
    manager._risk_denial_notifications = set()
    scheduled_file = tmp_path / "waiting.json"
    save_json(str(scheduled_file), [{"id": 10001, "status": "executing"}, {"id": 10002, "status": "executing"}])
    manager.scheduled_file = str(scheduled_file)

    assert manager._notify_scheduled_risk_denial_once(
        "VantageDemo", {"id": 10001}, "EQUITY_HIGH_WATER_MARK_MISSING"
    ) is True
    assert manager._notify_scheduled_risk_denial_once(
        "VantageDemo", {"id": 10002}, "EQUITY_HIGH_WATER_MARK_MISSING"
    ) is True

    assert len(messages) == 2
