"""Unit tests for parser module - parse_mapper_file, extract_parameter_mappings, detect_dynamic_features."""

import tempfile
from pathlib import Path

import pytest
from sqlopt.stages.init.parser import (
    ParsedStatement,
    _replace_cdata,
    detect_dynamic_features,
    extract_parameter_mappings,
    parse_mapper_file,
)


class TestReplaceCdata:
    """Tests for _replace_cdata function."""

    def test_cdata_replaced(self):
        """Test CDATA sections are properly escaped."""
        input_xml = "<![CDATA[SELECT * FROM users WHERE id = #{id}]]>"
        result = _replace_cdata(input_xml)
        assert "<![CDATA[" not in result
        assert "]]>" not in result
        assert "SELECT * FROM users" in result

    def test_cdata_with_special_chars(self):
        """Test CDATA with special characters."""
        input_xml = "<![CDATA[a < b AND c > d]]>"
        result = _replace_cdata(input_xml)
        assert "&lt;" in result
        assert "&gt;" in result

    def test_no_cdata_unchanged(self):
        """Test text without CDATA is unchanged."""
        input_xml = "<select>SELECT * FROM users</select>"
        result = _replace_cdata(input_xml)
        assert result == input_xml

    def test_multiple_cdata_sections(self):
        """Test multiple CDATA sections."""
        input_xml = "<![CDATA[first]]>middle<![CDATA[second]]>"
        result = _replace_cdata(input_xml)
        assert "<![CDATA[" not in result
        assert "first" in result
        assert "second" in result


class TestExtractParameterMappings:
    """Tests for extract_parameter_mappings function."""

    def test_simple_parameter(self):
        """Test extracting simple parameter."""
        from xml.etree import ElementTree as ET

        elem = ET.fromstring("<select>SELECT * FROM users WHERE id = #{id}</select>")
        result = extract_parameter_mappings(elem)
        assert len(result) == 1
        assert result[0]["name"] == "id"
        assert result[0]["jdbcType"] == "VARCHAR"

    def test_parameter_with_jdbc_type(self):
        """Test extracting parameter with explicit JDBC type."""
        from xml.etree import ElementTree as ET

        elem = ET.fromstring("<select>SELECT * FROM users WHERE id = #{id:INTEGER}</select>")
        result = extract_parameter_mappings(elem)
        assert len(result) == 1
        assert result[0]["name"] == "id"
        assert result[0]["jdbcType"] == "INTEGER"

    def test_multiple_parameters(self):
        """Test extracting multiple parameters."""
        from xml.etree import ElementTree as ET

        elem = ET.fromstring(
            "<select>SELECT * FROM users WHERE id = #{id} AND name = #{name}</select>"
        )
        result = extract_parameter_mappings(elem)
        assert len(result) == 2
        names = {r["name"] for r in result}
        assert names == {"id", "name"}

    def test_duplicate_parameters(self):
        """Test that duplicate parameters are deduplicated."""
        from xml.etree import ElementTree as ET

        elem = ET.fromstring(
            "<select>SELECT * FROM users WHERE id = #{id} AND ref = #{id}</select>"
        )
        result = extract_parameter_mappings(elem)
        assert len(result) == 1
        assert result[0]["name"] == "id"

    def test_no_parameters(self):
        """Test text with no parameters."""
        from xml.etree import ElementTree as ET

        elem = ET.fromstring("<select>SELECT * FROM users</select>")
        result = extract_parameter_mappings(elem)
        assert result == []


class TestDetectDynamicFeatures:
    """Tests for detect_dynamic_features function."""

    def test_detect_if_tag(self):
        """Test detecting if tag."""
        from xml.etree import ElementTree as ET

        elem = ET.fromstring("<select><if test='name != null'>AND name = #{name}</if></select>")
        result = detect_dynamic_features(elem)
        assert "IF" in result

    def test_detect_multiple_tags(self):
        """Test detecting multiple dynamic tags."""
        from xml.etree import ElementTree as ET

        elem = ET.fromstring(
            "<select><if test='name != null'>AND name = #{name}</if><where>1=1</where></select>"
        )
        result = detect_dynamic_features(elem)
        assert "IF" in result
        assert "WHERE" in result

    def test_detect_choose_when(self):
        """Test detecting choose/when tags."""
        from xml.etree import ElementTree as ET

        elem = ET.fromstring(
            "<select><choose><when test='a'>a</when><otherwise>b</otherwise></choose></select>"
        )
        result = detect_dynamic_features(elem)
        assert "CHOOSE" in result
        assert "WHEN" in result
        assert "OTHERWISE" in result

    def test_no_dynamic_tags(self):
        """Test with no dynamic tags."""
        from xml.etree import ElementTree as ET

        elem = ET.fromstring("<select>SELECT * FROM users</select>")
        result = detect_dynamic_features(elem)
        assert result == []

    def test_nested_dynamic_tags(self):
        """Test detecting dynamic tags in nested elements."""
        from xml.etree import ElementTree as ET

        elem = ET.fromstring("<select><if test='a'><if test='b'>nested</if></if></select>")
        result = detect_dynamic_features(elem)
        assert "IF" in result
        assert len(result) == 1


