"""Generate rich HTML reports for each pipeline stage."""

from __future__ import annotations

import html as html_escape
import pathlib
from typing import Any

from sqlopt.common.run_paths import RunPaths
from sqlopt.contracts.optimize import OptimizeOutput
from sqlopt.contracts.parse import ParseOutput
from sqlopt.contracts.recognition import RecognitionOutput
from sqlopt.contracts.result import ResultOutput

CHART_JS = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>'

DARK_THEME = """
<style>
    * { box-sizing: border-box; }
    body { background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 20px; }
    .container { max-width: 1400px; margin: 0 auto; }
    h1 { color: #f8fafc; font-size: 1.5rem; margin-bottom: 1rem; }
    h2 { color: #e2e8f0; font-size: 1.125rem; margin: 1.5rem 0 0.75rem; border-bottom: 1px solid #334155; padding-bottom: 0.5rem; }
    h3 { color: #cbd5e1; font-size: 1rem; margin: 1rem 0 0.5rem; }
    .card { background: #1e293b; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
    .stat { display: inline-block; margin-right: 1.5rem; }
    .stat-value { font-size: 1.5rem; font-weight: bold; color: #3b82f6; }
    .stat-label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; }
    table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
    th { text-align: left; padding: 0.75rem 0.5rem; background: #334155; color: #e2e8f0; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; cursor: pointer; user-select: none; }
    th:hover { background: #475569; }
    th::after { content: ' ↕'; opacity: 0.3; }
    th.asc::after { content: ' ↑'; opacity: 1; }
    th.desc::after { content: ' ↓'; opacity: 1; }
    td { padding: 0.5rem; border-bottom: 1px solid #334155; font-size: 0.875rem; }
    tr:hover { background: #1e3a5f; }
    .badge { display: inline-block; padding: 0.125rem 0.5rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
    .badge-high { background: #dc2626; color: white; }
    .badge-medium { background: #f59e0b; color: white; }
    .badge-low { background: #22c55e; color: white; }
    .badge-select { background: #3b82f6; color: white; }
    .badge-insert { background: #22c55e; color: white; }
    .badge-update { background: #f59e0b; color: white; }
    .badge-delete { background: #dc2626; color: white; }
    .badge-info { background: #6366f1; color: white; }
    .badge-warning { background: #f59e0b; color: white; }
    .risk-flag { display: inline-block; background: #dc2626; color: white; padding: 0.125rem 0.375rem; border-radius: 4px; font-size: 0.625rem; margin-right: 0.25rem; }
    .risk-flag-medium { background: #f59e0b; }
    .risk-flag-low { background: #22c55e; }
    .chart-container { height: 280px; margin: 1rem 0; position: relative; }
    .charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
    .empty { color: #64748b; font-style: italic; }
    pre { background: #0f172a; padding: 0.75rem; border-radius: 4px; overflow-x: auto; font-size: 0.75rem; }
    code { color: #a5b4fc; }
    .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
    .rank-high { color: #dc2626; font-weight: bold; }
    .rank-medium { color: #f59e0b; }
    .rank-low { color: #22c55e; }
    .expand-btn { cursor: pointer; color: #3b82f6; margin-right: 0.5rem; font-weight: bold; }
    .expand-btn:hover { color: #60a5fa; }
    .child-row { display: none; }
    .child-row.expanded { display: table-row; }
    .child-row td { background: #1a2744; padding-left: 2rem; font-size: 0.8125rem; }
    .group-header { cursor: pointer; }
    .group-header:hover { background: #1e3a5f; }
    .group-summary { display: inline-block; background: #334155; padding: 0.125rem 0.5rem; border-radius: 4px; font-size: 0.75rem; margin-left: 0.5rem; }
    .sql-text { max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; }
    .sql-text:hover { white-space: normal; word-break: break-all; }
    .tooltip { position: relative; }
    .tooltip::after { content: attr(data-full); display: none; position: absolute; background: #1e293b; border: 1px solid #475569; padding: 0.5rem; border-radius: 4px; font-size: 0.75rem; z-index: 100; width: 400px; right: 0; top: 100%; }
    .tooltip:hover::after { display: block; }
    .funnel { display: flex; align-items: center; gap: 1rem; margin: 1rem 0; }
    .funnel-step { flex: 1; background: linear-gradient(135deg, #334155 0%, #1e293b 100%); border-radius: 8px; padding: 1rem; text-align: center; position: relative; }
    .funnel-step::after { content: '→'; position: absolute; right: -1.5rem; top: 50%; transform: translateY(-50%); color: #64748b; font-size: 1.5rem; }
    .funnel-step:last-child::after { display: none; }
    .funnel-value { font-size: 2rem; font-weight: bold; color: #3b82f6; }
    .funnel-label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; margin-top: 0.25rem; }
    .funnel-reduction { color: #22c55e; font-size: 0.75rem; }
    .branch-detail { background: #1a2744; padding: 0.75rem; border-radius: 4px; margin: 0.25rem 0; }
    .branch-detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
    .branch-path { color: #a5b4fc; font-family: monospace; }
    .branch-condition { color: #94a3b8; font-size: 0.8125rem; margin: 0.25rem 0; }
    .branch-reasons { margin-top: 0.5rem; }
    .reason-tag { display: inline-block; background: #334155; padding: 0.125rem 0.5rem; border-radius: 4px; font-size: 0.6875rem; margin-right: 0.25rem; margin-bottom: 0.25rem; }
    .reason-tag.high { background: #dc262640; color: #fca5a5; border: 1px solid #dc2626; }
    .reason-tag.medium { background: #f59e0b40; color: #fcd34d; border: 1px solid #f59e0b; }
    .strategy-tag { display: inline-block; background: #6366f140; color: #a5b4fc; padding: 0.125rem 0.5rem; border-radius: 4px; font-size: 0.6875rem; margin-left: 0.5rem; }
    .metric-pair { display: flex; gap: 2rem; margin: 0.5rem 0; }
    .metric { text-align: center; }
    .metric-value { font-size: 1.25rem; font-weight: bold; }
    .metric-label { font-size: 0.6875rem; color: #64748b; text-transform: uppercase; }
    .progress-bar { height: 8px; background: #334155; border-radius: 4px; overflow: hidden; margin: 0.25rem 0; display: flex; }
    .progress-fill { height: 100%; border-radius: 4px; transition: width 0.3s; flex-shrink: 0; }
    .progress-fill.high { background: #dc2626; }
    .progress-fill.medium { background: #f59e0b; }
    .progress-fill.low { background: #22c55e; }
    .sql-preview { background: #0f172a; padding: 0.5rem; border-radius: 4px; font-family: monospace; font-size: 0.75rem; color: #a5b4fc; margin-top: 0.5rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-height: 60px; }
    .sort-btn { cursor: pointer; background: #334155; color: #94a3b8; padding: 0.125rem 0.5rem; border-radius: 4px; font-size: 0.6875rem; margin-left: 0.25rem; user-select: none; }
    .sort-btn:hover { background: #475569; color: #e2e8f0; }
    .sort-btn.asc, .sort-btn.desc { background: #3b82f6; color: white; }
    .branch-list { margin-top: 0.5rem; }
    .collapsible-unit .unit-body { display: none; }
    .collapsible-unit.expanded .unit-body { display: block; }
    .unit-header { cursor: pointer; padding: 0.25rem; }
    .unit-header:hover { background: #33415540; border-radius: 0.375rem; }
    .collapse-icon { display: inline-block; transition: transform 0.2s; font-size: 0.75rem; color: #64748b; margin-right: 0.25rem; }
    .collapsible-unit.expanded .collapse-icon { transform: rotate(90deg); }
</style>
"""

