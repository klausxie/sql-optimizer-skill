#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


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

from sqlopt.install_support import SKILL_NAME, commands_dir, safe_rmtree, skill_dir  # noqa: E402


def main() -> None:
    target_skill = skill_dir()
    target_commands = commands_dir()
    safe_rmtree(target_skill)
    for name in [
        "sql-optimizer-run.md",
        "sql-optimizer-status.md",
        "sql-optimizer-resume.md",
        "sql-optimizer-apply.md",
    ]:
        (target_commands / name).unlink(missing_ok=True)
    print(f"uninstalled skill: {SKILL_NAME}")
    print("note: project sqlopt.yml and runs data are preserved")


if __name__ == "__main__":
    main()
