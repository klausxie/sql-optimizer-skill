#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.contracts import ContractValidator
from sqlopt.io_utils import read_json, read_jsonl

p = Path(sys.argv[1])
v = ContractValidator(ROOT)
for row in read_jsonl(p / "pipeline" / "scan" / "sqlunits.jsonl"):
    v.validate("sqlunit", row)
for row in read_jsonl(p / "pipeline" / "scan" / "fragments.jsonl"):
    v.validate("fragment_record", row)
for row in read_jsonl(p / "pipeline" / "optimize" / "optimization.proposals.jsonl"):
    v.validate("optimization_proposal", row)
for row in read_jsonl(p / "pipeline" / "validate" / "acceptance.results.jsonl"):
    v.validate("acceptance_result", row)
for row in read_jsonl(p / "pipeline" / "patch_generate" / "patch.results.jsonl"):
    v.validate("patch_result", row)
for row in read_jsonl(p / "pipeline" / "verification" / "ledger.jsonl"):
    v.validate("verification_record", row)
v.validate("run_report", read_json(p / "overview" / "report.json"))
v.validate("ops_health", read_json(p / "pipeline" / "ops" / "health.json"))
v.validate("ops_topology", read_json(p / "pipeline" / "ops" / "topology.json"))
summary_path = p / "pipeline" / "verification" / "summary.json"
if summary_path.exists():
    v.validate("verification_summary", read_json(summary_path))
print("ok")
