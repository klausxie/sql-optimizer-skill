from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sqlopt.adapters import scanner_java as scanner_adapter
from sqlopt.adapters.scanner_java import run_scan
from sqlopt.contracts import ContractValidator
from sqlopt.errors import StageError
from sqlopt.stages import scan

ROOT = Path(__file__).resolve().parents[3]


class _Proc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class ScannerAdapterTest(unittest.TestCase):
    def test_build_unit_uses_statement_key_without_default_variant_suffix(self) -> None:
        unit = scanner_adapter._build_unit(
            Path("/tmp/demo_mapper.xml"),
            "demo.user",
            "findUsers",
            "SELECT",
            "SELECT * FROM users",
            1,
        )
        self.assertEqual(unit["statementKey"], "demo.user.findUsers")
        self.assertEqual(unit["sqlKey"], "demo.user.findUsers")
        self.assertNotIn("variantId", unit)

    def test_run_scan_supports_foreach_object_collection(self) -> None:
        jar = ROOT / "java" / "scan-agent" / "target" / "scan-agent-1.0.0.jar"
        if not jar.exists():
            self.skipTest("scan-agent jar not built")
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_foreach_") as td:
            root = Path(td)
            mapper = root / "src" / "main" / "resources" / "demo_mapper.xml"
            mapper.parent.mkdir(parents=True, exist_ok=True)
            mapper.write_text(
                """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="demo.user">
  <select id="findByList" resultType="map">
    SELECT id FROM users WHERE id IN
    <foreach collection="list" item="item" open="(" separator="," close=")">
      #{item.id}
    </foreach>
  </select>
</mapper>
""",
                encoding="utf-8",
            )
            run_dir = root / "runs" / "run_scan_foreach_object"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {
                    "mapper_globs": ["src/main/resources/*.xml"],
                    "java_scanner": {"jar_path": str(jar)},
                },
                "db": {"platform": "postgresql"},
            }
            units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")
            self.assertEqual(len(units), 1)
            self.assertEqual(units[0]["statementId"], "findByList")
            self.assertIn("#{item.id}", units[0]["sql"])
            self.assertIn("<foreach", units[0]["templateSql"])
            self.assertIn("FOREACH", units[0]["dynamicFeatures"])
            self.assertFalse(any(w.get("reason_code") == "SCAN_STATEMENT_PARSE_DEGRADED" for w in warnings))

    def test_run_scan_preserves_include_in_template_sql(self) -> None:
        jar = ROOT / "java" / "scan-agent" / "target" / "scan-agent-1.0.0.jar"
        if not jar.exists():
            self.skipTest("scan-agent jar not built")
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_include_") as td:
            root = Path(td)
            mapper = root / "src" / "main" / "resources" / "demo_mapper.xml"
            mapper.parent.mkdir(parents=True, exist_ok=True)
            mapper.write_text(
                """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="demo.user">
  <sql id="BaseWhere">WHERE status = #{status}</sql>
  <select id="findIncluded" resultType="map">
    SELECT id FROM users
    <include refid="BaseWhere" />
  </select>
</mapper>
""",
                encoding="utf-8",
            )
            run_dir = root / "runs" / "run_scan_include_template"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {
                    "mapper_globs": ["src/main/resources/*.xml"],
                    "java_scanner": {"jar_path": str(jar)},
                },
                "db": {"platform": "postgresql"},
            }
            units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")
            self.assertEqual(len(units), 1)
            self.assertEqual(units[0]["statementId"], "findIncluded")
            self.assertIn("WHERE status = #{status}", units[0]["sql"])
            self.assertIn("<include", units[0]["templateSql"])
            self.assertIn("INCLUDE", units[0]["dynamicFeatures"])
            self.assertEqual(units[0]["includeTrace"], ["demo.user.BaseWhere"])
            self.assertEqual(units[0]["dynamicTrace"]["includeFragments"][0]["ref"], "demo.user.BaseWhere")
            fragment_rows = [json.loads(line) for line in (run_dir / "artifacts" / "fragments.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(fragment_rows[0]["displayRef"], "demo.user.BaseWhere")
            self.assertEqual(warnings, [])

    def test_run_scan_tracks_nested_include_fragment_dynamic_features(self) -> None:
        jar = ROOT / "java" / "scan-agent" / "target" / "scan-agent-1.0.0.jar"
        if not jar.exists():
            self.skipTest("scan-agent jar not built")
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_include_nested_") as td:
            root = Path(td)
            mapper = root / "src" / "main" / "resources" / "demo_mapper.xml"
            mapper.parent.mkdir(parents=True, exist_ok=True)
            mapper.write_text(
                """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="demo.user">
  <sql id="NameFilter">AND name = #{name}</sql>
  <sql id="BaseWhere">
    <if test="status != null">
      WHERE status = #{status}
      <include refid="NameFilter" />
    </if>
  </sql>
  <select id="findNestedIncluded" resultType="map">
    SELECT id FROM users
    <include refid="BaseWhere" />
  </select>
</mapper>
""",
                encoding="utf-8",
            )
            run_dir = root / "runs" / "run_scan_include_nested"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {
                    "mapper_globs": ["src/main/resources/*.xml"],
                    "java_scanner": {"jar_path": str(jar)},
                },
                "db": {"platform": "postgresql"},
            }
            units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")
            self.assertEqual(len(units), 1)
            self.assertEqual(units[0]["includeTrace"], ["demo.user.BaseWhere", "demo.user.NameFilter"])
            include_fragments = {x["ref"]: x["dynamicFeatures"] for x in units[0]["dynamicTrace"]["includeFragments"]}
            self.assertEqual(include_fragments["demo.user.NameFilter"], [])
            self.assertIn("IF", include_fragments["demo.user.BaseWhere"])
            self.assertIn("INCLUDE", include_fragments["demo.user.BaseWhere"])
            self.assertEqual(warnings, [])

    def test_run_scan_enriches_java_output_with_choose_dynamic_render_identity_when_sql_is_localizable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_choose_identity_") as td:
            root = Path(td)
            jar = root / "java" / "scan-agent" / "target" / "scan-agent-1.0.0.jar"
            jar.parent.mkdir(parents=True, exist_ok=True)
            jar.write_text("jar-placeholder", encoding="utf-8")
            mapper = root / "src" / "main" / "resources" / "demo_mapper.xml"
            mapper.parent.mkdir(parents=True, exist_ok=True)
            mapper.write_text(
                """<mapper namespace="demo.user.advanced">
  <select id="findUsersByKeyword" resultType="map">
    SELECT id, name FROM users
    <where>
      <choose>
        <when test="keyword != null and keyword != ''">
          name ILIKE #{keyword}
        </when>
        <otherwise>
          status = 'ACTIVE'
        </otherwise>
      </choose>
    </where>
  </select>
</mapper>""",
                encoding="utf-8",
            )
            run_dir = root / "runs" / "run_scan_choose_identity"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {
                    "mapper_globs": ["src/main/resources/*.xml"],
                    "java_scanner": {"jar_path": "java/scan-agent/target/scan-agent-1.0.0.jar"},
                },
                "db": {"platform": "postgresql"},
            }

            def _fake_run(cmd: list[str]) -> _Proc:
                out_idx = cmd.index("--out-jsonl") + 1
                out_path = Path(cmd[out_idx])
                row = {
                    "sqlKey": "demo.user.advanced.findUsersByKeyword#v1",
                    "statementKey": "demo.user.advanced.findUsersByKeyword",
                    "xmlPath": str(mapper),
                    "namespace": "demo.user.advanced",
                    "statementId": "findUsersByKeyword",
                    "statementType": "SELECT",
                    "variantId": "v1",
                    "sql": "SELECT id, name FROM users WHERE name ILIKE #{keyword}",
                    "parameterMappings": [],
                    "paramExample": {},
                    "locators": {"statementId": "findUsersByKeyword"},
                    "riskFlags": [],
                    "scanWarnings": None,
                }
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
                return _Proc(0, "", "")

            with patch("sqlopt.adapters.scanner_java.run_capture_text", side_effect=_fake_run):
                units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")

            self.assertEqual(len(units), 1)
            identity = units[0].get("dynamicRenderIdentity")
            self.assertIsInstance(identity, dict)
            self.assertEqual(identity["surfaceType"], "CHOOSE_BRANCH_BODY")
            self.assertEqual(identity["renderMode"], "CHOOSE_BRANCH_RENDERED")
            self.assertEqual(identity["branchKind"], "WHEN")
            self.assertEqual(identity["renderedBranchSql"], "name ILIKE #{keyword}")
            self.assertEqual(len(units[0]["dynamicTrace"]["chooseBranchSurfaces"]), 2)
            self.assertEqual(warnings, [])

    def test_run_scan_adds_sample_render_identity_for_flattened_choose(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_choose_flattened_") as td:
            root = Path(td)
            mapper = root / "src" / "main" / "resources" / "demo_mapper.xml"
            mapper.parent.mkdir(parents=True, exist_ok=True)
            mapper.write_text(
                """<mapper namespace="demo.user.advanced">
  <select id="findUsersByKeyword" resultType="map">
    SELECT id, name FROM users
    <where>
      <choose>
        <when test="keyword != null and keyword != ''">
          name ILIKE #{keyword}
        </when>
        <when test="status != null and status != ''">
          status = #{status}
        </when>
        <otherwise>
          status != 'DELETED'
        </otherwise>
      </choose>
    </where>
  </select>
</mapper>""",
                encoding="utf-8",
            )
            run_dir = root / "runs" / "run_scan_choose_flattened"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {
                    "mapper_globs": ["src/main/resources/*.xml"],
                },
                "db": {"platform": "postgresql"},
            }

            units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")

            self.assertEqual(len(units), 1)
            identity = units[0].get("dynamicRenderIdentity")
            self.assertIsInstance(identity, dict)
            self.assertEqual(identity["surfaceType"], "CHOOSE_BRANCH_BODY")
            self.assertEqual(identity["renderMode"], "CHOOSE_BRANCH_RENDERED")
            self.assertEqual(identity["branchKind"], "WHEN")
            self.assertEqual(identity["branchOrdinal"], 0)
            self.assertEqual(identity["renderedBranchSql"], "name ILIKE #{keyword}")
            self.assertEqual(identity["branchTestFingerprint"], "keyword != null and keyword != ''")
            self.assertEqual(len(units[0]["dynamicTrace"]["chooseBranchSurfaces"]), 3)
            self.assertEqual(
                units[0]["dynamicTrace"]["chooseBranchSurfaces"][0]["renderedBranchSql"],
                "name ILIKE #{keyword}",
            )
            self.assertEqual(warnings, [])

    def test_run_scan_fails_when_java_jar_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_") as td:
            root = Path(td)
            run_dir = root / "runs" / "run_scan_fail_jar"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {
                    "mapper_globs": ["src/main/resources/**/*.xml"],
                    "java_scanner": {"jar_path": "java/scan-agent/target/missing.jar"},
                },
                "db": {"platform": "postgresql"},
            }
            units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")
            self.assertEqual(units, [])
            self.assertEqual(warnings[0]["severity"], "fatal")
            self.assertEqual(warnings[0]["reason_code"], "SCAN_UNKNOWN_EXIT")
            self.assertIn("jar not found", warnings[0]["message"])

    def test_run_scan_resolves_relative_jar_and_uses_strict_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_") as td:
            root = Path(td)
            jar = root / "java" / "scan-agent" / "target" / "scan-agent-1.0.0.jar"
            jar.parent.mkdir(parents=True, exist_ok=True)
            jar.write_text("jar-placeholder", encoding="utf-8")
            run_dir = root / "runs" / "run_scan_java_exit"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {
                    "mapper_globs": ["src/main/resources/**/*.xml"],
                    "java_scanner": {"jar_path": "java/scan-agent/target/scan-agent-1.0.0.jar"},
                    "class_resolution": {"mode": "strict"},
                },
                "db": {"platform": "postgresql"},
            }
            with patch(
                "sqlopt.adapters.scanner_java.run_capture_text",
                return_value=_Proc(10, "", "{\"reason_code\":\"SCAN_TYPE_ATTR_SANITIZED\",\"severity\":\"degradable\"}\n"),
            ) as run_mock:
                out_path = run_dir / "artifacts" / "scan.jsonl"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(
                    json.dumps(
                        {
                            "sqlKey": "demo.user.findUsers#v1",
                            "statementKey": "demo.user.findUsers",
                            "xmlPath": "x.xml",
                            "namespace": "demo.user",
                            "statementId": "findUsers",
                            "statementType": "SELECT",
                            "variantId": "v1",
                            "sql": "SELECT * FROM users",
                            "parameterMappings": [],
                            "paramExample": {},
                            "locators": {"statementId": "findUsers"},
                            "riskFlags": [],
                            "scanWarnings": None,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")
            self.assertEqual(units, [])
            self.assertEqual(warnings[-1]["severity"], "fatal")
            self.assertIn("strict mode", warnings[-1]["message"])

    def test_run_scan_normalizes_java_default_v1_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_") as td:
            root = Path(td)
            jar = root / "java" / "scan-agent" / "target" / "scan-agent-1.0.0.jar"
            jar.parent.mkdir(parents=True, exist_ok=True)
            jar.write_text("jar-placeholder", encoding="utf-8")
            run_dir = root / "runs" / "run_scan_java_identity"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {
                    "mapper_globs": ["src/main/resources/**/*.xml"],
                    "java_scanner": {"jar_path": "java/scan-agent/target/scan-agent-1.0.0.jar"},
                },
                "db": {"platform": "postgresql"},
            }
            with patch(
                "sqlopt.adapters.scanner_java.run_capture_text",
                return_value=_Proc(0, "", ""),
            ) as run_mock:
                out_path = run_dir / "artifacts" / "scan.jsonl"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(
                    json.dumps(
                        {
                            "sqlKey": "demo.user.findUsers#v1",
                            "xmlPath": "x.xml",
                            "namespace": "demo.user",
                            "statementId": "findUsers",
                            "statementType": "SELECT",
                            "variantId": "v1",
                            "sql": "SELECT * FROM users",
                            "parameterMappings": [],
                            "paramExample": {},
                            "locators": {"statementId": "findUsers"},
                            "riskFlags": [],
                            "scanWarnings": None,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")

            self.assertEqual(warnings, [])
            self.assertEqual(units[0]["statementKey"], "demo.user.findUsers")
            self.assertEqual(units[0]["sqlKey"], "demo.user.findUsers")
            self.assertNotIn("variantId", units[0])
            cmd = run_mock.call_args.args[0]
            self.assertEqual(Path(cmd[2]), jar.resolve())

    def test_run_scan_reads_java_output_when_successful(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_") as td:
            root = Path(td)
            jar = root / "java" / "scan-agent" / "target" / "scan-agent-1.0.0.jar"
            jar.parent.mkdir(parents=True, exist_ok=True)
            jar.write_text("jar-placeholder", encoding="utf-8")
            run_dir = root / "runs" / "run_scan_java_ok"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {
                    "mapper_globs": ["src/main/resources/**/*.xml"],
                    "java_scanner": {"jar_path": "java/scan-agent/target/scan-agent-1.0.0.jar"},
                },
                "db": {"platform": "postgresql"},
            }

            def _fake_run(cmd: list[str]) -> _Proc:
                out_idx = cmd.index("--out-jsonl") + 1
                out_path = Path(cmd[out_idx])
                row = {
                    "sqlKey": "demo.user.findUsers#v1",
                    "xmlPath": "x.xml",
                    "namespace": "demo.user",
                    "statementId": "findUsers",
                    "statementType": "SELECT",
                    "variantId": "v1",
                    "sql": "SELECT * FROM users WHERE status = #{status}",
                    "parameterMappings": [],
                    "paramExample": {},
                    "locators": {"statementId": "findUsers"},
                    "riskFlags": [],
                    "scanWarnings": None,
                }
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
                return _Proc(0, "", "")

            with patch("sqlopt.adapters.scanner_java.run_capture_text", side_effect=_fake_run):
                units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")
            self.assertEqual(len(units), 1)
            self.assertEqual(units[0]["statementKey"], "demo.user.findUsers")
            self.assertEqual(units[0]["sqlKey"], "demo.user.findUsers")
            self.assertNotIn("variantId", units[0])
            self.assertEqual(warnings, [])

    def test_python_fallback_skips_non_mapper_xml(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_") as td:
            root = Path(td)
            mapper_dir = root / "src" / "main" / "resources"
            mapper_dir.mkdir(parents=True, exist_ok=True)
            (mapper_dir / "ok_mapper.xml").write_text(
                """<mapper namespace="demo.user"><select id="a">SELECT 1</select></mapper>""",
                encoding="utf-8",
            )
            (mapper_dir / "not_mapper.xml").write_text(
                """<configuration><select id="x">SELECT 2</select></configuration>""",
                encoding="utf-8",
            )
            run_dir = root / "runs" / "run_scan_fallback_non_mapper"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {"mapper_globs": ["src/main/resources/**/*.xml"]},
                "db": {"platform": "postgresql"},
            }
            units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")
            self.assertEqual(warnings, [])
            self.assertEqual(len(units), 1)
            self.assertEqual(units[0]["statementId"], "a")

    def test_python_fallback_supports_namespaced_mapper(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_") as td:
            root = Path(td)
            mapper_dir = root / "src" / "main" / "resources"
            mapper_dir.mkdir(parents=True, exist_ok=True)
            (mapper_dir / "ok_mapper_ns.xml").write_text(
                """<mapper xmlns="https://mybatis.org/schema/mybatis-mapper" namespace="demo.user"><select id="a">SELECT 1</select></mapper>""",
                encoding="utf-8",
            )
            run_dir = root / "runs" / "run_scan_fallback_ns"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {"mapper_globs": ["src/main/resources/**/*.xml"]},
                "db": {"platform": "postgresql"},
            }
            units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")
            self.assertEqual(warnings, [])
            self.assertEqual(len(units), 1)
            self.assertEqual(units[0]["statementId"], "a")

    def test_python_fallback_preserves_template_sql_and_dynamic_features(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_fallback_dynamic_") as td:
            root = Path(td)
            mapper_dir = root / "src" / "main" / "resources"
            mapper_dir.mkdir(parents=True, exist_ok=True)
            (mapper_dir / "ok_mapper.xml").write_text(
                """<mapper namespace="demo.user">
<sql id="BaseWhere">WHERE status = #{status}</sql>
<select id="a">
  SELECT id FROM users
  <include refid="BaseWhere" />
</select>
</mapper>""",
                encoding="utf-8",
            )
            run_dir = root / "runs" / "run_scan_fallback_dynamic"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {"mapper_globs": ["src/main/resources/**/*.xml"]},
                "db": {"platform": "postgresql"},
            }
            units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")
            self.assertEqual(warnings, [])
            self.assertEqual(len(units), 1)
            self.assertIn("WHERE status = #{status}", units[0]["sql"])
            self.assertIn("<include", units[0]["templateSql"])
            self.assertIn("INCLUDE", units[0]["dynamicFeatures"])
            self.assertEqual(units[0]["includeTrace"], ["demo.user.BaseWhere"])
            self.assertEqual(units[0]["dynamicTrace"]["includeFragments"][0]["ref"], "demo.user.BaseWhere")

    def test_python_fallback_writes_fragment_catalog_with_bindings_and_locators(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_fragment_catalog_") as td:
            root = Path(td)
            mapper_dir = root / "src" / "main" / "resources"
            mapper_dir.mkdir(parents=True, exist_ok=True)
            (mapper_dir / "ok_mapper.xml").write_text(
                """<mapper namespace="demo.user">
<sql id="BaseWhere">
  <if test="status != null">
    WHERE ${alias}.status = #{status}
  </if>
</sql>
<select id="a">
  SELECT ${alias}.id FROM users ${alias}
  <include refid="BaseWhere">
    <property name="alias" value="u" />
  </include>
</select>
</mapper>""",
                encoding="utf-8",
            )
            run_dir = root / "runs" / "run_scan_fragment_catalog"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {"mapper_globs": ["src/main/resources/**/*.xml"]},
                "db": {"platform": "postgresql"},
            }
            units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")
            self.assertEqual(warnings, [])
            self.assertEqual(len(units), 1)
            self.assertIn("range", units[0]["locators"])
            self.assertEqual(units[0]["templateTarget"], "SQL_FRAGMENT_DEPENDENT")
            self.assertEqual(units[0]["includeBindings"][0]["properties"][0]["name"], "alias")
            fragment_rows = [json.loads(line) for line in (run_dir / "artifacts" / "fragments.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(fragment_rows), 1)
            self.assertEqual(fragment_rows[0]["displayRef"], "demo.user.BaseWhere")
            self.assertIn("IF", fragment_rows[0]["dynamicFeatures"])
            self.assertIn("range", fragment_rows[0]["locators"])
            self.assertEqual(fragment_rows[0]["includeBindings"], [])

    def test_python_fallback_tracks_choose_bind_trim_where_set_features(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_feature_matrix_") as td:
            root = Path(td)
            mapper_dir = root / "src" / "main" / "resources"
            mapper_dir.mkdir(parents=True, exist_ok=True)
            (mapper_dir / "feature_mapper.xml").write_text(
                """<mapper namespace="demo.user">
<select id="pickUsers">
  <bind name="likeName" value="'%' + name + '%'" />
  SELECT id FROM users
  <where>
    <choose>
      <when test="name != null">name LIKE #{likeName}</when>
      <otherwise>status = 'ACTIVE'</otherwise>
    </choose>
  </where>
</select>
<update id="updateUser">
  UPDATE users
  <trim prefix="SET" suffixOverrides=",">
    <set>
      <if test="name != null">name = #{name},</if>
    </set>
  </trim>
  WHERE id = #{id}
</update>
</mapper>""",
                encoding="utf-8",
            )
            run_dir = root / "runs" / "run_scan_feature_matrix"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {"mapper_globs": ["src/main/resources/**/*.xml"]},
                "db": {"platform": "postgresql"},
            }
            units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")

            self.assertEqual(warnings, [])
            self.assertEqual(len(units), 2)
            by_id = {row["statementId"]: row for row in units}
            self.assertIn("BIND", by_id["pickUsers"]["dynamicFeatures"])
            self.assertIn("CHOOSE", by_id["pickUsers"]["dynamicFeatures"])
            self.assertIn("WHERE", by_id["pickUsers"]["dynamicFeatures"])
            self.assertTrue(str(by_id["pickUsers"]["templateSql"]).strip())
            self.assertIn("range", by_id["pickUsers"]["locators"])
            self.assertIn("TRIM", by_id["updateUser"]["dynamicFeatures"])
            self.assertIn("SET", by_id["updateUser"]["dynamicFeatures"])
            self.assertTrue(str(by_id["updateUser"]["templateSql"]).strip())
            self.assertIn("range", by_id["updateUser"]["locators"])
            self.assertNotIn("SET SET", by_id["updateUser"]["sql"])

    def test_run_scan_normalizes_duplicate_set_from_java_scanner_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_java_set_") as td:
            root = Path(td)
            jar = root / "scan-agent.jar"
            jar.write_text("stub", encoding="utf-8")
            run_dir = root / "runs" / "run_scan_java_set"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {
                    "mapper_globs": [],
                    "java_scanner": {"jar_path": str(jar)},
                    "enable_fragment_catalog": False,
                },
                "db": {"platform": "postgresql"},
            }
            java_rows = [
                {
                    "sqlKey": "demo.user.updateUser#v1",
                    "xmlPath": "demo.xml",
                    "namespace": "demo.user",
                    "statementId": "updateUser",
                    "statementType": "UPDATE",
                    "variantId": "v1",
                    "sql": "UPDATE users SET SET status = #{status} WHERE id = #{id}",
                    "dynamicFeatures": ["IF", "TRIM", "SET"],
                    "parameterMappings": [],
                    "paramExample": {},
                    "locators": {"statementId": "updateUser"},
                    "riskFlags": [],
                    "scanWarnings": None,
                }
            ]
            with patch.object(scanner_adapter, "_run_java_scanner", return_value=(java_rows, [])):
                units, warnings = scanner_adapter.run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")

            self.assertEqual(warnings, [])
            self.assertEqual(len(units), 1)
            self.assertEqual(units[0]["sql"], "UPDATE users SET status = #{status} WHERE id = #{id}")

    def test_run_scan_fixture_dynamic_tags_mapper_reports_expected_features(self) -> None:
        project_root = ROOT / "tests" / "fixtures"
        jar = ROOT / "java" / "scan-agent" / "target" / "scan-agent-1.0.0.jar"
        if not jar.exists():
            self.skipTest("scan-agent jar not built")

        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_fixture_dynamic_tags_") as td:
            run_dir = Path(td) / "runs" / "run_scan_fixture_dynamic_tags"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(project_root)},
                "scan": {
                    "mapper_globs": ["scan_samples/dynamic_tags_mapper.xml"],
                    "max_variants_per_statement": 3,
                    "java_scanner": {"jar_path": str(jar)},
                },
                "db": {"platform": "postgresql"},
            }

            units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")

            self.assertEqual(warnings, [])
            self.assertEqual(len(units), 2)
            by_id = {row["statementId"]: row for row in units}

            self.assertEqual(
                by_id["patchUserStatusAdvanced"]["sql"],
                "UPDATE users SET status = #{status} WHERE id = #{id}",
            )
            self.assertEqual(set(by_id["patchUserStatusAdvanced"]["dynamicFeatures"]), {"IF", "TRIM", "SET"})

            self.assertEqual(
                set(by_id["searchUsersAdvanced"]["dynamicFeatures"]),
                {"FOREACH", "INCLUDE", "IF", "CHOOSE", "WHERE", "BIND"},
            )
            self.assertEqual(
                by_id["searchUsersAdvanced"]["includeTrace"],
                ["demo.scan.ActiveOnly", "demo.scan.TenantGuard"],
            )
            self.assertEqual(
                by_id["searchUsersAdvanced"]["dynamicTrace"]["includeFragments"][1]["dynamicFeatures"],
                ["IF"],
            )

            fragment_rows = [
                json.loads(line)
                for line in (run_dir / "artifacts" / "fragments.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(fragment_rows), 2)
            self.assertEqual({row["displayRef"] for row in fragment_rows}, {"demo.scan.ActiveOnly", "demo.scan.TenantGuard"})


class ScanStageTest(unittest.TestCase):
    def test_scan_stage_validates_fragment_catalog_when_present(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_stage_fragments_") as td:
            run_dir = Path(td) / "runs" / "run_scan_stage_fragments"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "artifacts" / "fragments.jsonl").write_text(
                json.dumps(
                    {
                        "fragmentKey": "x.xml::demo.user.BaseWhere",
                        "displayRef": "demo.user.BaseWhere",
                        "xmlPath": "x.xml",
                        "namespace": "demo.user",
                        "fragmentId": "BaseWhere",
                        "templateSql": "WHERE status = #{status}",
                        "dynamicFeatures": [],
                        "includeTrace": [],
                        "dynamicTrace": {"templateFeatures": [], "includeFragments": [], "resolutionDegraded": False},
                        "includeBindings": [],
                        "locators": {"nodeType": "SQL_FRAGMENT", "fragmentId": "BaseWhere", "range": {"startLine": 1, "startColumn": 1, "endLine": 1, "endColumn": 10}},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            config = {"project": {"root_path": td}, "scan": {"mapper_globs": []}, "db": {"platform": "postgresql"}}
            validator = ContractValidator(ROOT)
            rows = [
                {
                    "sqlKey": "demo.user.a#v1",
                    "xmlPath": "x.xml",
                    "namespace": "demo.user",
                    "statementId": "a",
                    "statementType": "SELECT",
                    "variantId": "v1",
                    "sql": "SELECT 1",
                    "parameterMappings": [],
                    "paramExample": {},
                    "locators": {"statementId": "a"},
                    "riskFlags": [],
                    "scanWarnings": None,
                }
            ]
            with patch("sqlopt.stages.scan.run_scan", return_value=(rows, [])):
                units = scan.execute(config, run_dir, validator)
            self.assertEqual(len(units), 1)

    def test_scan_stage_accepts_include_trace_display_refs_when_fragment_catalog_exists(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_stage_displayref_") as td:
            run_dir = Path(td) / "runs" / "run_scan_stage_displayref"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "artifacts" / "fragments.jsonl").write_text(
                json.dumps(
                    {
                        "fragmentKey": "x.xml::demo.user.BaseWhere",
                        "displayRef": "demo.user.BaseWhere",
                        "xmlPath": "x.xml",
                        "namespace": "demo.user",
                        "fragmentId": "BaseWhere",
                        "templateSql": "WHERE status = #{status}",
                        "dynamicFeatures": [],
                        "includeTrace": [],
                        "dynamicTrace": {"templateFeatures": [], "includeFragments": [], "resolutionDegraded": False},
                        "includeBindings": [],
                        "locators": {"nodeType": "SQL_FRAGMENT", "fragmentId": "BaseWhere", "range": {"startLine": 1, "startColumn": 1, "endLine": 1, "endColumn": 10}},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            config = {"project": {"root_path": td}, "scan": {"mapper_globs": []}, "db": {"platform": "postgresql"}}
            validator = ContractValidator(ROOT)
            rows = [
                {
                    "sqlKey": "demo.user.a#v1",
                    "xmlPath": "x.xml",
                    "namespace": "demo.user",
                    "statementId": "a",
                    "statementType": "SELECT",
                    "variantId": "v1",
                    "sql": "SELECT 1",
                    "templateSql": "SELECT 1 <include refid=\"BaseWhere\" />",
                    "dynamicFeatures": ["INCLUDE"],
                    "includeTrace": ["demo.user.BaseWhere"],
                    "dynamicTrace": {"statementFeatures": ["INCLUDE"], "includeFragments": [{"ref": "demo.user.BaseWhere", "dynamicFeatures": []}]},
                    "parameterMappings": [],
                    "paramExample": {},
                    "locators": {"statementId": "a", "range": {"startLine": 1, "startColumn": 1, "endLine": 1, "endColumn": 10}},
                    "riskFlags": [],
                    "scanWarnings": None,
                }
            ]
            with patch("sqlopt.stages.scan.run_scan", return_value=(rows, [])):
                units = scan.execute(config, run_dir, validator)

            self.assertEqual(len(units), 1)
            self.assertEqual(units[0]["verification"]["status"], "VERIFIED")
            self.assertEqual(units[0]["verification"]["reason_code"], "SCAN_EVIDENCE_VERIFIED")

    def test_scan_stage_propagates_reason_code_from_warning(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_stage_") as td:
            run_dir = Path(td) / "runs" / "run_scan_stage_reason"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {"project": {"root_path": td}, "scan": {"mapper_globs": []}, "db": {"platform": "postgresql"}}
            validator = Mock()
            with patch("sqlopt.stages.scan.run_scan", return_value=([], [{"reason_code": "SCAN_UNKNOWN_EXIT"}])):
                with self.assertRaises(StageError) as cm:
                    scan.execute(config, run_dir, validator)
            self.assertEqual(cm.exception.reason_code, "SCAN_UNKNOWN_EXIT")

    def test_scan_stage_fails_when_success_ratio_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_stage_") as td:
            root = Path(td)
            mapper = root / "src" / "main" / "resources" / "demo_mapper.xml"
            mapper.parent.mkdir(parents=True, exist_ok=True)
            mapper.write_text(
                """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="demo.user">
  <select id="a">SELECT 1</select>
  <select id="b">SELECT 2</select>
</mapper>
""",
                encoding="utf-8",
            )
            run_dir = root / "runs" / "run_scan_stage_ratio"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {
                    "mapper_globs": ["src/main/resources/**/*.xml"],
                    "class_resolution": {"min_success_ratio": 0.9},
                },
                "db": {"platform": "postgresql"},
            }
            validator = Mock()
            with patch(
                "sqlopt.stages.scan.run_scan",
                return_value=(
                    [
                        {
                            "sqlKey": "demo.user.a#v1",
                            "xmlPath": str(mapper),
                            "namespace": "demo.user",
                            "statementId": "a",
                            "statementType": "SELECT",
                            "variantId": "v1",
                            "sql": "SELECT 1",
                            "parameterMappings": [],
                            "paramExample": {},
                            "locators": {"statementId": "a"},
                            "riskFlags": [],
                            "scanWarnings": None,
                        }
                    ],
                    [],
                ),
            ):
                with self.assertRaises(StageError) as cm:
                    scan.execute(config, run_dir, validator)
            self.assertEqual(cm.exception.reason_code, "SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD")

    def test_scan_stage_coverage_count_supports_xml_namespace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_stage_") as td:
            root = Path(td)
            mapper = root / "src" / "main" / "resources" / "demo_mapper_ns.xml"
            mapper.parent.mkdir(parents=True, exist_ok=True)
            mapper.write_text(
                """<?xml version="1.0" encoding="UTF-8" ?>
<mapper xmlns="https://mybatis.org/schema/mybatis-mapper" namespace="demo.user">
  <select id="a">SELECT 1</select>
  <select id="b">SELECT 2</select>
</mapper>
""",
                encoding="utf-8",
            )
            run_dir = root / "runs" / "run_scan_stage_ns"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {"mapper_globs": ["src/main/resources/**/*.xml"], "class_resolution": {"min_success_ratio": 1.0}},
                "db": {"platform": "postgresql"},
            }
            validator = Mock()
            with patch(
                "sqlopt.stages.scan.run_scan",
                return_value=(
                    [
                        {
                            "sqlKey": "demo.user.a#v1",
                            "xmlPath": str(mapper),
                            "namespace": "demo.user",
                            "statementId": "a",
                            "statementType": "SELECT",
                            "variantId": "v1",
                            "sql": "SELECT 1",
                            "parameterMappings": [],
                            "paramExample": {},
                            "locators": {"statementId": "a"},
                            "riskFlags": [],
                            "scanWarnings": None,
                        }
                    ],
                    [],
                ),
            ):
                with self.assertRaises(StageError) as cm:
                    scan.execute(config, run_dir, validator)
            self.assertEqual(cm.exception.reason_code, "SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD")

    def test_scan_stage_non_mapper_xml_not_counted_in_discovered(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_stage_") as td:
            root = Path(td)
            mapper_dir = root / "src" / "main" / "resources"
            mapper_dir.mkdir(parents=True, exist_ok=True)
            mapper = mapper_dir / "demo_mapper.xml"
            mapper.write_text(
                """<mapper namespace="demo.user"><select id="a">SELECT 1</select></mapper>""",
                encoding="utf-8",
            )
            (mapper_dir / "not_mapper.xml").write_text(
                """<configuration><select id="x">SELECT 2</select></configuration>""",
                encoding="utf-8",
            )
            run_dir = root / "runs" / "run_scan_stage_non_mapper_filtered"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(root)},
                "scan": {"mapper_globs": ["src/main/resources/**/*.xml"], "class_resolution": {"min_success_ratio": 1.0}},
                "db": {"platform": "postgresql"},
            }
            validator = Mock()
            rows = [
                {
                    "sqlKey": "demo.user.a#v1",
                    "xmlPath": str(mapper),
                    "namespace": "demo.user",
                    "statementId": "a",
                    "statementType": "SELECT",
                    "variantId": "v1",
                    "sql": "SELECT 1",
                    "parameterMappings": [],
                    "paramExample": {},
                    "locators": {"statementId": "a"},
                    "riskFlags": [],
                    "scanWarnings": None,
                }
            ]
            with patch("sqlopt.stages.scan.run_scan", return_value=(rows, [])):
                units = scan.execute(config, run_dir, validator)
            self.assertEqual(len(units), 1)
            self.assertEqual(units[0]["sqlKey"], "demo.user.a#v1")


if __name__ == "__main__":
    unittest.main()
