#!/usr/bin/env python3
"""Enhanced doctor script with comprehensive diagnostics and auto-fix capabilities."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def _bootstrap() -> None:
    script_dir = Path(__file__).resolve().parent
    root_dir = script_dir.parent
    candidates = [root_dir / "python", root_dir / "runtime" / "python"]
    for path in candidates:
        if path.exists():
            sys.path.insert(0, str(path))
            return
    raise SystemExit("cannot locate python runtime (expected ./python or ./runtime/python)")


_bootstrap()

from sqlopt.install_support import cli_run_command, is_windows, skill_dir  # noqa: E402
from sqlopt.subprocess_utils import run_capture_text  # noqa: E402


class DiagnosticResult:
    """Result of a diagnostic check."""

    def __init__(self, name: str, passed: bool, message: str = "", suggestion: str = "", fixable: bool = False):
        self.name = name
        self.passed = passed
        self.message = message
        self.suggestion = suggestion
        self.fixable = fixable


class Doctor:
    """Enhanced diagnostic tool for SQL Optimizer."""

    def __init__(self, project_dir: Path, verbose: bool = False, fix: bool = False):
        self.project_dir = project_dir
        self.verbose = verbose
        self.fix = fix
        self.results: list[DiagnosticResult] = []
        self.skill_root = skill_dir()

    def run_all_checks(self) -> bool:
        """Run all diagnostic checks."""
        print("=" * 70)
        print("SQL Optimizer Doctor - Diagnostic Report")
        print("=" * 70)
        print(f"Project: {self.project_dir}")
        print(f"Skill:   {self.skill_root}")
        print(f"Mode:    {'Fix' if self.fix else 'Check'}")
        print("=" * 70)
        print()

        # Run checks in order
        self.check_python_version()
        self.check_skill_installation()
        self.check_config_file()
        self.check_config_validity()
        self.check_java_scanner()
        self.check_mapper_files()
        self.check_database_connection()
        self.check_opencode_available()
        self.check_runs_directory()

        # Print summary
        self.print_summary()

        return all(r.passed for r in self.results)

    def check_python_version(self) -> None:
        """Check Python version."""
        try:
            version = sys.version_info
            if version >= (3, 10):
                self.add_result(DiagnosticResult(
                    "Python Version",
                    True,
                    f"Python {version.major}.{version.minor}.{version.micro}"
                ))
            else:
                self.add_result(DiagnosticResult(
                    "Python Version",
                    False,
                    f"Python {version.major}.{version.minor}.{version.micro} (requires >= 3.10)",
                    "Upgrade Python to 3.10 or higher"
                ))
        except Exception as e:
            self.add_result(DiagnosticResult("Python Version", False, str(e)))

    def check_skill_installation(self) -> None:
        """Check if skill is properly installed."""
        cli = self.skill_root / "bin" / ("sqlopt-cli.cmd" if is_windows() else "sqlopt-cli")

        if cli.exists():
            self.add_result(DiagnosticResult(
                "Skill CLI",
                True,
                f"Found at {cli}"
            ))
        else:
            self.add_result(DiagnosticResult(
                "Skill CLI",
                False,
                f"Not found at {cli}",
                "Run: python3 install/install_skill.py --project <path>",
                fixable=True
            ))

    def check_config_file(self) -> None:
        """Check if config file exists."""
        config = self.project_dir / "sqlopt.yml"

        if config.exists():
            self.add_result(DiagnosticResult(
                "Config File",
                True,
                f"Found at {config}"
            ))
        else:
            self.add_result(DiagnosticResult(
                "Config File",
                False,
                f"Not found at {config}",
                "Copy templates/sqlopt.example.yml to your project as sqlopt.yml",
                fixable=True
            ))

            if self.fix:
                self.fix_config_file()

    def check_config_validity(self) -> None:
        """Check if config file is valid YAML with required fields."""
        config = self.project_dir / "sqlopt.yml"

        if not config.exists():
            return  # Already reported in check_config_file

        try:
            import yaml
            with open(config, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            # Check required fields
            required_fields = [
                ("project", "root_path"),
                ("scan", "mapper_globs"),
                ("db", "platform"),
                ("db", "dsn"),
            ]

            missing = []
            for *path, field in required_fields:
                current = data
                for key in path:
                    if not isinstance(current, dict) or key not in current:
                        missing.append(".".join(path + [field]))
                        break
                    current = current[key]
                else:
                    if field not in current:
                        missing.append(".".join(path + [field]))

            if missing:
                self.add_result(DiagnosticResult(
                    "Config Validity",
                    False,
                    f"Missing required fields: {', '.join(missing)}",
                    "Add missing fields to sqlopt.yml (see templates/sqlopt.example.yml)"
                ))
            else:
                self.add_result(DiagnosticResult(
                    "Config Validity",
                    True,
                    "All required fields present"
                ))

        except Exception as e:
            self.add_result(DiagnosticResult(
                "Config Validity",
                False,
                f"Invalid YAML: {e}",
                "Fix YAML syntax errors in sqlopt.yml"
            ))

    def check_java_scanner(self) -> None:
        """Check if Java scanner JAR exists."""
        config = self.project_dir / "sqlopt.yml"

        if not config.exists():
            return

        try:
            import yaml
            with open(config, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            jar_path = data.get("scan", {}).get("java_scanner", {}).get("jar_path", "")

            if jar_path == "__SCANNER_JAR__":
                self.add_result(DiagnosticResult(
                    "Java Scanner JAR",
                    False,
                    "Placeholder not replaced",
                    "Run: python3 install/install_skill.py --project <path>",
                    fixable=True
                ))
                return

            jar = Path(jar_path).expanduser()
            if jar.exists():
                self.add_result(DiagnosticResult(
                    "Java Scanner JAR",
                    True,
                    f"Found at {jar}"
                ))
            else:
                self.add_result(DiagnosticResult(
                    "Java Scanner JAR",
                    False,
                    f"Not found at {jar}",
                    "Reinstall skill or build JAR manually: cd java/scan-agent && mvn package"
                ))

        except Exception as e:
            self.add_result(DiagnosticResult(
                "Java Scanner JAR",
                False,
                f"Error checking: {e}"
            ))

    def check_mapper_files(self) -> None:
        """Check if mapper files exist."""
        config = self.project_dir / "sqlopt.yml"

        if not config.exists():
            return

        try:
            import yaml
            with open(config, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            mapper_globs = data.get("scan", {}).get("mapper_globs", [])

            if not mapper_globs:
                self.add_result(DiagnosticResult(
                    "Mapper Files",
                    False,
                    "No mapper_globs configured",
                    "Add mapper file patterns to scan.mapper_globs in sqlopt.yml"
                ))
                return

            # Check if any files match the globs
            import glob as glob_module
            found_files = []
            for pattern in mapper_globs:
                full_pattern = str(self.project_dir / pattern)
                matches = glob_module.glob(full_pattern, recursive=True)
                found_files.extend(matches)

            if found_files:
                self.add_result(DiagnosticResult(
                    "Mapper Files",
                    True,
                    f"Found {len(found_files)} mapper file(s)"
                ))
            else:
                self.add_result(DiagnosticResult(
                    "Mapper Files",
                    False,
                    "No mapper files found matching patterns",
                    "Check scan.mapper_globs patterns in sqlopt.yml"
                ))

        except Exception as e:
            self.add_result(DiagnosticResult(
                "Mapper Files",
                False,
                f"Error checking: {e}"
            ))

    def check_database_connection(self) -> None:
        """Check database connection."""
        config = self.project_dir / "sqlopt.yml"

        if not config.exists():
            return

        try:
            import yaml
            with open(config, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            db_reachable = data.get("validate", {}).get("db_reachable", True)

            if not db_reachable:
                self.add_result(DiagnosticResult(
                    "Database Connection",
                    True,
                    "Skipped (db_reachable=false)"
                ))
                return

            dsn = data.get("db", {}).get("dsn", "")
            platform = data.get("db", {}).get("platform", "")

            if not dsn or "<" in dsn:
                self.add_result(DiagnosticResult(
                    "Database Connection",
                    False,
                    "DSN not configured or contains placeholders",
                    "Set db.dsn in sqlopt.yml with actual connection string"
                ))
                return

            # Try to parse DSN
            if platform == "postgresql":
                # Basic check - don't actually connect
                if dsn.startswith("postgresql://"):
                    self.add_result(DiagnosticResult(
                        "Database Connection",
                        True,
                        f"DSN format valid ({platform})"
                    ))
                else:
                    self.add_result(DiagnosticResult(
                        "Database Connection",
                        False,
                        "Invalid PostgreSQL DSN format",
                        "Use format: postgresql://user:pass@host:port/db"
                    ))
            elif platform == "mysql":
                if dsn.startswith("mysql://"):
                    self.add_result(DiagnosticResult(
                        "Database Connection",
                        True,
                        f"DSN format valid ({platform})"
                    ))
                else:
                    self.add_result(DiagnosticResult(
                        "Database Connection",
                        False,
                        "Invalid MySQL DSN format",
                        "Use format: mysql://user:pass@host:port/db"
                    ))
            else:
                self.add_result(DiagnosticResult(
                    "Database Connection",
                    False,
                    f"Unknown platform: {platform}",
                    "Set db.platform to 'postgresql' or 'mysql'"
                ))

        except Exception as e:
            self.add_result(DiagnosticResult(
                "Database Connection",
                False,
                f"Error checking: {e}"
            ))

    def check_opencode_available(self) -> None:
        """Check if opencode command is available."""
        try:
            proc = run_capture_text(["opencode", "--version"])
            if proc.returncode == 0:
                version = (proc.stdout or "").strip()
                self.add_result(DiagnosticResult(
                    "OpenCode CLI",
                    True,
                    f"Available: {version}"
                ))
            else:
                self.add_result(DiagnosticResult(
                    "OpenCode CLI",
                    False,
                    "Command failed",
                    "Install OpenCode or check PATH"
                ))
        except (FileNotFoundError, OSError):
            self.add_result(DiagnosticResult(
                "OpenCode CLI",
                False,
                "Command not found",
                "Install OpenCode or add to PATH" + (" (reopen PowerShell if just installed)" if is_windows() else "")
            ))

    def check_runs_directory(self) -> None:
        """Check if runs directory exists and is writable."""
        runs_dir = self.project_dir / "runs"

        if runs_dir.exists():
            if runs_dir.is_dir():
                # Check if writable
                test_file = runs_dir / ".doctor_test"
                try:
                    test_file.touch()
                    test_file.unlink()
                    self.add_result(DiagnosticResult(
                        "Runs Directory",
                        True,
                        f"Exists and writable: {runs_dir}"
                    ))
                except Exception:
                    self.add_result(DiagnosticResult(
                        "Runs Directory",
                        False,
                        f"Exists but not writable: {runs_dir}",
                        "Check directory permissions"
                    ))
            else:
                self.add_result(DiagnosticResult(
                    "Runs Directory",
                    False,
                    f"Exists but is not a directory: {runs_dir}",
                    "Remove the file and let SQL Optimizer create the directory"
                ))
        else:
            self.add_result(DiagnosticResult(
                "Runs Directory",
                True,
                "Will be created on first run"
            ))

    def fix_config_file(self) -> None:
        """Auto-fix: Copy example config to project."""
        try:
            example = self.skill_root.parent / "templates" / "sqlopt.example.yml"
            target = self.project_dir / "sqlopt.yml"

            if example.exists():
                import shutil
                shutil.copy(example, target)
                print(f"  → Fixed: Copied {example} to {target}")
            else:
                print(f"  → Cannot fix: Example config not found at {example}")
        except Exception as e:
            print(f"  → Fix failed: {e}")

    def add_result(self, result: DiagnosticResult) -> None:
        """Add a diagnostic result and print it."""
        self.results.append(result)

        status = "✓" if result.passed else "✗"
        color = "\033[92m" if result.passed else "\033[91m"
        reset = "\033[0m"

        print(f"{color}[{status}]{reset} {result.name}")

        if result.message:
            print(f"    {result.message}")

        if not result.passed and result.suggestion:
            print(f"    💡 Suggestion: {result.suggestion}")

        if not result.passed and result.fixable and self.fix:
            print(f"    🔧 Attempting auto-fix...")

        print()

    def print_summary(self) -> None:
        """Print diagnostic summary."""
        print("=" * 70)
        print("Summary")
        print("=" * 70)

        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed

        print(f"Total checks: {len(self.results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print()

        if failed > 0:
            print("Failed checks:")
            for r in self.results:
                if not r.passed:
                    print(f"  • {r.name}")
                    if r.suggestion:
                        print(f"    → {r.suggestion}")
            print()

            fixable = sum(1 for r in self.results if not r.passed and r.fixable)
            if fixable > 0 and not self.fix:
                print(f"💡 {fixable} issue(s) can be auto-fixed. Run with --fix to attempt fixes.")
                print()

        if failed == 0:
            print("✓ All checks passed! Your environment is ready.")
        else:
            print("✗ Some checks failed. Please address the issues above.")

        print("=" * 70)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SQL Optimizer diagnostic tool - check environment and configuration"
    )
    p.add_argument(
        "--project",
        default=".",
        help="Project directory path (default: current directory)"
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed diagnostic information"
    )
    p.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to auto-fix common issues"
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    project_dir = Path(args.project).resolve()

    doctor = Doctor(project_dir, verbose=args.verbose, fix=args.fix)
    success = doctor.run_all_checks()

    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
