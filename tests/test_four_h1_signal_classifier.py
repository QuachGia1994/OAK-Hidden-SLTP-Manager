"""Regression tests for the v71 four-H1 signal classifier."""
from datetime import date, datetime
from itertools import product
from unittest.mock import patch
import unittest

import mt5_signal_bot


EXPECTED_GROUPS = {
    ("TANG", "TANG", "TANG", "TANG"): "SW",
    ("TANG", "TANG", "TANG", "GIAM"): "SW",
    ("TANG", "TANG", "GIAM", "TANG"): "BT",
    ("TANG", "TANG", "GIAM", "GIAM"): "BT",
    ("TANG", "GIAM", "TANG", "TANG"): "BT",
    ("TANG", "GIAM", "TANG", "GIAM"): "SW",
    ("TANG", "GIAM", "GIAM", "TANG"): "SW",
    ("TANG", "GIAM", "GIAM", "GIAM"): "SW",
    ("GIAM", "GIAM", "GIAM", "GIAM"): "SW",
    ("GIAM", "GIAM", "GIAM", "TANG"): "SW",
    ("GIAM", "GIAM", "TANG", "GIAM"): "BT",
    ("GIAM", "GIAM", "TANG", "TANG"): "BT",
    ("GIAM", "TANG", "GIAM", "GIAM"): "BT",
    ("GIAM", "TANG", "GIAM", "TANG"): "SW",
    ("GIAM", "TANG", "TANG", "GIAM"): "SW",
    ("GIAM", "TANG", "TANG", "TANG"): "SW",
}

EXPECTED_THREE_GROUPS = {
    ("TANG", "TANG", "TANG"): "SW",
    ("GIAM", "TANG", "TANG"): "SW",
    ("GIAM", "TANG", "GIAM"): "BT",
    ("GIAM", "GIAM", "TANG"): "BT",
    ("GIAM", "GIAM", "GIAM"): "SW",
    ("TANG", "GIAM", "GIAM"): "SW",
    ("TANG", "GIAM", "TANG"): "BT",
    ("TANG", "TANG", "GIAM"): "BT",
}


def _evidence(direction: str, open_time: datetime) -> dict[str, object]:
    return {
        "role": "C1",
        "state": "READY",
        "open_time": open_time.isoformat(),
        "close_time": open_time.replace(hour=open_time.hour + 1).isoformat(),
        "resolved_direction": direction,
        "direction": "BUY" if direction == "TANG" else "SELL",
    }


class FourH1ClassifierTests(unittest.TestCase):
    def test_all_sixteen_sequences_are_covered_by_the_ten_rules(self) -> None:
        sequences = set(product(("TANG", "GIAM"), repeat=4))
        self.assertEqual(sequences, set(EXPECTED_GROUPS))
        for directions, expected_group in EXPECTED_GROUPS.items():
            with self.subTest(directions=directions):
                self.assertEqual(
                    mt5_signal_bot.classify_four_h1_group(directions),
                    expected_group,
                )

    def test_invalid_or_incomplete_sequence_fails_closed(self) -> None:
        self.assertIsNone(
            mt5_signal_bot.classify_four_h1_group(("TANG", "GIAM", None, "TANG"))
        )
        self.assertIsNone(
            mt5_signal_bot.classify_four_h1_group(("TANG", "GIAM", "DOJI", "TANG"))
        )

    def test_signal_base_uses_c1_and_sw_bt_group(self) -> None:
        self.assertEqual(mt5_signal_bot.derive_signal_base("TANG", "SW"), "SELL")
        self.assertEqual(mt5_signal_bot.derive_signal_base("TANG", "BT"), "BUY")
        self.assertEqual(mt5_signal_bot.derive_signal_base("GIAM", "SW"), "BUY")
        self.assertEqual(mt5_signal_bot.derive_signal_base("GIAM", "BT"), "SELL")

    def test_h3_three_candle_classifier_covers_all_eight_sequences(self) -> None:
        sequences = set(product(("TANG", "GIAM"), repeat=3))
        self.assertEqual(sequences, set(EXPECTED_THREE_GROUPS))
        for directions, expected_group in EXPECTED_THREE_GROUPS.items():
            with self.subTest(directions=directions):
                self.assertEqual(
                    mt5_signal_bot.classify_three_candle_group(directions),
                    expected_group,
                )

    def test_entry_branches_and_exact_exceptions(self) -> None:
        self.assertEqual(mt5_signal_bot.apply_entry_rule("BUY", "07:11", 7), "SELL")
        self.assertEqual(mt5_signal_bot.apply_entry_rule("BUY", "07:49", 7), "SELL")
        self.assertEqual(mt5_signal_bot.apply_entry_rule("BUY", "08:25", 7), "BUY")
        self.assertEqual(mt5_signal_bot.apply_entry_rule("BUY", "15:25", 14), "SELL")
        self.assertEqual(mt5_signal_bot.apply_entry_rule("BUY", "16:49", 16), "BUY")
        self.assertEqual(mt5_signal_bot.apply_entry_rule("BUY", "17:25", 16), "BUY")
        self.assertEqual(mt5_signal_bot.apply_entry_rule("BUY", "15:11", 15), "WAIT")


