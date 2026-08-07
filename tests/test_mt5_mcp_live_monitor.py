# -*- coding: utf-8 -*-
"""Safety tests for the live MT5 MCP prototype (``mt5_mcp_live_server``).

Nothing here touches a real terminal, a real account or a real credential:
the broker package and ``psutil`` are replaced by in-memory fakes, the profile
store is a temporary JSON file and the "terminal" is an empty temp file. The
real ``MetaTrader5`` package is installed on this machine, so every test that
enables the live gate installs the fake in ``sys.modules`` first and asserts
that the real package was never imported.
"""
import asyncio
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import mt5_mcp_live_server as server  # noqa: E402

EXPECTED_TOOLS = {"live_account_overview", "live_positions", "live_trade_history"}

ENV_KEYS = ("OAK_MCP_PROFILES_FILE", "OAK_MCP_PROFILES",
            "OAK_MCP_LIVE_ENABLED", "OAK_MCP_LIVE_REQUIRE_DEMO")

# Keys/substrings that must never reach an MCP client.
FORBIDDEN_MARKERS = (
    "login", "password", "token", "server", "company", "path", "terminal64",
    ".exe", "C:\\", "ticket", "position_id", "order", "magic", "comment",
    "external_id", "account_uid", "9001", "5001", "88000", "oak-entry",
    "Vantage-Server",
)

OVERVIEW_KEYS = {
    "profile", "available", "account_mode", "currency", "balance", "equity",
    "margin", "free_margin", "margin_level", "open_profit", "source",
    "observed_at_utc",
}
POSITION_KEYS = {
    "symbol", "direction", "volume", "open_price", "current_price", "profit",
    "sl", "tp", "open_time_utc",
}
DEAL_KEYS = {
    "symbol", "deal_type", "entry_type", "reason_category", "volume", "price",
    "profit", "commission", "swap", "fee", "deal_time_utc",
}


def epoch(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp())


class Record:
    """Attribute bag standing in for a broker named tuple."""

    def __init__(self, **fields):
        self.__dict__.update(fields)


class FakeMT5:
    """Minimal stand-in for the broker package: reads only, no side effects."""

    ACCOUNT_TRADE_MODE_DEMO = 0

    def __init__(self, account=None, positions=(), deals=()):
        self.ACCOUNT_TRADE_MODE_DEMO = FakeMT5.ACCOUNT_TRADE_MODE_DEMO
        self.account = account
        self.positions = tuple(positions)
        self.deals = tuple(deals)
        self.initialize_result = True
        self.terminal = Record(connected=True)
        self.initialize_calls = []
        self.history_calls = []
        self.shutdown_calls = 0

    def initialize(self, path=None, portable=False, **extra):
        self.initialize_calls.append({"path": path, "portable": portable, **extra})
        return self.initialize_result

    def shutdown(self):
        self.shutdown_calls += 1
        return True

    def terminal_info(self):
        return self.terminal

    def account_info(self):
        return self.account

    def positions_get(self):
        return self.positions

    def history_deals_get(self, date_from, date_to, group=None):
        self.history_calls.append((date_from, date_to, group))
        return self.deals


class FakePsutilError(Exception):
    pass


class FakePsutil:
    """``process_iter`` over a fixed, in-memory process table."""

    Error = FakePsutilError

    def __init__(self, processes=()):
        self.processes = list(processes)

    def process_iter(self, attrs=None):
        for pid, name, exe in self.processes:
            yield Record(pid=pid, info={"name": name, "exe": exe})


def demo_account(**overrides):
    fields = {
        "trade_mode": 0, "login": 12345, "server": "Vantage-Server",
        "name": "Demo Holder", "currency": "USD", "balance": 10000.0,
        "equity": 10100.0, "margin": 500.0, "margin_free": 9600.0,
        "margin_level": 2020.0, "profit": 100.0,
    }
    fields.update(overrides)
    return Record(**fields)


def sample_positions():
    return (
        Record(ticket=5001, symbol="XAUUSD", type=0, volume=0.10,
               price_open=2500.0, price_current=2512.0, profit=120.0,
               sl=2480.0, tp=2560.0, time=epoch("2026-08-04T02:00:00"),
               magic=88000, comment="oak-entry", identifier=5001),
        Record(ticket=5002, symbol="EURUSD", type=1, volume=0.20,
               price_open=1.1, price_current=1.09, profit=20.0,
               sl=0.0, tp=0.0, time=epoch("2026-08-04T03:00:00"),
               magic=88000, comment="oak-entry", identifier=5002),
    )


