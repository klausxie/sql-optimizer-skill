"""Generate rich HTML reports for each pipeline stage."""

from __future__ import annotations

import html as html_escape
import pathlib
from typing import Any

from sqlopt.common.parse_stats import (
    OUTLIER_THEORETICAL_BRANCHES_THRESHOLD,
    STRATEGY_EXPLANATIONS,
    STRATEGY_NAMES,
    ParseStageStats,
)
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
    .section { margin-bottom: 1rem; }
    .section-header { cursor: pointer; padding: 0.5rem; background: #33415540; border-radius: 6px; margin-bottom: 0.25rem; }
    .section-header:hover { background: #47556940; }
    .section-body { padding: 0.5rem; }
    .tooltip-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        border-radius: 50%;
        background: #334155;
        color: #94a3b8;
        font-size: 0.65rem;
        font-weight: 700;
        cursor: help;
        margin-left: 0.25rem;
        position: relative;
    }
    .tooltip-icon:hover::after {
        content: attr(title);
        position: absolute;
        left: 50%;
        bottom: calc(100% + 6px);
        transform: translateX(-50%);
        background: #0f172a;
        border: 1px solid #475569;
        padding: 0.5rem 0.75rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 400;
        color: #e2e8f0;
        white-space: pre-wrap;
        max-width: 280px;
        z-index: 100;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    }
    .tooltip-icon:hover::before {
        content: '';
        position: absolute;
        left: 50%;
        bottom: calc(100% + 2px);
        transform: translateX(-50%);
        border: 4px solid transparent;
        border-top-color: #475569;
    }
    .formula-block { background: #0f172a; border-radius: 6px; padding: 0.75rem; margin: 0.5rem 0; }
    .formula-header { font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.5rem; font-weight: 600; }
    .formula-step { font-size: 0.75rem; color: #a5b4fc; font-family: monospace; padding: 0.15rem 0; }
    .formula-result { font-size: 0.8rem; color: #34d399; font-weight: 600; margin-top: 0.35rem; }
    .strategy-block { background: #0f172a; border-radius: 6px; padding: 0.75rem; margin: 0.5rem 0; }
    .strategy-header { font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.5rem; font-weight: 600; }
    .strategy-desc { font-size: 0.8rem; color: #e2e8f0; }
    .strategy-meaning { font-size: 0.75rem; color: #94a3b8; margin-top: 0.35rem; }
    .strategy-whatif { font-size: 0.75rem; color: #fbbf24; margin-top: 0.35rem; }
    .coverage-bar { margin: 0.5rem 0; }
    .coverage-label { font-size: 0.75rem; color: #94a3b8; margin-bottom: 0.35rem; }
    .coverage-value { font-size: 0.8rem; color: #34d399; font-weight: 600; margin-top: 0.25rem; }
    .coverage-bar .progress-bar { height: 8px; background: #334155; border-radius: 4px; overflow: hidden; margin-top: 0.25rem; }
    .coverage-bar .progress-fill { height: 100%; border-radius: 4px; background: linear-gradient(90deg, #22c55e, #86efac); }
    .strategy-card { background: #0f172a; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; border: 1px solid #334155; }
    .strategy-card .strategy-name { font-size: 1rem; font-weight: 600; color: #e2e8f0; margin-bottom: 0.5rem; }
    .strategy-card .strategy-cn { color: #94a3b8; font-weight: 400; font-size: 0.85rem; margin-left: 0.5rem; }
    .strategy-card .strategy-desc { font-size: 0.8rem; color: #94a3b8; line-height: 1.6; }
</style>
"""

BASE_JS = """
<script>
function toggleSection(header) {
    const body = header.nextElementSibling;
    const icon = header.querySelector('.collapse-icon');
    if (body.classList.contains('hidden')) {
        body.classList.remove('hidden');
        icon.textContent = '▼';
    } else {
        body.classList.add('hidden');
        icon.textContent = '▶';
    }
}

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


def generate_parse_report(output_or_stats: ParseOutput | ParseStageStats, output_path: str) -> None:
    if isinstance(output_or_stats, ParseStageStats):
        stats = output_or_stats
        units = stats.per_unit
        total_units = stats.total_units
        total_branches = stats.total_branches
        sum_theoretical = stats.sum_theoretical
        global_coverage = stats.coverage_pct
        high_risk = stats.high_risk_branches
        medium_risk = stats.medium_risk_branches
        low_risk = stats.low_risk_branches
        no_score = total_branches - high_risk - medium_risk - low_risk
        branch_types = stats.branch_type_distribution
        all_flags: dict[str, int] = dict(stats.risk_flag_distribution)
        strategy = stats.strategy
        max_branches = stats.max_branches
        strategy_display = STRATEGY_NAMES.get(strategy, strategy)
        strategy_explanation = STRATEGY_EXPLANATIONS.get(strategy, "")
        cond_distribution = stats.cond_distribution
        outlier_sum_theoretical = sum(u.theoretical_branches for u in stats.outlier_units)
        outlier_actual_branches = sum(u.actual_branches for u in stats.outlier_units)
        outlier_coverage_pct = (
            outlier_actual_branches / outlier_sum_theoretical * 100 if outlier_sum_theoretical > 0 else 0.0
        )
        normal_count = stats.normal_count
        outlier_count = stats.outlier_count
        if outlier_count > 0:
            outlier_rows = "".join(
                f'<tr><td style="font-size:0.8rem;"><code>{html_escape.escape(u.sql_unit_id)}</code></td>'
                f'<td style="text-align:center;font-size:0.8rem;">{u.cond_count}</td>'
                f'<td style="text-align:center;font-size:0.8rem;color:#dc2626;">{f"{u.theoretical_branches:,.0f}"}</td>'
                f'<td style="text-align:center;font-size:0.8rem;">{u.actual_branches}</td>'
                f'<td style="text-align:center;font-size:0.8rem;">{u.coverage_pct:.1f}%</td>'
                f'<td style="font-size:0.75rem;color:#94a3b8;">{html_escape.escape(u.reason)}</td></tr>'
                for u in stats.outlier_units
            )
            outlier_html = f"""
    <h2>极值单元列表</h2>
    <div class="card">
        <p style="color:#dc2626;font-size:0.8rem;margin-bottom:0.75rem;">
            ⚠️ 以下单元理论分支数超过 {OUTLIER_THEORETICAL_BRANCHES_THRESHOLD:,}, 已从正常统计中分离
        </p>
        <table>
            <thead><tr><th>SQL单元</th><th style="width:80px;text-align:center;">条件数</th><th style="width:120px;text-align:center;">理论分支</th><th style="width:100px;text-align:center;">实际分支</th><th style="width:80px;text-align:center;">覆盖率</th><th>原因</th></tr></thead>
            <tbody>{outlier_rows}</tbody>
        </table>
    </div>
    """
        else:
            outlier_html = ""
    else:
        output = output_or_stats
        units = output.sql_units_with_branches
        total_units = len(output.sql_units_with_branches)
        total_branches = sum(len(u.branches) for u in output.sql_units_with_branches)

        high_risk = sum(
            1 for u in output.sql_units_with_branches for b in u.branches if b.risk_score and b.risk_score >= 0.7
        )
        medium_risk = sum(
            1 for u in output.sql_units_with_branches for b in u.branches if b.risk_score and 0.4 <= b.risk_score < 0.7
        )
        low_risk = sum(
            1 for u in output.sql_units_with_branches for b in u.branches if b.risk_score and b.risk_score < 0.4
        )
        no_score = total_branches - high_risk - medium_risk - low_risk

        branch_types: dict[str, int] = {}
        for u in output.sql_units_with_branches:
            for b in u.branches:
                bt = b.branch_type or "unknown"
                branch_types[bt] = branch_types.get(bt, 0) + 1

        all_flags = {}
        for u in output.sql_units_with_branches:
            for b in u.branches:
                for f in b.risk_flags:
                    all_flags[f] = all_flags.get(f, 0) + 1

        strategy = getattr(output, "strategy", None) or "unknown"
        max_branches = getattr(output, "max_branches", 0) or 0
        strategy_display = STRATEGY_NAMES.get(strategy, strategy)
        strategy_explanation = STRATEGY_EXPLANATIONS.get(strategy, "")
        sum_theoretical = sum(u.theoretical_branches for u in output.sql_units_with_branches)
        global_coverage = total_branches / max(sum_theoretical, 1) * 100

        all_conditions: list[str] = []
        for u in output.sql_units_with_branches:
            for b in u.branches:
                all_conditions.extend(b.active_conditions)
        from collections import Counter

        cond_counter = Counter(all_conditions)
        cond_distribution = cond_counter.most_common(10)

        normal_count = total_units
        outlier_count = 0
        outlier_sum_theoretical = 0
        outlier_actual_branches = 0
        outlier_coverage_pct = 0.0
        outlier_html = ""

    # Branch type color map

    # Branch type color map
    bt_color = {"error": "#dc2626", "baseline_only": "#f59e0b", "normal": "#22c55e"}
    bt_items = sorted(branch_types.items(), key=lambda x: x[1], reverse=True)
    bt_html = "".join(
        f'<div style="flex:1;min-width:120px;background:#0f172a;border-radius:6px;padding:0.75rem;border:1px solid #334155;text-align:center;"><div style="font-size:1.25rem;font-weight:700;color:{bt_color.get(bt, "#94a3b8")};">{cnt}</div><div style="font-size:0.7rem;color:#94a3b8;text-transform:uppercase;">{bt}</div></div>'
        for bt, cnt in bt_items
    )

    cond_rows = "".join(
        f'<tr><td style="font-size:0.8rem;"><code>{html_escape.escape(c[:60])}</code></td><td style="text-align:center;font-size:0.8rem;color:#60a5fa;">{cnt}</td></tr>'
        for c, cnt in cond_distribution
    )

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
            <div class="stat"><div class="stat-value">{
        sum_theoretical
    }</div><div class="stat-label">理论分支</div></div>
            <div class="stat"><div class="stat-value">{high_risk}</div><div class="stat-label">高风险</div></div>
        </div>
    </div>

    <div class="section">
        <div class="section-header" onclick="toggleSection(this)">
          <h2><span class="collapse-icon">▼</span> 解析策略</h2>
        </div>
        <div class="section-body">
          <div style="display:flex;gap:1rem;align-items:center;margin-bottom:1rem;">
            <div class="stat-card" style="flex:1;text-align:center;">
              <div class="stat-value" style="font-size:1.25rem;">{strategy}</div>
              <div class="stat-label">{strategy_display}</div>
            </div>
            <div class="stat-card" style="flex:1;text-align:center;">
              <div class="stat-value" style="font-size:1.25rem;">{"无限制" if max_branches == 0 else max_branches}</div>
              <div class="stat-label">最大分支上限</div>
            </div>
          </div>
          <div style="margin-bottom:0.75rem;">
            <div style="font-size:0.8rem;color:#94a3b8;margin-bottom:0.5rem;">策略说明</div>
            <div style="font-size:0.8rem;color:#cbd5e1;line-height:1.6;">{strategy_explanation}</div>
          </div>
          <details style="margin-top:0.75rem;font-size:0.75rem;color:#64748b;">
            <summary style="cursor:pointer;font-weight:600;color:#94a3b8;margin-bottom:0.25rem;">4种策略对比</summary>
            <div style="margin-top:0.5rem;display:grid;gap:0.5rem;">
              <div class="strategy-card">
                <div class="strategy-name">
                  all_combinations <span class="strategy-cn">全组合策略</span>
                  <span class="tooltip-icon" title="所有条件的所有可能组合都测试。覆盖率 100%,但分支数指数增长(2^n)。5个条件=32分支,8个条件=256分支。">?</span>
                </div>
                <div class="strategy-desc">全组合策略会生成所有条件的所有可能组合。当条件数较多时,分支数呈指数增长(2^n)。</div>
              </div>
              <div class="strategy-card">
                <div class="strategy-name">
                  each <span class="strategy-cn">单测策略</span>
                  <span class="tooltip-icon" title="每个条件单独为 true/false。分支数随条件数线性增长(n)。适合大规模条件数的快速验证。">?</span>
                </div>
                <div class="strategy-desc">单测策略每个条件单独为 true/false,分支数随条件数线性增长(n)。</div>
              </div>
              <div class="strategy-card">
                <div class="strategy-name">
                  boundary <span class="strategy-cn">边界值策略</span>
                  <span class="tooltip-icon" title="只生成极值情况(全 true / 全 false / 各一个 false)。分支数最少(约 n+1)。">?</span>
                </div>
                <div class="strategy-desc">边界值策略只生成极值情况(全 true / 全 false / 各一个 false 等),分支数最少(约 n+1)。</div>
              </div>
              <div class="strategy-card">
                <div class="strategy-name">
                  ladder <span class="strategy-cn">阶梯采样策略</span>
                  <span class="tooltip-icon" title="加权采样,优先覆盖高风险条件组合,在分支数和覆盖率之间取得平衡。">?</span>
                </div>
                <div class="strategy-desc">阶梯采样策略结合了高权重两两组合和边界覆盖,在覆盖率和分支数之间取得平衡。</div>
              </div>
            </div>
          </details>
        </div>
    </div>

    <h2>分支筛选漏斗</h2>
    <div class="card">
        <div class="funnel">
            <div class="funnel-step">
                <div class="funnel-value">{sum_theoretical}</div>
                <div class="funnel-label">理论分支</div>
                <div class="funnel-reduction">100%</div>
            </div>
            <div class="funnel-step">
                <div class="funnel-value">{total_branches}</div>
                <div class="funnel-label">风险评估后</div>
                <div class="funnel-reduction">-{int((1 - total_branches / max(sum_theoretical, 1)) * 100)}%%</div>
            </div>
            <div class="funnel-step">
                <div class="funnel-value">{high_risk}</div>
                <div class="funnel-label">高风险保留</div>
                <div class="funnel-reduction">-{int((1 - high_risk / max(total_branches, 1)) * 100)}%%</div>
            </div>
        </div>
        <p style="color: #94a3b8; font-size: 0.875rem; margin-top: 1rem;">
            通过 <strong>风险评分策略</strong> 从理论 {sum_theoretical} 个分支中筛选出 <strong>{
        total_branches
    }</strong> 个进行优化分析,
            其中 <strong>{high_risk}</strong> 个为高风险分支需要重点关注。
        </p>
    </div>

    <h2>全局预估 vs 实际</h2>
    <div class="card">
        <div class="summary-grid">
            <div class="card">
                <div class="stat"><div class="stat-value">{
        stats.normal_sum_theoretical if isinstance(output_or_stats, ParseStageStats) else sum_theoretical
    }</div><div class="stat-label">正常理论分支</div></div>
                <div class="stat"><div class="stat-value">{
        stats.normal_total_branches if isinstance(output_or_stats, ParseStageStats) else total_branches
    }</div><div class="stat-label">正常实际分支</div></div>
                <div class="stat"><div class="stat-value" style="color:#22c55e;">{
        stats.normal_coverage_pct
        if isinstance(output_or_stats, ParseStageStats)
        else global_coverage:.1f}%</div><div class="stat-label">正常覆盖率</div></div>
                <div class="stat"><div class="stat-value">{
        normal_count
    }</div><div class="stat-label">正常单元</div></div>
            </div>
        </div>
        {
        f'''
        <div class="summary-grid" style="margin-top:0.75rem;">
            <div class="card" style="border:1px solid #dc262640;background:#dc262610;">
                <div class="stat"><div class="stat-value" style="color:#dc2626;">{outlier_sum_theoretical}</div><div class="stat-label">极值理论分支</div></div>
                <div class="stat"><div class="stat-value" style="color:#dc2626;">{outlier_actual_branches}</div><div class="stat-label">极值实际分支</div></div>
                <div class="stat"><div class="stat-value" style="color:#dc2626;">{outlier_coverage_pct:.1f}%</div><div class="stat-label">极值覆盖率</div></div>
                <div class="stat"><div class="stat-value" style="color:#dc2626;">{outlier_count}</div><div class="stat-label">极值单元</div></div>
            </div>
        </div>
        '''
        if outlier_count > 0
        else ""
    }
        <div class="summary-grid" style="margin-top:0.75rem;border-top:1px solid #334155;padding-top:0.75rem;">
            <div class="card">
                <div class="stat"><div class="stat-value">{
        sum_theoretical
    }</div><div class="stat-label">全量理论分支</div></div>
                <div class="stat"><div class="stat-value">{
        total_branches
    }</div><div class="stat-label">全量实际分支</div></div>
                <div class="stat"><div class="stat-value" style="color:#94a3b8;">{
        global_coverage:.1f}%</div><div class="stat-label">全量覆盖率</div></div>
                <div class="stat"><div class="stat-value">{
        total_units
    }</div><div class="stat-label">全量单元</div></div>
            </div>
        </div>
        <p style="color:#94a3b8;font-size:0.8rem;margin-top:0.75rem;">
            {"正常覆盖率不受极值单元影响。" if outlier_count > 0 else ""}覆盖率越高表示测试越完整。
            {"覆盖率较低是因为 ladder 策略有意采样而非全展开。" if strategy == "ladder" else ""}
        </p>
    </div>
    {outlier_html}
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

    <h2>分支类型分布</h2>
    <div class="card">
        <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:0.75rem;">
            {bt_html}
        </div>
        <p style="color:#64748b;font-size:0.75rem;">
            error = 展开异常 | baseline_only = 仅基线 | normal = 正常分支
        </p>
    </div>

    <h2>条件分布</h2>
    <div class="card">
        <p style="color:#94a3b8;font-size:0.8rem;margin-bottom:0.75rem;">Top 10 条件出现频次(一个条件在多个分支中重复出现)</p>
        <table>
            <thead><tr><th>条件</th><th style="width:80px;text-align:center;">出现次数</th></tr></thead>
            <tbody>
            {cond_rows}
            </tbody>
        </table>
    </div>

    <h2>各单元分支详情</h2>
"""

    for unit in units:
        theoretical = unit.theoretical_branches if unit.theoretical_branches > 0 else 1
        if hasattr(unit, "branches"):
            unit_high = sum(1 for b in unit.branches if b.risk_score and b.risk_score >= 0.7)
            unit_medium = sum(1 for b in unit.branches if b.risk_score and 0.4 <= b.risk_score < 0.7)
            actual_branches = len(unit.branches)
        else:
            unit_high = 0
            unit_medium = 0
            actual_branches = unit.actual_branches

        actual_strategy = strategy
        coverage_pct = (
            unit.coverage_pct
            if hasattr(unit, "coverage_pct")
            else (actual_branches / theoretical * 100 if theoretical > 0 else 0)
        )
        saved_pct = (theoretical - actual_branches) / theoretical * 100 if theoretical > 0 else 0

        formula_steps_html = ""
        if theoretical > 1:
            formula_steps_html = f"""
            <div class="formula-block">
              <div class="formula-header">
                理论分支数
                <span class="tooltip-icon" title="理论分支数 = 该SQL在所有条件组合下的最大可能分支数。IF → (1+1)=2, Choose → sum(when_i)+1">?</span>
              </div>
              <div class="formula-result">根据条件结构,共 {theoretical} 个理论分支</div>
            </div>
            """

        strategy_explain_html = ""
        if actual_strategy in ("ladder", "each", "boundary"):
            strategy_explain_html = f"""
            <div class="strategy-block">
              <div class="strategy-header">
                实际分支 ({actual_strategy} 策略)
                <span class="tooltip-icon" title="{STRATEGY_EXPLANATIONS.get(actual_strategy, "")}">?</span>
              </div>
              <div class="strategy-desc">
                {actual_strategy} 采样 <strong>{actual_branches}/{theoretical}</strong> 分支
                {("," + f"节省 <strong>{saved_pct:.1f}%</strong>") if saved_pct > 0 else ""}
              </div>
              <div class="strategy-meaning">
                覆盖率 {coverage_pct:.1f}% = 每 10 个分支有 {int(coverage_pct / 10)} 个被测试
              </div>
              <div class="strategy-whatif">
                💡 若需更完整覆盖,可切 all_combinations(需 {theoretical} 分支)
              </div>
            </div>
            """
        elif actual_strategy == "all_combinations":
            strategy_explain_html = f"""
            <div class="strategy-block">
              <div class="strategy-header">实际分支 (all_combinations 策略)</div>
              <div class="strategy-desc">全组合策略,覆盖率 100%,共 {actual_branches} 个分支</div>
            </div>
            """

        bar_color = "#22c55e" if coverage_pct >= 80 else "#f59e0b" if coverage_pct >= 50 else "#dc2626"
        coverage_bar_html = f"""
        <div class="coverage-bar">
          <div class="coverage-label">
            覆盖率
            <span class="tooltip-icon" title="覆盖率 = 实际分支数 / 理论分支数。覆盖率越高测试越完整。">?</span>
          </div>
          <div class="progress-bar" style="height:6px;background:#334155;border-radius:3px;overflow:hidden;">
            <div style="height:100%;width:{min(coverage_pct, 100):.1f}%;background:{bar_color};border-radius:3px;"></div>
          </div>
            <div class="coverage-value" style="color:{bar_color};">{coverage_pct:.1f}% ({actual_branches}/{theoretical})</div>
        </div>
        """

        safe_unit_id = html_escape.escape(unit.sql_unit_id)
        json_path = f"units/{html_escape.escape(RunPaths.sanitize_unit_id(unit.sql_unit_id))}.json"

        html += f"""
    <div class="card collapsible-unit" data-sortable data-unit-id="{safe_unit_id}" data-json-path="{json_path}">
        <div class="unit-header" onclick="toggleUnit(this)">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <h3 style="margin:0;"><span class="collapse-icon">▶</span> <code>{safe_unit_id}</code></h3>
                <div onclick="event.stopPropagation()">
                    <span class="strategy-tag">{actual_strategy}</span>
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
                    <div class="metric-value">{actual_branches}</div>
                    <div class="metric-label">实际分支</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="color:{bar_color};">{coverage_pct:.1f}%</div>
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
            {formula_steps_html}
            {strategy_explain_html}
            {coverage_bar_html}
            <div class="branch-list" data-loaded="false">
                <div style="color:#64748b;padding:0.5rem;font-style:italic;">点击展开加载分支详情...</div>
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

    <h2>执行计划详情(按SQL单元分组)</h2>
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

    <h2>优化建议(按SQL单元分组)</h2>
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
