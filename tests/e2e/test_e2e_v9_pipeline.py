from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from sqlopt.application.v9_stages import run_stage, STAGE_ORDER, build_stage_registry
from sqlopt.contracts import ContractValidator


_MIN_SQL_UNIT = {
    "sqlKey": "com.example.Demo.selectOne",
    "namespace": "com.example",
    "statementId": "selectOne",
    "statementType": "SELECT",
    "variantId": "v1",
    "xmlPath": "/tmp/Demo.xml",
    "sql": "SELECT 1 AS x",
    "templateSql": "SELECT 1 AS x",
    "parameterMappings": [],
    "paramExample": {},
    "locators": {},
    "dynamicTags": [],
    "riskFlags": [],
}


@pytest.fixture
def temp_run_dir():
    with tempfile.TemporaryDirectory(prefix="sqlopt_e2e_") as td:
        yield Path(td)


@pytest.fixture
def validator():
    return ContractValidator(Path(__file__).resolve().parents[3])


class DummyValidator:
    def validate_stage_input(self, _stage: str, _data: object) -> None:
        return None

    def validate_stage_output(self, _stage: str, _data: object) -> None:
        return None


class TestE2EV9PipelineInit:
    def test_init_stage_with_mocked_scanner(self, temp_run_dir, validator):
        with patch("sqlopt.application.v9_stages.init.Scanner") as mock_scanner_class:
            mock_result = Mock()
            mock_result.sql_units = [_MIN_SQL_UNIT]
            mock_scanner_class.return_value.scan.return_value = mock_result

            result = run_stage(
                "init",
                temp_run_dir,
                config={"project": {"root_path": str(temp_run_dir)}},
                validator=validator,
            )

        assert result["success"] is True
        assert result["sql_units_count"] == 1
        output_path = temp_run_dir / "init" / "sql_units.json"
        assert output_path.exists()
        units = json.loads(output_path.read_text())
        assert len(units) == 1
        assert units[0]["sqlKey"] == _MIN_SQL_UNIT["sqlKey"]


class TestE2EV9PipelineParse:
    def test_parse_stage_produces_branches(self, temp_run_dir, validator):
        init_dir = temp_run_dir / "init"
        init_dir.mkdir(parents=True)
        (init_dir / "sql_units.json").write_text(
            json.dumps([_MIN_SQL_UNIT], ensure_ascii=False, indent=2), encoding="utf-8"
        )

        result = run_stage(
            "parse",
            temp_run_dir,
            config={"project": {"root_path": str(temp_run_dir)}},
            validator=DummyValidator(),
        )

        assert result["success"] is True
        branches_path = temp_run_dir / "parse" / "sql_units_with_branches.json"
        assert branches_path.exists()
        units = json.loads(branches_path.read_text())
        assert len(units) == 1
        assert "branches" in units[0]


class TestE2EV9PipelineRecognition:
    def test_recognition_stage_with_mock(self, temp_run_dir, validator):
        init_dir = temp_run_dir / "init"
        init_dir.mkdir(parents=True)
        (init_dir / "sql_units.json").write_text(
            json.dumps([_MIN_SQL_UNIT], ensure_ascii=False, indent=2), encoding="utf-8"
        )

        parse_dir = temp_run_dir / "parse"
        parse_dir.mkdir(parents=True)
        parse_unit = dict(_MIN_SQL_UNIT)
        parse_unit["branches"] = [
            {"id": 1, "conditions": [], "sql": "SELECT 1", "type": "static"}
        ]
        parse_unit["branchCount"] = 1
        parse_unit["problemBranchCount"] = 0
        (parse_dir / "sql_units_with_branches.json").write_text(
            json.dumps([parse_unit], ensure_ascii=False, indent=2), encoding="utf-8"
        )

        with patch(
            "sqlopt.application.v9_stages.recognition.collect_baseline_v9"
        ) as mock_collect:
            mock_collect.return_value = [
                {
                    "sqlKey": _MIN_SQL_UNIT["sqlKey"],
                    "executionTimeMs": 5.2,
                    "rowsExamined": 100,
                    "rowsReturned": 1,
                    "databasePlatform": "postgresql",
                    "sampleParams": {},
                    "actualExecutionTimeMs": 5.0,
                    "bufferHitCount": 95,
                    "bufferReadCount": 5,
                    "indexUsed": None,
                    "explainPlan": {
                        "scan_type": "Seq Scan",
                        "estimated_cost": 1.0,
                        "estimated_rows": 100,
                    },
                }
            ]

            result = run_stage(
                "recognition",
                temp_run_dir,
                config={"db": {"dsn": "postgresql://localhost/test"}},
                validator=DummyValidator(),
            )

        assert result["success"] is True
        baselines_path = temp_run_dir / "recognition" / "baselines.json"
        assert baselines_path.exists()
        baselines = json.loads(baselines_path.read_text())
        assert len(baselines) == 1


