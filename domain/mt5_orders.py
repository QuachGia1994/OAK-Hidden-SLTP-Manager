# -*- coding: utf-8 -*-
"""MT5 order send helpers."""
from __future__ import annotations

import MetaTrader5 as mt5

def get_filling_type(symbol):
    """
    Dynamically select filling mode based on symbol properties.
    Priority: IOC > FOK > RETURN.
    """
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
    """Send order, retry with alternate filling modes on error 10030."""
    res = mt5.order_send(request)
    if res.retcode != 10030:
        return res
    modes = [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN]
    current_mode = request["type_filling"]
    if current_mode in modes:
        modes.remove(current_mode)
    for mode in modes:
        request["type_filling"] = mode
        res = mt5.order_send(request)
        if res.retcode == mt5.TRADE_RETCODE_DONE or res.retcode != 10030:
            break
    return res

