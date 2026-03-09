from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ..io_utils import read_json


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
        data = read_json(path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _index_candidates(repo_root: Path, project: Path | None) -> list[Path]:
    items: list[Path] = []
    if project is not None:
        items.append(project / "runs" / "index.json")
    items.extend(sorted(repo_root.glob("**/runs/index.json")))
    out: list[Path] = []
    seen: set[str] = set()
    for path in items:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
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


def resolve_run_id(
    run_id: str | None,
    *,
    project: str | Path | None = None,
    repo_root: Path | None = None,
) -> tuple[str, Path]:
    """Resolve explicit run_id or fallback to latest run within project/repo scope."""
    root = repo_root.resolve() if repo_root is not None else Path.cwd().resolve()
    project_path = Path(project).resolve() if project is not None else None

    rid, run_dir = _resolve_from_index(run_id, _index_candidates(root, project_path))
    if rid and run_dir:
        return rid, run_dir

    rid, run_dir = _scan_runs(root, project_path, run_id)
    if rid and run_dir:
        return rid, run_dir

    raise FileNotFoundError(run_id or "latest")
