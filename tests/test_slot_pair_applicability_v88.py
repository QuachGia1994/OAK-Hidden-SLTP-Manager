"""v88 canonical slot-scoped active pair map and NOT_APPLICABLE states."""
import unittest
from datetime import datetime, timedelta

from domain.signal_v87 import (
    SLOT_ACTIVE_PAIRS,
    SignalInvariantError,
    evaluate_slot,
    get_evaluated_pairs_for_hour,
)
from test_signal_v87_core import FixtureProvider, add_m30_layer

EXPECTED = {
    3: ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY"),
    7: ("XAUUSD", "GBPUSD", "GBPJPY"),
    9: ("XAUUSD", "GBPUSD", "GBPCAD"),
    12: ("XAUUSD", "GBPUSD", "GBPAUD"),
    14: ("XAUUSD", "GBPUSD", "GBPCAD"),
    16: ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD"),
}


class TestSlotPairApplicabilityV88(unittest.TestCase):

    def test_canonical_slot_map(self):
        for hour, expected in EXPECTED.items():
            with self.subTest(hour=hour):
                self.assertEqual(get_evaluated_pairs_for_hour(hour), expected)

    def test_xauusd_and_gbpusd_are_always_applicable(self):
        for hour in (3, 7, 9, 12, 14, 16):
            self.assertIn("XAUUSD", get_evaluated_pairs_for_hour(hour))
            self.assertIn("GBPUSD", get_evaluated_pairs_for_hour(hour))

    def test_h16_evaluates_all_five(self):
        self.assertEqual(
            get_evaluated_pairs_for_hour(16),
            ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD"),
        )

    def test_unknown_hour_returns_empty(self):
        self.assertEqual(get_evaluated_pairs_for_hour(99), ())

    def test_inactive_pairs_are_not_applicable(self):
        provider = FixtureProvider()
        slot_dt = datetime(2026, 8, 3, 9)
        add_m30_layer(provider, slot_dt, ("GIAM", "TANG", "GIAM"))
        snapshot = {symbol: {"d_direction": "SELL"} for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")}
        result = evaluate_slot(slot_dt, 9, provider, snapshot)
        self.assertEqual(result["applicable_pairs"], ["XAUUSD", "GBPUSD", "GBPCAD"])
        # H9: GBPAUD and GBPJPY are NOT_APPLICABLE.
        self.assertIsNone(result["pair_dirs"]["GBPAUD"])
        self.assertIsNone(result["pair_dirs"]["GBPJPY"])
        self.assertEqual(result["pair_signal_states"]["GBPAUD"], "NOT_APPLICABLE")
        self.assertEqual(result["pair_signal_states"]["GBPJPY"], "NOT_APPLICABLE")
        self.assertEqual(result["execution_state"]["GBPAUD"], "NOT_APPLICABLE")
        self.assertEqual(result["pair_entry_states"]["GBPAUD"], "NOT_APPLICABLE")
        self.assertEqual(result["pair_d_directions"]["GBPAUD"], None)
        self.assertNotIn("GBPAUD", result["pair_evidence"])
        # Applicable pairs stay normal.
        self.assertEqual(result["pair_signal_states"]["GBPCAD"], "READY")
        self.assertEqual(result["pair_signal_states"]["GBPUSD"], "READY")

    def test_h3_scopes_out_gbpcad(self):
        provider = FixtureProvider()
        slot_dt = datetime(2026, 8, 3, 3)
        add_m30_layer(provider, slot_dt, ("GIAM", "TANG", "GIAM"))
        snapshot = {symbol: {"d_direction": "BUY"} for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")}
        result = evaluate_slot(slot_dt, 3, provider, snapshot)
        self.assertEqual(result["applicable_pairs"], ["XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY"])
        self.assertIsNone(result["pair_dirs"]["GBPCAD"])
        self.assertEqual(result["pair_signal_states"]["GBPCAD"], "NOT_APPLICABLE")


if __name__ == "__main__":
    unittest.main()
