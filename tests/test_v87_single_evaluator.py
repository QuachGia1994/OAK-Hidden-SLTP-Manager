"""Guard against restoring obsolete v82 evaluator and entry-timing definitions."""

import ast
from pathlib import Path
import unittest


class V87SingleEvaluatorTests(unittest.TestCase):
    @staticmethod
    def _definitions(module: ast.Module, name: str) -> list[ast.FunctionDef]:
        return [
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]

    @staticmethod
    def _call_names(function: ast.FunctionDef) -> list[str]:
        return [
            node.func.id
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]

    def test_only_canonical_v87_evaluators_are_declared(self) -> None:
        source_path = Path(__file__).resolve().parents[1] / "mt5_signal_bot.py"
        module = ast.parse(source_path.read_text(encoding="utf-8"))
        evaluators = self._definitions(module, "evaluate_all_pairs_for_slot")
        symbol_timing = self._definitions(module, "evaluate_symbol_entry_timing_m30")
        xau_timing = self._definitions(module, "evaluate_xau_entry_timing_m30")

        self.assertEqual(len(evaluators), 1)
        self.assertEqual(len(symbol_timing), 1)
        self.assertEqual(len(xau_timing), 1)
        self.assertIn("v87 pipeline", ast.get_docstring(evaluators[0]) or "")
        self.assertIn("evaluate_v87_slot", self._call_names(evaluators[0]))
        self.assertIn("build_v87_entry_plan", self._call_names(symbol_timing[0]))
        self.assertIn("build_v87_entry_plan", self._call_names(xau_timing[0]))


if __name__ == "__main__":
    unittest.main()
