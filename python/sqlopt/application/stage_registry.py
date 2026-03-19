"""Stage registry for managing SQL Optimizer stages.

This module provides a singleton registry for stage classes, allowing
decorator-based registration and lazy instantiation of stage instances.

Usage:
    from sqlopt.application.stage_registry import stage_registry

    # Register a stage class
    @stage_registry.register
    class MyStage(Stage):
        name = "my_stage"
        dependencies = []

        def execute(self, context: StageContext) -> StageResult:
            ...

        def get_input_contracts(self) -> list[str]:
            return []

        def get_output_contracts(self) -> list[str]:
            return []

    # Get a stage instance
    stage = stage_registry.get("my_stage")

    # List all registered stages
    all_stages = stage_registry.list_stages()
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlopt.stages.base import Stage


class StageRegistry:
    """Singleton registry for managing stage classes and instances.

    The registry supports:
    - Decorator-based registration via @StageRegistry.register
    - Lazy instantiation (each stage is created only once)
    - Dependency tracking via stage.dependencies
    """

    _instance: "StageRegistry | None" = None

    def __init__(self):
        """Initialize the registry (use get_instance() instead)."""
        self._stage_classes: dict[str, type["Stage"]] = {}
        self._stage_instances: dict[str, "Stage"] = {}

    @classmethod
    def get_instance(cls) -> "StageRegistry":
        """Get the singleton instance of StageRegistry.

        Returns:
            StageRegistry: The singleton instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(
        self, stage_class: type["Stage"], name: str | None = None
    ) -> type["Stage"]:
        """Register a stage class.

        Can be used as a decorator or called directly.

        Args:
            stage_class: The stage class to register
            name: Optional name override. If not provided, uses stage_class.name

        Returns:
            The stage class (for decorator usage)

        Raises:
            ValueError: If a stage with the same name is already registered
            TypeError: If stage_class is not a valid Stage subclass
        """
        from sqlopt.stages.base import Stage as StageBase

        # Validate that it's a Stage subclass
        if not issubclass(stage_class, StageBase):
            raise TypeError(
                f"Cannot register {stage_class.__name__}: must be a subclass of Stage"
            )

        # Determine the stage name
        stage_name = name if name is not None else getattr(stage_class, "name", None)
        if stage_name is None:
            raise ValueError(
                f"Cannot register {stage_class.__name__}: stage must have a 'name' attribute "
                "or a name must be provided"
            )

        # Check for duplicate registration
        if stage_name in self._stage_classes:
            existing = self._stage_classes[stage_name]
            if existing is not stage_class:
                raise ValueError(
                    f"Cannot register {stage_class.__name__}: a stage named "
                    f"'{stage_name}' is already registered"
                )
            # Same class re-registered, no-op
            return stage_class

        self._stage_classes[stage_name] = stage_class
        return stage_class

    def get(self, name: str) -> "Stage":
        """Get a stage instance by name.

        The stage is instantiated lazily and cached (singleton per name).

        Args:
            name: The stage name

        Returns:
            The stage instance

        Raises:
            KeyError: If no stage with the given name is registered
        """
        if name not in self._stage_classes:
            raise KeyError(f"No stage registered with name '{name}'")

        if name not in self._stage_instances:
            stage_class = self._stage_classes[name]
            self._stage_instances[name] = stage_class()

        return self._stage_instances[name]

    def list_stages(self) -> list[str]:
        """List all registered stage names.

        Returns:
            Sorted list of stage names
        """
        return sorted(self._stage_classes.keys())

    def get_dependencies(self, name: str) -> list[str]:
        """Get the dependencies of a stage.

        Args:
            name: The stage name

        Returns:
            List of dependency stage names

        Raises:
            KeyError: If no stage with the given name is registered
        """
        if name not in self._stage_classes:
            raise KeyError(f"No stage registered with name '{name}'")

        stage_class = self._stage_classes[name]
        return list(getattr(stage_class, "dependencies", []))[:]  # Return a copy

    def clear(self) -> None:
        """Clear all registrations and instances.

        This is primarily useful for testing.

        Returns:
            None
        """
        self._stage_classes.clear()
        self._stage_instances.clear()


# Global singleton instance for convenience
stage_registry = StageRegistry.get_instance()
