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


@click.command()
@click.argument("stage", default="init")
@click.option("--config", default="./sqlopt.yml", help="Config file path")
@click.option("--mock/--no-mock", default=True, help="Enable/disable mock data override")
def run(stage: str, config: str, mock: bool) -> None:
    """Run a pipeline stage.

    STAGE is the stage name to run (default: init).
    Valid stages: init, parse, recognition, optimize, result.
    """
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

    runner = StageRunner(config)
    runner.paths.ensure_dirs()

    try:
        runner.run_stage(stage, use_mock=mock)
        click.echo(f"Stage '{stage}' completed successfully.")
    except (ValueError, RuntimeError) as e:
        click.echo(f"Error: Stage '{stage}' failed: {e}", err=True)
        sys.exit(1)


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
                click.echo(f"  - {f.name}")
        else:
            click.echo("  No mock templates found in templates/mock/")
        click.echo("\nUsage: sqlopt mock <run_id> [--source <path>]")
        return

    run_mock_dir = Path("runs") / run_id / "mock"
    run_mock_dir.mkdir(parents=True, exist_ok=True)

    src = Path(source) if source else template_mock_dir

    if not src.exists():
        click.echo(f"Error: Source directory not found: {src}", err=True)
        sys.exit(1)

    count = 0
    for f in src.iterdir():
        if f.is_file():
            shutil.copy2(f, run_mock_dir / f.name)
            click.echo(f"  Copied {f.name} -> {run_mock_dir / f.name}")
            count += 1

    if count == 0:
        click.echo("No files found to copy.")
    else:
        click.echo(f"\nCopied {count} mock file(s) to {run_mock_dir}")
        click.echo("Run stages with --mock flag to use these mock files.")


cli.add_command(run)
cli.add_command(mock)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
