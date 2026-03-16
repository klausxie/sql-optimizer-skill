"""
端到端集成测试 - CLI/Skill 架构测试

测试范围:
- external_llm 模式: CLI 输出 prompt
- 本地模式: CLI 使用启发式模式
- CLI/Skill 文件交互

运行方式:
    python -m pytest tests/test_e2e_cli_skill.py -v
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from sqlopt.contracts import ContractValidator
from sqlopt.stages import scan as scan_stage
from sqlopt.stages import optimize as optimize_stage

ROOT = Path(__file__).resolve().parents[1]


class E2ETestProject:
    """端到端测试项目构建器"""

    def __init__(self, prefix: str = "sqlopt_e2e_") -> None:
        self.temp_dir = tempfile.mkdtemp(prefix=prefix)
        self.root = Path(self.temp_dir)
        self._setup_structure()

    def _setup_structure(self) -> None:
        self.mapper_dir = self.root / "src" / "main" / "resources"
        self.mapper_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir = self.root / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def create_mapper(self, name: str, content: str) -> Path:
        mapper_path = self.mapper_dir / name
        mapper_path.write_text(content, encoding="utf-8")
        return mapper_path

    def get_config(self, external_llm: bool = False) -> dict:
        return {
            "config_version": "v1",
            "project": {"root_path": str(self.root)},
            "scan": {
                "mapper_globs": ["src/main/resources/**/*.xml"],
                "enable_fragment_catalog": True,
            },
            "db": {"platform": "postgresql", "dsn": "postgresql://test@localhost/test"},
            "llm": {"enabled": False, "provider": "heuristic"},
            "external_llm": {"enabled": external_llm},
            "branch": {"enabled": True, "diagnose": False},
            "report": {"enabled": False},
        }

    def create_run_dir(self, run_id: str | None = None) -> Path:
        resolved_id = run_id or f"run_e2e_{uuid4().hex[:8]}"
        run_dir = self.runs_dir / resolved_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建必要的目录结构 (pipeline 结构)
        (run_dir / "pipeline").mkdir(exist_ok=True)
        (run_dir / "pipeline" / "scan").mkdir(exist_ok=True)
        (run_dir / "pipeline" / "optimize").mkdir(exist_ok=True)
        (run_dir / "pipeline" / "supervisor").mkdir(exist_ok=True)
        
        return run_dir

    def cleanup(self) -> None:
        import shutil

        shutil.rmtree(self.root, ignore_errors=True)


class E2EOptimizeExternalLLMTest(unittest.TestCase):
    """测试 external_llm 模式 - CLI 输出 prompt"""

    def setUp(self) -> None:
        self.project = E2ETestProject()
        self.validator = ContractValidator(ROOT)

    def tearDown(self) -> None:
        self.project.cleanup()

    def test_01_external_llm_prompt_output(self) -> None:
        """测试 external_llm.enabled=true 时输出 prompt 文件"""
        # 创建测试 mapper
        self.project.create_mapper(
            "test_mapper.xml",
            """<mapper namespace="e2e.test">
  <select id="findById">
    SELECT * FROM users WHERE id = #{id}
  </select>
</mapper>""",
        )

        # 配置启用 external_llm 模式
        config = self.project.get_config(external_llm=True)
        run_dir = self.project.create_run_dir("run_external")

        # 执行 scan 阶段
        units = scan_stage.execute(config, run_dir, self.validator)
        self.assertGreaterEqual(len(units), 1)

        sql_unit = units[0]
        sql_key = sql_unit["sqlKey"]

        # 执行 optimize 阶段 (external_llm 模式)
        proposal = optimize_stage.execute_one(
            sql_unit, run_dir, self.validator, config
        )

        # 验证 prompt 文件输出 (在 pipeline/optimize 目录)
        prompt_file = run_dir / "pipeline" / "optimize" / f"{sql_key}.prompt.json"
        self.assertTrue(prompt_file.exists(), f"Prompt file should exist: {prompt_file}")

        # 验证 prompt 文件内容
        with open(prompt_file) as f:
            prompt_data = json.load(f)

        self.assertIn("sql_key", prompt_data)
        self.assertIn("stage", prompt_data)
        self.assertIn("timestamp", prompt_data)
        self.assertIn("prompt", prompt_data)
        self.assertEqual(prompt_data["stage"], "optimize")
        self.assertEqual(prompt_data["sql_key"], sql_key)

        # 验证 proposal 状态
        self.assertEqual(proposal.get("llmPromptStatus"), "WAITING_FOR_EXTERNAL_LLM")
        self.assertIn("llmPromptFile", proposal)

    def test_02_external_llm_disabled_local_mode(self) -> None:
        """测试 external_llm.enabled=false 时使用本地模式"""
        # 创建测试 mapper
        self.project.create_mapper(
            "test_local.xml",
            """<mapper namespace="e2e.local">
  <select id="findByName">
    SELECT * FROM users WHERE name = #{name}
  </select>
