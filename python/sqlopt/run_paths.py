from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .io_utils import ensure_dir
from .utils import sql_key_path_component

RUN_META_GLOB_SUFFIX = "supervisor/meta.json"
REL_RUN_INDEX_JSON = "run.index.json"

REL_OVERVIEW_REPORT_JSON = "overview/report.json"
REL_OVERVIEW_REPORT_MD = "overview/report.md"
REL_OVERVIEW_REPORT_SUMMARY_MD = "overview/report.summary.md"
REL_OVERVIEW_CONFIG_RESOLVED = "overview/config.resolved.json"

# Deprecated: legacy path constants (for backward compatibility)
REL_PIPELINE_SUPERVISOR_STATE = (
    "pipeline/supervisor/state.json"  # deprecated: use supervisor_dir
)
REL_PIPELINE_SUPERVISOR_PLAN = (
    "pipeline/supervisor/plan.json"  # deprecated: use supervisor_dir
)
REL_PIPELINE_SUPERVISOR_RESULTS_SCAN = (
    "pipeline/supervisor/results/scan.jsonl"  # deprecated: use supervisor_results_dir
)
REL_PIPELINE_SUPERVISOR_RESULTS_OPTIMIZE = "pipeline/supervisor/results/optimize.jsonl"  # deprecated: use supervisor_results_dir
REL_PIPELINE_SUPERVISOR_RESULTS_VALIDATE = "pipeline/supervisor/results/validate.jsonl"  # deprecated: use supervisor_results_dir
REL_PIPELINE_SUPERVISOR_RESULTS_PATCH = (
    "pipeline/supervisor/results/apply.jsonl"  # deprecated: use supervisor_results_dir
)
REL_PIPELINE_SUPERVISOR_RESULTS_REPORT = (
    "pipeline/supervisor/results/report.jsonl"  # deprecated: use supervisor_results_dir
)
REL_PIPELINE_MANIFEST = "pipeline/manifest.jsonl"
REL_PIPELINE_SCAN_UNITS = "pipeline/scan/sqlunits.jsonl"
REL_PIPELINE_SCAN_FRAGMENTS = "pipeline/scan/fragments.jsonl"
REL_PIPELINE_OPTIMIZE_PROPOSALS = "pipeline/optimize/optimization.proposals.jsonl"
REL_PIPELINE_VALIDATE_ACCEPTANCE = "pipeline/validate/acceptance.results.jsonl"
REL_PIPELINE_PATCH_RESULTS = "pipeline/apply/patch.results.jsonl"
REL_PIPELINE_OPS_TOPOLOGY = "pipeline/ops/topology.json"
REL_PIPELINE_OPS_HEALTH = "pipeline/ops/health.json"
REL_PIPELINE_OPS_FAILURES = "pipeline/ops/failures.jsonl"
REL_PIPELINE_VERIFICATION_LEDGER = "pipeline/verification/ledger.jsonl"
REL_PIPELINE_VERIFICATION_SUMMARY = "pipeline/verification/summary.json"

REL_SQL_CATALOG = "sql/catalog.jsonl"
REL_DIAGNOSTICS_SQL_OUTCOMES = "diagnostics/sql_outcomes.jsonl"
REL_DIAGNOSTICS_SQL_ARTIFACTS = "diagnostics/sql_artifacts.jsonl"
REL_DIAGNOSTICS_BLOCKERS_SUMMARY = "diagnostics/blockers.summary.json"

REPORT_RUN_INDEX_OVERVIEW_GROUP = [
    REL_OVERVIEW_REPORT_JSON,
    REL_OVERVIEW_REPORT_MD,
    REL_OVERVIEW_REPORT_SUMMARY_MD,
    REL_OVERVIEW_CONFIG_RESOLVED,
]

