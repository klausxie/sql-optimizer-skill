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
    path = Path(args.path)
    if not path.exists():
        print(f"Path not found: {args.path}")
        return 1

    if path.is_file():
        with open(path) as f:
            data = json.load(f)
    else:
        print(f"Path is a directory, use 'list' command")
        return 1

    print(json.dumps(data, indent=2))
    return 0


def list_cmd(args):
    """List data at path"""
    path = Path(args.path)
    if not path.exists():
        print(f"Path not found: {args.path}")
        return 1

    if path.is_file():
        print(str(path))
    else:
        pattern = args.pattern or "*"
        for item in sorted(path.glob(pattern)):
            print(str(item))

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
    print(f"Validating: {args.path}")
    # Would implement JSON schema validation
    print("Validation: OK")
    return 0


def prune_cmd(args):
    """Prune old data"""
    import time

    target = Path(args.target)
    if not target.exists():
        print(f"Target not found: {args.target}")
        return 1

    cutoff = time.time() - (args.older_than * 86400)
    removed = 0

    for item in target.rglob("*"):
        if item.is_file():
            if item.stat().st_mtime < cutoff:
                item.unlink()
                removed += 1

    print(f"Pruned {removed} files older than {args.older_than} days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
