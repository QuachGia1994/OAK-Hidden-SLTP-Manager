from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Candle:
    """Canonical H1 candle value used by scanner parity utilities."""

    time: int
    open: float
    high: float
    low: float
    close: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "time": self.time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
        }