class FourH1WindowTests(unittest.TestCase):
    def _capture_window(self, entry_time: str) -> tuple[dict[str, object], list[datetime]]:
        slot_dt = datetime(2026, 7, 29, 9, 0)
        captured: list[datetime] = []
        directions = iter(("TANG", "TANG", "GIAM", "TANG"))

        def read(_symbol: str, candle_dt: datetime, role: str):
            captured.append(candle_dt)
            item = _evidence(next(directions), candle_dt)
            item["role"] = role
            return item

        with patch.object(mt5_signal_bot, "read_h1_candle_evidence", side_effect=read):
            result = mt5_signal_bot.evaluate_pair_from_selected_h1(
                slot_dt,
                9,
                "XAUUSD",
                entry_time,
                as_of_dt=datetime(2026, 7, 29, 10, 1),
            )
        return result, captured

    def test_h_plus_1_25_uses_h_h_minus_1_h_minus_2_h_minus_3(self) -> None:
        result, captured = self._capture_window("10:25")
        self.assertEqual(
            captured,
            [
                datetime(2026, 7, 29, 9),
                datetime(2026, 7, 29, 8),
                datetime(2026, 7, 29, 7),
                datetime(2026, 7, 29, 6),
            ],
        )
        self.assertEqual(result["group"], "BT")
        self.assertEqual(result["direction"], "BUY")

    def test_h11_and_h49_use_h_minus_1_through_h_minus_4(self) -> None:
        for entry_time in ("09:11", "09:49"):
            with self.subTest(entry_time=entry_time):
                result, captured = self._capture_window(entry_time)
                self.assertEqual(
                    captured,
                    [
                        datetime(2026, 7, 29, 8),
                        datetime(2026, 7, 29, 7),
                        datetime(2026, 7, 29, 6),
                        datetime(2026, 7, 29, 5),
                    ],
                )
                self.assertEqual(result["direction"], "SELL")

    def test_h_plus_1_base_is_pending_until_its_h1_close(self) -> None:
        result = mt5_signal_bot.evaluate_pair_from_selected_h1(
            datetime(2026, 7, 29, 9),
            9,
            "XAUUSD",
            "10:25",
            as_of_dt=datetime(2026, 7, 29, 9, 59),
        )
        self.assertEqual(result["direction"], "WAIT")
        self.assertEqual(result["classification_reason"], "PENDING_H1_BASE_CANDLE")

    def test_h3_uses_previous_session_0400_base_then_0300_0200(self) -> None:
        slot_dt = datetime(2026, 7, 29, 3)
        captured: list[datetime] = []

        def read(_symbol: str, candle_dt: datetime, role: str):
            captured.append(candle_dt)
            direction = {4: "TANG", 3: "TANG", 2: "GIAM"}[candle_dt.hour]
            item = _evidence(direction, candle_dt)
            item["role"] = role
            return item

        for entry_time in ("03:11", "03:49", "04:25"):
            captured.clear()
            with self.subTest(entry_time=entry_time), patch.object(
                mt5_signal_bot,
                "resolve_previous_broker_session",
                return_value=date(2026, 7, 28),
            ), patch.object(
                mt5_signal_bot,
                "read_h1_candle_evidence",
                side_effect=read,
            ):
                result = mt5_signal_bot.evaluate_pair_from_selected_h1(
                    slot_dt, 3, "GBPJPY", entry_time
                )
            self.assertEqual(captured, [
                datetime(2026, 7, 28, 4),
                datetime(2026, 7, 28, 3),
                datetime(2026, 7, 28, 2),
            ])
            self.assertEqual(result["group"], "BT")
            self.assertEqual(result["direction"], "BUY")

    def test_thursday_reuses_monday_bt_but_monday_sw_waits_until_h7(self) -> None:
        thursday = datetime(2026, 7, 30, 3)
        bt = {"group": "BT", "direction": "SELL", "classification_reason": "source"}
        sw = {"group": "SW", "direction": "BUY", "classification_reason": "source"}
        with patch.object(mt5_signal_bot, "_evaluate_h3_source", return_value=bt):
            result = mt5_signal_bot.evaluate_pair_from_selected_h1(
                thursday, 3, "XAUUSD", "03:11"
            )
        self.assertEqual(result["direction"], "SELL")
        self.assertEqual(result["reused_monday"], "2026-07-27")
        self.assertEqual(result["classification_reason"], "THURSDAY_REUSE_MONDAY_BT")

        with patch.object(mt5_signal_bot, "_evaluate_h3_source", return_value=sw):
            result = mt5_signal_bot.evaluate_pair_from_selected_h1(
                thursday, 3, "XAUUSD", "03:49"
            )
        self.assertEqual(result["direction"], "WAIT")
        self.assertEqual(result["classification_reason"], "THURSDAY_MONDAY_SW_WAIT_UNTIL_H7")


