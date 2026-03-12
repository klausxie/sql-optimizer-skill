from __future__ import annotations

from dataclasses import dataclass, field
import re

from .template_rendering import normalize_sql_text

_CTE_HEAD_RE = re.compile(r"^\s*with\s+(?P<name>[a-z_][a-z0-9_]*)\s+as\s*\(", flags=re.IGNORECASE)
_SELECT_FROM_RE = re.compile(r"^\s*select\s+(?P<projection>.+?)\s+(?P<from_suffix>from\b.+)$", flags=re.IGNORECASE | re.DOTALL)
_OUTER_SELECT_RE = re.compile(
    r"^\s*select\s+(?P<projection>.+?)\s+from\s+(?P<target>[a-z_][a-z0-9_]*)(?:\s+(?:as\s+)?(?P<alias>[a-z_][a-z0-9_]*))?\s*(?P<suffix>.*)$",
    flags=re.IGNORECASE | re.DOTALL,
)
_RESERVED_OUTER_TOKENS = {"WHERE", "ORDER", "LIMIT", "OFFSET", "FETCH"}
_PROHIBITED_PATTERNS = (
    (r"\bdistinct\b", "DISTINCT_PRESENT"),
    (r"\bgroup\s+by\b", "GROUP_BY_PRESENT"),
    (r"\bhaving\b", "HAVING_PRESENT"),
    (r"\bunion\b", "UNION_PRESENT"),
    (r"\bover\s*\(", "WINDOW_PRESENT"),
    (r"\blimit\b", "LIMIT_PRESENT"),
    (r"\boffset\b", "OFFSET_PRESENT"),
    (r"\bfetch\b", "FETCH_PRESENT"),
    (r"^\s*with\b", "NESTED_CTE_PRESENT"),
)


@dataclass(frozen=True)
class SimpleCteInlineAnalysis:
    present: bool
    cte_name: str | None = None
    inner_sql: str | None = None
    outer_sql: str | None = None
    inner_projection: str | None = None
    inner_from_suffix: str | None = None
    outer_projection: str | None = None
    outer_suffix: str | None = None
    collapsible: bool = False
    blockers: list[str] = field(default_factory=list)
    inlined_sql: str | None = None


def _normalized_projection(expr: str | None) -> str | None:
    value = normalize_sql_text(expr or "")
    return value.lower() or None


def _find_matching_paren(text: str, start_idx: int) -> int:
    depth = 0
    for idx in range(start_idx, len(text)):
        char = text[idx]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def _parse_single_cte(sql: str) -> tuple[str | None, str | None, str | None, list[str]]:
    match = _CTE_HEAD_RE.match(sql)
    if not match:
        return None, None, None, []
    cte_name = str(match.group("name") or "").strip()
    open_paren_idx = match.end() - 1
    close_paren_idx = _find_matching_paren(sql, open_paren_idx)
    if close_paren_idx < 0:
        return cte_name or None, None, None, ["CTE_PAREN_MISMATCH"]
    inner_sql = normalize_sql_text(sql[open_paren_idx + 1 : close_paren_idx])
    outer_sql = normalize_sql_text(sql[close_paren_idx + 1 :])
    blockers: list[str] = []
    if outer_sql.startswith(","):
        blockers.append("MULTI_CTE_UNSUPPORTED")
    return cte_name or None, inner_sql or None, outer_sql or None, blockers


def analyze_simple_inline_cte(sql: str) -> SimpleCteInlineAnalysis:
    raw_sql = str(sql or "").strip()
    if not raw_sql:
        return SimpleCteInlineAnalysis(present=False)
    cte_name, inner_sql, outer_sql, blockers = _parse_single_cte(raw_sql)
    if not cte_name:
        return SimpleCteInlineAnalysis(present=False)
    if not inner_sql or not outer_sql:
        return SimpleCteInlineAnalysis(
            present=True,
            cte_name=cte_name,
            inner_sql=inner_sql,
            outer_sql=outer_sql,
            blockers=list(blockers) or ["CTE_PARSE_INCOMPLETE"],
        )

    inner_match = _SELECT_FROM_RE.match(inner_sql)
    outer_match = _OUTER_SELECT_RE.match(outer_sql)
    if inner_match is None:
        blockers.append("CTE_INNER_SELECT_UNSUPPORTED")
    if outer_match is None:
        blockers.append("CTE_OUTER_SELECT_UNSUPPORTED")

    inner_projection = normalize_sql_text(inner_match.group("projection")) if inner_match else None
    inner_from_suffix = normalize_sql_text(inner_match.group("from_suffix")) if inner_match else None
    outer_projection = normalize_sql_text(outer_match.group("projection")) if outer_match else None
    outer_target = str(outer_match.group("target") or "").strip().lower() if outer_match else None
    outer_alias = str(outer_match.group("alias") or "").strip() if outer_match else ""
    outer_suffix = normalize_sql_text(outer_match.group("suffix")) if outer_match else None
    if outer_alias.upper() in _RESERVED_OUTER_TOKENS:
        rebuilt_suffix = normalize_sql_text(f"{outer_alias} {outer_suffix or ''}")
        outer_suffix = rebuilt_suffix or None

    if outer_target and outer_target != cte_name.lower():
        blockers.append("CTE_OUTER_TARGET_MISMATCH")
    if outer_suffix and outer_suffix.lower().startswith("where "):
        blockers.append("CTE_OUTER_WHERE_UNSUPPORTED")
    for pattern, code in _PROHIBITED_PATTERNS:
        if inner_sql and re.search(pattern, inner_sql, flags=re.IGNORECASE):
            blockers.append(code)
    if inner_projection and outer_projection and _normalized_projection(inner_projection) != _normalized_projection(outer_projection):
        blockers.append("CTE_PROJECTION_MISMATCH")

    collapsible = bool(
        cte_name
        and inner_sql
        and outer_sql
        and inner_projection
        and inner_from_suffix
        and outer_projection
        and outer_target == cte_name.lower()
        and not blockers
    )
    inlined_sql = None
    if collapsible:
        suffix = f" {outer_suffix}" if outer_suffix else ""
        inlined_sql = normalize_sql_text(f"SELECT {outer_projection} {inner_from_suffix}{suffix}")
    return SimpleCteInlineAnalysis(
        present=True,
        cte_name=cte_name,
        inner_sql=inner_sql,
        outer_sql=outer_sql,
        inner_projection=inner_projection,
        inner_from_suffix=inner_from_suffix,
        outer_projection=outer_projection,
        outer_suffix=outer_suffix,
        collapsible=collapsible,
        blockers=blockers,
        inlined_sql=inlined_sql,
    )
