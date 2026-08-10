from datetime import datetime, timezone

from domain.mt5_execution import UNKNOWN_NEXT_ATTEMPT_AT_UTC
from repositories.sqlite_store import SQLiteStore


def _intent():
    now = "2026-08-10T12:00:00Z"
    return {
        "idempotency_key": "88|2026-08-10|9|XAUUSD|09:49|BUY",
        "logic_version": 88,
        "broker_date": "2026-08-10",
        "slot_hour": 9,
        "symbol": "XAUUSD",
        "common_entry_time": "09:49",
        "direction": "BUY",
        "entry_at_utc": now,
        "status": "PENDING",
        "attempts": 0,
        "next_attempt_at_utc": now,
        "order_ticket": None,
        "last_error": "",
        "created_at_utc": now,
        "updated_at_utc": now,
    }


def test_unknown_intent_is_persistable_and_not_due(tmp_path):
    store = SQLiteStore(str(tmp_path / "state.db"))
    intent = _intent()
    store.upsert_signal_execution_intent(intent)
    store.update_signal_execution_intent(
        intent["idempotency_key"],
        status="UNKNOWN",
        attempts=1,
        next_attempt_at_utc=UNKNOWN_NEXT_ATTEMPT_AT_UTC,
        last_error="UNKNOWN broker outcome: response lost",
        updated_at_utc="2026-08-10T12:01:00Z",
    )

    row = store._conn.execute(
        "SELECT status, attempts, next_attempt_at_utc, last_error FROM signal_execution_intents WHERE idempotency_key=?",
        (intent["idempotency_key"],),
    ).fetchone()

    assert dict(row) == {
        "status": "UNKNOWN",
        "attempts": 1,
        "next_attempt_at_utc": UNKNOWN_NEXT_ATTEMPT_AT_UTC,
        "last_error": "UNKNOWN broker outcome: response lost",
    }
    assert store.get_due_signal_execution_intents("2026-08-10T12:02:00Z") == []
    store.close()
