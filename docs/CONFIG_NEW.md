# SQL Optimizer 配置格式 v2 设计

> 版本: v2 (config_version: v2)
> 状态: 设计中

## 概述

v2 配置格式引入**声明式流水线**和**阶段特定配置**两大核心特性，使用户能够:

1. 显式定义流水线 stages 列表和执行顺序
2. 为每个 stage 提供独立的配置参数
3. 按需启用/禁用特定 stages
4. 集中管理跨阶段的通用配置

## 核心设计

### 1. 声明式流水线 `pipeline.stages[]`

```yaml
pipeline:
  stages:
    - name: discovery
      enabled: true
      config:
        # discovery 阶段特定配置
        parser: standard
        max_sql_length: 10000
        
    - name: branching
      enabled: true
      config:
        # branching 阶段特定配置
        max_branches: 100
        expand_foreach: true
        
    - name: baseline
      enabled: true
      config:
        # baseline 阶段特定配置
        timeout_ms: 30000
        collect_buffer_stats: true
```

### 2. 阶段列表

| Stage | 说明 | 默认启用 |
|-------|------|----------|
| `discovery` | 连接数据库、采集表结构、解析 MyBatis XML | true |
| `branching` | 展开动态标签生成分支路径 | true |
| `pruning` | 静态分析、风险标记、低价值分支过滤 | true |
| `baseline` | EXPLAIN 采集执行计划、记录性能基线 | true |
| `optimize` | 规则引擎 + LLM 生成优化建议 | true |
| `validate` | 语义验证、性能对比、结果集校验 | true |
| `patch` | 生成 XML 补丁、用户确认、应用变更 | true |

## 完整配置示例

```yaml
# ============================================================
# SQL Optimizer 配置 v2
# ============================================================
config_version: v2

project:
  root_path: .

# --- 扫描配置 ---
scan:
  mapper_globs:
    - src/main/resources/**/*.xml
  # 排除特定文件/目录
  exclude_patterns:
    - "**/test/**"
    - "**/*Test*.xml"

# --- 数据库配置 ---
db:
  platform: postgresql
  dsn: postgresql://user:password@127.0.0.1:5432/dbname?sslmode=disable
  schema: public
  statement_timeout_ms: 3000
  allow_explain_analyze: false

# --- LLM 配置 ---
llm:
  enabled: true
  provider: opencode_run
  timeout_ms: 80000
  # OpenAI 兼容配置
  # provider: direct_openai_compatible
  # api_base: https://api.openai.com/v1
  # api_key: sk-xxxx
  # api_model: gpt-4o-mini
  # api_timeout_ms: 30000
  # api_headers:
  #   X-Env: prod

# --- 声明式流水线配置 ---
pipeline:
  # 全局流水线配置
  profile: balanced  # fast | balanced | resilient
  
  # 阶段列表 (按执行顺序)
  stages:
    # ---- 发现阶段 ----
    - name: discovery
      enabled: true
      config:
        # 表结构缓存策略
        cache_schema: true
        cache_ttl_seconds: 3600
        # XML 解析器模式
        parser: standard  # standard | lenient

    # ---- 分支阶段 ----
    - name: branching
      enabled: true
      config:
        # 分支展开限制
        max_branches_per_sql: 100
        max_total_branches: 1000
        # foreach 展开策略
        expand_foreach: true
        foreach_max_iterations: 100
        # 风险检测
        detect_wildcard_risk: true
        detect_concat_risk: true

    # ---- 剪枝阶段 ----
    - name: pruning
      enabled: true
      config:
        # 风险等级阈值
        risk_threshold: medium  # low | medium | high | critical
        # 低价值分支过滤
        filter_low_value_branches: true
        low_value_cost_threshold: 0.01
        # 风险标记
        mark_prefix_wildcard: true
        mark_suffix_wildcard: true
        mark_concat_wildcard: true
        mark_function_wrap: true

    # ---- 基线阶段 ----
    - name: baseline
      enabled: true
      config:
        # 执行超时
        timeout_ms: 30000
        # 性能指标收集
        collect_buffer_stats: true
        collect_index_usage: true
        collect_rows_estimate: true
        # 参数绑定
        bind_params: true
        sample_param_count: 3

    # ---- 优化阶段 ----
    - name: optimize
      enabled: true
      config:
        # 优化策略
        strategy: rule_first  # rule_first | llm_first | hybrid
        # 规则引擎
        rules:
          enabled: true
          builtin_rules:
            - DOLLAR_SUBSTITUTION
            - SELECT_STAR
            - FULL_SCAN_RISK
        # LLM 优化
        llm:
          enabled: true
          temperature: 0.0
          max_candidates: 5
        # 性能阈值
        cost_threshold_pct: 0
        require_perf_improvement: false

    # ---- 验证阶段 ----
    - name: validate
      enabled: true
      config:
        # 验证策略
        validation_profile: balanced  # fast | balanced | thorough
        # 语义验证
        require_semantic_match: true
        semantic_strict_mode: true
        # 性能验证
        require_perf_evidence_for_pass: false
        require_verified_evidence_for_pass: false
        # 数据库验证
        db_reachable: true
        allow_db_unreachable_fallback: false
        plan_compare_enabled: false
        # 交付策略
        delivery_bias: conservative  # conservative | aggressive

    # ---- 补丁阶段 ----
    - name: patch
      enabled: true
      config:
        # 补丁模式
        mode: PATCH_ONLY  # PATCH_ONLY | AUTO_APPLY | REVIEW_ONLY
        # LLM 辅助
        llm_assist:
          enabled: false
          only_for_dynamic_sql: true
          generate_template_suggestions: true
        # 冲突处理
        conflict_resolution: manual  # manual | automatic

# --- 报告配置 ---
report:
  enabled: true
  format: markdown  # markdown | json | html
  include_verification: true
  include_trace: false

# --- 全局设置 (向后兼容) ---
# 以下字段在 v2 中已废弃，请迁移到 pipeline.stages[].config
# - validate.* -> pipeline.stages[validate].config
# - runtime.profile -> pipeline.profile
```