BASE_JS = """
<script>
function initSortableBranches(card) {
    card.querySelectorAll('.sort-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const sortKey = this.dataset.sort;
            const isAsc = this.classList.contains('asc');
            const newAsc = !isAsc;
            const container = card.querySelector('.branch-list');
            if (!container) return;
            const branches = Array.from(container.querySelectorAll('.branch-detail'));
            branches.sort((a, b) => {
                let aVal, bVal;
                if (sortKey === 'risk') {
                    aVal = parseFloat(a.dataset.riskScore) || 0;
                    bVal = parseFloat(b.dataset.riskScore) || 0;
                } else if (sortKey === 'path') {
                    aVal = a.dataset.pathId || '';
                    bVal = b.dataset.pathId || '';
                }
                if (sortKey === 'risk') {
                    return newAsc ? aVal - bVal : bVal - aVal;
                }
                return newAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
            });
            card.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('asc', 'desc'));
            this.classList.add(newAsc ? 'asc' : 'desc');
            branches.forEach(b => container.appendChild(b));
        });
    });
}

function getRiskLevel(score) {
    if (score === null || score === undefined) return { level: 'unknown', badgeClass: '' };
    if (score >= 0.7) return { level: 'high', badgeClass: 'badge-high' };
    if (score >= 0.4) return { level: 'medium', badgeClass: 'badge-medium' };
    return { level: 'low', badgeClass: 'badge-low' };
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderBranches(unitCard) {
    const branchList = unitCard.querySelector('.branch-list');
    if (!branchList || branchList.dataset.loaded === 'true' || branchList.dataset.loading === 'true') return;

    const jsonPath = unitCard.dataset.jsonPath;
    if (!jsonPath) return;

    branchList.dataset.loading = 'true';
    branchList.innerHTML = '<div style="color: #94a3b8; padding: 1rem; text-align: center;">加载中...</div>';

    fetch(jsonPath)
        .then(r => {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        })
        .then(data => {
            const branches = data.branches || [];

            if (branches.length === 0) {
                branchList.innerHTML = '<div style="color: #64748b; padding: 1rem; font-style: italic;">无分支数据</div>';
                branchList.dataset.loaded = 'true';
                branchList.dataset.loading = '';
                return;
            }

            branches.sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));

            let html = '';
            branches.forEach(b => {
                const risk = getRiskLevel(b.risk_score);
                const scoreStr = b.risk_score !== null && b.risk_score !== undefined ? b.risk_score.toFixed(2) : '-';
                const riskScoreVal = b.risk_score !== null && b.risk_score !== undefined ? b.risk_score : '0';
                const safeSql = escapeHtml(b.expanded_sql || '');
                const sqlPreview = safeSql.length > 100 ? safeSql.substring(0, 100) + '...' : safeSql;
                const safePathId = escapeHtml(b.path_id || '');
                const safeCond = escapeHtml(b.condition || '');
                const branchType = b.branch_type || (b.active_conditions && b.active_conditions.length > 0 ? '动态' : '静态');

                html += '<div class="branch-detail" data-risk-score="' + riskScoreVal + '" data-path-id="' + safePathId + '">';
                html += '<div class="branch-detail-header">';
                html += '<span><span class="branch-path">' + safePathId + '</span> ';
                html += '<span class="badge ' + risk.badgeClass + '">' + risk.level.toUpperCase() + '</span> ';
                html += '<span style="color: #94a3b8;">' + scoreStr + '</span></span>';
                html += '<span class="badge badge-info">' + escapeHtml(branchType) + '</span>';
                html += '</div>';

                if (b.condition) {
                    html += '<div class="branch-condition">条件: ' + (safeCond.length > 80 ? safeCond.substring(0, 80) + '...' : safeCond) + '</div>';
                }

                if (b.risk_flags && b.risk_flags.length > 0) {
                    html += '<div style="margin-top: 0.5rem;">';
                    b.risk_flags.forEach(f => {
                        const fc = risk.level === 'high' ? 'high' : risk.level === 'medium' ? 'medium' : '';
                        html += '<span class="reason-tag ' + fc + '">' + escapeHtml(f) + '</span>';
                    });
                    html += '</div>';
                }

                if (b.score_reasons && b.score_reasons.length > 0) {
                    html += '<div class="branch-reasons">';
                    b.score_reasons.forEach(r => {
                        html += '<span class="reason-tag">' + escapeHtml(r) + '</span>';
                    });
                    html += '</div>';
                }

                html += '<div class="sql-preview" title="' + safeSql + '">' + sqlPreview + '</div>';
                html += '</div>';
            });

            branchList.innerHTML = html;
            branchList.dataset.loaded = 'true';
            branchList.dataset.loading = '';
            initSortableBranches(unitCard);
        })
        .catch(err => {
            branchList.innerHTML = '<div style="color: #dc2626; padding: 1rem;">加载失败: ' + escapeHtml(err.message) + '</div>';
            branchList.dataset.loading = '';
        });
}

function toggleUnit(header) {
    const card = header.closest('.collapsible-unit');
    if (!card) return;
    const wasExpanded = card.classList.contains('expanded');
    card.classList.toggle('expanded');
    if (!wasExpanded) {
        renderBranches(card);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.card[data-sortable]').forEach(initSortableBranches);
});
</script>
"""


