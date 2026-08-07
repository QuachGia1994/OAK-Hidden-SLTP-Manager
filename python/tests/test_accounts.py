# -*- coding: utf-8 -*-
"""Tests for Phase 3 account-audit queries (§9) — account.get, positions,
deals, checkpoints, performance. Uses a temp trade_audit.db."""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_python_root = Path(__file__).resolve().parents[1]
if str(_python_root) not in sys.path:
    sys.path.insert(0, str(_python_root))

# Repo root for importing repositories/ + services/
_repo_root = _python_root.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from repositories.trade_audit_store import TradeAuditStore  # noqa: E402
from oak_core.supervisor.accounts import AccountQueries  # noqa: E402
from oak_core.supervisor import SupervisorApp  # noqa: E402
from oak_core.ipc.server import IpcServer  # noqa: E402


def seed_store(db_path: str) -> int:
    """Seed a temp ledger and return the account_id."""
    store = TradeAuditStore(db_path=db_path, read_only=True)
    account_id = store.upsert_account(
        account_uid="12345@Vantage-Server", profile_name="Vantage",
        broker="Vantage", server="Vantage-Server", currency="USD",
    )
    store.upsert_equity_sample(account_id, {
        "sampled_at_utc": "2026-08-04T03:00:00+00:00",
        "sampled_at_broker": "2026-08-04T03:00:00",
        "balance": 10000.0, "equity": 10100.0, "margin": 500.0,
        "free_margin": 9600.0, "margin_level": 2020.0, "open_profit": 100.0,
    })
    store.upsert_position(account_id, {
        "position_id": "5001", "position_ticket": "5001",
        "symbol": "XAUUSD", "direction": "BUY", "initial_volume": 0.10,
        "open_price": 2500.0, "open_time_utc": "2026-08-03T20:00:00+00:00",
        "source_type": "LIVE", "public_trade_id": "pub-5001",
    })
    store.upsert_deal(account_id, {
        "deal_ticket": "9001", "position_id": "5001", "symbol": "XAUUSD",
        "deal_type": "BUY", "entry_type": "IN", "reason_category": "",
        "volume": 0.10, "price": 2500.0, "profit": 0.0, "commission": -0.5,
        "swap": 0.0, "fee": 0.0, "deal_time_utc": "2026-08-03T20:00:00+00:00",
        "deal_time_broker": "", "magic": "88000", "comment": "",
    })
    run_id = store.upsert_checkpoint_run(
        account_id, "2026-08-04", 3,
        interval_start="2026-08-03T16:00:00", interval_end="2026-08-04T03:00:00",
        captured_at_utc="2026-08-04T03:05:00+00:00",
        capture_mode="NORMAL", status="COMPLETED",
    )
    store.upsert_checkpoint_position_state(run_id, {
        "position_id": "5001", "status_at_checkpoint": "STILL_OPEN",
        "volume": 0.10, "current_price": 2510.0, "floating_profit": 10.0,
        "sl": None, "tp": None, "capture_mode": "NORMAL",
    })
    store.close()
    return account_id


class AccountQueriesTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="oak-accounts-")
        self.db_path = os.path.join(self._tmpdir.name, "trade_audit.db")
        self.account_id = seed_store(self.db_path)
        # One store for the whole test; AccountQueries uses it directly.
        self.store = TradeAuditStore(db_path=self.db_path, read_only=True)
        self.queries = AccountQueries(store=self.store)

    def tearDown(self):
        if self.store is not None:
            self.store.close()
            self.store = None
        self._tmpdir.cleanup()


class TestAccountGet(AccountQueriesTestCase):
    def test_account_get_returns_latest_sample(self):
        result = self.queries.account_get("Vantage")
        self.assertTrue(result["available"])
        self.assertEqual(result["balance"], 10000.0)
        self.assertEqual(result["equity"], 10100.0)
        self.assertEqual(result["margin_level"], 2020.0)

    def test_account_get_unknown_profile(self):
        result = self.queries.account_get("Ghost")
        self.assertFalse(result["available"])


