# -*- coding: utf-8 -*-
"""Tests for centralized Telegram token resolver."""
import unittest
from unittest.mock import patch, MagicMock


class TestTokenResolver(unittest.TestCase):
    """Test resolve_telegram_token behavior."""

    @patch("secret_store._get_keyring")
    def test_real_token_returned_as_is(self, mock_kr):
        """Real token is returned unchanged."""
        from secret_store import resolve_telegram_token
        result = resolve_telegram_token("Vantage", "123456:ABC-DEF")
        self.assertEqual(result, "123456:ABC-DEF")
        mock_kr.assert_not_called()

    @patch("secret_store._get_keyring")
    def test_vault_token_calls_keyring(self, mock_kr):
        """__vault__ token triggers keyring lookup."""
        mock_kr.return_value.get_password.return_value = "real_token_from_keyring"
        from secret_store import resolve_telegram_token
        result = resolve_telegram_token("Vantage", "__vault__")
        self.assertEqual(result, "real_token_from_keyring")
        mock_kr.return_value.get_password.assert_called()

    @patch("secret_store._get_keyring")
    def test_empty_token_calls_keyring(self, mock_kr):
        """Empty token triggers keyring lookup."""
        mock_kr.return_value.get_password.return_value = "keyring_token"
        from secret_store import resolve_telegram_token
        result = resolve_telegram_token("Vantage", "")
        self.assertEqual(result, "keyring_token")

    @patch("secret_store._get_keyring")
    def test_none_token_calls_keyring(self, mock_kr):
        """None token triggers keyring lookup."""
        mock_kr.return_value.get_password.return_value = "keyring_token"
        from secret_store import resolve_telegram_token
        result = resolve_telegram_token("Vantage", None)
        self.assertEqual(result, "keyring_token")

    @patch("secret_store._get_keyring")
    def test_missing_keyring_returns_empty(self, mock_kr):
        """Missing keyring returns empty string."""
        mock_kr.return_value.get_password.return_value = None
        from secret_store import resolve_telegram_token
        result = resolve_telegram_token("Vantage", "__vault__")
        self.assertEqual(result, "")

    def test_no_profile_returns_empty(self):
        """No profile name returns empty string."""
        from secret_store import resolve_telegram_token
        result = resolve_telegram_token("", "__vault__")
        self.assertEqual(result, "")

    @patch("secret_store._get_keyring")
    def test_never_returns_vault_string(self, mock_kr):
        """Never returns __vault__ as usable token."""
        mock_kr.return_value.get_password.return_value = None
        from secret_store import resolve_telegram_token
        result = resolve_telegram_token("Vantage", "__vault__")
        self.assertNotEqual(result, "__vault__")


if __name__ == "__main__":
    unittest.main()
