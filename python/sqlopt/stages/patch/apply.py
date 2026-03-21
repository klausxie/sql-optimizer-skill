"""Apply stage functions.

Handles patch application to project files.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ...io_utils import read_json, read_jsonl, write_json
from ...run_paths import canonical_paths


def _patch_result_summary(run_dir: Path) -> dict:
    rows = [
        row
        for row in read_jsonl(canonical_paths(run_dir).patches_path)
        if isinstance(row, dict)
    ]
    selected_rows = [row for row in rows if row.get("patchFiles")]
    skipped_rows = [row for row in rows if not row.get("patchFiles")]
    reason_codes: list[str] = []
    for row in skipped_rows:
        code = str(((row.get("selectionReason") or {}).get("code")) or "").strip()
        if code and code not in reason_codes:
            reason_codes.append(code)
    return {
        "result_count": len(rows),
        "selected_count": len(selected_rows),
        "skipped_count": len(skipped_rows),
        "skipped_reason_codes": reason_codes[:5],
    }


def apply_patch_only(run_dir: Path) -> dict:
    patch_summary = _patch_result_summary(run_dir)
    state = {
        "mode": "PATCH_ONLY",
        "applied": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "message": "patch-only mode does not mutate project files; inspect patch results before applying manually",
        "patch_results": patch_summary,
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
    return cfg if isinstance(cfg, dict) else {}


def _collect_patch_files(run_dir: Path) -> list[Path]:
    rows = read_jsonl(canonical_paths(run_dir).patches_path)
    ordered: list[Path] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        for item in row.get("patchFiles") or []:
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
    project_root = Path(str(project_cfg.get("root_path" or "."))).resolve()
    patch_summary = _patch_result_summary(run_dir)
    patch_files = _collect_patch_files(run_dir)
    if not patch_files:
        state = {
            "mode": mode,
            "applied": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "message": "no patch files available to apply; review patch results for skipped reasons",
            "project_root": str(project_root),
            "applied_files": [],
            "failed_files": [],
            "patch_results": patch_summary,
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
        "message": "patches applied to project files"
        if applied_files and not failed_files
        else "apply finished with failures",
        "project_root": str(project_root),
        "applied_files": applied_files,
        "failed_files": failed_files,
        "patch_results": patch_summary,
    }
    write_json(run_dir / "apply" / "state.json", state)
    return state
