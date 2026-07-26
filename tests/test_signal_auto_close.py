"""Signal bot owns the two retrying ALL-position close windows."""
import json
from datetime import date, datetime
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import call, patch
import unittest

import mt5_signal_bot


class SignalAutoCloseTests(unittest.TestCase):
    def setUp(self) -> None:
        mt5_signal_bot._auto_close_completed.clear()
        mt5_signal_bot._auto_close_pending.clear()
        mt5_signal_bot._auto_close_last_attempt.clear()
        mt5_signal_bot._auto_close_last_alert.clear()

    def tearDown(self) -> None:
        mt5_signal_bot._auto_close_completed.clear()
        mt5_signal_bot._auto_close_pending.clear()
        mt5_signal_bot._auto_close_last_attempt.clear()
        mt5_signal_bot._auto_close_last_alert.clear()

    def test_weekday_cutoffs_and_prefixes(self) -> None:
        with patch.object(mt5_signal_bot, "_process_auto_close_group") as process:
            mt5_signal_bot._process_auto_closes(datetime(2026, 7, 14, 20, 0))

        self.assertEqual(
            process.call_args_list,
            [
                call(datetime(2026, 7, 14, 20, 0), "xau", (17, 59), ["XAUUSD"]),
                call(
                    datetime(2026, 7, 14, 20, 0),
                    "gbp",
                    (19, 59),
                    ["GBPAUD", "GBPCAD", "GBPJPY", "GBPUSD"],
                ),
            ],
        )

    def test_weekend_does_not_close(self) -> None:
        with patch.object(mt5_signal_bot, "_process_auto_close_group") as process:
            mt5_signal_bot._process_auto_closes(datetime(2026, 7, 18, 20, 0))

        process.assert_not_called()

    def test_before_cutoff_does_not_attempt_close(self) -> None:
        with patch.object(mt5_signal_bot, "_close_positions_by_prefix") as close:
            mt5_signal_bot._process_auto_close_group(
                datetime(2026, 7, 14, 17, 58),
                "xau",
                (17, 59),
                ["XAUUSD"],
            )

        close.assert_not_called()

    def test_prefix_close_includes_manual_and_other_ea_positions(self) -> None:
        positions = [
            SimpleNamespace(ticket=1, symbol="XAUUSD", type=0, volume=0.1, magic=0, comment="manual"),
            SimpleNamespace(ticket=2, symbol="XAUUSD.a", type=1, volume=0.2, magic=9876, comment="other EA"),
            SimpleNamespace(ticket=3, symbol="EURUSD", type=0, volume=0.3, magic=0, comment="manual"),
        ]
        result = SimpleNamespace(retcode=mt5_signal_bot.mt5.TRADE_RETCODE_DONE)

        with (
            patch.object(mt5_signal_bot, "mt5_ready", True),
            patch.object(mt5_signal_bot.mt5, "positions_get", side_effect=[positions, []]),
            patch.object(
                mt5_signal_bot.mt5,
                "symbol_info_tick",
                return_value=SimpleNamespace(bid=2000.0, ask=2000.5),
            ),
            patch.object(mt5_signal_bot.mt5, "order_send", return_value=result) as order_send,
            patch.object(
                mt5_signal_bot,
                "_get_order_filling_mode",
                return_value=getattr(mt5_signal_bot.mt5, "ORDER_FILLING_IOC", 1),
            ),
        ):
            outcome = mt5_signal_bot._close_positions_by_prefix(["XAUUSD"], "XAU-17:59")

        self.assertEqual(outcome, {"attempted": 2, "closed": 2, "remaining": 0})
        self.assertEqual(
            [request.args[0]["position"] for request in order_send.call_args_list],
            [1, 2],
        )

    def test_failure_retries_next_minute_and_only_then_persists_completion(self) -> None:
        cutoff = datetime(2026, 7, 14, 17, 59)
        next_minute = datetime(2026, 7, 14, 18, 0)
        outcomes = [
            {"attempted": 2, "closed": 1, "remaining": 1},
            {"attempted": 1, "closed": 1, "remaining": 0},
        ]

        with (
            patch.object(mt5_signal_bot, "_close_positions_by_prefix", side_effect=outcomes) as close,
            patch.object(mt5_signal_bot, "_save_state") as save,
            patch.object(mt5_signal_bot, "send_telegram"),
        ):
            mt5_signal_bot._process_auto_close_group(cutoff, "xau", (17, 59), ["XAUUSD"])
            mt5_signal_bot._process_auto_close_group(cutoff, "xau", (17, 59), ["XAUUSD"])
            self.assertNotIn((cutoff.date(), "xau"), mt5_signal_bot._auto_close_completed)
            self.assertIn((cutoff.date(), "xau"), mt5_signal_bot._auto_close_pending)
            self.assertEqual(save.call_count, 2)

            mt5_signal_bot._process_auto_close_group(next_minute, "xau", (17, 59), ["XAUUSD"])

        self.assertEqual(close.call_count, 2)
        self.assertIn((cutoff.date(), "xau"), mt5_signal_bot._auto_close_completed)
        self.assertNotIn((cutoff.date(), "xau"), mt5_signal_bot._auto_close_pending)
        self.assertEqual(save.call_count, 3)

    def test_no_positions_counts_as_completed(self) -> None:
        broker_dt = datetime(2026, 7, 14, 19, 59)

        with (
            patch.object(
                mt5_signal_bot,
                "_close_positions_by_prefix",
                return_value={"attempted": 0, "closed": 0, "remaining": 0},
            ),
            patch.object(mt5_signal_bot, "_save_state") as save,
            patch.object(mt5_signal_bot, "send_telegram") as telegram,
        ):
            mt5_signal_bot._process_auto_close_group(
                broker_dt,
                "gbp",
                (19, 59),
                ["GBPAUD", "GBPCAD", "GBPJPY", "GBPUSD"],
            )

        self.assertIn((broker_dt.date(), "gbp"), mt5_signal_bot._auto_close_completed)
        self.assertNotIn((broker_dt.date(), "gbp"), mt5_signal_bot._auto_close_pending)
        self.assertEqual(save.call_count, 2)
        telegram.assert_not_called()

    def test_previous_date_pending_state_retries_immediately_on_monday(self) -> None:
        friday = date(2026, 7, 17)
        monday = datetime(2026, 7, 20, 8, 0)

        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "bot_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "date": friday.isoformat(),
                        "day_signals": {},
                        "sent_today": [],
                        "auto_close_pending": [[friday.isoformat(), "xau"]],
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(mt5_signal_bot, "_STATE_FILE", str(state_path)),
                patch.object(mt5_signal_bot, "_trading_date", return_value=monday.date()),
            ):
                restored = mt5_signal_bot._load_state()

        obligation = (friday, "xau")
        self.assertEqual(
            restored,
            {"auto_close_pending": {obligation}, "auto_close_last_alert": {}},
        )
        mt5_signal_bot._auto_close_pending.update(restored["auto_close_pending"])

        with (
            patch.object(
                mt5_signal_bot,
                "_close_positions_by_prefix",
                return_value={"attempted": 1, "closed": 1, "remaining": 0},
            ) as close,
            patch.object(mt5_signal_bot, "_save_state") as save,
            patch.object(mt5_signal_bot, "send_telegram"),
        ):
            mt5_signal_bot._process_auto_closes(monday)

        close.assert_called_once_with(["XAUUSD"], "XAU-17:59")
        save.assert_called_once()
        self.assertNotIn(obligation, mt5_signal_bot._auto_close_pending)
        self.assertIn(obligation, mt5_signal_bot._auto_close_completed)

    def test_alert_throttle_survives_restart(self) -> None:
        broker_dt = datetime(2026, 7, 14, 18, 5)
        obligation = (broker_dt.date(), "xau")
        previous_alert = datetime(2026, 7, 14, 18, 0)
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "bot_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "date": broker_dt.date().isoformat(),
                        "day_signals": {},
                        "sent_today": [],
                        "auto_close_completed": [],
                        "auto_close_pending": [[broker_dt.date().isoformat(), "xau"]],
                        "auto_close_last_alert": [[
                            broker_dt.date().isoformat(), "xau", previous_alert.isoformat()
                        ]],
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(mt5_signal_bot, "_STATE_FILE", str(state_path)),
                patch.object(mt5_signal_bot, "_trading_date", return_value=broker_dt.date()),
            ):
                restored = mt5_signal_bot._load_state()

        mt5_signal_bot._auto_close_pending.update(restored["auto_close_pending"])
        mt5_signal_bot._auto_close_last_alert.update(restored["auto_close_last_alert"])
        with (
            patch.object(
                mt5_signal_bot,
                "_close_positions_by_prefix",
                return_value={"attempted": 1, "closed": 0, "remaining": 1},
            ),
            patch.object(mt5_signal_bot, "send_telegram") as telegram,
        ):
            mt5_signal_bot._process_auto_close_group(
                broker_dt, "xau", (17, 59), ["XAUUSD"], broker_dt.date()
            )

        telegram.assert_not_called()


if __name__ == "__main__":
    unittest.main()
