"""Parse stage - expands SQL branches from conditional logic."""

from sqlopt.contracts.parse import ParseOutput, SQLBranch, SQLUnitWithBranches
from sqlopt.stages.base import Stage


class ParseStage(Stage[None, ParseOutput]):
    """Parse stage: expands SQL branches from conditional logic.

    Input: None (stub - will be ParseInput later)
    Output: ParseOutput with SQL units and their branches
    """

    def __init__(self) -> None:
        """Initialize the parse stage."""
        super().__init__("parse")

    def run(self, _input_data: None = None) -> ParseOutput:
        """Execute parse stage.

        Args:
            input_data: None (stub - ParseInput not defined yet).

        Returns:
            ParseOutput with mock branches for development.
        """
        # Stub: create mock branches
        branch = SQLBranch(
            path_id="p1",
            condition=None,
            expanded_sql="SELECT * FROM users WHERE active = 1",
            is_valid=True,
        )
        unit_with_branches = SQLUnitWithBranches(
            sql_unit_id="stub-1",
            branches=[branch],
        )
        return ParseOutput(sql_units_with_branches=[unit_with_branches])