class TestParseMapperFile:
    """Tests for parse_mapper_file function."""

    def test_parse_simple_select(self):
        """Test parsing simple select statement."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <select id="findAll" resultType="User">
        SELECT * FROM users
    </select>
</mapper>"""
            )
            xml_path = Path(f.name)

        try:
            statements = parse_mapper_file(xml_path)
            assert len(statements) == 1
            stmt = statements[0]
            assert stmt.statement_id == "findAll"
            assert stmt.statement_type == "SELECT"
            assert stmt.namespace == "com.test.UserMapper"
            assert stmt.sql_key == "com.test.UserMapper.findAll"
        finally:
            xml_path.unlink()

    def test_parse_multiple_statements(self):
        """Test parsing multiple statements."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <select id="findAll">SELECT * FROM users</select>
    <insert id="insertUser">INSERT INTO users VALUES (#{id}, #{name})</insert>
    <update id="updateUser">UPDATE users SET name = #{name} WHERE id = #{id}</update>
    <delete id="deleteUser">DELETE FROM users WHERE id = #{id}</delete>
</mapper>"""
            )
            xml_path = Path(f.name)

        try:
            statements = parse_mapper_file(xml_path)
            assert len(statements) == 4
            types = {s.statement_type for s in statements}
            assert types == {"SELECT", "INSERT", "UPDATE", "DELETE"}
        finally:
            xml_path.unlink()

    def test_parse_without_namespace(self):
        """Test parsing statements without namespace."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper>
    <select id="findAll">SELECT * FROM users</select>
</mapper>"""
            )
            xml_path = Path(f.name)

        try:
            statements = parse_mapper_file(xml_path)
            assert len(statements) == 1
            assert statements[0].sql_key == "findAll"
            assert statements[0].namespace == ""
        finally:
            xml_path.unlink()

    def test_parse_cdata_section(self):
        """Test parsing statements with CDATA sections."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="test">
    <select id="findByCondition">
        <![CDATA[SELECT * FROM users WHERE id > #{minId}]]>
    </select>
</mapper>"""
            )
            xml_path = Path(f.name)

        try:
            statements = parse_mapper_file(xml_path)
            assert len(statements) == 1
            assert "SELECT * FROM users" in statements[0].xml_content
        finally:
            xml_path.unlink()

    def test_parse_with_parameters(self):
        """Test parsing statements with parameter mappings."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="test">
    <select id="findById">SELECT * FROM users WHERE id = #{id:INTEGER}</select>
</mapper>"""
            )
            xml_path = Path(f.name)

        try:
            statements = parse_mapper_file(xml_path)
            assert len(statements) == 1
            mappings = statements[0].parameter_mappings
            assert len(mappings) == 1
            assert mappings[0]["name"] == "id"
            assert mappings[0]["jdbcType"] == "INTEGER"
        finally:
            xml_path.unlink()

    def test_parse_with_dynamic_features(self):
        """Test parsing statements with dynamic features."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="test">
    <select id="findByCondition">
        SELECT * FROM users
        <where>
            <if test="name != null">AND name = #{name}</if>
            <if test="id != null">AND id = #{id}</if>
        </where>
    </select>
</mapper>"""
            )
            xml_path = Path(f.name)

        try:
            statements = parse_mapper_file(xml_path)
            assert len(statements) == 1
            features = statements[0].dynamic_features
            assert "IF" in features
            assert "WHERE" in features
        finally:
            xml_path.unlink()

    def test_parse_invalid_xml(self):
        """Test parsing invalid XML returns empty list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write("not valid xml <><><>")
            xml_path = Path(f.name)

        try:
            statements = parse_mapper_file(xml_path)
            assert statements == []
        finally:
            xml_path.unlink()

    def test_parse_nonexistent_file(self):
        """Test parsing nonexistent file returns empty list."""
        statements = parse_mapper_file(Path("/nonexistent/file.xml"))
        assert statements == []
