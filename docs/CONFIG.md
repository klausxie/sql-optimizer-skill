# SQL Optimizer 配置参考

本文档提供 SQL Optimizer 的完整配置说明。

## 配置架构

SQL Optimizer 采用两层配置系统：

```
用户配置 (5个根键)  ──→ 注入默认 ──→ 解析配置 (12个根键)
     ↓                                      ↓
  sqlopt.yml                     runs/<run_id>/config.resolved.json
```

**设计原则：**
1. 用户配置简洁稳定（仅 5 个根键）
2. 内部配置全面灵活（7 个自动注入的根键）
3. 用户无需指定内部配置项
4. 内部配置可独立演进而不影响用户配置

---

## 用户配置 (User-Facing)

用户只需配置以下 5 个根键：

### 1. project - 项目配置

| 配置项 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `root_path` | string | 是 | - | 项目根目录 (支持相对路径，会被解析为绝对路径) |

### 2. scan - 扫描配置

| 配置项 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `mapper_globs` | string[] | 是 | `["**/*Mapper.xml", "**/*.xml"]` | MyBatis XML 文件匹配模式 |

### 3. db - 数据库配置

| 配置项 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `platform` | string | 是 | - | 数据库类型: `postgresql` / `mysql` |
| `dsn` | string | 是 | - | 数据库连接字符串 |
| `schema` | string | 否 | `null` | 数据库 schema 名称 |

**支持的数据库：**
- `postgresql` - PostgreSQL (推荐)
- `mysql` - MySQL 5.6+ (包括 5.7, 8.0+)

**DSN 格式：**
```
postgresql://user:pass@host:port/dbname?sslmode=disable
mysql://user:pass@host:port/dbname
```

### 4. llm - LLM 配置

| 配置项 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `enabled` | boolean | 否 | `true` | 是否启用 LLM |
| `provider` | string | 否 | `opencode_builtin` | LLM 提供商 |
| `timeout_ms` | int | 否 | `15000` | LLM 请求超时 (毫秒) |
| `opencode_model` | string | 否 | `null` | OpenCode 模型名称 |
| `api_base` | string | 否 | `null` | OpenAI 兼容 API 地址 |
| `api_key` | string | 否 | `null` | API 密钥 |
| `api_model` | string | 否 | `null` | API 模型名称 |
| `api_timeout_ms` | int | 否 | `null` | API 请求超时 |
| `api_headers` | object | 否 | `null` | API 请求头 |

**LLM Provider 选项：**

| Provider | 说明 | 适用场景 |
|----------|------|----------|
| `opencode_run` | 外部 opencode run 命令 (推荐) | 生产环境 |
| `opencode_builtin` | 本地内置策略 | 离线测试 |
| `heuristic` | 简化启发式策略 | 快速验证 |
| `direct_openai_compatible` | OpenAI 兼容 API | 自定义 LLM |

**使用 direct_openai_compatible 时的必需配置：**
- `api_base` - API 端点地址
- `api_key` - API 密钥
- `api_model` - 模型名称

### 5. report - 报告配置

| 配置项 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `enabled` | boolean | 否 | `true` | 是否生成报告 |

### 6. rules - 规则配置

| 配置项 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `enabled` | boolean | 否 | `true` | 启用规则系统 |
| `custom_rules_path` | string | 否 | `null` | 自定义规则 YAML 文件路径 |
| `custom_rules` | object[] | 否 | `[]` | 内联自定义规则 |
| `builtin_rules` | object | 否 | 见下文 | 控制内置规则启用状态 |

**内置规则默认配置：**

```yaml
rules:
  builtin_rules:
    DOLLAR_SUBSTITUTION: true
    SELECT_STAR: true
    FULL_SCAN_RISK: true
```

