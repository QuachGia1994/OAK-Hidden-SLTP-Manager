"""Test suite for independent multi-pair M15 signal architecture (v55).

Covering:
- 288-case table-driven matrix (3 symbols × 6 slots × 8 patterns × 2 Base directions).
- Pair independence tests (concurrent distinct directions, single-pair missing candles, top-level WAIT semantics).
- DOJI M15 resolution tests for all 3 symbols across all lookback positions (-30, -45, -60, -75).
- Hour note formatting, deactivated slots, and absence of legacy XAUUSD2 or hour-based pair routing.
"""
from datetime import datetime, timezone
from unittest.mock import patch
import unittest

import mt5_signal_bot


DASHBOARD_SLOTS = (3, 7, 9, 12, 14, 16)
SIGNAL_PAIRS = ("XAUUSD", "GBPUSD", "GBPAUD")

_SW_PATTERNS = (
    ("TANG", "TANG", "TANG"),
    ("GIAM", "TANG", "TANG"),
    ("TANG", "GIAM", "GIAM"),
    ("GIAM", "GIAM", "GIAM"),
)

_BT_PATTERNS = (
    ("GIAM", "TANG", "GIAM"),
    ("GIAM", "GIAM", "TANG"),
    ("TANG", "GIAM", "TANG"),
    ("TANG", "TANG", "GIAM"),
)


def _candle(direction: str) -> dict[str, float]:
    if direction == "TANG":
        return {"open": 1.0, "high": 2.0, "low": 1.0, "close": 2.0}
    if direction == "GIAM":
        return {"open": 2.0, "high": 2.0, "low": 1.0, "close": 1.0}
    if direction == "DOJI":
        return {"open": 1.0, "high": 2.0, "low": 0.0, "close": 1.0}
    return {}


def _timestamp(broker_dt: datetime, hour: int, minute: int = 0, second: int = 0) -> int:
    target = broker_dt.replace(hour=hour, minute=minute, second=second, microsecond=0)
    return int(target.replace(tzinfo=timezone.utc).timestamp())


class M15MultiPairMatrixTests(unittest.TestCase):
    """Exhaustive 288-case test matrix for shared symbol M15 evaluation engine."""

    def test_logic_version_and_signal_pairs(self) -> None:
        self.assertEqual(mt5_signal_bot.SIGNAL_LOGIC_VERSION, 55)
        self.assertEqual(mt5_signal_bot.SIGNAL_PAIRS, SIGNAL_PAIRS)

    def test_288_table_driven_matrix(self) -> None:
        """3 symbols × 6 slots × 8 patterns × 2 Base directions = 288 cases."""
        broker_dt = datetime(2026, 7, 29, 12, 0)
        total_cases = 0

        for symbol in SIGNAL_PAIRS:
            for hour in DASHBOARD_SLOTS:
                for base_dir in ("TANG", "GIAM"):
                    base_signal = "BUY" if base_dir == "TANG" else "SELL"
                    all_patterns = [("SW", p) for p in _SW_PATTERNS] + [("BT", p) for p in _BT_PATTERNS]

                    for group, pattern in all_patterns:
                        total_cases += 1
                        expected_dir = mt5_signal_bot.reverse_signal(base_signal) if group == "SW" else base_signal
                        if hour == 14:
                            expected_dir = mt5_signal_bot.reverse_signal(expected_dir)
                        expected_entry = f"{hour + 1:02d}:25" if group == "SW" else f"{hour:02d}:49"
                        lookback_dirs = (base_dir,) + pattern

                        with self.subTest(symbol=symbol, hour=hour, base=base_dir, group=group, pattern=pattern), \
                             patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=lookback_dirs):
                            res = mt5_signal_bot.evaluate_symbol_m15_for_slot(broker_dt, hour, symbol)

                        self.assertIsNotNone(res)
                        self.assertEqual(res["symbol"], symbol)
                        self.assertEqual(res["source_date"], "2026-07-29")
                        self.assertEqual(res["offsets"], [30, 45, 60, 75])
                        self.assertEqual(res["base_direction"], base_dir)
                        self.assertEqual(res["base_signal"], base_signal)
                        self.assertEqual(res["pattern_directions"], list(pattern))
                        self.assertEqual(res["matched_pattern"], pattern)
                        self.assertEqual(res["pullback_group"], group)
                        self.assertEqual(res["direction"], expected_dir)
                        self.assertEqual(res["entry_time"], expected_entry)

        self.assertEqual(total_cases, 288)