class DashboardEvidenceTests(unittest.TestCase):
    def test_builds_one_versioned_h1_record_per_symbol(self) -> None:
        slot_dt = datetime(2026, 7, 29, 9)
        evidence = {
            symbol: {
                "timeframe": "H1",
                "group": "BT",
                "direction": "BUY",
                "candles": [_evidence("TANG", slot_dt.replace(hour=8))],
            }
            for symbol in mt5_signal_bot.SIGNAL_PAIRS
        }
        result = {
            "logic_version": 71,
            "entry_time": "09:11",
            "entry_state": "READY",
            "entry_rule": "H9_OPPOSITE",
            "pair_signal_states": {symbol: "READY" for symbol in evidence},
            "pair_evidence": evidence,
        }

        records = mt5_signal_bot._dashboard_signal_evidence(slot_dt, 9, result)

        self.assertEqual(len(records), 5)
        self.assertIn("2026-07-29:9:XAUUSD:v71", records)
        self.assertIn("2026-07-29:9:GBPCAD:v71", records)
        self.assertEqual(records["2026-07-29:9:GBPJPY:v71"]["timeframe"], "H1")
        self.assertEqual(records["2026-07-29:9:GBPJPY:v71"]["signal_state"], "READY")

    def test_h3_signal_evidence_does_not_wait_for_stage_a_entry(self) -> None:
        pending_entry = {"entry_state": "PENDING_FOLLOWUP", "entry_time": None}
        evidence = {
            "group": "SW",
            "direction": "WAIT",
            "classification_reason": "THURSDAY_MONDAY_SW_WAIT_UNTIL_H7",
        }
        with patch.object(
            mt5_signal_bot,
            "evaluate_pair_from_selected_h1",
            return_value=evidence,
        ):
            directions, pair_evidence = mt5_signal_bot._derive_pair_signals_and_evidence(
                datetime(2026, 7, 30, 3),
                3,
                pending_entry,
            )
        self.assertEqual(directions["XAUUSD"], "WAIT")
        self.assertEqual(pair_evidence["XAUUSD"]["group"], "SW")


if __name__ == "__main__":
    unittest.main()
