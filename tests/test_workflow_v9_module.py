from __future__ import annotations

from sqlopt.application import V9WorkflowEngine as ExportedV9WorkflowEngine, workflow_engine
from sqlopt.application.workflow_v9 import (
    STAGE_ORDER,
    V9WorkflowEngine,
    V9WorkflowEngine as DirectV9WorkflowEngine,
)
from sqlopt.application.v9_stages import (
    STAGE_ORDER as PACKAGE_STAGE_ORDER,
    build_stage_registry,
    get_stage_spec,
    merge_validation_into_proposal,
    normalize_sqlunit,
    run_init,
    run_optimize,
    run_parse,
    run_patch,
    run_recognition,
    run_stage,
)
from sqlopt.v9_pipeline import STAGE_ORDER as PIPELINE_STAGE_ORDER, require_v9_stage


def test_application_exports_v9_engine_alias() -> None:
    assert workflow_engine is ExportedV9WorkflowEngine
    assert ExportedV9WorkflowEngine is DirectV9WorkflowEngine


def test_workflow_v9_stage_order_is_canonical() -> None:
    assert STAGE_ORDER == ["init", "parse", "recognition", "optimize", "patch"]
    assert PIPELINE_STAGE_ORDER == STAGE_ORDER
    assert PACKAGE_STAGE_ORDER == STAGE_ORDER


def test_v9_stage_package_exports_stage_entrypoints() -> None:
    assert callable(build_stage_registry)
    assert callable(get_stage_spec)
    assert callable(require_v9_stage)
    assert callable(normalize_sqlunit)
    assert callable(merge_validation_into_proposal)
    assert callable(run_init)
    assert callable(run_parse)
    assert callable(run_recognition)
    assert callable(run_optimize)
    assert callable(run_patch)
    assert callable(run_stage)


def test_v9_workflow_rejects_legacy_target_stage_name(tmp_path) -> None:
    engine = V9WorkflowEngine(config={"project": {"root_path": str(tmp_path)}})

    try:
        engine.run(tmp_path, to_stage="discovery")
    except ValueError as exc:
        assert "unknown V9 target stage" in str(exc)
    else:
        raise AssertionError("expected ValueError for legacy target stage")
