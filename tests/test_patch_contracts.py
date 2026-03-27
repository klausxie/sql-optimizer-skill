from __future__ import annotations

from pathlib import Path

import pytest

from sqlopt.contracts import ContractValidator
from sqlopt.errors import ContractError
from sqlopt.patch_contracts import FROZEN_AUTO_PATCH_FAMILIES, build_patch_target_contract

ROOT = Path(__file__).resolve().parents[1]


def _validator() -> ContractValidator:
    return ContractValidator(ROOT)


def _acceptance_result_payload() -> dict[str, object]:
    return {
        "sqlKey": "demo.user.countUser#v2",
        "status": "PASS",
        "equivalence": {},
        "perfComparison": {},
        "securityChecks": {},
    }


def _patch_result_payload() -> dict[str, object]:
    return {
        "sqlKey": "demo.user.countUser#v2",
        "patchFiles": [],
        "diffSummary": {},
        "applyMode": "AUTO",
        "rollback": "NONE",
    }


def test_patch_target_contract_requires_replay_artifacts() -> None:
    with pytest.raises(ValueError, match="PATCH_REPLAY_CONTRACT_MISSING"):
        build_patch_target_contract(
            sql_key="demo.user.countUser#v2",
            target_sql="SELECT COUNT(*) FROM users",
            selected_candidate_id="1",
            selected_patch_strategy={"strategyType": "SAFE_WRAPPER_COLLAPSE"},
            family="STATIC_INCLUDE_WRAPPER_COLLAPSE",
            semantic_equivalence={"status": "PASS", "confidence": "HIGH"},
            patchability={"eligible": True},
            rewrite_materialization={"mode": "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE"},
            template_rewrite_ops=[{"op": "replace_statement_body"}],
            replay_contract=None,
            evidence_refs=["runs/demo/pipeline/validate/acceptance.results.jsonl"],
        )


def test_frozen_family_scope_is_authoritative() -> None:
    assert FROZEN_AUTO_PATCH_FAMILIES == {
        "STATIC_STATEMENT_REWRITE",
        "STATIC_WRAPPER_COLLAPSE",
        "STATIC_CTE_INLINE",
        "STATIC_INCLUDE_WRAPPER_COLLAPSE",
        "STATIC_ALIAS_PROJECTION_CLEANUP",
        "STATIC_IN_LIST_SIMPLIFICATION",
        "STATIC_LIMIT_OPTIMIZATION",
        "STATIC_ORDER_BY_SIMPLIFICATION",
        "STATIC_OR_SIMPLIFICATION",
        "STATIC_DISTINCT_ON_SIMPLIFICATION",
        "STATIC_SUBQUERY_WRAPPER_COLLAPSE",
        "STATIC_BOOLEAN_SIMPLIFICATION",
        "STATIC_CASE_SIMPLIFICATION",
        "STATIC_COALESCE_SIMPLIFICATION",
        "STATIC_EXPRESSION_FOLDING",
        "STATIC_NULL_COMPARISON",
        "DYNAMIC_COUNT_WRAPPER_COLLAPSE",
        "DYNAMIC_FILTER_WRAPPER_COLLAPSE",
        "DYNAMIC_FILTER_SELECT_LIST_CLEANUP",
        "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP",
        "REDUNDANT_GROUP_BY_WRAPPER",
        "REDUNDANT_HAVING_WRAPPER",
        "REDUNDANT_DISTINCT_WRAPPER",
        "GROUP_BY_FROM_ALIAS_CLEANUP",
        "GROUP_BY_HAVING_FROM_ALIAS_CLEANUP",
        "DISTINCT_FROM_ALIAS_CLEANUP",
    }
    assert "FOREACH_IN_PREDICATE" not in FROZEN_AUTO_PATCH_FAMILIES


def test_dynamic_filter_cleanup_frozen_scope_stays_registry_derived() -> None:
    assert "DYNAMIC_FILTER_SELECT_LIST_CLEANUP" in FROZEN_AUTO_PATCH_FAMILIES
    assert "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP" in FROZEN_AUTO_PATCH_FAMILIES


