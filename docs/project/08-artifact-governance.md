# 运行产物治理（Artifacts Governance）

本项目的运行产物以 `runs/<run-id>/` 为中心。为了避免后续演进中出现语义漂移、重复 source-of-truth 或历史 run 不可比较的问题，所有产物按以下规则治理。

## 1. 基本原则

1. `pipeline/supervisor/state.json` 是运行时阶段状态的唯一 source of truth。
2. `overview/report.json`、`overview/report.md`、`overview/report.summary.md` 都是派生产物，必须由当前运行态和阶段产物重建，不得手工编辑修正。
3. `pipeline/ops/*.json` 是诊断与运维派生产物，语义应与 `overview/report.json` 一致，不能单独演化出另一套状态定义。
4. 新增字段默认只能做加法兼容；如果会改变既有字段语义，必须先升级契约并明确迁移策略。

## 2. 产物分类

### A. 稳定契约（Stable Contract）

这些文件可被外部工具、发布流程或验收逻辑稳定依赖：

- `pipeline/supervisor/meta.json`
- `pipeline/supervisor/state.json`
- `pipeline/supervisor/plan.json`
- `overview/config.resolved.json`
- `overview/report.json`
- `pipeline/ops/topology.json`
- `pipeline/ops/health.json`
- `pipeline/ops/failures.jsonl`

规则：

1. 只能做加法兼容修改。
2. 变更前必须补回归测试和至少一个真实验收断言。
3. 不允许“同名字段换语义”。

### B. 阶段结果索引（Step Result Ledger）

这些文件记录阶段执行结果，是运行恢复和排障的主要索引：

- `pipeline/supervisor/results/preflight.jsonl`
- `pipeline/supervisor/results/diagnose.jsonl`
- `pipeline/supervisor/results/optimize.jsonl`
- `pipeline/supervisor/results/validate.jsonl`
- `pipeline/supervisor/results/apply.jsonl`
- `pipeline/supervisor/results/report.jsonl`

规则：

1. 行为必须追加式，避免覆盖历史执行记录。
2. 允许在 detail 字段中增加调试信息，但不应移除现有稳定字段。
3. 新增阶段时必须同步更新状态机与 report 聚合逻辑。

### C. 可重算阶段产物（Recomputable Artifacts）

这些文件是阶段执行的直接输出，可在同一输入下重新生成：

- `pipeline/diagnose/sqlunits.jsonl`
- `pipeline/diagnose/fragments.jsonl`
- `pipeline/optimize/optimization.proposals.jsonl`
- `pipeline/validate/acceptance.results.jsonl`
- `pipeline/apply/patch.results.jsonl`

规则：

1. 允许删除后重算。
2. 若结构变化影响 `report` 或 `resume`，必须同步更新所有读取方到新路径。
3. 不能被当作唯一运行状态来源。

### D. 展示层派生产物（Presentation-Only Derivatives）

这些文件用于人类阅读，不应反向驱动运行状态：

- `overview/report.md`
- `overview/report.summary.md`

规则：

1. 允许渲染样式演进。
2. 不得作为状态恢复依据。
3. 内容必须由 `overview/report.json` 和当前输入推导生成。

## 3. Source Of Truth Mapping

明确职责如下：

1. 运行是否完成：看 `pipeline/supervisor/state.json` + `pipeline/supervisor/meta.json`
2. 运行时解析配置：看 `overview/config.resolved.json`（由 `sqlopt.yml` 推导生成）
3. 阶段执行历史：看 `pipeline/supervisor/results/*.jsonl`
4. 外部汇总结论：看 `overview/report.json`
5. 运维诊断：看 `pipeline/ops/*.json`
6. 人类阅读摘要：看 `overview/report.summary.md` / `overview/report.md`

任何新逻辑如果需要“当前 phase 状态”，必须先读 `pipeline/supervisor/state.json`，而不是从 report 或 markdown 反推。

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

1. 不做历史 run 的自动迁移；读取逻辑仅支持 canonical 目录结构。
2. 对稳定契约默认使用“向后兼容加字段”策略。
3. 对展示层产物允许重生，不复用旧渲染结果。
