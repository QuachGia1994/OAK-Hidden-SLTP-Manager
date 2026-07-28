"""Regression coverage for the M15 canonical matrix (v52+).

Truth table (24 cases = 6 hours × 2 groups × 2 base directions):

Invariant 1: SW → XAUUSD reverses Base; BT → XAUUSD keeps Base.
Invariant 2: H=3/6/9 → GBPAUD opposite of Base; H=12/14/16 → GBPUSD same as Base.

Base=BUY:
  H=3/6/9  + SW: XAUUSD=SELL, GBP=SELL
  H=3/6/9  + BT: XAUUSD=BUY,  GBP=SELL
  H=12/14/16 + SW: XAUUSD=SELL, GBP=BUY
  H=12/14/16 + BT: XAUUSD=BUY,  GBP=BUY

Base=SELL:
  H=3/6/9  + SW: XAUUSD=BUY,  GBP=BUY
  H=3/6/9  + BT: XAUUSD=SELL, GBP=BUY
  H=12/14/16 + SW: XAUUSD=BUY,  GBP=SELL
  H=12/14/16 + BT: XAUUSD=SELL, GBP=SELL
"""
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import unittest

import mt5_signal_bot


ACTIVE_SLOTS = (3, 4, 6, 9, 12, 14, 16)
DASHBOARD_SLOTS = (3, 6, 9, 12, 14, 16)
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


# Truth table: (hour_group, base_direction, pullback_group) → (xau_signal, gbp_signal)
# hour_group: "early" = H=3/6/9, "late" = H=12/14/16
_TRUTH_TABLE = {
    # Base=BUY (TANG)
    ("early", "TANG", "SW"): ("SELL", "SELL"),
    ("early", "TANG", "BT"): ("BUY", "SELL"),
    ("late", "TANG", "SW"): ("SELL", "BUY"),
    ("late", "TANG", "BT"): ("BUY", "BUY"),
    # Base=SELL (GIAM)
    ("early", "GIAM", "SW"): ("BUY", "BUY"),
    ("early", "GIAM", "BT"): ("SELL", "BUY"),
    ("late", "GIAM", "SW"): ("BUY", "SELL"),
    ("late", "GIAM", "BT"): ("SELL", "SELL"),
}


def _pullback_directions(group: str) -> tuple[str, str, str]:
    """Return 3 pullback candle directions that classify to the given group."""
    return {
        "SW": ("GIAM", "GIAM", "GIAM"),  # giảm giảm giảm → SW
        "BT": ("GIAM", "TANG", "GIAM"),  # giảm tăng giảm → BT
    }[group]