def sample_deals():
    return (
        Record(ticket=9001, order=7001, position_id=5001, symbol="XAUUSD",
               type=0, entry=0, reason=3, volume=0.10, price=2500.0,
               profit=0.0, commission=-0.5, swap=0.0, fee=0.0,
               time=epoch("2026-08-03T20:00:00"), magic=88000,
               comment="oak-entry", external_id="ext-1"),
        Record(ticket=9002, order=7002, position_id=5001, symbol="XAUUSD",
               type=1, entry=1, reason=5, volume=0.10, price=2525.0,
               profit=25.0, commission=-0.5, swap=-0.2, fee=0.0,
               time=epoch("2026-08-04T02:00:00"), magic=88000,
               comment="oak-entry", external_id="ext-2"),
        Record(ticket=9003, order=7003, position_id=5003, symbol="EURUSD",
               type=0, entry=0, reason=0, volume=0.20, price=1.1,
               profit=0.0, commission=-0.3, swap=0.0, fee=0.0,
               time=epoch("2026-08-04T02:30:00"), magic=88000,
               comment="oak-entry", external_id="ext-3"),
        Record(ticket=9004, order=0, position_id=0, symbol="", type=2,
               entry=0, reason=0, volume=0.0, price=0.0, profit=1000.0,
               commission=0.0, swap=0.0, fee=0.0,
               time=epoch("2026-08-01T00:00:00"), magic=0, comment="",
               external_id=""),
    )


class LiveServerTestCase(unittest.TestCase):
    """Temp profile store + fake terminal file, with full env/module cleanup."""

    def setUp(self):
        self._tmp = TemporaryDirectory(prefix="oak-mcp-live-")
        root = Path(self._tmp.name).resolve()
        self.terminal = root / "Vantage" / "terminal64.exe"
        self.terminal.parent.mkdir(parents=True)
        self.terminal.write_text("not a real terminal", encoding="utf-8")
        self.profiles_file = root / "profiles.json"
        self.write_profiles({
            "Vantage": {"path": str(self.terminal), "mt5_portable": False},
            "Other": {"path": str(self.terminal), "mt5_portable": False},
        })
        self._saved_env = {key: os.environ.get(key) for key in ENV_KEYS}
        for key in ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["OAK_MCP_PROFILES_FILE"] = str(self.profiles_file)
        os.environ["OAK_MCP_PROFILES"] = "Vantage"
        self._saved_modules = {name: sys.modules.get(name)
                               for name in ("MetaTrader5", "psutil")}
        for name in ("MetaTrader5", "psutil"):
            sys.modules.pop(name, None)

    def tearDown(self):
        # The real broker package must never have been imported by a test.
        loaded = sys.modules.get("MetaTrader5")
        self.assertTrue(loaded is None or isinstance(loaded, FakeMT5),
                        "a real broker module was imported by the test")
        for name, module in self._saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    # -- fixtures ---------------------------------------------------------- #
    def write_profiles(self, payload):
        self.profiles_file.write_text(json.dumps(payload), encoding="utf-8")

    def install_fakes(self, account=None, positions=(), deals=(), processes=None):
        fake = FakeMT5(account=account if account is not None else demo_account(),
                       positions=positions, deals=deals)
        sys.modules["MetaTrader5"] = fake
        if processes is None:
            processes = [(4242, "terminal64.exe", str(self.terminal))]
        sys.modules["psutil"] = FakePsutil(processes)
        return fake

    def enable_live(self):
        os.environ["OAK_MCP_LIVE_ENABLED"] = "1"

    def assertPublicSafe(self, payload):
        scrubbed = dict(payload)
        scrubbed.pop("observed_at_utc", None)  # nondeterministic read stamp
        blob = json.dumps(scrubbed).lower()
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker.lower(), blob, f"leaked marker: {marker}")


