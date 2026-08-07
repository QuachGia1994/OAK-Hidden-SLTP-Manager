# -*- coding: utf-8 -*-
"""Tests for the read-only signal history + rule contract surface."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from oak_core.ipc.server import IpcServer  # noqa: E402
from oak_core.supervisor import SupervisorApp, history  # noqa: E402

#: Markers that must never appear in a response sent to React.
FORBIDDEN_MARKERS = ("tele_token", "password", "secret", ".exe", "account_uid", "pair_evidence")

RECORD_TEMPLATE = {
    "signal": "BUY",
    "signal_time": "07:00",
    "entry_time": "07:11",
    "entry_state": "READY",
    "signal_state": "READY",
    "signal_at_utc": "2026-08-03T04:00:00+00:00",
    "broker_utc_offset": 3,
    "broker_clock_verified": True,
    "logic_version": 88,
    "failure_reason": None,
    "pair_dirs": {"XAUUSD": "BUY", "GBPUSD": "BUY"},
    "pair_labels": {"XAUUSD": "REFERENCE"},
    "pair_entry_states": {"XAUUSD": "READY"},
}


def _record(date: str, hour: int, **overrides) -> dict:
    record = dict(RECORD_TEMPLATE, date=date, hour=hour)
    record.update(overrides)
    return record


class _DataRootCase(unittest.TestCase):
    """Shared temp data root; the modules never read a caller-supplied path."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(prefix="oak-history-")
        self.root = Path(self.tmpdir.name)
        history._archive_cache = None

    def tearDown(self):
        history._archive_cache = None
        self.tmpdir.cleanup()

    def write(self, name: str, payload) -> None:
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        (self.root / name).write_text(text, encoding="utf-8")

    @contextmanager
    def data_root(self):
        with patch("oak_core.supervisor.history._data_root", return_value=self.root), \
             patch("oak_core.supervisor.profiles._data_root", return_value=self.root):
            yield


class TestSignalHistory(_DataRootCase):
    def test_records_are_sanitized_and_newest_first(self):
        self.write("signals_log.json", [
            _record("2026-08-01", 7),
            _record("2026-08-03", 3, pair_evidence={"XAUUSD": {"secret": "x"}}, entry_prices={"XAUUSD": 4000}),
            _record("2026-08-03", 16, signal="SELL"),
            _record("2026-08-02", 12),
        ])
        with self.data_root():
            result = history.signal_history()

        self.assertEqual(result["source"], "local_signal_log")
        self.assertEqual(result["count"], 4)
        self.assertEqual(
            [(item["date"], item["hour"]) for item in result["records"]],
            [("2026-08-03", 16), ("2026-08-03", 3), ("2026-08-02", 12), ("2026-08-01", 7)],
        )
        newest = result["records"][0]
        self.assertEqual(newest["signal"], "SELL")
        self.assertEqual(newest["pair_dirs"], {"XAUUSD": "BUY", "GBPUSD": "BUY"})
        self.assertNotIn("pair_evidence", result["records"][1])
        self.assertNotIn("entry_prices", result["records"][1])
        blob = json.dumps(result, ensure_ascii=False)
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, blob)

    def test_limit_is_bounded_and_validated(self):
        self.write("signals_log.json", [_record("2026-08-03", hour) for hour in range(40)])
        with self.data_root():
            self.assertEqual(history.signal_history(limit=5)["count"], 5)
            self.assertEqual(history.signal_history(limit=0)["count"], 1)
            self.assertEqual(history.signal_history(limit=-10)["count"], 1)
            self.assertEqual(history.signal_history(limit="oops")["count"], 40)
            self.assertEqual(history.signal_history(limit=10**6)["count"], 40)

    def test_never_returns_more_than_max_records(self):
        self.write("signals_log.json", [
            _record("2026-08-03", index % 24) for index in range(history.MAX_RECORDS + 25)
        ])
        with self.data_root():
            result = history.signal_history(limit=history.MAX_RECORDS + 25)
        self.assertEqual(result["count"], history.MAX_RECORDS)

    def test_missing_and_malformed_files_degrade_to_empty(self):
        with self.data_root():
            missing = history.signal_history()
            self.write("signals_log.json", "{not json")
            broken = history.signal_history()
            self.write("signals_log.json", {"date": "2026-08-03"})
            wrong_shape = history.signal_history()
            self.write("signals_log.json", ["nope", 5, None, _record("2026-08-03", 9)])
            mixed = history.signal_history()

        self.assertEqual(missing["records"], [])
        self.assertEqual(broken["records"], [])
        self.assertEqual(wrong_shape["records"], [])
        self.assertEqual(mixed["count"], 1)
        self.assertEqual(mixed["records"][0]["hour"], 9)

    def test_corrupt_field_types_are_dropped_not_echoed(self):
        self.write("signals_log.json", [
            _record("2026-08-03", 9, signal={"nested": "object"}, pair_dirs=["XAUUSD"], failure_reason="x" * 900),
        ])
        with self.data_root():
            record = history.signal_history()["records"][0]
        self.assertIsNone(record["signal"])
        self.assertEqual(record["pair_dirs"], {})
        self.assertLessEqual(len(record["failure_reason"]), 240)