def _get_risk_level(score: float | None) -> tuple[str, str]:
    if score is None:
        return "unknown", ""
    if score >= 0.7:
        return "high", "badge-high"
    if score >= 0.4:
        return "medium", "badge-medium"
    return "low", "badge-low"


def generate_parse_report(output: ParseOutput, output_path: str) -> None:
    total_units = len(output.sql_units_with_branches)
    total_branches = sum(len(u.branches) for u in output.sql_units_with_branches)

    # Aggregate stats
    high_risk = sum(
        1 for u in output.sql_units_with_branches for b in u.branches if b.risk_score and b.risk_score >= 0.7
    )
    medium_risk = sum(
        1 for u in output.sql_units_with_branches for b in u.branches if b.risk_score and 0.4 <= b.risk_score < 0.7
    )
    low_risk = sum(1 for u in output.sql_units_with_branches for b in u.branches if b.risk_score and b.risk_score < 0.4)
    no_score = total_branches - high_risk - medium_risk - low_risk

    theoretical_branches = sum(u.theoretical_branches for u in output.sql_units_with_branches)

    # Branch type distribution
    branch_types: dict[str, int] = {}
    for u in output.sql_units_with_branches:
        for b in u.branches:
            bt = b.branch_type or "unknown"
            branch_types[bt] = branch_types.get(bt, 0) + 1

    # Risk flags distribution
    all_flags: dict[str, int] = {}
    for u in output.sql_units_with_branches:
        for b in u.branches:
            for f in b.risk_flags:
                all_flags[f] = all_flags.get(f, 0) + 1

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>解析阶段报告</title>
    {CHART_JS}
    <style>{DARK_THEME}</style>