class TestToolSurface(unittest.TestCase):
    def test_registers_exactly_three_live_read_tools(self):
        tools = asyncio.run(server.mcp.list_tools())
        self.assertEqual({tool.name for tool in tools}, EXPECTED_TOOLS)
        self.assertEqual(len(tools), 3)

    def test_no_mutation_or_control_tool_names(self):
        names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
        for banned in ("order", "close", "open", "start", "stop", "set",
                       "update", "write", "delete", "copy", "sltp", "modify",
                       "send", "login"):
            self.assertFalse([n for n in names if banned in n], f"suspicious: {banned}")

    def test_no_tool_accepts_a_path_credential_or_terminal_argument(self):
        for tool in asyncio.run(server.mcp.list_tools()):
            properties = set((tool.inputSchema or {}).get("properties", {}))
            for banned in ("path", "db", "database", "login", "password",
                           "server", "terminal", "sql", "query", "module",
                           "account_uid", "portable"):
                self.assertNotIn(banned, properties, f"{tool.name} exposes {banned}")


class TestDisabledByDefault(LiveServerTestCase):
    def test_every_tool_is_refused_without_the_explicit_opt_in(self):
        self.assertFalse(server.live_enabled())
        for call in (lambda: server.live_account_overview("Vantage"),
                     lambda: server.live_positions("Vantage"),
                     lambda: server.live_trade_history(
                         "Vantage", "2026-08-01T00:00:00+00:00",
                         "2026-08-05T00:00:00+00:00")):
            with self.assertRaises(server.LiveAccessError) as ctx:
                call()
            self.assertIn("disabled", str(ctx.exception))

    def test_refusal_happens_before_the_broker_package_is_imported(self):
        sys.modules["psutil"] = FakePsutil(
            [(4242, "terminal64.exe", str(self.terminal))])
        with self.assertRaises(server.LiveAccessError):
            server.live_account_overview("Vantage")
        self.assertNotIn("MetaTrader5", sys.modules)

    def test_only_an_exact_one_enables_live_access(self):
        for value in ("", "0", "true", "yes", "11", " 01", "TRUE"):
            os.environ["OAK_MCP_LIVE_ENABLED"] = value
            self.assertFalse(server.live_enabled(), f"accepted {value!r}")
        os.environ["OAK_MCP_LIVE_ENABLED"] = " 1 "  # surrounding blanks only
        self.assertTrue(server.live_enabled())

    def test_demo_gate_is_on_unless_explicitly_switched_off(self):
        self.assertTrue(server.demo_required())
        for value in ("", "1", "yes", "on", "anything"):
            os.environ["OAK_MCP_LIVE_REQUIRE_DEMO"] = value
            self.assertTrue(server.demo_required(), f"relaxed by {value!r}")
        os.environ["OAK_MCP_LIVE_REQUIRE_DEMO"] = "0"
        self.assertFalse(server.demo_required())


