"""Static contract checks for the MQL4 feeder schedule."""
from pathlib import Path
import unittest


class Mt4FeederContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (Path(__file__).parents[1] / "MT4_Data_Feeder.mq4").read_text(encoding="utf-8")

    def test_uses_only_active_logical_slots(self) -> None:
        self.assertIn("int logicalSlots[]  = {3, 4, 6, 9, 12, 14, 16};", self.source)

    def test_h9_and_h14_keep_normal_schedules_without_special_suppression(self) -> None:
        self.assertIn("int signalHours[]   = {3, 4, 6, 9, 12, 14, 16};", self.source)
        self.assertIn("int signalMinutes[] = {0, 0, 0, 0, 0, 0, 0};", self.source)
        self.assertNotIn("IsSuppressedSlot(slot, serverTime)", self.source)

    def test_retries_every_slot_once_per_minute_through_its_max_deadline(self) -> None:
        self.assertIn("int deadlineHours[]   = {4, 5, 7, 10, 13, 15, 17};", self.source)
        self.assertIn("int deadlineMinutes[] = {49, 25, 25, 25, 25, 25, 25};", self.source)
        self.assertIn("datetime lastAttemptMinutes[7];", self.source)
        self.assertIn("int completedDateKeys[7];", self.source)
        self.assertIn("for(int index = 0; index < ArraySize(logicalSlots); index++)", self.source)
        self.assertIn("lastAttemptMinutes[index] = currentMinute;", self.source)
        self.assertIn("if(SendSlotData(index, serverTime))", self.source)
        self.assertIn("completedDateKeys[index] = dateKey;", self.source)
        self.assertIn("return response >= 200 && response < 300;", self.source)
        self.assertIn(
            'StringFormat("%02d:%02d", signalHours[index], signalMinutes[index])',
            self.source,
        )

    def test_timer_and_tick_share_the_slot_window_processor(self) -> None:
        self.assertIn("EventSetTimer(1);", self.source)
        self.assertIn("EventKillTimer();", self.source)
        self.assertEqual(self.source.count("ProcessEligibleSlots();"), 2)

    def test_marks_dependency_slots_and_every_thursday_h3_as_deactivated(self) -> None:
        self.assertIn(
            "deactivated = slot == 4 || (slot == 3 && TimeDayOfWeek(serverTime) == 4)",
            self.source,
        )
        self.assertIn('json += "\\\"deactivated\\\":"', self.source)

    def test_uses_yesterday_h1_pairs_and_today_xau_m15_context(self) -> None:
        self.assertIn('input string GbpUsdSymbol = "GBPUSD";', self.source)
        self.assertIn('input string GbpAudSymbol = "GBPAUD";', self.source)
        self.assertIn('input string XauUsdSymbol = "XAUUSD";', self.source)
        self.assertIn(
            "datetime yesterdayStart = StrToTime(TimeToString(todayStart - 12 * 3600, TIME_DATE));",
            self.source,
        )
        self.assertIn("datetime yesterdaySlot = yesterdayStart + slot * 3600;", self.source)
        self.assertIn("yesterdaySlot - 3600", self.source)
        self.assertIn("yesterdaySlot - 7200", self.source)
        self.assertIn("todaySlot - 30 * 60", self.source)
        self.assertIn("todaySlot - 45 * 60", self.source)
        self.assertIn("todaySlot - 60 * 60", self.source)
        self.assertNotIn("todaySlot - 15 * 60", self.source)

    def test_reads_xau_m15_only_for_valid_opposite_h1_derivations(self) -> None:
        guard = (
            'if(gbpUsdSignal != "WAIT" && gbpAudSignal != "WAIT" '
            '&& gbpUsdSignal != gbpAudSignal)'
        )
        self.assertIn(guard, self.source)
        guard_position = self.source.index(guard)
        first_m15_read = self.source.index(
            "GetResolvedDirection(XauUsdSymbol, PERIOD_M15", guard_position
        )
        closing_brace = self.source.index("\n   }", first_m15_read)
        self.assertLess(guard_position, first_m15_read)
        self.assertLess(first_m15_read, closing_brace)

    def test_removes_the_old_m5_m30_payload(self) -> None:
        for legacy_field in ('"m35"', '"m40"', '"m30"', '"pattern_hour"'):
            self.assertNotIn(legacy_field, self.source)
        for field in (
            "gbpusd_h1_1",
            "gbpusd_h1_2",
            "gbpaud_h1_1",
            "gbpaud_h1_2",
            "xau_m15_1",
            "xau_m15_2",
            "xau_m15_3",
        ):
            self.assertIn(field, self.source)

    def test_doji_body_threshold_matches_python_two_percent_contract(self) -> None:
        self.assertIn(
            "MathAbs(closePrice - openPrice) / range < 0.02",
            self.source,
        )
        self.assertNotIn(
            "MathAbs(closePrice - openPrice) / range < 0.05",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
