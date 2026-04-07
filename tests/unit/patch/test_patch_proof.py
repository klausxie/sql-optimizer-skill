from __future__ import annotations

import unittest

from sqlopt.stages.patch_build import PatchBuildResult
from sqlopt.stages.patch_proof import _build_patch_target
from sqlopt.stages.patch_select import PatchSelectionContext


class PatchProofTest(unittest.TestCase):
    def test_count_wrapper_uses_replay_expected_sql_as_patch_target(self) -> None:
        selection = PatchSelectionContext(
            rewritten_sql="SELECT COUNT(1) FROM users WHERE status = #{status}",
            selected_candidate_id="unwrap-subquery",
            semantic_equivalence={"status": "PASS", "confidence": "HIGH"},
            semantic_gate_status="PASS",
            semantic_gate_confidence="HIGH",
            rewrite_facts={},
            dynamic_candidate_intent=None,
            dynamic_template=None,
            patchability={"blockingReasons": []},
            selected_patch_strategy={"strategyType": "DYNAMIC_STATEMENT_TEMPLATE_EDIT"},
            patch_strategy_candidates=[],
            rewrite_materialization={
                "mode": "STATEMENT_TEMPLATE_SAFE",
                "replayContract": {
                    "replayMode": "STATEMENT_TEMPLATE_SAFE",
                    "requiredTemplateOps": ["replace_statement_body"],
                    "expectedRenderedSql": "SELECT COUNT(*) FROM users WHERE status = #{status}",
                },
            },
            template_rewrite_ops=[{"op": "replace_statement_body", "afterTemplate": "SELECT COUNT(*) FROM users"}],
            family="DYNAMIC_COUNT_WRAPPER_COLLAPSE",
        )
        build = PatchBuildResult(
            selected_patch_strategy={"strategyType": "DYNAMIC_STATEMENT_TEMPLATE_EDIT"},
            rewrite_materialization=selection.rewrite_materialization,
            template_rewrite_ops=selection.template_rewrite_ops,
            family="DYNAMIC_COUNT_WRAPPER_COLLAPSE",
            artifact_kind="TEMPLATE",
            target_kind="statement",
            target_ref="countUsersFilteredWrapped",
        )

        patch_target = _build_patch_target(
            sql_unit={"sqlKey": "demo.user.advanced.countUsersFilteredWrapped"},
            selection=selection,
            build=build,
        )

        assert patch_target is not None
        self.assertEqual(
            patch_target["targetSql"],
            "SELECT COUNT(*) FROM users WHERE status = #{status}",
        )

