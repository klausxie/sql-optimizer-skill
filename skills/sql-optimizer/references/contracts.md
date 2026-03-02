- 契约文件位于 `contracts/*.schema.json`。
- 每个阶段输出在落盘最终产物前都要先做校验。

与代码保持一致的运行时配置补充：

1. `llm.provider` 支持：
- `opencode_run`
- `direct_openai_compatible`
- `opencode_builtin`
- `heuristic`

2. 当 `llm.provider=direct_openai_compatible` 时，必填配置键：
- `llm.api_base`
- `llm.api_key`
- `llm.api_model`

3. direct provider 可选配置键：
- `llm.api_timeout_ms`（正整数）
- `llm.api_headers`（`object<string,string>`）

4. `report.enabled` 默认值为 `true`；report 可以独立于 `to_stage` 做最终收口。