</head>
<body>
<div class="container">
    <h1>解析阶段报告</h1>

    <div class="summary-grid">
        <div class="card">
            <div class="stat"><div class="stat-value">{total_units}</div><div class="stat-label">SQL单元</div></div>
            <div class="stat"><div class="stat-value">{total_branches}</div><div class="stat-label">实际分支</div></div>
            <div class="stat"><div class="stat-value">{theoretical_branches}</div><div class="stat-label">理论分支</div></div>
            <div class="stat"><div class="stat-value">{high_risk}</div><div class="stat-label">高风险</div></div>
        </div>
    </div>

    <h2>分支筛选漏斗</h2>
    <div class="card">
        <div class="funnel">
            <div class="funnel-step">
                <div class="funnel-value">{theoretical_branches}</div>
                <div class="funnel-label">理论分支</div>
                <div class="funnel-reduction">100%</div>
            </div>
            <div class="funnel-step">
                <div class="funnel-value">{total_branches}</div>
                <div class="funnel-label">风险评估后</div>
                <div class="funnel-reduction">-{int((1 - total_branches / max(theoretical_branches, 1)) * 100)}%%</div>
            </div>
            <div class="funnel-step">
                <div class="funnel-value">{high_risk}</div>
                <div class="funnel-label">高风险保留</div>
                <div class="funnel-reduction">-{int((1 - high_risk / max(total_branches, 1)) * 100)}%%</div>
            </div>
        </div>
        <p style="color: #94a3b8; font-size: 0.875rem; margin-top: 1rem;">
            通过 <strong>风险评分策略</strong> 从理论 {theoretical_branches} 个分支中筛选出 <strong>{total_branches}</strong> 个进行优化分析,
            其中 <strong>{high_risk}</strong> 个为高风险分支需要重点关注。
        </p>
    </div>

    <div class="charts-grid">
        <div class="card">
            <h3>风险等级分布</h3>
            <div class="chart-container"><canvas id="riskChart"></canvas></div>
        </div>
        <div class="card">
            <h3>风险标志分布</h3>
            <div class="chart-container"><canvas id="flagsChart"></canvas></div>
        </div>
    </div>

    <h2>各单元分支详情</h2>
