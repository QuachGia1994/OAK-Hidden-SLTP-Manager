from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import MetaTrader5 as mt5

from market_data_provider import MT5MarketDataProvider, SnapshotMarketDataProvider
from pattern5_engine import WATCHLIST, resolve_symbol


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export MT5 H4 baseline snapshot for cloud parity")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--days", type=int, default=21)
    parser.add_argument("--symbols", default=",".join(WATCHLIST))
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def load_profiles() -> dict[str, object]:
    return json.loads((ROOT / "profiles.json").read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    if args.days < 3 or args.days > 90:
        raise RuntimeError("--days must be between 3 and 90")
    profiles = load_profiles()
    cfg = profiles.get(args.profile)
    if not isinstance(cfg, dict):
        raise RuntimeError(f"Unknown profile: {args.profile}")

    symbols = tuple(item.strip().upper() for item in args.symbols.split(",") if item.strip())
    initialized_here = mt5.terminal_info() is None
    if initialized_here and not mt5.initialize(
        path=str(cfg.get("path") or "") or None,
        portable=bool(cfg.get("mt5_portable", False)),
    ):
        raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")

    try:
        provider = MT5MarketDataProvider(mt5)
        broker_symbols = list(provider.symbols())
        end_epoch = int(time.time())
        start_epoch = end_epoch - args.days * 86400
        candles = {}
        offsets = {}
        resolved = {}
        for base in symbols:
            symbol = resolve_symbol(base, broker_symbols)
            if not symbol:
                raise RuntimeError(f"MT5 symbol not found for {base}")
            resolved[base] = symbol
            rows = tuple(provider.h4_range(symbol, start_epoch, end_epoch))
            if not rows:
                provider.warm_h4(symbol)
                rows = tuple(provider.h4_range(symbol, start_epoch, end_epoch))
            if not rows:
                raise RuntimeError(f"MT5 H4 history unavailable for {symbol}")
            candles[base] = rows
            offsets[base] = provider.broker_day_offset(symbol)

        snapshot = SnapshotMarketDataProvider(
            f"mt5:{args.profile}",
            candles,
            offsets,
        )
        payload = snapshot.as_payload()
        payload["metadata"] = {
            "profile": args.profile,
            "resolvedSymbols": resolved,
            "source": "mt5",
        }
        output = Path(args.output).resolve()
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "output": str(output), "provider": payload["provider"]}, ensure_ascii=False))
        return 0
    finally:
        if initialized_here:
            mt5.shutdown()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
