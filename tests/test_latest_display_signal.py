import unittest

from utils import ACTIVE_SIGNAL_LOGIC_VERSION, get_latest_display_signal


CURRENT_VERSION = ACTIVE_SIGNAL_LOGIC_VERSION


class LatestDisplaySignalTests(unittest.TestCase):
    def test_prefers_today_highest_hour(self):
        signals = [
            {"date": "2026-07-08", "hour": 16, "logic_version": CURRENT_VERSION, "pair_dirs": {"XAUUSD": "SELL"}},
            {"date": "2026-07-09", "hour": 7, "logic_version": CURRENT_VERSION, "pair_dirs": {"XAUUSD": "BUY"}},
            {"date": "2026-07-09", "hour": 9, "logic_version": CURRENT_VERSION, "pair_dirs": {"XAUUSD": "SELL"}},
            {"date": "2026-07-03", "hour": 16, "logic_version": CURRENT_VERSION, "pair_dirs": {"XAUUSD": "BUY"}},
        ]

        latest = get_latest_display_signal(signals, today="2026-07-09")

        self.assertEqual(latest["hour"], 9)
        self.assertEqual(latest["pair_dirs"], {"XAUUSD": "SELL"})

    def test_falls_back_to_latest_dated_row_when_no_today(self):
        signals = [
            {"date": "2026-07-03", "hour": 3, "logic_version": CURRENT_VERSION, "pair_dirs": {"XAUUSD": "BUY"}},
            {"date": "2026-07-07", "hour": 14, "logic_version": CURRENT_VERSION, "pair_dirs": {"XAUUSD": "SELL"}},
        ]

        latest = get_latest_display_signal(signals, today="2026-07-09")

        self.assertEqual(latest["date"], "2026-07-07")
        self.assertEqual(latest["hour"], 14)

    def test_can_disable_old_signal_fallback(self):
        signals = [
            {"date": "2026-07-10", "hour": 16, "logic_version": CURRENT_VERSION, "pair_dirs": {"XAUUSD": "BUY"}},
        ]

        latest = get_latest_display_signal(
            signals,
            today="2026-07-11",
            allow_fallback=False,
        )

        self.assertIsNone(latest)

    def test_legacy_deactivated_flag_does_not_hide_a_v87_signal(self):
        signal = {"date": "2026-07-30", "hour": 3, "deactivated": True,
                  "logic_version": CURRENT_VERSION, "pair_dirs": {"XAUUSD": "BUY"}}

        latest = get_latest_display_signal([signal], today="2026-07-30", allow_fallback=False)

        self.assertEqual(latest, signal)

    def test_thursday_h3_is_actionable_v65(self):
        """Since v65, Thursday H3 is actionable like any other weekday."""
        signal = {"date": "2026-07-30", "hour": 3,
                  "logic_version": CURRENT_VERSION, "pair_dirs": {"XAUUSD": "BUY"}}
        result = get_latest_display_signal([signal], today=signal["date"], allow_fallback=False)
        self.assertIsNotNone(result)
        self.assertEqual(result["hour"], 3)

    def test_ignores_removed_legacy_slots(self):
        signals = [
            {"date": "2026-07-30", "hour": 15, "logic_version": CURRENT_VERSION, "pair_dirs": {"XAUUSD": "BUY"}},
            {"date": "2026-07-30", "hour": 14, "logic_version": CURRENT_VERSION, "pair_dirs": {"XAUUSD": "SELL"}},
        ]

        latest = get_latest_display_signal(signals, today="2026-07-30")

        self.assertEqual(latest["hour"], 14)

    def test_ignores_records_before_the_h1_contract(self):
        signals = [
            {"date": "2026-07-30", "hour": 16, "logic_version": 48, "pair_dirs": {"XAUUSD": "SELL"}},
            {"date": "2026-07-30", "hour": 14, "logic_version": CURRENT_VERSION, "pair_dirs": {"XAUUSD": "BUY"}},
        ]

        latest = get_latest_display_signal(signals, today="2026-07-30")

        self.assertEqual(latest["hour"], 14)


if __name__ == "__main__":
    unittest.main()
