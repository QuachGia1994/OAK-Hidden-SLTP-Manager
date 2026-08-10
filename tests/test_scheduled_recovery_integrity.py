import time

from domain.copy_trade_manager import CopyTradeManager
from domain.json_io import load_json, save_json


def _manager(path):
    manager = object.__new__(CopyTradeManager)
    manager.scheduled_file = str(path)
    manager.scheduled_trades = load_json(str(path), [])
    manager.config = {"profile_name": "VantageDemo"}
    manager.notify = lambda *_args, **_kwargs: None
    return manager


def test_scheduled_claim_is_exactly_once_across_two_workers(tmp_path):
    path = tmp_path / "waiting.json"
    save_json(str(path), [{"id": 12345, "status": "waiting", "symbol": "XAUUSD"}])

    first = _manager(path)
    second = _manager(path)

    claimed_a = first._claim_scheduled_trade(12345)
    claimed_b = second._claim_scheduled_trade(12345)

    assert claimed_a is not None
    assert claimed_a["status"] == "executing"
    assert claimed_b is None
    assert load_json(str(path), [])[0]["status"] == "executing"


def test_stale_scheduled_claim_is_recoverable_after_worker_restart(tmp_path):
    path = tmp_path / "waiting.json"
    save_json(
        str(path),
        [{"id": 12345, "status": "executing", "claimed_by": 111, "claimed_at": time.time() - 60}],
    )

    restarted = _manager(path)
    claimed = restarted._claim_scheduled_trade(12345, stale_executing_sec=45)

    assert claimed is not None
    assert claimed["status"] == "executing"
    assert claimed["claimed_by"] != 111


def test_fresh_scheduled_claim_is_not_stolen(tmp_path):
    path = tmp_path / "waiting.json"
    save_json(
        str(path),
        [{"id": 12345, "status": "executing", "claimed_by": 111, "claimed_at": time.time()}],
    )

    other = _manager(path)
    assert other._claim_scheduled_trade(12345, stale_executing_sec=45) is None


def test_scheduled_finalize_persists_terminal_state(tmp_path):
    path = tmp_path / "waiting.json"
    save_json(
        str(path),
        [{"id": 12345, "status": "executing", "claimed_by": 111, "claimed_at": time.time()}],
    )

    manager = _manager(path)
    manager._finalize_scheduled_trade(12345, "executed")
    trade = load_json(str(path), [])[0]

    assert trade["status"] == "executed"
    assert "claimed_by" not in trade
    assert "claimed_at" not in trade
