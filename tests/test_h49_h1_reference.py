import os
import tempfile
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from domain.signal_v87 import evaluate_h49_reference_signal, evaluate_slot

from test_signal_v87_core import FixtureProvider


def add_h49_layers(provider, slot_dt):
    """Make both M30 layers SW so the entry plan resolves to the H:49 branch."""
    for opening, direction in zip(
        (slot_dt - timedelta(minutes=30), slot_dt - timedelta(minutes=60), slot_dt - timedelta(minutes=90)),
        ("TANG", "TANG", "TANG"),
    ):
        provider.add("XAUUSD", "M30", opening, 1, 2)
    for opening, direction in zip(
        (slot_dt, slot_dt - timedelta(minutes=30), slot_dt - timedelta(minutes=60)),
        ("TANG", "TANG", "TANG"),
    ):
        provider.add("XAUUSD", "M30", opening, 1, 2)


class TestH49H1Reference(unittest.TestCase):

    def _fixture(self, h1_open="100", h1_close="99"):
        provider = FixtureProvider()
        slot_dt = datetime(2026, 7, 31, 7)
        add_h49_layers(provider, slot_dt)
        provider.add("XAUUSD", "H1", slot_dt - timedelta(hours=1), h1_open, h1_close)
        return provider, slot_dt

    def test_h49_h7_down_h1_reverses_to_buy(self):
        provider, slot_dt = self._fixture(h1_open="100", h1_close="99")
        snapshot = {symbol: {"d_direction": "SELL"} for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")}
        result = evaluate_slot(slot_dt, 7, provider, snapshot, as_of=slot_dt + timedelta(minutes=30))
        self.assertEqual(result["entry_time"], "07:49")
        self.assertEqual(result["entry_branch"], "H_49")
        self.assertEqual(result["signal"], "BUY")
        self.assertEqual(result["core_signal"], "BUY")
        self.assertEqual(result["pair_dirs"]["XAUUSD"], "BUY")
        self.assertFalse(result["final_reverse_applied"])
        self.assertIsNone(result["failure_reason"])
        self.assertEqual(result["pair_evidence"]["XAUUSD"]["base_signal_source"], "PREVIOUS_XAU_H1_REVERSED")
        self.assertEqual(result["pair_evidence"]["XAUUSD"]["final_signal"], "BUY")

    def test_h49_h7_up_h1_reverses_to_sell(self):
        provider, slot_dt = self._fixture(h1_open="99", h1_close="100")
        snapshot = {symbol: {"d_direction": "BUY"} for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")}
        result = evaluate_slot(slot_dt, 7, provider, snapshot, as_of=slot_dt + timedelta(minutes=30))
        self.assertEqual(result["entry_time"], "07:49")
        self.assertEqual(result["entry_branch"], "H_49")
        self.assertEqual(result["signal"], "SELL")
        self.assertEqual(result["pair_dirs"]["XAUUSD"], "SELL")

    def test_h49_h1_doji_returns_wait(self):
        provider, slot_dt = self._fixture(h1_open="100", h1_close="100")
        snapshot = {symbol: {"d_direction": "BUY"} for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")}
        result = evaluate_slot(slot_dt, 7, provider, snapshot, as_of=slot_dt + timedelta(minutes=30))
        self.assertEqual(result["signal"], "WAIT")
        self.assertEqual(result["failure_reason"], "H49_H1_DOJI")
        self.assertEqual(result["pair_evidence"]["XAUUSD"]["failure_reason"], "H49_H1_DOJI")

    def test_h49_h1_missing_returns_wait(self):
        provider = FixtureProvider()
        slot_dt = datetime(2026, 7, 31, 7)
        add_h49_layers(provider, slot_dt)
        snapshot = {symbol: {"d_direction": "BUY"} for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")}
        result = evaluate_slot(slot_dt, 7, provider, snapshot, as_of=slot_dt + timedelta(minutes=30))
        self.assertEqual(result["signal"], "WAIT")
        self.assertEqual(result["failure_reason"], "H49_H1_MISSING")

    def test_h49_uses_exact_previous_completed_h1(self):
        provider, slot_dt = self._fixture(h1_open="100", h1_close="99")
        # An older, opposite H1 must be ignored: only the H1 right before the
        # slot decides the reversed signal.
        provider.add("XAUUSD", "H1", slot_dt - timedelta(hours=2), "99", "100")
        h49 = evaluate_h49_reference_signal(slot_dt, provider)
        self.assertEqual(h49["broker_open_at"], (slot_dt - timedelta(hours=1)).isoformat())
        self.assertEqual(h49["broker_close_at"], slot_dt.isoformat())
        self.assertEqual(h49["candle_direction"], "GIAM")
        self.assertEqual(h49["reversed_signal"], "BUY")
        self.assertEqual(h49["open_exact"], "100")
        self.assertEqual(h49["close_exact"], "99")

    def test_h49_does_not_use_reference_d(self):
        provider, slot_dt = self._fixture(h1_open="100", h1_close="99")
        snapshot = {
            "XAUUSD": {"d_direction": "SELL"},
            "GBPUSD": {"d_direction": "SELL"},
            "GBPAUD": {"d_direction": "SELL"},
            "GBPJPY": {"d_direction": "SELL"},
            "GBPCAD": {"d_direction": "SELL"},
        }
        result = evaluate_slot(slot_dt, 7, provider, snapshot, as_of=slot_dt + timedelta(minutes=30))
        # H1 down reverses to BUY regardless of the reference D being SELL.
        self.assertEqual(result["signal"], "BUY")
        self.assertEqual(result["pair_evidence"]["XAUUSD"]["base_signal_source"], "PREVIOUS_XAU_H1_REVERSED")

    def test_h49_does_not_use_day_mode(self):
        provider, slot_dt = self._fixture(h1_open="100", h1_close="99")
        snapshot = {symbol: {"d_direction": "BUY"} for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")}
        day_mode = SimpleNamespace(source_branch="H_11")
        result = evaluate_slot(slot_dt, 7, provider, snapshot, day_mode=day_mode, as_of=slot_dt + timedelta(minutes=30))
        self.assertEqual(result["entry_branch"], "H_49")
        self.assertEqual(result["signal"], "BUY")
        self.assertEqual(result["pair_evidence"]["XAUUSD"]["base_signal_source"], "PREVIOUS_XAU_H1_REVERSED")

    def test_h49_evidence_contains_exact_h1_ohlc(self):
        provider, slot_dt = self._fixture(h1_open="100", h1_close="99")
        snapshot = {symbol: {"d_direction": "SELL"} for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")}
        result = evaluate_slot(slot_dt, 7, provider, snapshot, as_of=slot_dt + timedelta(minutes=30))
        h49 = result["pair_evidence"]["XAUUSD"]["h49_h1_evidence"]
        self.assertEqual(h49["source_symbol"], "XAUUSD")
        self.assertEqual(h49["timeframe"], "H1")
        self.assertEqual(h49["open_exact"], "100")
        self.assertEqual(h49["close_exact"], "99")
        self.assertEqual(h49["candle_direction"], "GIAM")
        self.assertEqual(h49["reversed_signal"], "BUY")
        self.assertEqual(h49["state"], "READY")
        self.assertIsNone(h49["failure_reason"])
        self.assertEqual(result["pair_evidence"]["XAUUSD"]["evidence_schema_version"], 11)


if __name__ == "__main__":
    unittest.main()
