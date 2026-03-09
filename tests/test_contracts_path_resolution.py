from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlopt.contracts import ContractValidator


class ContractsPathResolutionTest(unittest.TestCase):
    def test_falls_back_to_packaged_contracts_when_project_contracts_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_contracts_missing_") as td:
            repo_root = Path(td)
            validator = ContractValidator(repo_root)
            self.assertTrue((validator.contract_dir / "sqlunit.schema.json").exists())
            schema = validator._schema("sqlunit")
            self.assertIsInstance(schema, dict)

    def test_prefers_project_contracts_when_present(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_contracts_present_") as td:
            repo_root = Path(td)
            contract_dir = repo_root / "contracts"
            contract_dir.mkdir(parents=True, exist_ok=True)
            (contract_dir / "sqlunit.schema.json").write_text(json.dumps({"type": "object"}), encoding="utf-8")
            validator = ContractValidator(repo_root)
            self.assertEqual(validator.contract_dir, contract_dir)
            self.assertEqual(validator._schema("sqlunit"), {"type": "object"})


if __name__ == "__main__":
    unittest.main()
