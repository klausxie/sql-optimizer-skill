"""Result stage - generates optimization reports and patches."""

from pathlib import Path

from sqlopt.contracts.result import Patch, Report, ResultOutput
from sqlopt.stages.base import Stage


class ResultStage(Stage[None, ResultOutput]):
    """Result stage: generates optimization reports and patches.

    Input: None (stub - will be ResultInput later)
    Output: ResultOutput with report and patches
    """

    def __init__(self) -> None:
        """Initialize the result stage."""
        super().__init__("result")

    def run(self, _input_data: None = None) -> ResultOutput:
        """Execute result stage.

        Args:
            input_data: None (stub - ResultInput not defined yet).

        Returns:
            ResultOutput with mock report and patches for development.
        """
        # Stub: create mock report
        report = Report(
            summary="Optimization analysis complete",
            details="Found 1 optimization opportunity",
            risks=["Low risk"],
            recommendations=["Consider adding index on user_id"],
        )
        patch = Patch(
            sql_unit_id="stub-1",
            original_xml='<select id="findUser">SELECT * FROM users</select>',
            patched_xml='<select id="findUser">SELECT id, name FROM users</select>',
            diff="--- old\n+++ new\n-SELECT *\n+SELECT id, name",
        )
        output = ResultOutput(
            can_patch=True,
            report=report,
            patches=[patch],
        )

        # Write output to runs directory
        self._write_output(output)

        return output

    def _write_output(self, output: ResultOutput) -> None:
        """Write stage output to runs directory.

        Args:
            output: The result stage output to persist.
        """
        output_dir = Path("runs") / "stub-run" / "result"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "result.json"
        output_file.write_text(output.to_json())
