from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlopt.contracts import ContractValidator
from sqlopt.errors import ContractError


class TestStageBoundaryValidation(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).parent.parent

    def _validator(self) -> ContractValidator:
        return ContractValidator(self.repo_root)

    def test_validate_stage_input_discovery_none(self) -> None:
        v = self._validator()
        v.validate_stage_input("discovery", {"some": "data"})

    def test_validate_stage_output_discovery_sqlunit(self) -> None:
        v = self._validator()
        sqlunit = {
            "sqlKey": "com.example.Mapper.selectAll",
            "xmlPath": "/tmp/mapper.xml",
            "namespace": "com.example",
            "statementId": "selectAll",
            "statementType": "SELECT",
            "variantId": "v1",
            "sql": "SELECT * FROM users",
            "parameterMappings": [],
            "paramExample": {},
            "locators": {},
            "riskFlags": [],
        }
        v.validate_stage_output("discovery", sqlunit)

    def test_validate_stage_input_branching_sqlunit(self) -> None:
        v = self._validator()
        sqlunit = {
            "sqlKey": "com.example.Mapper.selectAll",
            "xmlPath": "/tmp/mapper.xml",
            "namespace": "com.example",
            "statementId": "selectAll",
            "statementType": "SELECT",
            "variantId": "v1",
            "sql": "SELECT * FROM users",
            "parameterMappings": [],
            "paramExample": {},
            "locators": {},
            "riskFlags": [],
        }
        v.validate_stage_input("branching", sqlunit)

    def test_validate_stage_output_branching_sqlunit(self) -> None:
        v = self._validator()
        sqlunit = {
            "sqlKey": "com.example.Mapper.selectAll",
            "xmlPath": "/tmp/mapper.xml",
            "namespace": "com.example",
            "statementId": "selectAll",
            "statementType": "SELECT",
            "variantId": "v1",
            "sql": "SELECT * FROM users",
            "parameterMappings": [],
            "paramExample": {},
            "locators": {},
            "riskFlags": [],
            "branches": [
                {
                    "id": 1,
                    "conditions": [],
                    "sql": "SELECT * FROM users",
                    "type": "static",
                }
            ],
            "branchCount": 1,
        }
        v.validate_stage_output("branching", sqlunit)

    def test_validate_stage_input_pruning_sqlunit(self) -> None:
        v = self._validator()
        sqlunit = {
            "sqlKey": "com.example.Mapper.selectAll",
            "xmlPath": "/tmp/mapper.xml",
            "namespace": "com.example",
            "statementId": "selectAll",
            "statementType": "SELECT",
            "variantId": "v1",
            "sql": "SELECT * FROM users",
            "parameterMappings": [],
            "paramExample": {},
            "locators": {},
            "riskFlags": [],
        }
        v.validate_stage_input("pruning", sqlunit)

    def test_validate_stage_output_pruning_none(self) -> None:
        v = self._validator()
        v.validate_stage_output("pruning", {"custom": "risks"})

    def test_validate_stage_input_baseline_sqlunit(self) -> None:
        v = self._validator()
        sqlunit = {
            "sqlKey": "com.example.Mapper.selectAll",
            "xmlPath": "/tmp/mapper.xml",
            "namespace": "com.example",
            "statementId": "selectAll",
            "statementType": "SELECT",
            "variantId": "v1",
            "sql": "SELECT * FROM users",
            "parameterMappings": [],
            "paramExample": {},
            "locators": {},
            "riskFlags": [],
        }
        v.validate_stage_input("baseline", sqlunit)

    def test_validate_stage_output_baseline_baseline_result(self) -> None:
        v = self._validator()
        baseline = {
            "sql_key": "com.example.Mapper.selectAll",
            "execution_time_ms": 10.5,
            "rows_scanned": 100,
            "execution_plan": {"node_type": "Seq Scan"},
            "result_hash": "abc123",
        }
        v.validate_stage_output("baseline", baseline)

    def test_validate_stage_input_optimize_baseline_result(self) -> None:
        v = self._validator()
        baseline = {
            "sql_key": "com.example.Mapper.selectAll",
            "execution_time_ms": 10.5,
            "rows_scanned": 100,
            "execution_plan": {"node_type": "Seq Scan"},
            "result_hash": "abc123",
        }
        v.validate_stage_input("optimize", baseline)

    def test_validate_stage_output_optimize_optimization_proposal(self) -> None:
        v = self._validator()
        proposal = {
            "sqlKey": "com.example.Mapper.selectAll",
            "issues": ["PREFIX_WILDCARD"],
            "dbEvidenceSummary": {},
            "planSummary": {},
            "suggestions": [],
            "verdict": "ACTIONABLE",
        }
        v.validate_stage_output("optimize", proposal)

    def test_validate_stage_input_validate_optimization_proposal(self) -> None:
        v = self._validator()
        proposal = {
            "sqlKey": "com.example.Mapper.selectAll",
            "issues": ["PREFIX_WILDCARD"],
            "dbEvidenceSummary": {},
            "planSummary": {},
            "suggestions": [],
            "verdict": "ACTIONABLE",
        }
        v.validate_stage_input("validate", proposal)

    def test_validate_stage_output_validate_acceptance_result(self) -> None:
        v = self._validator()
        acceptance = {
            "sqlKey": "com.example.Mapper.selectAll",
            "status": "PASSED",
            "equivalence": {},
            "perfComparison": {},
            "securityChecks": {},
        }
        v.validate_stage_output("validate", acceptance)

    def test_validate_stage_input_patch_acceptance_result(self) -> None:
        v = self._validator()
        acceptance = {
            "sqlKey": "com.example.Mapper.selectAll",
            "status": "PASSED",
            "equivalence": {},
            "perfComparison": {},
            "securityChecks": {},
        }
        v.validate_stage_input("patch", acceptance)

    def test_validate_stage_output_patch_patch_result(self) -> None:
        v = self._validator()
        patch = {
            "sqlKey": "com.example.Mapper.selectAll",
            "patchFiles": [],
            "diffSummary": {},
            "applyMode": "MANUAL",
            "rollback": "N/A",
        }
        v.validate_stage_output("patch", patch)

    def test_validate_stage_input_unknown_stage_raises(self) -> None:
        v = self._validator()
        with self.assertRaisesRegex(ContractError, r"unknown stage: nonexistent"):
            v.validate_stage_input("nonexistent", {})

    def test_validate_stage_output_unknown_stage_raises(self) -> None:
        v = self._validator()
        with self.assertRaisesRegex(ContractError, r"unknown stage: nonexistent"):
            v.validate_stage_output("nonexistent", {})

    def test_get_stage_schema_valid(self) -> None:
        v = self._validator()
        schema = v.get_stage_schema("discovery", "output")
        self.assertIsInstance(schema, dict)
        self.assertEqual(schema.get("title"), "SqlUnit")

    def test_get_stage_schema_input(self) -> None:
        v = self._validator()
        schema = v.get_stage_schema("baseline", "input")
        self.assertIsInstance(schema, dict)
        self.assertEqual(schema.get("title"), "SqlUnit")

    def test_get_stage_schema_output(self) -> None:
        v = self._validator()
        schema = v.get_stage_schema("optimize", "output")
        self.assertIsInstance(schema, dict)
        self.assertEqual(schema.get("title"), "OptimizationProposal")

    def test_get_stage_schema_none_output(self) -> None:
        v = self._validator()
        schema = v.get_stage_schema("pruning", "output")
        self.assertIsNone(schema)

    def test_get_stage_schema_none_input(self) -> None:
        v = self._validator()
        schema = v.get_stage_schema("discovery", "input")
        self.assertIsNone(schema)

    def test_get_stage_schema_invalid_io_type(self) -> None:
        v = self._validator()
        with self.assertRaisesRegex(
            ContractError, r"io_type must be 'input' or 'output'"
        ):
            v.get_stage_schema("discovery", "invalid")

    def test_validate_stage_input_missing_required_fields_raises(self) -> None:
        v = self._validator()
        with self.assertRaisesRegex(
            ContractError, r"stage 'discovery' output validation failed"
        ):
            v.validate_stage_output("discovery", {})

    def test_validate_stage_input_wrong_type_raises(self) -> None:
        v = self._validator()
        with self.assertRaisesRegex(
            ContractError, r"stage 'discovery' output validation failed"
        ):
            v.validate_stage_output("discovery", "not an object")

    def test_validate_stage_output_error_includes_path(self) -> None:
        v = self._validator()
        sqlunit = {
            "sqlKey": "com.example.Mapper.selectAll",
            "xmlPath": "/tmp/mapper.xml",
            "namespace": "com.example",
            "statementId": "selectAll",
            "statementType": "SELECT",
            "variantId": "v1",
            "sql": "SELECT * FROM users",
            "parameterMappings": [],
            "paramExample": {},
            "locators": {},
            "riskFlags": [],
            "baseline": {
                "executionTime": "10ms",
                "rowsExamined": 100,
                "rowsReturned": 10,
                "usingIndex": True,
                "type": "INDEX_RANGE_SCAN",
                "planLines": [],
                "problematic": False,
                "baselineTest": "invalid_type_should_be_object",
            },
        }
        with self.assertRaisesRegex(
            ContractError,
            r"stage 'discovery' output validation failed.*path 'baseline\.baselineTest'",
        ):
            v.validate_stage_output("discovery", sqlunit)


class TestStageBoundaryIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).parent.parent

    def _validator(self) -> ContractValidator:
        return ContractValidator(self.repo_root)

    def test_full_pipeline_happy_path(self) -> None:
        v = self._validator()
        sqlunit = {
            "sqlKey": "com.example.Mapper.selectAll",
            "xmlPath": "/tmp/mapper.xml",
            "namespace": "com.example",
            "statementId": "selectAll",
            "statementType": "SELECT",
            "variantId": "v1",
            "sql": "SELECT * FROM users",
            "parameterMappings": [],
            "paramExample": {},
            "locators": {},
            "riskFlags": [],
        }
        v.validate_stage_output("discovery", sqlunit)
        v.validate_stage_input("branching", sqlunit)
        v.validate_stage_output("branching", sqlunit)
        v.validate_stage_input("pruning", sqlunit)
        v.validate_stage_output("pruning", {"risks": []})
        v.validate_stage_input("baseline", sqlunit)
        baseline = {
            "sql_key": "com.example.Mapper.selectAll",
            "execution_time_ms": 10.5,
            "rows_scanned": 100,
            "execution_plan": {"node_type": "Seq Scan"},
            "result_hash": "abc123",
        }
        v.validate_stage_output("baseline", baseline)
        v.validate_stage_input("optimize", baseline)
        proposal = {
            "sqlKey": "com.example.Mapper.selectAll",
            "issues": ["PREFIX_WILDCARD"],
            "dbEvidenceSummary": {},
            "planSummary": {},
            "suggestions": [],
            "verdict": "ACTIONABLE",
        }
        v.validate_stage_output("optimize", proposal)
        v.validate_stage_input("validate", proposal)
        acceptance = {
            "sqlKey": "com.example.Mapper.selectAll",
            "status": "PASSED",
            "equivalence": {},
            "perfComparison": {},
            "securityChecks": {},
        }
        v.validate_stage_output("validate", acceptance)
        v.validate_stage_input("patch", acceptance)
        patch = {
            "sqlKey": "com.example.Mapper.selectAll",
            "patchFiles": [],
            "diffSummary": {},
            "applyMode": "MANUAL",
            "rollback": "N/A",
        }
        v.validate_stage_output("patch", patch)


if __name__ == "__main__":
    unittest.main()
