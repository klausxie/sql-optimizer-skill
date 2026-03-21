from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...contracts import ContractValidator
from ...run_paths import canonical_paths
from .common import normalize_sqlunit


def run_init(
    run_dir: Path,
    *,
    config: dict[str, Any],
    validator: ContractValidator,
) -> dict[str, Any]:
    from ...stages.discovery import Scanner

    scanner = Scanner(config)
    root_path = config.get("project", {}).get("root_path", ".")

    result = scanner.scan(root_path)
    sql_units = [normalize_sqlunit(unit) for unit in result.sql_units]
    for unit in sql_units:
        validator.validate_stage_output("init", unit)

    output_path = canonical_paths(run_dir).init_sql_units_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(sql_units, f, indent=2, ensure_ascii=False)

    return {
        "success": True,
        "output_file": str(output_path),
        "sql_units_count": len(sql_units),
    }
