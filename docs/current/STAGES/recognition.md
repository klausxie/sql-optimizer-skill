# Recognition Stage

## Purpose

Recognition 阶段为每个 SQL 分支生成**性能基准数据**（EXPLAIN 执行计划、预估成本、实际执行时间、结果签名），为后续 Optimize 阶段提供优化前后的对比依据。

通俗理解：**拿着 Parse 阶段展开的 SQL，问数据库"这条 SQL 跑起来性能如何？"**，把答案记录下来。

---

## Inputs

| File | 内容 |
|------|------|
| `parse/sql_units_with_branches.json` 或 `parse/units/*.json` | Parse 阶段输出的分支 SQL |
| `init/table_schemas.json` | 表元数据（用于参数替换和类型推断） |

### 执行模式依赖

| 模式 | 需要的配置 | 行为 |
|------|-----------|------|
| **Mock 模式**（默认） | 无需数据库 | LLM Provider 生成模拟 EXPLAIN 数据 |
| **LLM 模式** | `llm_provider=opencode_run` 等 | 调用 LLM 生成 EXPLAIN 模拟数据 |
| **DB 模式** | 完整的 `db_host/port/name/user/password` | 实际连接数据库执行 `EXPLAIN` 和查询 |

---

## Process

### 1. 加载 Parse 输出

Recognition 支持两种输入格式：

- **Per-Unit 文件**（推荐）：`parse/units/{unit_id}.json` + `parse/units/_index.json`
- **兼容性文件**（冗余堆积）：`parse/sql_units_with_branches.json`

按 `sql_unit_id` + `path_id` 遍历每个分支。

### 2. 参数替换（MyBatis → 真实 SQL）

数据库的 `EXPLAIN` 需要真实的参数值，不能带 `#{}` 占位符。`_resolve_mybatis_params_for_explain` 负责替换：

```
WHERE status = #{status}  →  WHERE status = 1
WHERE name LIKE #{name}   →  WHERE name LIKE 'test'
```

**替换规则**（按优先级）：

| 参数名关键词 | 推断类型 | 替换值 |
|------------|----------|--------|
| `id`, `num`, `count`, `page`, `size`, `limit`, `offset` | INT | `1` |
| `status`, `type`, `mode`, `state` | INT | `1` |
| `name`, `email`, `title`, `desc`, `keyword` | VARCHAR | `'test'` |
| `date`, `time`, `start`, `end` | DATE/TIMESTAMP | `'2024-01-01'` |
| 其他 | 未知 | `1` |

当 `table_schemas.json` 可用时，会根据**列的实际类型**选择更准确的替换值（INT → `1`，DATE → `'2024-01-01'` 等）。

### 3. EXPLAIN 执行计划获取

对每个有效分支执行以下逻辑：

```
1. branch_type == "baseline_only" → 跳过 EXPLAIN，记录 cost=0
2. 有 DB Connector → db_connector.execute_explain(sql)
   └── 返回 plan, estimated_cost, actual_time_ms
3. 无 DB Connector → llm_provider.generate_baseline(sql)
   └── LLM 模拟生成 plan 和 cost 数据
```

**DB 模式支持的平台**：PostgreSQL（主要）、MySQL（`EXPLAIN FORMAT=JSON`）

**LLM Mock 模式**：当 `llm_provider=mock` 或无数据库时使用，根据 SQL 文本heuristic 生成模拟的 EXPLAIN 结果。

### 4. 实际查询执行（仅 DB 模式 + SELECT）

如果同时满足：
- 有 DB Connector **且**
- SQL 是只读 SELECT 语句（`EXPLAIN` 只看计划，不执行）

则额外执行实际查询，记录：
- `actual_time_ms`：查询耗时（毫秒）
- `rows_returned`：返回行数
- `result_signature`：结果集的 SHA256 校验和（前 20 行采样）

### 5. 指标提取

从 EXPLAIN plan 中提取：

| 指标 | 来源 | 说明 |
|------|------|------|
| `estimated_cost` | PostgreSQL `Total Cost` 或 MySQL `query_cost` |  planner 估算的相对成本 |
| `actual_time_ms` | PostgreSQL `Actual Total Time` | 实际执行时间（DB 模式） |
| `rows_examined` | 递归遍历 plan 树中所有 `Actual Rows` / `Plan Rows` | 估算扫描行数 |

### 6. 错误处理

EXPLAIN 或查询执行失败的分支仍会保留记录：

```
execution_error = "baseline_generation_failed: {具体异常}"
execution_error = "query_execution_failed: {具体异常}"
```

阶段**不中断**，继续处理其他分支。

---

## Execution Modes

### 并发执行（Mock / LLM 模式）

```
config.concurrency.enabled = true  且  无 DB Connector
```

