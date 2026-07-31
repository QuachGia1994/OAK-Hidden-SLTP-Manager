"""Regression tests for Day Mode persistence, sequential rebuild propagation, and restart recovery (v81)."""

from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot
from mt5_signal_bot import (
    DayMode,
    serialize_day_mode,
    deserialize_day_mode,
    reconstruct_current_day_mode,
    evaluate_all_pairs_for_slot,
    _build_rebuild_record,
    SIGNAL_LOGIC_VERSION,
)


def _fixture_d_dirs():
    return {
        "XAUUSD": {"d_direction": "SELL", "d_state": "READY", "symbol": "XAUUSD", "source_symbol": "GBPUSD", "timeframe": "H4", "source_open_time_broker": "20:00"},
        "GBPUSD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPUSD", "source_symbol": "GBPUSD", "timeframe": "H4", "source_open_time_broker": "20:00"},
        "GBPAUD": {"d_direction": "BUY", "d_state": "READY", "symbol": "GBPAUD", "source_symbol": "GBPAUD", "timeframe": "H4", "source_open_time_broker": "20:00"},
        "GBPJPY": {"d_direction": "WAIT", "d_state": "DOJI", "symbol": "GBPJPY", "source_symbol": "GBPJPY", "timeframe": "H4", "source_open_time_broker": "20:00"},
        "GBPCAD": {"d_direction": "SELL", "d_state": "READY", "symbol": "GBPCAD", "source_symbol": "GBPCAD", "timeframe": "H4", "source_open_time_broker": "20:00"},
    }


def _fixture_entry_timings(hour):
    # Thursday 2026-07-30 entries: H3 04:25, H7 08:25, H9 09:11, H12 12:11, H14 14:11
    timings = {
        3: "04:25",
        7: "08:25",
        9: "09:11",
        12: "12:11",
        14: "14:11",
        16: "16:11",
    }
    t = timings.get(hour, "09:11")
    return {
        "entry_time": t,
        "entry_state": "READY",
        "layer1": {"group": "BT"},
        "layer2": {"group": "BT"},
        "layer3": None,
    }