class TestE2EV9PipelineOptimize:
    def test_optimize_stage_with_mock(self, temp_run_dir, validator):
        init_dir = temp_run_dir / "init"
        init_dir.mkdir(parents=True)
        (init_dir / "sql_units.json").write_text(
            json.dumps([_MIN_SQL_UNIT], ensure_ascii=False, indent=2), encoding="utf-8"
        )

        parse_dir = temp_run_dir / "parse"
        parse_dir.mkdir(parents=True)
        (parse_dir / "sql_units_with_branches.json").write_text(
            json.dumps([_MIN_SQL_UNIT], ensure_ascii=False, indent=2), encoding="utf-8"
        )

        rec_dir = temp_run_dir / "recognition"
        rec_dir.mkdir(parents=True)
        (rec_dir / "baselines.json").write_text(
            json.dumps(
                [
                    {
                        "sql_key": _MIN_SQL_UNIT["sqlKey"],
                        "execution_time_ms": 5.2,
                        "rows_scanned": 100,
                        "execution_plan": {
                            "node_type": "Seq Scan",
                            "index_used": None,
                            "cost": 1.0,
                        },
                        "result_hash": "abc123",
                        "rows_returned": 1,
                        "database_platform": "postgresql",
                        "sample_params": {},
                        "actual_execution_time_ms": 5.0,
                        "buffer_hit_count": 95,
                        "buffer_read_count": 5,
                        "explain_plan": {},
                    }
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        with patch("sqlopt.platforms.sql.optimizer_sql.generate_proposal") as mock_gen:
            mock_proposal = Mock()
            mock_proposal.to_contract.return_value = {
                "sqlKey": _MIN_SQL_UNIT["sqlKey"],
                "originalSql": "SELECT 1 AS x",
                "optimizedSql": "SELECT 1 AS x",
                "rewrittenSql": "SELECT 1 AS x",
                "ruleName": "NO_OP",
                "issues": [],
                "verdict": "NO_ACTION",
                "confidence": "high",
                "validated": True,
            }
            mock_gen.return_value = mock_proposal

            with patch(
                "sqlopt.platforms.sql.validator_sql.validate_proposal"
            ) as mock_val:
                mock_val.return_value = Mock(
                    to_contract=lambda: {
                        "status": "PASSED",
                        "warnings": [],
                        "riskFlags": [],
                        "securityChecks": {},
                        "equivalence": {"is_equivalent": True},
                        "perfComparison": {},
                    }
                )

                result = run_stage(
                    "optimize",
                    temp_run_dir,
                    config={"db": {"dsn": "postgresql://localhost/test"}},
                    validator=DummyValidator(),
                )

        assert result["success"] is True


class TestE2EV9PipelinePatch:
    def test_patch_stage_produces_patches(self, temp_run_dir, validator):
        opt_dir = temp_run_dir / "optimize"
        opt_dir.mkdir(parents=True)
        (opt_dir / "proposals.json").write_text(
            json.dumps(
                [
                    {
                        "sqlKey": _MIN_SQL_UNIT["sqlKey"],
                        "originalSql": "SELECT 1 AS x",
                        "optimizedSql": "SELECT 1 AS x",
                        "ruleName": "NO_OP",
                        "issues": [],
                        "dbEvidenceSummary": {},
                        "planSummary": {},
                        "suggestions": [],
                        "verdict": "NO_ACTION",
                        "validated": False,
                    }
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        result = run_stage(
            "patch",
            temp_run_dir,
            config={},
            validator=validator,
        )

        assert result["success"] is True
        patches_path = temp_run_dir / "patch" / "patches.json"
        assert patches_path.exists()


class TestE2EV9Pipeline:
    def test_stage_registry_exposes_v9_stages(self, validator):
        registry = build_stage_registry(
            config={"project": {"root_path": "."}},
            validator=validator,
        )

        assert list(registry.keys()) == STAGE_ORDER
        assert STAGE_ORDER == ["init", "parse", "recognition", "optimize", "patch"]
