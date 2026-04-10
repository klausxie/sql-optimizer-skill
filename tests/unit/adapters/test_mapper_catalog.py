from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.adapters.mapper_catalog import enrich_sql_units_with_catalog


class MapperCatalogTest(unittest.TestCase):
    def test_enrich_sql_units_with_catalog_adds_choose_dynamic_render_identity_for_localizable_branch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_mapper_catalog_") as td:
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
        <otherwise>
          status = 'ACTIVE'
        </otherwise>
      </choose>
    </where>
  </select>
</mapper>""",
                encoding="utf-8",
            )
            units = [
                {
                    "sqlKey": "demo.user.advanced.findUsersByKeyword",
                    "statementKey": "demo.user.advanced.findUsersByKeyword",
                    "xmlPath": str(mapper),
                    "namespace": "demo.user.advanced",
                    "statementId": "findUsersByKeyword",
                    "statementType": "SELECT",
                    "sql": "SELECT id, name FROM users WHERE name ILIKE #{keyword}",
                    "parameterMappings": [],
                    "paramExample": {},
                    "locators": {"statementId": "findUsersByKeyword"},
                    "riskFlags": [],
                }
            ]

            enriched_units, _ = enrich_sql_units_with_catalog(units, root, ["src/main/resources/*.xml"])

            identity = enriched_units[0].get("dynamicRenderIdentity")
            self.assertIsInstance(identity, dict)
            self.assertEqual(identity["surfaceType"], "CHOOSE_BRANCH_BODY")
            self.assertEqual(identity["renderMode"], "CHOOSE_BRANCH_RENDERED")
            self.assertEqual(identity["branchKind"], "WHEN")
            self.assertEqual(identity["branchOrdinal"], 0)
            self.assertEqual(identity["renderedBranchSql"], "name ILIKE #{keyword}")
            self.assertEqual(identity["requiredEnvelopeShape"], "TOP_LEVEL_WHERE_CHOOSE")
            self.assertEqual(identity["requiredSiblingShape"]["branchCount"], 2)
            self.assertEqual(
                enriched_units[0]["dynamicTrace"]["chooseBranchSurfaces"],
                [
                    {
                        "surfaceType": "CHOOSE_BRANCH_BODY",
                        "chooseOrdinal": 0,
                        "branchOrdinal": 0,
                        "branchKind": "WHEN",
                        "renderedBranchSql": "name ILIKE #{keyword}",
                        "requiredEnvelopeShape": "TOP_LEVEL_WHERE_CHOOSE",
                        "branchTestFingerprint": "keyword != null and keyword != ''",
                    },
                    {
                        "surfaceType": "CHOOSE_BRANCH_BODY",
                        "chooseOrdinal": 0,
                        "branchOrdinal": 1,
                        "branchKind": "OTHERWISE",
                        "renderedBranchSql": "status = 'ACTIVE'",
                        "requiredEnvelopeShape": "TOP_LEVEL_WHERE_CHOOSE",
                    },
                ],
            )

    def test_enrich_sql_units_with_catalog_adds_sample_render_identity_for_flattened_choose(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_mapper_catalog_") as td:
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
            units = [
                {
                    "sqlKey": "demo.user.advanced.findUsersByKeyword",
                    "statementKey": "demo.user.advanced.findUsersByKeyword",
                    "xmlPath": str(mapper),
                    "namespace": "demo.user.advanced",
                    "statementId": "findUsersByKeyword",
                    "statementType": "SELECT",
                    "sql": (
                        "SELECT id, name FROM users "
                        "WHERE (name ILIKE #{keyword} OR status = #{status} OR status != 'DELETED')"
                    ),
                    "parameterMappings": [],
                    "paramExample": {},
                    "locators": {"statementId": "findUsersByKeyword"},
                    "riskFlags": [],
                }
            ]

            enriched_units, _ = enrich_sql_units_with_catalog(units, root, ["src/main/resources/*.xml"])

            identity = enriched_units[0].get("dynamicRenderIdentity")
            self.assertIsInstance(identity, dict)
            self.assertEqual(identity["surfaceType"], "CHOOSE_BRANCH_BODY")
            self.assertEqual(identity["renderMode"], "CHOOSE_BRANCH_RENDERED")
            self.assertEqual(identity["branchKind"], "WHEN")
            self.assertEqual(identity["branchOrdinal"], 0)
            self.assertEqual(identity["renderedBranchSql"], "name ILIKE #{keyword}")
            self.assertEqual(identity["branchTestFingerprint"], "keyword != null and keyword != ''")
            self.assertEqual(identity["requiredEnvelopeShape"], "TOP_LEVEL_WHERE_CHOOSE")
            self.assertEqual(identity["requiredSiblingShape"]["branchCount"], 3)
            self.assertEqual(
                enriched_units[0]["dynamicTrace"]["chooseBranchSurfaces"],
                [
                    {
                        "surfaceType": "CHOOSE_BRANCH_BODY",
                        "chooseOrdinal": 0,
                        "branchOrdinal": 0,
                        "branchKind": "WHEN",
                        "renderedBranchSql": "name ILIKE #{keyword}",
                        "requiredEnvelopeShape": "TOP_LEVEL_WHERE_CHOOSE",
                        "branchTestFingerprint": "keyword != null and keyword != ''",
                    },
                    {
                        "surfaceType": "CHOOSE_BRANCH_BODY",
                        "chooseOrdinal": 0,
                        "branchOrdinal": 1,
                        "branchKind": "WHEN",
                        "renderedBranchSql": "status = #{status}",
                        "requiredEnvelopeShape": "TOP_LEVEL_WHERE_CHOOSE",
                        "branchTestFingerprint": "status != null and status != ''",
                    },
                    {
                        "surfaceType": "CHOOSE_BRANCH_BODY",
                        "chooseOrdinal": 0,
                        "branchOrdinal": 2,
                        "branchKind": "OTHERWISE",
                        "renderedBranchSql": "status != 'DELETED'",
                        "requiredEnvelopeShape": "TOP_LEVEL_WHERE_CHOOSE",
                    },
                ],
            )
