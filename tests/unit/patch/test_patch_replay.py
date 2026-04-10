from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
import re

from sqlopt.platforms.sql.dynamic_surface_locator import locate_choose_branch_body_range
from sqlopt.stages.patching_render import build_range_patch
from sqlopt.verification.patch_replay import replay_patch_target


@contextmanager
def _mapper_path(body: str):
    with tempfile.TemporaryDirectory(prefix="patch_replay_") as td:
        path = Path(td) / "demo_mapper.xml"
        path.write_text(body, encoding="utf-8")
        yield path


def test_replay_patch_target_detects_target_drift() -> None:
    with _mapper_path(
        """<mapper namespace="demo.user">
  <sql id="BaseWhere">WHERE active = 1</sql>
  <select id="countUser">SELECT COUNT(*) FROM users <include refid="BaseWhere" /></select>
</mapper>"""
    ) as xml_path:
        result = replay_patch_target(
            sql_unit={
                "xmlPath": str(xml_path),
                "namespace": "demo.user",
                "statementId": "countUser",
            },
            patch_target={
                "targetSql": "SELECT COUNT(*) FROM users",
                "templateRewriteOps": [
                    {
                        "op": "replace_statement_body",
                        "afterTemplate": 'SELECT COUNT(*) FROM users <include refid="BaseWhere" />',
                    }
                ],
                "replayContract": {
                    "replayMode": "STATEMENT_TEMPLATE_SAFE",
                    "requiredTemplateOps": ["replace_statement_body"],
                    "expectedRenderedSql": "SELECT COUNT(*) FROM users WHERE active = 1",
                    "expectedRenderedSqlNormalized": "SELECT COUNT(*) FROM users WHERE active = 1",
                    "expectedFingerprint": {"kind": "normalized_sql", "value": "SELECT COUNT(*) FROM users WHERE active = 1"},
                    "requiredAnchors": [],
                    "requiredIncludes": ["demo.user.BaseWhere"],
                    "requiredPlaceholderShape": [],
                    "dialectSyntaxCheckRequired": True,
                },
            },
            fragment_catalog={},
        )

    assert result.matches_target is False
    assert result.drift_reason == "PATCH_TARGET_DRIFT"


def test_replay_patch_target_rejects_anchor_loss() -> None:
    with _mapper_path(
        """<mapper namespace="demo.user">
  <select id="findUsers">SELECT * FROM users <where>status = #{status}</where></select>
</mapper>"""
    ) as xml_path:
        result = replay_patch_target(
            sql_unit={
                "xmlPath": str(xml_path),
                "namespace": "demo.user",
                "statementId": "findUsers",
            },
            patch_target={
                "targetSql": "SELECT * FROM users WHERE status = #{status}",
                "templateRewriteOps": [
                    {
                        "op": "replace_statement_body",
                        "afterTemplate": "SELECT * FROM users WHERE status = #{status}",
                    }
                ],
                "replayContract": {
                    "replayMode": "STATEMENT_TEMPLATE_SAFE",
                    "requiredTemplateOps": ["replace_statement_body"],
                    "expectedRenderedSql": "SELECT * FROM users WHERE status = #{status}",
                    "expectedRenderedSqlNormalized": "SELECT * FROM users WHERE status = #{status}",
                    "expectedFingerprint": {"kind": "normalized_sql", "value": "SELECT * FROM users WHERE status = #{status}"},
                    "requiredAnchors": ["<where>"],
                    "requiredIncludes": [],
                    "requiredPlaceholderShape": ["#{status}"],
                    "dialectSyntaxCheckRequired": True,
                },
            },
            fragment_catalog={},
        )

    assert result.matches_target is False
    assert result.drift_reason == "PATCH_ANCHOR_LOSS"


