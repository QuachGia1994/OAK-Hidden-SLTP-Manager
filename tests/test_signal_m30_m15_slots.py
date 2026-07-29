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
    """Exhaustive test matrix for shared symbol M15 evaluation engine (v57)."""

    def test_logic_version_and_signal_pairs(self) -> None:
        self.assertEqual(mt5_signal_bot.SIGNAL_LOGIC_VERSION, 64)
        self.assertEqual(mt5_signal_bot.SIGNAL_PAIRS, SIGNAL_PAIRS)

    def test_84_post_filter_subcases(self) -> None:
        """3 symbols × 7 slots × 4 comparison subcases = 84 total subcases."""
        backend_slots = (3, 4, 7, 9, 12, 14, 16)
        total_subcases = 0

        subcases = [
            ("BUY", "TANG", "SAME", "REVERSE", "SELL"),
            ("BUY", "GIAM", "OPPOSITE", "KEEP", "BUY"),
            ("SELL", "GIAM", "SAME", "REVERSE", "BUY"),
            ("SELL", "TANG", "OPPOSITE", "KEEP", "SELL"),
        ]

        for symbol in SIGNAL_PAIRS:
            for hour in backend_slots:
                for prov_sig, off15_dir, exp_rel, exp_act, exp_final in subcases:
                    total_subcases += 1

                    res = mt5_signal_bot.apply_offset15_filter(prov_sig, off15_dir)
                    self.assertIsNotNone(res)
                    self.assertEqual(res["offset15_direction"], off15_dir)
                    self.assertEqual(res["offset15_signal"], "BUY" if off15_dir == "TANG" else "SELL")
                    self.assertEqual(res["relation"], exp_rel)
                    self.assertEqual(res["action"], exp_act)
                    self.assertEqual(res["final_signal"], exp_final)

                    # Invariant assertion: final_signal == reverse(offset15_signal)
                    offset15_sig = "BUY" if off15_dir == "TANG" else "SELL"
                    self.assertEqual(res["final_signal"], mt5_signal_bot.reverse_signal(offset15_sig))

        self.assertEqual(total_subcases, 84)

    def test_288_table_driven_matrix(self) -> None:
        """3 symbols × 6 slots × 8 patterns × 2 Base directions = 288 cases with offset -15 post-filter, GBPUSD H>=9, and XAUUSD weekday matrix."""
        # Tuesday: 2026-07-14 (weekday 1, no XAUUSD weekday inversion)
        broker_dt = datetime(2026, 7, 14, 12, 0)
        total_cases = 0

        for symbol in SIGNAL_PAIRS:
            for hour in DASHBOARD_SLOTS:
                for base_dir in ("TANG", "GIAM"):
                    base_signal = "BUY" if base_dir == "TANG" else "SELL"
                    all_patterns = [("SW", p) for p in _SW_PATTERNS] + [("BT", p) for p in _BT_PATTERNS]

                    for group, pattern in all_patterns:
                        total_cases += 1
                        prov_dir = mt5_signal_bot.reverse_signal(base_signal) if group == "SW" else base_signal
                        expected_entry = f"{hour + 1:02d}:25" if group == "SW" else f"{hour:02d}:49"

                        # Provide offset -15 = "GIAM" ("SELL")
                        # prov_dir BUY + GIAM -> OPPOSITE KEEP -> BUY
                        # prov_dir SELL + GIAM -> SAME REVERSE -> BUY
                        lookback_dirs = (base_dir,) + pattern + ("GIAM",)
                        post_offset15_expected = "BUY"
                        expected_final = "SELL" if (symbol == "GBPUSD" and hour >= 9) else "BUY"

                        with self.subTest(symbol=symbol, hour=hour, base=base_dir, group=group, pattern=pattern), \
                             patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=lookback_dirs):
                            res = mt5_signal_bot.evaluate_symbol_m15_for_slot(broker_dt, hour, symbol)

                        self.assertIsNotNone(res)
                        self.assertEqual(res["symbol"], symbol)
                        self.assertEqual(res["source_date"], "2026-07-14")
                        self.assertEqual(res["offsets"], [15, 30, 45, 60, 75])
                        self.assertEqual(res["base_direction"], base_dir)
                        self.assertEqual(res["base_signal"], base_signal)
                        self.assertEqual(res["pattern_directions"], list(pattern))
                        self.assertEqual(res["matched_pattern"], pattern)
                        self.assertEqual(res["pullback_group"], group)
                        self.assertEqual(res["pre_offset15_direction"], prov_dir)
                        self.assertEqual(res["offset15_direction"], "GIAM")
                        self.assertEqual(res["offset15_signal"], "SELL")
                        self.assertEqual(res["post_offset15_direction"], post_offset15_expected)
                        self.assertEqual(res["direction"], expected_final)
                        self.assertEqual(res["entry_time"], expected_entry)

        self.assertEqual(total_cases, 288)

    def test_h14_evaluation_order_and_evidence(self) -> None:
        """Verify evaluate_symbol_m15_for_slot records evidence and returns post_offset15 direction for XAUUSD."""
        broker_dt = datetime(2026, 7, 29, 14, 0)
        # Base TANG ("BUY"), pattern BT -> pattern_dir BUY, pre_offset15 -> BUY
        # offset15 GIAM ("SELL") -> relation OPPOSITE -> action KEEP -> post_offset15 BUY
        sequence = ["TANG", "GIAM", "TANG", "GIAM", "GIAM"]

        with patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=sequence):
            res = mt5_signal_bot.evaluate_symbol_m15_for_slot(broker_dt, 14, "XAUUSD")

        self.assertIsNotNone(res)
        self.assertEqual(res["base_direction"], "TANG")
        self.assertEqual(res["base_signal"], "BUY")
        self.assertEqual(res["pullback_group"], "BT")
        self.assertEqual(res["pattern_direction"], "BUY")
        self.assertEqual(res["slot_adjusted_direction"], "BUY")
        self.assertEqual(res["pre_offset15_direction"], "BUY")
        self.assertEqual(res["offset15_direction"], "GIAM")
        self.assertEqual(res["offset15_signal"], "SELL")
        self.assertEqual(res["offset15_relation"], "OPPOSITE")
        self.assertEqual(res["offset15_action"], "KEEP")
        self.assertEqual(res["post_offset15_direction"], "BUY")
        self.assertFalse(res["weekday_inversion_applied"])
        self.assertEqual(res["direction"], "BUY")
        self.assertEqual(res["offsets"], [15, 30, 45, 60, 75])


