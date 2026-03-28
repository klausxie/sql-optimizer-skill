"""Generate HTML reports for each pipeline stage."""

from __future__ import annotations

import pathlib

from sqlopt.contracts.optimize import OptimizeOutput
from sqlopt.contracts.parse import ParseOutput
from sqlopt.contracts.recognition import RecognitionOutput
from sqlopt.contracts.result import ResultOutput

DARK_THEME = """
<style>
    * { box-sizing: border-box; }
    body { background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 20px; }
    .container { max-width: 1200px; margin: 0 auto; }
    h1 { color: #f8fafc; font-size: 1.5rem; margin-bottom: 1rem; }
    h2 { color: #e2e8f0; font-size: 1.25rem; margin: 1.5rem 0 1rem; border-bottom: 1px solid #334155; padding-bottom: 0.5rem; }
    .card { background: #1e293b; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
    .stat { display: inline-block; margin-right: 1.5rem; }
    .stat-value { font-size: 1.5rem; font-weight: bold; color: #3b82f6; }
    .stat-label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; }
    table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
    th { text-align: left; padding: 0.5rem; background: #334155; color: #e2e8f0; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; }
    td { padding: 0.5rem; border-bottom: 1px solid #334155; font-size: 0.875rem; }
    tr:hover { background: #334155; }
    .badge { display: inline-block; padding: 0.125rem 0.5rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
    .badge-high { background: #dc2626; color: white; }
    .badge-medium { background: #f59e0b; color: white; }
    .badge-low { background: #22c55e; color: white; }
    .badge-select { background: #3b82f6; color: white; }
    .badge-insert { background: #22c55e; color: white; }
    .badge-update { background: #f59e0b; color: white; }
    .badge-delete { background: #dc2626; color: white; }
    .risk-flag { display: inline-block; background: #dc2626; color: white; padding: 0.125rem 0.375rem; border-radius: 4px; font-size: 0.625rem; margin-right: 0.25rem; }
    .chart-container { height: 300px; margin: 1rem 0; }
    .empty { color: #64748b; font-style: italic; }
    pre { background: #0f172a; padding: 1rem; border-radius: 4px; overflow-x: auto; font-size: 0.75rem; }
    code { color: #a5b4fc; }
    .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
    .rank-high { color: #dc2626; font-weight: bold; }
    .rank-medium { color: #f59e0b; }
    .rank-low { color: #22c55e; }
</style>
"""


def generate_parse_report(output: ParseOutput, output_path: str) -> None:
    """Generate HTML report for parse stage."""
    total_units = len(output.sql_units_with_branches)
    total_branches = sum(len(u.branches) for u in output.sql_units_with_branches)
    valid_branches = sum(1 for u in output.sql_units_with_branches for b in u.branches if b.is_valid)
    invalid_branches = total_branches - valid_branches

    risk_scores = [
        (u.sql_unit_id, b.risk_score)
        for u in output.sql_units_with_branches
        for b in u.branches
        if b.risk_score is not None
    ]
    risk_scores.sort(key=lambda x: x[1] or 0, reverse=True)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Parse Stage Report</title>
    {DARK_THEME}
</head>
<body>
<div class="container">
    <h1>Parse Stage Report</h1>

    <div class="summary-grid">
        <div class="card">
            <div class="stat">
                <div class="stat-value">{total_units}</div>
                <div class="stat-label">SQL Units</div>
            </div>
            <div class="stat">
                <div class="stat-value">{total_branches}</div>
                <div class="stat-label">Total Branches</div>
            </div>
            <div class="stat">
                <div class="stat-value">{valid_branches}</div>
                <div class="stat-label">Valid</div>
            </div>
            <div class="stat">
                <div class="stat-value">{invalid_branches}</div>
                <div class="stat-label">Invalid</div>
            </div>
        </div>
    </div>

    <h2>Branch Details</h2>
    <table>
        <thead>
            <tr>
                <th>SQL Unit</th>
                <th>Branch</th>
                <th>Type</th>
                <th>Valid</th>
                <th>Risk Score</th>
                <th>Risk Flags</th>
            </tr>
        </thead>
        <tbody>