def test_replay_patch_target_rejects_include_loss() -> None:
    with _mapper_path(
        """<mapper namespace="demo.user">
  <sql id="BaseWhere">WHERE active = 1</sql>
  <select id="findUsers">SELECT * FROM users <include refid="BaseWhere" /></select>
</mapper>"""
    ) as xml_path:
        result = replay_patch_target(
            sql_unit={
                "xmlPath": str(xml_path),
                "namespace": "demo.user",
                "statementId": "findUsers",
            },
            patch_target={
                "targetSql": "SELECT * FROM users WHERE active = 1",
                "templateRewriteOps": [
                    {
                        "op": "replace_statement_body",
                        "afterTemplate": "SELECT * FROM users WHERE active = 1",
                    }
                ],
                "replayContract": {
                    "replayMode": "STATEMENT_TEMPLATE_SAFE",
                    "requiredTemplateOps": ["replace_statement_body"],
                    "expectedRenderedSql": "SELECT * FROM users WHERE active = 1",
                    "expectedRenderedSqlNormalized": "SELECT * FROM users WHERE active = 1",
                    "expectedFingerprint": {"kind": "normalized_sql", "value": "SELECT * FROM users WHERE active = 1"},
                    "requiredAnchors": [],
                    "requiredIncludes": ["demo.user.BaseWhere"],
                    "requiredPlaceholderShape": [],
                    "dialectSyntaxCheckRequired": True,
                },
            },
            fragment_catalog={},
        )

    assert result.matches_target is False
    assert result.drift_reason == "PATCH_INCLUDE_LOSS"


def test_replay_patch_target_rejects_placeholder_shape_drift() -> None:
    with _mapper_path(
        """<mapper namespace="demo.user">
  <select id="findUsers">SELECT * FROM users WHERE status = #{status} AND created_at >= #{createdAfter}</select>
</mapper>"""
    ) as xml_path:
        result = replay_patch_target(
            sql_unit={
                "xmlPath": str(xml_path),
                "namespace": "demo.user",
                "statementId": "findUsers",
            },
            patch_target={
                "targetSql": "SELECT * FROM users WHERE status = #{status}",
                "templateRewriteOps": [
                    {
                        "op": "replace_statement_body",
                        "afterTemplate": "SELECT * FROM users WHERE status = #{status}",
                    }
                ],
                "replayContract": {
                    "replayMode": "STATEMENT_TEMPLATE_SAFE",
                    "requiredTemplateOps": ["replace_statement_body"],
                    "expectedRenderedSql": "SELECT * FROM users WHERE status = #{status}",
                    "expectedRenderedSqlNormalized": "SELECT * FROM users WHERE status = #{status}",
                    "expectedFingerprint": {"kind": "normalized_sql", "value": "SELECT * FROM users WHERE status = #{status}"},
                    "requiredAnchors": [],
                    "requiredIncludes": [],
                    "requiredPlaceholderShape": ["#{status}", "#{createdAfter}"],
                    "dialectSyntaxCheckRequired": True,
                },
            },
            fragment_catalog={},
        )

    assert result.matches_target is False
    assert result.drift_reason == "PATCH_PLACEHOLDER_SHAPE_DRIFT"


def test_replay_patch_target_rejects_if_test_drift() -> None:
    with _mapper_path(
        """<mapper namespace="demo.user">
  <select id="findUsers">
    SELECT id FROM users
    <where>
      <if test="status != null">AND status = #{status}</if>
    </where>
  </select>
</mapper>"""
    ) as xml_path:
        result = replay_patch_target(
            sql_unit={
                "xmlPath": str(xml_path),
                "namespace": "demo.user",
                "statementId": "findUsers",
            },
            patch_target={
                "targetSql": "SELECT id FROM users WHERE status = #{status}",
                "templateRewriteOps": [
                    {
                        "op": "replace_statement_body",
                        "afterTemplate": (
                            "SELECT id FROM users <where>"
                            '<if test="status != null and status != \'\'">AND status = #{status}</if>'
                            "</where>"
                        ),
                    }
                ],
                "replayContract": {
                    "replayMode": "STATEMENT_TEMPLATE_SAFE",
                    "requiredTemplateOps": ["replace_statement_body"],
                    "expectedRenderedSql": "SELECT id FROM users WHERE status = #{status}",
                    "expectedRenderedSqlNormalized": "SELECT id FROM users WHERE status = #{status}",
                    "expectedFingerprint": {
                        "kind": "normalized_sql",
                        "value": "SELECT id FROM users WHERE status = #{status}",
                    },
                    "requiredAnchors": ["<where>"],
                    "requiredIncludes": [],
                    "requiredPlaceholderShape": ["#{status}"],
                    "requiredIfTestShape": ["status != null"],
                    "requiredIfBodyShape": ["AND status = #{status}"],
                    "dialectSyntaxCheckRequired": True,
                },
            },
            fragment_catalog={},
        )

    assert result.matches_target is False
    assert result.drift_reason == "PATCH_DYNAMIC_IF_TEST_DRIFT"