class TestAttachGates(LiveServerTestCase):
    def setUp(self):
        super().setUp()
        self.enable_live()

    def test_profile_outside_the_allowlist_is_rejected(self):
        fake = self.install_fakes()
        for profile in ("Other", "Intruder", "", "  ", "vantage", "Vantage;Other"):
            with self.assertRaises(server.LiveAccessError, msg=repr(profile)):
                server.live_account_overview(profile)
        self.assertEqual(fake.initialize_calls, [])

    def test_missing_allowlist_is_a_configuration_error(self):
        os.environ.pop("OAK_MCP_PROFILES")
        fake = self.install_fakes()
        with self.assertRaises(server.LiveAccessError):
            server.live_account_overview("Vantage")
        self.assertEqual(fake.initialize_calls, [])

    def test_profile_absent_from_the_profile_store_is_rejected(self):
        self.write_profiles({"Other": {"path": str(self.terminal)}})
        fake = self.install_fakes()
        with self.assertRaises(server.LiveAccessError):
            server.live_account_overview("Vantage")
        self.assertEqual(fake.initialize_calls, [])

    def test_missing_profile_store_is_rejected(self):
        os.environ["OAK_MCP_PROFILES_FILE"] = str(
            Path(self._tmp.name) / "absent.json")
        fake = self.install_fakes()
        with self.assertRaises(server.LiveAccessError):
            server.live_positions("Vantage")
        self.assertEqual(fake.initialize_calls, [])

    def test_unusable_terminal_paths_are_rejected(self):
        missing = Path(self._tmp.name) / "Ghost" / "terminal64.exe"
        wrong_name = Path(self._tmp.name) / "Vantage" / "notepad.exe"
        wrong_name.write_text("x", encoding="utf-8")
        for path in ("", None, "terminal64.exe", str(missing), str(wrong_name),
                     str(self.terminal.parent)):
            self.write_profiles({"Vantage": {"path": path}})
            fake = self.install_fakes()
            with self.assertRaises(server.LiveAccessError, msg=repr(path)):
                server.live_account_overview("Vantage")
            self.assertEqual(fake.initialize_calls, [])

    def test_terminal_must_already_be_running_at_the_exact_path(self):
        other = Path(self._tmp.name) / "Other" / "terminal64.exe"
        other.parent.mkdir()
        other.write_text("x", encoding="utf-8")
        for processes in ([],
                          [(1, "notepad.exe", str(self.terminal))],
                          [(2, "terminal64.exe", str(other))],
                          [(3, "terminal64.exe", None)]):
            fake = self.install_fakes(processes=processes)
            with self.assertRaises(server.LiveAccessError) as ctx:
                server.live_account_overview("Vantage")
            self.assertIn("not running", str(ctx.exception))
            self.assertEqual(fake.initialize_calls, [])

    def test_process_inspection_failure_fails_closed(self):
        fake = FakeMT5(account=demo_account())
        sys.modules["MetaTrader5"] = fake
        sys.modules.pop("psutil", None)
        sys.modules["psutil"] = None  # import psutil -> ImportError
        with self.assertRaises(server.LiveAccessError) as ctx:
            server.live_account_overview("Vantage")
        self.assertIn("process inspection", str(ctx.exception))
        self.assertEqual(fake.initialize_calls, [])

    def test_attach_failure_is_reported_without_broker_details(self):
        fake = self.install_fakes()
        fake.initialize_result = False
        with self.assertRaises(server.LiveAccessError) as ctx:
            server.live_account_overview("Vantage")
        self.assertEqual(str(ctx.exception), "could not attach to the running terminal")
        self.assertEqual(fake.shutdown_calls, 1)

    def test_missing_terminal_or_account_state_is_refused(self):
        fake = self.install_fakes()
        fake.terminal = None
        with self.assertRaises(server.LiveAccessError):
            server.live_account_overview("Vantage")
        fake = self.install_fakes(account=None)
        fake.account = None
        with self.assertRaises(server.LiveAccessError):
            server.live_account_overview("Vantage")
        self.assertEqual(fake.shutdown_calls, 1)

    def test_non_demo_accounts_are_rejected_by_default(self):
        for trade_mode in (1, 2, None, "real"):
            fake = self.install_fakes(account=demo_account(trade_mode=trade_mode))
            with self.assertRaises(server.LiveAccessError) as ctx:
                server.live_account_overview("Vantage")
            self.assertIn("demo", str(ctx.exception))
            self.assertEqual(fake.shutdown_calls, 1)

    def test_login_and_server_hints_must_match_the_attached_account(self):
        for hints in ({"login_id": 99999}, {"login": 99999},
                      {"server": "OtherBroker-Live"}):
            profile = {"path": str(self.terminal), "mt5_portable": False}
            profile.update(hints)
            self.write_profiles({"Vantage": profile})
            fake = self.install_fakes()
            with self.assertRaises(server.LiveAccessError) as ctx:
                server.live_account_overview("Vantage")
            self.assertIn("does not match", str(ctx.exception))
            self.assertEqual(fake.shutdown_calls, 1)

    def test_matching_hints_are_accepted(self):
        self.write_profiles({"Vantage": {"path": str(self.terminal),
                                         "login_id": 12345,
                                         "server": "Vantage-Server"}})
        fake = self.install_fakes()
        result = server.live_account_overview("Vantage")
        self.assertTrue(result["available"])
        self.assertEqual(fake.shutdown_calls, 1)

    def test_attach_is_read_only_and_uses_the_configured_portable_flag(self):
        self.write_profiles({"Vantage": {"path": str(self.terminal),
                                         "mt5_portable": True}})
        fake = self.install_fakes()
        server.live_account_overview("Vantage")
        self.assertEqual(fake.initialize_calls,
                         [{"path": str(self.terminal), "portable": True}])
        self.assertEqual(fake.shutdown_calls, 1)


