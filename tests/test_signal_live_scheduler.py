"""Live scheduler guards for the v72 H:00 two-layer M30 engine."""

from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


def _result(signal="BUY", entry="07:11"):
    state = "READY" if signal in ("BUY", "SELL") else "WAIT"
    pair_dirs = {symbol: signal if state == "READY" else "WAIT" for symbol in mt5_signal_bot.SIGNAL_PAIRS}
    pair_entries = {
        symbol: (entry if symbol == "XAUUSD" else "08:00") if state == "READY" else None
        for symbol in mt5_signal_bot.SIGNAL_PAIRS
    }
    return {
        "signal": signal,
        "signal_state": state,
        "entry_state": state,
        "entry_time": entry if state == "READY" else None,
        "pair_dirs": pair_dirs,
        "pair_entry_times": pair_entries,
        "pair_signal_states": {symbol: state for symbol in mt5_signal_bot.SIGNAL_PAIRS},
        "pair_entry_states": {symbol: state for symbol in mt5_signal_bot.SIGNAL_PAIRS},
    }


class SignalLiveSchedulerTests(unittest.TestCase):
    def test_incomplete_signal_retries_before_latest_candidate(self) -> None:
        broker_dt = datetime(2026, 7, 14, 7, 5)
        sent = set()
        with (
            patch.object(mt5_signal_bot, "sent_today", sent),
            patch.object(mt5_signal_bot, "calculate_slot_signal", return_value=_result("WAIT")),
            patch.object(mt5_signal_bot, "_persist_live_result") as persist,
            patch.object(mt5_signal_bot, "_save_state") as save,
        ):
            emitted = mt5_signal_bot._process_live_slot(broker_dt, 7)

        self.assertFalse(emitted)
        persist.assert_called_once()
        save.assert_not_called()
        self.assertEqual(sent, set())

    def test_incomplete_signal_is_missed_after_latest_candidate(self) -> None:
        broker_dt = datetime(2026, 7, 14, 8, 26)
        sent = set()
        with (
            patch.object(mt5_signal_bot, "sent_today", sent),
            patch.object(mt5_signal_bot, "calculate_slot_signal", return_value=_result("WAIT")),
            patch.object(mt5_signal_bot, "_persist_live_result"),
            patch.object(mt5_signal_bot, "_save_state") as save,
        ):
            emitted = mt5_signal_bot._process_live_slot(broker_dt, 7)

        self.assertFalse(emitted)
        self.assertEqual(sent, {(broker_dt.date(), 7)})
        save.assert_called_once()

    def test_ready_signal_is_never_emitted_after_its_entry(self) -> None:
        broker_dt = datetime(2026, 7, 14, 7, 12)
        sent = set()
        with (
            patch.object(mt5_signal_bot, "sent_today", sent),
            patch.object(mt5_signal_bot, "calculate_slot_signal", return_value=_result()),
            patch.object(mt5_signal_bot, "_persist_live_result") as persist,
            patch.object(mt5_signal_bot, "send_xau_entry_ready_alert") as alert,
            patch.object(mt5_signal_bot, "_save_state") as save,
        ):
            emitted = mt5_signal_bot._process_live_slot(broker_dt, 7)

        self.assertFalse(emitted)
        persist.assert_not_called()
        alert.assert_not_called()
        self.assertEqual(sent, {(broker_dt.date(), 7)})
        save.assert_called_once()

    def test_ready_signal_at_publication_is_persisted_once(self) -> None:
        broker_dt = datetime(2026, 7, 14, 7, 0)
        sent = set()
        with (
            patch.object(mt5_signal_bot, "sent_today", sent),
            patch.object(mt5_signal_bot, "calculate_slot_signal", return_value=_result()),
            patch.object(mt5_signal_bot, "_persist_live_result") as persist,
            patch.object(mt5_signal_bot, "should_send_xau_entry_alert", return_value=True),
            patch.object(mt5_signal_bot, "send_xau_entry_ready_alert") as alert,
            patch.object(mt5_signal_bot, "_save_state") as save,
        ):
            emitted = mt5_signal_bot._process_live_slot(broker_dt, 7)

        self.assertTrue(emitted)
        persist.assert_called_once()
        alert.assert_called_once()
        self.assertEqual(sent, {(broker_dt.date(), 7)})
        save.assert_called_once()

    def test_partial_gbp_data_is_persisted_but_retried(self) -> None:
        broker_dt = datetime(2026, 7, 14, 7, 5)
        sent = set()
        result = _result()
        result["pair_dirs"]["GBPJPY"] = "WAIT"
        result["pair_entry_times"]["GBPJPY"] = None
        result["pair_signal_states"]["GBPJPY"] = "WAIT"
        result["pair_entry_states"]["GBPJPY"] = "WAIT"
        with (
            patch.object(mt5_signal_bot, "sent_today", sent),
            patch.object(mt5_signal_bot, "calculate_slot_signal", return_value=result),
            patch.object(mt5_signal_bot, "_persist_live_result") as persist,
            patch.object(mt5_signal_bot, "should_send_xau_entry_alert", return_value=False) as should_send,
            patch.object(mt5_signal_bot, "_save_state") as save,
        ):
            emitted = mt5_signal_bot._process_live_slot(broker_dt, 7)

        self.assertFalse(emitted)
        persist.assert_called_once()
        should_send.assert_not_called()
        save.assert_not_called()
        self.assertEqual(sent, set())

    def test_restart_marks_only_publications_already_passed(self) -> None:
        broker_dt = datetime(2026, 7, 14, 10, 0)
        sent = set()
        with patch.object(mt5_signal_bot, "sent_today", sent):
            mt5_signal_bot._mark_passed_slots_on_startup(broker_dt)
        self.assertEqual(sent, {(broker_dt.date(), 3), (broker_dt.date(), 7), (broker_dt.date(), 9)})

    def test_sent_guard_prevents_duplicate_calculation(self) -> None:
        broker_dt = datetime(2026, 7, 14, 7, 5)
        with (
            patch.object(mt5_signal_bot, "sent_today", {(broker_dt.date(), 7)}),
            patch.object(mt5_signal_bot, "calculate_slot_signal") as calculate,
        ):
            self.assertFalse(mt5_signal_bot._process_live_slot(broker_dt, 7))
        calculate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
