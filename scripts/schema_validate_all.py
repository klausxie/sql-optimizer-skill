#!/usr/bin/env python3
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
    for row in read_jsonl(
        run_dir / "pipeline" / "patch_generate" / "patch.results.jsonl"
    ):
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
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        validate_run_output(Path(sys.argv[1]))
    else:
        validate_schemas()
