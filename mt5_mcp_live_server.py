# -*- coding: utf-8 -*-
"""Read-only *live* MT5 MCP server (Phase 2 prototype) — attach-only, demo-gated.

Safety model
------------
* Separate process from the Phase 1 audit server: this file owns every live
  read, the audit server keeps owning the ledger. Neither imports the other.
* The broker package is **not** imported at module import time. It is imported
  inside one guarded session, only after every gate below has passed.
* Gates, evaluated fresh on every request and all fail-closed:
    1. ``OAK_MCP_LIVE_ENABLED`` must be exactly ``"1"`` (default: refused).
    2. the profile must be listed in ``OAK_MCP_PROFILES``;
    3. the profile must exist in ``OAK_MCP_PROFILES_FILE`` with a usable
       ``terminal64.exe`` path;
    4. that exact executable must already be running (checked with ``psutil``);
    5. optional ``login_id`` / ``login`` / ``server`` hints must match the
       attached account;
    6. unless ``OAK_MCP_LIVE_REQUIRE_DEMO`` is explicitly ``"0"``, the account
       trade mode must be the broker package's demo constant.
* This server only ever attaches to a terminal that the user started; it has no
  process-spawning code path and no way to sign in to an account.
* Only three read tools are registered. There is no trading, control or
  mutation surface, not even as a stub.
* Results are rebuilt field by field: no account identity, no ticket / order /
  position id, no magic, no comment, no terminal path and no credentials ever
  leave this process. Broker error details are never forwarded either.

Transport: stdio. JSON-RPC owns stdout, so all diagnostics go to stderr.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, NamedTuple

from mcp.server.fastmcp import FastMCP

_REPO_ROOT = Path(__file__).resolve().parent

SOURCE = "mt5_live"

_PROFILES_FILE_ENV = "OAK_MCP_PROFILES_FILE"
_PROFILES_ENV = "OAK_MCP_PROFILES"
_ENABLED_ENV = "OAK_MCP_LIVE_ENABLED"
_REQUIRE_DEMO_ENV = "OAK_MCP_LIVE_REQUIRE_DEMO"

_TERMINAL_EXE = "terminal64.exe"
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9._#\-]{1,32}$")
_MAX_HISTORY_DAYS = 31
_MAX_HISTORY_ROWS = 200

_DEAL_TYPES = {0: "BUY", 1: "SELL"}
_ENTRY_TYPES = {0: "IN", 1: "OUT", 2: "INOUT", 3: "OUT_BY"}
_POSITION_TYPES = {0: "BUY", 1: "SELL"}
_REASON_CATEGORIES = {
    0: "CLIENT", 1: "MOBILE", 2: "WEB", 3: "EXPERT", 4: "SL",
    5: "TP", 6: "SO", 7: "ROLLOVER", 8: "VMARGIN", 9: "SPLIT",
}

# The broker package keeps its connection state in process-global memory, so
# one live session at a time is the only safe concurrency model.
_SESSION_LOCK = threading.Lock()

log = logging.getLogger("mt5_mcp_live")
if not log.handlers:  # stderr only — stdout belongs to the MCP transport.
    _stderr_handler = logging.StreamHandler(sys.stderr)
    _stderr_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s - %(message)s")
    )
    log.addHandler(_stderr_handler)
    log.setLevel(logging.INFO)


class LiveAccessError(RuntimeError):
    """A live read was refused. Messages stay free of paths and credentials."""


# --------------------------------------------------------------------------- #
# Gates / configuration
# --------------------------------------------------------------------------- #
def live_enabled() -> bool:
    """Live access is off unless the operator opted in with an exact ``1``."""
    return (os.environ.get(_ENABLED_ENV) or "").strip() == "1"


def demo_required() -> bool:
    """Demo-only is the default; only an explicit ``0`` relaxes it."""
    return (os.environ.get(_REQUIRE_DEMO_ENV) or "1").strip() != "0"


def allowed_profiles() -> tuple[str, ...]:
    """Allow-listed profile names, read fresh on every request."""
    raw = os.environ.get(_PROFILES_ENV) or ""
    return tuple(name.strip() for name in raw.split(",") if name.strip())


def _require_profile(profile: str) -> str:
    """Fail closed unless *profile* is explicitly allow-listed."""
    allowed = allowed_profiles()
    if not allowed:
        raise LiveAccessError(
            f"{_PROFILES_ENV} is not configured: no profile may be read live"
        )
    name = (profile or "").strip()
    if name not in allowed:
        raise LiveAccessError(f"profile is not allow-listed: {profile!r}")
    return name


def resolve_profiles_file() -> Path:
    """Profile store location from the environment only — never from a tool."""
    configured = (os.environ.get(_PROFILES_FILE_ENV) or "").strip()
    path = Path(configured) if configured else _REPO_ROOT / "profiles.json"
    path = path.expanduser().resolve()
    if not path.is_file():
        raise LiveAccessError(
            f"profile configuration is unavailable (set {_PROFILES_FILE_ENV} "
            "to an existing JSON file)"
        )
    return path


def _profile_config(name: str) -> dict[str, Any]:
    """Read only the fields a live attach needs. Nothing here is ever returned."""
    try:
        raw = json.loads(resolve_profiles_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise LiveAccessError("profile configuration could not be read") from None
    if not isinstance(raw, dict):
        raise LiveAccessError("profile configuration is malformed")
    entry = raw.get(name)
    if not isinstance(entry, dict):
        raise LiveAccessError(f"profile is not configured: {name!r}")
    return {
        "path": entry.get("path"),
        "portable": bool(entry.get("mt5_portable", False)),
        "expected_login": entry.get("login_id", entry.get("login")),
        "expected_server": entry.get("server"),
    }


def _terminal_path(raw_path: Any) -> Path:
    """Absolute, existing ``terminal64.exe`` — anything else is refused."""
    if not raw_path:
        raise LiveAccessError("profile has no terminal configured")
    try:
        candidate = Path(os.path.expandvars(os.path.expanduser(str(raw_path))))
        if not candidate.is_absolute():
            raise LiveAccessError("profile terminal path is not absolute")
        candidate = candidate.resolve(strict=False)
    except (OSError, ValueError):
        raise LiveAccessError("profile terminal path is not usable") from None
    if candidate.name.lower() != _TERMINAL_EXE:
        raise LiveAccessError("profile terminal path is not a MetaTrader terminal")
    if not candidate.is_file() or not os.access(candidate, os.R_OK):
        raise LiveAccessError("profile terminal executable is not available")
    return candidate


def _require_running_terminal(path: Path) -> int:
    """PID of the already-running terminal at *path*; refuse when absent.

    Without process inspection there is no proof that an attach would land on
    the intended terminal, so a missing ``psutil`` is a refusal, not a warning.
    """
    try:
        import psutil  # type: ignore
    except ImportError:
        raise LiveAccessError(
            "process inspection is unavailable (install psutil): live read refused"
        ) from None
    wanted = str(path).lower()
    for process in psutil.process_iter(["name", "exe"]):
        try:
            info = process.info
            if str(info.get("name") or "").lower() != _TERMINAL_EXE:
                continue
            if str(info.get("exe") or "").lower() != wanted:
                continue
            return int(process.pid)
        except (psutil.Error, OSError, ValueError):
            continue
    raise LiveAccessError(
        "the profile terminal is not running: start it yourself first "
        "(this server never starts one)"
    )


# --------------------------------------------------------------------------- #
# Session
# --------------------------------------------------------------------------- #
class _LiveSession(NamedTuple):
    profile: str
    mt5: Any
    account: Any
    account_mode: str


def _account_mode(mt5: Any, account: Any) -> str:
    """``DEMO`` / ``REAL`` / ``UNKNOWN`` — anything unclear is not demo."""
    demo_mode = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0)
    try:
        mode = int(getattr(account, "trade_mode"))
    except (AttributeError, TypeError, ValueError):
        return "UNKNOWN"
    try:
        return "DEMO" if mode == int(demo_mode) else "REAL"
    except (TypeError, ValueError):
        return "UNKNOWN"


def _require_expected_account(account: Any, config: dict[str, Any]) -> None:
    """Verify the optional profile hints without echoing them anywhere."""
    expected_login = config.get("expected_login")
    if expected_login not in (None, ""):
        try:
            if int(getattr(account, "login", 0)) != int(expected_login):
                raise LiveAccessError(
                    "the attached account does not match the requested profile"
                )
        except (TypeError, ValueError):
            raise LiveAccessError(
                "the attached account could not be matched to the requested profile"
            ) from None
    expected_server = config.get("expected_server")
    if expected_server:
        actual = str(getattr(account, "server", "") or "")
        if str(expected_server).lower() not in actual.lower():
            raise LiveAccessError(
                "the attached account does not match the requested profile"
            )


@contextmanager
def _live_session(profile: str) -> Iterator[_LiveSession]:
    """Attach read-only to an already-running profile terminal for one request."""
    if not live_enabled():
        raise LiveAccessError(
            f"live MT5 access is disabled: set {_ENABLED_ENV}=1 only after the "
            "intended terminal is running and its account is confirmed demo"
        )
    name = _require_profile(profile)
    config = _profile_config(name)
    terminal = _terminal_path(config["path"])
    _require_running_terminal(terminal)

    with _SESSION_LOCK:
        try:
            import MetaTrader5 as mt5  # type: ignore
        except ImportError:
            raise LiveAccessError(
                "the MetaTrader5 package is not installed: live read refused"
            ) from None
        try:
            attached = bool(
                mt5.initialize(path=str(terminal), portable=bool(config["portable"]))
            )
            if not attached:
                raise LiveAccessError("could not attach to the running terminal")
            if mt5.terminal_info() is None:
                raise LiveAccessError("the terminal did not report its state")
            account = mt5.account_info()
            if account is None:
                raise LiveAccessError("the terminal did not report an account")
            _require_expected_account(account, config)
            mode = _account_mode(mt5, account)
            if demo_required() and mode != "DEMO":
                raise LiveAccessError(
                    "live reads are restricted to demo accounts "
                    f"({_REQUIRE_DEMO_ENV} is on)"
                )
            yield _LiveSession(profile=name, mt5=mt5, account=account,
                               account_mode=mode)
        except LiveAccessError:
            raise
        except Exception:
            # Broker/IPC failures must not leak their raw details to a client.
            log.exception("live read failed for an allow-listed profile")
            raise LiveAccessError("the live read failed in the terminal session")
        finally:
            try:
                mt5.shutdown()
            except Exception:  # noqa: BLE001 - shutdown must never mask the result
                log.warning("terminal session did not shut down cleanly")


# --------------------------------------------------------------------------- #
# Value helpers
# --------------------------------------------------------------------------- #
def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _meta() -> dict[str, Any]:
    """Provenance for a live read: the moment this process read the terminal."""
    return {"source": SOURCE, "observed_at_utc": _now_utc_iso()}


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _epoch_utc(value: Any) -> str | None:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def _parse_utc(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _required_bound(name: str, value: Any) -> datetime:
    if value in (None, ""):
        raise ValueError(f"{name} is required (ISO-8601 UTC timestamp)")
    parsed = _parse_utc(value)
    if parsed is None:
        raise ValueError(f"{name} must be an ISO-8601 UTC timestamp")
    return parsed


def _bounded_int(name: str, value: Any, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer between {low} and {high}") from None
    if number < low or number > high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return number


def _validated_symbol(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    symbol = str(value).strip()
    if not _SYMBOL_RE.match(symbol):
        raise ValueError("symbol must be 1-32 characters of [A-Za-z0-9._#-]")
    return symbol.upper()


def _reason_category(value: Any) -> str:
    try:
        return _REASON_CATEGORIES.get(int(value), "UNKNOWN")
    except (TypeError, ValueError):
        return "UNKNOWN"


def _public_position(position: Any) -> dict[str, Any]:
    """Rebuild a position from safe fields only (no ticket / magic / comment)."""
    try:
        direction = _POSITION_TYPES.get(int(getattr(position, "type")), "UNKNOWN")
    except (AttributeError, TypeError, ValueError):
        direction = "UNKNOWN"
    return {
        "symbol": str(getattr(position, "symbol", "") or ""),
        "direction": direction,
        "volume": _number(getattr(position, "volume", None)),
        "open_price": _number(getattr(position, "price_open", None)),
        "current_price": _number(getattr(position, "price_current", None)),
        "profit": _number(getattr(position, "profit", None)),
        "sl": _number(getattr(position, "sl", None)),
        "tp": _number(getattr(position, "tp", None)),
        "open_time_utc": _epoch_utc(getattr(position, "time", None)),
    }


def _public_deal(deal: Any, deal_type: str) -> dict[str, Any]:
    """Rebuild a deal from safe fields only (no ticket / order / position id)."""
    try:
        entry_type = _ENTRY_TYPES.get(int(getattr(deal, "entry")), "UNKNOWN")
    except (AttributeError, TypeError, ValueError):
        entry_type = "UNKNOWN"
    return {
        "symbol": str(getattr(deal, "symbol", "") or ""),
        "deal_type": deal_type,
        "entry_type": entry_type,
        "reason_category": _reason_category(getattr(deal, "reason", None)),
        "volume": _number(getattr(deal, "volume", None)),
        "price": _number(getattr(deal, "price", None)),
        "profit": _number(getattr(deal, "profit", None)),
        "commission": _number(getattr(deal, "commission", None)),
        "swap": _number(getattr(deal, "swap", None)),
        "fee": _number(getattr(deal, "fee", None)),
        "deal_time_utc": _epoch_utc(getattr(deal, "time", None)),
    }


# --------------------------------------------------------------------------- #
# MCP server (three live read tools only)
# --------------------------------------------------------------------------- #
mcp = FastMCP(
    "oak-mt5-live",
    instructions=(
        "Read-only live snapshots from an already-running MetaTrader 5 "
        "terminal. Disabled by default, restricted to allow-listed profiles "
        "and (unless explicitly relaxed) to demo accounts. No trading, no "
        "control, no terminal startup and no account sign-in are available. "
        "Every result carries source='mt5_live' plus the read time."
    ),
)


@mcp.tool()
def live_account_overview(profile: str) -> dict[str, Any]:
    """Live balance / equity / margin of one allow-listed profile's terminal.

    Returns no account identity: no number, no holder name, no server, no path.
    """
    with _live_session(profile) as session:
        account = session.account
        return {
            "profile": session.profile,
            "available": True,
            "account_mode": session.account_mode,
            "currency": str(getattr(account, "currency", "") or ""),
            "balance": _number(getattr(account, "balance", None)),
            "equity": _number(getattr(account, "equity", None)),
            "margin": _number(getattr(account, "margin", None)),
            "free_margin": _number(getattr(account, "margin_free", None)),
            "margin_level": _number(getattr(account, "margin_level", None)),
            "open_profit": _number(getattr(account, "profit", None)),
            **_meta(),
        }


@mcp.tool()
def live_positions(profile: str) -> dict[str, Any]:
    """Currently open positions, reduced to market facts only.

    Each row carries symbol, direction, volume, prices, profit, SL/TP and open
    time — never a ticket, magic, comment or account identifier.
    """
    with _live_session(profile) as session:
        raw = session.mt5.positions_get()
        if raw is None:  # ``None`` is an API error; an empty result means no rows.
            raise LiveAccessError("live positions read failed")
        positions = [_public_position(item) for item in raw]
        return {
            "profile": session.profile,
            "available": True,
            "account_mode": session.account_mode,
            "count": len(positions),
            "positions": positions,
            **_meta(),
        }


@mcp.tool()
def live_trade_history(
    profile: str,
    from_utc: str,
    to_utc: str,
    limit: int = 100,
    symbol: str | None = None,
) -> dict[str, Any]:
    """BUY/SELL deals in a bounded window, newest first (max 31 days, 200 rows).

    ``from_utc`` / ``to_utc`` are required inclusive ISO-8601 bounds. Ticket,
    order, position, magic and comment fields are never returned.
    """
    start = _required_bound("from_utc", from_utc)
    end = _required_bound("to_utc", to_utc)
    if start > end:
        raise ValueError("from_utc must not be later than to_utc")
    if end - start > timedelta(days=_MAX_HISTORY_DAYS):
        raise ValueError(
            f"the requested interval must not exceed {_MAX_HISTORY_DAYS} days"
        )
    count = _bounded_int("limit", limit, 1, _MAX_HISTORY_ROWS)
    wanted_symbol = _validated_symbol(symbol)

    with _live_session(profile) as session:
        raw = session.mt5.history_deals_get(start, end, group=wanted_symbol or "*")
        if raw is None:  # ``None`` is an API error; an empty result means no rows.
            raise LiveAccessError("live history read failed")
        selected: list[tuple[float, dict[str, Any]]] = []
        for item in raw:
            try:
                deal_type = _DEAL_TYPES.get(int(getattr(item, "type")))
            except (AttributeError, TypeError, ValueError):
                continue
            if deal_type is None:  # balance / credit / correction entries
                continue
            public = _public_deal(item, deal_type)
            if wanted_symbol and public["symbol"].upper() != wanted_symbol:
                continue
            selected.append((_number(getattr(item, "time", None)) or 0.0, public))
        selected.sort(key=lambda entry: entry[0], reverse=True)
        deals = [public for _ts, public in selected[:count]]
        return {
            "profile": session.profile,
            "available": True,
            "account_mode": session.account_mode,
            "count": len(deals),
            "deals": deals,
            **_meta(),
        }


def main() -> None:
    log.info(
        "Starting live MT5 MCP server (stdio, read-only, attach-only, "
        "enabled=%s, demo_required=%s)", live_enabled(), demo_required(),
    )
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
