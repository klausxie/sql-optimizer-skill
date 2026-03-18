"""V8 XML patch generator for MyBatis SQL optimization.

This module provides patch generation from validated optimization candidates.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...contracts import ContractValidator
from ...io_utils import append_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths


@dataclass
class PatchResult:
    sql_key: str
    original_sql: str
    patched_sql: str
    xml_fragment: str
    backup_needed: bool


class PatchGenerator:
    def generate_patch(self, sql_unit: dict, proposal: dict) -> str:
        namespace = sql_unit.get("namespace", "unknown")
        statement_id = sql_unit.get("statementId", "unknown")
        patched_sql = proposal.get("patched_sql", proposal.get("sql", ""))
        result_type = sql_unit.get("resultType", "map")

        return f"""<!-- Original: {namespace}.{statement_id} -->
<select id="{statement_id}" resultType="{result_type}">
  <!-- Patched SQL -->
  {patched_sql}
</select>"""

    def format_patch(self, xml_content: str) -> str:
        lines = xml_content.split("\n")
        formatted_lines = []
        indent_level = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                formatted_lines.append("")
                continue

            if stripped.startswith("</"):
                indent_level = max(0, indent_level - 1)

            formatted_lines.append("  " * indent_level + stripped)

            if (
                stripped.startswith("<")
                and not stripped.startswith("</")
                and not stripped.endswith("/>")
                and not stripped.startswith("<!--")
            ):
                if (
                    "</select>" not in stripped
                    and "</update>" not in stripped
                    and "</insert>" not in stripped
                    and "</delete>" not in stripped
                ):
                    indent_level += 1

        return "\n".join(formatted_lines)

    def create_patch_result(
        self,
        sql_unit: dict,
        proposal: dict,
        backup_needed: bool = True,
    ) -> PatchResult:
        namespace = sql_unit.get("namespace", "unknown")
        statement_id = sql_unit.get("statementId", "unknown")
        original_sql = sql_unit.get("sql", "")
        patched_sql = proposal.get("patched_sql", proposal.get("sql", ""))

        xml_fragment = self.generate_patch(sql_unit, proposal)
        formatted_fragment = self.format_patch(xml_fragment)

        return PatchResult(
            sql_key=f"{namespace}.{statement_id}",
            original_sql=original_sql,
            patched_sql=patched_sql,
            xml_fragment=formatted_fragment,
            backup_needed=backup_needed,
        )


def _check_patch_applicable(patch_file: Path, workdir: Path) -> tuple[bool, str | None]:
    try:
        proc = subprocess.run(
            ["git", "apply", "--check", str(patch_file)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:
        return False, str(exc)
    if proc.returncode == 0:
        return True, None
    detail = (proc.stderr or proc.stdout or "git apply --check failed").strip()
    return False, detail


def _build_patch_repair_hints(
    reason_code: str, apply_check_error: str | None, sql_unit: dict
) -> list[dict]:
    hints = []
    if reason_code == "APPLY_CHECK_FAILED":
        hints.append(
            {
                "hintId": "git-apply-check",
                "title": "Git apply check failed",
                "detail": apply_check_error or "Unknown error",
                "actionType": "MANUAL_REVIEW",
                "command": None,
            }
        )
    return hints


def _attach_patch_diagnostics(patch: dict, sql_unit: dict, acceptance: dict) -> dict:
    if "diagnostics" not in patch:
        patch["diagnostics"] = {}

    patch["diagnostics"]["sqlKey"] = sql_unit.get("sqlKey", "unknown")
    patch["diagnostics"]["namespace"] = sql_unit.get("namespace", "")
    patch["diagnostics"]["statementId"] = sql_unit.get("statementId", "")

    if acceptance:
        baseline_rows = acceptance.get("baselineRows")
        optimized_rows = acceptance.get("optimizedRows")
        if baseline_rows is not None and optimized_rows is not None:
            try:
                baseline_count = int(baseline_rows)
                optimized_count = int(optimized_rows)
                if baseline_count > 0:
                    improvement = (
                        (baseline_count - optimized_count) / baseline_count
                    ) * 100
                    patch["diagnostics"]["rowCountImprovement"] = f"{improvement:.1f}%"
            except (ValueError, TypeError):
                pass

    return patch


def _finalize_generated_patch(
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
) -> dict:
    applicable, error = _check_patch_applicable(patch_file, workdir)

    if not applicable:
        return {
            "status": "skipped",
            "sqlKey": sql_key,
            "statementKey": statement_key,
            "selectionReason": {
                "code": "APPLY_CHECK_FAILED",
                "message": f"Patch cannot be applied: {error}",
            },
            "patchFiles": [],
            "changedLines": 0,
            "candidatesEvaluated": candidates_evaluated,
            "selectedCandidateId": selected_candidate_id,
            "repairHints": _build_patch_repair_hints("APPLY_CHECK_FAILED", error, {}),
        }

    return {
        "status": "selected",
        "sqlKey": sql_key,
        "statementKey": statement_key,
        "patchFiles": [str(patch_file)],
        "patchText": patch_text,
        "changedLines": changed_lines,
        "candidatesEvaluated": candidates_evaluated,
        "selectedCandidateId": selected_candidate_id,
        "noEffectMessage": no_effect_message if not applicable else None,
        "selectionReason": {
            "code": "BEST_CANDIDATE",
            "message": "Selected best performing candidate",
        },
    }


def execute_one(
    sql_unit: dict,
    acceptance: dict,
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict:
    paths = canonical_paths(run_dir)

    project_root = Path.cwd().resolve()
    configured_root = str(
        (((config or {}).get("project", {}) or {}).get("root_path") or "")
    ).strip()
    if configured_root:
        candidate_root = Path(configured_root).resolve()
        if candidate_root.exists():
            project_root = candidate_root

    sql_key = sql_unit.get(
        "sqlKey",
        sql_unit.get("namespace", "unknown")
        + "."
        + sql_unit.get("statementId", "unknown"),
    )
    statement_key = sql_key

    rewritten_sql = acceptance.get("rewrittenSql") if acceptance else None

    if not rewritten_sql:
        patch_result = {
            "status": "skipped",
            "sqlKey": sql_key,
            "statementKey": statement_key,
            "patchFiles": [],
            "changedLines": 0,
            "candidatesEvaluated": 0,
            "selectedCandidateId": None,
            "selectionReason": {
                "code": "NO_REWRITTEN_SQL",
                "message": "No rewritten SQL available for patch generation",
            },
            "repairHints": [],
        }
    else:
        generator = PatchGenerator()
        patch_obj = generator.create_patch_result(
            sql_unit, {"patched_sql": rewritten_sql}
        )

        patch_result = {
            "status": "selected",
            "sqlKey": sql_key,
            "statementKey": statement_key,
            "patchFiles": [],
            "patchText": patch_obj.xml_fragment,
            "changedLines": len(patch_obj.xml_fragment.split("\n")),
            "candidatesEvaluated": 1,
            "selectedCandidateId": "primary",
            "selectionReason": {
                "code": "BEST_CANDIDATE",
                "message": "Selected best performing candidate",
            },
        }

    patch_result = _attach_patch_diagnostics(patch_result, sql_unit, acceptance)

    validator.validate("patch_result", patch_result)
    append_jsonl(paths.patches_path, patch_result)

    log_event(
        paths.manifest_path,
        "apply",
        "done",
        {"statement_key": sql_key},
    )

    return patch_result
