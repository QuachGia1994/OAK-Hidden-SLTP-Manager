from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from ctrader_cloud_config import CTraderCloudConfig
from ctrader_h1_market_data import H1_PARITY_SYMBOLS, collect_h1_snapshot_deferred


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch one IC Markets cTrader H1 scanner-parity snapshot")
    parser.add_argument("--days", type=int, default=2, help="H1 fetch window in days")
    parser.add_argument("--broker-date", default="", help="Optional broker date YYYY-MM-DD; default latest closed H1 date")
    parser.add_argument("--symbols", default=",".join(H1_PARITY_SYMBOLS), help="Comma-separated H1 symbols")
    parser.add_argument("--output", default="", help="Optional output JSON path")
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    symbols = tuple(item.strip().upper() for item in args.symbols.split(",") if item.strip())
    if not symbols:
        raise RuntimeError("At least one symbol is required")
    if args.days < 1 or args.days > 14:
        raise RuntimeError("--days must be between 1 and 14")

    session_url = (os.environ.get("OAK_CTRADER_SESSION_URL") or "").strip()
    dashboard_key = (os.environ.get("DASHBOARD_API_KEY") or "").strip()
    config = (
        CTraderCloudConfig.from_control_plane(session_url, dashboard_key)
        if session_url
        else CTraderCloudConfig.from_env()
    )
    current_hour = int(time.time()) // 3600 * 3600
    end_epoch = current_hour - 1  # fully closed H1 only
    start_epoch = end_epoch - args.days * 86400

    from twisted.internet import task

    def runner(reactor):
        deferred = collect_h1_snapshot_deferred(
            reactor,
            config,
            symbols=symbols,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
        )

        def emit(result):
            payload = result.as_payload(broker_date=args.broker_date.strip() or None)
            rendered = json.dumps(payload, ensure_ascii=False, indent=2)
            if args.output:
                path = Path(args.output).resolve()
                path.write_text(rendered + "\n", encoding="utf-8")
                print(json.dumps({
                    "ok": True,
                    "output": str(path),
                    "provider": payload.get("provider"),
                    "timeframe": "H1",
                    "brokerDate": payload.get("brokerDate"),
                }, ensure_ascii=False))
            else:
                print(rendered)
            return None

        def emit_error(failure):
            message = failure.getErrorMessage() if hasattr(failure, "getErrorMessage") else str(failure)
            print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
            return failure

        deferred.addCallbacks(emit, emit_error)
        return deferred

    task.react(runner)


if __name__ == "__main__":
    run()
