"""Tests for the H=4 Vietnamese stock similarity scanner."""
from __future__ import annotations

from datetime import date, timedelta
from math import exp
import unittest

from domain.stock_scanner import (
    AfternoonPoint,
    Direction,
    H4Signal,
    ScannerPolicy,
    StockScannerError,
    StockScore,
    build_forward_samples,
    extract_h4_signals,
    score_stock,
    select_top_stocks,
    walk_forward_backtest,
)


def _weekdays(start: date, count: int) -> list[date]:
    dates: list[date] = []
    cursor = start
    while len(dates) < count:
        if cursor.weekday() < 5:
            dates.append(cursor)
        cursor += timedelta(days=1)
    return dates


def _signal_record(trading_date: date | str, direction: str, **updates: object) -> dict[str, object]:
    record: dict[str, object] = {
        "date": trading_date.isoformat() if isinstance(trading_date, date) else trading_date,
        "hour": 4,
        "logic_version": 52,
        "pair_dirs": {"XAUUSD": direction},
    }
    record.update(updates)
    return record


class H4HistoryTests(unittest.TestCase):
    def test_extracts_sorted_current_contract_h4_xau(self) -> None:
        records = [
            _signal_record("2026-07-02", "SELL"),
            _signal_record("2026-07-01", "BUY"),
            _signal_record("2026-07-03", "BUY", hour=5),
            _signal_record("bad-date", "BUY"),
        ]

        signals = extract_h4_signals(records)

        self.assertEqual([signal.trading_date.isoformat() for signal in signals], ["2026-07-01", "2026-07-02"])
        self.assertEqual([signal.direction for signal in signals], [Direction.BUY, Direction.SELL])

    def test_rejects_missing_or_stale_version_and_legacy_stock_marker(self) -> None:
        records = [
            {"date": "2026-07-01", "hour": 4, "pair_dirs": {"XAUUSD": "BUY"}},
            _signal_record("2026-07-02", "BUY", logic_version=48),
            _signal_record("2026-07-03", "BUY", pair_dirs={"Stock-DIRECTION": "BUY"}),
            _signal_record("2026-07-04", "SELL", logic_version=52),
        ]

        signals = extract_h4_signals(records)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0], H4Signal(date(2026, 7, 4), Direction.SELL))

    def test_forward_samples_stop_at_last_completed_interval(self) -> None:
        dates = _weekdays(date(2026, 7, 1), 3)
        records = [_signal_record(item, "BUY") for item in dates]
        points = [
            AfternoonPoint(dates[0], 100.0, 1_000_000),
            AfternoonPoint(dates[1], 102.0, 1_000_000),
            AfternoonPoint(dates[2], 101.0, 1_000_000),
        ]

        samples = build_forward_samples(extract_h4_signals(records), points)

        self.assertEqual(len(samples), 2)
        self.assertEqual(samples[-1].signal_date, dates[1])
        self.assertAlmostEqual(exp(samples[0].forward_return), 1.02)

    def test_missing_stock_session_does_not_bridge_two_market_sessions(self) -> None:
        dates = _weekdays(date(2026, 7, 1), 3)
        records = [_signal_record(dates[0], "BUY")]
        points = [AfternoonPoint(dates[0], 100.0), AfternoonPoint(dates[2], 102.0)]

        samples = build_forward_samples(
            extract_h4_signals(records),
            points,
            trading_calendar=dates,
        )

        self.assertEqual(samples, [])


class StockScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dates = _weekdays(date(2026, 1, 5), 26)
        self.records = []
        for index, trading_date in enumerate(self.dates[:-1]):
            direction = "BUY" if index % 2 == 0 else "SELL"
            self.records.append({
                "date": trading_date.isoformat(),
                "hour": 4,
                "logic_version": 52,
                "pair_dirs": {"XAUUSD": direction},
            })
        self.signals = extract_h4_signals(self.records)
        self.policy = ScannerPolicy(hurdle_rate=0.001)

    def _aligned_points(self, aligned: bool) -> list[AfternoonPoint]:
        price = 100.0
        points = [AfternoonPoint(self.dates[0], price, 2_000_000)]
        for signal, next_date in zip(self.signals, self.dates[1:]):
            move = 0.01 * signal.direction.value
            price *= exp(move if aligned else -move)
            points.append(AfternoonPoint(next_date, price, 2_000_000))
        return points

    def test_scores_a_perfectly_aligned_stock(self) -> None:
        score = score_stock("AAA", self.signals, self._aligned_points(True), Direction.BUY, self.policy)

        self.assertTrue(score.eligible)
        self.assertEqual(score.sample_count, 25)
        self.assertEqual(score.direction_sample_count, 13)
        self.assertEqual(score.hit_rate, 1.0)
        self.assertEqual(score.conditional_hit_rate, 1.0)
        self.assertAlmostEqual(score.conditional_edge, 0.01)
        self.assertAlmostEqual(score.r_squared, 1.0)

    def test_rejects_an_inverse_stock(self) -> None:
        score = score_stock("BAD", self.signals, self._aligned_points(False), Direction.BUY, self.policy)

        self.assertFalse(score.eligible)
        self.assertEqual(score.hit_rate, 0.0)
        self.assertIn("hit_rate", score.rejection_reasons)

    def test_rejects_unsafe_policy_values(self) -> None:
        with self.assertRaises(StockScannerError):
            ScannerPolicy(hurdle_rate=-0.001)
        with self.assertRaises(StockScannerError):
            ScannerPolicy(minimum_direction_samples=0)

    def test_rejects_non_finite_capital(self) -> None:
        with self.assertRaises(StockScannerError):
            select_top_stocks([self._score("AAA", 0.014)], Direction.BUY, capital=float("nan"))

    def test_selects_top_three_with_equal_slots(self) -> None:
        scores = [
            self._score("AAA", 0.014),
            self._score("BBB", 0.012),
            self._score("CCC", 0.010),
            self._score("DDD", 0.008),
        ]

        selection = select_top_stocks(scores, Direction.BUY, capital=90_000_000)

        self.assertEqual([item.symbol for item in selection.candidates], ["AAA", "BBB", "CCC"])
        self.assertTrue(all(item.weight == 1 / 3 for item in selection.candidates))
        self.assertTrue(all(item.capital == 30_000_000 for item in selection.candidates))
        self.assertEqual(selection.cash_weight, 0.0)
        self.assertEqual(selection.action, "BUY_OR_HOLD")
        self.assertTrue(selection.requires_user_confirmation)
        self.assertFalse(selection.orders_submitted)

    def test_keeps_an_empty_slot_in_cash(self) -> None:
        selection = select_top_stocks(
            [self._score("AAA", 0.014), self._score("BBB", 0.012)],
            Direction.SELL,
            capital=90_000_000,
        )

        self.assertEqual(len(selection.candidates), 2)
        self.assertAlmostEqual(selection.cash_weight, 1 / 3)
        self.assertEqual(selection.action, "SELL_OR_AVOID")

    def test_walk_forward_backtest_never_uses_the_current_outcome(self) -> None:
        policy = ScannerPolicy(
            window_size=3,
            minimum_direction_samples=1,
            minimum_hit_rate=2 / 3,
            minimum_conditional_hit_rate=0.5,
        )
        dates = _weekdays(date(2026, 3, 2), 9)
        records = []
        for index, trading_date in enumerate(dates[:-1]):
            direction = "BUY" if index % 2 == 0 else "SELL"
            records.append(_signal_record(trading_date, direction))
        signals = extract_h4_signals(records)
        aligned = self._points_for(dates, signals, True)
        inverse = self._points_for(dates, signals, False)

        result = walk_forward_backtest(
            signals,
            {"AAA": aligned, "BAD": inverse},
            policy=policy,
            decision_limit=3,
        )

        self.assertEqual(result.evaluated_decisions, 3)
        self.assertEqual(result.hit_rate, 1.0)
        self.assertGreater(result.mean_aligned_return, 0)
        self.assertFalse(result.orders_submitted)

    def test_backtest_rejects_an_empty_decision_limit(self) -> None:
        with self.assertRaises(StockScannerError):
            walk_forward_backtest(self.signals, {}, decision_limit=0)

    @staticmethod
    def _score(symbol: str, edge: float) -> StockScore:
        return StockScore(
            symbol=symbol,
            sample_count=25,
            direction_sample_count=12,
            hit_rate=0.8,
            conditional_hit_rate=0.75,
            mean_aligned_return=edge,
            conditional_edge=edge,
            beta=edge,
            r_squared=0.5,
            eligible=True,
        )

    @staticmethod
    def _points_for(dates: list[date], signals: list, aligned: bool) -> list[AfternoonPoint]:
        price = 100.0
        points = [AfternoonPoint(dates[0], price, 2_000_000)]
        for signal, next_date in zip(signals, dates[1:]):
            move = 0.01 * signal.direction.value
            price *= exp(move if aligned else -move)
            points.append(AfternoonPoint(next_date, price, 2_000_000))
        return points


if __name__ == "__main__":
    unittest.main()
