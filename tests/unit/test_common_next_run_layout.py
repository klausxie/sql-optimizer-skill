from pathlib import Path

from sqlopt.common.next_run_layout import NextRunLayout


def test_next_run_layout_creates_documented_directories(tmp_path: Path) -> None:
    layout = NextRunLayout("run-next-001", base_dir=str(tmp_path))

    layout.ensure_dirs()

    assert (tmp_path / "run-next-001" / "init" / "sql_units" / "by_namespace").exists()
    assert (tmp_path / "run-next-001" / "recognition" / "execution" / "shards").exists()
    assert (tmp_path / "run-next-001" / "result" / "patches" / "by_namespace").exists()


def test_next_run_layout_path_helpers_match_contract_layout(tmp_path: Path) -> None:
    layout = NextRunLayout("run-next-002", base_dir=str(tmp_path))

    sql_unit_path = layout.init_sql_unit_file("com.foo.user.UserMapper", "findById")
    branch_path = layout.parse_branch_file("com.foo.user.UserMapper", "search", "branch_000127")
    finding_path = layout.recognition_finding_file("high", "finding_a1b2c3")
    patch_path = layout.result_patch_file("com.foo.user.UserMapper", "search")

    assert sql_unit_path == (
        tmp_path / "run-next-002" / "init" / "sql_units" / "by_namespace" / "com.foo.user.UserMapper" / "findById.json"
    )
    assert branch_path == (
        tmp_path
        / "run-next-002"
        / "parse"
        / "units"
        / "by_namespace"
        / "com.foo.user.UserMapper"
        / "search"
        / "branches"
        / "branch_000127.json"
    )
    assert finding_path == (
        tmp_path / "run-next-002" / "recognition" / "findings" / "by_severity" / "high" / "finding_a1b2c3.json"
    )
    assert patch_path == (
        tmp_path / "run-next-002" / "result" / "patches" / "by_namespace" / "com.foo.user.UserMapper" / "search.json"
    )


def test_next_run_layout_rejects_unknown_stage(tmp_path: Path) -> None:
    layout = NextRunLayout("run-next-003", base_dir=str(tmp_path))

    try:
        layout.stage_dir("unknown")
    except ValueError as exc:
        assert "Unknown stage" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown stage")