class M15CanonicalMatrixTests(unittest.TestCase):
    """24-case truth table regression: 6 hours × 2 base directions × 2 groups."""

    def test_active_slots_and_logic_version(self) -> None:
        self.assertEqual(mt5_signal_bot.ACTIVE_HOURS, frozenset(ACTIVE_SLOTS))
        self.assertEqual(mt5_signal_bot.SIGNAL_LOGIC_VERSION, 52)

    def test_dashboard_excludes_h4_h5(self) -> None:
        """H=4 and H=5 must not appear in dashboard TARGET_HOURS."""
        self.assertNotIn(4, DASHBOARD_SLOTS)
        self.assertNotIn(5, DASHBOARD_SLOTS)
        for h in DASHBOARD_SLOTS:
            self.assertIn(h, (3, 6, 9, 12, 14, 16))

    def test_pair_selection_by_hour(self) -> None:
        for h in (3, 6, 9):
            self.assertEqual(mt5_signal_bot._m15_pair_for_hour(h), "GBPAUD")
        for h in (12, 14, 16):
            self.assertEqual(mt5_signal_bot._m15_pair_for_hour(h), "GBPUSD")
        self.assertIsNone(mt5_signal_bot._m15_pair_for_hour(4))

    def test_truth_table_all_24_cases(self) -> None:
        """Verify all 24 combinations against the canonical truth table."""
        prev_session = datetime(2026, 7, 13).date()
        for hour in DASHBOARD_SLOTS:
            hour_group = "early" if hour in (3, 6, 9) else "late"
            for base_dir in ("TANG", "GIAM"):
                for group in ("SW", "BT"):
                    expected_xau, expected_gbp = _TRUTH_TABLE[(hour_group, base_dir, group)]
                    pullback = _pullback_directions(group)
                    directions = (base_dir,) + pullback

                    with self.subTest(hour=hour, base=base_dir, group=group), \
                         patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=directions), \
                         patch.object(mt5_signal_bot, "resolve_previous_broker_session", return_value=prev_session):
                        result = mt5_signal_bot.evaluate_m15_4candle_for_slot(
                            datetime(2026, 7, 14, 12, 0), hour,
                        )

                    self.assertEqual(result["xau_signal"], expected_xau,
                                     f"H={hour} base={base_dir} group={group}: XAUUSD mismatch")
                    self.assertEqual(result["gbp_signal"], expected_gbp,
                                     f"H={hour} base={base_dir} group={group}: GBP mismatch")
                    self.assertEqual(result["pullback_group"], group)
                    self.assertEqual(result["base_direction"], base_dir)

    def test_entry_time_sw_bt(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        for group in ("SW", "BT"):
            for hour in DASHBOARD_SLOTS:
                expected = f"{hour + 1:02d}:25" if group == "SW" else f"{hour:02d}:49"
                with self.subTest(hour=hour, group=group), \
                     patch.object(mt5_signal_bot, "evaluate_m15_4candle_for_slot",
                                  return_value={
                                      "base_direction": "TANG", "base_signal": "BUY",
                                      "pullback_group": group,
                                      "xau_signal": "BUY", "gbp_signal": "SELL",
                                      "pair": mt5_signal_bot._m15_pair_for_hour(hour),
                                  }):
                    self.assertEqual(
                        mt5_signal_bot.get_entry_time_for_slot(broker_dt, hour), expected,
                    )

    def test_evaluate_gbp_h1_slot_pair_dirs(self) -> None:
        """Verify pair_dirs contains correct XAUUSD + GBP pair."""
        broker_dt = datetime(2026, 7, 14, 12, 0)
        for hour in DASHBOARD_SLOTS:
            pair = mt5_signal_bot._m15_pair_for_hour(hour)
            m15 = {
                "base_direction": "TANG", "base_signal": "BUY",
                "pullback_group": "BT",
                "xau_signal": "BUY", "gbp_signal": "SELL" if hour in (3, 6, 9) else "BUY",
                "pair": pair,
            }
            with self.subTest(hour=hour), \
                 patch.object(mt5_signal_bot, "evaluate_m15_4candle_for_slot", return_value=m15):
                result = mt5_signal_bot.evaluate_gbp_h1_slot(broker_dt, hour)
            self.assertEqual(result["signal"], "BUY")
            self.assertIn("XAUUSD", result["pair_dirs"])
            self.assertIn(pair, result["pair_dirs"])
            self.assertEqual(result["pair_dirs"]["XAUUSD"], "BUY")

    def test_m15_4candle_uses_previous_session_candles(self) -> None:
        broker_dt = datetime(2026, 7, 14, 9, 0)
        prev_session = datetime(2026, 7, 13).date()
        seen: list[datetime] = []

        def lookback(symbol, tf, candle_dt):
            seen.append(candle_dt)
            return "TANG"

        with patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=lookback), \
             patch.object(mt5_signal_bot, "resolve_previous_broker_session", return_value=prev_session):
            mt5_signal_bot.evaluate_m15_4candle_for_slot(broker_dt, 9)

        for dt in seen:
            self.assertEqual(dt.date(), prev_session)
        self.assertCountEqual(seen, [
            datetime(2026, 7, 13, 8, 30),
            datetime(2026, 7, 13, 8, 15),
            datetime(2026, 7, 13, 8, 0),
            datetime(2026, 7, 13, 7, 45),
        ])

    def test_m15_4candle_none_when_missing(self) -> None:
        broker_dt = datetime(2026, 7, 14, 9, 0)
        prev_session = datetime(2026, 7, 13).date()
        with patch.object(mt5_signal_bot, "_lookback_candle_direction", return_value=None), \
             patch.object(mt5_signal_bot, "resolve_previous_broker_session", return_value=prev_session):
            self.assertIsNone(mt5_signal_bot.evaluate_m15_4candle_for_slot(broker_dt, 9))

    def test_m15_4candle_none_for_h4(self) -> None:
        broker_dt = datetime(2026, 7, 14, 9, 0)
        self.assertIsNone(mt5_signal_bot.evaluate_m15_4candle_for_slot(broker_dt, 4))

    def test_evaluate_gbp_h1_slot_h4_legacy(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        h1 = mt5_signal_bot.mt5.TIMEFRAME_H1
        prev_session = datetime(2026, 7, 13).date()
        candles = {
            ("GBPUSD", h1, datetime.combine(prev_session, datetime.min.time()).replace(hour=3)): _candle("TANG"),
            ("GBPUSD", h1, datetime.combine(prev_session, datetime.min.time()).replace(hour=2)): _candle("GIAM"),
            ("GBPAUD", h1, datetime.combine(prev_session, datetime.min.time()).replace(hour=3)): _candle("TANG"),
            ("GBPAUD", h1, datetime.combine(prev_session, datetime.min.time()).replace(hour=2)): _candle("GIAM"),
        }

        def get_candle(symbol, timeframe, timestamp):
            target = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
            return candles.get((symbol, timeframe, target))

        with (
            patch.object(mt5_signal_bot, "broker_time_to_ts", side_effect=_timestamp),
            patch.object(mt5_signal_bot, "get_candle_by_ts", side_effect=get_candle),
            patch.object(mt5_signal_bot, "resolve_previous_broker_session", return_value=prev_session),
        ):
            result = mt5_signal_bot.evaluate_gbp_h1_slot(broker_dt, 4)
        self.assertEqual(result["signal"], "BUY")
        self.assertEqual(result["entry_time"], "04:11")

    def test_active_calculation_no_legacy_paths(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        result = {
            "signal": "BUY",
            "entry_time": "12:49",
            "pair_dirs": {"XAUUSD": "BUY", "GBPUSD": "BUY"},
        }
        for hour in ACTIVE_SLOTS:
            with self.subTest(hour=hour), ExitStack() as stack:
                evaluate = stack.enter_context(
                    patch.object(mt5_signal_bot, "evaluate_gbp_h1_slot", return_value=dict(result))
                )
                for name in LEGACY_SEAMS:
                    stack.enter_context(
                        patch.object(mt5_signal_bot, name,
                                     side_effect=AssertionError(f"legacy: {name}"), create=True)
                    )
                calculated = mt5_signal_bot.calculate_slot_signal(broker_dt, hour)
            evaluate.assert_called_once_with(broker_dt, hour)
            self.assertEqual(calculated["signal"], "BUY")

    def test_h4_and_thursday_h3_deactivated(self) -> None:
        result = {"signal": "BUY", "entry_time": "03:49", "pair_dirs": {"XAUUSD": "BUY", "GBPAUD": "SELL"}}
        with patch.object(mt5_signal_bot, "evaluate_gbp_h1_slot", side_effect=lambda *_: dict(result)):
            self.assertTrue(mt5_signal_bot.calculate_slot_signal(datetime(2026, 7, 14, 4), 4)["deactivated"])
            self.assertTrue(mt5_signal_bot.calculate_slot_signal(datetime(2026, 7, 23, 3), 3)["deactivated"])
            self.assertFalse(mt5_signal_bot.calculate_slot_signal(datetime(2026, 7, 24, 3), 3).get("deactivated", False))

    def test_get_hour_note_correct_matrix(self) -> None:
        note_h9 = mt5_signal_bot.get_hour_note(9)
        self.assertIn("GBPAUD", note_h9)
        self.assertIn("SW", note_h9)
        self.assertIn("BT", note_h9)

        note_h14 = mt5_signal_bot.get_hour_note(14)
        self.assertIn("GBPUSD", note_h14)

        note_h4 = mt5_signal_bot.get_hour_note(4)
        self.assertIn("H1", note_h4)


if __name__ == "__main__":
    unittest.main()
