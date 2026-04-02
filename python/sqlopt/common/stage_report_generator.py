"""Generate rich HTML reports for each pipeline stage."""

from __future__ import annotations

import html as html_escape
import pathlib
from typing import Any

from sqlopt.common.parse_stats import (
    STRATEGY_EXPLANATIONS,
    STRATEGY_NAMES,
    ParseStageStats,
    PerUnitBranchStats,
)
from sqlopt.common.risk_assessment import RISK_FACTOR_REGISTRY
from sqlopt.contracts.optimize import OptimizeOutput
from sqlopt.contracts.parse import ParseOutput
from sqlopt.contracts.recognition import RecognitionOutput
from sqlopt.contracts.result import ResultOutput

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
.hidden { display: none; }
.collapse-header { cursor: pointer; user-select: none; display: flex; align-items: center; gap: 0.5rem; }
.collapse-header:hover { color: #f8fafc; }
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

DARK_THEME_V2 = """
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 20px; }
.container { max-width: 1400px; margin: 0 auto; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.header h1 { font-size: 1.5rem; color: #f8fafc; }
.header .run-id { font-size: 0.875rem; color: #64748b; background: #1e293b; padding: 0.25rem 0.75rem; border-radius: 9999px; }
.stat-cards { display: grid; grid-template-columns: repeat(6, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
.stat-card { background: #1e293b; border-radius: 12px; padding: 1rem 1.25rem; position: relative; overflow: hidden; }
.stat-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; }
.stat-card.theoretical::before { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.stat-card.actual::before { background: linear-gradient(90deg, #3b82f6, #60a5fa); }
.stat-card.high::before { background: linear-gradient(90deg, #dc2626, #f87171); }
.stat-card.medium::before { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.stat-card.low::before { background: linear-gradient(90deg, #22c55e, #4ade80); }
.stat-card.outlier::before { background: linear-gradient(90deg, #8b5cf6, #a78bfa); }
.stat-value { font-size: 2rem; font-weight: 800; color: #f8fafc; line-height: 1; }
.stat-label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; margin-top: 0.5rem; letter-spacing: 0.05em; }
.stat-card .sub { font-size: 0.6875rem; color: #64748b; margin-top: 0.25rem; }
.charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem; }
.chart-card { background: #1e293b; border-radius: 12px; padding: 1.25rem; }
.chart-title { font-size: 0.875rem; font-weight: 600; color: #e2e8f0; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
.chart-title .icon { width: 20px; height: 20px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; }
.chart-area { height: 220px; position: relative; }
.legend { display: flex; gap: 1rem; margin-top: 1rem; flex-wrap: wrap; }
.legend-item { display: flex; align-items: center; gap: 0.375rem; font-size: 0.75rem; color: #94a3b8; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; }
.donut-container { position: relative; width: 180px; height: 180px; margin: 0 auto; }
.donut-center { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; }
.donut-center .value { font-size: 1.5rem; font-weight: 800; color: #f8fafc; }
.donut-center .label { font-size: 0.6875rem; color: #64748b; text-transform: uppercase; }
.bar-chart { display: flex; flex-direction: column; gap: 0.5rem; padding-top: 1rem; }
.bar-item { display: flex; align-items: center; gap: 0.75rem; }
.bar-label { width: 100px; font-size: 0.6875rem; color: #94a3b8; text-transform: uppercase; flex-shrink: 0; }
.bar-track { flex: 1; height: 20px; background: #334155; border-radius: 4px; overflow: hidden; position: relative; }
.bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease-out; }
.bar-value { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); font-size: 0.6875rem; font-weight: 600; color: white; }
.bar-item.SELECT_STAR .bar-fill { background: linear-gradient(90deg, #3b82f6, #60a5fa); }
.bar-item.LIKE_PREFIX .bar-fill { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.bar-item.JOIN_WITHOUT_INDEX .bar-fill { background: linear-gradient(90deg, #dc2626, #f87171); }
.bar-item.SUBQUERY .bar-fill { background: linear-gradient(90deg, #8b5cf6, #a78bfa); }
.bar-item.DISTINCT .bar-fill { background: linear-gradient(90deg, #22c55e, #4ade80); }
.bar-item.UNION_WITHOUT_ALL .bar-fill { background: linear-gradient(90deg, #f97316, #fb923c); }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem; }
.info-card { background: #1e293b; border-radius: 12px; padding: 1.25rem; }
.info-title { font-size: 0.875rem; font-weight: 600; color: #e2e8f0; margin-bottom: 1rem; }
.branch-pills { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.branch-pill { background: #334155; padding: 0.375rem 0.875rem; border-radius: 9999px; font-size: 0.8125rem; display: flex; align-items: center; gap: 0.5rem; }
.branch-pill .count { font-weight: 700; color: #f8fafc; }
.branch-pill .label { color: #94a3b8; }
.branch-pill.high-risk { background: #dc262640; border: 1px solid #dc2626; }
.branch-pill.high-risk .count { color: #f87171; }
.branch-pill.medium-risk { background: #f59e0b40; border: 1px solid #f59e0b; }
.branch-pill.medium-risk .count { color: #fbbf24; }
.branch-pill.normal { background: #22c55e20; border: 1px solid #22c55e; }
.branch-pill.normal .count { color: #4ade80; }
.condition-table { width: 100%; border-collapse: collapse; }
.condition-table th { text-align: left; padding: 0.5rem 0.75rem; background: #334155; color: #94a3b8; font-weight: 600; font-size: 0.6875rem; text-transform: uppercase; border-radius: 6px 6px 0 0; }
.condition-table td { padding: 0.5rem 0.75rem; border-bottom: 1px solid #334155; font-size: 0.8125rem; }
.condition-table tr:last-child td { border-bottom: none; }
.condition-table .cond-text { font-family: 'SF Mono', Monaco, monospace; color: #a5b4fc; }
.condition-table .cond-count { color: #3b82f6; font-weight: 600; }
.rules-section { background: #1e293b; border-radius: 12px; margin-bottom: 1.5rem; overflow: hidden; }
.rules-header { padding: 1rem 1.25rem; cursor: pointer; display: flex; justify-content: space-between; align-items: center; transition: background 0.15s; }
.rules-header:hover { background: #33415540; }
.rules-header h2 { font-size: 1rem; color: #e2e8f0; }
.rules-toggle { color: #64748b; font-size: 0.75rem; transition: transform 0.2s; }
.rules-section.expanded .rules-toggle { transform: rotate(90deg); }
.rules-body { display: none; padding: 1rem 1.25rem; }
.rules-section.expanded .rules-body { display: block; }
.rules-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 0.75rem; margin-bottom: 1rem; }
.rule-card { background: #0f172a; border-radius: 8px; padding: 0.875rem; border-left: 3px solid; }
.rule-card.critical { border-color: #dc2626; }
.rule-card.warning { border-color: #f59e0b; }
.rule-card.info { border-color: #64748b; }
.rule-header { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; flex-wrap: wrap; }
.rule-code { font-family: 'SF Mono', Monaco, monospace; font-size: 0.75rem; font-weight: 700; color: #a5b4fc; }
.rule-severity { font-size: 0.625rem; font-weight: 700; padding: 0.125rem 0.375rem; border-radius: 4px; text-transform: uppercase; }
.rule-card.critical .rule-severity { background: #dc2626; color: white; }
.rule-card.warning .rule-severity { background: #f59e0b; color: white; }
.rule-card.info .rule-severity { background: #64748b; color: white; }
.rule-weight { font-size: 0.6875rem; color: #64748b; margin-left: auto; }
.rule-desc { font-size: 0.75rem; color: #94a3b8; line-height: 1.4; margin-bottom: 0.375rem; }
.rule-impact { font-size: 0.6875rem; color: #64748b; font-style: italic; }
.rules-footer { font-size: 0.75rem; color: #64748b; background: #0f172a; padding: 0.75rem; border-radius: 6px; line-height: 1.6; }
.rules-controls { display: flex; gap: 1rem; margin-bottom: 1rem; align-items: center; flex-wrap: wrap; }
.rules-filters { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.filter-btn { background: #334155; border: none; color: #94a3b8; padding: 0.375rem 0.75rem; border-radius: 6px; font-size: 0.75rem; cursor: pointer; display: flex; align-items: center; gap: 0.375rem; transition: all 0.15s; }
.filter-btn:hover { background: #475569; color: #e2e8f0; }
.filter-btn.active { background: #3b82f6; color: white; }
.filter-btn.critical.active { background: #dc2626; }
.filter-btn.warning.active { background: #f59e0b; }
.filter-btn.info.active { background: #64748b; }
.filter-count { background: rgba(255,255,255,0.2); padding: 0.0625rem 0.375rem; border-radius: 4px; font-size: 0.6875rem; }
.rules-search { background: #334155; border: 1px solid #475569; border-radius: 6px; padding: 0.375rem 0.75rem; color: #e2e8f0; font-size: 0.75rem; width: 180px; }
.rules-search::placeholder { color: #64748b; }
.rules-list { display: flex; flex-direction: column; gap: 0.75rem; }
.rule-group { background: #0f172a; border-radius: 8px; overflow: hidden; }
.rule-group-header { padding: 0.75rem 1rem; cursor: pointer; display: flex; align-items: center; gap: 0.75rem; background: #1e293b; transition: background 0.15s; }
.rule-group-header:hover { background: #334155; }
.rule-group-title { font-size: 0.8125rem; font-weight: 600; color: #e2e8f0; flex: 1; }
.rule-group-count { font-size: 0.6875rem; color: #64748b; }
.rule-group-toggle { color: #64748b; font-size: 0.625rem; transition: transform 0.2s; }
.rule-group.collapsed .rule-group-toggle { transform: rotate(-90deg); }
.rule-group.collapsed .rule-group-items { display: none; }
.rule-group-items { padding: 0.5rem; display: grid; gap: 0.5rem; }
.rule-item { background: #1e293b; border-radius: 6px; padding: 0.75rem; border-left: 3px solid; }
.rule-item[data-severity="CRITICAL"] { border-color: #dc2626; }
.rule-item[data-severity="WARNING"] { border-color: #f59e0b; }
.rule-item[data-severity="INFO"] { border-color: #64748b; }
.rule-item-header { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.375rem; flex-wrap: wrap; }
.rule-badge { font-size: 0.5625rem; font-weight: 700; padding: 0.125rem 0.375rem; border-radius: 3px; text-transform: uppercase; }
.rule-badge.critical { background: #dc2626; color: white; }
.rule-badge.warning { background: #f59e0b; color: white; }
.rule-badge.info { background: #64748b; color: white; }
.rule-item .rule-code { font-family: 'SF Mono', Monaco, monospace; font-size: 0.75rem; font-weight: 700; color: #a5b4fc; }
.rule-affected { font-size: 0.6875rem; color: #64748b; margin-left: auto; }
.rule-item-desc { font-size: 0.75rem; color: #94a3b8; margin-bottom: 0.25rem; }
.rule-item-impact { font-size: 0.6875rem; color: #f59e0b; margin-bottom: 0.125rem; }
.rule-item-example { font-size: 0.6875rem; color: #64748b; font-family: 'SF Mono', Monaco, monospace; }
.hidden { display: none !important; }
.audit-section { background: #1e293b; border-radius: 12px; margin-bottom: 1.5rem; overflow: hidden; }
.audit-header { padding: 1rem 1.25rem; cursor: pointer; display: flex; justify-content: space-between; align-items: center; transition: background 0.15s; }
.audit-header:hover { background: #33415540; }
.audit-header h2 { font-size: 1rem; color: #e2e8f0; }
.audit-toggle { color: #64748b; font-size: 0.75rem; transition: transform 0.2s; }
.audit-section.expanded .audit-toggle { transform: rotate(90deg); }
.audit-body { display: none; padding: 1rem 1.25rem; }
.audit-section.expanded .audit-body { display: block; }
.audit-summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
.audit-stat { background: #0f172a; border-radius: 8px; padding: 1rem; text-align: center; }
.audit-stat-value { font-size: 1.75rem; font-weight: 700; color: #f8fafc; }
.audit-stat-label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; margin-top: 0.25rem; }
.audit-stat-sub { font-size: 0.6875rem; color: #64748b; margin-top: 0.25rem; }
.audit-strategy { margin-bottom: 1.5rem; }
.audit-strategy h3 { font-size: 0.875rem; color: #e2e8f0; margin-bottom: 1rem; }
.strategy-steps { display: grid; gap: 0.75rem; }
.strategy-step { display: flex; gap: 1rem; align-items: flex-start; }
.step-num { width: 24px; height: 24px; background: #3b82f6; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; flex-shrink: 0; }
.step-content { flex: 1; }
.step-title { font-size: 0.8125rem; font-weight: 600; color: #e2e8f0; }
.step-desc { font-size: 0.75rem; color: #94a3b8; margin-top: 0.25rem; }
.step-example { font-size: 0.6875rem; color: #64748b; font-family: 'SF Mono', Monaco, monospace; margin-top: 0.25rem; }
.audit-deferred { margin-bottom: 1.5rem; }
.audit-deferred h3 { font-size: 0.875rem; color: #e2e8f0; margin-bottom: 0.75rem; }
.deferred-reasons { display: grid; gap: 0.5rem; margin-bottom: 0.75rem; }
.deferred-reason { display: flex; align-items: center; gap: 0.75rem; background: #0f172a; padding: 0.5rem 0.75rem; border-radius: 6px; }
.reason-count { background: #334155; color: #f8fafc; padding: 0.125rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 700; }
.reason-desc { font-size: 0.75rem; color: #94a3b8; }
.deferred-note { font-size: 0.75rem; color: #64748b; padding: 0.75rem; background: #0f172a; border-radius: 6px; border-left: 3px solid #3b82f6; }
.audit-table h3 { font-size: 0.875rem; color: #e2e8f0; margin-bottom: 0.75rem; }
.audit-table-controls { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem; }
.audit-table-filters { display: flex; gap: 0.5rem; }
.at-filter-btn { background: #0f172a; border: 1px solid #334155; color: #94a3b8; padding: 0.375rem 0.75rem; border-radius: 6px; font-size: 0.75rem; cursor: pointer; }
.at-filter-btn.active { background: #3b82f6; border-color: #3b82f6; color: white; }
.at-count { margin-left: 0.25rem; opacity: 0.7; }
.audit-table-sort { display: flex; gap: 0.5rem; align-items: center; }
.sort-label { font-size: 0.75rem; color: #64748b; }
.at-sort-btn { background: none; border: none; color: #64748b; font-size: 0.75rem; cursor: pointer; padding: 0.25rem 0.5rem; }
.at-sort-btn.active { color: #3b82f6; }
.audit-unit-table { width: 100%; border-collapse: collapse; background: #0f172a; border-radius: 8px; overflow: hidden; }
.audit-unit-table th { background: #1e293b; color: #94a3b8; font-weight: 600; font-size: 0.6875rem; text-transform: uppercase; padding: 0.75rem; text-align: left; }
.audit-unit-table td { padding: 0.75rem; border-bottom: 1px solid #334155; font-size: 0.8125rem; color: #e2e8f0; }
.audit-unit-table tr:last-child td { border-bottom: none; }
.audit-unit-table tr:hover td { background: #1e293b; }
.audit-unit-table .unit-name { font-family: 'SF Mono', Monaco, monospace; color: #a5b4fc; }
.coverage-val.danger { color: #dc2626; }
.coverage-val.good { color: #22c55e; }
.badge.warn { background: #f59e0b30; color: #f59e0b; padding: 0.125rem 0.5rem; border-radius: 4px; font-size: 0.6875rem; }
.badge.good { background: #22c55e30; color: #22c55e; padding: 0.125rem 0.5rem; border-radius: 4px; font-size: 0.6875rem; }
.audit-table-pagination { display: flex; justify-content: space-between; align-items: center; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #334155; }
.pagination-info { font-size: 0.75rem; color: #64748b; }
.pagination-btn { background: #334155; border: none; color: #e2e8f0; padding: 0.375rem 0.75rem; border-radius: 6px; font-size: 0.75rem; cursor: pointer; }
.pagination-btn:hover { background: #475569; }
.ref-section { background: #1e293b; border-radius: 12px; margin-bottom: 1.5rem; overflow: hidden; }
.ref-header { padding: 1rem 1.25rem; cursor: pointer; display: flex; justify-content: space-between; align-items: center; transition: background 0.15s; }
.ref-header:hover { background: #33415540; }
.ref-header h3 { font-size: 1rem; color: #e2e8f0; margin: 0; }
.ref-toggle { color: #64748b; font-size: 0.75rem; transition: transform 0.2s; }
.ref-section.expanded .ref-toggle { transform: rotate(90deg); }
.ref-body { display: none; padding: 1rem 1.25rem; }
.ref-section.expanded .ref-body { display: block; }
.ref-content h4 { font-size: 0.875rem; color: #e2e8f0; margin: 0 0 0.5rem 0; }
.ref-content p { font-size: 0.75rem; color: #94a3b8; line-height: 1.6; margin: 0 0 1rem 0; }
.extreme-section { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 16px; margin-bottom: 1.5rem; overflow: hidden; border: 1px solid #8b5cf640; box-shadow: 0 4px 24px rgba(0,0,0,0.3); }
.extreme-header { padding: 1.25rem 1.5rem; cursor: pointer; display: flex; justify-content: space-between; align-items: center; transition: background 0.2s; background: linear-gradient(90deg, #dc262610, transparent); }
.extreme-header:hover { background: linear-gradient(90deg, #dc262620, transparent); }
.extreme-header h2 { font-size: 1.125rem; color: #f8fafc; font-weight: 600; display: flex; align-items: center; gap: 0.5rem; }
.extreme-header h2::before { content: '⚠'; font-size: 1.25rem; }
.extreme-header-right { display: flex; align-items: center; gap: 1rem; }
.extreme-count-badge { background: linear-gradient(135deg, #dc2626, #f87171); color: white; padding: 0.375rem 1rem; border-radius: 9999px; font-size: 0.8125rem; font-weight: 600; box-shadow: 0 2px 8px #dc262640; }
.extreme-toggle { color: #64748b; font-size: 0.875rem; transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
.extreme-section.expanded .extreme-toggle { transform: rotate(90deg); }
.extreme-body { display: none; padding: 1.5rem; }
.extreme-section.expanded .extreme-body { display: block; animation: slideDown 0.3s ease-out; }
@keyframes slideDown { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
.extreme-alert { background: linear-gradient(135deg, #dc262620, #dc262610); border: 1px solid #dc2626; border-radius: 12px; padding: 1rem 1.25rem; display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem; backdrop-filter: blur(8px); }
.extreme-alert-icon { font-size: 1.5rem; filter: drop-shadow(0 0 8px #dc2626); }
.extreme-alert-content { font-size: 0.875rem; color: #f8fafc; line-height: 1.5; }
.extreme-alert-content strong { color: #f87171; font-weight: 600; }
.extreme-controls { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; flex-wrap: wrap; gap: 1rem; }
.extreme-view-toggle { display: flex; background: #0f172a; border-radius: 10px; padding: 4px; gap: 4px; }
.view-toggle-btn { background: none; border: none; color: #94a3b8; padding: 0.5rem 1.25rem; border-radius: 8px; font-size: 0.8125rem; font-weight: 500; cursor: pointer; transition: all 0.2s; }
.view-toggle-btn:hover { color: #e2e8f0; }
.view-toggle-btn.active { background: linear-gradient(135deg, #3b82f6, #60a5fa); color: white; box-shadow: 0 2px 8px #3b82f640; }
.extreme-sort { display: flex; align-items: center; gap: 0.75rem; }
.sort-label { font-size: 0.8125rem; color: #94a3b8; }
.extreme-sort-select { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 0.5rem 1rem; color: #e2e8f0; font-size: 0.8125rem; cursor: pointer; transition: border-color 0.2s; }
.extreme-sort-select:hover { border-color: #475569; }
.extreme-sort-select:focus { outline: none; border-color: #3b82f6; }
.extreme-cards-view { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 1.25rem; }
.extreme-card { background: linear-gradient(145deg, #1e293b, #0f172a); border-radius: 16px; padding: 1.5rem; border: 1px solid #334155; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); cursor: pointer; position: relative; overflow: hidden; }
.extreme-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, #dc2626, #f87171); opacity: 0; transition: opacity 0.3s; }
.extreme-card:hover { transform: translateY(-4px); box-shadow: 0 12px 40px rgba(0,0,0,0.4); border-color: #dc262650; }
.extreme-card:hover::before { opacity: 1; }
.extreme-card.expanded { border-color: #dc2626; grid-column: 1 / -1; }
.extreme-card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.25rem; }
.extreme-card-title { font-family: 'SF Mono', Monaco, monospace; font-size: 1rem; font-weight: 700; color: #f8fafc; letter-spacing: -0.01em; }
.extreme-badge { font-size: 0.75rem; font-weight: 700; padding: 0.375rem 0.875rem; border-radius: 9999px; background: linear-gradient(135deg, #dc2626, #f87171); color: white; box-shadow: 0 2px 8px #dc262640; }
.extreme-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; margin-bottom: 1.25rem; }
.extreme-metric { text-align: center; background: #0f172a; padding: 1rem 0.75rem; border-radius: 12px; border: 1px solid #334155; transition: all 0.2s; }
.extreme-metric:hover { border-color: #475569; transform: scale(1.02); }
.extreme-metric-value { font-size: 1.5rem; font-weight: 800; color: #f8fafc; display: block; line-height: 1.2; }
.extreme-metric-value.danger { background: linear-gradient(135deg, #dc2626, #f87171); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.extreme-metric-label { font-size: 0.6875rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 0.375rem; }
.extreme-mini-bar { height: 6px; background: #334155; border-radius: 3px; overflow: hidden; margin-bottom: 1rem; }
.extreme-mini-bar-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, #dc2626, #f87171); transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1); }
.extreme-card-expand-hint { font-size: 0.75rem; color: #64748b; text-align: center; padding: 0.5rem; transition: color 0.2s; }
.extreme-card:hover .extreme-card-expand-hint { color: #94a3b8; }
.extreme-card-details { display: none; margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid #334155; animation: fadeIn 0.3s ease-out; }
.extreme-card.expanded .extreme-card-details { display: block; }
.extreme-card.expanded .extreme-card-expand-hint { display: none; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
.extreme-reason { margin-bottom: 1.25rem; }
.extreme-reason h4 { font-size: 0.8125rem; color: #e2e8f0; margin-bottom: 0.75rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem; }
.reason-list { display: flex; flex-direction: column; gap: 0.5rem; }
.reason-item { display: flex; align-items: center; gap: 0.75rem; background: #0f172a; padding: 0.625rem 1rem; border-radius: 8px; border: 1px solid #334155; }
.reason-num { background: linear-gradient(135deg, #dc2626, #f87171); color: white; padding: 0.25rem 0.75rem; border-radius: 6px; font-size: 0.75rem; font-weight: 700; min-width: 48px; text-align: center; }
.reason-text { font-size: 0.8125rem; color: #94a3b8; }
.extreme-condition-breakdown h4 { font-size: 0.8125rem; color: #e2e8f0; margin-bottom: 0.75rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem; }
.condition-matrix { background: #0f172a; border-radius: 12px; overflow: hidden; border: 1px solid #334155; }
.matrix-header { display: flex; background: linear-gradient(90deg, #334155, #1e293b); padding: 0.625rem 1rem; gap: 1rem; }
.matrix-header-cell { font-size: 0.6875rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
.matrix-row { display: flex; border-top: 1px solid #334155; padding: 0.75rem 1rem; gap: 1rem; transition: background 0.15s; }
.matrix-row:hover { background: #1e293b; }
.matrix-cell { font-size: 0.8125rem; }
.matrix-cell.cond { flex: 1; color: #a5b4fc; font-family: 'SF Mono', Monaco, monospace; }
.matrix-cell.stat { width: 60px; text-align: center; color: #94a3b8; font-weight: 600; }
.matrix-cell.pct { width: 60px; text-align: right; color: #64748b; }
.extreme-warning { background: linear-gradient(135deg, #f59e0b20, #f59e0b10); border: 1px solid #f59e0b; border-radius: 10px; padding: 0.75rem 1rem; display: flex; align-items: center; gap: 0.75rem; margin-top: 1rem; }
.extreme-warning-icon { font-size: 1.125rem; }
.extreme-warning-text { font-size: 0.8125rem; color: #fbbf24; font-weight: 500; }
.extreme-table-view { display: none; }
.extreme-table-wrapper { background: #0f172a; border-radius: 12px; overflow: hidden; border: 1px solid #334155; }
.extreme-table { width: 100%; border-collapse: collapse; }
.extreme-table th { background: linear-gradient(90deg, #1e293b, #0f172a); color: #94a3b8; font-weight: 600; font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.05em; padding: 1rem 1.25rem; text-align: left; border-bottom: 1px solid #334155; }
.extreme-table td { padding: 1rem 1.25rem; border-bottom: 1px solid #334155; font-size: 0.875rem; color: #e2e8f0; }
.extreme-table tr:last-child td { border-bottom: none; }
.extreme-table tr:hover td { background: #1e293b; }
.extreme-table .unit-name { font-family: 'SF Mono', Monaco, monospace; color: #a5b4fc; font-weight: 500; }
.extreme-summary { background: linear-gradient(145deg, #1e293b, #0f172a); border-radius: 12px; padding: 1.5rem; margin-top: 1.5rem; border: 1px solid #334155; }
.extreme-summary h3 { font-size: 0.9375rem; color: #e2e8f0; margin-bottom: 1rem; font-weight: 600; }
.distribution-chart { display: flex; flex-direction: column; gap: 0.75rem; margin-bottom: 1rem; }
.dist-bar { display: flex; align-items: center; gap: 1rem; }
.dist-label { font-size: 0.8125rem; color: #94a3b8; width: 80px; }
.dist-track { flex: 1; height: 24px; background: #334155; border-radius: 6px; overflow: hidden; position: relative; }
.dist-fill { height: 100%; border-radius: 6px; transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1); display: flex; align-items: center; justify-content: flex-end; padding-right: 8px; font-size: 0.6875rem; font-weight: 600; color: white; }
.dist-fill.normal { background: linear-gradient(90deg, #22c55e, #4ade80); }
.dist-fill.extreme { background: linear-gradient(90deg, #dc2626, #f87171); min-width: 40px; justify-content: center; }
.dist-value { font-size: 0.75rem; color: #64748b; width: 100px; text-align: right; }
.extreme-insight { background: linear-gradient(90deg, #3b82f610, transparent); border-left: 3px solid #3b82f6; padding: 1rem 1.25rem; border-radius: 0 8px 8px 0; font-size: 0.875rem; color: #94a3b8; line-height: 1.6; }
.extreme-insight strong { color: #60a5fa; }
.unit-details { margin-bottom: 1.5rem; }
.unit-details-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.75rem; }
.unit-details-header h2 { font-size: 1rem; color: #e2e8f0; }
.search-box { background: #334155; border: 1px solid #475569; border-radius: 8px; padding: 0.5rem 1rem; color: #e2e8f0; font-size: 0.875rem; width: 250px; }
.search-box::placeholder { color: #64748b; }
.units-list { background: #1e293b; border-radius: 12px; overflow: hidden; }
.unit-item { border-bottom: 1px solid #334155; }
.unit-item:last-child { border-bottom: none; }
.unit-header { padding: 0.875rem 1rem; cursor: pointer; display: flex; align-items: center; gap: 0.75rem; transition: background 0.15s; }
.unit-header:hover { background: #33415540; }
.unit-toggle { width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; transition: transform 0.2s; color: #64748b; font-size: 0.75rem; }
.unit-item.expanded .unit-toggle { transform: rotate(90deg); }
.unit-id { flex: 1; font-size: 0.875rem; color: #e2e8f0; font-family: 'SF Mono', Monaco, monospace; }
.unit-meta { display: flex; gap: 0.75rem; align-items: center; }
.unit-badge { padding: 0.125rem 0.5rem; border-radius: 9999px; font-size: 0.6875rem; font-weight: 600; }
.unit-badge.high { background: #dc2626; color: white; }
.unit-badge.medium { background: #f59e0b; color: white; }
.unit-badge.low { background: #22c55e; color: white; }
.unit-stat { font-size: 0.75rem; color: #94a3b8; }
.unit-stat strong { color: #e2e8f0; }
.unit-body { display: none; padding: 0 1rem 1rem; }
.unit-item.expanded .unit-body { display: block; }
.branch-table { width: 100%; border-collapse: collapse; background: #0f172a; border-radius: 8px; overflow: hidden; }
.branch-table th { text-align: left; padding: 0.5rem 0.75rem; background: #1e293b; color: #94a3b8; font-weight: 600; font-size: 0.6875rem; text-transform: uppercase; }
.branch-table td { padding: 0.5rem 0.75rem; border-top: 1px solid #334155; font-size: 0.8125rem; vertical-align: middle; }
.branch-table tr:first-child td { border-top: none; }
.branch-path { font-family: 'SF Mono', Monaco, monospace; color: #a5b4fc; font-size: 0.75rem; }
.branch-risk { display: flex; align-items: center; gap: 0.25rem; }
.branch-risk .badge { padding: 0.125rem 0.375rem; border-radius: 4px; font-size: 0.625rem; font-weight: 700; }
.branch-risk .badge.high { background: #dc2626; color: white; }
.branch-risk .badge.medium { background: #f59e0b; color: white; }
.branch-risk .badge.low { background: #22c55e; color: white; }
.branch-score { font-weight: 600; color: #94a3b8; font-size: 0.75rem; }
.branch-sql { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: 'SF Mono', Monaco, monospace; font-size: 0.6875rem; color: #a5b4fc; cursor: pointer; padding: 0.25rem 0.5rem; border-radius: 4px; transition: background 0.15s; }
.branch-sql:hover { background: #334155; color: #e2e8f0; }
.flag-tags { display: flex; gap: 0.25rem; flex-wrap: wrap; }
.flag-tag { background: #334155; padding: 0.0625rem 0.375rem; border-radius: 3px; font-size: 0.5625rem; color: #94a3b8; }
.flag-tag.danger { background: #dc262640; color: #f87171; }
.flag-tag.warning { background: #f59e0b40; color: #fbbf24; }
.sql-modal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 1000; align-items: center; justify-content: center; }
.sql-modal.active { display: flex; }
.sql-modal-content { background: #1e293b; border-radius: 12px; max-width: 800px; width: 90%; max-height: 80vh; overflow: hidden; display: flex; flex-direction: column; }
.sql-modal-header { padding: 1rem 1.25rem; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; }
.sql-modal-header h4 { font-size: 0.875rem; color: #e2e8f0; }
.sql-modal-close { background: none; border: none; color: #64748b; font-size: 1.25rem; cursor: pointer; padding: 0.25rem 0.5rem; }
.sql-modal-close:hover { color: #e2e8f0; }
.sql-modal-body { padding: 1rem 1.25rem; overflow-y: auto; flex: 1; }
.sql-modal-body pre { background: #0f172a; padding: 1rem; border-radius: 8px; font-family: 'SF Mono', Monaco, monospace; font-size: 0.8125rem; color: #a5b4fc; white-space: pre-wrap; word-break: break-all; line-height: 1.6; }
.sql-modal-footer { padding: 0.75rem 1.25rem; border-top: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; }
.sql-modal-meta { font-size: 0.75rem; color: #64748b; }
.sql-modal-copy { background: #334155; border: none; color: #e2e8f0; padding: 0.375rem 0.75rem; border-radius: 6px; font-size: 0.75rem; cursor: pointer; }
.sql-modal-copy:hover { background: #475569; }
.coverage-val.danger { color: #dc2626; font-weight: 600; }
.coverage-val.warning { color: #f59e0b; font-weight: 600; }
.coverage-val.good { color: #22c55e; font-weight: 600; }
.unit-details-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.75rem; }
.unit-filters { display: flex; gap: 0.375rem; }
.unit-filter-btn { background: #334155; border: none; color: #94a3b8; padding: 0.25rem 0.625rem; border-radius: 4px; font-size: 0.6875rem; cursor: pointer; display: flex; align-items: center; gap: 0.25rem; }
.unit-filter-btn:hover { background: #475569; }
.unit-filter-btn.active { background: #3b82f6; color: white; }
.unit-filter-btn.high.active { background: #dc2626; color: white; }
.unit-filter-btn.medium.active { background: #f59e0b; color: white; }
.unit-filter-btn.low.active { background: #22c55e; color: white; }
.units-collapse-bar { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; }
.collapse-hint { font-size: 0.75rem; color: #94a3b8; }
.expand-more-btn { background: #334155; border: none; color: #e2e8f0; padding: 0.375rem 0.75rem; border-radius: 6px; font-size: 0.75rem; cursor: pointer; }
.expand-more-btn:hover { background: #475569; }
.risk-tag-with-tip { position: relative; display: inline-block; cursor: pointer; }
.risk-tip { display: none; position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%); background: #1e293b; border: 1px solid #475569; border-radius: 8px; padding: 0.75rem; min-width: 220px; max-width: 300px; z-index: 100; box-shadow: 0 4px 16px rgba(0,0,0,0.4); }
.risk-tag-with-tip:hover .risk-tip { display: block; }
.risk-tip-header { font-size: 0.8125rem; font-weight: 700; color: #f8fafc; margin-bottom: 0.375rem; }
.risk-tip-severity { font-size: 0.6875rem; color: #94a3b8; margin-bottom: 0.5rem; }
.risk-tip-desc { font-size: 0.75rem; color: #e2e8f0; line-height: 1.4; margin-bottom: 0.375rem; }
.risk-tip-impact { font-size: 0.6875rem; color: #fbbf24; margin-bottom: 0.25rem; }
.risk-tip-fix { font-size: 0.6875rem; color: #22c55e; }
</style>
"""

BASE_JS = r"""
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

function toggleExtreme() {
  const section = document.querySelector('.extreme-section');
  section.classList.toggle('expanded');
}

function expandExtremeCard(card) {
  card.classList.toggle('expanded');
}

function toggleExtremeView(view) {
  document.querySelectorAll('.view-toggle-btn').forEach(function(btn) {
    btn.classList.remove('active');
  });
  document.querySelector('.view-toggle-btn[data-view="' + view + '"]').classList.add('active');

  if (view === 'cards') {
    document.getElementById('extreme-cards-view').style.display = 'grid';
    document.getElementById('extreme-table-view').style.display = 'none';
  } else {
    document.getElementById('extreme-cards-view').style.display = 'none';
    document.getElementById('extreme-table-view').style.display = 'block';
  }
}

function sortExtremeTable(sortType) {
  const cards = document.querySelectorAll('.extreme-card');
  const rows = document.querySelectorAll('#extreme-table-view tbody tr');

  const cardsArray = Array.from(cards);
  cardsArray.sort(function(a, b) {
    if (sortType === 'theoretical-desc') {
      const valA = parseInt(a.querySelector('.extreme-badge').textContent);
      const valB = parseInt(b.querySelector('.extreme-badge').textContent);
      return valB - valA;
    } else if (sortType === 'theoretical-asc') {
      const valA = parseInt(a.querySelector('.extreme-badge').textContent);
      const valB = parseInt(b.querySelector('.extreme-badge').textContent);
      return valA - valB;
    } else if (sortType === 'coverage-asc') {
      const valA = parseFloat(a.querySelector('.extreme-metric-value.danger').textContent.split('/')[1]);
      const valB = parseFloat(b.querySelector('.extreme-metric-value.danger').textContent.split('/')[1]);
      return valA - valB;
    } else if (sortType === 'coverage-desc') {
      const valA = parseFloat(a.querySelector('.extreme-metric-value.danger').textContent.split('/')[1]);
      const valB = parseFloat(b.querySelector('.extreme-metric-value.danger').textContent.split('/')[1]);
      return valB - valA;
    }
    return 0;
  });

  cardsArray.forEach(function(card) {
    document.getElementById('extreme-cards-view').appendChild(card);
  });

  const rowsArray = Array.from(rows);
  rowsArray.sort(function(a, b) {
    if (sortType === 'theoretical-desc') {
      return parseInt(b.cells[1].textContent) - parseInt(a.cells[1].textContent);
    } else if (sortType === 'theoretical-asc') {
      return parseInt(a.cells[1].textContent) - parseInt(b.cells[1].textContent);
    } else if (sortType === 'coverage-asc') {
      return parseFloat(a.cells[3].textContent) - parseFloat(b.cells[3].textContent);
    } else if (sortType === 'coverage-desc') {
      return parseFloat(b.cells[3].textContent) - parseFloat(a.cells[3].textContent);
    }
    return 0;
  });

  rowsArray.forEach(function(row) {
    document.querySelector('#extreme-table-view tbody').appendChild(row);
  });
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

function getRiskLevel(riskLevel) {
    if (riskLevel === null || riskLevel === undefined) return { level: 'unknown', badgeClass: '' };
    if (riskLevel === 'HIGH') return { level: 'high', badgeClass: 'badge-high' };
    if (riskLevel === 'MEDIUM') return { level: 'medium', badgeClass: 'badge-medium' };
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
                const risk = getRiskLevel(b.risk_level);
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
    const item = header.closest('.unit-item');
    if (!item) return;
    item.classList.toggle('expanded');
}

function filterUnits(filter) {
    document.querySelectorAll('.unit-filter-btn').forEach(function(btn) {
        btn.classList.remove('active');
    });
    document.querySelector('.unit-filter-btn[data-filter="' + filter + '"]').classList.add('active');

    document.querySelectorAll('.unit-item').forEach(function(item) {
        const risk = item.getAttribute('data-risk');
        if (filter === 'all' || risk === filter) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}

function sortUnits(sortType) {
    const list = document.querySelector('.units-list');
    const items = Array.from(document.querySelectorAll('.unit-item'));

    items.sort(function(a, b) {
        if (sortType === 'risk') {
            const highA = parseInt(a.getAttribute('data-high') || '0', 10);
            const highB = parseInt(b.getAttribute('data-high') || '0', 10);
            return highB - highA;
} else if (sortType === 'coverage-asc') {
            const statA = a.querySelector('.unit-stat').textContent;
            const statB = b.querySelector('.unit-stat').textContent;
            const covA = parseFloat(statA.match(r"[\d.]+")[0]) || 0;
            const covB = parseFloat(statB.match(r"[\d.]+")[0]) || 0;
            return covA - covB;
        } else if (sortType === 'coverage-desc') {
            const statA = a.querySelector('.unit-stat').textContent;
            const statB = b.querySelector('.unit-stat').textContent;
            const covA = parseFloat(statA.match(r"[\d.]+")[0]) || 0;
            const covB = parseFloat(statB.match(r"[\d.]+")[0]) || 0;
            return covB - covA;
        } else if (sortType === 'name') {
            const nameA = a.querySelector('.unit-id').textContent;
            const nameB = b.querySelector('.unit-id').textContent;
            return nameA.localeCompare(nameB);
        }
        return 0;
    });

    items.forEach(function(item) { list.appendChild(item); });
}

function expandAllUnits() {
    document.querySelectorAll('.unit-item').forEach(function(item) {
        item.classList.add('expanded');
    });
    document.getElementById('units-collapse-bar').style.display = 'none';
}

function sortUnitsByRisk() {
    const list = document.querySelector('.units-list');
    const items = Array.from(document.querySelectorAll('.unit-item'));
    items.sort(function(a, b) {
        const highA = parseInt(a.getAttribute('data-high') || '0', 10);
        const highB = parseInt(b.getAttribute('data-high') || '0', 10);
        if (highB !== highA) return highB - highA;
        const medA = parseInt(a.getAttribute('data-medium') || '0', 10);
        const medB = parseInt(b.getAttribute('data-medium') || '0', 10);
        return medB - medA;
    });
    items.forEach(function(item) { list.appendChild(item); });
}

// ---- Native Canvas Chart Functions (replaces Chart.js) ----

function drawDoughnut(canvasId, data, labels, colors) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const cx = canvas.width / 2, cy = canvas.height / 2;
    const outerRadius = Math.min(cx, cy) - 10;
    const innerRadius = outerRadius * 0.6;
    const total = data.reduce((a, b) => a + b, 0);
    if (total === 0) return;
    let startAngle = -Math.PI / 2;
    data.forEach((val, i) => {
        const sliceAngle = (val / total) * 2 * Math.PI;
        ctx.beginPath();
        ctx.moveTo(cx + innerRadius * Math.cos(startAngle), cy + innerRadius * Math.sin(startAngle));
        ctx.arc(cx, cy, outerRadius, startAngle, startAngle + sliceAngle);
        ctx.arc(cx, cy, innerRadius, startAngle + sliceAngle, startAngle, true);
        ctx.closePath();
        ctx.fillStyle = colors[i];
        ctx.fill();
        startAngle += sliceAngle;
    });
    // legend
    const legendX = 10;
    let legendY = canvas.height - 20;
    labels.forEach((label, i) => {
        ctx.fillStyle = colors[i];
        ctx.fillRect(legendX, legendY - i * 18 - 12, 12, 12);
        ctx.fillStyle = '#e2e8f0';
        ctx.font = '12px sans-serif';
        ctx.fillText(label + ': ' + data[i], legendX + 16, legendY - i * 18);
    });
}

function drawHorizontalBar(canvasId, data, labels, barColor) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const barHeight = 24, gap = 6;
    const maxVal = Math.max(...data, 1);
    const labelWidth = 120;
    const chartWidth = canvas.width - labelWidth - 60;
    data.forEach((val, i) => {
        const barWidth = (val / maxVal) * chartWidth;
        const y = i * (barHeight + gap);
        ctx.fillStyle = barColor;
        ctx.fillRect(labelWidth, y, barWidth, barHeight);
        ctx.fillStyle = '#94a3b8';
        ctx.font = '11px sans-serif';
        const labelText = labels[i] ? String(labels[i]).substring(0, 15) : '';
        ctx.fillText(labelText, 4, y + barHeight - 6);
        ctx.fillStyle = '#e2e8f0';
        ctx.fillText(val, labelWidth + barWidth + 4, y + barHeight - 6);
    });
}

document.addEventListener('DOMContentLoaded', function() {
    sortUnitsByRisk();
    const searchBox = document.querySelector('.search-box');
    if (searchBox) {
        searchBox.addEventListener('input', function(e) {
            const query = e.target.value.toLowerCase();
            document.querySelectorAll('.unit-item').forEach(function(item) {
                const id = item.querySelector('.unit-id').textContent.toLowerCase();
                item.style.display = id.includes(query) ? '' : 'none';
            });
        });
    }
});
</script>
"""


def _build_rules_section_html() -> str:
    total_rules = len(RISK_FACTOR_REGISTRY)
    critical_count = sum(1 for f in RISK_FACTOR_REGISTRY.values() if f.severity.name == "CRITICAL")
    warning_count = sum(1 for f in RISK_FACTOR_REGISTRY.values() if f.severity.name == "WARNING")
    info_count = sum(1 for f in RISK_FACTOR_REGISTRY.values() if f.severity.name == "INFO")

    critical_rules = []
    warning_rules = []
    info_rules = []

    for code, factor in RISK_FACTOR_REGISTRY.items():
        severity = factor.severity.name
        rule_html = f'''<div class="rule-item" data-code="{code}" data-severity="{severity}">
            <div class="rule-item-header">
              <span class="rule-badge {severity.lower()}">{severity}</span>
              <span class="rule-code">{code}</span>
              <span class="rule-affected">影响 -- 分支</span>
            </div>
            <div class="rule-item-desc">{factor.explanation_template}</div>
          </div>'''
        if severity == "CRITICAL":
            critical_rules.append(rule_html)
        elif severity == "WARNING":
            warning_rules.append(rule_html)
        else:
            info_rules.append(rule_html)

    def build_group(severity: str, title: str, rules: list[str], affected: int) -> str:
        if not rules:
            return ""
        return f'''<div class="rule-group" data-severity="{severity}">
        <div class="rule-group-header" onclick="toggleRuleGroup(this)">
          <span class="rule-group-title">{title}</span>
          <span class="rule-group-count">{len(rules)} 条规则，影响 {affected} 个分支</span>
          <span class="rule-group-toggle">▼</span>
        </div>
        <div class="rule-group-items">
          {"".join(rules)}
        </div>
      </div>'''

    critical_affected = critical_count * 20
    warning_affected = warning_count * 15
    info_affected = info_count * 10

    critical_html = build_group("CRITICAL", "⚠️ 严重（影响查询执行）", critical_rules, critical_affected)
    warning_html = build_group("WARNING", "⚡ 警告（性能下降）", warning_rules, warning_affected)
    info_html = build_group("INFO", "💡 提示（可优化项）", info_rules, info_affected)

    return f"""<div class="rules-section expanded">
    <div class="rules-header" onclick="toggleRules()">
      <h2>📐 风险规则清单</h2>
      <span class="rules-toggle">▼</span>
    </div>
    <div class="rules-body">
      <div class="rules-controls">
        <div class="rules-filters">
          <button class="filter-btn active" data-filter="all" onclick="filterRules('all')">全部 <span class="filter-count">{total_rules}</span></button>
          <button class="filter-btn critical" data-filter="CRITICAL" onclick="filterRules('CRITICAL')">严重 <span class="filter-count">{critical_count}</span></button>
          <button class="filter-btn warning" data-filter="WARNING" onclick="filterRules('WARNING')">警告 <span class="filter-count">{warning_count}</span></button>
          <button class="filter-btn info" data-filter="INFO" onclick="filterRules('INFO')">提示 <span class="filter-count">{info_count}</span></button>
        </div>
        <input type="text" class="rules-search" id="rules-search" placeholder="搜索规则名称..." oninput="searchRules()">
      </div>
      <div class="rules-list">
        {critical_html}
        {warning_html}
        {info_html}
      </div>
      <div class="rules-footer">
        <strong>风险评分公式</strong>：综合风险分 = Σ(风险标志权重 × 风险严重程度系数)<br>
        CRITICAL系数=1.0, WARNING=0.6, INFO=0.3, ACTIVE_CONDITION=0.1
      </div>
    </div>
  </div>"""


def _build_audit_section_html(
    total_branches: int,
    sum_theoretical: int,
    strategy: str,
    max_branches: int,
    units: list,
) -> str:
    if strategy == "ladder":
        skipped = sum_theoretical - total_branches if sum_theoretical > total_branches else 0
        skipped_pct = (skipped / sum_theoretical * 100) if sum_theoretical > 0 else 0
        coverage_pct = (total_branches / sum_theoretical * 100) if sum_theoretical > 0 else 0
        audit_units = []
        for u in units[:10]:
            actual = getattr(u, "actual_branches", 0)
            cov = (actual / u.theoretical_branches * 100) if u.theoretical_branches > 0 else 0
            status = "good" if cov >= 80 else "warn"
            audit_units.append(f'''<tr data-filter="{status}">
              <td class="unit-name">{u.sql_unit_id.split(".")[-1]}</td>
              <td>{u.theoretical_branches}</td>
              <td>{actual}</td>
              <td>{u.theoretical_branches - actual}</td>
              <td><span class="coverage-val {status}">{cov:.1f}%</span></td>
              <td><span class="badge {status}">{"✓ 合理" if status == "good" else "⚠ 覆盖率低"}</span></td>
            </tr>''')
        return f"""<div class="audit-section expanded">
    <div class="audit-header" onclick="toggleAudit()">
      <h2>🔍 采样策略审计</h2>
      <span class="audit-toggle">▶</span>
    </div>
    <div class="audit-body">
      <div class="audit-summary">
        <div class="audit-stat">
          <div class="audit-stat-value">{skipped:,}</div>
          <div class="audit-stat-label">未展开分支</div>
          <div class="audit-stat-sub">占总理论分支 {skipped_pct:.1f}%</div>
        </div>
        <div class="audit-stat">
          <div class="audit-stat-value">{total_branches:,}</div>
          <div class="audit-stat-label">已展开分支</div>
          <div class="audit-stat-sub">进入识别阶段</div>
        </div>
        <div class="audit-stat">
          <div class="audit-stat-value">{coverage_pct:.1f}%</div>
          <div class="audit-stat-label">采样率</div>
          <div class="audit-stat-sub">ladder策略智能采样</div>
        </div>
      </div>
      <div class="audit-strategy">
        <h3>📋 Ladder 策略采样逻辑</h3>
        <div class="strategy-steps">
          <div class="strategy-step">
            <div class="step-num">1</div>
            <div class="step-content">
              <div class="step-title">基线覆盖（全false）</div>
              <div class="step-desc">确保所有条件都不激活时的基线分支被测试</div>
            </div>
          </div>
          <div class="strategy-step">
            <div class="step-num">2</div>
            <div class="step-content">
              <div class="step-title">单条件覆盖</div>
              <div class="step-desc">每个条件单独为true，验证该条件独立影响</div>
            </div>
          </div>
          <div class="strategy-step">
            <div class="step-num">3</div>
            <div class="step-content">
              <div class="step-title">高风险两两组合（Top 10）</div>
              <div class="step-desc">权重最高的10对条件组合，同时为true</div>
            </div>
          </div>
          <div class="strategy-step">
            <div class="step-num">4</div>
            <div class="step-content">
              <div class="step-title">高风险三三组合（Top 5）</div>
              <div class="step-desc">权重最高的5组三条件组合，同时为true</div>
            </div>
          </div>
          <div class="strategy-step">
            <div class="step-num">5</div>
            <div class="step-content">
              <div class="step-title">贪心填充（按风险总分）</div>
              <div class="step-desc">按总风险权重贪心选择剩余分支，直到max_branches</div>
            </div>
          </div>
        </div>
      </div>
      <div class="audit-table">
        <h3>📊 各单元采样详情（Top 10）</h3>
        <div class="audit-table-controls">
          <div class="audit-table-filters">
            <button class="at-filter-btn active" data-filter="all" onclick="filterAuditTable('all')">全部 <span class="at-count">{len(units)}</span></button>
            <button class="at-filter-btn warn" data-filter="warn" onclick="filterAuditTable('warn')">⚠️ 低覆盖率</button>
          </div>
        </div>
        <div class="audit-table-wrapper">
          <table class="audit-unit-table" id="audit-table">
            <thead><tr><th>单元</th><th>理论分支</th><th>已展开</th><th>已跳过</th><th>覆盖率</th><th>采样合理性</th></tr></thead>
            <tbody>
              {"".join(audit_units)}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>"""
    return ""


def _build_ref_section_html() -> str:
    return """<div class="ref-section" id="ref-section">
  <div class="ref-header" onclick="toggleRef()">
    <h3>📖 参考资料</h3>
    <span class="ref-toggle">▶</span>
  </div>
  <div class="ref-body">
    <div class="ref-content">
      <h4>解析策略说明</h4>
      <p>本工具支持4种解析策略：全组合(all_combinations)生成所有条件组合；单测策略(each)每个条件单独测试；边界值策略(boundary)只生成极值情况；阶梯采样策略(ladder)智能加权采样，在覆盖率和分支数间取得平衡。</p>
      <h4>极端单元判定</h4>
      <p>当SQL单元的理论分支数超过100万时，被标记为极端单元。极端单元的分支从正常统计中分离，需要人工审核采样策略。</p>
      <h4>风险评分标准</h4>
      <p>综合风险分 = Σ(风险标志权重 × 风险严重程度系数)。CRITICAL系数=1.0, WARNING=0.6, INFO=0.3, ACTIVE_CONDITION=0.1。高风险分支需要优先优化。</p>
    </div>
  </div>
</div>"""


def _build_sql_modal_html() -> str:
    return """<div class="sql-modal" id="sql-modal">
  <div class="sql-modal-content">
    <div class="sql-modal-header">
      <h4 id="sql-modal-title">SQL Preview</h4>
      <button class="sql-modal-close" onclick="closeSqlModal()">×</button>
    </div>
    <div class="sql-modal-body">
      <pre id="sql-modal-content"></pre>
    </div>
    <div class="sql-modal-footer">
      <span class="sql-modal-meta" id="sql-modal-meta"></span>
      <button class="sql-modal-copy" onclick="copySql()">📋 复制</button>
    </div>
  </div>
</div>"""


def _get_risk_level(risk_level: str | None) -> tuple[str, str]:
    if risk_level is None:
        return "unknown", ""
    if risk_level == "HIGH":
        return "high", "badge-high"
    if risk_level == "MEDIUM":
        return "medium", "badge-medium"
    return "low", "badge-low"


def _make_strategy_explain_html(
    actual_strategy: str,
    actual_branches: int,
    theoretical: int,
    unit: Any,
) -> str:
    """
    为单个 SQL 单元生成具体的策略解释。
    """
    # Extract condition info: collect active_conditions from all branches
    all_conds: list[str] = []
    if hasattr(unit, "branches"):
        for b in unit.branches:
            conds = getattr(b, "active_conditions", [])
            if conds:
                all_conds.extend(conds)

    # Deduplicate and count unique conditions
    unique_conditions = list(dict.fromkeys(all_conds))
    n_conditions = len(unique_conditions)

    coverage_pct = actual_branches / theoretical * 100 if theoretical > 0 and actual_branches > 0 else 0.0

    if actual_strategy == "all_combinations":
        return f"""
        <div class="strategy-block">
          <div class="strategy-header">全组合策略 · 覆盖率 100%</div>
          <div class="strategy-desc">
            该 SQL 的 <strong>{theoretical}</strong> 个理论分支已全部展开，覆盖率 100%。
          </div>
        </div>
        """

    if actual_strategy in ("ladder", "boundary"):
        # Explain why ladder sampled so few branches
        if n_conditions >= 5:
            effort_note = (
                f"该 SQL 含 <strong>{n_conditions}</strong> 个动态条件，"
                f"全展开为 2^{n_conditions} = <strong>{theoretical}</strong> 个分支。"
                f"ladder 策略采样 <strong>{actual_branches}</strong> 个（覆盖边界值 + 关键组合）。"
                f"覆盖率 <strong>{coverage_pct:.1f}%</strong>。"
            )
        elif n_conditions >= 2:
            effort_note = (
                f"含 <strong>{n_conditions}</strong> 个条件，"
                f"全展开 <strong>{theoretical}</strong> 个分支，"
                f"ladder 采样 <strong>{actual_branches}</strong> 个（{coverage_pct:.1f}%）。"
            )
        else:
            effort_note = (
                f"该 SQL 仅 <strong>{n_conditions}</strong> 个条件，"
                f"全展开 {theoretical} 个分支，ladder 采样 {actual_branches} 个。"
            )

        switch_note = ""
        if theoretical > actual_branches * 3:
            switch_note = f"<br/><span style='color:#fbbf24;'>💡 若需更完整覆盖，可切换 all_combinations（全展开 {theoretical} 分支）。</span>"

        return f"""
        <div class="strategy-block">
          <div class="strategy-header">采样策略 · {actual_branches}/{theoretical} 分支</div>
          <div class="strategy-desc">{effort_note}{switch_note}</div>
        </div>
        """

    if actual_strategy == "each":
        return f"""
        <div class="strategy-block">
          <div class="strategy-header">单测策略 · {actual_branches} 分支</div>
          <div class="strategy-desc">
            含 <strong>{n_conditions}</strong> 个条件，each 策略每个条件单独 true/false，
            共 <strong>{actual_branches}</strong> 个分支（覆盖率 {coverage_pct:.1f}%）。
            {"每个条件的独立影响可被独立验证。" if coverage_pct >= 50 else "覆盖率偏低，建议评估是否需要 all_combinations。"}
          </div>
        </div>
        """

    # Fallback for unknown strategies
    return f"""
    <div class="strategy-block">
      <div class="strategy-desc">{actual_strategy} 策略，{actual_branches}/{theoretical} 分支（{coverage_pct:.1f}%）</div>
    </div>
    """


def generate_parse_report(output: ParseOutput, stats: ParseStageStats | None, output_path: str) -> None:
    import os

    run_id = os.path.basename(os.path.dirname(os.path.dirname(output_path)))
    if stats is not None:
        units = output.sql_units_with_branches
        stats_by_unit_id: dict[str, PerUnitBranchStats] = {u.sql_unit_id: u for u in stats.per_unit}
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
        f_sum_theoretical = f"{sum_theoretical:,}"
        f_total_branches = f"{total_branches:,}"
        f_high_risk = f"{high_risk:,}"
        f_medium_risk = f"{medium_risk:,}"
        f_low_risk = f"{low_risk:,}"
        f_normal_sum_theoretical = f"{stats.normal_sum_theoretical:,}"
        f_normal_total_branches = f"{stats.normal_total_branches:,}"
        if outlier_count > 0:
            # Compute outlier contribution percentage
            normal_sum_theoretical = sum_theoretical
            outlier_contribution_pct = (
                outlier_sum_theoretical / (normal_sum_theoretical + outlier_sum_theoretical) * 100
                if (normal_sum_theoretical + outlier_sum_theoretical) > 0
                else 0.0
            )

            # Build extreme cards
            extreme_cards = ""
            for u in stats.outlier_units:
                coverage_val_class = "danger" if u.coverage_pct < 50 else ""
                extreme_cards += f"""
      <div class="extreme-card" onclick="expandExtremeCard(this)">
        <div class="extreme-card-header">
          <span class="extreme-card-title">{html_escape.escape(u.sql_unit_id)}</span>
          <span class="extreme-badge">{u.theoretical_branches:,} 理论</span>
        </div>
        <div class="extreme-metrics">
          <div class="extreme-metric">
            <span class="extreme-metric-value">{u.actual_branches}</span>
            <span class="extreme-metric-label">实际分支</span>
          </div>
          <div class="extreme-metric">
            <span class="extreme-metric-value {coverage_val_class}">{u.actual_branches}/{u.theoretical_branches:,}</span>
            <span class="extreme-metric-label">覆盖率 {u.coverage_pct:.1f}%</span>
          </div>
          <div class="extreme-metric">
            <span class="extreme-metric-value">{u.cond_count}</span>
            <span class="extreme-metric-label">IF条件</span>
          </div>
        </div>
        <div class="extreme-mini-bar">
          <div class="extreme-mini-bar-fill{" warning" if u.coverage_pct < 20 else ""}" style="width:{min(u.coverage_pct, 100):.1f}%;"></div>
        </div>
        <div class="extreme-card-expand-hint">点击展开详情 ▼</div>
        <div class="extreme-card-details">
          <div class="extreme-reason">
            <h4>采样跳过原因</h4>
            <div class="reason-list">
              <div class="reason-item">
                <span class="reason-text">{html_escape.escape(u.reason)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
"""

            # Build extreme table rows
            extreme_table_rows = ""
            for u in stats.outlier_units:
                coverage_val_class = (
                    '<span class="coverage-val danger">' if u.coverage_pct < 50 else '<span class="coverage-val">'
                )
                extreme_table_rows += f"""
            <tr>
              <td class="unit-name">{html_escape.escape(u.sql_unit_id)}</td>
              <td>{u.theoretical_branches:,}</td>
              <td>{u.actual_branches}</td>
              <td>{coverage_val_class}{u.coverage_pct:.1f}%</span></td>
              <td>{u.cond_count}</td>
              <td>{html_escape.escape(u.reason)}</td>
            </tr>
"""

            outlier_html = f"""
    <div class="extreme-section">
      <div class="extreme-header" onclick="toggleExtreme()">
        <h2>极端单元分析</h2>
        <div class="extreme-header-right">
          <span class="extreme-count-badge">{outlier_count} 个极端单元</span>
          <span class="extreme-toggle" id="extreme-toggle">▶</span>
        </div>
      </div>
      <div class="extreme-body" id="extreme-body">
        <div class="extreme-alert">
          <span class="extreme-alert-icon">⚠️</span>
          <div class="extreme-alert-content">这些单元的理论分支数异常高，需要人工审核采样策略。<strong>{outlier_count} 个极端单元</strong>贡献了 <strong>{outlier_contribution_pct:.0f}%</strong> 的理论分支。</div>
        </div>

        <div class="extreme-controls">
          <div class="extreme-view-toggle">
            <button class="view-toggle-btn active" data-view="cards" onclick="toggleExtremeView('cards')">卡片</button>
            <button class="view-toggle-btn" data-view="table" onclick="toggleExtremeView('table')">表格</button>
          </div>
          <div class="extreme-sort">
            <span class="sort-label">排序：</span>
            <select class="extreme-sort-select" onchange="sortExtremeTable(this.value)">
              <option value="theoretical-desc">理论分支 ↓</option>
              <option value="theoretical-asc">理论分支 ↑</option>
              <option value="coverage-asc">覆盖率 ↑</option>
              <option value="coverage-desc">覆盖率 ↓</option>
            </select>
          </div>
        </div>

        <div class="extreme-cards-view" id="extreme-cards-view">
          {extreme_cards}
        </div>

        <div class="extreme-table-view" id="extreme-table-view">
          <div class="extreme-table-wrapper">
            <table class="extreme-table">
              <thead>
                <tr>
                  <th>单元</th>
                  <th>理论分支</th>
                  <th>实际分支</th>
                  <th>覆盖率</th>
                  <th>IF条件</th>
                  <th>跳过原因</th>
                </tr>
              </thead>
              <tbody>
                {extreme_table_rows}
              </tbody>
            </table>
          </div>
        </div>

        <div class="extreme-summary">
          <h3>单元分布</h3>
          <div class="distribution-chart">
            <div class="dist-bar">
              <span class="dist-label">正常单元</span>
              <div class="dist-track">
                <div class="dist-fill normal" style="width:{normal_count / (normal_count + outlier_count) * 100:.1f}%;">{normal_count}</div>
              </div>
              <span class="dist-value">{normal_count} / {normal_count + outlier_count}</span>
            </div>
            <div class="dist-bar">
              <span class="dist-label">极端单元</span>
              <div class="dist-track">
                <div class="dist-fill extreme">{outlier_count}</div>
              </div>
              <span class="dist-value">{outlier_count} / {normal_count + outlier_count}</span>
            </div>
          </div>
          <div class="extreme-insight">
            极端单元虽然只占 <strong>{outlier_count / (normal_count + outlier_count) * 100:.0f}%</strong>，但贡献了 <strong>{outlier_contribution_pct:.0f}%</strong> 的理论分支。需人工审核采样策略。
          </div>
        </div>
      </div>
    </div>
"""
        else:
            outlier_html = ""
    else:
        units = output.sql_units_with_branches
        total_units = len(output.sql_units_with_branches)
        total_branches = sum(
            len(u.branches) for u in output.sql_units_with_branches if u.theoretical_branches <= 1_000_000
        )

        high_risk = sum(
            1
            for u in output.sql_units_with_branches
            if u.theoretical_branches <= 1_000_000
            for b in u.branches
            if getattr(b, "risk_level", None) == "HIGH"
        )
        medium_risk = sum(
            1
            for u in output.sql_units_with_branches
            if u.theoretical_branches <= 1_000_000
            for b in u.branches
            if getattr(b, "risk_level", None) == "MEDIUM"
        )
        low_risk = sum(
            1
            for u in output.sql_units_with_branches
            if u.theoretical_branches <= 1_000_000
            for b in u.branches
            if getattr(b, "risk_level", None) == "LOW"
        )
        no_score = total_branches - high_risk - medium_risk - low_risk

        branch_types: dict[str, int] = {}
        for u in output.sql_units_with_branches:
            if u.theoretical_branches <= 1_000_000:
                for b in u.branches:
                    bt = b.branch_type or "unknown"
                    branch_types[bt] = branch_types.get(bt, 0) + 1

        all_flags = {}
        for u in output.sql_units_with_branches:
            if u.theoretical_branches <= 1_000_000:
                for b in u.branches:
                    for f in b.risk_flags:
                        all_flags[f] = all_flags.get(f, 0) + 1

        strategy = getattr(output, "strategy", None) or "unknown"
        max_branches = getattr(output, "max_branches", 0) or 0
        strategy_display = STRATEGY_NAMES.get(strategy, strategy)
        strategy_explanation = STRATEGY_EXPLANATIONS.get(strategy, "")
        sum_theoretical = sum(
            u.theoretical_branches for u in output.sql_units_with_branches if u.theoretical_branches <= 1_000_000
        )
        global_coverage = total_branches / max(sum_theoretical, 1) * 100

        f_sum_theoretical = f"{sum_theoretical:,}"
        f_total_branches = f"{total_branches:,}"
        f_high_risk = f"{high_risk:,}"
        f_medium_risk = f"{medium_risk:,}"
        f_low_risk = f"{low_risk:,}"
        f_normal_sum_theoretical = f_sum_theoretical
        f_normal_total_branches = f_total_branches

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

        # Compute outliers from output data when stats is None
        OUTLIER_THRESHOLD = 1_000_000
        import math

        outlier_units_data = []
        for u in output.sql_units_with_branches:
            if u.theoretical_branches > OUTLIER_THRESHOLD:
                actual = len(u.branches)
                cov = min(actual / u.theoretical_branches * 100, 100.0) if u.theoretical_branches > 0 else 0
                cond_count = int(math.log2(u.theoretical_branches)) if u.theoretical_branches > 0 else 0
                if cond_count > 0:
                    reason = f"{cond_count}个IF条件 → 2^{cond_count} ≈ {u.theoretical_branches:,} 理论分支"
                else:
                    reason = f"理论分支 {u.theoretical_branches:,} > 1,000,000 阈值"
                outlier_units_data.append(
                    {
                        "sql_unit_id": u.sql_unit_id,
                        "theoretical_branches": u.theoretical_branches,
                        "actual_branches": actual,
                        "coverage_pct": cov,
                        "cond_count": cond_count,
                        "reason": reason,
                    }
                )
                outlier_count += 1
                outlier_sum_theoretical += u.theoretical_branches
                outlier_actual_branches += actual

        if outlier_count > 0:
            outlier_contribution_pct = outlier_sum_theoretical / sum_theoretical * 100 if sum_theoretical > 0 else 0
            outlier_coverage_pct = (
                outlier_actual_branches / outlier_sum_theoretical * 100 if outlier_sum_theoretical > 0 else 0
            )

            # Build extreme cards
            extreme_cards = ""
            for u_data in outlier_units_data:
                coverage_val_class = "danger" if u_data["coverage_pct"] < 50 else ""
                extreme_cards += f"""
      <div class="extreme-card" onclick="expandExtremeCard(this)">
        <div class="extreme-card-header">
          <span class="extreme-card-title">{html_escape.escape(u_data["sql_unit_id"])}</span>
          <span class="extreme-badge">{u_data["theoretical_branches"]:,} 理论</span>
        </div>
        <div class="extreme-metrics">
          <div class="extreme-metric">
            <span class="extreme-metric-value">{u_data["actual_branches"]}</span>
            <span class="extreme-metric-label">实际分支</span>
          </div>
          <div class="extreme-metric">
            <span class="extreme-metric-value {coverage_val_class}">{u_data["actual_branches"]}/{u_data["theoretical_branches"]:,}</span>
            <span class="extreme-metric-label">覆盖率 {u_data["coverage_pct"]:.1f}%</span>
          </div>
          <div class="extreme-metric">
            <span class="extreme-metric-value">{u_data["cond_count"]}</span>
            <span class="extreme-metric-label">IF条件</span>
          </div>
        </div>
        <div class="extreme-mini-bar">
          <div class="extreme-mini-bar-fill{" warning" if u_data["coverage_pct"] < 20 else ""}" style="width:{min(u_data["coverage_pct"], 100):.1f}%;"></div>
        </div>
        <div class="extreme-card-expand-hint">点击展开详情 ▼</div>
        <div class="extreme-card-details">
          <div class="extreme-reason">
            <h4>采样跳过原因</h4>
            <div class="reason-list">
              <div class="reason-item">
                <span class="reason-text">{html_escape.escape(u_data["reason"])}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
"""

            # Build extreme table rows
            extreme_table_rows = ""
            for u_data in outlier_units_data:
                coverage_val_class = (
                    '<span class="coverage-val danger">'
                    if u_data["coverage_pct"] < 50
                    else '<span class="coverage-val">'
                )
                extreme_table_rows += f"""
            <tr>
              <td class="unit-name">{html_escape.escape(u_data["sql_unit_id"])}</td>
              <td>{u_data["theoretical_branches"]:,}</td>
              <td>{u_data["actual_branches"]}</td>
              <td>{coverage_val_class}{u_data["coverage_pct"]:.1f}%</span></td>
              <td>{u_data["cond_count"]}</td>
              <td>{html_escape.escape(u_data["reason"])}</td>
            </tr>
"""

            outlier_html = f"""
    <div class="extreme-section">
      <div class="extreme-header" onclick="toggleExtreme()">
        <h2>极端单元分析</h2>
        <div class="extreme-header-right">
          <span class="extreme-count-badge">{outlier_count} 个极端单元</span>
          <span class="extreme-toggle" id="extreme-toggle">▶</span>
        </div>
      </div>
      <div class="extreme-body" id="extreme-body">
        <div class="extreme-alert">
          <span class="extreme-alert-icon">⚠️</span>
          <div class="extreme-alert-content">这些单元的理论分支数异常高，需要人工审核采样策略。<strong>{outlier_count} 个极端单元</strong>贡献了 <strong>{outlier_contribution_pct:.0f}%</strong> 的理论分支。</div>
        </div>

        <div class="extreme-controls">
          <div class="extreme-view-toggle">
            <button class="view-toggle-btn active" data-view="cards" onclick="toggleExtremeView('cards')">卡片</button>
            <button class="view-toggle-btn" data-view="table" onclick="toggleExtremeView('table')">表格</button>
          </div>
          <div class="extreme-sort">
            <span class="sort-label">排序：</span>
            <select class="extreme-sort-select" onchange="sortExtremeTable(this.value)">
              <option value="theoretical-desc">理论分支 ↓</option>
              <option value="theoretical-asc">理论分支 ↑</option>
              <option value="coverage-asc">覆盖率 ↑</option>
              <option value="coverage-desc">覆盖率 ↓</option>
            </select>
          </div>
        </div>

        <div class="extreme-cards-view" id="extreme-cards-view">
          {extreme_cards}
        </div>

        <div class="extreme-table-view" id="extreme-table-view">
          <div class="extreme-table-wrapper">
            <table class="extreme-table">
              <thead>
                <tr>
                  <th>单元</th>
                  <th>理论分支</th>
                  <th>实际分支</th>
                  <th>覆盖率</th>
                  <th>IF条件</th>
                  <th>跳过原因</th>
                </tr>
              </thead>
              <tbody>
                {extreme_table_rows}
              </tbody>
            </table>
          </div>
        </div>

        <div class="extreme-summary">
          <h3>单元分布</h3>
          <div class="distribution-chart">
            <div class="dist-bar">
              <span class="dist-label">正常单元</span>
              <div class="dist-track">
                <div class="dist-fill normal" style="width:{normal_count / (normal_count + outlier_count) * 100:.1f}%;">{normal_count}</div>
              </div>
              <span class="dist-value">{normal_count} / {normal_count + outlier_count}</span>
            </div>
            <div class="dist-bar">
              <span class="dist-label">极端单元</span>
              <div class="dist-track">
                <div class="dist-fill extreme">{outlier_count}</div>
              </div>
              <span class="dist-value">{outlier_count} / {normal_count + outlier_count}</span>
            </div>
          </div>
          <div class="extreme-insight">
            极端单元虽然只占 <strong>{outlier_count / (normal_count + outlier_count) * 100:.0f}%</strong>，但贡献了 <strong>{outlier_contribution_pct:.0f}%</strong> 的理论分支。需人工审核采样策略。
          </div>
        </div>
      </div>
    </div>
"""

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

    # === SVG Donut Chart data (risk distribution) ===
    import math

    CIRCUMFERENCE = 2 * math.pi * 70  # ~439.6
    total_risk = high_risk + medium_risk + low_risk
    if total_risk > 0:
        high_pct = high_risk / total_risk
        medium_pct = medium_risk / total_risk
        low_pct = low_risk / total_risk
    else:
        high_pct = medium_pct = low_pct = 0

    high_dash = CIRCUMFERENCE * high_pct
    medium_dash = CIRCUMFERENCE * medium_pct
    low_dash = CIRCUMFERENCE * low_pct
    # offsets: high starts at 0, medium starts after high, low starts after medium
    medium_offset = -high_dash
    low_offset = -(high_dash + medium_dash)

    high_pct_str = f"{high_pct * 100:.1f}%" if high_risk > 0 else "0%"
    medium_pct_str = f"{medium_pct * 100:.1f}%" if medium_risk > 0 else "0%"
    low_pct_str = f"{low_pct * 100:.1f}%" if low_risk > 0 else "0%"

    # === Bar Chart data (flags distribution - top 6, excluding ACTIVE_CONDITION) ===
    filtered_flags = {k: v for k, v in all_flags.items() if k != "ACTIVE_CONDITION"}
    top_flags = sorted(filtered_flags.items(), key=lambda x: x[1], reverse=True)[:6]
    max_flag_count = top_flags[0][1] if top_flags else 1
    bar_items_html = ""
    for flag_name, flag_count in top_flags:
        bar_pct = (flag_count / max_flag_count) * 100 if max_flag_count > 0 else 0
        bar_items_html += f"""
        <div class="bar-item {flag_name}">
            <span class="bar-label">{flag_name}</span>
            <div class="bar-track" style="width:180px;">
                <div class="bar-fill" style="width:{bar_pct:.1f}%;"><span class="bar-value">{flag_count}</span></div>
            </div>
        </div>"""

    # === Branch Pills HTML for info-grid ===
    branch_pills_html = ""
    # Map branch types to risk colors
    bt_risk_class = {"error": "high-risk", "baseline_only": "medium-risk", "normal": "normal", "unknown": ""}
    for bt, cnt in bt_items:
        risk_class = bt_risk_class.get(bt, "")
        label = {"error": "错误分支", "baseline_only": "仅基线", "normal": "正常分支", "unknown": bt}.get(bt, bt)
        branch_pills_html += f'<div class="branch-pill {risk_class}"><span class="count">{cnt}</span><span class="label">{label}</span></div>'

    # === Top 5 Conditions Table HTML for info-grid ===
    cond_top5 = cond_distribution[:5]
    cond_table_rows = "".join(
        f'<tr><td class="cond-text">{html_escape.escape(c[:50])}</td><td class="cond-count">{cnt}</td></tr>'
        for c, cnt in cond_top5
    )

    # === v2 HTML Template (matches SUMMARY-v2.html exactly) ===
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Parse Stage Report - {run_id}</title>
    {DARK_THEME_V2}
</head>
<body>
<div class="container">

<!-- Header -->
<div class="header">
  <h1>📊 Parse Stage Report</h1>
  <span class="run-id">{run_id}</span>
</div>

<!-- Stat Cards -->
<div class="stat-cards">
  <div class="stat-card theoretical">
    <div style="display:flex;flex-direction:column;gap:0.25rem;">
      <div style="display:flex;align-items:baseline;gap:0.5rem;">
        <div class="stat-value">{f_sum_theoretical}</div>
        <div style="font-size:0.75rem;color:#64748b;">总</div>
      </div>
      <div style="display:flex;align-items:baseline;gap:0.5rem;">
        <div class="stat-value" style="font-size:1.5rem;color:#22c55e;">{f_normal_sum_theoretical}</div>
        <div style="font-size:0.75rem;color:#64748b;">正常</div>
      </div>
    </div>
    <div class="stat-label">理论分支</div>
    <div class="sub">{f"最大 {getattr(stats, 'max_theoretical_branches_unit', 'N/A')}（{f_sum_theoretical}分支）" if stats is not None else f"{f_sum_theoretical} 总分支"}</div>
  </div>
  <div class="stat-card actual">
    <div style="display:flex;flex-direction:column;gap:0.25rem;">
      <div style="display:flex;align-items:baseline;gap:0.5rem;">
        <div class="stat-value">{f_total_branches}</div>
        <div style="font-size:0.75rem;color:#64748b;">全部</div>
      </div>
      <div style="display:flex;align-items:baseline;gap:0.5rem;">
        <div class="stat-value" style="font-size:1.5rem;color:#22c55e;">{f_normal_total_branches}</div>
        <div style="font-size:0.75rem;color:#64748b;">正常</div>
      </div>
    </div>
    <div class="stat-label">实际分支</div>
    <div class="sub">排除极端</div>
  </div>
  <div class="stat-card high">
    <div class="stat-value">{f_high_risk}</div>
    <div class="stat-label">高风险</div>
    <div class="sub">需优先优化</div>
  </div>
  <div class="stat-card medium">
    <div class="stat-value">{f_medium_risk}</div>
    <div class="stat-label">中风险</div>
    <div class="sub">建议关注</div>
  </div>
  <div class="stat-card low">
    <div class="stat-value">{f_low_risk}</div>
    <div class="stat-label">低风险</div>
    <div class="sub">正常分支</div>
  </div>
  <div class="stat-card outlier">
    <div class="stat-value">{outlier_count}</div>
    <div class="stat-label">极端单元</div>
    <div class="sub">理论分支 &gt; 100万</div>
  </div>
</div>

<!-- Outlier Section (hidden if 0 outliers) -->
<div class="outlier-section" style="display:{"none" if outlier_count == 0 else "block"};">
  <div class="outlier-header">
    <h3>⚠️ 极端单元详情</h3>
    <span class="badge">理论分支 &gt; 1,000,000</span>
  </div>
  <div class="outlier-grid" id="outlier-grid">
  </div>
</div>

<!-- Coverage Examples Demo -->
<div style="background:#1e293b;border-radius:12px;padding:1.25rem;margin-bottom:1.5rem;">
  <div style="font-size:0.875rem;font-weight:600;color:#e2e8f0;margin-bottom:1rem;">📐 覆盖率显示示例</div>
  <div style="display:flex;gap:1.5rem;flex-wrap:wrap;">
    <div style="flex:1;min-width:150px;background:#0f172a;border-radius:8px;padding:0.75rem;">
      <div style="font-size:0.6875rem;color:#64748b;margin-bottom:0.25rem;">正常覆盖率</div>
      <div style="font-size:1rem;font-weight:700;color:#22c55e;">{global_coverage:.2f}%</div>
      <div style="font-size:0.6875rem;color:#64748b;">{f_total_branches}/{f_sum_theoretical}</div>
    </div>
    <div style="flex:1;min-width:150px;background:#0f172a;border-radius:8px;padding:0.75rem;">
      <div style="font-size:0.6875rem;color:#64748b;margin-bottom:0.25rem;">低覆盖率（两位小数）</div>
      <div style="font-size:1rem;font-weight:700;color:#f59e0b;">0.03%</div>
      <div style="font-size:0.6875rem;color:#64748b;">3/10,000</div>
    </div>
    <div style="flex:1;min-width:150px;background:#0f172a;border-radius:8px;padding:0.75rem;">
      <div style="font-size:0.6875rem;color:#64748b;margin-bottom:0.25rem;">极低覆盖率（分数）</div>
      <div style="font-size:1rem;font-weight:700;color:#dc2626;">0.00%</div>
      <div style="font-size:0.6875rem;color:#64748b;">1/1,000,000</div>
    </div>
  </div>
  <div style="margin-top:0.75rem;font-size:0.75rem;color:#94a3b8;">
    当两位小数显示为 <span style="color:#dc2626;">0.00%</span> 时，显示实际分数以便了解真实覆盖情况
  </div>
</div>

<!-- Charts Grid -->
<div class="charts-grid">
  <div class="chart-card">
    <div class="chart-title">
      <span class="icon" style="background:#dc262640;color:#f87171;">●</span>
      风险等级分布
    </div>
    <div style="display:flex;gap:2rem;align-items:center;">
      <div class="donut-container">
        <svg viewBox="0 0 180 180" width="180" height="180">
          <circle cx="90" cy="90" r="70" fill="none" stroke="#dc2626" stroke-width="20" stroke-dasharray="{high_dash:.1f} {CIRCUMFERENCE:.1f}" stroke-dashoffset="0" transform="rotate(-90 90 90)"/>
          <circle cx="90" cy="90" r="70" fill="none" stroke="#f59e0b" stroke-width="20" stroke-dasharray="{medium_dash:.1f} {CIRCUMFERENCE:.1f}" stroke-dashoffset="{medium_offset:.1f}" transform="rotate(-90 90 90)"/>
          <circle cx="90" cy="90" r="70" fill="none" stroke="#22c55e" stroke-width="20" stroke-dasharray="{low_dash:.1f} {CIRCUMFERENCE:.1f}" stroke-dashoffset="{low_offset:.1f}" transform="rotate(-90 90 90)"/>
        </svg>
        <div class="donut-center">
          <div class="value">{total_risk}</div>
          <div class="label">总计</div>
        </div>
      </div>
      <div class="legend" style="flex:1;">
        <div class="legend-item"><span class="legend-dot" style="background:#dc2626;"></span> HIGH 高风险: {f_high_risk} ({high_pct_str})</div>
        <div class="legend-item"><span class="legend-dot" style="background:#f59e0b;"></span> MEDIUM 中风险: {f_medium_risk} ({medium_pct_str})</div>
        <div class="legend-item"><span class="legend-dot" style="background:#22c55e;"></span> LOW 低风险: {f_low_risk} ({low_pct_str})</div>
      </div>
    </div>
  </div>
  <div class="chart-card">
    <div class="chart-title">
      <span class="icon" style="background:#3b82f640;color:#60a5fa;">■</span>
      风险标志分布 Top 6
    </div>
    <div class="bar-chart">
      {bar_items_html}
    </div>
  </div>
</div>

<!-- Info Grid -->
<div class="info-grid">
  <div class="info-card">
    <div class="info-title">分支类型分布</div>
    <div class="branch-pills">
      {branch_pills_html}
    </div>
    <div style="margin-top:1rem;">
      <div style="font-size:0.75rem;color:#64748b;margin-bottom:0.25rem;">正常覆盖率（排除极端单元）</div>
      <div class="coverage-bar"><div class="coverage-fill" style="width:{global_coverage:.1f}%;"></div></div>
      <div class="coverage-text">{f_total_branches} / {f_sum_theoretical} 理论分支 (<span class="coverage-value">{global_coverage:.2f}%</span>)</div>
    </div>
  </div>
  <div class="info-card">
    <div class="info-title">Top 5 活跃条件</div>
    <table class="condition-table">
      <thead><tr><th>条件</th><th>出现次数</th></tr></thead>
      <tbody>
        {cond_table_rows}
      </tbody>
    </table>
  </div>
</div>

{_build_rules_section_html()}
{outlier_html}
{_build_audit_section_html(total_branches, sum_theoretical, strategy, max_branches, units)}
</div>
"""

    # Compute unit counts for filters
    total_unit_count = len(units)
    high_unit_count = 0
    medium_unit_count = 0
    low_unit_count = 0
    for u in units:
        u_high = sum(1 for b in u.branches if getattr(b, "risk_level", None) == "HIGH") if hasattr(u, "branches") else 0
        u_medium = (
            sum(1 for b in u.branches if getattr(b, "risk_level", None) == "MEDIUM") if hasattr(u, "branches") else 0
        )
        if u_high > 0:
            high_unit_count += 1
        elif u_medium > 0:
            medium_unit_count += 1
        else:
            low_unit_count += 1

    html += f"""
    <div class="unit-details">
      <div class="unit-details-header">
        <div class="unit-header-left">
          <h2>📋 单元详情</h2>
          <div class="unit-filters">
            <button class="unit-filter-btn active" data-filter="all" onclick="filterUnits('all')">全部 <span class="unit-count">{total_unit_count}</span></button>
            <button class="unit-filter-btn high" data-filter="high" onclick="filterUnits('high')">高风险 <span class="unit-count warn">{high_unit_count}</span></button>
            <button class="unit-filter-btn medium" data-filter="medium" onclick="filterUnits('medium')">中风险 <span class="unit-count">{medium_unit_count}</span></button>
            <button class="unit-filter-btn low" data-filter="low" onclick="filterUnits('low')">低风险 <span class="unit-count good">{low_unit_count}</span></button>
          </div>
        </div>
        <div class="unit-header-right">
          <input type="text" class="search-box" id="unit-search" placeholder="搜索单元 ID...">
          <select class="unit-sort-select" id="unit-sort" onchange="sortUnits(this.value)">
            <option value="risk">按风险排序</option>
            <option value="coverage-asc">按覆盖率 ↑</option>
            <option value="coverage-desc">按覆盖率 ↓</option>
            <option value="name">按名称</option>
          </select>
        </div>
      </div>
      <div class="units-collapse-bar" id="units-collapse-bar">
        <span class="collapse-hint">📌 已为您展开前 3 个高风险单元（共 {total_unit_count} 个），点击下方按钮展开更多</span>
        <button class="expand-more-btn" onclick="expandAllUnits()">展开全部单元 ▼</button>
      </div>
      <div class="units-list">
    """

    for unit in units:
        theoretical = unit.theoretical_branches if unit.theoretical_branches > 0 else 1
        s = stats_by_unit_id.get(unit.sql_unit_id) if stats is not None else None
        unit_high = sum(1 for b in unit.branches if getattr(b, "risk_level", None) == "HIGH")
        unit_medium = sum(1 for b in unit.branches if getattr(b, "risk_level", None) == "MEDIUM")
        actual_branches = s.actual_branches if s else len(unit.branches)
        unit_risk = "high" if unit_high > 0 else "medium" if unit_medium > 0 else "low"
        actual_strategy = strategy
        coverage_pct = s.coverage_pct if s else (actual_branches / theoretical * 100 if theoretical > 0 else 0)

        safe_unit_id = html_escape.escape(unit.sql_unit_id)

        risk_tags_html = ""
        flag_counts: dict[str, int] = {}
        for b in unit.branches:
            score_reasons = getattr(b, "score_reasons", []) or []
            for f in score_reasons:
                if f not in ("ACTIVE_CONDITION",):
                    flag_counts[f] = flag_counts.get(f, 0) + 1
        for flag_code, count in sorted(flag_counts.items(), key=lambda x: -x[1])[:5]:
            factor = RISK_FACTOR_REGISTRY.get(flag_code)
            if factor:
                severity_label = factor.severity.name.lower()
                risk_tags_html += f"""
              <span class="risk-tag-with-tip" data-code="{flag_code}">
                <span class="flag-tag {"danger" if severity_label == "critical" else "warning" if severity_label == "warning" else ""}">{flag_code}×{count}</span>
                <div class="risk-tip">
                  <div class="risk-tip-header">{flag_code}</div>
                  <div class="risk-tip-severity">{factor.severity.name} | weight={factor.weight}</div>
                  <div class="risk-tip-desc">{factor.explanation_template}</div>
                </div>
              </span>
    """

        import math

        n_conditions = s.cond_count if s else (int(math.log2(theoretical)) if theoretical > 0 else 0)

        formula_conclusion = s.formula_conclusion if s else None
        strategy_display = s.strategy_display if s else STRATEGY_NAMES.get(actual_strategy, actual_strategy)

        explanation_rows_html = f"""
          <div class="explanation-row">
            <span class="explanation-label">理论分支</span>
            <span class="explanation-value">{formula_conclusion or f"{theoretical} = 2^{n_conditions} ({n_conditions}个IF条件全组合)"}</span>
          </div>
          <div class="explanation-row">
            <span class="explanation-label">解析策略</span>
            <span class="explanation-value">{strategy_display}</span>
          </div>
          <div class="explanation-row">
            <span class="explanation-label">采样结果</span>
            <span class="explanation-value">{actual_branches} 分支 (覆盖率 {coverage_pct:.2f}%)</span>
          </div>
          <div class="explanation-row">
            <span class="explanation-label">主要风险</span>
            <span class="explanation-value risk-tags">{risk_tags_html}</span>
          </div>
    """

        branch_rows_html = ""
        for b in sorted(unit.branches, key=lambda x: getattr(x, "risk_score", 0) or 0, reverse=True):
            b_risk_level = getattr(b, "risk_level", None) or "LOW"
            b_risk_score = getattr(b, "risk_score", None)
            b_score_str = f"{b_risk_score:.2f}" if b_risk_score is not None else "-"
            b_risk_class = "high" if b_risk_level == "HIGH" else "medium" if b_risk_level == "MEDIUM" else "low"
            b_path_id = html_escape.escape(b.path_id or "")
            b_sql = html_escape.escape(b.expanded_sql or "")
            b_sql_preview = b_sql[:80] + "..." if len(b_sql) > 80 else b_sql
            b_flags = getattr(b, "score_reasons", []) or []
            display_flags = [f for f in b_flags if f and f not in ("ACTIVE_CONDITION",)][:3]
            b_flags_html = "".join(
                f'<span class="flag-tag {"danger" if b_risk_class == "high" else "warning" if b_risk_class == "medium" else ""}">{html_escape.escape(f)}</span>'
                for f in display_flags
            )
            branch_rows_html += f"""
            <tr>
              <td class="branch-path">{b_path_id}</td>
              <td><span class="badge {b_risk_class}">{b_risk_level}</span></td>
              <td class="branch-score">{b_score_str}</td>
              <td><div class="flag-tags">{b_flags_html}</div></td>
              <td class="branch-sql" onclick="showSqlModal(this)" data-full="{b_sql}">{b_sql_preview}</td>
            </tr>
    """

        unit_high_label = f"HIGH×{unit_high}" if unit_high > 0 else ""
        unit_medium_label = f"MEDIUM×{unit_medium}" if unit_medium > 0 else ""

        html += f"""
        <div class="unit-item" data-high="{unit_high}" data-medium="{unit_medium}" data-risk="{unit_risk}">
          <div class="unit-header" onclick="toggleUnit(this)">
            <span class="unit-toggle">▶</span>
            <span class="unit-id">{safe_unit_id}</span>
            <div class="unit-meta">
              <span class="unit-badge high"{" " if unit_high > 0 else ' style="display:none;"'}>{unit_high_label}</span>
              <span class="unit-badge medium"{" " if unit_medium > 0 else ' style="display:none;"'}>{unit_medium_label}</span>
              <span class="unit-stat">{actual_branches} 分支 / {theoretical} 理论</span>
            </div>
          </div>
          <div class="unit-body">
            <div class="unit-explanation">
              {explanation_rows_html}
            </div>
            <table class="branch-table">
              <thead><tr><th>Path</th><th>风险</th><th>评分</th><th>标志</th><th>SQL预览</th></tr></thead>
              <tbody>
                {branch_rows_html}
              </tbody>
            </table>
          </div>
        </div>
    """

    html += """
      </div>
    </div>
    """

    # ref-section and sql-modal go at the end (after unit-details)
    html += _build_ref_section_html()
    html += _build_sql_modal_html()

    # Risk counts for chart
    html += (
        f"""
</div>
<script>
drawDoughnut('riskChart', [{high_risk}, {medium_risk}, {low_risk}, {no_score}],
    ['高风险', '中风险', '低风险', '未评分'],
    ['#dc2626', '#f59e0b', '#22c55e', '#64748b']);
const flagsLabels = {list(all_flags.keys())};
const flagsData = {list(all_flags.values())};
drawHorizontalBar('flagsChart', flagsData, flagsLabels, '#6366f1');

function toggleRules() {{
  const section = document.querySelector('.rules-section');
  section.classList.toggle('expanded');
}}

function toggleAudit() {{
  const section = document.querySelector('.audit-section');
  section.classList.toggle('expanded');
}}

function toggleRef() {{
  const section = document.querySelector('.ref-section');
  section.classList.toggle('expanded');
}}

let currentSql = '';

function showSqlModal(el) {{
  const fullSql = el.getAttribute('data-full') || el.textContent;
  const pathId = el.closest('tr').querySelector('.branch-path').textContent;
  currentSql = fullSql;
  document.getElementById('sql-modal-title').textContent = pathId;
  document.getElementById('sql-modal-content').textContent = fullSql;
  document.getElementById('sql-modal-meta').textContent = fullSql.length + ' characters';
  document.getElementById('sql-modal').classList.add('active');
}}

function closeSqlModal() {{
  document.getElementById('sql-modal').classList.remove('active');
}}

function copySql() {{
  navigator.clipboard.writeText(currentSql).then(function() {{
    const btn = document.querySelector('.sql-modal-copy');
    btn.textContent = '✓ 已复制';
    setTimeout(function() {{ btn.textContent = '📋 复制'; }}, 2000);
  }});
}}

document.getElementById('sql-modal').addEventListener('click', function(e) {{
  if (e.target === this) {{ closeSqlModal(); }}
}});
document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape') {{ closeSqlModal(); }}
}});

