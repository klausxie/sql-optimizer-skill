"""Tests for ContractFileManager."""

import json
import tempfile
from pathlib import Path

import pytest
from sqlopt.common.contract_file_manager import ContractFileManager


class TestContractFileManagerInit:
    """Test ContractFileManager initialization."""

    def test_init_stores_run_id(self):
        """Test ContractFileManager stores run_id correctly."""
        mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
        assert mgr.run_id == "run-123"

    def test_init_stores_stage_name(self):
        """Test ContractFileManager stores stage_name correctly."""
        mgr = ContractFileManager(run_id="run-123", stage_name="optimize")
        assert mgr.stage_name == "optimize"

    def test_units_dir_constructed_correctly(self):
        """Test units_dir is constructed as runs/{run_id}/{stage_name}/units."""
        mgr = ContractFileManager(run_id="run-456", stage_name="recognition")
        assert mgr.units_dir == Path("runs") / "run-456" / "recognition" / "units"


class TestWriteUnitFile:
    """Test write_unit_file() method."""

    def test_write_unit_file_creates_file(self):
        """Test write_unit_file creates the unit file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            data = {"sql": "SELECT * FROM users", "params": ["id"]}
            result = mgr.write_unit_file("UserMapper.findUser", data)

            assert result.exists()
            assert result.name == "UserMapper.findUser.json"

    def test_write_unit_file_saves_json_data(self):
        """Test write_unit_file saves correct JSON data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            data = {"sql": "SELECT * FROM users", "params": ["id"]}
            mgr.write_unit_file("UserMapper.findUser", data)

            file_path = mgr.units_dir / "UserMapper.findUser.json"
            loaded = json.loads(file_path.read_text(encoding="utf-8"))
            assert loaded == data

    def test_write_unit_file_sanitizes_filename(self):
        """Test write_unit_file sanitizes unit ID with special characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            data = {"sql": "SELECT 1"}
            mgr.write_unit_file("foo/bar", data)

            # foo/bar should have / sanitized to _
            assert (mgr.units_dir / "foo_bar.json").exists()

    def test_write_unit_file_creates_parent_dirs(self):
        """Test write_unit_file creates parent directories if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            assert not mgr.units_dir.exists()

            data = {"sql": "SELECT 1"}
            mgr.write_unit_file("UserMapper.findUser", data)

            assert mgr.units_dir.exists()
            assert mgr.units_dir.is_dir()

    def test_write_unit_file_returns_path(self):
        """Test write_unit_file returns Path to the written file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            data = {"sql": "SELECT 1"}
            result = mgr.write_unit_file("UserMapper.findUser", data)

            assert isinstance(result, Path)
            assert result == mgr.units_dir / "UserMapper.findUser.json"


class TestWriteIndex:
    """Test write_index() method with atomic rename pattern."""

    def test_write_index_creates_index_file(self):
        """Test write_index creates the _index.json file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            mgr.write_index(["UserMapper.findUser", "OrderMapper.findOrders"])

            index_path = mgr.units_dir / "_index.json"
            assert index_path.exists()

    def test_write_index_saves_unit_ids(self):
        """Test write_index saves correct unit IDs list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            unit_ids = ["UserMapper.findUser", "OrderMapper.findOrders"]
            mgr.write_index(unit_ids)

            index_path = mgr.units_dir / "_index.json"
            loaded = json.loads(index_path.read_text(encoding="utf-8"))
            assert loaded == unit_ids

    def test_write_index_uses_atomic_rename(self):
        """Test write_index uses temp file then rename pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            mgr.write_index(["UserMapper.findUser"])

            # Temp file should not exist after rename
            temp_path = mgr.units_dir / "_index.json.tmp"
            assert not temp_path.exists()

            # Actual index file should exist
            index_path = mgr.units_dir / "_index.json"
            assert index_path.exists()

    def test_write_index_creates_parent_dirs(self):
        """Test write_index creates parent directories if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            assert not mgr.units_dir.exists()

            mgr.write_index(["UserMapper.findUser"])

            assert mgr.units_dir.exists()
            assert mgr.units_dir.is_dir()


class TestReadUnitFile:
    """Test read_unit_file() method."""

    def test_read_unit_file_returns_data(self):
        """Test read_unit_file returns the saved data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            data = {"sql": "SELECT * FROM users", "params": ["id"]}
            mgr.write_unit_file("UserMapper.findUser", data)

            loaded = mgr.read_unit_file("UserMapper.findUser")
            assert loaded == data

    def test_read_unit_file_raises_on_missing_file(self):
        """Test read_unit_file raises FileNotFoundError when file missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            with pytest.raises(FileNotFoundError):
                mgr.read_unit_file("NonExistent.unit")

    def test_read_unit_file_with_sanitized_name(self):
        """Test read_unit_file works with sanitized unit ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            data = {"sql": "SELECT 1"}
            mgr.write_unit_file("foo/bar", data)

            loaded = mgr.read_unit_file("foo/bar")
            assert loaded == data


