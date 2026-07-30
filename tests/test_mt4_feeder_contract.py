"""Static v72 contract for the MQL4 comparison feeder."""

from pathlib import Path
import unittest


class Mt4FeederContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (Path(__file__).parents[1] / "MT4_Data_Feeder.mq4").read_text(encoding="utf-8")

    def test_uses_v72_active_slots_and_latest_entry_deadlines(self) -> None:
        self.assertIn("#property version   \"2.12\"", self.source)
        self.assertIn("int logicalSlots[]    = {3, 7, 9, 12, 14, 16};", self.source)
        self.assertIn("int deadlineHours[]   = {4, 8, 10, 13, 15, 17};", self.source)
        self.assertIn("int deadlineMinutes[] = {49, 25, 25, 25, 25, 25};", self.source)
        self.assertIn("if(SendSlotData(index, serverTime)) completedDateKeys[index] = dateKey;", self.source)

    def test_reads_only_exact_symbol_m30_candles(self) -> None:
        self.assertIn("iBarShift(symbolName, PERIOD_M30, candleOpenTime, true)", self.source)
        self.assertIn("iTime(symbolName, PERIOD_M30, shift) != candleOpenTime", self.source)
        self.assertNotIn("PERIOD_H1", self.source)
        self.assertNotIn("PERIOD_M15", self.source)
        self.assertNotIn("PENDING", self.source)

    def test_layer_windows_are_exact(self) -> None:
        for offset in (30, 60, 90, 120, 150, 180):
            self.assertIn(f"slotTime - {offset} * 60", self.source)
        self.assertIn("if(slot == 3)", self.source)
        self.assertIn("layer1Group = ClassifyThree(", self.source)
        self.assertIn("layer2Group = ClassifyFour(", self.source)
        self.assertIn("GetM30Direction(XauUsdSymbol, slotTime - 30 * 60)", self.source)
        self.assertGreaterEqual(
            self.source.count("GetM30Direction(XauUsdSymbol, slotTime - 150 * 60)"),
            2,
        )

    def test_four_candle_classifier_keeps_ten_rules(self) -> None:
        for rule_number in range(1, 11):
            self.assertIn(f"ruleNumber = {rule_number};", self.source)
        self.assertIn('c4 == "GIAM") { ruleNumber = 2;', self.source)
        self.assertIn('c4 == "TANG") { ruleNumber = 7;', self.source)
        self.assertIn('ruleNumber = 10;', self.source)

    def test_entry_selection_uses_layer2_and_h3_0449(self) -> None:
        self.assertIn('lateEntry = slot == 3 ? "04:49"', self.source)
        self.assertIn('return layer2Group == "SW" ? earlyEntry : lateEntry;', self.source)
        self.assertNotIn("04:25", self.source)

    def test_each_gbp_pair_is_evaluated_independently(self) -> None:
        for symbol in ("GbpUsd", "GbpAud", "GbpJpy", "GbpCad"):
            self.assertIn(f"input string {symbol}Symbol", self.source)
        self.assertIn("for(int pairIndex = 1; pairIndex < 5; pairIndex++)", self.source)
        self.assertIn("EvaluateGbpSignal(symbols[pairIndex]", self.source)

    def test_xau_direction_follows_gbpaud_but_entry_uses_xau_layers(self) -> None:
        self.assertIn("entries[0] = xauEntry;", self.source)
        self.assertIn("(slot == 3 || slot == 14 || slot == 16)", self.source)
        self.assertIn("? ReverseSignal(signals[2]) : signals[2];", self.source)
        self.assertIn("string gbpEntry = NextFullHourEntry(xauEntry);", self.source)

    def test_payload_carries_pair_specific_entries_at_version_72(self) -> None:
        self.assertIn('json += "\\\"logic_version\\\":72,";', self.source)
        self.assertIn('"_entry\\\":\\\"" + entries[outputIndex]', self.source)
        self.assertNotIn('"entry_time"', self.source)
        self.assertNotIn("terminal_wait", self.source)

    def test_timer_and_tick_share_one_slot_processor(self) -> None:
        self.assertIn("EventSetTimer(1);", self.source)
        self.assertIn("EventKillTimer();", self.source)
        self.assertEqual(self.source.count("ProcessEligibleSlots();"), 2)


if __name__ == "__main__":
    unittest.main()