def test_replay_patch_target_rejects_if_body_drift() -> None:
    with _mapper_path(
        """<mapper namespace="demo.user">
  <select id="findUsers">
    SELECT id FROM users
    <where>
      <if test="status != null">AND status = #{status}</if>
    </where>
  </select>
</mapper>"""
    ) as xml_path:
        result = replay_patch_target(
            sql_unit={
                "xmlPath": str(xml_path),
                "namespace": "demo.user",
                "statementId": "findUsers",
            },
            patch_target={
                "targetSql": "SELECT id FROM users WHERE user_status = #{status}",
                "templateRewriteOps": [
                    {
                        "op": "replace_statement_body",
                        "afterTemplate": (
                            "SELECT id FROM users <where>"
                            '<if test="status != null">AND user_status = #{status}</if>'
                            "</where>"
                        ),
                    }
                ],
                "replayContract": {
                    "replayMode": "STATEMENT_TEMPLATE_SAFE",
                    "requiredTemplateOps": ["replace_statement_body"],
                    "expectedRenderedSql": "SELECT id FROM users WHERE user_status = #{status}",
                    "expectedRenderedSqlNormalized": "SELECT id FROM users WHERE user_status = #{status}",
                    "expectedFingerprint": {
                        "kind": "normalized_sql",
                        "value": "SELECT id FROM users WHERE user_status = #{status}",
                    },
                    "requiredAnchors": ["<where>"],
                    "requiredIncludes": [],
                    "requiredPlaceholderShape": ["#{status}"],
                    "requiredIfTestShape": ["status != null"],
                    "requiredIfBodyShape": ["AND status = #{status}"],
                    "dialectSyntaxCheckRequired": True,
                },
            },
            fragment_catalog={},
        )

    assert result.matches_target is False
    assert result.drift_reason == "PATCH_DYNAMIC_IF_BODY_DRIFT"


def test_replay_patch_target_accepts_choose_branch_local_edit() -> None:
    with _mapper_path(
        """<mapper namespace="demo.user.advanced">
  <select id="findUsersByKeyword">
    SELECT id, name, email, status, created_at, updated_at
    FROM users
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
</mapper>"""
    ) as xml_path:
        target_anchor = {
            "surfaceType": "CHOOSE_BRANCH_BODY",
            "chooseOrdinal": 0,
            "branchKind": "WHEN",
            "branchOrdinal": 0,
            "whereEnvelopeRequired": True,
            "branchTestFingerprint": "keyword != null and keyword != ''",
        }
        range_info = locate_choose_branch_body_range(xml_path.read_text(encoding="utf-8"), target_anchor)
        assert range_info is not None
        patch_text, _ = build_range_patch(xml_path, range_info, "email ILIKE #{keyword}")
        target_sql = (
            "SELECT id, name, email, status, created_at, updated_at "
            "FROM users WHERE email ILIKE #{keyword}"
        )
        result = replay_patch_target(
            sql_unit={
                "xmlPath": str(xml_path),
                "namespace": "demo.user.advanced",
                "statementId": "findUsersByKeyword",
                "templateSql": (
                    "SELECT id, name, email, status, created_at, updated_at FROM users "
                    "<where><choose><when test=\"keyword != null and keyword != ''\">"
                    "name ILIKE #{keyword}</when><otherwise>status = 'ACTIVE'</otherwise></choose></where>"
                ),
            },
            patch_target={
                "targetSql": target_sql,
                "templateRewriteOps": [
                    {
                        "op": "replace_choose_branch_body",
                        "targetSurface": "CHOOSE_BRANCH_BODY",
                        "targetAnchor": target_anchor,
                        "afterTemplate": "email ILIKE #{keyword}",
                    }
                ],
                "replayContract": {
                    "replayMode": "DYNAMIC_CHOOSE_BRANCH_TEMPLATE_SAFE",
                    "requiredTemplateOps": ["replace_choose_branch_body"],
                    "expectedRenderedSql": target_sql,
                    "expectedRenderedSqlNormalized": target_sql,
                    "expectedFingerprint": {"kind": "normalized_sql", "value": target_sql},
                    "requiredAnchors": [],
                    "requiredIncludes": [],
                    "requiredPlaceholderShape": ["#{keyword}"],
                    "dialectSyntaxCheckRequired": True,
                    "targetSurface": "CHOOSE_BRANCH_BODY",
                    "targetAnchor": target_anchor,
                    "requiredSurfaceIdentity": {
                        "branchCount": 2,
                        "targetBranchKind": "WHEN",
                        "targetBranchTestFingerprint": "keyword != null and keyword != ''",
                    },
                    "requiredSiblingShape": {
                        "siblingBranchCount": 1,
                        "siblingBranchFingerprints": [
                            {
                                "branchKind": "OTHERWISE",
                                "bodyFingerprint": "status = 'ACTIVE'",
                                "testFingerprint": "",
                            }
                        ],
                    },
                    "requiredEnvelopeShape": {
                        "whereEnvelopePresent": True,
                        "outerChooseCount": 1,
                        "outerUnsupportedTagsAbsent": True,
                    },
                    "surfaceFallbackAllowed": False,
                },
            },
            fragment_catalog={},
            patch_text=patch_text,
        )

    assert result.matches_target is True
    assert result.drift_reason is None


