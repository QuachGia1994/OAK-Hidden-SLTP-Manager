# -*- coding: utf-8 -*-
"""Tests for the audit dashboard publisher (§10, §11, §16).

Covers:
  - §16 mandatory test: test_public_trade_id_does_not_expose_ticket
  - Public payload leak tests (positions, ledger)
  - Overview equity sample precedence
  - Checkpoint sort order
  - build_all section coverage
  - push_all behaviour (no URL, mock HTTP, error isolation)
  - Empty account resilience
"""
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch, MagicMock

_workspace_root = Path(__file__).resolve().parents[1]
if str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))

from repositories.trade_audit_store import TradeAuditStore
from services.audit_dashboard_publisher import (
    AuditDashboardPublisher,
    public_trade_id,
    public_alias_for,
    DEFAULT_PUBLIC_ALIAS,
)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _make_position(position_id, symbol="XAUUSD", direction="SELL",
                   initial_volume=0.10, open_time_utc=None):
    return {
        "position_id": str(position_id),
        "position_ticket": str(position_id),
        "symbol": symbol,
        "direction": direction,
        "magic": "88000",
        "comment": "test-comment",
        "open_time_utc": open_time_utc,
        "open_time_broker": "",
        "open_price": 2500.0,
        "initial_volume": initial_volume,
        "source_type": "LIVE",
        "public_trade_id": "",
    }


def _make_deal(deal_ticket, position_id, entry_type="OUT", deal_type="SELL",
               volume=0.10, price=2510.0, profit=30.0, commission=-0.5,
               swap=0.0, fee=0.0,
               deal_time_utc="2026-08-04T04:00:00+00:00",
               symbol="XAUUSD", order_ticket=""):
    epoch = int(
        __import__("datetime").datetime.fromisoformat(deal_time_utc).timestamp()
    )
    return {
        "deal_ticket": str(deal_ticket),
        "position_id": str(position_id),
        "order_ticket": str(order_ticket),
        "symbol": symbol,
        "deal_type": deal_type,
        "entry_type": entry_type,
        "reason_raw": "",
        "reason_category": "",
        "volume": volume,
        "price": price,
        "profit": profit,
        "commission": commission,
        "swap": swap,
        "fee": fee,
        "deal_time_utc": deal_time_utc,
        "deal_time_broker": epoch,
        "magic": "88000",
        "comment": "deal-comment",
    }


def _seed_equity_sample(store, account_id, sampled_at_utc, balance, equity,
                         margin=0.0, free_margin=0.0, margin_level=0.0,
                         open_profit=0.0):
    store.upsert_equity_sample(account_id, {
        "sampled_at_utc": sampled_at_utc,
        "sampled_at_broker": sampled_at_utc,
        "balance": balance,
        "equity": equity,
        "margin": margin,
        "free_margin": free_margin,
        "margin_level": margin_level,
        "open_profit": open_profit,
    })


# ---------------------------------------------------------------------- #
# Base test case — temp DB
# ---------------------------------------------------------------------- #
class AuditDashboardPublisherTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="robot-sltp-audit-pub-")
        self.db_path = os.path.join(self._tmpdir.name, "trade_audit.db")
        self.store = TradeAuditStore(db_path=self.db_path, read_only=True)
        self.account_uid = "12345@Vantage-Server"

    def tearDown(self):
        if self.store:
            self.store.close()
        self._tmpdir.cleanup()

    def _create_account(self, public_alias=""):
        return self.store.upsert_account(
            account_uid=self.account_uid, profile_name="VantageDemo",
            broker="Vantage", server="Vantage-Server", currency="USD",
            public_alias=public_alias,
        )


