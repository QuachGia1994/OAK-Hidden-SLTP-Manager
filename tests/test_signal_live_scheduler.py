"""Live scheduler guards, retries, and logical slot identity."""
from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


class SignalLiveSchedulerTests(unittest.TestCase):
    def test_incomplete_signal_retries_before_deadline(self) -> None:
        broker_dt = datetime(2026, 7, 14, 6, 5)
        pending = set()

        with (
            patch.object(mt5_signal_bot, "sent_today", pending),
            patch.object(
                mt5_signal_bot,
                "calculate_slot_signal",
                return_value={"signal": "WAIT", "report": "missing candle"},
            ) as calculate,
            patch.object(mt5_signal_bot, "_save_state") as save,
        ):
            emitted = mt5_signal_bot._process_live_slot(broker_dt, 6)

        self.assertFalse(emitted)
        calculate.assert_called_once_with(broker_dt, 6)
        save.assert_not_called()
        self.assertEqual(pending, set())

    def test_slot_is_marked_missed_after_entry_deadline(self) -> None:
        broker_dt = datetime(2026, 7, 14, 6, 12)
        sent = set()

        with (
            patch.object(mt5_signal_bot, "sent_today", sent),
            patch.object(mt5_signal_bot, "calculate_slot_signal") as calculate,
            patch.object(mt5_signal_bot, "_save_state") as save,
        ):
            emitted = mt5_signal_bot._process_live_slot(broker_dt, 6)

        self.assertFalse(emitted)
        calculate.assert_not_called()
        save.assert_called_once()
        self.assertEqual(sent, {(broker_dt.date(), 6)})

    def test_restart_marks_passed_publications_without_catch_up(self) -> None:
        broker_dt = datetime(2026, 7, 14, 10, 0)
        sent = set()

        with patch.object(mt5_signal_bot, "sent_today", sent):
            mt5_signal_bot._mark_passed_slots_on_startup(broker_dt)

        self.assertEqual(
            sent,
            {
                (broker_dt.date(), 3),
                (broker_dt.date(), 4),
                (broker_dt.date(), 5),
                (broker_dt.date(), 6),
                (broker_dt.date(), 9),
            },
        )

    def test_sent_guard_prevents_duplicate_calculation(self) -> None:
        broker_dt = datetime(2026, 7, 14, 6, 5)
        sent = {(broker_dt.date(), 6)}

        with (
            patch.object(mt5_signal_bot, "sent_today", sent),
            patch.object(mt5_signal_bot, "calculate_slot_signal") as calculate,
        ):
            emitted = mt5_signal_bot._process_live_slot(broker_dt, 6)

        self.assertFalse(emitted)
        calculate.assert_not_called()

    def test_h3_is_logged_with_logical_hour_and_deactivated_flag(self) -> None:
        broker_dt = datetime(2026, 8, 6, 3, 0)
        sent = set()
        result = {
            "signal": "BUY",
            "report": "special H3 warning",
            "pattern_signal": "BUY",
            "deactivated": True,
            "pair_dirs": {"XAUUSD": "BUY", "GBPAUD": "SELL"},
            "skip_xau_m30": True,
        }

        with (
            patch.object(mt5_signal_bot, "sent_today", sent),
            patch.object(mt5_signal_bot, "calculate_slot_signal", return_value=result),
            patch.object(mt5_signal_bot, "evaluate_3_m30_classification_for_h3", return_value="BT"),
            patch.object(mt5_signal_bot, "log_signal") as log_signal,
            patch.object(mt5_signal_bot, "push_to_dashboard"),
            patch.object(mt5_signal_bot, "send_report", return_value=result["pair_dirs"]),
            patch.object(mt5_signal_bot, "_save_state"),
        ):
            emitted = mt5_signal_bot._process_live_slot(broker_dt, 3)

        self.assertTrue(emitted)
        self.assertEqual(log_signal.call_args.args[:4], (3, broker_dt, "BUY", "03:11"))
        self.assertTrue(log_signal.call_args.kwargs["deactivated"])
        self.assertIn((broker_dt.date(), 3), sent)


if __name__ == "__main__":
    unittest.main()
