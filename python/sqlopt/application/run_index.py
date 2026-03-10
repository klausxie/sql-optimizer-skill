from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..io_utils import read_json, write_json
from ..run_paths import RUN_META_GLOB_SUFFIX

_INDEX_CACHE: dict[Path, tuple[int, dict[str, dict]]] = {}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def run_index_path_for_runs_root(runs_root: Path) -> Path:
    return runs_root / "index.json"


def load_run_index(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        mtime_ns = path.stat().st_mtime_ns
    except Exception:
        mtime_ns = -1
    cached = _INDEX_CACHE.get(path)
    if cached is not None and cached[0] == mtime_ns:
        return dict(cached[1])
    try:
        data = read_json(path)
    except Exception:
        return {}
    normalized = data if isinstance(data, dict) else {}
    _INDEX_CACHE[path] = (mtime_ns, normalized)
    return dict(normalized)


def save_run_index(path: Path, index: dict[str, dict]) -> None:
    write_json(path, index)
    try:
        mtime_ns = path.stat().st_mtime_ns
    except Exception:
        mtime_ns = -1
    _INDEX_CACHE[path] = (mtime_ns, dict(index))


def remember_run(run_id: str, run_dir: Path, config_path: Path, runs_root: Path) -> None:
    index_path = run_index_path_for_runs_root(runs_root)
    index = load_run_index(index_path)
    index[run_id] = {
        "run_dir": str(run_dir.resolve()),
        "config_path": str(config_path.resolve()),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_run_index(index_path, index)


def resolve_run_dir(run_id: str, *, repo_root_fn: Callable[[], Path] | None = None) -> Path:
    root_fn = repo_root_fn or repo_root
    root = root_fn()
    candidates: list[Path] = sorted(root.glob("**/runs/index.json"))
    for index_path in candidates:
        row = load_run_index(index_path).get(run_id, {})
        run_dir = Path(str(row.get("run_dir", ""))) if row else Path("")
        if row and run_dir.exists():
            return run_dir
    for meta in root.glob(f"**/runs/{run_id}/{RUN_META_GLOB_SUFFIX}"):
        run_dir = meta.parent.parent.parent
        if run_dir.exists():
            return run_dir
    raise FileNotFoundError(run_id)
