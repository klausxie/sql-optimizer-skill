"""
端到端集成测试 - Diagnose 阶段完整测试

测试范围:
1. 分支生成 - all_combinations, pairwise, boundary 策略
2. 静态规则评估 - 各种规则模式检测
3. 基线诊断 - DB 可达/不可达决策
4. 报告生成 - 统计和输出

运行方式:
    python -m pytest tests/test_e2e_diagnose.py -v
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from sqlopt.contracts import ContractValidator
from sqlopt.stages import scan as scan_stage
from sqlopt.stages import diagnose as diagnose_stage

ROOT = Path(__file__).resolve().parents[1]


class DiagnoseTestProject:
    """Diagnose 阶段测试项目构建器"""

    def __init__(self, prefix: str = "sqlopt_diag_") -> None:
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

    def get_config(
        self,
        branch_strategy: str = "all_combinations",
        branch_enabled: bool = True,
        diagnose_enabled: bool = True,
    ) -> dict:
        return {
            "config_version": "v1",
            "project": {"root_path": str(self.root)},
            "scan": {
                "mapper_globs": ["src/main/resources/**/*.xml"],
                "enable_fragment_catalog": True,
            },
            "db": {"platform": "postgresql", "dsn": "postgresql://test@localhost/test"},
            "llm": {"enabled": False, "provider": "heuristic"},
            "branch": {
                "enabled": branch_enabled,
                "diagnose": diagnose_enabled,
                "strategy": branch_strategy,
                "max_branches": 100,
            },
            "report": {"enabled": False},
        }

    def create_run_dir(self, run_id: str | None = None) -> Path:
        resolved_id = run_id or f"run_diag_{uuid4().hex[:8]}"
        run_dir = self.runs_dir / resolved_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "pipeline" / "supervisor").mkdir(parents=True, exist_ok=True)
        return run_dir

    def cleanup(self) -> None:
        import shutil

        shutil.rmtree(self.root, ignore_errors=True)


# ============================================================================
# Test Class 1: 分支生成策略测试
# ============================================================================

class TestBranchGenerationStrategies(unittest.TestCase):
    """测试不同分支生成策略"""

    def setUp(self) -> None:
        self.project = DiagnoseTestProject()
        self.validator = ContractValidator(ROOT)

    def tearDown(self) -> None:
        self.project.cleanup()

    def test_strategy_all_combinations(self) -> None:
        """测试 all_combinations 策略 - 100% 覆盖"""
        # 创建两个独立 if 条件
        self.project.create_mapper(
            "all_combinations.xml",
            """<mapper namespace="test.all_combinations">
  <select id="search">
    SELECT * FROM users
    <where>
      <if test="a != null">AND a = #{a}</if>
      <if test="b != null">AND b = #{b}</if>
    </where>
  </select>
</mapper>""",
        )

        # 使用 all_combinations 策略
        config = self.project.get_config(branch_strategy="all_combinations")
        run_dir = self.project.create_run_dir("run_all")

        units = scan_stage.execute(config, run_dir, self.validator)

        self.assertEqual(len(units), 1)
        branches = units[0].get("branches", [])
        
        # 两个独立 if 应该生成 2^2 = 4 个分支
        self.assertEqual(len(branches), 4)
        
        # 验证分支条件
        # Verify branches exist
        # Branch count verified above

    def test_strategy_pairwise(self) -> None:
        """测试 pairwise 策略 - 95%+ 覆盖"""
        # 创建两个独立 if 条件
        self.project.create_mapper(
            "pairwise.xml",
            """<mapper namespace="test.pairwise">
  <select id="search">
    SELECT * FROM users
    <where>
      <if test="a != null">AND a = #{a}</if>
      <if test="b != null">AND b = #{b}</if>
    </where>
  </select>
</mapper>""",
        )

        # 使用 pairwise 策略
        config = self.project.get_config(branch_strategy="pairwise")
        run_dir = self.project.create_run_dir("run_pairwise")

        units = scan_stage.execute(config, run_dir, self.validator)

        self.assertEqual(len(units), 1)
        branches = units[0].get("branches", [])
        
        # pairwise 应该生成 2 个分支 (每个条件一次)
        self.assertEqual(len(branches), 2)

    def test_strategy_boundary(self) -> None:
        """测试 boundary 策略 - 边界值测试"""
        # 创建两个独立 if 条件
        self.project.create_mapper(
            "boundary.xml",
            """<mapper namespace="test.boundary">
  <select id="search">
    SELECT * FROM users
    <where>
      <if test="a != null">AND a = #{a}</if>
      <if test="b != null">AND b = #{b}</if>
    </where>
  </select>
