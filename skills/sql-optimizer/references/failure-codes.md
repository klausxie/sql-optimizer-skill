规范的 `reason_code` 列表请查看 `docs/failure-codes.md`。

常见阻塞问题快速指引：

1. `SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD`
- 含义：`parsed_count / discovered_count < scan.class_resolution.min_success_ratio`。
- 当前 `discovered_count` 逻辑只统计有效 MyBatis mapper XML（`<mapper ... namespace="...">`），非 mapper XML 会跳过。
- 在下调阈值前，先检查 `manifest.jsonl` 与 `scan.sqlunits.jsonl`。

2. `SCAN_SELECTION_SQL_KEY_NOT_FOUND` / `SCAN_SELECTION_SQL_KEY_AMBIGUOUS`
- `--sql-key` 支持完整 `sqlKey`、`namespace.statementId`、`statementId`、`statementId#vN`。
- 如果只给 `statementId` 且命中多个 SQL，CLI 会返回候选 full key；此时改用更具体的 key，而不是猜测。

3. `DB_CONNECTION_FAILED` / `VALIDATE_DB_UNREACHABLE`
- 先执行 `sqlopt-cli validate-config --config sqlopt.yml`。
- 如果 `db.dsn` 还包含 `<user>`、`<password>` 这类占位符，先修配置。
- 若数据库仍不可达，报告降级事实，不要把 validate 结果说成“已完成真实性能验证”。

4. `PREFLIGHT_LLM_UNREACHABLE`
- `opencode_run`：检查 `opencode run --format json --variant minimal "ping"` 和 opencode 配置。
- `direct_openai_compatible`：检查 `llm.api_base/api_key/api_model` 与 endpoint 连通性。
