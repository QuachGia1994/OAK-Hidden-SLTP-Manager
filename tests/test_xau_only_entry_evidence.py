import unittest
from pathlib import Path


class XauOnlyEvidenceTests(unittest.TestCase):
    def test_dashboard_source_exposes_only_xau(self):
        source = Path("dashboard/src/lib/signal-evidence.ts").read_text(encoding="utf-8")
        self.assertIn('const EVIDENCE_PAIRS = ["XAUUSD"]', source)
        self.assertNotIn('const EVIDENCE_PAIRS = ["XAUUSD", "GBPUSD"', source)


if __name__ == "__main__":
    unittest.main()
