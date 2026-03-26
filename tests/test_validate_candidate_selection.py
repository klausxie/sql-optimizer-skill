from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from sqlopt.patch_families.registry import lookup_patch_family_spec
from sqlopt.platforms.sql.validator_sql import validate_proposal


class ValidateCandidateSelectionTest(unittest.TestCase):
    def test_selects_best_improved_candidate_by_cost(self) -> None:
        sql_unit = {"sqlKey": "demo.user.listUsers#v1", "sql": "SELECT * FROM users", "statementType": "SELECT"}
        proposal = {
            "llmCandidates": [
                {"id": "c1", "rewrittenSql": "SELECT id FROM users", "rewriteStrategy": "projection"},
                {"id": "c2", "rewrittenSql": "SELECT id FROM users ORDER BY created_at DESC", "rewriteStrategy": "projection"},
            ],
            "suggestions": [],
        }
        config = {"db": {"dsn": "postgresql://dummy"}, "validate": {}, "policy": {}}

        def fake_semantics(_cfg, _orig, _rewritten, _dir):
            return {
                "checked": True,
                "method": "sql_semantic_compare_v2",
                "rowCount": {"status": "MATCH"},
                "keySetHash": {"status": "MATCH"},
                "evidenceRefs": [],
            }

        def fake_plan(_cfg, _orig, rewritten, _dir):
            if rewritten == "SELECT id FROM users":
                return {
                    "checked": True,
                    "method": "sql_explain_json_compare",
                    "beforeSummary": {"totalCost": 10.0},
                    "afterSummary": {"totalCost": 9.0},
                    "reasonCodes": ["TOTAL_COST_REDUCED"],
                    "improved": True,
                    "evidenceRefs": [],
                }
            return {
                "checked": True,
                "method": "sql_explain_json_compare",
                "beforeSummary": {"totalCost": 10.0},
                "afterSummary": {"totalCost": 8.0},
                "reasonCodes": ["TOTAL_COST_REDUCED"],
                "improved": True,
                "evidenceRefs": [],
            }

        with tempfile.TemporaryDirectory(prefix="validate_pick_") as td:
            with patch("sqlopt.platforms.sql.validator_sql.compare_semantics", side_effect=fake_semantics), patch(
                "sqlopt.platforms.sql.validator_sql.compare_plan", side_effect=fake_plan
            ):
                result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result.to_contract()["status"], "PASS")
        self.assertEqual(result["rewrittenSql"], "SELECT id FROM users ORDER BY created_at DESC")
        self.assertEqual(result.get("selectedCandidateId"), "c2")
        self.assertEqual(result.get("selectedCandidateSource"), "llm")
        self.assertEqual(result.get("selectionRationale", {}).get("strategy"), "PATCHABILITY_FIRST")
        self.assertEqual(result.get("deliveryReadiness", {}).get("tier"), "READY")
        self.assertEqual(result.get("decisionLayers", {}).get("delivery", {}).get("tier"), "READY")
        self.assertEqual(result.get("decisionLayers", {}).get("acceptance", {}).get("status"), "PASS")
        self.assertGreaterEqual(len(result.get("candidateEvaluations") or []), 2)
        self.assertEqual((result.get("equivalence") or {}).get("keySetHash", {}).get("status"), "MATCH")

    def test_prefers_more_patchable_candidate_before_best_cost(self) -> None:
        sql_unit = {"sqlKey": "demo.user.listUsers#v1", "sql": "SELECT * FROM users", "statementType": "SELECT"}
        proposal = {
            "llmCandidates": [
                {"id": "c1", "rewrittenSql": "SELECT id FROM users ORDER BY created_at DESC", "rewriteStrategy": "sort"},
            ],
            "suggestions": [{"action": "PROJECT_COLUMNS", "sql": "SELECT id FROM users"}],
        }
        config = {"db": {"dsn": "postgresql://dummy"}, "validate": {}, "policy": {}}

        def fake_semantics(_cfg, _orig, _rewritten, _dir):
            return {"checked": True, "method": "sql_semantic_compare_v1", "rowCount": {"status": "MATCH"}, "evidenceRefs": []}

        def fake_plan(_cfg, _orig, rewritten, _dir):
            if rewritten == "SELECT id FROM users ORDER BY created_at DESC":
                return {
                    "checked": True,
                    "method": "sql_explain_json_compare",
                    "beforeSummary": {"totalCost": 10.0},
                    "afterSummary": {"totalCost": 7.0},
                    "reasonCodes": ["TOTAL_COST_REDUCED"],
                    "improved": True,
                    "evidenceRefs": [],
                }
            return {
                "checked": True,
                "method": "sql_explain_json_compare",
                "beforeSummary": {"totalCost": 10.0},
                "afterSummary": {"totalCost": 9.0},
                "reasonCodes": ["TOTAL_COST_REDUCED"],
                "improved": True,
                "evidenceRefs": [],
            }

        with tempfile.TemporaryDirectory(prefix="validate_patchability_first_") as td:
            with patch("sqlopt.platforms.sql.validator_sql.compare_semantics", side_effect=fake_semantics), patch(
                "sqlopt.platforms.sql.validator_sql.compare_plan", side_effect=fake_plan
            ):
                result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))

        self.assertEqual(result["rewrittenSql"], "SELECT id FROM users")
        self.assertEqual(result.get("selectedCandidateSource"), "rule")
        evals = result.get("candidateEvaluations") or []
        self.assertGreater((evals[1].get("patchabilityScore") if len(evals) > 1 else 0), evals[0].get("patchabilityScore"))
        self.assertEqual(result.get("decisionLayers", {}).get("delivery", {}).get("selectedCandidateSource"), "rule")

    def test_rule_candidate_is_used_when_llm_candidate_invalid(self) -> None:
        sql_unit = {"sqlKey": "demo.user.listUsers#v1", "sql": "SELECT * FROM users ORDER BY created_at DESC", "statementType": "SELECT"}
        proposal = {
            "llmCandidates": [{"id": "bad", "rewrittenSql": "SELECT * FROM users ORDER BY ${orderBy}"}],
            "suggestions": [{"action": "PROJECT_COLUMNS", "sql": "SELECT id FROM users ORDER BY created_at DESC"}],
        }
        config = {"db": {"dsn": "postgresql://dummy"}, "validate": {}, "policy": {}}

        def fake_semantics(_cfg, _orig, _rewritten, _dir):
            return {"checked": True, "method": "sql_semantic_compare_v1", "rowCount": {"status": "MATCH"}, "evidenceRefs": []}

        def fake_plan(_cfg, _orig, _rewritten, _dir):
            return {
                "checked": True,
                "method": "sql_explain_json_compare",
                "beforeSummary": {"totalCost": 20.0},
                "afterSummary": {"totalCost": 10.0},
                "reasonCodes": ["TOTAL_COST_REDUCED"],
                "improved": True,
                "evidenceRefs": [],
            }

        with tempfile.TemporaryDirectory(prefix="validate_rule_") as td:
            with patch("sqlopt.platforms.sql.validator_sql.compare_semantics", side_effect=fake_semantics), patch(
                "sqlopt.platforms.sql.validator_sql.compare_plan", side_effect=fake_plan
            ):
                result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["rewrittenSql"], "SELECT id FROM users ORDER BY created_at DESC")
        self.assertEqual(result.get("selectedCandidateSource"), "rule")
        self.assertEqual(result.get("selectionRationale", {}).get("strategy"), "PATCHABILITY_FIRST")
        self.assertTrue(result.get("decisionLayers", {}).get("feasibility", {}).get("ready"))

    def test_rejects_question_mark_candidate_when_original_uses_hash_placeholder(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.findUsersByStatusRecent#v1",
            "sql": "SELECT id FROM users WHERE status = #{status}",
            "statementType": "SELECT",
        }
        proposal = {
            "llmCandidates": [{"id": "c1", "rewrittenSql": "SELECT id FROM users WHERE status = ?"}],
            "suggestions": [],
        }
        config = {"db": {"dsn": "postgresql://dummy"}, "validate": {}, "policy": {}}

        def fake_semantics(_cfg, _orig, _rewritten, _dir):
            return {"checked": True, "method": "sql_semantic_compare_v1", "rowCount": {"status": "MATCH"}, "evidenceRefs": []}

        def fake_plan(_cfg, _orig, _rewritten, _dir):
            return {
                "checked": True,
                "method": "sql_explain_json_compare",
                "beforeSummary": {"totalCost": 10.0},
                "afterSummary": {"totalCost": 10.0},
                "reasonCodes": ["TOTAL_COST_NOT_REDUCED"],
                "improved": False,
                "evidenceRefs": [],
            }

        with tempfile.TemporaryDirectory(prefix="validate_placeholder_") as td:
            with patch("sqlopt.platforms.sql.validator_sql.compare_semantics", side_effect=fake_semantics), patch(
                "sqlopt.platforms.sql.validator_sql.compare_plan", side_effect=fake_plan
            ):
                result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))

        self.assertEqual(result["rewrittenSql"], sql_unit["sql"])
        self.assertIn("VALIDATE_PLACEHOLDER_SEMANTICS_MISMATCH_WARN", result.get("warnings", []))

    def test_validate_emits_rewrite_materialization_for_static_sql(self) -> None:
        sql_unit = {"sqlKey": "demo.user.listUsers#v1", "sql": "SELECT * FROM users", "statementType": "SELECT"}
        proposal = {"llmCandidates": [], "suggestions": []}
        config = {"db": {}, "validate": {}, "patch": {}, "policy": {}}

        with tempfile.TemporaryDirectory(prefix="validate_materialization_") as td:
            result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td), fragment_catalog={})

        self.assertEqual(result["rewriteMaterialization"]["mode"], "STATEMENT_SQL")
        self.assertEqual(result["templateRewriteOps"], [])

    def test_validate_persists_patch_target_contract_for_ready_family(self) -> None:
        with tempfile.TemporaryDirectory(prefix="validate_patch_target_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            xml_path.write_text(
                """<mapper namespace="demo.user">
  <sql id="userBaseQuery">SELECT id FROM users</sql>
  <select id="countUser">select count(1) from (<include refid="userBaseQuery" />) tmp</select>
</mapper>""",
                encoding="utf-8",
            )
            base_ref = f"{xml_path.resolve()}::demo.user.userBaseQuery"
            sql_unit = {
                "sqlKey": "demo.user.countUser#v2",
                "sql": "select count(1) from ( SELECT id FROM users ) tmp",
                "statementType": "SELECT",
                "xmlPath": str(xml_path),
                "namespace": "demo.user",
                "statementId": "countUser",
                "templateSql": 'select count(1) from (<include refid="userBaseQuery" />) tmp',
                "dynamicFeatures": ["INCLUDE"],
                "includeBindings": [{"ref": base_ref, "properties": [], "bindingHash": "base"}],
                "primaryFragmentTarget": base_ref,
            }
            fragment_catalog = {
                base_ref: {
                    "fragmentKey": base_ref,
                    "xmlPath": str(xml_path),
                    "namespace": "demo.user",
                    "templateSql": "SELECT id FROM users",
                    "dynamicFeatures": [],
                    "includeBindings": [],
                }
            }
            proposal = {
                "llmCandidates": [
                    {
                        "id": "c1",
                        "rewrittenSql": "SELECT COUNT(*) FROM users",
                        "rewriteStrategy": "ELIMINATE_UNNECESSARY_SUBQUERY",
                    }
                ],
                "suggestions": [],
            }
            config = {"db": {"dsn": "postgresql://dummy"}, "validate": {}, "patch": {}, "policy": {}}

            def fake_semantics(_cfg, _orig, _rewritten, _dir):
                return {
                    "checked": True,
                    "method": "sql_semantic_compare_v2",
                    "rowCount": {"status": "MATCH"},
                    "keySetHash": {"status": "MATCH"},
                    "rowSampleHash": {"status": "MATCH"},
                    "evidenceRefs": [],
                    "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
                }

            def fake_plan(_cfg, _orig, _rewritten, _dir):
                return {
                    "checked": True,
                    "method": "sql_explain_json_compare",
                    "beforeSummary": {"totalCost": 10.0},
                    "afterSummary": {"totalCost": 8.0},
                    "reasonCodes": ["TOTAL_COST_REDUCED"],
                    "improved": True,
                    "evidenceRefs": [],
                }

            with patch("sqlopt.platforms.sql.validator_sql.compare_semantics", side_effect=fake_semantics), patch(
                "sqlopt.platforms.sql.validator_sql.compare_plan", side_effect=fake_plan
            ):
                result = validate_proposal(
                    sql_unit,
                    proposal,
                    True,
                    config=config,
                    evidence_dir=Path(td),
                    fragment_catalog=fragment_catalog,
                )

        patch_target = result.to_contract()["patchTarget"]
        self.assertEqual(patch_target["family"], "STATIC_INCLUDE_WRAPPER_COLLAPSE")
        self.assertEqual(patch_target["targetSql"], "SELECT COUNT(*) FROM users")
        self.assertEqual(patch_target["semanticGateStatus"], "PASS")
        self.assertEqual(patch_target["semanticGateConfidence"], "HIGH")
        self.assertEqual(patch_target["replayContract"]["expectedRenderedSql"], "SELECT COUNT(*) FROM users")
        self.assertTrue(patch_target["targetSqlNormalized"])
        self.assertTrue(patch_target["targetSqlFingerprint"])

    def test_validate_persists_static_alias_projection_cleanup_patch_target_for_ready_alias_only_case(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.advanced.listUsersProjectedAliases#v20",
            "sql": "SELECT id AS id, name AS name, email AS email FROM users ORDER BY created_at DESC",
            "statementType": "SELECT",
        }
        proposal = {
            "llmCandidates": [
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, name, email FROM users ORDER BY created_at DESC",
                    "rewriteStrategy": "REMOVE_REDUNDANT_PROJECTION_ALIASES",
                }
            ],
            "suggestions": [],
        }
        config = {"db": {"dsn": "postgresql://dummy"}, "validate": {}, "patch": {}, "policy": {}}

        def fake_semantics(_cfg, _orig, _rewritten, _dir):
            return {
                "checked": True,
                "method": "sql_semantic_compare_v2",
                "rowCount": {"status": "MATCH"},
                "keySetHash": {"status": "MATCH"},
                "rowSampleHash": {"status": "MATCH"},
                "evidenceRefs": [],
                "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
            }

        def fake_plan(_cfg, _orig, _rewritten, _dir):
            return {
                "checked": True,
                "method": "sql_explain_json_compare",
                "beforeSummary": {"totalCost": 10.0},
                "afterSummary": {"totalCost": 8.0},
                "reasonCodes": ["TOTAL_COST_REDUCED"],
                "improved": True,
                "evidenceRefs": [],
            }

        with tempfile.TemporaryDirectory(prefix="validate_static_alias_cleanup_") as td:
            with patch("sqlopt.platforms.sql.validator_sql.compare_semantics", side_effect=fake_semantics), patch(
                "sqlopt.platforms.sql.validator_sql.compare_plan", side_effect=fake_plan
            ):
                result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))

        patch_target = result.to_contract()["patchTarget"]
        self.assertEqual(patch_target["family"], "STATIC_ALIAS_PROJECTION_CLEANUP")
        self.assertEqual(patch_target["selectedPatchStrategy"]["strategyType"], "EXACT_TEMPLATE_EDIT")

    def test_validate_blocks_qualified_alias_neighbor_from_static_alias_projection_cleanup(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.advanced.listUsersProjectedQualifiedAliases#v21",
            "sql": "SELECT u.id AS id, u.name AS name, u.email AS email FROM users u ORDER BY u.created_at DESC",
            "statementType": "SELECT",
        }
        proposal = {
            "llmCandidates": [
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT u.id, u.name, u.email FROM users u ORDER BY u.created_at DESC",
                    "rewriteStrategy": "REMOVE_REDUNDANT_PROJECTION_ALIASES",
                }
            ],
            "suggestions": [],
        }
        config = {"db": {"dsn": "postgresql://dummy"}, "validate": {}, "patch": {}, "policy": {}}

        def fake_semantics(_cfg, _orig, _rewritten, _dir):
            return {
                "checked": True,
                "method": "sql_semantic_compare_v2",
                "rowCount": {"status": "MATCH"},
                "keySetHash": {"status": "MATCH"},
                "rowSampleHash": {"status": "MATCH"},
                "evidenceRefs": [],
                "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
            }

        def fake_plan(_cfg, _orig, _rewritten, _dir):
            return {
                "checked": True,
                "method": "sql_explain_json_compare",
                "beforeSummary": {"totalCost": 10.0},
                "afterSummary": {"totalCost": 8.0},
                "reasonCodes": ["TOTAL_COST_REDUCED"],
                "improved": True,
                "evidenceRefs": [],
            }

        with tempfile.TemporaryDirectory(prefix="validate_static_alias_neighbor_") as td:
            with patch("sqlopt.platforms.sql.validator_sql.compare_semantics", side_effect=fake_semantics), patch(
                "sqlopt.platforms.sql.validator_sql.compare_plan", side_effect=fake_plan
            ):
                result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))

        contract = result.to_contract()
        self.assertIsNone(contract.get("patchTarget"))
        self.assertIsNone(contract.get("selectedPatchStrategy"))
        self.assertEqual((contract.get("patchability") or {}).get("blockingReason"), "STATIC_ALIAS_PROJECTION_CLEANUP_SCOPE_MISMATCH")

    def test_validate_requires_registered_family_spec_before_persisting_patch_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="validate_patch_target_missing_spec_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            xml_path.write_text(
                """<mapper namespace="demo.user">
  <sql id="userBaseQuery">SELECT id FROM users</sql>
  <select id="countUser">select count(1) from (<include refid="userBaseQuery" />) tmp</select>
</mapper>""",
                encoding="utf-8",
            )
            base_ref = f"{xml_path.resolve()}::demo.user.userBaseQuery"
            sql_unit = {
                "sqlKey": "demo.user.countUser#v2",
                "sql": "select count(1) from ( SELECT id FROM users ) tmp",
                "statementType": "SELECT",
                "xmlPath": str(xml_path),
                "namespace": "demo.user",
                "statementId": "countUser",
                "templateSql": 'select count(1) from (<include refid="userBaseQuery" />) tmp',
                "dynamicFeatures": ["INCLUDE"],
                "includeBindings": [{"ref": base_ref, "properties": [], "bindingHash": "base"}],
                "primaryFragmentTarget": base_ref,
            }
            fragment_catalog = {
                base_ref: {
                    "fragmentKey": base_ref,
                    "xmlPath": str(xml_path),
                    "namespace": "demo.user",
                    "templateSql": "SELECT id FROM users",
                    "dynamicFeatures": [],
                    "includeBindings": [],
                }
            }
            proposal = {
                "llmCandidates": [
                    {
                        "id": "c1",
                        "rewrittenSql": "SELECT COUNT(*) FROM users",
                        "rewriteStrategy": "ELIMINATE_UNNECESSARY_SUBQUERY",
                    }
                ],
                "suggestions": [],
            }
            config = {"db": {"dsn": "postgresql://dummy"}, "validate": {}, "patch": {}, "policy": {}}

            def fake_semantics(_cfg, _orig, _rewritten, _dir):
                return {
                    "checked": True,
                    "method": "sql_semantic_compare_v2",
                    "rowCount": {"status": "MATCH"},
                    "keySetHash": {"status": "MATCH"},
                    "rowSampleHash": {"status": "MATCH"},
                    "evidenceRefs": [],
                    "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
                }

            def fake_plan(_cfg, _orig, _rewritten, _dir):
                return {
                    "checked": True,
                    "method": "sql_explain_json_compare",
                    "beforeSummary": {"totalCost": 10.0},
                    "afterSummary": {"totalCost": 8.0},
                    "reasonCodes": ["TOTAL_COST_REDUCED"],
                    "improved": True,
                    "evidenceRefs": [],
                }

            with patch("sqlopt.platforms.sql.validator_sql.compare_semantics", side_effect=fake_semantics), patch(
                "sqlopt.platforms.sql.validator_sql.compare_plan", side_effect=fake_plan
            ), patch("sqlopt.platforms.sql.validator_sql.lookup_patch_family_spec", return_value=None, create=True):
                result = validate_proposal(
                    sql_unit,
                    proposal,
                    True,
                    config=config,
                    evidence_dir=Path(td),
                    fragment_catalog=fragment_catalog,
                )

        self.assertIsNone(result.to_contract().get("patchTarget"))

    def test_validate_uses_registered_acceptance_policy_for_confidence_gate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="validate_patch_target_acceptance_policy_") as td:
            sql_unit = {
                "sqlKey": "demo.user.countUser#v2",
                "sql": "select count(1) from ( select id from users ) tmp",
                "statementType": "SELECT",
            }
            proposal = {
                "llmCandidates": [
                    {
                        "id": "c1",
                        "rewrittenSql": "SELECT COUNT(*) FROM users",
                        "rewriteStrategy": "ELIMINATE_UNNECESSARY_SUBQUERY",
                    }
                ],
                "suggestions": [],
            }
            config = {"db": {"dsn": "postgresql://dummy"}, "validate": {}, "patch": {}, "policy": {}}
            fake_spec = lookup_patch_family_spec("STATIC_INCLUDE_WRAPPER_COLLAPSE")
            assert fake_spec is not None
            fake_spec = replace(fake_spec, acceptance=replace(fake_spec.acceptance, semantic_min_confidence="HIGH"))

            def fake_semantics(_cfg, _orig, _rewritten, _dir):
                return {
                    "checked": True,
                    "method": "sql_semantic_compare_v2",
                    "rowCount": {"status": "MATCH"},
                    "evidenceRefs": [],
                }

            def fake_plan(_cfg, _orig, _rewritten, _dir):
                return {
                    "checked": True,
                    "method": "sql_explain_json_compare",
                    "beforeSummary": {"totalCost": 10.0},
                    "afterSummary": {"totalCost": 8.0},
                    "reasonCodes": ["TOTAL_COST_REDUCED"],
                    "improved": True,
                    "evidenceRefs": [],
                }

            fake_patch_plan = (
                {
                    "dynamicTemplate": {
                        "capabilityProfile": {
                            "baselineFamily": "STATIC_INCLUDE_WRAPPER_COLLAPSE",
                        }
                    }
                },
                None,
                {"eligible": True},
                {"strategyType": "SAFE_WRAPPER_COLLAPSE"},
                [],
                {
                    "mode": "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE",
                    "replayVerified": True,
                    "replayContract": {
                        "replayMode": "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE",
                        "requiredTemplateOps": ["replace_statement_body"],
                        "expectedRenderedSql": "SELECT COUNT(*) FROM users",
                        "expectedRenderedSqlNormalized": "SELECT COUNT(*) FROM users",
                        "expectedFingerprint": {"kind": "normalized_sql", "value": "SELECT COUNT(*) FROM users"},
                        "requiredAnchors": [],
                        "requiredIncludes": [],
                        "requiredPlaceholderShape": [],
                        "dialectSyntaxCheckRequired": True,
                    },
                },
                [],
            )

            with patch("sqlopt.platforms.sql.validator_sql.compare_semantics", side_effect=fake_semantics), patch(
                "sqlopt.platforms.sql.validator_sql.compare_plan", side_effect=fake_plan
            ), patch("sqlopt.platforms.sql.validator_sql.plan_patch_strategy", return_value=fake_patch_plan), patch(
                "sqlopt.platforms.sql.validator_sql.lookup_patch_family_spec",
                return_value=fake_spec,
                create=True,
            ):
                result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))

        self.assertIsNone(result.to_contract().get("patchTarget"))

    def test_validate_rejects_text_fallback_candidate(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.countUser#v2",
            "sql": "select count(1) from ( select id from users ) tmp",
            "statementType": "SELECT",
        }
        proposal = {
            "llmCandidates": [
                {
                    "id": "fallback:text",
                    "rewrittenSql": "The main optimization is removing the unnecessary subquery wrapper.",
                    "rewriteStrategy": "opencode_text_fallback",
                }
            ],
            "suggestions": [],
        }
        config = {"db": {"dsn": "postgresql://dummy"}, "validate": {}, "policy": {}}

        with tempfile.TemporaryDirectory(prefix="validate_text_fallback_") as td:
            result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))

        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result.get("feedback", {}).get("reason_code"), "VALIDATE_EQUIVALENCE_MISMATCH")
        self.assertEqual(result.get("decisionLayers", {}).get("delivery", {}).get("tier"), "BLOCKED")

    def test_prefers_canonical_count_star_when_patchability_ties(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.countUser#v2",
            "sql": "select count(1) from ( select id from users ) tmp",
            "statementType": "SELECT",
        }
        proposal = {
            "llmCandidates": [
                {"id": "c1", "rewrittenSql": "SELECT COUNT(1) FROM users", "rewriteStrategy": "ELIMINATE_UNNECESSARY_SUBQUERY"},
                {"id": "c2", "rewrittenSql": "SELECT COUNT(id) FROM users", "rewriteStrategy": "USE_PRIMARY_KEY_FOR_COUNT"},
                {"id": "c3", "rewrittenSql": "SELECT COUNT(*) FROM users", "rewriteStrategy": "STANDARD_COUNT_SYNTAX"},
            ],
            "suggestions": [],
        }
        config = {"db": {"dsn": "postgresql://dummy"}, "validate": {}, "policy": {}}

        def fake_semantics(_cfg, _orig, _rewritten, _dir):
            return {
                "checked": True,
                "method": "sql_semantic_compare_v2",
                "rowCount": {"status": "MATCH"},
                "keySetHash": {"status": "MATCH"},
                "rowSampleHash": {"status": "MATCH"},
                "evidenceRefs": [],
                "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
            }

        def fake_plan(_cfg, _orig, _rewritten, _dir):
            return {
                "checked": True,
                "method": "sql_explain_json_compare",
                "beforeSummary": {"totalCost": 10.0},
                "afterSummary": {"totalCost": 10.0},
                "reasonCodes": [],
                "improved": False,
                "evidenceRefs": [],
            }

        with tempfile.TemporaryDirectory(prefix="validate_count_star_") as td:
            with patch("sqlopt.platforms.sql.validator_sql.compare_semantics", side_effect=fake_semantics), patch(
                "sqlopt.platforms.sql.validator_sql.compare_plan", side_effect=fake_plan
            ):
                result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))

        self.assertEqual(result["rewrittenSql"], "SELECT COUNT(*) FROM users")
        self.assertEqual(result.get("selectedCandidateId"), "c3")
        self.assertEqual(result.get("canonicalization", {}).get("ruleId"), "COUNT_CANONICAL_FORM")
        self.assertTrue(result.get("canonicalization", {}).get("preferred"))


if __name__ == "__main__":
    unittest.main()
