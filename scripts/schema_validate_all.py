#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.contracts import ContractValidator
from sqlopt.io_utils import read_json, read_jsonl


def validate_schemas() -> None:
    """Validate all JSON schema files in contracts/ directory."""
    import jsonschema

    contracts_dir = ROOT / "contracts"
    schema_files = list(contracts_dir.glob("*.schema.json"))
    schema_files.extend(contracts_dir.glob("schemas/*.schema.json"))

    for schema_file in schema_files:
        try:
            schema = read_json(schema_file)
            jsonschema.Draft7Validator.check_schema(schema)
        except Exception as e:
            print(f"Invalid schema {schema_file}: {e}")
            raise SystemExit(1)

    print(f"Validated {len(schema_files)} schema files: ok")


def validate_run_output(run_dir: Path) -> None:
    """Validate run output files against schemas."""
    v = ContractValidator(ROOT)
    if (run_dir / "init" / "sql_units.json").exists():
        _validate_v9_run_output(v, run_dir)
    else:
        _validate_legacy_run_output(v, run_dir)
    print("ok")


def _validate_json_array(
    validator: ContractValidator, schema_name: str, path: Path
) -> None:
    rows = read_json(path)
    if not isinstance(rows, list):
        raise SystemExit(f"expected array in {path}")
    for row in rows:
        validator.validate(schema_name, row)


def _validate_if_present(
    validator: ContractValidator, schema_name: str, path: Path
) -> None:
    if path.exists():
        validator.validate(schema_name, read_json(path))


def _validate_v9_run_output(v: ContractValidator, run_dir: Path) -> None:
    _validate_json_array(v, "sqlunit", run_dir / "init" / "sql_units.json")
    _validate_json_array(v, "sqlunit", run_dir / "parse" / "sql_units_with_branches.json")
    _validate_json_array(v, "risks", run_dir / "parse" / "risks.json")
    _validate_json_array(v, "baseline_result", run_dir / "recognition" / "baselines.json")
    _validate_json_array(v, "optimization_proposal", run_dir / "optimize" / "proposals.json")
    _validate_json_array(v, "patch_result", run_dir / "patch" / "patches.json")
    _validate_if_present(v, "run_report", run_dir / "overview" / "report.json")
    _validate_if_present(v, "ops_health", run_dir / "pipeline" / "ops" / "health.json")
    _validate_if_present(v, "ops_topology", run_dir / "pipeline" / "ops" / "topology.json")
    _validate_if_present(
        v, "verification_summary", run_dir / "pipeline" / "verification" / "summary.json"
    )


def _validate_legacy_run_output(v: ContractValidator, run_dir: Path) -> None:
    for row in read_jsonl(run_dir / "pipeline" / "scan" / "sqlunits.jsonl"):
        v.validate("sqlunit", row)
    for row in read_jsonl(run_dir / "pipeline" / "scan" / "fragments.jsonl"):
        v.validate("fragment_record", row)
    for row in read_jsonl(
        run_dir / "pipeline" / "optimize" / "optimization.proposals.jsonl"
    ):
        v.validate("optimization_proposal", row)
    for row in read_jsonl(
        run_dir / "pipeline" / "validate" / "acceptance.results.jsonl"
    ):
        v.validate("acceptance_result", row)
    patch_results_path = run_dir / "pipeline" / "apply" / "patch.results.jsonl"
    if not patch_results_path.exists():
        patch_results_path = run_dir / "pipeline" / "patch_generate" / "patch.results.jsonl"
    for row in read_jsonl(patch_results_path):
        v.validate("patch_result", row)
    for row in read_jsonl(run_dir / "pipeline" / "verification" / "ledger.jsonl"):
        v.validate("verification_record", row)
    v.validate("run_report", read_json(run_dir / "overview" / "report.json"))
    v.validate("ops_health", read_json(run_dir / "pipeline" / "ops" / "health.json"))
    v.validate(
        "ops_topology", read_json(run_dir / "pipeline" / "ops" / "topology.json")
    )
    summary_path = run_dir / "pipeline" / "verification" / "summary.json"
    if summary_path.exists():
        v.validate("verification_summary", read_json(summary_path))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        validate_run_output(Path(sys.argv[1]))
    else:
        validate_schemas()
