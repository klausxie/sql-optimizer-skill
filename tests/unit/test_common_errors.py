"""Tests for error hierarchy."""

import pytest
from sqlopt.common.errors import (
    ConfigError,
    ContractError,
    DBError,
    LLMError,
    SQLOptError,
    StageError,
)


class TestSQLOptErrorBasics:
    """Test basic SQLOptError functionality."""

    def test_base_error_has_message(self):
        """Test that SQLOptError stores message correctly."""
        err = SQLOptError("test error message")
        assert err.message == "test error message"
        assert str(err) == "test error message"

    def test_base_error_has_empty_details_by_default(self):
        """Test that SQLOptError has empty details by default."""
        err = SQLOptError("test error")
        assert err.details == {}

    def test_base_error_with_details(self):
        """Test that SQLOptError accepts details dict."""
        err = SQLOptError("test error", details={"key": "value"})
        assert err.details == {"key": "value"}

    def test_base_error_to_dict(self):
        """Test that SQLOptError serializes to dict correctly."""
        err = SQLOptError("test error", details={"extra": "info"})
        result = err.to_dict()
        assert result["error"] == "SQLOptError"
        assert result["message"] == "test error"
        assert result["details"] == {"extra": "info"}

    def test_base_error_inherits_from_exception(self):
        """Test that SQLOptError inherits from Exception."""
        err = SQLOptError("base error")
        assert isinstance(err, Exception)


class TestErrorHierarchy:
    """Test error class hierarchy."""

    def test_config_error_inherits_from_sqlopt_error(self):
        """Test ConfigError inherits from SQLOptError."""
        err = ConfigError("config issue")
        assert isinstance(err, SQLOptError)
        assert isinstance(err, Exception)

    def test_stage_error_inherits_from_sqlopt_error(self):
        """Test StageError inherits from SQLOptError."""
        err = StageError("stage issue")
        assert isinstance(err, SQLOptError)
        assert isinstance(err, Exception)

    def test_contract_error_inherits_from_sqlopt_error(self):
        """Test ContractError inherits from SQLOptError."""
        err = ContractError("contract issue")
        assert isinstance(err, SQLOptError)
        assert isinstance(err, Exception)

    def test_llm_error_inherits_from_sqlopt_error(self):
        """Test LLMError inherits from SQLOptError."""
        err = LLMError("llm issue")
        assert isinstance(err, SQLOptError)
        assert isinstance(err, Exception)

    def test_db_error_inherits_from_sqlopt_error(self):
        """Test DBError inherits from SQLOptError."""
        err = DBError("db issue")
        assert isinstance(err, SQLOptError)
        assert isinstance(err, Exception)


class TestErrorToDict:
    """Test to_dict method on each error type."""

    def test_config_error_to_dict(self):
        """Test ConfigError to_dict returns correct error type name."""
        err = ConfigError("config problem", details={"field": "db_dsn"})
        result = err.to_dict()
        assert result["error"] == "ConfigError"
        assert result["message"] == "config problem"
        assert result["details"] == {"field": "db_dsn"}

    def test_stage_error_to_dict(self):
        """Test StageError to_dict returns correct error type name."""
        err = StageError("stage failed", details={"stage": "optimize"})
        result = err.to_dict()
        assert result["error"] == "StageError"
        assert result["message"] == "stage failed"
        assert result["details"] == {"stage": "optimize"}

    def test_contract_error_to_dict(self):
        """Test ContractError to_dict returns correct error type name."""
        err = ContractError("contract violated", details={"rule": "unique_key"})
        result = err.to_dict()
        assert result["error"] == "ContractError"
        assert result["message"] == "contract violated"
        assert result["details"] == {"rule": "unique_key"}

    def test_llm_error_to_dict(self):
        """Test LLMError to_dict returns correct error type name."""
        err = LLMError("llm unavailable", details={"provider": "openai"})
        result = err.to_dict()
        assert result["error"] == "LLMError"
        assert result["message"] == "llm unavailable"
        assert result["details"] == {"provider": "openai"}

    def test_db_error_to_dict(self):
        """Test DBError to_dict returns correct error type name."""
        err = DBError("connection failed", details={"host": "localhost"})
        result = err.to_dict()
        assert result["error"] == "DBError"
        assert result["message"] == "connection failed"
        assert result["details"] == {"host": "localhost"}


class TestErrorCanBeRaisedAndCaught:
    """Test that all errors can be raised and caught properly."""

    def test_raise_and_catch_sqlopt_error(self):
        """Test SQLOptError can be raised and caught."""
        with pytest.raises(SQLOptError) as exc_info:
            raise SQLOptError("base error occurred")
        assert exc_info.value.message == "base error occurred"

    def test_raise_and_catch_config_error(self):
        """Test ConfigError can be raised and caught."""
        with pytest.raises(ConfigError) as exc_info:
            raise ConfigError("config invalid")
        assert exc_info.value.message == "config invalid"

    def test_raise_and_catch_stage_error(self):
        """Test StageError can be raised and caught."""
        with pytest.raises(StageError) as exc_info:
            raise StageError("stage failed")
        assert exc_info.value.message == "stage failed"

    def test_raise_and_catch_contract_error(self):
        """Test ContractError can be raised and caught."""
        with pytest.raises(ContractError) as exc_info:
            raise ContractError("contract violated")
        assert exc_info.value.message == "contract violated"

    def test_raise_and_catch_llm_error(self):
        """Test LLMError can be raised and caught."""
        with pytest.raises(LLMError) as exc_info:
            raise LLMError("llm error")
        assert exc_info.value.message == "llm error"

    def test_raise_and_catch_db_error(self):
        """Test DBError can be raised and caught."""
        with pytest.raises(DBError) as exc_info:
            raise DBError("db error")
        assert exc_info.value.message == "db error"

    def test_catching_base_error_catches_all_subclasses(self):
        """Test that catching SQLOptError also catches all subclasses."""
        for error_class, msg in [
            (ConfigError, "config error"),
            (StageError, "stage error"),
            (ContractError, "contract error"),
            (LLMError, "llm error"),
            (DBError, "db error"),
        ]:
            with pytest.raises(SQLOptError) as exc_info:
                raise error_class(msg)
            assert exc_info.value.message == msg
