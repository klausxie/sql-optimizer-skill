from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ExpandedBranch:
    path_id: str
    condition: str | None
    expanded_sql: str
    is_valid: bool


def expand_branches(sql_text: str) -> list[ExpandedBranch]:
    branches = []

    if "<if" not in sql_text and "<where" not in sql_text and "<choose" not in sql_text:
        clean_sql = _strip_xml_tags(sql_text)
        branches.append(
            ExpandedBranch(
                path_id="default",
                condition=None,
                expanded_sql=clean_sql,
                is_valid=True,
            )
        )
        return branches

    branches.extend(_expand_if_tags(sql_text))

    return (
        branches
        if branches
        else [
            ExpandedBranch(
                path_id="default",
                condition=None,
                expanded_sql=_strip_xml_tags(sql_text),
                is_valid=True,
            )
        ]
    )


def _strip_xml_tags(sql: str) -> str:
    result = re.sub(r"<[^>]+>", "", sql)
    result = re.sub(r"\s+", " ", result)
    return result.strip()


def _get_sample_value(match: re.Match) -> str:
    param_name = match.group(1).lower()
    if any(k in param_name for k in ["id", "num", "count", "page", "size", "limit", "offset"]):
        return "1"
    if any(k in param_name for k in ["status", "type", "mode", "state"]):
        return "'active'"
    if any(k in param_name for k in ["name", "email", "title", "desc", "keyword"]):
        return "'test'"
    if any(k in param_name for k in ["date", "time", "start", "end"]):
        return "'2024-01-01'"
    return "1"


def _expand_if_tags(sql_text: str) -> list[ExpandedBranch]:
    branches = []

    if_test_pattern = re.compile(r"<if\s+test\s*=\s*['\"]([^'\"]+)['\"]\s*>(.*?)</if>", re.DOTALL)

    matches = list(if_test_pattern.finditer(sql_text))

    if not matches:
        clean_sql = _strip_xml_tags(sql_text)
        branches.append(ExpandedBranch(path_id="default", condition=None, expanded_sql=clean_sql, is_valid=True))
        return branches

    for idx, match in enumerate(matches):
        condition = match.group(1)
        content = match.group(2)

        base_sql = sql_text[: match.start()]
        after_sql = sql_text[match.end() :]

        path_id = f"if_{idx}"

        expanded = base_sql + content + after_sql
        expanded_clean = _strip_xml_tags(expanded)

        branches.append(
            ExpandedBranch(
                path_id=path_id,
                condition=condition,
                expanded_sql=expanded_clean,
                is_valid=True,
            )
        )

    default_sql = _strip_xml_tags(sql_text)
    branches.append(
        ExpandedBranch(
            path_id="default",
            condition=None,
            expanded_sql=default_sql,
            is_valid=True,
        )
    )

    return branches
