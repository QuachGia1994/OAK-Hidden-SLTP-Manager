"""GBP signals remain independent while their entry follows XAU timing."""

from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


def _signal_evidence(symbol, direction, group):
    state = "READY" if direction in ("BUY", "SELL") else "WAIT"
    return {
        "symbol": symbol,
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
            "GBPUSD": _signal_evidence("GBPUSD", "SELL", "SW"),
            "GBPAUD": _signal_evidence("GBPAUD", "BUY", "BT"),
            "GBPJPY": _signal_evidence("GBPJPY", "BUY", "SW"),
            "GBPCAD": _signal_evidence("GBPCAD", "SELL", "BT"),
        }
        with (
            patch.object(
                mt5_signal_bot,
                "evaluate_gbp_pair_signal_m30",
                side_effect=lambda _slot, _hour, symbol: rows[symbol],
            ),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30", return_value=_timing()),
            patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(datetime(2026, 7, 30, 7), 7)

        self.assertEqual(
            {symbol: result["pair_dirs"][symbol] for symbol in mt5_signal_bot.GBP_SIGNAL_PAIRS},
            {"GBPUSD": "SELL", "GBPAUD": "BUY", "GBPJPY": "BUY", "GBPCAD": "SELL"},
        )
        self.assertEqual(result["pair_dirs"]["XAUUSD"], "SELL")
        self.assertEqual(result["pair_entry_times"]["XAUUSD"], "07:49")
        self.assertEqual(
            {result["pair_entry_times"][symbol] for symbol in mt5_signal_bot.GBP_SIGNAL_PAIRS},
            {"08:00"},
        )

    def test_one_missing_gbp_signal_does_not_erase_other_pairs(self) -> None:
        rows = {
            "GBPUSD": _signal_evidence("GBPUSD", "SELL", "SW"),
            "GBPAUD": _signal_evidence("GBPAUD", "BUY", "BT"),
            "GBPJPY": _signal_evidence("GBPJPY", "WAIT", None),
            "GBPCAD": _signal_evidence("GBPCAD", "SELL", "BT"),
        }
        with (
            patch.object(
                mt5_signal_bot,
                "evaluate_gbp_pair_signal_m30",
                side_effect=lambda _slot, _hour, symbol: rows[symbol],
            ),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30", return_value=_timing()),
            patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(datetime(2026, 7, 30, 7), 7)

        self.assertEqual(result["pair_dirs"]["GBPJPY"], "WAIT")
        self.assertIsNone(result["pair_entry_times"]["GBPJPY"])
        self.assertEqual(result["pair_dirs"]["GBPUSD"], "SELL")
        self.assertEqual(result["pair_entry_times"]["GBPCAD"], "08:00")

    def test_missing_xau_timing_keeps_signals_but_blocks_all_entries(self) -> None:
        rows = {
            symbol: _signal_evidence(symbol, "BUY", "BT")
            for symbol in mt5_signal_bot.GBP_SIGNAL_PAIRS
        }
        with (
            patch.object(
                mt5_signal_bot,
                "evaluate_gbp_pair_signal_m30",
                side_effect=lambda _slot, _hour, symbol: rows[symbol],
            ),
            patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30", return_value=_timing(None)),
            patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
        ):
            result = mt5_signal_bot.evaluate_all_pairs_for_slot(datetime(2026, 7, 30, 7), 7)
        self.assertEqual(result["pair_dirs"]["GBPUSD"], "BUY")
        self.assertTrue(all(value is None for value in result["pair_entry_times"].values()))


if __name__ == "__main__":
    unittest.main()
