"""Configuration management for SQL Optimizer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml


@dataclass
class ConcurrencyConfig:
    enabled: bool = True
    max_workers: int = 4
    db_pool_size: int = 5
    llm_max_concurrent: int = 3
    batch_size: int = 10
    timeout_per_task: int = 300
    retry_count: int = 3
    retry_delay: int = 1


@dataclass
class SQLOptConfig:
    """SQL Optimizer configuration.

    Attributes:
        config_version: Configuration schema version.
        project_root_path: Root path of the project being analyzed.
        scan_mapper_globs: Glob patterns to find MyBatis mapper XML files.
        statement_types: List of SQL statement types to process (SELECT, INSERT, UPDATE, DELETE).
            If None or empty, all types are processed. Default: ["SELECT"]
        db_platform: Target database platform (postgresql, mysql).
        db_host: Database host address.
        db_port: Database port number.
        db_name: Database name.
        db_user: Database user.
        db_password: Database password.
        db_dsn: Database connection string (legacy/backward compatibility).
        llm_enabled: Whether to enable LLM-based optimization.
        llm_provider: LLM provider to use (opencode_run, openai, anthropic).
        contracts_version: Version of contracts schema to use.
        parse_strategy: Strategy for parsing dynamic SQL (ladder, pairwise).
        parse_max_branches: Maximum number of branches to generate per SQL.
    """

    config_version: str = "v1"
    project_root_path: str = "."
    scan_mapper_globs: List[str] = field(default_factory=lambda: ["src/main/resources/**/*.xml"])
    statement_types: List[str] = field(default_factory=lambda: ["SELECT"])
    db_platform: str = "postgresql"
    db_host: str | None = None
    db_port: int | None = None
    db_name: str | None = None
    db_user: str | None = None
    db_password: str | None = None
    db_dsn: str = ""
    llm_enabled: bool = True
    llm_provider: str = "opencode_run"
    contracts_version: str = "current"
    parse_strategy: str = "ladder"
    parse_max_branches: int = 50
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)


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
        statement_types=data.get("statement_types", ["SELECT"]),
        db_platform=data.get("db_platform", "postgresql"),
        db_host=data.get("db_host"),
        db_port=data.get("db_port"),
        db_name=data.get("db_name"),
        db_user=data.get("db_user"),
        db_password=data.get("db_password"),
        db_dsn=data.get("db_dsn", ""),
        llm_enabled=data.get("llm_enabled", True),
        llm_provider=data.get("llm_provider", "opencode_run"),
        contracts_version=data.get("contracts_version", "current"),
        parse_strategy=data.get("parse_strategy", "ladder"),
        parse_max_branches=data.get("parse_max_branches", 50),
        concurrency=ConcurrencyConfig(
            **(data.get("concurrency", {}) if isinstance(data.get("concurrency"), dict) else {})
        ),
    )