class TestLiveReads(LiveServerTestCase):
    def setUp(self):
        super().setUp()
        self.enable_live()
        self.fake = self.install_fakes(positions=sample_positions(),
                                       deals=sample_deals())

    def test_account_overview_is_sanitised_and_demo_labelled(self):
        result = server.live_account_overview("Vantage")
        self.assertEqual(set(result), OVERVIEW_KEYS)
        self.assertEqual(result["profile"], "Vantage")
        self.assertTrue(result["available"])
        self.assertEqual(result["account_mode"], "DEMO")
        self.assertEqual(result["source"], "mt5_live")
        self.assertEqual(result["currency"], "USD")
        self.assertEqual(result["balance"], 10000.0)
        self.assertEqual(result["equity"], 10100.0)
        self.assertEqual(result["free_margin"], 9600.0)
        self.assertEqual(result["open_profit"], 100.0)
        self.assertIsNotNone(server._parse_utc(result["observed_at_utc"]))
        self.assertNotIn("data_age_seconds", result)
        self.assertPublicSafe(result)
        self.assertEqual(self.fake.shutdown_calls, 1)

    def test_positions_expose_market_facts_only(self):
        result = server.live_positions("Vantage")
        self.assertEqual(set(result), {"profile", "available", "account_mode",
                                       "count", "positions", "source",
                                       "observed_at_utc"})
        self.assertEqual(result["count"], 2)
        self.assertEqual(set(result["positions"][0]), POSITION_KEYS)
        self.assertEqual([p["symbol"] for p in result["positions"]],
                         ["XAUUSD", "EURUSD"])
        self.assertEqual([p["direction"] for p in result["positions"]],
                         ["BUY", "SELL"])
        self.assertEqual(result["positions"][0]["open_time_utc"],
                         "2026-08-04T02:00:00+00:00")
        self.assertEqual(result["positions"][0]["sl"], 2480.0)
        self.assertPublicSafe(result)
        self.assertEqual(self.fake.shutdown_calls, 1)

    def test_genuinely_empty_responses_stay_successful(self):
        self.fake.positions = ()
        self.fake.deals = []
        positions = server.live_positions("Vantage")
        self.assertTrue(positions["available"])
        self.assertEqual(positions["count"], 0)
        self.assertEqual(positions["positions"], [])
        history = server.live_trade_history(
            "Vantage", "2026-08-01T00:00:00+00:00", "2026-08-05T00:00:00+00:00")
        self.assertTrue(history["available"])
        self.assertEqual(history["count"], 0)
        self.assertEqual(history["deals"], [])
        self.assertEqual(self.fake.shutdown_calls, 2)

    def test_a_failed_positions_read_is_not_reported_as_empty(self):
        self.fake.positions = None  # the broker API signals an error with None
        with self.assertRaises(server.LiveAccessError) as ctx:
            server.live_positions("Vantage")
        self.assertEqual(str(ctx.exception), "live positions read failed")
        self.assertEqual(self.fake.shutdown_calls, 1)

    def test_a_failed_history_read_is_not_reported_as_empty(self):
        self.fake.deals = None  # the broker API signals an error with None
        with self.assertRaises(server.LiveAccessError) as ctx:
            server.live_trade_history("Vantage", "2026-08-01T00:00:00+00:00",
                                      "2026-08-05T00:00:00+00:00")
        self.assertEqual(str(ctx.exception), "live history read failed")
        self.assertEqual(self.fake.shutdown_calls, 1)

    def test_history_is_bounded_sanitised_and_newest_first(self):
        result = server.live_trade_history(
            "Vantage", "2026-08-01T00:00:00+00:00", "2026-08-05T00:00:00+00:00")
        self.assertEqual(set(result), {"profile", "available", "account_mode",
                                       "count", "deals", "source",
                                       "observed_at_utc"})
        self.assertEqual(result["count"], 3)  # the BALANCE deal is dropped
        self.assertEqual(set(result["deals"][0]), DEAL_KEYS)
        self.assertEqual([d["symbol"] for d in result["deals"]],
                         ["EURUSD", "XAUUSD", "XAUUSD"])
        self.assertEqual([d["deal_type"] for d in result["deals"]],
                         ["BUY", "SELL", "BUY"])
        self.assertEqual(result["deals"][1]["entry_type"], "OUT")
        self.assertEqual(result["deals"][1]["reason_category"], "TP")
        self.assertEqual(result["deals"][2]["reason_category"], "EXPERT")
        self.assertEqual(result["deals"][0]["deal_time_utc"],
                         "2026-08-04T02:30:00+00:00")
        self.assertPublicSafe(result)
        self.assertEqual(self.fake.shutdown_calls, 1)

    def test_unknown_reason_codes_degrade_to_unknown(self):
        self.fake.deals = (Record(symbol="XAUUSD", type=0, entry=99, reason=42,
                                  volume=0.1, price=1.0, profit=0.0,
                                  commission=0.0, swap=0.0, fee=0.0,
                                  time=epoch("2026-08-04T02:00:00")),)
        deal = server.live_trade_history(
            "Vantage", "2026-08-01T00:00:00+00:00",
            "2026-08-05T00:00:00+00:00")["deals"][0]
        self.assertEqual(deal["reason_category"], "UNKNOWN")
        self.assertEqual(deal["entry_type"], "UNKNOWN")

    def test_history_limit_and_symbol_filter(self):
        result = server.live_trade_history(
            "Vantage", "2026-08-01T00:00:00+00:00",
            "2026-08-05T00:00:00+00:00", limit=1)
        self.assertEqual(result["count"], 1)
        result = server.live_trade_history(
            "Vantage", "2026-08-01T00:00:00+00:00",
            "2026-08-05T00:00:00+00:00", symbol="xauusd")
        self.assertEqual(result["count"], 2)
        self.assertEqual(self.fake.history_calls[-1][2], "XAUUSD")
        self.assertEqual(self.fake.history_calls[0][2], "*")

    def test_history_bounds_are_forwarded_as_utc_datetimes(self):
        server.live_trade_history("Vantage", "2026-08-01T00:00:00+00:00",
                                  "2026-08-05T00:00:00+00:00")
        start, end, _group = self.fake.history_calls[0]
        self.assertEqual(start, datetime(2026, 8, 1, tzinfo=timezone.utc))
        self.assertEqual(end, datetime(2026, 8, 5, tzinfo=timezone.utc))

    def test_history_rejects_invalid_windows_before_touching_the_terminal(self):
        for args, kwargs in (
            (("Vantage", "", "2026-08-05T00:00:00+00:00"), {}),
            (("Vantage", "2026-08-01T00:00:00+00:00", ""), {}),
            (("Vantage", "yesterday", "2026-08-05T00:00:00+00:00"), {}),
            (("Vantage", "2026-08-01T00:00:00+00:00", "2026-13-40"), {}),
            (("Vantage", "2026-08-05T00:00:00+00:00",
              "2026-08-01T00:00:00+00:00"), {}),
            (("Vantage", "2026-07-01T00:00:00+00:00",
              "2026-08-05T00:00:00+00:00"), {}),  # 35 days
            (("Vantage", "2026-08-01T00:00:00+00:00",
              "2026-08-05T00:00:00+00:00"), {"limit": 0}),
            (("Vantage", "2026-08-01T00:00:00+00:00",
              "2026-08-05T00:00:00+00:00"), {"limit": 201}),
            (("Vantage", "2026-08-01T00:00:00+00:00",
              "2026-08-05T00:00:00+00:00"), {"limit": "many"}),
            (("Vantage", "2026-08-01T00:00:00+00:00",
              "2026-08-05T00:00:00+00:00"), {"symbol": "XAU USD"}),
            (("Vantage", "2026-08-01T00:00:00+00:00",
              "2026-08-05T00:00:00+00:00"),
             {"symbol": "'; DROP TABLE deals;--"}),
        ):
            with self.assertRaises(ValueError, msg=f"{args}{kwargs}"):
                server.live_trade_history(*args, **kwargs)
        self.assertEqual(self.fake.initialize_calls, [])
        self.assertEqual(self.fake.history_calls, [])

    def test_exactly_31_days_is_accepted(self):
        result = server.live_trade_history(
            "Vantage", "2026-07-05T00:00:00+00:00", "2026-08-05T00:00:00+00:00")
        self.assertTrue(result["available"])

    def test_the_session_shuts_down_after_every_read(self):
        server.live_account_overview("Vantage")
        server.live_positions("Vantage")
        server.live_trade_history("Vantage", "2026-08-01T00:00:00+00:00",
                                  "2026-08-05T00:00:00+00:00")
        self.assertEqual(self.fake.shutdown_calls, 3)
        self.assertEqual(len(self.fake.initialize_calls), 3)


