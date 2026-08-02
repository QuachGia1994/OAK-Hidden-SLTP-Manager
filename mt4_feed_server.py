"""Local MT4 raw-feed collector for v87.

This process owns only ingestion and diagnostics.  It never calculates a
signal, compares MT4/MT5 output, or calls the Signal Engine.
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from repositories.mt4_feed_store import MT4FeedStore
from oak_logger import setup_logger

app = Flask(__name__)
feed_store = MT4FeedStore()
feed_store_lock = threading.RLock()
feed_error_lock = threading.Lock()
last_feed_error = None
log = setup_logger("mt4_feed_server")
SUPPORTED_TIMEFRAMES = {"M30", "H1", "H4"}
SCHEMA_VERSION = 2
MAX_SYMBOL_LENGTH = 128
MAX_BARS_PER_BATCH = 6000
# MT4's WebRequest allow-list is most reliable on the default HTTP port.  The
# EA therefore publishes on :80.  Keep :5001 as a separate local-only health
# and management listener so existing desktop/Bot consumers do not break.
EA_PUBLISH_PORT = 80
MANAGEMENT_PORT = 5001
EA_PUBLISH_BASE_URL = "http://127.0.0.1/mt4-feed"
MANAGEMENT_HEALTH_URL = "http://127.0.0.1:5001/mt4-feed/health"
LOCAL_HEALTH_PATH = "/mt4-feed/health"
LOOPBACK_ADDRESSES = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}


def _ea_publish_port() -> int:
    """Keep MT4 publishing on default HTTP port; reject stale custom overrides."""
    configured = os.environ.get("MT4_FEED_PORT", "").strip()
    if configured and configured != str(EA_PUBLISH_PORT):
        raise ValueError(
            "MT4_FEED_PORT must be unset or 80: MT4 EA publishing requires "
            "default HTTP port 80; :5001 is fixed for local health/management."
        )
    return EA_PUBLISH_PORT


def _authorized() -> bool:
    expected = os.environ.get("MT4_FEED_TOKEN", "").strip()
    return not expected or request.headers.get("X-MT4-FEED-TOKEN", "") == expected


def _is_loopback_health_request() -> bool:
    """Allow only the redacted loopback health route to bypass an optional token."""
    return request.path == LOCAL_HEALTH_PATH and request.remote_addr in LOOPBACK_ADDRESSES


def _public_heartbeat(heartbeat):
    """Return diagnostic clock metadata without account or broker-server identifiers."""
    if not heartbeat:
        return None
    fields = (
        "source_id", "broker_time", "broker_time_utc", "broker_utc_offset",
        "observed_at_utc", "last_sequence", "schema_version",
    )
    return {field: heartbeat[field] for field in fields if field in heartbeat}


def _record_feed_error(endpoint: str, error: Exception) -> None:
    """Keep one local diagnostic without changing the fail-closed data state."""
    global last_feed_error
    with feed_error_lock:
        last_feed_error = {
            "endpoint": endpoint,
            "message": str(error),
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        }


def _clear_feed_error(endpoint: str) -> None:
    """Remove a recovered endpoint error while preserving another endpoint's error."""
    global last_feed_error
    with feed_error_lock:
        if last_feed_error and last_feed_error.get("endpoint") == endpoint:
            last_feed_error = None


def _latest_feed_error():
    with feed_error_lock:
        return dict(last_feed_error) if last_feed_error else None


def _json_object():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    return payload


