#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _parse_version_from_pyproject(text: str) -> str:
    try:
        import tomllib  # type: ignore

        obj = tomllib.loads(text)
        return str(obj["project"]["version"])
    except Exception:
        pass
    try:
        import tomli  # type: ignore

        obj = tomli.loads(text)
        return str(obj["project"]["version"])
    except Exception:
        pass
    m = re.search(r'^version\s*=\s*"([^"]+)"\s*$', text, flags=re.MULTILINE)
    if not m:
        raise SystemExit("failed to parse version from pyproject.toml")
    return m.group(1)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--dist", default="")
    return p.parse_args()


def _copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        raise SystemExit(f"missing source path: {src}")
    shutil.copytree(src, dst, dirs_exist_ok=True)


def build_bundle(root_dir: Path, dist_dir: Path) -> Path:
    dist_dir.mkdir(parents=True, exist_ok=True)
    pyproject = root_dir / "pyproject.toml"
    version = _parse_version_from_pyproject(pyproject.read_text(encoding="utf-8"))
    bundle_name = f"sql-optimizer-bundle-v{version}"
    stage_dir = Path(tempfile.mkdtemp(prefix="sqlopt_bundle."))
    out_root = stage_dir / bundle_name
    (out_root / "runtime").mkdir(parents=True, exist_ok=True)
    (out_root / "templates").mkdir(parents=True, exist_ok=True)
    (out_root / "install").mkdir(parents=True, exist_ok=True)
    (out_root / "docs").mkdir(parents=True, exist_ok=True)

    _copy_tree(root_dir / "python", out_root / "runtime" / "python")
    _copy_tree(root_dir / "scripts", out_root / "runtime" / "scripts")
    _copy_tree(root_dir / "contracts", out_root / "runtime" / "contracts")
    _copy_tree(root_dir / "java", out_root / "runtime" / "java")
    shutil.copy2(root_dir / "pyproject.toml", out_root / "runtime" / "pyproject.toml")

    shutil.copy2(root_dir / "templates" / "sqlopt.example.yml", out_root / "templates" / "sqlopt.example.yml")
    for file_name in [
        "doctor.sh",
        "doctor.py",
        "build_bundle.sh",
        "build_bundle.py",
        "requirements.txt",
    ]:
        shutil.copy2(root_dir / "install" / file_name, out_root / "install" / file_name)
    for doc_name in [
        "INDEX.md",
        "INSTALL.md",
        "QUICKSTART.md",
        "CONFIG.md",
        "TROUBLESHOOTING.md",
        "current-spec.md",
    ]:
        shutil.copy2(root_dir / "docs" / doc_name, out_root / "docs" / doc_name)

    version_payload = {
        "name": "sql-optimizer",
        "version": version,
        "build_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "compat_contract_version": "v1.0.0",
    }
    (out_root / "version.json").write_text(json.dumps(version_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    archive = dist_dir / f"{bundle_name}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(out_root, arcname=bundle_name)
    return archive


def main() -> None:
    args = _parse_args()
    root_dir = Path(args.root).resolve()
    dist_dir = Path(args.dist).resolve() if args.dist else (root_dir / "dist")
    archive = build_bundle(root_dir, dist_dir)
    print(f"bundle created: {archive}")


if __name__ == "__main__":
    main()
