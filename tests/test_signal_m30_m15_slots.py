"""Regression coverage for the M15 4-candle slot algorithm (v50+)."""
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import unittest

import mt5_signal_bot


ACTIVE_SLOTS = (3, 4, 6, 9, 12, 14, 16)
LEGACY_SEAMS = (
    "analyze",
    "apply_xauusd_m30_logic",
    "evaluate_3_m30_classification_for_h3",
    "evaluate_4_m30_classification_before_hour",
    "evaluate_classification_for_slot",
    "evaluate_h3_candle_groups",
    "evaluate_h3_m30_slot",
    "evaluate_m30_m15_slot",
    "evaluate_slot_candle_groups",
    "_lookup_h3_signal_today",
    "_lookup_h4_signal_today",
    "_lookup_h16_signal_yesterday",
    "_lookup_signal_from_log",
)


def _candle(direction: str) -> dict[str, float]:
    if direction == "TANG":
        return {"open": 1.0, "high": 2.0, "low": 1.0, "close": 2.0}
    if direction == "GIAM":
        return {"open": 2.0, "high": 2.0, "low": 1.0, "close": 1.0}
    return {"open": 1.0, "high": 2.0, "low": 0.0, "close": 1.0}


def _timestamp(broker_dt: datetime, hour: int, minute: int = 0, second: int = 0) -> int:
    target = broker_dt.replace(hour=hour, minute=minute, second=second, microsecond=0)
    return int(target.replace(tzinfo=timezone.utc).timestamp())


def _m15_result(pair, base_dir, pullback_group, derived_signal):
    base_signal = "BUY" if base_dir == "TANG" else "SELL"
    return {
        "base_direction": base_dir,
        "base_signal": base_signal,
        "pullback_group": pullback_group,
        "derived_signal": derived_signal,
        "pair": pair,
    }


