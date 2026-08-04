# -*- coding: utf-8 -*-
"""Phase 5 legacy-isolation tests (§1, §16 of the refactor plan).

- test_legacy_signal_history_is_not_mixed_with_trade_history
- test_candle_signal_engine_disabled_by_default
- test_no_mt5_copy_rates_called_in_account_audit_mode
"""
import os
import sys
import unittest
from pathlib import Path

_workspace_root = Path(__file__).resolve().parents[1]
if str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))

from legacy.candle_signal_engine import (
    legacy_candle_signals_enabled,
    LEGACY_CANDLE_SIGNALS_FLAG,
)


class TestCandleSignalEngineDisabledByDefault(unittest.TestCase):
    def test_candle_signal_engine_disabled_by_default(self):
        # Remove the flag entirely → must default to False (account audit mode).
        os.environ.pop(LEGACY_CANDLE_SIGNALS_FLAG, None)
        self.assertFalse(legacy_candle_signals_enabled())

    def test_flag_can_be_enabled_explicitly(self):
        os.environ[LEGACY_CANDLE_SIGNALS_FLAG] = "1"
        self.assertTrue(legacy_candle_signals_enabled())
        os.environ[LEGACY_CANDLE_SIGNALS_FLAG] = "true"
        self.assertTrue(legacy_candle_signals_enabled())
        os.environ.pop(LEGACY_CANDLE_SIGNALS_FLAG, None)

    def test_flag_truthy_variants(self):
        for value in ("true", "yes", "on", "1", "TRUE", "Yes"):
            os.environ[LEGACY_CANDLE_SIGNALS_FLAG] = value
            self.assertTrue(legacy_candle_signals_enabled(), value)
        for value in ("false", "0", "no", "off", ""):
            os.environ[LEGACY_CANDLE_SIGNALS_FLAG] = value
            self.assertFalse(legacy_candle_signals_enabled(), value)
        os.environ.pop(LEGACY_CANDLE_SIGNALS_FLAG, None)


class TestLegacySignalHistoryNotMixed(unittest.TestCase):
    def test_legacy_signal_history_is_not_mixed_with_trade_history(self):
        # The trade audit store must NOT contain legacy signal-history tables.
        import tempfile
        from repositories.trade_audit_store import TradeAuditStore

        with tempfile.TemporaryDirectory(prefix="robot-sltp-legacy-") as tmp:
            store = TradeAuditStore(db_path=os.path.join(tmp, "audit.db"), read_only=True)
            try:
                tables = {
                    row[0] for row in store._conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
            finally:
                store.close()
        # Legacy signal stores live in signals_log.json / oak_state.db — never here.
        self.assertNotIn("signal_history", tables)
        self.assertNotIn("d_direction", tables)
        self.assertNotIn("d_direction_history", tables)
        # The audit ledger IS present (verified trade data only).
        self.assertIn("positions", tables)
        self.assertIn("deals", tables)
        self.assertIn("checkpoint_runs", tables)

    def test_legacy_engine_source_archived_not_auto_started(self):
        # The engine source now lives under legacy/candle_signal_engine/.
        from pathlib import Path as _P
        legacy_pkg = _P(_workspace_root, "legacy", "candle_signal_engine")
        self.assertTrue(legacy_pkg.joinpath("signal_v87.py").is_file())
        self.assertTrue(legacy_pkg.joinpath("signal_rules.py").is_file())
        # Production entry point must import the flag (audit gating wired).
        import mt5_signal_bot  # noqa: F401  (import succeeds ⇒ shims work)


class TestNoCopyRatesInAuditMode(unittest.TestCase):
    def test_no_mt5_copy_rates_called_in_account_audit_mode(self):
        """With the legacy flag off, the bot startup must not call preload
        (the only copy_rates_range caller in the provider)."""
        import mt5_signal_bot

        os.environ.pop(LEGACY_CANDLE_SIGNALS_FLAG, None)
        self.assertFalse(legacy_candle_signals_enabled())

        from datetime import datetime
        from unittest.mock import MagicMock, patch

        broker_dt = datetime(2026, 7, 29, 10)
        account = MagicMock(balance=10000.0)
        calls = 0

        def broker_time():
            nonlocal calls
            calls += 1
            if calls > 2:
                raise KeyboardInterrupt("stop controlled smoke test")
            return broker_dt

        preload = MagicMock()

        with patch.object(mt5_signal_bot, "MARKET_DATA_PROVIDER", preload), \
             patch.object(mt5_signal_bot, "try_init_mt5", return_value=True), \
             patch.object(mt5_signal_bot, "mt5") as terminal, \
             patch.object(mt5_signal_bot, "get_broker_time", side_effect=broker_time), \
             patch.object(mt5_signal_bot, "_load_state", return_value={"sent_today": set()}), \
             patch.object(mt5_signal_bot, "rebuild_signals_on_startup", return_value=0), \
             patch.object(mt5_signal_bot, "calculate_all_d_directions", return_value={}), \
             patch.object(mt5_signal_bot, "reconcile_pending_signal_alerts"), \
             patch.object(mt5_signal_bot, "push_to_dashboard"), \
             patch.object(mt5_signal_bot, "push_state_to_dashboard"), \
             patch.object(mt5_signal_bot, "push_prices_to_dashboard"), \
             patch.object(mt5_signal_bot, "send_telegram", return_value=True), \
             patch.object(mt5_signal_bot, "_process_live_slot"), \
             patch.object(mt5_signal_bot, "_check_and_rebuild_after_d_ready"), \
             patch.object(mt5_signal_bot, "_save_state"), \
             patch.object(mt5_signal_bot, "publish_d_direction_daily"):
            terminal.account_info.return_value = account
            preload.get_broker_utc_offset.return_value = 3
            # data_provider_name == "MT5" is the default; preload must be gated off.
            mt5_signal_bot.main(profile_name="VantageDemo")

        # preload is the copy_rates caller — must never fire in audit mode.
        preload.preload.assert_not_called()
        preload.assert_not_called()


if __name__ == "__main__":
    unittest.main()