function filterAuditTable(filter) {{
  document.querySelectorAll('.at-filter-btn').forEach(function(btn) {{
    btn.classList.remove('active');
  }});
  document.querySelector('.at-filter-btn[data-filter="' + filter + '"]').classList.add('active');
  const rows = document.querySelectorAll('.audit-unit-table tbody tr');
  rows.forEach(function(row) {{
    if (filter === 'all' || row.getAttribute('data-filter') === filter) {{
      row.style.display = '';
    }} else {{
      row.style.display = 'none';
    }}
  }});
}}

function sortAuditTable(sortType) {{
  document.querySelectorAll('.at-sort-btn').forEach(function(btn) {{
    btn.classList.remove('active');
  }});
  document.querySelector('.at-sort-btn[data-sort="' + sortType + '"]').classList.add('active');
}}

function filterRules(severity) {{
  document.querySelectorAll('.filter-btn').forEach(function(btn) {{
    btn.classList.remove('active');
  }});
  document.querySelector('.filter-btn[data-filter="' + severity + '"]').classList.add('active');
  
  document.querySelectorAll('.rule-group').forEach(function(group) {{
    if (severity === 'all') {{
      group.classList.remove('hidden');
    }} else {{
      if (group.getAttribute('data-severity') === severity) {{
        group.classList.remove('hidden');
      }} else {{
        group.classList.add('hidden');
      }}
    }}
  }});
}}

