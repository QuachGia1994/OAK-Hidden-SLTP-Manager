"""MT5 execution gateway for v88 slot-scoped common-entry signals.

The gateway persists one intent per ``logic/date/slot/symbol/entry/direction``
key before it can send an order.  This keeps restarts idempotent and leaves
pending intents retryable when MT5 is disconnected or a broker rejects a fill.

Only the slot's ``applicable_pairs`` are scheduled; inactive pairs are
NOT_APPLICABLE and never produce an intent or an order.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from domain.execution_policy import (
    ExecutionPolicyConfig,
    evaluate_execution_intent,
    evaluate_execution_policy,
)
from domain.risk_gate import RiskGateConfig, evaluate_risk_gate


SIGNAL_LOGIC_VERSION = 88
SIGNAL_PAIRS = ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value):
    if isinstance(value, datetime):
        current = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value or "")


def applicable_pairs_for(result):
    """Return the slot-scoped pairs that may be scheduled from a v88 result."""
    if not isinstance(result, dict):
        return ()
    declared = result.get("applicable_pairs")
    if isinstance(declared, (list, tuple)) and declared:
        return tuple(declared)
    states = result.get("pair_signal_states") or {}
    return tuple(symbol for symbol in SIGNAL_PAIRS if states.get(symbol) != "NOT_APPLICABLE")


class MT5ExecutionGateway:
    """Queue and, when explicitly enabled, execute the slot's applicable intents."""

    def __init__(self, mt5_module, store, *, enabled=False, volume=0.01, magic=88000,
                 symbol_resolver=None, max_drawdown_pct=6.0, max_volume=0.05,
                 allow_weekends=False):
        self.mt5 = mt5_module
        self.store = store
        self.enabled = bool(enabled)
        self.volume = float(volume)
        self.magic = int(magic)
        self.symbol_resolver = symbol_resolver or (lambda symbol: symbol)
        self.policy_config = ExecutionPolicyConfig(enabled=self.enabled, allow_weekends=allow_weekends)
        self.risk_config = RiskGateConfig(max_drawdown_pct=float(max_drawdown_pct), max_volume=float(max_volume))

    def schedule_signal(self, result, broker_date, slot_hour, now_utc=None):
        """Persist the common-entry intent for each applicable ready pair once."""
        policy = evaluate_execution_policy(
            result,
            slot_hour,
            now_utc=now_utc,
            config=ExecutionPolicyConfig(
                enabled=True,
                allow_weekends=self.policy_config.allow_weekends,
                max_entry_age_seconds=self.policy_config.max_entry_age_seconds,
            ),
        )
        if not policy.allowed:
            return []
        date_text = broker_date.isoformat() if hasattr(broker_date, "isoformat") else str(broker_date)
        entries = result.get("pair_entry_times") or {}
        entry_at = result.get("pair_entry_at_utc") or {}
        created_at = _iso(now_utc or _utc_now())
        keys = []
        for symbol in applicable_pairs_for(result):
            direction = (result.get("pair_dirs") or {}).get(symbol)
            entry_time = entries.get(symbol) or result.get("entry_time")
            entry_utc = entry_at.get(symbol) or result.get("entry_at_utc")
            if direction not in ("BUY", "SELL") or not entry_time or not entry_utc:
                continue
            key = self._key(date_text, slot_hour, symbol, entry_time, direction)
            self.store.upsert_signal_execution_intent({
                "idempotency_key": key,
                "logic_version": SIGNAL_LOGIC_VERSION,
                "broker_date": date_text,
                "slot_hour": int(slot_hour),
                "symbol": symbol,
                "common_entry_time": str(entry_time),
                "direction": direction,
                "entry_at_utc": _iso(entry_utc),
                "status": "PENDING",
                "attempts": 0,
                "next_attempt_at_utc": _iso(entry_utc),
                "order_ticket": None,
                "last_error": "",
                "created_at_utc": created_at,
                "updated_at_utc": created_at,
            })
            keys.append(key)
        return keys

    def process_due(self, now_utc=None):
        """Execute due intents; failures remain pending for a one-minute retry."""
        if not self.enabled:
            return []
        now = now_utc if isinstance(now_utc, datetime) else _utc_now()
        now_iso = _iso(now)
        executed = []
        for intent in self.store.get_due_signal_execution_intents(now_iso):
            result = self._execute_intent(intent, now_utc=now)
            if result.get("ok"):
                executed.append(intent["idempotency_key"])
        return executed

    @staticmethod
    def _is_actionable(result, slot_hour):
        if not isinstance(result, dict) or int(result.get("logic_version", -1)) != SIGNAL_LOGIC_VERSION:
            return False
        if int(result.get("hour", slot_hour)) != int(slot_hour):
            return False
        if result.get("signal_state") != "READY" or result.get("entry_state") != "READY":
            return False
        directions = result.get("pair_dirs") or {}
        states = result.get("pair_signal_states") or {}
        entries = result.get("pair_entry_times") or {}
        applicable = applicable_pairs_for(result)
        if not applicable:
            return False
        return all(directions.get(symbol) in ("BUY", "SELL") and states.get(symbol) == "READY" for symbol in applicable) and len({entries.get(symbol) for symbol in applicable}) == 1

    @staticmethod
    def _key(date_text, slot_hour, symbol, entry_time, direction):
        return f"{SIGNAL_LOGIC_VERSION}|{date_text}|{int(slot_hour)}|{symbol}|{entry_time}|{direction}"

    def _execute_intent(self, intent, now_utc=None):
        key = intent["idempotency_key"]
        now = now_utc if isinstance(now_utc, datetime) else _utc_now()
        try:
            policy = evaluate_execution_intent(
                intent,
                now_utc=now,
                config=self.policy_config,
            )
            if not policy.allowed:
                raise RuntimeError(policy.reason)
            account = self.mt5.account_info()
            account_balance = getattr(account, "balance", None) if account is not None else None
            account_equity = getattr(account, "equity", None) if account is not None else None
            risk = evaluate_risk_gate(
                balance=account_balance,
                equity=account_equity,
                volume=self.volume,
                config=self.risk_config,
            )
            if not risk.allowed:
                raise RuntimeError(risk.reason)
            symbol = self.symbol_resolver(intent["symbol"])
            if not self.mt5.symbol_select(symbol, True):
                raise RuntimeError("symbol is not available")
            comment = "OAK88-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
            existing = self._find_existing(symbol, comment)
            if existing is not None:
                self.store.update_signal_execution_intent(key, status="EXECUTED", order_ticket=int(existing), updated_at_utc=_iso(now), last_error="")
                return {"ok": True, "ticket": existing}
            tick = self.mt5.symbol_info_tick(symbol)
            info = self.mt5.symbol_info(symbol)
            if not tick or not info or self.volume <= 0:
                raise RuntimeError("MT5 symbol tick/info unavailable")
            order_type = getattr(self.mt5, "ORDER_TYPE_BUY", 0) if intent["direction"] == "BUY" else getattr(self.mt5, "ORDER_TYPE_SELL", 1)
            price = tick.ask if order_type == getattr(self.mt5, "ORDER_TYPE_BUY", 0) else tick.bid
            request = {
                "action": getattr(self.mt5, "TRADE_ACTION_DEAL", 1),
                "symbol": symbol,
                "volume": self._normalise_volume(info),
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": self.magic,
                "comment": comment,
                "type_time": getattr(self.mt5, "ORDER_TIME_GTC", 0),
                "type_filling": self._filling_mode(info),
            }
            response = self._send_with_filling_retry(request)
            done = getattr(self.mt5, "TRADE_RETCODE_DONE", 10009)
            partial = getattr(self.mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010)
            retcode = getattr(response, "retcode", None)
            if retcode not in (done, partial):
                existing = self._find_existing(symbol, comment)
                if existing is None:
                    raise RuntimeError(getattr(response, "comment", "order rejected") if response else "order_send returned no result")
            ticket = getattr(response, "order", None) or getattr(response, "deal", None)
            self.store.update_signal_execution_intent(key, status="EXECUTED", order_ticket=ticket, last_error="", updated_at_utc=_iso(now))
            return {"ok": True, "ticket": ticket}
        except Exception as error:
            attempts = int(intent.get("attempts") or 0) + 1
            retry_at = now + timedelta(minutes=1)
            self.store.update_signal_execution_intent(key, status="PENDING", attempts=attempts, next_attempt_at_utc=_iso(retry_at), last_error=str(error)[:500], updated_at_utc=_iso(now))
            return {"ok": False, "error": str(error)}

    def _find_existing(self, symbol, comment):
        for getter in (self.mt5.positions_get, self.mt5.orders_get):
            rows = getter(symbol=symbol) or []
            for row in rows:
                if getattr(row, "comment", "") == comment:
                    return getattr(row, "ticket", None) or getattr(row, "order", None)
        return None

    def _normalise_volume(self, info):
        minimum = float(getattr(info, "volume_min", self.volume))
        maximum = float(getattr(info, "volume_max", self.volume))
        step = float(getattr(info, "volume_step", 0.01) or 0.01)
        volume = min(max(self.volume, minimum), maximum)
        return round(round(volume / step) * step, 8)

    def _filling_mode(self, info):
        mode = getattr(info, "filling_mode", None)
        valid = {getattr(self.mt5, name, value) for name, value in (("ORDER_FILLING_IOC", 1), ("ORDER_FILLING_FOK", 0), ("ORDER_FILLING_RETURN", 2))}
        return mode if mode in valid else next(iter(valid))

    def _send_with_filling_retry(self, request):
        response = self.mt5.order_send(request)
        invalid = getattr(self.mt5, "TRADE_RETCODE_INVALID_FILL", 10030)
        if getattr(response, "retcode", None) != invalid:
            return response
        for mode_name in ("ORDER_FILLING_IOC", "ORDER_FILLING_FOK", "ORDER_FILLING_RETURN"):
            mode = getattr(self.mt5, mode_name, None)
            if mode is None or mode == request.get("type_filling"):
                continue
            request["type_filling"] = mode
            response = self.mt5.order_send(request)
            if getattr(response, "retcode", None) != invalid:
                break
        return response
