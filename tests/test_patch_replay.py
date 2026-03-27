from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path

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
