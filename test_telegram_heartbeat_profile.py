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

    def test_reads_oak_data_dir_profiles_when_path_omitted(self):
        """Packaged builds set OAK_DATA_DIR; the default path must follow it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, "profiles.json")
            with open(env_path, "w", encoding="utf-8") as f:
                json.dump({"VantageDemo": {"tele_chat": "from-env-root"}}, f)

            with patch.dict(os.environ, {"OAK_DATA_DIR": tmpdir}):
                self.assertEqual(mt5_signal_bot._default_profiles_path(), env_path)
                cfg = load_profile_config("VantageDemo")
                self.assertEqual(cfg.get("tele_chat"), "from-env-root")

                # An explicit path stays authoritative over OAK_DATA_DIR.
                explicit = self._write_profiles({"VantageDemo": {"tele_chat": "explicit"}})
                cfg = load_profile_config("VantageDemo", profiles_path=explicit)
                self.assertEqual(cfg.get("tele_chat"), "explicit")

    def test_default_path_falls_back_to_source_tree(self):
        """Without OAK_DATA_DIR the dev fallback beside the module is used."""
        env = dict(os.environ)
        env.pop("OAK_DATA_DIR", None)
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                mt5_signal_bot._default_profiles_path(),
                os.path.join(os.path.dirname(os.path.abspath(mt5_signal_bot.__file__)), "profiles.json"),
            )


class TestTokenMigrationTarget(unittest.TestCase):
    """Token migration must write the same file the profiles were read from."""

    def test_resolve_active_profile_passes_read_path_to_migration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "profiles.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"VantageDemo": {"tele_token": "__vault__"}}, f)

            with patch.object(mt5_signal_bot, "migrate_plaintext_tokens") as mock_migrate, \
                 patch.dict(os.environ, {"OAK_DATA_DIR": tmpdir}):
                resolved = mt5_signal_bot.resolve_active_profile("VantageDemo")

            self.assertEqual(resolved, "VantageDemo")
            _, kwargs = mock_migrate.call_args
            self.assertEqual(kwargs["profiles_path"], path)

    def test_migrate_writes_only_the_supplied_file(self):
        """With a fake keyring, migration vaults the token into the given file."""
        import secret_store

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "profiles.json")
            profiles = {"VantageDemo": {"tele_chat": "1", "tele_token": "plain-token"}}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(profiles, f)

            stored = {}

            class FakeKeyring:
                def set_password(self, service, identifier, value):
                    stored[identifier] = value

            with patch.object(secret_store, "_get_keyring", return_value=FakeKeyring()):
                migrated = secret_store.migrate_plaintext_tokens(profiles, profiles_path=path)

            self.assertEqual(migrated, 1)
            self.assertEqual(len(stored), 1)
            self.assertEqual(profiles["VantageDemo"]["tele_token"], "__vault__")
            with open(path, "r", encoding="utf-8") as f:
                on_disk = json.load(f)
            self.assertEqual(on_disk["VantageDemo"]["tele_token"], "__vault__")
            self.assertEqual(os.listdir(tmpdir), ["profiles.json"])


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