"""

    for unit in output.sql_units_with_branches:
        for branch in unit.branches:
            risk_badge = ""
            if branch.risk_flags:
                risk_badge = "".join(f'<span class="risk-flag">{f}</span>' for f in branch.risk_flags[:3])
            valid_icon = "✓" if branch.is_valid else "✗"
            risk_score_str = f"{branch.risk_score:.2f}" if branch.risk_score is not None else "-"
            html += f"""            <tr>
                <td><code>{unit.sql_unit_id}</code></td>
                <td>{branch.path_id}</td>
                <td>{branch.branch_type or "-"}</td>
                <td>{valid_icon}</td>
                <td>{risk_score_str}</td>
                <td>{risk_badge}</td>
            </tr>
"""

    html += """        </tbody>
    </table>

    <h2>Top Risk Branches</h2>
    <table>
        <thead>
            <tr><th>Rank</th><th>SQL Unit</th><th>Risk Score</th></tr>
        </thead>
        <tbody>
"""

    for i, (unit_id, score) in enumerate(risk_scores[:10], 1):
        rank_class = "rank-high" if i <= 3 else "rank-medium" if i <= 7 else "rank-low"
        html += f"""            <tr>
                <td class="{rank_class}">#{i}</td>
                <td><code>{unit_id}</code></td>
                <td>{score:.2f}</td>
            </tr>
"""

    html += """        </tbody>
    </table>
</div>
</body>
</html>"""

    pathlib.Path(output_path).write_text(html, encoding="utf-8")


def generate_recognition_report(output: RecognitionOutput, output_path: str) -> None:
    """Generate HTML report for recognition stage."""
    baselines = output.baselines if hasattr(output, "baselines") else []
    total = len(baselines)
    slow = sum(1 for b in baselines if b.actual_time_ms and b.actual_time_ms > 100)
    high_cost = sum(1 for b in baselines if b.estimated_cost and b.estimated_cost > 100)

    sorted_baselines = sorted(baselines, key=lambda x: x.estimated_cost or 0, reverse=True)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Recognition Stage Report</title>
    {DARK_THEME}
</head>
<body>
<div class="container">
    <h1>Recognition Stage Report</h1>

    <div class="summary-grid">
        <div class="card">
            <div class="stat">
                <div class="stat-value">{total}</div>
                <div class="stat-label">Total Plans</div>
            </div>
            <div class="stat">
                <div class="stat-value">{slow}</div>
                <div class="stat-label">Slow (&gt;100ms)</div>
            </div>
            <div class="stat">
                <div class="stat-value">{high_cost}</div>
                <div class="stat-label">High Cost (&gt;100)</div>
            </div>
        </div>
    </div>

    <h2>Costliest Plans</h2>
    <table>
        <thead>
            <tr>
                <th>SQL Unit</th>
                <th>Path</th>
                <th>Est. Cost</th>
                <th>Actual Time</th>
                <th>Rows</th>
            </tr>
        </thead>
        <tbody>
"""

    for b in sorted_baselines[:20]:
        actual_time = f"{b.actual_time_ms:.2f}ms" if b.actual_time_ms else "-"
        cost_class = (
            "rank-high" if (b.estimated_cost or 0) > 100 else "rank-medium" if (b.estimated_cost or 0) > 50 else ""
        )
        html += f"""            <tr>
                <td><code>{b.sql_unit_id}</code></td>
                <td>{b.path_id}</td>
                <td class="{cost_class}">{b.estimated_cost:.2f}</td>
                <td>{actual_time}</td>
                <td>{b.rows_returned or "-"}</td>
            </tr>
"""

    html += """        </tbody>
    </table>
</div>
</body>
</html>"""

    pathlib.Path(output_path).write_text(html, encoding="utf-8")


