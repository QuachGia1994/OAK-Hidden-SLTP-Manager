import time

from domain.copy_trade_manager import CopyTradeManager
from domain.json_io import load_json, save_json


def _manager(path):
    manager = object.__new__(CopyTradeManager)
    manager.scheduled_file = str(path)
    manager.scheduled_trades = load_json(str(path), [])
    manager.config = {"profile_name": "VantageDemo"}
    manager.notify = lambda message: manager.messages.append(message)
    manager.messages = []
    return manager


def test_scheduled_failure_retries_with_backoff_and_notifies_once(tmp_path):
    path = tmp_path / "waiting.json"
    save_json(str(path), [{"id": 42, "status": "executing"}])
    manager = _manager(path)
    trade = {"id": 42}

    manager._scheduled_failure_notify_once(trade, "MT5 unavailable", "mt5_unavailable")
    persisted = load_json(str(path), [])[0]
    first_retry = persisted["next_retry_at"]

    assert persisted["status"] == "waiting"
    assert first_retry > time.time()
    assert len(manager.messages) == 1

    manager._scheduled_failure_notify_once(trade, "MT5 unavailable", "mt5_unavailable")
    persisted_again = load_json(str(path), [])[0]

    assert persisted_again["next_retry_at"] > time.time()
    assert len(manager.messages) == 1


def test_changed_failure_reason_creates_one_new_notification_edge(tmp_path):
    path = tmp_path / "waiting.json"
    save_json(str(path), [{"id": 42, "status": "executing"}])
    manager = _manager(path)
    trade = {"id": 42}

    manager._scheduled_failure_notify_once(trade, "Market closed", "market_closed")
    manager._scheduled_failure_notify_once(trade, "Market closed", "market_closed")
    manager._scheduled_failure_notify_once(trade, "Broker rejected", "broker_rejected")

    assert len(manager.messages) == 2


def test_success_clears_retry_metadata(tmp_path):
    path = tmp_path / "waiting.json"
    save_json(
        str(path),
        [{
            "id": 42,
            "status": "waiting",
            "next_retry_at": time.time() + 5,
            "last_execution_failure": "market_closed",
        }],
    )
    manager = _manager(path)
    manager._finalize_scheduled_trade(42, "executed")

    persisted = load_json(str(path), [])[0]
    assert persisted["status"] == "executed"
    assert "next_retry_at" not in persisted
    assert "last_execution_failure" not in persisted
