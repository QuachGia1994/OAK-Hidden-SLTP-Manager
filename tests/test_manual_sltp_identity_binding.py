# -*- coding: utf-8 -*-
"""Regression: manual-position SL/TP requires bound MT5 identity."""
from __future__ import annotations

import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.mt5_terminal_service import (
    bind_live_mt5_account_identity,
    validate_mt5_mutation_session,
)
from domain.mt5_orders import send_mutation_idempotent


class FakeAccount:
    def __init__(self, login=1001, server="Broker-Demo", company="Broker Co", name="Demo"):
        self.login = login
        self.server = server
        self.company = company
        self.name = name


class FakeMT5:
    def __init__(self, login=1001, server="Broker-Demo", terminal_path=""):
        self.login = login
        self.server = server
        self.terminal_path = terminal_path
        self.order_send_calls = []

    def terminal_info(self):
        return types.SimpleNamespace(path=self.terminal_path)

    def account_info(self):
        return types.SimpleNamespace(login=self.login, server=self.server)

    def order_send(self, request):
        self.order_send_calls.append(dict(request))
        return types.SimpleNamespace(retcode=10009, order=55, comment="ok")


class TestBindLiveIdentity(unittest.TestCase):
    def test_fills_missing_login_and_server(self):
        cfg = {"path": r"C:\MT5\terminal64.exe", "profile_name": "Vantage"}
        bind_live_mt5_account_identity(cfg, FakeAccount(login=4242, server="Vantage-Demo"))
        self.assertEqual(cfg["login_id"], 4242)
        self.assertEqual(cfg["server"], "Vantage-Demo")

    def test_does_not_overwrite_configured_identity(self):
        cfg = {
            "path": r"C:\MT5\terminal64.exe",
            "login_id": 1001,
            "server": "Broker-Live",
        }
        bind_live_mt5_account_identity(cfg, FakeAccount(login=9999, server="Other"))
        self.assertEqual(cfg["login_id"], 1001)
        self.assertEqual(cfg["server"], "Broker-Live")

    def test_falls_back_to_company_when_server_missing(self):
        cfg = {"path": r"C:\MT5\terminal64.exe"}
        acc = FakeAccount(login=7, server="", company="ICMarketsSC-Demo")
        bind_live_mt5_account_identity(cfg, acc)
        self.assertEqual(cfg["login_id"], 7)
        self.assertEqual(cfg["server"], "ICMarketsSC-Demo")