可用内置规则：
- `DOLLAR_SUBSTITUTION` - 检测 `${}` 动态替换
- `SELECT_STAR` - 检测 SELECT * 用法
- `FULL_SCAN_RISK` - 检测无 WHERE 子句的全表扫描
- `SUBQUERY_IN_FROM` - 检测 FROM 子句子查询
- `OR_CONDITION_NO_INDEX` - 检测 OR 条件
- `FUNCTION_ON_INDEXED_COL` - 检测函数导致索引失效
- `LIKE_WILDCARD_START` - 检测 LIKE % 开头
- `NO_LIMIT` - 检测无 LIMIT
- `JOIN_WITHOUT_ON` - 检测 JOIN 无 ON 条件
- `DISTINCT_ABUSE` - 检测 DISTINCT 滥用
- `ORDER_BY_RANDOM` - 检测 ORDER BY RAND()
- `SENSITIVE_COLUMN_EXPOSED` - 检测敏感字段暴露

---

## 内部配置 (Internal - 自动注入)

以下配置由系统自动注入，用户无需配置：

### 7. apply - 应用模式

```yaml
apply:
  mode: PATCH_ONLY  # PATCH_ONLY | AUTO_APPLY
```

| 值 | 说明 |
|---|------|
| `PATCH_ONLY` | 仅生成补丁文件 |
| `AUTO_APPLY` | 自动应用补丁 |

### 8. policy - 优化策略

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `require_perf_improvement` | boolean | `false` | 是否要求性能提升才接受优化 |
| `cost_threshold_pct` | int | `0` | 成本降低阈值百分比 (0=不检查) |
| `allow_seq_scan_if_rows_below` | int | `0` | 允许顺序扫描的行数上限 |
| `semantic_strict_mode` | boolean | `true` | 语义严格模式 (不允许语义差异) |

### 9. validate - 验证策略

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `db_reachable` | boolean | `true` | 数据库是否可达 |
| `plan_compare_enabled` | boolean | `false` | 是否启用执行计划比较 |
| `allow_db_unreachable_fallback` | boolean | `true` | 数据库不可达时是否回退到其他验证方式 |
| `validation_profile` | string | `balanced` | 验证配置: balanced/fast/thorough |
| `selection_mode` | string | `patchability_first` | 候选选择模式 |
| `require_semantic_match` | boolean | `true` | 是否要求语义匹配 |
| `require_perf_evidence_for_pass` | boolean | `false` | 是否要求性能证据才能通过 |
| `require_verified_evidence_for_pass` | boolean | `false` | 是否要求验证证据才能通过 |
| `delivery_bias` | string | `conservative` | 交付倾向: conservative/aggressive |
| `llm_semantic_check.enabled` | boolean | `false` | 启用 LLM 语义检查 |
| `llm_semantic_check.only_on_db_mismatch` | boolean | `true` | 仅在 DB 验证不匹配时使用 LLM |

### 10. patch - 补丁生成

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `llm_assist.enabled` | boolean | `false` | 启用 LLM 辅助生成动态 SQL 补丁 |
| `llm_assist.only_for_dynamic_sql` | boolean | `true` | 仅用于动态 SQL (含 foreach/if 等标签) |
| `llm_assist.generate_template_suggestions` | boolean | `true` | 生成模板重写建议 |

### 11. diagnostics - 诊断配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `rulepacks` | object[] | 见下文 | 启用的规则包 |
| `loaded_rulepacks` | object[] | `[]` | 已加载的规则包 |
| `severity_overrides` | object | `{}` | 规则严重级别覆盖 |
| `disabled_rules` | string[] | `[]` | 禁用的规则 ID 列表 |
| `llm_feedback.enabled` | boolean | `false` | 启用 LLM 反馈收集 |
| `llm_feedback.log_detected_issues` | boolean | `true` | 记录检测到的问题 |
| `llm_feedback.auto_learn_patterns` | boolean | `false` | 自动学习模式 |

**默认规则包：**
```yaml
rulepacks:
  - builtin: core      # 核心规则
  - builtin: performance  # 性能规则
```

