"""Tests for InitStage behavior under partial mapper failures."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlopt.common.config import SQLOptConfig
from sqlopt.stages.init.parser import ParsedStatement
from sqlopt.stages.init.stage import InitStage

if TYPE_CHECKING:
    from pathlib import Path


def test_init_stage_skips_unparseable_mapper_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    good_mapper = tmp_path / "GoodMapper.xml"
    bad_mapper = tmp_path / "BadMapper.xml"

    def fake_find_mapper_files(_project_root, _globs):
        return [good_mapper, bad_mapper]

    def fake_parse_mapper_file(xml_path):
        if xml_path == bad_mapper:
            raise RuntimeError("invalid mapper xml")
        return (
            [
                ParsedStatement(
                    sql_key="com.test.GoodMapper.findAll",
                    namespace="com.test.GoodMapper",
                    statement_id="findAll",
                    statement_type="SELECT",
                    xml_path=str(good_mapper),
                    xml_content="<select id='findAll'>SELECT * FROM users</select>",
                    parameter_mappings=[],
                    dynamic_features=[],
                )
            ],
            [],
        )

    monkeypatch.setattr("sqlopt.stages.init.stage.find_mapper_files", fake_find_mapper_files)
    monkeypatch.setattr("sqlopt.stages.init.stage.parse_mapper_file", fake_parse_mapper_file)

    config = SQLOptConfig(project_root_path=str(tmp_path), statement_types=["SELECT"])
    stage = InitStage(config=config, run_id="init-skip-bad-file")

    output = stage.run()

    assert len(output.sql_units) == 1
    assert output.sql_units[0].sql_id == "findAll"
