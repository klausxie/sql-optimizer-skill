from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..patch_contracts import build_patch_target_contract, semantic_confidence_rank
from ..patch_families.registry import lookup_patch_family_spec
from ..verification.patch_artifact import materialize_patch_artifact
from ..verification.patch_replay import replay_patch_target
from ..verification.patch_syntax import verify_patch_syntax
from .patch_build import PatchBuildResult
from .patch_select import PatchSelectionContext


@dataclass(frozen=True)
class PatchProofResult:
    patch_target: dict[str, Any] | None
    replay_evidence: dict[str, Any]
    syntax_evidence: dict[str, Any]
    ok: bool
    reason_code: str | None


def _build_patch_target(
    *,
    sql_unit: dict[str, Any],
    selection: PatchSelectionContext,
    build: PatchBuildResult,
) -> dict[str, Any] | None:
    if not selection.rewritten_sql or not selection.selected_candidate_id or not build.selected_patch_strategy:
        return None
    # Check if patchable using blockingReasons (empty list = patchable)
    blocking_reasons = list((selection.patchability or {}).get("blockingReasons") or [])
    if blocking_reasons:
        return None

    replay_contract = dict((build.rewrite_materialization or {}).get("replayContract") or {})
    if not replay_contract:
        return None

    spec = lookup_patch_family_spec(build.family) if build.family else None
    if spec is None or spec.status != "FROZEN_AUTO_PATCH":
        return None

    semantic_equivalence = dict(selection.semantic_equivalence or {})
    semantic_status = str(semantic_equivalence.get("status") or selection.semantic_gate_status or "").strip().upper()
    if semantic_status != str(spec.acceptance.semantic_required_status or "").strip().upper():
        return None
    semantic_confidence = str(
        semantic_equivalence.get("confidence") or selection.semantic_gate_confidence or ""
    ).strip().upper()
    if semantic_confidence_rank(semantic_confidence) < semantic_confidence_rank(spec.acceptance.semantic_min_confidence):
        return None
    if not semantic_equivalence:
        semantic_equivalence = {
            "status": semantic_status,
            "confidence": semantic_confidence,
        }

    return build_patch_target_contract(
        sql_key=str(sql_unit.get("sqlKey") or ""),
        target_sql=selection.rewritten_sql,
        selected_candidate_id=selection.selected_candidate_id,
        selected_patch_strategy=build.selected_patch_strategy,
        family=build.family or "",
        semantic_equivalence=semantic_equivalence,
        patchability=dict(selection.patchability or {}),
        rewrite_materialization=dict(build.rewrite_materialization or {}),
        template_rewrite_ops=[dict(row) for row in build.template_rewrite_ops if isinstance(row, dict)],
        replay_contract=replay_contract,
        evidence_refs=[],
    )


def prove_patch_plan(
    *,
    sql_unit: dict[str, Any],
    selection: PatchSelectionContext,
    build: PatchBuildResult,
    fragment_catalog: dict[str, dict[str, Any]],
    patch_text: str,
    base_dir: Path | None = None,
) -> PatchProofResult:
    patch_target = _build_patch_target(
        sql_unit=sql_unit,
        selection=selection,
        build=build,
    )
    if not patch_target:
        return PatchProofResult(
            patch_target=None,
            replay_evidence={},
            syntax_evidence={},
            ok=False,
            reason_code="PATCH_TARGET_CONTRACT_MISSING",
        )

    artifact_result = materialize_patch_artifact(sql_unit=sql_unit, patch_text=patch_text, base_dir=base_dir)
    replay_result = replay_patch_target(
        sql_unit=sql_unit,
        patch_target=patch_target,
        fragment_catalog=fragment_catalog,
        patch_text=patch_text,
        artifact=artifact_result,
    )
    syntax_result = verify_patch_syntax(
        sql_unit=sql_unit,
        patch_target=patch_target,
        patch_text=patch_text,
        replay_result=replay_result,
        artifact=artifact_result,
    )
    replay_evidence = {
        "matchesTarget": replay_result.matches_target,
        "renderedSql": replay_result.rendered_sql,
        "normalizedRenderedSql": replay_result.normalized_rendered_sql,
        "driftReason": replay_result.drift_reason,
    }
    syntax_evidence = syntax_result.to_dict()
    ok = replay_result.matches_target is True and syntax_result.ok is True
    reason_code = replay_result.drift_reason or syntax_result.reason_code or None
    return PatchProofResult(
        patch_target=patch_target,
        replay_evidence=replay_evidence,
        syntax_evidence=syntax_evidence,
        ok=ok,
        reason_code=reason_code,
    )
