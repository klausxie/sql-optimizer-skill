"""Unit tests for scanner module - find_mapper_files function."""

import tempfile
from pathlib import Path

import pytest
from sqlopt.stages.init.scanner import find_mapper_files


class TestFindMapperFiles:
    """Tests for find_mapper_files function."""

    def test_find_single_xml_file(self):
        """Test finding a single XML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            xml_file = Path(tmpdir) / "test.xml"
            xml_file.write_text("<mapper></mapper>")

            result = find_mapper_files(tmpdir, ["*.xml"])
            assert len(result) == 1
            assert result[0].name == "test.xml"

    def test_find_multiple_xml_files(self):
        """Test finding multiple XML files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "file1.xml").write_text("<mapper></mapper>")
            (Path(tmpdir) / "file2.xml").write_text("<mapper></mapper>")
            (Path(tmpdir) / "file3.xml").write_text("<mapper></mapper>")

            result = find_mapper_files(tmpdir, ["*.xml"])
            assert len(result) == 3
            names = {r.name for r in result}
            assert names == {"file1.xml", "file2.xml", "file3.xml"}

    def test_find_nested_xml_files(self):
        """Test finding XML files in nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "subdir" / "nested"
            subdir.mkdir(parents=True)
            (subdir / "deep.xml").write_text("<mapper></mapper>")
            (Path(tmpdir) / "root.xml").write_text("<mapper></mapper>")

            result = find_mapper_files(tmpdir, ["**/*.xml"])
            assert len(result) == 2
            names = {r.name for r in result}
            assert "deep.xml" in names
            assert "root.xml" in names

    def test_glob_pattern_filter(self):
        """Test that glob pattern filters correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "UserMapper.xml").write_text("<mapper></mapper>")
            (Path(tmpdir) / "OrderMapper.xml").write_text("<mapper></mapper>")
            (Path(tmpdir) / "readme.txt").write_text("not xml")

            result = find_mapper_files(tmpdir, ["*Mapper.xml"])
            assert len(result) == 2
            names = {r.name for r in result}
            assert "UserMapper.xml" in names
            assert "OrderMapper.xml" in names
            assert "readme.txt" not in names

    def test_no_matches_returns_empty(self):
        """Test that empty list is returned when no files match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "readme.txt").write_text("not xml")

            result = find_mapper_files(tmpdir, ["*.xml"])
            assert result == []

    def test_non_xml_files_excluded(self):
        """Test that non-XML files are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "file.xml").write_text("<mapper></mapper>")
            (Path(tmpdir) / "file.txt").write_text("text")
            (Path(tmpdir) / "file.json").write_text("{}")

            result = find_mapper_files(tmpdir, ["*"])
            assert len(result) == 1
            assert result[0].suffix == ".xml"

    def test_no_duplicates(self):
        """Test that same file is not returned multiple times."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "file.xml").write_text("<mapper></mapper>")

            result = find_mapper_files(tmpdir, ["*.xml", "**/*.xml", "file.xml"])
            assert len(result) == 1

    def test_finds_xml_files(self):
        """Test that XML files are found by glob pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "file1.xml").write_text("<mapper></mapper>")
            (Path(tmpdir) / "file2.xml").write_text("<mapper></mapper>")

            result = find_mapper_files(tmpdir, ["*.xml"])
            assert len(result) == 2

    def test_sorted_return_order(self):
        """Test that results are sorted alphabetically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "z_file.xml").write_text("<mapper></mapper>")
            (Path(tmpdir) / "a_file.xml").write_text("<mapper></mapper>")
            (Path(tmpdir) / "m_file.xml").write_text("<mapper></mapper>")

            result = find_mapper_files(tmpdir, ["*.xml"])
            names = [r.name for r in result]
            assert names == sorted(names)
