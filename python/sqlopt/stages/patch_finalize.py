from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def finalize_generated_patch(
    *,
    sql_key: str,
    statement_key: str,
    patch_file: Path,
    patch_text: str,
    changed_lines: int,
    candidates_evaluated: int,
    selected_candidate_id: str | None,
    no_effect_message: str,
    workdir: Path,
    check_patch_applicable: Callable[[Path, Path], tuple[bool, str | None]],
    selected_patch_result: Callable[..., dict[str, Any]],
    skip_patch_result: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    if changed_lines <= 0:
        # No effective change: do not create an empty patch artifact.
        patch_file.unlink(missing_ok=True)
        return skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_NO_EFFECTIVE_CHANGE",
            reason_message=no_effect_message,
            candidates_evaluated=candidates_evaluated,
        )
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.write_text(patch_text, encoding="utf-8")
    applicable, apply_error = check_patch_applicable(patch_file, workdir)
    if not applicable:
        return skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_NOT_APPLICABLE",
            reason_message="generated patch failed git apply --check against project root",
            candidates_evaluated=candidates_evaluated,
            selected_candidate_id=selected_candidate_id,
            applicable=False,
            apply_check_error=apply_error,
        )
    return selected_patch_result(
        sql_key=sql_key,
        statement_key=statement_key,
        patch_file=patch_file,
        changed_lines=changed_lines,
        candidates_evaluated=candidates_evaluated,
        selected_candidate_id=selected_candidate_id,
    )