class TestSourceHasNoTradingSurface(unittest.TestCase):
    def setUp(self):
        self.source = (_REPO_ROOT / "mt5_mcp_live_server.py").read_text(
            encoding="utf-8")

    def test_no_trading_control_or_launch_api_is_referenced(self):
        for banned in ("order_send", "order_check", "mt5.login", "positions_close",
                       "ensure_mt5_profile_connected", "subprocess", "Popen",
                       "os.system", "os.startfile", "TradeAuditStore",
                       "sqlite3", "print("):
            self.assertNotIn(banned, self.source, f"forbidden reference: {banned}")

    def test_broker_package_is_imported_only_inside_the_guarded_session(self):
        imports = [line.strip() for line in self.source.splitlines()
                   if "import MetaTrader5" in line]
        self.assertEqual(len(imports), 1)
        self.assertTrue(imports[0].startswith("import MetaTrader5 as mt5"))
        for line in self.source.splitlines():
            if "import MetaTrader5" in line:
                self.assertTrue(line.startswith("        "),
                                "the broker import must not run at module level")

    def test_importing_the_server_loads_no_broker_module(self):
        """Fresh interpreter: importing the server pulls in no broker module."""
        code = ("import sys, mt5_mcp_live_server; "
                "print([n for n in sys.modules if 'metatrader' in n.lower()])")
        proc = subprocess.run([sys.executable, "-c", code], cwd=str(_REPO_ROOT),
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "[]")

    def test_server_runs_on_stdio_transport_only(self):
        self.assertIn('mcp.run(transport="stdio")', self.source)
        self.assertNotIn("streamable-http", self.source)


