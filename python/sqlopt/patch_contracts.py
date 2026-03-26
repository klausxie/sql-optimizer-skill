from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

from .patch_families.registry import list_registered_patch_families

FROZEN_AUTO_PATCH_FAMILIES = frozenset(
    spec.family for spec in list_registered_patch_families() if spec.status == "FROZEN_AUTO_PATCH"
)


def normalize_patch_target_sql(text: str) -> str:
    return " ".join(str(text or "").split())


def fingerprint_patch_target_sql(text: str) -> str:
    normalized = normalize_patch_target_sql(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_patch_target_contract(
    *,
    sql_key: str,
    target_sql: str,
    selected_candidate_id: str,
    selected_patch_strategy: dict[str, Any],
    family: str,
    semantic_equivalence: dict[str, Any],
    patchability: dict[str, Any],
    rewrite_materialization: dict[str, Any],
    template_rewrite_ops: list[dict[str, Any]],
    replay_contract: dict[str, Any] | None,
    evidence_refs: list[str],
    target_sql_fingerprint: str | None = None,
) -> dict[str, Any]:
    if replay_contract is None:
        raise ValueError("PATCH_REPLAY_CONTRACT_MISSING")

    normalized_target_sql = normalize_patch_target_sql(target_sql)
    fingerprint = target_sql_fingerprint or fingerprint_patch_target_sql(normalized_target_sql)
    replay = deepcopy(replay_contract)
    expected_rendered_sql = str(replay.get("expectedRenderedSql") or target_sql)
    replay["expectedRenderedSql"] = expected_rendered_sql
    replay["expectedRenderedSqlNormalized"] = (
        str(replay.get("expectedRenderedSqlNormalized") or "")
        or normalize_patch_target_sql(expected_rendered_sql)
    )
    replay["expectedFingerprint"] = replay.get("expectedFingerprint") or fingerprint_patch_target_sql(
        replay["expectedRenderedSqlNormalized"]
    )
    replay["requiredTemplateOps"] = [str(op) for op in replay.get("requiredTemplateOps") or []]
    replay["requiredAnchors"] = [str(anchor) for anchor in replay.get("requiredAnchors") or []]
    replay["requiredIncludes"] = [str(include) for include in replay.get("requiredIncludes") or []]
    placeholder_shape = replay.get("requiredPlaceholderShape")
    replay["requiredPlaceholderShape"] = list(placeholder_shape) if isinstance(placeholder_shape, list) else str(placeholder_shape or "")
    replay["dialectSyntaxCheckRequired"] = bool(replay.get("dialectSyntaxCheckRequired"))

    return {
        "sqlKey": sql_key,
        "selectedCandidateId": selected_candidate_id,
        "targetSql": target_sql,
        "targetSqlNormalized": normalized_target_sql,
        "targetSqlFingerprint": fingerprint,
        "semanticGateStatus": str(semantic_equivalence.get("status") or ""),
        "semanticGateConfidence": str(semantic_equivalence.get("confidence") or ""),
        "selectedPatchStrategy": deepcopy(selected_patch_strategy),
        "family": family,
        "semanticEquivalence": deepcopy(semantic_equivalence),
        "patchability": deepcopy(patchability),
        "rewriteMaterialization": deepcopy(rewrite_materialization),
        "templateRewriteOps": deepcopy(template_rewrite_ops),
        "replayContract": replay,
        "evidenceRefs": [str(ref) for ref in evidence_refs],
    }
