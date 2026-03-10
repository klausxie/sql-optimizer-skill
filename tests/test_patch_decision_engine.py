from __future__ import annotations

import unittest
from pathlib import Path

from sqlopt.stages.patch_decision_engine import decide_patch_result


def _skip_patch_result(**kwargs):
    return {
        "sqlKey": kwargs["sql_key"],
        "statementKey": kwargs["statement_key"],
        "selectionReason": {"code": kwargs["reason_code"], "message": kwargs["reason_message"]},
        "diffSummary": {"skipped": True},
        "applicable": kwargs.get("applicable"),
    }


def _finalize_generated_patch(**_kwargs):
    return {
        "selectionReason": {"code": "PATCH_SELECTED_SINGLE_PASS", "message": "selected"},
        "diffSummary": {"skipped": False},
        "applicable": True,
        "patchFiles": ["dummy.patch"],
    }


class PatchDecisionEngineTest(unittest.TestCase):
    def test_missing_locator_returns_locator_ambiguous(self) -> None:
        sql_unit = {"sqlKey": "demo.user.find#v1", "locators": {}}
        acceptance = {"sqlKey": "demo.user.find#v1", "status": "PASS", "rewrittenSql": "SELECT 1"}
        patch, ctx = decide_patch_result(
            sql_unit=sql_unit,
            acceptance=acceptance,
            run_dir=Path("/tmp"),
            acceptance_rows=[acceptance],
            project_root=Path("/tmp"),
            statement_key_fn=lambda x: x.split("#")[0],
            skip_patch_result=_skip_patch_result,
            finalize_generated_patch=_finalize_generated_patch,
            format_sql_for_patch=lambda x: x,
            normalize_sql_text=lambda x: " ".join(str(x).split()),
            format_template_ops_for_patch=lambda _sql, acc, _run: acc,
            detect_duplicate_clause_in_template_ops=lambda _acc: None,
            build_template_plan_patch=lambda _sql, _acc, _run: (None, 0, None),
            build_unified_patch=lambda _path, _id, _type, _sql: ("patch", 1),
        )

        self.assertEqual(ctx.statement_key, "demo.user.find")
        self.assertEqual(ctx.semantic_gate_status, "PASS")
        self.assertEqual(ctx.semantic_gate_confidence, "HIGH")
        self.assertEqual(patch["selectionReason"]["code"], "PATCH_LOCATOR_AMBIGUOUS")

    def test_dynamic_features_without_template_plan_returns_dynamic_template_rewrite_reason(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.find#v1",
            "locators": {"statementId": "find"},
            "statementType": "select",
            "statementId": "find",
            "xmlPath": "/tmp/demo_mapper.xml",
            "sql": "SELECT * FROM users",
            "dynamicFeatures": ["IF"],
            "dynamicTrace": {},
        }
        acceptance = {
            "sqlKey": "demo.user.find#v1",
            "status": "PASS",
            "rewrittenSql": "SELECT id FROM users",
            "selectedCandidateId": "c1",
        }
        patch, ctx = decide_patch_result(
            sql_unit=sql_unit,
            acceptance=acceptance,
            run_dir=Path("/tmp"),
            acceptance_rows=[acceptance],
            project_root=Path("/tmp"),
            statement_key_fn=lambda x: x.split("#")[0],
            skip_patch_result=_skip_patch_result,
            finalize_generated_patch=_finalize_generated_patch,
            format_sql_for_patch=lambda x: x,
            normalize_sql_text=lambda x: " ".join(str(x).split()),
            format_template_ops_for_patch=lambda _sql, acc, _run: acc,
            detect_duplicate_clause_in_template_ops=lambda _acc: None,
            build_template_plan_patch=lambda _sql, _acc, _run: (None, 0, None),
            build_unified_patch=lambda _path, _id, _type, _sql: ("patch", 1),
        )

        self.assertEqual(ctx.status, "PASS")
        self.assertEqual(ctx.semantic_gate_status, "PASS")
        self.assertEqual(ctx.semantic_gate_confidence, "HIGH")
        self.assertEqual(patch["selectionReason"]["code"], "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE")

    def test_semantic_gate_uncertain_blocks_patch_even_when_acceptance_passes(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.find#v1",
            "locators": {"statementId": "find"},
            "statementType": "select",
            "statementId": "find",
            "xmlPath": "/tmp/demo_mapper.xml",
            "sql": "SELECT * FROM users",
            "dynamicFeatures": [],
        }
        acceptance = {
            "sqlKey": "demo.user.find#v1",
            "status": "PASS",
            "rewrittenSql": "SELECT id FROM users",
            "selectedCandidateId": "c1",
            "semanticEquivalence": {"status": "UNCERTAIN"},
        }
        patch, ctx = decide_patch_result(
            sql_unit=sql_unit,
            acceptance=acceptance,
            run_dir=Path("/tmp"),
            acceptance_rows=[acceptance],
            project_root=Path("/tmp"),
            statement_key_fn=lambda x: x.split("#")[0],
            skip_patch_result=_skip_patch_result,
            finalize_generated_patch=_finalize_generated_patch,
            format_sql_for_patch=lambda x: x,
            normalize_sql_text=lambda x: " ".join(str(x).split()),
            format_template_ops_for_patch=lambda _sql, acc, _run: acc,
            detect_duplicate_clause_in_template_ops=lambda _acc: None,
            build_template_plan_patch=lambda _sql, _acc, _run: (None, 0, None),
            build_unified_patch=lambda _path, _id, _type, _sql: ("patch", 1),
        )

        self.assertEqual(ctx.status, "PASS")
        self.assertEqual(ctx.semantic_gate_status, "UNCERTAIN")
        self.assertEqual(ctx.semantic_gate_confidence, "LOW")
        self.assertEqual(patch["selectionReason"]["code"], "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS")

    def test_semantic_low_confidence_blocks_patch_even_when_status_passes(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.find#v1",
            "locators": {"statementId": "find"},
            "statementType": "select",
            "statementId": "find",
            "xmlPath": "/tmp/demo_mapper.xml",
            "sql": "SELECT * FROM users",
            "dynamicFeatures": [],
        }
        acceptance = {
            "sqlKey": "demo.user.find#v1",
            "status": "PASS",
            "rewrittenSql": "SELECT id FROM users",
            "selectedCandidateId": "c1",
            "semanticEquivalence": {"status": "PASS", "confidence": "LOW"},
        }
        patch, ctx = decide_patch_result(
            sql_unit=sql_unit,
            acceptance=acceptance,
            run_dir=Path("/tmp"),
            acceptance_rows=[acceptance],
            project_root=Path("/tmp"),
            statement_key_fn=lambda x: x.split("#")[0],
            skip_patch_result=_skip_patch_result,
            finalize_generated_patch=_finalize_generated_patch,
            format_sql_for_patch=lambda x: x,
            normalize_sql_text=lambda x: " ".join(str(x).split()),
            format_template_ops_for_patch=lambda _sql, acc, _run: acc,
            detect_duplicate_clause_in_template_ops=lambda _acc: None,
            build_template_plan_patch=lambda _sql, _acc, _run: (None, 0, None),
            build_unified_patch=lambda _path, _id, _type, _sql: ("patch", 1),
        )

        self.assertEqual(ctx.semantic_gate_status, "PASS")
        self.assertEqual(ctx.semantic_gate_confidence, "LOW")
        self.assertEqual(patch["selectionReason"]["code"], "PATCH_SEMANTIC_CONFIDENCE_LOW")


if __name__ == "__main__":
    unittest.main()
