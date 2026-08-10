from domain.copy_trade_manager import CopyTradeManager


def test_scheduled_risk_denial_notifies_once_per_intent_and_reason():
    manager = object.__new__(CopyTradeManager)
    messages = []
    manager.notify = messages.append
    manager._risk_denial_notifications = set()
    trade = {"id": 12345}

    assert manager._notify_scheduled_risk_denial_once(
        "VantageDemo", trade, "EQUITY_HIGH_WATER_MARK_MISSING"
    ) is True
    assert manager._notify_scheduled_risk_denial_once(
        "VantageDemo", trade, "EQUITY_HIGH_WATER_MARK_MISSING"
    ) is False
    assert manager._notify_scheduled_risk_denial_once(
        "VantageDemo", trade, "ACCOUNT_SNAPSHOT_MISSING"
    ) is True

    assert len(messages) == 2
    assert "EQUITY_HIGH_WATER_MARK_MISSING" in messages[0]
    assert "ACCOUNT_SNAPSHOT_MISSING" in messages[1]


def test_scheduled_risk_denial_deduplication_is_per_intent():
    manager = object.__new__(CopyTradeManager)
    messages = []
    manager.notify = messages.append
    manager._risk_denial_notifications = set()

    assert manager._notify_scheduled_risk_denial_once(
        "VantageDemo", {"id": 10001}, "EQUITY_HIGH_WATER_MARK_MISSING"
    ) is True
    assert manager._notify_scheduled_risk_denial_once(
        "VantageDemo", {"id": 10002}, "EQUITY_HIGH_WATER_MARK_MISSING"
    ) is True

    assert len(messages) == 2
