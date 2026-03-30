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
3. `status.complete=true` 是"已达到目标阶段"的判断依据。
4. 分步执行是为了保证每个步骤可控可追踪，支持中断恢复。
5. `report` 是唯一允许重生（regenerate）的阶段；其余已完成阶段默认跳过，不重复执行。

## 3. 监督状态文件（Supervisor）
运行时必须维护：
1. `runs/<run-id>/pipeline/supervisor/meta.json`
2. `runs/<run-id>/pipeline/supervisor/plan.json`
3. `runs/<run-id>/pipeline/supervisor/state.json`
4. `runs/<run-id>/pipeline/supervisor/results/*.jsonl`

要求：
1. `plan` 固化 statement 列表与顺序。
2. `state` 记录每个 statement 在每个 phase 的状态、重试、错误摘要。
3. `results` 记录每一步的结构化结果（`scan/optimize/validate/patch_generate/report`），供 `status/diagnose/report` 消费，且与 `pipeline/manifest.jsonl` 事件可交叉追踪。
4. `state.report_rebuild_required=true` 表示主流程已完成，但 `report` 派生产物需要重建。

## 4. Phase 状态约定
每个 phase 至少支持：
1. `PENDING`
2. `DONE`
3. `FAILED`
4. `SKIPPED`

运行级状态：
1. `RUNNING`
2. `READY_TO_FINALIZE`
3. `COMPLETED`

## 5. 失败与恢复策略
1. 失败分类：`fatal | retryable | degradable`。
2. retry 策略：由内置运行时策略控制（不再通过外部 `sqlopt.yml` 暴露）。
3. 可恢复原则：已完成 statement 不重复执行；失败 statement 可定点重试。
4. DB 不可达属于高风险事件，需在报告和 ops 健康中显式统计。
5. 若已完成 run 的 `report` 重建失败，运行级状态保持 `COMPLETED`，但 `report_rebuild_required=true`，提示后续仅重建 report。

## 6. 完成判定
1. 当 `to_stage` 无 pending statement，`complete=true`。
2. 若 report 开启（默认），运行结束时会触发 report finalization（即使 `to_stage` 早于 `report`）。
3. `apply` 不改变 analyze/validate/patch_generate 的完成定义，只增加应用态产物。
4. `status.next_action` 语义固定为：
   - `resume`：继续推进主流程
   - `report-rebuild`：只需重建 report 派生产物
   - `none`：当前目标阶段已完成
