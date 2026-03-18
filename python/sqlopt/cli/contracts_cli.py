#!/usr/bin/env python3
"""
SQL Optimizer Contracts CLI - Version Management

Usage:
    sqlopt-cli contracts version
    sqlopt-cli contracts diff --from v1.0.0 --to v1.1.0
    sqlopt-cli contracts publish --version v1.1.0 --changes "..."
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


def get_contracts_dir() -> Path:
    candidates = [
        Path.cwd() / "contracts",
        Path(__file__).resolve().parents[2] / "contracts",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def main():
    parser = argparse.ArgumentParser(
        description="SQL Optimizer Contracts - Version Management CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    version_parser = subparsers.add_parser("version", help="Show current version")

    diff_parser = subparsers.add_parser("diff", help="Compare two versions")
    diff_parser.add_argument(
        "--from", dest="from_ver", required=True, help="From version"
    )
    diff_parser.add_argument("--to", dest="to_ver", required=True, help="To version")

    publish_parser = subparsers.add_parser("publish", help="Publish new version")
    publish_parser.add_argument("--version", required=True, help="Version to publish")
    publish_parser.add_argument("--changes", required=True, help="Change description")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "version":
            return version_cmd(args)
        elif args.command == "diff":
            return diff_cmd(args)
        elif args.command == "publish":
            return publish_cmd(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def version_cmd(args):
    contracts_dir = get_contracts_dir()
    versions_file = contracts_dir / "versions.json"

    if not versions_file.exists():
        print("No versions.json found")
        return 1

    with open(versions_file) as f:
        versions = json.load(f)

    print(f"Current version: {versions.get('version', 'unknown')}")
    print(f"Schema version: {versions.get('schema_version', 'unknown')}")
    print(f"Created at: {versions.get('created_at', 'unknown')}")
    print(f"\nSchemas ({len(versions.get('schemas', []))}):")
    for schema in versions.get("schemas", []):
        print(f"  - {schema}")

    return 0


def diff_cmd(args):
    contracts_dir = get_contracts_dir()
    snapshots_dir = contracts_dir / "snapshots"

    from_dir = snapshots_dir / args.from_ver
    to_dir = snapshots_dir / args.to_ver

    if not from_dir.exists():
        print(f"Version {args.from_ver} not found in snapshots")
        return 1

    if not to_dir.exists():
        print(f"Version {args.to_ver} not found in snapshots")
        return 1

    from_files = set(f.name for f in from_dir.glob("*.json"))
    to_files = set(f.name for f in to_dir.glob("*.json"))

    added = to_files - from_files
    removed = from_files - to_files
    common = from_files & to_files

    print(f"Comparing {args.from_ver} -> {args.to_ver}")
    print()

    if added:
        print(f"Added schemas ({len(added)}):")
        for f in sorted(added):
            print(f"  + {f}")

    if removed:
        print(f"\nRemoved schemas ({len(removed)}):")
        for f in sorted(removed):
            print(f"  - {f}")

    if common:
        print(f"\nCommon schemas ({len(common)}):")
        for f in sorted(common):
            from_file = from_dir / f
            to_file = to_dir / f
            with open(from_file) as fp:
                from_content = fp.read()
            with open(to_file) as fp:
                to_content = fp.read()
            if from_content != to_content:
                print(f"  ~ {f} (modified)")
            else:
                print(f"    {f} (unchanged)")

    return 0


def publish_cmd(args):
    contracts_dir = get_contracts_dir()
    schemas_dir = contracts_dir / "schemas"
    snapshots_dir = contracts_dir / "snapshots"
    versions_file = contracts_dir / "versions.json"
    changelog_file = contracts_dir / "CHANGELOG.md"

    new_version = args.version

    if not new_version.startswith("v"):
        new_version = "v" + new_version

    snapshot_dir = snapshots_dir / new_version
    if snapshot_dir.exists():
        print(f"Version {new_version} already exists")
        return 1

    snapshot_dir.mkdir(parents=True)

    for schema_file in schemas_dir.glob("*.json"):
        shutil.copy2(schema_file, snapshot_dir / schema_file.name)

    now = datetime.now().strftime("%Y-%m-%d")
    changelog_entry = f"""## {new_version} ({now})

{args.changes}

"""

    if changelog_file.exists():
        existing = changelog_file.read_text()
        changelog_content = changelog_entry + "\n" + existing
    else:
        changelog_content = f"""# Changelog

{changelog_entry}
"""

    changelog_file.write_text(changelog_content)

    with open(versions_file) as f:
        versions = json.load(f)

    old_version = versions.get("version", "0.0.0")
    versions["version"] = new_version.lstrip("v")
    versions["schema_version"] = new_version.lstrip("v")
    versions["created_at"] = f"{now}T00:00:00Z"

    with open(versions_file, "w") as f:
        json.dump(versions, f, indent=2)

    print(f"Published version {new_version}")
    print(f"Snapshot created: {snapshot_dir}")
    print(f"Updated: {versions_file}")
    print(f"Updated: {changelog_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
