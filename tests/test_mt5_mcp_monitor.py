# -*- coding: utf-8 -*-
"""Safety tests for the read-only audit MCP prototype (``mt5_mcp_server``).

No terminal, no credentials, no orders: every test runs against a temporary
audit ledger seeded with the existing ``TradeAuditStore`` and then closed.
"""
import asyncio
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (str(_REPO_ROOT), str(_REPO_ROOT / "python")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from repositories.trade_audit_store import TradeAuditStore  # noqa: E402

import mt5_mcp_server as server  # noqa: E402

EXPECTED_TOOLS = {
    "list_accounts",
    "account_overview",
    "performance_summary",
    "trade_history",
    "equity_curve",
    "checkpoint_history",
    "risk_summary",
    "audit_integrity",
}

# Substrings that must never reach an MCP client.
SECRET_MARKERS = (
    "account_uid",
    "12345@Vantage-Server",
    "Vantage-Server",
    "login",
    "password",
    "token",
    "deal_ticket",
    "position_ticket",
    "public_trade_id",
    "magic",
    "88000",
    "oak-entry",
    "terminal64",
    ".exe",
    "C:\\",
)

DEAL_FIELDS = {
    "symbol", "deal_type", "entry_type", "reason_category", "volume", "price",
    "profit", "commission", "swap", "fee", "deal_time_utc",
}


def seed_ledger(db_path: str) -> int:
    """Seed a temporary ledger with the writable store, then close it."""
    store = TradeAuditStore(db_path=db_path, read_only=True)
    account_id = store.upsert_account(
        account_uid="12345@Vantage-Server", profile_name="Vantage",
        broker="Vantage", server="Vantage-Server", currency="USD",
        account_type="REAL",
    )
    for hour, equity in ((1, 10000.0), (2, 10500.0), (3, 10100.0)):
        store.upsert_equity_sample(account_id, {
            "sampled_at_utc": f"2026-08-04T{hour:02d}:00:00+00:00",
            "sampled_at_broker": f"2026-08-04T{hour:02d}:00:00",
            "balance": 10000.0, "equity": equity, "margin": 500.0,
            "free_margin": equity - 500.0, "margin_level": 2020.0,
            "open_profit": equity - 10000.0,
        })
    store.upsert_position(account_id, {
        "position_id": "5001", "position_ticket": "5001", "symbol": "XAUUSD",
        "direction": "BUY", "initial_volume": 0.10, "open_price": 2500.0,
        "open_time_utc": "2026-08-03T20:00:00+00:00", "source_type": "LIVE",
        "public_trade_id": "pub-5001", "magic": "88000", "comment": "oak-entry",
    })
    deals = (
        {"deal_ticket": "9001", "position_id": "5001", "symbol": "XAUUSD",
         "deal_type": "BUY", "entry_type": "IN", "reason_category": "MANUAL",
         "volume": 0.10, "price": 2500.0, "profit": 0.0, "commission": -0.5,
         "swap": 0.0, "fee": 0.0, "deal_time_utc": "2026-08-03T20:00:00+00:00"},
        {"deal_ticket": "9002", "position_id": "5001", "symbol": "XAUUSD",
         "deal_type": "SELL", "entry_type": "OUT", "reason_category": "TP",
         "volume": 0.10, "price": 2525.0, "profit": 25.0, "commission": -0.5,
         "swap": -0.2, "fee": 0.0, "deal_time_utc": "2026-08-04T02:00:00+00:00"},
        {"deal_ticket": "9003", "position_id": "5002", "symbol": "EURUSD",
         "deal_type": "BUY", "entry_type": "IN", "reason_category": "MANUAL",
         "volume": 0.20, "price": 1.1, "profit": 0.0, "commission": -0.3,
         "swap": 0.0, "fee": 0.0, "deal_time_utc": "2026-08-04T02:30:00+00:00"},
        {"deal_ticket": "9004", "position_id": "", "symbol": "",
         "deal_type": "BALANCE", "entry_type": "IN", "reason_category": "",
         "volume": 0.0, "price": 0.0, "profit": 1000.0, "commission": 0.0,
         "swap": 0.0, "fee": 0.0, "deal_time_utc": "2026-08-01T00:00:00+00:00"},
    )
    for deal in deals:
        deal.update({"magic": "88000", "comment": "oak-entry", "order_ticket": "1",
                     "reason_raw": "", "deal_time_broker": ""})
        store.upsert_deal(account_id, deal)
    run_id = store.upsert_checkpoint_run(
        account_id, "2026-08-04", 3,
        interval_start="2026-08-03T16:00:00", interval_end="2026-08-04T03:00:00",
        captured_at_utc="2026-08-04T03:05:00+00:00",
        capture_mode="NORMAL", status="COMPLETED",
    )
    store.upsert_snapshot(run_id, {
        "balance": 10000.0, "equity": 10100.0, "margin": 500.0,
        "free_margin": 9600.0, "margin_level": 2020.0, "open_profit": 100.0,
    })
    store.upsert_checkpoint_position_state(run_id, {
        "position_id": "5001", "status_at_checkpoint": "STILL_OPEN", "volume": 0.10,
        "current_price": 2525.0, "floating_profit": 25.0, "sl": 2490.0, "tp": 2530.0,
    })
    store.add_cash_flow(account_id, "2026-08-01T00:00:00+00:00", "DEPOSIT", 1000.0)
    store.append_audit_event(account_id, "ACCOUNT_SEEN", "account", "12345",
                             payload={"n": 1}, event_time_utc="2026-08-04T01:00:00+00:00")
    store.append_audit_event(account_id, "CHECKPOINT", "checkpoint_run", str(run_id),
                             payload={"n": 2}, event_time_utc="2026-08-04T03:05:00+00:00")
    store.close()
    return account_id


def sidecars(db_path: str) -> list:
    return [suffix for suffix in ("-wal", "-shm") if os.path.exists(db_path + suffix)]


def fingerprint(db_path: str) -> tuple:
    data = Path(db_path).read_bytes()
    return len(data), hashlib.sha256(data).hexdigest()


class McpMonitorTestCase(unittest.TestCase):
    """Temp ledger + allow-listed profile, with full environment cleanup."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="oak-mcp-")
        self.db_path = os.path.join(self._tmp.name, "trade_audit.db")
        self.account_id = seed_ledger(self.db_path)
        # Precondition: the writable store cleaned up its own WAL sidecars.
        self.assertEqual(sidecars(self.db_path), [])
        self._saved_env = {key: os.environ.get(key)
                           for key in ("OAK_MCP_AUDIT_DB", "OAK_MCP_PROFILES")}
        os.environ["OAK_MCP_AUDIT_DB"] = self.db_path
        os.environ["OAK_MCP_PROFILES"] = "Vantage"

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def assertPublicSafe(self, payload):
        blob = json.dumps(payload)
        for marker in SECRET_MARKERS:
            self.assertNotIn(marker, blob, f"leaked marker: {marker}")


class TestToolSurface(McpMonitorTestCase):
    def test_registers_exactly_eight_read_only_tools(self):
        tools = asyncio.run(server.mcp.list_tools())
        self.assertEqual({tool.name for tool in tools}, EXPECTED_TOOLS)
        self.assertEqual(len(tools), 8)

    def test_no_mutation_or_trading_tool_names(self):
        names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
        for banned in ("order", "close", "open", "start", "stop", "set", "update",
                       "write", "delete", "copy", "sltp", "modify", "send"):
            self.assertFalse([n for n in names if banned in n], f"suspicious: {banned}")

    def test_no_tool_accepts_a_path_or_credential_argument(self):
        for tool in asyncio.run(server.mcp.list_tools()):
            properties = set((tool.inputSchema or {}).get("properties", {}))
            for banned in ("db", "db_path", "path", "database", "login", "password",
                           "account_uid", "terminal", "sql", "query"):
                self.assertNotIn(banned, properties, f"{tool.name} exposes {banned}")


class TestAccountReports(McpMonitorTestCase):
    def test_list_accounts_safe_fields_only(self):
        result = server.list_accounts()
        self.assertTrue(result["configured"])
        self.assertEqual(result["source"], "audit_ledger")
        self.assertEqual(len(result["accounts"]), 1)
        account = result["accounts"][0]
        self.assertEqual(set(account), {"profile", "broker", "currency",
                                        "account_type", "available",
                                        "latest_sampled_at_utc"})
        self.assertEqual(account["profile"], "Vantage")
        self.assertTrue(account["available"])
        self.assertEqual(account["latest_sampled_at_utc"], "2026-08-04T03:00:00+00:00")
        self.assertEqual(result["observed_at_utc"], "2026-08-04T03:00:00+00:00")
        self.assertGreaterEqual(result["data_age_seconds"], 0.0)
        self.assertPublicSafe(result)

    def test_list_accounts_without_allowlist_is_empty(self):
        os.environ["OAK_MCP_PROFILES"] = "  "
        self.assertEqual(server.list_accounts(),
                         {"configured": False, "accounts": [],
                          "source": "audit_ledger", "observed_at_utc": None,
                          "data_age_seconds": None})

    def test_list_accounts_freshness_is_null_without_samples(self):
        os.environ["OAK_MCP_PROFILES"] = "Ghost"
        result = server.list_accounts()
        self.assertTrue(result["configured"])
        self.assertFalse(result["accounts"][0]["available"])
        self.assertEqual(result["source"], "audit_ledger")
        self.assertIsNone(result["observed_at_utc"])
        self.assertIsNone(result["data_age_seconds"])

    def test_account_overview_is_freshness_labelled(self):
        result = server.account_overview("Vantage")
        self.assertTrue(result["available"])
        self.assertEqual(result["source"], "audit_ledger")
        self.assertEqual(result["balance"], 10000.0)
        self.assertEqual(result["equity"], 10100.0)
        self.assertEqual(result["observed_at_utc"], "2026-08-04T03:00:00+00:00")
        self.assertGreaterEqual(result["data_age_seconds"], 0.0)
        self.assertPublicSafe(result)

    def test_unknown_profile_in_allowlist_is_unavailable(self):
        os.environ["OAK_MCP_PROFILES"] = "Vantage,Ghost"
        self.assertFalse(server.account_overview("Ghost")["available"])
        self.assertFalse(server.performance_summary("Ghost")["available"])
        self.assertFalse(server.trade_history("Ghost")["available"])
        self.assertFalse(server.equity_curve("Ghost")["available"])
        self.assertFalse(server.checkpoint_history("Ghost")["available"])
        self.assertFalse(server.risk_summary("Ghost")["available"])
        self.assertIsNone(server.audit_integrity("Ghost")["ok"])


class TestPerformanceReports(McpMonitorTestCase):
    def test_performance_summary_public_safe(self):
        result = server.performance_summary("Vantage")
        self.assertTrue(result["available"])
        self.assertEqual(result["source"], "audit_ledger")
        for key in ("current_balance", "current_equity", "realized_pl", "win_rate",
                    "profit_factor", "max_equity_drawdown", "drawdown_source",
                    "net_cash_flow", "total_commission"):
            self.assertIn(key, result)
        self.assertEqual(result["realized_pl"], 25.0)
        self.assertEqual(result["observed_at_utc"], "2026-08-04T03:00:00+00:00")
        self.assertGreaterEqual(result["data_age_seconds"], 0.0)
        self.assertPublicSafe(result)

    def test_unrealized_pl_is_not_invented(self):
        self.assertIsNone(server.performance_summary("Vantage")["unrealized_pl"])

    def test_equity_curve_is_chronological(self):
        result = server.equity_curve("Vantage", limit=10)
        self.assertEqual(result["source"], "audit_ledger")
        self.assertEqual(result["count"], 3)
        self.assertEqual([s["equity"] for s in result["samples"]],
                         [10000.0, 10500.0, 10100.0])
        self.assertEqual(set(result["samples"][0]), {"t", "equity", "balance"})
        self.assertEqual(result["observed_at_utc"], "2026-08-04T03:00:00+00:00")

    def test_checkpoint_history_public_fields(self):
        result = server.checkpoint_history("Vantage", limit=5)
        self.assertEqual(result["source"], "audit_ledger")
        self.assertEqual(result["count"], 1)
        self.assertEqual(set(result["checkpoints"][0]),
                         {"broker_date", "checkpoint_hour", "interval_start",
                          "interval_end", "captured_at_utc", "capture_mode", "status"})
        self.assertEqual(result["checkpoints"][0]["status"], "COMPLETED")
        self.assertPublicSafe(result)

    def test_risk_summary_is_marked_ledger_derived(self):
        result = server.risk_summary("Vantage")
        self.assertTrue(result["available"])
        self.assertEqual(result["source"], "audit_ledger")
        self.assertIn("ledger", result["basis"].lower())
        self.assertEqual(result["open_position_count"], 1)
        self.assertIn("max_equity_drawdown", result)
        self.assertPublicSafe(result)

    def test_risk_summary_succeeds_with_checkpoint_position_states(self):
        """Phase 1 risk_summary must succeed now that positions_list() reads
        checkpoint_position_states via the new ReadOnlyAuditStore method."""
        result = server.risk_summary("Vantage")
        self.assertTrue(result["available"])
        self.assertEqual(result["source"], "audit_ledger")
        self.assertIn("ledger", result["basis"].lower())
        # The seeded OPEN checkpoint state feeds positions_list -> 1 open position.
        self.assertEqual(result["open_position_count"], 1)
        self.assertEqual(result["exposure_by_symbol"].get("XAUUSD"), 0.10)
        self.assertPublicSafe(result)

    def test_audit_integrity_reports_chain_only(self):
        result = server.audit_integrity("Vantage")
        self.assertEqual(set(result),
                         {"profile", "source", "ok", "events", "first_broken"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["events"], 2)
        self.assertIsNone(result["first_broken"])


class TestTradeHistory(McpMonitorTestCase):
    def test_returns_trading_deals_newest_first(self):
        result = server.trade_history("Vantage")
        self.assertEqual(result["source"], "audit_ledger")
        self.assertEqual(result["count"], 3)  # BALANCE deal excluded
        self.assertEqual([d["symbol"] for d in result["deals"]],
                         ["EURUSD", "XAUUSD", "XAUUSD"])
        self.assertEqual(set(result["deals"][0]), DEAL_FIELDS)
        self.assertPublicSafe(result)

    def test_symbol_filter_is_case_insensitive(self):
        result = server.trade_history("Vantage", symbol="eurusd")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["deals"][0]["symbol"], "EURUSD")

    def test_date_range_filter(self):
        result = server.trade_history(
            "Vantage", from_utc="2026-08-04T00:00:00+00:00",
            to_utc="2026-08-04T02:15:00+00:00")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["deals"][0]["deal_time_utc"],
                         "2026-08-04T02:00:00+00:00")

    def test_limit_is_applied(self):
        result = server.trade_history("Vantage", limit=1)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["deals"][0]["symbol"], "EURUSD")

    def test_invalid_inputs_fail_closed(self):
        for kwargs in ({"limit": 0}, {"limit": 201}, {"limit": "many"},
                       {"from_utc": "yesterday"}, {"to_utc": "2026-13-40"},
                       {"symbol": "XAU USD"}, {"symbol": "'; DROP TABLE deals;--"},
                       {"from_utc": "2026-08-04T03:00:00+00:00",
                        "to_utc": "2026-08-04T01:00:00+00:00"}):
            with self.assertRaises(ValueError, msg=str(kwargs)):
                server.trade_history("Vantage", **kwargs)

    def test_bounded_limits_on_other_reports(self):
        for limit in (0, 1001):
            with self.assertRaises(ValueError):
                server.equity_curve("Vantage", limit=limit)
        for limit in (0, 101):
            with self.assertRaises(ValueError):
                server.checkpoint_history("Vantage", limit=limit)


class TestProfileAllowlist(McpMonitorTestCase):
    def _profile_tools(self):
        return (server.account_overview, server.performance_summary,
                server.trade_history, server.equity_curve,
                server.checkpoint_history, server.risk_summary,
                server.audit_integrity)

    def test_missing_allowlist_is_a_configuration_error(self):
        os.environ.pop("OAK_MCP_PROFILES")
        for tool in self._profile_tools():
            with self.assertRaises(ValueError, msg=tool.__name__):
                tool("Vantage")

    def test_profile_outside_allowlist_is_rejected(self):
        for tool in self._profile_tools():
            for profile in ("Intruder", "", "  ", "vantage", "Vantage;Other"):
                with self.assertRaises(ValueError, msg=f"{tool.__name__}:{profile!r}"):
                    tool(profile)

    def test_surrounding_whitespace_is_normalised_not_bypassed(self):
        self.assertTrue(server.account_overview(" Vantage ")["available"])

    def test_allowlist_is_re_read_per_call(self):
        self.assertTrue(server.account_overview("Vantage")["available"])
        os.environ["OAK_MCP_PROFILES"] = "Other"
        with self.assertRaises(ValueError):
            server.account_overview("Vantage")


class TestLedgerIsNeverModified(McpMonitorTestCase):
    def _call_all_reports(self):
        server.list_accounts()
        server.account_overview("Vantage")
        server.performance_summary("Vantage")
        server.trade_history("Vantage", limit=200)
        server.equity_curve("Vantage", limit=1000)
        server.checkpoint_history("Vantage", limit=100)
        server.risk_summary("Vantage")
        server.audit_integrity("Vantage")

    def test_database_bytes_unchanged_and_no_sidecars(self):
        before = fingerprint(self.db_path)
        self._call_all_reports()
        self.assertEqual(fingerprint(self.db_path), before)
        self.assertEqual(sidecars(self.db_path), [])

    def test_connection_is_query_only_and_read_only(self):
        store = server.ReadOnlyAuditStore(self.db_path)
        try:
            self.assertIn("mode=ro", store.read_only_uri(Path(self.db_path)))
            self.assertEqual(store._conn.execute("PRAGMA query_only").fetchone()[0], 1)
            with self.assertRaises(sqlite3.OperationalError):
                store._conn.execute(
                    "INSERT INTO cash_flows (account_id, time_utc, flow_type, amount)"
                    " VALUES (1, '2026-08-05T00:00:00+00:00', 'DEPOSIT', 1.0)")
        finally:
            store.close()
        self.assertEqual(sidecars(self.db_path), [])

    def test_missing_database_fails_closed(self):
        os.environ["OAK_MCP_AUDIT_DB"] = os.path.join(self._tmp.name, "absent.db")
        with self.assertRaises(FileNotFoundError):
            server.resolve_db_path()
        with self.assertRaises(FileNotFoundError):
            server.account_overview("Vantage")

    def test_directory_is_not_accepted_as_database(self):
        os.environ["OAK_MCP_AUDIT_DB"] = self._tmp.name
        with self.assertRaises(FileNotFoundError):
            server.resolve_db_path()


class TestNoLiveBrokerSurface(unittest.TestCase):
    def test_source_has_no_broker_or_mutation_api(self):
        source = (_REPO_ROOT / "mt5_mcp_server.py").read_text(encoding="utf-8")
        for banned in ("MetaTrader5", "order_send", "profile.update", "service.start",
                       "positions.close", "TradeAuditStore", "executescript",
                       "initialize(", "login", "INSERT ", "UPDATE ", "DELETE "):
            self.assertNotIn(banned, source, f"forbidden reference: {banned}")

    def test_importing_the_server_loads_no_broker_module(self):
        """Fresh interpreter: importing the server pulls in no broker module
        and writes nothing to stdout (stdout belongs to the MCP transport)."""
        code = ("import sys, mt5_mcp_server; "
                "print([n for n in sys.modules if 'metatrader' in n.lower()])")
        proc = subprocess.run([sys.executable, "-c", code], cwd=str(_REPO_ROOT),
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "[]")

    def test_server_runs_on_stdio_transport_only(self):
        source = (_REPO_ROOT / "mt5_mcp_server.py").read_text(encoding="utf-8")
        self.assertIn('mcp.run(transport="stdio")', source)
        self.assertNotIn("streamable-http", source)
        self.assertNotIn("print(", source)


if __name__ == "__main__":
    unittest.main()