# ===================================================================== #
# §16 MANDATORY TEST
# ===================================================================== #
class TestPublicTradeIdDoesNotExposeTicket(unittest.TestCase):
    """§16 — public_trade_id must be stable, non-reversible, hex 64 chars."""

    def test_public_trade_id_does_not_expose_ticket(self):
        secret = "test-secret-key-12345"
        uid = "12345@Vantage-Server"
        pid = "99887766"

        # Stability: same inputs → same id.
        id1 = public_trade_id(uid, pid, secret)
        id2 = public_trade_id(uid, pid, secret)
        self.assertEqual(id1, id2)

        # Different position_id → different id.
        id3 = public_trade_id(uid, "99887767", secret)
        self.assertNotEqual(id1, id3)

        # 64 hex chars when secret given (SHA-256 digest).
        self.assertEqual(len(id1), 64)
        self.assertRegex(id1, r"^[0-9a-f]{64}$")

        # The id must NOT contain the raw position_id or account_uid or login.
        self.assertNotIn(pid, id1)
        self.assertNotIn(uid, id1)
        self.assertNotIn("12345", id1)

        # Empty secret → fallback to sha256 (still one-way, not reversible).
        id_no_secret = public_trade_id(uid, pid, "")
        self.assertEqual(len(id_no_secret), 64)
        self.assertNotIn(pid, id_no_secret)
        self.assertNotIn(uid, id_no_secret)

        # None secret → fallback.
        id_none_secret = public_trade_id(uid, pid, None)
        self.assertEqual(len(id_none_secret), 64)
        self.assertNotIn(pid, id_none_secret)

        # Empty position_id → empty string.
        self.assertEqual(public_trade_id(uid, "", secret), "")


# ===================================================================== #
# SUPPORTING TESTS
# ===================================================================== #
class TestBuildPositionsNeverLeaksTicketOrComment(AuditDashboardPublisherTestCase):
    """Public position payload must contain zero raw-identity keys."""

    def test_build_positions_never_leaks_ticket_or_comment(self):
        acct_id = self._create_account()
        self.store.upsert_position(acct_id, _make_position("POS_001"))
        self.store.upsert_position(acct_id, _make_position("POS_002", symbol="EURUSD", direction="BUY"))

        pub = AuditDashboardPublisher(self.store, secret="s3cret")
        positions = pub.build_positions(self.account_uid)

        self.assertEqual(len(positions), 2)
        for p in positions:
            # Must have public_trade_id.
            self.assertIn("public_trade_id", p)
            # Must NEVER contain raw identity keys.
            for forbidden_key in ("position_id", "position_ticket", "magic", "comment", "account_uid"):
                self.assertNotIn(forbidden_key, p,
                                 f"Position payload leaked forbidden key: {forbidden_key}")
            # Public trade id must be 64 hex chars.
            self.assertEqual(len(p["public_trade_id"]), 64)


class TestBuildLedgerNeverLeaksDealTicket(AuditDashboardPublisherTestCase):
    """Public ledger payload must contain zero raw deal identity keys."""

    def test_build_ledger_never_leaks_deal_ticket(self):
        acct_id = self._create_account()
        # Trading deal (BUY/SELL) should appear.
        self.store.upsert_deal(acct_id, _make_deal("D1", "P1", deal_type="SELL", entry_type="OUT"))
        # BALANCE deal should be filtered out.
        self.store.upsert_deal(acct_id, _make_deal("D2", "", deal_type="BALANCE", entry_type="IN",
                                                     profit=1000.0))

        pub = AuditDashboardPublisher(self.store, secret="s3cret")
        ledger = pub.build_ledger(self.account_uid)

        # Only SELL deal should appear.
        self.assertEqual(len(ledger), 1)
        entry = ledger[0]
        for forbidden_key in ("deal_ticket", "order_ticket", "magic", "comment", "account_uid"):
            self.assertNotIn(forbidden_key, entry,
                             f"Ledger payload leaked forbidden key: {forbidden_key}")
        self.assertIn("public_trade_id", entry)


class TestOverviewUsesLatestEquitySample(AuditDashboardPublisherTestCase):
    """Overview must use the latest equity sample for balance/equity values."""

    def test_overview_uses_latest_equity_sample(self):
        acct_id = self._create_account()
        _seed_equity_sample(self.store, acct_id,
                            "2026-08-04T00:00:00+00:00",
                            balance=10000.0, equity=10050.0)
        _seed_equity_sample(self.store, acct_id,
                            "2026-08-04T01:00:00+00:00",
                            balance=10100.0, equity=10200.0,
                            margin=500.0, free_margin=9600.0,
                            margin_level=2040.0, open_profit=100.0)

        pub = AuditDashboardPublisher(self.store, secret="s3cret")
        overview = pub.build_overview(self.account_uid)

        self.assertAlmostEqual(overview["balance"], 10100.0)
        self.assertAlmostEqual(overview["equity"], 10200.0)
        self.assertAlmostEqual(overview["floating_pl"], 100.0)
        self.assertAlmostEqual(overview["margin"], 500.0)
        self.assertAlmostEqual(overview["free_margin"], 9600.0)
        self.assertAlmostEqual(overview["margin_level"], 2040.0)
        self.assertEqual(overview["broker"], "Vantage")
        self.assertEqual(overview["currency"], "USD")


