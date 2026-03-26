from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PatchSyntaxResult:
    ok: bool
    xml_parse_ok: bool
    rendered_sql_present: bool
    reason_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "xmlParseOk": self.xml_parse_ok,
            "renderedSqlPresent": self.rendered_sql_present,
            "reasonCode": self.reason_code,
        }


def verify_patch_syntax(
    *,
    sql_unit: dict[str, Any],
    patch_target: dict[str, Any],
    patch_text: str,
    replay_result: Any,
) -> PatchSyntaxResult:
    if getattr(replay_result, "matches_target", False) is not True:
        return PatchSyntaxResult(
            ok=False,
            xml_parse_ok=True,
            rendered_sql_present=bool(getattr(replay_result, "normalized_rendered_sql", None)),
            reason_code=str(getattr(replay_result, "drift_reason", None) or "PATCH_TARGET_DRIFT"),
        )
    xml_path = Path(str(sql_unit.get("xmlPath") or ""))
    xml_parse_ok = False
    if xml_path.exists():
        try:
            ET.parse(xml_path)
            xml_parse_ok = True
        except Exception:
            xml_parse_ok = False
    rendered_sql_present = bool(getattr(replay_result, "normalized_rendered_sql", None) or str(patch_target.get("targetSql") or "").strip())
    ok = xml_parse_ok and rendered_sql_present and bool(str(patch_text or "").strip())
    return PatchSyntaxResult(
        ok=ok,
        xml_parse_ok=xml_parse_ok,
        rendered_sql_present=rendered_sql_present,
        reason_code=None if ok else "PATCH_SYNTAX_INVALID",
    )
