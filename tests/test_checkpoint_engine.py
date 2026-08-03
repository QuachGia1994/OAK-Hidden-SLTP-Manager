# -*- coding: utf-8 -*-
"""Tests for the checkpoint engine (Phase 2 — section 6 & 16 semantics).

Covers:
  - §16 mandatory tests (6 exact names)
  - Supporting regression tests for Defects A, B, C
  - §6 semantics (PARTIALLY_CLOSED, close-reason never from PnL, etc.)
"""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

_workspace_root = Path(__file__).resolve().parents[1]
if str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))

from repositories.trade_audit_store import TradeAuditStore
from services.mt5_deal_reconciler import MT5DealReconciler, DEAL_REASON_SL, DEAL_REASON_TP, DEAL_REASON_CLIENT
from services.checkpoint_engine import (
    CheckpointEngine,
    previous_checkpoint,
    CHECKPOINT_HOURS,
    STILL_OPEN,
    PARTIALLY_CLOSED,
    NO_OPEN_POSITIONS,
)


# --------------------------------------------------------------------- #
# Fake MT5 — minimal stub whose history_deals_get returns canned deals.
# --------------------------------------------------------------------- #
class FakeMT5:
    def __init__(self, deals=None):
        self.deals = deals or []

    def history_deals_get(self, from_dt, to_dt):
        if self.deals is None:
            return None
        f_ts = from_dt.timestamp()
        t_ts = to_dt.timestamp()
        return [d for d in self.deals if d.time is not None and f_ts <= int(d.time) <= t_ts]


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #
def _make_account_info(**overrides):
    info = {
        "login": 12345, "server": "Vantage-Server", "currency": "USD",
        "account_type": "demo", "balance": 10000.0, "equity": 10050.0,
        "margin": 500.0, "free_margin": 9550.0, "margin_level": 2010.0,
        "open_profit": 50.0, "credit": 0.0, "profile_name": "VantageDemo",
        "broker": "Vantage",
    }
    info.update(overrides)
    return info


def _make_position(position_id="1001", symbol="XAUUSD", pos_type=0, volume=0.10,
                   price_open=2480.0, price_current=2500.0, sl=0.0, tp=0.0,
                   profit=20.0, magic=88000, comment="OAK-test"):
    return {
        "ticket": int(position_id),
        "position_id": position_id,
        "symbol": symbol,
        "type": pos_type,
        "volume": volume,
        "price_open": price_open,
        "price_current": price_current,
        "sl": sl,
        "tp": tp,
        "profit": profit,
        "magic": magic,
        "comment": comment,
    }


def _make_deal(deal_ticket, position_id, entry_type="OUT", reason_int=DEAL_REASON_SL,
               reason_category="CLOSED_SL", volume=0.10, price=2510.0, profit=30.0,
               deal_time_utc="2026-08-04T04:00:00+00:00"):
    """Return a dict suitable for store.upsert_deal (seeds deals directly)."""
    epoch = int(datetime.fromisoformat(deal_time_utc).timestamp())
    return {
        "deal_ticket": str(deal_ticket),
        "position_id": str(position_id),
        "symbol": "XAUUSD",
        "deal_type": "SELL",
        "entry_type": entry_type,
        "reason_raw": f"{reason_int}:CLOSED",
        "reason_category": reason_category,
        "volume": volume,
        "price": price,
        "profit": profit,
        "commission": -0.5,
        "swap": 0.0,
        "fee": 0.0,
        "deal_time_utc": deal_time_utc,
        "deal_time_broker": epoch,
        "magic": "88000",
        "comment": "",
    }


