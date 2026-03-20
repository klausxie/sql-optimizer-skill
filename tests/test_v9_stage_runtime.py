from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

from sqlopt.application.v9_stages import STAGE_ORDER, build_stage_registry, run_stage
from sqlopt.contracts import ContractValidator
from sqlopt.supervisor import init_run


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


def test_run_stage_dispatches_individual_v9_stage_without_workflow(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_001"
    run_dir.mkdir(parents=True, exist_ok=True)

    with patch("sqlopt.stages.discovery.Scanner") as mock_scanner_class:
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
