from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

from sqlopt.application.v9_stages import STAGE_ORDER, build_stage_registry, run_stage
from sqlopt.contracts import ContractValidator
from sqlopt.supervisor import init_run

_REPO_ROOT = Path(__file__).resolve().parents[1]

_MIN_SQL_UNIT = {
    "sqlKey": "com.example.Demo.selectOne",
    "namespace": "com.example",
    "statementId": "selectOne",
    "statementType": "SELECT",
    "variantId": "v1",
    "xmlPath": "/tmp/Demo.xml",
    "sql": "SELECT 1 AS x",
    "templateSql": "SELECT 1 AS x",
    "parameterMappings": [],
    "paramExample": {},
    "locators": {},
    "dynamicTags": [],
    "riskFlags": [],
}


class DummyValidator:
    def validate_stage_input(self, _stage: str, _data: object) -> None:
        return None

    def validate_stage_output(self, _stage: str, _data: object) -> None:
        return None


def test_build_stage_registry_exposes_canonical_v9_stage_order(tmp_path: Path) -> None:
    registry = build_stage_registry(
        config={"project": {"root_path": str(tmp_path)}},
        validator=ContractValidator(Path.cwd()),
    )

    assert list(registry.keys()) == STAGE_ORDER


def test_run_stage_dispatches_individual_v9_stage_without_workflow(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run_001"
    run_dir.mkdir(parents=True, exist_ok=True)

    with patch("sqlopt.application.v9_stages.init.Scanner") as mock_scanner_class:
        mock_result = Mock()
        mock_result.sql_units = [{"sqlKey": "demo.user.find", "sql": "select 1"}]
        mock_scanner_class.return_value.scan.return_value = mock_result

        result = run_stage(
            "init",
            run_dir,
            config={"project": {"root_path": str(tmp_path)}},
            validator=DummyValidator(),
        )

    assert result["success"] is True
    saved_units = json.loads((run_dir / "init" / "sql_units.json").read_text())
    assert saved_units[0]["sqlKey"] == "demo.user.find"


def test_run_parse_fixture_writes_parse_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_parse"
    run_dir.mkdir()
    init_dir = run_dir / "init"
    init_dir.mkdir(parents=True)
    (init_dir / "sql_units.json").write_text(
        json.dumps([_MIN_SQL_UNIT], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    validator = ContractValidator(_REPO_ROOT)
    result = run_stage(
        "parse",
        run_dir,
        config={"project": {"root_path": str(tmp_path)}},
        validator=validator,
    )
    assert result["success"] is True
    branches_path = run_dir / "parse" / "sql_units_with_branches.json"
    risks_path = run_dir / "parse" / "risks.json"
    assert branches_path.is_file()
    assert risks_path.is_file()
    units = json.loads(branches_path.read_text(encoding="utf-8"))
    assert isinstance(units, list) and units[0].get("branches")


def test_run_parse_missing_init_returns_error(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_noparse"
    run_dir.mkdir()
    result = run_stage(
        "parse",
        run_dir,
        config={"project": {"root_path": str(tmp_path)}},
        validator=ContractValidator(_REPO_ROOT),
    )
    assert result["success"] is False
    assert "Init" in str(result.get("error", ""))


@patch("sqlopt.application.v9_stages.recognition.collect_baseline_v9")
def test_run_recognition_fixture_writes_baselines(
    mock_collect: Mock, tmp_path: Path
) -> None:
    run_dir = tmp_path / "run_rec"
    run_dir.mkdir()
    parse_dir = run_dir / "parse"
    parse_dir.mkdir(parents=True)
    unit = dict(_MIN_SQL_UNIT)
    unit["branches"] = [
        {"id": 1, "conditions": [], "sql": "SELECT 1", "type": "static"}
    ]
    unit["branchCount"] = 1
    unit["problemBranchCount"] = 0
    (parse_dir / "sql_units_with_branches.json").write_text(
        json.dumps([unit], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    mock_collect.return_value = [
        {
            "sqlKey": unit["sqlKey"],
            "executionTimeMs": 0.1,
            "rowsExamined": 0,
            "rowsReturned": 1,
            "databasePlatform": "postgresql",
            "sampleParams": {},
            "actualExecutionTimeMs": 0.1,
            "bufferHitCount": 0,
            "bufferReadCount": 0,
            "explainPlan": {"scan_type": "Seq Scan", "estimated_cost": 0.01},
            "indexUsed": None,
        }
    ]
    validator = ContractValidator(_REPO_ROOT)
    result = run_stage(
        "recognition",
        run_dir,
        config={"project": {"root_path": str(tmp_path)}, "db": {}},
        validator=validator,
    )
    assert result["success"] is True
    out = run_dir / "recognition" / "baselines.json"
    assert out.is_file()
    rows = json.loads(out.read_text(encoding="utf-8"))
    assert rows and rows[0].get("sql_key") == unit["sqlKey"]


def test_run_optimize_fixture_writes_proposals(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_opt"
    run_dir.mkdir()
    parse_dir = run_dir / "parse"
    parse_dir.mkdir(parents=True)
    unit = dict(_MIN_SQL_UNIT)
    unit["branches"] = [
        {"id": 1, "conditions": [], "sql": "SELECT 1", "type": "static"}
    ]
    (parse_dir / "sql_units_with_branches.json").write_text(
        json.dumps([unit], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    rec_dir = run_dir / "recognition"
    rec_dir.mkdir(parents=True)
    (rec_dir / "baselines.json").write_text(
        json.dumps(
            [
                {
                    "sql_key": unit["sqlKey"],
                    "execution_time_ms": 0.1,
                    "rows_scanned": 0,
                    "execution_plan": {
                        "node_type": "Seq Scan",
                        "index_used": None,
                        "cost": 0.01,
                    },
                    "result_hash": "abc123def456",
                    "rows_returned": 1,
                    "database_platform": "postgresql",
                    "sample_params": {},
                    "actual_execution_time_ms": 0.1,
                    "buffer_hit_count": 0,
                    "buffer_read_count": 0,
                    "explain_plan": {"scan_type": "Seq Scan", "estimated_cost": 0.01},
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    cfg = {
        "project": {"root_path": str(tmp_path)},
        "db": {},
        "llm": {"enabled": False, "provider": "heuristic"},
    }
    result = run_stage(
        "optimize",
        run_dir,
        config=cfg,
        validator=ContractValidator(_REPO_ROOT),
    )
    assert result["success"] is True
    prop_path = run_dir / "optimize" / "proposals.json"
    assert prop_path.is_file()
    proposals = json.loads(prop_path.read_text(encoding="utf-8"))
    assert isinstance(proposals, list) and proposals[0].get("sqlKey") == unit["sqlKey"]


def test_run_patch_fixture_writes_patches_for_validated_proposal(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run_patch"
    run_dir.mkdir()
    opt_dir = run_dir / "optimize"
    opt_dir.mkdir(parents=True)
    proposal = {
        "sqlKey": _MIN_SQL_UNIT["sqlKey"],
        "issues": [],
        "dbEvidenceSummary": {},
        "planSummary": {},
        "suggestions": [],
        "verdict": "ACTIONABLE",
        "confidence": "high",
        "estimatedBenefit": "medium",
        "validated": True,
        "validationStatus": "PASS",
        "originalSql": "SELECT 1",
        "optimizedSql": "SELECT 1 WHERE 1=1",
        "rewrittenSql": "SELECT 1 WHERE 1=1",
        "ruleName": "demo_rule",
    }
    (opt_dir / "proposals.json").write_text(
        json.dumps([proposal], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result = run_stage(
        "patch",
        run_dir,
        config={"project": {"root_path": str(tmp_path)}},
        validator=ContractValidator(_REPO_ROOT),
    )
    assert result["success"] is True
    patches_path = run_dir / "patch" / "patches.json"
    assert patches_path.is_file()
    patches = json.loads(patches_path.read_text(encoding="utf-8"))
    assert patches and patches[0].get("applicable") is True


def test_init_run_writes_v9_supervisor_state_shape(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "run_demo"
    init_run(run_dir, {"config_version": "v1"}, "run_demo")

    state = json.loads((run_dir / "supervisor" / "state.json").read_text())
    plan = json.loads((run_dir / "supervisor" / "plan.json").read_text())

    assert state["completed_stages"] == []
    assert state["current_stage"] == ""
    assert state["status"] == "pending"
    assert plan["phases"] == STAGE_ORDER
    assert plan["to_stage"] == "patch"
