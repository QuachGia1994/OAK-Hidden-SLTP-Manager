"""Framework-independent orchestration helpers for the desktop VN30 advisor."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
import json
from math import isfinite
from pathlib import Path
from typing import Mapping, Sequence

from domain.stock_scanner import extract_h4_signals


MINIMUM_H4_SIGNALS = 27
STOCK_SECRET_PROFILE = "__vn30_advisor__"


class StockAdvisorDesktopErrorCode(str, Enum):
    """Stable desktop advisor configuration failures."""

    INVALID_SETTINGS = "invalid_settings"


class StockAdvisorDesktopError(ValueError):
    """Desktop advisor error with a stable machine-readable code."""

    def __init__(self, code: StockAdvisorDesktopErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class StockAdvisorDesktopSettings:
    """Non-secret settings controlled by the NativeQt advisor tab."""

    client_id: str = "oak-stock-scanner"
    capital: float = 90_000_000
    hurdle_bps: float = 0.0
    backfill_sessions: int = 260

    def __post_init__(self) -> None:
        if not self.client_id.strip():
            object.__setattr__(self, "client_id", "oak-stock-scanner")
        if not isfinite(self.capital) or self.capital < 0:
            raise StockAdvisorDesktopError(StockAdvisorDesktopErrorCode.INVALID_SETTINGS, "Capital is invalid")
        if not isfinite(self.hurdle_bps) or self.hurdle_bps < 0:
            raise StockAdvisorDesktopError(StockAdvisorDesktopErrorCode.INVALID_SETTINGS, "Hurdle is invalid")
        if self.backfill_sessions < MINIMUM_H4_SIGNALS:
            raise StockAdvisorDesktopError(StockAdvisorDesktopErrorCode.INVALID_SETTINGS, "Backfill is too short")


@dataclass(frozen=True, slots=True)
class StockAdvisorLaunchPlan:
    """Safe subprocess plan that contains no secret values."""

    program: str
    arguments: tuple[str, ...]
    output_path: Path
    requires_signal_pause: bool


def requires_h4_backfill(
    records: Sequence[Mapping[str, object]],
    current_date: date,
    minimum_signals: int = MINIMUM_H4_SIGNALS,
) -> bool:
    """Return whether history is short or lacks today's H=4 signal."""
    signals = extract_h4_signals(records)
    if len(signals) < minimum_signals:
        return True
    return signals[-1].trading_date != current_date


def requires_h4_backfill_file(path: Path, current_date: date) -> bool:
    """Read the signal log and conservatively request backfill on failure."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return True
    records = payload if isinstance(payload, list) else []
    return requires_h4_backfill([item for item in records if isinstance(item, Mapping)], current_date)


def build_stock_advisor_launch_plan(
    root: Path,
    executable: str,
    frozen: bool,
    settings: StockAdvisorDesktopSettings,
    requires_backfill: bool,
) -> StockAdvisorLaunchPlan:
    """Build a source or frozen advisor command without embedding secrets."""
    output_path = root / "stock_recommendation.json"
    prefix = ["--stock-advisor"] if frozen else [str(root / "vn_stock_advisor.py")]
    arguments = prefix + _advisor_arguments(root, output_path, settings)
    if requires_backfill:
        arguments.extend(["--backfill-h4", str(settings.backfill_sessions)])
    return StockAdvisorLaunchPlan(executable, tuple(arguments), output_path, requires_backfill)


def load_ssi_desktop_credentials() -> tuple[str, str]:
    """Load credentials or default to Local EOD mode."""
    try:
        from secret_store import get_secret
        api_key = get_secret(STOCK_SECRET_PROFILE, "ssi_api_key") or "local-eod-key"
        api_secret = get_secret(STOCK_SECRET_PROFILE, "ssi_api_secret") or "local-eod-secret"
        return api_key, api_secret
    except Exception:
        return "local-eod-key", "local-eod-secret"


def save_ssi_desktop_credentials(api_key: str, api_secret: str) -> None:
    """Store secrets outside JSON settings files if provided."""
    if not api_key.strip() and not api_secret.strip():
        return
    try:
        from secret_store import store_secret
        store_secret(STOCK_SECRET_PROFILE, "ssi_api_key", api_key.strip())
        store_secret(STOCK_SECRET_PROFILE, "ssi_api_secret", api_secret.strip())
    except Exception:
        pass


def render_stock_advisory(payload: Mapping[str, object]) -> str:
    """Render a compact trading-terminal summary for the desktop tab."""
    signal = payload.get("signal") if isinstance(payload.get("signal"), Mapping) else {}
    action = "BUY / HOLD" if payload.get("action") == "BUY_OR_HOLD" else "SELL / AVOID"
    lines = [
        f"{signal.get('date', '—')}  |  H4 {signal.get('direction', '—')}  |  {payload.get('status', '—')}",
        f"ACTION: {action}",
        "",
    ]
    candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
    lines.extend(_candidate_lines(candidates))
    lines.extend(["", "USER CONFIRMATION REQUIRED", "NO ORDER SUBMITTED"])
    return "\n".join(lines)


def _advisor_arguments(root: Path, output: Path, settings: StockAdvisorDesktopSettings) -> list[str]:
    return [
        "--signals-log", str(root / "signals_log.json"),
        "--capital", format(settings.capital, ".12g"),
        "--hurdle-bps", format(settings.hurdle_bps, ".12g"),
        "--output", str(output),
    ]


def _candidate_lines(candidates: Sequence[object]) -> list[str]:
    lines = ["RANK  SYMBOL   WEIGHT   CONDITIONAL HIT"]
    for item in candidates:
        if not isinstance(item, Mapping):
            continue
        weight = float(item.get("weight", 0)) * 100
        hit_rate = float(item.get("conditional_hit_rate", 0)) * 100
        lines.append(f"{item.get('rank', '—'):>4}  {item.get('symbol', '—'):<7}  {weight:>5.1f}%   {hit_rate:>6.1f}%")
    if len(lines) == 1:
        lines.append("—     NO ELIGIBLE SYMBOL")
    return lines
