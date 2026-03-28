"""Generate rich HTML reports for each pipeline stage."""

from __future__ import annotations

import pathlib

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
    .risk-flag { display: inline-block; background: #dc2626; color: white; padding: 0.125rem 0.375rem; border-radius: 4px; font-size: 0.625rem; margin-right: 0.25rem; }
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
</style>
"""

BASE_JS = """
<script>
function initSortableTables() {
    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', function() {
            const table = this.closest('table');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const col = this.dataset.sort;
            const isAsc = this.classList.contains('asc');
            
            // Remove sort classes from all headers
            table.querySelectorAll('th').forEach(h => { h.classList.remove('asc', 'desc'); });
            
            // Add appropriate class
            this.classList.add(isAsc ? 'desc' : 'asc');
            
            // Sort rows
            rows.sort((a, b) => {
                const aVal = a.dataset[col] || a.children[parseInt(this.dataset.col)].textContent;
                const bVal = b.dataset[col] || b.children[parseInt(this.dataset.col)].textContent;
                
                // Try numeric comparison
                const aNum = parseFloat(aVal);
                const bNum = parseFloat(bVal);
                if (!isNaN(aNum) && !isNaN(bNum)) {
                    return isAsc ? bNum - aNum : aNum - bNum;
                }
                
                // String comparison
                return isAsc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
            });
            
            rows.forEach(row => tbody.appendChild(row));
        });
    });
}

