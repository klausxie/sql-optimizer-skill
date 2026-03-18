# 功能需求基线（面向重构）

## 1. 产品目标
构建一个面向 MyBatis XML 的 SQL 优化系统，支持从扫描、分析、验证到补丁生成与应用的完整闭环，且全过程可审计、可恢复、可复现。

目标人群：
- 后端开发者（Java/MyBatis 项目维护者）
- DBA/性能治理工程师
- 接手本系统的 Agent/平台开发者

## 2. V1 必须交付能力
1. 初始化运行上下文，生成 `run_id` 和 `runs/<run-id>/`。
2. 扫描 mapper SQL，产出标准化 `SqlUnit` 列表。
3. 对 SQL 生成 `OptimizationProposal`（问题、证据、建议、结论）。
4. 对候选改写做验收，产出 `AcceptanceResult`。
5. 生成 patch/diff，产出 `PatchResult`，默认不直接改项目文件。
6. 支持人工触发应用补丁（`apply` 命令）。
7. 生成 Markdown + JSON 报告（`RunReport`）与 ops 健康产物。
8. 支持 `run/status/resume` 的可恢复执行。

## 3. 非目标（V1 不做）
1. 不做 CI 自动触发、自动建 PR、自动合并。
2. 不默认在生产环境执行 `EXPLAIN ANALYZE`。
3. 不承诺 100% 自动改写成功；允许 `NEED_MORE_PARAMS`。

## 4. 成功标准（DoD）
1. 任意一次运行都有完整产物目录和清晰失败定位。
2. 所有阶段结构化输出符合 `contracts/*.schema.json`。
3. 运行可中断后继续，直到目标阶段完成。
4. 报告能回答：做了什么、成功多少、失败在哪、下一步是什么。

## 5. 关键质量属性
1. 可审计：`pipeline/manifest.jsonl` 和阶段产物可追踪。
2. 可恢复：基于 `run_id` 恢复进度，无需重跑全部步骤。
3. 安全性：对 `${}` 风险有显式识别与记录。
4. 兼容性：契约变更必须可控，优先向后兼容。

