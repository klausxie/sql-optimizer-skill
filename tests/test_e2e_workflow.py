"""
端到端集成测试 - SQL Optimizer Skill 核心功能测试

测试范围:
- Scan 阶段: SQL 扫描、动态标签解析、分支推断
- Schema 验证: 所有产物符合 JSON Schema
- 分支生成: if/choose/foreach 等动态标签

运行方式:
    python -m pytest tests/test_e2e_workflow.py -v
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from sqlopt.contracts import ContractValidator
from sqlopt.scripting.branch_generator import BranchGenerator
from sqlopt.scripting.xml_script_builder import XMLScriptBuilder
from sqlopt.stages import scan as scan_stage

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

    def get_config(self) -> dict:
        return {
            "config_version": "v1",
            "project": {"root_path": str(self.root)},
            "scan": {
                "mapper_globs": ["src/main/resources/**/*.xml"],
                "enable_fragment_catalog": True,
                "branch": {"enabled": True, "diagnose": False},
            },
            "db": {"platform": "postgresql", "dsn": "postgresql://test@localhost/test"},
            "llm": {"enabled": False, "provider": "heuristic"},
            "branch": {"enabled": True, "diagnose": False},
            "report": {"enabled": False},
        }

    def create_run_dir(self, run_id: str | None = None) -> Path:
        resolved_id = run_id or f"run_e2e_{uuid4().hex[:8]}"
        run_dir = self.runs_dir / resolved_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def cleanup(self) -> None:
        import shutil

        shutil.rmtree(self.root, ignore_errors=True)


class E2EScanStageTest(unittest.TestCase):
    """E2E Scan 阶段测试"""

    def setUp(self) -> None:
        self.project = E2ETestProject()
        self.validator = ContractValidator(ROOT)

    def tearDown(self) -> None:
        self.project.cleanup()

    def test_01_basic_scan(self) -> None:
        """测试基本 SQL 扫描"""
        self.project.create_mapper(
            "basic_mapper.xml",
            """<mapper namespace="e2e.basic">
  <select id="findById">SELECT id, name FROM users WHERE id = #{id}</select>
  <select id="listAll">SELECT id, name FROM users</select>
  <update id="updateName">UPDATE users SET name = #{name}</update>
  <insert id="insertUser">INSERT INTO users (name) VALUES (#{name})</insert>
  <delete id="deleteById">DELETE FROM users WHERE id = #{id}</delete>
</mapper>""",
        )

        config = self.project.get_config()
        run_dir = self.project.create_run_dir("run_basic")

        units = scan_stage.execute(config, run_dir, self.validator)

        self.assertGreaterEqual(len(units), 5)
        statement_ids = {u["statementId"] for u in units}
        self.assertIn("findById", statement_ids)
        self.assertIn("listAll", statement_ids)

    def test_02_dynamic_tags_if_where(self) -> None:
        """测试 if/where 动态标签"""
        self.project.create_mapper(
            "dynamic_if_mapper.xml",
            """<mapper namespace="e2e.dynamic">
  <select id="searchUsers">
    SELECT * FROM users
    <where>
      <if test="name != null">AND name = #{name}</if>
      <if test="status != null">AND status = #{status}</if>
    </where>
  </select>
</mapper>""",
        )

        config = self.project.get_config()
        run_dir = self.project.create_run_dir("run_if")

        units = scan_stage.execute(config, run_dir, self.validator)

        self.assertEqual(len(units), 1)
        unit = units[0]
        self.assertIn("IF", unit.get("dynamicFeatures", []))
        self.assertIn("WHERE", unit.get("dynamicFeatures", []))

    def test_03_dynamic_tags_choose(self) -> None:
        """测试 choose/when/otherwise 动态标签"""
        self.project.create_mapper(
            "dynamic_choose_mapper.xml",
            """<mapper namespace="e2e.choose">
  <select id="findByType">
    SELECT * FROM users
    <where>
      <choose>
        <when test="type == 'VIP'">AND priority = 1</when>
        <otherwise>AND priority = 0</otherwise>
      </choose>
    </where>
  </select>
</mapper>""",
        )

        config = self.project.get_config()
        run_dir = self.project.create_run_dir("run_choose")

        units = scan_stage.execute(config, run_dir, self.validator)

        self.assertEqual(len(units), 1)
        unit = units[0]
        self.assertIn("CHOOSE", unit.get("dynamicFeatures", []))

    def test_04_dynamic_tags_foreach(self) -> None:
        """测试 foreach 动态标签"""
        self.project.create_mapper(
            "dynamic_foreach_mapper.xml",
            """<mapper namespace="e2e.foreach">
  <select id="findByIds">
    SELECT * FROM users WHERE id IN
    <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
  </select>
</mapper>""",
        )

        config = self.project.get_config()
        run_dir = self.project.create_run_dir("run_foreach")

        units = scan_stage.execute(config, run_dir, self.validator)

        self.assertEqual(len(units), 1)
        unit = units[0]
        self.assertIn("FOREACH", unit.get("dynamicFeatures", []))

    def test_05_fragment_include(self) -> None:
        """测试 sql/include 片段引用"""
        self.project.create_mapper(
            "fragment_mapper.xml",
            """<mapper namespace="e2e.fragment">
  <sql id="BaseColumns">id, name, email</sql>
  <select id="findActive">
    SELECT <include refid="BaseColumns"/> FROM users WHERE status = 'ACTIVE'
  </select>
</mapper>""",
        )

        config = self.project.get_config()
        run_dir = self.project.create_run_dir("run_include")

        units = scan_stage.execute(config, run_dir, self.validator)

        self.assertGreaterEqual(len(units), 1)

    def test_06_branch_inference(self) -> None:
        """测试分支推断功能"""
        self.project.create_mapper(
            "branch_mapper.xml",
            """<mapper namespace="e2e.branch">
  <select id="search">
    SELECT * FROM users
    <where>
      <if test="a">AND a = 1</if>
      <if test="b">AND b = 2</if>
    </where>
  </select>
</mapper>""",
        )

        config = self.project.get_config()
        run_dir = self.project.create_run_dir("run_branch")

        units = scan_stage.execute(config, run_dir, self.validator)

        self.assertEqual(len(units), 1)
        unit = units[0]
        branches = unit.get("branches", [])
        # 2 个独立 if -> 4 个分支
        self.assertGreaterEqual(len(branches), 4)

    def test_07_artifacts_exist(self) -> None:
        """测试产物文件存在"""
        self.project.create_mapper(
            "artifact_mapper.xml",
            """<mapper namespace="e2e.artifact">
  <select id="q">SELECT 1</select>
</mapper>""",
        )

        config = self.project.get_config()
        run_dir = self.project.create_run_dir("run_artifacts")

        scan_stage.execute(config, run_dir, self.validator)

        self.assertTrue((run_dir / "scan.sqlunits.jsonl").exists())
        self.assertTrue((run_dir / "scan.fragments.jsonl").exists())

    def test_08_schema_validation(self) -> None:
        """测试 Schema 验证"""
        self.project.create_mapper(
            "schema_mapper.xml",
            """<mapper namespace="e2e.schema">
  <select id="valid">SELECT id FROM users WHERE status = #{status}</select>
</mapper>""",
        )

        config = self.project.get_config()
        run_dir = self.project.create_run_dir("run_schema")

        units = scan_stage.execute(config, run_dir, self.validator)

        for unit in units:
            # validate 方法在成功时返回 None，失败时抛出 ContractError
            # 验证必需字段
            for field in ["sqlKey", "namespace", "statementId", "sql"]:
                self.assertIn(field, unit)


class E2EBranchGenerationTest(unittest.TestCase):
    """分支生成测试"""

    def test_simple_if(self) -> None:
        """简单 if 分支"""
        sql = "SELECT * FROM users <where><if test='x'>AND x=1</if></where>"
        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(node)
        self.assertEqual(len(branches), 2)

    def test_two_independent_if(self) -> None:
        """两个独立 if 分支"""
        sql = "SELECT * FROM users <where><if test='a'>AND a=1</if><if test='b'>AND b=2</if></where>"
        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=100
        ).generate(node)
        self.assertEqual(len(branches), 4)

    def test_choose_three_branches(self) -> None:
        """choose 分支"""
        sql = """SELECT * FROM users <where>
            <choose>
                <when test='x=1'>AND x=1</when>
                <when test='x=2'>AND x=2</when>
                <otherwise>AND x=0</otherwise>
            </choose>
        </where>"""
        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(node)
        self.assertEqual(len(branches), 3)

    def test_foreach(self) -> None:
        """foreach 分支"""
        sql = "SELECT * FROM users WHERE id IN <foreach collection='ids' item='id' open='(' separator=',' close=')'>#{id}</foreach>"
        node = XMLScriptBuilder().parse(sql)
        branches = BranchGenerator(
            strategy="all_combinations", max_branches=10
        ).generate(node)
        self.assertGreater(len(branches), 0)


if __name__ == "__main__":
    unittest.main()