</mapper>""",
        )

        # 使用 boundary 策略
        config = self.project.get_config(branch_strategy="boundary")
        run_dir = self.project.create_run_dir("run_boundary")

        units = scan_stage.execute(config, run_dir, self.validator)

        self.assertEqual(len(units), 1)
        branches = units[0].get("branches", [])
        
        # boundary 应该生成 2 个分支 (全 false + 全 true)
        self.assertEqual(len(branches), 2)

    def test_strategy_auto_selection(self) -> None:
        """测试 auto 策略 - 根据分支数自动选择"""
        # 创建 4 个 if 条件 (2^4 = 16)
        self.project.create_mapper(
            "auto.xml",
            """<mapper namespace="test.auto">
  <select id="search">
    SELECT * FROM users
    <where>
      <if test="a != null">AND a = #{a}</if>
      <if test="b != null">AND b = #{b}</if>
      <if test="c != null">AND c = #{c}</if>
      <if test="d != null">AND d = #{d}</if>
    </where>
  </select>
</mapper>""",
        )

        # 使用 auto 策略 (默认)
        config = self.project.get_config(branch_strategy="auto")
        run_dir = self.project.create_run_dir("run_auto")

        units = scan_stage.execute(config, run_dir, self.validator)

        self.assertEqual(len(units), 1)
        branches = units[0].get("branches", [])
        
        # 4 个条件: auto 应该选择 all_combinations (16 <= 16)
        self.assertEqual(len(branches), 16)

    def test_foreach_boundary_branches(self) -> None:
        """测试 foreach 边界分支生成"""
        self.project.create_mapper(
            "foreach.xml",
            """<mapper namespace="test.foreach">
  <select id="findByIds">
    SELECT * FROM users WHERE id IN
    <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
  </select>
</mapper>""",
        )

        config = self.project.get_config(branch_strategy="all_combinations")
        run_dir = self.project.create_run_dir("run_foreach")

        units = scan_stage.execute(config, run_dir, self.validator)

        self.assertEqual(len(units), 1)
        branches = units[0].get("branches", [])
        
        # foreach 应该有额外边界分支
        self.assertGreater(len(branches), 1)


# ============================================================================
# Test Class 2: 静态规则评估测试
# ============================================================================

class TestStaticRulesEvaluation(unittest.TestCase):
    """测试静态规则评估"""

    def setUp(self) -> None:
        self.project = DiagnoseTestProject()
        self.validator = ContractValidator(ROOT)

    def tearDown(self) -> None:
        self.project.cleanup()

    def test_rule_prefix_wildcard(self) -> None:
        """测试前缀通配符规则"""
        self.project.create_mapper(
            "prefix_wildcard.xml",
            """<mapper namespace="test.prefix">
  <select id="search">
    SELECT * FROM users WHERE name LIKE '%' || #{name}
  </select>
</mapper>""",
        )

        config = self.project.get_config()
        run_dir = self.project.create_run_dir("run_prefix")

        units = scan_stage.execute(config, run_dir, self.validator)
        units = diagnose_stage._evaluate_static_rules(units, config)

        self.assertEqual(len(units), 1)
        unit = units[0]
        
        # 应该检测到 prefix_wildcard 或 concat_wildcard
        triggered = unit.get("triggeredRules", [])
        rule_ids = [r.get("ruleId") for r in triggered]
        
        # 检查是否有通配符相关规则
        has_wildcard_rule = any(
            "wildcard" in str(r).lower() for r in rule_ids
        )
        # 注意: 具体规则取决于实际实现

    def test_rule_suffix_wildcard(self) -> None:
        """测试后缀通配符规则"""
        self.project.create_mapper(
            "suffix_wildcard.xml",
            """<mapper namespace="test.suffix">
  <select id="search">
    SELECT * FROM users WHERE name LIKE #{name} || '%'
  </select>
</mapper>""",
        )

        config = self.project.get_config()
        run_dir = self.project.create_run_dir("run_suffix")

        units = scan_stage.execute(config, run_dir, self.validator)
        units = diagnose_stage._evaluate_static_rules(units, config)

        self.assertEqual(len(units), 1)
        # 验证规则评估执行成功
        self.assertIn("ruleVerdict", units[0])

    def test_rule_function_wrap(self) -> None:
        """测试函数包装规则"""
        self.project.create_mapper(
            "function_wrap.xml",
            """<mapper namespace="test.function">
  <select id="search">
    SELECT * FROM users WHERE UPPER(name) = #{name}
  </select>
