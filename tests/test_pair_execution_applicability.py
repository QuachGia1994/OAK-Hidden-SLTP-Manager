"""v88 execution gateway schedules only the slot's applicable pairs."""
import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace

from domain.mt5_execution import (
    MT5ExecutionGateway,
    SIGNAL_LOGIC_VERSION,
    applicable_pairs_for,
)


class IntentStore:
    def __init__(self):
        self.rows = {}

    def upsert_signal_execution_intent(self, intent):
        self.rows.setdefault(intent["idempotency_key"], dict(intent))


class FakeMT5:
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_RETURN = 2
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_INVALID_FILL = 10030

    def account_info(self):
        return SimpleNamespace(balance=5000.0, equity=5000.0)

    def symbol_select(self, symbol, selected):
        return True

    def symbol_info(self, symbol):
        return SimpleNamespace(volume_min=0.01, volume_max=5.0, volume_step=0.01, filling_mode=1)

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(ask=1.2, bid=1.1)

    def positions_get(self, symbol=None):
        return []

    def orders_get(self, symbol=None):
        return []

    def order_send(self, request):
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, order=1, deal=1)


def _h7_ready():
    return {
        "logic_version": SIGNAL_LOGIC_VERSION,
        "signal": "BUY",
        "hour": 7,
        "signal_state": "READY",
        "entry_state": "READY",
        "entry_time": "07:49",
        "applicable_pairs": ["XAUUSD", "GBPUSD", "GBPJPY"],
        "pair_dirs": {"XAUUSD": "BUY", "GBPUSD": "BUY", "GBPAUD": None, "GBPJPY": "BUY", "GBPCAD": None},
        "pair_signal_states": {
            "XAUUSD": "READY", "GBPUSD": "READY", "GBPAUD": "NOT_APPLICABLE",
            "GBPJPY": "READY", "GBPCAD": "NOT_APPLICABLE",
        },
        "pair_entry_times": {"XAUUSD": "07:49", "GBPUSD": "07:49", "GBPAUD": None, "GBPJPY": "07:49", "GBPCAD": None},
        "pair_entry_at_utc": {
            "XAUUSD": "2026-08-03T04:49:00Z", "GBPUSD": "2026-08-03T04:49:00Z",
            "GBPAUD": None, "GBPJPY": "2026-08-03T04:49:00Z", "GBPCAD": None,
        },
    }


class TestPairExecutionApplicability(unittest.TestCase):

    def test_applicable_pairs_reader_uses_declared_slot(self):
        result = _h7_ready()
        self.assertEqual(applicable_pairs_for(result), ("XAUUSD", "GBPUSD", "GBPJPY"))

    def test_applicable_pairs_fallback_from_signal_states(self):
        result = dict(_h7_ready())
        del result["applicable_pairs"]
        self.assertEqual(
            applicable_pairs_for(result),
            ("XAUUSD", "GBPUSD", "GBPJPY"),
        )

    def test_schedule_only_applicable_pairs(self):
        store = IntentStore()
        gateway = MT5ExecutionGateway(FakeMT5(), store, enabled=False)
        keys = gateway.schedule_signal(_h7_ready(), date(2026, 8, 3), 7)
        self.assertEqual(len(keys), 3)
        self.assertEqual(len(store.rows), 3)
        symbols = {row["symbol"] for row in store.rows.values()}
        self.assertEqual(symbols, {"XAUUSD", "GBPUSD", "GBPJPY"})

    def test_inactive_pairs_never_create_intents(self):
        store = IntentStore()
        gateway = MT5ExecutionGateway(FakeMT5(), store, enabled=False)
        gateway.schedule_signal(_h7_ready(), date(2026, 8, 3), 7)
        self.assertTrue(all(row["symbol"] != "GBPAUD" for row in store.rows.values()))
        self.assertTrue(all(row["symbol"] != "GBPCAD" for row in store.rows.values()))

    def test_is_actionable_requires_only_applicable_pairs(self):
        gateway = MT5ExecutionGateway(FakeMT5(), IntentStore(), enabled=False)
        self.assertTrue(gateway._is_actionable(_h7_ready(), 7))

    def test_is_actionable_false_when_an_applicable_pair_waits(self):
        result = _h7_ready()
        result["pair_dirs"]["GBPJPY"] = "WAIT"
        result["pair_signal_states"]["GBPJPY"] = "WAIT"
        gateway = MT5ExecutionGateway(FakeMT5(), IntentStore(), enabled=False)
        self.assertFalse(gateway._is_actionable(result, 7))

    def test_is_actionable_false_for_wrong_logic_version(self):
        result = _h7_ready()
        result["logic_version"] = 87
        gateway = MT5ExecutionGateway(FakeMT5(), IntentStore(), enabled=False)
        self.assertFalse(gateway._is_actionable(result, 7))


if __name__ == "__main__":
    unittest.main()
