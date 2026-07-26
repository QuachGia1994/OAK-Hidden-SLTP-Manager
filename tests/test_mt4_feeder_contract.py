"""Static contract checks for the MQL4 feeder schedule."""
from pathlib import Path
import unittest


class Mt4FeederContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (Path(__file__).parents[1] / "MT4_Data_Feeder.mq4").read_text(encoding="utf-8")

    def test_uses_only_active_logical_slots(self) -> None:
        self.assertIn("int logicalSlots[]  = {3, 4, 5, 6, 9, 12, 14, 16};", self.source)

    def test_suppresses_late_special_and_post_special_slots(self) -> None:
        self.assertIn("IsSpecialPair(serverTime) || IsPostSpecialMonday(serverTime)", self.source)
        self.assertIn("if(IsSuppressedSlot(slot, serverTime))", self.source)

    def test_marks_only_special_thursday_h3_as_deactivated(self) -> None:
        self.assertIn("deactivated = slot == 3 && TimeDayOfWeek(serverTime) == 4 && special", self.source)
        self.assertIn('json += "\\\"deactivated\\\":"', self.source)


if __name__ == "__main__":
    unittest.main()