# --------------------------------------------------------------------- #
# Base test case — temp DB + engine setup
# --------------------------------------------------------------------- #
class CheckpointEngineTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="robot-sltp-ckpt-engine-")
        self.db_path = os.path.join(self._tmpdir.name, "trade_audit.db")
        self.store = TradeAuditStore(db_path=self.db_path, read_only=True)
        self.fake_mt5 = FakeMT5()
        self.reconciler = MT5DealReconciler(self.store, self.fake_mt5)
        self.engine = CheckpointEngine(self.store, self.reconciler)
        self.account_uid = "12345@Vantage-Server"

    def tearDown(self):
        if self.store:
            self.store.close()
        self._tmpdir.cleanup()

    def _run_ckpt(self, broker_date, checkpoint_hour, open_positions=None,
                  account_info=None, now_utc=None, deals=None):
        """Run a checkpoint, seeding any deals before execution."""
        if account_info is None:
            account_info = _make_account_info()
        if now_utc is None:
            now_utc = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        # Seed deals directly into the store so the engine can find them.
        if deals:
            account_id = self.store.upsert_account(
                account_uid=self.account_uid, profile_name="VantageDemo",
                broker="Vantage", server="Vantage-Server", currency="USD",
            )
            for d in deals:
                self.store.upsert_deal(account_id, d)
        return self.engine.run_checkpoint(
            account_uid=self.account_uid,
            broker_date=broker_date,
            checkpoint_hour=checkpoint_hour,
            account_info=account_info,
            open_positions=open_positions or [],
            now_utc=now_utc,
        )


# ===================================================================== #
# §16 MANDATORY TESTS (exact names)
# ===================================================================== #
class TestCheckpointH3OpensInterval(CheckpointEngineTestCase):
    """§16.1 — H3 opens the interval; position enters STILL_OPEN cohort."""

    def test_checkpoint_h3_opens_interval(self):
        pos = _make_position("1001", volume=0.10)
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)

        # Run H3 2026-08-04.  prev_checkpoint -> H16 2026-08-03 (does not exist).
        result = self._run_ckpt("2026-08-04", 3, open_positions=[pos], now_utc=now)

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["open_positions"], 1)

        account_id = self.store.upsert_account(
            account_uid=self.account_uid, profile_name="VantageDemo",
            broker="Vantage", server="Vantage-Server", currency="USD",
        )
        run = self.store.get_checkpoint_run(account_id, "2026-08-04", 3)
        self.assertIsNotNone(run)

        # Position 1001 captured in the H3 cohort as STILL_OPEN.
        states = self.store.list_checkpoint_position_states(run["id"])
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]["position_id"], "1001")
        self.assertEqual(states[0]["status_at_checkpoint"], STILL_OPEN)

        # Account snapshot exists.
        snapshots = self.store.list_snapshots(account_id)
        self.assertGreaterEqual(len(snapshots), 1)


class TestCheckpointH7ClosesH3Interval(CheckpointEngineTestCase):
    """§16.2 — H7 finalizes the H3 interval."""

    def test_checkpoint_h7_closes_h3_interval(self):
        pos = _make_position("1001", volume=0.10)
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)

        # 1) H3 opens interval for position 1001.
        self._run_ckpt("2026-08-04", 3, open_positions=[pos], now_utc=now)

        # 2) H7 — same position still open, no closing deal → STILL_OPEN.
        result = self._run_ckpt("2026-08-04", 7, open_positions=[pos], now_utc=now)

        account_id = self.store.upsert_account(
            account_uid=self.account_uid, profile_name="VantageDemo",
            broker="Vantage", server="Vantage-Server", currency="USD",
        )
        h3_run = self.store.get_checkpoint_run(account_id, "2026-08-04", 3)
        self.assertIsNotNone(h3_run)

        # H3 cohort finalized to STILL_OPEN (position still open, no close deal).
        h3_states = self.store.list_checkpoint_position_states(h3_run["id"])
        self.assertEqual(len(h3_states), 1)
        self.assertEqual(h3_states[0]["position_id"], "1001")
        self.assertEqual(h3_states[0]["status_at_checkpoint"], STILL_OPEN)

        # H7 run created with position 1001 in its own cohort.
        h7_run = self.store.get_checkpoint_run(account_id, "2026-08-04", 7)
        self.assertIsNotNone(h7_run)
        h7_states = self.store.list_checkpoint_position_states(h7_run["id"])
        self.assertEqual(len(h7_states), 1)
        self.assertEqual(h7_states[0]["position_id"], "1001")
        self.assertEqual(h7_states[0]["status_at_checkpoint"], STILL_OPEN)


