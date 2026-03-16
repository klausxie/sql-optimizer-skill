"""Tests for commands/baseline.py module."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from sqlopt.commands import baseline


class BaselineCommandTest(unittest.TestCase):
    """Test baseline command functionality."""

    def test_parse_mapper_xml_basic(self) -> None:
        """Test parsing a basic mapper XML file."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_baseline_") as td:
            mapper_file = Path(td) / "test_mapper.xml"
            mapper_file.write_text(
                """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="test">
  <select id="findById">SELECT * FROM users WHERE id = #{id}</select>
  <update id="updateName">UPDATE users SET name = #{name} WHERE id = #{id}</update>
</mapper>
""",
                encoding="utf-8",
            )
            result = baseline.parse_mapper_xml(str(mapper_file))
            self.assertIn("findById", result)
            self.assertIn("updateName", result)
            self.assertEqual(result["findById"]["type"], "select")
            self.assertEqual(result["updateName"]["type"], "update")

    def test_parse_mapper_xml_with_namespace(self) -> None:
        """Test parsing a mapper XML file with namespace."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_baseline_") as td:
            mapper_file = Path(td) / "ns_mapper.xml"
            mapper_file.write_text(
                """<?xml version="1.0" encoding="UTF-8" ?>
<mapper xmlns="http://mybatis.org/schema/mybatis-3-mapper" namespace="com.example.User">
  <select id="findAll">SELECT * FROM users</select>
</mapper>
""",
                encoding="utf-8",
            )
            result = baseline.parse_mapper_xml(str(mapper_file))
            self.assertIn("findAll", result)


if __name__ == "__main__":
    unittest.main()
