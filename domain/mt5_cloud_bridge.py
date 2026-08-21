# -*- coding: utf-8 -*-
"""Outbound Upstash mailbox bridge for cloud-controlled MT5 profile workers."""
from __future__ import annotations

import json
import os
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import MetaTrader5 as mt5

from domain.mt5_orders import send_mutation_idempotent, send_order_idempotent
from services.mt5_terminal_service import validate_mt5_mutation_session

ROOT = Path(__file__).resolve().parent.parent
TASK_PREFIX = "oak:mt5:bridge:task:v1:"
QUEUE_PREFIX = "oak:mt5:bridge:queue:v1:"
ARBITER_PREFIX = "oak:mt5:bridge:arbiter:v1:"
HEARTBEAT_PREFIX = "oak:mt5:bridge:heartbeat:v1:"
TASK_TTL_SECONDS = 7 * 24 * 3600
HEARTBEAT_TTL_SECONDS = 15
HEARTBEAT_INTERVAL_SECONDS = 5.0
POLL_INTERVAL_SECONDS = 1.0


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _profile_key(profile: object) -> str:
    return str(profile or "").strip().lower()


def _task_key(task_id: str) -> str:
    return f"{TASK_PREFIX}{task_id}"


def _queue_key(profile: str) -> str:
    return f"{QUEUE_PREFIX}{_profile_key(profile)}"


def _arbiter_key(task_id: str) -> str:
    return f"{ARBITER_PREFIX}{task_id}"


def _heartbeat_key(profile: str) -> str:
    return f"{HEARTBEAT_PREFIX}{_profile_key(profile)}"


