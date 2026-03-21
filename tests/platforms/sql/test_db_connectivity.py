"""Tests for db_connectivity module."""
import pytest
from unittest.mock import patch, MagicMock

from sqlopt.platforms.sql.db_connectivity import (
    check_db_connectivity,
    _check_mysql_connectivity,
    _check_postgresql_connectivity,
    _transform_result,
)


class TestCheckDbConnectivity:
    """Tests for check_db_connectivity function."""

    def test_returns_correct_structure_for_unsupported_platform(self):
        """Test returns proper structure for unsupported platform."""
        config = {"db": {"platform": "oracle", "dsn": "oracle://..."}}
        result = check_db_connectivity(config)

        assert isinstance(result, dict)
        assert "ok" in result
        assert "error" in result
        assert "driver" in result
        assert "db_version" in result
        assert result["ok"] is False
        assert "unsupported platform" in result["error"]
        assert result["driver"] is None
        assert result["db_version"] is None

    def test_handles_empty_platform(self):
        """Test graceful handling of empty platform."""
        config = {"db": {"platform": "", "dsn": "..."}}
        result = check_db_connectivity(config)

        assert result["ok"] is False
        assert "unsupported platform" in result["error"]

    def test_handles_missing_db_config(self):
        """Test graceful handling when db config is missing."""
        config = {}
        result = check_db_connectivity(config)

        assert result["ok"] is False
        assert "unsupported platform" in result["error"]

    def test_handles_none_db_config(self):
        """Test graceful handling when db config is None."""
        config = {"db": None}
        result = check_db_connectivity(config)

        assert result["ok"] is False


class TestCheckMysqlConnectivity:
    """Tests for _check_mysql_connectivity function."""

    @patch("sqlopt.platforms.sql.db_connectivity._transform_result")
    @patch("sqlopt.platforms.mysql.evidence.check_db_connectivity")
    def test_returns_transformed_result(self, mock_mysql_check, mock_transform):
        """Test mysql connectivity check returns transformed result."""
        mock_mysql_check.return_value = {"ok": True, "driver": "mysql"}
        mock_transform.return_value = {"ok": True, "driver": "mysql", "error": None, "db_version": "8.0"}

        config = {"db": {"platform": "mysql", "dsn": "..."}}
        result = _check_mysql_connectivity(config)

        mock_mysql_check.assert_called_once_with(config)
        mock_transform.assert_called_once()
        assert result["ok"] is True

    @patch("sqlopt.platforms.mysql.evidence.check_db_connectivity")
    def test_handles_missing_driver(self, mock_mysql_check):
        """Test graceful handling when mysql driver not installed."""
        mock_mysql_check.side_effect = ImportError("No module named 'mysql'")

        config = {"db": {"platform": "mysql", "dsn": "..."}}
        result = _check_mysql_connectivity(config)

        assert result["ok"] is False
        assert "mysql driver not installed" in result["error"]
        assert result["driver"] is None
        assert result["db_version"] is None


class TestCheckPostgresqlConnectivity:
    """Tests for _check_postgresql_connectivity function."""

    @patch("sqlopt.platforms.sql.db_connectivity._transform_result")
    @patch("sqlopt.platforms.postgresql.evidence.check_db_connectivity")
    def test_returns_transformed_result(self, mock_pg_check, mock_transform):
        """Test postgresql connectivity check returns transformed result."""
        mock_pg_check.return_value = {"ok": True, "driver": "postgresql"}
        mock_transform.return_value = {"ok": True, "driver": "postgresql", "error": None, "db_version": "14.0"}

        config = {"db": {"platform": "postgresql", "dsn": "..."}}
        result = _check_postgresql_connectivity(config)

        mock_pg_check.assert_called_once_with(config)
        mock_transform.assert_called_once()
        assert result["ok"] is True

    @patch("sqlopt.platforms.postgresql.evidence.check_db_connectivity")
    def test_handles_missing_driver(self, mock_pg_check):
        """Test graceful handling when postgresql driver not installed."""
        mock_pg_check.side_effect = ImportError("No module named 'psycopg'")

        config = {"db": {"platform": "postgresql", "dsn": "..."}}
        result = _check_postgresql_connectivity(config)

        assert result["ok"] is False
        assert "postgresql driver not installed" in result["error"]
        assert result["driver"] is None
        assert result["db_version"] is None


class TestTransformResult:
    """Tests for _transform_result function."""

    def test_extracts_version_field(self):
        """Test db_version extraction from version field."""
        result = _transform_result({"ok": True, "error": None, "driver": "mysql", "version": "8.0.32"})

        assert result["ok"] is True
        assert result["db_version"] == "8.0.32"

    def test_uses_existing_db_version(self):
        """Test db_version uses existing field when available."""
        result = _transform_result({"ok": True, "error": None, "driver": "pg", "db_version": "14.1", "version": "fallback"})

        assert result["db_version"] == "14.1"

    def test_handles_missing_version(self):
        """Test handles missing version gracefully."""
        result = _transform_result({"ok": False, "error": "connection failed", "driver": None})

        assert result["db_version"] is None
        assert result["error"] == "connection failed"
