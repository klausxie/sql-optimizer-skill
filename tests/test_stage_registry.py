"""Tests for StageRegistry."""

import pytest

from python.sqlopt.application.stage_registry import StageRegistry, stage_registry
from sqlopt.stages.base import Stage, StageContext, StageResult


class SimpleTestStage(Stage):
    """A simple test stage implementation."""

    name = "simple"
    version = "1.0.0"
    dependencies = []

    def execute(self, context: StageContext) -> StageResult:
        return StageResult(success=True)

    def get_input_contracts(self) -> list[str]:
        return []

    def get_output_contracts(self) -> list[str]:
        return []


class DependentTestStage(Stage):
    """A test stage with dependencies."""

    name = "dependent"
    version = "1.0.0"
    dependencies = ["simple"]

    def execute(self, context: StageContext) -> StageResult:
        return StageResult(success=True)

    def get_input_contracts(self) -> list[str]:
        return []

    def get_output_contracts(self) -> list[str]:
        return []


class TestStageRegistrySingleton:
    """Test StageRegistry singleton behavior."""

    def test_get_instance_returns_singleton(self):
        """get_instance() returns the same instance on multiple calls."""
        instance1 = StageRegistry.get_instance()
        instance2 = StageRegistry.get_instance()
        assert instance1 is instance2

    def test_module_level_stage_registry_is_singleton(self):
        """The module-level stage_registry is the singleton instance."""
        instance = StageRegistry.get_instance()
        assert stage_registry is instance


class TestStageRegistryRegister:
    """Test StageRegistry.register()."""

    def test_register_with_name_attribute(self):
        """register() uses stage.name when no name provided."""
        registry = StageRegistry()
        result = registry.register(SimpleTestStage)
        assert result is SimpleTestStage
        assert "simple" in registry.list_stages()

    def test_register_with_explicit_name(self):
        """register() uses explicit name when provided."""
        registry = StageRegistry()
        result = registry.register(SimpleTestStage, name="custom_name")
        assert result is SimpleTestStage
        assert "custom_name" in registry.list_stages()
        assert "simple" not in registry.list_stages()

    def test_register_decorator_style(self):
        """register() works as a decorator."""
        registry = StageRegistry()

        @registry.register
        class DecoratedStage(Stage):
            name = "decorated"
            version = "1.0.0"
            dependencies = []

            def execute(self, context: StageContext) -> StageResult:
                return StageResult(success=True)

            def get_input_contracts(self) -> list[str]:
                return []

            def get_output_contracts(self) -> list[str]:
                return []

        assert "decorated" in registry.list_stages()

    def test_register_same_class_twice_is_noop(self):
        """Registering the same class twice returns the class without error."""
        registry = StageRegistry()
        result1 = registry.register(SimpleTestStage)
        result2 = registry.register(SimpleTestStage)
        assert result1 is result2
        assert len(registry.list_stages()) == 1

    def test_register_duplicate_name_raises_error(self):
        """Registering different classes with same name raises ValueError."""

        class AnotherStage(Stage):
            name = "simple"
            version = "1.0.0"
            dependencies = []

            def execute(self, context: StageContext) -> StageResult:
                return StageResult(success=True)

            def get_input_contracts(self) -> list[str]:
                return []

            def get_output_contracts(self) -> list[str]:
                return []

        registry = StageRegistry()
        registry.register(SimpleTestStage)
        with pytest.raises(ValueError) as exc_info:
            registry.register(AnotherStage)
        assert "already registered" in str(exc_info.value)

    def test_register_non_stage_raises_type_error(self):
        class NotAStage:
            pass

        registry = StageRegistry()
        with pytest.raises(TypeError) as exc_info:
            registry.register(NotAStage)  # type: ignore
        assert "must be a subclass of Stage" in str(exc_info.value)

    def test_register_inherits_name_from_base_class(self):
        """Stage subclass without explicit name uses parent name."""

        class NoNameOverrideStage(Stage):
            version = "1.0.0"
            dependencies = []

            def execute(self, context: StageContext) -> StageResult:
                return StageResult(success=True)

            def get_input_contracts(self) -> list[str]:
                return []

            def get_output_contracts(self) -> list[str]:
                return []

        registry = StageRegistry()
        registry.register(NoNameOverrideStage)
        assert "base" in registry.list_stages()


