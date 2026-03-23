"""Tests for SQLOptConfig and load_config."""

import tempfile
from pathlib import Path

import pytest
import yaml
from sqlopt.common.config import SQLOptConfig, load_config


class TestSQLOptConfigDefaults:
    """Test SQLOptConfig default values."""

    def test_default_config_version(self):
        """Test default config_version is v1."""
        config = SQLOptConfig()
        assert config.config_version == "v1"

    def test_default_project_root_path(self):
        """Test default project_root_path is current directory."""
        config = SQLOptConfig()
        assert config.project_root_path == "."

    def test_default_scan_mapper_globs(self):
        """Test default scan_mapper_globs contains expected pattern."""
        config = SQLOptConfig()
        assert config.scan_mapper_globs == ["src/main/resources/**/*.xml"]

    def test_default_db_platform(self):
        """Test default db_platform is postgresql."""
        config = SQLOptConfig()
        assert config.db_platform == "postgresql"

    def test_default_db_dsn(self):
        """Test default db_dsn is empty string."""
        config = SQLOptConfig()
        assert config.db_dsn == ""

    def test_default_llm_enabled(self):
        """Test default llm_enabled is True."""
        config = SQLOptConfig()
        assert config.llm_enabled is True

    def test_default_llm_provider(self):
        """Test default llm_provider is opencode_run."""
        config = SQLOptConfig()
        assert config.llm_provider == "opencode_run"

    def test_default_contracts_version(self):
        """Test default contracts_version is current."""
        config = SQLOptConfig()
        assert config.contracts_version == "current"


class TestSQLOptConfigCustomValues:
    """Test SQLOptConfig with custom values."""

    def test_custom_values(self):
        """Test SQLOptConfig accepts custom values."""
        config = SQLOptConfig(
            config_version="v2",
            project_root_path="/custom/path",
            scan_mapper_globs=["custom/**/*.xml"],
            db_platform="mysql",
            db_dsn="mysql://localhost:3306/testdb",
            llm_enabled=False,
            llm_provider="openai",
            contracts_version="v1",
        )
        assert config.config_version == "v2"
        assert config.project_root_path == "/custom/path"
        assert config.scan_mapper_globs == ["custom/**/*.xml"]
        assert config.db_platform == "mysql"
        assert config.db_dsn == "mysql://localhost:3306/testdb"
        assert config.llm_enabled is False
        assert config.llm_provider == "openai"
        assert config.contracts_version == "v1"


class TestLoadConfig:
    """Test load_config function."""

    def test_load_config_from_valid_yaml(self):
        """Test loading config from a valid YAML file."""
        config_data = {
            "config_version": "v2",
            "project_root_path": "/my/project",
            "scan_mapper_globs": ["custom/**/*.xml"],
            "db_platform": "mysql",
            "db_dsn": "mysql://localhost:3306/mydb",
            "llm_enabled": False,
            "llm_provider": "anthropic",
            "contracts_version": "v1",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            config = load_config(temp_path)
            assert config.config_version == "v2"
            assert config.project_root_path == "/my/project"
            assert config.scan_mapper_globs == ["custom/**/*.xml"]
            assert config.db_platform == "mysql"
            assert config.db_dsn == "mysql://localhost:3306/mydb"
            assert config.llm_enabled is False
            assert config.llm_provider == "anthropic"
            assert config.contracts_version == "v1"
        finally:
            Path(temp_path).unlink()

    def test_load_config_with_missing_file(self):
        """Test load_config raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_config("/nonexistent/path/sqlopt.yml")
        assert "Config file not found" in str(exc_info.value)

    def test_load_config_with_empty_file(self):
        """Test load_config uses defaults when file is empty."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            config = load_config(temp_path)
            # Should use defaults for all values
            assert config.config_version == "v1"
            assert config.project_root_path == "."
            assert config.scan_mapper_globs == ["src/main/resources/**/*.xml"]
            assert config.db_platform == "postgresql"
            assert config.db_dsn == ""
            assert config.llm_enabled is True
            assert config.llm_provider == "opencode_run"
            assert config.contracts_version == "current"
        finally:
            Path(temp_path).unlink()

    def test_load_config_with_partial_values(self):
        """Test load_config uses defaults for missing fields."""
        config_data = {
            "config_version": "v3",
            "project_root_path": "/partial/project",
            # Other fields omitted
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            config = load_config(temp_path)
            assert config.config_version == "v3"
            assert config.project_root_path == "/partial/project"
            # Other fields should use defaults
            assert config.scan_mapper_globs == ["src/main/resources/**/*.xml"]
            assert config.db_platform == "postgresql"
            assert config.db_dsn == ""
            assert config.llm_enabled is True
            assert config.llm_provider == "opencode_run"
            assert config.contracts_version == "current"
        finally:
            Path(temp_path).unlink()

    def test_load_config_with_invalid_yaml_structure(self):
        """Test load_config raises ValueError for non-dict YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("- item1\n- item2\n")
            temp_path = f.name

        try:
            with pytest.raises(ValueError) as exc_info:
                load_config(temp_path)
            assert "must contain a YAML mapping" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()

    def test_load_config_with_only_comments(self):
        """Test load_config handles YAML with only comments."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("# This is a comment\n# Another comment\n")
            temp_path = f.name

        try:
            config = load_config(temp_path)
            # Should use all defaults
            assert config.config_version == "v1"
            assert config.project_root_path == "."
        finally:
            Path(temp_path).unlink()
