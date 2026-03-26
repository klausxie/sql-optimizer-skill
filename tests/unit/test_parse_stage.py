import json
from pathlib import Path

import pytest
from sqlopt.common.config import SQLOptConfig
from sqlopt.contracts.parse import ParseOutput
from sqlopt.stages.parse.stage import ParseStage


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
                        "fragment_id": "statusCondition",
                        "xml_path": str(mapper),
                        "start_line": 1,
                        "end_line": 4,
                        "xml_content": '<sql id="statusCondition"><if test="status != null">AND status = #{status}</if></sql>',
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
        (run_dir / "field_distributions.json").write_text(
            json.dumps(
                [
                    {
                        "table_name": "users",
                        "column_name": "status",
                        "total_count": 1200000,
                        "distinct_count": 2,
                        "null_count": 0,
                        "top_values": [{"value": "ACTIVE", "count": 1100000}],
                        "min_value": "ACTIVE",
                        "max_value": "INACTIVE",
                    }
                ]
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
        assert any("field_low_card:status" in branch.score_reasons for branch in branches)
        assert any("field_skewed:status" in branch.score_reasons for branch in branches)

    def test_parse_stage_writes_empty_outputs_for_empty_init(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        """ParseStage should persist empty outputs instead of falling back to stub in later stages."""
        monkeypatch.chdir(tmp_path)
        run_dir = tmp_path / "runs" / "parse-empty-test" / "init"
        run_dir.mkdir(parents=True)
        (run_dir / "sql_units.json").write_text("[]", encoding="utf-8")

        stage = ParseStage(run_id="parse-empty-test", use_mock=False)
        output = stage.run()

        assert output.sql_units_with_branches == []
        compat_file = tmp_path / "runs" / "parse-empty-test" / "parse" / "sql_units_with_branches.json"
        index_file = tmp_path / "runs" / "parse-empty-test" / "parse" / "units" / "_index.json"
        assert compat_file.exists()
        assert index_file.exists()
        assert ParseOutput.from_json(compat_file.read_text(encoding="utf-8")).sql_units_with_branches == []
        assert json.loads(index_file.read_text(encoding="utf-8")) == []

    def test_parse_stage_isolates_unit_failures_in_concurrent_mode(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """A single SQL unit failure should not abort the whole parse stage."""
        monkeypatch.chdir(tmp_path)
        run_dir = tmp_path / "runs" / "parse-concurrent-failure" / "init"
        run_dir.mkdir(parents=True)
        (run_dir / "sql_units.json").write_text(
            json.dumps(
                [
                    {
                        "id": "com.test.UserMapper.ok",
                        "mapper_file": "UserMapper.xml",
                        "sql_id": "ok",
                        "sql_text": "<select id='ok'>SELECT * FROM users</select>",
                        "statement_type": "SELECT",
                    },
                    {
                        "id": "com.test.UserMapper.bad",
                        "mapper_file": "UserMapper.xml",
                        "sql_id": "bad",
                        "sql_text": "<select id='bad'>SELECT * FROM broken</select>",
                        "statement_type": "SELECT",
                    },
                ]
            ),
            encoding="utf-8",
        )
        (run_dir / "sql_fragments.json").write_text("[]", encoding="utf-8")
        (run_dir / "table_schemas.json").write_text("{}", encoding="utf-8")
        (run_dir / "field_distributions.json").write_text("[]", encoding="utf-8")

        original_expand = __import__(
            "sqlopt.stages.parse.branch_expander",
            fromlist=["BranchExpander"],
        ).BranchExpander.expand

        def failing_expand(self, sql_text, default_namespace=None):
            if "broken" in sql_text:
                raise RuntimeError("simulated branch explosion")
            return original_expand(self, sql_text, default_namespace)

        monkeypatch.setattr("sqlopt.stages.parse.branch_expander.BranchExpander.expand", failing_expand)

        config = SQLOptConfig()
        config.concurrency.enabled = True
        config.concurrency.max_workers = 2
        config.concurrency.batch_size = 2
        stage = ParseStage(run_id="parse-concurrent-failure", use_mock=False, config=config)

        output = stage.run()

        assert len(output.sql_units_with_branches) == 2
        bad_unit = next(unit for unit in output.sql_units_with_branches if unit.sql_unit_id.endswith(".bad"))
        assert len(bad_unit.branches) == 1
        assert bad_unit.branches[0].is_valid is False
        assert bad_unit.branches[0].branch_type == "error"
        assert "parse_error" in bad_unit.branches[0].risk_flags
