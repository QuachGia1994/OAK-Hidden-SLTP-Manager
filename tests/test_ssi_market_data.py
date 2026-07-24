"""Tests for the read-only SSI market-data adapter."""
from __future__ import annotations

from types import SimpleNamespace
from datetime import date
import os
import unittest
from unittest.mock import patch

from services.ssi_market_data import (
    SSIConfigurationError,
    SSICredentials,
    SSIMarketDataProvider,
    aggregate_afternoon_vwap,
    credentials_from_environment,
)


class SSICredentialTests(unittest.TestCase):
    def test_reads_market_data_credentials_without_an_otp(self) -> None:
        values = {
            "SSI_CLIENT_ID": "oak-stock-scanner",
            "SSI_API_KEY": "key",
            "SSI_API_SECRET": "secret",
        }
        with patch.dict(os.environ, values, clear=True):
            credentials = credentials_from_environment()

        self.assertEqual(credentials.client_id, "oak-stock-scanner")
        self.assertNotIn("secret", repr(credentials))

    def test_missing_credentials_default_to_local_eod_mode(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            credentials = credentials_from_environment()
            self.assertEqual(credentials.api_key, "local-eod-key")

    def test_secret_is_redacted_from_dataclass_repr(self) -> None:
        credentials = SSICredentials("client", "key", "top-secret")
        self.assertNotIn("top-secret", repr(credentials))


class AfternoonVwapTests(unittest.TestCase):
    def test_uses_only_1305_through_1309_and_value_weighting(self) -> None:
        candles = [
            self._candle("2026/07/01 13:04:00", 10, 100, 1_000),
            self._candle("2026/07/01 13:05:00", 10, 100, 1_000),
            self._candle("2026/07/01 13:09:00", 20, 100, 2_000),
            self._candle("2026/07/01 13:10:00", 30, 100, 3_000),
        ]

        points = aggregate_afternoon_vwap(candles)

        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].price, 15.0)
        self.assertEqual(points[0].matched_value, 3_000)

    def test_ignores_non_finite_market_values(self) -> None:
        candles = [self._candle("2026/07/01 13:05:00", float("nan"), 100, 1_000)]

        self.assertEqual(aggregate_afternoon_vwap(candles), [])

    @staticmethod
    def _candle(timestamp: str, close: float, volume: int, value: float) -> SimpleNamespace:
        return SimpleNamespace(
            trading_date=timestamp,
            close_price=close,
            volume=volume,
            value=value,
        )


class SSIProviderTests(unittest.TestCase):
    def test_provider_uses_vn30_and_five_minute_history_only(self) -> None:
        service = _FakeMarketDataService()
        credentials = SSICredentials("client", "key", "secret")
        factory = lambda _credentials, _stack: service

        with SSIMarketDataProvider(credentials, service_factory=factory) as provider:
            symbols = provider.get_vn30_symbols()
            has_session = provider.has_trading_session(date(2026, 7, 1))
            points = provider.get_afternoon_points("AAA", date(2026, 7, 1), date(2026, 7, 2))

        self.assertEqual(symbols, ["AAA", "BBB"])
        self.assertTrue(has_session)
        self.assertEqual(points[0].price, 10.0)
        self.assertEqual(service.request["from_date"], "2026/07/01")
        self.assertEqual(service.request["to_date"], "2026/07/02")


class _FakeMarketDataService:
    def __init__(self) -> None:
        self.request: dict[str, object] = {}

    def get_securities_info_by_index(self, index: str) -> list[SimpleNamespace]:
        assert index == "VN30"
        return [SimpleNamespace(symbol="BBB"), SimpleNamespace(symbol="AAA")]

    def get_index_summary(self, index: str) -> SimpleNamespace:
        assert index == "VNINDEX"
        return SimpleNamespace(trading_date="2026/07/01 11:30:00")

    def get_ohlc_5minute_historical(self, **request: object) -> list[SimpleNamespace]:
        self.request = request
        return [AfternoonVwapTests._candle("2026/07/01 13:05:00", 10, 100, 1_000)]


if __name__ == "__main__":
    unittest.main()
