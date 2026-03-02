#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _parse_ts(value: Any) -> float:
    if not isinstance(value, str) or not value.strip():
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _load_index(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _index_candidates(repo_root: Path, project: Path | None) -> list[Path]:
    items: list[Path] = []
    if project is not None:
        items.append(project / "runs" / "index.json")
    items.append(repo_root / ".sqlopt-run-index.json")
    items.extend(sorted(repo_root.glob("**/runs/index.json")))
    out: list[Path] = []
    seen: set[str] = set()
    for x in items:
        key = str(x.resolve()) if x.exists() else str(x)
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out


def _resolve_from_index(run_id: str | None, candidates: list[Path]) -> tuple[str | None, Path | None]:
    latest: tuple[str, Path, float] | None = None
    for idx in candidates:
        rows = _load_index(idx)
        if run_id:
            row = rows.get(run_id, {})
            run_dir = Path(str(row.get("run_dir", ""))) if row else Path("")
            if row and run_dir.exists():
                return run_id, run_dir
            continue
        for rid, row in rows.items():
            run_dir = Path(str((row or {}).get("run_dir", "")))
            if not run_dir.exists():
                continue
            ts = _parse_ts((row or {}).get("updated_at"))
            if latest is None or ts > latest[2]:
                latest = (rid, run_dir, ts)
    if latest:
        return latest[0], latest[1]
    return None, None


def _scan_runs(repo_root: Path, project: Path | None, run_id: str | None) -> tuple[str | None, Path | None]:
    roots: list[Path] = []
    if project is not None and project.exists():
        roots.append(project)
    roots.append(repo_root)

    metas: list[Path] = []
    if run_id:
        for root in roots:
            metas.extend(root.glob(f"**/runs/{run_id}/supervisor/meta.json"))
        for meta in metas:
            run_dir = meta.parent.parent
            if run_dir.exists():
                return run_id, run_dir
        return None, None

    for root in roots:
        metas.extend(root.glob("**/runs/*/supervisor/meta.json"))
    metas = [m for m in metas if m.exists()]
    if not metas:
        return None, None
    metas.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    best = metas[0]
    rid = best.parent.parent.name
    return rid, best.parent.parent


def resolve_run_id(run_id: str | None, project: str | None = None) -> tuple[str, Path]:
    repo_root = _repo_root()
    project_path = Path(project).resolve() if project else None

    rid, run_dir = _resolve_from_index(run_id, _index_candidates(repo_root, project_path))
    if rid and run_dir:
        return rid, run_dir

    rid, run_dir = _scan_runs(repo_root, project_path, run_id)
    if rid and run_dir:
        return rid, run_dir

    raise FileNotFoundError(run_id or "latest")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id")
    p.add_argument("--project", default=".")
    p.add_argument("--print-run-dir", action="store_true")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    try:
        rid, run_dir = resolve_run_id(args.run_id, args.project)
    except FileNotFoundError:
        missing = args.run_id or "latest"
        print({"error": {"reason_code": "RUN_NOT_FOUND", "message": f"run_id not found: {missing}"}})
        raise SystemExit(2)
    if args.print_run_dir:
        print({"run_id": rid, "run_dir": str(run_dir)})
    else:
        print(rid)


if __name__ == "__main__":
    main()