## 字段参考

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `config_version` | string | 是 | 配置版本，填 `v2` |
| `project.root_path` | string | 是 | 项目根路径 |
| `scan.mapper_globs` | string[] | 是 | MyBatis XML 文件匹配模式 |
| `scan.exclude_patterns` | string[] | 否 | 排除的文件模式 |
| `db.platform` | string | 是 | `postgresql` 或 `mysql` |
| `db.dsn` | string | 是 | 数据库连接字符串 |
| `db.schema` | string | 否 | 数据库 schema |
| `db.statement_timeout_ms` | integer | 否 | 语句超时(毫秒) |
| `llm.enabled` | boolean | 否 | 是否启用 LLM (默认 true) |
| `llm.provider` | string | 是 | LLM 提供者 |
| `llm.timeout_ms` | integer | 否 | LLM 调用超时(毫秒) |
| `pipeline` | object | 否 | 流水线配置 |
| `report` | object | 否 | 报告配置 |
| `rules` | object | 否 | 规则配置 (向后兼容) |
| `prompt_injections` | object | 否 | Prompt 注入 (向后兼容) |

### pipeline 对象

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pipeline.profile` | string | 否 | 性能配置: `fast`, `balanced`, `resilient` |
| `pipeline.stages` | Stage[] | 否 | 阶段配置列表 |

### Stage 对象

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `stage.name` | string | 是 | 阶段名称 |
| `stage.enabled` | boolean | 否 | 是否启用 (默认 true) |
| `stage.config` | object | 否 | 阶段特定配置 |

### Stage 特定配置

#### discovery.config

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `cache_schema` | boolean | true | 是否缓存表结构 |
| `cache_ttl_seconds` | integer | 3600 | 缓存 TTL |
| `parser` | string | standard | XML 解析器模式 |

#### branching.config

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_branches_per_sql` | integer | 100 | 单个 SQL 最大分支数 |
| `max_total_branches` | integer | 1000 | 流水线总分支数上限 |
| `expand_foreach` | boolean | true | 是否展开 foreach |
| `foreach_max_iterations` | integer | 100 | foreach 最大迭代次数 |
| `detect_wildcard_risk` | boolean | true | 检测前后通配符风险 |
| `detect_concat_risk` | boolean | true | 检测 CONCAT 通配符风险 |

