from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "schema_validate_all.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("schema_validate_all_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_validate_run_output_supports_v9_layout(tmp_path: Path) -> None:
    mod = _load_module()
    run_dir = tmp_path / "runs" / "run_demo"

    sqlunit = {
        "sqlKey": "com.example.Mapper.selectAll",
        "xmlPath": "/tmp/mapper.xml",
        "namespace": "com.example.Mapper",
        "statementId": "selectAll",
        "statementType": "SELECT",
        "variantId": "v1",
        "sql": "SELECT * FROM users",
        "parameterMappings": [],
        "paramExample": {},
        "locators": {},
        "riskFlags": ["prefix_wildcard"],
        "branches": [
            {
                "id": 1,
                "conditions": [],
                "sql": "SELECT * FROM users",
                "type": "static",
            }
        ],
        "branchCount": 1,
        "problemBranchCount": 1,
    }
    risk_report = {
        "sqlKey": "com.example.Mapper.selectAll",
        "risks": [
            {
                "riskType": "prefix_wildcard",
                "severity": "HIGH",
                "message": "leading wildcard disables index lookups",
                "branchIds": [1],
            }
        ],
        "prunedBranches": [],
        "recommendedForBaseline": True,
    }
    baseline = {
        "sql_key": "com.example.Mapper.selectAll",
        "execution_time_ms": 10.5,
        "rows_scanned": 100,
        "execution_plan": {"node_type": "Seq Scan"},
        "result_hash": "abc123",
    }
    proposal = {
        "sqlKey": "com.example.Mapper.selectAll",
        "issues": ["PREFIX_WILDCARD"],
        "dbEvidenceSummary": {},
        "planSummary": {},
        "suggestions": [],
        "verdict": "ACTIONABLE",
        "validated": True,
        "validationStatus": "PASS",
        "originalSql": "SELECT * FROM users",
        "optimizedSql": "SELECT id FROM users",
    }
    patch_result = {
        "sqlKey": "com.example.Mapper.selectAll",
        "patchFiles": [],
        "diffSummary": {},
        "applyMode": "MANUAL",
        "rollback": "restore original mapper backup",
    }

    _write_json(run_dir / "init" / "sql_units.json", [sqlunit])
    _write_json(run_dir / "parse" / "sql_units_with_branches.json", [sqlunit])
    _write_json(run_dir / "parse" / "risks.json", [risk_report])
    _write_json(run_dir / "recognition" / "baselines.json", [baseline])
    _write_json(run_dir / "optimize" / "proposals.json", [proposal])
    _write_json(run_dir / "patch" / "patches.json", [patch_result])

    mod.validate_run_output(run_dir)
