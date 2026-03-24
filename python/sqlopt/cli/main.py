"""CLI entry point for SQL Optimizer."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import click
from sqlopt.common.config import SQLOptConfig, load_config
from sqlopt.stage_runner import StageRunner


@click.group()
def cli() -> None:
    """SQL Optimizer CLI - Analyze and optimize SQL queries."""


STAGE_ALIASES = {
    "1": "init",
    "2": "parse",
    "3": "recognition",
    "4": "optimize",
    "5": "result",
}


@click.command()
@click.argument("stage", default="init")
@click.option("--config", default="./sqlopt.yml", help="Config file path")
@click.option("--run-id", default=None, help="Run ID (defaults to latest if not specified)")
@click.option("--mock/--no-mock", default=False, help="Enable/disable mock data override")
def run(stage: str, config: str, run_id: str | None, mock: bool) -> None:
    """Run a pipeline stage.

    STAGE is the stage name to run (default: init).
    Valid stages: init, parse, recognition, optimize, result.
    Aliases: 1=init, 2=parse, 3=recognition, 4=optimize, 5=result.
    """
    stage = STAGE_ALIASES.get(stage, stage)

    click.echo(f"Loading config from: {config}")

    try:
        cfg: SQLOptConfig = load_config(config)
    except FileNotFoundError:
        click.echo(f"Error: Config file not found: {config}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"Error: Invalid config: {e}", err=True)
        sys.exit(1)

    click.echo(f"Config loaded: project_root={cfg.project_root_path}")

    auto_latest = run_id is None and stage != "init"
    runner = StageRunner(config, run_id=run_id, auto_latest=auto_latest)
    runner.paths.ensure_dirs()

    try:
        runner.run_stage(stage, use_mock=mock)
        click.echo(f"Stage '{stage}' completed successfully.")
        click.echo(f"Run ID: {runner.run_id}")
    except (ValueError, RuntimeError) as e:
        click.echo(f"Error: Stage '{stage}' failed: {e}", err=True)
        sys.exit(1)


MOCK_FILE_STAGE_MAP = {
    "sql_units.json": "init",
    "sql_units_with_branches.json": "parse",
    "baselines.json": "recognition",
    "proposals.json": "optimize",
    "report.json": "result",
}


@click.command()
@click.argument("run_id", required=False)
@click.option("--source", default=None, help="Source directory for mock templates")
def mock(run_id: str | None, source: str | None) -> None:
    """Copy mock data templates to a run's mock directory.

    RUN_ID is the run identifier. If not provided, lists available mock templates.

    Use --source to specify where to copy mock templates from.
    """
    template_mock_dir = Path(__file__).parent.parent.parent.parent / "templates" / "mock"

    if run_id is None:
        click.echo("Available mock templates:")
        if template_mock_dir.exists():
            for f in template_mock_dir.iterdir():
                stage = MOCK_FILE_STAGE_MAP.get(f.name, "unknown")
                click.echo(f"  - {f.name} (stage: {stage})")
        else:
            click.echo("  No mock templates found in templates/mock/")
        click.echo("\nUsage: sqlopt mock <run_id> [--source <path>]")
        return

    src = Path(source) if source else template_mock_dir

    if not src.exists():
        click.echo(f"Error: Source directory not found: {src}", err=True)
        sys.exit(1)

    count = 0
    for f in src.iterdir():
        if f.is_file():
            stage = MOCK_FILE_STAGE_MAP.get(f.name)
            if stage is None:
                click.echo(f"  Skipping {f.name} - unknown stage mapping")
                continue
            stage_mock_dir = Path("runs") / run_id / "mock" / stage
            stage_mock_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, stage_mock_dir / f.name)
            click.echo(f"  Copied {f.name} -> {stage_mock_dir / f.name}")
            count += 1

    if count == 0:
        click.echo("No files found to copy.")
    else:
        click.echo(f"\nCopied {count} mock file(s) to runs/{run_id}/mock/")
        click.echo("Run stages with --mock flag to use these mock files.")


cli.add_command(run)
cli.add_command(mock)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
