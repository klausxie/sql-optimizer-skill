"""Unit tests for XML mapping and XPath generation in init stage."""

import tempfile
from pathlib import Path

import pytest
from sqlopt.contracts.init import (
    FileMapping,
    FragmentMapping,
    InitOutput,
    StatementMapping,
    XMLMapping,
)
from sqlopt.stages.init.parser import ParsedStatement, parse_mapper_file
from sqlopt.stages.init.stage import _build_statement_xpath


class TestBuildStatementXpath:
    """Tests for _build_statement_xpath function."""

    def test_select_statement_xpath(self):
        """Test XPath generation for SELECT statement."""
        stmt = ParsedStatement(
            sql_key="com.test.UserMapper.findAll",
            namespace="com.test.UserMapper",
            statement_id="findAll",
            statement_type="SELECT",
            xml_path="/path/to/UserMapper.xml",
            xml_content="<select id='findAll'>SELECT * FROM users</select>",
            parameter_mappings=[],
            dynamic_features=[],
        )

        result = _build_statement_xpath(stmt)

        assert "/mapper/" in result
        assert "findAll" in result
        assert "select" in result

    def test_xpath_without_namespace(self):
        """Test XPath generation for statement without namespace."""
        stmt = ParsedStatement(
            sql_key="findAll",
            namespace="",
            statement_id="findAll",
            statement_type="SELECT",
            xml_path="/path/to/mapper.xml",
            xml_content="<select id='findAll'>SELECT * FROM users</select>",
            parameter_mappings=[],
            dynamic_features=[],
        )

        result = _build_statement_xpath(stmt)

        assert result == "/mapper/select[@id='findAll']"

    def test_xpath_with_namespace(self):
        """Test XPath generation with namespace uses namespace prefix."""
        stmt = ParsedStatement(
            sql_key="com.test.UserMapper.findById",
            namespace="com.test.UserMapper",
            statement_id="findById",
            statement_type="SELECT",
            xml_path="/path/to/UserMapper.xml",
            xml_content="<select id='findById'>SELECT * FROM users</select>",
            parameter_mappings=[],
            dynamic_features=[],
        )

        result = _build_statement_xpath(stmt)

        assert "com.test.UserMapper" in result
        assert "findById" in result

    def test_insert_statement_xpath(self):
        """Test XPath generation for INSERT statement."""
        stmt = ParsedStatement(
            sql_key="insertUser",
            namespace="",
            statement_id="insertUser",
            statement_type="INSERT",
            xml_path="/path/to/mapper.xml",
            xml_content="<insert id='insertUser'>INSERT INTO users</insert>",
            parameter_mappings=[],
            dynamic_features=[],
        )

        result = _build_statement_xpath(stmt)

        assert result == "/mapper/insert[@id='insertUser']"

    def test_update_statement_xpath(self):
        """Test XPath generation for UPDATE statement."""
        stmt = ParsedStatement(
            sql_key="updateUser",
            namespace="",
            statement_id="updateUser",
            statement_type="UPDATE",
            xml_path="/path/to/mapper.xml",
            xml_content="<update id='updateUser'>UPDATE users</update>",
            parameter_mappings=[],
            dynamic_features=[],
        )

        result = _build_statement_xpath(stmt)

        assert result == "/mapper/update[@id='updateUser']"


class TestXMLMappingStructure:
    """Tests for XMLMapping and related structures."""

    def test_file_mapping_creation(self):
        """Test creating a FileMapping."""
        file_mapping = FileMapping(xml_path="/path/to/mapper.xml")

        assert file_mapping.xml_path == "/path/to/mapper.xml"
        assert file_mapping.fragments == []
        assert file_mapping.statements == []

    def test_statement_mapping_creation(self):
        """Test creating a StatementMapping."""
        stmt_mapping = StatementMapping(
            sql_key="com.test.UserMapper.findAll",
            statement_id="findAll",
            xpath="/mapper/select[@id='findAll']",
            tag_name="select",
            id_attr="findAll",
            original_content="<select id='findAll'>SELECT *</select>",
        )

        assert stmt_mapping.sql_key == "com.test.UserMapper.findAll"
        assert stmt_mapping.tag_name == "select"
        assert "@id='findAll']" in stmt_mapping.xpath

    def test_fragment_mapping_creation(self):
        """Test creating a FragmentMapping."""
        frag_mapping = FragmentMapping(
            fragment_id="baseColumns",
            sql_key=None,
            xpath="/mapper/sql[@id='baseColumns']",
            tag_name="sql",
            id_attr="baseColumns",
            original_content="<sql id='baseColumns'>SELECT id, name</sql>",
        )

        assert frag_mapping.fragment_id == "baseColumns"
        assert frag_mapping.tag_name == "sql"
        assert frag_mapping.sql_key is None

    def test_xml_mapping_with_files(self):
        """Test creating XMLMapping with multiple files."""
        file1 = FileMapping(xml_path="/path/to/UserMapper.xml")
        file1.statements.append(
            StatementMapping(
                sql_key="findAll",
                statement_id="findAll",
                xpath="/mapper/select[@id='findAll']",
                tag_name="select",
                id_attr="findAll",
                original_content="<select id='findAll'/>",
            )
        )

        file2 = FileMapping(xml_path="/path/to/OrderMapper.xml")
        file2.fragments.append(
            FragmentMapping(
                fragment_id="baseColumns",
                sql_key=None,
                xpath="/mapper/sql[@id='baseColumns']",
                tag_name="sql",
                id_attr="baseColumns",
                original_content="<sql id='baseColumns'/>",
            )
        )

        xml_mapping = XMLMapping(files=[file1, file2])

        assert len(xml_mapping.files) == 2
        assert xml_mapping.files[0].xml_path == "/path/to/UserMapper.xml"
        assert xml_mapping.files[1].xml_path == "/path/to/OrderMapper.xml"
        assert len(xml_mapping.files[0].statements) == 1
        assert len(xml_mapping.files[1].fragments) == 1