class DayModeMatrixTests(unittest.TestCase):
    def test_exact_2026_07_30_thursday_matrix(self) -> None:
        """Section 24: Validate exact matrix for Thursday 2026-07-30."""
        target_date = datetime(2026, 7, 30)
        d_dirs = _fixture_d_dirs()

        current_mode = None
        results = {}

        for h in (3, 7, 9, 12, 14):
            with (
                patch.object(mt5_signal_bot, "calculate_all_d_directions", return_value=d_dirs),
                patch.object(mt5_signal_bot, "evaluate_xau_entry_timing_m30", return_value=_fixture_entry_timings(h)),
                patch.object(mt5_signal_bot, "evaluate_symbol_entry_timing_m30", return_value=_fixture_entry_timings(h)),
                patch.object(mt5_signal_bot.BROKER_CLOCK, "utc_offset_for_date", return_value=3),
            ):
                rec, next_modes = _build_rebuild_record(
                    target_date.replace(hour=h), h, day_mode=current_mode, d_directions=d_dirs
                )
                if isinstance(next_modes, dict):
                    # Use XAUUSD mode for backward compat
                    xau_dm = next_modes.get("XAUUSD")
                    if xau_dm is not None:
                        current_mode = xau_dm
                elif next_modes is not None:
                    current_mode = next_modes
                results[h] = rec

        # Assert Day Mode source is H3 04:25 H_PLUS_1_25 for all
        for h in (3, 7, 9, 12, 14):
            rec = results[h]
            self.assertEqual(rec["day_mode"], "DAY_MODE_H_PLUS_1_25")
            self.assertEqual(rec["day_mode_source_hour"], 3)
            self.assertEqual(rec["day_mode_source_entry_time"], "04:25")
            self.assertEqual(rec["day_mode_source_branch"], "H_PLUS_1_25")

        # H3: KEEP_D then Rule A (Thu H3 D-based) INVERT
        # Primary: XAU=SELL, GBP=BUY, AUD=BUY → Invert → XAU=BUY, GBP=SELL, AUD=SELL
        self.assertEqual(results[3]["pair_dirs"]["XAUUSD"], "BUY")
        self.assertEqual(results[3]["pair_dirs"]["GBPUSD"], "SELL")
        self.assertEqual(results[3]["pair_dirs"]["GBPAUD"], "SELL")

        # H7: KEEP_D, no inversion on Thursday H7
        self.assertEqual(results[7]["pair_dirs"]["XAUUSD"], "SELL")
        self.assertEqual(results[7]["pair_dirs"]["GBPUSD"], "BUY")
        self.assertEqual(results[7]["pair_dirs"]["GBPAUD"], "BUY")

        # H9: REVERSE_D -> XAU: BUY, GBPUSD: SELL, GBPAUD: SELL
        self.assertEqual(results[9]["pair_dirs"]["XAUUSD"], "BUY")
        self.assertEqual(results[9]["pair_dirs"]["GBPUSD"], "SELL")
        self.assertEqual(results[9]["pair_dirs"]["GBPAUD"], "SELL")

        # H12: REVERSE_D -> XAU: BUY, GBPUSD: SELL, GBPAUD: SELL
        self.assertEqual(results[12]["pair_dirs"]["XAUUSD"], "BUY")
        self.assertEqual(results[12]["pair_dirs"]["GBPUSD"], "SELL")
        self.assertEqual(results[12]["pair_dirs"]["GBPAUD"], "SELL")

        # H14: REVERSE_D -> XAU: BUY, GBPUSD: SELL, GBPAUD: SELL
        self.assertEqual(results[14]["pair_dirs"]["XAUUSD"], "BUY")
        self.assertEqual(results[14]["pair_dirs"]["GBPUSD"], "SELL")
        self.assertEqual(results[14]["pair_dirs"]["GBPAUD"], "SELL")

    def test_day_mode_serialization_roundtrip(self) -> None:
        """Section 3 & 25: Test day mode serialization and deserialization."""
        dm = DayMode(mode="DAY_MODE_H_PLUS_1_25", source_hour=3, source_entry_time="04:25", source_branch="H_PLUS_1_25")
        serialized = serialize_day_mode(dm)
        self.assertEqual(serialized["day_mode"], "DAY_MODE_H_PLUS_1_25")
        self.assertEqual(serialized["day_mode_source_hour"], 3)

        reconstructed = deserialize_day_mode(serialized)
        self.assertIsNotNone(reconstructed)
        self.assertEqual(reconstructed.mode, "DAY_MODE_H_PLUS_1_25")
        self.assertEqual(reconstructed.source_hour, 3)

        # None roundtrip
        serialized_none = serialize_day_mode(None)
        self.assertIsNone(serialized_none["day_mode"])
        self.assertIsNone(deserialize_day_mode(serialized_none))

    def test_startup_restart_recovery(self) -> None:
        """Section 26: Test recovery of day mode on bot restart mid-day."""
        records = [
            {
                "date": "2026-07-30",
                "hour": 3,
                "logic_version": 81,
                "day_mode": "DAY_MODE_H_PLUS_1_25",
                "day_mode_state": "RESOLVED",
                "day_mode_source_hour": 3,
                "day_mode_source_entry_time": "04:25",
                "day_mode_source_branch": "H_PLUS_1_25",
            },
            {
                "date": "2026-07-30",
                "hour": 7,
                "logic_version": 81,
                "day_mode": "DAY_MODE_H_PLUS_1_25",
                "day_mode_state": "RESOLVED",
                "day_mode_source_hour": 3,
                "day_mode_source_entry_time": "04:25",
                "day_mode_source_branch": "H_PLUS_1_25",
            },
        ]
        recovered = reconstruct_current_day_mode(records, datetime(2026, 7, 30).date(), 81)
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.mode, "DAY_MODE_H_PLUS_1_25")
        self.assertEqual(recovered.source_hour, 3)


if __name__ == "__main__":
    unittest.main()
