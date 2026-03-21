from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import ensure_dir, read_jsonl
from .utils import sql_key_path_component

RUN_META_GLOB_SUFFIX = "supervisor/meta.json"
REL_RUN_INDEX_JSON = "run.index.json"

REL_OVERVIEW_REPORT_JSON = "overview/report.json"
REL_OVERVIEW_REPORT_MD = "overview/report.md"
REL_OVERVIEW_REPORT_SUMMARY_MD = "overview/report.summary.md"
REL_OVERVIEW_CONFIG_RESOLVED = "overview/config.resolved.json"


def to_posix_relative(run_dir: Path, path: Path) -> str:
    return str(path.relative_to(run_dir)).replace("\\", "/")


@dataclass(frozen=True)
class RunPaths:
    run_dir: Path
    project_root: Path | None = None

    # --- Cache directory properties ---

    @property
    def cache_dir(self) -> Path:
        """Project-level cache directory: .sqlopt/cache"""
        root = self._resolve_project_root()
        return root / ".sqlopt" / "cache"

    @property
    def sqlmap_cache_dir(self) -> Path:
        """SQLMap cache directory: .sqlopt/cache/sqlmap_cache"""
        return self.cache_dir / "sqlmap_cache"

    @property
    def history_dir(self) -> Path:
        """History directory: .sqlopt/history"""
        root = self._resolve_project_root()
        return root / ".sqlopt" / "history"

    def db_schemas_dir(self, db_hash: str) -> Path:
        """Database schemas directory: .sqlopt/cache/db_schemas/{db_hash}"""
        return self.cache_dir / "db_schemas" / db_hash

    def _resolve_project_root(self) -> Path:
        """Resolve project root from run_dir or explicit project_root."""
        if self.project_root is not None:
            return self.project_root
        # Infer from run_dir: runs/<run_id>/ -> project_root
        return self.run_dir.parent.parent

    def ensure_cache_layout(self) -> None:
        """Create the cache directory structure."""
        for path in (
            self.cache_dir,
            self.sqlmap_cache_dir,
            self.history_dir,
        ):
            ensure_dir(path)

    # --- Run directory layout (V9: no pipeline/* tree) ---

    @property
    def overview_dir(self) -> Path:
        return self.run_dir / "overview"

    @property
    def supervisor_dir(self) -> Path:
        return self.run_dir / "supervisor"

    @property
    def supervisor_results_dir(self) -> Path:
        return self.supervisor_dir / "results"

    @property
    def state_path(self) -> Path:
        return self.supervisor_dir / "state.json"

    @property
    def plan_path(self) -> Path:
        return self.supervisor_dir / "plan.json"

    @property
    def meta_path(self) -> Path:
        return self.supervisor_dir / "meta.json"

    @property
    def manifest_path(self) -> Path:
        return self.supervisor_dir / "manifest.jsonl"

    @property
    def ops_dir(self) -> Path:
        return self.supervisor_dir / "ops"

    @property
    def topology_path(self) -> Path:
        return self.ops_dir / "topology.json"

    @property
    def health_path(self) -> Path:
        return self.ops_dir / "health.json"

    @property
    def failures_path(self) -> Path:
        return self.ops_dir / "failures.jsonl"

    @property
    def verification_dir(self) -> Path:
        return self.supervisor_dir / "verification"

    @property
    def verification_ledger_path(self) -> Path:
        return self.verification_dir / "ledger.jsonl"

    @property
    def verification_summary_path(self) -> Path:
        return self.verification_dir / "summary.json"

    @property
    def patches_path(self) -> Path:
        return self.v9_patch_dir / "legacy.patch.results.jsonl"

    @property
    def patch_files_dir(self) -> Path:
        return self.v9_patch_dir / "legacy_mapper_patches"

    def load_sql_units_map(self) -> dict[str, dict[str, Any]]:
        """Load sqlKey → unit from parse output or init JSON (V9 only)."""
        rows: list[dict[str, Any]] = []
        parse_path = self.parse_sql_units_with_branches_path
        if parse_path.exists():
            raw = json.loads(parse_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                rows = [x for x in raw if isinstance(x, dict)]
        elif self.init_sql_units_path.exists():
            raw = json.loads(self.init_sql_units_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                rows = [x for x in raw if isinstance(x, dict)]
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            k = str(row.get("sqlKey") or "").strip()
            if k:
                result[k] = row
        return result

    @property
    def config_resolved_path(self) -> Path:
        return self.overview_dir / "config.resolved.json"

    @property
    def report_json_path(self) -> Path:
        return self.overview_dir / "report.json"

    @property
    def report_md_path(self) -> Path:
        return self.overview_dir / "report.md"

    @property
    def report_summary_md_path(self) -> Path:
        return self.overview_dir / "report.summary.md"

    @property
    def sql_dir(self) -> Path:
        return self.run_dir / "sql"

    @property
    def diagnostics_dir(self) -> Path:
        return self.run_dir / "diagnostics"

    @property
    def project_context_dir(self) -> Path:
        return self.run_dir / "project_context"

    @property
    def sqlmap_catalog_dir(self) -> Path:
        return self.run_dir / "sqlmap_catalog"

    # --- V9 directory properties ---

    @property
    def init_dir(self) -> Path:
        return self.run_dir / "init"

    @property
    def init_sql_units_path(self) -> Path:
        return self.init_dir / "sql_units.json"

    @property
    def init_db_connectivity_path(self) -> Path:
        path = self.init_dir / "db_connectivity.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def init_schema_metadata_path(self) -> Path:
        path = self.init_dir / "schema_metadata.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def parse_dir(self) -> Path:
        return self.run_dir / "parse"

    @property
    def parse_sql_units_with_branches_path(self) -> Path:
        return self.parse_dir / "sql_units_with_branches.json"

    @property
    def parse_risks_path(self) -> Path:
        return self.parse_dir / "risks.json"

    @property
    def recognition_dir(self) -> Path:
        return self.run_dir / "recognition"

    @property
    def recognition_results_path(self) -> Path:
        return self.recognition_dir / "baselines.json"

    @property
    def v9_optimize_dir(self) -> Path:
        return self.run_dir / "optimize"

    @property
    def v9_proposals_path(self) -> Path:
        return self.v9_optimize_dir / "proposals.json"

    @property
    def v9_patch_dir(self) -> Path:
        return self.run_dir / "patch"

    @property
    def v9_patch_results_path(self) -> Path:
        return self.v9_patch_dir / "patches.json"

    @property
    def v9_patch_files_dir(self) -> Path:
        return self.v9_patch_dir / "patches"

    def supervisor_result_path(self, phase: str) -> Path:
        return self.supervisor_results_dir / f"{phase}.jsonl"

    def sql_artifact_dir(self, sql_key: str) -> Path:
        return self.sql_dir / sql_key_path_component(sql_key)

    def sql_trace_path(self, sql_key: str) -> Path:
        return self.sql_artifact_dir(sql_key) / "trace.optimize.llm.json"

    def sql_candidate_generation_diagnostics_path(self, sql_key: str) -> Path:
        return self.sql_artifact_dir(sql_key) / "candidate_generation_diagnostics.json"

    def sql_evidence_dir(self, sql_key: str) -> Path:
        return self.sql_artifact_dir(sql_key) / "evidence"

    def ensure_layout(self) -> None:
        for path in (
            self.run_dir,
            self.supervisor_dir,
            self.supervisor_results_dir,
            self.ops_dir,
            self.verification_dir,
            self.overview_dir,
            self.sql_dir,
            self.diagnostics_dir,
            self.project_context_dir,
            self.sqlmap_catalog_dir,
            self.init_dir,
            self.parse_dir,
            self.recognition_dir,
            self.v9_optimize_dir,
            self.v9_patch_dir,
            self.v9_patch_files_dir,
        ):
            ensure_dir(path)


def canonical_paths(run_dir: Path, project_root: Path | None = None) -> RunPaths:
    return RunPaths(run_dir=run_dir, project_root=project_root)