class TestH16IntervalClosesAtNextBrokerH3(CheckpointEngineTestCase):
    """§16.3 — H16 interval finalizes at the next broker H3."""

    def test_h16_interval_closes_at_next_broker_h3(self):
        pos = _make_position("2001", volume=0.10)
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)

        # H16 2026-08-03 opens with position 2001.
        self._run_ckpt("2026-08-03", 16, open_positions=[pos], now_utc=now)

        # H3 2026-08-04 — position 2001 still open → H16 finalized as STILL_OPEN.
        result = self._run_ckpt("2026-08-04", 3, open_positions=[pos], now_utc=now)

        account_id = self.store.upsert_account(
            account_uid=self.account_uid, profile_name="VantageDemo",
            broker="Vantage", server="Vantage-Server", currency="USD",
        )
        h16_run = self.store.get_checkpoint_run(account_id, "2026-08-03", 16)
        self.assertIsNotNone(h16_run)

        h16_states = self.store.list_checkpoint_position_states(h16_run["id"])
        self.assertEqual(len(h16_states), 1)
        self.assertEqual(h16_states[0]["position_id"], "2001")
        self.assertEqual(h16_states[0]["status_at_checkpoint"], STILL_OPEN)

        # H3 cohort also captures 2001 as STILL_OPEN.
        h3_run = self.store.get_checkpoint_run(account_id, "2026-08-04", 3)
        h3_states = self.store.list_checkpoint_position_states(h3_run["id"])
        self.assertEqual(len(h3_states), 1)
        self.assertEqual(h3_states[0]["position_id"], "2001")
        self.assertEqual(h3_states[0]["status_at_checkpoint"], STILL_OPEN)


class TestNoPositionsCreatesExplicitEmptyCheckpoint(CheckpointEngineTestCase):
    """§16.4 — No open positions → NO_OPEN_POSITIONS status, never a blank card."""

    def test_no_positions_creates_explicit_empty_checkpoint(self):
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        result = self._run_ckpt("2026-08-04", 3, open_positions=[], now_utc=now)

        self.assertEqual(result["status"], NO_OPEN_POSITIONS)
        self.assertEqual(result["open_positions"], 0)

        account_id = self.store.upsert_account(
            account_uid=self.account_uid, profile_name="VantageDemo",
            broker="Vantage", server="Vantage-Server", currency="USD",
        )
        run = self.store.get_checkpoint_run(account_id, "2026-08-04", 3)
        self.assertIsNotNone(run)
        self.assertEqual(run["status"], NO_OPEN_POSITIONS)

        # Snapshot still created (explicit empty checkpoint).
        snapshots = self.store.list_snapshots(account_id)
        self.assertGreaterEqual(len(snapshots), 1)

        # No position states.
        states = self.store.list_checkpoint_position_states(run["id"])
        self.assertEqual(len(states), 0)


class TestMissedCheckpointIsPartialReconstructed(CheckpointEngineTestCase):
    """§16.5 — Missed checkpoint → PARTIAL_RECONSTRUCTED, no fake floating P/L.
    Also verifies migration v3 applied (schema_version >= 3)."""

    def test_missed_checkpoint_is_partial_reconstructed(self):
        self.assertGreaterEqual(self.store.schema_version, 3)

        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        result = self.engine.reconstruct_missed_checkpoint(
            account_uid=self.account_uid,
            broker_date="2026-08-04",
            checkpoint_hour=3,
            account_info=_make_account_info(),
            now_utc=now,
        )

        self.assertEqual(result["capture_mode"], "RECONSTRUCTED")
        self.assertEqual(result["status"], "PARTIAL_RECONSTRUCTED")

        account_id = result["account_id"]
        run = self.store.get_checkpoint_run(account_id, "2026-08-04", 3)
        self.assertIsNotNone(run)
        self.assertEqual(run["capture_mode"], "RECONSTRUCTED")
        self.assertEqual(run["status"], "PARTIAL_RECONSTRUCTED")

        # Snapshot exists but has NULL balance/equity (no fake data).
        snapshots = self.store.list_snapshots(run["id"])
        self.assertEqual(len(snapshots), 1)
        self.assertIsNone(snapshots[0]["balance"])
        self.assertIsNone(snapshots[0]["equity"])


