# 配置与工程约定（v1 极简）

## 1. 外部配置边界
用户可配置主根键：
1. `project`
2. `scan`
3. `db`
4. `llm`
5. `report`
6. `config_version`

用户可配置扩展根键（可选）：
1. `rules`
2. `prompt_injections`

命名约束：
1. 全部使用 `snake_case`
2. 非 snake_case 视为配置错误

已移除且不再支持（出现即报错）：
1. `validate`
2. `policy`
3. `apply`
4. `patch`
5. `diagnostics`
6. `runtime`
7. `verification`

## 2. 必填与类型
必填：
1. `project.root_path`（非空字符串）
2. `scan.mapper_globs`（非空字符串数组）
3. `db.platform`（`postgresql | mysql`）
4. `db.dsn`（非空字符串）
5. `llm.provider`（`opencode_run | direct_openai_compatible | opencode_builtin | heuristic`）

可选：
1. `llm.enabled`（默认 `true`）
2. `llm.timeout_ms`
3. `llm.opencode_model`
4. `db.schema`（非默认 schema/database 时建议显式配置）
5. `llm.api_*` 与 `llm.api_headers`（仅 `direct_openai_compatible`）
6. `report.enabled`（默认 `true`）
7. `rules.*`（自定义/开关规则）
8. `prompt_injections.*`（LLM 提示注入）

## 3. 内置固定策略（不再外露）
以下配置已收敛为内部固定常量：
1. validate 策略（profile / selection / evidence gate）
2. policy 阈值与安全口径
3. runtime 超时与重试
4. apply 模式（默认 `PATCH_ONLY`）
5. diagnostics / verification / patch 辅助策略

说明：
1. `load_config` 会把这些内部字段注入 `config.resolved.json`
2. 用户不再通过 `sqlopt.yml` 修改上述策略

## 4. LLM Provider
`llm.provider` 支持：
1. `opencode_run`
2. `direct_openai_compatible`
3. `opencode_builtin`
4. `heuristic`

约束：
1. `direct_openai_compatible` 必须配置 `api_base/api_key/api_model`
2. `opencode_run` 与 `direct_openai_compatible` 保持严格失败语义

## 5. 数据库平台
`db.platform` 支持：
1. `postgresql`
2. `mysql`

边界：
1. MySQL 支持 5.6+（含 5.7、8.0+）
2. 不支持 MariaDB
3. MySQL 5.6 不支持 `MAX_EXECUTION_TIME` 时会自动降级，不阻塞 evidence / compare
4. 若 SQL 或候选含 MySQL 不支持的 PostgreSQL 方言（例如 `ILIKE`），按语法错误处理并在报告中暴露

## 6. 运行目录规范
统一路径：
1. `<project.root_path>/runs/<run-id>/`

核心产物：
1. `manifest.jsonl`
2. `scan.sqlunits.jsonl`
3. `scan.fragments.jsonl`
4. `proposals/optimization.proposals.jsonl`
5. `acceptance/acceptance.results.jsonl`
6. `patches/patch.results.jsonl`
7. `report.md`
8. `report.summary.md`
9. `report.json`
10. `ops/health.json`
11. `ops/topology.json`

## 7. 补丁与回滚约定
1. 默认 `PATCH_ONLY`，`apply` 不会隐式修改源码
2. 每个 `PatchResult` 必须提供 `rollback`
3. 生成 patch 文件应可通过 `git apply --check`

## 8. 架构分层约定
当前默认分层：
1. `models`：只定义内部文档对象与稳定导出 facade，不负责流程编排
2. `policy / selection / builder / loader`：负责规则、聚合、读取，不直接持久化稳定契约
3. `writer / stage`：负责 `to_contract()`、schema 校验和最终落盘

依赖方向：
1. `models` 不能反向依赖 `builder / writer / stage / policy`
2. facade 模块只做 re-export，不承载业务逻辑
3. 新增模型对外导出统一使用 `to_contract()`
