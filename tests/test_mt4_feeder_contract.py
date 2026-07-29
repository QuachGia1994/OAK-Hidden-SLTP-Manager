"""Static regression contract for the v71 MQL4 comparison feeder."""

from pathlib import Path
import unittest


class Mt4FeederContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (Path(__file__).parents[1] / "MT4_Data_Feeder.mq4").read_text(
            encoding="utf-8"
        )

    def test_uses_active_slots_and_retries_to_latest_entry_deadline(self) -> None:
        self.assertIn("int logicalSlots[]    = {3, 7, 9, 12, 14, 16};", self.source)
        self.assertIn("int deadlineHours[]   = {4, 8, 10, 13, 15, 17};", self.source)
        self.assertIn("int deadlineMinutes[] = {25, 25, 25, 25, 25, 25};", self.source)
        self.assertIn("datetime lastAttemptMinutes[6];", self.source)
        self.assertIn("if(SendSlotData(index, serverTime)) completedDateKeys[index] = dateKey;", self.source)
        self.assertIn("return response >= 200 && response < 300;", self.source)

    def test_timer_and_tick_share_the_slot_processor(self) -> None:
        self.assertIn("EventSetTimer(1);", self.source)
        self.assertIn("EventKillTimer();", self.source)
        self.assertEqual(self.source.count("ProcessEligibleSlots();"), 2)

    def test_reads_all_five_symbols_independently(self) -> None:
        for symbol in ("XauUsd", "GbpUsd", "GbpAud", "GbpJpy", "GbpCad"):
            self.assertIn(f'input string {symbol}Symbol', self.source)
        self.assertIn("string signals[5];", self.source)
        self.assertIn("signals[pairIndex] = EvaluatePairSignal(", self.source)
        self.assertIn(
            'string fields[5] = {"xauusd", "gbpusd", "gbpaud", "gbpjpy", "gbpcad"};',
            self.source,
        )

    def test_stage_a_keeps_the_existing_m15_entry_planner(self) -> None:
        for offset in (30, 45, 60, 75, 15):
            self.assertIn(f"slotTime - {offset} * 60", self.source)
        self.assertIn("ClassifyThree(p1, p2, p3)", self.source)
        self.assertIn("GetResolvedDirection(GbpAudSymbol, PERIOD_M15, slotTime + 30 * 60)", self.source)
        self.assertIn('if(slot == 3) return followupSame ? "03:49" : "04:25";', self.source)

    def test_h3_uses_0400_base_then_0300_0200_previous_session(self) -> None:
        self.assertIn("sourceStart + 4 * 3600", self.source)
        self.assertIn("sourceStart + 3 * 3600", self.source)
        self.assertIn("sourceStart + 2 * 3600", self.source)
        self.assertIn("group = ClassifyThree(c1, c2, c3);", self.source)
        self.assertIn("return DeriveSignalBase(c1, group);", self.source)
        self.assertNotIn("15 * 3600", self.source)

    def test_thursday_h3_reuses_monday_bt_and_stops_on_sw(self) -> None:
        self.assertIn("if(TimeDayOfWeek(slotTime) == 4) reference = slotTime - 3 * 86400;", self.source)
        self.assertIn('if(TimeDayOfWeek(slotTime) == 4 && group == "SW") return "WAIT";', self.source)
        self.assertIn('bool terminalWait = thursdayH3 && groups[0] == "SW";', self.source)
        self.assertIn('json += "\\\"terminal_wait\\\":"', self.source)
        send_slot = self.source.index("bool SendSlotData")
        h3_evaluation = self.source.index("if(thursdayH3)", send_slot)
        entry_planner = self.source.index("entryTime = SelectEntryTime", send_slot)
        self.assertLess(h3_evaluation, entry_planner)

    def test_three_candle_classifier_covers_all_eight_patterns(self) -> None:
        expected = {
            ("TANG", "TANG", "TANG"): "SW",
            ("GIAM", "TANG", "TANG"): "SW",
            ("GIAM", "TANG", "GIAM"): "BT",
            ("GIAM", "GIAM", "TANG"): "BT",
            ("GIAM", "GIAM", "GIAM"): "SW",
            ("TANG", "GIAM", "GIAM"): "SW",
            ("TANG", "GIAM", "TANG"): "BT",
            ("TANG", "TANG", "GIAM"): "BT",
        }
        for directions, group in expected.items():
            condition = " && ".join(
                f'c{index} == "{direction}"'
                for index, direction in enumerate(directions, start=1)
            )
            self.assertIn(f'if({condition}) return "{group}";', self.source)

    def test_h7_plus_uses_four_h1_and_entry_selected_base(self) -> None:
        self.assertIn("datetime baseTime = entryTime == plus25 ? slotTime : slotTime - 3600;", self.source)
        self.assertIn("if(serverTime < baseTime + 3600) return \"WAIT\";", self.source)
        for offset in (3600, 7200, 10800):
            self.assertIn(f"baseTime - {offset}", self.source)
        self.assertIn("group = ClassifyFour(c1, c2, c3, c4);", self.source)
        self.assertIn("ApplyEntryRule(DeriveSignalBase(c1, group), entryTime, slot)", self.source)

    def test_entry_reversal_has_only_two_exact_exceptions(self) -> None:
        self.assertIn('entryTime == "15:25" || entryTime == "16:49"', self.source)
        self.assertIn("else if(entryTime == h11 || entryTime == h49) result = ReverseSignal(signalBase);", self.source)

    def test_doji_resolution_matches_python_contract(self) -> None:
        self.assertIn("MathAbs(closePrice - openPrice) / range < 0.02", self.source)
        self.assertIn("if(timeframe == PERIOD_M15)", self.source)
        self.assertIn('return previous == "TANG" ? "GIAM" : "TANG";', self.source)
        self.assertIn("return previous;", self.source)

    def test_legacy_raw_candle_payload_is_removed(self) -> None:
        for field in (
            "gbpusd_h1_1",
            "gbpusd_h1_2",
            "gbpaud_h1_1",
            "xau_m15_1",
            "pattern_hour",
        ):
            self.assertNotIn(field, self.source)
        for field in ("_signal", "_group", "entry_time", "terminal_wait"):
            self.assertIn(field, self.source)


if __name__ == "__main__":
    unittest.main()
