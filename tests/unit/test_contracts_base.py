"""Tests for sqlopt.contracts.base module."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlopt.contracts.base import (
    dataclass_to_json,
    json_to_dataclass,
    load_json_file,
    save_json_file,
)


@dataclass
class SampleDataclass:
    """Sample dataclass for testing."""

    name: str
    value: int
    active: bool = True


class TestDataclassToJson:
    """Tests for dataclass_to_json function."""

    def test_dataclass_to_json_basic(self) -> None:
        """Test serialization of basic dataclass."""
        obj = SampleDataclass(name="test", value=42, active=True)
        result = dataclass_to_json(obj)

        parsed = json.loads(result)
        assert parsed["name"] == "test"
        assert parsed["value"] == 42
        assert parsed["active"] is True

    def test_dataclass_to_json_with_defaults(self) -> None:
        """Test serialization with default values."""
        obj = SampleDataclass(name="test", value=0)
        result = dataclass_to_json(obj)

        parsed = json.loads(result)
        assert parsed["name"] == "test"
        assert parsed["value"] == 0
        assert parsed["active"] is True  # default

    def test_dataclass_to_json_nested(self) -> None:
        """Test serialization of nested dataclass structure."""

        @dataclass
        class Inner:
            x: int

        @dataclass
        class Outer:
            inner: Inner
            label: str

        obj = Outer(inner=Inner(x=10), label="outer")
        result = dataclass_to_json(obj)

        parsed = json.loads(result)
        assert parsed["inner"]["x"] == 10
        assert parsed["label"] == "outer"

    def test_dataclass_to_json_raises_for_non_dataclass(self) -> None:
        """Test that TypeError is raised for non-dataclass objects."""
        with pytest.raises(TypeError, match=r"Expected dataclass instance"):
            dataclass_to_json("not a dataclass")

        with pytest.raises(TypeError, match=r"Expected dataclass instance"):
            dataclass_to_json({"key": "value"})

        with pytest.raises(TypeError, match=r"Expected dataclass instance"):
            dataclass_to_json([1, 2, 3])


class TestJsonToDataclass:
    """Tests for json_to_dataclass function."""

    def test_json_to_dataclass_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {"name": "test", "value": 42, "active": False}
        result = json_to_dataclass(SampleDataclass, data)

        assert isinstance(result, SampleDataclass)
        assert result.name == "test"
        assert result.value == 42
        assert result.active is False

    def test_json_to_dataclass_from_json_string(self) -> None:
        json_str = '{"name": "test", "value": 42, "active": true}'
        result = json_to_dataclass(SampleDataclass, json_str)

        assert isinstance(result, SampleDataclass)
        assert result.name == "test"
        assert result.value == 42
        assert result.active is True

    def test_json_to_dataclass_with_defaults(self) -> None:
        """Test that missing fields use defaults."""
        data = {"name": "test", "value": 42}  # missing 'active'
        result = json_to_dataclass(SampleDataclass, data)

        assert result.active is True  # default

    def test_json_to_dataclass_preserves_bool_false(self) -> None:
        """Test that False values are preserved correctly."""
        data = {"name": "test", "value": 0, "active": False}
        result = json_to_dataclass(SampleDataclass, data)

        assert result.value == 0
        assert result.active is False


class TestLoadJsonFile:
    """Tests for load_json_file function."""

    def test_load_json_file_from_pathlib(self) -> None:
        """Test loading from pathlib.Path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"key": "value", "num": 123}, f)
            temp_path = Path(f.name)

        try:
            result = load_json_file(temp_path)
            assert result["key"] == "value"
            assert result["num"] == 123
        finally:
            temp_path.unlink()

    def test_load_json_file_from_string(self) -> None:
        """Test loading from string path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"name": "test"}, f)
            temp_path = f.name

        try:
            result = load_json_file(temp_path)
            assert result["name"] == "test"
        finally:
            Path(temp_path).unlink()

    def test_load_json_file_nested_data(self) -> None:
        """Test loading nested JSON data."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
                    "count": 2,
                },
                f,
            )
            temp_path = f.name

        try:
            result = load_json_file(temp_path)
            assert len(result["users"]) == 2
            assert result["count"] == 2
        finally:
            Path(temp_path).unlink()


class TestSaveJsonFile:
    """Tests for save_json_file function."""

    def test_save_json_file_from_dict(self) -> None:
        """Test saving dictionary data."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            data = {"key": "value", "number": 42}
            save_json_file(data, temp_path)

            with Path(temp_path).open(encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded["key"] == "value"
            assert loaded["number"] == 42
        finally:
            Path(temp_path).unlink()

    def test_save_json_file_from_dataclass(self) -> None:
        """Test saving dataclass instance."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            obj = SampleDataclass(name="test", value=99, active=True)
            save_json_file(obj, temp_path)

            with Path(temp_path).open(encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded["name"] == "test"
            assert loaded["value"] == 99
            assert loaded["active"] is True
        finally:
            Path(temp_path).unlink()

    def test_save_json_file_indentation(self) -> None:
        """Test that saved JSON is indented."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            data = {"nested": {"key": "value"}}
            save_json_file(data, temp_path)

            with Path(temp_path).open(encoding="utf-8") as f:
                content = f.read()
            # Check for indentation (should have newlines/indentation)
            assert "\n" in content or "  " in content
        finally:
            Path(temp_path).unlink()

    def test_save_json_file_overwrites(self) -> None:
        """Test that save overwrites existing file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"old": "data"}, f)
            temp_path = f.name

        try:
            save_json_file({"new": "data"}, temp_path)

            with Path(temp_path).open(encoding="utf-8") as f:
                loaded = json.load(f)
            assert "old" not in loaded
            assert loaded["new"] == "data"
        finally:
            Path(temp_path).unlink()
