# -*- coding: utf-8 -*-
"""MT5 connection and trading operations service."""
import MetaTrader5 as mt5
from oak_logger import setup_logger
from services.mt5_terminal_service import ensure_mt5_profile_connected
from domain.mt5_orders import send_mutation_idempotent

log = setup_logger("mt5_service")


class MT5Service:
    """Wraps MT5 operations for connection, positions, and orders."""

    def __init__(self, path=None, profile_config=None):
        self._path = path
        self._profile_config = dict(profile_config or {})
        if self._path and not self._profile_config.get("path"):
            self._profile_config["path"] = self._path
        self._connected = False

    def connect(self):
        """Initialize MT5 connection."""
        profile = dict(self._profile_config)
        profile.setdefault("path", self._path or "")
        result = ensure_mt5_profile_connected(profile, mt5_module=mt5)
        ok = result.ok
        if ok:
            self._connected = True
            info = mt5.account_info()
            if info:
                log.info("MT5 connected: %s | %s", info.server, info.login)
        else:
            log.error("MT5 init failed [%s]: %s", result.failure_code, result.message)
        return ok

    def disconnect(self):
        """Shutdown MT5 connection."""
        if self._connected:
            mt5.shutdown()
            self._connected = False
            log.info("MT5 disconnected")

    @property
    def is_connected(self):
        return self._connected and mt5.terminal_info() is not None

    def account_info(self):
        """Get account info dict."""
        info = mt5.account_info()
        if info:
            return {
                "balance": info.balance,
                "equity": info.equity,
                "margin": info.margin,
                "margin_free": info.margin_free,
                "server": info.server,
                "login": info.login,
                "profit": info.profit,
            }
        return None

    def positions_get(self, symbol=None):
        """Get open positions, optionally filtered by symbol."""
        return mt5.positions_get(symbol=symbol)

    def symbol_info_tick(self, symbol):
        """Get latest tick for a symbol."""
        return mt5.symbol_info_tick(symbol)

    def symbol_info(self, symbol):
        """Get symbol info."""
        return mt5.symbol_info(symbol)

    def close_position(self, pos, volume=None):
        """Close a position by ticket."""
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            log.warning("No tick for %s, cannot close", pos.symbol)
            return None

        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.ask if close_type == mt5.ORDER_TYPE_BUY else tick.bid

        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": volume or pos.volume,
            "type": close_type,
            "position": pos.ticket,
            "price": price,
            "deviation": 20,
            "magic": pos.magic,
            "comment": "OAK Close",
        }
        account = mt5.account_info()
        account_key = getattr(account, "login", None) or self._path or "unknown"
        result = send_mutation_idempotent(
            req,
            f"service-close:{account_key}:{pos.ticket}:{volume or pos.volume}",
            mt5_module=mt5,
            reconcile=lambda: pos.ticket if not (mt5.positions_get(ticket=pos.ticket) or []) else None,
            profile_config=self._profile_config,
        )
        if result["status"] in ("DONE", "EXISTING"):
            log.info("Closed %s %s volume=%.2f", pos.symbol, "BUY" if pos.type == 0 else "SELL", volume or pos.volume)
        else:
            log.error("Close failed for %s: %s", pos.symbol, result.get("error", result["status"]))
        return result