"""

    for unit in output.sql_units_with_branches:
        theoretical = unit.theoretical_branches if unit.theoretical_branches > 0 else 1
        unit_high = sum(1 for b in unit.branches if b.risk_score and b.risk_score >= 0.7)
        unit_medium = sum(1 for b in unit.branches if b.risk_score and 0.4 <= b.risk_score < 0.7)

        # Determine strategy based on branch count
        strategy = "全展开" if len(unit.branches) >= theoretical * 0.8 else "风险优先"

        safe_unit_id = html_escape.escape(unit.sql_unit_id)
        json_path = f"units/{html_escape.escape(RunPaths.sanitize_unit_id(unit.sql_unit_id))}.json"

        html += f"""
    <div class="card collapsible-unit" data-sortable data-unit-id="{safe_unit_id}" data-json-path="{json_path}">
        <div class="unit-header" onclick="toggleUnit(this)">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin: 0;"><span class="collapse-icon">▶</span> <code>{safe_unit_id}</code></h3>
                <div onclick="event.stopPropagation()">
                    <span class="strategy-tag">{strategy}</span>
                    <span class="sort-btn" data-sort="risk" title="按风险排序">风险↓</span>
                    <span class="sort-btn" data-sort="path" title="按路径排序">路径↓</span>
                </div>
            </div>
            <div class="metric-pair">
                <div class="metric">
                    <div class="metric-value">{theoretical}</div>
                    <div class="metric-label">理论分支</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{len(unit.branches)}</div>
                    <div class="metric-label">实际分支</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{int(len(unit.branches) / max(theoretical, 1) * 100)}%</div>
                    <div class="metric-label">覆盖率</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="color: #dc2626;">{unit_high}</div>
                    <div class="metric-label">高风险</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="color: #f59e0b;">{unit_medium}</div>
                    <div class="metric-label">中风险</div>
                </div>
            </div>
        </div>
        <div class="unit-body">
            <div class="branch-list" data-loaded="false">
                <div style="color: #64748b; padding: 0.5rem; font-style: italic;">点击展开加载分支详情...</div>
            </div>
        </div>
    </div>
"""

    html += (
        f"""
</div>
<script>
const riskCtx = document.getElementById('riskChart').getContext('2d');
new Chart(riskCtx, {{
    type: 'doughnut',
    data: {{
        labels: ['高风险', '中风险', '低风险', '未评分'],
        datasets: [{{
            data: [{high_risk}, {medium_risk}, {low_risk}, {no_score}],
            backgroundColor: ['#dc2626', '#f59e0b', '#22c55e', '#64748b']
        }}]
    }},
    options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ position: 'bottom' }} }} }}
}});

const flagsLabels = {list(all_flags.keys())};
const flagsData = {list(all_flags.values())};
const flagsCtx = document.getElementById('flagsChart').getContext('2d');
new Chart(flagsCtx, {{
    type: 'bar',
    data: {{
        labels: flagsLabels,
        datasets: [{{ label: '出现次数', data: flagsData, backgroundColor: '#6366f1' }}]
    }},
    options: {{ responsive: true, maintainAspectRatio: false, indexAxis: 'y', plugins: {{ legend: {{ display: false }} }} }}
}});
</script>
"""
        + BASE_JS
        + """
