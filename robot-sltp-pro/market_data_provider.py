from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class Candle:
    """Canonical closed/open market candle used by Engine5 providers."""

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


class MarketDataProvider(Protocol):
    """Minimal broker-data contract required by Pattern5.

    Providers must preserve the broker candle boundary. Engine5 deliberately
    does not infer/rebucket H4 candles from arbitrary UTC bars.
    """

    provider_id: str

    def symbols(self) -> Sequence[str]: ...

    def broker_day_offset(self, symbol: str) -> int: ...

    def h4_range(self, symbol: str, start_epoch: int, end_epoch: int) -> Sequence[Candle]: ...

    def warm_h4(self, symbol: str) -> None: ...


class MT5MarketDataProvider:
    """Compatibility adapter around the MetaTrader5 Python module."""

    provider_id = "mt5"

    def __init__(self, mt5_module: Any):
        self._mt5 = mt5_module

    def symbols(self) -> Sequence[str]:
        return [str(item.name) for item in (self._mt5.symbols_get() or [])]

    def broker_day_offset(self, symbol: str) -> int:
        rates = self._mt5.copy_rates_from_pos(symbol, self._mt5.TIMEFRAME_D1, 0, 2)
        if rates is None or len(rates) < 1:
            raise RuntimeError(f"Khong lay duoc D1 cua {symbol}")
        return int(rates[0]["time"]) % 86400

    def h4_range(self, symbol: str, start_epoch: int, end_epoch: int) -> Sequence[Candle]:
        rates = self._mt5.copy_rates_range(
            symbol,
            self._mt5.TIMEFRAME_H4,
            start_epoch,
            end_epoch,
        )
        if rates is None:
            return []
        return [
            Candle(
                time=int(rate["time"]),
                open=float(rate["open"]),
                high=float(rate["high"]),
                low=float(rate["low"]),
                close=float(rate["close"]),
            )
            for rate in rates
        ]

    def warm_h4(self, symbol: str) -> None:
        self._mt5.symbol_select(symbol, True)
        self._mt5.copy_rates_from_pos(symbol, self._mt5.TIMEFRAME_H4, 0, 64)


class SnapshotMarketDataProvider:
    """Deterministic provider for cloud snapshots, replay and parity tests."""

    def __init__(
        self,
        provider_id: str,
        candles_by_symbol: dict[str, Sequence[Candle]],
        day_offsets: dict[str, int],
    ):
        self.provider_id = provider_id
        self._candles = {
            symbol: tuple(sorted(candles, key=lambda candle: candle.time))
            for symbol, candles in candles_by_symbol.items()
        }
        self._offsets = dict(day_offsets)

    def symbols(self) -> Sequence[str]:
        return tuple(self._candles)

    def broker_day_offset(self, symbol: str) -> int:
        if symbol not in self._offsets:
            raise RuntimeError(f"Missing broker day offset for {symbol}")
        return int(self._offsets[symbol])

    def h4_range(self, symbol: str, start_epoch: int, end_epoch: int) -> Sequence[Candle]:
        return tuple(
            candle
            for candle in self._candles.get(symbol, ())
            if start_epoch <= candle.time <= end_epoch
        )

    def warm_h4(self, symbol: str) -> None:
        return None

    def as_payload(self) -> dict[str, object]:
        return {
            "provider": self.provider_id,
            "dayOffsets": dict(self._offsets),
            "candles": {
                symbol: [candle.as_dict() for candle in candles]
                for symbol, candles in self._candles.items()
            },
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "SnapshotMarketDataProvider":
        provider_id = str(payload.get("provider") or "snapshot")
        raw_offsets = payload.get("dayOffsets")
        raw_candles = payload.get("candles")
        if not isinstance(raw_offsets, dict) or not isinstance(raw_candles, dict):
            raise ValueError("Invalid market-data snapshot payload")
        day_offsets = {str(key): int(value) for key, value in raw_offsets.items()}
        candles_by_symbol: dict[str, list[Candle]] = {}
        for symbol, rows in raw_candles.items():
            if not isinstance(rows, list):
                raise ValueError(f"Invalid candle list for {symbol}")
            parsed: list[Candle] = []
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError(f"Invalid candle row for {symbol}")
                parsed.append(
                    Candle(
                        time=int(row["time"]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                    )
                )
            candles_by_symbol[str(symbol)] = parsed
        return cls(provider_id, candles_by_symbol, day_offsets)
