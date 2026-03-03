# 运行产物治理（Artifacts Governance）

本项目的运行产物以 `runs/<run_id>/` 为中心。为了避免后续演进中出现语义漂移、重复 source-of-truth 或历史 run 不可比较的问题，所有产物按以下规则治理。

## 1. 基本原则

1. `supervisor/state.json` 是运行时阶段状态的唯一 source of truth。
2. `report.json`、`report.md`、`report.summary.md` 都是派生产物，必须由当前运行态和阶段产物重建，不得手工编辑修正。
3. `ops/*.json` 是诊断与运维派生产物，语义应与 `report.json` 一致，不能单独演化出另一套状态定义。
4. 新增字段默认只能做加法兼容；如果会改变既有字段语义，必须先升级契约并明确迁移策略。

## 2. 产物分类

### A. 稳定契约（Stable Contract）

这些文件可被外部工具、发布流程或验收逻辑稳定依赖：

- `supervisor/meta.json`
- `supervisor/state.json`
- `supervisor/plan.json`
- `report.json`
- `ops/topology.json`
- `ops/health.json`
- `ops/failures.jsonl`

规则：

1. 只能做加法兼容修改。
2. 变更前必须补回归测试和至少一个真实验收断言。
3. 不允许“同名字段换语义”。

### B. 阶段结果索引（Step Result Ledger）

这些文件记录阶段执行结果，是运行恢复和排障的主要索引：

- `supervisor/results/preflight.jsonl`
- `supervisor/results/scan.jsonl`
- `supervisor/results/optimize.jsonl`
- `supervisor/results/validate.jsonl`
- `supervisor/results/patch_generate.jsonl`
- `supervisor/results/report.jsonl`

规则：

1. 行为必须追加式，避免覆盖历史执行记录。
2. 允许在 detail 字段中增加调试信息，但不应移除现有稳定字段。
3. 新增阶段时必须同步更新状态机与 report 聚合逻辑。

### C. 可重算阶段产物（Recomputable Artifacts）

这些文件是阶段执行的直接输出，可在同一输入下重新生成：

- `scan.sqlunits.jsonl`
- `scan.fragments.jsonl`
- `proposals/optimization.proposals.jsonl`
- `acceptance/acceptance.results.jsonl`
- `patches/patch.results.jsonl`

规则：

1. 允许删除后重算。
2. 若结构变化影响 `report` 或 `resume`，必须同步补迁移或兼容读取逻辑。
3. 不能被当作唯一运行状态来源。

### D. 展示层派生产物（Presentation-Only Derivatives）

这些文件用于人类阅读，不应反向驱动运行状态：

- `report.md`
- `report.summary.md`

规则：

1. 允许渲染样式演进。
2. 不得作为状态恢复依据。
3. 内容必须由 `report.json` 和当前输入推导生成。

## 3. Source Of Truth Mapping

明确职责如下：

1. 运行是否完成：看 `supervisor/state.json` + `supervisor/meta.json`
2. 阶段执行历史：看 `supervisor/results/*.jsonl`
3. 外部汇总结论：看 `report.json`
4. 运维诊断：看 `ops/*.json`
5. 人类阅读摘要：看 `report.summary.md` / `report.md`

任何新逻辑如果需要“当前 phase 状态”，必须先读 `supervisor/state.json`，而不是从 report 或 markdown 反推。

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

1. 不做历史 run 的自动迁移；旧 run 以“尽量兼容读取”为主。
2. 对稳定契约默认使用“向后兼容加字段”策略。
3. 对展示层产物允许重生，不复用旧渲染结果。
