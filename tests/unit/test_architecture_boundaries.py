from __future__ import annotations

import ast
import unittest
from pathlib import Path

from sqlopt.application import workflow_engine


ROOT = Path(__file__).resolve().parents[2]


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

    def test_report_builder_delegates_metrics_to_report_metrics_module(self) -> None:
        path = ROOT / "python" / "sqlopt" / "stages" / "report_builder.py"
        imports = set(_import_targets(path))
        self.assertIn(".report_metrics", imports)
        self.assertNotIn("..failure_classification", imports)

    def test_cli_adapter_does_not_import_stage_modules_directly(self) -> None:
        path = ROOT / "python" / "sqlopt" / "cli.py"
        imports = set(_import_targets(path))
        stage_imports = {target for target in imports if target.endswith("stages") or ".stages." in target or target.startswith(".stages")}
        self.assertEqual(stage_imports, set(), "cli.py should delegate stage orchestration via application layer only")

    def test_workflow_engine_declares_explicit_phase_transition_table(self) -> None:
        self.assertEqual(
            workflow_engine.PHASE_TRANSITIONS,
            {
                "preflight": "scan",
                "scan": "optimize",
                "optimize": "validate",
                "validate": "patch_generate",
                "patch_generate": "report",
                "report": None,
            },
        )
        self.assertEqual(set(workflow_engine.PHASE_TRANSITIONS.keys()), set(workflow_engine.STAGE_ORDER))

    def test_config_module_delegates_parsing_to_configuration_package(self) -> None:
        path = ROOT / "python" / "sqlopt" / "config.py"
        imports = set(_import_targets(path))
        self.assertIn(".configuration.common", imports)
        self.assertIn(".configuration.defaults", imports)
        self.assertIn(".configuration.versioning", imports)

    def test_workflow_engine_delegates_to_workflow_component_modules(self) -> None:
        path = ROOT / "python" / "sqlopt" / "application" / "workflow_engine.py"
        imports = set(_import_targets(path))
        self.assertIn(".workflow_definition", imports)
        self.assertIn(".workflow_facade", imports)
        self.assertIn(".workflow_handlers_adapter", imports)
        self.assertIn(".workflow_step_runner", imports)
        forbidden_core = {"..runtime", "..io_utils", "..manifest", ".phase_runtime", ".stage_index"}
        self.assertTrue(forbidden_core.isdisjoint(imports), f"workflow_engine should avoid low-level runtime/io modules: {imports & forbidden_core}")

    def test_patch_generate_delegates_to_decision_and_verification_modules(self) -> None:
        path = ROOT / "python" / "sqlopt" / "stages" / "patch_generate.py"
        imports = set(_import_targets(path))
        # 现在使用新的 patch_decision 模块（含兼容层）
        self.assertIn(".patch_decision", imports)
        self.assertIn(".patch_verification", imports)
        self.assertIn(".patch_formatting", imports)


if __name__ == "__main__":
    unittest.main()