def _normalize_symbol(value, field_name: str) -> str:
    """Return a safe, stable feed key without restricting future instruments."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    symbol = value.strip().upper()
    if not symbol:
        raise ValueError(f"{field_name} is required")
    if len(symbol) > MAX_SYMBOL_LENGTH:
        raise ValueError(f"{field_name} exceeds {MAX_SYMBOL_LENGTH} characters")
    if any(ord(character) < 32 for character in symbol):
        raise ValueError(f"{field_name} contains control characters")
    return symbol


@app.before_request
def authenticate_feed():
    if _is_loopback_health_request():
        return None
    if request.path.startswith("/mt4-feed/") and not _authorized():
        return jsonify({"ok": False, "error": "unauthorized feed"}), 401
    return None


@app.post("/mt4-feed/heartbeat")
def post_heartbeat():
    try:
        payload = _json_object()
        if int(payload.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ValueError("schema_version must be 2")
        with feed_store_lock:
            feed_store.save_heartbeat(payload)
        _clear_feed_error("heartbeat")
        return jsonify({"ok": True, "source_id": payload.get("source_id", "")})
    except (TypeError, ValueError) as exc:
        _record_feed_error("heartbeat", exc)
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        _record_feed_error("heartbeat", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/mt4-feed/bars")
def post_bars():
    try:
        payload = _json_object()
        if int(payload.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ValueError("schema_version must be 2")
        symbol = _normalize_symbol(payload.get("symbol"), "symbol")
        timeframe = str(payload.get("timeframe", "")).upper()
        bars = payload.get("bars")
        if timeframe not in SUPPORTED_TIMEFRAMES or not isinstance(bars, list):
            raise ValueError("unsupported timeframe or bars is not a list")
        if len(bars) > MAX_BARS_PER_BATCH:
            raise ValueError(f"bars exceeds {MAX_BARS_PER_BATCH} items")
        if any(not isinstance(bar, dict) for bar in bars):
            raise ValueError("bars must contain JSON objects")
        if any(not bool(bar.get("is_complete", False)) for bar in bars):
            raise ValueError("only completed candles may be published")
        resolved_raw = payload.get("resolved_symbol")
        resolved_symbol = (
            symbol if resolved_raw is None
            else _normalize_symbol(resolved_raw, "resolved_symbol")
        )
        with feed_store_lock:
            count = feed_store.save_bars(
                str(payload.get("source_id", "mt4_ea")), symbol,
                resolved_symbol, timeframe, bars,
            )
        _clear_feed_error("bars")
        log.info("bars received symbol=%s timeframe=%s count=%d source_id=%s", symbol, timeframe, count, payload.get("source_id", "mt4_ea"))
        return jsonify({"ok": True, "inserted": count})
    except (TypeError, ValueError) as exc:
        _record_feed_error("bars", exc)
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        _record_feed_error("bars", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


def _bar_availability_payload():
    """Return persisted-bar diagnostics independent of heartbeat freshness."""
    with feed_store_lock:
        availability = feed_store.get_bar_availability()
    return {
        "bars_available": availability.get("bars_available", False),
        "latest_bar_by_symbol_timeframe": availability.get("latest_bar_by_symbol_timeframe", {}),
    }


def _heartbeat_state(data_state: str) -> str:
    """Map the health data_state onto the three-state heartbeat contract."""
    return "connected" if data_state == "connected" else "stale" if data_state in ("degraded", "stale") else "disconnected"


@app.get("/mt4-feed/health")
def get_health():
    with feed_store_lock:
        heartbeat = feed_store.get_latest_heartbeat()
    base = {
        "ok": True,
        "data_provider": "MT4",
        "data_state": "disconnected",
        "heartbeat_state": "disconnected",
        **_bar_availability_payload(),
    }
    if not heartbeat:
        if error := _latest_feed_error():
            base["last_feed_error"] = error
        return jsonify(base)
    try:
        if int(heartbeat.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ValueError("unsupported heartbeat schema")
        with feed_store_lock:
            feed_store.get_broker_utc_offset()
    except (TypeError, ValueError):
        response = {
            **base,
            "data_state": "degraded",
            "heartbeat_state": _heartbeat_state("degraded"),
            "clock_verified": False,
            "heartbeat": _public_heartbeat(heartbeat),
        }
        if error := _latest_feed_error():
            response["last_feed_error"] = error
        return jsonify(response)
    try:
        observed = datetime.fromisoformat(str(heartbeat["observed_at_utc"]).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        age = max(0.0, (datetime.now(timezone.utc) - observed).total_seconds())
    except (TypeError, ValueError):
        age = float("inf")
    state = "connected" if age <= 15 else "degraded" if age <= 60 else "stale"
    response = {
        **base,
        "data_state": state,
        "heartbeat_state": _heartbeat_state(state),
        "clock_verified": state in ("connected", "degraded"),
        "age_seconds": age,
        "heartbeat": _public_heartbeat(heartbeat),
    }
    if error := _latest_feed_error():
        response["last_feed_error"] = error
    return jsonify(response)


@app.get("/mt4-feed/bars")
def get_bars():
    try:
        symbol = _normalize_symbol(request.args.get("symbol"), "symbol")
        timeframe = request.args.get("timeframe", "").upper()
        start = request.args.get("start", "1970-01-01 00:00:00")
        end = request.args.get("end", "2099-12-31 23:59:59")
        if timeframe not in SUPPORTED_TIMEFRAMES:
            return jsonify({"ok": False, "error": "unsupported timeframe"}), 400
        with feed_store_lock:
            bars = feed_store.get_bars(symbol, timeframe, start, end)
        return jsonify({"ok": True, "symbol": symbol, "timeframe": timeframe, "count": len(bars), "bars": bars})
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


def _build_local_servers():
    """Build the EA and management listeners over the same Flask app/store."""
    ea_server = make_server("127.0.0.1", _ea_publish_port(), app, threaded=True)
    management_server = make_server(
        "127.0.0.1", MANAGEMENT_PORT, app, threaded=True,
    )
    return ea_server, management_server


def main() -> int:
    """Run the local-only MT4 collector on both required local HTTP ports."""
    try:
        ea_server, management_server = _build_local_servers()
    except (OSError, ValueError) as exc:
        print(
            "[MT4 FEED] Cannot bind required local ports :80 (EA publish) and "
            f":5001 (management): {exc}",
            flush=True,
        )
        return 2

    management_thread = threading.Thread(
        target=management_server.serve_forever,
        name="mt4-feed-management",
        daemon=True,
    )
    management_thread.start()
    print(
        "[MT4 FEED] EA publish: http://127.0.0.1/mt4-feed | "
        "management health: http://127.0.0.1:5001/mt4-feed/health",
        flush=True,
    )
    try:
        ea_server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        management_server.shutdown()
        management_thread.join(timeout=2.0)
        ea_server.server_close()
        management_server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
