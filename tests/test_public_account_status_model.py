# -*- coding: utf-8 -*-
"""Public LIVE/DEMO status and account model must use explicit metadata only."""
import unittest

from services.audit_dashboard_publisher import AuditDashboardPublisher


class TestPublicAccountStatusModel(unittest.TestCase):
    def test_real_to_live(self):
        self.assertEqual(AuditDashboardPublisher._public_account_status({"account_type": "REAL"}), "LIVE")
        self.assertEqual(AuditDashboardPublisher._public_account_status({"account_status": "LIVE"}), "LIVE")
        self.assertEqual(AuditDashboardPublisher._public_account_status({"trade_mode": 2}), "LIVE")
        self.assertEqual(AuditDashboardPublisher._public_account_status({"is_demo": False}), "LIVE")

    def test_demo_to_demo(self):
        self.assertEqual(AuditDashboardPublisher._public_account_status({"account_type": "DEMO"}), "DEMO")
        self.assertEqual(AuditDashboardPublisher._public_account_status({"trade_mode": 0}), "DEMO")
        self.assertEqual(AuditDashboardPublisher._public_account_status({"is_demo": True}), "DEMO")

    def test_missing_unknown(self):
        self.assertEqual(AuditDashboardPublisher._public_account_status({}), "UNKNOWN")
        self.assertEqual(AuditDashboardPublisher._public_account_status({"account_type": ""}), "UNKNOWN")
        self.assertEqual(AuditDashboardPublisher._public_account_status({"account_type": "ECN"}), "UNKNOWN")

    def test_explicit_ecn_model(self):
        self.assertEqual(AuditDashboardPublisher._public_account_model({"account_model": "ECN"}), "ECN")
        self.assertEqual(AuditDashboardPublisher._public_account_model({"account_model": "STANDARD"}), "STANDARD")
        self.assertEqual(AuditDashboardPublisher._public_account_model({"account_model": "CENT"}), "CENT")

    def test_never_infer_model_from_server_or_broker(self):
        self.assertEqual(
            AuditDashboardPublisher._public_account_model(
                {"broker": "ICMarkets", "server": "ICMarketsSC-ECN", "profile_name": "VantageDemo"}
            ),
            "",
        )
        self.assertEqual(
            AuditDashboardPublisher._public_account_model({"account_type": "ECN"}),
            "",
        )

    def test_never_infer_demo_from_profile_name(self):
        self.assertEqual(
            AuditDashboardPublisher._public_account_status(
                {"profile_name": "VantageDemo", "broker": "Vantage"}
            ),
            "UNKNOWN",
        )


if __name__ == "__main__":
    unittest.main()
