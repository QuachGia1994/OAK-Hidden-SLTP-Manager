"""v88 regression: H7 2026-07-31 must branch H_49 / entry 07:49 Broker.

The reversed signal is read from the fixture H1 candle 06:00 -> 07:00 Broker
(GIAM -> BUY); it is never hard-coded.  Final Reverse must NOT run at H7.
"""
import contextlib
import io
import unittest
from datetime import datetime, timedelta

from domain.signal_v87 import evaluate_slot
from test_signal_v87_core import FixtureProvider, add_m30_layer


def _build_h7_provider(h1_open="100", h1_close="99"):
    provider = FixtureProvider()
    slot_dt = datetime(2026, 7, 31, 7)
    # Layer 2 SW then Layer 3 SW -> H:49 branch.
    add_m30_layer(provider, slot_dt, ("TANG", "TANG", "TANG"))
    provider.add("XAUUSD", "M30", slot_dt, 1, 2)
    provider.add("XAUUSD", "M30", slot_dt - timedelta(minutes=30), 1, 2)
    provider.add("XAUUSD", "M30", slot_dt - timedelta(minutes=60), 1, 2)
    provider.add("XAUUSD", "H1", slot_dt - timedelta(hours=1), h1_open, h1_close)
    return provider, slot_dt


class TestH7_2026_07_31Regression(unittest.TestCase):

    def _evaluate(self, h1_open="100", h1_close="99"):
        provider, slot_dt = _build_h7_provider(h1_open, h1_close)
        snapshot = {
            "XAUUSD": {"d_direction": "SELL"},
            "GBPUSD": {"d_direction": "SELL"},
            "GBPJPY": {"d_direction": "SELL"},
        }
        return evaluate_slot(slot_dt, 7, provider, snapshot, as_of=slot_dt + timedelta(minutes=30))

    def test_h7_2026_07_31_giam_reverses_to_buy(self):
        result = self._evaluate()
        self.assertEqual(result["logic_version"], 88)
        self.assertEqual(result["entry_branch"], "H_49")
        self.assertEqual(result["entry_time"], "07:49")
        self.assertEqual(result["signal"], "BUY")
        self.assertEqual(result["pair_dirs"]["XAUUSD"], "BUY")
        self.assertEqual(result["pair_dirs"]["GBPUSD"], "BUY")
        self.assertFalse(result["final_reverse_applied"])
        self.assertIsNone(result["final_reverse_reason"])
        self.assertEqual(result["pair_evidence"]["XAUUSD"]["base_signal_source"], "PREVIOUS_XAU_H1_REVERSED")
        h49 = result["pair_evidence"]["XAUUSD"]["h49_h1_evidence"]
        self.assertEqual(h49["source_symbol"], "XAUUSD")
        self.assertEqual(h49["candle_direction"], "GIAM")
        self.assertEqual(h49["reversed_signal"], "BUY")

    def test_h49_h1_log_line_mentions_real_candle(self):
        provider, slot_dt = _build_h7_provider(h1_open="100", h1_close="99")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self._evaluate()
        log = buffer.getvalue()
        self.assertIn("[H49-H1]", log)
        self.assertIn("date=2026-07-31", log)
        self.assertIn("slot=H7", log)
        self.assertIn("source=XAUUSD H1 window=06:00->07:00 Broker", log)
        self.assertIn("direction=GIAM reversed_signal=BUY", log)

    def test_h7_tang_reverses_to_sell(self):
        result = self._evaluate(h1_open="99", h1_close="100")
        self.assertEqual(result["signal"], "SELL")
        self.assertEqual(result["pair_dirs"]["XAUUSD"], "SELL")
        self.assertEqual(result["pair_dirs"]["GBPUSD"], "SELL")
        self.assertFalse(result["final_reverse_applied"])

    def test_h7_xauusd_equals_gbpusd_invariant(self):
        result = self._evaluate()
        self.assertEqual(result["pair_dirs"]["XAUUSD"], result["pair_dirs"]["GBPUSD"])
        # Invariant is enforced on the final payload.
        self.assertEqual(result["signal"], result["pair_dirs"]["GBPUSD"])


if __name__ == "__main__":
    unittest.main()