function initExpandable() {
    document.querySelectorAll('.expand-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const groupId = this.dataset.group;
            const childRows = document.querySelectorAll(`.child-row[data-parent="${groupId}"]`);
            childRows.forEach(row => row.classList.toggle('expanded'));
            this.textContent = this.textContent === '▶' ? '▼' : '▶';
        });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    initSortableTables();
    initExpandable();
});
</script>
"""


def generate_parse_report(output: ParseOutput, output_path: str) -> None:
    """Generate rich HTML report for parse stage."""
    total_units = len(output.sql_units_with_branches)
    total_branches = sum(len(u.branches) for u in output.sql_units_with_branches)
    valid_branches = sum(1 for u in output.sql_units_with_branches for b in u.branches if b.is_valid)
    invalid_branches = total_branches - valid_branches

    # Risk distribution
    high_risk = sum(
        1 for u in output.sql_units_with_branches for b in u.branches if b.risk_score and b.risk_score >= 0.7
    )
    medium_risk = sum(
        1 for u in output.sql_units_with_branches for b in u.branches if b.risk_score and 0.4 <= b.risk_score < 0.7
    )
    low_risk = total_branches - high_risk - medium_risk

    # Branch type distribution
    branch_types = {}
    for u in output.sql_units_with_branches:
        for b in u.branches:
            bt = b.branch_type or "unknown"
            branch_types[bt] = branch_types.get(bt, 0) + 1

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
            <div class="stat"><div class="stat-value">{total_branches}</div><div class="stat-label">总分支</div></div>
            <div class="stat"><div class="stat-value">{valid_branches}</div><div class="stat-label">有效</div></div>
            <div class="stat"><div class="stat-value">{invalid_branches}</div><div class="stat-label">无效</div></div>
        </div>
    </div>

    <div class="charts-grid">
        <div class="card">
            <h3>风险分布</h3>
            <div class="chart-container"><canvas id="riskChart"></canvas></div>
        </div>
        <div class="card">
            <h3>分支类型</h3>
            <div class="chart-container"><canvas id="typeChart"></canvas></div>
        </div>
    </div>

    <h2>分支详情（按SQL单元分组）</h2>
    <table id="mainTable">
        <thead>
            <tr>
                <th data-sort="unit" data-col="0">SQL单元</th>
                <th data-sort="branches" data-col="1">分支数</th>
                <th data-sort="valid" data-col="2">有效</th>
                <th data-sort="risk" data-col="3">最大风险</th>
                <th data-sort="flags" data-col="4">风险标志</th>
            </tr>
        </thead>
        <tbody>
"""

    for unit in output.sql_units_with_branches:
        valid_cnt = sum(1 for b in unit.branches if b.is_valid)
        max_risk = max((b.risk_score or 0) for b in unit.branches)
        all_flags = list(set(f for b in unit.branches for f in b.risk_flags))[:3]
        risk_display = f"{max_risk:.2f}" if max_risk > 0 else "-"
        flags_display = "".join(f'<span class="risk-flag">{f}</span>' for f in all_flags) if all_flags else "-"

        html += f"""            <tr class="group-header" data-unit="{unit.sql_unit_id}">
                <td><span class="expand-btn" data-group="{unit.sql_unit_id}">▶</span><code>{unit.sql_unit_id}</code></td>
                <td>{len(unit.branches)}</td>
                <td>{valid_cnt}/{len(unit.branches)}</td>
                <td>{risk_display}</td>
                <td>{flags_display}</td>
            </tr>
"""
        for b in unit.branches:
            is_valid_icon = "✓" if b.is_valid else "✗"
            risk_str = f"{b.risk_score:.2f}" if b.risk_score is not None else "-"
            flags_str = (
                "".join(f'<span class="risk-flag">{f}</span>' for f in b.risk_flags[:2]) if b.risk_flags else "-"
            )
            cond = b.condition[:50] + "..." if b.condition and len(b.condition) > 50 else (b.condition or "-")
            html += f"""            <tr class="child-row" data-parent="{unit.sql_unit_id}">
                <td><code style="margin-left: 1rem;">{b.path_id}</code></td>
                <td>{b.branch_type or "-"}</td>
                <td>{is_valid_icon}</td>
                <td>{risk_str}</td>
                <td>{flags_str}</td>
            </tr>
"""

    html += (
        """        </tbody>
    </table>
</div>
<script>
const riskCtx = document.getElementById('riskChart').getContext('2d');
new Chart(riskCtx, {
    type: 'doughnut',
    data: {
        labels: ['High Risk', 'Medium Risk', 'Low Risk'],
        datasets: [{
            data: ["""
        f"{high_risk}, {medium_risk}, {low_risk}"
        """],
            backgroundColor: ['#dc2626', '#f59e0b', '#22c55e']
        }]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
});

const typeCtx = document.getElementById('typeChart').getContext('2d');
new Chart(typeCtx, {
    type: 'bar',
    data: {
        labels: """
        f"{list(branch_types.keys())}"
        """,
        datasets: [{
            label: 'Count',
            data: """
        f"{list(branch_types.values())}"
        """,
            backgroundColor: '#3b82f6'
        }]
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


def generate_recognition_report(output: RecognitionOutput, output_path: str) -> None:
    """Generate rich HTML report for recognition stage."""
    baselines = output.baselines if hasattr(output, "baselines") else []
    total = len(baselines)
    slow = sum(1 for b in baselines if b.actual_time_ms and b.actual_time_ms > 100)
    high_cost = sum(1 for b in baselines if b.estimated_cost and b.estimated_cost > 100)

    # Group by sql_unit_id
    by_unit = {}
    for b in baselines:
        if b.sql_unit_id not in by_unit:
            by_unit[b.sql_unit_id] = []
        by_unit[b.sql_unit_id].append(b)

    # Cost distribution for chart
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
    """Generate rich HTML report for optimize stage."""
    proposals = output.proposals if hasattr(output, "proposals") else []
    total = len(proposals)
    high_conf = sum(1 for p in proposals if p.confidence and p.confidence > 0.8)
    medium_conf = sum(1 for p in proposals if p.confidence and 0.5 < (p.confidence or 0) <= 0.8)
    low_conf = total - high_conf - medium_conf
    avg_gain = sum((p.gain_ratio or 0) for p in proposals) / total if total else 0

    # Group by unit
    by_unit = {}
    for p in proposals:
        if p.sql_unit_id not in by_unit:
            by_unit[p.sql_unit_id] = []
        by_unit[p.sql_unit_id].append(p)

    # Confidence distribution for chart
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
    <title>Optimize Stage Report</title>
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
    """Generate rich HTML report for result stage."""
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
