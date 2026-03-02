from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import load_config


def validate_config(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    results: dict[str, Any] = {
        "valid": True,
        "config_path": str(config_path),
        "checks": [],
    }

    required_fields = [
        ("project", "root_path"),
        ("scan", "mapper_globs"),
        ("db", "platform"),
        ("db", "dsn"),
    ]

    for *path, field in required_fields:
        current: Any = config
        field_path = ".".join(path + [field])
        try:
            for key in path:
                current = current[key]
            if field in current:
                results["checks"].append(
                    {
                        "field": field_path,
                        "status": "ok",
                        "value": str(current[field])[:50],
                    }
                )
            else:
                results["checks"].append(
                    {
                        "field": field_path,
                        "status": "missing",
                        "message": "Required field is missing",
                    }
                )
                results["valid"] = False
        except (KeyError, TypeError):
            results["checks"].append(
                {
                    "field": field_path,
                    "status": "missing",
                    "message": "Parent section is missing",
                }
            )
            results["valid"] = False

    dsn = config.get("db", {}).get("dsn", "")
    if "<" in dsn or ">" in dsn:
        results["checks"].append(
            {
                "field": "db.dsn",
                "status": "warning",
                "message": "DSN contains placeholders, please replace with actual values",
            }
        )

    jar_path = config.get("scan", {}).get("java_scanner", {}).get("jar_path", "")
    if jar_path == "__SCANNER_JAR__":
        results["checks"].append(
            {
                "field": "scan.java_scanner.jar_path",
                "status": "warning",
                "message": "JAR path is placeholder, run install_skill.py to fix",
            }
        )

    mapper_globs = config.get("scan", {}).get("mapper_globs", [])
    if mapper_globs:
        project_root = Path(config.get("project", {}).get("root_path", ".")).resolve()
        import glob as glob_module

        found_files: list[str] = []
        for pattern in mapper_globs:
            full_pattern = str(project_root / pattern)
            matches = glob_module.glob(full_pattern, recursive=True)
            found_files.extend(matches)

        results["checks"].append(
            {
                "field": "scan.mapper_globs",
                "status": "ok" if found_files else "warning",
                "message": f"Found {len(found_files)} mapper file(s)" if found_files else "No mapper files found",
            }
        )

    return results
