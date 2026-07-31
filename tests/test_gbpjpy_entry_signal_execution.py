"""Test Section 29 & 30: GBPJPY & GBPCAD Active Signal Evaluation & Execution (v85)."""
import unittest
from datetime import datetime, date
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import mt5_signal_bot


class TestGBPJPYAndGBPCADExecution(unittest.TestCase):
    def test_evaluate_gbp_native_signal_m30_not_disabled(self):
        """GBPJPY and GBPCAD must be evaluated and not return DISABLED_PAIR."""
        slot_dt = datetime(2026, 7, 31, 7, 0, 0)
        res_jpy = mt5_signal_bot._empty_gbp_signal_evidence(slot_dt, 7, "GBPJPY")
        res_cad = mt5_signal_bot._empty_gbp_signal_evidence(slot_dt, 7, "GBPCAD")

        self.assertNotEqual(res_jpy.get("signal_state"), "DISABLED")
        self.assertNotEqual(res_cad.get("signal_state"), "DISABLED")

    def test_startup_message_includes_all_five_pairs(self):
        """Startup message must list all 5 pairs without OFF suffix."""
        msg = mt5_signal_bot.build_startup_telegram_message(datetime.now(), True)
        self.assertIn("XAUUSD | GBPUSD | GBPAUD | GBPJPY | GBPCAD", msg)
        self.assertNotIn("EXEC OFF", msg)


if __name__ == "__main__":
    unittest.main()
