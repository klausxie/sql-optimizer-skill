"""Init stage - extracts SQL units from mapper files."""

from __future__ import annotations

from pathlib import Path

from sqlopt.contracts.init import InitOutput, SQLUnit
from sqlopt.stages.base import Stage


class InitStage(Stage[None, InitOutput]):
    """Init stage: extracts SQL units from MyBatis mapper files.

    Input: None (stub - will be InitInput later)
    Output: InitOutput with list of SQLUnits
    """

    def __init__(self) -> None:
        super().__init__("init")

    def run(self, _input_data: None = None) -> InitOutput:
        """Execute init stage.

        Args:
            _input_data: None (stub - InitInput not defined yet).

        Returns:
            InitOutput with mock SQL units for development.
        """
        # Stub: create mock SQL unit
        unit = SQLUnit(
            id="stub-1",
            mapper_file="UserMapper.xml",
            sql_id="findUser",
            sql_text="SELECT * FROM users WHERE id = #{id}",
            statement_type="SELECT",
        )
        output = InitOutput(sql_units=[unit], run_id="stub-run")

        # Write output to runs directory
        self._write_output(output)

        return output

    def _write_output(self, output: InitOutput) -> None:
        output_dir = Path("runs") / output.run_id / "init"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "sql_units.json"
        output_file.write_text(output.to_json())