def test_replay_patch_target_rejects_choose_branch_sibling_drift() -> None:
    with _mapper_path(
        """<mapper namespace="demo.user.advanced">
  <select id="findUsersByKeyword">
    SELECT id, name, email, status, created_at, updated_at
    FROM users
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
</mapper>"""
    ) as xml_path:
        target_anchor = {
            "surfaceType": "CHOOSE_BRANCH_BODY",
            "chooseOrdinal": 0,
            "branchKind": "WHEN",
            "branchOrdinal": 0,
            "whereEnvelopeRequired": True,
            "branchTestFingerprint": "keyword != null and keyword != ''",
        }
        range_info = locate_choose_branch_body_range(xml_path.read_text(encoding="utf-8"), target_anchor)
        assert range_info is not None
        patch_text, _ = build_range_patch(xml_path, range_info, "email ILIKE #{keyword}")
        target_sql = (
            "SELECT id, name, email, status, created_at, updated_at "
            "FROM users WHERE email ILIKE #{keyword}"
        )
        result = replay_patch_target(
            sql_unit={
                "xmlPath": str(xml_path),
                "namespace": "demo.user.advanced",
                "statementId": "findUsersByKeyword",
                "templateSql": (
                    "SELECT id, name, email, status, created_at, updated_at FROM users "
                    "<where><choose><when test=\"keyword != null and keyword != ''\">"
                    "name ILIKE #{keyword}</when><otherwise>status = 'ACTIVE'</otherwise></choose></where>"
                ),
            },
            patch_target={
                "targetSql": target_sql,
                "templateRewriteOps": [
                    {
                        "op": "replace_choose_branch_body",
                        "targetSurface": "CHOOSE_BRANCH_BODY",
                        "targetAnchor": target_anchor,
                        "afterTemplate": "email ILIKE #{keyword}",
                    }
                ],
                "replayContract": {
                    "replayMode": "DYNAMIC_CHOOSE_BRANCH_TEMPLATE_SAFE",
                    "requiredTemplateOps": ["replace_choose_branch_body"],
                    "expectedRenderedSql": target_sql,
                    "expectedRenderedSqlNormalized": target_sql,
                    "expectedFingerprint": {"kind": "normalized_sql", "value": target_sql},
                    "requiredAnchors": [],
                    "requiredIncludes": [],
                    "requiredPlaceholderShape": ["#{keyword}"],
                    "dialectSyntaxCheckRequired": True,
                    "targetSurface": "CHOOSE_BRANCH_BODY",
                    "targetAnchor": target_anchor,
                    "requiredSurfaceIdentity": {
                        "branchCount": 2,
                        "targetBranchKind": "WHEN",
                        "targetBranchTestFingerprint": "keyword != null and keyword != ''",
                    },
                    "requiredSiblingShape": {
                        "siblingBranchCount": 1,
                        "siblingBranchFingerprints": [
                            {
                                "branchKind": "OTHERWISE",
                                "bodyFingerprint": "status = 'PENDING'",
                                "testFingerprint": "",
                            }
                        ],
                    },
                    "requiredEnvelopeShape": {
                        "whereEnvelopePresent": True,
                        "outerChooseCount": 1,
                        "outerUnsupportedTagsAbsent": True,
                    },
                    "surfaceFallbackAllowed": False,
                },
            },
            fragment_catalog={},
            patch_text=patch_text,
        )

    assert result.matches_target is False
    assert result.drift_reason == "PATCH_DYNAMIC_CHOOSE_SIBLING_DRIFT"


