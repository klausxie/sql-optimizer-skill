# Sample Loader Module
# Loads test samples for patch module testing

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SampleLoader:
    """Loads test samples from the harness sample directory."""

    def __init__(self, harness_root: Path | None = None):
        if harness_root is None:
            harness_root = Path(__file__).parent
        self.harness_root = Path(harness_root)
        self.samples_dir = self.harness_root / "samples"

    def load_sql_unit(self, category: str, name: str) -> dict[str, Any]:
        """Load a SQL unit sample by category and name."""
        path = self.samples_dir / "sql_units" / category / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def load_proposal(self, category: str, name: str) -> dict[str, Any]:
        """Load a proposal sample by category and name."""
        path = self.samples_dir / "proposals" / category / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def load_acceptance(self, category: str, name: str) -> dict[str, Any]:
        """Load an acceptance sample by category and name."""
        path = self.samples_dir / "acceptance" / category / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def load_patch(self, category: str, name: str) -> dict[str, Any]:
        """Load a patch sample by category and name."""
        path = self.samples_dir / "patch" / category / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def list_sql_units(self, category: str | None = None) -> list[str]:
        """List available SQL unit sample names."""
        if category:
            dir_path = self.samples_dir / "sql_units" / category
        else:
            dir_path = self.samples_dir / "sql_units"
        if not dir_path.exists():
            return []
        return [p.stem for p in dir_path.glob("*.json")]

    def list_proposals(self, category: str | None = None) -> list[str]:
        """List available proposal sample names."""
        if category:
            dir_path = self.samples_dir / "proposals" / category
        else:
            dir_path = self.samples_dir / "proposals"
        if not dir_path.exists():
            return []
        return [p.stem for p in dir_path.glob("*.json")]

    def list_acceptance(self, category: str | None = None) -> list[str]:
        """List available acceptance sample names."""
        if category:
            dir_path = self.samples_dir / "acceptance" / category
        else:
            dir_path = self.samples_dir / "acceptance"
        if not dir_path.exists():
            return []
        return [p.stem for p in dir_path.glob("*.json")]

    def list_patch(self, category: str | None = None) -> list[str]:
        """List available patch sample names."""
        if category:
            dir_path = self.samples_dir / "patch" / category
        else:
            dir_path = self.samples_dir / "patch"
        if not dir_path.exists():
            return []
        return [p.stem for p in dir_path.glob("*.json")]

    def load_full_chain(
        self,
        sql_unit_sample: str,
        proposal_sample: str,
        acceptance_sample: str,
        patch_sample: str | None = None,
    ) -> dict[str, Any]:
        """Load a full chain of samples (sql_unit + proposal + acceptance + patch)."""
        # Parse the sample names to get categories
        sql_parts = sql_unit_sample.split("/")
        proposal_parts = proposal_sample.split("/")
        acceptance_parts = acceptance_sample.split("/")

        sql_category = sql_parts[0] if len(sql_parts) > 1 else "static"
        sql_name = sql_parts[-1]

        proposal_category = proposal_parts[0] if len(proposal_parts) > 1 else "static"
        proposal_name = proposal_parts[-1]

        acceptance_category = acceptance_parts[0] if len(acceptance_parts) > 1 else "pass"
        acceptance_name = acceptance_parts[-1]

        result = {
            "sql_unit": self.load_sql_unit(sql_category, sql_name),
            "proposal": self.load_proposal(proposal_category, proposal_name),
            "acceptance": self.load_acceptance(acceptance_category, acceptance_name),
        }

        if patch_sample:
            patch_parts = patch_sample.split("/")
            patch_category = patch_parts[0] if len(patch_parts) > 1 else "ready"
            patch_name = patch_parts[-1]
            result["patch"] = self.load_patch(patch_category, patch_name)

        return result


# Global loader instance
_loader: SampleLoader | None = None


def get_loader() -> SampleLoader:
    """Get the global SampleLoader instance."""
    global _loader
    if _loader is None:
        _loader = SampleLoader()
    return _loader