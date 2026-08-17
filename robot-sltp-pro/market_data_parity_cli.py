from __future__ import annotations

import argparse
import json
from pathlib import Path

from market_data_parity import compare_provider_range
from market_data_provider import SnapshotMarketDataProvider


def load_provider(path: Path) -> SnapshotMarketDataProvider:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Snapshot must be a JSON object: {path}")
    return SnapshotMarketDataProvider.from_payload(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare broker H4 snapshots before Engine5 cloud cutover")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--symbol", action="append", dest="symbols")
    parser.add_argument("--start", type=int, required=True, help="Unix epoch seconds")
    parser.add_argument("--end", type=int, required=True, help="Unix epoch seconds")
    parser.add_argument("--tolerance", type=float, default=1e-5)
    args = parser.parse_args()

    baseline = load_provider(args.baseline)
    candidate = load_provider(args.candidate)
    symbols = args.symbols or sorted(set(baseline.symbols()) & set(candidate.symbols()))
    reports = {}
    ok = True
    for symbol in symbols:
        report = compare_provider_range(
            baseline,
            candidate,
            symbol,
            args.start,
            args.end,
            price_tolerance=args.tolerance,
        )
        reports[symbol] = report.as_dict()
        ok = ok and report.ok

    print(json.dumps({
        "ok": ok,
        "baseline": baseline.provider_id,
        "candidate": candidate.provider_id,
        "symbols": reports,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
