# -*- coding: utf-8 -*-
"""Analysis open-position mapping preserves broker symbols."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import oak_qt_shell


class AnalysisLivePositionsTests(unittest.TestCase):
    def test_live_positions_preserve_plus_suffix(self):
        shell = object.__new__(oak_qt_shell.NativeShell)
        fake_pos = [
            SimpleNamespace(
                symbol="GBPJPY+",
                type=1,
                volume=0.01,
                price_open=190.12,
                price_current=190.50,
                profit=-1.25,
            ),
            SimpleNamespace(
                symbol="GBPUSD+",
                type=1,
                volume=0.01,
                price_open=1.2500,
                price_current=1.2510,
                profit=-0.50,
            ),
        ]

        class _MT5:
            @staticmethod
            def initialize(path=""):
                return True

            @staticmethod
            def positions_get():
                return fake_pos

            @staticmethod
            def shutdown():
                return None

        with patch.object(oak_qt_shell, "read_json", return_value={"Vantage": {"path": "C:/term/terminal64.exe"}}):
            with patch.dict("sys.modules", {"MetaTrader5": _MT5}):
                rows = oak_qt_shell.NativeShell._live_mt5_open_positions(shell, "Vantage")

        self.assertIsNotNone(rows)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["symbol"], "GBPJPY+")
        self.assertEqual(rows[1]["symbol"], "GBPUSD+")
        self.assertEqual(rows[0]["direction"], "SELL")
        self.assertEqual(rows[0]["source_type"], "LIVE_MT5")

    def test_live_positions_unavailable_returns_none(self):
        shell = object.__new__(oak_qt_shell.NativeShell)

        class _MT5:
            @staticmethod
            def initialize(path=""):
                return False

            @staticmethod
            def shutdown():
                return None

        with patch.object(oak_qt_shell, "read_json", return_value={"Vantage": {"path": "C:/term/terminal64.exe"}}):
            with patch.dict("sys.modules", {"MetaTrader5": _MT5}):
                rows = oak_qt_shell.NativeShell._live_mt5_open_positions(shell, "Vantage")
        self.assertIsNone(rows)


if __name__ == "__main__":
    unittest.main()
