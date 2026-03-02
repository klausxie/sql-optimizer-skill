from __future__ import annotations

from pathlib import Path
from typing import Any

from ..adapters.scanner_java import run_scan
from ..contracts import ContractValidator
from ..errors import StageError
from ..io_utils import read_jsonl, write_jsonl
from ..manifest import log_event
import glob
import xml.etree.ElementTree as ET


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _is_mybatis_mapper_root(root: ET.Element) -> bool:
    return _local_name(str(root.tag)).lower() == "mapper" and bool(str(root.attrib.get("namespace") or "").strip())


def _discover_statement_count(project_root: Path, mapper_globs: list[str]) -> int:
    total = 0
    files: list[str] = []
    for pat in mapper_globs:
        files.extend(glob.glob(str(project_root / pat), recursive=True))
    for fp in sorted(set(files)):
        try:
            root = ET.parse(fp).getroot()
        except Exception:
            continue
        if not _is_mybatis_mapper_root(root):
            continue
        for elem in root.iter():
            name = _local_name(str(elem.tag)).lower()
            if name in {"select", "update", "delete", "insert"}:
                total += 1
    return total


def execute(config: dict[str, Any], run_dir: Path, validator: ContractValidator) -> list[dict[str, Any]]:
    units, warnings = run_scan(config, run_dir, run_dir / "manifest.jsonl")
    scan_cfg = config.get("scan", {}) or {}
    class_resolution_cfg = scan_cfg.get("class_resolution", {}) or {}
    min_success_ratio = float(class_resolution_cfg.get("min_success_ratio", 0.9))
    project_root = Path(str((config.get("project", {}) or {}).get("root_path") or ".")).resolve()
    discovered_count = _discover_statement_count(project_root, list(scan_cfg.get("mapper_globs", [])))
    java_discovered = 0
    java_parsed = 0
    for warning in warnings:
        try:
            d = int(warning.get("discovered_count") or 0)
            p = int(warning.get("parsed_count") or 0)
        except Exception:
            d, p = 0, 0
        java_discovered = max(java_discovered, d)
        java_parsed = max(java_parsed, p)
    if java_discovered > 0:
        discovered_count = java_discovered
    if not units:
        for w in warnings:
            log_event(run_dir / "manifest.jsonl", "scan", "failed", w)
        reason_code = "SCAN_MAPPER_NOT_FOUND"
        for warning in warnings:
            code = warning.get("reason_code")
            if isinstance(code, str) and code.strip():
                reason_code = code
                break
        raise StageError("scan produced no sql units", reason_code=reason_code)

    if discovered_count > 0:
        parsed_count = java_parsed if java_parsed > 0 else len(units)
        success_ratio = parsed_count / discovered_count
        if success_ratio < min_success_ratio:
            payload = {
                "severity": "fatal",
                "reason_code": "SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD",
                "message": f"scan success ratio {success_ratio:.3f} below threshold {min_success_ratio:.3f}",
                "detail": {"discovered_count": discovered_count, "parsed_count": parsed_count, "min_success_ratio": min_success_ratio},
            }
            log_event(run_dir / "manifest.jsonl", "scan", "failed", payload)
            raise StageError("scan coverage below threshold", reason_code="SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD")

    for unit in units:
        validator.validate("sqlunit", unit)
    write_jsonl(run_dir / "scan.sqlunits.jsonl", units)
    fragments_path = run_dir / "scan.fragments.jsonl"
    for fragment in read_jsonl(fragments_path):
        validator.validate("fragment_record", fragment)
    for w in warnings:
        log_event(run_dir / "manifest.jsonl", "scan", "warning", w)
    log_event(run_dir / "manifest.jsonl", "scan", "done", {"sql_keys": [u["sqlKey"] for u in units]})
    return units