#### pruning.config

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `risk_threshold` | string | medium | 风险等级阈值 |
| `filter_low_value_branches` | boolean | true | 过滤低价值分支 |
| `low_value_cost_threshold` | float | 0.01 | 低价值分支成本阈值 |
| `mark_prefix_wildcard` | boolean | true | 标记前缀通配符 |
| `mark_suffix_wildcard` | boolean | true | 标记后缀通配符 |
| `mark_concat_wildcard` | boolean | true | 标记 CONCAT 通配符 |
| `mark_function_wrap` | boolean | true | 标记函数包装 |

#### baseline.config

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `timeout_ms` | integer | 30000 | 基线采集超时 |
| `collect_buffer_stats` | boolean | true | 收集缓冲区统计 |
| `collect_index_usage` | boolean | true | 收集索引使用情况 |
| `collect_rows_estimate` | boolean | true | 收集行数估算 |
| `bind_params` | boolean | true | 绑定参数执行 |
| `sample_param_count` | integer | 3 | 样本参数数量 |

#### optimize.config

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `strategy` | string | rule_first | 优化策略 |
| `rules.enabled` | boolean | true | 启用规则引擎 |
| `rules.builtin_rules` | string[] | - | 启用的内置规则 |
| `llm.enabled` | boolean | true | 启用 LLM 优化 |
| `llm.temperature` | float | 0.0 | LLM 温度参数 |
| `llm.max_candidates` | integer | 5 | 最大候选方案数 |
| `cost_threshold_pct` | integer | 0 | 成本阈值百分比 |
| `require_perf_improvement` | boolean | false | 是否要求性能提升 |

#### validate.config

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `validation_profile` | string | balanced | 验证配置: fast/balanced/thorough |
| `require_semantic_match` | boolean | true | 要求语义匹配 |
| `semantic_strict_mode` | boolean | true | 严格语义模式 |
| `require_perf_evidence_for_pass` | boolean | false | 要求性能证据 |
| `require_verified_evidence_for_pass` | boolean | false | 要求验证证据 |
| `db_reachable` | boolean | true | 数据库必须可达 |
| `allow_db_unreachable_fallback` | boolean | false | 允许数据库不可达时回退 |
| `plan_compare_enabled` | boolean | false | 启用计划比较 |
| `delivery_bias` | string | conservative | 交付策略 |

#### patch.config

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `mode` | string | PATCH_ONLY | 补丁模式 |
| `llm_assist.enabled` | boolean | false | 启用 LLM 辅助 |
| `llm_assist.only_for_dynamic_sql` | boolean | true | 仅对动态 SQL |
| `llm_assist.generate_template_suggestions` | boolean | true | 生成模板建议 |
| `conflict_resolution` | string | manual | 冲突解决策略 |

## 向后兼容性

v2 配置格式完全兼容 v1 格式:

```yaml
# v1 格式仍然有效
config_version: v1

project:
  root_path: .
scan:
  mapper_globs:
    - src/**/*.xml
db:
  platform: postgresql
  dsn: postgresql://user:pass@localhost/db
llm:
  provider: opencode_run
```

当检测到 `config_version: v1` 时，系统会自动:
1. 将 `validate.*` 字段映射到 `pipeline.stages[validate].config`
2. 将 `runtime.profile` 映射到 `pipeline.profile`
3. 使用默认阶段列表填充未指定的 stages

## 内部配置 (不暴露给用户)

以下字段由系统内部管理，不应在用户配置中指定:

| 字段 | 说明 |
|------|------|
| `apply` | 补丁应用模式 |
| `policy` | 优化策略 (已迁移到 stage.config) |
| `diagnostics` | 诊断规则包 |
| `verification` | 输出验证策略 |

## 迁移时间线

- **v2 (当前设计)**: 新配置格式，支持声明式流水线
- **v1 (deprecated)**: 旧配置格式，继续支持
- **未来版本**: 可能移除 v1 支持

## 验证规则

配置加载时验证:

1. `config_version` 必须是 `v1` 或 `v2`
2. `pipeline.stages[].name` 必须是有效阶段名
3. 不允许重复的阶段名
4. 阶段配置字段必须符合对应阶段的 schema
5. 未知字段会产生警告 (非错误)
