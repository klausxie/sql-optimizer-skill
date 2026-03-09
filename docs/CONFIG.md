# SQL Optimizer 配置参考（v1）

本文档是配置边界的单一事实来源（source of truth）。

## 1. 用户可配置边界

### 1.1 主根键（稳定）

用户配置文件（`sqlopt.yml`）主根键如下：

1. `config_version`
2. `project`
3. `scan`
4. `db`
5. `llm`
6. `report`

### 1.2 扩展根键（可选）

在主根键之外，支持两个扩展根键：

1. `rules`
2. `prompt_injections`

### 1.3 已移除根键（出现即报错）

以下根键在 v1 已移除，不再支持：

- `validate`
- `policy`
- `apply`
- `patch`
- `diagnostics`
- `runtime`
- `verification`

## 2. 主根键字段

### 2.1 `project`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `root_path` | string | 是 | 项目根目录，支持相对路径 |

### 2.2 `scan`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `mapper_globs` | string[] | 是 | MyBatis XML 匹配模式，必须非空 |

### 2.3 `db`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `platform` | string | 是 | `postgresql` 或 `mysql` |
| `dsn` | string | 是 | 数据库连接串 |
| `schema` | string/null | 否 | PostgreSQL 非默认 schema 时建议显式设置 |

说明：

- MySQL 支持 5.6+（含 5.7、8.0+），不支持 MariaDB。
- MySQL 场景遇 PostgreSQL 方言（如 `ILIKE`）时，不做自动改写，会按语法错误上报。

### 2.4 `llm`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `provider` | string | 是 | `opencode_run` / `direct_openai_compatible` / `opencode_builtin` / `heuristic` |
| `enabled` | bool | 否 | 默认 `true` |
| `timeout_ms` | int | 否 | 请求超时（毫秒） |
| `opencode_model` | string/null | 否 | `opencode_run` 可选模型名 |
| `api_base` | string/null | 条件必填 | 仅 `direct_openai_compatible` |
| `api_key` | string/null | 条件必填 | 仅 `direct_openai_compatible` |
| `api_model` | string/null | 条件必填 | 仅 `direct_openai_compatible` |
| `api_timeout_ms` | int/null | 否 | 仅 `direct_openai_compatible` |
| `api_headers` | object/null | 否 | 仅 `direct_openai_compatible` |

### 2.5 `report`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `enabled` | bool | 否 | 默认 `true` |

## 3. 扩展根键字段

### 3.1 `rules`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `enabled` | bool | 否 | 是否启用规则系统 |
| `custom_rules_path` | string/null | 否 | 外部规则文件路径 |
| `custom_rules` | array | 否 | 内联规则列表 |
| `builtin_rules` | object | 否 | 内置规则启停开关 |

### 3.2 `prompt_injections`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `system` | array | 否 | 全局系统提示 |
| `by_rule` | array | 否 | 按规则触发的提示 |

## 4. 内部注入配置（不可在用户配置中声明）

运行时会在 `config.resolved.json` 注入内部节：

- `apply`
- `policy`
- `validate`
- `patch`
- `diagnostics`
- `runtime`
- `verification`

这些节是执行层实现细节，不是用户配置边界。

## 5. 加载与校验流程

1. 读取 `sqlopt.yml`
2. 校验用户配置根键与字段（含已移除键拦截）
3. 补齐默认值
4. 注入内部节
5. 写入 `runs/<run_id>/config.resolved.json`

## 6. 示例

### 6.1 最小配置

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
  provider: opencode_run

report:
  enabled: true
```

### 6.2 启用扩展键示例

```yaml
config_version: v1

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: mysql
  dsn: mysql://user:pass@127.0.0.1:3306/db

llm:
  provider: direct_openai_compatible
  api_base: https://api.openai.com/v1
  api_key: sk-xxxx
  api_model: gpt-4o-mini

report:
  enabled: true

rules:
  builtin_rules:
    SELECT_STAR: false

prompt_injections:
  system:
    - role: system
      content: "优先给出可安全落地的改写建议。"
```

## 7. 相关文档

- [快速入门](QUICKSTART.md)
- [安装指南](INSTALL.md)
- [故障排查](TROUBLESHOOTING.md)
- [配置与工程约定](project/05-config-and-conventions.md)
