import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from domain.signal_v87 import build_entry_plan, evaluate_slot, final_reverse


class FixtureProvider:
    name = "MT4"

    def __init__(self):
        self.bars = {}

    def add(self, symbol, timeframe, opening, opening_price, closing_price):
        self.bars[(symbol, timeframe, opening)] = {
            "broker_dt": opening,
            "open": float(opening_price),
            "high": max(float(opening_price), float(closing_price)),
            "low": min(float(opening_price), float(closing_price)),
            "close": float(closing_price),
            "open_exact": str(opening_price),
            "close_exact": str(closing_price),
            "is_complete": True,
        }

    def get_exact_bar(self, symbol, timeframe, opening):
        return self.bars.get((symbol, timeframe, opening))


def add_m30_layer(provider, slot_dt, directions, layer3=False):
    opens = (slot_dt, slot_dt - timedelta(minutes=30), slot_dt - timedelta(minutes=60)) if layer3 else (
        slot_dt - timedelta(minutes=30), slot_dt - timedelta(minutes=60), slot_dt - timedelta(minutes=90)
    )
    for opening, direction in zip(opens, directions):
        provider.add("XAUUSD", "M30", opening, 2 if direction == "GIAM" else 1, 1 if direction == "GIAM" else 2)


class TestSignalV87Core(unittest.TestCase):
    def test_common_m30_entry_is_shared_and_xau_d_relation_stays_visible(self):
        provider = FixtureProvider()
        slot_dt = datetime(2026, 8, 3, 7)
        # GIAM/TANG/GIAM is BT, selecting H:11.
        add_m30_layer(provider, slot_dt, ("GIAM", "TANG", "GIAM"))
        snapshot = {
            "XAUUSD": {"d_direction": "BUY"},
            "GBPUSD": {"d_direction": "SELL"},
            "GBPAUD": {"d_direction": "SELL"},
            "GBPJPY": {"d_direction": "BUY"},
            "GBPCAD": {"d_direction": "SELL"},
        }
        result = evaluate_slot(slot_dt, 7, provider, snapshot)
        self.assertEqual(result["entry_time"], "07:11")
        self.assertEqual(set(result["pair_entry_times"].values()), {"07:11"})
        self.assertEqual(result["signal"], "SELL")
        self.assertEqual(result["pair_d_relations"]["XAUUSD"], "OPPOSITE_TO_REFERENCE")
        self.assertEqual(result["pair_dirs"]["XAUUSD"], result["pair_dirs"]["GBPUSD"])

    def test_h16_layers(self):
        provider = FixtureProvider()
        slot_dt = datetime(2026, 8, 3, 16)
        for opening, direction in zip((5, 4, 3), ("GIAM", "TANG", "GIAM")):
            provider.add("XAUUSD", "H1", slot_dt.replace(hour=opening), 2 if direction == "GIAM" else 1, 1 if direction == "GIAM" else 2)
        self.assertEqual(build_entry_plan(slot_dt, 16, provider)["entry_time"], "16:11")

    def test_m30_layer3_waits_until_the_h00_candle_closes(self):
        provider = FixtureProvider()
        slot_dt = datetime(2026, 8, 3, 7)
        add_m30_layer(provider, slot_dt, ("TANG", "TANG", "TANG"))
        provider.add("XAUUSD", "M30", slot_dt, 1, 2)
        self.assertEqual(build_entry_plan(slot_dt, 7, provider, slot_dt)["entry_state"], "PENDING_LAYER3")
        self.assertEqual(build_entry_plan(slot_dt, 7, provider, slot_dt + timedelta(minutes=30))["entry_time"], "07:49")

    def test_missing_mt4_layer_is_explicitly_fail_closed(self):
        provider = FixtureProvider()
        slot_dt = datetime(2026, 8, 3, 7)
        plan = build_entry_plan(slot_dt, 7, provider, slot_dt + timedelta(minutes=30))
        self.assertEqual(plan["entry_state"], "WAIT")
        self.assertEqual(plan["failure_reason"], "WAIT_MT4_DATA")

    def test_h7_layer2_doji_or_missing_never_falls_through_to_layer3(self):
        slot_dt = datetime(2026, 8, 3, 7)
        for state in ("DOJI", "MISSING"):
            with self.subTest(state=state):
                provider = FixtureProvider()
                # Layer 2: TANG / GIAM / unresolved.  Layer 3 would be
                # TANG / TANG / GIAM (BT) if it were incorrectly consulted.
                provider.add("XAUUSD", "M30", slot_dt - timedelta(minutes=30), 1, 2)
                provider.add("XAUUSD", "M30", slot_dt - timedelta(minutes=60), 2, 1)
                if state == "DOJI":
                    provider.add("XAUUSD", "M30", slot_dt - timedelta(minutes=90), 1, 1)
                provider.add("XAUUSD", "M30", slot_dt, 1, 2)

                plan = build_entry_plan(slot_dt, 7, provider, slot_dt + timedelta(minutes=30))

                self.assertEqual(plan["entry_state"], "WAIT")
                self.assertIsNone(plan["entry_time"])
                self.assertIsNone(plan["layer3"])

    def test_h16_layer2_doji_or_missing_never_falls_through_to_layer3(self):
        slot_dt = datetime(2026, 8, 3, 16)
        for state in ("DOJI", "MISSING"):
            with self.subTest(state=state):
                provider = FixtureProvider()
                # Layer 2: TANG / GIAM / unresolved.  Layer 3 would be
                # TANG / TANG / GIAM (BT) if it were incorrectly consulted.
                provider.add("XAUUSD", "H1", slot_dt.replace(hour=5), 1, 2)
                provider.add("XAUUSD", "H1", slot_dt.replace(hour=4), 2, 1)
                if state == "DOJI":
                    provider.add("XAUUSD", "H1", slot_dt.replace(hour=3), 1, 1)
                provider.add("XAUUSD", "H1", slot_dt.replace(hour=10), 1, 2)
                provider.add("XAUUSD", "H1", slot_dt.replace(hour=9), 1, 2)
                provider.add("XAUUSD", "H1", slot_dt.replace(hour=8), 2, 1)

                plan = build_entry_plan(slot_dt, 16, provider, slot_dt)

                self.assertEqual(plan["entry_state"], "WAIT")
                self.assertIsNone(plan["entry_time"])
                self.assertIsNone(plan["layer3"])

    def test_pending_layer3_cannot_reverse_reference_d_from_an_existing_day_mode(self):
        provider = FixtureProvider()
        slot_dt = datetime(2026, 8, 3, 7)
        add_m30_layer(provider, slot_dt, ("TANG", "TANG", "TANG"))
        snapshot = {symbol: {"d_direction": "BUY"} for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")}

        result = evaluate_slot(
            slot_dt,
            7,
            provider,
            snapshot,
            day_mode=SimpleNamespace(source_branch="H_11"),
            as_of=slot_dt,
        )

        self.assertEqual(result["entry_state"], "PENDING_LAYER3")
        self.assertEqual(result["signal"], "WAIT")
        self.assertEqual(result["core_signal"], "WAIT")

    def test_h49_xau_reference_does_not_report_missing_gbp_d_as_its_own_failure(self):
        provider = FixtureProvider()
        slot_dt = datetime(2026, 8, 3, 7)
        # Both M30 layers are SW, selecting the H:49 exception branch.
        add_m30_layer(provider, slot_dt, ("TANG", "TANG", "TANG"))
        provider.add("XAUUSD", "M30", slot_dt, 1, 2)
        provider.add("XAUUSD", "H1", slot_dt - timedelta(hours=1), 1, 2)
        snapshot = {"XAUUSD": {"d_direction": "BUY"}}

        result = evaluate_slot(
            slot_dt,
            7,
            provider,
            snapshot,
            as_of=slot_dt + timedelta(minutes=30),
        )

        self.assertEqual(result["entry_time"], "07:49")
        self.assertEqual(result["signal"], "SELL")
        self.assertIsNone(result["failure_reason"])
        self.assertIsNone(result["pair_evidence"]["XAUUSD"]["failure_reason"])
        self.assertEqual(result["pair_dirs"]["GBPAUD"], "WAIT")
        self.assertEqual(result["pair_evidence"]["GBPAUD"]["failure_reason"], "WAIT_MT4_DATA")

    def test_final_reverse_matrix_sample(self):
        self.assertEqual(final_reverse(3, datetime(2026, 8, 5).date()), (True, "H3_WEDNESDAY"))
        self.assertEqual(final_reverse(3, datetime(2026, 8, 6).date()), (True, "H3_THURSDAY"))
        self.assertEqual(final_reverse(16, datetime(2026, 8, 14).date()), (True, "H16_FRIDAY"))


if __name__ == "__main__":
    unittest.main()
