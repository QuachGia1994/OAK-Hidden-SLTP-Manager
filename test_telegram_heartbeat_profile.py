# -*- coding: utf-8 -*-
"""Tests for per-profile Telegram config resolution in publish_heartbeat().

Regression coverage for: dashboard reporting "Telegram: Not configured"
even though the running profile has a tele_chat/tele_token set, because
publish_heartbeat() was reading the global config.json chat ID instead of
the profile's own tele_chat.
"""
import unittest
import os
import json
import tempfile
from unittest.mock import patch

import mt5_signal_bot
from mt5_signal_bot import load_profile_config, publish_heartbeat


class TestLoadProfileConfig(unittest.TestCase):
    """Test load_profile_config(), the helper publish_heartbeat() relies on."""

    def _write_profiles(self, data):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_returns_profile_dict_when_present(self):
        path = self._write_profiles({"VantageDemo": {"tele_chat": "12345", "tele_token": "abc"}})
        cfg = load_profile_config("VantageDemo", profiles_path=path)
        self.assertEqual(cfg.get("tele_chat"), "12345")
        self.assertEqual(cfg.get("tele_token"), "abc")

    def test_returns_empty_dict_when_profile_missing(self):
        path = self._write_profiles({"Other": {}})
        cfg = load_profile_config("VantageDemo", profiles_path=path)
        self.assertEqual(cfg, {})

    def test_returns_empty_dict_when_no_profile_name(self):
        self.assertEqual(load_profile_config(""), {})
        self.assertEqual(load_profile_config(None), {})

    def test_returns_empty_dict_when_file_missing(self):
        cfg = load_profile_config("VantageDemo", profiles_path="/nonexistent/profiles.json")
        self.assertEqual(cfg, {})


class TestPublishHeartbeatUsesProfileTelegramConfig(unittest.TestCase):
    """publish_heartbeat() must use the running profile's tele_chat/tele_token,
    not just the global config.json values."""

    def _write_profiles(self, data):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    @patch.object(mt5_signal_bot, "_store")
    @patch.object(mt5_signal_bot, "_check_telegram_api", return_value=(True, "MyBot"))
    @patch.object(mt5_signal_bot, "resolve_telegram_token")
    def test_uses_profile_tele_chat_not_global(self, mock_resolve, mock_check_api, mock_store):
        """Even if global TELEGRAM_CHAT_ID is empty, a configured profile chat
        should mark Telegram as configured."""
        path = self._write_profiles({
            "VantageDemo": {"tele_chat": "999888777", "tele_token": "__vault__"}
        })
        mock_resolve.return_value = "real-token-from-keyring"

        with patch.object(mt5_signal_bot, "TELEGRAM_CHAT_ID", ""), \
             patch.object(mt5_signal_bot, "TELEGRAM_TOKEN", ""):
            publish_heartbeat("VantageDemo", mt5_connected=False, profiles_path=path)

        mock_resolve.assert_called_once_with("VantageDemo", "__vault__", global_fallback="")
        _, kwargs = mock_store.publish_heartbeat.call_args
        self.assertTrue(kwargs["telegram_configured"])

    @patch.object(mt5_signal_bot, "_store")
    @patch.object(mt5_signal_bot, "_check_telegram_api", return_value=(False, ""))
    @patch.object(mt5_signal_bot, "resolve_telegram_token", return_value="")
    def test_falls_back_to_global_when_profile_has_no_telegram(self, mock_resolve, mock_check_api, mock_store):
        """Profile without tele_chat falls back to the global config value."""
        path = self._write_profiles({"VantageDemo": {}})

        with patch.object(mt5_signal_bot, "TELEGRAM_CHAT_ID", "global-chat"), \
             patch.object(mt5_signal_bot, "TELEGRAM_TOKEN", "global-token"):
            publish_heartbeat("VantageDemo", mt5_connected=False, profiles_path=path)

        mock_resolve.assert_called_once_with("VantageDemo", None, global_fallback="global-token")
        _, kwargs = mock_store.publish_heartbeat.call_args
        # token resolves to "" (mocked) so configured should be False here
        self.assertFalse(kwargs["telegram_configured"])


if __name__ == "__main__":
    unittest.main()