### 12. runtime - 运行时配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `stage_timeout_ms.preflight` | int | `12000` | preflight 阶段超时 (毫秒) |
| `stage_timeout_ms.scan` | int | `60000` | scan 阶段超时 |
| `stage_timeout_ms.optimize` | int | `60000` | optimize 阶段超时 |
| `stage_timeout_ms.validate` | int | `60000` | validate 阶段超时 |
| `stage_timeout_ms.apply` | int | `15000` | apply 阶段超时 |
| `stage_timeout_ms.report` | int | `15000` | report 阶段超时 |
| `stage_retry_max.preflight` | int | `1` | preflight 最大重试次数 |
| `stage_retry_max.scan` | int | `1` | scan 最大重试次数 |
| `stage_retry_max.optimize` | int | `1` | optimize 最大重试次数 |
| `stage_retry_max.validate` | int | `1` | validate 最大重试次数 |
| `stage_retry_max.apply` | int | `1` | apply 最大重试次数 |
| `stage_retry_max.report` | int | `1` | report 最大重试次数 |
| `stage_retry_backoff_ms` | int | `1000` | 重试退避时间 (毫秒) |

### 13. verification - 验证配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enforce_verified_outputs` | boolean | `false` | 强制要求所有输出经过验证 |
| `critical_output_policy` | string | `warn` | 关键输出未验证时的策略: warn/block |

---

## 配置示例

### 最小配置

```yaml
config_version: v1

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: postgresql
  dsn: postgresql://user:pass@127.0.0.1:5432/db?sslmode=disable

llm:
  enabled: true
  provider: opencode_run
```

### 完整配置

```yaml
config_version: v1

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml
    - src/main/java/**/*Mapper.xml

db:
  platform: postgresql
  dsn: postgresql://user:pass@127.0.0.1:5432/mydb?sslmode=disable
  schema: public

llm:
  enabled: true
  provider: opencode_run
  timeout_ms: 30000
  opencode_model: claude-sonnet-4-20250514

report:
  enabled: true
```

### 使用 OpenAI 兼容 API

```yaml
config_version: v1

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: mysql
  dsn: mysql://root:password@localhost:3306/mydb

llm:
  enabled: true
  provider: direct_openai_compatible
  api_base: https://api.openai.com/v1
  api_key: sk-xxxxx
  api_model: gpt-4
  api_timeout_ms: 60000
```

---

## 移除的配置键

以下配置键已在 v1 中移除，不再支持：

| 移除的键 | 原因 | 替代方案 |
|----------|------|----------|
| `validate` | 合并为内部配置 | 系统自动管理 |
| `policy` | 合并为内部配置 | 系统自动管理 |
| `patch` | 合并为内部配置 | 系统自动管理 |
| `diagnostics` | 合并为内部配置 | 系统自动管理 |
| `runtime` | 合并为内部配置 | 系统自动管理 |
| `verification` | 合并为内部配置 | 系统自动管理 |
| `apply` | 合并为内部配置 | 系统自动管理 |
| `db.statement_timeout_ms` | 内部实现细节 | 系统自动管理 |
| `db.allow_explain_analyze` | 内部实现细节 | 系统自动管理 |

如果用户配置中包含以上键，系统会返回明确的错误提示。

---

## 配置加载流程

```
1. 读取用户配置文件 (sqlopt.yml)
           ↓
2. 验证用户配置 (仅验证 5 个用户根键)
           ↓
3. 应用默认配置 (apply_minimal_defaults)
   - 填充用户配置的默认值
   - 注入 7 个内部配置节
           ↓
4. 验证解析后的配置 (类型和约束检查)
           ↓
5. 保存到 runs/<run_id>/config.resolved.json
```

---

## 相关文档

- [快速入门指南](QUICKSTART.md) - 首次使用
- [故障排查](TROUBLESHOOTING.md) - 常见问题
- [失败码说明](failure-codes.md) - 错误码含义

---

**最后更新：** 2026-03-07