class TestReconstructedCheckpointDoesNotFakeFloatingProfit(CheckpointEngineTestCase):
    """§16.6 — Reconstructed checkpoint never fabricates floating P/L."""

    def test_reconstructed_checkpoint_does_not_fake_floating_profit(self):
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)

        # Seed a deal so the reconstruction finds a position.
        deal = _make_deal(
            deal_ticket="9001", position_id="3001", entry_type="IN",
            reason_int=0, reason_category="", volume=0.10, price=2500.0,
            profit=0.0, deal_time_utc="2026-08-03T20:00:00+00:00",
        )
        account_id = self.store.upsert_account(
            account_uid=self.account_uid, profile_name="VantageDemo",
            broker="Vantage", server="Vantage-Server", currency="USD",
        )
        self.store.upsert_deal(account_id, deal)

        result = self.engine.reconstruct_missed_checkpoint(
            account_uid=self.account_uid,
            broker_date="2026-08-04",
            checkpoint_hour=3,
            account_info=_make_account_info(),
            now_utc=now,
        )

        run_id = result["run_id"]
        states = self.store.list_checkpoint_position_states(run_id)
        self.assertGreaterEqual(len(states), 1)
        for s in states:
            # floating_profit must be NULL — never fabricated.
            self.assertIsNone(s["floating_profit"])


# ===================================================================== #
# SUPPORTING TESTS — regression for Defect A, B, C
# ===================================================================== #
class TestPreviousCheckpointHelper(CheckpointEngineTestCase):
    """previous_checkpoint() hour mapping and boundary."""

    def test_previous_checkpoint_helper_h3_maps_to_prev_day_h16(self):
        # H3 -> (prev_date, 16)
        prev_date, prev_hour = previous_checkpoint("2026-08-04", 3)
        self.assertEqual(prev_date, "2026-08-03")
        self.assertEqual(prev_hour, 16)

        # H7 -> same date, H3 (index 1 -> index 0)
        prev_date, prev_hour = previous_checkpoint("2026-08-04", 7)
        self.assertEqual(prev_date, "2026-08-04")
        self.assertEqual(prev_hour, 3)

        # H9 -> same date, H7
        prev_date, prev_hour = previous_checkpoint("2026-08-04", 9)
        self.assertEqual(prev_date, "2026-08-04")
        self.assertEqual(prev_hour, 7)

        # Invalid hour raises ValueError.
        with self.assertRaises(ValueError):
            previous_checkpoint("2026-08-04", 13)


class TestStillOpenFinalizationDoesNotCrash(CheckpointEngineTestCase):
    """Regression for Defect A: _mark_still_open must not receive extra arg."""

    def test_still_open_finalization_does_not_crash(self):
        pos = _make_position("4001", volume=0.15)
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)

        # H3 opens interval.
        self._run_ckpt("2026-08-04", 3, open_positions=[pos], now_utc=now)

        # H7 — same position still open → _mark_still_open called.
        # Before the fix this raised TypeError (extra argument).
        result = self._run_ckpt("2026-08-04", 7, open_positions=[pos], now_utc=now)
        self.assertEqual(result["status"], "COMPLETED")

        account_id = self.store.upsert_account(
            account_uid=self.account_uid, profile_name="VantageDemo",
            broker="Vantage", server="Vantage-Server", currency="USD",
        )
        h3_run = self.store.get_checkpoint_run(account_id, "2026-08-04", 3)
        states = self.store.list_checkpoint_position_states(h3_run["id"])
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]["status_at_checkpoint"], STILL_OPEN)