def generate_optimize_report(output: OptimizeOutput, output_path: str) -> None:
    """Generate HTML report for optimize stage."""
    proposals = output.proposals if hasattr(output, "proposals") else []
    total = len(proposals)
    high_conf = sum(1 for p in proposals if p.confidence and p.confidence > 0.8)
    avg_gain = sum((p.gain_ratio or 0) for p in proposals) / total if total else 0

    sorted_proposals = sorted(proposals, key=lambda x: x.confidence or 0, reverse=True)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Optimize Stage Report</title>
    {DARK_THEME}
</head>
<body>
<div class="container">
    <h1>Optimize Stage Report</h1>

    <div class="summary-grid">
        <div class="card">
            <div class="stat">
                <div class="stat-value">{total}</div>
                <div class="stat-label">Total Proposals</div>
            </div>
            <div class="stat">
                <div class="stat-value">{high_conf}</div>
                <div class="stat-label">High Confidence</div>
            </div>
            <div class="stat">
                <div class="stat-value">{avg_gain:.1f}%</div>
                <div class="stat-label">Avg Gain</div>
            </div>
        </div>
    </div>

    <h2>Optimization Proposals</h2>
    <table>
        <thead>
            <tr>
                <th>SQL Unit</th>
                <th>Confidence</th>
                <th>Gain Ratio</th>
                <th>Rationale</th>
            </tr>
        </thead>
        <tbody>
"""

    for p in sorted_proposals:
        conf_badge = (
            '<span class="badge badge-high">HIGH</span>'
            if (p.confidence or 0) > 0.8
            else '<span class="badge badge-medium">MED</span>'
            if (p.confidence or 0) > 0.5
            else '<span class="badge badge-low">LOW</span>'
        )
        gain_str = f"{p.gain_ratio:.1f}%" if p.gain_ratio else "-"
        html += f"""            <tr>
                <td><code>{p.sql_unit_id}</code></td>
                <td>{conf_badge} {(p.confidence or 0):.2f}</td>
                <td>{gain_str}</td>
                <td>{p.rationale[:80]}{"..." if len(p.rationale) > 80 else ""}</td>
            </tr>
"""

    html += """        </tbody>
    </table>
</div>
</body>
</html>"""

    pathlib.Path(output_path).write_text(html, encoding="utf-8")


def generate_result_report(output: ResultOutput, output_path: str) -> None:
    """Generate HTML report for result stage."""
    summary = output.summary if hasattr(output, "summary") else {}
    patches = summary.get("patches", []) if isinstance(summary, dict) else []

    high_conf = summary.get("high_confidence_count", 0) if isinstance(summary, dict) else 0
    medium_conf = summary.get("medium_confidence_count", 0) if isinstance(summary, dict) else 0
    low_conf = summary.get("low_confidence_count", 0) if isinstance(summary, dict) else 0

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Result Stage Report</title>
    {DARK_THEME}
</head>
<body>
<div class="container">
    <h1>Result Stage Report</h1>

    <div class="summary-grid">
        <div class="card">
            <div class="stat">
                <div class="stat-value">{len(patches)}</div>
                <div class="stat-label">Patches</div>
            </div>
            <div class="stat">
                <div class="stat-value">{high_conf}</div>
                <div class="stat-label">High Confidence</div>
            </div>
            <div class="stat">
                <div class="stat-value">{medium_conf}</div>
                <div class="stat-label">Medium Confidence</div>
            </div>
            <div class="stat">
                <div class="stat-value">{low_conf}</div>
                <div class="stat-label">Low Confidence</div>
            </div>
        </div>
    </div>

    <h2>Summary</h2>
    <div class="card">
        <p>{summary.get("summary", "No summary available") if isinstance(summary, dict) else str(summary)}</p>
    </div>

    <h2>Recommendations</h2>
    <div class="card">
"""

    recommendations = summary.get("recommendations", []) if isinstance(summary, dict) else []
    if recommendations:
        for rec in recommendations:
            html += f"        <div style='margin-bottom: 0.5rem;'>• {rec}</div>\n"
    else:
        html += "        <p class='empty'>No recommendations</p>\n"

    html += """    </div>
</div>
</body>
</html>"""

    pathlib.Path(output_path).write_text(html, encoding="utf-8")
