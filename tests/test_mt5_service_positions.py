from unittest.mock import patch

from services.mt5_service import MT5Service


def test_positions_get_all_does_not_pass_symbol_none():
    service = MT5Service()
    with patch("services.mt5_service.mt5.positions_get", return_value=("position",)) as mocked:
        assert service.positions_get() == ("position",)
    mocked.assert_called_once_with()


def test_positions_get_symbol_uses_exact_symbol_filter():
    service = MT5Service()
    with patch("services.mt5_service.mt5.positions_get", return_value=("position",)) as mocked:
        assert service.positions_get("XAUUSD+") == ("position",)
    mocked.assert_called_once_with(symbol="XAUUSD+")
