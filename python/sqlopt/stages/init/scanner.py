from __future__ import annotations

from pathlib import Path


def find_mapper_files(project_root: str, globs: list[str]) -> list[Path]:
    root = Path(project_root).resolve()
    found: list[Path] = []

    for pattern in globs:
        full_pattern = root / pattern
        for path in full_pattern.parent.glob(full_pattern.name):
            if path.suffix.lower() == ".xml" and path.is_file() and path not in found:
                found.append(path)

    return sorted(found)