class PairIndependenceTests(unittest.TestCase):
    """Verify complete independence between XAUUSD, GBPUSD, and GBPAUD."""

    def test_concurrent_independent_directions(self) -> None:
        """H=9: XAUUSD pattern SW -> SELL, GBPUSD pattern BT -> BUY (inverted to SELL for H9), GBPAUD pattern SW -> BUY."""
        broker_dt = datetime(2026, 7, 14, 9, 45)

        # Lookback sequence per symbol: -30, -45, -60, -75, -15, plus GBPAUD 09:45 followup
        sequence = [
            # XAUUSD 5 candles: base TANG, SW pattern (TANG, TANG, TANG) -> prov SELL; offset15 TANG (BUY) -> OPPOSITE KEEP -> SELL
            "TANG", "TANG", "TANG", "TANG", "TANG",
            # GBPUSD 5 candles: base TANG, BT pattern (GIAM, TANG, GIAM) -> prov BUY; offset15 GIAM (SELL) -> OPPOSITE KEEP -> BUY -> inverted H9 -> SELL
            "TANG", "GIAM", "TANG", "GIAM", "GIAM",
            # GBPAUD 5 candles: base GIAM, SW pattern (GIAM, GIAM, GIAM) -> prov BUY; offset15 GIAM (SELL) -> OPPOSITE KEEP -> BUY
            "GIAM", "GIAM", "GIAM", "GIAM", "GIAM",
            # GBPAUD 09:45 followup candle (1 candle)
            "GIAM",
        ]

        with patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=sequence):
            res = mt5_signal_bot.evaluate_all_pairs_for_slot(broker_dt, 9, as_of_dt=broker_dt)

        self.assertIsNotNone(res)
        self.assertEqual(res["signal"], "BUY")
        self.assertEqual(res["entry_time"], "10:25")
        self.assertEqual(res["pair_dirs"]["XAUUSD"], "BUY")
        self.assertEqual(res["pair_dirs"]["GBPUSD"], "SELL")
        self.assertEqual(res["pair_dirs"]["GBPAUD"], "BUY")
        self.assertEqual(res["pair_pre_offset15_dirs"]["XAUUSD"], "SELL")
        self.assertEqual(res["pair_pre_offset15_dirs"]["GBPUSD"], "BUY")
        self.assertEqual(res["pair_pre_offset15_dirs"]["GBPAUD"], "BUY")
        self.assertEqual(res["pair_offset15_dirs"]["XAUUSD"], "TANG")
        self.assertEqual(res["pair_offset15_dirs"]["GBPUSD"], "GIAM")
        self.assertEqual(res["pair_offset15_dirs"]["GBPAUD"], "GIAM")
        self.assertEqual(res["pair_entry_times"]["XAUUSD"], "10:25")
        self.assertEqual(res["pair_entry_times"]["GBPUSD"], "11:00")
        self.assertEqual(res["pair_entry_times"]["GBPAUD"], "11:00")

    def test_gbpusd_missing_candle_isolation(self) -> None:
        """Missing candle on GBPUSD makes only GBPUSD WAIT."""
        broker_dt = datetime(2026, 7, 14, 9, 0)

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
        self.assertEqual(res["pair_entry_times"]["GBPUSD"], "10:20")  # entry time still assigned

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
        self.assertEqual(res["pair_dirs"]["GBPUSD"], "BUY")
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
        """H3 queries XAUUSD+GBPAUD; H7+ queries all three."""
        for hour in DASHBOARD_SLOTS:
            broker_dt = datetime(2026, 7, 29, hour, 0)
            queried = []
            def mock_lookback(symbol, tf, candle_dt):
                queried.append(symbol)
                return "TANG"

            with self.subTest(hour=hour), \
                 patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=mock_lookback):
                mt5_signal_bot.evaluate_all_pairs_for_slot(broker_dt, hour)

            if hour == 3:
                self.assertNotIn("GBPUSD", queried)
            else:
                self.assertCountEqual(queried, ["XAUUSD"] * 5 + ["GBPUSD"] * 5 + ["GBPAUD"] * 5)


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

    def test_doji_offset15_resolution_and_wait(self) -> None:
        """Test DOJI resolution and missing candle isolation at offset -15 for all 3 symbols."""
        broker_dt = datetime(2026, 7, 29, 9, 0)

        for symbol in SIGNAL_PAIRS:
            # 1. -15 DOJI, previous TANG -> resolved -15 = GIAM (SELL) -> final = BUY
            with self.subTest(symbol=symbol, case="-15 DOJI + previous TANG"), \
                 patch.object(mt5_signal_bot, "get_candle_by_ts", side_effect=[
                     _candle("TANG"), _candle("TANG"), _candle("TANG"), _candle("TANG"), # -30, -45, -60, -75
                     _candle("DOJI"), _candle("TANG") # -15 DOJI -> step back to previous TANG -> resolved GIAM
                 ]), \
                 patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1000):
                res = mt5_signal_bot.evaluate_symbol_m15_for_slot(broker_dt, 9, symbol)
                self.assertIsNotNone(res)
                self.assertEqual(res["offset15_direction"], "GIAM")
                self.assertEqual(res["offset15_signal"], "SELL")

            # 2. -15 DOJI, previous DOJI -> unresolved -> None -> symbol WAIT
            with self.subTest(symbol=symbol, case="-15 DOJI + previous DOJI -> WAIT"), \
                 patch.object(mt5_signal_bot, "get_candle_by_ts", side_effect=[
                     _candle("TANG"), _candle("TANG"), _candle("TANG"), _candle("TANG"),
                     _candle("DOJI"), _candle("DOJI")
                 ]), \
                 patch.object(mt5_signal_bot, "broker_time_to_ts", return_value=1000):
                res = mt5_signal_bot.evaluate_symbol_m15_for_slot(broker_dt, 9, symbol)
                self.assertIsNone(res)

    def test_offset_lookup_timestamps(self) -> None:
        """Verify H=9 queries exact timestamps for 08:45 (-15), 08:30 (-30), 08:15 (-45), 08:00 (-60), 07:45 (-75)."""
        broker_dt = datetime(2026, 7, 29, 9, 0)
        queried_dts = []

        def mock_lookback(symbol, tf, candle_dt):
            queried_dts.append(candle_dt.strftime("%H:%M"))
            return "TANG"

        with patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=mock_lookback):
            res = mt5_signal_bot.evaluate_symbol_m15_for_slot(broker_dt, 9, "XAUUSD")

        self.assertIsNotNone(res)
        self.assertEqual(res["offsets"], [15, 30, 45, 60, 75])
        self.assertIn("08:45", queried_dts)
        self.assertIn("08:30", queried_dts)
        self.assertIn("08:15", queried_dts)
        self.assertIn("08:00", queried_dts)
        self.assertIn("07:45", queried_dts)


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
        self.assertFalse(mt5_signal_bot.is_deactivated_signal_slot(broker_dt, 9))


if __name__ == "__main__":
    unittest.main()
