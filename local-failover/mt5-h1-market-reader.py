import json
import os
import sys
import time
from datetime import datetime, timezone

import MetaTrader5 as mt5

DEFAULT_TERMINAL = r"C:\Program Files\MetaTrader 5 IC Markets Global\terminal64.exe"
SOURCES = ("XAUUSD", "AUDUSD", "USDJPY", "GBPUSD")
DEFAULT_DAYS = 2
MAX_DAYS = 120


def broker_wall_parts(epoch_seconds: int):
    # MetaTrader5 copy_rates_from_pos exposes MT5 server-wall timestamps in the
    # epoch field. Decode the components directly; applying the cTrader UTC->
    # ICMarkets UTC+2/+3 conversion here would shift the block twice.
    value = datetime.fromtimestamp(epoch_seconds, timezone.utc)
    return value.strftime("%Y-%m-%d"), value.hour, value.minute


def resolve_symbol(base: str):
    exact = mt5.symbol_info(base)
    if exact:
        return exact.name
    candidates = mt5.symbols_get(group=f"*{base}*") or []
    upper = base.upper()
    for item in candidates:
        name = str(item.name)
        if name.upper() == upper:
            return name
    for item in candidates:
        name = str(item.name)
        if name.upper().startswith(upper) or upper in name.upper():
            return name
    return ""


def parse_days(argv):
    days = DEFAULT_DAYS
    for index, value in enumerate(argv):
        if value == "--days" and index + 1 < len(argv):
            days = int(argv[index + 1])
    if days < 1 or days > MAX_DAYS:
        raise RuntimeError(f"days must be 1..{MAX_DAYS}")
    return days


def terminal_from_args(argv):
    terminal = os.environ.get("OAK_ICMARKETS_MT5_TERMINAL", DEFAULT_TERMINAL)
    for index, value in enumerate(argv):
        if value == "--terminal" and index + 1 < len(argv) and argv[index + 1].strip():
            terminal = argv[index + 1].strip()
    return terminal


def main():
    argv = sys.argv[1:]
    terminal = terminal_from_args(argv)
    days = parse_days(argv)
    bar_count = min(12_000, days * 96 + 192)

    if not mt5.initialize(path=terminal):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        account = mt5.account_info()
        terminal_info = mt5.terminal_info()
        if not account or not terminal_info or not terminal_info.connected:
            raise RuntimeError("ICMarkets MT5 is not connected")
        server = str(account.server or "")
        if "icmarkets" not in server.lower():
            raise RuntimeError(f"wrong MT5 server: {server}")

        payload_symbols = {}
        broker_anchor = None
        for base in SOURCES:
            symbol = resolve_symbol(base)
            if not symbol:
                raise RuntimeError(f"ICMarkets symbol not found: {base}")
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError(f"cannot select ICMarkets symbol: {symbol}")
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, bar_count)
            if rates is None or len(rates) < 8:
                raise RuntimeError(f"insufficient M15 bars for {symbol}: {mt5.last_error()}")

            current = rates[-1]
            if broker_anchor is None:
                broker_anchor = int(current["time"])
            bars = []
            for row in rates[:-1]:
                epoch = int(row["time"])
                broker_date, hour, minute = broker_wall_parts(epoch)
                open_price = float(row["open"])
                close_price = float(row["close"])
                bars.append({
                    "brokerDate": broker_date,
                    "hour": hour,
                    "minute": minute,
                    "direction": "T" if close_price > open_price else "G",
                })
            payload_symbols[base] = {"displayName": symbol, "bars": bars}

        if broker_anchor is None:
            raise RuntimeError("ICMarkets broker anchor unavailable")
        broker_date, broker_hour, broker_minute = broker_wall_parts(broker_anchor)
        print(json.dumps({
            "version": 1,
            "profile": "MT5 ICMarkets Local",
            "capturedAt": int(time.time() * 1000),
            "login": int(account.login),
            "server": server,
            "terminalPath": terminal,
            "brokerDate": broker_date,
            "brokerHour": broker_hour,
            "brokerMinute": broker_minute,
            "symbols": payload_symbols,
        }, separators=(",", ":")))
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