REPORT_RUN_INDEX_PIPELINE_GROUP = [
    REL_PIPELINE_MANIFEST,
    REL_PIPELINE_SCAN_UNITS,
    REL_PIPELINE_SCAN_FRAGMENTS,
    REL_PIPELINE_OPTIMIZE_PROPOSALS,
    REL_PIPELINE_VALIDATE_ACCEPTANCE,
    REL_PIPELINE_PATCH_RESULTS,
    REL_PIPELINE_SUPERVISOR_STATE,
    REL_PIPELINE_SUPERVISOR_PLAN,
    REL_PIPELINE_SUPERVISOR_RESULTS_SCAN,
    REL_PIPELINE_SUPERVISOR_RESULTS_OPTIMIZE,
    REL_PIPELINE_SUPERVISOR_RESULTS_VALIDATE,
    REL_PIPELINE_SUPERVISOR_RESULTS_PATCH,
    REL_PIPELINE_SUPERVISOR_RESULTS_REPORT,
    REL_PIPELINE_OPS_TOPOLOGY,
    REL_PIPELINE_OPS_HEALTH,
    REL_PIPELINE_OPS_FAILURES,
    REL_PIPELINE_VERIFICATION_LEDGER,
    REL_PIPELINE_VERIFICATION_SUMMARY,
]


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

    # --- Existing run directory properties ---

    @property
    def pipeline_dir(self) -> Path:
        return self.run_dir / "pipeline"

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
        return self.pipeline_dir / "manifest.jsonl"

    @property
    def scan_dir(self) -> Path:
        return self.pipeline_dir / "scan"

    @property
    def diagnose_dir(self) -> Path:
        """Alias for scan_dir - diagnose is the new stage name."""
        return self.pipeline_dir / "scan"

    @property
    def scan_units_path(self) -> Path:
        return self.scan_dir / "sqlunits.jsonl"

    @property
    def diagnose_units_path(self) -> Path:
        """Path to SQL units with baseline diagnostics."""
        return self.scan_dir / "diagnose.sqlunits.jsonl"

    @property
    def scan_fragments_path(self) -> Path:
        return self.scan_dir / "fragments.jsonl"

    @property
    def branching_dir(self) -> Path:
        return self.pipeline_dir / "branching"

    @property
    def branches_path(self) -> Path:
        return self.branching_dir / "branch.results.jsonl"

    @property
    def baseline_dir(self) -> Path:
        return self.pipeline_dir / "baseline"

    @property
    def baseline_results_path(self) -> Path:
        return self.baseline_dir / "baseline.results.jsonl"

    @property
    def optimize_dir(self) -> Path:
        return self.pipeline_dir / "optimize"

    @property
    def proposals_path(self) -> Path:
        return self.optimize_dir / "optimization.proposals.jsonl"

    @property
    def validate_dir(self) -> Path:
        return self.pipeline_dir / "validate"

    @property
    def acceptance_path(self) -> Path:
        return self.validate_dir / "acceptance.results.jsonl"

    @property
    def apply_dir(self) -> Path:
        return self.pipeline_dir / "apply"

    @property
    def patch_generate_dir(self) -> Path:
        """Alias for apply_dir - deprecated, use apply_dir."""
        return self.apply_dir

    @property
    def patches_path(self) -> Path:
        return self.apply_dir / "patch.results.jsonl"

    @property
    def patch_files_dir(self) -> Path:
        return self.apply_dir / "files"

    @property
    def ops_dir(self) -> Path:
        return self.pipeline_dir / "ops"

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
        return self.pipeline_dir / "verification"

    @property
    def verification_ledger_path(self) -> Path:
        return self.verification_dir / "ledger.jsonl"

    @property
    def verification_summary_path(self) -> Path:
        return self.verification_dir / "summary.json"

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
            self.scan_dir,
            self.branching_dir,
            self.baseline_dir,
            self.optimize_dir,
            self.validate_dir,
            self.apply_dir,
            self.ops_dir,
            self.verification_dir,
            self.overview_dir,
            self.sql_dir,
            self.diagnostics_dir,
            self.project_context_dir,
            self.sqlmap_catalog_dir,
        ):
            ensure_dir(path)


def canonical_paths(run_dir: Path, project_root: Path | None = None) -> RunPaths:
    return RunPaths(run_dir=run_dir, project_root=project_root)