def test_replay_patch_target_uses_fragment_artifact_output_for_fragment_ops() -> None:
    with _mapper_path(
        """<mapper namespace="demo.user">
  <sql id="BaseWhere">WHERE status = #{status}</sql>
  <select id="findUsers">SELECT * FROM users <include refid="BaseWhere" /></select>
</mapper>"""
    ) as xml_path:
        original = xml_path.read_text(encoding="utf-8")
        fragment_body = "WHERE status = #{status}"
        start = original.index(fragment_body)
        end = start + len(fragment_body)
        patch_text, changed_lines = build_range_patch(
            xml_path,
            {"startOffset": start, "endOffset": end},
            "WHERE status = #{status} AND active = 1",
        )
        assert patch_text is not None
        assert changed_lines > 0
        fragment_key = f"{xml_path.resolve()}::demo.user.BaseWhere"

        result = replay_patch_target(
            sql_unit={
                "xmlPath": str(xml_path),
                "namespace": "demo.user",
                "statementId": "findUsers",
            },
            patch_target={
                "targetSql": "WHERE status = #{status} AND active = 1",
                "templateRewriteOps": [
                    {
                        "op": "replace_fragment_body",
                        "targetRef": fragment_key,
                        "afterTemplate": "WHERE status = #{status} AND active = 1",
                    }
                ],
                "replayContract": {
                    "replayMode": "FRAGMENT_TEMPLATE_SAFE",
                    "requiredTemplateOps": ["replace_fragment_body"],
                    "expectedRenderedSql": "WHERE status = #{status} AND active = 1",
                    "expectedRenderedSqlNormalized": "WHERE status = #{status} AND active = 1",
                    "expectedFingerprint": {
                        "kind": "normalized_sql",
                        "value": "WHERE status = #{status} AND active = 1",
                    },
                    "requiredAnchors": [],
                    "requiredIncludes": [],
                    "requiredPlaceholderShape": ["#{status}"],
                    "dialectSyntaxCheckRequired": True,
                },
            },
            fragment_catalog={
                fragment_key: {
                    "fragmentKey": fragment_key,
                    "xmlPath": str(xml_path),
                    "namespace": "demo.user",
                    "templateSql": fragment_body,
                }
            },
            patch_text=patch_text,
        )

    assert result.matches_target is True
    assert result.drift_reason is None


