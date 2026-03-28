"""Generate visual HTML report for table relationship analysis."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Dict, List

from sqlopt.contracts.init import TableHotspot, TableRelationship


@dataclass
class RelationshipReportStats:
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


def generate_relationship_report(
    relationships: List[TableRelationship],
    hotspots: Dict[str, TableHotspot],
    output_path: str,
) -> None:
    """Generate an HTML report with charts for table relationship analysis."""
    stats = _compute_stats(relationships, hotspots)
    hotspots_sorted = sorted(hotspots.values(), key=lambda h: h.hotspot_score, reverse=True)
    rels_sorted = sorted(relationships, key=lambda r: r.confidence, reverse=True)

    html_content = _build_html(stats, hotspots_sorted, rels_sorted)

    with pathlib.Path(output_path).open("w", encoding="utf-8") as f:
        f.write(html_content)


def _compute_stats(
    relationships: List[TableRelationship],
    hotspots: Dict[str, TableHotspot],
) -> RelationshipReportStats:
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

    return RelationshipReportStats(
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


def _build_html(
    stats: RelationshipReportStats,
    hotspots: List[TableHotspot],
    relationships: List[TableRelationship],
) -> str:
    # JSON data for charts
    hotspot_labels = [h.table_name for h in hotspots[:10]]
    hotspot_incoming = [h.incoming_ref_count for h in hotspots[:10]]
    hotspot_outgoing = [h.outgoing_ref_count for h in hotspots[:10]]
    hotspot_scores = [h.hotspot_score for h in hotspots[:10]]
    direction_data = [stats.one_to_many, stats.many_to_one, stats.many_to_many]
    risk_data = [stats.high_risk_tables, stats.medium_risk_tables, stats.low_risk_tables]

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>表关系分析报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; padding: 2rem; }}
  .container {{ max-width: 1400px; margin: 0 auto; }}
  h1 {{ font-size: 2rem; font-weight: 700; margin-bottom: 0.5rem; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  .subtitle {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }}

  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
  .stat-card {{ background: #1e293b; border-radius: 12px; padding: 1.25rem; border: 1px solid #334155; }}
  .stat-card .label {{ font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }}
  .stat-card .value {{ font-size: 2rem; font-weight: 700; }}
  .stat-card .value.blue {{ color: #60a5fa; }}
  .stat-card .value.purple {{ color: #a78bfa; }}
  .stat-card .value.green {{ color: #34d399; }}
  .stat-card .value.orange {{ color: #fb923c; }}
  .stat-card .value.red {{ color: #f87171; }}
  .stat-card .sub {{ font-size: 0.75rem; color: #64748b; margin-top: 0.25rem; }}

  .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }}
  .chart-card {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }}
  .chart-card h2 {{ font-size: 1rem; font-weight: 600; margin-bottom: 1rem; color: #f1f5f9; }}
  .chart-container {{ position: relative; height: 280px; }}

  .tables-section {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; margin-bottom: 2rem; }}
  .tables-section h2 {{ font-size: 1rem; font-weight: 600; margin-bottom: 1rem; color: #f1f5f9; }}
  .tables-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; }}
  .table-card {{ background: #0f172a; border-radius: 8px; padding: 1rem; border: 1px solid #334155; }}
  .table-card .name {{ font-weight: 600; font-size: 1rem; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem; }}
  .table-card .badge {{ font-size: 0.65rem; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600; }}
  .badge.high {{ background: #7f1d1d; color: #fca5a5; }}
  .badge.medium {{ background: #78350f; color: #fdba74; }}
  .badge.low {{ background: #14532d; color: #86efac; }}
  .table-card .metrics {{ display: flex; gap: 1.5rem; font-size: 0.8rem; color: #94a3b8; }}
  .table-card .metric {{ display: flex; flex-direction: column; }}
  .table-card .metric span:first-child {{ font-size: 0.65rem; text-transform: uppercase; color: #64748b; }}
  .table-card .metric span:last-child {{ font-weight: 600; color: #e2e8f0; }}
  .table-card .score-bar {{ margin-top: 0.75rem; height: 4px; background: #334155; border-radius: 2px; overflow: hidden; }}
  .table-card .score-fill {{ height: 100%; background: linear-gradient(90deg, #60a5fa, #a78bfa); border-radius: 2px; }}

  .relations-section {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }}
  .relations-section h2 {{ font-size: 1rem; font-weight: 600; margin-bottom: 1rem; color: #f1f5f9; }}
  .relation-list {{ max-height: 400px; overflow-y: auto; }}
  .relation-item {{ display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem; background: #0f172a; border-radius: 8px; margin-bottom: 0.5rem; font-size: 0.85rem; }}
  .relation-item .arrow {{ color: #64748b; }}
  .relation-item .source {{ color: #60a5fa; font-weight: 500; }}
  .relation-item .target {{ color: #a78bfa; font-weight: 500; }}
  .relation-item .dir {{ color: #94a3b8; font-size: 0.75rem; background: #1e293b; padding: 0.15rem 0.5rem; border-radius: 4px; }}
  .relation-item .conf {{ color: #34d399; font-size: 0.75rem; }}
  .relation-item .explicit {{ color: #fbbf24; font-size: 0.65rem; background: #451a03; padding: 0.1rem 0.4rem; border-radius: 3px; }}

  .no-data {{ text-align: center; color: #64748b; padding: 2rem; }}
</style>
</head>
<body>
<div class="container">
  <h1>表关系分析报告</h1>
  <p class="subtitle">基于 SQL 语句推断的表关联关系与热点分析</p>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="label">总关系数</div>
      <div class="value blue">{stats.total_relationships}</div>
      <div class="sub">显式 JOIN: {stats.explicit_joins} | 隐式 WHERE: {stats.implicit_eqs}</div>
    </div>
    <div class="stat-card">
      <div class="label">热点表数量</div>
      <div class="value purple">{len(hotspots)}</div>
      <div class="sub">高风险: {stats.high_risk_tables} | 中风险: {stats.medium_risk_tables} | 低风险: {stats.low_risk_tables}</div>
    </div>
    <div class="stat-card">
      <div class="label">高热度表 (入度)</div>
      <div class="value orange">{stats.tables_with_most_incoming}</div>
      <div class="sub">被引用最多的表</div>
    </div>
    <div class="stat-card">
      <div class="label">高辐射表 (出度)</div>
      <div class="value green">{stats.tables_with_most_outgoing}</div>
      <div class="sub">引用最多的表</div>
    </div>
    <div class="stat-card">
      <div class="label">One-to-Many</div>
      <div class="value blue">{stats.one_to_many}</div>
    </div>
    <div class="stat-card">
      <div class="label">Many-to-One</div>
      <div class="value purple">{stats.many_to_one}</div>
    </div>
    <div class="stat-card">
      <div class="label">Many-to-Many</div>
      <div class="value green">{stats.many_to_many}</div>
    </div>
  </div>

  <div class="charts-grid">
    <div class="chart-card">
      <h2>热点表评分 TOP 10</h2>
      <div class="chart-container">
        <canvas id="hotspotChart"></canvas>
      </div>
    </div>
    <div class="chart-card">
      <h2>关系方向分布</h2>
      <div class="chart-container">
        <canvas id="directionChart"></canvas>
      </div>
    </div>
  </div>

  <div class="charts-grid">
    <div class="chart-card">
      <h2>热点表 IN/OUT 度</h2>
      <div class="chart-container">
        <canvas id="inOutChart"></canvas>
      </div>
    </div>
    <div class="chart-card">
      <h2>风险等级分布</h2>
      <div class="chart-container">
        <canvas id="riskChart"></canvas>
      </div>
    </div>
  </div>

  <div class="tables-section">
    <h2>热点表详情</h2>
    <div class="tables-grid">
      {"".join(_render_table_card(h) for h in hotspots[:20])}
    </div>
  </div>

  <div class="relations-section">
    <h2>关系详情 (按置信度排序)</h2>
    <div class="relation-list">
      {"".join(_render_relation(r) for r in relationships[:50])}
    </div>
  </div>
</div>

<script>
  const chartColors = {{
    blue: '#60a5fa',
    purple: '#a78bfa',
    green: '#34d399',
    orange: '#fb923c',
    red: '#f87171',
    gray: '#64748b',
  }}

  new Chart(document.getElementById('hotspotChart'), {{
    type: 'bar',
    data: {{
      labels: {hotspot_labels},
      datasets: [{{
        label: '热点评分',
        data: {hotspot_scores},
        backgroundColor: 'rgba(96, 165, 250, 0.6)',
        borderColor: '#60a5fa',
        borderWidth: 1,
        borderRadius: 4,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8' }} }},
        y: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8' }} }}
      }}
    }}
  }});

  new Chart(document.getElementById('directionChart'), {{
    type: 'doughnut',
    data: {{
      labels: ['One-to-Many', 'Many-to-One', 'Many-to-Many'],
      datasets: [{{
        data: {direction_data},
        backgroundColor: [chartColors.blue, chartColors.purple, chartColors.green],
        borderWidth: 0,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ position: 'bottom', labels: {{ color: '#94a3b8', padding: 16 }} }}
      }}
    }}
  }});

  new Chart(document.getElementById('inOutChart'), {{
    type: 'bar',
    data: {{
      labels: {hotspot_labels},
      datasets: [
        {{
          label: 'Incoming',
          data: {hotspot_incoming},
          backgroundColor: 'rgba(167, 139, 250, 0.6)',
          borderColor: '#a78bfa',
          borderWidth: 1,
          borderRadius: 4,
        }},
        {{
          label: 'Outgoing',
          data: {hotspot_outgoing},
          backgroundColor: 'rgba(52, 211, 153, 0.6)',
          borderColor: '#34d399',
          borderWidth: 1,
          borderRadius: 4,
        }}
      ]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
      scales: {{
        x: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8' }} }},
        y: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8' }} }}
      }}
    }}
  }});

  new Chart(document.getElementById('riskChart'), {{
    type: 'pie',
    data: {{
      labels: ['高风险', '中风险', '低风险'],
      datasets: [{{
        data: {risk_data},
        backgroundColor: [chartColors.red, chartColors.orange, chartColors.green],
        borderWidth: 0,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ position: 'bottom', labels: {{ color: '#94a3b8', padding: 16 }} }}
      }}
    }}
  }});
</script>
</body>
</html>"""


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
        <div class="metric">
          <span>Incoming</span>
          <span>{h.incoming_ref_count}</span>
        </div>
        <div class="metric">
          <span>Outgoing</span>
          <span>{h.outgoing_ref_count}</span>
        </div>
        <div class="metric">
          <span>Score</span>
          <span>{h.hotspot_score:.1f}</span>
        </div>
      </div>
      <div class="score-bar">
        <div class="score-fill" style="width: {bar_width}%"></div>
      </div>
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