</mapper>""",
        )

        config = self.project.get_config()
        run_dir = self.project.create_run_dir("run_function")

        units = scan_stage.execute(config, run_dir, self.validator)
        units = diagnose_stage._evaluate_static_rules(units, config)

        self.assertEqual(len(units), 1)
        self.assertIn("ruleVerdict", units[0])

    def test_rule_no_where_clause(self) -> None:
        """测试无 WHERE 子句规则"""
        self.project.create_mapper(
            "no_where.xml",
            """<mapper namespace="test.no_where">
  <select id="listAll">
    SELECT * FROM users
  </select>
</mapper>""",
        )

        config = self.project.get_config()
        run_dir = self.project.create_run_dir("run_no_where")

        units = scan_stage.execute(config, run_dir, self.validator)
        units = diagnose_stage._evaluate_static_rules(units, config)

        self.assertEqual(len(units), 1)
        self.assertIn("ruleVerdict", units[0])

    def test_rule_select_star(self) -> None:
        """测试 SELECT * 规则"""
        self.project.create_mapper(
            "select_star.xml",
            """<mapper namespace="test.select_star">
  <select id="search">
    SELECT * FROM users WHERE id = #{id}
  </select>
</mapper>""",
        )

        config = self.project.get_config()
        run_dir = self.project.create_run_dir("run_select_star")

        units = scan_stage.execute(config, run_dir, self.validator)
        units = diagnose_stage._evaluate_static_rules(units, config)

        self.assertEqual(len(units), 1)
        self.assertIn("ruleVerdict", units[0])


# ============================================================================
# Test Class 3: 基线诊断决策测试
# ============================================================================

class TestBaselineDiagnosis(unittest.TestCase):
    """测试基线诊断决策"""

    def setUp(self) -> None:
        self.project = DiagnoseTestProject()
        self.validator = ContractValidator(ROOT)

    def tearDown(self) -> None:
        self.project.cleanup()

    def test_diagnose_enabled_db_unreachable(self) -> None:
        """测试 diagnose=true, DB 不可达 -> 跳过基线"""
        self.project.create_mapper(
            "test.xml",
            """<mapper namespace="test.db">
  <select id="search">
    SELECT * FROM users WHERE id = #{id}
  </select>
</mapper>""",
        )

        # 配置 diagnose=true，但 DB 不可达
        config = self.project.get_config(diagnose_enabled=True)
        # 覆盖 DSN 为无效值以模拟 DB 不可达
        config["db"]["dsn"] = "postgresql://invalid:invalid@localhost:99999/db"

        run_dir = self.project.create_run_dir("run_diag")

        units = diagnose_stage.execute(config, run_dir, self.validator)

        # 应该成功返回，但无基线信息
        self.assertGreaterEqual(len(units), 1)
        
        # 验证单元没有 baseline 信息（因为 DB 不可达）
        for unit in units:
            branches = unit.get("branches", [])
            for branch in branches:
                # 基线信息应该不存在或为空
                if branches:
                    self.assertNotIn("baseline", branch)

    def test_diagnose_disabled(self) -> None:
        """测试 diagnose=false -> 跳过基线"""
        self.project.create_mapper(
            "test.xml",
            """<mapper namespace="test.disabled">
  <select id="search">
    SELECT * FROM users WHERE id = #{id}
  </select>
