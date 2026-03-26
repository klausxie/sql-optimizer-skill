"""Run layout builder for the next-generation slow-SQL pipeline design."""

from __future__ import annotations

from pathlib import Path


class NextRunLayout:
    """Manage the documented run directory layout for the next-generation design."""

    STAGES = ("init", "parse", "recognition", "optimize", "result")

    def __init__(self, run_id: str, base_dir: str = "./runs") -> None:
        self.run_id = run_id
        self.base_dir = Path(base_dir)
        self.run_dir = self.base_dir / run_id

    def stage_dir(self, stage_name: str) -> Path:
        self._validate_stage(stage_name)
        return self.run_dir / stage_name

    def stage_manifest(self, stage_name: str) -> Path:
        return self.stage_dir(stage_name) / "manifest.json"

    def stage_index(self, stage_name: str) -> Path:
        return self.stage_dir(stage_name) / "_index.json"

    def stage_summary(self, stage_name: str) -> Path:
        return self.stage_dir(stage_name) / "SUMMARY.md"

    @property
    def init_dir(self) -> Path:
        return self.stage_dir("init")

    @property
    def parse_dir(self) -> Path:
        return self.stage_dir("parse")

    @property
    def recognition_dir(self) -> Path:
        return self.stage_dir("recognition")

    @property
    def optimize_dir(self) -> Path:
        return self.stage_dir("optimize")

    @property
    def result_dir(self) -> Path:
        return self.stage_dir("result")

    def ensure_dirs(self) -> None:
        for stage_name, subdirs in self._stage_subdirs().items():
            root = self.stage_dir(stage_name)
            root.mkdir(parents=True, exist_ok=True)
            for subdir in subdirs:
                (root / subdir).mkdir(parents=True, exist_ok=True)

    def init_sql_unit_file(self, namespace: str, statement_id: str) -> Path:
        return self.init_dir / "sql_units" / "by_namespace" / namespace / f"{statement_id}.json"

    def init_table_file(self, table_name: str) -> Path:
        return self.init_dir / "tables" / f"{table_name}.json"

    def init_column_distribution_file(self, table_name: str, column_name: str) -> Path:
        return self.init_dir / "column_distributions" / table_name / f"{column_name}.json"

    def init_column_usage_file(self, namespace: str, statement_id: str) -> Path:
        return self.init_dir / "column_usages" / "by_namespace" / namespace / f"{statement_id}.json"

    def parse_statement_file(self, namespace: str, statement_id: str) -> Path:
        return self.parse_dir / "units" / "by_namespace" / namespace / statement_id / "statement.json"

    def parse_branch_file(self, namespace: str, statement_id: str, path_id: str) -> Path:
        return self.parse_dir / "units" / "by_namespace" / namespace / statement_id / "branches" / f"{path_id}.json"

    def recognition_cases_shard(self, shard_name: str) -> Path:
        return self.recognition_dir / "cases" / "shards" / shard_name

    def recognition_explain_shard(self, shard_name: str) -> Path:
        return self.recognition_dir / "explain" / "shards" / shard_name

    def recognition_execution_shard(self, shard_name: str) -> Path:
        return self.recognition_dir / "execution" / "shards" / shard_name

    def recognition_finding_file(self, severity: str, finding_id: str) -> Path:
        return self.recognition_dir / "findings" / "by_severity" / severity / f"{finding_id}.json"

    def optimize_proposal_file(self, namespace: str, statement_id: str, proposal_id: str) -> Path:
        return self.optimize_dir / "proposals" / "by_namespace" / namespace / statement_id / f"{proposal_id}.json"

    def optimize_validations_shard(self, shard_name: str) -> Path:
        return self.optimize_dir / "validations" / "shards" / shard_name

    def result_namespace_report_file(self, namespace: str) -> Path:
        return self.result_dir / "reports" / "by_namespace" / f"{namespace}.json"

    def result_patch_file(self, namespace: str, statement_id: str) -> Path:
        return self.result_dir / "patches" / "by_namespace" / namespace / f"{statement_id}.json"

    def _validate_stage(self, stage_name: str) -> None:
        if stage_name not in self.STAGES:
            raise ValueError(f"Unknown stage: {stage_name}. Expected one of {self.STAGES}")

    def _stage_subdirs(self) -> dict[str, list[str]]:
        return {
            "init": [
                "sql_units/by_namespace",
                "tables",
                "column_distributions",
                "column_usages/by_namespace",
            ],
            "parse": [
                "units/by_namespace",
                "priority_queue",
            ],
            "recognition": [
                "cases/shards",
                "explain/shards",
                "execution/shards",
                "findings/by_severity",
            ],
            "optimize": [
                "proposals/by_namespace",
                "validations/shards",
            ],
            "result": [
                "ranking",
                "reports/by_namespace",
                "patches/by_namespace",
            ],
        }
