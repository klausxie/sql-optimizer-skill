"""Generate unified HTML report for init stage."""

from __future__ import annotations

import json
import pathlib
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

from sqlopt.contracts.init import (
    InitOutput,
    SQLUnit,
    TableHotspot,
    TableRelationship,
)

# ---------------------------------------------------------------------------
# Helper data classes
# ---------------------------------------------------------------------------


@dataclass
class InitReportStats:
    """Summary statistics for the init report."""

    sql_unit_count: int
    files_count: int
    fragment_count: int
    table_ref_count: int
    schema_table_count: int
    file_size_bytes: int
    duration_seconds: float
    run_id: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_init_report(
    output: InitOutput,
    duration_seconds: float,
    files_count: int,
    file_size_bytes: int,
    schema_extraction_success: bool,
    field_distributions_count: int,
    output_path: str,
) -> None:
    """Generate the unified INIT stage HTML report (SUMMARY.html).

    Args:
        output: InitOutput containing all extracted SQL units, fragments, schemas, relationships.
        duration_seconds: Total execution time in seconds.
        files_count: Number of mapper files processed.
        file_size_bytes: Total size of output files in bytes.
        schema_extraction_success: Whether schema extraction succeeded.
        field_distributions_count: Number of field distributions collected.
        output_path: Destination path for the HTML file.
    """
    stats = _compute_stats(output, duration_seconds, files_count, file_size_bytes)
    rel_stats = _compute_rel_stats(output.table_relationships, output.table_hotspots)
    hotspots_sorted = sorted(output.table_hotspots.values(), key=lambda h: h.hotspot_score, reverse=True)
    rels_sorted = sorted(output.table_relationships, key=lambda r: r.confidence, reverse=True)

    html = _build_html(
        output=output,
        stats=stats,
        rel_stats=rel_stats,
        hotspots=hotspots_sorted,
        relationships=rels_sorted,
        schema_extraction_success=schema_extraction_success,
        field_distributions_count=field_distributions_count,
    )

    pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with pathlib.Path(output_path).open("w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# Statistics computation
# ---------------------------------------------------------------------------


def _compute_stats(
    output: InitOutput,
    duration_seconds: float,
    files_count: int,
    file_size_bytes: int,
) -> InitReportStats:
    all_tables = set()
    for unit in output.sql_units:
        all_tables.update(_extract_table_names(unit.sql_text))

    return InitReportStats(
        sql_unit_count=len(output.sql_units),
        files_count=files_count,
        fragment_count=len(output.sql_fragments),
        table_ref_count=len(all_tables),
        schema_table_count=len(output.table_schemas),
        file_size_bytes=file_size_bytes,
        duration_seconds=duration_seconds,
        run_id=output.run_id,
    )


def _compute_rel_stats(
    relationships: List[TableRelationship],
    hotspots: Dict[str, TableHotspot],
) -> Any:
    """Compute relationship statistics (reuse RelationshipReportStats structure)."""
    explicit = sum(1 for r in relationships if r.is_explicit_join)
    implicit = len(relationships) - explicit
    o2m = sum(1 for r in relationships if r.direction == "one-to-many")
    m2o = sum(1 for r in relationships if r.direction == "many-to-one")
    m2m = sum(1 for r in relationships if r.direction == "many-to-many")
    high = sum(1 for h in hotspots.values() if h.risk_level == "high")
    medium = sum(1 for h in hotspots.values() if h.risk_level == "medium")
    low = sum(1 for h in hotspots.values() if h.risk_level == "low")

    incoming_sorted = sorted(hotspots.values(), key=lambda h: h.incoming_ref_count, reverse=True)
    outgoing_sorted = sorted(hotspots.values(), key=lambda h: h.outgoing_ref_count, reverse=True)
    most_incoming = incoming_sorted[0].table_name if incoming_sorted else "N/A"
    most_outgoing = outgoing_sorted[0].table_name if outgoing_sorted else "N/A"

    # Use a simple dataclass-like object for compatibility
    @dataclass
    class RelStats:
        total_relationships: int
        explicit_joins: int
        implicit_eqs: int
        one_to_many: int
        many_to_one: int
        many_to_many: int
        high_risk_tables: int
        medium_risk_tables: int
        low_risk_tables: int
        tables_with_most_incoming: str
        tables_with_most_outgoing: str

    return RelStats(
        total_relationships=len(relationships),
        explicit_joins=explicit,
        implicit_eqs=implicit,
        one_to_many=o2m,
        many_to_one=m2o,
        many_to_many=m2m,
        high_risk_tables=high,
        medium_risk_tables=medium,
        low_risk_tables=low,
        tables_with_most_incoming=most_incoming,
        tables_with_most_outgoing=most_outgoing,
    )


# ---------------------------------------------------------------------------
# Table name extraction (mirrors summary_generator logic)
# ---------------------------------------------------------------------------

_TABLE_NAME_RE = re.compile(
    r"\b(?:from|join|into|update|into)\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)", re.IGNORECASE
)


def _extract_table_names(sql_text: str) -> List[str]:
    names: List[str] = []
    for m in _TABLE_NAME_RE.finditer(sql_text):
        t = m.group(1).strip()
        if t and t.upper() not in ("DUAL",):
            names.append(t)
    return names


# ---------------------------------------------------------------------------
# Parse strategy helpers (mirrors summary_generator logic)
# ---------------------------------------------------------------------------


def _count_conditions(sql_text: str) -> int:
    return len(re.findall(r"<if\s+test\s*=\s*[\"\']([^\"\']+)[\"\']", sql_text, re.IGNORECASE))


def _suggest_strategy(cond_count: int) -> str:
    if cond_count <= 3:
        return "all_combinations"
    if cond_count <= 8:
        return "ladder"
    return "pairwise"


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------


def _build_html(
    output: InitOutput,
    stats: InitReportStats,
    rel_stats: Any,
    hotspots: List[TableHotspot],
    relationships: List[TableRelationship],
    schema_extraction_success: bool,
    field_distributions_count: int,
) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Section 1 data
    type_counter = Counter(u.statement_type for u in output.sql_units)
    stmt_labels = ["SELECT", "INSERT", "UPDATE", "DELETE"]
    stmt_colors = {
        "SELECT": "#60a5fa",
        "INSERT": "#34d399",
        "UPDATE": "#fbbf24",
        "DELETE": "#f87171",
    }
    stmt_data = [type_counter.get(t, 0) for t in stmt_labels]
    stmt_colors_list = [stmt_colors.get(t, "#64748b") for t in stmt_labels]

    # Mapper overview
    mapper_rows = ""
    if output.xml_mappings:
        for fm in sorted(output.xml_mappings.files, key=lambda f: len(f.statements), reverse=True):
            filename = fm.xml_path.split("/")[-1]
            mapper_rows += f"""
          <tr>
            <td><code>{filename}</code></td>
            <td style="text-align:center">{len(fm.statements)}</td>
            <td style="text-align:center">{len(fm.fragments)}</td>
          </tr>"""

    # SQL units grouped by mapper
    units_by_file: Dict[str, List[SQLUnit]] = {}
    for unit in output.sql_units:
        units_by_file.setdefault(unit.mapper_file, []).append(unit)

    unit_cards_html = ""
    for mapper_file, units in sorted(units_by_file.items()):
        filename = mapper_file.split("/")[-1]
        unit_items = ""
        for u in units:
            icon = _stmt_icon(u.statement_type)
            unit_items += f'<div class="unit-item">{icon} <code>{u.sql_id}</code></div>'
        unit_cards_html += f"""
        <div class="unit-group">
          <div class="unit-group-header" onclick="toggleGroup(this)">
            <span class="collapse-icon">▶</span>
            <code>{filename}</code>
            <span class="unit-count">{len(units)} 个SQL</span>
          </div>
          <div class="unit-group-body">
            {unit_items}
          </div>
        </div>"""

    # Table references
    all_tables = set()
    for unit in output.sql_units:
        all_tables.update(_extract_table_names(unit.sql_text))
    table_list_html = "".join(f"<li><code>{t}</code></li>" for t in sorted(all_tables)[:50])
    if len(all_tables) > 50:
        table_list_html += f'<li class="truncated">... 还有 {len(all_tables) - 50} 张表</li>'

    # Schema tables
    schema_rows = ""
    if output.table_schemas:
        for table_name in sorted(list(output.table_schemas.keys())[:10]):
            cols = len(output.table_schemas[table_name].columns)
            schema_rows += f"""
          <tr>
            <td><code>{table_name}</code></td>
            <td style="text-align:center">{cols}</td>
          </tr>"""

    # SQL fragments
    fragment_items = ""
    for frag in output.sql_fragments[:10]:
        fname = frag.xml_path.split("/")[-1] if frag.xml_path else "unknown"
        fragment_items += f"""
        <div class="fragment-item">
          <code>{frag.fragment_id}</code>
          <span class="frag-meta">@ {fname}:{frag.start_line}</span>
        </div>"""
    if len(output.sql_fragments) > 10:
        fragment_items += f'<div class="fragment-more">... 还有 {len(output.sql_fragments) - 10} 个片段</div>'

    # Parse strategy table - sorted by condition count desc, no truncation
    strategy_units = [
        (unit, _count_conditions(unit.sql_text), _suggest_strategy(_count_conditions(unit.sql_text)))
        for unit in output.sql_units
    ]
    strategy_units.sort(key=lambda x: x[1], reverse=True)
    strategy_total = len(strategy_units)
    strategy_rows = "".join(
        f'<tr data-strategy="{s}">'
        f"<td><code>{u.sql_id}</code></td>"
        f'<td style="text-align:center">{c}</td>'
        f'<td><span class="strategy-tag">{s}</span></td>'
        f"</tr>"
        for u, c, s in strategy_units
    )

    # Section 4 data (relationship/charts)
    hotspot_labels = [h.table_name for h in hotspots[:10]]
    hotspot_incoming = [h.incoming_ref_count for h in hotspots[:10]]
    hotspot_outgoing = [h.outgoing_ref_count for h in hotspots[:10]]
    hotspot_scores = [h.hotspot_score for h in hotspots[:10]]
    direction_data = [rel_stats.one_to_many, rel_stats.many_to_one, rel_stats.many_to_many]
    risk_data = [rel_stats.high_risk_tables, rel_stats.medium_risk_tables, rel_stats.low_risk_tables]

    table_cards_html = "".join(_render_table_card(h) for h in hotspots[:20])
    relation_items_html = "".join(_render_relation(r) for r in relationships[:50])

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>INIT 阶段报告 - {stats.run_id}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; padding: 2rem; }}
  .container {{ max-width: 1400px; margin: 0 auto; }}

  /* Header */
  .page-header {{ margin-bottom: 2rem; }}
  .page-header h1 {{ font-size: 2rem; font-weight: 700; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem; }}
  .page-header .subtitle {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 1rem; }}
  .meta-badges {{ display: flex; flex-wrap: wrap; gap: 0.5rem; }}
  .meta-badge {{ background: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 0.3rem 0.75rem; font-size: 0.8rem; color: #94a3b8; }}
  .meta-badge span {{ color: #e2e8f0; font-weight: 600; }}

  /* Sections */
  .section {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; margin-bottom: 1.5rem; }}
  .section-header {{ display: flex; align-items: center; justify-content: space-between; cursor: pointer; user-select: none; }}
  .section-header h2 {{ font-size: 1rem; font-weight: 600; color: #f1f5f9; margin: 0; }}
  .section-header .collapse-icon {{ color: #64748b; margin-right: 0.5rem; transition: transform 0.2s; }}
  .section-header.collapsed .collapse-icon {{ transform: rotate(-90deg); }}
  .section-body {{ margin-top: 1rem; }}
  .section-body.hidden {{ display: none; }}

  /* Stats grid */
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
  .stat-card {{ background: #0f172a; border-radius: 8px; padding: 1rem; border: 1px solid #334155; text-align: center; }}
  .stat-card .value {{ font-size: 1.75rem; font-weight: 700; }}
  .stat-card .label {{ font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 0.25rem; }}

  /* Charts grid */
  .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem; }}
  .chart-card {{ background: #0f172a; border-radius: 8px; padding: 1rem; border: 1px solid #334155; }}
  .chart-card h3 {{ font-size: 0.85rem; font-weight: 600; color: #cbd5e1; margin-bottom: 0.75rem; }}
  .chart-container {{ position: relative; height: 220px; }}

  /* Tables */
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ text-align: left; padding: 0.6rem 0.75rem; background: #0f172a; color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; border-bottom: 1px solid #334155; }}
  td {{ padding: 0.6rem 0.75rem; border-bottom: 1px solid #1e293b; font-size: 0.85rem; color: #cbd5e1; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: rgba(255,255,255,0.02); }}
  .truncated {{ color: #64748b; font-style: italic; }}

  /* Unit groups (SQL list) */
  .unit-group {{ background: #0f172a; border-radius: 8px; margin-bottom: 0.5rem; border: 1px solid #334155; overflow: hidden; }}
  .unit-group-header {{ display: flex; align-items: center; gap: 0.5rem; padding: 0.75rem 1rem; cursor: pointer; }}
  .unit-group-header:hover {{ background: rgba(255,255,255,0.03); }}
  .unit-group-header .collapse-icon {{ color: #64748b; font-size: 0.7rem; transition: transform 0.2s; }}
  .unit-group-header.collapsed .collapse-icon {{ transform: rotate(-90deg); }}
  .unit-group-header code {{ font-size: 0.85rem; color: #60a5fa; }}
  .unit-count {{ margin-left: auto; font-size: 0.75rem; color: #64748b; }}
  .unit-group-body {{ border-top: 1px solid #1e293b; padding: 0.5rem 1rem; display: grid; gap: 0.25rem; }}
  .unit-group-body.hidden {{ display: none; }}
  .unit-item {{ font-size: 0.8rem; color: #94a3b8; padding: 0.2rem 0; }}
  .unit-item code {{ color: #cbd5e1; }}

  /* Table refs */
  .table-refs-list {{ display: flex; flex-wrap: wrap; gap: 0.5rem; max-height: 200px; overflow-y: auto; }}
  .table-refs-list li {{ background: #0f172a; border: 1px solid #334155; border-radius: 4px; padding: 0.2rem 0.5rem; font-size: 0.8rem; color: #94a3b8; list-style: none; }}
  .table-refs-list li code {{ color: #a78bfa; }}

  /* Schema status */
  .schema-status {{ display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; font-size: 0.85rem; }}
  .schema-ok {{ color: #34d399; }}
  .schema-warn {{ color: #fbbf24; }}
  .schema-skip {{ color: #64748b; }}

  /* Fragments */
  .fragment-list {{ display: grid; gap: 0.5rem; }}
  .fragment-item {{ background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 0.5rem 0.75rem; display: flex; align-items: center; gap: 0.75rem; }}
  .fragment-item code {{ color: #60a5fa; font-size: 0.85rem; }}
  .frag-meta {{ font-size: 0.75rem; color: #64748b; }}
  .fragment-more {{ font-size: 0.8rem; color: #64748b; font-style: italic; padding: 0.25rem 0.5rem; }}

  /* Strategy table */
  .strategy-tag {{ background: #1e3a5f; color: #60a5fa; border-radius: 4px; padding: 0.15rem 0.5rem; font-size: 0.75rem; font-weight: 600; }}
  .sort-icon {{ color: #60a5fa; font-size: 0.85rem; }}

  /* Section 4: Relationship */
  .rel-stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.75rem; margin-bottom: 1.5rem; }}
  .rel-stat-card {{ background: #0f172a; border-radius: 8px; padding: 1rem; border: 1px solid #334155; text-align: center; }}
  .rel-stat-card .label {{ font-size: 0.65rem; color: #94a3b8; text-transform: uppercase; margin-bottom: 0.25rem; }}
  .rel-stat-card .value {{ font-size: 1.5rem; font-weight: 700; }}
  .rel-stat-card .sub {{ font-size: 0.7rem; color: #64748b; margin-top: 0.2rem; }}
  .blue {{ color: #60a5fa; }}
  .purple {{ color: #a78bfa; }}
  .green {{ color: #34d399; }}
  .orange {{ color: #fb923c; }}
  .red {{ color: #f87171; }}

  /* Table cards */
  .tables-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 0.75rem; margin-top: 1rem; }}
  .table-card {{ background: #0f172a; border-radius: 8px; padding: 0.85rem; border: 1px solid #334155; }}
  .table-card .name {{ font-weight: 600; font-size: 0.9rem; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.4rem; }}
  .table-card .badge {{ font-size: 0.6rem; padding: 0.15rem 0.4rem; border-radius: 3px; font-weight: 600; }}
  .badge.high {{ background: #7f1d1d; color: #fca5a5; }}
  .badge.medium {{ background: #78350f; color: #fdba74; }}
  .badge.low {{ background: #14532d; color: #86efac; }}
  .table-card .metrics {{ display: flex; gap: 1rem; font-size: 0.75rem; color: #94a3b8; }}
  .table-card .metric {{ display: flex; flex-direction: column; }}
  .table-card .metric span:first-child {{ font-size: 0.6rem; text-transform: uppercase; color: #64748b; }}
  .table-card .metric span:last-child {{ font-weight: 600; color: #e2e8f0; }}
  .table-card .score-bar {{ margin-top: 0.5rem; height: 3px; background: #334155; border-radius: 2px; overflow: hidden; }}
  .table-card .score-fill {{ height: 100%; background: linear-gradient(90deg, #60a5fa, #a78bfa); border-radius: 2px; }}

  /* Relation items */
  .relation-list {{ max-height: 350px; overflow-y: auto; }}
  .relation-item {{ display: flex; align-items: center; gap: 0.6rem; padding: 0.6rem; background: #0f172a; border-radius: 6px; margin-bottom: 0.4rem; font-size: 0.8rem; }}
  .relation-item .source {{ color: #60a5fa; font-weight: 500; }}
  .relation-item .arrow {{ color: #64748b; }}
  .relation-item .target {{ color: #a78bfa; font-weight: 500; }}
  .relation-item .dir {{ color: #94a3b8; font-size: 0.7rem; background: #1e293b; padding: 0.1rem 0.4rem; border-radius: 3px; }}
  .relation-item .conf {{ color: #34d399; font-size: 0.7rem; }}
  .relation-item .explicit {{ color: #fbbf24; font-size: 0.6rem; background: #451a03; padding: 0.1rem 0.3rem; border-radius: 2px; }}

  /* No-data placeholder */
  .no-data {{ text-align: center; color: #64748b; padding: 1.5rem; font-style: italic; }}

  /* Footer */
  .page-footer {{ text-align: center; color: #475569; font-size: 0.75rem; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #1e293b; }}

  @media (max-width: 768px) {{
    .charts-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="container">

  <!-- ==================== HEADER ==================== -->
  <div class="page-header">
    <h1>INIT 阶段报告</h1>
    <p class="subtitle">SQL 扫描与表关系分析</p>
    <div class="meta-badges">
      <div class="meta-badge">Run: <span>{stats.run_id}</span></div>
      <div class="meta-badge">耗时: <span>{stats.duration_seconds:.2f}s</span></div>
      <div class="meta-badge">Mapper文件: <span>{stats.files_count}</span></div>
      <div class="meta-badge">SQL单元: <span>{stats.sql_unit_count}</span></div>
      <div class="meta-badge">表引用: <span>{stats.table_ref_count}</span></div>
      <div class="meta-badge">Schema表: <span>{stats.schema_table_count}</span></div>
      <div class="meta-badge">输出: <span>{stats.file_size_bytes:,} B</span></div>
    </div>
  </div>

  <!-- ==================== SECTION 1: SQL OVERVIEW ==================== -->
  <div class="section">
    <div class="section-header" onclick="toggleSection(this)">
      <h2><span class="collapse-icon">▼</span> [1] SQL 概览</h2>
    </div>
    <div class="section-body">
      <div class="stats-grid">
        {"".join(f'<div class="stat-card"><div class="value" style="color:{stmt_colors.get(t, "#64748b")}">{type_counter.get(t, 0)}</div><div class="label">{t}</div></div>' for t in stmt_labels)}
      </div>

      <div class="charts-grid">
        <div class="chart-card">
          <h3>SQL类型分布</h3>
          <div class="chart-container">
            <canvas id="typeChart"></canvas>
          </div>
        </div>
        <div class="chart-card">
          <h3>Mapper 文件统计</h3>
          <div class="chart-container">
            <canvas id="mapperChart"></canvas>
          </div>
        </div>
      </div>

      <h3 style="font-size:0.85rem;color:#94a3b8;margin:1rem 0 0.5rem;">Mapper 文件概览</h3>
      <table>
        <thead>
          <tr><th>文件</th><th style="text-align:center">语句数</th><th style="text-align:center">片段数</th></tr>
        </thead>
        <tbody>
          {mapper_rows or '<tr><td colspan="3" class="no-data">无可用数据</td></tr>'}
        </tbody>
      </table>

      <h3 style="font-size:0.85rem;color:#94a3b8;margin:1.2rem 0 0.5rem;">SQL 单元列表</h3>
      <div class="unit-groups">
        {unit_cards_html or '<div class="no-data">无SQL单元</div>'}
      </div>

      <h3 style="font-size:0.85rem;color:#94a3b8;margin:1.2rem 0 0.5rem;">表引用 (前 50)</h3>
      <ul class="table-refs-list">
        {table_list_html or '<li class="no-data">无表引用</li>'}
      </ul>
    </div>
  </div>

  <!-- ==================== SECTION 2: SCHEMA ANALYSIS ==================== -->
  <div class="section">
    <div class="section-header collapsed" onclick="toggleSection(this)">
      <h2><span class="collapse-icon">▼</span> [2] Schema 分析</h2>
    </div>
    <div class="section-body hidden">
      <div class="schema-status">
        {"OK" if output.table_schemas else "WARN" if schema_extraction_success else "SKIP"}
        <span class="schema-ok">成功提取 <strong>{len(output.table_schemas)}</strong> 个表的Schema</span>
        {"<span class='schema-warn'>(请检查数据库连接配置)</span>" if not output.table_schemas and schema_extraction_success else ""}
        {"<span class='schema-skip'>表Schema提取已跳过(无数据库连接)</span>" if not schema_extraction_success else ""}
      </div>
      {"<table><thead><tr><th>表名</th><th style='text-align:center'>列数</th></tr></thead><tbody>" + schema_rows + "</tbody></table>" if schema_rows else ""}
      {"<div class='no-data' style='margin-top:1rem;'>无Schema数据</div>" if not schema_rows else ""}

      <div style="margin-top:1rem;padding:0.75rem;background:#0f172a;border-radius:8px;border:1px solid #334155;">
        <div style="font-size:0.8rem;color:#94a3b8;margin-bottom:0.25rem;">WHERE 字段分布</div>
        <div style="font-size:1.2rem;font-weight:700;color:#60a5fa;">{field_distributions_count}</div>
        <div style="font-size:0.75rem;color:#64748b;">个字段已收集分布数据</div>
      </div>
    </div>
  </div>

  <!-- ==================== SECTION 3: SQL FRAGMENTS ==================== -->
  <div class="section">
    <div class="section-header collapsed" onclick="toggleSection(this)">
      <h2><span class="collapse-icon">▼</span> [3] SQL 片段</h2>
    </div>
    <div class="section-body hidden">
      <p style="font-size:0.85rem;color:#94a3b8;margin-bottom:1rem;">
        发现 <strong style="color:#e2e8f0">{len(output.sql_fragments)}</strong> 个可复用片段
      </p>
      <div class="fragment-list">
        {fragment_items or '<div class="no-data">无SQL片段</div>'}
      </div>
    </div>
  </div>

  <!-- ==================== SECTION 4: TABLE RELATIONSHIPS ==================== -->
  <div class="section">
    <div class="section-header" onclick="toggleSection(this)">
      <h2><span class="collapse-icon">▼</span> [4] 表关系分析</h2>
    </div>
    <div class="section-body">
      <div class="rel-stats-grid">
        <div class="rel-stat-card">
          <div class="label">总关系数</div>
          <div class="value blue">{rel_stats.total_relationships}</div>
          <div class="sub">JOIN: {rel_stats.explicit_joins} | WHERE: {rel_stats.implicit_eqs}</div>
        </div>
        <div class="rel-stat-card">
          <div class="label">热点表数量</div>
          <div class="value purple">{len(hotspots)}</div>
          <div class="sub">高: {rel_stats.high_risk_tables} | 中: {rel_stats.medium_risk_tables} | 低: {rel_stats.low_risk_tables}</div>
        </div>
        <div class="rel-stat-card">
          <div class="label">高热度表 (入度)</div>
          <div class="value orange">{rel_stats.tables_with_most_incoming}</div>
          <div class="sub">被引用最多</div>
        </div>
        <div class="rel-stat-card">
          <div class="label">高辐射表 (出度)</div>
          <div class="value green">{rel_stats.tables_with_most_outgoing}</div>
          <div class="sub">引用最多</div>
        </div>
        <div class="rel-stat-card">
          <div class="label">One-to-Many</div>
          <div class="value blue">{rel_stats.one_to_many}</div>
        </div>
        <div class="rel-stat-card">
          <div class="label">Many-to-One</div>
          <div class="value purple">{rel_stats.many_to_one}</div>
        </div>
        <div class="rel-stat-card">
          <div class="label">Many-to-Many</div>
          <div class="value green">{rel_stats.many_to_many}</div>
        </div>
      </div>

      <div class="charts-grid">
        <div class="chart-card">
          <h3>热点表评分 TOP 10</h3>
          <div class="chart-container"><canvas id="hotspotChart"></canvas></div>
        </div>
        <div class="chart-card">
          <h3>关系方向分布</h3>
          <div class="chart-container"><canvas id="directionChart"></canvas></div>
        </div>
      </div>

      <div class="charts-grid">
        <div class="chart-card">
          <h3>热点表 IN/OUT 度</h3>
          <div class="chart-container"><canvas id="inOutChart"></canvas></div>
        </div>
        <div class="chart-card">
          <h3>风险等级分布</h3>
          <div class="chart-container"><canvas id="riskChart"></canvas></div>
        </div>
      </div>

      <h3 style="font-size:0.85rem;color:#94a3b8;margin:0 0 0.75rem;">热点表详情 (TOP 20)</h3>
      <div class="tables-grid">
        {table_cards_html or '<div class="no-data">无热点表数据</div>'}
      </div>

      <h3 style="font-size:0.85rem;color:#94a3b8;margin:1rem 0 0.75rem;">关系详情 (TOP 50, 按置信度)</h3>
      <div class="relation-list">
        {relation_items_html or '<div class="no-data">无关系数据</div>'}
      </div>
    </div>
  </div>

  <!-- ==================== SECTION 5: PARSE STRATEGY ==================== -->
  <div class="section">
    <div class="section-header collapsed" onclick="toggleSection(this)">
      <h2><span class="collapse-icon">▼</span> [5] Parse 策略建议</h2>
    </div>
    <div class="section-body hidden">
      <details style="margin-bottom:0.75rem; font-size:0.8rem; color:#94a3b8;">
        <summary style="cursor:pointer; font-weight:600; color:#cbd5e1; margin-bottom:0.25rem;">Why 3 strategies?</summary>
        <div style="margin-top:0.5rem; padding:0.75rem; background:#0f172a; border-radius:8px; border:1px solid #334155; line-height:1.7;">
          <p style="margin-bottom:0.6rem;"><strong style="color:#60a5fa;">all_combinations</strong> (2^n branches): Full permutation of all conditions. Maximum coverage but exponential growth -- 5 conditions = 32 branches, 8 conditions = 256 branches, 10 conditions = 1024 branches. Selected when 2^n &lt;= 50. &quot;all_combinations&quot; (全组合策略): 生成所有条件的全排列, 提供最完整的覆盖. 但分支数随条件数指数增长: 5个条件=32个分支, 8个条件=256个分支, 10个条件=1024个分支. 当2^n小于等于50时选择此策略.</p>
          <p style="margin-bottom:0.6rem;"><strong style="color:#a78bfa;">ladder</strong> (weighted sampling): Activated when 2^n exceeds the threshold. Phased weighted coverage -- (1) all-false baseline (2) each condition true individually (3) high-risk pairs. Controls branch count while covering critical risks. &quot;ladder&quot; (阶梯策略): 当2^n超过阈值时激活, 采用加权采样分阶段覆盖: (1)全false基线 (2)逐个条件为true (3)高风险条件对. 在控制分支数量的同时确保关键风险被覆盖.</p>
          <p><strong style="color:#34d399;">pairwise</strong> (pairs only): When conditions &gt; 8, tests each condition individually (n branches, linear growth), suitable for large condition counts requiring fast validation. &quot;pairwise&quot; (配对策略): 当条件数超过8时, 仅测试每个条件单独为true和false的情况, 分支数随条件数线性增长. 适用于大规模条件数的快速验证.</p>
        </div>
      </details>
      <table id="strategyTable">
        <thead>
          <tr>
            <th>SQL Unit</th>
            <th style="text-align:center; cursor:pointer; user-select:none;" onclick="sortStrategyTable()">
              条件数 <span class="sort-icon" id="sortIcon">↓</span>
            </th>
            <th>
              建议策略
              <select id="strategyFilter" onchange="filterStrategyTable(this.value)" style="margin-left:0.5rem; background:#0f172a; border:1px solid #334155; border-radius:4px; color:#94a3b8; font-size:0.75rem; padding:0.15rem 0.4rem;">
                <option value="all">全部</option>
                <option value="all_combinations">all_combinations</option>
                <option value="ladder">ladder</option>
                <option value="pairwise">pairwise</option>
              </select>
            </th>
          </tr>
        </thead>
        <tbody id="strategyTableBody">
          {strategy_rows or '<tr><td colspan="3" class="no-data">无SQL单元</td></tr>'}
        </tbody>
      </table>
      <p style="font-size:0.75rem;color:#475569;margin-top:0.5rem;" id="strategyTableInfo" data-total="{strategy_total}"></p>
    </div>
  </div>

  <!-- ==================== FOOTER ==================== -->
  <div class="page-footer">
    由 SQL Optimizer 生成 | {timestamp}
  </div>

</div>

<script>
  // Section collapse/expand
  function toggleSection(header) {{
    header.classList.toggle('collapsed');
    header.nextElementSibling.classList.toggle('hidden');
  }}

  // Unit group collapse/expand
  function toggleGroup(header) {{
    header.classList.toggle('collapsed');
    header.nextElementSibling.classList.toggle('hidden');
  }}

  // Strategy filter - actually show/hide rows
  let strategySortDir = 'desc';
  function sortStrategyTable() {{
    strategySortDir = strategySortDir === 'desc' ? 'asc' : 'desc';
    const icon = document.getElementById('sortIcon');
    if (icon) icon.textContent = strategySortDir === 'desc' ? '↓' : '↑';
    const tbody = document.getElementById('strategyTableBody');
    if (!tbody) return;
    const rows = Array.from(tbody.querySelectorAll('tr[data-strategy]'));
    const filter = document.getElementById('strategyFilter');
    const currentFilter = filter ? filter.value : 'all';
    rows.sort((a, b) => {{
      const aCond = parseInt(a.querySelector('td:nth-child(2)').textContent, 10);
      const bCond = parseInt(b.querySelector('td:nth-child(2)').textContent, 10);
      return strategySortDir === 'desc' ? bCond - aCond : aCond - bCond;
    }});
    rows.forEach(row => {{
      const visible = currentFilter === 'all' || row.dataset.strategy === currentFilter;
      row.style.display = visible ? '' : 'none';
      tbody.appendChild(row);
    }});
    updateStrategyTableInfo();
  }}

  function filterStrategyTable(strategy) {{
    const tbody = document.getElementById('strategyTableBody');
    if (!tbody) return;
    const rows = Array.from(tbody.querySelectorAll('tr[data-strategy]'));
    rows.forEach(row => {{
      if (strategy === 'all' || row.dataset.strategy === strategy) {{
        row.style.display = '';
      }} else {{
        row.style.display = 'none';
      }}
    }});
    updateStrategyTableInfo();
  }}

  function updateStrategyTableInfo() {{
    const tbody = document.getElementById('strategyTableBody');
    const info = document.getElementById('strategyTableInfo');
    if (!tbody || !info) return;
    const total = parseInt(info.dataset.total || '0', 10);
    const rows = tbody.querySelectorAll('tr[data-strategy]');
    let shown = 0;
    for (const r of rows) {{ if (r.style.display !== 'none') shown++; }}
    const msg = '显示 ' + shown + ' / ' + total + ' 条';
    info.textContent = msg;
  }}

  const chartColors = {{
    blue: '#60a5fa',
    purple: '#a78bfa',
    green: '#34d399',
    orange: '#fb923c',
    red: '#f87171',
    gray: '#64748b',
  }};

  // SQL Type Doughnut
  new Chart(document.getElementById('typeChart'), {{
    type: 'doughnut',
    data: {{
      labels: {stmt_labels},
      datasets: [{{
        data: {stmt_data},
        backgroundColor: {stmt_colors_list},
        borderWidth: 0,
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#94a3b8', padding: 12 }} }} }}
    }}
  }});

  // Mapper statement count bar
  const mapperLabels = {json.dumps([fm.xml_path.split("/")[-1] for fm in (output.xml_mappings.files if output.xml_mappings else [])[:8]])};
  const mapperStmtCounts = {json.dumps([len(fm.statements) for fm in (output.xml_mappings.files if output.xml_mappings else [])[:8]])};
  new Chart(document.getElementById('mapperChart'), {{
    type: 'bar',
    data: {{
      labels: mapperLabels,
      datasets: [{{
        label: '语句数',
        data: mapperStmtCounts,
        backgroundColor: 'rgba(96,165,250,0.6)',
        borderColor: '#60a5fa',
        borderWidth: 1,
        borderRadius: 4,
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8', font: {{ size: 10 }} }} }},
        y: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8' }}, beginAtZero: true }}
      }}
    }}
  }});

  // Hotspot bar chart
  new Chart(document.getElementById('hotspotChart'), {{
    type: 'bar',
    data: {{
      labels: {hotspot_labels},
      datasets: [{{
        label: '热点评分', data: {hotspot_scores},
        backgroundColor: 'rgba(96,165,250,0.6)', borderColor: '#60a5fa', borderWidth: 1, borderRadius: 4,
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8', font: {{ size: 9 }} }} }},
        y: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8' }} }}
      }}
    }}
  }});

  // Direction doughnut
  new Chart(document.getElementById('directionChart'), {{
    type: 'doughnut',
    data: {{
      labels: ['One-to-Many', 'Many-to-One', 'Many-to-Many'],
      datasets: [{{
        data: {direction_data},
        backgroundColor: [chartColors.blue, chartColors.purple, chartColors.green], borderWidth: 0,
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#94a3b8', padding: 12 }} }} }}
    }}
  }});

  // IN/OUT grouped bar
  new Chart(document.getElementById('inOutChart'), {{
    type: 'bar',
    data: {{
      labels: {hotspot_labels},
      datasets: [
        {{ label: 'Incoming', data: {hotspot_incoming}, backgroundColor: 'rgba(167,139,250,0.6)', borderColor: '#a78bfa', borderWidth: 1, borderRadius: 4 }},
        {{ label: 'Outgoing', data: {hotspot_outgoing}, backgroundColor: 'rgba(52,211,153,0.6)', borderColor: '#34d399', borderWidth: 1, borderRadius: 4 }}
      ]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
      scales: {{
        x: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8', font: {{ size: 9 }} }} }},
        y: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8' }} }}
      }}
    }}
  }});

  // Risk pie
  new Chart(document.getElementById('riskChart'), {{
    type: 'pie',
    data: {{
      labels: ['高风险', '中风险', '低风险'],
      datasets: [{{
        data: {risk_data},
        backgroundColor: [chartColors.red, chartColors.orange, chartColors.green], borderWidth: 0,
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#94a3b8', padding: 12 }} }} }}
    }}
  }});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Render helpers (for table cards and relation items)
# ---------------------------------------------------------------------------


def _stmt_icon(stmt_type: str) -> str:
    icons = {"SELECT": "🟢", "INSERT": "🔵", "UPDATE": "🟡", "DELETE": "🔴"}
    return icons.get(stmt_type, "⚪")


def _render_table_card(h: TableHotspot) -> str:
    max_score = 25.0
    bar_width = min(h.hotspot_score / max_score * 100, 100)
    co_tables = ", ".join(h.co_occurrence_tables[:3])
    if len(h.co_occurrence_tables) > 3:
        co_tables += f" +{len(h.co_occurrence_tables) - 3}"
    return f"""
    <div class="table-card">
      <div class="name">
        {h.table_name}
        <span class="badge {h.risk_level}">{h.risk_level.upper()}</span>
      </div>
      <div class="metrics">
        <div class="metric"><span>Incoming</span><span>{h.incoming_ref_count}</span></div>
        <div class="metric"><span>Outgoing</span><span>{h.outgoing_ref_count}</span></div>
        <div class="metric"><span>Score</span><span>{h.hotspot_score:.1f}</span></div>
      </div>
      <div class="score-bar"><div class="score-fill" style="width:{bar_width}%"></div></div>
    </div>"""


def _render_relation(r: TableRelationship) -> str:
    explicit_tag = '<span class="explicit">EXPLICIT</span>' if r.is_explicit_join else ""
    conf_pct = int(r.confidence * 100)
    sql_count = len(r.sql_keys)
    return f"""
    <div class="relation-item">
      <span class="source">{r.source_table}</span>
      <span class="arrow">→</span>
      <span class="target">{r.target_table}</span>
      <span class="dir">{r.direction}</span>
      <span class="conf">conf={conf_pct}%</span>
      <span class="conf">sqls={sql_count}</span>
      {explicit_tag}
    </div>"""
