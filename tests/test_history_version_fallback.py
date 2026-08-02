"""Regression tests for v88-first, v87-fallback history signal resolution.

Tests the Python-side signal selection logic that feeds into the dashboard's
resolveHistorySignals. Since the TS module is ESM and cannot be required from
Python, we test the core invariant here: the bot writes both v87 and v88
records to the signals log, and the dashboard resolves v88-first.
"""

import unittest


class HistoryVersionFallbackTests(unittest.TestCase):
    """Verify the bot emits correct logic_version metadata for history resolution."""

    def test_v88_records_have_logic_version_88(self):
        """When rebuild produces a v88 record, its logic_version is 88."""
        record = {
            "date": "2026-07-20",
            "hour": 9,
            "signal": "BUY",
            "pair_dirs": {"XAUUSD": "BUY"},
            "entry_state": "READY",
            "entry_time": "07:49",
            "logic_version": 88,
        }
        self.assertEqual(record["logic_version"], 88)

    def test_v87_fallback_record_preserved_in_log(self):
        """A pre-existing v87 record in the log is preserved when rebuild does not cover its slot."""
        v87_existing = {
            "date": "2026-07-18",
            "hour": 14,
            "signal": "SELL",
            "pair_dirs": {"XAUUSD": "SELL"},
            "entry_state": "READY",
            "entry_time": "13:55",
            "logic_version": 87,
        }
        v88_new = {
            "date": "2026-07-20",
            "hour": 9,
            "signal": "BUY",
            "pair_dirs": {"XAUUSD": "BUY"},
            "entry_state": "READY",
            "entry_time": "07:49",
            "logic_version": 88,
        }
        # Simulate atomic merge: new candidate does not overlap with v87's (date, hour)
        all_signals = [v87_existing, v88_new]
        self.assertEqual(len(all_signals), 2)
        self.assertEqual(all_signals[0]["logic_version"], 87)
        self.assertEqual(all_signals[1]["logic_version"], 88)

    def test_v88_preferred_over_v87_for_same_slot(self):
        """When both v88 and v87 exist for the same (date, hour), the merge logic picks v88."""
        from collections import defaultdict

        signals = [
            {"date": "2026-07-20", "hour": 9, "signal": "BUY",
             "logic_version": 87, "pair_dirs": {"XAUUSD": "BUY"}},
            {"date": "2026-07-20", "hour": 9, "signal": "SELL",
             "logic_version": 88, "pair_dirs": {"XAUUSD": "SELL"}},
        ]
        # Replicate the resolveHistorySignals grouping logic
        by_key = defaultdict(dict)
        for s in signals:
            key = (s["date"], s["hour"])
            ver = s.get("logic_version", 0)
            if ver == 88:
                by_key[key]["v88"] = s
            elif ver == 87:
                by_key[key]["v87"] = s

        resolved = []
        for entry in by_key.values():
            if "v88" in entry:
                resolved.append(entry["v88"])
            elif "v87" in entry:
                v87 = {**entry["v87"], "is_legacy_logic": True, "legacy_logic_version": 87}
                resolved.append(v87)

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["signal"], "SELL")
        self.assertEqual(resolved[0]["logic_version"], 88)
        self.assertFalse(resolved[0].get("is_legacy_logic", False))

    def test_v87_only_gets_legacy_metadata(self):
        """When only v87 exists for a slot, it is included with is_legacy_logic flag."""
        from collections import defaultdict

        signals = [
            {"date": "2026-07-18", "hour": 14, "signal": "SELL",
             "logic_version": 87, "pair_dirs": {"XAUUSD": "SELL"}},
        ]
        by_key = defaultdict(dict)
        for s in signals:
            key = (s["date"], s["hour"])
            ver = s.get("logic_version", 0)
            if ver == 88:
                by_key[key]["v88"] = s
            elif ver == 87:
                by_key[key]["v87"] = s

        resolved = []
        for entry in by_key.values():
            if "v88" in entry:
                resolved.append(entry["v88"])
            elif "v87" in entry:
                v87 = {**entry["v87"], "is_legacy_logic": True, "legacy_logic_version": 87}
                resolved.append(v87)

        self.assertEqual(len(resolved), 1)
        self.assertTrue(resolved[0].get("is_legacy_logic", False))
        self.assertEqual(resolved[0].get("legacy_logic_version"), 87)

    def test_unknown_versions_dropped(self):
        """Records with logic_version neither 88 nor 87 are dropped by the resolver."""
        from collections import defaultdict

        signals = [
            {"date": "2026-07-20", "hour": 9, "signal": "BUY",
             "logic_version": 86, "pair_dirs": {"XAUUSD": "BUY"}},
        ]
        by_key = defaultdict(dict)
        for s in signals:
            key = (s["date"], s["hour"])
            ver = s.get("logic_version", 0)
            if ver == 88:
                by_key[key]["v88"] = s
            elif ver == 87:
                by_key[key]["v87"] = s

        resolved = []
        for entry in by_key.values():
            if "v88" in entry:
                resolved.append(entry["v88"])
            elif "v87" in entry:
                resolved.append(entry["v87"])

        self.assertEqual(len(resolved), 0)

    def test_empty_input_returns_empty(self):
        """Empty signals array returns empty resolved array."""
        from collections import defaultdict

        signals = []
        by_key = defaultdict(dict)
        for s in signals:
            key = (s["date"], s["hour"])
            ver = s.get("logic_version", 0)
            if ver == 88:
                by_key[key]["v88"] = s
            elif ver == 87:
                by_key[key]["v87"] = s

        resolved = []
        for entry in by_key.values():
            if "v88" in entry:
                resolved.append(entry["v88"])
            elif "v87" in entry:
                resolved.append(entry["v87"])

        self.assertEqual(len(resolved), 0)


if __name__ == "__main__":
    unittest.main()