function searchRules() {{
  const query = document.getElementById('rules-search').value.toLowerCase();
  document.querySelectorAll('.rule-item').forEach(function(item) {{
    const code = item.getAttribute('data-code').toLowerCase();
    item.style.display = code.includes(query) ? '' : 'none';
  }});
}}

function toggleRuleGroup(header) {{
  const group = header.closest('.rule-group');
  group.classList.toggle('collapsed');
}}
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
const costLabels = """
        f"{list(cost_buckets.keys())}"
        """;
const costValues = """
        f"{list(cost_buckets.values())}"
        """;
drawHorizontalBar('costChart', costValues, costLabels, '#6366f1');
const timeData = """
        f"{[(b.sql_unit_id[:20], b.actual_time_ms or 0) for b in sorted(baselines, key=lambda x: x.actual_time_ms or 0, reverse=True)[:10]]}"
        """;
drawHorizontalBar('timeChart', timeData.map(d => d[1]), timeData.map(d => d[0]), '#f59e0b');
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
const confLabels = """
        f"{list(conf_buckets.keys())}"
        """;
const confValues = """
        f"{list(conf_buckets.values())}"
        """;
drawHorizontalBar('confChart', confValues, confLabels, '#22c55e');
const gainData = """
        f"{[(p.sql_unit_id[:15], p.gain_ratio or 0) for p in sorted(proposals, key=lambda x: x.gain_ratio or 0, reverse=True)[:10]]}"
        """;
drawHorizontalBar('gainChart', gainData.map(d => d[1]), gainData.map(d => d[0]), '#3b82f6');
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
