"""Test verification that auto-close remains removed across contracts and startup messages."""
import unittest
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mt5_signal_bot import build_startup_telegram_message, SIGNAL_LOGIC_VERSION


class TestAutoCloseRemoved(unittest.TestCase):
    """Verify Auto-Close features remain completely removed."""

    def test_startup_telegram_message_structure(self):
        msg = build_startup_telegram_message(datetime(2026, 7, 31, 5, 0, 0), True)
        self.assertIn(f"v{SIGNAL_LOGIC_VERSION}", msg)
        self.assertIn("Independent M30 Entry + H4 20:00 D", msg)

    def test_contract_rules_state_no_auto_close(self):
        import json
        contract_path = os.path.join(os.path.dirname(__file__), "..", "signal_rule_contract.json")
        with open(contract_path, "r", encoding="utf-8") as f:
            contract = json.load(f)
        vn_text = " ".join(contract["rules"]["VN"])
        en_text = " ".join(contract["rules"]["EN"])
        self.assertIn("Không có Auto-Close", vn_text)
        self.assertIn("No Auto-Close", en_text)


if __name__ == "__main__":
    unittest.main()
