"""NativeQt integration for the local EOD D1 stock advisor."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from pathlib import Path
import sqlite3
from typing import Mapping


class StockAdvisorDesktopErrorCode(str, Enum):
    INVALID_SETTINGS = "invalid_settings"
    INVALID_DATA_SOURCE = "invalid_data_source"


class StockAdvisorDesktopError(ValueError):
    def __init__(self, code: StockAdvisorDesktopErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class StockAdvisorDesktopSettings:
    client_id: str = "oak-stock-scanner"
    capital: float = 90_000_000
    history_window: int = 20

    def __post_init__(self) -> None:
        if not self.client_id.strip():
            object.__setattr__(self, "client_id", "oak-stock-scanner")
        if not isfinite(self.capital) or self.capital < 0:
            raise StockAdvisorDesktopError(StockAdvisorDesktopErrorCode.INVALID_SETTINGS, "Capital is invalid")
        if self.history_window < 2:
            raise StockAdvisorDesktopError(StockAdvisorDesktopErrorCode.INVALID_SETTINGS, "D1 history window is too short")


@dataclass(frozen=True, slots=True)
class StockAdvisorLaunchPlan:
    program: str
    arguments: tuple[str, ...]
    output_path: Path
    requires_signal_pause: bool = False


def requires_d1_backfill_file(path: Path, current_date) -> bool:
    """Return whether the local EOD DB is missing usable records.

    The argument is intentionally a database path, never ``signals_log.json``.
    """
    try:
        with sqlite3.connect(path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM eod_prices WHERE date <= ?", (current_date.isoformat(),)).fetchone()
        return not row or int(row[0]) == 0
    except (OSError, sqlite3.Error):
        return True


def build_stock_advisor_launch_plan(
    root: Path,
    executable: str,
    frozen: bool,
    settings: StockAdvisorDesktopSettings,
    requires_backfill: bool = False,
) -> StockAdvisorLaunchPlan:
    output_path = root / "stock_recommendation.json"
    prefix = ["--stock-advisor"] if frozen else [str(root / "vn_stock_advisor.py")]
    arguments = prefix + [
        "--db-path", str(root / "data" / "market.db"),
        "--capital", format(settings.capital, ".12g"),
        "--history-window", str(settings.history_window),
        "--output", str(output_path),
    ]
    return StockAdvisorLaunchPlan(executable, tuple(arguments), output_path, False)


def render_stock_advisory(payload: Mapping[str, object], locale: str = "EN") -> str:
    """Render deterministic D1 results with explicit advisory-only wording."""
    lines = [
        f"D1 LOCAL EOD · {payload.get('as_of_date', '—')} · {payload.get('status', '—')}",
        "ADVISORY ONLY · NO ORDER SUBMITTED",
        "",
        "RANK  SYMBOL   DIRECTION  SCORE  QUALITY",
    ]
    results = payload.get("recommendations")
    if not isinstance(results, list):
        results = payload.get("results") if isinstance(payload.get("results"), list) else []
    for item in results:
        if not isinstance(item, Mapping):
            continue
        lines.append(
            f"{item.get('rank', '—'):>4}  {str(item.get('symbol', '—')):<7} "
            f"{str(item.get('direction', 'WAIT')):<9} {float(item.get('score', 0.0)):>5.2f}  {item.get('data_quality', '—')}"
        )
    if len(lines) == 4:
        lines.append("—     NO ELIGIBLE SYMBOL")
    return "\n".join(lines)


__all__ = [
    "StockAdvisorDesktopError",
    "StockAdvisorDesktopErrorCode",
    "StockAdvisorDesktopSettings",
    "StockAdvisorLaunchPlan",
    "build_stock_advisor_launch_plan",
    "requires_d1_backfill_file",
    "render_stock_advisory",
]
