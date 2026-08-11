# -*- coding: utf-8 -*-
"""MT5 order send helpers."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import MetaTrader5 as mt5


def _default_mutation_store():
    """Lazily open the durable mutation ledger without creating import cycles."""
    from repositories.sqlite_store import SQLiteStore
    return SQLiteStore()


def _mutation_operation(idempotency_key):
    return str(idempotency_key).split(":", 1)[0].upper() or "MUTATION"


def _mutation_target_ticket(request):
    for field in ("position", "order"):
        value = request.get(field)
        if value not in (None, ""):
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


def _mutation_ledger_start(store, key, request):
    """Persist the mutation before the first broker-facing call."""
    now = datetime.now(timezone.utc).isoformat()
    existing = store.get_mutation_intent(key)
    if existing:
        return existing
    intent = {
        "idempotency_key": key,
        "operation": _mutation_operation(key),
        "profile": str(key).split(":")[1] if ":" in key else "",
        "symbol": request.get("symbol", ""),
        "target_ticket": _mutation_target_ticket(request),
        "status": "PENDING",
        "attempts": 0,
        "order_ticket": None,
        "next_attempt_at_utc": now,
        "last_error": "",
        "created_at_utc": now,
        "updated_at_utc": now,
    }
    store.upsert_mutation_intent(intent)
    return store.get_mutation_intent(key) or intent


def _mutation_ledger_update(store, key, status, *, ticket=None, error="", attempts=None):
    now = datetime.now(timezone.utc).isoformat()
    changes = {
        "status": status,
        "updated_at_utc": now,
        "last_error": error,
    }
    if ticket is not None:
        changes["order_ticket"] = ticket
    if attempts is not None:
        changes["attempts"] = attempts
    if status == "UNKNOWN":
        changes["next_attempt_at_utc"] = "9999-12-31T23:59:59+00:00"
    else:
        changes["next_attempt_at_utc"] = now
    store.update_mutation_intent(key, **changes)


def get_filling_type(symbol):
    """Dynamically select a supported filling mode."""
    if not mt5.symbol_select(symbol, True):
        return mt5.ORDER_FILLING_IOC
    info = mt5.symbol_info(symbol)
    if info is None:
        return mt5.ORDER_FILLING_IOC
    filling_mode = info.filling_mode
    if filling_mode in (mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN):
        return filling_mode
    if isinstance(filling_mode, int):
        if filling_mode & 2:
            return mt5.ORDER_FILLING_IOC
        if filling_mode & 1:
            return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_IOC


def send_order_with_retry(request):
    """Send order, retry with alternate filling modes only on explicit 10030 rejection."""
    res = mt5.order_send(request)
    if getattr(res, "retcode", None) != 10030:
        return res
    modes = [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN]
    current_mode = request["type_filling"]
    if current_mode in modes:
        modes.remove(current_mode)
    for mode in modes:
        request["type_filling"] = mode
        res = mt5.order_send(request)
        if getattr(res, "retcode", None) != 10030:
            break
    return res


def _existing_order_by_comment(mt5_module, symbol, comment):
    """Find a previously accepted order/position by deterministic client key."""
    if not comment:
        return None
    for getter in (mt5_module.positions_get, mt5_module.orders_get):
        try:
            rows = getter(symbol=symbol) or []
        except TypeError:
            rows = getter() or []
        for row in rows:
            if getattr(row, "comment", "") == comment:
                return getattr(row, "ticket", None) or getattr(row, "order", None)
    return None


def send_mutation_idempotent(request, idempotency_key, *, mt5_module=None, reconcile=None, mutation_store=None):
    """Execute one non-entry mutation without blind retry on UNKNOWN.

    ``reconcile`` is a caller-supplied broker-state check that returns the
    resulting ticket/state when the mutation is known to have taken effect,
    or ``None`` when the outcome remains ambiguous. Explicit invalid-fill
    rejection is the only transport-level retry, matching entry semantics.
    """
    module = mt5_module or mt5
    key = str(idempotency_key or "").strip()
    if not key:
        raise ValueError("idempotency_key is required")
    request = dict(request)
    symbol = request.get("symbol")
    reconcile = reconcile or (lambda: None)
    store = mutation_store or _default_mutation_store()
    ledger = _mutation_ledger_start(store, key, request)
    if ledger.get("status") in ("DONE", "EXISTING"):
        return {"status": "EXISTING", "ticket": ledger.get("order_ticket"), "response": None}
    if ledger.get("status") in ("UNKNOWN", "EXECUTING"):
        # EXECUTING after process death must not re-send; only reconcile.
        try:
            state = reconcile()
        except Exception:
            state = None
        if state is not None:
            _mutation_ledger_update(store, key, "EXISTING", ticket=state, attempts=ledger.get("attempts", 0))
            return {"status": "EXISTING", "ticket": state, "response": None}
        if ledger.get("status") == "EXECUTING":
            _mutation_ledger_update(
                store,
                key,
                "UNKNOWN",
                error=ledger.get("last_error") or "stale EXECUTING; reconciliation required",
                attempts=ledger.get("attempts", 0),
            )
        return {
            "status": "UNKNOWN",
            "ticket": None,
            "response": None,
            "error": ledger.get("last_error") or "UNKNOWN requires reconciliation",
        }
    if ledger.get("status") == "REJECTED":
        store.update_mutation_intent(
            key,
            status="PENDING",
            next_attempt_at_utc=datetime.now(timezone.utc).isoformat(),
            updated_at_utc=datetime.now(timezone.utc).isoformat(),
        )
    now = datetime.now(timezone.utc).isoformat()
    claimed, did_claim = store.claim_mutation_intent(key, now)
    if not did_claim:
        if claimed and claimed.get("status") == "EXECUTING":
            # Process death can leave EXECUTING; never re-send — only reconcile.
            try:
                state = reconcile()
            except Exception:
                state = None
            if state is not None:
                _mutation_ledger_update(
                    store, key, "EXISTING", ticket=state, attempts=claimed.get("attempts", 0)
                )
                return {"status": "EXISTING", "ticket": state, "response": None}
            _mutation_ledger_update(
                store,
                key,
                "UNKNOWN",
                error=claimed.get("last_error") or "stale EXECUTING; reconciliation required",
                attempts=claimed.get("attempts", 0),
            )
            return {
                "status": "UNKNOWN",
                "ticket": None,
                "response": None,
                "error": "stale EXECUTING; reconciliation required",
            }
        if claimed and claimed.get("status") == "UNKNOWN":
            return {"status": "UNKNOWN", "ticket": None, "response": None, "error": claimed.get("last_error", "UNKNOWN requires reconciliation")}
        if claimed and claimed.get("status") in ("DONE", "EXISTING"):
            return {"status": "EXISTING", "ticket": claimed.get("order_ticket"), "response": None}
        return {"status": "UNKNOWN", "ticket": None, "response": None, "error": "mutation claim failed"}
    attempts = int(claimed.get("attempts", 1))

    try:
        response = module.order_send(request)
    except Exception as exc:
        try:
            state = reconcile()
        except Exception as reconcile_exc:
            state = None
            error = f"{exc}; reconciliation failed: {reconcile_exc}"
        else:
            error = str(exc)
        if state is not None:
            _mutation_ledger_update(store, key, "EXISTING", ticket=state, error=error, attempts=attempts)
            return {"status": "EXISTING", "ticket": state, "response": None}
        _mutation_ledger_update(store, key, "UNKNOWN", error=error, attempts=attempts)
        return {"status": "UNKNOWN", "ticket": None, "response": None, "error": error}

    retcode = getattr(response, "retcode", None)
    done_codes = {
        getattr(module, "TRADE_RETCODE_DONE", 10009),
        getattr(module, "TRADE_RETCODE_DONE_PARTIAL", 10010),
    }
    invalid_fill = getattr(module, "TRADE_RETCODE_INVALID_FILL", 10030)
    if retcode == invalid_fill:
        modes = [
            getattr(module, "ORDER_FILLING_IOC", None),
            getattr(module, "ORDER_FILLING_FOK", None),
            getattr(module, "ORDER_FILLING_RETURN", None),
        ]
        current = request.get("type_filling")
        for mode in dict.fromkeys(m for m in modes if m is not None and m != current):
            request["type_filling"] = mode
            try:
                response = module.order_send(request)
            except Exception as exc:
                try:
                    state = reconcile()
                except Exception as reconcile_exc:
                    state = None
                    error = f"{exc}; reconciliation failed: {reconcile_exc}"
                else:
                    error = str(exc)
                if state is not None:
                    _mutation_ledger_update(store, key, "EXISTING", ticket=state, error=error, attempts=attempts)
                    return {"status": "EXISTING", "ticket": state, "response": None}
                _mutation_ledger_update(store, key, "UNKNOWN", error=error, attempts=attempts)
                return {"status": "UNKNOWN", "ticket": None, "response": None, "error": error}
            retcode = getattr(response, "retcode", None)
            if retcode != invalid_fill:
                break

    if retcode in done_codes:
        ticket = getattr(response, "order", None) or getattr(response, "deal", None)
        _mutation_ledger_update(store, key, "DONE", ticket=ticket, attempts=attempts)
        return {
            "status": "DONE",
            "ticket": ticket,
            "response": response,
        }

    try:
        state = reconcile()
    except Exception:
        state = None
    if state is not None:
        _mutation_ledger_update(store, key, "EXISTING", ticket=state, attempts=attempts)
        return {"status": "EXISTING", "ticket": state, "response": response}
    status = "REJECTED" if response is not None else "UNKNOWN"
    error = getattr(response, "comment", "order rejected") if response is not None else "order_send returned no result"
    _mutation_ledger_update(store, key, status, error=error, attempts=attempts)
    return {
        "status": status,
        "ticket": None,
        "response": response,
        "error": error,
    }


def send_order_idempotent(request, idempotency_key, *, mt5_module=None):
    """Send one entry with deterministic reconciliation and no blind unknown-result retry."""
    module = mt5_module or mt5
    key = str(idempotency_key or "").strip()
    if not key:
        raise ValueError("idempotency_key is required")
    comment = "OAK-ID-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
    request = dict(request)
    request["comment"] = comment
    symbol = request.get("symbol")

    existing = _existing_order_by_comment(module, symbol, comment)
    if existing is not None:
        return {"status": "EXISTING", "ticket": existing, "response": None}

    try:
        response = module.order_send(request)
    except Exception as exc:
        existing = _existing_order_by_comment(module, symbol, comment)
        if existing is not None:
            return {"status": "EXISTING", "ticket": existing, "response": None}
        return {"status": "UNKNOWN", "ticket": None, "response": None, "error": str(exc)}

    retcode = getattr(response, "retcode", None)
    done_codes = {
        getattr(module, "TRADE_RETCODE_DONE", 10009),
        getattr(module, "TRADE_RETCODE_DONE_PARTIAL", 10010),
    }
    invalid_fill = getattr(module, "TRADE_RETCODE_INVALID_FILL", 10030)
    if retcode in done_codes:
        return {"status": "DONE", "ticket": getattr(response, "order", None) or getattr(response, "deal", None), "response": response}

    if retcode == invalid_fill:
        modes = [
            getattr(module, "ORDER_FILLING_IOC", None),
            getattr(module, "ORDER_FILLING_FOK", None),
            getattr(module, "ORDER_FILLING_RETURN", None),
        ]
        current = request.get("type_filling")
        for mode in dict.fromkeys(m for m in modes if m is not None and m != current):
            request["type_filling"] = mode
            try:
                response = module.order_send(request)
            except Exception as exc:
                existing = _existing_order_by_comment(module, symbol, comment)
                if existing is not None:
                    return {"status": "EXISTING", "ticket": existing, "response": None}
                return {"status": "UNKNOWN", "ticket": None, "response": None, "error": str(exc)}
            retcode = getattr(response, "retcode", None)
            if retcode != invalid_fill:
                break
        if retcode in done_codes:
            return {"status": "DONE", "ticket": getattr(response, "order", None) or getattr(response, "deal", None), "response": response}

    existing = _existing_order_by_comment(module, symbol, comment)
    if existing is not None:
        return {"status": "EXISTING", "ticket": existing, "response": response}
    return {
        "status": "REJECTED" if response is not None else "UNKNOWN",
        "ticket": None,
        "response": response,
        "error": getattr(response, "comment", "order rejected") if response is not None else "order_send returned no result",
    }
