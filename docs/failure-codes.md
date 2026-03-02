# 失败码（当前实现）

## 1. 分类语义
1. `retryable`
   - 可重试后恢复
2. `degradable`
   - 可继续流程，但结果降级
3. `fatal`
   - 需要修复输入或逻辑后再继续

优先级：
1. 先按 `phase + reason_code` 精确映射
2. 再按全局 `reason_code` 映射
3. 未命中时默认 `fatal`

## 2. 模板相关失败码

### Validate 阶段发出
1. `STATEMENT_TEMPLATE_REPLAY_MISMATCH`
   - where emitted: `validate -> template_materializer`
   - classification: `degradable`
   - default operator action: 保留动态模板，不自动 patch
2. `FRAGMENT_TEMPLATE_REPLAY_MISMATCH`
   - where emitted: `validate -> template_materializer`
   - classification: `degradable`
   - default operator action: 保留片段，不自动 patch
3. `FRAGMENT_MATERIALIZATION_DISABLED`
   - where emitted: `validate -> template_materializer`
   - classification: `degradable`
   - default operator action: 若要启用 fragment 自动 patch，显式打开 feature flag
4. `MULTIPLE_FRAGMENT_BINDINGS_MISMATCH`
   - where emitted: `validate -> template_materializer`
   - classification: `degradable`
   - default operator action: 保留手工处理，不自动 patch
5. `PATCH_FRAGMENT_PROPERTY_CONTEXT_UNSUPPORTED`
   - where emitted: `validate -> template_materializer`
   - classification: `degradable`
   - default operator action: 保留手工处理，不自动 patch
6. `DYNAMIC_SUBTREE_TOUCHED`
   - where emitted: `validate -> template_materializer`
   - classification: `degradable`
   - default operator action: 不自动改写动态子树
7. `ANCHOR_ALIGNMENT_FAILED`
   - where emitted: `validate -> template_materializer`
   - classification: `degradable`
   - default operator action: 保留原模板，要求人工确认

### Patch 阶段发出
1. `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE`
   - where emitted: `patch_generate`
   - classification: `degradable`
   - default operator action: 动态 statement 不直接用扁平 SQL 回写
2. `PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE`
   - where emitted: `patch_generate`
   - classification: `degradable`
   - default operator action: 涉及 include 片段，保守跳过
3. `PATCH_TEMPLATE_MATERIALIZATION_MISSING`
   - where emitted: `patch_generate`
   - classification: `degradable`
   - default operator action: validate 未给出可执行模板计划，不自动 patch
4. `PATCH_FRAGMENT_LOCATOR_AMBIGUOUS`
   - where emitted: `patch_generate`
   - classification: `degradable`
   - default operator action: 缺少稳定片段定位信息，不自动 patch

## 3. 其他常用失败码

### Scan
1. `SCAN_CLASS_RESOLUTION_DEGRADED` -> `degradable`
2. `SCAN_CLASS_NOT_FOUND` -> `degradable`
3. `SCAN_TYPE_ATTR_SANITIZED` -> `degradable`
4. `SCAN_STATEMENT_PARSE_DEGRADED` -> `degradable`
5. `SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD` -> `fatal`
6. `SCAN_XML_PARSE_FATAL` -> `fatal`
7. `SCAN_MAPPER_NOT_FOUND` -> `fatal`
8. `SCAN_UNKNOWN_EXIT` -> `fatal`

### Preflight
1. `PREFLIGHT_CHECK_FAILED` -> `fatal`
2. `PREFLIGHT_DB_UNREACHABLE` -> `fatal`
3. `PREFLIGHT_LLM_UNREACHABLE` -> `fatal`
4. `PREFLIGHT_SCANNER_MISSING` -> `fatal`

### Validate
1. `VALIDATE_DB_UNREACHABLE` -> `degradable`
2. `VALIDATE_PARAM_INSUFFICIENT` -> `degradable`
3. `VALIDATE_PERF_NOT_IMPROVED` -> `degradable`
4. `VALIDATE_PERF_NOT_IMPROVED_WARN` -> `degradable`
5. `VALIDATE_SEMANTIC_ERROR` -> `degradable`
6. `VALIDATE_SECURITY_DOLLAR_SUBSTITUTION` -> `degradable`
7. `VALIDATE_EQUIVALENCE_MISMATCH` -> `fatal`
8. `VALIDATE_TIMEOUT` -> `retryable`

### Patch
1. `PATCH_CONFLICT_NO_CLEAR_WINNER` -> `degradable`
2. `PATCH_NOT_APPLICABLE` -> `degradable`
3. `PATCH_NO_EFFECTIVE_CHANGE` -> `degradable`
4. `PATCH_LOCATOR_AMBIGUOUS` -> `degradable`
5. `PATCH_BLOCKED_BY_SEMANTIC_RISK` -> `fatal`
6. `PATCH_GENERATION_ERROR` -> `retryable`

### Runtime / Global
1. `RUNTIME_STAGE_TIMEOUT` -> `retryable`
2. `RUNTIME_RETRY_EXHAUSTED` -> `retryable`
3. `RUNTIME_SCHEMA_VALIDATION_FAILED` -> `fatal`
4. `UNSUPPORTED_PLATFORM` -> `fatal`

## 4. 备注
1. `SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD`
   - 触发条件：`parsed_count / discovered_count < scan.class_resolution.min_success_ratio`
2. `PREFLIGHT_LLM_UNREACHABLE`
   - 同时适用于 `opencode_run` 与 `direct_openai_compatible`
