from __future__ import annotations

from pathlib import Path

from ..contracts import ContractValidator
from .report_builder import build_report_artifacts
from .report_loader import load_report_inputs
from .report_writer import write_report_artifacts


def generate(run_id: str, mode: str, config: dict, run_dir: Path, validator: ContractValidator) -> dict:
    inputs = load_report_inputs(run_dir)
    artifacts = build_report_artifacts(run_id, mode, config, run_dir, inputs)
    return write_report_artifacts(run_id, mode, run_dir, validator, artifacts)