class TestStageRegistryGet:
    """Test StageRegistry.get()."""

    def test_get_returns_instance(self):
        """get() returns an instance of the registered stage."""
        registry = StageRegistry()
        registry.register(SimpleTestStage)
        instance = registry.get("simple")
        assert isinstance(instance, SimpleTestStage)

    def test_get_returns_same_instance(self):
        """get() returns the same instance on multiple calls (singleton)."""
        registry = StageRegistry()
        registry.register(SimpleTestStage)
        instance1 = registry.get("simple")
        instance2 = registry.get("simple")
        assert instance1 is instance2

    def test_get_unregistered_raises_key_error(self):
        """get() raises KeyError for unregistered stage."""
        registry = StageRegistry()
        with pytest.raises(KeyError) as exc_info:
            registry.get("nonexistent")
        assert "nonexistent" in str(exc_info.value)


class TestStageRegistryListStages:
    """Test StageRegistry.list_stages()."""

    def test_list_stages_returns_sorted_names(self):
        """list_stages() returns sorted list of registered stage names."""
        registry = StageRegistry()

        class StageZ(Stage):
            name = "z_stage"
            version = "1.0.0"
            dependencies = []

            def execute(self, context: StageContext) -> StageResult:
                return StageResult(success=True)

            def get_input_contracts(self) -> list[str]:
                return []

            def get_output_contracts(self) -> list[str]:
                return []

        class StageA(Stage):
            name = "a_stage"
            version = "1.0.0"
            dependencies = []

            def execute(self, context: StageContext) -> StageResult:
                return StageResult(success=True)

            def get_input_contracts(self) -> list[str]:
                return []

            def get_output_contracts(self) -> list[str]:
                return []

        registry.register(StageZ)
        registry.register(StageA)

        stages = registry.list_stages()
        assert stages == ["a_stage", "z_stage"]

    def test_list_stages_empty_for_empty_registry(self):
        """list_stages() returns empty list for empty registry."""
        registry = StageRegistry()
        assert registry.list_stages() == []


class TestStageRegistryGetDependencies:
    """Test StageRegistry.get_dependencies()."""

    def test_get_dependencies_returns_stage_dependencies(self):
        """get_dependencies() returns the stage's dependencies list."""
        registry = StageRegistry()
        registry.register(DependentTestStage)
        deps = registry.get_dependencies("dependent")
        assert deps == ["simple"]

    def test_get_dependencies_returns_copy(self):
        """get_dependencies() returns a copy, not the original list."""
        registry = StageRegistry()
        registry.register(DependentTestStage)
        deps1 = registry.get_dependencies("dependent")
        deps2 = registry.get_dependencies("dependent")
        deps1.append("modified")
        assert deps2 == ["simple"]

    def test_get_dependencies_unregistered_raises_key_error(self):
        """get_dependencies() raises KeyError for unregistered stage."""
        registry = StageRegistry()
        with pytest.raises(KeyError) as exc_info:
            registry.get_dependencies("nonexistent")
        assert "nonexistent" in str(exc_info.value)


class TestStageRegistryClear:
    """Test StageRegistry.clear()."""

    def test_clear_removes_all_stages(self):
        """clear() removes all registrations and instances."""
        registry = StageRegistry()
        registry.register(SimpleTestStage)
        registry.register(DependentTestStage)
        registry.get("simple")  # Ensure instance is created

        registry.clear()

        assert registry.list_stages() == []
        with pytest.raises(KeyError):
            registry.get("simple")

    def test_clear_allows_reregistration(self):
        """After clear(), new stages can be registered."""
        registry = StageRegistry()
        registry.register(SimpleTestStage)
        registry.clear()
        registry.register(DependentTestStage)

        assert registry.list_stages() == ["dependent"]


class TestStageRegistryIntegration:
    """Integration tests for StageRegistry."""

    def test_full_workflow(self):
        """Test complete workflow: register, get, list, get_dependencies."""
        registry = StageRegistry()

        registry.register(SimpleTestStage)
        registry.register(DependentTestStage)

        assert "simple" in registry.list_stages()
        assert "dependent" in registry.list_stages()

        simple_instance = registry.get("simple")
        assert isinstance(simple_instance, SimpleTestStage)

        dep_instance = registry.get("dependent")
        assert isinstance(dep_instance, DependentTestStage)

        assert simple_instance is registry.get("simple")
        assert dep_instance is registry.get("dependent")

        assert registry.get_dependencies("dependent") == ["simple"]
        assert registry.get_dependencies("simple") == []
