import json
from pathlib import Path

import pytest
from sqlopt.common.config import SQLOptConfig
from sqlopt.stages.parse.stage import ParseStage
from sqlopt.contracts.parse import ParseOutput


class TestParseStage:
    """Tests for ParseStage with config integration."""

    def test_parse_stage_with_config(self):
        """ParseStage accepts config and uses it."""
        config = SQLOptConfig(parse_strategy="ladder", parse_max_branches=50)
        stage = ParseStage(run_id="test", config=config)
        assert stage.config == config

    def test_parse_stage_without_config(self):
        """ParseStage works without config (uses defaults)."""
        stage = ParseStage(run_id="test")
        assert stage.config is None

    def test_parse_stage_run_returns_parse_output(self):
        """run() returns ParseOutput with correct structure."""
        config = SQLOptConfig(parse_strategy="ladder", parse_max_branches=50)
        stage = ParseStage(run_id="test", config=config)
        output = stage.run()
        assert isinstance(output, ParseOutput)
        assert hasattr(output, "sql_units_with_branches")

    def test_parse_stage_stub_data_without_run_id(self):
        """Without run_id, returns stub data."""
        stage = ParseStage()
        output = stage.run()
        assert isinstance(output, ParseOutput)
        assert len(output.sql_units_with_branches) >= 1

    def test_parse_stage_loads_fragments_and_preserves_branch_metadata(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        """ParseStage should resolve includes and propagate active/risk metadata."""
        monkeypatch.chdir(tmp_path)
        run_dir = tmp_path / "runs" / "parse-stage-test" / "init"
        run_dir.mkdir(parents=True)

        mapper = tmp_path / "src" / "main" / "resources" / "mapper" / "UserMapper.xml"
        mapper.parent.mkdir(parents=True)
        mapper.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <sql id="statusCondition">
        <if test="status != null">AND status = #{status}</if>
    </sql>
</mapper>""",
            encoding="utf-8",
        )

        statement_sql = """<select id="findByName"><bind name="namePattern" value="'%' + name + '%'"/>SELECT * FROM users <where><include refid="statusCondition"/><if test="name != null">AND name LIKE #{namePattern}</if></where></select>"""
        (run_dir / "sql_units.json").write_text(
            json.dumps(
                [
                    {
                        "id": "com.test.UserMapper.findByName",
                        "mapper_file": "UserMapper.xml",
                        "sql_id": "findByName",
                        "sql_text": statement_sql,
                        "statement_type": "SELECT",
                    }
                ]
            ),
            encoding="utf-8",
        )
        (run_dir / "sql_fragments.json").write_text(
            json.dumps(
                [
                    {
                        "fragmentId": "statusCondition",
                        "xmlPath": str(mapper),
                        "startLine": 1,
                        "endLine": 4,
                        "xmlContent": '<sql id="statusCondition"><if test="status != null">AND status = #{status}</if></sql>',
                    }
                ]
            ),
            encoding="utf-8",
        )
        (run_dir / "table_schemas.json").write_text(
            json.dumps(
                {
                    "users": {
                        "columns": [],
                        "indexes": [{"name": "idx_status", "columns": ["status"]}],
                        "statistics": {"rowCount": 1200000},
                    }
                }
            ),
            encoding="utf-8",
        )

        config = SQLOptConfig(parse_strategy="all_combinations", parse_max_branches=10)
        stage = ParseStage(run_id="parse-stage-test", use_mock=False, config=config)

        output = stage.run()

        assert len(output.sql_units_with_branches) == 1
        branches = output.sql_units_with_branches[0].branches
        assert any("status = #{status}" in branch.expanded_sql for branch in branches)
        assert any(branch.active_conditions for branch in branches)
        assert any("prefix_wildcard" in branch.risk_flags for branch in branches)
        assert any(branch.risk_score is not None for branch in branches)
        assert any(branch.score_reasons for branch in branches)