</mapper>""",
        )

        # 配置禁用 external_llm (默认模式)
        config = self.project.get_config(external_llm=False)
        run_dir = self.project.create_run_dir("run_local")

        # 执行 scan 阶段
        units = scan_stage.execute(config, run_dir, self.validator)
        self.assertGreaterEqual(len(units), 1)

        sql_unit = units[0]
        sql_key = sql_unit["sqlKey"]

        # 执行 optimize 阶段 (本地模式)
        proposal = optimize_stage.execute_one(
            sql_unit, run_dir, self.validator, config
        )

        # 验证不应生成 prompt 文件
        prompt_file = run_dir / "pipeline" / "optimize" / f"{sql_key}.prompt.json"
        self.assertFalse(prompt_file.exists(), "Prompt file should NOT exist in local mode")


class E2ECLISkillInteractionTest(unittest.TestCase):
    """测试 CLI 和 Skill 之间的文件交互"""

    def setUp(self) -> None:
        self.project = E2ETestProject()
        self.validator = ContractValidator(ROOT)

    def tearDown(self) -> None:
        self.project.cleanup()

    def test_03_cli_skill_file_contract(self) -> None:
        """测试 CLI 输出 prompt 的文件契约"""
        # 创建测试 mapper
        self.project.create_mapper(
            "contract_test.xml",
            """<mapper namespace="e2e.contract">
  <select id="search">
    SELECT * FROM users WHERE status = #{status}
  </select>
</mapper>""",
        )

        config = self.project.get_config(external_llm=True)
        run_dir = self.project.create_run_dir("run_contract")

        # CLI: scan 阶段
        units = scan_stage.execute(config, run_dir, self.validator)
        sql_unit = units[0]
        sql_key = sql_unit["sqlKey"]

        # CLI: optimize 阶段 (输出 prompt)
        optimize_stage.execute_one(sql_unit, run_dir, self.validator, config)

        # CLI 输出目录结构验证
        optimize_dir = run_dir / "pipeline" / "optimize"
        self.assertTrue(optimize_dir.exists(), "optimize directory should exist")

        prompt_file = optimize_dir / f"{sql_key}.prompt.json"
        self.assertTrue(prompt_file.exists())

        # Skill: 读取 prompt 文件的契约
        with open(prompt_file) as f:
            prompt_data = json.load(f)

        # Skill 需要的字段
        required_fields = ["sql_key", "stage", "timestamp", "prompt"]
        for field in required_fields:
            self.assertIn(field, prompt_data, f"Skill requires field: {field}")

        # 验证 prompt 内容不为空
        self.assertIsNotNone(prompt_data["prompt"])
        self.assertGreater(len(prompt_data["prompt"]), 0)


class E2EWorkflowIntegrationTest(unittest.TestCase):
    """完整工作流集成测试"""

    def setUp(self) -> None:
        self.project = E2ETestProject()
        self.validator = ContractValidator(ROOT)

    def tearDown(self) -> None:
        self.project.cleanup()

    def test_04_full_diagnose_optimize_workflow(self) -> None:
        """测试 diagnose → optimize 完整流程"""
        # 创建包含多个 SQL 的 mapper
        self.project.create_mapper(
            "full_workflow.xml",
            """<mapper namespace="e2e.workflow">
  <select id="findActive">
    SELECT * FROM users WHERE status = 'ACTIVE'
  </select>
  <select id="searchByName">
    SELECT * FROM users WHERE name LIKE CONCAT('%', #{name}, '%')
  </select>
</mapper>""",
        )

        config = self.project.get_config(external_llm=True)
        run_dir = self.project.create_run_dir("run_full")

        # 阶段 1: diagnose (scan)
        units = scan_stage.execute(config, run_dir, self.validator)
        self.assertGreaterEqual(len(units), 2)

        # 验证 scan 产物
        scan_file = run_dir / "scan.sqlunits.jsonl"
        self.assertTrue(scan_file.exists())

        # 阶段 2: optimize (external_llm 模式)
        for unit in units:
            optimize_stage.execute_one(unit, run_dir, self.validator, config)

        # 验证所有 SQL 都生成了 prompt 文件
        optimize_dir = run_dir / "pipeline" / "optimize"
        prompt_files = list(optimize_dir.glob("*.prompt.json"))
        self.assertEqual(len(prompt_files), len(units))

        # 验证目录结构完整性
        self.assertTrue((run_dir / "pipeline" / "supervisor").exists())


if __name__ == "__main__":
    unittest.main()
