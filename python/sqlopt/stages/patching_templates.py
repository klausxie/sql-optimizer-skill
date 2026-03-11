from __future__ import annotations

from pathlib import Path

from ..io_utils import read_jsonl
from ..run_paths import canonical_paths
from ..platforms.sql.materialization_constants import TEMPLATE_SAFE_MODES
from .patching_render import build_range_patch


def build_template_plan_patch(sql_unit: dict, acceptance: dict, run_dir: Path) -> tuple[str | None, int, dict | None]:
    materialization = acceptance.get("rewriteMaterialization") or {}
    mode = str(materialization.get("mode") or "").strip()
    ops = [row for row in (acceptance.get("templateRewriteOps") or []) if isinstance(row, dict)]
    if mode not in TEMPLATE_SAFE_MODES:
        return None, 0, None
    if materialization.get("replayVerified") is not True:
        return None, 0, {
            "code": "PATCH_TEMPLATE_MATERIALIZATION_MISSING",
            "message": "template rewrite cannot be applied without replay verification",
        }
    if not ops:
        return None, 0, {
            "code": "PATCH_TEMPLATE_MATERIALIZATION_MISSING",
            "message": "template materialization did not include rewrite ops",
        }
    statement_op = next((row for row in ops if str(row.get("op") or "") == "replace_statement_body"), None)
    if statement_op is not None:
        range_info = ((sql_unit.get("locators") or {}) if isinstance(sql_unit.get("locators"), dict) else {}).get("range")
        if not isinstance(range_info, dict):
            return None, 0, {
                "code": "PATCH_TEMPLATE_MATERIALIZATION_MISSING",
                "message": "statement template rewrite op missing range locator",
            }
        return build_range_patch(Path(str(sql_unit.get("xmlPath") or "")), range_info, str(statement_op.get("afterTemplate") or "")) + (None,)

    op = next((row for row in ops if str(row.get("op") or "") == "replace_fragment_body"), None)
    if op is None:
        return None, 0, {
            "code": "PATCH_TEMPLATE_MATERIALIZATION_MISSING",
            "message": "fragment template rewrite op missing",
        }
    target_ref = str(op.get("targetRef") or materialization.get("targetRef") or "").strip()
    fragment_rows = read_jsonl(canonical_paths(run_dir).scan_fragments_path)
    fragment = next((row for row in fragment_rows if str(row.get("fragmentKey") or "") == target_ref), None)
    if fragment is None:
        return None, 0, {
            "code": "PATCH_FRAGMENT_LOCATOR_AMBIGUOUS",
            "message": "fragment locator not found",
        }
    range_info = ((fragment.get("locators") or {}) if isinstance(fragment.get("locators"), dict) else {}).get("range")
    if not isinstance(range_info, dict):
        return None, 0, {
            "code": "PATCH_FRAGMENT_LOCATOR_AMBIGUOUS",
            "message": "fragment range locator missing",
        }
    return build_range_patch(Path(str(fragment.get("xmlPath") or "")), range_info, str(op.get("afterTemplate") or "")) + (None,)
