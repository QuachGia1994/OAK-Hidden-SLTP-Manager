# -*- coding: utf-8 -*-
"""MT5 order send helpers."""
from __future__ import annotations

import hashlib

import MetaTrader5 as mt5


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
