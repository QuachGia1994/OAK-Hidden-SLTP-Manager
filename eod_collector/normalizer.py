"""Normalizer module for EOD market data."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from eod_collector.models import EODRecord


COLUMN_MAPPINGS = {
    "ticker": "symbol",
    "ma_cp": "symbol",
    "symbol": "symbol",
    "date": "date",
    "trading_date": "date",
    "ngay": "date",
    "open": "open",
    "price_open": "open",
    "giamua": "open",
    "high": "high",
    "price_high": "high",
    "giacao": "high",
    "low": "low",
    "price_low": "low",
    "giathap": "low",
    "close": "close",
    "price_close": "close",
    "giadongcua": "close",
    "ref": "reference_price",
    "reference_price": "reference_price",
    "giathamchieu": "reference_price",
    "ceil": "ceiling_price",
    "ceiling_price": "ceiling_price",
    "giatran": "ceiling_price",
    "floor": "floor_price",
    "floor_price": "floor_price",
    "giasan": "floor_price",
    "vol": "volume",
    "volume": "volume",
    "klgd": "volume",
    "val": "value",
    "value": "value",
    "gtgd": "value",
}


class EODNormalizer:
    """Normalize raw dictionaries into valid EODRecord models."""

    def __init__(self, default_exchange: str = "HOSE", default_source: str = "collector") -> None:
        self.default_exchange = default_exchange.upper()
        self.default_source = default_source

    def normalize(self, raw_row: dict[str, Any], trading_date_override: str | None = None) -> EODRecord:
        normalized_dict: dict[str, Any] = {}
        for key, val in raw_row.items():
            clean_key = str(key).strip().lower()
            target_key = COLUMN_MAPPINGS.get(clean_key, clean_key)
            normalized_dict[target_key] = val

        symbol = str(normalized_dict.get("symbol", "")).strip().upper()
        exchange = str(normalized_dict.get("exchange", self.default_exchange)).strip().upper()
        
        raw_date = str(normalized_dict.get("date", trading_date_override or "")).strip()
        date_str = self._normalize_date(raw_date, trading_date_override)

        open_p = self._parse_number(normalized_dict.get("open", 0.0))
        high_p = self._parse_number(normalized_dict.get("high", 0.0))
        low_p = self._parse_number(normalized_dict.get("low", 0.0))
        close_p = self._parse_number(normalized_dict.get("close", 0.0))
        
        ref_p = self._parse_optional_number(normalized_dict.get("reference_price"))
        ceil_p = self._parse_optional_number(normalized_dict.get("ceiling_price"))
        floor_p = self._parse_optional_number(normalized_dict.get("floor_price"))

        volume = self._parse_number(normalized_dict.get("volume", 0.0))
        value = self._parse_number(normalized_dict.get("value", 0.0))
        source = str(normalized_dict.get("source", self.default_source))

        # Price scale normalization (Ensure thousands VND consistency: e.g. 125.0 for FPT)
        open_p, high_p, low_p, close_p, ref_p, ceil_p, floor_p = self._normalize_price_units(
            open_p, high_p, low_p, close_p, ref_p, ceil_p, floor_p
        )

        return EODRecord(
            date=date_str,
            symbol=symbol,
            exchange=exchange,
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            reference_price=ref_p,
            ceiling_price=ceil_p,
            floor_price=floor_p,
            volume=volume,
            value=value,
            source=source,
            foreign_buy_volume=self._parse_optional_number(normalized_dict.get("foreign_buy_volume")),
            foreign_sell_volume=self._parse_optional_number(normalized_dict.get("foreign_sell_volume")),
            foreign_buy_value=self._parse_optional_number(normalized_dict.get("foreign_buy_value")),
            foreign_sell_value=self._parse_optional_number(normalized_dict.get("foreign_sell_value")),
            adjusted_close=self._parse_optional_number(normalized_dict.get("adjusted_close")),
        )

    def _normalize_date(self, raw_date: str, fallback: str | None) -> str:
        if not raw_date and fallback:
            return fallback
        raw_date = raw_date.strip()
        patterns = ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"]
        for fmt in patterns:
            try:
                dt = datetime.strptime(raw_date, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        if fallback:
            return fallback
        return raw_date

    def _parse_number(self, val: Any) -> float:
        if val is None or val == "":
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        text = str(val).strip()
        text = re.sub(r"[^\d.,\-]", "", text)
        if not text:
            return 0.0

        # Handle thousand separators vs decimal point
        if "," in text and "." in text:
            if text.rfind(".") > text.rfind(","):
                # Standard format: 125,000.50 -> 125000.50
                text = text.replace(",", "")
            else:
                # European/Vietnamese format: 125.000,50 -> 125000.50
                text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            # Check if comma is thousand separator (e.g. 125,000 or 1,500,000)
            parts = text.split(",")
            if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
                text = "".join(parts)
            else:
                text = text.replace(",", ".")
        elif "." in text:
            # Check if dot is thousand separator (e.g. 125.000 or 1.500.000)
            parts = text.split(".")
            if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
                text = "".join(parts)

        try:
            return float(text)
        except ValueError:
            return 0.0

    def _parse_optional_number(self, val: Any) -> float | None:
        if val is None or val == "":
            return None
        res = self._parse_number(val)
        return res if res != 0.0 else None

    def _normalize_price_units(
        self,
        o: float, h: float, l: float, c: float,
        ref: float | None, ceil: float | None, flr: float | None
    ) -> tuple[float, float, float, float, float | None, float | None, float | None]:
        """Convert prices in full Dong (e.g. 125000) to standard Thousands VND (e.g. 125.0)."""
        scale = 1.0
        if max(o, h, l, c) > 10_000.0:
            scale = 0.001

        o = round(o * scale, 2)
        h = round(h * scale, 2)
        l = round(l * scale, 2)
        c = round(c * scale, 2)
        ref = round(ref * scale, 2) if ref is not None else None
        ceil = round(ceil * scale, 2) if ceil is not None else None
        flr = round(flr * scale, 2) if flr is not None else None
        return o, h, l, c, ref, ceil, flr
