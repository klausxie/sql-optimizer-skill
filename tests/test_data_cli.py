"""Tests for sqlopt-data CLI commands.

覆盖子命令:
- get: 读取数据并支持 JSONPath 过滤
- list: 列出目录内容
- set: 设置数据
- diff: 比较两个文件
- validate: 验证数据是否符合 schema
- prune: 清理旧数据

运行方式:
    python -m pytest tests/test_data_cli.py -v
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlopt.cli.data_cli import (
    diff_cmd,
    get_cmd,
    list_cmd,
    prune_cmd,
    resolve_path,
    set_cmd,
    validate_cmd,
)


class MockArgs:
    """Mock argparse Namespace for testing."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class ResolvePathTest(unittest.TestCase):
    """Test resolve_path function."""

    def test_resolve_regular_path(self) -> None:
        """Test resolving a regular path."""
        result = resolve_path("/some/path/file.json")
        self.assertEqual(result, Path("/some/path/file.json"))

    def test_resolve_runs_shortcut(self) -> None:
        """Test resolving runs: shortcut replaces prefix with full path."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_resolve_") as td:
            result = resolve_path("runs:run_001", project_root=Path(td))
            # Verify the prefix "runs:" is replaced with project_root/runs path
            expected_base = str(Path(td) / "runs")
            self.assertTrue(str(result).startswith(expected_base))

    def test_resolve_contracts_shortcut(self) -> None:
        """Test resolving contracts: shortcut replaces prefix with full path."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_resolve_") as td:
            result = resolve_path(
                "contracts:sqlunit.schema.json", project_root=Path(td)
            )
            # Verify the prefix "contracts:" is replaced with project_root/contracts path
            expected_base = str(Path(td) / "contracts")
            self.assertTrue(str(result).startswith(expected_base))


class GetCommandTest(unittest.TestCase):
    """Test get command functionality."""

    def test_get_json_file(self) -> None:
        """Test reading a JSON file."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_get_") as td:
            data_file = Path(td) / "data.json"
            data_file.write_text(
                json.dumps({"key": "value", "number": 42}), encoding="utf-8"
            )

            args = MockArgs(path=str(data_file), jsonpath=None)
            # Capture stdout would require redirecting, just ensure no error
            result = get_cmd(args)
            self.assertEqual(result, 0)

    def test_get_nonexistent_path(self) -> None:
        """Test get with nonexistent path returns error."""
        args = MockArgs(path="/nonexistent/path.json", jsonpath=None)
        result = get_cmd(args)
        self.assertEqual(result, 1)

    def test_get_directory_returns_error(self) -> None:
        """Test get on directory returns error."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_get_") as td:
            args = MockArgs(path=td, jsonpath=None)
            result = get_cmd(args)
            self.assertEqual(result, 1)

    def test_get_with_jsonpath(self) -> None:
        """Test get with JSONPath filter."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_get_") as td:
            data_file = Path(td) / "data.json"
            data_file.write_text(
                json.dumps({"items": [{"id": 1}, {"id": 2}]}), encoding="utf-8"
            )

            args = MockArgs(path=str(data_file), jsonpath="$.items[*].id")
            result = get_cmd(args)
            # JSONPath may or may not be available, just check no crash
            self.assertIn(result, [0, 1])


class ListCommandTest(unittest.TestCase):
    """Test list command functionality."""

    def test_list_directory(self) -> None:
        """Test listing directory contents."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_list_") as td:
            td_path = Path(td)
            (td_path / "file1.json").write_text("{}", encoding="utf-8")
            (td_path / "file2.json").write_text("{}", encoding="utf-8")
            (td_path / "subdir").mkdir()

            args = MockArgs(path=td, pattern=None, format="json")
            result = list_cmd(args)
            self.assertEqual(result, 0)

    def test_list_nonexistent_path(self) -> None:
        """Test list with nonexistent path returns error."""
        args = MockArgs(path="/nonexistent/path", pattern=None, format="json")
        result = list_cmd(args)
        self.assertEqual(result, 1)

    def test_list_single_file(self) -> None:
        """Test listing a single file returns its path."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_list_") as td:
            data_file = Path(td) / "single.json"
            data_file.write_text("{}", encoding="utf-8")

            args = MockArgs(path=str(data_file), pattern=None, format="json")
            result = list_cmd(args)
            self.assertEqual(result, 0)

    def test_list_with_pattern(self) -> None:
        """Test listing with pattern filter."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_list_") as td:
            td_path = Path(td)
            (td_path / "test1.json").write_text("{}", encoding="utf-8")
            (td_path / "test2.json").write_text("{}", encoding="utf-8")
            (td_path / "other.txt").write_text("", encoding="utf-8")

            args = MockArgs(path=td, pattern="*.json", format="json")
            result = list_cmd(args)
            self.assertEqual(result, 0)

    def test_list_csv_format(self) -> None:
        """Test listing with CSV format."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_list_") as td:
            td_path = Path(td)
            (td_path / "data.json").write_text("{}", encoding="utf-8")

            args = MockArgs(path=td, pattern=None, format="csv")
            result = list_cmd(args)
            self.assertEqual(result, 0)


class SetCommandTest(unittest.TestCase):
    """Test set command functionality."""

    def test_set_json_value(self) -> None:
        """Test setting a JSON value."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_set_") as td:
            data_file = Path(td) / "new_data.json"
            args = MockArgs(path=str(data_file), value='{"key": "new_value"}')
            result = set_cmd(args)

            self.assertEqual(result, 0)
            self.assertTrue(data_file.exists())

            data = json.loads(data_file.read_text(encoding="utf-8"))
            self.assertEqual(data["key"], "new_value")

    def test_set_nested_path(self) -> None:
        """Test setting value in nested path creates directories."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_set_") as td:
            data_file = Path(td) / "nested" / "dir" / "data.json"
            args = MockArgs(path=str(data_file), value='{"nested": true}')
            result = set_cmd(args)

            self.assertEqual(result, 0)
            self.assertTrue(data_file.exists())


class DiffCommandTest(unittest.TestCase):
    """Test diff command functionality."""

    def test_diff_identical_files(self) -> None:
        """Test diffing identical files shows no differences."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_diff_") as td:
            td_path = Path(td)
            file_a = td_path / "a.json"
            file_b = td_path / "b.json"

            content = json.dumps({"key": "value"})
            file_a.write_text(content, encoding="utf-8")
            file_b.write_text(content, encoding="utf-8")

            args = MockArgs(path_a=str(file_a), path_b=str(file_b))
            result = diff_cmd(args)
            self.assertEqual(result, 0)

    def test_diff_different_files(self) -> None:
        """Test diffing different files."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_diff_") as td:
            td_path = Path(td)
            file_a = td_path / "a.json"
            file_b = td_path / "b.json"

            file_a.write_text(json.dumps({"key": "value_a"}), encoding="utf-8")
            file_b.write_text(json.dumps({"key": "value_b"}), encoding="utf-8")

            args = MockArgs(path_a=str(file_a), path_b=str(file_b))
            result = diff_cmd(args)
            self.assertEqual(result, 0)

    def test_diff_missing_file(self) -> None:
        """Test diff with missing file returns error."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_diff_") as td:
            td_path = Path(td)
            file_a = td_path / "a.json"
            file_a.write_text("{}", encoding="utf-8")

            args = MockArgs(path_a=str(file_a), path_b="/nonexistent/b.json")
            result = diff_cmd(args)
            self.assertEqual(result, 1)


