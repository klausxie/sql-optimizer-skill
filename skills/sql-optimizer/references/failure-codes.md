规范的 `reason_code` 列表请查看 `docs/failure-codes.md`。

常见阻塞问题快速指引：

1. `SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD`
- 含义：`parsed_count / discovered_count < scan.class_resolution.min_success_ratio`。
- 当前 `discovered_count` 逻辑只统计有效 MyBatis mapper XML（`<mapper ... namespace="...">`），非 mapper XML 会跳过。
- 在下调阈值前，先检查 `manifest.jsonl` 与 `scan.sqlunits.jsonl`。

2. `PREFLIGHT_LLM_UNREACHABLE`
- `opencode_run`：检查 `opencode run --format json --variant minimal "ping"` 和 opencode 配置。
- `direct_openai_compatible`：检查 `llm.api_base/api_key/api_model` 与 endpoint 连通性。