class TestPartiallyClosedPosition(CheckpointEngineTestCase):
    """Regression for Defect C: PARTIALLY_CLOSED status and close info."""

    def test_partially_closed_position_is_partially_closed(self):
        pos = _make_position("5001", volume=0.20)
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        closing_deal = _make_deal(
            deal_ticket="5100", position_id="5001", entry_type="OUT",
            reason_int=DEAL_REASON_SL, reason_category="CLOSED_SL",
            volume=0.10, price=2510.0, profit=25.0,
            deal_time_utc="2026-08-04T04:00:00+00:00",
        )

        # H3 opens interval with position 5001 (volume 0.20).
        self._run_ckpt("2026-08-04", 3, open_positions=[pos],
                        now_utc=now, deals=[closing_deal])

        # H7 — position still open, closing deal exists in interval → PARTIALLY_CLOSED.
        result = self._run_ckpt("2026-08-04", 7, open_positions=[pos], now_utc=now)

        account_id = self.store.upsert_account(
            account_uid=self.account_uid, profile_name="VantageDemo",
            broker="Vantage", server="Vantage-Server", currency="USD",
        )
        h3_run = self.store.get_checkpoint_run(account_id, "2026-08-04", 3)
        self.assertIsNotNone(h3_run)

        h3_states = self.store.list_checkpoint_position_states(h3_run["id"])
        self.assertEqual(len(h3_states), 1)
        state = h3_states[0]
        self.assertEqual(state["position_id"], "5001")
        self.assertEqual(state["status_at_checkpoint"], PARTIALLY_CLOSED)
        # Close info recorded from the deal.
        self.assertEqual(state["close_price"], 2510.0)
        self.assertEqual(state["close_time_utc"], "2026-08-04T04:00:00+00:00")
        self.assertEqual(state["close_reason"], "CLOSED_SL")
        self.assertEqual(state["realized_profit_to_date"], 25.0)
        # Volume/current_price/sl/tp from the state (not from the deal).
        self.assertEqual(state["volume"], 0.20)


class TestNoDuplicatePositionStates(CheckpointEngineTestCase):
    """Regression for Defect B: upsert, not duplicate, per (run, position)."""

    def test_no_duplicate_position_states_per_run(self):
        pos = _make_position("6001", volume=0.10)
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)

        # H3 opens.
        self._run_ckpt("2026-08-04", 3, open_positions=[pos], now_utc=now)
        # H7 — same position still open, no close deal.
        self._run_ckpt("2026-08-04", 7, open_positions=[pos], now_utc=now)

        account_id = self.store.upsert_account(
            account_uid=self.account_uid, profile_name="VantageDemo",
            broker="Vantage", server="Vantage-Server", currency="USD",
        )
        h3_run = self.store.get_checkpoint_run(account_id, "2026-08-04", 3)
        states = self.store.list_checkpoint_position_states(h3_run["id"])
        # Exactly one row per position — no duplicate from finalization.
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]["position_id"], "6001")


class TestCheckpointRunIsIdempotent(CheckpointEngineTestCase):
    """Running the same checkpoint twice creates no duplicate run/position rows."""

    def test_checkpoint_run_is_idempotent(self):
        pos = _make_position("7001", volume=0.10)
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)

        # Run H3 twice — same (account, date, hour).
        self._run_ckpt("2026-08-04", 3, open_positions=[pos], now_utc=now)
        self._run_ckpt("2026-08-04", 3, open_positions=[pos], now_utc=now)

        account_id = self.store.upsert_account(
            account_uid=self.account_uid, profile_name="VantageDemo",
            broker="Vantage", server="Vantage-Server", currency="USD",
        )
        runs = self.store.list_checkpoint_runs(account_id)
        self.assertEqual(len(runs), 1)

        h3_run = self.store.get_checkpoint_run(account_id, "2026-08-04", 3)
        states = self.store.list_checkpoint_position_states(h3_run["id"])
        self.assertEqual(len(states), 1)