class TestPositionsList(AccountQueriesTestCase):
    def test_positions_public_safe(self):
        positions = self.queries.positions_list("Vantage")
        self.assertEqual(len(positions), 1)
        p = positions[0]
        self.assertEqual(p["public_trade_id"], "pub-5001")
        self.assertEqual(p["symbol"], "XAUUSD")
        self.assertEqual(p["direction"], "BUY")
        # No raw identity KEYS leak (public_trade_id is the only id field).
        self.assertEqual(
            set(p.keys()),
            {"public_trade_id", "symbol", "direction", "volume",
             "open_price", "open_time_utc", "source_type"},
        )

    def test_positions_unknown_profile_empty(self):
        self.assertEqual(self.queries.positions_list("Ghost"), [])

    def test_positions_closed_at_latest_checkpoint_excluded(self):
        # A newer checkpoint marks the position CLOSED — the historical
        # ``positions`` row must stay, but must not be reported as open.
        run_id = self.store.upsert_checkpoint_run(
            self.account_id, "2026-08-04", 4,
            interval_start="2026-08-04T03:00:00", interval_end="2026-08-04T04:00:00",
            captured_at_utc="2026-08-04T04:05:00+00:00",
            capture_mode="NORMAL", status="COMPLETED",
        )
        self.store.upsert_checkpoint_position_state(run_id, {
            "position_id": "5001", "status_at_checkpoint": "CLOSED_MANUAL",
            "volume": 0.10, "close_price": 2510.0,
            "close_time_utc": "2026-08-04T03:30:00+00:00",
            "close_reason": "MANUAL", "capture_mode": "NORMAL",
        })
        self.assertEqual(self.queries.positions_list("Vantage"), [])
        # Historical ledger row untouched.
        self.assertEqual(len(self.store.list_positions(account_id=self.account_id)), 1)

    def test_positions_partially_closed_uses_state_volume(self):
        run_id = self.store.upsert_checkpoint_run(
            self.account_id, "2026-08-04", 5,
            captured_at_utc="2026-08-04T05:05:00+00:00",
            capture_mode="NORMAL", status="COMPLETED",
        )
        self.store.upsert_checkpoint_position_state(run_id, {
            "position_id": "5001", "status_at_checkpoint": "PARTIALLY_CLOSED",
            "volume": 0.04, "current_price": 2510.0, "capture_mode": "NORMAL",
        })
        positions = self.queries.positions_list("Vantage")
        self.assertEqual(len(positions), 1)
        self.assertAlmostEqual(positions[0]["volume"], 0.04)

    def test_positions_empty_latest_checkpoint(self):
        # Latest checkpoint exists but records no states at all.
        self.store.upsert_checkpoint_run(
            self.account_id, "2026-08-05", 0,
            captured_at_utc="2026-08-05T00:05:00+00:00",
            capture_mode="NORMAL", status="COMPLETED",
        )
        self.assertEqual(self.queries.positions_list("Vantage"), [])

    def test_positions_without_any_checkpoint_empty(self):
        account_id = self.store.upsert_account(
            account_uid="67890@Other-Server", profile_name="Other",
            broker="Other", server="Other-Server", currency="USD",
        )
        self.store.upsert_position(account_id, {
            "position_id": "7001", "position_ticket": "7001",
            "symbol": "EURUSD", "direction": "SELL", "initial_volume": 0.20,
            "open_price": 1.1, "open_time_utc": "2026-08-03T20:00:00+00:00",
            "source_type": "RECONSTRUCTED", "public_trade_id": "pub-7001",
        })
        self.assertEqual(self.queries.positions_list("Other"), [])


class TestDealsAndCheckpoints(AccountQueriesTestCase):
    def test_deals_list_trading_only(self):
        deals = self.queries.deals_list("Vantage", limit=50)
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0]["deal_type"], "BUY")
        blob = json.dumps(deals)
        self.assertNotIn("deal_ticket", blob)

    def test_checkpoints_chronological(self):
        checkpoints = self.queries.checkpoints_list("Vantage")
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0]["checkpoint_hour"], 3)
        self.assertEqual(checkpoints[0]["capture_mode"], "NORMAL")
        self.assertEqual(checkpoints[0]["status"], "COMPLETED")


class TestPerformanceSummary(AccountQueriesTestCase):
    def test_performance_public_safe(self):
        result = self.queries.performance_summary("Vantage")
        self.assertTrue(result["available"])
        for key in ("current_balance", "current_equity", "profit_factor",
                    "win_rate", "max_equity_drawdown", "drawdown_source"):
            self.assertIn(key, result)

    def test_performance_unknown_profile(self):
        result = self.queries.performance_summary("Ghost")
        self.assertFalse(result["available"])


