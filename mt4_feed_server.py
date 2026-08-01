"""Local MT4 raw-feed collector for v87.

This process owns only ingestion and diagnostics.  It never calculates a
signal, compares MT4/MT5 output, or calls the Signal Engine.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from flask import Flask, jsonify, request

from repositories.mt4_feed_store import MT4FeedStore

app = Flask(__name__)
feed_store = MT4FeedStore()
SUPPORTED_SYMBOLS = {"XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD"}
SUPPORTED_TIMEFRAMES = {"M30", "H1", "H4"}
SCHEMA_VERSION = 2


def _authorized() -> bool:
    expected = os.environ.get("MT4_FEED_TOKEN", "").strip()
    return not expected or request.headers.get("X-MT4-FEED-TOKEN", "") == expected


def _json_object():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    return payload


@app.before_request
def authenticate_feed():
    if request.path.startswith("/mt4-feed/") and not _authorized():
        return jsonify({"ok": False, "error": "unauthorized feed"}), 401
    return None


@app.post("/mt4-feed/heartbeat")
def post_heartbeat():
    try:
        payload = _json_object()
        if int(payload.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ValueError("schema_version must be 2")
        feed_store.save_heartbeat(payload)
        return jsonify({"ok": True, "source_id": payload.get("source_id", "")})
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/mt4-feed/bars")
def post_bars():
    try:
        payload = _json_object()
        if int(payload.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ValueError("schema_version must be 2")
        symbol = str(payload.get("symbol", "")).upper()
        timeframe = str(payload.get("timeframe", "")).upper()
        bars = payload.get("bars")
        if symbol not in SUPPORTED_SYMBOLS or timeframe not in SUPPORTED_TIMEFRAMES or not isinstance(bars, list):
            raise ValueError("unsupported symbol/timeframe or bars is not a list")
        if any(not isinstance(bar, dict) for bar in bars):
            raise ValueError("bars must contain JSON objects")
        if any(not bool(bar.get("is_complete", False)) for bar in bars):
            raise ValueError("only completed candles may be published")
        count = feed_store.save_bars(
            str(payload.get("source_id", "mt4_ea")), symbol,
            str(payload.get("resolved_symbol", symbol)), timeframe, bars,
        )
        return jsonify({"ok": True, "inserted": count})
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.get("/mt4-feed/health")
def get_health():
    heartbeat = feed_store.get_latest_heartbeat()
    if not heartbeat:
        return jsonify({"ok": True, "data_provider": "MT4", "data_state": "disconnected"})
    try:
        if int(heartbeat.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ValueError("unsupported heartbeat schema")
        feed_store.get_broker_utc_offset()
    except (TypeError, ValueError):
        return jsonify({
            "ok": True,
            "data_provider": "MT4",
            "data_state": "degraded",
            "clock_verified": False,
            "heartbeat": heartbeat,
        })
    try:
        observed = datetime.fromisoformat(str(heartbeat["observed_at_utc"]).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        age = max(0.0, (datetime.now(timezone.utc) - observed).total_seconds())
    except (TypeError, ValueError):
        age = float("inf")
    state = "connected" if age <= 15 else "degraded" if age <= 60 else "stale"
    return jsonify({"ok": True, "data_provider": "MT4", "data_state": state,
                    "clock_verified": state in ("connected", "degraded"),
                    "age_seconds": age, "heartbeat": heartbeat})


@app.get("/mt4-feed/bars")
def get_bars():
    try:
        symbol = request.args.get("symbol", "").upper()
        timeframe = request.args.get("timeframe", "").upper()
        start = request.args.get("start", "1970-01-01 00:00:00")
        end = request.args.get("end", "2099-12-31 23:59:59")
        if symbol not in SUPPORTED_SYMBOLS or timeframe not in SUPPORTED_TIMEFRAMES:
            return jsonify({"ok": False, "error": "unsupported symbol/timeframe"}), 400
        bars = feed_store.get_bars(symbol, timeframe, start, end)
        return jsonify({"ok": True, "symbol": symbol, "timeframe": timeframe, "count": len(bars), "bars": bars})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("MT4_FEED_PORT", "5001")), threaded=True)
