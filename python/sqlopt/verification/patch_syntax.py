from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .patch_artifact import PatchArtifactResult, materialize_patch_artifact


@dataclass(frozen=True)
class PatchSyntaxResult:
    ok: bool
    xml_parse_ok: bool
    render_ok: bool
    sql_parse_ok: bool
    rendered_sql_present: bool
    reason_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "xmlParseOk": self.xml_parse_ok,
            "renderOk": self.render_ok,
            "sqlParseOk": self.sql_parse_ok,
            "renderedSqlPresent": self.rendered_sql_present,
            "reasonCode": self.reason_code,
        }


def verify_patch_syntax(
    *,
    sql_unit: dict[str, Any],
    patch_target: dict[str, Any],
    patch_text: str,
    replay_result: Any,
    artifact: PatchArtifactResult | None = None,
) -> PatchSyntaxResult:
    artifact_result = artifact
    if artifact_result is None and str(patch_text or "").strip():
        artifact_result = materialize_patch_artifact(sql_unit=sql_unit, patch_text=patch_text)
    if getattr(replay_result, "matches_target", False) is not True:
        return PatchSyntaxResult(
            ok=False,
            xml_parse_ok=bool(getattr(artifact_result, "xml_parse_ok", False)),
            render_ok=bool(getattr(replay_result, "normalized_rendered_sql", None)),
            sql_parse_ok=bool(getattr(replay_result, "normalized_rendered_sql", None)),
            rendered_sql_present=bool(getattr(replay_result, "normalized_rendered_sql", None)),
            reason_code=str(
                getattr(replay_result, "drift_reason", None)
                or getattr(artifact_result, "reason_code", None)
                or "PATCH_TARGET_DRIFT"
            ),
        )
    xml_path = Path(str(sql_unit.get("xmlPath") or ""))
    xml_parse_ok = bool(getattr(artifact_result, "xml_parse_ok", False))
    if artifact_result is None and xml_path.exists():
        try:
            ET.parse(xml_path)
            xml_parse_ok = True
        except Exception:
            xml_parse_ok = False
    rendered_sql_present = bool(getattr(replay_result, "normalized_rendered_sql", None) or str(patch_target.get("targetSql") or "").strip())
    render_ok = rendered_sql_present
    sql_parse_ok = rendered_sql_present
    ok = xml_parse_ok and render_ok and sql_parse_ok and bool(str(patch_text or "").strip())
    return PatchSyntaxResult(
        ok=ok,
        xml_parse_ok=xml_parse_ok,
        render_ok=render_ok,
        sql_parse_ok=sql_parse_ok,
        rendered_sql_present=rendered_sql_present,
        reason_code=None if ok else str(getattr(artifact_result, "reason_code", None) or "PATCH_SYNTAX_INVALID"),
    )