class TestMutationAfterBind(unittest.TestCase):
    def _terminal(self, tmp_path: Path) -> Path:
        terminal = tmp_path / "terminal64.exe"
        terminal.write_bytes(b"fake")
        return terminal

    def test_unbound_profile_rejected_before_order_send(self):
        terminal = self._terminal(Path("."))
        # use tmp via pathlib in setUp style
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            terminal = Path(tmp) / "terminal64.exe"
            terminal.write_bytes(b"fake")
            mt5 = FakeMT5(terminal_path=str(terminal.parent))
            profile = {"path": str(terminal), "profile_name": "Vantage"}
            ok, reason = validate_mt5_mutation_session(mt5, profile)
            self.assertFalse(ok)
            self.assertEqual(reason, "MUTATION_LOGIN_REQUIRED")

            store = MagicMock()
            store.get_mutation_intent.return_value = None
            store.upsert_mutation_intent.return_value = None
            result = send_mutation_idempotent(
                {
                    "action": 6,  # TRADE_ACTION_SLTP placeholder
                    "position": 1,
                    "symbol": "XAUUSD",
                    "sl": 1.0,
                    "tp": 2.0,
                },
                "visible-sltp:Vantage:1:1.0:2.0",
                mt5_module=mt5,
                mutation_store=store,
                profile_config=profile,
            )
            self.assertEqual(result["status"], "REJECTED")
            self.assertIn("MUTATION_LOGIN_REQUIRED", result["error"])
            self.assertEqual(mt5.order_send_calls, [])

    def test_bound_identity_accepted_and_sends_sltp(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            terminal = Path(tmp) / "terminal64.exe"
            terminal.write_bytes(b"fake")
            mt5 = FakeMT5(login=1001, server="Broker-Demo", terminal_path=str(terminal.parent))
            profile = {"path": str(terminal), "profile_name": "Vantage"}
            bind_live_mt5_account_identity(profile, FakeAccount(1001, "Broker-Demo"))

            ok, reason = validate_mt5_mutation_session(mt5, profile)
            self.assertTrue(ok, reason)
            self.assertEqual(reason, "MUTATION_SESSION_OK")

            store = MagicMock()
            store.get_mutation_intent.return_value = None
            store.upsert_mutation_intent.return_value = None
            store.claim_mutation_intent.return_value = (
                {
                    "idempotency_key": "visible-sltp:Vantage:9:1.0:2.0",
                    "status": "PENDING",
                    "attempts": 0,
                },
                True,
            )

            # TRADE_ACTION_SLTP constant may not match Fake; send path only needs order_send
            with patch("domain.mt5_orders.mt5", mt5):
                result = send_mutation_idempotent(
                    {
                        "action": getattr(mt5, "TRADE_ACTION_SLTP", 6),
                        "position": 9,
                        "symbol": "XAUUSD",
                        "sl": 1.0,
                        "tp": 2.0,
                    },
                    "visible-sltp:Vantage:9:1.0:2.0",
                    mt5_module=mt5,
                    mutation_store=store,
                    profile_config=profile,
                    reconcile=lambda: None,
                )

            self.assertIn(result["status"], ("DONE", "EXISTING", "UNKNOWN", "REJECTED"))
            # Primary proof: session gate opened and order_send was attempted for valid identity.
            self.assertTrue(len(mt5.order_send_calls) >= 1)
            sent = mt5.order_send_calls[0]
            self.assertEqual(sent.get("position"), 9)
            self.assertEqual(sent.get("symbol"), "XAUUSD")

    def test_wrong_account_rejected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            terminal = Path(tmp) / "terminal64.exe"
            terminal.write_bytes(b"fake")
            mt5 = FakeMT5(login=1001, server="Broker-Demo", terminal_path=str(terminal.parent))
            profile = {
                "path": str(terminal),
                "login_id": 9999,
                "server": "Broker-Demo",
            }
            ok, reason = validate_mt5_mutation_session(mt5, profile)
            self.assertFalse(ok)
            self.assertEqual(reason, "ACCOUNT_MISMATCH")

    def test_wrong_server_rejected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            terminal = Path(tmp) / "terminal64.exe"
            terminal.write_bytes(b"fake")
            mt5 = FakeMT5(login=1001, server="Broker-Demo", terminal_path=str(terminal.parent))
            profile = {
                "path": str(terminal),
                "login_id": 1001,
                "server": "Other-Server",
            }
            ok, reason = validate_mt5_mutation_session(mt5, profile)
            self.assertFalse(ok)
            self.assertEqual(reason, "ACCOUNT_MISMATCH")

    def test_path_mismatch_rejected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            terminal = Path(tmp) / "terminal64.exe"
            terminal.write_bytes(b"fake")
            other = Path(tmp) / "other" / "terminal64.exe"
            other.parent.mkdir(parents=True, exist_ok=True)
            other.write_bytes(b"fake")
            mt5 = FakeMT5(login=1001, server="Broker-Demo", terminal_path=str(terminal.parent))
            profile = {
                "path": str(other),
                "login_id": 1001,
                "server": "Broker-Demo",
            }
            ok, reason = validate_mt5_mutation_session(mt5, profile)
            self.assertFalse(ok)
            self.assertEqual(reason, "TERMINAL_PATH_MISMATCH")


if __name__ == "__main__":
    unittest.main()
