"""CLI entry point for SQL Optimizer."""

import sys

import click
from sqlopt.common.config import SQLOptConfig, load_config
from sqlopt.stage_runner import StageRunner


@click.group()
def cli() -> None:
    """SQL Optimizer CLI - Analyze and optimize SQL queries."""


@click.command()
@click.argument("stage", default="init")
@click.option("--config", default="./sqlopt.yml", help="Config file path")
def run(stage: str, config: str) -> None:
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
        runner.run_stage(stage)
        click.echo(f"Stage '{stage}' completed successfully.")
    except (ValueError, RuntimeError) as e:
        click.echo(f"Error: Stage '{stage}' failed: {e}", err=True)
        sys.exit(1)


cli.add_command(run)


if __name__ == "__main__":
    cli()
