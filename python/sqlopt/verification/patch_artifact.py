from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_HUNK_RE = re.compile(r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@")


@dataclass(frozen=True)
class PatchArtifactResult:
    applied: bool
    xml_parse_ok: bool
    patched_text: str | None
    root: ET.Element | None
    reason_code: str | None = None


def _normalize_patch_path(path: str) -> str:
    normalized = str(path or "").strip()
    if normalized.startswith("a/") or normalized.startswith("b/"):
        normalized = normalized[2:]
    return normalized


def _expected_patch_paths(xml_path: Path, base_dir: Path | None = None) -> set[str]:
    expected = {xml_path.as_posix()}
    try:
        expected.add(xml_path.resolve().as_posix())
    except Exception:
        pass
    if base_dir is not None:
        try:
            expected.add(xml_path.resolve().relative_to(base_dir.resolve()).as_posix())
        except Exception:
            pass
    try:
        expected.add(xml_path.resolve().relative_to(Path.cwd().resolve()).as_posix())
    except Exception:
        pass
    return {value for value in expected if value}


def _extract_target_path(patch_lines: list[str]) -> str | None:
    for line in patch_lines:
        if line.startswith("+++ "):
            candidate = _normalize_patch_path(line[4:])
            if candidate and candidate != "/dev/null":
                return candidate
    return None


def _apply_unified_diff(original_text: str, patch_text: str) -> str:
    patch_lines = patch_text.splitlines()
    hunk_start = next((idx for idx, line in enumerate(patch_lines) if line.startswith("@@ ")), -1)
    if hunk_start < 0:
        raise ValueError("missing unified diff hunk header")

    original_lines = original_text.splitlines()
    had_trailing_newline = original_text.endswith("\n")
    patched_lines: list[str] = []
    original_index = 0
    cursor = hunk_start

    while cursor < len(patch_lines):
        header = patch_lines[cursor]
        if not header.startswith("@@ "):
            raise ValueError("unexpected patch line outside hunk")
        match = _HUNK_RE.match(header)
        if match is None:
            raise ValueError("invalid unified diff hunk header")
        old_start_number = int(match.group("old_start"))
        old_count = int(match.group("old_count") or "1")
        new_count = int(match.group("new_count") or "1")
        if old_count == 0:
            if old_start_number < 1 or old_start_number > len(original_lines) + 1:
                raise ValueError("hunk start beyond source length")
        elif old_start_number < 1 or old_start_number > len(original_lines):
            raise ValueError("hunk start beyond source length")
        old_start = max(0, old_start_number - 1)
        patched_lines.extend(original_lines[original_index:old_start])
        original_index = old_start
        consumed_old = 0
        produced_new = 0
        cursor += 1

        while cursor < len(patch_lines) and not patch_lines[cursor].startswith("@@ "):
            line = patch_lines[cursor]
            if line.startswith("\\ No newline at end of file"):
                cursor += 1
                continue
            marker = line[:1]
            content = line[1:]
            if marker == " ":
                if original_index >= len(original_lines) or original_lines[original_index] != content:
                    raise ValueError("context mismatch while applying patch artifact")
                patched_lines.append(content)
                original_index += 1
                consumed_old += 1
                produced_new += 1
            elif marker == "-":
                if original_index >= len(original_lines) or original_lines[original_index] != content:
                    raise ValueError("removal mismatch while applying patch artifact")
                original_index += 1
                consumed_old += 1
            elif marker == "+":
                patched_lines.append(content)
                produced_new += 1
            else:
                raise ValueError("unsupported unified diff line")
            cursor += 1
        if consumed_old != old_count or produced_new != new_count:
            raise ValueError("hunk line counts do not match header")

    patched_lines.extend(original_lines[original_index:])
    patched_text = "\n".join(patched_lines)
    if had_trailing_newline:
        patched_text += "\n"
    return patched_text


def materialize_patch_artifact(
    *,
    sql_unit: dict[str, Any],
    patch_text: str,
    base_dir: Path | None = None,
) -> PatchArtifactResult:
    xml_path = Path(str(sql_unit.get("xmlPath") or ""))
    if not str(patch_text or "").strip():
        return PatchArtifactResult(False, False, None, None, "PATCH_ARTIFACT_MISSING")
    if not xml_path.exists():
        return PatchArtifactResult(False, False, None, None, "PATCH_XML_SOURCE_MISSING")

    patch_lines = patch_text.splitlines()
    target_path = _extract_target_path(patch_lines)
    if target_path and target_path not in _expected_patch_paths(xml_path, base_dir):
        return PatchArtifactResult(False, False, None, None, "PATCH_ARTIFACT_TARGET_MISMATCH")

    try:
        patched_text = _apply_unified_diff(xml_path.read_text(encoding="utf-8"), patch_text)
    except Exception:
        return PatchArtifactResult(False, False, None, None, "PATCH_ARTIFACT_INVALID")

    try:
        root = ET.fromstring(patched_text)
    except ET.ParseError:
        return PatchArtifactResult(True, False, patched_text, None, "PATCH_XML_PARSE_FAILED")
    return PatchArtifactResult(True, True, patched_text, root, None)
