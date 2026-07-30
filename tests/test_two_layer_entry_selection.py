"""Canonical layer-one candidates and layer-two selection table."""

import unittest

from domain.signal_rules import deferred_gbp_entry_time, select_two_layer_entry


class TwoLayerEntrySelectionTests(unittest.TestCase):
    def test_h3_decision_table(self) -> None:
        expected = {
            ("SW", "SW"): "03:49",
            ("SW", "BT"): "04:49",
            ("BT", "SW"): "03:11",
            ("BT", "BT"): "03:49",
        }
        self._assert_table(3, expected)

    def test_regular_slot_decision_tables(self) -> None:
        for hour in (7, 9, 12, 14, 16):
            expected = {
                ("SW", "SW"): f"{hour:02d}:49",
                ("SW", "BT"): f"{hour + 1:02d}:25",
                ("BT", "SW"): f"{hour:02d}:11",
                ("BT", "BT"): f"{hour:02d}:49",
            }
            with self.subTest(hour=hour):
                self._assert_table(hour, expected)

    def _assert_table(self, hour: int, expected: dict[tuple[str, str], str]) -> None:
        for (layer1, layer2), entry_time in expected.items():
            result = select_two_layer_entry(hour, layer1, layer2)
            self.assertEqual(result["state"], "READY")
            self.assertEqual(result["entry_time"], entry_time)
            self.assertEqual(result["entry_selection"], "EARLY" if layer2 == "SW" else "LATE")

    def test_unresolved_group_fails_closed(self) -> None:
        self.assertEqual(select_two_layer_entry(7, None, "BT")["state"], "WAIT")
        self.assertEqual(select_two_layer_entry(7, "SW", None)["state"], "WAIT")

    def test_gbp_entry_is_the_next_whole_hour_after_xau(self) -> None:
        expected = {
            "03:11": "04:00",
            "03:49": "04:00",
            "04:25": "05:00",
            "04:49": "05:00",
            "16:49": "17:00",
            "17:25": "18:00",
        }
        for xau_entry, gbp_entry in expected.items():
            with self.subTest(xau_entry=xau_entry):
                self.assertEqual(deferred_gbp_entry_time(xau_entry), gbp_entry)


if __name__ == "__main__":
    unittest.main()
