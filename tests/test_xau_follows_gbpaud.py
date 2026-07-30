"""XAU direction follows GBPAUD while XAU entry follows its own M30 timing."""

import unittest

import mt5_signal_bot


def _source(direction):
    return {"direction": direction, "signal_state": "READY" if direction != "WAIT" else "WAIT"}


def _timing(entry):
    return {"entry_time": entry, "entry_state": "READY" if entry else "WAIT", "layer1": {}, "layer2": {}}


class XauFollowsGbpaudTests(unittest.TestCase):
    def test_h3_h14_h16_reverse_final_gbpaud_signal(self) -> None:
        for hour in (3, 14, 16):
            with self.subTest(hour=hour):
                evidence = mt5_signal_bot.derive_xau_from_gbpaud(
                    hour, _source("BUY"), _timing(f"{hour:02d}:49")
                )
                self.assertEqual(evidence["direction"], "SELL")
                self.assertEqual(evidence["entry_time"], f"{hour:02d}:49")
                self.assertEqual(evidence["direction_relation_to_gbpaud"], "OPPOSITE")
                self.assertEqual(evidence["direction_rule"], "OPPOSITE_GBPAUD")

    def test_h7_h9_h12_keep_final_gbpaud_signal(self) -> None:
        for hour in (7, 9, 12):
            with self.subTest(hour=hour):
                evidence = mt5_signal_bot.derive_xau_from_gbpaud(
                    hour, _source("BUY"), _timing(f"{hour:02d}:49")
                )
                self.assertEqual(evidence["direction"], "BUY")
                self.assertEqual(evidence["direction_relation_to_gbpaud"], "SAME")
                self.assertEqual(evidence["direction_rule"], "SAME_AS_GBPAUD")

    def test_entry_does_not_come_from_gbpaud(self) -> None:
        source = {**_source("BUY"), "entry_time": "08:00"}
        evidence = mt5_signal_bot.derive_xau_from_gbpaud(7, source, _timing("07:49"))
        self.assertEqual(evidence["entry_time"], "07:49")

    def test_wait_has_no_direction_or_entry_fallback(self) -> None:
        evidence = mt5_signal_bot.derive_xau_from_gbpaud(7, _source("WAIT"), _timing("07:49"))
        self.assertEqual(evidence["direction"], "WAIT")
        self.assertIsNone(evidence["entry_time"])
        self.assertEqual(evidence["source_symbol"], "GBPAUD")

if __name__ == "__main__":
    unittest.main()
