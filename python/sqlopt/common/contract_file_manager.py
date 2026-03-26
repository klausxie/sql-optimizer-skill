"""ContractFileManager - Per-unit file operations for contract data."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class ContractFileManager:
    """Manages per-unit file storage for contract data.

    File structure:
        runs/{run_id}/{stage_name}/units/{unit_id_sanitized}.json
        runs/{run_id}/{stage_name}/units/_index.json
    """

    def __init__(self, run_id: str, stage_name: str) -> None:
        """Initialize the file manager.

        Args:
            run_id: The run identifier (e.g., "run-20260325-120000")
            stage_name: The stage name (e.g., "recognition", "optimize")
        """
        self.run_id = run_id
        self.stage_name = stage_name
        self.units_dir = Path("runs") / run_id / stage_name / "units"

    def write_unit_file(self, unit_id: str, data: dict[str, Any]) -> Path:
        """Write a single unit's data to its own file.

        Args:
            unit_id: Fully qualified unit ID (e.g., "UserMapper.findUser")
            data: The unit data to write

        Returns:
            Path to the written file
        """
        self.units_dir.mkdir(parents=True, exist_ok=True)
        filename = self._sanitize_filename(unit_id)
        file_path = self.units_dir / f"{filename}.json"
        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return file_path

    def write_index(self, unit_ids: list[str]) -> Path:
        """Write the index file with atomic write pattern (temp + rename).

        Args:
            unit_ids: List of unit IDs to include in the index

        Returns:
            Path to the written index file
        """
        self.units_dir.mkdir(parents=True, exist_ok=True)
        index_path = self.units_dir / "_index.json"
        temp_path = self.units_dir / "_index.json.tmp"

        temp_path.write_text(json.dumps(unit_ids, indent=2, ensure_ascii=False), encoding="utf-8")
        # Path.rename() does not replace existing files on Windows.
        temp_path.replace(index_path)
        return index_path

    def read_unit_file(self, unit_id: str) -> dict[str, Any]:
        """Read a single unit's data from its file.

        Args:
            unit_id: Fully qualified unit ID

        Returns:
            The unit data as a dictionary

        Raises:
            FileNotFoundError: If the unit file does not exist
        """
        filename = self._sanitize_filename(unit_id)
        file_path = self.units_dir / f"{filename}.json"
        return json.loads(file_path.read_text(encoding="utf-8"))

    def read_index(self) -> list[str]:
        """Read the index file.

        Returns:
            List of unit IDs

        Raises:
            FileNotFoundError: If the index file does not exist
        """
        index_path = self.units_dir / "_index.json"
        return json.loads(index_path.read_text(encoding="utf-8"))

    def get_file_size(self, path: Path) -> int:
        """Get the size of a file in bytes.

        Args:
            path: Path to the file

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If the file does not exist
        """
        return path.stat().st_size

    def _sanitize_filename(self, unit_id: str) -> str:
        """Sanitize unit ID for use as a filename.

        Replaces characters that are invalid in filenames:
        - Forward slash (/)
        - Backslash (\\)
        - Question mark (?)
        - Asterisk (*)
        - Colon (:)

        Args:
            unit_id: The unit ID to sanitize

        Returns:
            Sanitized filename-safe string
        """
        return re.sub(r"[/\\?*:]", "_", unit_id)