class TestReadIndex:
    """Test read_index() method."""

    def test_read_index_returns_unit_ids(self):
        """Test read_index returns the saved unit IDs list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            unit_ids = ["UserMapper.findUser", "OrderMapper.findOrders"]
            mgr.write_index(unit_ids)

            loaded = mgr.read_index()
            assert loaded == unit_ids

    def test_read_index_raises_on_missing_file(self):
        """Test read_index raises FileNotFoundError when index missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            with pytest.raises(FileNotFoundError):
                mgr.read_index()


class TestGetFileSize:
    """Test get_file_size() method."""

    def test_get_file_size_returns_bytes(self):
        """Test get_file_size returns correct file size in bytes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            data = {"sql": "SELECT * FROM users"}
            file_path = mgr.write_unit_file("UserMapper.findUser", data)

            size = mgr.get_file_size(file_path)
            assert size > 0
            assert isinstance(size, int)

    def test_get_file_size_raises_on_missing_file(self):
        """Test get_file_size raises FileNotFoundError when file missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
            mgr.units_dir = Path(tmpdir) / "runs" / "run-123" / "recognition" / "units"

            missing_path = mgr.units_dir / "nonexistent.json"

            with pytest.raises(FileNotFoundError):
                mgr.get_file_size(missing_path)


class TestSanitizeFilename:
    """Test _sanitize_filename() method."""

    def test_sanitize_replaces_forward_slash(self):
        """Test _sanitize_filename replaces forward slash with underscore."""
        mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
        assert mgr._sanitize_filename("foo/bar") == "foo_bar"

    def test_sanitize_replaces_backslash(self):
        """Test _sanitize_filename replaces backslash with underscore."""
        mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
        assert mgr._sanitize_filename("foo\\bar") == "foo_bar"

    def test_sanitize_replaces_question_mark(self):
        """Test _sanitize_filename replaces question mark with underscore."""
        mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
        assert mgr._sanitize_filename("foo?bar") == "foo_bar"

    def test_sanitize_replaces_asterisk(self):
        """Test _sanitize_filename replaces asterisk with underscore."""
        mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
        assert mgr._sanitize_filename("foo*bar") == "foo_bar"

    def test_sanitize_replaces_colon(self):
        """Test _sanitize_filename replaces colon with underscore."""
        mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
        assert mgr._sanitize_filename("foo:bar") == "foo_bar"

    def test_sanitize_preserves_valid_characters(self):
        """Test _sanitize_filename preserves alphanumeric and valid chars."""
        mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
        assert mgr._sanitize_filename("UserMapper.findUser") == "UserMapper.findUser"

    def test_sanitize_handles_multiple_special_chars(self):
        """Test _sanitize_filename handles multiple special characters."""
        mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
        assert mgr._sanitize_filename("a?b*c") == "a_b_c"

    def test_sanitize_handles_all_invalid_chars(self):
        """Test _sanitize_filename replaces all invalid filename characters."""
        mgr = ContractFileManager(run_id="run-123", stage_name="recognition")
        result = mgr._sanitize_filename("a/b\\c?d*e:f")
        assert result == "a_b_c_d_e_f"