class TestFileGroupingLogic:
    """Tests for file grouping logic in InitOutput."""

    def test_statements_grouped_by_file(self):
        """Test that statements are correctly grouped by file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <select id="findAll">SELECT * FROM users</select>
    <select id="findById">SELECT * FROM users WHERE id = #{id}</select>
    <insert id="insertUser">INSERT INTO users (name) VALUES (#{name})</insert>
</mapper>"""
            )
            xml_path = Path(f.name)

        try:
            statements, _ = parse_mapper_file(xml_path)

            # Group by file (in this case, all from same file)
            file_to_statements: dict[str, list] = {}
            for stmt in statements:
                if stmt.xml_path not in file_to_statements:
                    file_to_statements[stmt.xml_path] = []
                file_to_statements[stmt.xml_path].append(stmt)

            assert len(file_to_statements) == 1
            file_path = next(iter(file_to_statements.keys()))
            assert len(file_to_statements[file_path]) == 3
        finally:
            xml_path.unlink()

    def test_multiple_files_create_multiple_groups(self):
        """Test that multiple files create multiple groups."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f1:
            f1.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <select id="findAll">SELECT * FROM users</select>
</mapper>"""
            )
            xml_path1 = Path(f1.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f2:
            f2.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.OrderMapper">
    <select id="findAll">SELECT * FROM orders</select>
</mapper>"""
            )
            xml_path2 = Path(f2.name)

        try:
            statements1, _ = parse_mapper_file(xml_path1)
            statements2, _ = parse_mapper_file(xml_path2)

            all_statements = statements1 + statements2

            file_to_statements: dict[str, list] = {}
            for stmt in all_statements:
                if stmt.xml_path not in file_to_statements:
                    file_to_statements[stmt.xml_path] = []
                file_to_statements[stmt.xml_path].append(stmt)

            assert len(file_to_statements) == 2
        finally:
            xml_path1.unlink()
            xml_path2.unlink()

    def test_fragments_grouped_by_file(self):
        """Test that fragments are correctly grouped by file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <sql id="baseColumns">SELECT id, name, email</sql>
    <sql id="whereClause">WHERE active = true</sql>
</mapper>"""
            )
            xml_path = Path(f.name)

        try:
            _, fragments = parse_mapper_file(xml_path)

            file_to_fragments: dict[str, list] = {}
            for frag in fragments:
                if frag.xml_path not in file_to_fragments:
                    file_to_fragments[frag.xml_path] = []
                file_to_fragments[frag.xml_path].append(frag)

            assert len(file_to_fragments) == 1
            file_path = next(iter(file_to_fragments.keys()))
            assert len(file_to_fragments[file_path]) == 2
        finally:
            xml_path.unlink()


class TestInitOutputWithXmlMappings:
    """Tests for InitOutput with XML mappings."""

    def test_init_output_serialization(self):
        """Test that InitOutput with XMLMapping serializes correctly."""
        file_mapping = FileMapping(xml_path="/path/to/mapper.xml")
        file_mapping.statements.append(
            StatementMapping(
                sql_key="findAll",
                statement_id="findAll",
                xpath="/mapper/select[@id='findAll']",
                tag_name="select",
                id_attr="findAll",
                original_content="<select id='findAll'/>",
            )
        )

        xml_mapping = XMLMapping(files=[file_mapping])

        output = InitOutput(
            sql_units=[],
            run_id="test-run",
            xml_mappings=xml_mapping,
        )

        json_str = output.to_json()
        assert "test-run" in json_str
        assert "/path/to/mapper.xml" in json_str

    def test_init_output_with_mixed_content(self):
        """Test InitOutput with both statements and fragments."""
        from sqlopt.contracts.init import SQLFragment, SQLUnit

        file_mapping = FileMapping(xml_path="/path/to/mapper.xml")
        file_mapping.statements.append(
            StatementMapping(
                sql_key="findAll",
                statement_id="findAll",
                xpath="/mapper/select[@id='findAll']",
                tag_name="select",
                id_attr="findAll",
                original_content="<select id='findAll'/>",
            )
        )
        file_mapping.fragments.append(
            FragmentMapping(
                fragment_id="baseColumns",
                sql_key=None,
                xpath="/mapper/sql[@id='baseColumns']",
                tag_name="sql",
                id_attr="baseColumns",
                original_content="<sql id='baseColumns'/>",
            )
        )

        sql_unit = SQLUnit(
            id="findAll",
            mapper_file="mapper.xml",
            sql_id="findAll",
            sql_text="SELECT * FROM users",
            statement_type="SELECT",
        )

        sql_fragment = SQLFragment(
            fragment_id="baseColumns",
            xml_path="/path/to/mapper.xml",
            start_line=1,
            end_line=5,
            xml_content="<sql id='baseColumns'>SELECT id</sql>",
        )

        output = InitOutput(
            sql_units=[sql_unit],
            run_id="test-run",
            sql_fragments=[sql_fragment],
            xml_mappings=XMLMapping(files=[file_mapping]),
        )

        assert len(output.sql_units) == 1
        assert len(output.sql_fragments) == 1
        assert len(output.xml_mappings.files) == 1
        assert len(output.xml_mappings.files[0].statements) == 1
        assert len(output.xml_mappings.files[0].fragments) == 1
