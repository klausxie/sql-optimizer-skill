from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _import_targets(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = "." * node.level + module
            targets.append(module)
    return targets


class ArchitectureBoundariesTest(unittest.TestCase):
    def test_sql_model_modules_do_not_depend_on_flow_modules(self) -> None:
        files = [
            ROOT / "python" / "sqlopt" / "platforms" / "sql" / "candidate_models.py",
            ROOT / "python" / "sqlopt" / "platforms" / "sql" / "validation_models.py",
        ]
        forbidden = {
            ".candidate_selection",
            ".acceptance_policy",
            ".validator_sql",
            ".validation_strategy",
        }

        for path in files:
            imports = set(_import_targets(path))
            self.assertTrue(forbidden.isdisjoint(imports), f"{path.name} should not import flow modules: {imports & forbidden}")

    def test_sql_models_facade_only_reexports_model_modules(self) -> None:
        path = ROOT / "python" / "sqlopt" / "platforms" / "sql" / "models.py"
        imports = set(_import_targets(path))
        self.assertEqual(imports, {"__future__", ".candidate_models", ".validation_models"})

    def test_report_models_do_not_depend_on_flow_modules(self) -> None:
        path = ROOT / "python" / "sqlopt" / "stages" / "report_models.py"
        imports = set(_import_targets(path))
        forbidden = {
            ".report_loader",
            ".report_builder",
            ".report_writer",
            ".report",
        }
        self.assertTrue(forbidden.isdisjoint(imports), f"report_models.py should not import flow modules: {imports & forbidden}")

    def test_report_interfaces_only_reexports_model_modules(self) -> None:
        path = ROOT / "python" / "sqlopt" / "stages" / "report_interfaces.py"
        imports = set(_import_targets(path))
        self.assertEqual(imports, {"__future__", ".report_models"})


if __name__ == "__main__":
    unittest.main()
