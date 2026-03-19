"""Tests for Stage base class contract.

This module defines and tests the contract that all Stage implementations must follow.
"""

import pytest
from pathlib import Path
from typing import Any

from python.sqlopt.stages.base import Stage, StageContext, StageResult


class MockStage(Stage):
    """Mock Stage implementation for testing the contract."""

    name: str = "mock"
    version: str = "1.0.0"
    dependencies: list[str] = []

    def __init__(
        self,
        input_contracts: list[str] | None = None,
        output_contracts: list[str] | None = None,
        validate_result: bool = True,
        execute_success: bool = True,
        execute_errors: list[str] | None = None,
        execute_warnings: list[str] | None = None,
    ):
        self._input_contracts = input_contracts or []
        self._output_contracts = output_contracts or []
        self._validate_result = validate_result
        self._execute_success = execute_success
        self._execute_errors = execute_errors or []
        self._execute_warnings = execute_warnings or []

    def execute(self, context: StageContext) -> StageResult:
        return StageResult(
            success=self._execute_success,
            output_files=[],
            artifacts={},
            errors=self._execute_errors,
            warnings=self._execute_warnings,
        )

    def get_input_contracts(self) -> list[str]:
        return self._input_contracts

    def get_output_contracts(self) -> list[str]:
        return self._output_contracts

    def validate_input(self, context: StageContext) -> bool:
        return self._validate_result

    def cleanup(self, context: StageContext):
        # Track cleanup calls
        self._cleanup_called = True


class TestStageCannotBeInstantiated:
    """Test that Stage abstract class cannot be instantiated directly."""

    def test_stage_is_abstract_cannot_instantiate(self):
        """Stage cannot be instantiated directly - it's abstract."""
        with pytest.raises(TypeError) as exc_info:
            Stage()
        assert "abstract" in str(exc_info.value).lower()


class TestStageAbstractMethods:
    """Test that Stage subclasses must implement all abstract methods."""

    def test_subclass_without_execute_raises_error(self):
        """Subclass without execute() implementation raises TypeError on instantiation."""

        class IncompleteStage(Stage):
            name = "incomplete"

            def get_input_contracts(self) -> list[str]:
                return []

            def get_output_contracts(self) -> list[str]:
                return []

        with pytest.raises(TypeError) as exc_info:
            IncompleteStage()
        assert "abstract" in str(exc_info.value).lower()
        assert "execute" in str(exc_info.value)

    def test_subclass_without_get_input_contracts_raises_error(self):
        """Subclass without get_input_contracts() implementation raises TypeError on instantiation."""

        class IncompleteStage(Stage):
            name = "incomplete"

            def execute(self, context: StageContext) -> StageResult:
                return StageResult(success=True)

            def get_output_contracts(self) -> list[str]:
                return []

        with pytest.raises(TypeError) as exc_info:
            IncompleteStage()
        assert "abstract" in str(exc_info.value).lower()
        assert "get_input_contracts" in str(exc_info.value)

    def test_subclass_without_get_output_contracts_raises_error(self):
        """Subclass without get_output_contracts() implementation raises TypeError on instantiation."""

        class IncompleteStage(Stage):
            name = "incomplete"

            def execute(self, context: StageContext) -> StageResult:
                return StageResult(success=True)

            def get_input_contracts(self) -> list[str]:
                return []

        with pytest.raises(TypeError) as exc_info:
            IncompleteStage()
        assert "abstract" in str(exc_info.value).lower()
        assert "get_output_contracts" in str(exc_info.value)

    def test_subclass_with_all_abstract_methods_can_instantiate(self):
        """Subclass with all abstract methods implemented can be instantiated."""

        class CompleteStage(Stage):
            name = "complete"

            def execute(self, context: StageContext) -> StageResult:
                return StageResult(success=True)

            def get_input_contracts(self) -> list[str]:
                return []

            def get_output_contracts(self) -> list[str]:
                return []

        stage = CompleteStage()
        assert stage.name == "complete"


