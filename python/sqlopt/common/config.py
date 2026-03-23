"""Configuration management for SQL Optimizer."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml


@dataclass
class SQLOptConfig:
    """SQL Optimizer configuration.

    Attributes:
        config_version: Configuration schema version.
        project_root_path: Root path of the project being analyzed.
        scan_mapper_globs: Glob patterns to find MyBatis mapper XML files.
        db_platform: Target database platform (postgresql, mysql).
        db_dsn: Database connection string for validation.
        llm_enabled: Whether to enable LLM-based optimization.
        llm_provider: LLM provider to use (opencode_run, openai, anthropic).
        contracts_version: Version of contracts schema to use.
    """

    config_version: str = "v1"
    project_root_path: str = "."
    scan_mapper_globs: List[str] = field(default_factory=lambda: ["src/main/resources/**/*.xml"])
    db_platform: str = "postgresql"
    db_dsn: str = ""
    llm_enabled: bool = True
    llm_provider: str = "opencode_run"
    contracts_version: str = "current"


def load_config(config_path: str = "./sqlopt.yml") -> SQLOptConfig:
    """Load configuration from YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        SQLOptConfig instance with loaded values.

    Raises:
        FileNotFoundError: If config file does not exist.
        ValueError: If required fields are missing or invalid.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError("Config file must contain a YAML mapping")

    return SQLOptConfig(
        config_version=data.get("config_version", "v1"),
        project_root_path=data.get("project_root_path", "."),
        scan_mapper_globs=data.get("scan_mapper_globs", ["src/main/resources/**/*.xml"]),
        db_platform=data.get("db_platform", "postgresql"),
        db_dsn=data.get("db_dsn", ""),
        llm_enabled=data.get("llm_enabled", True),
        llm_provider=data.get("llm_provider", "opencode_run"),
        contracts_version=data.get("contracts_version", "current"),
    )
