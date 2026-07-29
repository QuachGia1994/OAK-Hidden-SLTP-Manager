# -*- coding: utf-8 -*-
"""Tests for pending follow-up recovery after restart.

Root cause: startup rebuild wrote PENDING_FOLLOWUP record with entry_time=N/A,
then _mark_passed_slots_on_startup marked H3 as sent_today, preventing
the live loop from ever resolving the follow-up.
"""
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

import mt5_signal_bot


class H3PendingFollowupTests(unittest.TestCase):
    """Verify H3 pending follow-up is properly handled after restart."""

    def test_h3_opposite_needs_followup(self):
        """H3 with OPPOSITE initial relation needs follow-up at 03:45."""
        slot_dt = datetime(2026, 7, 29, 3, 0)
        plan = mt5_signal_bot.build_xau_entry_plan(
            slot_dt, 3,
            xauusd_signal="BUY",
            gbpaud_offset15_direction="GIAM",  # OPPOSITE
            followup_gbpaud_direction=None,     # not yet available
        )
        self.assertEqual(plan["entry_state"], "PENDING_FOLLOWUP")
        self.assertIsNone(plan["entry_time"])
        self.assertEqual(plan["entry_candidate"], "03:49")

    def test_h3_same_ready_immediately(self):
        """H3 with SAME initial relation is READY at 03:11."""
        slot_dt = datetime(2026, 7, 29, 3, 0)
        plan = mt5_signal_bot.build_xau_entry_plan(
            slot_dt, 3,
            xauusd_signal="BUY",
            gbpaud_offset15_direction="TANG",  # SAME
        )
        self.assertEqual(plan["entry_state"], "READY")
        self.assertEqual(plan["entry_time"], "03:11")

    def test_h3_opposite_followup_same_gives_0349(self):
        """H3 OPPOSITE + follow-up SAME → 03:49."""
        slot_dt = datetime(2026, 7, 29, 3, 0)
        plan = mt5_signal_bot.build_xau_entry_plan(
            slot_dt, 3,
            xauusd_signal="BUY",
            gbpaud_offset15_direction="GIAM",  # OPPOSITE
            followup_gbpaud_direction="TANG",   # SAME followup
        )
        self.assertEqual(plan["entry_state"], "READY")
        self.assertEqual(plan["entry_time"], "03:49")

    def test_h3_opposite_followup_opposite_gives_0449(self):
        """H3 OPPOSITE + follow-up OPPOSITE → 04:49."""
        slot_dt = datetime(2026, 7, 29, 3, 0)
        plan = mt5_signal_bot.build_xau_entry_plan(
            slot_dt, 3,
            xauusd_signal="BUY",
            gbpaud_offset15_direction="GIAM",  # OPPOSITE
            followup_gbpaud_direction="GIAM",   # OPPOSITE followup
        )
        self.assertEqual(plan["entry_state"], "READY")
        self.assertEqual(plan["entry_time"], "04:49")

    def test_can_resolve_h3_followup_after_0345(self):
        """After 03:45, H3 follow-up should be resolvable."""
        slot_dt = datetime(2026, 7, 29, 3, 0)
        as_of = datetime(2026, 7, 29, 3, 45)
        self.assertTrue(
            mt5_signal_bot.can_resolve_entry_followup(slot_dt, as_of_dt=as_of)
        )

    def test_cannot_resolve_h3_followup_before_0345(self):
        """Before 03:45, H3 follow-up should not be resolvable."""
        slot_dt = datetime(2026, 7, 29, 3, 0)
        as_of = datetime(2026, 7, 29, 3, 20)
        self.assertFalse(
            mt5_signal_bot.can_resolve_entry_followup(slot_dt, as_of_dt=as_of)
        )


