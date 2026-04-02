from __future__ import annotations


def assert_fixture_scenario_summary(
    summary: dict[str, object],
    *,
    next_count: int | None = None,
    next_target_sql_key: str | None = None,
    roadmap_theme_counts: dict[str, int] | None = None,
    roadmap_stage_counts: dict[str, int] | None = None,
) -> None:
    if next_count is not None:
        actual_next_count = int((((summary.get("roadmapStageCounts") or {}).get("NEXT")) or 0))
        if actual_next_count != next_count:
            raise AssertionError(f"expected NEXT roadmap count {next_count}, got {actual_next_count}")
    if next_target_sql_key is not None:
        next_targets = {str(x) for x in (summary.get("nextTargetSqlKeys") or [])}
        if next_target_sql_key not in next_targets:
            raise AssertionError(f"expected next target sql key {next_target_sql_key!r} in summary")
    for key, expected in (roadmap_theme_counts or {}).items():
        actual = int((((summary.get("roadmapThemeCounts") or {}).get(key)) or 0))
        if actual != expected:
            raise AssertionError(f"expected roadmap theme {key!r} count {expected}, got {actual}")
    for key, expected in (roadmap_stage_counts or {}).items():
        actual = int((((summary.get("roadmapStageCounts") or {}).get(key)) or 0))
        if actual != expected:
            raise AssertionError(f"expected roadmap stage {key!r} count {expected}, got {actual}")
