# Patch Runner Module
# Executes patch generation with test samples

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from sqlopt.contracts import ContractValidator
from sqlopt.stages import patch_generate as patch_gen


class PatchRunner:
    """Test harness for running patch generation with samples."""

    def __init__(self, harness_root: Path | None = None):
        if harness_root is None:
            harness_root = Path(__file__).parent
        self.harness_root = Path(harness_root)
        self.samples_dir = self.harness_root / "samples"

    def run_with_samples(
        self,
        sql_unit_sample: str,
        proposal_sample: str,
        acceptance_sample: str,
        run_dir: Path,
        validator: ContractValidator | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run patch generation with specified samples.

        Args:
            sql_unit_sample: SQL unit sample name (e.g., "static/wrapper_count")
            proposal_sample: Proposal sample name
            acceptance_sample: Acceptance sample name
            run_dir: Run directory for outputs
            validator: Contract validator
            config: Configuration dict

        Returns:
            Patch result dict
        """
        # Parse sample names
        sql_parts = sql_unit_sample.split("/")
        proposal_parts = proposal_sample.split("/")
        acceptance_parts = acceptance_sample.split("/")

        # Load samples
        sql_unit = self._load_json(["sql_units"] + sql_parts)
        proposal = self._load_json(["proposals"] + proposal_parts)
        acceptance = self._load_json(["acceptance"] + acceptance_parts)

        # Create run directory structure
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)

        # Write acceptance results to run_dir for patch_generate to read
        acceptance_path = run_dir / "acceptance" / "acceptance.results.jsonl"
        acceptance_path.parent.mkdir(parents=True, exist_ok=True)
        acceptance_path.write_text(json.dumps(acceptance, ensure_ascii=False) + "\n", encoding="utf-8")

        # Execute patch generation
        result = patch_gen.execute_one(
            sql_unit=sql_unit,
            acceptance=acceptance,
            run_dir=run_dir,
            validator=validator,
            config=config,
        )

        return result

    def _load_json(self, parts: list[str]) -> dict[str, Any]:
        """Load a JSON sample file."""
        category = parts[-2]
        name = parts[-1]
        path = self.samples_dir / "/".join(parts[:-2]) / category / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def list_available_samples(self) -> dict[str, list[str]]:
        """List all available samples by category."""
        return {
            "sql_units": self._list_samples_in_dir(self.samples_dir / "sql_units"),
            "proposals": self._list_samples_in_dir(self.samples_dir / "proposals"),
            "acceptance": self._list_samples_in_dir(self.samples_dir / "acceptance"),
            "patch": self._list_samples_in_dir(self.samples_dir / "patch"),
        }

    def _list_samples_in_dir(self, base_dir: Path) -> dict[str, list[str]]:
        """List samples in a directory by category."""
        result = {}
        if not base_dir.exists():
            return result
        for category_dir in base_dir.iterdir():
            if category_dir.is_dir():
                category = category_dir.name
                result[category] = [p.stem for p in category_dir.glob("*.json")]
        return result


def run_patch_test(
    sql_unit_sample: str,
    proposal_sample: str,
    acceptance_sample: str,
    run_dir: Path,
    expected_tier: str | None = None,
    validator: ContractValidator | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool, str]:
    """
    Run a patch test with samples and validate result.

    Returns:
        (result, passed, message)
    """
    runner = PatchRunner()

    try:
        result = runner.run_with_samples(
            sql_unit_sample=sql_unit_sample,
            proposal_sample=proposal_sample,
            acceptance_sample=acceptance_sample,
            run_dir=run_dir,
            validator=validator,
            config=config,
        )

        # Validate expected tier if provided
        if expected_tier:
            actual_tier = result.get("deliveryOutcome", {}).get("tier", "UNKNOWN")
            if actual_tier == expected_tier:
                return result, True, f"Expected tier {expected_tier} matches actual {actual_tier}"
            else:
                return result, False, f"Expected tier {expected_tier} but got {actual_tier}"

        return result, True, "Test completed"

    except Exception as e:
        return {}, False, f"Test failed: {str(e)}"


# Global runner instance
_runner: PatchRunner | None = None


def get_runner() -> PatchRunner:
    """Get the global PatchRunner instance."""
    global _runner
    if _runner is None:
        _runner = PatchRunner()
    return _runner