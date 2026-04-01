from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..io_utils import read_json, read_jsonl, write_json
from ..run_paths import canonical_paths


def apply_patch_only(run_dir: Path) -> dict:
    state = {
        "mode": "PATCH_ONLY",
        "applied": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "message": "patch-only mode does not mutate project files",
    }
    write_json(run_dir / "apply" / "state.json", state)
    return state


def _resolved_config(run_dir: Path) -> dict:
    config_path = canonical_paths(run_dir).config_resolved_path
    if not config_path.exists():
        return {}
    try:
        cfg = read_json(config_path)
    except Exception:
        return {}
    if not isinstance(cfg, dict):
        return {}
    resolved = cfg.get("resolved_config")
    if isinstance(resolved, dict):
        return resolved
    return cfg


def _collect_patch_files(run_dir: Path) -> list[Path]:
    rows = read_jsonl(canonical_paths(run_dir).patches_path)
    ordered: list[Path] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        for item in (row.get("patchFiles") or []):
            p = Path(str(item)).resolve()
            key = str(p)
            if key in seen:
                continue
            seen.add(key)
            if p.exists():
                ordered.append(p)
    return ordered


def apply_from_config(run_dir: Path) -> dict:
    cfg = _resolved_config(run_dir)
    apply_cfg = (cfg.get("apply", {}) or {}) if isinstance(cfg, dict) else {}
    mode = str(apply_cfg.get("mode", "PATCH_ONLY")).strip().upper()
    if mode != "APPLY_IN_PLACE":
        return apply_patch_only(run_dir)

    project_cfg = (cfg.get("project", {}) or {}) if isinstance(cfg, dict) else {}
    project_root = Path(str(project_cfg.get("root_path") or ".")).resolve()
    patch_files = _collect_patch_files(run_dir)
    if not patch_files:
        state = {
            "mode": mode,
            "applied": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "message": "no patch files available to apply",
            "project_root": str(project_root),
            "applied_files": [],
            "failed_files": [],
        }
        write_json(run_dir / "apply" / "state.json", state)
        return state

    applied_files: list[str] = []
    failed_files: list[dict] = []
    for patch_file in patch_files:
        try:
            proc = subprocess.run(
                ["git", "apply", str(patch_file)],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:
            failed_files.append({"patch_file": str(patch_file), "error": str(exc)})
            continue
        if proc.returncode == 0:
            applied_files.append(str(patch_file))
        else:
            failed_files.append(
                {
                    "patch_file": str(patch_file),
                    "error": (proc.stderr or proc.stdout or "git apply failed").strip(),
                }
            )

    state = {
        "mode": mode,
        "applied": bool(applied_files) and not failed_files,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "message": "patches applied to project files" if applied_files and not failed_files else "apply finished with failures",
        "project_root": str(project_root),
        "applied_files": applied_files,
        "failed_files": failed_files,
    }
    write_json(run_dir / "apply" / "state.json", state)
    return state