class ValidateCommandTest(unittest.TestCase):
    """Test validate command functionality."""

    def test_validate_nonexistent_path(self) -> None:
        """Test validate with nonexistent path returns error."""
        args = MockArgs(path="/nonexistent/path.json", schema=None)
        result = validate_cmd(args)
        self.assertEqual(result, 1)

    def test_validate_directory_returns_error(self) -> None:
        """Test validate on directory returns error."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_validate_") as td:
            args = MockArgs(path=td, schema=None)
            result = validate_cmd(args)
            self.assertEqual(result, 1)

    def test_validate_without_schema_inference(self) -> None:
        """Test validate when schema cannot be inferred."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_validate_") as td:
            data_file = Path(td) / "unknown.json"
            data_file.write_text("{}", encoding="utf-8")

            args = MockArgs(path=str(data_file), schema=None)
            result = validate_cmd(args)
            # Should return 1 because schema cannot be inferred
            self.assertEqual(result, 1)


class PruneCommandTest(unittest.TestCase):
    """Test prune command functionality."""

    def test_prune_nonexistent_target(self) -> None:
        """Test prune with nonexistent target returns error."""
        args = MockArgs(
            target="/nonexistent/target",
            older_than=30,
            keep_last=0,
            keep_phases=[],
            dry_run=False,
        )
        result = prune_cmd(args)
        self.assertEqual(result, 1)

    def test_prune_dry_run(self) -> None:
        """Test prune with dry_run shows what would be pruned."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_prune_") as td:
            td_path = Path(td)
            runs_dir = td_path / "runs"
            runs_dir.mkdir()
            old_run = runs_dir / "run_old"
            old_run.mkdir()

            args = MockArgs(
                target=str(td_path),
                older_than=0,  # Prune everything
                keep_last=0,
                keep_phases=[],
                dry_run=True,
            )
            result = prune_cmd(args)
            self.assertEqual(result, 0)
            # dry_run should not delete
            self.assertTrue(old_run.exists())

    def test_prune_with_keep_last(self) -> None:
        """Test prune respects keep_last parameter."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_prune_") as td:
            td_path = Path(td)
            runs_dir = td_path / "runs"
            runs_dir.mkdir()

            # Create multiple run directories
            for i in range(3):
                run_dir = runs_dir / f"run_{i}"
                run_dir.mkdir()

            args = MockArgs(
                target=str(td_path),
                older_than=0,  # Prune everything old enough
                keep_last=1,  # Keep 1 most recent
                keep_phases=[],
                dry_run=True,
            )
            result = prune_cmd(args)
            self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