class TestPhase4CurvesAndRisk(AccountQueriesTestCase):
    def seed_extra_samples(self):
        store = self.store
        # Hours 00, 01, 02, 04 — 03 already exists from seed_store (10100).
        for idx, equity in enumerate([10000.0, 10500.0, 9800.0, 10200.0]):
            hour = [0, 1, 2, 4][idx]
            store.upsert_equity_sample(self.account_id, {
                "sampled_at_utc": f"2026-08-04T{hour:02d}:00:00+00:00",
                "sampled_at_broker": f"2026-08-04T{hour:02d}:00:00",
                "balance": equity, "equity": equity, "margin": 500.0,
                "free_margin": equity - 500.0, "margin_level": 2000.0,
                "open_profit": 0.0,
            })

    def test_equity_curve_chronological(self):
        self.seed_extra_samples()
        curve = self.queries.equity_curve("Vantage", limit=100)
        # 5 samples: 10000, 10500, 9800, 10100(seed 03:00), 10200.
        self.assertEqual(len(curve), 5)
        self.assertEqual(curve[0]["equity"], 10000.0)
        self.assertEqual(curve[-1]["equity"], 10200.0)
        self.assertEqual(curve[1]["equity"], 10500.0)

    def test_drawdown_curve_peak_logic(self):
        self.seed_extra_samples()
        curve = self.queries.drawdown_curve("Vantage", limit=100)
        # 10000 -> peak 10000 dd 0; 10500 -> peak 10500 dd 0;
        # 9800 -> peak 10500 dd 700; 10100 -> dd 400; 10200 -> dd 300.
        dds = [c["drawdown"] for c in curve]
        self.assertEqual(dds[0], 0.0)
        self.assertEqual(dds[1], 0.0)
        self.assertAlmostEqual(dds[2], 700.0)
        self.assertAlmostEqual(dds[-1], 300.0)

    def test_risk_summary_exposure(self):
        self.seed_extra_samples()
        result = self.queries.risk_summary("Vantage")
        self.assertTrue(result["available"])
        self.assertEqual(result["exposure_by_symbol"], {"XAUUSD": 0.10})
        self.assertEqual(result["open_position_count"], 1)
        self.assertIn("max_equity_drawdown", result)
        # Direction exposure BUY=0.10 (our seeded position is BUY).
        self.assertAlmostEqual(result["exposure_by_direction"].get("BUY", 0.0), 0.10)

    def test_risk_unknown_profile(self):
        result = self.queries.risk_summary("Ghost")
        self.assertFalse(result["available"])


class TestSupervisorAccountHandlers(unittest.TestCase):
    def _make_server(self, input_text, db_path):
        stdin = io.StringIO(input_text)
        stdout = io.StringIO()
        stderr = io.StringIO()
        server = IpcServer(stdin=stdin, stdout=stdout, stderr=stderr)
        store = TradeAuditStore(db_path=db_path, read_only=True)
        queries = AccountQueries(store=store)
        app = SupervisorApp(server=server, account_queries=queries)
        # Keep the store so tests can close it before tmpdir cleanup.
        self._server_store = store
        return server, stdout, app

    def _responses(self, stdout):
        return [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]

    def _run(self, text, db_path):
        server, stdout, app = self._make_server(text, db_path)
        app.run()
        try:
            return self._responses(stdout)
        finally:
            self._server_store.close()

    def test_account_get_handler_roundtrip(self):
        with tempfile.TemporaryDirectory(prefix="oak-ipc3-") as tmp:
            db_path = os.path.join(tmp, "trade_audit.db")
            seed_store(db_path)
            responses = self._run(
                '{"v":1,"id":"a1","method":"account.get","params":{"profile":"Vantage"}}\n'
                '{"v":1,"id":"p1","method":"positions.list","params":{"profile":"Vantage"}}\n'
                '{"v":1,"id":"c1","method":"checkpoints.list","params":{"profile":"Vantage"}}\n',
                db_path)
            self.assertTrue(responses[0]["ok"])
            self.assertEqual(responses[0]["result"]["balance"], 10000.0)
            self.assertTrue(responses[1]["ok"])
            self.assertEqual(len(responses[1]["result"]["positions"]), 1)
            self.assertTrue(responses[2]["ok"])
            self.assertEqual(len(responses[2]["result"]["checkpoints"]), 1)

    def test_account_get_missing_param_errors(self):
        with tempfile.TemporaryDirectory(prefix="oak-ipc3-") as tmp:
            db_path = os.path.join(tmp, "trade_audit.db")
            seed_store(db_path)
            responses = self._run(
                '{"v":1,"id":"a2","method":"account.get"}\n', db_path)
            self.assertFalse(responses[0]["ok"])


if __name__ == "__main__":
    unittest.main()
