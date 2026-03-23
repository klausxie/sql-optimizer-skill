"""Abstract base class for all pipeline stages."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

Input = TypeVar("Input")
Output = TypeVar("Output")


class Stage(ABC, Generic[Input, Output]):
    """Abstract base class for all pipeline stages.

    Type Parameters:
        Input: The input contract type for this stage.
        Output: The output contract type for this stage.

    Attributes:
        name: Stage name (e.g., 'init', 'parse').
    """

    def __init__(self, name: str) -> None:
        """Initialize the stage with a name.

        Args:
            name: Stage identifier (e.g., 'init', 'parse').
        """
        self.name = name

    @abstractmethod
    def run(self, input_data: Input) -> Output:
        """Execute the stage with given input.

        Args:
            input_data: Stage input contract.

        Returns:
            Stage output contract.
        """
        ...

    def validate_input(self, _input_data: Input) -> bool:
        """Validate input before running. Override for custom validation.

        Args:
            _input_data: Stage input contract to validate.

        Returns:
            True if input is valid, False otherwise.
        """
        return True

    def validate_output(self, _output: Output) -> bool:
        """Validate output after running. Override for custom validation.

        Args:
            _output: Stage output contract to validate.

        Returns:
            True if output is valid, False otherwise.
        """
        return True
