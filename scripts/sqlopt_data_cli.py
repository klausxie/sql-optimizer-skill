#!/usr/bin/env python3
"""
SQL Optimizer Data CLI Entry Point

Usage:
    sqlopt-data get <path>
    sqlopt-data list <path>
    sqlopt-data set <path> <value>
    sqlopt-data diff <path-a> <path-b>
    sqlopt-data validate <path>
    sqlopt-data prune <target>
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.cli.data_cli import main

if __name__ == "__main__":
    sys.exit(main())