class TestTodayRules(_DataRootCase):
    CONTRACT = {
        "logic_version": 88,
        "public_slots": [3, 7, 9, 12, 14, 16],
        "internal_slots": [],
        "rules": {"VN": ["Quy tắc VN"], "EN": ["Rule EN"]},
        "startup_summary": "v88 summary",
    }

    def test_locale_selection_and_public_fields(self):
        self.write("signal_rule_contract.json", self.CONTRACT)
        self.write("bot_state.json", {
            "date": "2026-08-03",
            "broker_time": "2026-08-03T20:45:02",
            "broker_utc_offset": 3,
            "tele_token": "123:secret",
        })
        with self.data_root():
            vn = history.today_rules()
            en = history.today_rules("en")
            fallback = history.today_rules("de")

        self.assertEqual(vn["rules"], ["Quy tắc VN"])
        self.assertEqual(en["rules"], ["Rule EN"])
        self.assertEqual(fallback["locale"], "VN")
        self.assertTrue(vn["available"])
        self.assertEqual(vn["source"], "signal_rule_contract")
        self.assertEqual(vn["logic_version"], 88)
        self.assertEqual(vn["public_slots"], [3, 7, 9, 12, 14, 16])
        self.assertEqual(vn["startup_summary"], "v88 summary")
        self.assertIsNone(vn["reason"])
        self.assertNotIn("internal_slots", vn)
        blob = json.dumps(vn, ensure_ascii=False)
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, blob)

    def test_broker_metadata_is_reported_as_verified_only_when_stamped(self):
        self.write("signal_rule_contract.json", self.CONTRACT)
        self.write("bot_state.json", {
            "date": "2026-08-03",
            "broker_time": "2026-08-03T20:45:02",
            "broker_utc_offset": 3,
        })
        with self.data_root():
            trusted = history.today_rules()
            self.write("bot_state.json", {"date": "2026-08-03", "broker_time": "", "broker_utc_offset": None})
            untrusted = history.today_rules()

        self.assertTrue(trusted["broker_clock_verified"])
        self.assertEqual(trusted["broker_date"], "2026-08-03")
        self.assertEqual(trusted["broker_time"], "20:45:02")
        self.assertEqual(trusted["broker_utc_offset"], 3)
        self.assertFalse(untrusted["broker_clock_verified"])
        self.assertIsNone(untrusted["broker_time"])
        self.assertIsNone(untrusted["broker_utc_offset"])
        self.assertEqual(untrusted["broker_date"], "2026-08-03")

    def test_missing_broker_state_never_fabricates_a_broker_day(self):
        self.write("signal_rule_contract.json", self.CONTRACT)
        with self.data_root():
            result = history.today_rules()
        self.assertFalse(result["broker_clock_verified"])
        self.assertIsNone(result["broker_date"])
        self.assertIsNone(result["broker_time"])
        self.assertTrue(result["available"])

    def test_missing_contract_reports_unavailable_without_inventing_rules(self):
        repo_contract = self.root / "absent" / "signal_rule_contract.json"
        with patch("oak_core.supervisor.history._data_root", return_value=self.root), \
             patch("oak_core.supervisor.history._REPO_ROOT", repo_contract.parent):
            missing = history.today_rules()
            self.write("signal_rule_contract.json", "{broken")
            broken = history.today_rules()

        for result in (missing, broken):
            self.assertFalse(result["available"])
            self.assertEqual(result["reason"], "rule_contract_unavailable")
            self.assertEqual(result["rules"], [])
            self.assertEqual(result["public_slots"], [])
            self.assertIsNone(result["logic_version"])
            self.assertEqual(result["source"], "signal_rule_contract")

    def test_repo_root_contract_is_the_fallback(self):
        repo_root = self.root / "repo"
        repo_root.mkdir()
        (repo_root / "signal_rule_contract.json").write_text(
            json.dumps(self.CONTRACT), encoding="utf-8",
        )
        with patch("oak_core.supervisor.history._data_root", return_value=self.root), \
             patch("oak_core.supervisor.history._REPO_ROOT", repo_root):
            result = history.today_rules()
        self.assertTrue(result["available"])
        self.assertEqual(result["rules"], ["Quy tắc VN"])

    def test_locale_present_but_empty_is_reported(self):
        self.write("signal_rule_contract.json", dict(self.CONTRACT, rules={"VN": ["Quy tắc VN"]}))
        with self.data_root():
            result = history.today_rules("EN")
        self.assertTrue(result["available"])
        self.assertEqual(result["rules"], [])
        self.assertEqual(result["reason"], "no_rules_for_locale")