- 使用 `ConcurrentExecutor` 并发处理分支
- `max_workers` 控制并发数（默认 4）
- 每个 task 独立调用 LLM Provider，互不干扰

### 顺序执行（DB 模式）

```
有 DB Connector  且  config.concurrency.enabled = true
```

**强制切换为顺序执行**，因为：
1. 数据库连接不适合高并发共享
2. EXPLAIN + 实际查询是长时操作，并发可能导致连接池耗尽

### Stub 模式（无 run_id）

无 `run_id` 时返回硬编码的 stub baseline，不读写任何文件。

---

## Outputs

### Per-Unit 文件（主存储）

```
runs/{run_id}/recognition/units/{unit_id}.json
runs/{run_id}/recognition/units/_index.json
```

### 兼容性文件（冗余堆积，建议移除）

```
runs/{run_id}/recognition/baselines.json
```

### `PerformanceBaseline` 字段说明

| 字段 | 含义 |
|------|------|
| `sql_unit_id` | SQL Unit 标识 |
| `path_id` | 分支标识（如 `branch_0`） |
| `original_sql` | 替换参数后的可执行 SQL |
| `plan` | EXPLAIN 执行计划（字典结构，不同数据库格式不同） |
| `estimated_cost` | planner 估算成本（相对值，PostgreSQL 特有） |
| `actual_time_ms` | 实际执行时间（毫秒），仅 DB 模式有值 |
| `rows_returned` | 返回行数，仅 DB 模式 SELECT 查询有值 |
| `rows_examined` | 估算扫描行数，从 plan 树提取 |
| `result_signature` | 结果集校验和 `{row_count, sample_size, columns, checksum}` |
| `execution_error` | 执行异常信息，为 `None` 表示成功 |
| `branch_type` | 分支类型（从 Parse 阶段传递） |

---

## Risks（潜在问题）

### 高风险

| 问题 | 描述 | 后果 |
|------|------|------|
| **`#{ } 参数推断错误** | 参数替换基于变量名猜测，不一定匹配业务含义 | 生成的 SQL 可能索引失效，产生错误的 cost 评估 |
| **Mock/LLM 数据不可信** | 无 DB 时的 estimated_cost 是模拟数据 | 可能与实际执行计划差异巨大 |
| **DB 连接耗尽** | 并发模式下 DB Connector 被多线程共享 | 顺序执行是正确Safety 开关，不是性能问题 |
| **`${ } 原样保留** | Parse 阶段未处理的 `${}` 直接透传到 EXPLAIN | 注入风险，SQL 执行报错 |

### 中风险

| 问题 | 描述 | 后果 |
|------|------|------|
| **非 SELECT SQL 也执行** | 系统仅用 `sql_upper.startswith("SELECT")` 判断 | INSERT/UPDATE/DELETE 可能被识别为只读（误判） |
| **`actual_time_ms` 反映测试数据** | EXPLAIN 的 sample 值与生产数据分布不同 | 实际执行时间可能与评估差异大 |
| **`rows_examined` 提取不完整** | 只取 plan 树中最大值，可能遗漏子节点 | 低估扫描行数 |
| **并发 LLM 调用超时** | `timeout_per_task=120s`，超时不重试 | 部分分支丢失 baseline |

### 低风险

| 问题 | 描述 | 后果 |
|------|------|------|
| **无 `table_schemas.json`** | 无法做列类型推断，退化为启发式替换 | 参数替换精度下降 |
| **`result_signature` 仅采样 20 行** | 大结果集只取前 20 行做校验和 | 少量行差异可能未检出 |
| **PostgreSQL / MySQL plan 格式差异** | `_estimate_cost_from_plan` 需要兼容两种格式 | 某些边缘 plan 结构可能 cost 提取失败 |

---

## 与 Parse / Optimize 的关系

```
Parse 阶段                          Recognition 阶段                     Optimize 阶段
──────────────────────────────────  ───────────────────────────────────  ──────────────────────────────────
输入: XML SQL                       输入: 分支 SQL + 表结构              输入: Baseline 数据
处理: 动态标签展开 + 风险评分       处理: EXPLAIN + 参数替换 + 执行      处理: LLM 生成优化 SQL + 验证
输出: 每个分支的展开 SQL             输出: 每个分支的性能基准              输出: 优化建议 + 对比数据
                              ──────────────────────────────────────▶
                              Parse output.optimize_input →  Optimize 拿 baseline 比对优化效果
```

Recognition 的核心价值：**建立 Optimize 前的性能基准**，使优化后可以量化改进幅度（cost 降低 X%，执行时间减少 Yms）。

---

## 相关文件

- 核心实现：`python/sqlopt/stages/recognition/stage.py`
- 契约定义：`python/sqlopt/contracts/recognition.py`
- DB 连接器：`python/sqlopt/common/db_connector.py`
- LLM Provider：`python/sqlopt/common/llm_mock_generator.py`
