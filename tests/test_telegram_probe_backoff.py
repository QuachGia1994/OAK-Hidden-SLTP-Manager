"""Regression tests for Telegram health probes and warning throttling."""

import socket
import unittest
from unittest.mock import Mock, patch

import mt5_signal_bot
import telegram_client


class TelegramProbeBackoffTests(unittest.TestCase):
    def setUp(self) -> None:
        mt5_signal_bot._tg_fail_streak = 0
        mt5_signal_bot._tg_last_ok_name = ""
        mt5_signal_bot._tg_last_ok_mono = 0.0
        mt5_signal_bot._tg_last_probe_mono = 0.0
        mt5_signal_bot._tg_next_probe_mono = 0.0
        mt5_signal_bot._tg_cached_api_ok = False
        mt5_signal_bot._tg_cached_bot = ""
        mt5_signal_bot._tg_probe_key = None
        mt5_signal_bot._tg_last_check_iso = ""
        telegram_client._last_network_warning_at = 0.0
        telegram_client._suppressed_network_warnings = 0

    def test_get_me_logs_one_warning_after_all_attempts(self) -> None:
        timeout_error = socket.timeout("timed out")
        with patch("telegram_client.urllib.request.urlopen", side_effect=timeout_error) as opener:
            with patch.object(telegram_client.log, "warning") as warning:
                result = telegram_client.telegram_get_me("token", retries=2, timeout=0.01)

        self.assertEqual((False, "network_error"), result)
        self.assertEqual(3, opener.call_count)
        self.assertEqual(1, warning.call_count)
        self.assertNotIn("token", str(warning.call_args))

    def test_repeated_network_warnings_are_rate_limited(self) -> None:
        with patch("telegram_client.urllib.request.urlopen", side_effect=socket.timeout("timed out")):
            with patch("telegram_client.time.monotonic", side_effect=[10.0, 20.0]):
                with patch.object(telegram_client.log, "warning") as warning:
                    telegram_client.telegram_get_me("token", retries=0)
                    telegram_client.telegram_get_me("token", retries=0)

        self.assertEqual(1, warning.call_count)

    def test_signal_heartbeat_uses_exponential_probe_backoff(self) -> None:
        profile = {"tele_token": "stored-token", "tele_chat": "123"}
        probe_times = [0.0, 10.0, 44.0, 45.0, 100.0, 134.0, 135.0]
        store = Mock()
        with patch.object(mt5_signal_bot, "_store", store):
            with patch.object(mt5_signal_bot, "load_profile_config", return_value=profile):
                with patch.object(mt5_signal_bot, "resolve_telegram_token", return_value="token"):
                    with patch.object(mt5_signal_bot, "_check_telegram_api", return_value=(False, "network_error")) as check:
                        with patch("mt5_signal_bot.time.monotonic", side_effect=probe_times):
                            for _ in probe_times:
                                mt5_signal_bot.publish_heartbeat("Demo", False)

        self.assertEqual(3, check.call_count)
        self.assertEqual(len(probe_times), store.publish_heartbeat.call_count)

    def test_profile_change_cannot_reuse_previous_bot_health(self) -> None:
        store = Mock()
        profiles = {
            "Alpha": {"tele_token": "alpha", "tele_chat": "1"},
            "Beta": {"tele_token": "beta", "tele_chat": "2"},
        }
        with patch.object(mt5_signal_bot, "_store", store):
            with patch.object(mt5_signal_bot, "load_profile_config", side_effect=lambda name, **_: profiles[name]):
                with patch.object(mt5_signal_bot, "resolve_telegram_token", side_effect=lambda name, *_args, **_kwargs: name):
                    with patch.object(
                        mt5_signal_bot,
                        "_check_telegram_api",
                        side_effect=[(True, "alpha_bot"), (False, "network_error")],
                    ):
                        with patch("mt5_signal_bot.time.monotonic", side_effect=[0.0, 1.0]):
                            mt5_signal_bot.publish_heartbeat("Alpha", False)
                            mt5_signal_bot.publish_heartbeat("Beta", False)

        beta_heartbeat = store.publish_heartbeat.call_args_list[-1].kwargs
        self.assertFalse(beta_heartbeat["telegram_api_ok"])
        self.assertEqual("network_error", beta_heartbeat["telegram_bot_name"])

    def test_health_probe_uses_one_bounded_network_attempt(self) -> None:
        with patch.object(mt5_signal_bot, "telegram_get_me", return_value=(False, "network_error")) as get_me:
            result = mt5_signal_bot._check_telegram_api("token")

        self.assertEqual((False, "network_error"), result)
        get_me.assert_called_once_with("token", retries=0, timeout=5.0)


if __name__ == "__main__":
    unittest.main()
