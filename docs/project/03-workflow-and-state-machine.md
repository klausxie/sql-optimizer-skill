# 流程与状态机规格

## 1. 命令模型
统一入口：`python <SQL_OPT_ROOT>/scripts/sqlopt_cli.py`

子命令：
1. `run`：从目标阶段范围开始推进。
2. `status`：查看当前 run 的阶段状态与剩余工作。
3. `resume`：在同一 `run_id` 上继续推进。
4. `apply`：执行补丁应用动作（默认 patch-only 语义）。

默认阶段目标：
- 不指定 `stage` 时，目标为 `patch_generate`。

## 2. 执行语义
1. 阶段顺序固定：`preflight -> scan -> optimize -> validate -> patch_generate -> report`。
2. `run/resume` 每次调用最多推进一个 statement step（受 `max_step_ms` 预算约束）。
3. `status.complete=true` 是“已达到目标阶段”的判断依据。
4. 为什么一个个 statement step循环推进？因为opencode执行命令时最大超时 120s。若所有sql集中优化，正常项目多sql情况下很容易超过 120s。

## 3. 监督状态文件（Supervisor）
运行时必须维护：
1. `runs/<run_id>/supervisor/meta.json`
2. `runs/<run_id>/supervisor/plan.json`
3. `runs/<run_id>/supervisor/state.json`
4. `runs/<run_id>/supervisor/results/*.jsonl`

要求：
1. `plan` 固化 statement 列表与顺序。
2. `state` 记录每个 statement 在每个 phase 的状态、重试、错误摘要。
3. `results` 记录每一步的结构化结果（`scan/optimize/validate/patch_generate/report`），供 `status/diagnose/report` 消费，且与 `manifest.jsonl` 事件可交叉追踪。

## 4. Phase 状态约定
每个 phase 至少支持：
1. `PENDING`
2. `DONE`
3. `FAILED`

运行级状态：
1. `RUNNING`
2. `READY_TO_FINALIZE`
3. `COMPLETED`

## 5. 失败与恢复策略
1. 失败分类：`fatal | retryable | degradable`。
2. retry 策略：由 `runtime.stage_retry_*` 控制。
3. 可恢复原则：已完成 statement 不重复执行；失败 statement 可定点重试。
4. DB 不可达属于高风险事件，需在报告和 ops 健康中显式统计。

## 6. 完成判定
1. 当 `to_stage` 无 pending statement，`complete=true`。
2. 若 `report.enabled=true`（默认），运行结束时会触发 report finalization（即使 `to_stage` 早于 `report`）。
3. `apply` 不改变 analyze/validate/patch_generate 的完成定义，只增加应用态产物。
