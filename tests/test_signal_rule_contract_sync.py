"""Unit test suite for canonical signal rule contract synchronization."""
import json
import os
import subprocess
import sys
import unittest

import mt5_signal_bot
from utils import ACTIVE_SIGNAL_LOGIC_VERSION


class SignalRuleContractSyncTests(unittest.TestCase):
    def test_canonical_contract_file_exists_and_valid(self) -> None:
        """Verify signal_rule_contract.json exists and contains correct version and slots."""
        contract_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "signal_rule_contract.json",
        )
        self.assertTrue(os.path.exists(contract_path))
        with open(contract_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data.get("logic_version"), 63)
        self.assertEqual(data.get("public_slots"), [3, 7, 9, 12, 14, 16])
        self.assertEqual(data.get("internal_slots"), [4])
        self.assertEqual(mt5_signal_bot.SIGNAL_LOGIC_VERSION, 63)
        self.assertEqual(ACTIVE_SIGNAL_LOGIC_VERSION, 63)

    def test_generator_check_passes(self) -> None:
        """Verify scripts/generate_dashboard_signal_rules.py --check returns exit code 0."""
        gen_script = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts",
            "generate_dashboard_signal_rules.py",
        )
        res = subprocess.run(
            [sys.executable, gen_script, "--check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, msg=f"Generator check failed: {res.stderr}")
        self.assertIn("OK: Generated signal rules are up to date", res.stdout)


if __name__ == "__main__":
    unittest.main()