class TestCloseReasonNeverInferredFromPnl(CheckpointEngineTestCase):
    """Close reason from MT5 reason enum, never inferred from profit/loss."""

    def test_close_reason_never_inferred_from_pnl(self):
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        account_id = self.store.upsert_account(
            account_uid=self.account_uid, profile_name="VantageDemo",
            broker="Vantage", server="Vantage-Server", currency="USD",
        )

        # A) Losing deal with DEAL_REASON_CLIENT → CLOSED_MANUAL (not CLOSED_SL).
        pos_a = _make_position("8001", volume=0.10)
        deal_a = _make_deal(
            deal_ticket="8100", position_id="8001", entry_type="OUT",
            reason_int=DEAL_REASON_CLIENT, reason_category="CLOSED_MANUAL_DESKTOP",
            volume=0.10, price=2460.0, profit=-99.0,
            deal_time_utc="2026-08-04T04:00:00+00:00",
        )
        self._run_ckpt("2026-08-04", 3, open_positions=[pos_a],
                        now_utc=now, deals=[deal_a])
        self._run_ckpt("2026-08-04", 7, open_positions=[], now_utc=now)

        h3_run = self.store.get_checkpoint_run(account_id, "2026-08-04", 3)
        states_a = self.store.list_checkpoint_position_states(h3_run["id"])
        self.assertEqual(len(states_a), 1)
        self.assertEqual(states_a[0]["status_at_checkpoint"], "CLOSED_MANUAL")
        self.assertNotEqual(states_a[0]["status_at_checkpoint"], "CLOSED_SL")

        # B) Winning deal with DEAL_REASON_SL → CLOSED_SL, not CLOSED_TP.
        pos_b = _make_position("8002", volume=0.10)
        deal_b = _make_deal(
            deal_ticket="8200", position_id="8002", entry_type="OUT",
            reason_int=DEAL_REASON_SL, reason_category="CLOSED_SL",
            volume=0.10, price=2520.0, profit=55.0,
            deal_time_utc="2026-08-05T04:00:00+00:00",
        )
        self._run_ckpt("2026-08-05", 3, open_positions=[pos_b],
                        now_utc=now, deals=[deal_b])
        self._run_ckpt("2026-08-05", 7, open_positions=[], now_utc=now)

        h3_run_b = self.store.get_checkpoint_run(account_id, "2026-08-05", 3)
        states_b = self.store.list_checkpoint_position_states(h3_run_b["id"])
        self.assertEqual(len(states_b), 1)
        self.assertEqual(states_b[0]["status_at_checkpoint"], "CLOSED_SL")
        self.assertNotEqual(states_b[0]["status_at_checkpoint"], "CLOSED_TP")

        # C) Losing deal with DEAL_REASON_TP → CLOSED_TP, not CLOSED_SL.
        pos_c = _make_position("8003", volume=0.10)
        deal_c = _make_deal(
            deal_ticket="8300", position_id="8003", entry_type="OUT",
            reason_int=DEAL_REASON_TP, reason_category="CLOSED_TP",
            volume=0.10, price=2470.0, profit=-15.0,
            deal_time_utc="2026-08-06T04:00:00+00:00",
        )
        self._run_ckpt("2026-08-06", 3, open_positions=[pos_c],
                        now_utc=now, deals=[deal_c])
        self._run_ckpt("2026-08-06", 7, open_positions=[], now_utc=now)

        h3_run_c = self.store.get_checkpoint_run(account_id, "2026-08-06", 3)
        states_c = self.store.list_checkpoint_position_states(h3_run_c["id"])
        self.assertEqual(len(states_c), 1)
        self.assertEqual(states_c[0]["status_at_checkpoint"], "CLOSED_TP")
        self.assertNotEqual(states_c[0]["status_at_checkpoint"], "CLOSED_SL")


class TestH3SnapshotCapturesAccountState(CheckpointEngineTestCase):
    """Account snapshot persisted with all required fields."""

    def test_h3_snapshot_captures_account_state(self):
        pos = _make_position("9001", volume=0.10)
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        info = _make_account_info(
            balance=15000.0, equity=15100.0, margin=800.0,
            free_margin=14300.0, margin_level=1887.5,
        )

        self._run_ckpt("2026-08-04", 3, open_positions=[pos],
                        account_info=info, now_utc=now)

        account_id = self.store.upsert_account(
            account_uid=self.account_uid, profile_name="VantageDemo",
            broker="Vantage", server="Vantage-Server", currency="USD",
        )
        h3_run = self.store.get_checkpoint_run(account_id, "2026-08-04", 3)
        self.assertIsNotNone(h3_run)

        snapshots = self.store.list_snapshots(account_id)
        self.assertGreaterEqual(len(snapshots), 1)
        snap = snapshots[-1]
        self.assertAlmostEqual(snap["balance"], 15000.0)
        self.assertAlmostEqual(snap["equity"], 15100.0)
        self.assertAlmostEqual(snap["margin"], 800.0)
        self.assertAlmostEqual(snap["free_margin"], 14300.0)
        self.assertAlmostEqual(snap["margin_level"], 1887.5)



if __name__ == "__main__":
    unittest.main()
