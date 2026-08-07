# -*- coding: utf-8 -*-
"""Tests for the read-only local economic-news cache surface."""
import ast
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
from oak_core.supervisor import SupervisorApp, news  # noqa: E402

#: Lowercase markers that must never appear in a response sent to React.
FORBIDDEN_MARKERS = (
    "tele_token", "password", "secret", "api_key", "redis", "http://", "https://", "dashboard_api",
)


def assert_public(case: unittest.TestCase, payload) -> None:
    blob = json.dumps(payload, ensure_ascii=False).lower()
    for marker in FORBIDDEN_MARKERS:
        case.assertNotIn(marker, blob)

VN_LINES = [
    "• 05:45 NZD 🔴 [HIGH] Employment Change q/q",
    "• 19:30 USD 🔴 [NỔI BẬT] Non-Farm Payrolls",
]
EN_LINES = ["• 13:00 GBP 🔴 [HIGH] GDP m/m"]


class _NewsCase(unittest.TestCase):
    """Shared temp data root; the module never reads a caller-supplied path."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(prefix="oak-news-")
        self.root = Path(self.tmpdir.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()

    def tearDown(self):
        self.tmpdir.cleanup()

    def write(self, name: str, payload) -> None:
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        (self.root / name).write_text(text, encoding="utf-8")

    def write_cache(self, locale: str, date: str = "2026-08-05", version: int = 6, lines=None) -> None:
        self.write(f"news_cache_{locale}.json", {"date": date, "v": version, "news": lines or []})

    def stamp_broker(self, date: str = "2026-08-05", *, verified: bool = True) -> None:
        self.write("bot_state.json", {
            "date": date,
            "broker_time": f"{date}T20:45:02" if verified else "",
            "broker_utc_offset": 3 if verified else None,
        })

    @contextmanager
    def data_root(self):
        with patch("oak_core.supervisor.news._data_root", return_value=self.root), \
             patch("oak_core.supervisor.news._REPO_ROOT", self.repo), \
             patch("oak_core.supervisor.profiles._data_root", return_value=self.root):
            yield


class TestLocalNewsParsing(_NewsCase):
    def test_vn_and_en_lines_become_structured_items(self):
        self.write_cache("VN", lines=VN_LINES)
        self.write_cache("EN", date="2026-07-16", lines=EN_LINES)
        self.stamp_broker()
        with self.data_root():
            vn = news.local_news("VN")
            en = news.local_news("EN")

        self.assertEqual(vn["source"], "local_news_cache")
        self.assertEqual(vn["locale"], "VN")
        self.assertTrue(vn["available"])
        self.assertEqual(vn["cache_date"], "2026-08-05")
        self.assertEqual(vn["cache_version"], 6)
        self.assertEqual(vn["count"], 2)
        self.assertEqual(vn["items"][0], {
            "date": "2026-08-05",
            "time": "05:45",
            "currency": "NZD",
            "title": "Employment Change q/q",
            "impact": "high",
            "critical": False,
        })
        self.assertEqual(en["locale"], "EN")
        self.assertEqual(en["items"][0]["currency"], "GBP")
        self.assertEqual(en["items"][0]["title"], "GDP m/m")
        assert_public(self, [vn, en])

    def test_impact_and_critical_mapping(self):
        self.write_cache("VN", lines=[
            "• 19:30 USD 🔴 [NỔI BẬT] Non-Farm Payrolls",
            "• 20:00 EUR 🟠 [MEDIUM] Retail Sales m/m",
            "• 21:00 JPY 🟢 [LOW] Housing Starts y/y",
            "• 22:00 USD FOMC Statement",
            "• 23:00 CAD 🟡 Ivey PMI",
        ])
        with self.data_root():
            items = news.local_news()["items"]

        self.assertEqual([item["impact"] for item in items], ["high", "medium", "low", "high", "medium"])
        self.assertEqual([item["critical"] for item in items], [True, False, False, True, False])
        # Decoration never leaks into the headline.
        self.assertEqual(items[0]["title"], "Non-Farm Payrolls")
        self.assertEqual(items[1]["title"], "Retail Sales m/m")

    def test_malformed_lines_are_dropped_not_echoed(self):
        self.write_cache("VN", lines=[
            "• 05:45 NZD 🔴 [HIGH] Employment Change q/q",
            "⚠️ Lỗi hệ thống tin tức: boom",
            "• 99:99 USD 🔴 [HIGH] Impossible clock",
            "• 12:00 ??? 🔴 [HIGH] Unknown currency",
            "• 12:30 USD 🔴 [HIGH]",
            {"time": "13:00"},
            None,
            "",
        ])
        with self.data_root():
            result = news.local_news()

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["time"], "05:45")
        self.assertIn("malformed_lines_dropped", result["warnings"])
        blob = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("Impossible clock", blob)
        self.assertNotIn("Unknown currency", blob)

    def test_item_count_and_title_length_are_bounded(self):
        self.write_cache("VN", lines=[
            f"• 07:{index % 60:02d} USD 🔴 [HIGH] {'x' * 900}" for index in range(news.MAX_ITEMS + 25)
        ])
        with self.data_root():
            result = news.local_news()

        self.assertEqual(result["count"], news.MAX_ITEMS)
        self.assertIn("item_limit_reached", result["warnings"])
        self.assertLessEqual(len(result["items"][0]["title"]), 160)

    def test_locale_is_validated_and_falls_back_to_vn(self):
        self.write_cache("VN", lines=VN_LINES)
        self.write_cache("EN", lines=EN_LINES)
        with self.data_root():
            self.assertEqual(news.local_news("en")["locale"], "EN")
            self.assertEqual(news.local_news("de")["locale"], "VN")
            self.assertEqual(news.local_news("")["locale"], "VN")
            self.assertEqual(news.local_news(None)["locale"], "VN")
            self.assertEqual(news.local_news("../../etc/passwd")["locale"], "VN")

    def test_missing_and_corrupt_cache_degrade_to_unavailable(self):
        with self.data_root():
            missing = news.local_news()
            self.write("news_cache_VN.json", "{not json")
            broken = news.local_news()
            self.write("news_cache_VN.json", ["just", "a", "list"])
            wrong_shape = news.local_news()
            self.write("news_cache_VN.json", {"date": "2026-08-05", "v": 6, "news": "oops"})
            wrong_news = news.local_news()
            self.write_cache("VN", lines=[])
            empty = news.local_news()

        for result in (missing, broken, wrong_shape):
            self.assertFalse(result["available"])
            self.assertEqual(result["items"], [])
            self.assertIn("news_cache_unavailable", result["warnings"])
        self.assertTrue(wrong_news["available"])
        self.assertIn("news_cache_malformed", wrong_news["warnings"])
        self.assertEqual(wrong_news["items"], [])
        self.assertTrue(empty["available"])
        self.assertIn("news_cache_empty", empty["warnings"])

    def test_repo_root_cache_is_the_fallback(self):
        (self.repo / "news_cache_EN.json").write_text(
            json.dumps({"date": "2026-07-16", "v": 6, "news": EN_LINES}, ensure_ascii=False),
            encoding="utf-8",
        )
        with self.data_root():
            result = news.local_news("EN")
        self.assertTrue(result["available"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["cache_date"], "2026-07-16")

    def test_data_root_cache_wins_over_repo_root(self):
        (self.repo / "news_cache_VN.json").write_text(
            json.dumps({"date": "2020-01-01", "v": 1, "news": ["• 01:00 USD 🔴 [HIGH] Old"]}, ensure_ascii=False),
            encoding="utf-8",
        )
        self.write_cache("VN", lines=VN_LINES)
        with self.data_root():
            result = news.local_news()
        self.assertEqual(result["cache_date"], "2026-08-05")
        self.assertEqual(result["cache_version"], 6)


class TestLocalNewsStaleness(_NewsCase):
    def test_fresh_cache_on_verified_broker_day_is_not_stale(self):
        self.write_cache("VN", date="2026-08-05", lines=VN_LINES)
        self.stamp_broker("2026-08-05")
        with self.data_root():
            result = news.local_news()

        self.assertIs(result["stale"], False)
        self.assertTrue(result["broker_clock_verified"])
        self.assertEqual(result["broker_date"], "2026-08-05")
        self.assertNotIn("broker_clock_unverified", result["warnings"])

    def test_old_cache_on_verified_broker_day_is_stale(self):
        self.write_cache("VN", date="2026-07-16", lines=VN_LINES)
        self.stamp_broker("2026-08-05")
        with self.data_root():
            result = news.local_news()
        self.assertIs(result["stale"], True)
        self.assertEqual(result["cache_date"], "2026-07-16")
        self.assertEqual(result["broker_date"], "2026-08-05")

    def test_unverified_or_missing_clock_never_fabricates_a_broker_day(self):
        self.write_cache("VN", date="2026-08-05", lines=VN_LINES)
        with self.data_root():
            no_state = news.local_news()
            self.stamp_broker("2026-08-05", verified=False)
            unverified = news.local_news()
            self.write("bot_state.json", {"date": "2026-08-05", "broker_time": "2026-08-05T20:45:02"})
            no_offset = news.local_news()
            self.write("bot_state.json", "{broken")
            broken_state = news.local_news()

        for result in (no_state, unverified, no_offset, broken_state):
            self.assertIsNone(result["stale"])
            self.assertIsNone(result["broker_date"])
            self.assertFalse(result["broker_clock_verified"])
            self.assertIn("broker_clock_unverified", result["warnings"])
            # The cached items still render; only freshness is unknown.
            self.assertEqual(result["count"], 2)

    def test_missing_cache_date_reports_unknown_freshness(self):
        self.write("news_cache_VN.json", {"v": 6, "news": VN_LINES})
        self.stamp_broker("2026-08-05")
        with self.data_root():
            result = news.local_news()
        self.assertIsNone(result["stale"])
        self.assertIsNone(result["cache_date"])
        self.assertIsNone(result["items"][0]["date"])
        self.assertIn("cache_date_unknown", result["warnings"])

    def test_corrupt_version_is_reported_as_unknown(self):
        self.write("news_cache_VN.json", {"date": "2026-08-05", "v": "six", "news": VN_LINES})
        with self.data_root():
            result = news.local_news()
        self.assertIsNone(result["cache_version"])
        self.assertEqual(result["count"], 2)


class TestNewsIpcHandler(_NewsCase):
    def _run(self, *lines: str) -> list[dict]:
        stdout = io.StringIO()
        server = IpcServer(stdin=io.StringIO("".join(f"{line}\n" for line in lines)),
                           stdout=stdout, stderr=io.StringIO())
        SupervisorApp(server=server).run()
        return [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]

    def test_jsonl_handler_returns_public_payload(self):
        self.write_cache("VN", lines=VN_LINES)
        self.write_cache("EN", date="2026-07-16", lines=EN_LINES)
        self.stamp_broker("2026-08-05")
        with self.data_root():
            responses = self._run(
                '{"v":1,"id":"n1","method":"news.local","params":{"locale":"EN"}}',
                '{"v":1,"id":"n2","method":"news.local"}',
            )

        english, default = responses[0], responses[1]
        self.assertTrue(english["ok"], english)
        self.assertEqual(english["result"]["locale"], "EN")
        self.assertIs(english["result"]["stale"], True)
        self.assertTrue(default["ok"], default)
        self.assertEqual(default["result"]["locale"], "VN")
        self.assertIs(default["result"]["stale"], False)
        self.assertEqual(default["result"]["source"], "local_news_cache")
        assert_public(self, responses)

    def test_handler_survives_a_missing_cache(self):
        with self.data_root():
            responses = self._run('{"v":1,"id":"n3","method":"news.local","params":{"locale":"VN"}}')
        self.assertTrue(responses[0]["ok"], responses[0])
        self.assertFalse(responses[0]["result"]["available"])
        self.assertEqual(responses[0]["result"]["items"], [])


class TestNewsModuleIsCredentialFree(unittest.TestCase):
    """The helper must stay a pure local reader — no feed, no store, no write."""

    ALLOWED_IMPORTS = {"__future__", "json", "re", "pathlib", "typing", "profiles"}

    def test_module_imports_no_network_or_credential_dependency(self):
        tree = ast.parse(Path(news.__file__).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported <= self.ALLOWED_IMPORTS, sorted(imported - self.ALLOWED_IMPORTS))

    def test_module_never_writes(self):
        source = Path(news.__file__).read_text(encoding="utf-8")
        for marker in ("write_text", "open(", "os.environ", "subprocess"):
            self.assertNotIn(marker, source, marker)


if __name__ == "__main__":
    unittest.main()