</body>
</html>"""
    )

    pathlib.Path(output_path).write_text(html, encoding="utf-8")


def generate_recognition_report(output: RecognitionOutput, output_path: str) -> None:
    baselines = output.baselines if hasattr(output, "baselines") else []
    total = len(baselines)
    slow = sum(1 for b in baselines if b.actual_time_ms and b.actual_time_ms > 100)
    high_cost = sum(1 for b in baselines if b.estimated_cost and b.estimated_cost > 100)

    by_unit: dict[str, list[Any]] = {}
    for b in baselines:
        if b.sql_unit_id not in by_unit:
            by_unit[b.sql_unit_id] = []
        by_unit[b.sql_unit_id].append(b)

    cost_buckets = {"0-10": 0, "10-50": 0, "50-100": 0, "100-500": 0, "500+": 0}
    for b in baselines:
        c = b.estimated_cost or 0
        if c < 10:
            cost_buckets["0-10"] += 1
        elif c < 50:
            cost_buckets["10-50"] += 1
        elif c < 100:
            cost_buckets["50-100"] += 1
        elif c < 500:
            cost_buckets["100-500"] += 1
        else:
            cost_buckets["500+"] += 1

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>识别阶段报告</title>
    {CHART_JS}
    <style>{DARK_THEME}</style>
</head>
<body>
<div class="container">
    <h1>识别阶段报告</h1>

    <div class="summary-grid">
        <div class="card">
            <div class="stat"><div class="stat-value">{total}</div><div class="stat-label">总计划数</div></div>
            <div class="stat"><div class="stat-value">{slow}</div><div class="stat-label">慢查询</div></div>
            <div class="stat"><div class="stat-value">{high_cost}</div><div class="stat-label">高成本</div></div>
        </div>
    </div>

    <div class="charts-grid">
        <div class="card">
            <h3>成本分布</h3>
            <div class="chart-container"><canvas id="costChart"></canvas></div>
        </div>
        <div class="card">
            <h3>执行时间 (Top 10)</h3>
            <div class="chart-container"><canvas id="timeChart"></canvas></div>
        </div>
    </div>

    <h2>执行计划详情（按SQL单元分组）</h2>
    <table>
        <thead>
            <tr>
                <th>SQL单元</th>
                <th data-sort="cost" data-col="1">预估成本</th>
                <th data-sort="time" data-col="2">时间(ms)</th>
                <th data-sort="rows" data-col="3">行数</th>
                <th>计划类型</th>
            </tr>
        </thead>
        <tbody>
"""

    for unit_id, unit_baselines in sorted(
        by_unit.items(), key=lambda x: max((b.estimated_cost or 0) for b in x[1]), reverse=True
    ):
        max_cost = max((b.estimated_cost or 0) for b in unit_baselines)
        max_time = max((b.actual_time_ms or 0) for b in unit_baselines)
        total_rows = sum((b.rows_returned or 0) for b in unit_baselines)

        plan_type = "-"
        if unit_baselines[0].plan:
            plan_str = str(unit_baselines[0].plan)
            if "Index Scan" in plan_str:
                plan_type = "索引扫描"
            elif "Seq Scan" in plan_str:
                plan_type = "全表扫描"
            elif "Nested Loop" in plan_str:
                plan_type = "嵌套循环"
            elif "Hash Join" in plan_str:
                plan_type = "哈希连接"

        cost_class = "rank-high" if max_cost > 100 else "rank-medium" if max_cost > 50 else ""

        html += f"""            <tr class="group-header">
                <td><code>{unit_id}</code><span class="group-summary">{len(unit_baselines)} 个计划</span></td>
                <td class="{cost_class}">{max_cost:.2f}</td>
                <td>{max_time:.2f}</td>
                <td>{total_rows}</td>
                <td><span class="badge badge-info">{plan_type}</span></td>
            </tr>
"""
        for b in unit_baselines:
            plan_short = "-"
            if b.plan:
                plan_str = str(b.plan)
                if "Index Scan" in plan_str:
                    plan_short = "索引扫描"
                elif "Seq Scan" in plan_str:
                    plan_short = "全表扫描"
                elif "Nested Loop" in plan_str:
                    plan_short = "嵌套循环"
                elif "Hash Join" in plan_str:
                    plan_short = "哈希连接"
            time_str = f"{b.actual_time_ms:.2f}" if b.actual_time_ms else "-"
            html += f"""            <tr class="child-row">
                <td style="padding-left: 2rem;"><code>{b.path_id}</code></td>
                <td>{b.estimated_cost:.2f}</td>
                <td>{time_str}</td>
                <td>{b.rows_returned or "-"}</td>
                <td>{plan_short}</td>
            </tr>
"""

    html += (
        """        </tbody>
    </table>
</div>
<script>
const costCtx = document.getElementById('costChart').getContext('2d');
new Chart(costCtx, {
    type: 'bar',
    data: {
        labels: """
        f"{list(cost_buckets.keys())}"
        """,
        datasets: [{ label: 'Plans', data: """
        f"{list(cost_buckets.values())}"
        """, backgroundColor: '#6366f1' }]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
});

const timeData = """
        f"{[(b.sql_unit_id[:20], b.actual_time_ms or 0) for b in sorted(baselines, key=lambda x: x.actual_time_ms or 0, reverse=True)[:10]]}"
        """;
const timeCtx = document.getElementById('timeChart').getContext('2d');
new Chart(timeCtx, {
    type: 'bar',
    data: {
        labels: timeData.map(d => d[0]),
        datasets: [{ label: 'Time (ms)', data: timeData.map(d => d[1]), backgroundColor: '#f59e0b' }]
    },
    options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y', plugins: { legend: { display: false } } }
});
</script>
"""
        + BASE_JS
        + """
</body>
</html>"""
    )

    pathlib.Path(output_path).write_text(html, encoding="utf-8")


