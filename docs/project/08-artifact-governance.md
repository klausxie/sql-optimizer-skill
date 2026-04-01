# 运行产物治理（Artifacts Governance）

本项目的运行产物以 `runs/<run-id>/` 为中心。为了避免语义漂移、重复 source-of-truth 或历史 run 不可比较的问题，所有产物按以下规则治理。

## 1. 基本原则

1. `control/state.json` 是运行时阶段状态的唯一 source of truth。
2. `control/plan.json` 是固定输入计划与 resolved config 的唯一持久入口。
3. `control/manifest.jsonl` 是执行历史的唯一追加式账本。
4. `report.json` 是极简派生摘要，不得反向驱动恢复逻辑。
5. `artifacts/*.jsonl` 是阶段直接输出，可删除后重算。
6. `sql/catalog.jsonl` 与 `sql/<sql-key>/index.json` 是按 SQL 的导航索引，不定义运行状态。

## 2. 产物分类

### A. 稳定契约（Stable Contract）

这些文件可被外部工具、发布流程或验收逻辑稳定依赖：

- `control/state.json`
- `control/plan.json`
- `control/manifest.jsonl`
- `report.json`
- `sql/catalog.jsonl`
- `sql/<sql-key>/index.json`

规则：

1. 只能做加法兼容修改。
2. 变更前必须补回归测试和至少一个真实验收断言。
3. 不允许“同名字段换语义”。

### B. 可重算阶段产物（Recomputable Artifacts）

这些文件是阶段执行的直接输出，可在同一输入下重新生成：

- `artifacts/scan.jsonl`
- `artifacts/fragments.jsonl`
- `artifacts/proposals.jsonl`
- `artifacts/acceptance.jsonl`
- `artifacts/patches.jsonl`

规则：

1. 允许删除后重算。
2. 若结构变化影响 `report`、`resume` 或 `apply`，必须同步更新所有读取方。
3. 不能被当作唯一运行状态来源。

### C. SQL 下钻索引（SQL Drilldown）

这些文件用于按 SQL 下钻证据：

- `sql/catalog.jsonl`
- `sql/<sql-key>/index.json`
- `sql/<sql-key>/trace.optimize.llm.json`
- `sql/<sql-key>/candidate_generation_diagnostics.json`
- `sql/<sql-key>/evidence/*`

规则：

1. 允许扩展导航字段，但不能重新定义运行状态。
2. 路径引用必须指向当前 canonical layout。
3. `verification` 不再引用独立 ledger 文件，而是依赖阶段产物中的嵌入记录。

## 3. Source Of Truth Mapping

明确职责如下：

1. 运行是否完成：看 `control/state.json`
2. 运行时解析配置：看 `control/plan.json`
3. 阶段执行历史：看 `control/manifest.jsonl`
4. 外部汇总结论：看 `report.json`
5. 阶段直接事实：看 `artifacts/*.jsonl`
6. 单条 SQL 的证据导航：看 `sql/catalog.jsonl` 与 `sql/<sql-key>/index.json`

任何新逻辑如果需要“当前 phase 状态”，必须先读 `control/state.json`，而不是从 report 或 SQL 索引反推。

## 4. 变更要求

当新增或修改 artifacts 时，至少要同时完成：

1. 说明它属于哪一类产物
2. 说明它的 source of truth 是什么
3. 说明它是否允许删除后重算
4. 增加对应的单元测试或验收断言

## 5. 序列化边界

为避免内部模型和外部契约重新耦合，默认遵循以下规则：

1. `models` 层负责定义内部文档对象。
2. 对外 JSON 契约统一通过 `to_contract()` 导出。
3. `builder / policy / selection` 可以组装模型，但不应在中途手工拼接稳定契约 payload。
4. `writer / stage` 出口层负责最终持久化和 schema 校验。
5. 不再引入 `as_dict()`、`*_payload()` 等并行序列化命名。

## 6. 当前默认策略

1. 不做历史 run 的自动迁移；读取逻辑仅支持当前 canonical 目录结构。
2. 对稳定契约默认使用“向后兼容加字段”策略。
3. `report.json` 保持极简摘要，不再承载大列表或 ops/diagnostics 细节。
4. 展示层 Markdown 报告已移除，不复用旧渲染结果。
