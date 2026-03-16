"""Tests for commands/branch.py module."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.commands import branch


class BranchCommandTest(unittest.TestCase):
    """Test branch command functionality."""

    def test_parse_mapper_xml_basic(self) -> None:
        """Test parsing a basic mapper XML file."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_branch_") as td:
            mapper_file = Path(td) / "test_mapper.xml"
            mapper_file.write_text(
                """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="test">
  <select id="findById">SELECT * FROM users WHERE id = #{id}</select>
  <select id="findActive">
    SELECT * FROM users
    <if test="status != null">WHERE status = #{status}</if>
  </select>
</mapper>
""",
                encoding="utf-8",
            )
            result = branch.parse_mapper_xml(str(mapper_file))
            self.assertIn("findById", result)
            self.assertIn("findActive", result)
            self.assertIn("<if", result["findActive"]["template_sql"])

    def test_parse_mapper_xml_with_foreach(self) -> None:
        """Test parsing mapper XML with foreach."""
        with tempfile.TemporaryDirectory(prefix="sqlopt_branch_") as td:
            mapper_file = Path(td) / "foreach_mapper.xml"
            mapper_file.write_text(
                """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="test">
  <select id="findByIds">
    SELECT * FROM users WHERE id IN
    <foreach collection="ids" item="id" open="(" separator="," close=")">
      #{id}
    </foreach>
  </select>
</mapper>
""",
                encoding="utf-8",
            )
            result = branch.parse_mapper_xml(str(mapper_file))
            self.assertIn("findByIds", result)
            self.assertIn("foreach", result["findByIds"]["template_sql"].lower())


if __name__ == "__main__":
    unittest.main()
