"""
Shared Storage Module

Run artifacts storage and retrieval.
"""

import json
from pathlib import Path
from typing import Any


def save_artifact(run_dir: Path, artifact_type: str, data: Any) -> Path:
    """Save artifact to run directory.

    Args:
        run_dir: Run directory path
        artifact_type: Type of artifact (e.g., 'scan', 'optimize', 'validate')
        data: Data to save

    Returns:
        Path to saved artifact
    """
    artifact_dir = run_dir / "pipeline" / artifact_type
    artifact_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = artifact_dir / "data.json"
    with open(artifact_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return artifact_path


def load_artifact(run_dir: Path, artifact_type: str) -> Any:
    """Load artifact from run directory.

    Args:
        run_dir: Run directory path
        artifact_type: Type of artifact

    Returns:
        Loaded artifact data
    """
    artifact_path = run_dir / "pipeline" / artifact_type / "data.json"

    if not artifact_path.exists():
        return None

    with open(artifact_path, encoding="utf-8") as f:
        return json.load(f)


def list_artifacts(run_dir: Path) -> list[str]:
    """List all artifacts in run directory.

    Args:
        run_dir: Run directory path

    Returns:
        List of artifact types
    """
    pipeline_dir = run_dir / "pipeline"

    if not pipeline_dir.exists():
        return []

    artifacts = []
    for item in pipeline_dir.iterdir():
        if item.is_dir() and (item / "data.json").exists():
            artifacts.append(item.name)

    return artifacts


__all__ = [
    "save_artifact",
    "load_artifact",
    "list_artifacts",
]
