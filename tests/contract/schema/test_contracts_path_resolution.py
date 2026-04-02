from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlopt.contracts import SCHEMA_MAP, ContractValidator
from sqlopt.errors import ContractError


class ContractsPathResolutionTest(unittest.TestCase):
    def test_falls_back_to_packaged_contracts_when_project_contracts_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_contracts_missing_") as td:
            repo_root = Path(td)
            validator = ContractValidator(repo_root)
            self.assertTrue((validator.contract_dir / "stages" / "sqlunit.schema.json").exists())
            schema = validator._schema("sqlunit")
            self.assertIsInstance(schema, dict)

    def test_prefers_project_contracts_when_present(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_contracts_present_") as td:
            repo_root = Path(td)
            contract_dir = repo_root / "contracts"
            (contract_dir / "stages").mkdir(parents=True, exist_ok=True)
            (contract_dir / "stages" / "sqlunit.schema.json").write_text(json.dumps({"type": "object"}), encoding="utf-8")
            validator = ContractValidator(repo_root)
            self.assertEqual(validator.contract_dir, contract_dir)
            self.assertEqual(validator._schema("sqlunit"), {"type": "object"})

    def test_schema_inventory_uses_grouped_paths(self) -> None:
        validator = ContractValidator(Path(__file__).resolve().parents[3])
        self.assertEqual(
            {
                "sqlunit",
                "fragment_record",
                "optimization_proposal",
                "acceptance_result",
                "patch_result",
                "run_report",
                "run_index",
                "sql_artifact_index_row",
            },
            set(SCHEMA_MAP.keys()),
        )
        self.assertEqual(SCHEMA_MAP["sqlunit"], "stages/sqlunit.schema.json")
        self.assertEqual(SCHEMA_MAP["run_report"], "run/run_report.schema.json")
        self.assertEqual(SCHEMA_MAP["sql_artifact_index_row"], "sql/sql_artifact_index_row.schema.json")

    def test_removed_contract_names_are_unknown(self) -> None:
        validator = ContractValidator(Path(__file__).resolve().parents[3])
        for name in ("verification_record", "verification_summary", "ops_health", "ops_topology"):
            with self.assertRaisesRegex(ContractError, "unknown schema"):
                validator.validate(name, {})


if __name__ == "__main__":
    unittest.main()
