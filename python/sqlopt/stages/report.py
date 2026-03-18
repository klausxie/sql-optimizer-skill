# =============================================================================
# DEPRECATED MODULE
# =============================================================================
# This module is deprecated as of V8 and will be removed in a future release.
# Migration timeline:
#   - V8 (current): Kept for backward compatibility
#   - V9 (planned): May be removed or further deprecated
#
# New architecture: Use application/workflow_engine.py for stage orchestration
# Reference: docs/V8/V8_SUMMARY.md
# =============================================================================

from __future__ import annotations

from pathlib import Path

from ..contracts import ContractValidator
from ..errors import StageError
from .report_builder import build_report_artifacts
from .report_loader import load_report_inputs
from .report_writer import write_report_artifacts


def _verification_gate_mode(config: dict) -> str:
    verification_cfg = dict(config.get("verification") or {})
    policy = verification_cfg.get("critical_output_policy")
    if policy is not None:
        return str(policy).strip().lower()
    if bool(verification_cfg.get("enforce_verified_outputs", False)):
        return "block"
    return "warn"


def generate(
    run_id: str, mode: str, config: dict, run_dir: Path, validator: ContractValidator
) -> dict:
    inputs = load_report_inputs(run_dir)
    artifacts = build_report_artifacts(run_id, mode, config, run_dir, inputs)
    payload = write_report_artifacts(run_id, mode, run_dir, validator, artifacts)
    if _verification_gate_mode(config) == "block" and payload.get(
        "validation_warnings"
    ):
        raise StageError(
            "verification gate failed: unverified critical outputs present",
            reason_code="VERIFICATION_GATE_FAILED",
        )
    return payload
