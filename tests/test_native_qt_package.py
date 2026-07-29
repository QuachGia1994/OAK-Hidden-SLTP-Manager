"""Packaging contracts for the NativeQt installer."""

import subprocess
import sys
import unittest

from build_native_qt_exe import EXTRA_PACKAGE_FILES, HIDDEN_IMPORTS, VERSION as PACKAGE_VERSION
from domain.constants import VERSION as APP_VERSION
from oak_qt_shell import APP_VERSION as SHELL_VERSION


class NativeQtPackageTests(unittest.TestCase):
    def test_package_carries_project_license_and_release_docs(self) -> None:
        self.assertIn("LICENSE.txt", EXTRA_PACKAGE_FILES)
        self.assertIn("THIRD_PARTY_NOTICES.md", EXTRA_PACKAGE_FILES)
        self.assertIn("DESIGN.md", EXTRA_PACKAGE_FILES)
        self.assertIn("signal_rule_contract.json", EXTRA_PACKAGE_FILES)

    def test_native_package_and_shell_share_the_app_version(self) -> None:
        self.assertEqual(PACKAGE_VERSION, APP_VERSION)
        self.assertEqual(SHELL_VERSION, APP_VERSION)

    def test_native_package_contains_stock_advisor_runtime(self) -> None:
        self.assertIn("vn_stock_advisor", HIDDEN_IMPORTS)
        self.assertIn("services.stock_advisor_desktop", HIDDEN_IMPORTS)
        self.assertIn("ssi_sdk", HIDDEN_IMPORTS)

    def test_domain_import_does_not_eager_load_mt5_dependencies(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import sys, domain; print('MetaTrader5' in sys.modules)"],
            capture_output=True,
            check=True,
            text=True,
        )
        self.assertEqual(result.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
