# 交付检查清单（当前版本）

## 1. 启动前
1. `contracts/*.schema.json` 已确认是公开契约
2. CLI 稳定面仍是：`run / status / resume / apply`
3. 默认运行目录仍是：`runs/<run_id>/`

## 2. 必测回归
1. 正常全流程到 `patch_generate`
2. `resume` 能从阶段失败后继续
3. schema 校验失败时快速失败
4. DB 不可达时 report 仍可生成
5. statement 多变体冲突时保守跳过
6. 至少一条 SQL `PASS` 并生成 patch
7. patch 通过 `git apply --check`
8. `scan.fragments.jsonl` 可生成且通过 schema 校验
9. `<include><property .../></include>` 的 binding 信息被正确记录
10. 架构守卫测试通过：
   - `tests/test_architecture_boundaries.py`
   - `tests/test_contract_model_interfaces.py`

## 3. 模板感知专项回归
1. 默认配置下：
   - fragment catalog 生成能力生效（`scan.fragments.jsonl` 存在）
   - fragment 自动物化保持关闭（无显式自动落地）
2. statement-level include-safe 模板 patch 仍要求 `replayVerified=true`
3. fragment 自动物化默认不会误触发
4. 动态 statement 仍不会被扁平 SQL 直接覆盖
5. report 仍能重生，不复用旧报告

## 4. 发布前验收
1. 所有核心产物存在且结构合法
2. `report.json` 与 `ops/*.json` 通过 schema 校验
3. `ops/failures.jsonl` 与 `report.stats` 含 `fatal / retryable / degradable` 统计
4. 至少一份真实项目运行样例可复现
5. 文档描述与当前默认行为一致
6. CI 中显式 `Architecture guards` 步骤已通过
7. 显式 `to_stage=report` 重建后：
   - `report.json.stats` 不重复累计
   - `supervisor/results/report.jsonl` 不重复追加 `DONE`

## 5. 离线 Smoke Run（推荐）
1. 将 `tests/fixtures/project` 复制到临时目录，避免污染仓库内 fixture
2. 在临时项目中覆盖一份离线安全配置：
   - `llm.enabled=false`
   - `llm.provider=heuristic`
3. 执行 `run --to-stage patch_generate`，随后循环执行 `status/resume` 直到 `complete=true`
4. 验证以下文件存在且内容一致：
   - `supervisor/state.json`
   - `supervisor/meta.json`
   - `report.json`
   - `report.summary.md`
5. 重点检查：
   - `state.phase_status.report == DONE`
   - `report.json.stats.pipeline_coverage.report == DONE`
   - `report.summary.md` 显示 `report DONE`
6. 发布前优先执行统一验收入口：
   - `python3 scripts/ci/release_acceptance.py`
7. 如需单独排查，可分别执行：
   - `python3 scripts/ci/opencode_smoke_acceptance.py`
   - `python3 scripts/ci/degraded_runtime_acceptance.py`
   - `python3 scripts/ci/report_rebuild_acceptance.py`