def test_replay_patch_target_tolerates_operator_spacing_drift_in_choose_filters() -> None:
    with _mapper_path(
        """<mapper namespace="demo.user.advanced">
  <select id="listUsersFilteredAliasedChoose">
    SELECT id AS id, name AS name, email AS email, status AS status, created_at AS created_at, updated_at AS updated_at
    FROM users
    <where>
      <choose>
        <when test="status != null and status != ''">status = #{status}</when>
        <otherwise>status != 'DELETED'</otherwise>
      </choose>
    </where>
    ORDER BY created_at DESC
  </select>
</mapper>"""
    ) as xml_path:
        original = xml_path.read_text(encoding="utf-8")
        match = re.search(
            r'(<select id="listUsersFilteredAliasedChoose">)([\s\S]*?)(</select>)',
            original,
        )
        assert match is not None
        after = (
            "SELECT id, name, email, status, created_at, updated_at "
            "FROM users\n"
            "    <where>\n"
            "      <choose>\n"
            "        <when test=\"status != null and status != ''\">status = #{status}</when>\n"
            "        <otherwise>status != 'DELETED'</otherwise>\n"
            "      </choose>\n"
            "    </where>\n"
            "    ORDER BY created_at DESC"
        )
        start, end = match.span(2)
        patch_text, changed_lines = build_range_patch(
            xml_path,
            {"startOffset": start, "endOffset": end},
            after,
        )
        assert patch_text is not None
        assert changed_lines > 0

        result = replay_patch_target(
            sql_unit={
                "xmlPath": str(xml_path),
                "namespace": "demo.user.advanced",
                "statementId": "listUsersFilteredAliasedChoose",
            },
            patch_target={
                "targetSql": (
                    "SELECT id, name, email, status, created_at, updated_at FROM users "
                    "WHERE (status = #{status} OR status != 'DELETED') ORDER BY created_at DESC"
                ),
                "templateRewriteOps": [
                    {
                        "op": "replace_statement_body",
                        "afterTemplate": after,
                    }
                ],
                "replayContract": {
                    "replayMode": "STATEMENT_TEMPLATE_SAFE",
                    "requiredTemplateOps": ["replace_statement_body"],
                    "expectedRenderedSql": (
                        "SELECT id, name, email, status, created_at, updated_at FROM users "
                        "WHERE (status = #{status} OR status != 'DELETED') ORDER BY created_at DESC"
                    ),
                    "expectedRenderedSqlNormalized": (
                        "SELECT id, name, email, status, created_at, updated_at FROM users "
                        "WHERE (status = #{status} OR status != 'DELETED') ORDER BY created_at DESC"
                    ),
                    "expectedFingerprint": {
                        "kind": "normalized_sql",
                        "value": (
                            "SELECT id, name, email, status, created_at, updated_at FROM users "
                            "WHERE (status = #{status} OR status != 'DELETED') ORDER BY created_at DESC"
                        ),
                    },
                    "requiredAnchors": [],
                    "requiredIncludes": [],
                    "requiredPlaceholderShape": ["#{status}"],
                    "dialectSyntaxCheckRequired": True,
                },
            },
            fragment_catalog={},
            patch_text=patch_text,
        )

    assert result.matches_target is True
    assert result.drift_reason is None


def test_replay_patch_target_tolerates_union_keyword_spacing_drift() -> None:
    with _mapper_path(
        """<mapper namespace="demo.shipment.harness">
  <select id="listShipmentStatusUnionWrapped">
    SELECT id, status, shipped_at FROM (
      SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED'
      UNION
      SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED'
    ) su ORDER BY status, id
  </select>
</mapper>"""
    ) as xml_path:
        original = xml_path.read_text(encoding="utf-8")
        match = re.search(
            r'(<select id="listShipmentStatusUnionWrapped">)([\s\S]*?)(</select>)',
            original,
        )
        assert match is not None
        after = (
            "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED'\n"
            "    UNION\n"
            "    SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED'\n"
            "    ORDER BY status, id"
        )
        start, end = match.span(2)
        patch_text, changed_lines = build_range_patch(
            xml_path,
            {"startOffset": start, "endOffset": end},
            after,
        )
        assert patch_text is not None
        assert changed_lines > 0

        result = replay_patch_target(
            sql_unit={
                "xmlPath": str(xml_path),
                "namespace": "demo.shipment.harness",
                "statementId": "listShipmentStatusUnionWrapped",
            },
            patch_target={
                "targetSql": (
                    "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED' "
                    "UNION SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED' "
                    "ORDER BY status, id"
                ),
                "templateRewriteOps": [
                    {
                        "op": "replace_statement_body",
                        "afterTemplate": after,
                    }
                ],
                "replayContract": {
                    "replayMode": "STATEMENT_TEMPLATE_SAFE",
                    "requiredTemplateOps": ["replace_statement_body"],
                    "expectedRenderedSql": (
                        "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED' "
                        "UNION SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED' "
                        "ORDER BY status, id"
                    ),
                    "expectedRenderedSqlNormalized": (
                        "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED' "
                        "UNION SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED' "
                        "ORDER BY status, id"
                    ),
                    "expectedFingerprint": {
                        "kind": "normalized_sql",
                        "value": (
                            "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED' "
                            "UNION SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED' "
                            "ORDER BY status, id"
                        ),
                    },
                    "requiredAnchors": [],
                    "requiredIncludes": [],
                    "requiredPlaceholderShape": [],
                    "dialectSyntaxCheckRequired": True,
                },
            },
            fragment_catalog={},
            patch_text=patch_text,
        )

    assert result.matches_target is True
    assert result.drift_reason is None
