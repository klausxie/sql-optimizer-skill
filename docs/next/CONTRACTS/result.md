# 阶段 5 契约

## 目标实体

- `PrioritizedFinding`
- `GlobalReport`
- `NamespaceReport`
- `PatchArtifact`

## `PrioritizedFinding`

```json
{
  "rank": 1,
  "finding_id": "finding_a1b2c3",
  "statement_key": "com.foo.user.UserMapper.search",
  "path_id": "branch_000127",
  "case_id": "case_hot_value_001",
  "severity": "high",
  "impact_score": 91.4,
  "best_proposal_id": "proposal_x1y2z3",
  "recommendation_level": "strong"
}
```

## `GlobalReport`

```json
{
  "summary": {
    "statements_scanned": 1200,
    "branches_generated": 8400,
    "explain_executed": 12000,
    "execution_baselines": 2400,
    "verified_slow_sql": 320,
    "high_risk_candidates": 180
  },
  "top_findings": [
    {
      "rank": 1,
      "finding_id": "finding_a1b2c3",
      "statement_key": "com.foo.user.UserMapper.search"
    }
  ]
}
```

## `NamespaceReport`

```json
{
  "namespace": "com.foo.user.UserMapper",
  "verified_slow_sql": 12,
  "recommended_actions": 7,
  "findings": [
    "finding_a1b2c3"
  ]
}
```

## `PatchArtifact`

```json
{
  "statement_key": "com.foo.user.UserMapper.search",
  "mapper_file": "UserMapper.xml",
  "proposal_id": "proposal_x1y2z3",
  "original_xml": "<select id=\"search\">...</select>",
  "patched_xml": "<select id=\"search\">...</select>",
  "diff": "--- original\n+++ optimized\n..."
}
```

## 存储布局

```text
result/
├── manifest.json
├── _index.json
├── ranking/
│   └── top_ranked.json
├── reports/
│   ├── report.json
│   └── by_namespace/{namespace}.json
├── patches/
│   ├── _index.json
│   └── by_namespace/{namespace}/{statement_id}.json
└── SUMMARY.md
```
