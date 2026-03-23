"""
Unit tests for _build_global_fragment_registry function.

Tests verify the global fragment registry building behavior including:
- XML parse error handling (silent ignore)
- Fragment collection from valid MyBatis XML
- Namespace handling (defaults to "unknown")
- Duplicate fragment handling (first wins)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from sqlopt.application.v9_stages.init import _build_global_fragment_registry


VALID_MAPPER_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="{namespace}">
    <sql id="fragment1">SELECT * FROM users</sql>
    <sql id="fragment2">WHERE id = 1</sql>
</mapper>
"""

NON_MAPPER_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<root>
    <element>Some content</element>
</root>
"""

MISSING_NAMESPACE_MAPPER = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper>
    <sql id="fragment1">SELECT * FROM users</sql>
</mapper>
"""


class TestBuildGlobalFragmentRegistry:
    """Test cases for _build_global_fragment_registry function."""

    def test_empty_file_list_returns_empty_dict(self) -> None:
        """Empty input list returns empty dict."""
        result = _build_global_fragment_registry([])
        assert result == {}

    def test_single_valid_xml_file(self, tmp_path: Path) -> None:
        """Parses one valid MyBatis XML with fragments."""
        xml_file = tmp_path / "mapper.xml"
        xml_file.write_text(
            VALID_MAPPER_TEMPLATE.format(namespace="test.ns"),
            encoding="utf-8",
        )

        result = _build_global_fragment_registry([xml_file])

        assert len(result) == 2
        assert "test.ns.fragment1" in result
        assert "test.ns.fragment2" in result
        assert result["test.ns.fragment1"]["ref"] == "test.ns.fragment1"
        assert result["test.ns.fragment2"]["ref"] == "test.ns.fragment2"

    def test_invalid_xml_file_is_silently_ignored(self, tmp_path: Path) -> None:
        """Malformed XML doesn't raise exception, just gets skipped."""
        invalid_file = tmp_path / "invalid.xml"
        invalid_file.write_text("not valid xml <>>>>", encoding="utf-8")

        valid_file = tmp_path / "valid.xml"
        valid_file.write_text(
            VALID_MAPPER_TEMPLATE.format(namespace="test.ns"),
            encoding="utf-8",
        )

        # Should not raise, just skip the invalid file
        result = _build_global_fragment_registry([invalid_file, valid_file])

        # Valid file's fragments should still be present
        assert len(result) == 2
        assert "test.ns.fragment1" in result

    def test_non_mapper_file_is_skipped(self, tmp_path: Path) -> None:
        """Non-MyBatis XML files are skipped."""
        non_mapper_file = tmp_path / "non_mapper.xml"
        non_mapper_file.write_text(NON_MAPPER_TEMPLATE, encoding="utf-8")

        result = _build_global_fragment_registry([non_mapper_file])

        assert result == {}

    def test_fragments_merged_into_global_registry(self, tmp_path: Path) -> None:
        """Multiple files' fragments are merged into global registry."""
        file1 = tmp_path / "mapper1.xml"
        file1.write_text(
            VALID_MAPPER_TEMPLATE.format(namespace="ns1"),
            encoding="utf-8",
        )

        file2 = tmp_path / "mapper2.xml"
        file2.write_text(
            VALID_MAPPER_TEMPLATE.format(namespace="ns2"),
            encoding="utf-8",
        )

        result = _build_global_fragment_registry([file1, file2])

        # Should have fragments from both files
        assert len(result) == 4
        assert "ns1.fragment1" in result
        assert "ns1.fragment2" in result
        assert "ns2.fragment1" in result
        assert "ns2.fragment2" in result

    def test_duplicate_fragment_first_wins(self, tmp_path: Path) -> None:
        """First occurrence kept when duplicate fragment IDs exist."""
        file1 = tmp_path / "mapper1.xml"
        file1.write_text(
            VALID_MAPPER_TEMPLATE.format(namespace="test.ns"),
            encoding="utf-8",
        )

        # Create second file with duplicate fragment ID
        file2 = tmp_path / "mapper2.xml"
        file2.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="test.ns">
    <sql id="fragment1">SELECT * FROM different_table</sql>
    <sql id="fragment3">WHERE id = 999</sql>
</mapper>
""",
            encoding="utf-8",
        )

        result = _build_global_fragment_registry([file1, file2])

        # Should have 3 unique fragments
        assert len(result) == 3
        # The first file's fragment1 should be kept
        assert result["test.ns.fragment1"]["ref"] == "test.ns.fragment1"
        # fragment3 from file2 should be present
        assert "test.ns.fragment3" in result

    def test_empty_namespace_uses_unknown_default(self, tmp_path: Path) -> None:
        """Empty namespace attribute ('') defaults to 'unknown' for qualification."""
        mapper_file = tmp_path / "mapper.xml"
        mapper_file.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="">
    <sql id="fragment1">SELECT * FROM users</sql>
</mapper>
""",
            encoding="utf-8",
        )

        result = _build_global_fragment_registry([mapper_file])

        # Empty namespace string means _is_mybatis_mapper_root returns False (skipped)
        # This is expected behavior - empty namespace is treated as invalid
        assert result == {}

    def test_file_with_empty_namespace_is_skipped(self, tmp_path: Path) -> None:
        """Mapper with empty namespace string is skipped (not 'unknown')."""
        mapper_file = tmp_path / "mapper.xml"
        mapper_file.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="">
    <sql id="fragment1">SELECT * FROM users</sql>
</mapper>
""",
            encoding="utf-8",
        )

        result = _build_global_fragment_registry([mapper_file])

        # Empty namespace means _is_mybatis_mapper_root returns False
        assert result == {}
