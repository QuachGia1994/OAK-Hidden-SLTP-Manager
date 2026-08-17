import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

APP = Path(__file__).resolve().parents[1] / "robot-sltp-pro"
sys.path.insert(0, str(APP))

from ctrader_cloud_config import CTraderCloudConfig, authorization_url


class CTraderCloudConfigTests(unittest.TestCase):
    def test_status_never_returns_secrets(self):
        env = {
            "OAK_CTRADER_CLIENT_ID": "client-id-value",
            "OAK_CTRADER_CLIENT_SECRET": "client-secret-value",
            "OAK_CTRADER_ACCESS_TOKEN": "access-token-value",
            "OAK_CTRADER_REFRESH_TOKEN": "refresh-token-value",
            "OAK_CTRADER_ACCOUNT_ID": "12345",
            "OAK_CTRADER_ENV": "live",
        }
        with patch.dict(os.environ, env, clear=False):
            status = CTraderCloudConfig.from_env().status()
        self.assertTrue(status["configured"])
        self.assertTrue(status["refreshTokenConfigured"])
        rendered = repr(status)
        self.assertNotIn("client-secret-value", rendered)
        self.assertNotIn("access-token-value", rendered)
        self.assertNotIn("refresh-token-value", rendered)

    def test_missing_fields_fail_readiness(self):
        names = [
            "OAK_CTRADER_CLIENT_ID",
            "OAK_CTRADER_CLIENT_SECRET",
            "OAK_CTRADER_ACCESS_TOKEN",
            "OAK_CTRADER_REFRESH_TOKEN",
            "OAK_CTRADER_ACCOUNT_ID",
        ]
        with patch.dict(os.environ, {name: "" for name in names}, clear=False):
            status = CTraderCloudConfig.from_env().status()
        self.assertFalse(status["configured"])
        self.assertIn("OAK_CTRADER_ACCOUNT_ID", status["missing"])

    def test_from_mapping_accepts_control_plane_shape(self):
        config = CTraderCloudConfig.from_mapping({
            "clientId": "client",
            "clientSecret": "secret",
            "accessToken": "access",
            "accountId": 987,
            "environment": "demo",
            "broker": "ICMarkets",
        })
        self.assertEqual(config.account_id, 987)
        self.assertEqual(config.environment, "demo")
        self.assertEqual(config.missing_for_market_data(), ())

    def test_control_plane_uses_api_key_header_and_never_needs_refresh_token(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.read.return_value = (
            b'{"ok":true,"clientId":"client","clientSecret":"secret",'
            b'"accessToken":"access","accountId":123,"environment":"demo",'
            b'"broker":"ICMarkets"}'
        )
        with patch("ctrader_cloud_config.urlopen", return_value=response) as mocked:
            config = CTraderCloudConfig.from_control_plane(
                "https://www.oakgatekeeper.uk/api/ctrader/session",
                "dashboard-key",
            )
        request = mocked.call_args.args[0]
        self.assertEqual(request.get_header("X-api-key"), "dashboard-key")
        self.assertEqual(config.access_token, "access")
        self.assertEqual(config.refresh_token, "")

    def test_authorization_url_uses_accounts_or_trading_scope(self):
        read_url = authorization_url("client", "https://example.com/callback")
        trade_url = authorization_url("client", "https://example.com/callback", trading=True)
        self.assertIn("scope=accounts", read_url)
        self.assertIn("scope=trading", trade_url)
        self.assertNotIn("secret", read_url)


if __name__ == "__main__":
    unittest.main()