class M15FourCandleSlotTests(unittest.TestCase):
    def test_active_slots_and_logic_version_are_current(self) -> None:
        self.assertEqual(mt5_signal_bot.ACTIVE_HOURS, frozenset(ACTIVE_SLOTS))
        self.assertEqual(mt5_signal_bot.SIGNAL_LOGIC_VERSION, 50)
        self.assertEqual(mt5_signal_bot.GBP_SOURCE_PAIRS, ("GBPUSD", "GBPAUD"))

    def test_pair_selection_by_hour(self) -> None:
        self.assertEqual(mt5_signal_bot._m15_pair_for_hour(3), "GBPAUD")
        self.assertEqual(mt5_signal_bot._m15_pair_for_hour(6), "GBPAUD")
        self.assertEqual(mt5_signal_bot._m15_pair_for_hour(9), "GBPAUD")
        self.assertEqual(mt5_signal_bot._m15_pair_for_hour(12), "GBPUSD")
        self.assertEqual(mt5_signal_bot._m15_pair_for_hour(14), "GBPUSD")
        self.assertEqual(mt5_signal_bot._m15_pair_for_hour(16), "GBPUSD")
        self.assertIsNone(mt5_signal_bot._m15_pair_for_hour(4))

    def test_m15_4candle_uses_yesterday_candles(self) -> None:
        """Candles must come from yesterday, not today."""
        broker_dt = datetime(2026, 7, 14, 9, 0)
        seen: list[datetime] = []

        def lookback(symbol, tf, candle_dt):
            seen.append(candle_dt)
            return "TANG"

        with patch.object(
            mt5_signal_bot, "_lookback_candle_direction", side_effect=lookback,
        ):
            mt5_signal_bot.evaluate_m15_4candle_for_slot(broker_dt, 9)

        # All candles must be from yesterday (2026-07-13)
        for dt in seen:
            self.assertEqual(dt.date(), datetime(2026, 7, 13).date())
        # Specific times: 8:30, 8:15, 8:00, 7:45 yesterday
        self.assertCountEqual(seen, [
            datetime(2026, 7, 13, 8, 30),
            datetime(2026, 7, 13, 8, 15),
            datetime(2026, 7, 13, 8, 0),
            datetime(2026, 7, 13, 7, 45),
        ])

    def test_m15_4candle_base_sw_reverses(self) -> None:
        broker_dt = datetime(2026, 7, 14, 9, 0)
        directions = ("TANG", "GIAM", "GIAM", "GIAM")
        with patch.object(
            mt5_signal_bot, "_lookback_candle_direction", side_effect=directions,
        ):
            result = mt5_signal_bot.evaluate_m15_4candle_for_slot(broker_dt, 9)
        self.assertEqual(result["pair"], "GBPAUD")
        self.assertEqual(result["base_direction"], "TANG")
        self.assertEqual(result["base_signal"], "BUY")
        self.assertEqual(result["pullback_group"], "SW")
        self.assertEqual(result["derived_signal"], "SELL")

    def test_m15_4candle_base_bt_keeps(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        directions = ("GIAM", "TANG", "GIAM", "TANG")
        with patch.object(
            mt5_signal_bot, "_lookback_candle_direction", side_effect=directions,
        ):
            result = mt5_signal_bot.evaluate_m15_4candle_for_slot(broker_dt, 12)
        self.assertEqual(result["pair"], "GBPUSD")
        self.assertEqual(result["base_direction"], "GIAM")
        self.assertEqual(result["base_signal"], "SELL")
        self.assertEqual(result["pullback_group"], "BT")
        self.assertEqual(result["derived_signal"], "SELL")

    def test_m15_4candle_none_when_any_candle_missing(self) -> None:
        broker_dt = datetime(2026, 7, 14, 9, 0)
        with patch.object(mt5_signal_bot, "_lookback_candle_direction", return_value=None):
            self.assertIsNone(mt5_signal_bot.evaluate_m15_4candle_for_slot(broker_dt, 9))

    def test_m15_4candle_none_for_h4(self) -> None:
        broker_dt = datetime(2026, 7, 14, 9, 0)
        self.assertIsNone(mt5_signal_bot.evaluate_m15_4candle_for_slot(broker_dt, 4))

    def test_all_eight_pullback_sequences_classify_correctly(self) -> None:
        broker_dt = datetime(2026, 7, 14, 9, 0)
        expectations = {
            ("TANG", "TANG", "TANG", "TANG"): ("SW", "SELL"),
            ("TANG", "GIAM", "TANG", "TANG"): ("SW", "SELL"),
            ("TANG", "GIAM", "TANG", "GIAM"): ("BT", "BUY"),
            ("TANG", "GIAM", "GIAM", "TANG"): ("BT", "BUY"),
            ("GIAM", "GIAM", "GIAM", "GIAM"): ("SW", "BUY"),
            ("GIAM", "TANG", "GIAM", "GIAM"): ("SW", "BUY"),
            ("GIAM", "TANG", "GIAM", "TANG"): ("BT", "SELL"),
            ("GIAM", "TANG", "TANG", "GIAM"): ("BT", "SELL"),
        }
        for directions, (expected_group, expected_signal) in expectations.items():
            with self.subTest(directions=directions), patch.object(
                mt5_signal_bot, "_lookback_candle_direction", side_effect=directions,
            ):
                result = mt5_signal_bot.evaluate_m15_4candle_for_slot(broker_dt, 9)
            self.assertEqual(result["pullback_group"], expected_group)
            self.assertEqual(result["derived_signal"], expected_signal)

    def test_entry_time_sw_bt_for_all_m15_slots(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        m15_slots = (3, 6, 9, 12, 14, 16)
        for group in ("SW", "BT"):
            for hour in m15_slots:
                expected = f"{hour + 1:02d}:25" if group == "SW" else f"{hour:02d}:49"
                with self.subTest(hour=hour, group=group):
                    m15 = _m15_result(
                        mt5_signal_bot._m15_pair_for_hour(hour),
                        "TANG", group,
                        "SELL" if group == "SW" else "BUY",
                    )
                    with patch.object(
                        mt5_signal_bot, "evaluate_m15_4candle_for_slot", return_value=m15,
                    ):
                        self.assertEqual(
                            mt5_signal_bot.get_entry_time_for_slot(broker_dt, hour),
                            expected,
                        )

    def test_evaluate_gbp_h1_slot_uses_m15_for_non_h4(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        m15 = _m15_result("GBPAUD", "TANG", "BT", "BUY")
        with patch.object(
            mt5_signal_bot, "evaluate_m15_4candle_for_slot", return_value=m15,
        ) as mock_m15:
            result = mt5_signal_bot.evaluate_gbp_h1_slot(broker_dt, 9)
        mock_m15.assert_called_once_with(broker_dt, 9)
        self.assertEqual(result["signal"], "BUY")
        self.assertEqual(result["entry_time"], "09:49")
        self.assertEqual(result["m15_pair"], "GBPAUD")
        self.assertEqual(result["m15_pullback_group"], "BT")

    def test_evaluate_gbp_h1_slot_h4_still_uses_legacy_logic(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        h1 = mt5_signal_bot.mt5.TIMEFRAME_H1
        previous_day = broker_dt.date() - timedelta(days=1)
        candles = {
            ("GBPUSD", h1, datetime.combine(previous_day, datetime.min.time()).replace(hour=3)): _candle("TANG"),
            ("GBPUSD", h1, datetime.combine(previous_day, datetime.min.time()).replace(hour=2)): _candle("GIAM"),
            ("GBPAUD", h1, datetime.combine(previous_day, datetime.min.time()).replace(hour=3)): _candle("TANG"),
            ("GBPAUD", h1, datetime.combine(previous_day, datetime.min.time()).replace(hour=2)): _candle("GIAM"),
        }

        def get_candle(symbol, timeframe, timestamp):
            target = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
            return candles.get((symbol, timeframe, target))

        with (
            patch.object(mt5_signal_bot, "broker_time_to_ts", side_effect=_timestamp),
            patch.object(mt5_signal_bot, "get_candle_by_ts", side_effect=get_candle),
        ):
            result = mt5_signal_bot.evaluate_gbp_h1_slot(broker_dt, 4)
        self.assertEqual(result["signal"], "BUY")
        self.assertEqual(result["entry_time"], "04:11")

    def test_missing_or_unresolved_data_returns_wait(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        with patch.object(mt5_signal_bot, "evaluate_gbp_h1_slot", return_value=None):
            self.assertEqual(mt5_signal_bot.calculate_slot_signal(broker_dt, 12)["signal"], "WAIT")

        with patch.object(
            mt5_signal_bot, "_lookback_candle_direction", return_value=None,
        ):
            self.assertIsNone(mt5_signal_bot.evaluate_m15_4candle_for_slot(broker_dt, 9))

    def test_active_calculation_does_not_use_legacy_paths(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        result = {
            "signal": "BUY",
            "entry_time": "12:49",
            "pair_dirs": {"XAUUSD": "BUY"},
            "m15_pair": "GBPUSD",
            "m15_base_direction": "TANG",
            "m15_base_signal": "BUY",
            "m15_pullback_group": "BT",
        }

        for hour in ACTIVE_SLOTS:
            with self.subTest(hour=hour), ExitStack() as stack:
                evaluate = stack.enter_context(
                    patch.object(mt5_signal_bot, "evaluate_gbp_h1_slot", return_value=dict(result))
                )
                for name in LEGACY_SEAMS:
                    stack.enter_context(
                        patch.object(
                            mt5_signal_bot, name,
                            side_effect=AssertionError(f"legacy path used: {name}"),
                            create=True,
                        )
                    )
                calculated = mt5_signal_bot.calculate_slot_signal(broker_dt, hour)

            evaluate.assert_called_once_with(broker_dt, hour)
            self.assertEqual(calculated["signal"], "BUY")

    def test_h4_and_thursday_h3_are_deactivated_only(self) -> None:
        result = {
            "signal": "BUY",
            "entry_time": "03:49",
            "pair_dirs": {"XAUUSD": "BUY"},
        }
        with patch.object(
            mt5_signal_bot, "evaluate_gbp_h1_slot",
            side_effect=lambda *_args: dict(result),
        ):
            self.assertTrue(mt5_signal_bot.calculate_slot_signal(datetime(2026, 7, 14, 4), 4)["deactivated"])
            self.assertTrue(mt5_signal_bot.calculate_slot_signal(datetime(2026, 7, 23, 3), 3)["deactivated"])
            friday = mt5_signal_bot.calculate_slot_signal(datetime(2026, 7, 24, 3), 3)

        self.assertFalse(friday.get("deactivated", False))

    def test_get_hour_note_describes_m15_pair(self) -> None:
        note_h9 = mt5_signal_bot.get_hour_note(9)
        self.assertIn("GBPAUD", note_h9)
        self.assertIn("4-candle", note_h9)

        note_h14 = mt5_signal_bot.get_hour_note(14)
        self.assertIn("GBPUSD", note_h14)

        note_h4 = mt5_signal_bot.get_hour_note(4)
        self.assertIn("GBPUSD/GBPAUD H1", note_h4)
        self.assertIn("DO NOT ENTER", note_h4)


if __name__ == "__main__":
    unittest.main()