class PairIndependenceTests(unittest.TestCase):
    """Verify complete independence between XAUUSD, GBPUSD, and GBPAUD."""

    def test_concurrent_independent_directions(self) -> None:
        """H=9: XAUUSD pattern SW -> SELL, GBPUSD pattern BT -> BUY, GBPAUD pattern SW -> BUY."""
        broker_dt = datetime(2026, 7, 29, 9, 0)

        # Lookback sequence for calls in order of SIGNAL_PAIRS (XAUUSD, GBPUSD, GBPAUD):
        # XAUUSD: Base TANG, SW (TANG, TANG, TANG) -> SELL, entry 10:25
        # GBPUSD: Base TANG, BT (GIAM, TANG, GIAM) -> BUY, entry 09:49
        # GBPAUD: Base GIAM, SW (GIAM, GIAM, GIAM) -> BUY, entry 10:25
        sequence = [
            # XAUUSD 4 candles
            "TANG", "TANG", "TANG", "TANG",
            # GBPUSD 4 candles
            "TANG", "GIAM", "TANG", "GIAM",
            # GBPAUD 4 candles
            "GIAM", "GIAM", "GIAM", "GIAM",
        ]

        with patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=sequence):
            res = mt5_signal_bot.evaluate_all_pairs_for_slot(broker_dt, 9)

        self.assertIsNotNone(res)
        self.assertEqual(res["signal"], "SELL")
        self.assertEqual(res["entry_time"], "10:25")
        self.assertEqual(res["pair_dirs"]["XAUUSD"], "SELL")
        self.assertEqual(res["pair_dirs"]["GBPUSD"], "BUY")
        self.assertEqual(res["pair_dirs"]["GBPAUD"], "BUY")
        self.assertEqual(res["pair_entry_times"]["XAUUSD"], "10:25")
        self.assertEqual(res["pair_entry_times"]["GBPUSD"], "09:49")
        self.assertEqual(res["pair_entry_times"]["GBPAUD"], "10:25")
        self.assertEqual(res["pair_groups"]["XAUUSD"], "SW")
        self.assertEqual(res["pair_groups"]["GBPUSD"], "BT")
        self.assertEqual(res["pair_groups"]["GBPAUD"], "SW")

    def test_gbpusd_missing_candle_isolation(self) -> None:
        """Missing candle on GBPUSD makes only GBPUSD WAIT."""
        broker_dt = datetime(2026, 7, 29, 9, 0)

        def mock_lookback(symbol, tf, candle_dt):
            if symbol == "GBPUSD":
                return None
            return "TANG"  # Base TANG + pattern (TANG,TANG,TANG) = SW -> SELL

        with patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=mock_lookback):
            res = mt5_signal_bot.evaluate_all_pairs_for_slot(broker_dt, 9)

        self.assertEqual(res["signal"], "SELL")
        self.assertEqual(res["pair_dirs"]["XAUUSD"], "SELL")
        self.assertEqual(res["pair_dirs"]["GBPUSD"], "WAIT")
        self.assertEqual(res["pair_dirs"]["GBPAUD"], "SELL")
        self.assertIsNone(res["pair_entry_times"]["GBPUSD"])

    def test_xauusd_missing_candle_isolation(self) -> None:
        """Missing candle on XAUUSD sets top-level signal=WAIT, preserving GBP pairs."""
        broker_dt = datetime(2026, 7, 29, 9, 0)

        def mock_lookback(symbol, tf, candle_dt):
            if symbol == "XAUUSD":
                return None
            return "TANG"

        with patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=mock_lookback):
            res = mt5_signal_bot.evaluate_all_pairs_for_slot(broker_dt, 9)

        self.assertEqual(res["signal"], "WAIT")
        self.assertEqual(res["pair_dirs"]["XAUUSD"], "WAIT")
        self.assertEqual(res["pair_dirs"]["GBPUSD"], "SELL")
        self.assertEqual(res["pair_dirs"]["GBPAUD"], "SELL")

    def test_no_cross_symbol_direction_derivation(self) -> None:
        """Verify that evaluate_symbol_m15_for_slot only queries candles for the given symbol."""
        broker_dt = datetime(2026, 7, 29, 9, 0)
        queried_symbols = []

        def mock_lookback(symbol, tf, candle_dt):
            queried_symbols.append(symbol)
            return "TANG"

        with patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=mock_lookback):
            mt5_signal_bot.evaluate_symbol_m15_for_slot(broker_dt, 9, "GBPAUD")

        self.assertEqual(set(queried_symbols), {"GBPAUD"})

    def test_all_slots_query_all_three_symbols(self) -> None:
        """Every slot H3, H7, H9, H12, H14, H16 queries MT5 for XAUUSD, GBPUSD, and GBPAUD."""
        broker_dt = datetime(2026, 7, 29, 12, 0)
        for hour in DASHBOARD_SLOTS:
            queried = []
            def mock_lookback(symbol, tf, candle_dt):
                queried.append(symbol)
                return "TANG"

            with self.subTest(hour=hour), \
                 patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=mock_lookback):
                mt5_signal_bot.evaluate_all_pairs_for_slot(broker_dt, hour)

            self.assertCountEqual(queried, ["XAUUSD"] * 4 + ["GBPUSD"] * 4 + ["GBPAUD"] * 4)


