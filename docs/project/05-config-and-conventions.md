# 配置与工程约定（当前默认）

## 1. 配置根键
允许的根键：
1. `project`
2. `scan`
3. `db`
4. `validate`
5. `policy`
6. `apply`
7. `diagnostics`
8. `runtime`
9. `llm`
10. `report`
11. `verification`

命名约束：
1. 全部使用 `snake_case`
2. 非 snake_case 视为配置错误

## 2. Profile 覆盖规则
1. `runtime.profile`：`fast | balanced | resilient`
2. `validate.validation_profile`：`strict | balanced | relaxed`
3. 应用顺序：先加载 profile 默认值，再叠加用户配置

### 2.1 Validate 策略默认值
默认：
1. `validate.selection_mode=patchability_first`
2. `validate.require_semantic_match=true`
3. `validate.require_perf_evidence_for_pass=false`
4. `validate.require_verified_evidence_for_pass=false`
5. `validate.delivery_bias=conservative`

当前约束：
1. 第一阶段只支持 `selection_mode=patchability_first`
2. 第一阶段只支持 `delivery_bias=conservative`
3. 这些字段当前主要用于固定决策口径与 `decisionLayers` 输出，不改变既有主流程命令形态

## 3. LLM Provider
`llm.provider` 当前支持：
1. `opencode_run`
2. `direct_openai_compatible`
3. `opencode_builtin`
4. `heuristic`

说明：
1. `opencode_run` 与 `direct_openai_compatible` 为严格失败语义
2. `provider=direct_openai_compatible` 时必须配置：
   - `llm.api_base`
   - `llm.api_key`
   - `llm.api_model`

## 3.1 数据库平台
`db.platform` 当前支持：
1. `postgresql`
2. `mysql`

边界：
1. MySQL 仅支持 8.0+
2. 不支持 MariaDB
3. `db.dsn` 的 MySQL 连接串格式固定为：`mysql://user:pass@host:3306/db`
4. 若要先做离线 smoke run，推荐：
   - `validate.db_reachable=false`
   - `validate.allow_db_unreachable_fallback=true`
5. 若 SQL 或候选含 MySQL 不支持的 PostgreSQL 方言（例如 `ILIKE`），当前不会做方言兼容转换，而是按 SQL 语法错误处理

## 4. Report 约定
默认：
1. `report.enabled=true`

当前行为：
1. 即使 `to_stage` 早于 `report`，只要 report 开启，运行结束时仍会收口 report
2. 若 later stage 产物更新，再次跑 `to_stage=report` 会重生 report，而不是复用旧报告

## 5. Template Rewrite 相关开关

### 5.1 `scan.enable_fragment_catalog`
默认：
1. `true`

行为影响：
1. 生成 `scan.fragments.jsonl`
2. 为 statement / fragment 记录源码 range locator
3. 记录 `<include><property>` 绑定信息

性质：
1. 低风险观测能力
2. 默认开启

### 5.2 `patch.template_rewrite.enable_fragment_materialization`
默认：
1. `false`

行为影响：
1. validate 仍会输出 `rewriteMaterialization`
2. 但默认不会把 fragment 级模板 rewrite 视为可自动应用 patch

性质：
1. 高风险行为开关
2. 默认关闭

## 6. 运行目录规范
统一路径：
1. `<project.root_path>/runs/<run_id>/`

核心产物：
1. `manifest.jsonl`
2. `scan.sqlunits.jsonl`
3. `scan.fragments.jsonl`（默认开启）
4. `proposals/optimization.proposals.jsonl`
5. `acceptance/acceptance.results.jsonl`
6. `patches/patch.results.jsonl`
7. `report.md`
8. `report.summary.md`
9. `report.json`
10. `ops/health.json`
11. `ops/topology.json`

## 7. 补丁与回滚约定
1. 默认 `apply.mode=PATCH_ONLY`
2. 每个 `PatchResult` 必须提供 `rollback`
3. in-place apply 只能显式触发，不能隐式执行
4. 生成的 patch 文件应可通过 `git apply --check`

## 8. 诊断与告警约定
1. 失败要在 `ops/failures.jsonl` 可追踪
2. DB 不可达、LLM 超时、schema 校验失败必须有结构化统计
3. report 应包含可执行下一步动作（命令或配置建议）
4. 非 blocking 但用户应看到的 DB 证据异常（例如 optimize 的 `EXPLAIN` 语法错误）应进入：
   - `report.json.validation_warnings`
   - `report.summary.md` 的 `## Warnings`
   - `sqlopt-cli verify --summary-only` 的 `warnings`
5. `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR` 表示 optimize 阶段的 DB evidence `EXPLAIN` 因 SQL 语法失败；原始错误仍保留在 proposal 的 `dbEvidenceSummary.explainError`

## 9. 诊断规则包约定
默认：
1. `diagnostics.rulepacks=[{builtin: core}, {builtin: performance}]`
2. `diagnostics.severity_overrides={}`
3. `diagnostics.disabled_rules=[]`

当前支持：
1. 内置规则包只支持 `core` 与 `performance`
2. `diagnostics.rulepacks` 也支持 `file: <path>`，路径相对配置文件解析
3. 外部规则文件第一阶段只支持声明式规则：
   - `match.sql_contains`
   - `match.sql_regex`
   - `match.statement_type_is`
   - `match.dynamic_feature_has`
   - `action.suggestion_sql_template`
   - `action.block_actionability`
4. `severity_overrides` 允许按规则 ID 覆盖为 `info | warn | error`
5. `disabled_rules` 会直接从提案诊断中移除对应规则

边界：
1. 第一阶段仅支持声明式规则包（内置与文件），不执行用户自定义代码
2. 规则严重级别会影响 issue 呈现，但不会绕过底层安全约束（例如 `${}` 仍会降低可落地性）

## 10. 架构分层约定
当前默认分层：
1. `models`：只定义内部文档对象与稳定导出 facade，不负责流程编排
2. `policy / selection / builder / loader`：负责规则、聚合、读取，不直接持久化稳定契约
3. `writer / stage`：负责 `to_contract()`、schema 校验和最终落盘

依赖方向：
1. `models` 不能反向依赖 `builder / writer / stage / policy`
2. facade 模块（如 `platforms/sql/models.py`、`stages/report_interfaces.py`）只做 re-export，不承载业务逻辑
3. 新增模型对外导出时统一使用 `to_contract()`，不再引入 `as_dict()` 或 `*_payload()` 命名

当前稳定入口：
1. SQL 模型入口：`sqlopt.platforms.sql.models`
2. Report 模型入口：`sqlopt.stages.report_interfaces`