def generate_optimize_report(output: OptimizeOutput, output_path: str) -> None:
    proposals = output.proposals if hasattr(output, "proposals") else []
    total = len(proposals)
    high_conf = sum(1 for p in proposals if p.confidence and p.confidence > 0.8)
    medium_conf = sum(1 for p in proposals if p.confidence and 0.5 < (p.confidence or 0) <= 0.8)
    avg_gain = sum((p.gain_ratio or 0) for p in proposals) / total if total else 0

    by_unit: dict[str, list[Any]] = {}
    for p in proposals:
        if p.sql_unit_id not in by_unit:
            by_unit[p.sql_unit_id] = []
        by_unit[p.sql_unit_id].append(p)

    conf_buckets = {"0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
    for p in proposals:
        c = p.confidence or 0
        if c < 0.2:
            conf_buckets["0-0.2"] += 1
        elif c < 0.4:
            conf_buckets["0.2-0.4"] += 1
        elif c < 0.6:
            conf_buckets["0.4-0.6"] += 1
        elif c < 0.8:
            conf_buckets["0.6-0.8"] += 1
        else:
            conf_buckets["0.8-1.0"] += 1

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>优化阶段报告</title>
    {CHART_JS}
    <style>{DARK_THEME}</style>
</head>
<body>
<div class="container">
    <h1>优化阶段报告</h1>

    <div class="summary-grid">
        <div class="card">
            <div class="stat"><div class="stat-value">{total}</div><div class="stat-label">优化建议</div></div>
            <div class="stat"><div class="stat-value">{high_conf}</div><div class="stat-label">高置信</div></div>
            <div class="stat"><div class="stat-value">{medium_conf}</div><div class="stat-label">中置信</div></div>
            <div class="stat"><div class="stat-value">{avg_gain:.1f}%</div><div class="stat-label">平均收益</div></div>
        </div>
    </div>

    <div class="charts-grid">
        <div class="card">
            <h3>置信度分布</h3>
            <div class="chart-container"><canvas id="confChart"></canvas></div>
        </div>
        <div class="card">
            <h3>收益比率 (Top 10)</h3>
            <div class="chart-container"><canvas id="gainChart"></canvas></div>
        </div>
    </div>

    <h2>优化建议（按SQL单元分组）</h2>
    <table>
        <thead>
            <tr>
                <th>SQL单元</th>
                <th data-sort="conf" data-col="1">置信度</th>
                <th data-sort="gain" data-col="2">收益比率</th>
                <th>优化理由</th>
            </tr>
        </thead>
        <tbody>
"""

    for unit_id, unit_proposals in sorted(
        by_unit.items(), key=lambda x: max((p.confidence or 0) for p in x[1]), reverse=True
    ):
        max_conf = max((p.confidence or 0) for p in unit_proposals)
        avg_gain_unit = sum((p.gain_ratio or 0) for p in unit_proposals) / len(unit_proposals)
        conf_badge = (
            '<span class="badge badge-high">高</span>'
            if max_conf > 0.8
            else '<span class="badge badge-medium">中</span>'
            if max_conf > 0.5
            else '<span class="badge badge-low">低</span>'
        )

        html += f"""            <tr class="group-header">
                <td><code>{unit_id}</code><span class="group-summary">{len(unit_proposals)} 个建议</span></td>
                <td>{conf_badge} {max_conf:.2f}</td>
                <td>{avg_gain_unit:.1f}%</td>
                <td>-</td>
            </tr>
"""
        for p in unit_proposals:
            conf = p.confidence or 0
            conf_b = (
                '<span class="badge badge-high">高</span>'
                if conf > 0.8
                else '<span class="badge badge-medium">中</span>'
                if conf > 0.5
                else '<span class="badge badge-low">低</span>'
            )
            gain_str = f"{p.gain_ratio:.1f}%" if p.gain_ratio else "-"
            rationale_short = p.rationale[:60] + "..." if len(p.rationale) > 60 else p.rationale
            html += f"""            <tr class="child-row">
                <td style="padding-left: 2rem;"><code>{p.path_id}</code></td>
                <td>{conf_b} {conf:.2f}</td>
                <td>{gain_str}</td>
                <td class="sql-text" data-full="{p.rationale}">{rationale_short}</td>
            </tr>
"""

    html += (
        """        </tbody>
    </table>
</div>
<script>
const confCtx = document.getElementById('confChart').getContext('2d');
new Chart(confCtx, {
    type: 'bar',
    data: {
        labels: """
        f"{list(conf_buckets.keys())}"
        """,
        datasets: [{ label: 'Proposals', data: """
        f"{list(conf_buckets.values())}"
        """, backgroundColor: '#22c55e' }]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
});

const gainData = """
        f"{[(p.sql_unit_id[:15], p.gain_ratio or 0) for p in sorted(proposals, key=lambda x: x.gain_ratio or 0, reverse=True)[:10]]}"
        """;
const gainCtx = document.getElementById('gainChart').getContext('2d');
new Chart(gainCtx, {
    type: 'bar',
    data: {
        labels: gainData.map(d => d[0]),
        datasets: [{ label: 'Gain %', data: gainData.map(d => d[1]), backgroundColor: '#3b82f6' }]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
});
</script>
"""
        + BASE_JS
        + """
</body>
</html>"""
    )

    pathlib.Path(output_path).write_text(html, encoding="utf-8")


def generate_result_report(output: ResultOutput, output_path: str) -> None:
    summary = output.summary if hasattr(output, "summary") else {}
    patches = summary.get("patches", []) if isinstance(summary, dict) else []

    high_conf = summary.get("high_confidence_count", 0) if isinstance(summary, dict) else 0
    medium_conf = summary.get("medium_confidence_count", 0) if isinstance(summary, dict) else 0
    low_conf = summary.get("low_confidence_count", 0) if isinstance(summary, dict) else 0

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>结果阶段报告</title>
    {CHART_JS}
    <style>{DARK_THEME}</style>
</head>
<body>
<div class="container">
    <h1>结果阶段报告</h1>

    <div class="summary-grid">
        <div class="card">
            <div class="stat"><div class="stat-value">{len(patches)}</div><div class="stat-label">补丁数</div></div>
            <div class="stat"><div class="stat-value">{high_conf}</div><div class="stat-label">高置信</div></div>
            <div class="stat"><div class="stat-value">{medium_conf}</div><div class="stat-label">中置信</div></div>
            <div class="stat"><div class="stat-value">{low_conf}</div><div class="stat-label">低置信</div></div>
        </div>
    </div>

    <div class="card">
        <h3>摘要</h3>
        <p>{summary.get("summary", "暂无摘要") if isinstance(summary, dict) else str(summary)}</p>
    </div>

    <h2>建议</h2>
    <div class="card">
"""

    recommendations = summary.get("recommendations", []) if isinstance(summary, dict) else []
    if recommendations:
        for rec in recommendations:
            html += f"        <div style='margin-bottom: 0.5rem;'>• {rec}</div>\n"
    else:
        html += "        <p class='empty'>暂无建议</p>\n"

    html += (
        """    </div>
</div>
"""
        + BASE_JS
        + """
</body>
</html>"""
    )

    pathlib.Path(output_path).write_text(html, encoding="utf-8")
