from __future__ import annotations

import json
from pathlib import Path

from ....utils import statement_key
from ..runtime.project import FIXTURE_SCENARIOS_PATH


def _normalize_scenario_rows(raw_rows: list[dict]) -> list[dict]:
    last_index_by_statement: dict[str, int] = {}
    last_row_by_statement: dict[str, dict] = {}
    for index, row in enumerate(raw_rows):
        sql_key = str(row.get("sqlKey") or "").strip()
        if not sql_key:
            continue
        key = statement_key(sql_key)
        last_index_by_statement[key] = index
        last_row_by_statement[key] = row

    normalized: list[dict] = []
    for key, row in sorted(last_row_by_statement.items(), key=lambda item: last_index_by_statement[item[0]]):
        payload = dict(row)
        sql_key = str(payload.get("sqlKey") or "").strip()
        if not sql_key:
            normalized.append(payload)
            continue
        payload["statementKey"] = str(payload.get("statementKey") or key)
        payload["sqlKey"] = key
        payload.pop("variantId", None)
        normalized.append(payload)
    return normalized


def load_scenarios(path: Path | None = None) -> list[dict]:
    scenario_path = path or FIXTURE_SCENARIOS_PATH
    return _normalize_scenario_rows(json.loads(scenario_path.read_text(encoding="utf-8")))


def save_scenarios(scenarios: list[dict], path: Path | None = None) -> Path:
    scenario_path = path or FIXTURE_SCENARIOS_PATH
    scenario_path.write_text(json.dumps(scenarios, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return scenario_path


def summarize_scenarios(scenarios: list[dict]) -> dict[str, object]:
    scenario_class_counts: dict[str, int] = {}
    blocker_family_counts: dict[str, int] = {}
    roadmap_stage_counts: dict[str, int] = {}
    roadmap_theme_counts: dict[str, int] = {}
    next_target_sql_keys: list[str] = []
    for row in scenarios:
        scenario_class = str(row.get("scenarioClass") or "")
        blocker_family = str(row.get("targetBlockerFamily") or "")
        roadmap_stage = str(row.get("roadmapStage") or "")
        roadmap_theme = str(row.get("roadmapTheme") or "")
        if scenario_class:
            scenario_class_counts[scenario_class] = scenario_class_counts.get(scenario_class, 0) + 1
        if blocker_family:
            blocker_family_counts[blocker_family] = blocker_family_counts.get(blocker_family, 0) + 1
        if roadmap_stage:
            roadmap_stage_counts[roadmap_stage] = roadmap_stage_counts.get(roadmap_stage, 0) + 1
        if roadmap_theme:
            roadmap_theme_counts[roadmap_theme] = roadmap_theme_counts.get(roadmap_theme, 0) + 1
        if roadmap_stage == "NEXT":
            next_target_sql_keys.append(str(row.get("sqlKey") or ""))
    return {
        "scenarioClassCounts": scenario_class_counts,
        "blockerFamilyCounts": blocker_family_counts,
        "roadmapStageCounts": roadmap_stage_counts,
        "roadmapThemeCounts": roadmap_theme_counts,
        "nextTargetSqlKeys": next_target_sql_keys,
    }
