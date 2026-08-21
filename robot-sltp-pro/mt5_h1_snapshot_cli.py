from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parent
for path in (ROOT, APP):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import MetaTrader5 as mt5

from domain.xau_h1_pattern_scanner import resolve_symbol_variant
from h1_market_data import build_h1_snapshot_payload
from market_data_provider import Candle
from services.mt5_service import MT5Service


DEFAULT_SYMBOLS = ("GBPUSD", "AUDUSD", "EURUSD", "USDCAD", "USDJPY")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export attach-only MT5 H1 snapshot for scanner parity")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--broker-date", default="", help="Optional broker date YYYY-MM-DD; default latest closed H1 date")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--bars", type=int, default=72, help="Closed H1 bars to request per symbol")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def load_profiles() -> dict[str, object]:
    return json.loads((ROOT / "profiles.json").read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    if args.bars < 24 or args.bars > 336:
        raise RuntimeError("--bars must be between 24 and 336")
    profiles = load_profiles()
    cfg = profiles.get(args.profile)
    if not isinstance(cfg, dict):
        raise RuntimeError(f"Unknown profile: {args.profile}")

    service = MT5Service(path=str(cfg.get("path") or "") or None, profile_config=cfg)
    if not service.connect(allow_process_start=False):
        raise RuntimeError(f"MT5 profile is not already running/attachable: {args.profile}")
    try:
        symbols = tuple(item.strip().upper() for item in args.symbols.split(",") if item.strip())
        available = tuple(mt5.symbols_get() or ())
        candles_by_symbol: dict[str, tuple[Candle, ...]] = {}
        resolved: dict[str, str] = {}
        for base in symbols:
            broker_symbol = resolve_symbol_variant(base, available)
            if not broker_symbol:
                raise RuntimeError(f"MT5 symbol not found for {base}")
            if mt5.symbol_select(broker_symbol, True) is False:
                raise RuntimeError(f"MT5 symbol_select failed for {broker_symbol}")
            rows = mt5.copy_rates_from_pos(broker_symbol, mt5.TIMEFRAME_H1, 1, args.bars)
            if rows is None or len(rows) == 0:
                raise RuntimeError(f"MT5 closed H1 history unavailable for {broker_symbol}")
            candles_by_symbol[base] = tuple(Candle(
                time=int(row["time"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
            ) for row in rows)
            resolved[base] = broker_symbol

        payload = build_h1_snapshot_payload(
            provider=f"mt5-h1:{args.profile}",
            candles_by_symbol=candles_by_symbol,
            broker_date=args.broker_date.strip() or None,
            metadata={
                "profile": args.profile,
                "resolvedSymbols": resolved,
                "source": "mt5",
                "attachOnly": True,
                "scope": "H1 scanner parity",
            },
        )
        output = Path(args.output).resolve()
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({
            "ok": True,
            "output": str(output),
            "provider": payload["provider"],
            "timeframe": "H1",
            "brokerDate": payload["brokerDate"],
        }, ensure_ascii=False))
        return 0
    finally:
        service.disconnect()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
