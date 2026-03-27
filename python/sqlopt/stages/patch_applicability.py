from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .patch_build import PatchBuildResult


@dataclass(frozen=True)
class PatchApplicabilityResult:
    artifact_kind: str
    target_file: str | None
    materialized: bool
    applicability_checked: bool
    apply_ready_candidate: bool
    failure_class: str | None
    reason_code: str | None
    target_kind: str | None = None
    target_ref: str | None = None


def run_patch_applicability(
    *,
    build: PatchBuildResult,
    patch_file: Path,
    workdir: Path,
    check_patch_applicable: Callable[[Path, Path], tuple[bool, str | None]],
    artifact_kind: str | None = None,
) -> tuple[PatchApplicabilityResult, str | None]:
    applicable, apply_error = check_patch_applicable(patch_file, workdir)
    return (
        PatchApplicabilityResult(
            artifact_kind=artifact_kind or build.artifact_kind,
            target_file=build.target_file,
            materialized=True,
            applicability_checked=True,
            apply_ready_candidate=applicable,
            failure_class=None if applicable else "APPLICABILITY_FAILURE",
            reason_code=None if applicable else "PATCH_NOT_APPLICABLE",
            target_kind=build.target_kind,
            target_ref=build.target_ref,
        ),
        apply_error,
    )


def build_delivery_verdict(
    *,
    applicability: PatchApplicabilityResult,
    proof_ok: bool | None,
    proof_reason_code: str | None,
) -> dict[str, str | None]:
    if not applicability.materialized:
        return {
            "artifactKind": applicability.artifact_kind,
            "deliveryStage": "BUILD_FAILED",
            "failureClass": applicability.failure_class or "BUILD_FAILURE",
            "reasonCode": applicability.reason_code,
        }
    if not applicability.applicability_checked or not applicability.apply_ready_candidate:
        return {
            "artifactKind": applicability.artifact_kind,
            "deliveryStage": "APPLICABILITY_FAILED",
            "failureClass": applicability.failure_class or "APPLICABILITY_FAILURE",
            "reasonCode": applicability.reason_code,
        }
    if proof_ok is False:
        return {
            "artifactKind": applicability.artifact_kind,
            "deliveryStage": "PROOF_FAILED",
            "failureClass": "PROOF_FAILURE",
            "reasonCode": proof_reason_code,
        }
    return {
        "artifactKind": applicability.artifact_kind,
        "deliveryStage": "APPLY_READY",
        "failureClass": None,
        "reasonCode": None,
    }