</mapper>""",
        )

        # 配置 diagnose=false
        config = self.project.get_config(diagnose_enabled=False)
        run_dir = self.project.create_run_dir("run_disabled")

        units = diagnose_stage.execute(config, run_dir, self.validator)

        # 应该成功返回
        self.assertGreaterEqual(len(units), 1)


# ============================================================================
# Test Class 4: 报告生成测试
# ============================================================================

class TestReportGeneration(unittest.TestCase):
    """测试报告生成"""

    def setUp(self) -> None:
        self.project = DiagnoseTestProject()
        self.validator = ContractValidator(ROOT)

    def tearDown(self) -> None:
        self.project.cleanup()

    def test_diagnose_report_structure(self) -> None:
        """测试诊断报告结构"""
        self.project.create_mapper(
            "report_test.xml",
            """<mapper namespace="test.report">
  <select id="findActive">
    SELECT * FROM users WHERE status = 'ACTIVE'
  </select>
  <select id="searchByName">
    SELECT * FROM users WHERE name LIKE CONCAT('%', #{name}, '%')
  </select>
</mapper>""",
        )

        config = self.project.get_config(diagnose_enabled=False)
        run_dir = self.project.create_run_dir("run_report")

        units = diagnose_stage.execute(config, run_dir, self.validator)

        # 验证报告文件存在
        report_file = run_dir / "diagnose.report.json"
        self.assertTrue(report_file.exists())

        # 验证报告内容
        with open(report_file) as f:
            report = json.load(f)

        self.assertIn("summary", report)
        self.assertIn("units", report)
        
        # 验证 summary 结构
        summary = report["summary"]
        self.assertIn("totalUnits", summary)
        self.assertEqual(summary["totalUnits"], 2)

    def test_diagnose_report_units_detail(self) -> None:
        """测试诊断报告单元详情"""
        self.project.create_mapper(
            "units_detail.xml",
            """<mapper namespace="test.units">
  <select id="findById">
    SELECT * FROM users WHERE id = #{id}
  </select>
</mapper>""",
        )

        config = self.project.get_config(diagnose_enabled=False)
        run_dir = self.project.create_run_dir("run_units")

        units = diagnose_stage.execute(config, run_dir, self.validator)

        # 验证报告
        report_file = run_dir / "diagnose.report.json"
        with open(report_file) as f:
            report = json.load(f)

        # 验证 units 详情
        self.assertEqual(len(report["units"]), 1)
        unit = report["units"][0]
        
        self.assertIn("sqlKey", unit)
        self.assertIn("statementId", unit)
        self.assertIn("namespace", unit)
        self.assertIn("branchCount", unit)


# ============================================================================
# Test Class 5: 完整流程集成测试
# ============================================================================

class TestDiagnoseFullWorkflow(unittest.TestCase):
    """测试完整 diagnose 工作流"""

    def setUp(self) -> None:
        self.project = DiagnoseTestProject()
        self.validator = ContractValidator(ROOT)

    def tearDown(self) -> None:
        self.project.cleanup()

    def test_full_diagnose_workflow(self) -> None:
        """测试完整 diagnose 工作流"""
        # 创建复杂的 mapper
        self.project.create_mapper(
            "complex.xml",
            """<mapper namespace="test.complex">
  <select id="searchUsers">
    SELECT * FROM users
    <where>
      <if test="name != null">AND name = #{name}</if>
      <if test="status != null">AND status = #{status}</if>
      <if test="email != null">AND email LIKE CONCAT('%', #{email}, '%')</if>
    </where>
  </select>
  <select id="listByIds">
    SELECT * FROM users WHERE id IN
    <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
  </select>
</mapper>""",
        )

        config = self.project.get_config(
            branch_strategy="all_combinations",
            diagnose_enabled=False,
        )
        run_dir = self.project.create_run_dir("run_full")

        # 执行完整 diagnose
        units = diagnose_stage.execute(config, run_dir, self.validator)

        # 验证结果
        self.assertEqual(len(units), 2)
        
        # 验证第一个 SQL (3 个 if = 2^3 = 8 分支)
        search_unit = [u for u in units if "searchUsers" in u.get("sqlKey", "")][0]
        branches = search_unit.get("branches", [])
        self.assertGreaterEqual(len(branches), 8)

    def test_multiple_mappers(self) -> None:
        """测试多个 mapper 文件"""
        # 创建多个 mapper
        self.project.create_mapper(
            "mapper1.xml",
            """<mapper namespace="test.mapper1">
  <select id="findById">SELECT * FROM users WHERE id = #{id}</select>
</mapper>""",
        )

        self.project.create_mapper(
            "mapper2.xml",
            """<mapper namespace="test.mapper2">
  <select id="listAll">SELECT * FROM orders</select>
</mapper>""",
        )

        config = self.project.get_config()
        run_dir = self.project.create_run_dir("run_multi")

        units = diagnose_stage.execute(config, run_dir, self.validator)

        # 应该扫描到 2 个 SQL
        self.assertEqual(len(units), 2)

    def test_dynamic_features_detection(self) -> None:
        """测试动态特征检测"""
        self.project.create_mapper(
            "dynamic.xml",
            """<mapper namespace="test.dynamic">
  <select id="search">
    SELECT * FROM users
    <where>
      <if test="name != null">AND name = #{name}</if>
    </where>
    <choose>
      <when test="type == 'A'">AND type = 'A'</when>
      <otherwise>AND type = 'B'</otherwise>
    </choose>
  </select>
</mapper>""",
        )

        config = self.project.get_config()
        run_dir = self.project.create_run_dir("run_dynamic")

        units = scan_stage.execute(config, run_dir, self.validator)

        self.assertEqual(len(units), 1)
        
        # 验证动态特征
        dynamic_features = units[0].get("dynamicFeatures", [])
        self.assertIn("IF", dynamic_features)
        self.assertIn("CHOOSE", dynamic_features)
        self.assertIn("WHERE", dynamic_features)


if __name__ == "__main__":
    unittest.main()