def test_acceptance_result_patch_target_is_optional() -> None:
    _validator().validate("acceptance_result", _acceptance_result_payload())


def test_acceptance_result_rejects_patch_owned_fields() -> None:
    payload = _acceptance_result_payload()
    payload["patchTarget"] = {"sqlKey": "demo.user.countUser#v2"}

    with pytest.raises(ContractError, match="acceptance_result schema validation failed"):
        _validator().validate("acceptance_result", payload)


def test_patch_result_rejects_public_patch_target() -> None:
    payload = _patch_result_payload()
    payload["patchTarget"] = {
        "sqlKey": "demo.user.countUser#v2",
        "selectedCandidateId": "1",
        "targetSql": "SELECT COUNT(*) FROM users",
        "targetSqlNormalized": "SELECT COUNT(*) FROM users",
        "targetSqlFingerprint": "demo-fingerprint",
        "semanticGateStatus": "PASS",
        "semanticGateConfidence": "HIGH",
        "selectedPatchStrategy": {"strategyType": "SAFE_WRAPPER_COLLAPSE"},
        "family": "STATIC_INCLUDE_WRAPPER_COLLAPSE",
        "semanticEquivalence": {"status": "PASS", "confidence": "HIGH"},
        "patchability": {"eligible": True},
        "rewriteMaterialization": {"mode": "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE"},
        "templateRewriteOps": [{"op": "replace_statement_body"}],
        "replayContract": {
            "replayMode": "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE",
            "requiredTemplateOps": ["replace_statement_body"],
            "expectedRenderedSql": "SELECT COUNT(*) FROM users",
            "expectedRenderedSqlNormalized": "SELECT COUNT(*) FROM users",
            "expectedFingerprint": "demo-fingerprint",
            "requiredAnchors": [],
            "requiredPlaceholderShape": "NONE",
            "dialectSyntaxCheckRequired": True,
        },
        "evidenceRefs": ["runs/demo/pipeline/validate/acceptance.results.jsonl"],
    }

    with pytest.raises(ContractError, match="patch_result schema validation failed"):
        _validator().validate("patch_result", payload)


def test_complete_patch_target_contract_is_internal_only() -> None:
    contract = build_patch_target_contract(
        sql_key="demo.user.countUser#v2",
        target_sql=" SELECT  COUNT(*)  FROM users ",
        selected_candidate_id="1",
        selected_patch_strategy={"strategyType": "SAFE_WRAPPER_COLLAPSE"},
        family="STATIC_INCLUDE_WRAPPER_COLLAPSE",
        semantic_equivalence={"status": "PASS", "confidence": "HIGH"},
        patchability={"eligible": True},
        rewrite_materialization={"mode": "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE"},
        template_rewrite_ops=[{"op": "replace_statement_body"}],
        replay_contract={
            "replayMode": "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE",
            "requiredTemplateOps": ["replace_statement_body"],
            "expectedRenderedSql": " SELECT  COUNT(*)  FROM users ",
            "requiredAnchors": [],
            "requiredIncludes": [],
            "requiredPlaceholderShape": "NONE",
            "dialectSyntaxCheckRequired": True,
        },
        evidence_refs=["runs/demo/pipeline/validate/acceptance.results.jsonl"],
    )

    assert contract["targetSqlNormalized"] == "SELECT COUNT(*) FROM users"
    assert contract["targetSqlFingerprint"] == contract["replayContract"]["expectedFingerprint"]
    assert contract["semanticGateStatus"] == "PASS"
    assert contract["semanticGateConfidence"] == "HIGH"
    assert contract["replayContract"]["expectedRenderedSqlNormalized"] == "SELECT COUNT(*) FROM users"

    patch_payload = _patch_result_payload()
    patch_payload["patchTarget"] = contract
    with pytest.raises(ContractError, match="patch_result schema validation failed"):
        _validator().validate("patch_result", patch_payload)
