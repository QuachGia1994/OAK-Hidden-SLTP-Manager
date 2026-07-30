"""GBP native signals remain independent while their entry follows H+1:00 schedule."""

from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


def _native_evidence(symbol, direction, group):
    state = "READY" if direction in ("BUY", "SELL") else "WAIT"
    return {
        "symbol": symbol,
        "native_signal": direction,
        "direction": direction,
        "signal_state": state,
        "entry_time": None,
        "entry_state": "WAIT",
        "layer1": {"group": group},
    }


def _timing(entry="07:49"):
    return {
        "symbol": "XAUUSD",
        "entry_time": entry,
        "entry_state": "READY" if entry else "WAIT",
        "layer1": {"group": "SW"},
        "layer2": {"group": "SW"},
    }


class GbpPairIndependenceTests(unittest.TestCase):
    def test_signals_are_independent_but_gbp_entries_share_next_hour(self) -> None:
        rows = {
            "GBPUSD": _native_evidence("GBPUSD", "SELL", "SW"),
            "GBPAUD": _native_evidence("GBPAUD", "BUY", "BT"),
            "GBPJPY": _native_evidence("GBPJPY", "WAIT", None),
            "GBPCAD": _native_evidence("GBPCAD", "WAIT", None),
        }
        with (
            patch.object(
                mt5_signal_bot,
                "evaluate_gbp_native_signal_m30",
                side_effect=lambda _slot, _hour, symbol, as_of_dt=None: rows[symbol],
            ),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30", return_value=_timing()),
            patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(datetime(2026, 7, 30, 7), 7)

        # H7: XAUUSD = native GBPAUD = BUY
        # GBPAUD = native GBPUSD = SELL
        # GBPUSD = native GBPUSD = SELL (since H7 not in 12, 14, 16)
        self.assertEqual(result["pair_dirs"]["XAUUSD"], "BUY")
        self.assertEqual(result["pair_dirs"]["GBPAUD"], "SELL")
        self.assertEqual(result["pair_dirs"]["GBPUSD"], "SELL")
        self.assertEqual(result["pair_entry_times"]["XAUUSD"], "07:49")
        self.assertEqual(result["pair_entry_times"]["GBPUSD"], "08:00")
        self.assertEqual(result["pair_entry_times"]["GBPAUD"], "08:00")
        self.assertEqual(result["pair_signal_states"]["GBPJPY"], "DISABLED")
        self.assertEqual(result["pair_signal_states"]["GBPCAD"], "DISABLED")


if __name__ == "__main__":
    unittest.main()