class StartupMarkPendingTests(unittest.TestCase):
    """Verify _mark_passed_slots_on_startup does NOT mark PENDING_FOLLOWUP slots."""

    def test_pending_followup_not_marked_sent(self):
        """A slot with PENDING_FOLLOWUP should NOT be added to sent_today."""
        mt5_signal_bot.sent_today = set()
        broker_dt = datetime(2026, 7, 29, 3, 20)

        mock_result = {
            "signal": "BUY",
            "entry_state": "PENDING_FOLLOWUP",
            "entry_time": None,
        }
        with patch.object(mt5_signal_bot, "evaluate_all_pairs_for_slot", return_value=mock_result), \
             patch.object(mt5_signal_bot, "calculate_slot_signal", return_value=mock_result), \
             patch.object(mt5_signal_bot, "get_target_hours", return_value=[3]), \
             patch.object(mt5_signal_bot, "get_signal_datetime_for_slot",
                          return_value=datetime(2026, 7, 29, 3, 0)):
            mt5_signal_bot._mark_passed_slots_on_startup(broker_dt)

        key = (broker_dt.date(), 3)
        self.assertNotIn(key, mt5_signal_bot.sent_today)

    def test_ready_slot_marked_sent(self):
        """A slot with READY entry should be marked sent."""
        mt5_signal_bot.sent_today = set()
        broker_dt = datetime(2026, 7, 29, 4, 0)

        mock_result = {
            "signal": "BUY",
            "entry_state": "READY",
            "entry_time": "03:11",
        }
        with patch.object(mt5_signal_bot, "evaluate_all_pairs_for_slot", return_value=mock_result), \
             patch.object(mt5_signal_bot, "calculate_slot_signal", return_value=mock_result), \
             patch.object(mt5_signal_bot, "get_target_hours", return_value=[3]), \
             patch.object(mt5_signal_bot, "get_signal_datetime_for_slot",
                          return_value=datetime(2026, 7, 29, 3, 0)):
            mt5_signal_bot._mark_passed_slots_on_startup(broker_dt)

        key = (broker_dt.date(), 3)
        self.assertIn(key, mt5_signal_bot.sent_today)

    def test_wait_slot_marked_sent(self):
        """A slot with WAIT should be marked sent (no action needed)."""
        mt5_signal_bot.sent_today = set()
        broker_dt = datetime(2026, 7, 29, 4, 0)

        mock_result = {
            "signal": "WAIT",
            "entry_state": "WAIT",
            "entry_time": None,
        }
        with patch.object(mt5_signal_bot, "evaluate_all_pairs_for_slot", return_value=mock_result), \
             patch.object(mt5_signal_bot, "calculate_slot_signal", return_value=mock_result), \
             patch.object(mt5_signal_bot, "get_target_hours", return_value=[3]), \
             patch.object(mt5_signal_bot, "get_signal_datetime_for_slot",
                          return_value=datetime(2026, 7, 29, 3, 0)):
            mt5_signal_bot._mark_passed_slots_on_startup(broker_dt)

        key = (broker_dt.date(), 3)
        self.assertIn(key, mt5_signal_bot.sent_today)

    def test_future_slot_not_marked(self):
        """A slot whose signal time hasn't arrived yet should NOT be marked."""
        mt5_signal_bot.sent_today = set()
        broker_dt = datetime(2026, 7, 29, 2, 30)

        with patch.object(mt5_signal_bot, "get_target_hours", return_value=[3]), \
             patch.object(mt5_signal_bot, "get_signal_datetime_for_slot",
                          return_value=datetime(2026, 7, 29, 3, 0)):
            mt5_signal_bot._mark_passed_slots_on_startup(broker_dt)

        key = (broker_dt.date(), 3)
        self.assertNotIn(key, mt5_signal_bot.sent_today)


class RestartFollowupRecoveryTests(unittest.TestCase):
    """Verify that restart after H:45 resolves pending follow-ups."""

    def test_restart_after_0345_resolves_h3(self):
        """Restart at 04:00 should resolve H3 that was pending at 03:00."""
        slot_dt = datetime(2026, 7, 29, 3, 0)
        as_of = datetime(2026, 7, 29, 4, 0)

        # can_resolve_entry_followup should return True
        self.assertTrue(
            mt5_signal_bot.can_resolve_entry_followup(slot_dt, as_of_dt=as_of)
        )

    def test_historical_complete_resolves_h3(self):
        """Past-date rebuild should always resolve H3 follow-up."""
        slot_dt = datetime(2026, 7, 28, 3, 0)

        self.assertTrue(
            mt5_signal_bot.can_resolve_entry_followup(
                slot_dt, historical_complete=True
            )
        )


class EntryTimeNotNATests(unittest.TestCase):
    """Verify entry_time is never written as N/A."""

    def test_rebuild_slot_signal_writes_none_not_na(self):
        """rebuild_slot_signal should write None for pending entry, not N/A."""
        broker_dt = datetime(2026, 7, 29, 3, 0)
        mock_result = {
            "signal": "BUY",
            "entry_state": "PENDING_FOLLOWUP",
            "entry_time": None,
            "pair_dirs": {"XAUUSD": "BUY", "GBPUSD": "SELL", "GBPAUD": "BUY"},
            "source_date": "2026-07-29",
        }

        logged = {}
        def capture_log(h, dt, sig, entry_time, pair_dirs, note, **kwargs):
            logged["entry_time"] = entry_time

        with patch.object(mt5_signal_bot, "evaluate_all_pairs_for_slot", return_value=mock_result), \
             patch.object(mt5_signal_bot, "log_signal", side_effect=capture_log), \
             patch.object(mt5_signal_bot, "is_deactivated_signal_slot", return_value=False), \
             patch.object(mt5_signal_bot, "get_hour_note", return_value=""):
            mt5_signal_bot.rebuild_slot_signal(broker_dt, 3)

        self.assertIsNone(logged["entry_time"])


if __name__ == "__main__":
    unittest.main()