class TestOpencodeConfig(unittest.TestCase):
    def setUp(self):
        self.path = _REPO_ROOT / ".opencode" / "opencode.json"
        self.config = json.loads(self.path.read_text(encoding="utf-8"))

    def test_config_parses_and_declares_the_schema(self):
        self.assertEqual(self.config["$schema"], "https://opencode.ai/config.json")
        self.assertEqual(set(self.config["mcp"]), {"oak-mt5-audit", "oak-mt5-live"})

    def test_audit_server_is_enabled_and_ledger_only(self):
        audit = self.config["mcp"]["oak-mt5-audit"]
        self.assertEqual(audit["type"], "local")
        self.assertEqual(audit["command"], ["python", "mt5_mcp_server.py"])
        self.assertTrue(audit["enabled"])
        self.assertEqual(audit["environment"]["OAK_MCP_AUDIT_DB"],
                         "data/trade_audit.db")
        self.assertNotIn("OAK_MCP_LIVE_ENABLED", audit["environment"])

    def test_live_server_is_enabled_and_real_allowed(self):
        live = self.config["mcp"]["oak-mt5-live"]
        self.assertEqual(live["type"], "local")
        self.assertEqual(live["command"], ["python", "mt5_mcp_live_server.py"])
        self.assertTrue(live["enabled"])
        self.assertEqual(live["environment"]["OAK_MCP_LIVE_ENABLED"], "1")
        self.assertEqual(live["environment"]["OAK_MCP_LIVE_REQUIRE_DEMO"], "0")
        self.assertEqual(live["environment"]["OAK_MCP_PROFILES_FILE"],
                         "profiles.json")

    def test_config_carries_no_secret_or_machine_specific_value(self):
        blob = self.path.read_text(encoding="utf-8").lower()
        for marker in ("password", "token", "secret", "api_key", "apikey",
                       "login", "terminal64", ".exe", "c:\\", "users\\"):
            self.assertNotIn(marker, blob, f"leaked marker: {marker}")


if __name__ == "__main__":
    unittest.main()