class TestCheckpointsSortedChronologically(AuditDashboardPublisherTestCase):
    """Checkpoint list must be returned in chronological ascending order."""

    def test_checkpoints_sorted_chronologically(self):
        acct_id = self._create_account()
        # Insert out of order (newest first due to DESC in store).
        self.store.upsert_checkpoint_run(acct_id, "2026-08-04", 7, status="COMPLETED",
                                         captured_at_utc="2026-08-04T07:30:00+00:00")
        self.store.upsert_checkpoint_run(acct_id, "2026-08-04", 3, status="COMPLETED",
                                         captured_at_utc="2026-08-04T03:30:00+00:00")
        self.store.upsert_checkpoint_run(acct_id, "2026-08-03", 21, status="COMPLETED",
                                         captured_at_utc="2026-08-03T21:30:00+00:00")

        pub = AuditDashboardPublisher(self.store, secret="s3cret")
        cps = pub.build_checkpoints(self.account_uid)

        self.assertEqual(len(cps), 3)
        # Must be ascending by broker_date then checkpoint_hour.
        self.assertEqual(cps[0]["broker_date"], "2026-08-03")
        self.assertEqual(cps[0]["checkpoint_hour"], 21)
        self.assertEqual(cps[1]["broker_date"], "2026-08-04")
        self.assertEqual(cps[1]["checkpoint_hour"], 3)
        self.assertEqual(cps[2]["broker_date"], "2026-08-04")
        self.assertEqual(cps[2]["checkpoint_hour"], 7)


class TestBuildAllContainsAllSections(AuditDashboardPublisherTestCase):
    """build_all must return a dict with all 7 section keys."""

    def test_build_all_contains_all_sections(self):
        acct_id = self._create_account()
        pub = AuditDashboardPublisher(self.store, secret="s3cret")
        result = pub.build_all(self.account_uid)

        self.assertIsInstance(result, dict)
        for key in ("overview", "positions", "checkpoints", "ledger",
                     "performance", "risk", "audit"):
            self.assertIn(key, result)
        self.assertIsInstance(result["overview"], dict)
        self.assertIsInstance(result["positions"], list)
        self.assertIsInstance(result["checkpoints"], list)
        self.assertIsInstance(result["ledger"], list)
        self.assertIsInstance(result["performance"], dict)
        self.assertIsInstance(result["risk"], dict)
        self.assertIsInstance(result["audit"], dict)


class TestPushAllWithoutUrlReturnsNotPushed(AuditDashboardPublisherTestCase):
    """push_all with no dashboard_url returns pushed=False, never raises."""

    def test_push_all_without_url_returns_not_pushed(self):
        self._create_account()
        pub = AuditDashboardPublisher(self.store, secret="s3cret",
                                       dashboard_url="", api_key="")
        result = pub.push_all(self.account_uid)

        self.assertFalse(result["pushed"])
        self.assertEqual(result["reason"], "no dashboard url")


class TestPushAllWithNoneUrlFallsBackToConfig(AuditDashboardPublisherTestCase):
    """push_all with default None url reads config.json (may push or not)."""

    def test_push_all_with_none_uses_config(self):
        self._create_account()
        # None means "use config.json / env fallback".
        pub = AuditDashboardPublisher(self.store, secret="s3cret",
                                       dashboard_url=None, api_key=None)
        # Config.json may or may not have dashboard_url; result depends on env.
        result = pub.push_all(self.account_uid)
        # Just verify it doesn't raise.
        self.assertIsInstance(result, dict)
        self.assertIn("pushed", result)


