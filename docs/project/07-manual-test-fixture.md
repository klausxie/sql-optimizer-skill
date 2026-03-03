# Fixture 项目手工测试指南

本文档说明如何在本地手工跑通 `tests/fixtures/project`，并查看每个阶段输出。

## 1. 约定与前提

- 测试项目固定路径：`tests/fixtures/project`
- 配置文件固定：`tests/fixtures/project/sqlopt.yml`
- scan-only 配置：`tests/fixtures/project/sqlopt.scan.local.yml`
- run 数据目录固定：`tests/fixtures/project/runs/<run_id>`
- 以下命令都在仓库根目录执行：`/Users/klaus/Desktop/sql-optimizer`

前提环境：

1. Python 3 可用。
2. 本地 PostgreSQL 可连通（以 `sqlopt.yml` 里的 `db.dsn` 为准）。
3. 若启用在线 LLM：
   - `llm.provider=opencode_run`：`opencode` 命令可用；
   - `llm.provider=direct_openai_compatible`：`api_base/api_key/api_model` 可用且网络可达。
4. Java scanner jar 已存在：`java/scan-agent/target/scan-agent-1.0.0.jar`。

## 2. 快速自检（建议每次先做）

### 2.1 数据库连通性

```bash
psql "postgresql://postgres:Aa28012801@127.0.0.1:5432/postgres?sslmode=disable" -c "select 1;"
```

预期：返回 `1`。

### 2.2 LLM 连通性

当 `llm.provider=opencode_run`：

```bash
opencode run --format json --variant minimal "ping"
```

预期：输出事件里有 `"text":"pong"`。

如果这里失败，不要继续跑 pipeline，先修复 opencode 配置。

当 `llm.provider=direct_openai_compatible`：
1. 先确认 `sqlopt.yml` 中 `api_base/api_key/api_model` 已配置。
2. 直接执行 preflight（见 3.1）验证连通性。

## 3. 启动一次手工 run

## 3.1 运行命令

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run \
  --config tests/fixtures/project/sqlopt.yml \
  --run-id run_manual_$(date +%Y%m%d_%H%M%S)
```

预期：返回类似：

```text
{'run_id': 'run_manual_20260226_213000', 'result': {'complete': False, 'phase': 'scan'}}
```

记录返回的 `run_id`，后续都用它。

## 3.2 查看状态

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py status --run-id <run_id>
```

关键信息：

- `current_phase`
- `phase_status`
- `last_reason_code`
- `next_action`

`next_action` 判定：

- `resume`：继续推进未完成阶段
- `report-rebuild`：主流程已完成，只需执行 `run --to-stage report --run-id <run_id>`
- `none`：当前目标阶段已完成，无需继续

## 3.3 持续推进到完成

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py resume --run-id <run_id>
```

如未完成，重复执行 `resume` + `status`，直到 `complete: True`。

若 `status` 返回 `next_action: 'report-rebuild'`，改为执行：

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --config tests/fixtures/project/sqlopt.yml --to-stage report --run-id <run_id>
```

可用轮询命令：

```bash
for i in {1..60}; do
  PYTHONPATH=python python3 scripts/sqlopt_cli.py resume --run-id <run_id> >/tmp/sqlopt_resume.out
  PYTHONPATH=python python3 scripts/sqlopt_cli.py status --run-id <run_id>
  sleep 1
done
```

## 3.4 只验证 scan 覆盖（推荐用于 scanner 相关改动）

当你只修改了 scanner / scan verification，不需要把整条 pipeline 跑完时，优先执行：

```bash
python3 scripts/run_until_budget.py \
  --config tests/fixtures/project/sqlopt.scan.local.yml \
  --to-stage scan \
  --max-steps 10 \
  --max-seconds 30
```

这份配置只扫描：

- `tests/fixtures/project/scan_samples/dynamic_tags_mapper.xml`

当前样例覆盖：

- `bind`
- `choose/when/otherwise`
- `where`
- `if`
- `foreach`
- `include`
- `trim`
- `set`

建议至少检查：

1. `scan.sqlunits.jsonl`
   - `searchUsersAdvanced.dynamicFeatures` 含 `FOREACH/INCLUDE/IF/CHOOSE/WHERE/BIND`
   - `patchUserStatusAdvanced.sql` 不含重复 `SET SET`
2. `scan.fragments.jsonl`
   - `ActiveOnly` / `TenantGuard` 两个 fragment 都存在
3. `verification/ledger.jsonl`
   - 两条 statement 都是 `SCAN_EVIDENCE_VERIFIED`

## 4. 查看输出结果

run 目录：

```text
tests/fixtures/project/runs/<run_id>/
```

核心文件：

1. `manifest.jsonl`：阶段事件、失败原因。
2. `proposals/optimization.proposals.jsonl`：优化候选。
3. `acceptance/acceptance.results.jsonl`：validate 结论。
4. `patches/patch.results.jsonl`：补丁生成与 apply-check 结果。
5. `report.json`：汇总统计。

常用查看命令：

```bash
tail -n 50 tests/fixtures/project/runs/<run_id>/manifest.jsonl
cat tests/fixtures/project/runs/<run_id>/report.json
cat tests/fixtures/project/runs/<run_id>/acceptance/acceptance.results.jsonl
cat tests/fixtures/project/runs/<run_id>/patches/patch.results.jsonl
```

## 5. 手工应用 patch（可选）

当 patch 阶段完成后，可执行：

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py apply --run-id <run_id>
```

注意：当前默认 `apply.mode: PATCH_ONLY`，主要用于产出 patch 文件与可应用性检查。

## 6. 常见问题排查

## 6.1 `RUNTIME_RETRY_EXHAUSTED` + `Was there a typo in the url or port?`

这通常是 `opencode` 调用的模型端点不可达。

排查顺序：

1. 先跑 `opencode run --format json --variant minimal "ping"`。
2. 检查 `~/.opencode/opencode.json` 的 `provider/options/baseURL/apiKey/model`。
3. 如果网络不稳定，可在 `sqlopt.yml` 调高：
   - `llm.timeout_ms`
   - `runtime.stage_retry_max.optimize`
   - `runtime.stage_retry_backoff_ms`
4. 当前策略为 LLM 严格模式：`opencode_run` 或 `direct_openai_compatible` 不可达都直接失败，不做降级。

## 6.2 数据库未连通

表现：validate 阶段出现 `VALIDATE_DB_UNREACHABLE` 相关结果。

检查：

1. `db.dsn` 是否正确。
2. PostgreSQL 是否启动、端口是否监听。
3. 用户权限是否能执行 `EXPLAIN` / 查询目标表。

## 6.3 patch 文件无法 apply

检查 `patches/patch.results.jsonl`：

- `applicable: false` 表示 `git apply --check` 未通过。
- `applyCheckError` 会给出具体冲突/上下文不匹配原因。

## 7. 推荐的最小回归用例

每次改动后至少做一次：

1. `run` + 多次 `resume` 到 `complete: True`。
2. 确认 `report.json` 存在且可解析。
3. 确认 `patch.results.jsonl` 中至少有一条 `applicable: true`（针对可 patch SQL）。
4. 抽查 `acceptance.results.jsonl` 中 `selectedCandidateSource/selectedCandidateId/warnings/riskFlags` 字段。
