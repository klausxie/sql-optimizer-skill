from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .io_utils import ensure_dir
from .utils import sql_key_path_component

REL_REPORT_JSON = "report.json"

REL_CONTROL_DIR = "control"
REL_CONTROL_STATE = "control/state.json"
REL_CONTROL_PLAN = "control/plan.json"
REL_CONTROL_MANIFEST = "control/manifest.jsonl"

REL_ARTIFACTS_DIR = "artifacts"
REL_ARTIFACTS_SCAN = "artifacts/scan.jsonl"
REL_ARTIFACTS_FRAGMENTS = "artifacts/fragments.jsonl"
REL_ARTIFACTS_PROPOSALS = "artifacts/proposals.jsonl"
REL_ARTIFACTS_ACCEPTANCE = "artifacts/acceptance.jsonl"
REL_ARTIFACTS_PATCHES = "artifacts/patches.jsonl"

REL_SQL_DIR = "sql"
REL_SQL_CATALOG = "sql/catalog.jsonl"


def to_posix_relative(run_dir: Path, path: Path) -> str:
    return str(path.relative_to(run_dir)).replace("\\", "/")


@dataclass(frozen=True)
class RunPaths:
    run_dir: Path

    @property
    def report_json_path(self) -> Path:
        return self.run_dir / REL_REPORT_JSON

    @property
    def control_dir(self) -> Path:
        return self.run_dir / REL_CONTROL_DIR

    @property
    def state_path(self) -> Path:
        return self.run_dir / REL_CONTROL_STATE

    @property
    def plan_path(self) -> Path:
        return self.run_dir / REL_CONTROL_PLAN

    @property
    def manifest_path(self) -> Path:
        return self.run_dir / REL_CONTROL_MANIFEST

    @property
    def artifacts_dir(self) -> Path:
        return self.run_dir / REL_ARTIFACTS_DIR

    @property
    def scan_config_path(self) -> Path:
        return self.artifacts_dir / "scan.config.json"

    @property
    def scan_selection_path(self) -> Path:
        return self.artifacts_dir / "selection.json"

    @property
    def preflight_path(self) -> Path:
        return self.control_dir / "preflight.json"

    @property
    def scan_units_path(self) -> Path:
        return self.run_dir / REL_ARTIFACTS_SCAN

    @property
    def scan_fragments_path(self) -> Path:
        return self.run_dir / REL_ARTIFACTS_FRAGMENTS

    @property
    def proposals_path(self) -> Path:
        return self.run_dir / REL_ARTIFACTS_PROPOSALS

    @property
    def acceptance_path(self) -> Path:
        return self.run_dir / REL_ARTIFACTS_ACCEPTANCE

    @property
    def patches_path(self) -> Path:
        return self.run_dir / REL_ARTIFACTS_PATCHES

    @property
    def sql_dir(self) -> Path:
        return self.run_dir / REL_SQL_DIR

    @property
    def sql_catalog_path(self) -> Path:
        return self.run_dir / REL_SQL_CATALOG

    @property
    def template_suggestions_dir(self) -> Path:
        return self.control_dir / "template_suggestions"

    def sql_artifact_dir(self, sql_key: str) -> Path:
        return self.sql_dir / sql_key_path_component(sql_key)

    def sql_index_path(self, sql_key: str) -> Path:
        return self.sql_artifact_dir(sql_key) / "index.json"

    def sql_trace_path(self, sql_key: str) -> Path:
        return self.sql_artifact_dir(sql_key) / "trace.optimize.llm.json"

    def sql_candidate_generation_diagnostics_path(self, sql_key: str) -> Path:
        return self.sql_artifact_dir(sql_key) / "candidate_generation_diagnostics.json"

    def sql_evidence_dir(self, sql_key: str) -> Path:
        return self.sql_artifact_dir(sql_key) / "evidence"

    @property
    def llm_feedback_path(self) -> Path:
        return self.control_dir / "llm_feedback.jsonl"

    @property
    def llm_feedback_analysis_path(self) -> Path:
        return self.control_dir / "llm_feedback_analysis.json"

    def ensure_layout(self) -> None:
        for path in (self.run_dir, self.control_dir, self.artifacts_dir, self.sql_dir):
            ensure_dir(path)


def canonical_paths(run_dir: Path) -> RunPaths:
    return RunPaths(run_dir=run_dir)
