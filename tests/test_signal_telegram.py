"""Unit test suite for send_telegram credential resolution, profile priority, and error isolation."""
from unittest.mock import MagicMock, patch
import urllib.error
import unittest
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot


class SignalTelegramTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_active_profile = mt5_signal_bot._active_profile

    def tearDown(self) -> None:
        mt5_signal_bot._active_profile = self.original_active_profile

    def test_profile_keyring_token_resolution(self) -> None:
        """Test A: profile tele_token = __vault__ resolves via keyring for active profile."""
        mt5_signal_bot._active_profile = "VantageDemo"
        mock_cfg = {"tele_token": "__vault__", "tele_chat": "123456789"}

        with (
            patch("mt5_signal_bot.load_profile_config", return_value=mock_cfg),
            patch("mt5_signal_bot.resolve_telegram_token", return_value="resolved_keyring_token") as mock_resolve,
            patch.object(mt5_signal_bot, "TELEGRAM_ADMIN_CHAT_ID", "7732907060"),
            patch("urllib.request.urlopen") as mock_urlopen,
        ):
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"ok": true}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = mt5_signal_bot.send_telegram("Hello test")

        self.assertTrue(res)
        mock_resolve.assert_called_once_with(
            "VantageDemo", "__vault__", global_fallback=mt5_signal_bot.TELEGRAM_TOKEN
        )

    def test_profile_raw_token_used_before_global_fallback(self) -> None:
        """Test B: real token in profile is resolved before global fallback."""
        mt5_signal_bot._active_profile = "VantageDemo"
        mock_cfg = {"tele_token": "profile_raw_token_999", "tele_chat": "123456789"}

        with (
            patch("mt5_signal_bot.load_profile_config", return_value=mock_cfg),
            patch("mt5_signal_bot.resolve_telegram_token", return_value="profile_raw_token_999") as mock_resolve,
            patch.object(mt5_signal_bot, "TELEGRAM_ADMIN_CHAT_ID", "7732907060"),
            patch("urllib.request.urlopen") as mock_urlopen,
        ):
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"ok": true}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = mt5_signal_bot.send_telegram("Hello raw token")

        self.assertTrue(res)
        mock_resolve.assert_called_once_with(
            "VantageDemo", "profile_raw_token_999", global_fallback=mt5_signal_bot.TELEGRAM_TOKEN
        )

    def test_global_fallback_when_profile_token_missing(self) -> None:
        """Test C: global TELEGRAM_TOKEN is used if profile has no token or keyring value."""
        mt5_signal_bot._active_profile = "VantageDemo"
        mock_cfg = {"tele_token": "", "tele_chat": "123456789"}

        with (
            patch("mt5_signal_bot.load_profile_config", return_value=mock_cfg),
            patch("mt5_signal_bot.resolve_telegram_token", return_value="global_fallback_token_123") as mock_resolve,
            patch.object(mt5_signal_bot, "TELEGRAM_ADMIN_CHAT_ID", "7732907060"),
            patch("urllib.request.urlopen") as mock_urlopen,
        ):
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"ok": true}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = mt5_signal_bot.send_telegram("Hello fallback")

        self.assertTrue(res)
        mock_resolve.assert_called_once_with(
            "VantageDemo", "", global_fallback=mt5_signal_bot.TELEGRAM_TOKEN
        )

    def test_admin_chat_id_from_config(self) -> None:
        """Test D: TELEGRAM_ADMIN_CHAT_ID from config.json is used for routing."""
        mt5_signal_bot._active_profile = "VantageDemo"
        mock_cfg = {"tele_token": "valid_token", "tele_chat": "-1001234567890"}

        with (
            patch("mt5_signal_bot.load_profile_config", return_value=mock_cfg),
            patch("mt5_signal_bot.resolve_telegram_token", return_value="valid_token"),
            patch.object(mt5_signal_bot, "TELEGRAM_ADMIN_CHAT_ID", "7732907060"),
            patch("urllib.request.urlopen") as mock_urlopen,
        ):
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"ok": true}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            mt5_signal_bot.send_telegram("Test admin chat routing")

            req = mock_urlopen.call_args[0][0]
            self.assertIn(b'"chat_id": 7732907060', req.data)
            self.assertNotIn(b'"chat_id": -1001234567890', req.data)

    def test_missing_credentials_fails_safely(self) -> None:
        """Test E: missing token or chat ID returns False without raising an exception."""
        mt5_signal_bot._active_profile = ""
        with (
            patch("mt5_signal_bot.load_profile_config", return_value={}),
            patch("mt5_signal_bot.resolve_telegram_token", return_value=""),
            patch.object(mt5_signal_bot, "TELEGRAM_ADMIN_CHAT_ID", ""),
        ):
            res = mt5_signal_bot.send_telegram("Test missing creds")

        self.assertFalse(res)

    def test_telegram_network_error_fails_safely(self) -> None:
        """Test F: network exception returns False without crashing the caller."""
        mt5_signal_bot._active_profile = "VantageDemo"
        mock_cfg = {"tele_token": "valid_token", "tele_chat": "999888777"}

        with (
            patch("mt5_signal_bot.load_profile_config", return_value=mock_cfg),
            patch("mt5_signal_bot.resolve_telegram_token", return_value="valid_token"),
            patch.object(mt5_signal_bot, "TELEGRAM_ADMIN_CHAT_ID", "7732907060"),
            patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network down")),
        ):
            res = mt5_signal_bot.send_telegram("Test network error")

        self.assertFalse(res)

    def test_startup_telegram_call_does_not_raise_typeerror(self) -> None:
        """Test G: real send_telegram call site with VantageDemo profile executes without TypeError."""
        mt5_signal_bot._active_profile = "VantageDemo"
        mock_cfg = {"tele_token": "valid_token", "tele_chat": "999888777"}

        with (
            patch("mt5_signal_bot.load_profile_config", return_value=mock_cfg),
            patch("mt5_signal_bot.resolve_telegram_token", return_value="valid_token") as mock_resolve,
            patch.object(mt5_signal_bot, "TELEGRAM_ADMIN_CHAT_ID", "7732907060"),
            patch("urllib.request.urlopen") as mock_urlopen,
        ):
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"ok": true}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            msg = mt5_signal_bot.build_startup_telegram_message(None, mt5_connected=True)
            res = mt5_signal_bot.send_telegram(msg)

        self.assertTrue(res)
        mock_resolve.assert_called_once_with(
            "VantageDemo", "valid_token", global_fallback=mt5_signal_bot.TELEGRAM_TOKEN
        )


if __name__ == "__main__":
    unittest.main()
