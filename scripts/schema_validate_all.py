#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.contracts import ContractValidator
from sqlopt.io_utils import read_json, read_jsonl

p = Path(sys.argv[1])
v = ContractValidator(ROOT)


def validate_jsonl(path: Path, schema_name: str) -> None:
    if not path.exists():
        return
    for row in read_jsonl(path):
        v.validate(schema_name, row)


validate_jsonl(p / "artifacts" / "scan.jsonl", "sqlunit")
validate_jsonl(p / "artifacts" / "fragments.jsonl", "fragment_record")
validate_jsonl(p / "artifacts" / "proposals.jsonl", "optimization_proposal")
validate_jsonl(p / "artifacts" / "acceptance.jsonl", "acceptance_result")
validate_jsonl(p / "artifacts" / "statement_convergence.jsonl", "statement_convergence")
validate_jsonl(p / "artifacts" / "patches.jsonl", "patch_result")

report_path = p / "report.json"
if report_path.exists():
    v.validate("run_report", read_json(report_path))

catalog_path = p / "sql" / "catalog.jsonl"
if catalog_path.exists():
    validate_jsonl(catalog_path, "sql_artifact_index_row")

print("ok")
