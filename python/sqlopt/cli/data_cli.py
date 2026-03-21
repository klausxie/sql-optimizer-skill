#!/usr/bin/env python3
"""
SQL Optimizer Data CLI - Data Management

Usage:
    sqlopt-data get <path> [--jsonpath <path>]
    sqlopt-data list <path>
    sqlopt-data set <path> <value>
    sqlopt-data diff <path-a> <path-b>
    sqlopt-data validate <path> [--schema <schema>]
    sqlopt-data prune <target> [--older-than <days>]
"""

import argparse
import json
import sys
from pathlib import Path


def resolve_path(path_str: str, project_root: Path = None) -> Path:
    """Resolve path with support for shortcuts like runs:, cache:, contracts:"""
    if project_root is None:
        cwd = Path.cwd()
        if cwd.name == "python":
            project_root = cwd.parent
        else:
            project_root = cwd

    path_str = path_str.strip()

    shortcuts = {
        "runs:": project_root / "runs",
        "cache:": project_root / "cache",
        "contracts:": project_root / "contracts",
    }

    for prefix, full_path in shortcuts.items():
        if path_str.startswith(prefix):
            resolved = path_str.replace(prefix, str(full_path), 1)
            return Path(resolved)

    return Path(path_str)


def main():
    parser = argparse.ArgumentParser(
        description="SQL Optimizer Data - Data Management CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # get command
    get_parser = subparsers.add_parser("get", help="Get data at path")
    get_parser.add_argument("path", help="Data path")
    get_parser.add_argument("--jsonpath", help="JSONPath filter")

    # list command
    list_parser = subparsers.add_parser("list", help="List data at path")
    list_parser.add_argument("path", help="Data path")
    list_parser.add_argument("--pattern", help="Filter pattern")
    list_parser.add_argument(
        "--format",
        choices=["json", "table", "csv"],
        default="json",
        help="Output format",
    )

    # set command
    set_parser = subparsers.add_parser("set", help="Set data at path")
    set_parser.add_argument("path", help="Data path")
    set_parser.add_argument("value", help="Value to set")

    # diff command
    diff_parser = subparsers.add_parser("diff", help="Compare two data paths")
    diff_parser.add_argument("path_a", help="First path")
    diff_parser.add_argument("path_b", help="Second path")

    # validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate data against schema"
    )
    validate_parser.add_argument("path", help="Data path")
    validate_parser.add_argument("--schema", help="Schema name")

    # prune command
    prune_parser = subparsers.add_parser("prune", help="Prune old data")
    prune_parser.add_argument("target", help="Target to prune")
    prune_parser.add_argument("--older-than", type=int, default=30, help="Days old")
    prune_parser.add_argument(
        "--keep-last", type=int, default=0, help="Keep last N runs"
    )
    prune_parser.add_argument(
        "--keep-phases",
        nargs="*",
        default=[],
        help="Keep runs in these phases (completed, failed, running)",
    )
    prune_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be pruned without actually pruning",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "get":
            return get_cmd(args)
        elif args.command == "list":
            return list_cmd(args)
        elif args.command == "set":
            return set_cmd(args)
        elif args.command == "diff":
            return diff_cmd(args)
        elif args.command == "validate":
            return validate_cmd(args)
        elif args.command == "prune":
            return prune_cmd(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def get_cmd(args):
    """Get data at path"""
    path = resolve_path(args.path)
    if not path.exists():
        print(f"Path not found: {args.path}")
        return 1

    if path.is_file():
        with open(path) as f:
            data = json.load(f)
    else:
        print(f"Path is a directory, use 'list' command")
        return 1

    if args.jsonpath:
        try:
            from jsonpath_ng import parse

            jp = parse(args.jsonpath)
            matches = jp.find(data)
            if matches:
                results = [m.value for m in matches]
                print(json.dumps(results if len(results) > 1 else results[0], indent=2))
            else:
                print("No matches found")
                return 1
        except Exception as e:
            print(f"JSONPath error: {e}")
            return 1
    else:
        print(json.dumps(data, indent=2))
    return 0


def list_cmd(args):
    """List data at path"""
    path = resolve_path(args.path)
    if not path.exists():
        print(f"Path not found: {args.path}")
        return 1

    if path.is_file():
        print(str(path))
        return 0

    pattern = args.pattern or "*"
    items = sorted(path.glob(pattern))
    output_format = getattr(args, "format", "json") or "json"

    if output_format == "json":
        for item in items:
            print(str(item))
    elif output_format == "table":
        try:
            from rich.console import Console
            from rich.table import Table

            console = Console()
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Path", style="cyan")
            table.add_column("Type", style="green")
            table.add_column("Size", justify="right")

            for item in items:
                item_type = "dir" if item.is_dir() else "file"
                size = str(item.stat().st_size) if item.is_file() else "-"
                table.add_row(str(item.relative_to(path.parent)), item_type, size)

            console.print(table)
        except ImportError:
            print("rich not installed, falling back to json")
            for item in items:
                print(str(item))
    elif output_format == "csv":
        print("path,type,size")
        for item in items:
            item_type = "dir" if item.is_dir() else "file"
            size = str(item.stat().st_size) if item.is_file() else ""
            print(f"{item},{item_type},{size}")

    return 0


def set_cmd(args):
    """Set data at path"""
    path = Path(args.path)
    path.parent.mkdir(parents=True, exist_ok=True)

    value = json.loads(args.value)
    with open(path, "w") as f:
        json.dump(value, f, indent=2)

    print(f"Set: {args.path}")
    return 0


def diff_cmd(args):
    """Compare two data paths"""
    import difflib

    path_a = Path(args.path_a)
    path_b = Path(args.path_b)

    if not path_a.exists() or not path_b.exists():
        print("Both paths must exist")
        return 1

    with open(path_a) as f:
        data_a = f.read()
    with open(path_b) as f:
        data_b = f.read()

    diff = difflib.unified_diff(
        data_a.splitlines(),
        data_b.splitlines(),
        fromfile=str(path_a),
        tofile=str(path_b),
        lineterm="",
    )

    for line in diff:
        print(line)

    return 0


def validate_cmd(args):
    """Validate data against schema"""
    path = resolve_path(args.path)
    if not path.exists():
        print(f"Path not found: {args.path}")
        return 1

    if path.is_file():
        with open(path) as f:
            data = json.load(f)
    else:
        print(f"Path is a directory, use 'list' command")
        return 1

    try:
        from sqlopt.contracts import ContractValidator, SCHEMA_MAP
        import sys
        from pathlib import Path as P

        repo_root = P(sys.argv[0]).parent.parent if sys.argv else P.cwd()
        validator = ContractValidator(repo_root)

        schema_name = args.schema
        if not schema_name:
            for name, filename in SCHEMA_MAP.items():
                if path.name.replace(".json", "") in filename.replace(
                    ".schema.json", ""
                ):
                    schema_name = name
                    break

        if not schema_name:
            print(f"Could not infer schema from path: {args.path}")
            print(f"Available schemas: {', '.join(SCHEMA_MAP.keys())}")
            print("Use --schema to specify")
            return 1

        validator.validate(schema_name, data)
        print(f"Validation: OK ({schema_name})")
        return 0

    except Exception as e:
        print(f"Validation failed: {e}")
        return 1


def prune_cmd(args):
    """Prune old data with smart retention policies"""
    import time

    target = resolve_path(args.target)
    if not target.exists():
        print(f"Target not found: {args.target}")
        return 1

    cutoff = time.time() - (args.older_than * 86400)
    removed = 0
    skipped = 0
    pruned_items = []

    keep_phases = set(args.keep_phases) if args.keep_phases else set()

    for item in target.iterdir():
        if not item.is_dir():
            continue

        if item.name == "runs":
            run_dirs = sorted(
                item.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True
            )

            runs_to_keep = set()

            if args.keep_last > 0:
                for run_dir in run_dirs[: args.keep_last]:
                    runs_to_keep.add(run_dir.name)

            if keep_phases:
                for run_dir in run_dirs:
                    state_file = run_dir / "supervisor" / "state.json"
                    if state_file.exists():
                        try:
                            import json

                            with open(state_file) as f:
                                state = json.load(f)
                                stage = state.get("current_stage", "")
                                if stage in keep_phases:
                                    runs_to_keep.add(run_dir.name)
                        except:
                            pass

            for run_dir in run_dirs:
                if run_dir.name in runs_to_keep:
                    skipped += 1
                    continue

                if run_dir.stat().st_mtime < cutoff:
                    if args.dry_run:
                        pruned_items.append(str(run_dir))
                    else:
                        import shutil

                        shutil.rmtree(run_dir)
                    removed += 1
        else:
            if item.stat().st_mtime < cutoff:
                if args.dry_run:
                    pruned_items.append(str(item))
                else:
                    item.unlink()
                removed += 1

    if args.dry_run:
        print(f"Would prune {removed} items:")
        for item in pruned_items[:10]:
            print(f"  - {item}")
        if len(pruned_items) > 10:
            print(f"  ... and {len(pruned_items) - 10} more")
        print(f"Would skip {skipped} items")
    else:
        print(f"Pruned {removed} items, skipped {skipped}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