class TestStageExecute:
    """Test Stage.execute() method contract."""

    def test_execute_returns_stage_result(self):
        """execute() must return a StageResult instance."""
        stage = MockStage()
        context = StageContext(
            run_id="test_run",
            config={},
            data_dir=Path("/tmp/test"),
            cache_dir=Path("/tmp/cache"),
        )

        result = stage.execute(context)

        assert isinstance(result, StageResult)

    @pytest.mark.parametrize(
        "success,expected_success",
        [
            (True, True),
            (False, False),
        ],
    )
    def test_execute_success_field_reflects_outcome(
        self, success: bool, expected_success: bool
    ):
        """execute() StageResult.success reflects the execution outcome."""
        stage = MockStage(execute_success=success)
        context = StageContext(
            run_id="test_run",
            config={},
            data_dir=Path("/tmp/test"),
            cache_dir=Path("/tmp/cache"),
        )

        result = stage.execute(context)

        assert result.success == expected_success

    def test_execute_can_return_errors(self):
        """execute() can return errors in StageResult.errors."""
        errors = ["error1", "error2"]
        stage = MockStage(execute_success=False, execute_errors=errors)
        context = StageContext(
            run_id="test_run",
            config={},
            data_dir=Path("/tmp/test"),
            cache_dir=Path("/tmp/cache"),
        )

        result = stage.execute(context)

        assert result.errors == errors

    def test_execute_can_return_warnings(self):
        """execute() can return warnings in StageResult.warnings."""
        warnings = ["warning1", "warning2"]
        stage = MockStage(execute_warnings=warnings)
        context = StageContext(
            run_id="test_run",
            config={},
            data_dir=Path("/tmp/test"),
            cache_dir=Path("/tmp/cache"),
        )

        result = stage.execute(context)

        assert result.warnings == warnings


class TestStageInputOutputContracts:
    """Test Stage.get_input_contracts() and get_output_contracts() contract."""

    def test_get_input_contracts_returns_list(self):
        """get_input_contracts() must return a list."""
        stage = MockStage(input_contracts=["contract1", "contract2"])

        result = stage.get_input_contracts()

        assert isinstance(result, list)

    def test_get_output_contracts_returns_list(self):
        """get_output_contracts() must return a list."""
        stage = MockStage(output_contracts=["contract3", "contract4"])

        result = stage.get_output_contracts()

        assert isinstance(result, list)

    @pytest.mark.parametrize(
        "input_contracts",
        [
            [],
            ["contract1"],
            ["contract1", "contract2"],
            ["a", "b", "c"],
        ],
    )
    def test_get_input_contracts_various_values(self, input_contracts: list[str]):
        """get_input_contracts() returns the contracts provided during init."""
        stage = MockStage(input_contracts=input_contracts)

        result = stage.get_input_contracts()

        assert result == input_contracts

    @pytest.mark.parametrize(
        "output_contracts",
        [
            [],
            ["contract1"],
            ["contract1", "contract2"],
            ["x", "y", "z"],
        ],
    )
    def test_get_output_contracts_various_values(self, output_contracts: list[str]):
        """get_output_contracts() returns the contracts provided during init."""
        stage = MockStage(output_contracts=output_contracts)

        result = stage.get_output_contracts()

        assert result == output_contracts


class TestStageValidateInput:
    """Test Stage.validate_input() method contract."""

    def test_validate_input_returns_bool(self):
        """validate_input() must return a boolean."""
        stage = MockStage()

        context = StageContext(
            run_id="test_run",
            config={},
            data_dir=Path("/tmp/test"),
            cache_dir=Path("/tmp/cache"),
        )

        result = stage.validate_input(context)

        assert isinstance(result, bool)

    @pytest.mark.parametrize(
        "validate_result,expected",
        [
            (True, True),
            (False, False),
        ],
    )
    def test_validate_input_returns_provided_value(
        self, validate_result: bool, expected: bool
    ):
        """validate_input() returns the value set during init."""
        stage = MockStage(validate_result=validate_result)

        context = StageContext(
            run_id="test_run",
            config={},
            data_dir=Path("/tmp/test"),
            cache_dir=Path("/tmp/cache"),
        )

        result = stage.validate_input(context)

        assert result == expected


