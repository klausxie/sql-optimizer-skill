"""Unit tests for fragment-related functions in init stage."""

import tempfile
from pathlib import Path

import pytest
from sqlopt.stages.init.parser import ParsedFragment, parse_mapper_file
from sqlopt.stages.init.stage import _parsed_to_sqlfragment


class TestParsedToSqlfragment:
    """Tests for _parsed_to_sqlfragment function."""

    def test_basic_fragment_conversion(self):
        """Test basic conversion of ParsedFragment to SQLFragment."""
        frag = ParsedFragment(
            fragment_id="baseColumns",
            xml_path="/path/to/mapper.xml",
            start_line=5,
            end_line=10,
            xml_content="<sql id='baseColumns'>SELECT id, name FROM users</sql>",
            xpath="/mapper/sql[@id='baseColumns']",
        )

        result = _parsed_to_sqlfragment(frag)

        assert result.fragmentId == "baseColumns"
        assert result.xmlPath == "/path/to/mapper.xml"
        assert result.startLine == 5
        assert result.endLine == 10
        assert "SELECT id, name FROM users" in result.xmlContent

    def test_fragment_with_no_id(self):
        """Test fragment with different ID."""
        frag = ParsedFragment(
            fragment_id="myFragment",
            xml_path="/path/to/OtherMapper.xml",
            start_line=1,
            end_line=3,
            xml_content="<sql id='myFragment'>SELECT *</sql>",
            xpath="/mapper/sql[@id='myFragment']",
        )

        result = _parsed_to_sqlfragment(frag)

        assert result.fragmentId == "myFragment"
        assert result.xmlPath == "/path/to/OtherMapper.xml"

    def test_fragment_preserves_xml_content(self):
        """Test that XML content is preserved exactly."""
        xml_content = "<sql id='testFrag'><where>1=1</where></sql>"
        frag = ParsedFragment(
            fragment_id="testFrag",
            xml_path="/path/to/test.xml",
            start_line=1,
            end_line=1,
            xml_content=xml_content,
            xpath="/mapper/sql[@id='testFrag']",
        )

        result = _parsed_to_sqlfragment(frag)

        assert result.xmlContent == xml_content


class TestFragmentExtractionFromXml:
    """Tests for fragment extraction from XML files via parse_mapper_file."""

    def test_extract_single_fragment(self):
        """Test extracting a single SQL fragment from XML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <sql id="baseColumns">
        SELECT id, name, email FROM users
    </sql>
</mapper>"""
            )
            xml_path = Path(f.name)

        try:
            _, fragments = parse_mapper_file(xml_path)
            assert len(fragments) == 1
            frag = fragments[0]
            assert frag.fragment_id == "baseColumns"
            assert "SELECT id, name, email FROM users" in frag.xml_content
            assert frag.start_line > 0
        finally:
            xml_path.unlink()

    def test_extract_multiple_fragments(self):
        """Test extracting multiple SQL fragments from XML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <sql id="baseColumns">
        SELECT id, name FROM users
    </sql>
    <sql id="insertFields">
        id, name, created_at
    </sql>
    <sql id="whereClause">
        WHERE active = true
    </sql>
</mapper>"""
            )
            xml_path = Path(f.name)

        try:
            _, fragments = parse_mapper_file(xml_path)
            assert len(fragments) == 3
            fragment_ids = {f.fragment_id for f in fragments}
            assert fragment_ids == {"baseColumns", "insertFields", "whereClause"}
        finally:
            xml_path.unlink()

    def test_fragment_xpath_generation(self):
        """Test that XPath is correctly generated for fragments."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <sql id="baseColumns">SELECT id FROM users</sql>
</mapper>"""
            )
            xml_path = Path(f.name)

        try:
            _, fragments = parse_mapper_file(xml_path)
            assert len(fragments) == 1
            frag = fragments[0]
            assert "@id='baseColumns']" in frag.xpath
            assert "/mapper/sql[" in frag.xpath
        finally:
            xml_path.unlink()

    def test_fragment_without_id_ignored(self):
        """Test that fragments without id attribute are ignored."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper>
    <sql>SELECT id FROM users</sql>
    <sql id="validFragment">SELECT name FROM users</sql>
</mapper>"""
            )
            xml_path = Path(f.name)

        try:
            _, fragments = parse_mapper_file(xml_path)
            assert len(fragments) == 1
            assert fragments[0].fragment_id == "validFragment"
        finally:
            xml_path.unlink()

    def test_fragment_with_namespace_in_xpath(self):
        """Test that mapper namespace affects fragment XPath."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <sql id="baseColumns">SELECT id FROM users</sql>
</mapper>"""
            )
            xml_path = Path(f.name)

        try:
            _, fragments = parse_mapper_file(xml_path)
            assert len(fragments) == 1
            # The _build_xpath uses root_tag which is "mapper", so namespace is not in xpath for sql elements
            assert "/mapper/sql[@id='baseColumns']" in fragments[0].xpath
        finally:
            xml_path.unlink()

    def test_fragment_line_numbers(self):
        """Test that fragment line numbers are correctly tracked."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="test">
    <sql id="frag">
        line 1
        line 2
        line 3
    </sql>
</mapper>"""
            )
            xml_path = Path(f.name)

        try:
            _, fragments = parse_mapper_file(xml_path)
            assert len(fragments) == 1
            # Line numbers should be tracked (start_line should be > 1 due to XML header)
            assert fragments[0].start_line >= 1
            assert fragments[0].end_line >= fragments[0].start_line
        finally:
            xml_path.unlink()


class TestSqlFragmentsInInitOutput:
    """Tests for SQL fragments being correctly added to InitOutput."""

    def test_fragment_added_to_output(self):
        """Test that fragments are properly converted and can be added to InitOutput."""
        from sqlopt.contracts.init import InitOutput, SQLFragment

        frag = ParsedFragment(
            fragment_id="testFrag",
            xml_path="/path/to/mapper.xml",
            start_line=1,
            end_line=5,
            xml_content="<sql id='testFrag'>SELECT *</sql>",
            xpath="/mapper/sql[@id='testFrag']",
        )

        sql_fragment = _parsed_to_sqlfragment(frag)

        # Verify it can be used in InitOutput
        output = InitOutput(
            sql_units=[],
            run_id="test-run",
            sql_fragments=[sql_fragment],
        )

        assert len(output.sql_fragments) == 1
        assert output.sql_fragments[0].fragmentId == "testFrag"

    def test_multiple_fragments_in_output(self):
        """Test that multiple fragments can be added to InitOutput."""
        from sqlopt.contracts.init import InitOutput

        fragments = []
        for i in range(3):
            frag = ParsedFragment(
                fragment_id=f"frag{i}",
                xml_path=f"/path/to/mapper{i}.xml",
                start_line=i * 5,
                end_line=i * 5 + 3,
                xml_content=f"<sql id='frag{i}'>SELECT {i}</sql>",
                xpath=f"/mapper/sql[@id='frag{i}']",
            )
            fragments.append(_parsed_to_sqlfragment(frag))

        output = InitOutput(
            sql_units=[],
            run_id="test-run",
            sql_fragments=fragments,
        )

        assert len(output.sql_fragments) == 3
        assert {f.fragmentId for f in output.sql_fragments} == {"frag0", "frag1", "frag2"}