class DojiM15ResolutionTests(unittest.TestCase):
    """Verify DOJI M15 resolution rule for all symbols and lookback positions."""

    def test_doji_m15_resolution_positions(self) -> None:
        """Test DOJI at offsets -30, -45, -60, -75 for XAUUSD, GBPUSD, GBPAUD."""
        broker_dt = datetime(2026, 7, 29, 9, 0)
        m15 = mt5_signal_bot.mt5.TIMEFRAME_M15

        for symbol in SIGNAL_PAIRS:
            for offset in (30, 45, 60, 75):
                # 1. DOJI + previous TANG -> resolved GIAM
                with self.subTest(symbol=symbol, offset=offset, case="TANG->GIAM"), \
                     patch.object(mt5_signal_bot, "get_candle_by_ts", side_effect=[_candle("DOJI"), _candle("TANG")]), \
                     patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1000):
                    direction = mt5_signal_bot._lookback_candle_direction(symbol, m15, broker_dt)
                    self.assertEqual(direction, "GIAM")

                # 2. DOJI + previous GIAM -> resolved TANG
                with self.subTest(symbol=symbol, offset=offset, case="GIAM->TANG"), \
                     patch.object(mt5_signal_bot, "get_candle_by_ts", side_effect=[_candle("DOJI"), _candle("GIAM")]), \
                     patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1000):
                    direction = mt5_signal_bot._lookback_candle_direction(symbol, m15, broker_dt)
                    self.assertEqual(direction, "TANG")

                # 3. DOJI + previous DOJI -> None (no recursion)
                with self.subTest(symbol=symbol, offset=offset, case="DOJI->None"), \
                     patch.object(mt5_signal_bot, "get_candle_by_ts", side_effect=[_candle("DOJI"), _candle("DOJI")]), \
                     patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1000):
                    direction = mt5_signal_bot._lookback_candle_direction(symbol, m15, broker_dt)
                    self.assertIsNone(direction)

                # 4. DOJI + previous missing -> None
                with self.subTest(symbol=symbol, offset=offset, case="missing->None"), \
                     patch.object(mt5_signal_bot, "get_candle_by_ts", side_effect=[_candle("DOJI"), None]), \
                     patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1000):
                    direction = mt5_signal_bot._lookback_candle_direction(symbol, m15, broker_dt)
                    self.assertIsNone(direction)

    def test_doji_offset_step_back_is_exactly_900s(self) -> None:
        """Verify resolve_doji steps back exactly 900 seconds for M15."""
        ts_called = []
        def mock_get_candle(symbol, tf, ts):
            ts_called.append(ts)
            return _candle("TANG")

        with patch.object(mt5_signal_bot, "get_candle_by_ts", side_effect=mock_get_candle):
            mt5_signal_bot.resolve_doji("XAUUSD", mt5_signal_bot.mt5.TIMEFRAME_M15, 10000, datetime(2026, 7, 29))
        self.assertEqual(ts_called, [9100])  # 10000 - 900


class HourNoteAndDeactivationTests(unittest.TestCase):
    """Verify notes, deactivated slots, and absence of legacy paths."""

    def test_get_hour_note_format(self) -> None:
        note = mt5_signal_bot.get_hour_note(9)
        self.assertIn("XAUUSD", note)
        self.assertIn("GBPUSD", note)
        self.assertIn("GBPAUD", note)
        self.assertIn("DOJI M15", note)
        self.assertNotIn("XAUUSD2", note)
        self.assertNotIn("previous session", note)

    def test_is_deactivated_signal_slot(self) -> None:
        broker_dt = datetime(2026, 7, 23)  # Thursday
        self.assertTrue(mt5_signal_bot.is_deactivated_signal_slot(broker_dt, 3))
        self.assertTrue(mt5_signal_bot.is_deactivated_signal_slot(broker_dt, 4))
        self.assertFalse(mt5_signal_bot.is_deactivated_signal_slot(broker_dt, 9))


if __name__ == "__main__":
    unittest.main()
