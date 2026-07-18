"""Keep every literal Classic UI translation key available in EN and VN."""

import ast
import unittest
from pathlib import Path

from domain.i18n import LANG


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", ".mimocode", "dashboard", "dist", "venv"}


def classic_translation_keys() -> set[str]:
    """Collect literal calls to the Classic UI ``T`` helper."""
    keys: set[str] = set()
    for path in ROOT.rglob("*.py"):
        if EXCLUDED_PARTS.intersection(path.parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id != "T" or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                keys.add(first.value)
    return keys


class ClassicI18nCatalogTests(unittest.TestCase):
    def test_every_literal_key_exists_in_english_and_vietnamese(self) -> None:
        keys = classic_translation_keys()

        for language in ("EN", "VN"):
            missing = sorted(key for key in keys if key not in LANG[language])
            self.assertFalse(missing, f"{language} is missing: {', '.join(missing)}")


if __name__ == "__main__":
    unittest.main()
