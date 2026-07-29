"""Unit test suite for build_startup_telegram_message and compact Telegram rules format."""
from datetime import datetime
import unittest

import mt5_signal_bot


class StartupTelegramMessageTests(unittest.TestCase):
    def test_build_startup_telegram_message_content(self) -> None:
        """Verify startup message structure, slot listing, canonical rules, and length constraints."""
        broker_dt = datetime(2026, 7, 29, 13, 35)
        msg = mt5_signal_bot.build_startup_telegram_message(broker_dt, mt5_connected=True)

        self.assertIn("🤖 OAK SIGNAL BOT ONLINE · v63", msg)
        self.assertIn("MT5: ✅ OK | Broker: 13:35", msg)
        self.assertIn("Slots: H3 · H7 · H9 · H12 · H14 · H16", msg)
        self.assertIn("Pairs: GBPAUD / GBPUSD → XAUUSD", msg)
        self.assertIn("XAU: entry :11/:25 = cùng GBPAUD · :49 = đảo", msg)
        self.assertIn("H3: GBPUSD chờ H7 · GBPAUD là Stock-Direction", msg)
        self.assertIn("Safety: H4 nội bộ · thiếu dữ liệu → WAIT", msg)
        self.assertIn("Auto-close: XAU 17:59 · GBP 19:59 Broker", msg)

        # Exclusions: Must not contain legacy texts
        self.assertNotIn("H1 hôm qua", msg)
        self.assertNotIn("H6", msg)
        self.assertNotIn("DO NOT ENTER", msg)
        self.assertNotIn("KHÔNG VÀO LỆNH", msg)
        self.assertNotIn("weekday inversion", msg.lower())

        # Line count constraint: max ~8 lines
        lines = [l for l in msg.splitlines() if l.strip()]
        self.assertLessEqual(len(lines), 8)

    def test_build_startup_telegram_message_disconnected(self) -> None:
        """Verify disconnected MT5 status rendering in startup message."""
        msg = mt5_signal_bot.build_startup_telegram_message(None, mt5_connected=False)
        self.assertIn("MT5: ⚠️ DISCONNECTED | Broker: --:--", msg)


if __name__ == "__main__":
    unittest.main()
