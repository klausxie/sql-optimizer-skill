from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sqlopt.contracts import ContractValidator
from sqlopt.errors import StageError
from sqlopt.stages import scan
from sqlopt.stages.scan import run_scan

ROOT = Path(__file__).resolve().parents[1]


class ScannerAdapterTest(unittest.TestCase):
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
            units, warnings = run_scan(
                config, run_dir, run_dir / "pipeline" / "manifest.jsonl"
            )
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
            units, warnings = run_scan(
                config, run_dir, run_dir / "pipeline" / "manifest.jsonl"
            )
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
            units, warnings = run_scan(
                config, run_dir, run_dir / "pipeline" / "manifest.jsonl"
            )
            self.assertEqual(warnings, [])
            self.assertEqual(len(units), 1)
            self.assertIn("WHERE status = #{status}", units[0]["sql"])
            self.assertIn("<include", units[0]["templateSql"])
            self.assertIn("INCLUDE", units[0]["dynamicFeatures"])
            self.assertEqual(units[0]["includeTrace"], ["demo.user.BaseWhere"])
            self.assertEqual(
                units[0]["dynamicTrace"]["includeFragments"][0]["ref"],
                "demo.user.BaseWhere",
            )

    def test_python_fallback_writes_fragment_catalog_with_bindings_and_locators(
        self,
    ) -> None:
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
            units, warnings = run_scan(
                config, run_dir, run_dir / "pipeline" / "manifest.jsonl"
            )
            self.assertEqual(warnings, [])
            self.assertEqual(len(units), 1)
            self.assertIn("range", units[0]["locators"])
            self.assertEqual(units[0]["templateTarget"], "SQL_FRAGMENT_DEPENDENT")
            self.assertEqual(
                units[0]["includeBindings"][0]["properties"][0]["name"], "alias"
            )
            fragment_rows = [
                json.loads(line)
                for line in (run_dir / "pipeline" / "scan" / "fragments.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
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
            units, warnings = run_scan(
                config, run_dir, run_dir / "pipeline" / "manifest.jsonl"
            )

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


class ScanStageTest(unittest.TestCase):
    def test_scan_stage_validates_fragment_catalog_when_present(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_stage_fragments_") as td:
            run_dir = Path(td) / "runs" / "run_scan_stage_fragments"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "scan").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "scan" / "fragments.jsonl").write_text(
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
                        "dynamicTrace": {
                            "templateFeatures": [],
                            "includeFragments": [],
                            "resolutionDegraded": False,
                        },
                        "includeBindings": [],
                        "locators": {
                            "nodeType": "SQL_FRAGMENT",
                            "fragmentId": "BaseWhere",
                            "range": {
                                "startLine": 1,
                                "startColumn": 1,
                                "endLine": 1,
                                "endColumn": 10,
                            },
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            config = {
                "project": {"root_path": td},
                "scan": {"mapper_globs": []},
                "db": {"platform": "postgresql"},
            }
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

    def test_scan_stage_accepts_include_trace_display_refs_when_fragment_catalog_exists(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_stage_displayref_") as td:
            run_dir = Path(td) / "runs" / "run_scan_stage_displayref"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "scan").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "scan" / "fragments.jsonl").write_text(
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
                        "dynamicTrace": {
                            "templateFeatures": [],
                            "includeFragments": [],
                            "resolutionDegraded": False,
                        },
                        "includeBindings": [],
                        "locators": {
                            "nodeType": "SQL_FRAGMENT",
                            "fragmentId": "BaseWhere",
                            "range": {
                                "startLine": 1,
                                "startColumn": 1,
                                "endLine": 1,
                                "endColumn": 10,
                            },
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            config = {
                "project": {"root_path": td},
                "scan": {"mapper_globs": []},
                "db": {"platform": "postgresql"},
            }
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
                    "templateSql": 'SELECT 1 <include refid="BaseWhere" />',
                    "dynamicFeatures": ["INCLUDE"],
                    "includeTrace": ["demo.user.BaseWhere"],
                    "dynamicTrace": {
                        "statementFeatures": ["INCLUDE"],
                        "includeFragments": [
                            {"ref": "demo.user.BaseWhere", "dynamicFeatures": []}
                        ],
                    },
                    "parameterMappings": [],
                    "paramExample": {},
                    "locators": {
                        "statementId": "a",
                        "range": {
                            "startLine": 1,
                            "startColumn": 1,
                            "endLine": 1,
                            "endColumn": 10,
                        },
                    },
                    "riskFlags": [],
                    "scanWarnings": None,
                }
            ]
            with patch("sqlopt.stages.scan.run_scan", return_value=(rows, [])):
                units = scan.execute(config, run_dir, validator)

            ledger_rows = [
                json.loads(line)
                for line in (run_dir / "pipeline" / "verification" / "ledger.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            self.assertEqual(len(units), 1)
            self.assertEqual(len(ledger_rows), 1)
            self.assertEqual(ledger_rows[0]["status"], "VERIFIED")
            self.assertEqual(ledger_rows[0]["reason_code"], "SCAN_EVIDENCE_VERIFIED")

    def test_scan_stage_propagates_reason_code_from_warning(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_scan_stage_") as td:
            run_dir = Path(td) / "runs" / "run_scan_stage_reason"
            run_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": td},
                "scan": {"mapper_globs": []},
                "db": {"platform": "postgresql"},
            }
            validator = Mock()
            with patch(
                "sqlopt.stages.scan.run_scan",
                return_value=([], [{"reason_code": "SCAN_UNKNOWN_EXIT"}]),
            ):
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
            self.assertEqual(
                cm.exception.reason_code, "SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD"
            )

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
                "scan": {
                    "mapper_globs": ["src/main/resources/**/*.xml"],
                    "class_resolution": {"min_success_ratio": 1.0},
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
            self.assertEqual(
                cm.exception.reason_code, "SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD"
            )

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
                "scan": {
                    "mapper_globs": ["src/main/resources/**/*.xml"],
                    "class_resolution": {"min_success_ratio": 1.0},
                },
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