class TestStageCleanup:
    """Test Stage.cleanup() method contract."""

    def test_cleanup_does_not_raise(self):
        """cleanup() must not raise any exception."""
        stage = MockStage()

        context = StageContext(
            run_id="test_run",
            config={},
            data_dir=Path("/tmp/test"),
            cache_dir=Path("/tmp/cache"),
        )

        # Should not raise
        stage.cleanup(context)

    def test_cleanup_accepts_stage_context(self):
        """cleanup() accepts a StageContext parameter."""

        class CleanupTrackingStage(MockStage):
            def __init__(self):
                super().__init__()
                self.cleanup_called_with = None

            def cleanup(self, context: StageContext):
                self.cleanup_called_with = context

        stage = CleanupTrackingStage()
        context = StageContext(
            run_id="test_run",
            config={"key": "value"},
            data_dir=Path("/tmp/test"),
            cache_dir=Path("/tmp/cache"),
            metadata={"meta": "data"},
        )

        stage.cleanup(context)

        assert stage.cleanup_called_with is context


class TestStageContext:
    """Test StageContext dataclass."""

    def test_stage_context_has_required_fields(self):
        """StageContext must have run_id field."""
        context = StageContext(run_id="test_run")

        assert context.run_id == "test_run"

    def test_stage_context_has_optional_fields(self):
        """StageContext has optional fields with defaults."""
        context = StageContext(
            run_id="test_run",
            config={"key": "value"},
            data_dir=Path("/tmp/data"),
            cache_dir=Path("/tmp/cache"),
            metadata={"meta": "data"},
        )

        assert context.config == {"key": "value"}
        assert context.data_dir == Path("/tmp/data")
        assert context.cache_dir == Path("/tmp/cache")
        assert context.metadata == {"meta": "data"}

    def test_stage_context_get_method(self):
        """StageContext.get() returns metadata value or default."""
        context = StageContext(
            run_id="test_run",
            metadata={"key": "value"},
        )

        assert context.get("key") == "value"
        assert context.get("missing") is None
        assert context.get("missing", "default") == "default"

    def test_stage_context_set_method(self):
        """StageContext.set() sets metadata value."""
        context = StageContext(run_id="test_run")

        context.set("new_key", "new_value")

        assert context.get("new_key") == "new_value"


class TestStageResult:
    """Test StageResult dataclass."""

    def test_stage_result_has_required_fields(self):
        """StageResult must have success field."""
        result = StageResult(success=True)

        assert result.success is True

    def test_stage_result_has_optional_fields(self):
        """StageResult has optional fields with defaults."""
        result = StageResult(
            success=True,
            output_files=[Path("/tmp/out.txt")],
            artifacts={"key": "value"},
            errors=["error1"],
            warnings=["warning1"],
        )

        assert result.output_files == [Path("/tmp/out.txt")]
        assert result.artifacts == {"key": "value"}
        assert result.errors == ["error1"]
        assert result.warnings == ["warning1"]

    def test_stage_result_defaults(self):
        """StageResult optional fields have correct defaults."""
        result = StageResult(success=True)

        assert result.output_files == []
        assert result.artifacts == {}
        assert result.errors == []
        assert result.warnings == []


class TestStageClassAttributes:
    """Test Stage class attributes."""

    def test_stage_has_name_attribute(self):
        """Stage has a name class attribute."""
        assert hasattr(Stage, "name")

    def test_stage_has_version_attribute(self):
        """Stage has a version class attribute."""
        assert hasattr(Stage, "version")

    def test_stage_has_dependencies_attribute(self):
        """Stage has a dependencies class attribute."""
        assert hasattr(Stage, "dependencies")
        assert isinstance(Stage.dependencies, list)

    def test_mock_stage_can_override_attributes(self):
        """Mock stage can override class attributes."""

        class CustomStage(MockStage):
            name = "custom"
            version = "2.0.0"
            dependencies = ["dep1", "dep2"]

        stage = CustomStage()

        assert stage.name == "custom"
        assert stage.version == "2.0.0"
        assert stage.dependencies == ["dep1", "dep2"]
