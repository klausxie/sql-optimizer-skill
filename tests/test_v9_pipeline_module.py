from __future__ import annotations

import pytest

from sqlopt.v9_pipeline import DB_REQUIRED_STAGES, STAGE_ORDER, require_v9_stage


def test_v9_pipeline_stage_order_is_canonical() -> None:
    assert STAGE_ORDER == ["init", "parse", "recognition", "optimize", "patch"]


def test_v9_pipeline_db_required_stages_are_runtime_backed() -> None:
    assert DB_REQUIRED_STAGES == {"recognition", "optimize"}


def test_require_v9_stage_accepts_known_stage() -> None:
    assert require_v9_stage("optimize") == "optimize"


def test_require_v9_stage_rejects_legacy_stage() -> None:
    with pytest.raises(ValueError):
        require_v9_stage("report")


def test_require_v9_stage_rejects_patch_generate_alias() -> None:
    with pytest.raises(ValueError):
        require_v9_stage("patch_generate")