class TestHistoryIpcHandlers(_DataRootCase):
    def _run(self, *lines: str) -> list[dict]:
        stdout = io.StringIO()
        server = IpcServer(stdin=io.StringIO("".join(f"{line}\n" for line in lines)),
                           stdout=stdout, stderr=io.StringIO())
        SupervisorApp(server=server).run()
        return [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]

    def test_jsonl_handlers_return_public_payloads(self):
        self.write("signals_log.json", [_record("2026-08-03", 3), _record("2026-08-03", 16)])
        self.write("signal_rule_contract.json", TestTodayRules.CONTRACT)
        self.write("bot_state.json", {"date": "2026-08-03", "broker_time": "", "broker_utc_offset": None})
        with self.data_root():
            responses = self._run(
                '{"v":1,"id":"h1","method":"history.signals","params":{"limit":1}}',
                '{"v":1,"id":"r1","method":"rules.today","params":{"locale":"EN"}}',
            )

        history_result, rules_result = responses[0], responses[1]
        self.assertTrue(history_result["ok"], history_result)
        self.assertEqual(history_result["result"]["count"], 1)
        self.assertEqual(history_result["result"]["records"][0]["hour"], 16)
        self.assertTrue(rules_result["ok"], rules_result)
        self.assertEqual(rules_result["result"]["rules"], ["Rule EN"])
        self.assertFalse(rules_result["result"]["broker_clock_verified"])
        blob = json.dumps(responses, ensure_ascii=False)
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, blob)

    def test_handlers_accept_missing_params(self):
        self.write("signals_log.json", [_record("2026-08-03", 3)])
        self.write("signal_rule_contract.json", TestTodayRules.CONTRACT)
        with self.data_root():
            responses = self._run(
                '{"v":1,"id":"h2","method":"history.signals"}',
                '{"v":1,"id":"r2","method":"rules.today"}',
            )
        self.assertTrue(all(response["ok"] for response in responses), responses)
        self.assertEqual(responses[0]["result"]["count"], 1)
        self.assertEqual(responses[1]["result"]["locale"], "VN")


if __name__ == "__main__":
    unittest.main()
