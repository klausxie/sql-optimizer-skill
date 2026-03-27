"""CLI entry point for SQL Optimizer."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess  # noqa: S404
import sys
from pathlib import Path

import click
from sqlopt.common.config import SQLOptConfig, load_config
from sqlopt.common.run_paths import RunPaths
from sqlopt.stage_runner import StageRunner

GIT_CMD = shutil.which("git") or "git"

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    force=True,
)


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
            stage_mock_dir = RunPaths(run_id).mock_stage_dir(stage)
            stage_mock_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, stage_mock_dir / f.name)
            click.echo(f"  Copied {f.name} -> {stage_mock_dir / f.name}")
            count += 1

    if count == 0:
        click.echo("No files found to copy.")
    else:
        click.echo(f"\nCopied {count} mock file(s) to runs/{run_id}/mock/")
        click.echo("Run stages with --mock flag to use these mock files.")


@click.command("apply")
@click.argument("unit_id")
@click.option("--run-id", required=True, help="Run ID")
@click.option("--dry-run", is_flag=True, help="Preview without applying")
def apply(unit_id: str, run_id: str, dry_run: bool) -> None:
    """Apply a patch to a mapper XML file using git apply."""
    paths = RunPaths(run_id)
    patch_file = paths.result_unit_patch(unit_id)
    meta_file = paths.result_unit_meta(unit_id)

    if not patch_file.exists():
        click.echo(f"Error: Patch file not found: {patch_file}", err=True)
        sys.exit(1)

    if not meta_file.exists():
        click.echo(f"Error: Meta file not found: {meta_file}", err=True)
        sys.exit(1)

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    mapper_file = meta.get("mapper_file", "")
    click.echo(f"Patch: {unit_id}")
    click.echo(f"Mapper: {mapper_file}")

    result = subprocess.run(  # noqa: S603
        [GIT_CMD, "apply", "--verbose", "--check", patch_file],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        click.echo(f"Error: Patch validation failed:\n{result.stderr}", err=True)
        sys.exit(1)
    click.echo("Patch validation passed.")

    if dry_run:
        click.echo("\n--- Dry Run - Patch Preview ---")
        click.echo(patch_file.read_text(encoding="utf-8"))
        click.echo("--- End Preview ---")
        return

    subprocess.run([GIT_CMD, "stash"], capture_output=True)  # noqa: S603
    result = subprocess.run([GIT_CMD, "apply", patch_file], capture_output=True, text=True)  # noqa: S603
    if result.returncode != 0:
        click.echo(f"Error: Failed to apply patch:\n{result.stderr}", err=True)
        subprocess.run([GIT_CMD, "stash", "pop"], capture_output=True)  # noqa: S603
        sys.exit(1)

    click.echo(f"Patch applied successfully to: {mapper_file}")
    click.echo("Run `git stash drop` to remove backup or `git stash pop` to restore original.")


@click.command("diff")
@click.argument("unit_id")
@click.option("--run-id", required=True, help="Run ID")
def diff(unit_id: str, run_id: str) -> None:
    """Display the patch diff for a unit."""
    paths = RunPaths(run_id)
    patch_file = paths.result_unit_patch(unit_id)

    if not patch_file.exists():
        click.echo(f"Error: Patch file not found: {patch_file}", err=True)
        sys.exit(1)

    click.echo(patch_file.read_text(encoding="utf-8"))


@click.command("patches")
@click.option("--run-id", required=True, help="Run ID")
def patches(run_id: str) -> None:
    """List all available patches."""
    paths = RunPaths(run_id)
    index_file = paths.result_units_index

    if not index_file.exists():
        click.echo(f"Error: No patches found for run {run_id}", err=True)
        sys.exit(1)

    index_data = json.loads(index_file.read_text(encoding="utf-8"))
    unit_ids = index_data.get("units", [])

    if not unit_ids:
        click.echo("No patches available.")
        return

    click.echo(f"Patches for run {run_id}:\n")
    click.echo(f"{'Unit ID':<25} {'SQL ID':<20} {'Confidence':<12} {'Rationale'}")
    click.echo("-" * 100)

    for unit_id in unit_ids:
        meta_file = paths.result_unit_meta(unit_id)
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            sql_id = meta.get("sql_id", "N/A")
            confidence = meta.get("confidence", 0.0)
            rationale = meta.get("rationale", "N/A")
            click.echo(f"{unit_id:<25} {sql_id:<20} {confidence:<12.2f} {rationale[:50]}")


cli.add_command(run)
cli.add_command(mock)
cli.add_command(apply)
cli.add_command(diff)
cli.add_command(patches)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