class UpstashRestClient:
    def __init__(self, url: str, token: str, *, timeout: float = 3.0):
        self.url = str(url or "").rstrip("/")
        self.token = str(token or "")
        self.timeout = float(timeout)

    def command(self, *args: object) -> Any:
        payload = json.dumps(list(args), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = Request(
            self.url,
            data=payload,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
        if decoded.get("error"):
            raise RuntimeError(f"Upstash bridge command failed: {decoded['error']}")
        return decoded.get("result")


def _parse_task(raw: object) -> dict | None:
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(value, dict) or value.get("version") != 1:
            return None
        if not value.get("id") or value.get("status") not in {"pending", "running", "done", "failed", "uncertain", "cancelled"}:
            return None
        return value
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _result(action: str, ok: bool, detail: str, *, uncertain: bool = False, broker_ref: object = None, positions: list[dict] | None = None) -> dict:
    output = {"ok": bool(ok), "action": str(action), "detail": str(detail)}
    if uncertain:
        output["uncertain"] = True
    if broker_ref not in (None, ""):
        output["brokerRef"] = str(broker_ref)
    if positions is not None:
        output["positions"] = positions
    return output


def _resolve_symbol(module: Any, requested: object) -> str | None:
    symbol = str(requested or "").strip().upper()
    if not symbol:
        return None
    try:
        if module.symbol_info(symbol):
            return symbol
    except Exception:
        pass
    if "XAU" in symbol or "GOLD" in symbol:
        for candidate in ("XAUUSD", "GOLD", "XAUUSD+", "GOLD+", "XAUUSD.m", "GOLD.m", "XAUUSD.pro", "GOLD.pro"):
            try:
                if module.symbol_info(candidate):
                    return candidate
            except Exception:
                continue
    try:
        rows = module.symbols_get() or []
    except Exception:
        rows = []
    candidates = []
    for row in rows:
        name = str(getattr(row, "name", "") or "")
        upper = name.upper()
        if symbol in upper or upper in symbol:
            candidates.append(name)
    return sorted(candidates, key=lambda value: (abs(len(value) - len(symbol)), value))[0] if candidates else None


def _filling_type(module: Any, symbol: str) -> int:
    try:
        module.symbol_select(symbol, True)
        info = module.symbol_info(symbol)
    except Exception:
        info = None
    fallback = getattr(module, "ORDER_FILLING_IOC", 1)
    if info is None:
        return fallback
    mode = getattr(info, "filling_mode", fallback)
    supported = {
        getattr(module, "ORDER_FILLING_IOC", None),
        getattr(module, "ORDER_FILLING_FOK", None),
        getattr(module, "ORDER_FILLING_RETURN", None),
    }
    if mode in supported:
        return mode
    if isinstance(mode, int):
        if mode & 2:
            return getattr(module, "ORDER_FILLING_IOC", fallback)
        if mode & 1:
            return getattr(module, "ORDER_FILLING_FOK", fallback)
    return fallback


def _serialize_position(position: Any) -> dict:
    return {
        "ticket": int(getattr(position, "ticket", 0) or 0),
        "symbol": str(getattr(position, "symbol", "") or ""),
        "side": "BUY" if int(getattr(position, "type", 0) or 0) == 0 else "SELL",
        "lots": float(getattr(position, "volume", 0) or 0),
        "profit": float(getattr(position, "profit", 0) or 0),
        "openPrice": float(getattr(position, "price_open", 0) or 0),
        "currentPrice": float(getattr(position, "price_current", 0) or 0),
        "sl": float(getattr(position, "sl", 0) or 0),
        "tp": float(getattr(position, "tp", 0) or 0),
    }


def _validate_task_identity(task: dict, profile_config: dict, module: Any) -> tuple[bool, str]:
    profile_name = str(profile_config.get("profile_name") or "")
    if _profile_key(task.get("bridgeProfile")) != _profile_key(profile_name):
        return False, "BRIDGE_PROFILE_MISMATCH"
    try:
        expected_login = int(task.get("login") or 0)
        account = module.account_info()
        actual_login = int(getattr(account, "login", 0) or 0) if account is not None else 0
    except (TypeError, ValueError):
        return False, "BRIDGE_LOGIN_INVALID"
    if expected_login <= 0 or actual_login != expected_login:
        return False, f"BRIDGE_LOGIN_MISMATCH:{actual_login}:{expected_login}"
    session_ok, session_reason = validate_mt5_mutation_session(module, profile_config)
    return (True, "MUTATION_SESSION_OK") if session_ok else (False, session_reason)


def _entry_result(task: dict, profile_config: dict, module: Any) -> dict:
    payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
    protection = task.get("protection") if isinstance(task.get("protection"), dict) else {}
    symbol = _resolve_symbol(module, payload.get("symbol"))
    if not symbol:
        return _result("entry", False, "MT5 symbol could not be resolved")
    side = str(payload.get("side") or "").upper()
    if side not in {"BUY", "SELL"}:
        return _result("entry", False, "Entry side must be BUY or SELL")
    try:
        lots = float(payload.get("lot") or 0)
        sl_points = float(protection.get("slPoints") or 0)
        tp_points = float(protection.get("tpPoints") or 0)
    except (TypeError, ValueError):
        return _result("entry", False, "Entry lot/SL/TP is invalid")
    if lots <= 0 or sl_points <= 0 or tp_points <= 0:
        return _result("entry", False, "Entry lot/SL/TP must be positive")
    info = module.symbol_info(symbol)
    tick = module.symbol_info_tick(symbol)
    if info is None or tick is None:
        return _result("entry", False, "MT5 symbol/tick is unavailable")
    minimum = float(getattr(info, "volume_min", 0) or 0)
    maximum = float(getattr(info, "volume_max", 0) or 0)
    step = float(getattr(info, "volume_step", 0) or 0)
    if minimum > 0 and lots < minimum - 1e-12:
        return _result("entry", False, f"Lot {lots} is below MT5 minimum {minimum}")
    if maximum > 0 and lots > maximum + 1e-12:
        return _result("entry", False, f"Lot {lots} exceeds MT5 maximum {maximum}")
    if step > 0:
        units = lots / step
        if abs(units - round(units)) > 1e-8:
            return _result("entry", False, f"Lot {lots} does not match MT5 volume step {step}")
    buy = side == "BUY"
    order_type = module.ORDER_TYPE_BUY if buy else module.ORDER_TYPE_SELL
    price = float(getattr(tick, "ask" if buy else "bid", 0) or 0)
    point = float(getattr(info, "point", 0) or 0)
    digits = int(getattr(info, "digits", 5) or 5)
    if price <= 0 or point <= 0:
        return _result("entry", False, "MT5 price/point is unavailable")
    sl = price - sl_points * point if buy else price + sl_points * point
    tp = price + tp_points * point if buy else price - tp_points * point
    request = {
        "action": module.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lots,
        "type": order_type,
        "price": price,
        "sl": round(sl, digits),
        "tp": round(tp, digits),
        "deviation": 20,
        "magic": int(float(profile_config.get("magic", 0) or 0)),
        "type_time": module.ORDER_TIME_GTC,
        "type_filling": _filling_type(module, symbol),
    }
    outcome = send_order_idempotent(
        request,
        f"cloud-entry:{task['id']}",
        mt5_module=module,
        profile_config=profile_config,
    )
    if outcome["status"] in {"DONE", "EXISTING"}:
        return _result("entry", True, f"{side} {symbol} {lots} lot", broker_ref=outcome.get("ticket"))
    if outcome["status"] == "UNKNOWN":
        return _result("entry", False, outcome.get("error", "MT5 entry outcome unknown"), uncertain=True)
    return _result("entry", False, outcome.get("error", "MT5 entry rejected"))


def _close_result(task: dict, profile_config: dict, module: Any, mutation_store=None) -> dict:
    payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
    scope = str(payload.get("scope") or "ALL").strip().upper()
    symbol = None if scope == "ALL" else _resolve_symbol(module, scope)
    if scope != "ALL" and not symbol:
        return _result("close", False, "MT5 close symbol could not be resolved")
    try:
        positions = list(module.positions_get() or [])
    except Exception as error:
        return _result("close", False, f"MT5 positions query failed: {error}")
    if symbol:
        positions = [position for position in positions if str(getattr(position, "symbol", "")).upper() == symbol.upper()]
    if not positions:
        return _result("close", True, "No matching open position")
    failures = []
    uncertain = False
    refs = []
    closed = 0
    for position in positions:
        tick = module.symbol_info_tick(position.symbol)
        if tick is None:
            failures.append(f"#{position.ticket}: no tick")
            continue
        is_buy = int(position.type) == int(module.POSITION_TYPE_BUY)
        close_type = module.ORDER_TYPE_SELL if is_buy else module.ORDER_TYPE_BUY
        request = {
            "action": module.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": close_type,
            "position": position.ticket,
            "price": float(getattr(tick, "bid" if is_buy else "ask", 0) or 0),
            "deviation": 20,
            "magic": int(getattr(position, "magic", 0) or 0),
            "comment": "OAK Cloud Close",
            "type_time": module.ORDER_TIME_GTC,
            "type_filling": _filling_type(module, position.symbol),
        }

        def reconcile(ticket=position.ticket):
            return ticket if not (module.positions_get(ticket=ticket) or []) else None

        outcome = send_mutation_idempotent(
            request,
            f"cloud-close:{task['id']}:{position.ticket}",
            mt5_module=module,
            reconcile=reconcile,
            mutation_store=mutation_store,
            profile_config=profile_config,
        )
        if outcome["status"] in {"DONE", "EXISTING"}:
            closed += 1
            if outcome.get("ticket") is not None:
                refs.append(str(outcome["ticket"]))
        else:
            uncertain = uncertain or outcome["status"] == "UNKNOWN"
            failures.append(f"#{position.ticket}: {outcome.get('error', outcome['status'])}")
    if failures:
        detail = f"Closed {closed}/{len(positions)}; " + "; ".join(failures)
        return _result("close", False, detail, uncertain=uncertain, broker_ref=",".join(refs) if refs else None)
    return _result("close", True, f"Closed {closed} position(s)", broker_ref=",".join(refs) if refs else None)


def _modify_result(task: dict, profile_config: dict, module: Any, mutation_store=None) -> dict:
    payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
    field = str(payload.get("field") or "").upper()
    symbol = _resolve_symbol(module, payload.get("symbol"))
    try:
        value = float(payload.get("value") or 0)
    except (TypeError, ValueError):
        value = 0
    if field not in {"SL", "TP"} or value <= 0 or not symbol:
        return _result("modify", False, "MT5 modify request is invalid")
    positions = [
        position for position in (module.positions_get() or [])
        if str(getattr(position, "symbol", "")).upper() == symbol.upper()
    ]
    if not positions:
        return _result("modify", True, "No matching open position")
    failures = []
    uncertain = False
    refs = []
    updated = 0
    for position in positions:
        info = module.symbol_info(position.symbol)
        if info is None:
            failures.append(f"#{position.ticket}: no symbol info")
            continue
        digits = int(getattr(info, "digits", 5) or 5)
        point = float(getattr(info, "point", 0) or 0)
        target_sl = round(value if field == "SL" else float(getattr(position, "sl", 0) or 0), digits)
        target_tp = round(value if field == "TP" else float(getattr(position, "tp", 0) or 0), digits)
        request = {
            "action": module.TRADE_ACTION_SLTP,
            "position": position.ticket,
            "symbol": position.symbol,
            "sl": target_sl,
            "tp": target_tp,
        }

        def reconcile(ticket=position.ticket, sl=target_sl, tp=target_tp, tolerance=point):
            rows = module.positions_get(ticket=ticket) or []
            if not rows:
                return None
            current = rows[0]
            sl_ok = abs(float(getattr(current, "sl", 0) or 0) - sl) <= max(tolerance, 1e-8)
            tp_ok = abs(float(getattr(current, "tp", 0) or 0) - tp) <= max(tolerance, 1e-8)
            return ticket if sl_ok and tp_ok else None

        outcome = send_mutation_idempotent(
            request,
            f"cloud-modify:{task['id']}:{position.ticket}:{field}:{value}",
            mt5_module=module,
            reconcile=reconcile,
            mutation_store=mutation_store,
            profile_config=profile_config,
        )
        if outcome["status"] in {"DONE", "EXISTING"}:
            updated += 1
            refs.append(str(position.ticket))
        else:
            uncertain = uncertain or outcome["status"] == "UNKNOWN"
            failures.append(f"#{position.ticket}: {outcome.get('error', outcome['status'])}")
    if failures:
        return _result("modify", False, f"Updated {updated}/{len(positions)}; " + "; ".join(failures), uncertain=uncertain, broker_ref=",".join(refs) if refs else None)
    return _result("modify", True, f"Updated {field} on {updated} position(s)", broker_ref=",".join(refs) if refs else None)


def execute_mt5_bridge_task(task: dict, profile_config: dict, *, mt5_module=None, mutation_store=None) -> dict:
    """Execute one already-claimed bridge task inside the owning MT5 worker thread."""
    module = mt5_module or mt5
    action = str(task.get("action") or "")
    identity_ok, identity_reason = _validate_task_identity(task, profile_config, module)
    if not identity_ok:
        return _result(action or "unknown", False, f"MT5 bridge identity/session denied: {identity_reason}")
    if action == "positions":
        try:
            positions = [_serialize_position(position) for position in (module.positions_get() or [])]
            return _result("positions", True, f"{len(positions)} open position(s)", positions=positions)
        except Exception as error:
            return _result("positions", False, f"MT5 positions query failed: {error}")
    if action == "entry":
        return _entry_result(task, profile_config, module)
    if action == "close":
        return _close_result(task, profile_config, module, mutation_store=mutation_store)
    if action == "modify":
        return _modify_result(task, profile_config, module, mutation_store=mutation_store)
    return _result(action or "unknown", False, "Unsupported MT5 bridge action")


class MT5CloudBridge:
    """Network transport thread; MT5 calls remain on the MonitorWorker thread."""

    def __init__(self, profile_config: dict, *, login: int, server: str, log_callback=None):
        _load_dotenv()
        self.profile_config = profile_config
        self.profile = str(profile_config.get("profile_name") or "")
        self.login = int(login or 0)
        self.server = str(server or "")
        self.log = log_callback or (lambda _message: None)
        self.url = os.environ.get("UPSTASH_REDIS_REST_URL", "")
        self.token = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
        self.client = UpstashRestClient(self.url, self.token) if self.url and self.token else None
        self.incoming: queue.Queue[dict] = queue.Queue()
        self.outgoing: queue.Queue[tuple[dict, dict]] = queue.Queue()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self._pending_results: list[tuple[dict, dict]] = []

    @property
    def enabled(self) -> bool:
        return self.client is not None and bool(self.profile and self.login > 0)

    def start(self) -> bool:
        if not self.enabled:
            self.log("[MT5-BRIDGE] disabled: shared Upstash credentials/profile identity unavailable")
            return False
        self.thread = threading.Thread(target=self._run, name=f"mt5-cloud-bridge-{self.profile}", daemon=True)
        self.thread.start()
        self.log(f"[MT5-BRIDGE] outbound mailbox active for {self.profile} login={self.login}")
        return True

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)

    def next_task(self) -> dict | None:
        try:
            return self.incoming.get_nowait()
        except queue.Empty:
            return None

    def complete(self, task: dict, result: dict) -> None:
        self.outgoing.put((task, result))

    def _store_task(self, task: dict) -> None:
        self.client.command("SET", _task_key(str(task["id"])), json.dumps(task, ensure_ascii=False, separators=(",", ":")), "EX", TASK_TTL_SECONDS)

    def _flush_results(self) -> None:
        while True:
            try:
                self._pending_results.append(self.outgoing.get_nowait())
            except queue.Empty:
                break
        remaining = []
        for task, result in self._pending_results:
            try:
                final = dict(task)
                final["result"] = result
                final["status"] = "uncertain" if result.get("uncertain") else ("done" if result.get("ok") else "failed")
                final["updatedAt"] = int(time.time() * 1000)
                self._store_task(final)
            except Exception as error:
                self.log(f"[MT5-BRIDGE] result upload failed: {error}")
                remaining.append((task, result))
        self._pending_results = remaining

    def _heartbeat(self) -> None:
        heartbeat = json.dumps({
            "profile": self.profile,
            "login": self.login,
            "server": self.server,
            "runtime": "python-worker",
            "version": "1",
            "at": int(time.time() * 1000),
        }, ensure_ascii=False, separators=(",", ":"))
        self.client.command("SET", _heartbeat_key(self.profile), heartbeat, "EX", HEARTBEAT_TTL_SECONDS)

    def _claim_next(self) -> None:
        task_id = self.client.command("LINDEX", _queue_key(self.profile), 0)
        if not task_id:
            return
        task_id = str(task_id)
        claim_token = f"worker:{self.profile}:{uuid.uuid4().hex}"
        claimed = self.client.command("SET", _arbiter_key(task_id), claim_token, "NX", "EX", TASK_TTL_SECONDS)
        self.client.command("LREM", _queue_key(self.profile), 1, task_id)
        if claimed != "OK":
            return
        task = _parse_task(self.client.command("GET", _task_key(task_id)))
        if not task or task.get("status") != "pending":
            return
        if _profile_key(task.get("bridgeProfile")) != _profile_key(self.profile) or int(task.get("login") or 0) != self.login:
            task["status"] = "failed"
            task["updatedAt"] = int(time.time() * 1000)
            task["result"] = _result(str(task.get("action") or "unknown"), False, "MT5 bridge task identity does not match this local worker")
            self._store_task(task)
            return
        task["status"] = "running"
        task["updatedAt"] = int(time.time() * 1000)
        self._store_task(task)
        self.incoming.put(task)

    def _run(self) -> None:
        next_heartbeat = 0.0
        while not self.stop_event.is_set():
            try:
                self._flush_results()
                now = time.monotonic()
                if now >= next_heartbeat:
                    self._heartbeat()
                    next_heartbeat = now + HEARTBEAT_INTERVAL_SECONDS
                self._claim_next()
            except Exception as error:
                self.log(f"[MT5-BRIDGE] transport error: {error}")
            self.stop_event.wait(POLL_INTERVAL_SECONDS)
        try:
            self._flush_results()
        except Exception:
            pass


__all__ = [
    "MT5CloudBridge",
    "UpstashRestClient",
    "execute_mt5_bridge_task",
]