class TestPushAllPostsToEndpointsWithApiKey(AuditDashboardPublisherTestCase):
    """push_all must POST to all 7 endpoints with X-API-Key header."""

    def test_push_all_posts_to_endpoints_with_api_key(self):
        self._create_account()
        pub = AuditDashboardPublisher(self.store, secret="s3cret",
                                       dashboard_url="https://example.com",
                                       api_key="my-secret-key")

        captured_requests = []

        class FakeResponse:
            status = 200
            def read(self):
                return b'{"ok":true}'
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        def fake_urlopen(request, timeout=None):
            captured_requests.append(request)
            return FakeResponse()

        with patch("services.audit_dashboard_publisher.urllib.request.urlopen",
                    side_effect=fake_urlopen):
            result = pub.push_all(self.account_uid)

        self.assertTrue(result["pushed"])
        self.assertEqual(len(captured_requests), 7)

        # Verify API key header on every request.
        # NOTE: Python Request.add_header capitalizes the first letter and
        # lowercases the rest, so "X-API-Key" becomes "X-api-key" internally.
        for req in captured_requests:
            self.assertEqual(req.get_header("X-api-key"), "my-secret-key")
            self.assertEqual(req.method, "POST")
            self.assertIn("/api/trade-audit/", req.full_url)

        # Verify all 7 endpoint sections returned ok=True.
        for section in ("overview", "positions", "checkpoints", "ledger",
                         "performance", "risk", "audit"):
            self.assertTrue(result["results"][section]["ok"],
                            f"Section {section} should be ok=True")


class TestPushAllContinuesOnEndpointError(AuditDashboardPublisherTestCase):
    """push_all must isolate per-endpoint errors, never abort the loop."""

    def test_push_all_continues_on_endpoint_error(self):
        self._create_account()
        pub = AuditDashboardPublisher(self.store, secret="s3cret",
                                       dashboard_url="https://example.com",
                                       api_key="key")

        call_count = [0]

        class FakeResponse:
            status = 200
            def read(self):
                return b'{}'
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        def fake_urlopen(request, timeout=None):
            call_count[0] += 1
            if call_count[0] == 2:
                raise urllib.error.HTTPError(
                    request.full_url, 500, "Server Error", {}, None
                )
            return FakeResponse()

        with patch("services.audit_dashboard_publisher.urllib.request.urlopen",
                    side_effect=fake_urlopen):
            result = pub.push_all(self.account_uid)

        # Overall pushed=False because one endpoint failed.
        self.assertFalse(result["pushed"])
        # Second endpoint (positions) failed.
        self.assertFalse(result["results"]["positions"]["ok"])
        self.assertEqual(result["results"]["positions"]["status"], 500)
        # Other endpoints succeeded.
        self.assertTrue(result["results"]["overview"]["ok"])
        self.assertTrue(result["results"]["checkpoints"]["ok"])
        self.assertTrue(result["results"]["ledger"]["ok"])
        self.assertTrue(result["results"]["performance"]["ok"])
        self.assertTrue(result["results"]["risk"]["ok"])
        self.assertTrue(result["results"]["audit"]["ok"])


class TestEmptyAccountBuildsDoNotRaise(AuditDashboardPublisherTestCase):
    """Fresh account with no data → all builders return empty/default, no exception."""

    def test_empty_account_builds_do_not_raise(self):
        self._create_account()
        pub = AuditDashboardPublisher(self.store, secret="s3cret",
                                       dashboard_url="", api_key="")

        overview = pub.build_overview(self.account_uid)
        self.assertIsInstance(overview, dict)
        self.assertEqual(overview["balance"], None)
        self.assertEqual(overview["equity"], None)

        positions = pub.build_positions(self.account_uid)
        self.assertEqual(positions, [])

        checkpoints = pub.build_checkpoints(self.account_uid)
        self.assertEqual(checkpoints, [])

        ledger = pub.build_ledger(self.account_uid)
        self.assertEqual(ledger, [])

        performance = pub.build_performance(self.account_uid)
        self.assertIsInstance(performance, dict)
        self.assertIn("win_rate_basis", performance)
        self.assertIn("trading_return_pct", performance)
        self.assertIn("account_growth_pct", performance)

        risk = pub.build_risk(self.account_uid)
        self.assertIsInstance(risk, dict)
        self.assertEqual(risk["open_position_count"], 0)

        audit = pub.build_audit(self.account_uid)
        self.assertIsInstance(audit, dict)

        # build_all must also not raise.
        all_data = pub.build_all(self.account_uid)
        self.assertEqual(set(all_data.keys()),
                         {"overview", "positions", "checkpoints", "ledger",
                          "performance", "risk", "audit"})

        # push_all without url must not raise.
        push_result = pub.push_all(self.account_uid)
        self.assertFalse(push_result["pushed"])


if __name__ == "__main__":
    unittest.main()
