"""Branch context for tracking branch generation state.

This module provides the BranchContext class which tracks the current
state during branch generation, including which conditions are active
and the current branch path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BranchContext:
    """Context for tracking branch generation state.

    This class maintains the current state during branch generation,
    including:
    - The current branch ID and path
    - Active conditions for the current branch
    - All conditions encountered so far
    - Configuration options
    """

    branch_id: int = 0
    """Unique identifier for the current branch."""

    active_conditions: list[str] = field(default_factory=list)
    """List of conditions that evaluate to TRUE in this branch."""

    all_conditions: list[str] = field(default_factory=list)
    """All conditions collected from if/when nodes in the SQL."""

    bindings: dict[str, Any] = field(default_factory=dict)
    """Variable bindings for ${} placeholder substitution."""

    current_path: list[str] = field(default_factory=list)
    """The path of nodes traversed to reach current position."""

    def __post_init__(self) -> None:
        """Ensure lists are properly initialized."""
        if self.active_conditions is None:
            self.active_conditions = []
        if self.all_conditions is None:
            self.all_conditions = []
        if self.bindings is None:
            self.bindings = {}
        if self.current_path is None:
            self.current_path = []

    def add_condition(self, condition: str) -> None:
        """Add a condition to the all_conditions list.

        Args:
            condition: The OGNL expression string to add.
        """
        if condition and condition not in self.all_conditions:
            self.all_conditions.append(condition)

    def activate_condition(self, condition: str) -> None:
        """Mark a condition as active (TRUE) for current branch.

        Args:
            condition: The condition to activate.
        """
        if condition and condition not in self.active_conditions:
            self.active_conditions.append(condition)
            self.add_condition(condition)

    def deactivate_condition(self, condition: str) -> None:
        """Mark a condition as inactive (FALSE) for current branch.

        Args:
            condition: The condition to deactivate.
        """
        if condition in self.active_conditions:
            self.active_conditions.remove(condition)

    def is_condition_active(self, condition: str) -> bool:
        """Check if a condition is active.

        Args:
            condition: The condition to check.

        Returns:
            True if the condition is in the active list.
        """
        return condition in self.active_conditions

    def push_path(self, node_type: str, node_id: str = "") -> None:
        """Push a node onto the current path.

        Args:
            node_type: Type of node (e.g., 'if', 'choose', 'foreach').
            node_id: Optional identifier for the node.
        """
        path_entry = f"{node_type}"
        if node_id:
            path_entry += f":{node_id}"
        self.current_path.append(path_entry)

    def pop_path(self) -> str | None:
        """Pop the last path entry.

        Returns:
            The popped path entry, or None if path is empty.
        """
        if self.current_path:
            return self.current_path.pop()
        return None

    def get_path_string(self) -> str:
        """Get the current path as a string.

        Returns:
            Path string like 'root > choose > when:1'
        """
        if not self.current_path:
            return "root"
        return " > ".join(self.current_path)

    def bind(self, name: str, value: Any) -> None:
        """Bind a variable for ${} placeholder substitution.

        Args:
            name: Variable name.
            value: Value to bind.
        """
        self.bindings[name] = value

    def get_binding(self, name: str) -> Any:
        """Get a bound variable value.

        Args:
            name: Variable name.

        Returns:
            The bound value, or None if not found.
        """
        return self.bindings.get(name)

    def copy(self) -> BranchContext:
        """Create a deep copy of this context.

        Returns:
            A new BranchContext with the same state.
        """
        return BranchContext(
            branch_id=self.branch_id,
            active_conditions=self.active_conditions.copy(),
            all_conditions=self.all_conditions.copy(),
            bindings=self.bindings.copy(),
            current_path=self.current_path.copy(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for serialization.

        Returns:
            Dictionary representation of the context.
        """
        return {
            "branch_id": self.branch_id,
            "active_conditions": self.active_conditions,
            "all_conditions": self.all_conditions,
            "bindings": self.bindings,
            "path": self.get_path_string(),
        }
