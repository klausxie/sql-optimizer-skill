"""Shared helpers for creating stage runtime dependencies."""

from __future__ import annotations

from typing import Any

from sqlopt.common.config import SQLOptConfig


def create_db_connector_from_config(config: SQLOptConfig | None) -> Any | None:
    """Create a database connector from config when connection settings exist."""
    if config is None:
        return None
    if not (config.db_host and config.db_port and config.db_name):
        return None
    from sqlopt.common.db_connector import create_connector

    return create_connector(
        platform=config.db_platform,
        host=config.db_host,
        port=config.db_port,
        db=config.db_name,
        user=config.db_user or "",
        password=config.db_password or "",
        **config.db_connect_options,
    )


def create_llm_provider_from_config(config: SQLOptConfig | None, db_connector: Any | None = None) -> Any | None:
    """Create an LLM provider from config when enabled."""
    if config is None or not config.llm_enabled:
        return None
    from sqlopt.common.llm_mock_generator import OpenAILLMProvider, OpenCodeRunLLMProvider

    if config.llm_provider == "openai":
        return OpenAILLMProvider(
            db_connector=db_connector,
            base_url=config.openai_base_url,
            model=config.openai_model or "gpt-4o-mini",
        )
    if config.llm_provider == "opencode_run":
        return OpenCodeRunLLMProvider(db_connector=db_connector)
    return None
