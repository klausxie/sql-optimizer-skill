from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..adapters.mybatis_xml import is_mybatis_mapper_root as _shared_is_mybatis_mapper_root
from ..adapters.mybatis_xml import local_name as _shared_local_name
from ..adapters.scanner_java import run_scan
from ..contracts import ContractValidator
from ..errors import StageError
from ..io_utils import read_jsonl, write_jsonl
from ..manifest import log_event
from ..run_paths import canonical_paths
from ..utils import statement_key_from_row
from ..verification.models import VerificationCheck, VerificationRecord
from ..verification.writer import append_verification_record
import glob
import xml.etree.ElementTree as ET


def _local_name(tag: str) -> str:
    return _shared_local_name(tag)


def _is_mybatis_mapper_root(root: ET.Element) -> bool:
    return _shared_is_mybatis_mapper_root(root)


def _statement_key(sql_key: str) -> str:
    return sql_key.split("#", 1)[0]


def _fragment_lookup_keys(row: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for value in (row.get("fragmentKey"), row.get("displayRef")):
        text = str(value or "").strip()
        if text and text not in keys:
            keys.append(text)
    return keys


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
    paths = canonical_paths(run_dir)
    manifest_path = paths.manifest_path
    scan_units_path = paths.scan_units_path
    fragments_path = paths.scan_fragments_path
    units, warnings = run_scan(config, run_dir, manifest_path)
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
            log_event(manifest_path, "scan", "failed", w)
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
            log_event(manifest_path, "scan", "failed", payload)
            raise StageError("scan coverage below threshold", reason_code="SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD")

    fragment_rows = read_jsonl(fragments_path)
    for fragment in fragment_rows:
        validator.validate("fragment_record", fragment)
    fragment_index: dict[str, dict[str, Any]] = {}
    for fragment in fragment_rows:
        for key in _fragment_lookup_keys(fragment):
            fragment_index[key] = fragment
    fragment_catalog_enabled = bool(scan_cfg.get("enable_fragment_catalog", True))
    for unit in units:
        unit["statementKey"] = statement_key_from_row(unit)
        sql_key = str(unit.get("sqlKey") or "")
        dynamic_features = [str(x) for x in (unit.get("dynamicFeatures") or []) if str(x).strip()]
        locators = dict(unit.get("locators") or {})
        include_refs = [str(x) for x in (unit.get("includeTrace") or []) if str(x).strip()]
        is_dynamic = bool(dynamic_features)
        has_locator = bool(str(locators.get("statementId") or unit.get("statementId") or "").strip())
        has_range = bool(locators.get("range"))
        has_template_sql = bool(str(unit.get("templateSql") or "").strip())
        include_refs_resolved = all(ref in fragment_index for ref in include_refs)
        checks = [
            VerificationCheck("sql_key_present", bool(sql_key), "error", None if sql_key else "SCAN_SQL_KEY_MISSING"),
            VerificationCheck(
                "xml_path_present",
                bool(str(unit.get("xmlPath") or "").strip()),
                "error",
                None if str(unit.get("xmlPath") or "").strip() else "SCAN_XML_PATH_MISSING",
            ),
            VerificationCheck("statement_locator_present", has_locator, "error", None if has_locator else "SCAN_STATEMENT_LOCATOR_MISSING"),
            VerificationCheck(
                "dynamic_template_sql_present",
                (not is_dynamic) or has_template_sql,
                "warn" if is_dynamic else "info",
                None if (not is_dynamic) or has_template_sql else "SCAN_TEMPLATE_SQL_MISSING",
            ),
            VerificationCheck(
                "dynamic_range_present",
                (not is_dynamic) or has_range,
                "warn" if is_dynamic else "info",
                None if (not is_dynamic) or has_range else "SCAN_DYNAMIC_RANGE_MISSING",
            ),
            VerificationCheck(
                "include_trace_resolved",
                (not include_refs) or include_refs_resolved or (not fragment_catalog_enabled),
                "warn" if include_refs else "info",
                None if (not include_refs) or include_refs_resolved or (not fragment_catalog_enabled) else "SCAN_INCLUDE_TRACE_UNRESOLVED",
            ),
        ]
        if not sql_key or not has_locator or not str(unit.get("xmlPath") or "").strip():
            status = "UNVERIFIED"
            reason_code = "SCAN_CRITICAL_EVIDENCE_MISSING"
            reason_message = "scan output is missing key identity or locator fields"
        elif is_dynamic and (not has_template_sql or not has_range):
            status = "PARTIAL"
            reason_code = "SCAN_DYNAMIC_EVIDENCE_PARTIAL"
            reason_message = "dynamic statement is missing templateSql or source range evidence"
        elif include_refs and fragment_catalog_enabled and not include_refs_resolved:
            status = "PARTIAL"
            reason_code = "SCAN_INCLUDE_TRACE_PARTIAL"
            reason_message = "include trace contains fragment references not present in the fragment catalog"
        else:
            status = "VERIFIED"
            reason_code = "SCAN_EVIDENCE_VERIFIED"
            reason_message = "scan output includes the expected structural evidence"
        unit["verification"] = append_verification_record(
            run_dir,
            validator,
            VerificationRecord(
                run_id=run_dir.name,
                sql_key=sql_key,
                statement_key=statement_key_from_row(unit),
                phase="scan",
                status=status,
                reason_code=reason_code,
                reason_message=reason_message,
                evidence_refs=[
                    str(scan_units_path),
                    *([str(fragments_path)] if fragments_path.exists() else []),
                ],
                inputs={
                    "dynamic": is_dynamic,
                    "dynamic_features": dynamic_features,
                    "fragment_catalog_enabled": fragment_catalog_enabled,
                    "include_ref_count": len(include_refs),
                },
                checks=checks,
                verdict={
                    "has_template_sql": has_template_sql,
                    "has_source_range": has_range,
                    "include_refs_resolved": include_refs_resolved or (not include_refs) or (not fragment_catalog_enabled),
                },
                created_at=datetime.now(timezone.utc).isoformat(),
            ),
        )
        validator.validate("sqlunit", unit)
    write_jsonl(scan_units_path, units)
    for w in warnings:
        log_event(manifest_path, "scan", "warning", w)
    log_event(manifest_path, "scan", "done", {"sql_keys": [u["sqlKey"] for u in units]})
    return units
