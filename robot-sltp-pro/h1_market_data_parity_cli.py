from __future__ import annotations

import argparse
import json
from pathlib import Path

from h1_market_data import compare_h1_candles, parse_h1_snapshot, scanner_relevant_h1


def load_payload(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Snapshot must be a JSON object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare current-day H1 scanner semantics between MT5 and cTrader")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--symbol", action="append", dest="symbols")
    parser.add_argument("--tolerance", type=float, default=1e-5, help="OHLC diagnostic tolerance; not part of pass/fail")
    args = parser.parse_args()

    baseline_payload = load_payload(args.baseline)
    candidate_payload = load_payload(args.candidate)
    if baseline_payload.get("brokerDate") != candidate_payload.get("brokerDate"):
        raise RuntimeError(
            f"Broker-date mismatch: {baseline_payload.get('brokerDate')} vs {candidate_payload.get('brokerDate')}"
        )
    baseline = parse_h1_snapshot(baseline_payload)
    candidate = parse_h1_snapshot(candidate_payload)
    symbols = args.symbols or sorted(set(baseline) & set(candidate))
    if not symbols:
        raise RuntimeError("No common H1 symbols to compare")

    reports = {}
    ok = True
    for symbol in symbols:
        report = compare_h1_candles(
            scanner_relevant_h1(baseline.get(symbol, ())),
            scanner_relevant_h1(candidate.get(symbol, ())),
            symbol,
            price_tolerance=args.tolerance,
        )
        reports[symbol] = report.as_dict()
        ok = ok and report.ok

    print(json.dumps({
        "ok": ok,
        "timeframe": "H1",
        "brokerDate": baseline_payload.get("brokerDate"),
        "baseline": baseline_payload.get("provider"),
        "candidate": candidate_payload.get("provider"),
        "parityRule": "broker-day H01..H16 timestamp + T/G direction; OHLC is diagnostic only",
        "symbols": reports,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
