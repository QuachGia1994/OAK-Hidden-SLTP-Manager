import unittest
from datetime import datetime
import mt5_signal_bot as bot


class SignalTelegramTests(unittest.TestCase):
    def _record(self, entry="07:49"):
        return {
            "logic_version": 87, "source_date": "2026-08-01", "hour": 7,
            "signal": "BUY", "signal_state": "READY", "entry_state": "READY",
            "record_revision": 2, "entry_time": entry,
            "pair_dirs": {pair: "BUY" for pair in bot.DISPLAY_SIGNAL_PAIRS},
        }

    def test_message_has_signal_only(self):
        message = bot.build_signal_telegram_message(self._record(), datetime(2026, 8, 1, 7, 0))
        self.assertIn("SIGNAL H7", message)
        self.assertNotIn("Entry", message)
        self.assertNotIn("07:49", message)

    def test_dedup_ignores_entry_change(self):
        bot.signal_alerts_sent.clear()
        record = self._record()
        bot.signal_alerts_sent.add(bot.build_signal_alert_fingerprint(record))
        record["entry_time"] = "08:25"
        self.assertFalse(bot.should_send_signal_alert(record, bot.signal_alerts_sent))


if __name__ == "__main__":
    unittest.main()
