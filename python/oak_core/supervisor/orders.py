# -*- coding: utf-8 -*-
"""Order management queries for the supervisor (Phase 4/5, Â§9).

Reads/writes the legacy sqlite_store (scheduled_trades, scheduled_close,
pending_partials) so the Tauri desktop mirrors the Native Qt "Chá» xá»­ lĂ½"
tab and the Telegram order commands. Execution itself stays in the Python
workers â€” the desktop only views and schedules.
"""
from pathlib import Path

from .accounts import _REPO_ROOT, _ensure_imports


def _store():
    _ensure_imports()
    from repositories.sqlite_store import SQLiteStore
    return SQLiteStore()


# --------------------------------------------------------------------- #
# Queries (read-only for the UI)
# --------------------------------------------------------------------- #
def scheduled_trades_list() -> list:
    try:
        store = _store()
        rows = store.get_scheduled_trades()
        result = []
        for r in rows:
            result.append({
                "id": r.get("id"),
                "symbol": r.get("symbol", ""),
                "type": r.get("type"),
                "lot": r.get("lot", ""),
                "sl": r.get("sl", "0"),
                "tp": r.get("tp", "0"),
                "time": r.get("time", ""),
                "date": r.get("date", ""),
                "status": r.get("status", "waiting"),
            })
        return result
    except Exception:
        return []


def scheduled_closes_list() -> list:
    try:
        store = _store()
        rows = store.get_scheduled_closes()
        result = []
        for r in rows:
            result.append({
                "id": r.get("id"),
                "time": r.get("time", ""),
                "date": r.get("date", ""),
                "filter": r.get("filter", "all"),
                "sym": r.get("sym", ""),
            })
        return result
    except Exception:
        return []


def pending_partials_list() -> list:
    try:
        store = _store()
        conn = getattr(store, "_conn", None)
        if conn is None:
            return []
        rows = conn.execute(
            "SELECT ticket, symbol, type, target_profit, close_volume, profile "
            "FROM pending_partials ORDER BY ticket"
        ).fetchall()
        result = []
        for r in rows:
            result.append({
                "ticket": r[0], "symbol": r[1], "type": r[2],
                "target_profit": r[3], "close_volume": r[4], "profile": r[5],
            })
        return result
    except Exception:
        return []


def orders_summary() -> dict:
    """All order-management sections in one call for the desktop UI."""
    return {
        "scheduled_trades": scheduled_trades_list(),
        "scheduled_closes": scheduled_closes_list(),
        "pending_partials": pending_partials_list(),
    }


# --------------------------------------------------------------------- #
# Writes (mirror Telegram command semantics, whitelisted fields only)
# --------------------------------------------------------------------- #
def add_scheduled_trade(symbol: str, order_type: int, lot: str,
                        time: str, date: str, sl: str = "0", tp: str = "0") -> dict:
    """Schedule an order (mirror of /set). Fields validated by the store."""
    store = _store()
    # The legacy table uses an explicit id; allocate max+1 (or 1 when empty).
    try:
        next_id = store._conn.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 FROM scheduled_trades"
        ).fetchone()[0]
    except Exception:
        next_id = 1
    trade = {
        "id": int(next_id), "symbol": str(symbol).upper(), "type": int(order_type),
        "lot": str(lot), "time": str(time), "date": str(date),
        "sl": str(sl), "tp": str(tp), "status": "waiting",
    }
    store.add_scheduled_trade(trade)
    return {"added": True, "trade": trade}


def delete_scheduled_trade(trade_id: int) -> dict:
    store = _store()
    store.delete_trade(int(trade_id))
    return {"deleted": True, "id": int(trade_id)}


def add_scheduled_close(time: str, date: str, filter: str = "all", sym: str = "") -> dict:
    store = _store()
    store.add_scheduled_close({
        "time": str(time), "date": str(date),
        "filter": str(filter), "sym": str(sym),
    })
    return {"added": True, "time": str(time), "date": str(date)}


def delete_scheduled_close(rowid: int) -> dict:
    store = _store()
    store.delete_scheduled_close(int(rowid))
    return {"deleted": True, "id": int(rowid)}


def clear_scheduled_closes() -> dict:
    store = _store()
    store.clear_scheduled_closes()
    return {"cleared": True}


